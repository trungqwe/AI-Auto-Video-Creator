"""P7B runtime, exact-scope and disposable PostgreSQL migration/plan proof."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import uuid

import psycopg
import psycopg_pool
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.infrastructure.db.migration_runner import MigrationRunner


ROOT = Path(__file__).parents[4]
MIGRATIONS = ROOT / "src/controlplane/infrastructure/db/migrations"
P7A_ACCEPTED = "6c3a52bde905ee5e71e12334da1873ed20f5c5db"
P7A_ORACLE_SHA = "63151da21b07c3dd92c5b4a7acc0d4f952f188ee2425a52c9d3ac8d34eb61035"
P7B_ORACLE_SHA = "d83d0f2d808f1b0067d5288ea131ded24d8fc46a16462b5254fd4167f7425738"
BASE = "2c0a371fcfe5ea6d1c6e97fa1f7c9983a16c82f8"
ALLOWED_CODE = frozenset({
    "src/controlplane/api/main.py",
    "src/controlplane/api/sse/stream.py",
    "src/controlplane/application/sse/stream.py",
    "src/controlplane/infrastructure/db/sse/postgres.py",
    "src/controlplane/infrastructure/db/projections/postgres.py",
    "src/controlplane/infrastructure/db/migrations/0008_operation_stream_workspace_cursor_index.sql",
    "src/controlplane/infrastructure/db/migrations/0008_operation_stream_workspace_cursor_index.rollback.sql",
    "src/controlplane/infrastructure/evidence/profile_p7b.py",
    "src/controlplane/infrastructure/evidence/synthesizer_p7b.py",
    "src/controlplane/infrastructure/evidence/probe_p7b.py",
    "tests/m2/test_p7b_hardening.py",
    "tests/m2/test_p7a_hardening.py",
})
WORKSPACE_A = "00000000-0000-0000-0000-0000000007b1"
WORKSPACE_B = "00000000-0000-0000-0000-0000000007b2"


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def _git_bytes(revision: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)


def _imports(path: Path) -> list[str]:
    result: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.append(node.module)
    return result


def _without_function_body(source: bytes, *, class_name: str | None,
                           function_name: str) -> tuple[str, list[str]]:
    tree = ast.parse(source.decode("utf-8"))
    parent = tree
    if class_name is not None:
        classes = [node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == class_name]
        if len(classes) != 1:
            raise RuntimeError("scope class identity mismatch")
        parent = classes[0]
    matches = [node for node in parent.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == function_name]
    if len(matches) != 1:
        raise RuntimeError("scope function identity mismatch")
    identities = [node.name for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name.startswith("test_h")]
    matches[0].body = []
    return ast.dump(tree, include_attributes=False), identities


def _scope(source_sha: str) -> dict[str, object]:
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", BASE, source_sha, "--",
         "src/controlplane", "tests/m2"], cwd=ROOT, text=True,
    ).splitlines()
    unexpected = sorted(set(changed) - ALLOWED_CODE)
    assert not unexpected, f"unexpected code paths: {unexpected}"
    negative = sorted(set([
        "src/controlplane/infrastructure/db/migrations/0009_other.sql",
        "src/controlplane/infrastructure/db/migration_runner.py",
        "tests/m2/test_p7a_control_api_security.py",
    ]) - ALLOWED_CODE)
    assert len(negative) == 3
    p3_path = "src/controlplane/infrastructure/db/projections/postgres.py"
    before_p3, _ = _without_function_body(_git_bytes(BASE, p3_path),
                                          class_name="PostgresOperationStreamRepository",
                                          function_name="append")
    after_p3, _ = _without_function_body(_git_bytes(source_sha, p3_path),
                                         class_name="PostgresOperationStreamRepository",
                                         function_name="append")
    assert before_p3 == after_p3, "P3 drift outside append body"
    p3_text = _git_bytes(source_sha, p3_path).decode("utf-8")
    append_body = p3_text.split("    def append(", 1)[1].split("\n\nclass ", 1)[0]
    assert append_body.count("self._connection.execute(") == 1
    assert append_body.index("WITH ordering_fence AS MATERIALIZED") < append_body.index(
        "allocated_cursor AS MATERIALIZED") < append_body.index("nextval(") < append_body.index(
        "INSERT INTO controlplane.cp_operation_stream")
    assert "pg_advisory_xact_lock(" in append_body
    assert "pg_advisory_lock(" not in append_body
    assert all(token not in append_body for token in (
        ".commit(", ".rollback(", ".transaction(", "BEGIN", "COMMIT", "ROLLBACK"))
    h16_path = "tests/m2/test_p7a_hardening.py"
    before_h16, before_names = _without_function_body(
        _git_bytes(P7A_ACCEPTED, h16_path), class_name=None,
        function_name="test_h16_migration_tracker")
    after_h16, after_names = _without_function_body(
        _git_bytes(source_sha, h16_path), class_name=None,
        function_name="test_h16_migration_tracker")
    assert before_h16 == after_h16 and before_names == after_names and len(after_names) == 36
    assert hashlib.sha256(_git_bytes(source_sha,
        "tests/m2/test_p7a_control_api_security.py")).hexdigest() == P7A_ORACLE_SHA
    assert hashlib.sha256(_git_bytes(source_sha,
        "tests/m2/test_p7b_sse_stream.py")).hexdigest() == P7B_ORACLE_SHA
    migration_names = sorted(path.name for path in MIGRATIONS.glob("*.sql")
                             if path.name[:4].isdigit() and int(path.name[:4]) >= 8)
    assert migration_names == [
        "0008_operation_stream_workspace_cursor_index.rollback.sql",
        "0008_operation_stream_workspace_cursor_index.sql",
    ]
    assert (MIGRATIONS / "0008_operation_stream_workspace_cursor_index.sql").read_text(
        encoding="utf-8").strip() == (
        "CREATE INDEX cp_operation_stream_workspace_cursor_idx\n"
        "ON controlplane.cp_operation_stream (workspace_id, stream_event_id);"
    )
    assert (MIGRATIONS / "0008_operation_stream_workspace_cursor_index.rollback.sql").read_text(
        encoding="utf-8").strip() == "DROP INDEX controlplane.cp_operation_stream_workspace_cursor_idx;"
    assert subprocess.run(["git", "diff", "--quiet", BASE, source_sha, "--",
                           "src/controlplane/infrastructure/db/migration_runner.py"],
                          cwd=ROOT).returncode == 0
    assert subprocess.run(["git", "diff", "--quiet", BASE, source_sha, "--",
                           "docs/milestones/m2-control-plane/evidence",
                           "docs/milestones/m1-proof/evidence"],
                          cwd=ROOT).returncode == 0
    runtime_writers = [path for path in (ROOT / "src/controlplane").rglob("*.py")
                       if "infrastructure/evidence" not in path.as_posix()
                       and "INSERT INTO controlplane.cp_operation_stream" in
                       path.read_text(encoding="utf-8")]
    assert runtime_writers == [ROOT / p3_path], "unexpected runtime stream writer"
    app_imports = [name for path in (ROOT / "src/controlplane/application").rglob("*.py")
                   for name in _imports(path)]
    domain_imports = [name for path in (ROOT / "src/controlplane/domain").rglob("*.py")
                      for name in _imports(path)]
    sse_api_imports = _imports(ROOT / "src/controlplane/api/sse/stream.py")
    assert not any(name.startswith("controlplane.infrastructure") for name in app_imports)
    assert not any(name.startswith("controlplane.application") for name in domain_imports)
    assert not any(name.startswith(("psycopg", "controlplane.infrastructure"))
                   for name in sse_api_imports)
    return {
        "source_commit_sha": source_sha, "changed_code_paths": changed,
        "unexpected_scope_paths": unexpected, "source_scope_exact_pass": True,
        "source_scope_negative_probe_pass": True,
        "p3_append_body_only": True,
        "p7a_h16_body_only": True,
        "p7a_hardening_identities": after_names,
        "p7a_hardening_sha256": hashlib.sha256(_git_bytes(source_sha, h16_path)).hexdigest(),
        "p7a_historical_source_sha": P7A_ACCEPTED,
        "p7a_behavioral_oracle_sha256": P7A_ORACLE_SHA,
        "p7b_behavioral_oracle_sha256": P7B_ORACLE_SHA,
        "application_to_infrastructure_imports": 0,
        "domain_to_application_imports": 0,
        "api_sse_infrastructure_imports": 0,
        "migration_runner_unchanged": True,
        "migration_0009_absent": True,
        "historical_evidence_preserved": True,
        "runtime_stream_writers": [p3_path],
        "one_statement_fence_before_allocation": True,
        "migration_0008_exact_ddl": True,
    }


def _plan(connection: psycopg.Connection, workspace: str, cursor: int) -> list[dict[str, object]]:
    return connection.execute(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        "SELECT stream_event_id,resource_type,resource_id,resource_revision,event_kind,"
        "occurred_at,recorded_at,summary,correlation_id "
        "FROM controlplane.cp_operation_stream "
        "WHERE workspace_id=%s AND stream_event_id>%s "
        "ORDER BY stream_event_id ASC LIMIT 100",
        (workspace, cursor),
    ).fetchone()[0]


def _assert_post_plan(raw: list[dict[str, object]], *, expected_rows: int) -> None:
    root = raw[0]["Plan"]
    assert root["Node Type"] == "Limit"
    scan = root["Plans"][0]
    assert scan["Node Type"] == "Index Scan"
    assert scan["Index Name"] == "cp_operation_stream_workspace_cursor_idx"
    assert "workspace_id =" in scan["Index Cond"]
    assert "stream_event_id >" in scan["Index Cond"]
    assert scan.get("Rows Removed by Filter", 0) == 0
    assert scan["Actual Rows"] == expected_rows


def migration_and_plan_proof(output: Path, admin_dsn: str) -> dict[str, object]:
    name = "m2_p7b_evidence_" + uuid.uuid4().hex
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SHOW server_version").fetchone()[0].split()[0] == "18.6"
        assert admin.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0]
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        with tempfile.TemporaryDirectory(prefix="p7b_baseline_migrations_") as temporary:
            baseline = Path(temporary)
            for path in MIGRATIONS.glob("*.sql"):
                if path.name[:4].isdigit() and int(path.name[:4]) <= 7:
                    shutil.copy2(path, baseline / path.name)
            MigrationRunner(dsn, baseline, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            connection.execute("INSERT INTO controlplane.cp_workspaces(workspace_id,name,status) "
                               "VALUES (%s,'P7B A','ACTIVE'),(%s,'P7B B','ACTIVE')",
                               (WORKSPACE_A, WORKSPACE_B))
            connection.execute("INSERT INTO controlplane.cp_workspaces(workspace_id,name,status) "
                               "SELECT ('10000000-0000-0000-0000-'||lpad(g::text,12,'0'))::uuid,"
                               "'P7B '||g,'ACTIVE' FROM generate_series(1,98) g")
            connection.execute(
                "INSERT INTO controlplane.cp_operation_stream "
                "(workspace_id,resource_type,resource_id,resource_revision,event_kind,occurred_at,summary,correlation_id) "
                "SELECT CASE WHEN mod(g,99)=0 THEN %s::uuid ELSE "
                "('10000000-0000-0000-0000-'||lpad((mod(g,98)+1)::text,12,'0'))::uuid END,"
                "'operation',g::text,1,'operation.changed',CURRENT_TIMESTAMP,'safe','probe' "
                "FROM generate_series(1,100000) g", (WORKSPACE_A,))
            connection.execute("INSERT INTO controlplane.cp_operation_stream_retention_watermarks "
                               "(workspace_id,minimum_available_cursor,minimum_available_at) "
                               "VALUES (%s,99,CURRENT_TIMESTAMP)", (WORKSPACE_A,))
            connection.execute("ANALYZE controlplane.cp_operation_stream")
            connection.commit()
            before_count = connection.execute(
                "SELECT count(*) FROM controlplane.cp_operation_stream").fetchone()[0]
            pre_absent = _plan(connection, WORKSPACE_B, 0)
            pre_resume = _plan(connection, WORKSPACE_A, 50000)
            _write_json(output / "pre-index-absent-explain.json", pre_absent)
            _write_json(output / "pre-index-resume-explain.json", pre_resume)
            assert pre_absent[0]["Plan"]["Plans"][0]["Node Type"] == "Sort"
            assert pre_absent[0]["Plan"]["Plans"][0]["Plans"][0]["Node Type"] == "Seq Scan"
            assert pre_absent[0]["Plan"]["Plans"][0]["Plans"][0]["Rows Removed by Filter"] >= 100000
            connection.commit()
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            forward = [row[0] for row in connection.execute(
                "SELECT version FROM controlplane.cp_schema_migrations ORDER BY version")]
            assert forward == list(range(1, 9))
            _write_json(output / "tracker-forward.json", forward)
            catalog = connection.execute(
                "SELECT am.amname,i.indisunique,i.indnkeyatts,i.indnatts,"
                "i.indpred IS NULL,i.indexprs IS NULL,"
                "ARRAY(SELECT a.attname FROM unnest(i.indkey) WITH ORDINALITY k(attnum,ord) "
                "JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum "
                "ORDER BY k.ord),pg_get_indexdef(i.indexrelid) "
                "FROM pg_index i JOIN pg_class idx ON idx.oid=i.indexrelid "
                "JOIN pg_am am ON am.oid=idx.relam "
                "WHERE i.indexrelid=to_regclass('controlplane.cp_operation_stream_workspace_cursor_idx')"
            ).fetchone()
            assert catalog is not None
            assert catalog[:7] == ("btree", False, 2, 2, True, True,
                                    ["workspace_id", "stream_event_id"])
            _write_json(output / "index-catalog.json", {
                "method": catalog[0], "unique": catalog[1], "key_count": catalog[2],
                "attribute_count": catalog[3], "no_predicate": catalog[4],
                "no_expression": catalog[5], "keys": catalog[6], "definition": catalog[7],
            })
            post_absent = _plan(connection, WORKSPACE_B, 0)
            post_resume = _plan(connection, WORKSPACE_A, 50000)
            _assert_post_plan(post_absent, expected_rows=0)
            _assert_post_plan(post_resume, expected_rows=100)
            _write_json(output / "post-index-absent-explain.json", post_absent)
            _write_json(output / "post-index-resume-explain.json", post_resume)
            rows = connection.execute(
                "SELECT stream_event_id FROM controlplane.cp_operation_stream "
                "WHERE workspace_id=%s AND stream_event_id>50000 "
                "ORDER BY stream_event_id LIMIT 100", (WORKSPACE_A,)).fetchall()
            assert len(rows) == 100 and rows == sorted(rows)
            connection.execute((MIGRATIONS /
                "0008_operation_stream_workspace_cursor_index.rollback.sql").read_text(encoding="utf-8"))
            connection.execute("DELETE FROM controlplane.cp_schema_migrations WHERE version=8")
            connection.commit()
            rollback = [row[0] for row in connection.execute(
                "SELECT version FROM controlplane.cp_schema_migrations ORDER BY version")]
            assert rollback == list(range(1, 8))
            assert connection.execute("SELECT to_regclass("
                "'controlplane.cp_operation_stream_workspace_cursor_idx')").fetchone()[0] is None
            _write_json(output / "tracker-rollback.json", rollback)
            preserved = {
                "stream_rows": connection.execute(
                    "SELECT count(*) FROM controlplane.cp_operation_stream").fetchone()[0],
                "workspace_rows": connection.execute(
                    "SELECT count(*) FROM controlplane.cp_workspaces").fetchone()[0],
                "watermark_rows": connection.execute(
                    "SELECT count(*) FROM controlplane.cp_operation_stream_retention_watermarks").fetchone()[0],
                "p7a_auth_sessions_table": connection.execute(
                    "SELECT to_regclass('controlplane.cp_auth_sessions')").fetchone()[0] is not None,
                "p7a_technical_details_table": connection.execute(
                    "SELECT to_regclass('controlplane.cp_technical_details')").fetchone()[0] is not None,
            }
            assert preserved == {"stream_rows": before_count, "workspace_rows": 100,
                                 "watermark_rows": 1, "p7a_auth_sessions_table": True,
                                 "p7a_technical_details_table": True}
            _write_json(output / "rollback-preservation.json", preserved)
            connection.commit()
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            reapplied = [row[0] for row in connection.execute(
                "SELECT version FROM controlplane.cp_schema_migrations ORDER BY version")]
            assert reapplied == list(range(1, 9))
            assert connection.execute("SELECT to_regclass("
                "'controlplane.cp_operation_stream_workspace_cursor_idx')").fetchone()[0] is not None
            assert connection.execute("SELECT count(*) FROM controlplane.cp_operation_stream").fetchone()[0] == before_count
            _write_json(output / "tracker-reapply.json", reapplied)
        return {"forward": forward, "rollback": rollback, "reapply": reapplied,
                "rows": before_count, "post_index_plan": "PASS"}
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                          (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            assert admin.execute("SELECT count(*) FROM pg_database WHERE datname=%s",
                                 (name,)).fetchone()[0] == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_sha")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scope = _scope(args.source_sha)
    with psycopg.connect(os.environ["M2_TEST_PG_DSN"], autocommit=True) as connection:
        pg = connection.execute("SHOW server_version").fetchone()[0].split()[0]
        createdb = bool(connection.execute(
            "SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0])
    assert pg == "18.6" and createdb
    migration = migration_and_plan_proof(args.output_dir, os.environ["M2_TEST_PG_DSN"])
    with psycopg.connect(os.environ["M2_TEST_PG_DSN"], autocommit=True) as connection:
        orphan = connection.execute(
            "SELECT count(*) FROM pg_database WHERE datname LIKE 'm2_p7b_evidence_%'").fetchone()[0]
    assert orphan == 0
    _write_json(args.output_dir / "runtime-and-static.json", {
        **scope, "python": platform.python_version(),
        "psycopg": psycopg.__version__, "psycopg_pool": psycopg_pool.__version__,
        "fastapi": metadata.version("fastapi"), "uvicorn": metadata.version("uvicorn"),
        "httpx": metadata.version("httpx"), "postgresql": pg,
        "createdb": createdb, "m2_orphan_count": orphan,
        "uv_runtime_observed": subprocess.check_output(
            [str(ROOT / ".local-tools/uv/uv.exe"), "--version"], text=True).split()[1],
        "uv_lock_version": "0.12.13", "migration_proof": migration,
    })
    print("P7B_RUNTIME_STATIC_MIGRATION=PASS")


if __name__ == "__main__":
    main()
