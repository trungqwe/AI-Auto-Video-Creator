"""E-14: Port TTS, route J, fake adapter và TtsInvocationRecord (CT-AI-ROUTE-001, CT-AI-ROUTE-002).

coveredIds: TST-SEC-INV-012, CT-AI-ROUTE-001, CT-AI-ROUTE-002
"""
import ast
import copy
import dataclasses
import hashlib
import inspect
import io
import json
import pathlib
import socket
import wave
import pytest

from voice.adapters.fake_tts import (
    FakeFailure,
    FakeTtsEngine,
    FakeVoiceRoute,
    UnknownReservation,
    fake_rate_limit,
    fake_timeout,
)
from voice.domain.tts_invocation import (
    BINDING_VERSION,
    ERROR_RATE_LIMIT,
    ERROR_TIMEOUT,
    FALLBACK_NOT_ALLOWED,
    FORBIDDEN_FIELD,
    FallbackNotAllowed,
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
    TtsAttemptPolicy,
    TtsInvocationRecord,
    TtsProviderError,
    TtsRunOutcome,
    TtsSynthesis,
    UsageMetrics,
    VALIDATION_RESULTS,
    WRONG_TYPE,
    fingerprint_tts_input,
    parse_attempt_policy,
    plan_provider_path,
    redact_error,
    run_tts_attempts,
    validate_provider_route_decision,
    validate_provider_route_request,
)
from voice.domain.voice_track import (
    INPUT_NOT_READY,
    ScriptBindingError,
    VoiceTrackRejected,
)
from voice.ports.script_text import ScriptText
from voice.ports.tts import TtsEnginePort, VoiceRoutePort

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'j-provider-route.json'
ROUTE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
VOICE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
DOMAIN_SOURCE = ROOT / 'src' / 'voice' / 'domain' / 'tts_invocation.py'
PORT_SOURCE = ROOT / 'src' / 'voice' / 'ports' / 'tts.py'
FAKE_SOURCE = ROOT / 'src' / 'voice' / 'adapters' / 'fake_tts.py'
CANARY = 'canary-7f3a9c1e-not-a-real-secret'
REQUEST = 'ProviderRouteRequest'
DECISION = 'ProviderRouteDecision'
AI_ROLE = 'voice_synthesis'  # GIẢ ĐỊNH IMPL-PLAN-E §7, ai_role thật do J đăng ký ở CONV-E-11
PRIMARY = 'fake-tts-provider'
VALIDATORS = {REQUEST: validate_provider_route_request, DECISION: validate_provider_route_decision}


def _binding_entity(name: str) -> dict:
    entities = json.loads(BINDING_PATH.read_text(encoding='utf-8'))['entities']
    return next(e for e in entities if e['name'] == name)


def _route_fixture(name: str) -> dict:
    return json.loads(ROUTE_FIXTURE.read_text(encoding='utf-8'))['entities'][name]


def _derive(entity: dict) -> tuple[dict, dict, dict, tuple]:
    fields = entity.get('fields', [])
    req = {f['name']: f['type'] for f in fields if f.get('required', False)}
    opt = {f['name']: f['type'] for f in fields if not f.get('required', False)}
    items = {f['name']: f['items'] for f in fields if 'items' in f}
    forbidden = tuple(entity.get('forbidden_fields', ()))
    return (req, opt, items, forbidden)


def _route_request(**extra) -> dict:
    base = copy.deepcopy(_route_fixture(REQUEST)['valid'][0])
    base['ai_role'] = AI_ROLE
    base.update(extra)
    return base


def _decision_payload(**extra) -> dict:
    base = copy.deepcopy(_route_fixture(DECISION)['valid'][0])
    base.update(extra)
    return base


def _voice_request() -> dict:
    return copy.deepcopy(json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))['entities']['VoiceTrackRequest']['valid'][0])


def _script(request=None, text='Xin chào') -> ScriptText:
    if request is None:
        request = _voice_request()
    return ScriptText(script_version_id=request['script_version_id'], text=text, script_fingerprint=request['script_fingerprint'])


def _issues(validator, payload) -> list[tuple[str, str]]:
    return [(i.code, i.field) for i in validator(payload)]


# --- Phần 2: test binding và validator ---


def test_binding_constants_match_binding():
    assert _derive(_binding_entity(REQUEST)) == (dict(ROUTE_REQUEST_REQUIRED), dict(ROUTE_REQUEST_OPTIONAL), {}, ())
    assert _derive(_binding_entity(DECISION)) == (dict(ROUTE_DECISION_REQUIRED), dict(ROUTE_DECISION_OPTIONAL), dict(ROUTE_DECISION_ITEMS), tuple(ROUTE_DECISION_FORBIDDEN))
    assert tuple(ROUTE_DECISION_FORBIDDEN) == ('secret_value', 'api_key', 'access_token', 'refresh_token')
    assert BINDING_VERSION == json.loads(BINDING_PATH.read_text(encoding='utf-8'))['binding_version']


