"""G-03: fencing generation và recovery epoch (CT-WF-004, CT-WF-006).

coveredIds: CT-WF-004, CT-WF-006, INV-003, INV-016, TST-WF-INV-003, TST-WF-INV-016
"""
from __future__ import annotations

import ast
import copy
import dataclasses
from datetime import datetime, timedelta, timezone
import json
import pathlib

import pytest

from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.orchestration.fencing import (
    ACCEPTED,
    GRANT_EXPIRED,
    GRANT_MISMATCH,
    INPUT_FINGERPRINT_MISMATCH,
    INVALID_EXPIRY,
    OPERATION_CONFLICT,
    STALE_EXECUTION_GENERATION,
    STALE_RECOVERY_EPOCH,
    FencingDecision,
    GrantClaims,
    claims_from_execution_grant,
    evaluate_result_fencing,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-activity-execution' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'fencing.py'
NOW = datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)
EXPIRES = '2026-10-18T09:00:00Z'
FP = 'fp-001'
GRANT_ID = '00000000-0000-4000-8000-000000000065'
STAGE = '00000000-0000-4000-8000-000000000062'
HOUR = timedelta(hours=1)
_DEFAULT_RESULT = object()


def _result(**changes):
    raw = json.loads(FIXTURE.read_text(encoding='utf-8'))
    payload = copy.deepcopy(raw['entities']['ActivityResult']['valid'][0])
    payload.update(changes)
    return payload


def _claims(**changes):
    base = {
        'grant_id': GRANT_ID,
        'stage_run_id': STAGE,
        'execution_generation': 3,
        'recovery_epoch': 'epoch-0001',
        'worker_lease_id': 'lease-001',
        'issued_at': '2026-10-18T07:00:00Z',
        'expires_at': EXPIRES,
        'allowed_operation': 'commit_voice_track',
        'input_fingerprint': FP,
    }
    base.update(changes)
    return GrantClaims(**base)


def _evaluate(claims=None, generation=3, epoch='epoch-0001', result=_DEFAULT_RESULT, fingerprint=FP, now=NOW, conflict=False):
    return evaluate_result_fencing(
        claims or _claims(),
        generation,
        epoch,
        _result() if result is _DEFAULT_RESULT else result,
        fingerprint,
        now,
        conflict,
    )


CASES = [
    ('valid', {}, True, ACCEPTED),
    ('one_second_before_expiry', {'now': NOW + HOUR - timedelta(seconds=1)}, True, ACCEPTED),
    ('result_generation_old', {'result': _result(execution_generation=2)}, False, STALE_EXECUTION_GENERATION),
    ('current_generation_ahead', {'generation': 4}, False, STALE_EXECUTION_GENERATION),
    ('result_generation_string', {'result': _result(execution_generation='3')}, False, STALE_EXECUTION_GENERATION),
    ('claims_generation_old', {'claims': _claims(execution_generation=2)}, False, STALE_EXECUTION_GENERATION),
    ('current_epoch_new', {'epoch': 'epoch-0002'}, False, STALE_RECOVERY_EPOCH),
    ('result_epoch_old', {'result': _result(recovery_epoch='epoch-0000')}, False, STALE_RECOVERY_EPOCH),
    ('claims_epoch_old', {'claims': _claims(recovery_epoch='epoch-0000')}, False, STALE_RECOVERY_EPOCH),
    ('result_empty', {'result': {}}, False, STALE_RECOVERY_EPOCH),
    ('grant_id_mismatch', {'result': _result(grant_id='other')}, False, GRANT_MISMATCH),
    ('stage_run_mismatch', {'result': _result(stage_run_id='other')}, False, GRANT_MISMATCH),
    ('expired_at_boundary', {'now': NOW + HOUR}, False, GRANT_EXPIRED),
    ('expired_after', {'now': NOW + 2 * HOUR}, False, GRANT_EXPIRED),
    ('expiry_garbage', {'claims': _claims(expires_at='not-a-date')}, False, INVALID_EXPIRY),
    ('expiry_naive', {'claims': _claims(expires_at='2026-10-18T09:00:00')}, False, INVALID_EXPIRY),
    ('expiry_none', {'claims': _claims(expires_at=None)}, False, INVALID_EXPIRY),
    ('expiry_empty', {'claims': _claims(expires_at='')}, False, INVALID_EXPIRY),
    ('now_naive', {'now': datetime(2026, 10, 18, 8, 0)}, False, INVALID_EXPIRY),
    ('fingerprint_mismatch', {'fingerprint': 'fp-other'}, False, INPUT_FINGERPRINT_MISMATCH),
    ('conflicting_receipt', {'conflict': True}, False, OPERATION_CONFLICT),
]


