"""Authenticated, bounded Server-Sent Events presentation."""

from __future__ import annotations

import asyncio
import json
import re
import time
from threading import BoundedSemaphore
from typing import Any, AsyncIterator, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from controlplane.application.sse.stream import SseStreamService, parse_cursor

router = APIRouter()

_PROBLEM_SPECS = {
    "INVALID_CURSOR": (400, "validation", False, "Cursor không hợp lệ."),
    "CURSOR_MISMATCH": (400, "validation", False, "Cursor không khớp."),
    "CURSOR_AHEAD": (409, "conflict", False, "Cursor vượt quá dữ liệu hiện có."),
    "UNKNOWN_CURSOR": (409, "conflict", False, "Cursor không tồn tại trong workspace."),
    "RATE_LIMITED": (429, "capacity", True, "Luồng SSE tạm thời đã đạt giới hạn kết nối đồng thời."),
}


class SseStreamPresenter:
    def __init__(self, reader_factory: Callable[[Any], Any]) -> None:
        self._reader_factory = reader_factory
        self._clients = BoundedSemaphore(16)
        self._polls = BoundedSemaphore(3)

    @staticmethod
    def _problem(request: Request, status: int, code: str) -> JSONResponse:
        expected_status, category, retryable, detail = _PROBLEM_SPECS[code]
        if status != expected_status:
            raise ValueError("SSE ProblemDetail status mismatch")
        correlation_id = request.state.correlation_id
        response = JSONResponse(
            {"type": "about:blank", "title": code.replace("_", " ").title(),
             "status": status, "detail": detail,
             "instance": correlation_id, "code": code,
             "category": category, "retryable": retryable,
             "correlation_id": correlation_id,
             "field_errors": {}},
            status_code=status, media_type="application/problem+json",
        )
        return response

    @staticmethod
    def _event_frame(row: Any) -> str:
        if re.fullmatch(r"[A-Za-z0-9_.-]+", row.event_kind, re.ASCII) is None:
            raise ValueError("invalid event kind")
        payload = {
            "cursor": str(row.stream_event_id),
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "resource_revision": row.resource_revision,
            "event_kind": row.event_kind,
            "occurred_at": row.occurred_at.isoformat(),
            "recorded_at": row.recorded_at.isoformat(),
            "summary": row.summary,
            "correlation_id": row.correlation_id,
        }
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        return f"id: {row.stream_event_id}\nevent: {row.event_kind}\ndata: {data}\n\n"

    def frames(self, *, workspace_id: str, connection: Any,
               request: Request) -> StreamingResponse | JSONResponse:
        queries = request.query_params.getlist("cursor")
        headers = request.headers.getlist("last-event-id")
        if len(queries) > 1 or len(headers) > 1:
            return self._problem(request, 400, "INVALID_CURSOR")
        try:
            query_cursor = parse_cursor(queries[0]) if queries else None
            header_cursor = parse_cursor(headers[0]) if headers else None
        except ValueError:
            return self._problem(request, 400, "INVALID_CURSOR")
        if query_cursor is not None and header_cursor is not None and query_cursor != header_cursor:
            return self._problem(request, 400, "CURSOR_MISMATCH")
        cursor = query_cursor if query_cursor is not None else header_cursor
        service = SseStreamService(self._reader_factory(connection))
        if cursor is None:
            cursor = service.initial_baseline(workspace_id=workspace_id)
            classification = "valid"
        else:
            classification = service.classify_cursor(workspace_id=workspace_id, cursor=cursor)
        if classification == "ahead":
            return self._problem(request, 409, "CURSOR_AHEAD")
        if classification == "unknown":
            return self._problem(request, 409, "UNKNOWN_CURSOR")
        if classification == "invalid":
            return self._problem(request, 400, "INVALID_CURSOR")
        if not self._clients.acquire(blocking=False):
            return self._problem(request, 429, "RATE_LIMITED")
        token = request.cookies.get("cp_session", "")
        manager = request.app.state.manager
        session_service = request.app.state.session_service

        def poll(after: int) -> list[Any]:
            with manager.borrow_connection() as borrowed:
                return SseStreamService(self._reader_factory(borrowed)).replay_after(
                    workspace_id=workspace_id, cursor=after,
                )

        def revalidate() -> bool:
            try:
                with manager.borrow_connection() as borrowed:
                    current = session_service.resolve(connection=borrowed, token=token)
                return current["workspace_id"] == workspace_id
            except PermissionError:
                return False

        async def stream_frames() -> AsyncIterator[str]:
            nonlocal cursor
            last_heartbeat = time.monotonic()
            last_validation = time.monotonic()
            try:
                if classification == "resync_required":
                    yield ('event: resync_required\n'
                           'data: {"resync_required":true,"reason":"cursor_expired",'
                           '"action":"query_resource_snapshots"}\n\n')
                    return
                yield "retry: 1000\n\n"
                while not await request.is_disconnected():
                    now = time.monotonic()
                    if now - last_validation >= 30:
                        if not await asyncio.to_thread(revalidate):
                            return
                        last_validation = now
                    if self._polls.acquire(blocking=False):
                        try:
                            rows = await asyncio.to_thread(poll, cursor)
                        finally:
                            self._polls.release()
                        for row in rows:
                            cursor = row.stream_event_id
                            yield self._event_frame(row)
                            last_heartbeat = time.monotonic()
                    else:
                        await asyncio.sleep(0.1)
                        continue
                    if time.monotonic() - last_heartbeat >= 15:
                        yield ": keepalive\n\n"
                        last_heartbeat = time.monotonic()
                    await asyncio.sleep(1)
            finally:
                self._clients.release()

        return StreamingResponse(
            stream_frames(), media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )


@router.get("/v1/operations/stream")
def stream(request: Request) -> object:
    identity = request.state.identity
    with request.app.state.manager.borrow_connection() as connection:
        return request.app.state.sse_presenter.frames(
            workspace_id=identity["workspace_id"], connection=connection, request=request,
        )
