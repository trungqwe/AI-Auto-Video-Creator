"""Production ActivityInputPort of E (PW-E3): input_refs of an ActivityRequest to the typed arguments of the one E command, and the output refs of the image safety chain (DQ-11).

Fan-out item rule: the item of an activity is the first ref of its ref_type in input_refs (the flow puts the item right after the workflow refs). An image that AssessImageSafety judged SAFE or UNCERTAIN reaches NormalizeMedia as the original, and a blurred copy reaches it unless its transform failed (a post assessment that is not SAFE is only a warning); an excluded image is replaced by the next media seed of the selection, and without a seed the activity succeeds with no output. TransformSensitiveImage follows the same rule: a request without a sensitive_image ref (no image needs the blur) succeeds with no output.
"""
from __future__ import annotations

import datetime
import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from controlplane.domain.orchestration import ExecutionGrant
from voice.adapters.profile_media_policy import (
    EXCLUDED,
    TRANSFORM,
    USABLE,
    build_image_safety_policy,
    build_image_safety_rules,
    build_loudness_constraints,
    build_mix_constraints,
    build_normalize_spec,
    build_transform_output_profile,
    build_transform_policy,
    build_vision_timeout_seconds,
    image_disposition,
)
from voice.adapters.real_llm_image_safety import LlmImageSafetyDetector, VisionRoutePort
from voice.application.media_pipeline import (
    KIND_IMAGE_SAFETY,
    KIND_PROCESSED_MEDIA,
    OP_ASSESS_IMAGE_SAFETY,
    OP_NORMALIZE_MEDIA,
    OP_PREPARE_AUDIO_BED,
    OP_PROBE_MEDIA,
    OP_TRANSFORM_SENSITIVE_IMAGE,
    VerifiedOutput,
)
from voice.application.voice_pipeline import (
    COMMAND_CREATE_VOICE_TRACK,
    COMMAND_CREATE_WORD_TIMING,
    CreateVoiceTrackCommand,
    CreateWordTimingCommand,
)
from voice.domain.audio_bed import AudioBedRequest, AudioCue
from voice.domain.image_safety import IMAGE_KIND, ImageSafetyAssessment
from voice.domain.image_transform import TransformRegion, TransformResult, TransformStatus
from voice.domain.normalize import compute_plan_fingerprint, compute_spec_fingerprint
from voice.domain.processing import ArtifactRef
from voice.domain.speed_fit import SpeedFitPolicy
from voice.domain.timing_coverage import TokenizationPolicy
from voice.ports.repositories import KIND_VOICE, EventContext, OutputRepository
from voice.ports.script_text import ScriptTextPort
from voice.worker.activity_handler import NO_OUTPUT_KEY, SUCCEEDED, VoiceActivityDeps, handle_activity, validate_activity_request

INPUT_NOT_READY = 'INPUT_NOT_READY'
UNKNOWN_ACTIVITY = 'UNKNOWN_ACTIVITY'
REF_SCRIPT = 'script_version'
REF_SNAPSHOT = 'production_snapshot'
REF_SELECTION = 'creative_asset_selection'
REF_PLAN = 'production_plan'
REF_SELECTED_MEDIA = 'selected_media'
REF_ASSESSMENT = 'image_safety_assessment'
REF_SENSITIVE_IMAGE = 'sensitive_image'
REF_MEDIA = 'media_artifact'
ASSESSMENT_PREFIX = 'assessment:'
REASON_SEED_FALLBACK = 'seed_fallback'
REASON_NO_SENSITIVE_IMAGE = 'no_sensitive_image'


