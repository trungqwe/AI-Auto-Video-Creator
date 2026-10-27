"""CP-5-COMPLETION: nối completion vào composition root; BL-CV-08 và BL-CV-06 vẫn PENDING (src/main.py chưa gọi mô-đun này)."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from catalog.application.usage import MediaUsageRecorder
from catalog.persistence.usage import media_usage_repository_factory
from controlplane.application.orchestration.batch_allocation import AllocateJobService, FinalizeBatchService
from controlplane.application.orchestration.commit_completion import (
    CommitVideoCompletion,
    CompletionContext,
    CompletionResult,
)
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle
from controlplane.application.orchestration.variant_handlers import commit_video_completion_handler, reserve_variant_handler
from controlplane.infrastructure.db.orchestration.postgres_completion import (
    PostgresCompletionUnitOfWork,
    PostgresMediaUsagePort,
)


class CompletionService:
    def __init__(self, transactions: Any, workspace_id: str) -> None:
        self._transactions = transactions
        self._workspace_id = workspace_id

    def complete(self, request: Mapping[str, Any], context: CompletionContext) -> CompletionResult:
        uow = PostgresCompletionUnitOfWork(self._transactions, self._workspace_id, request)
        recorder = MediaUsageRecorder(media_usage_repository_factory(self._workspace_id))
        usage = PostgresMediaUsagePort(uow, recorder)
        return CommitVideoCompletion(lambda: uow, usage).execute(request, context)


def build_completion_service(transactions: Any, workspace_id: str) -> CompletionService:
    return CompletionService(transactions, workspace_id)


def completion_activity_services(
    transactions: Any,
    *,
    connection_factory: Callable[[], Any],
    workspace_id: str,
    selector: Any,
    clock: Callable[[], Any],
) -> dict[str, Callable[..., Any]]:
    recorder = MediaUsageRecorder(media_usage_repository_factory(workspace_id))
    return {
        'AllocateJob': AllocateJobService(connection_factory, selector, workspace_id=workspace_id),
        'FinalizeBatch': FinalizeBatchService(BatchLifecycle(connection_factory, clock, workspace_id=workspace_id)),
        'ReserveVariant': reserve_variant_handler(transactions, workspace_id=workspace_id),
        'CommitVideoCompletion': commit_video_completion_handler(
            transactions, workspace_id=workspace_id, clock=clock, usage_recorder=recorder
        ),
    }


__all__ = ['CompletionService', 'build_completion_service', 'completion_activity_services']
