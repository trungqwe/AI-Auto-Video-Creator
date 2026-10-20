"""ADAPT-D: AIInvocationPort on RoutedInvocationService through 9Router (CT-AI-ROUTE-002, CT-COST-001, BL-CV-04).

HTTP transport is faked by patching urllib.request.urlopen: no real network, no real secret.
"""
from __future__ import annotations

import pytest

from controlplane.config.adapter import (
    DEFAULT_APPROVED_ENDPOINTS,
    ApprovedEndpointRegistry,
    NineRouterHTTPAdapter,
    UnapprovedEndpointError,
)

import io
import json
import pathlib
import socket
import urllib.error
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from controlplane.application.config_security.capacity_reservation import CapacityReservationBook
from controlplane.application.config_security.fallback_policy import FallbackIntentPolicy
from controlplane.application.config_security.route_resolver import ProviderRouteResolver, RouteCandidate
from controlplane.application.config_security.routed_invocation import RoutedInvocationService
from controlplane.domain.config_security.capacity_snapshot import quota_domain_key
from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.incremental_cost import IncrementalCostRecord
from controlplane.domain.config_security.route_binding import ProviderRouteDecision as JRouteDecision
from controlplane.domain.config_security.route_binding import ProviderRouteRequest
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.secret_redaction import find_canaries
from creative.adapters.real_ai_invocation import (
    RoutedAIInvocation,
    WaitingAIInvocationResult,
    budget_policy_from_config,
)
from creative.adapters.real_route_executor import InvocationPayloadStore, NineRouterExecutor, RouteExecutorConfig
from creative.domain.invocation import AIInvocationResult, ProviderRouteDecision
from creative.domain.ref_resolver import ResourceRef
from creative.domain.untrusted import PromptEnvelope, UntrustedText
from creative.ports.ai import AIInvocationPort


ENDPOINT = 'http://127.0.0.1:20128'


def test_registry_from_config_builds_registry_from_config_endpoints() -> None:
    registry = ApprovedEndpointRegistry.from_config([ENDPOINT + '/'])
    assert registry.endpoints == frozenset({ENDPOINT})
    assert registry.config_owned is True
    assert registry.validate(ENDPOINT) == ENDPOINT
    assert registry.is_approved('http://127.0.0.1:9') is False
    with pytest.raises(UnapprovedEndpointError):
        registry.validate('http://evil.example:20128')
    with pytest.raises(UnapprovedEndpointError):
        registry.register('http://127.0.0.1:9')


def test_registry_from_config_fails_closed_on_empty_or_invalid_entries() -> None:
    for bad in ([], [''], ['not-a-url'], ['ftp://127.0.0.1:1']):
        with pytest.raises(UnapprovedEndpointError):
            ApprovedEndpointRegistry.from_config(bad)
    with pytest.raises(UnapprovedEndpointError):
        ApprovedEndpointRegistry.from_config(ENDPOINT)


def test_default_registry_behaviour_is_unchanged() -> None:
    default = ApprovedEndpointRegistry()
    assert default.endpoints == DEFAULT_APPROVED_ENDPOINTS
    assert default.config_owned is False
    assert 'http://mock-9router:8000' in DEFAULT_APPROVED_ENDPOINTS
    with pytest.raises(UnapprovedEndpointError):
        ApprovedEndpointRegistry([ENDPOINT])
    with pytest.raises(UnapprovedEndpointError):
        NineRouterHTTPAdapter(base_url=ENDPOINT)
    with pytest.raises(UnapprovedEndpointError):
        NineRouterHTTPAdapter(base_url='http://localhost:8000', registry=ApprovedEndpointRegistry(['http://localhost:8000']))
    assert NineRouterHTTPAdapter(base_url='http://localhost:8000').base_url == 'http://localhost:8000'


def test_adapter_accepts_only_config_owned_registry_and_binds_its_endpoint() -> None:
    registry = ApprovedEndpointRegistry.from_config([ENDPOINT])
    adapter = NineRouterHTTPAdapter(base_url=ENDPOINT, registry=registry)
    assert adapter.registry is registry
    assert adapter.bound_endpoint == ENDPOINT
    with pytest.raises(UnapprovedEndpointError):
        NineRouterHTTPAdapter(base_url='http://127.0.0.1:20129', registry=registry)



