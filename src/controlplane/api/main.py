"""Single FastAPI composition point for the local Control API."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
from urllib.parse import urlsplit
import uuid

from controlplane.api.routes.control import router as control_router
from controlplane.api.routes.session import router as session_router
from controlplane.api.sse.stream import SseStreamPresenter, router as sse_router
from controlplane.api.security import enforce_csrf, enforce_host
from controlplane.api.technical_details import record_internal_error
from controlplane.application.control_api.query_ports import ControlApiQueryService
from controlplane.application.session_security import BootstrapCapabilityRegistry, SessionSecurityService
from controlplane.application.technical_details import TechnicalDetailService
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.control_api_queries import PostgresControlQueries
from controlplane.infrastructure.db.session_security import PostgresSessionRepository
from controlplane.infrastructure.db.sse.postgres import PostgresSseReader
from controlplane.infrastructure.db.technical_details import PostgresTechnicalDetailRepository


def _problem(status: int, code: str, category: str, correlation_id: str,
             detail: str, technical_detail_ref: str | None = None) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank", "title": code.replace("_", " ").title(),
        "status": status, "detail": detail, "instance": correlation_id,
        "code": code, "category": category, "retryable": False,
        "correlation_id": correlation_id, "field_errors": {},
    }
    if technical_detail_ref is not None:
        body["technical_detail_ref"] = technical_detail_ref
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def _httpx_request(request: Request) -> httpx.Request:
    # Validators consume headers only. Never parse an attacker-controlled Host
    # as the temporary adapter URL before the Host policy has evaluated it.
    return httpx.Request(request.method, "https://localhost/", headers=request.scope["headers"])


def _valid_origin(request: Request, allowed: set[str]) -> bool:
    origins = request.headers.getlist("origin")
    if not origins:
        return request.method in {"GET", "HEAD", "OPTIONS"}
    if len(origins) != 1 or origins[0] not in allowed:
        return False
    try:
        parsed = urlsplit(origins[0])
        return (parsed.scheme == "https" and parsed.hostname in {"localhost", "127.0.0.1"}
                and parsed.port is not None and not parsed.path and not parsed.query
                and not parsed.fragment and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def create_app(*, manager: object | None = None,
               allowed_origins: set[str] | None = None,
               bootstrap_registry: BootstrapCapabilityRegistry | None = None) -> FastAPI:
    app = FastAPI(title="Control Plane", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.manager = manager
    app.state.allowed_origins = allowed_origins or set()
    app.state.bootstrap_registry = bootstrap_registry or BootstrapCapabilityRegistry()
    app.state.session_service = SessionSecurityService(PostgresSessionRepository)
    app.state.query_service = ControlApiQueryService(PostgresControlQueries)
    app.state.technical_detail_service = TechnicalDetailService(PostgresTechnicalDetailRepository)
    app.state.command_service = (
        compose_command_service(manager.unit_of_work) if manager is not None else None
    )
    app.state.sse_presenter = SseStreamPresenter(PostgresSseReader)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response: JSONResponse
        try:
            # Effective order is explicit, independent of decorator stacking.
            enforce_host(_httpx_request(request))
            if not _valid_origin(request, app.state.allowed_origins):
                raise PermissionError("invalid Origin")
            if manager is None:
                response = _problem(503, "CAPABILITY_UNAVAILABLE", "dependency",
                                    correlation_id, "Control API chưa được cấu hình.")
            else:
                bootstrap = request.url.path == "/v1/session/bootstrap"
                if not bootstrap:
                    with manager.borrow_connection() as connection:
                        request.state.identity = app.state.session_service.resolve(
                            connection=connection,
                            token=request.cookies.get("cp_session", ""),
                        )
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    enforce_csrf(_httpx_request(request))
                if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not bootstrap:
                    keys = request.headers.getlist("idempotency-key")
                    if len(keys) != 1 or not keys[0].strip():
                        raise ValueError("Idempotency-Key header required")
                    if request.method == "PUT":
                        matches = request.headers.getlist("if-match")
                        if len(matches) != 1 or not matches[0].strip():
                            raise ValueError("If-Match header required")
                response = await call_next(request)
        except PermissionError:
            response = _problem(403, "POLICY_VIOLATION", "security", correlation_id,
                                "Yêu cầu không được phép.")
        except LookupError:
            response = _problem(404, "NOT_FOUND", "validation", correlation_id,
                                "Không tìm thấy tài nguyên.")
        except RevisionConflictError:
            response = _problem(409, "REVISION_CONFLICT", "conflict", correlation_id,
                                "Phiên bản đã thay đổi.")
        except ValueError as exc:
            code = ("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
                    if str(exc) == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
                    else "VALIDATION_ERROR")
            status = 409 if code.startswith("IDEMPOTENCY") else 422
            response = _problem(status, code, "conflict" if status == 409 else "validation",
                                correlation_id, "Yêu cầu không hợp lệ.")
        except Exception as exc:
            detail_ref = None
            if manager is not None and hasattr(request.state, "identity"):
                try:
                    with manager.unit_of_work() as uow:
                        # Exception messages may contain opaque tokens or DSNs. Keep stack
                        # frames and type, never the untrusted message or locals.
                        safe_trace = "".join(traceback.format_list(
                            traceback.extract_tb(exc.__traceback__)
                        )) + type(exc).__name__
                        problem = record_internal_error(
                            workspace_id=request.state.identity["workspace_id"],
                            correlation_id=correlation_id,
                            error_type=type(exc).__name__, internal_detail=safe_trace,
                            connection=uow.connection,
                        )
                        detail_ref = str(problem["technical_detail_ref"])
                except Exception:
                    pass
            response = _problem(500, "INTERNAL_ERROR", "internal", correlation_id,
                                "Đã xảy ra lỗi nội bộ.", detail_ref)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    app.include_router(session_router)
    app.include_router(sse_router)
    app.include_router(control_router)
    return app
