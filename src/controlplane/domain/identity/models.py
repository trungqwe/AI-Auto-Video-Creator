"""Persistence-neutral identity records returned by M2-P1 repositories."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    name: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Actor:
    actor_id: str
    workspace_id: str
    actor_type: str
    display_name: str
    status: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class AuthSession:
    session_id: str
    workspace_id: str
    actor_id: str
    status: str
    created_at: datetime | None = None
    expires_at: datetime | None = None
