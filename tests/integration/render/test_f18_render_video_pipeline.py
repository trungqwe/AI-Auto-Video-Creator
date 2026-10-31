"""F-18: integration RenderVideo, lease GPU và ReconcileRender trong tiến trình (CT-RND-004, CT-STATE-011).

coveredIds: CT-RND-004, CT-STATE-011, TST-SEC-INV-012, TST-E2E-001 (đoạn render), TST-CTR-INV-001
"""
from __future__ import annotations

import ast
import hashlib
import pathlib

import pytest

from controlplane.domain.statemachine import OperationState
from render.adapters.fake_renderer import (
    AFTER_SIDE_EFFECT, BEFORE_SIDE_EFFECT, DURING_SIDE_EFFECT, FakeOutputStorage, FakeRenderer, OutputAlreadyExists,
)
from render.application.package_pipeline import RenderPackageNotFound, StaleGrant
from render.application.render_video import (
    COMMAND_RENDER, AttemptInProgress, GpuLeaseNotAvailable, InMemoryRenderUnitOfWork, PackageNotValidated, ReconcileNotNeeded,
    ReconcileRenderCommand, ReconcileRequired, RenderAttemptNotFound, RenderPipeline, RenderVideoCommand,
)
from render.domain.render_attempt import RenderAttemptRejected
from render.domain.render_command import KIND_RENDER, RenderCommandSpec, ToolIdentity
from render.ports.lease import GPU_LOCK_ID, GpuLease, GpuLeasePort, GpuLeaseUnavailable, GpuLeaseWaitExpired
from render.ports.output_probe import OutputProbePort
from render.ports.renderer import OutputObservationPort, RendererPort, RendererTimeout
from render.ports.repositories import KIND_ATTEMPT
from test_f17_resolve_validate_pipeline import Rig, _context, _validation_context

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'render' / 'application' / 'render_video.py'
CANARY = 'CANARY-5d2e8b-SECRET'
CONTENT = b'fake-video-bytes'
CONTENT_SHA = hashlib.sha256(CONTENT).hexdigest()
S = OperationState
SPEC = RenderCommandSpec(
    kind=KIND_RENDER, argv=('ffmpeg',), redacted_argv=('{tool}',), spec_fingerprint='f' * 64,
    tool_identity=ToolIdentity(name='ffmpeg', version='6.1', build='test-build'),
)


def out_ref(n: int = 1) -> str:
    return f'out/render-{n}.mp4'


class FakeLease:
    def __init__(self, slots: int = 2) -> None:
        self.slots = slots
        self.held: list[GpuLease] = []
        self.acquired: list[GpuLease] = []
        self.released: list[GpuLease] = []

    def acquire(self, owner_ref: str) -> GpuLease:
        if len(self.held) >= self.slots:
            raise GpuLeaseUnavailable()
        lease = GpuLease(lease_id=f'lease-{len(self.acquired) + 1}', owner_ref=owner_ref)
        self.held.append(lease)
        self.acquired.append(lease)
        return lease

    def release(self, lease: GpuLease) -> None:
        if lease in self.held:
            self.held.remove(lease)
        self.released.append(lease)


class WaitExpiredLease:
    def __init__(self) -> None:
        self.acquire_calls: list[str] = []
        self.released: list[GpuLease] = []

    def acquire(self, owner_ref: str) -> GpuLease:
        self.acquire_calls.append(owner_ref)
        raise GpuLeaseWaitExpired('no slot within the wait limit')

    def release(self, lease: GpuLease) -> None:
        self.released.append(lease)


class SpyProbe:
    def __init__(self, storage: FakeOutputStorage) -> None:
        self.storage = storage
        self.calls: list[str] = []

    def probe(self, output_ref: str):
        self.calls.append(output_ref)
        return self.storage.probe(output_ref)


def snapshot(uow) -> tuple:
    return tuple(dict(table._rows) for table in uow._tables)


