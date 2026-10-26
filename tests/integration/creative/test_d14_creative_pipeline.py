"""D-14: chuỗi command sáng tạo, mỗi command một UoW (output mới, AIInvocationRecord, receipt, outbox event).

coveredIds: TST-INT-INV-004, TST-INT-INV-005
"""
from __future__ import annotations

import ast
import copy
import json
import pathlib
import re
import socket

import pytest

import creative.application.pipeline as pipeline_module
from controlplane.domain.concurrency import RevisionConflictError
from creative.adapters.fake_ai import FakeAIAdapter, FakeProviderRoute
from creative.adapters.memory import InMemoryUnitOfWork
from creative.application.pipeline import AI_ROLES, CreativePipeline, IdempotencyConflict, PipelineRejected
from creative.domain.asset_selection import HookCandidate, MediaCandidate, SafetyRightsPolicy, ScoringWeights, ThumbnailCandidate
from creative.domain.script import LanguageVoicePolicy, TargetRange
from creative.domain.timeline_mode import TimelinePolicy, TimelinePolicyViolation, authorize_timeline_narrative
from creative.domain.variant import SameRunVariant, build_variant_fingerprint
from creative.ports.repositories import EventContext

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'creative' / 'application' / 'pipeline.py'
WS = 'ws-1'
POLICY = LanguageVoicePolicy(language='en', speech_rate=2.0)
RANGE = TargetRange(min_seconds=5, max_seconds=20)
TIMELINE_POLICY = TimelinePolicy(frozenset({'event_update_accepted'}))
SCRIPT_ARGS = dict(
    snapshot_id='snap-1', analysis_id='an-1', analysis_revision=1, set_id='set-1', angle_id='angle-a',
    script_version_id='script-1', language_policy=POLICY, target_range=RANGE)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError('network is forbidden in D-14 tests')

    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)


def _ctx(number, workspace_id=WS):
    return EventContext(
        workspace_id=workspace_id, correlation_id='corr-1', actor='tester', occurred_at='2026-10-19T08:00:00+00:00',
        recovery_epoch='epoch-1', event_id=f'evt-{number}', message_id=f'msg-{number}')


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



def _selection_json():
    return {
        'visual_hook': _ref('visual_hook', 'vh-1', 'vh-1-r1'), 'audio_hook': _ref('audio_hook', 'ah-1', 'ah-1-r1'),
        'thumbnail': _ref('thumbnail', 'th-1', 'th-1-r1'),
        'scenes': [
            {'scene_id': 'sc-1', 'ref': _ref('media_asset', 'm-1', 'm-1-av'), 'rationale': 'opens on the union'},
            {'scene_id': 'sc-2', 'ref': _ref('media_asset', 'm-2', 'm-2-av'), 'rationale': 'context shot'},
        ],
        'music_intents': [{'cue': 'intro_pad', 'description': 'soft pad'}],
        'sfx_intents': [{'cue': 'whoosh', 'description': 'short whoosh'}],
        'rationale': 'angle focused selection',
    }


def _visual(asset, start, end):
    return {
        'media_asset_id': asset, 'start_ms': start, 'end_ms': end, 'crop_intent': 'center on subject',
        'overlay_intent': 'lower third', 'effect_intent': 'slow push-in'}


def _plan_json():
    return {
        'timeline': {'segments': [
            {'scene_id': 'sc-1', 'start_ms': 0, 'end_ms': 8000, 'transition_intent': 'hard cut', 'visuals': [_visual('m-1', 0, 8000)]},
            {'scene_id': 'sc-2', 'start_ms': 8000, 'end_ms': 20000, 'transition_intent': 'cross dissolve', 'visuals': [_visual('m-2', 8000, 20000)]},
        ]},
        'hook_placement': {'hook_time_range': {'start_ms': 0, 'end_ms': 5000}, 'thumbnail_time_range': {'start_ms': 1200, 'end_ms': 2400}},
        'voice_profile_intent': {'direction': 'warm and confident', 'pace': 'steady', 'emotion': 'curious'},
        'music_cues': [{'cue': 'intro_pad', 'start_ms': 0, 'end_ms': 20000}],
        'sfx_cues': [{'cue': 'whoosh', 'start_ms': 7800, 'end_ms': 8200}],
        'subtitle_style_intent': {'style': 'bold white captions', 'karaoke': True, 'highlight_intent': 'active word turns yellow'},
        'allowed_fallbacks': [
            {'rule_id': 'fb-1', 'kind': 'replace_asset', 'scene_id': 'sc-2', 'replacement_media_asset_id': 'm-3'},
            {'rule_id': 'fb-2', 'kind': 'simplify_transition', 'scene_id': 'sc-1'},
        ],
        'output_metadata_requirement': 'english title, caption and 3-4 hashtags',
    }


