"""D-04: Port định tuyến AI, fake adapter và AIInvocationRecord (CT-AI-ROUTE-001, CT-AI-010).

coveredIds: CT-AI-010, CT-AI-ROUTE-001, TST-SEC-INV-012
"""
import ast
import copy
import dataclasses
import hashlib
import inspect
import json
import pathlib
import socket

import pytest

from creative.adapters.fake_ai import (
    FakeAIAdapter,
    FakeProviderRoute,
    NoScriptedResponse,
    UnknownReservation,
)
from creative.domain import invocation as invocation_module
from creative.domain.invocation import (
    AIInvocationRecord,
    AIInvocationResult,
    BINDING_VERSION,
    FORBIDDEN_FIELD,
    InvocationUsage,
    MISSING_REQUIRED,
    ProviderRouteDecision,
    REDACTED,
    ROUTE_DECISION_FORBIDDEN,
    ROUTE_DECISION_ITEMS,
    ROUTE_DECISION_OPTIONAL,
    ROUTE_DECISION_REQUIRED,
    ROUTE_REQUEST_OPTIONAL,
    ROUTE_REQUEST_REQUIRED,
    RouteContractViolation,
    VALIDATION_RESULTS,
    WRONG_TYPE,
    fingerprint_envelope,
    fingerprint_output,
    redact_error,
    validate_provider_route_decision,
    validate_provider_route_request,
)
from creative.domain.ref_resolver import ResourceRef
from creative.domain.untrusted import ModelOutput, PromptEnvelope, UntrustedText
from creative.ports.ai import AIInvocationPort, ProviderRoutePort

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'j-provider-route.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
SOURCES = tuple(ROOT / 'src' / 'creative' / p for p in ('domain/invocation.py', 'ports/ai.py', 'adapters/fake_ai.py'))
CANARY = 'canary-7f3a9c1e-not-a-real-secret'
REQUEST = 'ProviderRouteRequest'
DECISION = 'ProviderRouteDecision'
VALIDATORS = {REQUEST: validate_provider_route_request, DECISION: validate_provider_route_decision}
REQUIRED = {REQUEST: ROUTE_REQUEST_REQUIRED, DECISION: ROUTE_DECISION_REQUIRED}


def _binding():
    return json.loads(BINDING_PATH.read_text(encoding='utf-8'))


def _entity(name):
    for entity in _binding()['entities']:
        if entity['name'] == name:
            return entity
    raise KeyError(name)


def _fixture(name):
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][name]


def _derive(entity):
    req = {f['name']: f['type'] for f in entity.get('fields', []) if f.get('required')}
    opt = {f['name']: f['type'] for f in entity.get('fields', []) if not f.get('required')}
    items = {f['name']: f['items'] for f in entity.get('fields', []) if 'items' in f}
    forbidden = tuple(entity.get('forbidden_fields', ()))
    return (req, opt, items, forbidden)


def _request():
    return copy.deepcopy(_fixture(REQUEST)['valid'][0])


def _decision():
    return copy.deepcopy(_fixture(DECISION)['valid'][0])


def _issues(entity_name, payload):
    return [(i.code, i.field) for i in VALIDATORS[entity_name](payload)]


def test_request_constants_match_binding():
    assert _derive(_entity(REQUEST)) == (dict(ROUTE_REQUEST_REQUIRED), dict(ROUTE_REQUEST_OPTIONAL), {}, ())


def test_decision_constants_match_binding():
    assert _derive(_entity(DECISION)) == (
        dict(ROUTE_DECISION_REQUIRED),
        dict(ROUTE_DECISION_OPTIONAL),
        dict(ROUTE_DECISION_ITEMS),
        tuple(ROUTE_DECISION_FORBIDDEN),
    )
    assert tuple(ROUTE_DECISION_FORBIDDEN) == ('secret_value', 'api_key', 'access_token', 'refresh_token')


def test_binding_version_constant_matches_binding():
    assert BINDING_VERSION == _binding()['binding_version']


