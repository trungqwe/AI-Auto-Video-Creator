"""D-15: lỗi provider và fallback (timeout, rate limit, sai schema, hallucinated ref; fallback theo decision của J giao allowed_fallbacks).

coveredIds: CT-AI-ROUTE-002, CT-AI-010
"""
from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import socket

import pytest

from controlplane.domain.concurrency import RevisionConflictError
from creative.adapters.fake_ai import FakeProviderRoute
from creative.adapters.memory import InMemoryUnitOfWork
from creative.application.pipeline import HALLUCINATED_REF, INPUT_NOT_READY, SCHEMA_VIOLATION, PipelineRejected
from creative.application.provider_failure import (
    FALLBACK_CHANGES_INTENT, PROVIDER_ERROR, PROVIDER_RATE_LIMITED, PROVIDER_TIMEOUT, PROVIDER_UNREACHABLE,
    ProviderCallStatus, ProviderFailureHandler, ProviderFailurePolicy, classify_provider_error, parse_failure_policy)
from creative.domain.invocation import (
    AIInvocationRecord, AIInvocationResult, InvocationUsage, fingerprint_envelope, fingerprint_output, redact_error)
from creative.domain.output_metadata import OUTPUT_LANGUAGE, OutputMetadata
from creative.domain.ref_resolver import RefResolver, ResourceRef
from creative.domain.untrusted import PromptEnvelope, UntrustedText, read_model_output

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'creative' / 'application' / 'provider_failure.py'
WS = 'ws-1'
KEY = f'{WS}:k-1'
PROMPT = ResourceRef(WS, 'prompt_revision', 'output_metadata', 'output_metadata-r1')
ENVELOPE = PromptEnvelope(
    prompt_ref=PROMPT, instructions='Return JSON metadata',
    data=(UntrustedText('{}', ResourceRef(WS, 'production_snapshot', 'snap-1', 'src-fp')),))
RESOLVER = RefResolver(
    workspace_id=WS, allowed_refs=[ResourceRef(WS, 'article_revision', 'a-1', 'v1')], allowed_ref_types={'article_revision'})


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError('network is forbidden in D-15 tests')

    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)


def _request(allowed=()):
    return {
        'ai_role': 'output_metadata', 'job_ref': 'job-1', 'snapshot_ref': 'snap-1',
        'config_refs': ['prompt:output_metadata@output_metadata-r1'], 'data_sensitivity': 'internal',
        'quality_latency_cost_bounds': {}, 'allowed_fallbacks': list(allowed)}


def _ref(ref_id):
    return {'workspace_id': WS, 'ref_type': 'article_revision', 'ref_id': ref_id, 'revision_id': 'v1'}


def _payload(refs=('a-1',), body=None):
    body = body if body is not None else {'title': 'Port Strike Ends', 'caption': 'Ships move again.', 'hashtags': ['#Port', '#Strike', '#Ships']}
    return {'text': json.dumps(body), 'refs': [_ref(item) for item in refs]}


def _raising(error):
    def call():
        raise error

    return ('raise', call)


OK = ('ok', _payload())
BAD_SCHEMA = ('ok', _payload(body={'title': 'only a title'}))
HALLUCINATED = ('ok', _payload(refs=('a-404',)))
TIMEOUT = ('error', 'timeout after 30s calling api_key=abc123secret')
RATE_LIMIT = ('error', 'rate limit exceeded HTTP 429 Authorization: Bearer abc.def-123')
CONNECT = ('raise', lambda: socket.create_connection(('provider.invalid', 443)))
RESOLVE = ('raise', lambda: socket.getaddrinfo('provider.invalid', 443))


class ChainRoute(FakeProviderRoute):
    """Fake route whose decision lists a fixed fallback_order, whatever allowed_fallbacks the request carries."""

    def __init__(self, order=()):
        super().__init__(provider_ref='primary')
        self._order = tuple(order)

    def resolve(self, request):
        return dataclasses.replace(super().resolve(request), fallback_order=self._order)


