"""PW-E3: ImageSafetyPolicy and NormalizeSpec from the production profile, ActivityInputPort E and the image safety chain (DQ-11), on real PostgreSQL 18.6 and the pinned FFmpeg.

coveredIds: PW-E3-01, CT-MED-001, CT-MED-007
"""
from __future__ import annotations

import base64
import copy
import datetime
import hashlib
import io
import json
import pathlib
import struct
import wave
import zlib

import pw_support
import pytest

from controlplane.api.wiring.production_profile import load_production_profile
from controlplane.domain.orchestration import ExecutionGrant
from controlplane.infrastructure.db.uow import TransactionManager
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from creative.persistence.repositories import PostgresScriptRepository
from voice.adapters import profile_media_policy as pmp
from voice.adapters.activity_inputs import ActivityInputError, LazyVerifiedOutputs, MediaArtifact, PlanAudio, ProductionActivityInputs, VoiceSettings, handle_voice_activity
from voice.adapters.postgres_script_text import PostgresScriptText
from voice.adapters.profile_media_policy import ProfileParameterMissing
from voice.adapters.real_ffmpeg_media_tool import RealFfmpegMediaTool
from voice.adapters.real_llm_image_safety import LlmImageSafetyDetector
from voice.adapters.wav_duration import measure_wav_duration_ms
from voice.application.media_pipeline import MediaPipeline, VerifiedOutput
from voice.application.voice_pipeline import CreateVoiceTrackCommand, CreateWordTimingCommand
from voice.domain.audio_bed import AudioCue
from voice.domain.image_safety import ImageSafetyAssessment, SafetyOutcome
from voice.domain.image_transform import TransformRegion
from voice.domain.processing import ArtifactRef
from voice.domain.timing_coverage import TokenizationPolicy
from voice.domain.voice_track import VoiceTrack, check_duration
from voice.persistence import PostgresVoiceUnitOfWork
from voice.worker.activity_handler import VoiceActivityDeps

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
LOCK_PATH = ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
NOW = datetime.datetime(2026, 10, 27, 1, 0, tzinfo=datetime.timezone.utc)
JOB = 'job-e3'
STAGE_RUN = 'job-e3:process:r1'
TOKENIZATION = TokenizationPolicy(revision='tok-test-v1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)
MASK = 'region:0.250000,0.250000,0.500000,0.500000'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding='utf-8'))


def profile_params() -> dict:
    return copy.deepcopy(dict(load_production_profile(PROFILE_PATH).parameters))


def png_bytes(seed: int, size: int = 64) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)

    rows = b''.join(bytes([0]) + bytes(v for x in range(size) for v in ((x * 4 + seed) % 256, (y * 4) % 256, (255 - x * 4) % 256)) for y in range(size))
    return bytes.fromhex('89504e470d0a1a0a') + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')


