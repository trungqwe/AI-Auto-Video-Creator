# M1-P5 — Red Observations (Test-First Evidence)

**Ngày ghi nhận ban đầu:** 13-09-2026  
**Lệnh thực thi ban đầu:** `py -3.13 -m uv run --frozen pytest tests/m1/p5 -v`  
**Kết quả quan sát ban đầu:** 6 FAILED in 0.08s (Exit Code: 1)

---

## 1. Danh sách các ca kiểm thử thất bại ban đầu theo đúng Oracle

| Test ID | Tên ca kiểm thử | Nguyên nhân RED quan sát được |
|---|---|---|
| `TST-M1-P5-001` | `test_tst_m1_p5_001_exact_python_uv_and_frozen_lock_integrity` | `NotImplementedError: Stub: check_runtime_environment not implemented` |
| `TST-M1-P5-002` | `test_tst_m1_p5_002_postgresql_connection_rollback_and_vietnamese_utf8` | `NotImplementedError: Stub: check_postgresql_compat not implemented` |
| `TST-M1-P5-003` | `test_tst_m1_p5_003_temporal_sdk_and_server_handshake_smoke` | `NotImplementedError: Stub: check_temporal_compat not implemented` |
| `TST-M1-P5-004` | `test_tst_m1_p5_004_google_client_boundaries_and_missing_credential_classification` | `NotImplementedError: Stub: check_google_client_boundaries not implemented` |
| `TST-M1-P5-005` | `test_tst_m1_p5_005_ffmpeg_version_buildconf_and_safe_probe` | `NotImplementedError: Stub: check_ffmpeg_compat not implemented` |
| `TST-M1-P5-006` | `test_tst_m1_p5_006_evidence_hash_mismatch_and_unsupported_version_rejected` | `NotImplementedError: Stub: verify_evidence_integrity not implemented` |

---

## 2. Ghi nhận Độ lệch Lịch sử (Historical Deviation Note)

> [!WARNING]
> **Deviation: `RED_EVIDENCE_MISSING_FOR_R3_REMEDIATION`**  
> Trong đợt kiểm toán độc lập R3, ca kiểm thử `TST-M1-P5-007` (machine-readable compatibility matrix) đã được phát triển để bổ sung ma trận JSON nhưng chưa lưu tách riêng tệp log stdout của giai đoạn RED. Độ lệch này được ghi nhận công khai theo nguyên tắc minh bạch dữ liệu kiểm toán.

---

## 3. Bằng chứng Quan sát RED Đợt Audit R4 (R4-03 Evidence)

Trước khi thực hiện cải tiến R4 (Dynamic Matrix Observation từ runtime thực tế), bài kiểm thử `TST-M1-P5-008` đã được tạo lập trước và chứng kiến trạng thái RED đúng oracle:

- **Lệnh thực thi:** `pytest tests/m1/p5/test_compatibility_smoke.py -k test_tst_m1_p5_008_dynamic_matrix_observation -v`
- **Kết quả:** `FAILED` đúng oracle (exit code 1).
- **Hiện tượng quan sát:** `AssertionError: assert 'timestamp' in matrix` (hoặc hardcoded static assertion mismatch khi đo runtime động).
- **Tệp bằng chứng thô:** `docs/milestones/m1-proof/evidence/m1-p6/red-r4-stdout.txt`