def _metadata_json():
    return {
        'title': 'Port Strike Ends After Three Days', 'caption': 'Ships are set to move again this week.',
        'hashtags': ['#Port', '#Strike', '#Shipping']}



def _media(asset_id, score):
    return MediaCandidate(
        media_asset_id=asset_id, rendition_ref=f'{asset_id}-rend', artifact_version_ref=f'{asset_id}-av',
        provenance={'source': 'catalog'}, semantic_match_components={'entity': score}, technical_fitness={'score': score},
        availability='AVAILABLE', safety_rights_status={'rights_cleared': True}, recent_usage_summary={'times_used': 0},
        reason_codes=('ENTITY_MATCH',))


def _hook(kind, hook_id):
    return HookCandidate(
        hook_kind=kind, hook_id=hook_id, revision_id=f'{hook_id}-r1', availability='AVAILABLE',
        safety_rights_status={'rights_cleared': True}, semantic_match_components={'topic': 0.7},
        provenance={'source': 'user_imported'})


def _asset_inputs():
    thumbnail = ThumbnailCandidate(
        thumbnail_id='th-1', revision_id='th-1-r1', subject_refs=('entity-1',), crop_focus={'x': 0.5},
        overlay_intent='question_mark', availability='AVAILABLE', safety_rights_status={'rights_cleared': True},
        semantic_match_components={'entity': 0.8}, provenance={'source': 'catalog'})
    return dict(
        media_candidates=[_media('m-1', 0.9), _media('m-2', 0.8), _media('m-3', 0.7)],
        visual_hook_candidates=[_hook('visual_hook', 'vh-1')], audio_hook_candidates=[_hook('audio_hook', 'ah-1')],
        thumbnail_candidates=[thumbnail],
        safety_policy=SafetyRightsPolicy(
            revision='safe-v1', allowed_availability=('AVAILABLE',), required_flags=('rights_cleared',), blocked_flags=('unsafe',)),
        music_sfx_policy_revision='music-v1', preset_registry_revision='preset-v1',
        weights=ScoringWeights(semantic=0.6, technical=0.4, recent_usage_penalty=0.1))


ROUTE_KEY_OF = {
    'content_analysis': 'analysis', 'story_angles': 'angle', 'script_generation': 'script',
    'asset_selection': 'selection', 'production_plan': 'selection', 'output_metadata': 'metadata'}


def _responses(rev):
    payloads = {
        'analysis': _analysis_json(rev), 'angle': _angles_json(rev), 'script': _script_json(rev),
        'selection': _selection_json(), 'metadata': _metadata_json()}
    return {role: {'text': json.dumps(payload), 'refs': []} for role, payload in payloads.items()}


class SelectionSplitAI(FakeAIAdapter):
    """asset_selection and production_plan share the route key 'selection'; pick the scripted response by the envelope instructions (fake_ai.py stays untouched)."""

    def __init__(self, route, **kwargs):
        super().__init__(route, **kwargs)
        self._selection_by_instructions = {
            'Return JSON for asset_selection': {'text': json.dumps(_selection_json()), 'refs': []},
            'Return JSON for production_plan': {'text': json.dumps(_plan_json()), 'refs': []}}

    def invoke(self, decision, envelope):
        if self._route.role_for_reservation(decision.capacity_reservation_ref) == 'selection':
            self._responses['selection'] = copy.deepcopy(self._selection_by_instructions[envelope.instructions])
        return super().invoke(decision, envelope)


class SpyRoute(FakeProviderRoute):
    def __init__(self):
        super().__init__()
        self.requests = []

    def resolve(self, request):
        self.requests.append(copy.deepcopy(dict(request)))
        return super().resolve(request)


