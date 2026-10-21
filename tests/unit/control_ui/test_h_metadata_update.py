"""H-09: router cập nhật metadata theo allowlist (CT-API-001, CT-API-003, CT-API-004, CT-API-009).

coveredIds: CT-API-001, CT-API-003, CT-API-004, CT-API-009
"""
import ast
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controlplane.api.routes.modules.metadata_update import FORBIDDEN_METADATA_FIELDS, RevisionConflictError, build_metadata_router
from controlplane.api.routes.modules.problem_detail import PROBLEM_SPECS, problem_body

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'api' / 'routes' / 'modules' / 'metadata_update.py'
PREFIX = '/v1/articles'
ITEM_URL = PREFIX + '/item-1'
CORRELATION_ID = 'corr-h09-0001'
IDENTITY = {'workspace_id': 'ws-h09', 'actor_id': 'actor-h09'}
GOOD_HEADERS = {'If-Match': '3', 'Idempotency-Key': 'idem-h09-1'}
ALLOWED = ['notes', 'title']
FORBIDDEN = sorted(FORBIDDEN_METADATA_FIELDS)


class FakeApply:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = {'id': 'item-1', 'revision': 4} if result is None else result
        self.error = error

    def __call__(self, request, item_id, expected_revision, changes, idempotency_key):
        self.calls.append({'request': request, 'item_id': item_id, 'expected_revision': expected_revision, 'changes': changes, 'idempotency_key': idempotency_key})
        if self.error is not None:
            raise self.error
        return self.result


def make_client(fake, allowed_fields=ALLOWED, prefix=PREFIX):
    app = FastAPI()

    @app.middleware('http')
    async def inject_state(request, call_next):
        request.state.correlation_id = CORRELATION_ID
        request.state.identity = IDENTITY
        return await call_next(request)

    app.include_router(build_metadata_router(prefix=prefix, allowed_fields=allowed_fields, apply_update=fake))
    return TestClient(app)


def patch(client, body=None, headers=None, url=ITEM_URL):
    return client.patch(url, json={'notes': 'ghi chú mới'} if body is None else body, headers=GOOD_HEADERS if headers is None else headers)


def assert_problem(response, code, keys):
    assert response.status_code == PROBLEM_SPECS[code][0]
    assert response.headers['content-type'].split(';')[0] == 'application/problem+json'
    payload = response.json()
    assert payload['code'] == code
    assert payload['correlation_id'] == CORRELATION_ID
    assert list(payload['field_errors']) == keys
    return payload


def test_forbidden_fields_constant_is_exact_frozenset():
    assert isinstance(FORBIDDEN_METADATA_FIELDS, frozenset)
    assert FORBIDDEN_METADATA_FIELDS == frozenset({'article_body', 'body', 'script', 'script_text', 'event_relation', 'event_links', 'secret', 'secret_value'})


def test_revision_conflict_error_is_plain_exception():
    assert RevisionConflictError.__bases__ == (Exception,)


@pytest.mark.parametrize('allowed', [['notes', 'script'], ('title', 'article_body'), {'secret'}, frozenset({'notes', 'event_links'})] + [[name] for name in FORBIDDEN])
def test_allowed_fields_intersecting_forbidden_raise_at_build(allowed):
    with pytest.raises(ValueError) as excinfo:
        build_metadata_router(prefix=PREFIX, allowed_fields=allowed, apply_update=FakeApply())
    assert excinfo.value.args == ('forbidden_field_allowed',)


def test_valid_patch_calls_apply_update_once_with_int_revision():
    fake = FakeApply(result={'id': 'item-1', 'revision': 4, 'notes': 'ghi chú mới'})
    response = patch(make_client(fake))
    assert response.status_code == 200
    assert response.json() == fake.result
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call['item_id'] == 'item-1'
    assert call['expected_revision'] == 3 and type(call['expected_revision']) is int
    assert call['changes'] == {'notes': 'ghi chú mới'}
    assert call['idempotency_key'] == 'idem-h09-1'
    assert call['request'].state.identity == IDENTITY
    assert call['request'].state.correlation_id == CORRELATION_ID


@pytest.mark.parametrize('value, expected', [('0', 0), ('007', 7), ('12345', 12345)])
def test_if_match_digits_parsed_as_decimal_int(value, expected):
    fake = FakeApply()
    response = patch(make_client(fake), headers={'If-Match': value, 'Idempotency-Key': 'idem-1'})
    assert response.status_code == 200
    assert fake.calls[0]['expected_revision'] == expected
    assert type(fake.calls[0]['expected_revision']) is int


