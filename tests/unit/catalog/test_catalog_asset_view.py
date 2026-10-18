"""C-07: MediaAssetView read model (CT-MED-002) and display status (D8-C-09)."""
import ast
import inspect
import json
import pathlib
import unittest

from catalog.application import asset_view
from catalog.application.asset_view import DisplayStatus, build_media_asset_view, resolve_display_status
from catalog.domain.identity import (
    CanonicalFingerprint, MediaAsset, MediaKind, ProvenanceEntry, ProvenanceRelation, RightsAssessment, RightsStatus,
)
from catalog.domain.renditions import Rendition, RenditionKind, RenditionSet
from catalog.domain.states import Availability, ImageSafetyState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_FILE = ROOT / 'src' / 'catalog' / 'application' / 'asset_view.py'
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'c-d-media-candidates' / 'payloads.json'
ASSET_ID = 'asset-1'
FINGERPRINT = 'a' * 64
GROUPS = {'identity', 'provenance', 'semantics', 'technical', 'safety', 'rights', 'availability', 'renditions', 'usage'}
STATUSES = {'original', 'processed', 'uncertain', 'failed', 'unavailable'}
EVIDENCE = ('rights-evidence-1', 'rights-evidence-2')


def entry(n):
    return ProvenanceEntry(
        f'source-{n}', f'article-{n}' if n % 2 else None, None,
        f'https://example.test/{n}.jpg', f'2026-10-0{n}T00:00:00Z', ProvenanceRelation.HERO_IMAGE,
    )


def make_asset(kind=MediaKind.IMAGE, rights=RightsStatus.KNOWN, fingerprint=FINGERPRINT, count=2):
    fp = None if fingerprint is None else CanonicalFingerprint(fingerprint)
    provenance = tuple(entry(n) for n in range(1, count + 1))
    return MediaAsset(ASSET_ID, kind, fp, provenance, RightsAssessment(rights, EVIDENCE), 3)


def make_set(*kinds, asset_id=ASSET_ID):
    return RenditionSet(asset_id, tuple(
        Rendition(f'rendition-{k}', asset_id, k, f'artifact-{k}', 'artifact-original', 'spec-1', 'proc-1',
                  ('artifact-original',))
        for k in kinds
    ))


def build(**overrides):
    args = dict(
        asset=make_asset(), renditions=make_set(RenditionKind.ORIGINAL), image_safety=ImageSafetyState.SAFE,
        availability=Availability.AVAILABLE,
        semantics={'entities': ['entity-1'], 'topics': ['topic-1'], 'language': 'vi', 'tags': ['tag-1']},
        technical={'width': 1920, 'height': 1080, 'has_audio': False},
        usage_summary={'count': 2, 'recent_jobs': ['job-1'], 'roles': ['hero']},
    )
    args.update(overrides)
    return build_media_asset_view(**args)


class ViewTestCase(unittest.TestCase):
    def group(self, view, name):
        self.assertIsInstance(view, dict)
        self.assertIn(name, view, f'missing group {name}')
        return view[name]


class DisplayStatusEnumTests(unittest.TestCase):
    def test_values(self):
        self.assertEqual({s.value for s in DisplayStatus}, STATUSES)
        self.assertEqual(len(DisplayStatus), 5)


