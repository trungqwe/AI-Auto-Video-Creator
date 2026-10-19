"""G-05: chính sách retry theo operation receipt (CT-WF-005, CT-STATE-011).

coveredIds: CT-WF-005, CT-STATE-011
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from controlplane.domain.orchestration import operation_receipt
from controlplane.domain.orchestration.operation_receipt import (
    RetryDecision,
    apply_reconcile,
    decide_retry,
)
from controlplane.domain.statemachine import (
    ForbiddenTransitionError,
    OperationState,
    ReconciliationEvidence,
    TransitionResult,
    transition_operation,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'operation_receipt.py'
FP = 'fp-001'
OTHER_FP = 'fp-002'
S = OperationState
D = RetryDecision

SAME_FP_CASES = [
    (S.PREPARED, True, D.WAIT_IN_FLIGHT),
    (S.PREPARED, False, D.WAIT_IN_FLIGHT),
    (S.STARTED, True, D.WAIT_IN_FLIGHT),
    (S.STARTED, False, D.WAIT_IN_FLIGHT),
    (S.SUCCEEDED, True, D.RETURN_PREVIOUS_OUTPUT),
    (S.SUCCEEDED, False, D.RETURN_PREVIOUS_OUTPUT),
    (S.OUTCOME_UNKNOWN, True, D.RECONCILE_FIRST),
    (S.OUTCOME_UNKNOWN, False, D.RECONCILE_FIRST),
    (S.FAILED, True, D.NEW_ATTEMPT_SAME_KEY),
    (S.FAILED, False, D.FAIL_FINAL),
]


@pytest.mark.parametrize(('state', 'retryable', 'expected'), SAME_FP_CASES, ids=[f'{state.value}-retryable={retryable}' for state, retryable, _ in SAME_FP_CASES])
def test_same_fingerprint_table(state, retryable, expected):
    assert decide_retry(state, FP, FP, retryable) == expected


@pytest.mark.parametrize('retryable', [True, False])
@pytest.mark.parametrize('fp', [None, OTHER_FP])
def test_no_receipt_executes(retryable, fp):
    assert decide_retry(None, fp, FP, retryable) is D.EXECUTE


@pytest.mark.parametrize('state', list(S))
@pytest.mark.parametrize('retryable', [True, False])
def test_different_fingerprint_requires_new_operation_key(state, retryable):
    assert decide_retry(state, FP, OTHER_FP, retryable) is D.NEW_OPERATION_KEY_REQUIRED


def test_receipt_without_fingerprint_fails_closed():
    assert decide_retry(S.SUCCEEDED, None, FP, True) is D.NEW_OPERATION_KEY_REQUIRED


@pytest.mark.parametrize('retryable', [True, False])
@pytest.mark.parametrize('receipt_fp', [FP, OTHER_FP, None])
def test_outcome_unknown_never_executes(retryable, receipt_fp):
    decision = decide_retry(S.OUTCOME_UNKNOWN, receipt_fp, FP, retryable)
    assert decision is not D.EXECUTE
    if receipt_fp == FP:
        assert decision is D.RECONCILE_FIRST


def test_unknown_state_raises_value_error():
    with pytest.raises(ValueError):
        decide_retry('BOGUS', FP, FP, True)
    with pytest.raises(ValueError):
        decide_retry('BOGUS', FP, OTHER_FP, True)


def test_state_accepts_string_value():
    assert decide_retry('OUTCOME_UNKNOWN', FP, FP, False) is D.RECONCILE_FIRST


def test_decision_members_are_exactly_seven():
    assert {m.value for m in RetryDecision} == {
        'EXECUTE',
        'NEW_OPERATION_KEY_REQUIRED',
        'RETURN_PREVIOUS_OUTPUT',
        'RECONCILE_FIRST',
        'NEW_ATTEMPT_SAME_KEY',
        'FAIL_FINAL',
        'WAIT_IN_FLIGHT',
    }


EV = 'evidence-ref-001'
REV = 3


@pytest.mark.parametrize('outcome', [S.SUCCEEDED, S.FAILED])
def test_reconcile_with_evidence_accepted(outcome):
    assert apply_reconcile(S.OUTCOME_UNKNOWN, REV, EV, outcome) == TransitionResult(state=outcome, revision=REV + 1)


@pytest.mark.parametrize('outcome', [S.SUCCEEDED, S.FAILED])
@pytest.mark.parametrize('evidence_ref', [None, '', '   '])
def test_reconcile_without_evidence_rejected(outcome, evidence_ref):
    with pytest.raises(ForbiddenTransitionError) as exc:
        apply_reconcile(S.OUTCOME_UNKNOWN, REV, evidence_ref, outcome)
    assert exc.value.code == 'FORBIDDEN_TRANSITION'
    assert exc.value.aggregate_type == 'operation'
    assert exc.value.current_state is S.OUTCOME_UNKNOWN
    assert exc.value.requested_next_state is outcome
    assert exc.value.current_revision == REV


@pytest.mark.parametrize('state', [S.PREPARED, S.STARTED, S.SUCCEEDED, S.FAILED])
def test_reconcile_only_from_outcome_unknown(state):
    with pytest.raises(ForbiddenTransitionError):
        apply_reconcile(state, REV, EV, S.SUCCEEDED)


@pytest.mark.parametrize('outcome', [S.PREPARED, S.STARTED, S.OUTCOME_UNKNOWN])
def test_reconcile_rejects_non_terminal_outcome(outcome):
    with pytest.raises(ForbiddenTransitionError):
        apply_reconcile(S.OUTCOME_UNKNOWN, REV, EV, outcome)


@pytest.mark.parametrize('state', [S.SUCCEEDED, S.FAILED])
def test_terminal_never_reopens_started(state):
    with pytest.raises(ForbiddenTransitionError):
        transition_operation(current_state=state, current_revision=REV, expected_revision=REV, requested_state=S.STARTED)
    with pytest.raises(ForbiddenTransitionError):
        apply_reconcile(state, REV, EV, S.STARTED)


def test_reconcile_delegates_to_transition_operation(monkeypatch):
    calls = []
    sentinel = object()

    def fake(**kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(operation_receipt, 'transition_operation', fake)
    result = apply_reconcile(S.OUTCOME_UNKNOWN, REV, EV, S.SUCCEEDED)
    assert result is sentinel
    assert calls == [
        dict(
            current_state=S.OUTCOME_UNKNOWN,
            current_revision=REV,
            expected_revision=REV,
            requested_state=S.SUCCEEDED,
            reconciliation_evidence=ReconciliationEvidence(EV),
        )
    ]


def test_reconcile_without_evidence_does_not_call_transition(monkeypatch):
    def fake(**kwargs):
        raise AssertionError('transition_operation should not be called')

    monkeypatch.setattr(operation_receipt, 'transition_operation', fake)
    with pytest.raises(ForbiddenTransitionError):
        apply_reconcile(S.OUTCOME_UNKNOWN, REV, None, S.SUCCEEDED)


def test_timeout_after_side_effect_is_never_blindly_retried():
    t = transition_operation(current_state=S.STARTED, current_revision=1, expected_revision=1, requested_state=S.OUTCOME_UNKNOWN)
    assert decide_retry(t.state, FP, FP, True) is D.RECONCILE_FIRST
    r = apply_reconcile(t.state, t.revision, EV, S.SUCCEEDED)
    assert r.state is S.SUCCEEDED
    assert decide_retry(r.state, FP, FP, True) is D.RETURN_PREVIOUS_OUTPUT


def test_module_imports_only_stdlib_and_statemachine():
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
