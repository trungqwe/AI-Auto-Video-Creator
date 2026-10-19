"""A-10 SourceCandidate evaluation and registration (CT-SRC-003A, CT-STATE-002A).

Each command runs in one Unit of Work holding candidate, source, CommandReceipt and outbox writes.
Registration re-reads canonical identity (source or tombstone) and policy inside that UoW. The default
policy provider returns None, so production auto-registration stays NOT_READY until a Tier policy exists.
Event payloads carry refs, revision, disposition and a fixed reason code only (A-RULE-014).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlsplit
import uuid

from controlplane.application.idempotency import request_hash
from controlplane.domain.events import DomainEvent
from controlplane.domain.interfaces.outbox import IOutboxWriter
from source_ingestion.application.source_commands import (
    AGGREGATE_TYPE as SOURCE_AGGREGATE_TYPE,
    CONTRACT_NAME as SOURCE_CONTRACT_NAME,
    CONTRACT_VERSION,
    EVENT_REGISTERED,
    IdempotencyConflictError,
)
from source_ingestion.domain import source as source_domain
from source_ingestion.domain import source_candidate as candidate_domain
from source_ingestion.domain.locator import Resolver, validate_locator
from source_ingestion.domain.source import Source, SourcePolicy
from source_ingestion.domain.source_candidate import (
    REVISION_CONFLICT,
    WAITING_POLICY,
    CandidateStatus,
    RegistrationPolicy,
    SourceCandidate,
)
from source_ingestion.ports.repositories import (
    CommandReceipt,
    ReceiptStore,
    SourceCandidateRepository,
    SourceRepository,
)

COMMAND_EVALUATE = 'EvaluateSourceCandidate'
COMMAND_REGISTER = 'RegisterSourceCandidate'
EVENT_DISCOVERED = 'SourceCandidateDiscovered'
EVENT_RESOLVED = 'SourceCandidateResolved'
AGGREGATE_TYPE = 'SourceCandidate'
CONTRACT_NAME = 'source_ingestion.source_candidate'
PRODUCER = 'A'
SCHEMA_VERSION = '1.0.0'
SENSITIVITY = 'internal'
AUTO_REGISTRATION_READY = 'READY'
AUTO_REGISTRATION_NOT_READY = 'NOT_READY'
DISPOSITION_DISCOVERED = 'DISCOVERED'
REASON_DISCOVERED = 'CANDIDATE_DISCOVERED'
RESOLVED_REASONS = {
    CandidateStatus.MATCHED_EXISTING: 'IDENTITY_MATCHES_SOURCE',
    CandidateStatus.BLOCKED_TOMBSTONE: 'IDENTITY_MATCHES_TOMBSTONE',
    CandidateStatus.REJECTED: 'POLICY_FORBIDS',
    CandidateStatus.REGISTERED: 'REGISTERED_BY_POLICY',
}


class CandidateNotFoundError(LookupError):
    def __init__(self, candidate_id: str) -> None:
        self.code = 'CANDIDATE_NOT_FOUND'
        self.candidate_id = candidate_id
        super().__init__(self.code)


class PolicyRevisionMismatchError(ValueError):
    def __init__(self, current_revision: str, requested_revision: str) -> None:
        self.code = 'POLICY_REVISION_MISMATCH'
        self.current_revision = current_revision
        self.requested_revision = requested_revision
        super().__init__(self.code)


@dataclass(frozen=True)
class CandidateCommandResult:
    code: str
    candidate: SourceCandidate
    current_revision: int
    reason: str | None
    receipt: CommandReceipt | None
    replayed: bool
    source_ref: str | None
    tombstone_ref: str | None


@dataclass(frozen=True)
class _EventContext:
    workspace_id: str
    actor: str
    correlation_id: str
    at: datetime


class CandidateUnitOfWork(Protocol):
    sources: SourceRepository
    candidates: SourceCandidateRepository
    receipts: ReceiptStore
    outbox: IOutboxWriter

    def commit(self) -> None: ...
    def __enter__(self) -> CandidateUnitOfWork: ...
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None: ...


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string.')
    return value


def _require_revision(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError('expected_revision must be an int >= 1')
    return value


def _names_for_hash(values: object, field: str) -> list[str]:
    if isinstance(values, str) or not isinstance(values, Iterable):
        raise ValueError(f'{field} must be a collection of strings')
    items = list(values)
    if any(not isinstance(item, str) for item in items):
        raise ValueError(f'{field} must be a collection of strings')
    return sorted(set(items))


def no_tier_policy(workspace_id: str) -> RegistrationPolicy | None:
    """Production default: no Tier policy is approved yet, so registration waits (NOT_READY)."""
    return None


def auto_registration_readiness(policy: RegistrationPolicy | None) -> str:
    ready = (
        policy is not None and policy.auto_registration_enabled and policy.permitted
        and policy.source_kind is not None and bool(policy.topics) and policy.tier is not None
    )
    return AUTO_REGISTRATION_READY if ready else AUTO_REGISTRATION_NOT_READY


def _result(
    code: str, candidate: SourceCandidate, *, receipt: CommandReceipt | None, replayed: bool, reason: str | None = None,
) -> CandidateCommandResult:
    return CandidateCommandResult(
        code=code, candidate=candidate, current_revision=candidate.revision,
        reason=reason if reason is not None else candidate.reason, receipt=receipt, replayed=replayed,
        source_ref=candidate.registered_source_ref or candidate.matched_source_ref,
        tombstone_ref=candidate.matched_tombstone_ref,
    )


def _candidate_payload(candidate: SourceCandidate, disposition: str, reason: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'candidate_id': candidate.candidate_id, 'revision': candidate.revision,
        'disposition': disposition, 'reason': reason,
    }
    source_ref = candidate.registered_source_ref or candidate.matched_source_ref
    if source_ref is not None:
        payload['source_ref'] = source_ref
    if candidate.matched_tombstone_ref is not None:
        payload['tombstone_ref'] = candidate.matched_tombstone_ref
    return payload


class CandidateRegistrationHandler:
    def __init__(
        self, *, uow: CandidateUnitOfWork, resolver: Resolver, recovery_epoch: str,
        policy_provider: Callable[[str], RegistrationPolicy | None] = no_tier_policy,
        clock: Callable[[], datetime] | None = None, new_id: Callable[[], str] | None = None,
    ) -> None:
        _require_text(recovery_epoch, 'recovery_epoch')
        self._uow = uow
        self._resolver = resolver
        self._recovery_epoch = recovery_epoch
        self._policy_provider = policy_provider
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._new_id = new_id if new_id is not None else lambda: str(uuid.uuid4())

    def readiness(self, workspace_id: str) -> str:
        return auto_registration_readiness(self._policy_provider(workspace_id))

    def _replay(
        self, uow: CandidateUnitOfWork, workspace_id: str, idempotency_key: str, digest: str,
    ) -> CandidateCommandResult | None:
        stored = uow.receipts.get(workspace_id, idempotency_key)
        if stored is None:
            return None
        if stored.request_hash != digest:
            raise IdempotencyConflictError(idempotency_key, stored.request_hash, digest)
        candidate = uow.candidates.get(workspace_id, stored.aggregate_ref)
        if candidate is None:
            raise CandidateNotFoundError(stored.aggregate_ref)
        return _result(candidate.status.value, candidate, receipt=stored, replayed=True)

    def _current_policy(self, workspace_id: str, policy_revision: str) -> RegistrationPolicy | None:
        policy = self._policy_provider(workspace_id)
        if policy is not None and policy.revision != policy_revision:
            raise PolicyRevisionMismatchError(policy.revision, policy_revision)
        return policy

    def _emit(
        self, uow: CandidateUnitOfWork, ctx: _EventContext, *, event_name: str, aggregate_type: str,
        contract_name: str, aggregate_id: str, revision: int, payload: dict[str, Any],
    ) -> None:
        event = DomainEvent(
            contract_name=contract_name, contract_version=CONTRACT_VERSION, message_id=self._new_id(),
            workspace_id=ctx.workspace_id, correlation_id=ctx.correlation_id, causation_id=None, trace_context=None,
            occurred_at=ctx.at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'), actor=ctx.actor,
            recovery_epoch=self._recovery_epoch, payload=payload, event_id=self._new_id(), event_name=event_name,
            aggregate_type=aggregate_type, aggregate_id=aggregate_id, aggregate_revision=revision,
            producer=PRODUCER, schema_version=SCHEMA_VERSION, sensitivity=SENSITIVITY,
        )
        uow.outbox.append_event(
            event.event_name, event.aggregate_id, dataclasses.asdict(event),
            f'{ctx.workspace_id}:{event_name}:{aggregate_id}:{revision}',
        )

    def _emit_candidate(
        self, uow: CandidateUnitOfWork, ctx: _EventContext, candidate: SourceCandidate,
        event_name: str, disposition: str, reason: str,
    ) -> None:
        self._emit(
            uow, ctx, event_name=event_name, aggregate_type=AGGREGATE_TYPE, contract_name=CONTRACT_NAME,
            aggregate_id=candidate.candidate_id, revision=candidate.revision,
            payload=_candidate_payload(candidate, disposition, reason),
        )


    def evaluate_source_candidate(
        self, *, workspace_id: str, idempotency_key: str, actor: str, correlation_id: str,
        observed_locator: str, discovery_method: str, discovery_evidence: str, policy_revision: str,
        source_kind_candidates: Iterable[str] = (), topic_candidates: Iterable[str] = (),
    ) -> CandidateCommandResult:
        for field, value in (
            ('workspace_id', workspace_id), ('idempotency_key', idempotency_key), ('actor', actor),
            ('correlation_id', correlation_id), ('observed_locator', observed_locator),
            ('discovery_method', discovery_method), ('discovery_evidence', discovery_evidence),
            ('policy_revision', policy_revision),
        ):
            _require_text(value, field)
        kinds = _names_for_hash(source_kind_candidates, 'source_kind_candidates')
        topics = _names_for_hash(topic_candidates, 'topic_candidates')
        digest = request_hash({
            'command_name': COMMAND_EVALUATE, 'workspace_id': workspace_id,
            'payload': {
                'observed_locator': observed_locator, 'discovery_method': discovery_method,
                'discovery_evidence': discovery_evidence, 'policy_revision': policy_revision,
                'source_kind_candidates': kinds, 'topic_candidates': topics,
            },
        })
        ctx = _EventContext(workspace_id, actor, correlation_id, self._clock())
        with self._uow as uow:
            replayed = self._replay(uow, workspace_id, idempotency_key, digest)
            if replayed is not None:
                return replayed
            self._current_policy(workspace_id, policy_revision)
            canonical = validate_locator(observed_locator, self._resolver).locator
            discovered = candidate_domain.discover_candidate(
                candidate_id=self._new_id(), workspace_id=workspace_id, observed_locator=observed_locator,
                canonical_locator=canonical, discovery_method=discovery_method,
                discovery_evidence=discovery_evidence, source_kind_candidates=kinds, topic_candidates=topics,
                actor=actor, at=ctx.at,
            )
            uow.candidates.add(discovered)
            validating = candidate_domain.begin_validation(
                discovered, expected_revision=discovered.revision, actor=actor, at=ctx.at,
            ).candidate
            uow.candidates.save(validating)
            identity = uow.sources.resolve_identity(workspace_id, canonical)
            final = candidate_domain.complete_validation(
                validating, expected_revision=validating.revision, identity=identity,
                validation_passed=True, actor=actor, at=ctx.at,
            ).candidate
            uow.candidates.save(final)
            receipt = CommandReceipt(workspace_id, idempotency_key, digest, final.candidate_id, final.revision)
            uow.receipts.put(receipt)
            self._emit_candidate(uow, ctx, discovered, EVENT_DISCOVERED, DISPOSITION_DISCOVERED, REASON_DISCOVERED)
            if final.is_terminal:
                self._emit_candidate(uow, ctx, final, EVENT_RESOLVED, final.status.value, RESOLVED_REASONS[final.status])
            uow.commit()
        return _result(final.status.value, final, receipt=receipt, replayed=False)


    def register_source_candidate(
        self, *, workspace_id: str, idempotency_key: str, actor: str, correlation_id: str,
        candidate_id: str, expected_revision: int, policy_revision: str,
    ) -> CandidateCommandResult:
        for field, value in (
            ('workspace_id', workspace_id), ('idempotency_key', idempotency_key), ('actor', actor),
            ('correlation_id', correlation_id), ('candidate_id', candidate_id), ('policy_revision', policy_revision),
        ):
            _require_text(value, field)
        _require_revision(expected_revision)
        digest = request_hash({
            'command_name': COMMAND_REGISTER, 'workspace_id': workspace_id,
            'payload': {'candidate_id': candidate_id, 'expected_revision': expected_revision, 'policy_revision': policy_revision},
        })
        ctx = _EventContext(workspace_id, actor, correlation_id, self._clock())
        with self._uow as uow:
            replayed = self._replay(uow, workspace_id, idempotency_key, digest)
            if replayed is not None:
                return replayed
            candidate = uow.candidates.get(workspace_id, candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(candidate_id)
            policy = self._current_policy(workspace_id, policy_revision)
            identity = uow.sources.resolve_identity(workspace_id, candidate.canonical_locator)
            decision = candidate_domain.register_candidate(
                candidate, expected_revision=expected_revision, identity=identity, policy=policy,
                new_source_ref=self._new_id(), actor=actor, at=ctx.at,
            )
            if decision.code in (WAITING_POLICY, REVISION_CONFLICT):
                return _result(decision.code, decision.candidate, receipt=None, replayed=False, reason=decision.reason)
            final = decision.candidate
            uow.candidates.save(final)
            source = self._new_source(final, actor, ctx.at) if final.status is CandidateStatus.REGISTERED else None
            if source is not None:
                uow.sources.add(source)
            receipt = CommandReceipt(workspace_id, idempotency_key, digest, final.candidate_id, final.revision)
            uow.receipts.put(receipt)
            if source is not None:
                self._emit(
                    uow, ctx, event_name=EVENT_REGISTERED, aggregate_type=SOURCE_AGGREGATE_TYPE,
                    contract_name=SOURCE_CONTRACT_NAME, aggregate_id=source.source_id, revision=source.revision,
                    payload={
                        'source_id': source.source_id, 'revision': source.revision, 'status': source.status.value,
                        'source_kind': source.source_kind, 'tier': source.tier, 'policy_revision': source.policy_revision,
                    },
                )
            self._emit_candidate(uow, ctx, final, EVENT_RESOLVED, final.status.value, RESOLVED_REASONS[final.status])
            uow.commit()
        return _result(final.status.value, final, receipt=receipt, replayed=False)


    @staticmethod
    def _new_source(candidate: SourceCandidate, actor: str, at: datetime) -> Source:
        return source_domain.register_source(
            source_id=str(candidate.registered_source_ref), workspace_id=candidate.workspace_id,
            canonical_locator=candidate.canonical_locator,
            name=urlsplit(candidate.canonical_locator).hostname or candidate.canonical_locator,
            source_kind=str(candidate.source_kind), tier=str(candidate.tier), topics=candidate.topics,
            notes='', collection_enabled=True, admin_metadata={}, actor=actor, at=at,
            policy=SourcePolicy(
                policy_revision=str(candidate.policy_revision), source_kinds=frozenset({str(candidate.source_kind)}),
                tiers=frozenset({str(candidate.tier)}), admin_metadata_keys=frozenset(),
            ),
        )


__all__ = [
    'AUTO_REGISTRATION_NOT_READY', 'AUTO_REGISTRATION_READY', 'COMMAND_EVALUATE', 'COMMAND_REGISTER',
    'EVENT_DISCOVERED', 'EVENT_RESOLVED', 'CandidateCommandResult', 'CandidateNotFoundError',
    'CandidateRegistrationHandler', 'CandidateUnitOfWork', 'PolicyRevisionMismatchError',
    'auto_registration_readiness', 'no_tier_policy',
]
