"""AuthorizeTimelineNarrative (CT-AI-005): gate for the from_then_to_now production mode.

coveredIds: CT-AI-005, TST-CTR-INV-006

Pure domain: no I/O, no clock, no id generation. Accepted event-update ref type names come from the caller's
TimelinePolicy; the module has no hidden default (fixture name: event_update_accepted). CT-CNT-005
EventUpdateAccepted has no binding yet (CONV-D-07), so only ref_type and revision_id of source_refs are checked.
The module never changes production_mode; a downgrade needs a new recorded decision made outside this module.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from creative.domain.snapshot import PRODUCTION_MODES, ProductionSnapshot

POLICY_VIOLATION = 'POLICY_VIOLATION'
EVENT_UPDATE_MISSING = 'event_update_accepted_missing'
EVENT_UPDATE_REVISION_MISSING = 'event_update_revision_missing'
TIMELINE_MODE = 'from_then_to_now'


class TimelinePolicyViolation(Exception):
    """CT-AI-005 refusal: `code` is POLICY_VIOLATION, `reason` is the stable machine reason; snapshot and mode stay untouched."""

    def __init__(self, reason: str) -> None:
        super().__init__(f'{POLICY_VIOLATION}: {reason}')
        self.code = POLICY_VIOLATION
        self.reason = reason


@dataclass(frozen=True)
class TimelinePolicy:
    """Caller-supplied policy: names of the ref types that count as an accepted event update (no hidden default)."""

    event_update_ref_types: frozenset[str]

    def __post_init__(self) -> None:
        names = self.event_update_ref_types
        if not isinstance(names, frozenset) or not names or not all(isinstance(name, str) and name for name in names):
            raise ValueError('event_update_ref_types must be a non-empty frozenset of non-empty strings')


@dataclass(frozen=True, kw_only=True)
class TimelineAuthorization:
    """Result of a successful check: the snapshot mode as given plus the accepted event-update refs that justify it."""

    snapshot_id: str
    production_mode: str
    event_update_refs: tuple[Mapping[str, str], ...]


def _text(ref: object, name: str) -> str:
    value = ref.get(name) if isinstance(ref, Mapping) else None
    return value if isinstance(value, str) else ''


def authorize_timeline_narrative(snapshot: ProductionSnapshot, policy: TimelinePolicy) -> TimelineAuthorization:
    """CT-AI-005: allow from_then_to_now only with an accepted event-update ref that carries a revision.

    Raises TimelinePolicyViolation (code POLICY_VIOLATION, stable reason) otherwise and ValueError for malformed
    arguments; other production modes pass through unchanged. The snapshot is never modified, its mode never replaced.
    """
    if not isinstance(snapshot, ProductionSnapshot):
        raise ValueError('snapshot must be a ProductionSnapshot')
    if not isinstance(policy, TimelinePolicy):
        raise ValueError('policy must be a TimelinePolicy')
    if snapshot.production_mode not in PRODUCTION_MODES:
        raise ValueError(f'production_mode must be one of {PRODUCTION_MODES!r}')
    if snapshot.production_mode != TIMELINE_MODE:
        return TimelineAuthorization(snapshot_id=snapshot.snapshot_id, production_mode=snapshot.production_mode, event_update_refs=())
    accepted = [ref for ref in snapshot.source_refs if _text(ref, 'ref_type') in policy.event_update_ref_types]
    if not accepted:
        raise TimelinePolicyViolation(EVENT_UPDATE_MISSING)
    with_revision = tuple(ref for ref in accepted if _text(ref, 'revision_id'))
    if not with_revision:
        raise TimelinePolicyViolation(EVENT_UPDATE_REVISION_MISSING)
    return TimelineAuthorization(snapshot_id=snapshot.snapshot_id, production_mode=snapshot.production_mode, event_update_refs=with_revision)
