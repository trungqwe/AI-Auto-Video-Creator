"""SUPPLEMENTAL collection per video (A-16; A-RULE-002, A-RULE-005).

G passes job, scene, intent and budget refs through an ExecutionGrant. A checks the grant and the source
tombstone before every fetch, records the work as a CollectionRun with purpose SUPPLEMENTAL, never creates or
counts a periodic run and never moves the source checkpoint shared with the periodic run. A new package goes to B
through ContentHandoffPort. Handoff C (media to C) is not wired here: it waits for CT-MED-001 (CONV-A-07).
"""
from __future__ import annotations

import dataclasses
import datetime
import enum
from collections.abc import Callable, Mapping

from controlplane.domain.orchestration import ExecutionGrant

from source_ingestion.application.collect_source import (
    ERROR_ADAPTER_CONTRACT,
    ERROR_ADAPTER_EXCEPTION,
    ERROR_FINGERPRINT_MISSING,
    ERROR_INVALID_LOCATOR,
    ERROR_ITEM_COMMIT,
    ERROR_ITEM_FAILED,
    ERROR_VALIDATION,
    EVENT_DOCUMENT_AVAILABLE,
    CollectionUnitOfWork,
    ItemError,
    _available_payload,
    _checkpoint_ref,
    _exception_text,
    _failure,
    _item_error,
    _observation_fingerprint,
    _utc_now,
)
from source_ingestion.application.package_builder import HtmlExtractor, PackageContext, build_package
from source_ingestion.domain.collection_run import (
    TERMINAL_STATUSES,
    AttemptOutcome,
    CollectionPurpose,
    CollectionRun,
    RetryPolicy,
    RunStatus,
    TerminalReason,
    deactivate_source,
    record_attempt_outcome,
    record_committed_packages,
    resume_retry,
    schedule_run,
    start_run,
)
from source_ingestion.domain.locator import LocatorError, canonicalize_locator
from source_ingestion.domain.package import ExtractionPolicy, PackageValidationError, validate_package_schema
from source_ingestion.domain.source import Source, SourceStatus
from source_ingestion.domain.source_candidate import IdentityMatchKind
from source_ingestion.ports.partners import ActivityGrantPort, ContentHandoffPort
from source_ingestion.ports.repositories import PackageRecord
from source_ingestion.ports.source_adapter import CandidateListing, FetchedDocument, SourceAdapter

ERROR_GRANT_NOT_CURRENT = 'GRANT_NOT_CURRENT'
ERROR_GRANT_SCOPE_MISMATCH = 'GRANT_SCOPE_MISMATCH'
ERROR_SOURCE_NOT_FOUND = 'SOURCE_NOT_FOUND'
ERROR_SOURCE_TOMBSTONED = 'SOURCE_TOMBSTONED'
ERROR_SOURCE_INACTIVE = 'SOURCE_INACTIVE'
ERROR_RUN_CONFLICT = 'RUN_ID_CONFLICT'
ERROR_HANDOFF_B = 'HANDOFF_B_FAILED'
ERROR_HANDOFF_B_CONTRACT = 'HANDOFF_B_CONTRACT_VIOLATION'
REASON_BUDGET_EXHAUSTED = 'BUDGET_EXHAUSTED'
REASON_DEADLINE_EXCEEDED = 'DEADLINE_EXCEEDED'
REASON_RETRY_EXHAUSTED = 'RETRY_EXHAUSTED'
REASON_NO_CANDIDATES = 'NO_CANDIDATES'
REASON_NO_NEW_PACKAGES = 'NO_NEW_PACKAGES'
REASON_PREFIX = 'SUPPLEMENTAL_REASON:'
B_DISPOSITIONS = frozenset({
    'NEW_ARTICLE',
    'NEW_REVISION',
    'DUPLICATE_MEDIA_ONLY',
    'DUPLICATE_NO_NEW_VALUE',
    'REJECTED_INCOMPLETE',
})


class SupplementalOutcome(str, enum.Enum):
    FOUND = 'FOUND'
    PARTIAL = 'PARTIAL'
    NOT_FOUND = 'NOT_FOUND'
    BLOCKED = 'BLOCKED'
    FAILED = 'FAILED'



def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string')
    return value


@dataclasses.dataclass(frozen=True)
class SupplementalBudget:
    budget_ref: str
    max_fetches: int
    deadline_at: datetime.datetime

    def __post_init__(self) -> None:
        _require_text(self.budget_ref, 'budget_ref')
        if type(self.max_fetches) is not int or self.max_fetches < 1:
            raise ValueError('max_fetches must be an int >= 1')
        if not isinstance(self.deadline_at, datetime.datetime) or self.deadline_at.utcoffset() is None:
            raise ValueError('deadline_at must be a timezone-aware datetime')


