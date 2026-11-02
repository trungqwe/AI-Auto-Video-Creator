"""ADAPT-E-MEDIA-FIX4 (RG-13): chuẩn hoá giữ tỉ lệ, che mờ tối thiểu, ảnh chưa chắc dùng nguyên gốc, bản che luôn dùng được, vùng null hỏi lại một lần; FFmpeg ghim, PNG tổng hợp, không DB.

coveredIds: CT-PROC-005, CT-PROC-006, CT-PROC-007, DQ-11
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import pathlib
import struct
import subprocess
import zlib
from types import SimpleNamespace

import pytest

from controlplane.api.wiring.production_profile import load_production_profile
from controlplane.api.wiring.voice import VoiceServices, voice_activity_deps
from controlplane.domain.orchestration import ExecutionGrant
from voice.adapters import real_ffmpeg_media_tool as tool_module
from voice.adapters.activity_inputs import MediaArtifact, ProductionActivityInputs, handle_voice_activity
from voice.adapters.memory import InMemoryUnitOfWork
from voice.adapters.profile_media_policy import (
    build_image_safety_rules,
    build_vision_timeout_seconds,
    read_ffmpeg_tool_version,
)
from voice.adapters.real_ffmpeg_media_tool import RealFfmpegMediaTool, format_mask_ref
from voice.adapters.real_llm_image_safety import LlmImageSafetyDetector
from voice.application.media_pipeline import VerifiedOutput
from voice.domain.image_safety import SafetyOutcome
from voice.domain.image_transform import TransformRegion, TransformRequest
from voice.domain.normalize import NormalizeSpec, NormalizeStep, plan_rendition
from voice.domain.processing import ArtifactRef, Disposition
from voice.worker.activity_handler import VoiceActivityDeps

ROOT = pathlib.Path(__file__).resolve().parents[4]
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
LOCK_PATH = ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
NOW = datetime.datetime(2026, 11, 2, 1, 0, tzinfo=datetime.timezone.utc)
WS = 'ws-r13'
JOB = 'job-r13'
STAGE_RUN = 'job-r13:process:r1'
GRANT = ExecutionGrant(WS, 'op-r13', JOB, STAGE_RUN, 1, 0)
CATEGORIES = ('minor_child', 'nudity_sexual', 'graphic_violence', 'weapon', 'hate_symbol', 'logo_watermark')
BOX = {'x': 0.25, 'y': 0.25, 'width': 0.5, 'height': 0.5}
BASE_REFS = [{'ref_type': 'creative_asset_selection', 'ref_id': 'sel-r13'}]


@pytest.fixture(autouse=True)
def pinned_ffmpeg():
    if not FFMPEG.is_file():
        pytest.fail(
            'BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.',
            pytrace=False,
        )


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png(width: int, height: int, seed: int = 0) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xFFFFFFFF)

    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(((x * 7 + y + seed) % 256, (y * 5 + x // 3) % 256, (x * y // 3 + seed) % 256))
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(bytes(rows))) + chunk(b'IEND', b'')


def size_of(path: pathlib.Path) -> tuple[int, int]:
    data = path.read_bytes()
    return struct.unpack('>II', data[16:24])


def raw_rgb(path: pathlib.Path) -> bytes:
    done = subprocess.run(
        [str(FFMPEG), '-v', 'error', '-nostdin', '-i', str(path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


def answer(scores=None, detections=(), confidence=0.9):
    return {
        'confidence': confidence,
        'detections': list(detections),
        'scores': {**{c: 0.0 for c in CATEGORIES}, **(scores or {})},
    }


def det(category, confidence, region=BOX):
    return {'category': category, 'confidence': confidence, 'region': region}


CLEAN = answer()


class Route:
    def __init__(self) -> None:
        self.scores = {}
        self.regions = {}
        self.calls = []
        self.prompts = []
        self.default = CLEAN

    def invoke_vision(self, ai_role, instructions, image_base64, media_type, timeout_seconds):
        digest = sha(base64.b64decode(image_base64))
        kind = 'regions' if '"regions"' in instructions else 'scores'
        self.calls.append((digest, kind))
        self.prompts.append(instructions)
        if kind == 'regions':
            value = self.regions[digest].pop(0)
        else:
            value = self.scores.get(digest, self.default)
        return value if isinstance(value, str) else json.dumps(value)


class Grants:
    def is_grant_current(self, grant) -> bool:
        return True


class World:
    def __init__(self, tmp_path, route) -> None:
        self.route = route
        self.src = tmp_path / 'src'
        self.out = tmp_path / 'out'
        self.src.mkdir()
        self.out.mkdir()
        self.paths = {}
        self.items = {}
        self.seeds = []
        self.selected = []
        profile = load_production_profile(PROFILE_PATH)
        self.rules = build_image_safety_rules(profile.parameters)
        timeout = build_vision_timeout_seconds(profile.parameters)
        self.uow = InMemoryUnitOfWork()
        self.tool = RealFfmpegMediaTool(FFMPEG, LOCK_PATH, self.resolve_input, self.resolve_output)

        def factory(artifact):
            return LlmImageSafetyDetector(
                route,
                artifact,
                self.read_image,
                categories=self.rules.categories,
                timeout_seconds=timeout,
                uncertain_min=self.rules.uncertain_min,
            )

        services = VoiceServices('test', lambda: self.uow, None, None, self.tool, factory, None)
        runtime = SimpleNamespace(
            staging_root=tmp_path / 'staging',
            runtime_lock_path=LOCK_PATH,
            vision_route=route,
            tokenization={
                'revision': 'tok-r13',
                'unicode_form': 'NFC',
                'casefold': True,
                'edge_strip_categories': ('P',),
                'gap_tolerance_ms': 500,
                'min_confidence': 0.5,
            },
        )
        base, _ = voice_activity_deps(
            services,
            manager=SimpleNamespace(),
            workspace_id=WS,
            profile=profile,
            runtime=runtime,
            grants=Grants(),
            clock=lambda: NOW,
            music_sources=(),
        )
        self.inputs = ProductionActivityInputs(
            parameters=profile.parameters,
            tool_version=read_ffmpeg_tool_version(LOCK_PATH),
            scripts=None,
            outputs=self.uow.outputs,
            media=self,
            plans=None,
            selections=self,
            vision=route,
            read_image=self.read_image,
            verify_output=self.verify_output,
            settings=None,
            clock=lambda: NOW,
        )
        self.deps = VoiceActivityDeps(voice=None, media=base.media, grants=Grants(), inputs=self.inputs, clock=lambda: NOW)

    def resolve_input(self, ref):
        if ref in self.paths:
            return self.paths[ref]
        return self.out / (ref.replace(':', '_') + '.png')

    def resolve_output(self, ref, extension):
        return self.out / (ref.replace(':', '_') + '.' + extension)

    def read_image(self, ref):
        return (self.resolve_input(ref).read_bytes(), 'image/png')

    def verify_output(self, ref):
        path = self.out / (ref.replace(':', '_') + '.png')
        if not path.is_file():
            return None
        data = path.read_bytes()
        return VerifiedOutput(sha(data), len(data))

    def media_artifact(self, *, workspace_id, media_asset_id, artifact_version_ref):
        ref, data = self.items[media_asset_id]
        return MediaArtifact(ref, 'png', 'image/png', len(data))

    def fallback_media(self, *, workspace_id, selection_ref):
        return self.seeds

    def sha(self, name):
        return self.items['media-' + name][0].content_sha256

    def add_image(self, name, width, height, answer_value):
        data = png(width, height, len(self.items))
        path = self.src / (name + '.png')
        path.write_bytes(data)
        ref = ArtifactRef('art-' + name, sha(data))
        self.paths[ref.ref] = path
        self.items['media-' + name] = (ref, data)
        self.route.scores[ref.content_sha256] = answer_value
        return {'ref_type': 'selected_media', 'ref_id': 'media-' + name, 'revision_id': 'v-' + name}


def merge(*groups):
    seen = {}
    for group in groups:
        for ref in group:
            seen.setdefault((ref['ref_type'], ref['ref_id']), dict(ref))
    return list(seen.values())


def request(name, index, refs):
    return {
        'workflow_id': 'wf-r13',
        'workflow_run_id': 'run-r13',
        'stage_run_id': STAGE_RUN,
        'activity_name': name,
        'activity_version': '1',
        'input_refs': refs,
        'operation_key': 'wf-r13:process:' + name + ':' + str(index) + ':r1',
        'capability_requirements': {'task_queue': 'desktop_cpu'},
        'retry_policy_ref': 'retry-1',
        'video_job_id': JOB,
    }


def run_chain(world, selected):
    world.selected = selected
    produced, assess, transform = [], [], []
    for index, item in enumerate(selected):
        result = handle_voice_activity(
            request('AssessImageSafety', index, merge(BASE_REFS, [item], selected, produced)),
            GRANT,
            world.deps,
            world.inputs,
        )
        assert result['disposition'] == 'succeeded'
        produced.extend(result['output_refs'])
        assess.append(result)
    for index, ref in enumerate([r for r in produced if r['ref_type'] == 'sensitive_image']):
        result = handle_voice_activity(
            request('TransformSensitiveImage', index, merge(BASE_REFS, selected, produced)),
            GRANT,
            world.deps,
            world.inputs,
        )
        produced.extend(result['output_refs'])
        transform.append(result)
    return SimpleNamespace(produced=produced, assess=assess, transform=transform)


def test_blur_radius_follows_the_shorter_side():
    assert [tool_module.blur_radius(*size) for size in ((200, 100), (1000, 500), (32, 32), (8, 8), (100, 200))] == [
        16,
        83,
        5,
        2,
        16,
    ]
    assert (tool_module.BLUR_MIN_RADIUS, tool_module.BLUR_REGION_DIVISOR, tool_module.LUMA_POWER) == (4, 6, 1)
    assert not hasattr(tool_module, 'LUMA_RADIUS')


@pytest.mark.parametrize(
    'width,height,out_w,out_h',
    [(1200, 800, 1080, 720), (1001, 667, 1000, 666), (400, 200, 400, 200)],
)
def test_normalize_fits_inside_the_frame_without_stretch_or_pad(tmp_path, width, height, out_w, out_h):
    data = png(width, height)
    path = tmp_path / 'in.png'
    path.write_bytes(data)
    tool = RealFfmpegMediaTool(
        FFMPEG,
        LOCK_PATH,
        lambda ref: path,
        lambda ref, ext: tmp_path / (ref.replace(':', '_') + '.' + ext),
    )
    spec = NormalizeSpec(
        operations=(NormalizeStep('resize', {'width': 1080, 'height': 1920}),),
        tool_version=read_ffmpeg_tool_version(LOCK_PATH),
        spec_revision='normalize-r6',
    )
    outcome = tool.run(plan_rendition(ArtifactRef('src-1', sha(data)), spec, 'image'))
    assert outcome.status is Disposition.SUCCEEDED, outcome.error
    assert size_of(tmp_path / (outcome.output_ref.replace(':', '_') + '.png')) == (out_w, out_h)


def test_blur_changes_only_the_pixels_inside_the_region(tmp_path):
    data = png(400, 300)
    path = tmp_path / 'in.png'
    path.write_bytes(data)
    tool = RealFfmpegMediaTool(
        FFMPEG,
        LOCK_PATH,
        lambda ref: path,
        lambda ref, ext: tmp_path / (ref.replace(':', '_') + '.' + ext),
    )
    request_ = TransformRequest(
        ArtifactRef('src-1', sha(data)),
        (TransformRegion('weapon', 0.9, format_mask_ref(0.25, 0.25, 0.5, 0.5)),),
        ('weapon',),
        (('weapon', 'blur'),),
        'tp-r13',
        {'format': 'png'},
    )
    output = tool.transform(request_)
    processed = tmp_path / (output.processed_ref.ref.replace(':', '_') + '.png')
    assert size_of(processed) == (400, 300)
    before, after = raw_rgb(path), raw_rgb(processed)
    row = 1200
    for y in range(300):
        b, a = before[y * row:(y + 1) * row], after[y * row:(y + 1) * row]
        if not 75 <= y < 225:
            assert b == a, y
        else:
            assert b[:300] == a[:300] and b[900:] == a[900:], y
    before_region = b''.join(before[y * row + 300:y * row + 900] for y in range(75, 225))
    after_region = b''.join(after[y * row + 300:y * row + 900] for y in range(75, 225))
    assert before_region != after_region


def choice(world, chain, item):
    return world.inputs.normalize_source(WS, merge(BASE_REFS, [item], world.selected, chain.produced))


def assessment_of(world, index):
    return world.uow.outputs.latest(
        'image_safety_assessment', 'wf-r13:process:AssessImageSafety:' + str(index) + ':r1'
    ).record


def sensitive(chain):
    return [r for r in chain.produced if r['ref_type'] == 'sensitive_image']


def test_confirmed_group_is_blurred_and_an_unsure_logo_beside_it_is_ignored(tmp_path):
    route = Route()
    world = World(tmp_path, route)
    item = world.add_image(
        'a', 320, 240, answer({'weapon': 0.9, 'logo_watermark': 0.4}, [det('weapon', 0.9), det('logo_watermark', 0.4)])
    )
    chain = run_chain(world, [item])
    record = assessment_of(world, 0)
    assert record.outcome is SafetyOutcome.TRANSFORM_REQUIRED
    assert record.categories == ('weapon',)
    source = choice(world, chain, item)
    assert source.reason == 'blurred'
    assert source.artifact.ref.startswith('processed:')
    assert [kind for _, kind in route.calls] == ['scores', 'scores']
    assert len(sensitive(chain)) == 1


def test_a_blurred_copy_that_is_still_flagged_stays_usable_with_a_warning(tmp_path):
    route = Route()
    route.default = answer({'weapon': 0.9}, [det('weapon', 0.9)])
    world = World(tmp_path, route)
    item = world.add_image('a', 320, 240, answer({'weapon': 0.9}, [det('weapon', 0.9)]))
    chain = run_chain(world, [item])
    source = choice(world, chain, item)
    assert source.reason == 'blurred_with_warning'
    assert source.artifact.ref.startswith('processed:')
    assert [kind for _, kind in route.calls] == ['scores', 'scores']
    assert len(chain.transform) == 1
    assert len(sensitive(chain)) == 1


def test_an_unsure_image_uses_the_original(tmp_path):
    route = Route()
    world = World(tmp_path, route)
    item = world.add_image('a', 160, 120, answer({'weapon': 0.4}))
    chain = run_chain(world, [item])
    assert assessment_of(world, 0).outcome is SafetyOutcome.UNCERTAIN
    source = choice(world, chain, item)
    assert source.reason == 'uncertain'
    assert source.artifact == world.items['media-a'][0]
    assert sensitive(chain) == []
    assert chain.transform == []
    assert [kind for _, kind in route.calls] == ['scores']


def test_a_null_region_is_asked_again_exactly_once(tmp_path):
    route = Route()
    world = World(tmp_path, route)
    item = world.add_image('a', 320, 240, answer({'weapon': 0.9}, [det('weapon', 0.9, None)]))
    route.regions[world.sha('a')] = [{'regions': [{'category': 'weapon', 'region': BOX}]}]
    chain = run_chain(world, [item])
    assert [kind for _, kind in route.calls] == ['scores', 'regions', 'scores']
    assert '- weapon: ' in route.prompts[1]
    source = choice(world, chain, item)
    assert source.reason == 'blurred'


def test_a_region_that_stays_null_excludes_the_image_after_one_retry(tmp_path):
    route = Route()
    world = World(tmp_path, route)
    item = world.add_image('a', 320, 240, answer({'weapon': 0.9}, [det('weapon', 0.9, None)]))
    route.regions[world.sha('a')] = [{'regions': [{'category': 'weapon', 'region': None}]}]
    chain = run_chain(world, [item])
    assert [kind for _, kind in route.calls] == ['scores', 'regions']
    source = choice(world, chain, item)
    assert source.artifact is None
    assert source.reason == 'blur_without_region'
    assert sensitive(chain) == []
    assert chain.transform == []


def test_a_group_still_missing_its_region_blurs_nothing(tmp_path):
    route = Route()
    world = World(tmp_path, route)
    item = world.add_image(
        'a',
        320,
        240,
        answer({'weapon': 0.9, 'hate_symbol': 0.9}, [det('weapon', 0.9), det('hate_symbol', 0.9, None)]),
    )
    route.regions[world.sha('a')] = [{'regions': []}]
    chain = run_chain(world, [item])
    assert [kind for _, kind in route.calls] == ['scores', 'regions']
    assert '- hate_symbol: ' in route.prompts[1] and '- weapon: ' not in route.prompts[1]
    source = choice(world, chain, item)
    assert source.artifact is None
    assert source.reason == 'blur_without_region'
    assert sensitive(chain) == []


def test_nudity_and_a_failed_detector_are_never_used(tmp_path):
    route = Route()
    world = World(tmp_path, route)
    nude = world.add_image('n', 160, 120, answer({'nudity_sexual': 0.9}, [det('nudity_sexual', 0.9)]))
    failed = world.add_image('f', 160, 120, 'not json')
    chain = run_chain(world, [nude, failed])
    for item, reason in ((nude, 'reject_category'), (failed, 'detection_failed')):
        source = choice(world, chain, item)
        assert source.artifact is None
        assert source.reason == reason
    assert chain.transform == []


def test_a_blur_that_cannot_be_made_is_excluded_as_transform_failed(tmp_path):
    route = Route()
    world = World(tmp_path, route)
    tiny = {'x': 0.5, 'y': 0.5, 'width': 0.005, 'height': 0.005}
    item = world.add_image('a', 320, 240, answer({'weapon': 0.9}, [det('weapon', 0.9, tiny)]))
    chain = run_chain(world, [item])
    source = choice(world, chain, item)
    assert source.artifact is None
    assert source.reason == 'transform_failed'


def test_reassess_runs_once_and_a_failed_detection_is_a_warning(tmp_path):
    route = Route()
    world = World(tmp_path, route)
    world.add_image('a', 160, 120, CLEAN)
    ref = world.items['media-a'][0]
    cases = (
        (CLEAN, SafetyOutcome.SAFE, None),
        (answer({'weapon': 0.9}, [det('weapon', 0.9)]), SafetyOutcome.TRANSFORM_REQUIRED, None),
        ('not json', SafetyOutcome.DETECTION_FAILED, 'post_transform_not_reassessed'),
    )
    for default, outcome, reason in cases:
        route.calls.clear()
        route.scores.clear()
        route.default = default
        assessment = world.tool._reassess(ref)
        assert assessment.outcome is outcome
        if reason:
            assert assessment.reason == reason
        assert len(route.calls) == 1
