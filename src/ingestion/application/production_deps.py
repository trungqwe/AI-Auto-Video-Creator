"""PW-A2: dựng ResolveActivityDeps theo từng lời gọi cho handler ResolveCollectedDocument (CT-CNT-001, CT-WF-003).

Mỗi lời gọi nhận một UnitOfWork mới. tier_lookup đọc cp_sources, package_loader tra cp_collected_document_packages theo collected_document_id; kết nối đến từ connection_factory được tiêm nên mô-đun không nạp psycopg. dedup_policy mặc định theo corpus B-12 (docs/delivery-evidence/b-12/report.md).
"""
from __future__ import annotations

import copy
import re
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from controlplane.application.orchestration.workflows.activities import (
    INVALID_ACTIVITY_REQUEST,
    MISSING_EXECUTION_GRANT,
    REF_TYPE_COLLECTED_DOCUMENT,
    ActivityHandler,
    ActivityRejected,
)
from ingestion.application.activity_handler import (
    KIND_ACTIVITY_RESULT,
    ActivityRequestError,
    ResolveActivityDeps,
    handle_resolve_activity,
)
from ingestion.application.ports import UnitOfWork
from ingestion.application.resolve_document import DEDUP_POLICY_REVISION, KIND_MEDIA_ATTACHMENT
from ingestion.domain.fingerprint import NEAR_DUPLICATE_JACCARD, SHINGLE_SIZE

EXECUTION_GRANT_FIELD = 'execution_grant'
# Mặc định dedup (D8): revision có tên riêng, hai ngưỡng theo corpus B-12 (jaccard 0.8, shingle 3); đổi bằng cách truyền dedup_policy khác vào ResolveDepsFactory.
DEFAULT_DEDUP_POLICY = MappingProxyType({
    DEDUP_POLICY_REVISION: 'dedup-default-v1',
    NEAR_DUPLICATE_JACCARD: 0.8,
    SHINGLE_SIZE: 3,
})
# PostgresRecordRepository chỉ có bảng cho bốn kind khác; hai kind này do handler và resolve_document dùng nên giữ trong tiến trình (mục mở trong báo cáo).
PROCESS_LOCAL_KINDS = frozenset({KIND_ACTIVITY_RESULT, KIND_MEDIA_ATTACHMENT})
ConnectionFactory = Callable[[], AbstractContextManager[Any]]
_TIER_RE = re.compile(r'tier_([1-3])')


def new_id() -> str:
    return str(uuid.uuid4())

class PostgresSourceTierLookup:
    """SourceTierLookup đọc tier từ cp_sources (payload 'tier_1'..'tier_3'); nguồn lạ hoặc tier ngoài dải là LookupError, handler xử lý thành FAILED_FINAL không thử lại."""

    def __init__(self, connection_factory: ConnectionFactory, workspace_id: str) -> None:
        self._connection_factory = connection_factory
        self._workspace_id = workspace_id

    def tier_of(self, source_id: str) -> int:
        with self._connection_factory() as connection:
            row = connection.execute(
                "SELECT payload->>'tier' FROM controlplane.cp_sources WHERE workspace_id = %s AND source_id = %s",
                (self._workspace_id, source_id),
            ).fetchone()
        match = _TIER_RE.fullmatch(row[0] or '') if row is not None else None
        if match is None:
            raise LookupError(f'no tier for source_id {source_id}')
        return int(match.group(1))


class PostgresPackageLoader:
    """package_loader: tra CollectedDocumentPackage theo collected_document_id trong cp_collected_document_packages; không thấy thì LookupError."""

    def __init__(self, connection_factory: ConnectionFactory, workspace_id: str) -> None:
        self._connection_factory = connection_factory
        self._workspace_id = workspace_id

    def __call__(self, input_ref: Mapping[str, Any]) -> Mapping[str, Any]:
        document_id = input_ref.get('ref_id')
        if input_ref.get('ref_type') != REF_TYPE_COLLECTED_DOCUMENT or not isinstance(document_id, str) or not document_id:
            raise LookupError('input_ref is not a collected_document')
        with self._connection_factory() as connection:
            row = connection.execute(
                "SELECT payload FROM controlplane.cp_collected_document_packages WHERE workspace_id = %s AND payload->>'collected_document_id' = %s ORDER BY created_at LIMIT 1",
                (self._workspace_id, document_id),
            ).fetchone()
        if row is None:
            raise LookupError(f'collected document {document_id} not found')
        return dict(row[0])

