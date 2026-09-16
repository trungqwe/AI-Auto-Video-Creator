"""Capability-authenticated local-launch session redemption."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/v1")


@router.post("/session/bootstrap")
def redeem_bootstrap(request: Request) -> JSONResponse:
    capability = request.headers.get("x-launch-capability")
    if not capability:
        raise PermissionError("bootstrap capability required")
    binding = request.app.state.bootstrap_registry.consume(capability)
    with request.app.state.manager.unit_of_work() as uow:
        session_id, token = request.app.state.session_service.create(
            connection=uow.connection, binding=binding,
        )
    response = JSONResponse({"session_id": session_id, "status": "active"})
    response.set_cookie("cp_session", token, httponly=True, secure=True,
                        samesite="strict", path="/")
    nonce = secrets.token_urlsafe(32)
    response.set_cookie("csrf_token", nonce, httponly=False, secure=True,
                        samesite="strict", path="/")
    return response
