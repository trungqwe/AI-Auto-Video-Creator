"""F-20: worker activity handler của F cho workflow G (CT-WF-003, CT-WF-006).

coveredIds: CT-WF-003, CT-WF-006, TST-WF-INV-003, TST-E2E-014 (phía F)
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import hashlib
import json
import pathlib

import pytest

from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.statemachine import OperationState
from render.adapters.fake_renderer import AFTER_SIDE_EFFECT, BEFORE_SIDE_EFFECT, FakeOutputStorage, FakeRenderer
from render.application.inspect_output import InspectOutputCommand, OutputPipeline, PrepareOutputReadyCommand
from render.application.package_pipeline import ResolveRenderPackageCommand, ValidateRenderPackageCommand
from render.application.render_video import InMemoryRenderUnitOfWork, ReconcileRenderCommand, RenderPipeline, RenderVideoCommand
from render.ports.renderer import RendererTimeout
from render.ports.repositories import KIND_ATTEMPT, KIND_PACKAGE, KIND_QUALITY_REPORT
from render.worker import activity_handler as ah
from render.worker.activity_handler import ActivityRequestError, RenderActivityDeps, handle_activity, validate_activity_request
from test_f17_resolve_validate_pipeline import Rig as PackageRig
from test_f17_resolve_validate_pipeline import _context, _grant, _inputs, _validation_context
from test_f18_render_video_pipeline import CANARY, CONTENT, SPEC, FakeLease, SpyProbe, out_ref, snapshot
from test_f19_inspect_output_pipeline import EXPECTED, POLICY, SEGMENTS, WORDS, FakeInspector, FakeProbe, evidence, measured

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'render' / 'worker' / 'activity_handler.py'
BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'g-activity-execution.json'
BINDING_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-activity-execution' / 'payloads.json'
NOW = datetime.datetime(2026, 10, 20, 8, 0, 0, tzinfo=datetime.timezone.utc)
SECRET = 'hunter2-SECRET'
RESOLVE, VALIDATE, RENDER, INSPECT = 'resolve_render_package', 'validate_render_package', 'render_video', 'inspect_output'
RECONCILE, PREPARE = 'reconcile_render', 'prepare_output_ready'
GRANT = _grant()
OLD_GENERATION = dataclasses.replace(GRANT, execution_generation=1)
OLD_EPOCH = dataclasses.replace(GRANT, recovery_epoch=0)
NEW_GENERATION = dataclasses.replace(GRANT, execution_generation=3)


class WorkerDied(BaseException):
    # a worker process that dies mid-render: not an Exception, so no handler of F can turn it into a result
    pass


class CountingGrants:
    # handler-level GrantCurrencyPort: counts the questions and answers like the grant port of the pipelines
    def __init__(self, inner) -> None:
        self.inner = inner
        self.calls = 0

    def is_grant_current(self, grant) -> bool:
        self.calls += 1
        return self.inner.is_grant_current(grant)


class FakeInputs:
    # test-only ActivityInputPort: builds the one F command of each activity from fixed fixtures and the input_refs
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.raises: Exception | None = None
        self.command_key: str | None = None
        self.command_grant: ExecutionGrant | None = None
        self.wrong_type = False
        self.resolve_inputs = None
        self.validation_context = _validation_context()
        self.orphan_after_seconds = None
        self.nothing_to_reconcile = False

    def resolve(self, activity_name, request, grant):
        self.calls.append(activity_name)
        if self.raises is not None:
            raise self.raises
        key = self.command_key or request['operation_key']
        owner = self.command_grant or grant
        refs = {ref['ref_type']: ref['ref_id'] for ref in request['input_refs']}
        context = _context()
        if activity_name == RESOLVE:
            inputs = _inputs() if self.resolve_inputs is None else self.resolve_inputs
            command = ResolveRenderPackageCommand(operation_key=key, grant=owner, inputs=inputs, context=context)
        elif activity_name == VALIDATE:
            command = ValidateRenderPackageCommand(
                operation_key=key, grant=owner, render_package_id=refs['render_package'],
                validation_context=self.validation_context, context=context,
            )
        elif activity_name == RENDER:
            command = RenderVideoCommand(
                grant=owner, render_package_id=refs['render_package'], render_attempt_id=key, output_artifact_ref=out_ref(1),
                receipt_ref=f'receipt-{key}', command_spec=SPEC, context=context, secret_values=(CANARY,),
            )
        elif activity_name == INSPECT:
            command = InspectOutputCommand(
                grant=owner, operation_key=key, render_package_id=refs['render_package'], render_attempt_id=refs['render_attempt'],
                policy=POLICY, expected_language=EXPECTED, word_timings=WORDS, segments=SEGMENTS, context=context,
            )
        elif activity_name == RECONCILE:
            if self.nothing_to_reconcile:
                return {'nothing_to_reconcile': True}
            command = ReconcileRenderCommand(
                grant=owner, render_attempt_id=refs['render_attempt'], context=context,
                expected_sha256=hashlib.sha256(CONTENT).hexdigest(), orphan_after_seconds=self.orphan_after_seconds,
            )
        elif activity_name == PREPARE:
            command = PrepareOutputReadyCommand(
                grant=owner, operation_key=key, render_package_id=refs['render_package'], render_attempt_id=refs['render_attempt'],
                quality_report_ref=refs['quality_report'], video_output_id=f'video-output-{key}',
                expected_sha256=hashlib.sha256(CONTENT).hexdigest(), context=context,
            )
        else:
            raise KeyError(activity_name)
        return {'command': 'not-a-command' if self.wrong_type else command}


class ActivityRig:
    def __init__(self, *, slots: int = 2, extra_grants: tuple[ExecutionGrant, ...] = ()) -> None:
        self.uow = InMemoryRenderUnitOfWork()
        self.base = PackageRig(self.uow)
        self.base.grants.current.update(extra_grants)
        self.storage = FakeOutputStorage()
        self.renderer = FakeRenderer(self.storage, output_ref=out_ref(1), content=CONTENT)
        self.lease = FakeLease(slots)
        self.qc_probe = FakeProbe(measured())
        self.inspector = FakeInspector(evidence())
        render = RenderPipeline(
            uow=self.uow, renderer=self.renderer, lease=self.lease, probe=SpyProbe(self.storage), observer=self.storage,
            grants=self.base.grants,
        )
        output = OutputPipeline(
            uow=self.uow, probe=self.qc_probe, inspector=self.inspector, observer=self.storage, grants=self.base.grants,
        )
        self.grants = CountingGrants(self.base.grants)
        self.inputs = FakeInputs()
        self.deps = RenderActivityDeps(
            package=self.base.pipeline, render=render, output=output, grants=self.grants, inputs=self.inputs, clock=lambda: NOW,
        )


def request_of(activity: str = RESOLVE, operation_key: str = 'op-key-1', refs=None, **extra) -> dict:
    request = {
        'workflow_id': 'wf-1',
        'workflow_run_id': 'wfr-1',
        'stage_run_id': 'stage-1',
        'activity_name': activity,
        'activity_version': '1',
        'input_refs': [{'ref_type': 'production_plan', 'ref_id': 'plan-1'}] if refs is None else refs,
        'operation_key': operation_key,
        'capability_requirements': {'tool': 'ffmpeg'},
        'retry_policy_ref': 'retry-r1',
    }
    return {**request, **extra}


def run(rig: ActivityRig, activity: str, key: str = 'op-key-1', refs=None, grant: ExecutionGrant = GRANT, **extra) -> dict:
    return handle_activity(request_of(activity, key, refs, **extra), grant, rig.deps)


def pkg_ref(package_id: str) -> dict:
    return {'ref_type': 'render_package', 'ref_id': package_id}


def attempt_ref(attempt_id: str) -> dict:
    return {'ref_type': 'render_attempt', 'ref_id': attempt_id}


def assert_render_attempt_and_output_refs(refs: list, attempt_id: str = 'op-render-1') -> None:
    # PW-F4-FIX1 adds a verified sha256 to the render_output ref; a ref without it still passes (code before and after FIX1)
    assert isinstance(refs, list) and len(refs) == 2
    attempt, output = refs
    assert attempt == {'ref_type': 'render_attempt', 'ref_id': attempt_id}
    assert {key: value for key, value in output.items() if key != 'sha256'} == {'ref_type': 'render_output', 'ref_id': out_ref(1)}
    if 'sha256' in output:
        digest = output['sha256']
        assert isinstance(digest, str) and len(digest) == 64 and set(digest) <= set('0123456789abcdef')


def prepared(rig: ActivityRig) -> str:
    package_id = run(rig, RESOLVE, 'op-resolve-1')['output_refs'][0]['ref_id']
    assert run(rig, VALIDATE, 'op-validate-1', [pkg_ref(package_id)])['disposition'] == 'succeeded'
    return package_id


def rendered(rig: ActivityRig) -> tuple[str, str]:
    package_id = prepared(rig)
    assert run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])['disposition'] == 'succeeded'
    return package_id, 'op-render-1'


def test_resolve_activity_returns_a_succeeded_result_with_the_package_ref():
    rig = ActivityRig()
    result = run(rig, RESOLVE)
    package = rig.uow.renders.latest(KIND_PACKAGE, result['output_refs'][0]['ref_id']).record
    receipt = rig.uow.receipts.get('ws-1', 'ResolveRenderPackage', 'op-key-1')
    assert result == {
        'stage_run_id': 'stage-1', 'grant_id': 'op-grant-1', 'execution_generation': 2, 'recovery_epoch': '1',
        'disposition': 'succeeded', 'output_refs': [{'ref_type': 'render_package', 'ref_id': package.render_package_id}],
        'completed_at': '2026-10-20T08:00:00Z',
        'metrics': {'input_artifact_count': len(package.input_artifacts), 'replayed': False}, 'warnings': [],
        'operation_receipt_ref': receipt.receipt_ref,
    }
    assert rig.inputs.calls == [RESOLVE] and rig.renderer.calls == 0


def test_validate_activity_succeeds_on_a_passing_report():
    rig = ActivityRig()
    package_id = run(rig, RESOLVE, 'op-resolve-1')['output_refs'][0]['ref_id']
    result = run(rig, VALIDATE, 'op-validate-1', [pkg_ref(package_id)])
    package = rig.uow.renders.latest(KIND_PACKAGE, package_id).record
    report = rig.uow.reports.latest(package.package_fingerprint)
    assert result['disposition'] == 'succeeded' and report.passed is True and 'problem' not in result
    assert result['output_refs'] == [{'ref_type': 'package_validation_report', 'ref_id': report.report_id}]
    assert result['metrics'] == {'finding_count': 0, 'replayed': False}
    assert result['operation_receipt_ref'] == rig.uow.receipts.get('ws-1', 'ValidateRenderPackage', 'op-validate-1').receipt_ref
    assert rig.renderer.calls == 0 and rig.lease.acquired == []


def test_a_failed_validation_report_is_a_stored_failed_result_and_blocks_the_render():
    rig = ActivityRig()
    rig.inputs.validation_context = _validation_context(voice=None)
    package_id = run(rig, RESOLVE, 'op-resolve-1')['output_refs'][0]['ref_id']
    result = run(rig, VALIDATE, 'op-validate-1', [pkg_ref(package_id)])
    package = rig.uow.renders.latest(KIND_PACKAGE, package_id).record
    report = rig.uow.reports.latest(package.package_fingerprint)
    problem = result['problem']
    assert result['disposition'] == 'failed' and report.passed is False and len(report.findings) >= 1
    assert result['output_refs'] == [{'ref_type': 'package_validation_report', 'ref_id': report.report_id}]
    assert result['metrics']['finding_count'] == len(report.findings)
    assert (problem['code'], problem['category'], problem['retryable']) == ('package_validation_failed', 'validation', False)
    blocked = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    assert blocked['disposition'] == 'failed' and blocked['problem']['code'] == 'package_not_validated'
    assert rig.renderer.calls == 0 and rig.lease.acquired == []


def test_render_activity_runs_only_the_render_and_never_the_inspection():
    rig = ActivityRig()
    package_id = prepared(rig)
    result = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    assert result['disposition'] == 'succeeded' and 'problem' not in result
    assert (result['stage_run_id'], result['grant_id']) == ('stage-1', 'op-grant-1')
    assert (result['execution_generation'], result['recovery_epoch']) == (2, '1')
    assert result['completed_at'] == '2026-10-20T08:00:00Z'
    assert_render_attempt_and_output_refs(result['output_refs'])
    assert result['metrics'] == {'wall_time_ms': 1200, 'peak_disk_bytes': 4096, 'replayed': False}
    assert result['warnings'] == [] and result['operation_receipt_ref'] == 'receipt-op-render-1'
    assert rig.renderer.calls == 1 and rig.lease.held == [] and len(rig.lease.released) == 1
    assert [record.event_type for record in rig.uow.outbox.records()] == ['RenderCompleted']
    assert rig.qc_probe.calls == [] and rig.inspector.calls == []
    assert rig.uow.renders.latest(KIND_QUALITY_REPORT, 'op-render-1') is None


def test_a_finished_stage_never_starts_the_next_stage():
    rig = ActivityRig()
    package_id = run(rig, RESOLVE, 'op-resolve-1')['output_refs'][0]['ref_id']
    assert rig.uow.reports._rows == {} and rig.inputs.calls == [RESOLVE]
    run(rig, VALIDATE, 'op-validate-1', [pkg_ref(package_id)])
    assert rig.renderer.calls == 0 and rig.uow.attempt_index._rows == {} and rig.lease.acquired == []
    run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    assert rig.inputs.calls == [RESOLVE, VALIDATE, RENDER]
    assert rig.qc_probe.calls == [] and rig.inspector.calls == []
    assert rig.uow.renders.latest(KIND_QUALITY_REPORT, 'op-render-1') is None


def test_desktop_and_gpu_capability_are_never_waited_for_by_f():
    rig = ActivityRig()
    result = run(rig, RESOLVE, capability_requirements={'desktop': 'required', 'gpu': 'required'})
    assert result['disposition'] == 'succeeded' and 'problem' not in result


def test_a_full_gpu_pool_gives_a_retryable_capacity_problem_without_waiting():
    rig = ActivityRig(slots=0)
    package_id = prepared(rig)
    before = snapshot(rig.uow)
    result = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    problem = result['problem']
    assert result['disposition'] == 'failed' and result['output_refs'] == []
    assert (problem['code'], problem['category'], problem['retryable']) == ('gpu_lease_unavailable', 'capacity', True)
    assert rig.renderer.calls == 0 and snapshot(rig.uow) == before


@pytest.mark.parametrize('stale', [OLD_GENERATION, OLD_EPOCH], ids=['old_generation', 'old_recovery_epoch'])
def test_stale_grant_is_rejected_before_any_input_lookup_or_commit(stale):  # TST-WF-INV-003
    rig = ActivityRig()
    before = snapshot(rig.uow)
    result = run(rig, RENDER, 'op-key-1', [pkg_ref('package-1')], stale)
    problem = result['problem']
    assert result['disposition'] == 'stale' and result['output_refs'] == []
    assert (problem['code'], problem['category'], problem['retryable']) == ('STALE_GRANT', 'conflict', False)
    assert (result['execution_generation'], result['recovery_epoch']) == (stale.execution_generation, str(stale.recovery_epoch))
    assert rig.inputs.calls == [] and rig.renderer.calls == 0 and rig.lease.acquired == [] and snapshot(rig.uow) == before
    assert rig.deps.results.get('ws-1', 'op-key-1') is None


def test_stale_grant_cannot_write_a_new_attempt_after_a_current_one_committed():  # TST-WF-INV-003
    rig = ActivityRig()
    package_id, _ = rendered(rig)
    before = snapshot(rig.uow)
    result = run(rig, RENDER, 'op-render-2', [pkg_ref(package_id)], OLD_GENERATION)
    assert result['disposition'] == 'stale'
    assert rig.uow.renders.latest(KIND_ATTEMPT, 'op-render-2') is None
    assert snapshot(rig.uow) == before and rig.renderer.calls == 1 and len(rig.lease.acquired) == 1


def test_stale_grant_does_not_receive_the_stored_result_of_a_newer_generation():  # TST-WF-INV-003
    rig = ActivityRig()
    run(rig, RESOLVE)
    result = run(rig, RESOLVE, grant=OLD_GENERATION)
    assert result['disposition'] == 'stale' and result['output_refs'] == []


def test_same_operation_key_returns_the_stored_result_without_running_again():
    rig = ActivityRig()
    package_id = prepared(rig)
    first = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    second = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    assert second == first and first['metrics']['replayed'] is False
    assert rig.renderer.calls == 1 and len(rig.lease.acquired) == 1 and len(rig.uow.outbox.records()) == 1
    assert rig.inputs.calls.count(RENDER) == 1
    second['metrics']['replayed'] = True
    assert run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)]) == first


def test_same_operation_key_under_a_newer_current_generation_keeps_outputs_and_takes_the_new_identity():
    rig = ActivityRig(extra_grants=(NEW_GENERATION,))
    package_id = prepared(rig)
    first = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    second = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)], NEW_GENERATION)
    assert (first['execution_generation'], second['execution_generation']) == (2, 3)
    assert second['disposition'] == 'succeeded' and second['output_refs'] == first['output_refs']
    assert rig.renderer.calls == 1


def test_same_operation_key_for_a_different_activity_is_a_conflict():
    rig = ActivityRig()
    first = run(rig, RESOLVE, 'op-key-1')
    package_id = first['output_refs'][0]['ref_id']
    before = snapshot(rig.uow)
    conflict = run(rig, VALIDATE, 'op-key-1', [pkg_ref(package_id)])
    assert conflict['disposition'] == 'failed' and conflict['problem']['code'] == 'OPERATION_KEY_CONFLICT'
    assert conflict['output_refs'] == [] and snapshot(rig.uow) == before
    assert run(rig, RESOLVE, 'op-key-1') == first


def test_a_pipeline_idempotency_conflict_is_a_failed_result_with_its_code():
    rig = ActivityRig()
    rig.inputs.validation_context = _validation_context(voice=None)
    package_id = run(rig, RESOLVE, 'op-resolve-1')['output_refs'][0]['ref_id']
    assert run(rig, VALIDATE, 'op-validate-1', [pkg_ref(package_id)])['disposition'] == 'failed'
    rig.inputs.validation_context = _validation_context()
    before = snapshot(rig.uow)
    result = run(rig, VALIDATE, 'op-validate-1', [pkg_ref(package_id)])
    problem = result['problem']
    assert result['disposition'] == 'failed'
    assert (problem['code'], problem['category'], problem['retryable']) == ('IDEMPOTENCY_CONFLICT', 'conflict', False)
    assert snapshot(rig.uow) == before


@pytest.mark.parametrize('name', ['bogus_activity', 'RenderVideo'])
def test_unknown_activity_name_returns_a_structured_problem_without_running_anything(name):
    rig = ActivityRig()
    before = snapshot(rig.uow)
    result = run(rig, name)
    problem = result['problem']
    assert result['disposition'] == 'failed' and result['output_refs'] == []
    assert (problem['code'], problem['retryable'], problem['category']) == ('UNKNOWN_ACTIVITY', False, 'validation')
    assert problem['correlation_id'] == 'wfr-1' and problem['instance'] == 'urn:stage-run:stage-1'
    assert rig.inputs.calls == [] and snapshot(rig.uow) == before and rig.renderer.calls == 0
    assert rig.deps.results.get('ws-1', 'op-key-1') is None


def test_supported_activity_names_are_the_six_f_commands():
    assert ah.ACTIVITY_NAMES == ('resolve_render_package', 'validate_render_package', 'reconcile_render', 'render_video', 'inspect_output', 'prepare_output_ready')


@pytest.mark.parametrize('activity', [RESOLVE, VALIDATE, RENDER, INSPECT])
def test_operation_key_inside_the_command_must_match_the_request(activity):
    rig = ActivityRig()
    package_id, attempt_id = rendered(rig)
    rig.inputs.command_key = 'op-other'
    before, calls = snapshot(rig.uow), rig.renderer.calls
    result = run(rig, activity, 'op-key-9', [pkg_ref(package_id), attempt_ref(attempt_id)])
    problem = result['problem']
    assert result['disposition'] == 'failed'
    assert (problem['code'], problem['retryable'], problem['category']) == ('OPERATION_KEY_MISMATCH', False, 'validation')
    assert snapshot(rig.uow) == before and rig.renderer.calls == calls


@pytest.mark.parametrize(
    ('field_name', 'value', 'code'),
    [('command_grant', dataclasses.replace(GRANT, execution_generation=9), 'GRANT_MISMATCH'), ('wrong_type', True, 'COMMAND_TYPE_MISMATCH')],
)
def test_a_command_that_does_not_belong_to_the_request_is_rejected_before_it_runs(field_name, value, code):
    rig = ActivityRig()
    package_id = prepared(rig)
    before = snapshot(rig.uow)
    setattr(rig.inputs, field_name, value)
    result = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    assert result['disposition'] == 'failed' and result['problem']['code'] == code and result['problem']['retryable'] is False
    assert rig.renderer.calls == 0 and snapshot(rig.uow) == before


def test_a_resolve_error_is_a_failed_result_with_its_code_and_nothing_committed():
    rig = ActivityRig()
    rig.inputs.resolve_inputs = _inputs(output_path_ref=None)
    before = snapshot(rig.uow)
    result = run(rig, RESOLVE)
    problem = result['problem']
    assert result['disposition'] == 'failed'
    assert (problem['code'], problem['category'], problem['retryable']) == ('missing_required', 'validation', False)
    assert snapshot(rig.uow) == before and rig.deps.results.get('ws-1', 'op-key-1') is None


def test_an_unknown_package_is_a_failed_result_with_its_code():
    rig = ActivityRig()
    result = run(rig, VALIDATE, 'op-validate-1', [pkg_ref('missing-package')])
    assert result['disposition'] == 'failed' and result['problem']['code'] == 'RENDER_PACKAGE_NOT_FOUND'


def test_a_renderer_crash_is_a_failed_result_without_output_and_without_the_secret():
    rig = ActivityRig()
    package_id = prepared(rig)
    rig.renderer.inject(BEFORE_SIDE_EFFECT, RuntimeError(f'ffmpeg crashed {CANARY} token={CANARY} at C:/secret/dir/x.mp4'))
    result = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    problem = result['problem']
    assert result['disposition'] == 'failed' and result['output_refs'] == [{'ref_type': 'render_attempt', 'ref_id': 'op-render-1'}]
    assert (problem['code'], problem['category'], problem['retryable']) == ('render_attempt_failed', 'dependency', True)
    text = repr(result)
    assert CANARY not in text and 'C:/secret' not in text and 'ffmpeg crashed' not in text
    assert rig.uow.outbox.records() == () and rig.lease.held == []
    again = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    assert again['disposition'] == 'failed' and again['metrics']['replayed'] is True and rig.renderer.calls == 1


def test_a_renderer_timeout_is_outcome_unknown_and_a_new_attempt_needs_a_reconcile_first():
    rig = ActivityRig()
    package_id = prepared(rig)
    rig.renderer.inject(AFTER_SIDE_EFFECT, RendererTimeout('render timed out'))
    result = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    problem = result['problem']
    assert result['disposition'] == 'outcome_unknown' and result['output_refs'] == [{'ref_type': 'render_attempt', 'ref_id': 'op-render-1'}]
    assert (problem['code'], problem['retryable']) == ('render_outcome_unknown', False)
    again = run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    assert again['disposition'] == 'outcome_unknown' and rig.renderer.calls == 1
    other = run(rig, RENDER, 'op-render-2', [pkg_ref(package_id)])
    assert other['disposition'] == 'failed' and other['problem']['code'] == 'reconcile_required' and rig.renderer.calls == 1


def test_inspect_activity_returns_the_quality_report_and_the_warning_gates():
    rig = ActivityRig()
    package_id, attempt_id = rendered(rig)
    result = run(rig, INSPECT, 'op-inspect-1', [pkg_ref(package_id), attempt_ref(attempt_id)])
    report = rig.uow.renders.latest(KIND_QUALITY_REPORT, attempt_id).record
    assert result['disposition'] == 'succeeded' and report.passed is True and 'problem' not in result
    assert result['output_refs'] == [{'ref_type': 'quality_report', 'ref_id': report.report_id}]
    assert result['metrics'] == {'gate_count': 13, 'blocking_gate_count': 0, 'blocking_gates': [], 'replayed': False}
    assert result['warnings'] == ['VISUAL_CONTINUITY:not_evaluated', 'AUDIO_MIX_QUALITY:not_evaluated']
    assert result['operation_receipt_ref'] == rig.uow.receipts.get('ws-1', 'InspectOutput', 'op-inspect-1').receipt_ref
    assert [record.event_type for record in rig.uow.outbox.records()].count('OutputQualityChecked') == 1


def test_a_failed_quality_report_is_a_failed_result_with_the_blocking_gates():
    rig = ActivityRig()
    package_id, attempt_id = rendered(rig)
    rig.qc_probe.measurements = measured(duration_ms=60999)
    result = run(rig, INSPECT, 'op-inspect-1', [pkg_ref(package_id), attempt_ref(attempt_id)])
    report = rig.uow.renders.latest(KIND_QUALITY_REPORT, attempt_id).record
    problem = result['problem']
    assert result['disposition'] == 'failed' and report.passed is False
    assert result['output_refs'] == [{'ref_type': 'quality_report', 'ref_id': report.report_id}]
    assert result['metrics']['blocking_gates'] == ['DURATION_RANGE'] and result['metrics']['blocking_gate_count'] == 1
    assert (problem['code'], problem['category'], problem['retryable']) == ('quality_gates_failed', 'validation', False)


def test_reconcile_activity_settles_an_unknown_attempt_with_its_output():
    rig = ActivityRig()
    package_id = prepared(rig)
    rig.renderer.inject(AFTER_SIDE_EFFECT, RendererTimeout('t'))
    run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    result = run(rig, RECONCILE, 'op-reconcile-1', [pkg_ref(package_id), attempt_ref('op-render-1')])
    assert result['disposition'] == 'succeeded'
    assert_render_attempt_and_output_refs(result['output_refs'])
    assert result['metrics']['reconciled_state'] == 'succeeded'
    attempt = rig.uow.renders.latest(KIND_ATTEMPT, 'op-render-1').record
    assert attempt.receipt_state is OperationState.SUCCEEDED
    assert [record.event_type for record in rig.uow.outbox.records()].count('RenderCompleted') == 1


def test_reconcile_activity_of_a_missing_output_is_a_definite_failed_attempt():
    rig = ActivityRig()
    package_id = prepared(rig)
    rig.renderer.inject(BEFORE_SIDE_EFFECT, RendererTimeout('t'))
    run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    result = run(rig, RECONCILE, 'op-reconcile-1', [pkg_ref(package_id), attempt_ref('op-render-1')])
    assert result['disposition'] == 'succeeded'
    assert result['output_refs'] == [{'ref_type': 'render_attempt', 'ref_id': 'op-render-1'}]
    assert result['metrics']['reconciled_state'] == 'failed'
    attempt = rig.uow.renders.latest(KIND_ATTEMPT, 'op-render-1').record
    assert attempt.receipt_state is OperationState.FAILED
    assert [record.event_type for record in rig.uow.outbox.records()].count('RenderCompleted') == 0


def test_reconcile_activity_gives_a_definite_result_for_an_orphaned_started_attempt():
    rig = ActivityRig()
    package_id = prepared(rig)
    rig.renderer.inject(BEFORE_SIDE_EFFECT, WorkerDied())
    with pytest.raises(WorkerDied):
        run(rig, RENDER, 'op-render-1', [pkg_ref(package_id)])
    attempt = rig.uow.renders.latest(KIND_ATTEMPT, 'op-render-1').record
    assert attempt.receipt_state is OperationState.STARTED
    assert rig.lease.held == []
    rig.inputs.orphan_after_seconds = 3600
    failed_reconcile = run(rig, RECONCILE, 'op-reconcile-1', [pkg_ref(package_id), attempt_ref('op-render-1')])
    assert failed_reconcile['disposition'] == 'failed'
    assert failed_reconcile['problem']['code'] == 'attempt_in_progress'
    attempt = rig.uow.renders.latest(KIND_ATTEMPT, 'op-render-1').record
    assert attempt.receipt_state is OperationState.STARTED
    rig.inputs.orphan_after_seconds = 0
    ok_reconcile = run(rig, RECONCILE, 'op-reconcile-1', [pkg_ref(package_id), attempt_ref('op-render-1')])
    assert ok_reconcile['disposition'] == 'succeeded'
    assert ok_reconcile['metrics']['reconciled_state'] == 'failed'
    attempt = rig.uow.renders.latest(KIND_ATTEMPT, 'op-render-1').record
    assert attempt.receipt_state is OperationState.FAILED
    assert attempt.error in ('output_missing', 'reconcile_output_missing')


def test_reconcile_activity_without_an_open_attempt_is_a_no_op_success():
    rig = ActivityRig()
    rig.inputs.nothing_to_reconcile = True
    result = run(rig, RECONCILE)
    assert result['disposition'] == 'succeeded'
    assert result['output_refs'] == []
    assert result['metrics'] == {'reconciled_state': 'none'}


def test_prepare_activity_returns_the_video_output_after_a_passing_qc():
    rig = ActivityRig()
    package_id, attempt_id = rendered(rig)
    inspect_result = run(rig, INSPECT, 'op-inspect-1', [pkg_ref(package_id), attempt_ref(attempt_id)])
    report_id = inspect_result['output_refs'][0]['ref_id']
    result = run(rig, PREPARE, 'op-prepare-1', [pkg_ref(package_id), attempt_ref(attempt_id), {'ref_type': 'quality_report', 'ref_id': report_id}])
    assert result['disposition'] == 'succeeded'
    assert result['output_refs'] == [
        {'ref_type': 'video_output', 'ref_id': 'video-output-op-prepare-1'},
        {'ref_type': 'quality_report', 'ref_id': report_id},
    ]
    assert result['metrics']['ready'] is True
    assert run(rig, PREPARE, 'op-prepare-1', [pkg_ref(package_id), attempt_ref(attempt_id), {'ref_type': 'quality_report', 'ref_id': report_id}]) == result


def test_prepare_activity_after_a_failed_qc_is_not_ready():
    rig = ActivityRig()
    package_id, attempt_id = rendered(rig)
    rig.qc_probe.measurements = measured(duration_ms=60999)
    inspect_result = run(rig, INSPECT, 'op-inspect-1', [pkg_ref(package_id), attempt_ref(attempt_id)])
    report_id = inspect_result['output_refs'][0]['ref_id']
    result = run(rig, PREPARE, 'op-prepare-1', [pkg_ref(package_id), attempt_ref(attempt_id), {'ref_type': 'quality_report', 'ref_id': report_id}])
    assert result['disposition'] == 'failed'
    assert result['problem']['code'] == 'output_not_ready'
    assert result['output_refs'] == [{'ref_type': 'quality_report', 'ref_id': report_id}]


def test_unexpected_exceptions_become_redacted_failed_results():
    class LeakyCode(Exception):
        code = f'token={SECRET}'

    for error in (RuntimeError(f'db password={SECRET} lost'), LeakyCode(f'Bearer {SECRET}')):
        rig = ActivityRig()
        rig.inputs.raises = error
        before = snapshot(rig.uow)
        result = run(rig, RESOLVE)
        assert result['disposition'] == 'failed'
        assert (result['problem']['code'], result['problem']['retryable']) == ('ACTIVITY_ABORTED', True)
        assert SECRET not in repr(result)
        assert rig.deps.results.get('ws-1', 'op-key-1') is None and snapshot(rig.uow) == before


INVALID_REQUESTS = (
    ('missing_operation_key', lambda r: r.pop('operation_key'), ('missing_required', 'operation_key')),
    ('secret_in_payload', lambda r: r.update(secret_value=SECRET), ('forbidden_field', 'secret_value')),
    ('raw_blob_in_payload', lambda r: r.update(raw_blob='x'), ('forbidden_field', 'raw_blob')),
    ('blank_activity_name', lambda r: r.update(activity_name=' '), ('invalid_value', 'activity_name')),
    ('empty_input_refs', lambda r: r.update(input_refs=[]), ('invalid_value', 'input_refs')),
    ('input_ref_without_id', lambda r: r.update(input_refs=[{'ref_type': 'render_package'}]), ('invalid_value', 'input_refs')),
    ('input_refs_as_string', lambda r: r.update(input_refs='ref-1'), ('wrong_type', 'input_refs')),
    ('other_stage_run', lambda r: r.update(stage_run_id='stage-2'), ('invalid_value', 'execution_grant.stage_run_id')),
)
INVALID_GRANTS = (
    ('not_an_execution_grant', {'workspace_id': 'ws-1'}, ('wrong_type', 'execution_grant')),
    ('negative_generation', dataclasses.replace(GRANT, execution_generation=-1), ('invalid_value', 'execution_grant.execution_generation')),
    ('blank_workspace', dataclasses.replace(GRANT, workspace_id=' '), ('invalid_value', 'execution_grant.workspace_id')),
)


@pytest.mark.parametrize(('mutate', 'issue'), [case[1:] for case in INVALID_REQUESTS], ids=[case[0] for case in INVALID_REQUESTS])
def test_invalid_request_raises_before_any_grant_check_lookup_or_write(mutate, issue):
    rig = ActivityRig()
    request = request_of()
    mutate(request)
    before = snapshot(rig.uow)
    with pytest.raises(ActivityRequestError) as raised:
        handle_activity(request, GRANT, rig.deps)
    assert raised.value.code == 'VALIDATION_ERROR' and issue in raised.value.issues
    assert SECRET not in repr(raised.value)
    assert (rig.grants.calls, rig.inputs.calls) == (0, []) and snapshot(rig.uow) == before and rig.renderer.calls == 0


@pytest.mark.parametrize(('grant', 'issue'), [case[1:] for case in INVALID_GRANTS], ids=[case[0] for case in INVALID_GRANTS])
def test_invalid_grant_raises_validation_error_before_any_grant_check(grant, issue):
    rig = ActivityRig()
    with pytest.raises(ActivityRequestError) as raised:
        handle_activity(request_of(), grant, rig.deps)
    assert raised.value.code == 'VALIDATION_ERROR' and issue in raised.value.issues
    assert (rig.grants.calls, rig.inputs.calls) == (0, [])


def test_results_carry_every_required_binding_field_and_a_contract_disposition():
    binding = json.loads(BINDING.read_text(encoding='utf-8'))
    entity = next(item for item in binding['entities'] if item['name'] == 'ActivityResult')
    required = {item['name'] for item in entity['fields'] if item['required']}
    dispositions = next(item for item in entity['fields'] if item['name'] == 'disposition')['enum']
    results = [run(ActivityRig(), RESOLVE), run(ActivityRig(), RESOLVE, grant=OLD_EPOCH), run(ActivityRig(), 'bogus_activity')]
    for result in results:
        assert required <= set(result)
        assert result['disposition'] in dispositions
        assert type(result['execution_generation']) is int and isinstance(result['recovery_epoch'], str)
        assert isinstance(result['output_refs'], list)


def test_binding_fixture_requests_are_valid_and_invalid_cases_report_their_expected_error():
    entity = json.loads(BINDING_FIXTURE.read_text(encoding='utf-8'))['entities']['ActivityRequest']
    valid = entity['valid'][0]
    grant = dataclasses.replace(GRANT, stage_run_id=valid['stage_run_id'])
    assert validate_activity_request(valid, grant) == []
    for case in entity['invalid']:
        expected = (case['expected_error']['code'], case['expected_error']['field'])
        assert expected in validate_activity_request(case['payload'], grant), case['case']


def imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_handler_imports_no_temporalio_ui_api_creative_voice_or_catalog_code():
    banned_parts = {'temporalio', 'creative', 'voice', 'catalog'}
    banned = sorted(
        name
        for name in imported_modules(MODULE_PATH)
        if banned_parts & set(name.split('.')) or name.startswith(('controlplane.ui', 'controlplane.api'))
    )
    assert banned == []


def test_handler_imports_only_stdlib_controlplane_domain_and_render_layers():
    stdlib = {'__future__', 'copy', 'datetime', 're', 'collections.abc', 'dataclasses', 'types', 'typing'}
    allowed = ('controlplane.domain', 'render.application', 'render.domain')
    unexpected = sorted(name for name in imported_modules(MODULE_PATH) if name not in stdlib and not name.startswith(allowed))
    assert unexpected == []


def test_handler_never_waits_sleeps_or_opens_io():
    waiting = {'time', 'asyncio', 'threading', 'sched', 'subprocess', 'socket', 'os'}
    assert sorted(name for name in imported_modules(MODULE_PATH) if name.split('.')[0] in waiting) == []


def test_handler_registers_no_workflow_or_activity_through_decorators():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    assert [node.name for node in ast.walk(tree) if isinstance(node, functions) and node.decorator_list] == []


def test_handler_uses_the_controlplane_execution_grant_and_defines_no_grant_class():
    assert ah.ExecutionGrant is ExecutionGrant
    defined = [name for name, value in vars(ah).items() if isinstance(value, type) and value.__module__ == ah.__name__]
    assert [name for name in defined if name.endswith('Grant')] == []


def test_handler_never_reads_the_secret_values_of_a_command():
    assert 'secret_values' not in MODULE_PATH.read_text(encoding='utf-8')


def test_module_docstring_lists_the_covered_ids():
    docstring = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-WF-003, CT-WF-006, TST-WF-INV-003, TST-E2E-014' in docstring
