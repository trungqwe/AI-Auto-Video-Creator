"""B-11: ResolveCollectedDocument activity handler for G (CT-WF-003, CT-WF-006, D8-B-12, EG-M3-5)."""
import copy
import itertools
import json
import pathlib
import re
from datetime import datetime, timezone

import pytest

from ingestion.application.activity_handler import (
    ACTIVITY_NAME,
    FORBIDDEN_FIELD,
    INVALID_VALUE,
    OPERATION_KEY_CONFLICT,
    REQUEST_FORBIDDEN,
    REQUEST_OPTIONAL,
    REQUEST_REQUIRED,
    RESULT_ENUM,
    RESULT_OPTIONAL,
    RESULT_REQUIRED,
    ActivityRequestError,
    ResolveActivityDeps,
    handle_resolve_activity,
    validate_activity_request,
    validate_activity_result,
    validate_resolve_request,
)
from ingestion.application.resolve_document import FAILED_FINAL, FAILED_RETRYABLE, VALIDATION_ERROR
from ingestion.domain.package_validation import ENUM_VIOLATION, MISSING_REQUIRED, WRONG_TYPE
from ingestion.infrastructure.memory import InMemorySourceTierLookup, InMemoryUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'g-activity-execution.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-activity-execution' / 'payloads.json'
DOCUMENT_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'a-b-collected-document' / 'payloads.json'
HANDLER_PATH = ROOT / 'src' / 'ingestion' / 'application' / 'activity_handler.py'
REQUEST = 'ActivityRequest'
RESULT = 'ActivityResult'
ENTITIES = (REQUEST, RESULT)
VALIDATORS = {REQUEST: validate_activity_request, RESULT: validate_activity_result}
CONSTANTS = {REQUEST: (REQUEST_REQUIRED, REQUEST_OPTIONAL, {}), RESULT: (RESULT_REQUIRED, RESULT_OPTIONAL, RESULT_ENUM)}
POLICY = {'dedup_policy_revision': 'dedup-policy-r1', 'near_duplicate_jaccard': 0.90, 'shingle_size': 5}
SOURCE_A = '00000000-0000-4000-8000-000000000002'
TIERS = {SOURCE_A: 2}
GRANT = {
    'grant_id': '00000000-0000-4000-8000-000000000065',
    'execution_generation': 3,
    'recovery_epoch': 'epoch-0007',
    'stage_run_id': '00000000-0000-4000-8000-000000000062',
}
EMPTY = ((),) * 6


def _binding_entity(name: str) -> dict:
    entities = json.loads(BINDING_PATH.read_text(encoding='utf-8'))['entities']
    return next(item for item in entities if item['name'] == name)


def _fixture(entity: str) -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][entity]


def _documents() -> dict:
    return json.loads(DOCUMENT_PATH.read_text(encoding='utf-8'))['entities']['CollectedDocumentPackage']


def _package(number: int = 1) -> dict:
    package = copy.deepcopy(_documents()['valid'][0])
    if number != 1:
        package['collected_document_id'] = f'00000000-0000-4000-9000-{number:012d}'
    return package


def _doc_id(package: dict) -> str:
    return package['collected_document_id']


def _two_documents() -> tuple[dict, dict]:
    first, second = _package(1), _package(2)
    first['extracted_content_candidate']['text'] = ' '.join(f'alpha{i:02d}' for i in range(40))
    second['extracted_content_candidate']['text'] = ' '.join(f'bravo{i:02d}' for i in range(40))
    second['final_url'] = 'https://news.example.org/second'
    return first, second


def _request(package: dict, key: str = 'op-resolve-1', **overrides: object) -> dict:
    request = copy.deepcopy(_fixture(REQUEST)['valid'][0])
    request.update(
        activity_name=ACTIVITY_NAME,
        operation_key=key,
        execution_grant=dict(GRANT),
        input_refs=[{'ref_type': 'collected_document_package', 'ref_id': _doc_id(package)}],
    )
    request.update(overrides)
    return request

class _Ids:
    def __init__(self) -> None:
        self.issued: list[str] = []

    def __call__(self) -> str:
        self.issued.append(f'b11-{len(self.issued) + 1:04d}')
        return self.issued[-1]


