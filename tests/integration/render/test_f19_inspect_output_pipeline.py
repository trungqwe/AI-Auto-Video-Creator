"""F-19: integration InspectOutput và PrepareOutputReady trong tiến trình (CT-QC-001, CT-RND-005).

coveredIds: CT-QC-001, CT-RND-005, TST-E2E-INV-009, TST-QC-INV-019, TST-E2E-001 (đoạn QC)
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from controlplane.domain.statemachine import OperationState
from render.application.inspect_output import (
    COMMAND_INSPECT, AttemptPackageMismatch, InspectOutputCommand, OutputNotInspectable, OutputPipeline, PrepareOutputReadyCommand,
    QualityReportNotFound,
)
from render.application.package_pipeline import IdempotencyConflict, RenderPackageNotFound, StaleGrant
from render.application.render_video import RenderAttemptNotFound
from render.domain.content_gates import ExpectedLanguageRevisions
from render.domain.quality_report import GateName, GateResult, GateStatus, QualityPolicy
from render.ports.output_inspector import (
    AudioHookEvidence, DisclosureEvidence, DisclosureObservation, KaraokeEvidence, KaraokeWordObservation, LanguageEvidence,
    OutputEvidence, SubtitleEvidence, ThumbnailEvidence, VisualHookEvidence,
)
from render.ports.output_probe import OutputMeasurements, OutputProbePort
from render.ports.renderer import OutputObservationPort
from render.ports.repositories import KIND_QUALITY_REPORT
from test_f17_resolve_validate_pipeline import SCRIPT_FP, SUBTITLE_HASH, VOICE_HASH, _context, _inputs
from test_f18_render_video_pipeline import CONTENT_SHA, RenderRig, out_ref, snapshot

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'render' / 'application' / 'inspect_output.py'
S = OperationState
THUMB_REF = '00000000-0000-4000-8000-000000000056'
WORDS = ({'start_ms': 0}, {'start_ms': 400}, {'start_ms': 900})
SEGMENTS = ({'segment_id': 's1', 'claim_mode': 'source_backed'}, {'segment_id': 's2', 'claim_mode': 'inference'})
PROFILE = {'container': 'mp4', 'video_codec': 'h264', 'audio_codec': 'aac', 'width': 1080, 'height': 1920, 'fps': 30}
POLICY = QualityPolicy(revision='qc-policy-v1', thresholds={
    'DURATION_RANGE': {'duration_range_ms': [61000, 70000]},
    'VOICE_AUDIBLE': {'min_voice_level': -30.0},
    'OUTPUT_PROFILE_VALID': PROFILE,
    'VISUAL_HOOK_PRESENT': {'min_similarity': 0.8},
    'AUDIO_HOOK_PRESENT': {'min_level_db': -30.0},
    'SUBTITLE_BURNED_IN': {'min_frames_with_text': 10},
    'KARAOKE_TIMING_VALID': {'tolerance_ms': 80},
    'ENGLISH_OUTPUT_VALID': {'required_language': 'en'},
})
POLICY_WITH_WARNING = QualityPolicy(revision='qc-policy-v1', thresholds={**POLICY.thresholds, 'VISUAL_CONTINUITY': {'max_gap_ms': 500}})
EXPECTED = ExpectedLanguageRevisions(script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH, subtitle_text_hash=SUBTITLE_HASH)


def measured(**changes) -> OutputMeasurements:
    values = dict(
        decodable=True, duration_ms=65000, width=1080, height=1920, fps=30.0, video_codec='h264', audio_codec='aac', container='mp4',
        has_audio_stream=True, audio_level=-12.0, severe_audio_errors=(),
    )
    values.update(changes)
    return OutputMeasurements(**values)


def karaoke(offsets=(0, 5, -20)) -> KaraokeEvidence:
    marks = tuple(KaraokeWordObservation(word_index=i, highlight_ms=WORDS[i]['start_ms'] + offset) for i, offset in enumerate(offsets))
    return KaraokeEvidence(evidence_ref='ev-karaoke', observations=marks)


def language(**changes) -> LanguageEvidence:
    values = dict(
        evidence_ref='ev-lang', script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH, subtitle_text_hash=SUBTITLE_HASH,
        output_metadata_revision='out-meta-v1', script_locale='en', voice_locale='en-US', subtitle_locale='en', title_locale='en', hashtag_locale='en',
    )
    values.update(changes)
    return LanguageEvidence(**values)


def evidence(**changes) -> OutputEvidence:
    values = dict(
        visual_hook=VisualHookEvidence(evidence_ref='ev-visual', start_ms=500, end_ms=2500, similarity=0.9),
        audio_hook=AudioHookEvidence(evidence_ref='ev-audio', start_ms=500, end_ms=2500, level_db=-20.0),
        thumbnail=ThumbnailEvidence(evidence_ref='ev-thumb', time_ms=1000, asset_ref=THUMB_REF),
        subtitle=SubtitleEvidence(evidence_ref='ev-sub', frames_with_text=120), karaoke=karaoke(), language=language(),
        disclosure=DisclosureEvidence(evidence_ref='ev-disc', observations=(DisclosureObservation(segment_id='s2', visible=True),)),
    )
    values.update(changes)
    return OutputEvidence(**values)


class FakeProbe:
    def __init__(self, measurements: OutputMeasurements) -> None:
        self.measurements = measurements
        self.calls: list[str] = []

    def probe(self, output_ref: str) -> OutputMeasurements:
        self.calls.append(output_ref)
        return self.measurements


class FakeInspector:
    def __init__(self, value: OutputEvidence) -> None:
        self.evidence = value
        self.calls: list[tuple[str, str]] = []

    def inspect(self, output_ref: str, package) -> OutputEvidence:
        self.calls.append((output_ref, package.render_package_id))
        return self.evidence


class FlipGrants:
    """Answers from a fixed list; after the list is empty the grant is no longer current."""

    def __init__(self, *answers: bool) -> None:
        self.answers = list(answers)

    def is_grant_current(self, grant) -> bool:
        return self.answers.pop(0) if self.answers else False


def by_gate(report) -> dict:
    return {item.gate: item for item in report.gates}


class QcRig:
    def __init__(self, *, measurements=None, evidence_value=None, grants=None, fail_render: bool = False) -> None:
        self.rr = RenderRig()
        if fail_render:
            self.rr.renderer.fail_text = 'encoder rejected input'
        self.rr.render()
        self.uow = self.rr.uow
        self.package = self.rr.package
        self.probe = FakeProbe(measured() if measurements is None else measurements)
        self.inspector = FakeInspector(evidence() if evidence_value is None else evidence_value)
        self.pipeline = OutputPipeline(
            uow=self.uow, probe=self.probe, inspector=self.inspector, observer=self.rr.storage,
            grants=self.rr.base.grants if grants is None else grants,
        )

    def inspect_command(self, key: str = 'op-inspect-1', **changes) -> InspectOutputCommand:
        values = dict(
            grant=self.rr.base.grant, operation_key=key, render_package_id=self.package.render_package_id, render_attempt_id='attempt-1',
            policy=POLICY, expected_language=EXPECTED, word_timings=WORDS, segments=SEGMENTS, context=_context(),
        )
        values.update(changes)
        return InspectOutputCommand(**values)

    def inspect(self, key: str = 'op-inspect-1', **changes):
        return self.pipeline.inspect_output(self.inspect_command(key, **changes))

    def prepare(self, report_ref: str, key: str = 'op-ready-1', **changes):
        values = dict(
            grant=self.rr.base.grant, operation_key=key, render_package_id=self.package.render_package_id, render_attempt_id='attempt-1',
            quality_report_ref=report_ref, video_output_id='video-1', expected_sha256=CONTENT_SHA, context=_context(),
        )
        values.update(changes)
        return self.pipeline.prepare_output_ready(PrepareOutputReadyCommand(**values))

    def quality_events(self) -> list:
        return [record for record in self.uow.outbox.records() if record.event_type == 'OutputQualityChecked']


def test_passing_output_stores_report_receipt_trace_and_event_in_one_unit_of_work():
    rig = QcRig()
    commits = []
    original = rig.uow.commit

    def counting_commit():
        commits.append(1)
        original()

    rig.uow.commit = counting_commit
    outcome = rig.inspect()
    report, receipt = outcome.report, outcome.receipt
    assert outcome.replayed is False and report.passed is True and len(report.gates) == 13 and commits == [1]
    gates = by_gate(report)
    for name in (GateName.VISUAL_CONTINUITY, GateName.AUDIO_MIX_QUALITY):
        assert (gates[name].status, gates[name].reason) == (GateStatus.NOT_EVALUATED, 'INPUT_NOT_READY')
    assert rig.uow.renders.latest(KIND_QUALITY_REPORT, 'attempt-1').record == report
    assert rig.uow.receipts.get('ws-1', COMMAND_INSPECT, 'op-inspect-1') == receipt
    assert receipt.state is S.SUCCEEDED and receipt.report_id == report.report_id
    assert receipt.package_fingerprint == rig.package.package_fingerprint
    trace = rig.uow.traces.records()[-1]
    assert (trace.command, trace.outcome, trace.receipt_ref) == (COMMAND_INSPECT, 'qc_passed', receipt.receipt_ref)
    (event,) = rig.quality_events()
    assert event.aggregate_id == report.report_id and event.payload['passed'] is True and event.payload['blocking_gates'] == []
    assert set(event.payload) == {'quality_report_ref', 'render_attempt_id', 'output_artifact_ref', 'passed', 'blocking_gates', 'gate_statuses', 'policy_revision'}
    assert len(event.payload['gate_statuses']) == 13 and event.payload['quality_report_ref'] == report.report_id
    assert rig.probe.calls == [out_ref(1)] and len(rig.inspector.calls) == 1 and rig.uow.active is False


@pytest.mark.parametrize('table, method', [('outbox', 'append_event'), ('traces', 'append')])
def test_failure_inside_the_unit_of_work_rolls_back_report_receipt_trace_and_event(table, method):
    rig = QcRig()
    before = snapshot(rig.uow)

    def boom(*args):
        raise RuntimeError('store down')

    setattr(getattr(rig.uow, table), method, boom)
    with pytest.raises(RuntimeError):
        rig.inspect()
    assert snapshot(rig.uow) == before and rig.uow.active is False
    assert rig.uow.renders.latest(KIND_QUALITY_REPORT, 'attempt-1') is None


@pytest.mark.parametrize('port, method', [('probe', 'probe'), ('inspector', 'inspect')])
def test_port_failure_writes_nothing(port, method):
    rig = QcRig()
    before = snapshot(rig.uow)

    def boom(*args):
        raise RuntimeError('port down')

    setattr(getattr(rig, port), method, boom)
    with pytest.raises(RuntimeError):
        rig.inspect()
    assert snapshot(rig.uow) == before and rig.uow.active is False and rig.quality_events() == []


def test_fakes_satisfy_the_ports():
    rig = QcRig()
    assert isinstance(rig.probe, OutputProbePort) and isinstance(rig.rr.storage, OutputObservationPort) and callable(rig.inspector.inspect)


@pytest.mark.parametrize('duration, passed', [(60999, False), (61000, True), (70000, True), (70001, False)])
def test_duration_boundaries_are_inclusive_and_the_event_follows_the_verdict(duration, passed):
    rig = QcRig(measurements=measured(duration_ms=duration))
    report = rig.inspect().report
    gate = by_gate(report)[GateName.DURATION_RANGE]
    assert report.passed is passed and (gate.status is GateStatus.PASSED) is passed and gate.measured_value == duration
    (event,) = rig.quality_events()
    assert event.payload['passed'] is passed


FAILING = [
    ('thumbnail_outside_hook_range', {}, {'thumbnail': ThumbnailEvidence(evidence_ref='ev-thumb', time_ms=3500, asset_ref=THUMB_REF)}, GateName.THUMBNAIL_PRESENT, 'thumbnail_outside_hook_range'),
    ('subtitle_not_burned_in', {}, {'subtitle': None}, GateName.SUBTITLE_BURNED_IN, 'subtitle_not_observed'),
    ('karaoke_out_of_tolerance', {}, {'karaoke': karaoke((0, 5, 200))}, GateName.KARAOKE_TIMING_VALID, 'karaoke_timing_out_of_tolerance'),
    ('english_evidence_revision_mismatch', {}, {'language': language(output_metadata_revision='out-meta-v0')}, GateName.ENGLISH_OUTPUT_VALID, 'language_evidence_revision_mismatch'),
    ('horizontal_output', {'width': 1920, 'height': 1080}, {}, GateName.OUTPUT_PROFILE_VALID, 'profile_mismatch:width,height'),
    ('inference_disclosure_missing', {}, {'disclosure': None}, GateName.INFERENCE_DISCLOSURE_PRESENT, 'disclosure_not_observed'),
]


@pytest.mark.parametrize('name, changes, evidence_changes, gate_name, reason', FAILING, ids=[case[0] for case in FAILING])
def test_one_failing_hard_gate_fails_the_report_and_the_event_is_still_emitted(name, changes, evidence_changes, gate_name, reason):
    rig = QcRig(measurements=measured(**changes), evidence_value=evidence(**evidence_changes))
    outcome = rig.inspect()
    report = outcome.report
    gate = by_gate(report)[gate_name]
    assert report.passed is False and gate.status is GateStatus.FAILED and gate.reason.startswith(reason)
    assert report.blocking_gates == (gate_name,)
    assert outcome.receipt.state is S.SUCCEEDED and rig.uow.traces.records()[-1].outcome == 'qc_failed'
    (event,) = rig.quality_events()
    assert event.payload['passed'] is False and event.payload['blocking_gates'] == [gate_name.value]
    assert event.payload['gate_statuses'][gate_name.value] == 'failed'


def test_failed_warning_gate_is_recorded_and_never_blocks():
    warning = GateResult(gate=GateName.VISUAL_CONTINUITY, status=GateStatus.FAILED, threshold_revision='qc-policy-v1', reason='frame_gap_detected', measured_value=900)
    rig = QcRig()
    report = rig.inspect(policy=POLICY_WITH_WARNING, warning_results=(warning,)).report
    gates = by_gate(report)
    assert report.passed is True and report.blocking_gates == ()
    assert gates[GateName.VISUAL_CONTINUITY].status is GateStatus.FAILED and gates[GateName.AUDIO_MIX_QUALITY].status is GateStatus.NOT_EVALUATED
    with pytest.raises(ValueError):
        rig.inspect_command(warning_results=(GateResult(gate=GateName.FILE_PLAYABLE, status=GateStatus.PASSED),))


def test_inference_disclosure_is_not_applicable_without_inference_segments():
    rig = QcRig()
    report = rig.inspect(segments=(SEGMENTS[0],)).report
    gate = by_gate(report)[GateName.INFERENCE_DISCLOSURE_PRESENT]
    assert report.passed is True and gate.status is GateStatus.NOT_APPLICABLE


def test_same_operation_key_replays_without_ports_or_writes():
    rig = QcRig()
    first = rig.inspect()
    before = snapshot(rig.uow)
    again = rig.inspect()
    assert again.replayed is True and again.receipt == first.receipt and again.report == first.report
    assert rig.probe.calls == [out_ref(1)] and len(rig.inspector.calls) == 1 and snapshot(rig.uow) == before
    with pytest.raises(IdempotencyConflict) as caught:
        rig.inspect(policy=POLICY_WITH_WARNING)
    assert caught.value.problem.code == 'IDEMPOTENCY_CONFLICT' and snapshot(rig.uow) == before


def test_new_key_with_identical_content_reuses_the_stored_report_and_the_event():
    rig = QcRig()
    first = rig.inspect('op-1')
    second = rig.inspect('op-2')
    assert second.replayed is False and second.report == first.report and second.receipt.receipt_ref != first.receipt.receipt_ref
    assert len(rig.uow.renders.revisions(KIND_QUALITY_REPORT, 'attempt-1')) == 1 and len(rig.quality_events()) == 1
    assert len([item for item in rig.uow.receipts.records() if item.command == COMMAND_INSPECT]) == 2


def test_reinspection_with_another_result_adds_a_revision_and_a_second_event():
    rig = QcRig()
    first = rig.inspect('op-1').report
    rig.inspector.evidence = evidence(subtitle=None)
    second = rig.inspect('op-2').report
    revisions = rig.uow.renders.revisions(KIND_QUALITY_REPORT, 'attempt-1')
    assert [item.revision for item in revisions] == [1, 2] and [item.record for item in revisions] == [first, second]
    events = rig.quality_events()
    assert [event.payload['passed'] for event in events] == [True, False] and events[0].aggregate_id != events[1].aggregate_id


def test_stale_grant_is_refused_by_both_commands_without_ports_or_writes():
    rig = QcRig()
    ref = rig.inspect().report.report_id
    before = snapshot(rig.uow)
    rig.rr.base.grants.current.clear()
    with pytest.raises(StaleGrant) as caught:
        rig.inspect('op-inspect-new')
    assert caught.value.code == 'STALE_GRANT'
    with pytest.raises(StaleGrant):
        rig.prepare(ref, 'op-ready-new')
    with pytest.raises(StaleGrant):
        rig.inspect()
    assert snapshot(rig.uow) == before and rig.probe.calls == [out_ref(1)] and len(rig.inspector.calls) == 1


def test_unknown_attempt_package_report_and_package_mismatch_are_refused_without_writes():
    rig = QcRig()
    other = rig.rr.base.resolve('op-resolve-2', inputs=_inputs(output_profile_revision='out-prof-v2')).package
    before = snapshot(rig.uow)
    with pytest.raises(RenderAttemptNotFound):
        rig.inspect(render_attempt_id='missing')
    with pytest.raises(RenderPackageNotFound):
        rig.inspect(render_package_id='missing')
    with pytest.raises(AttemptPackageMismatch) as caught:
        rig.inspect(render_package_id=other.render_package_id)
    assert caught.value.code == 'attempt_package_mismatch'
    with pytest.raises(QualityReportNotFound):
        rig.prepare('0' * 64)
    assert snapshot(rig.uow) == before and rig.probe.calls == [] and rig.inspector.calls == []


def test_attempt_that_is_not_succeeded_is_not_inspectable():
    rig = QcRig(fail_render=True)
    before = snapshot(rig.uow)
    with pytest.raises(OutputNotInspectable) as caught:
        rig.inspect()
    assert caught.value.code == 'attempt_not_succeeded' and snapshot(rig.uow) == before
    assert rig.probe.calls == [] and rig.inspector.calls == []


def test_qc_pass_gives_video_output_but_not_completion_when_upload_is_not_verified():
    rig = QcRig()
    ref = rig.inspect().report.report_id
    files_before, operations_before = dict(rig.rr.storage.files), list(rig.rr.storage.operations)
    outcome = rig.prepare(ref)
    video = outcome.video_output
    assert outcome.ready is True and outcome.reasons == () and outcome.replayed is False
    assert video.video_output_id == 'video-1' and video.output_artifact_ref == out_ref(1) and video.output_sha256 == CONTENT_SHA
    assert video.quality_report_ref == ref and video.render_attempt_ref == 'attempt-1'
    assert video.package_fingerprint == rig.package.package_fingerprint and video.output_metadata_revision == rig.package.output_metadata_revision
    m = outcome.milestones
    assert (m.render_succeeded, m.qc_passed, m.upload_verified, m.completion_committed, m.completion_eligible) == (True, True, False, False, False)
    assert rig.rr.storage.files == files_before and rig.rr.storage.operations == operations_before == [('write', out_ref(1))]
    assert outcome.receipt.state is S.SUCCEEDED and rig.uow.traces.records()[-1].outcome == 'output_ready'
    assert [record.event_type for record in rig.uow.outbox.records()] == ['RenderCompleted', 'OutputQualityChecked']
    later = rig.prepare(ref, 'op-ready-2', upload_verified=True)
    assert later.ready is True and later.milestones.completion_eligible is True and later.milestones.completion_committed is False
    assert later.video_output == video and rig.rr.storage.operations == operations_before


def test_render_succeeded_but_qc_failed_creates_no_video_output():
    rig = QcRig(evidence_value=evidence(subtitle=None))
    report = rig.inspect().report
    outcome = rig.prepare(report.report_id, upload_verified=True)
    assert report.passed is False and outcome.ready is False and outcome.video_output is None and outcome.reasons == ('quality_not_passed',)
    m = outcome.milestones
    assert (m.render_succeeded, m.qc_passed, m.upload_verified, m.completion_committed, m.completion_eligible) == (True, False, True, False, False)
    assert rig.uow.traces.records()[-1].outcome == 'output_not_ready'


@pytest.mark.parametrize('expected, reasons', [('0' * 64, ('output_hash_mismatch',)), (None, ('expected_sha256_invalid',))])
def test_hash_not_matching_the_verified_source_is_not_ready(expected, reasons):
    rig = QcRig()
    outcome = rig.prepare(rig.inspect().report.report_id, expected_sha256=expected)
    assert outcome.ready is False and outcome.video_output is None and outcome.reasons == reasons
    assert outcome.milestones.qc_passed is True and outcome.milestones.completion_eligible is False


def test_missing_output_file_is_not_ready():
    rig = QcRig()
    ref = rig.inspect().report.report_id
    rig.rr.storage.files.pop(out_ref(1))
    outcome = rig.prepare(ref)
    assert outcome.ready is False and outcome.video_output is None and outcome.reasons == ('output_missing',)


def test_grant_that_stops_being_current_before_the_verdict_is_not_ready():
    rig = QcRig(grants=FlipGrants(True, True, False))
    outcome = rig.prepare(rig.inspect().report.report_id)
    assert outcome.ready is False and outcome.video_output is None and outcome.reasons == ('grant_invalid',)


def test_prepare_requires_the_current_report_of_the_attempt():
    rig = QcRig()
    good = rig.inspect('op-1').report
    rig.inspector.evidence = evidence(subtitle=None)
    bad = rig.inspect('op-2').report
    with pytest.raises(QualityReportNotFound) as caught:
        rig.prepare(good.report_id)
    assert caught.value.code == 'QUALITY_REPORT_NOT_FOUND'
    outcome = rig.prepare(bad.report_id)
    assert outcome.ready is False and 'quality_not_passed' in outcome.reasons


def test_prepare_replays_by_operation_key_and_conflicts_on_another_payload():
    rig = QcRig()
    ref = rig.inspect().report.report_id
    first = rig.prepare(ref)
    again = rig.prepare(ref)
    assert again.replayed is True and again.receipt == first.receipt and again.video_output == first.video_output
    before = snapshot(rig.uow)
    with pytest.raises(IdempotencyConflict):
        rig.prepare(ref, upload_verified=True)
    assert snapshot(rig.uow) == before


ALLOWED_IMPORTS = frozenset({
    '__future__', 'collections.abc', 'dataclasses', 'typing',
    'controlplane.application.idempotency.canonicalization', 'controlplane.domain.common.contracts', 'controlplane.domain.orchestration',
    'controlplane.domain.statemachine', 'render.application.package_pipeline', 'render.application.render_video',
    'render.domain.content_gates', 'render.domain.events', 'render.domain.output_ready', 'render.domain.package_contract',
    'render.domain.quality_report', 'render.domain.render_attempt', 'render.domain.technical_gates', 'render.ports.output_inspector',
    'render.ports.output_probe', 'render.ports.renderer', 'render.ports.repositories',
})
FORBIDDEN_WORDS = ('delete', 'remove', 'unlink', 'rmtree', 'rmdir', 'truncate')


def test_module_imports_only_f_and_controlplane_contracts():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module)
    assert names <= ALLOWED_IMPORTS


def test_module_has_no_delete_or_file_removal_api():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    assert [name for name in names if any(word in name.lower() for word in FORBIDDEN_WORDS)] == []


def test_test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert any(line.startswith('coveredIds:') for line in (doc or '').splitlines())
