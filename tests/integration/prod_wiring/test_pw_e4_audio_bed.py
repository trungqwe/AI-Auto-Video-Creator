"""PW-E4: production AudioBedPort finds, collects and records provenance of external music (FR-AUD-007, FR-AUD-004) on real PostgreSQL 18.6; the HTTPS transport is a fake serving a sample WAV.

coveredIds: PW-E4-01, FR-AUD-007, FR-AUD-004
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import io
import json
import logging
import pathlib
import wave
from collections.abc import Mapping

import pytest

from controlplane.infrastructure.db.uow import TransactionManager
from voice.adapters.audio_bed_source import AudioBedSource, HttpsResponse, MusicSource, MusicSourceError, check_music_url, load_music_sources, silent_wav
from voice.adapters.wav_duration import measure_wav_duration_ms
from voice.application import media_pipeline as mp
from voice.domain.audio_bed import AudioBedRequest, AudioCue, LoudnessConstraints, LoudnessReport
from voice.domain.processing import Disposition
from voice.persistence import PostgresVoiceUnitOfWork
from voice.ports.repositories import EventContext

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCES_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'music_sources.json'
NOW = datetime.datetime(2026, 10, 27, 2, 0, tzinfo=datetime.timezone.utc)
LIMITS = LoudnessConstraints(min_lufs=-20, max_lufs=-12, max_true_peak_dbtp=-1.0)
PRIMARY_URL = 'https://music-primary.test/bed.wav'
FALLBACK_URL = 'https://music-fallback.test/bed.wav'
PROVENANCE_FIELDS = ('url', 'license', 'author', 'attribution', 'collected_at', 'sha256')


def wav_bytes(duration_ms: int, rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(2 * duration_ms * rate // 1000))
    return buffer.getvalue()


SAMPLE = wav_bytes(8000)
OTHER = wav_bytes(9000)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_source(role: str, url: str, data: bytes, moods=('calm',)) -> MusicSource:
    return MusicSource(source_id=f'{role}-test', role=role, url=url, license='CC BY 4.0', attribution='Test Track by Tester', author='Tester', sha256=sha(data), moods=tuple(moods))


class FakeTransport:
    def __init__(self, bodies: dict, status: int = 200, redirect_to: str | None = None) -> None:
        self.bodies, self.status, self.redirect_to, self.calls = dict(bodies), status, redirect_to, []

    def fetch(self, url: str, *, max_bytes: int, timeout_seconds: float) -> HttpsResponse:
        self.calls.append(url)
        if url not in self.bodies:
            raise OSError('unreachable')
        return HttpsResponse(self.status, self.bodies[url], self.redirect_to or url)


def ctx(name: str) -> EventContext:
    return EventContext(workspace_id='ws-1', correlation_id='corr-1', actor='worker-e', occurred_at='2026-10-27T00:00:00+00:00', recovery_epoch='epoch-1', event_id=f'evt-{name}', message_id=f'msg-{name}')


def request(end_ms: int = 5000, mood: str | None = 'calm', kind: str = 'music') -> AudioBedRequest:
    cue = AudioCue(kind=kind, start_ms=0, end_ms=end_ms, artifact_ref='music-1', mood=mood)
    return AudioBedRequest(cues=(cue,), voice_artifact_ref='voice-1', preset_audio_policy_revision='audio-pol-1', loudness_constraints=LIMITS, mix_constraints={'bed_gain_db': -20}, fallback_allowed=False)


class LibraryVerified(Mapping):
    """Verified output evidence read from the stored library file, like the I artifact check."""

    def __init__(self, library: pathlib.Path) -> None:
        self.library = library

    def __getitem__(self, ref: str) -> mp.VerifiedOutput:
        for suffix in ('.audio', '.wav'):
            path = self.library / f'{ref}{suffix}'
            if path.is_file():
                data = path.read_bytes()
                return mp.VerifiedOutput(sha(data), len(data))
        raise KeyError(ref)

    def __iter__(self):
        return iter(())

    def __len__(self) -> int:
        return 0


class Rig:
    def __init__(self, database, bed: AudioBedSource, library: pathlib.Path) -> None:
        self.manager = TransactionManager(database.dsn)
        self.uow = PostgresVoiceUnitOfWork(self.manager, workspace_id=database.workspace_id)
        self.pipeline = mp.MediaPipeline(self.uow, audio_bed=bed)
        self.library = library

    def run(self, key: str, req: AudioBedRequest):
        return self.pipeline.prepare_audio_bed(key, ctx(key), req, verified_outputs=LibraryVerified(self.library))

    def stored(self, key: str):
        return self.uow.outputs.latest('audio_bed_result', key).record


@pytest.fixture
def rig_factory(pw_database, tmp_path):
    rigs = []

    def build(transport: FakeTransport, sources) -> Rig:
        library = tmp_path / 'library'
        bed = AudioBedSource(sources=sources, library_dir=library, transport=transport, duration_probe=measure_wav_duration_ms, loudness_meter=lambda body: LoudnessReport(integrated_lufs=-16.0, true_peak_dbtp=-2.0), clock=lambda: NOW)
        rigs.append(Rig(pw_database, bed, library))
        return rigs[-1]

    yield build
    for item in rigs:
        item.manager.close()


def test_pw_e4_music_sources_json_has_exactly_two_complete_sources() -> None:
    raw = json.loads(SOURCES_PATH.read_text(encoding='utf-8'))['sources']
    assert len(raw) == 2 and sorted(item['role'] for item in raw) == ['fallback', 'primary']
    for item in raw:
        assert item['url'].startswith('https://') and item['attribution'].strip() and item['author'].strip()
        assert len(item['sha256']) == 64 and set(item['sha256']) <= set('0123456789abcdef')
        assert 'nc' not in item['license'].lower().replace('-', ' ').split()
    loaded = load_music_sources(SOURCES_PATH)
    assert [item.role for item in loaded] == ['primary', 'fallback'] and all(item.moods for item in loaded)


BAD_MUTATIONS = {
    'third_source': lambda s: s.append(dict(s[0], source_id='third')),
    'missing_author': lambda s: s[0].pop('author'),
    'nc_license': lambda s: s[0].update(license='CC BY-NC 4.0'),
    'invented_sha256': lambda s: s[0].update(sha256='abc'),
    'http_url': lambda s: s[0].update(url='http://example.test/a.wav'),
    'two_primaries': lambda s: s[1].update(role='primary'),
    'empty_attribution': lambda s: s[0].update(attribution=' '),
}


@pytest.mark.parametrize('name', sorted(BAD_MUTATIONS))
def test_pw_e4_loader_rejects_incomplete_or_noncommercial_lists(tmp_path, name) -> None:
    sources = json.loads(SOURCES_PATH.read_text(encoding='utf-8'))['sources']
    BAD_MUTATIONS[name](sources)
    path = tmp_path / 'music_sources.json'
    path.write_text(json.dumps({'sources': sources}), encoding='utf-8')
    with pytest.raises(MusicSourceError):
        load_music_sources(path)


def test_pw_e4_collects_new_music_and_records_every_provenance_field(rig_factory) -> None:
    transport = FakeTransport({PRIMARY_URL: SAMPLE})
    rig = rig_factory(transport, (make_source('primary', PRIMARY_URL, SAMPLE), make_source('fallback', FALLBACK_URL, OTHER)))
    result = rig.run('op-bed-1', request())
    assert result.receipt.disposition is Disposition.SUCCEEDED and 'AUDIO_MIX_QUALITY' not in result.receipt.warnings
    stored = rig.stored('op-bed-1')
    assert stored == result.record
    track = stored.provenance['tracks'][0]
    assert all(track[name] for name in PROVENANCE_FIELDS)
    assert track['url'] == PRIMARY_URL and track['sha256'] == sha(SAMPLE) and track['license'] == 'CC BY 4.0' and track['author'] == 'Tester'
    assert track['collected_at'] == '2026-10-27T02:00:00+00:00'
    assert stored.provenance['ai_generated'] is False and stored.risk_metadata['bed_kind'] == 'external_music'
    assert (rig.library / f'music-{sha(SAMPLE)}.audio').read_bytes() == SAMPLE
    assert transport.calls == [PRIMARY_URL]


def test_pw_e4_search_reuses_collected_music_by_mood_and_duration(rig_factory) -> None:
    transport = FakeTransport({PRIMARY_URL: SAMPLE, FALLBACK_URL: OTHER})
    rig = rig_factory(transport, (make_source('primary', PRIMARY_URL, SAMPLE), make_source('fallback', FALLBACK_URL, OTHER)))
    rig.run('op-bed-1', request(end_ms=5000))
    again = rig.run('op-bed-2', request(end_ms=6000))
    assert transport.calls == [PRIMARY_URL] and again.record.provenance['tracks'][0]['sha256'] == sha(SAMPLE)
    longer = rig.run('op-bed-3', request(end_ms=8500))
    assert longer.record.provenance['tracks'][0]['sha256'] == sha(OTHER)
    assert transport.calls == [PRIMARY_URL, PRIMARY_URL, FALLBACK_URL]
    reused = rig.run('op-bed-4', request(end_ms=8600))
    assert reused.record.provenance['tracks'][0]['sha256'] == sha(OTHER) and len(transport.calls) == 3
    tense = rig.run('op-bed-5', request(mood='tense'))
    assert tense.record.provenance['bed_kind'] == 'none' and len(transport.calls) == 3


def test_pw_e4_wrong_sha256_is_rejected_stored_nowhere_and_fallback_is_used(rig_factory, caplog) -> None:
    transport = FakeTransport({PRIMARY_URL: OTHER, FALLBACK_URL: OTHER})
    rig = rig_factory(transport, (make_source('primary', PRIMARY_URL, SAMPLE), make_source('fallback', FALLBACK_URL, OTHER)))
    with caplog.at_level(logging.WARNING, logger='voice.adapters.audio_bed_source'):
        result = rig.run('op-bed-1', request())
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert result.record.provenance['tracks'][0]['source_id'] == 'fallback-test'
    assert transport.calls == [PRIMARY_URL, FALLBACK_URL]
    assert 'music_sha256_mismatch' in caplog.text
    assert sorted(path.name for path in rig.library.glob('music-*.audio')) == [f'music-{sha(OTHER)}.audio']


@pytest.mark.parametrize('case', ['wrong_sha256', 'unreachable', 'http_500', 'redirect'])
def test_pw_e4_without_usable_music_the_bed_is_none_with_warning_and_the_chain_goes_on(rig_factory, case) -> None:
    bodies = {'wrong_sha256': {PRIMARY_URL: OTHER, FALLBACK_URL: OTHER}, 'unreachable': {}}.get(case, {PRIMARY_URL: SAMPLE, FALLBACK_URL: SAMPLE})
    transport = FakeTransport(bodies, status=500 if case == 'http_500' else 200, redirect_to='https://evil.example/x.wav' if case == 'redirect' else None)
    rig = rig_factory(transport, (make_source('primary', PRIMARY_URL, SAMPLE), make_source('fallback', FALLBACK_URL, SAMPLE)))
    result = rig.run('op-bed-none', request())
    assert result.receipt.disposition is Disposition.SUCCEEDED
    assert 'AUDIO_MIX_QUALITY' in result.receipt.warnings and 'AUDIO_MIX_QUALITY' in result.record.warnings
    stored = rig.stored('op-bed-none')
    assert stored.provenance['bed_kind'] == 'none' and stored.risk_metadata['bed_kind'] == 'none' and stored.provenance['ai_generated'] is False
    assert stored.provenance['errors']
    assert not list(rig.library.glob('music-*'))
    assert (rig.library / f'{stored.renditions[0].rendition_ref}.wav').read_bytes() == silent_wav(5000)


@pytest.mark.parametrize('url', ['https://evil.example/bed.wav', 'http://music-primary.test/bed.wav', 'https://music-primary.test/other.wav', 'https://user:pw@music-primary.test/bed.wav', 'https://127.0.0.1/bed.wav', 'https://music-primary.test:8443/bed.wav', 'file:///etc/passwd'])
def test_pw_e4_url_outside_the_pinned_list_is_blocked(url) -> None:
    sources = (make_source('primary', PRIMARY_URL, SAMPLE), make_source('fallback', FALLBACK_URL, OTHER))
    with pytest.raises(MusicSourceError) as caught:
        check_music_url(url, sources)
    assert caught.value.code == 'music_url_not_allowed'
    assert check_music_url(PRIMARY_URL, sources) is sources[0]


def test_pw_e4_module_docstring_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    line = [item for item in doc.splitlines() if item.startswith('coveredIds:')][0]
    ids = {item.strip() for item in line[len('coveredIds:'):].split(',')}
    assert {'PW-E4-01', 'FR-AUD-007', 'FR-AUD-004'} <= ids
