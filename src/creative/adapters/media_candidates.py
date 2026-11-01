"""Media candidates of SelectCreativeAssets read from the catalog of C (PW-D3, OI-ADAPT-10).

Assets come through an injected catalog scope, so this module holds no SQL and no connection. The candidate query of C (CT-MED-005) shapes every candidate; D only gathers the index entries: the twelve seed images and the images that came with the articles of the snapshot. An article image enters with its provenance (source URL, article, sha256, fetch time) and the flag needs_image_safety; it is rights_cleared by the user decision OI-ADAPT-10 (rights_basis OI-ADAPT-10) and AssessImageSafety still decides later; a seed image is rights_cleared only when its seed rights status is SELF_GENERATED; no candidate is cleared by default. An image with incomplete provenance, without a fingerprint or without a verified version is dropped, and a missing seed image is refused, so the list always holds a seed fallback. Every candidate carries the UUID of the verified version of its bytes, resolved through the injected resolve_version. The article_ref of a stored article image is the id of the collected document of the pinned revision, so an image is accepted when its article_ref is the article id or one of the document ids that resolve_documents(article_id, revision_id) returns for the pinned revision; the topic of an accepted image is its article id.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from typing import Any

from catalog.application.candidate_query import CandidateIndexEntry, query_media_candidates
from creative.domain.asset_selection import INPUT_NOT_READY, MediaCandidate, SelectionRejected, parse_media_candidate

SCENE_ROLE = 'scene_visual'
ORIGIN_SEED = 'seed'
ORIGIN_ARTICLE = 'article'
SEED_LOCATOR = re.compile(r'seed://bg-(0[1-9]|1[0-2])\.png')
SEED_SCAN_TERMS = 'seed png'
SEED_RIGHTS_STATUS = 'SELF_GENERATED'
ARTICLE_IMAGE_RIGHTS_STATUS = 'UNVERIFIED'
RIGHTS_BASIS_ARTICLE_IMAGE = 'OI-ADAPT-10'
RELATION_USER_IMPORTED = 'user_imported'
ARTICLE_RELATIONS = frozenset({'hero_image', 'inline_image'})
REF_TYPE_ARTICLE_REVISION = 'article_revision'
SCAN_LIMIT = 200
MAX_ARTICLE_IMAGES = 24


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ''


def _article_refs(snapshot: Any) -> tuple[tuple[str, str], ...]:
    """(article_id, revision_id) of every article_revision ref of the snapshot, in snapshot order and without repeats."""
    refs = ((_text(ref.get('ref_id')), _text(ref.get('revision_id'))) for ref in snapshot.source_refs if ref.get('ref_type') == REF_TYPE_ARTICLE_REVISION)
    return tuple(dict.fromkeys(item for item in refs if item[0]))


def _article_ids(snapshot: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(article_id for article_id, _ in _article_refs(snapshot)))


def _document_ids(value: object) -> tuple[str, ...]:
    """Collected document ids from resolve_documents: a tuple or list of strings, anything else is a TypeError (never a silent empty list)."""
    if not isinstance(value, (tuple, list)) or not all(isinstance(item, str) for item in value):
        raise TypeError('resolve_documents must return a tuple or list of strings')
    return tuple(dict.fromkeys(item.strip() for item in value if item.strip()))


def _provenance_of(asset: Any, origin: str, article_keys: Mapping[str, str]) -> Any | None:
    """First provenance entry that makes the asset usable as `origin`, else None; no fingerprint means no bytes to use."""
    if asset.kind.value != 'image' or asset.fingerprint is None:
        return None
    for entry in asset.provenance:
        if not (_text(entry.original_locator) and _text(entry.observed_at)):
            continue
        relation = entry.relation.value
        if origin == ORIGIN_SEED and relation == RELATION_USER_IMPORTED and SEED_LOCATOR.fullmatch(entry.original_locator):
            return entry
        if origin == ORIGIN_ARTICLE and relation in ARTICLE_RELATIONS and entry.article_ref in article_keys:
            return entry
    return None


def _usable(assets: Any, origin: str, article_keys: Mapping[str, str]) -> list[tuple[Any, Any]]:
    pairs = ((asset, _provenance_of(asset, origin, article_keys)) for asset in assets)
    return [(asset, entry) for asset, entry in pairs if entry is not None]


def _index_entry(asset: Any, entry: Any, origin: str, version_ref: str, article_id: str | None) -> CandidateIndexEntry:
    sha256 = asset.fingerprint.value
    article = origin == ORIGIN_ARTICLE
    safety = {'rights_status': asset.rights.status.value, 'needs_image_safety': article, 'origin': origin}
    if article:
        safety['article_image_rights_status'] = ARTICLE_IMAGE_RIGHTS_STATUS
        safety['rights_cleared'] = True
        safety['rights_basis'] = RIGHTS_BASIS_ARTICLE_IMAGE
    else:
        safety['seed_rights_status'] = SEED_RIGHTS_STATUS
        safety['rights_cleared'] = safety['seed_rights_status'] == SEED_RIGHTS_STATUS
    return CandidateIndexEntry(
        media_asset_id=asset.media_asset_id, rendition_ref=f'original:{asset.media_asset_id}',
        artifact_version_ref=version_ref, kind='image', roles=(SCENE_ROLE,), entities=(),
        topics=(article_id,) if article else (), scenes=(),
        provenance={
            'origin': origin, 'source_url': entry.original_locator, 'source_ref': entry.source_ref,
            'article_ref': entry.article_ref, 'sha256': sha256, 'fetched_at': entry.observed_at, 'relation': entry.relation.value},
        technical_fitness={'probed': False}, availability='AVAILABLE', safety_rights_status=safety, usage_refs=())


class PostgresMediaCandidates:
    """Media candidate port of SelectCreativeAssets over the media tables of C.

    `open_assets(workspace_id)` returns a context manager that yields the asset repository of the catalog (a reader with `search(query, limit)`) on a connection of the caller; the composition root wires the PostgreSQL repository of C there. `resolve_version(sha256)` returns the UUID of the verified version of the image bytes or None. `resolve_documents(article_id, revision_id)` returns the collected document ids of exactly that pinned revision as a tuple or list (empty when the revision is unknown); it has no default and runs before open_assets. `safety_policy_revision` is the caller's revision and has no default.
    """

    def __init__(
        self,
        open_assets: Callable[[str], AbstractContextManager[Any]],
        *,
        resolve_version: Callable[[str], str | None],
        resolve_documents: Callable[[str, str], Sequence[str]],
        safety_policy_revision: str,
    ) -> None:
        if not callable(open_assets):
            raise TypeError('open_assets must be callable')
        if not callable(resolve_version):
            raise TypeError('resolve_version must be callable')
        if not callable(resolve_documents):
            raise TypeError('resolve_documents must be callable')
        if not isinstance(safety_policy_revision, str) or not safety_policy_revision:
            raise ValueError('safety_policy_revision must be a non-empty string')
        self._open_assets = open_assets
        self._resolve_version = resolve_version
        self._resolve_documents = resolve_documents
        self._safety_policy_revision = safety_policy_revision

    def _article_keys(self, snapshot: Any) -> dict[str, str]:
        """Accepted article_ref value -> article_id: the article id itself and every collected document id of the pinned revision."""
        keys: dict[str, str] = {}
        for article_id, revision_id in _article_refs(snapshot):
            keys.setdefault(article_id, article_id)
            for document_id in _document_ids(self._resolve_documents(article_id, revision_id)):
                keys.setdefault(document_id, article_id)
        return keys

    def _entries(self, pairs: list[tuple[Any, Any]], origin: str, keys: Mapping[str, str]) -> list[CandidateIndexEntry]:
        """Index entries of the images whose bytes have a verified version; an image without one is dropped like an image without a fingerprint."""
        entries = []
        for asset, entry in pairs:
            version_ref = self._resolve_version(asset.fingerprint.value)
            if isinstance(version_ref, str) and version_ref:
                entries.append(_index_entry(asset, entry, origin, version_ref, keys.get(entry.article_ref)))
        return entries

    def media_candidates(self, *, workspace_id: str, snapshot: Any) -> tuple[MediaCandidate, ...]:
        """Article images of the snapshot first, then the seed images; SelectionRejected(INPUT_NOT_READY, seed_media_missing) when no seed image is usable."""
        keys = self._article_keys(snapshot)
        with self._open_assets(workspace_id) as assets:
            seeds = _usable(assets.search(SEED_SCAN_TERMS, SCAN_LIMIT), ORIGIN_SEED, keys)
            articles: dict[str, tuple[Any, Any]] = {}
            for key in keys:
                for asset, entry in _usable(assets.search(key, SCAN_LIMIT), ORIGIN_ARTICLE, keys):
                    articles.setdefault(asset.media_asset_id, (asset, entry))
        entries = self._entries(list(articles.values()), ORIGIN_ARTICLE, keys)[:MAX_ARTICLE_IMAGES]
        entries += self._entries(seeds, ORIGIN_SEED, keys)
        query = {
            'production_snapshot_ref': snapshot.snapshot_id, 'scene_intent': {'topics': list(_article_ids(snapshot))},
            'media_kinds': ['image'], 'roles': [SCENE_ROLE], 'safety_policy_revision': self._safety_policy_revision,
            'limit': max(1, len(entries))}
        found, _ = query_media_candidates(query, entries)
        candidates = tuple(parse_media_candidate(item) for item in found)
        if not any(item.provenance.get('origin') == ORIGIN_SEED for item in candidates):
            raise SelectionRejected(INPUT_NOT_READY, 'seed_media_missing', 'media_candidates')
        return candidates
