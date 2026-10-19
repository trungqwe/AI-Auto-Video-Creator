"""D-13: Port lưu trữ append-only, UoW in-memory, outbox và event của D.

coveredIds: acceptance §12 mục 1 (lưu bất biến)
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
import pathlib

import pytest
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.events import contracts
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.interfaces.uow import IUnitOfWork
from creative.adapters import memory
from creative.domain.analysis import AnalysisTrace, ContentAnalysis
from creative.domain.angles import StoryAngle, StoryAngleSet
from creative.domain.invocation import AIInvocationRecord, InvocationUsage
from creative.domain.output_metadata import OutputMetadata
from creative.domain.production_plan import ProductionPlan
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from creative.domain.snapshot import build_production_snapshot
from creative.domain.variant import VariantValidationResult
from creative.ports import repositories

ROOT = pathlib.Path(__file__).resolve().parents[3]
ENVELOPE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'domain-event-envelope' / 'payloads.json'
BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'domain-event-envelope.json'
SOURCES = (
    ROOT / 'src' / 'creative' / 'ports' / 'repositories.py',
    ROOT / 'src' / 'creative' / 'adapters' / 'memory.py',
)


def _ref(ref_id: str = 'a1') -> ResourceRef:
    return ResourceRef(workspace_id='ws-1', ref_type='article', ref_id=ref_id, revision_id='r1')


def _snapshot(snapshot_id: str = 'snap-1', ref_id: str = 'a1') -> object:
    return build_production_snapshot(
        snapshot_id=snapshot_id,
        production_mode='single_article',
        source_refs=[{'ref_type': 'article', 'ref_id': ref_id, 'revision_id': 'r1'}],
        index_revision_refs=[],
        configuration_revision_refs=[{'ref_type': 'config', 'ref_id': 'c1', 'revision_id': 'r1'}],
        content_ref_types=['article'],
        eligibility_reason='eligible',
        snapshot_timestamp='2026-10-19T00:00:00Z',
    )


def _analysis(analysis_id: str = 'analysis-1', revision: int = 1) -> ContentAnalysis:
    return ContentAnalysis(
        analysis_id=analysis_id,
        revision=revision,
        snapshot_id='snap-1',
        source_set_fingerprint='a' * 64,
        configuration_bundle_fingerprint='b' * 64,
        source_refs=(),
        topic='topic',
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
        trace=AnalysisTrace('p', 'm', _ref('prompt-1'), 'policy-1'),
    )


def _angle_set(set_id: str = 'set-1') -> StoryAngleSet:
    return StoryAngleSet(
        set_id=set_id,
        analysis_id='analysis-1',
        analysis_revision=1,
        requested_count=1,
        generation='initial',
        variation_policy_revision='vp-1',
        angles=(
            StoryAngle(
                angle_id='angle-1',
                title='T',
                summary='S',
                narrative_question='Q?',
                focus_entities=('city',),
                timeframe='2026',
                evidence_refs=(_ref(),),
                planned_inference_elements=(),
                planned_creative_elements=(),
                suitability='high',
                risk_flags=(),
            ),
        ),
        excluded=(),
    )


def _script(script_version_id: str = 'script-1', text: str = 'hello world') -> ScriptVersion:
    return ScriptVersion(
        script_version_id=script_version_id,
        language='en',
        hook_intent='hook',
        thumbnail_transition='cut',
        segments=(
            ScriptSegment(
                segment_id='s1',
                order=0,
                text=text,
                claim_mode='transition',
                scene_intent='intro',
                source_refs=(),
                disclosure=None,
                word_count=2,
                estimated_seconds=1.0,
            ),
        ),
        pronunciation_hints=(),
        speech_rate=2.0,
        estimated_duration_seconds=1.0,
    )


def _plan(production_plan_id: str = 'plan-1', fingerprint: str = 'c' * 64) -> ProductionPlan:
    return ProductionPlan(
        production_plan_id=production_plan_id,
        script_version_id='script-1',
        script_fingerprint='a' * 64,
        preset_revision_ref='preset-1',
        selection_fingerprint='b' * 64,
        timeline={},
        hook_placement={},
        thumbnail_overlay_intent='overlay',
        voice_profile_intent={},
        music_cues=(),
        sfx_cues=(),
        subtitle_style_intent={},
        allowed_fallbacks=(),
        output_metadata_ref=None,
        output_metadata_requirement='required',
        plan_fingerprint=fingerprint,
    )


def _validation(registry_revision: int = 3, valid: bool = True) -> VariantValidationResult:
    return VariantValidationResult(
        valid=valid,
        same_run_angle_distinct=True,
        exact_duplicate=False,
        distinct_factors=('voice',),
        nearest_prior_refs=(),
        reason_codes=('variant_distinct',),
        input_hashes={'candidate': 'a' * 64},
        registry_revision=registry_revision,
        phase='plan',
        variation_policy_revision='vp-1',
        own_reservation_id=None,
        output_hash=None,
    )


def _metadata(source_job_ref: str = 'job-1', revision: int = 1) -> OutputMetadata:
    return OutputMetadata(
        title='Title',
        caption='Caption',
        hashtags=('#one', '#two', '#three'),
        language='en',
        source_job_ref=source_job_ref,
        source_output_refs=('vv-1',),
        metadata_revision=revision,
    )


def _invocation(attempt: int = 1) -> AIInvocationRecord:
    return AIInvocationRecord(
        ai_role='analyst',
        provider_ref='p',
        model_ref='m',
        account_ref='a',
        route_revision='r1',
        prompt_revision='pr1',
        config_revision='c1',
        input_fingerprint='a' * 64,
        usage=InvocationUsage(1, 1, 'low'),
        latency_ms=5,
        attempt=attempt,
        fallback_path=('p',),
        validation_result='passed',
        output_fingerprint='b' * 64,
    )


def _receipt(key: str = 'k-1', workspace_id: str = 'ws-1') -> repositories.CommandReceipt:
    return repositories.CommandReceipt(
        workspace_id=workspace_id,
        idempotency_key=key,
        request_hash='a' * 64,
        aggregate_ref='snap-1',
        aggregate_revision=1,
    )


def _uow() -> memory.InMemoryUnitOfWork:
    return memory.InMemoryUnitOfWork()


APPEND_CASES = {
    'analyses': ('analysis-1', lambda n: _analysis('analysis-1', n)),
    'angle_sets': ('k-1', lambda n: _angle_set(f'set-{n}')),
    'scripts': ('k-1', lambda n: _script(f'script-{n}', f'hello world {n}')),
    'plans': ('k-1', lambda n: _plan(f'plan-{n}')),
    'variant_validations': ('k-1', lambda n: _validation(n)),
    'output_metadata': ('job-1', lambda n: _metadata('job-1', n)),
    'invocations': ('k-1', lambda n: _invocation(n)),
}


def test_snapshot_id_is_unique():
    uow = _uow()
    s1 = _snapshot('snap-1', 'a1')
    with uow:
        uow.snapshots.add(s1)
        uow.commit()

    with uow:
        with pytest.raises(repositories.DuplicateSnapshotError):
            uow.snapshots.add(_snapshot('snap-1', 'a2'))
        with pytest.raises(repositories.DuplicateSnapshotError):
            uow.snapshots.add(s1)

    assert uow.snapshots.get('snap-1').source_refs[0]['ref_id'] == 'a1'
    assert len(uow.snapshots.list_snapshots()) == 1
    assert uow.snapshots.get('nope') is None


def test_snapshot_add_validates_type_and_transaction():
    uow = _uow()
    with uow:
        with pytest.raises(TypeError):
            uow.snapshots.add(object())
    with pytest.raises(memory.TransactionNotActiveError):
        uow.snapshots.add(_snapshot())
    assert uow.snapshots.list_snapshots() == ()


@pytest.mark.parametrize('attr', list(APPEND_CASES))
def test_append_only_keeps_every_revision(attr: str):
    uow = _uow()
    key, make = APPEND_CASES[attr]
    r1, r2 = make(1), make(2)
    with uow:
        repo = getattr(uow, attr)
        s1 = repo.append(key, 1, r1)
        repo.append(key, 2, r2)
        uow.commit()

    assert repo.latest(key).revision == 2
    assert repo.latest(key).record is r2
    revs = repo.revisions(key)
    assert len(revs) == 2
    assert revs[0] is s1
    assert revs[0].record is r1
    assert [s.revision for s in revs] == [1, 2]
    assert isinstance(s1, repositories.StoredRecord)
    assert s1.kind == repo.kind
    assert repo.latest('khong-co') is None
    assert repo.revisions('khong-co') == ()


def test_new_script_revision_never_overwrites_old():
    uow = _uow()
    with uow:
        uow.scripts.append('job-1', 1, _script('script-1', 'one two'))
        uow.commit()

    with uow:
        with pytest.raises(RevisionConflictError) as exc_info:
            uow.scripts.append('job-1', 1, _script('script-2', 'three four'))
        assert exc_info.value.current_revision == 1

        with pytest.raises(RevisionConflictError) as exc_info:
            uow.scripts.append('job-1', 3, _script('script-3', 'five six'))
        assert exc_info.value.current_revision == 1

        with pytest.raises(RevisionConflictError) as exc_info:
            uow.scripts.append('job-moi', 2, _script('script-4', 'seven eight'))
        assert exc_info.value.current_revision == 0

    assert uow.scripts.latest('job-1').record.script_version_id == 'script-1'
    assert len(uow.scripts.revisions('job-1')) == 1


@pytest.mark.parametrize(
    'attr, make',
    [
        ('angle_sets', lambda n: _angle_set(f'set-{n}')),
        ('scripts', lambda n: _script(f'script-{n}')),
        ('plans', lambda n: _plan(f'plan-{n}')),
    ],
)
def test_record_id_is_unique_across_keys(attr, make):
    uow = _uow()
    with uow:
        repo = getattr(uow, attr)
        repo.append('k-1', 1, make(1))
        uow.commit()

    with uow:
        repo = getattr(uow, attr)
        with pytest.raises(repositories.DuplicateRecordError):
            repo.append('k-2', 1, make(1))
        with pytest.raises(repositories.DuplicateRecordError):
            repo.append('k-1', 2, make(1))
        repo.append('k-1', 2, make(2))

    assert repo.revisions('k-2') == ()


def test_identity_must_match_key_and_revision():
    uow = _uow()
    with uow:
        with pytest.raises(ValueError):
            uow.analyses.append('analysis-2', 1, _analysis('analysis-1', 1))
        with pytest.raises(ValueError):
            uow.analyses.append('analysis-1', 2, _analysis('analysis-1', 1))
        with pytest.raises(ValueError):
            uow.output_metadata.append('job-2', 1, _metadata('job-1', 1))
        with pytest.raises(ValueError):
            uow.output_metadata.append('job-1', 2, _metadata('job-1', 1))
    assert uow.analyses.revisions('analysis-1') == ()


def test_argument_validation():
    uow = _uow()
    with uow:
        with pytest.raises(TypeError):
            uow.scripts.append('k', 1, object())
        with pytest.raises(TypeError):
            uow.scripts.append('k', 1, _plan())
        for bad_rev in (0, '1', True, None, -1):
            with pytest.raises(ValueError):
                uow.scripts.append('k', bad_rev, _script())
        for bad_key in ('', ' ', None):
            with pytest.raises(ValueError):
                uow.scripts.append(bad_key, 1, _script())

    with pytest.raises(memory.TransactionNotActiveError):
        uow.scripts.append('k', 1, _script())
    assert uow.scripts.latest('k') is None


def test_receipt_store_is_append_only():
    uow = _uow()
    with uow:
        uow.receipts.put(_receipt('k-1'))
        with pytest.raises(repositories.DuplicateReceiptError):
            uow.receipts.put(_receipt('k-1'))
        uow.receipts.put(_receipt('k-1', 'ws-2'))
        uow.commit()

    assert uow.receipts.get('ws-1', 'k-1') == _receipt('k-1')
    assert uow.receipts.get('ws-1', 'khong-co') is None

    with uow:
        with pytest.raises(TypeError):
            uow.receipts.put(object())

    with pytest.raises(memory.TransactionNotActiveError):
        uow.receipts.put(_receipt('k-9'))


def test_command_receipt_validates_fields():
    valid = {
        'workspace_id': 'ws-1',
        'idempotency_key': 'k',
        'request_hash': 'a' * 64,
        'aggregate_ref': 'snap-1',
        'aggregate_revision': 1,
    }
    for field in ('workspace_id', 'idempotency_key', 'request_hash', 'aggregate_ref'):
        for bad in ('', ' ', None):
            d = dict(valid)
            d[field] = bad
            with pytest.raises(ValueError):
                repositories.CommandReceipt(**d)

    for bad_rev in (0, -1, True, '1', 1.0):
        d = dict(valid)
        d['aggregate_revision'] = bad_rev
        with pytest.raises(ValueError):
            repositories.CommandReceipt(**d)

    r = repositories.CommandReceipt(**valid)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.aggregate_ref = 'x'


def test_repositories_have_no_overwrite_or_delete_api():
    uow = _uow()
    for repo in (
        uow.snapshots,
        uow.analyses,
        uow.angle_sets,
        uow.scripts,
        uow.plans,
        uow.variant_validations,
        uow.output_metadata,
        uow.invocations,
    ):
        for name in ('delete', 'remove', 'save', 'update', 'overwrite', 'put', 'clear', 'pop', 'replace'):
            assert not hasattr(repo, name)

    for name in ('delete', 'remove', 'save', 'update', 'overwrite', 'clear', 'pop', 'replace'):
        assert not hasattr(uow.receipts, name)


def test_repositories_satisfy_protocols():
    uow = _uow()
    assert isinstance(uow.snapshots, repositories.SnapshotRepository)
    assert isinstance(uow.analyses, repositories.AnalysisRepository)
    assert isinstance(uow.angle_sets, repositories.AngleSetRepository)
    assert isinstance(uow.scripts, repositories.ScriptRepository)
    assert isinstance(uow.plans, repositories.PlanRepository)
    assert isinstance(uow.variant_validations, repositories.VariantValidationRepository)
    assert isinstance(uow.output_metadata, repositories.OutputMetadataRepository)
    assert isinstance(uow.invocations, repositories.InvocationRecordRepository)

    for repo in (
        uow.analyses,
        uow.angle_sets,
        uow.scripts,
        uow.plans,
        uow.variant_validations,
        uow.output_metadata,
        uow.invocations,
    ):
        assert isinstance(repo, repositories.AppendOnlyRepository)

    assert isinstance(uow.receipts, repositories.ReceiptStore)


def test_stored_record_is_frozen():
    s = repositories.StoredRecord('script', 'k', 1, 'rec')
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.revision = 9


def test_record_types_cover_every_kind():
    assert set(repositories.RECORD_TYPES) == {
        repositories.KIND_ANALYSIS,
        repositories.KIND_ANGLE_SET,
        repositories.KIND_SCRIPT,
        repositories.KIND_PLAN,
        repositories.KIND_VARIANT_VALIDATION,
        repositories.KIND_OUTPUT_METADATA,
        repositories.KIND_INVOCATION,
    }
    with pytest.raises(ValueError):
        memory.InMemoryAppendOnlyRepository(_uow(), 'khong-ton-tai')


def _append_event(uow, dedup='d-1', payload=None):
    return uow.outbox.append_event(
        'ScriptVersionCreated',
        'script-1',
        payload or {'script_version_id': 'script-1'},
        dedup,
    )


def test_uow_and_outbox_implement_controlplane_interfaces():
    assert issubclass(memory.InMemoryUnitOfWork, IUnitOfWork)
    uow = _uow()
    assert isinstance(uow, IUnitOfWork)
    assert isinstance(uow.outbox, IOutboxWriter)
    assert issubclass(memory.InMemoryOutboxWriter, IOutboxWriter)


def test_commit_persists_records_receipts_and_outbox():
    uow = _uow()
    with uow:
        uow.snapshots.add(_snapshot())
        uow.scripts.append('job-1', 1, _script())
        uow.receipts.put(_receipt())
        _append_event(uow)
        uow.commit()

    assert uow.active is False
    assert uow.snapshots.get('snap-1') is not None
    assert uow.scripts.latest('job-1') is not None
    assert uow.receipts.get('ws-1', 'k-1') is not None
    assert len(uow.outbox.records()) == 1


def test_exit_without_commit_rolls_back_everything():
    uow = _uow()
    with uow:
        uow.snapshots.add(_snapshot())
        uow.scripts.append('job-1', 1, _script())
        uow.receipts.put(_receipt())
        _append_event(uow)

    assert uow.snapshots.get('snap-1') is None
    assert uow.scripts.latest('job-1') is None
    assert uow.receipts.get('ws-1', 'k-1') is None
    assert uow.outbox.records() == ()
    assert uow.active is False


def test_exception_in_block_rolls_back_everything_including_outbox():
    uow = _uow()
    with pytest.raises(RuntimeError):
        with uow:
            uow.snapshots.add(_snapshot())
            uow.scripts.append('job-1', 1, _script())
            _append_event(uow)
            raise RuntimeError('boom')

    assert uow.snapshots.list_snapshots() == ()
    assert uow.scripts.revisions('job-1') == ()
    assert uow.outbox.records() == ()


def test_explicit_rollback_keeps_committed_revision_only():
    uow = _uow()
    with uow:
        uow.scripts.append('job-1', 1, _script('script-1'))
        _append_event(uow, 'd-1')
        uow.commit()

    with uow:
        uow.scripts.append('job-1', 2, _script('script-2'))
        _append_event(uow, 'd-2')
        uow.rollback()

    assert len(uow.scripts.revisions('job-1')) == 1
    assert uow.scripts.latest('job-1').record.script_version_id == 'script-1'
    assert len(uow.outbox.records()) == 1
    assert uow.outbox.records()[0].deduplication_id == 'd-1'


def test_rollback_restores_snapshot_id_uniqueness_slot():
    uow = _uow()
    with uow:
        uow.snapshots.add(_snapshot('snap-1'))
        uow.rollback()

    with uow:
        uow.snapshots.add(_snapshot('snap-1'))
        uow.commit()

    assert uow.snapshots.get('snap-1') is not None


def test_begin_twice_and_finish_without_begin():
    uow = _uow()
    uow.begin()
    with pytest.raises(memory.TransactionAlreadyActiveError):
        uow.begin()
    uow.rollback()

    with pytest.raises(memory.TransactionNotActiveError):
        uow.commit()
    with pytest.raises(memory.TransactionNotActiveError):
        uow.rollback()


def test_outbox_dedups_by_deduplication_id():
    uow = _uow()
    with uow:
        e1 = _append_event(uow, 'd-1', {'script_version_id': 'script-1'})
        e2 = _append_event(uow, 'd-1', {'script_version_id': 'script-ignored'})
        assert e1 == e2
        assert len(uow.outbox.records()) == 1
        assert uow.outbox.records()[0].payload['script_version_id'] == 'script-1'
        e3 = _append_event(uow, 'd-2')
        assert e3 != e1
        assert len(uow.outbox.records()) == 2
        uow.commit()

    with uow:
        e4 = _append_event(uow, 'd-1', {'script_version_id': 'script-ignored-2'})
        assert e4 == e1
        assert len(uow.outbox.records()) == 2
        uow.commit()


def test_outbox_rejects_unsafe_blank_or_non_mapping_input():
    uow = _uow()
    with uow:
        for bad_payload in ({'audio': b'RIFF'}, {'note': 'token=abc'}, [1, 2], 'text'):
            with pytest.raises(ValueError):
                uow.outbox.append_event('ScriptVersionCreated', 's-1', bad_payload, 'd-1')

        for bad in ('', ' '):
            with pytest.raises(ValueError):
                uow.outbox.append_event(bad, 's-1', {'k': 'v'}, 'd-1')
            with pytest.raises(ValueError):
                uow.outbox.append_event('ScriptVersionCreated', bad, {'k': 'v'}, 'd-1')
            with pytest.raises(ValueError):
                uow.outbox.append_event('ScriptVersionCreated', 's-1', {'k': 'v'}, bad)

    assert uow.outbox.records() == ()
    with pytest.raises(memory.TransactionNotActiveError):
        uow.outbox.append_event('ScriptVersionCreated', 's-1', {'k': 'v'}, 'd-1')


def test_outbox_record_is_read_only_deep_copy():
    uow = _uow()
    lst = ['a']
    with uow:
        uow.outbox.append_event('ScriptVersionCreated', 's-1', {'refs': lst}, 'd-1')
        lst.append('b')
        rec = uow.outbox.records()[0]
        assert list(rec.payload['refs']) == ['a']
        with pytest.raises(TypeError):
            rec.payload['x'] = 1
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.event_id = 'o'


def _context(**over):
    base = {
        'workspace_id': 'ws-1',
        'correlation_id': 'corr-1',
        'actor': 'worker-d',
        'occurred_at': '2026-10-19T00:00:00Z',
        'recovery_epoch': 'epoch-0001',
        'event_id': 'evt-1',
        'message_id': 'msg-1',
    }
    base.update(over)
    return repositories.EventContext(**base)


CASES = {
    'ProductionSnapshotCommitted': {
        'builder': repositories.build_production_snapshot_committed,
        'kw': 'snapshot',
        'make': lambda: _snapshot('snap-1'),
        'expected': lambda r: {
            'snapshot_id': r.snapshot_id,
            'source_set_fingerprint': r.source_set_fingerprint,
            'configuration_bundle_fingerprint': r.configuration_bundle_fingerprint,
        },
        'aggregate_id': 'snap-1',
    },
    'StoryAnglesGenerated': {
        'builder': repositories.build_story_angles_generated,
        'kw': 'angle_set',
        'make': lambda: _angle_set('set-1'),
        'expected': lambda r: {
            'set_id': r.set_id,
            'analysis_id': r.analysis_id,
            'analysis_revision': r.analysis_revision,
            'angle_ids': [a.angle_id for a in r.angles],
            'variation_policy_revision': r.variation_policy_revision,
        },
        'aggregate_id': 'set-1',
    },
    'ScriptVersionCreated': {
        'builder': repositories.build_script_version_created,
        'kw': 'script',
        'make': lambda: _script('script-1'),
        'expected': lambda r: {
            'script_version_id': r.script_version_id,
            'script_fingerprint': r.script_fingerprint,
        },
        'aggregate_id': 'script-1',
    },
    'ProductionPlanCreated': {
        'builder': repositories.build_production_plan_created,
        'kw': 'plan',
        'make': lambda: _plan('plan-1'),
        'expected': lambda r: {
            'production_plan_id': r.production_plan_id,
            'script_version_id': r.script_version_id,
            'plan_fingerprint': r.plan_fingerprint,
            'selection_fingerprint': r.selection_fingerprint,
        },
        'aggregate_id': 'plan-1',
    },
    'VariantValidated': {
        'builder': repositories.build_variant_validated,
        'kw': 'result',
        'make': lambda: _validation(3),
        'expected': lambda r: {
            'validation_hash': r.validation_hash,
            'registry_revision': r.registry_revision,
            'phase': r.phase,
            'variation_policy_revision': r.variation_policy_revision,
        },
        'aggregate_id': 'vv-1',
    },
    'OutputMetadataCreated': {
        'builder': repositories.build_output_metadata_created,
        'kw': 'metadata',
        'make': lambda: _metadata('job-1', 2),
        'expected': lambda r: {
            'source_job_ref': r.source_job_ref,
            'metadata_revision': r.metadata_revision,
            'source_output_refs': list(r.source_output_refs),
        },
        'aggregate_id': 'job-1',
    },
}


def _build(name: str, **over):
    case = CASES[name]
    record = over.pop('record', None)
    if record is None:
        record = case['make']()
    context = over.pop('context', _context())
    aggregate_id = over.pop('aggregate_id', case['aggregate_id'])
    aggregate_revision = over.pop('aggregate_revision', 3)
    event = case['builder'](
        context,
        aggregate_id=aggregate_id,
        aggregate_revision=aggregate_revision,
        **{case['kw']: record},
    )
    return event, record


@pytest.mark.parametrize('name', list(CASES))
def test_builder_returns_controlplane_domain_event(name: str):
    event, record = _build(name)
    assert type(event) is contracts.DomainEvent
    assert repositories.DomainEvent is contracts.DomainEvent
    assert event.event_name == name
    assert event.aggregate_type == repositories.EVENT_AGGREGATE_TYPES[name]
    assert event.producer == 'D'
    assert event.schema_version == '1.0.0'
    assert event.sensitivity == 'internal'
    assert event.contract_name == 'creative.events'
    assert event.contract_version == 1
    assert event.recovery_epoch == 'epoch-0001'
    assert event.aggregate_revision == 3
    assert event.event_id == 'evt-1'
    assert event.message_id == 'msg-1'
    assert event.workspace_id == 'ws-1'
    assert event.payload == CASES[name]['expected'](record)
    json.dumps(event.payload)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.event_name = 'X'


@pytest.mark.parametrize('name', list(CASES))
def test_payload_carries_only_refs_revisions_and_fingerprints(name: str):
    event, _ = _build(name)
    forbidden_keys = {'title', 'caption', 'hashtags', 'text', 'prompt', 'narration', 'segments', 'timeline', 'body'}
    assert not (forbidden_keys & set(event.payload.keys()))
    for k, v in event.payload.items():
        if isinstance(v, list):
            assert all(isinstance(x, str) and len(x) <= repositories.MAX_VALUE_LENGTH for x in v)
        elif isinstance(v, str):
            assert len(v) <= repositories.MAX_VALUE_LENGTH
        elif isinstance(v, int) and not isinstance(v, bool):
            pass
        else:
            pytest.fail(f'Unexpected type for payload value {k}: {type(v)}')


@pytest.mark.parametrize('name', list(CASES))
def test_wrong_record_type_is_rejected(name: str):
    case = CASES[name]
    with pytest.raises(TypeError):
        case['builder'](_context(), aggregate_id='x', aggregate_revision=1, **{case['kw']: object()})


def test_variant_not_valid_is_rejected():
    with pytest.raises(ValueError):
        _build('VariantValidated', record=_validation(3, valid=False))


def test_plan_without_fingerprint_is_rejected():
    with pytest.raises(ValueError):
        _build('ProductionPlanCreated', record=_plan('plan-1', fingerprint=''))


def test_secret_or_trace_value_is_rejected_by_contract_guard():
    with pytest.raises(ValueError, match='unsafe domain event payload'):
        _build('ScriptVersionCreated', record=_script('token=abc'))
    with pytest.raises(ValueError, match='unsafe domain event payload'):
        _build('ScriptVersionCreated', record=_script('traceback'))


def test_builder_calls_contract_payload_guard(monkeypatch):
    called = []

    def spy(payload):
        called.append(copy.deepcopy(payload))
        return contracts.ensure_safe_event_payload(payload)

    monkeypatch.setattr(repositories, 'ensure_safe_event_payload', spy)
    event, record = _build('ScriptVersionCreated')
    assert len(called) >= 1
    assert called[0] == CASES['ScriptVersionCreated']['expected'](record)


def test_invalid_context_and_revision_are_rejected():
    with pytest.raises(repositories.EventEnvelopeError) as exc_info:
        _build('ScriptVersionCreated', context=_context(recovery_epoch=None))
    assert ('wrong_type', 'recovery_epoch') in exc_info.value.issues

    with pytest.raises(repositories.EventEnvelopeError) as exc_info:
        _build('ScriptVersionCreated', context=_context(recovery_epoch=''))
    assert ('constraint_violation', 'recovery_epoch') in exc_info.value.issues

    with pytest.raises(repositories.EventEnvelopeError) as exc_info:
        _build('ScriptVersionCreated', context=_context(event_id=''))
    assert ('constraint_violation', 'event_id') in exc_info.value.issues

    for bad_rev in ('3', True, 0, -1, None):
        with pytest.raises(repositories.EventEnvelopeError):
            _build('ScriptVersionCreated', aggregate_revision=bad_rev)

    for bad_ctx in (
        {'workspace_id': ' '},
        {'actor': ''},
        {'message_id': ''},
        {'correlation_id': ''},
        {'occurred_at': 'không-phải-ngày'},
        {'causation_id': ''},
    ):
        with pytest.raises(ValueError):
            _context(**bad_ctx)

    assert _context(causation_id=None).causation_id is None


def test_deduplication_id_for_is_stable():
    e3, _ = _build('ScriptVersionCreated', aggregate_revision=3)
    e4, _ = _build('ScriptVersionCreated', aggregate_revision=4)
    assert repositories.deduplication_id_for(e3) == 'ws-1:ScriptVersionCreated:script-1:3'
    assert repositories.deduplication_id_for(e4) == 'ws-1:ScriptVersionCreated:script-1:4'
    assert repositories.deduplication_id_for(e3) != repositories.deduplication_id_for(e4)
    with pytest.raises(TypeError):
        repositories.deduplication_id_for(object())


def test_event_flows_through_outbox_inside_uow():
    event = _build('ScriptVersionCreated')[0]
    uow = _uow()
    with uow:
        uow.outbox.append_event(
            event.event_name,
            event.aggregate_id,
            dataclasses.asdict(event),
            repositories.deduplication_id_for(event),
        )
    assert uow.outbox.records() == ()

    with uow:
        uow.outbox.append_event(
            event.event_name,
            event.aggregate_id,
            dataclasses.asdict(event),
            repositories.deduplication_id_for(event),
        )
        uow.commit()

    assert len(uow.outbox.records()) == 1
    assert uow.outbox.records()[0].payload['payload']['script_fingerprint'] == event.payload['script_fingerprint']
    assert uow.outbox.records()[0].payload['producer'] == 'D'

    with uow:
        uow.outbox.append_event(
            event.event_name,
            event.aggregate_id,
            dataclasses.asdict(event),
            repositories.deduplication_id_for(event),
        )
        uow.commit()

    assert len(uow.outbox.records()) == 1


def test_fixture_valid_envelope_has_no_issues():
    fixture = json.loads(ENVELOPE_FIXTURE.read_text(encoding='utf-8'))
    valid = fixture['entities']['DomainEvent']['valid'][0]
    assert repositories.envelope_issues(valid) == ()


def _load_invalid_cases():
    fixture = json.loads(ENVELOPE_FIXTURE.read_text(encoding='utf-8'))
    return fixture['entities']['DomainEvent']['invalid']


@pytest.mark.parametrize('case', _load_invalid_cases(), ids=[c['case'] for c in _load_invalid_cases()])
def test_fixture_invalid_envelopes(case):
    invalid_cases = _load_invalid_cases()
    assert {c['case'] for c in invalid_cases} == {
        'producer_outside_modules',
        'aggregate_revision_as_string',
        'stack_trace_in_event',
        'missing_recovery_epoch',
    }
    expected = case['expected_error']
    assert repositories.envelope_issues(case['payload']) == ((expected['code'], expected['field']),)


def test_builder_envelopes_are_valid_for_all_events():
    for name in CASES:
        event = _build(name)[0]
        envelope = {n: getattr(event, n) for n in repositories.ENVELOPE_FIELDS}
        assert repositories.envelope_issues(envelope) == ()
        assert repositories.envelope_issues(dataclasses.asdict(event)) == ()


def test_constants_match_binding():
    binding = json.loads(BINDING.read_text(encoding='utf-8'))
    entity = next(e for e in binding['entities'] if e['name'] == 'DomainEvent')
    assert {f['name']: f['type'] for f in entity['fields']} == dict(repositories.ENVELOPE_FIELDS)
    assert next(f['enum'] for f in entity['fields'] if f['name'] == 'producer') == list(repositories.MODULE_IDS)
    assert set(entity['forbidden_fields']) == repositories.FORBIDDEN_ENVELOPE_FIELDS


def test_envelope_issues_edge_cases():
    assert repositories.envelope_issues([]) == (('wrong_type', '$'),)
    fixture = json.loads(ENVELOPE_FIXTURE.read_text(encoding='utf-8'))
    valid = fixture['entities']['DomainEvent']['valid'][0]

    bad_blob = copy.deepcopy(valid)
    bad_blob['payload'] = {'a': {'blob': 'x'}}
    assert ('forbidden_field', 'blob') in repositories.envelope_issues(bad_blob)

    bad_bytes = copy.deepcopy(valid)
    bad_bytes['payload'] = {'bytes_field': b'x'}
    assert ('forbidden_field', 'payload') in repositories.envelope_issues(bad_bytes)

    bad_rev_bool = copy.deepcopy(valid)
    bad_rev_bool['aggregate_revision'] = True
    assert ('wrong_type', 'aggregate_revision') in repositories.envelope_issues(bad_rev_bool)

    bad_rev_zero = copy.deepcopy(valid)
    bad_rev_zero['aggregate_revision'] = 0
    assert ('constraint_violation', 'aggregate_revision') in repositories.envelope_issues(bad_rev_zero)

    bad_eid = copy.deepcopy(valid)
    bad_eid['event_id'] = ' '
    assert ('constraint_violation', 'event_id') in repositories.envelope_issues(bad_eid)

    bad_prod = copy.deepcopy(valid)
    bad_prod['producer'] = 'd'
    assert ('enum_violation', 'producer') in repositories.envelope_issues(bad_prod)

    bad_prod_int = copy.deepcopy(valid)
    bad_prod_int['producer'] = 5
    assert ('wrong_type', 'producer') in repositories.envelope_issues(bad_prod_int)


def test_sources_reuse_controlplane_types_and_respect_boundaries():
    for src_path in SOURCES:
        tree = ast.parse(src_path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in {'IUnitOfWork', 'IOutboxWriter', 'DomainEvent'}
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split('.')[0]
                    assert not alias.name.startswith('src.')
                    assert root not in {
                        'os',
                        'socket',
                        'subprocess',
                        'time',
                        'random',
                        'uuid',
                        'requests',
                        'urllib',
                        'http',
                        'psycopg',
                        'source_ingestion',
                        'ingestion',
                        'catalog',
                        'voice',
                        'render',
                    }
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split('.')[0]
                    assert not node.module.startswith('src.')
                    assert root not in {
                        'os',
                        'socket',
                        'subprocess',
                        'time',
                        'random',
                        'uuid',
                        'requests',
                        'urllib',
                        'http',
                        'psycopg',
                        'source_ingestion',
                        'ingestion',
                        'catalog',
                        'voice',
                        'render',
                    }

    mem_tree = ast.parse(SOURCES[1].read_text(encoding='utf-8'))
    mem_imports: dict[str, list[str]] = {}
    for node in ast.walk(mem_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mem_imports.setdefault(node.module, []).extend(a.name for a in node.names)
    assert 'IUnitOfWork' in mem_imports.get('controlplane.domain.interfaces.uow', [])
    assert 'IOutboxWriter' in mem_imports.get('controlplane.domain.interfaces.outbox', [])
    assert 'RevisionConflictError' in mem_imports.get('controlplane.domain.concurrency', [])

    repo_tree = ast.parse(SOURCES[0].read_text(encoding='utf-8'))
    repo_imports: dict[str, list[str]] = {}
    for node in ast.walk(repo_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            repo_imports.setdefault(node.module, []).extend(a.name for a in node.names)
    assert 'DomainEvent' in repo_imports.get('controlplane.domain.events.contracts', [])
    assert 'ensure_safe_event_payload' in repo_imports.get('controlplane.domain.events.contracts', [])

    assert IUnitOfWork in memory.InMemoryUnitOfWork.__mro__
    assert IOutboxWriter in memory.InMemoryOutboxWriter.__mro__
