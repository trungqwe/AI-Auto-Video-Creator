# M1-P6 — Red Observations (Test-First Evidence)

**Ngày ghi nhận ban đầu:** 13-09-2026  
**Lệnh thực thi ban đầu:** `py -3.13 -m uv run --frozen pytest tests/m1/p6 -v`  
**Kết quả quan sát ban đầu:** 5 FAILED in 0.07s (Exit Code: 1)

---

## 1. Danh sách các ca kiểm thử thất bại ban đầu theo đúng Oracle

| Test ID | Tên ca kiểm thử | Nguyên nhân RED quan sát được |
|---|---|---|
| `TST-M1-P6-001` | `test_tst_m1_p6_001_manifest_schema_and_completeness_validation` | `NotImplementedError: Stub: validate_manifest_schema not implemented` |
| `TST-M1-P6-002` | `test_tst_m1_p6_002_artifact_hash_tampering_and_missing_file_detection` | `NotImplementedError: Stub: validate_manifest_artifacts not implemented` |
| `TST-M1-P6-003` | `test_tst_m1_p6_003_milestone_exit_rule_engine_gate_enforcement` | `NotImplementedError: Stub: evaluate_milestone_gates not implemented` |
| `TST-M1-P6-004` | `test_tst_m1_p6_004_scoped_gate_boundary_protection` | `NotImplementedError: Stub: evaluate_milestone_gates not implemented` |
| `TST-M1-P6-005` | `test_tst_m1_p6_005_secret_and_canary_scanner_fail_closed` | `NotImplementedError: Stub: scan_secrets_in_directory not implemented` |

---

## 2. Ghi nhận Độ lệch Lịch sử (Historical Deviation Note)

> [!WARNING]
> **Deviation: `RED_EVIDENCE_MISSING_FOR_R3_REMEDIATION`**  
> Trong đợt kiểm toán độc lập R3, các ca kiểm thử `TST-M1-P6-006` (fail-closed package status parser) và `TST-M1-P6-007` (missing mandatory evidence blocks ready) đã được phát triển để tăng cường an toàn cho manifest builder nhưng chưa lưu tách riêng tệp log stdout của giai đoạn RED. Độ lệch này được ghi nhận công khai theo nguyên tắc minh bạch dữ liệu kiểm toán.

---

## 3. Bằng chứng Quan sát RED Đợt Audit R4 (R4-03 Evidence)

Trước khi thực hiện cải tiến R4 (Capability Evidence Fail-Closed & Package Inclusion), bài kiểm thử `TST-M1-P6-008` đã được tạo lập trước và chứng kiến trạng thái RED đúng oracle:

- **Lệnh thực thi:** `pytest tests/m1/p6/test_evidence_audit.py -k test_tst_m1_p6_008_capability_evidence_fail_closed -v`
- **Kết quả:** `FAILED` đúng oracle (exit code 1).
- **Hiện tượng quan sát:** `AssertionError: assert 'm1-p6' in REQUIRED_M1_PACKAGES` (m1-p6 chưa được đưa vào mandatory packages hoặc thiếu capability check cho p2/p3/p5).
- **Tệp bằng chứng thô:** `docs/milestones/m1-proof/evidence/m1-p6/red-r4-stdout.txt`

---

## 3. Bằng chứng Quan sát RED Đợt Audit R5 (R5-04 Evidence)

Trước khi thực hiện cải tiến R5 (Semantic Capability Validation trong Evidence Manifest), bài kiểm thử `TST-M1-P6-009` đã được tạo lập trước và chứng kiến trạng thái RED đúng oracle:

- **Lệnh thực thi:** `pytest tests/m1/p6/test_evidence_audit.py -k test_tst_m1_p6_009_semantic_capability_validation -v`
- **Mục tiêu:** Kiểm chứng validator phân tích sâu cấu trúc machine-readable: từ chối cấp E3 và đánh dấu semantic fail nếu P3 `process_isolated` không phải True, hoặc `broker_pid == desktop_pid`, hoặc `secure_storage_verified` không phải True; từ chối manifest nếu P5 compatibility matrix có bất kỳ runtime nào bị FAIL, UNAVAILABLE hoặc null.
- **Kết quả:** `FAILED` đúng oracle (exit code 1).
- **Hiện tượng quan sát:** `AssertionError: assert 'E3' not in manifest1['evidence_classification']['m1-p3']` (trước remediation manifest vẫn cấp E3 hoặc fallback chuỗi chứa E3).
- **Tệp bằng chứng thô UTF-8:** `docs/milestones/m1-proof/evidence/m1-p6/red-r5-stdout.txt`.
