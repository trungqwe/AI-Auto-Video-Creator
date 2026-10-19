"""CollectSource use case (A-11, CT-SRC-005; A-RULE-004, A-RULE-008, A-RULE-012).

Creates or restores the periodic CollectionRun, commits every valid item in its own unit of work and
isolates failures between items and between sources. Adapters are injected; this module opens no socket.
"""
from __future__ import annotations

import dataclasses
import datetime
import re
from collections.abc import Callable, Iterable
from typing import Any, Protocol
from urllib.parse import urlsplit

from controlplane.domain.common.contracts import ProblemDetail
from controlplane.domain.interfaces.outbox import IOutboxWriter

from source_ingestion.application.package_builder import HtmlExtractor, PackageContext, build_package
from source_ingestion.domain.checkpoint import (
    AdapterCheckpointSemantics,
    CheckpointCompleteness,
    CheckpointRejected,
    CollectionCheckpoint,
    ensure_checkpoint_loadable,
    seal_checkpoint,
)
from source_ingestion.domain.collection_run import (
    TERMINAL_STATUSES,
    AttemptOutcome,
    CollectionPurpose,
    CollectionRun,
    RetryPolicy,
    RunStatus,
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
from source_ingestion.ports.repositories import (
    CheckpointRepository,
    CollectionRunRepository,
    PackageRecord,
    PackageRepository,
    SourceRepository,
)
from source_ingestion.ports.source_adapter import (
    CandidateListing,
    CapabilityUnavailable,
    FetchedDocument,
    SourceAdapter,
)

START_CURSOR = 'cursor:start'
NO_CHECKPOINT_REF = 'checkpoint:none'
EVENT_RUN_STARTED = 'CollectionRunStarted'
EVENT_DOCUMENT_AVAILABLE = 'CollectedDocumentAvailable'
EVENT_RUN_COMPLETED = 'CollectionRunCompleted'
EVENT_RUN_FAILED = 'CollectionRunFailed'
ERROR_SOURCE_NOT_FOUND = 'SOURCE_NOT_FOUND'
ERROR_ADAPTER_EXCEPTION = 'ADAPTER_EXCEPTION'
ERROR_ADAPTER_CONTRACT = 'ADAPTER_CONTRACT_VIOLATION'
ERROR_VALIDATION = 'VALIDATION_ERROR'
ERROR_ITEM_FAILED = 'ITEM_PROCESSING_FAILED'
ERROR_ITEM_COMMIT = 'ITEM_COMMIT_FAILED'
ERROR_COLLECTION_ABORTED = 'COLLECTION_ABORTED'
ERROR_FINGERPRINT_MISSING = 'FINGERPRINT_MISSING'
ERROR_INVALID_LOCATOR = 'INVALID_LOCATOR'
ERROR_CHECKPOINT_REJECTED = 'CHECKPOINT_REJECTED'
MAX_ERROR_TEXT = 200


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string')
    return value


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@dataclasses.dataclass(frozen=True)
class CollectSourceRequest:
    workspace_id: str
    source_id: str
    business_date: datetime.date
    run_id: str
    retry_policy: RetryPolicy
    adapter_revision: str
    checkpoint_version: int = 1
    execution_generation: int = 0
    extraction_policy: ExtractionPolicy | None = None

    def __post_init__(self) -> None:
        for name in ('workspace_id', 'source_id', 'run_id', 'adapter_revision'):
            _require_text(getattr(self, name), name)
        if isinstance(self.business_date, datetime.datetime) or not isinstance(self.business_date, datetime.date):
            raise ValueError('business_date must be a datetime.date')
        if not isinstance(self.retry_policy, RetryPolicy):
            raise ValueError('retry_policy must be a RetryPolicy')
        if type(self.checkpoint_version) is not int or self.checkpoint_version < 1:
            raise ValueError('checkpoint_version must be an int >= 1')
        if type(self.execution_generation) is not int or self.execution_generation < 0:
            raise ValueError('execution_generation must be an int >= 0')
        if self.extraction_policy is not None and not isinstance(self.extraction_policy, ExtractionPolicy):
            raise ValueError('extraction_policy must be an ExtractionPolicy')


@dataclasses.dataclass(frozen=True)
class SourceCollectionJob:
    request: CollectSourceRequest
    adapter: SourceAdapter
    extractor: HtmlExtractor


@dataclasses.dataclass(frozen=True)
class ItemError:
    """Redacted error: locator has no credentials, query or fragment; message passed redaction."""

    locator: str
    code: str
    message: str


@dataclasses.dataclass(frozen=True)
class CollectionRunResult:
    run_id: str
    workspace_id: str
    source_id: str
    status: RunStatus
    urls_seen: int
    fetched: int
    skipped: int
    failed: int
    packages_committed: int
    package_refs: tuple[str, ...]
    cursor: str | None
    errors: tuple[ItemError, ...]
    replayed: bool = False


class CollectionUnitOfWork(Protocol):
    sources: SourceRepository
    runs: CollectionRunRepository
    packages: PackageRepository
    checkpoints: CheckpointRepository
    outbox: IOutboxWriter

    def __enter__(self) -> Any: ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

    def commit(self) -> None: ...


_URL_RE = re.compile(r'https?://[^\s<>]+')
_PRIVATE_KEY_RE = re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', re.DOTALL)
_BEARER_RE = re.compile(r'(?i)\bBearer\s+[^\s,;]+')
_ASSIGNMENT_RE = re.compile(
    r'(?i)\b(password|passwd|secret|token|access[_-]?token|refresh[_-]?token|api[_-]?key|credential|authorization)'
    r'(\s*[:=]\s*)([^\s,;&]+)'
)


@dataclasses.dataclass
class _Tally:
    urls_seen: int = 0
    fetched: int = 0
    skipped: int = 0
    failed: int = 0
    committed: int = 0
    errors: list[ItemError] = dataclasses.field(default_factory=list)


def _safe_locator(locator: object) -> str:
    """Scheme, host, port and path only: no credentials, query or fragment."""
    try:
        parts = urlsplit(str(locator).strip())
        host = parts.hostname
        port = parts.port
    except ValueError:
        return '[invalid-locator]'
    if not parts.scheme or not host:
        return '[invalid-locator]'
    netloc = f'[{host}]' if ':' in host else host
    if port is not None:
        netloc = f'{netloc}:{port}'
    return f'{parts.scheme.lower()}://{netloc}{parts.path}'


def _redact(text: object) -> str:
    value = _URL_RE.sub(lambda match: _safe_locator(match.group(0)), str(text))
    value = _PRIVATE_KEY_RE.sub('[REDACTED PRIVATE KEY]', value)
    value = _BEARER_RE.sub('Bearer [REDACTED]', value)
    value = _ASSIGNMENT_RE.sub(lambda match: match.group(1) + match.group(2) + '[REDACTED]', value)
    return value[:MAX_ERROR_TEXT]


def _item_error(locator: object, code: str, detail: object = '') -> ItemError:
    safe = _safe_locator(locator) if locator else ''
    return ItemError(safe, code, _redact(detail))


def _exception_text(exc: BaseException) -> str:
    return f'{type(exc).__name__}: {exc}'


def _iso(value: datetime.datetime) -> str:
    return value.astimezone(datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + 'Z'


def _checkpoint_ref(uow: CollectionUnitOfWork, source_id: str) -> str:
    latest = uow.checkpoints.get_latest(source_id)
    return latest.fingerprint if latest is not None else NO_CHECKPOINT_REF


def _public_cursor(checkpoint: CollectionCheckpoint | None) -> str | None:
    """Cursor the adapter understands: the START_CURSOR placeholder means no cursor yet."""
    if checkpoint is None or checkpoint.cursor == START_CURSOR:
        return None
    return checkpoint.cursor


def _next_checkpoint(
    source: Source,
    request: CollectSourceRequest,
    run: CollectionRun,
    previous: CollectionCheckpoint | None,
    *,
    cursor: str,
    item_ids: tuple[str, ...],
    completeness: CheckpointCompleteness,
    recorded_at: datetime.datetime,
) -> CollectionCheckpoint:
    return seal_checkpoint(CollectionCheckpoint(
        checkpoint_version=request.checkpoint_version,
        revision=1 if previous is None else previous.revision + 1,
        source_id=source.source_id,
        source_revision=source.revision,
        adapter_type=source.source_kind,
        adapter_revision=request.adapter_revision,
        cursor=cursor,
        item_ids=item_ids,
        run_id=run.run_id,
        attempt_id=f'{run.run_id}:attempt-{len(run.attempts) + 1}',
        execution_generation=request.execution_generation,
        completeness=completeness,
        recorded_at=_iso(recorded_at),
        fingerprint='sha256:unsealed',
    ))


def _event_payload(run: CollectionRun) -> dict[str, object]:
    decision = run.terminal_decision
    return {
        'run_id': run.run_id,
        'workspace_id': run.workspace_id,
        'source_id': run.source_id,
        'business_date': run.business_date.isoformat(),
        'status': run.status.value,
        'committed_package_count': run.committed_package_count,
        'warning_count': len(run.warnings),
        'terminal_reason': decision.reason.value if decision is not None else None,
    }


def _emit_terminal_event(uow: CollectionUnitOfWork, run: CollectionRun) -> None:
    if run.status is RunStatus.FAILED_FINAL:
        name = EVENT_RUN_FAILED
    elif run.status in (RunStatus.COMPLETED, RunStatus.COMPLETED_PARTIAL):
        name = EVENT_RUN_COMPLETED
    else:
        return
    uow.outbox.append_event(name, run.run_id, _event_payload(run), f'{name}:{run.run_id}')


def _acquire_run(
    uow: CollectionUnitOfWork, request: CollectSourceRequest, source: Source
) -> tuple[CollectionRun, bool]:
    """Create or restore the periodic run in one UoW (A-RULE-004); returns (run, created)."""
    with uow:
        run = uow.runs.get_periodic(request.workspace_id, request.source_id, request.business_date)
        created = run is None
        if run is None:
            run = schedule_run(
                run_id=request.run_id,
                workspace_id=request.workspace_id,
                source_id=request.source_id,
                business_date=request.business_date,
                purpose=CollectionPurpose.PERIODIC,
                retry_policy=request.retry_policy,
            )
            uow.runs.add(run)
            uow.outbox.append_event(
                EVENT_RUN_STARTED, run.run_id, _event_payload(run), f'{EVENT_RUN_STARTED}:{run.run_id}'
            )
        before = run
        ref = _checkpoint_ref(uow, request.source_id)
        if run.status not in TERMINAL_STATUSES and run.status is not RunStatus.WAITING_RECONCILIATION:
            if source.status is not SourceStatus.ACTIVE:
                run = deactivate_source(run, checkpoint_ref=ref)
            elif run.status is RunStatus.SCHEDULED:
                run = start_run(run, source_active=True, checkpoint_ref=ref)
            elif run.status is RunStatus.WAITING_RETRY:
                run = resume_retry(run, source_active=True, deadline_passed=False, checkpoint_ref=ref)
        if run is not before:
            uow.runs.save(run)
            if run.status in TERMINAL_STATUSES:
                _emit_terminal_event(uow, run)
        uow.commit()
    return run, created


def _failure(value: object) -> tuple[str, bool] | None:
    """(code, retryable) for a ProblemDetail or CapabilityUnavailable; None for a success value."""
    if isinstance(value, ProblemDetail):
        return str(value.values.get('code', 'PROBLEM')), value.values.get('retryable') is True
    if isinstance(value, CapabilityUnavailable):
        return value.code, False
    return None


def _observation_fingerprint(package: dict[str, object]) -> str | None:
    fingerprints = package.get('content_fingerprints')
    if isinstance(fingerprints, dict):
        value = fingerprints.get('raw_body_sha256')
        if isinstance(value, str) and value:
            return value
    return None


def _prepare(
    job: SourceCollectionJob,
    source: Source,
    run: CollectionRun,
    document: FetchedDocument,
    fetched_at: datetime.datetime,
):
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


def _available_payload(package: dict[str, object], canonical: str, fingerprint: str) -> dict[str, object]:
    return {
        'collected_document_id': package['collected_document_id'],
        'source_id': package['source_id'],
        'source_revision': package['source_revision'],
        'collection_run_id': package['collection_run_id'],
        'canonical_locator': _safe_locator(canonical),
        'observation_fingerprint': fingerprint,
        'extraction_disposition': package['extraction_disposition'],
        'content_eligibility': package.get('content_eligibility'),
        'fetched_at': package['fetched_at'],
    }


def _collect_item(
    uow: CollectionUnitOfWork,
    job: SourceCollectionJob,
    source: Source,
    run: CollectionRun,
    locator: str,
    cursor_in: str,
    tally: _Tally,
    clock: Callable[[], datetime.datetime],
) -> CollectionRun:
    """Fetch, build, gate and commit one item in its own UoW (A-RULE-008); returns the (advanced) run."""
    tally.urls_seen += 1
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
    fetched_at = clock()
    prepared = _prepare(job, source, run, fetched, fetched_at)
    if isinstance(prepared, str):
        tally.failed += 1
        tally.errors.append(_item_error(locator, prepared))
        return run
    package, canonical, fingerprint = prepared
    if uow.packages.get(source.source_id, canonical, fingerprint) is not None:
        tally.skipped += 1
        return run
    item_id = f'{canonical}|{fingerprint}'
    try:
        with uow:
            uow.packages.add(PackageRecord(source.source_id, canonical, fingerprint, run.run_id, package))
            advanced = record_committed_packages(run, 1)
            uow.runs.save(advanced)
            previous = uow.checkpoints.get_latest(source.source_id)
            proposed = _next_checkpoint(
                source, job.request, run, previous,
                cursor=cursor_in, item_ids=(item_id,),
                completeness=CheckpointCompleteness.PARTIAL, recorded_at=fetched_at,
            )
            uow.checkpoints.advance(proposed, (item_id,))
            uow.outbox.append_event(
                EVENT_DOCUMENT_AVAILABLE,
                str(package['collected_document_id']),
                _available_payload(package, canonical, fingerprint),
                f'{EVENT_DOCUMENT_AVAILABLE}:{source.source_id}:{canonical}:{fingerprint}',
            )
            uow.commit()
    except Exception as exc:
        tally.failed += 1
        tally.errors.append(_item_error(locator, ERROR_ITEM_COMMIT, _exception_text(exc)))
        return run
    tally.committed += 1
    return advanced


def _terminal_errors(run: CollectionRun) -> tuple[ItemError, ...]:
    if run.status is RunStatus.FAILED_FINAL and run.terminal_decision is not None:
        return (ItemError('', run.terminal_decision.reason.value, ''),)
    return ()


def _result(
    uow: CollectionUnitOfWork,
    run: CollectionRun,
    tally: _Tally | None = None,
    *,
    replayed: bool = False,
    errors: tuple[ItemError, ...] | None = None,
) -> CollectionRunResult:
    tally = tally if tally is not None else _Tally()
    return CollectionRunResult(
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        source_id=run.source_id,
        status=run.status,
        urls_seen=tally.urls_seen,
        fetched=tally.fetched,
        skipped=tally.skipped,
        failed=tally.failed,
        packages_committed=tally.committed,
        package_refs=tuple(str(r.payload['collected_document_id']) for r in uow.packages.list_by_run(run.run_id)),
        cursor=_public_cursor(uow.checkpoints.get_latest(run.source_id)),
        errors=tuple(tally.errors if errors is None else errors),
        replayed=replayed,
    )


def _failure_result(
    request: CollectSourceRequest,
    code: str,
    detail: object = '',
    *,
    run_id: str | None = None,
    status: RunStatus = RunStatus.FAILED_FINAL,
) -> CollectionRunResult:
    return CollectionRunResult(
        run_id=run_id or request.run_id,
        workspace_id=request.workspace_id,
        source_id=request.source_id,
        status=status,
        urls_seen=0, fetched=0, skipped=0, failed=0, packages_committed=0,
        package_refs=(),
        cursor=None,
        errors=(_item_error('', code, detail),),
    )


def _finish(
    uow: CollectionUnitOfWork,
    job: SourceCollectionJob,
    source: Source,
    run: CollectionRun,
    tally: _Tally,
    outcome: AttemptOutcome,
    *,
    listing: CandidateListing | None,
    clock: Callable[[], datetime.datetime],
) -> CollectionRunResult:
    """Run completion UoW: final checkpoint, attempt outcome, warnings, terminal event; items stay committed."""
    warnings = tuple(f'{error.code}:{error.locator}' if error.locator else error.code for error in tally.errors)
    with uow:
        if listing is not None and listing.cursor is not None and tally.failed == 0:
            completeness = CheckpointCompleteness.COMPLETE if listing.complete else CheckpointCompleteness.PARTIAL
            proposed = _next_checkpoint(
                source, job.request, run, uow.checkpoints.get_latest(source.source_id),
                cursor=listing.cursor, item_ids=(), completeness=completeness, recorded_at=clock(),
            )
            uow.checkpoints.advance(proposed, ())
        run = record_attempt_outcome(
            run, outcome, source_active=True, deadline_passed=False,
            checkpoint_ref=_checkpoint_ref(uow, source.source_id),
        )
        run = dataclasses.replace(run, warnings=tuple(dict.fromkeys(run.warnings + warnings)))
        uow.runs.save(run)
        _emit_terminal_event(uow, run)
        uow.commit()
    return _result(uow, run, tally)


def collect_source(
    uow: CollectionUnitOfWork,
    job: SourceCollectionJob,
    *,
    clock: Callable[[], datetime.datetime] = _utc_now,
) -> CollectionRunResult:
    """Create or restore the periodic run of one source and collect it item by item (CT-SRC-005)."""
    request = job.request
    source = uow.sources.get(request.workspace_id, request.source_id)
    if source is None:
        return _failure_result(request, ERROR_SOURCE_NOT_FOUND)
    run, created = _acquire_run(uow, request, source)
    if run.status is not RunStatus.RUNNING:
        return _result(uow, run, replayed=not created, errors=_terminal_errors(run))
    tally = _Tally()
    checkpoint = uow.checkpoints.get_latest(source.source_id)
    try:
        if checkpoint is not None:
            ensure_checkpoint_loadable(
                checkpoint,
                source_id=source.source_id,
                semantics=AdapterCheckpointSemantics(
                    adapter_type=source.source_kind,
                    adapter_revision=request.adapter_revision,
                    checkpoint_version=request.checkpoint_version,
                ),
            )
    except CheckpointRejected as rejected:
        tally.errors.append(_item_error('', ERROR_CHECKPOINT_REJECTED, rejected.code))
        return _finish(uow, job, source, run, tally, AttemptOutcome.FAILED_FINAL, listing=None, clock=clock)
    try:
        listing = job.adapter.list_candidates(source.canonical_locator, _public_cursor(checkpoint))
    except Exception as exc:
        tally.errors.append(_item_error(source.canonical_locator, ERROR_ADAPTER_EXCEPTION, _exception_text(exc)))
        return _finish(uow, job, source, run, tally, AttemptOutcome.FAILED_FINAL, listing=None, clock=clock)
    failure = _failure(listing)
    if failure is not None or not isinstance(listing, CandidateListing):
        code = failure[0] if failure is not None else ERROR_ADAPTER_CONTRACT
        tally.errors.append(_item_error(source.canonical_locator, code))
        retryable = failure is not None and failure[1]
        outcome = AttemptOutcome.FAILED_RETRYABLE if retryable else AttemptOutcome.FAILED_FINAL
        return _finish(uow, job, source, run, tally, outcome, listing=None, clock=clock)
    cursor_in = checkpoint.cursor if checkpoint is not None else START_CURSOR
    for locator in listing.locators:
        run = _collect_item(uow, job, source, run, locator, cursor_in, tally, clock)
    outcome = AttemptOutcome.SUCCEEDED if tally.failed == 0 else AttemptOutcome.FAILED_FINAL
    return _finish(uow, job, source, run, tally, outcome, listing=listing, clock=clock)


def collect_sources(
    uow: CollectionUnitOfWork,
    jobs: Iterable[SourceCollectionJob],
    *,
    clock: Callable[[], datetime.datetime] = _utc_now,
) -> tuple[CollectionRunResult, ...]:
    """Collect sources one after another; a source that raises never stops the others (A-RULE-012)."""
    results: list[CollectionRunResult] = []
    for job in jobs:
        try:
            results.append(collect_source(uow, job, clock=clock))
        except Exception as exc:
            results.append(_aborted_result(uow, job.request, exc))
    return tuple(results)


def _aborted_result(uow: CollectionUnitOfWork, request: CollectSourceRequest, exc: Exception) -> CollectionRunResult:
    """Redacted result for an exception that escaped collect_source; committed items stay committed."""
    try:
        stored = uow.runs.get_periodic(request.workspace_id, request.source_id, request.business_date)
    except Exception:
        stored = None
    if stored is None:
        return _failure_result(request, ERROR_COLLECTION_ABORTED, _exception_text(exc))
    return _failure_result(
        request, ERROR_COLLECTION_ABORTED, _exception_text(exc), run_id=stored.run_id, status=stored.status
    )


__all__ = [
    'CollectSourceRequest',
    'CollectionRunResult',
    'CollectionUnitOfWork',
    'ItemError',
    'SourceCollectionJob',
    'collect_source',
    'collect_sources',
]
