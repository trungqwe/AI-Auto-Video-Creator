# Báo cáo bằng chứng G-11

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `1f92cf4e3edb03004573fffcc020f5a1b2bc3da6`
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-11 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider` (chạy trên khung RED chưa có logic ở bước 7)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `101 failed, 9 passed in 0.60s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/orchestration/test_g_command_semantics.py::test_retry_keeps_job_snapshot_intent_and_fingerprint[1-FAILED_RETRYABLE] - NotImplementedError: G-11 RED stub: decide_retry_stage`
  - `FAILED tests/unit/orchestration/test_g_command_semantics.py::test_variant_creates_new_job_with_parent_refs - NotImplementedError: G-11 RED stub: decide_new_variant`
  - `FAILED tests/unit/orchestration/test_g_command_semantics.py::test_regenerate_creates_downstream_revision_only[collect-expected0] - NotImplementedError: G-11 RED stub: decide_regenerate`
  - `FAILED tests/unit/orchestration/test_g_command_semantics.py::test_debug_auto_advance_true_is_rejected - NotImplementedError: G-11 RED stub: validate_debug_request`
  - `FAILED tests/unit/orchestration/test_g_retry_policy.py::test_delay_sequence_is_exponential_and_capped - NotImplementedError: G-11 RED stub: next_delay`
  - `FAILED tests/unit/orchestration/test_g_retry_policy.py::test_should_retry_table[1-True-3-True] - NotImplementedError: G-11 RED stub: should_retry`
  - `FAILED tests/unit/orchestration/test_g_retry_policy.py::test_schedule_to_start_timeout_does_not_consume_attempt - NotImplementedError: G-11 RED stub: consumes_attempt`
  - `FAILED tests/unit/orchestration/test_g_retry_policy.py::test_repeated_schedule_to_start_never_exhausts_retries - NotImplementedError: G-11 RED stub: attempts_after_timeout`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 9 test hợp lệ đã PASS ngay từ đầu. Tất cả 101 test thất bại đều là `NotImplementedError` do stub 'G-11 RED stub: ...' hoặc thiếu validation.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 10)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `110 passed in 0.11s`

## Thay đổi

- 5 tệp thuộc owned paths:
  - `src/controlplane/domain/orchestration/command_semantics.py`: Triển khai ngữ nghĩa các lệnh retry, variant, regenerate và debug theo pure domain. Bao gồm `decide_retry_stage` giữ video_job_id, snapshot_ref, intent, fingerprint, tăng attempt và giữ completed_count_delta = 0 (từ chối đổi fingerprint qua USE_REGENERATE_OR_VARIANT); `decide_new_variant` tạo job_id mới giữ parent refs và counts_toward_target = False; `decide_regenerate` duyệt đồ thị phụ thuộc theo topo chỉ tạo revision cho downstream mà không sửa lịch sử; `validate_debug_request` ép auto_advance bắt buộc False.
  - `src/controlplane/domain/orchestration/retry_policy.py`: Triển khai chính sách retry và backoff thuần domain không dùng I/O, đồng hồ hay jitter; mọi tham số RetryPolicy bắt buộc và không có giá trị mặc định; `next_delay` tính luỹ thừa có trần an toàn số mũ lớn; `should_retry` kiểm tra attempt < max_attempts; `consumes_attempt` và `attempts_after_timeout` không tiêu thụ attempt khi gặp timeout SCHEDULE_TO_START (CT-WF-007); module không chứa hằng số nào ngoài 0 và 1.
  - `tests/unit/orchestration/test_g_command_semantics.py`: Bộ kiểm thử đơn vị toàn diện gồm 18 nhóm test bao gồm retry giữ nguyên nhận diện và không phải variant, từ chối fingerprint thay đổi, từ chối stage không thuộc tập retryable hoặc khác job_id, validate đầy đủ JobContext, variant tạo job mới với parent refs, regenerate tạo downstream revision theo đồ thị không mutate input, debug từ chối auto_advance = True, tính bất biến của dataclass frozen và ranh giới import.
  - `tests/unit/orchestration/test_g_retry_policy.py`: Bộ kiểm thử đơn vị toàn diện gồm 17 nhóm test bao gồm chuỗi delay luỹ thừa có trần, tính xác định deterministic, trần chống overflow số mũ lớn, kiểm tra tham số bắt buộc không có giá trị mặc định, từ chối giá trị vi phạm, ma trận bảng should_retry, timeout schedule-to-start không làm cạn kiệt attempt, kiểm tra tĩnh AST không có hằng số ngoài 0 và 1, không có vòng lặp while vô hạn và chỉ import stdlib.
  - `docs/delivery-evidence/g-11/report.md`: Báo cáo bằng chứng nghiệm thu lưu lại chi tiết môi trường, RED, GREEN, thay đổi, lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds và pendingUserCheckpoint.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider` | 0 | `110 passed in 0.11s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `max_attempts` là tổng số attempt gồm attempt đầu, `should_retry` là `attempt < max_attempts`.
2. `next_delay = min(initial * multiplier^(attempt-1), max_delay)`, attempt tính từ 1, không jitter.
3. Timeout `schedule_to_start` không tiêu thụ attempt qua `consumes_attempt` / `attempts_after_timeout` (CT-WF-007).
4. GIẢ ĐỊNH: `JobContext` yêu cầu cả `parent_article_ref` và `parent_event_ref` không rỗng theo CT-ORC-006.
5. `decide_retry_stage` chỉ cho phép stage ở tập `ATTEMPT_SOURCE_STATES` của G-06, trạng thái khác trả `RETRY_NOT_ALLOWED`.
6. Fingerprint đổi trả `CommandSemanticsError(USE_REGENERATE_OR_VARIANT)`.
7. `decide_regenerate` nhận `dependency_graph` dạng `stage_type -> Sequence[stage_type]` phụ thuộc, trả danh sách stage cần revision mới theo thứ tự topo, không sửa lịch sử (`rewrites_history = False`).
8. `validate_debug_request` chỉ chấp nhận bool `False`, không stage nào tự chạy sau debug (`auto_run_stage_types = ()`).
9. Tham số backoff không có mặc định cứng, nguồn là cấu hình J (D8-G-07, PUC-G-04).

## Ánh xạ phản ví dụ

- Retry coi như biến thể mới -> Được loại trừ bởi test `test_retry_is_not_a_variant` và `test_retry_keeps_job_snapshot_intent_and_fingerprint`.
- Variant tính vào target trước completion -> Được loại trừ bởi test `test_variant_creates_new_job_with_parent_refs` (xác nhận `counts_toward_target is False`).
- Debug tự chạy stage kế -> Được loại trừ bởi test `test_debug_auto_advance_true_is_rejected` và `test_debug_auto_advance_false_runs_nothing_next`.
- Backoff vô hạn -> Được loại trừ bởi test `test_delay_never_exceeds_cap`, `test_delay_huge_attempt_returns_cap_without_overflow` và `test_module_has_no_unbounded_loop`.
- Hard-code 10/300/3 của schedule-policy.yaml -> Được loại trừ bởi test `test_no_hard_coded_numeric_defaults` và `test_no_default_values`.

## coveredIds

- `CT-ORC-004`
- `CT-ORC-005`
- `CT-ORC-006`
- `CT-WF-007`
- `CT-WF-008`
- (Không đóng TST-E2E-010/014 đầy đủ, chỉ phần logic G)

## Danh sách chờ user (pendingUserCheckpoint)

- `PUC-G-04` (xác nhận D8-G-07 tham số retry/backoff từ cấu hình J)
- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Chỉ dùng thư viện chuẩn Python (stdlib) và gói domain nội bộ `controlplane.domain`.
- Không đổi state machine, binding, fixture; không sửa file ngoài owned paths.
- Không gọi dịch vụ thật; không đọc thông tin bảo mật hay credentials.
