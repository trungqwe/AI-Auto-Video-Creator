"""Test-only application driver for M2-P8 E2E verification.

Advances Batch/Job/Operation lifecycle states via application ports and repositories.
This module is test-only and does not authorize production mutations.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
import uuid

# Ensure src directory is available on sys.path.
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
import psycopg
from psycopg import sql
import uvicorn

from controlplane.api.main import create_app
from controlplane.application.session_security import (
    BootstrapCapabilityRegistry,
)
from controlplane.domain.events import DomainEvent
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.projections.postgres import PostgresOperationStreamRepository
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.security.loopback_certificate import (
    provision_loopback_certificate,
)

DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000801"
DEFAULT_ACTOR_ID = "00000000-0000-0000-0000-000000000802"
DEFAULT_TEST_DB_NAME = "m2_p8_e2e_test"
MIGRATIONS_DIR = SRC_DIR / "controlplane" / "infrastructure" / "db" / "migrations"


def resolve_dsn(explicit_dsn: str | None = None) -> str:
    """Resolve the test database DSN from explicit arg, env, or local Docker."""
    if explicit_dsn:
        return explicit_dsn
    env_dsn = os.environ.get("M2_TEST_PG_DSN")
    if env_dsn:
        return env_dsn
    try:
        output = subprocess.check_output(
            ["docker", "port", "ai-auto-video-m2-pg", "5432/tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        port = output.strip().split(":")[-1]
        return f"postgresql://m2test:m2test@127.0.0.1:{port}/{DEFAULT_TEST_DB_NAME}"
    except Exception:
        return f"postgresql://m2test:m2test@127.0.0.1:5432/{DEFAULT_TEST_DB_NAME}"


def ensure_schema_and_fixtures(admin_dsn: str, db_name: str = DEFAULT_TEST_DB_NAME) -> str:
    """Ensure the target database exists, migrations are applied, and test fixtures exist."""
    conninfo = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    admin_db_info = dict(conninfo)
    admin_db_info["dbname"] = "postgres"
    target_info = dict(conninfo)
    target_info["dbname"] = db_name

    admin_conn_str = psycopg.conninfo.make_conninfo(**admin_db_info)
    target_conn_str = psycopg.conninfo.make_conninfo(**target_info)

    try:
        with psycopg.connect(admin_conn_str, autocommit=True) as admin_conn:
            exists = admin_conn.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (db_name,)
            ).fetchone()
            if not exists:
                admin_conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    except Exception:
        pass

    runner = MigrationRunner(target_conn_str, MIGRATIONS_DIR, is_test_env=True)
    runner.migrate_up()

    with psycopg.connect(target_conn_str) as conn:
        conn.execute(
            """
            INSERT INTO controlplane.cp_workspaces (workspace_id, name, status)
            VALUES (%s, 'M2-P8 Test Workspace', 'ACTIVE')
            ON CONFLICT (workspace_id) DO NOTHING
            """,
            (DEFAULT_WORKSPACE_ID,),
        )
        conn.execute(
            """
            INSERT INTO controlplane.cp_actors (actor_id, workspace_id, actor_type, display_name, status)
            VALUES (%s, %s, 'user', 'M2-P8 Test Admin', 'ACTIVE')
            ON CONFLICT (actor_id) DO NOTHING
            """,
            (DEFAULT_ACTOR_ID, DEFAULT_WORKSPACE_ID),
        )
        conn.commit()

    return target_conn_str


class TestDriver:
    """Internal application test driver for advancing isolated test state."""

    def __init__(
        self,
        dsn: str,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        actor_id: str = DEFAULT_ACTOR_ID,
    ) -> None:
        self.dsn = dsn
        self.workspace_id = workspace_id
        self.actor_id = actor_id

    def advance_operation_state(
        self,
        *,
        operation_id: str,
        status: str,
        summary: str,
        correlation_id: str | None = None,
    ) -> int:
        """Advance an operation lifecycle state and push event to operation stream."""
        corr_id = correlation_id or str(uuid.uuid4())
        event = DomainEvent(
            contract_name="controlplane.operation",
            contract_version=1,
            message_id=str(uuid.uuid4()),
            workspace_id=self.workspace_id,
            correlation_id=corr_id,
            causation_id=None,
            trace_context=None,
            occurred_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            actor=self.actor_id,
            recovery_epoch=1,
            payload={"operation_id": operation_id, "status": status, "summary": summary},
            event_id=str(uuid.uuid4()),
            event_name=f"operation.{status.lower()}",
            aggregate_type="operation",
            aggregate_id=operation_id,
            aggregate_revision=1,
            producer="controlplane.test_driver",
            schema_version=1,
            sensitivity="internal",
        )
        with psycopg.connect(self.dsn) as conn:
            cursor = PostgresOperationStreamRepository(conn).append(
                event=event, safe_summary=summary, operation_id=operation_id
            )
            conn.commit()
            return cursor

    def seed_job(
        self,
        *,
        job_id: str | None = None,
        batch_id: str | None = None,
        status: str = "CREATED",
        snapshot_ref: str = "snap-test-001",
        revision: int = 1,
    ) -> str:
        """Seed an isolated test job with its parent batch."""
        jid = job_id or str(uuid.uuid4())
        bid = batch_id or str(uuid.uuid4())
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                INSERT INTO controlplane.cp_production_batches
                (workspace_id, batch_id, status, target_count)
                VALUES (%s, %s, 'CREATED', 5)
                ON CONFLICT (workspace_id, batch_id) DO NOTHING
                """,
                (self.workspace_id, bid),
            )
            conn.execute(
                """
                INSERT INTO controlplane.cp_video_jobs
                (job_id, workspace_id, batch_id, status, snapshot_ref, revision)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, job_id) DO UPDATE SET status=%s, revision=%s
                """,
                (jid, self.workspace_id, bid, status, snapshot_ref, revision, status, revision),
            )
            conn.commit()
        return jid


