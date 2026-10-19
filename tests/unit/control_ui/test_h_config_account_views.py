"""Kiểm thử view cấu hình, tài khoản và revision hiệu lực của job (H-06).

coveredIds: CT-API-006, CT-API-009, CT-API-010, TST-INT-INV-004, TST-SEC-INV-012.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
from pathlib import Path
import re
from typing import Any

import pytest

from controlplane.application.projections.config_account_views import (
    ACCOUNT_STATUSES,
    SECRET_FIELD_KEYS,
    SNAPSHOT_STATES,
    ConfigRevisionView,
    ExternalAccountView,
    JobConfigRevisionView,
    build_account_view,
    build_config_revision_view,
    build_job_config_revision_view,
)

ROOT = Path(__file__).resolve().parents[3]
CONFIG_FIELDS = (
    "config_revision_id",
    "scope_kind",
    "scope_key",
    "config_revision_number",
    "revision",
    "status",
    "content_hash",
    "created_at",
)
ACCOUNT_FIELDS = (
    "account_ref",
    "provider",
    "account_label",
    "status",
    "updated_at",
)
JOB_FIELDS = (
    "job_id",
    "snapshot_state",
    "configuration_revision_refs",
    "configuration_bundle_fingerprint",
)
CONFIG_ROW = {
    "config_revision_id": "c-1",
    "scope_kind": "workspace",
    "scope_key": "ws-1",
    "config_revision_number": 3,
    "revision": 7,
    "status": "active",
    "content_hash": "h-1",
    "created_at": "2026-10-20T09:00:00+00:00",
}


def test_config_view_fields_match_configs_query_keys() -> None:
    src = (ROOT / "src/controlplane/infrastructure/db/control_api_queries.py").read_text(encoding="utf-8")
    body = src.split("def configs(")[1].split("\n    def ")[0]
    keys = re.findall(r'"([a-z_]+)": row\[\d+\]', body)
    assert len(keys) == 8
    assert set(keys) == {f.name for f in dataclasses.fields(ConfigRevisionView)}
    assert tuple(f.name for f in dataclasses.fields(ConfigRevisionView)) == CONFIG_FIELDS


def test_build_config_revision_view_keeps_values() -> None:
    view = build_config_revision_view(CONFIG_ROW)
    assert isinstance(view, ConfigRevisionView)
    assert view.to_dict() == CONFIG_ROW
    assert tuple(view.to_dict().keys()) == CONFIG_FIELDS


def test_build_config_revision_view_drops_unknown_keys() -> None:
    row = {**CONFIG_ROW, "workspace_id": "w", "extra": 1}
    snapshot = copy.deepcopy(row)
    result = build_config_revision_view(row)
    assert result.to_dict() == CONFIG_ROW
    assert "extra" not in result.to_dict()
    assert row == snapshot


@pytest.mark.parametrize("missing_field", CONFIG_FIELDS)
def test_build_config_revision_view_missing_field(missing_field: str) -> None:
    row = {k: v for k, v in CONFIG_ROW.items() if k != missing_field}
    with pytest.raises(ValueError, match="^missing_field$"):
        build_config_revision_view(row)


def test_config_view_is_frozen() -> None:
    view = ConfigRevisionView(**CONFIG_ROW)
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.status = "x"  # type: ignore[misc]


@pytest.mark.parametrize("payload", [None, [], "x"])
def test_config_builder_rejects_non_mapping(payload: Any) -> None:
    with pytest.raises(ValueError, match="^invalid_payload$"):
        build_config_revision_view(payload)

ACCOUNT = {
    "account_ref": "acc-1",
    "provider": "google_drive",
    "account_label": "Kênh chính",
    "status": "enabled",
    "updated_at": "2026-10-20T09:00:00Z",
}


def test_account_constants() -> None:
    assert ACCOUNT_STATUSES == ("enabled", "disabled", "degraded", "revoked", "invalid")
    assert all(status == status.lower() for status in ACCOUNT_STATUSES)
    assert SECRET_FIELD_KEYS == frozenset({
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


@pytest.mark.parametrize("status", ACCOUNT_STATUSES)
def test_build_account_view_accepts_every_status(status: str) -> None:
    view = build_account_view({**ACCOUNT, "status": status})
    assert isinstance(view, ExternalAccountView)
    assert view.status == status
    assert tuple(view.to_dict().keys()) == ACCOUNT_FIELDS


@pytest.mark.parametrize("bad_status", ["ENABLED", "Enabled", "active", "", None, 1])
def test_build_account_view_rejects_bad_status(bad_status: Any) -> None:
    with pytest.raises(ValueError, match="^invalid_status$"):
        build_account_view({**ACCOUNT, "status": bad_status})


@pytest.mark.parametrize("missing_field", ACCOUNT_FIELDS)
def test_build_account_view_missing_field(missing_field: str) -> None:
    payload = {k: v for k, v in ACCOUNT.items() if k != missing_field}
    with pytest.raises(ValueError, match="^missing_field$"):
        build_account_view(payload)


@pytest.mark.parametrize("key", sorted(SECRET_FIELD_KEYS))
def test_top_level_secret_key_rejected(key: str) -> None:
    for variant in (key, key.upper(), key.title()):
        with pytest.raises(ValueError, match="^secret_field_present$"):
            build_account_view({**ACCOUNT, variant: "x"})


@pytest.mark.parametrize("extra", [
    {"oauth": {"refresh_token": "x"}},
    {"meta": {"a": {"b": {"API_KEY": "x"}}}},
    {"history": [{"Password": "x"}]},
    {"items": [[{"client_secret": "x"}]]},
    {"items": ({"AUTHORIZATION": "x"},)},
])
def test_nested_secret_key_rejected(extra: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="^secret_field_present$"):
        build_account_view({**ACCOUNT, **extra})


def test_secret_error_does_not_leak_value() -> None:
    canary = "CANARY-SECRET-1"
    payload = {**ACCOUNT, "refresh_token": canary}
    with pytest.raises(ValueError) as excinfo:
        build_account_view(payload)
    assert str(excinfo.value) == "secret_field_present"
    assert canary not in str(excinfo.value)


def test_secret_check_precedes_other_validation() -> None:
    payload = {**ACCOUNT, "status": "ENABLED", "password": "x"}
    with pytest.raises(ValueError, match="^secret_field_present$"):
        build_account_view(payload)


def test_account_builder_drops_extra_keys_and_keeps_payload() -> None:
    payload = {**ACCOUNT, "note": "ok", "meta": {"region": "vn"}}
    snapshot = copy.deepcopy(payload)
    view = build_account_view(payload)
    assert view.to_dict() == ACCOUNT
    assert payload == snapshot


def test_account_view_dict_has_no_secret_keys() -> None:
    view = ExternalAccountView(**ACCOUNT)
    assert set(k.lower() for k in view.to_dict()).isdisjoint(SECRET_FIELD_KEYS)


@pytest.mark.parametrize("payload", [None, [], "x"])
def test_account_builder_rejects_non_mapping(payload: Any) -> None:
    with pytest.raises(ValueError, match="^invalid_payload$"):
        build_account_view(payload)

REFS = [{"config_revision_id": "c-1", "revision": 3}]
VALID_FP = "0123456789abcdef" * 4


def _job(**overrides: Any) -> dict[str, Any]:
    return {
        "job_id": "job-1",
        "snapshot_state": "COMMITTED",
        "configuration_revision_refs": REFS,
        "configuration_bundle_fingerprint": VALID_FP,
        **overrides,
    }


def test_job_constants() -> None:
    assert SNAPSHOT_STATES == ("NOT_COMMITTED", "COMMITTED")


def test_committed_job_with_refs_and_fingerprint_is_valid() -> None:
    view = build_job_config_revision_view(_job())
    assert isinstance(view, JobConfigRevisionView)
    assert view.configuration_revision_refs == tuple(REFS)
    assert view.configuration_bundle_fingerprint == VALID_FP
    assert tuple(view.to_dict().keys()) == JOB_FIELDS
    assert view.to_dict()["configuration_revision_refs"] == REFS
    assert isinstance(view.to_dict()["configuration_revision_refs"], list)


@pytest.mark.parametrize("empty_refs", [[], ()])
def test_committed_job_with_empty_refs_rejected(empty_refs: Any) -> None:
    with pytest.raises(ValueError, match="^missing_revision_refs$"):
        build_job_config_revision_view(_job(configuration_revision_refs=empty_refs))


@pytest.mark.parametrize("bad_fp", [
    "0123456789abcdef" * 3 + "0123456789abcde",
    VALID_FP + "0",
    VALID_FP.upper(),
    "g" * 64,
    None,
    "",
    123,
])
def test_committed_job_bad_fingerprint_rejected(bad_fp: Any) -> None:
    with pytest.raises(ValueError, match="^invalid_fingerprint$"):
        build_job_config_revision_view(_job(configuration_bundle_fingerprint=bad_fp))


def test_not_committed_job_may_be_empty() -> None:
    view1 = build_job_config_revision_view(_job(snapshot_state="NOT_COMMITTED", configuration_revision_refs=[], configuration_bundle_fingerprint=None))
    assert view1.configuration_revision_refs == ()
    assert view1.configuration_bundle_fingerprint is None

    view2 = build_job_config_revision_view(_job(snapshot_state="NOT_COMMITTED", configuration_revision_refs=[], configuration_bundle_fingerprint=""))
    assert view2.configuration_revision_refs == ()
    assert view2.configuration_bundle_fingerprint is None


def test_not_committed_job_with_bad_fingerprint_rejected() -> None:
    with pytest.raises(ValueError, match="^invalid_fingerprint$"):
        build_job_config_revision_view(_job(snapshot_state="NOT_COMMITTED", configuration_revision_refs=[], configuration_bundle_fingerprint=VALID_FP.upper()))


@pytest.mark.parametrize("bad_state", ["committed", "Committed", "PENDING", "", None])
def test_invalid_snapshot_state(bad_state: Any) -> None:
    with pytest.raises(ValueError, match="^invalid_snapshot_state$"):
        build_job_config_revision_view(_job(snapshot_state=bad_state))


@pytest.mark.parametrize("missing_field", JOB_FIELDS)
def test_job_missing_field(missing_field: str) -> None:
    payload = {k: v for k, v in _job().items() if k != missing_field}
    with pytest.raises(ValueError, match="^missing_field$"):
        build_job_config_revision_view(payload)


@pytest.mark.parametrize("refs", [None, "abc", {"a": 1}, ["c-1"], [1]])
@pytest.mark.parametrize("state", SNAPSHOT_STATES)
def test_invalid_revision_refs_rejected(refs: Any, state: str) -> None:
    with pytest.raises(ValueError, match="^invalid_revision_refs$"):
        build_job_config_revision_view(_job(snapshot_state=state, configuration_revision_refs=refs))


@pytest.mark.parametrize("payload", [None, [], "x"])
def test_job_builder_rejects_non_mapping(payload: Any) -> None:
    with pytest.raises(ValueError, match="^invalid_payload$"):
        build_job_config_revision_view(payload)


def test_job_field_names_match_binding() -> None:
    binding = json.loads((ROOT / "docs/parallel-delivery/bindings/b-d-production-snapshot.json").read_text(encoding="utf-8"))
    fields = {f["name"]: f for e in binding["entities"] for f in e["fields"]}
    assert "configuration_revision_refs" in fields and "configuration_bundle_fingerprint" in fields
    assert fields["configuration_revision_refs"]["type"] == "array"
    assert fields["configuration_bundle_fingerprint"]["type"] == "sha256"
    assert fields["configuration_revision_refs"]["required"] is True
    assert fields["configuration_bundle_fingerprint"]["required"] is True
    job_view_fields = tuple(f.name for f in dataclasses.fields(JobConfigRevisionView))
    assert "configuration_revision_refs" in job_view_fields
    assert "configuration_bundle_fingerprint" in job_view_fields


def test_module_is_pure_stdlib() -> None:
    code = (ROOT / "src/controlplane/application/projections/config_account_views.py").read_text(encoding="utf-8")
    tree = ast.parse(code)
    root_imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_imports.add(node.module.split(".")[0])
    assert root_imports.issubset({"__future__", "collections", "dataclasses", "re", "typing"})