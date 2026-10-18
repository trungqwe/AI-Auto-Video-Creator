"""B-4: module B DomainEvent envelope (CT-EVT-002, CT-EVT-003) against BINDING-DOMAIN-EVENT-ENVELOPE."""
import json
import pathlib
import re

import pytest

from controlplane.domain.events import contracts
from ingestion.domain import events
from ingestion.domain.events import AGGREGATE_TYPES, EVENT_NAMES, PRODUCER, SCHEMA_VERSION, SENSITIVITY, build_event

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'domain-event-envelope.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'domain-event-envelope' / 'payloads.json'
EVENTS_PATH = ROOT / 'src' / 'ingestion' / 'domain' / 'events.py'
B_EVENTS = ('ArticleRevisionAccepted', 'DuplicateDocumentResolved', 'EventLinkResolved', 'EventUpdateAccepted')
TYPE_CHECKS = {
    'string': lambda value: isinstance(value, str),
    'integer': lambda value: isinstance(value, int) and not isinstance(value, bool),
    'object': lambda value: isinstance(value, dict),
}


def _entity() -> dict:
    binding = json.loads(BINDING_PATH.read_text(encoding='utf-8'))
    return next(item for item in binding['entities'] if item['name'] == 'DomainEvent')


def _args(**overrides: object) -> dict:
    args = {
        'event_name': 'ArticleRevisionAccepted',
        'aggregate_type': 'Article',
        'aggregate_id': '00000000-0000-4000-8000-0000000000b1',
        'aggregate_revision': 3,
        'payload': {
            'article_id': '00000000-0000-4000-8000-0000000000b1',
            'article_revision_id': '00000000-0000-4000-8000-0000000000b2',
            'revision': 3,
            'source_refs': ['collected-document:00000000-0000-4000-8000-0000000000b3'],
        },
        'recovery_epoch': 'epoch-0001',
        'event_id': '00000000-0000-4000-8000-0000000000b4',
    }
    args.update(overrides)
    return args


def _with_payload(**extra: object) -> dict:
    return _args(payload={**_args()['payload'], **extra})


def test_event_names_are_exactly_module_b_catalog() -> None:
    assert EVENT_NAMES == frozenset(B_EVENTS)


def test_aggregate_types_are_module_b_aggregates() -> None:
    assert AGGREGATE_TYPES == frozenset({'Article', 'ArticleRevision', 'CollectedDocumentResolution', 'Event', 'EventUpdate'})


@pytest.mark.parametrize('event_name', B_EVENTS)
def test_output_has_binding_required_fields_with_binding_types(event_name: str) -> None:
    fields = _entity()['fields']
    assert [field for field in fields if field['required']], 'binding required fields must not be empty'
    event = build_event(**_args(event_name=event_name))
    assert set(event) == {field['name'] for field in fields}
    for field in fields:
        assert TYPE_CHECKS[field['type']](event[field['name']]), field['name']
        if 'enum' in field:
            assert event[field['name']] in field['enum'], field['name']
    assert event['event_name'] == event_name
    assert (event['producer'], PRODUCER) == ('B', 'B')
    assert (event['schema_version'], SCHEMA_VERSION) == ('1.0.0', '1.0.0')
    assert (event['sensitivity'], SENSITIVITY) == ('internal', 'internal')
    assert event['recovery_epoch'] == 'epoch-0001'
    assert event['payload'] == _args()['payload']


def test_output_keys_match_fixture_valid_event() -> None:
    valid = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities']['DomainEvent']['valid'][0]
    assert set(build_event(**_args())) == set(valid)


def test_output_has_no_binding_forbidden_field() -> None:
    forbidden = set(_entity()['forbidden_fields'])
    assert forbidden, 'binding forbidden_fields must not be empty'
    event = build_event(**_args())
    assert event and not forbidden & set(event)
    assert not forbidden & set(event['payload'])


@pytest.mark.parametrize('key', _entity()['forbidden_fields'])
def test_forbidden_field_in_payload_is_rejected(key: str) -> None:
    with pytest.raises(ValueError):
        build_event(**_with_payload(**{key: 'x'}))


