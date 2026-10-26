"""PERSIST-I: kiem tra adapter PostgreSQL cua storage metadata tren PostgreSQL 18.6."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import uuid

import psycopg
import psycopg.errors
import pytest

from controlplane.application.storage_meta import ArtifactLocationStore, ArtifactVersionStore, CleanupAuthorizationStore
from controlplane.application.storage_meta.cloud_persist import PersistArtifactToCloud, UploadReceipt, UploadReceiptState
from controlplane.application.storage_meta.declare_version import DeclareArtifactVersionService
from controlplane.application.storage_meta.materialization import WorkingSetPolicy
from controlplane.domain.events import DomainEvent
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta.declaration import DeclareArtifactVersionRequest
from controlplane.domain.storage_meta.verification import IntegrityObservation
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
from controlplane.infrastructure.db.storage_meta.catalog import PostgresArtifactVersionCatalog
from controlplane.infrastructure.db.storage_meta.records import ArtifactLocationFields, ArtifactVersionExtension, RevisionPlacement
from controlplane.infrastructure.db.uow import TransactionManager

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
STORAGE_META_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'storage_meta'
try:
    _port = subprocess.check_output(['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'], text=True, stderr=subprocess.DEVNULL).strip().split(':')[-1]
    _DEFAULT_DSN = f'postgresql://m2test:m2test@127.0.0.1:{_port}/postgres'
except Exception:
    _DEFAULT_DSN = 'postgresql://m2test:m2test@127.0.0.1:57027/postgres'
PG_DSN = os.environ.get('M2_TEST_PG_DSN', _DEFAULT_DSN)
HASH_A = 'a' * 64
HASH_B = 'b' * 64


@pytest.fixture
def db():
    name = f'persist_i_{uuid.uuid4().hex[:8]}'
    admin = psycopg.connect(PG_DSN, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        dsn = PG_DSN.rsplit('/', 1)[0] + f'/{name}'
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        yield dsn, add_workspace(dsn)
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
        admin.close()


@pytest.fixture
def conn(db):
    with psycopg.connect(db[0]) as connection:
        yield connection


def add_workspace(dsn: str) -> str:
    workspace_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as seed:
        seed.execute(
            'INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)',
            (workspace_id, 'w', 'ACTIVE'),
        )
    return str(workspace_id)


def count(connection, table, where='true', params=()):
    return connection.execute(
        f'SELECT count(*) FROM controlplane.{table} WHERE {where}', params
    ).fetchone()[0]


def version_values(ws, artifact_id='artifact-i', sha=HASH_A, size=128, **extra):
    return {'workspace_id': ws, 'artifact_id': artifact_id, 'sha256_hash': sha, 'size_bytes': size, 'mime_type': 'video/mp4', 'artifact_kind': 'rendered_video', 'owner_ref': 'owner-i', 'retention_ref': 'retention-i', 'sensitivity_ref': 'internal', **extra}


def seed_version(conn, ws, artifact_id='artifact-i', sha=HASH_A, size=128):
    version = PostgresStorageMetaRepository(conn, ws).insert_version(str(uuid.uuid4()), version_values(ws, artifact_id, sha, size))
    conn.commit()
    return version.artifact_version_id


def location_values(ws, version_id, name='obj-1', **extra):
    return {'workspace_id': ws, 'artifact_version_id': version_id, 'backend_ref': 'local-disk', 'provider_namespace_ref': 'ns-i', 'provider_object_ref': name, 'logical_locator': f'loc/{name}', **extra}


def test_migrations_to_18_and_schema_matches_0010(db):
    with psycopg.connect(db[0], autocommit=True) as connection:
        assert [r[0] for r in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()] == list(range(1, 20))
        table_cols = {
            'cp_artifact_versions': {'intended_storage_class', 'producer_operation_ref', 'lineage_refs'},
            'cp_artifact_locations': {'device_ref', 'logical_category', 'last_verified_at', 'lease_ref', 'retention_state', 'cleanup_state'},
            'cp_upload_receipts': {'workspace_id', 'operation_key', 'artifact_version_id', 'source_location_id', 'target_backend_ref', 'provider_object_ref', 'state', 'verification_evidence_ref', 'revision', 'created_at', 'updated_at'},
            'cp_materialization_leases': {'workspace_id', 'lease_ref', 'operation_key', 'device_ref', 'staging_root_ref', 'expected_total_bytes', 'state', 'expires_at', 'revision', 'created_at', 'updated_at'},
            'cp_revision_placements': {'workspace_id', 'placement_id', 'artifact_version_id', 'revision_ref', 'storage_class', 'location_id', 'created_at'},
            'cp_working_set_policies': {'workspace_id', 'policy_ref', 'policy_revision', 'max_videos_per_render', 'max_working_set_bytes', 'created_at'},
        }
        for table, expected in table_cols.items():
            cols = {r[0] for r in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'controlplane' AND table_name = %s", (table,)).fetchall()}
            assert expected <= cols, f"Missing columns in {table}: {expected - cols}"
        recovery_epoch_type = connection.execute("SELECT data_type FROM information_schema.columns WHERE table_schema = 'controlplane' AND table_name = 'cp_cleanup_authorizations' AND column_name = 'recovery_epoch'").fetchone()[0]
        assert recovery_epoch_type == 'text'
        check_constraints = [r[0] for r in connection.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'controlplane.cp_upload_receipts'::regclass AND contype = 'c'").fetchall()]
        assert any('OUTCOME_UNKNOWN' in c for c in check_constraints)


def test_repository_and_catalog_expose_all_port_methods():
    for name in ('find_version', 'insert_version', 'get_version', 'insert_location', 'get_location', 'update_location', 'insert_authorization', 'authorize_location', 'get', 'save'):
        assert callable(getattr(PostgresStorageMetaRepository, name))
    for name in ('find_matching', 'find_artifact_id', 'insert_version'):
        assert callable(getattr(PostgresArtifactVersionCatalog, name))


def declare_payload(**extra):
    return {'artifact_kind': 'rendered_video', 'owner_resource_ref': 'job-1', 'content_sha256': HASH_A, 'size_bytes': 256, 'media_type': 'video/mp4', 'lineage_refs': ['src-1'], 'retention_class': 'standard', 'sensitivity_class': 'internal', 'intended_storage_class': 'cloud-cold', 'producer_operation_ref': 'op-render-1', **extra}


def test_version_round_trip_with_extension_columns(conn, db):
    ws = db[1]
    repository = PostgresStorageMetaRepository(conn, ws)
    version_id = str(uuid.uuid4())
    values = version_values(ws, intended_storage_class='cloud-cold', producer_operation_ref='op-1', lineage_refs=['parent-a', 'parent-b'])
    inserted = repository.insert_version(version_id, values)
    conn.commit()
    assert inserted is not None and inserted.artifact_version_id == version_id
    assert repository.get_version_extension(ws, version_id) == ArtifactVersionExtension(version_id, 'cloud-cold', 'op-1', ('parent-a', 'parent-b'))
    assert repository.find_version(ws, 'artifact-i', HASH_A) == inserted and repository.get_version(ws, version_id) == inserted
    assert repository.insert_version(str(uuid.uuid4()), values) is None
    assert count(conn, 'cp_artifact_versions') == 1
    plain = seed_version(conn, ws, 'artifact-plain', HASH_B)
    assert repository.get_version_extension(ws, plain) == ArtifactVersionExtension(plain, None, None, ())
    assert repository.get_version_extension(add_workspace(db[0]), version_id) is None


def test_register_duplicate_returns_existing_version(conn, db):
    ws = db[1]
    store = ArtifactVersionStore(lambda c: PostgresStorageMetaRepository(c, ws))
    values = version_values(ws)
    first = store.register(**values, connection=conn)
    second = store.register(**{**values, 'size_bytes': 999}, connection=conn)
    assert second == first and second.size_bytes == 128
    assert count(conn, 'cp_artifact_versions') == 1


def test_catalog_declare_is_idempotent_and_workspace_scoped(conn, db):
    ws = db[1]
    catalog = PostgresArtifactVersionCatalog(conn, ws)
    service = DeclareArtifactVersionService(catalog)
    first = service.declare(declare_payload())
    conn.commit()
    assert first.matched_existing is False and first.policy_decision == 'new_version'
    again = service.declare(declare_payload())
    assert again.matched_existing is True and again.artifact_version_id == first.artifact_version_id and again.artifact_id == first.artifact_id
    assert count(conn, 'cp_artifact_versions') == 1
    row = conn.execute('SELECT artifact_kind, owner_ref, sha256_hash, size_bytes, mime_type, retention_ref, sensitivity_ref, intended_storage_class, producer_operation_ref, lineage_refs FROM controlplane.cp_artifact_versions WHERE artifact_version_id = %s', (first.artifact_version_id,)).fetchone()
    assert row == ('rendered_video', 'job-1', HASH_A, 256, 'video/mp4', 'standard', 'internal', 'cloud-cold', 'op-render-1', ['src-1'])
    revised = service.declare(declare_payload(content_sha256=HASH_B, size_bytes=300))
    conn.commit()
    assert revised.matched_existing is False and revised.artifact_id == first.artifact_id and revised.artifact_version_id != first.artifact_version_id
    assert count(conn, 'cp_artifact_versions') == 2
    assert catalog.find_matching('job-1', 'rendered_video', HASH_A).artifact_version_id == first.artifact_version_id
    assert catalog.find_matching('job-1', 'rendered_video', 'c' * 64) is None and catalog.find_artifact_id('other', 'rendered_video') is None
    other = PostgresArtifactVersionCatalog(conn, add_workspace(db[0]))
    assert other.find_matching('job-1', 'rendered_video', HASH_A) is None and other.find_artifact_id('job-1', 'rendered_video') is None
    with pytest.raises(psycopg.errors.UniqueViolation):
        catalog.insert_version(first.artifact_id, str(uuid.uuid4()), DeclareArtifactVersionRequest(**declare_payload()))
    conn.rollback()


def make_cleanup_eligible(conn, ws, version_id, name):
    store = ArtifactLocationStore(lambda c: PostgresStorageMetaRepository(c, ws))
    location = store.declare(**location_values(ws, version_id, name), connection=conn)
    for state in (ArtifactLocationState.MATERIALIZING, ArtifactLocationState.AVAILABLE_UNVERIFIED, ArtifactLocationState.VERIFYING, ArtifactLocationState.VERIFIED, ArtifactLocationState.CLEANUP_ELIGIBLE):
        location = store.transition(workspace_id=ws, location_id=location.location_id, expected_revision=location.revision, requested_state=state, verification_evidence_ref='verify-i', connection=conn)
    conn.commit()
    return location


def authorize_cleanup(conn, ws, version_id, location, epoch, current_epoch):
    now = datetime.now(timezone.utc)
    store = CleanupAuthorizationStore(lambda c: PostgresStorageMetaRepository(c, ws))
    return store.authorize(workspace_id=ws, location_id=location.location_id, expected_revision=location.revision, artifact_version_id=version_id, artifact_hash=HASH_A, reason='retention-complete', policy_revision='policy-i', completion_evidence_ref='completion-i', verification_evidence_ref='verify-i', issued_at=now, expires_at=now + timedelta(hours=1), recovery_epoch=epoch, current_recovery_epoch=current_epoch, authorizing_owner_ref='owner-i', actor_ref='actor-i', audit_ref='audit-i', correlation_ref='corr-i', connection=conn)


def test_versions_and_authorizations_reject_update_and_delete(conn, db):
    ws = db[1]
    version_id = seed_version(conn, ws)
    authorization = authorize_cleanup(conn, ws, version_id, make_cleanup_eligible(conn, ws, version_id, 'obj-im'), '007', '007')
    conn.commit()
    auth_id = authorization.cleanup_authorization_id
    attempts = (
        ('UPDATE controlplane.cp_artifact_versions SET size_bytes = 1 WHERE artifact_version_id = %s', (version_id,)),
        ('DELETE FROM controlplane.cp_artifact_versions WHERE artifact_version_id = %s', (version_id,)),
        ('UPDATE controlplane.cp_cleanup_authorizations SET reason = %s WHERE cleanup_authorization_id = %s', ('changed', auth_id)),
        ('DELETE FROM controlplane.cp_cleanup_authorizations WHERE cleanup_authorization_id = %s', (auth_id,)),
    )
    for statement, params in attempts:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(statement, params)
        conn.rollback()
    assert count(conn, 'cp_artifact_versions') == 1 and count(conn, 'cp_cleanup_authorizations') == 1
    assert conn.execute('SELECT size_bytes FROM controlplane.cp_artifact_versions WHERE artifact_version_id = %s', (version_id,)).fetchone()[0] == 128


def test_cleanup_authorization_recovery_epoch_is_text(conn, db):
    ws = db[1]
    version_id = seed_version(conn, ws)
    data_type = conn.execute("SELECT data_type FROM information_schema.columns WHERE table_schema = 'controlplane' AND table_name = 'cp_cleanup_authorizations' AND column_name = 'recovery_epoch'").fetchone()[0]
    assert data_type == 'text'
    leading_zero = authorize_cleanup(conn, ws, version_id, make_cleanup_eligible(conn, ws, version_id, 'obj-e1'), '007', '007')
    assert leading_zero.recovery_epoch == '007'
    stored = conn.execute('SELECT recovery_epoch FROM controlplane.cp_cleanup_authorizations WHERE cleanup_authorization_id = %s', (leading_zero.cleanup_authorization_id,)).fetchone()[0]
    assert stored == '007' and isinstance(stored, str)
    named = authorize_cleanup(conn, ws, version_id, make_cleanup_eligible(conn, ws, version_id, 'obj-e2'), 'epoch-b', 'epoch-b')
    assert named.recovery_epoch == 'epoch-b'
    numeric = authorize_cleanup(conn, ws, version_id, make_cleanup_eligible(conn, ws, version_id, 'obj-e3'), 7, 7)
    assert numeric.recovery_epoch == '7' and str(numeric.recovery_epoch) == str(7)
    with pytest.raises(ValueError, match='stale recovery epoch'):
        authorize_cleanup(conn, ws, version_id, make_cleanup_eligible(conn, ws, version_id, 'obj-e4'), 'epoch-a', 'epoch-b')


def make_receipt(version_id, state=UploadReceiptState.PREPARED, evidence=None, key='op-1', object_id='obj-cloud-1', sha=HASH_A, size=128):
    return UploadReceipt(key, version_id, sha, size, object_id, state, evidence)


def test_location_ct_sto_002_fields_round_trip(conn, db):
    ws = db[1]
    version_id = seed_version(conn, ws)
    repository = PostgresStorageMetaRepository(conn, ws)
    store = ArtifactLocationStore(lambda c: PostgresStorageMetaRepository(c, ws))
    verified_at = datetime(2026, 10, 22, 7, 0, tzinfo=timezone.utc)
    location = store.declare(**location_values(ws, version_id, 'obj-f1', device_ref='disk-1', logical_category='render-output', last_verified_at=verified_at, lease_ref='lease-f1', retention_state='RETAINED', cleanup_state='NONE'), connection=conn)
    conn.commit()
    fields = repository.get_location_fields(ws, location.location_id)
    assert fields is not None and (fields.location_id, fields.device_ref, fields.logical_category, fields.lease_ref, fields.retention_state, fields.cleanup_state) == (location.location_id, 'disk-1', 'render-output', 'lease-f1', 'RETAINED', 'NONE')
    assert datetime.fromisoformat(fields.last_verified_at) == verified_at
    plain = store.declare(**location_values(ws, version_id, 'obj-f2'), connection=conn)
    conn.commit()
    assert repository.get_location_fields(ws, plain.location_id) == ArtifactLocationFields(plain.location_id, None, None, None, None, None, None)
    for state in (ArtifactLocationState.MATERIALIZING, ArtifactLocationState.AVAILABLE_UNVERIFIED, ArtifactLocationState.VERIFYING):
        plain = store.transition(workspace_id=ws, location_id=plain.location_id, expected_revision=plain.revision, requested_state=state, verification_evidence_ref='verify-f2', connection=conn)
    assert repository.get_location_fields(ws, plain.location_id).last_verified_at is None
    plain = store.transition(workspace_id=ws, location_id=plain.location_id, expected_revision=plain.revision, requested_state=ArtifactLocationState.VERIFIED, verification_evidence_ref='verify-f2', connection=conn)
    assert repository.get_location_fields(ws, plain.location_id).last_verified_at is not None
    assert repository.get_location_fields(ws, str(uuid.uuid4())) is None


def test_upload_receipt_round_trip_and_outcome_unknown(conn, db):
    ws = db[1]
    version_id = seed_version(conn, ws)
    repository = PostgresStorageMetaRepository(conn, ws)
    assert repository.get('op-1') is None
    prepared = make_receipt(version_id)
    repository.save(prepared)
    conn.commit()
    assert repository.get('op-1') == prepared
    unknown = make_receipt(version_id, UploadReceiptState.OUTCOME_UNKNOWN)
    repository.save(unknown)
    conn.commit()
    assert repository.get('op-1') == unknown
    row = conn.execute('SELECT state, revision, target_backend_ref FROM controlplane.cp_upload_receipts WHERE workspace_id = %s AND operation_key = %s', (ws, 'op-1')).fetchone()
    assert row == ('OUTCOME_UNKNOWN', 2, 'cloud')
    verified = make_receipt(version_id, UploadReceiptState.VERIFIED, 'evidence-1')
    repository.save(verified)
    conn.commit()
    assert repository.get('op-1') == verified
    for lost in (UploadReceiptState.CORRUPT, UploadReceiptState.MISSING):
        repository.save(make_receipt(version_id, lost))
        conn.commit()
        assert conn.execute('SELECT state FROM controlplane.cp_upload_receipts WHERE operation_key = %s', ('op-1',)).fetchone()[0] == 'FAILED'
        assert repository.get('op-1').state is UploadReceiptState.CORRUPT
    assert count(conn, 'cp_upload_receipts') == 1


def test_upload_receipt_unique_per_operation_key_and_bound_to_version(conn, db):
    ws = db[1]
    version_id = seed_version(conn, ws)
    other_version = seed_version(conn, ws, 'artifact-2', HASH_B, 64)
    repository = PostgresStorageMetaRepository(conn, ws)
    repository.save(make_receipt(version_id))
    conn.commit()
    assert count(conn, 'cp_upload_receipts') == 1
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute('INSERT INTO controlplane.cp_upload_receipts (workspace_id, operation_key, artifact_version_id, target_backend_ref, state, revision) VALUES (%s, %s, %s, %s, %s, %s)', (ws, 'op-1', version_id, 'cloud', 'PREPARED', 1))
    conn.rollback()
    with pytest.raises(ValueError):
        repository.save(make_receipt(other_version, sha=HASH_B, size=64))
    with pytest.raises(ValueError):
        repository.save(make_receipt(version_id, object_id='other-object'))
    with pytest.raises(ValueError):
        repository.save(make_receipt(version_id, key='op-2', sha=HASH_B))
    with pytest.raises(LookupError):
        repository.save(make_receipt(str(uuid.uuid4()), key='op-3'))
    assert count(conn, 'cp_upload_receipts') == 1 and repository.get('op-1') == make_receipt(version_id)
    assert PostgresStorageMetaRepository(conn, add_workspace(db[0])).get('op-1') is None
    with pytest.raises(ValueError):
        PostgresStorageMetaRepository(conn).get('op-1')


class FakeCloud:
    def __init__(self):
        self.timeout_on_upload = True
        self.uploaded = []
        self.observation = IntegrityObservation(True, HASH_A, 128, 'cloud-evidence-1')

    def reserve_object_id(self, namespace_ref):
        return 'obj-cloud-1'

    def upload(self, object_id, artifact_version_id, content_sha256, size_bytes):
        if self.timeout_on_upload:
            raise TimeoutError('upload timeout')
        self.uploaded.append(object_id)

    def lookup(self, object_id):
        return self.observation


def test_persist_to_cloud_outcome_unknown_then_reconcile_after_restart(conn, db):
    ws = db[1]
    version_id = seed_version(conn, ws)
    cloud = FakeCloud()
    result = PersistArtifactToCloud(cloud, PostgresStorageMetaRepository(conn, ws)).execute(version_id, HASH_A, 128, True, 'ns-i', 'op-cloud-1', 'grant-1')
    conn.commit()
    assert result.state is ArtifactLocationState.OUTCOME_UNKNOWN
    persisted = PostgresStorageMetaRepository(conn, ws).get('op-cloud-1')
    assert persisted is not None and persisted.state is UploadReceiptState.OUTCOME_UNKNOWN and persisted.object_id == 'obj-cloud-1'
    assert conn.execute('SELECT state, revision FROM controlplane.cp_upload_receipts WHERE operation_key = %s', ('op-cloud-1',)).fetchone() == ('OUTCOME_UNKNOWN', 2)
    cloud.timeout_on_upload = False
    with psycopg.connect(db[0]) as other:
        use_case = PersistArtifactToCloud(cloud, PostgresStorageMetaRepository(other, ws))
        reconciled = use_case.reconcile('op-cloud-1')
        other.commit()
        assert reconciled.state is ArtifactLocationState.VERIFIED and reconciled.verification_evidence_ref == 'cloud-evidence-1'
        replay = use_case.execute(version_id, HASH_A, 128, True, 'ns-i', 'op-cloud-1', 'grant-1')
        assert replay.state is ArtifactLocationState.VERIFIED and cloud.uploaded == []
    assert conn.execute('SELECT state FROM controlplane.cp_upload_receipts WHERE operation_key = %s', ('op-cloud-1',)).fetchone()[0] == 'VERIFIED'
    assert count(conn, 'cp_upload_receipts') == 1


def test_materialization_lease_round_trip_and_idempotent_per_operation(conn, db):
    ws = db[1]
    repository = PostgresStorageMetaRepository(conn, ws)
    expires = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)
    lease = repository.insert_lease('lease-1', 'op-m1', 'disk-1', 'staging/root-1', 4096, expires)
    conn.commit()
    assert lease is not None and (lease.lease_ref, lease.operation_key, lease.device_ref, lease.staging_root_ref, lease.expected_total_bytes, lease.state, lease.revision) == ('lease-1', 'op-m1', 'disk-1', 'staging/root-1', 4096, 'ACTIVE', 1)
    assert datetime.fromisoformat(lease.expires_at) == expires
    assert repository.insert_lease('lease-2', 'op-m1', 'disk-2', 'staging/root-2', 1, expires) == lease
    assert count(conn, 'cp_materialization_leases') == 1
    assert repository.get_lease('lease-1') == lease and repository.get_lease('missing') is None
    with pytest.raises(psycopg.errors.UniqueViolation):
        repository.insert_lease('lease-1', 'op-m2', 'disk-1', 'staging/root-1', 1, expires)
    conn.rollback()
    assert repository.settle_lease('lease-1', 5, 'RELEASED') is None
    with pytest.raises(ValueError):
        repository.settle_lease('lease-1', 1, 'ACTIVE')
    released = repository.settle_lease('lease-1', 1, 'RELEASED')
    conn.commit()
    assert released is not None and released.state == 'RELEASED' and released.revision == 2
    assert repository.settle_lease('lease-1', 2, 'EXPIRED') is None


def test_revision_placement_round_trip_and_idempotent(conn, db):
    ws = db[1]
    version_id = seed_version(conn, ws)
    repository = PostgresStorageMetaRepository(conn, ws)
    location = repository.insert_location(str(uuid.uuid4()), location_values(ws, version_id, 'obj-p1'))
    conn.commit()
    placement = repository.insert_revision_placement('pl-1', version_id, 'rev-1', 'cloud-cold', location.location_id)
    conn.commit()
    assert placement == RevisionPlacement('pl-1', version_id, 'rev-1', 'cloud-cold', location.location_id)
    assert repository.insert_revision_placement('pl-2', version_id, 'rev-1', 'local-hot') == placement
    assert count(conn, 'cp_revision_placements') == 1
    second = repository.insert_revision_placement('pl-3', version_id, 'rev-2', 'local-hot')
    conn.commit()
    assert second is not None and second.location_id is None
    assert repository.list_revision_placements(version_id) == [placement, second]
    assert repository.get_revision_placement('pl-1') == placement and repository.get_revision_placement('missing') is None
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        repository.insert_revision_placement('pl-9', str(uuid.uuid4()), 'rev-1', 'local-hot')
    conn.rollback()


def test_working_set_policy_round_trip_and_latest_revision(conn, db):
    ws = db[1]
    repository = PostgresStorageMetaRepository(conn, ws)
    assert repository.get_working_set_policy('policy-main') is None
    r1 = WorkingSetPolicy(10000, '1', 5)
    r2 = WorkingSetPolicy(20000, '2', 3)
    assert repository.insert_working_set_policy('policy-main', r1) is True
    assert repository.insert_working_set_policy('policy-main', r2) is True
    assert repository.insert_working_set_policy('policy-main', WorkingSetPolicy(1, '2', 1)) is False
    conn.commit()
    assert repository.get_working_set_policy('policy-main') == r2 and repository.get_working_set_policy('policy-main', '1') == r1
    assert repository.get_working_set_policy('policy-main', '9') is None
    with pytest.raises(ValueError):
        repository.insert_working_set_policy('policy-main', WorkingSetPolicy(1, 'rev-x', 1))
    conn.execute('INSERT INTO controlplane.cp_working_set_policies (workspace_id, policy_ref, policy_revision) VALUES (%s, %s, %s)', (ws, 'policy-nolimit', 1))
    conn.commit()
    with pytest.raises(ValueError):
        repository.get_working_set_policy('policy-nolimit')
    assert count(conn, 'cp_working_set_policies', 'policy_ref = %s', ('policy-main',)) == 2


def make_event(ws, version_id):
    return DomainEvent(contract_name='storage.artifact_version.declared', contract_version=1, message_id=str(uuid.uuid4()), workspace_id=ws, correlation_id='corr-1', causation_id=None, trace_context=None, occurred_at='2026-10-22T08:00:00Z', actor='persist-i-test', recovery_epoch=7, payload={'artifact_version_id': version_id}, event_id=str(uuid.uuid4()), event_name='ArtifactVersionDeclared', aggregate_type='artifact_version', aggregate_id=version_id, aggregate_revision=1, producer='persist-i-test', schema_version=1, sensitivity='internal')


def test_declare_and_outbox_roll_back_together(db):
    dsn, ws = db
    manager = TransactionManager(dsn, pool_max_size=2)
    observer = psycopg.connect(dsn, autocommit=True)
    try:
        def work(uow):
            result = DeclareArtifactVersionService(PostgresArtifactVersionCatalog(uow.connection, ws)).declare(declare_payload())
            PostgresOutboxRepository(uow.connection).enqueue(make_event(ws, result.artifact_version_id))

        with pytest.raises(RuntimeError, match='boom'):
            with manager.unit_of_work() as uow:
                work(uow)
                assert count(observer, 'cp_artifact_versions') == 0
                raise RuntimeError('boom')
        assert count(observer, 'cp_artifact_versions') == 0 and count(observer, 'cp_outbox_events') == 0
        with manager.unit_of_work() as uow:
            work(uow)
        assert count(observer, 'cp_artifact_versions') == 1 and count(observer, 'cp_outbox_events') == 1
    finally:
        manager.close()
        observer.close()


def test_adapter_source_has_no_ddl_cloud_adapter_or_transaction_control():
    files = list(STORAGE_META_DIR.rglob('*.py'))
    assert {f.name for f in files} >= {'__init__.py', 'catalog.py', 'records.py'}
    text = ' '.join(f.read_text(encoding='utf-8') for f in files)
    for banned in ('CREATE TABLE', 'ALTER TABLE', 'CREATE INDEX', 'CloudObjectPort', 'reserve_object_id', 'connect(', 'ConnectionPool', 'TransactionManager', '.commit(', '.rollback(', 'from src.', 'import src'):
        assert banned not in text, f'Found banned token: {banned}'
    assert not hasattr(PostgresStorageMetaRepository, 'reserve_object_id') and not hasattr(PostgresStorageMetaRepository, 'lookup')
