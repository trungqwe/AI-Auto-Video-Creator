"""Kiểm thử tích hợp ADAPT-LAUNCH bằng subprocess giả, không chạy Docker.

coveredIds: PW-W1-01
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import hashlib
import importlib.util
import json
import os
import re
import sys
from types import SimpleNamespace
from pathlib import Path
import typing
import pytest

ROOT = Path(__file__).resolve().parents[4]
LAUNCHER_PATH = ROOT / "tools" / "launcher" / "launcher.py"
COMPOSE_PATH = ROOT / "tools" / "launcher" / "docker-compose.yml"
LOCK_PATH = ROOT / "tools" / "runtime" / "runtime.lock.json"
PROFILE_PATH = ROOT / "tools" / "launcher" / "prod" / "profile.json"
RUNBOOK_PATH = ROOT / "docs" / "runbook" / "runbook-v1.md"

@pytest.fixture(scope="module")
def launcher():
    spec = importlib.util.spec_from_file_location("adapt_launch_launcher", LAUNCHER_PATH)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m

class FakeRun:
    def __init__(self, returncodes: dict[str, int] | None = None):
        self.calls: list[tuple[list[str], dict[str, typing.Any]]] = []
        self.returncodes = returncodes or {}

    def __call__(self, cmd: list[str], **kw: typing.Any) -> SimpleNamespace:
        self.calls.append((cmd, kw))
        if kw.get("stdout") is not None and hasattr(kw["stdout"], "write"):
            kw["stdout"].write(b"PGDMP-fake")
        cmd_str = " ".join(str(c) for c in cmd)
        code = 0
        for pattern, rc in self.returncodes.items():
            if pattern in cmd_str:
                code = rc
                break
        return SimpleNamespace(returncode=code, stdout="", stderr="")

class FakeProc:
    def __init__(self, pid: int = 4242):
        self.pid = pid

    def poll(self) -> None:
        return None

@dataclasses.dataclass
class Fx:
    launcher: typing.Any
    deps: typing.Any
    run: FakeRun
    out: list[str]
    events: list[typing.Any]
    alive: set[int]
    layout: typing.Any

def make_fx(launcher: typing.Any, tmp_path: Path, **over: typing.Any) -> Fx:
    environ = {"AIAVC_DATA_DIR": str(tmp_path / "data")}
    try:
        layout = launcher.resolve_layout(environ)
    except Exception:
        layout = None
    out_list: list[str] = []
    events: list[typing.Any] = []
    alive: set[int] = set()
    fake_run = FakeRun()

    def fake_out(msg: str) -> None:
        out_list.append(str(msg))

    def fake_ask(prompt: str = "") -> str:
        events.append(("ask", prompt))
        return ""

    def fake_sleep(sec: float) -> None:
        events.append(("sleep", sec))

    def fake_wait_tcp(host: str, port: int, timeout: float) -> bool:
        events.append(("wait_tcp", port))
        return True

    def fake_pid_alive(pid: int) -> bool:
        return pid in alive

    def fake_migrate(dsn: str) -> None:
        events.append(("migrate", dsn))

    def fake_ensure_identity(dsn: str, ws: str, actor: str) -> None:
        events.append(("identity", ws, actor))

    def fake_make_cert(cert_p: Path, key_p: Path) -> None:
        cert_p.parent.mkdir(parents=True, exist_ok=True)
        key_p.parent.mkdir(parents=True, exist_ok=True)
        cert_p.write_bytes(b"CERT")
        key_p.write_bytes(b"KEY")
        events.append(("cert",))

    def fake_open_browser(url: str) -> bool:
        events.append(("browser", url))
        return True

    def fake_spawn(cmd: list[str], **kw: typing.Any) -> FakeProc:
        events.append(("spawn", cmd, kw))
        alive.add(4242)
        return FakeProc(4242)

    def fake_run_consent(client_p: Path, vault_p: Path, timeout: int, present_url: typing.Callable[[str], None]) -> SimpleNamespace:
        events.append(("run_consent", client_p, vault_p, timeout))
        return SimpleNamespace(secret_ref="drive-primary-oauth", fingerprint="v1")

    def fake_load_app(env: dict[str, str], lay: typing.Any) -> SimpleNamespace:
        events.append(("load_app",))
        return SimpleNamespace(launch_url=lambda actor_id, ttl_seconds=60: "https://127.0.0.1:8443/launch?cap=CAP-CANARY-9")

    def fake_start_worker(app: typing.Any, lay: typing.Any) -> SimpleNamespace:
        events.append(("start_worker",))
        return SimpleNamespace(stop=lambda: events.append(("worker_stopped",)))

    def fake_serve_tls(app: typing.Any, *, port: int, certfile: Path, keyfile: Path, on_ready: typing.Callable[[], None], should_stop: typing.Callable[[], bool]) -> None:
        events.append(("serve_tls", port))
        on_ready()

    def fake_now() -> datetime.datetime:
        return datetime.datetime(2026, 10, 22, 3, 4, 5, tzinfo=datetime.timezone.utc)

    def fake_ensure_namespace(host: str, port: int) -> str:
        events.append(("namespace", host, port))
        return "REGISTERED"

    def fake_begin_session(dsn: str, ws: str, ref: str, epoch: str) -> None:
        events.append(("begin_session", dsn, ws, ref, epoch))

    def fake_end_session(dsn: str, ws: str, ref: str) -> None:
        events.append(("end_session", dsn, ws, ref))

    def fake_max_session_epoch(dsn: str, ws: str) -> int:
        events.append(("max_session_epoch", dsn, ws))
        return 0

    def fake_seed_defaults(dsn: str, ws: str, actor: str, epoch: str) -> None:
        events.append(("seed_defaults", dsn, ws, actor, epoch))

    deps = launcher.Deps(
        environ=environ,
        run=fake_run,
        spawn=fake_spawn,
        out=fake_out,
        ask=fake_ask,
        sleep=fake_sleep,
        wait_tcp=fake_wait_tcp,
        pid_alive=fake_pid_alive,
        migrate=fake_migrate,
        ensure_identity=fake_ensure_identity,
        begin_session=fake_begin_session,
        end_session=fake_end_session,
        max_session_epoch=fake_max_session_epoch,
        make_cert=fake_make_cert,
        open_browser=fake_open_browser,
        run_consent=fake_run_consent,
        load_app=fake_load_app,
        start_worker=fake_start_worker,
        serve_tls=fake_serve_tls,
        now=fake_now,
        ensure_namespace=fake_ensure_namespace,
        seed_defaults=fake_seed_defaults,
    )
    if over:
        deps = dataclasses.replace(deps, **over)
    return Fx(launcher=launcher, deps=deps, run=fake_run, out=out_list, events=events, alive=alive, layout=layout)

def test_compose_images_pinned_by_lock_digest():
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    images = re.findall(r"^\s*image:\s*(\S+)\s*$", text, re.M)
    assert len(images) == 3
    pattern = r"^[a-z0-9./-]+:[0-9][0-9.]*@sha256:[0-9a-f]{64}$"
    for img in images:
        assert re.match(pattern, img), f"Invalid image format: {img}"
        assert "latest" not in img
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    postgres_digest = "sha256:" + lock["pins"]["postgresql_image"]["sha256"]
    temporal_digest = "sha256:" + lock["pins"]["temporal_server_binary"]["sha256"]
    admin_tools_image = "temporalio/admin-tools:1.31.2@sha256:dbc5fcd6ee8f0f4d808bf765af9a87dea9d8a283abfdcfbd2fc148496ba66107"
    assert images[0].split("@")[1] == postgres_digest
    assert images[2].split("@")[1] == temporal_digest
    assert images[1] == admin_tools_image
    assert images[1].startswith("temporalio/admin-tools:" + lock["versions"]["temporal_server"] + "@")
    assert images[2].startswith("temporalio/server:")
    assert lock["versions"]["postgresql"] in images[0]
    assert lock["versions"]["temporal_server"] in images[1]
    assert lock["versions"]["temporal_server"] in images[2]

def test_compose_ports_loopback_only():
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    ports = set()
    in_ports = False
    for line in text.splitlines():
        if re.match(r"^\s*ports:\s*$", line):
            in_ports = True
            continue
        if in_ports:
            stripped = line.strip()
            if stripped.startswith("- "):
                val = stripped[2:].strip().strip('"\'')
                ports.add(val)
            else:
                in_ports = False
    assert ports == {"127.0.0.1:57028:5432", "127.0.0.1:7233:7233"}
    assert "0.0.0.0" not in text
    assert "8233" not in text and "7243" not in text

def test_compose_temporal_schema_command_single_shell_string():
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    block_match = re.search(r"^  temporal-schema:\n(.*?)(?=^  \S|^\S|\Z)", text, re.M | re.S)
    assert block_match, "Thiếu service temporal-schema"
    block = block_match.group(1)
    assert re.search(r'^    entrypoint: \["/bin/sh", "-c"\]\s*$', block, re.M)
    cmd_match = re.search(r"^    command:[ \t]*\r?\n((?:      .*(?:\r?\n|\Z))+)", block, re.M)
    assert cmd_match, "command phải là danh sách YAML (khoá command: rồi các dòng '- ' thụt vào)"
    lines = [ln for ln in cmd_match.group(1).splitlines() if ln.strip()]
    items = [ln for ln in lines if re.match(r"^      - ", ln)]
    assert len(items) == 1, "command phải có đúng một phần tử"
    assert lines[0].strip() == "- >-"
    assert all(ln.startswith("        ") for ln in lines[1:]), "thân chuỗi gấp dòng phải thụt sâu hơn phần tử"
    command = " ".join(ln.strip() for ln in lines[1:])
    assert command.startswith("set -e;")
    assert command.count("temporal-sql-tool") == 6
    calls = re.findall(r"temporal-sql-tool\s+--db\s+(temporal(?:_visibility)?)\s+(create|setup-schema|update-schema)\b", command)
    assert calls == [
        ("temporal", "create"),
        ("temporal", "setup-schema"),
        ("temporal", "update-schema"),
        ("temporal_visibility", "create"),
        ("temporal_visibility", "setup-schema"),
        ("temporal_visibility", "update-schema"),
    ]
    assert "-d /etc/temporal/schema/postgresql/v12/temporal/versioned" in command
    assert "-d /etc/temporal/schema/postgresql/v12/visibility/versioned" in command

def test_compose_named_volume_and_no_secret():
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "aiavc_pgdata:/var/lib/postgresql" in text
    assert re.search(r"^volumes:\s*\n\s*aiavc_pgdata:", text, re.M)
    for line in text.splitlines():
        if "- aiavc_pgdata" in line:
            assert not line.strip().startswith("- ./") and ":\\" not in line
        if any(k in line for k in ["POSTGRES_PASSWORD:", "POSTGRES_PWD:", "SQL_PASSWORD:"]):
            assert "${AIAVC_PG_PASSWORD" in line


def test_compose_temporal_dynamic_config_mounted_readonly():
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    block_match = re.search(r"^  temporal:\r?\n(.*?)(?=^  \S|^\S|\Z)", text, re.M | re.S)
    assert block_match, "Thiếu service temporal"
    block = block_match.group(1)
    mount = "./temporal-dynamicconfig.yaml:/etc/temporal/config/dynamicconfig/docker.yaml:ro"
    vol_match = re.search(r"^    volumes:[ \t]*\r?\n((?:      - .*(?:\r?\n|\Z))+)", block, re.M)
    assert vol_match, "service temporal thiếu khoá volumes"
    volumes = [ln.strip()[2:].strip().strip('"\'') for ln in vol_match.group(1).splitlines() if ln.strip()]
    assert mount in volumes
    env_match = re.search(r"^      DYNAMIC_CONFIG_FILE_PATH:[ \t]*\"?([^\"\s]+)\"?[ \t]*$", block, re.M)
    assert env_match, "Thiếu DYNAMIC_CONFIG_FILE_PATH"
    assert env_match.group(1) == "/etc/temporal/config/dynamicconfig/docker.yaml"
    config_path = ROOT / "tools" / "launcher" / "temporal-dynamicconfig.yaml"
    assert config_path.is_file()
    lines = [ln.strip() for ln in config_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    comments = [ln for ln in lines if ln.startswith("#")]
    body = [ln for ln in lines if not ln.startswith("#")]
    assert len(comments) == 1
    assert body == ["{}"]


def test_launcher_top_level_imports_stdlib_only():
    text = LAUNCHER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in sys.stdlib_module_names, f"Non-stdlib module import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                assert root in sys.stdlib_module_names, f"Non-stdlib module import: {node.module}"
    allowed = {"controlplane", "main", "psycopg", "cryptography", "temporalio", "uvicorn"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in sys.stdlib_module_names or root in allowed, f"Forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                assert root in sys.stdlib_module_names or root in allowed, f"Forbidden import: {node.module}"
    assert "from src." not in text
    assert "0.0.0.0" not in text

def test_commands_are_the_seven(launcher):
    assert launcher.COMMANDS == ("start", "stop", "down", "status", "backup", "restore", "oauth")

def test_layout_outside_git_tree(launcher, tmp_path):
    d = tmp_path / "data"
    layout = launcher.resolve_layout({"AIAVC_DATA_DIR": str(d)})
    for prop in ["tls_dir", "secrets_dir", "vault_dir", "staging_dir", "models_dir", "backups_dir", "state_dir", "logs_dir"]:
        p = getattr(layout, prop)
        assert isinstance(p, Path)
    with pytest.raises(launcher.LauncherError):
        launcher.resolve_layout({"AIAVC_DATA_DIR": str(launcher.ROOT / "sub")})
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(launcher.LauncherError):
        launcher.resolve_layout({"AIAVC_DATA_DIR": str(repo / "data")})
    with pytest.raises(launcher.LauncherError):
        launcher.resolve_layout({})
    layout2 = launcher.resolve_layout({"LOCALAPPDATA": str(tmp_path / "AppData" / "Local")})
    assert layout2.data_dir.name == "AIAutoVideoCreator"

def test_password_created_once_and_private(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    p1 = launcher.load_or_create_password(fx.layout)
    p2 = launcher.load_or_create_password(fx.layout)
    assert p1 == p2
    assert len(p1) >= 32
    assert fx.layout.password_file.parent == fx.layout.secrets_dir
    dsn = launcher.build_dsn(p1)
    assert dsn.startswith("postgresql://controlplane:")
    assert "@127.0.0.1:57028/controlplane" in dsn

def test_start_orders_steps_and_hides_secret(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    rc = launcher.cmd_start(fx.deps, SimpleNamespace())
    assert rc == 0
    first_cmd, first_kw = fx.run.calls[0]
    assert first_cmd == ["docker", "compose", "-p", "aiavc", "-f", str(launcher.COMPOSE_FILE), "up", "-d"]
    assert first_kw["env"]["AIAVC_PG_PASSWORD"]
    assert any(call[0] == ["docker", "exec", "aiavc-postgres", "pg_isready", "-U", "controlplane", "-d", "controlplane"] for call in fx.run.calls)
    ev_names = []
    for ev in fx.events:
        if ev[0] == "wait_tcp":
            ev_names.append(f"wait_tcp_{ev[1]}")
        else:
            ev_names.append(ev[0])
    expected_order = ["wait_tcp_7233", "namespace", "migrate", "identity", "cert", "spawn", "wait_tcp_8443"]
    sub_evs = [e for e in ev_names if e in expected_order]
    assert sub_evs == expected_order
    namespace_ev = [ev for ev in fx.events if ev[0] == "namespace"][0]
    assert namespace_ev[1:] == ("127.0.0.1", 7233)
    assert any("Namespace Temporal default" in line for line in fx.out)
    migrate_ev = [ev for ev in fx.events if ev[0] == "migrate"][0]
    assert ":57028/" in migrate_ev[1]
    spawn_ev = [ev for ev in fx.events if ev[0] == "spawn"][0]
    assert spawn_ev[1] == [sys.executable, str(launcher.LAUNCHER_FILE), "_serve"]
    child_env = spawn_ev[2]["env"]
    assert child_env["CONTROLPLANE_PROFILE"] == "production"
    assert child_env["CONTROLPLANE_PORT"] == "8443"
    assert child_env["CONTROLPLANE_PROFILE_PATH"]
    assert child_env["CONTROLPLANE_WORKSPACE_ID"]
    assert child_env["CONTROLPLANE_DSN"]
    password = first_kw["env"]["AIAVC_PG_PASSWORD"]
    for cmd, _ in fx.run.calls:
        for arg in cmd:
            assert password not in arg
    for arg in spawn_ev[1]:
        assert password not in arg
    all_out = "\n".join(fx.out)
    assert password not in all_out
    assert not any(ev[0] == "browser" for ev in fx.events)
    for cmd, _ in fx.run.calls:
        if "compose" in cmd:
            for flag in ["-v", "--volumes", "--rmi", "rm", "prune", "volume"]:
                assert flag not in cmd

def test_start_fails_closed_when_compose_fails(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.deps.run.returncodes["compose"] = 1
    with pytest.raises(launcher.LauncherError):
        launcher.cmd_start(fx.deps, SimpleNamespace())
    assert not any(ev[0] == "migrate" for ev in fx.events)
    assert not any(ev[0] == "spawn" for ev in fx.events)

def test_start_fails_closed_when_temporal_namespace_cannot_be_ensured(launcher, tmp_path):
    # Ổn định hoá 25/10/2026 (S5): image temporalio/server không tự đăng ký namespace default; thiếu nó thì không workflow nào chạy.
    def failing_namespace(host: str, port: int) -> str:
        raise launcher.LauncherError("Namespace Temporal default chưa sẵn sàng sau 60 giây.")
    fx = make_fx(launcher, tmp_path, ensure_namespace=failing_namespace)
    with pytest.raises(launcher.LauncherError):
        launcher.cmd_start(fx.deps, SimpleNamespace())
    assert not any(ev[0] == "migrate" for ev in fx.events)
    assert not any(ev[0] == "spawn" for ev in fx.events)


def test_worker_stop_waits_for_the_worker_thread_not_a_lost_future(launcher, monkeypatch):
    # Ổn định hoá 25/10/2026 (S6): khi các worker dừng, group.run() xong và loop của luồng worker dừng trước khi task
    # group.stop() hoàn tất; stop() từng chờ future đó đủ STOP_GRACE_SECONDS (60 giây) dù worker đã dừng.
    import asyncio
    import time as _time
    launcher.ensure_src_on_path()
    import temporalio.client
    import controlplane.api.wiring.workflow as workflow_wiring
    import controlplane.api.wiring.production as production_wiring
    import controlplane.api.wiring.production_profile as profile_wiring
    seen = {}

    class FakeClient:
        @staticmethod
        async def connect(target, namespace="default", **kw):
            seen["connect"] = (target, namespace)
            return SimpleNamespace()

    class FakeGroup:
        def __init__(self, client, registration, *, graceful_shutdown_seconds):
            self.done = None

        async def run(self):
            self.done = asyncio.Event()
            await self.done.wait()

        async def stop(self):
            seen["stopped"] = True
            self.done.set()
            await asyncio.sleep(0.2)

    import controlplane.application.orchestration.capability_view as capability_view
    import controlplane.application.orchestration.grant_runtime as grant_runtime
    import controlplane.infrastructure.db.orchestration.collection_scheduler as scheduler_module
    import controlplane.infrastructure.db.orchestration.outbox_relay as relay_module

    class IdleLoop:
        def __init__(self, *args, **kw):
            pass

        async def run_forever(self, stop_event, *args):
            await stop_event.wait()
            seen.setdefault("background_stopped", []).append(type(self).__name__)

    class FakeRelay(IdleLoop):
        pass

    class FakeScheduler(IdleLoop):
        pass

    class FakeStarter(IdleLoop):
        pass

    monkeypatch.setattr(temporalio.client, "Client", FakeClient)
    monkeypatch.setattr(workflow_wiring, "assemble_activity_handlers", lambda **kw: {})
    monkeypatch.setattr(launcher, "assemble_dfe_handlers", lambda *a, **kw: {})
    monkeypatch.setattr(workflow_wiring, "build_workflow_services", lambda **kw: SimpleNamespace(settings=SimpleNamespace()))
    monkeypatch.setattr(workflow_wiring, "wrap_dispatcher", lambda services, **kw: services)
    monkeypatch.setattr(workflow_wiring, "build_capability_probes", lambda **kw: {})
    monkeypatch.setattr(workflow_wiring, "build_temporal_registration", lambda services, **kw: SimpleNamespace())
    monkeypatch.setattr(grant_runtime, "build_grant_issuer", lambda *a, **k: (lambda *x: None))
    monkeypatch.setattr(capability_view, "CapabilityReader", lambda probes: (lambda: {}))
    monkeypatch.setattr(relay_module, "OutboxRelay", FakeRelay)
    monkeypatch.setattr(scheduler_module, "CollectionScheduler", FakeScheduler)
    monkeypatch.setattr(scheduler_module, "EnrichmentStarter", FakeStarter)
    monkeypatch.setattr(production_wiring, "TemporalWorkerGroup", FakeGroup)
    parameters = {"collection.tiers": {"tier_1": "x"}, "collection.collection_interval_minutes": 180}
    monkeypatch.setattr(profile_wiring, "load_production_profile", lambda path: SimpleNamespace(parameters=parameters))
    monkeypatch.setattr(launcher, "STOP_GRACE_SECONDS", 5)
    runtime = SimpleNamespace(ffmpeg_path=Path("ffmpeg.exe"), runtime_lock_path=Path("runtime.lock.json"), gpu_lease=SimpleNamespace())
    app = SimpleNamespace(
        manager=SimpleNamespace(dsn="postgresql://unused"),
        workspace_id="ws-1",
        services={"collection": SimpleNamespace(), "storage": SimpleNamespace()},
        api_app=SimpleNamespace(state=SimpleNamespace(production_runtime=runtime)),
    )
    handle = launcher.start_worker(app, None)
    _time.sleep(0.3)
    started = _time.monotonic()
    handle.stop()
    assert seen.get("stopped") is True
    assert _time.monotonic() - started < 2, "stop waited for a future the stopped loop never resolves"
    assert seen["connect"] == ("127.0.0.1:7233", "default")
    assert sorted(seen["background_stopped"]) == ["FakeRelay", "FakeScheduler", "FakeStarter"]


def test_default_deps_ensure_the_temporal_namespace(launcher):
    deps = launcher.default_deps({})
    assert deps.ensure_namespace is launcher.ensure_temporal_namespace
    assert launcher.TEMPORAL_NAMESPACE == "default"
    assert launcher.TEMPORAL_RETENTION_SECONDS > 0


def test_start_is_noop_when_worker_running(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.layout.ensure_dirs()
    fx.layout.pid_file.write_text("4242", encoding="utf-8")
    fx.alive.add(4242)
    rc = launcher.cmd_start(fx.deps, SimpleNamespace())
    assert rc == 0
    assert fx.run.calls == []
    assert not any(ev[0] == "spawn" for ev in fx.events)

def test_stop_only_signals_worker_never_docker(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.layout.ensure_dirs()
    fx.layout.pid_file.write_text("4242", encoding="utf-8")
    fx.alive.add(4242)
    def custom_sleep(sec):
        if fx.layout.stop_file.exists():
            fx.alive.discard(4242)
    fx.deps.sleep = custom_sleep
    rc = launcher.cmd_stop(fx.deps, SimpleNamespace())
    assert rc == 0
    assert fx.run.calls == []
    assert not fx.layout.pid_file.exists()

def test_stop_without_worker(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    rc = launcher.cmd_stop(fx.deps, SimpleNamespace())
    assert rc == 0
    assert fx.run.calls == []

def test_stop_reports_failure_when_worker_does_not_exit(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.layout.ensure_dirs()
    fx.layout.pid_file.write_text("4242", encoding="utf-8")
    fx.alive.add(4242)
    rc = launcher.cmd_stop(fx.deps, SimpleNamespace())
    assert rc == 1
    assert fx.run.calls == []

def test_down_stops_worker_then_compose_down_keeps_volumes(launcher, tmp_path):
    fh = make_fx(launcher, tmp_path)
    fh.layout.ensure_dirs()
    fh.layout.pid_file.write_text("4242", encoding="utf-8")
    fh.alive.add(4242)
    def custom_sleep(sec):
        if fh.layout.stop_file.exists():
            fh.alive.discard(4242)
    fh.deps.sleep = custom_sleep
    rc = launcher.cmd_down(fh.deps, SimpleNamespace())
    assert rc == 0
    assert fh.run.calls[-1][0] == ["docker", "compose", "-p", "aiavc", "-f", str(launcher.COMPOSE_FILE), "down"]
    for cmd, _ in fh.run.calls:
        for flag in ["-v", "--volumes", "--rmi", "volume", "rm", "prune"]:
            assert flag not in cmd

def test_status_prints_state_without_secrets(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    pw = launcher.load_or_create_password(fx.layout)
    rc = launcher.cmd_status(fx.deps, SimpleNamespace())
    assert rc == 0
    assert any(cmd[-1] == "ps" for cmd, _ in fx.run.calls)
    all_out = "\n".join(fx.out)
    assert pw not in all_out

def test_backup_uses_pg_dump_via_docker_exec(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    rc = launcher.cmd_backup(fx.deps, SimpleNamespace(out=None))
    assert rc == 0
    expected_cmd = ["docker", "exec", "aiavc-postgres", "pg_dump", "-U", "controlplane", "-Fc", "-d", "controlplane"]
    assert any(cmd == expected_cmd for cmd, _ in fx.run.calls)
    dump_file = fx.layout.backups_dir / "aiavc-20261022T030405Z.dump"
    assert dump_file.exists()
    assert dump_file.read_bytes() == b"PGDMP-fake"
    sha_file = fx.layout.backups_dir / "aiavc-20261022T030405Z.dump.sha256"
    assert sha_file.exists()
    expected_sha = hashlib.sha256(b"PGDMP-fake").hexdigest()
    assert expected_sha in sha_file.read_text(encoding="utf-8")
    for cmd, _ in fx.run.calls:
        for arg in cmd:
            assert "AIAVC_PG_PASSWORD" not in arg

def test_backup_failure_removes_partial_file(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.deps.run.returncodes["pg_dump"] = 1
    with pytest.raises(launcher.LauncherError):
        launcher.cmd_backup(fx.deps, SimpleNamespace(out=None))
    dump_file = fx.layout.backups_dir / "aiavc-20261022T030405Z.dump"
    assert not dump_file.exists()

def test_restore_creates_new_database_and_new_recovery_epoch(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.layout.ensure_dirs()
    dump = fx.layout.backups_dir / "test.dump"
    dump.write_bytes(b"PGDMP-fake")
    dump.with_name("test.dump.sha256").write_text(hashlib.sha256(b"PGDMP-fake").hexdigest(), encoding="utf-8")
    rc = launcher.cmd_restore(fx.deps, SimpleNamespace(file=str(dump), yes=True))
    assert rc == 0
    cmd_names = [(call[0][4] if len(call[0]) > 4 and call[0][2] == "-i" else call[0][3]) for call in fx.run.calls if len(call[0]) > 3]
    assert "pg_isready" in cmd_names
    assert "createdb" in cmd_names
    assert "pg_restore" in cmd_names
    createdb_call = [call for call in fx.run.calls if call[0][3] == "createdb"][0]
    assert createdb_call[0] == ["docker", "exec", "aiavc-postgres", "createdb", "-U", "controlplane", "controlplane_20261022030405"]
    pg_restore_call = [call for call in fx.run.calls if "pg_restore" in call[0]][0]
    assert pg_restore_call[0] == ["docker", "exec", "-i", "aiavc-postgres", "pg_restore", "-U", "controlplane", "-d", "controlplane_20261022030405", "--no-owner", "--exit-on-error"]
    assert pg_restore_call[1].get("stdin") is not None
    assert not any("dropdb" in call[0] for call in fx.run.calls)
    assert not any("DROP" in str(call[0]) for call in fx.run.calls)
    assert fx.layout.active_db_file.read_text(encoding="utf-8").strip() == "controlplane_20261022030405"
    epoch_data = json.loads(fx.layout.epoch_file.read_text(encoding="utf-8"))
    last_hist = epoch_data["history"][-1]
    assert last_hist["epoch"] == "1"
    assert last_hist["database"] == "controlplane_20261022030405"
    assert last_hist["source_sha256"] == hashlib.sha256(b"PGDMP-fake").hexdigest()
    t2 = datetime.datetime(2026, 10, 22, 3, 4, 6, tzinfo=datetime.timezone.utc)
    fx.deps.now = lambda: t2
    rc2 = launcher.cmd_restore(fx.deps, SimpleNamespace(file=str(dump), yes=True))
    assert rc2 == 0
    epoch_data2 = json.loads(fx.layout.epoch_file.read_text(encoding="utf-8"))
    assert len(epoch_data2["history"]) == 2
    assert epoch_data2["history"][-1]["epoch"] != last_hist["epoch"]
    assert epoch_data2["history"][-1]["epoch"] == "2"
    assert launcher.active_db_name(fx.layout) == "controlplane_20261022030406"

def test_restore_refuses_bad_inputs(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.layout.ensure_dirs()
    dump = fx.layout.backups_dir / "test.dump"
    dump.write_bytes(b"PGDMP-fake")
    dump.with_name("test.dump.sha256").write_text("bad_checksum", encoding="utf-8")
    with pytest.raises(launcher.LauncherError):
        launcher.cmd_restore(fx.deps, SimpleNamespace(file=str(dump), yes=True))
    assert fx.run.calls == []
    dump.with_name("test.dump.sha256").write_text(hashlib.sha256(b"PGDMP-fake").hexdigest(), encoding="utf-8")
    fx.layout.pid_file.write_text("4242", encoding="utf-8")
    fx.alive.add(4242)
    with pytest.raises(launcher.LauncherError):
        launcher.cmd_restore(fx.deps, SimpleNamespace(file=str(dump), yes=True))
    fx.alive.clear()
    rc = launcher.cmd_restore(fx.deps, SimpleNamespace(file=str(dump), yes=False))
    assert rc != 0
    assert not any("createdb" in str(call[0]) for call in fx.run.calls)

def test_restore_failure_drops_only_new_database(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.layout.ensure_dirs()
    dump = fx.layout.backups_dir / "test.dump"
    dump.write_bytes(b"PGDMP-fake")
    dump.with_name("test.dump.sha256").write_text(hashlib.sha256(b"PGDMP-fake").hexdigest(), encoding="utf-8")
    fx.deps.run.returncodes["pg_restore"] = 1
    with pytest.raises(launcher.LauncherError):
        launcher.cmd_restore(fx.deps, SimpleNamespace(file=str(dump), yes=True))
    drop_calls = [call[0] for call in fx.run.calls if len(call[0]) > 3 and call[0][3] == "dropdb"]
    assert len(drop_calls) == 1
    assert drop_calls[0] == ["docker", "exec", "aiavc-postgres", "dropdb", "-U", "controlplane", "--if-exists", "controlplane_20261022030405"]
    assert not fx.layout.active_db_file.exists()
    assert not fx.layout.epoch_file.exists()

def test_oauth_prints_vietnamese_steps_then_calls_flow(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.layout.ensure_dirs()
    client_file = fx.layout.secrets_dir / "oauth-client.json"
    client_file.write_text("{}", encoding="utf-8")
    rc = launcher.cmd_oauth(fx.deps, SimpleNamespace())
    assert rc == 0
    all_out = "\n".join(fx.out)
    assert "Bước 1" in all_out
    assert "Bước 2" in all_out
    assert "Bước 3" in all_out
    assert "drive.file" in all_out
    assert any(ord(c) > 127 for c in all_out)
    consent_calls = [ev for ev in fx.events if ev[0] == "run_consent"]
    assert len(consent_calls) == 1
    assert consent_calls[0][1] == client_file
    assert consent_calls[0][2] == fx.layout.vault_dir
    assert consent_calls[0][3] == 300
    assert "drive-primary-oauth" in all_out

def test_oauth_missing_client_file(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    rc = launcher.cmd_oauth(fx.deps, SimpleNamespace())
    assert rc == 2
    assert not any(ev[0] == "run_consent" for ev in fx.events)
    all_out = "\n".join(fx.out)
    assert any(ord(c) > 127 for c in all_out)

def test_oauth_failure_does_not_echo_exception(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    fx.layout.ensure_dirs()
    client_file = fx.layout.secrets_dir / "oauth-client.json"
    client_file.write_text("{}", encoding="utf-8")
    def bad_run_consent(*args, **kw):
        raise RuntimeError("CANARY-SECRET-123")
    fx.deps.run_consent = bad_run_consent
    rc = launcher.cmd_oauth(fx.deps, SimpleNamespace())
    assert rc == 1
    all_out = "\n".join(fx.out)
    assert "CANARY-SECRET-123" not in all_out
    assert "RuntimeError" in all_out

def test_serve_issues_one_time_capability_and_opens_launch_url(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    identity = launcher.load_or_create_identity(fx.layout)
    received_actor = []
    class FakeApp:
        def launch_url(self, actor_id: str, ttl_seconds: int = 60) -> str:
            received_actor.append(actor_id)
            return "https://127.0.0.1:8443/launch?cap=CAP-CANARY-9"
    worker_stopped = []
    class FakeWorker:
        def stop(self) -> None:
            worker_stopped.append(True)
    serve_kw = {}
    def custom_serve_tls(app, *, port, certfile, keyfile, on_ready, should_stop):
        serve_kw["port"] = port
        serve_kw["certfile"] = certfile
        serve_kw["keyfile"] = keyfile
        serve_kw["should_stop"] = should_stop
        on_ready()
    fx.deps.load_app = lambda env, lay: FakeApp()
    fx.deps.start_worker = lambda app, lay: FakeWorker()
    fx.deps.serve_tls = custom_serve_tls
    rc = launcher.cmd_serve(fx.deps, SimpleNamespace())
    assert rc == 0
    browser_calls = [ev for ev in fx.events if ev[0] == "browser"]
    assert len(browser_calls) == 1
    assert browser_calls[0][1] == "https://127.0.0.1:8443/launch?cap=CAP-CANARY-9"
    assert received_actor == [identity["actor_id"]]
    all_out = "\n".join(fx.out)
    assert "CAP-CANARY-9" not in all_out
    assert worker_stopped == [True]
    assert not fx.layout.pid_file.exists()
    assert serve_kw["port"] == 8443
    assert serve_kw["certfile"] == fx.layout.cert_file
    assert serve_kw["keyfile"] == fx.layout.key_file
    fx.layout.stop_file.write_text("stop", encoding="utf-8")
    assert serve_kw["should_stop"]() is True

def test_serve_blocked_ports_message(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    def bad_load_app(*a, **k):
        raise launcher.LauncherError("BLOCKED: thiếu cổng ProductionRuntime")
    fx.deps.load_app = bad_load_app
    rc = launcher.cmd_serve(fx.deps, SimpleNamespace())
    assert rc != 0
    assert not any(ev[0] == "start_worker" for ev in fx.events)
    assert not any(ev[0] == "browser" for ev in fx.events)


def test_load_runtime_ports_wires_build_production_ports(launcher, tmp_path, monkeypatch):
    launcher.ensure_src_on_path()
    import controlplane.infrastructure.production_ports.assembly as assembly
    from controlplane.infrastructure.production_ports.ports_config import load_ports_config
    layout = launcher.resolve_layout({"AIAVC_DATA_DIR": str(tmp_path / "data")})
    profile = SimpleNamespace(name="profile-canary")
    sentinel = {"route_catalog": object()}
    calls = []
    def fake_build(*args, **kwargs):
        calls.append((args, kwargs))
        return sentinel
    monkeypatch.setattr(assembly, "build_production_ports", fake_build)
    result = launcher._load_runtime_ports(layout, profile)
    assert result is sentinel
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (profile,)
    assert args[0] is profile
    assert kwargs["vault_dir"] == layout.vault_dir
    assert kwargs["staging_dir"] == layout.staging_dir
    assert kwargs["state_dir"] == layout.state_dir
    assert kwargs["oauth_client_secrets_path"] == layout.secrets_dir / "oauth-client.json"
    assert kwargs["ports_config"] == load_ports_config(ROOT / "tools" / "launcher" / "prod" / "ports.json")
    assert set(kwargs) == {"vault_dir", "staging_dir", "state_dir", "oauth_client_secrets_path", "ports_config"}


def test_load_runtime_ports_wraps_exception_as_blocked(launcher, tmp_path, monkeypatch):
    launcher.ensure_src_on_path()
    import controlplane.infrastructure.production_ports.assembly as assembly
    layout = launcher.resolve_layout({"AIAVC_DATA_DIR": str(tmp_path / "data")})
    def boom(*args, **kwargs):
        raise RuntimeError("x")
    monkeypatch.setattr(assembly, "build_production_ports", boom)
    with pytest.raises(launcher.LauncherError) as exc:
        launcher._load_runtime_ports(layout, SimpleNamespace(name="profile-canary"))
    message = str(exc.value)
    assert message.startswith("BLOCKED:")
    assert "RuntimeError" in message


def test_make_self_signed_cert_has_loopback_san(launcher, tmp_path):
    cert_p = tmp_path / "cert.pem"
    key_p = tmp_path / "key.pem"
    launcher.make_self_signed_cert(cert_p, key_p)
    assert cert_p.exists() and key_p.exists()
    import cryptography.x509
    cert = cryptography.x509.load_pem_x509_certificate(cert_p.read_bytes())
    san = cert.extensions.get_extension_for_oid(cryptography.x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    ips = [str(x) for x in san.get_values_for_type(cryptography.x509.IPAddress)]
    dns = [str(x) for x in san.get_values_for_type(cryptography.x509.DNSName)]
    assert "127.0.0.1" in ips
    assert "localhost" in dns
    diff = cert.not_valid_after_utc - cert.not_valid_before_utc
    assert diff.days <= 400

def test_pid_alive_current_process(launcher):
    assert launcher.pid_alive(os.getpid()) is True
    assert launcher.pid_alive(2**22 + 12345) is False
    assert launcher.pid_alive(0) is False
    assert launcher.pid_alive(-1) is False

def test_runbook_has_six_numbered_sections():
    assert RUNBOOK_PATH.exists()
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert text.count("\n## ") >= 6
    sections = re.findall(r"^##\s+([0-9]+)\.\s+(.*)$", text, re.M)
    assert len(sections) >= 6
    expected_titles = ["Khởi động", "Dừng", "Tiếp tục", "Sao lưu", "Khôi phục", "Xử lý lỗi"]
    for i, title in enumerate(expected_titles, 1):
        num_str, name = sections[i - 1]
        assert int(num_str) == i
        assert title in name
    assert "pg_dump" in text
    assert "docker exec" in text
    assert "recovery epoch" in text
    appendix_headers = [h for h in re.findall(r"^##\s+(.*)$", text, re.M) if "CP7" in h]
    assert len(appendix_headers) >= 1
    prof = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    def find_conservative(obj, prefix=""):
        res = []
        if isinstance(obj, dict):
            if "value" in obj and obj.get("basis") == "CONSERVATIVE_DEFAULT":
                res.append(prefix)
            for k, v in obj.items():
                sub = f"{prefix}.{k}" if prefix else k
                res.extend(find_conservative(v, sub))
        return res
    keys = find_conservative(prof)
    for k in keys:
        assert k in text, f"Missing parameter in runbook: {k}"
    assert "???" not in text

def test_main_dispatch_and_usage(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    assert launcher.main(["status"], fx.deps) == 0
    with pytest.raises(SystemExit) as exc:
        launcher.main(["bogus"], fx.deps)
    assert exc.value.code == 2


def test_start_seeds_defaults_between_session_and_spawn(launcher, tmp_path):
    fx = make_fx(launcher, tmp_path)
    assert launcher.cmd_start(fx.deps, SimpleNamespace()) == 0
    names = [ev[0] for ev in fx.events]
    assert names.index("begin_session") < names.index("seed_defaults") < names.index("spawn")
    seed = [ev for ev in fx.events if ev[0] == "seed_defaults"][0]
    assert seed[4] == "1"
