"""J-18: RoutedInvocationService (CT-AI-ROUTE-002, CT-COST-001, TST-INT-INV-004, TST-SEC-INV-012).

coveredIds: CT-AI-ROUTE-002, CT-COST-001, TST-INT-INV-004, TST-SEC-INV-012
"""
from __future__ import annotations

import dataclasses
import inspect
import itertools
import json
import pathlib
import re
import socket
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from controlplane.application.config_security import routed_invocation
from controlplane.application.config_security.capacity_reservation import CapacityReservationBook
from controlplane.application.config_security.fallback_policy import FallbackIntentPolicy
from controlplane.application.config_security.route_resolver import ProviderRouteResolver, RouteCandidate
from controlplane.application.config_security.routed_invocation import (
    BUDGET_BLOCKED,
    SKIPPED_AI_NOT_REQUIRED,
    SUCCEEDED,
    WAITING_PROVIDER,
    ExecutionResult,
    ProviderExecutorPort,
    RoutedInvocationService,
)
from controlplane.config.models import RateLimitError
from controlplane.domain.config_security.capacity_snapshot import quota_domain_key
from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.incremental_cost import BudgetPolicy, IncrementalCostRecord
from controlplane.domain.config_security.route_binding import ProviderRouteRequest
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.secret_redaction import find_canaries

FIXTURE = pathlib.Path(__file__).resolve().parents[2] / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
NOW = datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
WS = 'ws-1'
ROLE = 'script_generation'
JOB = '00000000-0000-4000-8000-000000000100'
CFG = 'cfg-rev-1'
PRM = 'prm-rev-1'
CANARY = 'sk-CANARY0123456789abcdef'


@pytest.fixture(autouse=True)
def network_calls(monkeypatch):
    calls: list = []

    def _blocked(*args, **kwargs):
        calls.append(args)
        raise RuntimeError('network is blocked in J-18 tests')

    monkeypatch.setattr(socket, 'create_connection', _blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', _blocked)
    yield calls
    assert calls == []


def _account(account_id: str) -> ExternalAccount:
    return ExternalAccount(
        external_account_id=account_id, workspace_id=WS, provider='gemini', account_label='label-' + account_id,
        status=ExternalAccountStatus.ENABLED, project_ref='proj-a', capabilities=frozenset({ROLE}), credential_version=1,
        credential_updated_at=None, credential_expires_at=None, quota_observation_ref=None, health=None, revision=1,
    )


def _candidate(ref: str) -> RouteCandidate:
    return RouteCandidate(
        candidate_ref=ref, provider_ref=ref, model_ref='model-' + ref, account=_account('acc-' + ref),
        quota_domain_key=quota_domain_key('gemini', 'proj-a', 'model-' + ref), cost_class='low',
        max_data_sensitivity='confidential', roles=frozenset({ROLE}), local=False,
    )


def _request(**overrides) -> ProviderRouteRequest:
    payload = dict(json.loads(FIXTURE.read_text(encoding='utf-8'))['entities']['ProviderRouteRequest']['valid'][0])
    payload.update(overrides)
    return ProviderRouteRequest(**payload)


class FakeCatalog:
    def __init__(self, items) -> None:
        self.items = tuple(items)

    def candidates(self, workspace_id: str, ai_role: str):
        return self.items


class SpyBook(CapacityReservationBook):
    def __init__(self) -> None:
        self.calls: list = []
        counter = itertools.count(1)
        super().__init__(ref_factory=lambda: f'res-{next(counter)}')

    def reserve(self, *args, **kwargs):
        self.calls.append(args)
        return super().reserve(*args, **kwargs)


class FakeLedger:
    def __init__(self, seed=()) -> None:
        self.items = list(seed)
        self.appended: list = []

    def records(self, workspace_id, window_start, window_end):
        return tuple(self.items)

    def append(self, workspace_id, record) -> None:
        self.items.append(record)
        self.appended.append((workspace_id, record))


class ScriptedExecutor:
    def __init__(self, script=None) -> None:
        self.script = {key: list(value) for key, value in (script or {}).items()}
        self.calls: list = []

    def execute(self, decision, candidate_ref, request_payload_ref, credential_method):
        self.calls.append((candidate_ref, request_payload_ref, credential_method, decision))
        queue = self.script.get(candidate_ref)
        if queue:
            item = queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return ExecutionResult(ok=True, output_ref='out-' + candidate_ref, usage_cost=Decimal('0'), error=None)


def _fail(error: BaseException, cost: Decimal = Decimal('0')) -> ExecutionResult:
    return ExecutionResult(ok=False, output_ref=None, usage_cost=cost, error=error)


def _window(now):
    return (datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc))


