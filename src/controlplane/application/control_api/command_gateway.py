"""Cổng nhận lệnh Control API CT-API-003..006.

Idempotency và receipt 'accepted' nằm ở đây, nghiệp vụ do handler của phân hệ
chủ sở hữu cấp qua port. KHÔNG import controlplane.infrastructure, KHÔNG có chuỗi SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from controlplane.application.control_api.errors import CapabilityUnavailableError
from controlplane.application.control_api.receipts import accepted_receipt
from controlplane.application.idempotency import request_hash


@dataclass(frozen=True)
class CommandOutcome:
    operation_id: str | None
    resource_ref: dict[str, object]
    current_revision: int | None


class CommandHandlerPort(Protocol):
    """Port handler lệnh phân hệ.

    Handler ném controlplane.domain.concurrency.RevisionConflictError khi expected_revision lệch.
    """

    def handle(
        self,
        *,
        connection: Any,
        workspace_id: str,
        actor_id: str,
        correlation_id: str,
        resource_id: str | None,
        expected_revision: int | None,
        payload: Mapping[str, object],
    ) -> CommandOutcome:
        ...


class ControlCommandGateway:
    """Cổng nhận lệnh Control API, quản lý tính lũy quyền (idempotency) và receipt."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], Any],
        idempotency_factory: Callable[[Any], Any],
        receipt_fields_factory: Callable[[Any], Any],
        handlers: Mapping[str, CommandHandlerPort] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._idempotency_factory = idempotency_factory
        self._receipt_fields_factory = receipt_fields_factory
        self._handlers: dict[str, CommandHandlerPort] = dict(handlers or {})

    def register(self, command_name: str, handler: CommandHandlerPort) -> None:
        if command_name in self._handlers:
            raise ValueError("handler already registered")
        self._handlers[command_name] = handler

    def submit(
        self,
        *,
        command_name: str,
        workspace_id: str,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        resource_id: str | None,
        expected_revision: int | None,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        handler = self._handlers.get(command_name)
        if handler is None:
            raise CapabilityUnavailableError(command_name)

        logical = {
            "workspace_id": workspace_id,
            "command_name": command_name,
            "resource_id": resource_id or "",
            "expected_revision": expected_revision,
            "payload": dict(payload),
        }
        digest = request_hash(logical)
        key = {
            "workspace_id": workspace_id,
            "command_name": command_name,
            "idempotency_key": idempotency_key,
        }

        with self._uow_factory() as uow:
            connection = uow.connection
            idempotency = self._idempotency_factory(connection)
            idempotency.lock_key(**key)
            record = idempotency.get_record(**key)
            if record is not None:
                if record[0] != digest:
                    raise ValueError("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD")
                return accepted_receipt(idempotency.replay_receipt(record[1]))

            outcome = handler.handle(
                connection=connection,
                workspace_id=workspace_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                resource_id=resource_id,
                expected_revision=expected_revision,
                payload=payload,
            )
            receipt = idempotency.create_receipt(workspace_id=workspace_id)
            receipt = self._receipt_fields_factory(connection).bind(
                workspace_id=workspace_id,
                receipt_id=receipt["receipt_id"],
                operation_id=outcome.operation_id,
                resource_ref=outcome.resource_ref,
                current_revision=outcome.current_revision,
            )
            idempotency.create_record(
                workspace_id=workspace_id,
                command_name=command_name,
                idempotency_key=idempotency_key,
                request_hash=digest,
                receipt_id=receipt["receipt_id"],
            )
            return accepted_receipt(receipt)