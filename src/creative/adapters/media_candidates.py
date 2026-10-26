"""Media candidates of SelectCreativeAssets read from the catalog of C (PW-D3, OI-ADAPT-10).

Assets come through an injected catalog scope, so this module holds no SQL and no connection. The candidate query of C (CT-MED-005) shapes every candidate; D only gathers the index entries: the twelve seed images and the images that came with the articles of the snapshot. An article image enters with its provenance (source URL, article, sha256, fetch time) and the flag needs_image_safety; its rights are never a filter here (OI-ADAPT-10), AssessImageSafety decides later. An image with incomplete provenance or without a fingerprint is dropped, and a missing seed image is refused, so the list always holds a seed fallback.
"""
from __future__ import annotations

import re
from collections.abc import Callable
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
RELATION_USER_IMPORTED = 'user_imported'
ARTICLE_RELATIONS = frozenset({'hero_image', 'inline_image'})
REF_TYPE_ARTICLE_REVISION = 'article_revision'
SCAN_LIMIT = 200
MAX_ARTICLE_IMAGES = 24


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ''


def _article_ids(snapshot: Any) -> tuple[str, ...]:
    ids = (_text(ref.get('ref_id')) for ref in snapshot.source_refs if ref.get('ref_type') == REF_TYPE_ARTICLE_REVISION)
    return tuple(dict.fromkeys(item for item in ids if item))


def _provenance_of(asset: Any, origin: str, article_ids: tuple[str, ...]) -> Any | None:
    """First provenance entry that makes the asset usable as `origin`, else None; no fingerprint means no bytes to use."""
    if asset.kind.value != 'image' or asset.fingerprint is None:
        return None
    for entry in asset.provenance:
        if not (_text(entry.original_locator) and _text(entry.observed_at)):
            continue
        relation = entry.relation.value
        if origin == ORIGIN_SEED and relation == RELATION_USER_IMPORTED and SEED_LOCATOR.fullmatch(entry.original_locator):
            return entry
        if origin == ORIGIN_ARTICLE and relation in ARTICLE_RELATIONS and entry.article_ref in article_ids:
            return entry
    return None


def _usable(assets: Any, origin: str, article_ids: tuple[str, ...]) -> list[tuple[Any, Any]]:
    pairs = ((asset, _provenance_of(asset, origin, article_ids)) for asset in assets)
    return [(asset, entry) for asset, entry in pairs if entry is not None]


def _index_entry(asset: Any, entry: Any, origin: str) -> CandidateIndexEntry:
    sha256 = asset.fingerprint.value
    article = origin == ORIGIN_ARTICLE
    safety = {'rights_status': asset.rights.status.value, 'needs_image_safety': article, 'origin': origin}
    if article:
        safety['article_image_rights_status'] = ARTICLE_IMAGE_RIGHTS_STATUS
    else:
        safety['seed_rights_status'] = SEED_RIGHTS_STATUS
    return CandidateIndexEntry(
        media_asset_id=asset.media_asset_id, rendition_ref=f'original:{asset.media_asset_id}',
        artifact_version_ref=f'sha256:{sha256}', kind='image', roles=(SCENE_ROLE,), entities=(),
        topics=(entry.article_ref,) if article else (), scenes=(),
        provenance={
            'origin': origin, 'source_url': entry.original_locator, 'source_ref': entry.source_ref,
            'article_ref': entry.article_ref, 'sha256': sha256, 'fetched_at': entry.observed_at, 'relation': entry.relation.value},
        technical_fitness={'probed': False}, availability='AVAILABLE', safety_rights_status=safety, usage_refs=())


class PostgresMediaCandidates:
    """Media candidate port of SelectCreativeAssets over the media tables of C.

    `open_assets(workspace_id)` returns a context manager that yields the asset repository of the catalog (a reader with `search(query, limit)`) on a connection of the caller; the composition root wires the PostgreSQL repository of C there. `safety_policy_revision` is the caller's revision and has no default.
    """

    def __init__(self, open_assets: Callable[[str], AbstractContextManager[Any]], *, safety_policy_revision: str) -> None:
        if not callable(open_assets):
            raise TypeError('open_assets must be callable')
        if not isinstance(safety_policy_revision, str) or not safety_policy_revision:
            raise ValueError('safety_policy_revision must be a non-empty string')
        self._open_assets = open_assets
        self._safety_policy_revision = safety_policy_revision

    def media_candidates(self, *, workspace_id: str, snapshot: Any) -> tuple[MediaCandidate, ...]:
        """Article images of the snapshot first, then the seed images; SelectionRejected(INPUT_NOT_READY, seed_media_missing) when no seed image is usable."""
        article_ids = _article_ids(snapshot)
        with self._open_assets(workspace_id) as assets:
            seeds = _usable(assets.search(SEED_SCAN_TERMS, SCAN_LIMIT), ORIGIN_SEED, article_ids)
            articles: dict[str, tuple[Any, Any]] = {}
            for article_id in article_ids:
                for asset, entry in _usable(assets.search(article_id, SCAN_LIMIT), ORIGIN_ARTICLE, article_ids):
                    articles.setdefault(asset.media_asset_id, (asset, entry))
        entries = [_index_entry(asset, entry, ORIGIN_ARTICLE) for asset, entry in list(articles.values())[:MAX_ARTICLE_IMAGES]]
        entries += [_index_entry(asset, entry, ORIGIN_SEED) for asset, entry in seeds]
        query = {
            'production_snapshot_ref': snapshot.snapshot_id, 'scene_intent': {'topics': list(article_ids)},
            'media_kinds': ['image'], 'roles': [SCENE_ROLE], 'safety_policy_revision': self._safety_policy_revision,
            'limit': max(1, len(entries))}
        found, _ = query_media_candidates(query, entries)
        candidates = tuple(parse_media_candidate(item) for item in found)
        if not any(item.provenance.get('origin') == ORIGIN_SEED for item in candidates):
            raise SelectionRejected(INPUT_NOT_READY, 'seed_media_missing', 'media_candidates')
        return candidates
