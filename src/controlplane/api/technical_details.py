"""Unimplemented durable technical-detail boundary for P7A Behavioral RED."""

from __future__ import annotations

from typing import Any


def record_internal_error(
    *, workspace_id: str, correlation_id: str, error_type: str,
    internal_detail: str, connection: Any,
) -> dict[str, object]:
    """Eventually persist internal detail and return only a safe ProblemDetail."""
    raise NotImplementedError("P7A-003 technical-detail safety/storage unimplemented")


def retrieve_technical_detail(
    *, detail_ref: str, session_workspace_id: str, connection: Any,
) -> dict[str, object]:
    """Eventually authorize a workspace-scoped detail lookup."""
    raise NotImplementedError("P7A-003 technical-detail retrieval unimplemented")
