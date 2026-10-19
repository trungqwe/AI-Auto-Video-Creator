"""D-17: Projection truy vết read-only từ output về snapshot, analysis, angle, model/prompt/config revision và input revision.

coveredIds: acceptance §12 mục 7, exit gate G1
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import pathlib
import socket

import pytest
from creative.adapters.fake_ai import FakeAIAdapter, FakeProviderRoute
from creative.adapters.memory import InMemoryUnitOfWork
from creative.domain.analysis import AnalysisTrace, ContentAnalysis
from creative.domain.angles import StoryAngle, StoryAngleSet
from creative.domain.invocation import AIInvocationRecord, InvocationUsage, redact_error
from creative.domain.output_metadata import OutputMetadata
from creative.domain.production_plan import ProductionPlan
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from creative.domain.snapshot import build_production_snapshot
from creative.domain.untrusted import PromptEnvelope, UntrustedText
from creative.domain.variant import VariantValidationResult
from creative.ports.repositories import KIND_OUTPUT_METADATA, KIND_PLAN, KIND_SCRIPT, KIND_VARIANT_VALIDATION
from creative.projections import trace_queries as tq

SOURCE = pathlib.Path(__file__).resolve().parents[3] / 'src' / 'creative' / 'projections' / 'trace_queries.py'
CANARY = 'sk-canary-SECRET-0123456789'
TABLES = ('snapshots', 'analyses', 'angle_sets', 'scripts', 'plans', 'variant_validations', 'output_metadata', 'invocations')
OUTPUTS = (
    (KIND_SCRIPT, 'script-key'),
    (KIND_PLAN, 'plan-key'),
    (KIND_VARIANT_VALIDATION, 'validation-key'),
    (KIND_OUTPUT_METADATA, 'job'),
)


def _ref(ws, ref_id='a1', ref_type='article', revision='r1'):
    return ResourceRef(workspace_id=ws, ref_type=ref_type, ref_id=ref_id, revision_id=revision)


def _snapshot(s):
    return build_production_snapshot(
        snapshot_id=f'snap{s}',
        production_mode='single_article',
        source_refs=[{'ref_type': 'article', 'ref_id': f'a{s}', 'revision_id': 'r1'}],
        index_revision_refs=[{'ref_type': 'index', 'ref_id': f'i{s}', 'revision_id': 'ri1'}],
        configuration_revision_refs=[{'ref_type': 'config', 'ref_id': f'c{s}', 'revision_id': 'rc1'}],
        content_ref_types=['article'],
        eligibility_reason='eligible',
        snapshot_timestamp='2026-10-19T00:00:00Z',
    )


def _analysis(snapshot, ws, s, revision):
    return ContentAnalysis(
        analysis_id=f'analysis{s}',
        revision=revision,
        snapshot_id=snapshot.snapshot_id,
        source_set_fingerprint=snapshot.source_set_fingerprint,
        configuration_bundle_fingerprint=snapshot.configuration_bundle_fingerprint,
        source_refs=snapshot.source_refs,
        topic=f'topic {revision}',
        entities=(),
        timeline=(),
        locations=(),
        facts=(),
        uncertainties=(),
        contradictions=(),
        event_relation='standalone',
        update_context='',
        risk_flags=(),
        narrative_opportunities=(),
        media_needs=(),
        trace=AnalysisTrace('prov', 'model', _ref(ws, f'prompt{s}', 'prompt_revision', 'pr1'), 'policy-1'),
    )


def _angle_set(ws, s):
    angle = StoryAngle(
        angle_id=f'angle{s}', title='T', summary='S', narrative_question='Q?', focus_entities=('city',),
        timeframe='2026', evidence_refs=(_ref(ws),), planned_inference_elements=(), planned_creative_elements=(),
        suitability='high', risk_flags=(),
    )
    return StoryAngleSet(
        set_id=f'set{s}', analysis_id=f'analysis{s}', analysis_revision=1, requested_count=1, generation='initial',
        variation_policy_revision='vp-1', angles=(angle,), excluded=(),
    )


def _script(ws, s, n):
    segment = ScriptSegment(
        segment_id='s1', order=0, text=f'hello world {n}', claim_mode='source_backed', scene_intent='intro',
        source_refs=(_ref(ws),), disclosure=None, word_count=3, estimated_seconds=1.0,
    )
    return ScriptVersion(
        script_version_id=f'script{s}-{n}', language='en', hook_intent='hook', thumbnail_transition='cut',
        segments=(segment,), pronunciation_hints=(), speech_rate=2.0, estimated_duration_seconds=1.0,
    )


def _plan(s):
    return ProductionPlan(
        production_plan_id=f'plan{s}', script_version_id=f'script{s}-1', script_fingerprint='a' * 64,
        preset_revision_ref='preset-1', selection_fingerprint='b' * 64, timeline={}, hook_placement={},
        thumbnail_overlay_intent='overlay', voice_profile_intent={}, music_cues=(), sfx_cues=(),
        subtitle_style_intent={}, allowed_fallbacks=(), output_metadata_ref=None,
        output_metadata_requirement='required', plan_fingerprint='c' * 64,
    )


def _validation():
    return VariantValidationResult(
        valid=True, same_run_angle_distinct=True, exact_duplicate=False, distinct_factors=('voice',),
        nearest_prior_refs=(), reason_codes=('variant_distinct',), input_hashes={'candidate': 'a' * 64},
        registry_revision=3, phase='plan', variation_policy_revision='vp-1', own_reservation_id=None, output_hash=None,
    )


def _metadata(s):
    return OutputMetadata(
        title='Title', caption='Caption', hashtags=('#one', '#two', '#three'), language='en',
        source_job_ref=f'job{s}', source_output_refs=('vv-1',), metadata_revision=1,
    )


def _invocation(role, prompt_revision='pr1', error=None):
    fields = dict(
        ai_role=role, provider_ref='prov-1', model_ref='model-1', account_ref='acc-1', route_revision='route-1',
        prompt_revision=prompt_revision, config_revision='cfg-1', input_fingerprint='a' * 64,
        usage=InvocationUsage(1, 1, 'low'), latency_ms=5, attempt=1, fallback_path=('prov-1',),
        validation_result='passed',
    )
    if error is None:
        fields['output_fingerprint'] = 'b' * 64
    else:
        fields['error'] = error
    return AIInvocationRecord(**fields)


def _link(ws, kind, key, revision, s='', **over):
    fields = dict(
        workspace_id=ws, output_kind=kind, output_key=key, output_revision=revision, snapshot_id=f'snap{s}',
        analysis_id=f'analysis{s}', analysis_revision=1, angle_set_key=f'angles{s}', angle_set_revision=1,
        angle_id=f'angle{s}',
        invocation_refs=(tq.InvocationRef(key=f'inv{s}-1', revision=1), tq.InvocationRef(key=f'inv{s}-2', revision=1)),
    )
    fields.update(over)
    return tq.TraceLink(**fields)


def _seed(uow, ws='ws-1', s='', invocations=None):
    snapshot = _snapshot(s)
    first, second = invocations or (_invocation('analysis'), _invocation('script_generation'))
    with uow:
        uow.snapshots.add(snapshot)
        uow.analyses.append(f'analysis{s}', 1, _analysis(snapshot, ws, s, 1))
        uow.analyses.append(f'analysis{s}', 2, _analysis(snapshot, ws, s, 2))
        uow.angle_sets.append(f'angles{s}', 1, _angle_set(ws, s))
        uow.scripts.append(f'script-key{s}', 1, _script(ws, s, 1))
        uow.scripts.append(f'script-key{s}', 2, _script(ws, s, 2))
        uow.plans.append(f'plan-key{s}', 1, _plan(s))
        uow.variant_validations.append(f'validation-key{s}', 1, _validation())
        uow.output_metadata.append(f'job{s}', 1, _metadata(s))
        uow.invocations.append(f'inv{s}-1', 1, first)
        uow.invocations.append(f'inv{s}-2', 1, second)
        uow.commit()
    outputs = (
        (KIND_SCRIPT, f'script-key{s}', 1), (KIND_SCRIPT, f'script-key{s}', 2), (KIND_PLAN, f'plan-key{s}', 1),
        (KIND_VARIANT_VALIDATION, f'validation-key{s}', 1), (KIND_OUTPUT_METADATA, f'job{s}', 1),
    )
    return tuple(_link(ws, kind, key, revision, s) for kind, key, revision in outputs)


class _ReadOnlyTable:
    READS = frozenset({'get', 'latest', 'revisions'})

    def __init__(self, name, table, calls):
        self._name = name
        self._table = table
        self._calls = calls

    def __getattr__(self, attr):
        if attr not in self.READS:
            raise AssertionError(f'{self._name}.{attr} is not a read API')
        self._calls.append((self._name, attr))
        return getattr(self._table, attr)


class _GuardedStore:
    def __init__(self, uow):
        self.calls = []
        for name in TABLES:
            setattr(self, name, _ReadOnlyTable(name, getattr(uow, name), self.calls))


def _state(uow):
    return tuple(dict(table._rows) for table in uow._tables)


def _trace(store, links, kind, key, ws='ws-1', **kw):
    return tq.trace_output(store, links, workspace_id=ws, output_kind=kind, output_key=key, **kw)


def _keys(value):
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


def _ai_records():
    route = FakeProviderRoute()
    responses = {'analysis': {'text': 'a', 'refs': []}, 'script_generation': {'text': 'b', 'refs': []}}
    adapter = FakeAIAdapter(route, responses=responses, config_revision='cfg-r1')
    envelope = PromptEnvelope(
        prompt_ref=_ref('ws-1', 'p-1', 'prompt_revision', 'pr-ai'),
        instructions='Summarize the data field.',
        data=[UntrustedText(text='sample article', provenance=_ref('ws-1'))],
    )
    request = {
        'job_ref': 'job-1', 'snapshot_ref': 'snap', 'config_refs': ['c1'], 'data_sensitivity': 'internal',
        'quality_latency_cost_bounds': {}, 'allowed_fallbacks': [],
    }
    for role in ('analysis', 'script_generation'):
        adapter.invoke(route.resolve({**request, 'ai_role': role}), envelope)
    return route, adapter


@pytest.mark.parametrize(('kind', 'key'), OUTPUTS)
def test_trace_walks_output_back_to_every_origin(kind, key):
    uow = InMemoryUnitOfWork()
    links = _seed(uow)
    trace = _trace(uow, links, kind, key)
    revision = 2 if kind == KIND_SCRIPT else 1
    assert (trace.workspace_id, trace.output_kind, trace.output_key, trace.output_revision) == ('ws-1', kind, key, revision)
    assert trace.snapshot['snapshot_id'] == 'snap'
    assert [r['revision_id'] for r in trace.snapshot['source_refs']] == ['r1']
    assert [r['revision_id'] for r in trace.snapshot['index_revision_refs']] == ['ri1']
    assert [r['revision_id'] for r in trace.snapshot['configuration_revision_refs']] == ['rc1']
    assert trace.snapshot['source_set_fingerprint'] == uow.snapshots.get('snap').source_set_fingerprint
    assert (trace.analysis['analysis_id'], trace.analysis['revision'], trace.analysis['snapshot_id']) == ('analysis', 1, 'snap')
    assert (trace.analysis['provider'], trace.analysis['model']) == ('prov', 'model')
    assert trace.analysis['prompt_ref']['revision_id'] == 'pr1'
    assert (trace.angle['set_id'], trace.angle['angle_id'], trace.angle['analysis_revision']) == ('set', 'angle', 1)
    assert trace.angle['variation_policy_revision'] == 'vp-1' and trace.angle['distinction_fingerprint']
    seen = [(i.ai_role, i.provider_ref, i.model_ref, i.prompt_revision, i.config_revision) for i in trace.invocations]
    assert seen == [
        ('analysis', 'prov-1', 'model-1', 'pr1', 'cfg-1'),
        ('script_generation', 'prov-1', 'model-1', 'pr1', 'cfg-1'),
    ]
    assert all(i.input_fingerprint == 'a' * 64 and i.route_revision == 'route-1' for i in trace.invocations)


def test_trace_payload_is_json_safe_immutable_and_fresh():
    uow = InMemoryUnitOfWork()
    links = _seed(uow)
    trace = _trace(uow, links, KIND_PLAN, 'plan-key')
    payload = trace.to_payload()
    assert json.loads(json.dumps(payload)) == payload
    assert set(payload) == {'workspace_id', 'output', 'snapshot', 'analysis', 'angle', 'invocations', 'history'}
    assert payload['output']['fingerprint'] == 'c' * 64
    assert _trace(uow, links, KIND_OUTPUT_METADATA, 'job').output_fingerprint is None
    payload['snapshot']['source_refs'].clear()
    assert trace.to_payload()['snapshot']['source_refs']
    with pytest.raises(TypeError):
        trace.snapshot['snapshot_id'] = 'x'
    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.output_key = 'x'


def test_revision_history_keeps_every_revision_without_overwrite():
    uow = InMemoryUnitOfWork()
    links = _seed(uow)
    entries = tq.list_output_revisions(uow, links, workspace_id='ws-1', output_kind=KIND_SCRIPT, output_key='script-key')
    assert [e.revision for e in entries] == [1, 2]
    stored = uow.scripts.revisions('script-key')
    fingerprints = [e.output_fingerprint for e in entries]
    assert fingerprints == [item.record.script_fingerprint for item in stored]
    assert fingerprints[0] != fingerprints[1]
    latest = _trace(uow, links, KIND_SCRIPT, 'script-key')
    first = _trace(uow, links, KIND_SCRIPT, 'script-key', output_revision=1)
    assert (latest.output_revision, first.output_revision) == (2, 1)
    assert (latest.output_fingerprint, first.output_fingerprint) == (fingerprints[1], fingerprints[0])
    assert first.history == latest.history == entries
    assert first.analysis['revision'] == 1 and len(uow.analyses.revisions('analysis')) == 2
    with pytest.raises(tq.TraceNotFound):
        _trace(uow, links, KIND_SCRIPT, 'script-key', output_revision=3)


def test_workspace_filter_never_returns_another_workspaces_output():
    uow = InMemoryUnitOfWork()
    links = _seed(uow, 'ws-1') + _seed(uow, 'ws-2', '-b')
    assert tq.list_outputs(links, workspace_id='ws-1') == (
        (KIND_OUTPUT_METADATA, 'job', 1), (KIND_PLAN, 'plan-key', 1), (KIND_SCRIPT, 'script-key', 1),
        (KIND_SCRIPT, 'script-key', 2), (KIND_VARIANT_VALIDATION, 'validation-key', 1),
    )
    assert {key for _, key, _ in tq.list_outputs(links, workspace_id='ws-2')} == {
        'job-b', 'plan-key-b', 'script-key-b', 'validation-key-b',
    }
    assert tq.list_outputs(links, workspace_id='ws-3') == ()
    assert _trace(uow, links, KIND_PLAN, 'plan-key-b', ws='ws-2').workspace_id == 'ws-2'
    with pytest.raises(tq.TraceNotFound) as other:
        _trace(uow, links, KIND_PLAN, 'plan-key-b', ws='ws-1')
    with pytest.raises(tq.TraceNotFound) as reverse:
        _trace(uow, links, KIND_PLAN, 'plan-key', ws='ws-2')
    with pytest.raises(tq.TraceNotFound) as unknown:
        _trace(uow, links, KIND_PLAN, 'plan-missing')
    assert str(other.value) == str(reverse.value) == str(unknown.value)
    other_history = tq.list_output_revisions(
        uow, links, workspace_id='ws-1', output_kind=KIND_SCRIPT, output_key='script-key-b')
    assert other_history == ()


@pytest.mark.parametrize(('kind', 'key', 'field'), [
    (KIND_PLAN, 'plan-key', 'analysis.trace.prompt_ref'),
    (KIND_SCRIPT, 'script-key', 'script.source_refs'),
])
def test_chain_from_another_workspace_is_rejected(kind, key, field):
    uow = InMemoryUnitOfWork()
    links = tuple(_link('ws-2', l.output_kind, l.output_key, l.output_revision) for l in _seed(uow, 'ws-1'))
    with pytest.raises(tq.TraceIncomplete) as error:
        _trace(uow, links, kind, key, ws='ws-2')
    assert (error.value.reason, error.value.field) == ('workspace_mismatch', field)


BROKEN_CHAINS = (
    ({'snapshot_id': 'nope'}, 'snapshot_missing', 'snapshot'),
    ({'snapshot_id': 'snap-b'}, 'snapshot_mismatch', 'analysis.snapshot_id'),
    ({'analysis_revision': 9}, 'analysis_missing', 'analysis'),
    ({'angle_set_key': 'nope'}, 'angle_set_missing', 'angle_set'),
    ({'angle_id': 'nope'}, 'angle_missing', 'angle_id'),
    ({'invocation_refs': (tq.InvocationRef(key='nope', revision=1),)}, 'invocation_missing', 'invocation_refs[0]'),
)


@pytest.mark.parametrize(('over', 'reason', 'field'), BROKEN_CHAINS)
def test_broken_chain_fails_closed_with_fixed_codes(over, reason, field):
    uow = InMemoryUnitOfWork()
    _seed(uow)
    _seed(uow, 'ws-1', '-b')
    links = (_link('ws-1', KIND_PLAN, 'plan-key', 1, **over),)
    with pytest.raises(tq.TraceIncomplete) as error:
        _trace(uow, links, KIND_PLAN, 'plan-key')
    assert (error.value.reason, error.value.field) == (reason, field)


def test_trace_without_prompt_revision_is_rejected():
    uow = InMemoryUnitOfWork()
    links = _seed(uow)
    object.__setattr__(uow.invocations.latest('inv-2').record, 'prompt_revision', '')
    with pytest.raises(tq.TraceIncomplete) as error:
        _trace(uow, links, KIND_PLAN, 'plan-key')
    assert (error.value.reason, error.value.field) == ('trace_field_missing', 'invocations[1].prompt_revision')


def test_trace_link_and_queries_reject_invalid_input():
    bad = (
        {'output_kind': 'analysis'}, {'workspace_id': ' '}, {'output_revision': 0}, {'analysis_revision': True},
        {'invocation_refs': ()}, {'invocation_refs': 'inv-1'}, {'invocation_refs': ('inv-1',)},
    )
    for over in bad:
        with pytest.raises(ValueError):
            _link('ws-1', KIND_PLAN, 'plan-key', 1, **over)
    with pytest.raises(ValueError):
        tq.InvocationRef(key='', revision=1)
    with pytest.raises(ValueError):
        tq.InvocationRef(key='inv', revision=0)
    link = _link('ws-1', KIND_PLAN, 'plan-key', 1)
    with pytest.raises(ValueError):
        tq.list_outputs((link, link), workspace_id='ws-1')
    with pytest.raises(TypeError):
        tq.list_outputs(('x',), workspace_id='ws-1')
    uow = InMemoryUnitOfWork()
    with pytest.raises(ValueError):
        _trace(uow, (), 'analysis', 'k')
    with pytest.raises(ValueError):
        _trace(uow, (), KIND_PLAN, ' ')
    with pytest.raises(ValueError):
        _trace(uow, (), KIND_PLAN, 'k', ws='')


WRITE_CALLS = frozenset({
    'append', 'add', 'put', 'append_event', 'begin', 'commit', 'rollback', 'invoke', 'resolve', 'resolve_all',
})
BANNED_IMPORTS = (
    'creative.adapters', 'creative.application', 'creative.worker', 'creative.ports.ai', 'controlplane', 'socket',
    'urllib', 'http', 'os', 'subprocess', 'time', 'datetime', 'random', 'uuid', 'temporalio', 'psycopg',
)


def test_query_never_invokes_ai_and_opens_no_connection(monkeypatch):
    route, adapter = _ai_records()
    uow = InMemoryUnitOfWork()
    links = _seed(uow, invocations=tuple(adapter.records))
    before = (route.resolve_calls, adapter.invoke_calls, dict(adapter.calls_by_role))
    assert before[1] == 2

    def boom(*args, **kwargs):
        raise AssertionError('network used by a trace query')

    monkeypatch.setattr(socket, 'create_connection', boom)
    monkeypatch.setattr(socket, 'getaddrinfo', boom)
    for link in links:
        trace = _trace(uow, links, link.output_kind, link.output_key, output_revision=link.output_revision)
        assert [i.prompt_revision for i in trace.invocations] == ['pr-ai', 'pr-ai']
        tq.list_output_revisions(
            uow, links, workspace_id='ws-1', output_kind=link.output_kind, output_key=link.output_key)
    tq.list_outputs(links, workspace_id='ws-1')
    assert (route.resolve_calls, adapter.invoke_calls, dict(adapter.calls_by_role)) == before
    assert not {'adapter', 'route', 'ai', 'port'} & set(inspect.signature(tq.trace_output).parameters)


def test_trace_never_exposes_secret_or_unredacted_error():
    uow = InMemoryUnitOfWork()
    failed = _invocation('analysis', error=redact_error(f'upstream rejected api_key={CANARY}', [CANARY]))
    leaked = _invocation('script_generation', error='placeholder')
    object.__setattr__(leaked, 'error', f'upstream rejected token {CANARY}')
    links = _seed(uow, invocations=(failed, leaked))
    forbidden = {'secret_value', 'api_key', 'access_token', 'refresh_token', 'authorization', 'password', 'text', 'narration'}
    for link in links:
        trace = _trace(uow, links, link.output_kind, link.output_key, output_revision=link.output_revision)
        payload = trace.to_payload()
        text = json.dumps(payload, ensure_ascii=False)
        assert CANARY not in text and 'hello world' not in text
        assert '[REDACTED]' in text and not forbidden & _keys(payload)
        assert trace.invocations[1].error == 'upstream rejected token [REDACTED]'


def test_query_is_read_only():
    uow = InMemoryUnitOfWork()
    links = _seed(uow)
    before = _state(uow)
    store = _GuardedStore(uow)
    with pytest.raises(AssertionError):
        store.plans.append('k', 1, object())
    for link in links:
        _trace(store, links, link.output_kind, link.output_key, output_revision=link.output_revision)
        tq.list_output_revisions(
            store, links, workspace_id='ws-1', output_kind=link.output_kind, output_key=link.output_key)
    assert not uow.active and _state(uow) == before
    assert {name for _, name in store.calls} <= {'get', 'latest', 'revisions'}
    assert {table for table, _ in store.calls} == set(TABLES)


def test_module_is_pure_read_only_code():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not called & WRITE_CALLS
    imported = {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
    imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    banned = [m for m in imported if any(m == b or m.startswith(b + '.') for b in BANNED_IMPORTS)]
    assert imported and banned == []


def test_test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8'))) or ''
    line = next((item for item in doc.splitlines() if item.startswith('coveredIds:')), '')
    assert 'acceptance §12 mục 7' in line and 'exit gate G1' in line
