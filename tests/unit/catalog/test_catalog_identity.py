"""C-01: catalog package skeleton and media identity (MediaAsset, fingerprint, provenance, rights)."""
import ast
import dataclasses
import importlib
import importlib.util
import inspect
import json
import pathlib
import typing
import unittest

from catalog.domain.identity import (
    CanonicalFingerprint,
    MediaAsset,
    MediaKind,
    ProvenanceEntry,
    ProvenanceRelation,
    RightsAssessment,
    RightsStatus,
)
from catalog.ports.repositories import MediaAssetRepository

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGE_DIR = ROOT / 'src' / 'catalog'
SUBPACKAGES = ('domain', 'application', 'ports')
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'i-artifact-version' / 'payloads.json'
VALID_HEX = '0123456789abcdef' * 4
OTHER_HEX = 'f' * 64


def load_request_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    return data['entities']['DeclareArtifactVersionRequest']


def make_entry(article_ref: str = 'article-1') -> ProvenanceEntry:
    return ProvenanceEntry(
        source_ref='source-1',
        article_ref=article_ref,
        event_ref='event-1',
        original_locator=f'https://example.test/{article_ref}/hero.jpg',
        observed_at='2026-10-18T00:00:00Z',
        relation=ProvenanceRelation.HERO_IMAGE,
    )


def make_asset(**overrides: object) -> MediaAsset:
    fields: dict[str, object] = {
        'media_asset_id': 'asset-1',
        'kind': MediaKind.IMAGE,
        'fingerprint': None,
        'provenance': (make_entry(),),
        'rights': RightsAssessment(status=RightsStatus.UNKNOWN, evidence_refs=()),
        'index_revision': 1,
    }
    fields.update(overrides)
    return MediaAsset(**fields)


class EnumValueTests(unittest.TestCase):
    def test_enum_value_sets(self) -> None:
        self.assertEqual({m.value for m in MediaKind}, {'image', 'clip', 'audio'})
        self.assertEqual({s.value for s in RightsStatus}, {'known', 'unknown', 'disputed'})
        self.assertEqual(
            {r.value for r in ProvenanceRelation},
            {'hero_image', 'inline_image', 'embedded_clip', 'official_social_clip', 'user_imported', 'ai_generated'},
        )


class CanonicalFingerprintTests(unittest.TestCase):
    def test_accepts_64_lowercase_hex(self) -> None:
        self.assertEqual(CanonicalFingerprint(VALID_HEX).value, VALID_HEX)

    def test_rejects_non_canonical_values(self) -> None:
        for bad in (VALID_HEX.upper(), VALID_HEX[:-1], VALID_HEX + '0', 'g' * 64, VALID_HEX[:-1] + '\n', '', None, 123):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    CanonicalFingerprint(bad)

    def test_fingerprint_is_frozen(self) -> None:
        fingerprint = CanonicalFingerprint(VALID_HEX)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            fingerprint.value = OTHER_HEX


class FixtureBindingTests(unittest.TestCase):
    def test_valid_payload_content_sha256_is_accepted(self) -> None:
        valid = load_request_fixture()['valid']
        self.assertTrue(valid, 'fixture has no valid DeclareArtifactVersionRequest payload')
        for payload in valid:
            with self.subTest(content_sha256=payload['content_sha256']):
                fingerprint = CanonicalFingerprint(payload['content_sha256'])
                self.assertEqual(fingerprint.value, payload['content_sha256'])
                self.assertEqual(make_asset().with_fingerprint(fingerprint).fingerprint, fingerprint)

    def test_uppercase_content_hash_case_is_rejected(self) -> None:
        cases = {case['case']: case for case in load_request_fixture()['invalid']}
        self.assertIn('content_hash_uppercase', cases)
        case = cases['content_hash_uppercase']
        self.assertEqual(case['expected_error']['field'], 'content_sha256')
        with self.assertRaises(ValueError):
            CanonicalFingerprint(case['payload']['content_sha256'])