class ViewGroupTests(ViewTestCase):
    def test_view_has_every_ct_med_002_group(self):
        view = build()
        for name in sorted(GROUPS | {'display_status'}):
            with self.subTest(group=name):
                self.group(view, name)
        self.assertEqual(set(view), GROUPS | {'display_status'})

    def test_identity_group(self):
        self.assertEqual(
            self.group(build(), 'identity'),
            {
                'media_asset_id': ASSET_ID,
                'kind': 'image',
                'canonical_fingerprint': FINGERPRINT,
                'index_revision': 3,
            },
        )

    def test_identity_without_fingerprint(self):
        view = build(asset=make_asset(fingerprint=None))
        self.assertIsNone(self.group(view, 'identity')['canonical_fingerprint'])

    def test_provenance_keeps_every_entry_in_order(self):
        asset = make_asset(count=5)
        view = build(asset=asset)
        self.assertEqual(
            self.group(view, 'provenance'),
            [
                {
                    'source_ref': e.source_ref,
                    'article_ref': e.article_ref,
                    'event_ref': e.event_ref,
                    'original_locator': e.original_locator,
                    'observed_at': e.observed_at,
                    'relation': e.relation.value,
                }
                for e in asset.provenance
            ],
        )
        self.assertEqual(len(self.group(view, 'provenance')), 5)

    def test_pass_through_groups_are_copies(self):
        semantics = {'tags': ['t']}
        technical = {'width': 1}
        usage = {'count': 1}
        view = build(semantics=semantics, technical=technical, usage_summary=usage)
        for group_name, input_val in (('semantics', semantics), ('technical', technical), ('usage', usage)):
            self.assertEqual(self.group(view, group_name), input_val)
            self.assertIsNot(self.group(view, group_name), input_val)
        self.group(view, 'semantics')['extra'] = 1
        self.assertNotIn('extra', semantics)

    def test_renditions_group_lists_every_rendition(self):
        rs = make_set(RenditionKind.ORIGINAL, RenditionKind.NORMALIZED, RenditionKind.THUMBNAIL)
        self.assertEqual(
            self.group(build(renditions=rs), 'renditions'),
            [
                {
                    'rendition_ref': r.rendition_ref,
                    'kind': r.kind.value,
                    'artifact_version_ref': r.artifact_version_ref,
                    'source_artifact_version_ref': r.source_artifact_version_ref,
                    'transformation_spec_revision': r.transformation_spec_revision,
                    'processor_version': r.processor_version,
                    'lineage': list(r.lineage),
                }
                for r in rs.renditions
            ],
        )

    def test_safety_group(self):
        view_uncertain = build(image_safety=ImageSafetyState.UNCERTAIN)
        self.assertEqual(
            self.group(view_uncertain, 'safety'),
            {'image_safety_state': 'UNCERTAIN', 'usability': 'usable_with_warning'},
        )
        view_clip = build(asset=make_asset(kind=MediaKind.CLIP), image_safety=None)
        self.assertEqual(
            self.group(view_clip, 'safety'),
            {'image_safety_state': None, 'usability': 'usable'},
        )

    def test_availability_group(self):
        view_missing = build(availability=Availability.MISSING)
        self.assertEqual(
            self.group(view_missing, 'availability'),
            {'state': 'MISSING', 'usability': 'not_usable'},
        )
        view_unavail_src = build(availability=Availability.UNAVAILABLE_SOURCE)
        self.assertEqual(
            self.group(view_unavail_src, 'availability'),
            {'state': 'UNAVAILABLE_SOURCE', 'usability': 'usable'},
        )

    def test_view_is_json_serializable(self):
        view = build()
        self.group(view, 'display_status')
        self.assertEqual(json.loads(json.dumps(view)), view)


def expected_status(safety, availability, kinds):
    if availability in ('MISSING', 'CORRUPT', 'RECOVERING'):
        return 'unavailable'
    if safety in ('UNREADABLE', 'TRANSFORM_FAILED'):
        return 'failed'
    if safety in ('UNCERTAIN', 'DETECTION_FAILED'):
        return 'uncertain'
    if safety == 'PROCESSED_READY' or {'normalized', 'blurred', 'recolored'} & set(kinds):
        return 'processed'
    return 'original'


class RightsVisibilityTests(ViewTestCase):
    def test_uncertain_rights_are_shown_with_evidence(self):
        for status in (RightsStatus.UNKNOWN, RightsStatus.DISPUTED):
            with self.subTest(status=status):
                view = build(asset=make_asset(rights=status))
                self.assertEqual(
                    self.group(view, 'rights'),
                    {'status': status.value, 'evidence_refs': list(EVIDENCE), 'uncertain': True},
                )
                self.assertEqual(self.group(view, 'display_status'), 'original')

    def test_known_rights_keep_evidence(self):
        self.assertEqual(
            self.group(build(), 'rights'),
            {'status': 'known', 'evidence_refs': list(EVIDENCE), 'uncertain': False},
        )


