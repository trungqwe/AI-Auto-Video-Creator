"""Local Journal and Recovery Proof module for M1-P4.

Provides durable SQLite journal storage on desktop, atomic file finalization on Windows,
startup reconciliation with cloud receipt verification, and recovery epoch quarantine.
"""
from __future__ import annotations
import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from contextlib import contextmanager

class LocalJournalDB:
    """SQLite local journal storage for desktop workstation."""
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_key TEXT UNIQUE NOT NULL,
                    artifact_id TEXT NOT NULL,
                    version_hash TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    recovery_epoch INTEGER NOT NULL,
                    generation INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS cleanup_authorizations (
                    auth_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local_path TEXT NOT NULL,
                    version_hash TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    recovery_epoch INTEGER NOT NULL,
                    expires_at_utc TEXT NOT NULL,
                    status TEXT NOT NULL
                );
            """)

    def record_entry(
        self,
        operation_key: str,
        artifact_id: str,
        version_hash: str,
        local_path: str,
        stage: str,
        recovery_epoch: int,
        generation: int,
        status: str = "PENDING",
    ) -> int:
        norm_path = str(Path(local_path))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO journal_entries (
                    operation_key, artifact_id, version_hash, local_path, stage,
                    recovery_epoch, generation, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(operation_key) DO UPDATE SET
                    artifact_id = excluded.artifact_id,
                    version_hash = excluded.version_hash,
                    local_path = excluded.local_path,
                    stage = excluded.stage,
                    recovery_epoch = excluded.recovery_epoch,
                    generation = excluded.generation,
                    status = excluded.status,
                    updated_at_utc = CURRENT_TIMESTAMP
            """, (operation_key, artifact_id, version_hash, norm_path, stage, recovery_epoch, generation, status))
            conn.commit()
            return cursor.lastrowid

    def update_status(self, entry_id: int, status: str) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE journal_entries
                SET status = ?, updated_at_utc = CURRENT_TIMESTAMP
                WHERE entry_id = ?
            """, (status, entry_id))
            conn.commit()

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM journal_entries WHERE entry_id = ?", (entry_id,)).fetchone()
            return dict(row) if row else None

    def get_entries_by_status(self, statuses: List[str]) -> List[Dict[str, Any]]:
        if not statuses:
            return []
        placeholders = ",".join("?" for _ in statuses)
        with self._get_connection() as conn:
            rows = conn.execute(f"SELECT * FROM journal_entries WHERE status IN ({placeholders})", statuses).fetchall()
            return [dict(r) for r in rows]

    def get_all_entries(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM journal_entries").fetchall()
            return [dict(r) for r in rows]

    def quarantine_entries_older_than_epoch(self, active_epoch: int) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE journal_entries
                SET status = 'QUARANTINED', updated_at_utc = CURRENT_TIMESTAMP
                WHERE recovery_epoch < ? AND status NOT IN ('COMMITTED_ON_CLOUD', 'QUARANTINED')
            """, (active_epoch,))
            conn.commit()
            return cursor.rowcount

    def create_cleanup_authorization(
        self,
        local_path: str,
        version_hash: str,
        reason: str,
        recovery_epoch: int,
        expires_at_utc: str,
    ) -> int:
        norm_path = str(Path(local_path))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cleanup_authorizations (
                    local_path, version_hash, reason, recovery_epoch, expires_at_utc, status
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE')
            """, (norm_path, version_hash, reason, recovery_epoch, expires_at_utc))
            conn.commit()
            return cursor.lastrowid

    def get_active_cleanup_authorization(self, local_path: str, active_epoch: int) -> Optional[Dict[str, Any]]:
        norm_path = str(Path(local_path))
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM cleanup_authorizations
                WHERE local_path = ? AND recovery_epoch = ? AND status = 'ACTIVE'
            """, (norm_path, active_epoch)).fetchone()
            return dict(row) if row else None

    def has_active_journal_reference(self, local_path: str) -> bool:
        norm_path = str(Path(local_path))
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT 1 FROM journal_entries
                WHERE local_path = ? AND status IN ('PENDING', 'COMPLETED_LOCALLY', 'SUBMITTED')
            """, (norm_path,)).fetchone()
            return row is not None


class AtomicFileWriter:
    """Atomic file writer with temp-file write, fsync, and atomic rename on Windows."""
    def write_file_atomic(
        self,
        target_path: Path,
        data: bytes,
        expected_hash: Optional[str] = None,
    ) -> Tuple[int, str]:
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        actual_hash = hashlib.sha256(data).hexdigest()
        if expected_hash and actual_hash != expected_hash:
            raise ValueError(f"Hash mismatch: expected {expected_hash}, got {actual_hash}")

        # Tạo file tạm trong cùng thư mục đích để bảo đảm atomic rename trên cùng volume
        tmp_file = target.parent / f"{target.name}.{os.getpid()}_{id(data)}.tmp"
        try:
            with open(tmp_file, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace trên Windows (os.replace ghi đè an toàn và nguyên tử)
            os.replace(tmp_file, target)
        except Exception:
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass
            raise

        return len(data), actual_hash


class LocalRecoveryEngine:
    """Startup reconciliation engine for local journal and recovery epoch."""
    def __init__(self, journal_db: LocalJournalDB, cloud_receipt_verifier: Any, active_epoch: int = 1) -> None:
        self.journal_db = journal_db
        self.cloud_receipt_verifier = cloud_receipt_verifier
        self.active_epoch = active_epoch

    def reconcile_startup(self) -> Dict[str, Any]:
        # 1. Cách ly các entry thuộc về recovery epoch cũ
        self.journal_db.quarantine_entries_older_than_epoch(self.active_epoch)

        pending_resend = []
        reconciled_with_cloud = []
        quarantined = []
        corrupt_or_missing = []

        all_entries = self.journal_db.get_all_entries()

        for entry in all_entries:
            if entry["status"] == "QUARANTINED":
                quarantined.append(entry)
                continue

            if entry["status"] in ("PENDING", "COMPLETED_LOCALLY", "SUBMITTED"):
                file_path = Path(entry["local_path"])
                # Kiểm tra tệp vật lý trên đĩa
                if not file_path.is_file():
                    self.journal_db.update_status(entry["entry_id"], "CORRUPT_OR_MISSING")
                    corrupt_or_missing.append(entry)
                    continue

                # Kiểm tra toàn vẹn hash
                observed_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                if observed_hash != entry["version_hash"]:
                    self.journal_db.update_status(entry["entry_id"], "CORRUPT_OR_MISSING")
                    corrupt_or_missing.append(entry)
                    continue

                # Đối soát với Cloud Receipt nếu có verifier
                if self.cloud_receipt_verifier is not None:
                    cloud_rcpt = self.cloud_receipt_verifier.get_operation_receipt(entry["operation_key"])
                    if cloud_rcpt and cloud_rcpt.get("status") == "COMMITTED":
                        self.journal_db.update_status(entry["entry_id"], "COMMITTED_ON_CLOUD")
                        reconciled_with_cloud.append(entry)
                        continue

                # Tệp toàn vẹn nhưng cloud chưa commit -> Cần gửi lại
                pending_resend.append(entry)

        return {
            "active_epoch": self.active_epoch,
            "pending_resend": pending_resend,
            "reconciled_with_cloud": reconciled_with_cloud,
            "quarantined": quarantined,
            "corrupt_or_missing": corrupt_or_missing,
        }


class LocalCleanupEvaluator:
    """Evaluates whether a local artifact file is eligible for cleanup."""
    def evaluate_cleanup(
        self,
        target_path: Path,
        active_epoch: int,
        journal_db: LocalJournalDB,
        is_cache: bool = True,
        cloud_verified: bool = True,
    ) -> Tuple[bool, str]:
        target_str = str(Path(target_path))

        # Invariant 1: Tuyệt đối không dọn tệp đang có journal tham chiếu active hoặc unsent
        if journal_db.has_active_journal_reference(target_str):
            return False, "ACTIVE_JOURNAL_REFERENCE"

        # Invariant 2: Tệp staging phải được xác nhận trên cloud mới được xóa
        if not is_cache and not cloud_verified:
            return False, "NOT_CLOUD_VERIFIED"

        # Invariant 3: Tệp cache thuần túy đã xác minh cloud và hết lease -> cho phép dọn
        if is_cache and cloud_verified:
            return True, "CACHE_EXPIRED_AND_CLOUD_VERIFIED"

        # Invariant 4: Kiểm tra Authorization hợp lệ cùng epoch
        auth = journal_db.get_active_cleanup_authorization(target_str, active_epoch)
        if auth is not None:
            return True, f"AUTHORIZED_BY_{auth['reason']}"

        return False, "CLEANUP_DENIED_DEFAULT"
