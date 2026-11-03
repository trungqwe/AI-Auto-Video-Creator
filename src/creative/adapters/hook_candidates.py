"""Visual and audio hook candidates of SelectCreativeAssets read from the hook library of C (PW-D3, CT-MED-006).

Hooks come through an injected catalog scope, so this module holds no SQL and no connection. Each enabled hook revision becomes an index entry that the candidate query of C turns into component scores and evidence; D keeps the C order and makes no ranking here. A kind without any enabled hook is refused instead of returning an empty list. A hook is rights_cleared when its seed_rights_status metadata is SELF_GENERATED or when its hook_license metadata is a license that allows commercial use in a video (Pixabay Content License, CC0, CC BY 3.0/4.0; CC BY also needs hook_author and hook_attribution).

PW-D3-FIX4 (FR-HOOK-004, FR-HOOK-005, FR-HOOK-008): every candidate carries provenance.index (tags, description, source, license, author, attribution) so that the AI chooses the hook by content. With exclude_placeholders (the production launcher), a hook generated from a recipe of hooks.json (metadata recipe_template, the gradient and sweep placeholders vh-01..05, ah-01..05) is never a candidate; when only placeholders are enabled the kind is refused with reason only_placeholder_<kind>_candidates, so the job is marked as missing an eligible hook instead of rendering a placeholder.
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
PLACEHOLDER_METADATA_KEY = 'recipe_template'
CLEARED_HOOK_LICENSES = frozenset({'Pixabay Content License', 'CC0-1.0', 'CC-BY-3.0', 'CC-BY-4.0'})
ATTRIBUTION_HOOK_LICENSES = frozenset({'CC-BY-3.0', 'CC-BY-4.0'})
INDEX_METADATA_KEYS = (('source', 'hook_source'), ('license', 'hook_license'), ('author', 'hook_author'), ('attribution', 'hook_attribution'), ('page_url', 'hook_page_url'))


def _technical(metadata: Sequence[Sequence[str]]) -> dict[str, int]:
    values = dict(metadata)
    return {key: int(values[key]) for key in TECHNICAL_KEYS if str(values.get(key, '')).isdigit()}


def _reference(revision: Any) -> str:
    return f'hook:{revision.hook_id}:r{revision.revision}'


def is_placeholder(revision: Any) -> bool:
    """A hook generated from a recipe of hooks.json (seed placeholder), not real footage or a recorded sound."""
    return PLACEHOLDER_METADATA_KEY in dict(revision.technical_metadata)


def _rights(metadata: dict[str, str], revision: Any) -> dict[str, object]:
    if metadata.get('seed_rights_status') == SEED_RIGHTS_STATUS:
        return {'rights_status': SEED_RIGHTS_STATUS, 'rights_cleared': True}
    license_code = metadata.get('hook_license')
    if license_code in CLEARED_HOOK_LICENSES:
        cleared = license_code not in ATTRIBUTION_HOOK_LICENSES or bool(metadata.get('hook_author', '').strip() and metadata.get('hook_attribution', '').strip())
        return {'rights_status': license_code, 'rights_cleared': cleared}
    return {'rights_status': metadata.get('seed_rights_status') or license_code or revision.provenance.value, 'rights_cleared': False}


def _index(revision: Any, metadata: dict[str, str]) -> dict[str, object]:
    index: dict[str, object] = {'tags': list(revision.tags), 'description': revision.description}
    for name, key in INDEX_METADATA_KEYS:
        if metadata.get(key):
            index[name] = metadata[key]
    return index


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
            'sha256': metadata.get('media_sha256'), 'technical': technical, 'index': _index(revision, metadata),
            'placeholder': is_placeholder(revision)},
        technical_fitness=dict(technical), availability='AVAILABLE',
        safety_rights_status=_rights(metadata, revision), usage_refs=())


class PostgresHookCandidates:
    """Hook candidate port of SelectCreativeAssets over the hook tables of C.

    `open_hooks(workspace_id)` returns a context manager that yields the hook history of the catalog (a reader with `list_heads()`) on a connection of the caller. `safety_policy_revision` is the caller's revision and has no default. `exclude_placeholders` drops the recipe placeholders (the production launcher sets it).
    """

    def __init__(self, open_hooks: Callable[[str], AbstractContextManager[Any]], *, safety_policy_revision: str, exclude_placeholders: bool = False) -> None:
        if not callable(open_hooks):
            raise TypeError('open_hooks must be callable')
        if not isinstance(safety_policy_revision, str) or not safety_policy_revision:
            raise ValueError('safety_policy_revision must be a non-empty string')
        if not isinstance(exclude_placeholders, bool):
            raise TypeError('exclude_placeholders must be a bool')
        self._open_hooks = open_hooks
        self._safety_policy_revision = safety_policy_revision
        self._exclude_placeholders = exclude_placeholders

    def visual_hook_candidates(self, *, workspace_id: str, snapshot_ref: str, topics: Sequence[str] = ()) -> tuple[HookCandidate, ...]:
        return self._candidates(workspace_id, snapshot_ref, topics, REF_TYPE_VISUAL_HOOK)

    def audio_hook_candidates(self, *, workspace_id: str, snapshot_ref: str, topics: Sequence[str] = ()) -> tuple[HookCandidate, ...]:
        return self._candidates(workspace_id, snapshot_ref, topics, REF_TYPE_AUDIO_HOOK)

    def _candidates(self, workspace_id: str, snapshot_ref: str, topics: Sequence[str], hook_kind: str) -> tuple[HookCandidate, ...]:
        with self._open_hooks(workspace_id) as hooks:
            heads = hooks.list_heads()
        enabled = {
            _reference(head.revision): head.revision for head in heads
            if head.revision.enabled and head.revision.kind.value == hook_kind}
        revisions = {ref: revision for ref, revision in enabled.items() if not (self._exclude_placeholders and is_placeholder(revision))}
        entries = [_index_entry(revision, hook_kind) for revision in revisions.values()]
        if not entries:
            reason = f'only_placeholder_{hook_kind}_candidates' if enabled else f'no_{hook_kind}_candidates'
            raise SelectionRejected(INPUT_NOT_READY, reason, hook_kind)
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