NOW = datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
WS = 'ws-1'
ROLE = 'script_generation'
JOB = 'job-1'
RESERVATION = 'res-external-1'
CANARY = 'sk-CANARY0123456789abcdef'
BUDGET_CONFIG = {'monthly_limit': '50', 'hard_stop': True}
EXECUTOR_CONFIG = {
    'endpoint': ENDPOINT,
    'approved_endpoints': [ENDPOINT],
    'request_timeout_seconds': 5,
    'max_retries': 1,
    'backoff_factor': 0.001,
    'cost_per_request': '0',
}
ENVELOPE = PromptEnvelope(
    prompt_ref=ResourceRef(WS, 'prompt_revision', ROLE, 'prm-1'),
    instructions='Write the script',
    data=(UntrustedText('source text', ResourceRef(WS, 'production_snapshot', 'snap-1', 'fp-1')),),
)
DECISION = ProviderRouteDecision(
    provider_ref='c1', model_ref='model-c1', account_ref='acc-1', route_revision='route-rev-1',
    rationale_codes=('ROLE_OK',), fallback_order=(), capacity_reservation_ref=RESERVATION,
    credential_acquisition_method='secret_broker_handle', estimated_cost_class='free', project_ref='proj-a',
)
REQUEST = ProviderRouteRequest(
    ai_role=ROLE, job_ref=JOB, snapshot_ref='snap-1', config_refs=['prompt:script_generation@prm-1'],
    data_sensitivity='internal', quality_latency_cost_bounds={}, allowed_fallbacks=[],
)



class FakeCatalog:
    def candidates(self, workspace_id, ai_role):
        account = ExternalAccount(
            external_account_id='acc-1', workspace_id=WS, provider='gemini', account_label='label-1',
            status=ExternalAccountStatus.ENABLED, project_ref='proj-a', capabilities=frozenset({ROLE}),
            credential_version=1, credential_updated_at=None, credential_expires_at=None,
            quota_observation_ref=None, health=None, revision=1,
        )
        return (RouteCandidate(
            candidate_ref='c1', provider_ref='c1', model_ref='model-c1', account=account,
            quota_domain_key=quota_domain_key('gemini', 'proj-a', 'model-c1'), cost_class='free',
            max_data_sensitivity='confidential', roles=frozenset({ROLE}), local=False,
        ),)


class FakeLedger:
    def __init__(self, seed=()):
        self.items = list(seed)
        self.appended = []

    def records(self, workspace_id, window_start, window_end):
        return tuple(self.items)

    def append(self, workspace_id, record):
        self.items.append(record)
        self.appended.append((workspace_id, record))


class FakeCredentials:
    def __init__(self):
        self.calls = []

    @contextmanager
    def acquire(self, credential_method, account_ref):
        self.calls.append((credential_method, account_ref))
        yield CANARY


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False



def _ok(text='{"title":"t"}'):
    body = {'choices': [{'message': {'content': text}}], 'usage': {'prompt_tokens': 7, 'completion_tokens': 3}}
    return FakeResponse(json.dumps(body).encode('utf-8'))


def _http_error(code, msg='error'):
    return urllib.error.HTTPError(url=ENDPOINT + '/v1/chat', code=code, msg=msg, hdrs={}, fp=io.BytesIO(b'{}'))


def _window(now):
    return (datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc))


def _cost_record(amount):
    return IncrementalCostRecord(
        record_id='seed-1', provider='prov', service='svc', operation_ref='op-seed-1', job_ref=None, batch_ref=None,
        quantity=Decimal('1'), unit='request', estimated_cost=amount, actual_cost=amount, currency='USD',
        source='seed', occurred_at='2026-10-10T00:00:00+00:00', cost_category='api_paid',
    )


def _build(budget=BUDGET_CONFIG, executor_config=EXECUTOR_CONFIG, ledger=None):
    ledger = ledger if ledger is not None else FakeLedger()
    store = InvocationPayloadStore()
    credentials = FakeCredentials()
    executor = NineRouterExecutor(RouteExecutorConfig.from_mapping(executor_config), store, credentials)
    resolver = ProviderRouteResolver(FakeCatalog(), CapacityReservationBook(), lambda key: None, 'route-rev-1')
    service = RoutedInvocationService(resolver, executor, budget_policy_from_config(budget), ledger, _window)
    ai = RoutedAIInvocation(
        service, store, request_for={RESERVATION: REQUEST}.__getitem__, clock=lambda: NOW,
        config_revision='cfg-rev-1', intent_policy=FallbackIntentPolicy(False, False), units=1, ttl_seconds=300,
        desktop_online=lambda: True,
    )
    return ai, ledger, credentials


