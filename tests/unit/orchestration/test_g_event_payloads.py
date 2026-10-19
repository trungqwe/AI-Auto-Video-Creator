"""G-13: event payload của G (CT-EVT-002/003; TST-SEC-INV-012 phần G).

coveredIds: CT-EVT-002, CT-EVT-003, TST-SEC-INV-012 (phần G)
"""
import ast
import copy
import inspect
import json
import pathlib

import pytest

from controlplane.application.orchestration import event_payloads as ep
from controlplane.application.orchestration.event_payloads import build_g_event

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'orchestration' / 'event_payloads.py'
ENTITY = json.loads((ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'domain-event-envelope.json').read_text(encoding='utf-8'))['entities'][0]
REQUIRED = [field['name'] for field in ENTITY['fields'] if field['required']]
FORBIDDEN = ENTITY['forbidden_fields']
CANARY = 'CANARY-9f3a'
G_EVENTS = ['BatchStarted', 'JobAllocated', 'StageStateChanged', 'JobWaiting', 'JobFailed', 'VideoCompleted', 'BatchTargetReached', 'BatchExhausted']
PAYLOADS = {
    'BatchStarted': {'batch_id': 'batch-1', 'workspace_id': 'ws-1'},
    'JobAllocated': {'batch_id': 'batch-1', 'job_id': 'job-1', 'reservation_id': 'res-1'},
    'StageStateChanged': {'job_id': 'job-1', 'stage_run_id': 'run-1', 'stage_run_revision': 3},
    'JobWaiting': {'job_id': 'job-1', 'stage_run_id': 'run-1'},
    'JobFailed': {'job_id': 'job-1', 'stage_run_id': 'run-1'},
    'VideoCompleted': {'batch_id': 'batch-1', 'job_id': 'job-1', 'completion_id': 'led-1'},
    'BatchTargetReached': {'batch_id': 'batch-1'},
    'BatchExhausted': {'batch_id': 'batch-1'},
}
_UNSET = object()


def build(event_name='BatchStarted', payload=_UNSET, **override):
    args = {'event_name': event_name, 'aggregate_id': 'agg-1', 'aggregate_revision': 4, 'recovery_epoch': 'epoch-1', 'payload': copy.deepcopy(PAYLOADS[event_name]) if payload is _UNSET else payload}
    return build_g_event(**(args | override))


def test_event_names_are_exactly_the_eight_g_events():
    assert ep.EVENT_NAMES == frozenset(G_EVENTS)
    assert set(PAYLOADS) == set(G_EVENTS)


@pytest.mark.parametrize('name', G_EVENTS)
def test_valid_event_has_every_required_envelope_field(name):
    event = build(name)
    assert len(REQUIRED) == 10
    assert set(event) == set(REQUIRED)
    assert event['event_name'] == name
    assert event['aggregate_id'] == 'agg-1'
    assert event['aggregate_revision'] == 4
    assert event['payload'] == PAYLOADS[name]
    assert event['event_id'] == f'{name}:agg-1:4'


@pytest.mark.parametrize('name', G_EVENTS)
def test_envelope_constants_follow_d8_g_10(name):
    event = build(name)
    assert event['producer'] == 'G'
    assert event['schema_version'] == '1' and type(event['schema_version']) is str
    assert event['sensitivity'] == 'internal'
    assert event['recovery_epoch'] == 'epoch-1' and type(event['recovery_epoch']) is str
    assert type(event['aggregate_revision']) is int


def test_aggregate_type_per_event():
    types = {name: build(name)['aggregate_type'] for name in G_EVENTS}
    assert types == {'BatchStarted': 'Batch', 'JobAllocated': 'VideoJob', 'StageStateChanged': 'StageRun', 'JobWaiting': 'VideoJob', 'JobFailed': 'VideoJob', 'VideoCompleted': 'VideoJob', 'BatchTargetReached': 'Batch', 'BatchExhausted': 'Batch'}


def test_build_is_deterministic_and_does_not_alias_or_mutate_input():
    payload = {'batch_id': 'batch-1', 'job_ids': ['job-1', 'job-2']}
    before = copy.deepcopy(payload)
    first = build(payload=payload)
    assert first == build(payload=payload)
    assert payload == before
    first['payload']['job_ids'].append('job-3')
    assert payload == before


def test_tuple_values_become_lists_and_zero_revision_is_allowed():
    event = build(payload={'job_ids': ('job-1',), 'stage_run_revision': 0}, aggregate_revision=0)
    assert event['payload'] == {'job_ids': ['job-1'], 'stage_run_revision': 0}
    assert event['aggregate_revision'] == 0

def assert_rejected(**kwargs):
    with pytest.raises(ValueError) as info:
        build(**kwargs)
    assert CANARY not in str(info.value)