def test_drift_comparison_detects_mutated_binding():
    expected = _derive(_binding_entity(DECISION))
    assert expected[0] and expected[3]
    b1 = copy.deepcopy(_binding_entity(DECISION))
    f_rev = next(f for f in b1['fields'] if f['name'] == 'route_revision')
    f_rev['required'] = False
    b2 = copy.deepcopy(_binding_entity(DECISION))
    b2['forbidden_fields'].remove('api_key')
    assert _derive(b1) != expected
    assert _derive(b2) != expected


CASES = [(e, c) for e in (REQUEST, DECISION) for c in _route_fixture(e)['invalid']]


def test_fixture_has_required_cases():
    assert {c['case'] for _, c in CASES} >= {'missing_data_sensitivity', 'api_key_leaked', 'missing_route_revision', 'fallback_order_as_string'}


@pytest.mark.parametrize('entity,case', CASES, ids=[e + '-' + c['case'] for e, c in CASES])
def test_fixture_invalid_case_returns_expected_issue(entity, case):
    expected = case['expected_error']
    assert _issues(VALIDATORS[entity], case['payload']) == [(expected['code'], expected['field'])]


def test_fixture_valid_payloads_have_no_issues():
    for entity in (REQUEST, DECISION):
        for payload in _route_fixture(entity)['valid']:
            assert _issues(VALIDATORS[entity], payload) == []


def test_each_missing_required_field_is_reported():
    for entity, required in ((REQUEST, ROUTE_REQUEST_REQUIRED), (DECISION, ROUTE_DECISION_REQUIRED)):
        assert len(required) > 0
        for name in required:
            payload = copy.deepcopy(_route_fixture(entity)['valid'][0])
            del payload[name]
            assert _issues(VALIDATORS[entity], payload) == [(MISSING_REQUIRED, name)]


WRONG = [
    (REQUEST, 'ai_role', 5),
    (REQUEST, 'job_ref', None),
    (REQUEST, 'config_refs', 'x'),
    (REQUEST, 'quality_latency_cost_bounds', []),
    (REQUEST, 'allowed_fallbacks', 'x'),
    (REQUEST, 'health_quota_ref', 5),
    (DECISION, 'provider_ref', 5),
    (DECISION, 'fallback_order', 'gemini'),
    (DECISION, 'fallback_order', None),
    (DECISION, 'rationale_codes', [1]),
    (DECISION, 'project_ref', 5),
    (DECISION, 'estimated_cost_class', None),
]


@pytest.mark.parametrize('entity,field,value', WRONG)
def test_field_counterexamples_are_wrong_type(entity, field, value):
    payload = copy.deepcopy(_route_fixture(entity)['valid'][0])
    payload[field] = value
    assert _issues(VALIDATORS[entity], payload) == [(WRONG_TYPE, field)]


def test_optional_nullable_and_unknown_fields_are_accepted():
    for entity, field in ((REQUEST, 'health_quota_ref'), (DECISION, 'project_ref')):
        for val in ('ref-1', None):
            payload = copy.deepcopy(_route_fixture(entity)['valid'][0])
            payload[field] = val
            assert _issues(VALIDATORS[entity], payload) == []
        payload = copy.deepcopy(_route_fixture(entity)['valid'][0])
        payload['x_future_optional_field'] = {'additive': True}
        assert _issues(VALIDATORS[entity], payload) == []


def test_non_mapping_payload_is_wrong_type():
    for entity in (REQUEST, DECISION):
        for bad in (None, [], 'payload'):
            assert _issues(VALIDATORS[entity], bad) == [(WRONG_TYPE, '$')]

# --- Phần 3: forbidden_fields và ProviderRouteDecision ---


def _leak(name: str, position: int) -> dict:
    payload = _decision_payload()
    if position == 0:
        payload[name] = CANARY
    elif position == 1:
        payload['extra'] = {'deep': {'deeper': {name: CANARY}}}
    elif position == 2:
        payload['fallback_order'] = [{'meta': {name: CANARY}}]
    elif position == 3:
        payload['fallback_order'] = [[{name: CANARY}]]
    elif position == 4:
        payload['fallback_order'] = ({name: CANARY},)
    else:
        payload[name.upper()] = CANARY
    return payload


def test_decision_forbidden_fields_rejected_at_every_depth():
    assert len(ROUTE_DECISION_FORBIDDEN) == 4
    for name in ROUTE_DECISION_FORBIDDEN:
        for position in range(6):
            payload = _leak(name, position)
            assert _issues(validate_provider_route_decision, payload) == [(FORBIDDEN_FIELD, name)]
            with pytest.raises(RouteContractViolation) as excinfo:
                ProviderRouteDecision.from_payload(payload)
            assert CANARY not in str(excinfo.value)
            assert CANARY not in repr(excinfo.value)


