"""IMGGEN-SVC: API HTTP loopback của sidecar sinh ảnh (token, job, idempotency, trạng thái, dừng, lưu qua khởi động lại) và chu kỳ
ba pha của engine.run_cycle (gom caption đang chờ, cổng VRAM, OOM thử lại một lần). Server thật trên cổng tạm, gọi bằng http.client;
backend là ScriptedBackend (không torch, không GPU, không mạng).
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import struct
import subprocess
import sys
import threading
import time
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))

from imagegen import engine, protocol, server, weights  # noqa: E402

TOKEN = 'k' * 40
JOB_A, JOB_B = 'a' * 32, 'b' * 32
VERIFIED = weights.Verification(True, [], [], [], False, False, 0.0)
COMMIT = {'limit_bytes': 78_000_000_000, 'available_bytes': 15_000_000_000, 'used_bytes': 63_000_000_000, 'ram_available_bytes': 5_000_000_000}


class OutOfMemoryError(RuntimeError):
    pass


def tiny_png(seed: int) -> bytes:
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    pixel = b'\x00' + bytes([seed % 256, (seed >> 8) % 256, 0])
    return (engine.PNG_SIGNATURE + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(pixel)) + chunk(b'IEND', b''))


class ScriptedBackend:
    """Stands in for engine.KleinBackend: records every call, returns tiny PNGs and raises where the test scripts it."""

    def __init__(self, *, free=20_000_000_000, oom_on=(), fail_on=(), unavailable=False, host=None, commit=None, phase_memory=False):
        self.calls = []
        self.free = free
        self.oom_on = list(oom_on)
        self.fail_on = set(fail_on)
        self.unavailable = unavailable
        self.host = host
        self.commit = commit
        self.phase_memory = phase_memory
        self.released = 0

    def requirement(self, phase):
        return engine.PHASE_REQUIREMENT_BYTES[phase]

    @staticmethod
    def _next(value):
        if isinstance(value, list):
            return value.pop(0) if len(value) > 1 else value[0]
        return value

    def free_vram(self):
        if self.unavailable:
            raise engine.EngineUnavailable('CUDA is not available')
        return self._next(self.free)

    def host_available(self):
        return self._next(self.host)

    def commit_available(self):
        return self._next(self.commit)

    def memory(self):
        return {'private_bytes': 1_234} if self.phase_memory else None

    def is_oom(self, error):
        return engine._is_oom_error(error)

    def fp8_path(self):
        return 'tensorwise'

    def _call(self, method, key):
        self.calls.append((method, key))
        if (method, key) in self.oom_on:
            self.oom_on.remove((method, key))
            raise OutOfMemoryError('CUDA out of memory. Tried to allocate 2.00 GiB')
        if (method, key) in self.fail_on:
            raise ValueError(f'scripted failure in {method}')

    def load(self, phase):
        self._call('load', phase)
        if self.phase_memory:
            return {'memory_before_load': {'private_bytes': 1_000}, 'memory_after_load': {'private_bytes': 1_064}}
        return None

    def unload(self, phase):
        self.calls.append(('unload', phase))
        info = {'peak_allocated_bytes': 1}
        if self.phase_memory:
            info.update(memory_after_phase={'private_bytes': 1_080}, memory_after_free={'private_bytes': 1_010},
                        peak_private_bytes_phase=1_100, residual_private_bytes=10)
        return info

    def encode(self, item):
        self._call('encode', item.key)
        return ('embeds', item.key)

    def denoise(self, item, embeds):
        self._call('denoise', item.key)
        assert embeds == ('embeds', item.key)
        return ('latents', item.key)

    def decode(self, item, latents):
        self._call('decode', item.key)
        assert latents == ('latents', item.key)
        return tiny_png(item.seed)

    def release(self):
        self.released += 1


class Gate:
    """A verifier that answers only when the test opens it."""

    def __init__(self, result=VERIFIED):
        self.result = result
        self.opened = threading.Event()

    def __call__(self):
        self.opened.wait(10)
        return self.result


class Service:
    def __init__(self, tmp_path: Path, backend, *, verifier=lambda: VERIFIED, clock=time.time):
        self.backend = backend
        self.logs = []
        self.stop_file = tmp_path / 'state' / 'stop.request'
        self.parent = {'alive': True}
        self.app = server.App(backend=backend, out_dir=tmp_path / 'out', token=TOKEN, verifier=verifier,
                              gpu_memory=lambda: {'free_bytes': 11_000_000_000, 'total_bytes': 12_878_610_432}, commit_probe=lambda: dict(COMMIT), clock=clock,
                              log=self.logs.append)
        self.http = server.make_server(self.app, 0)
        self.port = self.http.server_address[1]
        self.result = {}
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        wait_for(lambda: self.app._threads)

    def _serve(self):
        self.result['ended'] = server.serve(self.app, self.http, stop_file=self.stop_file, parent_alive=lambda: self.parent['alive'],
                                            grace=5, poll=0.05)

    def call(self, method, path, body=None, token=TOKEN):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            headers = {'Authorization': f'Bearer {token}'} if token else {}
            data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode('utf-8'))
            if data is not None:
                headers['Content-Type'] = 'application/json'
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def json(self, method, path, body=None, token=TOKEN):
        status, _headers, data = self.call(method, path, body, token)
        return status, json.loads(data.decode('utf-8'))

    def job(self, job_id):
        return self.json('GET', f'/v1/jobs/{job_id}')[1]

    def wait_job(self, job_id, states=('done', 'failed')):
        wait_for(lambda: self.job(job_id)['state'] in states)
        return self.job(job_id)

    def stop(self):
        self.app.request_stop('test teardown')
        self.thread.join(10)


@pytest.fixture
def services():
    started = []
    yield started
    for service in started:
        service.stop()


def start(services, tmp_path, backend=None, **kwargs) -> Service:
    service = Service(tmp_path, backend or ScriptedBackend(), **kwargs)
    services.append(service)
    return service


def wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError('condition not reached in time')


def job_body(job_id=JOB_A, count=3, caption='A wide documentary photograph of an empty boulevard at dawn, soft haze.'):
    return {'job_id': job_id, 'items': [{'item_id': f'shot-{n}', 'caption': f'{caption} Variant {n}.', 'width': 864, 'height': 1536,
                                         'steps': 16, 'seed': protocol.derive_seed(job_id, f'shot-{n}')} for n in range(count)]}


def keys(job_id, count=3):
    return [f'{job_id}/shot-{n}' for n in range(count)]


def test_health_needs_no_token_and_turns_idle_after_verification(services, tmp_path):
    gate = Gate()
    service = start(services, tmp_path, verifier=gate)
    assert service.http.server_address[0] == '127.0.0.1'
    status, health = service.json('GET', '/v1/health', token=None)
    assert status == 200 and health['state'] == 'verifying'
    gate.opened.set()
    wait_for(lambda: service.json('GET', '/v1/health', token=None)[1]['state'] == 'idle')
    health = service.json('GET', '/v1/health', token=None)[1]
    assert health['revision'] == protocol.MODEL_REVISION and health['queue'] == {'jobs': 0, 'items': 0}
    assert health['fp8_path'] == 'tensorwise' and health['vram']['free_bytes'] == 11_000_000_000 and health['protocol'] == 1
    assert service.backend.calls == []


def test_every_other_endpoint_needs_the_bearer_token(services, tmp_path):
    service = start(services, tmp_path)
    assert service.json('POST', '/v1/jobs', job_body(), token=None)[0] == 401
    status, body = service.json('POST', '/v1/jobs', job_body(), token='x' * 40)
    assert status == 401 and body['error']['code'] == 'UNAUTHORIZED'
    assert service.json('GET', f'/v1/jobs/{JOB_A}', token=None)[0] == 401
    assert service.json('POST', '/v1/shutdown', token='x' * 40)[0] == 401
    assert service.json('GET', '/v1/nothing', token=None)[0] == 404
    assert not service.app.stopping.is_set() and service.app.jobs.counts() == {'jobs': 0, 'items': 0}


def test_a_job_goes_through_three_phases_and_serves_its_pngs(services, tmp_path):
    service = start(services, tmp_path)
    status, view = service.json('POST', '/v1/jobs', job_body())
    assert status == 202 and view['created'] is True and view['job_id'] == JOB_A
    done = service.wait_job(JOB_A)
    assert done['state'] == 'done'
    k = keys(JOB_A)
    assert service.backend.calls == ([('load', 'text_encoder')] + [('encode', x) for x in k] + [('unload', 'text_encoder'), ('load', 'transformer')]
                                     + [('denoise', x) for x in k] + [('unload', 'transformer'), ('load', 'vae')] + [('decode', x) for x in k]
                                     + [('unload', 'vae')])
    for n, item in enumerate(done['items']):
        assert item['state'] == 'done' and item['fp8_path'] == 'tensorwise' and item['attempts'] == 1 and item['error'] is None
        assert set(item['seconds']) == {'text_encoder', 'transformer', 'vae'}
        status, headers, data = service.call('GET', f'/v1/jobs/{JOB_A}/items/shot-{n}')
        assert status == 200 and headers['Content-Type'] == 'image/png' and data.startswith(engine.PNG_SIGNATURE)
        assert headers['X-Content-SHA256'] == hashlib.sha256(data).hexdigest() == item['sha256'] and item['bytes'] == len(data)
        assert (tmp_path / 'out' / JOB_A / f'item-{n}.png').read_bytes() == data
    assert service.json('GET', '/v1/health', token=None)[1]['state'] == 'idle'


def test_captions_of_all_queued_jobs_share_one_cycle(services, tmp_path):
    gate = Gate()
    service = start(services, tmp_path, verifier=gate)
    assert service.json('POST', '/v1/jobs', job_body(JOB_A, 3))[0] == 202
    assert service.json('POST', '/v1/jobs', job_body(JOB_B, 2))[0] == 202
    assert service.json('GET', '/v1/health', token=None)[1]['queue'] == {'jobs': 2, 'items': 5}
    gate.opened.set()
    service.wait_job(JOB_A)
    service.wait_job(JOB_B)
    calls = service.backend.calls
    assert calls.count(('load', 'text_encoder')) == 1 and calls.count(('load', 'transformer')) == 1
    first_unload = calls.index(('unload', 'text_encoder'))
    assert [c for c in calls[:first_unload] if c[0] == 'encode'] == [('encode', x) for x in keys(JOB_A, 3) + keys(JOB_B, 2)]


def test_the_same_body_is_idempotent_and_another_body_conflicts(services, tmp_path):
    service = start(services, tmp_path)
    service.json('POST', '/v1/jobs', job_body())
    service.wait_job(JOB_A)
    status, view = service.json('POST', '/v1/jobs', job_body())
    assert status == 202 and view['created'] is False and view['state'] == 'done'
    assert [c for c in service.backend.calls if c[0] == 'encode'] == [('encode', x) for x in keys(JOB_A)]
    status, body = service.json('POST', '/v1/jobs', job_body(caption='A different caption for the same job.'))
    assert status == 409 and body['error']['code'] == 'JOB_CONFLICT'


def test_out_of_memory_is_retried_once(services, tmp_path):
    k = keys(JOB_A)
    service = start(services, tmp_path, ScriptedBackend(oom_on=[('denoise', k[0])]))
    service.json('POST', '/v1/jobs', job_body())
    assert service.wait_job(JOB_A)['state'] == 'done'
    calls = service.backend.calls
    at = calls.index(('denoise', k[0]))
    assert calls[at + 1:at + 4] == [('unload', 'transformer'), ('load', 'transformer'), ('denoise', k[0])]
    assert service.app.last_cycle['stats']['transformer']['oom_retries'] == 1


def test_a_second_out_of_memory_fails_the_items_until_the_post_is_repeated(services, tmp_path):
    k = keys(JOB_A)
    service = start(services, tmp_path, ScriptedBackend(oom_on=[('denoise', k[0]), ('denoise', k[0])]))
    service.json('POST', '/v1/jobs', job_body())
    failed = service.wait_job(JOB_A)
    assert failed['state'] == 'failed'
    for item in failed['items']:
        assert item['state'] == 'failed' and item['error']['code'] == 'GPU_OUT_OF_MEMORY' and item['error']['retryable'] is True
    assert ('load', 'vae') not in service.backend.calls
    status, view = service.json('POST', '/v1/jobs', job_body())
    assert status == 202 and view['created'] is False
    again = service.wait_job(JOB_A, states=('done',))
    assert all(item['state'] == 'done' and item['attempts'] == 2 for item in again['items'])


def test_a_failing_item_does_not_fail_its_neighbours(services, tmp_path):
    k = keys(JOB_A)
    service = start(services, tmp_path, ScriptedBackend(fail_on={('decode', k[1])}))
    service.json('POST', '/v1/jobs', job_body())
    view = service.wait_job(JOB_A)
    assert view['state'] == 'failed' and [i['state'] for i in view['items']] == ['done', 'failed', 'done']
    assert view['items'][1]['error']['code'] == 'GENERATION_FAILED' and view['items'][1]['error']['message'].startswith('vae: ValueError')


def test_not_provisioned_answers_503_with_the_file_list(services, tmp_path):
    missing = weights.Verification(False, ['acme/klein@aaaaaaaaaaaa/vae/x.safetensors'], [], [], True, False, 0.1)
    service = start(services, tmp_path, verifier=lambda: missing)
    wait_for(lambda: service.json('GET', '/v1/health', token=None)[1]['state'] == 'not_provisioned')
    health = service.json('GET', '/v1/health', token=None)[1]
    assert health['missing'] == ['missing: acme/klein@aaaaaaaaaaaa/vae/x.safetensors']
    status, body = service.json('POST', '/v1/jobs', job_body())
    assert status == 503 and body['error']['code'] == 'NOT_PROVISIONED' and body['error']['missing'] == health['missing']
    assert service.backend.calls == []


def test_jobs_accepted_while_verifying_fail_when_the_weights_are_missing(services, tmp_path):
    gate = Gate(weights.Verification(False, [], ['acme/klein@aaaaaaaaaaaa/x (sha256 0, expected 1)'], [], True, False, 0.1))
    service = start(services, tmp_path, verifier=gate)
    assert service.json('POST', '/v1/jobs', job_body())[0] == 202
    gate.opened.set()
    view = service.wait_job(JOB_A)
    assert all(item['error']['code'] == 'NOT_PROVISIONED' for item in view['items'])
    assert service.backend.calls == []


def test_an_unavailable_engine_turns_the_service_to_error(services, tmp_path):
    service = start(services, tmp_path, ScriptedBackend(unavailable=True))
    service.json('POST', '/v1/jobs', job_body())
    view = service.wait_job(JOB_A)
    assert all(item['error']['code'] == 'ENGINE_UNAVAILABLE' for item in view['items'])
    health = service.json('GET', '/v1/health', token=None)[1]
    assert health['state'] == 'error' and 'CUDA' in health['error']
    status, body = service.json('POST', '/v1/jobs', job_body(JOB_B))
    assert status == 503 and body['error']['code'] == 'ENGINE_UNAVAILABLE'


@pytest.mark.parametrize('trigger', ['stop_file', 'parent', 'shutdown'])
def test_stop_file_parent_exit_and_shutdown_each_stop_the_service(services, tmp_path, trigger):
    service = start(services, tmp_path)
    wait_for(lambda: service.app.state == 'idle')
    if trigger == 'stop_file':
        service.stop_file.parent.mkdir(parents=True, exist_ok=True)
        service.stop_file.write_text('stop', encoding='utf-8')
    elif trigger == 'parent':
        service.parent['alive'] = False
    else:
        assert service.json('POST', '/v1/shutdown')[0] == 202
    service.thread.join(10)
    assert not service.thread.is_alive() and service.result['ended'] is True
    assert service.http.socket.fileno() == -1 and service.backend.released >= 1
    assert trigger != 'stop_file' or service.stop_file.exists()


def test_jobs_survive_a_restart_and_expire_after_24_hours(services, tmp_path):
    first = start(services, tmp_path)
    first.json('POST', '/v1/jobs', job_body())
    done = first.wait_job(JOB_A)
    first.stop()
    second = start(services, tmp_path)
    assert second.job(JOB_A)['items'] == done['items']
    status, headers, data = second.call('GET', f'/v1/jobs/{JOB_A}/items/shot-2')
    assert status == 200 and headers['X-Content-SHA256'] == done['items'][2]['sha256']
    assert second.backend.calls == []
    second.stop()
    later = start(services, tmp_path, clock=lambda: time.time() + protocol.RESULT_TTL_SECONDS + 60)
    assert later.json('GET', f'/v1/jobs/{JOB_A}')[0] == 404
    assert not (tmp_path / 'out' / JOB_A).exists()


def test_a_corrupt_stored_png_is_regenerated_on_the_next_post(services, tmp_path):
    service = start(services, tmp_path)
    service.json('POST', '/v1/jobs', job_body())
    service.wait_job(JOB_A)
    (tmp_path / 'out' / JOB_A / 'item-1.png').write_bytes(b'not a png')
    status, body = service.json('GET', f'/v1/jobs/{JOB_A}/items/shot-1')
    assert status == 500 and body['error']['code'] == 'RESULT_CORRUPT'
    item = service.job(JOB_A)['items'][1]
    assert item['state'] == 'failed' and item['error']['code'] == 'RESULT_MISSING' and item['error']['retryable'] is True
    service.json('POST', '/v1/jobs', job_body())
    view = service.wait_job(JOB_A, states=('done',))
    assert view['items'][1]['attempts'] == 2 and service.call('GET', f'/v1/jobs/{JOB_A}/items/shot-1')[0] == 200


def test_unfinished_items_are_queued_again_after_a_crash_or_an_interruption(tmp_path):
    store = server.JobStore(tmp_path / 'out')
    store.submit(protocol.parse_job(json.dumps(job_body(JOB_A, 2)).encode('utf-8')))
    store.submit(protocol.parse_job(json.dumps(job_body(JOB_B, 1)).encode('utf-8')))
    batch = store.take(2)
    assert [item.key for item in batch] == keys(JOB_A, 2)
    reloaded = server.JobStore(tmp_path / 'out')
    assert reloaded.load() == {'loaded': 2, 'requeued': 3, 'lost': 0}
    assert reloaded.queue == keys(JOB_A, 2) + keys(JOB_B, 1)
    outcomes = [engine.ItemOutcome(batch[0].key, png=tiny_png(1)), engine.ItemOutcome(batch[1].key)]
    store.finish(engine.CycleResult(outcomes, [batch[1].key], {}))
    assert store.queue == [batch[1].key] + keys(JOB_B, 1)
    view = store.view(JOB_A)
    assert [i['state'] for i in view['items']] == ['done', 'queued'] and view['items'][1]['attempts'] == 0


def test_the_vram_gate_waits_for_free_memory_then_gives_up():
    class Clock:
        now = 0.0

        def sleep(self, seconds):
            self.now += seconds

    item = engine.WorkItem(f'{JOB_A}/shot-0', 'caption', 864, 1536, 16, 7)
    clock, states = Clock(), []
    backend = ScriptedBackend(free=[1, 1, 10 ** 12])
    result = engine.run_cycle(backend, [item], on_state=lambda s, p: states.append((s, p)), sleep=clock.sleep, clock=lambda: clock.now,
                              vram_wait_max=60)
    assert result.outcomes[0].png is not None and ('busy', 'waiting_vram:text_encoder') in states
    assert result.stats['text_encoder']['waited_seconds'] == 2 * engine.VRAM_POLL_SECONDS
    clock = Clock()
    starved = ScriptedBackend(free=1)
    result = engine.run_cycle(starved, [item], sleep=clock.sleep, clock=lambda: clock.now, vram_wait_max=60)
    assert result.outcomes[0].error_code == 'GPU_MEMORY_UNAVAILABLE' and not any(c[0] == 'load' for c in starved.calls)
    assert engine.VRAM_MARGIN_BYTES == 1_500_000_000


def test_requests_the_server_refuses(services, tmp_path):
    gate = Gate()
    service = start(services, tmp_path, verifier=gate)
    connection = http.client.HTTPConnection('127.0.0.1', service.port, timeout=10)
    connection.putrequest('POST', '/v1/jobs')
    connection.putheader('Authorization', f'Bearer {TOKEN}')
    connection.putheader('Content-Length', str(protocol.MAX_BODY_BYTES + 1))
    connection.endheaders()
    response = connection.getresponse()
    assert response.status == 413 and json.loads(response.read())['error']['code'] == 'BODY_TOO_LARGE'
    connection.close()
    status, body = service.json('POST', '/v1/jobs', b'{"job_id": 1}')
    assert status == 400 and body['error']['field'] == 'body'
    assert service.json('PUT', '/v1/jobs', b'{}')[0] == 405
    assert service.json('GET', f'/v1/jobs/{"c" * 32}')[0] == 404
    assert service.json('GET', '/v1/jobs/../../etc')[0] == 404
    service.json('POST', '/v1/jobs', job_body())
    status, body = service.json('GET', f'/v1/jobs/{JOB_A}/items/shot-0')
    assert status == 409 and body['error']['code'] == 'ITEM_NOT_READY'


def test_the_queue_is_bounded(services, tmp_path):
    service = start(services, tmp_path, verifier=Gate())
    for n in range(protocol.MAX_QUEUED_ITEMS // protocol.MAX_ITEMS_PER_JOB):
        assert service.json('POST', '/v1/jobs', job_body(f'{n:032x}', protocol.MAX_ITEMS_PER_JOB))[0] == 202
    status, body = service.json('POST', '/v1/jobs', job_body('f' * 32, 1))
    assert status == 429 and body['error']['code'] == 'QUEUE_FULL'


def test_the_host_memory_gate_waits_for_ram_then_reports_host_memory_low():
    class Clock:
        now = 0.0

        def sleep(self, seconds):
            self.now += seconds

    item = engine.WorkItem(f'{JOB_A}/shot-0', 'caption', 864, 1536, 16, 7)
    low, enough = engine.HOST_MIN_AVAILABLE_BYTES - 1, engine.HOST_MIN_AVAILABLE_BYTES
    clock, states = Clock(), []
    backend = ScriptedBackend(host=[low, enough])
    result = engine.run_cycle(backend, [item], on_state=lambda s, p: states.append((s, p)), sleep=clock.sleep, clock=lambda: clock.now,
                              vram_wait_max=60)
    assert result.outcomes[0].png is not None and ('busy', 'waiting_ram:text_encoder') in states
    assert result.stats['text_encoder']['host_available_before_bytes'] == enough
    clock = Clock()
    starved = ScriptedBackend(host=low)
    result = engine.run_cycle(starved, [item], sleep=clock.sleep, clock=lambda: clock.now, vram_wait_max=60)
    assert result.outcomes[0].error_code == 'HOST_MEMORY_LOW' and not any(c[0] == 'load' for c in starved.calls)


def test_private_memory_left_after_a_phase_is_cleaned_then_refused():
    mib = 1024 * 1024
    assert engine.residual_action(4_000 * mib, 4_000 * mib + engine.FREE_TOLERANCE_BYTES) == 'ok'
    assert engine.residual_action(4_000 * mib, 4_000 * mib + engine.FREE_TOLERANCE_BYTES + 1) == 'clean'
    assert engine.residual_action(4_000 * mib, 4_000 * mib + engine.RESIDUAL_LIMIT_BYTES + 1) == 'refuse'
    assert engine.residual_action(None, 5) == 'ok'
    # A whole component left behind (the 6.27 GB fp8 transformer, the 8.88 GB text encoder) is always refused.
    assert engine.FREE_TOLERANCE_BYTES < engine.RESIDUAL_LIMIT_BYTES < 6_270_949_144


def test_phase_memory_figures_reach_the_cycle_stats_and_health(services, tmp_path):
    service = start(services, tmp_path, ScriptedBackend(phase_memory=True))
    service.json('POST', '/v1/jobs', job_body())
    assert service.wait_job(JOB_A)['state'] == 'done'
    health = service.json('GET', '/v1/health', token=None)[1]
    for phase in engine.PHASES:
        record = health['last_cycle']['stats'][phase]
        assert record['memory_before_load'] == {'private_bytes': 1_000} and record['memory_after_free'] == {'private_bytes': 1_010}
        assert record['peak_private_bytes_phase'] == 1_100 and record['residual_private_bytes'] == 10
    assert health['memory'] == {'private_bytes': 1_234}
    assert any('peak 1100 B, residual after free 10 B' in line for line in service.logs)


def test_the_commit_gate_waits_for_system_commit_then_reports_host_commit_low():
    class Clock:
        now = 0.0

        def sleep(self, seconds):
            self.now += seconds

    item = engine.WorkItem(f'{JOB_A}/shot-0', 'caption', 864, 1536, 16, 7)
    need = engine.PHASE_COMMIT_BYTES['text_encoder'] + engine.COMMIT_MARGIN_BYTES
    enough = max(engine.PHASE_COMMIT_BYTES.values()) + engine.COMMIT_MARGIN_BYTES
    clock, states = Clock(), []
    backend = ScriptedBackend(commit=[need - 1, enough])
    result = engine.run_cycle(backend, [item], on_state=lambda s, p: states.append((s, p)), sleep=clock.sleep, clock=lambda: clock.now,
                              vram_wait_max=60)
    assert result.outcomes[0].png is not None and ('busy', 'waiting_commit:text_encoder') in states
    assert result.stats['transformer']['commit_available_before_bytes'] == enough
    clock = Clock()
    starved = ScriptedBackend(commit=need - 1)
    result = engine.run_cycle(starved, [item], sleep=clock.sleep, clock=lambda: clock.now, vram_wait_max=60)
    assert result.outcomes[0].error_code == 'HOST_COMMIT_LOW' and not any(c[0] == 'load' for c in starved.calls)
    assert 'HOST_COMMIT_LOW' in protocol.RETRYABLE_ITEM_ERRORS
    assert engine.COMMIT_MARGIN_BYTES == 2_000_000_000 and engine.PHASE_COMMIT_BYTES['transformer'] >= 10_000_000_000


def test_the_memory_budget_judges_working_set_host_private_and_residuals():
    gib, mib = 1024 ** 3, 1024 ** 2
    # Control's streaming measurement (02/11/2026): private tracks GPU reserved; host part about 3.2 GiB, working set 1.8 GiB.
    first = {'text_encoder': {'residual_private_bytes': int(1.15 * gib)}, 'transformer': {'residual_private_bytes': -10 * mib},
             'vae': {'residual_private_bytes': 200 * mib}}
    steady = {phase: {'residual_private_bytes': 20 * mib} for phase in engine.PHASES}
    peaks = {'peak_wset_bytes': int(1.8 * gib), 'peak_private_minus_gpu_bytes': int(3.4 * gib), 'peak_private_bytes': int(12.65 * gib)}
    budget = engine.memory_budget([first, steady], peaks)
    assert budget['passed'] is True and budget['ok'] == {'peak_wset': True, 'peak_private_minus_gpu': True, 'first_cycle_residual': True,
                                                         'steady_residual': True}
    assert budget['figures']['peak_private_bytes'] == int(12.65 * gib)
    assert engine.memory_budget([first], peaks)['ok']['steady_residual'] is None and engine.memory_budget([first], peaks)['passed']
    leaky = dict(steady, transformer={'residual_private_bytes': 600 * mib})
    assert engine.memory_budget([first, leaky], peaks)['ok']['steady_residual'] is False
    assert engine.memory_budget([first, steady], dict(peaks, peak_private_minus_gpu_bytes=5 * gib))['passed'] is False
    assert engine.memory_budget([first, steady], dict(peaks, peak_wset_bytes=5 * gib))['ok']['peak_wset'] is False
    assert engine.memory_budget([dict(first, vae={'residual_private_bytes': 3 * gib}), steady], peaks)['ok']['first_cycle_residual'] is False


@pytest.mark.skipif(sys.platform != 'win32', reason='GlobalMemoryStatusEx is the Windows commit counter')
def test_system_commit_reads_the_windows_commit_limit():
    commit = engine.system_commit()
    assert commit['limit_bytes'] > commit['available_bytes'] > 0 and commit['ram_available_bytes'] > 0
    assert commit['used_bytes'] == commit['limit_bytes'] - commit['available_bytes']


def test_health_reports_the_system_commit(services, tmp_path):
    service = start(services, tmp_path)
    health = service.json('GET', '/v1/health', token=None)[1]
    assert health['commit'] == COMMIT


@pytest.mark.skipif(sys.platform != 'win32', reason='the handle watch is the Windows path the launcher runs on')
def test_parent_watch_follows_a_real_process():
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        watch = server.ParentWatch(child.pid)
        assert watch.alive() is True
    finally:
        child.kill()
        child.wait(10)
    assert watch.alive() is False
    assert server.ParentWatch(os.getpid()).alive() is True
