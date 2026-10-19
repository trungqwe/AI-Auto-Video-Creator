"""F-13: technical output gates (CT-QC-001): FILE_PLAYABLE, DURATION_RANGE, OUTPUT_PROFILE_VALID, VOICE_AUDIBLE.

coveredIds: CT-QC-001
"""
import ast
import dataclasses
import math
import pathlib
import re
import unittest
from enum import StrEnum

from render.domain import quality_report
from render.domain.technical_gates import (
    INPUT_NOT_READY,
    GateName,
    GateResult,
    GateStatus,
    evaluate_duration_range,
    evaluate_file_playable,
    evaluate_output_profile,
    evaluate_technical_gates,
    evaluate_voice_audible,
)
from render.ports.output_probe import OutputMeasurements, OutputProbePort

ROOT = pathlib.Path(__file__).resolve().parents[3]
GATES_SOURCE = ROOT / 'src' / 'render' / 'domain' / 'technical_gates.py'
PORT_SOURCE = ROOT / 'src' / 'render' / 'ports' / 'output_probe.py'
PASSED = GateStatus.PASSED
FAILED = GateStatus.FAILED
NOT_EVALUATED = GateStatus.NOT_EVALUATED
LOW_MS = 61000
HIGH_MS = 70000
POLICY = {'duration_range_ms': [LOW_MS, HIGH_MS], 'min_voice_level': -30.0}
PROFILE = {'container': 'mp4', 'video_codec': 'h264', 'audio_codec': 'aac', 'width': 1080, 'height': 1920, 'fps': 30}


def measure(**overrides):
    values = {
        'decodable': True, 'duration_ms': 65000, 'width': 1080, 'height': 1920, 'fps': 30, 'video_codec': 'h264',
        'audio_codec': 'aac', 'container': 'mp4', 'has_audio_stream': True, 'audio_level': -20.0, 'severe_audio_errors': (),
    }
    values.update(overrides)
    return OutputMeasurements(**values)


class FakeProbe:
    def __init__(self, measurements):
        self.measurements = measurements
        self.calls = []

    def probe(self, output_ref):
        self.calls.append(output_ref)
        return self.measurements


class ResultTestCase(unittest.TestCase):
    def assertResult(self, item, status, reason=None):
        self.assertIsInstance(item, GateResult)
        self.assertIs(item.status, status)
        if status is PASSED:
            self.assertIsNone(item.reason)
        elif reason is not None:
            self.assertTrue((item.reason or '').startswith(reason), item.reason)


class OutputMeasurementsTests(unittest.TestCase):
    def test_fields_defaults_and_frozen(self):
        names = ['decodable', 'duration_ms', 'width', 'height', 'fps', 'video_codec', 'audio_codec', 'container',
                 'has_audio_stream', 'audio_level', 'severe_audio_errors']
        item = OutputMeasurements()
        self.assertEqual([f.name for f in dataclasses.fields(item)], names)
        self.assertTrue(all(getattr(item, name) is None for name in names))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.width = 1

    def test_list_of_audio_errors_becomes_a_tuple(self):
        self.assertEqual(OutputMeasurements(severe_audio_errors=['clipping']).severe_audio_errors, ('clipping',))

    def test_fake_probe_satisfies_the_port(self):
        self.assertIsInstance(FakeProbe(measure()), OutputProbePort)
        self.assertNotIsInstance(object(), OutputProbePort)


