"""IMGGEN-SVC (thật, chỉ Control chạy trên máy có GPU): trọng số đã cấp khớp weights.lock.json, sidecar khởi động ngoại tuyến
(HTTPS_PROXY trỏ cổng chết), sinh 2 ảnh rồi 1 ảnh 864x1536 / 16 bước, đo thời gian mỗi ảnh (gồm cả khởi tạo CUDA), VRAM đỉnh
từng pha, bộ nhớ riêng trước/sau nạp, sau pha, sau giải phóng; chấm ngân sách của Control (working set đỉnh <= 4 GiB, đỉnh private
trừ VRAM đang giữ <= 4 GiB, phần dư <= 2,5 GiB chu kỳ đầu và <= 512 MiB chu kỳ sau), báo private thô và commit hệ thống, cùng fp8_path.

Chỉ được thu thập khi dòng lệnh nêu tests/real (tests/real/conftest.py). Biến môi trường:
- AIAVC_DATA_DIR (hoặc LOCALAPPDATA/AIAutoVideoCreator) cho <data>;
- AIAVC_IMAGEGEN_PYTHON ghi đè python của sidecar (mặc định <data>/imagegen/venv/Scripts/python.exe);
- AIAVC_IMAGEGEN_HUB ghi đè <data>/models/hf-hub.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO / 'tools') not in sys.path:
    sys.path.insert(0, str(REPO / 'tools'))

from imagegen import engine, protocol, weights  # noqa: E402

SERVER = REPO / 'tools' / 'imagegen' / 'server.py'
MANIFEST = REPO / 'tools' / 'imagegen' / 'weights.lock.json'
DEAD_PROXY = 'http://127.0.0.1:9'
READY_SECONDS = 300
JOB_SECONDS = 15 * 60
VRAM_MAX_BYTES = 10_000_000_000
# Budget set by Control 02/11/2026 (engine.memory_budget): peak working set, peak private commit minus GPU reserved in the same
# sample (WDDM charges device memory to the process commit), residual after a phase: first cycle <= engine.RESIDUAL_LIMIT_BYTES,
# steady state <= engine.STEADY_RESIDUAL_MAX_BYTES. The raw private peak is reported only.
PEAK_WSET_MAX_BYTES = 4 * 1024 ** 3
HOST_PRIVATE_MAX_BYTES = 4 * 1024 ** 3
SECONDS_PER_IMAGE_MAX = 60.0
CAPTIONS = (
    'Full-color documentary photograph taken at street level at dawn. A wide, empty city boulevard runs from the lower foreground '
    'into soft morning haze between rows of pale stone apartment buildings with closed grey metal shutters. Wet asphalt reflects '
    'the cool blue sky and a few warm street lamps that are still lit. Bare plane trees line both pavements, their branches '
    'thin and dark against the haze. In the middle distance a single delivery bicycle leans against a lamp post. The light is '
    'low and even, the palette is muted grey, blue and beige with small amber accents, the lens is a moderate telephoto with '
    'gentle compression, and the image has fine film grain and a calm, quiet mood.',
    'Close-up documentary photograph of rain on an old painted metal railing beside a river embankment in late afternoon. Large '
    'water droplets cling to the underside of the green rail and catch soft daylight, while the river beyond is a smooth band '
    'of blurred grey water. Fallen yellow leaves rest on the wet stone ledge in the lower third of the frame. The depth of field '
    'is shallow, so only the nearest droplets are sharp. The light is diffuse and cool, the colours are deep green, slate grey '
    'and ochre, and the image has gentle contrast, fine grain and a reflective, unhurried mood.',
)


def _data_root() -> Path:
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR', 'not a PNG'
    return struct.unpack('>II', data[16:24])


class Client:
    def __init__(self, port: int, token: str):
        self.port, self.token = port, token

    def call(self, method, path, body=None, auth=True):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            headers = {'Authorization': f'Bearer {self.token}'} if auth else {}
            data = None if body is None else json.dumps(body).encode('utf-8')
            if data is not None:
                headers['Content-Type'] = 'application/json'
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def json(self, method, path, body=None, auth=True):
        status, _headers, data = self.call(method, path, body, auth)
        return status, json.loads(data.decode('utf-8'))


@pytest.fixture
def sidecar(tmp_path):
    data = _data_root()
    hub = Path(os.environ.get('AIAVC_IMAGEGEN_HUB') or data / 'models' / 'hf-hub')
    python = Path(os.environ.get('AIAVC_IMAGEGEN_PYTHON') or data / 'imagegen' / 'venv' / 'Scripts' / 'python.exe')
    assert python.is_file(), f'sidecar python missing: {python}'
    manifest = weights.load_manifest(MANIFEST)
    check = weights.verify(hub, manifest, write=False)
    assert check.ok, check.problems()
    port, token = _free_port(), secrets.token_urlsafe(36)
    stop_file = tmp_path / 'stop.request'
    env = dict(os.environ, **{protocol.TOKEN_ENV: token, 'HTTPS_PROXY': DEAD_PROXY, 'HTTP_PROXY': DEAD_PROXY, 'HF_HUB_OFFLINE': '1',
                              'TRANSFORMERS_OFFLINE': '1'})
    log = (tmp_path / 'sidecar.log').open('wb')
    process = subprocess.Popen([str(python), '-I', str(SERVER), '--port', str(port), '--hub', str(hub), '--out', str(tmp_path / 'out'),
                                '--parent-pid', str(os.getpid()), '--stop-file', str(stop_file)],
                               cwd=str(REPO), env=env, stdout=log, stderr=subprocess.STDOUT)
    client = Client(port, token)
    try:
        yield process, client, tmp_path / 'sidecar.log'
    finally:
        if process.poll() is None:
            stop_file.write_text('stop', encoding='utf-8')
            try:
                process.wait(60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(30)
        log.close()


def _wait_health(client: Client, process, states, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert process.poll() is None, f'sidecar exited with {process.returncode}'
        try:
            status, health = client.json('GET', '/v1/health', auth=False)
        except OSError:
            time.sleep(1)
            continue
        if status == 200 and health['state'] in states:
            return health
        time.sleep(1)
    pytest.fail(f'sidecar not in {states} after {timeout} s')


PHASE_NAMES = ('text_encoder', 'transformer', 'vae')


def _run_job(client, process, captions, label, emit):
    job_id = hashlib.sha256(f'imggen-real:{label}:{time.time_ns()}'.encode()).hexdigest()[:32]
    body = {'job_id': job_id, 'items': [
        {'item_id': f'{label}-{n}', 'caption': caption, 'width': protocol.DEFAULT_WIDTH, 'height': protocol.DEFAULT_HEIGHT,
         'steps': protocol.DEFAULT_STEPS, 'seed': protocol.derive_seed(job_id, f'{label}-{n}')} for n, caption in enumerate(captions)]}
    started = time.monotonic()
    status, view = client.json('POST', '/v1/jobs', body)
    assert status == 202 and view['created'] is True, view
    deadline = time.monotonic() + JOB_SECONDS
    while view['state'] not in ('done', 'failed'):
        assert process.poll() is None and time.monotonic() < deadline, 'job did not finish'
        time.sleep(2)
        view = client.json('GET', f'/v1/jobs/{job_id}')[1]
    elapsed = time.monotonic() - started
    assert view['state'] == 'done', view
    for item in view['items']:
        status, headers, data = client.call('GET', f"/v1/jobs/{job_id}/items/{item['item_id']}")
        assert status == 200 and headers['X-Content-SHA256'] == hashlib.sha256(data).hexdigest() == item['sha256']
        assert _png_size(data) == (protocol.DEFAULT_WIDTH, protocol.DEFAULT_HEIGHT)
        assert item['fp8_path'] == 'tensorwise', item
        emit(f"IMGGEN-SVC item {item['item_id']}: {len(data)} bytes, fp8_path {item['fp8_path']}, seconds {json.dumps(item['seconds'])}")
    health = client.json('GET', '/v1/health', auth=False)[1]
    stats = health['last_cycle']['stats']
    for phase in PHASE_NAMES:
        record = stats[phase]
        figures = {key: (record.get(key) or {}).get('private_bytes') for key in ('memory_before_load', 'memory_after_load',
                                                                                  'memory_after_phase', 'memory_after_free')}
        emit(f"IMGGEN-SVC {label} {phase}: private {json.dumps(figures)}, peak in phase {record.get('peak_private_bytes_phase')}, "
             f"residual {record.get('residual_private_bytes')}, gpu reserved after load "
             f"{(record.get('memory_after_load') or {}).get('gpu_reserved_bytes')}, load {record.get('load_seconds')} s")
    return elapsed, health


def test_sidecar_generates_offline_illustrations_within_budget(sidecar, emit):
    process, client, log_path = sidecar
    health = _wait_health(client, process, ('idle', 'not_provisioned', 'error'), READY_SECONDS)
    assert health['state'] == 'idle', health
    assert health['revision'] == protocol.MODEL_REVISION
    # First cycle: two images; the CUDA libraries load their kernels on first use, so a phase may keep up to the engine's own
    # refusal limit. Second cycle (steady state): every phase must give back what it took.
    elapsed, first = _run_job(client, process, CAPTIONS, 'first', emit)
    _elapsed, second = _run_job(client, process, CAPTIONS[:1], 'second', emit)
    stats = first['last_cycle']['stats']
    peaks = {phase: stats[phase].get('peak_allocated_bytes') for phase in PHASE_NAMES}
    per_image = elapsed / len(CAPTIONS)
    process_memory = second.get('process') or {}
    memory = second.get('memory') or {}
    budget = engine.memory_budget([first['last_cycle']['stats'], second['last_cycle']['stats']],
                                  {'peak_wset_bytes': process_memory.get('peak_wset_bytes'),
                                   'peak_private_minus_gpu_bytes': memory.get('peak_private_minus_gpu_bytes'),
                                   'peak_private_bytes': process_memory.get('peak_private_bytes')})
    emit(f'IMGGEN-SVC first cycle: {stats.get("cycle_seconds")} s, {per_image:.1f} s/image, VRAM peaks {json.dumps(peaks)}, '
         f'fp8 {second["fp8_path"]}')
    emit(f"IMGGEN-SVC budget: {json.dumps(budget['ok'])}, figures {json.dumps(budget['figures'])}, commit {json.dumps(second.get('commit'))}")
    assert all(isinstance(v, int) and v <= VRAM_MAX_BYTES for v in peaks.values()), peaks
    # Control 02/11/2026: WDDM charges GPU memory to the process commit, so the raw private peak is reported, not asserted.
    assert budget['ok']['peak_wset'] and budget['figures']['peak_wset_bytes'] <= PEAK_WSET_MAX_BYTES, budget
    assert budget['ok']['peak_private_minus_gpu'] and budget['figures']['peak_private_minus_gpu_bytes'] <= HOST_PRIVATE_MAX_BYTES, budget
    assert budget['ok']['first_cycle_residual'] and budget['ok']['steady_residual'] is True, budget
    assert second.get('commit') and second['commit']['available_bytes'] > 0, second.get('commit')
    assert per_image <= SECONDS_PER_IMAGE_MAX, per_image
    assert client.json('POST', '/v1/shutdown')[0] == 202
    assert process.wait(60) == 0
    assert 'Traceback' not in log_path.read_text(encoding='utf-8', errors='replace')
