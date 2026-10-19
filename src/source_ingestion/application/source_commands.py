"""A-09 source management command handler (RegisterSource, UpdateSourceMetadata, RemoveSource, RestoreSource).

Each command executes inside a single Unit of Work recording:
- source revision
- CommandReceipt (idempotency key scoped by workspace and validated by request_hash)
- outbox domain event built using controlplane DomainEvent.

Replay returns the original receipt for identical payload, or raises IdempotencyConflictError for conflicting payload.
Event payloads carry identifiers and status metadata only, avoiding locators, notes, or credentials (A-RULE-014).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
import uuid

from controlplane.application.idempotency import request_hash
from controlplane.domain.events import DomainEvent
from controlplane.domain.interfaces.outbox import IOutboxWriter
from source_ingestion.domain import source as source_domain
from source_ingestion.domain.locator import Resolver, validate_locator
from source_ingestion.domain.source import Source, SourcePolicy
from source_ingestion.domain.source_candidate import IdentityMatchKind
from source_ingestion.ports.repositories import CommandReceipt, ReceiptStore, SourceRepository

COMMAND_REGISTER = 'RegisterSource'
COMMAND_UPDATE = 'UpdateSourceMetadata'
COMMAND_REMOVE = 'RemoveSource'
COMMAND_RESTORE = 'RestoreSource'

EVENT_REGISTERED = 'SourceRegistered'
EVENT_UPDATED = 'SourceMetadataUpdated'
EVENT_REMOVED = 'SourceRemoved'
EVENT_RESTORED = 'SourceRestored'

AGGREGATE_TYPE = 'Source'
PRODUCER = 'A'
SCHEMA_VERSION = '1.0.0'
SENSITIVITY = 'internal'
CONTRACT_NAME = 'source_ingestion.source'
CONTRACT_VERSION = 1


class IdempotencyConflictError(ValueError):
    def __init__(self, idempotency_key: str, existing_hash: str, requested_hash: str) -> None:
        self.code = 'IDEMPOTENCY_CONFLICT'
        self.idempotency_key = idempotency_key
        self.existing_hash = existing_hash
        self.requested_hash = requested_hash
        super().__init__(self.code)


class TombstoneConflictError(ValueError):
    def __init__(self, source_ref: str) -> None:
        self.code = 'SOURCE_TOMBSTONED'
        self.source_ref = source_ref
        super().__init__(self.code)


class SourceAlreadyRegisteredError(ValueError):
    def __init__(self, source_ref: str) -> None:
        self.code = 'SOURCE_ALREADY_REGISTERED'
        self.source_ref = source_ref
        super().__init__(self.code)


class SourceNotFoundError(LookupError):
    def __init__(self, source_ref: str) -> None:
        self.code = 'SOURCE_NOT_FOUND'
        self.source_ref = source_ref
        super().__init__(self.code)


@dataclass(frozen=True)
class CommandResult:
    receipt: CommandReceipt
    replayed: bool


class SourceUnitOfWork(Protocol):
    sources: SourceRepository
    receipts: ReceiptStore
    outbox: IOutboxWriter

    def commit(self) -> None: ...
    def __enter__(self) -> SourceUnitOfWork: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None: ...


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string.')
    return value


def _require_revision(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError('expected_revision must be an int >= 1')
    return value


def _topics_for_hash(topics: object) -> list[str]:
    if isinstance(topics, str) or not isinstance(topics, Iterable):
        raise ValueError('topics must be a collection of strings')
    items = list(topics)
    if any(not isinstance(t, str) for t in items):
        raise ValueError('topics must be a collection of strings')
    return sorted(set(items))


def _metadata_for_hash(metadata: object) -> dict[str, str]:
    if not isinstance(metadata, Mapping):
        raise ValueError('admin_metadata must be a mapping')
    return dict(metadata)


class SourceCommandHandler:
    def __init__(
        self,
        *,
        uow: SourceUnitOfWork,
        policy_provider: Callable[[str], SourcePolicy],
        resolver: Resolver,
        recovery_epoch: str,
        clock: Callable[[], datetime] | None = None,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        _require_text(recovery_epoch, 'recovery_epoch')
        self._uow = uow
        self._policy_provider = policy_provider
        self._resolver = resolver
        self._recovery_epoch = recovery_epoch
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._new_id = new_id if new_id is not None else lambda: str(uuid.uuid4())

    def _run(
        self,
        *,
        command_name: str,
        workspace_id: str,
        idempotency_key: str,
        actor: str,
        correlation_id: str,
        logical: dict[str, Any],
        mutate: Callable[[SourceUnitOfWork, datetime], tuple[Source, str, dict[str, Any]]],
    ) -> CommandResult:
        _require_text(workspace_id, 'workspace_id')
        _require_text(idempotency_key, 'idempotency_key')
        _require_text(actor, 'actor')
        _require_text(correlation_id, 'correlation_id')
        digest = request_hash({'command_name': command_name, 'workspace_id': workspace_id, 'payload': logical})
        at = self._clock()
        with self._uow as uow:
            stored = uow.receipts.get(workspace_id, idempotency_key)
            if stored is not None:
                if stored.request_hash != digest:
                    raise IdempotencyConflictError(idempotency_key, stored.request_hash, digest)
                return CommandResult(stored, True)
            source, event_name, event_payload = mutate(uow, at)
            receipt = CommandReceipt(
                workspace_id=workspace_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                aggregate_ref=source.source_id,
                aggregate_revision=source.revision,
            )
            uow.receipts.put(receipt)
            event = self._build_event(
                event_name=event_name,
                source=source,
                workspace_id=workspace_id,
                actor=actor,
                correlation_id=correlation_id,
                at=at,
                payload=event_payload,
            )
            uow.outbox.append_event(
                event.event_name,
                event.aggregate_id,
                dataclasses.asdict(event),
                f'{workspace_id}:{event_name}:{source.source_id}:{source.revision}',
            )
            uow.commit()
        return CommandResult(receipt, False)

    def _build_event(
        self,
        *,
        event_name: str,
        source: Source,
        workspace_id: str,
        actor: str,
        correlation_id: str,
        at: datetime,
        payload: dict[str, Any],
    ) -> DomainEvent:
        return DomainEvent(
            contract_name=CONTRACT_NAME,
            contract_version=CONTRACT_VERSION,
            message_id=self._new_id(),
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            causation_id=None,
            trace_context=None,
            occurred_at=at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
            actor=actor,
            recovery_epoch=self._recovery_epoch,
            payload=payload,
            event_id=self._new_id(),
            event_name=event_name,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=source.source_id,
            aggregate_revision=source.revision,
            producer=PRODUCER,
            schema_version=SCHEMA_VERSION,
            sensitivity=SENSITIVITY,
        )

    def _load(self, uow: SourceUnitOfWork, workspace_id: str, source_id: str) -> Source:
        source = uow.sources.get(workspace_id, source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        return source

    def register_source(
        self,
        *,
        workspace_id: str,
        idempotency_key: str,
        actor: str,
        correlation_id: str,
        locator: str,
        name: str,
        source_kind: str,
        tier: str,
        topics: Iterable[str],
        notes: str = '',
        collection_enabled: bool = True,
        admin_metadata: Mapping[str, str] | None = None,
    ) -> CommandResult:
        metadata = _metadata_for_hash(admin_metadata or {})
        logical = {
            'locator': locator,
            'name': name,
            'source_kind': source_kind,
            'tier': tier,
            'topics': _topics_for_hash(topics),
            'notes': notes,
            'collection_enabled': collection_enabled,
            'admin_metadata': metadata,
        }

        def mutate(uow: SourceUnitOfWork, at: datetime) -> tuple[Source, str, dict[str, Any]]:
            canonical = validate_locator(locator, self._resolver).locator
            match = uow.sources.resolve_identity(workspace_id, canonical)
            if match.kind is IdentityMatchKind.TOMBSTONE:
                raise TombstoneConflictError(match.ref)
            if match.kind is IdentityMatchKind.EXISTING_SOURCE:
                raise SourceAlreadyRegisteredError(match.ref)
            source = source_domain.register_source(
                source_id=self._new_id(),
                workspace_id=workspace_id,
                canonical_locator=canonical,
                name=name,
                source_kind=source_kind,
                tier=tier,
                topics=topics,
                notes=notes,
                collection_enabled=collection_enabled,
                admin_metadata=metadata,
                actor=actor,
                at=at,
                policy=self._policy_provider(workspace_id),
            )
            uow.sources.add(source)
            return (
                source,
                EVENT_REGISTERED,
                {
                    'source_id': source.source_id,
                    'revision': source.revision,
                    'status': source.status.value,
                    'source_kind': source.source_kind,
                    'tier': source.tier,
                    'policy_revision': source.policy_revision,
                },
            )

        return self._run(
            command_name=COMMAND_REGISTER,
            workspace_id=workspace_id,
            idempotency_key=idempotency_key,
            actor=actor,
            correlation_id=correlation_id,
            logical=logical,
            mutate=mutate,
        )

    def update_source_metadata(
        self,
        *,
        workspace_id: str,
        idempotency_key: str,
        actor: str,
        correlation_id: str,
        source_id: str,
        expected_revision: int,
        tier: str | None = None,
        topics: Iterable[str] | None = None,
        notes: str | None = None,
        collection_enabled: bool | None = None,
        admin_metadata: Mapping[str, str] | None = None,
    ) -> CommandResult:
        _require_revision(expected_revision)
        logical = {
            'source_id': source_id,
            'expected_revision': expected_revision,
            'tier': tier,
            'topics': None if topics is None else _topics_for_hash(topics),
            'notes': notes,
            'collection_enabled': collection_enabled,
            'admin_metadata': None if admin_metadata is None else _metadata_for_hash(admin_metadata),
        }

        def mutate(uow: SourceUnitOfWork, at: datetime) -> tuple[Source, str, dict[str, Any]]:
            before = self._load(uow, workspace_id, source_id)
            after = source_domain.update_source_metadata(
                before,
                expected_revision=expected_revision,
                actor=actor,
                at=at,
                policy=self._policy_provider(workspace_id),
                tier=tier,
                topics=topics,
                notes=notes,
                collection_enabled=collection_enabled,
                admin_metadata=admin_metadata,
            )
            uow.sources.save(after)
            changed = [
                name
                for name in ('admin_metadata', 'notes', 'status', 'tier', 'topics')
                if getattr(before, name) != getattr(after, name)
            ]
            return (
                after,
                EVENT_UPDATED,
                {
                    'source_id': after.source_id,
                    'revision': after.revision,
                    'status': after.status.value,
                    'tier': after.tier,
                    'policy_revision': after.policy_revision,
                    'changed_fields': changed,
                },
            )

        return self._run(
            command_name=COMMAND_UPDATE,
            workspace_id=workspace_id,
            idempotency_key=idempotency_key,
            actor=actor,
            correlation_id=correlation_id,
            logical=logical,
            mutate=mutate,
        )

    def remove_source(
        self,
        *,
        workspace_id: str,
        idempotency_key: str,
        actor: str,
        correlation_id: str,
        source_id: str,
        expected_revision: int,
        reason: str | None = None,
    ) -> CommandResult:
        _require_revision(expected_revision)
        logical = {
            'source_id': source_id,
            'expected_revision': expected_revision,
            'reason': reason,
        }

        def mutate(uow: SourceUnitOfWork, at: datetime) -> tuple[Source, str, dict[str, Any]]:
            before = self._load(uow, workspace_id, source_id)
            after = source_domain.remove_source(
                before,
                expected_revision=expected_revision,
                actor=actor,
                at=at,
                reason=reason,
            )
            uow.sources.save(after)
            return (
                after,
                EVENT_REMOVED,
                {
                    'source_id': after.source_id,
                    'revision': after.revision,
                    'status': after.status.value,
                    'previous_status': before.status.value,
                },
            )

        return self._run(
            command_name=COMMAND_REMOVE,
            workspace_id=workspace_id,
            idempotency_key=idempotency_key,
            actor=actor,
            correlation_id=correlation_id,
            logical=logical,
            mutate=mutate,
        )

    def restore_source(
        self,
        *,
        workspace_id: str,
        idempotency_key: str,
        actor: str,
        correlation_id: str,
        source_id: str,
        expected_revision: int,
    ) -> CommandResult:
        _require_revision(expected_revision)
        logical = {
            'source_id': source_id,
            'expected_revision': expected_revision,
        }

        def mutate(uow: SourceUnitOfWork, at: datetime) -> tuple[Source, str, dict[str, Any]]:
            before = self._load(uow, workspace_id, source_id)
            after = source_domain.restore_source(
                before,
                expected_revision=expected_revision,
                actor=actor,
                at=at,
                policy=self._policy_provider(workspace_id),
            )
            uow.sources.save(after)
            return (
                after,
                EVENT_RESTORED,
                {
                    'source_id': after.source_id,
                    'revision': after.revision,
                    'status': after.status.value,
                    'status_reason': after.status_reason,
                    'policy_revision': after.policy_revision,
                },
            )

        return self._run(
            command_name=COMMAND_RESTORE,
            workspace_id=workspace_id,
            idempotency_key=idempotency_key,
            actor=actor,
            correlation_id=correlation_id,
            logical=logical,
            mutate=mutate,
        )


__all__ = [
    'COMMAND_REGISTER',
    'COMMAND_UPDATE',
    'COMMAND_REMOVE',
    'COMMAND_RESTORE',
    'EVENT_REGISTERED',
    'EVENT_UPDATED',
    'EVENT_REMOVED',
    'EVENT_RESTORED',
    'IdempotencyConflictError',
    'TombstoneConflictError',
    'SourceAlreadyRegisteredError',
    'SourceNotFoundError',
    'CommandResult',
    'SourceUnitOfWork',
    'SourceCommandHandler',
]