def test_decision_constructor_rejects_nested_api_key():
    kwargs = {**_decision_payload(), 'fallback_order': ({'api_key': CANARY},)}
    with pytest.raises(RouteContractViolation) as excinfo:
        ProviderRouteDecision(**kwargs)
    assert [(i.code, i.field) for i in excinfo.value.issues] == [(FORBIDDEN_FIELD, 'api_key')]
    assert CANARY not in str(excinfo.value)
    assert CANARY not in repr(excinfo.value)


def test_route_request_with_secret_key_is_rejected():
    for name in ROUTE_DECISION_FORBIDDEN:
        payload = _route_request()
        payload['quality_latency_cost_bounds'] = {'nested': [{name: CANARY}]}
        assert _issues(validate_provider_route_request, payload) == [(FORBIDDEN_FIELD, name)]


def test_decision_round_trips_fixture_and_is_frozen():
    decision = ProviderRouteDecision.from_payload(_decision_payload())
    assert decision.to_payload() == _decision_payload()
    assert isinstance(decision.rationale_codes, tuple)
    assert isinstance(decision.fallback_order, tuple)
    assert ProviderRouteDecision.__dataclass_params__.frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.route_revision = 'x'
    with_project = ProviderRouteDecision.from_payload(_decision_payload(project_ref='proj-1'))
    assert with_project.to_payload()['project_ref'] == 'proj-1'
    assert 'project_ref' not in decision.to_payload()
    assert ProviderRouteDecision.from_payload({**_decision_payload(), 'x_future': 1}).to_payload() == _decision_payload()


def test_decision_rejects_invalid_fixture_cases_and_bad_values():
    for case in _route_fixture(DECISION)['invalid']:
        with pytest.raises(RouteContractViolation) as excinfo:
            ProviderRouteDecision.from_payload(case['payload'])
        assert (excinfo.value.issues[0].code, excinfo.value.issues[0].field) == (case['expected_error']['code'], case['expected_error']['field'])
    for bad in ({'fallback_order': 'gemini'}, {'fallback_order': [{'plain': 'dict'}]}, {'route_revision': None}):
        with pytest.raises(RouteContractViolation):
            ProviderRouteDecision(**{**_decision_payload(), **bad})

# --- Phần 4: TtsInvocationRecord ---


def _record_kwargs(**over) -> dict:
    d = dict(
        provider_ref='p',
        model_ref='m',
        account_ref='a',
        route_revision='route-v1',
        input_fingerprint='a' * 64,
        usage_metrics={'characters': 5},
        latency_ms=5,
        attempt=1,
        fallback_path=('p',),
        validation_result='not_run',
        voice_revision='voice-r1',
        output_fingerprint='b' * 64,
    )
    d.update(over)
    return d


def _error_kwargs(**over) -> dict:
    return _record_kwargs(**{
        'voice_revision': None,
        'output_fingerprint': None,
        'error': 'rate limit exceeded',
        'error_code': ERROR_RATE_LIMIT,
        **over,
    })


RECORD_FIELDS = {
    'provider_ref', 'model_ref', 'account_ref', 'project_ref', 'route_revision',
    'voice_revision', 'input_fingerprint', 'output_fingerprint', 'usage_metrics',
    'latency_ms', 'attempt', 'fallback_path', 'validation_result', 'error', 'error_code'
}


def test_record_field_set_and_frozen():
    record = TtsInvocationRecord(**_record_kwargs())
    assert {f.name for f in dataclasses.fields(TtsInvocationRecord)} == RECORD_FIELDS
    assert TtsInvocationRecord.__dataclass_params__.frozen
    for name in (*RECORD_FIELDS, 'unknown_attribute'):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(record, name, 'v')
    assert isinstance(record.fallback_path, tuple)
    with pytest.raises(TypeError):
        record.usage_metrics['x'] = 1
    source = {'characters': 5}
    record2 = TtsInvocationRecord(**_record_kwargs(usage_metrics=source))
    source['characters'] = 99
    assert record2.usage_metrics['characters'] == 5
    assert isinstance(record2.usage_metrics, UsageMetrics)


def test_record_payload_is_complete_and_json_safe():
    record = TtsInvocationRecord(**_record_kwargs())
    payload = record.to_payload()
    assert set(payload) == RECORD_FIELDS
    assert payload['usage_metrics'] == {'characters': 5}
    assert type(payload['usage_metrics']) is dict
    assert payload['fallback_path'] == ['p']
    assert payload['project_ref'] is None
    assert json.loads(record.to_json()) == payload
    assert payload['voice_revision'] == 'voice-r1'