class ScriptedAI:
    """AIInvocationPort fake: each provider pops its next scripted outcome; a provider missing from the script raises KeyError, so an unexpected call fails the test."""

    def __init__(self, route, script):
        self._route = route
        self._script = {provider: list(outcomes) for provider, outcomes in script.items()}
        self.calls = []

    def invoke(self, decision, envelope):
        provider = decision.provider_ref
        self.calls.append(provider)
        kind, value = self._script[provider].pop(0)
        if kind == 'raise':
            value()
        fields = dict(
            ai_role=self._route.role_for_reservation(decision.capacity_reservation_ref), provider_ref=provider,
            model_ref=decision.model_ref, account_ref=decision.account_ref, project_ref=decision.project_ref,
            route_revision=decision.route_revision, prompt_revision=envelope.prompt_ref.revision_id, config_revision='cfg-1',
            input_fingerprint=fingerprint_envelope(envelope), usage=InvocationUsage(1, 1, decision.estimated_cost_class),
            latency_ms=5, attempt=1, fallback_path=(provider,), validation_result='not_run')
        if kind == 'error':
            return AIInvocationResult(record=AIInvocationRecord(**fields, error=redact_error(value)), output=None)
        output = read_model_output(value)
        record = AIInvocationRecord(**fields, output_fingerprint=fingerprint_output(output))
        return AIInvocationResult(record=record, output=output)


class SpyValidator:
    """The one validator of the stage: records which provider's output it saw, rejects schema violations and hallucinated refs."""

    def __init__(self):
        self.providers = []

    def __call__(self, result):
        self.providers.append(result.record.provider_ref)
        try:
            raw = json.loads(result.output.text)
            metadata = OutputMetadata(
                title=raw['title'], caption=raw['caption'], hashtags=tuple(raw['hashtags']), language=OUTPUT_LANGUAGE,
                source_job_ref='job-1', source_output_refs=('variant-1',), metadata_revision=1)
        except (KeyError, TypeError, ValueError) as error:
            raise PipelineRejected(SCHEMA_VIOLATION, 'invalid_output_metadata', 'output_metadata') from error
        for position, proposed in enumerate(result.output.proposed_refs):
            resolution = RESOLVER.resolve(proposed)
            if not resolution.ok:
                raise PipelineRejected(HALLUCINATED_REF, resolution.reason, f'proposed_refs[{position}]')
        return metadata


class Rig:
    def __init__(self, script, *, order=()):
        self.uow = InMemoryUnitOfWork()
        self.route = ChainRoute(order)
        self.ai = ScriptedAI(self.route, script)
        self.validator = SpyValidator()
        self.handler = ProviderFailureHandler(uow_factory=lambda: self.uow, route=self.route, ai=self.ai)

    def run(self, *, allowed=(), policy=None, key='k-1', **extra):
        policy = {'max_attempts': 3} if policy is None else policy
        return self.handler.run(
            idempotency_key=key, route_request=_request(allowed), envelope=ENVELOPE, config_revision='cfg-1',
            validator=self.validator, policy=policy, **extra)


def _old_record():
    return AIInvocationRecord(
        ai_role='output_metadata', provider_ref='primary', model_ref='fake-model', account_ref='fake-account', route_revision='r1',
        prompt_revision='output_metadata-r1', config_revision='cfg-1', input_fingerprint='a' * 64, usage=InvocationUsage(1, 1, 'free'),
        latency_ms=1, attempt=1, fallback_path=('primary',), validation_result='passed', output_fingerprint='b' * 64)


def _old_metadata(revision=1):
    return OutputMetadata(
        title='Old title', caption='Old caption', hashtags=('#One', '#Two', '#Three'), language=OUTPUT_LANGUAGE,
        source_job_ref='job-1', source_output_refs=('variant-1',), metadata_revision=revision)


