from pathlib import Path

import psycopg


ROOT = Path(__file__).parents[3]
UP = ROOT / "sql" / "m1" / "remediation_r1_up.sql"
DOWN = ROOT / "sql" / "m1" / "remediation_r1_down.sql"
DSN = "postgresql://postgres@127.0.0.1:55432/aiavc_m1"
TABLES = [
    "workspace_epochs",
    "execution_grants_v2",
    "accepted_activity_results_v2",
    "operation_receipts_v2",
    "completion_admissions",
]


def remediation_table_count(connection: psycopg.Connection) -> int:
    return connection.execute(
        """
        SELECT count(*) FROM pg_tables
         WHERE schemaname = 'public' AND tablename = ANY(%s)
        """,
        (TABLES,),
    ).fetchone()[0]


def test_remediation_migration_moves_forward_and_back() -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(UP.read_text(encoding="utf-8"))
        assert remediation_table_count(connection) == len(TABLES)
        connection.execute(DOWN.read_text(encoding="utf-8"))
        assert remediation_table_count(connection) == 0
        connection.execute(UP.read_text(encoding="utf-8"))
        assert remediation_table_count(connection) == len(TABLES)
