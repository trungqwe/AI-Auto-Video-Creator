"""G-09: cổng điều kiện completion (CT-ORC-008 bước 1–2, CT-ORC-012, INV-010).

coveredIds: CT-ORC-008, CT-ORC-012, INV-010, TST-E2E-INV-009 (phần G)
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import inspect
import json
import pathlib

import pytest

from controlplane.domain.orchestration import ReservationState
from controlplane.domain.orchestration import completion_gate as gate
from controlplane.domain.orchestration.completion_gate import GateAction, GateDecision, ReservationBinding, check_completion
from controlplane.domain.orchestration.fencing import ACCEPTED, GRANT_EXPIRED, STALE_EXECUTION_GENERATION, STALE_RECOVERY_EPOCH, FencingDecision
from controlplane.domain.statemachine import JobState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'completion_gate.py'
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-c-i-completion' / 'payloads.json').read_text(encoding='utf-8'))
REQUEST = 'CommitVideoCompletionRequest'
LEDGER = 'CompletionLedgerEntry'
READY = JobState.READY_FOR_COMPLETION
FENCING_OK = FencingDecision(True, ACCEPTED)
REJECT = GateAction.REJECT
INVALID_CASES = FIXTURE['entities'][REQUEST]['invalid']
_UNSET = object()


def valid_request():
    return copy.deepcopy(FIXTURE['entities'][REQUEST]['valid'][0])


def ledger_for(request):
    ledger = copy.deepcopy(FIXTURE['entities'][LEDGER]['valid'][0])
    for field in gate.LEDGER_COMPARED_FIELDS:
        ledger[field] = copy.deepcopy(request[field])
    return ledger


def reservation_for(request, **override):
    fields = {'reservation_id': request['variant_reservation_id'], 'job_id': request['video_job_id'], 'output_sha256': request['output_sha256'], 'state': ReservationState.ACTIVE}
    return ReservationBinding(**(fields | override))


def run(request=_UNSET, *, job_state=READY, fencing=FENCING_OK, reservation=_UNSET, revision=_UNSET, ledger=None, conflict=False):
    base = valid_request()
    request = base if request is _UNSET else request
    if reservation is _UNSET:
        reservation = reservation_for(base)
    if revision is _UNSET:
        revision = base['expected_variant_registry_revision']
    return check_completion(job_state, request, fencing, reservation, revision, ledger, variant_conflict_confirmed=conflict)


def test_valid_fixture_request_proceeds_only_when_every_gate_passes():
    decision = run()
    assert decision == GateDecision('PROCEED', GateAction.PROCEED)
    assert decision.ledger is None


@pytest.mark.parametrize('case', INVALID_CASES, ids=[case['case'] for case in INVALID_CASES])
def test_invalid_fixture_payload_is_invalid_request(case):
    assert run(case['payload']) == GateDecision('INVALID_REQUEST', REJECT)


@pytest.mark.parametrize('bad', [None, [], 'text', 1, True])
def test_non_mapping_request_is_invalid_request(bad):
    assert run(bad) == GateDecision('INVALID_REQUEST', REJECT)


def test_invalid_request_wins_over_every_later_check():
    request = valid_request()
    del request['output_sha256']
    decision = run(request, job_state=JobState.ACTIVE, fencing=FencingDecision(False, STALE_RECOVERY_EPOCH), reservation=None, revision=99, ledger=ledger_for(valid_request()), conflict=True)
    assert decision == GateDecision('INVALID_REQUEST', REJECT)


def test_compared_fields_exist_in_both_request_and_ledger_fixture():
    ledger = FIXTURE['entities'][LEDGER]['valid'][0]
    assert len(gate.LEDGER_COMPARED_FIELDS) == 9
    assert set(gate.LEDGER_COMPARED_FIELDS) <= set(valid_request()) & set(ledger)


def test_same_input_ledger_returns_existing_ledger():
    request = valid_request()
    ledger = ledger_for(request)
    decision = run(request, ledger=ledger)
    assert decision.code == 'ALREADY_COMPLETED'
    assert decision.action == GateAction.RETURN_EXISTING_LEDGER
    assert decision.ledger is ledger


def _different(field):
    if field == 'media_usage_manifest':
        return [{'media_asset_id': 'other-asset', 'role': 'thumbnail'}]
    return 'different-' + field


@pytest.mark.parametrize('field', gate.LEDGER_COMPARED_FIELDS)
def test_ledger_with_different_input_is_conflict(field):
    request = valid_request()
    ledger = ledger_for(request)
    ledger[field] = _different(field)
    assert run(request, ledger=ledger) == GateDecision('CONFLICT', REJECT)


@pytest.mark.parametrize('field', gate.LEDGER_COMPARED_FIELDS)
def test_ledger_missing_a_compared_field_is_conflict(field):
    request = valid_request()
    ledger = ledger_for(request)
    del ledger[field]
    assert run(request, ledger=ledger) == GateDecision('CONFLICT', REJECT)


def test_repeated_completion_never_proceeds_or_creates_second_ledger():
    request = valid_request()
    assert run(request, ledger=ledger_for(request)).action != GateAction.PROCEED
    other = ledger_for(request)
    other['output_sha256'] = 'f' * 64
    assert run(request, ledger=other).action != GateAction.PROCEED


def test_existing_ledger_wins_over_job_state_fencing_and_registry():
    request = valid_request()
    decision = run(request, job_state=JobState.COMPLETED, fencing=FencingDecision(False, STALE_RECOVERY_EPOCH), reservation=None, revision=99, ledger=ledger_for(request), conflict=True)
    assert decision.code == 'ALREADY_COMPLETED'


@pytest.mark.parametrize('bad', ['ledger', [], 1, True])
def test_non_mapping_existing_ledger_raises_type_error(bad):
    with pytest.raises(TypeError):
        run(ledger=bad)


NOT_READY_STATES = [state for state in JobState if state != READY]


@pytest.mark.parametrize('state', NOT_READY_STATES)
def test_job_not_ready_state_is_rejected(state):
    assert run(job_state=state) == GateDecision('JOB_NOT_READY', REJECT)


@pytest.mark.parametrize('bad', [None, 'READY', 'unknown', 5])
def test_unknown_job_state_is_not_ready(bad):
    assert run(job_state=bad) == GateDecision('JOB_NOT_READY', REJECT)


def test_active_job_is_never_completed_directly():
    assert run(job_state=JobState.ACTIVE).action != GateAction.PROCEED


@pytest.mark.parametrize('code', [STALE_RECOVERY_EPOCH, STALE_EXECUTION_GENERATION, GRANT_EXPIRED])
def test_fencing_rejection_returns_the_fencing_code(code):
    assert run(fencing=FencingDecision(False, code)) == GateDecision(code, REJECT)


def test_job_state_is_checked_before_fencing():
    decision = run(job_state=JobState.ACTIVE, fencing=FencingDecision(False, STALE_RECOVERY_EPOCH))
    assert decision == GateDecision('JOB_NOT_READY', REJECT)


@pytest.mark.parametrize('bad', [None, True, {'accepted': True}])
def test_non_fencing_decision_raises_type_error(bad):
    with pytest.raises(TypeError):
        run(fencing=bad)


@pytest.mark.parametrize('blank', ['', ' ', '\t\n'])
def test_blank_cloud_verification_ref_is_missing(blank):
    request = valid_request()
    request['cloud_location_verification_ref'] = blank
    assert run(request) == GateDecision('CLOUD_VERIFICATION_MISSING', REJECT)


def test_absent_cloud_verification_ref_is_invalid_request_and_never_proceeds():
    request = valid_request()
    del request['cloud_location_verification_ref']
    assert run(request) == GateDecision('INVALID_REQUEST', REJECT)


def test_qc_passed_but_not_cloud_verified_never_proceeds():
    request = valid_request()
    request['cloud_location_verification_ref'] = ''
    decision = run(request, job_state=READY)
    assert decision.action != GateAction.PROCEED
    assert decision.code == 'CLOUD_VERIFICATION_MISSING'


def test_cloud_verification_is_checked_after_fencing_and_before_reservation():
    request = valid_request()
    request['cloud_location_verification_ref'] = ''
    assert run(request, fencing=FencingDecision(False, GRANT_EXPIRED)).code == GRANT_EXPIRED
    assert run(request, reservation=None).code == 'CLOUD_VERIFICATION_MISSING'


@pytest.mark.parametrize(
    'override',
    [{'state': ReservationState.CONVERTED}, {'state': ReservationState.RELEASED}, {'job_id': 'other-job'}, {'output_sha256': 'f' * 64}, {'reservation_id': 'other-reservation'}],
    ids=['converted', 'released', 'wrong_job', 'wrong_hash', 'wrong_reservation_id'],
)
def test_reservation_not_active_or_not_bound_is_invalid(override):
    request = valid_request()
    decision = run(request, reservation=reservation_for(request, **override))
    assert decision == GateDecision('RESERVATION_INVALID', REJECT)


@pytest.mark.parametrize('bad', [None, 'ACTIVE', {'state': 'ACTIVE'}])
def test_missing_or_untyped_reservation_is_invalid(bad):
    assert run(reservation=bad) == GateDecision('RESERVATION_INVALID', REJECT)


def test_reservation_is_checked_before_registry_revision():
    request = valid_request()
    decision = run(request, reservation=reservation_for(request, state=ReservationState.CONVERTED), revision=99)
    assert decision.code == 'RESERVATION_INVALID'


@pytest.mark.parametrize('current', [11, 13, 0, None, '12', True, 12.0])
def test_registry_revision_mismatch_is_stale_and_keeps_waiting(current):
    decision = run(revision=current)
    assert decision == GateDecision('VARIANT_REGISTRY_STALE', GateAction.KEEP_WAITING)
    assert decision.ledger is None


def test_stale_registry_never_proceeds_even_with_confirmed_conflict():
    decision = run(revision=13, conflict=True)
    assert decision == GateDecision('VARIANT_REGISTRY_STALE', GateAction.KEEP_WAITING)


def test_confirmed_conflict_at_matching_revision_fails_job_and_releases():
    assert run(conflict=True) == GateDecision('VARIANT_CONFLICT_FINAL', GateAction.FAIL_JOB_RELEASE)


@pytest.mark.parametrize('bad', [1, 'yes', None])
def test_conflict_flag_must_be_bool(bad):
    with pytest.raises(TypeError):
        run(conflict=bad)


def test_inputs_are_not_mutated():
    request = valid_request()
    ledger = ledger_for(request)
    before = (copy.deepcopy(request), copy.deepcopy(ledger))
    run(request, ledger=ledger)
    run(request, revision=13)
    assert (request, ledger) == before


def test_decision_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        run().code = 'X'


def test_signature_has_no_write_port_and_conflict_flag_is_keyword_only():
    parameters = inspect.signature(check_completion).parameters
    assert list(parameters) == ['job_state', 'request', 'fencing', 'reservation', 'current_registry_revision', 'existing_ledger', 'variant_conflict_confirmed']
    flag = parameters['variant_conflict_confirmed']
    assert flag.kind is inspect.Parameter.KEYWORD_ONLY and flag.default is False


def test_gate_actions_are_exactly_the_five_known_values():
    assert [action.value for action in GateAction] == ['PROCEED', 'REJECT', 'RETURN_EXISTING_LEDGER', 'KEEP_WAITING', 'FAIL_JOB_RELEASE']


def test_module_is_pure_and_imports_only_domain():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add(node.module.split('.')[0])
            if node.module.startswith('controlplane'):
                assert node.module.startswith('controlplane.domain')
    assert roots <= {'__future__', 'collections', 'dataclasses', 'enum', 'controlplane'}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert attributes & {'now', 'utcnow', 'today', 'open', 'read_text', 'write_text'} == set()