def _seed(uow):
    with uow:
        uow.output_metadata.append('job-1', 1, _old_metadata())
        uow.invocations.append(f'{WS}:k-0', 1, _old_record())
        uow.commit()


def _history(uow):
    return uow.output_metadata.revisions('job-1'), uow.invocations.revisions(f'{WS}:k-0')


def test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-AI-ROUTE-002, CT-AI-010' in doc.splitlines()


def test_network_is_blocked_for_every_test():
    with pytest.raises(OSError):
        socket.create_connection(('example.com', 80))
    with pytest.raises(OSError):
        socket.getaddrinfo('example.com', 80)


FAILURES = (
    ('timeout_record', TIMEOUT, PROVIDER_TIMEOUT, 'not_run', 0),
    ('rate_limit_record', RATE_LIMIT, PROVIDER_RATE_LIMITED, 'not_run', 0),
    ('timeout_raised', _raising(TimeoutError('read timed out api_key=raw-secret-1')), PROVIDER_TIMEOUT, 'not_run', 0),
    ('connect_blocked', CONNECT, PROVIDER_UNREACHABLE, 'not_run', 0),
    ('resolve_blocked', RESOLVE, PROVIDER_UNREACHABLE, 'not_run', 0),
    ('schema_violation', BAD_SCHEMA, SCHEMA_VIOLATION, 'failed', 1),
    ('hallucinated_ref', HALLUCINATED, HALLUCINATED_REF, 'failed', 1),
)


@pytest.mark.parametrize(
    ('outcome', 'code', 'validation', 'validator_calls'), [item[1:] for item in FAILURES], ids=[item[0] for item in FAILURES])
def test_failure_kinds_become_redacted_problems_with_recorded_attempt(outcome, code, validation, validator_calls):
    rig = Rig({'primary': [outcome]})
    result = rig.run(policy={'max_attempts': 1})
    assert result.status is ProviderCallStatus.WAITING and result.output is None and result.output_revision is None
    assert result.wait_reason == 'attempt_budget_exhausted'
    assert (result.problem.code, result.problem.provider_ref, result.problem.attempt) == (code, 'primary', 1)
    (record,) = result.records
    assert (record.attempt, record.validation_result, record.fallback_path) == (1, validation, ('primary',))
    assert len(rig.validator.providers) == validator_calls
    assert [item.record for item in rig.uow.invocations.revisions(KEY)] == [record]
    text = json.dumps([problem.to_payload() for problem in result.problems]) + record.to_json()
    assert not any(secret in text for secret in ('abc123secret', 'abc.def-123', 'raw-secret-1'))


def test_known_secret_values_are_redacted_from_problem_and_record():
    rig = Rig({'primary': [_raising(TimeoutError('timed out for hunter2-private'))]})
    result = rig.run(policy={'max_attempts': 1}, known_secrets=('hunter2-private',))
    text = json.dumps(result.problem.to_payload()) + result.records[0].to_json()
    assert 'hunter2-private' not in text and '[REDACTED]' in text


def test_failures_never_delete_or_edit_old_output_or_history():
    rig = Rig({'primary': [TIMEOUT, OK]})
    _seed(rig.uow)
    before = _history(rig.uow)
    failed = rig.run(policy={'max_attempts': 1})
    assert failed.status is ProviderCallStatus.WAITING and _history(rig.uow) == before
    ok = rig.run(policy={'max_attempts': 1}, current_output_revision=1)
    assert ok.status is ProviderCallStatus.ACCEPTED and ok.output_revision == 2 and _history(rig.uow) == before
    assert len(rig.uow.invocations.revisions(KEY)) == 2
    with rig.uow:
        rig.uow.output_metadata.append('job-1', ok.output_revision, _old_metadata(2))
        rig.uow.commit()
    revisions = rig.uow.output_metadata.revisions('job-1')
    assert [item.revision for item in revisions] == [1, 2] and revisions[0] == before[0][0]
    with pytest.raises(RevisionConflictError), rig.uow:
        rig.uow.output_metadata.append('job-1', 1, _old_metadata(1))