@dataclasses.dataclass(frozen=True)
class SupplementalRequest:
    workspace_id: str
    source_id: str
    run_id: str
    job_id: str
    scene_ref: str
    intent_ref: str
    intent: Mapping[str, str]
    budget: SupplementalBudget
    grant: ExecutionGrant
    retry_policy: RetryPolicy
    extraction_policy: ExtractionPolicy | None = None

    def __post_init__(self) -> None:
        for name in ('workspace_id', 'source_id', 'run_id', 'job_id', 'scene_ref', 'intent_ref'):
            _require_text(getattr(self, name), name)
        if not isinstance(self.intent, Mapping) or not self.intent:
            raise ValueError('intent must be a non-empty mapping')
        for key, value in self.intent.items():
            _require_text(key, 'intent key')
            _require_text(value, 'intent value')
        object.__setattr__(self, 'intent', dict(self.intent))
        if not isinstance(self.budget, SupplementalBudget):
            raise ValueError('budget must be a SupplementalBudget')
        if not isinstance(self.grant, ExecutionGrant):
            raise ValueError('grant must be an ExecutionGrant')
        if not isinstance(self.retry_policy, RetryPolicy):
            raise ValueError('retry_policy must be a RetryPolicy')
        if self.extraction_policy is not None and not isinstance(self.extraction_policy, ExtractionPolicy):
            raise ValueError('extraction_policy must be an ExtractionPolicy')


@dataclasses.dataclass(frozen=True)
class SupplementalJob:
    request: SupplementalRequest
    adapter: SourceAdapter
    extractor: HtmlExtractor



@dataclasses.dataclass(frozen=True)
class SupplementalDiscovery:
    """Media discovery with its provenance; new_package is False when the article already existed."""

    package_ref: str
    new_package: bool
    discovery: Mapping[str, object]


@dataclasses.dataclass(frozen=True)
class SupplementalResult:
    outcome: SupplementalOutcome
    reason: str | None
    run_id: str | None
    status: RunStatus | None
    job_id: str
    scene_ref: str
    intent_ref: str
    budget_ref: str
    urls_seen: int
    fetched: int
    skipped: int
    failed: int
    blocked: int
    packages_committed: int
    package_refs: tuple[str, ...]
    discoveries: tuple[SupplementalDiscovery, ...]
    resolutions: tuple[Mapping[str, object], ...]
    errors: tuple[ItemError, ...]
    replayed: bool = False




@dataclasses.dataclass
class _Tally:
    fetch_attempts: int = 0
    fetched: int = 0
    skipped: int = 0
    failed: int = 0
    blocked: int = 0
    errors: list[ItemError] = dataclasses.field(default_factory=list)
    discoveries: list[SupplementalDiscovery] = dataclasses.field(default_factory=list)
    resolutions: list[Mapping[str, object]] = dataclasses.field(default_factory=list)


def _expired(request: SupplementalRequest, clock: Callable[[], datetime.datetime]) -> bool:
    return clock() >= request.budget.deadline_at


def _source_block(source: Source | None) -> str | None:
    if source is None:
        return ERROR_SOURCE_NOT_FOUND
    if source.status is SourceStatus.REMOVED_TOMBSTONE:
        return ERROR_SOURCE_TOMBSTONED
    if source.status is not SourceStatus.ACTIVE:
        return ERROR_SOURCE_INACTIVE
    return None


def _outcome_from_run(run: CollectionRun) -> SupplementalOutcome:
    decision = run.terminal_decision
    if run.status is RunStatus.COMPLETED_PARTIAL:
        return SupplementalOutcome.PARTIAL
    if run.status is RunStatus.COMPLETED:
        return SupplementalOutcome.FOUND if run.committed_package_count > 0 else SupplementalOutcome.NOT_FOUND
    if run.status is RunStatus.FAILED_FINAL and decision is not None:
        if decision.reason is TerminalReason.RETRY_EXHAUSTED:
            return SupplementalOutcome.NOT_FOUND
        if decision.reason is TerminalReason.SOURCE_INACTIVE:
            return SupplementalOutcome.BLOCKED
    return SupplementalOutcome.FAILED


def _stored_reason(run: CollectionRun) -> str | None:
    for warning in reversed(run.warnings):
        if warning.startswith(REASON_PREFIX):
            return warning[len(REASON_PREFIX):] or None
    return None


