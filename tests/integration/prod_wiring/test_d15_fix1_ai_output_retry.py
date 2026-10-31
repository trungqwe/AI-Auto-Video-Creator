"""D-15-FIX1: a D command that calls AI retries a failed model output up to ai.retry.max_attempts, records every attempt durably and answers a structured problem (CP7-10, RG-09).

coveredIds: D-15-FIX1, CT-AI-ROUTE-002, CT-WF-008
"""
from __future__ import annotations

import copy
import dataclasses
import datetime
import importlib.util
import json
import pathlib
from types import MappingProxyType, SimpleNamespace

import pytest

from controlplane.api.wiring.creative import CreativeServices, creative_activity_deps, creative_activity_handlers
from controlplane.api.wiring.production_profile import load_production_profile
from controlplane.application.orchestration.job_lifecycle import JobLifecycleListener
from controlplane.application.orchestration.result_recorder import ResultRecordingDispatcher
from controlplane.application.orchestration.workflows.activities import ActivityDispatcher
from controlplane.domain.orchestration.job_waiting import WaitReason
from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.uow import TransactionManager
from creative.adapters.activity_inputs import SourceSetPin
from creative.adapters.fake_ai import FakeProviderRoute
from creative.adapters.real_ai_invocation import WaitingAIInvocationResult
from creative.application.prompts import seed_default_prompts
from creative.domain.invocation import AIInvocationRecord, AIInvocationResult, InvocationUsage, fingerprint_envelope, fingerprint_output, redact_error
from creative.domain.untrusted import read_model_output
from creative.persistence.uow import PostgresCreativeUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
NOW = datetime.datetime(2026, 10, 30, 8, 0, 0, tzinfo=datetime.timezone.utc)
ACTIVITIES = ('BuildProductionSnapshot', 'AnalyzeContent', 'GenerateStoryAngles', 'GenerateScript')


