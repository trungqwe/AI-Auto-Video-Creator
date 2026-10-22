"""Kiểm thử tích hợp cho CP-4-WIRING (composition root, module routers, control command routes)."""

from __future__ import annotations

import ast
from contextlib import contextmanager
import importlib.util
import json
import logging
from pathlib import Path
import re
import uuid

from fastapi.routing import _iter_routes_with_context
from fastapi.testclient import TestClient
import pytest

from controlplane.api.main import create_app
from controlplane.api.routes.modules.metadata_update import (
    FORBIDDEN_METADATA_FIELDS,
    RevisionConflictError as ModuleRevisionConflict,
)
import controlplane.application.control_api.command_catalog as command_catalog
import controlplane.application.control_api.route_catalog as route_catalog
from controlplane.application.projections.list_query import Page
from controlplane.domain.concurrency import RevisionConflictError

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = "00000000-0000-0000-0000-0000000004a1"
ACTOR = "00000000-0000-0000-0000-0000000004a2"
SESSION = "00000000-0000-0000-0000-0000000004a3"
ORIGIN = "https://localhost:8443"
SECRET = "cp4-secret-value-do-not-leak"
STORED_REVISION = 3


class FakeUow:
    def __init__(self) -> None:
        self.connection = object()

    def __enter__(self) -> FakeUow:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeManager:
    def unit_of_work(self) -> FakeUow:
        return FakeUow()

    @contextmanager
    def borrow_connection(self):
        yield object()


class FakeSessionService:
    def resolve(self, *, connection: object, token: str) -> dict[str, str]:
        if token == "valid":
            return {
                "workspace_id": WORKSPACE,
                "actor_id": ACTOR,
                "session_id": SESSION,
            }
        raise PermissionError("invalid session token")