class Rig:
    def __init__(self, uow=None, source_rev='v1'):
        self.uow = uow if uow is not None else InMemoryUnitOfWork()
        self.route = SpyRoute()
        self.ai = SelectionSplitAI(self.route, responses=_responses(source_rev), config_revision='cfg-fake')
        self.pipeline = CreativePipeline(
            uow_factory=lambda: self.uow, route=self.route, ai=self.ai,
            instructions={role: f'Return JSON for {role}' for role in AI_ROLES})



def _prepare(rig):
    pipeline = rig.pipeline
    out = {}
    out['snapshot'] = pipeline.build_production_snapshot(context=_ctx(1), idempotency_key='k-snap', **_snapshot_args())
    out['analysis'] = pipeline.analyze_content(
        context=_ctx(2), idempotency_key='k-analysis', snapshot_id='snap-1', analysis_id='an-1', revision=1)
    out['angles'] = pipeline.generate_story_angles(
        context=_ctx(3), idempotency_key='k-angles', snapshot_id='snap-1', analysis_id='an-1', analysis_revision=1,
        set_id='set-1', requested_count=2, variation_policy_revision='var-v1')
    return out


def _variant_args(fingerprint, **overrides):
    args = dict(
        snapshot_id='snap-1', variant_ref='variant-1', candidate=fingerprint, completed=(), active_reservations=(),
        same_run=(), registry_revision=0, variation_policy_revision='var-v1', phase='plan')
    args.update(overrides)
    return args


def _run_chain(rig):
    pipeline = rig.pipeline
    out = _prepare(rig)
    out['script'] = pipeline.generate_script(context=_ctx(4), idempotency_key='k-script', **SCRIPT_ARGS)
    out['selection'] = pipeline.select_creative_assets(
        context=_ctx(5), idempotency_key='k-select', snapshot_id='snap-1', script_version_id='script-1',
        set_id='set-1', angle_id='angle-a', **_asset_inputs())
    out['plan'] = pipeline.build_production_plan(
        context=_ctx(6), idempotency_key='k-plan', snapshot_id='snap-1', script_version_id='script-1',
        selection=out['selection'].output, production_plan_id='plan-1', preset_revision_ref='preset-v1')
    angle = rig.uow.angle_sets.latest('set-1').record.angles[0]
    out['fingerprint'] = build_variant_fingerprint(
        script=out['script'].output, plan=out['plan'].output, selection=out['selection'].output,
        angle_distinction_fingerprint=angle.distinction_fingerprint)
    out['variant'] = pipeline.validate_variant(context=_ctx(7), idempotency_key='k-variant', **_variant_args(out['fingerprint']))
    out['metadata'] = pipeline.generate_output_metadata(
        context=_ctx(8), idempotency_key='k-meta', snapshot_id='snap-1', source_job_ref='job-1',
        source_output_refs=('variant-1',), metadata_revision=1)
    return out



COMMANDS = (
    ('snapshot', 'k-snap', 'BuildProductionSnapshot', 'snap-1', 'ProductionSnapshotCommitted'),
    ('analysis', 'k-analysis', 'AnalyzeContent', 'an-1', None),
    ('angles', 'k-angles', 'GenerateStoryAngles', 'set-1', 'StoryAnglesGenerated'),
    ('script', 'k-script', 'GenerateScript', 'script-1', 'ScriptVersionCreated'),
    ('selection', 'k-select', 'SelectCreativeAssets', None, None),
    ('plan', 'k-plan', 'BuildProductionPlan', 'plan-1', 'ProductionPlanCreated'),
    ('variant', 'k-variant', 'ValidateVariant', 'variant-1', 'VariantValidated'),
    ('metadata', 'k-meta', 'GenerateOutputMetadata', 'job-1', 'OutputMetadataCreated'),
)
AI_STEPS = (
    ('analysis', 'k-analysis', 'content_analysis'), ('angles', 'k-angles', 'story_angles'),
    ('script', 'k-script', 'script_generation'), ('selection', 'k-select', 'asset_selection'),
    ('plan', 'k-plan', 'production_plan'), ('metadata', 'k-meta', 'output_metadata'),
)


def test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: TST-INT-INV-004, TST-INT-INV-005' in doc.splitlines()