class GateResultTests(unittest.TestCase):
    def test_declared_types_mirror_f12(self):
        self.assertTrue(issubclass(GateName, StrEnum) and issubclass(GateStatus, StrEnum))
        self.assertEqual([i.value for i in GateStatus], [i.value for i in quality_report.GateStatus])
        for item in GateName:
            self.assertEqual(quality_report.GateName(item.value).value, item.value)
        self.assertEqual([f.name for f in dataclasses.fields(GateResult)], [f.name for f in dataclasses.fields(quality_report.GateResult)])

    def test_frozen_and_non_passed_needs_reason(self):
        item = GateResult(gate='FILE_PLAYABLE', status='passed')
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.status = FAILED
        with self.assertRaises(ValueError):
            GateResult(gate=GateName.FILE_PLAYABLE, status=FAILED)

    def test_gate_outputs_are_accepted_by_f12(self):
        outputs = evaluate_technical_gates(FakeProbe(measure()), 'ref', policy=POLICY, expected_profile=PROFILE)
        outputs += evaluate_technical_gates(FakeProbe(None), 'ref', policy={}, expected_profile=None)
        for item in outputs:
            converted = quality_report.GateResult(
                gate=item.gate.value, status=item.status.value, evidence_ref=item.evidence_ref,
                measured_value=item.measured_value, threshold_revision=item.threshold_revision, reason=item.reason,
            )
            self.assertEqual(converted.status.value, item.status.value)


class FilePlayableTests(ResultTestCase):
    def test_complete_decodable_output_passes(self):
        item = evaluate_file_playable(measure())
        self.assertResult(item, PASSED)
        self.assertIs(item.gate, GateName.FILE_PLAYABLE)

    def test_missing_probe_result_or_undecodable_output_fails(self):
        self.assertResult(evaluate_file_playable(None), FAILED, 'missing_measurement')
        self.assertResult(evaluate_file_playable(measure(decodable=False)), FAILED, 'not_decodable')
        for bad in (None, 1, 'yes'):
            with self.subTest(decodable=bad):
                self.assertResult(evaluate_file_playable(measure(decodable=bad)), FAILED, 'missing_measurement')

    def test_each_missing_core_measurement_fails(self):
        for name in ('duration_ms', 'width', 'height', 'fps', 'video_codec', 'container'):
            with self.subTest(name=name):
                self.assertResult(evaluate_file_playable(measure(**{name: None})), FAILED, 'missing_measurement:' + name)

    def test_non_measurement_object_is_a_type_error(self):
        with self.assertRaises(TypeError):
            evaluate_file_playable({'decodable': True})


class DurationRangeTests(ResultTestCase):
    def run_gate(self, duration, policy=POLICY):
        return evaluate_duration_range(measure(duration_ms=duration), policy)

    def test_inclusive_boundaries(self):
        cases = ((60999, FAILED), (61000, PASSED), (61001, PASSED), (69999, PASSED), (70000, PASSED), (70001, FAILED), (0, FAILED), (-1, FAILED))
        for duration, status in cases:
            with self.subTest(duration=duration):
                self.assertResult(self.run_gate(duration), status, 'out_of_range')
        self.assertIs(self.run_gate(70001).gate, GateName.DURATION_RANGE)
        self.assertEqual(self.run_gate(70001).measured_value, 70001)

    def test_threshold_comes_from_the_policy(self):
        policy = {'duration_range_ms': (1000, 2000)}
        self.assertResult(self.run_gate(1500, policy), PASSED)
        self.assertResult(self.run_gate(LOW_MS, policy), FAILED, 'out_of_range')
        self.assertResult(self.run_gate(2001, policy), FAILED, 'out_of_range')

    def test_non_integer_duration_fails(self):
        for bad in (61000.0, 65000.5, True, False, math.nan, math.inf, '65000', [65000]):
            with self.subTest(duration=bad):
                self.assertResult(self.run_gate(bad), FAILED, 'invalid_measurement')
        self.assertIsNone(self.run_gate(math.nan).measured_value)
        self.assertResult(self.run_gate(None), FAILED, 'missing_measurement')
        self.assertResult(evaluate_duration_range(None, POLICY), FAILED, 'missing_measurement')

    def test_missing_or_malformed_threshold_is_not_evaluated(self):
        key = 'duration_range_ms'
        bad = (None, {}, 'x', {key: None}, {key: []}, {key: [LOW_MS]}, {key: [HIGH_MS, LOW_MS]}, {key: [-1, HIGH_MS]},
               {key: [True, HIGH_MS]}, {key: [LOW_MS + 0.5, HIGH_MS]}, {key: '61000-70000'}, {key: [LOW_MS, HIGH_MS, HIGH_MS]})
        for policy in bad:
            with self.subTest(policy=policy):
                self.assertResult(evaluate_duration_range(measure(), policy), NOT_EVALUATED, INPUT_NOT_READY)
        self.assertResult(evaluate_duration_range(None, None), NOT_EVALUATED, INPUT_NOT_READY)

    def test_threshold_revision_is_carried(self):
        self.assertEqual(evaluate_duration_range(measure(), POLICY, threshold_revision='policy-r1').threshold_revision, 'policy-r1')
        self.assertIsNone(evaluate_duration_range(measure(), POLICY).threshold_revision)
        self.assertIsNone(evaluate_duration_range(measure(), POLICY, threshold_revision='  ').threshold_revision)


