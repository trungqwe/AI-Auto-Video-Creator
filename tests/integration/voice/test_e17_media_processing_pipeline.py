"""E-17: command xử lý media và audio bed (CT-PROC-003..CT-PROC-007, CT-AUD-001, CT-STATE-011).

coveredIds: TST-E2E-011 (phía E), CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007, CT-AUD-001
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from voice.adapters.memory import InMemoryUnitOfWork
from voice.application.media_pipeline import (
    AudioBedOutcome,
    IdempotencyConflictError,
    ImageBatchItem,
    MediaPipeline,
    RetryNotAllowedError,
    VerifiedOutput,
)
from voice.domain.audio_bed import (
    AudioBedRejected,
    AudioBedRequest,
    AudioCue,
    LoudnessConstraints,
    LoudnessReport,
    PreparedRendition,
)
from voice.domain.image_safety import (
    ImageDetection,
    ImageSafetyAssessment,
    ImageSafetyError,
    ImageSafetyPolicy,
    SafetyOutcome,
)
from voice.domain.image_transform import TransformOutput, TransformPolicy, TransformRegion
from voice.domain.normalize import SAFETY_TRANSFORM_NOT_APPLICABLE, NormalizeSpec, NormalizeStep, plan_rendition
from voice.domain.probe import MediaType, Readability
from voice.domain.processing import ArtifactRef, Disposition, ProcessingContractError
from voice.ports.media_tool import ToolOutcome
from voice.ports.repositories import EventContext

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'voice' / 'application' / 'media_pipeline.py'
SHA_A, SHA_B, SHA_C, SHA_D = 'a' * 64, 'b' * 64, 'c' * 64, 'd' * 64
IMAGE_REF = ArtifactRef('img-1', SHA_A)
CLIP_REF = ArtifactRef('clip-1', SHA_A)

IMAGE_RAW = {
    'format': {'format_name': 'png_pipe'},
    'streams': [{'codec_type': 'image', 'codec_name': 'png', 'width': 640, 'height': 480}],
}
VIDEO_RAW = {
    'format': {'format_name': 'mov,mp4', 'duration': '3.0'},
    'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 1280, 'height': 720, 'r_frame_rate': '30/1'}],
}
CORRUPT_RAW = {'streams': [{'codec_type': 'video', 'width': -5, 'height': 10}]}

IMAGE_POLICY = ImageSafetyPolicy(
    revision='sp-1',
    confidence_threshold=0.6,
    transform_categories=['gore', 'weapon'],
    require_transform_before_use=False,
)
TRANSFORM_POLICY = TransformPolicy(revision='tp-1', actions={'gore': 'blur', 'weapon': 'recolor'})
REGIONS = (TransformRegion(category='gore', confidence=0.9, mask_ref='mask-1'),)
OUTPUT_PROFILE = {'format': 'png'}
TRANSFORM_REQUIRED = ImageSafetyAssessment(
    outcome=SafetyOutcome.TRANSFORM_REQUIRED,
    original_usable=True,
    reason='categories_require_transform',
    categories=('gore',),
    confidence=0.9,
    policy_revision='sp-1',
)
POST_ASSESSMENTS = {
    SafetyOutcome.SAFE: ImageSafetyAssessment(
        outcome=SafetyOutcome.SAFE, original_usable=True, reason='post_check_clean'
    ),
    SafetyOutcome.UNCERTAIN: ImageSafetyAssessment(
        outcome=SafetyOutcome.UNCERTAIN,
        original_usable=True,
        reason='confidence_below_threshold',
        warnings=('confidence_below_threshold',),
    ),
}


def _spec(revision: str, step: NormalizeStep) -> NormalizeSpec:
    return NormalizeSpec(operations=(step,), tool_version='ffmpeg-fake-1', spec_revision=revision)


RESIZE_SPEC = _spec('spec-1', NormalizeStep('resize', {'width': 1080, 'height': 1920}))
OTHER_SPEC = _spec('spec-2', NormalizeStep('resize', {'width': 720, 'height': 1280}))
CLIP_SPEC = _spec('spec-clip', NormalizeStep('transcode', {'codec': 'h264'}))
BLUR_SPEC = _spec('spec-blur', NormalizeStep('blur', {'radius': 5}))

class FakeProbe:
    def __init__(self, raw: dict | None = None, raises: Exception | None = None) -> None:
        self.raw = {} if raw is None else raw
        self.raises = raises
        self.calls: list[ArtifactRef] = []

    def probe(self, artifact_ref: ArtifactRef) -> dict:
        self.calls.append(artifact_ref)
        if self.raises is not None:
            raise self.raises
        return self.raw


class FakeTool:
    def __init__(self, outcome: ToolOutcome | None = None, raises: Exception | None = None) -> None:
        self.outcome = outcome
        self.raises = raises
        self.calls: list = []

    def run(self, plan):
        self.calls.append(plan)
        if self.raises is not None:
            raise self.raises
        if self.outcome is not None:
            return self.outcome
        return ToolOutcome(Disposition.SUCCEEDED, output_ref=plan.output_ref, output_sha256=SHA_B)


class FakeTransform:
    def __init__(
        self,
        post_outcome: SafetyOutcome = SafetyOutcome.SAFE,
        raises: Exception | None = None,
        fail_refs: frozenset = frozenset(),
        replace_original: bool = False,
    ) -> None:
        self.post_outcome = post_outcome
        self.raises = raises
        self.fail_refs = fail_refs
        self.replace_original = replace_original
        self.calls: list = []

    def transform(self, request):
        self.calls.append(request)
        if self.raises is not None or request.source_ref.ref in self.fail_refs:
            raise self.raises or RuntimeError('transform crashed')
        source = request.source_ref
        processed = source if self.replace_original else ArtifactRef(f'proc-{source.ref}', SHA_C)
        return TransformOutput(
            processed_ref=processed,
            evidence_ref='evidence-1',
            processor_version='fake-1.0',
            post_assessment=POST_ASSESSMENTS[self.post_outcome],
        )


class FakeAudioBed:
    def __init__(
        self,
        outcome: AudioBedOutcome | None = None,
        raises: Exception | None = None,
        lufs: float = -16.0,
        source_ref: str | None = None,
        rendition_refs: tuple | None = None,
    ) -> None:
        self.outcome = outcome
        self.raises = raises
        self.lufs = lufs
        self.source_ref = source_ref
        self.rendition_refs = rendition_refs
        self.calls: list = []

    def prepare(self, request):
        self.calls.append(request)
        if self.raises is not None:
            raise self.raises
        if self.outcome is not None:
            return self.outcome
        refs = self.rendition_refs or tuple(f'bed-{i}' for i in range(len(request.cues)))
        renditions = tuple(
            PreparedRendition(
                cue_index=i,
                rendition_ref=ref,
                source_artifact_ref=self.source_ref or request.cues[i].artifact_ref,
                mood=request.cues[i].mood,
            )
            for i, ref in enumerate(refs)
        )
        return AudioBedOutcome(
            status=Disposition.SUCCEEDED,
            renditions=renditions,
            output_hashes=tuple(SHA_D for _ in renditions),
            loudness_report=LoudnessReport(integrated_lufs=self.lufs, true_peak_dbtp=-2.0),
            provenance={'tool': 'fake-bed'},
            risk_metadata={'risk': 'low'},
        )


class CrashOnCommitUow(InMemoryUnitOfWork):
    def __init__(self, fail_commits: int = 0) -> None:
        super().__init__()
        self.fail_commits = fail_commits

    def commit(self) -> None:
        if self.fail_commits > 0:
            self.fail_commits -= 1
            raise RuntimeError('simulated crash before receipt')
        super().commit()


def ctx(name: str) -> EventContext:
    return EventContext(
        workspace_id='ws-1',
        correlation_id='corr-1',
        actor='worker-e',
        occurred_at='2026-10-19T00:00:00+00:00',
        recovery_epoch='epoch-1',
        event_id=f'evt-{name}',
        message_id=f'msg-{name}',
    )


def make_pipeline(uow=None, **ports):
    uow = InMemoryUnitOfWork() if uow is None else uow
    return uow, MediaPipeline(uow, **ports)


def events(uow) -> list:
    return [record.event_type for record in uow.outbox.records()]


def stored(uow, kind: str, key: str):
    item = uow.outputs.latest(kind, key)
    return None if item is None else item.record


def raising_detector():
    raise RuntimeError('detector crashed')


def assess(pipeline, key, detector, *, ref=IMAGE_REF, kind='image', policy=IMAGE_POLICY):
    return pipeline.assess_image_safety(key, ctx(key), ref, kind, detector, policy)


def transform(pipeline, key, *, kind='image', hook=False, assessment=TRANSFORM_REQUIRED, verified_outputs=None):
    return pipeline.transform_sensitive_image(
        key,
        ctx(key),
        media_kind=kind,
        user_visual_hook=hook,
        assessment=assessment,
        source_ref=IMAGE_REF,
        regions=REGIONS,
        policy=TRANSFORM_POLICY,
        output_profile=OUTPUT_PROFILE,
        verified_outputs=verified_outputs,
    )


def out_ref(spec=RESIZE_SPEC, ref=IMAGE_REF, kind='image') -> str:
    return plan_rendition(ref, spec, kind).output_ref


def verified(ref: str, sha: str = SHA_B, size: int = 2048) -> dict:
    return {ref: VerifiedOutput(sha, size)}


def normalize(pipeline, key, *, ref=IMAGE_REF, spec=RESIZE_SPEC, kind='image', verified_outputs=None):
    return pipeline.normalize_media(
        key, ctx(key), input_ref=ref, spec=spec, media_kind=kind, verified_outputs=verified_outputs
    )


def audio_request(**overrides) -> AudioBedRequest:
    fields = {
        'cues': (AudioCue(kind='music', start_ms=0, end_ms=5000, artifact_ref='music-1', mood='calm'),),
        'voice_artifact_ref': 'voice-1',
        'preset_audio_policy_revision': 'audio-pol-1',
        'loudness_constraints': LoudnessConstraints(min_lufs=-20, max_lufs=-12, max_true_peak_dbtp=-1.0),
        'mix_constraints': {'duck_db': -12},
        'fallback_allowed': False,
    }
    fields.update(overrides)
    return AudioBedRequest(**fields)


def prepare_bed(pipeline, key, request=None, verified_outputs=None):
    request = audio_request() if request is None else request
    return pipeline.prepare_audio_bed(key, ctx(key), request, verified_outputs=verified_outputs)

def test_probe_media_records_report_and_receipt_without_event():
    probe = FakeProbe(IMAGE_RAW)
    uow, pipeline = make_pipeline(probe=probe)
    result = pipeline.probe_media(
        'op-p-1', IMAGE_REF, declared_extension='png', declared_mime='image/png', observed_size=2048
    )
    assert result.replayed is False
    assert result.receipt.operation == 'ProbeMedia'
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert result.record.media_type is MediaType.IMAGE
    assert result.record.readability is Readability.READABLE
    assert stored(uow, 'probe_report', 'op-p-1') is result.record
    assert stored(uow, 'receipt', 'op-p-1') == result.receipt
    assert events(uow) == []
    assert probe.calls == [IMAGE_REF]


def test_probe_media_does_not_trust_declared_extension_or_mime():
    probe = FakeProbe(VIDEO_RAW)
    uow, pipeline = make_pipeline(probe=probe)
    result = pipeline.probe_media(
        'op-p-2', IMAGE_REF, declared_extension='png', declared_mime='image/png', observed_size=2048
    )
    assert result.record.media_type is MediaType.VIDEO
    assert 'declared_type_mismatch' in result.receipt.warnings


def test_probe_media_unreadable_and_corrupt_are_recorded_with_warnings():
    probe1 = FakeProbe({})
    uow1, pipeline1 = make_pipeline(probe=probe1)
    res1 = pipeline1.probe_media('op-p-3', IMAGE_REF, observed_size=0)
    assert res1.record.readability is Readability.UNREADABLE
    assert 'unreadable' in res1.receipt.warnings

    probe2 = FakeProbe(CORRUPT_RAW)
    uow2, pipeline2 = make_pipeline(probe=probe2)
    res2 = pipeline2.probe_media('op-p-4', IMAGE_REF, observed_size=10)
    assert res2.record.readability is Readability.CORRUPT
    assert res2.receipt.warnings == ('corruption:invalid_stream_field',)
    assert res2.receipt.disposition is Disposition.SUCCEEDED


def test_probe_media_port_crash_is_failed_without_output():
    probe = FakeProbe(raises=RuntimeError('boom'))
    uow, pipeline = make_pipeline(probe=probe)
    result = pipeline.probe_media('op-p-5', IMAGE_REF, observed_size=10)
    assert result.receipt.disposition is Disposition.FAILED
    assert result.receipt.error == 'RuntimeError'
    assert result.record is None
    assert stored(uow, 'probe_report', 'op-p-5') is None
    assert stored(uow, 'receipt', 'op-p-5') == result.receipt


def test_assess_safe_image_records_assessment_and_event():
    uow, pipeline = make_pipeline()
    result = assess(pipeline, 'op-a-1', lambda: ImageDetection('completed', (), 0.9))
    assert result.record.outcome is SafetyOutcome.SAFE
    assert result.receipt.outcome == 'SAFE'
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert stored(uow, 'image_safety_assessment', 'op-a-1') is result.record
    assert events(uow) == ['ImageSafetyAssessed']
    (rec,) = uow.outbox.records()
    assert rec.payload['assessment_ref'] == 'assessment:op-a-1'
    assert rec.payload['artifact_ref'] == 'img-1'
    assert rec.payload['content_sha256'] == SHA_A
    assert rec.payload['policy_revision'] == 'sp-1'


@pytest.mark.parametrize(
    'detector, expected',
    [
        (lambda: ImageDetection('completed', (), 0.3), SafetyOutcome.UNCERTAIN),
        (lambda: ImageDetection('failed'), SafetyOutcome.DETECTION_FAILED),
        (raising_detector, SafetyOutcome.DETECTION_FAILED),
    ],
)
def test_assess_uncertain_and_detector_failures_continue_with_warning(detector, expected):
    uow, pipeline = make_pipeline()
    result = assess(pipeline, 'op-a-2', detector)
    assert result.record.outcome is expected
    assert result.record.original_usable is True
    assert len(result.record.warnings) > 0
    assert result.receipt.warnings == result.record.warnings
    assert result.receipt.outcome == expected.value
    assert result.receipt.outcome != 'SAFE'
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert events(uow) == ['ImageSafetyAssessed']


def test_assess_unreadable_image_is_not_usable():
    uow, pipeline = make_pipeline()
    result = assess(pipeline, 'op-a-unread', lambda: ImageDetection('unreadable'))
    assert result.record.outcome is SafetyOutcome.UNREADABLE
    assert result.record.original_usable is False
    assert result.receipt.outcome == 'UNREADABLE'


def test_assess_transform_required_keeps_categories():
    uow, pipeline = make_pipeline()
    result = assess(pipeline, 'op-a-req', lambda: ImageDetection('completed', ('gore',), 0.9))
    assert result.record.outcome is SafetyOutcome.TRANSFORM_REQUIRED
    assert result.record.categories == ('gore',)


def test_assess_clip_is_rejected_without_writes():
    calls = []
    detector = lambda: calls.append(1)
    uow, pipeline = make_pipeline()
    with pytest.raises(ProcessingContractError) as exc:
        assess(pipeline, 'op-a-clip', detector, ref=CLIP_REF, kind='clip')
    assert exc.value.code == SAFETY_TRANSFORM_NOT_APPLICABLE
    assert calls == []
    assert stored(uow, 'receipt', 'op-a-clip') is None
    assert events(uow) == []


def test_assess_missing_policy_is_input_not_ready():
    uow, pipeline = make_pipeline()
    key = 'op-a-nopol'
    with pytest.raises(ImageSafetyError) as exc:
        assess(pipeline, key, lambda: ImageDetection('completed', (), 0.9), policy=None)
    assert exc.value.code == 'INPUT_NOT_READY'
    assert stored(uow, 'receipt', key) is None

def test_transform_verified_output_is_recorded_with_event():
    tool = FakeTransform()
    uow, pipeline = make_pipeline(transformer=tool)
    verified_map = {'proc-img-1': VerifiedOutput(SHA_C, 1000)}
    result = transform(pipeline, 'op-t-1', verified_outputs=verified_map)
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert result.receipt.outcome == 'SAFE'
    assert result.receipt.output_refs == ('proc-img-1',)
    assert result.receipt.output_hashes == (SHA_C,)
    assert result.record.processed_ref == ArtifactRef('proc-img-1', SHA_C)
    assert result.record.original_ref == IMAGE_REF
    assert len(tool.calls) == 1
    assert stored(uow, 'processed_media', 'op-t-1') is result.record
    (rec,) = uow.outbox.records()
    assert rec.event_type == 'MediaProcessingCompleted'
    assert rec.payload['output_artifact_refs'] == ['proc-img-1']
    assert rec.payload['output_hashes'] == [SHA_C]
    assert rec.payload['operation_receipt_ref'] == 'receipt:op-t-1'


def test_transform_post_assessment_uncertain_is_warning_not_safe():
    tool = FakeTransform(post_outcome=SafetyOutcome.UNCERTAIN)
    uow, pipeline = make_pipeline(transformer=tool)
    verified_map = {'proc-img-1': VerifiedOutput(SHA_C, 1000)}
    result = transform(pipeline, 'op-t-2', verified_outputs=verified_map)
    assert result.record.status == 'warning'
    assert result.record.outcome is SafetyOutcome.UNCERTAIN
    assert result.receipt.outcome == 'UNCERTAIN'
    assert result.receipt.warnings == ('post_assessment_uncertain',)
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert events(uow) == ['MediaProcessingCompleted']


def test_transform_port_crash_is_transform_failed_not_safe():
    tool = FakeTransform(raises=RuntimeError('boom'))
    uow, pipeline = make_pipeline(transformer=tool)
    result = transform(pipeline, 'op-t-3', verified_outputs=None)
    assert result.receipt.disposition is Disposition.FAILED
    assert result.receipt.outcome == 'TRANSFORM_FAILED'
    assert result.receipt.error == 'transform_raised'
    assert result.record.processed_ref is None
    assert result.record.outcome is SafetyOutcome.TRANSFORM_FAILED
    assert result.record.post_assessment.original_usable is True
    assert stored(uow, 'processed_media', 'op-t-3') is result.record
    assert events(uow) == []


def test_transform_processed_replacing_original_is_failed():
    tool = FakeTransform(replace_original=True)
    uow, pipeline = make_pipeline(transformer=tool)
    result = transform(pipeline, 'op-t-4', verified_outputs={'img-1': VerifiedOutput(SHA_A, 1000)})
    assert result.receipt.error == 'processed_replaces_original'
    assert result.record.processed_ref is None
    assert events(uow) == []


@pytest.mark.parametrize(
    'verified_outputs, error',
    [
        (None, 'output_not_verified'),
        ({'proc-img-1': VerifiedOutput(SHA_D, 10)}, 'output_hash_mismatch'),
    ],
)
def test_transform_unverified_output_is_failed_without_event(verified_outputs, error):
    tool = FakeTransform()
    uow, pipeline = make_pipeline(transformer=tool)
    key = 'op-t-unver'
    result = transform(pipeline, key, verified_outputs=verified_outputs)
    assert result.receipt.disposition is Disposition.FAILED
    assert result.receipt.error == error
    assert result.receipt.outcome == 'TRANSFORM_FAILED'
    assert result.record is None
    assert stored(uow, 'processed_media', key) is None
    assert events(uow) == []


def test_transform_clip_is_rejected_without_writes():
    tool = FakeTransform()
    uow, pipeline = make_pipeline(transformer=tool)
    key = 'op-t-clip'
    with pytest.raises(ProcessingContractError) as exc:
        transform(pipeline, key, kind='clip')
    assert exc.value.code == SAFETY_TRANSFORM_NOT_APPLICABLE
    assert tool.calls == []
    assert stored(uow, 'receipt', key) is None
    assert events(uow) == []


def test_transform_skipped_when_user_hook_already_blurred():
    tool = FakeTransform()
    uow, pipeline = make_pipeline(transformer=tool)
    key = 'op-t-hook'
    result = transform(pipeline, key, hook=True)
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert result.receipt.warnings == ('hook_already_blurred',)
    assert result.record is None
    assert tool.calls == []
    assert events(uow) == []


def test_transform_requires_transform_required_assessment():
    tool = FakeTransform()
    uow, pipeline = make_pipeline(transformer=tool)
    key = 'op-t-notreq'
    with pytest.raises(ImageSafetyError) as exc:
        transform(pipeline, key, assessment=POST_ASSESSMENTS[SafetyOutcome.SAFE])
    assert exc.value.reason == 'assessment_not_transform_required'
    assert tool.calls == []
    assert stored(uow, 'receipt', key) is None

def test_normalize_image_records_new_rendition_and_event():
    tool = FakeTool()
    uow, pipeline = make_pipeline(tool=tool)
    ref = out_ref()
    result = normalize(pipeline, 'op-n-1', verified_outputs=verified(ref))
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert result.receipt.output_refs == (ref,)
    assert result.receipt.output_hashes == (SHA_B,)
    assert result.record.output_ref == ref
    assert result.record.output_ref != IMAGE_REF.ref
    assert result.record.input_ref == IMAGE_REF
    assert result.record.lineage_refs == ('img-1',)
    assert tool.calls[0].input_ref == IMAGE_REF
    assert tool.calls[0].output_ref == ref
    assert stored(uow, 'processed_media', 'op-n-1') is result.record
    (rec,) = uow.outbox.records()
    assert rec.event_type == 'MediaProcessingCompleted'
    assert rec.payload['output_artifact_refs'] == [ref]
    assert rec.payload['output_hashes'] == [SHA_B]
    assert rec.payload['operation_receipt_ref'] == 'receipt:op-n-1'


def test_normalize_clip_is_allowed():
    tool = FakeTool()
    uow, pipeline = make_pipeline(tool=tool)
    ref = out_ref(CLIP_SPEC, CLIP_REF, 'clip')
    result = normalize(
        pipeline, 'op-n-clip', ref=CLIP_REF, spec=CLIP_SPEC, kind='clip', verified_outputs=verified(ref)
    )
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert events(uow) == ['MediaProcessingCompleted']


def test_normalize_clip_with_blur_is_rejected_without_tool_call():
    tool = FakeTool()
    uow, pipeline = make_pipeline(tool=tool)
    key = 'op-n-clipblur'
    with pytest.raises(ProcessingContractError) as exc:
        normalize(pipeline, key, ref=CLIP_REF, spec=BLUR_SPEC, kind='clip')
    assert exc.value.code == SAFETY_TRANSFORM_NOT_APPLICABLE
    assert tool.calls == []
    assert stored(uow, 'receipt', key) is None


def test_normalize_crash_in_tool_is_failed_and_replay_does_not_rerun():
    tool = FakeTool(raises=RuntimeError('ffmpeg crashed'))
    uow, pipeline = make_pipeline(tool=tool)
    first = normalize(pipeline, 'op-n-3')
    assert first.receipt.disposition is Disposition.FAILED
    assert first.receipt.error == 'RuntimeError'
    assert first.record is None
    assert stored(uow, 'processed_media', 'op-n-3') is None
    assert events(uow) == []
    replay = normalize(pipeline, 'op-n-3')
    assert replay.replayed is True
    assert replay.receipt == first.receipt
    assert len(tool.calls) == 1
    tool.raises = None
    retry = normalize(pipeline, 'op-n-3b', verified_outputs=verified(out_ref()))
    assert retry.receipt.disposition is Disposition.SUCCEEDED
    assert len(tool.calls) == 2


def test_normalize_tool_failed_status_keeps_error_text():
    tool = FakeTool(outcome=ToolOutcome(Disposition.FAILED, error='ffmpeg exit 1'))
    uow, pipeline = make_pipeline(tool=tool)
    result = normalize(pipeline, 'op-n-4')
    assert result.receipt.disposition is Disposition.FAILED
    assert result.receipt.error == 'ffmpeg exit 1'
    assert events(uow) == []


def test_normalize_outcome_unknown_from_tool_blocks_direct_retry():
    tool = FakeTool(outcome=ToolOutcome(Disposition.OUTCOME_UNKNOWN))
    uow, pipeline = make_pipeline(tool=tool)
    first = normalize(pipeline, 'op-n-5')
    assert first.receipt.disposition is Disposition.OUTCOME_UNKNOWN
    assert stored(uow, 'processed_media', 'op-n-5') is None
    assert events(uow) == []
    replay = normalize(pipeline, 'op-n-5')
    assert replay.replayed is True
    assert len(tool.calls) == 1
    with pytest.raises(RetryNotAllowedError):
        normalize(pipeline, 'op-n-5b')
    assert len(tool.calls) == 1


def test_normalize_crash_after_side_effect_before_receipt_is_outcome_unknown():
    uow = CrashOnCommitUow(fail_commits=1)
    tool = FakeTool()
    pipeline = MediaPipeline(uow, tool=tool)
    ref = out_ref()
    result = normalize(pipeline, 'op-n-6', verified_outputs=verified(ref))
    assert result.receipt.disposition is Disposition.OUTCOME_UNKNOWN
    assert result.receipt.error == 'receipt_commit_failed'
    assert stored(uow, 'processed_media', 'op-n-6') is None
    assert events(uow) == []
    assert len(tool.calls) == 1
    assert stored(uow, 'receipt', 'op-n-6') == result.receipt
    with pytest.raises(RetryNotAllowedError):
        normalize(pipeline, 'op-n-6b', verified_outputs=verified(ref))
    assert len(tool.calls) == 1


@pytest.mark.parametrize(
    'verified_outputs, error',
    [
        (None, 'output_not_verified'),
        (verified(out_ref(), sha=SHA_D), 'output_hash_mismatch'),
    ],
)
def test_normalize_partial_or_hash_mismatch_is_not_ready(verified_outputs, error):
    tool = FakeTool()
    uow, pipeline = make_pipeline(tool=tool)
    result = normalize(pipeline, 'op-n-7', verified_outputs=verified_outputs)
    assert result.receipt.disposition is Disposition.FAILED
    assert result.receipt.error == error
    assert result.record is None
    assert stored(uow, 'processed_media', 'op-n-7') is None
    assert events(uow) == []
    assert len(tool.calls) == 1


@pytest.mark.parametrize('raw', [CORRUPT_RAW, {}])
def test_normalize_corrupt_or_unreadable_output_is_not_ready(raw):
    ref = out_ref()
    probe = FakeProbe(raw)
    tool = FakeTool()
    uow, pipeline = make_pipeline(tool=tool, probe=probe)
    result = normalize(pipeline, 'op-n-8', verified_outputs=verified(ref))
    assert result.receipt.error == 'output_not_readable'
    assert result.receipt.disposition is Disposition.FAILED
    assert events(uow) == []
    assert stored(uow, 'processed_media', 'op-n-8') is None
    assert probe.calls == [ArtifactRef(ref, SHA_B)]


def test_normalize_readable_output_probe_passes():
    ref = out_ref()
    probe = FakeProbe(IMAGE_RAW)
    tool = FakeTool()
    uow, pipeline = make_pipeline(tool=tool, probe=probe)
    result = normalize(pipeline, 'op-n-9', verified_outputs=verified(ref))
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert events(uow) == ['MediaProcessingCompleted']


def test_normalize_output_probe_crash_is_not_ready():
    ref = out_ref()
    probe = FakeProbe(raises=RuntimeError('probe down'))
    tool = FakeTool()
    uow, pipeline = make_pipeline(tool=tool, probe=probe)
    result = normalize(pipeline, 'op-n-10', verified_outputs=verified(ref))
    assert result.receipt.error == 'output_not_readable'
    assert events(uow) == []


def test_normalize_tool_returning_original_ref_never_replaces_original():
    tool = FakeTool(outcome=ToolOutcome(Disposition.SUCCEEDED, output_ref=IMAGE_REF.ref, output_sha256=SHA_B))
    uow, pipeline = make_pipeline(tool=tool)
    key = 'op-n-repl'
    result = normalize(pipeline, key, verified_outputs={'img-1': VerifiedOutput(SHA_B, 10)})
    assert result.receipt.disposition is Disposition.FAILED
    assert result.receipt.error == 'output_ref_mismatch'
    assert stored(uow, 'processed_media', key) is None
    assert events(uow) == []
    assert tool.calls[0].input_ref == IMAGE_REF
    assert tool.calls[0].output_ref != IMAGE_REF.ref


def test_normalize_same_key_same_request_replays_and_different_request_conflicts():
    tool = FakeTool()
    uow, pipeline = make_pipeline(tool=tool)
    ref = out_ref()
    first = normalize(pipeline, 'op-n-11', verified_outputs=verified(ref))
    second = normalize(pipeline, 'op-n-11', verified_outputs=verified(ref))
    assert second.replayed is True
    assert second.receipt == first.receipt
    assert second.record is first.record
    assert len(tool.calls) == 1
    assert len(uow.outputs.revisions('receipt', 'op-n-11')) == 1
    assert events(uow) == ['MediaProcessingCompleted']
    with pytest.raises(IdempotencyConflictError) as exc:
        normalize(pipeline, 'op-n-11', spec=OTHER_SPEC)
    assert exc.value.code == 'IDEMPOTENCY_CONFLICT'
    assert len(tool.calls) == 1

def test_audio_bed_verified_output_is_recorded_with_event():
    port = FakeAudioBed()
    uow, pipeline = make_pipeline(audio_bed=port)
    result = prepare_bed(pipeline, 'op-b-1', verified_outputs=verified('bed-0', SHA_D, 4096))
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert result.receipt.operation == 'PrepareAudioBed'
    assert result.receipt.output_refs == ('bed-0',)
    assert result.receipt.output_hashes == (SHA_D,)
    assert result.record.renditions[0].rendition_ref == 'bed-0'
    assert result.record.cue_timings[0].end_ms == 5000
    assert stored(uow, 'audio_bed_result', 'op-b-1') is result.record
    assert len(port.calls) == 1
    (rec,) = uow.outbox.records()
    assert rec.event_type == 'MediaProcessingCompleted'
    assert rec.payload['output_artifact_refs'] == ['bed-0']
    assert rec.payload['output_hashes'] == [SHA_D]


def test_audio_bed_missing_loudness_constraints_is_input_not_ready():
    port = FakeAudioBed()
    uow, pipeline = make_pipeline(audio_bed=port)
    request = audio_request(loudness_constraints=None)
    key = 'op-b-noloud'
    with pytest.raises(AudioBedRejected) as exc:
        prepare_bed(pipeline, key, request=request)
    assert exc.value.code == 'INPUT_NOT_READY'
    assert port.calls == []
    assert stored(uow, 'receipt', key) is None
    assert events(uow) == []


def test_audio_bed_loudness_out_of_target_is_failed():
    port = FakeAudioBed(lufs=-30.0)
    uow, pipeline = make_pipeline(audio_bed=port)
    key = 'op-b-badlufs'
    result = prepare_bed(pipeline, key, verified_outputs=verified('bed-0', SHA_D, 4096))
    assert result.receipt.disposition is Disposition.FAILED
    assert result.receipt.error == 'loudness_out_of_target:integrated_lufs'
    assert result.record is None
    assert stored(uow, 'audio_bed_result', key) is None
    assert events(uow) == []


def test_audio_bed_substitution_not_allowed_is_failed():
    port = FakeAudioBed(source_ref='music-x')
    uow, pipeline = make_pipeline(audio_bed=port)
    key = 'op-b-sub'
    result = prepare_bed(pipeline, key, verified_outputs=verified('bed-0', SHA_D, 4096))
    assert result.receipt.error == 'substitution_not_allowed:renditions'
    assert events(uow) == []


def test_audio_bed_rendition_replacing_original_is_failed():
    port = FakeAudioBed(rendition_refs=('music-1',))
    uow, pipeline = make_pipeline(audio_bed=port)
    key = 'op-b-repl'
    result = prepare_bed(pipeline, key, verified_outputs=verified('music-1', SHA_D, 4096))
    assert result.receipt.error == 'output_replaces_original'
    assert events(uow) == []


def test_audio_bed_unverified_output_is_failed():
    port1 = FakeAudioBed()
    uow1, pipeline1 = make_pipeline(audio_bed=port1)
    res1 = prepare_bed(pipeline1, 'op-b-unv1', verified_outputs=None)
    assert res1.receipt.error == 'output_not_verified'
    assert events(uow1) == []

    port2 = FakeAudioBed()
    uow2, pipeline2 = make_pipeline(audio_bed=port2)
    res2 = prepare_bed(pipeline2, 'op-b-unv2', verified_outputs=verified('bed-0', SHA_A))
    assert res2.receipt.error == 'output_hash_mismatch'
    assert events(uow2) == []


def test_audio_bed_crash_and_outcome_unknown_paths():
    port_a = FakeAudioBed(raises=RuntimeError('mixer crashed'))
    uow_a, pipe_a = make_pipeline(audio_bed=port_a)
    res_a = prepare_bed(pipe_a, 'op-b-cr1')
    assert res_a.receipt.disposition is Disposition.FAILED
    assert res_a.receipt.error == 'RuntimeError'

    port_b = FakeAudioBed(outcome=AudioBedOutcome(status=Disposition.OUTCOME_UNKNOWN))
    uow_b, pipe_b = make_pipeline(audio_bed=port_b)
    res_b = prepare_bed(pipe_b, 'op-b-cr2')
    assert res_b.receipt.disposition is Disposition.OUTCOME_UNKNOWN
    with pytest.raises(RetryNotAllowedError):
        prepare_bed(pipe_b, 'op-b-cr2-retry')
    assert len(port_b.calls) == 1

    uow_c = CrashOnCommitUow(fail_commits=1)
    port_c = FakeAudioBed()
    pipe_c = MediaPipeline(uow_c, audio_bed=port_c)
    key_c = 'op-b-cr3'
    res_c = prepare_bed(pipe_c, key_c, verified_outputs=verified('bed-0', SHA_D, 4096))
    assert res_c.receipt.disposition is Disposition.OUTCOME_UNKNOWN
    assert res_c.receipt.error == 'receipt_commit_failed'
    assert stored(uow_c, 'audio_bed_result', key_c) is None
    assert events(uow_c) == []


def test_image_batch_continues_through_uncertain_failed_and_unreadable_images():
    transformer = FakeTransform(fail_refs=frozenset({'img-5'}))
    uow, pipeline = make_pipeline(transformer=transformer)
    gore = lambda: ImageDetection('completed', ('gore',), 0.9)
    items = [
        ImageBatchItem('i1', ArtifactRef('img-1', SHA_A), lambda: ImageDetection('completed', (), 0.9)),
        ImageBatchItem('i2', ArtifactRef('img-2', SHA_A), lambda: ImageDetection('completed', (), 0.3)),
        ImageBatchItem('i3', ArtifactRef('img-3', SHA_A), raising_detector),
        ImageBatchItem('i4', ArtifactRef('img-4', SHA_A), lambda: ImageDetection('unreadable')),
        ImageBatchItem('i5', ArtifactRef('img-5', SHA_A), gore, regions=REGIONS),
        ImageBatchItem('i6', ArtifactRef('img-6', SHA_A), gore, regions=REGIONS),
    ]
    results = pipeline.process_image_batch(
        'b1',
        items,
        safety_policy=IMAGE_POLICY,
        transform_policy=TRANSFORM_POLICY,
        output_profile=OUTPUT_PROFILE,
        context_for=lambda key: ctx(key.replace(':', '-')),
        verified_outputs={'proc-img-6': VerifiedOutput(SHA_C, 10)},
    )
    assert len(results) == 6
    assert [r.item_id for r in results] == ['i1', 'i2', 'i3', 'i4', 'i5', 'i6']
    assert [r.outcome for r in results] == [
        SafetyOutcome.SAFE,
        SafetyOutcome.UNCERTAIN,
        SafetyOutcome.DETECTION_FAILED,
        SafetyOutcome.UNREADABLE,
        SafetyOutcome.TRANSFORM_FAILED,
        SafetyOutcome.SAFE,
    ]
    assert [r.usable_ref for r in results] == [
        ArtifactRef('img-1', SHA_A),
        ArtifactRef('img-2', SHA_A),
        ArtifactRef('img-3', SHA_A),
        None,
        ArtifactRef('img-5', SHA_A),
        ArtifactRef('proc-img-6', SHA_C),
    ]
    assert results[5].processed_ref == ArtifactRef('proc-img-6', SHA_C)
    assert results[4].processed_ref is None
    assert results[1].warnings == ('confidence_below_threshold',)
    assert results[2].warnings == ('detector_raised',)
    assert 'transform_raised' in results[4].warnings
    for idx, item in enumerate(items):
        assert results[idx].original_ref == item.artifact_ref
    assert len(transformer.calls) == 2
    assert events(uow).count('ImageSafetyAssessed') == 6
    assert events(uow).count('MediaProcessingCompleted') == 1
    for r in results:
        assert len(r.receipt_refs) >= 1


def test_module_has_no_adapter_process_or_clock_imports():
    text = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(text)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    forbidden = (
        'voice.adapters',
        'subprocess',
        'socket',
        'os',
        'shutil',
        'time',
        'datetime',
        'random',
        'uuid',
        'pathlib',
        'temporalio',
        'src',
    )
    for name in names:
        for f in forbidden:
            assert name != f and not name.startswith(f + '.'), f'forbidden import: {name}'