class CompositeApp:
    """Composite ASGI application routing /v1/ to Control API and other paths to Web UI."""

    def __init__(self, api_app: FastAPI, web_app: FastAPI) -> None:
        self.api_app = api_app
        self.web_app = web_app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") in ("http", "websocket"):
            path = scope.get("path", "")
            if path.startswith("/v1/"):
                await self.api_app(scope, receive, send)
                return
        await self.web_app(scope, receive, send)


def create_test_application(
    dsn: str,
    dist_dir: Path | None = None,
    allowed_origins: set[str] | None = None,
) -> CompositeApp:
    """Create the full composite application with Control API, test driver routes and static UI."""
    manager = TransactionManager(dsn)
    registry = BootstrapCapabilityRegistry()
    origins = allowed_origins or {
        "https://localhost:8000",
        "https://127.0.0.1:8000",
        "https://localhost:5173",
        "https://127.0.0.1:5173",
    }

    # 1. Real Control API
    api_app = create_app(
        manager=manager,
        allowed_origins=origins,
        bootstrap_registry=registry,
    )

    # 2. Web & Test Driver App
    web_app = FastAPI(title="Control Plane Admin Web UI", docs_url=None, redoc_url=None)
    driver = TestDriver(dsn)

    @web_app.get("/test-driver/health")
    def test_health() -> dict[str, str]:
        return {"status": "ready", "workspace_id": DEFAULT_WORKSPACE_ID}

    @web_app.post("/test-driver/issue-capability")
    def issue_capability() -> dict[str, str]:
        capability = registry.issue(
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor_id=DEFAULT_ACTOR_ID,
        )
        return {
            "capability": capability,
            "workspace_id": DEFAULT_WORKSPACE_ID,
            "actor_id": DEFAULT_ACTOR_ID,
        }

    @web_app.post("/test-driver/advance-operation")
    async def advance_op(request: Request) -> JSONResponse:
        body = await request.json()
        operation_id = body["operation_id"]
        status = body.get("status", "RUNNING")
        summary = body.get("summary", f"Chuyển trạng thái sang {status}")
        cursor = driver.advance_operation_state(
            operation_id=operation_id, status=status, summary=summary
        )
        return JSONResponse({"ok": True, "cursor": cursor, "status": status, "summary": summary})

    @web_app.post("/test-driver/seed-jobs")
    async def seed_jobs() -> dict[str, Any]:
        job1 = driver.seed_job(status="ACTIVE", snapshot_ref="snap-seed-01")
        job2 = driver.seed_job(status="CREATED", snapshot_ref="snap-seed-02")
        return {"seeded": [job1, job2]}

    # Mount UI static build if dist directory exists
    target_dist = dist_dir or (SRC_DIR / "controlplane" / "ui" / "dist")
    if target_dist.exists() and (target_dist / "index.html").exists():
        web_app.mount("/", StaticFiles(directory=str(target_dist), html=True), name="static_ui")

    return CompositeApp(api_app, web_app)


def run_server(
    port: int = 8000,
    dsn: str | None = None,
    dist_dir: Path | None = None,
) -> None:
    """Run the test application behind a transient trusted loopback TLS server."""
    target_dsn = resolve_dsn(dsn)
    target_dsn = ensure_schema_and_fixtures(target_dsn)

    allowed_origins = {
        f"https://localhost:{port}",
        f"https://127.0.0.1:{port}",
    }
    app = create_test_application(
        dsn=target_dsn,
        dist_dir=dist_dir,
        allowed_origins=allowed_origins,
    )

    with provision_loopback_certificate() as cert:
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            ssl_certfile=cert.certificate_path,
            ssl_keyfile=cert.private_key_path,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        print(f"Test server running on https://localhost:{port} (PID: {os.getpid()})")
        server.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="M2-P8 Test Driver")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Run loopback TLS test server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Listen port")
    serve_parser.add_argument("--dsn", type=str, default=None, help="PostgreSQL DSN")

    advance_parser = subparsers.add_parser("advance-operation", help="Advance operation state")
    advance_parser.add_argument("--operation-id", required=True, help="Operation UUID")
    advance_parser.add_argument("--status", required=True, help="New status")
    advance_parser.add_argument("--summary", default="", help="Safe summary")
    advance_parser.add_argument("--dsn", type=str, default=None, help="PostgreSQL DSN")

    seed_parser = subparsers.add_parser("seed", help="Seed test fixtures")
    seed_parser.add_argument("--dsn", type=str, default=None, help="PostgreSQL DSN")

    args = parser.parse_args()
    if args.command == "serve":
        run_server(port=args.port, dsn=args.dsn)
    elif args.command == "advance-operation":
        dsn = resolve_dsn(args.dsn)
        driver = TestDriver(dsn)
        cursor = driver.advance_operation_state(
            operation_id=args.operation_id,
            status=args.status,
            summary=args.summary or f"Trạng thái {args.status}",
        )
        print(f"Advanced operation {args.operation_id} to {args.status} (cursor={cursor})")
    elif args.command == "seed":
        dsn = resolve_dsn(args.dsn)
        ensure_schema_and_fixtures(dsn)
        driver = TestDriver(dsn)
        driver.seed_job(status="ACTIVE")
        print("Seeded test workspace, actor, and jobs.")
    else:
        parser.print_help()