def _discoveries(record: PackageRecord, new_package: bool) -> list[SupplementalDiscovery]:
    ref = str(record.payload['collected_document_id'])
    media = record.payload.get('media_discoveries') or ()
    return [SupplementalDiscovery(ref, new_package, dict(item)) for item in media if isinstance(item, Mapping)]


def _stored_discoveries(records: tuple[PackageRecord, ...]) -> tuple[SupplementalDiscovery, ...]:
    found: list[SupplementalDiscovery] = []
    for record in records:
        found.extend(_discoveries(record, True))
    return tuple(found)


def _blocked(request: SupplementalRequest, code: str) -> SupplementalResult:
    return SupplementalResult(
        outcome=SupplementalOutcome.BLOCKED, reason=code, run_id=None, status=None,
        job_id=request.job_id, scene_ref=request.scene_ref, intent_ref=request.intent_ref,
        budget_ref=request.budget.budget_ref,
        urls_seen=0, fetched=0, skipped=0, failed=0, blocked=0, packages_committed=0,
        package_refs=(), discoveries=(), resolutions=(), errors=(_item_error('', code),),
    )


def _build_result(
    uow: CollectionUnitOfWork,
    request: SupplementalRequest,
    run: CollectionRun,
    tally: _Tally,
    reason: str | None,
    *,
    replayed: bool = False,
) -> SupplementalResult:
    records = uow.packages.list_by_run(run.run_id)
    return SupplementalResult(
        outcome=_outcome_from_run(run), reason=reason, run_id=run.run_id, status=run.status,
        job_id=request.job_id, scene_ref=request.scene_ref, intent_ref=request.intent_ref,
        budget_ref=request.budget.budget_ref,
        urls_seen=tally.fetch_attempts, fetched=tally.fetched, skipped=tally.skipped, failed=tally.failed,
        blocked=tally.blocked, packages_committed=run.committed_package_count,
        package_refs=tuple(str(r.payload['collected_document_id']) for r in records),
        discoveries=_stored_discoveries(records) if replayed else tuple(tally.discoveries),
        resolutions=tuple(tally.resolutions), errors=tuple(tally.errors), replayed=replayed,
    )



def _prepare(job: SupplementalJob, source: Source, run: CollectionRun, document: FetchedDocument, fetched_at: datetime.datetime):
    """Build the package and pass the A-02 layer-1 gate; returns (package, canonical, fingerprint) or an error code."""
    try:
        package = build_package(
            document,
            job.extractor,
            PackageContext(
                source_id=source.source_id,
                source_revision=source.revision,
                collection_run_id=run.run_id,
                fetched_at=fetched_at,
            ),
            extraction_policy=job.request.extraction_policy,
            source_kind=source.source_kind,
        )
        if validate_package_schema(package):
            return ERROR_VALIDATION
        fingerprint = _observation_fingerprint(package)
        if fingerprint is None:
            return ERROR_FINGERPRINT_MISSING
        return package, canonicalize_locator(str(package['final_url'])), fingerprint
    except PackageValidationError:
        return ERROR_VALIDATION
    except LocatorError:
        return ERROR_INVALID_LOCATOR
    except Exception:
        return ERROR_ITEM_FAILED


def _supplemental_payload(
    request: SupplementalRequest, package: dict[str, object], canonical: str, fingerprint: str
) -> dict[str, object]:
    return {
        **_available_payload(package, canonical, fingerprint),
        'purpose': CollectionPurpose.SUPPLEMENTAL.value,
        'job_id': request.job_id,
        'scene_ref': request.scene_ref,
        'intent_ref': request.intent_ref,
        'budget_ref': request.budget.budget_ref,
    }


def _hand_off_to_b(content_port: ContentHandoffPort, package: dict[str, object], locator: str, tally: _Tally) -> None:
    try:
        resolution = content_port.resolve_collected_document(dict(package))
    except Exception as exc:
        tally.failed += 1
        tally.errors.append(_item_error(locator, ERROR_HANDOFF_B, _exception_text(exc)))
        return
    if (
        not isinstance(resolution, Mapping)
        or resolution.get('collected_document_id') != package['collected_document_id']
        or resolution.get('disposition') not in B_DISPOSITIONS
    ):
        tally.failed += 1
        tally.errors.append(_item_error(locator, ERROR_HANDOFF_B_CONTRACT))
        return
    tally.resolutions.append(dict(resolution))



