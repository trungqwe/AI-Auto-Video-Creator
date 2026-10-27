"""PW-A2: dựng CollectActivityDeps theo từng lời gọi cho handler CollectSource (CT-SRC-004, CT-SRC-005, CT-WF-003).

Mỗi lời gọi nhận deps mới: UnitOfWork mới, adapter chọn theo từng nguồn (loại nguồn đọc từ cp_sources) và extractor gắn với đúng adapter đó. UnitOfWork, SecureFetcher và cổng grant được tiêm từ composition root.
"""
from __future__ import annotations

import datetime
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from controlplane.application.orchestration.workflows.activities import (
    INVALID_ACTIVITY_REQUEST,
    MISSING_EXECUTION_GRANT,
    ActivityHandler,
    ActivityRejected,
)
from controlplane.domain.orchestration.fencing import GrantClaims
from source_ingestion.adapters.real_feed_source import ADAPTER_VERSION, EXTRACTOR_VERSION, SOURCE_KINDS, RealFeedSource
from source_ingestion.adapters.secure_fetch import FetchPolicy, SecureFetcher
from source_ingestion.application.collect_source import CollectionUnitOfWork
from source_ingestion.domain.collection_run import RetryPolicy
from source_ingestion.domain.package import ExtractionPolicy
from source_ingestion.ports.source_adapter import (
    AdapterDescriptor,
    AdapterOperation,
    CapabilityUnavailable,
    ExtractedCandidate,
    FetchedDocument,
    SourceAdapter,
)
from source_ingestion.worker.activity_handler import (
    ActivityRequestError,
    ClaimsCurrencyPort,
    CollectActivityDeps,
    InMemoryActivityResultStore,
    handle_collect_source_activity,
)

EXECUTION_GRANT_FIELD = 'execution_grant'
# Mặc định (D8): thử lại tối đa 3 lần; feed RSS/Atom bắt buộc có tiêu đề; adapter_revision gắn với phiên bản RealFeedSource.
DEFAULT_RETRY_POLICY = RetryPolicy('retry-default-v1', 3)
DEFAULT_EXTRACTION_POLICY = ExtractionPolicy('extraction-default-v1', {kind: True for kind in sorted(SOURCE_KINDS)})
DEFAULT_ADAPTER_REVISION = 'real-feed-' + ADAPTER_VERSION
# collect_source đọc cả ngoài khối with của UnitOfWork; đây là các thao tác đọc của repository.
READ_METHODS = frozenset({'get', 'get_periodic', 'get_latest', 'list_by_run', 'list_by_source', 'list_sources', 'resolve_identity'})


class UnavailableSourceAdapter:
    """SourceAdapter cho nguồn không tìm thấy hoặc loại chưa hỗ trợ: mọi thao tác trả CapabilityUnavailable, không bao giờ là thành công rỗng."""

    def __init__(self, reason: str) -> None:
        self._reason = reason
        self.descriptor = AdapterDescriptor('unavailable-source', '1', frozenset())

    def _unavailable(self, operation: AdapterOperation) -> CapabilityUnavailable:
        return self.descriptor.unavailable(operation, self._reason)

    def probe(self, locator: str) -> CapabilityUnavailable:
        return self._unavailable(AdapterOperation.PROBE)

    def list_candidates(self, locator: str, cursor: str | None) -> CapabilityUnavailable:
        return self._unavailable(AdapterOperation.LIST_CANDIDATES)

    def fetch_document(self, locator: str) -> CapabilityUnavailable:
        return self._unavailable(AdapterOperation.FETCH_DOCUMENT)

    def extract_candidate(self, document: FetchedDocument) -> CapabilityUnavailable:
        return self._unavailable(AdapterOperation.EXTRACT_CANDIDATE)

    def resume_from_checkpoint(self, checkpoint_version: str, cursor: str) -> CapabilityUnavailable:
        return self._unavailable(AdapterOperation.RESUME_FROM_CHECKPOINT)

    def supplemental_search(self, intent: Mapping[str, str]) -> CapabilityUnavailable:
        return self._unavailable(AdapterOperation.SUPPLEMENTAL_SEARCH)

class _FetchBridge:
    """HtmlExtractor của một lời gọi: giao cho extract_candidate của adapter đã chọn, trên đúng FetchedDocument vừa tải (giữ nguyên bytes và requested_locator để tra gợi ý ảnh, tác giả của feed)."""

    version: str = EXTRACTOR_VERSION

    def __init__(self) -> None:
        self._adapter: SourceAdapter | None = None
        self._last: FetchedDocument | None = None

    def bind(self, adapter: SourceAdapter) -> SourceAdapter:
        self._adapter = adapter
        self._last = None
        return _RecordingAdapter(adapter, self)

    def remember(self, document: FetchedDocument) -> None:
        self._last = document

    def extract(self, html: str, *, base_locator: str) -> ExtractedCandidate:
        adapter, document = self._adapter, self._last
        if adapter is None or document is None or document.observation.final_locator != base_locator:
            raise LookupError('FETCHED_DOCUMENT_UNAVAILABLE')
        extracted = adapter.extract_candidate(document)
        if not isinstance(extracted, ExtractedCandidate):
            raise LookupError('EXTRACTION_UNAVAILABLE')
        return extracted


