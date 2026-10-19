"""J-04: đồ thị trạng thái ConfigRevision và ExternalAccount (CT-STATE-013, CT-ACC-001; D8-J-09).

Pure domain: no I/O, no clock, no mutation. Edges are the exact CT-STATE-013 text; self-transitions are forbidden, INVALIDATED is terminal
and DEGRADED, INVALID, REVOKED have no exit edge (REVOKED is re-enabled only by a new credential version, J-06).
ConfigRevisionStatus and ForbiddenTransitionError are imported read-only.
"""
from __future__ import annotations

from enum import StrEnum

from controlplane.domain.config_security import ConfigRevisionStatus
from controlplane.domain.statemachine import ForbiddenTransitionError

CONFIG_AGGREGATE_TYPE = 'config_revision'
ACCOUNT_AGGREGATE_TYPE = 'external_account'


class ExternalAccountStatus(StrEnum):
    ENABLED = 'ENABLED'
    DISABLED = 'DISABLED'
    DEGRADED = 'DEGRADED'
    INVALID = 'INVALID'
    REVOKED = 'REVOKED'


CONFIG_REVISION_EDGES: frozenset[tuple[ConfigRevisionStatus, ConfigRevisionStatus]] = frozenset({
    (ConfigRevisionStatus.DRAFT, ConfigRevisionStatus.PUBLISHED),
    (ConfigRevisionStatus.PUBLISHED, ConfigRevisionStatus.SUPERSEDED),
    (ConfigRevisionStatus.DRAFT, ConfigRevisionStatus.INVALIDATED),
    (ConfigRevisionStatus.PUBLISHED, ConfigRevisionStatus.INVALIDATED),
    (ConfigRevisionStatus.SUPERSEDED, ConfigRevisionStatus.INVALIDATED),
})
ACCOUNT_EDGES: frozenset[tuple[ExternalAccountStatus, ExternalAccountStatus]] = frozenset({
    (ExternalAccountStatus.DISABLED, ExternalAccountStatus.ENABLED),
    (ExternalAccountStatus.ENABLED, ExternalAccountStatus.DISABLED),
    (ExternalAccountStatus.ENABLED, ExternalAccountStatus.DEGRADED),
    (ExternalAccountStatus.ENABLED, ExternalAccountStatus.INVALID),
    (ExternalAccountStatus.ENABLED, ExternalAccountStatus.REVOKED),
})


def can_transition_config(current: ConfigRevisionStatus, requested: ConfigRevisionStatus) -> bool:
    return (current, requested) in CONFIG_REVISION_EDGES


def can_transition_account(current: ExternalAccountStatus, requested: ExternalAccountStatus) -> bool:
    return (current, requested) in ACCOUNT_EDGES


def require_config_transition(current: ConfigRevisionStatus, requested: ConfigRevisionStatus, current_revision: int) -> None:
    if not can_transition_config(current, requested):
        raise ForbiddenTransitionError(
            aggregate_type=CONFIG_AGGREGATE_TYPE, current_state=current, requested_next_state=requested, current_revision=current_revision,
        )


def require_account_transition(current: ExternalAccountStatus, requested: ExternalAccountStatus, current_revision: int) -> None:
    if not can_transition_account(current, requested):
        raise ForbiddenTransitionError(
            aggregate_type=ACCOUNT_AGGREGATE_TYPE, current_state=current, requested_next_state=requested, current_revision=current_revision,
        )


def account_status_view(status: ExternalAccountStatus | str) -> str:
    """Return the lowercase CT-ACC-001 view status; an unknown status raises ValueError."""
    return ExternalAccountStatus(status).value.lower()