def _cost_record(amount: Decimal) -> IncrementalCostRecord:
    return IncrementalCostRecord(
        record_id='seed-1', provider='prov', service='svc', operation_ref='op-seed-1', job_ref=None, batch_ref=None,
        quantity=Decimal('1'), unit='request', estimated_cost=amount, actual_cost=amount, currency='USD', source='seed',
        occurred_at='2026-10-10T00:00:00+00:00', cost_category='api_paid',
    )


def _service(candidates=('c1', 'c2'), executor=None, policy=None, ledger=None, model_ref_for=None):
    book = SpyBook()
    resolver = ProviderRouteResolver(FakeCatalog([_candidate(ref) for ref in candidates]), book, lambda key: None, 'route-v1')
    executor = executor or ScriptedExecutor()
    ledger = ledger or FakeLedger()
    policy = policy or BudgetPolicy(monthly_limit=None)
    service = RoutedInvocationService(resolver, executor, policy, ledger, _window, model_ref_for=model_ref_for)
    return service, executor, ledger, book


def _invoke(service, request=None, ai_required=True, intent=None, cfg=CFG, prm=PRM, desktop_online=True):
    return service.invoke(
        request=request or _request(allowed_fallbacks=['c2']), workspace_id=WS, now=NOW, units=1, ttl_seconds=60,
        desktop_online=desktop_online, intent_policy=intent or FallbackIntentPolicy(False, False), ai_required=ai_required,
        config_revision_id=cfg, prompt_revision_id=prm, local_candidate_refs=frozenset(),
    )


def test_module_docstring_declares_covered_ids():
    assert 'coveredIds: CT-AI-ROUTE-002, CT-COST-001, TST-INT-INV-004, TST-SEC-INV-012' in (__doc__ or '')


def test_source_does_not_import_router_or_adapter():
    text = pathlib.Path(routed_invocation.__file__).read_text(encoding='utf-8')
    assert re.search(r'config\.(router|adapter)', text) is None


def test_executor_port_takes_no_secret():
    params = list(inspect.signature(ProviderExecutorPort.execute).parameters)
    assert params == ['self', 'decision', 'candidate_ref', 'request_payload_ref', 'credential_method']


@pytest.mark.parametrize(('cfg', 'prm'), [('', PRM), (CFG, ''), ('   ', PRM), (CFG, '  '), (None, PRM), (CFG, None)])
def test_missing_revision_raises_value_error(cfg, prm):
    service, executor, ledger, book = _service()
    with pytest.raises(ValueError):
        _invoke(service, cfg=cfg, prm=prm)
    assert executor.calls == [] and ledger.appended == [] and book.calls == []


def test_success_record_carries_revisions_and_credential_method_only():
    service, executor, ledger, book = _service()
    record = _invoke(service)
    assert record.outcome == SUCCEEDED and record.output_ref == 'out-c1'
    assert (record.config_revision_id, record.prompt_revision_id) == (CFG, PRM)
    assert record.route_decision.model_ref == 'model-c1'
    assert len(record.attempts) == 1
    attempt = record.attempts[0]
    assert (attempt.candidate_ref, attempt.model_ref, attempt.config_revision_id, attempt.prompt_revision_id, attempt.outcome) == ('c1', 'model-c1', CFG, PRM, SUCCEEDED)
    candidate_ref, payload_ref, method, decision = executor.calls[0]
    assert (candidate_ref, payload_ref, method) == ('c1', _request().snapshot_ref, 'secret_broker_handle')
    assert decision is record.route_decision
    assert ledger.appended == []


def _limit_policy(hard_stop: bool, limit: str = '10') -> BudgetPolicy:
    return BudgetPolicy(monthly_limit=Decimal(limit), hard_stop=hard_stop)