class RenderRig:
    def __init__(self, *, validate: bool = True, slots: int = 2, lease=None) -> None:
        self.uow = InMemoryRenderUnitOfWork()
        self.base = Rig(self.uow)
        self.package = self.base.resolve().package
        if validate:
            self.base.validate(self.package.render_package_id, context=_validation_context())
        self.storage = FakeOutputStorage()
        self.renderer = FakeRenderer(self.storage, output_ref=out_ref(1), content=CONTENT)
        self.lease = FakeLease(slots) if lease is None else lease
        self.probe = SpyProbe(self.storage)
        self.pipeline = RenderPipeline(
            uow=self.uow, renderer=self.renderer, lease=self.lease, probe=self.probe, observer=self.storage, grants=self.base.grants,
        )

    def command(self, n: int = 1, **changes) -> RenderVideoCommand:
        values = {
            'grant': self.base.grant, 'render_package_id': self.package.render_package_id, 'render_attempt_id': f'attempt-{n}',
            'output_artifact_ref': out_ref(n), 'receipt_ref': f'receipt-{n}', 'command_spec': SPEC, 'context': _context(),
            'secret_values': (CANARY,),
        }
        values.update(changes)
        return RenderVideoCommand(**values)

    def render(self, n: int = 1, **changes):
        self.renderer.output_ref = out_ref(n)
        return self.pipeline.render_video(self.command(n, **changes))

    def reconcile(self, n: int = 1, expected_sha256: str | None = None):
        command = ReconcileRenderCommand(
            grant=self.base.grant, render_attempt_id=f'attempt-{n}', context=_context(), expected_sha256=expected_sha256,
        )
        return self.pipeline.reconcile_render(command)

    def states(self, n: int = 1) -> list:
        return [item.record.receipt_state for item in self.uow.renders.revisions(KIND_ATTEMPT, f'attempt-{n}')]

    def events(self) -> tuple:
        return self.uow.outbox.records()


def leaked_text(rig: RenderRig, result) -> str:
    attempts = [item.record.to_json() for rows in rig.uow.renders._rows.values() for item in rows if item.kind == KIND_ATTEMPT]
    events = [repr((record.event_type, dict(record.payload))) for record in rig.events()]
    problem = [] if result.problem is None else [repr(result.problem.values)]
    traces = [repr(trace) for trace in rig.uow.traces.records()]
    return ' '.join(attempts + events + problem + traces)


def unknown_rig(point: str = AFTER_SIDE_EFFECT) -> RenderRig:
    rig = RenderRig()
    rig.renderer.inject(point, RendererTimeout('render timed out'))
    rig.render()
    rig.renderer.fault = None
    return rig


def test_success_gives_succeeded_attempt_outbox_event_and_returns_the_lease():
    rig = RenderRig()
    result = rig.render()
    attempt = result.attempt
    assert result.replayed is False and result.problem is None and rig.renderer.calls == 1
    assert attempt.receipt_state is S.SUCCEEDED and attempt.revision == 2 and attempt.output_artifact_ref == out_ref(1)
    assert attempt.wall_time_ms == 1200 and attempt.peak_disk_bytes == 4096
    assert rig.states() == [S.PREPARED, S.STARTED, S.SUCCEEDED]
    (event,) = rig.events()
    assert event.event_type == 'RenderCompleted' and event.aggregate_id == 'attempt-1'
    assert event.payload['output_artifact_ref'] == out_ref(1) and event.payload['render_attempt_id'] == 'attempt-1'
    assert [lease.lock_id for lease in rig.lease.acquired] == [GPU_LOCK_ID]
    assert rig.lease.held == [] and rig.lease.released == rig.lease.acquired
    trace = rig.uow.traces.records()[-1]
    assert (trace.command, trace.outcome) == (COMMAND_RENDER, 'render_succeeded') and rig.uow.active is False
    assert rig.storage.operations == [('write', out_ref(1))]


def test_same_attempt_id_replays_without_a_second_render_or_lease():
    rig = RenderRig()
    first = rig.render()
    again = rig.render()
    assert again.replayed is True and again.attempt == first.attempt
    assert rig.renderer.calls == 1 and len(rig.lease.acquired) == 1 and len(rig.events()) == 1


