"""SQLite local journal for desktop recovery state (CT-STO-005, ADR-0006)."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

TERMINAL_STATES = frozenset({"COMPLETED", "ABANDONED"})
_RAW_URI_PREFIXES = ("http://", "https://")
_SYNCHRONOUS_NAMES = {0: "off", 1: "normal", 2: "full", 3: "extra"}
_COLUMNS = ("device_ref", "session_ref", "job_ref", "stage_ref", "artifact_version_id", "local_location_ref", "operation_key", "generation", "lease_ref", "state", "checkpoint", "content_sha256", "upload_session_ref", "observed_at", "cleanup_eligible", "recovery_epoch")
_SCHEMA = """CREATE TABLE IF NOT EXISTS local_journal_entries (
    device_ref TEXT NOT NULL,
    session_ref TEXT NOT NULL,
    job_ref TEXT NOT NULL,
    stage_ref TEXT NOT NULL,
    artifact_version_id TEXT,
    local_location_ref TEXT,
    operation_key TEXT NOT NULL UNIQUE,
    generation INTEGER NOT NULL CHECK (generation >= 0),
    lease_ref TEXT,
    state TEXT NOT NULL,
    checkpoint TEXT,
    content_sha256 TEXT,
    upload_session_ref TEXT CHECK (upload_session_ref IS NULL OR (upload_session_ref NOT LIKE 'http://%' AND upload_session_ref NOT LIKE 'https://%')),
    observed_at TEXT NOT NULL,
    cleanup_eligible INTEGER NOT NULL DEFAULT 0 CHECK (cleanup_eligible IN (0, 1)),
    recovery_epoch TEXT NOT NULL
)"""
_SELECT = "SELECT " + ", ".join(_COLUMNS) + " FROM local_journal_entries"
_SELECT_GENERATION = "SELECT generation FROM local_journal_entries WHERE operation_key=?"
_INSERT = "INSERT INTO local_journal_entries (" + ", ".join(_COLUMNS) + ") VALUES (" + ", ".join("?" for _ in _COLUMNS) + ")"
_UPDATE = "UPDATE local_journal_entries SET " + ", ".join(f"{name}=?" for name in _COLUMNS) + " WHERE operation_key=?"
_UNFINISHED = _SELECT + " WHERE state NOT IN (" + ", ".join("?" for _ in TERMINAL_STATES) + ") ORDER BY rowid"


@dataclass(frozen=True, slots=True)
class JournalEntry:
    device_ref: str
    session_ref: str
    job_ref: str
    stage_ref: str
    operation_key: str
    generation: int
    state: str
    observed_at: str
    recovery_epoch: str
    artifact_version_id: str | None = None
    local_location_ref: str | None = None
    lease_ref: str | None = None
    checkpoint: str | None = None
    content_sha256: str | None = None
    upload_session_ref: str | None = None
    cleanup_eligible: bool = False


class StaleGenerationError(Exception):
    """Raised when a write carries a generation lower than the stored one."""


class SqliteLocalJournal:
    def __init__(self, db_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            mode = self._connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise RuntimeError("local journal requires WAL journal mode")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute(_SCHEMA)
        except BaseException:
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def pragma_settings(self) -> dict[str, str]:
        mode = self._connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = self._connection.execute("PRAGMA synchronous").fetchone()[0]
        return {"journal_mode": str(mode).lower(), "synchronous": _SYNCHRONOUS_NAMES.get(synchronous, str(synchronous))}

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")

    def record(self, entry: JournalEntry) -> JournalEntry:
        _reject_raw_session_uri(entry.upload_session_ref)
        values = _values(entry)
        with self._transaction() as connection:
            row = connection.execute(_SELECT_GENERATION, (entry.operation_key,)).fetchone()
            if row is None:
                connection.execute(_INSERT, values)
            elif entry.generation < row[0]:
                raise StaleGenerationError(f"generation {entry.generation} is older than stored generation {row[0]}")
            else:
                connection.execute(_UPDATE, values + (entry.operation_key,))
        return entry

    def get(self, operation_key: str) -> JournalEntry | None:
        row = self._connection.execute(_SELECT + " WHERE operation_key=?", (operation_key,)).fetchone()
        return None if row is None else _entry(row)

    def list_unfinished(self) -> list[JournalEntry]:
        rows = self._connection.execute(_UNFINISHED, tuple(sorted(TERMINAL_STATES))).fetchall()
        return [_entry(row) for row in rows]

    def mark_state(self, operation_key: str, generation: int, state: str, checkpoint: str | None) -> JournalEntry:
        with self._transaction() as connection:
            row = connection.execute(_SELECT_GENERATION, (operation_key,)).fetchone()
            if row is None:
                raise KeyError(operation_key)
            if generation < row[0]:
                raise StaleGenerationError(f"generation {generation} is older than stored generation {row[0]}")
            connection.execute("UPDATE local_journal_entries SET generation=?, state=?, checkpoint=? WHERE operation_key=?", (generation, state, checkpoint, operation_key))
            return _entry(connection.execute(_SELECT + " WHERE operation_key=?", (operation_key,)).fetchone())

    def entries_from_other_epoch(self, current_epoch: str) -> list[JournalEntry]:
        rows = self._connection.execute(_SELECT + " WHERE recovery_epoch <> ? ORDER BY rowid", (str(current_epoch),)).fetchall()
        return [_entry(row) for row in rows]


def _reject_raw_session_uri(reference: str | None) -> None:
    if isinstance(reference, str) and reference.strip().lower().startswith(_RAW_URI_PREFIXES):
        raise ValueError("upload_session_ref must be a secret reference, not a raw session URI")


def _values(entry: JournalEntry) -> tuple[object, ...]:
    return tuple(int(getattr(entry, name)) if name == "cleanup_eligible" else getattr(entry, name) for name in _COLUMNS)


def _entry(row: tuple[object, ...]) -> JournalEntry:
    fields = dict(zip(_COLUMNS, row))
    fields["cleanup_eligible"] = bool(fields["cleanup_eligible"])
    return JournalEntry(**fields)


__all__ = ["JournalEntry", "SqliteLocalJournal", "StaleGenerationError"]
