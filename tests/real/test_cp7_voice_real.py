"""CP7-6 / RG-05: TTS Kokoro và aligner faster-whisper thật; đo WAV, từ không khớp, mốc câu, tốc độ nói, VRAM."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import cp7_common as c  # noqa: E402
from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts  # noqa: E402
from voice.adapters.real_whisper_aligner import RealWhisperAligner, WhisperAlignerConfig  # noqa: E402
from voice.domain.timing_coverage import TokenizationPolicy  # noqa: E402
from voice.domain.tts_invocation import ProviderRouteDecision  # noqa: E402
from voice.ports.aligner import AlignerError, AlignmentRequest  # noqa: E402
from voice.ports.script_text import ScriptText  # noqa: E402

LOCK = REPO / 'tools' / 'launcher' / 'prod' / 'model-weights.lock.json'
PROFILE = REPO / 'tools' / 'launcher' / 'prod' / 'profile.json'
RUNTIME_LOCK = REPO / 'tools' / 'runtime' / 'runtime.lock.json'
REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-6' / 'report.md'
FFMPEG_EXE = Path('C:/ffmpeg/bin/ffmpeg.exe')
DEADLINE = c.Deadline(90 * 60)
GPU_MAX_SECONDS = 60 * 60
VRAM_MAX_MIB = 11 * 1024
MUSIC_DB = -20.0
SFX_DB = -12.0
MIN_PASSAGE_OK = 0.95
MIN_SENTENCE_OK = 0.95
MIN_RATE_OK = 0.90
RATE_TOLERANCE = 0.10


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _profile_value(*keys):
    node = _json(PROFILE)
    for key in keys:
        node = node[key]
    return node['value']


def _data_root():
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _in_git_tree(path):
    resolved = path.resolve()
    return any((p / '.git').exists() for p in (resolved, *resolved.parents))


def _find_dir(root, names):
    for directory in [root, *sorted(p for p in root.iterdir() if p.is_dir())]:
        if all((directory / name).is_file() for name in names):
            return directory
    pytest.fail(f'no directory under {root} holds {names}')


POLICY = TokenizationPolicy(revision='cp7-6-real-1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)
DECISION = ProviderRouteDecision(provider_ref='kokoro-local', model_ref='kokoro-v1.0', account_ref='local', route_revision='cp7-6', rationale_codes=('LOCAL',), fallback_order=(), capacity_reservation_ref='cp7-6-res', credential_acquisition_method='none', estimated_cost_class='free')

DIALOGUES = (
    'Local municipal officials inaugurated a modern solar charging pavilion near the central railway station. Commuters recharged their electric scooters while waiting for morning trains.',
    'Experienced maritime captains guided cargo vessels into the deep water harbor yesterday morning. Dock workers unloaded shipping containers under mild sunny skies.',
    'Talented student musicians rehearsed classical symphonies inside the community concert hall this afternoon. Proud parents applauded the harmonious orchestral performance warmly.',
    'Skilled restoration carpenters repaired historic wooden storefronts throughout the heritage market district. Local merchants praised the preservation effort and welcomed visiting tourists.',
    'Community volunteers planted dozens of native flowering trees around the school playground. Neighborhood children gathered every afternoon to water the new botanical garden.',
    'A modern regional environmental science museum opened near the tranquil river yesterday morning. Families gathered to explore interactive ecological exhibits and enjoy the educational discovery pavilions.',
    'Solar panels installed on school rooftops generate clean renewable electricity throughout the entire year. The district expects substantial savings while teaching students about modern sustainable energy.',
    'The annual science fair attracted young inventors from several regional schools. Visitors admired creative projects focused on clean water systems and automated robotic arms for daily tasks.',
    'Engineers completed the inspection of the historic suspension bridge today. Traffic resumed normally after technicians confirmed that the steel cables and foundation remained in perfect condition.',
    'The neighborhood community garden produced an abundant harvest of fragrant herbs and ripe seasonal vegetables. Dedicated volunteers delivered fresh produce parcels to regional community dining centers.',
    'Scientists observed thousands of migrating birds resting along the southern coastline during their seasonal journey. The protected wetland reserve provides essential food and shelter before the large flocks continue flying across the open ocean. Dedicated conservation teams monitor water quality and bird health every single week.',
    'The regional museum launched an interactive exhibition showcasing several centuries of traditional maritime history. Visitors can examine detailed wooden ship models and read authentic navigational charts used by ancient explorers. Knowledgeable museum guides explain how brave sailors navigated rough seas using the stars and simple compass instruments.',
    'City planners presented an ambitious and comprehensive proposal to expand bicycle lanes across downtown districts. The multiyear project aims to reduce vehicle traffic congestion and encourage healthier commuting habits among urban residents. Construction begins next spring and will add shaded resting areas along major commercial avenues.',
    'Astronomers gathered at the remote mountain observatory to witness a rare planetary alignment this evening. Clear night skies and low atmospheric humidity provided optimal conditions for recording high resolution digital images. Leading researchers will share their detailed telescopic observations with educational institutions and international universities around the world.',
    'A dedicated group of university engineering students developed an autonomous solar powered water filtration device. The compact machine removes hazardous impurities and provides safe drinking water for remote off grid villages. Extended field trials demonstrated outstanding efficiency under intense tropical heat and rapidly varying river water conditions.',
    'Agricultural experts introduced drought resistant wheat varieties to support farming communities facing warmer climates. These crops require significantly less irrigation while producing stable yields across diverse soil types. Farmers reported promising initial harvests and expressed confidence in sustainable food production for the upcoming seasons as regional weather patterns become more unpredictable.',
    'Local authorities announced the completion of an underground storm water management tunnel beneath the urban center. The massive infrastructure project diverts excess rainfall away from residential streets during severe tropical storms. Urban hydrologists confirmed that the system performed exceptionally well during recent heavy downpours and prevented localized flooding across vulnerable low lying neighborhoods.',
    'An international botanical team discovered three previously undocumented orchid species hidden within a remote mountain valley. The delicate flowers thrive on mossy limestone cliffs where constant mist provides essential moisture. Conservationists are now working with local rangers to establish a protected ecological zone and prevent illegal harvesting by commercial plant collectors.',
    'Medical researchers published encouraging results from a long term study on the benefits of regular brisk walking. Participants who walked thirty minutes every morning showed significant improvements in cardiovascular stamina and sleep quality. Health organizations recommend incorporating simple outdoor exercise into daily routines to maintain long term physical and mental wellbeing.',
    'Marine biologists tracked a pod of humpback whales migrating along the continental shelf toward tropical breeding grounds. Acoustic sensors deployed across the bay recorded complex vocalizations exchanged between mothers and calves. Researchers hope these detailed audio recordings will help clarify social communication patterns and navigation methods used across long ocean journeys.',
)
SCRIPTS = (
    'The global transition toward renewable energy accelerated significantly during the past decade. Solar and wind installations now generate a substantial portion of worldwide electricity demand. Technological breakthroughs in battery storage allow clean energy to power cities during peak hours. Engineers design advanced power grids that automatically balance supply and demand across vast regions. Government policies and industrial investments further stimulate innovation in sustainable energy sectors. Electric vehicles become increasingly common on city streets and reduce urban carbon emissions. Public transit systems adopt hydrogen buses to deliver clean transportation for growing populations. Research institutions explore geothermal power sources to provide reliable base load energy. Communities embrace decentralized microgrids to protect essential services from extreme weather disruptions. International cooperation remains vital for sharing clean technologies with emerging economic markets. Modern manufacturing facilities rely on automated recycling systems to recover precious rare earth metals. Future projections suggest that renewable power will dominate the global landscape within two decades.',
    'Oceanographic expeditions continue to reveal fascinating secrets hidden beneath the deep ocean waves. Unmanned submersibles descend thousands of meters to explore underwater volcanic ridges and trenches. Scientists discover specialized organisms that flourish without sunlight near boiling hydrothermal vents. These unique creatures utilize chemical energy rather than solar light to sustain biological life. Advanced sonar mapping produces highly detailed digital models of the complex seafloor topography. Marine geologists analyze rock samples to understand tectonic plate movements and seismic activity. Autonomous research floats drift across remote ocean basins collecting continuous water quality data. Climate scientists examine temperature and salinity measurements to track changing global circulation patterns. Marine conservation organizations work tirelessly to establish protected wildlife corridors across the open sea. International agreements aim to safeguard fragile deep sea ecosystems from industrial mining activities. Biochemists study unique marine compounds that could lead to revolutionary medical treatments and antibiotics. Preserving ocean biodiversity ensures that marine life continues to support planetary health for generations.',
    'Space exploration agencies prepare ambitious missions to study the moon and distant planetary bodies. Robotic rovers traverse rocky Martian terrain searching for evidence of ancient microbial life forms. Automated drilling instruments extract soil samples and analyze mineral compositions beneath the dusty surface. Orbital satellites transmit high resolution photographs capturing dramatic canyon walls and frozen polar caps. Engineers construct next generation space telescopes capable of detecting atmospheres around distant exoplanets. Astronomers analyze starlight filtering through alien clouds to search for potential atmospheric biosignatures. International teams collaborate to design habitable lunar stations for long duration scientific research missions. Astronauts will test closed loop life support systems and extract water ice from shadowed polar craters. Aerospace engineers invent lightweight thermal shields to protect exploration spacecraft during rapid atmospheric reentry. Deep space communication networks maintain constant data links with robotic explorers across the solar system. Mission planners schedule robotic probe flybys to study icy moons orbiting giant gas planets. These cooperative space missions expand human understanding and inspire the next generation of scientists.',
    'Modern agricultural practices adapt rapidly to address environmental challenges and feed growing populations. Precision farming technologies utilize satellite imagery and drones to monitor crop health across vast fields. Automated sensors measure soil moisture and deliver water directly to plant roots when necessary. This targeted irrigation strategy conserves precious water supplies while increasing overall harvest yields. Agricultural scientists develop natural pest management methods to reduce reliance on chemical insecticides. Beneficial insects and companion planting create balanced ecosystems that protect commercial food crops. Vertical farming facilities located inside urban centers produce fresh greens using specialized lighting. These indoor farms consume minimal water and eliminate the need for long distance food transportation. Robotic harvesting machines gently collect ripe fruit without damaging delicate tree branches or leaves. Soil scientists encourage regenerative planting techniques to restore organic matter and beneficial microbial activity. Sustainable farming techniques ensure food security while preserving vital soil health for the future. Consumers increasingly support local growers who prioritize environmental stewardship and ethical farming.',
    'Urban forestry programs transform concrete city landscapes into vibrant green and healthy environments. Municipal authorities plant thousands of native shade trees along major streets and residential avenues. These mature tree canopies significantly lower summer air temperatures by providing natural cooling shade. Foliage also absorbs air pollutants and filters airborne dust particles to improve neighborhood breathing air. City parks serve as welcoming social hubs where residents gather for recreation and relaxation. Community volunteers plant pollinator gardens filled with native wildflowers to support honeybees and butterflies. Engineers integrate green rooftops and permeable pavements into new architectural construction guidelines. These ecological designs reduce stormwater runoff and prevent severe urban flooding during sudden cloudbursts. Landscape architects preserve historic wooded groves to provide natural sanctuary within busy metropolitan sectors. Civic leaders fund botanical education centers to teach neighborhood youth about environmental conservation principles. Ecologists observe that urban green corridors allow songbirds and small wildlife to navigate the city. Investing in urban nature creates resilient cities that promote human wellness and ecological balance.',
)
ITEMS = tuple(('dialogue', t) for t in DIALOGUES) + tuple(('script', t) for t in SCRIPTS)


def _sentences(text):
    return re.findall(r'[^.]+[.]', text)


assert len(DIALOGUES) == 20 and len(SCRIPTS) == 5
assert all(15 <= len(t.split()) <= 60 for t in DIALOGUES)
assert all(150 <= len(t.split()) <= 190 for t in SCRIPTS)
assert len({t for _, t in ITEMS}) == 25
for _, _text in ITEMS:
    assert re.fullmatch(r'[A-Za-z .]+', _text) and ''.join(_sentences(_text)) == _text


@pytest.fixture(scope='module')
def weights():
    lock = _json(LOCK)
    entries = lock['files']
    assert lock['storage']['in_git'] is False and len(entries) >= 6
    for entry in entries:
        name = entry['name']
        assert entry['status'] == 'PINNED', f'{name} not PINNED'
        assert re.fullmatch(r'[0-9a-f]{64}', str(entry['sha256'])), f'{name} sha256 invalid'
        assert '<commit>' not in entry['url'], f'{name} url has no pinned commit'
    root = _data_root() / lock['storage']['subdir']
    assert root.is_dir(), 'models directory missing'
    resolved = root.resolve()
    assert not _in_git_tree(resolved) and resolved != REPO and REPO not in resolved.parents, 'weights inside Git tree'
    groups = {}
    for entry in entries:
        groups.setdefault(entry['group'], []).append(entry['name'])
    directories = {group: _find_dir(root, names) for group, names in groups.items()}
    details = []
    for entry in entries:
        name = entry['name']
        actual = _sha256(directories[entry['group']] / name)
        assert actual == entry['sha256'], f'sha256 mismatch for {name}'
        details.append(f'{name} sha256={actual} group={entry["group"]}')
    return SimpleNamespace(kokoro_dir=directories['kokoro-onnx'], whisper_dir=directories['faster-whisper-small.en'], details=details)


def _wav_info(data):
    with wave.open(BytesIO(data), 'rb') as wav:
        return wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes(), wav.readframes(wav.getnframes())


def _samples(data):
    return np.frombuffer(_wav_info(data)[4], dtype='<i2').astype(np.float64) / 32768.0


def _rms(x):
    return float(np.sqrt(np.mean(np.square(x))))


def _write_wav(path, samples, rate):
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype('<i2').tobytes()
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return path.read_bytes()


def _mix(voice, rate):
    t = np.arange(voice.size) / rate
    music = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.18, 329.63)) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t))
    music = music * (_rms(voice) * 10 ** (MUSIC_DB / 20) / _rms(music))
    length = int(0.12 * rate)
    burst = np.random.default_rng(7).standard_normal(length) * np.hanning(length)
    burst = burst * (_rms(voice) * 10 ** (SFX_DB / 20) / _rms(burst))
    sfx = np.zeros_like(voice)
    for fraction in (0.25, 0.55, 0.85):
        begin = int(fraction * voice.size)
        piece = sfx[begin:begin + length]
        piece += burst[:piece.size]
    mixed = voice + music + sfx
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.99:
        mixed = mixed * (0.99 / peak)
    return mixed, 20 * math.log10(_rms(music) / _rms(voice))


REFERENCE_NOISE_DB = -30
SENSITIVITY_NOISE_DB = (-40, -35, -30)
REFERENCE_MIN_SILENCE_S = 0.1
END_MARGIN_MS = 50
CUT_WINDOW_FRACTION = 0.35
CUT_WINDOW_MIN_MS = 1000


def _silences(wav_path, duration_ms, noise_db):
    # silencedetect của FFmpeg ghim chạy trên giọng sạch; trả danh sách (bắt đầu ms, kết thúc ms) các khoảng im
    proc = subprocess.run([str(FFMPEG_EXE), '-hide_banner', '-nostats', '-i', str(wav_path), '-af', f'silencedetect=noise={noise_db}dB:d={REFERENCE_MIN_SILENCE_S}', '-f', 'null', '-'], capture_output=True, text=True, timeout=DEADLINE.timeout(120), check=False)
    assert proc.returncode == 0, 'ffmpeg silencedetect failed'
    silences, start = [], None
    for line in proc.stderr.splitlines():
        found = re.search(r'silence_start: (-?[0-9.]+)', line)
        if found:
            start = max(0, int(round(float(found.group(1)) * 1000)))
            continue
        found = re.search(r'silence_end: ([0-9.]+)', line)
        if found and start is not None:
            silences.append((start, int(round(float(found.group(1)) * 1000))))
            start = None
    if start is not None:
        silences.append((start, duration_ms))
    return silences


def _sentence_spans(wav_path, duration_ms, sentences, noise_db):
    # mốc câu tham chiếu chỉ lấy từ giọng sạch và độ dài văn bản, độc lập aligner: đầu câu đầu = hết khoảng im đầu file, cuối câu cuối = bắt đầu khoảng im cuối file; mỗi ranh giới câu là khoảng im DÀI NHẤT nằm trong cửa sổ quanh vị trí kỳ vọng (thời gian còn lại chia theo tỉ lệ số ký tự các câu còn lại, tính lại sau mỗi lần cắt) nên chỗ nghỉ hơi giữa câu ở xa vị trí đó không lẫn với ranh giới thật
    silences = _silences(wav_path, duration_ms, noise_db)
    begin = silences[0][1] if silences and silences[0][0] <= 0 else 0
    finish = silences[-1][0] if silences and silences[-1][0] > begin and silences[-1][1] >= duration_ms - END_MARGIN_MS else duration_ms
    inner = [s for s in silences if s[0] > begin and s[1] < finish]
    lengths = [len(sentence) for sentence in sentences]
    picked, cursor, remaining = [], begin, sum(lengths)
    for length in lengths[:-1]:
        expected = cursor + (finish - cursor) * length / remaining
        window = max(CUT_WINDOW_MIN_MS, CUT_WINDOW_FRACTION * (expected - cursor))
        ahead = [s for s in inner if s[0] > cursor]
        pool = [s for s in ahead if abs(s[0] - expected) <= window]
        if pool:
            cut = max(pool, key=lambda s: (s[1] - s[0], -abs(s[0] - expected)))
        elif ahead:
            cut = min(ahead, key=lambda s: abs(s[0] - expected))
        else:
            break
        picked.append(cut)
        cursor = cut[1]
        remaining -= length
    spans, start = [], begin
    for cut in picked:
        spans.append((start, cut[0]))
        start = cut[1]
    spans.append((start, finish))
    rest = [s[1] - s[0] for s in inner if s not in picked]
    return spans, (min((s[1] - s[0] for s in picked), default=0), max(rest, default=0))


class _VramSampler(threading.Thread):
    # lấy mẫu nvidia-smi memory.used mỗi giây suốt lượt đo; lỗi nvidia-smi được ghi lại, không bị nuốt
    def __init__(self):
        super().__init__(daemon=True)
        self.samples = []
        self.error = None
        self._halt = threading.Event()

    def run(self):
        while True:
            try:
                proc = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10, check=False)
                if proc.returncode != 0:
                    raise RuntimeError('nvidia-smi exit ' + str(proc.returncode))
                self.samples.append(max(int(token) for token in proc.stdout.split()))
            except Exception as exc:
                self.error = exc
                return
            if self._halt.wait(1.0):
                return

    def finish(self):
        self._halt.set()
        self.join(15)


def _sentence_outcomes(sentences, result, report, spans):
    # (lệch đầu ms, lệch cuối ms) CÓ DẤU = mốc aligner trừ mốc silencedetect; số khoảng nói bằng số câu thì ghép theo thứ tự câu, ngược lại chọn khoảng trùng nhiều nhất; (None, None) = câu hỏng
    missing = set(report.missing_script_indices)
    matched = [i for i in range(report.script_token_count) if i not in missing]
    assert len(matched) == len(result.words), 'matched token count differs from aligned words'
    by_token = dict(zip(matched, result.words))
    paired = len(spans) == len(sentences)
    outcomes, cursor = [], 0
    for index, sentence in enumerate(sentences):
        count = len(sentence.split())
        words = [by_token[i] for i in range(cursor, cursor + count) if i in by_token]
        cursor += count
        if not words:
            outcomes.append((None, None))
            continue
        start, end = words[0]['start_ms'], words[-1]['end_ms']
        if paired:
            best = spans[index]
        else:
            best = max(spans, key=lambda s: min(s[1], end) - max(s[0], start), default=None)
            if best is not None and min(best[1], end) - max(best[0], start) <= 0:
                best = None
        if best is None:
            outcomes.append((None, None))
        else:
            outcomes.append((start - best[0], end - best[1]))
    return outcomes


def _measure_item(tts, aligner, paths, work, sid, kind, text, rate_hz):
    fingerprint = hashlib.sha256(text.encode('utf-8')).hexdigest()
    request = {'script_version_id': sid, 'script_fingerprint': fingerprint, 'voice_profile_ref': 'cp7-6-voice', 'provider_route_ref': 'cp7-6-route', 'expected_language': 'en-US', 'operation_key': 'cp7-6-' + sid, 'execution_grant_ref': 'cp7-6-grant'}
    synthesis = tts.synthesize(DECISION, ScriptText(sid, text, fingerprint), request)
    data = synthesis.audio_bytes
    channels, width, rate, frames, _ = _wav_info(data)
    clean = _samples(data)
    duration_ms = frames * 1000 // rate
    clean_path = work / (sid + '-clean.wav')
    clean_path.write_bytes(data)
    sentences = _sentences(text)
    refs = {db: _sentence_spans(clean_path, duration_ms, sentences, db) for db in SENSITIVITY_NOISE_DB}
    spans, margin = refs[REFERENCE_NOISE_DB]
    mixed, music_db = _mix(clean, rate)
    assert abs(music_db - MUSIC_DB) < 0.1, 'music level off target'
    paths[sid] = work / (sid + '-mix.wav')
    mix_bytes = _write_wav(paths[sid], mixed, rate)
    aligner.last_report = None
    result, error = None, None
    try:
        result = aligner.align(AlignmentRequest(voice_artifact_ref=sid, voice_hash=hashlib.sha256(mix_bytes).hexdigest(), voice_duration_ms=duration_ms, script_version_id=sid, script_text=text, expected_language='en-US'))
    except AlignerError as exc:
        error = exc.code
    report = aligner.last_report
    if result is not None and report is not None:
        ratio = report.unmatched_ratio
        by_noise = {db: _sentence_outcomes(sentences, result, report, ref[0]) for db, ref in refs.items()}
    else:
        ratio, by_noise = 1.0, {db: [(None, None)] * len(sentences) for db in refs}
    paths[sid + '-clean'] = clean_path
    clean_outcomes = [(None, None)] * len(sentences)
    aligner.last_report = None
    try:
        clean_result = aligner.align(AlignmentRequest(voice_artifact_ref=sid + '-clean', voice_hash=hashlib.sha256(data).hexdigest(), voice_duration_ms=duration_ms, script_version_id=sid, script_text=text, expected_language='en-US'))
    except AlignerError:
        clean_result = None
    if clean_result is not None and aligner.last_report is not None:
        clean_outcomes = _sentence_outcomes(sentences, clean_result, aligner.last_report, spans)
    valid = channels == 1 and width == 2 and rate == rate_hz and frames > 0 and float(np.max(np.abs(clean))) > 0.01
    return SimpleNamespace(sid=sid, kind=kind, words=len(text.split()), duration_ms=duration_ms, valid=valid, latency_ms=synthesis.latency_ms, ratio=ratio, error=error, outcomes=by_noise[REFERENCE_NOISE_DB], spans=len(spans), sentences=len(sentences), margin=margin, sensitivity=by_noise, clean_outcomes=clean_outcomes, rms_db=20 * math.log10(_rms(clean)))


@pytest.fixture(scope='module')
def measurement(weights, tmp_path_factory):
    assert FFMPEG_EXE.is_file(), 'pinned ffmpeg missing'
    ffmpeg_sha = _sha256(FFMPEG_EXE)
    assert ffmpeg_sha == _json(RUNTIME_LOCK)['pins']['ffmpeg']['sha256'], 'ffmpeg differs from pin'
    voice = _profile_value('voice', 'engine')
    engine = _profile_value('aligner', 'engine')
    work = tmp_path_factory.mktemp('cp7_voice')
    staging = work / 'staging'
    staging.mkdir()
    rate_hz = voice['output']['sample_rate_hz']
    tts = RealKokoroTts(KokoroConfig(weights_dir=weights.kokoro_dir, lock_path=LOCK, staging_dir=staging, voice=voice['voice'], speed=voice['speed'], language=voice['lang'], sample_rate=rate_hz))
    paths = {}
    aligner = RealWhisperAligner(WhisperAlignerConfig(model_dir=weights.whisper_dir, lock_path=LOCK, resolve_audio=lambda ref: paths[ref], tokenization_policy=POLICY, max_unmatched_word_ratio=1.0, language=engine['language'], device=engine['device'], compute_type=engine['compute_type']))
    items = []
    sampler = _VramSampler()
    started = time.monotonic()
    sampler.start()
    try:
        for index, (kind, text) in enumerate(ITEMS):
            DEADLINE.check()
            items.append(_measure_item(tts, aligner, paths, work, f'{kind}-{index:02d}', kind, text, rate_hz))
    finally:
        sampler.finish()
    return SimpleNamespace(items=items, vram=sampler.samples, vram_error=sampler.error, elapsed=time.monotonic() - started, rate_hz=rate_hz, voice=voice['voice'], speed=voice['speed'], device=engine['device'], tolerance_ms=_profile_value('aligner', 'word_timing_tolerance_ms'), ratio_cap=_profile_value('aligner', 'max_unmatched_word_ratio'), profile_wpm=_profile_value('voice', 'speech_rate_wpm'), av_version=importlib.metadata.version('av'), ffmpeg_sha=ffmpeg_sha)


def test_rg05_weights_pinned(weights, emit):
    emit(c.report_line('RG-05', 'weights_pinned', 'PASS'))
    for line in weights.details:
        emit('- weights_pinned: ' + line)


def test_rg05_tts_valid_wav(measurement, emit):
    items = measurement.items
    assert sum(1 for i in items if i.kind == 'dialogue') == 20 and sum(1 for i in items if i.kind == 'script') == 5
    invalid = [i.sid for i in items if not i.valid]
    assert not invalid, f'invalid WAV: {invalid}'
    emit(c.report_line('RG-05', 'tts_valid_wav', 'PASS'))
    emit(f'- tts_valid_wav: valid={len(items)}/{len(items)} format={measurement.rate_hz}Hz mono 16-bit voice={measurement.voice} speed={measurement.speed}')
    emit('- tts_valid_wav: words_and_actual_duration_ms=' + json.dumps({i.sid: [i.words, i.duration_ms] for i in items}))
    emit(f'- tts_valid_wav: synth_latency_ms_max={max(i.latency_ms for i in items)} total_audio_s={sum(i.duration_ms for i in items) / 1000:.1f}')


def test_rg05_aligner_unmatched(measurement, emit):
    items = measurement.items
    assert not [i.sid for i in items if i.error == 'aligner_runtime_error'], 'aligner runtime error: production decode path failed'
    ok = [i for i in items if i.error is None and i.ratio <= measurement.ratio_cap]
    assert len(ok) / len(items) >= MIN_PASSAGE_OK, f'unmatched ratio ok only {len(ok)}/{len(items)}'
    emit(c.report_line('RG-05', 'aligner_unmatched', 'PASS'))
    emit(f'- aligner_unmatched: passages_ok={len(ok)}/{len(items)} cap={measurement.ratio_cap} max_ratio={max(i.ratio for i in items):.4f} aligner_errors={[i.sid for i in items if i.error]}')
    emit('- aligner_unmatched: ratio_by_passage=' + json.dumps({i.sid: round(i.ratio, 4) for i in items}))
    emit(f'- aligner_unmatched: audio=voice + music {MUSIC_DB} dB + 3 SFX at {SFX_DB} dB; aligner device={measurement.device}')
    emit(f'- aligner_unmatched: model=real faster-whisper small.en weights pinned; audio decoded by the production path (faster_whisper.decode_audio inside RealWhisperAligner, no test-side decode) with av=={measurement.av_version}; adapter unchanged')


def _percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))] if ordered else None


def test_rg05_aligner_timing(measurement, emit):
    items = measurement.items
    tolerance = measurement.tolerance_ms
    deltas = [outcome for i in items for outcome in i.outcomes]
    scored = [d for d in deltas if d[0] is not None]
    quantiles = (0.1, 0.5, 0.9)
    emit('- aligner_timing: diag signed start_delta_ms p10/p50/p90=' + '/'.join(str(_percentile([d[0] for d in scored], q)) for q in quantiles) + ' end_delta_ms p10/p50/p90=' + '/'.join(str(_percentile([d[1] for d in scored], q)) for q in quantiles) + f' scored={len(scored)}/{len(deltas)}')
    emit('- aligner_timing: diag spans_sentences_margin_ms_by_passage=' + json.dumps({i.sid: [i.spans, i.sentences, list(i.margin)] for i in items}))
    emit('- aligner_timing: diag deltas_ms_by_passage=' + json.dumps({i.sid: i.outcomes for i in items}))
    sensitivity = {str(db): sum(1 for i in items for d in i.sensitivity[db] if d[0] is not None and abs(d[0]) <= tolerance and abs(d[1]) <= tolerance) for db in SENSITIVITY_NOISE_DB}
    emit('- aligner_timing: diag sentences_ok_by_reference_noise_db=' + json.dumps(sensitivity) + f' primary_db={REFERENCE_NOISE_DB} total={len(deltas)}')
    emit(f'- aligner_timing: diag clean_voice_rms_dbfs_median={sorted(i.rms_db for i in items)[len(items) // 2]:.1f}')
    clean_ok = sum(1 for i in items for d in i.clean_outcomes if d[0] is not None and abs(d[0]) <= tolerance and abs(d[1]) <= tolerance)
    emit(f'- aligner_timing: diag clean_voice_sentences_ok={clean_ok}/{len(deltas)} (same aligner and same reference on the voice without music and SFX; diagnostic only, not the verdict)')
    gaps = [(a[1] + b[0]) / 2 for i in items for a, b in zip(i.outcomes, i.outcomes[1:]) if a[1] is not None and b[0] is not None]
    emit(f'- aligner_timing: diag gap_midpoint_within_tolerance={sum(1 for g in gaps if abs(g) <= tolerance)}/{len(gaps)} (mean of end delta of sentence n and start delta of sentence n+1; diagnostic only, not the verdict)')
    ok = [d for d in deltas if d[0] is not None and abs(d[0]) <= tolerance and abs(d[1]) <= tolerance]
    assert len(ok) / len(deltas) >= MIN_SENTENCE_OK, f'sentence timing ok only {len(ok)}/{len(deltas)}'
    measured = sorted(max(abs(d[0]), abs(d[1])) for d in scored)
    emit(c.report_line('RG-05', 'aligner_timing', 'PASS'))
    emit(f'- aligner_timing: sentences_ok={len(ok)}/{len(deltas)} tolerance_ms={tolerance} max_delta_ms={measured[-1]} median_delta_ms={measured[len(measured) // 2]}')
    emit(f'- aligner_timing: reference=ffmpeg silencedetect on clean voice noise={REFERENCE_NOISE_DB}dB d={REFERENCE_MIN_SILENCE_S}s, each sentence cut = longest inner silence within +-{CUT_WINDOW_FRACTION} of the text-length-proportional expected position (min window {CUT_WINDOW_MIN_MS} ms, re-estimated after each cut); ffmpeg_sha256={measurement.ffmpeg_sha}; passages_with_fewer_spans_than_sentences={[i.sid for i in items if i.spans != i.sentences]}')


def test_rg05_speech_rate_calibrated(measurement, emit):
    items = measurement.items

    def wpm_of(group):
        return int(round(sum(i.words for i in group) / (sum(i.duration_ms for i in group) / 60000)))

    def deviation(item, wpm):
        return abs(item.words / wpm * 60000 - item.duration_ms) / item.duration_ms

    suggested = wpm_of(items)
    within = sum(1 for i in items if deviation(i, suggested) <= RATE_TOLERANCE)
    assert within / len(items) >= MIN_RATE_OK, f'speech rate within 10 percent only {within}/{len(items)} at wpm={suggested}'
    dialogues = [i for i in items if i.kind == 'dialogue']
    scripts = [i for i in items if i.kind == 'script']
    held = wpm_of(dialogues)
    held_ok = sum(1 for i in scripts if deviation(i, held) <= RATE_TOLERANCE)
    base = measurement.profile_wpm
    base_ok = sum(1 for i in items if deviation(i, base) <= RATE_TOLERANCE)
    emit(c.report_line('RG-05', 'speech_rate_calibrated', 'PASS'))
    emit(f'- speech_rate_calibrated: suggested_speech_rate_wpm={suggested} within_10pct={within}/{len(items)} max_deviation={max(deviation(i, suggested) for i in items):.3f}')
    emit(f'- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm={held} scripts_within_10pct={held_ok}/{len(scripts)}')
    emit(f'- speech_rate_calibrated: profile_wpm={base} within_10pct={base_ok}/{len(items)} (before calibration; profile not modified)')


def test_rg05_vram_peak(measurement, emit):
    samples = measurement.vram
    assert measurement.vram_error is None, f'nvidia-smi sampling failed: {measurement.vram_error}'
    assert len(samples) >= max(10, int(measurement.elapsed / 2)), 'too few per-second VRAM samples'
    peak = max(samples)
    assert peak <= VRAM_MAX_MIB, f'VRAM peak {peak} MiB above {VRAM_MAX_MIB} MiB'
    assert measurement.elapsed <= GPU_MAX_SECONDS, 'run exceeded 60 minutes'
    emit(c.report_line('RG-05', 'vram_peak', 'PASS'))
    emit(f'- vram_peak: peak_mib={peak} limit_mib={VRAM_MAX_MIB} samples={len(samples)} interval=1s first_mib={samples[0]} elapsed_s={measurement.elapsed:.0f}')
    emit(f'- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device={measurement.device}')


def test_rg05_secret_scan(measurement, emit):
    report = REPORT.read_text(encoding='utf-8') if REPORT.is_file() else ''
    corpus = chr(10).join(text for _, text in ITEMS)
    for label, text in (('report', report), ('test', Path(__file__).read_text(encoding='utf-8')), ('corpus', corpus)):
        assert c.scan_secrets(text) == [], f'secret pattern in {label}'
    emit(c.report_line('RG-05', 'secret_scan', 'PASS'))
    emit('- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)')