def test_hard_stop_over_budget_blocks_before_resolve_and_execute():
    service, executor, _, book = _service(policy=_limit_policy(True), ledger=FakeLedger([_cost_record(Decimal('12'))]))
    record = _invoke(service)
    assert record.outcome == BUDGET_BLOCKED and record.cost_status == 'EXCEEDED'
    assert executor.calls == [] and book.calls == []
    assert record.attempts == () and record.route_decision is None
    assert (record.config_revision_id, record.prompt_revision_id) == (CFG, PRM)


def test_soft_limit_over_budget_still_runs_with_warning_status():
    service, executor, _, _ = _service(policy=_limit_policy(False), ledger=FakeLedger([_cost_record(Decimal('12'))]))
    record = _invoke(service)
    assert record.outcome == SUCCEEDED and record.cost_status == 'EXCEEDED'
    assert [call[0] for call in executor.calls] == ['c1']


def test_warn_80_only_labels_cost_status_even_with_hard_stop():
    service, executor, _, _ = _service(policy=_limit_policy(True), ledger=FakeLedger([_cost_record(Decimal('8'))]))
    record = _invoke(service)
    assert record.outcome == SUCCEEDED and record.cost_status == 'WARN_80'
    assert len(executor.calls) == 1


def test_hard_stop_without_configured_limit_never_blocks():
    service, executor, _, _ = _service(policy=BudgetPolicy(monthly_limit=None, hard_stop=True), ledger=FakeLedger([_cost_record(Decimal('1000'))]))
    record = _invoke(service)
    assert record.outcome == SUCCEEDED and record.cost_status == 'NO_LIMIT'
    assert len(executor.calls) == 1


def test_under_budget_status_is_ok():
    service, _, _, _ = _service(policy=_limit_policy(True))
    assert _invoke(service).cost_status == 'OK'


def test_positive_usage_cost_is_appended_to_ledger_even_on_failure():
    paid = ExecutionResult(ok=True, output_ref='out-paid', usage_cost=Decimal('0.25'), error=None)
    service, _, ledger, _ = _service(executor=ScriptedExecutor({'c1': [paid]}))
    assert _invoke(service).outcome == SUCCEEDED
    assert len(ledger.appended) == 1
    workspace_id, cost = ledger.appended[0]
    assert workspace_id == WS and cost.actual_cost == Decimal('0.25') and cost.estimated_cost == Decimal('0.25')
    assert (cost.job_ref, cost.currency, cost.cost_category) == (JOB, 'USD', 'api_paid')
    failed = _fail(RuntimeError('boom'), Decimal('0.10'))
    service, _, ledger, _ = _service(executor=ScriptedExecutor({'c1': [failed]}))
    _invoke(service)
    assert [cost.actual_cost for _, cost in ledger.appended] == [Decimal('0.10')]


def test_budget_is_rechecked_before_each_switch_attempt():
    first = _fail(RateLimitError(), Decimal('11'))
    service, executor, ledger, _ = _service(policy=_limit_policy(True), executor=ScriptedExecutor({'c1': [first]}))
    record = _invoke(service)
    assert [call[0] for call in executor.calls] == ['c1']
    assert record.outcome == BUDGET_BLOCKED and record.cost_status == 'EXCEEDED'
    assert [attempt.candidate_ref for attempt in record.attempts] == ['c1']
    assert len(ledger.appended) == 1


def test_rate_limit_then_switch_succeeds_with_two_attempts_carrying_revisions():
    service, executor, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(RateLimitError())]}), model_ref_for={'c2': 'model-c2'}.get)
    record = _invoke(service)
    assert record.outcome == SUCCEEDED and record.output_ref == 'out-c2'
    assert [(a.candidate_ref, a.model_ref, a.outcome) for a in record.attempts] == [('c1', 'model-c1', 'RATE_LIMIT'), ('c2', 'model-c2', SUCCEEDED)]
    assert all((a.config_revision_id, a.prompt_revision_id) == (CFG, PRM) for a in record.attempts)
    assert [call[0] for call in executor.calls] == ['c1', 'c2']