class OutputProfileTests(ResultTestCase):
    def test_matching_output_passes_and_extra_profile_keys_are_ignored(self):
        self.assertResult(evaluate_output_profile(measure(), PROFILE), PASSED)
        self.assertResult(evaluate_output_profile(measure(), {**PROFILE, 'revision': 'r1'}), PASSED)

    def test_landscape_output_fails_for_portrait_profile(self):
        landscape = {**PROFILE, 'width': 1920, 'height': 1080}
        self.assertResult(evaluate_output_profile(measure(width=1920, height=1080), PROFILE), FAILED, 'profile_mismatch:width,height')
        self.assertResult(evaluate_output_profile(measure(), landscape), FAILED, 'profile_mismatch:width,height')
        self.assertResult(evaluate_output_profile(measure(width=1920, height=1080), landscape), PASSED)

    def test_each_field_mismatch_fails(self):
        changes = {'container': 'mkv', 'video_codec': 'vp9', 'audio_codec': 'opus', 'width': 1081, 'height': 1921, 'fps': 24}
        for name, value in changes.items():
            with self.subTest(name=name):
                item = evaluate_output_profile(measure(**{name: value}), PROFILE)
                self.assertResult(item, FAILED, 'profile_mismatch:' + name)

    def test_text_ignores_case_and_fps_compares_numerically(self):
        self.assertResult(evaluate_output_profile(measure(container=' MP4 ', video_codec='H264'), PROFILE), PASSED)
        self.assertResult(evaluate_output_profile(measure(fps=30.0), PROFILE), PASSED)
        self.assertResult(evaluate_output_profile(measure(fps=29.97), PROFILE), FAILED, 'profile_mismatch:fps')
        self.assertResult(evaluate_output_profile(measure(fps=math.nan), PROFILE), FAILED, 'profile_mismatch:fps')

    def test_missing_or_mistyped_measurement_fails(self):
        self.assertResult(evaluate_output_profile(None, PROFILE), FAILED, 'missing_measurement')
        for name in PROFILE:
            with self.subTest(name=name):
                self.assertResult(evaluate_output_profile(measure(**{name: None}), PROFILE), FAILED, 'missing_measurement:' + name)
        for name, value in (('width', '1080'), ('height', 1920.0), ('container', 5)):
            with self.subTest(name=name):
                self.assertResult(evaluate_output_profile(measure(**{name: value}), PROFILE), FAILED, 'profile_mismatch:' + name)

    def test_missing_or_malformed_profile_is_not_evaluated(self):
        cases = [None, {}, 'portrait', {**PROFILE, 'width': 0}, {**PROFILE, 'width': 1080.0}, {**PROFILE, 'width': True},
                 {**PROFILE, 'fps': math.nan}, {**PROFILE, 'fps': 0}, {**PROFILE, 'fps': '30'}, {**PROFILE, 'container': ' '},
                 {**PROFILE, 'video_codec': 7}]
        cases += [{key: value for key, value in PROFILE.items() if key != name} for name in PROFILE]
        for profile in cases:
            with self.subTest(profile=profile):
                self.assertResult(evaluate_output_profile(measure(), profile), NOT_EVALUATED, INPUT_NOT_READY)
        self.assertResult(evaluate_output_profile(None, None), NOT_EVALUATED, INPUT_NOT_READY)

    def test_threshold_revision_is_carried(self):
        self.assertEqual(evaluate_output_profile(measure(), PROFILE, threshold_revision='p1').threshold_revision, 'p1')
        self.assertEqual(evaluate_output_profile(measure(), None, threshold_revision='p1').threshold_revision, 'p1')


