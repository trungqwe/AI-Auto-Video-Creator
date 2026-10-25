"""Trình khởi chạy và quản lý vòng đời AI Auto Video Creator (ADAPT-LAUNCH)."""
from __future__ import annotations

import argparse
import collections.abc
import dataclasses
import datetime
import hashlib
import ipaddress
import json
import os
import pathlib
import re
import secrets
import socket
import subprocess
import sys
import time
import typing
import urllib.parse
import uuid
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_FILE = Path(__file__).resolve()
COMPOSE_FILE = ROOT / 'tools' / 'launcher' / 'docker-compose.yml'
RUNTIME_LOCK = ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
WEIGHTS_LOCK = ROOT / 'tools' / 'launcher' / 'prod' / 'model-weights.lock.json'
MIGRATIONS_DIR = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'

PROJECT = 'aiavc'
LOOPBACK = '127.0.0.1'
POSTGRES_PORT = 57028
TEMPORAL_PORT = 7233
APP_PORT = 8443
POSTGRES_CONTAINER = 'aiavc-postgres'
DB_USER = 'controlplane'
DB_NAME = 'controlplane'

PG_WAIT_SECONDS = 120
TEMPORAL_WAIT_SECONDS = 180
APP_WAIT_SECONDS = 120
STOP_GRACE_SECONDS = 60
OAUTH_CONSENT_TIMEOUT_SECONDS = 300
# Namespace mà Temporal worker dùng; image temporalio/server không tự đăng ký nó như image auto-setup cũ (ổn định hoá 25/10/2026, S5).
TEMPORAL_NAMESPACE = 'default'
# Lịch sử workflow đã đóng giữ 7 ngày: đủ cho đối soát và diễn tập khôi phục.
TEMPORAL_RETENTION_SECONDS = 7 * 24 * 3600
NAMESPACE_WAIT_SECONDS = 60

COMMANDS = ('start', 'stop', 'down', 'status', 'backup', 'restore', 'oauth')


class LauncherError(Exception):
    """Lỗi vận hành launcher với thông điệp tiếng Việt an toàn (không chứa bí mật)."""