class _Clock:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)


class _Loader:
    def __init__(self, items: dict) -> None:
        self.items = items
        self.calls: list[str] = []

    def __call__(self, ref: dict) -> dict:
        self.calls.append(ref['ref_id'])
        item = self.items[ref['ref_id']]
        if isinstance(item, Exception):
            raise item
        return copy.deepcopy(item)


class _Env:
    def __init__(self, items: dict | None = None) -> None:
        counter = itertools.count(1)
        self.uow = InMemoryUnitOfWork(id_factory=lambda: f'outbox-{next(counter)}')
        self.ids = _Ids()
        self.clock = _Clock()
        self.loader = _Loader({} if items is None else items)
        self.deps = ResolveActivityDeps(self.uow, InMemorySourceTierLookup(TIERS), self.ids, POLICY)

    def handle(self, request: dict) -> dict:
        return handle_resolve_activity(request, self.loader, self.deps, self.clock)

    def snapshot(self) -> tuple:
        kinds = ('collected_document_resolution', 'dedup_evidence', 'article_media_attachment', 'activity_result')
        return (
            self.uow.committed('article'),
            *(tuple(dict(record) for record in self.uow.committed(kind)) for kind in kinds),
            self.uow.committed_outbox(),
        )

def _issues(entity: str, payload: object) -> list[tuple[str, str]]:
    return [(issue.code, issue.field) for issue in VALIDATORS[entity](payload)]


def _derive(fields: list[dict]) -> tuple[dict, dict, dict]:
    return (
        {f['name']: f['type'] for f in fields if f['required']},
        {f['name']: f['type'] for f in fields if not f['required']},
        {f['name']: tuple(f['enum']) for f in fields if 'enum' in f},
    )


@pytest.mark.parametrize('entity', ENTITIES)
def test_constants_match_binding(entity: str) -> None:
    constants = tuple(dict(table) for table in CONSTANTS[entity])
    assert constants[0]
    assert constants == _derive(_binding_entity(entity)['fields'])


def test_forbidden_fields_match_binding() -> None:
    assert REQUEST_FORBIDDEN == tuple(_binding_entity(REQUEST)['forbidden_fields']) == ('secret_value', 'raw_blob')


@pytest.mark.parametrize('entity', ENTITIES)
def test_fixture_valid_payloads_have_no_binding_issues(entity: str) -> None:
    valid = _fixture(entity)['valid']
    assert valid
    for payload in valid:
        assert _issues(entity, payload) == []


@pytest.mark.parametrize(
    ('entity', 'case'),
    [pytest.param(entity, case, id=case['case']) for entity in ENTITIES for case in _fixture(entity)['invalid']],
)
def test_fixture_invalid_case_returns_expected_issue(entity: str, case: dict) -> None:
    expected = case['expected_error']
    assert _issues(entity, case['payload']) == [(expected['code'], expected['field'])]


@pytest.mark.parametrize('entity', ENTITIES)
def test_each_missing_required_field_is_reported(entity: str) -> None:
    for name in CONSTANTS[entity][0]:
        payload = copy.deepcopy(_fixture(entity)['valid'][0])
        del payload[name]
        assert _issues(entity, payload) == [(MISSING_REQUIRED, name)], name


@pytest.mark.parametrize('entity', ENTITIES)
def test_non_mapping_payload_is_wrong_type(entity: str) -> None:
    for value in (None, [], 'payload'):
        assert _issues(entity, value) == [(WRONG_TYPE, '$')], value


@pytest.mark.parametrize(('field', 'value', 'code'), [
    ('disposition', 'done', ENUM_VIOLATION),
    ('execution_generation', True, WRONG_TYPE),
    ('completed_at', '2026-10-18T08:00:00', WRONG_TYPE),
    ('output_refs', None, WRONG_TYPE),
])
def test_result_counterexamples_are_rejected(field: str, value: object, code: str) -> None:
    payload = copy.deepcopy(_fixture(RESULT)['valid'][0])
    payload[field] = value
    assert _issues(RESULT, payload) == [(code, field)]

