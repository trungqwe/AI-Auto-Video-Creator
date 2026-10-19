"""Read-only Source/Run query projections (A-17; A-RULE-014).

Queries read through injected repository ports and never touch an adapter, transport or socket,
so a query cannot trigger a fetch. Every query is scoped to one workspace: a record of another
workspace is reported as not found. Package traces are rebuilt from an allowlist and carry no
cookie, credential, token header or URL userinfo/query. Source health is derived from the latest
terminal CollectionRun (D8 default; no separate health store exists).
"""
from __future__ import annotations

import dataclasses
import datetime
import enum
import re
from collections.abc import Mapping
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

from source_ingestion.domain.collection_run import (
    TERMINAL_STATUSES,
    AttemptOutcome,
    CollectionPurpose,
    CollectionRun,
    RunStatus,
)
from source_ingestion.domain.source import Source, SourceStatus
from source_ingestion.ports.repositories import (
    CollectionRunRepository,
    PackageRepository,
    SourceRepository,
)

SENSITIVE_HEADER_MARKERS = (
    'auth', 'cookie', 'token', 'secret', 'api-key', 'apikey', 'password', 'session', 'signature',
    'credential', 'csrf',
)
REDACTED = '[redacted]'
_CODE_RE = re.compile(r'[A-Za-z0-9_.:/+\-]{1,200}')
_URL_RE = re.compile(r'''[A-Za-z][A-Za-z0-9+.\-]*://[^\s<>"',;]+''')


class SourceHealth(str, enum.Enum):
    HEALTHY = 'HEALTHY'
    DEGRADED = 'DEGRADED'
    FAILING = 'FAILING'
    UNKNOWN = 'UNKNOWN'


@dataclasses.dataclass(frozen=True)
class SourceListFilter:
    """AND of the fields that are set; None means no constraint."""

    tier: str | None = None
    topic: str | None = None
    status: SourceStatus | None = None
    source_kind: str | None = None
    health: SourceHealth | None = None

    def __post_init__(self) -> None:
        for name in ('tier', 'topic', 'source_kind'):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f'{name} must be a non-empty string or None')
        if self.status is not None and not isinstance(self.status, SourceStatus):
            raise TypeError('status must be a SourceStatus or None')
        if self.health is not None and not isinstance(self.health, SourceHealth):
            raise TypeError('health must be a SourceHealth or None')


@dataclasses.dataclass(frozen=True)
class RunCounters:
    run_count: int
    attempt_count: int
    committed_package_count: int
    completed_count: int
    completed_partial_count: int
    failed_final_count: int
    in_progress_count: int


@dataclasses.dataclass(frozen=True)
class LastCollection:
    run_id: str
    business_date: datetime.date
    purpose: CollectionPurpose
    status: RunStatus


@dataclasses.dataclass(frozen=True)
class SourceSummary:
    source_id: str
    name: str
    canonical_locator: str
    source_kind: str
    tier: str
    topics: tuple[str, ...]
    status: SourceStatus
    status_reason: str | None
    health: SourceHealth
    last_collection: LastCollection | None
    revision: int
    updated_at: datetime.datetime


@dataclasses.dataclass(frozen=True)
class SourceDetail:
    summary: SourceSummary
    notes: str
    admin_metadata: tuple[tuple[str, str], ...]
    policy_revision: str
    created_by: str
    created_at: datetime.datetime
    updated_by: str
    counters: RunCounters


@dataclasses.dataclass(frozen=True)
class RevisionView:
    revision: int
    tier: str
    topics: tuple[str, ...]
    status: SourceStatus
    status_reason: str | None
    notes: str
    policy_revision: str
    updated_by: str
    updated_at: datetime.datetime


@dataclasses.dataclass(frozen=True)
class AttemptView:
    attempt_no: int
    outcome: AttemptOutcome


