"""Prompt source adapter reading published prompt revisions through a scope port (PW-D1, FR-CFG-007).

Reads published prompt revisions via a scope port without direct database access.
"""
from __future__ import annotations

from typing import Any, Protocol

from controlplane.domain.config_security import ConfigRevisionStatus
from creative.application.roles import AI_ROLES, PROMPT_SCOPE_KIND


class PromptScopePort(Protocol):
    def current(self, *, workspace_id: str, scope_kind: str, scope_key: str) -> Any | None:
        ...


class PromptNotSeeded(LookupError):
    """Raised when a required prompt revision is missing or not published."""


class ConfigPromptSource:
    def __init__(self, scope: PromptScopePort, workspace_id: str) -> None:
        self._scope = scope
        self._workspace_id = workspace_id

    def _current(self, role: str) -> Any:
        revision = self._scope.current(
            workspace_id=self._workspace_id,
            scope_kind=PROMPT_SCOPE_KIND,
            scope_key=role,
        )
        if revision is None or revision.status is not ConfigRevisionStatus.PUBLISHED:
            raise PromptNotSeeded(role)
        return revision

    def snapshot_refs(self) -> list[dict[str, str]]:
        return [
            {
                'ref_type': 'prompt',
                'ref_id': role,
                'revision_id': self._current(role).config_revision_id,
            }
            for role in AI_ROLES
        ]

    def instructions(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for role in AI_ROLES:
            rev = self._current(role)
            payload = rev.payload if isinstance(rev.payload, dict) else {}
            instr = payload.get('instructions')
            if not isinstance(instr, str) or not instr.strip():
                raise PromptNotSeeded(role)
            result[role] = instr
        return result


__all__ = [
    'ConfigPromptSource',
    'PromptNotSeeded',
    'PromptScopePort',
]
