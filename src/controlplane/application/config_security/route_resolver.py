"""J-13: ProviderRouteResolver (CT-AI-ROUTE-001, CT-CAP-001, TST-SEC-INV-020; D8-J-04, D8-J-12, D8-J-13).

Application service thuần: không I/O, không đọc đồng hồ; chọn route từ catalog do caller cấp, không bao giờ chọn ref ngoài catalog.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from controlplane.application.config_security.capacity_reservation import (
    CapacityReservationBook,
    CapacityUnavailableError,
)
from controlplane.domain.config_security.capacity_snapshot import DomainCapacity
from controlplane.domain.config_security.external_account import ExternalAccount, account_allows_role
from controlplane.domain.config_security.route_binding import ProviderRouteDecision, ProviderRouteRequest
from controlplane.domain.config_security.status_graph import ExternalAccountStatus

NO_ELIGIBLE_ROUTE = 'NO_ELIGIBLE_ROUTE'
COST_ORDER = ('free', 'low', 'medium', 'high')
SENSITIVITY_ORDER = ('public', 'internal', 'confidential')
ROLE_OK = 'ROLE_OK'
QUOTA_AVAILABLE = 'QUOTA_AVAILABLE'
QUOTA_UNCERTAIN = 'QUOTA_UNCERTAIN'
COST_WITHIN_BOUND = 'COST_WITHIN_BOUND'
CREDENTIAL_METHOD = 'secret_broker_handle'
HEALTH_UNAVAILABLE = 'unavailable'

ACCOUNT_NOT_ELIGIBLE = 'ACCOUNT_NOT_ELIGIBLE'
SENSITIVITY_EXCEEDED = 'SENSITIVITY_EXCEEDED'
COST_EXCEEDS_BOUND = 'COST_EXCEEDS_BOUND'
LOCAL_OFFLINE = 'LOCAL_OFFLINE'
CAPACITY_UNAVAILABLE = 'CAPACITY_UNAVAILABLE'


class NoRouteError(Exception):
    def __init__(self, code: str, rationale_codes: Sequence[str] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.rationale_codes = tuple(rationale_codes)


@dataclass(frozen=True)
class RouteCandidate:
    candidate_ref: str
    provider_ref: str
    model_ref: str
    account: ExternalAccount
    quota_domain_key: str
    cost_class: str
    max_data_sensitivity: str
    roles: frozenset[str]
    local: bool


class RouteCatalogPort(Protocol):
    def candidates(self, workspace_id: str, ai_role: str) -> Sequence[RouteCandidate]: ...


def _require_text(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _require_positive_int(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f'{name} must be a positive integer')


def _require_aware_now(now: datetime) -> None:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must be a timezone-aware datetime')


def _rank(order: Sequence[str], value: Any) -> int | None:
    if isinstance(value, str) and value in order:
        return order.index(value)
    return None


def _bound_rank(bounds: Any) -> int | None:
    raw = bounds.get('max_cost_class') if isinstance(bounds, dict) else None
    if raw is None:
        return 0
    return _rank(COST_ORDER, raw)


def _exclusion_reason(
    candidate: RouteCandidate,
    workspace_id: str,
    ai_role: str,
    sensitivity_rank: int | None,
    bound_rank: int | None,
    desktop_online: bool,
    capacity: DomainCapacity | None,
) -> str | None:
    if candidate.account.status is not ExternalAccountStatus.ENABLED or not account_allows_role(
        candidate.account, workspace_id, ai_role
    ):
        return ACCOUNT_NOT_ELIGIBLE
    cand_sens_rank = _rank(SENSITIVITY_ORDER, candidate.max_data_sensitivity)
    if sensitivity_rank is None or cand_sens_rank is None or sensitivity_rank > cand_sens_rank:
        return SENSITIVITY_EXCEEDED
    cand_cost_rank = _rank(COST_ORDER, candidate.cost_class)
    if bound_rank is None or cand_cost_rank is None or cand_cost_rank > bound_rank:
        return COST_EXCEEDS_BOUND
    if candidate.local and desktop_online is not True:
        return LOCAL_OFFLINE
    if capacity is not None and (
        (isinstance(capacity.health, str) and capacity.health.strip().casefold() == HEALTH_UNAVAILABLE)
        or capacity.remaining_requests == 0
    ):
        return CAPACITY_UNAVAILABLE
    return None


class ProviderRouteResolver:
    def __init__(
        self,
        catalog: RouteCatalogPort,
        reservations: CapacityReservationBook,
        capacities: Callable[[str], DomainCapacity | None],
        route_revision: str,
    ) -> None:
        _require_text('route_revision', route_revision)
        self._catalog = catalog
        self._reservations = reservations
        self._capacities = capacities
        self._route_revision = route_revision

    def resolve(
        self,
        request: ProviderRouteRequest,
        workspace_id: str,
        now: datetime,
        units: int,
        ttl_seconds: int,
        desktop_online: bool,
    ) -> ProviderRouteDecision:
        """Giải quyết route provider độc lập nội dung model (INV-020); reservation chỉ là hint."""
        if not isinstance(request, ProviderRouteRequest):
            raise TypeError('request must be a ProviderRouteRequest')
        _require_text('workspace_id', workspace_id)
        _require_text('ai_role', request.ai_role)
        _require_text('job_ref', request.job_ref)
        _require_aware_now(now)
        _require_positive_int('units', units)
        _require_positive_int('ttl_seconds', ttl_seconds)

        sensitivity_rank = _rank(SENSITIVITY_ORDER, request.data_sensitivity)
        bound_rank = _bound_rank(request.quality_latency_cost_bounds)
        reasons: dict[str, None] = {}
        eligible: list[tuple[RouteCandidate, DomainCapacity | None]] = []

        for candidate in sorted(self._catalog.candidates(workspace_id, request.ai_role), key=lambda item: item.candidate_ref):
            capacity = self._capacities(candidate.quota_domain_key)
            reason = _exclusion_reason(
                candidate, workspace_id, request.ai_role, sensitivity_rank, bound_rank, desktop_online, capacity
            )
            if reason:
                reasons[reason] = None
                continue
            eligible.append((candidate, capacity))

        eligible.sort(key=lambda pair: (_rank(COST_ORDER, pair[0].cost_class), pair[0].candidate_ref))

        operation_key = f'{request.job_ref}:{request.ai_role}'
        chosen = None
        reservation = None
        failed: set[str] = set()
        for candidate, capacity in eligible:
            try:
                reservation = self._reservations.reserve(
                    candidate.quota_domain_key, units, ttl_seconds, operation_key, now, capacity
                )
            except CapacityUnavailableError:
                failed.add(candidate.candidate_ref)
                reasons[CAPACITY_UNAVAILABLE] = None
                continue
            chosen = (candidate, capacity)
            break

        if chosen is None:
            raise NoRouteError(NO_ELIGIBLE_ROUTE, tuple(reasons))

        selected, selected_capacity = chosen
        allowed = (
            frozenset(item for item in request.allowed_fallbacks if isinstance(item, str))
            if isinstance(request.allowed_fallbacks, (list, tuple))
            else frozenset()
        )
        fallback_order = [
            c.candidate_ref
            for c, _ in eligible
            if c is not selected and c.candidate_ref not in failed and c.candidate_ref in allowed
        ]

        uncertain = selected_capacity is None or selected_capacity.remaining_requests is None
        rationale_codes = [ROLE_OK, QUOTA_UNCERTAIN if uncertain else QUOTA_AVAILABLE, COST_WITHIN_BOUND]

        return ProviderRouteDecision(
            provider_ref=selected.provider_ref,
            model_ref=selected.model_ref,
            account_ref=selected.account.external_account_id,
            route_revision=self._route_revision,
            rationale_codes=rationale_codes,
            fallback_order=fallback_order,
            capacity_reservation_ref=reservation.reservation_ref,
            credential_acquisition_method=CREDENTIAL_METHOD,
            estimated_cost_class=selected.cost_class,
            project_ref=selected.account.project_ref,
        )