class _ProcessLocalRecords:
    """RecordRepository: kind trong PROCESS_LOCAL_KINDS được stage và chỉ công bố khi commit; kind khác chuyển cho repository của UoW bên trong."""

    def __init__(self, inner: Any, shared: dict[tuple[str, str], dict[str, Any]], lock: Any) -> None:
        self._inner = inner
        self._shared = shared
        self._lock = lock
        self.staged: dict[tuple[str, str], dict[str, Any]] = {}

    def get(self, kind: str, record_id: str) -> Mapping[str, Any] | None:
        if kind not in PROCESS_LOCAL_KINDS:
            return self._inner.get(kind, record_id)
        key = (kind, record_id)
        with self._lock:
            stored = self.staged[key] if key in self.staged else self._shared.get(key)
        return None if stored is None else copy.deepcopy(stored)

    def put(self, kind: str, record_id: str, record: Mapping[str, Any]) -> None:
        if kind not in PROCESS_LOCAL_KINDS:
            self._inner.put(kind, record_id, record)
            return
        self.staged[(kind, record_id)] = copy.deepcopy(dict(record))

    def list(self, kind: str) -> tuple[Mapping[str, Any], ...]:
        if kind not in PROCESS_LOCAL_KINDS:
            return self._inner.list(kind)
        with self._lock:
            merged = {key: value for key, value in self._shared.items() if key[0] == kind}
        merged.update({key: value for key, value in self.staged.items() if key[0] == kind})
        return tuple(copy.deepcopy(value) for value in merged.values())

    def publish(self) -> None:
        with self._lock:
            self._shared.update(self.staged)
        self.staged = {}


class ProcessLocalRecordsUnitOfWork:
    """UnitOfWork bọc UoW PostgreSQL của B: articles, resolutions, events, outbox giữ nguyên; records bổ sung hai kind chưa có bảng."""

    def __init__(self, inner: UnitOfWork, shared: dict[tuple[str, str], dict[str, Any]], lock: Any) -> None:
        self._inner = inner
        self.articles = inner.articles
        self.resolutions = inner.resolutions
        self.events = inner.events
        self.outbox = inner.outbox
        self.records = _ProcessLocalRecords(inner.records, shared, lock)

    def __enter__(self) -> ProcessLocalRecordsUnitOfWork:
        self._inner.__enter__()
        self.records.staged = {}
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.records.staged = {}
        self._inner.__exit__(exc_type, exc, tb)

    def commit(self) -> None:
        self._inner.commit()
        self.records.publish()

    def rollback(self) -> None:
        self._inner.rollback()
        self.records.staged = {}

@dataclass(frozen=True)
class ResolveDepsFactory:
    """Cấu hình dùng chung; deps_for_call dựng ResolveActivityDeps mới (UoW mới, tier_lookup mới) cho mỗi lời gọi. Chỉ kho kind process-local được chia sẻ có chủ đích."""

    uow_factory: Callable[[], UnitOfWork]
    connection_factory: ConnectionFactory
    workspace_id: str
    dedup_policy: Mapping[str, Any] = field(default_factory=lambda: DEFAULT_DEDUP_POLICY)
    topic_rules: Sequence[Mapping[str, Any]] = ()
    id_factory: Callable[[], str] = new_id
    shared_records: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    records_lock: Any = field(default_factory=threading.Lock, init=False, repr=False)

    def deps_for_call(self) -> ResolveActivityDeps:
        uow = ProcessLocalRecordsUnitOfWork(self.uow_factory(), self.shared_records, self.records_lock)
        return ResolveActivityDeps(
            uow=uow,
            tier_lookup=PostgresSourceTierLookup(self.connection_factory, self.workspace_id),
            id_factory=self.id_factory,
            dedup_policy=self.dedup_policy,
            topic_rules=self.topic_rules,
        )

    def package_loader(self) -> PostgresPackageLoader:
        return PostgresPackageLoader(self.connection_factory, self.workspace_id)


def reject_request_error(error: ActivityRequestError) -> ActivityRejected:
    """ActivityRequestError -> ActivityRejected để _activity_fn ném ApplicationError(non_retryable=True) thay vì thử lại vô hạn."""
    issues = [{'code': issue.code, 'field': issue.field} for issue in error.issues]
    missing = any(issue['field'] == EXECUTION_GRANT_FIELD for issue in issues)
    return ActivityRejected(MISSING_EXECUTION_GRANT if missing else INVALID_ACTIVITY_REQUEST, issues)


def resolve_activity_handler(factory: ResolveDepsFactory, clock: Callable[[], datetime]) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        try:
            return handle_resolve_activity(request, factory.package_loader(), factory.deps_for_call(), clock)
        except ActivityRequestError as error:
            raise reject_request_error(error) from error

    return handler


__all__ = [
    'DEFAULT_DEDUP_POLICY',
    'PostgresPackageLoader',
    'PostgresSourceTierLookup',
    'ProcessLocalRecordsUnitOfWork',
    'ResolveDepsFactory',
    'reject_request_error',
    'resolve_activity_handler',
]
