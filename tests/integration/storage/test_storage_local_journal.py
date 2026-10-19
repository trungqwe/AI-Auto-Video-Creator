"""I-05: SqliteLocalJournal persists desktop recovery state durably (CT-STO-005, ADR-0006, INV-012)."""
import ast
import contextlib
import dataclasses
import pathlib
import sqlite3

import pytest

from controlplane.infrastructure.storage.local_journal import JournalEntry, SqliteLocalJournal, StaleGenerationError

ROOT = pathlib.Path(__file__).resolve().parents[3]
STORAGE_DIR = ROOT / "src" / "controlplane" / "infrastructure" / "storage"
EXPECTED_COLUMNS = ["device_ref", "session_ref", "job_ref", "stage_ref", "artifact_version_id", "local_location_ref", "operation_key", "generation", "lease_ref", "state", "checkpoint", "content_sha256", "upload_session_ref", "observed_at", "cleanup_eligible", "recovery_epoch"]
SECRET_URI = "https://upload.example.invalid/session?upload_id=CANARY-SECRET-TOKEN"


def make_entry(operation_key: str = "op-001", **overrides: object) -> JournalEntry:
    fields: dict[str, object] = {
        "device_ref": "device-01", "session_ref": "session-01", "job_ref": "job-01", "stage_ref": "stage-upload",
        "artifact_version_id": "11111111-1111-4111-8111-111111111111", "local_location_ref": "staging/job-01/output.mp4",
        "operation_key": operation_key, "generation": 1, "lease_ref": "lease-01", "state": "UPLOADING",
        "checkpoint": "offset=0", "content_sha256": "a" * 64, "upload_session_ref": "secret-ref://drive/session-01",
        "observed_at": "2026-10-19T00:00:00+00:00", "cleanup_eligible": False, "recovery_epoch": "epoch-1",
    }
    fields.update(overrides)
    return JournalEntry(**fields)


def keys(entries: list[JournalEntry]) -> list[str]:
    return [entry.operation_key for entry in entries]


