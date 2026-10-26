"""AI roles of the creative pipeline and their route keys (PW-D1, CT-AI-ROUTE-001).

route_key is the only place that translates a pipeline role into a key of the production profile ai.route_model_refs.
"""
from __future__ import annotations

from types import MappingProxyType

ROLE_ANALYSIS = 'content_analysis'
ROLE_ANGLES = 'story_angles'
ROLE_SCRIPT = 'script_generation'
ROLE_SELECTION = 'asset_selection'
ROLE_PLAN = 'production_plan'
ROLE_METADATA = 'output_metadata'
AI_ROLES = (
    ROLE_ANALYSIS,
    ROLE_ANGLES,
    ROLE_SCRIPT,
    ROLE_SELECTION,
    ROLE_PLAN,
    ROLE_METADATA,
)
PROMPT_SCOPE_KIND = 'prompt'

ROUTE_KEYS = MappingProxyType({
    ROLE_ANALYSIS: 'analysis',
    ROLE_ANGLES: 'angle',
    ROLE_SCRIPT: 'script',
    ROLE_SELECTION: 'selection',
    ROLE_PLAN: 'selection',
    ROLE_METADATA: 'metadata',
})


class UnknownRoleError(ValueError):
    """Raised when an unrecognized pipeline role is passed to route_key."""


def route_key(role: str) -> str:
    """Translate a creative pipeline role into its route key."""
    if not isinstance(role, str) or role not in ROUTE_KEYS:
        raise UnknownRoleError(f'unknown AI role: {role!r}')
    return ROUTE_KEYS[role]


__all__ = [
    'AI_ROLES',
    'PROMPT_SCOPE_KIND',
    'ROLE_ANALYSIS',
    'ROLE_ANGLES',
    'ROLE_METADATA',
    'ROLE_PLAN',
    'ROLE_SCRIPT',
    'ROLE_SELECTION',
    'ROUTE_KEYS',
    'UnknownRoleError',
    'route_key',
]