@dataclasses.dataclass(frozen=True)
class Layout:
    data_dir: Path

    @property
    def tls_dir(self) -> Path:
        return self.data_dir / 'tls'

    @property
    def secrets_dir(self) -> Path:
        return self.data_dir / 'secrets'

    @property
    def vault_dir(self) -> Path:
        return self.data_dir / 'vault'

    @property
    def staging_dir(self) -> Path:
        return self.data_dir / 'staging'

    @property
    def models_dir(self) -> Path:
        return self.data_dir / 'models'

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / 'backups'

    @property
    def state_dir(self) -> Path:
        return self.data_dir / 'state'

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / 'logs'

    @property
    def cert_file(self) -> Path:
        return self.tls_dir / 'cert.pem'

    @property
    def key_file(self) -> Path:
        return self.tls_dir / 'key.pem'

    @property
    def password_file(self) -> Path:
        return self.secrets_dir / 'postgres-password'

    @property
    def pid_file(self) -> Path:
        return self.state_dir / 'worker.pid'

    @property
    def stop_file(self) -> Path:
        return self.state_dir / 'stop.request'

    @property
    def identity_file(self) -> Path:
        return self.state_dir / 'identity.json'

    @property
    def epoch_file(self) -> Path:
        return self.state_dir / 'recovery-epoch.json'

    @property
    def active_db_file(self) -> Path:
        return self.state_dir / 'active-db'

    @property
    def serve_log(self) -> Path:
        return self.logs_dir / 'serve.log'

    def ensure_dirs(self) -> None:
        for d in (
            self.tls_dir,
            self.secrets_dir,
            self.vault_dir,
            self.staging_dir,
            self.models_dir,
            self.backups_dir,
            self.state_dir,
            self.logs_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
@dataclasses.dataclass
class Deps:
    environ: dict[str, str]
    run: typing.Callable[..., typing.Any]
    spawn: typing.Callable[..., typing.Any]
    out: typing.Callable[[str], None]
    ask: typing.Callable[[str], str]
    sleep: typing.Callable[[float], None]
    wait_tcp: typing.Callable[[str, int, float], bool]
    pid_alive: typing.Callable[[int], bool]
    migrate: typing.Callable[[str], None]
    ensure_identity: typing.Callable[[str, str, str], None]
    make_cert: typing.Callable[[Path, Path], None]
    open_browser: typing.Callable[[str], bool]
    run_consent: typing.Callable[..., typing.Any]
    load_app: typing.Callable[..., typing.Any]
    start_worker: typing.Callable[..., typing.Any]
    serve_tls: typing.Callable[..., None]
    now: typing.Callable[[], datetime.datetime]
    # (host, port) -> 'EXISTS' | 'REGISTERED'; None bỏ qua bước này (chỉ khi không có Temporal thật).
    ensure_namespace: typing.Callable[[str, int], str] | None = None


def resolve_layout(environ: typing.Mapping[str, str], root: Path = ROOT) -> Layout:
    base = environ.get('AIAVC_DATA_DIR')
    if base:
        data_path = Path(base)
    elif environ.get('LOCALAPPDATA'):
        data_path = Path(environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'
    else:
        raise LauncherError('Thiếu AIAVC_DATA_DIR hoặc LOCALAPPDATA để xác định thư mục dữ liệu ngoài Git.')

    data_path = data_path.resolve()
    resolved_root = root.resolve()
    try:
        data_path.relative_to(resolved_root)
        is_under_root = True
    except ValueError:
        is_under_root = False

    if is_under_root:
        raise LauncherError(f'Thư mục dữ liệu phải nằm ngoài cây Git ({data_path} nằm trong {resolved_root}).')

    curr = data_path
    while True:
        if (curr / '.git').exists():
            raise LauncherError(f'Thư mục dữ liệu phải nằm ngoài cây Git ({curr} chứa .git).')
        parent = curr.parent
        if parent == curr:
            break
        curr = parent

    return Layout(data_dir=data_path)


def read_image_digests(lock_path: Path = RUNTIME_LOCK) -> dict[str, str]:
    if not lock_path.exists():
        raise LauncherError(f'Không tìm thấy tệp runtime lock: {lock_path}')
    try:
        data = json.loads(lock_path.read_text(encoding='utf-8'))
        pins = data.get('pins', {})
        pg = pins.get('postgresql_image', {})
        temporal = pins.get('temporal_server_binary', {})
        if pg.get('status') != 'PINNED' or not re.match(r'^[0-9a-f]{64}$', str(pg.get('sha256', ''))):
            raise LauncherError('postgresql_image trong runtime.lock.json không có trạng thái PINNED hoặc SHA-256 không hợp lệ')
        if temporal.get('status') != 'PINNED' or not re.match(r'^[0-9a-f]{64}$', str(temporal.get('sha256', ''))):
            raise LauncherError('temporal_server_binary trong runtime.lock.json không có trạng thái PINNED hoặc SHA-256 không hợp lệ')
        return {
            'postgres': f"sha256:{pg['sha256']}",
            'temporal': f"sha256:{temporal['sha256']}",
        }
    except Exception as exc:
        if isinstance(exc, LauncherError):
            raise
        raise LauncherError(f'Lỗi đọc runtime.lock.json: {exc}') from exc


def check_compose_matches_lock(compose_path: Path = COMPOSE_FILE, lock_path: Path = RUNTIME_LOCK) -> None:
    if not compose_path.exists():
        raise LauncherError(f'Không tìm thấy tệp compose: {compose_path}')
    text = compose_path.read_text(encoding='utf-8')
    image_lines = re.findall(r'^\s*image:\s*(\S+)\s*$', text, re.M)
    if not image_lines:
        raise LauncherError('Tệp docker-compose.yml không chứa định nghĩa image nào')
    for img in image_lines:
        if '@sha256:' not in img:
            raise LauncherError(f'Image trong docker-compose.yml không sử dụng digest @sha256: {img}')
    digests = read_image_digests(lock_path)
    if digests['postgres'] not in text:
        raise LauncherError(f"Digest của PostgreSQL {digests['postgres']} không có trong docker-compose.yml")
    if digests['temporal'] not in text:
        raise LauncherError(f"Digest của Temporal {digests['temporal']} không có trong docker-compose.yml")


def compose_command(*args: str) -> list[str]:
    return ['docker', 'compose', '-p', PROJECT, '-f', str(COMPOSE_FILE), *args]


def load_or_create_password(layout: Layout) -> str:
    if layout.password_file.exists():
        pw = layout.password_file.read_text(encoding='utf-8').strip()
        if len(pw) < 32:
            raise LauncherError('Mật khẩu PostgreSQL trong tệp secrets không đủ độ dài an toàn (tối thiểu 32 ký tự).')
        return pw
    layout.ensure_dirs()
    pw = secrets.token_urlsafe(32)
    fd = os.open(str(layout.password_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(pw)
    return pw


def build_dsn(password: str, db_name: str = DB_NAME) -> str:
    quoted_pw = urllib.parse.quote(password, safe='')
    return f'postgresql://{DB_USER}:{quoted_pw}@{LOOPBACK}:{POSTGRES_PORT}/{db_name}'


def active_db_name(layout: Layout) -> str:
    if layout.active_db_file.exists():
        val = layout.active_db_file.read_text(encoding='utf-8').strip()
        if not re.match(r'^[a-z][a-z0-9_]{0,62}$', val):
            raise LauncherError(f'Tên CSDL đang kích hoạt không hợp lệ: {val}')
        return val
    return DB_NAME


def load_or_create_identity(layout: Layout) -> dict[str, str]:
    if layout.identity_file.exists():
        try:
            data = json.loads(layout.identity_file.read_text(encoding='utf-8'))
            uuid.UUID(str(data.get('workspace_id', '')))
            uuid.UUID(str(data.get('actor_id', '')))
            return {
                'workspace_id': str(data['workspace_id']),
                'actor_id': str(data['actor_id']),
            }
        except Exception as exc:
            raise LauncherError(f'Tệp identity.json bị hỏng: {exc}') from exc
    layout.ensure_dirs()
    ws = str(uuid.uuid4())
    actor = str(uuid.uuid4())
    ident = {'workspace_id': ws, 'actor_id': actor}
    atomic_write_text(layout.identity_file, json.dumps(ident, indent=2))
    return ident


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f'{path.name}.tmp-{os.getpid()}-{time.time_ns()}')
    tmp_path.write_text(text, encoding='utf-8')
    os.replace(tmp_path, path)


def read_pid(layout: Layout) -> int | None:
    if not layout.pid_file.exists():
        return None
    try:
        raw = layout.pid_file.read_text(encoding='utf-8').strip()
        return int(raw)
    except Exception:
        try:
            layout.pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == 'win32':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h_proc = kernel32.OpenProcess(0x1000, False, pid)
        if not h_proc:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code)):
                return exit_code.value == 259  # STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(h_proc)
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True


def wait_for_tcp(host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(1.0)
    return False


def ensure_temporal_namespace(host: str, port: int, namespace: str = TEMPORAL_NAMESPACE,
                              timeout_seconds: float = NAMESPACE_WAIT_SECONDS) -> str:
    """Bảo đảm namespace của worker có trên Temporal: 'EXISTS' nếu đã có, 'REGISTERED' nếu vừa đăng ký.

    Thiếu namespace thì mọi lượt poll của worker hỏng và không workflow nào chạy; không bảo đảm được thì LauncherError.
    """
    ensure_src_on_path()
    import asyncio

    async def _ensure() -> str:
        from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest, RegisterNamespaceRequest
        from temporalio.client import Client
        from temporalio.service import RPCError, RPCStatusCode

        deadline = time.monotonic() + timeout_seconds
        client = None
        while client is None:
            try:
                client = await Client.connect(f'{host}:{port}', namespace=namespace)
            except Exception as exc:
                if time.monotonic() >= deadline:
                    raise LauncherError(f'Không kết nối được Temporal để kiểm namespace {namespace} ({type(exc).__name__}).') from None
                await asyncio.sleep(1.0)
        service = client.workflow_service

        async def exists() -> bool:
            try:
                await service.describe_namespace(DescribeNamespaceRequest(namespace=namespace))
                return True
            except RPCError as exc:
                if exc.status == RPCStatusCode.NOT_FOUND:
                    return False
                raise

        if await exists():
            return 'EXISTS'
        request = RegisterNamespaceRequest(namespace=namespace)
        request.workflow_execution_retention_period.seconds = TEMPORAL_RETENTION_SECONDS
        try:
            await service.register_namespace(request)
        except RPCError as exc:
            if exc.status != RPCStatusCode.ALREADY_EXISTS:
                raise
        while time.monotonic() < deadline:
            if await exists():
                return 'REGISTERED'
            await asyncio.sleep(1.0)
        raise LauncherError(f'Namespace Temporal {namespace} chưa sẵn sàng sau {int(timeout_seconds)} giây.')

    try:
        return asyncio.run(_ensure())
    except LauncherError:
        raise
    except Exception as exc:
        raise LauncherError(f'Không bảo đảm được namespace Temporal {namespace} ({type(exc).__name__}).') from None


def make_self_signed_cert(cert_file: Path, key_file: Path) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'AI Auto Video Creator loopback'),
    ])
    san = x509.SubjectAlternativeName([
        x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
        x509.DNSName('localhost'),
    ])
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now_utc - datetime.timedelta(minutes=1))
        .not_valid_after(now_utc + datetime.timedelta(days=365))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    fd = os.open(str(key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))


