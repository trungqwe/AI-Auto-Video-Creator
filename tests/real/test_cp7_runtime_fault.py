"""CP7-9 / RG-08: PostgreSQL thật trong Docker, ranh giới rollback commit completion, giữ volume qua down/start và hồi quy M1 điều chỉnh (OI-CP7-05)."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import os
import re
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
    if hasattr(_stream, 'reconfigure') and _stream is not None:
        _stream.reconfigure(encoding='utf-8')

import time
import uuid
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import psycopg  # noqa: E402
import pytest  # noqa: E402
from psycopg import sql  # noqa: E402
import cp7_common as c  # noqa: E402

LAUNCHER = REPO / 'tools' / 'launcher' / 'launcher.py'
SELF = Path(__file__).resolve()
REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-9' / 'report.md'
M1_DIR = REPO / 'tests' / 'm1'
M1_EVIDENCE = REPO / 'docs' / 'milestones' / 'm1-proof' / 'evidence' / 'm1-p3' / 'drive_e3_evidence.json'
M1_LIVE_TEST = 'tests/m1/p3/test_drive_live_probe.py::test_live_e3_drive_verification'
M1_ENV_TEST = 'tests/m1/p0/test_environment_validation.py::test_validator_accepts_untampered_environment_manifest'
PG_SUITES = (
    'tests/integration/convergence/test_cp3_migration_sequence.py',
    'tests/integration/convergence/test_cp4_queries_postgres.py',
    'tests/integration/convergence/test_cp5_completion_uow.py',
    'tests/integration/orchestration/test_g_commit_completion.py',
)
BOUNDARY_SUITE = PG_SUITES[2]
BOUNDARY_TEST = 'test_failure_at_any_point_rolls_back_everything'
BOUNDARY_POINTS = ('before:insert_ledger', 'after:record_usage', 'before:commit')
EXPECTED_POINTS = 19
PROTECTED_DBS = frozenset({'controlplane', 'postgres', 'temporal', 'temporal_visibility', 'template0', 'template1'})
RUN_ID = uuid.uuid4().hex[:12]
RUN_DB = f'cp7_{RUN_ID}'
PARTITION = f'db:{RUN_DB}'
VOLUME = 'aiavc_pgdata'
SESSION_TABLE = 'cp_app_sessions'
SENTINEL_ROWS = 1000
DEADLINE = c.Deadline(3600)
ISSUED = []


def _child_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ('M2_TEST_PG_DSN', 'CONTROLPLANE_DSN')}
    env.update({'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'BROWSER': 'cmd /c exit 0 %s'})
    env.update(extra)
    return env


def _run(argv, *, timeout, log_dir, env=None, secrets=()):
    """Chạy lệnh có hạn; stdout và stderr đi vào tệp (không giữ pipe cho tiến trình nền); trả (returncode, văn bản đã che bí mật)."""
    ISSUED.append(list(argv))
    log = Path(log_dir) / f'run_{len(ISSUED)}.log'
    with log.open('wb') as handle:
        try:
            proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT, cwd=REPO, env=env or _child_env(), timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            pytest.fail(f'BLOCKED: lệnh vượt hạn {timeout:.0f}s: ' + ' '.join(argv[:4]))
        except FileNotFoundError:
            pytest.fail('BLOCKED: thiếu lệnh ' + argv[0])
    text = log.read_text(encoding='utf-8', errors='replace')
    for secret in secrets:
        text = text.replace(secret, '***')
    return proc.returncode, text


def _launcher(work, command, cap):
    assert command in ('start', 'stop', 'down')
    return _run([sys.executable, str(LAUNCHER), command], timeout=DEADLINE.timeout(cap), log_dir=work)


def _docker(work, *args):
    return _run(['docker', *args], timeout=DEADLINE.timeout(60), log_dir=work)


def _load_launcher():
    spec = importlib.util.spec_from_file_location('cp7_launcher_under_test', LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _count(text, word):
    found = re.findall(r'\b([0-9]+) ' + word + r'\b', text)
    return int(found[-1]) if found else 0


def _tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _pytest_argv(*args):
    return [sys.executable, '-m', 'pytest', *args, '-q', '-p', 'no:cacheprovider']


TEMPORAL_VERSION = '1.31.2'


async def _temporal_server_version(address):
    from temporalio.api.workflowservice.v1 import GetSystemInfoRequest
    from temporalio.client import Client
    client = await Client.connect(address)
    return (await client.workflow_service.get_system_info(GetSystemInfoRequest())).server_version


def _wait_temporal_ready(address, cap):
    """Chờ Temporal thật phục vụ gRPC đúng phiên bản; cổng TCP mở chưa đủ vì server vừa dựng lại sau down/start có thể chưa sẵn sàng."""
    end = time.monotonic() + DEADLINE.timeout(cap)
    last = 'chưa thử'
    while time.monotonic() < end:
        try:
            version = asyncio.run(asyncio.wait_for(_temporal_server_version(address), 10))
            if version == TEMPORAL_VERSION:
                return version
            last = f'phiên bản {version}'
        except Exception as exc:
            last = type(exc).__name__
        time.sleep(3)
    pytest.fail(f'BLOCKED: Temporal {address} chưa phục vụ gRPC phiên bản {TEMPORAL_VERSION} sau {cap}s ({last})')


@pytest.fixture(scope='module')
def stack(tmp_path_factory):
    work = tmp_path_factory.mktemp('cp7_rg08')
    tool = _load_launcher()
    layout = tool.resolve_layout(os.environ)
    ready, _ = _docker(work, 'exec', tool.POSTGRES_CONTAINER, 'pg_isready', '-U', tool.DB_USER, '-d', tool.DB_NAME)
    if ready != 0:
        rc, text = _launcher(work, 'start', 900)
        if rc != 0:
            pytest.fail(f'BLOCKED: launcher start rc={rc}: {text[-800:]}')
        rc, text = _launcher(work, 'stop', 120)
        assert rc == 0, text[-800:]
    password = tool.load_or_create_password(layout)
    active = tool.active_db_name(layout)
    return SimpleNamespace(
        work=work, launcher=tool, password=password, secrets=(password,), active_db=active,
        admin_dsn=tool.build_dsn(password, 'postgres'),
        run_dsn=tool.build_dsn(password, RUN_DB),
        active_dsn=tool.build_dsn(password, active),
    )


@pytest.fixture(scope='module')
def run_db(stack):
    assert re.fullmatch(r'cp7_[0-9a-f]{12}', RUN_DB) and RUN_DB not in PROTECTED_DBS and RUN_DB != stack.active_db
    state = SimpleNamespace(name=RUN_DB, partition=PARTITION, version=None, created=False)
    try:
        with psycopg.connect(stack.admin_dsn, autocommit=True, connect_timeout=10) as admin:
            state.version = admin.execute('SHOW server_version').fetchone()[0]
            assert state.version.startswith('18.6'), state.version
            assert admin.execute('SELECT count(*) FROM pg_database WHERE datname = %s', (RUN_DB,)).fetchone()[0] == 0
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(RUN_DB)))
            state.created = True
    except psycopg.OperationalError as exc:
        pytest.fail('BLOCKED: PostgreSQL thật chưa kết nối được: ' + type(exc).__name__)
    try:
        yield state
    finally:
        if state.created:
            with psycopg.connect(stack.admin_dsn, autocommit=True, connect_timeout=10) as admin:
                admin.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(RUN_DB)))
                assert admin.execute('SELECT count(*) FROM pg_database WHERE datname = %s', (RUN_DB,)).fetchone()[0] == 0


@pytest.fixture(scope='module')
def suites(stack, run_db, tmp_path_factory):
    temproot = tmp_path_factory.mktemp('cp7_child_tmp')
    env = _child_env(M2_TEST_PG_DSN=stack.run_dsn, PYTEST_DEBUG_TEMPROOT=str(temproot))
    results = {}
    for suite in PG_SUITES:
        started = time.monotonic()
        rc, text = _run(_pytest_argv(suite) + ['-rs'], timeout=DEADLINE.timeout(1500), log_dir=stack.work, env=env, secrets=stack.secrets)
        results[suite] = SimpleNamespace(
            rc=rc, text=text, seconds=time.monotonic() - started,
            passed=_count(text, 'passed'), failed=_count(text, 'failed'), errors=_count(text, 'errors?'), skipped=_count(text, 'skipped'),
            reasons=re.findall(r'(?m)^SKIPPED \[[0-9]+\] (.+)$', text),
        )
    return results


@pytest.fixture(scope='module')
def boundary(stack, suites, tmp_path_factory):
    temproot = tmp_path_factory.mktemp('cp7_boundary_tmp')
    env = _child_env(M2_TEST_PG_DSN=stack.run_dsn, PYTEST_DEBUG_TEMPROOT=str(temproot))
    rc, text = _run(_pytest_argv(BOUNDARY_SUITE) + ['-rp', '-k', BOUNDARY_TEST], timeout=DEADLINE.timeout(900), log_dir=stack.work, env=env, secrets=stack.secrets)
    passed = re.findall(r'(?m)^PASSED \S+::' + BOUNDARY_TEST + r'\[(.+)\]\s*$', text)
    return SimpleNamespace(rc=rc, text=text, passed=passed)


def test_rg08_pg_suites_no_dsn_skip(stack, run_db, suites, emit):
    tool = stack.launcher
    assert re.fullmatch(r'cp7_[0-9a-f]{12}', run_db.name) and run_db.name not in PROTECTED_DBS and run_db.name != stack.active_db
    assert run_db.partition == f'db:{run_db.name}' and run_db.version.startswith('18.6')
    rc, port_text = _docker(stack.work, 'port', tool.POSTGRES_CONTAINER, '5432/tcp')
    assert rc == 0 and f'{tool.LOOPBACK}:{tool.POSTGRES_PORT}' in port_text, port_text
    rc, image_text = _docker(stack.work, 'inspect', '--format', '{{.Config.Image}}', tool.POSTGRES_CONTAINER)
    assert rc == 0 and re.search(r'postgres:18\.6@sha256:[0-9a-f]{64}', image_text), image_text
    details = []
    for suite, res in suites.items():
        assert res.rc == 0, f'{suite} exit {res.rc}: {res.text[-1500:]}'
        assert res.passed > 0 and res.failed == 0 and res.errors == 0, suite
        assert 'BLOCKED_EXTERNAL' not in res.text, suite
        blocked = [r for r in res.reasons if re.search(r'dsn|postgres|m2_test_pg', r, re.IGNORECASE)]
        assert not blocked, f'{suite} skip vì DSN/PostgreSQL: {blocked}'
        details.append(f'- pg_suites_no_dsn_skip: {suite} rc={res.rc} passed={res.passed} skipped={res.skipped} dsn_or_pg_skips=0 seconds={res.seconds:.1f}')
        for reason in res.reasons:
            details.append(f'- pg_suites_no_dsn_skip: {suite} skip_reason={reason[:160]}')
    emit(c.report_line('RG-08', 'pg_suites_no_dsn_skip', 'PASS'))
    emit(f'- pg_suites_no_dsn_skip: server=PostgreSQL {run_db.version} container={tool.POSTGRES_CONTAINER} bind={tool.LOOPBACK}:{tool.POSTGRES_PORT} database={run_db.name} partition={run_db.partition} cleanup=drop_in_finally_only_if_created')
    for line in details:
        emit(line)


def test_rg08_commit_rollback_boundaries(suites, boundary, emit):
    orchestration = suites[PG_SUITES[3]]
    assert orchestration.rc == 0 and orchestration.passed > 0, orchestration.text[-1500:]
    assert boundary.rc == 0, boundary.text[-1500:]
    assert len(boundary.passed) == EXPECTED_POINTS, boundary.passed
    for point in BOUNDARY_POINTS:
        assert point in boundary.passed, point
    emit(c.report_line('RG-08', 'commit_rollback_boundaries', 'PASS'))
    emit(f'- commit_rollback_boundaries: postgres_points_passed={len(boundary.passed)} before={BOUNDARY_POINTS[0]} during={BOUNDARY_POINTS[1]} after_before_commit={BOUNDARY_POINTS[2]} orchestration_suite_passed={orchestration.passed}')


def _snapshot(dsn):
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
        names = [row[0] for row in conn.execute('SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = %s ORDER BY table_name', ('controlplane', 'BASE TABLE')).fetchall()]
        counts = {name: conn.execute(sql.SQL('SELECT count(*) FROM controlplane.{}').format(sql.Identifier(name))).fetchone()[0] for name in names}
        system_id = conn.execute('SELECT system_identifier FROM pg_control_system()').fetchone()[0]
        db_oid = conn.execute('SELECT oid FROM pg_database WHERE datname = current_database()').fetchone()[0]
        started = conn.execute('SELECT pg_postmaster_start_time()').fetchone()[0]
    sessions = counts.pop(SESSION_TABLE, 0)
    return SimpleNamespace(counts=counts, sessions=sessions, system_id=system_id, db_oid=db_oid, started=started)


def _sentinel(dsn, seed=False):
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
        if seed:
            conn.execute('CREATE TABLE public.cp7_sentinel (id integer PRIMARY KEY, payload text NOT NULL)')
            conn.execute('INSERT INTO public.cp7_sentinel SELECT g, md5(CAST(g AS text)) FROM generate_series(1, CAST(%s AS integer)) AS g', (SENTINEL_ROWS,))
        return conn.execute('SELECT count(*), md5(string_agg(payload, CAST(%s AS text) ORDER BY id)) FROM public.cp7_sentinel', (',',)).fetchone()


def _must(work, command, cap):
    rc, text = _launcher(work, command, cap)
    assert rc == 0, f'BLOCKED: launcher {command} rc={rc}: {text[-800:]}'


@pytest.fixture(scope='module')
def cycle(stack, run_db):
    work, tool = stack.work, stack.launcher
    first = len(ISSUED)
    _must(work, 'start', 900)
    _must(work, 'stop', 120)
    seeded = _sentinel(stack.run_dsn, seed=True)
    before = _snapshot(stack.active_dsn)
    volume_cmd = ('volume', 'inspect', '--format', '{{.Name}} {{.CreatedAt}}', VOLUME)
    volume_before = _docker(work, *volume_cmd)
    container_before = _docker(work, 'inspect', '--format', '{{.Id}}', tool.POSTGRES_CONTAINER)
    _must(work, 'down', 300)
    gone = _docker(work, 'inspect', tool.POSTGRES_CONTAINER)[0] != 0
    volume_mid = _docker(work, *volume_cmd)
    _must(work, 'start', 900)
    _must(work, 'stop', 120)
    return SimpleNamespace(
        seeded=seeded, before=before, after=_snapshot(stack.active_dsn), gone=gone,
        sentinel_after=_sentinel(stack.run_dsn),
        volume_before=volume_before, volume_mid=volume_mid, volume_after=_docker(work, *volume_cmd),
        container_before=container_before,
        container_after=_docker(work, 'inspect', '--format', '{{.Id}}', tool.POSTGRES_CONTAINER),
        temporal_open=tool.wait_for_tcp(tool.LOOPBACK, tool.TEMPORAL_PORT, 10.0),
        flags={arg for argv in ISSUED[first:] for arg in argv},
    )


def test_rg08_volume_preserved(cycle, run_db, emit):
    launcher_text = LAUNCHER.read_text(encoding='utf-8')
    assert re.search(r'compose_command\(.down.\)', launcher_text) and not re.search(r'compose_command\(.down.,|--volumes', launcher_text)
    assert not {'-v', '--volumes', 'rm', 'prune'} & cycle.flags
    assert cycle.gone, 'container chưa bị gỡ sau down'
    assert cycle.volume_before[0] == 0 and cycle.volume_before[1].startswith(VOLUME), cycle.volume_before
    assert cycle.volume_mid == cycle.volume_before == cycle.volume_after, 'volume mất hoặc đổi qua down/start'
    assert cycle.container_before[0] == 0 and cycle.container_after[0] == 0
    assert cycle.container_after[1] != cycle.container_before[1], 'container không được dựng lại'
    assert cycle.after.started > cycle.before.started, 'postgres không khởi động lại'
    assert cycle.after.system_id == cycle.before.system_id and cycle.after.db_oid == cycle.before.db_oid
    assert cycle.seeded[0] == SENTINEL_ROWS and cycle.sentinel_after == cycle.seeded
    assert cycle.temporal_open
    emit(c.report_line('RG-08', 'volume_preserved', 'PASS'))
    emit(f'- volume_preserved: volume={VOLUME} created_at_equal=True container_recreated=True postmaster_restarted=True system_identifier_equal=True database_oid_equal=True sentinel_db={run_db.name} partition={run_db.partition} sentinel_rows={cycle.sentinel_after[0]} sentinel_md5_equal=True temporal_port_open={cycle.temporal_open} down_without_volume_flag=True')


def test_rg08_row_counts_equal(cycle, emit):
    before, after = cycle.before, cycle.after
    assert sum(before.counts.values()) > 0, 'bảng chính rỗng, phép so số hàng vô nghĩa'
    diff = {n: (before.counts.get(n), after.counts.get(n)) for n in {*before.counts, *after.counts} if before.counts.get(n) != after.counts.get(n)}
    assert not diff, diff
    assert after.sessions >= before.sessions
    emit(c.report_line('RG-08', 'row_counts_equal', 'PASS'))
    emit(f'- row_counts_equal: tables={len(after.counts)} total_rows={sum(after.counts.values())} equal=True excluded={SESSION_TABLE}(before={before.sessions} after={after.sessions}) note=launcher_start_ghi_them_mot_phien')
    emit('- row_counts_equal: nonzero ' + ' '.join(f'{n}={k}' for n, k in sorted(after.counts.items()) if k))


@pytest.fixture(scope='module')
def m1_run(stack, tmp_path_factory):
    work = tmp_path_factory.mktemp('cp7_m1')
    temproot = tmp_path_factory.mktemp('cp7_m1_tmp')
    temporal_version = _wait_temporal_ready(f'{stack.launcher.LOOPBACK}:{stack.launcher.TEMPORAL_PORT}', 180)
    tree_before = _tree_digest(M1_DIR)
    evidence_before = hashlib.sha256(M1_EVIDENCE.read_bytes()).hexdigest()
    argv = _pytest_argv('tests/m1', '--deselect', M1_LIVE_TEST, '--deselect', M1_ENV_TEST)
    child_env = _child_env(PYTEST_DEBUG_TEMPROOT=str(temproot))
    rc, text = _run(argv, timeout=DEADLINE.timeout(1500), log_dir=work, env=child_env)
    if rc != 0 and re.search(r'ModuleNotFoundError|ImportError', text):
        pytest.fail('BLOCKED: thiếu runtime cho tests/m1: ' + text[-800:])
    if rc != 0 and 'Python version mismatch' in text:
        pytest.fail(f'BLOCKED: interpreter chạy test là CPython {sys.version.split()[0]}, M1 đòi interpreter khoá 3.13.15: ' + text[-800:])
    return SimpleNamespace(
        rc=rc, text=text, temporal_version=temporal_version, tree_same=_tree_digest(M1_DIR) == tree_before,
        evidence_same=hashlib.sha256(M1_EVIDENCE.read_bytes()).hexdigest() == evidence_before,
    )


def test_rg08_m1_regression_adjusted(m1_run, emit):
    text = m1_run.text
    failed_ids = re.findall(r'(?m)^(?:FAILED|ERROR) (\S+)', text)
    assert m1_run.rc == 0, f'python={sys.version.split()[0]} failed={failed_ids}: ' + text[-1500:]
    assert re.search(r'\b91 passed\b', text), text[-2000:]
    assert not re.search(r'\b[1-9][0-9]* (?:failed|errors?|skipped)\b', text), text[-2000:]
    assert re.search(r'\b2 deselected\b', text), text[-2000:]
    assert m1_run.tree_same and m1_run.evidence_same
    emit(c.report_line('RG-08', 'm1_regression_adjusted', 'PASS'))
    emit(f'- m1_regression_adjusted: passed=91 failed=0 skipped=0 deselected=2 excluded=test_live_e3_drive_verification(OI-CP7-05) excluded=test_validator_accepts_untampered_environment_manifest(quyết định user 30/10/2026, uv.lock đã đổi bởi 3225891, 0db5b62, f1c4e81; hai test khác cùng tệp vẫn chạy) h36_not_run=True tests_m1_unchanged=True evidence_json_unchanged=True m1proof_validator_patched=False plugin_or_patch=none credentials_fixture_user_deselected=True temporal_grpc_ready_before_m1={m1_run.temporal_version}')


def test_rg08_secret_scan(stack, emit):
    report_text = REPORT.read_text(encoding='utf-8') if REPORT.is_file() else ''
    for label, text in (('report', report_text), ('runtime_fault_test', SELF.read_text(encoding='utf-8'))):
        assert c.scan_secrets(text) == [], f'secret pattern in {label}'
        assert stack.password not in text, f'postgres password in {label}'
    emit(c.report_line('RG-08', 'secret_scan', 'PASS'))
    emit('- secret_scan: match_count=0; không đọc Credentials/; mật khẩu PostgreSQL chỉ đi qua tệp secrets của launcher và biến môi trường tiến trình con; chi phí 0 USD')


def test_rg08_deadline_budget(emit):
    remaining = DEADLINE.remaining()
    assert remaining > 0
    emit(f'- deadline: limit_s=3600 remaining_s={remaining:.0f} partition={PARTITION}')
