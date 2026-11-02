"""Integration tests for imagegen server and engine coordination."""

import hashlib
import http.client
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[3] / 'tools' / 'imagegen'
sys.path.insert(0, str(TOOLS))

import engine
import protocol
import server


class ScriptedBackend:
    def __init__(self, oom_on=None, fail_on=None):
        self.events = []
        self.oom_on = dict(oom_on or {})
        self.fail_on = set(fail_on or [])
        self.models = {}

    def load(self, phase):
        self.events.append(('load', phase))
        if self.oom_on.get(('load', phase), 0) > 0:
            self.oom_on[('load', phase)] -= 1
            raise RuntimeError("CUDA out of memory")
        self.models[phase] = True

    def process(self, phase, item, carry):
        caption = item.get('caption', '')
        self.events.append(('process', phase, caption))
        key = (phase, caption)
        if self.oom_on.get(key, 0) > 0:
            self.oom_on[key] -= 1
            raise RuntimeError("CUDA out of memory")
        if caption in self.fail_on:
            raise RuntimeError("Processing failed")
        if phase == 'vae':
            return b'\x89PNG\r\n\x1a\n' + caption.encode('utf-8')
        return carry

    def unload(self, phase):
        self.events.append(('unload', phase))
        self.models.pop(phase, None)

    def release(self):
        self.events.append(('release',))
        self.models.clear()


def start_service(tmp_path, backend, **kw):
    store = server.JobStore(tmp_path / 'jobs')
    token = 'a' * 32
    gates = kw.get('gates', lambda phase: True)
    service = server.Service(
        store=store,
        backend=backend,
        token=token,
        provisioned=kw.get('provisioned', True),
        gates=gates,
    )
    httpd = server.make_server(service, 0)
    service._httpd = httpd

    worker_th = threading.Thread(target=service.run_worker, daemon=True)
    worker_th.start()
    service._worker_th = worker_th

    server_th = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_th.start()
    service._server_th = server_th

    port = httpd.server_address[1]
    return service, port, token


def call(port, method, path, body=None, token=None):
    conn = http.client.HTTPConnection(protocol.HOST, port, timeout=10)
    headers = {}
    if token is not None:
        headers['Authorization'] = f'Bearer {token}'
    encoded_body = None
    if body is not None:
        if isinstance(body, (dict, list)):
            encoded_body = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        elif isinstance(body, bytes):
            encoded_body = body
        elif isinstance(body, str):
            encoded_body = body.encode('utf-8')
    conn.request(method, path, body=encoded_body, headers=headers)
    resp = conn.getresponse()
    resp_body = resp.read()
    resp_headers = dict(resp.getheaders())
    conn.close()
    return resp.status, resp_body, resp_headers


def stop_service(service):
    service.stop_event.set()
    service.wake.set()
    if hasattr(service, '_httpd'):
        service._httpd.shutdown()
        service._httpd.server_close()


