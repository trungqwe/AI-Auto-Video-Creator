# Báo cáo bằng chứng G-05

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4dc0964ce286447d5d95987b402d08b9e99cdfa5`
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-05 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `53 failed, 2 passed in 0.35s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/orchestration/test_g_operation_receipt.py::test_same_fingerprint_table[PREPARED-retryable=True] - NotImplementedError: G-05 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_operation_receipt.py::test_no_receipt_executes[None-True] - NotImplementedError: G-05 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_operation_receipt.py::test_different_fingerprint_requires_new_operation_key[True-PREPARED] - NotImplementedError: G-05 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_operation_receipt.py::test_receipt_without_fingerprint_fails_closed - NotImplementedError: G-05 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_operation_receipt.py::test_reconcile_with_evidence_accepted[SUCCEEDED] - NotImplementedError: G-05 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_operation_receipt.py::test_timeout_after_side_effect_is_never_blindly_retried - NotImplementedError: G-05 RED skeleton`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test hợp lệ (`test_decision_members_are_exactly_seven`, `test_module_imports_only_stdlib_and_statemachine`) đã PASS ngay từ đầu. Tất cả 53 test thất bại đều là `NotImplementedError` do khung skeleton chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `55 passed in 0.07s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/domain/orchestration/operation_receipt.py`: Định nghĩa enum `RetryDecision` với 7 giá trị (`EXECUTE`, `NEW_OPERATION_KEY_REQUIRED`, `RETURN_PREVIOUS_OUTPUT`, `RECONCILE_FIRST`, `NEW_ATTEMPT_SAME_KEY`, `FAIL_FINAL`, `WAIT_IN_FLIGHT`), hàm `decide_retry` (CT-WF-005) đánh giá chính sách thử lại theo receipt và fingerprint, hàm `apply_reconcile` (CT-STATE-011) thực hiện chuyển trạng thái đối soát từ `OUTCOME_UNKNOWN` sang kết quả cuối cùng có bằng chứng hợp lệ, ủy quyền sang `transition_operation`. Module chỉ import stdlib và import chỉ đọc từ `controlplane.domain.statemachine`.
  - `tests/unit/orchestration/test_g_operation_receipt.py`: Bộ kiểm thử toàn diện gồm 55 test cases kiểm tra bảng quyết định cùng fingerprint, không receipt thì luôn `EXECUTE`, fingerprint khác yêu cầu `NEW_OPERATION_KEY_REQUIRED`, receipt thiếu fingerprint fail-closed, `OUTCOME_UNKNOWN` không bao giờ `EXECUTE`, validation state lạ ném ValueError, chấp nhận state dạng chuỗi, đối soát có evidence thành công, thiếu evidence hoặc evidence rỗng bị từ chối với `ForbiddenTransitionError`, chỉ đối soát từ `OUTCOME_UNKNOWN`, chặn outcome không phải terminal, trạng thái terminal không bao giờ mở lại `STARTED`, ủy quyền chính xác sang `transition_operation`, timeout sau side-effect không bao giờ retry mù, và giới hạn import chỉ gồm stdlib và statemachine.
  - `docs/delivery-evidence/g-05/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider` | 0 | `55 passed in 0.07s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Thứ tự ưu tiên trong `decide_retry`: không có receipt -> `EXECUTE`, sau đó fingerprint khác -> `NEW_OPERATION_KEY_REQUIRED`, sau đó xét theo trạng thái receipt.
2. Receipt không có fingerprint (`receipt_fingerprint is None`) coi là khác fingerprint mới (fail-closed) và trả `NEW_OPERATION_KEY_REQUIRED`.
3. `FAILED` kèm `retryable=True` trả `NEW_ATTEMPT_SAME_KEY` thể hiện một attempt mới cho cùng key, không phải chuyển trạng thái `FAILED -> STARTED` vì đồ thị trạng thái `CT-STATE` chặn mở lại terminal.
4. Tham số `retryable` bị bỏ qua với `OUTCOME_UNKNOWN`; luôn trả `RECONCILE_FIRST` và không bao giờ `EXECUTE`.
5. Evidence rỗng hoặc toàn khoảng trắng (`not isinstance(evidence_ref, str) or not evidence_ref.strip()`) coi là thiếu evidence và bị từ chối bằng `ForbiddenTransitionError`.
6. `apply_reconcile` chỉ hợp lệ khi chuyển đổi từ trạng thái `OUTCOME_UNKNOWN`.

## Ánh xạ phản ví dụ

- Timeout sau side effect thực hiện lại mù -> `test_timeout_after_side_effect_is_never_blindly_retried` và `test_outcome_unknown_never_executes`
- Retry từ OUTCOME_UNKNOWN -> `test_outcome_unknown_never_executes`, `test_same_fingerprint_table[OUTCOME_UNKNOWN-retryable=True]`, `test_same_fingerprint_table[OUTCOME_UNKNOWN-retryable=False]`
- Fingerprint khác dùng lại key cũ -> `test_different_fingerprint_requires_new_operation_key`

## coveredIds

- `CT-WF-005`
- `CT-STATE-011`

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi statemachine, pyproject.toml, uv.lock, binding, fixture.
- Chỉ dùng stdlib và import chỉ đọc từ `controlplane.domain.statemachine`.
- Không gọi dịch vụ thật.
