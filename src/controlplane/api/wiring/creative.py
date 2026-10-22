from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ D (creative).
GIẢ ĐỊNH: capacities trả None (chưa có nguồn snapshot hạn mức, resolver coi là không rõ);
intent_policy bảo thủ (snapshot_committed False, fallback_allowed_after_snapshot False);
units 1; desktop_online luôn True vì v1 chỉ chạy trên máy này; một workspace mỗi lần dựng."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from controlplane.api.wiring._shared import PooledCostLedger, PooledReservationStore
from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    WiringConfig,
)
from controlplane.application.config_security.capacity_reservation import (
    CapacityReservationBook,
)
from controlplane.application.config_security.fallback_policy import (
    FallbackIntentPolicy,
)
from controlplane.application.config_security.route_resolver import (
    ProviderRouteResolver,
)
from controlplane.application.config_security.routed_invocation import (
    RoutedInvocationService,
)
from controlplane.domain.config_security.route_binding import (
    ProviderRouteRequest,
)
from creative.adapters.fake_ai import FakeAIAdapter, FakeProviderRoute
from creative.adapters.memory import InMemoryUnitOfWork
from creative.adapters.real_ai_invocation import (
    RoutedAIInvocation,
    budget_policy_from_config,
)
from creative.adapters.real_route_executor import (
    InvocationPayloadStore,
    NineRouterExecutor,
    RouteExecutorConfig,
)
from creative.domain.invocation import (
    ProviderRouteDecision as CreativeRouteDecision,
    RouteContractViolation,
    validate_provider_route_request,
)
from creative.persistence.uow import PostgresCreativeUnitOfWork


class RoutedProviderRoute:
    def __init__(
        self,
        resolver: ProviderRouteResolver,
        workspace_id: str,
        units: int,
        ttl_seconds: int,
        clock: Callable[[], datetime],
        desktop_online: Callable[[], bool],
    ) -> None:
        self._resolver = resolver
        self._workspace_id = workspace_id
        self._units = units
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._desktop_online = desktop_online
        self.requests: dict[str, ProviderRouteRequest] = {}

    def resolve(self, request: Mapping[str, Any]) -> CreativeRouteDecision:
        issues = validate_provider_route_request(request)
        if issues:
            raise RouteContractViolation('ProviderRouteRequest', issues)
        req = ProviderRouteRequest(
            ai_role=request['ai_role'],
            job_ref=request['job_ref'],
            snapshot_ref=request['snapshot_ref'],
            config_refs=list(request['config_refs']),
            data_sensitivity=request['data_sensitivity'],
            quality_latency_cost_bounds=dict(request['quality_latency_cost_bounds']),
            allowed_fallbacks=list(request['allowed_fallbacks']),
            health_quota_ref=request.get('health_quota_ref'),
        )
        decision = self._resolver.resolve(
            req,
            self._workspace_id,
            self._clock(),
            self._units,
            self._ttl_seconds,
            self._desktop_online(),
        )
        self.requests[decision.capacity_reservation_ref] = req
        payload: dict[str, Any] = {
            'provider_ref': decision.provider_ref,
            'model_ref': decision.model_ref,
            'account_ref': decision.account_ref,
            'route_revision': decision.route_revision,
            'rationale_codes': list(decision.rationale_codes),
            'fallback_order': list(decision.fallback_order),
            'capacity_reservation_ref': decision.capacity_reservation_ref,
            'credential_acquisition_method': decision.credential_acquisition_method,
            'estimated_cost_class': decision.estimated_cost_class,
        }
        if decision.project_ref is not None:
            payload['project_ref'] = decision.project_ref
        return CreativeRouteDecision.from_payload(payload)

    def request_for(self, ref: str) -> ProviderRouteRequest:
        return self.requests[ref]


def monthly_window(timezone_name: str) -> Callable[[datetime], tuple[datetime, datetime]]:
    tz = ZoneInfo(timezone_name)

    def window(now: datetime) -> tuple[datetime, datetime]:
        local = now.astimezone(tz)
        start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return (start.astimezone(timezone.utc), nxt.astimezone(timezone.utc))

    return window


@dataclass(frozen=True)
class CreativeServices:
    mode: str
    uow_factory: Callable[[], Any]
    route: Any
    ai: Any
    executor: Any
    payload_store: Any


def build_creative_services(manager: Any, config: WiringConfig) -> CreativeServices:
    if config.mode != PROFILE_PRODUCTION:
        route = FakeProviderRoute()
        ai = FakeAIAdapter(route, responses={}, config_revision='test-profile')
        return CreativeServices(config.mode, InMemoryUnitOfWork, route, ai, None, None)

    profile, runtime = config.production_parts()
    a = profile.ai
    rev = f'profile-{profile.revision}'
    clock = lambda: datetime.now(timezone.utc)
    executor_config = RouteExecutorConfig.from_mapping({
        'endpoint': a.route_endpoint,
        'approved_endpoints': [a.route_endpoint],
        'request_timeout_seconds': a.request_timeout_seconds,
        'max_retries': a.retry.max_attempts - 1,
        'backoff_factor': a.retry.backoff_base_seconds,
        'cost_per_request': runtime.route_cost_per_request,
    })
    store = InvocationPayloadStore()
    executor = NineRouterExecutor(executor_config, store, runtime.provider_credentials)
    budget = budget_policy_from_config({
        'monthly_limit': profile.budget.monthly_limit,
        'hard_stop': profile.budget.hard_stop,
        'warn_ratio': profile.budget.warn_at_ratio,
        'currency': profile.budget.currency,
    })
    book = CapacityReservationBook(PooledReservationStore(manager, config.workspace_id))
    resolver = ProviderRouteResolver(runtime.route_catalog, book, lambda domain_key: None, rev)
    service = RoutedInvocationService(
        resolver,
        executor,
        budget,
        PooledCostLedger(manager),
        monthly_window(profile.budget.window_timezone),
        model_ref_for=a.route_model_refs.get,
    )
    route = RoutedProviderRoute(resolver, config.workspace_id, 1, a.reservation_ttl_seconds, clock, lambda: True)
    ai = RoutedAIInvocation(
        service,
        store,
        request_for=route.request_for,
        clock=clock,
        config_revision=rev,
        intent_policy=FallbackIntentPolicy(snapshot_committed=False, fallback_allowed_after_snapshot=False),
        units=1,
        ttl_seconds=a.reservation_ttl_seconds,
        desktop_online=lambda: True,
    )
    uow_factory = partial(PostgresCreativeUnitOfWork, manager, workspace_id=config.workspace_id)
    return CreativeServices('production', uow_factory, route, ai, executor, store)


__all__ = ['CreativeServices', 'RoutedProviderRoute', 'build_creative_services', 'monthly_window']
