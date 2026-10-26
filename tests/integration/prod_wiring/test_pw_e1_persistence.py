"""PW-E1: PostgresOutputRepository stores every kind that VoicePipeline and MediaPipeline write, on a real PostgreSQL 18.6 database.

coveredIds: PW-E1-01, CONV-E-01, CT-MED-001
"""
from __future__ import annotations

import copy
import io
import json
import pathlib
import wave

import pw_support
import pytest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.infrastructure.db.uow import TransactionManager
from voice.adapters.fake_aligner import FakeAligner
from voice.adapters.fake_tts import FakeTtsEngine, FakeVoiceRoute
from voice.application import media_pipeline as mp
from voice.application import voice_pipeline as vp
from voice.domain.audio_bed import AudioBedRequest, AudioCue, LoudnessConstraints, LoudnessReport, PreparedRendition
from voice.domain.image_safety import ImageDetection, ImageSafetyAssessment, ImageSafetyPolicy, SafetyOutcome
from voice.domain.image_transform import TransformOutput, TransformPolicy, TransformRegion
from voice.domain.normalize import NormalizeSpec, NormalizeStep, plan_rendition
from voice.domain.processing import ArtifactRef, Disposition
from voice.domain.timing_coverage import TokenizationPolicy
from voice.persistence import PostgresVoiceUnitOfWork, UnsupportedKindError
from voice.persistence.output_repository import SUPPORTED_KINDS
from voice.ports.media_tool import ToolOutcome
from voice.ports.repositories import KIND_VOICE, KIND_WORD_TIMING, EventContext
from voice.ports.script_text import ScriptText

ROOT = pathlib.Path(__file__).resolve().parents[3]
VOICE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
ROUTE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
TRACK = 'track-1'
TEXT = 'Breaking news today'
ATTEMPTS = {'max_attempts': 2, 'max_attempts_per_provider': 2}
DURATION_RANGE = (500, 70000)
TOKENIZATION = TokenizationPolicy(revision='tok-test-v1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)

SHA_A, SHA_B, SHA_C, SHA_D = 'a' * 64, 'b' * 64, 'c' * 64, 'd' * 64
IMAGE_REF = ArtifactRef('img-1', SHA_A)
IMAGE_RAW = {'format': {'format_name': 'png_pipe'}, 'streams': [{'codec_type': 'image', 'codec_name': 'png', 'width': 640, 'height': 480}]}
IMAGE_POLICY = ImageSafetyPolicy(revision='sp-1', confidence_threshold=0.6, transform_categories=['gore', 'weapon'], require_transform_before_use=False)
TRANSFORM_POLICY = TransformPolicy(revision='tp-1', actions={'gore': 'blur', 'weapon': 'recolor'})
REGIONS = (TransformRegion(category='gore', confidence=0.9, mask_ref='mask-1'),)
OUTPUT_PROFILE = {'format': 'png'}
TRANSFORM_REQUIRED = ImageSafetyAssessment(outcome=SafetyOutcome.TRANSFORM_REQUIRED, original_usable=True, reason='categories_require_transform', categories=('gore',), confidence=0.9, policy_revision='sp-1')
POST_SAFE = ImageSafetyAssessment(outcome=SafetyOutcome.SAFE, original_usable=True, reason='post_check_clean')
RESIZE_SPEC = NormalizeSpec(operations=(NormalizeStep('resize', {'width': 1080, 'height': 1920}),), tool_version='ffmpeg-fake-1', spec_revision='spec-1')
NORMALIZED_REF = plan_rendition(IMAGE_REF, RESIZE_SPEC, 'image').output_ref
KIND_TABLES = {
    'voice': 'cp_voice_tracks',
    'word_timing': 'cp_word_timings',
    'tts_invocation': 'cp_tts_invocation_records',
    'receipt': 'cp_voice_receipts',
    'timing_report': 'cp_timing_validation_reports',
    'language_evidence': 'cp_language_evidence',
    'probe_report': 'cp_probe_reports',
    'image_safety_assessment': 'cp_image_safety_assessments',
    'processed_media': 'cp_processed_media',
    'audio_bed_result': 'cp_audio_bed_results',
    'receipt_by_request': 'cp_analysis_results',
}


def _voice_request() -> dict:
    data = json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))
    return dict(data['entities']['VoiceTrackRequest']['valid'][0])


def _route_request() -> dict:
    data = json.loads(ROUTE_FIXTURE.read_text(encoding='utf-8'))
    base = copy.deepcopy(data['entities']['ProviderRouteRequest']['valid'][0])
    return {**base, 'ai_role': 'voice_synthesis', 'allowed_fallbacks': []}