def test_drift_comparison_detects_mutated_binding():
    expected = _derive(_entity(DECISION))

    # 1. required=False for route_revision
    m1 = copy.deepcopy(_entity(DECISION))
    for f in m1['fields']:
        if f['name'] == 'route_revision':
            f['required'] = False
    assert _derive(m1) != expected

    # 2. type of route_revision -> 'array'
    m2 = copy.deepcopy(_entity(DECISION))
    for f in m2['fields']:
        if f['name'] == 'route_revision':
            f['type'] = 'array'
    assert _derive(m2) != expected

    # 3. add field {'name': 'x_new', 'type': 'string', 'required': True}
    m3 = copy.deepcopy(_entity(DECISION))
    m3['fields'].append({'name': 'x_new', 'type': 'string', 'required': True})
    assert _derive(m3) != expected

    # 4. delete key 'items' of rationale_codes
    m4 = copy.deepcopy(_entity(DECISION))
    for f in m4['fields']:
        if f['name'] == 'rationale_codes' and 'items' in f:
            del f['items']
    assert _derive(m4) != expected

    # 5. remove 'api_key' from forbidden_fields
    m5 = copy.deepcopy(_entity(DECISION))
    m5['forbidden_fields'] = [x for x in m5['forbidden_fields'] if x != 'api_key']
    assert _derive(m5) != expected


def test_fixture_has_valid_and_invalid_cases():
    for name in (REQUEST, DECISION):
        assert len(_fixture(name)['valid']) >= 1
    assert len(_fixture(REQUEST)['invalid']) >= 1
    assert len(_fixture(DECISION)['invalid']) >= 3


def test_fixture_valid_payloads_have_no_issues():
    for entity in (REQUEST, DECISION):
        for payload in _fixture(entity)['valid']:
            assert _issues(entity, payload) == []


CASES = [(entity, case) for entity in (REQUEST, DECISION) for case in _fixture(entity)['invalid']]


@pytest.mark.parametrize('entity,case', CASES, ids=[f"{e}-{c['case']}" for e, c in CASES])
def test_fixture_invalid_case_returns_expected_issue(entity, case):
    expected = case['expected_error']
    assert _issues(entity, case['payload']) == [(expected['code'], expected['field'])]


def test_each_missing_required_field_is_reported():
    for entity in (REQUEST, DECISION):
        assert len(REQUIRED[entity]) > 0
        for name in REQUIRED[entity]:
            payload = copy.deepcopy(_fixture(entity)['valid'][0])
            del payload[name]
            assert _issues(entity, payload) == [(MISSING_REQUIRED, name)]


@pytest.mark.parametrize(
    'entity,field,value',
    [
        (REQUEST, 'ai_role', 5),
        (REQUEST, 'job_ref', None),
        (REQUEST, 'config_refs', 'x'),
        (REQUEST, 'config_refs', {'a': 1}),
        (REQUEST, 'quality_latency_cost_bounds', []),
        (REQUEST, 'quality_latency_cost_bounds', 'x'),
        (REQUEST, 'allowed_fallbacks', 'x'),
        (REQUEST, 'health_quota_ref', 5),
        (DECISION, 'provider_ref', 5),
        (DECISION, 'fallback_order', 'gemini'),
        (DECISION, 'fallback_order', None),
        (DECISION, 'rationale_codes', 'QUOTA'),
        (DECISION, 'rationale_codes', [1]),
        (DECISION, 'rationale_codes', ['OK', None]),
        (DECISION, 'project_ref', 5),
        (DECISION, 'estimated_cost_class', None),
    ],
)
def test_field_counterexamples_are_wrong_type(entity, field, value):
    payload = copy.deepcopy(_fixture(entity)['valid'][0])
    payload[field] = value
    assert _issues(entity, payload) == [(WRONG_TYPE, field)]


