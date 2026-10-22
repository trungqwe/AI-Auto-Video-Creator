"""Authenticated Control API route handlers; persistence stays behind services."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from controlplane.api.routes.modules.problem_detail import problem_response
from controlplane.api.routes.modules.read_only_listing import build_listing_router
from controlplane.application.control_api.command_catalog import COMMAND_SPECS, CommandSpec
from controlplane.application.control_api.errors import CapabilityUnavailableError
from controlplane.application.control_api.receipts import accepted_receipt
from controlplane.application.projections.list_query import ListQuery, ListQueryError, Page, parse_list_query

router = APIRouter(prefix="/v1")


def _identity(request: Request) -> dict[str, str]:
    return request.state.identity


_LIST_DEFAULT_LIMIT = 50
_LIST_MAX_LIMIT = 100


def _list_query(request: Request, *, sort: str, filters: tuple[str, ...]) -> ListQuery:
    params = {"direction": "desc", **dict(request.query_params)}
    try:
        return parse_list_query(
            params, allowed_sorts=(sort,), allowed_filters=filters,
            default_limit=_LIST_DEFAULT_LIMIT, max_limit=_LIST_MAX_LIMIT,
        )
    except ListQueryError as exc:
        raise ValueError(str(exc)) from exc


@router.get("/operations")
def operations(request: Request) -> dict[str, object]:
    query = _list_query(request, sort="accepted_at", filters=())
    with request.app.state.manager.borrow_connection() as connection:
        page = request.app.state.query_service.operations(
            connection=connection, workspace_id=_identity(request)["workspace_id"], query=query,
        )
    return {"items": list(page.items), "next_cursor": page.next_cursor}


@router.get("/operations/{operation_id}")
def operation(request: Request, operation_id: str) -> dict[str, object]:
    operation_id = str(uuid.UUID(operation_id))
    with request.app.state.manager.borrow_connection() as connection:
        result = request.app.state.query_service.operation(
            connection=connection, workspace_id=_identity(request)["workspace_id"],
            operation_id=operation_id,
        )
    if result is None:
        raise LookupError("operation not found")
    return result


@router.get("/batches")
def batches(request: Request) -> dict[str, object]:
    query = _list_query(request, sort="created_at", filters=("status",))
    with request.app.state.manager.borrow_connection() as connection:
        page = request.app.state.query_service.batches(
            connection=connection, workspace_id=_identity(request)["workspace_id"], query=query,
        )
    return {"items": list(page.items), "next_cursor": page.next_cursor}


@router.get("/batches/{batch_id}")
def batch(request: Request, batch_id: str) -> dict[str, object]:
    batch_id = str(uuid.UUID(batch_id))
    with request.app.state.manager.borrow_connection() as connection:
        result = request.app.state.query_service.batch(
            connection=connection, workspace_id=_identity(request)["workspace_id"],
            batch_id=batch_id,
        )
    if result is None:
        raise LookupError("batch not found")
    return result


@router.post("/batches")
async def start_batch(request: Request) -> JSONResponse:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValueError("batch payload must be an object")
    identity = _identity(request)
    receipt = request.app.state.command_service.start_batch(
        workspace_id=identity["workspace_id"], actor_id=identity["actor_id"],
        correlation_id=request.state.correlation_id,
        idempotency_key=request.headers["idempotency-key"], payload=payload,
    )
    return JSONResponse(jsonable_encoder(receipt), status_code=202)


@router.get("/jobs")
def jobs(request: Request) -> dict[str, object]:
    query = _list_query(request, sort="created_at", filters=("batch_id", "status"))
    with request.app.state.manager.borrow_connection() as connection:
        page = request.app.state.query_service.jobs(
            connection=connection, workspace_id=_identity(request)["workspace_id"], query=query,
        )
    return {"items": list(page.items), "next_cursor": page.next_cursor}


@router.get("/jobs/{job_id}")
def job(request: Request, job_id: str) -> dict[str, object]:
    job_id = str(uuid.UUID(job_id))
    with request.app.state.manager.borrow_connection() as connection:
        result = request.app.state.query_service.job(
            connection=connection, workspace_id=_identity(request)["workspace_id"],
            job_id=job_id,
        )
    if result is None:
        raise LookupError("job not found")
    return result


@router.get("/configs")
def configs(request: Request) -> dict[str, object]:
    query = _list_query(request, sort="created_at", filters=())
    with request.app.state.manager.borrow_connection() as connection:
        page = request.app.state.query_service.configs(
            connection=connection, workspace_id=_identity(request)["workspace_id"], query=query,
        )
    return {"items": list(page.items), "next_cursor": page.next_cursor}


@router.put("/configs/{scope}")
async def put_config(request: Request, scope: str) -> dict[str, object]:
    scope_kind, separator, scope_key = scope.partition(":")
    if not separator or not scope_kind or not scope_key:
        raise ValueError("scope must be kind:key")
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValueError("configuration payload must be an object")
    header = request.headers["if-match"]
    if not header.isdecimal():
        raise ValueError("If-Match must be an integer revision")
    identity = _identity(request)
    return request.app.state.command_service.put_config(
        workspace_id=identity["workspace_id"], actor_id=identity["actor_id"],
        idempotency_key=request.headers["idempotency-key"],
        scope_kind=scope_kind, scope_key=scope_key,
        expected_revision=int(header), payload=payload,
    )


@router.get("/errors/{detail_ref}")
def technical_detail(request: Request, detail_ref: str) -> dict[str, object]:
    detail_ref = str(uuid.UUID(detail_ref))
    identity = _identity(request)
    with request.app.state.manager.unit_of_work() as uow:
        return request.app.state.technical_detail_service.retrieve(
            connection=uow.connection, detail_ref=detail_ref,
            workspace_id=identity["workspace_id"], actor_id=identity["actor_id"],
            session_id=identity["session_id"],
            correlation_id=request.state.correlation_id,
        )

_RESOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_REVISION = re.compile(r"[0-9]{1,18}")


def _single_header(request: Request, name: str) -> str | None:
    values = request.headers.getlist(name)
    return values[0] if len(values) == 1 and values[0].strip() else None


async def _read_body(request: Request, spec: CommandSpec) -> tuple[dict[str, Any], str | None]:
    if spec.body_mode == "none":
        return ({}, None)
    raw = await request.body()
    if not raw.strip():
        return ({}, "Phải là JSON object không rỗng.") if spec.body_mode == "required" else ({}, None)
    try:
        payload = json.loads(raw)
    except ValueError:
        return ({}, "Phải là JSON object.")
    if not isinstance(payload, dict):
        return ({}, "Phải là JSON object.")
    if spec.body_mode == "required" and not payload:
        return ({}, "Phải là JSON object không rỗng.")
    return (payload, None)


def _register_command(spec: CommandSpec) -> None:
    async def run_command(request: Request) -> JSONResponse:
        identity = _identity(request)
        idempotency_key = _single_header(request, "idempotency-key")
        if_match = _single_header(request, "if-match")
        payload, body_error = await _read_body(request, spec)
        errors: dict[str, str] = {}
        if idempotency_key is None:
            errors["Idempotency-Key"] = "Bắt buộc, không rỗng và chỉ gửi một lần."
        expected_revision = None
        if spec.requires_if_match:
            if if_match is None or _REVISION.fullmatch(if_match) is None:
                errors["If-Match"] = "Bắt buộc, là số revision gồm chữ số ASCII."
            else:
                expected_revision = int(if_match)
        resource_id = request.path_params.get("resource_id")
        if resource_id is not None and _RESOURCE_ID.fullmatch(resource_id) is None:
            errors["resource_id"] = "Mã tài nguyên không hợp lệ."
        if body_error is not None:
            errors["body"] = body_error
        else:
            for name in sorted(spec.required_fields):
                val = payload.get(name)
                if not isinstance(val, str) or not val.strip():
                    errors[name] = "Bắt buộc, là chuỗi không rỗng."
        if errors:
            return problem_response(request, "VALIDATION_FAILED", field_errors=errors)
        offending = {k: "Trường không được phép." for k in payload if k not in spec.allowed_fields}
        if offending:
            return problem_response(request, "FORBIDDEN_FIELD", field_errors=offending)
        gateway = request.app.state.command_gateway
        if gateway is None:
            raise CapabilityUnavailableError(spec.name)
        receipt = await run_in_threadpool(
            gateway.submit,
            command_name=spec.name,
            workspace_id=identity["workspace_id"],
            actor_id=identity["actor_id"],
            correlation_id=request.state.correlation_id,
            idempotency_key=idempotency_key,
            resource_id=resource_id,
            expected_revision=expected_revision,
            payload=payload,
        )
        return JSONResponse(jsonable_encoder(accepted_receipt(receipt)), status_code=202)

    run_command.__name__ = "command_" + spec.name
    router.add_api_route(
        spec.path,
        run_command,
        methods=[spec.method],
        status_code=202,
        response_model=None,
        name=spec.name,
    )


for _spec in COMMAND_SPECS:
    _register_command(_spec)


@dataclass(frozen=True)
class QueryListing:
    prefix: str
    query_method: str
    allowed_sorts: tuple[str, ...]
    allowed_filters: frozenset[str]


# Only resources whose table and columns exist in migrations 0009..0018 are listed; the rest stay BLOCKED (see control_api_queries.BLOCKED_LIST_RESOURCES).
QUERY_LISTINGS: tuple[QueryListing, ...] = (
    QueryListing("/v1/stage-runs", "stage_runs", ("created_at",), frozenset({"job_id", "status"})),
)


def _query_fetch_page(method: str):
    def fetch_page(request: Request, workspace_id: str, query: ListQuery) -> Page:
        if "direction" not in request.query_params:
            query = replace(query, direction="desc")
        with request.app.state.manager.borrow_connection() as connection:
            return getattr(request.app.state.query_service, method)(
                connection=connection, workspace_id=workspace_id, query=query,
            )

    return fetch_page


def build_query_listing_routers() -> list[APIRouter]:
    return [
        build_listing_router(
            prefix=listing.prefix, fetch_page=_query_fetch_page(listing.query_method),
            allowed_sorts=listing.allowed_sorts, allowed_filters=listing.allowed_filters,
            default_limit=_LIST_DEFAULT_LIMIT, max_limit=_LIST_MAX_LIMIT,
        )
        for listing in QUERY_LISTINGS
    ]