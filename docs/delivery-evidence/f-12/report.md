# Báo cáo bằng chứng F-12

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `a461b76e086b8d41ce4f0607da1e2c2460d3c90f`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-12 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider` (chạy trên stub trung tính ở bước 15)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `129 failed, 17 passed, 8 subtests passed in 1.47s`
- Các dòng FAILED tiêu biểu:
  1. `GateResultTests.test_measured_value_accepts_only_finite_scalars`: `AssertionError: QualityReportError not raised`
  2. `GateResultTests.test_not_applicable_is_only_for_hard_conditional_gates`: `AssertionError: QualityReportError not raised`
  3. `QualityPolicyTests.test_equal_policies_are_equal_and_hashable`: `AssertionError: False is not true`
  4. `QualityPolicyTests.test_has_threshold`: `AssertionError: False is not true`
  5. `BuildQualityReportTests.test_duplicate_gate_results_are_rejected`: `AssertionError: QualityReportError not raised`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection.

## GREEN

- Lệnh thực thi: cùng lệnh sau khi cài đặt
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `45 passed, 129 subtests passed in 0.12s`

## Thay đổi

- `src/render/domain/quality_report.py`: GateName (13 gate), GateKind và GATE_KINDS theo bảng CT-QC-001, GateStatus, GateResult frozen, QualityPolicy frozen (thresholds đóng băng sâu), QualityReport frozen (tự kiểm passed và report_id), build_quality_report, compute_report_id, QualityReportError.
- `tests/unit/render/test_f12_quality_report.py`: 6 lớp test và 45 test methods (129 subtests).
- `docs/delivery-evidence/f-12/report.md`: báo cáo này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider` | 0 | 45 passed, 129 subtests passed |
| 2 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 75 subtests passed |
| 3 | `python -c "import pathlib; assert 'STUB-' not in pathlib.Path('src/render/domain/quality_report.py').read_text(encoding='utf-8')"` | 0 | Sạch mọi marker stub |
| 4 | `git diff --check` | 0 | Không có lỗi định dạng hay khoảng trắng thừa |

## Quyết định mặc định (D8)

1. `build_quality_report(results, applicability, *, policy=None)`: policy là tham số từ khoá tùy chọn; warning không có `threshold_revision` hoặc không có ngưỡng trong policy → `not_evaluated` kèm `INPUT_NOT_READY`.
2. Report luôn có đủ 13 gate theo thứ tự GateName; hard gate thiếu → `not_evaluated` với reason `missing_result` nên `passed` False.
3. hard_conditional: applicability thiếu hoặc không khai được coi là áp dụng (fail-closed); applicability False → `not_applicable` và bỏ qua kết quả đã truyền.
4. `not_applicable` chỉ hợp lệ cho gate hard_conditional; mâu thuẫn với applicability → `not_evaluated` reason `applicability_mismatch`.
5. `measured_value` chỉ là scalar hữu hạn; `time_range` là cặp số nguyên ms với 0 <= start <= end (GIẢ ĐỊNH); reason bắt buộc khi status khác passed.
6. `passed` dẫn xuất từ gate; `report_id` là `request_hash` của policy_revision và các gate.

## Ánh xạ phản ví dụ

- Report pass khi thiếu hard gate → test_missing_hard_gate_makes_report_fail, test_empty_results_never_pass
- Warning làm fail → test_failing_warnings_never_fail_the_report
- Disclosure không áp dụng vẫn bị tính → test_not_applicable_disclosure_is_not_counted
- Gate trùng được chấp nhận → test_duplicate_gate_results_are_rejected

## coveredIds

- `CT-QC-001`
- `CT-QC-002`

## Danh sách chờ user (pendingUserCheckpoint)

- Ngưỡng audio mix và visual continuity (warning, nâng thành hard gate phải do user).
- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Chỉ stdlib và canonicalizer đã có; không gọi dịch vụ thật.
