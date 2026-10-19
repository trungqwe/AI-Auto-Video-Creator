"""F-05: ResolveRenderPackage from locked refs (CT-RND-002).

coveredIds: CT-RND-002, acceptance §8 mục 6 (phía resolve)
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from collections.abc import Iterable, Mapping

from render.domain.package_contract import (
    MISSING_REQUIRED, WRONG_TYPE, ContractViolation, RenderPackageRecord, validate_render_package_payload,
)
from render.domain.package_fingerprint import PackageFingerprintError, compute_package_fingerprint, verify_package_fingerprint
from render.ports.inputs import LocalMaterialRef, PlanAssetPort, ResolveInputs, ResolvedAsset

ASSET_OUTSIDE_PLAN_OR_FALLBACK = 'asset_outside_plan_or_fallback'
URL_NOT_ALLOWED = 'url_not_allowed'
INVALID_MATERIALIZATION_REF = 'invalid_materialization_ref'
DUPLICATE_ARTIFACT_VERSION = 'duplicate_artifact_version'
DUPLICATE_MATERIALIZATION_REF = 'duplicate_materialization_ref'
RENDER_PACKAGE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, 'render-package.f.ai-auto-video-creator')

_REF_FIELDS = ('production_snapshot_ref', 'script_version_ref', 'production_plan_ref', 'preset_revision_ref', 'voice_artifact_ref', 'word_timing_ref', 'output_metadata_revision', 'output_profile_revision')
_MAPPING_FIELDS = ('timeline', 'hook_placement', 'subtitle_config', 'mix_plan')
_HOOK_REFS = ('visual_hook_ref', 'audio_hook_ref', 'thumbnail_ref')
_LOCAL_REF_RE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9._-]{0,127}')
_PENDING_ID = 'pending'
_PENDING_FINGERPRINT = '0' * 64
_URL_SEP = ':/' + '/'


class ResolveError(ValueError):
    """A package could not be resolved; `code` is the stable reason and `field` the offending input field path."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(f'{code}:{field}')
        self.code = code
        self.field = field


def _text(value: object, field: str) -> str:
    if value is None:
        raise ResolveError(MISSING_REQUIRED, field)
    if not isinstance(value, str):
        raise ResolveError(WRONG_TYPE, field)
    if not value.strip():
        raise ResolveError(MISSING_REQUIRED, field)
    return value


def _mapping(value: object, field: str) -> Mapping:
    if value is None:
        raise ResolveError(MISSING_REQUIRED, field)
    if not isinstance(value, Mapping):
        raise ResolveError(WRONG_TYPE, field)
    return value


def _sequence(value: object, field: str) -> tuple:
    if value is None:
        raise ResolveError(MISSING_REQUIRED, field)
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ResolveError(WRONG_TYPE, field)
    return tuple(value)


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(v) for v in value]
    return value


def _scan_urls(value: object, path: str) -> None:
    if isinstance(value, str):
        if _URL_SEP in value:
            raise ResolveError(URL_NOT_ALLOWED, path)
    elif isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f'{path}.{key}' if path else str(key)
            _scan_urls(child, child_path)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            child_path = f'{path}[{index}]'
            _scan_urls(child, child_path)


def _fallback_ids(fallbacks: tuple) -> set[str]:
    ids: set[str] = set()
    for i, item in enumerate(fallbacks):
        if not isinstance(item, Mapping):
            raise ResolveError(WRONG_TYPE, f'allowed_fallbacks[{i}]')
        if 'artifact_version_id' in item:
            val = _text(item['artifact_version_id'], f'allowed_fallbacks[{i}].artifact_version_id')
            ids.add(val)
    return ids


def _plan_ids(plan_assets: PlanAssetPort, plan_ref: str) -> set[str]:
    refs = plan_assets.asset_refs(plan_ref)
    if refs is None:
        raise ResolveError(MISSING_REQUIRED, 'plan_assets')
    if isinstance(refs, (str, bytes)) or not isinstance(refs, Iterable):
        raise ResolveError(WRONG_TYPE, 'plan_assets')
    result: set[str] = set()
    for item in refs:
        if not isinstance(item, str):
            raise ResolveError(WRONG_TYPE, 'plan_assets')
        result.add(item)
    return result


def _assets(items: tuple) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for index, asset in enumerate(items):
        base = f'input_artifacts[{index}]'
        if not isinstance(asset, ResolvedAsset):
            raise ResolveError(WRONG_TYPE, base)
        version = _text(asset.artifact_version_id, f'{base}.artifact_version_id')
        _text(asset.role, f'{base}.role')
        if version in seen:
            raise ResolveError(DUPLICATE_ARTIFACT_VERSION, f'{base}.artifact_version_id')
        seen.add(version)
        result.append({
            'artifact_version_id': version,
            'sha256': asset.sha256,
            'size_bytes': asset.size_bytes,
            'media_type': asset.media_type,
        })
    return result