def test_missing_if_match_is_422_and_not_applied():
    fake = FakeApply()
    response = patch(make_client(fake), headers={'Idempotency-Key': 'idem-1'})
    assert_problem(response, 'VALIDATION_FAILED', ['If-Match'])
    assert fake.calls == []


@pytest.mark.parametrize('value', ['abc', '', '-1', '+1', '1.5', '0x1', '1 2', '"3"', 'W/"3"', '3a', '9' * 19])
def test_invalid_if_match_is_422_and_not_applied(value):
    fake = FakeApply()
    response = patch(make_client(fake), headers={'If-Match': value, 'Idempotency-Key': 'idem-1'})
    assert_problem(response, 'VALIDATION_FAILED', ['If-Match'])
    assert fake.calls == []


def test_duplicate_if_match_header_is_422_and_not_applied():
    fake = FakeApply()
    response = patch(make_client(fake), headers=[('If-Match', '1'), ('If-Match', '2'), ('Idempotency-Key', 'idem-1')])
    assert_problem(response, 'VALIDATION_FAILED', ['If-Match'])
    assert fake.calls == []


@pytest.mark.parametrize('value', [None, '', '   '])
def test_missing_or_blank_idempotency_key_is_422_and_not_applied(value):
    fake = FakeApply()
    headers = {'If-Match': '3'}
    if value is not None:
        headers['Idempotency-Key'] = value
    response = patch(make_client(fake), headers=headers)
    assert_problem(response, 'VALIDATION_FAILED', ['Idempotency-Key'])
    assert fake.calls == []


def test_duplicate_idempotency_key_is_422_and_not_applied():
    fake = FakeApply()
    response = patch(make_client(fake), headers=[('If-Match', '1'), ('Idempotency-Key', 'a'), ('Idempotency-Key', 'b')])
    assert_problem(response, 'VALIDATION_FAILED', ['Idempotency-Key'])
    assert fake.calls == []


@pytest.mark.parametrize('raw', [b'', b'not json', b'[]', b'"text"', b'null', b'1', b'true', b'{}', b'[{"notes": "x"}]', b'\xff\xfe'])
def test_non_object_or_empty_body_is_422_and_not_applied(raw):
    fake = FakeApply()
    response = make_client(fake).patch(ITEM_URL, content=raw, headers={**GOOD_HEADERS, 'Content-Type': 'application/json'})
    assert_problem(response, 'VALIDATION_FAILED', ['body'])
    assert fake.calls == []


def test_all_validation_errors_are_reported_together():
    fake = FakeApply()
    response = make_client(fake).patch(ITEM_URL, content=b'[]', headers={'Content-Type': 'application/json'})
    assert_problem(response, 'VALIDATION_FAILED', ['Idempotency-Key', 'If-Match', 'body'])
    assert fake.calls == []


@pytest.mark.parametrize('name', FORBIDDEN)
def test_forbidden_key_is_422_forbidden_field_and_not_applied(name):
    fake = FakeApply()
    response = patch(make_client(fake), body={name: 'x'})
    assert_problem(response, 'FORBIDDEN_FIELD', [name])
    assert fake.calls == []


def test_article_body_example_from_acceptance():
    fake = FakeApply()
    response = patch(make_client(fake), body={'article_body': 'x'})
    payload = assert_problem(response, 'FORBIDDEN_FIELD', ['article_body'])
    assert payload['status'] == 422
    assert fake.calls == []


def test_all_offending_keys_are_listed_and_nothing_applied():
    fake = FakeApply()
    body = {'notes': 'ok', 'article_body': 'x', 'unknown_field': 'y', 'script': 'z'}
    response = patch(make_client(fake), body=body)
    assert_problem(response, 'FORBIDDEN_FIELD', ['article_body', 'unknown_field', 'script'])
    assert fake.calls == []


def test_key_outside_allowed_fields_is_rejected_even_if_not_in_forbidden_set():
    fake = FakeApply()
    response = patch(make_client(fake, allowed_fields=['notes']), body={'title': 'x'})
    assert_problem(response, 'FORBIDDEN_FIELD', ['title'])
    assert fake.calls == []


def test_header_errors_take_precedence_over_forbidden_field():
    fake = FakeApply()
    response = patch(make_client(fake), body={'article_body': 'x'}, headers={'Idempotency-Key': 'idem-1'})
    assert_problem(response, 'VALIDATION_FAILED', ['If-Match'])
    assert fake.calls == []


