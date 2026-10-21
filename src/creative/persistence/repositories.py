"""PostgreSQL repositories of D over the 0015_creative tables; they run on the connection of their unit of work and never open one."""
from __future__ import annotations

import json
import uuid
from types import MappingProxyType
from typing import Any

from controlplane.domain.concurrency import RevisionConflictError
from creative.domain.snapshot import ProductionSnapshot
from creative.persistence.codec import decode_record, encode_record
from creative.ports import repositories as ports

RECORD_TABLES = MappingProxyType({
    ports.KIND_ANALYSIS: 'controlplane.cp_content_analyses',
    ports.KIND_ANGLE_SET: 'controlplane.cp_story_angle_sets',
    ports.KIND_SCRIPT: 'controlplane.cp_script_versions',
    ports.KIND_PLAN: 'controlplane.cp_production_plans',
    ports.KIND_VARIANT_VALIDATION: 'controlplane.cp_variant_validations',
    ports.KIND_OUTPUT_METADATA: 'controlplane.cp_output_metadata',
    ports.KIND_INVOCATION: 'controlplane.cp_ai_invocation_records',
})


def _json(value: Any) -> str:
    return json.dumps(encode_record(value), ensure_ascii=False, allow_nan=False)


def same_workspace(own: str, other: Any) -> bool:
    try:
        return str(uuid.UUID(other)) == own
    except (AttributeError, TypeError, ValueError):
        return False


def insert_all(connection: Any, statements: list[tuple[str, tuple]]) -> Exception | None:
    """Run INSERTs in one savepoint; return a unique violation (all undone), raise other errors."""
    connection.execute('SAVEPOINT creative_insert')
    try:
        for statement, params in statements:
            connection.execute(statement, params)
    except Exception as error:
        if getattr(error, 'sqlstate', None) != '23505':
            raise
        connection.execute('ROLLBACK TO SAVEPOINT creative_insert')
        connection.execute('RELEASE SAVEPOINT creative_insert')
        return error
    connection.execute('RELEASE SAVEPOINT creative_insert')
    return None


def violated_constraint(error: Exception) -> str:
    return getattr(getattr(error, 'diag', None), 'constraint_name', None) or ''


class _Repository:
    def __init__(self, connection_source: Any, workspace_id: str) -> None:
        self._connection = connection_source
        self._workspace_id = workspace_id


class PostgresSnapshotRepository(_Repository):
    def add(self, snapshot: ProductionSnapshot) -> None:
        if not isinstance(snapshot, ProductionSnapshot):
            raise TypeError('snapshot must be a ProductionSnapshot')
        error = insert_all(self._connection(), [(
            'INSERT INTO controlplane.cp_production_snapshots (snapshot_id, workspace_id, source_set_fingerprint, configuration_bundle_fingerprint, payload) VALUES (%s, %s::uuid, %s, %s, %s::jsonb)',
            (snapshot.snapshot_id, self._workspace_id, snapshot.source_set_fingerprint, snapshot.configuration_bundle_fingerprint, _json(snapshot)),
        )])
        if error is not None:
            raise ports.DuplicateSnapshotError(snapshot.snapshot_id) from error

    def get(self, snapshot_id: str) -> ProductionSnapshot | None:
        row = self._connection().execute(
            'SELECT payload FROM controlplane.cp_production_snapshots WHERE workspace_id = %s::uuid AND snapshot_id = %s',
            (self._workspace_id, snapshot_id),
        ).fetchone()
        return None if row is None else decode_record(ProductionSnapshot, row[0])

    def list_snapshots(self) -> tuple[ProductionSnapshot, ...]:
        found = self._connection().execute(
            'SELECT payload FROM controlplane.cp_production_snapshots WHERE workspace_id = %s::uuid ORDER BY created_at, snapshot_id',
            (self._workspace_id,),
        ).fetchall()
        return tuple(decode_record(ProductionSnapshot, row[0]) for row in found)


