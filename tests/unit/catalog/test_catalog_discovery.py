"""C-03: media discovery registration and provenance merge (CT-MED-001)."""
import dataclasses
import json
import pathlib
import unittest

from catalog.application.discovery import DiscoveryObservation, DiscoveryResult, Disposition, register_discovery
from catalog.domain.identity import CanonicalFingerprint, MediaAsset, MediaKind, ProvenanceEntry, ProvenanceRelation

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'i-artifact-version' / 'payloads.json'


def fixture_fingerprint() -> CanonicalFingerprint:
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    valid = data['entities']['DeclareArtifactVersionRequest']['valid']
    return CanonicalFingerprint(valid[0]['content_sha256'])


def make_entry(article_ref: str = 'article-1') -> ProvenanceEntry:
    return ProvenanceEntry(
        source_ref='source-1',
        article_ref=article_ref,
        event_ref='event-1',
        original_locator=f'https://example.test/{article_ref}/hero.jpg',
        observed_at='2026-10-18T00:00:00Z',
        relation=ProvenanceRelation.HERO_IMAGE,
    )


def make_observation(
    discovery_id: str = 'discovery-1',
    article_ref: str = 'article-1',
    fingerprint: CanonicalFingerprint | None = None,
    locator_validated: bool = True,
) -> DiscoveryObservation:
    return DiscoveryObservation(
        discovery_id=discovery_id,
        kind=MediaKind.IMAGE,
        provenance=make_entry(article_ref),
        fingerprint=fingerprint,
        locator_validated=locator_validated,
    )


class FakeMediaAssetRepository:
    """In-memory MediaAssetRepository that records every call."""

    def __init__(self) -> None:
        self.assets: dict[str, MediaAsset] = {}
        self.discoveries: dict[str, str] = {}
        self.calls: list[str] = []
        self.saves: list[tuple[MediaAsset, str | None]] = []

    def get(self, media_asset_id: str) -> MediaAsset | None:
        self.calls.append('get')
        return self.assets.get(media_asset_id)

    def find_by_fingerprint(self, fingerprint: CanonicalFingerprint) -> MediaAsset | None:
        self.calls.append('find_by_fingerprint')
        return next((a for a in self.assets.values() if a.fingerprint == fingerprint), None)

    def find_by_discovery_id(self, discovery_id: str) -> MediaAsset | None:
        self.calls.append('find_by_discovery_id')
        asset_id = self.discoveries.get(discovery_id)
        return None if asset_id is None else self.assets[asset_id]

    def save(self, asset: MediaAsset, discovery_id: str | None = None) -> None:
        self.calls.append('save')
        self.saves.append((asset, discovery_id))
        self.assets[asset.media_asset_id] = asset
        if discovery_id is not None:
            self.discoveries[discovery_id] = asset.media_asset_id


class DispositionEnumTests(unittest.TestCase):
    def test_disposition_values(self) -> None:
        self.assertEqual({d.value for d in Disposition}, {'new_asset', 'new_provenance', 'duplicate_observation', 'rejected'})


class RepostProvenanceTests(unittest.TestCase):
    def test_repost_same_fingerprint_other_article_appends_provenance(self) -> None:
        repo = FakeMediaAssetRepository()
        fingerprint = fixture_fingerprint()
        first = register_discovery(repo, make_observation('discovery-1', 'article-1', fingerprint), 'asset-1')
        self.assertEqual(first, DiscoveryResult('asset-1', Disposition.NEW_ASSET, False))
        repost = register_discovery(repo, make_observation('discovery-2', 'article-2', fingerprint), 'asset-2')
        self.assertEqual(repost, DiscoveryResult('asset-1', Disposition.NEW_PROVENANCE, False))
        self.assertEqual(list(repo.assets), ['asset-1'])
        stored = repo.assets['asset-1']
        self.assertEqual(stored.provenance, (make_entry('article-1'), make_entry('article-2')))
        self.assertEqual(stored.fingerprint, fingerprint)
        self.assertEqual(repo.discoveries, {'discovery-1': 'asset-1', 'discovery-2': 'asset-1'})

    def test_same_fingerprint_and_provenance_is_duplicate_observation(self) -> None:
        repo = FakeMediaAssetRepository()
        fingerprint = fixture_fingerprint()
        register_discovery(repo, make_observation('discovery-1', 'article-1', fingerprint), 'asset-1')
        self.assertEqual(len(repo.saves), 1)
        again = register_discovery(repo, make_observation('discovery-2', 'article-1', fingerprint), 'asset-2')
        self.assertEqual(again, DiscoveryResult('asset-1', Disposition.DUPLICATE_OBSERVATION, False))
        self.assertEqual(len(repo.saves), 1)
        self.assertEqual(list(repo.assets), ['asset-1'])
        self.assertEqual(repo.assets['asset-1'].provenance, (make_entry('article-1'),))


