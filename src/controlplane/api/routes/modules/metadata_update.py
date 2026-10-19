"""Router cập nhật metadata theo allowlist (H-09, CT-API-001, CT-API-003, CT-API-004, CT-API-009).

Route duy nhất PATCH {prefix}/{item_id}. Lệnh ghi thật do phân hệ chủ sở hữu cấp qua apply_update.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from controlplane.api.routes.modules.problem_detail import problem_response

FORBIDDEN_METADATA_FIELDS = frozenset({'article_body', 'body', 'script', 'script_text', 'event_relation', 'event_links', 'secret', 'secret_value'})
_REVISION_PATTERN = re.compile(r'[0-9]+')
_MAX_REVISION_DIGITS = 18


class RevisionConflictError(Exception):
    """apply_update ném khi expected_revision khác revision hiện tại."""


def _single_header(request: Request, name: str) -> str | None:
    values = request.headers.getlist(name)
    return values[0] if len(values) == 1 else None


def _parse_revision(value: str | None) -> int | None:
    if value is None or len(value) > _MAX_REVISION_DIGITS or _REVISION_PATTERN.fullmatch(value) is None:
        return None
    return int(value)


async def _read_changes(request: Request) -> dict[str, Any] | None:
    try:
        payload = await request.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) and payload else None


def build_metadata_router(*, prefix: str, allowed_fields: Iterable[str], apply_update: Callable[..., dict[str, Any]]) -> APIRouter:
    if not isinstance(prefix, str) or not prefix.startswith('/v1/'):
        raise ValueError('invalid_prefix')
    allowed = frozenset(allowed_fields)
    if allowed & FORBIDDEN_METADATA_FIELDS:
        raise ValueError('forbidden_field_allowed')
    router = APIRouter(prefix=prefix)

    async def update_metadata(request: Request, item_id: str) -> JSONResponse:
        idempotency_key = _single_header(request, 'idempotency-key')
        revision = _parse_revision(_single_header(request, 'if-match'))
        changes = await _read_changes(request)
        errors: dict[str, str] = {}
        if idempotency_key is None or not idempotency_key.strip():
            errors['Idempotency-Key'] = 'Bắt buộc, không rỗng và chỉ gửi một lần.'
        if revision is None:
            errors['If-Match'] = 'Bắt buộc, là số revision gồm chữ số ASCII.'
        if changes is None:
            errors['body'] = 'Phải là JSON object không rỗng.'
        if errors:
            return problem_response(request, 'VALIDATION_FAILED', field_errors=errors)
        offending = {key: 'Trường không được phép thay đổi.' for key in changes if key not in allowed}
        if offending:
            return problem_response(request, 'FORBIDDEN_FIELD', field_errors=offending)
        try:
            result = await run_in_threadpool(apply_update, request=request, item_id=item_id, expected_revision=revision, changes=changes, idempotency_key=idempotency_key)
        except RevisionConflictError:
            return problem_response(request, 'REVISION_CONFLICT')
        return JSONResponse(jsonable_encoder(result), status_code=200)

    router.add_api_route('/{item_id}', update_metadata, methods=['PATCH'])
    return router
