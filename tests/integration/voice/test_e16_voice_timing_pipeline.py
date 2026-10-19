"""E-16: integration CreateVoiceTrack and CreateWordTiming in-process (CT-TTS-001, CT-SUB-001, CT-RND-002).

coveredIds: CT-TTS-001, CT-SUB-001, CT-RND-002, TST-MEDIA-INV-007 (phía E)
"""

from __future__ import annotations

import ast
import copy
import io
import json
import pathlib
import wave

import pytest
from voice.adapters.fake_aligner import FakeAligner
from voice.adapters.fake_tts import FakeTtsEngine, FakeVoiceRoute, fake_rate_limit, fake_timeout
from voice.adapters.memory import InMemoryUnitOfWork
from voice.application import voice_pipeline as vp
from voice.domain.language_evidence import RevisionMismatchError
from voice.domain.timing_binding import TimingBindingError
from voice.domain.timing_coverage import TokenizationPolicy
from voice.domain.tts_invocation import TtsSynthesis
from voice.domain.voice_track import ScriptBindingError, VoiceTrackRejected
from voice.domain.word_timing import WordTimingError
from voice.ports.aligner import AlignerError
from voice.ports.repositories import EventContext
from voice.ports.script_text import ScriptText

ROOT = pathlib.Path(__file__).resolve().parents[3]
VOICE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
ROUTE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
SOURCES = (
    ROOT / 'src' / 'voice' / 'application' / 'voice_pipeline.py',
    ROOT / 'src' / 'voice' / 'ports' / 'aligner.py',
    ROOT / 'src' / 'voice' / 'adapters' / 'fake_aligner.py',
)
TRACK = 'track-1'
TEXT = 'Breaking news today'
OTHER_SHA = 'fedcba9876543210' * 4
PRIMARY = 'fake-tts-provider'
# test-only policy inputs (GIẢ ĐỊNH, IMPL-PLAN-E §7): src/ has no default for any of them
ATTEMPTS = {'max_attempts': 2, 'max_attempts_per_provider': 2}
DURATION_RANGE = (500, 70000)
TOKENIZATION = TokenizationPolicy(
    revision='tok-test-v1',
    unicode_form='NFC',
    casefold=True,
    edge_strip_categories=('P',),
    gap_tolerance_ms=500,
    min_confidence=0.5,
)


def _voice_request(**extra) -> dict:
    data = json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))
    return {**data['entities']['VoiceTrackRequest']['valid'][0], **extra}


def _route_request() -> dict:
    data = json.loads(ROUTE_FIXTURE.read_text(encoding='utf-8'))
    base = copy.deepcopy(data['entities']['ProviderRouteRequest']['valid'][0])
    return {**base, 'ai_role': 'voice_synthesis', 'allowed_fallbacks': []}


def _context(name: str) -> EventContext:
    return EventContext(
        workspace_id='ws-1',
        correlation_id='corr-1',
        actor='tester',
        occurred_at='2026-01-01T00:00:00+00:00',
        recovery_epoch='epoch-1',
        event_id=f'evt-{name}',
        message_id=f'msg-{name}',
    )