MUTATIONS = [
    pytest.param(lambda r: r.update(activity_name='CreateVoiceTrack'), (INVALID_VALUE, 'activity_name'), id='other_activity'),
    pytest.param(lambda r: r.update(operation_key='  '), (INVALID_VALUE, 'operation_key'), id='blank_operation_key'),
    pytest.param(lambda r: r.update(input_refs=[]), (INVALID_VALUE, 'input_refs'), id='no_input_ref'),
    pytest.param(lambda r: r['input_refs'].append(dict(r['input_refs'][0])), (INVALID_VALUE, 'input_refs'), id='two_input_refs'),
    pytest.param(lambda r: r.update(input_refs=['doc-1']), (WRONG_TYPE, 'input_refs'), id='input_ref_not_object'),
    pytest.param(lambda r: r['input_refs'][0].pop('ref_id'), (WRONG_TYPE, 'input_refs'), id='input_ref_without_id'),
    pytest.param(lambda r: r.pop('execution_grant'), (MISSING_REQUIRED, 'execution_grant'), id='no_grant'),
    pytest.param(lambda r: r.update(execution_grant=None), (MISSING_REQUIRED, 'execution_grant'), id='null_grant'),
    pytest.param(lambda r: r.update(execution_grant='grant'), (WRONG_TYPE, 'execution_grant'), id='grant_not_object'),
    pytest.param(lambda r: r['execution_grant'].pop('grant_id'), (MISSING_REQUIRED, 'execution_grant.grant_id'), id='grant_without_id'),
    pytest.param(lambda r: r['execution_grant'].pop('execution_generation'), (MISSING_REQUIRED, 'execution_grant.execution_generation'), id='grant_without_generation'),
    pytest.param(lambda r: r['execution_grant'].pop('recovery_epoch'), (MISSING_REQUIRED, 'execution_grant.recovery_epoch'), id='grant_without_epoch'),
    pytest.param(lambda r: r['execution_grant'].update(execution_generation='3'), (WRONG_TYPE, 'execution_grant.execution_generation'), id='generation_string'),
    pytest.param(lambda r: r['execution_grant'].update(recovery_epoch='epoch 7'), (INVALID_VALUE, 'execution_grant.recovery_epoch'), id='epoch_with_space'),
    pytest.param(lambda r: r['execution_grant'].update(stage_run_id='other-stage'), (INVALID_VALUE, 'execution_grant.stage_run_id'), id='grant_for_other_stage'),
    pytest.param(lambda r: r.update(secret_value='x'), (FORBIDDEN_FIELD, 'secret_value'), id='secret_value'),
    pytest.param(lambda r: r.update(raw_blob=''), (FORBIDDEN_FIELD, 'raw_blob'), id='raw_blob'),
]


def _resolve_issues(request: dict) -> list[tuple[str, str]]:
    return [(issue.code, issue.field) for issue in validate_resolve_request(request)]


def test_valid_resolve_request_has_no_issues_and_binding_fixture_is_not_a_resolve_request() -> None:
    assert _resolve_issues(_request(_package())) == []
    assert _resolve_issues(_fixture(REQUEST)['valid'][0]) == [
        (INVALID_VALUE, 'activity_name'),
        (MISSING_REQUIRED, 'execution_grant'),
    ]


@pytest.mark.parametrize(('mutate', 'expected'), MUTATIONS)
def test_resolve_request_rules(mutate: object, expected: tuple[str, str]) -> None:
    request = _request(_package())
    mutate(request)
    assert _resolve_issues(request) == [expected]


@pytest.mark.parametrize(('mutate', 'expected'), MUTATIONS)
def test_rejected_request_never_loads_resolves_or_builds_a_result(mutate: object, expected: tuple[str, str]) -> None:
    package = _package()
    env = _Env({_doc_id(package): package})
    request = _request(package)
    mutate(request)
    with pytest.raises(ActivityRequestError) as raised:
        env.handle(request)
    assert raised.value.code == VALIDATION_ERROR
    assert [(issue.code, issue.field) for issue in raised.value.issues] == [expected]
    assert (env.loader.calls, env.clock.calls, env.ids.issued) == ([], 0, [])
    assert env.snapshot() == EMPTY