def ensure_src_on_path() -> None:
    src_dir = str(ROOT / 'src')
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def run_migrations(dsn: str) -> None:
    ensure_src_on_path()
    from controlplane.infrastructure.db.migration_runner import MigrationRunner
    runner = MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=False)
    runner.migrate_up()


def ensure_identity(dsn: str, workspace_id: str, actor_id: str) -> None:
    import psycopg
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s) ON CONFLICT (workspace_id) DO NOTHING",
                (workspace_id, 'AI Auto Video Creator', 'ACTIVE'),
            )
            cur.execute(
                "INSERT INTO controlplane.cp_actors (actor_id, workspace_id, actor_type, display_name, status) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (actor_id) DO NOTHING",
                (actor_id, workspace_id, 'user', 'Người vận hành', 'ACTIVE'),
            )


def run_consent(client_secrets_path: Path, vault_dir: Path, timeout_seconds: int, present_url: typing.Callable[[str], None]) -> typing.Any:
    ensure_src_on_path()
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.oauth_google_loopback import DriveOAuthConfig, run_consent as adapt_j_run_consent
    cfg = DriveOAuthConfig.from_mapping({
        'oauth_client_secrets_path': client_secrets_path,
        'oauth_consent_timeout_seconds': timeout_seconds,
    })
    return adapt_j_run_consent(cfg, DpapiSecretStore(vault_dir), present_url)


