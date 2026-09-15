"""Structural P5A configuration and secret-boundary contracts.

Behavior is intentionally deferred until the approved RED evidence exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ConfigRevisionStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class ConfigRevision:
    config_revision_id: str
    workspace_id: str
    scope_kind: str
    scope_key: str
    config_revision_number: int
    revision: int
    content_hash: str
    payload: dict[str, Any]
    status: ConfigRevisionStatus


@dataclass(frozen=True)
class SecretHandle:
    secret_handle_id: str
    workspace_id: str
    provider_ref: str
    account_ref: str
    alias_ref: str
    redacted_fingerprint_or_version: str
    validation_status: str
    revoked_at: str | None
    expires_at: str | None
    audit_ref: str


__all__ = ["ConfigRevision", "ConfigRevisionStatus", "SecretHandle"]