@dataclasses.dataclass(frozen=True)
class RunView:
    run_id: str
    business_date: datetime.date
    purpose: CollectionPurpose
    status: RunStatus
    attempts: tuple[AttemptView, ...]
    committed_package_count: int
    terminal_reason: str | None
    checkpoint_ref: str | None
    reconciliation_count: int
    warnings: tuple[str, ...]
    retry_policy_revision: str
    max_attempts: int


@dataclasses.dataclass(frozen=True)
class TraceStep:
    step: str | None
    url: str | None
    hop: int | None
    extractor_version: str | None
    fetch_policy_revision: str | None


@dataclasses.dataclass(frozen=True)
class TracePackage:
    collected_document_id: str | None
    source_revision: int | None
    requested_url: str | None
    final_url: str | None
    fetched_at: str | None
    http_status: int | None
    media_type: str | None
    size_bytes: int | None
    redirect_chain: tuple[str, ...]
    safe_headers: tuple[tuple[str, str], ...]
    fetch_policy_revision: str | None
    extraction_disposition: str | None
    extractor_version: str | None
    content_eligibility: str | None
    eligibility_reason: str | None
    provenance: tuple[TraceStep, ...]
    warnings: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class RunTrace:
    run_id: str
    source_id: str
    packages: tuple[TracePackage, ...]


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string')
    return value