def test_succeeded_result_has_every_required_field_and_grant_from_request() -> None:
    package = _package()
    env = _Env({_doc_id(package): package})
    request = _request(package)
    result = env.handle(request)
    assert validate_activity_result(result) == []
    assert result['disposition'] == 'succeeded' and 'problem' not in result
    assert (result['stage_run_id'], result['grant_id'], result['execution_generation'], result['recovery_epoch']) == (
        request['stage_run_id'], GRANT['grant_id'], 3, 'epoch-0007',
    )
    assert result['completed_at'] == '2026-10-18T09:00:00Z'
    assert result['output_refs'] == [
        {'ref_type': 'collected_document_resolution', 'ref_id': f'{_doc_id(package)}:dedup-policy-r1'},
    ]
    (stored,) = env.uow.committed('collected_document_resolution')
    assert (stored['collected_document_id'], stored['dedup_policy_revision'], stored['disposition']) == (
        _doc_id(package), 'dedup-policy-r1', 'NEW_ARTICLE',
    )
    (record,) = env.uow.committed_outbox()
    assert record.payload['recovery_epoch'] == 'epoch-0007'
    assert env.loader.calls == [_doc_id(package)]


@pytest.mark.parametrize('error', [ConnectionError('storage.internal:5432 refused'), TimeoutError('slow'), OSError('disk')])
def test_retryable_loader_error_returns_failed_result_with_problem(error: OSError) -> None:
    package = _package()
    env = _Env({_doc_id(package): error})
    result = env.handle(_request(package))
    assert validate_activity_result(result) == []
    assert (result['disposition'], result['output_refs']) == ('failed', [])
    assert (result['grant_id'], result['execution_generation'], result['recovery_epoch']) == (
        GRANT['grant_id'], 3, 'epoch-0007',
    )
    assert (result['problem']['code'], result['problem']['retryable']) == (FAILED_RETRYABLE, True)
    assert str(error) not in repr(result)
    assert env.snapshot() == EMPTY


def test_port_error_during_resolve_is_failed_retryable_then_retry_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    package = _package()
    env = _Env({_doc_id(package): package})
    request = _request(package)

    def down(*args: object, **kwargs: object) -> None:
        raise ConnectionError('storage unavailable')

    monkeypatch.setattr(env.uow.outbox, 'append_event', down)
    failed = env.handle(request)
    assert validate_activity_result(failed) == []
    assert (failed['disposition'], failed['problem']['code'], failed['problem']['retryable']) == (
        'failed', FAILED_RETRYABLE, True,
    )
    assert env.snapshot() == EMPTY
    monkeypatch.undo()
    assert env.handle(request)['disposition'] == 'succeeded'
    assert env.loader.calls == [_doc_id(package)] * 2
    assert len(env.uow.committed('article')) == 1

def test_missing_package_is_failed_final() -> None:
    package = _package()
    env = _Env({_doc_id(package): LookupError('unknown ref')})
    result = env.handle(_request(package))
    assert validate_activity_result(result) == []
    assert (result['disposition'], result['problem']['code'], result['problem']['retryable']) == (
        'failed', FAILED_FINAL, False,
    )
    assert env.snapshot() == EMPTY


def test_invalid_package_is_failed_with_validation_problem() -> None:
    case = _documents()['invalid'][0]
    env = _Env({'doc-invalid': copy.deepcopy(case['payload'])})
    request = _request(_package(), input_refs=[{'ref_type': 'collected_document_package', 'ref_id': 'doc-invalid'}])
    result = env.handle(request)
    expected = case['expected_error']
    assert validate_activity_result(result) == []
    assert (result['disposition'], result['problem']['code'], result['problem']['retryable']) == (
        'failed', VALIDATION_ERROR, False,
    )
    assert result['problem']['issues'] == [{'code': expected['code'], 'field': expected['field']}]
    assert env.snapshot() == EMPTY


