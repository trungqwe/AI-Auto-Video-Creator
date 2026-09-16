"""Independent P7A GREEN hardening checks against disposable PostgreSQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ast
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import ssl
from threading import Lock
import time
import uuid

from fastapi.testclient import TestClient
import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.api.main import create_app
from controlplane.api.tls import start_loopback_tls_server
from controlplane.application.session_security import (
    BootstrapBinding, BootstrapCapabilityRegistry, SessionSecurityService,
)
from controlplane.infrastructure.db.session_security import PostgresSessionRepository


MIGRATIONS = Path(__file__).parents[2] / "src/controlplane/infrastructure/db/migrations"
WORKSPACE = "00000000-0000-0000-0000-0000000007a1"
ACTOR = "00000000-0000-0000-0000-0000000007a2"


@contextmanager
def disposable_database():
    admin_dsn = os.environ["M2_TEST_PG_DSN"]
    name = f"m2_p7a_hardening_{uuid.uuid4().hex}"
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SHOW server_version").fetchone()[0].split()[0] == "18.6"
        assert admin.execute(
            "SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user"
        ).fetchone()[0]
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "INSERT INTO controlplane.cp_workspaces(workspace_id,name,status) "
                "VALUES (%s,'P7A hardening','ACTIVE')", (WORKSPACE,),
            )
            connection.execute(
                "INSERT INTO controlplane.cp_actors"
                "(actor_id,workspace_id,actor_type,display_name,status) "
                "VALUES (%s,%s,'user','P7A','ACTIVE')", (ACTOR, WORKSPACE),
            )
            connection.commit()
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def _counts(dsn: str) -> tuple[int, int, int, int, int]:
    with psycopg.connect(dsn) as connection:
        return tuple(connection.execute(
            f"SELECT count(*) FROM controlplane.{table}"
        ).fetchone()[0] for table in (
            "cp_production_batches", "cp_command_receipts",
            "cp_idempotency_records", "cp_outbox_events", "cp_config_revisions",
        ))


def _service(dsn: str):
    manager = TransactionManager(dsn)
    return manager, compose_command_service(manager.unit_of_work)


@contextmanager
def authenticated_app(dsn: str):
    manager = TransactionManager(dsn)
    registry = BootstrapCapabilityRegistry()
    app = create_app(
        manager=manager,
        allowed_origins={"https://localhost:8443"},
        bootstrap_registry=registry,
    )
    capability = registry.issue(workspace_id=WORKSPACE, actor_id=ACTOR)
    with TestClient(app, base_url="https://localhost:8443", raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/session/bootstrap",
            headers={
                "Origin": "https://localhost:8443",
                "X-Launch-Capability": capability,
                "Cookie": "csrf_token=bootstrap",
                "X-CSRF-Token": "bootstrap",
            },
        )
        assert response.status_code == 200, response.text
        try:
            yield client, app, manager, registry, capability, response
        finally:
            manager.close()


def _mutation_headers(client: TestClient, *, key: str = "http-test") -> dict[str, str]:
    return {
        "Origin": "https://localhost:8443",
        "X-CSRF-Token": client.cookies["csrf_token"],
        "Idempotency-Key": key,
    }


def _fault_after_method(service: object, attribute: str, method: str,
                        fault: RuntimeError, *, factory: bool) -> None:
    original = getattr(service, attribute)

    class FaultAdapter:
        def __init__(self, delegate):
            self._delegate = delegate

        def __getattr__(self, name):
            target = getattr(self._delegate, name)
            if name != method:
                return target

            def write_then_fail(*args, **kwargs):
                target(*args, **kwargs)
                raise fault
            return write_then_fail

    if factory:
        setattr(service, attribute,
                lambda connection: FaultAdapter(original(connection)))
    else:
        setattr(service, attribute, FaultAdapter(original))


def test_h01_actual_app_host_reject() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.get("/v1/operations", headers={"Host": "localhost.evil"})
        assert response.status_code == 403


def test_h02_origin_reject() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.get("/v1/operations", headers={"Origin": "https://evil.test"})
        assert response.status_code == 403


def test_h03_valid_host_origin_success() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.get("/v1/operations", headers={"Origin": "https://localhost:8443"})
        assert response.status_code == 200
        assert response.json() == {"items": [], "next_cursor": None}


def test_h04_csrf_missing_reject() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.post(
            "/v1/batches", json={"target_completed_videos": 2},
            headers={"Origin": "https://localhost:8443", "Idempotency-Key": "h04"},
        )
        assert response.status_code == 403
        assert _counts(dsn) == (0, 0, 0, 0, 0)


def test_h05_csrf_mismatch_reject() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        headers = _mutation_headers(client, key="h05")
        headers["X-CSRF-Token"] = "mismatched"
        response = client.post("/v1/batches", json={"target_completed_videos": 2}, headers=headers)
        assert response.status_code == 403
        assert _counts(dsn) == (0, 0, 0, 0, 0)


def test_h06_csrf_match_success() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.post(
            "/v1/batches", json={"target_completed_videos": 2},
            headers=_mutation_headers(client, key="h06"),
        )
        assert response.status_code == 202, response.text
        assert _counts(dsn) == (1, 1, 1, 1, 0)


def test_h07_session_cookie_flags() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (*_, response):
        cookies = response.headers.get_list("set-cookie")
        session_cookie = next(cookie for cookie in cookies if cookie.startswith("cp_session="))
        csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("csrf_token="))
        assert all(flag in session_cookie for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"))
        assert all(flag in csrf_cookie for flag in ("Secure", "SameSite=strict", "Path=/"))
        assert "HttpOnly" not in csrf_cookie


def test_h08_client_workspace_ignored() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.post(
            "/v1/batches", json={"workspace_id": str(uuid.uuid4()), "target_completed_videos": 2},
            headers=_mutation_headers(client, key="h08"),
        )
        assert response.status_code == 202, response.text
        with psycopg.connect(dsn) as connection:
            assert str(connection.execute(
                "SELECT workspace_id FROM controlplane.cp_production_batches"
            ).fetchone()[0]) == WORKSPACE


def test_h09_session_workspace_binding() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_) :
        with psycopg.connect(dsn) as connection:
            row = connection.execute(
                "SELECT workspace_id,actor_id,octet_length(token_hash) "
                "FROM controlplane.cp_auth_sessions"
            ).fetchone()
            assert tuple(map(str, row[:2])) == (WORKSPACE, ACTOR)
            assert row[2] == 32
        assert client.get("/v1/operations").status_code == 200


def _record_detail(manager: TransactionManager, *, workspace_id: str = WORKSPACE) -> str:
    from controlplane.api.technical_details import record_internal_error

    with manager.unit_of_work() as uow:
        problem = record_internal_error(
            workspace_id=workspace_id, correlation_id="detail-probe",
            error_type="ProbeError", internal_detail="password=canary-secret",
            connection=uow.connection,
        )
    return str(problem["technical_detail_ref"])


def test_h10_detail_cross_workspace_reject() -> None:
    other_workspace, other_actor = str(uuid.uuid4()), str(uuid.uuid4())
    with disposable_database() as dsn, authenticated_app(dsn) as (client, _, manager, registry, *_):
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "INSERT INTO controlplane.cp_workspaces(workspace_id,name,status) "
                "VALUES (%s,'Other workspace','ACTIVE')", (other_workspace,),
            )
            connection.execute(
                "INSERT INTO controlplane.cp_actors(actor_id,workspace_id,actor_type,display_name,status) "
                "VALUES (%s,%s,'user','Other actor','ACTIVE')", (other_actor, other_workspace),
            )
            connection.commit()
        detail_ref = _record_detail(manager, workspace_id=other_workspace)
        response = client.get(f"/v1/errors/{detail_ref}")
        assert response.status_code == 404
        with psycopg.connect(dsn) as connection:
            assert connection.execute(
                "SELECT count(*) FROM controlplane.cp_technical_detail_access_audit"
            ).fetchone()[0] == 0
        assert registry.issue(workspace_id=other_workspace, actor_id=other_actor)


def test_h11_problem_detail_safe() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, app, *_):
        class BrokenQueries:
            def operations(self, **kwargs):
                raise RuntimeError("password=canary-secret C:/internal/private.py")
        app.state.query_service = BrokenQueries()
        response = client.get("/v1/operations")
        assert response.status_code == 500
        assert response.headers["content-type"].startswith("application/problem+json")
        assert "canary-secret" not in response.text
        assert "private.py" not in response.text
        assert response.json()["technical_detail_ref"]


def test_h12_detail_durable_row() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (_, _, manager, *_):
        detail_ref = _record_detail(manager)
        with psycopg.connect(dsn) as connection:
            row = connection.execute(
                "SELECT error_type,stack_trace,sanitized_context "
                "FROM controlplane.cp_technical_details WHERE detail_ref=%s", (detail_ref,),
            ).fetchone()
        assert row == ("ProbeError", "password=[REDACTED]", {})


def test_h13_detail_access_audit() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, _, manager, _, _, bootstrap):
        detail_ref = _record_detail(manager)
        response = client.get(f"/v1/errors/{detail_ref}")
        assert response.status_code == 200, response.text
        with psycopg.connect(dsn) as connection:
            row = connection.execute(
                "SELECT workspace_id,actor_id,session_id,detail_ref "
                "FROM controlplane.cp_technical_detail_access_audit"
            ).fetchone()
        assert str(row[0]) == WORKSPACE and str(row[1]) == ACTOR
        assert str(row[2]) == bootstrap.json()["session_id"]
        assert str(row[3]) == detail_ref


def test_h14_migration_forward() -> None:
    with disposable_database() as dsn, psycopg.connect(dsn) as connection:
        assert connection.execute(
            "SELECT to_regclass('controlplane.cp_technical_details')"
        ).fetchone()[0] is not None
        assert connection.execute(
            "SELECT to_regclass('controlplane.cp_technical_detail_access_audit')"
        ).fetchone()[0] is not None
        assert connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='controlplane' AND table_name='cp_auth_sessions' "
            "AND column_name='token_hash'"
        ).fetchone() == ("token_hash",)


def test_h15_rollback_preserves_0001_0006() -> None:
    with disposable_database() as dsn:
        with psycopg.connect(dsn) as connection:
            connection.execute((MIGRATIONS / "0007_technical_details.rollback.sql").read_text(encoding="utf-8"))
            connection.execute("DELETE FROM controlplane.cp_schema_migrations WHERE version=7")
            connection.commit()
            assert connection.execute("SELECT to_regclass('controlplane.cp_technical_details')").fetchone()[0] is None
            assert connection.execute("SELECT to_regclass('controlplane.cp_auth_sessions')").fetchone()[0] is not None
            assert connection.execute("SELECT count(*) FROM controlplane.cp_workspaces").fetchone()[0] == 1


def test_h16_migration_tracker() -> None:
    with disposable_database() as dsn:
        with psycopg.connect(dsn) as connection:
            versions = [row[0] for row in connection.execute(
                "SELECT version FROM controlplane.cp_schema_migrations ORDER BY version"
            )]
            assert versions == list(range(1, 8))
            connection.execute((MIGRATIONS / "0007_technical_details.rollback.sql").read_text(encoding="utf-8"))
            connection.execute("DELETE FROM controlplane.cp_schema_migrations WHERE version=7")
            connection.commit()
            assert [row[0] for row in connection.execute(
                "SELECT version FROM controlplane.cp_schema_migrations ORDER BY version"
            )] == list(range(1, 7))
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            assert [row[0] for row in connection.execute(
                "SELECT version FROM controlplane.cp_schema_migrations ORDER BY version"
            )] == list(range(1, 8))


def test_h17_actual_fastapi_tls_request() -> None:
    with disposable_database() as dsn:
        manager = TransactionManager(dsn)
        try:
            with manager.unit_of_work() as uow:
                _, token = SessionSecurityService(PostgresSessionRepository).create(
                    connection=uow.connection,
                    binding=BootstrapBinding(
                        WORKSPACE, ACTOR, datetime.now(timezone.utc) + timedelta(seconds=60),
                    ),
                )
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                with httpx.Client(verify=context, timeout=5) as client:
                    response = client.get(
                        f"https://localhost:{endpoint.port}/v1/operations",
                        cookies={"cp_session": token},
                    )
            assert response.status_code == 200, response.text
            assert response.json() == {"items": [], "next_cursor": None}
            assert response.headers["x-correlation-id"]
        finally:
            manager.close()


def test_h18_tls_verification_enabled() -> None:
    with start_loopback_tls_server() as endpoint:
        context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
        with httpx.Client(verify=context, timeout=5) as client:
            assert client.get(f"https://127.0.0.1:{endpoint.port}/v1/jobs").status_code == 503
        try:
            httpx.get(f"https://127.0.0.1:{endpoint.port}/v1/jobs", timeout=5)
        except httpx.ConnectError:
            pass
        else:
            raise AssertionError("self-signed certificate accepted without explicit CA")


def test_h19_loopback_only() -> None:
    with start_loopback_tls_server() as endpoint:
        assert endpoint.host == "127.0.0.1"
        assert endpoint.port > 0
        context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
        with httpx.Client(verify=context, timeout=5) as client:
            response = client.get(
                f"https://127.0.0.1:{endpoint.port}/v1/operations",
                headers={"Host": "remote.example"},
            )
        assert response.status_code == 403


def test_h20_response_log_redaction(caplog) -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, app, *_):
        class BrokenQueries:
            def operations(self, **kwargs):
                raise RuntimeError("password=canary-secret")
        app.state.query_service = BrokenQueries()
        response = client.get("/v1/operations")
        assert response.status_code == 500
        assert "canary-secret" not in response.text
        assert "canary-secret" not in caplog.text


def test_h21_idempotency_header_reject() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        headers = _mutation_headers(client)
        del headers["Idempotency-Key"]
        response = client.post("/v1/batches", json={"target_completed_videos": 2}, headers=headers)
        assert response.status_code == 422
        assert _counts(dsn) == (0, 0, 0, 0, 0)


def test_h22_if_match_reject() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.put(
            "/v1/configs/module:example", json={"enabled": True},
            headers=_mutation_headers(client, key="h22"),
        )
        assert response.status_code == 422
        assert _counts(dsn) == (0, 0, 0, 0, 0)


def test_h23_revision_conflict_409() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        headers = _mutation_headers(client, key="h23-first")
        headers["If-Match"] = "0"
        first = client.put("/v1/configs/module:example", json={"enabled": True}, headers=headers)
        assert first.status_code == 200, first.text
        headers["Idempotency-Key"] = "h23-stale"
        stale = client.put("/v1/configs/module:example", json={"enabled": False}, headers=headers)
        assert stale.status_code == 409, stale.text
        assert stale.json()["code"] == "REVISION_CONFLICT"
        assert _counts(dsn) == (0, 1, 1, 1, 1)


def test_h24_business_validation_422() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.post(
            "/v1/batches", json={"target_completed_videos": 0},
            headers=_mutation_headers(client, key="h24"),
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert _counts(dsn) == (0, 0, 0, 0, 0)


def test_h25_idempotent_replay_one_command() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        headers = _mutation_headers(client, key="h25")
        payload = {"target_completed_videos": 2}
        first = client.post("/v1/batches", json=payload, headers=headers)
        second = client.post("/v1/batches", json=payload, headers=headers)
        assert first.status_code == second.status_code == 202
        assert first.json()["receipt_id"] == second.json()["receipt_id"]
        assert first.json()["operation_id"] == second.json()["operation_id"]
        assert _counts(dsn) == (1, 1, 1, 1, 0)


def test_h26_correlation_id() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        accepted = client.get("/v1/operations")
        rejected = client.get("/v1/operations", headers={"Host": "evil.test"})
        assert accepted.headers["x-correlation-id"]
        assert rejected.headers["x-correlation-id"]
        assert rejected.json()["correlation_id"] == rejected.headers["x-correlation-id"]
        assert accepted.headers["x-correlation-id"] != rejected.headers["x-correlation-id"]


def test_h27_accepted_202_not_completion() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, *_):
        response = client.post(
            "/v1/batches", json={"target_completed_videos": 2},
            headers=_mutation_headers(client, key="h27"),
        )
        assert response.status_code == 202
        assert response.json()["disposition"] == "accepted"
        with psycopg.connect(dsn) as connection:
            status = connection.execute(
                "SELECT status FROM controlplane.cp_production_batches"
            ).fetchone()[0]
        assert status == "CREATED"


def test_h28_static_architecture() -> None:
    root = Path(__file__).parents[2] / "src/controlplane"
    application = list((root / "application/control_api").rglob("*.py"))
    api = list((root / "api").rglob("*.py"))
    assert application and api
    for path in application:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, ast.ImportFrom) and node.module and
            node.module.startswith("controlplane.infrastructure")
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.Constant) and isinstance(node.value, str) and
            any(word in node.value.upper() for word in ("INSERT INTO", "UPDATE CONTROLPLANE", "DELETE FROM"))
            for node in ast.walk(tree)
        )
    for path in api:
        source = path.read_text(encoding="utf-8")
        assert "PostgresIdempotencyRepository" not in source
        assert "PostgresOutboxRepository" not in source
        assert "import psycopg" not in source
        assert "INSERT INTO" not in source


def test_h35_bootstrap_capability_single_use_and_expiry() -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, _, _, registry, capability, _):
        headers = {
            "Origin": "https://localhost:8443",
            "X-Launch-Capability": capability,
            "X-CSRF-Token": client.cookies["csrf_token"],
        }
        replay = client.post("/v1/session/bootstrap", headers=headers)
        assert replay.status_code == 403
        expiring = registry.issue(workspace_id=WORKSPACE, actor_id=ACTOR, ttl_seconds=1)
        time.sleep(1.1)
        headers["X-Launch-Capability"] = expiring
        expired = client.post("/v1/session/bootstrap", headers=headers)
        assert expired.status_code == 403
        with psycopg.connect(dsn) as connection:
            assert connection.execute("SELECT count(*) FROM controlplane.cp_auth_sessions").fetchone()[0] == 1


def test_h36_bootstrap_capability_not_leaked(caplog) -> None:
    with disposable_database() as dsn, authenticated_app(dsn) as (client, _, _, _, capability, bootstrap):
        token = client.cookies["cp_session"]
        assert capability not in bootstrap.text
        assert token not in bootstrap.text
        assert capability not in str(bootstrap.request.url)
        assert token not in str(bootstrap.request.url)
        assert capability not in caplog.text and token not in caplog.text
        with psycopg.connect(dsn) as connection:
            row = connection.execute("SELECT token_hash FROM controlplane.cp_auth_sessions").fetchone()[0]
        assert len(row) == 32
        assert token.encode() not in row


def test_h29_start_batch_atomic_commit() -> None:
    with disposable_database() as dsn:
        manager, service = _service(dsn)
        try:
            receipt = service.start_batch(
                workspace_id=WORKSPACE, actor_id=ACTOR, correlation_id="h29",
                idempotency_key="h29", payload={"target_completed_videos": 3},
            )
            assert receipt["operation_id"] is not None
            assert receipt["resource_ref"]["kind"] == "production_batch"
            assert receipt["current_revision"] is None
            assert _counts(dsn) == (1, 1, 1, 1, 0)
            with psycopg.connect(dsn) as connection:
                row = connection.execute(
                    "SELECT aggregate_id,payload FROM controlplane.cp_outbox_events"
                ).fetchone()
                assert row[0] == receipt["resource_ref"]["batch_id"]
                assert row[1]["operation_id"] == str(receipt["operation_id"])
                assert row[1]["receipt_id"] == str(receipt["receipt_id"])
        finally:
            manager.close()


def test_h30_start_batch_fault_full_rollback() -> None:
    with disposable_database() as dsn:
        manager = TransactionManager(dsn)
        try:
            for stage in ("batch", "receipt", "idempotency", "outbox", "precommit"):
                service = compose_command_service(manager.unit_of_work)
                fault = RuntimeError(f"injected {stage} fault")
                if stage == "batch":
                    inner = service._start_batch_service

                    class FaultBatch:
                        def start(self, **kwargs):
                            inner.start(**kwargs)
                            raise fault

                    service._start_batch_service = FaultBatch()
                elif stage in {"receipt", "idempotency", "outbox"}:
                    attribute, method = {
                        "receipt": ("_receipt_fields_factory", "bind"),
                        "idempotency": ("_idempotency_factory", "create_record"),
                        "outbox": ("_outbox_factory", "enqueue"),
                    }[stage]
                    _fault_after_method(service, attribute, method, fault, factory=True)
                try:
                    service.start_batch(
                        workspace_id=WORKSPACE, actor_id=ACTOR, correlation_id="h30",
                        idempotency_key=f"h30-{stage}", payload={"target_completed_videos": 2},
                        inject_before_commit=fault if stage == "precommit" else None,
                    )
                except RuntimeError as exc:
                    assert exc is fault
                else:
                    raise AssertionError(f"{stage} fault was not raised")
                assert _counts(dsn) == (0, 0, 0, 0, 0)
        finally:
            manager.close()


def test_h31_start_batch_duplicate_same_identity() -> None:
    with disposable_database() as dsn:
        manager = TransactionManager(dsn)
        count_lock = Lock()
        uow_count = 0

        def counted_uow():
            nonlocal uow_count
            with count_lock:
                uow_count += 1
            return manager.unit_of_work()

        service = compose_command_service(counted_uow)
        try:
            def submit(_: int):
                return service.start_batch(
                    workspace_id=WORKSPACE, actor_id=ACTOR, correlation_id="h31",
                    idempotency_key="h31", payload={"target_completed_videos": 2},
                )
            with ThreadPoolExecutor(max_workers=2) as executor:
                first, second = list(executor.map(submit, range(2)))
            assert first["receipt_id"] == second["receipt_id"]
            assert first["operation_id"] == second["operation_id"]
            assert first["resource_ref"] == second["resource_ref"]
            assert {first["disposition"], second["disposition"]} == {"accepted", "duplicate"}
            assert _counts(dsn) == (1, 1, 1, 1, 0)
            assert uow_count == 2
        finally:
            manager.close()


def test_h32_start_batch_key_reuse_conflict() -> None:
    with disposable_database() as dsn:
        manager, service = _service(dsn)
        try:
            service.start_batch(
                workspace_id=WORKSPACE, actor_id=ACTOR, correlation_id="h32",
                idempotency_key="h32", payload={"target_completed_videos": 2},
            )
            try:
                service.start_batch(
                    workspace_id=WORKSPACE, actor_id=ACTOR, correlation_id="h32",
                    idempotency_key="h32", payload={"target_completed_videos": 4},
                )
            except ValueError as exc:
                assert str(exc) == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
            else:
                raise AssertionError("changed input was accepted")
            assert _counts(dsn) == (1, 1, 1, 1, 0)
        finally:
            manager.close()


def test_h33_config_mutation_atomic_idempotency() -> None:
    with disposable_database() as dsn:
        manager, service = _service(dsn)
        try:
            receipt = service.put_config(
                workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key="h33",
                scope_kind="module", scope_key="example", expected_revision=0,
                payload={"enabled": True},
            )
            assert receipt["current_revision"] == 2
            assert _counts(dsn) == (0, 1, 1, 1, 1)
            for stage in ("config_create", "config_publish", "receipt", "idempotency", "precommit"):
                attempt = compose_command_service(manager.unit_of_work)
                fault = RuntimeError(f"config {stage} fault")
                if stage != "precommit":
                    attribute, method, factory = {
                        "config_create": ("_config_service", "create_revision", False),
                        "config_publish": ("_config_repository", "publish", False),
                        "receipt": ("_receipt_fields_factory", "bind", True),
                        "idempotency": ("_idempotency_factory", "create_record", True),
                    }[stage]
                    _fault_after_method(attempt, attribute, method, fault, factory=factory)
                try:
                    attempt.put_config(
                        workspace_id=WORKSPACE, actor_id=ACTOR,
                        idempotency_key=f"h33-{stage}", scope_kind="module",
                        scope_key=f"other-{stage}", expected_revision=0,
                        payload={"enabled": False},
                        inject_before_commit=fault if stage == "precommit" else None,
                    )
                except RuntimeError as exc:
                    assert exc is fault
                else:
                    raise AssertionError(f"{stage} fault was not raised")
                assert _counts(dsn) == (0, 1, 1, 1, 1)
        finally:
            manager.close()


def test_h34_config_duplicate_no_second_revision() -> None:
    with disposable_database() as dsn:
        manager, service = _service(dsn)
        try:
            kwargs = dict(
                workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key="h34",
                scope_kind="module", scope_key="example", expected_revision=0,
                payload={"enabled": True},
            )
            first = service.put_config(**kwargs)
            second = service.put_config(**kwargs)
            assert first["receipt_id"] == second["receipt_id"]
            assert first["resource_ref"] == second["resource_ref"]
            assert _counts(dsn) == (0, 1, 1, 1, 1)
        finally:
            manager.close()
