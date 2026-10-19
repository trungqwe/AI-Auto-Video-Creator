"""F-05: input DTOs and ports for ResolveRenderPackage (CT-RND-002).

F-local DTOs (CONV-F-07, CONV-F-14). Stdlib only, no I/O. ResolveInputs field names equal the 17 hashed RenderPackage fields;
None means the input is missing. input_artifacts holds assets that I already verified (built via ArtifactInfoPort by the caller).

coveredIds: CT-RND-002
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, kw_only=True)
class ResolvedAsset:
    """One exact artifact version; role says what it is for (voice, visual, ...) and is not copied into the package."""

    artifact_version_id: str
    sha256: str
    size_bytes: int
    media_type: str
    role: str


@dataclass(frozen=True, kw_only=True)
class LocalMaterialRef:
    """Opaque local reference issued by I for one materialized artifact version; never a free path string."""

    artifact_version_id: str
    local_ref: str


@dataclass(frozen=True, kw_only=True)
class ResolveInputs:
    """Locked refs for CT-RND-002; every field defaults to None (missing)."""

    production_snapshot_ref: str | None = None
    script_version_ref: str | None = None
    production_plan_ref: str | None = None
    preset_revision_ref: str | None = None
    voice_artifact_ref: str | None = None
    word_timing_ref: str | None = None
    output_metadata_revision: str | None = None
    output_profile_revision: str | None = None
    language_validation_refs: tuple[str, ...] | None = None
    input_artifacts: tuple[ResolvedAsset, ...] | None = None
    timeline: Mapping | None = None
    hook_placement: Mapping | None = None
    subtitle_config: Mapping | None = None
    mix_plan: Mapping | None = None
    allowed_fallbacks: tuple[Mapping, ...] | None = None
    materialization_manifest: tuple[LocalMaterialRef, ...] | None = None
    output_path_ref: str | None = None


@runtime_checkable
class PlanAssetPort(Protocol):
    """Asset refs (artifact_version_id) the ProductionPlan allows; None when the plan is unknown."""

    def asset_refs(self, production_plan_ref: str) -> Iterable[str] | None:
        ...


@runtime_checkable
class ArtifactInfoPort(Protocol):
    """Exact artifact facts by version id; None when unknown. Adapters implement it; no I/O here."""

    def get_asset(self, artifact_version_id: str) -> ResolvedAsset | None:
        ...