def test_optional_fields():
    req1 = copy.deepcopy(_fixture(REQUEST)['valid'][0])
    req1['health_quota_ref'] = 'q-1'
    assert _issues(REQUEST, req1) == []
    req2 = copy.deepcopy(_fixture(REQUEST)['valid'][0])
    req2['health_quota_ref'] = None
    assert _issues(REQUEST, req2) == []

    dec1 = copy.deepcopy(_fixture(DECISION)['valid'][0])
    dec1['project_ref'] = 'proj-1'
    assert _issues(DECISION, dec1) == []
    dec2 = copy.deepcopy(_fixture(DECISION)['valid'][0])
    dec2['project_ref'] = None
    assert _issues(DECISION, dec2) == []


def test_unknown_field_is_ignored():
    for entity in (REQUEST, DECISION):
        payload = copy.deepcopy(_fixture(entity)['valid'][0])
        payload['x_future_optional_field'] = {'additive': True}
        assert _issues(entity, payload) == []


def test_non_mapping_payload_is_wrong_type():
    for entity in (REQUEST, DECISION):
        for bad in (None, [], 'payload'):
            assert _issues(entity, bad) == [(WRONG_TYPE, '$')]


def test_forbidden_fields_rejected_at_every_depth():
    assert len(ROUTE_DECISION_FORBIDDEN) == 4
    for name in ROUTE_DECISION_FORBIDDEN:
        positions = [
            lambda p, n=name: p.update({n: CANARY}),
            lambda p, n=name: p.update({'extra': {'deep': {'deeper': {n: CANARY}}}}),
            lambda p, n=name: p.update({'fallback_order': [{'meta': {n: CANARY}}]}),
            lambda p, n=name: p.update({'fallback_order': [[{n: CANARY}]]}),
            lambda p, n=name: p.update({'fallback_order': ({n: CANARY},)}),
            lambda p, n=name: p.update({n.upper(): CANARY}),
        ]
        for apply_pos in positions:
            payload = _decision()
            apply_pos(payload)
            assert _issues(DECISION, payload) == [(FORBIDDEN_FIELD, name)]


def test_nested_api_key_decision_is_rejected_everywhere():
    payload = _decision()
    payload['fallback_order'] = [{'meta': {'api_key': CANARY}}]
    assert validate_provider_route_decision(payload) != []
    with pytest.raises(RouteContractViolation) as excinfo:
        ProviderRouteDecision.from_payload(payload)
    assert [(i.code, i.field) for i in excinfo.value.issues] == [(FORBIDDEN_FIELD, 'api_key')]
    assert CANARY not in str(excinfo.value)
    assert CANARY not in repr(excinfo.value)

    kwargs = {**_decision(), 'fallback_order': ({'api_key': CANARY},)}
    with pytest.raises(RouteContractViolation) as excinfo2:
        ProviderRouteDecision(**kwargs)
    assert CANARY not in str(excinfo2.value)
    assert CANARY not in repr(excinfo2.value)


def test_decision_round_trips_fixture_and_is_frozen():
    d = ProviderRouteDecision.from_payload(_decision())
    assert d.to_payload() == _decision()
    assert isinstance(d.rationale_codes, tuple)
    assert isinstance(d.fallback_order, tuple)
    assert ProviderRouteDecision.__dataclass_params__.frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(d, 'route_revision', 'x')

    payload_with_proj = {**_decision(), 'project_ref': 'proj-1'}
    d_proj = ProviderRouteDecision.from_payload(payload_with_proj)
    assert d_proj.project_ref == 'proj-1'
    assert 'project_ref' in d_proj.to_payload()
    assert d_proj.to_payload()['project_ref'] == 'proj-1'

    d_no_proj = ProviderRouteDecision.from_payload(_decision())
    assert 'project_ref' not in d_no_proj.to_payload()


def test_from_payload_rejects_invalid_fixture_cases():
    for case in _fixture(DECISION)['invalid']:
        with pytest.raises(RouteContractViolation) as excinfo:
            ProviderRouteDecision.from_payload(case['payload'])
        expected = case['expected_error']
        assert (excinfo.value.issues[0].code, excinfo.value.issues[0].field) == (expected['code'], expected['field'])


