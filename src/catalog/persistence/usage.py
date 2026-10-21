'''PostgreSQL MediaUsageRepository over cp_media_usage; rows are staged on the connection of the caller's completion transaction (migration 0014_catalog).'''

import uuid
from collections.abc import Callable
from typing import Any

from catalog.persistence._db import fetch_one, run, workspace_uuid
from catalog.ports.usage import MediaUsageRecord, UsageKind

_EXISTS = 'SELECT 1 FROM controlplane.cp_media_usage WHERE workspace_id = %s AND completion_id = %s AND media_asset_id = %s AND role = %s AND usage_kind = %s'
_INSERT = (
    'INSERT INTO controlplane.cp_media_usage (workspace_id, usage_id, completion_id, video_job_id, media_asset_id, role, '
    'usage_kind, rendition_ref, artifact_version_ref, selection_rationale) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) '
    'ON CONFLICT (workspace_id, completion_id, media_asset_id, role, usage_kind) DO NOTHING'
)
_COUNT = 'SELECT count(*) FROM controlplane.cp_media_usage WHERE workspace_id = %s AND media_asset_id = %s AND usage_kind = %s'


class PostgresMediaUsageRepository:
    '''Runs on the connection of the caller; commit and rollback stay with the completion unit of work.'''

    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace = workspace_uuid(workspace_id)

    def exists(self, completion_id: str, media_asset_id: str, role: str, usage_kind: UsageKind) -> bool:
        params = (self._workspace, completion_id, media_asset_id, role, UsageKind(usage_kind).value)
        return fetch_one(self._connection, _EXISTS, params) is not None

    def add(self, record: MediaUsageRecord) -> None:
        values = (
            self._workspace,
            uuid.uuid4().hex,
            record.completion_id,
            record.video_job_id,
            record.media_asset_id,
            record.role,
            record.usage_kind.value,
            record.rendition_ref,
            record.artifact_version_ref,
            record.selection_rationale,
        )
        run(self._connection, _INSERT, values)

    def count_production(self, media_asset_id: str) -> int:
        row = fetch_one(self._connection, _COUNT, (self._workspace, media_asset_id, UsageKind.production.value))
        return row[0]


def media_usage_repository_factory(workspace_id: str) -> Callable[[Any], PostgresMediaUsageRepository]:
    '''Factory for MediaUsageRecorder: borrows uow.connection of the completion unit of work.'''

    def factory(uow: Any) -> PostgresMediaUsageRepository:
        return PostgresMediaUsageRepository(uow.connection, workspace_id)

    return factory
