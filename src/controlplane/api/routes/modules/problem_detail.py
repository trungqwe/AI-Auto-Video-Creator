"""Builder ProblemDetail dùng chung cho route module (H-07, CT-API-010).

Bộ khóa khớp SseStreamPresenter._problem ở api/sse/stream.py. Trường detail luôn lấy từ
PROBLEM_SPECS, không bao giờ từ ngoại lệ.
"""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import Request
from fastapi.responses import JSONResponse

PROBLEM_SPECS: dict[str, tuple[int, str, bool, str]] = {
    'VALIDATION_FAILED': (422, 'validation', False, 'Dữ liệu gửi lên không hợp lệ.'),
    'FORBIDDEN_FIELD': (422, 'validation', False, 'Yêu cầu chứa trường không được phép thay đổi.'),
    'REVISION_CONFLICT': (409, 'conflict', False, 'Bản ghi đã được thay đổi bởi thao tác khác. Hãy tải lại rồi thử lại.'),
    'NOT_FOUND': (404, 'not_found', False, 'Không tìm thấy tài nguyên được yêu cầu.'),
}


def _checked_field_errors(field_errors: Mapping[str, str] | None) -> dict[str, str]:
    if field_errors is None:
        return {}
    if not isinstance(field_errors, Mapping):
        raise ValueError('field_errors_must_be_strings')
    for key, value in field_errors.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError('field_errors_must_be_strings')
    return dict(field_errors)


def problem_body(code: str, *, correlation_id: str, field_errors: Mapping[str, str] | None = None, technical_detail_ref: str | None = None) -> dict[str, Any]:
    if not isinstance(code, str) or code not in PROBLEM_SPECS:
        raise ValueError('unknown_problem_code')
    errors = _checked_field_errors(field_errors)
    status, category, retryable, detail = PROBLEM_SPECS[code]
    body: dict[str, Any] = {
        'type': 'about:blank', 'title': code.replace('_', ' ').title(),
        'status': status, 'detail': detail,
        'instance': correlation_id, 'code': code,
        'category': category, 'retryable': retryable,
        'correlation_id': correlation_id,
        'field_errors': errors,
    }
    if technical_detail_ref:
        body['technical_detail_ref'] = technical_detail_ref
    return body


def problem_response(request: Request, code: str, *, field_errors: Mapping[str, str] | None = None, technical_detail_ref: str | None = None) -> JSONResponse:
    body = problem_body(code, correlation_id=request.state.correlation_id, field_errors=field_errors, technical_detail_ref=technical_detail_ref)
    return JSONResponse(body, status_code=body['status'], media_type='application/problem+json')