def test_decision_constructor_rejects_bad_values():
    with pytest.raises(RouteContractViolation):
        ProviderRouteDecision(**{**_decision(), 'fallback_order': 'gemini'})
    with pytest.raises(RouteContractViolation):
        ProviderRouteDecision(**{**_decision(), 'fallback_order': [{'plain': 'dict'}]})
    with pytest.raises(RouteContractViolation):
        ProviderRouteDecision(**{**_decision(), 'route_revision': None})


def _envelope(text='bài viết mẫu', prompt_revision='prompt-r1', instructions='Summarize the data field.'):
    return PromptEnvelope(
        prompt_ref=ResourceRef('ws-1', 'prompt_revision', 'p-1', prompt_revision),
        instructions=instructions,
        data=[UntrustedText(text=text, provenance=ResourceRef('ws-1', 'article', 'a-1', 'r-2'))],
    )


def _rig(route=None, **kw):
    route = route or FakeProviderRoute()
    adapter = FakeAIAdapter(
        route,
        responses={
            'script_generation': {'text': 'script A', 'refs': []},
            'metadata_generation': {'text': 'meta B', 'refs': []},
        },
        config_revision='cfg-r1',
        **kw,
    )
    return (route, adapter)


def _resolve(route, role='script_generation', **extra):
    return route.resolve({**_request(), 'ai_role': role, **extra})


def _record_kwargs(**o):
    base = dict(
        ai_role='script_generation',
        provider_ref='p',
        model_ref='m',
        account_ref='a',
        route_revision='route-v1',
        prompt_revision='prompt-r1',
        config_revision='cfg-r1',
        input_fingerprint='a' * 64,
        output_fingerprint='b' * 64,
        usage=InvocationUsage(1, 2, 'low'),
        latency_ms=5,
        attempt=1,
        fallback_path=('p',),
        validation_result='not_run',
    )
    base.update(o)
    return base


def test_fakes_satisfy_ports_and_signatures():
    assert isinstance(FakeProviderRoute(), ProviderRoutePort)
    _, adapter = _rig()
    assert isinstance(adapter, AIInvocationPort)
    assert list(inspect.signature(ProviderRoutePort.resolve).parameters) == ['self', 'request']
    assert list(inspect.signature(AIInvocationPort.invoke).parameters) == ['self', 'decision', 'envelope']


def test_fake_route_returns_valid_decision_and_counts():
    route = FakeProviderRoute()
    d1 = _resolve(route, allowed_fallbacks=['fake-local'])
    assert validate_provider_route_decision(d1.to_payload()) == []
    assert route.resolve_calls == 1
    assert d1.fallback_order == ('fake-local',)
    d2 = _resolve(route)
    assert route.resolve_calls == 2
    assert d2.capacity_reservation_ref != d1.capacity_reservation_ref
    assert route.role_for_reservation(d1.capacity_reservation_ref) == 'script_generation'
    with pytest.raises(UnknownReservation):
        route.role_for_reservation('nope')


def test_fake_route_rejects_invalid_request_and_still_counts():
    route = FakeProviderRoute()
    case = _fixture(REQUEST)['invalid'][0]
    expected = case['expected_error']
    with pytest.raises(RouteContractViolation) as excinfo:
        route.resolve(case['payload'])
    assert [(i.code, i.field) for i in excinfo.value.issues] == [(expected['code'], expected['field'])]
    assert route.resolve_calls == 1