@pytest.mark.parametrize('case', ['no_report', 'failed_report', 'passing_then_failed', 'fresh_context_fails'])
def test_package_without_a_passing_report_is_refused_before_lease_and_renderer(case):
    rig = RenderRig(validate=case in ('passing_then_failed', 'fresh_context_fails'))
    if case in ('failed_report', 'passing_then_failed'):
        rig.base.validate(rig.package.render_package_id, 'op-validate-bad', _validation_context(voice=None))
    changes = {'validation_context': _validation_context(voice=None)} if case == 'fresh_context_fails' else {}
    before = snapshot(rig.uow)
    with pytest.raises(PackageNotValidated) as caught:
        rig.render(**changes)
    problem = caught.value.problem
    assert caught.value.code == 'package_not_validated' and problem.code == 'package_not_validated'
    assert (problem.category, problem.retryable) == ('conflict', False)
    assert rig.renderer.calls == 0 and rig.lease.acquired == [] and snapshot(rig.uow) == before


def test_stale_grant_and_unknown_package_are_refused_without_effects():
    rig = RenderRig()
    before = snapshot(rig.uow)
    with pytest.raises(RenderPackageNotFound):
        rig.render(render_package_id='missing-package')
    rig.base.grants.current.clear()
    with pytest.raises(StaleGrant):
        rig.render()
    with pytest.raises(StaleGrant):
        rig.reconcile()
    assert rig.renderer.calls == 0 and rig.lease.acquired == [] and snapshot(rig.uow) == before


@pytest.mark.parametrize('point', [BEFORE_SIDE_EFFECT, DURING_SIDE_EFFECT])
def test_crash_before_or_during_the_side_effect_is_failed_without_ready_output(point):
    rig = RenderRig()
    rig.renderer.inject(point, RuntimeError(f'ffmpeg crashed {CANARY} token={CANARY} at C:/secret/dir/x.mp4'))
    result = rig.render()
    attempt = result.attempt
    assert attempt.receipt_state is S.FAILED and attempt.output_artifact_ref == out_ref(1)
    assert rig.states() == [S.PREPARED, S.STARTED, S.FAILED]
    assert rig.events() == () and rig.lease.held == [] and len(rig.lease.released) == 1
    assert result.problem.code == 'render_attempt_failed' and result.problem.retryable is True
    assert CANARY not in leaked_text(rig, result) and 'C:/secret' not in attempt.error
    if point == DURING_SIDE_EFFECT:
        assert rig.storage.files[out_ref(1)].complete is False and rig.storage.operations == [('write', out_ref(1))]
    else:
        assert rig.storage.files == {} and rig.storage.operations == []


def test_renderer_reported_failure_is_failed_and_redacted():
    rig = RenderRig()
    rig.renderer.fail_text = f'encoder rejected input {CANARY} password={CANARY}'
    result = rig.render()
    assert result.attempt.receipt_state is S.FAILED and rig.events() == () and rig.lease.held == []
    assert CANARY not in leaked_text(rig, result) and rig.storage.files == {}


def test_timeout_after_the_side_effect_is_outcome_unknown_and_never_ready():
    rig = RenderRig()
    rig.renderer.inject(AFTER_SIDE_EFFECT, RendererTimeout('render timed out'))
    result = rig.render()
    attempt = result.attempt
    assert attempt.receipt_state is S.OUTCOME_UNKNOWN and attempt.finished_at is None and attempt.revision == 2
    assert result.problem.code == 'render_outcome_unknown' and result.problem.retryable is False
    assert rig.events() == () and rig.lease.held == [] and rig.storage.files[out_ref(1)].complete is True
    assert rig.uow.traces.records()[-1].outcome == 'render_outcome_unknown'


def test_direct_retry_from_outcome_unknown_is_refused_before_lease_and_renderer():
    rig = unknown_rig()
    before = snapshot(rig.uow)
    with pytest.raises(ReconcileRequired) as caught:
        rig.render(2)
    assert caught.value.problem.code == 'reconcile_required'
    assert rig.renderer.calls == 1 and len(rig.lease.acquired) == 1 and snapshot(rig.uow) == before
    assert rig.uow.renders.latest(KIND_ATTEMPT, 'attempt-2') is None