def test_network_is_blocked_for_every_test():
    with pytest.raises(OSError):
        socket.create_connection(('example.com', 80))
    with pytest.raises(OSError):
        socket.getaddrinfo('example.com', 80)


def test_every_command_is_one_unit_of_work_with_receipt_and_outbox_event():
    rig = Rig()
    out = _run_chain(rig)
    uow = rig.uow
    for name, key, command, aggregate, event in COMMANDS:
        result = out[name]
        assert (result.command, result.replayed) == (command, False)
        assert uow.receipts.get(WS, key) == result.receipt
        assert re.fullmatch('[0-9a-f]{64}', result.receipt.request_hash)
        assert result.receipt.aggregate_revision == 1
        assert (result.event_id is None) == (event is None)
        if aggregate is not None:
            assert result.receipt.aggregate_ref == aggregate
    assert out['selection'].receipt.aggregate_ref == 'selection:' + out['selection'].output.selection_fingerprint
    expected = [(event, aggregate) for _, _, _, aggregate, event in COMMANDS if event]
    assert [(r.event_type, r.aggregate_id) for r in uow.outbox.records()] == expected
    assert [r.event_id for r in uow.outbox.records()] == [out[name].event_id for name, _, _, _, event in COMMANDS if event]
    assert uow.snapshots.get('snap-1') is out['snapshot'].output
    assert uow.analyses.latest('an-1').record is out['analysis'].output
    assert uow.angle_sets.latest('set-1').record is out['angles'].output
    assert uow.scripts.latest('script-1').record is out['script'].output
    assert uow.plans.latest('plan-1').record is out['plan'].output
    assert uow.variant_validations.latest('variant-1').record is out['variant'].output
    assert uow.output_metadata.latest('job-1').record is out['metadata'].output
    assert out['variant'].output.valid is True
    for _, key, role in AI_STEPS:
        assert uow.invocations.latest('ws-1:' + key).record.ai_role == ROUTE_KEY_OF[role]
    assert uow.invocations.latest('ws-1:k-snap') is None and uow.invocations.latest('ws-1:k-variant') is None
    assert rig.ai.invoke_calls == 6 and rig.ai.calls_by_role == {'analysis': 1, 'angle': 1, 'script': 1, 'selection': 2, 'metadata': 1}



def test_every_output_carries_snapshot_model_prompt_config_and_input_revision():
    rig = Rig()
    out = _run_chain(rig)
    snapshot = out['snapshot'].output
    for name, key, role in AI_STEPS:
        trace = out[name].trace
        record = rig.uow.invocations.latest(trace.invocation_key).record
        assert trace.invocation_key == 'ws-1:' + key
        assert (trace.snapshot_ref, trace.model_ref, trace.prompt_revision) == ('snap-1', 'fake-model', f'{role}-r1')
        assert trace.model_ref == record.model_ref and trace.prompt_revision == record.prompt_revision
        assert trace.config_revision == snapshot.configuration_bundle_fingerprint
        assert trace.input_revision == snapshot.source_set_fingerprint
        assert (record.ai_role, record.config_revision, record.error) == (ROUTE_KEY_OF[role], 'cfg-fake', None)
    for name in ('snapshot', 'variant'):
        trace = out[name].trace
        assert (trace.snapshot_ref, trace.model_ref, trace.prompt_revision) == ('snap-1', None, None)
        assert trace.config_revision == snapshot.configuration_bundle_fingerprint
    analysis = out['analysis'].output
    assert analysis.snapshot_id == 'snap-1'
    assert (analysis.trace.model, analysis.trace.policy_revision) == ('fake-model', 'cfg-fake')
    assert analysis.trace.prompt_ref.revision_id == 'content_analysis-r1'


def test_generate_script_without_committed_snapshot_is_refused_with_zero_ai_calls():
    rig = Rig()
    with pytest.raises(PipelineRejected) as caught:
        rig.pipeline.generate_script(context=_ctx(1), idempotency_key='k-script', **SCRIPT_ARGS)
    assert (caught.value.code, caught.value.reason) == ('INPUT_NOT_READY', 'snapshot_not_committed')
    assert (rig.ai.invoke_calls, rig.route.resolve_calls, rig.route.requests) == (0, 0, [])
    assert rig.uow.receipts.get(WS, 'k-script') is None and rig.uow.scripts.latest('script-1') is None
    assert rig.uow.invocations.latest('ws-1:k-script') is None and rig.uow.outbox.records() == ()
    rig.pipeline.build_production_snapshot(context=_ctx(2), idempotency_key='k-snap', **_snapshot_args())
    with pytest.raises(PipelineRejected) as missing:
        rig.pipeline.generate_script(context=_ctx(3), idempotency_key='k-script', **SCRIPT_ARGS)
    assert missing.value.reason == 'analysis_not_found'
    assert (rig.ai.invoke_calls, rig.route.resolve_calls) == (0, 0)