class ActivityInputError(ValueError):
    """The input_refs cannot give the command its inputs; `code` is the stable token the activity handler reports."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class MediaArtifact:
    """One stored image: its ArtifactRef (ref and sha256) and what ProbeMedia declares about it."""

    ref: ArtifactRef
    declared_extension: str | None
    declared_mime: str | None
    observed_size: int


@dataclass(frozen=True)
class PlanAudio:
    """Audio part of the production plan; loudness limits and bed gain come from the profile, not from here."""

    cues: tuple[AudioCue, ...]
    preset_audio_policy_revision: str
    mix_constraints: Mapping[str, object]
    fallback_allowed: bool
    fallback_artifact_refs: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class VoiceSettings:
    voice_profile_ref: str
    provider_route_ref: str
    expected_language: str
    data_sensitivity: str
    max_cost_class: str
    duration_policy: tuple[int, int]
    tokenization_policy: TokenizationPolicy
    attempt_policy: Mapping[str, object] | None = None
    speed_fit: SpeedFitPolicy | None = None


@dataclass(frozen=True)
class NormalizeSource:
    artifact: ArtifactRef | None
    reason: str


@dataclass(frozen=True)
class _Frame:
    workspace_id: str
    job_id: str
    operation_key: str
    refs: Sequence[Mapping[str, Any]]


class MediaArtifactPort(Protocol):
    def media_artifact(self, *, workspace_id: str, media_asset_id: str, artifact_version_ref: str) -> MediaArtifact:
        ...


class PlanAudioPort(Protocol):
    def plan_audio(self, *, workspace_id: str, production_plan_id: str) -> PlanAudio:
        ...


class SelectionFallbackPort(Protocol):
    def fallback_media(self, *, workspace_id: str, selection_ref: str) -> Sequence[MediaArtifact]:
        """Media seed of the selection, in order; seeds are trusted media and replace excluded images one for one."""
        ...


class LazyVerifiedOutputs(Mapping):
    """verified_outputs of the media commands: the output ref exists only after the tool ran, so the evidence of I is asked per ref when the pipeline reads it."""

    def __init__(self, verify: Callable[[str], VerifiedOutput | None]) -> None:
        self._verify = verify

    def __getitem__(self, ref: str) -> VerifiedOutput:
        item = self._verify(ref)
        if not isinstance(item, VerifiedOutput):
            raise KeyError(ref)
        return item

    def __iter__(self):
        return iter(())

    def __len__(self) -> int:
        return 0


def _iso(moment: datetime.datetime) -> str:
    if not isinstance(moment, datetime.datetime) or moment.tzinfo is None:
        raise ValueError('clock must return a timezone-aware datetime')
    return moment.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _refs_of(refs: Sequence[Mapping[str, Any]], ref_type: str) -> list[Mapping[str, Any]]:
    return [ref for ref in refs if ref.get('ref_type') == ref_type and _is_text(ref.get('ref_id'))]


def _first_ref(refs: Sequence[Mapping[str, Any]], ref_type: str) -> Mapping[str, Any]:
    found = _refs_of(refs, ref_type)
    if not found:
        raise ActivityInputError(INPUT_NOT_READY, f'missing_{ref_type}_ref')
    return found[0]


def _last_ref(refs: Sequence[Mapping[str, Any]], ref_type: str) -> Mapping[str, Any]:
    found = _refs_of(refs, ref_type)
    if not found:
        raise ActivityInputError(INPUT_NOT_READY, f'missing_{ref_type}_ref')
    return found[-1]


def _revision_id(ref: Mapping[str, Any]) -> str:
    value = ref.get('revision_id')
    if not _is_text(value):
        raise ActivityInputError(INPUT_NOT_READY, 'missing_revision_id')
    return value


def _track_key(job_id: str) -> str:
    return f'track:{job_id}'


class ProductionActivityInputs:
    """ActivityInputPort of E for production: `resolve` returns {'command': <E-16 command>} for the two voice activities and the keyword arguments of the MediaPipeline method (with `context` where the method has it, never operation_key) for the media activities; `resolve` returns {NO_OUTPUT_KEY: reason} for TransformSensitiveImage when there is no sensitive_image ref."""

    def __init__(
        self, *, parameters: Mapping[str, object], tool_version: str, scripts: ScriptTextPort, outputs: OutputRepository,
        media: MediaArtifactPort, plans: PlanAudioPort, selections: SelectionFallbackPort, vision: VisionRoutePort,
        read_image: Callable[[str], tuple[bytes, str]], verify_output: Callable[[str], VerifiedOutput | None],
        settings: VoiceSettings, clock: Callable[[], datetime.datetime],
    ) -> None:
        self._rules = build_image_safety_rules(parameters)
        self._safety_policy = build_image_safety_policy(parameters)
        self._transform_policy = build_transform_policy(parameters)
        self._output_profile = build_transform_output_profile(parameters)
        self._normalize_spec = build_normalize_spec(parameters, tool_version=tool_version)
        self._loudness = build_loudness_constraints(parameters)
        self._mix = build_mix_constraints(parameters)
        self._vision_timeout = build_vision_timeout_seconds(parameters)
        self._scripts = scripts
        self._outputs = outputs
        self._media = media
        self._plans = plans
        self._selections = selections
        self._vision = vision
        self._read_image = read_image
        self._verify_output = verify_output
        self._settings = settings
        self._clock = clock
        self._detectors: dict[str, LlmImageSafetyDetector] = {}
        self._builders = {
            COMMAND_CREATE_VOICE_TRACK: self._voice_track, COMMAND_CREATE_WORD_TIMING: self._word_timing,
            OP_PROBE_MEDIA: self._probe, OP_ASSESS_IMAGE_SAFETY: self._assess,
            OP_TRANSFORM_SENSITIVE_IMAGE: self._transform, OP_NORMALIZE_MEDIA: self._normalize,
            OP_PREPARE_AUDIO_BED: self._audio_bed,
        }


    def resolve(self, activity_name: str, request: Mapping[str, Any], grant: ExecutionGrant) -> dict[str, Any]:
        builder = self._builders.get(activity_name)
        if builder is None:
            raise ActivityInputError(UNKNOWN_ACTIVITY, 'unknown_activity')
        key = request['operation_key']
        frame = _Frame(grant.workspace_id, request.get('video_job_id') or grant.job_id, key, request['input_refs'])
        context = EventContext(
            workspace_id=grant.workspace_id, correlation_id=request['workflow_run_id'], actor='voice-worker',
            occurred_at=_iso(self._clock()), recovery_epoch=str(grant.recovery_epoch), event_id=f'evt:{key}', message_id=f'msg:{key}')
        return builder(frame, grant, context)

    def _voice_request(self, frame: _Frame, grant: ExecutionGrant) -> dict[str, Any]:
        script_id = _last_ref(frame.refs, REF_SCRIPT)['ref_id']
        text = self._scripts.get_text(script_id)
        return {
            'script_version_id': script_id, 'script_fingerprint': text.script_fingerprint,
            'voice_profile_ref': self._settings.voice_profile_ref, 'provider_route_ref': self._settings.provider_route_ref,
            'expected_language': self._settings.expected_language, 'operation_key': frame.operation_key,
            'execution_grant_ref': grant.operation_id,
        }

    def _voice_track(self, frame: _Frame, grant: ExecutionGrant, context: EventContext) -> dict[str, Any]:
        settings = self._settings
        route_request = {
            'ai_role': 'voice_synthesis', 'job_ref': frame.job_id, 'snapshot_ref': _last_ref(frame.refs, REF_SNAPSHOT)['ref_id'],
            'config_refs': [], 'data_sensitivity': settings.data_sensitivity,
            'quality_latency_cost_bounds': {'max_cost_class': settings.max_cost_class}, 'allowed_fallbacks': [],
        }
        return {'command': CreateVoiceTrackCommand(
            track_key=_track_key(frame.job_id), voice_request=self._voice_request(frame, grant), route_request=route_request,
            attempt_policy=settings.attempt_policy, duration_policy=settings.duration_policy, context=context,
            speed_fit=settings.speed_fit)}

    def _word_timing(self, frame: _Frame, grant: ExecutionGrant, context: EventContext) -> dict[str, Any]:
        return {'command': CreateWordTimingCommand(
            track_key=_track_key(frame.job_id), voice_request=self._voice_request(frame, grant),
            tokenization_policy=self._settings.tokenization_policy, context=context)}

    def _artifact(self, workspace_id: str, item: Mapping[str, Any]) -> MediaArtifact:
        return self._media.media_artifact(workspace_id=workspace_id, media_asset_id=item['ref_id'], artifact_version_ref=_revision_id(item))

    def _probe(self, frame: _Frame, grant: ExecutionGrant, context: EventContext) -> dict[str, Any]:
        art = self._artifact(frame.workspace_id, _first_ref(frame.refs, REF_SELECTED_MEDIA))
        return {'artifact_ref': art.ref, 'declared_extension': art.declared_extension, 'declared_mime': art.declared_mime, 'observed_size': art.observed_size}

    def _assess(self, frame: _Frame, grant: ExecutionGrant, context: EventContext) -> dict[str, Any]:
        art = self._artifact(frame.workspace_id, _first_ref(frame.refs, REF_SELECTED_MEDIA))
        detector = LlmImageSafetyDetector(self._vision, art.ref, self._read_image, categories=self._rules.categories, timeout_seconds=self._vision_timeout, uncertain_min=self._rules.uncertain_min, transform_min=self._rules.uncertain_max_exclusive, region_categories=tuple(sorted(self._rules.blur_categories)))
        self._detectors[frame.operation_key] = detector
        return {'context': context, 'artifact_ref': art.ref, 'media_kind': IMAGE_KIND, 'detector': detector, 'policy': self._safety_policy}

    def _stored_assessment(self, assessment_ref: str) -> ImageSafetyAssessment:
        stored = self._outputs.latest(KIND_IMAGE_SAFETY, assessment_ref.removeprefix(ASSESSMENT_PREFIX))
        if stored is None:
            raise ActivityInputError(INPUT_NOT_READY, 'assessment_not_stored')
        return stored.record

    def _verdict(self, refs: Sequence[Mapping[str, Any]], media_id: str) -> tuple[str, str, ArtifactRef | None]:
        """(kind, reason, processed): SAFE and UNCERTAIN images are usable as the original; a blurred copy is usable unless the transform failed, and a post assessment that is not SAFE is only a warning (RG-13)."""
        link = next((ref for ref in _refs_of(refs, REF_ASSESSMENT) if ref.get('source_ref_id') == media_id), None)
        if link is None:
            return (EXCLUDED, 'not_assessed', None)
        assessment = self._stored_assessment(link['ref_id'])
        has_regions = any(ref['ref_id'] == media_id and ref.get('regions') for ref in _refs_of(refs, REF_SENSITIVE_IMAGE))
        kind, reason = image_disposition(assessment, self._rules, has_regions=has_regions)
        if kind != TRANSFORM:
            return (kind, reason, None)
        made = next((ref for ref in _refs_of(refs, REF_MEDIA) if ref.get('produced_by') == OP_TRANSFORM_SENSITIVE_IMAGE and ref.get('source_ref_id') == media_id), None)
        stored = None if made is None else self._outputs.latest(KIND_PROCESSED_MEDIA, made['operation_key'])
        record = None if stored is None else stored.record
        if not isinstance(record, TransformResult) or record.status is TransformStatus.FAILURE:
            return (EXCLUDED, 'transform_failed', None)
        return (TRANSFORM, 'blurred' if record.status is TransformStatus.SUCCESS else 'blurred_with_warning', record.processed_ref)

    def normalize_source(self, workspace_id: str, refs: Sequence[Mapping[str, Any]]) -> NormalizeSource:
        """The image NormalizeMedia may take for the first selected_media item: the original when SAFE, the blurred copy when SAFE after the transform, else the media seed of the selection with the same rank among the excluded images, else nothing."""
        item = _first_ref(refs, REF_SELECTED_MEDIA)
        kind, reason, processed = self._verdict(refs, item['ref_id'])
        if kind == USABLE:
            return NormalizeSource(self._artifact(workspace_id, item).ref, reason)
        if kind == TRANSFORM:
            return NormalizeSource(processed, reason)
        ordered = list(dict.fromkeys(ref['source_ref_id'] for ref in _refs_of(refs, REF_ASSESSMENT) if _is_text(ref.get('source_ref_id'))))
        for ref in _refs_of(refs, REF_SELECTED_MEDIA):
            if ref['ref_id'] not in ordered:
                ordered.append(ref['ref_id'])
        excluded = [ref_id for ref_id in ordered if self._verdict(refs, ref_id)[0] == EXCLUDED]
        selections = _refs_of(refs, REF_SELECTION)
        seeds = () if not selections else tuple(self._selections.fallback_media(workspace_id=workspace_id, selection_ref=selections[-1]['ref_id']))
        position = excluded.index(item['ref_id'])
        if position < len(seeds):
            return NormalizeSource(seeds[position].ref, REASON_SEED_FALLBACK)
        return NormalizeSource(None, reason)

    def _transform(self, frame: _Frame, grant: ExecutionGrant, context: EventContext) -> dict[str, Any]:
        if not _refs_of(frame.refs, REF_SENSITIVE_IMAGE):
            return {NO_OUTPUT_KEY: REASON_NO_SENSITIVE_IMAGE}
        item = _first_ref(frame.refs, REF_SENSITIVE_IMAGE)
        art = self._artifact(frame.workspace_id, item)
        try:
            regions = tuple(TransformRegion(raw['category'], raw['confidence'], raw['mask_ref']) for raw in item['regions'])
            assessment_ref = item['assessment_ref']
        except (KeyError, TypeError):
            raise ActivityInputError(INPUT_NOT_READY, 'invalid_sensitive_image_ref') from None
        return {
            'context': context, 'media_kind': IMAGE_KIND, 'user_visual_hook': False,
            'assessment': self._stored_assessment(assessment_ref), 'source_ref': art.ref, 'regions': regions,
            'policy': self._transform_policy, 'output_profile': self._output_profile,
            'verified_outputs': LazyVerifiedOutputs(self._verify_output),
        }

    def _normalize(self, frame: _Frame, grant: ExecutionGrant, context: EventContext) -> dict[str, Any]:
        source = self.normalize_source(frame.workspace_id, frame.refs)
        if source.artifact is None:
            raise ActivityInputError(INPUT_NOT_READY, f'image_excluded:{source.reason}')
        plan_fp = compute_plan_fingerprint(source.artifact, compute_spec_fingerprint(self._normalize_spec))
        output_ref = 'rendition:' + hashlib.sha256(f'{frame.operation_key}|{plan_fp}'.encode('utf-8')).hexdigest()
        return {
            'context': context, 'input_ref': source.artifact, 'spec': self._normalize_spec, 'media_kind': IMAGE_KIND,
            'output_ref': output_ref,
            'verified_outputs': LazyVerifiedOutputs(self._verify_output),
        }

    def _audio_bed(self, frame: _Frame, grant: ExecutionGrant, context: EventContext) -> dict[str, Any]:
        plan = self._plans.plan_audio(workspace_id=frame.workspace_id, production_plan_id=_last_ref(frame.refs, REF_PLAN)['ref_id'])
        voice = self._outputs.latest(KIND_VOICE, _track_key(frame.job_id))
        if voice is None:
            raise ActivityInputError(INPUT_NOT_READY, 'voice_track_missing')
        request = AudioBedRequest(
            cues=tuple(plan.cues), voice_artifact_ref=voice.record.voice_artifact_ref,
            preset_audio_policy_revision=plan.preset_audio_policy_revision, loudness_constraints=self._loudness,
            mix_constraints={**plan.mix_constraints, **self._mix}, fallback_allowed=plan.fallback_allowed,
            fallback_artifact_refs=tuple(plan.fallback_artifact_refs))
        return {'context': context, 'request': request, 'verified_outputs': LazyVerifiedOutputs(self._verify_output)}

    def assessment_refs(self, request: Mapping[str, Any]) -> list[dict[str, Any]]:
        """One image_safety_assessment ref per image; a sensitive_image item (with the blur regions) only for an image that must be blurred and has regions. Regions come from the detector of this call: a replayed call has none, so the image is excluded (fail closed)."""
        key = request['operation_key']
        item = _first_ref(request['input_refs'], REF_SELECTED_MEDIA)
        detector = self._detectors.pop(key, None)
        regions = () if detector is None else detector.regions
        link = {'ref_type': REF_ASSESSMENT, 'ref_id': f'{ASSESSMENT_PREFIX}{key}', 'source_ref_id': item['ref_id'], 'revision_id': _revision_id(item)}
        refs = [link]
        stored = self._outputs.latest(KIND_IMAGE_SAFETY, key)
        if stored is None:
            return refs
        usable = tuple(region for region in regions if region.category in stored.record.categories)
        if image_disposition(stored.record, self._rules, has_regions=bool(usable))[0] == TRANSFORM:
            refs.append({
                'ref_type': REF_SENSITIVE_IMAGE, 'ref_id': item['ref_id'], 'revision_id': _revision_id(item),
                'assessment_ref': link['ref_id'],
                'regions': [{'category': r.category, 'confidence': r.confidence, 'mask_ref': r.mask_ref} for r in usable],
            })
        return refs

    def transform_refs(self, request: Mapping[str, Any], result_refs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        item = _first_ref(request['input_refs'], REF_SENSITIVE_IMAGE)
        return [
            {**ref, 'source_ref_id': item['ref_id'], 'produced_by': OP_TRANSFORM_SENSITIVE_IMAGE, 'operation_key': request['operation_key']}
            for ref in result_refs
        ]

def _skipped(grant: ExecutionGrant, deps: VoiceActivityDeps, warning: str) -> dict[str, Any]:
    """Succeeded result without output for an image that must not be normalized (DQ-11); built like handle_activity builds its results."""
    moment = deps.clock()
    if not isinstance(moment, datetime.datetime) or moment.tzinfo is None:
        raise ValueError('clock must return a timezone-aware datetime')
    return {
        'stage_run_id': grant.stage_run_id, 'grant_id': grant.operation_id, 'execution_generation': grant.execution_generation,
        'recovery_epoch': str(grant.recovery_epoch), 'disposition': SUCCEEDED, 'output_refs': [],
        'completed_at': moment.astimezone(datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + 'Z',
        'warnings': [warning],
    }


def handle_voice_activity(request: Mapping[str, Any], grant: ExecutionGrant, deps: VoiceActivityDeps, inputs: ProductionActivityInputs) -> dict[str, Any]:
    name = request.get('activity_name')
    if name == OP_NORMALIZE_MEDIA and not validate_activity_request(request, grant) and deps.grants.is_grant_current(grant):
        try:
            source = inputs.normalize_source(grant.workspace_id, request['input_refs'])
        except ActivityInputError:
            source = None
        if source is not None and source.artifact is None:
            return _skipped(grant, deps, f'image_excluded:{source.reason}')
    result = handle_activity(request, grant, deps)
    if result.get('disposition') != SUCCEEDED:
        return result
    if name == OP_ASSESS_IMAGE_SAFETY:
        return {**result, 'output_refs': inputs.assessment_refs(request)}
    if name == OP_TRANSFORM_SENSITIVE_IMAGE and result.get('output_refs'):
        return {**result, 'output_refs': inputs.transform_refs(request, result['output_refs'])}
    if name == OP_NORMALIZE_MEDIA and result.get('output_refs'):
        item = _first_ref(request['input_refs'], REF_SELECTED_MEDIA)
        return {**result, 'output_refs': [{**ref, 'source_ref_id': item['ref_id']} for ref in result['output_refs']]}
    return result


__all__ = (
    'ActivityInputError',
    'LazyVerifiedOutputs',
    'MediaArtifact',
    'MediaArtifactPort',
    'NormalizeSource',
    'PlanAudio',
    'PlanAudioPort',
    'ProductionActivityInputs',
    'SelectionFallbackPort',
    'VoiceSettings',
    'handle_voice_activity',
)