def test_adapter_returns_scripted_response_per_role():
    route, adapter = _rig()
    r1 = adapter.invoke(_resolve(route, 'script_generation'), _envelope())
    r2 = adapter.invoke(_resolve(route, 'metadata_generation'), _envelope())
    assert r1.output.text == 'script A'
    assert r2.output.text == 'meta B'
    assert r1.record.ai_role == 'script_generation'
    assert r2.record.ai_role == 'metadata_generation'
    assert adapter.invoke_calls == 2
    assert adapter.calls_by_role == {'script_generation': 1, 'metadata_generation': 1}
    r3 = adapter.invoke(_resolve(route, 'script_generation'), _envelope())
    assert adapter.invoke_calls == 3
    assert adapter.calls_by_role['script_generation'] == 2
    assert r3.output.text == 'script A'
    assert len(adapter.records) == 3


def test_scripted_tool_fields_are_ignored():
    route = FakeProviderRoute()
    adapter = FakeAIAdapter(
        route,
        responses={'script_generation': {'text': 'script A', 'refs': [], 'tool_call': {'name': 'fetch_url'}}},
        config_revision='cfg-r1',
    )
    result = adapter.invoke(_resolve(route, 'script_generation'), _envelope())
    assert not hasattr(result.output, 'tool_call')
    assert {f.name for f in dataclasses.fields(result.output)} == {'text', 'proposed_refs'}


def test_unscripted_role_raises_and_counts():
    route, adapter = _rig()
    with pytest.raises(NoScriptedResponse):
        adapter.invoke(_resolve(route, 'unknown_role'), _envelope())
    assert adapter.invoke_calls == 1
    assert adapter.records == []


def test_invoke_rejects_wrong_argument_types_before_counting():
    route, adapter = _rig()
    decision = _resolve(route)
    with pytest.raises(TypeError):
        adapter.invoke({}, _envelope())
    with pytest.raises(TypeError):
        adapter.invoke(decision, 'raw text')
    assert adapter.invoke_calls == 0

    other_route = FakeProviderRoute()
    other_decision = _resolve(other_route)
    with pytest.raises(UnknownReservation):
        adapter.invoke(other_decision, _envelope())


def test_no_network_when_socket_is_patched(monkeypatch):
    attempts = []

    def boom(*a, **k):
        attempts.append(a)
        raise OSError('network disabled')

    monkeypatch.setattr(socket, 'create_connection', boom)
    monkeypatch.setattr(socket, 'getaddrinfo', boom)

    route1, adapter1 = _rig()
    dec1 = _resolve(route1)
    adapter1.invoke(dec1, _envelope())

    route2, adapter2 = _rig(errors={'script_generation': 'upstream 500'})
    dec2 = _resolve(route2)
    adapter2.invoke(dec2, _envelope())

    assert attempts == []
    with pytest.raises(OSError):
        socket.getaddrinfo('example.invalid', 80)
    assert len(attempts) == 1


RECORD_FIELDS = {
    'ai_role',
    'provider_ref',
    'model_ref',
    'account_ref',
    'project_ref',
    'route_revision',
    'prompt_revision',
    'config_revision',
    'input_fingerprint',
    'output_fingerprint',
    'usage',
    'latency_ms',
    'attempt',
    'fallback_path',
    'validation_result',
    'error',
}


def test_record_field_set_and_frozen():
    assert {f.name for f in dataclasses.fields(AIInvocationRecord)} == RECORD_FIELDS
    assert AIInvocationRecord.__dataclass_params__.frozen
    record = AIInvocationRecord(**_record_kwargs())
    for name in (*RECORD_FIELDS, 'unknown_attribute'):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(record, name, 'val')
    assert isinstance(record.fallback_path, tuple)