class DisplayStatusPriorityTests(ViewTestCase):
    def test_matches_priority_oracle(self):
        O = RenditionKind.ORIGINAL
        for availability in Availability:
            for safety in ImageSafetyState:
                for kinds in ((O,), (O, RenditionKind.BLURRED), (O, RenditionKind.THUMBNAIL)):
                    with self.subTest(availability=availability, safety=safety, kinds=kinds):
                        expected = expected_status(safety.value, availability.value, [k.value for k in kinds])
                        self.assertEqual(
                            resolve_display_status(MediaKind.IMAGE, safety, availability, make_set(*kinds)),
                            DisplayStatus(expected),
                        )
                        self.assertEqual(
                            self.group(
                                build(image_safety=safety, availability=availability, renditions=make_set(*kinds)),
                                'display_status',
                            ),
                            expected,
                        )

    def test_missing_is_always_unavailable(self):
        O = RenditionKind.ORIGINAL
        pairs = [(MediaKind.IMAGE, s) for s in ImageSafetyState] + [
            (MediaKind.CLIP, None),
            (MediaKind.AUDIO, None),
        ]
        renditions = make_set(O, RenditionKind.NORMALIZED)
        for kind, safety in pairs:
            with self.subTest(kind=kind, safety=safety):
                self.assertEqual(
                    resolve_display_status(kind, safety, Availability.MISSING, renditions),
                    DisplayStatus.UNAVAILABLE,
                )
                view = build(
                    asset=make_asset(kind=kind),
                    image_safety=safety,
                    availability=Availability.MISSING,
                    renditions=renditions,
                )
                self.assertEqual(self.group(view, 'display_status'), 'unavailable')

    def test_transform_failed_is_never_processed(self):
        O = RenditionKind.ORIGINAL
        renditions = make_set(
            O,
            RenditionKind.NORMALIZED,
            RenditionKind.BLURRED,
            RenditionKind.RECOLORED,
        )
        for avail in (Availability.AVAILABLE, Availability.UNAVAILABLE_SOURCE):
            with self.subTest(availability=avail):
                status = resolve_display_status(MediaKind.IMAGE, ImageSafetyState.TRANSFORM_FAILED, avail, renditions)
                self.assertEqual(status, DisplayStatus.FAILED)
                self.assertNotEqual(status, DisplayStatus.PROCESSED)
                view = build(
                    image_safety=ImageSafetyState.TRANSFORM_FAILED,
                    availability=avail,
                    renditions=renditions,
                )
                self.assertEqual(self.group(view, 'display_status'), 'failed')
                self.assertNotEqual(self.group(view, 'display_status'), 'processed')

    def test_uncertain_is_not_merged_into_original(self):
        O = RenditionKind.ORIGINAL
        renditions = make_set(O)
        for safety in (ImageSafetyState.UNCERTAIN, ImageSafetyState.DETECTION_FAILED):
            with self.subTest(safety=safety):
                status = resolve_display_status(MediaKind.IMAGE, safety, Availability.AVAILABLE, renditions)
                self.assertEqual(status, DisplayStatus.UNCERTAIN)
                self.assertNotEqual(status, DisplayStatus.ORIGINAL)
                view = build(
                    image_safety=safety,
                    availability=Availability.AVAILABLE,
                    renditions=renditions,
                )
                self.assertEqual(self.group(view, 'display_status'), 'uncertain')
                self.assertNotEqual(self.group(view, 'display_status'), 'original')

    def test_processing_renditions_mark_processed(self):
        O = RenditionKind.ORIGINAL
        for k in (RenditionKind.NORMALIZED, RenditionKind.BLURRED, RenditionKind.RECOLORED):
            with self.subTest(kind=k):
                rs = make_set(O, k)
                self.assertEqual(
                    resolve_display_status(MediaKind.IMAGE, ImageSafetyState.SAFE, Availability.AVAILABLE, rs),
                    DisplayStatus.PROCESSED,
                )
                view = build(image_safety=ImageSafetyState.SAFE, renditions=rs)
                self.assertEqual(self.group(view, 'display_status'), 'processed')
        clip_rs = make_set(O, RenditionKind.NORMALIZED)
        self.assertEqual(
            resolve_display_status(MediaKind.CLIP, None, Availability.AVAILABLE, clip_rs),
            DisplayStatus.PROCESSED,
        )
        clip_view = build(asset=make_asset(kind=MediaKind.CLIP), image_safety=None, renditions=clip_rs)
        self.assertEqual(self.group(clip_view, 'display_status'), 'processed')
        ready_rs = make_set(O)
        self.assertEqual(
            resolve_display_status(MediaKind.IMAGE, ImageSafetyState.PROCESSED_READY, Availability.AVAILABLE, ready_rs),
            DisplayStatus.PROCESSED,
        )
        ready_view = build(image_safety=ImageSafetyState.PROCESSED_READY, renditions=ready_rs)
        self.assertEqual(self.group(ready_view, 'display_status'), 'processed')

    def test_unprocessed_renditions_stay_original(self):
        O = RenditionKind.ORIGINAL
        rs = make_set(O, RenditionKind.THUMBNAIL, RenditionKind.EXTRACTED_FRAME)
        self.assertEqual(
            resolve_display_status(MediaKind.IMAGE, ImageSafetyState.SAFE, Availability.AVAILABLE, rs),
            DisplayStatus.ORIGINAL,
        )
        view = build(image_safety=ImageSafetyState.SAFE, renditions=rs)
        self.assertEqual(self.group(view, 'display_status'), 'original')
        orig_rs = make_set(O)
        for kind in (MediaKind.CLIP, MediaKind.AUDIO):
            with self.subTest(kind=kind):
                self.assertEqual(
                    resolve_display_status(kind, None, Availability.AVAILABLE, orig_rs),
                    DisplayStatus.ORIGINAL,
                )
                k_view = build(asset=make_asset(kind=kind), image_safety=None, renditions=orig_rs)
                self.assertEqual(self.group(k_view, 'display_status'), 'original')

    def test_unavailable_source_keeps_status(self):
        O = RenditionKind.ORIGINAL
        rs = make_set(O)
        self.assertEqual(
            resolve_display_status(MediaKind.IMAGE, ImageSafetyState.SAFE, Availability.UNAVAILABLE_SOURCE, rs),
            DisplayStatus.ORIGINAL,
        )
        view_safe = build(image_safety=ImageSafetyState.SAFE, availability=Availability.UNAVAILABLE_SOURCE, renditions=rs)
        self.assertEqual(self.group(view_safe, 'display_status'), 'original')
        self.assertEqual(
            resolve_display_status(MediaKind.IMAGE, ImageSafetyState.UNCERTAIN, Availability.UNAVAILABLE_SOURCE, rs),
            DisplayStatus.UNCERTAIN,
        )
        view_unc = build(image_safety=ImageSafetyState.UNCERTAIN, availability=Availability.UNAVAILABLE_SOURCE, renditions=rs)
        self.assertEqual(self.group(view_unc, 'display_status'), 'uncertain')

    def test_five_statuses_are_distinguishable(self):
        O = RenditionKind.ORIGINAL
        pairs = [
            (Availability.MISSING, ImageSafetyState.SAFE),
            (Availability.AVAILABLE, ImageSafetyState.UNREADABLE),
            (Availability.AVAILABLE, ImageSafetyState.UNCERTAIN),
            (Availability.AVAILABLE, ImageSafetyState.PROCESSED_READY),
            (Availability.AVAILABLE, ImageSafetyState.SAFE),
        ]
        rs = make_set(O)
        statuses = [
            self.group(build(availability=avail, image_safety=safety, renditions=rs), 'display_status')
            for avail, safety in pairs
        ]
        self.assertEqual(statuses, ['unavailable', 'failed', 'uncertain', 'processed', 'original'])
        self.assertEqual(set(statuses), STATUSES)


