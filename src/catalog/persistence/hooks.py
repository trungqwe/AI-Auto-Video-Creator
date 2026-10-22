'''PostgreSQL hook history over cp_hooks and cp_hook_revisions; a drop-in for catalog.application.hooks.HookHistory.'''

from typing import Any

from psycopg.types.json import Jsonb

from catalog.domain.hooks import HookHead, HookKind, HookRevision, format_hook_timestamp
from catalog.domain.identity import ProvenanceRelation
from catalog.persistence._db import build_search_text, fetch_all, fetch_one, run, search_terms, workspace_uuid
from controlplane.domain.concurrency import RevisionConflictError

_REVISION = 'SELECT r.hook_id, r.revision, r.artifact_version_ref, r.payload FROM controlplane.cp_hook_revisions r '
_HEAD = 'SELECT current_revision, kind FROM controlplane.cp_hooks WHERE workspace_id = %s AND hook_id = %s FOR UPDATE'
_FTS = '''SELECT hook_id FROM controlplane.cp_hooks WHERE workspace_id = %s AND string_to_array(search_text, ' ') @> %s::text[] AND (is_enabled OR NOT %s::boolean) ORDER BY hook_id'''
_HEAD_ROWS = (
    'SELECT r.hook_id, r.revision, r.artifact_version_ref, r.payload, h.updated_at FROM controlplane.cp_hooks h '
    'JOIN controlplane.cp_hook_revisions r ON r.workspace_id = h.workspace_id AND r.hook_id = h.hook_id AND r.revision = h.current_revision '
    'WHERE h.workspace_id = %s'
)
_INSERT_HOOK = (
    'INSERT INTO controlplane.cp_hooks (workspace_id, hook_id, kind, current_revision, is_enabled, search_text) '
    'VALUES (%s, %s, %s, %s, %s, %s)'
)
_UPDATE_HOOK = (
    'UPDATE controlplane.cp_hooks SET current_revision = %s, is_enabled = %s, search_text = %s, '
    'updated_at = CURRENT_TIMESTAMP WHERE workspace_id = %s AND hook_id = %s'
)
_INSERT_REVISION = (
    'INSERT INTO controlplane.cp_hook_revisions (workspace_id, hook_id, revision, artifact_version_ref, payload) '
    'VALUES (%s, %s, %s, %s, %s)'
)


def _payload(hook: HookRevision) -> dict:
    return {
        'kind': hook.kind.value,
        'tags': list(hook.tags),
        'description': hook.description,
        'note': hook.note,
        'enabled': hook.enabled,
        'technical_metadata': [list(pair) for pair in hook.technical_metadata],
        'provenance': hook.provenance.value,
    }


def _hook(row: tuple) -> HookRevision:
    hook_id, revision, artifact_version_ref, payload = row
    return HookRevision(
        hook_id=hook_id,
        revision=revision,
        kind=HookKind(payload['kind']),
        artifact_version_ref=artifact_version_ref,
        tags=tuple(payload['tags']),
        description=payload['description'],
        note=payload['note'],
        enabled=payload['enabled'],
        technical_metadata=tuple((key, value) for key, value in payload['technical_metadata']),
        provenance=ProvenanceRelation(payload['provenance']),
    )


def _head(row: tuple) -> HookHead:
    return HookHead(revision=_hook(row[:4]), updated_at=format_hook_timestamp(row[4]))


class PostgresHookHistory:
    '''Runs on the connection of the caller; a stored revision is never replaced.'''

    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace = workspace_uuid(workspace_id)

    def get(self, hook_id: str, revision: int) -> HookRevision:
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise KeyError((hook_id, revision))
        sql = _REVISION + 'WHERE r.workspace_id = %s AND r.hook_id = %s AND r.revision = %s'
        row = fetch_one(self._connection, sql, (self._workspace, hook_id, revision))
        if row is None:
            raise KeyError((hook_id, revision))
        return _hook(row)

    def latest(self, hook_id: str) -> HookRevision:
        sql = _REVISION + 'JOIN controlplane.cp_hooks h ON h.workspace_id = r.workspace_id AND h.hook_id = r.hook_id AND h.current_revision = r.revision WHERE h.workspace_id = %s AND h.hook_id = %s'
        row = fetch_one(self._connection, sql, (self._workspace, hook_id))
        if row is None:
            raise KeyError(hook_id)
        return _hook(row)

    def head(self, hook_id: str) -> HookHead:
        row = fetch_one(self._connection, _HEAD_ROWS + ' AND h.hook_id = %s', (self._workspace, hook_id))
        if row is None:
            raise KeyError(hook_id)
        return _head(row)

    def list_heads(self) -> list[HookHead]:
        rows = fetch_all(self._connection, _HEAD_ROWS + ' ORDER BY h.hook_id', (self._workspace,))
        return [_head(row) for row in rows]

    def append(self, revision: HookRevision) -> None:
        head = fetch_one(self._connection, _HEAD, (self._workspace, revision.hook_id))
        current = 0 if head is None else head[0]
        if revision.revision != current + 1:
            raise RevisionConflictError(current)
        if head is not None and head[1] != revision.kind.value:
            raise ValueError('hook kind never changes between revisions')
        text = build_search_text(revision.kind.value, *revision.tags, revision.description, revision.note)
        if head is None:
            run(self._connection, _INSERT_HOOK, (self._workspace, revision.hook_id, revision.kind.value, revision.revision, revision.enabled, text))
        else:
            run(self._connection, _UPDATE_HOOK, (revision.revision, revision.enabled, text, self._workspace, revision.hook_id))
        run(self._connection, _INSERT_REVISION, (self._workspace, revision.hook_id, revision.revision, revision.artifact_version_ref, Jsonb(_payload(revision))))

    def search(self, query: str, enabled_only: bool = True) -> list[HookRevision]:
        terms = search_terms(query)
        if not terms:
            return []
        rows = fetch_all(self._connection, _FTS, (self._workspace, terms, enabled_only))
        return [self.latest(row[0]) for row in rows]
