"""Tests for epoch quarantine, cleanup evaluation, and file integrity in local journal (TST-M1-P4-004..006)."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
import pytest
from m1proof.local_journal import (
    AtomicFileWriter,
    LocalCleanupEvaluator,
    LocalJournalDB,
    LocalRecoveryEngine,
)

def test_tst_m1_p4_004_stale_epoch_or_generation_quarantined(
    staging_env: dict[str, Path],
    journal_db: LocalJournalDB,
    cloud_verifier: Any,
):
    """TST-M1-P4-004: Stale recovery epoch or old generation entries are quarantined; no mutation permitted."""
    target_file = staging_env["staging"] / "artifact_p4_004.mp4"
    target_file.write_bytes(b"DATA_EPOCH_1")
    file_hash = hashlib.sha256(b"DATA_EPOCH_1").hexdigest()

    entry_id = journal_db.record_entry(
        operation_key="op_epoch_old_004",
        artifact_id="art_004",
        version_hash=file_hash,
        local_path=str(target_file),
        stage="ENCODE",
        recovery_epoch=1,
        generation=1,
        status="PENDING",
    )

    # Hệ thống chuyển sang Recovery Epoch 2 (ví dụ sau sự cố khôi phục / rebuild control state)
    engine = LocalRecoveryEngine(journal_db, cloud_verifier, active_epoch=2)
    reconcile_result = engine.reconcile_startup()

    # Oracle: entry từ epoch 1 bị đưa vào quarantined, không được gửi lên cloud
    assert "op_epoch_old_004" in [e["operation_key"] for e in reconcile_result["quarantined"]]
    updated_entry = journal_db.get_entry(entry_id)
    assert updated_entry["status"] == "QUARANTINED"


def test_tst_m1_p4_005_cache_eviction_protects_unsent_journal_and_active_refs(
    staging_env: dict[str, Path],
    journal_db: LocalJournalDB,
):
    """TST-M1-P4-005: Cache eviction allows clearing verified cache but strictly protects active journal refs."""
    evaluator = LocalCleanupEvaluator()
    writer = AtomicFileWriter()

    # 1. Tệp Cache thuần túy: đã xác minh trên cloud, không còn journal reference
    cache_file = staging_env["cache"] / "cache_artifact_005.mp4"
    writer.write_file_atomic(cache_file, b"CACHE_DATA_ALREADY_ON_CLOUD")

    eligible, reason = evaluator.evaluate_cleanup(
        target_path=cache_file,
        active_epoch=1,
        journal_db=journal_db,
        is_cache=True,
        cloud_verified=True,
    )
    assert eligible is True
    assert reason == "CACHE_EXPIRED_AND_CLOUD_VERIFIED"

    # 2. Tệp Staging đang có Unsent Journal reference
    staging_file = staging_env["staging"] / "staging_artifact_unsent_005.mp4"
    file_hash = hashlib.sha256(b"UNSENT_DATA").hexdigest()
    writer.write_file_atomic(staging_file, b"UNSENT_DATA", expected_hash=file_hash)

    journal_db.record_entry(
        operation_key="op_active_ref_005",
        artifact_id="art_005",
        version_hash=file_hash,
        local_path=str(staging_file),
        stage="UPLOAD",
        recovery_epoch=1,
        generation=1,
        status="COMPLETED_LOCALLY",
    )

    eligible_active, reason_active = evaluator.evaluate_cleanup(
        target_path=staging_file,
        active_epoch=1,
        journal_db=journal_db,
        is_cache=False,
        cloud_verified=False,
    )
    # Oracle: Cấm xóa tệp đang có journal tham chiếu active hoặc chưa gửi
    assert eligible_active is False
    assert "ACTIVE_JOURNAL_REFERENCE" in reason_active or "NOT_CLOUD_VERIFIED" in reason_active


def test_tst_m1_p4_006_file_missing_or_hash_mismatch_detected(
    staging_env: dict[str, Path],
    journal_db: LocalJournalDB,
    cloud_verifier: Any,
):
    """TST-M1-P4-006: Missing local file or hash mismatch keeps error/unknown state; never claims success."""
    # Case A: Tệp vật lý không tồn tại trên đĩa
    missing_file = staging_env["staging"] / "non_existent_006.mp4"
    entry_missing_id = journal_db.record_entry(
        operation_key="op_missing_file_006",
        artifact_id="art_006_missing",
        version_hash="expected_hash_006_a",
        local_path=str(missing_file),
        stage="RENDER",
        recovery_epoch=1,
        generation=1,
        status="COMPLETED_LOCALLY",
    )

    # Case B: Tệp vật lý có tồn tại nhưng bị thay đổi nội dung byte (hash mismatch)
    tampered_file = staging_env["staging"] / "tampered_006.mp4"
    tampered_file.write_bytes(b"CORRUPTED_TAMPERED_CONTENT")
    actual_tampered_hash = hashlib.sha256(b"CORRUPTED_TAMPERED_CONTENT").hexdigest()
    different_expected_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    entry_tampered_id = journal_db.record_entry(
        operation_key="op_tampered_file_006",
        artifact_id="art_006_tampered",
        version_hash=different_expected_hash,
        local_path=str(tampered_file),
        stage="RENDER",
        recovery_epoch=1,
        generation=1,
        status="COMPLETED_LOCALLY",
    )

    engine = LocalRecoveryEngine(journal_db, cloud_verifier, active_epoch=1)
    reconcile_result = engine.reconcile_startup()

    # Oracle: Cả 2 trường hợp đều bị phát hiện trong corrupt_or_missing và chuyển trạng thái lỗi
    corrupt_keys = [e["operation_key"] for e in reconcile_result["corrupt_or_missing"]]
    assert "op_missing_file_006" in corrupt_keys
    assert "op_tampered_file_006" in corrupt_keys

    entry_a = journal_db.get_entry(entry_missing_id)
    assert entry_a["status"] == "CORRUPT_OR_MISSING"

    entry_b = journal_db.get_entry(entry_tampered_id)
    assert entry_b["status"] == "CORRUPT_OR_MISSING"
