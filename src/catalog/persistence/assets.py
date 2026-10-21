'''PostgreSQL MediaAssetRepository over cp_media_assets and cp_media_provenance (migration 0014_catalog).'''

from typing import Any

from psycopg.types.json import Jsonb

from catalog.domain.identity import CanonicalFingerprint, MediaAsset
from catalog.persistence._db import fetch_all, fetch_one, run, search_terms, workspace_uuid
from catalog.persistence.mapping import (
    asset_from_rows,
    asset_payload,
    asset_search_text,
    asset_status,
    fingerprint_column,
    is_pending,
    provenance_id,
    provenance_to_json,
)

_COLUMNS = 'media_asset_id, fingerprint, revision, payload'
_DISCOVERY = '''(discovery_id = %s OR payload->'discovery_ids' @> to_jsonb(%s::text))'''
_FTS = '''string_to_array(search_text, ' ') @> %s::text[]'''
_LOCK = 'SELECT fingerprint, payload FROM controlplane.cp_media_assets WHERE workspace_id = %s AND media_asset_id = %s FOR UPDATE'
_HISTORY = '''SELECT payload FROM controlplane.cp_media_provenance WHERE workspace_id = %s AND media_asset_id = %s ORDER BY (payload->>'seq')::int'''
_UPSERT = (
    'INSERT INTO controlplane.cp_media_assets AS a '
    '(workspace_id, media_asset_id, fingerprint, discovery_id, status, revision, payload, search_text) '
    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s) '
    'ON CONFLICT (workspace_id, media_asset_id) DO UPDATE SET fingerprint = EXCLUDED.fingerprint, '
    'discovery_id = COALESCE(EXCLUDED.discovery_id, a.discovery_id), status = EXCLUDED.status, '
    'revision = EXCLUDED.revision, payload = EXCLUDED.payload, search_text = EXCLUDED.search_text, '
    'updated_at = CURRENT_TIMESTAMP'
)
_PROVENANCE = (
    'INSERT INTO controlplane.cp_media_provenance (workspace_id, provenance_id, media_asset_id, relation, payload) '
    'VALUES (%s, %s, %s, %s, %s) ON CONFLICT (workspace_id, provenance_id) DO NOTHING'
)


class PostgresMediaAssetRepository:
    '''Runs on the connection of the caller; commit and rollback stay with the caller's unit of work.'''

    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace = workspace_uuid(workspace_id)

    def get(self, media_asset_id: str) -> MediaAsset | None:
        return self._first('media_asset_id = %s', (media_asset_id,))

    def find_by_fingerprint(self, fingerprint: CanonicalFingerprint) -> MediaAsset | None:
        return self._first('fingerprint = %s', (fingerprint.value,))

    def find_by_discovery_id(self, discovery_id: str) -> MediaAsset | None:
        return self._first(_DISCOVERY, (discovery_id, discovery_id))

    def search(self, query: str, limit: int = 20) -> list[MediaAsset]:
        terms = search_terms(query)
        if not terms:
            return []
        return [self._load(row) for row in self._select(_FTS, (terms,), limit)]

    def _select(self, where: str, params: tuple, limit: int) -> list[tuple]:
        sql = f'SELECT {_COLUMNS} FROM controlplane.cp_media_assets WHERE workspace_id = %s AND {where} ORDER BY media_asset_id LIMIT %s'
        return fetch_all(self._connection, sql, (self._workspace, *params, limit))

    def _first(self, where: str, params: tuple) -> MediaAsset | None:
        rows = self._select(where, params, 1)
        return self._load(rows[0]) if rows else None

    def save(self, asset: MediaAsset, discovery_id: str | None = None) -> None:
        current = fetch_one(self._connection, _LOCK, (self._workspace, asset.media_asset_id))
        column = fingerprint_column(asset)
        if current is not None and not is_pending(current[0]) and current[0] != column:
            raise ValueError('fingerprint is already set and immutable')
        discovery_ids = [] if current is None else list(current[1].get('discovery_ids', []))
        if discovery_id is not None:
            owners = self._select(_DISCOVERY, (discovery_id, discovery_id), 1)
            if owners and owners[0][0] != asset.media_asset_id:
                raise ValueError('discovery_id already belongs to another media asset')
            if discovery_id not in discovery_ids:
                discovery_ids.append(discovery_id)
        payload = Jsonb(asset_payload(asset, discovery_ids))
        values = (self._workspace, asset.media_asset_id, column, discovery_id, asset_status(asset), asset.index_revision, payload, asset_search_text(asset))
        run(self._connection, _UPSERT, values)
        for position, entry in enumerate(asset.provenance):
            body = Jsonb({'seq': position, 'entry': provenance_to_json(entry)})
            row = (self._workspace, provenance_id(asset.media_asset_id, entry), asset.media_asset_id, entry.relation.value, body)
            run(self._connection, _PROVENANCE, row)

    def _load(self, row: tuple) -> MediaAsset:
        media_asset_id, fingerprint, revision, payload = row
        history = fetch_all(self._connection, _HISTORY, (self._workspace, media_asset_id))
        return asset_from_rows(media_asset_id, fingerprint, revision, payload, [item[0] for item in history])
