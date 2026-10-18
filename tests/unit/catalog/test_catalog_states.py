"""C-02: catalog read-state axes (CT-STATE-005/006) and usability classification (D8-C-05)."""
import ast
import inspect
import json
import pathlib
import unittest

from catalog.domain import states
from catalog.domain.identity import MediaKind
from catalog.domain.states import (
    Availability,
    DiscoveryState,
    ImageSafetyState,
    RenditionState,
    Usability,
    classify_availability,
    classify_safety,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_FILE = ROOT / 'src' / 'catalog' / 'domain' / 'states.py'
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'c-d-media-candidates' / 'payloads.json'
EXPECTED_IMAGE_USABILITY = {
    'NOT_ASSESSED': 'not_usable',
    'ASSESSING': 'not_usable',
    'SAFE': 'usable',
    'TRANSFORM_REQUIRED': 'not_usable',
    'UNCERTAIN': 'usable_with_warning',
    'DETECTION_FAILED': 'usable_with_warning',
    'UNREADABLE': 'not_usable',
    'TRANSFORMING': 'not_usable',
    'PROCESSED_READY': 'usable',
    'TRANSFORM_FAILED': 'usable_with_warning',
}
EXPECTED_AVAILABILITY_USABILITY = {
    'AVAILABLE': 'usable',
    'UNAVAILABLE_SOURCE': 'usable',
    'MISSING': 'not_usable',
    'CORRUPT': 'not_usable',
    'RECOVERING': 'not_usable',
}
WARNING_STATES = ('UNCERTAIN', 'DETECTION_FAILED', 'TRANSFORM_FAILED')


def load_media_candidates() -> list[dict]:
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    return data['entities']['MediaCandidate']['valid']


class EnumValueTests(unittest.TestCase):
    def test_discovery_state_values(self) -> None:
        self.assertEqual({s.value for s in DiscoveryState}, {'DISCOVERED', 'ACQUIRING', 'CATALOGED', 'FAILED'})

    def test_rendition_state_values(self) -> None:
        self.assertEqual(
            {s.value for s in RenditionState},
            {'DECLARED', 'PROCESSING', 'READY', 'FAILED', 'OUTCOME_UNKNOWN'},
        )

    def test_availability_values(self) -> None:
        self.assertEqual({s.value for s in Availability}, set(EXPECTED_AVAILABILITY_USABILITY))

    def test_image_safety_state_values(self) -> None:
        self.assertEqual({s.value for s in ImageSafetyState}, set(EXPECTED_IMAGE_USABILITY))

    def test_usability_values(self) -> None:
        self.assertEqual({u.value for u in Usability}, {'usable', 'usable_with_warning', 'not_usable'})

    def test_contract_state_names_equal_values(self) -> None:
        for enum_cls in (DiscoveryState, RenditionState, Availability, ImageSafetyState):
            with self.subTest(enum=enum_cls.__name__):
                self.assertEqual([m.name for m in enum_cls], [m.value for m in enum_cls])


class SafetyClassificationTests(unittest.TestCase):
    def test_image_mapping_covers_every_state(self) -> None:
        for name, expected in EXPECTED_IMAGE_USABILITY.items():
            with self.subTest(state=name):
                self.assertIs(classify_safety(MediaKind.IMAGE, ImageSafetyState[name]), Usability(expected))

    def test_warning_states_are_never_usable(self) -> None:
        for name in WARNING_STATES:
            with self.subTest(state=name):
                result = classify_safety(MediaKind.IMAGE, ImageSafetyState[name])
                self.assertIsNot(result, Usability.USABLE)
                self.assertIs(result, Usability.USABLE_WITH_WARNING)

    def test_unreadable_is_not_usable(self) -> None:
        self.assertIs(classify_safety(MediaKind.IMAGE, ImageSafetyState.UNREADABLE), Usability.NOT_USABLE)

    def test_clip_and_audio_without_safety_are_usable(self) -> None:
        for kind in (MediaKind.CLIP, MediaKind.AUDIO):
            with self.subTest(kind=kind.value):
                self.assertIs(classify_safety(kind, None), Usability.USABLE)

    def test_clip_and_audio_reject_safety_state(self) -> None:
        for kind in (MediaKind.CLIP, MediaKind.AUDIO):
            for state in ImageSafetyState:
                with self.subTest(kind=kind.value, state=state.value):
                    with self.assertRaises(ValueError):
                        classify_safety(kind, state)

    def test_image_requires_safety_state(self) -> None:
        with self.assertRaises(ValueError):
            classify_safety(MediaKind.IMAGE, None)

    def test_rejects_unknown_safety_value(self) -> None:
        with self.assertRaises(ValueError):
            classify_safety(MediaKind.IMAGE, 'BLURRED')


class AvailabilityClassificationTests(unittest.TestCase):
    def test_mapping_covers_every_value(self) -> None:
        for name, expected in EXPECTED_AVAILABILITY_USABILITY.items():
            with self.subTest(availability=name):
                self.assertIs(classify_availability(Availability[name]), Usability(expected))

    def test_unavailable_source_keeps_eligibility(self) -> None:
        self.assertIs(classify_availability(Availability.UNAVAILABLE_SOURCE), Usability.USABLE)

    def test_rejects_unknown_availability(self) -> None:
        with self.assertRaises(ValueError):
            classify_availability('GONE')

    def test_fixture_candidate_availability_is_usable(self) -> None:
        candidates = load_media_candidates()
        self.assertTrue(candidates, 'fixture has no valid MediaCandidate payload')
        for payload in candidates:
            with self.subTest(availability=payload['availability']):
                self.assertIs(classify_availability(Availability(payload['availability'])), Usability.USABLE)


class ModuleSurfaceTests(unittest.TestCase):
    def test_no_transition_names(self) -> None:
        names = [name for name in vars(states) if name.lower().startswith('transition')]
        self.assertEqual(names, [])

    def test_public_functions_are_classifiers_only(self) -> None:
        functions = sorted(
            name
            for name, obj in vars(states).items()
            if inspect.isfunction(obj) and obj.__module__ == states.__name__ and not name.startswith('_')
        )
        self.assertEqual(functions, ['classify_availability', 'classify_safety'])

    def test_does_not_import_controlplane_state_machine(self) -> None:
        tree = ast.parse(MODULE_FILE.read_text(encoding='utf-8'))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or '')
        self.assertEqual([m for m in modules if m.startswith(('controlplane', 'src.'))], [])
