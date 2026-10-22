"""CP-5-COMPLETION: nối completion vào composition root; BL-CV-08 và BL-CV-06 vẫn PENDING (src/main.py chưa gọi mô-đun này)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from catalog.application.usage import MediaUsageRecorder
from catalog.persistence.usage import media_usage_repository_factory
from controlplane.application.orchestration.commit_completion import (
    CommitVideoCompletion,
    CompletionContext,
    CompletionResult,
)
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


__all__ = ['CompletionService', 'build_completion_service']
