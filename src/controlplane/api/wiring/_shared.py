from __future__ import annotations

"""ADAPT-WIRE: tiện ích trung lập dùng chung cho wiring qua connection pool của TransactionManager.
GIẢ ĐỊNH: ref của artifact là đường dẫn tương đối dưới staging root."""

from pathlib import Path
from typing import Any

from controlplane.infrastructure.db.config_security.stores import (
    PostgresCostLedger,
    PostgresReservationStore,
)


class PooledReservationStore:
    def __init__(self, manager: Any, workspace_id: str) -> None:
        self._manager = manager
        self._workspace_id = workspace_id

    def get_by_operation(self, operation_key: str) -> Any:
        with self._manager.borrow_connection() as connection:
            return PostgresReservationStore(connection, self._workspace_id).get_by_operation(operation_key)

    def list_by_domain(self, domain_key: str) -> Any:
        with self._manager.borrow_connection() as connection:
            return PostgresReservationStore(connection, self._workspace_id).list_by_domain(domain_key)

    def list_all(self) -> Any:
        with self._manager.borrow_connection() as connection:
            return PostgresReservationStore(connection, self._workspace_id).list_all()

    def add(self, reservation: Any) -> None:
        with self._manager.borrow_connection() as connection:
            PostgresReservationStore(connection, self._workspace_id).add(reservation)

    def remove(self, reservation_ref: str) -> Any:
        with self._manager.borrow_connection() as connection:
            return PostgresReservationStore(connection, self._workspace_id).remove(reservation_ref)


class PooledCostLedger:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def records(self, workspace_id: str, window_start: Any, window_end: Any) -> tuple[Any, ...]:
        with self._manager.borrow_connection() as connection:
            return tuple(PostgresCostLedger(connection).records(workspace_id, window_start, window_end))

    def append(self, workspace_id: str, record: Any) -> None:
        with self._manager.borrow_connection() as connection:
            PostgresCostLedger(connection).append(workspace_id, record)


def resolve_under_root(root: Path, ref: str) -> Path:
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError('INVALID_ARTIFACT_REF')
    p_ref = Path(ref)
    if p_ref.is_absolute() or p_ref.drive or '..' in p_ref.parts:
        raise ValueError('INVALID_ARTIFACT_REF')
    base = root.resolve()
    candidate = (root / ref).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError('INVALID_ARTIFACT_REF')
    return candidate


__all__ = ['PooledCostLedger', 'PooledReservationStore', 'resolve_under_root']