class MediaAssetFingerprintTests(unittest.TestCase):
    def test_attribute_assignment_raises_frozen_instance_error(self) -> None:
        asset = make_asset()
        replacements = {
            'media_asset_id': 'asset-2',
            'kind': MediaKind.CLIP,
            'fingerprint': CanonicalFingerprint(VALID_HEX),
            'provenance': (),
            'rights': RightsAssessment(status=RightsStatus.KNOWN, evidence_refs=()),
            'index_revision': 2,
        }
        for name, value in replacements.items():
            with self.subTest(field=name):
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(asset, name, value)

    def test_with_fingerprint_sets_once_and_never_overwrites(self) -> None:
        asset = make_asset()
        fingerprint = CanonicalFingerprint(VALID_HEX)
        updated = asset.with_fingerprint(fingerprint)
        self.assertEqual(updated.fingerprint, fingerprint)
        self.assertIsNone(asset.fingerprint)
        for second in (CanonicalFingerprint(OTHER_HEX), fingerprint):
            with self.subTest(second=second.value):
                with self.assertRaises(ValueError):
                    updated.with_fingerprint(second)
        self.assertEqual(updated.fingerprint, fingerprint)

    def test_raw_string_fingerprint_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_asset().with_fingerprint(VALID_HEX)
        with self.assertRaises(ValueError):
            make_asset(fingerprint=VALID_HEX.upper())


