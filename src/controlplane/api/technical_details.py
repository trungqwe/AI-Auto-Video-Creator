"""Presentation facade for durable, workspace-scoped technical details."""

from __future__ import annotations

from typing import Any

from controlplane.application.technical_details import TechnicalDetailService
from controlplane.infrastructure.db.technical_details import PostgresTechnicalDetailRepository
from controlplane.infrastructure.security.redaction import redact_text


_service = TechnicalDetailService(PostgresTechnicalDetailRepository)


def record_internal_error(
    *, workspace_id: str, correlation_id: str, error_type: str,
    internal_detail: str, connection: Any,
) -> dict[str, object]:
    """Persist a redacted diagnostic and return an opaque safe reference."""
    detail_ref = _service.record(
        connection=connection, workspace_id=workspace_id,
        correlation_id=correlation_id, error_type=error_type,
        redacted_detail=redact_text(internal_detail),
    )
    return {
        "type": "about:blank", "title": "Internal Server Error", "status": 500,
        "detail": "Đã xảy ra lỗi nội bộ.", "code": "INTERNAL_ERROR", "category": "internal",
        "retryable": False, "correlation_id": correlation_id,
        "technical_detail_ref": detail_ref,
    }


def retrieve_technical_detail(
    *, detail_ref: str, session_workspace_id: str, connection: Any,
) -> dict[str, object]:
    """Direct helper lookup; authenticated HTTP route supplies audit identity."""
    return _service.retrieve(connection=connection, detail_ref=detail_ref,
                             workspace_id=session_workspace_id)
