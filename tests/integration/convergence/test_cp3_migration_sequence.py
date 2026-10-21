'''CP-3-MIGRATIONS: kiểm chuỗi migration 0009..0018 (tĩnh và trên PostgreSQL 18.6 dùng một lần).'''
from __future__ import annotations

import datetime
import os
import re
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Jsonb

from controlplane.infrastructure.db.migration_runner import MigrationRunner

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_REL = 'src/controlplane/infrastructure/db/migrations'
MIGRATIONS_DIR = REPO_ROOT / MIGRATIONS_REL
RUNNER_REL = 'src/controlplane/infrastructure/db/migration_runner.py'
BASE_SHA = '2d8a9686da7c7261d67a406c153a912d3f4de36d'
NAMES = {9: '0009_config_security_extensions', 10: '0010_storage_meta_extensions', 11: '0011_orchestration_extensions', 12: '0012_source_ingestion', 13: '0013_ingestion', 14: '0014_catalog', 15: '0015_creative', 16: '0016_voice', 17: '0017_render', 18: '0018_control_ui_indexes'}
PATTERN = ('record_key', 'revision', 'payload')
RECEIPT = ('idempotency_key', 'request_hash', 'aggregate_ref', 'aggregate_revision')
EXPECTED: dict[int, dict[str, tuple[str, ...]]] = {}
ADDED: dict[int, dict[str, tuple[str, ...]]] = {}
EXPECTED[9] = {
    'cp_external_accounts': ('external_account_id', 'provider', 'account_label', 'status', 'capabilities_json', 'credential_version', 'credential_updated_at', 'credential_expires_at', 'quota_observation_ref', 'health', 'revision'),
    'cp_provider_capacity_snapshots': ('snapshot_id', 'domain_key', 'remaining_requests', 'retry_after_at', 'observed_at', 'confidence_flag'),
    'cp_capacity_reservations': ('reservation_ref', 'domain_key', 'units', 'expires_at', 'operation_key', 'confidence_flag'),
    'cp_cost_records': ('record_id', 'provider', 'service', 'operation_ref', 'quantity', 'unit', 'estimated_cost', 'actual_cost', 'currency', 'source', 'occurred_at', 'cost_category'),
    'cp_audit_records': ('audit_id', 'actor_ref', 'action', 'resource_ref', 'revision_before', 'revision_after', 'occurred_at', 'correlation_id', 'outcome', 'redacted_reason'),
}
ADDED[9] = {'cp_secret_handles': ('credential_version', 'revocation_version'), 'cp_config_revisions': ('scope_kind',)}
EXPECTED[10] = {
    'cp_upload_receipts': ('operation_key', 'artifact_version_id', 'source_location_id', 'target_backend_ref', 'provider_object_ref', 'state', 'verification_evidence_ref', 'revision'),
    'cp_materialization_leases': ('lease_ref', 'operation_key', 'device_ref', 'staging_root_ref', 'expected_total_bytes', 'state', 'expires_at'),
    'cp_revision_placements': ('placement_id', 'artifact_version_id', 'revision_ref', 'storage_class', 'location_id'),
    'cp_working_set_policies': ('policy_ref', 'policy_revision', 'max_videos_per_render', 'max_working_set_bytes'),
}
ADDED[10] = {
    'cp_artifact_versions': ('intended_storage_class', 'producer_operation_ref', 'lineage_refs'),
    'cp_artifact_locations': ('device_ref', 'logical_category', 'last_verified_at', 'lease_ref', 'retention_state', 'cleanup_state'),
    'cp_cleanup_authorizations': ('recovery_epoch',),
}
EXPECTED[11] = {
    'cp_execution_grants': ('grant_id', 'stage_run_id', 'execution_generation', 'recovery_epoch', 'worker_lease_id', 'issued_at', 'expires_at', 'allowed_operation', 'input_fingerprint', 'revoked_at'),
    'cp_orchestration_receipts': RECEIPT,
    'cp_cleanup_eligibility': ('cleanup_eligibility_id', 'video_job_id', 'artifact_version_id', 'cleanup_policy_ref', 'eligible_at', 'status'),
    'cp_app_sessions': ('session_ref', 'status', 'recovery_epoch', 'started_at', 'ended_at'),
}
ADDED[11] = {
    'cp_stage_runs': ('recovery_epoch', 'stage_type', 'input_refs', 'dependency_refs', 'wait_reason', 'problem', 'started_at', 'finished_at', 'updated_at', 'superseded_by'),
    'cp_video_jobs': ('wait_reason', 'parent_variant_ref', 'prior_variant_ref'),
    'cp_completion_ledger': ('completion_id', 'session_ref', 'cloud_location_ref', 'cloud_location_verification_ref', 'snapshot_ref', 'script_version_ref', 'production_plan_ref', 'preset_revision_ref', 'quality_report_ref', 'variant_validation_ref', 'media_usage_manifest', 'output_naming_metadata', 'cost_usage_summary', 'cleanup_policy_ref'),
    'cp_production_batches': ('stop_reason', 'stopped_at'),
}
EXPECTED[12] = {
    'cp_sources': ('source_id', 'canonical_locator', 'status', 'revision', 'payload'),
    'cp_source_identities': ('canonical_locator', 'source_id', 'is_tombstone', 'tombstoned_at'),
    'cp_source_candidates': ('candidate_id', 'canonical_locator', 'status', 'revision', 'payload'),
    'cp_collection_runs': ('run_id', 'source_id', 'run_kind', 'business_date', 'status', 'revision', 'payload'),
    'cp_collection_attempts': ('attempt_id', 'run_id', 'attempt_index', 'status', 'started_at', 'finished_at', 'payload'),
    'cp_collection_checkpoints': ('checkpoint_id', 'source_id', 'sequence_no', 'payload'),
    'cp_fetch_observations': ('observation_id', 'run_id', 'source_id', 'canonical_locator', 'observation_fingerprint', 'observed_at', 'payload'),
    'cp_collected_document_packages': ('source_id', 'canonical_locator', 'observation_fingerprint', 'collection_run_id', 'payload'),
    'cp_source_command_receipts': RECEIPT,
}
EXPECTED[13] = {
    'cp_articles': ('article_id', 'identity_key', 'exact_fingerprint', 'revision', 'payload'),
    'cp_article_revisions': ('article_id', 'revision', 'payload'),
    'cp_collected_document_resolutions': ('collected_document_id', 'dedup_policy_revision', 'payload'),
    'cp_dedup_evidence': ('evidence_id', 'collected_document_id', 'dedup_policy_revision', 'payload'),
    'cp_events': ('event_id', 'revision', 'payload'),
    'cp_event_link_candidates': ('record_id', 'payload'),
    'cp_event_updates': ('record_id', 'event_id', 'payload'),
    'cp_event_update_candidates': ('record_id', 'payload'),
}
EXPECTED[14] = {
    'cp_media_assets': ('media_asset_id', 'fingerprint', 'discovery_id', 'status', 'revision', 'payload', 'search_text'),
    'cp_media_provenance': ('provenance_id', 'media_asset_id', 'relation', 'payload'),
    'cp_media_renditions': ('rendition_ref', 'media_asset_id', 'kind', 'artifact_version_ref', 'source_artifact_version_ref', 'transformation_spec_revision', 'processor_version', 'lineage_refs'),
    'cp_hooks': ('hook_id', 'kind', 'current_revision', 'is_enabled', 'search_text'),
    'cp_hook_revisions': ('hook_id', 'revision', 'artifact_version_ref', 'payload'),
    'cp_media_usage': ('usage_id', 'completion_id', 'video_job_id', 'media_asset_id', 'role', 'usage_kind', 'rendition_ref', 'artifact_version_ref', 'selection_rationale'),
}
EXPECTED[15] = {
    'cp_production_snapshots': ('snapshot_id', 'source_set_fingerprint', 'configuration_bundle_fingerprint', 'payload'),
    'cp_content_analyses': PATTERN,
    'cp_story_angle_sets': PATTERN + ('set_id',),
    'cp_story_angles': ('angle_id', 'set_id', 'payload'),
    'cp_script_versions': PATTERN + ('script_version_id',),
    'cp_production_plans': PATTERN + ('production_plan_id',),
    'cp_variant_validations': PATTERN,
    'cp_output_metadata': PATTERN,
    'cp_ai_invocation_records': PATTERN,
    'cp_creative_receipts': RECEIPT,
}
EXPECTED[16] = {
    'cp_processed_media': PATTERN,
    'cp_image_safety_assessments': PATTERN,
    'cp_voice_tracks': PATTERN + ('voice_hash',),
    'cp_word_timings': PATTERN + ('timing_artifact_ref',),
    'cp_timing_validation_reports': PATTERN,
    'cp_tts_invocation_records': PATTERN,
    'cp_language_evidence': PATTERN,
    'cp_audio_bed_results': PATTERN,
    'cp_probe_reports': PATTERN,
    'cp_analysis_results': PATTERN,
    'cp_voice_receipts': RECEIPT,
}
EXPECTED[17] = {
    'cp_render_preset_revisions': PATTERN,
    'cp_render_packages': PATTERN + ('package_fingerprint',),
    'cp_package_validation_reports': PATTERN,
    'cp_render_attempts': PATTERN + ('render_attempt_id',),
    'cp_quality_reports': PATTERN,
    'cp_quality_gate_results': PATTERN,
    'cp_video_outputs': ('output_artifact_ref', 'render_attempt_id', 'payload'),
    'cp_render_operation_receipts': RECEIPT,
}
# --- EXPECTED_BLOCKS ---
APPEND_ONLY_EXPLICIT = {
    9: ('cp_audit_records',),
    12: ('cp_collection_checkpoints', 'cp_fetch_observations', 'cp_collected_document_packages', 'cp_source_command_receipts'),
    13: ('cp_article_revisions', 'cp_dedup_evidence', 'cp_event_updates'),
    14: ('cp_media_provenance', 'cp_media_renditions', 'cp_hook_revisions', 'cp_media_usage'),
}
SAMPLE_OVERRIDES = {'cp_audit_records': {'outcome': 'succeeded'}, 'cp_media_usage': {'usage_kind': 'production'}}


