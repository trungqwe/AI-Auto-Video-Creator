"""Minimal application semantics for the M1-P1 contract proof."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Callable, Literal, Protocol

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict


class ContractProofError(RuntimeError):
    """Base error for a rejected proof operation."""


class IdempotencyConflict(ContractProofError):
    """An idempotency key was reused for different logical input."""


class InjectedFailure(ContractProofError):
    """A deterministic failure injected at a transaction boundary."""


class EventGap(ContractProofError):
    """A consumer observed a revision gap and must reload owner state."""


class OutcomeUnknown(ContractProofError):
    """The operation committed but its caller did not receive the receipt."""

    def __init__(self, receipt_id: str) -> None:
        super().__init__("OUTCOME_UNKNOWN")
        self.receipt_id = receipt_id


class StaleExecution(ContractProofError):
    """A result was produced under an obsolete generation or epoch."""


class ReconciliationRequired(ContractProofError):
    """An external side effect must be reconciled before retry."""


class SensitiveDataRejected(ContractProofError):
    """A contract payload contained a forbidden sensitive key."""


class MutationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str
    idempotency_key: str
    workspace_id: str
    aggregate_id: str
    expected_revision: int
    recovery_epoch: str
    execution_generation: int
    payload: dict[str, object]


class CommandReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str
    receipt_id: str
    disposition: Literal["accepted", "duplicate"]
    resource_revision: int
    accepted_at: datetime


class DomainEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    workspace_id: str
    aggregate_id: str
    aggregate_revision: int
    payload: dict[str, object]


class ActivityCommit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_id: str
    workspace_id: str
    grant_id: str
    execution_generation: int
    recovery_epoch: str
    payload: dict[str, object]


class ExternalOperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_key: str
    workspace_id: str
    operation_type: str
    recovery_epoch: str
    input_payload: dict[str, object]


class OperationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_key: str
    receipt_id: str
    state: Literal["prepared", "started", "outcome_unknown", "succeeded", "failed"]
    output_refs: dict[str, object]
    attempt: int


class MediaUsageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    media_id: str
    artifact_id: str
    role: str
    time_range: str
    transform_ref: str
    selection_rationale: str


class CompletionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str
    idempotency_key: str
    workspace_id: str
    job_id: str
    batch_id: str
    capacity_reservation_id: str
    variant_reservation_id: str
    expected_variant_registry_revision: int
    output_artifact_id: str
    output_hash: str
    cloud_location_ref: str
    snapshot_ref: str
    script_ref: str
    plan_ref: str
    quality_report_ref: str
    variant_validation_ref: str
    output_metadata_ref: str
    cleanup_policy_ref: str
    grant_id: str
    execution_generation: int
    recovery_epoch: str
    media_usages: list[MediaUsageInput]


class CompletionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str
    receipt_id: str
    completion_id: str
    disposition: Literal["accepted", "duplicate"]
    completed_count: int
    variant_registry_revision: int
    completed_at: datetime


class MediaUsageOwnerPort(Protocol):
    def record_usages(
        self,
        connection: psycopg.Connection,
        *,
        workspace_id: str,
        completion_id: str,
        job_id: str,
        usages: list[dict[str, object]],
        completed_at: datetime,
    ) -> None: ...


class OutboxDispatcher:
    """Deliver one unpublished event and checkpoint only after the callback returns."""

    def __init__(self, dsn: str, consumer: Callable[[DomainEvent], bool]) -> None:
        self._dsn = dsn
        self._consumer = consumer

    def dispatch_next(self, *, inject_failure: str | None = None) -> bool:
        with psycopg.connect(self._dsn) as connection:
            row = connection.execute(
                """
                SELECT event_id, workspace_id, aggregate_id,
                       aggregate_revision, payload
                  FROM outbox_events
                 WHERE published_at IS NULL
                 ORDER BY occurred_at, event_id
                 LIMIT 1
                 FOR UPDATE SKIP LOCKED
                """
            ).fetchone()
            if row is None:
                return False

            event = DomainEvent(
                event_id=row[0],
                workspace_id=row[1],
                aggregate_id=row[2],
                aggregate_revision=row[3],
                payload=row[4],
            )
            self._consumer(event)
            if inject_failure == "after_dispatch_before_checkpoint":
                raise InjectedFailure("after_dispatch_before_checkpoint")

            connection.execute(
                "UPDATE outbox_events SET published_at = %s WHERE event_id = %s",
                (datetime.now(UTC), event.event_id),
            )
            return True


SENSITIVE_KEY_PARTS = ("authorization", "credential", "password", "secret", "token")


def find_sensitive_key(value: object, path: str = "payload") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold()
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                return f"{path}.{key}"
            found = find_sensitive_key(child, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = find_sensitive_key(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def canonical_fingerprint(command: MutationCommand) -> str:
    logical_input = command.model_dump(
        exclude={"command_id", "idempotency_key"},
        mode="json",
    )
    canonical = json.dumps(
        logical_input,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def completion_fingerprint(command: CompletionCommand) -> str:
    logical_input = command.model_dump(
        exclude={"command_id", "idempotency_key"},
        mode="json",
    )
    canonical = json.dumps(
        logical_input,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class ContractProofService:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def execute_mutation(
        self,
        command: MutationCommand,
        *,
        inject_failure: str | None = None,
    ) -> CommandReceipt:
        if find_sensitive_key(command.payload) is not None:
            raise SensitiveDataRejected("SENSITIVE_DATA_REJECTED")
        fingerprint = canonical_fingerprint(command)
        receipt_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"m1-p1:{command.workspace_id}:{command.idempotency_key}",
            )
        )
        now = datetime.now(UTC)

        with psycopg.connect(self._dsn) as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"{command.workspace_id}:{command.idempotency_key}",),
            )
            existing = connection.execute(
                """
                SELECT command_id, receipt_id, payload_fingerprint,
                       resource_revision, accepted_at
                  FROM command_receipts
                 WHERE workspace_id = %s AND idempotency_key = %s
                """,
                (command.workspace_id, command.idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing[2] != fingerprint:
                    raise IdempotencyConflict(
                        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
                    )
                return CommandReceipt(
                    command_id=existing[0],
                    receipt_id=existing[1],
                    disposition="duplicate",
                    resource_revision=existing[3],
                    accepted_at=existing[4],
                )

            current = connection.execute(
                """
                SELECT revision
                  FROM proof_aggregates
                 WHERE workspace_id = %s AND aggregate_id = %s
                 FOR UPDATE
                """,
                (command.workspace_id, command.aggregate_id),
            ).fetchone()
            current_revision = 0 if current is None else current[0]
            if current_revision != command.expected_revision:
                raise ContractProofError(
                    f"REVISION_CONFLICT: expected {command.expected_revision}, "
                    f"observed {current_revision}"
                )
            next_revision = current_revision + 1
            connection.execute(
                """
                INSERT INTO proof_aggregates (
                    workspace_id, aggregate_id, revision, payload, updated_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, aggregate_id) DO UPDATE
                    SET revision = EXCLUDED.revision,
                        payload = EXCLUDED.payload,
                        updated_at = EXCLUDED.updated_at
                """,
                (
                    command.workspace_id,
                    command.aggregate_id,
                    next_revision,
                    Jsonb(command.payload),
                    now,
                ),
            )
            if inject_failure == "after_mutation":
                raise InjectedFailure("after_mutation")

            event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"event:{receipt_id}"))
            event_payload = {
                "aggregate_id": command.aggregate_id,
                "revision": next_revision,
            }
            connection.execute(
                """
                INSERT INTO outbox_events (
                    event_id, workspace_id, aggregate_type, aggregate_id,
                    aggregate_revision, event_name, recovery_epoch, payload,
                    occurred_at
                ) VALUES (%s, %s, 'ProofAggregate', %s, %s,
                          'ProofAggregateChanged', %s, %s, %s)
                """,
                (
                    event_id,
                    command.workspace_id,
                    command.aggregate_id,
                    next_revision,
                    command.recovery_epoch,
                    Jsonb(event_payload),
                    now,
                ),
            )
            result = {
                "aggregate_id": command.aggregate_id,
                "resource_revision": next_revision,
            }
            connection.execute(
                """
                INSERT INTO command_receipts (
                    workspace_id, idempotency_key, command_id, receipt_id,
                    payload_fingerprint, disposition, resource_revision,
                    result, recovery_epoch, execution_generation, accepted_at
                ) VALUES (%s, %s, %s, %s, %s, 'accepted', %s,
                          %s, %s, %s, %s)
                """,
                (
                    command.workspace_id,
                    command.idempotency_key,
                    command.command_id,
                    receipt_id,
                    fingerprint,
                    next_revision,
                    Jsonb(result),
                    command.recovery_epoch,
                    command.execution_generation,
                    now,
                ),
            )

        receipt = CommandReceipt(
            command_id=command.command_id,
            receipt_id=receipt_id,
            disposition="accepted",
            resource_revision=next_revision,
            accepted_at=now,
        )
        if inject_failure == "after_commit_before_ack":
            raise OutcomeUnknown(receipt_id)
        return receipt

    def consume_event(self, consumer_id: str, event: DomainEvent) -> bool:
        now = datetime.now(UTC)
        lock_key = f"{consumer_id}:{event.workspace_id}:{event.aggregate_id}"
        with psycopg.connect(self._dsn) as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (lock_key,),
            )
            duplicate = connection.execute(
                """
                SELECT 1 FROM consumer_event_receipts
                 WHERE consumer_id = %s AND event_id = %s
                """,
                (consumer_id, event.event_id),
            ).fetchone()
            if duplicate is not None:
                return False

            current = connection.execute(
                """
                SELECT aggregate_revision, apply_count
                  FROM consumer_projections
                 WHERE consumer_id = %s AND workspace_id = %s
                   AND aggregate_id = %s
                 FOR UPDATE
                """,
                (consumer_id, event.workspace_id, event.aggregate_id),
            ).fetchone()
            current_revision = 0 if current is None else current[0]
            if event.aggregate_revision > current_revision + 1:
                raise EventGap("EVENT_REVISION_GAP")

            applied = event.aggregate_revision == current_revision + 1
            if applied:
                apply_count = 1 if current is None else current[1] + 1
                connection.execute(
                    """
                    INSERT INTO consumer_projections (
                        consumer_id, workspace_id, aggregate_id,
                        aggregate_revision, payload, apply_count, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (consumer_id, workspace_id, aggregate_id)
                    DO UPDATE SET
                        aggregate_revision = EXCLUDED.aggregate_revision,
                        payload = EXCLUDED.payload,
                        apply_count = EXCLUDED.apply_count,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        consumer_id,
                        event.workspace_id,
                        event.aggregate_id,
                        event.aggregate_revision,
                        Jsonb(event.payload),
                        apply_count,
                        now,
                    ),
                )
            connection.execute(
                """
                INSERT INTO consumer_event_receipts (consumer_id, event_id, observed_at)
                VALUES (%s, %s, %s)
                """,
                (consumer_id, event.event_id, now),
            )
        return applied

    def set_execution_fence(
        self,
        *,
        workspace_id: str,
        grant_id: str,
        execution_generation: int,
        recovery_epoch: str,
    ) -> None:
        with psycopg.connect(self._dsn) as connection:
            connection.execute(
                """
                INSERT INTO execution_fences (
                    workspace_id, grant_id, execution_generation,
                    recovery_epoch, updated_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, grant_id) DO UPDATE SET
                    execution_generation = EXCLUDED.execution_generation,
                    recovery_epoch = EXCLUDED.recovery_epoch,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    workspace_id,
                    grant_id,
                    execution_generation,
                    recovery_epoch,
                    datetime.now(UTC),
                ),
            )

    def commit_activity_result(self, result: ActivityCommit) -> None:
        with psycopg.connect(self._dsn) as connection:
            fence = connection.execute(
                """
                SELECT execution_generation, recovery_epoch
                  FROM execution_fences
                 WHERE workspace_id = %s AND grant_id = %s
                 FOR UPDATE
                """,
                (result.workspace_id, result.grant_id),
            ).fetchone()
            if fence is None or fence[0] != result.execution_generation:
                raise StaleExecution("STALE_EXECUTION_GENERATION")
            if fence[1] != result.recovery_epoch:
                raise StaleExecution("STALE_RECOVERY_EPOCH")
            connection.execute(
                """
                INSERT INTO accepted_activity_results (
                    result_id, workspace_id, grant_id, execution_generation,
                    recovery_epoch, payload, committed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (result_id) DO NOTHING
                """,
                (
                    result.result_id,
                    result.workspace_id,
                    result.grant_id,
                    result.execution_generation,
                    result.recovery_epoch,
                    Jsonb(result.payload),
                    datetime.now(UTC),
                ),
            )

    def prepare_external_operation(
        self, request: ExternalOperationRequest
    ) -> OperationReceipt:
        fingerprint = hashlib.sha256(
            json.dumps(
                request.input_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        receipt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"operation:{request.operation_key}"))
        now = datetime.now(UTC)
        with psycopg.connect(self._dsn) as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (request.operation_key,),
            )
            existing = connection.execute(
                """
                SELECT input_fingerprint FROM operation_receipts
                 WHERE operation_key = %s
                """,
                (request.operation_key,),
            ).fetchone()
            if existing is not None:
                if existing[0] != fingerprint:
                    raise IdempotencyConflict(
                        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
                    )
                return self._load_operation_receipt(connection, request.operation_key)
            connection.execute(
                """
                INSERT INTO operation_receipts (
                    operation_key, receipt_id, workspace_id, operation_type,
                    input_fingerprint, recovery_epoch, state, output_refs,
                    attempt, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 'prepared', %s, 1, %s, %s)
                """,
                (
                    request.operation_key,
                    receipt_id,
                    request.workspace_id,
                    request.operation_type,
                    fingerprint,
                    request.recovery_epoch,
                    Jsonb({}),
                    now,
                    now,
                ),
            )
            return self._load_operation_receipt(connection, request.operation_key)

    def mark_operation_started(self, operation_key: str) -> None:
        self._set_operation_state(operation_key, "started")

    def mark_operation_outcome_unknown(self, operation_key: str) -> None:
        self._set_operation_state(operation_key, "outcome_unknown")

    def retry_external_operation(
        self, request: ExternalOperationRequest
    ) -> OperationReceipt:
        fingerprint = hashlib.sha256(
            json.dumps(
                request.input_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        with psycopg.connect(self._dsn) as connection:
            receipt = self._load_operation_receipt(connection, request.operation_key)
            row = connection.execute(
                """
                SELECT input_fingerprint, state FROM operation_receipts
                 WHERE operation_key = %s
                """,
                (request.operation_key,),
            ).fetchone()
            if row[0] != fingerprint:
                raise IdempotencyConflict(
                    "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
                )
            if row[1] == "outcome_unknown":
                raise ReconciliationRequired("RECONCILIATION_REQUIRED")
            return receipt

    def reconcile_external_operation(
        self, operation_key: str, *, output_refs: dict[str, object]
    ) -> OperationReceipt:
        with psycopg.connect(self._dsn) as connection:
            connection.execute(
                """
                UPDATE operation_receipts
                   SET state = 'succeeded', output_refs = %s, updated_at = %s
                 WHERE operation_key = %s AND state = 'outcome_unknown'
                """,
                (Jsonb(output_refs), datetime.now(UTC), operation_key),
            )
            return self._load_operation_receipt(connection, operation_key)

    def complete_video(
        self,
        command: CompletionCommand,
        *,
        media_usage_port: MediaUsageOwnerPort,
        inject_failure: str | None = None,
    ) -> CompletionReceipt:
        if find_sensitive_key(command.model_dump(mode="python")) is not None:
            raise SensitiveDataRejected("SENSITIVE_DATA_REJECTED")

        fingerprint = completion_fingerprint(command)
        receipt_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"m1-p1-completion-receipt:{command.workspace_id}:{command.idempotency_key}",
            )
        )
        completion_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"m1-p1-completion:{command.workspace_id}:{command.idempotency_key}",
            )
        )
        completed_at = datetime.now(UTC)

        with psycopg.connect(self._dsn) as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"completion:{command.workspace_id}:{command.idempotency_key}",),
            )
            existing = connection.execute(
                """
                SELECT input_fingerprint
                  FROM completion_ledgers
                 WHERE workspace_id = %s AND idempotency_key = %s
                """,
                (command.workspace_id, command.idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing[0] != fingerprint:
                    raise IdempotencyConflict(
                        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
                    )
                return self._load_completion_receipt(
                    connection,
                    command.workspace_id,
                    command.idempotency_key,
                    disposition="duplicate",
                )

            fence = connection.execute(
                """
                SELECT execution_generation, recovery_epoch
                  FROM execution_fences
                 WHERE workspace_id = %s AND grant_id = %s
                 FOR UPDATE
                """,
                (command.workspace_id, command.grant_id),
            ).fetchone()
            if fence is None or fence[0] != command.execution_generation:
                raise StaleExecution("STALE_EXECUTION_GENERATION")
            if fence[1] != command.recovery_epoch:
                raise StaleExecution("STALE_RECOVERY_EPOCH")

            registry = connection.execute(
                """
                SELECT revision FROM variant_registries
                 WHERE workspace_id = %s
                 FOR UPDATE
                """,
                (command.workspace_id,),
            ).fetchone()
            if (
                registry is None
                or registry[0] != command.expected_variant_registry_revision
            ):
                raise ContractProofError("VARIANT_VALIDATION_STALE")

            job = connection.execute(
                """
                SELECT batch_id, state FROM proof_video_jobs
                 WHERE workspace_id = %s AND job_id = %s
                 FOR UPDATE
                """,
                (command.workspace_id, command.job_id),
            ).fetchone()
            if job is None or job != (command.batch_id, "running"):
                raise ContractProofError("JOB_NOT_COMPLETABLE")

            capacity = connection.execute(
                """
                SELECT batch_id, job_id, state FROM batch_capacity_reservations
                 WHERE workspace_id = %s AND reservation_id = %s
                 FOR UPDATE
                """,
                (command.workspace_id, command.capacity_reservation_id),
            ).fetchone()
            if capacity != (command.batch_id, command.job_id, "active"):
                raise ContractProofError("CAPACITY_RESERVATION_INVALID")

            variant = connection.execute(
                """
                SELECT job_id, output_hash, state FROM variant_reservations
                 WHERE workspace_id = %s AND reservation_id = %s
                 FOR UPDATE
                """,
                (command.workspace_id, command.variant_reservation_id),
            ).fetchone()
            if variant != (command.job_id, command.output_hash, "active"):
                raise ContractProofError("VARIANT_RESERVATION_INVALID")

            next_registry_revision = registry[0] + 1
            batch = connection.execute(
                """
                SELECT target_count, completed_count FROM proof_batches
                 WHERE workspace_id = %s AND batch_id = %s
                 FOR UPDATE
                """,
                (command.workspace_id, command.batch_id),
            ).fetchone()
            if batch is None or batch[1] >= batch[0]:
                raise ContractProofError("BATCH_TARGET_ALREADY_REACHED")
            next_completed_count = batch[1] + 1

            usage_manifest = [usage.model_dump(mode="json") for usage in command.media_usages]
            connection.execute(
                """
                INSERT INTO completion_ledgers (
                    workspace_id, completion_id, receipt_id, command_id,
                    idempotency_key, input_fingerprint, job_id, batch_id,
                    output_artifact_id, output_hash, cloud_location_ref,
                    snapshot_ref, script_ref, plan_ref, quality_report_ref,
                    variant_validation_ref, output_metadata_ref,
                    cleanup_policy_ref, media_usage_manifest,
                    variant_registry_revision, completed_count, completed_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    command.workspace_id,
                    completion_id,
                    receipt_id,
                    command.command_id,
                    command.idempotency_key,
                    fingerprint,
                    command.job_id,
                    command.batch_id,
                    command.output_artifact_id,
                    command.output_hash,
                    command.cloud_location_ref,
                    command.snapshot_ref,
                    command.script_ref,
                    command.plan_ref,
                    command.quality_report_ref,
                    command.variant_validation_ref,
                    command.output_metadata_ref,
                    command.cleanup_policy_ref,
                    Jsonb(usage_manifest),
                    next_registry_revision,
                    next_completed_count,
                    completed_at,
                ),
            )
            self._inject(inject_failure, "after_ledger")

            connection.execute(
                """
                UPDATE proof_video_jobs
                   SET state = 'completed', output_hash = %s, completed_at = %s
                 WHERE workspace_id = %s AND job_id = %s
                """,
                (
                    command.output_hash,
                    completed_at,
                    command.workspace_id,
                    command.job_id,
                ),
            )
            self._inject(inject_failure, "after_job")

            connection.execute(
                """
                UPDATE batch_capacity_reservations SET state = 'converted'
                 WHERE workspace_id = %s AND reservation_id = %s
                """,
                (command.workspace_id, command.capacity_reservation_id),
            )
            connection.execute(
                """
                UPDATE proof_batches SET completed_count = %s
                 WHERE workspace_id = %s AND batch_id = %s
                """,
                (next_completed_count, command.workspace_id, command.batch_id),
            )
            self._inject(inject_failure, "after_capacity")

            connection.execute(
                """
                UPDATE variant_reservations SET state = 'converted'
                 WHERE workspace_id = %s AND reservation_id = %s
                """,
                (command.workspace_id, command.variant_reservation_id),
            )
            connection.execute(
                """
                UPDATE variant_registries SET revision = %s
                 WHERE workspace_id = %s
                """,
                (next_registry_revision, command.workspace_id),
            )
            self._inject(inject_failure, "after_variant")

            media_usage_port.record_usages(
                connection,
                workspace_id=command.workspace_id,
                completion_id=completion_id,
                job_id=command.job_id,
                usages=usage_manifest,
                completed_at=completed_at,
            )
            self._inject(inject_failure, "after_media_usage")

            event_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"m1-p1-video-completed:{completion_id}")
            )
            connection.execute(
                """
                INSERT INTO outbox_events (
                    event_id, workspace_id, aggregate_type, aggregate_id,
                    aggregate_revision, event_name, recovery_epoch, payload,
                    occurred_at
                ) VALUES (%s, %s, 'VideoJob', %s, 1, 'VideoCompleted', %s, %s, %s)
                """,
                (
                    event_id,
                    command.workspace_id,
                    command.job_id,
                    command.recovery_epoch,
                    Jsonb(
                        {
                            "completion_id": completion_id,
                            "output_artifact_id": command.output_artifact_id,
                            "output_hash": command.output_hash,
                        }
                    ),
                    completed_at,
                ),
            )
            self._inject(inject_failure, "after_outbox")

            eligibility_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"m1-p1-cleanup:{completion_id}")
            )
            connection.execute(
                """
                INSERT INTO cleanup_eligibilities (
                    workspace_id, eligibility_id, completion_id, job_id,
                    output_hash, cleanup_policy_ref, recovery_epoch, state,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'eligible', %s)
                """,
                (
                    command.workspace_id,
                    eligibility_id,
                    completion_id,
                    command.job_id,
                    command.output_hash,
                    command.cleanup_policy_ref,
                    command.recovery_epoch,
                    completed_at,
                ),
            )
            self._inject(inject_failure, "after_cleanup_eligibility")

            receipt = self._load_completion_receipt(
                connection,
                command.workspace_id,
                command.idempotency_key,
                disposition="accepted",
            )

        if inject_failure == "after_commit_before_ack":
            raise OutcomeUnknown(receipt.receipt_id)
        return receipt

    def _set_operation_state(self, operation_key: str, state: str) -> None:
        with psycopg.connect(self._dsn) as connection:
            updated = connection.execute(
                """
                UPDATE operation_receipts
                   SET state = %s, updated_at = %s
                 WHERE operation_key = %s
                """,
                (state, datetime.now(UTC), operation_key),
            )
            if updated.rowcount != 1:
                raise ContractProofError("OPERATION_NOT_FOUND")

    @staticmethod
    def _inject(inject_failure: str | None, boundary: str) -> None:
        if inject_failure == boundary:
            raise InjectedFailure(boundary)

    @staticmethod
    def _load_completion_receipt(
        connection: psycopg.Connection,
        workspace_id: str,
        idempotency_key: str,
        *,
        disposition: Literal["accepted", "duplicate"],
    ) -> CompletionReceipt:
        row = connection.execute(
            """
            SELECT command_id, receipt_id, completion_id, completed_count,
                   variant_registry_revision, completed_at
              FROM completion_ledgers
             WHERE workspace_id = %s AND idempotency_key = %s
            """,
            (workspace_id, idempotency_key),
        ).fetchone()
        if row is None:
            raise ContractProofError("COMPLETION_RECEIPT_NOT_FOUND")
        return CompletionReceipt(
            command_id=row[0],
            receipt_id=row[1],
            completion_id=row[2],
            disposition=disposition,
            completed_count=row[3],
            variant_registry_revision=row[4],
            completed_at=row[5],
        )

    @staticmethod
    def _load_operation_receipt(
        connection: psycopg.Connection, operation_key: str
    ) -> OperationReceipt:
        row = connection.execute(
            """
            SELECT operation_key, receipt_id, state, output_refs, attempt
              FROM operation_receipts
             WHERE operation_key = %s
            """,
            (operation_key,),
        ).fetchone()
        if row is None:
            raise ContractProofError("OPERATION_NOT_FOUND")
        return OperationReceipt(
            operation_key=row[0],
            receipt_id=row[1],
            state=row[2],
            output_refs=row[3],
            attempt=row[4],
        )
