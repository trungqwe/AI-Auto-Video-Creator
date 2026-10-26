"""Selection store of D over PostgreSQL (PW-D2): CreativeAssetSelection rows in controlplane.cp_creative_selections.

Idempotent per job: equal content returns the stored revision, new content is the next revision, every row carries content_sha256 of its payload. The connection factory is injected.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from creative.domain.asset_selection import CreativeAssetSelection, FallbackCandidate, SceneAssignment
from creative.domain.ref_resolver import ResourceRef

SELECTION_ID_PREFIX = 'selection:'
_LATEST_FOR_JOB = (
    'SELECT selection_revision, content_sha256 FROM controlplane.cp_creative_selections '
    'WHERE workspace_id = %s AND job_id = %s ORDER BY selection_revision DESC LIMIT 1'
)
_INSERT = (
    'INSERT INTO controlplane.cp_creative_selections (workspace_id, selection_id, job_id, selection_revision, content_sha256, payload) '
    'VALUES (%s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (workspace_id, job_id, selection_revision) DO NOTHING'
)
_LATEST_BY_ID = (
    'SELECT payload, content_sha256 FROM controlplane.cp_creative_selections '
    'WHERE workspace_id = %s AND selection_id = %s ORDER BY selection_revision DESC LIMIT 1'
)


class SelectionIntegrityError(ValueError):
    """A stored row does not match its content_sha256 or selection_fingerprint, or a revision was taken by another writer."""

    code = 'SELECTION_INTEGRITY'


@dataclass(frozen=True)
class StoredSelection:
    selection_id: str
    job_id: str
    revision: int
    content_sha256: str
    selection: CreativeAssetSelection


def selection_id_of(selection: CreativeAssetSelection) -> str:
    return SELECTION_ID_PREFIX + selection.selection_fingerprint


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def content_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode('utf-8')).hexdigest()


def _ref(item: Mapping[str, str]) -> ResourceRef:
    return ResourceRef(item['workspace_id'], item['ref_type'], item['ref_id'], item['revision_id'])


def _intents(items: Any) -> tuple[Mapping[str, str], ...]:
    return tuple(MappingProxyType(dict(item)) for item in items)


def _decode(payload: Mapping[str, Any]) -> CreativeAssetSelection:
    selection = CreativeAssetSelection(
        snapshot_ref=payload['snapshot_ref'], script_ref=payload['script_ref'], angle_ref=payload['angle_ref'],
        safety_policy_revision=payload['safety_policy_revision'], music_sfx_policy_revision=payload['music_sfx_policy_revision'],
        preset_registry_revision=payload['preset_registry_revision'], visual_hook=_ref(payload['visual_hook']),
        audio_hook=_ref(payload['audio_hook']), thumbnail=_ref(payload['thumbnail']),
        thumbnail_overlay_intent=payload['thumbnail_overlay_intent'],
        assignments=tuple(SceneAssignment(**item) for item in payload['assignments']),
        music_intents=_intents(payload['music_intents']), sfx_intents=_intents(payload['sfx_intents']),
        fallback_candidates=tuple(FallbackCandidate(**item) for item in payload['fallback_candidates']),
        rationale=payload['rationale'],
        score_components=MappingProxyType({key: MappingProxyType(dict(value)) for key, value in payload['score_components'].items()}),
        selection_fingerprint=payload['selection_fingerprint'],
    )
    if selection.compute_fingerprint() != selection.selection_fingerprint:
        raise SelectionIntegrityError('selection_fingerprint_mismatch')
    return selection


class PostgresSelectionStore:
    """SelectionStorePort over PostgreSQL; `connect` returns a context-managed connection (commit on a clean exit, close on exit)."""

    def __init__(self, connect: Callable[[], Any]) -> None:
        if not callable(connect):
            raise TypeError('connect must be callable')
        self._connect = connect

    def save(self, *, workspace_id: str, job_id: str, selection: CreativeAssetSelection) -> StoredSelection:
        """Equal content to the latest revision of the job returns that revision; other content is stored as the next revision."""
        if not isinstance(selection, CreativeAssetSelection):
            raise TypeError('selection must be a CreativeAssetSelection')
        payload = selection.to_payload()
        digest = content_sha256(payload)
        selection_id = selection_id_of(selection)
        with self._connect() as connection:
            with connection.transaction():
                row = connection.execute(_LATEST_FOR_JOB, (workspace_id, job_id)).fetchone()
                if row is not None and row[1] == digest:
                    return StoredSelection(selection_id, job_id, int(row[0]), digest, selection)
                revision = 1 if row is None else int(row[0]) + 1
                inserted = connection.execute(_INSERT, (workspace_id, selection_id, job_id, revision, digest, _canonical(payload)))
                if inserted.rowcount != 1:
                    raise SelectionIntegrityError('selection_revision_taken')
        return StoredSelection(selection_id, job_id, revision, digest, selection)

    def load(self, *, workspace_id: str, selection_id: str) -> CreativeAssetSelection | None:
        """Latest stored revision of selection_id, verified against content_sha256 and selection_fingerprint; None when unknown."""
        with self._connect() as connection:
            row = connection.execute(_LATEST_BY_ID, (workspace_id, selection_id)).fetchone()
        if row is None:
            return None
        payload = row[0] if isinstance(row[0], Mapping) else json.loads(row[0])
        if content_sha256(payload) != row[1]:
            raise SelectionIntegrityError('content_sha256_mismatch')
        return _decode(payload)


__all__ = [
    'PostgresSelectionStore',
    'SELECTION_ID_PREFIX',
    'SelectionIntegrityError',
    'StoredSelection',
    'content_sha256',
    'selection_id_of',
]