CASES += [
    ('epoch_beats_all', {'epoch': 'epoch-0002', 'generation': 9, 'result': _result(grant_id='other'), 'fingerprint': 'x', 'conflict': True, 'now': NOW + 2 * HOUR}, False, STALE_RECOVERY_EPOCH),
    ('generation_beats_grant_mismatch', {'result': _result(execution_generation=2, grant_id='other')}, False, STALE_EXECUTION_GENERATION),
    ('grant_mismatch_beats_expired', {'result': _result(grant_id='other'), 'now': NOW + 2 * HOUR}, False, GRANT_MISMATCH),
    ('expired_beats_fingerprint', {'now': NOW + 2 * HOUR, 'fingerprint': 'x'}, False, GRANT_EXPIRED),
    ('invalid_expiry_beats_fingerprint', {'claims': _claims(expires_at='bad'), 'fingerprint': 'x'}, False, INVALID_EXPIRY),
    ('fingerprint_beats_conflict', {'fingerprint': 'x', 'conflict': True}, False, INPUT_FINGERPRINT_MISMATCH),
]


@pytest.mark.parametrize(('kwargs', 'accepted', 'code'), [pytest.param(k, a, c, id=i) for i, k, a, c in CASES])
def test_decision_table(kwargs, accepted, code):
    assert _evaluate(**kwargs) == FencingDecision(accepted, code)


def test_restore_same_generation_old_epoch_rejected():  # TST-WF-INV-016
    decision = _evaluate(generation=3, epoch='epoch-0002', result=_result(execution_generation=3, recovery_epoch='epoch-0001'))
    assert decision == FencingDecision(False, STALE_RECOVERY_EPOCH)


def test_stale_generation_rejected():  # TST-WF-INV-003
    assert _evaluate(generation=4, result=_result(execution_generation=3)) == FencingDecision(False, STALE_EXECUTION_GENERATION)


@pytest.mark.parametrize('current_epoch', [1, '1'])
def test_int_epoch_on_grant_matches_string_epoch_on_result(current_epoch):
    grant = ExecutionGrant('ws-1', GRANT_ID, 'job-1', STAGE, 3, 1)
    claims = claims_from_execution_grant(grant, worker_lease_id='lease-001', issued_at='2026-10-18T07:00:00Z', expires_at=EXPIRES, allowed_operation='commit_voice_track', input_fingerprint=FP)
    assert claims.recovery_epoch == '1' and isinstance(claims.recovery_epoch, str)
    decision = _evaluate(claims=claims, epoch=current_epoch, result=_result(recovery_epoch='1'))
    assert decision == FencingDecision(True, ACCEPTED)


def test_claims_from_execution_grant_maps_fields():
    grant = ExecutionGrant('ws-1', GRANT_ID, 'job-1', STAGE, 3, 7)
    claims = claims_from_execution_grant(grant, worker_lease_id='lease-9', issued_at='2026-10-18T07:00:00Z', expires_at=EXPIRES, allowed_operation='write_output', input_fingerprint='fp-9')
    assert claims == GrantClaims(GRANT_ID, STAGE, 3, '7', 'lease-9', '2026-10-18T07:00:00Z', EXPIRES, 'write_output', 'fp-9')


def test_dataclasses_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        _claims().execution_generation = 9
    with pytest.raises(dataclasses.FrozenInstanceError):
        FencingDecision(True, ACCEPTED).accepted = False


@pytest.mark.parametrize('bad', [None, '', 'x', 123, '2026-13-45T99:00:00Z', '2026-10-18'])
def test_invalid_expiry_never_raises(bad):
    assert _evaluate(claims=_claims(expires_at=bad)) == FencingDecision(False, INVALID_EXPIRY)


@pytest.mark.parametrize('bad_result', [None, 'text', 42, []])
def test_non_mapping_result_rejected_without_raising(bad_result):
    assert _evaluate(result=bad_result).accepted is False


def test_evaluation_is_pure():
    claims, result = _claims(), _result()
    claims_before, result_before = copy.deepcopy(claims), copy.deepcopy(result)
    evaluate_result_fencing(claims, 3, 'epoch-0001', result, FP, NOW, False)
    assert claims == claims_before and result == result_before


def test_module_imports_only_stdlib_and_p6_domain():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots, internal = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
            if (node.module or '').startswith('controlplane'):
                internal.add(node.module)
    assert roots <= {'__future__', 'collections', 'dataclasses', 'datetime', 'controlplane'}
    assert internal == {'controlplane.domain.orchestration'}
