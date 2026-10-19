"""C-08: resolve_renderable_version renders only VERIFIED artifacts with matching hash (phần C của TST-INT-INV-008, TST-E2E-011)."""
import ast
import dataclasses
import json
import pathlib
import unittest

from catalog.application.renderable import ArtifactVersionView, RenderableResolution, resolve_renderable_version
from catalog.domain.identity import MediaKind
from catalog.domain.renditions import Rendition, RenditionKind
from catalog.domain.states import Availability, ImageSafetyState, Usability
from controlplane.domain.statemachine import ArtifactLocationState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_FILE = ROOT / 'src' / 'catalog' / 'application' / 'renderable.py'
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'i-artifact-version' / 'payloads.json'
ENTITIES = json.loads(FIXTURE.read_text(encoding='utf-8'))['entities']
REQUEST = ENTITIES['DeclareArtifactVersionRequest']['valid'][0]
UPPERCASE_SHA256 = next(
    case['payload']['content_sha256']
    for case in ENTITIES['DeclareArtifactVersionRequest']['invalid']
    if case['case'] == 'content_hash_uppercase'
)
ARTIFACT_REF = ENTITIES['DeclareArtifactVersionResult']['valid'][0]['artifact_version_id']
EXPECTED_SHA256 = REQUEST['content_sha256']
OTHER_SHA256 = 'f' * 64
SEVERITY = {Usability.USABLE: 0, Usability.USABLE_WITH_WARNING: 1, Usability.NOT_USABLE: 2}
SAFETY_USABILITY = {
    'NOT_ASSESSED': Usability.NOT_USABLE,
    'ASSESSING': Usability.NOT_USABLE,
    'SAFE': Usability.USABLE,
    'TRANSFORM_REQUIRED': Usability.NOT_USABLE,
    'UNCERTAIN': Usability.USABLE_WITH_WARNING,
    'DETECTION_FAILED': Usability.USABLE_WITH_WARNING,
    'UNREADABLE': Usability.NOT_USABLE,
    'TRANSFORMING': Usability.NOT_USABLE,
    'PROCESSED_READY': Usability.USABLE,
    'TRANSFORM_FAILED': Usability.USABLE_WITH_WARNING,
}
AVAILABILITY_USABILITY = {
    'AVAILABLE': Usability.USABLE,
    'UNAVAILABLE_SOURCE': Usability.USABLE,
    'MISSING': Usability.NOT_USABLE,
    'CORRUPT': Usability.NOT_USABLE,
    'RECOVERING': Usability.NOT_USABLE,
}


def make_rendition(**overrides: object) -> Rendition:
    fields: dict[str, object] = {
        'rendition_ref': 'rendition-original',
        'media_asset_id': 'asset-1',
        'kind': RenditionKind.ORIGINAL,
        'artifact_version_ref': ARTIFACT_REF,
        'source_artifact_version_ref': ARTIFACT_REF,
        'transformation_spec_revision': 'none',
        'processor_version': 'none',
        'lineage': (),
    }
    fields.update(overrides)
    return Rendition(**fields)


def make_artifact(**overrides: object) -> ArtifactVersionView:
    fields: dict[str, object] = {
        'artifact_version_ref': ARTIFACT_REF,
        'content_sha256': EXPECTED_SHA256,
        'size_bytes': REQUEST['size_bytes'],
        'media_type': REQUEST['media_type'],
        'location_state': ArtifactLocationState.VERIFIED,
        'is_local': True,
    }
    fields.update(overrides)
    return ArtifactVersionView(**fields)


def resolve(artifact: ArtifactVersionView | None = None, **overrides: object) -> RenderableResolution:
    arguments: dict[str, object] = {
        'rendition': make_rendition(),
        'artifact': artifact or make_artifact(),
        'expected_sha256': EXPECTED_SHA256,
        'media_kind': MediaKind.IMAGE,
        'image_safety': ImageSafetyState.SAFE,
        'availability': Availability.AVAILABLE,
    }
    arguments.update(overrides)
    return resolve_renderable_version(**arguments)


