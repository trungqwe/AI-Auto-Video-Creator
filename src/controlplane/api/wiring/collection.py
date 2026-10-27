from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ A (source_ingestion).
Đấu nối RealHttpTransport, RealFeedSource, RealMediaFetcher và PostgresSourceIngestionUnitOfWork."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
import socket
from pathlib import Path
from typing import Any

from controlplane.api.wiring.production_profile import (
    FetchPolicyValues,
    PROFILE_PRODUCTION,
    ProductionProfileError,
    WiringConfig,
)
from source_ingestion.adapters.memory import InMemoryUnitOfWork
from source_ingestion.adapters.real_feed_source import RealFeedSource
from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.adapters.real_media_fetch import RealMediaFetcher
from source_ingestion.adapters.secure_fetch import FetchPolicy, SecureFetcher
from source_ingestion.application.plan_cycle import PlanCollectionCycle, plan_collection_cycle_handler
from source_ingestion.application.seed_sources import seed_sources
from source_ingestion.application.source_commands import SourceCommandHandler
from source_ingestion.domain.source import SourcePolicy
from source_ingestion.persistence.unit_of_work import (
    PostgresSourceIngestionUnitOfWork,
)
from source_ingestion.worker.production_deps import CollectDepsFactory, collect_source_activity_handler

FEED_KINDS = ('rss_feed', 'atom_feed')


def system_dns_resolver(host: str) -> tuple[str, ...]:
    try:
        return tuple(sorted({info[4][0] for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}))
    except OSError:
        return ()


def _policy(values: FetchPolicyValues, revision: int) -> FetchPolicy:
    return FetchPolicy(
        revision=f'profile-{revision}',
        max_redirects=values.max_redirects,
        max_body_bytes=values.max_body_bytes,
        allowed_media_types=frozenset(values.content_types),
        timeout_seconds=values.timeout_seconds,
    )


@dataclass(frozen=True)
class CollectionServices:
    mode: str
    uow_factory: Callable[[], Any]
    source_adapters: Mapping[str, Any]
    media_fetcher: Any
    transport: Any
    workspace_id: str = ''
    fetcher: Any = None
    feed_policy: Any = None
    article_policy: Any = None


def build_collection_services(manager: Any, config: WiringConfig) -> CollectionServices:
    if config.mode != PROFILE_PRODUCTION:
        return CollectionServices(config.mode, InMemoryUnitOfWork, {}, None, None)

    profile, runtime = config.production_parts()
    c = profile.collection
    transport = RealHttpTransport(user_agent=c.user_agent)
    fetcher = SecureFetcher(transport, system_dns_resolver)
    feed = _policy(c.feed, profile.revision)
    article = _policy(c.article, profile.revision)
    image = _policy(c.image, profile.revision)

    kinds = [k for k in c.source_kinds if k in FEED_KINDS]
    if not kinds:
        raise ProductionProfileError('collection.source_kind', 'invalid parameter')

    source_adapters = {
        k: RealFeedSource(fetcher, source_kind=k, feed_policy=feed, article_policy=article)
        for k in kinds
    }
    media_fetcher = RealMediaFetcher(
        fetcher,
        image_policy=image,
        staging_root=runtime.staging_root / 'media',
    )
    uow_factory = partial(PostgresSourceIngestionUnitOfWork, manager, workspace_id=config.workspace_id)
    return CollectionServices('production', uow_factory, source_adapters, media_fetcher, transport, config.workspace_id, fetcher, feed, article)


def collection_activity_handlers(
    services: CollectionServices, *, grants: Any, tier_order: Sequence[str], clock: Callable[[], Any]
) -> dict[str, Any]:
    if services.mode != PROFILE_PRODUCTION:
        raise ProductionProfileError('collection.mode', 'not a production profile')
    plan = PlanCollectionCycle(
        uow_factory=services.uow_factory,
        workspace_id=services.workspace_id,
        tier_order=tier_order,
        clock=clock,
    )
    factory = CollectDepsFactory(
        uow_factory=services.uow_factory,
        grants=grants,
        workspace_id=services.workspace_id,
        fetcher=services.fetcher,
        feed_policy=services.feed_policy,
        article_policy=services.article_policy,
    )
    return {
        'PlanCollectionCycle': plan_collection_cycle_handler(plan, clock),
        'CollectSource': collect_source_activity_handler(factory, clock),
    }


def seed_collection_sources(
    manager: Any,
    *,
    workspace_id: str,
    profile: Any,
    sources_path: Path,
    recovery_epoch: str,
    resolver: Callable[[str], Any] | None = None,
) -> Any:
    policy = SourcePolicy(
        policy_revision='profile-' + str(profile.revision),
        source_kinds=frozenset(profile.collection.source_kinds),
        tiers=frozenset(profile.parameters['collection.tiers']),
        admin_metadata_keys=frozenset(),
    )
    handler = SourceCommandHandler(
        uow=PostgresSourceIngestionUnitOfWork(manager, workspace_id=workspace_id),
        policy_provider=lambda _workspace_id: policy,
        resolver=resolver or system_dns_resolver,
        recovery_epoch=recovery_epoch,
    )
    return seed_sources(handler, sources_path, workspace_id=workspace_id)


__all__ = ['CollectionServices', 'build_collection_services', 'collection_activity_handlers', 'seed_collection_sources', 'system_dns_resolver']
