"""G-14: lý do dừng batch (CT-ORC-010; TST-E2E-006, TST-E2E-007).

coveredIds: CT-ORC-010, TST-E2E-006, TST-E2E-007
"""
import ast
import itertools
import pathlib
import pytest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.orchestration.batch_outcome import (
    BatchOutcome,
    decide_batch_outcome,
    plan_batch_transition,
)
from controlplane.domain.statemachine import (
    BatchState,
    ForbiddenTransitionError,
    TransitionResult,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'batch_outcome.py'
O = BatchOutcome


def _decide(ledger=0, target=5, active=0, eligible=0, blocked=0, fault=False):
    return decide_batch_outcome(ledger, target, active, eligible, blocked, fault)


def test_outcome_has_exactly_five_values():
    assert [o.value for o in BatchOutcome] == [
        'COMPLETED_TARGET',
        'COMPLETED_EXHAUSTED',
        'WAITING_CAPABILITY',
        'FAILED_SYSTEM',
        'CONTINUE',
    ]


@pytest.mark.parametrize('ledger,active,eligible,blocked', [
    (5, 0, 0, 0),
    (6, 0, 0, 0),
    (5, 2, 3, 1),
    (7, 1, 0, 2),
])
def test_target_reached_by_ledger_count(ledger, active, eligible, blocked):
    assert _decide(ledger=ledger, active=active, eligible=eligible, blocked=blocked) == O.COMPLETED_TARGET


def test_exhausted_only_when_no_candidate_and_no_active_reservation():
    assert _decide(ledger=2, eligible=0, active=0, blocked=0) == O.COMPLETED_EXHAUSTED


@pytest.mark.parametrize('active', [1, 2, 3])
def test_waiting_job_holding_reservation_is_never_exhausted(active):
    assert _decide(ledger=0, target=5, active=active, eligible=0, blocked=0) == O.CONTINUE
    assert _decide(ledger=0, target=5, active=active, eligible=0, blocked=1) == O.WAITING_CAPABILITY


def test_blocked_work_is_never_exhausted():
    assert _decide(blocked=2, eligible=0, active=0) == O.WAITING_CAPABILITY
    assert _decide(blocked=2, eligible=3) == O.CONTINUE


@pytest.mark.parametrize('eligible,active', list(itertools.product(range(1, 4), range(0, 3))))
def test_eligible_candidates_continue(eligible, active):
    assert _decide(eligible=eligible, active=active, blocked=0) == O.CONTINUE


def test_system_fault_wins_over_everything():
    assert _decide(ledger=5, fault=True) == O.FAILED_SYSTEM
    assert _decide(eligible=0, active=0, fault=True) == O.FAILED_SYSTEM
    assert _decide(blocked=3, fault=True) == O.FAILED_SYSTEM


def test_single_failed_final_job_keeps_batch_running():
    # Tr??c l?i:
    r1 = _decide(ledger=2, active=3, eligible=4)
    assert r1 == O.CONTINUE
    assert r1 != O.FAILED_SYSTEM
    # Sau khi job FAILED_FINAL nh? su?t:
    r2 = _decide(ledger=2, active=2, eligible=4)
    assert r2 == O.CONTINUE
    assert r2 != O.FAILED_SYSTEM
    # Th?m ca h?t candidate:
    r3 = _decide(ledger=2, active=0, eligible=0, blocked=0)
    assert r3 == O.COMPLETED_EXHAUSTED
    assert r3 != O.FAILED_SYSTEM


def test_failed_system_only_with_fault_flag_and_exact_exhausted_rule():
    target = 3
    for ledger, active, eligible, blocked in itertools.product(range(4), repeat=4):
        outcome = _decide(ledger=ledger, target=target, active=active, eligible=eligible, blocked=blocked, fault=False)
        assert outcome != O.FAILED_SYSTEM
        if ledger < 3 and active == 0 and eligible == 0 and blocked == 0:
            assert outcome == O.COMPLETED_EXHAUSTED
        else:
            assert outcome != O.COMPLETED_EXHAUSTED
        if ledger >= 3:
            assert outcome == O.COMPLETED_TARGET
        else:
            assert outcome != O.COMPLETED_TARGET


@pytest.mark.parametrize('field', ['ledger_count', 'target', 'active_reservations', 'eligible_remaining', 'capability_blocked_work'])
@pytest.mark.parametrize('bad', [-1, True, False, 1.5, '1', None])
def test_counts_are_validated(field, bad):
    kwargs = {
        'ledger_count': 0,
        'target': 5,
        'active_reservations': 0,
        'eligible_remaining': 0,
        'capability_blocked_work': 0,
        'system_fault': False,
    }
    kwargs[field] = bad
    with pytest.raises(ValueError):
        decide_batch_outcome(**kwargs)


@pytest.mark.parametrize('bad', [0, 1, None, 'x'])
def test_system_fault_must_be_bool(bad):
    with pytest.raises(TypeError):
        _decide(fault=bad)


def test_decide_is_deterministic():
    args = (2, 5, 1, 2, 0, False)
    assert decide_batch_outcome(*args) == decide_batch_outcome(*args)


def _plan(state, outcome, rev=7, expected=7):
    return plan_batch_transition(
        current_state=state,
        current_revision=rev,
        expected_revision=expected,
        outcome=outcome,
    )


def test_continue_moves_waiting_capability_back_to_running():
    assert _plan(BatchState.WAITING_CAPABILITY, O.CONTINUE) == TransitionResult(state=BatchState.RUNNING, revision=8)


def test_waiting_capability_outcome_moves_running_to_waiting():
    assert _plan(BatchState.RUNNING, O.WAITING_CAPABILITY) == TransitionResult(state=BatchState.WAITING_CAPABILITY, revision=8)


@pytest.mark.parametrize('outcome,expected_state', [
    (O.COMPLETED_TARGET, BatchState.COMPLETED_TARGET),
    (O.COMPLETED_EXHAUSTED, BatchState.COMPLETED_EXHAUSTED),
    (O.FAILED_SYSTEM, BatchState.FAILED_SYSTEM),
])
@pytest.mark.parametrize('current_state', [BatchState.RUNNING, BatchState.WAITING_CAPABILITY])
def test_terminal_transitions(outcome, expected_state, current_state):
    assert _plan(current_state, outcome) == TransitionResult(state=expected_state, revision=8)


def test_noop_when_batch_already_in_target_state():
    assert _plan(BatchState.RUNNING, O.CONTINUE) is None
    assert _plan(BatchState.WAITING_CAPABILITY, O.WAITING_CAPABILITY) is None
    assert _plan(BatchState.RUNNING, O.CONTINUE, rev=7, expected=3) is None


@pytest.mark.parametrize('state', [
    BatchState.CREATED,
    BatchState.COMPLETED_TARGET,
    BatchState.COMPLETED_EXHAUSTED,
    BatchState.FAILED_SYSTEM,
])
@pytest.mark.parametrize('outcome', list(BatchOutcome))
def test_forbidden_transitions(state, outcome):
    with pytest.raises(ForbiddenTransitionError):
        _plan(state, outcome)


def test_revision_conflict():
    with pytest.raises(RevisionConflictError):
        _plan(BatchState.RUNNING, O.WAITING_CAPABILITY, rev=7, expected=6)


@pytest.mark.parametrize('bad', ['CONTINUE', None])
def test_outcome_must_be_batch_outcome(bad):
    with pytest.raises(TypeError):
        _plan(BatchState.RUNNING, bad)


def test_waiting_job_keeps_batch_running_end_to_end():
    outcome = decide_batch_outcome(1, 5, 1, 0, 0, False)
    assert outcome == O.CONTINUE
    assert _plan(BatchState.RUNNING, outcome) is None


def test_module_imports_only_stdlib_and_controlplane_domain():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots, internal = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
            if (node.module or '').startswith('controlplane'):
                internal.add(node.module)
    assert roots <= {'__future__', 'enum', 'controlplane'}
    assert internal == {'controlplane.domain.statemachine'}