@pytest.fixture
def db_path(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "journal.sqlite3"


@pytest.fixture
def journal(db_path: pathlib.Path):
    opened = SqliteLocalJournal(db_path)
    yield opened
    opened.close()


def test_package_init_is_single_line_docstring() -> None:
    source = (STORAGE_DIR / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert len(tree.body) == 1
    assert isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant)
    assert isinstance(tree.body[0].value.value, str)
    assert len(source.strip().splitlines()) == 1


def test_pragmas_are_wal_and_synchronous_full(journal: SqliteLocalJournal, db_path: pathlib.Path) -> None:
    assert journal.pragma_settings() == {"journal_mode": "wal", "synchronous": "full"}
    with contextlib.closing(sqlite3.connect(db_path)) as raw:
        assert raw.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_table_has_ct_sto_005_columns_and_unique_operation_key(journal: SqliteLocalJournal, db_path: pathlib.Path) -> None:
    journal.record(make_entry())
    with contextlib.closing(sqlite3.connect(db_path)) as raw:
        columns = [row[1] for row in raw.execute("PRAGMA table_info(local_journal_entries)").fetchall()]
        indexes = raw.execute("PRAGMA index_list(local_journal_entries)").fetchall()
        unique_columns = [[info[2] for info in raw.execute(f"PRAGMA index_info({index[1]})").fetchall()] for index in indexes if index[2] == 1]
    assert columns == EXPECTED_COLUMNS
    assert ["operation_key"] in unique_columns


def test_entries_survive_close_and_reopen(journal: SqliteLocalJournal, db_path: pathlib.Path) -> None:
    entries = [make_entry(f"op-{n:03d}", generation=n) for n in range(1, 4)]
    for entry in entries:
        journal.record(entry)
    journal.close()
    reopened = SqliteLocalJournal(db_path)
    try:
        assert [reopened.get(entry.operation_key) for entry in entries] == entries
        assert keys(reopened.list_unfinished()) == ["op-001", "op-002", "op-003"]
    finally:
        reopened.close()


def test_round_trip_preserves_none_bool_and_opaque_epoch(journal: SqliteLocalJournal) -> None:
    entry = make_entry("op-opaque", artifact_version_id=None, local_location_ref=None, lease_ref=None, checkpoint=None, content_sha256=None, upload_session_ref=None, cleanup_eligible=True, recovery_epoch="007")
    journal.record(entry)
    assert journal.get("op-opaque") == entry
    assert journal.get("op-missing") is None


def test_record_upserts_by_operation_key(journal: SqliteLocalJournal) -> None:
    journal.record(make_entry(generation=1, state="UPLOADING"))
    newer = make_entry(generation=2, state="UPLOADED", checkpoint="offset=1024")
    journal.record(newer)
    assert journal.get("op-001") == newer
    assert keys(journal.list_unfinished()) == ["op-001"]


def test_record_with_same_generation_replaces_entry(journal: SqliteLocalJournal) -> None:
    journal.record(make_entry(generation=3, checkpoint="offset=1"))
    again = make_entry(generation=3, checkpoint="offset=2")
    journal.record(again)
    assert journal.get("op-001") == again


def test_older_generation_is_rejected_and_never_overwrites(journal: SqliteLocalJournal) -> None:
    current = make_entry(generation=5, state="UPLOADED", checkpoint="offset=2048")
    journal.record(current)
    with pytest.raises(StaleGenerationError):
        journal.record(make_entry(generation=4, state="UPLOADING", checkpoint="offset=0"))
    with pytest.raises(StaleGenerationError):
        journal.mark_state("op-001", 4, "FAILED", "offset=0")
    assert journal.get("op-001") == current


def test_mark_state_updates_state_checkpoint_and_generation(journal: SqliteLocalJournal) -> None:
    journal.record(make_entry(generation=1))
    journal.mark_state("op-001", 1, "UPLOADED", "offset=2048")
    assert journal.get("op-001") == make_entry(generation=1, state="UPLOADED", checkpoint="offset=2048")
    journal.mark_state("op-001", 2, "VERIFIED", "hash-ok")
    assert journal.get("op-001") == make_entry(generation=2, state="VERIFIED", checkpoint="hash-ok")


def test_mark_state_unknown_operation_key_raises_key_error(journal: SqliteLocalJournal) -> None:
    with pytest.raises(KeyError):
        journal.mark_state("op-missing", 1, "UPLOADED", None)
    assert journal.list_unfinished() == []


def test_list_unfinished_excludes_terminal_states(journal: SqliteLocalJournal) -> None:
    journal.record(make_entry("op-a", state="UPLOADING"))
    journal.record(make_entry("op-b", state="COMPLETED"))
    journal.record(make_entry("op-c", state="ABANDONED"))
    journal.record(make_entry("op-d", state="OUTCOME_UNKNOWN"))
    assert keys(journal.list_unfinished()) == ["op-a", "op-d"]
    journal.mark_state("op-a", 1, "COMPLETED", "done")
    assert keys(journal.list_unfinished()) == ["op-d"]


def test_entries_from_other_epoch_lists_old_epochs_including_terminal(journal: SqliteLocalJournal) -> None:
    journal.record(make_entry("op-old", recovery_epoch="epoch-1"))
    journal.record(make_entry("op-old-done", recovery_epoch="epoch-1", state="COMPLETED"))
    journal.record(make_entry("op-new", recovery_epoch="epoch-2"))
    assert keys(journal.entries_from_other_epoch("epoch-2")) == ["op-old", "op-old-done"]
    assert keys(journal.entries_from_other_epoch("epoch-1")) == ["op-new"]
    assert keys(journal.entries_from_other_epoch("epoch-3")) == ["op-old", "op-old-done", "op-new"]


@pytest.mark.parametrize("uri", [
    SECRET_URI,
    "http://upload.example.invalid/session?id=CANARY-SECRET-TOKEN",
    "HTTPS://upload.example.invalid/CANARY-SECRET-TOKEN",
    "  https://upload.example.invalid/CANARY-SECRET-TOKEN",
])
def test_raw_session_uri_is_rejected_and_never_stored(journal: SqliteLocalJournal, db_path: pathlib.Path, uri: str) -> None:
    with pytest.raises(ValueError) as caught:
        journal.record(make_entry(upload_session_ref=uri))
    assert "CANARY-SECRET-TOKEN" not in str(caught.value)
    assert journal.get("op-001") is None
    journal.close()
    for suffix in ("", "-wal"):
        path = pathlib.Path(str(db_path) + suffix)
        if path.exists():
            assert b"CANARY-SECRET-TOKEN" not in path.read_bytes()


def test_raw_session_uri_does_not_replace_existing_secret_ref(journal: SqliteLocalJournal) -> None:
    current = make_entry(generation=1)
    journal.record(current)
    with pytest.raises(ValueError):
        journal.record(make_entry(generation=2, upload_session_ref=SECRET_URI))
    assert journal.get("op-001") == current


def test_failed_insert_rolls_back_and_leaves_no_entry(journal: SqliteLocalJournal, db_path: pathlib.Path) -> None:
    with pytest.raises(sqlite3.Error):
        journal.record(make_entry("op-bad", checkpoint=object()))
    with pytest.raises(sqlite3.IntegrityError):
        journal.record(make_entry("op-neg", generation=-1))
    assert journal.get("op-bad") is None
    assert journal.get("op-neg") is None
    good = make_entry("op-good")
    journal.record(good)
    assert journal.get("op-good") == good
    other = SqliteLocalJournal(db_path)
    try:
        assert keys(other.list_unfinished()) == ["op-good"]
    finally:
        other.close()


def test_failed_update_rolls_back_to_previous_entry(journal: SqliteLocalJournal) -> None:
    current = make_entry(generation=1, checkpoint="offset=1")
    journal.record(current)
    with pytest.raises(sqlite3.Error):
        journal.record(make_entry(generation=2, checkpoint=object()))
    with pytest.raises(sqlite3.Error):
        journal.mark_state("op-001", 2, "UPLOADED", object())
    assert journal.get("op-001") == current
    journal.mark_state("op-001", 2, "UPLOADED", "offset=2")
    assert journal.get("op-001") == dataclasses.replace(current, generation=2, state="UPLOADED", checkpoint="offset=2")


def test_public_api_has_no_delete_function() -> None:
    names = sorted(name for name in dir(SqliteLocalJournal) if not name.startswith("_"))
    assert names == ["close", "entries_from_other_epoch", "get", "list_unfinished", "mark_state", "pragma_settings", "record"]


def test_module_source_has_no_delete_no_video_completed_and_only_stdlib_sqlite() -> None:
    source = (STORAGE_DIR / "local_journal.py").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "delete" not in lowered
    assert "videocompleted" not in lowered
    tree = ast.parse(source)
    roots = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    roots |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "sqlite3" in roots
    assert roots <= {"__future__", "collections", "contextlib", "dataclasses", "pathlib", "sqlite3"}