def test_reconcile_resolves_to_succeeded_when_hash_and_playback_match():
    rig = unknown_rig()
    result = rig.reconcile(expected_sha256=CONTENT_SHA)
    attempt = result.attempt
    assert attempt.receipt_state is S.SUCCEEDED and attempt.revision == 3 and attempt.error is None and result.problem is None
    assert rig.probe.calls == [out_ref(1)]
    assert rig.states() == [S.PREPARED, S.STARTED, S.OUTCOME_UNKNOWN, S.SUCCEEDED]
    (event,) = rig.events()
    assert event.event_type == 'RenderCompleted' and event.payload['revision'] == 3
    assert rig.uow.traces.records()[-1].outcome == 'reconcile_succeeded' and rig.renderer.calls == 1


@pytest.mark.parametrize('point, expected_sha, reason', [
    (AFTER_SIDE_EFFECT, '0' * 64, 'reconcile_output_corrupt'),
    (BEFORE_SIDE_EFFECT, CONTENT_SHA, 'reconcile_output_missing'),
])
def test_reconcile_missing_or_corrupt_output_is_failed_without_event(point, expected_sha, reason):
    rig = unknown_rig(point)
    result = rig.reconcile(expected_sha256=expected_sha)
    assert result.attempt.receipt_state is S.FAILED and result.attempt.error == reason
    assert result.problem.code == 'render_attempt_failed' and rig.events() == () and rig.probe.calls == [out_ref(1)]
    assert {operation for operation, _ in rig.storage.operations} <= {'write'}


def test_reconcile_without_conclusive_evidence_keeps_outcome_unknown():
    rig = unknown_rig()
    before = snapshot(rig.uow)
    result = rig.reconcile()
    assert result.attempt.receipt_state is S.OUTCOME_UNKNOWN and result.attempt.revision == 2
    assert result.problem.code == 'render_outcome_unknown' and snapshot(rig.uow) == before
    assert rig.probe.calls == [out_ref(1)] and rig.events() == ()
    with pytest.raises(ReconcileRequired):
        rig.render(2)


def test_retry_after_reconcile_failed_makes_a_new_attempt_with_a_new_output():
    rig = unknown_rig()
    rig.reconcile(expected_sha256='0' * 64)
    old = rig.uow.renders.revisions(KIND_ATTEMPT, 'attempt-1')
    result = rig.render(2)
    assert result.attempt.receipt_state is S.SUCCEEDED and result.attempt.render_attempt_id == 'attempt-2'
    assert result.attempt.output_artifact_ref == out_ref(2)
    assert rig.uow.renders.revisions(KIND_ATTEMPT, 'attempt-1') == old and rig.states(1)[-1] is S.FAILED
    assert sorted(rig.storage.files) == [out_ref(1), out_ref(2)] and rig.storage.files[out_ref(1)].data == CONTENT
    assert rig.storage.operations == [('write', out_ref(1)), ('write', out_ref(2))]
    (event,) = rig.events()
    assert event.aggregate_id == 'attempt-2'


def test_new_attempt_cannot_reuse_an_earlier_output_ref_and_the_lease_is_returned():
    rig = RenderRig()
    rig.renderer.inject(BEFORE_SIDE_EFFECT, RuntimeError('crash'))
    rig.render()
    rig.renderer.fault = None
    before = snapshot(rig.uow)
    with pytest.raises(RenderAttemptRejected) as caught:
        rig.render(2, output_artifact_ref=out_ref(1))
    assert caught.value.code == 'output_artifact_ref_reused'
    assert len(rig.lease.acquired) == 2 and rig.lease.held == [] and len(rig.lease.released) == 2
    assert snapshot(rig.uow) == before and rig.renderer.calls == 1


def test_lease_is_returned_when_settling_the_attempt_raises():
    rig = RenderRig()

    def boom(trace):
        raise RuntimeError('trace store down')

    rig.uow.traces.append = boom
    with pytest.raises(RuntimeError):
        rig.render()
    assert rig.lease.held == [] and len(rig.lease.released) == 1
    assert rig.states() == [S.PREPARED, S.STARTED] and rig.events() == ()
    with pytest.raises(AttemptInProgress) as caught:
        rig.render(2)
    assert caught.value.problem.code == 'attempt_in_progress'