def _load_runtime_ports(layout: Layout, profile: typing.Any) -> dict[str, typing.Any]:
    try:
        ensure_src_on_path()
        from controlplane.infrastructure.production_ports.assembly import build_production_ports
        from controlplane.infrastructure.production_ports.ports_config import load_ports_config
        return build_production_ports(
            profile,
            vault_dir=layout.vault_dir,
            staging_dir=layout.staging_dir,
            state_dir=layout.state_dir,
            oauth_client_secrets_path=layout.secrets_dir / 'oauth-client.json',
            ports_config=load_ports_config(ROOT / 'tools' / 'launcher' / 'prod' / 'ports.json'),
        )
    except Exception as exc:
        raise LauncherError(f'BLOCKED: cổng production chưa sẵn: {type(exc).__name__}: {exc}') from None


def build_runtime(profile: typing.Any, layout: Layout, environ: typing.Mapping[str, str]) -> typing.Any:
    from decimal import Decimal
    from controlplane.api.wiring.production import ProductionRuntime
    ports = _load_runtime_ports(layout, profile)
    return ProductionRuntime(
        ffmpeg_path=Path(environ.get('AIAVC_FFMPEG_PATH', r'C:\ffmpeg\bin\ffmpeg.exe')),
        ffprobe_path=Path(environ.get('AIAVC_FFPROBE_PATH', r'C:\ffmpeg\bin\ffprobe.exe')),
        runtime_lock_path=RUNTIME_LOCK,
        weights_dir=layout.models_dir / 'weights',
        weights_lock_path=WEIGHTS_LOCK,
        whisper_model_dir=layout.models_dir / 'whisper',
        staging_root=layout.staging_dir,
        secret_store_root=layout.vault_dir,
        oauth_client_secrets_path=layout.secrets_dir / 'oauth-client.json',
        oauth_consent_timeout_seconds=OAUTH_CONSENT_TIMEOUT_SECONDS,
        route_cost_per_request=Decimal('0'),
        tokenization={
            'revision': 'adapt-launch-1',
            'unicode_form': 'NFC',
            'casefold': True,
            'edge_strip_categories': ('P',),
            'gap_tolerance_ms': 500,
            'min_confidence': 0.5,
        },
        **ports,
    )


def load_app(environ: typing.Mapping[str, str], layout: Layout) -> typing.Any:
    ensure_src_on_path()
    from main import build_app
    return build_app(environ, runtime_factory=lambda profile: build_runtime(profile, layout, environ))


def start_worker(app: typing.Any, layout: Layout) -> typing.Any:
    ensure_src_on_path()
    import asyncio
    import threading
    from temporalio.client import Client
    from controlplane.api.wiring.workflow import build_workflow_services, build_temporal_registration
    from controlplane.api.wiring.production import TemporalWorkerGroup
    from controlplane.api.wiring.production_profile import load_production_profile

    profile = load_production_profile(PROFILE_PATH)
    services = build_workflow_services(
        parameters=profile.parameters,
        handlers={},
        clock=lambda: datetime.datetime.now(datetime.timezone.utc),
        timezone_approved=True,
    )

    def _grant_issuer(*_args: typing.Any, **_kwargs: typing.Any) -> typing.NoReturn:
        raise LauncherError('grant_issuer chưa nối')

    def _capability_reader(*_args: typing.Any, **_kwargs: typing.Any) -> typing.NoReturn:
        raise LauncherError('capability_reader chưa nối')

    registration = build_temporal_registration(
        services,
        grant_issuer=_grant_issuer,
        capability_reader=_capability_reader,
    )

    loop = asyncio.new_event_loop()
    group_box: list[typing.Any] = []
    ready_evt = threading.Event()
    init_err: list[Exception] = []

    async def _runner() -> None:
        try:
            client = await Client.connect(f'{LOOPBACK}:{TEMPORAL_PORT}')
            heartbeat_sec = float(profile.parameters.get('workflow.heartbeat_seconds', 30.0))
            group = TemporalWorkerGroup(client, registration, graceful_shutdown_seconds=heartbeat_sec)
            group_box.append(group)
            ready_evt.set()
            await group.run()
        except Exception as e:
            init_err.append(e)
            ready_evt.set()

    def _thread_target() -> None:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_runner())

    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()
    ready_evt.wait(timeout=10.0)
    if init_err:
        raise LauncherError(f'Khởi động Temporal worker thất bại: {init_err[0]}')

    class WorkerHandle:
        def stop(self) -> None:
            if group_box:
                try:
                    fut = asyncio.run_coroutine_threadsafe(group_box[0].stop(), loop)
                    fut.result(timeout=STOP_GRACE_SECONDS)
                except Exception:
                    pass
            t.join(timeout=STOP_GRACE_SECONDS)

    return WorkerHandle()


