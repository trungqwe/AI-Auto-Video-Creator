"""Production PlanAssetPort and ArtifactInfoPort over the controlplane tables of D and I, plus the script segment reader (PW-F3, CT-AI-004)."""
from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from render.ports.inputs import ResolvedAsset

_PLAN_SQL = (
    'SELECT payload FROM controlplane.cp_production_plans '
    'WHERE workspace_id = %s::uuid AND production_plan_id = %s '
    'ORDER BY revision DESC LIMIT 1'
)

_ASSET_SQL = (
    'SELECT v.artifact_version_id::text, v.sha256_hash, v.size_bytes, v.mime_type, v.artifact_kind '
    'FROM controlplane.cp_artifact_versions v '
    'WHERE v.workspace_id = %s::uuid AND v.artifact_version_id = %s::uuid '
    'AND EXISTS ('
    'SELECT 1 FROM controlplane.cp_artifact_locations l '
    'WHERE l.workspace_id = v.workspace_id AND l.artifact_version_id = v.artifact_version_id '
    "AND l.state = 'VERIFIED' AND (l.observed_hash IS NULL OR l.observed_hash = v.sha256_hash)"
    ')'
)

_SCRIPT_SQL = (
    'SELECT payload FROM controlplane.cp_script_versions '
    'WHERE workspace_id = %s::uuid AND script_version_id = %s '
    'ORDER BY revision DESC LIMIT 1'
)

SCRIPT_NOT_FOUND = 'SCRIPT_NOT_FOUND'
SCRIPT_PAYLOAD_INVALID = 'SCRIPT_PAYLOAD_INVALID'


class PlanPayloadInvalid(ValueError):
    """Raised when a production plan payload is malformed."""


class ScriptSegmentsError(ValueError):
    """Raised when stored script segments cannot be parsed or validated."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclass(frozen=True, kw_only=True)
class ScriptSegmentInfo:
    segment_id: str
    order: int
    claim_mode: str
    disclosure: str | None
    word_count: int


def _document(value: object) -> Mapping | None:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return None
        return parsed if isinstance(parsed, Mapping) else None
    return None


def _workspace(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError('workspace_id must be a non-empty string')
    return value


class PostgresPlanAssets:
    def __init__(self, manager: Any, *, workspace_id: str) -> None:
        self._manager = manager
        self._workspace_id = _workspace(workspace_id)

    def asset_refs(self, production_plan_ref: str) -> tuple[str, ...] | None:
        if not isinstance(production_plan_ref, str) or not production_plan_ref:
            raise ValueError('production_plan_ref must be a non-empty string')
        with self._manager.borrow_connection() as connection:
            row = connection.execute(_PLAN_SQL, (self._workspace_id, production_plan_ref)).fetchone()
        if row is None:
            return None
        payload = _document(row[0])
        if payload is None:
            raise PlanPayloadInvalid('timeline')
        timeline = payload.get('timeline')
        if not isinstance(timeline, Mapping):
            raise PlanPayloadInvalid('timeline')
        refs: set[str] = set()
        segments = timeline.get('segments')
        if isinstance(segments, list):
            for scene in segments:
                if isinstance(scene, Mapping):
                    visuals = scene.get('visuals')
                    if isinstance(visuals, list):
                        for visual in visuals:
                            if isinstance(visual, Mapping):
                                ref = visual.get('artifact_version_ref')
                                if isinstance(ref, str) and ref:
                                    refs.add(ref)
        hook_placement = payload.get('hook_placement')
        if isinstance(hook_placement, Mapping):
            for key in ('visual_hook_ref', 'audio_hook_ref', 'thumbnail_ref'):
                ref = hook_placement.get(key)
                if isinstance(ref, str) and ref:
                    refs.add(ref)
        fallbacks = payload.get('allowed_fallbacks')
        if isinstance(fallbacks, list):
            for item in fallbacks:
                if isinstance(item, Mapping):
                    ref = item.get('replacement_artifact_version_ref')
                    if isinstance(ref, str) and ref:
                        refs.add(ref)
        return tuple(sorted(refs))


class PostgresArtifactInfo:
    def __init__(self, manager: Any, *, workspace_id: str) -> None:
        self._manager = manager
        self._workspace_id = _workspace(workspace_id)

    def get_asset(self, artifact_version_id: str) -> ResolvedAsset | None:
        if not isinstance(artifact_version_id, str):
            return None
        try:
            normalized = str(uuid.UUID(artifact_version_id))
        except ValueError:
            return None
        with self._manager.borrow_connection() as connection:
            row = connection.execute(_ASSET_SQL, (self._workspace_id, normalized)).fetchone()
        if row is None:
            return None
        return ResolvedAsset(
            artifact_version_id=row[0],
            sha256=row[1],
            size_bytes=int(row[2]),
            media_type=row[3],
            role=row[4],
        )


def read_script_segments(
    manager: Any, *, workspace_id: str, script_version_ref: str
) -> tuple[ScriptSegmentInfo, ...]:
    workspace = _workspace(workspace_id)
    if not isinstance(script_version_ref, str) or not script_version_ref:
        raise ValueError('script_version_ref must be a non-empty string')
    with manager.borrow_connection() as connection:
        row = connection.execute(_SCRIPT_SQL, (workspace, script_version_ref)).fetchone()
    if row is None:
        raise ScriptSegmentsError(SCRIPT_NOT_FOUND, script_version_ref)
    payload = _document(row[0])
    segments = payload.get('segments') if payload is not None else None
    if not isinstance(segments, list) or len(segments) == 0:
        raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, 'segments')
    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    parsed: list[ScriptSegmentInfo] = []
    for i, s in enumerate(segments):
        if not isinstance(s, Mapping):
            raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, f'segments[{i}]')
        seg_id = s.get('segment_id')
        if not isinstance(seg_id, str) or not seg_id:
            raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, f'segments[{i}].segment_id')
        order = s.get('order')
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, f'segments[{i}].order')
        claim_mode = s.get('claim_mode')
        if not isinstance(claim_mode, str) or not claim_mode:
            raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, f'segments[{i}].claim_mode')
        disclosure = s.get('disclosure')
        if disclosure is not None and not isinstance(disclosure, str):
            raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, f'segments[{i}].disclosure')
        word_count = s.get('word_count')
        if not isinstance(word_count, int) or isinstance(word_count, bool) or word_count < 0:
            raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, f'segments[{i}].word_count')
        if seg_id in seen_ids:
            raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, f'segments[{i}].segment_id')
        if order in seen_orders:
            raise ScriptSegmentsError(SCRIPT_PAYLOAD_INVALID, f'segments[{i}].order')
        seen_ids.add(seg_id)
        seen_orders.add(order)
        parsed.append(
            ScriptSegmentInfo(
                segment_id=seg_id,
                order=order,
                claim_mode=claim_mode,
                disclosure=disclosure,
                word_count=word_count,
            )
        )
    return tuple(sorted(parsed, key=lambda item: item.order))


__all__ = (
    'PlanPayloadInvalid',
    'PostgresArtifactInfo',
    'PostgresPlanAssets',
    'SCRIPT_NOT_FOUND',
    'SCRIPT_PAYLOAD_INVALID',
    'ScriptSegmentInfo',
    'ScriptSegmentsError',
    'read_script_segments',
)
