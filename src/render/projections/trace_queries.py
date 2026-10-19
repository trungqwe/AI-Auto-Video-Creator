"""F-21: read-only trace projection of F (CT-RND-004, CT-QC-001, TST-E2E-001): walks an output back to its attempt, package, input hashes, tool, redacted command spec and QC gates.

Queries read only through a TraceStore (the read side of RenderRepository) and caller-supplied TraceLink entries; they never call a renderer, probe, inspector or writer.
Every query is scoped to one workspace: a chain of another workspace is reported as not found. Views are rebuilt from an allowlist, text is redacted again, and the four milestones stay four separate facts.
GIẢ ĐỊNH: F records hold no workspace, so TraceLink carries workspace_id, the quality report key and the upload (I) and completion (G) facts; a package without an attempt has no link yet. Persistence waits for CONV-F-01.

coveredIds: CT-RND-004, CT-QC-001 (truy vết), TST-E2E-001 (truy vết ngược từ output)
"""
from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from controlplane.domain.statemachine import OperationState
from render.domain.quality_report import GateResult
from render.domain.render_attempt import REDACTED, _redact
from render.ports.repositories import KIND_ATTEMPT, KIND_PACKAGE, KIND_QUALITY_REPORT

MAX_TEXT = 2000
_SENSITIVE_RE = re.compile(r'password|passwd|secret|token|api[-_]?key|bearer|authorization|credential|traceback|stack trace', re.IGNORECASE)
_CODE_RE = re.compile(r'[A-Za-z0-9_.:/+-]{1,200}')


class TraceNotFound(LookupError):
    """No stored chain of this workspace matches; a chain of another workspace gives the same error, so its existence never leaks."""

    def __init__(self) -> None:
        super().__init__('trace_not_found')


class TraceIncomplete(ValueError):
    """The chain back from an output is broken; reason and field are fixed codes, never stored values."""

    def __init__(self, reason: str, field: str) -> None:
        super().__init__(f'trace_incomplete: {reason} ({field})')
        self.reason = reason
        self.field = field