def test_waiting_outcome_leaves_retry_to_g_and_attempt_numbers_continue():
    rig = Rig({'primary': [RATE_LIMIT, OK]})
    first = rig.run(policy={'max_attempts': 1})
    assert first.status is ProviderCallStatus.WAITING and rig.ai.calls == ['primary']
    second = rig.run(policy={'max_attempts': 1})
    assert second.status is ProviderCallStatus.ACCEPTED and rig.ai.calls == ['primary', 'primary']
    stored = rig.uow.invocations.revisions(KEY)
    assert [(item.revision, item.record.attempt) for item in stored] == [(1, 1), (2, 2)]
    assert stored[0].record == first.records[0] and stored[1].record == second.final_record


def test_fallback_follows_decision_order_intersected_with_allowed_fallbacks():
    rig = Rig({'primary': [TIMEOUT], 'fb-local': [RATE_LIMIT], 'fb-other': [OK]}, order=('fb-local', 'fb-paid', 'fb-other'))
    policy = {'max_attempts': 5, 'intent_preserving_providers': ['fb-local', 'fb-other']}
    result = rig.run(allowed=('fb-other', 'fb-local'), policy=policy)
    assert result.status is ProviderCallStatus.ACCEPTED
    assert rig.ai.calls == ['primary', 'fb-local', 'fb-other'] and result.provider_path == tuple(rig.ai.calls)
    assert result.skipped_fallbacks == ('fb-paid',)
    assert [item.attempt for item in result.records] == [1, 2, 3]
    assert [item.fallback_path for item in result.records] == [
        ('primary',), ('primary', 'fb-local'), ('primary', 'fb-local', 'fb-other')]


def test_no_fallback_when_allowed_fallbacks_is_empty_or_missing_from_decision():
    rig = Rig({'primary': [TIMEOUT]}, order=('fb-local',))
    result = rig.run(allowed=(), policy={'max_attempts': 3, 'intent_preserving_providers': ['fb-local']})
    assert rig.ai.calls == ['primary'] and result.skipped_fallbacks == ('fb-local',)
    assert result.status is ProviderCallStatus.WAITING and result.wait_reason == 'providers_exhausted'
    other = Rig({'primary': [TIMEOUT]}, order=())
    result = other.run(allowed=('fb-extra',), policy={'max_attempts': 3})
    assert other.ai.calls == ['primary'] and result.skipped_fallbacks == ()


def test_fallback_output_goes_through_the_same_validator_and_records_revisions():
    rig = Rig({'primary': [TIMEOUT], 'fb-local': [BAD_SCHEMA], 'fb-other': [OK]}, order=('fb-local', 'fb-other'))
    policy = {'max_attempts': 5, 'intent_preserving_providers': ['fb-local', 'fb-other']}
    result = rig.run(allowed=('fb-local', 'fb-other'), policy=policy)
    assert rig.validator.providers == ['fb-local', 'fb-other']
    assert result.status is ProviderCallStatus.ACCEPTED and isinstance(result.output, OutputMetadata)
    assert [(item.provider_ref, item.code) for item in result.problems] == [('primary', PROVIDER_TIMEOUT), ('fb-local', SCHEMA_VIOLATION)]
    assert [item.validation_result for item in result.records] == ['not_run', 'failed', 'passed']
    final = result.final_record
    assert (final.provider_ref, final.model_ref, final.prompt_revision, final.config_revision) == (
        'fb-other', 'fake-model', 'output_metadata-r1', 'cfg-1')
    assert final.output_fingerprint is not None
    hallucinating = Rig({'primary': [TIMEOUT], 'fb-local': [HALLUCINATED]}, order=('fb-local',))
    blocked = hallucinating.run(allowed=('fb-local',), policy={'max_attempts': 5, 'intent_preserving_providers': ['fb-local']})
    assert blocked.status is ProviderCallStatus.WAITING and blocked.output is None
    assert blocked.problem.code == HALLUCINATED_REF and blocked.wait_reason == 'providers_exhausted'