NO_SNAPSHOT_CALLS = {
    'analyze_content': dict(analysis_id='an-1', revision=1),
    'generate_story_angles': dict(
        analysis_id='an-1', analysis_revision=1, set_id='set-1', requested_count=2, variation_policy_revision='var-v1'),
    'generate_output_metadata': dict(source_job_ref='job-1', source_output_refs=('variant-1',), metadata_revision=1),
}


@pytest.mark.parametrize('name', sorted(NO_SNAPSHOT_CALLS))
def test_ai_commands_without_committed_snapshot_never_reach_the_ai(name):
    rig = Rig()
    with pytest.raises(PipelineRejected) as caught:
        getattr(rig.pipeline, name)(context=_ctx(1), idempotency_key='k-x', snapshot_id='snap-missing', **NO_SNAPSHOT_CALLS[name])
    assert caught.value.reason == 'snapshot_not_committed'
    assert (rig.ai.invoke_calls, rig.route.resolve_calls) == (0, 0)
    assert rig.uow.receipts.get(WS, 'k-x') is None and rig.uow.outbox.records() == ()



def test_refused_timeline_snapshot_is_never_committed_and_script_is_refused():
    rig = Rig()
    with pytest.raises(TimelinePolicyViolation) as caught:
        rig.pipeline.build_production_snapshot(
            context=_ctx(1), idempotency_key='k-tl', timeline_policy=TIMELINE_POLICY, **_snapshot_args('snap-tl', mode='from_then_to_now'))
    assert caught.value.reason == 'event_update_accepted_missing'
    assert rig.uow.snapshots.get('snap-tl') is None and rig.uow.receipts.get(WS, 'k-tl') is None
    assert rig.uow.outbox.records() == ()
    with pytest.raises(PipelineRejected) as refused:
        rig.pipeline.generate_script(context=_ctx(2), idempotency_key='k-s', **{**SCRIPT_ARGS, 'snapshot_id': 'snap-tl'})
    assert refused.value.reason == 'snapshot_not_committed'
    assert (rig.ai.invoke_calls, rig.route.resolve_calls) == (0, 0)


def test_from_then_to_now_goes_through_d07_and_other_modes_do_not_need_the_policy(monkeypatch):
    seen = []

    def spy(snapshot, policy):
        seen.append((snapshot.snapshot_id, snapshot.production_mode, policy))
        return authorize_timeline_narrative(snapshot, policy)

    monkeypatch.setattr(pipeline_module, 'authorize_timeline_narrative', spy)
    rig = Rig()
    sources = [
        {'ref_type': 'article_revision', 'ref_id': 'a-1', 'revision_id': 'v1'},
        {'ref_type': 'event_update_accepted', 'ref_id': 'u-1', 'revision_id': 'rev-1'},
    ]
    args = _snapshot_args(
        'snap-tl', mode='from_then_to_now', source_refs=sources, content_ref_types=['article_revision', 'event_update_accepted'])
    result = rig.pipeline.build_production_snapshot(context=_ctx(1), idempotency_key='k-tl', timeline_policy=TIMELINE_POLICY, **args)
    assert seen == [('snap-tl', 'from_then_to_now', TIMELINE_POLICY)]
    assert rig.uow.snapshots.get('snap-tl') is result.output
    with pytest.raises(PipelineRejected) as caught:
        rig.pipeline.build_production_snapshot(context=_ctx(2), idempotency_key='k-tl2', **{**args, 'snapshot_id': 'snap-tl2'})
    assert caught.value.reason == 'missing_timeline_policy'
    assert rig.uow.snapshots.get('snap-tl2') is None
    rig.pipeline.build_production_snapshot(context=_ctx(3), idempotency_key='k-single', **_snapshot_args('snap-1'))
    assert len(seen) == 1


