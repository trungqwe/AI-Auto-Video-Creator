"""IMGGEN-LAUNCH: launcher khởi chạy, canh và dừng sidecar ảnh minh hoạ (Deps.start_imagegen, cmd_serve, cmd_status); không DB, GPU, torch
hay mạng ngoài loopback.

Double: ScriptedProcess (tiến trình con giả ghi terminate và kill), ScriptedHandle (sidecar giả cho cmd_serve) và ScriptedSidecar (máy chủ
HTTP trên cổng tạm của loopback nói phần API mà launcher dùng). Hai test cuối chạy tools/imagegen/server.py thật bằng interpreter của runtime
khoá (server chỉ cần thư viện chuẩn khi chưa nạp mô hình): dòng lệnh, token và tệp dừng của launcher phải khớp CLI của sidecar.

coveredIds: OI-CP7-11-Q2
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import functools
import http.client
import http.server
import importlib.util
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
IMAGEGEN_DIR = ROOT / 'tools' / 'imagegen'
SEVEN_COMMANDS = ('start', 'stop', 'down', 'status', 'backup', 'restore', 'oauth')
REVISION = '337337621b8526e120f2275d250242f4a6bedd75'
JOB_BODY = {'job_id': 'a' * 32, 'items': [{'item_id': 'i1', 'caption': 'A quiet street at dusk, wet asphalt, soft light.', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]}
NO_WAIT = {'stop_file_wait': 0.01, 'grace': 0.01, 'kill_wait': 0.01}


@pytest.fixture(scope='module')
def launcher():
    spec = importlib.util.spec_from_file_location('imggen_launch_launcher', LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_protocol():
    spec = importlib.util.spec_from_file_location('imggen_launch_protocol', IMAGEGEN_DIR / 'protocol.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def wait_until(check, seconds=60.0, step=0.1):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(step)
    return None


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


class ScriptedProcess:
    """Tiến trình con giả: ghi lại wait, terminate và kill, và thoát đúng lúc kịch bản định (exit_on: 'wait:<n>', 'terminate', 'kill')."""

    def __init__(self, pid=4343, exit_on=None):
        self.pid = pid
        self.returncode = None
        self.calls = []
        self.exit_on = dict(exit_on or {})

    def exit(self, code=0):
        if self.returncode is None:
            self.returncode = code

    def _maybe_exit(self, action):
        if action in self.exit_on:
            self.exit(self.exit_on[action])

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.calls.append(('wait', timeout))
        self._maybe_exit(f"wait:{sum(1 for call in self.calls if call[0] == 'wait')}")
        if self.returncode is None:
            raise subprocess.TimeoutExpired('scripted', timeout)
        return self.returncode

    def terminate(self):
        self.calls.append(('terminate',))
        self._maybe_exit('terminate')

    def kill(self):
        self.calls.append(('kill',))
        self._maybe_exit('kill')


class ScriptedSidecar:
    """Máy chủ HTTP giả trên cổng tạm của loopback: GET /v1/health không cần token, POST /v1/shutdown cần bearer token (và cho tiến trình giả thoát)."""

    def __init__(self, token='t' * 43, health=None, process=None, delay=0.0, reply=None):
        self.token = token
        self.process = process
        self.delay = delay
        self.reply = reply
        self.requests = []
        self.health_body = health if health is not None else {
            'service': 'aiavc-imagegen', 'state': 'idle', 'phase': None, 'revision': REVISION, 'queue': {'jobs': 2, 'items': 5}}
        double = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, format, *args):  # noqa: A002
                pass

            def _send(self, status, body):
                try:
                    self.send_response(status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass

            def do_GET(self):  # noqa: N802
                double.requests.append(('GET', self.path, self.headers.get('Authorization')))
                if double.delay:
                    time.sleep(double.delay)
                if double.reply is not None:
                    self._send(*double.reply)
                elif self.path == '/v1/health':
                    self._send(200, json.dumps(double.health_body).encode('utf-8'))
                else:
                    self._send(404, b'{}')

            def do_POST(self):  # noqa: N802
                double.requests.append(('POST', self.path, self.headers.get('Authorization')))
                if self.path == '/v1/shutdown' and self.headers.get('Authorization') == f'Bearer {double.token}':
                    if double.process is not None:
                        double.process.exit(0)
                    self._send(202, b'{"stopping":true}')
                else:
                    self._send(401, b'{}')

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


@pytest.fixture
def double():
    made = []

    def make(**kwargs):
        made.append(ScriptedSidecar(**kwargs))
        return made[-1]

    yield make
    for item in made:
        item.close()


class ScriptedHandle:
    """Sidecar giả cho cmd_serve: health() trả lần lượt các trạng thái (None là chưa trả lời; trạng thái cuối lặp lại), stop() ghi vào events."""

    def __init__(self, events, states=('idle',), exit_code=None, stop_error=None, missing=()):
        self.events = events
        self.states = list(states)
        self._exit_code = exit_code
        self.stop_error = stop_error
        self.missing = list(missing)
        self.port = 57030

    def exit_code(self):
        return self._exit_code

    def health(self):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if state is None:
            return None
        body = {'service': 'aiavc-imagegen', 'state': state, 'phase': None, 'revision': REVISION, 'queue': {'jobs': 0, 'items': 0}}
        if state == 'not_provisioned':
            body['missing'] = self.missing
        return body

    def stop(self):
        self.events.append(('sidecar_stopped',))
        if self.stop_error is not None:
            raise self.stop_error


def build_deps(launcher, tmp_path, events, **over):
    def note(name):
        def record(*args, **kwargs):
            events.append((name, *args))
        return record

    def start_worker(app, layout):
        events.append(('start_worker',))
        return SimpleNamespace(stop=lambda: events.append(('worker_stopped',)))

    def serve_tls(app, *, port, certfile, keyfile, on_ready, should_stop):
        events.append(('serve_tls', port))

    deps = launcher.Deps(
        environ={'AIAVC_DATA_DIR': str(tmp_path / 'data')},
        run=lambda cmd, **kwargs: SimpleNamespace(returncode=0, stdout='', stderr=''),
        spawn=lambda cmd, **kwargs: SimpleNamespace(pid=4242),
        out=lambda message: events.append(('out', str(message))),
        ask=lambda prompt='': '',
        sleep=lambda seconds: events.append(('sleep', seconds)),
        wait_tcp=lambda host, port, timeout: True,
        pid_alive=lambda pid: False,
        migrate=note('migrate'),
        ensure_identity=note('identity'),
        begin_session=note('begin_session'),
        end_session=note('end_session'),
        max_session_epoch=lambda dsn, workspace_id: 0,
        make_cert=lambda cert, key: None,
        open_browser=lambda url: True,
        run_consent=lambda *args, **kwargs: None,
        load_app=lambda env, layout: SimpleNamespace(launch_url=lambda actor_id, ttl_seconds=60: 'https://127.0.0.1:8443/launch?cap=IMGGEN'),
        start_worker=start_worker,
        serve_tls=serve_tls,
        now=lambda: datetime.datetime(2026, 11, 2, 9, 0, 0, tzinfo=datetime.timezone.utc),
        ensure_namespace=lambda host, port: 'EXISTS',
    )
    return dataclasses.replace(deps, **over) if over else deps


def serving(launcher, tmp_path, events, handle, **over):
    """Chạy cmd_serve với start_imagegen trả handle (ghi một sự kiện start_imagegen); trả (rc, layout, deps). Sự kiện nằm trong events."""

    def start_imagegen(layout, environ):
        events.append(('start_imagegen', layout, environ))
        return handle

    deps = build_deps(launcher, tmp_path, events, **{'start_imagegen': start_imagegen, **over})
    rc = launcher.cmd_serve(deps, SimpleNamespace())
    return rc, launcher.resolve_layout(deps.environ), deps


def names(events):
    return [event[0] for event in events if event[0] not in ('out', 'sleep')]


def lines(events):
    return [event[1] for event in events if event[0] == 'out']


def provisioned_layout(launcher, tmp_path):
    layout = launcher.resolve_layout({'AIAVC_DATA_DIR': str(tmp_path / 'data')})
    layout.imagegen_python.parent.mkdir(parents=True)
    layout.imagegen_python.write_bytes(b'')
    return layout


def spawn_recorder(calls, **process_args):
    def spawn(argv, **kwargs):
        process = ScriptedProcess(**process_args)
        calls.append((argv, kwargs, process))
        return process
    return spawn


def test_deps_has_an_optional_start_imagegen_and_the_cli_wires_the_real_one(launcher, tmp_path, monkeypatch):
    fields = {field.name: field for field in dataclasses.fields(launcher.Deps)}
    assert fields['start_imagegen'].default is None
    assert launcher.default_deps({'AIAVC_DATA_DIR': str(tmp_path / 'data')}).start_imagegen is None
    assert launcher.COMMANDS == SEVEN_COMMANDS
    seen = []
    monkeypatch.setattr(launcher, 'cmd_status', lambda deps, args: seen.append(deps) or 0)
    assert launcher.main(['status']) == 0
    assert seen[0].start_imagegen is launcher.start_imagegen
    assert seen[0].seed_media is launcher.seed_media and seen[0].seed_defaults is launcher.seed_defaults


def test_constants_match_the_sidecar_protocol_and_the_launcher_imports_nothing_of_it(launcher):
    protocol = load_protocol()
    assert launcher.IMAGEGEN_PORT == protocol.DEFAULT_PORT == 57030
    assert launcher.IMAGEGEN_TOKEN_ENV == protocol.TOKEN_ENV
    assert launcher.IMAGEGEN_SERVICE == protocol.SERVICE_NAME
    assert len(secrets.token_urlsafe(launcher.IMAGEGEN_TOKEN_BYTES)) >= protocol.TOKEN_MIN_CHARS
    assert launcher.IMAGEGEN_SERVER == IMAGEGEN_DIR / 'server.py' and launcher.IMAGEGEN_SERVER.is_file()
    text = LAUNCHER_PATH.read_text(encoding='utf-8')
    assert 'from tools' not in text and 'from src.' not in text
    imported = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
    assert not imported & {'tools', 'imagegen', 'server', 'engine', 'protocol', 'weights', 'torch', 'diffusers', 'transformers'}


def test_layout_names_the_sidecar_paths_inside_the_data_dir(launcher, tmp_path):
    layout = launcher.resolve_layout({'AIAVC_DATA_DIR': str(tmp_path / 'data')})
    data = layout.data_dir
    assert layout.hf_hub_dir == data / 'models' / 'hf-hub'
    assert layout.imagegen_dir == data / 'imagegen'
    assert layout.imagegen_python == data / 'imagegen' / 'venv' / 'Scripts' / 'python.exe'
    assert layout.imagegen_out_dir == data / 'imagegen' / 'out'
    assert layout.imagegen_endpoint_file == data / 'imagegen' / 'endpoint.json'
    assert layout.imagegen_log == data / 'logs' / 'imagegen.log'


def test_serve_starts_the_sidecar_before_the_worker_and_stops_it_after_the_worker(launcher, tmp_path):
    events = []
    rc, layout, deps = serving(launcher, tmp_path, events, ScriptedHandle(events))
    assert rc == 0
    assert names(events) == ['start_imagegen', 'start_worker', 'serve_tls', 'worker_stopped', 'sidecar_stopped']
    started = next(event for event in events if event[0] == 'start_imagegen')
    assert started[1] == layout and started[2] is deps.environ
    ready = [line for line in lines(events) if 'Sidecar ảnh minh hoạ' in line]
    assert len(ready) == 1 and 'idle' in ready[0] and 'revision 337337621b85' in ready[0] and '0 job, 0 ảnh' in ready[0]
    assert not layout.pid_file.exists()


@pytest.mark.parametrize('error, fragment', [
    (None, None),
    ('launcher', 'chưa cài (not provisioned)'),
    ('generic', 'RuntimeError'),
], ids=['no_sidecar', 'launcher_error', 'unexpected_error'])
def test_a_sidecar_that_cannot_start_never_blocks_the_app(launcher, tmp_path, error, fragment):
    events = []

    def start_imagegen(layout, environ):
        if error == 'launcher':
            raise launcher.LauncherError('Sidecar ảnh minh hoạ chưa cài (not provisioned): thiếu X.')
        if error == 'generic':
            raise RuntimeError('CANARY-SECRET-IMG')
        return None

    deps = build_deps(launcher, tmp_path, events, start_imagegen=start_imagegen)
    assert launcher.cmd_serve(deps, SimpleNamespace()) == 0
    assert names(events) == ['start_worker', 'serve_tls', 'worker_stopped']
    text = '\n'.join(lines(events))
    assert (fragment is None) or (fragment in text)
    assert 'CANARY-SECRET-IMG' not in text


def test_a_not_provisioned_sidecar_is_reported_in_one_clear_line_and_the_app_still_starts(launcher, tmp_path):
    events = []
    handle = ScriptedHandle(events, states=('not_provisioned',), missing=['black-forest-labs/flux-3-image-klein/text_encoder/a.safetensors', 'b', 'c'])
    rc, layout, _ = serving(launcher, tmp_path, events, handle)
    assert rc == 0 and 'serve_tls' in names(events)
    clear = [line for line in lines(events) if 'not provisioned' in line]
    assert len(clear) == 1
    assert '3 tệp' in clear[0] and 'text_encoder/a.safetensors' in clear[0] and 'provision.py' in clear[0] and 'Ứng dụng vẫn khởi động' in clear[0]
    assert not any(event[0] == 'sleep' for event in events)


def test_the_start_waits_at_most_five_seconds_for_a_verifying_sidecar(launcher, tmp_path):
    assert launcher.IMAGEGEN_READY_POLLS * launcher.IMAGEGEN_READY_POLL_SECONDS == 5.0
    events = []
    rc, _, _ = serving(launcher, tmp_path, events, ScriptedHandle(events, states=('verifying',)))
    sleeps = [event[1] for event in events if event[0] == 'sleep']
    assert rc == 0 and len(sleeps) == launcher.IMAGEGEN_READY_POLLS and sum(sleeps) == 5.0
    assert any('chưa báo xong kiểm trọng số' in line for line in lines(events))
    assert names(events) == ['start_imagegen', 'start_worker', 'serve_tls', 'worker_stopped', 'sidecar_stopped']
    events = []
    rc, _, _ = serving(launcher, tmp_path, events, ScriptedHandle(events, states=('verifying', None, 'idle')))
    assert rc == 0 and sum(1 for event in events if event[0] == 'sleep') == 2
    assert any('idle' in line for line in lines(events))


def test_the_ready_wait_is_capped_by_the_clock_when_every_poll_is_slow(launcher, tmp_path, monkeypatch):
    class SlowHandle(ScriptedHandle):
        def health(self):
            time.sleep(0.5)
            return None

    monkeypatch.setattr(launcher, 'IMAGEGEN_READY_POLL_SECONDS', 0.05)
    events = []
    deps = build_deps(launcher, tmp_path, events, sleep=time.sleep)
    started = time.monotonic()
    launcher.announce_imagegen(deps, launcher.resolve_layout(deps.environ), SlowHandle(events))
    assert time.monotonic() - started < 5.0
    assert any('chưa báo xong' in line for line in lines(events))


def test_a_sidecar_that_exits_at_once_is_reported_with_its_code_and_still_cleaned_up(launcher, tmp_path):
    events = []
    rc, _, _ = serving(launcher, tmp_path, events, ScriptedHandle(events, exit_code=3))
    assert rc == 0 and 'serve_tls' in names(events) and names(events)[-1] == 'sidecar_stopped'
    report = [line for line in lines(events) if 'thoát ngay' in line]
    assert len(report) == 1 and 'mã 3' in report[0] and 'cổng đang bị tiến trình khác chiếm' in report[0] and 'imagegen.log' in report[0]


def test_a_failed_worker_start_stops_the_sidecar(launcher, tmp_path):
    events = []

    def refuse(app, layout):
        events.append(('start_worker',))
        raise launcher.LauncherError('BLOCKED: thiếu cổng ProductionRuntime')

    rc, _, _ = serving(launcher, tmp_path, events, ScriptedHandle(events), start_worker=refuse)
    assert rc == 1 and names(events) == ['start_imagegen', 'start_worker', 'sidecar_stopped']
    events = []

    def explode(app, layout):
        raise RuntimeError('worker exploded')

    with pytest.raises(RuntimeError):
        serving(launcher, tmp_path, events, ScriptedHandle(events), start_worker=explode)
    assert names(events) == ['start_imagegen', 'sidecar_stopped']


def test_the_sidecar_stops_when_serve_tls_fails_and_a_stop_error_is_only_logged(launcher, tmp_path):
    events = []

    def failing_serve(app, *, port, certfile, keyfile, on_ready, should_stop):
        raise RuntimeError('serve_tls failed')

    with pytest.raises(RuntimeError):
        serving(launcher, tmp_path, events, ScriptedHandle(events), serve_tls=failing_serve)
    assert names(events) == ['start_imagegen', 'start_worker', 'worker_stopped', 'sidecar_stopped']
    events = []
    rc, layout, _ = serving(launcher, tmp_path, events, ScriptedHandle(events, stop_error=RuntimeError('CANARY-STOP')))
    text = '\n'.join(lines(events))
    assert rc == 0 and 'Không dừng gọn được sidecar ảnh minh hoạ (RuntimeError)' in text and 'CANARY-STOP' not in text
    assert not layout.pid_file.exists() and not layout.stop_file.exists()


def test_start_imagegen_builds_the_documented_command_and_a_scrubbed_environment(launcher, tmp_path):
    layout = provisioned_layout(launcher, tmp_path)
    environ = {'AIAVC_DATA_DIR': str(layout.data_dir), 'CONTROLPLANE_DSN': 'postgresql://controlplane:CANARY-PG@127.0.0.1:57028/controlplane',
               'HF_TOKEN': 'CANARY-HF', 'SYSTEMROOT': 'C:/Windows', 'HTTPS_PROXY': 'http://127.0.0.1:9', 'AIAVC_IMAGEGEN_TOKEN': 'stale-token'}
    calls = []
    sidecar = launcher.start_imagegen(layout, environ, spawn=spawn_recorder(calls, pid=7001))
    argv, kwargs, process = calls[0]
    assert argv == [str(layout.imagegen_python), '-I', str(IMAGEGEN_DIR / 'server.py'), '--port', '57030',
                    '--hub', str(layout.data_dir / 'models' / 'hf-hub'), '--out', str(layout.data_dir / 'imagegen' / 'out'),
                    '--parent-pid', str(os.getpid()), '--stop-file', str(layout.stop_file)]
    env = kwargs['env']
    token = env['AIAVC_IMAGEGEN_TOKEN']
    assert len(token) >= 32 and token != 'stale-token' and token not in ' '.join(argv)
    assert env['HF_HUB_OFFLINE'] == '1' and env['TRANSFORMERS_OFFLINE'] == '1'
    assert 'CONTROLPLANE_DSN' not in env and 'HF_TOKEN' not in env and 'AIAVC_DATA_DIR' not in env
    assert env['SYSTEMROOT'] == 'C:/Windows' and env['HTTPS_PROXY'] == 'http://127.0.0.1:9'
    assert kwargs['cwd'] == str(launcher.ROOT) and kwargs['stdin'] is subprocess.DEVNULL and kwargs['stderr'] is subprocess.STDOUT
    assert kwargs['stdout'].name == str(layout.imagegen_log)
    assert isinstance(sidecar, launcher.ImagegenSidecar) and sidecar.pid == 7001 and sidecar.process is process and sidecar.port == 57030


def test_each_start_gets_a_fresh_token_and_the_endpoint_file_names_it(launcher, tmp_path):
    layout = provisioned_layout(launcher, tmp_path)
    calls = []
    first = launcher.start_imagegen(layout, {}, spawn=spawn_recorder(calls, pid=7001))
    endpoint = json.loads(layout.imagegen_endpoint_file.read_text(encoding='utf-8'))
    assert endpoint == {'url': 'http://127.0.0.1:57030', 'token': first.token, 'pid': 7001}
    second = launcher.start_imagegen(layout, {}, spawn=spawn_recorder(calls, pid=7002))
    assert first.token != second.token and calls[0][1]['env']['AIAVC_IMAGEGEN_TOKEN'] == first.token
    assert json.loads(layout.imagegen_endpoint_file.read_text(encoding='utf-8'))['token'] == second.token
    assert first.token not in layout.imagegen_log.read_text(encoding='utf-8')


def test_start_imagegen_refuses_without_the_private_environment_or_the_sidecar_source(launcher, tmp_path, monkeypatch):
    layout = launcher.resolve_layout({'AIAVC_DATA_DIR': str(tmp_path / 'data')})
    calls = []
    layout.imagegen_endpoint_file.parent.mkdir(parents=True)
    layout.imagegen_endpoint_file.write_text(json.dumps({'url': 'x', 'token': 'left-by-a-crashed-run', 'pid': 1}), encoding='utf-8')
    with pytest.raises(launcher.LauncherError) as missing:
        launcher.start_imagegen(layout, {}, spawn=spawn_recorder(calls))
    assert 'not provisioned' in str(missing.value) and str(layout.imagegen_python) in str(missing.value)
    assert not layout.imagegen_endpoint_file.exists()
    layout.imagegen_python.parent.mkdir(parents=True)
    layout.imagegen_python.write_bytes(b'')
    monkeypatch.setattr(launcher, 'IMAGEGEN_SERVER', tmp_path / 'absent' / 'server.py')
    with pytest.raises(launcher.LauncherError) as no_source:
        launcher.start_imagegen(layout, {}, spawn=spawn_recorder(calls))
    assert 'mã nguồn' in str(no_source.value)
    assert calls == [] and not layout.imagegen_endpoint_file.exists()


def test_stop_leaves_a_sidecar_that_obeys_the_stop_file_alone(launcher, tmp_path, double):
    layout = provisioned_layout(launcher, tmp_path)
    process = ScriptedProcess(exit_on={'wait:1': 0})
    served = double()
    sidecar = launcher.ImagegenSidecar(process, layout, served.token, served.port)
    layout.imagegen_endpoint_file.write_text(json.dumps({'url': 'x', 'token': served.token, 'pid': 1}), encoding='utf-8')
    layout.stop_file.parent.mkdir(parents=True, exist_ok=True)
    layout.stop_file.write_text('stop', encoding='utf-8')
    assert sidecar.stop(**NO_WAIT) == 0
    assert served.requests == [] and process.calls == [('wait', 0.01)]
    assert not layout.imagegen_endpoint_file.exists()


def test_stop_posts_shutdown_with_the_bearer_token_when_the_stop_file_is_not_enough(launcher, tmp_path, double):
    layout = provisioned_layout(launcher, tmp_path)
    process = ScriptedProcess()
    served = double(process=process)
    sidecar = launcher.ImagegenSidecar(process, layout, served.token, served.port)
    assert not layout.stop_file.exists()
    assert sidecar.stop(**NO_WAIT) == 0
    assert served.requests == [('POST', '/v1/shutdown', f'Bearer {served.token}')]
    assert process.calls == [('wait', 0.01)]


def test_stop_terminates_then_kills_a_sidecar_that_ignores_everything(launcher, tmp_path, double):
    layout = provisioned_layout(launcher, tmp_path)
    process = ScriptedProcess(exit_on={'kill': -9})
    served = double()
    sidecar = launcher.ImagegenSidecar(process, layout, 'not-the-token', served.port)
    layout.stop_file.parent.mkdir(parents=True, exist_ok=True)
    layout.stop_file.write_text('stop', encoding='utf-8')
    assert sidecar.stop(stop_file_wait=0.01, grace=0.02, kill_wait=0.03) == -9
    assert process.calls == [('wait', 0.01), ('wait', 0.02), ('terminate',), ('wait', 0.03), ('kill',), ('wait', 0.03)]
    assert served.requests == [('POST', '/v1/shutdown', 'Bearer not-the-token')]
    again = len(process.calls)
    assert sidecar.stop(**NO_WAIT) == -9 and len(process.calls) == again


def test_stop_of_an_exited_sidecar_only_forgets_its_own_endpoint(launcher, tmp_path, double):
    layout = provisioned_layout(launcher, tmp_path)
    served = double()
    process = ScriptedProcess()
    process.exit(4)
    sidecar = launcher.ImagegenSidecar(process, layout, served.token, served.port)
    layout.imagegen_endpoint_file.write_text(json.dumps({'url': 'x', 'token': 'someone-elses', 'pid': 1}), encoding='utf-8')
    assert sidecar.stop() == 4
    assert layout.imagegen_endpoint_file.exists() and served.requests == [] and process.calls == []
    layout.imagegen_endpoint_file.write_text(json.dumps({'url': 'x', 'token': served.token, 'pid': 1}), encoding='utf-8')
    sidecar.stop()
    assert not layout.imagegen_endpoint_file.exists()


def test_the_health_probe_reads_only_a_real_sidecar_answer(launcher, double):
    served = double()
    health = launcher.fetch_imagegen_health(served.port)
    assert health['state'] == 'idle' and health['queue'] == {'jobs': 2, 'items': 5} and served.requests == [('GET', '/v1/health', None)]
    other_service = double(health={'service': 'something-else', 'state': 'idle'})
    assert launcher.fetch_imagegen_health(other_service.port) is None
    for reply in ((200, b'not json'), (200, b'[1, 2]'), (500, b'{"service": "aiavc-imagegen"}'), (200, b'\xff\xfe')):
        assert launcher.fetch_imagegen_health(double(reply=reply).port) is None
    slow = double(delay=0.6)
    assert launcher.fetch_imagegen_health(slow.port, timeout=0.2) is None
    assert launcher.fetch_imagegen_health(free_port(), timeout=0.3) is None


def test_status_prints_the_sidecar_health_or_not_provisioned_or_not_running(launcher, tmp_path, double, monkeypatch):
    events = []
    deps = build_deps(launcher, tmp_path, events, start_imagegen=lambda layout, environ: None)
    layout = launcher.resolve_layout(deps.environ)
    password = launcher.load_or_create_password(layout)
    served = double()
    monkeypatch.setattr(launcher, 'IMAGEGEN_PORT', served.port)
    assert launcher.cmd_status(deps, SimpleNamespace()) == 0
    line = next(text for text in lines(events) if 'Sidecar ảnh minh hoạ' in text)
    assert f'cổng {served.port}' in line and 'idle' in line and 'revision 337337621b85' in line and '2 job, 5 ảnh' in line
    events.clear()
    served.health_body = {'service': 'aiavc-imagegen', 'state': 'not_provisioned', 'revision': REVISION, 'missing': ['x/a.safetensors', 'y']}
    assert launcher.cmd_status(deps, SimpleNamespace()) == 0
    line = next(text for text in lines(events) if 'Sidecar ảnh minh hoạ' in text)
    assert 'not provisioned' in line and '2 tệp' in line and 'x/a.safetensors' in line
    events.clear()
    monkeypatch.setattr(launcher, 'IMAGEGEN_PORT', free_port())
    monkeypatch.setattr(launcher, 'IMAGEGEN_HTTP_TIMEOUT_SECONDS', 0.3)
    assert launcher.cmd_status(deps, SimpleNamespace()) == 0
    assert 'chưa cài (not provisioned)' in next(text for text in lines(events) if 'Sidecar ảnh minh hoạ' in text)
    events.clear()
    layout.imagegen_python.parent.mkdir(parents=True)
    layout.imagegen_python.write_bytes(b'')
    assert launcher.cmd_status(deps, SimpleNamespace()) == 0
    assert 'không chạy (not running)' in next(text for text in lines(events) if 'Sidecar ảnh minh hoạ' in text)
    assert password not in '\n'.join(lines(events)) and served.token not in '\n'.join(lines(events))


def real_sidecar(launcher, tmp_path, monkeypatch):
    """Khởi chạy server.py thật qua start_imagegen: chỉ đổi interpreter của môi trường uv riêng (không có trong lane) bằng interpreter của runtime khoá."""
    layout = provisioned_layout(launcher, tmp_path)
    port = free_port()
    monkeypatch.setattr(launcher, 'IMAGEGEN_PORT', port)

    def spawn(argv, **kwargs):
        return subprocess.Popen([sys.executable, *argv[1:]], **kwargs)

    sidecar = launcher.start_imagegen(layout, dict(os.environ), spawn=spawn)

    def ready():
        assert sidecar.exit_code() is None, f'sidecar thật thoát với mã {sidecar.exit_code()}: {layout.imagegen_log.read_text(encoding="utf-8")[-600:]}'
        health = launcher.fetch_imagegen_health(port, timeout=10)
        return bool(health) and health.get('state') in ('not_provisioned', 'idle')

    try:
        assert wait_until(ready), 'sidecar thật không sẵn sàng sau 60 giây'
    except BaseException:
        sidecar.stop(stop_file_wait=0, grace=1, kill_wait=1)
        raise
    return layout, sidecar, port


def post_job(port, token):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
    try:
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        connection.request('POST', '/v1/jobs', body=json.dumps(JOB_BODY).encode('utf-8'), headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read().decode('utf-8'))
    finally:
        connection.close()


def test_the_real_sidecar_takes_the_launchers_token_and_stops_on_the_launchers_stop_file(launcher, tmp_path, monkeypatch):
    layout, sidecar, port = real_sidecar(launcher, tmp_path, monkeypatch)
    try:
        health = launcher.fetch_imagegen_health(port, timeout=10)
        assert health['state'] == 'not_provisioned' and health['revision'] == REVISION and health['queue'] == {'jobs': 0, 'items': 0}
        assert 'not provisioned' in launcher.describe_imagegen_health(health, port)
        token = json.loads(layout.imagegen_endpoint_file.read_text(encoding='utf-8'))['token']
        assert post_job(port, None)[0] == 401 and post_job(port, 'x' * 43)[0] == 401
        status, body = post_job(port, token)
        assert status == 503 and body['error']['code'] == 'NOT_PROVISIONED'
        events = []
        deps = build_deps(launcher, tmp_path, events, start_imagegen=lambda layout, environ: None)
        assert launcher.cmd_status(deps, SimpleNamespace()) == 0
        assert any('not provisioned' in line and f'cổng {port}' in line for line in lines(events))
        announced = []
        launcher.announce_imagegen(dataclasses.replace(deps, out=announced.append, sleep=time.sleep), layout, sidecar)
        assert len(announced) == 1 and 'not provisioned' in announced[0] and 'provision.py' in announced[0]
        layout.stop_file.parent.mkdir(parents=True, exist_ok=True)
        layout.stop_file.write_text('stop', encoding='utf-8')
        assert sidecar.stop(stop_file_wait=30, grace=30, kill_wait=5) == 0
        assert not layout.imagegen_endpoint_file.exists()
        log = layout.imagegen_log.read_text(encoding='utf-8')
        assert 'NOT provisioned' in log and token not in log
    finally:
        sidecar.stop(stop_file_wait=0, grace=1, kill_wait=1)


def test_the_real_sidecar_stops_on_shutdown_without_a_stop_file(launcher, tmp_path, monkeypatch):
    layout, sidecar, port = real_sidecar(launcher, tmp_path, monkeypatch)
    try:
        assert not layout.stop_file.exists()
        assert sidecar.stop(stop_file_wait=30, grace=30, kill_wait=5) == 0
        monkeypatch.setattr(launcher, 'IMAGEGEN_HTTP_TIMEOUT_SECONDS', 0.3)
        assert launcher.fetch_imagegen_health(port) is None
        assert not layout.imagegen_endpoint_file.exists()
    finally:
        sidecar.stop(stop_file_wait=0, grace=1, kill_wait=1)


def test_serve_with_the_real_sidecar_reports_not_provisioned_and_leaves_nothing_running(launcher, tmp_path, monkeypatch):
    layout = provisioned_layout(launcher, tmp_path)
    port = free_port()
    monkeypatch.setattr(launcher, 'IMAGEGEN_PORT', port)
    seen = {}
    events = []

    def spawn(argv, **kwargs):
        return subprocess.Popen([sys.executable, *argv[1:]], **kwargs)

    def serve_tls(app, *, port, certfile, keyfile, on_ready, should_stop):
        events.append(('serve_tls', port))
        seen['health'] = launcher.fetch_imagegen_health(timeout=10)
        seen['endpoint'] = json.loads(layout.imagegen_endpoint_file.read_text(encoding='utf-8'))

    deps = build_deps(launcher, tmp_path, events, start_imagegen=functools.partial(launcher.start_imagegen, spawn=spawn), sleep=time.sleep, serve_tls=serve_tls)
    deps = dataclasses.replace(deps, environ={**os.environ, 'AIAVC_DATA_DIR': str(tmp_path / 'data')})
    assert launcher.cmd_serve(deps, SimpleNamespace()) == 0
    assert names(events) == ['start_worker', 'serve_tls', 'worker_stopped']
    clear = [line for line in lines(events) if 'not provisioned' in line]
    assert len(clear) == 1 and f'cổng {port}' in clear[0]
    assert seen['health']['state'] == 'not_provisioned' and seen['endpoint']['url'] == f'http://127.0.0.1:{port}'
    monkeypatch.setattr(launcher, 'IMAGEGEN_HTTP_TIMEOUT_SECONDS', 0.3)
    assert launcher.fetch_imagegen_health() is None
    assert not layout.imagegen_endpoint_file.exists() and not layout.pid_file.exists()
