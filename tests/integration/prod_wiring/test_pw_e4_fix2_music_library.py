"""PW-E4-FIX2: kho nhạc nền lớn dần từ catalog đã thu (R11, FR-AUD-007) và chọn xoay vòng ổn định theo video, không còn mọi video cùng một bản.

Gọi thẳng AudioBedSource.prepare với transport giả (không mạng, không DB).

coveredIds: FR-AUD-004, FR-AUD-007
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import wave

import pytest

from voice.adapters.audio_bed_source import (
    CATALOG_RELATIVE_PATH,
    MUSIC_LIBRARY_TARGET,
    AudioBedSource,
    HttpsResponse,
    MusicSource,
    PreparedMusic,
    load_music_catalog,
    save_music_catalog,
)
from voice.domain.audio_bed import AudioBedRequest, AudioCue, LoudnessConstraints, LoudnessReport

NOW = datetime.datetime(2026, 11, 3, 2, 0, tzinfo=datetime.timezone.utc)
LIMITS = LoudnessConstraints(min_lufs=-20, max_lufs=-12, max_true_peak_dbtp=-1.0)
PRIMARY_URL = 'https://music-primary.test/bed.wav'
FALLBACK_URL = 'https://music-fallback.test/bed.wav'


def wav_bytes(duration_ms: int, tone: int = 0) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(bytes([tone % 256, 0]) * (duration_ms * 8))
    return buffer.getvalue()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source(role: str, url: str, data: bytes, moods=('calm',), source_id=None) -> MusicSource:
    return MusicSource(source_id=source_id or f'{role}-{sha(data)[:6]}', role=role, url=url, license='CC-BY-4.0', attribution='Track by Tester', author='Tester', sha256=sha(data), moods=tuple(moods))


class Transport:
    def __init__(self, bodies):
        self.bodies = dict(bodies)
        self.calls = []

    def fetch(self, url, *, max_bytes, timeout_seconds):
        self.calls.append(url)
        if url not in self.bodies:
            raise OSError('unreachable')
        return HttpsResponse(200, self.bodies[url], url)


def prepare_music(body: bytes) -> PreparedMusic:
    with wave.open(io.BytesIO(body)) as wav:
        duration = wav.getnframes() * 1000 // wav.getframerate()
    return PreparedMusic(data=body, duration_ms=duration, report=LoudnessReport(integrated_lufs=-16.0, true_peak_dbtp=-2.0))


def request(voice: str, *, end_ms: int = 5000, mood=None, cue_text: str = 'music-1') -> AudioBedRequest:
    cue = AudioCue(kind='music', start_ms=0, end_ms=end_ms, artifact_ref=cue_text, mood=mood)
    return AudioBedRequest(cues=(cue,), voice_artifact_ref=voice, preset_audio_policy_revision='audio-pol-1', loudness_constraints=LIMITS, mix_constraints={'bed_gain_db': -20}, fallback_allowed=False)


def track_sha(outcome) -> str:
    assert outcome.provenance['bed_kind'] == 'external_music', outcome.provenance
    return outcome.provenance['tracks'][0]['sha256']


@pytest.fixture
def world(tmp_path):
    library = tmp_path / 'audio_library'
    pinned_body, fallback_body = wav_bytes(60000, 1), wav_bytes(60000, 2)
    catalog_bodies = {f'https://cdn.freesound.org/previews/1/{n}_hq.mp3': wav_bytes(60000, 10 + n) for n in range(8)}
    catalog = [source('catalog', url, body, moods=('calm', 'ambient') if n % 2 == 0 else ('tense', 'dramatic'), source_id=f'freesound-{n}')
               for n, (url, body) in enumerate(catalog_bodies.items())]
    save_music_catalog(library / CATALOG_RELATIVE_PATH, catalog)
    transport = Transport({PRIMARY_URL: pinned_body, FALLBACK_URL: fallback_body, **catalog_bodies})
    pinned = (source('primary', PRIMARY_URL, pinned_body), source('fallback', FALLBACK_URL, fallback_body))
    bed = AudioBedSource(sources=pinned, library_dir=library, transport=transport, prepare_music=prepare_music, clock=lambda: NOW)
    return bed, transport, catalog, library


def test_catalog_round_trips_and_skips_bad_entries(tmp_path) -> None:
    path = tmp_path / 'catalog' / 'music_sources.json'
    good = source('catalog', 'https://cdn.freesound.org/previews/1/1_hq.mp3', b'x', source_id='freesound-1')
    save_music_catalog(path, [good])
    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['sources'] += [{**raw['sources'][0], 'license': 'CC BY-NC 4.0', 'url': 'https://cdn.freesound.org/previews/1/2_hq.mp3'}, dict(raw['sources'][0]), {'role': 'catalog'}]
    path.write_text(json.dumps(raw), encoding='utf-8')
    assert load_music_catalog(path) == (good,)
    assert load_music_catalog(tmp_path / 'missing.json') == ()
    path.write_text('{not json', encoding='utf-8')
    assert load_music_catalog(path) == ()


def test_library_grows_from_the_catalog_until_the_target(world) -> None:
    bed, transport, catalog, library = world
    used = [track_sha(bed.prepare(request(f'voice-{n}'))) for n in range(MUSIC_LIBRARY_TARGET + 4)]
    collected = sorted(path.name for path in library.glob('music-*.audio'))
    assert len(collected) == MUSIC_LIBRARY_TARGET
    assert PRIMARY_URL not in transport.calls and FALLBACK_URL not in transport.calls
    assert len(transport.calls) == MUSIC_LIBRARY_TARGET
    assert len(set(used)) >= 3


def test_same_video_gets_the_same_track_again(world) -> None:
    bed, transport, _, _ = world
    for n in range(MUSIC_LIBRARY_TARGET):
        bed.prepare(request(f'warm-{n}'))
    calls = len(transport.calls)
    first = [track_sha(bed.prepare(request(f'voice-{n}'))) for n in range(5)]
    again = [track_sha(bed.prepare(request(f'voice-{n}'))) for n in range(5)]
    assert first == again and len(transport.calls) == calls


def test_cue_text_words_steer_a_cue_without_mood(world) -> None:
    bed, _, catalog, _ = world
    tense = {item.sha256 for item in catalog if 'tense' in item.moods}
    for n in range(MUSIC_LIBRARY_TARGET):
        bed.prepare(request(f'warm-{n}'))
    picked = {track_sha(bed.prepare(request(f'voice-{n}', cue_text='slow tense build under the reveal'))) for n in range(6)}
    assert picked and picked <= tense


def test_explicit_mood_stays_strict(world) -> None:
    bed, _, catalog, _ = world
    calm = {item.sha256 for item in catalog if 'calm' in item.moods} | {sha(wav_bytes(60000, 1)), sha(wav_bytes(60000, 2))}
    picked = {track_sha(bed.prepare(request(f'voice-{n}', mood='calm'))) for n in range(6)}
    assert picked <= calm
    none = bed.prepare(request('voice-x', mood='joyful'))
    assert none.provenance['bed_kind'] == 'none'


def test_without_catalog_the_pinned_sources_behave_as_before(tmp_path) -> None:
    body = wav_bytes(60000, 1)
    transport = Transport({PRIMARY_URL: body})
    bed = AudioBedSource(sources=(source('primary', PRIMARY_URL, body), source('fallback', FALLBACK_URL, wav_bytes(60000, 2))), library_dir=tmp_path / 'lib', transport=transport, prepare_music=prepare_music, clock=lambda: NOW)
    assert track_sha(bed.prepare(request('voice-1', mood='calm'))) == sha(body)
    assert track_sha(bed.prepare(request('voice-2', mood='calm'))) == sha(body)
    assert transport.calls == [PRIMARY_URL]


def test_a_failing_catalog_source_falls_back_to_the_library(world) -> None:
    bed, transport, catalog, _ = world
    first = track_sha(bed.prepare(request('voice-0')))
    transport.bodies = {}
    again = track_sha(bed.prepare(request('voice-1')))
    assert again == first and len(transport.calls) == 1 + 2
