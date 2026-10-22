from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ A (source_ingestion).
Đấu nối RealHttpTransport, RealFeedSource, RealMediaFetcher và PostgresSourceIngestionUnitOfWork."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
import socket
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
from source_ingestion.persistence.unit_of_work import (
    PostgresSourceIngestionUnitOfWork,
)

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
    return CollectionServices('production', uow_factory, source_adapters, media_fetcher, transport)


__all__ = ['CollectionServices', 'build_collection_services', 'system_dns_resolver']
