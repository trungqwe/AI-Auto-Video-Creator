"""CP7-12 / RG-11: xoay secret, thu hồi credential ngắn hạn, rollback cấu hình; trần 0 USD, không gọi AI; Deadline 90 phút; dừng bằng Ctrl+C; không đụng bí mật thật (OI-CP7-07)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
if str(REPO / 'tools' / 'real') not in sys.path:
    sys.path.insert(0, str(REPO / 'tools' / 'real'))
if str(REPO / 'src') not in sys.path:
    sys.path.insert(0, str(REPO / 'src'))

import psycopg  # noqa: E402
import pytest  # noqa: E402
from psycopg import sql  # noqa: E402

import cp7_batch_driver as d  # noqa: E402
import cp7_common as c  # noqa: E402

DEADLINE = c.Deadline(90 * 60)
ROTATE_REF = 'cp7-rotate'
STATE = {'values': [], 'lines': []}


def _data_root():
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'


def _pass(emit, item, *details):
    line = c.report_line('RG-11', item, 'PASS')
    emit(line)
    STATE['lines'].append(line)
    for detail in details:
        assert detail.isascii(), f'detail must be ascii: {detail}'
        emit('- ' + item + ': ' + detail)
        STATE['lines'].append('- ' + item + ': ' + detail)


def test_rg11_rotation_old_version_rejected(emit):
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.secret_redaction import SecretValue
    from controlplane.security.broker import CredentialBroker, UnauthorizedSecretAccessError

    store = DpapiSecretStore(_data_root() / 'vault')
    old = 'cp7-rg11-synth-old-' + uuid.uuid4().hex
    new = 'cp7-rg11-synth-new-' + uuid.uuid4().hex
    STATE['values'].append(old)
    STATE['values'].append(new)
    v1 = store.put(ROTATE_REF, SecretValue(old))
    v2 = store.put(ROTATE_REF, SecretValue(new))
    assert v2 == v1 + 1
    assert store.current_version(ROTATE_REF) == v2

    try:
        ref_dir = _data_root() / 'vault' / hashlib.sha256(ROTATE_REF.encode('utf-8')).hexdigest()
        with CredentialBroker(store.export_vault([ROTATE_REF])).acquire_secret(ROTATE_REF) as h:
            got = h.get_secret_value()
        assert got == new and got != old

        store.revoke(ROTATE_REF, v1)
        assert not (ref_dir / f'v{v1}.bin').exists()
        assert (ref_dir / f'v{v1}.revoked').exists()
        assert store.current_version(ROTATE_REF) == v2
        assert store.export_vault([ROTATE_REF])[ROTATE_REF] == (ref_dir / f'v{v2}.bin').read_bytes()
        with CredentialBroker(store.export_vault([ROTATE_REF])).acquire_secret(ROTATE_REF) as h:
            assert h.get_secret_value() == new
        store.revoke(ROTATE_REF, v1)

        blob = b''.join(p.read_bytes() for p in ref_dir.iterdir() if p.is_file())
        assert old.encode() not in blob and new.encode() not in blob

        store.revoke(ROTATE_REF, v2)
        assert store.export_vault([ROTATE_REF]) == {}
        with pytest.raises(UnauthorizedSecretAccessError):
            with CredentialBroker({}).acquire_secret(ROTATE_REF):
                pass

        _pass(emit, 'rotation_old_version_rejected', f'versions=v{v1}->v{v2} old_bin_removed=True old_revoked_marker=True export_is_new_version=True all_revoked_denied=True')
    finally:
        for v in (v1, v2):
            try:
                store.revoke(ROTATE_REF, v)
            except (ValueError, FileNotFoundError):
                pass


MIGRATIONS_DIR = REPO / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
PROTECTED_DBS = frozenset({'controlplane', 'postgres', 'temporal', 'temporal_visibility', 'template0', 'template1'})
RUN_DB = 'cp7_' + uuid.uuid4().hex[:12]


@pytest.fixture(scope='module')
def stack(tmp_path_factory):
    work = tmp_path_factory.mktemp('cp7_rg11')
    tool = d.load_launcher()
    layout = tool.resolve_layout(os.environ)
    password = tool.load_or_create_password(layout)
    admin_dsn = tool.build_dsn(password, 'postgres')
    try:
        psycopg.connect(admin_dsn, connect_timeout=10).close()
    except psycopg.OperationalError:
        d.start_capturing(work, 'bring_up')
        d.stop_until_exited()
        try:
            psycopg.connect(admin_dsn, connect_timeout=10).close()
        except psycopg.OperationalError:
            pytest.fail('BLOCKED: PostgreSQL thật chưa kết nối được')
    return SimpleNamespace(
        work=work, tool=tool, layout=layout, password=password,
        admin_dsn=admin_dsn, active_db=tool.active_db_name(layout),
    )


@pytest.fixture(scope='module')
def run_db(stack):
    assert re.fullmatch(r'cp7_[0-9a-f]{12}', RUN_DB)
    assert RUN_DB not in PROTECTED_DBS and RUN_DB != stack.active_db
    with psycopg.connect(stack.admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(RUN_DB)))
    dsn = stack.tool.build_dsn(stack.password, RUN_DB)
    from controlplane.infrastructure.db.migration_runner import MigrationRunner
    MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=RUN_DB).migrate_up()

    ws = str(uuid.uuid4())
    actor = str(uuid.uuid4())
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)',
            (ws, 'cp7-rg11', 'ACTIVE'),
        )
        conn.execute(
            'INSERT INTO controlplane.cp_actors (actor_id, workspace_id, actor_type, display_name, status) VALUES (%s, %s, %s, %s, %s)',
            (actor, ws, 'user', 'cp7-rg11-actor', 'ACTIVE'),
        )
    try:
        yield SimpleNamespace(dsn=dsn, ws=ws)
    finally:
        with psycopg.connect(stack.admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(RUN_DB)))
            assert admin.execute('SELECT count(*) FROM pg_database WHERE datname = %s', (RUN_DB,)).fetchone()[0] == 0


def test_rg11_revoke_job_waiting(stack, run_db, emit):
    from controlplane.infrastructure.db.config_security import PostgresConfigSecurityRepository
    from controlplane.domain.config_security.external_account import ExternalAccount
    from controlplane.domain.config_security.status_graph import ExternalAccountStatus
    from controlplane.application.config_security.credential_issuance import (
        CredentialIssuer, validate_grant, GrantRevokedError,
    )
    from controlplane.application.orchestration.job_lifecycle import JobLifecycleListener
    from controlplane.application.storage_meta.persist_handler import CREDENTIAL_UNAVAILABLE
    from controlplane.infrastructure.security.secret_redaction import SecretValue

    conn = psycopg.connect(run_db.dsn, autocommit=True)
    ws = run_db.ws
    try:
        conn.execute(
            'INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)',
            ('cp7-batch', ws, 'RUNNING', 1),
        )
        conn.execute(
            'INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, %s, %s, %s, %s, %s)',
            ('cp7-job', 'cp7-batch', ws, 'ACTIVE', 'snap-1', 1),
        )

        PostgresConfigSecurityRepository(conn).register_secret_handle(
            secret_handle_id=str(uuid.uuid4()), workspace_id=ws, provider_ref='cp7-synthetic',
            account_ref='cp7-acct', alias_ref='cp7-rotate', redacted_fingerprint_or_version='v1',
            validation_status='valid', audit_ref='cp7-12', credential_version=1, revocation_version=0,
        )

        class _PgRevocations:
            def __init__(self, c_conn, w_id):
                self._c = c_conn
                self._w = w_id

            def revocation_version(self, account_ref):
                row = self._c.execute('SELECT revocation_version FROM controlplane.cp_secret_handles WHERE workspace_id=%s AND account_ref=%s', (self._w, account_ref)).fetchone()
                return int(row[0]) if row else 0

        class _Minter:
            def mint(self, grant):
                val = 'cp7-rg11-synth-short-' + uuid.uuid4().hex
                STATE['values'].append(val)
                return SecretValue(val)

        revs = _PgRevocations(conn, ws)
        account = ExternalAccount(
            external_account_id='cp7-acct', workspace_id=ws, provider='cp7-synthetic',
            account_label='cp7-rg11', status=ExternalAccountStatus.ENABLED, project_ref=None,
            capabilities=frozenset({'cp7-cap'}), credential_version=1, credential_updated_at=None,
            credential_expires_at=None, quota_observation_ref=None, health=None, revision=1,
        )

        issuer = CredentialIssuer(_Minter(), revs, 300)
        now = datetime.now(timezone.utc)
        cred1 = issuer.issue(account, 'worker', 'cp7-cap', ['cp7.use'], 60, now, job_ref='cp7-job', workspace_id=ws)
        validate_grant(cred1.grant, account, now, revs)

        conn.execute(
            "UPDATE controlplane.cp_secret_handles SET revocation_version = revocation_version + 1 WHERE workspace_id=%s AND account_ref='cp7-acct'",
            (ws,),
        )
        with pytest.raises(GrantRevokedError):
            validate_grant(cred1.grant, account, now, revs)

        listener = JobLifecycleListener(lambda: psycopg.connect(run_db.dsn, autocommit=True), workspace_id=ws)
        listener.on_result(
            {'stage_run_id': 'cp7-job:sync:r1', 'activity_name': 'PersistVideoOutput'},
            {'disposition': 'waiting', 'problem': {'code': CREDENTIAL_UNAVAILABLE, 'retryable': True}},
        )
        row = conn.execute(
            "SELECT status, wait_reason FROM controlplane.cp_video_jobs WHERE workspace_id=%s AND job_id='cp7-job'",
            (ws,),
        ).fetchone()
        assert row == ('WAITING', 'credential_unavailable')
        assert conn.execute('SELECT count(*) FROM controlplane.cp_video_jobs WHERE workspace_id=%s', (ws,)).fetchone()[0] == 1

        cred2 = issuer.issue(account, 'worker', 'cp7-cap', ['cp7.use'], 60, now, job_ref='cp7-job', workspace_id=ws)
        validate_grant(cred2.grant, account, now, revs)
        with pytest.raises(GrantRevokedError):
            validate_grant(cred1.grant, account, now, revs)

        listener.on_result(
            {'stage_run_id': 'cp7-job:sync:r1', 'activity_name': 'CheckResume'},
            {'disposition': 'succeeded'},
        )
        row = conn.execute(
            "SELECT status, wait_reason FROM controlplane.cp_video_jobs WHERE workspace_id=%s AND job_id='cp7-job'",
            (ws,),
        ).fetchone()
        assert row == ('ACTIVE', None)

        _pass(emit, 'revoke_job_waiting', 'old_grant_rejected=True job_wait_reason=credential_unavailable job_rows=1 resumed_active_after_new_credential=True db=disposable')
    finally:
        conn.close()


class _Api(d.ApiSession):
    def put_config(self, scope, payload, if_match):
        headers = {
            'Cookie': '; '.join(f'{k}={v}' for k, v in self.cookies.items()),
            'Origin': f'https://{d.HOST}:{d.PORT}',
            'X-CSRF-Token': self.cookies['csrf_token'],
            'Content-Type': 'application/json',
            'Idempotency-Key': str(uuid.uuid4()),
            'If-Match': str(if_match),
        }
        body = json.dumps(payload).encode('utf-8')
        t0 = time.perf_counter()
        status, _, text = self._request('PUT', '/v1/configs/' + scope, headers, body)
        return status, (time.perf_counter() - t0) * 1000.0, text


@pytest.fixture(scope='module')
def live(stack):
    db = d.ReadOnlyDb(stack.tool)
    d.stop_until_exited()
    try:
        d.require_no_other_workflows()
    except d.BlockedError as exc:
        pytest.fail(str(exc))
    launch_path, _, _ = d.start_capturing(stack.work, 'rg11')
    session = _Api(db.layout.cert_file)
    session.open(launch_path)
    try:
        yield SimpleNamespace(db=db, session=session)
    finally:
        d.stop_until_exited()


def _latest_config(db, kind, key):
    rows = db.query(
        'SELECT config_revision_number, revision, content_hash FROM controlplane.cp_config_revisions WHERE workspace_id = %s AND scope_kind = %s AND scope_key = %s ORDER BY config_revision_number DESC LIMIT 1',
        kind, key,
    )
    return rows[0] if rows else (0, 0, None)


def _scope_rows(db, kind, key):
    return db.query(
        'SELECT config_revision_number, content_hash, payload::text FROM controlplane.cp_config_revisions WHERE workspace_id = %s AND scope_kind = %s AND scope_key = %s ORDER BY config_revision_number ASC',
        kind, key,
    )


def test_rg11_rollback_hash_restored(live, emit):
    kind = 'policy'
    key = 'cp7-rg11-probe'
    scope = f'{kind}:{key}'
    A = {'cp7_probe': 'A', 'limit': 1}
    B = {'cp7_probe': 'B', 'limit': 2}
    before = _scope_rows(live.db, kind, key)
    (n0, _, _) = _latest_config(live.db, kind, key)

    (num, rev, _) = _latest_config(live.db, kind, key)
    status, _, text = live.session.put_config(scope, A, rev)
    assert status in (200, 202), f'status={status}: {c.redact(text[:200])}'
    num_a, _, hash_a = _latest_config(live.db, kind, key)

    (num, rev, _) = _latest_config(live.db, kind, key)
    status, _, text = live.session.put_config(scope, B, rev)
    assert status in (200, 202), f'status={status}: {c.redact(text[:200])}'
    num_b, _, hash_b = _latest_config(live.db, kind, key)

    (num, rev, _) = _latest_config(live.db, kind, key)
    status, _, text = live.session.put_config(scope, A, rev)
    assert status in (200, 202), f'status={status}: {c.redact(text[:200])}'
    num_c, _, hash_c = _latest_config(live.db, kind, key)

    assert hash_a != hash_b
    assert hash_c == hash_a
    assert (num_a, num_b, num_c) == (n0 + 1, n0 + 2, n0 + 3)

    after = _scope_rows(live.db, kind, key)
    assert after[:len(before)] == before
    assert len(after) == len(before) + 3
    assert after[len(before)][0] == n0 + 1 and after[len(before)][1] == hash_a
    assert after[len(before) + 1][0] == n0 + 2 and after[len(before) + 1][1] == hash_b

    _pass(emit, 'rollback_hash_restored', f'scope={scope} revisions=n{n0+1}->n{n0+3} hash_a={hash_a[:8]} hash_b={hash_b[:8]} hash_after_rollback={hash_c[:8]} old_rows_unchanged=True')


def test_rg11_secret_scan(emit):
    surfaces = [('emitted', chr(10).join(STATE['lines']))]
    logs_dir = _data_root() / 'logs'
    if logs_dir.is_dir():
        for p in logs_dir.glob('*.log'):
            try:
                surfaces.append((p.name, p.read_text(encoding='utf-8', errors='replace')))
            except Exception:
                pass
    report_file = REPO / 'docs' / 'delivery-evidence' / 'cp7-12' / 'report.md'
    if report_file.is_file():
        surfaces.append(('report', report_file.read_text(encoding='utf-8', errors='replace')))

    total_matches = 0
    for name, text in surfaces:
        total_matches += len(c.scan_secrets(text))
        for value in STATE['values']:
            assert text.count(value) == 0, f'synthetic value hit in {name}'

    assert total_matches == 0
    assert len(STATE['values']) >= 3
    _pass(emit, 'secret_scan', f'surfaces={len(surfaces)} secret_pattern_matches=0 synthetic_value_hits=0')
