"""J-14: Chính sách fallback có kiểm soát (CT-AI-ROUTE-002; D8-J-07).
Dịch vụ ứng dụng thuần túy, không I/O, không sleep, không random.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from controlplane.config.adapter import ProviderAuthenticationError, ProviderTimeoutError
from controlplane.config.models import RateLimitError
from controlplane.domain.config_security.route_binding import ProviderRouteDecision

RATE_LIMIT = 'RATE_LIMIT'
TIMEOUT = 'TIMEOUT'
AUTH = 'AUTH'
UNKNOWN = 'UNKNOWN'

SWITCH = 'SWITCH'
WAIT = 'WAIT'
CONTINUE_WITHOUT_AI = 'CONTINUE_WITHOUT_AI'
NEW_OUTPUT_REVISION_REQUIRED = 'NEW_OUTPUT_REVISION_REQUIRED'

PROVENANCE_REQUIRED = ('model_ref', 'prompt_revision', 'config_revision')

AI_NOT_REQUIRED = 'AI_NOT_REQUIRED'
FAILURE_NOT_SWITCHABLE = 'FAILURE_NOT_SWITCHABLE'
FALLBACK_AVAILABLE = 'FALLBACK_AVAILABLE'
FALLBACK_EXHAUSTED = 'FALLBACK_EXHAUSTED'
SNAPSHOT_COMMITTED_NEW_REVISION = 'SNAPSHOT_COMMITTED_NEW_REVISION'


def _require_bool(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be a bool')


def _require_text_items(name: str, value: object, kinds: tuple[type, ...]) -> None:
    if not isinstance(value, kinds) or not all(isinstance(item, str) for item in value):
        raise ValueError(f'{name} must be a collection of strings')


@dataclass(frozen=True)
class FallbackIntentPolicy:
    snapshot_committed: bool
    fallback_allowed_after_snapshot: bool

    def __post_init__(self) -> None:
        _require_bool('snapshot_committed', self.snapshot_committed)
        _require_bool('fallback_allowed_after_snapshot', self.fallback_allowed_after_snapshot)


@dataclass(frozen=True)
class FallbackOutcome:
    action: str
    next_candidate_ref: str | None
    provenance_required: tuple[str, ...]
    reason_codes: tuple[str, ...]


def _outcome(action: str, next_ref: str | None, reason: str) -> FallbackOutcome:
    return FallbackOutcome(action, next_ref, PROVENANCE_REQUIRED, (reason,))


def classify_failure(error: BaseException) -> str:
    if isinstance(error, RateLimitError) or getattr(error, 'code', None) == 429:
        return RATE_LIMIT
    if isinstance(error, (TimeoutError, ProviderTimeoutError)):
        return TIMEOUT
    if isinstance(error, ProviderAuthenticationError):
        return AUTH
    return UNKNOWN


def decide_fallback(
    decision: ProviderRouteDecision,
    failure_kind: str,
    attempted: Sequence[str],
    intent_policy: FallbackIntentPolicy,
    desktop_online: bool,
    local_candidate_refs: frozenset[str],
    ai_required: bool,
) -> FallbackOutcome:
    if not isinstance(decision, ProviderRouteDecision):
        raise TypeError('decision must be a ProviderRouteDecision')
    if not isinstance(intent_policy, FallbackIntentPolicy):
        raise TypeError('intent_policy must be a FallbackIntentPolicy')
    if not isinstance(failure_kind, str):
        raise ValueError('failure_kind must be a str')
    _require_text_items('attempted', attempted, (list, tuple))
    _require_text_items('local_candidate_refs', local_candidate_refs, (set, frozenset))
    _require_bool('desktop_online', desktop_online)
    _require_bool('ai_required', ai_required)
    if not isinstance(decision.fallback_order, (list, tuple)):
        raise ValueError('fallback_order must be a list or tuple')

    if not ai_required:
        return _outcome(CONTINUE_WITHOUT_AI, None, AI_NOT_REQUIRED)
    if failure_kind not in (RATE_LIMIT, TIMEOUT):
        return _outcome(WAIT, None, FAILURE_NOT_SWITCHABLE)

    tried = frozenset(attempted)
    for ref in decision.fallback_order:
        if not isinstance(ref, str) or ref in tried or (ref in local_candidate_refs and not desktop_online):
            continue
        if intent_policy.snapshot_committed and not intent_policy.fallback_allowed_after_snapshot:
            return _outcome(NEW_OUTPUT_REVISION_REQUIRED, None, SNAPSHOT_COMMITTED_NEW_REVISION)
        return _outcome(SWITCH, ref, FALLBACK_AVAILABLE)

    return _outcome(WAIT, None, FALLBACK_EXHAUSTED)


def backoff_seconds(attempt: int, base: int, cap: int) -> int:
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 0:
        raise ValueError('attempt must be a non-negative int')
    if not isinstance(base, int) or isinstance(base, bool) or base <= 0:
        raise ValueError('base must be a positive int')
    if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
        raise ValueError('cap must be a positive int')
    if attempt >= cap.bit_length():
        return cap
    return min(cap, base * 2**attempt)
