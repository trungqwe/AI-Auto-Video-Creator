"""J-04: đồ thị trạng thái ConfigRevision và ExternalAccount (CT-STATE-013, CT-ACC-001).

coveredIds: CT-STATE-013, CT-ACC-001
"""
import itertools

import pytest

from controlplane.application.config_security import _allowed_transition
from controlplane.application.projections.config_account_views import ACCOUNT_STATUSES
from controlplane.domain.config_security import ConfigRevisionStatus, status_graph
from controlplane.domain.config_security.status_graph import (
    ACCOUNT_EDGES, CONFIG_REVISION_EDGES, ExternalAccountStatus, account_status_view, can_transition_account,
    can_transition_config, require_account_transition, require_config_transition,
)
from controlplane.domain.statemachine import ForbiddenTransitionError

C = ConfigRevisionStatus
A = ExternalAccountStatus

DECLARED_CONFIG = {'DRAFT', 'PUBLISHED', 'SUPERSEDED', 'INVALIDATED'}
DECLARED_ACCOUNT = {'ENABLED', 'DISABLED', 'DEGRADED', 'INVALID', 'REVOKED'}
EXPECTED_CONFIG_EDGES = frozenset({
    (C.DRAFT, C.PUBLISHED), (C.PUBLISHED, C.SUPERSEDED), (C.DRAFT, C.INVALIDATED),
    (C.PUBLISHED, C.INVALIDATED), (C.SUPERSEDED, C.INVALIDATED),
})
EXPECTED_ACCOUNT_EDGES = frozenset({
    (A.DISABLED, A.ENABLED), (A.ENABLED, A.DISABLED), (A.ENABLED, A.DEGRADED), (A.ENABLED, A.INVALID), (A.ENABLED, A.REVOKED),
})
EXPECTED_VIEW = {'ENABLED': 'enabled', 'DISABLED': 'disabled', 'DEGRADED': 'degraded', 'REVOKED': 'revoked', 'INVALID': 'invalid'}
CONFIG_PAIRS = list(itertools.product(C, C))
ACCOUNT_PAIRS = list(itertools.product(A, A))


def _pair_id(pair) -> str:
    return f'{pair[0].name}-{pair[1].name}'


def test_every_enum_member_is_declared():
    assert {m.name for m in C} == DECLARED_CONFIG
    assert {m.name for m in A} == DECLARED_ACCOUNT
    assert all(m.value == m.name for m in A)
    assert set(EXPECTED_VIEW) == DECLARED_ACCOUNT
    assert status_graph.ConfigRevisionStatus is C


def test_edge_sets_are_exact_frozensets_of_five():
    assert isinstance(CONFIG_REVISION_EDGES, frozenset) and len(CONFIG_REVISION_EDGES) == 5
    assert CONFIG_REVISION_EDGES == EXPECTED_CONFIG_EDGES
    assert isinstance(ACCOUNT_EDGES, frozenset) and len(ACCOUNT_EDGES) == 5
    assert ACCOUNT_EDGES == EXPECTED_ACCOUNT_EDGES


@pytest.mark.parametrize('pair', CONFIG_PAIRS, ids=_pair_id)
def test_config_pair_is_allowed_only_on_declared_edges(pair):
    current, requested = pair
    allowed = pair in EXPECTED_CONFIG_EDGES
    assert can_transition_config(current, requested) is allowed
    if allowed:
        assert require_config_transition(current, requested, 7) is None
        return
    with pytest.raises(ForbiddenTransitionError) as info:
        require_config_transition(current, requested, 7)
    error = info.value
    assert (error.aggregate_type, error.current_state, error.requested_next_state, error.current_revision) == ('config_revision', current, requested, 7)


@pytest.mark.parametrize('pair', ACCOUNT_PAIRS, ids=_pair_id)
def test_account_pair_is_allowed_only_on_declared_edges(pair):
    current, requested = pair
    allowed = pair in EXPECTED_ACCOUNT_EDGES
    assert can_transition_account(current, requested) is allowed
    if allowed:
        assert require_account_transition(current, requested, 3) is None
        return
    with pytest.raises(ForbiddenTransitionError) as info:
        require_account_transition(current, requested, 3)
    error = info.value
    assert (error.aggregate_type, error.current_state, error.requested_next_state, error.current_revision) == ('external_account', current, requested, 3)


@pytest.mark.parametrize('pair', CONFIG_PAIRS, ids=_pair_id)
def test_config_graph_matches_application_allowed_transition(pair):
    assert can_transition_config(*pair) is _allowed_transition(*pair)


def test_config_counterexamples_are_rejected():
    assert not can_transition_config(C.DRAFT, C.SUPERSEDED)
    assert not can_transition_config(C.SUPERSEDED, C.PUBLISHED)
    assert not any(can_transition_config(C.INVALIDATED, status) for status in C)
    assert not any(can_transition_config(status, status) for status in C)


def test_account_counterexamples_are_rejected():
    assert not can_transition_account(A.REVOKED, A.ENABLED)
    assert not can_transition_account(A.DISABLED, A.REVOKED)
    for terminal in (A.DEGRADED, A.INVALID, A.REVOKED):
        assert not any(can_transition_account(terminal, status) for status in A)
    assert not any(can_transition_account(status, status) for status in A)


@pytest.mark.parametrize('status', list(A), ids=lambda status: status.name)
def test_account_status_view_is_lowercase_value(status):
    view = account_status_view(status)
    assert type(view) is str
    assert view == EXPECTED_VIEW[status.name]


def test_account_status_view_matches_projection_statuses():
    assert {account_status_view(status) for status in A} == set(ACCOUNT_STATUSES)


def test_account_status_view_rejects_unknown_status():
    with pytest.raises(ValueError):
        account_status_view('UNKNOWN')