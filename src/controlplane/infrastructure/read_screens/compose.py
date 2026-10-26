"""Composes the ten read-only Dashboard list services over one connection scope (RS-12).

Building the mapping opens no connection; each service borrows one only while it serves a request. Only media exposes apply_update, and it raises CapabilityUnavailableError.
"""
from __future__ import annotations

from typing import Any

from controlplane.infrastructure.read_screens.accounts import AccountModuleService
from controlplane.infrastructure.read_screens.articles import ArticleModuleService
from controlplane.infrastructure.read_screens.artifacts import ArtifactModuleService
from controlplane.infrastructure.read_screens.cost import CostModuleService
from controlplane.infrastructure.read_screens.events import EventModuleService
from controlplane.infrastructure.read_screens.media import MediaModuleService
from controlplane.infrastructure.read_screens.scripts import ScriptModuleService
from controlplane.infrastructure.read_screens.sessions import SessionModuleService
from controlplane.infrastructure.read_screens.snapshots import SnapshotModuleService
from controlplane.infrastructure.read_screens.story_angles import StoryAngleModuleService


def compose_read_screens(manager: Any) -> dict[str, Any]:
    scope = manager.borrow_connection
    return {
        'articles': ArticleModuleService(scope),
        'events': EventModuleService(scope),
        'media': MediaModuleService(scope),
        'artifacts': ArtifactModuleService(scope),
        'snapshots': SnapshotModuleService(scope),
        'story-angles': StoryAngleModuleService(scope),
        'scripts': ScriptModuleService(scope),
        'sessions': SessionModuleService(scope),
        'accounts': AccountModuleService(scope),
        'cost': CostModuleService(scope),
    }