INVALID = [
    ('provider_ref', ''),
    ('provider_ref', None),
    ('model_ref', 5),
    ('account_ref', ''),
    ('route_revision', None),
    ('attempt', 0),
    ('attempt', True),
    ('latency_ms', -1),
    ('latency_ms', True),
    ('input_fingerprint', 'abc'),
    ('input_fingerprint', 'A' * 64),
    ('output_fingerprint', None),
    ('voice_revision', None),
    ('validation_result', 'maybe'),
    ('fallback_path', ()),
    ('fallback_path', 'p'),
    ('fallback_path', ('x',)),
    ('project_ref', ''),
    ('error', 'x'),
    ('error_code', 'x'),
]


@pytest.mark.parametrize('key,value', INVALID)
def test_record_rejects_invalid_values(key, value):
    with pytest.raises(ValueError):
        TtsInvocationRecord(**_record_kwargs(**{key: value}))


def test_record_usage_metrics_rules():
    with pytest.raises(TypeError):
        TtsInvocationRecord(**_record_kwargs(usage_metrics=[1]))
    with pytest.raises(ValueError):
        TtsInvocationRecord(**_record_kwargs(usage_metrics={'nested': [{'api_key': CANARY}]}))
    assert VALIDATION_RESULTS == ('not_run', 'passed', 'failed')


def test_error_record_rules():
    rec = TtsInvocationRecord(**_error_kwargs())
    assert rec.output_fingerprint is None
    assert rec.voice_revision is None
    for bad in (
        _error_kwargs(error='401 api_key=' + CANARY),
        _error_kwargs(output_fingerprint='b' * 64),
        _error_kwargs(voice_revision='voice-r1'),
        _error_kwargs(error_code=None),
        _error_kwargs(error=''),
    ):
        with pytest.raises(ValueError):
            TtsInvocationRecord(**bad)
    valid_rec = TtsInvocationRecord(**_error_kwargs())
    assert CANARY not in repr(valid_rec)

# --- Phần 5: TtsProviderError, redact, fingerprint ---


def test_provider_error_carries_code_retryable_and_redacted_message():
    err = TtsProviderError(ERROR_TIMEOUT, 'timeout api_key=' + CANARY, retryable=True, latency_ms=7)
    assert (err.code, err.retryable, err.latency_ms) == (ERROR_TIMEOUT, True, 7)
    assert REDACTED in err.message and CANARY not in err.message
    for surface in (str(err), repr(err), err.message, repr(err.args)):
        assert CANARY not in surface
    err2 = TtsProviderError(ERROR_RATE_LIMIT, 'quota hit for ' + CANARY, retryable=False, known_secrets=(CANARY,))
    assert err2.message == 'quota hit for ' + REDACTED and err2.retryable is False
    for bad in ('yes', 1, None):
        with pytest.raises(TypeError):
            TtsProviderError(ERROR_TIMEOUT, 'x', retryable=bad)
    with pytest.raises(ValueError):
        TtsProviderError('', 'x', retryable=True)
    with pytest.raises(TypeError):
        TtsProviderError(ERROR_TIMEOUT, 'x', retryable=True, known_secrets='abc')
    with pytest.raises(ValueError):
        TtsProviderError(ERROR_TIMEOUT, 'x', retryable=True, latency_ms=-1)


