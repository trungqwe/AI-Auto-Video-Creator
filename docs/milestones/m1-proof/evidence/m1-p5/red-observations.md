# M1-P5 — Red Observations (Test-First Evidence)

**Ngày ghi nhận:** 13-09-2026  
**Lệnh thực thi:** `py -3.13 -m uv run --frozen pytest tests/m1/p5 -v`  
**Kết quả quan sát:** 6 FAILED in 0.08s (Exit Code: 1)

## Danh sách các ca kiểm thử thất bại theo đúng Oracle

| Test ID | Tên ca kiểm thử | Nguyên nhân RED quan sát được |
|---|---|---|
| `TST-M1-P5-001` | `test_tst_m1_p5_001_exact_python_uv_and_frozen_lock_integrity` | `NotImplementedError: Stub: check_runtime_environment not implemented` |
| `TST-M1-P5-002` | `test_tst_m1_p5_002_postgresql_connection_rollback_and_vietnamese_utf8` | `NotImplementedError: Stub: check_postgresql_compat not implemented` |
| `TST-M1-P5-003` | `test_tst_m1_p5_003_temporal_sdk_and_server_handshake_smoke` | `NotImplementedError: Stub: check_temporal_compat not implemented` |
| `TST-M1-P5-004` | `test_tst_m1_p5_004_google_client_boundaries_and_missing_credential_classification` | `NotImplementedError: Stub: check_google_client_boundaries not implemented` |
| `TST-M1-P5-005` | `test_tst_m1_p5_005_ffmpeg_version_buildconf_and_safe_probe` | `NotImplementedError: Stub: check_ffmpeg_compat not implemented` |
| `TST-M1-P5-006` | `test_tst_m1_p5_006_evidence_hash_mismatch_and_unsupported_version_rejected` | `NotImplementedError: Stub: verify_evidence_integrity not implemented` |

## Trích xuất log kiểm thử RED

```text
=========================== short test summary info ===========================
FAILED tests/m1/p5/test_compatibility_smoke.py::test_tst_m1_p5_001_exact_python_uv_and_frozen_lock_integrity
FAILED tests/m1/p5/test_compatibility_smoke.py::test_tst_m1_p5_002_postgresql_connection_rollback_and_vietnamese_utf8
FAILED tests/m1/p5/test_compatibility_smoke.py::test_tst_m1_p5_003_temporal_sdk_and_server_handshake_smoke
FAILED tests/m1/p5/test_compatibility_smoke.py::test_tst_m1_p5_004_google_client_boundaries_and_missing_credential_classification
FAILED tests/m1/p5/test_compatibility_smoke.py::test_tst_m1_p5_005_ffmpeg_version_buildconf_and_safe_probe
FAILED tests/m1/p5/test_compatibility_smoke.py::test_tst_m1_p5_006_evidence_hash_mismatch_and_unsupported_version_rejected
============================== 6 failed in 0.08s ==============================
```

## Kết luận
Bằng chứng RED được xác nhận hợp lệ: toàn bộ 6 bài test thất bại thuần túy do thiếu mã nguồn nghiệp vụ thực tế, không có lỗi cấu hình hay thiếu package môi trường.
