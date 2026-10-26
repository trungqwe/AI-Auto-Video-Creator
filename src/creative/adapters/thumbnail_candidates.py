"""Thumbnail candidates of SelectCreativeAssets (PW-D3, CT-MED-006).

A candidate is a valid frame of a visual hook (inside the hook window) or a still image taken from the media candidates, and always carries the reason it is a candidate. Pure: no I/O and no catalog access.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from creative.domain.asset_selection import (
    INPUT_NOT_READY, REF_TYPE_VISUAL_HOOK, HookCandidate, MediaCandidate, SelectionRejected, ThumbnailCandidate)

DEFAULT_OVERLAY_INTENT = 'headline_text'
SOURCE_VISUAL_HOOK = 'visual_hook'
SOURCE_MEDIA_ASSET = 'media_asset'


def _hook_duration_ms(hook: HookCandidate) -> int | None:
    technical = hook.provenance.get('technical')
    value = technical.get('duration_ms') if isinstance(technical, Mapping) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


class ThumbnailCandidates:
    def __init__(self, *, overlay_intent: str = DEFAULT_OVERLAY_INTENT) -> None:
        if not isinstance(overlay_intent, str) or not overlay_intent.strip():
            raise ValueError('overlay_intent must be a non-empty string')
        self._overlay_intent = overlay_intent

    def thumbnail_candidates(
        self, *, visual_hooks: Iterable[HookCandidate], media_candidates: Iterable[MediaCandidate],
    ) -> tuple[ThumbnailCandidate, ...]:
        """Hook frames first, then image stills; SelectionRejected(INPUT_NOT_READY, no_thumbnail_candidates) when there is no valid frame."""
        candidates: list[ThumbnailCandidate] = []
        for hook in visual_hooks:
            if hook.hook_kind != REF_TYPE_VISUAL_HOOK:
                raise ValueError('thumbnail frames come from visual hooks only')
            duration = _hook_duration_ms(hook)
            if duration is None:
                continue
            frame_ms = duration // 2
            candidates.append(self._build(
                thumbnail_id=f'thumb:{hook.hook_id}', revision_id=f'{hook.revision_id}:frame-{frame_ms}', subject=hook.hook_id,
                frame_ms=frame_ms, availability=hook.availability, safety=hook.safety_rights_status,
                semantic=hook.semantic_match_components,
                source={
                    'source_kind': SOURCE_VISUAL_HOOK, 'source_ref_id': hook.hook_id, 'source_revision_id': hook.revision_id,
                    'hook_window_ms': [0, duration]},
                reason=f'frame at {frame_ms} ms inside the {duration} ms window of visual hook {hook.hook_id}'))
        for media in media_candidates:
            candidates.append(self._build(
                thumbnail_id=f'thumb:{media.media_asset_id}', revision_id=f'{media.artifact_version_ref}:still',
                subject=media.media_asset_id, frame_ms=0, availability=media.availability,
                safety=media.safety_rights_status, semantic=media.semantic_match_components,
                source={
                    'source_kind': SOURCE_MEDIA_ASSET, 'source_ref_id': media.media_asset_id,
                    'source_revision_id': media.artifact_version_ref, 'source_provenance': dict(media.provenance)},
                reason=f'still image {media.media_asset_id} as the thumbnail frame'))
        if not candidates:
            raise SelectionRejected(INPUT_NOT_READY, 'no_thumbnail_candidates', 'thumbnail_candidates')
        return tuple(candidates)

    def _build(
        self, *, thumbnail_id: str, revision_id: str, subject: str, frame_ms: int, availability: str,
        safety: Mapping[str, object], semantic: Mapping[str, object], source: dict, reason: str,
    ) -> ThumbnailCandidate:
        if not reason.strip():
            raise ValueError('a thumbnail candidate needs a reason')
        return ThumbnailCandidate(
            thumbnail_id=thumbnail_id, revision_id=revision_id, subject_refs=(subject,),
            crop_focus={'x': 0.5, 'y': 0.5, 'frame_ms': frame_ms}, overlay_intent=self._overlay_intent,
            availability=availability, safety_rights_status=dict(safety), semantic_match_components=dict(semantic),
            provenance={**source, 'frame_ms': frame_ms, 'reason': reason})