class _RecordingAdapter:
    """Bọc adapter của một nguồn: nhớ FetchedDocument vừa tải cho _FetchBridge; mọi thuộc tính khác chuyển cho adapter bên trong."""

    def __init__(self, adapter: SourceAdapter, bridge: _FetchBridge) -> None:
        self.adapter = adapter
        self._bridge = bridge

    def fetch_document(self, locator: str) -> Any:
        result = self.adapter.fetch_document(locator)
        if isinstance(result, FetchedDocument):
            self._bridge.remember(result)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self.adapter, name)


class _ReadThroughRepository:
    """Thao tác đọc (READ_METHODS) ngoài khối with mượn kết nối ngắn hạn; thao tác khác đi thẳng và phải nằm trong khối with."""

    def __init__(self, uow: Any, repository: Any) -> None:
        self._uow = uow
        self._repository = repository

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._repository, name)
        if name not in READ_METHODS:
            return target

        def read(*args: Any, **kwargs: Any) -> Any:
            if self._uow.active:
                return target(*args, **kwargs)
            with self._uow:
                return target(*args, **kwargs)

        return read


class ReadThroughUnitOfWork:
    """CollectionUnitOfWork bọc PostgresSourceIngestionUnitOfWork (cần thuộc tính active)."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.sources = _ReadThroughRepository(inner, inner.sources)
        self.runs = _ReadThroughRepository(inner, inner.runs)
        self.packages = _ReadThroughRepository(inner, inner.packages)
        self.checkpoints = _ReadThroughRepository(inner, inner.checkpoints)
        self.outbox = inner.outbox

    def __enter__(self) -> ReadThroughUnitOfWork:
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._inner.__exit__(exc_type, exc_val, exc_tb)

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()

@dataclass(frozen=True)
class CollectDepsFactory:
    """Cấu hình dùng chung, không giữ trạng thái theo lời gọi; deps_for_call dựng CollectActivityDeps mới cho mỗi lời gọi. results là kho kết quả idempotent duy nhất được chia sẻ có chủ đích."""

    uow_factory: Callable[[], CollectionUnitOfWork]
    grants: ClaimsCurrencyPort
    workspace_id: str
    fetcher: SecureFetcher
    feed_policy: FetchPolicy
    article_policy: FetchPolicy
    retry_policy: RetryPolicy = field(default_factory=lambda: DEFAULT_RETRY_POLICY)
    extraction_policy: ExtractionPolicy = field(default_factory=lambda: DEFAULT_EXTRACTION_POLICY)
    adapter_revision: str = DEFAULT_ADAPTER_REVISION
    results: InMemoryActivityResultStore = field(default_factory=InMemoryActivityResultStore)

    def source_adapter(self, source_id: str) -> SourceAdapter:
        """Adapter mới cho đúng một nguồn: loại nguồn đọc từ cp_sources, không khoá theo kind và không dùng chung instance giữa các nguồn."""
        uow = self.uow_factory()
        with uow:
            source = uow.sources.get(self.workspace_id, source_id)
        if source is None:
            return UnavailableSourceAdapter('source_not_found')
        if source.source_kind not in SOURCE_KINDS:
            return UnavailableSourceAdapter('source_kind_unsupported')
        return RealFeedSource(
            self.fetcher,
            source_kind=source.source_kind,
            feed_policy=self.feed_policy,
            article_policy=self.article_policy,
        )

    def deps_for_call(self) -> CollectActivityDeps:
        bridge = _FetchBridge()

        def adapter_for(source_id: str) -> SourceAdapter:
            return bridge.bind(self.source_adapter(source_id))

        return CollectActivityDeps(
            uow=ReadThroughUnitOfWork(self.uow_factory()),
            grants=self.grants,
            adapter_for=adapter_for,
            extractor=bridge,
            retry_policy=self.retry_policy,
            adapter_revision=self.adapter_revision,
            workspace_id=self.workspace_id,
            extraction_policy=self.extraction_policy,
            results=self.results,
        )


def reject_request_error(error: ActivityRequestError) -> ActivityRejected:
    """ActivityRequestError -> ActivityRejected để _activity_fn ném ApplicationError(non_retryable=True) thay vì thử lại vô hạn."""
    issues = [{'code': code, 'field': name} for code, name in error.issues]
    missing = any(issue['field'] == EXECUTION_GRANT_FIELD for issue in issues)
    return ActivityRejected(MISSING_EXECUTION_GRANT if missing else INVALID_ACTIVITY_REQUEST, issues)


def collect_source_activity_handler(
    factory: CollectDepsFactory, clock: Callable[[], datetime.datetime]
) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        try:
            return handle_collect_source_activity(request, claims, factory.deps_for_call(), clock)
        except ActivityRequestError as error:
            raise reject_request_error(error) from error

    return handler


__all__ = [
    'CollectDepsFactory',
    'ReadThroughUnitOfWork',
    'UnavailableSourceAdapter',
    'collect_source_activity_handler',
    'reject_request_error',
]