@pytest.mark.parametrize('name', ['RenderCompleted', 'ArticleRevisionAccepted', 'batchstarted', 'BatchStarted ', '', None, 5, ['BatchStarted']])
def test_unknown_event_name_is_rejected(name):
    assert_rejected(event_name=name, payload={'batch_id': 'batch-1'})


@pytest.mark.parametrize('value', ['', ' ', 'a b', 'x' * 257, None, 5])
def test_invalid_aggregate_id_is_rejected(value):
    assert_rejected(aggregate_id=value)


@pytest.mark.parametrize('value', [True, '1', 1.0, -1, None])
def test_invalid_aggregate_revision_is_rejected(value):
    assert_rejected(aggregate_revision=value)


@pytest.mark.parametrize('value', [3, 0, True, 3.0, None, '', ' ', 'a b', 'x' * 257])
def test_int_or_blank_recovery_epoch_never_reaches_the_envelope(value):
    assert_rejected(recovery_epoch=value)


@pytest.mark.parametrize('payload', [None, [], 'text', 1, ('batch_id', 'x')])
def test_non_mapping_payload_is_rejected(payload):
    assert_rejected(payload=payload)


def test_forbidden_fields_come_from_the_binding():
    assert set(FORBIDDEN) == {'secret_value', 'raw_oauth_response', 'stack_trace', 'blob'}
    assert ep.FORBIDDEN_FIELDS == frozenset(FORBIDDEN)


@pytest.mark.parametrize('field', FORBIDDEN)
def test_forbidden_field_is_rejected(field):
    assert_rejected(payload={'batch_id': 'batch-1', field: CANARY})


@pytest.mark.parametrize('value', [f'secret={CANARY}', f'token:{CANARY}', f'password={CANARY}', 'Traceback', f'stack trace: {CANARY}', b'blob-bytes', bytearray(b'x')])
def test_canary_secret_or_stack_trace_value_is_rejected(value):
    assert_rejected(payload={'batch_id': 'batch-1', 'job_id': value})


@pytest.mark.parametrize('key', ['token_id', 'secret_id', 'password_id'])
def test_secret_like_key_is_rejected_by_the_safety_helper(key):
    assert_rejected(payload={'batch_id': 'batch-1', key: CANARY})


def test_safety_helper_is_called_with_the_payload(monkeypatch):
    calls = []

    def fake(payload):
        calls.append(payload)
        raise ValueError('unsafe domain event payload')

    monkeypatch.setattr(ep, 'ensure_safe_event_payload', fake)
    assert_rejected()
    assert calls == [PAYLOADS['BatchStarted']]


@pytest.mark.parametrize('key', ['article_text', 'title', 'media_ref', 'BatchId', 'batch id', '', 5, None])
def test_payload_key_must_name_an_id_or_revision(key):
    assert_rejected(payload={'batch_id': 'batch-1', key: 'x'})


@pytest.mark.parametrize('value', [{'nested': 'x'}, 1.5, True, None, -1, '', 'two words', 'x' * 257, ['ok', 'two words'], [{'a': 1}], [[1]]])
def test_payload_value_must_be_an_id_or_revision(value):
    assert_rejected(payload={'batch_id': 'batch-1', 'job_id': value})

def test_video_completed_requires_completion_id():
    assert build('VideoCompleted')['payload']['completion_id'] == 'led-1'
    assert_rejected(event_name='VideoCompleted', payload={'batch_id': 'batch-1', 'job_id': 'job-1'})


@pytest.mark.parametrize('value', ['', ' ', 5, ['led-1'], None])
def test_video_completed_rejects_invalid_completion_id(value):
    assert_rejected(event_name='VideoCompleted', payload={'job_id': 'job-1', 'completion_id': value})


def test_other_events_do_not_require_completion_id():
    for name in G_EVENTS:
        if name != 'VideoCompleted':
            assert 'completion_id' not in build(name)['payload']


def test_signature_is_the_five_parameters_of_the_slice():
    assert list(inspect.signature(build_g_event).parameters) == ['event_name', 'aggregate_id', 'aggregate_revision', 'recovery_epoch', 'payload']


def test_safety_helper_is_the_read_only_import_from_domain_events():
    import controlplane.domain.events.contracts as contracts

    assert ep.ensure_safe_event_payload is contracts.ensure_safe_event_payload


def test_module_is_pure_and_imports_only_the_safety_helper():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots = set()
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add(node.module.split('.')[0])
            modules.add(node.module)
    assert roots <= {'__future__', 'collections', 're', 'typing', 'controlplane'}
    assert {module for module in modules if module.startswith('controlplane')} == {'controlplane.domain.events.contracts'}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert attributes & {'now', 'utcnow', 'today', 'open', 'read_text', 'write_text'} == set()