def _ctx(name: str) -> EventContext:
    return EventContext(workspace_id='ws-1', correlation_id='corr-1', actor='worker-e', occurred_at='2026-10-27T00:00:00+00:00', recovery_epoch='epoch-1', event_id=f'evt-{name}', message_id=f'msg-{name}')


def _wav_duration_ms(audio: bytes) -> int:
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        return wav.getnframes() * 1000 // wav.getframerate()


class _ScriptPort:
    def __init__(self, text: ScriptText) -> None:
        self._text = text

    def get_text(self, script_version_id: str) -> ScriptText:
        return self._text


def _audio_request() -> AudioBedRequest:
    cue = AudioCue(kind='music', start_ms=0, end_ms=5000, artifact_ref='music-1', mood='calm')
    return AudioBedRequest(cues=(cue,), voice_artifact_ref='voice-1', preset_audio_policy_revision='audio-pol-1', loudness_constraints=LoudnessConstraints(min_lufs=-20, max_lufs=-12, max_true_peak_dbtp=-1.0), mix_constraints={'duck_db': -12}, fallback_allowed=False)


class _Probe:
    def __init__(self) -> None:
        self.calls: list = []

    def probe(self, artifact_ref):
        self.calls.append(artifact_ref)
        return IMAGE_RAW


class _Tool:
    def __init__(self, outcome: ToolOutcome | None = None) -> None:
        self.outcome = outcome
        self.calls: list = []

    def run(self, plan):
        self.calls.append(plan)
        return self.outcome or ToolOutcome(Disposition.SUCCEEDED, output_ref=plan.output_ref, output_sha256=SHA_B)


class _Transform:
    def __init__(self) -> None:
        self.calls: list = []

    def transform(self, request):
        self.calls.append(request)
        return TransformOutput(processed_ref=ArtifactRef(f'proc-{request.source_ref.ref}', SHA_C), evidence_ref='evidence-1', processor_version='fake-1.0', post_assessment=POST_SAFE)


class _AudioBed:
    def __init__(self) -> None:
        self.calls: list = []

    def prepare(self, request):
        self.calls.append(request)
        renditions = tuple(PreparedRendition(cue_index=i, rendition_ref=f'bed-{i}', source_artifact_ref=cue.artifact_ref, mood=cue.mood) for i, cue in enumerate(request.cues))
        return mp.AudioBedOutcome(status=Disposition.SUCCEEDED, renditions=renditions, output_hashes=tuple(SHA_D for _ in renditions), loudness_report=LoudnessReport(integrated_lufs=-16.0, true_peak_dbtp=-2.0), provenance={'tool': 'fake-bed'}, risk_metadata={'risk': 'low'})


class VoiceRig:
    def __init__(self, database) -> None:
        request = _voice_request()
        script = ScriptText(script_version_id=request['script_version_id'], text=TEXT, script_fingerprint=request['script_fingerprint'])
        route = FakeVoiceRoute()
        self.manager = TransactionManager(database.dsn)
        self.uow = PostgresVoiceUnitOfWork(self.manager, workspace_id=database.workspace_id)
        self.kokoro = pw_support.FakeKokoro(results={'synthesize': FakeTtsEngine(route).synthesize})
        self.aligner = pw_support.FakeAligner(results={'align': FakeAligner().align})
        self.pipeline = vp.VoicePipeline(uow=self.uow, script_port=_ScriptPort(script), route_port=route, tts_engine=self.kokoro, aligner=self.aligner, measure_duration_ms=_wav_duration_ms)


class MediaRig:
    def __init__(self, database, **ports) -> None:
        self.manager = TransactionManager(database.dsn)
        self.uow = PostgresVoiceUnitOfWork(self.manager, workspace_id=database.workspace_id)
        self.pipeline = mp.MediaPipeline(self.uow, **ports)


@pytest.fixture
def make_voice_rig(pw_database):
    rigs: list = []

    def build() -> VoiceRig:
        rigs.append(VoiceRig(pw_database))
        return rigs[-1]

    yield build
    for rig in rigs:
        rig.manager.close()


@pytest.fixture
def make_media_rig(pw_database):
    rigs: list = []

    def build(**ports) -> MediaRig:
        rigs.append(MediaRig(pw_database, **ports))
        return rigs[-1]

    yield build
    for rig in rigs:
        rig.manager.close()


def _counts(database) -> dict[str, int]:
    with database.connect() as connection:
        return {kind: connection.execute(f'SELECT count(*) FROM controlplane.{table}').fetchone()[0] for kind, table in KIND_TABLES.items()}


def _outbox_count(database) -> int:
    with database.connect() as connection:
        return connection.execute('SELECT count(*) FROM controlplane.cp_outbox_events').fetchone()[0]