def serve_tls(
    app: typing.Any,
    *,
    port: int,
    certfile: Path,
    keyfile: Path,
    on_ready: typing.Callable[[], None],
    should_stop: typing.Callable[[], bool],
) -> None:
    ensure_src_on_path()
    import threading
    import uvicorn
    from controlplane.api.wiring.production import loopback_config

    server = uvicorn.Server(loopback_config(app, port=port, certfile=certfile, keyfile=keyfile))

    def _wait_started() -> None:
        while not server.started and not server.should_exit:
            time.sleep(0.1)
        if server.started:
            on_ready()

    def _watch_stop() -> None:
        while not server.should_exit:
            if should_stop():
                server.should_exit = True
                break
            time.sleep(1.0)

    t_ready = threading.Thread(target=_wait_started, daemon=True)
    t_stop = threading.Thread(target=_watch_stop, daemon=True)
    t_ready.start()
    t_stop.start()
    server.run()


def default_deps(environ: typing.Mapping[str, str] | None = None) -> Deps:
    return Deps(
        environ=dict(os.environ if environ is None else environ),
        run=subprocess.run,
        spawn=subprocess.Popen,
        out=print,
        ask=input,
        sleep=time.sleep,
        wait_tcp=wait_for_tcp,
        pid_alive=pid_alive,
        migrate=run_migrations,
        ensure_identity=ensure_identity,
        make_cert=make_self_signed_cert,
        open_browser=webbrowser.open,
        run_consent=run_consent,
        load_app=load_app,
        start_worker=start_worker,
        serve_tls=serve_tls,
        now=lambda: datetime.datetime.now(datetime.timezone.utc),
        ensure_namespace=ensure_temporal_namespace,
    )
