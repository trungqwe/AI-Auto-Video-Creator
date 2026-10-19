"""G-03: đánh giá fencing generation và recovery epoch (CT-WF-004, CT-WF-006; INV-003, INV-016)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from controlplane.domain.orchestration import ExecutionGrant

ACCEPTED = 'ACCEPTED'
STALE_RECOVERY_EPOCH = 'STALE_RECOVERY_EPOCH'
STALE_EXECUTION_GENERATION = 'STALE_EXECUTION_GENERATION'
GRANT_MISMATCH = 'GRANT_MISMATCH'
GRANT_EXPIRED = 'GRANT_EXPIRED'
INVALID_EXPIRY = 'INVALID_EXPIRY'
INPUT_FINGERPRINT_MISMATCH = 'INPUT_FINGERPRINT_MISMATCH'
OPERATION_CONFLICT = 'OPERATION_CONFLICT'


@dataclass(frozen=True)
class GrantClaims:
    grant_id: str
    stage_run_id: str
    execution_generation: int
    recovery_epoch: str
    worker_lease_id: str
    issued_at: str
    expires_at: str
    allowed_operation: str
    input_fingerprint: str


@dataclass(frozen=True)
class FencingDecision:
    accepted: bool
    code: str


def claims_from_execution_grant(grant: ExecutionGrant, *, worker_lease_id: str, issued_at: str, expires_at: str, allowed_operation: str, input_fingerprint: str) -> GrantClaims:
    return GrantClaims(
        grant_id=grant.operation_id,
        stage_run_id=grant.stage_run_id,
        execution_generation=grant.execution_generation,
        recovery_epoch=str(grant.recovery_epoch),
        worker_lease_id=worker_lease_id,
        issued_at=issued_at,
        expires_at=expires_at,
        allowed_operation=allowed_operation,
        input_fingerprint=input_fingerprint,
    )


def _epoch_text(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    return str(value)


def _is_generation(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_expiry(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value[:-1] + '+00:00' if value.endswith('Z') else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _reject(code: str) -> FencingDecision:
    return FencingDecision(False, code)


def evaluate_result_fencing(
    claims: GrantClaims,
    current_generation: int,
    current_recovery_epoch: str | int,
    result: Mapping[str, object],
    input_fingerprint: str,
    now: datetime,
    has_conflicting_success_receipt: bool,
) -> FencingDecision:
    fields = result if isinstance(result, Mapping) else {}
    current_epoch = _epoch_text(current_recovery_epoch)
    if current_epoch is None or _epoch_text(fields.get('recovery_epoch')) != current_epoch or claims.recovery_epoch != current_epoch:
        return _reject(STALE_RECOVERY_EPOCH)
    result_generation = fields.get('execution_generation')
    if not _is_generation(current_generation) or not _is_generation(result_generation) or result_generation != current_generation or claims.execution_generation != current_generation:
        return _reject(STALE_EXECUTION_GENERATION)
    if fields.get('grant_id') != claims.grant_id or fields.get('stage_run_id') != claims.stage_run_id:
        return _reject(GRANT_MISMATCH)
    expires_at = _parse_expiry(claims.expires_at)
    if expires_at is None or not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return _reject(INVALID_EXPIRY)
    if now >= expires_at:
        return _reject(GRANT_EXPIRED)
    if input_fingerprint != claims.input_fingerprint:
        return _reject(INPUT_FINGERPRINT_MISMATCH)
    if has_conflicting_success_receipt:
        return _reject(OPERATION_CONFLICT)
    return FencingDecision(True, ACCEPTED)


__all__ = [
    'ACCEPTED', 'GRANT_EXPIRED', 'GRANT_MISMATCH', 'INPUT_FINGERPRINT_MISMATCH', 'INVALID_EXPIRY', 'OPERATION_CONFLICT',
    'STALE_EXECUTION_GENERATION', 'STALE_RECOVERY_EPOCH', 'FencingDecision', 'GrantClaims',
    'claims_from_execution_grant', 'evaluate_result_fencing',
]