def test_redact_error_masks_secret_shapes():
    texts = [
        f'api_key={CANARY}',
        '{\"api_key\": \"' + CANARY + '\"}',
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


def test_input_fingerprint_is_deterministic_and_binding_checked():
    request = _voice_request()
    base = fingerprint_tts_input(_script(request), request)
    assert len(base) == 64 and set(base) <= set('0123456789abcdef')
    assert base == fingerprint_tts_input(_script(request), request)
    changed = {**request, 'voice_profile_ref': 'other-voice'}
    assert fingerprint_tts_input(_script(changed), changed) != base
    styled = {**request, 'style_parameters': {'pace': 'slow'}}
    assert fingerprint_tts_input(_script(styled), styled) != base
    assert fingerprint_tts_input(_script(request, text='khác'), request) == base
    other = ScriptText(script_version_id=request['script_version_id'], text='x', script_fingerprint='f' * 64)
    with pytest.raises(ScriptBindingError):
        fingerprint_tts_input(other, request)

# --- Phần 6: fake route và fake engine ---


def _rig(**kw) -> tuple[FakeVoiceRoute, FakeTtsEngine]:
    route = FakeVoiceRoute()
    return route, FakeTtsEngine(route, **kw)


def _resolve(route: FakeVoiceRoute, **extra) -> ProviderRouteDecision:
    return route.resolve(_route_request(**extra))


def test_fakes_satisfy_ports_and_signatures():
    route, engine = _rig()
    assert isinstance(route, VoiceRoutePort) and isinstance(engine, TtsEnginePort)
    assert not isinstance(object(), VoiceRoutePort) and not isinstance(object(), TtsEnginePort)
    assert list(inspect.signature(VoiceRoutePort.resolve).parameters) == ['self', 'request']
    assert list(inspect.signature(TtsEnginePort.synthesize).parameters) == ['self', 'decision', 'script_text', 'request']


def test_fake_route_returns_valid_decision_counts_and_rejects_invalid_request():
    route = FakeVoiceRoute()
    d1 = _resolve(route, allowed_fallbacks=['fb-1'])
    assert validate_provider_route_decision(d1.to_payload()) == []
    assert d1.fallback_order == ('fb-1',)
    assert route.resolve_calls == 1
    d2 = _resolve(route)
    assert d2.capacity_reservation_ref != d1.capacity_reservation_ref
    assert route.role_for_reservation(d1.capacity_reservation_ref) == AI_ROLE
    with pytest.raises(UnknownReservation):
        route.role_for_reservation('nope')
    case = _route_fixture(REQUEST)['invalid'][0]
    with pytest.raises(RouteContractViolation) as excinfo:
        route.resolve(case['payload'])
    assert [(i.code, i.field) for i in excinfo.value.issues] == [(case['expected_error']['code'], case['expected_error']['field'])]
    assert route.resolve_calls == 3
    leaky = _route_request()
    leaky['quality_latency_cost_bounds'] = {'api_key': CANARY}
    with pytest.raises(RouteContractViolation) as excinfo2:
        route.resolve(leaky)
    assert CANARY not in str(excinfo2.value) and CANARY not in repr(excinfo2.value)


def test_engine_returns_wav_of_scripted_duration_and_counts_calls():
    route, engine = _rig(duration_ms=1500, sample_rate=8000, voice_revision='voice-r7', latency_ms=12)
    decision = _resolve(route)
    request = _voice_request()
    script = _script(request)
    result = engine.synthesize(decision, script, request)
    assert isinstance(result, TtsSynthesis)
    with wave.open(io.BytesIO(result.audio_bytes), 'rb') as wav:
        assert wav.getframerate() == 8000
        assert wav.getnchannels() == 1
        assert wav.getnframes() * 1000 // wav.getframerate() == 1500
    assert result.voice_revision == 'voice-r7'
    assert result.latency_ms == 12
    assert result.usage_metrics['characters'] == len(script.text)
    assert engine.synthesize_calls == 1
    assert engine.calls_by_provider == {decision.provider_ref: 1}
    again = engine.synthesize(decision, script, request)
    assert again.audio_bytes == result.audio_bytes
    assert engine.synthesize_calls == 2


def test_engine_rejects_bad_input_before_counting():
    route, engine = _rig()
    decision = _resolve(route)
    request = _voice_request()
    for bad in [
        ({}, _script(request), request),
        (decision, 'raw text', request),
        (decision, _script(request), 'request'),
    ]:
        with pytest.raises(TypeError):
            engine.synthesize(*bad)
    wrong = ScriptText(script_version_id=request['script_version_id'], text='x', script_fingerprint='f' * 64)
    with pytest.raises(ScriptBindingError):
        engine.synthesize(decision, wrong, request)
    other_route = FakeVoiceRoute()
    other_decision = other_route.resolve(_route_request())
    with pytest.raises(UnknownReservation):
        engine.synthesize(other_decision, _script(request), request)
    assert engine.synthesize_calls == 0

# --- Phần 7: lỗi của fake, kịch bản, mạng, constructor ---


def test_engine_raises_timeout_and_rate_limit_as_retryable_redacted_errors():
    for failure, code in (
        (fake_timeout('timeout api_key=' + CANARY), ERROR_TIMEOUT),
        (fake_rate_limit('429 Authorization: Bearer ' + CANARY), ERROR_RATE_LIMIT),
    ):
        route, engine = _rig(scripts={PRIMARY: [failure]})
        request = _voice_request()
        with pytest.raises(TtsProviderError) as excinfo:
            engine.synthesize(_resolve(route), _script(request), request)
        err = excinfo.value
        assert err.code == code
        assert err.retryable is True
        assert REDACTED in err.message
        assert CANARY not in err.message and CANARY not in repr(err)
        assert engine.synthesize_calls == 1
    route, engine = _rig(scripts={PRIMARY: [FakeFailure('upstream', 'bad ' + CANARY, False)]}, known_secrets=(CANARY,))
    with pytest.raises(TtsProviderError) as excinfo2:
        engine.synthesize(_resolve(route), _script(request), request)
    err2 = excinfo2.value
    assert err2.retryable is False
    assert err2.message == 'bad ' + REDACTED


def test_scripts_advance_per_provider_and_repeat_last():
    route, engine = _rig(scripts={PRIMARY: [fake_timeout(), 'ok']})
    decision = _resolve(route)
    request = _voice_request()
    script = _script(request)
    with pytest.raises(TtsProviderError):
        engine.synthesize(decision, script, request)
    s2 = engine.synthesize(decision, script, request)
    assert isinstance(s2, TtsSynthesis)
    s3 = engine.synthesize(decision, script, request)
    assert isinstance(s3, TtsSynthesis)
    assert engine.calls_by_provider == {PRIMARY: 3}


def test_fakes_open_no_network_when_socket_is_patched(monkeypatch):
    attempts = []
    def boom(*a, **k):
        attempts.append(a)
        raise OSError('network disabled')
    monkeypatch.setattr(socket, 'create_connection', boom)
    monkeypatch.setattr(socket, 'getaddrinfo', boom)
    route, engine = _rig(scripts={PRIMARY: ['ok', fake_timeout()]})
    decision = _resolve(route)
    request = _voice_request()
    engine.synthesize(decision, _script(request), request)
    with pytest.raises(TtsProviderError):
        engine.synthesize(decision, _script(request), request)
    assert attempts == []
    with pytest.raises(OSError):
        socket.getaddrinfo('example.invalid', 80)
    assert len(attempts) == 1


def test_engine_constructor_validation():
    route = FakeVoiceRoute()
    for bad_call in (
        lambda: FakeTtsEngine(route, duration_ms=0),
        lambda: FakeTtsEngine(route, sample_rate=-1),
        lambda: FakeTtsEngine(route, scripts={PRIMARY: []}),
        lambda: FakeTtsEngine(route, scripts={PRIMARY: ['bogus']}),
        lambda: FakeTtsEngine(route, voice_revision=''),
    ):
        with pytest.raises(ValueError):
            bad_call()
    for bad_call in (
        lambda: FakeTtsEngine('route'),
        lambda: FakeTtsEngine(route, known_secrets='abc'),
    ):
        with pytest.raises(TypeError):
            bad_call()

# --- Phần 8a: policy và fallback path ---


def test_attempt_policy_requires_both_limits_from_input():
    for missing in (None, {}, {'max_attempts': 3}, {'max_attempts_per_provider': 2}, {'max_attempts': None, 'max_attempts_per_provider': 2}):
        with pytest.raises(VoiceTrackRejected) as excinfo:
            parse_attempt_policy(missing)
        assert excinfo.value.code == INPUT_NOT_READY and excinfo.value.reason == 'missing_attempt_policy'
    policy = parse_attempt_policy({'max_attempts': 3, 'max_attempts_per_provider': 2})
    assert (policy.max_attempts, policy.max_attempts_per_provider) == (3, 2)
    assert TtsAttemptPolicy.__dataclass_params__.frozen
    for bad in (0, -1, True, 2.5, '3'):
        with pytest.raises(ValueError):
            parse_attempt_policy({'max_attempts': bad, 'max_attempts_per_provider': 1})
        with pytest.raises(ValueError):
            parse_attempt_policy({'max_attempts': 1, 'max_attempts_per_provider': bad})
    with pytest.raises(TypeError):
        parse_attempt_policy([3, 2])


def test_attempt_limits_have_no_default_in_source():
    tree = ast.parse(DOMAIN_SOURCE.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ('parse_attempt_policy', 'run_tts_attempts'):
            defaults = [d for d in node.args.defaults + node.args.kw_defaults if d is not None]
            assert defaults == []
        elif isinstance(node, ast.ClassDef) and node.name == 'TtsAttemptPolicy':
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign):
                    assert stmt.value is None


def _path_rig(allowed=('fb-1', 'fb-2')) -> tuple[dict, ProviderRouteDecision]:
    route = FakeVoiceRoute()
    request = _route_request(allowed_fallbacks=list(allowed))
    return request, route.resolve(request)


def test_plan_provider_path_follows_decision_order_within_allowed():
    request, decision = _path_rig()
    assert plan_provider_path(decision, request) == (PRIMARY, 'fb-1', 'fb-2')
    assert plan_provider_path(decision, {**request, 'allowed_fallbacks': ['fb-2', 'fb-1', 'extra']}) == (PRIMARY, 'fb-1', 'fb-2')
    request2, decision2 = _path_rig(allowed=('fb-1', PRIMARY))
    dup = dataclasses.replace(decision2, fallback_order=('fb-1', PRIMARY, 'fb-1'))
    assert plan_provider_path(dup, request2) == (PRIMARY, 'fb-1')


def test_provider_outside_allowed_fallbacks_is_rejected():
    request, decision = _path_rig()
    outside = dataclasses.replace(decision, fallback_order=('fb-1', 'paid-provider'))
    with pytest.raises(FallbackNotAllowed) as excinfo:
        plan_provider_path(outside, request)
    assert excinfo.value.provider_ref == 'paid-provider'
    assert excinfo.value.code == FALLBACK_NOT_ALLOWED
    with pytest.raises(FallbackNotAllowed):
        plan_provider_path(decision, {**request, 'allowed_fallbacks': []})
    with pytest.raises(RouteContractViolation):
        plan_provider_path(decision, {**request, 'allowed_fallbacks': 'fb-1'})
    with pytest.raises(RouteContractViolation):
        plan_provider_path(decision, {**request, 'allowed_fallbacks': ['fb-1', 5]})

# --- Phần 8b: run_tts_attempts ---

POLICY = {'max_attempts': 4, 'max_attempts_per_provider': 2}  # test-only, GIẢ ĐỊNH


def _prepare(scripts=None, allowed=('fb-1', 'fb-2'), **engine_kwargs) -> tuple[FakeTtsEngine, dict]:
    route = FakeVoiceRoute()
    engine = FakeTtsEngine(route, scripts=scripts, **engine_kwargs)
    route_request = _route_request(allowed_fallbacks=list(allowed))
    voice_request = _voice_request()
    return (engine, {
        'decision': route.resolve(route_request),
        'route_request': route_request,
        'voice_request': voice_request,
        'script_text': _script(voice_request),
    })


def _run(scripts=None, policy=POLICY, **kw) -> tuple[FakeTtsEngine, dict, TtsRunOutcome]:
    engine, args = _prepare(scripts, **kw)
    return (engine, args, run_tts_attempts(engine, policy=policy, **args))


class _BrokenEngine:
    def __init__(self, result=None):
        self.calls = 0
        self._result = result
    def synthesize(self, decision, script_text, request):
        self.calls += 1
        if self._result is None:
            raise RuntimeError('boom')
        return self._result


def test_first_attempt_success_records_route_voice_and_fingerprints():
    engine, args, outcome = _run()
    assert outcome.error is None
    assert isinstance(outcome.synthesis, TtsSynthesis)
    assert len(outcome.records) == 1
    assert engine.synthesize_calls == 1
    record = outcome.records[0]
    assert (record.provider_ref, record.model_ref, record.account_ref, record.route_revision, record.project_ref) == (
        args['decision'].provider_ref,
        args['decision'].model_ref,
        args['decision'].account_ref,
        args['decision'].route_revision,
        args['decision'].project_ref,
    )
    assert record.attempt == 1
    assert record.fallback_path == (PRIMARY,)
    assert record.voice_revision == 'fake-voice-v1'
    assert record.validation_result == 'not_run'
    assert record.error is None
    assert record.error_code is None
    assert record.input_fingerprint == fingerprint_tts_input(args['script_text'], args['voice_request'])
    assert record.output_fingerprint == hashlib.sha256(outcome.synthesis.audio_bytes).hexdigest()
    assert record.usage_metrics == outcome.synthesis.usage_metrics
    assert TtsRunOutcome.__dataclass_params__.frozen


def test_outcome_requires_exactly_one_of_synthesis_or_error():
    _, _, ok = _run()
    error = TtsProviderError(ERROR_TIMEOUT, 'timeout', retryable=True)
    with pytest.raises(ValueError):
        TtsRunOutcome(synthesis=None, records=(), error=None)
    with pytest.raises(ValueError):
        TtsRunOutcome(synthesis=ok.synthesis, records=ok.records, error=error)


def test_retryable_error_retries_same_provider_then_succeeds():
    engine, args, outcome = _run({PRIMARY: [fake_timeout(), 'ok']})
    assert outcome.error is None
    assert engine.calls_by_provider == {PRIMARY: 2}
    first, second = outcome.records
    assert (first.attempt, first.error_code, first.output_fingerprint, first.voice_revision) == (1, ERROR_TIMEOUT, None, None)
    assert (second.attempt, second.error) == (2, None)
    assert first.fallback_path == second.fallback_path == (PRIMARY,)


def test_non_retryable_error_moves_to_next_fallback_in_order():
    failure = FakeFailure('invalid_voice', 'voice rejected', False)
    engine, args, outcome = _run({PRIMARY: [failure]})
    assert outcome.error is None
    assert engine.calls_by_provider == {PRIMARY: 1, 'fb-1': 1}
    assert [r.attempt for r in outcome.records] == [1, 2]
    assert outcome.records[0].error_code == 'invalid_voice'
    assert outcome.records[0].error == 'voice rejected'
    assert outcome.records[-1].fallback_path == (PRIMARY, 'fb-1')
    assert outcome.records[-1].provider_ref == 'fb-1'


def test_per_provider_limit_then_fallback():
    engine, args, outcome = _run({PRIMARY: [fake_rate_limit()]})
    assert engine.calls_by_provider == {PRIMARY: 2, 'fb-1': 1}
    assert [r.attempt for r in outcome.records] == [1, 2, 3]
    assert [r.error_code for r in outcome.records] == [ERROR_RATE_LIMIT, ERROR_RATE_LIMIT, None]


def test_budget_exhausted_returns_last_error_without_more_calls():
    scripts = {
        PRIMARY: [fake_timeout('t-primary')],
        'fb-1': [fake_rate_limit('r-fb1')],
        'fb-2': [fake_timeout('t-fb2')],
    }
    engine, args, outcome = _run(scripts)
    assert outcome.synthesis is None
    assert isinstance(outcome.error, TtsProviderError)
    assert engine.synthesize_calls == 4
    assert engine.calls_by_provider == {PRIMARY: 2, 'fb-1': 2}
    assert outcome.error.code == ERROR_RATE_LIMIT
    assert outcome.error.message == 'r-fb1'
    assert len(outcome.records) == 4
    assert all(r.error is not None for r in outcome.records)


def test_retry_is_bounded_by_policy():
    always = {PRIMARY: [fake_timeout()], 'fb-1': [fake_timeout()], 'fb-2': [fake_timeout()]}
    engine1, _, out1 = _run(always, policy={'max_attempts': 3, 'max_attempts_per_provider': 1000})
    assert engine1.synthesize_calls == 3 and out1.error is not None
    engine2, _, out2 = _run(always, policy={'max_attempts': 1000, 'max_attempts_per_provider': 1})
    assert engine2.synthesize_calls == 3 and out2.error is not None
    assert out2.records[-1].provider_ref == 'fb-2'

# --- Phần 8c: kiểm đầu vào, canary, kiểm tĩnh ---


def test_missing_policy_or_bad_binding_makes_zero_calls():
    engine, args = _prepare()
    with pytest.raises(VoiceTrackRejected) as excinfo:
        run_tts_attempts(engine, policy=None, **args)
    assert excinfo.value.code == INPUT_NOT_READY
    with pytest.raises(VoiceTrackRejected):
        run_tts_attempts(engine, policy={'max_attempts': 3}, **args)
    wrong = ScriptText(script_version_id=args['voice_request']['script_version_id'], text='x', script_fingerprint='f' * 64)
    with pytest.raises(ScriptBindingError):
        run_tts_attempts(engine, policy=POLICY, **{**args, 'script_text': wrong})
    outside = dataclasses.replace(args['decision'], fallback_order=('fb-1', 'paid-provider'))
    with pytest.raises(FallbackNotAllowed):
        run_tts_attempts(engine, policy=POLICY, **{**args, 'decision': outside})
    assert engine.synthesize_calls == 0


def test_unexpected_engine_behaviour_is_not_swallowed():
    _, args = _prepare()
    broken = _BrokenEngine()
    with pytest.raises(RuntimeError):
        run_tts_attempts(broken, policy=POLICY, **args)
    assert broken.calls == 1
    junk = _BrokenEngine(result='not-a-synthesis')
    with pytest.raises(TypeError):
        run_tts_attempts(junk, policy=POLICY, **args)
    assert junk.calls == 1


def test_canary_never_reaches_record_error_or_outcome_surfaces():
    scripts = {
        PRIMARY: [fake_timeout('timeout api_key=' + CANARY)],
        'fb-1': [FakeFailure('upstream', 'oops ' + CANARY, False)],
    }
    _, _, outcome = _run(scripts, known_secrets=(CANARY,))
    assert outcome.error is None
    assert len(outcome.records) == 4
    errors = [r for r in outcome.records if r.error is not None]
    assert len(errors) == 3
    assert all(REDACTED in r.error for r in errors)
    surfaces = [repr(outcome)]
    for record in outcome.records:
        surfaces.append(repr(record))
        surfaces.append(str(record))
        surfaces.append(record.to_json())
        surfaces.append(str(record.to_payload()))
        surfaces.append(json.dumps(dataclasses.asdict(record), default=str))
    for surface in surfaces:
        assert CANARY not in surface


SOURCE_IMPORTS = {
    DOMAIN_SOURCE: {
        '__future__', 'collections.abc', 'copy', 'dataclasses', 'hashlib',
        'json', 're', 'types', 'typing', 'voice.domain.voice_track', 'voice.ports.script_text',
    },
    PORT_SOURCE: {
        '__future__', 'collections.abc', 'typing', 'voice.domain.tts_invocation', 'voice.ports.script_text',
    },
    FAKE_SOURCE: {
        '__future__', 'collections.abc', 'dataclasses', 'io', 'wave',
        'voice.domain.tts_invocation', 'voice.domain.voice_track', 'voice.ports.script_text',
    },
}
FORBIDDEN_MODULES = (
    'socket', 'ssl', 'http', 'urllib', 'requests', 'httpx', 'aiohttp',
    'subprocess', 'asyncio', 'os', 'pathlib', 'ftplib', 'smtplib', 'creative', 'controlplane',
)


def test_sources_stay_inside_import_allowlist():
    for path, allowed in SOURCE_IMPORTS.items():
        tree = ast.parse(path.read_text(encoding='utf-8'))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                prefix = '.' * node.level
                mod = node.module or ''
                found.add(prefix + mod)
        assert found <= allowed, f'{path.name} imports forbidden/unexpected: {found - allowed}'
        for name in found:
            for module in FORBIDDEN_MODULES:
                assert name != module and not name.startswith(module + '.'), f'{path.name} imports forbidden {name}'


def test_test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: TST-SEC-INV-012, CT-AI-ROUTE-001, CT-AI-ROUTE-002' in (doc or '').splitlines()