def _text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _positive(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')


def _code(value: object) -> str | None:
    """Identifier-like value, None for a non-string, REDACTED for free text or secret-like text."""
    if not isinstance(value, str):
        return None
    return value if _CODE_RE.fullmatch(value) and not _SENSITIVE_RE.search(value) else REDACTED


def _scrub(value: object) -> str:
    """Free text: secret assignments, bearer tokens and absolute paths are replaced first; text that still looks secret-like or holds a traceback becomes REDACTED."""
    if not isinstance(value, str):
        return REDACTED
    text = _redact(value, limit=MAX_TEXT)
    return REDACTED if _SENSITIVE_RE.search(text) else text


@dataclasses.dataclass(frozen=True, kw_only=True)
class TraceLink:
    """Caller-supplied edges of one attempt: its workspace, package id, quality report key and the facts F does not own (upload from I, completion from G; GIẢ ĐỊNH until CONV-F-01 stores them)."""

    workspace_id: str
    render_package_id: str
    render_attempt_id: str
    quality_report_key: str | None = None
    upload_verified: bool = False
    completion_committed: bool = False

    def __post_init__(self) -> None:
        for name in ('workspace_id', 'render_package_id', 'render_attempt_id'):
            _text(name, getattr(self, name))
        if self.quality_report_key is not None:
            _text('quality_report_key', self.quality_report_key)
        for name in ('upload_verified', 'completion_committed'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'{name} must be a bool')


def _checked(links: Iterable[TraceLink]) -> tuple[TraceLink, ...]:
    """Validate links: one link per attempt, and a package or report key belongs to one workspace only."""
    if isinstance(links, (str, bytes, Mapping)) or not isinstance(links, Iterable):
        raise TypeError('links must be an iterable of TraceLink')
    items = tuple(links)
    attempts: set[str] = set()
    owners: dict[tuple[str, str], str] = {}
    for link in items:
        if not isinstance(link, TraceLink):
            raise TypeError('links items must be TraceLink')
        if link.render_attempt_id in attempts:
            raise ValueError('duplicate trace link')
        attempts.add(link.render_attempt_id)
        for kind, value in (('package', link.render_package_id), ('report', link.quality_report_key)):
            if value is not None and owners.setdefault((kind, value), link.workspace_id) != link.workspace_id:
                raise ValueError(f'{kind} linked to two workspaces')
    return items


class _Payload:
    def to_payload(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class RevisionEntry:
    """One stored revision of a record; receipt_state is set for attempts only."""

    revision: int
    receipt_state: str | None


@dataclasses.dataclass(frozen=True)
class AttemptEntry:
    render_attempt_id: str | None
    revision: int
    receipt_state: str
    output_artifact_ref: str | None


@dataclasses.dataclass(frozen=True)
class InputArtifactView:
    artifact_version_id: str | None
    sha256: str | None
    size_bytes: int
    media_type: str | None


@dataclasses.dataclass(frozen=True)
class CommandSpecView:
    """Only redacted_argv is ever shown; the executable view of the argv is never read."""

    kind: str | None
    redacted_argv: tuple[str, ...]
    spec_fingerprint: str | None


@dataclasses.dataclass(frozen=True)
class GateView:
    gate: str
    kind: str
    status: str
    evidence_ref: str | None
    time_range: tuple[int, int] | None
    measured_value: bool | int | float | str | None
    threshold_revision: str | None
    reason: str | None


@dataclasses.dataclass(frozen=True)
class MilestonesView:
    """Four independent facts; there is deliberately no merged flag."""

    render_succeeded: bool
    qc_passed: bool
    upload_verified: bool
    completion_committed: bool


@dataclasses.dataclass(frozen=True, kw_only=True)
class PackageTrace(_Payload):
    workspace_id: str
    render_package_id: str
    revision: int
    package_fingerprint: str | None
    production_snapshot_ref: str | None
    script_version_ref: str | None
    production_plan_ref: str | None
    preset_revision_ref: str | None
    voice_artifact_ref: str | None
    word_timing_ref: str | None
    output_metadata_revision: str | None
    output_profile_revision: str | None
    language_validation_refs: tuple[str | None, ...]
    input_artifacts: tuple[InputArtifactView, ...]
    history: tuple[RevisionEntry, ...]
    attempts: tuple[AttemptEntry, ...]


@dataclasses.dataclass(frozen=True, kw_only=True)
class AttemptTrace(_Payload):
    workspace_id: str
    render_attempt_id: str
    revision: int
    attempt_revision: int
    render_package_id: str
    package_fingerprint: str | None
    output_artifact_ref: str | None
    tool_name: str
    tool_version: str
    build_version: str
    command_spec: CommandSpecView
    receipt_state: str
    receipt_ref: str | None
    started_at: str | None
    finished_at: str | None
    wall_time_ms: int | None
    peak_disk_bytes: int | None
    warnings: tuple[str, ...]
    error: str | None
    history: tuple[RevisionEntry, ...]


@dataclasses.dataclass(frozen=True, kw_only=True)
class QualityTrace(_Payload):
    workspace_id: str
    quality_report_key: str
    revision: int
    report_id: str | None
    policy_revision: str | None
    passed: bool
    blocking_gates: tuple[str, ...]
    gates: tuple[GateView, ...]
    history: tuple[RevisionEntry, ...]


@dataclasses.dataclass(frozen=True, kw_only=True)
class OutputTrace(_Payload):
    workspace_id: str
    output_artifact_ref: str | None
    attempt: AttemptTrace
    package: PackageTrace
    quality: QualityTrace | None
    milestones: MilestonesView


class _RecordReader(Protocol):
    def latest(self, kind: str, key: str) -> Any: ...

    def revisions(self, kind: str, key: str) -> tuple[Any, ...]: ...


class TraceStore(Protocol):
    """Read side of F storage (InMemoryUnitOfWork has this shape); the projection calls only latest and revisions."""

    renders: _RecordReader



def _state(record: object) -> str | None:
    state = getattr(record, 'receipt_state', None)
    return None if state is None else state.value


def _iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, 'isoformat') else None


def _stored(store: TraceStore, kind: str, key: str, revision: int | None) -> Any:
    if revision is None:
        return store.renders.latest(kind, key)
    return next((item for item in store.renders.revisions(kind, key) if item.revision == revision), None)


def _history(store: TraceStore, kind: str, key: str) -> tuple[RevisionEntry, ...]:
    return tuple(RevisionEntry(item.revision, _state(item.record)) for item in store.renders.revisions(kind, key))


def _check_query(workspace_id: object, key_name: str, key: object, revision: object = None) -> None:
    _text('workspace_id', workspace_id)
    _text(key_name, key)
    if revision is not None:
        _positive('revision', revision)


def _link_of(links: tuple[TraceLink, ...], workspace_id: str, field: str, value: str) -> TraceLink | None:
    return next((item for item in links if item.workspace_id == workspace_id and getattr(item, field) == value), None)


def _command_spec_view(raw: object) -> CommandSpecView:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise TraceIncomplete('command_spec_invalid', 'command_spec') from None
    argv = data.get('redacted_argv') if isinstance(data, Mapping) else None
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        raise TraceIncomplete('command_spec_invalid', 'command_spec')
    return CommandSpecView(
        kind=_code(data.get('kind')),
        redacted_argv=tuple(_scrub(item) for item in argv),
        spec_fingerprint=_code(data.get('spec_fingerprint')),
    )


def _check_package(store: TraceStore, link: TraceLink, attempt: Any) -> None:
    package = store.renders.latest(KIND_PACKAGE, link.render_package_id)
    if package is None:
        raise TraceIncomplete('package_missing', 'render_package_id')
    if package.record.package_fingerprint != attempt.package_fingerprint:
        raise TraceIncomplete('package_fingerprint_mismatch', 'package_fingerprint')


def _attempt_entry(store: TraceStore, link: TraceLink) -> AttemptEntry | None:
    stored = store.renders.latest(KIND_ATTEMPT, link.render_attempt_id)
    if stored is None:
        return None
    record = stored.record
    return AttemptEntry(
        render_attempt_id=_code(link.render_attempt_id),
        revision=stored.revision,
        receipt_state=record.receipt_state.value,
        output_artifact_ref=_code(record.output_artifact_ref),
    )


def _package_trace(store: TraceStore, links: tuple[TraceLink, ...], workspace_id: str, package_id: str, revision: int | None) -> PackageTrace:
    owned = [item for item in links if item.workspace_id == workspace_id and item.render_package_id == package_id]
    stored = _stored(store, KIND_PACKAGE, package_id, revision) if owned else None
    if stored is None:
        raise TraceNotFound()
    record = stored.record
    entries = (_attempt_entry(store, item) for item in owned)
    attempts = sorted((entry for entry in entries if entry is not None), key=lambda entry: entry.render_attempt_id or '')
    return PackageTrace(
        workspace_id=workspace_id,
        render_package_id=package_id,
        revision=stored.revision,
        package_fingerprint=_code(record.package_fingerprint),
        production_snapshot_ref=_code(record.production_snapshot_ref),
        script_version_ref=_code(record.script_version_ref),
        production_plan_ref=_code(record.production_plan_ref),
        preset_revision_ref=_code(record.preset_revision_ref),
        voice_artifact_ref=_code(record.voice_artifact_ref),
        word_timing_ref=_code(record.word_timing_ref),
        output_metadata_revision=_code(record.output_metadata_revision),
        output_profile_revision=_code(record.output_profile_revision),
        language_validation_refs=tuple(_code(item) for item in record.language_validation_refs),
        input_artifacts=tuple(
            InputArtifactView(_code(item.artifact_version_id), _code(item.sha256), item.size_bytes, _code(item.media_type))
            for item in record.input_artifacts
        ),
        history=_history(store, KIND_PACKAGE, package_id),
        attempts=tuple(attempts),
    )


def _attempt_trace(store: TraceStore, link: TraceLink, stored: Any) -> AttemptTrace:
    attempt = stored.record
    return AttemptTrace(
        workspace_id=link.workspace_id,
        render_attempt_id=link.render_attempt_id,
        revision=stored.revision,
        attempt_revision=attempt.revision,
        render_package_id=link.render_package_id,
        package_fingerprint=_code(attempt.package_fingerprint),
        output_artifact_ref=_code(attempt.output_artifact_ref),
        tool_name=_scrub(attempt.tool_name),
        tool_version=_scrub(attempt.tool_version),
        build_version=_scrub(attempt.build_version),
        command_spec=_command_spec_view(attempt.command_spec),
        receipt_state=attempt.receipt_state.value,
        receipt_ref=_code(attempt.receipt_ref),
        started_at=_iso(attempt.started_at),
        finished_at=_iso(attempt.finished_at),
        wall_time_ms=attempt.wall_time_ms,
        peak_disk_bytes=attempt.peak_disk_bytes,
        warnings=tuple(_scrub(item) for item in attempt.warnings),
        error=None if attempt.error is None else _scrub(attempt.error),
        history=_history(store, KIND_ATTEMPT, link.render_attempt_id),
    )


def _gate_view(item: GateResult) -> GateView:
    measured = item.measured_value
    return GateView(
        gate=item.gate.value,
        kind=item.kind.value,
        status=item.status.value,
        evidence_ref=_code(item.evidence_ref),
        time_range=item.time_range,
        measured_value=_scrub(measured) if isinstance(measured, str) else measured,
        threshold_revision=_code(item.threshold_revision),
        reason=None if item.reason is None else _scrub(item.reason),
    )


def _quality_trace(store: TraceStore, workspace_id: str, key: str, stored: Any) -> QualityTrace:
    report = stored.record
    return QualityTrace(
        workspace_id=workspace_id,
        quality_report_key=key,
        revision=stored.revision,
        report_id=_code(report.report_id),
        policy_revision=_code(report.policy_revision),
        passed=report.passed,
        blocking_gates=tuple(item.value for item in report.blocking_gates),
        gates=tuple(_gate_view(item) for item in report.gates),
        history=_history(store, KIND_QUALITY_REPORT, key),
    )


def _output_trace(store: TraceStore, links: tuple[TraceLink, ...], link: TraceLink, stored: Any) -> OutputTrace:
    attempt = stored.record
    _check_package(store, link, attempt)
    quality = None
    if link.quality_report_key is not None:
        report = store.renders.latest(KIND_QUALITY_REPORT, link.quality_report_key)
        if report is None:
            raise TraceIncomplete('quality_report_missing', 'quality_report_key')
        quality = _quality_trace(store, link.workspace_id, link.quality_report_key, report)
    return OutputTrace(
        workspace_id=link.workspace_id,
        output_artifact_ref=_code(attempt.output_artifact_ref),
        attempt=_attempt_trace(store, link, stored),
        package=_package_trace(store, links, link.workspace_id, link.render_package_id, None),
        quality=quality,
        milestones=MilestonesView(
            render_succeeded=attempt.receipt_state is OperationState.SUCCEEDED,
            qc_passed=quality is not None and quality.passed,
            upload_verified=link.upload_verified,
            completion_committed=link.completion_committed,
        ),
    )


def trace_render_package(store: TraceStore, links: Iterable[TraceLink], *, workspace_id: str, render_package_id: str, revision: int | None = None) -> PackageTrace:
    """Trace one package revision (latest by default) to its refs, input hashes and every attempt; TraceNotFound outside workspace_id; never calls a renderer or probe."""
    _check_query(workspace_id, 'render_package_id', render_package_id, revision)
    return _package_trace(store, _checked(links), workspace_id, render_package_id, revision)


def trace_attempt(store: TraceStore, links: Iterable[TraceLink], *, workspace_id: str, render_attempt_id: str, revision: int | None = None) -> AttemptTrace:
    """Trace one attempt revision (latest by default) to tool, build, redacted command spec and its package; TraceIncomplete when the package chain is broken."""
    _check_query(workspace_id, 'render_attempt_id', render_attempt_id, revision)
    link = _link_of(_checked(links), workspace_id, 'render_attempt_id', render_attempt_id)
    stored = None if link is None else _stored(store, KIND_ATTEMPT, render_attempt_id, revision)
    if stored is None:
        raise TraceNotFound()
    _check_package(store, link, stored.record)
    return _attempt_trace(store, link, stored)


def trace_quality_report(store: TraceStore, links: Iterable[TraceLink], *, workspace_id: str, quality_report_key: str, revision: int | None = None) -> QualityTrace:
    """Trace one QualityReport revision (latest by default) to every gate with its evidence and the blocking gates."""
    _check_query(workspace_id, 'quality_report_key', quality_report_key, revision)
    items = _checked(links)
    owned = any(item.workspace_id == workspace_id and item.quality_report_key == quality_report_key for item in items)
    stored = _stored(store, KIND_QUALITY_REPORT, quality_report_key, revision) if owned else None
    if stored is None:
        raise TraceNotFound()
    return _quality_trace(store, workspace_id, quality_report_key, stored)


def trace_output(store: TraceStore, links: Iterable[TraceLink], *, workspace_id: str, output_artifact_ref: str) -> OutputTrace:
    """Trace an output back to its latest attempt, package, QC report and the four separate milestones; TraceNotFound outside workspace_id."""
    _text('workspace_id', workspace_id)
    _text('output_artifact_ref', output_artifact_ref)
    items = _checked(links)
    for item in items:
        if item.workspace_id != workspace_id:
            continue
        stored = store.renders.latest(KIND_ATTEMPT, item.render_attempt_id)
        if stored is not None and stored.record.output_artifact_ref == output_artifact_ref:
            return _output_trace(store, items, item, stored)
    raise TraceNotFound()


__all__ = [
    'AttemptEntry',
    'AttemptTrace',
    'CommandSpecView',
    'GateView',
    'InputArtifactView',
    'MilestonesView',
    'OutputTrace',
    'PackageTrace',
    'QualityTrace',
    'RevisionEntry',
    'TraceIncomplete',
    'TraceLink',
    'TraceNotFound',
    'TraceStore',
    'trace_attempt',
    'trace_output',
    'trace_quality_report',
    'trace_render_package',
]
