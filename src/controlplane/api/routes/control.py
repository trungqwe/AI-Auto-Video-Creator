"""Authenticated Control API route handlers; persistence stays behind services."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import uuid

router = APIRouter(prefix="/v1")


def _identity(request: Request) -> dict[str, str]:
    return request.state.identity


@router.get("/operations")
def operations(request: Request) -> dict[str, object]:
    with request.app.state.manager.borrow_connection() as connection:
        items = request.app.state.query_service.operations(
            connection=connection, workspace_id=_identity(request)["workspace_id"],
        )
    return {"items": items, "next_cursor": None}


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
    with request.app.state.manager.borrow_connection() as connection:
        items = request.app.state.query_service.jobs(
            connection=connection, workspace_id=_identity(request)["workspace_id"],
        )
    return {"items": items, "next_cursor": None}


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
    with request.app.state.manager.borrow_connection() as connection:
        items = request.app.state.query_service.configs(
            connection=connection, workspace_id=_identity(request)["workspace_id"],
        )
    return {"items": items, "next_cursor": None}


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