def test_switch_model_ref_falls_back_to_candidate_ref_without_lookup():
    service, _, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(RateLimitError())]}))
    assert _invoke(service).attempts[1].model_ref == 'c2'


@pytest.mark.parametrize(('error', 'attempts'), [(RateLimitError(), 2), (TimeoutError('t'), 2), (RuntimeError('boom'), 1)])
def test_every_candidate_failing_returns_waiting_provider_without_raising(error, attempts):
    service, _, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(error)], 'c2': [_fail(error)]}))
    record = _invoke(service)
    assert record.outcome == WAITING_PROVIDER and record.output_ref is None
    assert len(record.attempts) == attempts
    assert all(a.outcome != SUCCEEDED for a in record.attempts)
    assert all((a.config_revision_id, a.prompt_revision_id) == (CFG, PRM) for a in record.attempts)


def test_executor_exception_is_recorded_not_raised():
    service, _, _, _ = _service(executor=ScriptedExecutor({'c1': [RuntimeError('boom')]}))
    record = _invoke(service)
    assert record.outcome == WAITING_PROVIDER
    assert record.attempts[0].outcome == 'UNKNOWN'


def test_fallback_never_leaves_allowed_list():
    service, executor, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(RateLimitError())]}))
    record = _invoke(service, request=_request(allowed_fallbacks=[]))
    assert record.outcome == WAITING_PROVIDER
    assert [call[0] for call in executor.calls] == ['c1']


def test_ai_not_required_skips_on_provider_failure():
    service, _, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(RuntimeError('boom'))]}))
    record = _invoke(service, ai_required=False)
    assert record.outcome == SKIPPED_AI_NOT_REQUIRED
    assert len(record.attempts) == 1


def test_snapshot_committed_without_permission_requires_new_output_revision():
    service, executor, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(RateLimitError())]}))
    record = _invoke(service, intent=FallbackIntentPolicy(True, False))
    assert record.outcome == 'NEW_OUTPUT_REVISION_REQUIRED'
    assert [call[0] for call in executor.calls] == ['c1']


def test_snapshot_committed_with_permission_still_switches():
    service, _, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(RateLimitError())]}))
    record = _invoke(service, intent=FallbackIntentPolicy(True, True))
    assert record.outcome == SUCCEEDED and len(record.attempts) == 2


@pytest.mark.parametrize(('ai_required', 'outcome'), [(True, WAITING_PROVIDER), (False, SKIPPED_AI_NOT_REQUIRED)])
def test_no_eligible_route_never_raises(ai_required, outcome):
    service, executor, _, _ = _service(candidates=())
    record = _invoke(service, ai_required=ai_required)
    assert record.outcome == outcome and record.route_decision is None and record.attempts == ()
    assert executor.calls == []


@pytest.mark.parametrize('error', [RateLimitError(429, f'quota exceeded {CANARY}'), RuntimeError(f'boom {CANARY}')])
def test_canary_in_executor_result_error_is_redacted_everywhere(error):
    service, _, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(error)], 'c2': [_fail(error)]}))
    record = _invoke(service)
    assert record.outcome == WAITING_PROVIDER
    assert find_canaries([CANARY], record, repr(record), str(record), dataclasses.asdict(record)) == []
    assert record.attempts
    for attempt in record.attempts:
        assert attempt.error is not None and type(error).__name__ in attempt.error and '[REDACTED]' in attempt.error


def test_canary_in_raised_executor_exception_is_redacted():
    error = RuntimeError(f'leak {CANARY}')
    service, _, _, _ = _service(executor=ScriptedExecutor({'c1': [error]}))
    record = _invoke(service)
    assert find_canaries([CANARY], record, repr(record), dataclasses.asdict(record)) == []


def test_network_primitives_are_blocked_and_unused(network_calls):
    with pytest.raises(RuntimeError):
        socket.create_connection(('127.0.0.1', 9))
    with pytest.raises(RuntimeError):
        socket.getaddrinfo('localhost', 9)
    assert len(network_calls) == 2
    network_calls.clear()
    service, _, _, _ = _service(executor=ScriptedExecutor({'c1': [_fail(RateLimitError())]}))
    assert _invoke(service).outcome == SUCCEEDED
    assert network_calls == []
