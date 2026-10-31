"""E-16: CreateVoiceTrack and CreateWordTiming command handlers (CT-TTS-001, CT-SUB-001, CT-RND-002, CT-EVT-002).

Application layer: only domain, ports and controlplane types; no I/O, no clock, no adapter import.
The WAV file is named by the injected place_artifact(artifact_ref, wav_bytes) callable (DQ-13: voice-artifact-<sha256 of the WAV bytes>); this module does no file I/O.
Each command writes outputs, receipt and outbox event in one unit of work: all commit together or none does.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from controlplane.application.idempotency.canonicalization import request_hash
from controlplane.domain.interfaces.outbox import IOutboxWriter
from voice.domain.language_evidence import (
    LOCALE_REPORT_FIELD,
    LanguageEvidence,
    RevisionMismatchError,
    build_language_evidence,
)
from voice.domain.speed_fit import SpeedFitPolicy, plan_speed_fit
from voice.domain.timing_binding import TimingBinding, require_valid_timing
from voice.domain.timing_coverage import (
    CoverageReport,
    GapReport,
    TokenizationPolicy,
    build_gap_report,
    check_coverage,
)
from voice.domain.tts_invocation import TtsInvocationRecord, run_tts_attempts
from voice.domain.voice_track import (
    VOICE_DURATION_OUT_OF_RANGE,
    DurationFinding,
    VoiceTrack,
    VoiceTrackValidationError,
    check_duration,
    compute_voice_hash,
    validate_voice_track_request,
    verify_script_binding,
)
from voice.domain.word_timing import WordTimingRecord, validate_word_timing
from voice.ports.aligner import AlignerPort, AlignmentRequest
from voice.ports.repositories import (
    KIND_VOICE,
    KIND_WORD_TIMING,
    EventContext,
    OutputRepository,
    build_voice_ready,
    build_word_timing_ready,
    deduplication_id_for,
)
from voice.ports.script_text import ScriptTextPort
from voice.ports.tts import TtsEnginePort, VoiceRoutePort

INPUT_NOT_READY = 'INPUT_NOT_READY'
IDEMPOTENCY_CONFLICT = 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'
WORD_COVERAGE_INCOMPLETE = 'word_coverage_incomplete'
COMMAND_CREATE_VOICE_TRACK = 'CreateVoiceTrack'
COMMAND_CREATE_WORD_TIMING = 'CreateWordTiming'
KIND_TTS_INVOCATION = 'tts_invocation'
KIND_RECEIPT = 'receipt'
KIND_TIMING_REPORT = 'timing_report'
KIND_LANGUAGE_EVIDENCE = 'language_evidence'
WARNING_SPEED_FIT_APPLIED = 'speed_fit_applied'


class IdempotencyConflict(ValueError):
    def __init__(self, operation_key: str) -> None:
        self.code = IDEMPOTENCY_CONFLICT
        self.operation_key = operation_key
        super().__init__(f'{IDEMPOTENCY_CONFLICT}: {operation_key}')


class PipelineInputNotReady(Exception):
    def __init__(self, reason: str) -> None:
        self.code = INPUT_NOT_READY
        self.reason = reason
        super().__init__(f'{INPUT_NOT_READY}: {reason}')


class VoiceGenerationFailed(Exception):
    """Every TTS attempt failed; records are the committed failed invocation records and code is the last error code."""

    def __init__(self, code: str, message: str, *, retryable: bool, records: tuple[TtsInvocationRecord, ...]) -> None:
        self.code = code
        self.retryable = retryable
        self.records = records
        super().__init__(f'{code}: {message}')


class VoiceDurationRejected(Exception):
    def __init__(self, finding: DurationFinding, *, first_finding: DurationFinding | None = None) -> None:
        self.code = VOICE_DURATION_OUT_OF_RANGE
        self.finding = finding
        self.first_finding = first_finding
        super().__init__(f'{self.code}: {finding.actual_duration_ms}')


class TimingCoverageIncomplete(Exception):
    def __init__(self, report: CoverageReport) -> None:
        self.code = WORD_COVERAGE_INCOMPLETE
        self.report = report
        super().__init__(f'{self.code}: missing={report.missing_indices} extra={report.extra_indices}')


@dataclasses.dataclass(frozen=True, kw_only=True)
class CreateVoiceTrackCommand:
    track_key: str
    voice_request: Mapping[str, object]
    route_request: Mapping[str, object]
    attempt_policy: Mapping[str, object] | None
    duration_policy: tuple[int, int] | list[int] | None
    context: EventContext
    speed_fit: SpeedFitPolicy | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class CreateWordTimingCommand:
    track_key: str
    voice_request: Mapping[str, object]
    tokenization_policy: TokenizationPolicy | None
    context: EventContext


@dataclasses.dataclass(frozen=True, kw_only=True)
class PipelineReceipt:
    command: str
    operation_key: str
    request_hash: str
    receipt_ref: str
    output_kind: str
    output_key: str
    output_revision: int


@dataclasses.dataclass(frozen=True, kw_only=True)
class TimingValidationReport:
    validation_report_ref: str
    timing_artifact_ref: str
    coverage: CoverageReport
    gap_report: GapReport
    aligner_revision: str


@dataclasses.dataclass(frozen=True)
class VoiceTrackOutcome:
    receipt: PipelineReceipt
    voice_track: VoiceTrack
    replayed: bool


@dataclasses.dataclass(frozen=True)
class WordTimingOutcome:
    receipt: PipelineReceipt
    timing: WordTimingRecord
    language_evidence: LanguageEvidence
    replayed: bool


class VoiceUnitOfWork(Protocol):
    """UoW of E-15 (in-memory now, PostgreSQL later): outputs and outbox share one transaction."""

    outputs: OutputRepository
    outbox: IOutboxWriter

    def __enter__(self) -> Any: ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

    def commit(self) -> None: ...


def _receipt_key(workspace_id: str, command: str, operation_key: str) -> str:
    return f'{workspace_id}:{command}:{operation_key}'


def _append(uow: Any, kind: str, key: str, record: object) -> int:
    latest = uow.outputs.latest(kind, key)
    revision = 1 if latest is None else latest.revision + 1
    uow.outputs.append(kind, key, revision, record)
    return revision


def _emit(uow: Any, event: Any) -> None:
    uow.outbox.append_event(event.event_name, event.aggregate_id, event.payload, deduplication_id_for(event))


def _judged(records: tuple[TtsInvocationRecord, ...], finding: DurationFinding | None, measured_ms: int, *, record_duration: bool) -> tuple[TtsInvocationRecord, ...]:
    """Mark the last (successful) record of a take with its validation verdict; with record_duration also store measured_duration_ms in its usage_metrics."""
    changes: dict[str, Any] = {'validation_result': 'failed' if finding is not None else 'passed'}
    if record_duration:
        changes['usage_metrics'] = {**dict(records[-1].usage_metrics), 'measured_duration_ms': measured_ms}
    return records[:-1] + (dataclasses.replace(records[-1], **changes),)


class VoicePipeline:
    def __init__(
        self,
        *,
        uow: VoiceUnitOfWork,
        script_port: ScriptTextPort,
        route_port: VoiceRoutePort,
        tts_engine: TtsEnginePort,
        aligner: AlignerPort,
        measure_duration_ms: Callable[[bytes], int],
        place_artifact: Callable[[str, bytes], object] | None = None,
    ) -> None:
        self._uow = uow
        self._script_port = script_port
        self._route_port = route_port
        self._tts_engine = tts_engine
        self._aligner = aligner
        self._measure_duration_ms = measure_duration_ms
        self._place_artifact = place_artifact

    def _replay(self, workspace_id: str, command: str, operation_key: str, digest: str) -> PipelineReceipt | None:
        stored = self._uow.outputs.latest(KIND_RECEIPT, _receipt_key(workspace_id, command, operation_key))
        if stored is None:
            return None
        if stored.record.request_hash != digest:
            raise IdempotencyConflict(operation_key)
        return stored.record

    def _stored_record(self, receipt: PipelineReceipt, kind: str) -> Any:
        return self._uow.outputs.revisions(kind, receipt.output_key)[receipt.output_revision - 1].record

    def _latest_voice(self, track_key: str) -> VoiceTrack:
        stored = self._uow.outputs.latest(KIND_VOICE, track_key)
        if stored is None:
            raise PipelineInputNotReady('voice_track_missing')
        return stored.record

    def _commit_invocations(self, track_key: str, records: tuple[TtsInvocationRecord, ...]) -> None:
        with self._uow as uow:
            for record in records:
                _append(uow, KIND_TTS_INVOCATION, track_key, record)
            uow.commit()

    def create_voice_track(self, command: CreateVoiceTrackCommand) -> VoiceTrackOutcome:
        request = command.voice_request
        issues = validate_voice_track_request(request)
        if issues:
            raise VoiceTrackValidationError(issues)
        workspace_id, operation_key = command.context.workspace_id, request['operation_key']
        digest = request_hash({'command': COMMAND_CREATE_VOICE_TRACK, 'request': dict(request)})
        replayed = self._replay(workspace_id, COMMAND_CREATE_VOICE_TRACK, operation_key, digest)
        if replayed is not None:
            return VoiceTrackOutcome(replayed, self._stored_record(replayed, KIND_VOICE), True)
        script_text = self._script_port.get_text(request['script_version_id'])
        verify_script_binding(request, script_text)
        # fail-closed on a missing or malformed duration policy before any TTS call; the finding is ignored here
        check_duration(0, command.duration_policy)
        decision = self._route_port.resolve(command.route_request)
        run = run_tts_attempts(
            self._tts_engine, decision, command.route_request, request, script_text, command.attempt_policy
        )
        if run.synthesis is None:
            self._commit_invocations(command.track_key, run.records)
            raise VoiceGenerationFailed(
                run.error.code, run.error.message, retryable=run.error.retryable, records=run.records
            )
        audio = run.synthesis.audio_bytes
        actual_duration_ms = self._measure_duration_ms(audio)
        finding = check_duration(actual_duration_ms, command.duration_policy)
        speed_fit = command.speed_fit
        records = _judged(run.records, finding, actual_duration_ms, record_duration=speed_fit is not None)
        speed_scale = None
        first_take_duration_ms = None
        if finding is not None and speed_fit is not None:
            first_finding = finding
            first_take_duration_ms = actual_duration_ms
            speed_scale = plan_speed_fit(actual_duration_ms, command.duration_policy, speed_fit)
            retake = run_tts_attempts(
                self._tts_engine, decision, command.route_request, request, script_text, command.attempt_policy,
                speed_scale=speed_scale,
            )
            offset = records[-1].attempt
            numbered = tuple(dataclasses.replace(item, attempt=offset + item.attempt) for item in retake.records)
            if retake.synthesis is None:
                records = records + numbered
                self._commit_invocations(command.track_key, records)
                raise VoiceGenerationFailed(
                    retake.error.code, retake.error.message, retryable=retake.error.retryable, records=records
                )
            run = retake
            audio = retake.synthesis.audio_bytes
            actual_duration_ms = self._measure_duration_ms(audio)
            finding = check_duration(actual_duration_ms, command.duration_policy)
            records = records + _judged(numbered, finding, actual_duration_ms, record_duration=True)
            if finding is not None:
                self._commit_invocations(command.track_key, records)
                raise VoiceDurationRejected(finding, first_finding=first_finding)
        elif finding is not None:
            self._commit_invocations(command.track_key, records)
            raise VoiceDurationRejected(finding)
        voice_hash = compute_voice_hash(audio)
        artifact_ref = f'voice-artifact-{voice_hash}'
        if self._place_artifact is not None:
            self._place_artifact(artifact_ref, audio)  # DQ-13: the file gets this exact name before anything is committed
        receipt_ref = f'receipt-{digest[:32]}'
        usage_metrics = run.synthesis.usage_metrics.to_dict()
        warnings: tuple[str, ...] = ()
        if speed_scale is not None:
            usage_metrics = {**usage_metrics, 'speed_scale': speed_scale, 'first_take_duration_ms': first_take_duration_ms}
            warnings = (WARNING_SPEED_FIT_APPLIED,)
        voice = VoiceTrack(
            voice_artifact_ref=artifact_ref,
            script_version_id=request['script_version_id'],
            script_fingerprint=request['script_fingerprint'],
            voice_hash=voice_hash,
            actual_duration_ms=actual_duration_ms,
            provider_model_voice_revision=run.synthesis.voice_revision,
            usage_metrics=usage_metrics,
            warnings=warnings,
            receipt_ref=receipt_ref,
        )
        with self._uow as uow:
            for record in records:
                _append(uow, KIND_TTS_INVOCATION, command.track_key, record)
            revision = _append(uow, KIND_VOICE, command.track_key, voice)
            receipt = PipelineReceipt(
                command=COMMAND_CREATE_VOICE_TRACK,
                operation_key=operation_key,
                request_hash=digest,
                receipt_ref=receipt_ref,
                output_kind=KIND_VOICE,
                output_key=command.track_key,
                output_revision=revision,
            )
            _append(uow, KIND_RECEIPT, _receipt_key(workspace_id, COMMAND_CREATE_VOICE_TRACK, operation_key), receipt)
            _emit(uow, build_voice_ready(
                command.context,
                aggregate_id=voice.voice_artifact_ref,
                aggregate_revision=revision,
                artifact_verified=True,
                voice_artifact_ref=voice.voice_artifact_ref,
                voice_hash=voice_hash,
                script_version_id=voice.script_version_id,
                receipt_ref=receipt_ref,
            ))
            uow.commit()
        return VoiceTrackOutcome(receipt, voice, False)

    def create_word_timing(self, command: CreateWordTimingCommand) -> WordTimingOutcome:
        request = command.voice_request
        issues = validate_voice_track_request(request)
        if issues:
            raise VoiceTrackValidationError(issues)
        workspace_id, operation_key = command.context.workspace_id, request['operation_key']
        digest = request_hash({'command': COMMAND_CREATE_WORD_TIMING, 'request': dict(request)})
        replayed = self._replay(workspace_id, COMMAND_CREATE_WORD_TIMING, operation_key, digest)
        if replayed is not None:
            self.require_current_timing(command.track_key, request)
            return WordTimingOutcome(
                replayed,
                self._stored_record(replayed, KIND_WORD_TIMING),
                self._stored_record(replayed, KIND_LANGUAGE_EVIDENCE),
                True,
            )
        script_text = self._script_port.get_text(request['script_version_id'])
        verify_script_binding(request, script_text)
        voice = self._latest_voice(command.track_key)
        mismatched = [name for name in ('script_version_id', 'script_fingerprint') if request[name] != getattr(voice, name)]
        if mismatched:
            raise RevisionMismatchError(mismatched)
        result = self._aligner.align(AlignmentRequest(
            voice_artifact_ref=voice.voice_artifact_ref,
            voice_hash=voice.voice_hash,
            voice_duration_ms=voice.actual_duration_ms,
            script_version_id=voice.script_version_id,
            script_text=script_text.text,
            expected_language=request['expected_language'],
        ))
        words = [dict(word) for word in result.words]
        boundaries = [dict(item) for item in result.segment_boundaries]
        content = request_hash({
            'script_fingerprint': request['script_fingerprint'],
            'voice_hash': voice.voice_hash,
            'aligner_revision': result.aligner_revision,
            'words': words,
            'segment_boundaries': boundaries,
        })[:32]
        timing = validate_word_timing({
            'script_version_id': voice.script_version_id,
            'script_fingerprint': voice.script_fingerprint,
            'voice_hash': voice.voice_hash,
            'timing_artifact_ref': f'timing-artifact-{content}',
            'words': words,
            'segment_boundaries': boundaries,
            'validation_report_ref': f'timing-report-{content}',
            'voice_duration_ms': voice.actual_duration_ms,
        })
        coverage = check_coverage(script_text.text, timing.words, command.tokenization_policy)
        if not coverage.complete:
            raise TimingCoverageIncomplete(coverage)
        gap_report = build_gap_report(timing.words, voice.actual_duration_ms, command.tokenization_policy)
        gaps = tuple(gap.to_payload() for gap in gap_report.alignment_gaps)
        timing = dataclasses.replace(timing, alignment_gaps=gaps)
        require_valid_timing(TimingBinding.from_word_timing(timing), script_text.script_fingerprint, voice.voice_hash)
        locale_report = {LOCALE_REPORT_FIELD: result.voice_locale_reported}
        evidence = build_language_evidence(request, voice, locale_report, timing)
        report = TimingValidationReport(
            validation_report_ref=timing.validation_report_ref,
            timing_artifact_ref=timing.timing_artifact_ref,
            coverage=coverage,
            gap_report=gap_report,
            aligner_revision=result.aligner_revision,
        )
        receipt_ref = f'receipt-{digest[:32]}'
        with self._uow as uow:
            revision = _append(uow, KIND_WORD_TIMING, command.track_key, timing)
            _append(uow, KIND_TIMING_REPORT, command.track_key, report)
            _append(uow, KIND_LANGUAGE_EVIDENCE, command.track_key, evidence)
            receipt = PipelineReceipt(
                command=COMMAND_CREATE_WORD_TIMING,
                operation_key=operation_key,
                request_hash=digest,
                receipt_ref=receipt_ref,
                output_kind=KIND_WORD_TIMING,
                output_key=command.track_key,
                output_revision=revision,
            )
            _append(uow, KIND_RECEIPT, _receipt_key(workspace_id, COMMAND_CREATE_WORD_TIMING, operation_key), receipt)
            _emit(uow, build_word_timing_ready(
                command.context,
                aggregate_id=timing.timing_artifact_ref,
                aggregate_revision=revision,
                artifact_verified=True,
                timing_artifact_ref=timing.timing_artifact_ref,
                voice_hash=voice.voice_hash,
                script_version_id=voice.script_version_id,
                validation_report_ref=timing.validation_report_ref,
            ))
            uow.commit()
        return WordTimingOutcome(receipt, timing, evidence, False)

    def require_current_timing(self, track_key: str, voice_request: Mapping[str, object]) -> WordTimingRecord:
        """Return the latest timing only while it is bound to the current script fingerprint and latest voice hash (TST-MEDIA-INV-007)."""
        issues = validate_voice_track_request(voice_request)
        if issues:
            raise VoiceTrackValidationError(issues)
        stored = self._uow.outputs.latest(KIND_WORD_TIMING, track_key)
        if stored is None:
            raise PipelineInputNotReady('word_timing_missing')
        voice = self._latest_voice(track_key)
        script_text = self._script_port.get_text(voice_request['script_version_id'])
        binding = TimingBinding.from_word_timing(stored.record)
        require_valid_timing(binding, script_text.script_fingerprint, voice.voice_hash)
        return stored.record
