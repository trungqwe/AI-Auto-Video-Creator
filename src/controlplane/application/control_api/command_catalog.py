"""Danh mục đặc tả các lệnh Control API (CT-API-003..006).

COMMAND_SPECS gồm 14 lệnh đi qua cổng lệnh (trả 202 receipt).
UpdateSourceMetadata (CT-API-003) do router metadata H-09 phục vụ nên không nằm trong COMMAND_SPECS mà ghi ở METADATA_ROUTED_COMMANDS.
StartProductionBatch (POST /v1/batches) và PublishConfigurationRevision (PUT /v1/configs/{scope})
đã có sẵn ở control.py nên KHÔNG khai báo lại ở đây.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSpec:
    name: str
    method: str
    path: str
    requires_if_match: bool
    body_mode: str
    required_fields: frozenset[str]
    allowed_fields: frozenset[str]
    contract: str

    def __post_init__(self) -> None:
        if self.body_mode not in {"none", "required", "optional"}:
            raise ValueError(f"invalid body_mode: {self.body_mode}")
        if not self.required_fields.issubset(self.allowed_fields):
            raise ValueError("required_fields must be a subset of allowed_fields")


COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "RegisterSource",
        "POST",
        "/sources",
        False,
        "required",
        frozenset({"url"}),
        frozenset({"url", "name", "tier", "topics", "tags", "notes"}),
        "CT-API-003",
    ),
    CommandSpec(
        "RemoveSource",
        "DELETE",
        "/sources/{resource_id}",
        True,
        "none",
        frozenset(),
        frozenset(),
        "CT-API-003",
    ),
    CommandSpec(
        "RestoreSource",
        "POST",
        "/sources/{resource_id}/restore",
        True,
        "none",
        frozenset(),
        frozenset(),
        "CT-API-003",
    ),
    CommandSpec(
        "TestSource",
        "POST",
        "/sources/{resource_id}/test",
        False,
        "none",
        frozenset(),
        frozenset(),
        "CT-API-003",
    ),
    CommandSpec(
        "ImportVisualHook",
        "POST",
        "/hooks/visual",
        False,
        "required",
        frozenset({"artifact_ref"}),
        frozenset({"artifact_ref", "name", "tags", "description"}),
        "CT-API-004",
    ),
    CommandSpec(
        "ImportAudioHook",
        "POST",
        "/hooks/audio",
        False,
        "required",
        frozenset({"artifact_ref"}),
        frozenset({"artifact_ref", "name", "tags", "description"}),
        "CT-API-004",
    ),
    CommandSpec(
        "RunDebugStage",
        "POST",
        "/jobs/{resource_id}/debug-stage",
        False,
        "required",
        frozenset({"stage"}),
        frozenset({"stage"}),
        "CT-API-005",
    ),
    CommandSpec(
        "RetryStage",
        "POST",
        "/jobs/{resource_id}/retry-stage",
        False,
        "required",
        frozenset({"stage"}),
        frozenset({"stage"}),
        "CT-API-005",
    ),
    CommandSpec(
        "CreateNewVariant",
        "POST",
        "/jobs/{resource_id}/variants",
        False,
        "optional",
        frozenset(),
        frozenset({"reason"}),
        "CT-API-005",
    ),
    CommandSpec(
        "RegenerateFromStage",
        "POST",
        "/jobs/{resource_id}/regenerate",
        False,
        "required",
        frozenset({"stage"}),
        frozenset({"stage"}),
        "CT-API-005",
    ),
    CommandSpec(
        "UpdateSecret",
        "PUT",
        "/secrets/{resource_id}",
        True,
        "required",
        frozenset({"value"}),
        frozenset({"value"}),
        "CT-API-006",
    ),
    CommandSpec(
        "TestExternalAccount",
        "POST",
        "/external-accounts/{resource_id}/test",
        False,
        "none",
        frozenset(),
        frozenset(),
        "CT-API-006",
    ),
    CommandSpec(
        "EnableExternalAccount",
        "POST",
        "/external-accounts/{resource_id}/enable",
        True,
        "none",
        frozenset(),
        frozenset(),
        "CT-API-006",
    ),
    CommandSpec(
        "DisableExternalAccount",
        "POST",
        "/external-accounts/{resource_id}/disable",
        True,
        "none",
        frozenset(),
        frozenset(),
        "CT-API-006",
    ),
)


# UpdateSourceMetadata do router metadata H-09 phục vụ theo docs/implementation/convergence-ext-ui/plan.md:110:
# PATCH /v1/sources/{item_id} (route_catalog.METADATA_RESOURCES, allowlist tier, topic_tags, notes, enabled),
# trả 200 kèm giá trị đã commit thay vì 202 receipt. Không khai CommandSpec để route lệnh không che route metadata.
METADATA_ROUTED_COMMANDS: tuple[str, ...] = ("UpdateSourceMetadata",)
