"""Resolver for model-proposed refs (CT-AI-000): existence, workspace, revision and allowlist; typed schema is not enough."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

REASONS = ('unknown_ref', 'workspace_mismatch', 'revision_mismatch', 'not_allowlisted')
_FIELDS = ('workspace_id', 'ref_type', 'ref_id', 'revision_id')


@dataclass(frozen=True)
class ResourceRef:
    workspace_id: str
    ref_type: str
    ref_id: str
    revision_id: str

    def __post_init__(self) -> None:
        for name in _FIELDS:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be a non-empty string')


@dataclass(frozen=True)
class RefResolution:
    ref: ResourceRef | None
    reason: str | None

    def __post_init__(self) -> None:
        if (self.ref is None) == (self.reason is None):
            raise ValueError('exactly one of ref and reason must be set')
        if self.reason is not None and self.reason not in REASONS:
            raise ValueError(f'unknown reason: {self.reason}')

    @property
    def ok(self) -> bool:
        return self.ref is not None


class RefResolver:
    def __init__(self, *, workspace_id: str, allowed_refs: Iterable[ResourceRef], allowed_ref_types: Iterable[str]) -> None:
        if isinstance(allowed_ref_types, str):
            raise TypeError('allowed_ref_types must be an iterable of str, not a single str')
        refs = tuple(allowed_refs)
        index: dict[tuple[str, str], ResourceRef] = {}
        for item in refs:
            if not isinstance(item, ResourceRef):
                raise TypeError('allowed_refs must contain ResourceRef items')
            if item.workspace_id != workspace_id:
                raise ValueError('allowed_refs must belong to the resolver workspace')
            key = (item.ref_type, item.ref_id)
            if key in index:
                raise ValueError('duplicate allowed ref')
            index[key] = item
        self.workspace_id = workspace_id
        self.allowed_refs = refs
        self.allowed_ref_types = frozenset(allowed_ref_types)
        self._index = index

    def resolve(self, proposed: Mapping[str, object]) -> RefResolution:
        values = [proposed.get(name) if isinstance(proposed, Mapping) else None for name in _FIELDS]
        if not all(isinstance(value, str) and value for value in values):
            return RefResolution(None, 'unknown_ref')
        workspace_id, ref_type, ref_id, revision_id = values
        if workspace_id != self.workspace_id:
            return RefResolution(None, 'workspace_mismatch')
        if ref_type not in self.allowed_ref_types:
            return RefResolution(None, 'not_allowlisted')
        known = self._index.get((ref_type, ref_id))
        if known is None:
            return RefResolution(None, 'unknown_ref')
        if known.revision_id != revision_id:
            return RefResolution(None, 'revision_mismatch')
        return RefResolution(known, None)

    def resolve_all(self, proposed: Iterable[Mapping[str, object]]) -> tuple[RefResolution, ...]:
        return tuple(self.resolve(item) for item in proposed)