class FakeGateway:
    """Service giả của cổng lệnh Control API."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.records: dict[tuple[str, str, str], tuple[str, dict[str, object]]] = {}
        self.extra: dict[str, object] = {}

    def submit(
        self,
        *,
        command_name: str,
        workspace_id: str,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        resource_id: str | None,
        expected_revision: int | None,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self.calls.append({
            "command_name": command_name,
            "workspace_id": workspace_id,
            "actor_id": actor_id,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "resource_id": resource_id,
            "expected_revision": expected_revision,
            "payload": payload,
        })
        if expected_revision is not None and expected_revision != STORED_REVISION:
            raise RevisionConflictError(STORED_REVISION)
        digest = json.dumps([command_name, resource_id, expected_revision, payload], sort_keys=True)
        key = (workspace_id, command_name, idempotency_key)
        if key in self.records:
            old_digest, old_receipt = self.records[key]
            if old_digest != digest:
                raise ValueError("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD")
            receipt = dict(old_receipt, disposition="duplicate")
            return receipt
        receipt = {
            "receipt_id": str(uuid.uuid4()),
            "command_id": str(uuid.uuid4()),
            "disposition": "accepted",
            "operation_id": str(uuid.uuid4()),
            "resource_ref": {"kind": command_name, "id": resource_id},
            "accepted_at": "2026-10-22T00:00:00Z",
            "current_revision": STORED_REVISION,
        }
        receipt.update(self.extra)
        self.records[key] = (digest, receipt)
        return receipt


class RecordingModuleService:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[object, ...]] = []

    def fetch_page(self, request: object, workspace_id: str, query: object) -> Page:
        self.calls.append(("fetch_page", workspace_id, query))
        return Page(items=({"id": "x1", "name": self.name},), next_cursor="cur-1")

    def fetch_one(self, request: object, workspace_id: str, item_id: str) -> dict[str, str] | None:
        self.calls.append(("fetch_one", workspace_id, item_id))
        if item_id == "missing":
            return None
        return {"id": item_id, "name": self.name}

    def apply_update(
        self,
        *,
        request: object,
        item_id: str,
        expected_revision: int,
        changes: dict[str, object],
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("apply_update", item_id, expected_revision, changes))
        if expected_revision != STORED_REVISION:
            raise ModuleRevisionConflict(f"revision mismatch: {expected_revision}")
        return {
            "status": "accepted",
            "disposition": "accepted",
            "resource_ref": {"kind": self.name, "id": item_id},
            "current_revision": expected_revision + 1,
        }


class FakeCommandService:
    def start_batch(self, **kwargs: object) -> dict[str, object]:
        return {"receipt_id": str(uuid.uuid4()), "disposition": "accepted"}

    def put_config(self, **kwargs: object) -> dict[str, object]:
        if kwargs.get("expected_revision") != STORED_REVISION:
            raise RevisionConflictError(STORED_REVISION)
        return {"receipt_id": str(uuid.uuid4()), "disposition": "accepted"}


def make_app(
    gateway: object | None = None,
    module_services: dict[str, object] | None = None,
    command_service: object | None = None,
) -> object:
    app = create_app(manager=FakeManager(), allowed_origins={ORIGIN})
    app.state.session_service = FakeSessionService()
    app.state.command_gateway = gateway
    app.state.module_services = (
        module_services if module_services is not None
        else {n: RecordingModuleService(n) for n in ("sources", "hooks", "media")}
    )
    app.state.command_service = command_service
    return app


def make_client(app: object) -> TestClient:
    return TestClient(app, base_url=ORIGIN, raise_server_exceptions=False)


def mutation_headers(key: str | None = "key-1", if_match: str | None = None) -> dict[str, str]:
    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": "t",
        "Cookie": "csrf_token=t; cp_session=valid",
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    if if_match is not None:
        headers["If-Match"] = str(if_match)
    return headers


READ_HEADERS = {"Cookie": "cp_session=valid"}


def send(client: TestClient, method: str, path: str, body: object | None, headers: dict[str, str]):
    if body is None:
        return client.request(method, path, headers=headers)
    return client.request(method, path, headers=headers, json=body)


COMMANDS = [
    ("RegisterSource", "POST", "/v1/sources", False, {"url": "https://example.org/feed.xml", "name": "Example"}),
    ("RemoveSource", "DELETE", "/v1/sources/src-1", True, None),
    ("RestoreSource", "POST", "/v1/sources/src-1/restore", True, None),
    ("TestSource", "POST", "/v1/sources/src-1/test", False, None),
    ("ImportVisualHook", "POST", "/v1/hooks/visual", False, {"artifact_ref": "artifact-1", "name": "hook"}),
    ("ImportAudioHook", "POST", "/v1/hooks/audio", False, {"artifact_ref": "artifact-2"}),
    ("RunDebugStage", "POST", "/v1/jobs/job-1/debug-stage", False, {"stage": "script"}),
    ("RetryStage", "POST", "/v1/jobs/job-1/retry-stage", False, {"stage": "script"}),
    ("CreateNewVariant", "POST", "/v1/jobs/job-1/variants", False, {}),
    ("RegenerateFromStage", "POST", "/v1/jobs/job-1/regenerate", False, {"stage": "voice"}),
    ("UpdateSecret", "PUT", "/v1/secrets/secret-1", True, {"value": SECRET}),
    ("TestExternalAccount", "POST", "/v1/external-accounts/acct-1/test", False, None),
    ("EnableExternalAccount", "POST", "/v1/external-accounts/acct-1/enable", True, None),
    ("DisableExternalAccount", "POST", "/v1/external-accounts/acct-1/disable", True, None),
]

# UpdateSourceMetadata không đi qua cổng lệnh: do router metadata H-09 phục vụ
# (PATCH /v1/sources/{item_id}, 200 kèm giá trị đã commit, không phải 202 receipt).
METADATA_ROUTED = [
    ("UpdateSourceMetadata", "PATCH", "/v1/sources/src-1", True, {"tier": "T1", "notes": "ghi chú"}),
]


def RID(path: str) -> str | None:
    for prefix, resource_id in (
        ("/v1/sources/", "src-1"),
        ("/v1/jobs/", "job-1"),
        ("/v1/secrets/", "secret-1"),
        ("/v1/external-accounts/", "acct-1"),
    ):
        if path.startswith(prefix):
            return resource_id
    return None


# ============================================================================
# PHẦN 2a: Test lệnh Control API (14 lệnh qua cổng lệnh CT-API-003..006; UpdateSourceMetadata xem PHẦN 2c)
# ============================================================================


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_command_returns_accepted_receipt(name, method, path, if_match, body):
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(if_match="3" if if_match else None)
    response = send(client, method, path, body, headers)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert "receipt_id" in data
    assert "x-correlation-id" in response.headers
    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["command_name"] == name
    assert call["workspace_id"] == WORKSPACE
    assert call["actor_id"] == ACTOR
    assert call["resource_id"] == RID(path)
    assert call["expected_revision"] == (3 if if_match else None)


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_command_requires_idempotency_key(name, method, path, if_match, body):
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(key=None, if_match="3" if if_match else None)
    response = send(client, method, path, body, headers)
    assert response.status_code == 422
    assert gateway.calls == []


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_command_requires_if_match(name, method, path, if_match, body):
    if not if_match:
        pytest.skip("Lệnh không yêu cầu If-Match")
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway))
    # Thiếu If-Match
    response_missing = send(client, method, path, body, mutation_headers(if_match=None))
    assert response_missing.status_code == 422
    if method != "PUT":
        data = response_missing.json()
        assert data.get("code") == "VALIDATION_FAILED"
        assert "If-Match" in data.get("field_errors", {})
    # If-Match 'abc'
    response_invalid = send(client, method, path, body, mutation_headers(if_match="abc"))
    assert response_invalid.status_code == 422
    assert gateway.calls == []


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_command_stale_revision_is_409(name, method, path, if_match, body):
    if not if_match:
        pytest.skip("Lệnh không yêu cầu If-Match")
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(if_match="99")
    response = send(client, method, path, body, headers)
    assert response.status_code == 409
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    data = response.json()
    assert data.get("code") == "REVISION_CONFLICT"


# ============================================================================
# PHẦN 2b: Test hành vi Idempotency, Normalization và Bảo mật của Route
# ============================================================================


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_command_duplicate_key_returns_same_receipt(name, method, path, if_match, body):
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(key="dup-key", if_match="3" if if_match else None)

    r1 = send(client, method, path, body, headers)
    assert r1.status_code == 202
    d1 = r1.json()
    assert d1["status"] == "accepted"
    receipt_id_1 = d1["receipt_id"]

    r2 = send(client, method, path, body, headers)
    assert r2.status_code == 202
    d2 = r2.json()
    assert d2["status"] == "accepted"
    assert d2["receipt_id"] == receipt_id_1
    assert d2.get("disposition") == "duplicate"

    if isinstance(body, dict) and body:
        first_key = next(iter(body.keys()))
        diff_body = dict(body)
        diff_body[first_key] = "khac"
        r3 = send(client, method, path, diff_body, headers)
        assert r3.status_code == 409
        assert r3.json().get("code") == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
    elif body is None and if_match and RID(path) is not None:
        other_path = path.replace(RID(path), "other-1")
        r3 = send(client, method, other_path, None, headers)
        assert r3.status_code == 409
        assert r3.json().get("code") == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
    else:
        pytest.skip("cannot vary payload for empty body without resource id")


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_command_normalizes_receipt(name, method, path, if_match, body):
    gateway = FakeGateway()
    gateway.extra = {"status": "succeeded", "value": SECRET, "secret": SECRET}
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(if_match="3" if if_match else None)
    response = send(client, method, path, body, headers)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert SECRET not in response.text
    assert "value" not in data
    assert "secret" not in data


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_command_rejects_unknown_field(name, method, path, if_match, body):
    if not body:
        pytest.skip("Lệnh không có body để kiểm tra trường lạ")
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(if_match="3" if if_match else None)
    forbidden_body = dict(body)
    forbidden_body["script"] = "x"
    response = send(client, method, path, forbidden_body, headers)
    assert response.status_code == 422
    data = response.json()
    assert data.get("code") == "FORBIDDEN_FIELD"
    assert "script" in data.get("field_errors", {})
    assert gateway.calls == []


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_command_without_gateway_is_503(name, method, path, if_match, body):
    client = make_client(make_app(gateway=None))
    headers = mutation_headers(if_match="3" if if_match else None)
    response = send(client, method, path, body, headers)
    assert response.status_code == 503
    data = response.json()
    assert data.get("code") == "CAPABILITY_UNAVAILABLE"


# ============================================================================
# PHẦN 2c: UpdateSourceMetadata đi qua router metadata H-09 (PATCH /v1/sources/{item_id})
# ============================================================================

METADATA_ROUTED_PARAMS = ("name,method,path,if_match,body", METADATA_ROUTED)


def make_services() -> dict[str, RecordingModuleService]:
    return {n: RecordingModuleService(n) for n in ("sources", "hooks", "media")}


@pytest.mark.parametrize(*METADATA_ROUTED_PARAMS, ids=[c[0] for c in METADATA_ROUTED])
def test_metadata_routed_returns_committed_value(name, method, path, if_match, body):
    gateway = FakeGateway()
    services = make_services()
    client = make_client(make_app(gateway=gateway, module_services=services))
    response = send(client, method, path, body, mutation_headers(if_match="3"))
    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "disposition": "accepted",
        "resource_ref": {"kind": "sources", "id": "src-1"},
        "current_revision": 4,
    }
    assert "x-correlation-id" in response.headers
    assert services["sources"].calls == [("apply_update", "src-1", 3, body)]
    assert services["hooks"].calls == [] and services["media"].calls == []
    assert gateway.calls == []


@pytest.mark.parametrize(*METADATA_ROUTED_PARAMS, ids=[c[0] for c in METADATA_ROUTED])
def test_metadata_routed_requires_idempotency_key(name, method, path, if_match, body):
    gateway = FakeGateway()
    services = make_services()
    client = make_client(make_app(gateway=gateway, module_services=services))
    response = send(client, method, path, body, mutation_headers(key=None, if_match="3"))
    assert response.status_code == 422
    assert services["sources"].calls == []
    assert gateway.calls == []


@pytest.mark.parametrize(*METADATA_ROUTED_PARAMS, ids=[c[0] for c in METADATA_ROUTED])
def test_metadata_routed_requires_if_match(name, method, path, if_match, body):
    gateway = FakeGateway()
    services = make_services()
    client = make_client(make_app(gateway=gateway, module_services=services))
    response_missing = send(client, method, path, body, mutation_headers(if_match=None))
    assert response_missing.status_code == 422
    data = response_missing.json()
    assert data.get("code") == "VALIDATION_FAILED"
    assert "If-Match" in data.get("field_errors", {})
    response_invalid = send(client, method, path, body, mutation_headers(if_match="abc"))
    assert response_invalid.status_code == 422
    assert services["sources"].calls == []
    assert gateway.calls == []


@pytest.mark.parametrize(*METADATA_ROUTED_PARAMS, ids=[c[0] for c in METADATA_ROUTED])
def test_metadata_routed_stale_revision_is_409(name, method, path, if_match, body):
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway, module_services=make_services()))
    response = send(client, method, path, body, mutation_headers(if_match="99"))
    assert response.status_code == 409
    assert response.json().get("code") == "REVISION_CONFLICT"
    assert gateway.calls == []


@pytest.mark.parametrize("field", ["topics", "tags", "admin_metadata", "script"])
@pytest.mark.parametrize(*METADATA_ROUTED_PARAMS, ids=[c[0] for c in METADATA_ROUTED])
def test_metadata_routed_rejects_fields_outside_allowlist(name, method, path, if_match, body, field):
    gateway = FakeGateway()
    services = make_services()
    client = make_client(make_app(gateway=gateway, module_services=services))
    response = send(client, method, path, {"tier": "T1", field: "x"}, mutation_headers(if_match="3"))
    assert response.status_code == 422
    data = response.json()
    assert data.get("code") == "FORBIDDEN_FIELD"
    assert field in data.get("field_errors", {})
    assert "tier" not in data.get("field_errors", {})
    assert services["sources"].calls == []
    assert gateway.calls == []


@pytest.mark.parametrize(*METADATA_ROUTED_PARAMS, ids=[c[0] for c in METADATA_ROUTED])
def test_metadata_routed_without_service_is_503(name, method, path, if_match, body):
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway, module_services={}))
    response = send(client, method, path, body, mutation_headers(if_match="3"))
    assert response.status_code == 503
    assert response.json().get("code") == "CAPABILITY_UNAVAILABLE"
    assert gateway.calls == []


@pytest.mark.parametrize(*METADATA_ROUTED_PARAMS, ids=[c[0] for c in METADATA_ROUTED])
def test_metadata_routed_put_is_not_routed(name, method, path, if_match, body):
    gateway = FakeGateway()
    client = make_client(make_app(gateway=gateway, module_services=make_services()))
    response = client.put(path, headers=mutation_headers(if_match="3"), json=body)
    assert response.status_code in (404, 405)
    assert gateway.calls == []


def test_update_secret_never_leaks_or_reads(caplog):
    caplog.set_level(logging.DEBUG)
    gateway = FakeGateway()
    app = make_app(gateway=gateway)
    client = make_client(app)
    headers = mutation_headers(if_match="3")
    response = client.put("/v1/secrets/secret-1", headers=headers, json={"value": SECRET})
    assert response.status_code == 202
    assert SECRET not in response.text
    assert SECRET not in caplog.text
    assert SECRET not in str(dict(response.headers))
    get_resp = client.get("/v1/secrets/secret-1", headers=READ_HEADERS)
    assert get_resp.status_code in (404, 405)
    for route, _ in _iter_routes_with_context(app.routes):
        if hasattr(route, "path") and "secret" in route.path:
            methods = set(getattr(route, "methods", set())) - {"HEAD", "OPTIONS"}
            assert methods.issubset({"PUT"})


def test_existing_start_batch_and_config_routes():
    app = make_app(command_service=FakeCommandService())
    client = make_client(app)
    headers = mutation_headers()
    r1 = client.post("/v1/batches", headers=headers, json={"target_completed_videos": 2})
    assert r1.status_code == 202
    assert r1.json().get("disposition") == "accepted"

    r1_nokey = client.post("/v1/batches", headers=mutation_headers(key=None), json={"target_completed_videos": 2})
    assert r1_nokey.status_code == 422

    r2_conflict = client.put("/v1/configs/global:default", headers=mutation_headers(if_match="9"), json={"a": 1})
    assert r2_conflict.status_code == 409
    assert r2_conflict.json().get("code") == "REVISION_CONFLICT"

    r2_ok = client.put("/v1/configs/global:default", headers=mutation_headers(if_match="3"), json={"a": 1})
    assert r2_ok.status_code == 200

    r2_noifmatch = client.put("/v1/configs/global:default", headers=mutation_headers(if_match=None), json={"a": 1})
    assert r2_noifmatch.status_code == 422


# ============================================================================
# PHẦN 3: Test Mount Router H-08/H-09 Trong create_app
# ============================================================================


def test_mount_routes_present_and_unique():
    app = make_app()
    pairs = [
        (m, r.path)
        for r, _ in _iter_routes_with_context(app.routes)
        if getattr(r, "methods", None)
        for m in sorted(r.methods - {"HEAD", "OPTIONS"})
    ]
    assert len(pairs) == len(set(pairs))
    expected = [
        ("GET", "/v1/sources"),
        ("GET", "/v1/sources/{item_id}"),
        ("GET", "/v1/hooks"),
        ("GET", "/v1/hooks/{item_id}"),
        ("GET", "/v1/media"),
        ("GET", "/v1/media/{item_id}"),
        ("PATCH", "/v1/hooks/{item_id}"),
        ("PATCH", "/v1/media/{item_id}"),
        ("PATCH", "/v1/sources/{item_id}"),
    ]
    for pair in expected:
        assert pair in pairs, f"Thiếu route {pair} trong app.routes"
    assert ("PATCH", "/v1/sources/{resource_id}") not in pairs
    source_patches = [p for m, p in pairs if m == "PATCH" and p.startswith("/v1/sources")]
    assert source_patches == ["/v1/sources/{item_id}"]


@pytest.mark.parametrize("resource", ["sources", "hooks", "media"])
def test_mount_listing_calls_service(resource):
    services = {n: RecordingModuleService(n) for n in ("sources", "hooks", "media")}
    client = make_client(make_app(module_services=services))
    r1 = client.get(f"/v1/{resource}?limit=1", headers=READ_HEADERS)
    assert r1.status_code == 200
    assert r1.json() == {"items": [{"id": "x1", "name": resource}], "next_cursor": "cur-1"}
    assert len(services[resource].calls) == 1
    call0 = services[resource].calls[0]
    assert call0[0] == "fetch_page"
    assert call0[1] == WORKSPACE
    assert call0[2].limit == 1
    for other_name, other_svc in services.items():
        if other_name != resource:
            assert other_svc.calls == []

    r_workspace_err = client.get(f"/v1/{resource}?workspace_id=other", headers=READ_HEADERS)
    assert r_workspace_err.status_code == 422
    assert len(services[resource].calls) == 1

    r_one = client.get(f"/v1/{resource}/x1", headers=READ_HEADERS)
    assert r_one.status_code == 200
    assert r_one.json()["id"] == "x1"

    r_missing = client.get(f"/v1/{resource}/missing", headers=READ_HEADERS)
    assert r_missing.status_code == 404
    assert r_missing.headers.get("content-type", "").startswith("application/problem+json")
    assert r_missing.json().get("code") == "NOT_FOUND"


@pytest.mark.parametrize("resource,field", [("hooks", "description"), ("media", "notes"), ("sources", "notes")])
def test_mount_metadata_update_calls_service(resource, field):
    services = {n: RecordingModuleService(n) for n in ("sources", "hooks", "media")}
    service = services[resource]
    client = make_client(make_app(module_services=services))
    r_ok = client.patch(
        f"/v1/{resource}/h1",
        headers=mutation_headers(if_match="3"),
        json={field: "v"},
    )
    assert r_ok.status_code == 200
    assert r_ok.json().get("status") == "accepted"
    assert len(service.calls) == 1
    assert service.calls[0] == ("apply_update", "h1", 3, {field: "v"})

    r_conflict = client.patch(
        f"/v1/{resource}/h1",
        headers=mutation_headers(if_match="9"),
        json={field: "v"},
    )
    assert r_conflict.status_code == 409
    assert r_conflict.json().get("code") == "REVISION_CONFLICT"

    r_forbidden = client.patch(
        f"/v1/{resource}/h1",
        headers=mutation_headers(if_match="3"),
        json={"script": "x"},
    )
    assert r_forbidden.status_code == 422
    assert r_forbidden.json().get("code") == "FORBIDDEN_FIELD"

    r_nokey = client.patch(
        f"/v1/{resource}/h1",
        headers=mutation_headers(key=None, if_match="3"),
        json={field: "v"},
    )
    assert r_nokey.status_code == 422

    r_put = client.put(
        f"/v1/{resource}/h1",
        headers=mutation_headers(if_match="3"),
        json={field: "v"},
    )
    assert r_put.status_code in (404, 405)


def test_mount_sources_metadata_accepts_tier_topic_tags_enabled():
    services = make_services()
    client = make_client(make_app(module_services=services))
    changes = {"tier": "T2", "topic_tags": ["kinh-te", "cong-nghe"], "enabled": False}
    response = client.patch("/v1/sources/s1", headers=mutation_headers(if_match="3"), json=changes)
    assert response.status_code == 200
    assert services["sources"].calls == [("apply_update", "s1", 3, changes)]
    assert services["hooks"].calls == [] and services["media"].calls == []


def test_sources_metadata_resource_allowlist():
    resources = {r.name: r for r in route_catalog.METADATA_RESOURCES}
    assert set(resources) == {"sources", "hooks", "media"}
    sources = resources["sources"]
    assert sources.prefix == "/v1/sources"
    assert sources.allowed_fields == frozenset({"tier", "topic_tags", "notes", "enabled"})
    assert sources.allowed_fields.isdisjoint(FORBIDDEN_METADATA_FIELDS)


def test_mount_without_service_is_503():
    client = make_client(make_app(module_services={}))
    response = client.get("/v1/sources", headers=READ_HEADERS)
    assert response.status_code == 503
    assert response.json().get("code") == "CAPABILITY_UNAVAILABLE"


def test_modules_init_untouched():
    assert (ROOT / "src/controlplane/api/routes/modules/__init__.py").read_bytes() == b""


# ============================================================================
# PHẦN 4: Composition Root, Kiểm tra AST và Ranh giới Phạm vi
# ============================================================================


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
    return modules


OWNED_SOURCES = [
    ROOT / "src/main.py",
    ROOT / "src/controlplane/api/main.py",
    ROOT / "src/controlplane/api/routes/control.py",
] + sorted((ROOT / "src/controlplane/api/routes/modules").glob("*.py")) + sorted(
    (ROOT / "src/controlplane/application/control_api").rglob("*.py")
)


def test_src_main_exists_and_is_thin():
    path = ROOT / "src/main.py"
    assert path.is_file(), "src/main.py must exist"
    text = path.read_text(encoding="utf-8")
    assert "create_app" in text
    assert "TransactionManager" in text
    assert "from src." not in text
    assert "import src." not in text
    assert len(text.splitlines()) <= 90
    allowed_prefixes = {"__future__", "collections", "dataclasses", "os", "fastapi"}
    allowed_exact = {
        "controlplane.api.main",
        "controlplane.infrastructure.db.uow",
        "controlplane.entrypoint",
    }
    for mod in imported_modules(path):
        top = mod.split(".")[0]
        assert top in allowed_prefixes or mod in allowed_exact, f"Module import không được phép trong src/main.py: {mod}"
    assert re.search(r"://[^/\s]*:[^@\s]*@", text) is None


def test_src_main_builds_app_from_config(monkeypatch):
    path = ROOT / "src/main.py"
    assert path.is_file(), "src/main.py must exist"
    spec = importlib.util.spec_from_file_location("cp4_src_main", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(importlib.import_module("sys").modules, spec.name, module)
    spec.loader.exec_module(module)

    recorded_kwargs = []

    class FakeTM:
        def __init__(self, dsn: str):
            self.dsn = dsn

    def fake_create_app(**kwargs):
        recorded_kwargs.append(kwargs)
        return object()

    monkeypatch.setattr(module, "TransactionManager", FakeTM)
    monkeypatch.setattr(module, "create_app", fake_create_app)

    # 1. Hợp lệ với port mặc định
    app = module.build_app({"CONTROLPLANE_DSN": "postgresql://u@h/d"})
    assert app is not None
    assert len(recorded_kwargs) == 1
    assert recorded_kwargs[0]["manager"].dsn == "postgresql://u@h/d"
    assert recorded_kwargs[0]["allowed_origins"] == {
        "https://localhost:8443",
        "https://127.0.0.1:8443",
    }

    # 2. Port tuỳ chỉnh
    recorded_kwargs.clear()
    module.build_app({"CONTROLPLANE_DSN": "postgresql://u@h/d", "CONTROLPLANE_PORT": "9000"})
    assert recorded_kwargs[0]["allowed_origins"] == {
        "https://localhost:9000",
        "https://127.0.0.1:9000",
    }

    # 3. Thiếu DSN
    with pytest.raises(ValueError, match="CONTROLPLANE_DSN is required"):
        module.build_app({})

    # 4. Port không phải số
    with pytest.raises(ValueError, match="CONTROLPLANE_PORT must be an integer"):
        module.build_app({"CONTROLPLANE_DSN": "postgresql://u@h/d", "CONTROLPLANE_PORT": "abc"})

    # 5. Port ngoài phạm vi 1..65535
    with pytest.raises(ValueError, match="CONTROLPLANE_PORT must be within 1..65535"):
        module.build_app({"CONTROLPLANE_DSN": "postgresql://u@h/d", "CONTROLPLANE_PORT": "70000"})


def test_owned_sources_have_no_cross_imports_or_src_prefix():
    forbidden_prefixes = {"source_ingestion", "ingestion", "catalog", "creative", "voice", "render"}
    for path in OWNED_SOURCES:
        if path.is_file():
            for mod in imported_modules(path):
                assert mod != "src" and not mod.startswith("src."), f"Cấm import tiền tố src: {mod} trong {path}"
                top = mod.split(".")[0]
                assert top not in forbidden_prefixes, f"Cấm import chéo phân hệ: {mod} trong {path}"


def wiring_package_problems(wiring_dir: Path) -> list[str]:
    # BL-CV-06 đã đóng bởi CP-2D-REGISTRY. Theo docs/implementation/convergence-ext/slices.md (EXT) dòng 137,
    # CP-5-COMPLETION tạo completion.py; CP-6-WORKFLOW (workflow.py), ADAPT-WIRE và ADAPT-PROD cũng thêm mô-đun
    # vào thư mục này. Phạm vi của Worker CP-4-WIRING do ownedPaths chặn, nên test chỉ kiểm gói tồn tại.
    problems: list[str] = []
    if not (wiring_dir / "__init__.py").is_file():
        problems.append("BL-CV-06: thiếu src/controlplane/api/wiring/__init__.py")
    return problems


def test_wiring_package_exists():
    assert wiring_package_problems(ROOT / "src/controlplane/api/wiring") == []


def test_wiring_package_problems_only_init(tmp_path):
    wiring_dir = tmp_path / "wiring"
    wiring_dir.mkdir()
    (wiring_dir / "__init__.py").write_text("", encoding="utf-8")
    assert wiring_package_problems(wiring_dir) == []


def test_wiring_package_problems_allows_ext_modules(tmp_path):
    wiring_dir = tmp_path / "wiring"
    wiring_dir.mkdir()
    for name in ("__init__.py", "completion.py", "workflow.py"):
        (wiring_dir / name).write_text("", encoding="utf-8")
    assert wiring_package_problems(wiring_dir) == []


def test_wiring_package_problems_reports_missing_init(tmp_path):
    wiring_dir = tmp_path / "wiring"
    wiring_dir.mkdir()
    (wiring_dir / "completion.py").write_text("", encoding="utf-8")
    problems = wiring_package_problems(wiring_dir)
    assert problems != []
    assert "BL-CV-06" in problems[0]


def test_control_sources_have_no_secret_read_path():
    forbidden_names = {"get_secret", "read_secret", "reveal_secret", "resolve_secret", "decrypt", "get_secret_value"}
    target_files = [
        ROOT / "src/controlplane/api/routes/control.py",
    ] + sorted((ROOT / "src/controlplane/application/control_api").rglob("*.py"))
    for path in target_files:
        if path.is_file():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                    raise AssertionError(f"Cấm đọc bí mật (Attribute): {node.attr} trong {path}")
                if isinstance(node, ast.Name) and node.id in forbidden_names:
                    raise AssertionError(f"Cấm đọc bí mật (Name): {node.id} trong {path}")
                if isinstance(node, ast.FunctionDef) and node.name in forbidden_names:
                    raise AssertionError(f"Cấm đọc bí mật (FunctionDef): {node.name} trong {path}")


def test_command_catalog_covers_contract():
    path = ROOT / "src/controlplane/application/control_api/command_catalog.py"
    assert path.is_file(), "command_catalog.py must exist"
    text = path.read_text(encoding="utf-8")
    contract_names = [cmd[0] for cmd in COMMANDS] + [cmd[0] for cmd in METADATA_ROUTED]
    assert len(contract_names) == 15
    assert len(set(contract_names)) == 15
    for cmd_name in contract_names:
        assert f"'{cmd_name}'" in text or f'"{cmd_name}"' in text, f"Thiếu {cmd_name} trong command_catalog.py"
    spec_names = [spec.name for spec in command_catalog.COMMAND_SPECS]
    assert len(spec_names) == 14
    assert set(spec_names) == {cmd[0] for cmd in COMMANDS}
    assert "UpdateSourceMetadata" not in spec_names
    assert getattr(command_catalog, "METADATA_ROUTED_COMMANDS", None) == ("UpdateSourceMetadata",)

# ============================================================================
# PHẦN 5a: Fake cho test ControlCommandGateway thật
# (Nhóm test này viết SAU khi có lớp vì oracle RED của nó chỉ là ImportError)
# ============================================================================

from controlplane.application.control_api.command_gateway import CommandOutcome, ControlCommandGateway


class MemStore:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str], tuple[str, str]] = {}
        self.receipts: dict[str, dict[str, Any]] = {}


class MemIdempotency:
    def __init__(self, store: MemStore) -> None:
        self.store = store

    def lock_key(self, **kw: Any) -> None:
        pass

    def get_record(self, **kw: Any) -> Any:
        return self.store.records.get((kw["workspace_id"], kw["command_name"], kw["idempotency_key"]))

    def replay_receipt(self, receipt_id: str) -> dict[str, Any]:
        return dict(self.store.receipts[receipt_id], disposition="duplicate")

    def create_receipt(self, workspace_id: str) -> dict[str, Any]:
        rid = str(uuid.uuid4())
        rc = {
            "receipt_id": rid,
            "command_id": str(uuid.uuid4()),
            "disposition": "accepted",
            "operation_id": None,
            "resource_ref": None,
            "accepted_at": "2026-10-22T00:00:00Z",
            "current_revision": None,
        }
        self.store.receipts[rid] = rc
        return rc

    def create_record(self, **kw: Any) -> None:
        self.store.records[(kw["workspace_id"], kw["command_name"], kw["idempotency_key"])] = (
            kw["request_hash"],
            kw["receipt_id"],
        )


class MemReceiptFields:
    def __init__(self, store: MemStore) -> None:
        self.store = store

    def bind(
        self,
        *,
        workspace_id: str,
        receipt_id: str,
        operation_id: str | None,
        resource_ref: dict[str, object],
        current_revision: int | None,
    ) -> dict[str, Any]:
        rc = self.store.receipts[receipt_id]
        rc["operation_id"] = operation_id
        rc["resource_ref"] = resource_ref
        rc["current_revision"] = current_revision
        return rc


class MemHandler:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict[str, Any]] = []

    def handle(self, **kw: Any) -> CommandOutcome:
        self.calls.append(kw)
        if kw.get("expected_revision") is not None and kw["expected_revision"] != STORED_REVISION:
            raise RevisionConflictError(STORED_REVISION)
        return CommandOutcome(
            operation_id=str(uuid.uuid4()),
            resource_ref={"kind": self.name, "id": kw["resource_id"]},
            current_revision=STORED_REVISION + 1,
        )


def build_gateway(store: MemStore, handlers: Mapping[str, Any] | None = None) -> ControlCommandGateway:
    return ControlCommandGateway(
        uow_factory=FakeManager().unit_of_work,
        idempotency_factory=lambda connection: MemIdempotency(store),
        receipt_fields_factory=lambda connection: MemReceiptFields(store),
        handlers=handlers,
    )


# ============================================================================
# PHẦN 5b: Test gateway thật qua HTTP
# ============================================================================


@pytest.mark.parametrize("name,method,path,if_match,body", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_gateway_all_commands_accepted(name, method, path, if_match, body):
    store = MemStore()
    handlers = {c[0]: MemHandler(c[0]) for c in COMMANDS}
    client = make_client(make_app(gateway=build_gateway(store, handlers)))
    headers = mutation_headers(if_match="3" if if_match else None)
    response = send(client, method, path, body, headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert len(handlers[name].calls) == 1
    for other_name, other_h in handlers.items():
        if other_name != name:
            assert len(other_h.calls) == 0
    assert len(store.records) == 1


def test_gateway_duplicate_returns_same_receipt_and_calls_handler_once():
    store = MemStore()
    handler = MemHandler("RegisterSource")
    gateway = build_gateway(store, {"RegisterSource": handler})
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(key="dup-key")
    body = {"url": "https://example.org/feed.xml", "name": "Example"}

    r1 = client.post("/v1/sources", headers=headers, json=body)
    assert r1.status_code == 202
    d1 = r1.json()
    assert d1["status"] == "accepted"

    r2 = client.post("/v1/sources", headers=headers, json=body)
    assert r2.status_code == 202
    d2 = r2.json()
    assert d2["status"] == "accepted"
    assert d1["receipt_id"] == d2["receipt_id"]
    assert len(handler.calls) == 1


def test_gateway_changed_payload_is_409():
    store = MemStore()
    handler = MemHandler("RegisterSource")
    gateway = build_gateway(store, {"RegisterSource": handler})
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(key="dup-key")

    r1 = client.post("/v1/sources", headers=headers, json={"url": "https://example.org/1"})
    assert r1.status_code == 202

    r2 = client.post("/v1/sources", headers=headers, json={"url": "https://example.org/2"})
    assert r2.status_code == 409
    assert r2.json().get("code") == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
    assert len(handler.calls) == 1


def test_gateway_stale_revision_writes_nothing():
    store = MemStore()
    handler = MemHandler("RemoveSource")
    gateway = build_gateway(store, {"RemoveSource": handler})
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(if_match="99")

    response = client.delete("/v1/sources/src-1", headers=headers)
    assert response.status_code == 409
    assert response.json().get("code") == "REVISION_CONFLICT"
    assert store.records == {}
    assert store.receipts == {}


def test_gateway_missing_handler_is_503():
    store = MemStore()
    gateway = build_gateway(store, {})
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers()

    response = client.post("/v1/sources", headers=headers, json={"url": "https://example.org/feed.xml"})
    assert response.status_code == 503
    assert response.json().get("code") == "CAPABILITY_UNAVAILABLE"
    assert store.records == {}


def test_gateway_never_stores_or_returns_secret(caplog):
    caplog.set_level(logging.DEBUG)
    store = MemStore()
    handler = MemHandler("UpdateSecret")
    gateway = build_gateway(store, {"UpdateSecret": handler})
    client = make_client(make_app(gateway=gateway))
    headers = mutation_headers(if_match="3")

    response = client.put("/v1/secrets/secret-1", headers=headers, json={"value": SECRET})
    assert response.status_code == 202
    assert SECRET not in response.text
    assert SECRET not in caplog.text
    assert SECRET not in repr(store.records)
    assert SECRET not in repr(store.receipts)


def test_gateway_register_twice_raises():
    gateway = build_gateway(MemStore(), {})
    h = MemHandler("X")
    gateway.register("X", h)
    with pytest.raises(ValueError, match="already registered"):
        gateway.register("X", h)


def test_create_app_gateway_without_handlers_is_503():
    app = create_app(manager=FakeManager(), allowed_origins={ORIGIN})
    app.state.session_service = FakeSessionService()
    assert app.state.command_gateway is not None
    client = make_client(app)
    headers = mutation_headers()

    response = client.post("/v1/sources", headers=headers, json={"url": "https://example.org/f"})
    assert response.status_code == 503
    assert response.json().get("code") == "CAPABILITY_UNAVAILABLE"