def test_no_free_gpu_slot_is_refused_before_any_attempt_or_render():
    rig = RenderRig(slots=0)
    before = snapshot(rig.uow)
    with pytest.raises(GpuLeaseNotAvailable) as caught:
        rig.render()
    problem = caught.value.problem
    assert (caught.value.code, problem.category, problem.retryable) == ('gpu_lease_unavailable', 'capacity', True)
    assert rig.renderer.calls == 0 and snapshot(rig.uow) == before


def test_gpu_lease_wait_expired_is_a_non_retryable_capacity_rejection_before_any_attempt():
    lease = WaitExpiredLease()
    rig = RenderRig(lease=lease)
    before = snapshot(rig.uow)
    with pytest.raises(GpuLeaseNotAvailable) as caught:
        rig.render()
    problem = caught.value.problem
    assert (caught.value.code, problem.category, problem.retryable) == ('gpu_lease_wait_expired', 'capacity', False)
    assert problem.values.get('status') == 503
    assert lease.acquire_calls == ['attempt-1'] and lease.released == []
    assert rig.renderer.calls == 0 and snapshot(rig.uow) == before


@pytest.mark.parametrize('knob, value, reason', [
    ('write_partial', True, 'output_not_decodable'),
    ('claimed_sha256', '0' * 64, 'output_hash_mismatch'),
])
def test_partial_file_or_hash_mismatch_is_failed_not_ready_and_the_file_is_kept(knob, value, reason):
    rig = RenderRig()
    setattr(rig.renderer, knob, value)
    result = rig.render()
    assert result.attempt.receipt_state is S.FAILED and result.attempt.error == reason
    assert rig.events() == () and rig.lease.held == []
    assert out_ref(1) in rig.storage.files and rig.storage.operations == [('write', out_ref(1))]


def test_outcome_with_another_output_ref_is_failed():
    rig = RenderRig()
    rig.renderer.output_ref = 'out/other.mp4'
    result = rig.pipeline.render_video(rig.command())
    assert result.attempt.receipt_state is S.FAILED and result.attempt.error == 'output_ref_mismatch'
    assert rig.events() == () and rig.lease.held == []


def test_reconcile_refuses_attempts_that_are_not_unknown_or_missing():
    rig = RenderRig()
    rig.render()
    rig.probe.calls.clear()
    with pytest.raises(ReconcileNotNeeded) as caught:
        rig.reconcile()
    assert caught.value.problem.code == 'reconcile_not_needed' and rig.probe.calls == []
    with pytest.raises(RenderAttemptNotFound):
        rig.reconcile(9)


def test_fake_storage_has_no_delete_and_refuses_overwrite():
    storage = FakeOutputStorage()
    storage.write('out/a.mp4', b'one', complete=True)
    with pytest.raises(OutputAlreadyExists):
        storage.write('out/a.mp4', b'two', complete=True)
    assert storage.files['out/a.mp4'].data == b'one'
    assert storage.operations == [('write', 'out/a.mp4'), ('write_refused', 'out/a.mp4')]
    assert {name for name in dir(FakeOutputStorage) if not name.startswith('_')} == {'observe', 'probe', 'write'}


def test_fakes_satisfy_the_ports():
    rig = RenderRig()
    assert isinstance(rig.renderer, RendererPort) and isinstance(rig.lease, GpuLeasePort)
    assert isinstance(rig.storage, OutputObservationPort) and isinstance(rig.probe, OutputProbePort)


ALLOWED_IMPORTS = frozenset({
    '__future__', 'dataclasses', 'datetime', 'hashlib', 're', 'types', 'typing',
    'controlplane.domain.common.contracts', 'controlplane.domain.orchestration', 'controlplane.domain.statemachine',
    'render.adapters.memory', 'render.application.package_pipeline', 'render.domain.events', 'render.domain.package_contract',
    'render.domain.render_attempt', 'render.domain.render_command', 'render.domain.validate_package', 'render.ports.lease',
    'render.ports.output_probe', 'render.ports.renderer', 'render.ports.repositories',
})


def test_module_imports_only_f_and_controlplane_contracts():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module)
    assert names <= ALLOWED_IMPORTS


def test_test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert any(line.startswith('coveredIds:') for line in (doc or '').splitlines())