def cmd_start(deps: Deps, args: argparse.Namespace) -> int:
    layout = resolve_layout(deps.environ)
    layout.ensure_dirs()

    pid = read_pid(layout)
    if pid is not None and deps.pid_alive(pid):
        deps.out('Worker đang chạy; bỏ qua khởi động mới.')
        return 0
    elif pid is not None:
        try:
            layout.pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    check_compose_matches_lock()
    password = load_or_create_password(layout)
    env = dict(deps.environ)
    env['AIAVC_PG_PASSWORD'] = password

    r = deps.run(compose_command('up', '-d'), env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise LauncherError('docker compose up thất bại; kiểm tra Docker Desktop đã chạy')

    pg_ready = False
    for _ in range(PG_WAIT_SECONDS):
        res = deps.run(
            ['docker', 'exec', POSTGRES_CONTAINER, 'pg_isready', '-U', DB_USER, '-d', DB_NAME],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            pg_ready = True
            break
        deps.sleep(1)
    if not pg_ready:
        raise LauncherError('PostgreSQL chưa sẵn sàng sau thời gian chờ.')

    if not deps.wait_tcp(LOOPBACK, TEMPORAL_PORT, TEMPORAL_WAIT_SECONDS):
        raise LauncherError('Temporal server chưa sẵn sàng trên cổng 7233 sau thời gian chờ.')
    if deps.ensure_namespace is not None:
        state = deps.ensure_namespace(LOOPBACK, TEMPORAL_PORT)
        deps.out(f'Namespace Temporal {TEMPORAL_NAMESPACE}: {"đã có" if state == "EXISTS" else "vừa đăng ký"}.')

    dsn = build_dsn(password, active_db_name(layout))
    deps.migrate(dsn)

    identity = load_or_create_identity(layout)
    deps.ensure_identity(dsn, identity['workspace_id'], identity['actor_id'])

    if not layout.cert_file.exists() or not layout.key_file.exists():
        deps.make_cert(layout.cert_file, layout.key_file)

    try:
        layout.stop_file.unlink(missing_ok=True)
    except Exception:
        pass

    child_env = dict(deps.environ)
    child_env['CONTROLPLANE_DSN'] = dsn
    child_env['CONTROLPLANE_PORT'] = str(APP_PORT)
    child_env['CONTROLPLANE_PROFILE'] = 'production'
    child_env['CONTROLPLANE_PROFILE_PATH'] = str(PROFILE_PATH)
    child_env['CONTROLPLANE_WORKSPACE_ID'] = identity['workspace_id']
    child_env['AIAVC_ACTOR_ID'] = identity['actor_id']
    child_env['AIAVC_DATA_DIR'] = str(layout.data_dir)
    child_env['PYTHONUTF8'] = '1'
    if layout.epoch_file.exists():
        try:
            epoch_data = json.loads(layout.epoch_file.read_text(encoding='utf-8'))
            history = epoch_data.get('history', [])
            if history:
                child_env['AIAVC_RECOVERY_EPOCH'] = history[-1]['epoch']
        except Exception:
            pass

    with open(layout.serve_log, 'ab') as logfile:
        proc = deps.spawn(
            [sys.executable, str(LAUNCHER_FILE), '_serve'],
            env=child_env,
            cwd=str(ROOT),
            stdout=logfile,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0),
        )
    atomic_write_text(layout.pid_file, str(proc.pid))

    if not deps.wait_tcp(LOOPBACK, APP_PORT, APP_WAIT_SECONDS):
        deps.out('Ứng dụng chưa mở cổng; xem logs/serve.log')
        return 1

    deps.out('Đã khởi động; trình duyệt sẽ mở tại /launch (capability dùng một lần, hết hạn sau 60 giây).')
    return 0


def cmd_stop(deps: Deps, args: argparse.Namespace) -> int:
    layout = resolve_layout(deps.environ)
    pid = read_pid(layout)
    if pid is None:
        deps.out('Không có worker đang chạy; container và dữ liệu không bị đụng tới.')
        return 0
    if not deps.pid_alive(pid):
        try:
            layout.pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        deps.out('Worker không còn chạy (tiến trình đã dừng từ trước).')
        return 0

    atomic_write_text(layout.stop_file, 'stop')
    for _ in range(STOP_GRACE_SECONDS):
        if not deps.pid_alive(pid):
            break
        deps.sleep(1)

    if not deps.pid_alive(pid):
        try:
            layout.stop_file.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            layout.pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        deps.out('Đã dừng worker và ứng dụng; container và volume giữ nguyên, việc dở tiếp tục khi chạy start lại.')
        return 0

    deps.out(f'Worker chưa thoát sau {STOP_GRACE_SECONDS} giây; không ép tắt để tránh mất việc đang chạy, xem runbook mục 6.')
    return 1


def cmd_down(deps: Deps, args: argparse.Namespace) -> int:
    rc = cmd_stop(deps, args)
    if rc != 0:
        raise LauncherError('Worker chưa dừng nên không chạy down')
    layout = resolve_layout(deps.environ)
    password = load_or_create_password(layout)
    env = dict(deps.environ)
    env['AIAVC_PG_PASSWORD'] = password
    r = deps.run(compose_command('down'), env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise LauncherError('docker compose down thất bại')
    deps.out('Đã gỡ container; volume aiavc_pgdata và dữ liệu được giữ nguyên.')
    return 0


def cmd_status(deps: Deps, args: argparse.Namespace) -> int:
    layout = resolve_layout(deps.environ)
    deps.out(f'Thư mục dữ liệu: {layout.data_dir}')
    pid = read_pid(layout)
    if pid is not None and deps.pid_alive(pid):
        deps.out(f'Worker: Đang chạy (PID: {pid})')
    elif pid is not None:
        deps.out(f'Worker: Không hoạt động (PID cũ: {pid})')
    else:
        deps.out('Worker: Không hoạt động')
    db = active_db_name(layout)
    deps.out(f'CSDL đang dùng: {db}')
    epoch = 'chưa có'
    if layout.epoch_file.exists():
        try:
            data = json.loads(layout.epoch_file.read_text(encoding='utf-8'))
            history = data.get('history', [])
            if history:
                epoch = history[-1].get('epoch', 'chưa có')
        except Exception:
            pass
    deps.out(f'Recovery epoch hiện tại: {epoch}')
    for port, name in ((POSTGRES_PORT, 'PostgreSQL'), (TEMPORAL_PORT, 'Temporal'), (APP_PORT, 'Application')):
        status = 'Mở' if deps.wait_tcp(LOOPBACK, port, 1.0) else 'Đóng'
        deps.out(f'Cổng {port} ({name}): {status}')
    password = load_or_create_password(layout)
    env = dict(deps.environ)
    env['AIAVC_PG_PASSWORD'] = password
    res = deps.run(compose_command('ps'), env=env, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout:
        deps.out(res.stdout)
    return 0
def cmd_backup(deps: Deps, args: argparse.Namespace) -> int:
    layout = resolve_layout(deps.environ)
    layout.ensure_dirs()
    if getattr(args, 'out', None):
        out_path = Path(args.out)
    else:
        stamp = deps.now().strftime('%Y%m%dT%H%M%SZ')
        out_path = layout.backups_dir / f'aiavc-{stamp}.dump'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'wb') as fh:
        r = deps.run(
            ['docker', 'exec', POSTGRES_CONTAINER, 'pg_dump', '-U', DB_USER, '-Fc', '-d', active_db_name(layout)],
            stdout=fh,
            stderr=subprocess.PIPE,
        )
    if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        raise LauncherError('pg_dump thất bại; tệp sao lưu dở đã bị loại')

    h = hashlib.sha256()
    with open(out_path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    digest = h.hexdigest()
    sha_file = out_path.with_name(f'{out_path.name}.sha256')
    atomic_write_text(sha_file, f'{digest}  {out_path.name}\n')
    deps.out(f'Đã tạo bản sao lưu: {out_path}')
    deps.out(f'SHA-256: {digest}')
    return 0


def cmd_restore(deps: Deps, args: argparse.Namespace) -> int:
    layout = resolve_layout(deps.environ)
    src = Path(args.file)
    if not src.is_file():
        raise LauncherError(f'Tệp sao lưu không tồn tại hoặc không phải tệp: {src}')

    h = hashlib.sha256()
    with open(src, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    real_sha = h.hexdigest()

    sidecar = src.with_name(f'{src.name}.sha256')
    if sidecar.exists():
        expected_content = sidecar.read_text(encoding='utf-8').strip()
        expected_hash = expected_content.split()[0] if expected_content else ''
        if real_sha != expected_hash:
            raise LauncherError(f'Mã băm SHA-256 của bản sao lưu không khớp tệp sidecar ({real_sha} != {expected_hash})')
    else:
        deps.out('Cảnh báo: Không tìm thấy tệp .sha256 kiểm tra tính toàn vẹn; tiếp tục khôi phục.')

    pid = read_pid(layout)
    if pid is not None and deps.pid_alive(pid):
        raise LauncherError('Hãy chạy stop trước khi khôi phục')

    if not getattr(args, 'yes', False):
        confirm = deps.ask('Gõ RESTORE để tạo CSDL mới từ bản sao lưu: ')
        if confirm.strip() != 'RESTORE':
            deps.out('Đã hủy khôi phục.')
            return 2

    res = deps.run(
        ['docker', 'exec', POSTGRES_CONTAINER, 'pg_isready', '-U', DB_USER, '-d', DB_NAME],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise LauncherError('PostgreSQL chưa sẵn sàng để thực hiện khôi phục.')

    t = deps.now()
    stamp = t.strftime('%Y%m%d%H%M%S')
    new_db = f'controlplane_{stamp}'
    epoch = f'rec-{stamp}-{secrets.token_hex(4)}'

    res_create = deps.run(
        ['docker', 'exec', POSTGRES_CONTAINER, 'createdb', '-U', DB_USER, new_db],
        capture_output=True,
        text=True,
    )
    if res_create.returncode != 0:
        raise LauncherError(f'Tạo CSDL mới {new_db} thất bại.')

    with open(src, 'rb') as fh:
        res_restore = deps.run(
            ['docker', 'exec', '-i', POSTGRES_CONTAINER, 'pg_restore', '-U', DB_USER, '-d', new_db, '--no-owner', '--exit-on-error'],
            stdin=fh,
            stderr=subprocess.PIPE,
        )
    if res_restore.returncode != 0:
        deps.run(
            ['docker', 'exec', POSTGRES_CONTAINER, 'dropdb', '-U', DB_USER, '--if-exists', new_db],
            capture_output=True,
            text=True,
        )
        raise LauncherError(f'pg_restore vào {new_db} thất bại; đã loại bỏ CSDL tạm.')

    history = []
    if layout.epoch_file.exists():
        try:
            data = json.loads(layout.epoch_file.read_text(encoding='utf-8'))
            history = list(data.get('history', []))
        except Exception:
            pass
    history.append({
        'epoch': epoch,
        'restored_at': t.isoformat(),
        'database': new_db,
        'source_sha256': real_sha,
    })
    atomic_write_text(layout.epoch_file, json.dumps({'history': history}, indent=2))
    atomic_write_text(layout.active_db_file, new_db)
    deps.out(f'Khôi phục thành công. CSDL mới: {new_db}, Recovery epoch mới: {epoch}')
    deps.out('Nhắc nhở: Chạy start rồi reconcile Drive/journal trước khi bật cleanup.')
    return 0
def cmd_oauth(deps: Deps, args: argparse.Namespace) -> int:
    layout = resolve_layout(deps.environ)
    client_env = deps.environ.get('AIAVC_OAUTH_CLIENT_SECRETS')
    client = Path(client_env) if client_env else layout.secrets_dir / 'oauth-client.json'
    if not client.is_file():
        deps.out(
            'Hướng dẫn cấu hình Google Drive OAuth:\n'
            '1. Tạo OAuth client loại Desktop trong Google Cloud Console.\n'
            '2. Tải tệp JSON client secrets và lưu ngoài cây Git tại:\n'
            f'   {client}\n'
            '   (hoặc đặt biến môi trường AIAVC_OAUTH_CLIENT_SECRETS trỏ tới tệp).\n'
            '3. Tuyệt đối không dán nội dung tệp client JSON vào chat, issues hay terminal.'
        )
        return 2

    deps.out('Các bước ủy quyền Google Drive OAuth:')
    deps.out(f'Bước 1. Xác nhận tệp client secrets JSON tại đường dẫn ngoài Git: {client}')
    deps.out('Bước 2. Launcher sẽ hiển thị liên kết xác thực cục bộ và mở nó trên trình duyệt.')
    deps.out('Bước 3. Đăng nhập đúng một tài khoản Google Drive và bấm đồng ý phạm vi drive.file (quyền tối thiểu) một lần duy nhất.')
    deps.out('Bước 4. Chờ thông báo đã nhận xác nhận trên trình duyệt rồi đóng tab; token sẽ được bảo mật trong kho DPAPI cục bộ và không hiển thị.')
    deps.out(f'Lưu ý: Yêu cầu ủy quyền sẽ hết hạn sau {OAUTH_CONSENT_TIMEOUT_SECONDS} giây.')

    deps.ask('Nhấn Enter khi sẵn sàng ... ')

    def present_url(url: str) -> None:
        deps.out(f'Mở liên kết sau để cấp quyền Drive: {url}')
        deps.open_browser(url)

    try:
        handle = deps.run_consent(client, layout.vault_dir, OAUTH_CONSENT_TIMEOUT_SECONDS, present_url)
    except Exception as exc:
        deps.out(f'OAuth thất bại ({type(exc).__name__}); chạy lại oauth hoặc xem runbook mục 6')
        return 1

    deps.out(f'Đã lưu token qua kho DPAPI: {handle.secret_ref} ({handle.fingerprint}).')
    return 0


def cmd_serve(deps: Deps, args: argparse.Namespace) -> int:
    layout = resolve_layout(deps.environ)
    layout.ensure_dirs()
    try:
        app = deps.load_app(deps.environ, layout)
    except LauncherError as exc:
        deps.out(str(exc))
        return 1

    identity = load_or_create_identity(layout)

    try:
        worker = deps.start_worker(app, layout)
    except LauncherError as exc:
        deps.out(str(exc))
        return 1

    atomic_write_text(layout.pid_file, str(os.getpid()))
    try:
        url = app.launch_url(actor_id=identity['actor_id'], ttl_seconds=60)
        deps.serve_tls(
            app,
            port=APP_PORT,
            certfile=layout.cert_file,
            keyfile=layout.key_file,
            on_ready=lambda: deps.open_browser(url),
            should_stop=lambda: layout.stop_file.exists(),
        )
    finally:
        worker.stop()
        try:
            layout.pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            layout.stop_file.unlink(missing_ok=True)
        except Exception:
            pass
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='launcher',
        description='Quản lý vòng đời AI Auto Video Creator (ADAPT-LAUNCH).',
    )
    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        metavar='{' + ','.join(COMMANDS) + '}',
    )

    subparsers.add_parser('start', help='Khởi động ngăn xếp container, di chuyển CSDL và chạy worker.')
    subparsers.add_parser('stop', help='Dừng worker và ứng dụng một cách an toàn (giữ container và volume).')
    subparsers.add_parser('down', help='Dừng worker và gỡ các container compose (giữ volume dữ liệu).')
    subparsers.add_parser('status', help='Xem trạng thái hiện tại của worker, CSDL và các cổng kết nối.')

    p_backup = subparsers.add_parser('backup', help='Tạo bản sao lưu CSDL PostgreSQL qua pg_dump.')
    p_backup.add_argument('--out', default=None, help='Đường dẫn tệp sao lưu đầu ra (tùy chọn).')

    p_restore = subparsers.add_parser('restore', help='Khôi phục CSDL từ bản sao lưu thành CSDL mới với epoch mới.')
    p_restore.add_argument('--file', required=True, help='Đường dẫn tệp sao lưu .dump.')
    p_restore.add_argument('--yes', action='store_true', help='Bỏ qua bước xác nhận tương tác.')

    subparsers.add_parser('oauth', help='Hướng dẫn và thực hiện ủy quyền Google Drive OAuth.')
    subparsers.add_parser('_serve', help=argparse.SUPPRESS)

    return parser


def main(argv: list[str] | None = None, deps: Deps | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    actual_deps = deps or default_deps()
    handlers: dict[str, typing.Callable[[Deps, argparse.Namespace], int]] = {
        'start': cmd_start,
        'stop': cmd_stop,
        'down': cmd_down,
        'status': cmd_status,
        'backup': cmd_backup,
        'restore': cmd_restore,
        'oauth': cmd_oauth,
        '_serve': cmd_serve,
    }
    handler = handlers[args.command]
    try:
        return handler(actual_deps, args)
    except LauncherError as exc:
        actual_deps.out(f'Lỗi: {exc}')
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