class DiscoveryIdempotencyTests(unittest.TestCase):
    def test_resent_discovery_id_returns_same_asset_without_new_record(self) -> None:
        for fingerprint in (fixture_fingerprint(), None):
            with self.subTest(fingerprint=fingerprint):
                repo = FakeMediaAssetRepository()
                observation = make_observation('discovery-1', 'article-1', fingerprint)
                first = register_discovery(repo, observation, 'asset-1')
                self.assertEqual(first.disposition, Disposition.NEW_ASSET)
                again = register_discovery(repo, observation, 'asset-2')
                self.assertEqual(again, DiscoveryResult('asset-1', Disposition.DUPLICATE_OBSERVATION, fingerprint is None))
                self.assertEqual(list(repo.assets), ['asset-1'])
                self.assertEqual(len(repo.saves), 1)
                self.assertEqual(repo.assets['asset-1'].provenance, (make_entry('article-1'),))


class LocatorValidationTests(unittest.TestCase):
    def test_unvalidated_locator_is_rejected_without_save(self) -> None:
        for fingerprint in (fixture_fingerprint(), None):
            with self.subTest(fingerprint=fingerprint):
                repo = FakeMediaAssetRepository()
                observation = make_observation(fingerprint=fingerprint, locator_validated=False)
                result = register_discovery(repo, observation, 'asset-1')
                self.assertEqual(result, DiscoveryResult(None, Disposition.REJECTED, False))
                self.assertNotIn('save', repo.calls)
                self.assertEqual((repo.saves, repo.assets, repo.discoveries), ([], {}, {}))

    def test_unvalidated_repost_does_not_touch_existing_asset(self) -> None:
        repo = FakeMediaAssetRepository()
        fingerprint = fixture_fingerprint()
        register_discovery(repo, make_observation('discovery-1', 'article-1', fingerprint), 'asset-1')
        self.assertEqual(len(repo.saves), 1)
        observation = make_observation('discovery-2', 'article-2', fingerprint, locator_validated=False)
        self.assertEqual(register_discovery(repo, observation, 'asset-2').disposition, Disposition.REJECTED)
        self.assertEqual(len(repo.saves), 1)
        self.assertEqual(repo.assets['asset-1'].provenance, (make_entry('article-1'),))
        self.assertNotIn('discovery-2', repo.discoveries)


class NewAssetTests(unittest.TestCase):
    def test_new_asset_acquisition_required_only_without_fingerprint(self) -> None:
        for fingerprint, expected in ((fixture_fingerprint(), False), (None, True)):
            with self.subTest(fingerprint=fingerprint):
                repo = FakeMediaAssetRepository()
                result = register_discovery(repo, make_observation(fingerprint=fingerprint), 'asset-1')
                self.assertEqual(result, DiscoveryResult('asset-1', Disposition.NEW_ASSET, expected))
                self.assertEqual(len(repo.saves), 1)
                saved, discovery_id = repo.saves[0]
                self.assertEqual(discovery_id, 'discovery-1')
                self.assertEqual((saved.media_asset_id, saved.kind, saved.fingerprint), ('asset-1', MediaKind.IMAGE, fingerprint))
                self.assertEqual(saved.provenance, (make_entry('article-1'),))

    def test_unfingerprinted_discoveries_never_merge(self) -> None:
        repo = FakeMediaAssetRepository()
        self.assertEqual(register_discovery(repo, make_observation('discovery-1', 'article-1'), 'asset-1').disposition, Disposition.NEW_ASSET)
        second = register_discovery(repo, make_observation('discovery-2', 'article-2'), 'asset-2')
        self.assertEqual(second, DiscoveryResult('asset-2', Disposition.NEW_ASSET, True))
        self.assertEqual(sorted(repo.assets), ['asset-1', 'asset-2'])

    def test_different_fingerprint_creates_new_asset(self) -> None:
        repo = FakeMediaAssetRepository()
        register_discovery(repo, make_observation('discovery-1', 'article-1', fixture_fingerprint()), 'asset-1')
        other = CanonicalFingerprint('f' * 64)
        result = register_discovery(repo, make_observation('discovery-2', 'article-1', other), 'asset-2')
        self.assertEqual(result, DiscoveryResult('asset-2', Disposition.NEW_ASSET, False))
        self.assertEqual(repo.assets['asset-1'].provenance, (make_entry('article-1'),))


class ObservationValidationTests(unittest.TestCase):
    def test_observation_rejects_invalid_fields(self) -> None:
        bad = (('discovery_id', ''), ('kind', 'image'), ('provenance', None), ('fingerprint', '0' * 64), ('locator_validated', 'yes'))
        for field, value in bad:
            with self.subTest(field=field):
                fields = {'discovery_id': 'discovery-1', 'kind': MediaKind.IMAGE, 'provenance': make_entry(), 'fingerprint': None, 'locator_validated': True}
                fields[field] = value
                with self.assertRaises(ValueError):
                    DiscoveryObservation(**fields)

    def test_observation_and_result_are_frozen(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            make_observation().locator_validated = False
        with self.assertRaises(dataclasses.FrozenInstanceError):
            DiscoveryResult('asset-1', Disposition.NEW_ASSET, False).disposition = Disposition.REJECTED
