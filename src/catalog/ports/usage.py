"""Usage ports owned by capability C: MediaUsage record and repository Protocol; PostgreSQL adapter arrives with CONV-C-01."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class UsageKind(StrEnum):
    production = "production"
    technical = "technical"


@dataclass(frozen=True, slots=True)
class MediaUsageRecord:
    """One usage row; only ``production`` rows count toward media reuse."""

    completion_id: str
    video_job_id: str
    media_asset_id: str
    role: str
    usage_kind: UsageKind
    rendition_ref: str | None = None
    artifact_version_ref: str | None = None
    selection_rationale: str | None = None

    def __post_init__(self) -> None:
        for name in ("completion_id", "video_job_id", "media_asset_id", "role"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.usage_kind, UsageKind):
            raise ValueError("usage_kind must be a UsageKind")
        for name in ("rendition_ref", "artifact_version_ref", "selection_rationale"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{name} must be None or a non-empty string")


class MediaUsageRepository(Protocol):
    def exists(self, completion_id: str, media_asset_id: str, role: str, usage_kind: UsageKind) -> bool: ...

    def add(self, record: MediaUsageRecord) -> None: ...
