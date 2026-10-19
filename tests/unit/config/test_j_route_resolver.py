"""J-13: ProviderRouteResolver (CT-AI-ROUTE-001, CT-CAP-001, TST-SEC-INV-020).

coveredIds: CT-AI-ROUTE-001, CT-CAP-001, TST-SEC-INV-020
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import itertools
import json
import pathlib
import re
from datetime import datetime, timezone

import pytest

from controlplane.application.config_security import route_resolver
from controlplane.application.config_security.capacity_reservation import CapacityReservationBook
from controlplane.application.config_security.route_resolver import (
    NO_ELIGIBLE_ROUTE,
    NoRouteError,
    ProviderRouteResolver,
    RouteCandidate,
    RouteCatalogPort,
)
from controlplane.domain.config_security.capacity_snapshot import DomainCapacity, quota_domain_key
from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.route_binding import (
    ProviderRouteDecision,
    ProviderRouteRequest,
    validate_route_decision,
    validate_route_request,
)
from controlplane.domain.config_security.status_graph import ExternalAccountStatus

FIXTURE = pathlib.Path(__file__).resolve().parents[2] / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
NOW = datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
WS = 'ws-1'
ROLE = 'script_generation'
JOB = '00000000-0000-4000-8000-000000000100'


def _account(
    account_id: str = 'acc-1',
    status: ExternalAccountStatus = ExternalAccountStatus.ENABLED,
    workspace_id: str = WS,
    capabilities: frozenset[str] = frozenset({ROLE}),
    project_ref: str | None = 'proj-a',
) -> ExternalAccount:
    return ExternalAccount(
        external_account_id=account_id,
        workspace_id=workspace_id,
        provider='gemini',
        account_label='label-' + account_id,
        status=status,
        project_ref=project_ref,
        capabilities=capabilities,
        credential_version=1,
        credential_updated_at=None,
        credential_expires_at=None,
        quota_observation_ref=None,
        health=None,
        revision=1,
    )


def _candidate(
    ref: str,
    cost: str = 'low',
    sensitivity: str = 'confidential',
    local: bool = False,
    account: ExternalAccount | None = None,
    domain: str | None = None,
) -> RouteCandidate:
    acc = account or _account('acc-' + ref)
    return RouteCandidate(
        candidate_ref=ref,
        provider_ref='prov-' + ref,
        model_ref='model-' + ref,
        account=acc,
        quota_domain_key=domain or quota_domain_key('gemini', 'proj-a', 'model-' + ref),
        cost_class=cost,
        max_data_sensitivity=sensitivity,
        roles=frozenset({ROLE}),
        local=local,
    )


def _request(**overrides) -> ProviderRouteRequest:
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    payload = dict(data['entities']['ProviderRouteRequest']['valid'][0])
    payload.update(overrides)
    return ProviderRouteRequest(**payload)


def _capacity(domain: str, remaining: int | None = 5, health: str = 'healthy') -> DomainCapacity:
    return DomainCapacity(
        domain_key=domain,
        limit_requests=10,
        used_requests=0,
        remaining_requests=remaining,
        health=health,
        confidence='observed' if remaining is not None else 'unknown',
        reset_at=None,
        observed_at=None,
    )


class FakeCatalog:
    def __init__(self, items) -> None:
        self.items = tuple(items)
        self.calls: list[tuple[str, str]] = []

    def candidates(self, workspace_id: str, ai_role: str) -> tuple[RouteCandidate, ...]:
        self.calls.append((workspace_id, ai_role))
        return self.items


class SpyBook(CapacityReservationBook):
    def __init__(self) -> None:
        self.calls: list[dict] = []
        counter = itertools.count(1)
        super().__init__(ref_factory=lambda: f'res-{next(counter)}')

    def reserve(self, domain_key, units, ttl_seconds, operation_key, now, domain_capacity):
        self.calls.append({
            'domain_key': domain_key,
            'units': units,
            'ttl_seconds': ttl_seconds,
            'operation_key': operation_key,
            'now': now,
            'domain_capacity': domain_capacity,
        })
        return super().reserve(domain_key, units, ttl_seconds, operation_key, now, domain_capacity)


def _resolver(items, caps=None, book=None):
    caps_dict = caps if caps is not None else {}
    b = book or SpyBook()
    catalog = FakeCatalog(items)
    resolver = ProviderRouteResolver(catalog, b, lambda key: caps_dict.get(key), 'route-v1')
    return (resolver, catalog, b)


def _resolve(resolver, request=None, units=1, ttl_seconds=60, desktop_online=True, workspace_id=WS, now=NOW):
    return resolver.resolve(request or _request(), workspace_id, now, units, ttl_seconds, desktop_online)


# --- 3. Cấu trúc ---


def test_module_docstring_declares_covered_ids():
    assert 'coveredIds: CT-AI-ROUTE-001, CT-CAP-001, TST-SEC-INV-020' in (__doc__ or '')


def test_resolver_source_does_not_import_router_or_adapter():
    src = inspect.getsource(route_resolver)
    assert re.search(r'config[.](router|adapter)', src) is None
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != 'controlplane.config' and not alias.name.startswith('controlplane.config.')
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module != 'controlplane.config' and not node.module.startswith('controlplane.config.')


def test_route_candidate_is_frozen_with_nine_fields_in_order():
    field_names = [f.name for f in dataclasses.fields(RouteCandidate)]
    assert field_names == [
        'candidate_ref',
        'provider_ref',
        'model_ref',
        'account',
        'quota_domain_key',
        'cost_class',
        'max_data_sensitivity',
        'roles',
        'local',
    ]
    cand = _candidate('a')
    with pytest.raises(dataclasses.FrozenInstanceError):
        cand.candidate_ref = 'other'  # type: ignore[misc]


def test_catalog_port_declares_candidates():
    params = list(inspect.signature(RouteCatalogPort.candidates).parameters.keys())
    assert params == ['self', 'workspace_id', 'ai_role']


def test_constructor_and_resolve_signatures():
    init_params = inspect.signature(ProviderRouteResolver.__init__).parameters
    assert list(init_params.keys()) == ['self', 'catalog', 'reservations', 'capacities', 'route_revision']
    for p in init_params.values():
        assert p.default is inspect.Parameter.empty
    resolve_params = inspect.signature(ProviderRouteResolver.resolve).parameters
    assert list(resolve_params.keys()) == ['self', 'request', 'workspace_id', 'now', 'units', 'ttl_seconds', 'desktop_online']
    for p in resolve_params.values():
        assert p.default is inspect.Parameter.empty


def test_no_route_error_shape():
    e = NoRouteError('NO_ELIGIBLE_ROUTE', ['A'])
    assert e.code == 'NO_ELIGIBLE_ROUTE'
    assert e.rationale_codes == ('A',)
    assert isinstance(e, Exception)
    assert NO_ELIGIBLE_ROUTE == 'NO_ELIGIBLE_ROUTE'
    assert NoRouteError('X').rationale_codes == ()


# --- 4. Loại candidate (1) ---


@pytest.mark.parametrize('status', [
    ExternalAccountStatus.DISABLED,
    ExternalAccountStatus.DEGRADED,
    ExternalAccountStatus.INVALID,
    ExternalAccountStatus.REVOKED,
])
def test_account_not_enabled_is_excluded(status):
    cand = _candidate('a', account=_account('acc-a', status=status))
    resolver, _, book = _resolver([cand])
    with pytest.raises(NoRouteError) as info:
        _resolve(resolver)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'ACCOUNT_NOT_ELIGIBLE' in info.value.rationale_codes
    assert book.calls == []


def test_account_without_role_or_in_other_workspace_is_excluded():
    cases = [
        _account('acc-1', capabilities=frozenset({'other_role'})),
        _account('acc-2', capabilities=frozenset()),
        _account('acc-3', workspace_id='ws-2'),
    ]
    for acc in cases:
        resolver, _, book = _resolver([_candidate('a', account=acc)])
        with pytest.raises(NoRouteError) as info:
            _resolve(resolver)
        assert info.value.code == 'NO_ELIGIBLE_ROUTE'
        assert 'ACCOUNT_NOT_ELIGIBLE' in info.value.rationale_codes
        assert book.calls == []


def test_disabled_account_is_skipped_for_next_candidate():
    c1 = _candidate('a-free', cost='free', account=_account('acc-1', status=ExternalAccountStatus.DISABLED))
    c2 = _candidate('b-low', cost='low', account=_account('acc-2', status=ExternalAccountStatus.ENABLED))
    resolver, _, book = _resolver([c1, c2])
    decision = _resolve(resolver)
    assert decision.provider_ref == 'prov-b-low'


def test_sensitivity_above_candidate_max_is_excluded():
    req = _request(data_sensitivity='confidential')
    cand = _candidate('a', sensitivity='internal')
    resolver, _, book = _resolver([cand])
    with pytest.raises(NoRouteError) as info:
        _resolve(resolver, request=req)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'SENSITIVITY_EXCEEDED' in info.value.rationale_codes
    assert book.calls == []

    for req_sens, cand_sens in [
        ('public', 'public'),
        ('internal', 'internal'),
        ('internal', 'confidential'),
        ('public', 'confidential'),
    ]:
        r, _, _ = _resolver([_candidate('a', sensitivity=cand_sens)])
        d = _resolve(r, request=_request(data_sensitivity=req_sens))
        assert d.provider_ref == 'prov-a'


def test_unknown_sensitivity_value_is_excluded_fail_closed():
    cases = [
        (_request(data_sensitivity='top_secret'), _candidate('a', sensitivity='confidential')),
        (_request(data_sensitivity='public'), _candidate('a', sensitivity='top_secret')),
        (_request(data_sensitivity=''), _candidate('a', sensitivity='confidential')),
    ]
    for req, cand in cases:
        r, _, book = _resolver([cand])
        with pytest.raises(NoRouteError) as info:
            _resolve(r, request=req)
        assert info.value.code == 'NO_ELIGIBLE_ROUTE'
        assert 'SENSITIVITY_EXCEEDED' in info.value.rationale_codes
        assert book.calls == []


def test_cost_above_bound_is_no_route_even_if_sole_candidate():
    req = _request(quality_latency_cost_bounds={'max_cost_class': 'low'})
    for cost in ['medium', 'high']:
        r, _, book = _resolver([_candidate('a', cost=cost)])
        with pytest.raises(NoRouteError) as info:
            _resolve(r, request=req)
        assert info.value.code == 'NO_ELIGIBLE_ROUTE'
        assert 'COST_EXCEEDS_BOUND' in info.value.rationale_codes
        assert book.calls == []
    for cost in ['low', 'free']:
        r, _, _ = _resolver([_candidate('a', cost=cost)])
        d = _resolve(r, request=req)
        assert d.provider_ref == 'prov-a'


def test_unknown_candidate_cost_is_excluded():
    req = _request(quality_latency_cost_bounds={'max_cost_class': 'high'})
    cand = _candidate('a', cost='premium')
    r, _, book = _resolver([cand])
    with pytest.raises(NoRouteError) as info:
        _resolve(r, request=req)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'COST_EXCEEDS_BOUND' in info.value.rationale_codes
    assert book.calls == []


def test_unknown_bound_value_excludes_everything():
    req = _request(quality_latency_cost_bounds={'max_cost_class': 'ultra'})
    cand = _candidate('a', cost='free')
    r, _, book = _resolver([cand])
    with pytest.raises(NoRouteError) as info:
        _resolve(r, request=req)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'COST_EXCEEDS_BOUND' in info.value.rationale_codes
    assert book.calls == []


def test_missing_bound_accepts_only_free():
    req_empty = _request(quality_latency_cost_bounds={})
    r1, _, book1 = _resolver([_candidate('a', cost='low')])
    with pytest.raises(NoRouteError) as info:
        _resolve(r1, request=req_empty)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'COST_EXCEEDS_BOUND' in info.value.rationale_codes
    assert book1.calls == []

    r2, _, _ = _resolver([_candidate('a', cost='free')])
    assert _resolve(r2, request=req_empty).provider_ref == 'prov-a'

    req_none = _request(quality_latency_cost_bounds={'max_cost_class': None})
    r3, _, book3 = _resolver([_candidate('a', cost='low')])
    with pytest.raises(NoRouteError) as info:
        _resolve(r3, request=req_none)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'COST_EXCEEDS_BOUND' in info.value.rationale_codes
    assert book3.calls == []


def test_local_candidate_excluded_when_desktop_offline():
    cand_local = _candidate('a-local', cost='free', local=True)
    cand_cloud = _candidate('b-cloud', cost='low', local=False)

    r1, _, book1 = _resolver([cand_local])
    with pytest.raises(NoRouteError) as info:
        _resolve(r1, desktop_online=False)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'LOCAL_OFFLINE' in info.value.rationale_codes
    assert book1.calls == []

    r2, _, _ = _resolver([cand_local])
    assert _resolve(r2, desktop_online=True).provider_ref == 'prov-a-local'

    r3, _, _ = _resolver([cand_cloud])
    assert _resolve(r3, desktop_online=False).provider_ref == 'prov-b-cloud'

    r4, _, _ = _resolver([cand_local, cand_cloud])
    assert _resolve(r4, desktop_online=False).provider_ref == 'prov-b-cloud'

    r5, _, book5 = _resolver([cand_local])
    with pytest.raises(NoRouteError) as info:
        _resolve(r5, desktop_online=1)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'LOCAL_OFFLINE' in info.value.rationale_codes
    assert book5.calls == []


# --- 5. Loại candidate (2): capacity ---


def test_capacity_unavailable_health_or_zero_remaining_is_excluded():
    cand = _candidate('a')
    d = cand.quota_domain_key

    r1, _, book1 = _resolver([cand], caps={d: _capacity(d, health='unavailable')})
    with pytest.raises(NoRouteError) as info:
        _resolve(r1)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'CAPACITY_UNAVAILABLE' in info.value.rationale_codes
    assert book1.calls == []

    r2, _, book2 = _resolver([cand], caps={d: _capacity(d, remaining=0)})
    with pytest.raises(NoRouteError) as info:
        _resolve(r2)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'CAPACITY_UNAVAILABLE' in info.value.rationale_codes
    assert book2.calls == []

    r3, _, _ = _resolver([cand], caps={d: _capacity(d, remaining=5, health='healthy')})
    assert _resolve(r3).provider_ref == 'prov-a'


def test_two_accounts_in_same_quota_domain_are_one_budget():
    d = quota_domain_key('gemini', 'proj-a', 'shared')
    ca = _candidate('a', account=_account('acc-a'), domain=d)
    cb = _candidate('b', account=_account('acc-b'), domain=d)

    r1, _, book1 = _resolver([ca, cb], caps={d: _capacity(d, remaining=0)})
    with pytest.raises(NoRouteError) as info:
        _resolve(r1)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'CAPACITY_UNAVAILABLE' in info.value.rationale_codes
    assert book1.calls == []

    r2, _, _ = _resolver([ca, cb], caps={d: _capacity(d, remaining=1)})
    dec1 = _resolve(r2, request=_request(job_ref='00000000-0000-4000-8000-000000000100'), units=1)
    assert dec1.provider_ref == 'prov-a'
    with pytest.raises(NoRouteError) as info:
        _resolve(r2, request=_request(job_ref='00000000-0000-4000-8000-000000000200'), units=1)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'CAPACITY_UNAVAILABLE' in info.value.rationale_codes


def test_capacity_taken_by_another_operation_falls_to_next_candidate():
    da = quota_domain_key('gemini', 'proj-a', 'da')
    db = quota_domain_key('gemini', 'proj-a', 'db')
    ca = _candidate('a-free', cost='free', domain=da)
    cb = _candidate('b-low', cost='low', domain=db)
    caps = {da: _capacity(da, remaining=1), db: _capacity(db, remaining=5)}
    resolver, _, book = _resolver([ca, cb], caps=caps)
    book.reserve(da, 1, 60, 'other:op', NOW, caps[da])
    req = _request(quality_latency_cost_bounds={'max_cost_class': 'high'}, allowed_fallbacks=['a-free', 'b-low'])
    dec = _resolve(resolver, request=req)
    assert dec.provider_ref == 'prov-b-low'
    assert 'a-free' not in dec.fallback_order


def test_unknown_remaining_keeps_candidate_with_quota_uncertain():
    cand = _candidate('a')
    d = cand.quota_domain_key

    r1, _, _ = _resolver([cand], caps={d: _capacity(d, remaining=None)})
    dec1 = _resolve(r1)
    assert dec1.provider_ref == 'prov-a'
    assert 'QUOTA_UNCERTAIN' in dec1.rationale_codes
    assert 'QUOTA_AVAILABLE' not in dec1.rationale_codes

    r2, _, _ = _resolver([cand], caps={})
    dec2 = _resolve(r2)
    assert dec2.provider_ref == 'prov-a'
    assert 'QUOTA_UNCERTAIN' in dec2.rationale_codes
    assert 'QUOTA_AVAILABLE' not in dec2.rationale_codes


def test_capacities_is_queried_with_candidate_quota_domain_key():
    cand = _candidate('a')
    seen = []
    catalog = FakeCatalog([cand])
    book = SpyBook()
    resolver = ProviderRouteResolver(catalog, book, lambda key: seen.append(key), 'route-v1')
    _resolve(resolver)
    assert seen == [cand.quota_domain_key]


def test_no_candidate_gives_no_route_with_empty_rationale():
    resolver, catalog, book = _resolver([])
    with pytest.raises(NoRouteError) as info:
        _resolve(resolver)
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert info.value.rationale_codes == ()
    assert catalog.calls == [(WS, ROLE)]
    assert book.calls == []


def test_no_route_rationale_names_the_exclusion_reasons():
    c_disabled = _candidate('a', account=_account('acc-a', status=ExternalAccountStatus.DISABLED))
    c_sens = _candidate('b', sensitivity='public')
    resolver, _, book = _resolver([c_disabled, c_sens])
    with pytest.raises(NoRouteError) as info:
        _resolve(resolver, request=_request(data_sensitivity='internal'))
    assert info.value.code == 'NO_ELIGIBLE_ROUTE'
    assert 'ACCOUNT_NOT_ELIGIBLE' in info.value.rationale_codes
    assert 'SENSITIVITY_EXCEEDED' in info.value.rationale_codes
    assert len(set(info.value.rationale_codes)) == len(info.value.rationale_codes)


# --- 6. Chọn và decision ---


def test_selects_cheapest_available():
    c_high = _candidate('c-high', cost='high')
    c_low = _candidate('b-low', cost='low')
    c_med = _candidate('a-medium', cost='medium')
    req = _request(quality_latency_cost_bounds={'max_cost_class': 'high'})
    r1, _, _ = _resolver([c_high, c_low, c_med])
    assert _resolve(r1, request=req).provider_ref == 'prov-b-low'
    c_free = _candidate('z-free', cost='free')
    r2, _, _ = _resolver([c_high, c_low, c_med, c_free])
    assert _resolve(r2, request=req).provider_ref == 'prov-z-free'


def test_tie_on_cost_breaks_by_candidate_ref_ascending():
    c_bx = _candidate('b-x', cost='low')
    c_ax = _candidate('a-x', cost='low')
    c_cx = _candidate('c-x', cost='low')
    r1, _, _ = _resolver([c_bx, c_ax, c_cx])
    assert _resolve(r1).provider_ref == 'prov-a-x'
    r2, _, _ = _resolver(list(reversed([c_bx, c_ax, c_cx])))
    assert _resolve(r2).provider_ref == 'prov-a-x'


def test_same_input_gives_equal_decision():
    resolver, _, book = _resolver([_candidate('a')])
    req = _request()
    d1 = _resolve(resolver, request=req)
    d2 = _resolve(resolver, request=req)
    assert d1 == d2
    assert len(book.calls) == 2
    assert d1.capacity_reservation_ref == d2.capacity_reservation_ref
    assert len(book._store.list_all()) == 1


def test_reserve_is_called_with_operation_key_job_and_role():
    cand = _candidate('a')
    d = cand.quota_domain_key
    caps = {d: _capacity(d, remaining=5)}
    resolver, _, book = _resolver([cand], caps=caps)
    dec = _resolve(resolver, units=3, ttl_seconds=90)
    assert len(book.calls) == 1
    call = book.calls[0]
    assert call['domain_key'] == cand.quota_domain_key
    assert call['units'] == 3
    assert call['ttl_seconds'] == 90
    assert call['operation_key'] == JOB + ':' + ROLE
    assert call['now'] == NOW
    assert call['domain_capacity'] == caps[d]
    assert dec.capacity_reservation_ref == 'res-1'


def test_decision_fields():
    cand = _candidate('a', cost='low', account=_account('acc-a', project_ref='proj-x'))
    d = cand.quota_domain_key
    catalog = FakeCatalog([cand])
    book = SpyBook()
    resolver = ProviderRouteResolver(catalog, book, lambda k: _capacity(d, remaining=5), 'rev-42')
    dec = resolver.resolve(_request(), WS, NOW, 1, 60, True)
    assert isinstance(dec, ProviderRouteDecision)
    assert dec.provider_ref == 'prov-a'
    assert dec.model_ref == 'model-a'
    assert dec.account_ref == 'acc-a'
    assert dec.route_revision == 'rev-42'
    assert dec.rationale_codes == ['ROLE_OK', 'QUOTA_AVAILABLE', 'COST_WITHIN_BOUND']
    assert isinstance(dec.rationale_codes, list)
    assert dec.credential_acquisition_method == 'secret_broker_handle'
    assert dec.estimated_cost_class == 'low'
    assert dec.project_ref == 'proj-x'
    assert dec.fallback_order == []

    resolver_unc = ProviderRouteResolver(catalog, SpyBook(), lambda k: _capacity(d, remaining=None), 'rev-42')
    dec_unc = resolver_unc.resolve(_request(), WS, NOW, 1, 60, True)
    assert dec_unc.rationale_codes == ['ROLE_OK', 'QUOTA_UNCERTAIN', 'COST_WITHIN_BOUND']

    cand_no_proj = _candidate('b', cost='low', account=_account('acc-b', project_ref=None))
    resolver_no_p = ProviderRouteResolver(FakeCatalog([cand_no_proj]), SpyBook(), lambda k: None, 'rev-42')
    assert resolver_no_p.resolve(_request(), WS, NOW, 1, 60, True).project_ref is None


def test_decision_passes_validate_route_decision_without_forbidden_keys():
    cand = _candidate('a', cost='low')
    resolver, _, _ = _resolver([cand])
    dec = _resolve(resolver)
    payload = dataclasses.asdict(dec)
    assert validate_route_decision(payload) == []
    forbidden = {'secret_value', 'api_key', 'access_token', 'refresh_token'}
    for k in payload:
        assert k.casefold() not in forbidden
    assert 'api_key' not in repr(dec).lower()


def test_fixture_valid_request_passes_validate_route_request_and_resolves():
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    valid_payload = data['entities']['ProviderRouteRequest']['valid'][0]
    assert validate_route_request(valid_payload) == []
    resolver, _, _ = _resolver([_candidate('a', cost='low')])
    dec = _resolve(resolver, request=_request())
    assert isinstance(dec, ProviderRouteDecision)
    invalid_case = next(item for item in data['entities']['ProviderRouteRequest']['invalid'] if item['case'] == 'missing_data_sensitivity')
    issues = validate_route_request(invalid_case['payload'])
    assert invalid_case['expected_error'] in issues


# --- 7. Fallback và đầu vào ---


def test_fallback_order_contains_only_allowed_remaining_candidates():
    ca = _candidate('a', cost='free')
    cb = _candidate('b', cost='low')
    cc = _candidate('c', cost='medium')
    cd = _candidate('d', cost='low')
    req = _request(quality_latency_cost_bounds={'max_cost_class': 'high'}, allowed_fallbacks=['d', 'c', 'b'])
    resolver, _, _ = _resolver([ca, cb, cc, cd])
    dec = _resolve(resolver, request=req)
    assert dec.provider_ref == 'prov-a'
    assert dec.fallback_order == ['b', 'd', 'c']


def test_unknown_fallback_ref_is_ignored():
    ca = _candidate('a', cost='free')
    cb = _candidate('b', cost='low')
    resolver, _, _ = _resolver([ca, cb])
    req1 = _request(quality_latency_cost_bounds={'max_cost_class': 'high'}, allowed_fallbacks=['ghost', 'b'])
    assert _resolve(resolver, request=req1).fallback_order == ['b']
    req2 = _request(quality_latency_cost_bounds={'max_cost_class': 'high'}, allowed_fallbacks=[7, None, 'b'])
    assert _resolve(resolver, request=req2).fallback_order == ['b']
    req3 = _request(quality_latency_cost_bounds={'max_cost_class': 'high'}, allowed_fallbacks=[])
    assert _resolve(resolver, request=req3).fallback_order == []


def test_selected_and_ineligible_candidates_are_not_in_fallback_order():
    ca = _candidate('a', cost='free')
    cb = _candidate('b', cost='low', account=_account('acc-b', status=ExternalAccountStatus.DISABLED))
    cc = _candidate('c', cost='low', sensitivity='public')
    resolver, _, _ = _resolver([ca, cb, cc])
    req = _request(data_sensitivity='internal', quality_latency_cost_bounds={'max_cost_class': 'high'}, allowed_fallbacks=['a', 'b', 'c'])
    dec = _resolve(resolver, request=req)
    assert dec.provider_ref == 'prov-a'
    assert dec.fallback_order == []


def test_request_cannot_inject_ref_outside_catalog():
    r1, _, _ = _resolver([])
    req1 = _request(allowed_fallbacks=['evil'])
    with pytest.raises(NoRouteError):
        _resolve(r1, request=req1)

    r2, _, _ = _resolver([_candidate('a')])
    req2 = _request(allowed_fallbacks=['evil'])
    dec2 = _resolve(r2, request=req2)
    assert dec2.provider_ref == 'prov-a'
    assert dec2.fallback_order == []


def test_resolve_does_not_mutate_inputs():
    req = _request()
    req_dict_before = dataclasses.asdict(req)
    cand = _candidate('a')
    resolver, catalog, _ = _resolver([cand])
    items_before = list(catalog.items)
    _resolve(resolver, request=req)
    assert dataclasses.asdict(req) == req_dict_before
    assert list(catalog.items) == items_before


@pytest.mark.parametrize('bad_kwargs', [
    {'workspace_id': ''},
    {'workspace_id': '   '},
    {'now': datetime(2026, 10, 20)},
    {'units': 0},
    {'units': -1},
    {'units': True},
    {'ttl_seconds': 0},
    {'ttl_seconds': True},
    {'request': _request(job_ref='')},
    {'request': _request(ai_role='')},
])
def test_invalid_inputs_raise_value_error(bad_kwargs):
    cand = _candidate('a')
    resolver, _, book = _resolver([cand])
    call_args = {'request': _request(), 'workspace_id': WS, 'now': NOW, 'units': 1, 'ttl_seconds': 60, 'desktop_online': True}
    call_args.update(bad_kwargs)
    with pytest.raises(ValueError):
        resolver.resolve(**call_args)
    assert book.calls == []


def test_invalid_request_type_raises_type_error():
    resolver, _, book = _resolver([_candidate('a')])
    with pytest.raises(TypeError):
        resolver.resolve({}, WS, NOW, 1, 60, True)  # type: ignore[arg-type]
    assert book.calls == []


def test_empty_route_revision_raises_value_error():
    with pytest.raises(ValueError):
        ProviderRouteResolver(FakeCatalog([]), SpyBook(), lambda k: None, '')
