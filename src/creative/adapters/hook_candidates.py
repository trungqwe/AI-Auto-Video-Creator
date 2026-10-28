"""Visual and audio hook candidates of SelectCreativeAssets read from the hook library of C (PW-D3, CT-MED-006).

Hooks come through an injected catalog scope, so this module holds no SQL and no connection. Each enabled hook revision becomes an index entry that the candidate query of C turns into component scores and evidence; D keeps the C order and makes no ranking here. A kind without any enabled hook is refused instead of returning an empty list. A hook is rights_cleared only when its seed_rights_status metadata is SELF_GENERATED.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from typing import Any

from catalog.application.candidate_query import CandidateIndexEntry, query_media_candidates
from creative.domain.asset_selection import (
    INPUT_NOT_READY, REF_TYPE_AUDIO_HOOK, REF_TYPE_VISUAL_HOOK, HookCandidate, SelectionRejected)

MEDIA_KIND_BY_HOOK_KIND = {REF_TYPE_VISUAL_HOOK: 'clip', REF_TYPE_AUDIO_HOOK: 'audio'}
TECHNICAL_KEYS = ('width', 'height', 'fps', 'duration_ms', 'sample_rate_hz', 'channels')
SEED_RIGHTS_STATUS = 'SELF_GENERATED'


def _technical(metadata: Sequence[Sequence[str]]) -> dict[str, int]:
    values = dict(metadata)
    return {key: int(values[key]) for key in TECHNICAL_KEYS if str(values.get(key, '')).isdigit()}


def _reference(revision: Any) -> str:
    return f'hook:{revision.hook_id}:r{revision.revision}'


def _index_entry(revision: Any, hook_kind: str) -> CandidateIndexEntry:
    metadata = dict(revision.technical_metadata)
    technical = _technical(revision.technical_metadata)
    return CandidateIndexEntry(
        media_asset_id=metadata.get('media_asset_id') or revision.hook_id, rendition_ref=_reference(revision),
        artifact_version_ref=revision.artifact_version_ref, kind=MEDIA_KIND_BY_HOOK_KIND[hook_kind], roles=(hook_kind,),
        entities=(), topics=tuple(revision.tags), scenes=(),
        provenance={
            'origin': 'hook_library', 'relation': revision.provenance.value, 'hook_id': revision.hook_id,
            'hook_revision': revision.revision, 'artifact_version_ref': revision.artifact_version_ref,
            'sha256': metadata.get('media_sha256'), 'technical': technical},
        technical_fitness=dict(technical), availability='AVAILABLE',
        safety_rights_status={'rights_status': metadata.get('seed_rights_status', revision.provenance.value), 'rights_cleared': metadata.get('seed_rights_status') == SEED_RIGHTS_STATUS}, usage_refs=())


class PostgresHookCandidates:
    """Hook candidate port of SelectCreativeAssets over the hook tables of C.

    `open_hooks(workspace_id)` returns a context manager that yields the hook history of the catalog (a reader with `list_heads()`) on a connection of the caller. `safety_policy_revision` is the caller's revision and has no default.
    """

    def __init__(self, open_hooks: Callable[[str], AbstractContextManager[Any]], *, safety_policy_revision: str) -> None:
        if not callable(open_hooks):
            raise TypeError('open_hooks must be callable')
        if not isinstance(safety_policy_revision, str) or not safety_policy_revision:
            raise ValueError('safety_policy_revision must be a non-empty string')
        self._open_hooks = open_hooks
        self._safety_policy_revision = safety_policy_revision

    def visual_hook_candidates(self, *, workspace_id: str, snapshot_ref: str, topics: Sequence[str] = ()) -> tuple[HookCandidate, ...]:
        return self._candidates(workspace_id, snapshot_ref, topics, REF_TYPE_VISUAL_HOOK)

    def audio_hook_candidates(self, *, workspace_id: str, snapshot_ref: str, topics: Sequence[str] = ()) -> tuple[HookCandidate, ...]:
        return self._candidates(workspace_id, snapshot_ref, topics, REF_TYPE_AUDIO_HOOK)

    def _candidates(self, workspace_id: str, snapshot_ref: str, topics: Sequence[str], hook_kind: str) -> tuple[HookCandidate, ...]:
        with self._open_hooks(workspace_id) as hooks:
            heads = hooks.list_heads()
        revisions = {
            _reference(head.revision): head.revision for head in heads
            if head.revision.enabled and head.revision.kind.value == hook_kind}
        entries = [_index_entry(revision, hook_kind) for revision in revisions.values()]
        if not entries:
            raise SelectionRejected(INPUT_NOT_READY, f'no_{hook_kind}_candidates', hook_kind)
        query = {
            'production_snapshot_ref': snapshot_ref, 'scene_intent': {'topics': list(topics)},
            'media_kinds': [MEDIA_KIND_BY_HOOK_KIND[hook_kind]], 'roles': [hook_kind],
            'safety_policy_revision': self._safety_policy_revision, 'limit': len(entries)}
        found, _ = query_media_candidates(query, entries)
        candidates = []
        for item in found:
            revision = revisions[item['rendition_ref']]
            candidates.append(HookCandidate(
                hook_kind=hook_kind, hook_id=revision.hook_id, revision_id=f'{revision.hook_id}-r{revision.revision}',
                availability=item['availability'], safety_rights_status=item['safety_rights_status'],
                semantic_match_components=item['semantic_match_components'],
                provenance={**item['provenance'], 'technical_fitness': item['technical_fitness'], 'reason_codes': item['reason_codes']}))
        return tuple(candidates)