def _manifest(items: tuple) -> dict:
    manifest: dict = {}
    for index, item in enumerate(items):
        base = f'materialization_manifest[{index}]'
        if not isinstance(item, LocalMaterialRef):
            raise ResolveError(WRONG_TYPE, base)
        key = _text(item.artifact_version_id, f'{base}.artifact_version_id')
        local = _text(item.local_ref, f'{base}.local_ref')
        if _LOCAL_REF_RE.fullmatch(local) is None:
            raise ResolveError(INVALID_MATERIALIZATION_REF, f'{base}.local_ref')
        if key in manifest:
            raise ResolveError(DUPLICATE_MATERIALIZATION_REF, f'{base}.artifact_version_id')
        manifest[key] = {'local_ref': local}
    return manifest


def _referenced(timeline: Mapping, hook_placement: Mapping) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    segments = timeline.get('segments')
    if isinstance(segments, (list, tuple)):
        for i, segment in enumerate(segments):
            if isinstance(segment, Mapping):
                refs = segment.get('visual_asset_refs')
                if isinstance(refs, (list, tuple)):
                    for j, ref in enumerate(refs):
                        if isinstance(ref, str):
                            result.append((ref, f'timeline.segments[{i}].visual_asset_refs[{j}]'))
    for key in _HOOK_REFS:
        ref = hook_placement.get(key)
        if isinstance(ref, str):
            result.append((ref, f'hook_placement.{key}'))
    return result


def resolve_render_package(inputs: ResolveInputs, plan_assets: PlanAssetPort) -> RenderPackageRecord:
    """Build the immutable RenderPackageRecord from locked refs; raises ResolveError(code, field) and never invents text, URLs or paths."""
    if not isinstance(inputs, ResolveInputs):
        raise ResolveError(WRONG_TYPE, 'inputs')
    if not isinstance(plan_assets, PlanAssetPort):
        raise ResolveError(WRONG_TYPE, 'plan_assets')

    payload: dict = {name: _text(getattr(inputs, name), name) for name in _REF_FIELDS}

    refs = _sequence(inputs.language_validation_refs, 'language_validation_refs')
    for index, ref in enumerate(refs):
        if not isinstance(ref, str):
            raise ResolveError(WRONG_TYPE, f'language_validation_refs[{index}]')
    payload['language_validation_refs'] = sorted(refs)

    assets = _assets(_sequence(inputs.input_artifacts, 'input_artifacts'))

    for name in _MAPPING_FIELDS:
        payload[name] = _thaw(_mapping(getattr(inputs, name), name))

    fallbacks = _sequence(inputs.allowed_fallbacks, 'allowed_fallbacks')
    fallback_ids = _fallback_ids(fallbacks)
    payload['allowed_fallbacks'] = _thaw(fallbacks)

    payload['materialization_manifest'] = _manifest(_sequence(inputs.materialization_manifest, 'materialization_manifest'))
    payload['output_path_ref'] = _text(inputs.output_path_ref, 'output_path_ref')

    allowed = _plan_ids(plan_assets, payload['production_plan_ref']) | fallback_ids | {payload['voice_artifact_ref'], payload['word_timing_ref']}

    for index, asset in enumerate(assets):
        if asset['artifact_version_id'] not in allowed:
            raise ResolveError(ASSET_OUTSIDE_PLAN_OR_FALLBACK, f'input_artifacts[{index}]')

    for ref, field in _referenced(payload['timeline'], payload['hook_placement']):
        if ref not in allowed:
            raise ResolveError(ASSET_OUTSIDE_PLAN_OR_FALLBACK, field)

    payload['input_artifacts'] = sorted(assets, key=lambda item: (item['artifact_version_id'], item['sha256'], item['size_bytes'], item['media_type']))
    _scan_urls(payload, '')

    try:
        record = validate_render_package_payload({**payload, 'render_package_id': _PENDING_ID, 'package_fingerprint': _PENDING_FINGERPRINT})
        fingerprint = compute_package_fingerprint(record)
    except ContractViolation as exc:
        raise ResolveError(exc.code, exc.field) from exc
    except PackageFingerprintError as exc:
        raise ResolveError(exc.code, exc.field) from exc

    sealed = dataclasses.replace(record, package_fingerprint=fingerprint, render_package_id=str(uuid.uuid5(RENDER_PACKAGE_NAMESPACE, fingerprint)))
    verify_package_fingerprint(sealed)
    return sealed