class ProvenanceTests(unittest.TestCase):
    def test_with_provenance_returns_new_copy_and_appends(self) -> None:
        original = make_asset(fingerprint=CanonicalFingerprint(VALID_HEX))
        first = original.provenance[0]
        repost = make_entry('article-2')
        updated = original.with_provenance(repost)
        self.assertIsNot(updated, original)
        self.assertEqual(updated.provenance, (first, repost))
        self.assertEqual(original.provenance, (first,))
        self.assertEqual(updated.fingerprint, original.fingerprint)
        self.assertEqual(updated.rights, original.rights)
        self.assertEqual(updated.index_revision, original.index_revision)

    def test_with_provenance_skips_duplicate_entry(self) -> None:
        asset = make_asset().with_provenance(make_entry('article-2'))
        again = asset.with_provenance(make_entry('article-2'))
        self.assertEqual(len(again.provenance), 2)
        self.assertEqual(again.provenance, asset.provenance)
        self.assertEqual(again.with_provenance(make_entry()).provenance, asset.provenance)

    def test_provenance_entry_is_frozen(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            make_entry().article_ref = 'article-3'

    def test_ai_generated_entry_is_a_plain_provenance_entry_of_the_article(self) -> None:
        locator = 'aigen://flux-3-image-klein/337337621b85/' + VALID_HEX
        entry = ProvenanceEntry('imggen-pipe', 'article-1', None, locator, '2026-11-02T00:00:00Z', ProvenanceRelation.AI_GENERATED)
        self.assertEqual(entry.relation.value, 'ai_generated')
        self.assertIs(ProvenanceRelation('ai_generated'), ProvenanceRelation.AI_GENERATED)
        asset = make_asset(fingerprint=CanonicalFingerprint(VALID_HEX), provenance=(entry,))
        self.assertEqual(asset.provenance, (entry,))
        self.assertIs(asset.with_provenance(entry), asset)
        self.assertEqual(asset.with_provenance(make_entry()).provenance, (entry, make_entry()))


class RightsTests(unittest.TestCase):
    def test_uncertain_rights_are_stored_without_blocking(self) -> None:
        for status in (RightsStatus.UNKNOWN, RightsStatus.DISPUTED):
            with self.subTest(status=status.value):
                rights = RightsAssessment(status=status, evidence_refs=('evidence-1',))
                asset = make_asset(rights=rights)
                self.assertEqual(asset.rights.status, status)
                self.assertEqual(asset.rights.evidence_refs, ('evidence-1',))
                updated = asset.with_fingerprint(CanonicalFingerprint(VALID_HEX)).with_provenance(make_entry('article-2'))
                self.assertEqual(updated.rights, rights)

    def test_rights_assessment_is_frozen(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            RightsAssessment(status=RightsStatus.UNKNOWN, evidence_refs=()).status = RightsStatus.KNOWN


class RepositoryPortTests(unittest.TestCase):
    EXPECTED = {
        'get': ['self', 'media_asset_id'],
        'find_by_fingerprint': ['self', 'fingerprint'],
        'find_by_discovery_id': ['self', 'discovery_id'],
        'save': ['self', 'asset', 'discovery_id'],
    }

    def test_protocol_members(self) -> None:
        self.assertTrue(typing.is_protocol(MediaAssetRepository))
        self.assertEqual(typing.get_protocol_members(MediaAssetRepository), frozenset(self.EXPECTED))

    def test_method_signatures(self) -> None:
        for name, expected in self.EXPECTED.items():
            with self.subTest(method=name):
                method = getattr(MediaAssetRepository, name, None)
                self.assertIsNotNone(method, f'MediaAssetRepository.{name} is missing')
                self.assertEqual(list(inspect.signature(method).parameters), expected)
        save = getattr(MediaAssetRepository, 'save', None)
        self.assertIsNotNone(save, 'MediaAssetRepository.save is missing')
        self.assertIsNone(inspect.signature(save).parameters['discovery_id'].default)


def imported_names(path: pathlib.Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'), filename=str(path))):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return names


class PackageLayoutTests(unittest.TestCase):
    def test_package_importable_from_src_root(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('catalog'), 'catalog is not importable from the src/ root')
        module = importlib.import_module('catalog')
        self.assertEqual(pathlib.Path(module.__file__).resolve(), PACKAGE_DIR / '__init__.py')
        for name in SUBPACKAGES:
            with self.subTest(subpackage=name):
                sub = importlib.import_module(f'catalog.{name}')
                self.assertEqual(pathlib.Path(sub.__file__).resolve(), PACKAGE_DIR / name / '__init__.py')

    def test_package_inits_are_docstring_only(self) -> None:
        for init in (PACKAGE_DIR / '__init__.py', *(PACKAGE_DIR / name / '__init__.py' for name in SUBPACKAGES)):
            with self.subTest(path=init.relative_to(ROOT).as_posix()):
                tree = ast.parse(init.read_text(encoding='utf-8'), filename=str(init))
                self.assertEqual(len(tree.body), 1, 'package __init__ must contain only its docstring')
                self.assertTrue(ast.get_docstring(tree), 'package __init__ must have a non-empty docstring')

    def test_no_src_prefixed_imports(self) -> None:
        files = [*sorted(p for p in PACKAGE_DIR.rglob('*.py') if '__pycache__' not in p.parts), pathlib.Path(__file__).resolve()]
        violations = {
            path.relative_to(ROOT).as_posix(): bad
            for path in files
            if (bad := [n for n in imported_names(path) if n == 'src' or n.startswith('src.')])
        }
        self.assertEqual(violations, {})

    def test_no_duplicate_trees_or_test_package_markers(self) -> None:
        self.assertFalse((ROOT / 'src' / 'storage').exists(), 'src/storage must not exist')
        for name in ('storage', 'orchestration', 'ui'):
            with self.subTest(directory=name):
                self.assertEqual([p for p in PACKAGE_DIR.rglob(name) if p.is_dir()], [])
        here = pathlib.Path(__file__).resolve().parent
        for marker in (here / '__init__.py', here / 'conftest.py', ROOT / 'tests' / 'conftest.py', ROOT / 'tests' / 'unit' / 'conftest.py'):
            with self.subTest(marker=marker.relative_to(ROOT).as_posix()):
                self.assertFalse(marker.exists())