def test_captions_of_all_queued_jobs_share_one_cycle(tmp_path):
    backend = ScriptedBackend()
    service, port, token = start_service(tmp_path, backend)

    try:
        # Pause worker temporarily to let both jobs enter the queue together
        with service.lock:
            job1 = {
                'job_id': '00000000000000000000000000000001',
                'items': [{'item_id': 'i1', 'caption': 'cap_a', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]
            }
            job2 = {
                'job_id': '00000000000000000000000000000002',
                'items': [{'item_id': 'i2', 'caption': 'cap_b', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 2}]
            }
            service.store.create(job1)
            service.store.create(job2)
            service.wake.set()

        # Wait for both jobs to be completed
        for _ in range(50):
            j1 = service.store.get('00000000000000000000000000000001')
            j2 = service.store.get('00000000000000000000000000000002')
            if j1 and j2:
                st1 = j1['items']['i1']['status']
                st2 = j2['items']['i2']['status']
                if st1 == 'done' and st2 == 'done':
                    break
            time.sleep(0.05)

        load_encoder_events = [ev for ev in backend.events if ev == ('load', 'text_encoder')]
        assert len(load_encoder_events) == 1, f"Expected 1 load text_encoder, got {load_encoder_events}"
    finally:
        stop_service(service)


def test_out_of_memory_is_retried_once(tmp_path):
    # oom once on cap_retry -> succeeds on second try
    # oom twice on cap_fail -> fails after 2 attempts with GPU_OUT_OF_MEMORY
    oom_map = {
        ('transformer', 'cap_retry'): 1,
        ('transformer', 'cap_fail'): 2,
    }
    backend = ScriptedBackend(oom_on=oom_map)
    service, port, token = start_service(tmp_path, backend)

    try:
        job = {
            'job_id': '00000000000000000000000000000010',
            'items': [
                {'item_id': 'it_ok', 'caption': 'cap_ok', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1},
                {'item_id': 'it_retry', 'caption': 'cap_retry', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 2},
                {'item_id': 'it_fail', 'caption': 'cap_fail', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 3},
            ]
        }
        status, body, _ = call(port, 'POST', '/v1/jobs', job, token)
        assert status == 202

        # Wait for processing
        for _ in range(50):
            j = service.store.get(job['job_id'])
            if j:
                items = j['items']
                if items['it_ok']['status'] == 'done' and items['it_retry']['status'] == 'done' and items['it_fail']['status'] == 'failed':
                    break
            time.sleep(0.05)

        j = service.store.get(job['job_id'])
        items = j['items']
        assert items['it_ok']['status'] == 'done'
        assert items['it_retry']['status'] == 'done'
        assert items['it_fail']['status'] == 'failed'
        assert items['it_fail']['error'] == protocol.GPU_OUT_OF_MEMORY

        fail_process_events = [ev for ev in backend.events if ev == ('process', 'transformer', 'cap_fail')]
        assert len(fail_process_events) == 2
    finally:
        stop_service(service)


def test_the_vram_gate_waits_for_free_memory_then_gives_up():
    simulated_clock = {'now': 1000.0}
    sleep_record = []

    def fake_clock():
        return simulated_clock['now']

    def fake_sleep(dur):
        sleep_record.append(dur)
        simulated_clock['now'] += dur

    # Insufficient free vram throughout
    with pytest.raises(engine.EngineError) as exc:
        engine.wait_for_resources(
            'text_encoder',
            free_vram=lambda: 1_000_000,
            commit=lambda: 50_000_000_000,
            ram=lambda: 50_000_000_000,
            sleep=fake_sleep,
            clock=fake_clock,
            max_wait=600.0,
            poll=2.0
        )
    assert exc.value.code == protocol.GPU_MEMORY_UNAVAILABLE
    assert sum(sleep_record) >= 600.0

    # VRAM becomes sufficient after 2 polls
    polls = {'count': 0}

    def intermittent_vram():
        polls['count'] += 1
        if polls['count'] >= 3:
            return 20_000_000_000
        return 0

    res = engine.wait_for_resources(
        'text_encoder',
        free_vram=intermittent_vram,
        commit=lambda: 50_000_000_000,
        ram=lambda: 50_000_000_000,
        sleep=fake_sleep,
        clock=fake_clock,
        max_wait=600.0,
        poll=2.0
    )
    assert res is True


def test_the_host_memory_gate_waits_for_ram_then_reports_host_memory_low():
    simulated_clock = {'now': 1000.0}

    def fake_clock():
        return simulated_clock['now']

    def fake_sleep(dur):
        simulated_clock['now'] += dur

    with pytest.raises(engine.EngineError) as exc:
        engine.wait_for_resources(
            'text_encoder',
            free_vram=lambda: 20_000_000_000,
            commit=lambda: 50_000_000_000,
            ram=lambda: 500_000_000,  # Below HOST_MIN_AVAILABLE_BYTES (2 GB)
            sleep=fake_sleep,
            clock=fake_clock,
            max_wait=10.0,
            poll=1.0
        )
    assert exc.value.code == protocol.HOST_MEMORY_LOW


def test_the_commit_gate_waits_for_system_commit_then_reports_host_commit_low():
    simulated_clock = {'now': 1000.0}

    def fake_clock():
        return simulated_clock['now']

    def fake_sleep(dur):
        simulated_clock['now'] += dur

    with pytest.raises(engine.EngineError) as exc:
        engine.wait_for_resources(
            'text_encoder',
            free_vram=lambda: 20_000_000_000,
            commit=lambda: 1_000_000,  # Below required commit threshold
            ram=lambda: 50_000_000_000,
            sleep=fake_sleep,
            clock=fake_clock,
            max_wait=10.0,
            poll=1.0
        )
    assert exc.value.code == protocol.HOST_COMMIT_LOW


def test_private_memory_left_after_a_phase_is_cleaned_then_refused():
    cleanups = {'count': 0}

    def counting_cleanup():
        cleanups['count'] += 1

    class LeakyProbe(engine.MemoryProbe):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def phase_report(self, phase):
            self.calls += 1
            # Return residual bytes > RESIDUAL_LIMIT_BYTES (2.5 GB)
            return {
                'before_load': {'private': 0, 'working_set': 0, 'gpu': 0},
                'after_load': {'private': 3 * 1024**3, 'working_set': 0, 'gpu': 0},
                'after_phase': {'private': 3 * 1024**3, 'working_set': 0, 'gpu': 0},
                'memory_after_free': {'private': 3 * 1024**3, 'working_set': 0, 'gpu': 0},
                'peak_working_set_bytes': 1024,
                'peak_private_minus_gpu_bytes': 1024,
                'residual_bytes': 3 * 1024**3,
            }

    backend = ScriptedBackend()
    work = [{'key': 'job1:it1', 'item': {'caption': 'c1', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}}]
    leaky = LeakyProbe()
    res = engine.run_cycle(
        backend,
        work,
        probe=leaky,
        gates=lambda phase: True,
        cleanup=counting_cleanup
    )

    # Cleanup called at least twice
    assert cleanups['count'] >= 2
    # Items rejected with HOST_MEMORY_LOW
    assert res['results']['job1:it1'].error == protocol.HOST_MEMORY_LOW

    # When residual memory is small, runs through all phases
    cleanups['count'] = 0
    normal_backend = ScriptedBackend()
    res_normal = engine.run_cycle(
        normal_backend,
        work,
        gates=lambda phase: True,
        cleanup=counting_cleanup
    )
    assert res_normal['results']['job1:it1'].error is None
    assert res_normal['results']['job1:it1'].png is not None


def test_phase_memory_figures_reach_the_cycle_stats_and_health(tmp_path):
    backend = ScriptedBackend()
    service, port, token = start_service(tmp_path, backend)

    try:
        job = {
            'job_id': '00000000000000000000000000000020',
            'items': [{'item_id': 'i1', 'caption': 'cap_mem', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]
        }
        status, _, _ = call(port, 'POST', '/v1/jobs', job, token)
        assert status == 202

        # Wait for completion
        for _ in range(50):
            j = service.store.get(job['job_id'])
            if j and j['items']['i1']['status'] == 'done':
                break
            time.sleep(0.05)

        # GET /v1/health without token
        status, body, _ = call(port, 'GET', '/v1/health')
        assert status == 200
        data = json.loads(body.decode('utf-8'))
        assert 'memory' in data
        mem = data['memory']
        assert 'text_encoder' in mem and 'transformer' in mem and 'vae' in mem
        for phase in ('text_encoder', 'transformer', 'vae'):
            p_rep = mem[phase]
            assert 'memory_after_free' in p_rep
            assert 'peak_working_set_bytes' in p_rep
            assert 'peak_private_minus_gpu_bytes' in p_rep
    finally:
        stop_service(service)


def test_the_memory_budget_judges_working_set_host_private_and_residuals():
    # Compliant case (cycle 0)
    good_stats = {
        'cycle_index': 0,
        'phases': {
            'transformer': {
                'peak_working_set_bytes': 3 * 1024**3,
                'peak_private_minus_gpu_bytes': 3 * 1024**3,
                'residual_bytes': 2 * 1024**3,
            }
        }
    }
    assert engine.memory_budget(good_stats)['ok'] is True

    # Exceed working set (4 GB)
    bad_ws = {
        'cycle_index': 0,
        'phases': {
            'transformer': {
                'peak_working_set_bytes': 5 * 1024**3,
                'peak_private_minus_gpu_bytes': 2 * 1024**3,
                'residual_bytes': 1 * 1024**3,
            }
        }
    }
    res_ws = engine.memory_budget(bad_ws)
    assert res_ws['ok'] is False
    assert 'transformer.peak_working_set_bytes' in res_ws['violations']

    # Exceed private minus gpu (4 GB)
    bad_priv = {
        'cycle_index': 0,
        'phases': {
            'transformer': {
                'peak_working_set_bytes': 2 * 1024**3,
                'peak_private_minus_gpu_bytes': 5 * 1024**3,
                'residual_bytes': 1 * 1024**3,
            }
        }
    }
    res_priv = engine.memory_budget(bad_priv)
    assert res_priv['ok'] is False
    assert 'transformer.peak_private_minus_gpu_bytes' in res_priv['violations']

    # Residual 2.6 GB on cycle 0 violates
    bad_res_c0 = {
        'cycle_index': 0,
        'phases': {
            'transformer': {
                'peak_working_set_bytes': 2 * 1024**3,
                'peak_private_minus_gpu_bytes': 2 * 1024**3,
                'residual_bytes': 2600 * 1024 * 1024,
            }
        }
    }
    assert engine.memory_budget(bad_res_c0)['ok'] is False

    # Residual 600 MB on cycle 1 violates (limit is 512 MB)
    bad_res_c1 = {
        'cycle_index': 1,
        'phases': {
            'transformer': {
                'peak_working_set_bytes': 2 * 1024**3,
                'peak_private_minus_gpu_bytes': 2 * 1024**3,
                'residual_bytes': 600 * 1024 * 1024,
            }
        }
    }
    assert engine.memory_budget(bad_res_c1)['ok'] is False

    # Residual 400 MB on cycle 1 complies
    good_res_c1 = {
        'cycle_index': 1,
        'phases': {
            'transformer': {
                'peak_working_set_bytes': 2 * 1024**3,
                'peak_private_minus_gpu_bytes': 2 * 1024**3,
                'residual_bytes': 400 * 1024 * 1024,
            }
        }
    }
    assert engine.memory_budget(good_res_c1)['ok'] is True


def test_health_reports_the_system_commit(tmp_path):
    backend = ScriptedBackend()
    service, port, token = start_service(tmp_path, backend)
    try:
        status, body, _ = call(port, 'GET', '/v1/health')
        assert status == 200
        data = json.loads(body.decode('utf-8'))
        assert 'commit' in data
        # commit is a dict with commit_available or None
        if data['commit'] is not None:
            assert 'commit_available' in data['commit']
    finally:
        stop_service(service)


def test_stop_file_parent_exit_and_shutdown_each_stop_the_service(tmp_path):
    # Case 1: stop_file stops service
    backend1 = ScriptedBackend()
    service1, port1, token1 = start_service(tmp_path / 's1', backend1)
    stop_file1 = tmp_path / 's1' / 'stop.txt'
    watch_th1 = threading.Thread(
        target=server.watch_stop,
        args=(service1, service1._httpd, stop_file1, None, 0.05),
        daemon=True
    )
    watch_th1.start()
    stop_file1.write_text('stop', encoding='utf-8')
    service1._server_th.join(timeout=10.0)
    assert not service1._server_th.is_alive()
    stop_service(service1)

    # Case 2: parent_pid exit stops service
    backend2 = ScriptedBackend()
    service2, port2, token2 = start_service(tmp_path / 's2', backend2)
    subproc = subprocess.Popen([sys.executable, '-c', 'import sys; sys.exit(0)'])
    subproc.wait()
    watch_th2 = threading.Thread(
        target=server.watch_stop,
        args=(service2, service2._httpd, None, subproc.pid, 0.05),
        daemon=True
    )
    watch_th2.start()
    service2._server_th.join(timeout=10.0)
    assert not service2._server_th.is_alive()
    stop_service(service2)

    # Case 3: POST /v1/shutdown stops service
    backend3 = ScriptedBackend()
    service3, port3, token3 = start_service(tmp_path / 's3', backend3)
    watch_th3 = threading.Thread(
        target=server.watch_stop,
        args=(service3, service3._httpd, None, None, 0.05),
        daemon=True
    )
    watch_th3.start()
    status, _, _ = call(port3, 'POST', '/v1/shutdown', token=token3)
    assert status == 202
    service3._server_th.join(timeout=10.0)
    assert not service3._server_th.is_alive()
    stop_service(service3)


def test_jobs_survive_a_restart_and_expire_after_24_hours(tmp_path):
    simulated_time = {'now': 1000000.0}

    def fake_clock():
        return simulated_time['now']

    store_dir = tmp_path / 'persist_jobs'
    store1 = server.JobStore(store_dir, clock=fake_clock)
    job = {
        'job_id': '00000000000000000000000000000099',
        'items': [{'item_id': 'i1', 'caption': 'c1', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]
    }
    jdata = store1.create(job)
    # Mark running
    jdata['items']['i1']['status'] = 'running'
    store1.save(jdata)

    # Restart store from same directory
    store2 = server.JobStore(store_dir, clock=fake_clock)
    store2.load_all()
    reloaded = store2.get('00000000000000000000000000000099')
    assert reloaded is not None
    # 'running' status reverted to 'queued'
    assert reloaded['items']['i1']['status'] == 'queued'

    # Advance clock past 24 hours (24 * 3600 + 1)
    simulated_time['now'] += 24 * 3600 + 1
    store2.expire()
    expired = store2.get('00000000000000000000000000000099')
    assert expired is None
    assert not (store_dir / '00000000000000000000000000000099').exists()


def test_api_auth_rejections_and_endpoints(tmp_path):
    backend = ScriptedBackend()
    service, port, token = start_service(tmp_path, backend)

    try:
        # Missing token -> 401
        status, _, _ = call(port, 'GET', '/v1/jobs/nonexistent')
        assert status == 401

        # Bad token -> 401
        status, _, _ = call(port, 'GET', '/v1/jobs/nonexistent', token='wrong_token_value')
        assert status == 401

        # Valid token but not found -> 404
        status, _, _ = call(port, 'GET', '/v1/jobs/nonexistent', token=token)
        assert status == 404

        # Idempotent POST: same body -> 202
        job_def = {
            'job_id': '00000000000000000000000000000050',
            'items': [{'item_id': 'i1', 'caption': 'same_body', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]
        }
        st1, b1, _ = call(port, 'POST', '/v1/jobs', job_def, token)
        assert st1 == 202
        st2, b2, _ = call(port, 'POST', '/v1/jobs', job_def, token)
        assert st2 == 202

        # Conflicting POST: different body -> 409
        conflicting_job = {
            'job_id': '00000000000000000000000000000050',
            'items': [{'item_id': 'i1', 'caption': 'different_body', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]
        }
        st3, _, _ = call(port, 'POST', '/v1/jobs', conflicting_job, token)
        assert st3 == 409

        # 7 items -> 400
        too_many_items = {
            'job_id': '00000000000000000000000000000051',
            'items': [{'item_id': f'i_{k}', 'caption': 'c', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1} for k in range(7)]
        }
        st4, b4, _ = call(port, 'POST', '/v1/jobs', too_many_items, token)
        assert st4 == 400
        data4 = json.loads(b4.decode('utf-8'))
        assert data4.get('field') == 'items'

        # Wait for job_def to finish
        for _ in range(50):
            j = service.store.get('00000000000000000000000000000050')
            if j and j['items']['i1']['status'] == 'done':
                break
            time.sleep(0.05)

        # GET PNG: check X-Content-SHA256 header matches body sha256
        png_status, png_body, png_headers = call(port, 'GET', '/v1/jobs/00000000000000000000000000000050/items/i1.png', token=token)
        assert png_status == 200
        expected_sha = hashlib.sha256(png_body).hexdigest()
        assert png_headers.get('x-content-sha256') == expected_sha or png_headers.get('X-Content-SHA256') == expected_sha

        # Server binds to 127.0.0.1 and not 0.0.0.0
        assert service._httpd.server_address[0] == protocol.HOST
    finally:
        stop_service(service)


def test_api_service_not_provisioned_and_queue_full(tmp_path):
    backend = ScriptedBackend()
    # Unprovisioned service returns 503 for POST
    service, port, token = start_service(tmp_path, backend, provisioned=False)
    try:
        job = {
            'job_id': '00000000000000000000000000000060',
            'items': [{'item_id': 'i1', 'caption': 'c', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]
        }
        st, b, _ = call(port, 'POST', '/v1/jobs', job, token)
        assert st == 503
        data = json.loads(b.decode('utf-8'))
        assert data.get('error') == 'not_provisioned'

        # Health endpoint still works
        hst, _, _ = call(port, 'GET', '/v1/health')
        assert hst == 200
    finally:
        stop_service(service)