def _code(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value if _CODE_RE.fullmatch(value) else REDACTED


def _int(value: object) -> int | None:
    return value if type(value) is int else None


def _items(value: object) -> tuple[object, ...]:
    return tuple(value) if isinstance(value, (list, tuple)) else ()


def redact_locator(value: object) -> str:
    """Scheme, host, port and path only; userinfo, query and fragment are dropped."""
    if not isinstance(value, str):
        return REDACTED
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return REDACTED
    if not parts.scheme or not parts.netloc:
        return REDACTED
    return f'{parts.scheme}://{parts.netloc.rpartition("@")[2]}{parts.path}'


def _scrub(value: str) -> str:
    return _URL_RE.sub(lambda match: redact_locator(match.group(0)), value)


def redact_headers(headers: object) -> tuple[tuple[str, str], ...]:
    """Lower-cased headers without credential/cookie/token names; URLs in values lose their query."""
    kept: list[tuple[str, str]] = []
    for item in _items(headers):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        name, value = item
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        lowered = name.strip().lower()
        if lowered and not any(marker in lowered for marker in SENSITIVE_HEADER_MARKERS):
            kept.append((lowered, _scrub(value)))
    return tuple(kept)


_HEALTH_BY_STATUS = {
    RunStatus.COMPLETED: SourceHealth.HEALTHY,
    RunStatus.COMPLETED_PARTIAL: SourceHealth.DEGRADED,
    RunStatus.FAILED_FINAL: SourceHealth.FAILING,
}


def _last_terminal(runs: tuple[CollectionRun, ...]) -> CollectionRun | None:
    """Runs arrive sorted by (business_date, run_id); the last terminal one is the last collection."""
    terminal = [run for run in runs if run.status in TERMINAL_STATUSES]
    return terminal[-1] if terminal else None


def _counters(runs: tuple[CollectionRun, ...]) -> RunCounters:
    return RunCounters(
        run_count=len(runs),
        attempt_count=sum(len(run.attempts) for run in runs),
        committed_package_count=sum(run.committed_package_count for run in runs),
        completed_count=sum(run.status is RunStatus.COMPLETED for run in runs),
        completed_partial_count=sum(run.status is RunStatus.COMPLETED_PARTIAL for run in runs),
        failed_final_count=sum(run.status is RunStatus.FAILED_FINAL for run in runs),
        in_progress_count=sum(run.status not in TERMINAL_STATUSES for run in runs),
    )


def _summary(source: Source, runs: tuple[CollectionRun, ...]) -> SourceSummary:
    last = _last_terminal(runs)
    return SourceSummary(
        source_id=source.source_id,
        name=source.name,
        canonical_locator=source.canonical_locator,
        source_kind=source.source_kind,
        tier=source.tier,
        topics=tuple(sorted(source.topics)),
        status=source.status,
        status_reason=source.status_reason,
        health=SourceHealth.UNKNOWN if last is None else _HEALTH_BY_STATUS[last.status],
        last_collection=None if last is None else LastCollection(
            last.run_id, last.business_date, last.purpose, last.status
        ),
        revision=source.revision,
        updated_at=source.updated_at,
    )


def _matches(criteria: SourceListFilter, summary: SourceSummary) -> bool:
    return (
        (criteria.tier is None or summary.tier == criteria.tier)
        and (criteria.topic is None or criteria.topic in summary.topics)
        and (criteria.status is None or summary.status is criteria.status)
        and (criteria.source_kind is None or summary.source_kind == criteria.source_kind)
        and (criteria.health is None or summary.health is criteria.health)
    )


def _run_view(run: CollectionRun) -> RunView:
    decision = run.terminal_decision
    return RunView(
        run_id=run.run_id,
        business_date=run.business_date,
        purpose=run.purpose,
        status=run.status,
        attempts=tuple(AttemptView(attempt.attempt_no, attempt.outcome) for attempt in run.attempts),
        committed_package_count=run.committed_package_count,
        terminal_reason=None if decision is None else decision.reason.value,
        checkpoint_ref=run.checkpoint_ref,
        reconciliation_count=len(run.reconciliations),
        warnings=tuple(_scrub(warning) for warning in run.warnings),
        retry_policy_revision=run.retry_policy.revision,
        max_attempts=run.retry_policy.max_attempts,
    )


def _url(value: object) -> str | None:
    return redact_locator(value) if isinstance(value, str) else None


def _trace_step(item: object) -> TraceStep | None:
    if not isinstance(item, Mapping):
        return None
    return TraceStep(
        step=_code(item.get('step')),
        url=_url(item.get('url')),
        hop=_int(item.get('hop')),
        extractor_version=_code(item.get('extractor_version')),
        fetch_policy_revision=_code(item.get('fetch_policy_revision')),
    )


def _trace_package(payload: Mapping[str, object]) -> TracePackage:
    """Allowlist rebuild: unknown keys, bodies and request headers never reach the trace."""
    observed = payload.get('http_observation')
    http = observed if isinstance(observed, Mapping) else {}
    steps = (_trace_step(item) for item in _items(payload.get('provenance_chain')))
    return TracePackage(
        collected_document_id=_code(payload.get('collected_document_id')),
        source_revision=_int(payload.get('source_revision')),
        requested_url=_url(payload.get('requested_url')),
        final_url=_url(payload.get('final_url')),
        fetched_at=_code(payload.get('fetched_at')),
        http_status=_int(http.get('status')),
        media_type=_code(http.get('media_type')),
        size_bytes=_int(http.get('size_bytes')),
        redirect_chain=tuple(redact_locator(url) for url in _items(http.get('redirect_chain'))),
        safe_headers=redact_headers(http.get('safe_headers')),
        fetch_policy_revision=_code(http.get('fetch_policy_revision')),
        extraction_disposition=_code(payload.get('extraction_disposition')),
        extractor_version=_code(payload.get('extractor_version')),
        content_eligibility=_code(payload.get('content_eligibility')),
        eligibility_reason=_code(payload.get('eligibility_reason')),
        provenance=tuple(step for step in steps if step is not None),
        warnings=tuple(_code(warning) or REDACTED for warning in _items(payload.get('warnings'))),
    )


@runtime_checkable
class SourceRevisionReader(Protocol):
    """Read-only history of Source aggregate snapshots; persistence waits for CONV-A-01."""

    def list_revisions(self, workspace_id: str, source_id: str) -> tuple[Source, ...]:
        ...


class SourceQueryService:
    """Read-only queries; repositories are used through get/list methods only."""

    def __init__(
        self,
        sources: SourceRepository,
        runs: CollectionRunRepository,
        packages: PackageRepository,
        revisions: SourceRevisionReader,
    ) -> None:
        self._sources = sources
        self._runs = runs
        self._packages = packages
        self._revisions = revisions

    def _source(self, workspace_id: str, source_id: str) -> Source | None:
        _text(workspace_id, 'workspace_id')
        _text(source_id, 'source_id')
        source = self._sources.get(workspace_id, source_id)
        if source is None or source.workspace_id != workspace_id or source.source_id != source_id:
            return None
        return source

    def _runs_of(self, workspace_id: str, source_id: str) -> tuple[CollectionRun, ...]:
        owned = (
            run for run in self._runs.list_by_source(workspace_id, source_id)
            if run.workspace_id == workspace_id and run.source_id == source_id
        )
        return tuple(sorted(owned, key=lambda run: (run.business_date, run.run_id)))

    def list_sources(
        self, workspace_id: str, source_filter: SourceListFilter | None = None
    ) -> tuple[SourceSummary, ...]:
        _text(workspace_id, 'workspace_id')
        criteria = SourceListFilter() if source_filter is None else source_filter
        if not isinstance(criteria, SourceListFilter):
            raise TypeError('source_filter must be a SourceListFilter or None')
        summaries = []
        for source in self._sources.list_sources(workspace_id):
            if source.workspace_id != workspace_id:
                continue
            summary = _summary(source, self._runs_of(workspace_id, source.source_id))
            if _matches(criteria, summary):
                summaries.append(summary)
        return tuple(sorted(summaries, key=lambda item: item.source_id))

    def get_source(self, workspace_id: str, source_id: str) -> SourceDetail | None:
        source = self._source(workspace_id, source_id)
        if source is None:
            return None
        runs = self._runs_of(workspace_id, source_id)
        return SourceDetail(
            summary=_summary(source, runs),
            notes=source.notes,
            admin_metadata=source.admin_metadata,
            policy_revision=source.policy_revision,
            created_by=source.created_by,
            created_at=source.created_at,
            updated_by=source.updated_by,
            counters=_counters(runs),
        )

    def list_source_revisions(self, workspace_id: str, source_id: str) -> tuple[RevisionView, ...] | None:
        if self._source(workspace_id, source_id) is None:
            return None
        snapshots = [
            item for item in self._revisions.list_revisions(workspace_id, source_id)
            if item.workspace_id == workspace_id and item.source_id == source_id
        ]
        return tuple(
            RevisionView(
                revision=item.revision, tier=item.tier, topics=tuple(sorted(item.topics)),
                status=item.status, status_reason=item.status_reason, notes=item.notes,
                policy_revision=item.policy_revision, updated_by=item.updated_by, updated_at=item.updated_at,
            )
            for item in sorted(snapshots, key=lambda item: item.revision)
        )

    def list_runs(self, workspace_id: str, source_id: str) -> tuple[RunView, ...] | None:
        if self._source(workspace_id, source_id) is None:
            return None
        return tuple(_run_view(run) for run in self._runs_of(workspace_id, source_id))

    def get_package_trace(self, workspace_id: str, source_id: str, run_id: str) -> RunTrace | None:
        _text(run_id, 'run_id')
        if self._source(workspace_id, source_id) is None:
            return None
        run = self._runs.get(run_id)
        if run is None or run.workspace_id != workspace_id or run.source_id != source_id:
            return None
        records = [
            record for record in self._packages.list_by_run(run_id)
            if record.source_id == source_id and record.collection_run_id == run_id
        ]
        packages = sorted(
            (_trace_package(record.payload) for record in records),
            key=lambda package: (package.fetched_at or '', package.collected_document_id or ''),
        )
        return RunTrace(run_id=run_id, source_id=source_id, packages=tuple(packages))


__all__ = [
    'AttemptView',
    'LastCollection',
    'REDACTED',
    'RevisionView',
    'RunCounters',
    'RunTrace',
    'RunView',
    'SENSITIVE_HEADER_MARKERS',
    'SourceDetail',
    'SourceHealth',
    'SourceListFilter',
    'SourceQueryService',
    'SourceRevisionReader',
    'SourceSummary',
    'TracePackage',
    'TraceStep',
    'redact_headers',
    'redact_locator',
]