def _load_d14():
    path = ROOT / 'tests' / 'integration' / 'creative' / 'test_d14_creative_pipeline.py'
    spec = importlib.util.spec_from_file_location('pw_d15_fix1_d14_support', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D14 = _load_d14()
ARTICLE_TEXT = 'The harbor union ended its three day strike.'


class ScriptedAI:
    """AIInvocationPort: each route key (analysis, angle, script) pops its next scripted answer; a call beyond the script raises AssertionError."""

    def __init__(self, route, script):
        self.route = route
        self.script = {role: list(items) for role, items in script.items()}
        self.calls = []

    def invoke(self, decision, envelope):
        role = self.route.role_for_reservation(decision.capacity_reservation_ref)
        self.calls.append(role)
        if not self.script.get(role):
            raise AssertionError(f'unscripted AI call {len(self.calls)} for {role}')
        kind, value = self.script[role].pop(0)
        fields = dict(
            ai_role=role, provider_ref=decision.provider_ref, model_ref=decision.model_ref, account_ref=decision.account_ref,
            project_ref=decision.project_ref, route_revision=decision.route_revision, prompt_revision=envelope.prompt_ref.revision_id,
            config_revision='cfg-test', input_fingerprint=fingerprint_envelope(envelope),
            usage=InvocationUsage(1, 1, decision.estimated_cost_class), latency_ms=1, attempt=1,
            fallback_path=(decision.provider_ref,), validation_result='not_run')
        if kind == 'text':
            output = read_model_output({'text': value, 'refs': []})
            return AIInvocationResult(record=AIInvocationRecord(**fields, output_fingerprint=fingerprint_output(output)), output=output)
        record = AIInvocationRecord(**fields, error=redact_error(value))
        if kind == 'waiting':
            return WaitingAIInvocationResult(record=record, output=None, wait_reason='WAITING_PROVIDER')
        return AIInvocationResult(record=record, output=None)


def ok(body):
    return ('text', json.dumps(body))


def fenced(body):
    return ('text', '```json' + chr(10) + json.dumps(body) + chr(10) + '```')


def truncated(body):
    return ('text', json.dumps(body)[:-1])


class CurrentGrants:
    def is_grant_current(self, grant):
        return True


class SourceSets:
    def source_set(self, *, workspace_id, source_set_ref):
        return SourceSetPin(
            production_mode='single_article', eligibility_reason='eligible',
            source_refs=({'ref_type': 'article_revision', 'ref_id': 'a-1', 'revision_id': 'v1'},))


def with_attempts(profile, attempts=None):
    """A trial copy of the production profile: optional max_attempts and a voice range that fits the D14 script scenario."""
    changes = {}
    if attempts is not None:
        changes['ai'] = dataclasses.replace(profile.ai, retry=dataclasses.replace(profile.ai.retry, max_attempts=attempts))
    changes['parameters'] = MappingProxyType({
        **profile.parameters, 'voice.duration_range_ms': {'min': 5000, 'max': 20000}, 'voice.speech_rate_wpm': 120})
    return dataclasses.replace(profile, **changes)


PROFILE_ATTEMPTS = load_production_profile(PROFILE_PATH).ai.retry.max_attempts


def seed_article(db):
    revision = {
        'article_revision_id': 'v1', 'article_id': 'a-1', 'revision_number': 1, 'title': 'Port strike ends',
        'normalized_text': ARTICLE_TEXT, 'source_id': 'src-1', 'published_at': '2026-10-17T08:00:00+00:00', 'topic': 'labor'}
    with db.connect() as connection:
        connection.execute(
            'INSERT INTO controlplane.cp_articles (workspace_id, article_id, identity_key, exact_fingerprint, revision, payload) VALUES (%s, %s, %s, %s, 1, %s::jsonb)',
            (db.workspace_id, 'a-1', 'identity-a-1', 'f' * 64, json.dumps({'article_id': 'a-1'})))
        connection.execute(
            'INSERT INTO controlplane.cp_article_revisions (workspace_id, article_id, revision, payload) VALUES (%s, %s, 1, %s::jsonb)',
            (db.workspace_id, 'a-1', json.dumps(revision)))


def seed_job(db):
    with db.connect() as connection:
        connection.execute(
            'INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, 1)',
            ('batch-1', db.workspace_id, 'RUNNING'))
        connection.execute(
            'INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, %s, %s, %s, %s, 1)',
            ('job-1', 'batch-1', db.workspace_id, 'CREATED', 'snap-1'))


class Rig:
    def __init__(self, db, manager, script, profile):
        self.db = db
        self.ws = db.workspace_id
        self.route = FakeProviderRoute()
        self.ai = ScriptedAI(self.route, script)
        self.uow_factory = lambda: PostgresCreativeUnitOfWork(manager, workspace_id=self.ws)
        services = CreativeServices('production', self.uow_factory, self.route, self.ai, None, None)
        selections = SimpleNamespace()
        self.deps = creative_activity_deps(
            services, manager=manager, workspace_id=self.ws, profile=profile, runtime=SimpleNamespace(), grants=CurrentGrants(),
            sources=SourceSets(), selection_inputs=SimpleNamespace(), selections=selections, clock=lambda: NOW)
        handlers = creative_activity_handlers(self.deps, selections, workspace_id=self.ws)
        inner = ActivityDispatcher({name: handlers[name] for name in ACTIVITIES})
        self.dispatcher = ResultRecordingDispatcher(
            inner, db.connect, lambda: NOW, [JobLifecycleListener(db.connect, workspace_id=self.ws)], workspace_id=self.ws)
        self.refs = [{'ref_type': 'job_candidate', 'ref_id': 'cand-1'}, {'ref_type': 'source_set', 'ref_id': 'sourceset-1'}]

    def run(self, activity, stage, refs=None):
        sid = f'job-1:{stage}:r1'
        op = f'op:{stage}:{activity}'
        grant = {
            'grant_id': 'grant-' + op, 'stage_run_id': sid, 'execution_generation': 1, 'recovery_epoch': '1',
            'worker_lease_id': 'lease-1', 'issued_at': '2026-10-30T07:00:00Z', 'expires_at': '2026-10-30T09:00:00Z',
            'allowed_operation': activity, 'input_fingerprint': 'fp-1'}
        request = {
            'workflow_id': 'wf-1', 'workflow_run_id': 'wfr-1', 'stage_run_id': sid, 'activity_name': activity,
            'activity_version': '1', 'input_refs': [dict(ref) for ref in (self.refs if refs is None else refs)],
            'operation_key': op, 'capability_requirements': {'task_queue': 'desktop-cpu'}, 'retry_policy_ref': 'retry-r1',
            'video_job_id': 'job-1', 'execution_grant': grant}
        return self.dispatcher.dispatch(request)

    def ok(self, activity, stage):
        result = self.run(activity, stage)
        assert result['disposition'] == 'succeeded', result
        self.refs.extend(result['output_refs'])
        return result

    def op(self, activity, stage):
        return f'{self.ws}:op:{stage}:{activity}'

    def attempts(self, activity, stage):
        with self.uow_factory() as uow:
            return [(item.revision, item.record.attempt, item.record.validation_result) for item in uow.invocations.revisions(self.op(activity, stage))]

    def receipt(self, activity, stage):
        with self.uow_factory() as uow:
            return uow.receipts.get(self.ws, f'op:{stage}:{activity}')

    def count(self, kind):
        with self.uow_factory() as uow:
            if kind == 'analysis':
                return len(uow.analyses.revisions('analysis:job-1:r1'))
            return len(uow.angle_sets.revisions('angles:job-1:r1'))

    def events(self, name):
        with self.db.connect() as connection:
            return connection.execute(
                'SELECT count(*) FROM controlplane.cp_outbox_events WHERE workspace_id = %s AND event_name = %s', (self.ws, name)).fetchone()[0]

    def job_status(self):
        with self.db.connect() as connection:
            return connection.execute(
                'SELECT status FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s', (self.ws, 'job-1')).fetchone()[0]

    def stage_row(self, stage):
        with self.db.connect() as connection:
            return connection.execute(
                'SELECT status, wait_reason FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND stage_run_id = %s',
                (self.ws, f'job-1:{stage}:r1')).fetchone()


@pytest.fixture
def make_rig(pw_database, monkeypatch):
    monkeypatch.setattr(D14, 'WS', pw_database.workspace_id)
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        seed_article(pw_database)
        seed_job(pw_database)
        seed_default_prompts(compose_command_service(manager.unit_of_work), workspace_id=pw_database.workspace_id, actor_id=pw_database.actor_id)
        yield lambda script, attempts=None: Rig(pw_database, manager, script, with_attempts(load_production_profile(PROFILE_PATH), attempts))
    finally:
        manager.close()


def test_story_angles_retry_after_fenced_json_records_both_attempts(make_rig):
    rig = make_rig({'analysis': [ok(D14._analysis_json('v1'))], 'angle': [truncated(D14._angles_json('v1')), ok(D14._angles_json('v1'))]})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    rig.ok('AnalyzeContent', 'analyze')
    result = rig.run('GenerateStoryAngles', 'angles')
    assert result['disposition'] == 'succeeded', result
    assert rig.ai.calls.count('angle') == 2
    assert rig.attempts('GenerateStoryAngles', 'angles') == [(1, 1, 'failed'), (2, 2, 'passed')]
    assert rig.count('angles') == 1
    assert rig.receipt('GenerateStoryAngles', 'angles') is not None
    assert rig.events('StoryAnglesGenerated') == 1


def test_analyze_content_retries_a_missing_required_field(make_rig):
    bad = {key: value for key, value in D14._analysis_json('v1').items() if key != 'topic'}
    rig = make_rig({'analysis': [ok(bad), ok(D14._analysis_json('v1'))]})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    result = rig.run('AnalyzeContent', 'analyze')
    assert result['disposition'] == 'succeeded', result
    assert rig.ai.calls == ['analysis', 'analysis']
    assert rig.attempts('AnalyzeContent', 'analyze') == [(1, 1, 'failed'), (2, 2, 'passed')]
    assert rig.count('analysis') == 1


def test_generate_script_retries_a_missing_required_field(make_rig):
    bad = {key: value for key, value in D14._script_json('v1').items() if key != 'segments'}
    rig = make_rig({
        'analysis': [ok(D14._analysis_json('v1'))], 'angle': [ok(D14._angles_json('v1'))],
        'script': [ok(bad), ok(D14._script_json('v1'))]})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    rig.ok('AnalyzeContent', 'analyze')
    rig.ok('GenerateStoryAngles', 'angles')
    result = rig.run('GenerateScript', 'script')
    assert result['disposition'] == 'succeeded', result
    assert rig.ai.calls.count('script') == 2
    assert rig.attempts('GenerateScript', 'script') == [(1, 1, 'failed'), (2, 2, 'passed')]


def test_schema_violation_on_every_attempt_stops_at_max_attempts_with_a_structured_problem(make_rig):
    bad = truncated(D14._analysis_json('v1'))
    rig = make_rig({'analysis': [bad] * (PROFILE_ATTEMPTS + 2)})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    result = rig.run('AnalyzeContent', 'analyze')
    assert result['disposition'] == 'failed'
    problem = result['problem']
    assert (problem['code'], problem['retryable']) == ('ai_output_schema_violation', False)
    assert problem['field_errors'] == {'reason': 'not_json', 'field': 'root', 'attempts': str(PROFILE_ATTEMPTS)}
    assert rig.ai.calls.count('analysis') == PROFILE_ATTEMPTS
    assert rig.attempts('AnalyzeContent', 'analyze') == [(n, n, 'failed') for n in range(1, PROFILE_ATTEMPTS + 1)]
    assert rig.count('analysis') == 0
    assert rig.receipt('AnalyzeContent', 'analyze') is None
    assert rig.stage_row('analyze')[0] == 'FAILED_FINAL'
    assert rig.job_status() == 'FAILED_FINAL'
    assert 'harbor union' not in json.dumps(result)


def test_hallucinated_ref_on_the_first_attempt_then_valid_succeeds(make_rig):
    angles = copy.deepcopy(D14._angles_json('v1'))
    angles['angles'][0]['evidence_refs'] = [D14._ref('article_revision', 'a-404', 'v1')]
    rig = make_rig({'analysis': [ok(D14._analysis_json('v1'))], 'angle': [ok(angles), ok(D14._angles_json('v1'))]})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    rig.ok('AnalyzeContent', 'analyze')
    result = rig.run('GenerateStoryAngles', 'angles')
    assert result['disposition'] == 'succeeded', result
    assert rig.ai.calls.count('angle') == 2
    assert rig.attempts('GenerateStoryAngles', 'angles') == [(1, 1, 'failed'), (2, 2, 'passed')]


def test_uncommitted_snapshot_makes_zero_ai_calls(make_rig):
    rig = make_rig({'analysis': [ok(D14._analysis_json('v1'))]})
    refs = rig.refs + [{'ref_type': 'production_snapshot', 'ref_id': 'snapshot:job-1:r9', 'revision_id': '1'}]
    result = rig.run('AnalyzeContent', 'analyze', refs=refs)
    assert result['disposition'] == 'failed'
    assert result['problem']['code'] == 'INPUT_NOT_READY'
    assert 'field_errors' not in result['problem']
    assert rig.ai.calls == []
    assert rig.attempts('AnalyzeContent', 'analyze') == []


def test_repeating_a_succeeded_operation_key_returns_the_receipt_without_ai(make_rig):
    rig = make_rig({'analysis': [ok(D14._analysis_json('v1'))]})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    first = rig.ok('AnalyzeContent', 'analyze')
    again_rig = make_rig({})
    again_rig.refs = rig.refs
    again = again_rig.run('AnalyzeContent', 'analyze')
    assert again['disposition'] == 'succeeded', again
    assert again['metrics']['replayed'] is True
    assert again_rig.ai.calls == []
    assert rig.ai.calls.count('analysis') == 1
    assert again['output_refs'] == first['output_refs']
    assert rig.count('analysis') == 1


@pytest.mark.parametrize(('kind', 'text', 'expected'), [
    ('waiting', 'budget_blocked: BUDGET_BLOCKED', 'quota_wait'),
    ('waiting', 'waiting_provider: rate limit exceeded HTTP 429', 'quota_wait'),
    ('waiting', 'waiting_provider: timeout after 30s', 'provider_unavailable'),
    ('error', 'provider_failed: auth rejected HTTP 401', None),
])
def test_waiting_provider_results_wait_and_auth_failure_fails(make_rig, kind, text, expected):
    rig = make_rig({'analysis': [(kind, text)]})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    result = rig.run('AnalyzeContent', 'analyze')
    problem = result['problem']
    if kind == 'waiting':
        assert result['disposition'] == 'waiting', result
        assert problem['code'] == expected
        assert expected in {reason.value for reason in WaitReason}
        assert problem['retryable'] is True
        assert rig.job_status() == 'WAITING'
        assert rig.stage_row('analyze')[1] == expected
    else:
        assert result['disposition'] == 'failed', result
        assert problem['code'] == 'ai_invocation_failed'
        assert problem['retryable'] is False
    assert rig.ai.calls == ['analysis']
    assert rig.attempts('AnalyzeContent', 'analyze') == [(1, 1, 'not_run')]
    assert rig.count('analysis') == 0
    assert rig.receipt('AnalyzeContent', 'analyze') is None


@pytest.mark.parametrize('attempts', [2, 4])
def test_composition_passes_max_attempts_from_the_profile(make_rig, attempts):
    bad = truncated(D14._analysis_json('v1'))
    rig = make_rig({'analysis': [bad] * (attempts + 2)}, attempts=attempts)
    rig.ok('BuildProductionSnapshot', 'snapshot')
    result = rig.run('AnalyzeContent', 'analyze')
    assert rig.ai.calls.count('analysis') == attempts
    assert result['problem']['field_errors']['attempts'] == str(attempts)
    history = rig.attempts('AnalyzeContent', 'analyze')
    assert len(history) == attempts and {item[2] for item in history} == {'failed'}


def test_wiring_reads_max_attempts_only_from_the_profile():
    text = (ROOT / 'src' / 'controlplane' / 'api' / 'wiring' / 'creative.py').read_text(encoding='utf-8')
    assert 'ProviderFailurePolicy(max_attempts=profile.ai.retry.max_attempts)' in text


def test_pipeline_source_uses_the_failure_handler():
    text = (ROOT / 'src' / 'creative' / 'application' / 'pipeline.py').read_text(encoding='utf-8')
    assert 'ProviderFailureHandler' in text and 'self._ai.invoke' not in text and 'from src.' not in text


def test_analyze_content_accepts_a_fenced_json_object_on_the_first_attempt(make_rig):
    rig = make_rig({'analysis': [fenced(D14._analysis_json('v1'))]})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    result = rig.run('AnalyzeContent', 'analyze')
    assert result['disposition'] == 'succeeded', result
    assert rig.ai.calls.count('analysis') == 1
    assert rig.attempts('AnalyzeContent', 'analyze') == [(1, 1, 'passed')]
    assert rig.count('analysis') == 1


def test_story_angles_accepts_json_surrounded_by_sentences_on_the_first_attempt(make_rig):
    chatter = ('text', 'Here are the angles:' + chr(10) + json.dumps(D14._angles_json('v1')) + chr(10) + 'Let me know if you need more.')
    rig = make_rig({'analysis': [ok(D14._analysis_json('v1'))], 'angle': [chatter]})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    rig.ok('AnalyzeContent', 'analyze')
    result = rig.run('GenerateStoryAngles', 'angles')
    assert result['disposition'] == 'succeeded', result
    assert rig.ai.calls.count('angle') == 1
    assert rig.attempts('GenerateStoryAngles', 'angles') == [(1, 1, 'passed')]
    assert rig.count('angles') == 1


def test_empty_model_output_on_every_attempt_fails_with_reason_empty_output(make_rig):
    rig = make_rig({'analysis': [('text', '')] * (PROFILE_ATTEMPTS + 2)})
    rig.ok('BuildProductionSnapshot', 'snapshot')
    result = rig.run('AnalyzeContent', 'analyze')
    assert result['disposition'] == 'failed'
    assert result['problem']['code'] == 'ai_output_schema_violation'
    assert result['problem']['field_errors'] == {'reason': 'empty_output', 'field': 'root', 'attempts': str(PROFILE_ATTEMPTS)}
    assert rig.ai.calls.count('analysis') == PROFILE_ATTEMPTS
    assert rig.count('analysis') == 0