def append_only_tables(number):
    return APPEND_ONLY_EXPLICIT.get(number, tuple(EXPECTED[number]))


def sql_of(number, rollback=False):
    suffix = '.rollback.sql' if rollback else '.sql'
    return (MIGRATIONS_DIR / (NAMES[number] + suffix)).read_text(encoding='utf-8')


def strip(text):
    lines = [line.split('--')[0] for line in text.splitlines()]
    return ' '.join(' '.join(lines).split())


def word(name):
    return '(?<![a-z0-9_])' + name + '(?![a-z0-9_])'


def git(*args):
    proc = subprocess.run(['git', *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.split()


def test_sequence_and_pairs():
    forward = [p.name for p in MIGRATIONS_DIR.iterdir() if re.fullmatch('[0-9]{4}_[a-z0-9_]+[.]sql', p.name)]
    assert sorted(int(name[:4]) for name in forward) == list(range(1, 19))
    for number, stem in NAMES.items():
        found = sorted(p.name for p in MIGRATIONS_DIR.glob(f'{number:04d}_*.sql'))
        assert found == sorted([f'{stem}.sql', f'{stem}.rollback.sql']), (number, found)
    assert len(list(MIGRATIONS_DIR.glob('*.rollback.sql'))) == 18


def test_expected_tables_and_columns_in_sql():
    assert sorted(EXPECTED) == list(range(9, 18))
    for number, tables in EXPECTED.items():
        sql = strip(sql_of(number))
        for table, columns in tables.items():
            assert re.search('CREATE TABLE controlplane[.]' + table + ' ?[(]', sql), (number, table)
            for column in columns:
                assert re.search(word(column), sql), (number, table, column)
    for number, tables in ADDED.items():
        sql = strip(sql_of(number))
        for table, columns in tables.items():
            assert re.search('ALTER TABLE controlplane[.]' + table + ' ', sql), (number, table)
            for column in columns:
                assert re.search(word(column), sql), (number, table, column)


def test_rollback_drops_only_own_objects():
    for number in NAMES:
        created = set(re.findall('CREATE TABLE controlplane[.]([a-z0-9_]+)', sql_of(number)))
        rollback = strip(sql_of(number, rollback=True))
        dropped = set(re.findall('DROP TABLE IF EXISTS controlplane[.]([a-z0-9_]+)', rollback))
        assert created == dropped, (number, created ^ dropped)
        assert 'CASCADE' not in rollback.upper() and 'DROP SCHEMA' not in rollback.upper(), number


def test_forbidden_constructs_absent():
    for number in NAMES:
        for rollback in (False, True):
            text = ' ' + strip(sql_of(number, rollback)).upper()
            for banned in ('CONCURRENTLY', 'CREATE EXTENSION', 'VECTOR', ' BEGIN;', ' COMMIT;'):
                assert banned not in text, (number, rollback, banned)


def test_0018_only_keyset_indexes():
    sql = strip(sql_of(18))
    wanted = {
        'cp_production_batches': '(workspace_id, created_at DESC, batch_id DESC)',
        'cp_video_jobs': '(workspace_id, created_at DESC, job_id DESC)',
        'cp_command_receipts': '(workspace_id, accepted_at DESC, receipt_id DESC)',
    }
    for table, columns in wanted.items():
        assert re.search('CREATE INDEX [a-z0-9_]+ ON controlplane[.]' + table + ' ' + re.escape(columns), sql), table
    assert len(re.findall('CREATE (?:UNIQUE )?INDEX', sql)) == 3
    assert 'CREATE TABLE' not in sql.upper() and 'ALTER TABLE' not in sql.upper()


def test_append_only_tables_have_reject_trigger():
    for number in (9, 12, 13, 14, 15, 16, 17):
        sql = strip(sql_of(number))
        for table in append_only_tables(number):
            pattern = 'CREATE TRIGGER [a-z0-9_]+ BEFORE UPDATE OR DELETE ON controlplane[.]' + table + ' FOR EACH ROW EXECUTE FUNCTION controlplane[.][a-z0-9_]+[(][)]'
            assert re.search(pattern, sql), (number, table)


def test_pinned_migrations_and_runner_untouched():
    changed = git('diff', '--name-only', BASE_SHA, '--', 'src')
    untracked = git('ls-files', '--others', '--exclude-standard', '--', 'src')
    assert not [name for name in changed if re.search('/migrations/000[1-8]_', name)], changed
    assert RUNNER_REL not in changed
    allowed = '/migrations/(0009|001[0-8])_[a-z0-9_]+([.]rollback)?[.]sql$'
    outside = [name for name in changed + untracked if not re.search(allowed, name)]
    assert outside == [], outside


try:
    _p = subprocess.check_output(['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'], text=True, stderr=subprocess.DEVNULL).strip().split(':')[-1]
    _DEFAULT_DSN = f'postgresql://m2test:m2test@127.0.0.1:{_p}/postgres'
except Exception:
    _DEFAULT_DSN = 'postgresql://m2test:m2test@127.0.0.1:57027/postgres'
PG_DSN = os.environ.get('M2_TEST_PG_DSN', _DEFAULT_DSN)


def insert_sample(connection, table, workspace_id, **overrides):
    values = {**SAMPLE_OVERRIDES.get(table, {}), **overrides}
    rows = connection.execute(
        'SELECT column_name, data_type FROM information_schema.columns '
        'WHERE table_schema = %s AND table_name = %s AND is_nullable = %s AND column_default IS NULL '
        'ORDER BY ordinal_position',
        ('controlplane', table, 'NO'),
    ).fetchall()
    for name, data_type in rows:
        if name in values:
            continue
        if name == 'workspace_id':
            values[name] = workspace_id
        elif data_type == 'uuid':
            values[name] = uuid.uuid4()
        elif data_type in ('bigint', 'integer', 'numeric'):
            values[name] = 1
        elif data_type == 'boolean':
            values[name] = False
        elif data_type == 'jsonb':
            values[name] = Jsonb({})
        elif data_type == 'date':
            values[name] = datetime.date(2026, 1, 1)
        elif data_type.startswith('timestamp'):
            values[name] = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        else:
            values[name] = 'x'
    names = ', '.join(values)
    marks = ', '.join(['%s'] * len(values))
    connection.execute(f'INSERT INTO controlplane.{table} ({names}) VALUES ({marks})', list(values.values()))


def column_types(connection):
    rows = connection.execute(
        'SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = %s',
        ('controlplane',),
    ).fetchall()
    return {(table, column): data_type for table, column, data_type in rows}


def assert_versions(dsn, count):
    with psycopg.connect(dsn) as connection:
        rows = connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()
    assert [row[0] for row in rows] == list(range(1, count + 1))


def assert_schema(dsn):
    workspace_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as connection:
        columns = column_types(connection)
        for blocks in (EXPECTED, ADDED):
            for number, tables in blocks.items():
                for table, names in tables.items():
                    for name in names:
                        assert (table, name) in columns, (number, table, name)
        for table in ('cp_cleanup_authorizations', 'cp_stage_runs', 'cp_app_sessions'):
            assert columns[(table, 'recovery_epoch')] == 'text', table
        assert columns[('cp_outbox_events', 'recovery_epoch')] == 'bigint'
        vector = connection.execute('SELECT count(*) FROM pg_extension WHERE extname = %s', ('vector',)).fetchone()[0]
        assert vector == 0
        assert not [c for (t, c) in columns if t == 'cp_collection_runs' and 'policy' in c]
        defs = [row[0] for row in connection.execute('SELECT indexdef FROM pg_indexes WHERE schemaname = %s', ('controlplane',)).fetchall()]
        keysets = (
            ('cp_production_batches', '(workspace_id, created_at DESC, batch_id DESC)'),
            ('cp_video_jobs', '(workspace_id, created_at DESC, job_id DESC)'),
            ('cp_command_receipts', '(workspace_id, accepted_at DESC, receipt_id DESC)'),
        )
        for table, cols in keysets:
            assert any(f'ON controlplane.{table} USING btree {cols}' in d for d in defs), table
        connection.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (workspace_id, 'w', 'ACTIVE'))
        for number in (9, 12, 13, 14, 15, 16, 17):
            for table in append_only_tables(number):
                insert_sample(connection, table, workspace_id)
                for statement in (f'UPDATE controlplane.{table} SET workspace_id = workspace_id', f'DELETE FROM controlplane.{table}'):
                    with pytest.raises(psycopg.errors.RaiseException):
                        connection.execute(statement)
                count = connection.execute(f'SELECT count(*) FROM controlplane.{table}').fetchone()[0]
                assert count == 1, table
        day = datetime.date(2026, 1, 1)
        insert_sample(connection, 'cp_collection_runs', workspace_id, run_id='r1', run_kind='PERIODIC', business_date=day)
        with pytest.raises(psycopg.errors.UniqueViolation):
            insert_sample(connection, 'cp_collection_runs', workspace_id, run_id='r2', run_kind='PERIODIC', business_date=day)
        insert_sample(connection, 'cp_collection_runs', workspace_id, run_id='r3', run_kind='MANUAL', business_date=day)
        insert_sample(connection, 'cp_voice_tracks', workspace_id, record_key='k1', voice_hash='h')
        with pytest.raises(psycopg.errors.UniqueViolation):
            insert_sample(connection, 'cp_voice_tracks', workspace_id, record_key='k2', voice_hash='h')


def test_postgres_up_down_up_and_constraints():
    name = f'm2_p1_test_{uuid.uuid4().hex[:8]}'
    admin = psycopg.connect(PG_DSN, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        dsn = PG_DSN.rsplit('/', 1)[0] + f'/{name}'
        runner = MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name)
        runner.migrate_up()
        assert_versions(dsn, 18)
        assert_schema(dsn)
        runner.migrate_down()
        with psycopg.connect(dsn) as connection:
            assert connection.execute('SELECT to_regclass(%s)', ('controlplane.cp_schema_migrations',)).fetchone()[0] is None
        runner.migrate_up()
        assert_versions(dsn, 18)
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
        admin.close()
