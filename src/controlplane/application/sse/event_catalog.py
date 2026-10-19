"""Danh mục event kind và kế hoạch resync của luồng SSE (H-03, CT-API-008)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from types import MappingProxyType

EVENT_KIND_PATTERN = r"[A-Za-z0-9_.-]+"

BASE_STREAM_EVENT_KINDS: tuple[str, ...] = (
    "operation.accepted",
    "operation.running",
    "operation.succeeded",
    "operation.failed",
    "operation.changed",
    "production_batch.start_accepted",
    "job.created",
    "job.running",
    "job.completed",
    "job.failed",
)

SNAPSHOT_RESOURCES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "operation": ("operations",),
    "production_batch": ("batches",),
    "job": ("jobs",),
})
ALL_SNAPSHOT_RESOURCES: tuple[str, ...] = ("operations", "batches", "jobs")


def is_valid_event_kind(kind: object) -> bool:
    return isinstance(kind, str) and re.fullmatch(EVENT_KIND_PATTERN, kind, re.ASCII) is not None


class StreamKindRegistry:
    def __init__(self) -> None:
        self._owner_by_kind: dict[str, str] = {}

    def register(self, module_prefix: str, kinds: Iterable[str]) -> None:
        if not is_valid_event_kind(module_prefix) or "." in module_prefix:
            raise ValueError("invalid_event_kind")
        if isinstance(kinds, (str, bytes)):
            raise ValueError("invalid_event_kind")
        pending = tuple(kinds)
        lead = module_prefix + "."
        for kind in pending:
            if not is_valid_event_kind(kind):
                raise ValueError("invalid_event_kind")
            owner = self._owner_by_kind.get(kind)
            if owner is not None and owner != module_prefix:
                raise ValueError("kind_owned_by_other_prefix")
            if not kind.startswith(lead) or len(kind) == len(lead):
                raise ValueError("invalid_event_kind")
        for kind in pending:
            self._owner_by_kind[kind] = module_prefix

    def all_kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._owner_by_kind))


def default_registry() -> StreamKindRegistry:
    registry = StreamKindRegistry()
    for prefix in ("operation", "production_batch", "job"):
        registry.register(
            prefix,
            [kind for kind in BASE_STREAM_EVENT_KINDS if kind.startswith(prefix + ".")],
        )
    return registry


def snapshot_resources_for(resource_type: object) -> tuple[str, ...]:
    if isinstance(resource_type, str):
        known = SNAPSHOT_RESOURCES.get(resource_type)
        if known is not None:
            return known
    return ALL_SNAPSHOT_RESOURCES


def resync_targets(resource_types: Iterable[str]) -> tuple[str, ...]:
    if isinstance(resource_types, str):
        resource_types = (resource_types,)
    merged: dict[str, None] = {}
    for resource_type in resource_types:
        for resource in snapshot_resources_for(resource_type):
            merged.setdefault(resource)
    return tuple(merged)
