"""Hook library with append-only revision history: ImportHook and UpdateHookMetadata (CT-HOOK-001/002, capability C)."""

import dataclasses

from catalog.domain.hooks import HookKind, HookRevision
from controlplane.domain.concurrency import RevisionConflictError


class HookHistory:
    """In-memory store of every hook revision; earlier revisions stay readable for job snapshots."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[HookRevision]] = {}

    def get(self, hook_id: str, revision: int) -> HookRevision:
        revisions = self._revisions.get(hook_id, [])
        if isinstance(revision, bool) or not isinstance(revision, int) or not (1 <= revision <= len(revisions)):
            raise KeyError((hook_id, revision))
        return revisions[revision - 1]

    def latest(self, hook_id: str) -> HookRevision:
        revisions = self._revisions.get(hook_id)
        if not revisions:
            raise KeyError(hook_id)
        return revisions[-1]

    def append(self, revision: HookRevision) -> None:
        """Store the next revision of a hook; a stored revision is never replaced."""
        current = len(self._revisions.get(revision.hook_id, ()))
        if revision.revision != current + 1:
            raise RevisionConflictError(current)
        self._revisions.setdefault(revision.hook_id, []).append(revision)


def import_hook(
    history: HookHistory,
    *,
    hook_id: str,
    kind: HookKind,
    artifact_version_ref: str,
    tags: tuple[str, ...] = (),
    description: str = "",
    note: str = "",
    enabled: bool = True,
    technical_metadata: tuple[tuple[str, str], ...] = (),
) -> HookRevision:
    """Import one visual or audio hook as revision 1 with user_imported provenance (CT-HOOK-001)."""
    hook = HookRevision(
        hook_id=hook_id,
        revision=1,
        kind=kind,
        artifact_version_ref=artifact_version_ref,
        tags=tags,
        description=description,
        note=note,
        enabled=enabled,
        technical_metadata=technical_metadata,
    )
    history.append(hook)
    return hook


def update_hook_metadata(
    history: HookHistory,
    hook_id: str,
    expected_revision: int,
    *,
    tags: tuple[str, ...] | None = None,
    description: str | None = None,
    note: str | None = None,
    enabled: bool | None = None,
) -> HookRevision:
    """Append revision + 1 with changed admin metadata; kind and artifact_version_ref never change (CT-HOOK-002)."""
    current = history.latest(hook_id)
    if expected_revision != current.revision:
        raise RevisionConflictError(current.revision)
    changes = {
        name: value
        for name, value in (("tags", tags), ("description", description), ("note", note), ("enabled", enabled))
        if value is not None
    }
    updated = dataclasses.replace(current, revision=current.revision + 1, **changes)
    history.append(updated)
    return updated
