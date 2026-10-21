'''PostgreSQL store of immutable renditions over cp_media_renditions (migration 0014_catalog).'''

import re
from typing import Any

from psycopg.types.json import Jsonb

from catalog.domain.renditions import Rendition, RenditionKind, RenditionSet
from catalog.persistence._db import fetch_all, fetch_one, run, workspace_uuid

_SPEC_REVISION = re.compile('0|[1-9][0-9]*')
_SELECT = (
    'SELECT rendition_ref, media_asset_id, kind, artifact_version_ref, source_artifact_version_ref, '
    'transformation_spec_revision, processor_version, lineage_refs FROM controlplane.cp_media_renditions '
    'WHERE workspace_id = %s AND '
)
_INSERT = (
    'INSERT INTO controlplane.cp_media_renditions (workspace_id, rendition_ref, media_asset_id, kind, '
    'artifact_version_ref, source_artifact_version_ref, transformation_spec_revision, processor_version, '
    'lineage_refs, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, clock_timestamp())'
)


def _rendition(row: tuple) -> Rendition:
    ref, asset_id, kind, version_ref, source_ref, spec_revision, processor, lineage = row
    return Rendition(
        rendition_ref=ref,
        media_asset_id=asset_id,
        kind=RenditionKind(kind),
        artifact_version_ref=version_ref,
        source_artifact_version_ref=source_ref,
        transformation_spec_revision=str(spec_revision),
        processor_version=processor,
        lineage=tuple(lineage),
    )


class PostgresRenditionStore:
    '''Runs on the connection of the caller; a stored rendition is never updated or deleted.'''

    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace = workspace_uuid(workspace_id)

    def get(self, rendition_ref: str) -> Rendition | None:
        row = fetch_one(self._connection, _SELECT + 'rendition_ref = %s', (self._workspace, rendition_ref))
        return None if row is None else _rendition(row)

    def list_for_asset(self, media_asset_id: str) -> RenditionSet:
        sql = _SELECT + 'media_asset_id = %s ORDER BY created_at, rendition_ref'
        rows = fetch_all(self._connection, sql, (self._workspace, media_asset_id))
        return RenditionSet(media_asset_id, tuple(_rendition(row) for row in rows))

    def add(self, rendition: Rendition) -> None:
        if not _SPEC_REVISION.fullmatch(rendition.transformation_spec_revision):
            raise ValueError('transformation_spec_revision must be a canonical decimal string for cp_media_renditions')
        existing = self.get(rendition.rendition_ref)
        if existing is not None:
            if existing != rendition:
                raise ValueError('rendition_ref already stores another rendition; renditions are immutable')
            return
        values = (
            self._workspace,
            rendition.rendition_ref,
            rendition.media_asset_id,
            rendition.kind.value,
            rendition.artifact_version_ref,
            rendition.source_artifact_version_ref,
            int(rendition.transformation_spec_revision),
            rendition.processor_version,
            Jsonb(list(rendition.lineage)),
        )
        run(self._connection, _INSERT, values)
