# Báo cáo bằng chứng G-07

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4fd21816ce8c657983f0e09d226209f381b13f5c`
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-07 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 9)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `85 failed, 3 passed in 0.68s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/orchestration/test_g_allocation_policy.py::test_can_allocate_table[5-0-0-True] - NotImplementedError: G-07 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_allocation_policy.py::test_plan_round_grants_one_to_three_distinct_angles[1] - NotImplementedError: G-07 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_allocation_policy.py::test_reservation_action_table[WAITING-HOLD] - NotImplementedError: G-07 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_job_allocation.py::test_allocate_creates_job_and_reservation_inside_lock - NotImplementedError: G-07 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_job_allocation.py::test_mid_failure_after_job_insert_leaves_no_orphan_job - NotImplementedError: G-07 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_job_allocation.py::test_eight_threads_race_for_last_slot_single_winner[0] - NotImplementedError: G-07 RED skeleton`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 3 test hợp lệ (`test_can_allocate_takes_ledger_count_not_files`, `test_max_jobs_per_round_is_three`, `test_expected_actions_cover_every_job_state`) đã PASS ngay từ đầu. Tất cả 85 test thất bại đều là `NotImplementedError: G-07 RED skeleton` do khung skeleton chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 12)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `88 passed in 0.21s`

## Thay đổi

- 5 tệp thuộc owned paths:
  - `src/controlplane/domain/orchestration/allocation_policy.py`: Cung cấp hằng số `MAX_JOBS_PER_ROUND = 3`, dataclass `AllocationCandidate`, enum `ReservationAction` (`HOLD`, `RELEASE`, `CONVERT`, `NONE`), hàm `can_allocate` kiểm tra sức chứa dựa trên đếm ledger, hàm `plan_round` lập kế hoạch 1–3 job với góc quay riêng biệt được validate trước khi cắt theo `slots_left`, và hàm `reservation_action` ánh xạ `JobState` sang hành động reservation (WAITING giữ suất, FAILED_FINAL giải phóng suất, COMPLETED chuyển đổi, các trạng thái khác trả NONE).
  - `src/controlplane/application/orchestration/job_allocation.py`: Cung cấp exception `BatchTargetReachedError`, dataclass `JobReservation`, protocol `AllocationStorePort` (với `lock_batch`, `count_ledger`, `count_active`, `find_reservation`, `create_job_and_reservation`), và lớp `JobAllocationService` với phương thức `allocate` thực hiện cấp suất job và reservation nguyên tử trong khối khóa theo batch.
  - `tests/unit/orchestration/test_g_allocation_policy.py`: Bộ kiểm thử 65 ca kiểm tra bảng quyết định `can_allocate`, từ chối tham số không hợp lệ, chữ ký hàm nhận đếm ledger không nhận số tệp, `MAX_JOBS_PER_ROUND == 3`, cấp 1–3 góc quay khác nhau, giới hạn theo `slots_left`, từ chối yêu cầu >3 hoặc trùng góc quay, từ chối tham số sai, và bảng `reservation_action` phủ toàn bộ `JobState`.
  - `tests/unit/orchestration/test_g_job_allocation.py`: Bộ kiểm thử 23 ca kiểm tra `JobAllocationService` qua fake store có khóa luồng thật, kiểm tra cấp job và reservation trong khóa, đếm ledger thay vì tệp đĩa, tôn trọng target, retry cùng job_id trả reservation cũ mà không tăng suất (kể cả khi hết chỗ), từ chối job_id thuộc batch khác, từ chối tham số sai trước khi khóa, rollback không để lại job mồ côi khi lỗi giữa chừng, và kiểm thử tranh chấp đa luồng (8 luồng tranh suất cuối có đúng 1 winner theo TST-WF-INV-018, 8 luồng với 6 suất cấp đúng 6, 8 luồng retry cùng job_id chia sẻ 1 reservation).
  - `docs/delivery-evidence/g-07/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cacheprovider` | 0 | `88 passed in 0.21s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `plan_round` kiểm tra toàn bộ yêu cầu (1–3, `angle_slot` khác nhau sau strip, không rỗng) trước khi cắt theo `slots_left`; `slots_left=0` trả tuple rỗng; danh sách rỗng bị `ValueError`.
2. `reservation_action` trả `NONE` cho `CREATED`, `SNAPSHOTTED`, `ACTIVE`, `READY_FOR_COMPLETION`; state lạ hoặc không phải chuỗi bị `ValueError`.
3. `lock_batch` của `AllocationStorePort` là context manager yield `target_completed_videos`, thoát bình thường là commit, exception là rollback toàn khối (không để lại job mồ côi).
4. `find_reservation` chạy trước kiểm target nên retry ở suất cuối vẫn trả reservation cũ một cách an toàn.
5. `job_id` đã thuộc batch khác bị từ chối bằng `ValueError`.
6. Đếm số, không có ngưỡng mặc định cứng (D8-G-07), `MAX_JOBS_PER_ROUND = 3` là quy tắc sản phẩm INV-013.

## Ánh xạ phản ví dụ

- Đếm tệp thay cho ledger -> `test_allocate_counts_ledger_not_files` và `test_can_allocate_takes_ledger_count_not_files`
- Hai job cùng angle_slot -> `test_plan_round_rejects_bad_requests` và `test_plan_round_validates_before_truncating_by_slots_left`
- Retry tạo reservation mới -> `test_retry_same_job_id_returns_old_reservation_without_new_slot`, `test_waiting_holds_slot_and_retry_does_not_create_reservation`, và `test_eight_threads_retrying_same_job_id_share_one_reservation`
- Hai allocator cùng nhận suất cuối -> `test_eight_threads_race_for_last_slot_single_winner`
- Job mồ côi sau lỗi giữa chừng -> `test_mid_failure_after_job_insert_leaves_no_orphan_job`

## coveredIds

- `CT-ORC-002`
- `INV-018`
- `INV-013`

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `__init__.py`, `statemachine`, migration, `pyproject.toml`, lockfile.
- Chỉ dùng stdlib và các kiểu dữ liệu từ `controlplane.domain.statemachine`.
- Fake store chỉ chứng minh logic mức TST-WF-INV-018, ca PostgreSQL thật nằm ở tests/m2 P6.
- Không gọi dịch vụ thật.