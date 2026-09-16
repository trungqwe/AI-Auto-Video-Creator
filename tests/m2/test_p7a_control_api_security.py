"""Exact four independent M2-P7A Behavioral RED security oracles."""

from __future__ import annotations

import os
import socket
import ssl
import uuid
from pathlib import Path

import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.api.security import enforce_csrf, enforce_host
from controlplane.api.technical_details import (
    record_internal_error,
    retrieve_technical_detail,
)
from controlplane.api.tls import start_loopback_tls_server
from controlplane.infrastructure.db.migration_runner import MigrationRunner


MIGRATIONS = Path(__file__).parents[2] / "src/controlplane/infrastructure/db/migrations"
WORKSPACE_ID = "00000000-0000-0000-0000-000000000701"
FOREIGN_WORKSPACE_ID = "00000000-0000-0000-0000-000000000702"
FAKE_DETAIL = "Traceback: C:/test-only/fake-path.py; FAKE_CANARY_NOT_A_SECRET"


def test_tst_m2_p7a_001_host_header_spoofing_rejected() -> None:
    request = httpx.Request("GET", "https://localhost/v1/operations", headers={"Host": "evil.com"})
    try:
        enforce_host(request)
    except PermissionError:
        pass
    else:
        raise AssertionError("Foreign Host must be rejected before dispatch")
    for allowed in ("localhost", "localhost:8443", "127.0.0.1", "127.0.0.1:8443"):
        enforce_host(httpx.Request("GET", "https://localhost/v1/operations", headers={"Host": allowed}))


def test_tst_m2_p7a_002_csrf_mutation_without_token_rejected() -> None:
    for headers in (
        {"Cookie": "csrf_token=fake-test-nonce"},
        {"X-CSRF-Token": "fake-test-nonce"},
        {"Cookie": "csrf_token=fake-test-nonce", "X-CSRF-Token": "different-fake-nonce"},
    ):
        request = httpx.Request("POST", "https://localhost/v1/batches", headers=headers)
        try:
            enforce_csrf(request)
        except PermissionError:
            pass
        else:
            raise AssertionError("Missing or mismatched double-submit token must be rejected")
    valid = httpx.Request(
        "POST", "https://localhost/v1/batches",
        headers={"Cookie": "csrf_token=fake-test-nonce", "X-CSRF-Token": "fake-test-nonce"},
    )
    enforce_csrf(valid)


def test_tst_m2_p7a_003_safe_technical_detail_ref_retrieval() -> None:
    admin_dsn = os.environ["M2_TEST_PG_DSN"]
    name = f"m2_p7a_test_{uuid.uuid4().hex}"
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SHOW server_version").fetchone()[0].split()[0] == "18.6"
        assert admin.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0]
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "INSERT INTO controlplane.cp_workspaces (workspace_id,name,status) "
                "VALUES (%s,'P7A','ACTIVE'),(%s,'P7A foreign','ACTIVE')",
                (WORKSPACE_ID, FOREIGN_WORKSPACE_ID),
            )
            connection.commit()
            problem = record_internal_error(
                workspace_id=WORKSPACE_ID, correlation_id=str(uuid.uuid4()),
                error_type="FakeTestError", internal_detail=FAKE_DETAIL, connection=connection,
            )
            serialized = str(problem)
            assert "technical_detail_ref" in problem
            assert FAKE_DETAIL not in serialized
            assert "Traceback" not in serialized
            detail = retrieve_technical_detail(
                detail_ref=str(problem["technical_detail_ref"]),
                session_workspace_id=WORKSPACE_ID, connection=connection,
            )
            assert detail["error_type"] == "FakeTestError"
            try:
                retrieve_technical_detail(
                    detail_ref=str(problem["technical_detail_ref"]),
                    session_workspace_id=FOREIGN_WORKSPACE_ID, connection=connection,
                )
            except (LookupError, PermissionError):
                pass
            else:
                raise AssertionError("Foreign workspace must not retrieve technical detail")
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_tst_m2_p7a_004_tls_handshake_verification() -> None:
    with start_loopback_tls_server() as endpoint:
        assert endpoint.host in {"localhost", "127.0.0.1"}
        context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
        with socket.create_connection((endpoint.host, endpoint.port), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname="localhost") as tls:
                assert tls.version() in {"TLSv1.2", "TLSv1.3"}
                assert tls.getpeercert()
