from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import pytest

REPOSITORY_ROOT = Path(__file__).parents[3]
src_path = str(REPOSITORY_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from m1proof.local_journal import LocalJournalDB

class MockCloudReceiptVerifier:
    """Mock verifier conforming to P1 cloud operation receipt port."""
    def __init__(self) -> None:
        self._receipts: Dict[str, Dict[str, Any]] = {}

    def register_receipt(self, operation_key: str, status: str, receipt_id: str, artifact_id: Optional[str] = None) -> None:
        self._receipts[operation_key] = {
            "operation_key": operation_key,
            "status": status,
            "receipt_id": receipt_id,
            "artifact_id": artifact_id or f"art_{receipt_id}",
        }

    def get_operation_receipt(self, operation_key: str) -> Optional[Dict[str, Any]]:
        return self._receipts.get(operation_key)


@pytest.fixture
def staging_env(tmp_path: Path) -> Dict[str, Path]:
    """Provide isolated directory paths for staging, cache, and temporary files."""
    staging_root = tmp_path / "staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return {
        "root": tmp_path,
        "staging": staging_root,
        "cache": cache_dir,
        "temp": temp_dir,
    }


@pytest.fixture
def journal_db(tmp_path: Path) -> LocalJournalDB:
    """Provide a fresh LocalJournalDB instance on a temporary SQLite database."""
    db_file = tmp_path / "journal_test.db"
    return LocalJournalDB(db_file)


@pytest.fixture
def cloud_verifier() -> MockCloudReceiptVerifier:
    """Provide a fresh mock cloud receipt verifier."""
    return MockCloudReceiptVerifier()
