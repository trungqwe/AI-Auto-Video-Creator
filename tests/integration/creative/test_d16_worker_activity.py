"""D-16: worker activity handler of D for workflow G (CT-WF-003, CT-WF-006).

coveredIds: CT-WF-003, CT-WF-006
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import json
import pathlib
import socket
import types

import pytest

from controlplane.domain.orchestration import ExecutionGrant
from creative.adapters.fake_ai import FakeAIAdapter, FakeProviderRoute
from creative.adapters.memory import InMemoryUnitOfWork
from creative.application.pipeline import AI_ROLES, CommandResult, CreativePipeline
from creative.domain.script import LanguageVoicePolicy, TargetRange
from creative.ports.repositories import CommandReceipt, EventContext
from creative.worker import activity_handler as ah
from creative.worker.activity_handler import (
    ActivityRequestError,
    CreativeActivityDeps,
    InMemoryActivityResultStore,
    handle_activity,
    validate_activity_request,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'creative' / 'worker' / 'activity_handler.py'
BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'g-activity-execution.json'
BINDING_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-activity-execution' / 'payloads.json'
WS = 'ws-1'
POLICY = LanguageVoicePolicy(language='en', speech_rate=2.0)
RANGE = TargetRange(min_seconds=5, max_seconds=20)
SCRIPT_ARGS = dict(
    snapshot_id='snap-1', analysis_id='an-1', analysis_revision=1, set_id='set-1', angle_id='angle-a',
    script_version_id='script-1', language_policy=POLICY, target_range=RANGE)
NOW = datetime.datetime(2026, 10, 19, 8, 0, 0, tzinfo=datetime.timezone.utc)
SECRET = 'hunter2-SECRET'
GRANT = ExecutionGrant(WS, 'op-1', 'job-1', 'stage-1', 3, 1)
OLD_GENERATION = dataclasses.replace(GRANT, execution_generation=2)
OLD_EPOCH = dataclasses.replace(GRANT, recovery_epoch=0)
NEW_GENERATION = dataclasses.replace(GRANT, execution_generation=4)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError('network is forbidden in D-16 tests')

    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)


def _ref(ref_type, ref_id, revision_id):
    return {'workspace_id': WS, 'ref_type': ref_type, 'ref_id': ref_id, 'revision_id': revision_id}


def _config_refs(revision):
    refs = [{'ref_type': 'prompt', 'ref_id': role, 'revision_id': f'{role}-{revision}'} for role in AI_ROLES]
    return refs + [{'ref_type': 'config_bundle', 'ref_id': 'bundle', 'revision_id': revision}]


def _snapshot_args(snapshot_id='snap-1', *, cfg='r1', source_rev='v1', mode='single_article', **overrides):
    args = dict(
        snapshot_id=snapshot_id, production_mode=mode,
        source_refs=[{'ref_type': 'article_revision', 'ref_id': 'a-1', 'revision_id': source_rev}],
        index_revision_refs=[], configuration_revision_refs=_config_refs(cfg), content_ref_types=['article_revision'],
        eligibility_reason='eligible', snapshot_timestamp='2026-10-19T08:00:00+00:00', video_job_ref='job-1')
    args.update(overrides)
    return args


def _analysis_json(rev):
    return {
        'topic': 'Port strike ends', 'entities': [{'name': 'Harbor Union', 'entity_type': 'organization'}],
        'timeline': [{'time_label': '2026-10-17', 'description': 'Strike begins'}], 'locations': ['Rotterdam'],
        'facts': [{'id': 'f-1', 'text': 'The union ended the strike.', 'evidence_refs': [_ref('article_revision', 'a-1', rev)]}],
        'uncertainties': [], 'contradictions': [], 'event_relation': 'standalone', 'update_context': '',
        'risk_flags': [], 'narrative_opportunities': ['Shipping impact'], 'media_needs': ['port footage'],
    }


def _angles_json(rev):
    base = {
        'summary': 'Short summary', 'evidence_refs': [_ref('article_revision', 'a-1', rev)],
        'planned_inference_elements': ['cause'], 'planned_creative_elements': ['map'], 'suitability': 'high', 'risk_flags': [],
    }
    return {'angles': [
        {**base, 'angle_id': 'angle-a', 'title': 'Why', 'narrative_question': 'Why did the strike end?',
         'focus_entities': ['Harbor Union'], 'timeframe': '2026-10'},
        {**base, 'angle_id': 'angle-b', 'title': 'Who pays', 'narrative_question': 'Who pays for the deal?',
         'focus_entities': ['Port Authority'], 'timeframe': '2026-11'},
    ]}


def _script_json(rev):
    return {
        'language': 'en', 'hook_intent': 'strike ends', 'thumbnail_transition': 'fade',
        'pronunciation_hints': [{'term': 'Rotterdam', 'pronunciation': 'ROT-er-dam'}],
        'segments': [
            {'segment_id': 's1', 'text': 'The harbor union ended its three day strike this week', 'claim_mode': 'source_backed',
             'scene_intent': 'scene one', 'source_refs': [_ref('article_revision', 'a-1', rev)]},
            {'segment_id': 's2', 'text': 'Ships should start moving again by tomorrow morning', 'claim_mode': 'inference',
             'scene_intent': 'scene two', 'source_refs': [], 'disclosure': 'This is an inference from the sources.'},
        ],
    }


def _metadata_json():
    return {
        'title': 'Port Strike Ends After Three Days', 'caption': 'Ships are set to move again this week.',
        'hashtags': ['#Port', '#Strike', '#Shipping']}


ARGS = {
    'BuildProductionSnapshot': lambda: _snapshot_args(),
    'AnalyzeContent': lambda: dict(snapshot_id='snap-1', analysis_id='an-1', revision=1),
    'GenerateStoryAngles': lambda: dict(
        snapshot_id='snap-1', analysis_id='an-1', analysis_revision=1, set_id='set-1', requested_count=2,
        variation_policy_revision='var-v1'),
    'GenerateScript': lambda: dict(SCRIPT_ARGS),
    'GenerateOutputMetadata': lambda: dict(
        snapshot_id='snap-1', source_job_ref='job-1', source_output_refs=('variant-1',), metadata_revision=1),
}
RESPONSES = {
    role: {'text': json.dumps(payload), 'refs': []}
    for role, payload in {
        'analysis': _analysis_json('v1'),
        'angle': _angles_json('v1'),
        'script': _script_json('v1'),
        'metadata': _metadata_json(),
    }.items()
}


def context_of(name, grant, *, workspace=None, epoch=None):
    return EventContext(
        workspace_id=workspace or grant.workspace_id,
        correlation_id='corr-1',
        actor='worker-d',
        occurred_at='2026-10-19T08:00:00+00:00',
        recovery_epoch=epoch or str(grant.recovery_epoch),
        event_id=f'evt-{name}',
        message_id=f'msg-{name}',
    )


class FakeGrants:
    """Test-only GrantCurrencyPort: a grant is current only when it equals one of the given grants."""

    def __init__(self, *current: ExecutionGrant) -> None:
        self.current = set(current)
        self.calls = 0

    def is_grant_current(self, grant: ExecutionGrant) -> bool:
        self.calls += 1
        return grant in self.current


class FakeInputs:
    """Test-only ActivityInputPort: builds the keyword arguments of the one D-14 command from fixed fixtures."""

    def __init__(self) -> None:
        self.overrides: dict = {}
        self.workspace: str | None = None
        self.epoch: str | None = None
        self.raises: Exception | None = None
        self.calls: list[str] = []

    def resolve(self, activity_name, request, grant):
        self.calls.append(activity_name)
        if self.raises is not None:
            raise self.raises
        context = context_of(request['operation_key'], grant, workspace=self.workspace, epoch=self.epoch)
        return {'context': context, **ARGS[activity_name](), **self.overrides}


class StubInputs:
    """Test-only ActivityInputPort for the routing test: a context and a marker, whatever the activity."""

    def resolve(self, activity_name, request, grant):
        return {'context': context_of(request['operation_key'], grant), 'marker': activity_name}


class Rig:
    def __init__(self, *, grants=(GRANT,), errors=None, known_secrets=()) -> None:
        self.uow = InMemoryUnitOfWork()
        self.route = FakeProviderRoute()
        self.ai = FakeAIAdapter(
            self.route, responses=RESPONSES, config_revision='cfg-fake', errors=errors, known_secrets=known_secrets)
        pipeline = CreativePipeline(
            uow_factory=lambda: self.uow,
            route=self.route,
            ai=self.ai,
            instructions={role: f'Return JSON for {role}' for role in AI_ROLES},
        )
        self.grants = FakeGrants(*grants)
        self.inputs = FakeInputs()
        self.deps = CreativeActivityDeps(pipeline=pipeline, grants=self.grants, inputs=self.inputs, clock=lambda: NOW)

    def events(self) -> list[str]:
        return [record.event_type for record in self.uow.outbox.records()]

    def untouched(self) -> bool:
        counters = (self.ai.invoke_calls, self.route.resolve_calls, len(self.uow.snapshots.list_snapshots()))
        return counters == (0, 0, 0) and self.events() == []


def request_of(activity='BuildProductionSnapshot', operation_key='op-snap', **extra) -> dict:
    request = {
        'workflow_id': 'wf-1',
        'workflow_run_id': 'wfr-1',
        'stage_run_id': 'stage-1',
        'activity_name': activity,
        'activity_version': '1',
        'input_refs': [{'ref_type': 'production_snapshot', 'ref_id': 'snap-1'}],
        'operation_key': operation_key,
        'capability_requirements': {'provider': 'ai'},
        'retry_policy_ref': 'retry-r1',
    }
    return {**request, **extra}


CHAIN = (
    ('BuildProductionSnapshot', 'op-snap'),
    ('AnalyzeContent', 'op-analysis'),
    ('GenerateStoryAngles', 'op-angles'),
    ('GenerateScript', 'op-script'),
)
ROUTING = {  # activity_name -> (CreativePipeline method, ref_type of the output ref)
    'BuildProductionSnapshot': ('build_production_snapshot', 'production_snapshot'),
    'AnalyzeContent': ('analyze_content', 'content_analysis'),
    'GenerateStoryAngles': ('generate_story_angles', 'story_angle_set'),
    'GenerateScript': ('generate_script', 'script_version'),
    'SelectCreativeAssets': ('select_creative_assets', 'creative_asset_selection'),
    'BuildProductionPlan': ('build_production_plan', 'production_plan'),
    'ValidateVariant': ('validate_variant', 'variant_validation'),
    'GenerateOutputMetadata': ('generate_output_metadata', 'output_metadata'),
}


def handle(rig: Rig, request: dict | None = None, grant: ExecutionGrant = GRANT):
    return handle_activity(request if request is not None else request_of(), grant, rig.deps)


def run_chain(rig: Rig) -> list[dict]:
    return [handle(rig, request_of(name, key)) for name, key in CHAIN]


def _spy_method(command):
    def method(self, **kwargs):
        self.calls.append((command, kwargs))
        receipt = CommandReceipt(WS, kwargs['idempotency_key'], 'f' * 64, f'{command}-1', 1)
        return CommandResult(
            command=command, receipt=receipt, replayed=False, output=self.output, event_id=None, trace=None)

    return method


class SpyPipeline:
    """Test-only pipeline: records each command call and returns a canned CommandResult."""

    def __init__(self) -> None:
        self.calls: list = []
        self.output = None


for _command, (_method, _) in ROUTING.items():
    setattr(SpyPipeline, _method, _spy_method(_command))


def test_module_docstring_lists_the_covered_ids():
    docstring = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-WF-003, CT-WF-006' in docstring.splitlines()


def test_snapshot_activity_returns_a_succeeded_activity_result():
    rig = Rig()
    result = handle(rig)
    assert result['disposition'] == 'succeeded'
    assert (result['stage_run_id'], result['grant_id']) == ('stage-1', 'op-1')
    assert (result['execution_generation'], result['recovery_epoch']) == (3, '1')
    assert result['completed_at'] == '2026-10-19T08:00:00Z'
    assert result['output_refs'] == [{'ref_type': 'production_snapshot', 'ref_id': 'snap-1', 'revision_id': '1'}]
    assert result['metrics'] == {'replayed': False, 'aggregate_revision': 1, 'ai_invoked': False}
    assert result['warnings'] == []
    assert result['operation_receipt_ref'] == 'receipt:op-snap'
    assert 'problem' not in result
    assert rig.events() == ['ProductionSnapshotCommitted'] and rig.ai.invoke_calls == 0
    assert rig.inputs.calls == ['BuildProductionSnapshot']


def test_ai_activities_run_one_command_each_and_a_finished_stage_never_starts_the_next():
    rig = Rig()
    first = handle(rig)
    assert rig.inputs.calls == ['BuildProductionSnapshot'] and rig.ai.invoke_calls == 0
    assert rig.uow.analyses.latest('an-1') is None
    rest = [handle(rig, request_of(name, key)) for name, key in CHAIN[1:]]
    assert [item['disposition'] for item in [first, *rest]] == ['succeeded'] * 4
    assert [item['output_refs'][0]['ref_type'] for item in rest] == ['content_analysis', 'story_angle_set', 'script_version']
    assert [item['output_refs'][0]['ref_id'] for item in rest] == ['an-1', 'set-1', 'script-1']
    assert [item['metrics']['ai_invoked'] for item in rest] == [True, True, True]
    assert rig.ai.calls_by_role == {'analysis': 1, 'angle': 1, 'script': 1}
    assert rig.events() == ['ProductionSnapshotCommitted', 'StoryAnglesGenerated', 'ScriptVersionCreated']
    assert rig.uow.scripts.latest('script-1') is not None


def test_generate_output_metadata_activity_returns_its_metadata_ref():
    rig = Rig()
    handle(rig)
    result = handle(rig, request_of('GenerateOutputMetadata', 'op-meta'))
    assert result['disposition'] == 'succeeded'
    assert result['output_refs'] == [{'ref_type': 'output_metadata', 'ref_id': 'job-1', 'revision_id': '1'}]
    assert rig.events() == ['ProductionSnapshotCommitted', 'OutputMetadataCreated']


def test_desktop_capability_is_never_waited_for_by_d():
    rig = Rig()
    result = handle(rig, request_of(capability_requirements={'desktop': 'required'}))
    assert result['disposition'] == 'succeeded' and 'problem' not in result


def test_unknown_activity_name_returns_a_structured_problem_without_running_anything():
    rig = Rig()
    result = handle(rig, request_of('RenderVideo'))
    assert result['disposition'] == 'failed' and result['output_refs'] == []
    problem = result['problem']
    assert (problem['code'], problem['retryable'], problem['category']) == ('UNKNOWN_ACTIVITY', False, 'validation')
    assert problem['correlation_id'] == 'wfr-1' and problem['instance'] == 'urn:stage-run:stage-1'
    assert rig.inputs.calls == [] and rig.untouched()
    assert rig.deps.results.get(WS, 'op-snap') is None


@pytest.mark.parametrize('activity', list(ROUTING))
def test_each_activity_name_runs_exactly_its_own_pipeline_method(activity):
    spy = SpyPipeline()
    deps = CreativeActivityDeps(pipeline=spy, grants=FakeGrants(GRANT), inputs=StubInputs(), clock=lambda: NOW)
    result = handle_activity(request_of(activity, 'op-x'), GRANT, deps)
    assert [call[0] for call in spy.calls] == [activity]
    kwargs = spy.calls[0][1]
    assert kwargs['idempotency_key'] == 'op-x' and kwargs['marker'] == activity
    assert isinstance(kwargs['context'], EventContext)
    assert result['disposition'] == 'succeeded' and result['warnings'] == []
    assert result['output_refs'] == [{'ref_type': ROUTING[activity][1], 'ref_id': f'{activity}-1', 'revision_id': '1'}]
    assert result['operation_receipt_ref'] == 'receipt:op-x'


def test_invalid_variant_result_carries_reason_code_warnings():
    spy = SpyPipeline()
    spy.output = types.SimpleNamespace(valid=False, reason_codes=('same_run_angle_duplicate', 'exact_duplicate'))
    deps = CreativeActivityDeps(pipeline=spy, grants=FakeGrants(GRANT), inputs=StubInputs(), clock=lambda: NOW)
    result = handle_activity(request_of('ValidateVariant', 'op-var'), GRANT, deps)
    assert result['disposition'] == 'succeeded'
    assert result['warnings'] == ['variant_invalid:same_run_angle_duplicate', 'variant_invalid:exact_duplicate']


STALE_GRANTS = [OLD_GENERATION, OLD_EPOCH]
STALE_IDS = ['old_generation', 'old_recovery_epoch']


@pytest.mark.parametrize('stale', STALE_GRANTS, ids=STALE_IDS)
def test_stale_grant_is_rejected_before_any_input_lookup_or_commit(stale):
    rig = Rig()
    result = handle(rig, grant=stale)
    assert result['disposition'] == 'stale'
    assert (result['problem']['code'], result['problem']['retryable']) == ('STALE_GRANT', False)
    assert result['output_refs'] == []
    assert (result['execution_generation'], result['recovery_epoch']) == (
        stale.execution_generation,
        str(stale.recovery_epoch),
    )
    assert rig.inputs.calls == [] and rig.untouched()
    assert rig.deps.results.get(WS, 'op-snap') is None


@pytest.mark.parametrize('stale', STALE_GRANTS, ids=STALE_IDS)
def test_stale_grant_cannot_write_a_new_script_after_a_current_one_committed(stale):
    rig = Rig()
    run_chain(rig)
    rig.inputs.overrides = {'script_version_id': 'script-2'}
    before = (rig.ai.invoke_calls, rig.events(), len(rig.uow.scripts.revisions('script-1')))
    result = handle(rig, request_of('GenerateScript', 'op-script-2'), stale)
    assert result['disposition'] == 'stale' and result['output_refs'] == []
    assert (rig.ai.invoke_calls, rig.events(), len(rig.uow.scripts.revisions('script-1'))) == before
    assert rig.uow.scripts.latest('script-2') is None
    assert rig.uow.receipts.get(WS, 'op-script-2') is None
    assert rig.inputs.calls.count('GenerateScript') == 1


def test_stale_grant_does_not_receive_the_stored_result_of_a_newer_generation():
    rig = Rig()
    handle(rig)
    result = handle(rig, grant=OLD_GENERATION)
    assert result['disposition'] == 'stale' and result['output_refs'] == []


def test_same_operation_key_returns_the_stored_result_without_running_again():
    rig = Rig()
    first = run_chain(rig)[-1]
    calls = (rig.ai.invoke_calls, list(rig.inputs.calls), rig.events())
    second = handle(rig, request_of('GenerateScript', 'op-script'))
    assert second == first
    assert (rig.ai.invoke_calls, rig.inputs.calls, rig.events()) == calls
    second['metrics']['replayed'] = True
    assert handle(rig, request_of('GenerateScript', 'op-script')) == first


def test_same_operation_key_under_a_newer_current_generation_keeps_outputs_and_takes_the_new_identity():
    rig = Rig(grants=(GRANT, NEW_GENERATION))
    first = handle(rig)
    second = handle(rig, grant=NEW_GENERATION)
    assert (first['execution_generation'], second['execution_generation']) == (3, 4)
    assert second['disposition'] == 'succeeded' and second['output_refs'] == first['output_refs']
    assert rig.events() == ['ProductionSnapshotCommitted'] and rig.inputs.calls == ['BuildProductionSnapshot']


def test_same_operation_key_for_a_different_activity_is_a_conflict():
    rig = Rig()
    first = handle(rig)
    conflict = handle(rig, request_of('AnalyzeContent', 'op-snap'))
    assert conflict['disposition'] == 'failed' and conflict['output_refs'] == []
    assert conflict['problem']['code'] == 'OPERATION_KEY_CONFLICT'
    assert rig.ai.invoke_calls == 0 and rig.uow.analyses.latest('an-1') is None
    assert handle(rig) == first


def test_a_lost_result_store_replays_from_the_d14_receipt_without_a_second_write():
    rig = Rig()
    first = run_chain(rig)[-1]
    calls, events = rig.ai.invoke_calls, rig.events()
    fresh = dataclasses.replace(rig.deps, results=InMemoryActivityResultStore())
    again = handle_activity(request_of('GenerateScript', 'op-script'), GRANT, fresh)
    assert again['disposition'] == 'succeeded' and again['output_refs'] == first['output_refs']
    assert again['metrics'] == {**first['metrics'], 'replayed': True, 'ai_invoked': False}
    assert again['operation_receipt_ref'] == first['operation_receipt_ref']
    assert (rig.ai.invoke_calls, rig.events()) == (calls, events)
    assert len(rig.uow.scripts.revisions('script-1')) == 1


def test_same_key_with_other_command_arguments_is_an_idempotency_conflict():
    rig = Rig()
    run_chain(rig)
    calls = rig.ai.invoke_calls
    rig.inputs.overrides = {'script_version_id': 'script-9'}
    fresh = dataclasses.replace(rig.deps, results=InMemoryActivityResultStore())
    result = handle_activity(request_of('GenerateScript', 'op-script'), GRANT, fresh)
    problem = result['problem']
    assert result['disposition'] == 'failed'
    assert (problem['code'], problem['category'], problem['retryable']) == (
        'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD',
        'conflict',
        False,
    )
    assert rig.uow.scripts.latest('script-9') is None and rig.ai.invoke_calls == calls


def test_a_command_rejection_is_a_failed_result_with_its_code_and_nothing_committed():
    rig = Rig()
    result = handle(rig, request_of('GenerateScript', 'op-script'))
    problem = result['problem']
    assert result['disposition'] == 'failed' and result['output_refs'] == []
    assert (problem['code'], problem['category'], problem['retryable']) == ('INPUT_NOT_READY', 'validation', False)
    assert rig.untouched() and rig.uow.receipts.get(WS, 'op-script') is None
    assert rig.deps.results.get(WS, 'op-script') is None


def test_provider_failure_is_a_failed_result_with_a_code_only_problem():
    rig = Rig(errors={'analysis': f'upstream timeout token={SECRET}'}, known_secrets=(SECRET,))
    handle(rig)
    result = handle(rig, request_of('AnalyzeContent', 'op-analysis'))
    problem = result['problem']
    assert result['disposition'] == 'failed' and result['output_refs'] == []
    assert (problem['code'], problem['category'], problem['retryable']) == ('ai_invocation_failed', 'dependency', False)
    assert SECRET not in repr(result) and 'upstream' not in repr(result)
    assert rig.uow.analyses.latest('an-1') is None and rig.uow.invocations.latest('ws-1:op-analysis') is None
    assert rig.deps.results.get(WS, 'op-analysis') is None


class LeakyCode(Exception):
    code = f'token={SECRET}'


UNEXPECTED = (
    ('runtime_error', RuntimeError(f'db password={SECRET} lost'), 'ACTIVITY_ABORTED', True),
    ('leaky_code', LeakyCode(f'Bearer {SECRET}'), 'ACTIVITY_ABORTED', True),
    ('value_error', ValueError(f'bad Bearer {SECRET}'), 'INVALID_COMMAND_INPUT', False),
)


@pytest.mark.parametrize(
    ('error', 'code', 'retryable'), [case[1:] for case in UNEXPECTED], ids=[case[0] for case in UNEXPECTED]
)
def test_unexpected_exceptions_become_redacted_failed_results(error, code, retryable):
    rig = Rig()
    rig.inputs.raises = error
    result = handle(rig)
    assert result['disposition'] == 'failed'
    assert (result['problem']['code'], result['problem']['retryable']) == (code, retryable)
    assert SECRET not in repr(result)
    assert rig.deps.results.get(WS, 'op-snap') is None and rig.untouched()


def test_a_new_key_for_an_existing_script_id_is_a_non_retryable_conflict_and_commits_nothing():
    rig = Rig()
    run_chain(rig)
    events = rig.events()
    result = handle(rig, request_of('GenerateScript', 'op-script-2'))
    problem = result['problem']
    assert result['disposition'] == 'failed'
    assert (problem['code'], problem['category'], problem['retryable']) == ('REVISION_CONFLICT', 'conflict', False)
    assert len(rig.uow.scripts.revisions('script-1')) == 1 and rig.events() == events
    assert rig.uow.receipts.get(WS, 'op-script-2') is None
    assert rig.uow.invocations.latest('ws-1:op-script-2') is None


@pytest.mark.parametrize(
    ('workspace', 'epoch'), [('ws-2', None), (None, '0')], ids=['other_workspace', 'other_recovery_epoch']
)
def test_command_context_of_another_workspace_or_epoch_is_refused_before_the_command(workspace, epoch):
    rig = Rig()
    rig.inputs.workspace, rig.inputs.epoch = workspace, epoch
    result = handle(rig)
    assert result['disposition'] == 'failed'
    assert (result['problem']['code'], result['problem']['category']) == ('GRANT_CONTEXT_MISMATCH', 'validation')
    assert rig.untouched() and rig.deps.results.get(WS, 'op-snap') is None


INVALID_REQUESTS = (
    ('missing_operation_key', lambda r: r.pop('operation_key'), ('missing_required', 'operation_key')),
    ('secret_in_payload', lambda r: r.update(secret_value=SECRET), ('forbidden_field', 'secret_value')),
    ('raw_blob_in_payload', lambda r: r.update(raw_blob='x'), ('forbidden_field', 'raw_blob')),
    ('blank_activity_name', lambda r: r.update(activity_name=' '), ('invalid_value', 'activity_name')),
    ('empty_input_refs', lambda r: r.update(input_refs=[]), ('invalid_value', 'input_refs')),
    ('input_ref_without_id', lambda r: r.update(input_refs=[{'ref_type': 'script_version'}]), ('invalid_value', 'input_refs')),
    ('input_refs_as_string', lambda r: r.update(input_refs='ref-1'), ('wrong_type', 'input_refs')),
    ('other_stage_run', lambda r: r.update(stage_run_id='stage-2'), ('invalid_value', 'execution_grant.stage_run_id')),
)
INVALID_GRANTS = (
    ('not_an_execution_grant', {'workspace_id': WS}, ('wrong_type', 'execution_grant')),
    (
        'negative_generation',
        dataclasses.replace(GRANT, execution_generation=-1),
        ('invalid_value', 'execution_grant.execution_generation'),
    ),
    ('blank_workspace', dataclasses.replace(GRANT, workspace_id=' '), ('invalid_value', 'execution_grant.workspace_id')),
)


@pytest.mark.parametrize(
    ('mutate', 'issue'), [case[1:] for case in INVALID_REQUESTS], ids=[case[0] for case in INVALID_REQUESTS]
)
def test_invalid_request_raises_before_any_grant_check_lookup_or_write(mutate, issue):
    rig = Rig()
    request = request_of()
    mutate(request)
    with pytest.raises(ActivityRequestError) as raised:
        handle(rig, request)
    assert raised.value.code == 'VALIDATION_ERROR' and issue in raised.value.issues
    assert SECRET not in repr(raised.value)
    assert (rig.grants.calls, rig.inputs.calls) == (0, []) and rig.untouched()


@pytest.mark.parametrize(
    ('grant', 'issue'), [case[1:] for case in INVALID_GRANTS], ids=[case[0] for case in INVALID_GRANTS]
)
def test_invalid_grant_raises_validation_error_before_any_grant_check(grant, issue):
    rig = Rig()
    with pytest.raises(ActivityRequestError) as raised:
        handle(rig, grant=grant)
    assert raised.value.code == 'VALIDATION_ERROR' and issue in raised.value.issues
    assert (rig.grants.calls, rig.inputs.calls) == (0, []) and rig.untouched()


def imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_handler_registers_no_workflow_or_activity_through_decorators():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    assert [node.name for node in ast.walk(tree) if isinstance(node, functions) and node.decorator_list] == []


def test_handler_uses_the_controlplane_execution_grant_and_defines_no_grant_class():
    assert ah.ExecutionGrant is ExecutionGrant
    defined = [name for name, value in vars(ah).items() if isinstance(value, type) and value.__module__ == ah.__name__]
    assert [name for name in defined if name.endswith('Grant')] == []


def test_results_carry_every_required_binding_field_and_a_contract_disposition():
    binding = json.loads(BINDING.read_text(encoding='utf-8'))
    entity = next(item for item in binding['entities'] if item['name'] == 'ActivityResult')
    required = {item['name'] for item in entity['fields'] if item['required']}
    dispositions = next(item for item in entity['fields'] if item['name'] == 'disposition')['enum']
    results = [handle(Rig()), handle(Rig(), grant=OLD_EPOCH), handle(Rig(), request_of('RenderVideo'))]
    for result in results:
        assert required <= set(result)
        assert result['disposition'] in dispositions
        assert type(result['execution_generation']) is int and isinstance(result['recovery_epoch'], str)
        assert isinstance(result['output_refs'], list)


def test_binding_fixture_requests_are_valid_and_invalid_cases_report_their_expected_error():
    entity = json.loads(BINDING_FIXTURE.read_text(encoding='utf-8'))['entities']['ActivityRequest']
    valid = entity['valid'][0]
    grant = dataclasses.replace(GRANT, stage_run_id=valid['stage_run_id'])
    assert validate_activity_request(valid, grant) == []
    for case in entity['invalid']:
        expected = (case['expected_error']['code'], case['expected_error']['field'])
        assert expected in validate_activity_request(case['payload'], grant), case['case']


def test_supported_activity_names_are_the_eight_d14_commands():
    assert ah.ACTIVITY_NAMES == (
        'BuildProductionSnapshot', 'AnalyzeContent', 'GenerateStoryAngles', 'GenerateScript',
        'SelectCreativeAssets', 'BuildProductionPlan', 'ValidateVariant', 'GenerateOutputMetadata')
    assert ah.ACTIVITY_NAMES == tuple(ROUTING)


def test_handler_imports_no_temporalio_ui_api_voice_or_render_code():
    banned_parts = {'temporalio', 'voice', 'render'}
    banned = sorted(
        name for name in imported_modules(MODULE_PATH)
        if banned_parts & set(name.split('.')) or name.startswith(('controlplane.ui', 'controlplane.api')))
    assert banned == []


def test_handler_imports_only_stdlib_controlplane_domain_and_creative_layers():
    stdlib = {'__future__', 'copy', 'datetime', 're', 'collections.abc', 'dataclasses', 'types', 'typing'}
    allowed = ('controlplane.domain', 'creative.application', 'creative.domain', 'creative.ports')
    unexpected = sorted(name for name in imported_modules(MODULE_PATH) if name not in stdlib and not name.startswith(allowed))
    assert unexpected == []


def test_handler_never_waits_sleeps_or_opens_io():
    waiting = {'time', 'asyncio', 'threading', 'sched', 'subprocess', 'socket', 'os'}
    assert sorted(name for name in imported_modules(MODULE_PATH) if name.split('.')[0] in waiting) == []
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    sleeps = [
        node for node in ast.walk(tree)
        if (isinstance(node, ast.Attribute) and node.attr == 'sleep') or (isinstance(node, ast.Name) and node.id == 'sleep')]
    assert sleeps == []