def test_missing_prompt_revision_in_snapshot_is_refused_before_any_ai_call():
    rig = Rig()
    bundle_only = [{'ref_type': 'config_bundle', 'ref_id': 'bundle', 'revision_id': 'r1'}]
    rig.pipeline.build_production_snapshot(
        context=_ctx(1), idempotency_key='k-snap', **_snapshot_args(configuration_revision_refs=bundle_only))
    with pytest.raises(PipelineRejected) as caught:
        rig.pipeline.analyze_content(context=_ctx(2), idempotency_key='k-analysis', snapshot_id='snap-1', analysis_id='an-1', revision=1)
    assert (caught.value.reason, caught.value.field) == ('missing_prompt_revision', 'content_analysis')
    assert (rig.ai.invoke_calls, rig.route.resolve_calls) == (0, 0)
    assert rig.uow.analyses.latest('an-1') is None



def test_config_and_source_change_after_snapshot_keeps_old_job_refs_and_new_job_gets_new_revisions():
    old = Rig()
    snap_old = old.pipeline.build_production_snapshot(
        context=_ctx(1), idempotency_key='k-s1', **_snapshot_args('snap-1', cfg='r1', source_rev='v1')).output
    new = Rig(uow=old.uow, source_rev='v2')
    snap_new = new.pipeline.build_production_snapshot(
        context=_ctx(2), idempotency_key='k-s2', **_snapshot_args('snap-2', cfg='r2', source_rev='v2')).output
    job_old = old.pipeline.analyze_content(context=_ctx(3), idempotency_key='k-a1', snapshot_id='snap-1', analysis_id='an-1', revision=1)
    job_new = new.pipeline.analyze_content(context=_ctx(4), idempotency_key='k-a2', snapshot_id='snap-2', analysis_id='an-2', revision=1)
    assert old.uow.snapshots.get('snap-1') is snap_old and old.uow.snapshots.get('snap-2') is snap_new
    assert snap_old.configuration_bundle_fingerprint != snap_new.configuration_bundle_fingerprint
    assert snap_old.source_set_fingerprint != snap_new.source_set_fingerprint
    for job, snap, rev, source_rev in ((job_old, snap_old, 'r1', 'v1'), (job_new, snap_new, 'r2', 'v2')):
        assert job.trace.snapshot_ref == snap.snapshot_id
        assert job.trace.config_revision == snap.configuration_bundle_fingerprint
        assert job.trace.input_revision == snap.source_set_fingerprint
        assert job.trace.prompt_revision == f'content_analysis-{rev}'
        assert job.output.configuration_bundle_fingerprint == snap.configuration_bundle_fingerprint
        assert job.output.source_set_fingerprint == snap.source_set_fingerprint
        assert job.output.facts[0].evidence[0].revision_id == source_rev
    assert old.uow.invocations.latest('ws-1:k-a1').record.prompt_revision == 'content_analysis-r1'
    assert old.route.requests[0]['snapshot_ref'] == 'snap-1' and new.route.requests[0]['snapshot_ref'] == 'snap-2'
    assert all(ref.endswith('r1') for ref in old.route.requests[0]['config_refs'])
    assert all(ref.endswith('r2') for ref in new.route.requests[0]['config_refs'])



def test_same_key_and_payload_returns_old_receipt_without_second_script():
    rig = Rig()
    out = _run_chain(rig)
    calls, events = rig.ai.invoke_calls, len(rig.uow.outbox.records())
    again = rig.pipeline.generate_script(context=_ctx(30), idempotency_key='k-script', **SCRIPT_ARGS)
    assert again.replayed is True and again.receipt == out['script'].receipt
    assert (again.output, again.event_id, again.trace) == (None, None, None)
    assert len(rig.uow.scripts.revisions('script-1')) == 1
    assert rig.ai.invoke_calls == calls and len(rig.uow.outbox.records()) == events
    assert rig.ai.calls_by_role['script'] == 1
    snap = rig.pipeline.build_production_snapshot(context=_ctx(31), idempotency_key='k-snap', **_snapshot_args())
    assert snap.replayed is True and snap.receipt == out['snapshot'].receipt


