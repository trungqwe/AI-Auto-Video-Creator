# M1-P6 — Red Observations (Test-First Evidence)

**Ngày ghi nhận:** 13-09-2026  
**Lệnh thực thi:** `py -3.13 -m uv run --frozen pytest tests/m1/p6 -v`  
**Kết quả quan sát:** 5 FAILED in 0.07s (Exit Code: 1)

## Danh sách các ca kiểm thử thất bại theo đúng Oracle

| Test ID | Tên ca kiểm thử | Nguyên nhân RED quan sát được |
|---|---|---|
| `TST-M1-P6-001` | `test_tst_m1_p6_001_manifest_schema_and_completeness_validation` | `NotImplementedError: Stub: validate_manifest_schema not implemented` |
| `TST-M1-P6-002` | `test_tst_m1_p6_002_artifact_hash_tampering_and_missing_file_detection` | `NotImplementedError: Stub: validate_manifest_artifacts not implemented` |
| `TST-M1-P6-003` | `test_tst_m1_p6_003_milestone_exit_rule_engine_gate_enforcement` | `NotImplementedError: Stub: evaluate_milestone_gates not implemented` |
| `TST-M1-P6-004` | `test_tst_m1_p6_004_scoped_gate_boundary_protection` | `NotImplementedError: Stub: evaluate_milestone_gates not implemented` |
| `TST-M1-P6-005` | `test_tst_m1_p6_005_secret_and_canary_scanner_fail_closed` | `NotImplementedError: Stub: scan_secrets_in_directory not implemented` |

## Trích xuất log kiểm thử RED

```text
=========================== short test summary info ===========================
FAILED tests/m1/p6/test_evidence_audit.py::test_tst_m1_p6_001_manifest_schema_and_completeness_validation
FAILED tests/m1/p6/test_evidence_audit.py::test_tst_m1_p6_002_artifact_hash_tampering_and_missing_file_detection
FAILED tests/m1/p6/test_evidence_audit.py::test_tst_m1_p6_003_milestone_exit_rule_engine_gate_enforcement
FAILED tests/m1/p6/test_evidence_audit.py::test_tst_m1_p6_004_scoped_gate_boundary_protection
FAILED tests/m1/p6/test_evidence_audit.py::test_tst_m1_p6_005_secret_and_canary_scanner_fail_closed
============================== 5 failed in 0.07s ==============================
```

## Kết luận
Bằng chứng RED được xác nhận hợp lệ: toàn bộ 5 bài test thất bại thuần túy do thiếu mã nguồn nghiệp vụ thực tế trong stub, không có lỗi cấu hình hay thiếu package môi trường.
