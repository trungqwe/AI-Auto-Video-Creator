"""G-04: cấp grant đơn điệu, một lease hoạt động mỗi stage (CT-WF-004, INV-003).

coveredIds: CT-WF-004, INV-003, INV-016, TST-WF-INV-003
"""
from __future__ import annotations

import ast
import dataclasses
from datetime import datetime, timedelta, timezone
import pathlib
import threading

import pytest

from controlplane.application.orchestration.grant_issuance import ActiveGrantExistsError, GrantIssuer
from controlplane.domain.orchestration.fencing import (
    ACCEPTED,
    STALE_EXECUTION_GENERATION,
    STALE_RECOVERY_EPOCH,
    FencingDecision,
    GrantClaims,
    evaluate_result_fencing,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'orchestration' / 'grant_issuance.py'
NOW = datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
STAGE = '00000000-0000-4000-8000-000000000062'
OTHER_STAGE = '00000000-0000-4000-8000-000000000063'
OP = 'commit_voice_track'
FP = 'fp-001'
_UNSET = object()


class FakeGrantStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.grants = {}
        self.revoked = []
        self.insert_log = []
        self.calls = []
        self.fail_next_insert = False
        self.latest_override = _UNSET

    def latest_generation(self, stage_run_id):
        with self._lock:
            self.calls.append('latest_generation')
            if self.latest_override is not _UNSET:
                return self.latest_override
            return max((c.execution_generation for c in self.grants.values() if c.stage_run_id == stage_run_id), default=0)

    def active_grant(self, stage_run_id, now):
        with self._lock:
            self.calls.append('active_grant')
            live = [c for c in self.grants.values() if c.stage_run_id == stage_run_id and c.grant_id not in self.revoked]
            return max(live, key=lambda c: c.execution_generation) if live else None

    def insert(self, claims):
        with self._lock:
            self.calls.append('insert')
            if self.fail_next_insert:
                self.fail_next_insert = False
                raise RuntimeError('insert failed')
            assert claims.grant_id not in self.grants, 'grant_id reused'
            same_stage = [c for c in self.grants.values() if c.stage_run_id == claims.stage_run_id]
            assert all(c.execution_generation < claims.execution_generation for c in same_stage), 'generation reused or decreased'
            assert all(c.grant_id in self.revoked for c in same_stage), 'second active grant for stage'
            self.grants[claims.grant_id] = claims
            self.insert_log.append(claims)

    def revoke(self, grant_id):
        with self._lock:
            self.calls.append('revoke')
            self.revoked.append(grant_id)

    def active_count(self, stage_run_id):
        with self._lock:
            return sum(1 for c in self.grants.values() if c.stage_run_id == stage_run_id and c.grant_id not in self.revoked)


class FakeEpochs:
    def __init__(self, value='epoch-0001'):
        self.value = value

    def current(self):
        return self.value


def _issuer(epoch='epoch-0001'):
    store, epochs = FakeGrantStore(), FakeEpochs(epoch)
    return GrantIssuer(store, epochs), store, epochs


def _issue(issuer, lease='lease-001', now=NOW, ttl=3600, stage=STAGE, op=OP, fp=FP):
    return issuer.issue(stage, op, fp, lease, ttl, now)


def _result(claims, **changes):
    payload = {'grant_id': claims.grant_id, 'stage_run_id': claims.stage_run_id, 'execution_generation': claims.execution_generation, 'recovery_epoch': claims.recovery_epoch}
    payload.update(changes)
    return payload


def _run_threads(count, target):
    barrier = threading.Barrier(count)
    outcomes = [None] * count

    def worker(index):
        barrier.wait()
        try:
            outcomes[index] = target(index)
        except Exception as exc:
            outcomes[index] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return outcomes


def test_first_issue_returns_claims_and_inserts():
    issuer, store, _ = _issuer()
    claims = _issue(issuer)
    assert isinstance(claims, GrantClaims)
    assert (claims.stage_run_id, claims.execution_generation, claims.recovery_epoch) == (STAGE, 1, 'epoch-0001')
    assert (claims.worker_lease_id, claims.allowed_operation, claims.input_fingerprint) == ('lease-001', OP, FP)
    assert (claims.issued_at, claims.expires_at) == ('2026-10-18T08:00:00Z', '2026-10-18T09:00:00Z')
    assert claims.grant_id and store.insert_log == [claims]


def test_claims_are_frozen():
    issuer, _, _ = _issuer()
    with pytest.raises(dataclasses.FrozenInstanceError):
        _issue(issuer).execution_generation = 9


def test_ttl_seconds_is_required():
    issuer, store, _ = _issuer()
    with pytest.raises(TypeError):
        issuer.issue(STAGE, OP, FP, 'lease-001', now=NOW)
    assert store.calls == []


def test_other_lease_with_live_grant_raises():
    issuer, store, _ = _issuer()
    first = _issue(issuer, 'lease-A')
    for now in (NOW, NOW + HOUR - timedelta(seconds=1)):
        with pytest.raises(ActiveGrantExistsError) as info:
            _issue(issuer, 'lease-B', now=now)
        assert (info.value.stage_run_id, info.value.grant_id) == (STAGE, first.grant_id)
    assert store.insert_log == [first] and store.revoked == []


def test_same_lease_same_request_is_idempotent():
    issuer, store, _ = _issuer()
    first = _issue(issuer)
    assert _issue(issuer, now=NOW + timedelta(minutes=10)) == first
    assert store.insert_log == [first] and store.revoked == []


@pytest.mark.parametrize(('op', 'fp'), [('write_output', FP), (OP, 'fp-other')])
def test_same_lease_different_request_raises(op, fp):
    issuer, store, _ = _issuer()
    first = _issue(issuer)
    with pytest.raises(ActiveGrantExistsError):
        _issue(issuer, op=op, fp=fp)
    assert store.insert_log == [first] and store.revoked == []


def test_eight_threads_issue_one_active_grant():
    issuer, store, _ = _issuer()
    outcomes = _run_threads(8, lambda i: _issue(issuer, f'lease-{i}'))
    granted = [o for o in outcomes if isinstance(o, GrantClaims)]
    refused = [o for o in outcomes if isinstance(o, ActiveGrantExistsError)]
    assert len(granted) == 1 and len(refused) == 7
    assert store.insert_log == granted and store.active_count(STAGE) == 1
    assert granted[0].execution_generation == 1
    assert {r.grant_id for r in refused} == {granted[0].grant_id}


def test_eight_issuers_sharing_one_store_issue_one_active_grant():
    store, epochs = FakeGrantStore(), FakeEpochs()
    issuers = [GrantIssuer(store, epochs) for _ in range(8)]
    outcomes = _run_threads(8, lambda i: _issue(issuers[i], f'lease-{i}'))
    assert sum(isinstance(o, GrantClaims) for o in outcomes) == 1
    assert sum(isinstance(o, ActiveGrantExistsError) for o in outcomes) == 7
    assert store.active_count(STAGE) == 1 and len(store.insert_log) == 1


def test_eight_threads_same_lease_share_one_grant():
    issuer, store, _ = _issuer()
    outcomes = _run_threads(8, lambda i: _issue(issuer))
    assert all(isinstance(o, GrantClaims) for o in outcomes)
    assert len({o.grant_id for o in outcomes}) == 1 and len(store.insert_log) == 1


def test_eight_threads_after_expiry_issue_one_new_generation():
    issuer, store, _ = _issuer()
    old = _issue(issuer, 'lease-old')
    later = NOW + 2 * HOUR
    outcomes = _run_threads(8, lambda i: _issue(issuer, f'lease-{i}', now=later))
    granted = [o for o in outcomes if isinstance(o, GrantClaims)]
    assert len(granted) == 1 and granted[0].execution_generation == 2
    assert sum(isinstance(o, ActiveGrantExistsError) for o in outcomes) == 7
    assert store.revoked == [old.grant_id] and store.active_count(STAGE) == 1


def test_reissue_after_expiry_increments_generation_and_revokes_old_grant():
    issuer, store, _ = _issuer()
    first = _issue(issuer, 'lease-A')
    second = _issue(issuer, 'lease-B', now=NOW + HOUR)
    third = _issue(issuer, 'lease-C', now=NOW + 3 * HOUR)
    assert [c.execution_generation for c in (first, second, third)] == [1, 2, 3]
    assert store.revoked == [first.grant_id, second.grant_id]
    assert len({c.grant_id for c in (first, second, third)}) == 3
    assert store.active_count(STAGE) == 1


def test_generation_continues_after_latest_grant_was_revoked():
    issuer, store, _ = _issuer()
    store.insert(GrantClaims('seed-grant', STAGE, 5, 'epoch-0001', 'lease-old', '2026-10-18T06:00:00Z', '2026-10-18T07:00:00Z', OP, FP))
    store.revoke('seed-grant')
    assert _issue(issuer).execution_generation == 6


def test_generation_is_per_stage():
    issuer, _, _ = _issuer()
    assert _issue(issuer, stage=STAGE).execution_generation == 1
    assert _issue(issuer, stage=OTHER_STAGE).execution_generation == 1


def test_unparsable_expiry_on_existing_grant_is_treated_as_expired():
    issuer, store, _ = _issuer()
    store.insert(GrantClaims('seed-grant', STAGE, 1, 'epoch-0001', 'lease-old', 'x', 'not-a-date', OP, FP))
    claims = _issue(issuer, 'lease-new')
    assert claims.execution_generation == 2 and store.revoked == ['seed-grant']


def test_epoch_is_read_from_port_at_issue_time():
    issuer, _, epochs = _issuer('epoch-0001')
    first = _issue(issuer, 'lease-A')
    epochs.value = 'epoch-0002'
    second = _issue(issuer, 'lease-B', now=NOW + HOUR)
    assert (first.recovery_epoch, second.recovery_epoch) == ('epoch-0001', 'epoch-0002')


def test_int_epoch_is_stringified():
    issuer, _, _ = _issuer(7)
    assert _issue(issuer).recovery_epoch == '7'


def test_same_lease_with_stale_epoch_gets_replacement_grant():
    issuer, store, epochs = _issuer('epoch-0001')
    first = _issue(issuer)
    epochs.value = 'epoch-0002'
    second = _issue(issuer, now=NOW + timedelta(minutes=10))
    assert (second.execution_generation, second.recovery_epoch) == (2, 'epoch-0002')
    assert store.revoked == [first.grant_id] and store.active_count(STAGE) == 1


def test_other_lease_live_grant_with_stale_epoch_still_raises():
    issuer, store, epochs = _issuer('epoch-0001')
    first = _issue(issuer, 'lease-A')
    epochs.value = 'epoch-0002'
    with pytest.raises(ActiveGrantExistsError):
        _issue(issuer, 'lease-B', now=NOW + timedelta(minutes=10))
    assert store.insert_log == [first] and store.revoked == []


def test_fencing_rejects_result_of_old_grant_after_reissue():  # TST-WF-INV-003
    issuer, _, epochs = _issuer()
    old = _issue(issuer, 'lease-A')
    new = _issue(issuer, 'lease-B', now=NOW + HOUR)
    check = NOW + HOUR + timedelta(minutes=5)
    stale = evaluate_result_fencing(old, new.execution_generation, epochs.current(), _result(old), FP, check, False)
    fresh = evaluate_result_fencing(new, new.execution_generation, epochs.current(), _result(new), FP, check, False)
    assert stale == FencingDecision(False, STALE_EXECUTION_GENERATION)
    assert fresh == FencingDecision(True, ACCEPTED)


def test_fencing_rejects_old_epoch_result_after_epoch_change():  # TST-WF-INV-016
    issuer, _, epochs = _issuer('epoch-0001')
    old = _issue(issuer, 'lease-A')
    epochs.value = 'epoch-0002'
    new = _issue(issuer, 'lease-B', now=NOW + HOUR)
    check = NOW + HOUR + timedelta(minutes=5)
    stale = evaluate_result_fencing(old, new.execution_generation, epochs.current(), _result(old), FP, check, False)
    fresh = evaluate_result_fencing(new, new.execution_generation, epochs.current(), _result(new), FP, check, False)
    assert stale == FencingDecision(False, STALE_RECOVERY_EPOCH)
    assert fresh == FencingDecision(True, ACCEPTED)


def test_revoked_grant_is_never_active_or_returned_again():
    issuer, store, _ = _issuer()
    seen = [_issue(issuer, f'lease-{step}', now=NOW + step * 2 * HOUR) for step in range(5)]
    revoked = set(store.revoked)
    assert [c.execution_generation for c in seen] == [1, 2, 3, 4, 5]
    assert len(revoked) == 4 and seen[-1].grant_id not in revoked
    assert all(c.grant_id in revoked for c in seen[:-1])
    assert store.active_grant(STAGE, NOW + 10 * HOUR) == seen[-1]


@pytest.mark.parametrize('kwargs', [
    {'ttl': 0}, {'ttl': -1}, {'ttl': True}, {'ttl': 1.5}, {'ttl': '60'}, {'ttl': None},
    {'now': datetime(2026, 10, 18, 8, 0)}, {'now': '2026-10-18T08:00:00Z'},
    {'stage': ''}, {'op': ''}, {'fp': ''}, {'lease': ''}, {'lease': None},
])
def test_invalid_arguments_raise_before_any_store_access(kwargs):
    issuer, store, _ = _issuer()
    with pytest.raises(ValueError):
        _issue(issuer, **kwargs)
    assert store.calls == []


@pytest.mark.parametrize('bad', [-1, True, '1', None])
def test_invalid_latest_generation_from_store_is_rejected(bad):
    issuer, store, _ = _issuer()
    store.latest_override = bad
    with pytest.raises(ValueError):
        _issue(issuer)
    assert store.insert_log == []


@pytest.mark.parametrize('bad', [None, True, 1.5, ''])
def test_invalid_epoch_from_port_is_rejected(bad):
    issuer, store, _ = _issuer(bad)
    with pytest.raises(ValueError):
        _issue(issuer)
    assert store.insert_log == []


def test_failed_insert_does_not_consume_generation_or_hold_lock():
    issuer, store, _ = _issuer()
    store.fail_next_insert = True
    with pytest.raises(RuntimeError):
        _issue(issuer)
    assert _issue(issuer).execution_generation == 1


def test_module_imports_only_stdlib_and_g03_fencing():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots, internal = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
            if (node.module or '').startswith('controlplane'):
                internal.add(node.module)
    assert roots <= {'__future__', 'datetime', 'threading', 'typing', 'uuid', 'controlplane'}
    assert internal == {'controlplane.domain.orchestration.fencing'}