@pytest.mark.parametrize(('max_attempts', 'expected'), [(1, 1), (2, 2), (3, 3), (1000, 3)])
def test_attempt_budget_comes_from_policy_and_never_loops(max_attempts, expected):
    rig = Rig({name: [TIMEOUT] * 5 for name in ('primary', 'fb-a', 'fb-b')}, order=('fb-a', 'fb-b'))
    policy = {'max_attempts': max_attempts, 'intent_preserving_providers': ['fb-a', 'fb-b']}
    result = rig.run(allowed=('fb-a', 'fb-b'), policy=policy)
    assert len(rig.ai.calls) == expected == len(result.records)
    assert result.status is ProviderCallStatus.WAITING and result.problem == result.problems[-1]
    assert result.problem.attempt == expected
    assert result.wait_reason == ('attempt_budget_exhausted' if max_attempts <= 3 else 'providers_exhausted')


def test_missing_or_invalid_attempt_policy_is_refused_before_any_route_or_ai_call():
    rig = Rig({'primary': [OK]})
    with pytest.raises(PipelineRejected) as missing:
        rig.run(policy={})
    assert (missing.value.code, missing.value.reason) == (INPUT_NOT_READY, 'missing_attempt_policy')
    for bad in (0, -1, True, '3', 2.5):
        with pytest.raises(ValueError):
            rig.run(policy={'max_attempts': bad})
    for bad in ({'max_attempts': 1, 'on_intent_change': 'silent'}, {'max_attempts': 1, 'intent_preserving_providers': 'fb-a'}):
        with pytest.raises(ValueError):
            rig.run(policy=bad)
    assert rig.route.resolve_calls == 0 and rig.ai.calls == [] and rig.uow.invocations.revisions(KEY) == ()
    assert parse_failure_policy(ProviderFailurePolicy(max_attempts=2)).max_attempts == 2


def test_fallback_changing_intent_waits_without_calling_the_provider():
    rig = Rig({'primary': [TIMEOUT]}, order=('fb-local',))
    result = rig.run(allowed=('fb-local',), policy={'max_attempts': 3})
    assert rig.ai.calls == ['primary'] and result.status is ProviderCallStatus.WAITING
    assert result.wait_reason == FALLBACK_CHANGES_INTENT
    assert (result.problem.code, result.problem.provider_ref) == (FALLBACK_CHANGES_INTENT, 'fb-local')
    assert len(result.records) == 1 and rig.validator.providers == []


def test_fallback_changing_intent_creates_new_output_revision_when_policy_allows():
    rig = Rig({'primary': [TIMEOUT], 'fb-local': [OK]}, order=('fb-local',))
    _seed(rig.uow)
    before = _history(rig.uow)
    policy = {'max_attempts': 3, 'on_intent_change': 'new_revision'}
    result = rig.run(allowed=('fb-local',), policy=policy, current_output_revision=1)
    assert result.status is ProviderCallStatus.NEW_REVISION and result.output_revision == 2
    assert result.final_record.provider_ref == 'fb-local' and _history(rig.uow) == before


@pytest.mark.parametrize(
    ('message', 'code'),
    [
        ('Request timed out', PROVIDER_TIMEOUT), ('HTTP 429 too many requests', PROVIDER_RATE_LIMITED),
        ('rate_limit_exceeded', PROVIDER_RATE_LIMITED), ('internal server error', PROVIDER_ERROR),
    ])
def test_classify_provider_error(message, code):
    assert classify_provider_error(message) == code


def test_provider_failure_source_has_no_adapter_clock_network_import_and_no_while_loop():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    names = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    names |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    banned = {'socket', 'uuid', 'time', 'random', 'datetime'}
    assert not [name for name in names if name.split('.')[0] in banned or name.startswith('creative.adapters')]
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.While)]