def test_same_key_with_different_payload_is_an_idempotency_conflict_on_request_hash():
    rig = Rig()
    out = _run_chain(rig)
    calls = rig.ai.invoke_calls
    with pytest.raises(IdempotencyConflict) as caught:
        rig.pipeline.generate_script(context=_ctx(32), idempotency_key='k-script', **{**SCRIPT_ARGS, 'script_version_id': 'script-2'})
    assert str(caught.value) == 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'
    assert caught.value.existing_hash == out['script'].receipt.request_hash != caught.value.incoming_hash
    assert re.fullmatch('[0-9a-f]{64}', caught.value.incoming_hash)
    with pytest.raises(IdempotencyConflict):
        rig.pipeline.analyze_content(context=_ctx(33), idempotency_key='k-script', snapshot_id='snap-1', analysis_id='an-2', revision=1)
    assert rig.uow.scripts.latest('script-2') is None and rig.uow.analyses.latest('an-2') is None
    assert rig.ai.invoke_calls == calls
    assert rig.uow.receipts.get(WS, 'k-script') == out['script'].receipt


def test_new_key_for_same_script_id_does_not_create_a_second_script():
    rig = Rig()
    _run_chain(rig)
    events = len(rig.uow.outbox.records())
    with pytest.raises(RevisionConflictError):
        rig.pipeline.generate_script(context=_ctx(34), idempotency_key='k-script-2', **SCRIPT_ARGS)
    assert len(rig.uow.scripts.revisions('script-1')) == 1
    assert rig.uow.receipts.get(WS, 'k-script-2') is None and rig.uow.invocations.latest('ws-1:k-script-2') is None
    assert len(rig.uow.outbox.records()) == events



def test_outbox_failure_rolls_back_output_record_receipt_and_outbox_together():
    rig = Rig()
    _prepare(rig)
    uow = rig.uow
    events = len(uow.outbox.records())

    def broken(*args, **kwargs):
        raise RuntimeError('outbox down')

    uow.outbox.append_event = broken
    with pytest.raises(RuntimeError):
        rig.pipeline.generate_script(context=_ctx(4), idempotency_key='k-script', **SCRIPT_ARGS)
    assert uow.scripts.latest('script-1') is None and uow.invocations.latest('ws-1:k-script') is None
    assert uow.receipts.get(WS, 'k-script') is None and len(uow.outbox.records()) == events
    del uow.outbox.append_event
    result = rig.pipeline.generate_script(context=_ctx(5), idempotency_key='k-script', **SCRIPT_ARGS)
    assert result.replayed is False and uow.scripts.latest('script-1').record is result.output
    assert len(uow.outbox.records()) == events + 1


def test_invalid_variant_is_stored_with_receipt_without_event_and_revisions_increase():
    rig = Rig()
    out = _run_chain(rig)
    events = len(rig.uow.outbox.records())
    sibling = SameRunVariant(ref_id='sib-1', fingerprint=out['fingerprint'])
    bad = rig.pipeline.validate_variant(
        context=_ctx(40), idempotency_key='k-variant-2', **_variant_args(out['fingerprint'], variant_ref='variant-2', same_run=(sibling,)))
    assert bad.output.valid is False and 'same_run_angle_duplicate' in bad.output.reason_codes
    assert bad.event_id is None and len(rig.uow.outbox.records()) == events
    assert rig.uow.variant_validations.latest('variant-2').record is bad.output
    assert rig.uow.receipts.get(WS, 'k-variant-2') == bad.receipt
    later = rig.pipeline.validate_variant(
        context=_ctx(41), idempotency_key='k-variant-out', **_variant_args(out['fingerprint'], phase='output', output_hash='a' * 64))
    assert later.receipt.aggregate_revision == 2 and later.event_id not in (None, out['variant'].event_id)


def test_pipeline_source_has_no_adapter_clock_network_import_and_outbox_only_through_uow():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    names = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    names |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    banned = {'socket', 'uuid', 'time', 'random', 'datetime'}
    assert not [name for name in names if name.split('.')[0] in banned or name.startswith('creative.adapters')]
    appends = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr == 'append_event']
    assert appends and all(
        isinstance(node.value, ast.Attribute) and node.value.attr == 'outbox'
        and isinstance(node.value.value, ast.Name) and node.value.value.id == 'uow'
        for node in appends)