def _voice_cmd(name: str = 'voice-1') -> vp.CreateVoiceTrackCommand:
    return vp.CreateVoiceTrackCommand(track_key=TRACK, voice_request=_voice_request(), route_request=_route_request(), attempt_policy=ATTEMPTS, duration_policy=DURATION_RANGE, context=_ctx(name))


def _timing_cmd(name: str = 'timing-1') -> vp.CreateWordTimingCommand:
    return vp.CreateWordTimingCommand(track_key=TRACK, voice_request=_voice_request(), tokenization_policy=TOKENIZATION, context=_ctx(name))


def _full_ports() -> dict:
    return {'probe': _Probe(), 'tool': _Tool(), 'transformer': _Transform(), 'audio_bed': _AudioBed()}


def _boom(*args, **kwargs):
    raise RuntimeError('outbox down')


def _run_media(pipeline) -> dict:
    return {
        'probe': pipeline.probe_media('op-p-1', IMAGE_REF, declared_extension='png', declared_mime='image/png', observed_size=2048),
        'assess': pipeline.assess_image_safety('op-a-1', _ctx('op-a-1'), IMAGE_REF, 'image', lambda: ImageDetection('completed', (), 0.9), IMAGE_POLICY),
        'transform': pipeline.transform_sensitive_image('op-t-1', _ctx('op-t-1'), media_kind='image', user_visual_hook=False, assessment=TRANSFORM_REQUIRED, source_ref=IMAGE_REF, regions=REGIONS, policy=TRANSFORM_POLICY, output_profile=OUTPUT_PROFILE, verified_outputs={'proc-img-1': mp.VerifiedOutput(SHA_C, 1000)}),
        'normalize': pipeline.normalize_media('op-n-1', _ctx('op-n-1'), input_ref=IMAGE_REF, spec=RESIZE_SPEC, media_kind='image', verified_outputs={NORMALIZED_REF: mp.VerifiedOutput(SHA_B, 2048)}),
        'bed': pipeline.prepare_audio_bed('op-b-1', _ctx('op-b-1'), _audio_request(), verified_outputs={'bed-0': mp.VerifiedOutput(SHA_D, 4096)}),
    }


def test_pw_e1_every_kind_of_both_pipelines_has_rows(pw_database, make_voice_rig, make_media_rig):
    voice_rig = make_voice_rig()
    voice = voice_rig.pipeline.create_voice_track(_voice_cmd())
    timing = voice_rig.pipeline.create_word_timing(_timing_cmd())
    results = _run_media(make_media_rig(**_full_ports()).pipeline)
    assert all(item.receipt.disposition is Disposition.SUCCEEDED and not item.replayed for item in results.values())
    counts = _counts(pw_database)
    assert set(counts) == set(SUPPORTED_KINDS) and len(set(KIND_TABLES.values())) == 11
    assert all(count >= 1 for count in counts.values()), counts
    outputs = make_media_rig().uow.outputs
    op_key = _voice_request()['operation_key']
    assert outputs.latest(KIND_VOICE, TRACK).record == voice.voice_track
    assert outputs.latest(KIND_WORD_TIMING, TRACK).record == timing.timing
    assert outputs.latest('language_evidence', TRACK).record == timing.language_evidence
    assert outputs.latest('tts_invocation', TRACK).record.output_fingerprint == voice.voice_track.voice_hash
    assert outputs.latest('timing_report', TRACK).record.coverage.complete is True
    assert outputs.latest('receipt', f'ws-1:CreateVoiceTrack:{op_key}').record == voice.receipt
    assert outputs.latest('receipt', f'ws-1:CreateWordTiming:{op_key}').record == timing.receipt
    stored = {'probe': ('op-p-1', 'probe_report'), 'assess': ('op-a-1', 'image_safety_assessment'), 'transform': ('op-t-1', 'processed_media'), 'normalize': ('op-n-1', 'processed_media'), 'bed': ('op-b-1', 'audio_bed_result')}
    for name, (key, kind) in stored.items():
        result = results[name]
        assert outputs.latest(kind, key).record == result.record
        assert outputs.latest('receipt', key).record == result.receipt
        assert outputs.latest('receipt_by_request', result.receipt.request_fingerprint).record == result.receipt


