from __future__ import annotations

"""PW-W1: wiring cho phân hệ B (ingestion).
Đấu nối PostgresIngestionUnitOfWork, ResolveDepsFactory (ResolveCollectedDocument) và PostgresCandidateSelector (AllocateJob).
Không gọi dịch vụ ngoài lúc dựng."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    ProductionProfileError,
    WiringConfig,
)
from ingestion.application.candidate_selector import PostgresCandidateSelector
from ingestion.application.production_deps import ResolveDepsFactory, resolve_activity_handler
from ingestion.infrastructure.memory import InMemoryUnitOfWork
from ingestion.persistence.uow import PostgresIngestionUnitOfWork


@dataclass(frozen=True)
class IngestionServices:
    mode: str
    workspace_id: str
    uow_factory: Callable[[], Any]
    resolve_factory: Any


def build_ingestion_services(manager: Any, config: WiringConfig) -> IngestionServices:
    if config.mode != PROFILE_PRODUCTION:
        return IngestionServices(config.mode, config.workspace_id, InMemoryUnitOfWork, None)
    uow_factory = partial(PostgresIngestionUnitOfWork, manager, workspace_id=config.workspace_id)
    resolve_factory = ResolveDepsFactory(
        uow_factory=uow_factory,
        connection_factory=manager.borrow_connection,
        workspace_id=config.workspace_id,
    )
    return IngestionServices('production', config.workspace_id, uow_factory, resolve_factory)


def ingestion_activity_handlers(services: IngestionServices, clock: Callable[[], Any]) -> dict[str, Any]:
    if services.resolve_factory is None:
        raise ProductionProfileError('ingestion.mode', 'not a production profile')
    return {'ResolveCollectedDocument': resolve_activity_handler(services.resolve_factory, clock)}


def ingestion_candidate_selector(
    services: IngestionServices, *, connection_factory: Callable[[], Any], clock: Callable[[], Any]
) -> PostgresCandidateSelector:
    return PostgresCandidateSelector(
        connection_factory, services.uow_factory, workspace_id=services.workspace_id, clock=clock
    )


__all__ = [
    'IngestionServices',
    'build_ingestion_services',
    'ingestion_activity_handlers',
    'ingestion_candidate_selector',
]