def _wav(duration_ms: int, sample_rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(2 * (sample_rate * duration_ms // 1000)))
    return buffer.getvalue()


def _wav_duration_ms(audio: bytes) -> int:
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        return wav.getnframes() * 1000 // wav.getframerate()


class _ScriptPort:
    def __init__(self, *texts: ScriptText) -> None:
        self._texts = {text.script_version_id: text for text in texts}

    def get_text(self, script_version_id: str) -> ScriptText:
        return self._texts[script_version_id]


class _DurationSequenceEngine:
    """Test-only TTS engine: call n returns a silent WAV of durations[n], so every voice has its own hash."""

    def __init__(self, durations: list[int]) -> None:
        self._durations = durations
        self.synthesize_calls = 0

    def synthesize(self, decision, script_text, request) -> TtsSynthesis:
        duration = self._durations[min(self.synthesize_calls, len(self._durations) - 1)]
        self.synthesize_calls += 1
        return TtsSynthesis(
            audio_bytes=_wav(duration),
            voice_revision='seq-voice-v1',
            usage_metrics={'characters': len(script_text.text)},
            latency_ms=0,
        )


class Rig:
    def __init__(self, *, tts_scripts=None, engine=None, aligner=None, fingerprint=None, extra_texts=()) -> None:
        request = _voice_request()
        script = ScriptText(
            script_version_id=request['script_version_id'],
            text=TEXT,
            script_fingerprint=fingerprint or request['script_fingerprint'],
        )
        self.uow = InMemoryUnitOfWork()
        self.route = FakeVoiceRoute()
        self.engine = FakeTtsEngine(self.route, scripts=tts_scripts) if engine is None else engine
        self.aligner = FakeAligner() if aligner is None else aligner
        self.pipeline = vp.VoicePipeline(
            uow=self.uow,
            script_port=_ScriptPort(script, *extra_texts),
            route_port=self.route,
            tts_engine=self.engine,
            aligner=self.aligner,
            measure_duration_ms=_wav_duration_ms,
        )

    def revs(self, kind: str) -> tuple:
        return self.uow.outputs.revisions(kind, TRACK)

    def receipt(self, command: str, operation_key: str = 'op-voice-001'):
        return self.uow.outputs.latest('receipt', f'ws-1:{command}:{operation_key}')

    def events(self) -> list[str]:
        return [record.event_type for record in self.uow.outbox.records()]


def _voice_cmd(request=None, *, attempts=ATTEMPTS, duration=DURATION_RANGE, name='voice-1'):
    return vp.CreateVoiceTrackCommand(
        track_key=TRACK,
        voice_request=_voice_request() if request is None else request,
        route_request=_route_request(),
        attempt_policy=attempts,
        duration_policy=duration,
        context=_context(name),
    )


def _timing_cmd(request=None, *, policy=TOKENIZATION, name='timing-1'):
    return vp.CreateWordTimingCommand(
        track_key=TRACK,
        voice_request=_voice_request() if request is None else request,
        tokenization_policy=policy,
        context=_context(name),
    )


def test_create_voice_track_commits_voice_invocation_receipt_and_event_together():
    rig = Rig()
    outcome = rig.pipeline.create_voice_track(_voice_cmd())
    voice = outcome.voice_track
    request = _voice_request()
    assert outcome.replayed is False
    assert (voice.script_version_id, voice.script_fingerprint) == (request['script_version_id'], request['script_fingerprint'])
    assert voice.actual_duration_ms == 1000
    assert voice.provider_model_voice_revision == 'fake-voice-v1'
    assert voice.receipt_ref == outcome.receipt.receipt_ref
    stored = rig.uow.outputs.latest('voice', TRACK)
    assert stored.record is voice and stored.revision == 1
    (invocation,) = [item.record for item in rig.revs('tts_invocation')]
    assert (invocation.validation_result, invocation.attempt, invocation.error) == ('passed', 1, None)
    assert invocation.output_fingerprint == voice.voice_hash
    assert rig.receipt('CreateVoiceTrack').record == outcome.receipt
    (record,) = rig.uow.outbox.records()
    assert record.event_type == 'VoiceReady'
    assert dict(record.payload) == {
        'voice_artifact_ref': voice.voice_artifact_ref,
        'voice_hash': voice.voice_hash,
        'script_version_id': voice.script_version_id,
        'receipt_ref': voice.receipt_ref,
    }
    assert rig.engine.synthesize_calls == 1


def test_fingerprint_mismatch_is_rejected_before_any_tts_call():
    rig = Rig(fingerprint=OTHER_SHA)
    with pytest.raises(ScriptBindingError) as info:
        rig.pipeline.create_voice_track(_voice_cmd())
    assert info.value.code == 'script_fingerprint_mismatch'
    assert (rig.engine.synthesize_calls, rig.route.resolve_calls) == (0, 0)
    assert rig.revs('voice') == () and rig.revs('tts_invocation') == ()
    assert rig.receipt('CreateVoiceTrack') is None and rig.events() == []


@pytest.mark.parametrize('kwargs', [{'attempts': None}, {'duration': None}], ids=['attempt_policy', 'duration_policy'])
def test_missing_policy_is_rejected_before_any_tts_call(kwargs):
    rig = Rig()
    with pytest.raises(VoiceTrackRejected) as info:
        rig.pipeline.create_voice_track(_voice_cmd(**kwargs))
    assert info.value.code == 'INPUT_NOT_READY'
    assert rig.engine.synthesize_calls == 0
    assert rig.revs('voice') == () and rig.events() == []


def test_same_operation_key_and_payload_replays_receipt_without_second_voice():
    rig = Rig()
    first = rig.pipeline.create_voice_track(_voice_cmd())
    second = rig.pipeline.create_voice_track(_voice_cmd(name='voice-2'))
    assert second.replayed is True
    assert second.receipt == first.receipt and second.voice_track is first.voice_track
    assert rig.engine.synthesize_calls == 1
    assert len(rig.revs('voice')) == 1 and len(rig.revs('tts_invocation')) == 1
    assert rig.events() == ['VoiceReady']


def test_same_operation_key_with_different_payload_is_idempotency_conflict():
    rig = Rig()
    rig.pipeline.create_voice_track(_voice_cmd())
    changed = _voice_request(voice_profile_ref='other-profile')
    with pytest.raises(vp.IdempotencyConflict) as info:
        rig.pipeline.create_voice_track(_voice_cmd(changed, name='voice-2'))
    assert info.value.code == 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'
    assert rig.engine.synthesize_calls == 1 and len(rig.revs('voice')) == 1


@pytest.mark.parametrize('failure', [fake_timeout(), fake_rate_limit()], ids=['timeout', 'rate_limit'])
def test_provider_failure_records_failed_attempts_without_voice_or_event(failure):
    rig = Rig(tts_scripts={PRIMARY: (failure,)})
    with pytest.raises(vp.VoiceGenerationFailed) as info:
        rig.pipeline.create_voice_track(_voice_cmd())
    assert info.value.code == failure.code and info.value.retryable is True
    records = [item.record for item in rig.revs('tts_invocation')]
    assert [(r.attempt, r.error_code, r.validation_result) for r in records] == [
        (1, failure.code, 'not_run'),
        (2, failure.code, 'not_run'),
    ]
    assert all(r.error and r.voice_revision is None for r in records)
    assert rig.revs('voice') == () and rig.events() == []
    assert rig.receipt('CreateVoiceTrack') is None


def test_provider_failure_keeps_earlier_voice_history_unchanged():
    rig = Rig(tts_scripts={PRIMARY: ('ok', fake_timeout(), fake_rate_limit())})
    first = rig.pipeline.create_voice_track(_voice_cmd())
    second_request = _voice_request(operation_key='op-voice-002')
    with pytest.raises(vp.VoiceGenerationFailed) as info:
        rig.pipeline.create_voice_track(_voice_cmd(second_request, name='voice-2'))
    assert info.value.code == 'rate_limit'
    assert [item.record for item in rig.revs('voice')] == [first.voice_track]
    assert [item.record.error_code for item in rig.revs('tts_invocation')] == [None, 'timeout', 'rate_limit']
    assert rig.events() == ['VoiceReady']
    assert rig.receipt('CreateVoiceTrack', 'op-voice-002') is None


def test_duration_outside_policy_is_rejected_and_invocation_marked_failed():
    rig = Rig(engine=_DurationSequenceEngine([100]))
    with pytest.raises(vp.VoiceDurationRejected) as info:
        rig.pipeline.create_voice_track(_voice_cmd())
    assert info.value.code == 'voice_duration_out_of_range'
    assert info.value.finding.actual_duration_ms == 100
    (invocation,) = [item.record for item in rig.revs('tts_invocation')]
    assert invocation.validation_result == 'failed'
    assert rig.revs('voice') == () and rig.events() == []
    assert rig.receipt('CreateVoiceTrack') is None


def test_outbox_failure_rolls_back_voice_invocation_and_receipt(monkeypatch):
    rig = Rig()

    def broken(*args, **kwargs):
        raise RuntimeError('outbox down')

    monkeypatch.setattr(rig.uow.outbox, 'append_event', broken)
    with pytest.raises(RuntimeError):
        rig.pipeline.create_voice_track(_voice_cmd())
    assert rig.uow.active is False
    assert rig.revs('voice') == () and rig.revs('tts_invocation') == ()
    assert rig.receipt('CreateVoiceTrack') is None
    assert rig.uow.outbox.records() == ()


def test_create_word_timing_without_voice_is_rejected_and_aligner_not_called():
    rig = Rig()
    with pytest.raises(vp.PipelineInputNotReady) as info:
        rig.pipeline.create_word_timing(_timing_cmd())
    assert (info.value.code, info.value.reason) == ('INPUT_NOT_READY', 'voice_track_missing')
    assert rig.aligner.align_calls == 0
    assert rig.revs('word_timing') == () and rig.events() == []


def test_create_word_timing_commits_timing_report_evidence_receipt_and_event_together():
    rig = Rig()
    voice = rig.pipeline.create_voice_track(_voice_cmd()).voice_track
    outcome = rig.pipeline.create_word_timing(_timing_cmd())
    timing = outcome.timing
    assert outcome.replayed is False
    assert [word.normalized_text for word in timing.words] == ['breaking', 'news', 'today']
    assert (timing.voice_hash, timing.script_fingerprint) == (voice.voice_hash, voice.script_fingerprint)
    assert timing.voice_duration_ms == 1000 and timing.alignment_gaps == ()
    assert rig.uow.outputs.latest('word_timing', TRACK).record is timing
    report = rig.uow.outputs.latest('timing_report', TRACK).record
    assert report.validation_report_ref == timing.validation_report_ref
    assert report.coverage.complete is True and report.gap_report.alignment_gaps == ()
    evidence = rig.uow.outputs.latest('language_evidence', TRACK).record
    assert evidence is outcome.language_evidence
    assert (evidence.voice_hash, evidence.timing_artifact_ref) == (voice.voice_hash, timing.timing_artifact_ref)
    assert evidence.findings == ()
    assert rig.receipt('CreateWordTiming').record == outcome.receipt
    assert rig.events() == ['VoiceReady', 'WordTimingReady']
    assert dict(rig.uow.outbox.records()[1].payload) == {
        'timing_artifact_ref': timing.timing_artifact_ref,
        'voice_hash': voice.voice_hash,
        'script_version_id': voice.script_version_id,
        'validation_report_ref': timing.validation_report_ref,
    }
    assert rig.aligner.align_calls == 1


@pytest.mark.parametrize('mode', ['reorder', 'drop_last'])
def test_aligner_reordered_or_missing_words_do_not_emit_word_timing_ready(mode):
    rig = Rig(aligner=FakeAligner(mode=mode))
    rig.pipeline.create_voice_track(_voice_cmd())
    with pytest.raises(vp.TimingCoverageIncomplete) as info:
        rig.pipeline.create_word_timing(_timing_cmd())
    assert info.value.code == 'word_coverage_incomplete'
    assert info.value.report.complete is False
    assert rig.aligner.align_calls == 1
    for kind in ('word_timing', 'timing_report', 'language_evidence'):
        assert rig.revs(kind) == ()
    assert rig.events() == ['VoiceReady']
    assert rig.receipt('CreateWordTiming') is None


def test_aligner_word_beyond_voice_duration_is_rejected():
    rig = Rig(aligner=FakeAligner(mode='beyond_duration'))
    rig.pipeline.create_voice_track(_voice_cmd())
    with pytest.raises(WordTimingError) as info:
        rig.pipeline.create_word_timing(_timing_cmd())
    assert (info.value.code, info.value.field) == ('constraint_violation', 'words')
    assert rig.revs('word_timing') == () and rig.events() == ['VoiceReady']


def test_same_timing_operation_key_replays_receipt_and_conflicts_on_different_payload():
    rig = Rig()
    rig.pipeline.create_voice_track(_voice_cmd())
    first = rig.pipeline.create_word_timing(_timing_cmd())
    second = rig.pipeline.create_word_timing(_timing_cmd(name='timing-2'))
    assert second.replayed is True
    assert second.receipt == first.receipt and second.timing is first.timing
    assert second.language_evidence is first.language_evidence
    assert rig.aligner.align_calls == 1 and len(rig.revs('word_timing')) == 1
    assert rig.events() == ['VoiceReady', 'WordTimingReady']
    changed = _voice_request(style_parameters={'pace': 'fast'})
    with pytest.raises(vp.IdempotencyConflict):
        rig.pipeline.create_word_timing(_timing_cmd(changed, name='timing-3'))
    assert rig.aligner.align_calls == 1


def test_locale_mismatch_is_recorded_as_finding_and_does_not_block_timing():
    rig = Rig(aligner=FakeAligner(locale_reported='fr'))
    rig.pipeline.create_voice_track(_voice_cmd())
    outcome = rig.pipeline.create_word_timing(_timing_cmd())
    assert [finding.code for finding in outcome.language_evidence.findings] == ['language_mismatch']
    assert rig.events() == ['VoiceReady', 'WordTimingReady']


def test_aligner_error_propagates_without_any_timing_write():
    failure = AlignerError('timeout', 'aligner timeout', retryable=True)
    rig = Rig(aligner=FakeAligner(failure=failure))
    rig.pipeline.create_voice_track(_voice_cmd())
    with pytest.raises(AlignerError) as info:
        rig.pipeline.create_word_timing(_timing_cmd())
    assert info.value.code == 'timeout' and rig.aligner.align_calls == 1
    for kind in ('word_timing', 'timing_report', 'language_evidence'):
        assert rig.revs(kind) == ()
    assert rig.receipt('CreateWordTiming') is None and rig.events() == ['VoiceReady']


def test_outbox_failure_rolls_back_timing_report_evidence_and_receipt(monkeypatch):
    rig = Rig()
    rig.pipeline.create_voice_track(_voice_cmd())

    def broken(*args, **kwargs):
        raise RuntimeError('outbox down')

    monkeypatch.setattr(rig.uow.outbox, 'append_event', broken)
    with pytest.raises(RuntimeError):
        rig.pipeline.create_word_timing(_timing_cmd())
    assert rig.uow.active is False
    for kind in ('word_timing', 'timing_report', 'language_evidence'):
        assert rig.revs(kind) == ()
    assert rig.receipt('CreateWordTiming') is None and rig.events() == ['VoiceReady']


def test_voice_change_after_timing_rejects_old_timing_and_new_timing_needs_new_command():
    rig = Rig(engine=_DurationSequenceEngine([1000, 2000]))
    rig.pipeline.create_voice_track(_voice_cmd())
    old = rig.pipeline.create_word_timing(_timing_cmd())
    assert rig.pipeline.require_current_timing(TRACK, _voice_request()) is old.timing
    new_request = _voice_request(operation_key='op-voice-002')
    new_voice = rig.pipeline.create_voice_track(_voice_cmd(new_request, name='voice-2')).voice_track
    assert new_voice.voice_hash != old.timing.voice_hash
    with pytest.raises(TimingBindingError) as info:
        rig.pipeline.require_current_timing(TRACK, new_request)
    assert info.value.reasons == ('voice_changed',)
    assert info.value.timing_artifact_ref == old.timing.timing_artifact_ref
    with pytest.raises(TimingBindingError):
        rig.pipeline.create_word_timing(_timing_cmd(name='timing-replay'))
    assert rig.aligner.align_calls == 1
    new = rig.pipeline.create_word_timing(_timing_cmd(new_request, name='timing-2'))
    assert new.replayed is False and new.timing.voice_hash == new_voice.voice_hash
    assert new.timing.voice_duration_ms == 2000
    assert rig.pipeline.require_current_timing(TRACK, new_request) is new.timing
    assert [item.revision for item in rig.revs('word_timing')] == [1, 2]
    assert rig.revs('word_timing')[0].record is old.timing
    assert rig.aligner.align_calls == 2


def test_script_change_after_timing_rejects_old_timing_and_stale_voice():
    other_id = '00000000-0000-4000-8000-000000000040'
    other_text = ScriptText(script_version_id=other_id, text='Breaking news tomorrow', script_fingerprint=OTHER_SHA)
    rig = Rig(extra_texts=(other_text,))
    rig.pipeline.create_voice_track(_voice_cmd())
    rig.pipeline.create_word_timing(_timing_cmd())
    new_request = _voice_request(script_version_id=other_id, script_fingerprint=OTHER_SHA, operation_key='op-voice-002')
    with pytest.raises(TimingBindingError) as info:
        rig.pipeline.require_current_timing(TRACK, new_request)
    assert info.value.reasons == ('script_changed',)
    with pytest.raises(RevisionMismatchError) as mismatch:
        rig.pipeline.create_word_timing(_timing_cmd(new_request, name='timing-2'))
    assert mismatch.value.fields == ('script_version_id', 'script_fingerprint')
    assert rig.aligner.align_calls == 1 and len(rig.revs('word_timing')) == 1


FORBIDDEN_ROOTS = frozenset(
    {'os', 'subprocess', 'socket', 'shutil', 'time', 'datetime', 'uuid', 'random', 'urllib', 'http', 'psycopg', 'temporalio'}
)


def test_sources_have_no_clock_io_or_adapter_imports():
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or '']
            else:
                continue
            for name in names:
                assert name.split('.')[0] not in FORBIDDEN_ROOTS, (path.name, name)
                if path.name != 'fake_aligner.py':
                    assert not name.startswith('voice.adapters'), (path.name, name)