def test_success_record_pins_route_prompt_config_and_fingerprints():
    route = FakeProviderRoute(project_ref='proj-1')
    route, adapter = _rig(route)
    env = _envelope()
    decision = _resolve(route)
    result = adapter.invoke(decision, env)
    rec = result.record
    assert rec.provider_ref == decision.provider_ref
    assert rec.model_ref == decision.model_ref
    assert rec.account_ref == decision.account_ref
    assert rec.route_revision == decision.route_revision
    assert rec.project_ref == decision.project_ref
    assert rec.prompt_revision == 'prompt-r1'
    assert rec.config_revision == 'cfg-r1'
    assert rec.input_fingerprint == fingerprint_envelope(env)
    assert rec.output_fingerprint == fingerprint_output(result.output)
    assert len(rec.input_fingerprint) == 64 and set(rec.input_fingerprint) <= set('0123456789abcdef')
    assert len(rec.output_fingerprint) == 64 and set(rec.output_fingerprint) <= set('0123456789abcdef')
    assert rec.fallback_path == (decision.provider_ref,)
    assert rec.attempt == 1
    assert rec.latency_ms == 0
    assert rec.usage.cost_class == decision.estimated_cost_class
    assert rec.validation_result == 'not_run'
    assert rec.error is None
    assert adapter.records == [rec]
    assert AIInvocationResult.__dataclass_params__.frozen


def test_record_payload_is_complete_and_json_safe():
    record = AIInvocationRecord(**_record_kwargs())
    payload = record.to_payload()
    assert set(payload) == RECORD_FIELDS
    assert payload['usage'] == {'input_tokens': 1, 'output_tokens': 2, 'cost_class': 'low'}
    assert payload['fallback_path'] == ['p']
    assert json.loads(record.to_json()) == payload


@pytest.mark.parametrize(
    'name',
    ('ai_role', 'provider_ref', 'model_ref', 'account_ref', 'route_revision', 'prompt_revision', 'config_revision'),
)
@pytest.mark.parametrize('value', ('', None, 5))
def test_record_string_fields_reject_invalid(name, value):
    with pytest.raises(ValueError):
        AIInvocationRecord(**_record_kwargs(**{name: value}))


def test_record_without_prompt_revision_is_rejected():
    kwargs = _record_kwargs()
    del kwargs['prompt_revision']
    with pytest.raises(TypeError):
        AIInvocationRecord(**kwargs)


@pytest.mark.parametrize(
    'key,val',
    [
        ('attempt', 0),
        ('attempt', True),
        ('latency_ms', -1),
        ('input_fingerprint', 'abc'),
        ('input_fingerprint', 'A' * 64),
        ('output_fingerprint', None),
        ('validation_result', 'maybe'),
        ('fallback_path', ()),
        ('fallback_path', 'p'),
        ('error', 'x'),
        ('project_ref', ''),
    ],
)
def test_record_rejects_invalid_values(key, val):
    with pytest.raises(ValueError):
        AIInvocationRecord(**_record_kwargs(**{key: val}))


def test_record_and_usage_types():
    with pytest.raises(TypeError):
        AIInvocationRecord(**_record_kwargs(usage={'input_tokens': 1}))
    with pytest.raises(ValueError):
        InvocationUsage(-1, 0, 'low')


def test_record_rejects_unredacted_error():
    with pytest.raises(ValueError):
        AIInvocationRecord(**_record_kwargs(output_fingerprint=None, error=f'401 api_key={CANARY}'))
    rec = AIInvocationRecord(**_record_kwargs(output_fingerprint=None, error='rate limit exceeded'))
    assert rec.output_fingerprint is None


def test_redact_error_masks_secret_shapes():
    texts = [
        f'api_key={CANARY}',
        f'{{"api_key": "{CANARY}"}}',
        f'Authorization: Bearer {CANARY}',
        f'access_token: {CANARY}',
        f'refresh_token={CANARY}',
        f'secret_value={CANARY}',
        f'password={CANARY}',
        f'Bearer {CANARY}',
        'key sk-abcdef123456 leaked',
    ]
    for text in texts:
        out = redact_error(text)
        assert CANARY not in out
        assert 'abcdef123456' not in out
        assert REDACTED in out
        assert redact_error(out) == out

    assert redact_error(f'boom {CANARY} boom', (CANARY,)) == f'boom {REDACTED} boom'
    assert redact_error('rate limit exceeded, retry later') == 'rate limit exceeded, retry later'
    with pytest.raises(TypeError):
        redact_error('msg', known_secrets='abc')
    with pytest.raises(TypeError):
        redact_error(5)


