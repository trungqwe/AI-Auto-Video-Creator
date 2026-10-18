"""C-04: immutable renditions, transformation-fingerprint dedupe (CT-MED-003) and clip safety-transform guard."""
import ast
import dataclasses
import hashlib
import json
import pathlib
import unittest

from catalog.domain.identity import MediaKind
from catalog.domain.renditions import (
    Rendition,
    RenditionKind,
    RenditionRejected,
    RenditionSet,
    transformation_fingerprint,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_FILE = ROOT / 'src' / 'catalog' / 'domain' / 'renditions.py'
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'i-artifact-version' / 'payloads.json'
ASSET_ID = 'asset-1'
ORIGINAL_ARTIFACT = 'artifact-version-original'


def load_result_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    return data['entities']['DeclareArtifactVersionResult']


def make_rendition(**overrides: object) -> Rendition:
    fields: dict[str, object] = {
        'rendition_ref': 'rendition-blurred-1',
        'media_asset_id': ASSET_ID,
        'kind': RenditionKind.BLURRED,
        'artifact_version_ref': 'artifact-version-blurred-1',
        'source_artifact_version_ref': ORIGINAL_ARTIFACT,
        'transformation_spec_revision': 'blur-spec-r1',
        'processor_version': 'processor-1.0.0',
        'lineage': (ORIGINAL_ARTIFACT,),
    }
    fields.update(overrides)
    return Rendition(**fields)


def make_original(**overrides: object) -> Rendition:
    fields: dict[str, object] = {
        'rendition_ref': 'rendition-original',
        'kind': RenditionKind.ORIGINAL,
        'artifact_version_ref': ORIGINAL_ARTIFACT,
        'source_artifact_version_ref': ORIGINAL_ARTIFACT,
        'transformation_spec_revision': 'none',
        'processor_version': 'none',
        'lineage': (),
    }
    fields.update(overrides)
    return make_rendition(**fields)


def expected_fingerprint(source: str, kind: str, spec: str, processor: str) -> str:
    payload = {
        'source_artifact_version_ref': source,
        'kind': kind,
        'transformation_spec_revision': spec,
        'processor_version': processor,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()


class EnumValueTests(unittest.TestCase):
    def test_rendition_kind_values(self) -> None:
        self.assertEqual(
            {k.value for k in RenditionKind},
            {'original', 'normalized', 'blurred', 'recolored', 'thumbnail', 'extracted_frame'},
        )


class RenditionValueTests(unittest.TestCase):
    def test_rendition_is_frozen(self) -> None:
        rendition = make_rendition()
        for field in dataclasses.fields(Rendition):
            with self.subTest(field=field.name):
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(rendition, field.name, 'replaced')

    def test_kind_is_coerced_and_unknown_kind_rejected(self) -> None:
        self.assertIs(make_rendition(kind='blurred').kind, RenditionKind.BLURRED)
        with self.assertRaises(ValueError):
            make_rendition(kind='sharpened')

    def test_rendition_requires_output_artifact_and_refs(self) -> None:
        for name in ('rendition_ref', 'media_asset_id', 'artifact_version_ref', 'source_artifact_version_ref'):
            for bad in ('', None):
                with self.subTest(field=name, value=bad):
                    with self.assertRaises(ValueError):
                        make_rendition(**{name: bad})

    def test_lineage_must_be_tuple_of_str(self) -> None:
        for bad in ([ORIGINAL_ARTIFACT], (1,), None):
            with self.subTest(lineage=bad):
                with self.assertRaises(ValueError):
                    make_rendition(lineage=bad)


class TransformationFingerprintTests(unittest.TestCase):
    def test_matches_sha256_of_sorted_json(self) -> None:
        expected = expected_fingerprint(ORIGINAL_ARTIFACT, 'blurred', 'blur-spec-r1', 'processor-1.0.0')
        self.assertEqual(transformation_fingerprint(make_rendition()), expected)

    def test_output_refs_and_lineage_do_not_change_fingerprint(self) -> None:
        base = transformation_fingerprint(make_rendition())
        other = make_rendition(rendition_ref='rendition-blurred-2', artifact_version_ref='artifact-version-blurred-2', lineage=())
        self.assertEqual(transformation_fingerprint(other), base)

    def test_each_transformation_input_changes_fingerprint(self) -> None:
        base = transformation_fingerprint(make_rendition())
        changes = {
            'source_artifact_version_ref': 'artifact-version-other',
            'kind': RenditionKind.RECOLORED,
            'transformation_spec_revision': 'blur-spec-r2',
            'processor_version': 'processor-1.0.1',
        }
        for name, value in changes.items():
            with self.subTest(field=name):
                self.assertNotEqual(transformation_fingerprint(make_rendition(**{name: value})), base)


class DedupeTests(unittest.TestCase):
    def test_same_transformation_returns_existing_rendition(self) -> None:
        first = make_rendition()
        registered, kept = RenditionSet(ASSET_ID).register(first, MediaKind.IMAGE)
        self.assertIs(kept, first)
        retry = make_rendition(rendition_ref='rendition-blurred-2', artifact_version_ref='artifact-version-blurred-2')
        again, returned = registered.register(retry, MediaKind.IMAGE)
        self.assertEqual(returned.rendition_ref, 'rendition-blurred-1')
        self.assertEqual(returned.artifact_version_ref, 'artifact-version-blurred-1')
        self.assertEqual(again.renditions, (first,))
        self.assertEqual(registered.renditions, (first,))

    def test_register_returns_new_set_and_keeps_old_set(self) -> None:
        empty = RenditionSet(ASSET_ID)
        original = make_original()
        with_original, _ = empty.register(original, MediaKind.IMAGE)
        blurred = make_rendition()
        updated, returned = with_original.register(blurred, MediaKind.IMAGE)
        self.assertIs(returned, blurred)
        self.assertEqual(empty.renditions, ())
        self.assertEqual(with_original.renditions, (original,))
        self.assertEqual(updated.renditions, (original, blurred))
        self.assertEqual(updated.renditions[0].artifact_version_ref, ORIGINAL_ARTIFACT)

    def test_rendition_ref_reused_for_other_transformation_is_rejected(self) -> None:
        registered, first = RenditionSet(ASSET_ID).register(make_rendition(), MediaKind.IMAGE)
        clash = make_rendition(transformation_spec_revision='blur-spec-r2', artifact_version_ref='artifact-version-blurred-2')
        with self.assertRaises(RenditionRejected) as caught:
            registered.register(clash, MediaKind.IMAGE)
        self.assertEqual(caught.exception.code, 'RENDITION_REF_CONFLICT')
        self.assertEqual(registered.renditions, (first,))

    def test_rendition_of_other_asset_is_rejected(self) -> None:
        with self.assertRaises(RenditionRejected) as caught:
            RenditionSet(ASSET_ID).register(make_rendition(media_asset_id='asset-2'), MediaKind.IMAGE)
        self.assertEqual(caught.exception.code, 'MEDIA_ASSET_MISMATCH')


class ClipSafetyTransformTests(unittest.TestCase):
    def test_clip_rejects_blurred_and_recolored(self) -> None:
        for kind in (RenditionKind.BLURRED, RenditionKind.RECOLORED):
            with self.subTest(kind=kind.value):
                empty = RenditionSet(ASSET_ID)
                with self.assertRaises(RenditionRejected) as caught:
                    empty.register(make_rendition(kind=kind), MediaKind.CLIP)
                self.assertEqual(caught.exception.code, 'CLIP_SAFETY_TRANSFORM_FORBIDDEN')
                self.assertIsInstance(caught.exception, ValueError)
                self.assertEqual(empty.renditions, ())

    def test_clip_accepts_non_safety_renditions(self) -> None:
        for kind in (RenditionKind.NORMALIZED, RenditionKind.THUMBNAIL, RenditionKind.EXTRACTED_FRAME):
            with self.subTest(kind=kind.value):
                rendition = make_rendition(kind=kind)
                registered, returned = RenditionSet(ASSET_ID).register(rendition, MediaKind.CLIP)
                self.assertIs(returned, rendition)
                self.assertEqual(registered.renditions, (rendition,))

    def test_image_accepts_safety_transforms(self) -> None:
        for kind in (RenditionKind.BLURRED, RenditionKind.RECOLORED):
            with self.subTest(kind=kind.value):
                rendition = make_rendition(kind=kind)
                registered, returned = RenditionSet(ASSET_ID).register(rendition, MediaKind.IMAGE)
                self.assertIs(returned, rendition)
                self.assertEqual(registered.renditions, (rendition,))


class OriginalSeparationTests(unittest.TestCase):
    def test_rendition_rejected_is_value_error(self) -> None:
        self.assertTrue(issubclass(RenditionRejected, ValueError))

    def test_second_original_with_other_artifact_is_rejected(self) -> None:
        registered, original = RenditionSet(ASSET_ID).register(make_original(), MediaKind.CLIP)
        variants = {
            'other_source': make_original(rendition_ref='rendition-original-2', artifact_version_ref='artifact-version-other', source_artifact_version_ref='artifact-version-other'),
            'same_fingerprint': make_original(rendition_ref='rendition-original-2', artifact_version_ref='artifact-version-other'),
        }
        for name, other in variants.items():
            with self.subTest(variant=name):
                with self.assertRaises(RenditionRejected) as caught:
                    registered.register(other, MediaKind.CLIP)
                self.assertEqual(caught.exception.code, 'ORIGINAL_ALREADY_REGISTERED')
                self.assertEqual(registered.renditions, (original,))

    def test_same_original_is_idempotent(self) -> None:
        registered, original = RenditionSet(ASSET_ID).register(make_original(), MediaKind.IMAGE)
        again, returned = registered.register(make_original(), MediaKind.IMAGE)
        self.assertIs(returned, original)
        self.assertEqual(again.renditions, (original,))


class FixtureBindingTests(unittest.TestCase):
    def test_artifact_version_id_from_fixture_is_kept_as_output_ref(self) -> None:
        valid = load_result_fixture()['valid']
        self.assertTrue(valid, 'fixture has no valid DeclareArtifactVersionResult payload')
        for payload in valid:
            artifact = payload['artifact_version_id']
            with self.subTest(artifact_version_id=artifact):
                original = make_original(artifact_version_ref=artifact, source_artifact_version_ref=artifact)
                registered, _ = RenditionSet(ASSET_ID).register(original, MediaKind.IMAGE)
                blurred = make_rendition(source_artifact_version_ref=artifact, lineage=(artifact,))
                updated, _ = registered.register(blurred, MediaKind.IMAGE)
                self.assertEqual([r.artifact_version_ref for r in updated.renditions], [artifact, 'artifact-version-blurred-1'])
                self.assertEqual(updated.renditions[1].source_artifact_version_ref, artifact)


class ModuleSurfaceTests(unittest.TestCase):
    def test_module_imports_only_stdlib_and_catalog(self) -> None:
        tree = ast.parse(MODULE_FILE.read_text(encoding='utf-8'), filename=str(MODULE_FILE))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        self.assertLessEqual(modules, {'dataclasses', 'enum', 'hashlib', 'json', 'catalog.domain.identity'})
