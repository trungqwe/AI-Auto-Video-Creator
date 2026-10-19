"""G-04: cấp grant đơn điệu và một lease hoạt động mỗi stage (CT-WF-004; INV-003, INV-016)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
from typing import Protocol
import uuid

from controlplane.domain.orchestration.fencing import GrantClaims


class ActiveGrantExistsError(Exception):
    def __init__(self, stage_run_id: str, grant_id: str) -> None:
        super().__init__(f'ACTIVE_GRANT_EXISTS: {stage_run_id} {grant_id}')
        self.stage_run_id = stage_run_id
        self.grant_id = grant_id


class GrantStorePort(Protocol):
    def latest_generation(self, stage_run_id: str) -> int: ...
    def active_grant(self, stage_run_id: str, now: datetime) -> GrantClaims | None: ...
    def insert(self, claims: GrantClaims) -> None: ...
    def revoke(self, grant_id: str) -> None: ...


class RecoveryEpochPort(Protocol):
    def current(self) -> str | int: ...


_ISSUE_LOCK = threading.Lock()


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')


def _epoch_text(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)) or value == '':
        raise ValueError('recovery epoch must be a non-empty string or an int')
    return str(value)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _is_live(claims: GrantClaims, now: datetime) -> bool:
    text = claims.expires_at
    if not isinstance(text, str):
        return False
    try:
        expires_at = datetime.fromisoformat(text[:-1] + '+00:00' if text.endswith('Z') else text)
    except ValueError:
        return False
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        return False
    return now < expires_at


class GrantIssuer:
    def __init__(self, store: GrantStorePort, epochs: RecoveryEpochPort) -> None:
        self._store = store
        self._epochs = epochs

    def issue(self, stage_run_id: str, allowed_operation: str, input_fingerprint: str, worker_lease_id: str, ttl_seconds: int, now: datetime) -> GrantClaims:
        for name, value in (('stage_run_id', stage_run_id), ('allowed_operation', allowed_operation), ('input_fingerprint', input_fingerprint), ('worker_lease_id', worker_lease_id)):
            _require_text(name, value)
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ValueError('ttl_seconds must be a positive int')
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('now must be timezone-aware')
        with _ISSUE_LOCK:
            epoch = _epoch_text(self._epochs.current())
            active = self._store.active_grant(stage_run_id, now)
            if active is not None:
                if _is_live(active, now):
                    if active.worker_lease_id != worker_lease_id:
                        raise ActiveGrantExistsError(stage_run_id, active.grant_id)
                    if active.recovery_epoch == epoch:
                        if active.allowed_operation == allowed_operation and active.input_fingerprint == input_fingerprint:
                            return active
                        raise ActiveGrantExistsError(stage_run_id, active.grant_id)
                self._store.revoke(active.grant_id)
            latest = self._store.latest_generation(stage_run_id)
            if isinstance(latest, bool) or not isinstance(latest, int) or latest < 0:
                raise ValueError('latest_generation must be a non-negative int')
            claims = GrantClaims(
                grant_id=str(uuid.uuid4()),
                stage_run_id=stage_run_id,
                execution_generation=latest + 1,
                recovery_epoch=epoch,
                worker_lease_id=worker_lease_id,
                issued_at=_iso(now),
                expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
                allowed_operation=allowed_operation,
                input_fingerprint=input_fingerprint,
            )
            self._store.insert(claims)
            return claims


__all__ = ['ActiveGrantExistsError', 'GrantIssuer', 'GrantStorePort', 'RecoveryEpochPort']
