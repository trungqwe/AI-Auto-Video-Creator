"""H-07: builder ProblemDetail cho route module (CT-API-010, QR-UX-004).

coveredIds: CT-API-001, CT-API-010, QR-UX-004
"""
import ast
import inspect
import json
import pathlib
import re

import pytest
from starlette.requests import Request

from controlplane.api.routes.modules.problem_detail import PROBLEM_SPECS, problem_body, problem_response

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'api' / 'routes' / 'modules' / 'problem_detail.py'
STREAM_PATH = ROOT / 'src' / 'controlplane' / 'api' / 'sse' / 'stream.py'
CORRELATION_ID = 'corr-h07-0001'
EXPECTED = {
    'VALIDATION_FAILED': (422, 'validation', False, 'Dữ liệu gửi lên không hợp lệ.'),
    'FORBIDDEN_FIELD': (422, 'validation', False, 'Yêu cầu chứa trường không được phép thay đổi.'),
    'REVISION_CONFLICT': (409, 'conflict', False, 'Bản ghi đã được thay đổi bởi thao tác khác. Hãy tải lại rồi thử lại.'),
    'NOT_FOUND': (404, 'not_found', False, 'Không tìm thấy tài nguyên được yêu cầu.'),
}
CODES = list(EXPECTED)
BASE_KEYS = ['type', 'title', 'status', 'detail', 'instance', 'code', 'category', 'retryable', 'correlation_id', 'field_errors']


def make_request(state=None):
    return Request({'type': 'http', 'state': {} if state is None else state})


def test_specs_cover_exactly_four_codes_with_expected_values():
    assert isinstance(PROBLEM_SPECS, dict)
    assert list(PROBLEM_SPECS) == CODES
    for code in CODES:
        assert tuple(PROBLEM_SPECS[code]) == EXPECTED[code]
        assert PROBLEM_SPECS[code][2] is False


@pytest.mark.parametrize('code', CODES)
def test_problem_body_has_exact_ten_keys(code):
    status, category, retryable, detail = EXPECTED[code]
    body = problem_body(code, correlation_id=CORRELATION_ID)
    assert list(body) == BASE_KEYS
    assert len(body) == 10
    assert body == {'type': 'about:blank', 'title': code.replace('_', ' ').title(), 'status': status, 'detail': detail, 'instance': CORRELATION_ID, 'code': code, 'category': category, 'retryable': retryable, 'correlation_id': CORRELATION_ID, 'field_errors': {}}
    assert body['retryable'] is False
    assert body['instance'] == CORRELATION_ID


@pytest.mark.parametrize('code', CODES)
def test_technical_detail_ref_added_only_when_present(code):
    with_ref = problem_body(code, correlation_id=CORRELATION_ID, technical_detail_ref='td-0001')
    assert list(with_ref) == BASE_KEYS + ['technical_detail_ref']
    assert len(with_ref) == 11
    assert with_ref['technical_detail_ref'] == 'td-0001'
    for ref in (None, ''):
        assert 'technical_detail_ref' not in problem_body(code, correlation_id=CORRELATION_ID, technical_detail_ref=ref)


def test_field_errors_are_copied_and_default_is_fresh():
    source = {'title': 'Bắt buộc', 'script': 'Không được để trống'}
    body = problem_body('VALIDATION_FAILED', correlation_id=CORRELATION_ID, field_errors=source)
    assert body['field_errors'] == source
    assert body['field_errors'] is not source
    body['field_errors']['x'] = 'y'
    assert 'x' not in source
    first = problem_body('NOT_FOUND', correlation_id=CORRELATION_ID)
    first['field_errors']['leak'] = 'v'
    assert problem_body('NOT_FOUND', correlation_id=CORRELATION_ID)['field_errors'] == {}


@pytest.mark.parametrize('bad', [{'a': {'b': 1}}, {'a': 1}, {'a': None}, {'a': ['x']}, {'a': b'x'}, {1: 'x'}, 'abc', [('a', 'b')]])
def test_non_string_field_errors_are_rejected(bad):
    with pytest.raises(ValueError) as excinfo:
        problem_body('VALIDATION_FAILED', correlation_id=CORRELATION_ID, field_errors=bad)
    assert excinfo.value.args == ('field_errors_must_be_strings',)


