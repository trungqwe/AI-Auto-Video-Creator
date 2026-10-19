"""E-19: read-only trace projection of voice, word timing and processed media (acceptance section 10 item 1 of contract 07).

Queries read through an injected TraceReader and never touch a provider, adapter, transport or repository writer, so a query cannot trigger TTS.
Every query is scoped to one workspace: an entry of another workspace is reported as not found, even when the reader returns it.
Views are rebuilt from an allowlist: no secret, execution grant, technical report or unredacted error text reaches a trace.
Provider, model and route come from the reader (the TtsInvocationRecord of E-14 is not delivered yet, ASSUMPTION); persistence waits for CONV-E-01.
"""
from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

from voice.domain.language_evidence import LanguageEvidence
from voice.domain.processing import ProcessingRequest, ProcessingResult, retention_intent
from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import WordTimingRecord

REDACTED = '[redacted]'
_SENSITIVE_RE = re.compile(r'password|secret|token|api[-_]?key|bearer|authorization|credential|traceback|stack trace', re.IGNORECASE)
_CODE_RE = re.compile(r'[A-Za-z0-9_.:/+-]{1,200}')
_URL_RE = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*://[^<>,;\s]+')


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string')
    return value


def _revision(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError('revision must be a positive integer')
    return value


def _code(value: object) -> str | None:
    """Identifier-like value, None for a non-string, REDACTED for free text or secret-like text."""
    if not isinstance(value, str):
        return None
    return value if _CODE_RE.fullmatch(value) and not _SENSITIVE_RE.search(value) else REDACTED


def redact_locator(value: str) -> str:
    """Scheme, host, port and path only; userinfo, query and fragment are dropped."""
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return REDACTED
    if not parts.scheme or not parts.netloc:
        return REDACTED
    return f'{parts.scheme}://{parts.netloc.rpartition("@")[2]}{parts.path}'


def _scrub(value: object) -> str:
    """Free text (warnings): secret-like or traceback text becomes REDACTED, URLs lose userinfo and query."""
    if not isinstance(value, str) or _SENSITIVE_RE.search(value):
        return REDACTED
    return _URL_RE.sub(lambda match: redact_locator(match.group(0)), value)


def _scrub_all(values: object) -> tuple[str, ...]:
    return tuple(_scrub(item) for item in values) if isinstance(values, (list, tuple)) else ()


def _metrics(values: Mapping[str, object]) -> tuple[tuple[str, int | float], ...]:
    """Numeric usage metrics whose names are identifier-like and not secret-like."""
    return tuple(sorted(
        (name, value) for name, value in values.items()
        if isinstance(name, str) and _CODE_RE.fullmatch(name) and not _SENSITIVE_RE.search(name)
        and isinstance(value, (int, float)) and not isinstance(value, bool)
    ))


@dataclasses.dataclass(frozen=True, kw_only=True)
class VoiceEntry:
    """One stored VoiceTrack revision plus the route facts the reader knows (provider, model, route ref)."""

    workspace_id: str
    key: str
    revision: int
    track: VoiceTrack
    provider_route_ref: str | None = None
    provider: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        _text(self.workspace_id, 'workspace_id')
        _text(self.key, 'key')
        _revision(self.revision)
        if not isinstance(self.track, VoiceTrack):
            raise TypeError('track must be a VoiceTrack')


@dataclasses.dataclass(frozen=True, kw_only=True)
class TimingEntry:
    """One stored WordTiming revision plus the LanguageEvidence recorded for it, if any."""

    workspace_id: str
    key: str
    revision: int
    timing: WordTimingRecord
    language_evidence: LanguageEvidence | None = None

    def __post_init__(self) -> None:
        _text(self.workspace_id, 'workspace_id')
        _text(self.key, 'key')
        _revision(self.revision)
        if not isinstance(self.timing, WordTimingRecord):
            raise TypeError('timing must be a WordTimingRecord')
        if self.language_evidence is not None and not isinstance(self.language_evidence, LanguageEvidence):
            raise TypeError('language_evidence must be a LanguageEvidence or None')


@dataclasses.dataclass(frozen=True, kw_only=True)
class MediaEntry:
    """One processing operation revision; ProcessingResult already guarantees a processor identity (tool and version)."""

    workspace_id: str
    operation_id: str
    revision: int
    request: ProcessingRequest
    result: ProcessingResult
    output_kind: str

    def __post_init__(self) -> None:
        _text(self.workspace_id, 'workspace_id')
        _text(self.operation_id, 'operation_id')
        _revision(self.revision)
        if not isinstance(self.request, ProcessingRequest):
            raise TypeError('request must be a ProcessingRequest')
        if not isinstance(self.result, ProcessingResult):
            raise TypeError('result must be a ProcessingResult')
        retention_intent(self.output_kind)


@runtime_checkable
class TraceReader(Protocol):
    """Read-only source of stored entries; it may return entries of other workspaces, the queries filter them out."""

    def voice_entries(self, workspace_id: str, key: str) -> tuple[VoiceEntry, ...]:
        ...

    def timing_entries(self, workspace_id: str, key: str) -> tuple[TimingEntry, ...]:
        ...

    def media_entries(self, workspace_id: str, operation_id: str) -> tuple[MediaEntry, ...]:
        ...


@dataclasses.dataclass(frozen=True)
class RevisionRef:
    """History item: voice_artifact_ref (voice), timing_artifact_ref (timing) or operation_receipt_ref (media) of that revision."""

    revision: int
    ref: str | None


@dataclasses.dataclass(frozen=True)
class VoiceTrace:
    workspace_id: str
    key: str
    revision: int
    voice_artifact_ref: str | None
    voice_hash: str
    script_version_id: str | None
    script_fingerprint: str
    provider_route_ref: str | None
    provider: str | None
    model: str | None
    voice_revision: str | None
    receipt_ref: str | None
    actual_duration_ms: int
    retention_class: str
    usage_metrics: tuple[tuple[str, int | float], ...]
    warnings: tuple[str, ...]
    history: tuple[RevisionRef, ...]


@dataclasses.dataclass(frozen=True)
class LanguageEvidenceView:
    evidence_ref: str | None
    expected_language: str | None
    voice_locale_reported: str | None
    subtitle_text_hash: str | None
    finding_codes: tuple[str | None, ...]


@dataclasses.dataclass(frozen=True)
class TimingTrace:
    workspace_id: str
    key: str
    revision: int
    timing_artifact_ref: str | None
    voice_hash: str
    script_version_id: str | None
    script_fingerprint: str
    validation_report_ref: str | None
    voice_duration_ms: int | None
    word_count: int
    language_evidence: LanguageEvidenceView | None
    retention_class: str
    history: tuple[RevisionRef, ...]


@dataclasses.dataclass(frozen=True)
class InputRef:
    ref: str | None
    content_sha256: str


@dataclasses.dataclass(frozen=True)
class ProcessedMediaTrace:
    workspace_id: str
    operation_id: str
    revision: int
    output_kind: str | None
    retention_class: str
    disposition: str
    input_artifact_refs: tuple[InputRef, ...]
    operation_spec_revision: str | None
    processor_tool: str | None
    processor_version: str | None
    input_fingerprint: str
    output_artifact_refs: tuple[str | None, ...]
    operation_receipt_ref: str | None
    warnings: tuple[str, ...]
    history: tuple[RevisionRef, ...]


def _check_query(reader: object, workspace_id: object, key: object, key_name: str, revision: object) -> None:
    if not isinstance(reader, TraceReader):
        raise TypeError('reader must be a TraceReader')
    _text(workspace_id, 'workspace_id')
    _text(key, key_name)
    if revision is not None:
        _revision(revision)


def _owned(entries: Sequence, workspace_id: str, key_field: str, key: str) -> list:
    """Entries of this workspace and key only, ascending by revision; the reader is never trusted to filter."""
    return sorted(
        (item for item in entries if item.workspace_id == workspace_id and getattr(item, key_field) == key),
        key=lambda item: item.revision,
    )


def _pick(owned: Sequence, revision: int | None):
    if revision is None:
        return owned[-1] if owned else None
    matching = [item for item in owned if item.revision == revision]
    return matching[-1] if matching else None


def _history(owned: Sequence, ref_of: Callable[[object], object]) -> tuple[RevisionRef, ...]:
    return tuple(RevisionRef(item.revision, _code(ref_of(item))) for item in owned)


def trace_voice(reader: TraceReader, workspace_id: str, key: str, revision: int | None = None) -> VoiceTrace | None:
    """Trace one VoiceTrack revision (latest by default) back to script, route, provider, model, voice revision and receipt."""
    _check_query(reader, workspace_id, key, 'key', revision)
    owned = _owned(reader.voice_entries(workspace_id, key), workspace_id, 'key', key)
    entry = _pick(owned, revision)
    if entry is None:
        return None
    track = entry.track
    return VoiceTrace(
        workspace_id=entry.workspace_id,
        key=entry.key,
        revision=entry.revision,
        voice_artifact_ref=_code(track.voice_artifact_ref),
        voice_hash=track.voice_hash,
        script_version_id=_code(track.script_version_id),
        script_fingerprint=track.script_fingerprint,
        provider_route_ref=_code(entry.provider_route_ref),
        provider=_code(entry.provider),
        model=_code(entry.model),
        voice_revision=_code(track.provider_model_voice_revision),
        receipt_ref=_code(track.receipt_ref),
        actual_duration_ms=track.actual_duration_ms,
        retention_class=track.retention_class,
        usage_metrics=_metrics(track.usage_metrics),
        warnings=_scrub_all(track.warnings),
        history=_history(owned, lambda item: item.track.voice_artifact_ref),
    )


def _evidence_view(entry: TimingEntry) -> LanguageEvidenceView | None:
    """Evidence is attached only when it is bound to this exact timing, voice and script."""
    evidence, timing = entry.language_evidence, entry.timing
    if evidence is None:
        return None
    if (evidence.voice_hash, evidence.script_fingerprint, evidence.timing_artifact_ref) != (
        timing.voice_hash, timing.script_fingerprint, timing.timing_artifact_ref,
    ):
        return None
    return LanguageEvidenceView(
        evidence_ref=_code(evidence.evidence_ref),
        expected_language=_code(evidence.expected_language),
        voice_locale_reported=_code(evidence.voice_locale_reported),
        subtitle_text_hash=_code(evidence.subtitle_text_hash),
        finding_codes=tuple(_code(finding.code) for finding in evidence.findings),
    )


def trace_timing(reader: TraceReader, workspace_id: str, key: str, revision: int | None = None) -> TimingTrace | None:
    """Trace one WordTiming revision (latest by default) back to voice_hash, script fingerprint, validation report and language evidence."""
    _check_query(reader, workspace_id, key, 'key', revision)
    owned = _owned(reader.timing_entries(workspace_id, key), workspace_id, 'key', key)
    entry = _pick(owned, revision)
    if entry is None:
        return None
    timing = entry.timing
    return TimingTrace(
        workspace_id=entry.workspace_id,
        key=entry.key,
        revision=entry.revision,
        timing_artifact_ref=_code(timing.timing_artifact_ref),
        voice_hash=timing.voice_hash,
        script_version_id=_code(timing.script_version_id),
        script_fingerprint=timing.script_fingerprint,
        validation_report_ref=_code(timing.validation_report_ref),
        voice_duration_ms=timing.voice_duration_ms,
        word_count=len(timing.words),
        language_evidence=_evidence_view(entry),
        retention_class=retention_intent('word_timing').value,
        history=_history(owned, lambda item: item.timing.timing_artifact_ref),
    )


def trace_processed_media(
    reader: TraceReader, workspace_id: str, operation_id: str, revision: int | None = None
) -> ProcessedMediaTrace | None:
    """Trace one processing operation revision (latest by default) back to input refs, spec revision and processor identity."""
    _check_query(reader, workspace_id, operation_id, 'operation_id', revision)
    owned = _owned(reader.media_entries(workspace_id, operation_id), workspace_id, 'operation_id', operation_id)
    entry = _pick(owned, revision)
    if entry is None:
        return None
    request, result = entry.request, entry.result
    identity = result.processor_identity
    return ProcessedMediaTrace(
        workspace_id=entry.workspace_id,
        operation_id=entry.operation_id,
        revision=entry.revision,
        output_kind=_code(entry.output_kind),
        retention_class=retention_intent(entry.output_kind).value,
        disposition=result.disposition.value,
        input_artifact_refs=tuple(InputRef(_code(item.ref), item.content_sha256) for item in request.input_artifact_refs),
        operation_spec_revision=_code(request.operation_spec_revision),
        processor_tool=_code(identity['tool']),
        processor_version=_code(identity['version']),
        input_fingerprint=result.input_fingerprint,
        output_artifact_refs=tuple(_code(item.ref) for item in result.output_artifact_refs),
        operation_receipt_ref=_code(result.operation_receipt_ref),
        warnings=_scrub_all(result.warnings),
        history=_history(owned, lambda item: item.result.operation_receipt_ref),
    )


__all__ = [
    'InputRef',
    'LanguageEvidenceView',
    'MediaEntry',
    'ProcessedMediaTrace',
    'REDACTED',
    'RevisionRef',
    'TimingEntry',
    'TimingTrace',
    'TraceReader',
    'VoiceEntry',
    'VoiceTrace',
    'redact_locator',
    'trace_processed_media',
    'trace_timing',
    'trace_voice',
]
