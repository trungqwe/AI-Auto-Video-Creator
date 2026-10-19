"""Validators for BINDING-I-ARTIFACT-VERSION 1.0.0 (CT-STO-001); unknown additive fields are ignored."""
import re
from dataclasses import dataclass

BINDING_VERSION = "1.0.0"
MISSING_REQUIRED = "missing_required"
WRONG_TYPE = "wrong_type"

_SHA256_RE = re.compile(r"[0-9a-f]{64}")

REQUEST_FIELDS = (
    ("artifact_kind", "string", True),
    ("owner_resource_ref", "string", True),
    ("content_sha256", "sha256", True),
    ("size_bytes", "integer", True),
    ("media_type", "string", True),
    ("lineage_refs", "array", True),
    ("retention_class", "string", True),
    ("sensitivity_class", "string", True),
    ("intended_storage_class", "string", True),
    ("producer_operation_ref", "string", True),
)

RESULT_FIELDS = (
    ("artifact_id", "string", True),
    ("artifact_version_id", "string", True),
    ("matched_existing", "boolean", True),
    ("policy_decision", "string", True),
    ("required_operation", "string", False),
)


@dataclass(frozen=True)
class DeclareArtifactVersionRequest:
    artifact_kind: str
    owner_resource_ref: str
    content_sha256: str
    size_bytes: int
    media_type: str
    lineage_refs: list
    retention_class: str
    sensitivity_class: str
    intended_storage_class: str
    producer_operation_ref: str


@dataclass(frozen=True)
class DeclareArtifactVersionResult:
    artifact_id: str
    artifact_version_id: str
    matched_existing: bool
    policy_decision: str
    required_operation: str | None = None


def _has_type(value: object, binding_type: str) -> bool:
    if binding_type == "string":
        return isinstance(value, str)
    if binding_type == "sha256":
        return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None
    if binding_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if binding_type == "boolean":
        return isinstance(value, bool)
    if binding_type == "array":
        return isinstance(value, list)
    raise ValueError(f"Unknown binding type: {binding_type}")


def _validate(payload: object, fields: tuple[tuple[str, str, bool], ...]) -> list[dict]:
    if not isinstance(payload, dict):
        return [{"code": WRONG_TYPE, "field": "payload"}]
    errors: list[dict] = []
    for name, binding_type, required in fields:
        if name not in payload:
            if required:
                errors.append({"code": MISSING_REQUIRED, "field": name})
            continue
        if not _has_type(payload[name], binding_type):
            errors.append({"code": WRONG_TYPE, "field": name})
    return errors


def validate_declare_request(payload: dict) -> list[dict]:
    return _validate(payload, REQUEST_FIELDS)


def validate_declare_result(payload: dict) -> list[dict]:
    return _validate(payload, RESULT_FIELDS)


__all__ = [
    "BINDING_VERSION",
    "DeclareArtifactVersionRequest",
    "DeclareArtifactVersionResult",
    "MISSING_REQUIRED",
    "REQUEST_FIELDS",
    "RESULT_FIELDS",
    "WRONG_TYPE",
    "validate_declare_request",
    "validate_declare_result",
]
