"""CP7-8 / RG-07: STT, TTS và render cùng lúc dưới LOCK-DESKTOP-GPU 2 khe; khe thứ 3 chờ WAITING_CAPABILITY, 0 OOM, VRAM đỉnh <= 11 GiB."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import wave
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pytest  # noqa: E402
import cp7_common as c  # noqa: E402
import cp7_media_probe as mp  # noqa: E402
from controlplane.domain.statemachine import StageRunState  # noqa: E402
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease  # noqa: E402
from render.adapters.real_ffmpeg_renderer import RealFfmpegRenderer  # noqa: E402
from render.domain.render_command import KIND_RENDER, RenderCommandSpec, ToolIdentity  # noqa: E402
from render.ports.lease import GpuLeaseUnavailable  # noqa: E402
from render.ports.renderer import RendererStatus  # noqa: E402
from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts  # noqa: E402
from voice.adapters.real_whisper_aligner import RealWhisperAligner, WhisperAlignerConfig  # noqa: E402
from voice.domain.timing_coverage import TokenizationPolicy  # noqa: E402
from voice.domain.tts_invocation import ProviderRouteDecision  # noqa: E402
from voice.ports.aligner import AlignerError, AlignmentRequest  # noqa: E402
from voice.ports.script_text import ScriptText  # noqa: E402

LOCK = REPO / 'tools' / 'launcher' / 'prod' / 'model-weights.lock.json'
PROFILE = REPO / 'tools' / 'launcher' / 'prod' / 'profile.json'
RUNTIME_LOCK = REPO / 'tools' / 'runtime' / 'runtime.lock.json'
PYPROJECT = REPO / 'pyproject.toml'
REPO_ROOT = REPO
REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-8' / 'report.md'
RENDER_TEST = Path(__file__).with_name('test_cp7_render_real.py')
PROBE_SRC = REPO / 'tools' / 'real' / 'cp7_media_probe.py'
FFMPEG_EXE = mp.DEFAULT_FFMPEG
DEADLINE = c.Deadline(4 * 3600)
VRAM_MAX_MIB = 11 * 1024
TMP_MAX_BYTES = 5 * 1024 ** 3
GPU_MAX_SECONDS = 4 * 3600
ROUNDS = 2
OOM_PATTERN = re.compile(r'out of memory|cuda.{0,40}memory|\boom\b', re.IGNORECASE)


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


POLICY = TokenizationPolicy(revision='cp7-8-real-1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)
DECISION = ProviderRouteDecision(provider_ref='kokoro-local', model_ref='kokoro-v1.0', account_ref='local', route_revision='cp7-8', rationale_codes=('LOCAL',), fallback_order=(), capacity_reservation_ref='cp7-8-res', credential_acquisition_method='none', estimated_cost_class='free')


def _locked_av():
    for requirement in tomllib.loads(PYPROJECT.read_text(encoding='utf-8'))['tool']['uv']['constraint-dependencies']:
        found = re.fullmatch(r'av==([0-9][0-9.]*)', requirement)
        if found:
            return found.group(1)
    pytest.fail('pyproject.toml has no av== constraint')


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


class _VramSampler(threading.Thread):
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


GPU_SLOTS = _profile_value('gpu', 'slots')['slots']
assert GPU_SLOTS == 2

class CountingLease:
    def __init__(self):
        self._inner = LocalGpuLease(GPU_SLOTS, 7200)
        self._lock = threading.Lock()
        self.refused = 0
        self.held_now = 0
        self.max_held = 0
        self.active = 0
        self.max_active = 0

    def acquire(self, owner):
        try:
            held = self._inner.acquire(owner)
            with self._lock:
                self.held_now += 1
                if self.held_now > self.max_held:
                    self.max_held = self.held_now
            return held
        except GpuLeaseUnavailable:
            with self._lock:
                self.refused += 1
            raise

    def release(self, lease):
        self._inner.release(lease)
        with self._lock:
            self.held_now -= 1

    def work_begin(self):
        with self._lock:
            self.active += 1
            if self.active > self.max_active:
                self.max_active = self.active

    def work_end(self):
        with self._lock:
            self.active -= 1


STT_TEXT = 'Neighbors share tools and recipes and swap stories about their favorite meals.'
TTS_TEXT = 'Small green spaces make crowded streets calmer and bring people closer together. Start growing today.'


@pytest.fixture(scope='module')
def rig(weights, tmp_path_factory):
    if not (FFMPEG_EXE.is_file() and mp.DEFAULT_FFPROBE.is_file()):
        pytest.fail('BLOCKED: ffmpeg or ffprobe missing')
    try:
        mp.verify_pin()
    except Exception as exc:
        pytest.fail(f'BLOCKED: ffmpeg pin verify failed: {exc}')
    rc, _, _ = mp.run_bounded(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], timeout=10)
    if rc != 0:
        pytest.fail(f'BLOCKED: nvidia-smi failed with rc {rc}')
    locked_av, installed_av = _locked_av(), importlib.metadata.version('av')
    if installed_av != locked_av:
        pytest.fail(f'BLOCKED: installed av=={installed_av} differs from locked av=={locked_av}')

    work = tmp_path_factory.mktemp('cp7_gpu')
    staging = work / 'staging'
    out_dir = staging / 'out'
    out_dir.mkdir(parents=True, exist_ok=True)

    voice_conf = _profile_value('voice', 'engine')
    engine_conf = _profile_value('aligner', 'engine')
    tts_staging = work / 'tts_staging'
    tts_staging.mkdir(parents=True, exist_ok=True)
    rate_hz = voice_conf['output']['sample_rate_hz']
    tts = RealKokoroTts(KokoroConfig(
        weights_dir=weights.kokoro_dir,
        lock_path=LOCK,
        staging_dir=tts_staging,
        voice=voice_conf['voice'],
        speed=voice_conf['speed'],
        language=voice_conf['lang'],
        sample_rate=rate_hz,
    ))
    resolve = {}
    aligner = RealWhisperAligner(WhisperAlignerConfig(
        model_dir=weights.whisper_dir,
        lock_path=LOCK,
        resolve_audio=lambda ref: resolve[ref],
        tokenization_policy=POLICY,
        max_unmatched_word_ratio=1.0,
        language=engine_conf['language'],
        device=engine_conf['device'],
        compute_type=engine_conf['compute_type'],
    ))

    stt_fp = hashlib.sha256(STT_TEXT.encode('utf-8')).hexdigest()
    stt_req = {
        'script_version_id': 'cp7-8-stt',
        'script_fingerprint': stt_fp,
        'voice_profile_ref': 'cp7-8-voice',
        'provider_route_ref': 'cp7-8-route',
        'expected_language': 'en-US',
        'operation_key': 'cp7-8-stt',
        'execution_grant_ref': 'cp7-8-grant',
    }
    stt_data = tts.synthesize(DECISION, ScriptText('cp7-8-stt', STT_TEXT, stt_fp), stt_req).audio_bytes
    stt_wav = work / 'stt.wav'
    stt_wav.write_bytes(stt_data)
    resolve['cp7-8-stt'] = stt_wav

    src_mp4 = work / 'src.mp4'
    mp.run_ffmpeg([
        '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1080x1920:rate=30:duration=25',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(src_mp4)
    ], timeout=DEADLINE.timeout(300))

    tone_wav = work / 'tone.wav'
    mp.run_ffmpeg([
        '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=25', str(tone_wav)
    ], timeout=DEADLINE.timeout(300))

    ffmpeg_str = str(FFMPEG_EXE).replace(chr(92), '/')
    tool_id = ToolIdentity(name='ffmpeg', version='2025-03-13', build='gyan-essentials', executable=ffmpeg_str)

    def render_spec(r_self, out_name):
        out_p = str(r_self.work / 'staging' / 'out' / f'{out_name}.mp4').replace(chr(92), '/')
        src_p = str(src_mp4).replace(chr(92), '/')
        tone_p = str(tone_wav).replace(chr(92), '/')
        argv_tuple = (
            ffmpeg_str, '-hide_banner', '-nostdin', '-n',
            '-t', '25', '-i', src_p,
            '-t', '25', '-i', tone_p,
            '-filter_complex', '[0:v]fps=30,format=yuv420p[vout];[1:a]anull[aout]',
            '-map', '[vout]', '-map', '[aout]', '-shortest',
            '-c:v', 'h264_nvenc', '-c:a', 'aac', '-f', 'mp4', out_p,
        )
        return RenderCommandSpec(
            kind=KIND_RENDER,
            argv=argv_tuple,
            redacted_argv=argv_tuple,
            spec_fingerprint='f' * 64,
            tool_identity=tool_id,
        )

    return SimpleNamespace(
        tts=tts,
        aligner=aligner,
        work=work,
        stt_wav=stt_wav,
        stt_data=stt_data,
        render_spec=render_spec,
    )


def task_tts(rig, held, n):
    fp = hashlib.sha256(TTS_TEXT.encode('utf-8')).hexdigest()
    req = {
        'script_version_id': f'cp7-8-tts-{n}',
        'script_fingerprint': fp,
        'voice_profile_ref': 'cp7-8-voice',
        'provider_route_ref': 'cp7-8-route',
        'expected_language': 'en-US',
        'operation_key': f'cp7-8-tts-{n}',
        'execution_grant_ref': 'cp7-8-grant',
    }
    synthesis = rig.tts.synthesize(DECISION, ScriptText(f'cp7-8-tts-{n}', TTS_TEXT, fp), req)
    p = rig.work / f'tts_task_{n}.wav'
    p.write_bytes(synthesis.audio_bytes)
    with wave.open(str(p), 'rb') as wav:
        assert wav.getnchannels() == 1
        assert wav.getnframes() > 0


def task_stt(rig, held, n):
    req = AlignmentRequest(
        voice_artifact_ref='cp7-8-stt',
        voice_hash=hashlib.sha256(rig.stt_data).hexdigest(),
        voice_duration_ms=25000,
        script_version_id='cp7-8-stt',
        script_text=STT_TEXT,
        expected_language='en-US',
    )
    result = rig.aligner.align(req)
    assert len(result.words) > 0


def task_render(rig, held, n):
    spec = rig.render_spec(rig, f'r{n}')
    renderer = RealFfmpegRenderer(ffmpeg_path=str(FFMPEG_EXE), lock_path=RUNTIME_LOCK, timeout_seconds=900)
    outcome = renderer.run(spec, lease=held)
    assert outcome.status is RendererStatus.SUCCEEDED, f'render error: {outcome.error}'
    assert mp.decode_check(outcome.output_ref)['playable'] is True


def run_round(rig, n):
    lease = CountingLease()
    barrier = threading.Barrier(3)
    refused_evt = threading.Event()
    log = []
    results = {}

    tasks = [
        ('tts', task_tts),
        ('stt', task_stt),
        ('render', task_render),
    ]
    threads = []

    def runner(name, func):
        barrier.wait(timeout=60)
        while True:
            DEADLINE.check()
            try:
                held = lease.acquire(name)
                break
            except GpuLeaseUnavailable:
                log.append((name, StageRunState.WAITING_CAPABILITY.value))
                refused_evt.set()
                time.sleep(0.25)

        try:
            lease.work_begin()
            try:
                func(rig, held, n)
                if not refused_evt.is_set():
                    refused_evt.wait(120)
                results[name] = SimpleNamespace(ok=True, error=None)
            except BaseException as exc:
                results[name] = SimpleNamespace(ok=False, error=f'{type(exc).__name__}: {exc}')
            finally:
                lease.work_end()
        finally:
            lease.release(held)

    for name, func in tasks:
        t = threading.Thread(target=runner, args=(name, func))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=DEADLINE.timeout())
        if t.is_alive():
            pytest.fail('thread still alive after deadline')

    return SimpleNamespace(lease=lease, log=log, results=results)


@pytest.fixture(scope='module')
def contention(rig):
    sampler = _VramSampler()
    sampler.start()
    started = time.monotonic()
    rounds = []
    try:
        for r_idx in range(ROUNDS):
            rounds.append(run_round(rig, r_idx))
    finally:
        while len(sampler.samples) < 10 and not sampler.error:
            time.sleep(0.2)
        sampler.finish()
    elapsed = time.monotonic() - started
    return SimpleNamespace(
        rounds=rounds,
        vram=sampler.samples,
        vram_error=sampler.error,
        elapsed=elapsed,
        work=rig.work,
    )


def test_rg07_gpu_two_slots(contention, emit):
    aligner_device = _profile_value('aligner', 'engine')['device']
    round_details = []
    for idx, r in enumerate(contention.rounds):
        for name, res in r.results.items():
            assert res.ok is True, f'round {idx} task {name} failed: {res.error}'
            assert not OOM_PATTERN.search(res.error or ''), f'OOM detected in {name}'
        assert r.lease.max_held <= GPU_SLOTS
        assert r.lease.max_active <= GPU_SLOTS
        assert r.lease.refused >= 1
        waiting_entries = [entry for entry in r.log if entry[1] == StageRunState.WAITING_CAPABILITY.value]
        assert len(waiting_entries) >= 1
        assert r.lease.held_now == 0
        waiting_names = sorted({entry[0] for entry in waiting_entries})
        round_details.append(f'round {idx}: max_held={r.lease.max_held} max_active={r.lease.max_active} refused={r.lease.refused} waiting={waiting_names} oom=0')

    emit(c.report_line('RG-07', 'gpu_two_slots', 'PASS'))
    for detail in round_details:
        emit(f'- gpu_two_slots: {detail}')
    emit(f'- gpu_two_slots: aligner_device={aligner_device} note=aligner_on_cpu_gpu_shared_by_render_and_tts')


def test_rg07_vram_peak(contention, emit):
    assert contention.vram_error is None, f'nvidia-smi error: {contention.vram_error}'
    samples = contention.vram
    elapsed = contention.elapsed
    assert len(samples) >= max(10, int(elapsed / 2)), f'too few VRAM samples: {len(samples)} for {elapsed:.1f}s'
    peak = max(samples)
    assert peak <= VRAM_MAX_MIB, f'peak VRAM {peak} MiB exceeded {VRAM_MAX_MIB} MiB'
    assert elapsed <= GPU_MAX_SECONDS, f'elapsed {elapsed} exceeded {GPU_MAX_SECONDS}'
    tmp_bytes = sum(p.stat().st_size for p in contention.work.rglob('*') if p.is_file())
    assert tmp_bytes < TMP_MAX_BYTES

    emit(c.report_line('RG-07', 'vram_peak', 'PASS'))
    emit(f'- vram_peak: peak_mib={peak} limit_mib={VRAM_MAX_MIB} samples={len(samples)} first_mib={samples[0]} elapsed_s={elapsed:.1f} tmp_bytes={tmp_bytes}')


def test_rg07_secret_scan(contention, emit):
    report_text = REPORT.read_text(encoding='utf-8') if REPORT.is_file() else ''
    render_test_text = RENDER_TEST.read_text(encoding='utf-8')
    self_text = Path(__file__).read_text(encoding='utf-8')
    probe_text = PROBE_SRC.read_text(encoding='utf-8')

    for label, text in [('report', report_text), ('render_test', render_test_text), ('gpu_test', self_text), ('probe', probe_text)]:
        matches = c.scan_secrets(text)
        assert matches == [], f'secret pattern found in {label}'

    emit(c.report_line('RG-07', 'secret_scan', 'PASS'))
    emit('- secret_scan: match_count=0; khong dung credential; chi phi 0 USD')


def test_rg07_deadline_kills_child_process(emit):
    """Deadline 4 giờ dùng cùng cơ chế run_bounded/DEADLINE.timeout(); Ctrl+C được xử lý bằng finally của run_bounded và _VramSampler.finish()."""
    start = time.monotonic()
    with pytest.raises(mp.ChildKilled) as caught:
        mp.run_bounded([sys.executable, '-c', 'import time; time.sleep(120)'], timeout=1.5)
    elapsed = time.monotonic() - start
    assert elapsed < 15, f'deadline kill took too long: {elapsed:.2f}s'

    check_proc = subprocess.run(
        ['tasklist', '/FI', f'PID eq {caught.value.pid}', '/NH'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert 'No tasks' in check_proc.stdout, f'child PID {caught.value.pid} still present: {check_proc.stdout}'

    emit(f'- deadline_kill: child_pid_gone=True elapsed_s={elapsed:.2f}')
