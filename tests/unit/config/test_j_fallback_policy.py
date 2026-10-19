"""J-14: Chính sách fallback có kiểm soát (CT-AI-ROUTE-002).

coveredIds: CT-AI-ROUTE-002
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import itertools

import pytest

from controlplane.application.config_security import fallback_policy
from controlplane.application.config_security.fallback_policy import (
    AUTH,
    CONTINUE_WITHOUT_AI,
    NEW_OUTPUT_REVISION_REQUIRED,
    PROVENANCE_REQUIRED,
    RATE_LIMIT,
    SWITCH,
    TIMEOUT,
    UNKNOWN,
    WAIT,
    FallbackIntentPolicy,
    FallbackOutcome,
    backoff_seconds,
    classify_failure,
    decide_fallback,
)
from controlplane.config.adapter import (
    ProviderAuthenticationError,
    ProviderHTTPError,
    ProviderRateLimitExceededError,
    ProviderTimeoutError,
)
from controlplane.config.models import RateLimitError
from controlplane.domain.config_security.route_binding import ProviderRouteDecision


class _Coded(Exception):
    def __init__(self, code: object) -> None:
        super().__init__(f"coded: {code}")
        self.code = code


def test_module_docstring_declares_covered_ids():
    assert 'coveredIds: CT-AI-ROUTE-002' in (__doc__ or '')


def test_source_does_not_mention_router_or_http_adapter():
    src = inspect.getsource(fallback_policy)
    assert 'ProviderRouter' not in src and 'NineRouterHTTPAdapter' not in src


def test_source_imports_only_exception_classes_and_pure_modules():
    src = inspect.getsource(fallback_policy)
    tree = ast.parse(src)
    forbidden_roots = {'time', 'random', 'datetime', 'socket', 'urllib', 'controlplane.config.router'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split('.')[0]
                assert root not in forbidden_roots
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_roots
            if node.module == 'controlplane.config.adapter':
                assert {alias.name for alias in node.names} == {
                    'ProviderAuthenticationError',
                    'ProviderTimeoutError',
                }
            elif node.module == 'controlplane.config.models':
                assert {alias.name for alias in node.names} == {'RateLimitError'}
            elif node.module and node.module.startswith('controlplane.config'):
                pytest.fail(f'forbidden import from {node.module}')


@pytest.mark.parametrize(
    ('error', 'kind'),
    [
        (RateLimitError(), RATE_LIMIT),
        (RateLimitError(code=500), RATE_LIMIT),
        (ProviderRateLimitExceededError(), RATE_LIMIT),
        (_Coded(429), RATE_LIMIT),
        (_Coded(500), UNKNOWN),
        (TimeoutError(), TIMEOUT),
        (ProviderTimeoutError(), TIMEOUT),
        (ProviderAuthenticationError(), AUTH),
        (ProviderHTTPError(), UNKNOWN),
        (ValueError(), UNKNOWN),
        (ValueError('429'), UNKNOWN),
        (_Coded('429'), UNKNOWN),
    ],
)
def test_classify_failure_with_real_exception_classes(error: BaseException, kind: str):
    assert classify_failure(error) == kind


def test_classify_failure_non_exception_object_is_unknown():
    assert classify_failure(object()) == UNKNOWN


def _decision(fallback_order: Sequence[object] = ('b', 'c')) -> ProviderRouteDecision:
    return ProviderRouteDecision(
        provider_ref='prov-a',
        model_ref='model-a',
        account_ref='acc-a',
        route_revision='rev-1',
        rationale_codes=['ROLE_OK'],
        fallback_order=list(fallback_order),
        capacity_reservation_ref='res-1',
        credential_acquisition_method='secret_broker_handle',
        estimated_cost_class='low',
    )


def _policy(committed: bool = False, allowed: bool = False) -> FallbackIntentPolicy:
    return FallbackIntentPolicy(committed, allowed)


def _decide(**overrides: object) -> FallbackOutcome:
    params: dict[str, object] = {
        'decision': _decision(),
        'failure_kind': RATE_LIMIT,
        'attempted': ('a',),
        'intent_policy': _policy(),
        'desktop_online': True,
        'local_candidate_refs': frozenset(),
        'ai_required': True,
    }
    params.update(overrides)
    return decide_fallback(
        decision=params['decision'],  # type: ignore[arg-type]
        failure_kind=params['failure_kind'],  # type: ignore[arg-type]
        attempted=params['attempted'],  # type: ignore[arg-type]
        intent_policy=params['intent_policy'],  # type: ignore[arg-type]
        desktop_online=params['desktop_online'],  # type: ignore[arg-type]
        local_candidate_refs=params['local_candidate_refs'],  # type: ignore[arg-type]
        ai_required=params['ai_required'],  # type: ignore[arg-type]
    )


def test_rate_limit_switches_to_first_fallback():
    outcome = _decide(failure_kind=RATE_LIMIT)
    assert outcome.action == SWITCH
    assert outcome.next_candidate_ref == 'b'
    assert outcome.reason_codes == ('FALLBACK_AVAILABLE',)


def test_timeout_switches_to_first_fallback():
    outcome = _decide(failure_kind=TIMEOUT)
    assert outcome.action == SWITCH
    assert outcome.next_candidate_ref == 'b'
    assert outcome.reason_codes == ('FALLBACK_AVAILABLE',)


def test_attempted_candidates_are_skipped():
    outcome = _decide(attempted=('a', 'b'))
    assert outcome.action == SWITCH
    assert outcome.next_candidate_ref == 'c'
    assert outcome.reason_codes == ('FALLBACK_AVAILABLE',)


def test_exhausted_fallback_waits():
    outcome = _decide(attempted=('a', 'b', 'c'))
    assert outcome.action == WAIT
    assert outcome.next_candidate_ref is None
    assert outcome.reason_codes == ('FALLBACK_EXHAUSTED',)


def test_empty_fallback_order_waits():
    outcome = _decide(decision=_decision(fallback_order=()))
    assert outcome.action == WAIT
    assert outcome.next_candidate_ref is None
    assert outcome.reason_codes == ('FALLBACK_EXHAUSTED',)


def test_auth_and_unknown_wait_even_with_fallback():
    for kind in (AUTH, UNKNOWN, 'WHATEVER'):
        outcome = _decide(failure_kind=kind)
        assert outcome.action == WAIT
        assert outcome.next_candidate_ref is None
        assert outcome.reason_codes == ('FAILURE_NOT_SWITCHABLE',)


def test_ai_not_required_continues_without_ai():
    for kind in (RATE_LIMIT, AUTH):
        outcome = _decide(ai_required=False, failure_kind=kind, intent_policy=_policy(True, False))
        assert outcome.action == CONTINUE_WITHOUT_AI
        assert outcome.next_candidate_ref is None
        assert outcome.reason_codes == ('AI_NOT_REQUIRED',)


def test_snapshot_committed_without_permission_requires_new_revision():
    outcome = _decide(intent_policy=_policy(True, False), failure_kind=RATE_LIMIT)
    assert outcome.action == NEW_OUTPUT_REVISION_REQUIRED
    assert outcome.next_candidate_ref is None
    assert outcome.reason_codes == ('SNAPSHOT_COMMITTED_NEW_REVISION',)


def test_snapshot_committed_with_permission_switches():
    outcome = _decide(intent_policy=_policy(True, True))
    assert outcome.action == SWITCH
    assert outcome.next_candidate_ref == 'b'
    assert outcome.reason_codes == ('FALLBACK_AVAILABLE',)


def test_snapshot_not_committed_switches_regardless_of_permission():
    outcome = _decide(intent_policy=_policy(False, False))
    assert outcome.action == SWITCH
    assert outcome.next_candidate_ref == 'b'
    assert outcome.reason_codes == ('FALLBACK_AVAILABLE',)


def test_snapshot_committed_without_permission_still_waits_for_auth_and_when_exhausted():
    outcome_auth = _decide(intent_policy=_policy(True, False), failure_kind=AUTH)
    assert outcome_auth.action == WAIT
    assert outcome_auth.next_candidate_ref is None
    assert outcome_auth.reason_codes == ('FAILURE_NOT_SWITCHABLE',)

    outcome_exhausted = _decide(
        intent_policy=_policy(True, False),
        failure_kind=RATE_LIMIT,
        attempted=('a', 'b', 'c'),
    )
    assert outcome_exhausted.action == WAIT
    assert outcome_exhausted.next_candidate_ref is None
    assert outcome_exhausted.reason_codes == ('FALLBACK_EXHAUSTED',)


def test_local_candidate_skipped_when_desktop_offline():
    decision_both = _decision(fallback_order=('loc', 'b'))
    outcome_both = _decide(
        decision=decision_both,
        local_candidate_refs=frozenset({'loc'}),
        desktop_online=False,
    )
    assert outcome_both.action == SWITCH
    assert outcome_both.next_candidate_ref == 'b'

    decision_local_only = _decision(fallback_order=('loc',))
    outcome_local_only = _decide(
        decision=decision_local_only,
        local_candidate_refs=frozenset({'loc'}),
        desktop_online=False,
    )
    assert outcome_local_only.action == WAIT
    assert outcome_local_only.next_candidate_ref is None
    assert outcome_local_only.reason_codes == ('FALLBACK_EXHAUSTED',)


def test_local_candidate_chosen_when_desktop_online():
    decision = _decision(fallback_order=('loc', 'b'))
    outcome = _decide(
        decision=decision,
        local_candidate_refs=frozenset({'loc'}),
        desktop_online=True,
    )
    assert outcome.action == SWITCH
    assert outcome.next_candidate_ref == 'loc'
    assert outcome.reason_codes == ('FALLBACK_AVAILABLE',)


def test_provenance_required_is_constant_for_every_action():
    kinds = (RATE_LIMIT, TIMEOUT, AUTH, UNKNOWN)
    ai_flags = (True, False)
    policies = ((False, False), (True, False), (True, True))
    decision = _decision(fallback_order=('b', 'c'))
    for failure_kind, ai_required, (committed, allowed) in itertools.product(kinds, ai_flags, policies):
        outcome = _decide(
            decision=decision,
            failure_kind=failure_kind,
            ai_required=ai_required,
            intent_policy=_policy(committed, allowed),
        )
        assert outcome.provenance_required == ('model_ref', 'prompt_revision', 'config_revision')
        assert outcome.provenance_required == PROVENANCE_REQUIRED
        assert isinstance(outcome.reason_codes, tuple)
        assert len(outcome.reason_codes) == 1
        if outcome.next_candidate_ref is not None:
            assert outcome.next_candidate_ref in decision.fallback_order


def test_never_selects_candidate_outside_fallback_order():
    decision = _decision(fallback_order=('x',))
    outcome = _decide(decision=decision, attempted=())
    assert outcome.next_candidate_ref == 'x'
    assert outcome.next_candidate_ref != 'a'


def test_non_string_entries_in_fallback_order_are_ignored():
    decision = _decision(fallback_order=[None, 7, 'b'])
    outcome = _decide(decision=decision)
    assert outcome.action == SWITCH
    assert outcome.next_candidate_ref == 'b'


def test_same_input_gives_equal_outcome_and_inputs_not_mutated():
    decision = _decision(fallback_order=['b', 'c'])
    attempted = ['a']
    fallback_order_copy = list(decision.fallback_order)
    attempted_copy = list(attempted)

    out1 = decide_fallback(
        decision=decision,
        failure_kind=RATE_LIMIT,
        attempted=attempted,
        intent_policy=_policy(),
        desktop_online=True,
        local_candidate_refs=frozenset(),
        ai_required=True,
    )
    out2 = decide_fallback(
        decision=decision,
        failure_kind=RATE_LIMIT,
        attempted=attempted,
        intent_policy=_policy(),
        desktop_online=True,
        local_candidate_refs=frozenset(),
        ai_required=True,
    )
    assert out1 == out2
    assert decision.fallback_order == fallback_order_copy
    assert attempted == attempted_copy


def test_outcome_and_policy_are_frozen():
    policy = _policy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.snapshot_committed = True  # type: ignore[misc]

    outcome = FallbackOutcome(SWITCH, 'b', PROVENANCE_REQUIRED, ('FALLBACK_AVAILABLE',))
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.action = WAIT  # type: ignore[misc]


def test_backoff_doubles_from_base_and_is_capped():
    assert backoff_seconds(0, 1, 60) == 1
    assert backoff_seconds(1, 1, 60) == 2
    assert backoff_seconds(2, 1, 60) == 4
    assert backoff_seconds(3, 2, 10) == 10
    assert backoff_seconds(2, 1, 4) == 4
    assert backoff_seconds(10, 1, 8) == 8


def test_backoff_huge_attempt_returns_cap_immediately():
    assert backoff_seconds(10**9, 1, 60) == 60
    assert backoff_seconds(10**9, 5, 100) == 100


def test_backoff_returns_int_and_is_deterministic():
    r1 = backoff_seconds(2, 3, 20)
    r2 = backoff_seconds(2, 3, 20)
    assert isinstance(r1, int)
    assert r1 == r2


def test_backoff_parameters_are_required():
    sig_backoff = inspect.signature(backoff_seconds)
    assert list(sig_backoff.parameters.keys()) == ['attempt', 'base', 'cap']
    for p in sig_backoff.parameters.values():
        assert p.default is inspect.Parameter.empty

    sig_decide = inspect.signature(decide_fallback)
    assert list(sig_decide.parameters.keys()) == [
        'decision',
        'failure_kind',
        'attempted',
        'intent_policy',
        'desktop_online',
        'local_candidate_refs',
        'ai_required',
    ]
    for p in sig_decide.parameters.values():
        assert p.default is inspect.Parameter.empty


def test_backoff_rejects_invalid_values():
    invalid_cases = [
        (-1, 1, 60),
        (True, 1, 60),
        (1.5, 1, 60),
        (0, 0, 60),
        (0, -1, 60),
        (0, True, 60),
        (0, 1, 0),
        (0, 1, -5),
        (0, 1, True),
        (0, '1', 60),
    ]
    for attempt, base, cap in invalid_cases:
        with pytest.raises(ValueError):
            backoff_seconds(attempt, base, cap)  # type: ignore[arg-type]


def test_intent_policy_requires_bools():
    invalid_policies = [
        (1, True),
        (True, None),
        ('yes', False),
    ]
    for committed, allowed in invalid_policies:
        with pytest.raises(ValueError):
            FallbackIntentPolicy(committed, allowed)  # type: ignore[arg-type]


def test_decide_fallback_rejects_invalid_inputs():
    valid_decision = _decision()
    valid_policy = _policy()

    with pytest.raises(TypeError):
        _decide(decision={'provider_ref': 'a'})

    with pytest.raises(TypeError):
        _decide(intent_policy=(True, False))

    with pytest.raises(ValueError):
        _decide(failure_kind=None)

    with pytest.raises(ValueError):
        _decide(attempted='b')

    with pytest.raises(ValueError):
        _decide(attempted=[1])

    with pytest.raises(ValueError):
        _decide(desktop_online=1)

    with pytest.raises(ValueError):
        _decide(ai_required=None)

    with pytest.raises(ValueError):
        _decide(local_candidate_refs=['x'])

    with pytest.raises(ValueError):
        _decide(local_candidate_refs=frozenset({1}))

    bad_order_decision = dataclasses.replace(valid_decision, fallback_order='bc')
    with pytest.raises(ValueError):
        _decide(decision=bad_order_decision)
