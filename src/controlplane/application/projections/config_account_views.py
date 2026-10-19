"""Pure config, account and job-config read models for CT-API-006, CT-API-009, CT-API-010 (H-06)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any

CONFIG_REVISION_FIELDS: tuple[str, ...] = (
    "config_revision_id",
    "scope_kind",
    "scope_key",
    "config_revision_number",
    "revision",
    "status",
    "content_hash",
    "created_at",
)
ACCOUNT_VIEW_FIELDS = (
    "account_ref",
    "provider",
    "account_label",
    "status",
    "updated_at",
)
ACCOUNT_STATUSES = (
    "enabled",
    "disabled",
    "degraded",
    "revoked",
    "invalid",
)
SECRET_FIELD_KEYS: frozenset[str] = frozenset({
    "secret",
    "secret_value",
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "private_key",
    "client_secret",
    "authorization",
    "credential",
})
SNAPSHOT_STATES = (
    "NOT_COMMITTED",
    "COMMITTED",
)
JOB_CONFIG_FIELDS = (
    "job_id",
    "snapshot_state",
    "configuration_revision_refs",
    "configuration_bundle_fingerprint",
)
FINGERPRINT_PATTERN: str = r"[0-9a-f]{64}"


@dataclass(frozen=True)
class ConfigRevisionView:
    config_revision_id: str
    scope_kind: str
    scope_key: str
    config_revision_number: Any
    revision: Any
    status: str
    content_hash: str
    created_at: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_revision_id": self.config_revision_id,
            "scope_kind": self.scope_kind,
            "scope_key": self.scope_key,
            "config_revision_number": self.config_revision_number,
            "revision": self.revision,
            "status": self.status,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ExternalAccountView:
    account_ref: str
    provider: str
    account_label: str
    status: str
    updated_at: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_ref": self.account_ref,
            "provider": self.provider,
            "account_label": self.account_label,
            "status": self.status,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class JobConfigRevisionView:
    job_id: str
    snapshot_state: str
    configuration_revision_refs: tuple[dict[str, Any], ...]
    configuration_bundle_fingerprint: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "snapshot_state": self.snapshot_state,
            "configuration_revision_refs": [dict(ref) for ref in self.configuration_revision_refs],
            "configuration_bundle_fingerprint": self.configuration_bundle_fingerprint,
        }


def build_config_revision_view(row: Mapping[str, Any]) -> ConfigRevisionView:
    if not isinstance(row, Mapping):
        raise ValueError("invalid_payload")
    if any(name not in row for name in CONFIG_REVISION_FIELDS):
        raise ValueError("missing_field")
    return ConfigRevisionView(**{name: row[name] for name in CONFIG_REVISION_FIELDS})


def _has_secret_key(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            (isinstance(key, str) and key.lower() in SECRET_FIELD_KEYS) or _has_secret_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_secret_key(item) for item in value)
    return False


def build_account_view(payload: Mapping[str, Any]) -> ExternalAccountView:
    if not isinstance(payload, Mapping):
        raise ValueError("invalid_payload")
    if _has_secret_key(payload):
        raise ValueError("secret_field_present")
    if any(name not in payload for name in ACCOUNT_VIEW_FIELDS):
        raise ValueError("missing_field")
    status = payload["status"]
    if not isinstance(status, str) or status not in ACCOUNT_STATUSES:
        raise ValueError("invalid_status")
    return ExternalAccountView(**{name: payload[name] for name in ACCOUNT_VIEW_FIELDS})


def build_job_config_revision_view(payload: Mapping[str, Any]) -> JobConfigRevisionView:
    if not isinstance(payload, Mapping):
        raise ValueError("invalid_payload")
    if any(name not in payload for name in JOB_CONFIG_FIELDS):
        raise ValueError("missing_field")
    state = payload["snapshot_state"]
    if not isinstance(state, str) or state not in SNAPSHOT_STATES:
        raise ValueError("invalid_snapshot_state")
    refs = payload["configuration_revision_refs"]
    if not isinstance(refs, (list, tuple)) or any(not isinstance(item, Mapping) for item in refs):
        raise ValueError("invalid_revision_refs")
    fingerprint = payload["configuration_bundle_fingerprint"]
    if state == "COMMITTED":
        if not refs:
            raise ValueError("missing_revision_refs")
        if not (isinstance(fingerprint, str) and re.fullmatch(FINGERPRINT_PATTERN, fingerprint)):
            raise ValueError("invalid_fingerprint")
    else:
        if fingerprint == "":
            fingerprint = None
        if fingerprint is not None and not (isinstance(fingerprint, str) and re.fullmatch(FINGERPRINT_PATTERN, fingerprint)):
            raise ValueError("invalid_fingerprint")
    return JobConfigRevisionView(
        job_id=payload["job_id"],
        snapshot_state=state,
        configuration_revision_refs=tuple(dict(item) for item in refs),
        configuration_bundle_fingerprint=fingerprint,
    )