def _collect_item(
    uow: CollectionUnitOfWork,
    job: SupplementalJob,
    source: Source,
    run: CollectionRun,
    locator: str,
    tally: _Tally,
    content_port: ContentHandoffPort,
    clock: Callable[[], datetime.datetime],
) -> CollectionRun:
    """Tombstone-check, fetch, build, gate and commit one item in its own UoW, then hand it to B."""
    request = job.request
    try:
        requested = canonicalize_locator(locator)
    except LocatorError:
        tally.failed += 1
        tally.errors.append(_item_error(locator, ERROR_INVALID_LOCATOR))
        return run
    if uow.sources.resolve_identity(request.workspace_id, requested).kind is IdentityMatchKind.TOMBSTONE:
        tally.blocked += 1
        tally.errors.append(_item_error(locator, ERROR_SOURCE_TOMBSTONED))
        return run
    tally.fetch_attempts += 1
    try:
        fetched = job.adapter.fetch_document(locator)
    except Exception as exc:
        tally.failed += 1
        tally.errors.append(_item_error(locator, ERROR_ADAPTER_EXCEPTION, _exception_text(exc)))
        return run
    failure = _failure(fetched)
    if failure is not None or not isinstance(fetched, FetchedDocument):
        tally.failed += 1
        tally.errors.append(_item_error(locator, failure[0] if failure is not None else ERROR_ADAPTER_CONTRACT))
        return run
    tally.fetched += 1
    prepared = _prepare(job, source, run, fetched, clock())
    if isinstance(prepared, str):
        tally.failed += 1
        tally.errors.append(_item_error(locator, prepared))
        return run
    package, canonical, fingerprint = prepared
    existing = uow.packages.get(source.source_id, canonical, fingerprint)
    if existing is not None:
        tally.skipped += 1
        tally.discoveries.extend(_discoveries(existing, False))
        return run
    record = PackageRecord(source.source_id, canonical, fingerprint, run.run_id, package)
    try:
        with uow:
            uow.packages.add(record)
            advanced = record_committed_packages(run, 1)
            uow.runs.save(advanced)
            uow.outbox.append_event(
                EVENT_DOCUMENT_AVAILABLE,
                str(package['collected_document_id']),
                _supplemental_payload(request, package, canonical, fingerprint),
                f'{EVENT_DOCUMENT_AVAILABLE}:{source.source_id}:{canonical}:{fingerprint}',
            )
            uow.commit()
    except Exception as exc:
        tally.failed += 1
        tally.errors.append(_item_error(locator, ERROR_ITEM_COMMIT, _exception_text(exc)))
        return run
    tally.discoveries.extend(_discoveries(record, True))
    _hand_off_to_b(content_port, package, locator, tally)
    return advanced



def _open_run(uow: CollectionUnitOfWork, request: SupplementalRequest, clock: Callable[[], datetime.datetime]) -> CollectionRun:
    run = start_run(
        schedule_run(
            run_id=request.run_id,
            workspace_id=request.workspace_id,
            source_id=request.source_id,
            business_date=clock().date(),
            purpose=CollectionPurpose.SUPPLEMENTAL,
            retry_policy=request.retry_policy,
        ),
        source_active=True,
        checkpoint_ref=_checkpoint_ref(uow, request.source_id),
    )
    with uow:
        uow.runs.add(run)
        uow.commit()
    return run


def _resume(
    uow: CollectionUnitOfWork,
    request: SupplementalRequest,
    run: CollectionRun,
    clock: Callable[[], datetime.datetime],
) -> CollectionRun:
    expired = _expired(request, clock)
    resumed = resume_retry(
        run, source_active=True, deadline_passed=expired, checkpoint_ref=_checkpoint_ref(uow, request.source_id)
    )
    if resumed.status in TERMINAL_STATUSES:
        reason = REASON_DEADLINE_EXCEEDED if expired else REASON_RETRY_EXHAUSTED
        resumed = dataclasses.replace(resumed, warnings=run.warnings + (REASON_PREFIX + reason,))
    with uow:
        uow.runs.save(resumed)
        uow.commit()
    return resumed


def _conclude(
    uow: CollectionUnitOfWork,
    request: SupplementalRequest,
    run: CollectionRun,
    tally: _Tally,
    reason: str | None,
    outcome: AttemptOutcome,
    *,
    deadline_passed: bool = False,
    source_inactive: bool = False,
) -> SupplementalResult:
    """Close the attempt: terminal or waiting state, warnings and the reason marker; never touches the checkpoint."""
    ref = _checkpoint_ref(uow, request.source_id)
    if source_inactive:
        run = deactivate_source(run, checkpoint_ref=ref)
    else:
        run = record_attempt_outcome(
            run, outcome, source_active=True, deadline_passed=deadline_passed, checkpoint_ref=ref
        )
    notes = tuple(dict.fromkeys(f'{e.code}:{e.locator}' if e.locator else e.code for e in tally.errors))
    fresh = tuple(note for note in notes if note not in run.warnings)
    run = dataclasses.replace(run, warnings=run.warnings + fresh + (REASON_PREFIX + (reason or ''),))
    with uow:
        uow.runs.save(run)
        uow.commit()
    return _build_result(uow, request, run, tally, reason)



