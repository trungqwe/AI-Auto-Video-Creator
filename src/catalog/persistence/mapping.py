'''Mapping between MediaAsset and the 0014_catalog columns.'''

import hashlib
import json

from catalog.domain.identity import (
    CanonicalFingerprint,
    MediaAsset,
    MediaKind,
    ProvenanceEntry,
    ProvenanceRelation,
    RightsAssessment,
    RightsStatus,
)
from catalog.domain.states import DiscoveryState
from catalog.persistence._db import build_search_text

PENDING_PREFIX = 'pending:'


def fingerprint_column(asset: MediaAsset) -> str:
    '''cp_media_assets.fingerprint is NOT NULL, so an asset still waiting for acquisition keeps a per-asset placeholder.'''
    if asset.fingerprint is None:
        return PENDING_PREFIX + asset.media_asset_id
    return asset.fingerprint.value


def is_pending(column_value: str) -> bool:
    return column_value.startswith(PENDING_PREFIX)


def asset_status(asset: MediaAsset) -> str:
    return (DiscoveryState.DISCOVERED if asset.fingerprint is None else DiscoveryState.CATALOGED).value


def asset_payload(asset: MediaAsset, discovery_ids: list[str]) -> dict:
    return {
        'kind': asset.kind.value,
        'rights': {'status': asset.rights.status.value, 'evidence_refs': list(asset.rights.evidence_refs)},
        'discovery_ids': discovery_ids,
    }


def asset_search_text(asset: MediaAsset) -> str:
    parts = [asset.kind.value, asset.rights.status.value]
    for entry in asset.provenance:
        refs = (entry.source_ref, entry.article_ref, entry.event_ref, entry.original_locator, entry.relation.value)
        parts.extend(ref for ref in refs if ref)
    return build_search_text(*parts)


def provenance_to_json(entry: ProvenanceEntry) -> dict:
    return {
        'source_ref': entry.source_ref,
        'article_ref': entry.article_ref,
        'event_ref': entry.event_ref,
        'original_locator': entry.original_locator,
        'observed_at': entry.observed_at,
        'relation': entry.relation.value,
    }


def provenance_from_json(data: dict) -> ProvenanceEntry:
    return ProvenanceEntry(
        source_ref=data['source_ref'],
        article_ref=data['article_ref'],
        event_ref=data['event_ref'],
        original_locator=data['original_locator'],
        observed_at=data['observed_at'],
        relation=ProvenanceRelation(data['relation']),
    )


def provenance_id(media_asset_id: str, entry: ProvenanceEntry) -> str:
    blob = json.dumps([media_asset_id, provenance_to_json(entry)], sort_keys=True)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def asset_from_rows(media_asset_id: str, fingerprint: str, revision: int, payload: dict, provenance_payloads: list[dict]) -> MediaAsset:
    rights = payload['rights']
    return MediaAsset(
        media_asset_id=media_asset_id,
        kind=MediaKind(payload['kind']),
        fingerprint=None if is_pending(fingerprint) else CanonicalFingerprint(fingerprint),
        provenance=tuple(provenance_from_json(item['entry']) for item in provenance_payloads),
        rights=RightsAssessment(RightsStatus(rights['status']), tuple(rights['evidence_refs'])),
        index_revision=revision,
    )