@pytest.fixture(autouse=True)
def isolate_network_and_sleep(monkeypatch):
    def blocked(*args, **kwargs):
        raise RuntimeError('real network is blocked in ADAPT-D tests')

    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)
    monkeypatch.setattr('time.sleep', lambda seconds: None)




def test_invoke_succeeded_returns_output_and_redacted_record() -> None:
    ai, ledger, credentials = _build()
    assert isinstance(ai, AIInvocationPort)
    with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
        result = ai.invoke(DECISION, ENVELOPE)
    assert not isinstance(result, WaitingAIInvocationResult)
    record = result.record
    assert record.error is None
    assert result.output.text == '{"title":"t"}'
    assert (record.ai_role, record.provider_ref, record.model_ref, record.account_ref) == (ROLE, 'c1', 'model-c1', 'acc-1')
    assert (record.prompt_revision, record.config_revision, record.route_revision) == ('prm-1', 'cfg-rev-1', 'route-rev-1')
    assert (record.usage.input_tokens, record.usage.output_tokens) == (7, 3)
    assert credentials.calls == [('secret_broker_handle', 'acc-1')]
    headers = {key.lower(): value for key, value in urlopen.call_args[0][0].headers.items()}
    assert headers['authorization'] == 'Bearer ' + CANARY
    assert find_canaries([CANARY], record.to_json(), repr(result)) == []
    assert ledger.appended == []


def test_rate_limit_inside_retry_budget_still_succeeds() -> None:
    ai, _, _ = _build()
    with patch('urllib.request.urlopen', side_effect=[_http_error(429), _ok()]) as urlopen:
        result = ai.invoke(DECISION, ENVELOPE)
    assert result.record.error is None
    assert urlopen.call_count == 2


def test_rate_limit_exhausted_is_retryable_waiting_not_final_error() -> None:
    ai, ledger, _ = _build()
    with patch('urllib.request.urlopen', side_effect=[_http_error(429), _http_error(429)]) as urlopen:
        result = ai.invoke(DECISION, ENVELOPE)
    assert isinstance(result, WaitingAIInvocationResult)
    assert result.retryable is True
    assert result.wait_reason == 'WAITING_PROVIDER'
    assert result.output is None
    assert result.record.error.startswith('waiting_provider:')
    assert urlopen.call_count == 2
    assert ledger.appended == []




def test_hard_stop_blocks_before_any_call_and_is_retryable_waiting() -> None:
    ai, _, credentials = _build(ledger=FakeLedger([_cost_record(Decimal('51'))]))
    with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
        result = ai.invoke(DECISION, ENVELOPE)
    assert isinstance(result, WaitingAIInvocationResult)
    assert result.wait_reason == 'BUDGET_BLOCKED'
    assert result.retryable is True
    assert result.record.error.startswith('budget_blocked:')
    urlopen.assert_not_called()
    assert credentials.calls == []


def test_budget_limit_and_hard_stop_come_from_config() -> None:
    cases = (
        ({'monthly_limit': '50', 'hard_stop': True}, True),
        ({'monthly_limit': '50', 'hard_stop': False}, False),
        ({'monthly_limit': '60', 'hard_stop': True}, False),
        ({'monthly_limit': '5', 'hard_stop': True}, True),
    )
    for budget, blocked in cases:
        ai, _, _ = _build(budget=budget, ledger=FakeLedger([_cost_record(Decimal('51'))]))
        with patch('urllib.request.urlopen', return_value=_ok()):
            result = ai.invoke(DECISION, ENVELOPE)
        assert isinstance(result, WaitingAIInvocationResult) is blocked, budget
        if not blocked:
            assert result.record.error is None


def test_cost_is_recorded_through_the_ledger_only_when_positive() -> None:
    ai, ledger, _ = _build(executor_config=dict(EXECUTOR_CONFIG, cost_per_request='0.25'))
    with patch('urllib.request.urlopen', return_value=_ok()):
        result = ai.invoke(DECISION, ENVELOPE)
    assert result.record.error is None
    assert len(ledger.appended) == 1
    workspace_id, cost = ledger.appended[0]
    assert (workspace_id, cost.actual_cost, cost.job_ref, cost.source) == (WS, Decimal('0.25'), JOB, 'routed_invocation')
    free_ai, free_ledger, _ = _build()
    with patch('urllib.request.urlopen', return_value=_ok()):
        free_ai.invoke(DECISION, ENVELOPE)
    assert free_ledger.appended == []




