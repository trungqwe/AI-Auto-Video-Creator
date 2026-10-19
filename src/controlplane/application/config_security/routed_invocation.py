"""J-18: RoutedInvocationService (CT-AI-ROUTE-002, CT-COST-001, TST-INT-INV-004, TST-SEC-INV-012).

Ghép resolve, kiểm ngân sách, execute và fallback có kiểm soát. Không I/O mạng, không đọc đồng hồ; executor chỉ nhận phương thức lấy credential, không bao giờ nhận secret.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from controlplane.application.config_security.fallback_policy import (
    CONTINUE_WITHOUT_AI,
    NEW_OUTPUT_REVISION_REQUIRED,
    SWITCH,
    FallbackIntentPolicy,
    classify_failure,
    decide_fallback,
)
from controlplane.application.config_security.route_resolver import NoRouteError, ProviderRouteResolver
from controlplane.domain.config_security.incremental_cost import (
    BudgetPolicy,
    BudgetStatus,
    IncrementalCostRecord,
    evaluate_budget,
    should_block,
)
from controlplane.domain.config_security.route_binding import ProviderRouteDecision, ProviderRouteRequest
from controlplane.infrastructure.security.secret_redaction import redact_value

SUCCEEDED = 'SUCCEEDED'
BUDGET_BLOCKED = 'BUDGET_BLOCKED'
WAITING_PROVIDER = 'WAITING_PROVIDER'
SKIPPED_AI_NOT_REQUIRED = 'SKIPPED_AI_NOT_REQUIRED'
COST_CATEGORY = 'api_paid'
COST_SOURCE = 'routed_invocation'
_OUTCOME_BY_ACTION = {
    CONTINUE_WITHOUT_AI: SKIPPED_AI_NOT_REQUIRED,
    NEW_OUTPUT_REVISION_REQUIRED: NEW_OUTPUT_REVISION_REQUIRED,
}


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    output_ref: str | None
    usage_cost: Decimal
    error: BaseException | None = None


@dataclass(frozen=True)
class AttemptRecord:
    candidate_ref: str
    model_ref: str
    config_revision_id: str
    prompt_revision_id: str
    outcome: str
    error: str | None = None


@dataclass(frozen=True)
class InvocationRecord:
    route_decision: ProviderRouteDecision | None
    attempts: tuple[AttemptRecord, ...]
    outcome: str
    config_revision_id: str
    prompt_revision_id: str
    cost_status: str
    output_ref: str | None = None


class ProviderExecutorPort(Protocol):
    def execute(self, decision: ProviderRouteDecision, candidate_ref: str, request_payload_ref: str, credential_method: str) -> ExecutionResult: ...


class CostLedgerPort(Protocol):
    def records(self, workspace_id: str, window_start: datetime, window_end: datetime) -> Iterable[IncrementalCostRecord]: ...
    def append(self, workspace_id: str, record: IncrementalCostRecord) -> None: ...


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _safe_text(value: str | None) -> str | None:
    return None if value is None else redact_value(value)


def _error_text(error: BaseException | None) -> str:
    name = type(error).__name__
    try:
        return redact_value(f'{name}: {error}')
    except Exception:
        return name


class RoutedInvocationService:
    def __init__(
        self,
        resolver: ProviderRouteResolver,
        executor: ProviderExecutorPort,
        budget_policy: BudgetPolicy,
        cost_ledger: CostLedgerPort,
        window_provider: Callable[[datetime], tuple[datetime, datetime]],
        *,
        model_ref_for: Callable[[str], str | None] | None = None,
    ) -> None:
        if not isinstance(budget_policy, BudgetPolicy):
            raise TypeError('budget_policy must be a BudgetPolicy')
        self._resolver = resolver
        self._executor = executor
        self._budget_policy = budget_policy
        self._cost_ledger = cost_ledger
        self._window_provider = window_provider
        self._model_ref_for = model_ref_for

    def invoke(
        self,
        request: ProviderRouteRequest,
        workspace_id: str,
        now: datetime,
        units: int,
        ttl_seconds: int,
        desktop_online: bool,
        intent_policy: FallbackIntentPolicy,
        ai_required: bool,
        config_revision_id: str,
        prompt_revision_id: str,
        local_candidate_refs: frozenset[str],
    ) -> InvocationRecord:
        _require_text('config_revision_id', config_revision_id)
        _require_text('prompt_revision_id', prompt_revision_id)
        if not isinstance(intent_policy, FallbackIntentPolicy):
            raise TypeError('intent_policy must be a FallbackIntentPolicy')
        local_refs = frozenset(local_candidate_refs)
        decision: ProviderRouteDecision | None = None
        candidate_ref = ''
        model_ref = ''
        attempts: list[AttemptRecord] = []
        attempted: list[str] = []

        def finish(outcome: str, status: BudgetStatus, output_ref: str | None = None) -> InvocationRecord:
            return InvocationRecord(
                decision, tuple(attempts), outcome, config_revision_id, prompt_revision_id, status.level.value, _safe_text(output_ref)
            )

        while True:
            status = self._budget_status(workspace_id, now)
            if should_block(status, self._budget_policy, Decimal('0')):
                return finish(BUDGET_BLOCKED, status)
            if decision is None:
                try:
                    decision = self._resolver.resolve(request, workspace_id, now, units, ttl_seconds, desktop_online)
                except NoRouteError:
                    return finish(WAITING_PROVIDER if ai_required else SKIPPED_AI_NOT_REQUIRED, status)
                candidate_ref = decision.provider_ref
                model_ref = decision.model_ref
            result = self._execute(decision, candidate_ref, request.snapshot_ref)
            attempted.append(candidate_ref)
            self._charge(workspace_id, request, decision, model_ref, now, units, len(attempted), result)
            if result.ok:
                attempts.append(AttemptRecord(candidate_ref, model_ref, config_revision_id, prompt_revision_id, SUCCEEDED))
                return finish(SUCCEEDED, status, result.output_ref)
            failure = classify_failure(result.error)
            attempts.append(
                AttemptRecord(candidate_ref, model_ref, config_revision_id, prompt_revision_id, failure, _error_text(result.error))
            )
            fallback = decide_fallback(
                decision, failure, tuple(attempted), intent_policy, desktop_online, local_refs, ai_required
            )
            if fallback.action != SWITCH:
                return finish(_OUTCOME_BY_ACTION.get(fallback.action, WAITING_PROVIDER), status)
            candidate_ref = fallback.next_candidate_ref
            looked_up = self._model_ref_for(candidate_ref) if self._model_ref_for is not None else None
            model_ref = looked_up or candidate_ref

    def _budget_status(self, workspace_id: str, now: datetime) -> BudgetStatus:
        start, end = self._window_provider(now)
        records = self._cost_ledger.records(workspace_id, start, end)
        return evaluate_budget(records, self._budget_policy, start, end, now)

    def _execute(self, decision: ProviderRouteDecision, candidate_ref: str, payload_ref: str) -> ExecutionResult:
        try:
            result = self._executor.execute(decision, candidate_ref, payload_ref, decision.credential_acquisition_method)
        except Exception as exc:
            return ExecutionResult(False, None, Decimal('0'), exc)
        if not isinstance(result, ExecutionResult):
            return ExecutionResult(False, None, Decimal('0'), TypeError('executor must return ExecutionResult'))
        if not result.ok and result.error is None:
            return ExecutionResult(False, None, result.usage_cost, RuntimeError('EXECUTION_FAILED'))
        return result

    def _charge(
        self,
        workspace_id: str,
        request: ProviderRouteRequest,
        decision: ProviderRouteDecision,
        model_ref: str,
        now: datetime,
        units: int,
        number: int,
        result: ExecutionResult,
    ) -> None:
        cost = result.usage_cost
        if not isinstance(cost, Decimal) or not cost.is_finite() or cost <= 0:
            return
        operation_ref = f'{request.job_ref}:{request.ai_role}:{number}'
        record = IncrementalCostRecord(
            record_id=operation_ref,
            provider=decision.provider_ref,
            service=model_ref,
            operation_ref=operation_ref,
            job_ref=request.job_ref,
            batch_ref=None,
            quantity=Decimal(units),
            unit='request',
            estimated_cost=cost,
            actual_cost=cost,
            currency=self._budget_policy.currency,
            source=COST_SOURCE,
            occurred_at=now.isoformat(),
            cost_category=COST_CATEGORY,
        )
        self._cost_ledger.append(workspace_id, record)
