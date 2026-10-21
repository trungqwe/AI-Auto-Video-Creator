"""ADAPT-E-MEDIA integration tests for real FFmpeg media tool and vision LLM image safety detector.

subprocess.run and vision route J are simulated for unit-level integration testing.
Actual FFmpeg and sensitive image assets belong to CP7-E-04 and CP7-E-03.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

from voice.adapters import real_ffmpeg_media_tool as tool_module
from voice.adapters import real_llm_image_safety as safety_module
from voice.adapters.real_ffmpeg_media_tool import (
    FfmpegPinError,
    FfmpegToolError,
    RealFfmpegMediaTool,
    format_mask_ref,
    parse_mask_ref,
)
from voice.adapters.real_llm_image_safety import (
    ImageSafetyDetectionError,
    LlmImageSafetyDetector,
    parse_vision_output,
)
from voice.domain.image_safety import (
    DetectionStatus,
    ImageSafetyAssessment,
    ImageSafetyPolicy,
    SafetyOutcome,
    assess_image_safety,
    original_usable_for,
)
from voice.domain.image_transform import (
    TransformPolicy,
    TransformRegion,
    TransformRequest,
    TransformPort,
    transform_sensitive_image,
)
from voice.domain.normalize import (
    NormalizeSpec,
    NormalizeStep,
    plan_rendition,
    verify_tool_outcome,
)
from voice.domain.processing import ArtifactRef, Disposition
from voice.ports.media_tool import MediaToolPort
from voice.ports.probe import ProbePort

ARCHIVE = '2025-03-13-git-958c46800e-essentials_build'
FFMPEG_BYTES = b'fake-ffmpeg-binary'
IMAGE_BYTES = b'fake-image-bytes'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeRun:
    def __init__(
        self,
        *,
        version_line: str | None = None,
        probe_json: dict | None = None,
        returncode: int = 0,
        raise_timeout: bool = False,
        output_bytes: bytes = b'rendered',
    ) -> None:
        self.calls: list[tuple[list[str], dict]] = []
        self.version_line = version_line
        self.probe_json = probe_json
        self.returncode = returncode
        self.raise_timeout = raise_timeout
        self.output_bytes = output_bytes

    def __call__(self, args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs))
        stem = Path(args[0]).stem
        if stem == 'ffprobe' and '-version' in args:
            stdout = (self.version_line or f'ffprobe version {ARCHIVE}-www.gyan.dev') + '\nbuilt with gcc\n'
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr='')
        if stem == 'ffprobe':
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps(self.probe_json or {}), stderr='')

        if self.raise_timeout:
            raise subprocess.TimeoutExpired(args, kwargs['timeout'])

        out_path = Path(args[-1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(self.output_bytes)
        return subprocess.CompletedProcess(args, self.returncode, stdout='', stderr='secret-stderr')


def build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: str = 'PINNED',
    pin_sha: str | None = None,
    fake: FakeRun | None = None,
    reassess=None,
):
    if fake is None:
        fake = FakeRun()
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = bin_dir / 'ffmpeg.exe'
    ffmpeg.write_bytes(FFMPEG_BYTES)
    ffprobe = bin_dir / 'ffprobe.exe'
    ffprobe.write_bytes(b'fake-ffprobe-binary')

    lock = tmp_path / 'runtime.lock.json'
    lock_data = {
        'pins': {
            'ffmpeg': {
                'sha256': pin_sha or sha(FFMPEG_BYTES),
                'status': status,
                'archive_name': ARCHIVE,
                'measured_artifact': 'ffmpeg.exe',
            }
        }
    }
    lock.write_text(json.dumps(lock_data, ensure_ascii=False), encoding='utf-8')

    in_path = tmp_path / 'in.png'
    in_path.write_bytes(IMAGE_BYTES)

    monkeypatch.setattr(tool_module.subprocess, 'run', fake)
    tool = RealFfmpegMediaTool(
        ffmpeg,
        lock,
        resolve_input=lambda ref: tmp_path / 'in.png',
        resolve_output=lambda ref, ext: tmp_path / (ref.replace(':', '_') + '.' + ext),
        timeout_seconds=30.0,
        reassess=reassess,
    )
    paths = {'ffmpeg': ffmpeg, 'ffprobe': ffprobe, 'lock': lock, 'in': in_path}
    return tool, fake, paths


def make_plan(output_ref: str = 'rendition:out-1', steps: tuple[NormalizeStep, ...] | None = None):
    return plan_rendition(
        ArtifactRef('src-1', sha(IMAGE_BYTES)),
        NormalizeSpec(
            operations=steps or (NormalizeStep('resize', {'width': 1080, 'height': 1920}),),
            tool_version='ffmpeg-test',
            spec_revision='spec-1',
        ),
        'image',
        output_ref=output_ref,
    )


def test_pin_match_runs_absolute_argv_without_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch)
    plan = make_plan()
    outcome = tool.run(plan)

    assert outcome.status is Disposition.SUCCEEDED
    assert outcome.output_sha256 == sha(b'rendered')
    verify_tool_outcome(plan, outcome)

    assert fake.calls[0][0] == [str(paths['ffprobe']), '-version']

    ffmpeg_call = fake.calls[1]
    args = ffmpeg_call[0]
    assert args[0] == str(paths['ffmpeg'])
    assert Path(args[0]).is_absolute()
    assert '-n' in args
    assert args[-1] != str(paths['in'])
    i_idx = args.index('-i')
    assert args[i_idx + 1] == str(paths['in'])

    for c_args, c_kwargs in fake.calls:
        assert isinstance(c_args, list)
        assert c_kwargs.get('shell') is False
        assert c_kwargs['timeout'] == 30.0

    assert paths['in'].read_bytes() == IMAGE_BYTES


def test_pin_sha_mismatch_refused_before_any_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch, pin_sha='0' * 64)
    outcome = tool.run(make_plan())
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'ffmpeg_sha256_mismatch'
    assert fake.calls == []


def test_pin_status_blocked_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch, status='BLOCKED')
    outcome = tool.run(make_plan())
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'pin_not_pinned'
    assert fake.calls == []


def test_ffprobe_build_string_mismatch_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake = FakeRun(version_line='ffprobe version 2024-01-01-other')
    tool, fake, paths = build(tmp_path, monkeypatch, fake=fake)
    outcome = tool.run(make_plan())
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'ffprobe_build_mismatch'
    assert len(fake.calls) > 0
    assert all(Path(call[0][0]).stem == 'ffprobe' for call in fake.calls)


def test_missing_lock_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch)
    paths['lock'].unlink()
    outcome = tool.run(make_plan())
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'pin_unreadable'


def test_relative_or_path_ffmpeg_rejected(tmp_path: Path):
    lock = tmp_path / 'lock.json'
    with pytest.raises(ValueError):
        RealFfmpegMediaTool('ffmpeg', lock, lambda r: tmp_path, lambda r, e: tmp_path)
    with pytest.raises(ValueError):
        RealFfmpegMediaTool('ffmpeg.exe', lock, lambda r: tmp_path, lambda r, e: tmp_path)


def test_existing_output_never_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch)
    plan = make_plan(output_ref='rendition:pre-existing')
    existing = tmp_path / 'rendition_pre-existing.png'
    existing.write_bytes(b'keep')
    outcome = tool.run(plan)
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'output_exists'
    assert existing.read_bytes() == b'keep'
    assert not any(Path(call[0][0]).stem == 'ffmpeg' for call in fake.calls)


def test_output_equal_to_input_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake = FakeRun()
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = bin_dir / 'ffmpeg.exe'
    ffmpeg.write_bytes(FFMPEG_BYTES)
    ffprobe = bin_dir / 'ffprobe.exe'
    ffprobe.write_bytes(b'fake-ffprobe-binary')
    lock = tmp_path / 'lock.json'
    lock.write_text(
        json.dumps({'pins': {'ffmpeg': {'sha256': sha(FFMPEG_BYTES), 'status': 'PINNED', 'archive_name': ARCHIVE}}}, ensure_ascii=False),
        encoding='utf-8',
    )
    in_path = tmp_path / 'in.png'
    in_path.write_bytes(IMAGE_BYTES)
    monkeypatch.setattr(tool_module.subprocess, 'run', fake)
    tool = RealFfmpegMediaTool(
        ffmpeg,
        lock,
        resolve_input=lambda r: in_path,
        resolve_output=lambda r, e: in_path,
    )
    outcome = tool.run(make_plan())
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'output_is_input'
    assert in_path.read_bytes() == IMAGE_BYTES


def test_input_sha_mismatch_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch)
    paths['in'].write_bytes(b'other')
    outcome = tool.run(make_plan())
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'input_sha256_mismatch'


def test_timeout_gives_outcome_unknown_and_discards_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake = FakeRun(raise_timeout=True)
    tool, fake, paths = build(tmp_path, monkeypatch, fake=fake)
    outcome = tool.run(make_plan())
    assert outcome.status is Disposition.OUTCOME_UNKNOWN
    assert outcome.error == 'ffmpeg_timeout'
    assert outcome.output_ref is None
    assert outcome.output_sha256 is None


def test_nonzero_exit_fails_and_discards_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake = FakeRun(returncode=1)
    tool, fake, paths = build(tmp_path, monkeypatch, fake=fake)
    plan = make_plan(output_ref='rendition:fail-1')
    outcome = tool.run(plan)
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'ffmpeg_exit_1'
    assert not (tmp_path / 'rendition_fail-1.png').exists()
    assert 'secret-stderr' not in (outcome.error or '')


def test_plan_operations_build_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch)
    steps = (
        NormalizeStep('crop', {'x': 0, 'y': 0, 'width': 100, 'height': 100}),
        NormalizeStep('resize', {'width': 1080, 'height': 1920}),
        NormalizeStep('pad', {'width': 1080, 'height': 1920, 'color': '#000000'}),
        NormalizeStep('transcode', {'codec': 'h264', 'container': 'mp4'}),
        NormalizeStep('audio_normalize', {'preset': 'p'}),
    )
    plan = plan_rendition(
        ArtifactRef('src-1', sha(IMAGE_BYTES)),
        NormalizeSpec(operations=steps, tool_version='ffmpeg-test', spec_revision='spec-1'),
        'image',
    )
    outcome = tool.run(plan)
    assert outcome.status is Disposition.SUCCEEDED
    ffmpeg_args = fake.calls[1][0]
    vf_idx = ffmpeg_args.index('-vf')
    assert ffmpeg_args[vf_idx + 1] == 'crop=100:100:0:0,scale=1080:1920,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:0x000000'
    cv_idx = ffmpeg_args.index('-c:v')
    assert ffmpeg_args[cv_idx + 1] == 'libx264'
    af_idx = ffmpeg_args.index('-af')
    assert ffmpeg_args[af_idx + 1] == 'loudnorm=I=-16:TP=-1.5:LRA=11'
    assert ffmpeg_args[-1].endswith('.mp4')


def test_unsupported_operation_and_codec_fail_without_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch)
    steps = (NormalizeStep('transcode', {'codec': 'vp9'}),)
    plan = plan_rendition(
        ArtifactRef('src-1', sha(IMAGE_BYTES)),
        NormalizeSpec(operations=steps, tool_version='ffmpeg-test', spec_revision='spec-1'),
        'image',
    )
    outcome = tool.run(plan)
    assert outcome.status is Disposition.FAILED
    assert outcome.error == 'unsupported_codec'
    assert not any(Path(call[0][0]).stem == 'ffmpeg' for call in fake.calls)


def test_ports_are_structurally_satisfied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch)
    assert isinstance(tool, MediaToolPort)
    assert isinstance(tool, TransformPort)
    assert isinstance(tool, ProbePort)


PROBE = {'streams': [{'width': 400, 'height': 200}]}


def make_request(action: str = 'blur', mask: str | None = None) -> TransformRequest:
    return TransformRequest(
        ArtifactRef('src-1', sha(IMAGE_BYTES)),
        (TransformRegion('weapon', 0.9, mask or format_mask_ref(0.25, 0.25, 0.5, 0.5)),),
        ('weapon',),
        (('weapon', action),),
        'tp-1',
        {'format': 'png'},
    )


def test_mask_ref_roundtrip_and_rejects_invalid():
    assert parse_mask_ref(format_mask_ref(0.25, 0.25, 0.5, 0.5)) == (0.25, 0.25, 0.5, 0.5)
    with pytest.raises(ValueError):
        format_mask_ref(0.8, 0, 0.5, 0.5)
    with pytest.raises(ValueError):
        format_mask_ref(0, 0, 0, 0.5)
    with pytest.raises(ValueError):
        format_mask_ref(float('nan'), 0, 0.5, 0.5)
    with pytest.raises(ValueError):
        parse_mask_ref('mask-1')


def test_transform_blur_builds_boxblur_filtergraph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch, fake=FakeRun(probe_json=PROBE))
    output = tool.transform(make_request())
    ffmpeg_call = fake.calls[-1]
    fc_idx = ffmpeg_call[0].index('-filter_complex')
    assert ffmpeg_call[0][fc_idx + 1] == '[0:v]split=2[b0][t0];[t0]crop=200:100:100:50,boxblur=luma_radius=25:luma_power=3[k0];[b0][k0]overlay=100:50[b1]'
    map_idx = ffmpeg_call[0].index('-map')
    assert ffmpeg_call[0][map_idx + 1] == '[b1]'
    assert output.processed_ref.ref.startswith('processed:') and output.processed_ref.ref != 'src-1'
    assert output.processed_ref.content_sha256 == sha(b'rendered')
    assert output.evidence_ref == 'evidence:' + sha(b'rendered')
    assert output.processor_version == 'ffmpeg-' + ARCHIVE
    assert output.post_assessment.outcome is SafetyOutcome.DETECTION_FAILED
    assert paths['in'].read_bytes() == IMAGE_BYTES
    for c_args, c_kwargs in fake.calls:
        assert c_kwargs.get('shell') is False


def test_transform_through_domain_success_with_reassess_and_warning_without(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    safe_assessment = ImageSafetyAssessment(
        outcome=SafetyOutcome.SAFE,
        original_usable=True,
        reason='no_sensitive_category',
        confidence=0.95,
        policy_revision='ip-1',
    )
    transform_required_assessment = ImageSafetyAssessment(
        outcome=SafetyOutcome.TRANSFORM_REQUIRED,
        original_usable=True,
        reason='categories_require_transform',
        categories=('weapon',),
        confidence=0.9,
        policy_revision='ip-1',
    )
    regions = (TransformRegion('weapon', 0.9, format_mask_ref(0.25, 0.25, 0.5, 0.5)),)

    tool_reassess, _, _ = build(tmp_path / 't1', monkeypatch, fake=FakeRun(probe_json=PROBE), reassess=lambda ref: safe_assessment)
    res1 = transform_sensitive_image(
        'image',
        False,
        transform_required_assessment,
        ArtifactRef('src-1', sha(IMAGE_BYTES)),
        regions,
        TransformPolicy('tp-1', {'weapon': 'blur'}),
        {'format': 'png'},
        tool_reassess,
    )
    assert res1.status.value == 'success'
    assert res1.processed_ref.ref != res1.original_ref.ref

    tool_no_reassess, _, _ = build(tmp_path / 't2', monkeypatch, fake=FakeRun(probe_json=PROBE))
    res2 = transform_sensitive_image(
        'image',
        False,
        transform_required_assessment,
        ArtifactRef('src-1', sha(IMAGE_BYTES)),
        regions,
        TransformPolicy('tp-1', {'weapon': 'blur'}),
        {'format': 'png'},
        tool_no_reassess,
    )
    assert res2.status.value == 'warning'
    assert res2.processed_ref.ref != res2.original_ref.ref


def test_transform_reject_action_not_processed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    transform_required_assessment = ImageSafetyAssessment(
        outcome=SafetyOutcome.TRANSFORM_REQUIRED,
        original_usable=True,
        reason='categories_require_transform',
        categories=('weapon',),
        confidence=0.9,
        policy_revision='ip-1',
    )
    regions = (TransformRegion('weapon', 0.9, format_mask_ref(0.25, 0.25, 0.5, 0.5)),)
    tool, fake, _ = build(tmp_path, monkeypatch, fake=FakeRun(probe_json=PROBE))
    result = transform_sensitive_image(
        'image',
        False,
        transform_required_assessment,
        ArtifactRef('src-1', sha(IMAGE_BYTES)),
        regions,
        TransformPolicy('tp-1', {'weapon': 'reject'}),
        {'format': 'png'},
        tool,
    )
    assert result.status.value == 'failure'
    assert 'transform_raised' in result.warnings
    assert not any(Path(call[0][0]).stem == 'ffmpeg' for call in fake.calls)


def test_transform_region_too_small_and_bad_mask_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, _ = build(tmp_path, monkeypatch, fake=FakeRun(probe_json=PROBE))
    req_small = make_request(mask=format_mask_ref(0, 0, 0.005, 0.005))
    with pytest.raises(FfmpegToolError) as exc_info:
        tool.transform(req_small)
    assert exc_info.value.code == 'region_too_small'
    with pytest.raises(ValueError):
        tool.transform(make_request(mask='mask-1'))


def test_transform_pin_mismatch_raises_before_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, _ = build(tmp_path, monkeypatch, pin_sha='0' * 64, fake=FakeRun(probe_json=PROBE))
    with pytest.raises(FfmpegToolError):
        tool.transform(make_request())
    assert fake.calls == []


def test_probe_returns_ffprobe_dict_and_empty_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool, fake, paths = build(tmp_path, monkeypatch, fake=FakeRun(probe_json=PROBE))
    assert tool.probe(ArtifactRef('src-1', sha(IMAGE_BYTES))) == PROBE
    probe_call = fake.calls[1]
    assert '-show_format' in probe_call[0] and '-show_streams' in probe_call[0]
    assert probe_call[0][0] == str(paths['ffprobe'])

    class NonJsonFake(FakeRun):
        def __call__(self, args, **kwargs):
            res = super().__call__(args, **kwargs)
            if Path(args[0]).stem == 'ffprobe' and '-version' not in args:
                return subprocess.CompletedProcess(args, 0, stdout='not-json', stderr='')
            return res

    tool_bad, _, _ = build(tmp_path / 'bad', monkeypatch, fake=NonJsonFake())
    assert tool_bad.probe(ArtifactRef('src-1', sha(IMAGE_BYTES))) == {}

    tool_pin, _, _ = build(tmp_path / 'pin', monkeypatch, pin_sha='0' * 64)
    assert tool_pin.probe(ArtifactRef('src-1', sha(IMAGE_BYTES))) == {}

    assert tool.probe(ArtifactRef('missing', sha(IMAGE_BYTES))) == {}


POLICY = ImageSafetyPolicy('ip-1', 0.5, ['weapon', 'minor_child'], True)


class FakeRoute:
    def __init__(self, result=None, error=None) -> None:
        self.calls: list[tuple[str, str, str, str, float]] = []
        self.result = result
        self.error = error

    def invoke_vision(self, ai_role: str, instructions: str, image_base64: str, media_type: str, timeout_seconds: float) -> str | Mapping[str, object]:
        self.calls.append((ai_role, instructions, image_base64, media_type, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.result


REF = ArtifactRef('img-1', sha(IMAGE_BYTES))


def make_detector(route, *, clock=None, read=None):
    kwargs = {}
    if clock is not None:
        kwargs['clock'] = clock
    return LlmImageSafetyDetector(
        route,
        REF,
        read or (lambda r: (IMAGE_BYTES, 'image/png')),
        timeout_seconds=120.0,
        **kwargs,
    )


GOOD = json.dumps({'confidence': 0.95, 'detections': []})


def test_clean_image_is_safe():
    route = FakeRoute(result=GOOD)
    detector = make_detector(route)
    assessment = assess_image_safety('image', detector, POLICY)
    assert assessment.outcome is SafetyOutcome.SAFE
    assert len(route.calls) == 1
    call = route.calls[0]
    assert call[0] == 'image_safety'
    assert call[3] == 'image/png'
    assert call[4] == 120.0
    assert base64.b64decode(call[2]) == IMAGE_BYTES


def test_sensitive_region_requires_transform():
    raw_detections = [{'category': 'weapon', 'confidence': 0.9, 'region': {'x': 0.25, 'y': 0.25, 'width': 0.5, 'height': 0.5}}]
    payload = {'confidence': 0.9, 'detections': raw_detections}

    for result in [
        json.dumps(payload),
        '```json\n' + json.dumps(payload) + '\n```',
        payload,
    ]:
        route = FakeRoute(result=result)
        detector = make_detector(route)
        assessment = assess_image_safety('image', detector, POLICY)
        assert assessment.outcome is SafetyOutcome.TRANSFORM_REQUIRED
        assert assessment.categories == ('weapon',)
        expected_region = TransformRegion('weapon', 0.9, format_mask_ref(0.25, 0.25, 0.5, 0.5))
        assert detector.regions == (expected_region,)


def test_low_confidence_is_uncertain():
    route = FakeRoute(result=json.dumps({'confidence': 0.4, 'detections': [{'category': 'weapon', 'confidence': 0.4}]}))
    detector = make_detector(route)
    assessment = assess_image_safety('image', detector, POLICY)
    assert assessment.outcome is SafetyOutcome.UNCERTAIN


def test_non_policy_category_is_safe_but_unknown_category_fails():
    route_child = FakeRoute(result=json.dumps({'confidence': 0.9, 'detections': [{'category': 'minor_child', 'confidence': 0.9}]}))
    assessment_child = assess_image_safety('image', make_detector(route_child), POLICY)
    assert assessment_child.outcome is SafetyOutcome.TRANSFORM_REQUIRED

    route_cat = FakeRoute(result=json.dumps({'confidence': 0.9, 'detections': [{'category': 'cat', 'confidence': 0.9}]}))
    detector_cat = make_detector(route_cat)
    assessment_cat = assess_image_safety('image', detector_cat, POLICY)
    assert assessment_cat.outcome is SafetyOutcome.DETECTION_FAILED
    assert detector_cat.failure_code == 'unknown_category'


@pytest.mark.parametrize(
    'bad_raw',
    [
        'not json',
        '[]',
        '{}',
        json.dumps({'confidence': '0.9', 'detections': []}),
        json.dumps({'confidence': True, 'detections': []}),
        json.dumps({'confidence': 1.5, 'detections': []}),
        '{"confidence": NaN, "detections": []}',
        json.dumps({'confidence': 0.9, 'detections': {}}),
        json.dumps({'confidence': 0.9, 'detections': [{'confidence': 0.9}]}),
        json.dumps({'confidence': 0.9, 'detections': [{'category': 'weapon', 'confidence': 0.9, 'region': {'x': 0.9, 'y': 0.0, 'width': 0.5, 'height': 0.5}}]}),
        None,
        42,
    ],
)
def test_malformed_output_is_detection_failed(bad_raw):
    route = FakeRoute(result=bad_raw)
    detector = make_detector(route)
    assessment = assess_image_safety('image', detector, POLICY)
    assert assessment.outcome is SafetyOutcome.DETECTION_FAILED
    assert assessment.outcome is not SafetyOutcome.SAFE
    assert assessment.original_usable == original_usable_for(SafetyOutcome.DETECTION_FAILED, POLICY.require_transform_before_use)
    assert detector.regions == ()


def test_route_error_and_timeout_are_detection_failed():
    route_timeout = FakeRoute(error=TimeoutError())
    det_timeout = make_detector(route_timeout)
    ass_timeout = assess_image_safety('image', det_timeout, POLICY)
    assert ass_timeout.outcome is SafetyOutcome.DETECTION_FAILED
    assert det_timeout.failure_code == 'route_timeout'

    route_err = FakeRoute(error=RuntimeError('image-bytes-leak'))
    det_err = make_detector(route_err)
    ass_err = assess_image_safety('image', det_err, POLICY)
    assert ass_err.outcome is SafetyOutcome.DETECTION_FAILED
    assert det_err.failure_code == 'detector_error'
    assert 'image-bytes-leak' not in repr(ass_err)

    clock_values = [0.0, 500.0, 500.0]
    det_slow = make_detector(FakeRoute(result=GOOD), clock=lambda: clock_values.pop(0))
    ass_slow = assess_image_safety('image', det_slow, POLICY)
    assert ass_slow.outcome is SafetyOutcome.DETECTION_FAILED
    assert det_slow.failure_code == 'route_timeout'


def test_image_integrity_and_read_errors_fail_closed_without_calling_route():
    route = FakeRoute(result=GOOD)
    det1 = make_detector(route, read=lambda r: (b'different-bytes', 'image/png'))
    ass1 = assess_image_safety('image', det1, POLICY)
    assert ass1.outcome is SafetyOutcome.DETECTION_FAILED
    assert det1.failure_code == 'image_sha256_mismatch'

    def _raise_io(r):
        raise OSError('io error')

    det2 = make_detector(route, read=_raise_io)
    ass2 = assess_image_safety('image', det2, POLICY)
    assert ass2.outcome is SafetyOutcome.DETECTION_FAILED
    assert det2.failure_code == 'detector_error'

    det3 = make_detector(route, read=lambda r: (IMAGE_BYTES, 'text/plain'))
    ass3 = assess_image_safety('image', det3, POLICY)
    assert ass3.outcome is SafetyOutcome.DETECTION_FAILED
    assert det3.failure_code == 'bad_image'

    assert route.calls == []


def test_image_content_never_logged_or_leaked(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(0):
        route_ok = FakeRoute(result=GOOD)
        det_ok = make_detector(route_ok)
        assess_image_safety('image', det_ok, POLICY)

        route_err = FakeRoute(error=RuntimeError('leak-check'))
        det_err = make_detector(route_err)
        ass_err = assess_image_safety('image', det_err, POLICY)

    assert caplog.records == []
    encoded = base64.b64encode(IMAGE_BYTES).decode()
    assert encoded not in repr(ass_err)
    assert encoded not in (det_err.failure_code or '')


def test_adapter_sources_have_no_egress_or_shell():
    adapter_dir = Path(tool_module.__file__).parent
    tool_text = (adapter_dir / 'real_ffmpeg_media_tool.py').read_text(encoding='utf-8')
    safety_text = (adapter_dir / 'real_llm_image_safety.py').read_text(encoding='utf-8')

    safety_ast = ast.parse(safety_text)
    imported_names: set[str] = set()
    for node in ast.walk(safety_ast):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.add(node.module.split('.')[0])

    forbidden_modules = {'urllib', 'http', 'socket', 'requests', 'logging', 'subprocess'}
    assert imported_names.isdisjoint(forbidden_modules)

    for text in (tool_text, safety_text):
        assert 'shell=True' not in text
        assert 'from src.' not in text

    assert 'boxblur' in tool_text
    assert 'runtime.lock.json' in tool_text
    assert 'shell=False' in tool_text