"""PW-A3: handler RegisterMediaDiscovery (CT-MED-001, capability C) bọc register_discovery.

Anh tải kèm bài do media_fetcher tải và băm sha256 (RealMediaFetcher ở wiring thật). Mỗi ảnh chỉ được đăng ký khi observation có đủ provenance: URL gốc, bài (article_ref), thời điểm quan sát và sha256 (fingerprint). Handler không cấp quyền dùng: quyền tài sản do register_discovery đặt, handler không đổi quyền và không ghi bản ghi sử dụng.
"""
from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from catalog.application.discovery import Disposition, register_discovery
from catalog.ports.repositories import MediaAssetRepository
from controlplane.application.orchestration.workflows.activities import (
    INVALID_ACTIVITY_REQUEST,
    MISSING_EXECUTION_GRANT,
    REF_TYPE_COLLECTED_DOCUMENT,
    ActivityHandler,
    ActivityRejected,
)

ACTIVITY_NAME = 'RegisterMediaDiscovery'
REF_TYPE_MEDIA_ASSET = 'media_asset'
SUCCEEDED = 'succeeded'
FAILED = 'failed'
PROBLEM_PACKAGE_NOT_FOUND = 'collected_document_not_found'
PROBLEM_PACKAGE_UNAVAILABLE = 'collected_document_unavailable'
_ASSET_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, 'urn:catalog:media-asset')
_COUNT_KEY = {
    Disposition.NEW_ASSET: 'registered',
    Disposition.NEW_PROVENANCE: 'provenance_added',
    Disposition.DUPLICATE_OBSERVATION: 'duplicates',
    Disposition.REJECTED: 'rejected',
}


class MediaFetcher(Protocol):
    def fetch_article_media(
        self, media_items: Any, *, source_ref: str | None, article_ref: str | None, event_ref: str | None = None
    ) -> Any:
        """Trả về đối tượng có `staged` (mỗi phần tử có `observation`) và `problems`."""


@dataclass(frozen=True)
class MediaDiscoveryDeps:
    workspace_id: str
    package_loader: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    media_fetcher: MediaFetcher
    open_assets: Callable[[str], AbstractContextManager[MediaAssetRepository]]


def _utc(moment: datetime.datetime) -> str:
    return moment.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _problem(code: str, retryable: bool, message: str) -> dict[str, Any]:
    return {'code': code, 'retryable': retryable, 'message': message}


def _input_ref(request: Mapping[str, Any]) -> Mapping[str, Any]:
    refs = request.get('input_refs')
    ref = refs[0] if isinstance(refs, (list, tuple)) and refs else None
    valid = (
        isinstance(ref, Mapping)
        and ref.get('ref_type') == REF_TYPE_COLLECTED_DOCUMENT
        and isinstance(ref.get('ref_id'), str)
        and bool(ref['ref_id'].strip())
    )
    if not valid:
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    return ref


def _has_provenance(observation: Any) -> bool:
    entry = observation.provenance
    return bool(entry.original_locator and entry.article_ref and entry.observed_at and observation.fingerprint is not None)


def _new_asset_id(discovery_id: str) -> str:
    return 'ma-' + str(uuid.uuid5(_ASSET_NAMESPACE, discovery_id))


def register_media_discovery(
    request: Mapping[str, Any], claims: Any, deps: MediaDiscoveryDeps, clock: Callable[[], datetime.datetime]
) -> dict[str, Any]:
    if claims is None:
        raise ActivityRejected(MISSING_EXECUTION_GRANT)
    input_ref = _input_ref(request)

    def build(disposition: str, output_refs: list[dict[str, str]], metrics: dict[str, int] | None = None, problem: dict[str, Any] | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            'stage_run_id': claims.stage_run_id,
            'grant_id': claims.grant_id,
            'execution_generation': claims.execution_generation,
            'recovery_epoch': claims.recovery_epoch,
            'disposition': disposition,
            'output_refs': output_refs,
            'completed_at': _utc(clock()),
        }
        if metrics is not None:
            result['metrics'] = metrics
        if problem is not None:
            result['problem'] = problem
        return result

    try:
        package = deps.package_loader(input_ref)
    except LookupError:
        return build(FAILED, [], problem=_problem(PROBLEM_PACKAGE_NOT_FOUND, False, 'collected document package not found'))
    except OSError:
        return build(FAILED, [], problem=_problem(PROBLEM_PACKAGE_UNAVAILABLE, True, 'collected document package could not be loaded'))
    batch = deps.media_fetcher.fetch_article_media(
        package.get('media_discoveries') or (), source_ref=package.get('source_id'), article_ref=input_ref['ref_id']
    )
    counts = dict.fromkeys(('registered', 'provenance_added', 'duplicates', 'rejected'), 0)
    asset_ids: dict[str, None] = {}
    with deps.open_assets(deps.workspace_id) as repository:
        for staged in batch.staged:
            observation = staged.observation
            if not _has_provenance(observation):
                counts['rejected'] += 1
                continue
            outcome = register_discovery(repository, observation, _new_asset_id(observation.discovery_id))
            counts[_COUNT_KEY[outcome.disposition]] += 1
            if outcome.media_asset_id is not None:
                asset_ids[outcome.media_asset_id] = None
    metrics = {**counts, 'fetch_problems': len(batch.problems)}
    return build(SUCCEEDED, [{'ref_type': REF_TYPE_MEDIA_ASSET, 'ref_id': asset_id} for asset_id in asset_ids], metrics)


def register_media_discovery_handler(deps: MediaDiscoveryDeps, clock: Callable[[], datetime.datetime]) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        return register_media_discovery(request, claims, deps, clock)

    return handler


__all__ = [
    'MediaDiscoveryDeps',
    'MediaFetcher',
    'register_media_discovery',
    'register_media_discovery_handler',
]
