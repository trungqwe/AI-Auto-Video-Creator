"""Đánh giá cleanup (CT-STO-007) và kiểm tra cleanup authorization (CT-STO-008)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import ArtifactLocation, CleanupAuthorization

ELIGIBLE = "eligible"
DEFERRED = "deferred"
FORBIDDEN = "forbidden"
INVALID_EXPIRY = "INVALID_EXPIRY"
CLEANABLE_STORAGE_CLASSES = frozenset({"local_staging", "local_cache"})
EVALUABLE_LOCATION_STATES = frozenset({ArtifactLocationState.VERIFIED, ArtifactLocationState.CLEANUP_ELIGIBLE})
TRANSIENT_RETENTION_CLASSES = frozenset({"per_video", "temporary"})


@dataclass(frozen=True)
class CleanupEvaluationRequest:
    storage_class: str
    location_state: ArtifactLocationState
    retention_class: str
    cloud_copy_verified: bool
    active_lease: bool
    completion_ref: str | None
    superseded_ref: str | None
    request_recovery_epoch: str
    current_recovery_epoch: str


@dataclass(frozen=True)
class CleanupEvaluation:
    decision: str
    reason_codes: tuple[str, ...]
    earliest_cleanup_at: datetime | None = None


def _has_ref(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _parse_expiry(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if _is_aware(parsed) else None


def evaluate_cleanup(request: CleanupEvaluationRequest) -> CleanupEvaluation:
    forbidden: list[str] = []
    if request.storage_class not in CLEANABLE_STORAGE_CLASSES:
        forbidden.append("NOT_LOCAL_STAGING")
    if request.location_state not in EVALUABLE_LOCATION_STATES:
        forbidden.append("LOCATION_NOT_VERIFIED")
    if request.retention_class not in TRANSIENT_RETENTION_CLASSES and request.cloud_copy_verified is not True:
        forbidden.append("DURABLE_COPY_NOT_VERIFIED")
    if str(request.request_recovery_epoch) != str(request.current_recovery_epoch):
        forbidden.append("STALE_RECOVERY_EPOCH")
    if forbidden:
        return CleanupEvaluation(FORBIDDEN, tuple(forbidden))
    deferred: list[str] = []
    if request.active_lease:
        deferred.append("ACTIVE_LEASE")
    if not (_has_ref(request.completion_ref) or _has_ref(request.superseded_ref)):
        deferred.append("NO_COMPLETION_EVIDENCE")
    if deferred:
        return CleanupEvaluation(DEFERRED, tuple(deferred))
    return CleanupEvaluation(ELIGIBLE, ())


def check_cleanup_authorization(
    authorization: CleanupAuthorization,
    location: ArtifactLocation,
    current_recovery_epoch: str,
    now: datetime,
    path_within_staging: bool,
    active_lease: bool,
) -> tuple[bool, tuple[str, ...]]:
    expires_at = _parse_expiry(authorization.expires_at)
    if expires_at is None or not _is_aware(now):
        return False, (INVALID_EXPIRY,)
    reasons: list[str] = []
    if authorization.location_id != location.location_id:
        reasons.append("LOCATION_MISMATCH")
    if authorization.artifact_version_id != location.artifact_version_id:
        reasons.append("ARTIFACT_VERSION_MISMATCH")
    if authorization.artifact_hash != location.observed_hash:
        reasons.append("HASH_MISMATCH")
    if location.state != ArtifactLocationState.CLEANUP_AUTHORIZED:
        reasons.append("LOCATION_NOT_AUTHORIZED")
    if active_lease:
        reasons.append("ACTIVE_LEASE")
    if not now < expires_at:
        reasons.append("EXPIRED")
    if str(authorization.recovery_epoch) != current_recovery_epoch:
        reasons.append("STALE_RECOVERY_EPOCH")
    if path_within_staging is not True:
        reasons.append("PATH_OUTSIDE_STAGING")
    return not reasons, tuple(reasons)


__all__ = ["CleanupEvaluation", "CleanupEvaluationRequest", "check_cleanup_authorization", "evaluate_cleanup"]
