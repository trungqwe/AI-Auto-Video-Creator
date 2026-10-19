"""G-08: luồng VariantReservation và registry revision (CT-ORC-012).

coveredIds: CT-ORC-012, TST-WF-VAR-001, TST-WF-VAR-003, TST-WF-VAR-004 (phía G)
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import threading

import pytest

from controlplane.application.orchestration import variant_reservation_flow as flow_module
from controlplane.application.orchestration.variant_reservation_flow import (
    ReserveVariantRequest,
    VariantRegistryPort,
    VariantReservationFlow,
)
from controlplane.domain.orchestration import OrchestrationContractError, ReservationState
from controlplane.domain.statemachine import JobState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'orchestration' / 'variant_reservation_flow.py'
WS = '00000000-0000-4000-8000-000000000081'
OTHER_WS = '00000000-0000-4000-8000-000000000082'
ACTIVE = ReservationState.ACTIVE
RELEASED = ReservationState.RELEASED
CONVERTED = ReservationState.CONVERTED
STALE = 'VARIANT_VALIDATION_STALE'
CONFLICT = 'VARIANT_CONFLICT'
FORBIDDEN = 'FORBIDDEN_TRANSITION'


class FakeRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self.revisions = {}
        self.records = {}
        self.calls = []
        self.fail_next_save = False

    def revision(self, workspace_id=WS):
        return self.revisions.get(workspace_id, 1)

    def count(self, name):
        return self.calls.count(name)

    def states(self):
        return [r.state for r in self.records.values()]

    def job_ids(self):
        return [r.job_id for r in self.records.values()]

    def current_revision(self, workspace_id):
        with self._lock:
            self.calls.append('current_revision')
            return self.revisions.get(workspace_id, 1)

    def find_by_job(self, workspace_id, job_id):
        with self._lock:
            self.calls.append('find_by_job')
            return next((r for r in self.records.values() if r.workspace_id == workspace_id and r.job_id == job_id), None)

    def find_active_by_fingerprint(self, workspace_id, fingerprint):
        with self._lock:
            self.calls.append('find_active_by_fingerprint')
            return next((r for r in self.records.values() if r.workspace_id == workspace_id and r.fingerprint == fingerprint and r.state in (ACTIVE, CONVERTED)), None)

    def save(self, record):
        with self._lock:
            self.calls.append('save')
            if self.fail_next_save:
                self.fail_next_save = False
                raise RuntimeError('save failed')
            prior = self.records.get(record.reservation_id)
            assert prior is None or prior.state == ACTIVE, 'terminal reservation reopened'
            if prior is None:
                assert not any(r.workspace_id == record.workspace_id and r.job_id == record.job_id for r in self.records.values()), 'second reservation row for job'
            self.records[record.reservation_id] = record

    def bump_revision(self, workspace_id):
        with self._lock:
            self.calls.append('bump_revision')
            self.revisions[workspace_id] = self.revisions.get(workspace_id, 1) + 1
            return self.revisions[workspace_id]


def make_request(job='job-1', fp='fp-1', expected=1, ws=WS):
    return ReserveVariantRequest(
        workspace_id=ws, job_id=job, fingerprint=fp, snapshot_scope='snap-1', validation_ref='val-1',
        variation_policy_revision='pol-1', expected_registry_revision=expected, idempotency_key=f'idem-{job}',
    )


def code_of(call, *args):
    with pytest.raises(OrchestrationContractError) as info:
        call(*args)
    return info.value.code


@pytest.fixture
def registry():
    return FakeRegistry()


@pytest.fixture
def flow(registry):
    return VariantReservationFlow(registry)


def test_reserve_creates_active_reservation_and_bumps_revision_once(flow, registry):
    receipt = flow.reserve(make_request())
    assert receipt.state is ACTIVE
    assert receipt.committed_registry_revision == 2
    assert registry.revision() == 2
    assert registry.count('save') == 1 and registry.count('bump_revision') == 1
    assert registry.states() == [ACTIVE]
    assert (receipt.workspace_id, receipt.job_id, receipt.idempotency_key) == (WS, 'job-1', 'idem-job-1')


def test_stale_expected_revision_creates_nothing_and_keeps_revision(flow, registry):
    registry.revisions[WS] = 3
    assert code_of(flow.reserve, make_request(expected=1)) == STALE
    assert registry.records == {}
    assert registry.revision() == 3
    assert registry.count('save') == 0 and registry.count('bump_revision') == 0


def test_var_001_two_jobs_same_fingerprint_one_wins_other_stale_then_conflict(flow, registry):
    winner = flow.reserve(make_request(job='job-a'))
    assert winner.state is ACTIVE
    assert code_of(flow.reserve, make_request(job='job-b')) == STALE
    refreshed = registry.current_revision(WS)
    assert refreshed == 2
    assert code_of(flow.reserve, make_request(job='job-b', expected=refreshed)) == CONFLICT
    assert registry.job_ids() == ['job-a']
    assert registry.revision() == 2


def test_converted_fingerprint_of_other_job_conflicts(flow, registry):
    flow.reserve(make_request(job='job-a'))
    flow.convert(WS, 'job-a', JobState.COMPLETED)
    revision = registry.revision()
    assert code_of(flow.reserve, make_request(job='job-b', expected=revision)) == CONFLICT
    assert registry.job_ids() == ['job-a']
    assert registry.revision() == revision


def test_released_fingerprint_can_be_reserved_by_another_job(flow, registry):
    flow.reserve(make_request(job='job-a'))
    flow.release(WS, 'job-a', JobState.FAILED_FINAL)
    receipt = flow.reserve(make_request(job='job-b', expected=registry.revision()))
    assert receipt.state is ACTIVE
    assert sorted(s.value for s in registry.states()) == ['ACTIVE', 'RELEASED']


def test_registry_revision_is_scoped_per_workspace(flow, registry):
    flow.reserve(make_request())
    other = flow.reserve(make_request(ws=OTHER_WS))
    assert other.state is ACTIVE
    assert registry.revision(WS) == 2 and registry.revision(OTHER_WS) == 2


def test_lost_ack_retry_returns_old_receipt_without_new_reservation(flow, registry):
    request = make_request()
    first = flow.reserve(request)
    saves = registry.count('save')
    for _ in range(3):
        assert flow.reserve(request) == first
    assert len(registry.records) == 1
    assert registry.count('save') == saves
    assert registry.revision() == 2


@pytest.mark.parametrize('field,value', [
    ('fingerprint', 'fp-other'), ('snapshot_scope', 'snap-2'), ('validation_ref', 'val-2'),
    ('variation_policy_revision', 'pol-2'), ('expected_registry_revision', 7), ('idempotency_key', 'idem-other'),
])
def test_same_job_with_different_input_is_conflict(flow, registry, field, value):
    request = make_request()
    flow.reserve(request)
    assert code_of(flow.reserve, dataclasses.replace(request, **{field: value})) == CONFLICT
    assert registry.states() == [ACTIVE]
    assert registry.revision() == 2


def _run_threads(targets):
    threads = [threading.Thread(target=target) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_concurrent_identical_reserve_creates_single_reservation(flow, registry):
    request = make_request()
    receipts = []
    _run_threads([lambda: receipts.append(flow.reserve(request)) for _ in range(8)])
    assert len(receipts) == 8 and len(set(receipts)) == 1
    assert registry.states() == [ACTIVE]
    assert registry.revision() == 2


def test_concurrent_jobs_with_same_fingerprint_exactly_one_wins(flow, registry):
    outcomes = []

    def attempt(job):
        try:
            outcomes.append(flow.reserve(make_request(job=job)).state)
        except OrchestrationContractError as error:
            outcomes.append(error.code)

    _run_threads([lambda: attempt('job-a'), lambda: attempt('job-b')])
    assert len(outcomes) == 2 and ACTIVE in outcomes and STALE in outcomes
    assert registry.states() == [ACTIVE]
    assert registry.revision() == 2


@pytest.mark.parametrize('field', ['workspace_id', 'job_id', 'fingerprint', 'snapshot_scope', 'validation_ref', 'variation_policy_revision', 'idempotency_key'])
def test_reserve_rejects_empty_text_before_touching_registry(flow, registry, field):
    with pytest.raises(ValueError):
        flow.reserve(dataclasses.replace(make_request(), **{field: ''}))
    assert registry.calls == []


@pytest.mark.parametrize('bad', [0, -1, True, '1', 1.0, None])
def test_reserve_rejects_invalid_expected_revision(flow, registry, bad):
    with pytest.raises(ValueError):
        flow.reserve(dataclasses.replace(make_request(), expected_registry_revision=bad))
    assert registry.calls == []


def test_reserve_rejects_non_request_object(flow, registry):
    with pytest.raises(TypeError):
        flow.reserve({'job_id': 'job-1'})
    assert registry.calls == []


def test_release_requires_recorded_terminal_failure(flow, registry):
    flow.reserve(make_request())
    before = (dict(registry.records), registry.revision())
    for state in JobState:
        if state is not JobState.FAILED_FINAL:
            assert code_of(flow.release, WS, 'job-1', state) == FORBIDDEN
    assert (dict(registry.records), registry.revision()) == before


def test_release_after_failed_final_bumps_revision_once_and_is_idempotent(flow, registry):
    flow.reserve(make_request())
    receipt = flow.release(WS, 'job-1', JobState.FAILED_FINAL)
    assert receipt.state is RELEASED
    assert registry.revision() == 3
    assert flow.release(WS, 'job-1', JobState.FAILED_FINAL) == receipt
    assert registry.revision() == 3
    assert registry.count('save') == 2
    assert registry.find_active_by_fingerprint(WS, 'fp-1') is None


def test_convert_only_on_completion_and_only_once(flow, registry):
    flow.reserve(make_request())
    for state in JobState:
        if state is not JobState.COMPLETED:
            assert code_of(flow.convert, WS, 'job-1', state) == FORBIDDEN
    assert registry.states() == [ACTIVE]
    assert registry.revision() == 2
    receipt = flow.convert(WS, 'job-1', JobState.COMPLETED)
    assert receipt.state is CONVERTED
    assert registry.revision() == 3
    assert flow.convert(WS, 'job-1', JobState.COMPLETED) == receipt
    assert registry.revision() == 3
    assert registry.count('save') == 2


def test_release_and_convert_of_unknown_job_are_not_found(flow, registry):
    assert code_of(flow.release, WS, 'ghost', JobState.FAILED_FINAL) == 'NOT_FOUND'
    assert code_of(flow.convert, WS, 'ghost', JobState.COMPLETED) == 'NOT_FOUND'
    assert registry.revision() == 1
    assert registry.count('save') == 0


def test_converted_cannot_be_released_and_released_cannot_be_converted(flow, registry):
    flow.reserve(make_request(job='job-a', fp='fp-a'))
    flow.reserve(make_request(job='job-b', fp='fp-b', expected=2))
    flow.convert(WS, 'job-a', JobState.COMPLETED)
    flow.release(WS, 'job-b', JobState.FAILED_FINAL)
    revision = registry.revision()
    assert code_of(flow.release, WS, 'job-a', JobState.FAILED_FINAL) == FORBIDDEN
    assert code_of(flow.convert, WS, 'job-b', JobState.COMPLETED) == FORBIDDEN
    assert sorted(s.value for s in registry.states()) == ['CONVERTED', 'RELEASED']
    assert registry.revision() == revision


@pytest.mark.parametrize('method', ['release', 'convert'])
def test_settle_rejects_empty_ids(flow, registry, method):
    state = JobState.FAILED_FINAL if method == 'release' else JobState.COMPLETED
    with pytest.raises(ValueError):
        getattr(flow, method)('', 'job-1', state)
    with pytest.raises(ValueError):
        getattr(flow, method)(WS, '', state)
    assert registry.calls == []


@pytest.mark.parametrize('hook', ['on_wait', 'on_desktop_offline', 'on_lease_expired'])
def test_wait_offline_and_lease_expiry_do_not_change_reservation(flow, registry, hook):
    receipt = flow.reserve(make_request())
    records, saves = dict(registry.records), registry.count('save')
    for _ in range(2):
        assert getattr(flow, hook)(WS, 'job-1') == receipt
    assert getattr(flow, hook)(WS, 'job-ghost') is None
    assert registry.records == records
    assert registry.count('save') == saves
    assert registry.revision() == 2


@pytest.mark.parametrize('terminal', ['release', 'convert'])
def test_old_receipt_never_resurrects_active(flow, registry, terminal):
    request = make_request()
    old = flow.reserve(request)
    if terminal == 'release':
        settled = flow.release(WS, 'job-1', JobState.FAILED_FINAL)
    else:
        settled = flow.convert(WS, 'job-1', JobState.COMPLETED)
    revision, saves = registry.revision(), registry.count('save')
    replay = flow.reserve(request)
    assert replay.reservation_id == old.reservation_id
    assert replay.state is settled.state and replay.state is not ACTIVE
    assert registry.revision() == revision and registry.count('save') == saves
    assert registry.states() == [settled.state]
    again = dataclasses.replace(request, expected_registry_revision=revision, idempotency_key='idem-new')
    assert code_of(flow.reserve, again) == CONFLICT
    assert registry.states() == [settled.state]


def test_each_create_release_convert_bumps_revision_exactly_once(flow, registry):
    flow.reserve(make_request(job='job-a', fp='fp-a', expected=1))
    assert registry.revision() == 2
    flow.reserve(make_request(job='job-b', fp='fp-b', expected=2))
    assert registry.revision() == 3
    flow.release(WS, 'job-a', JobState.FAILED_FINAL)
    assert registry.revision() == 4
    flow.convert(WS, 'job-b', JobState.COMPLETED)
    assert registry.revision() == 5
    assert registry.count('save') == 4 and registry.count('bump_revision') == 4


def test_var_004_two_distinct_variants_both_succeed_after_refresh(flow, registry):
    first = flow.reserve(make_request(job='job-a', fp='fp-a', expected=1))
    assert code_of(flow.reserve, make_request(job='job-b', fp='fp-b', expected=1)) == STALE
    refreshed = registry.current_revision(WS)
    second = flow.reserve(make_request(job='job-b', fp='fp-b', expected=refreshed))
    assert first.state is ACTIVE and second.state is ACTIVE
    assert second.committed_registry_revision == 3 and registry.revision() == 3
    assert registry.states() == [ACTIVE, ACTIVE]


def test_save_failure_does_not_bump_revision(flow, registry):
    registry.fail_next_save = True
    with pytest.raises(RuntimeError):
        flow.reserve(make_request())
    assert registry.records == {} and registry.revision() == 1
    assert registry.count('bump_revision') == 0
    assert flow.reserve(make_request()).committed_registry_revision == 2


def test_receipt_is_immutable(flow):
    receipt = flow.reserve(make_request())
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.state = RELEASED


def test_port_exposes_exactly_the_five_registry_methods():
    assert [n for n in dir(VariantRegistryPort) if not n.startswith('_')] == [
        'bump_revision', 'current_revision', 'find_active_by_fingerprint', 'find_by_job', 'save',
    ]


def test_module_imports_only_stdlib_and_controlplane_domain():
    assert flow_module.ReservationState is ReservationState
    names = []
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module)
    allowed = {'__future__', 'dataclasses', 'threading', 'typing', 'uuid'}
    for name in names:
        assert name in allowed or name == 'controlplane.domain' or name.startswith('controlplane.domain.'), name