class VoiceAudibleTests(ResultTestCase):
    def test_audible_voice_passes(self):
        item = evaluate_voice_audible(measure(), POLICY)
        self.assertResult(item, PASSED)
        self.assertIs(item.gate, GateName.VOICE_AUDIBLE)
        self.assertEqual(item.measured_value, -20.0)

    def test_level_must_be_strictly_above_the_minimum(self):
        policy = {'min_voice_level': -20.0}
        self.assertResult(evaluate_voice_audible(measure(audio_level=-20.0), policy), FAILED, 'voice_below_min_level')
        self.assertResult(evaluate_voice_audible(measure(audio_level=-20.5), policy), FAILED, 'voice_below_min_level')
        self.assertResult(evaluate_voice_audible(measure(audio_level=-19.5), policy), PASSED)
        zero = {'min_voice_level': 0}
        self.assertResult(evaluate_voice_audible(measure(audio_level=0), zero), FAILED, 'voice_below_min_level')
        self.assertResult(evaluate_voice_audible(measure(audio_level=0.5), zero), PASSED)

    def test_no_audio_stream_fails(self):
        item = evaluate_voice_audible(measure(has_audio_stream=False, audio_level=0.0), POLICY)
        self.assertResult(item, FAILED, 'no_audio_stream')

    def test_severe_audio_error_fails(self):
        for errors in (('clipping',), ['clipping']):
            with self.subTest(errors=errors):
                self.assertResult(evaluate_voice_audible(measure(severe_audio_errors=errors), POLICY), FAILED, 'severe_audio_error')

    def test_missing_measurements_fail(self):
        self.assertResult(evaluate_voice_audible(None, POLICY), FAILED, 'missing_measurement')
        for name in ('has_audio_stream', 'audio_level', 'severe_audio_errors'):
            with self.subTest(name=name):
                self.assertResult(evaluate_voice_audible(measure(**{name: None}), POLICY), FAILED, 'missing_measurement')
        self.assertResult(evaluate_voice_audible(measure(has_audio_stream=1), POLICY), FAILED, 'missing_measurement')

    def test_malformed_measurements_fail(self):
        for level in (math.nan, math.inf, 'loud', True):
            with self.subTest(level=level):
                self.assertResult(evaluate_voice_audible(measure(audio_level=level), POLICY), FAILED, 'invalid_measurement')
        for errors in ('clipping', (1,), 5):
            with self.subTest(errors=errors):
                self.assertResult(evaluate_voice_audible(measure(severe_audio_errors=errors), POLICY), FAILED, 'invalid_measurement')

    def test_missing_or_malformed_threshold_is_not_evaluated(self):
        key = 'min_voice_level'
        for policy in (None, {}, 'x', {key: None}, {key: True}, {key: math.nan}, {key: math.inf}, {key: '-30'}):
            with self.subTest(policy=policy):
                self.assertResult(evaluate_voice_audible(measure(), policy), NOT_EVALUATED, INPUT_NOT_READY)
        self.assertResult(evaluate_voice_audible(None, None), NOT_EVALUATED, INPUT_NOT_READY)