def test_provider_failure_is_final_and_record_and_logs_hold_no_secret(caplog) -> None:
    ai, _, _ = _build()
    failure = _http_error(500, msg=f'upstream echo api_key={CANARY} {CANARY}')
    with patch('urllib.request.urlopen', side_effect=failure):
        result = ai.invoke(DECISION, ENVELOPE)
    assert not isinstance(result, WaitingAIInvocationResult)
    assert isinstance(result, AIInvocationResult)
    assert result.output is None
    assert result.record.error.startswith('provider_failed:')
    assert find_canaries([CANARY], result.record.to_json(), repr(result), caplog.text) == []


def test_budget_policy_from_config_has_no_defaults() -> None:
    policy = budget_policy_from_config(BUDGET_CONFIG)
    assert policy.monthly_limit == Decimal('50')
    assert policy.hard_stop is True
    bad_configs = (
        {'hard_stop': True},
        {'monthly_limit': '50'},
        {'monthly_limit': 50.0, 'hard_stop': True},
        {'monthly_limit': '50', 'hard_stop': 'yes'},
    )
    for bad in bad_configs:
        with pytest.raises(ValueError):
            budget_policy_from_config(bad)




def _executor(config=EXECUTOR_CONFIG):
    store = InvocationPayloadStore()
    credentials = FakeCredentials()
    return NineRouterExecutor(RouteExecutorConfig.from_mapping(config), store, credentials), store, credentials


def _j_decision():
    return JRouteDecision(
        provider_ref='c1', model_ref='model-c1', account_ref='acc-1', route_revision='route-rev-1',
        rationale_codes=['ROLE_OK'], fallback_order=[], capacity_reservation_ref='res-1',
        credential_acquisition_method='secret_broker_handle', estimated_cost_class='free', project_ref=None,
    )


def test_executor_rejects_endpoint_outside_the_configured_list() -> None:
    with pytest.raises(UnapprovedEndpointError):
        _executor(dict(EXECUTOR_CONFIG, endpoint='http://evil.example:20128'))


def test_executor_config_requires_every_key() -> None:
    for name in EXECUTOR_CONFIG:
        with pytest.raises(ValueError):
            RouteExecutorConfig.from_mapping({key: value for key, value in EXECUTOR_CONFIG.items() if key != name})
    with pytest.raises(ValueError):
        RouteExecutorConfig.from_mapping(dict(EXECUTOR_CONFIG, approved_endpoints=[]))


def test_executor_takes_timeout_retry_backoff_and_endpoint_from_config() -> None:
    config = dict(EXECUTOR_CONFIG, request_timeout_seconds=7, max_retries=2, backoff_factor=0.5)
    executor, store, _ = _executor(config)
    adapter = executor.http_adapter
    assert (adapter.timeout, adapter.max_retries, adapter.backoff_factor, adapter.base_url) == (7.0, 2, 0.5, ENDPOINT)
    store.put_request('ref-1', 'prompt')
    with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
        result = executor.execute(_j_decision(), 'c1', 'ref-1', 'secret_broker_handle')
    assert result.ok is True
    assert urlopen.call_args.kwargs['timeout'] == 7.0
    assert urlopen.call_args[0][0].full_url == ENDPOINT + '/v1/chat'
    assert store.pop_output(result.output_ref)['usage']['prompt_tokens'] == 7



def test_executor_refuses_any_credential_method_other_than_the_broker_handle() -> None:
    executor, store, credentials = _executor()
    store.put_request('ref-1', 'prompt')
    with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
        result = executor.execute(_j_decision(), 'c1', 'ref-1', 'plaintext_token')
    assert result.ok is False
    assert isinstance(result.error, ValueError)
    assert credentials.calls == []
    urlopen.assert_not_called()


def test_production_modules_have_no_mock_host_fixed_endpoint_or_src_import() -> None:
    root = pathlib.Path(__file__).resolve().parents[4] / 'src' / 'creative' / 'adapters'
    texts = {name: (root / name).read_text(encoding='utf-8') for name in ('real_ai_invocation.py', 'real_route_executor.py')}
    for name, text in texts.items():
        for forbidden in ('mock-9router', 'from src.', 'import src.', '20128', '127.0.0.1', 'localhost', 'http://', 'https://', "Decimal('50')"):
            assert forbidden not in text, (name, forbidden)
    assert 'RoutedInvocationService' in texts['real_ai_invocation.py']