def test_forbidden_field_response_never_echoes_values():
    fake = FakeApply()
    response = patch(make_client(fake), body={'script': 'GIA-TRI-NHAY-CAM-123'})
    assert response.status_code == 422
    assert 'GIA-TRI-NHAY-CAM-123' not in response.text


def test_revision_conflict_maps_to_409_problem():
    fake = FakeApply(error=RevisionConflictError('stale-detail'))
    response = patch(make_client(fake))
    payload = assert_problem(response, 'REVISION_CONFLICT', [])
    assert payload == problem_body('REVISION_CONFLICT', correlation_id=CORRELATION_ID)
    assert 'stale-detail' not in response.text
    assert len(fake.calls) == 1


def test_other_errors_propagate_out_of_router():
    fake = FakeApply(error=RuntimeError('boom'))
    with pytest.raises(RuntimeError):
        patch(make_client(fake))
    assert len(fake.calls) == 1


class FakeStore:
    def __init__(self):
        self.revision = 1
        self.notes = 'cũ'
        self.writes = 0

    def __call__(self, request, item_id, expected_revision, changes, idempotency_key):
        if expected_revision != self.revision:
            raise RevisionConflictError('stale')
        self.notes = changes['notes']
        self.revision += 1
        self.writes += 1
        return {'id': item_id, 'revision': self.revision, 'notes': self.notes}


def test_stale_if_match_is_conflict_and_does_not_write():
    store = FakeStore()
    client = make_client(store)
    first = client.patch(ITEM_URL, json={'notes': 'mới'}, headers={'If-Match': '1', 'Idempotency-Key': 'idem-1'})
    assert first.status_code == 200
    assert first.json()['revision'] == 2
    second = client.patch(ITEM_URL, json={'notes': 'ghi đè'}, headers={'If-Match': '1', 'Idempotency-Key': 'idem-2'})
    assert_problem(second, 'REVISION_CONFLICT', [])
    assert (store.notes, store.revision, store.writes) == ('mới', 2, 1)


def test_idempotency_key_is_forwarded_verbatim():
    fake = FakeApply()
    patch(make_client(fake), headers={'If-Match': '2', 'Idempotency-Key': 'Khoa-Idem_0001'})
    assert fake.calls[0]['idempotency_key'] == 'Khoa-Idem_0001'


@pytest.mark.parametrize('method', ['GET', 'PUT', 'DELETE', 'POST'])
def test_other_methods_return_405_and_do_not_apply(method):
    fake = FakeApply()
    response = make_client(fake).request(method, ITEM_URL, headers=GOOD_HEADERS)
    assert response.status_code == 405
    assert fake.calls == []


@pytest.mark.parametrize('allowed', [['notes', 'title'], ('notes',), {'title'}, frozenset(), []])
def test_safe_allowed_fields_build_router(allowed):
    router = build_metadata_router(prefix=PREFIX, allowed_fields=allowed, apply_update=FakeApply())
    assert len(router.routes) == 1


@pytest.mark.parametrize('prefix', ['', '/v1', 'v1/articles', '/v2/articles', '/api/v1/articles', '/V1/articles', None])
def test_prefix_must_start_with_v1_slash(prefix):
    with pytest.raises(ValueError):
        build_metadata_router(prefix=prefix, allowed_fields=ALLOWED, apply_update=FakeApply())


def test_router_has_exactly_one_patch_route():
    router = build_metadata_router(prefix=PREFIX, allowed_fields=ALLOWED, apply_update=FakeApply())
    assert len(router.routes) == 1
    route = router.routes[0]
    assert route.path == PREFIX + '/{item_id}'
    assert set(route.methods) == {'PATCH'}


def test_router_uses_given_prefix():
    fake = FakeApply()
    client = make_client(fake, prefix='/v1/configs/metadata')
    response = patch(client, url='/v1/configs/metadata/cfg-9')
    assert response.status_code == 200
    assert fake.calls[0]['item_id'] == 'cfg-9'


def test_module_source_is_scoped_and_has_no_blanket_except():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert all(n.type is not None for n in handlers)
    assert not {'Exception', 'BaseException'} & {ast.unparse(n.type) for n in handlers}
    imported = {n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert 'controlplane.api.routes.modules.problem_detail' in imported


def test_modules_directory_is_declared_package():
    assert MODULE_PATH.parent.is_dir()
    assert (MODULE_PATH.parent / '__init__.py').is_file()