class LocationStateTests(unittest.TestCase):
    def test_every_location_state_only_verified_is_usable(self) -> None:
        codes = {ArtifactLocationState.MISSING: 'ARTIFACT_MISSING', ArtifactLocationState.CORRUPT: 'ARTIFACT_CORRUPT'}
        for state in ArtifactLocationState:
            with self.subTest(location_state=state.value):
                resolution = resolve(make_artifact(location_state=state))
                self.assertIs(resolution.location_state, state)
                if state is ArtifactLocationState.VERIFIED:
                    self.assertIs(resolution.usability, Usability.USABLE)
                    self.assertEqual(resolution.reason_codes, ())
                else:
                    self.assertIs(resolution.usability, Usability.NOT_USABLE)
                    self.assertEqual(resolution.reason_codes, (codes.get(state, 'ARTIFACT_NOT_VERIFIED'),))

    def test_unverified_missing_or_corrupt_never_render(self) -> None:
        cases = {
            ArtifactLocationState.AVAILABLE_UNVERIFIED: 'ARTIFACT_NOT_VERIFIED',
            ArtifactLocationState.MISSING: 'ARTIFACT_MISSING',
            ArtifactLocationState.CORRUPT: 'ARTIFACT_CORRUPT',
        }
        for state, code in cases.items():
            for is_local in (True, False):
                with self.subTest(location_state=state.value, is_local=is_local):
                    artifact = make_artifact(location_state=state, is_local=is_local)
                    resolution = resolve(artifact, availability=Availability.UNAVAILABLE_SOURCE)
                    self.assertIs(resolution.usability, Usability.NOT_USABLE)
                    self.assertEqual(resolution.reason_codes, (code,))

    def test_artifact_view_rejects_untyped_state_and_flag(self) -> None:
        for overrides in ({'location_state': 'VERIFIED'}, {'is_local': 1}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    make_artifact(**overrides)


class HashTests(unittest.TestCase):
    def test_fixture_hash_matches_and_is_usable(self) -> None:
        valid = ENTITIES['DeclareArtifactVersionRequest']['valid']
        self.assertTrue(valid, 'fixture has no valid DeclareArtifactVersionRequest payload')
        for payload in valid:
            with self.subTest(content_sha256=payload['content_sha256']):
                artifact = make_artifact(content_sha256=payload['content_sha256'])
                resolution = resolve(artifact, expected_sha256=payload['content_sha256'])
                self.assertEqual(resolution.content_sha256, payload['content_sha256'])
                self.assertIs(resolution.usability, Usability.USABLE)
                self.assertEqual(resolution.reason_codes, ())

    def test_hash_mismatch_is_not_usable(self) -> None:
        resolution = resolve(expected_sha256=OTHER_SHA256)
        self.assertIs(resolution.usability, Usability.NOT_USABLE)
        self.assertEqual(resolution.reason_codes, ('HASH_MISMATCH',))
        self.assertEqual(resolution.content_sha256, EXPECTED_SHA256)

    def test_uppercase_hash_from_fixture_is_mismatch(self) -> None:
        resolution = resolve(make_artifact(content_sha256=UPPERCASE_SHA256))
        self.assertIs(resolution.usability, Usability.NOT_USABLE)
        self.assertEqual(resolution.reason_codes, ('HASH_MISMATCH',))

    def test_location_and_hash_reasons_are_both_reported(self) -> None:
        artifact = make_artifact(location_state=ArtifactLocationState.MISSING)
        resolution = resolve(artifact, expected_sha256=OTHER_SHA256)
        self.assertIs(resolution.usability, Usability.NOT_USABLE)
        self.assertEqual(resolution.reason_codes, ('ARTIFACT_MISSING', 'HASH_MISMATCH'))


class MaterializationTests(unittest.TestCase):
    def test_materialization_required_is_not_is_local(self) -> None:
        for is_local in (True, False):
            with self.subTest(is_local=is_local):
                resolution = resolve(make_artifact(is_local=is_local))
                self.assertIs(resolution.materialization_required, not is_local)
                self.assertIs(resolution.usability, Usability.USABLE)

    def test_resolution_carries_artifact_fields(self) -> None:
        resolution = resolve(make_artifact(is_local=False))
        self.assertEqual(
            (resolution.artifact_version_ref, resolution.size_bytes, resolution.media_type),
            (ARTIFACT_REF, REQUEST['size_bytes'], REQUEST['media_type']),
        )
        self.assertIs(resolution.safety_state, ImageSafetyState.SAFE)


class CombinationTests(unittest.TestCase):
    def test_unavailable_source_with_verified_is_usable(self) -> None:
        resolution = resolve(availability=Availability.UNAVAILABLE_SOURCE)
        self.assertIs(resolution.usability, Usability.USABLE)
        self.assertEqual(resolution.reason_codes, ())

    def test_uncertain_image_is_usable_with_warning(self) -> None:
        resolution = resolve(image_safety=ImageSafetyState.UNCERTAIN)
        self.assertIs(resolution.usability, Usability.USABLE_WITH_WARNING)
        self.assertEqual(resolution.reason_codes, ('IMAGE_SAFETY_UNCERTAIN',))
        self.assertIs(resolution.safety_state, ImageSafetyState.UNCERTAIN)

    def test_unreadable_image_is_not_usable(self) -> None:
        resolution = resolve(image_safety=ImageSafetyState.UNREADABLE)
        self.assertIs(resolution.usability, Usability.NOT_USABLE)
        self.assertEqual(resolution.reason_codes, ('IMAGE_SAFETY_UNREADABLE',))

    def test_missing_availability_is_not_usable(self) -> None:
        resolution = resolve(availability=Availability.MISSING)
        self.assertIs(resolution.usability, Usability.NOT_USABLE)
        self.assertEqual(resolution.reason_codes, ('AVAILABILITY_MISSING',))

    def test_worst_of_safety_and_availability_for_every_pair(self) -> None:
        for safety in ImageSafetyState:
            for availability in Availability:
                with self.subTest(image_safety=safety.value, availability=availability.value):
                    expected = max(SAFETY_USABILITY[safety], AVAILABILITY_USABILITY[availability], key=SEVERITY.__getitem__)
                    resolution = resolve(image_safety=safety, availability=availability)
                    self.assertIs(resolution.usability, expected)

    def test_warning_never_hides_unverified_location(self) -> None:
        artifact = make_artifact(location_state=ArtifactLocationState.AVAILABLE_UNVERIFIED)
        resolution = resolve(artifact, image_safety=ImageSafetyState.UNCERTAIN)
        self.assertIs(resolution.usability, Usability.NOT_USABLE)
        self.assertEqual(resolution.reason_codes, ('ARTIFACT_NOT_VERIFIED', 'IMAGE_SAFETY_UNCERTAIN'))

    def test_clip_and_audio_have_no_image_safety_axis(self) -> None:
        for kind in (MediaKind.CLIP, MediaKind.AUDIO):
            with self.subTest(media_kind=kind.value):
                resolution = resolve(media_kind=kind, image_safety=None)
                self.assertIs(resolution.usability, Usability.USABLE)
                self.assertIsNone(resolution.safety_state)
        with self.assertRaises(ValueError):
            resolve(media_kind=MediaKind.CLIP, image_safety=ImageSafetyState.SAFE)
        with self.assertRaises(ValueError):
            resolve(image_safety=None)


class ReadOnlyTests(unittest.TestCase):
    def test_rendition_must_reference_artifact(self) -> None:
        with self.assertRaises(ValueError):
            resolve(rendition=make_rendition(artifact_version_ref='artifact-version-other'))

    def test_resolution_does_not_change_artifact(self) -> None:
        for state in ArtifactLocationState:
            with self.subTest(location_state=state.value):
                artifact = make_artifact(location_state=state)
                snapshot = dataclasses.astuple(artifact)
                resolve(artifact, expected_sha256=OTHER_SHA256)
                self.assertEqual(dataclasses.astuple(artifact), snapshot)
                self.assertIs(artifact.location_state, state)

    def test_artifact_and_resolution_are_frozen(self) -> None:
        artifact = make_artifact()
        for value in (artifact, resolve(artifact)):
            with self.subTest(type=type(value).__name__):
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    value.location_state = ArtifactLocationState.MISSING

    def test_module_never_writes_location_state(self) -> None:
        tree = ast.parse(MODULE_FILE.read_text(encoding='utf-8'), filename=str(MODULE_FILE))
        modules: set[str] = set()
        statemachine_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
                if node.module == 'controlplane.domain.statemachine':
                    statemachine_names.update(alias.name for alias in node.names)
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            else:
                targets = []
            for target in targets:
                self.assertFalse(isinstance(target, ast.Attribute) and target.attr == 'location_state')
            if isinstance(node, ast.Attribute):
                self.assertNotEqual(node.attr, '__setattr__')
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, {'setattr', 'object'})
                self.assertFalse(node.id.startswith('transition'))
            if isinstance(node, ast.FunctionDef):
                self.assertFalse(node.name.startswith('transition'))
        self.assertEqual(statemachine_names, {'ArtifactLocationState'})
        self.assertLessEqual(
            modules,
            {
                'dataclasses',
                'types',
                'catalog.domain.identity',
                'catalog.domain.renditions',
                'catalog.domain.states',
                'controlplane.domain.statemachine',
            },
        )