def wav_bytes(duration_ms: int, rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(2 * duration_ms * rate // 1000))
    return buffer.getvalue()


def merge(*groups) -> list[dict]:
    seen, merged = set(), []
    for group in groups:
        for ref in group:
            key = (ref['ref_type'], ref['ref_id'])
            if key not in seen:
                seen.add(key)
                merged.append(dict(ref))
    return merged


def assessment(outcome, usable: bool, reason: str, **kwargs) -> ImageSafetyAssessment:
    return ImageSafetyAssessment(outcome=outcome, original_usable=usable, reason=reason, **kwargs)


def build_all(params: dict, tool_version: str = 'ffmpeg-test-1') -> None:
    pmp.build_image_safety_policy(params)
    pmp.build_transform_policy(params)
    pmp.build_transform_output_profile(params)
    pmp.build_normalize_spec(params, tool_version=tool_version)
    pmp.build_voice_duration_policy(params)
    pmp.build_loudness_constraints(params)
    pmp.build_mix_constraints(params)
    pmp.build_vision_timeout_seconds(params)


def make_script(workspace_id: str, script_id: str, narration: list[str]) -> ScriptVersion:
    ref = ResourceRef(workspace_id, 'article', 'ref-e3', 'rev-1')
    segments = tuple(
        ScriptSegment(segment_id=f'{script_id}-{index}', order=index, text=text, claim_mode='inference', scene_intent='scene', source_refs=(ref,), disclosure=None, word_count=len(text.split()), estimated_seconds=1.0)
        for index, text in enumerate(narration)
    )
    return ScriptVersion(script_version_id=script_id, language='en', hook_intent='hook', thumbnail_transition='cut', segments=segments, pronunciation_hints=(), speech_rate=2.5, estimated_duration_seconds=3.0)


def seed_scripts(manager, workspace_id: str, scripts: list) -> None:
    with manager.borrow_connection() as connection:
        repository = PostgresScriptRepository(lambda: connection, workspace_id)
        for script in scripts:
            repository.append(script.script_version_id, 1, script)


def test_pw_e3_policy_and_spec_are_built_from_the_production_profile() -> None:
    raw, params = raw_profile(), profile_params()
    thresholds = raw['image_safety']['thresholds']['value']
    policy = pmp.build_image_safety_policy(params)
    assert policy.confidence_threshold == thresholds['uncertain_range']['max_exclusive']
    assert list(policy.transform_categories) == sorted(raw['image_safety']['categories']['value'])
    assert policy.require_transform_before_use is True and policy.revision == 'image-safety-r' + str(raw['meta']['revision']['value'])
    assert dict(pmp.build_transform_policy(params).actions) == {name: 'blur' for name in thresholds['blur_min_confidence']}
    boxblur = raw['image_safety']['boxblur']['value']
    assert pmp.build_transform_output_profile(params) == {'filter': 'boxblur', 'luma_radius': boxblur['luma_radius'], 'luma_power': boxblur['luma_power']}
    version = pmp.read_ffmpeg_tool_version(LOCK_PATH)
    assert version == json.loads(LOCK_PATH.read_text(encoding='utf-8'))['pins']['ffmpeg']['archive_name']
    spec = pmp.build_normalize_spec(params, tool_version=version)
    render = raw['render']['profile']['value']
    assert [(str(step.operation), dict(step.params)) for step in spec.operations] == [('resize', {'width': render['width'], 'height': render['height']})]
    assert spec.tool_version == version and spec.spec_revision == 'normalize-r' + str(raw['meta']['revision']['value'])
    params['image_safety.thresholds']['uncertain_range']['max_exclusive'] = 0.7
    params['render.profile']['width'] = 720
    assert pmp.build_image_safety_policy(params).confidence_threshold == 0.7
    assert dict(pmp.build_normalize_spec(params, tool_version=version).operations[0].params)['width'] == 720


MISSING_CASES = ('image_safety.categories', 'image_safety.thresholds', 'image_safety.boxblur', 'render.profile', 'meta.revision', 'voice.duration_range_ms', 'audio.loudness', 'audio.bed_gain_db', 'image_safety.vision')


def test_pw_e3_missing_profile_parameter_is_blocked() -> None:
    for name in MISSING_CASES:
        params = profile_params()
        del params[name]
        with pytest.raises(ProfileParameterMissing) as caught:
            build_all(params)
        assert caught.value.code == 'BLOCKED' and caught.value.parameter == name
    params = profile_params()
    del params['image_safety.thresholds']['uncertain_range']
    with pytest.raises(ProfileParameterMissing) as caught:
        build_all(params)
    assert caught.value.parameter == 'image_safety.thresholds.uncertain_range'
    params = profile_params()
    params['image_safety.thresholds']['detector_failure_action'] = 'keep'
    with pytest.raises(ProfileParameterMissing) as caught:
        build_all(params)
    assert caught.value.parameter == 'image_safety.thresholds.detector_failure_action'
    with pytest.raises(ProfileParameterMissing):
        pmp.read_ffmpeg_tool_version(ROOT / 'tools' / 'runtime' / 'missing.lock.json')
    params = profile_params()
    del params['image_safety.boxblur']
    with pytest.raises(ProfileParameterMissing) as blocked:
        ProductionActivityInputs(parameters=params, tool_version='x-1', scripts=None, outputs=None, media=None, plans=None, selections=None, vision=None, read_image=None, verify_output=None, settings=None, clock=lambda: NOW)
    assert blocked.value.parameter == 'image_safety.boxblur'


def test_pw_e3_only_a_safe_image_is_usable_and_nothing_uncertain_becomes_safe() -> None:
    rules = pmp.build_image_safety_rules(profile_params())
    warn = {'warnings': ('w',)}
    required = {'categories': ('weapon',)}
    cases = [
        (assessment(SafetyOutcome.SAFE, True, 'no_sensitive_category'), True, (pmp.USABLE, 'safe')),
        (assessment(SafetyOutcome.UNCERTAIN, True, 'confidence_below_threshold', **warn), True, (pmp.EXCLUDED, 'uncertain')),
        (assessment(SafetyOutcome.DETECTION_FAILED, True, 'detector_failed', **warn), True, (pmp.EXCLUDED, 'detection_failed')),
        (assessment(SafetyOutcome.TRANSFORM_FAILED, True, 'transform_failed', **warn), True, (pmp.EXCLUDED, 'transform_failed')),
        (assessment(SafetyOutcome.UNREADABLE, False, 'unreadable_file'), True, (pmp.EXCLUDED, 'unreadable')),
        (assessment(SafetyOutcome.TRANSFORM_REQUIRED, False, 'categories_require_transform', **required), True, (pmp.TRANSFORM, 'blur_required')),
        (assessment(SafetyOutcome.TRANSFORM_REQUIRED, False, 'categories_require_transform', **required), False, (pmp.EXCLUDED, 'blur_without_region')),
        (assessment(SafetyOutcome.TRANSFORM_REQUIRED, False, 'categories_require_transform', categories=('minor_child', 'weapon')), True, (pmp.EXCLUDED, 'reject_category')),
    ]
    for item, regions, expected in cases:
        assert pmp.image_disposition(item, rules, has_regions=regions) == expected


def test_pw_e3_voice_duration_policy_comes_from_the_profile_and_checks_the_measured_wav() -> None:
    bounds = raw_profile()['voice']['duration_range_ms']['value']
    policy = pmp.build_voice_duration_policy(profile_params())
    assert policy == (bounds['min'], bounds['max'])
    for duration_ms, inside in ((bounds['min'], True), (bounds['max'], True), (bounds['min'] - 1, False), (bounds['max'] + 1, False)):
        measured = measure_wav_duration_ms(wav_bytes(duration_ms))
        assert measured == duration_ms
        finding = check_duration(measured, policy)
        assert (finding is None) == inside
        assert inside or finding.code == 'voice_duration_out_of_range'


class Grants:
    def is_grant_current(self, grant) -> bool:
        return True


class VisionRouter(pw_support.FakeRouter):
    def invoke_vision(self, ai_role, instructions, image_base64, media_type, timeout_seconds):
        return self._record('invoke_vision', ai_role, instructions, image_base64, media_type, timeout_seconds)


class MediaPort:
    def __init__(self) -> None:
        self.items: dict[str, tuple[ArtifactRef, bytes]] = {}

    def media_artifact(self, *, workspace_id, media_asset_id, artifact_version_ref):
        ref, data = self.items[media_asset_id]
        return MediaArtifact(ref, 'png', 'image/png', len(data))


class PlanPort:
    def __init__(self, plan: PlanAudio) -> None:
        self.plan = plan

    def plan_audio(self, *, workspace_id, production_plan_id):
        return self.plan


class SelectionPort:
    def __init__(self, seeds: list) -> None:
        self.seeds = seeds

    def fallback_media(self, *, workspace_id, selection_ref):
        return self.seeds


class World:
    def __init__(self, database, tmp_path: pathlib.Path) -> None:
        self.params = profile_params()
        self.database = database
        workspace = database.workspace_id
        self.manager = TransactionManager(database.dsn)
        self.uow = PostgresVoiceUnitOfWork(self.manager, workspace_id=workspace)
        self.script = make_script(workspace, 'sv-e3', ['Breaking news', 'today in town'])
        seed_scripts(self.manager, workspace, [self.script])
        self.src, self.out = tmp_path / 'src', tmp_path / 'out'
        self.src.mkdir()
        self.out.mkdir()
        self.media = MediaPort()
        self.answers: dict[str, object] = {}
        self.paths: dict[str, pathlib.Path] = {}
        self.seeds: list[MediaArtifact] = []
        self.router = VisionRouter(results={'invoke_vision': self.answer_for})
        self.cue = AudioCue(kind='music', start_ms=0, end_ms=5000, artifact_ref='music-1', mood='calm')
        plan = PlanAudio(cues=(self.cue,), preset_audio_policy_revision='audio-pol-1', mix_constraints={'duck_db': -12}, fallback_allowed=False, fallback_artifact_refs=())
        self.grant = ExecutionGrant(workspace, 'op-e3', JOB, STAGE_RUN, 1, 0)
        self.base_refs = [
            {'ref_type': 'script_version', 'ref_id': 'sv-e3'},
            {'ref_type': 'production_snapshot', 'ref_id': 'snap-e3'},
            {'ref_type': 'creative_asset_selection', 'ref_id': 'sel-e3'},
            {'ref_type': 'production_plan', 'ref_id': 'plan-e3'},
        ]
        settings = VoiceSettings(voice_profile_ref='voice-af_heart', provider_route_ref='route-kokoro-local', expected_language='en', data_sensitivity='internal', max_cost_class='low', duration_policy=pmp.build_voice_duration_policy(self.params), tokenization_policy=TOKENIZATION, attempt_policy={'max_attempts': 2, 'max_attempts_per_provider': 2})
        self.inputs = ProductionActivityInputs(
            parameters=self.params, tool_version=pmp.read_ffmpeg_tool_version(LOCK_PATH),
            scripts=PostgresScriptText(self.manager, workspace_id=workspace), outputs=self.uow.outputs, media=self.media,
            plans=PlanPort(plan), selections=SelectionPort(self.seeds), vision=self.router, read_image=self.read_image,
            verify_output=self.verify_output, settings=settings, clock=lambda: NOW)

    def _write(self, name: str, seed: int) -> tuple[ArtifactRef, bytes]:
        data = png_bytes(seed)
        path = self.src / f'{name}.png'
        path.write_bytes(data)
        ref = ArtifactRef(f'art-{name}', sha(data))
        self.paths[ref.ref] = path
        return ref, data

    def add_image(self, name: str, seed: int, answer: object) -> dict:
        ref, data = self._write(name, seed)
        self.media.items[f'media-{name}'] = (ref, data)
        self.answers[ref.content_sha256] = answer
        return {'ref_type': 'selected_media', 'ref_id': f'media-{name}', 'revision_id': f'v-{name}'}

    def add_seed(self, name: str, seed: int) -> None:
        ref, data = self._write(f'seed-{name}', seed)
        self.seeds.append(MediaArtifact(ref, 'png', 'image/png', len(data)))

    def answer_for(self, ai_role, instructions, image_base64, media_type, timeout_seconds):
        return self.answers[sha(base64.b64decode(image_base64))]

    def read_image(self, ref: str):
        return self.paths[ref].read_bytes(), 'image/png'

    def resolve_input(self, ref: str) -> pathlib.Path:
        return self.paths[ref] if ref in self.paths else self.out / (ref.replace(':', '_') + '.png')

    def resolve_output(self, ref: str, extension: str) -> pathlib.Path:
        return self.out / (ref.replace(':', '_') + '.' + extension)

    def verify_output(self, ref: str):
        path = self.out / (ref.replace(':', '_') + '.png')
        if not path.is_file():
            return None
        data = path.read_bytes()
        return VerifiedOutput(sha(data), len(data))

    def request(self, name: str, index: int, input_refs: list) -> dict:
        return {
            'workflow_id': 'wf-e3', 'workflow_run_id': 'run-e3', 'stage_run_id': STAGE_RUN, 'activity_name': name,
            'activity_version': '1', 'input_refs': input_refs, 'operation_key': f'wf-e3:process:{name}:{index}:r1',
            'capability_requirements': {'task_queue': 'desktop_cpu'}, 'retry_policy_ref': 'retry-1', 'video_job_id': JOB,
        }

    def store(self, kind: str, key: str, record: object) -> None:
        with self.uow as uow:
            uow.outputs.append(kind, key, 1, record)
            uow.commit()

    def close(self) -> None:
        self.manager.close()


def test_pw_e3_voice_probe_and_assess_inputs_come_from_the_ports(pw_database, tmp_path) -> None:
    world = World(pw_database, tmp_path)
    try:
        item = world.add_image('a', 1, {'confidence': 0.9, 'detections': []})
        art, data = world.media.items['media-a']
        refs = merge(world.base_refs, [item])

        def resolve(name):
            return world.inputs.resolve(name, world.request(name, 0, refs), world.grant)

        track = resolve('CreateVoiceTrack')['command']
        assert isinstance(track, CreateVoiceTrackCommand) and track.track_key == 'track:job-e3'
        assert track.voice_request == {'script_version_id': 'sv-e3', 'script_fingerprint': world.script.script_fingerprint, 'voice_profile_ref': 'voice-af_heart', 'provider_route_ref': 'route-kokoro-local', 'expected_language': 'en', 'operation_key': 'wf-e3:process:CreateVoiceTrack:0:r1', 'execution_grant_ref': 'op-e3'}
        assert track.route_request['ai_role'] == 'voice_synthesis' and track.route_request['job_ref'] == JOB and track.route_request['snapshot_ref'] == 'snap-e3'
        assert track.duration_policy == pmp.build_voice_duration_policy(world.params) and track.context.workspace_id == pw_database.workspace_id
        timing = resolve('CreateWordTiming')['command']
        assert isinstance(timing, CreateWordTimingCommand) and timing.track_key == track.track_key and timing.tokenization_policy == TOKENIZATION
        assert timing.voice_request['script_fingerprint'] == world.script.script_fingerprint and timing.voice_request['operation_key'].endswith('CreateWordTiming:0:r1')
        assert resolve('ProbeMedia') == {'artifact_ref': art, 'declared_extension': 'png', 'declared_mime': 'image/png', 'observed_size': len(data)}
        assess = resolve('AssessImageSafety')
        assert set(assess) == {'context', 'artifact_ref', 'media_kind', 'detector', 'policy'}
        assert assess['artifact_ref'] == art and assess['media_kind'] == 'image' and isinstance(assess['detector'], LlmImageSafetyDetector)
        assert assess['policy'] == pmp.build_image_safety_policy(world.params)
        with pytest.raises(ActivityInputError) as unknown:
            world.inputs.resolve('Nope', world.request('Nope', 0, refs), world.grant)
        assert unknown.value.code == 'UNKNOWN_ACTIVITY'
        with pytest.raises(ActivityInputError) as missing:
            world.inputs.resolve('ProbeMedia', world.request('ProbeMedia', 0, world.base_refs), world.grant)
        assert missing.value.code == 'INPUT_NOT_READY'
    finally:
        world.close()


def test_pw_e3_transform_normalize_and_audio_bed_inputs_come_from_the_ports(pw_database, tmp_path) -> None:
    world = World(pw_database, tmp_path)
    try:
        safe_item = world.add_image('a', 1, {'confidence': 0.9, 'detections': []})
        weapon_item = world.add_image('b', 2, {'confidence': 0.9, 'detections': []})
        safe = assessment(SafetyOutcome.SAFE, True, 'no_sensitive_category')
        weapon = assessment(SafetyOutcome.TRANSFORM_REQUIRED, False, 'categories_require_transform', categories=('weapon',), confidence=0.9, policy_revision='image-safety-r1')
        world.store('image_safety_assessment', 'assess-a', safe)
        world.store('image_safety_assessment', 'assess-b', weapon)
        link_a = {'ref_type': 'image_safety_assessment', 'ref_id': 'assessment:assess-a', 'source_ref_id': 'media-a', 'revision_id': 'v-a'}
        sensitive = {'ref_type': 'sensitive_image', 'ref_id': 'media-b', 'revision_id': 'v-b', 'assessment_ref': 'assessment:assess-b', 'regions': [{'category': 'weapon', 'confidence': 0.9, 'mask_ref': MASK}]}
        version = pmp.read_ffmpeg_tool_version(LOCK_PATH)

        def resolve(name, refs):
            return world.inputs.resolve(name, world.request(name, 0, refs), world.grant)

        normalize = resolve('NormalizeMedia', merge(world.base_refs, [safe_item], [link_a]))
        assert normalize['input_ref'] == world.media.items['media-a'][0] and normalize['media_kind'] == 'image'
        assert normalize['spec'] == pmp.build_normalize_spec(world.params, tool_version=version)
        assert isinstance(normalize['verified_outputs'], LazyVerifiedOutputs) and normalize['verified_outputs'].get('rendition:none') is None
        with pytest.raises(ActivityInputError):
            resolve('NormalizeMedia', merge(world.base_refs, [safe_item]))
        transform = resolve('TransformSensitiveImage', merge(world.base_refs, [sensitive], [safe_item, weapon_item]))
        assert transform['assessment'] == weapon and transform['source_ref'] == world.media.items['media-b'][0]
        assert transform['regions'] == (TransformRegion('weapon', 0.9, MASK),) and transform['user_visual_hook'] is False
        assert transform['policy'] == pmp.build_transform_policy(world.params) and transform['output_profile'] == pmp.build_transform_output_profile(world.params)
        voice = VoiceTrack(voice_artifact_ref='voice-artifact-' + 'a' * 64, script_version_id='sv-e3', script_fingerprint=world.script.script_fingerprint, voice_hash='a' * 64, actual_duration_ms=61000, provider_model_voice_revision='kokoro-v1.0', usage_metrics={}, warnings=(), receipt_ref='receipt-e3')
        world.store('voice', 'track:job-e3', voice)
        request = resolve('PrepareAudioBed', merge(world.base_refs))['request']
        assert request.voice_artifact_ref == voice.voice_artifact_ref and request.cues == (world.cue,)
        assert request.loudness_constraints == pmp.build_loudness_constraints(world.params)
        assert dict(request.mix_constraints) == {'duck_db': -12, 'bed_gain_db': raw_profile()['audio']['bed_gain_db']['value']}
    finally:
        world.close()


def run_chain(world: World) -> dict:
    if not FFMPEG.is_file():
        pytest.fail('BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.', pytrace=False)
    region = {'x': 0.25, 'y': 0.25, 'width': 0.5, 'height': 0.5}
    answers = {
        'safe': {'confidence': 0.9, 'detections': []},
        'uncertain': {'confidence': 0.4, 'detections': []},
        'blur': {'confidence': 0.9, 'detections': [{'category': 'weapon', 'confidence': 0.9, 'region': region}]},
        'reject': {'confidence': 0.9, 'detections': [{'category': 'minor_child', 'confidence': 0.9, 'region': region}]},
        'failed': 'not json',
    }
    selected = [world.add_image(name, index, answer) for index, (name, answer) in enumerate(answers.items(), start=1)]
    world.add_seed('s0', 20)
    world.add_seed('s1', 21)
    tool = RealFfmpegMediaTool(FFMPEG, LOCK_PATH, world.resolve_input, world.resolve_output, reassess=lambda ref: assessment(SafetyOutcome.SAFE, True, 'post_check_clean'))
    deps = VoiceActivityDeps(voice=None, media=MediaPipeline(world.uow, probe=tool, tool=tool, transformer=tool), grants=Grants(), inputs=world.inputs, clock=lambda: NOW)
    produced: list[dict] = []

    def run(name, index, item):
        refs = merge(world.base_refs, [item], selected, produced)
        result = handle_voice_activity(world.request(name, index, refs), world.grant, deps, world.inputs)
        assert result['disposition'] == 'succeeded', result
        return result

    chain = {'answers': answers, 'selected': selected, 'produced': produced, 'assess': [], 'transform': [], 'normalized': {}}
    for index, item in enumerate(selected):
        result = run('AssessImageSafety', index, item)
        chain['assess'].append(result)
        produced.extend(result['output_refs'])
    for index, item in enumerate([ref for ref in produced if ref['ref_type'] == 'sensitive_image']):
        result = run('TransformSensitiveImage', index, item)
        chain['transform'].append(result)
        produced.extend(result['output_refs'])
    for index, item in enumerate(selected):
        result = run('NormalizeMedia', index, item)
        chain['normalized'][item['ref_id']] = result
        produced.extend(result['output_refs'])
    return chain


def test_pw_e3_safety_chain_excludes_unsafe_images_and_blurs_with_the_pinned_ffmpeg(pw_database, tmp_path) -> None:
    world = World(pw_database, tmp_path)
    try:
        chain = run_chain(world)
        answers, selected, produced = chain['answers'], chain['selected'], chain['produced']
        for item, result in zip(selected, chain['assess']):
            links = [ref for ref in result['output_refs'] if ref['ref_type'] == 'image_safety_assessment']
            assert len(links) == 1 and links[0]['source_ref_id'] == item['ref_id']
        outcomes = {name: world.uow.outputs.latest('image_safety_assessment', f'wf-e3:process:AssessImageSafety:{index}:r1').record.outcome for index, name in enumerate(answers)}
        assert outcomes == {'safe': SafetyOutcome.SAFE, 'uncertain': SafetyOutcome.UNCERTAIN, 'blur': SafetyOutcome.TRANSFORM_REQUIRED, 'reject': SafetyOutcome.TRANSFORM_REQUIRED, 'failed': SafetyOutcome.DETECTION_FAILED}
        sensitive = [ref for ref in produced if ref['ref_type'] == 'sensitive_image']
        assert [ref['ref_id'] for ref in sensitive] == ['media-blur'] and sensitive[0]['regions']
        assert len(chain['transform']) == 1
        made = chain['transform'][0]['output_refs']
        assert [ref['produced_by'] for ref in made] == ['TransformSensitiveImage'] and made[0]['source_ref_id'] == 'media-blur'
        blurred = made[0]['ref_id']
        used = {}
        for index, item in enumerate(selected):
            stored = world.uow.outputs.latest('processed_media', f'wf-e3:process:NormalizeMedia:{index}:r1')
            used[item['ref_id']] = None if stored is None else stored.record.input_ref.ref
        assert used == {'media-safe': 'art-safe', 'media-uncertain': 'art-seed-s0', 'media-blur': blurred, 'media-reject': 'art-seed-s1', 'media-failed': None}
        failed = chain['normalized']['media-failed']
        assert failed['output_refs'] == [] and failed['warnings'] == ['image_excluded:detection_failed']
        assert not set(used.values()) & {'art-uncertain', 'art-reject', 'art-failed', 'art-blur'}
        for key in ('media-safe', 'media-uncertain', 'media-blur', 'media-reject'):
            assert [ref['source_ref_id'] for ref in chain['normalized'][key]['output_refs']] == [key]
        blurred_file = world.out / (blurred.replace(':', '_') + '.png')
        assert blurred_file.is_file() and sha(blurred_file.read_bytes()) != world.media.items['media-blur'][0].content_sha256
    finally:
        world.close()
