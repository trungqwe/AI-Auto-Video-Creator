"""Visual and audio hook revisions (CT-HOOK-001, CT-HOOK-002, capability C)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from catalog.domain.identity import ProvenanceRelation


class HookKind(StrEnum):
    VISUAL_HOOK = "visual_hook"
    AUDIO_HOOK = "audio_hook"


@dataclass(frozen=True, slots=True)
class HookRevision:
    """One immutable revision of a user-imported hook; visual and audio hooks carry no pairing field."""

    hook_id: str
    revision: int
    kind: HookKind
    artifact_version_ref: str
    tags: tuple[str, ...]
    description: str
    note: str
    enabled: bool
    technical_metadata: tuple[tuple[str, str], ...]
    provenance: ProvenanceRelation = ProvenanceRelation.USER_IMPORTED

    def __post_init__(self) -> None:
        if not isinstance(self.hook_id, str) or not self.hook_id:
            raise ValueError("hook_id must be a non-empty string")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.kind, HookKind):
            raise ValueError("kind must be a HookKind")
        if not isinstance(self.artifact_version_ref, str) or not self.artifact_version_ref:
            raise ValueError("artifact_version_ref must be a non-empty string")
        if not isinstance(self.tags, tuple) or not all(isinstance(t, str) for t in self.tags):
            raise ValueError("tags must be a tuple of strings")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        if not isinstance(self.note, str):
            raise ValueError("note must be a string")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a bool")
        if not isinstance(self.technical_metadata, tuple) or not all(
            isinstance(pair, tuple) and len(pair) == 2 and isinstance(pair[0], str) and isinstance(pair[1], str)
            for pair in self.technical_metadata
        ):
            raise ValueError("technical_metadata must be a tuple of 2-tuples of strings")
        if self.provenance is not ProvenanceRelation.USER_IMPORTED:
            raise ValueError("hook provenance is always user_imported")


def format_hook_timestamp(moment: datetime) -> str:
    """Format an aware datetime as YYYY-MM-DDTHH:MM:SS.ffffffZ in UTC; naive values are rejected."""
    if not isinstance(moment, datetime) or moment.utcoffset() is None:
        raise ValueError("moment must be a timezone-aware datetime")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True, slots=True)
class HookHead:
    """Latest revision of one hook with the UTC time of its last write (YYYY-MM-DDTHH:MM:SS.ffffffZ)."""

    revision: HookRevision
    updated_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.revision, HookRevision):
            raise ValueError("revision must be a HookRevision")
        if not isinstance(self.updated_at, str) or not self.updated_at:
            raise ValueError("updated_at must be a non-empty string")