@pytest.mark.parametrize('code', ['X', '', 'validation_failed', 'INVALID_CURSOR', None, 404])
def test_unknown_code_is_rejected(code):
    with pytest.raises(ValueError) as excinfo:
        problem_body(code, correlation_id=CORRELATION_ID)
    assert excinfo.value.args == ('unknown_problem_code',)
    with pytest.raises(ValueError) as excinfo:
        problem_response(make_request({'correlation_id': CORRELATION_ID}), code)
    assert excinfo.value.args == ('unknown_problem_code',)


def test_unknown_code_is_checked_before_field_errors():
    with pytest.raises(ValueError) as excinfo:
        problem_body('X', correlation_id=CORRELATION_ID, field_errors={'a': {'b': 1}})
    assert excinfo.value.args == ('unknown_problem_code',)


@pytest.mark.parametrize('code', CODES)
def test_problem_response_uses_state_correlation_id_and_table(code):
    status = EXPECTED[code][0]
    response = problem_response(make_request({'correlation_id': CORRELATION_ID}), code)
    assert response.status_code == status
    assert response.media_type == 'application/problem+json'
    assert response.headers['content-type'].split(';')[0] == 'application/problem+json'
    payload = json.loads(response.body.decode('utf-8'))
    assert payload == problem_body(code, correlation_id=CORRELATION_ID)
    assert payload['instance'] == payload['correlation_id'] == CORRELATION_ID
    assert payload['status'] == status


def test_problem_response_passes_field_errors_and_ref():
    response = problem_response(make_request({'correlation_id': CORRELATION_ID}), 'VALIDATION_FAILED', field_errors={'title': 'Bắt buộc'}, technical_detail_ref='td-0002')
    payload = json.loads(response.body.decode('utf-8'))
    assert payload['field_errors'] == {'title': 'Bắt buộc'}
    assert payload['technical_detail_ref'] == 'td-0002'
    assert len(payload) == 11


def test_problem_response_requires_correlation_id_in_state():
    with pytest.raises(AttributeError):
        problem_response(make_request(), 'NOT_FOUND')


def test_problem_response_rejects_non_string_field_errors():
    with pytest.raises(ValueError) as excinfo:
        problem_response(make_request({'correlation_id': CORRELATION_ID}), 'VALIDATION_FAILED', field_errors={'a': {'b': 1}})
    assert excinfo.value.args == ('field_errors_must_be_strings',)


def test_response_body_has_no_traceback():
    request = make_request({'correlation_id': CORRELATION_ID})
    for code in CODES:
        text = problem_response(request, code, field_errors={'a': 'x'}, technical_detail_ref='td-0003').body.decode('utf-8')
        assert 'Traceback' not in text


def test_signatures_cannot_take_detail_from_exception():
    keyword_only = inspect.Parameter.KEYWORD_ONLY
    body_params = inspect.signature(problem_body).parameters
    assert list(body_params) == ['code', 'correlation_id', 'field_errors', 'technical_detail_ref']
    assert body_params['correlation_id'].kind is keyword_only
    assert body_params['correlation_id'].default is inspect.Parameter.empty
    response_params = inspect.signature(problem_response).parameters
    assert list(response_params) == ['request', 'code', 'field_errors', 'technical_detail_ref']
    for name in ('field_errors', 'technical_detail_ref'):
        assert body_params[name].kind is keyword_only and body_params[name].default is None
        assert response_params[name].kind is keyword_only and response_params[name].default is None


def test_module_source_has_no_exception_or_traceback_handling():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    imported = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {(n.module or '').split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert 'traceback' not in imported
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert 'str' not in called


def test_modules_directory_has_no_init_file():
    assert MODULE_PATH.parent.is_dir()
    assert not (MODULE_PATH.parent / '__init__.py').exists()


def test_key_set_matches_sse_presenter_problem():
    source = STREAM_PATH.read_text(encoding='utf-8')
    match = re.search(r'def _problem\(.*?status_code=status', source, re.DOTALL)
    assert match is not None
    segment = match.group(0)
    keys = re.findall(r'"([a-z_]+)":', segment)
    assert keys == BASE_KEYS
    assert '"type": "about:blank"' in segment
    assert 'code.replace("_", " ").title()' in segment
    assert '"field_errors": {}' in segment
    assert 'media_type="application/problem+json"' in source
    assert list(problem_body('NOT_FOUND', correlation_id=CORRELATION_ID)) == keys