class PostgresAppendOnlyRepository(_Repository):
    def __init__(self, connection_source, workspace_id, kind):
        if kind not in RECORD_TABLES:
            raise ValueError(f'unknown kind: {kind}')
        super().__init__(connection_source, workspace_id)
        self.kind = kind
        self._table = RECORD_TABLES[kind]

    def _latest_revision(self, connection: Any, key: str) -> int:
        return connection.execute(
            f'SELECT COALESCE(MAX(revision), 0) FROM {self._table} WHERE workspace_id = %s::uuid AND record_key = %s',
            (self._workspace_id, key),
        ).fetchone()[0]

    def append(self, key: str, revision: int, record: object):
        connection = self._connection()
        if not isinstance(key, str) or not key.strip():
            raise ValueError('key must be a non-empty string')
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError('revision must be a positive integer')
        if not isinstance(record, ports.RECORD_TYPES[self.kind]):
            raise TypeError(f'record must be a {ports.RECORD_TYPES[self.kind].__name__}')
        if self.kind == ports.KIND_ANALYSIS and (key != record.analysis_id or revision != record.revision):
            raise ValueError('key and revision must match record identity')
        if self.kind == ports.KIND_OUTPUT_METADATA and (key != record.source_job_ref or revision != record.metadata_revision):
            raise ValueError('key and revision must match record identity')
        latest = self._latest_revision(connection, key)
        if revision != latest + 1:
            raise RevisionConflictError(latest)
        attr = ports.UNIQUE_ID_ATTRS.get(self.kind)
        columns = 'workspace_id, record_key, revision, payload'
        marks = '%s::uuid, %s, %s, %s::jsonb'
        values = [self._workspace_id, key, revision, _json(record)]
        if attr is not None:
            columns, marks = columns + ', ' + attr, marks + ', %s'
            values.append(getattr(record, attr))
        statements = [(f'INSERT INTO {self._table} ({columns}) VALUES ({marks})', tuple(values))]
        if self.kind == ports.KIND_ANGLE_SET:
            statements += [(
                'INSERT INTO controlplane.cp_story_angles (workspace_id, angle_id, set_id, payload) VALUES (%s::uuid, %s, %s, %s::jsonb)',
                (self._workspace_id, f'{record.set_id}:{angle.angle_id}', record.set_id, _json(angle)),
            ) for angle in record.angles]
        error = insert_all(connection, statements)
        if error is not None:
            if violated_constraint(error) == self._table.split('.')[1] + '_pkey':
                raise RevisionConflictError(self._latest_revision(connection, key)) from error
            if attr is None:
                raise error
            raise ports.DuplicateRecordError(f'{attr} already stored: {getattr(record, attr)}') from error
        return ports.StoredRecord(self.kind, key, revision, record)

    def _stored(self, key, row):
        return ports.StoredRecord(self.kind, key, row[0], decode_record(ports.RECORD_TYPES[self.kind], row[1]))

    def latest(self, key: str):
        row = self._connection().execute(
            f'SELECT revision, payload FROM {self._table} WHERE workspace_id = %s::uuid AND record_key = %s ORDER BY revision DESC LIMIT 1',
            (self._workspace_id, key),
        ).fetchone()
        return None if row is None else self._stored(key, row)

    def revisions(self, key: str):
        found = self._connection().execute(
            f'SELECT revision, payload FROM {self._table} WHERE workspace_id = %s::uuid AND record_key = %s ORDER BY revision ASC',
            (self._workspace_id, key),
        ).fetchall()
        return tuple(self._stored(key, row) for row in found)


class PostgresAnalysisRepository(PostgresAppendOnlyRepository):
    def __init__(self, connection_source: Any, workspace_id: str) -> None:
        super().__init__(connection_source, workspace_id, ports.KIND_ANALYSIS)


class PostgresAngleSetRepository(PostgresAppendOnlyRepository):
    def __init__(self, connection_source: Any, workspace_id: str) -> None:
        super().__init__(connection_source, workspace_id, ports.KIND_ANGLE_SET)


class PostgresScriptRepository(PostgresAppendOnlyRepository):
    def __init__(self, connection_source: Any, workspace_id: str) -> None:
        super().__init__(connection_source, workspace_id, ports.KIND_SCRIPT)


class PostgresPlanRepository(PostgresAppendOnlyRepository):
    def __init__(self, connection_source: Any, workspace_id: str) -> None:
        super().__init__(connection_source, workspace_id, ports.KIND_PLAN)


class PostgresVariantValidationRepository(PostgresAppendOnlyRepository):
    def __init__(self, connection_source: Any, workspace_id: str) -> None:
        super().__init__(connection_source, workspace_id, ports.KIND_VARIANT_VALIDATION)


class PostgresOutputMetadataRepository(PostgresAppendOnlyRepository):
    def __init__(self, connection_source: Any, workspace_id: str) -> None:
        super().__init__(connection_source, workspace_id, ports.KIND_OUTPUT_METADATA)


class PostgresInvocationRecordRepository(PostgresAppendOnlyRepository):
    def __init__(self, connection_source: Any, workspace_id: str) -> None:
        super().__init__(connection_source, workspace_id, ports.KIND_INVOCATION)


class PostgresReceiptStore(_Repository):
    def get(self, workspace_id: str, idempotency_key: str) -> ports.CommandReceipt | None:
        if not same_workspace(self._workspace_id, workspace_id):
            raise ValueError('workspace_id must be the workspace of the unit of work')
        row = self._connection().execute(
            'SELECT request_hash, aggregate_ref, aggregate_revision FROM controlplane.cp_creative_receipts WHERE workspace_id = %s::uuid AND idempotency_key = %s',
            (self._workspace_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        return ports.CommandReceipt(workspace_id=workspace_id, idempotency_key=idempotency_key, request_hash=row[0], aggregate_ref=row[1], aggregate_revision=row[2])

    def put(self, receipt: ports.CommandReceipt) -> None:
        if not isinstance(receipt, ports.CommandReceipt):
            raise TypeError('receipt must be a CommandReceipt')
        if not same_workspace(self._workspace_id, receipt.workspace_id):
            raise ValueError('workspace_id must be the workspace of the unit of work')
        error = insert_all(self._connection(), [(
            'INSERT INTO controlplane.cp_creative_receipts (workspace_id, idempotency_key, request_hash, aggregate_ref, aggregate_revision) VALUES (%s::uuid, %s, %s, %s, %s)',
            (self._workspace_id, receipt.idempotency_key, receipt.request_hash, receipt.aggregate_ref, receipt.aggregate_revision),
        )])
        if error is not None:
            raise ports.DuplicateReceiptError(receipt.idempotency_key) from error


__all__ = [
    'PostgresAnalysisRepository',
    'PostgresAngleSetRepository',
    'PostgresAppendOnlyRepository',
    'PostgresInvocationRecordRepository',
    'PostgresOutputMetadataRepository',
    'PostgresPlanRepository',
    'PostgresReceiptStore',
    'PostgresScriptRepository',
    'PostgresSnapshotRepository',
    'PostgresVariantValidationRepository',
]