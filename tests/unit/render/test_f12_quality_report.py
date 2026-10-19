"""F-12: QualityReport, gate groups and pass verdict (CT-QC-001, CT-QC-002).

coveredIds: CT-QC-001, CT-QC-002
"""
import ast
import dataclasses
import pathlib
import re
import unittest
from enum import StrEnum

from controlplane.application.idempotency.canonicalization import request_hash
from render.domain.quality_report import (
    DUPLICATE_GATE,
    GATE_KINDS,
    GATE_ORDER,
    INPUT_NOT_READY,
    GateKind,
    GateName,
    GateResult,
    GateStatus,
    QualityPolicy,
    QualityReport,
    QualityReportError,
    build_quality_report,
    compute_report_id,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'render' / 'domain' / 'quality_report.py'
HARD = (
    'FILE_PLAYABLE', 'DURATION_RANGE', 'VISUAL_HOOK_PRESENT', 'AUDIO_HOOK_PRESENT', 'THUMBNAIL_PRESENT',
    'SUBTITLE_BURNED_IN', 'KARAOKE_TIMING_VALID', 'VOICE_AUDIBLE', 'ENGLISH_OUTPUT_VALID', 'OUTPUT_PROFILE_VALID',
)
CONDITIONAL = 'INFERENCE_DISCLOSURE_PRESENT'
WARNINGS = ('VISUAL_CONTINUITY', 'AUDIO_MIX_QUALITY')
ALL_NAMES = (*HARD, CONDITIONAL, *WARNINGS)
POLICY_REVISION = 'fixture-policy-1'
PASSED = GateStatus.PASSED
FAILED = GateStatus.FAILED
NOT_EVALUATED = GateStatus.NOT_EVALUATED
NOT_APPLICABLE = GateStatus.NOT_APPLICABLE


def result(name, status=PASSED, **kwargs):
    if status is not PASSED:
        kwargs.setdefault('reason', 'fixture-reason')
    return GateResult(gate=name, status=status, **kwargs)


def full_results(skip=(), **overrides):
    """One result per gate (warnings carry a threshold_revision); overrides replace the result of a gate."""
    items = []
    for name in ALL_NAMES:
        if name in skip:
            continue
        if name in overrides:
            items.append(overrides[name])
        elif name in WARNINGS:
            items.append(result(name, threshold_revision=POLICY_REVISION))
        else:
            items.append(result(name))
    return items


def by_gate(report):
    return {item.gate.value: item for item in report.gates}


class ReportTestCase(unittest.TestCase):
    def assertRejected(self, code, field, func, *args, **kwargs):
        with self.assertRaises(QualityReportError) as caught:
            func(*args, **kwargs)
        self.assertEqual((caught.exception.code, caught.exception.field), (code, field))


class EnumTests(ReportTestCase):
    def test_gate_name_is_str_enum_with_exactly_thirteen_gates(self):
        self.assertTrue(issubclass(GateName, StrEnum))
        self.assertEqual([item.name for item in GateName], list(ALL_NAMES))
        self.assertEqual([item.value for item in GateName], list(ALL_NAMES))
        self.assertEqual(GATE_ORDER, tuple(GateName))
        self.assertEqual(len(GATE_ORDER), 13)

    def test_gate_kind_and_status_values(self):
        self.assertTrue(issubclass(GateKind, StrEnum))
        self.assertTrue(issubclass(GateStatus, StrEnum))
        self.assertEqual([item.value for item in GateKind], ['hard', 'hard_conditional', 'warning'])
        self.assertEqual([item.value for item in GateStatus], ['passed', 'failed', 'not_applicable', 'not_evaluated'])

    def test_gate_kinds_follow_the_ct_qc_001_table(self):
        self.assertEqual(set(GATE_KINDS), set(GateName))
        for name in HARD:
            self.assertIs(GATE_KINDS[GateName(name)], GateKind.HARD, name)
        self.assertIs(GATE_KINDS[GateName(CONDITIONAL)], GateKind.HARD_CONDITIONAL)
        for name in WARNINGS:
            self.assertIs(GATE_KINDS[GateName(name)], GateKind.WARNING, name)
        with self.assertRaises(TypeError):
            GATE_KINDS[GateName.FILE_PLAYABLE] = GateKind.WARNING


class GateResultTests(ReportTestCase):
    def test_fields_and_frozen(self):
        item = result('FILE_PLAYABLE', evidence_ref='fixture-evidence', measured_value=1.5, threshold_revision=POLICY_REVISION)
        names = ['gate', 'status', 'evidence_ref', 'time_range', 'measured_value', 'threshold_revision', 'reason']
        self.assertEqual([f.name for f in dataclasses.fields(item)], names)
        self.assertIs(item.gate, GateName.FILE_PLAYABLE)
        self.assertIs(item.kind, GateKind.HARD)
        for name, value in (('status', FAILED), ('reason', 'x'), ('gate', GateName.DURATION_RANGE)):
            with self.subTest(name=name), self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(item, name, value)

    def test_text_inputs_are_coerced_to_enums(self):
        item = GateResult(gate='VOICE_AUDIBLE', status='failed', reason='fixture-reason')
        self.assertIs(item.gate, GateName.VOICE_AUDIBLE)
        self.assertIs(item.status, FAILED)

    def test_unknown_or_malformed_gate_name_is_rejected(self):
        cases = (('BOGUS_GATE', 'unknown_gate'), ('file_playable', 'unknown_gate'), ('', 'unknown_gate'), (1, 'wrong_type'), (None, 'wrong_type'))
        for bad, code in cases:
            with self.subTest(bad=bad):
                self.assertRejected(code, 'gate', GateResult, gate=bad, status=PASSED)

    def test_unknown_status_is_rejected(self):
        self.assertRejected('invalid_value', 'status', GateResult, gate='FILE_PLAYABLE', status='ok')
        self.assertRejected('wrong_type', 'status', GateResult, gate='FILE_PLAYABLE', status=1)

    def test_time_range_is_a_pair_of_non_negative_ordered_integers(self):
        self.assertEqual(result('THUMBNAIL_PRESENT', time_range=[100, 250]).time_range, (100, 250))
        self.assertEqual(result('THUMBNAIL_PRESENT', time_range=(0, 0)).time_range, (0, 0))
        cases = (((250, 100), 'invalid_value'), ((-1, 5), 'invalid_value'), ((0, 2 ** 53), 'invalid_value'), ((True, 5), 'wrong_type'), ((1.5, 5), 'wrong_type'), ((1,), 'wrong_type'), ((1, 2, 3), 'wrong_type'), ('12', 'wrong_type'))
        for bad, code in cases:
            with self.subTest(bad=bad):
                self.assertRejected(code, 'time_range', result, 'THUMBNAIL_PRESENT', time_range=bad)

    def test_measured_value_accepts_only_finite_scalars(self):
        for good in (None, 'text', True, 0, 61000, 2.5):
            with self.subTest(good=good):
                self.assertEqual(result('DURATION_RANGE', measured_value=good).measured_value, good)
        cases = ((float('nan'), 'invalid_value'), (float('inf'), 'invalid_value'), (2 ** 53, 'invalid_value'), ([1], 'wrong_type'), ({'a': 1}, 'wrong_type'), (b'x', 'wrong_type'))
        for bad, code in cases:
            with self.subTest(bad=repr(bad)):
                self.assertRejected(code, 'measured_value', result, 'DURATION_RANGE', measured_value=bad)

    def test_optional_text_fields_reject_blank_and_non_text(self):
        for field in ('evidence_ref', 'threshold_revision', 'reason'):
            for bad, code in (('', 'invalid_value'), ('  ', 'invalid_value'), (5, 'wrong_type')):
                with self.subTest(field=field, bad=bad):
                    values = {'reason': 'fixture-reason', field: bad}
                    self.assertRejected(code, field, GateResult, gate='FILE_PLAYABLE', status=FAILED, **values)

    def test_reason_is_required_unless_passed(self):
        self.assertIsNone(GateResult(gate='FILE_PLAYABLE', status=PASSED).reason)
        for status in (FAILED, NOT_EVALUATED):
            with self.subTest(status=status):
                self.assertRejected('missing_required', 'reason', GateResult, gate='FILE_PLAYABLE', status=status)
        self.assertRejected('missing_required', 'reason', GateResult, gate=CONDITIONAL, status=NOT_APPLICABLE)

    def test_not_applicable_is_only_for_hard_conditional_gates(self):
        self.assertIs(result(CONDITIONAL, NOT_APPLICABLE).status, NOT_APPLICABLE)
        for name in (*HARD, *WARNINGS):
            with self.subTest(name=name):
                self.assertRejected('invalid_value', 'status', result, name, NOT_APPLICABLE)


class QualityPolicyTests(ReportTestCase):
    def make(self, **thresholds):
        return QualityPolicy(revision=POLICY_REVISION, thresholds=thresholds)

    def test_policy_is_frozen_with_revision_and_thresholds(self):
        policy = self.make(VISUAL_CONTINUITY={'max_gap_ms': 40})
        self.assertEqual([f.name for f in dataclasses.fields(policy)], ['revision', 'thresholds'])
        self.assertEqual(policy.revision, POLICY_REVISION)
        for name, value in (('revision', 'other'), ('thresholds', {})):
            with self.subTest(name=name), self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(policy, name, value)

    def test_thresholds_are_deeply_read_only_and_detached_from_source(self):
        source = {'VISUAL_CONTINUITY': {'max_gap_ms': 40, 'bands': [1, {'inner': 2}]}}
        policy = QualityPolicy(revision=POLICY_REVISION, thresholds=source)
        source['VISUAL_CONTINUITY']['max_gap_ms'] = 99
        source['VISUAL_CONTINUITY']['bands'].append(3)
        self.assertEqual(policy.thresholds['VISUAL_CONTINUITY']['max_gap_ms'], 40)
        self.assertEqual(len(policy.thresholds['VISUAL_CONTINUITY']['bands']), 2)
        with self.assertRaises(TypeError):
            policy.thresholds['VISUAL_CONTINUITY'] = {}
        with self.assertRaises(TypeError):
            policy.thresholds['VISUAL_CONTINUITY']['max_gap_ms'] = 1
        with self.assertRaises(TypeError):
            policy.thresholds['VISUAL_CONTINUITY']['bands'][1]['inner'] = 9

    def test_revision_and_thresholds_are_validated(self):
        for bad, code in ((None, 'missing_required'), ('', 'invalid_value'), ('  ', 'invalid_value'), (3, 'wrong_type')):
            with self.subTest(bad=bad):
                self.assertRejected(code, 'revision', QualityPolicy, revision=bad, thresholds={})
        self.assertRejected('wrong_type', 'thresholds', QualityPolicy, revision=POLICY_REVISION, thresholds=[('FILE_PLAYABLE', 1)])
        self.assertRejected('wrong_type', 'thresholds', QualityPolicy, revision=POLICY_REVISION, thresholds=None)

    def test_threshold_keys_must_be_known_gate_names_and_values_json_like(self):
        rev = POLICY_REVISION
        self.assertRejected('unknown_gate', 'thresholds', QualityPolicy, revision=rev, thresholds={'BOGUS_GATE': 1})
        self.assertRejected('wrong_type', 'thresholds', QualityPolicy, revision=rev, thresholds={1: 1})
        self.assertRejected('invalid_value', 'thresholds', QualityPolicy, revision=rev, thresholds={'FILE_PLAYABLE': float('nan')})
        self.assertRejected('wrong_type', 'thresholds', QualityPolicy, revision=rev, thresholds={'FILE_PLAYABLE': {1, 2}})

    def test_has_threshold(self):
        policy = self.make(VISUAL_CONTINUITY={'max_gap_ms': 40}, AUDIO_MIX_QUALITY={}, FILE_PLAYABLE=None, VOICE_AUDIBLE=0)
        self.assertTrue(policy.has_threshold('VISUAL_CONTINUITY'))
        self.assertTrue(policy.has_threshold(GateName.VISUAL_CONTINUITY))
        self.assertTrue(policy.has_threshold('VOICE_AUDIBLE'))
        self.assertFalse(policy.has_threshold('AUDIO_MIX_QUALITY'))
        self.assertFalse(policy.has_threshold('FILE_PLAYABLE'))
        self.assertFalse(policy.has_threshold('DURATION_RANGE'))
        self.assertRejected('unknown_gate', 'gate', policy.has_threshold, 'BOGUS_GATE')

    def test_equal_policies_are_equal_and_hashable(self):
        first, second = self.make(VISUAL_CONTINUITY={'a': 1}), self.make(VISUAL_CONTINUITY={'a': 1})
        self.assertEqual(first, second)
        self.assertEqual(len({first, second, self.make()}), 2)


class BuildQualityReportTests(ReportTestCase):
    def test_all_gates_passed_is_a_passing_report(self):
        report = build_quality_report(full_results(), {CONDITIONAL: True})
        self.assertIsInstance(report, QualityReport)
        self.assertTrue(report.passed)
        self.assertEqual(report.blocking_gates, ())
        self.assertEqual(tuple(item.gate for item in report.gates), GATE_ORDER)
        self.assertEqual(len(report.gates), 13)

    def test_report_is_frozen(self):
        report = build_quality_report(full_results())
        for name, value in (('passed', False), ('report_id', 'x'), ('gates', ()), ('policy_revision', 'x')):
            with self.subTest(name=name), self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(report, name, value)
        self.assertIsInstance(report.gates, tuple)

    def test_report_id_is_request_hash_of_the_report_content(self):
        policy = QualityPolicy(revision=POLICY_REVISION, thresholds={'VISUAL_CONTINUITY': {'max_gap_ms': 40}})
        duration = result('DURATION_RANGE', measured_value=61500, threshold_revision=POLICY_REVISION, time_range=[0, 61500], evidence_ref='fixture-evidence')
        report = build_quality_report(full_results(DURATION_RANGE=duration), None, policy=policy)
        rows = [
            {'gate': g.gate.value, 'status': g.status.value, 'evidence_ref': g.evidence_ref,
             'time_range': None if g.time_range is None else list(g.time_range), 'measured_value': g.measured_value,
             'threshold_revision': g.threshold_revision, 'reason': g.reason}
            for g in report.gates
        ]
        self.assertEqual(report.report_id, request_hash({'policy_revision': POLICY_REVISION, 'gates': rows}))
        self.assertEqual(report.report_id, compute_report_id(POLICY_REVISION, report.gates))
        self.assertIsNotNone(re.fullmatch(r'[0-9a-f]{64}', report.report_id))
        self.assertEqual(report.policy_revision, POLICY_REVISION)

    def test_report_id_is_stable_and_sensitive_to_content(self):
        base = build_quality_report(full_results())
        self.assertEqual(base, build_quality_report(full_results()))
        self.assertEqual(base.report_id, build_quality_report(list(reversed(full_results()))).report_id)
        changed = build_quality_report(full_results(DURATION_RANGE=result('DURATION_RANGE', measured_value=61500)))
        self.assertNotEqual(base.report_id, changed.report_id)
        failed = build_quality_report(full_results(FILE_PLAYABLE=result('FILE_PLAYABLE', FAILED)))
        self.assertNotEqual(base.report_id, failed.report_id)
        thresholds = {name: {'k': 1} for name in WARNINGS}
        first = build_quality_report(full_results(), policy=QualityPolicy(revision='fixture-policy-1', thresholds=thresholds))
        second = build_quality_report(full_results(), policy=QualityPolicy(revision='fixture-policy-2', thresholds=thresholds))
        self.assertNotEqual(first.report_id, second.report_id)

    def test_missing_hard_gate_makes_report_fail(self):
        for name in HARD:
            with self.subTest(name=name):
                report = build_quality_report(full_results(skip=(name,)), {CONDITIONAL: True})
                self.assertFalse(report.passed)
                item = by_gate(report)[name]
                self.assertIs(item.status, NOT_EVALUATED)
                self.assertEqual(item.reason, 'missing_result')
                self.assertEqual(report.blocking_gates, (GateName(name),))

    def test_failed_or_not_evaluated_hard_gate_makes_report_fail(self):
        for name in HARD:
            for status in (FAILED, NOT_EVALUATED):
                with self.subTest(name=name, status=status):
                    report = build_quality_report(full_results(**{name: result(name, status)}))
                    self.assertFalse(report.passed)
                    self.assertEqual(report.blocking_gates, (GateName(name),))
                    self.assertIs(by_gate(report)[name].status, status)

    def test_empty_results_never_pass(self):
        report = build_quality_report([])
        self.assertFalse(report.passed)
        self.assertEqual(report.blocking_gates, tuple(GateName(name) for name in (*HARD, CONDITIONAL)))
        self.assertEqual(len(report.gates), 13)

    def test_failing_warnings_never_fail_the_report(self):
        items = full_results(
            VISUAL_CONTINUITY=result('VISUAL_CONTINUITY', FAILED, threshold_revision=POLICY_REVISION),
            AUDIO_MIX_QUALITY=result('AUDIO_MIX_QUALITY', FAILED, threshold_revision=POLICY_REVISION),
        )
        report = build_quality_report(items)
        self.assertTrue(report.passed)
        self.assertEqual(report.blocking_gates, ())
        for name in WARNINGS:
            self.assertIs(by_gate(report)[name].status, FAILED)

    def test_warning_without_threshold_is_not_evaluated_with_input_not_ready(self):
        self.assertEqual(INPUT_NOT_READY, 'INPUT_NOT_READY')
        for name in WARNINGS:
            for given in (result(name), result(name, FAILED), result(name, NOT_EVALUATED), None):
                with self.subTest(name=name, given=given):
                    items = full_results(skip=(name,)) if given is None else full_results(**{name: given})
                    report = build_quality_report(items)
                    item = by_gate(report)[name]
                    self.assertIs(item.status, NOT_EVALUATED)
                    self.assertEqual(item.reason, INPUT_NOT_READY)
                    self.assertIsNone(item.threshold_revision)
                    self.assertTrue(report.passed)

    def test_unready_warning_drops_measurements(self):
        given = result('AUDIO_MIX_QUALITY', measured_value=0.4, evidence_ref='fixture-evidence')
        item = by_gate(build_quality_report(full_results(AUDIO_MIX_QUALITY=given)))['AUDIO_MIX_QUALITY']
        self.assertIsNone(item.measured_value)
        self.assertIsNone(item.evidence_ref)

    def test_warning_threshold_must_also_exist_in_the_policy(self):
        ready = QualityPolicy(revision=POLICY_REVISION, thresholds={name: {'k': 1} for name in WARNINGS})
        partial = QualityPolicy(revision=POLICY_REVISION, thresholds={'VISUAL_CONTINUITY': {'k': 1}})
        report = build_quality_report(full_results(), policy=ready)
        for name in WARNINGS:
            self.assertIs(by_gate(report)[name].status, PASSED)
        report = build_quality_report(full_results(), policy=partial)
        self.assertIs(by_gate(report)['VISUAL_CONTINUITY'].status, PASSED)
        self.assertIs(by_gate(report)['AUDIO_MIX_QUALITY'].status, NOT_EVALUATED)
        self.assertEqual(by_gate(report)['AUDIO_MIX_QUALITY'].reason, INPUT_NOT_READY)
        self.assertTrue(report.passed)

    def test_not_applicable_disclosure_is_not_counted(self):
        for given in (None, result(CONDITIONAL), result(CONDITIONAL, FAILED), result(CONDITIONAL, NOT_APPLICABLE)):
            with self.subTest(given=given):
                items = full_results(skip=(CONDITIONAL,)) if given is None else full_results(**{CONDITIONAL: given})
                report = build_quality_report(items, {CONDITIONAL: False})
                item = by_gate(report)[CONDITIONAL]
                self.assertIs(item.status, NOT_APPLICABLE)
                self.assertEqual(item.reason, 'not_applicable')
                self.assertTrue(report.passed)
                self.assertEqual(report.blocking_gates, ())

    def test_applicable_disclosure_must_pass(self):
        applicabilities = ({CONDITIONAL: True}, {GateName.INFERENCE_DISCLOSURE_PRESENT: True}, {}, None)
        for applicability in applicabilities:
            with self.subTest(applicability=applicability):
                self.assertTrue(build_quality_report(full_results(), applicability).passed)
                for given in (None, result(CONDITIONAL, FAILED), result(CONDITIONAL, NOT_EVALUATED), result(CONDITIONAL, NOT_APPLICABLE)):
                    items = full_results(skip=(CONDITIONAL,)) if given is None else full_results(**{CONDITIONAL: given})
                    report = build_quality_report(items, applicability)
                    self.assertFalse(report.passed)
                    self.assertEqual(report.blocking_gates, (GateName.INFERENCE_DISCLOSURE_PRESENT,))

    def test_not_applicable_result_contradicting_applicability_is_not_evaluated(self):
        report = build_quality_report(full_results(**{CONDITIONAL: result(CONDITIONAL, NOT_APPLICABLE)}), {CONDITIONAL: True})
        item = by_gate(report)[CONDITIONAL]
        self.assertIs(item.status, NOT_EVALUATED)
        self.assertEqual(item.reason, 'applicability_mismatch')

    def test_applicability_only_changes_the_conditional_gate(self):
        report = build_quality_report(full_results(FILE_PLAYABLE=result('FILE_PLAYABLE', FAILED)), {CONDITIONAL: False})
        self.assertFalse(report.passed)
        self.assertEqual(report.blocking_gates, (GateName.FILE_PLAYABLE,))

    def test_invalid_applicability_is_rejected(self):
        build = build_quality_report
        self.assertRejected('invalid_value', 'applicability', build, full_results(), {'FILE_PLAYABLE': False})
        self.assertRejected('invalid_value', 'applicability', build, full_results(), {'VISUAL_CONTINUITY': False})
        self.assertRejected('unknown_gate', 'applicability', build, full_results(), {'BOGUS_GATE': False})
        for bad in (1, 0, 'false', None):
            with self.subTest(bad=bad):
                self.assertRejected('wrong_type', 'applicability', build, full_results(), {CONDITIONAL: bad})
        self.assertRejected('wrong_type', 'applicability', build, full_results(), [CONDITIONAL])

    def test_duplicate_gate_results_are_rejected(self):
        self.assertEqual(DUPLICATE_GATE, 'duplicate_gate')
        for name in ALL_NAMES:
            with self.subTest(name=name):
                self.assertRejected('duplicate_gate', name, build_quality_report, [*full_results(), result(name)])
        self.assertRejected('duplicate_gate', 'FILE_PLAYABLE', build_quality_report, [*full_results(), result('FILE_PLAYABLE', FAILED)])
        twin = result('FILE_PLAYABLE')
        items = [*full_results(skip=('FILE_PLAYABLE',)), twin, twin]
        self.assertRejected('duplicate_gate', 'FILE_PLAYABLE', build_quality_report, items)

    def test_unknown_gate_and_malformed_inputs_are_rejected(self):
        self.assertRejected('unknown_gate', 'gate', GateResult, gate='BOGUS_GATE', status=PASSED)
        bogus = {'gate': 'BOGUS_GATE', 'status': 'passed'}
        self.assertRejected('wrong_type', 'results', build_quality_report, [*full_results(), bogus])
        self.assertRejected('wrong_type', 'results', build_quality_report, None)
        self.assertRejected('wrong_type', 'results', build_quality_report, 'FILE_PLAYABLE')
        self.assertRejected('wrong_type', 'policy', build_quality_report, full_results(), None, policy={'revision': 'x'})

    def test_results_may_be_any_iterable_and_are_not_mutated(self):
        items = full_results()
        snapshot = list(items)
        self.assertTrue(build_quality_report(iter(items)).passed)
        self.assertTrue(build_quality_report(tuple(items)).passed)
        self.assertEqual(items, snapshot)


class QualityReportValueTests(ReportTestCase):
    def make_report(self):
        return build_quality_report(full_results())

    def fields(self, report, **overrides):
        values = {'report_id': report.report_id, 'policy_revision': report.policy_revision, 'gates': report.gates, 'passed': report.passed}
        return values | overrides

    def test_field_names(self):
        self.assertEqual([f.name for f in dataclasses.fields(QualityReport)], ['report_id', 'policy_revision', 'gates', 'passed'])

    def test_rebuilding_from_its_own_fields_is_equal_and_hashable(self):
        report = self.make_report()
        rebuilt = QualityReport(**self.fields(report))
        self.assertEqual(rebuilt, report)
        self.assertEqual(len({report, rebuilt, build_quality_report(full_results())}), 1)

    def test_inconsistent_passed_or_report_id_is_rejected(self):
        report = self.make_report()
        self.assertRejected('invalid_value', 'passed', QualityReport, **self.fields(report, passed=False))
        self.assertRejected('invalid_value', 'passed', QualityReport, **self.fields(report, passed=1))
        self.assertRejected('invalid_value', 'report_id', QualityReport, **self.fields(report, report_id='0' * 64))
        failing = build_quality_report(full_results(FILE_PLAYABLE=result('FILE_PLAYABLE', FAILED)))
        self.assertFalse(failing.passed)
        self.assertRejected('invalid_value', 'passed', QualityReport, **self.fields(failing, passed=True))

    def test_gates_must_be_the_complete_ordered_set(self):
        report = self.make_report()
        gates = list(report.gates)
        for bad in (gates[:-1], gates[1:], list(reversed(gates)), [*gates, gates[0]], []):
            with self.subTest(count=len(bad)):
                self.assertRejected('invalid_value', 'gates', QualityReport, **self.fields(report, gates=tuple(bad)))
        self.assertRejected('wrong_type', 'gates', QualityReport, **self.fields(report, gates=(*gates[:-1], 'x')))

    def test_policy_revision_is_validated(self):
        report = self.make_report()
        self.assertRejected('invalid_value', 'policy_revision', QualityReport, **self.fields(report, policy_revision=''))


class SourceScanTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(SOURCE.read_text(encoding='utf-8'))

    def test_module_holds_no_threshold_or_profile_numbers(self):
        constants = [node.value for node in ast.walk(self.tree) if isinstance(node, ast.Constant)]
        numbers = {v for v in constants if isinstance(v, (int, float)) and not isinstance(v, bool)}
        self.assertLessEqual(numbers, {0, 1, 2, 53})
        texts = [v for v in constants if isinstance(v, str)]
        self.assertEqual([t for t in texts if re.search(r'[0-9]+ *[x*] *[0-9]+', t)], [])
        self.assertEqual([t for t in texts if 'fixture' in t.lower()], [])

    def test_module_imports_only_pure_stdlib_and_the_shared_canonicalizer(self):
        modules = {a.name for n in ast.walk(self.tree) if isinstance(n, ast.Import) for a in n.names}
        modules |= {n.module for n in ast.walk(self.tree) if isinstance(n, ast.ImportFrom)}
        canonicalizer = 'controlplane.application.idempotency.canonicalization'
        self.assertEqual(modules, {'__future__', 'math', 'collections.abc', 'dataclasses', 'enum', 'types', canonicalizer})
        imported = {(n.module, a.name) for n in ast.walk(self.tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        self.assertIn((canonicalizer, 'request_hash'), imported)

    def test_module_declares_covered_ids(self):
        doc = ast.get_docstring(self.tree) or ''
        self.assertTrue(any(line.startswith('coveredIds:') for line in doc.splitlines()))