def collect_supplemental(
    uow: CollectionUnitOfWork,
    job: SupplementalJob,
    *,
    grants: ActivityGrantPort,
    content_port: ContentHandoffPort,
    clock: Callable[[], datetime.datetime] = _utc_now,
) -> SupplementalResult:
    """Run one supplemental search for a video job: grant, tombstone and budget gates, packages, handoff B."""
    request = job.request
    grant = request.grant
    if grant.workspace_id != request.workspace_id or grant.job_id != request.job_id:
        return _blocked(request, ERROR_GRANT_SCOPE_MISMATCH)
    if not grants.is_grant_current(grant):
        return _blocked(request, ERROR_GRANT_NOT_CURRENT)
    code = _source_block(uow.sources.get(request.workspace_id, request.source_id))
    if code is not None:
        return _blocked(request, code)
    tally = _Tally()
    existing = uow.runs.get(request.run_id)
    resumed = False
    if existing is None:
        run = _open_run(uow, request, clock)
    elif existing.purpose is not CollectionPurpose.SUPPLEMENTAL or (existing.workspace_id, existing.source_id) != (
        request.workspace_id, request.source_id
    ):
        return _blocked(request, ERROR_RUN_CONFLICT)
    elif existing.status is RunStatus.WAITING_RETRY:
        run, resumed = _resume(uow, request, existing, clock), True
    else:
        run = existing
    if run.status is not RunStatus.RUNNING:
        replayed = existing is not None and not resumed
        return _build_result(uow, request, run, tally, _stored_reason(run), replayed=replayed)
    if _expired(request, clock):
        return _conclude(uow, request, run, tally, REASON_DEADLINE_EXCEEDED, AttemptOutcome.FAILED_RETRYABLE, deadline_passed=True)
    try:
        listing = job.adapter.supplemental_search(dict(request.intent))
    except Exception as exc:
        tally.errors.append(_item_error('', ERROR_ADAPTER_EXCEPTION, _exception_text(exc)))
        return _conclude(uow, request, run, tally, ERROR_ADAPTER_EXCEPTION, AttemptOutcome.FAILED_FINAL)
    failure = _failure(listing)
    if failure is not None or not isinstance(listing, CandidateListing):
        code = failure[0] if failure is not None else ERROR_ADAPTER_CONTRACT
        tally.errors.append(_item_error('', code))
        outcome = AttemptOutcome.FAILED_RETRYABLE if failure is not None and failure[1] else AttemptOutcome.FAILED_FINAL
        return _conclude(uow, request, run, tally, code, outcome, deadline_passed=_expired(request, clock))
    if not listing.locators:
        return _conclude(uow, request, run, tally, REASON_NO_CANDIDATES, AttemptOutcome.SUCCEEDED)
    reason = None
    stop_code = None
    for locator in listing.locators:
        if _expired(request, clock):
            reason = REASON_DEADLINE_EXCEEDED
            break
        if tally.fetch_attempts >= request.budget.max_fetches:
            reason = REASON_BUDGET_EXHAUSTED
            break
        current = uow.sources.get(request.workspace_id, request.source_id)
        stop_code = _source_block(current)
        if stop_code is not None:
            tally.blocked += 1
            tally.errors.append(_item_error('', stop_code))
            break
        run = _collect_item(uow, job, current, run, locator, tally, content_port, clock)
    if stop_code is not None:
        return _conclude(uow, request, run, tally, stop_code, AttemptOutcome.FAILED_FINAL, source_inactive=True)
    if reason is not None:
        return _conclude(uow, request, run, tally, reason, AttemptOutcome.FAILED_RETRYABLE, deadline_passed=True)
    if tally.failed > 0:
        first_failure = next(e.code for e in tally.errors if e.code != ERROR_SOURCE_TOMBSTONED)
        return _conclude(uow, request, run, tally, first_failure, AttemptOutcome.FAILED_FINAL)
    reason = REASON_NO_NEW_PACKAGES if run.committed_package_count == 0 else None
    return _conclude(uow, request, run, tally, reason, AttemptOutcome.SUCCEEDED)



__all__ = [
    'SupplementalBudget',
    'SupplementalDiscovery',
    'SupplementalJob',
    'SupplementalOutcome',
    'SupplementalRequest',
    'SupplementalResult',
    'collect_supplemental',
]
