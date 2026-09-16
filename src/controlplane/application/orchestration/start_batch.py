"""P7A StartProductionBatch command port."""

from __future__ import annotations

from typing import Any, Callable, Protocol
import uuid


class StartBatchRepositoryPort(Protocol):
    def insert(self, *, workspace_id: str, batch_id: str, target_count: int) -> None: ...


class StartBatchService:
    def __init__(self, repository_factory: Callable[[Any], StartBatchRepositoryPort]) -> None:
        self._repository_factory = repository_factory

    def start(self, *, connection: Any, workspace_id: str, target_count: int) -> str:
        if not isinstance(target_count, int) or isinstance(target_count, bool) or target_count <= 0:
            raise ValueError("target_completed_videos must be a positive integer")
        batch_id = str(uuid.uuid4())
        self._repository_factory(connection).insert(
            workspace_id=workspace_id, batch_id=batch_id, target_count=target_count,
        )
        return batch_id