def test_pw_e1_replay_after_restart_returns_stored_receipt_and_writes_nothing(pw_database, make_voice_rig, make_media_rig):
    first = make_voice_rig()
    voice = first.pipeline.create_voice_track(_voice_cmd())
    timing = first.pipeline.create_word_timing(_timing_cmd())
    results = _run_media(make_media_rig(**_full_ports()).pipeline)
    counts, outbox = _counts(pw_database), _outbox_count(pw_database)
    restarted = make_voice_rig()
    again_voice = restarted.pipeline.create_voice_track(_voice_cmd('voice-2'))
    again_timing = restarted.pipeline.create_word_timing(_timing_cmd('timing-2'))
    assert again_voice.replayed is True and again_timing.replayed is True
    assert again_voice.receipt == voice.receipt and again_voice.voice_track == voice.voice_track
    assert again_timing.receipt == timing.receipt and again_timing.timing == timing.timing
    assert restarted.kokoro.call_count('synthesize') == 0 and restarted.aligner.call_count('align') == 0
    ports = _full_ports()
    replayed = _run_media(make_media_rig(**ports).pipeline)
    assert all(item.replayed for item in replayed.values())
    assert {name: item.receipt for name, item in replayed.items()} == {name: item.receipt for name, item in results.items()}
    assert all(not port.calls for port in ports.values())
    assert _counts(pw_database) == counts and _outbox_count(pw_database) == outbox
    with pytest.raises(mp.IdempotencyConflictError):
        make_media_rig(**_full_ports()).pipeline.probe_media('op-p-1', IMAGE_REF, observed_size=4096)


def test_pw_e1_failure_midway_rolls_back_every_kind_and_the_outbox(pw_database, make_voice_rig, make_media_rig, monkeypatch):
    rig = make_voice_rig()
    with monkeypatch.context() as patch:
        patch.setattr(rig.uow.outbox, 'append_event', _boom)
        with pytest.raises(RuntimeError, match='outbox down'):
            rig.pipeline.create_voice_track(_voice_cmd())
    assert rig.uow.active is False
    assert set(_counts(pw_database).values()) == {0} and _outbox_count(pw_database) == 0
    retried = rig.pipeline.create_voice_track(_voice_cmd('voice-retry'))
    assert retried.replayed is False
    counts = _counts(pw_database)
    assert (counts[KIND_VOICE], counts['tts_invocation'], counts['receipt']) == (1, 1, 1) and _outbox_count(pw_database) == 1
    media = make_media_rig(**_full_ports())
    with monkeypatch.context() as patch:
        patch.setattr(media.uow.outbox, 'append_event', _boom)
        failed = media.pipeline.assess_image_safety('op-a-1', _ctx('op-a-1'), IMAGE_REF, 'image', lambda: ImageDetection('completed', (), 0.9), IMAGE_POLICY)
    assert failed.replayed is False and failed.record is None
    assert failed.receipt.disposition is Disposition.FAILED and failed.receipt.error == mp.ERR_RECEIPT_COMMIT_FAILED
    counts = _counts(pw_database)
    assert counts['image_safety_assessment'] == 0 and _outbox_count(pw_database) == 1
    assert counts['receipt'] == 2 and counts['receipt_by_request'] == 1


def test_pw_e1_repository_rejects_bad_kind_record_and_second_receipt_revision(pw_database, make_media_rig):
    rig = make_media_rig()
    outputs, fingerprint = rig.uow.outputs, 'f' * 64
    receipt = mp.OperationReceipt('op-x', 'ProbeMedia', fingerprint, Disposition.SUCCEEDED)
    with rig.uow:
        with pytest.raises(UnsupportedKindError):
            outputs.append('no_such_kind', 'k', 1, object())
        with pytest.raises(TypeError):
            outputs.append('probe_report', 'k', 1, object())
        with pytest.raises(TypeError):
            outputs.append('receipt', 'k', 1, object())
        outputs.append('receipt', 'op-x', 1, receipt)
        with pytest.raises(RevisionConflictError):
            outputs.append('receipt', 'op-x', 2, receipt)
        with pytest.raises(RevisionConflictError):
            outputs.append('receipt_by_request', fingerprint, 2, receipt)
        outputs.append('receipt_by_request', fingerprint, 1, receipt)
        outputs.append('receipt_by_request', fingerprint, 2, receipt)
        rig.uow.commit()
    assert [item.revision for item in outputs.revisions('receipt_by_request', fingerprint)] == [1, 2]
    assert outputs.latest('receipt', 'op-x').record == receipt
    assert _counts(pw_database)['receipt'] == 1


def test_pw_e1_supported_kinds_match_every_kind_the_pipelines_write():
    written = {KIND_VOICE, KIND_WORD_TIMING, vp.KIND_TTS_INVOCATION, vp.KIND_RECEIPT, vp.KIND_TIMING_REPORT, vp.KIND_LANGUAGE_EVIDENCE, mp.KIND_PROBE_REPORT, mp.KIND_IMAGE_SAFETY, mp.KIND_PROCESSED_MEDIA, mp.KIND_AUDIO_BED, mp.KIND_RECEIPT_BY_REQUEST}
    assert len(written) == 11
    assert set(SUPPORTED_KINDS) == written == set(KIND_TABLES)
