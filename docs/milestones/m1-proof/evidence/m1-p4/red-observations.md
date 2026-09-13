# M1-P4 — Red Observations (Test-First Evidence)

**Ngày ghi nhận:** 13-09-2026  
**Lệnh thực thi:** `py -3.13 -m uv run --frozen pytest tests/m1/p4 -v`  
**Kết quả quan sát:** 6 FAILED in 0.09s (Exit Code: 1)

## Danh sách các ca kiểm thử thất bại theo đúng Oracle

| Test ID | Tên ca kiểm thử | Nguyên nhân RED quan sát được |
|---|---|---|
| `TST-M1-P4-001` | `test_tst_m1_p4_001_crash_after_artifact_complete_resends_operation` | `NotImplementedError: Stub: write_file_atomic not yet implemented` |
| `TST-M1-P4-002` | `test_tst_m1_p4_002_crash_during_write_or_rename_rejects_partial_byte` | `NotImplementedError: Stub: write_file_atomic not yet implemented` |
| `TST-M1-P4-003` | `test_tst_m1_p4_003_lost_ack_reconciles_existing_cloud_receipt` | `NotImplementedError: Stub: write_file_atomic not yet implemented` |
| `TST-M1-P4-004` | `test_tst_m1_p4_004_stale_epoch_or_generation_quarantined` | `NotImplementedError: Stub: record_entry not yet implemented` |
| `TST-M1-P4-005` | `test_tst_m1_p4_005_cache_eviction_protects_unsent_journal_and_active_refs` | `NotImplementedError: Stub: write_file_atomic not yet implemented` |
| `TST-M1-P4-006` | `test_tst_m1_p4_006_file_missing_or_hash_mismatch_detected` | `NotImplementedError: Stub: record_entry not yet implemented` |

## Trích xuất log kiểm thử RED

```text
=========================== short test summary info ===========================
FAILED tests/m1/p4/test_journal_crash_recovery.py::test_tst_m1_p4_001_crash_after_artifact_complete_resends_operation
FAILED tests/m1/p4/test_journal_crash_recovery.py::test_tst_m1_p4_002_crash_during_write_or_rename_rejects_partial_byte
FAILED tests/m1/p4/test_journal_crash_recovery.py::test_tst_m1_p4_003_lost_ack_reconciles_existing_cloud_receipt
FAILED tests/m1/p4/test_journal_epoch_and_cleanup.py::test_tst_m1_p4_004_stale_epoch_or_generation_quarantined
FAILED tests/m1/p4/test_journal_epoch_and_cleanup.py::test_tst_m1_p4_005_cache_eviction_protects_unsent_journal_and_active_refs
FAILED tests/m1/p4/test_journal_epoch_and_cleanup.py::test_tst_m1_p4_006_file_missing_or_hash_mismatch_detected
============================== 6 failed in 0.09s ==============================
```

## Kết luận
Bằng chứng RED được xác nhận hợp lệ: thất bại hoàn toàn do thiếu mã nguồn nghiệp vụ thực tế, không có lỗi cấu hình hay thiếu gói môi trường.