@pytest.mark.parametrize('failing', [0, 1])
def test_one_failing_document_does_not_fail_the_other_request(failing: int) -> None:
    packages = _two_documents()
    env = _Env({_doc_id(package): package for package in packages})
    env.loader.items[_doc_id(packages[failing])] = ConnectionError('upstream unavailable')
    requests = [_request(package, key=f'op-resolve-{number}') for number, package in enumerate(packages)]
    results = [env.handle(request) for request in requests]
    healthy = 1 - failing
    assert all(validate_activity_result(result) == [] for result in results)
    assert [result['disposition'] for result in results] == ['succeeded' if n == healthy else 'failed' for n in (0, 1)]
    assert results[failing]['problem']['retryable'] is True and 'problem' not in results[healthy]
    assert results[healthy]['output_refs'][0]['ref_id'] == f'{_doc_id(packages[healthy])}:dedup-policy-r1'
    articles = env.uow.committed('article')
    assert [article.revisions[0].collected_document_id for article in articles] == [_doc_id(packages[healthy])]
    env.loader.items[_doc_id(packages[failing])] = packages[failing]
    assert env.handle(requests[failing])['disposition'] == 'succeeded'
    assert len(env.uow.committed('article')) == 2

def test_same_operation_key_returns_same_result_without_resolving_again() -> None:
    package = _package()
    env = _Env({_doc_id(package): package})
    request = _request(package)
    first = env.handle(request)
    assert validate_activity_result(first) == []
    assert first['disposition'] == 'succeeded'
    before, issued, clock_calls = env.snapshot(), list(env.ids.issued), env.clock.calls
    assert env.handle(copy.deepcopy(request)) == first
    assert env.loader.calls == [_doc_id(package)]
    assert (env.snapshot(), env.ids.issued, env.clock.calls) == (before, issued, clock_calls)
    first['output_refs'].clear()
    assert env.handle(request)['output_refs'] != []


def test_failed_attempt_is_not_stored_so_the_same_key_resolves_again() -> None:
    package = _package()
    env = _Env({_doc_id(package): ConnectionError('down')})
    request = _request(package)
    assert env.handle(request).get('disposition') == 'failed'
    assert env.uow.committed('activity_result') == ()
    env.loader.items[_doc_id(package)] = package
    assert env.handle(request).get('disposition') == 'succeeded'
    assert env.loader.calls == [_doc_id(package)] * 2


def test_operation_key_reused_for_another_input_is_conflict_without_resolving() -> None:
    first, second = _two_documents()
    env = _Env({_doc_id(first): first, _doc_id(second): second})
    assert env.handle(_request(first, key='op-shared')).get('disposition') == 'succeeded'
    before = env.snapshot()
    result = env.handle(_request(second, key='op-shared'))
    assert validate_activity_result(result) == []
    assert (result['disposition'], result['problem']['code'], result['problem']['retryable']) == (
        'failed', OPERATION_KEY_CONFLICT, False,
    )
    assert env.loader.calls == [_doc_id(first)]
    assert env.snapshot() == before


def test_new_operation_key_for_a_resolved_document_does_not_duplicate_aggregates() -> None:
    package = _package()
    env = _Env({_doc_id(package): package})
    first = env.handle(_request(package, key='op-resolve-1'))
    second = env.handle(_request(package, key='op-resolve-2'))
    assert validate_activity_result(first) == validate_activity_result(second) == []
    assert (first['disposition'], second['disposition']) == ('succeeded', 'succeeded')
    assert second['output_refs'] == first['output_refs']
    assert (len(env.uow.committed('article')), len(env.uow.committed_outbox())) == (1, 1)
    assert len(env.uow.committed('activity_result')) == 2


BOUNDARY_RE = re.compile('(?m)^[ ]*(from|import)[ ]+(src[.]|socket|requests|httpx|urllib|http[.]client|psycopg)')


def test_handler_source_respects_import_boundary() -> None:
    source = HANDLER_PATH.read_text(encoding='utf-8')
    assert source.strip()
    assert not BOUNDARY_RE.search(source)
    for line in ('from src.ingestion import x', 'import http.client', 'from urllib.parse import urljoin'):
        assert BOUNDARY_RE.search(line), line