def test_canary_in_fake_error_never_reaches_record_surfaces():
    configs = [
        dict(errors={'script_generation': f'upstream 401 api_key={CANARY}; Authorization: Bearer {CANARY}'}),
        dict(errors={'script_generation': f'upstream failure for {CANARY}'}, known_secrets=(CANARY,)),
    ]
    for kw in configs:
        route, adapter = _rig(**kw)
        result = adapter.invoke(_resolve(route), _envelope())
        rec = result.record
        assert result.output is None
        assert rec.error is not None
        assert REDACTED in rec.error
        assert rec.output_fingerprint is None
        assert rec.validation_result == 'not_run'
        surfaces = [
            repr(rec),
            str(rec),
            repr(result),
            json.dumps(rec.to_payload()),
            rec.to_json(),
            json.dumps(dataclasses.asdict(rec), default=str),
            str(rec.to_payload()),
        ]
        for s in surfaces:
            assert CANARY not in s
        assert len(rec.input_fingerprint) == 64 and set(rec.input_fingerprint) <= set('0123456789abcdef')


def test_result_requires_output_exactly_when_no_error():
    ok = AIInvocationRecord(**_record_kwargs())
    bad = AIInvocationRecord(**_record_kwargs(output_fingerprint=None, error='boom'))
    with pytest.raises(ValueError):
        AIInvocationResult(record=ok, output=None)
    with pytest.raises(ValueError):
        AIInvocationResult(record=bad, output=ModelOutput(text='x', proposed_refs=()))
    r_ok = AIInvocationResult(record=ok, output=ModelOutput(text='x', proposed_refs=()))
    r_bad = AIInvocationResult(record=bad, output=None)
    assert r_ok.output is not None
    assert r_bad.output is None
    with pytest.raises(TypeError):
        AIInvocationResult(record='x', output=None)


def test_fingerprints_are_deterministic_and_input_sensitive():
    base = fingerprint_envelope(_envelope())
    assert base == fingerprint_envelope(_envelope())
    assert base != fingerprint_envelope(_envelope(text='khác'))
    assert base != fingerprint_envelope(_envelope(prompt_revision='prompt-r2'))
    assert base != fingerprint_envelope(_envelope(instructions='Different'))

    expected_output_fp = hashlib.sha256(
        json.dumps({'text': 't', 'proposed_refs': []}, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    ).hexdigest()
    assert fingerprint_output(ModelOutput(text='t', proposed_refs=())) == expected_output_fp
    assert fingerprint_output(ModelOutput(text='t', proposed_refs=())) != fingerprint_output(ModelOutput(text='other', proposed_refs=()))

    with pytest.raises(TypeError):
        fingerprint_envelope('x')
    with pytest.raises(TypeError):
        fingerprint_output('x')


ALLOWED_IMPORTS = {
    '__future__',
    'collections.abc',
    'copy',
    'dataclasses',
    'hashlib',
    'json',
    're',
    'types',
    'typing',
    'creative.domain.invocation',
    'creative.domain.untrusted',
}
NETWORK = (
    'socket',
    'ssl',
    'http',
    'urllib',
    'requests',
    'httpx',
    'aiohttp',
    'subprocess',
    'asyncio',
    'os',
    'pathlib',
    'ftplib',
    'smtplib',
)


def test_sources_stay_inside_import_allowlist():
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                prefix = '.' * node.level
                mod = node.module or ''
                found.add(f'{prefix}{mod}')
        assert found <= ALLOWED_IMPORTS, f'{path} imports {found - ALLOWED_IMPORTS}'
        for name in found:
            for net in NETWORK:
                assert name != net and not name.startswith(f'{net}.'), f'{path} imports forbidden network module {name}'


def test_test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-AI-010, CT-AI-ROUTE-001, TST-SEC-INV-012' in doc.splitlines()
