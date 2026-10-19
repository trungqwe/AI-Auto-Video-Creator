# Báo cáo bằng chứng G-06

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `4dc0964ce286447d5d95987b402d08b9e99cdfa5`
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-06 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider` (chạy trên khung RED chưa có logic ở bước 10)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `143 failed, 4 passed in 0.90s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/orchestration/test_g_stage_run_plan.py::test_plan_attempt_creates_new_pending_row_keeping_identity[WAITING_DEPENDENCY] - NotImplementedError: G-06 RED stub: plan_attempt`
  - `FAILED tests/unit/orchestration/test_g_stage_run_plan.py::test_dependencies_ready_true_without_dependencies - NotImplementedError: G-06 RED stub: dependencies_ready`
  - `FAILED tests/unit/orchestration/test_g_stage_run_plan.py::test_succeeded_without_fencing_or_owner_commit_is_rejected[True-False] - NotImplementedError: G-06 RED stub: apply_activity_result`
  - `FAILED tests/unit/orchestration/test_g_job_waiting.py::test_stage_requires_desktop_true_for_r18_stages[script] - NotImplementedError: G-06 RED stub: stage_requires_desktop`
  - `FAILED tests/unit/orchestration/test_g_job_waiting.py::test_collection_proceeds_while_script_waits_desktop_offline[view0] - NotImplementedError: G-06 RED stub: evaluate_wait`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 4 test hợp lệ (`test_module_imports_only_stdlib_and_controlplane_domain` trong test_g_stage_run_plan, `test_wait_reason_has_exactly_the_eight_ct_orc_007_values`, `test_ready_for_completion_is_not_completed`, `test_module_imports_only_stdlib_and_controlplane_domain` trong test_g_job_waiting) đã PASS ngay từ đầu. Tất cả 143 test thất bại đều là `NotImplementedError` do stub 'G-06 RED stub: ...'.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 15)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `147 passed in 0.18s`

## Thay đổi

- 5 tệp thuộc owned paths:
  - `src/controlplane/domain/orchestration/stage_run_plan.py`: Triển khai mô hình StageRun theo attempt (D8-G-01), hàm thuần `plan_attempt` tạo hàng StageRun mới ở trạng thái PENDING giữ nguyên job_id, stage_type, input_refs; hàm kiểm tra dependency sẵn sàng `dependencies_ready` dựa trên attempt mới nhất; và hàm áp kết quả activity `apply_activity_result` tuân thủ nghiêm ngặt fencing_accepted và owner_commit_confirmed (D8-G-02) chuyển trạng thái qua `transition_stage_run`.
  - `src/controlplane/domain/orchestration/job_waiting.py`: Triển khai StrEnum WaitReason đủ 8 giá trị theo CT-ORC-007; hàm kiểm tra stage cần desktop `stage_requires_desktop` đúng cho script, plan, tts theo cổng R18; hàm đánh giá chờ fail-closed `evaluate_wait` (chỉ available/degraded chạy được, còn lại Wait desktop_offline); hàm chuyển trạng thái job ACTIVE <-> WAITING `plan_job_transition`; và hàm phục hồi `on_capability_restored` chỉ trả các stage WAITING_CAPABILITY chưa bị supersede mà không restart toàn bộ pipeline.
  - `tests/unit/orchestration/test_g_stage_run_plan.py`: Bộ kiểm thử đơn vị toàn diện gồm 61 test cases bao gồm plan_attempt kiểm tra identity và từ chối các trạng thái không được tạo attempt, dependencies_ready kiểm tra attempt mới nhất, thứ tự 4 mốc render/qc/sync/complete, apply_activity_result với ma trận fencing/commit/retryable, disposition waiting không đổi stage, tính bất biến của dataclass frozen, tính thuần và ranh giới import.
  - `tests/unit/orchestration/test_g_job_waiting.py`: Bộ kiểm thử đơn vị toàn diện gồm 86 test cases bao gồm kiểm tra 8 giá trị enum WaitReason, phân biệt stage R18 vs cloud, ma trận đánh giá năng lực fail-closed (mất capability không bao giờ làm job FAILED_FINAL), chuyển trạng thái job ACTIVE <-> WAITING, chứng minh READY_FOR_COMPLETION khác COMPLETED, khôi phục năng lực không khởi động lại pipeline, và ranh giới import.
  - `docs/delivery-evidence/g-06/report.md`: Báo cáo bằng chứng nghiệm thu lưu lại chi tiết môi trường, RED, GREEN, thay đổi, lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds và pendingUserCheckpoint.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider` | 0 | `147 passed in 0.18s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `dependency_refs` là danh sách `stage_type` cùng job, sẵn sàng khi mọi hàng của attempt mới nhất đều đạt `SUCCEEDED`.
2. `plan_attempt` chỉ cho phép previous ở các trạng thái `WAITING_DEPENDENCY`, `WAITING_CAPABILITY`, `FAILED_RETRYABLE`, `STALE` (D8-G-01); từ chối nghiêm ngặt các trạng thái `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED_FINAL`, `OUTCOME_UNKNOWN`.
3. Disposition `waiting` khi stage đang ở `RUNNING` không đổi trạng thái stage, giữ nguyên revision và trả về `job_waiting=True` (D8-G-02).
4. Result không qua fencing mà không thuộc `succeeded` hoặc `stale` sẽ bị từ chối bằng `FENCING_REJECTED`.
5. `capability_view` dùng khoá `desktop_production` với `status`; chỉ `available` và `degraded` là đủ điều kiện để chạy, còn lại (thiếu, unavailable, unknown, giá trị lạ) đều trả về `Wait(WaitReason.DESKTOP_OFFLINE)` (fail-closed).
6. Tập stage cần desktop cố định là `script`, `plan`, `tts` theo quy tắc cổng R18, là tập mở theo D8-G-05.
7. Chỉ `desktop_offline` được sinh ra từ `evaluate_wait`, bảy reason còn lại trong `WaitReason` là các giá trị enum chuẩn bị sẵn cho các gói G-11/G-12 dùng.

## Ánh xạ phản ví dụ

- Stage SUCCEEDED chỉ vì worker báo xong -> Được loại trừ bởi test `test_succeeded_without_fencing_or_owner_commit_is_rejected`.
- Resume chạy lại stage SUCCEEDED -> Được loại trừ bởi test `test_succeeded_stage_is_never_rerun_by_a_result` và `test_plan_attempt_rejects_states_that_must_not_get_a_new_attempt`.
- Capability mất làm job FAILED_FINAL -> Được loại trừ bởi test `test_capability_loss_never_fails_the_job`.
- Script chạy khi desktop offline -> Được loại trừ bởi test `test_collection_proceeds_while_script_waits_desktop_offline` và `test_desktop_stage_waits_unless_desktop_is_available_or_degraded`.

## coveredIds

- `CT-ORC-003`
- `CT-ORC-007`
- `CT-WF-007`
- `CT-STATE-008`
- `CT-STATE-009`
- (Không đóng TST-E2E-007/008)

## Danh sách chờ user (pendingUserCheckpoint)

- `PUC-G-02` (xác nhận D8-G-01/D8-G-02)
- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Chỉ dùng thư viện chuẩn Python (stdlib) và gói domain nội bộ `controlplane.domain`.
- Không đổi state machine, binding, fixture; không thêm cạnh mới vào state machine.
- Không gọi dịch vụ thật; không đọc thông tin bảo mật hay credentials.