class EvaluateTechnicalGatesTests(ResultTestCase):
    def run_all(self, measurements, **kwargs):
        kwargs.setdefault('policy', POLICY)
        kwargs.setdefault('expected_profile', PROFILE)
        return evaluate_technical_gates(FakeProbe(measurements), 'out-ref-1', **kwargs)

    def test_returns_four_gates_in_f12_order_with_evidence_ref(self):
        probe = FakeProbe(measure())
        results = evaluate_technical_gates(probe, 'out-ref-1', policy=POLICY, expected_profile=PROFILE, threshold_revision='r1')
        self.assertEqual(probe.calls, ['out-ref-1'])
        names = [item.gate.value for item in results]
        self.assertEqual(names, ['FILE_PLAYABLE', 'DURATION_RANGE', 'VOICE_AUDIBLE', 'OUTPUT_PROFILE_VALID'])
        order = [gate.value for gate in quality_report.GATE_ORDER]
        self.assertEqual(names, [name for name in order if name in names])
        self.assertTrue(all(item.status is PASSED and item.evidence_ref == 'out-ref-1' for item in results))

    def test_landscape_output_for_portrait_profile_fails_only_the_profile_gate(self):
        results = self.run_all(measure(width=1920, height=1080))
        self.assertEqual([item.status for item in results], [PASSED, PASSED, PASSED, FAILED])

    def test_too_long_video_fails_only_the_duration_gate(self):
        results = self.run_all(measure(duration_ms=70001))
        self.assertEqual([item.status for item in results], [PASSED, FAILED, PASSED, PASSED])

    def test_unreadable_probe_result_fails_every_measured_gate(self):
        results = self.run_all(None)
        self.assertEqual([item.status for item in results], [FAILED] * 4)
        self.assertTrue(all(item.reason.startswith('missing_measurement') for item in results))

    def test_missing_thresholds_are_not_evaluated(self):
        results = self.run_all(measure(), policy={}, expected_profile=None)
        self.assertEqual([item.status for item in results], [PASSED, NOT_EVALUATED, NOT_EVALUATED, NOT_EVALUATED])
        self.assertEqual([item.reason for item in results[1:]], [INPUT_NOT_READY] * 3)

    def test_blank_output_ref_is_rejected_before_probing(self):
        for bad in (None, '', '  ', 5):
            with self.subTest(output_ref=bad):
                probe = FakeProbe(measure())
                with self.assertRaises(ValueError):
                    evaluate_technical_gates(probe, bad, policy=POLICY, expected_profile=PROFILE)
                self.assertEqual(probe.calls, [])


class SourceScanTests(unittest.TestCase):
    def setUp(self):
        self.trees = {path: ast.parse(path.read_text(encoding='utf-8')) for path in (GATES_SOURCE, PORT_SOURCE)}

    def test_modules_hold_no_threshold_or_profile_values(self):
        banned = {30, 61, 70, 1080, 1920, 60999, 61000, 70000, 70001}
        for path, tree in self.trees.items():
            constants = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)]
            numbers = {v for v in constants if isinstance(v, (int, float)) and not isinstance(v, bool)}
            texts = [v for v in constants if isinstance(v, str)]
            with self.subTest(path=path.name):
                self.assertLessEqual(numbers, {0, 1, 2})
                self.assertEqual(numbers & banned, set())
                self.assertEqual([t for t in texts if re.search(r'[0-9]+ *[x*] *[0-9]+', t)], [])
                self.assertEqual([t for t in texts if 'fixture' in t.lower()], [])
                self.assertEqual({'mp4', 'h264', 'aac'} & set(texts), set())

    def test_modules_import_only_the_allowed_modules(self):
        expected = {
            GATES_SOURCE: {'__future__', 'math', 'collections.abc', 'dataclasses', 'enum', 'render.ports.output_probe'},
            PORT_SOURCE: {'__future__', 'dataclasses', 'typing'},
        }
        for path, tree in self.trees.items():
            modules = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            modules |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
            with self.subTest(path=path.name):
                self.assertEqual(modules, expected[path])

    def test_modules_declare_covered_ids(self):
        for path, tree in self.trees.items():
            doc = ast.get_docstring(tree) or ''
            with self.subTest(path=path.name):
                self.assertIn('coveredIds: CT-QC-001', doc.splitlines())
