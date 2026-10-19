"""E-15: OutputRepository append-only, UoW in-memory, outbox và event của E (CT-EVT-002, CT-EVT-003).

coveredIds: CT-EVT-002, CT-EVT-003 (phía E), TST-INT-INV-008 (phía E)
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
from voice.adapters import memory
from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import validate_word_timing
from voice.ports import repositories

ROOT = pathlib.Path(__file__).resolve().parents[3]
ENVELOPE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'domain-event-envelope' / 'payloads.json'
BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'domain-event-envelope.json'
VOICE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
SOURCES = (
    ROOT / 'src' / 'voice' / 'ports' / 'repositories.py',
    ROOT / 'src' / 'voice' / 'adapters' / 'memory.py',
)


def _fixture(entity: str) -> dict:
    data = json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))
    return data['entities'][entity]['valid'][0]


def _voice(char: str = 'a', ref: str = 'voice-1') -> VoiceTrack:
    return VoiceTrack.from_payload({
        **_fixture('VoiceTrackResult'),
        'voice_hash': char * 64,
        'voice_artifact_ref': ref,
    })


def _timing(ref: str = 'timing-1'):
    raw = validate_word_timing(_fixture('WordTiming'))
    return dataclasses.replace(raw, timing_artifact_ref=ref)


def _uow() -> memory.InMemoryUnitOfWork:
    return memory.InMemoryUnitOfWork()


# ---------------------------------------------------------------------------
# Phần 1: OutputRepository append-only
# ---------------------------------------------------------------------------


def test_append_latest_and_revisions():
    uow = _uow()
    v1 = _voice('a', 'voice-1')
    v2 = _voice('b', 'voice-2')
    with uow:
        uow.outputs.append('voice', 'video-1', 1, v1)
        uow.outputs.append('voice', 'video-1', 2, v2)
        uow.commit()
    latest_item = uow.outputs.latest('voice', 'video-1')
    assert latest_item is not None
    assert latest_item.revision == 2
    assert latest_item.record is v2
    revs = uow.outputs.revisions('voice', 'video-1')
    assert len(revs) == 2
    assert revs[0].revision == 1
    assert revs[0].record is v1
    assert revs[1].revision == 2
    assert revs[1].record is v2
    assert uow.outputs.latest('voice', 'non-existent') is None
    assert uow.outputs.revisions('voice', 'non-existent') == ()


def test_same_or_skipped_revision_is_rejected_and_keeps_old():
    uow = _uow()
    v1 = _voice('a', 'voice-1')
    v2 = _voice('b', 'voice-2')
    v3 = _voice('c', 'voice-3')
    with uow:
        uow.outputs.append('voice', 'video-1', 1, v1)
        uow.commit()

    with uow:
        with pytest.raises(RevisionConflictError) as exc_info1:
            uow.outputs.append('voice', 'video-1', 1, v2)
        assert exc_info1.value.current_revision == 1

        with pytest.raises(RevisionConflictError) as exc_info2:
            uow.outputs.append('voice', 'video-1', 3, v3)
        assert exc_info2.value.current_revision == 1

        with pytest.raises(RevisionConflictError) as exc_info3:
            uow.outputs.append('voice', 'video-new', 2, v2)
        assert exc_info3.value.current_revision == 0

    assert uow.outputs.latest('voice', 'video-1').record is v1
    assert len(uow.outputs.revisions('voice', 'video-1')) == 1


def test_duplicate_voice_hash_is_rejected():
    uow = _uow()
    v1 = _voice('a', 'voice-1')
    v2 = _voice('a', 'voice-2')
    with uow:
        uow.outputs.append('voice', 'video-1', 1, v1)
        uow.commit()

    with uow:
        with pytest.raises(repositories.DuplicateOutputError):
            uow.outputs.append('voice', 'video-2', 1, v2)
        with pytest.raises(repositories.DuplicateOutputError):
            uow.outputs.append('voice', 'video-1', 2, v2)

    assert uow.outputs.revisions('voice', 'video-2') == ()


def test_duplicate_timing_artifact_ref_is_rejected():
    uow = _uow()
    t1 = _timing('timing-1')
    t2 = _timing('timing-1')
    with uow:
        uow.outputs.append('word_timing', 'video-1', 1, t1)
        uow.commit()

    with uow:
        with pytest.raises(repositories.DuplicateOutputError):
            uow.outputs.append('word_timing', 'video-2', 1, t2)
        with pytest.raises(repositories.DuplicateOutputError):
            uow.outputs.append('word_timing', 'video-1', 2, t2)

    assert uow.outputs.revisions('word_timing', 'video-2') == ()


def test_record_type_revision_and_names_are_validated():
    uow = _uow()
    with uow:
        with pytest.raises(TypeError):
            uow.outputs.append('voice', 'k', 1, object())
        with pytest.raises(TypeError):
            uow.outputs.append('word_timing', 'k', 1, _voice())

        for bad_rev in (0, '1', True, None, -1):
            with pytest.raises(ValueError):
                uow.outputs.append('voice', 'k', bad_rev, _voice())

        for bad_val in ('', ' ', None):
            with pytest.raises(ValueError):
                uow.outputs.append(bad_val, 'k', 1, _voice())
            with pytest.raises(ValueError):
                uow.outputs.append('voice', bad_val, 1, _voice())


def test_repository_has_no_overwrite_or_delete_api():
    uow = _uow()
    repo = uow.outputs
    for forbidden_name in ('delete', 'remove', 'save', 'update', 'overwrite', 'put', 'clear', 'pop'):
        assert not hasattr(repo, forbidden_name)
    assert isinstance(repo, repositories.OutputRepository)


def test_write_outside_transaction_is_rejected():
    uow = _uow()
    with pytest.raises(memory.TransactionNotActiveError):
        uow.outputs.append('voice', 'video-1', 1, _voice())
    assert uow.outputs.latest('voice', 'video-1') is None
    assert uow.outputs.revisions('voice', 'video-1') == ()


def test_stored_output_is_frozen():
    stored = repositories.StoredOutput('voice', 'k', 1, 'rec')
    with pytest.raises(dataclasses.FrozenInstanceError):
        stored.revision = 9


# ---------------------------------------------------------------------------
# Phần 2: Unit of Work và Outbox
# ---------------------------------------------------------------------------


def _append_event(uow, dedup='d-1', payload=None):
    return uow.outbox.append_event(
        'VoiceReady',
        'voice-1',
        payload or {'voice_artifact_ref': 'voice-1'},
        dedup,
    )


def test_uow_and_outbox_implement_controlplane_interfaces():
    assert issubclass(memory.InMemoryUnitOfWork, IUnitOfWork)
    uow = _uow()
    assert isinstance(uow, IUnitOfWork)
    assert isinstance(uow.outbox, IOutboxWriter)
    assert isinstance(uow.outputs, repositories.OutputRepository)


def test_commit_persists_outputs_and_outbox():
    uow = _uow()
    with uow:
        uow.outputs.append('voice', 'v-1', 1, _voice())
        _append_event(uow)
        uow.commit()
    assert uow.active is False
    assert uow.outputs.latest('voice', 'v-1') is not None
    assert len(uow.outbox.records()) == 1


def test_exit_without_commit_rolls_back_outputs_and_outbox():
    uow = _uow()
    with uow:
        uow.outputs.append('voice', 'v-1', 1, _voice())
        _append_event(uow)
    assert uow.outputs.latest('voice', 'v-1') is None
    assert uow.outbox.records() == ()
    assert uow.active is False


def test_exception_in_block_rolls_back_everything():
    uow = _uow()
    with pytest.raises(RuntimeError):
        with uow:
            uow.outputs.append('voice', 'v-1', 1, _voice())
            _append_event(uow)
            raise RuntimeError('boom')
    assert uow.outputs.latest('voice', 'v-1') is None
    assert uow.outbox.records() == ()
    assert uow.active is False


def test_explicit_rollback_removes_new_revision_but_keeps_committed():
    uow = _uow()
    with uow:
        uow.outputs.append('voice', 'v-1', 1, _voice('a', 'voice-1'))
        _append_event(uow, dedup='d-1')
        uow.commit()

    with uow:
        uow.outputs.append('voice', 'v-1', 2, _voice('b', 'voice-2'))
        _append_event(uow, dedup='d-2')
        uow.rollback()

    revs = uow.outputs.revisions('voice', 'v-1')
    assert len(revs) == 1
    assert revs[0].revision == 1
    recs = uow.outbox.records()
    assert len(recs) == 1
    assert recs[0].deduplication_id == 'd-1'


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
        e1 = _append_event(uow, dedup='d-1', payload={'voice_artifact_ref': 'voice-1'})
        e2 = _append_event(uow, dedup='d-1', payload={'voice_artifact_ref': 'voice-ignored'})
        assert e1 == e2
        recs = uow.outbox.records()
        assert len(recs) == 1
        assert recs[0].payload['voice_artifact_ref'] == 'voice-1'

        e3 = _append_event(uow, dedup='d-2', payload={'voice_artifact_ref': 'voice-2'})
        assert e3 != e1
        assert len(uow.outbox.records()) == 2
        uow.commit()

    with uow:
        e4 = _append_event(uow, dedup='d-1', payload={'voice_artifact_ref': 'voice-new'})
        assert e4 == e1
        assert len(uow.outbox.records()) == 2
        uow.commit()


def test_outbox_rejects_unsafe_blank_or_non_mapping_input():
    uow = _uow()
    with uow:
        for bad_payload in (
            {'audio': b'RIFF....'},
            {'note': 'token=abc'},
            [1, 2, 3],
            'not-mapping',
        ):
            with pytest.raises(ValueError):
                uow.outbox.append_event('VoiceReady', 'voice-1', bad_payload, 'd-1')

        for bad_str in ('', ' '):
            with pytest.raises(ValueError):
                uow.outbox.append_event(bad_str, 'voice-1', {'k': 'v'}, 'd-1')
            with pytest.raises(ValueError):
                uow.outbox.append_event('VoiceReady', bad_str, {'k': 'v'}, 'd-1')
            with pytest.raises(ValueError):
                uow.outbox.append_event('VoiceReady', 'voice-1', {'k': 'v'}, bad_str)

        assert uow.outbox.records() == ()

    with pytest.raises(memory.TransactionNotActiveError):
        uow.outbox.append_event('VoiceReady', 'voice-1', {'k': 'v'}, 'd-1')


def test_outbox_record_is_read_only_deep_copy():
    uow = _uow()
    source_list = ['a']
    with uow:
        uow.outbox.append_event('VoiceReady', 'voice-1', {'refs': source_list}, 'd-1')
        source_list.append('b')
        recs = uow.outbox.records()
        assert list(recs[0].payload['refs']) == ['a']
        with pytest.raises(TypeError):
            recs[0].payload['x'] = 1
        with pytest.raises(dataclasses.FrozenInstanceError):
            recs[0].event_id = 'other'


# ---------------------------------------------------------------------------
# Phần 3: Event Builders
# ---------------------------------------------------------------------------


def _context(**over):
    base = {
        'workspace_id': 'ws-1',
        'correlation_id': 'corr-1',
        'actor': 'worker-e',
        'occurred_at': '2026-10-19T00:00:00Z',
        'recovery_epoch': 'epoch-0001',
        'event_id': 'evt-1',
        'message_id': 'msg-1',
    }
    base.update(over)
    return repositories.EventContext(**base)


CASES = {
    'ImageSafetyAssessed': {
        'builder': repositories.build_image_safety_assessed,
        'kwargs_payload': {
            'assessment_ref': 'assess-1',
            'artifact_ref': 'img-1',
            'content_sha256': 'c' * 64,
            'policy_revision': 'policy-r1',
        },
        'expected_payload': {
            'assessment_ref': 'assess-1',
            'artifact_ref': 'img-1',
            'content_sha256': 'c' * 64,
            'policy_revision': 'policy-r1',
        },
        'aggregate_id': 'assess-1',
        'needs_verified': False,
    },
    'MediaProcessingCompleted': {
        'builder': repositories.build_media_processing_completed,
        'kwargs_payload': {
            'processing_operation_id': 'op-1',
            'output_artifact_refs': ['out-1', 'out-2'],
            'output_hashes': ['d' * 64, 'e' * 64],
            'operation_receipt_ref': 'rcpt-1',
        },
        'expected_payload': {
            'processing_operation_id': 'op-1',
            'output_artifact_refs': ['out-1', 'out-2'],
            'output_hashes': ['d' * 64, 'e' * 64],
            'operation_receipt_ref': 'rcpt-1',
        },
        'aggregate_id': 'op-1',
        'needs_verified': True,
    },
    'VoiceReady': {
        'builder': repositories.build_voice_ready,
        'kwargs_payload': {
            'voice_artifact_ref': 'voice-1',
            'voice_hash': 'a' * 64,
            'script_version_id': 'script-v1',
            'receipt_ref': 'rcpt-2',
        },
        'expected_payload': {
            'voice_artifact_ref': 'voice-1',
            'voice_hash': 'a' * 64,
            'script_version_id': 'script-v1',
            'receipt_ref': 'rcpt-2',
        },
        'aggregate_id': 'voice-1',
        'needs_verified': True,
    },
    'WordTimingReady': {
        'builder': repositories.build_word_timing_ready,
        'kwargs_payload': {
            'timing_artifact_ref': 'timing-1',
            'voice_hash': 'a' * 64,
            'script_version_id': 'script-v1',
            'validation_report_ref': 'report-1',
        },
        'expected_payload': {
            'timing_artifact_ref': 'timing-1',
            'voice_hash': 'a' * 64,
            'script_version_id': 'script-v1',
            'validation_report_ref': 'report-1',
        },
        'aggregate_id': 'timing-1',
        'needs_verified': True,
    },
}


def _build(name: str, **over):
    info = CASES[name]
    builder = info['builder']
    kwargs = dict(info['kwargs_payload'])
    context = over.pop('context', _context())
    agg_id = over.pop('aggregate_id', info['aggregate_id'])
    agg_rev = over.pop('aggregate_revision', 3)
    call_kwargs = {
        'aggregate_id': agg_id,
        'aggregate_revision': agg_rev,
    }
    if info['needs_verified']:
        call_kwargs['artifact_verified'] = over.pop('artifact_verified', True)
    kwargs.update(over)
    call_kwargs.update(kwargs)
    return builder(context, **call_kwargs)


@pytest.mark.parametrize('event_name', list(CASES.keys()))
def test_builder_returns_controlplane_domain_event(event_name):
    event = _build(event_name)
    assert type(event) is contracts.DomainEvent
    assert repositories.DomainEvent is contracts.DomainEvent
    assert event.event_name == event_name
    assert event.aggregate_type == repositories.EVENT_AGGREGATE_TYPES[event_name]
    assert event.producer == 'E'
    assert event.schema_version == '1.0.0'
    assert event.sensitivity == 'internal'
    assert event.recovery_epoch == 'epoch-0001'
    assert event.aggregate_revision == 3
    assert event.event_id == 'evt-1'
    assert event.message_id == 'msg-1'
    assert event.workspace_id == 'ws-1'
    assert event.payload == CASES[event_name]['expected_payload']
    json.dumps(event.payload)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.event_name = 'Other'


@pytest.mark.parametrize('event_name', list(CASES.keys()))
def test_payload_values_are_only_ref_hash_revision(event_name):
    event = _build(event_name)
    for key, val in event.payload.items():
        assert any(
            key.endswith(suffix)
            for suffix in ('_ref', '_refs', '_hash', '_hashes', '_sha256', '_id', '_revision')
        )
        assert isinstance(val, (str, list))
        if isinstance(val, list):
            for item in val:
                assert isinstance(item, str)
        assert not isinstance(val, bytes)


@pytest.mark.parametrize('event_name', [k for k, v in CASES.items() if v['needs_verified']])
def test_unverified_artifact_is_rejected(event_name):
    for bad_flag in (False, None, 0, 1, 'true'):
        with pytest.raises(repositories.ArtifactNotVerifiedError) as exc_info:
            _build(event_name, artifact_verified=bad_flag)
        assert exc_info.value.code == 'ARTIFACT_NOT_VERIFIED'
    event = _build(event_name, artifact_verified=True)
    assert event.event_name == event_name
    info = CASES[event_name]
    with pytest.raises(TypeError):
        info['builder'](_context(), aggregate_id='id-1', aggregate_revision=1, **info['kwargs_payload'])


def test_image_safety_builder_has_no_verified_flag():
    with pytest.raises(TypeError):
        repositories.build_image_safety_assessed(
            _context(),
            aggregate_id='assess-1',
            aggregate_revision=1,
            artifact_verified=True,
            **CASES['ImageSafetyAssessed']['kwargs_payload'],
        )


@pytest.mark.parametrize('event_name', list(CASES.keys()))
def test_audio_bytes_or_bad_hash_in_payload_is_rejected(event_name):
    kwargs = dict(CASES[event_name]['kwargs_payload'])
    for k in kwargs:
        bad_kw = dict(kwargs)
        bad_kw[k] = b'RIFFdata'
        with pytest.raises(ValueError):
            _build(event_name, **bad_kw)

    for k in kwargs:
        if any(k.endswith(s) for s in ('_hash', '_hashes', '_sha256')):
            for bad_hash in ('ABC', 'a' * 63):
                bad_kw = dict(kwargs)
                if k == 'output_hashes':
                    bad_kw[k] = [bad_hash, 'e' * 64]
                else:
                    bad_kw[k] = bad_hash
                with pytest.raises(ValueError):
                    _build(event_name, **bad_kw)

    if event_name == 'MediaProcessingCompleted':
        with pytest.raises(ValueError):
            _build(
                'MediaProcessingCompleted',
                output_hashes=['d' * 64],
                output_artifact_refs=['out-1', 'out-2'],
            )
        with pytest.raises(ValueError):
            _build(
                'MediaProcessingCompleted',
                output_artifact_refs=[],
                output_hashes=[],
            )


def test_secret_or_trace_value_is_rejected_by_contract_guard():
    with pytest.raises(ValueError, match='unsafe domain event payload'):
        _build('VoiceReady', voice_artifact_ref='token=abc')
    with pytest.raises(ValueError, match='unsafe domain event payload'):
        _build('VoiceReady', voice_artifact_ref='traceback')


def test_builder_calls_contract_payload_guard(monkeypatch):
    calls = []

    def spy(payload):
        calls.append(payload)
        return contracts.ensure_safe_event_payload(payload)

    monkeypatch.setattr(repositories, 'ensure_safe_event_payload', spy)
    event = _build('VoiceReady')
    assert len(calls) > 0
    assert calls[0] == CASES['VoiceReady']['expected_payload']


# ---------------------------------------------------------------------------
# Phần 4: Context, Dedup, Envelope Fixture, Ranh giới
# ---------------------------------------------------------------------------


def test_invalid_context_and_revision_are_rejected():
    ctx_none_epoch = _context(recovery_epoch=None)
    with pytest.raises(repositories.EventEnvelopeError) as exc_info:
        _build('VoiceReady', context=ctx_none_epoch)
    assert ('wrong_type', 'recovery_epoch') in exc_info.value.issues

    ctx_empty_epoch = _context(recovery_epoch='')
    with pytest.raises(repositories.EventEnvelopeError) as exc_info:
        _build('VoiceReady', context=ctx_empty_epoch)
    assert ('constraint_violation', 'recovery_epoch') in exc_info.value.issues

    ctx_empty_event_id = _context(event_id='')
    with pytest.raises(repositories.EventEnvelopeError) as exc_info:
        _build('VoiceReady', context=ctx_empty_event_id)
    assert ('constraint_violation', 'event_id') in exc_info.value.issues

    for bad_rev in ('3', True, 0, -1, None):
        with pytest.raises(repositories.EventEnvelopeError) as exc_info:
            _build('VoiceReady', aggregate_revision=bad_rev)
        assert isinstance(exc_info.value, ValueError)

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

    ctx_valid = _context(causation_id=None)
    assert ctx_valid.causation_id is None


def test_deduplication_id_for_is_stable():
    event = _build('VoiceReady')
    assert repositories.deduplication_id_for(event) == 'ws-1:VoiceReady:voice-1:3'
    event2 = _build('VoiceReady', aggregate_revision=4)
    assert repositories.deduplication_id_for(event2) == 'ws-1:VoiceReady:voice-1:4'
    assert repositories.deduplication_id_for(event) != repositories.deduplication_id_for(event2)


def test_event_flows_through_outbox_inside_uow():
    event = _build('VoiceReady')
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

    recs = uow.outbox.records()
    assert len(recs) == 1
    assert recs[0].payload['payload']['voice_hash'] == 'a' * 64
    assert recs[0].payload['producer'] == 'E'

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
    valid_envelope = fixture['entities']['DomainEvent']['valid'][0]
    assert repositories.envelope_issues(valid_envelope) == ()


def _load_invalid_cases():
    fixture = json.loads(ENVELOPE_FIXTURE.read_text(encoding='utf-8'))
    return fixture['entities']['DomainEvent']['invalid']


@pytest.mark.parametrize(
    'case',
    _load_invalid_cases(),
    ids=[c['case'] for c in _load_invalid_cases()],
)
def test_fixture_invalid_envelopes(case):
    assert {c['case'] for c in _load_invalid_cases()} == {
        'producer_outside_modules',
        'aggregate_revision_as_string',
        'stack_trace_in_event',
        'missing_recovery_epoch',
    }
    issues = repositories.envelope_issues(case['payload'])
    expected = case['expected_error']
    assert issues == ((expected['code'], expected['field']),)


def test_builder_envelopes_are_valid_for_all_events():
    for event_name in CASES:
        event = _build(event_name)
        envelope_dict = {n: getattr(event, n) for n in repositories.ENVELOPE_FIELDS}
        assert repositories.envelope_issues(envelope_dict) == ()
        assert repositories.envelope_issues(dataclasses.asdict(event)) == ()


def test_constants_match_binding():
    binding = json.loads(BINDING.read_text(encoding='utf-8'))
    entity = next(e for e in binding['entities'] if e['name'] == 'DomainEvent')
    fields = entity['fields']
    binding_fields = {f['name']: f['type'] for f in fields}
    assert binding_fields == dict(repositories.ENVELOPE_FIELDS)
    producer_field = next(f for f in fields if f['name'] == 'producer')
    assert producer_field['enum'] == list(repositories.MODULE_IDS)
    assert set(entity['forbidden_fields']) == repositories.FORBIDDEN_ENVELOPE_FIELDS


def test_envelope_issues_edge_cases():
    assert repositories.envelope_issues([]) == (('wrong_type', '$'),)
    fixture = json.loads(ENVELOPE_FIXTURE.read_text(encoding='utf-8'))
    valid = copy.deepcopy(fixture['entities']['DomainEvent']['valid'][0])

    p1 = copy.deepcopy(valid)
    p1['payload'] = {'a': {'blob': 'x'}}
    assert ('forbidden_field', 'blob') in repositories.envelope_issues(p1)

    p2 = copy.deepcopy(valid)
    p2['payload'] = {'bytes_field': b'some-bytes'}
    assert ('forbidden_field', 'payload') in repositories.envelope_issues(p2)

    p3 = copy.deepcopy(valid)
    p3['aggregate_revision'] = True
    assert ('wrong_type', 'aggregate_revision') in repositories.envelope_issues(p3)

    p4 = copy.deepcopy(valid)
    p4['aggregate_revision'] = 0
    assert ('constraint_violation', 'aggregate_revision') in repositories.envelope_issues(p4)

    p5 = copy.deepcopy(valid)
    p5['event_id'] = ' '
    assert ('constraint_violation', 'event_id') in repositories.envelope_issues(p5)

    p6 = copy.deepcopy(valid)
    p6['producer'] = 'e'
    assert ('enum_violation', 'producer') in repositories.envelope_issues(p6)

    p7 = copy.deepcopy(valid)
    p7['producer'] = 5
    assert ('wrong_type', 'producer') in repositories.envelope_issues(p7)

    p8 = copy.deepcopy(valid)
    p8['workspace_id'] = 'ws-1'
    assert repositories.envelope_issues(p8) == ()


def test_sources_reuse_controlplane_types_and_respect_boundaries():
    forbidden_imports = {
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
    }
    for source_path in SOURCES:
        tree = ast.parse(source_path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in ('IUnitOfWork', 'IOutboxWriter', 'DomainEvent')
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith('src.')
                    root_mod = alias.name.split('.')[0]
                    assert root_mod not in forbidden_imports
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith('src.')
                    root_mod = node.module.split('.')[0]
                    assert root_mod not in forbidden_imports

    mem_tree = ast.parse(SOURCES[1].read_text(encoding='utf-8'))
    mem_imports = {}
    for node in ast.walk(mem_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mem_imports[node.module] = [alias.name for alias in node.names]

    assert 'IUnitOfWork' in mem_imports.get('controlplane.domain.interfaces.uow', [])
    assert 'IOutboxWriter' in mem_imports.get('controlplane.domain.interfaces.outbox', [])
    assert 'RevisionConflictError' in mem_imports.get('controlplane.domain.concurrency', [])

    repo_tree = ast.parse(SOURCES[0].read_text(encoding='utf-8'))
    repo_imports = {}
    for node in ast.walk(repo_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            repo_imports[node.module] = [alias.name for alias in node.names]

    assert 'DomainEvent' in repo_imports.get('controlplane.domain.events.contracts', [])
    assert 'ensure_safe_event_payload' in repo_imports.get('controlplane.domain.events.contracts', [])

    assert IUnitOfWork in memory.InMemoryUnitOfWork.__mro__
    assert IOutboxWriter in memory.InMemoryOutboxWriter.__mro__