class InputValidationTests(unittest.TestCase):
    def test_rejects_non_asset(self):
        with self.assertRaises(ValueError):
            build(asset={'media_asset_id': ASSET_ID})

    def test_rejects_non_rendition_set(self):
        with self.assertRaises(ValueError):
            build(renditions=make_set(RenditionKind.ORIGINAL).renditions)

    def test_rejects_renditions_of_other_asset(self):
        with self.assertRaises(ValueError):
            build(renditions=make_set(RenditionKind.ORIGINAL, asset_id='asset-2'))

    def test_rejects_non_mapping_groups(self):
        for name in ('semantics', 'technical', 'usage_summary'):
            for bad in (None, ['x']):
                with self.subTest(name=name, bad=bad):
                    with self.assertRaises(ValueError):
                        build(**{name: bad})

    def test_rejects_invalid_safety_pairing(self):
        with self.assertRaises(ValueError):
            build(image_safety=None)
        with self.assertRaises(ValueError):
            build(asset=make_asset(kind=MediaKind.CLIP), image_safety=ImageSafetyState.SAFE)

    def test_rejects_unknown_availability(self):
        with self.assertRaises(ValueError):
            build(availability='GONE')


class FixtureBindingTests(ViewTestCase):
    def test_candidate_fixture_maps_into_view(self):
        payload = json.loads(FIXTURE.read_text(encoding='utf-8'))['entities']['MediaCandidate']['valid'][0]
        asset_id = payload['media_asset_id']
        asset = MediaAsset(asset_id, MediaKind.IMAGE, None, (entry(1),), RightsAssessment(RightsStatus.UNKNOWN, ()), 1)
        rendition = Rendition(
            payload['rendition_ref'],
            asset_id,
            RenditionKind.ORIGINAL,
            payload['artifact_version_ref'],
            payload['artifact_version_ref'],
            'none',
            'none',
            (),
        )
        view = build(
            asset=asset,
            renditions=RenditionSet(asset_id, (rendition,)),
            availability=Availability(payload['availability']),
            technical=payload['technical_fitness'],
            usage_summary=payload['recent_usage_summary'],
        )
        self.assertEqual(self.group(view, 'identity')['media_asset_id'], asset_id)
        renditions = self.group(view, 'renditions')
        self.assertEqual(renditions[0]['rendition_ref'], payload['rendition_ref'])
        self.assertEqual(renditions[0]['artifact_version_ref'], payload['artifact_version_ref'])
        self.assertEqual(self.group(view, 'availability')['state'], payload['availability'])
        self.assertEqual(self.group(view, 'technical'), payload['technical_fitness'])
        self.assertEqual(self.group(view, 'usage'), payload['recent_usage_summary'])
        self.assertEqual(self.group(view, 'rights'), {'status': 'unknown', 'evidence_refs': [], 'uncertain': True})
        self.assertEqual(self.group(view, 'display_status'), 'original')


class ModuleSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(MODULE_FILE.read_text(encoding='utf-8'))

    def test_imports_are_pure(self):
        modules = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        self.assertTrue({m.split('.')[0] for m in modules} <= {'collections', 'enum', 'catalog'})

    def test_no_io_calls(self):
        call_names = [
            node.func.id
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        self.assertEqual(
            set(call_names) & {'open', 'print', 'input', 'exec', 'eval', 'compile', '__import__'},
            set(),
        )

        attr_names = [
            node.attr
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Attribute)
        ]
        self.assertEqual(
            set(attr_names) & {'read_text', 'write_text', 'read_bytes', 'write_bytes', 'open', 'system', 'run', 'Popen', 'unlink', 'mkdir'},
            set(),
        )

    def test_public_functions(self):
        self.assertEqual(
            sorted(
                name for name, obj in vars(asset_view).items()
                if inspect.isfunction(obj) and obj.__module__ == asset_view.__name__ and not name.startswith('_')
            ),
            ['build_media_asset_view', 'resolve_display_status'],
        )

    def test_is_deterministic(self):
        self.assertEqual(build(), build())