@pytest.mark.parametrize('event_name', ['ArticleIngested', 'ArticleUpdated', 'EventDiscovered', 'SourceRemoved', 'articlerevisionaccepted', '', None])
def test_unknown_event_name_is_rejected(event_name: object) -> None:
    with pytest.raises(ValueError):
        build_event(**_args(event_name=event_name))


@pytest.mark.parametrize('key', ['token', 'access_token', 'token_ref'])
def test_payload_token_key_is_rejected_by_contract_guard(key: str) -> None:
    with pytest.raises(ValueError, match='unsafe domain event payload'):
        build_event(**_with_payload(**{key: 'opaque-value'}))


@pytest.mark.parametrize('key', ['normalized_text', 'title', 'body', 'raw_html', 'extracted_content_candidate'])
def test_payload_article_text_key_is_rejected(key: str) -> None:
    with pytest.raises(ValueError):
        build_event(**_with_payload(**{key: 'noi-dung-bai-viet'}))


@pytest.mark.parametrize('value', ['Toàn văn bài viết có nhiều câu.', 'x' * 257, 'dong-1\ndong-2', ''])
def test_payload_article_text_value_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        build_event(**_with_payload(article_revision_ref=value))


@pytest.mark.parametrize('value', ['secret=canary-b4-0001', 'password:canary-b4-0001', 'token=canary-b4-0001'])
def test_payload_canary_secret_value_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match='unsafe domain event payload'):
        build_event(**_with_payload(article_id=value))


@pytest.mark.parametrize('value', [None, {'nested_id': 'x'}, True, 1.5, b'blob', [['x']], -1])
def test_payload_value_outside_id_revision_ref_is_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        build_event(**_with_payload(article_revision_id=value))


@pytest.mark.parametrize('payload', [{}, None, ['article_id'], 'article_id'])
def test_payload_must_be_non_empty_mapping(payload: object) -> None:
    with pytest.raises(ValueError):
        build_event(**_args(payload=payload))


@pytest.mark.parametrize('recovery_epoch', [None, '', 0, 1, 'epoch 1'])
def test_invalid_recovery_epoch_is_rejected(recovery_epoch: object) -> None:
    with pytest.raises(ValueError):
        build_event(**_args(recovery_epoch=recovery_epoch))


def test_missing_recovery_epoch_argument_is_rejected() -> None:
    args = _args()
    del args['recovery_epoch']
    with pytest.raises(TypeError):
        build_event(**args)


@pytest.mark.parametrize(('name', 'value'), [
    ('event_id', ''), ('event_id', None), ('aggregate_id', ''), ('aggregate_id', 7),
    ('aggregate_revision', '3'), ('aggregate_revision', True), ('aggregate_revision', 0),
    ('aggregate_type', 'Source'), ('aggregate_type', None),
])
def test_invalid_envelope_argument_is_rejected(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        build_event(**_args(**{name: value}))


def test_build_event_calls_contract_payload_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def spy(payload: object) -> None:
        calls.append(payload)
        contracts.ensure_safe_event_payload(payload)

    monkeypatch.setattr(events, 'ensure_safe_event_payload', spy)
    build_event(**_args())
    assert calls == [_args()['payload']]


def test_events_module_reuses_contract_guard_without_src_prefix() -> None:
    assert events.ensure_safe_event_payload is contracts.ensure_safe_event_payload
    text = EVENTS_PATH.read_text(encoding='utf-8')
    assert re.search(r'(?m)^from controlplane\.domain\.events\.contracts import ensure_safe_event_payload$', text)
    assert not re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', text)


def test_payload_is_copied_not_aliased() -> None:
    payload = _args()['payload']
    event = build_event(**_args(payload=payload))
    payload['source_refs'].append('collected-document:other')
    assert event['payload']['source_refs'] == _args()['payload']['source_refs']


def test_duplicate_document_resolved_carries_new_media_discovery_refs() -> None:
    payload = {
        'collected_document_id': '00000000-0000-4000-8000-0000000000c1',
        'article_id': '00000000-0000-4000-8000-0000000000b1',
        'new_media_discovery_refs': ['media-discovery:00000000-0000-4000-8000-0000000000c2'],
    }
    args = _args(event_name='DuplicateDocumentResolved', aggregate_type='CollectedDocumentResolution', payload=payload)
    assert build_event(**args)['payload'] == payload
