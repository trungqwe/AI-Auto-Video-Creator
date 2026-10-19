"""G-10: CommitVideoCompletion trong một unit of work (CT-ORC-008; INV-010, INV-017).

coveredIds: CT-ORC-008, INV-010, INV-017 (TST-WF-INV-010, TST-WF-INV-017 mức logic)
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import pathlib

import pytest

from controlplane.application.orchestration.commit_completion import (
    CommitVideoCompletion,
    CompletionContext,
    CompletionRejectedError,
    CompletionStorePort,
    JobRecord,
)
from controlplane.application.orchestration.event_payloads import build_g_event
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.domain.orchestration import ReservationState
from controlplane.domain.orchestration import completion_gate as gate
from controlplane.domain.orchestration.completion_binding import validate_ledger_entry
from controlplane.domain.orchestration.completion_gate import GateAction, ReservationBinding
from controlplane.domain.orchestration.fencing import ACCEPTED, STALE_RECOVERY_EPOCH, FencingDecision
from controlplane.domain.statemachine import JobState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'orchestration' / 'commit_completion.py'
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-c-i-completion' / 'payloads.json').read_text(encoding='utf-8'))
REQUEST = FIXTURE['entities']['CommitVideoCompletionRequest']['valid'][0]
LEDGER = FIXTURE['entities']['CompletionLedgerEntry']['valid'][0]
JOB_ID = REQUEST['video_job_id']
RES_ID = REQUEST['variant_reservation_id']
SHA = REQUEST['output_sha256']
REV = REQUEST['expected_variant_registry_revision']
BATCH = LEDGER['batch_ref']
JOB_REVISION = 3
CONTEXT_KEYS = (
    'completion_id', 'batch_ref', 'session_ref', 'cloud_location_ref', 'preset_revision_ref',
    'output_naming_metadata', 'cost_usage_summary', 'audit_actor', 'cleanup_policy_ref', 'completed_at',
)
WRITE_STEPS = (
    'insert_ledger', 'set_job_state', 'convert_capacity_reservation', 'convert_variant_reservation',
    'set_registry_revision', 'increment_batch_completed', 'record_usage', 'insert_outbox', 'insert_cleanup_eligibility',
)
POINTS = [f'{when}:{name}' for name in WRITE_STEPS for when in ('before', 'after')] + ['before:commit']


def valid_request():
    return copy.deepcopy(REQUEST)


def make_context(**override):
    fields = {key: copy.deepcopy(LEDGER[key]) for key in CONTEXT_KEYS}
    fields['fencing'] = FencingDecision(True, ACCEPTED)
    return CompletionContext(**(fields | override))

class InjectedFailure(RuntimeError):
    pass


class Recorder:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.log = []
        self.unexpected = []

    def hit(self, point):
        self.log.append(point)
        if point == self.fail_at:
            raise InjectedFailure(point)


def step(name):
    def wrap(method):
        def run(self, *args):
            self.rec.hit(f'before:{name}')
            method(self, *args)
            self.rec.hit(f'after:{name}')
        run.__name__ = method.__name__
        return run
    return wrap


class World:
    def __init__(self):
        self.ledgers = {}
        self.jobs = {JOB_ID: JobRecord(JOB_ID, JobState.READY_FOR_COMPLETION, JOB_REVISION)}
        self.variant = {RES_ID: ReservationBinding(RES_ID, JOB_ID, SHA, ReservationState.ACTIVE)}
        self.capacity = {JOB_ID: 'ACTIVE'}
        self.registry_revision = REV
        self.batch_counts = {BATCH: 0}
        self.usage = []
        self.outbox = []
        self.cleanup = []

    def snapshot(self):
        return copy.deepcopy(self.__dict__)

    def restore(self, snapshot):
        self.__dict__.clear()
        self.__dict__.update(copy.deepcopy(snapshot))


class FakeStore:
    def __init__(self, world, rec):
        self.world = world
        self.rec = rec

    def __getattr__(self, name):
        self.rec.unexpected.append(name)
        raise AttributeError(name)

    def find_ledger(self, video_job_id):
        return copy.deepcopy(self.world.ledgers.get(video_job_id))

    def get_job(self, job_id):
        return self.world.jobs.get(job_id)

    def get_variant_reservation(self, reservation_id):
        return self.world.variant.get(reservation_id)

    def get_registry_revision(self):
        return self.world.registry_revision

    @step('insert_ledger')
    def insert_ledger(self, ledger):
        assert ledger['video_job_id'] not in self.world.ledgers
        self.world.ledgers[ledger['video_job_id']] = copy.deepcopy(dict(ledger))

    @step('set_job_state')
    def set_job_state(self, job_id, state, revision):
        self.world.jobs[job_id] = JobRecord(job_id, state, revision)

    @step('convert_capacity_reservation')
    def convert_capacity_reservation(self, job_id):
        self.world.capacity[job_id] = 'CONVERTED'

    @step('convert_variant_reservation')
    def convert_variant_reservation(self, reservation_id):
        self.world.variant[reservation_id] = dataclasses.replace(self.world.variant[reservation_id], state=ReservationState.CONVERTED)

    @step('set_registry_revision')
    def set_registry_revision(self, revision):
        self.world.registry_revision = revision

    @step('increment_batch_completed')
    def increment_batch_completed(self, batch_ref):
        self.world.batch_counts[batch_ref] += 1

    @step('insert_outbox')
    def insert_outbox(self, event):
        self.world.outbox.append(copy.deepcopy(dict(event)))

    @step('insert_cleanup_eligibility')
    def insert_cleanup_eligibility(self, record):
        self.world.cleanup.append(copy.deepcopy(dict(record)))

class FakeMediaUsage:
    def __init__(self, world, rec):
        self.world = world
        self.rec = rec

    @step('record_usage')
    def record(self, manifest):
        self.world.usage.append(copy.deepcopy(manifest))


class FakeUow(IUnitOfWork):
    def __init__(self, world, rec):
        self.world = world
        self.rec = rec
        self.store = FakeStore(world, rec)
        self.snapshot = None
        self.committed = False
        self.rolled_back = False

    def begin(self):
        self.snapshot = self.world.snapshot()

    def commit(self):
        self.rec.hit('before:commit')
        self.snapshot = None
        self.committed = True

    def rollback(self):
        if self.snapshot is not None:
            self.world.restore(self.snapshot)
            self.snapshot = None
        self.rolled_back = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None


class Harness:
    def __init__(self, fail_at=None):
        self.world = World()
        self.rec = Recorder(fail_at)
        self.uows = []
        self.usage = FakeMediaUsage(self.world, self.rec)
        self.service = CommitVideoCompletion(self.make_uow, self.usage)

    def make_uow(self):
        uow = FakeUow(self.world, self.rec)
        self.uows.append(uow)
        return uow


def run_ok(harness=None):
    h = harness or Harness()
    return h, h.service.execute(valid_request(), make_context())


def test_execute_completes_everything_in_one_committed_unit_of_work():
    h, result = run_ok()
    w = h.world
    assert result.code == 'COMPLETED'
    assert w.ledgers == {JOB_ID: result.ledger}
    assert w.jobs[JOB_ID] == JobRecord(JOB_ID, JobState.COMPLETED, JOB_REVISION + 1)
    assert w.capacity[JOB_ID] == 'CONVERTED'
    assert w.variant[RES_ID].state == ReservationState.CONVERTED
    assert w.registry_revision == REV + 1
    assert w.batch_counts[BATCH] == 1
    assert w.usage == [REQUEST['media_usage_manifest']]
    assert len(h.uows) == 1 and h.uows[0].committed and not h.uows[0].rolled_back


def test_ledger_is_a_valid_binding_entry_with_non_request_fields_from_context():
    _, result = run_ok()
    context = make_context()
    assert validate_ledger_entry(result.ledger) == []
    for key in CONTEXT_KEYS:
        assert result.ledger[key] == getattr(context, key)
    for field in gate.LEDGER_COMPARED_FIELDS:
        assert result.ledger[field] == REQUEST[field]


def test_write_order_puts_outbox_after_usage_and_every_state_write():
    h, _ = run_ok()
    writes = [p[len('before:'):] for p in h.rec.log if p.startswith('before:') and p != 'before:commit']
    assert writes == list(WRITE_STEPS)
    assert h.rec.log[-1] == 'before:commit'


def test_video_completed_event_is_built_by_g13_builder():
    h, result = run_ok()
    expected = build_g_event(
        'VideoCompleted', JOB_ID, JOB_REVISION + 1, REQUEST['recovery_epoch'],
        {'completion_id': result.ledger['completion_id'], 'video_job_id': JOB_ID, 'variant_registry_revision': REV + 1},
    )
    assert h.world.outbox == [expected]


def test_cleanup_eligibility_is_a_record_and_no_delete_command_is_issued():
    h, result = run_ok()
    assert h.world.cleanup == [{
        'completion_id': result.ledger['completion_id'],
        'video_job_id': JOB_ID,
        'output_artifact_version_id': REQUEST['output_artifact_version_id'],
        'cleanup_policy_ref': make_context().cleanup_policy_ref,
        'state': 'CLEANUP_ELIGIBLE',
    }]
    assert h.rec.unexpected == []

def test_repeat_same_input_five_times_counts_once():
    h = Harness()
    results = [h.service.execute(valid_request(), make_context()) for _ in range(5)]
    w = h.world
    assert results[0].code == 'COMPLETED'
    assert all(r.code == 'ALREADY_COMPLETED' for r in results[1:])
    assert all(r.ledger == results[0].ledger for r in results)
    assert w.batch_counts[BATCH] == 1
    assert len(w.ledgers) == len(w.outbox) == len(w.usage) == len(w.cleanup) == 1
    assert w.registry_revision == REV + 1
    assert w.jobs[JOB_ID].revision == JOB_REVISION + 1
    assert h.rec.log.count('before:insert_ledger') == 1


def changed(field, value):
    if field == 'output_sha256':
        return 'f' * 64
    if isinstance(value, list):
        return []
    return value + '-changed'


CONFLICT_FIELDS = [field for field in gate.LEDGER_COMPARED_FIELDS if field != 'video_job_id']


@pytest.mark.parametrize('field', CONFLICT_FIELDS)
def test_same_job_with_different_input_is_conflict_and_writes_nothing(field):
    h, _ = run_ok()
    before = h.world.snapshot()
    log_size = len(h.rec.log)
    request = valid_request()
    request[field] = changed(field, request[field])
    with pytest.raises(CompletionRejectedError) as info:
        h.service.execute(request, make_context())
    assert info.value.code == 'CONFLICT'
    assert info.value.action == GateAction.REJECT
    assert h.world.snapshot() == before
    assert h.rec.log[log_size:] == []


EARLIER_THAN_OUTBOX = WRITE_STEPS[:WRITE_STEPS.index('insert_outbox')]


@pytest.mark.parametrize('point', POINTS)
def test_failure_at_any_step_rolls_back_everything(point):
    h = Harness(fail_at=point)
    before = h.world.snapshot()
    with pytest.raises(InjectedFailure):
        h.service.execute(valid_request(), make_context())
    assert h.world.snapshot() == before
    assert h.uows[0].rolled_back and not h.uows[0].committed
    assert h.world.ledgers == {} and h.world.usage == [] and h.world.outbox == []
    assert h.world.batch_counts[BATCH] == 0


@pytest.mark.parametrize('point', [f'{when}:{name}' for name in EARLIER_THAN_OUTBOX for when in ('before', 'after')])
def test_outbox_is_never_attempted_when_an_earlier_step_fails(point):
    h = Harness(fail_at=point)
    with pytest.raises(InjectedFailure):
        h.service.execute(valid_request(), make_context())
    assert 'before:insert_outbox' not in h.rec.log


def test_retry_after_rolled_back_failure_completes_once():
    h = Harness(fail_at='after:record_usage')
    with pytest.raises(InjectedFailure):
        h.service.execute(valid_request(), make_context())
    h.rec.fail_at = None
    result = h.service.execute(valid_request(), make_context())
    assert result.code == 'COMPLETED'
    assert h.world.batch_counts[BATCH] == 1
    assert len(h.world.ledgers) == len(h.world.usage) == len(h.world.outbox) == 1
    assert h.world.registry_revision == REV + 1

def no_write_attempted(h):
    return [p for p in h.rec.log if p.startswith('before:')] == []


@pytest.mark.parametrize('revision', [0, REV - 1, REV + 1])
def test_stale_registry_writes_nothing_and_keeps_waiting(revision):
    h = Harness()
    h.world.registry_revision = revision
    before = h.world.snapshot()
    with pytest.raises(CompletionRejectedError) as info:
        h.service.execute(valid_request(), make_context())
    assert info.value.code == 'VARIANT_REGISTRY_STALE'
    assert info.value.action == GateAction.KEEP_WAITING
    assert h.world.snapshot() == before
    assert no_write_attempted(h)
    assert h.uows[0].rolled_back and not h.uows[0].committed


def case_job_active(h):
    h.world.jobs[JOB_ID] = JobRecord(JOB_ID, JobState.ACTIVE, JOB_REVISION)
    return valid_request(), make_context()


def case_job_missing(h):
    del h.world.jobs[JOB_ID]
    return valid_request(), make_context()


def case_fencing_rejected(h):
    return valid_request(), make_context(fencing=FencingDecision(False, STALE_RECOVERY_EPOCH))


def case_blank_cloud_verification(h):
    request = valid_request()
    request['cloud_location_verification_ref'] = '  '
    return request, make_context()


def case_reservation_converted(h):
    h.world.variant[RES_ID] = dataclasses.replace(h.world.variant[RES_ID], state=ReservationState.CONVERTED)
    return valid_request(), make_context()


def case_reservation_missing(h):
    del h.world.variant[RES_ID]
    return valid_request(), make_context()


def case_invalid_request(h):
    request = valid_request()
    del request['output_sha256']
    return request, make_context()


def case_confirmed_variant_conflict(h):
    return valid_request(), make_context(variant_conflict_confirmed=True)


REJECT_CASES = [
    (case_job_active, 'JOB_NOT_READY', GateAction.REJECT),
    (case_job_missing, 'JOB_NOT_READY', GateAction.REJECT),
    (case_fencing_rejected, STALE_RECOVERY_EPOCH, GateAction.REJECT),
    (case_blank_cloud_verification, 'CLOUD_VERIFICATION_MISSING', GateAction.REJECT),
    (case_reservation_converted, 'RESERVATION_INVALID', GateAction.REJECT),
    (case_reservation_missing, 'RESERVATION_INVALID', GateAction.REJECT),
    (case_invalid_request, 'INVALID_REQUEST', GateAction.REJECT),
    (case_confirmed_variant_conflict, 'VARIANT_CONFLICT_FINAL', GateAction.FAIL_JOB_RELEASE),
]


@pytest.mark.parametrize('case,code,action', REJECT_CASES, ids=[case[0].__name__ for case in REJECT_CASES])
def test_gate_rejection_writes_nothing(case, code, action):
    h = Harness()
    request, context = case(h)
    before = h.world.snapshot()
    with pytest.raises(CompletionRejectedError) as info:
        h.service.execute(request, context)
    assert (info.value.code, info.value.action) == (code, action)
    assert h.world.snapshot() == before
    assert no_write_attempted(h)

def test_context_must_be_a_completion_context():
    h = Harness()
    with pytest.raises(TypeError):
        h.service.execute(valid_request(), {})
    assert h.uows == []


def test_store_port_has_no_delete_or_media_usage_operation():
    names = [name for name in dir(CompletionStorePort) if not name.startswith('_')]
    assert names
    assert not [n for n in names if any(word in n for word in ('delete', 'remove', 'unlink', 'purge', 'usage'))]


def test_module_has_no_io_clock_or_delete_names():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    imported = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {'os', 'shutil', 'pathlib', 'subprocess', 'time', 'datetime', 'uuid', 'random', 'socket'}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not [x for x in names if any(word in x.lower() for word in ('delete', 'unlink', 'remove', 'rmtree'))]
