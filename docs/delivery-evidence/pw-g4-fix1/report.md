# Báo cáo: Job video tới FAILED_FINAL và trả suất khi VideoProductionWorkflow thất bại (PW-G4-FIX1)

Task: PW-G4-FIX1
Nhóm lỗi: R26 (job, dòng stage và suất capacity kẹt ACTIVE khi workflow con kết thúc FAILED)
Nguồn lỗi: phân tích Control ngày 31/10/2026 (CP7-10, PW-G2-FIX1)

## 1. Trạng thái

ỨNG VIÊN SẴN SÀNG ĐỂ KIỂM trên cơ sở 07dd1ce099044e25a1787e28cbbf2eaaa518d841: mọi lệnh kiểm bắt buộc xanh (kết quả thật ở mục 5).

## 2. Ngữ nghĩa mới

`JobTerminator.fail(FailJobRequest)` chạy trong một giao dịch, không ném lỗi nghiệp vụ, khoá job rồi registry rồi capacity.

- `stage_run_id` có chủ khác `video_job_id`: trả `STAGE_OWNER_MISMATCH`, không đổi gì. Job không tồn tại: `JOB_NOT_FOUND`. Job CREATED: `JOB_NOT_FAILABLE`, không đổi gì (kể cả dòng stage).
- COMPLETED: không làm gì. SNAPSHOTTED: sang ACTIVE rồi FAILED_FINAL. ACTIVE, WAITING, READY_FOR_COMPLETION: sang FAILED_FINAL.
- Khi job ở FAILED_FINAL (vừa đặt hay có từ trước): trả giữ chỗ variant theo `reservation_action` qua `VariantReservationFlow.release` (bỏ qua NOT_FOUND) và đặt capacity ACTIVE thành RELEASED.
- Dòng stage RUNNING chuyển FAILED_FINAL với problem `{code, activity, disposition, retryable: False}` (code thiếu thì `RETRY_EXHAUSTED`). Dòng ở trạng thái khác (OUTCOME_UNKNOWN, PENDING) giữ nguyên. Gọi lần hai không đổi gì.
- Workflow: sau `_drive`, `_run_stage_graph` gọi activity nội bộ `FailVideoJob` khi VideoProductionWorkflow có `video_job_id`, status FAILED, `hold_on_failure` False và `workflow.patched('job-terminal-on-failure')`. Lỗi của lời gọi bị bắt (`ActivityError`) và ghi log; snapshot trả về không đổi.
- `FailVideoJob` nằm trong `INTERNAL_ACTIVITIES` (queue control), không qua grant hay recorder. `wrap_dispatcher` gắn `job_terminator`; thiếu terminator thì `ApplicationError('JOB_TERMINATOR_UNBOUND', non_retryable=True)`.

## 3. Tệp đã sửa

- `src/controlplane/application/orchestration/job_terminal.py` (mới)
- `src/controlplane/application/orchestration/workflows/activities.py`
- `src/controlplane/application/orchestration/workflows/definitions.py`
- `src/controlplane/api/wiring/workflow.py`
- `tests/integration/prod_wiring/test_pw_g4_fix1_job_terminal.py` (mới, 20 test)
- `docs/delivery-evidence/pw-g4-fix1/report.md` (báo cáo này)

## 4. Test

| Ca | Nội dung |
| --- | --- |
| 01, 01b | JobTerminator trên job ACTIVE: FAILED_FINAL, dòng, capacity, variant; gọi lần hai không đổi; code thiếu thành RETRY_EXHAUSTED |
| 02, 02b-02e | SNAPSHOTTED, WAITING, READY_FOR_COMPLETION; COMPLETED; CREATED; job không có variant; owner mismatch và job không tồn tại |
| 03 | Dòng OUTCOME_UNKNOWN và PENDING giữ nguyên |
| 04 | failed retryable hết lượt (đúng 3 lần dispatch) |
| 05 | stale hết lượt |
| 06 | handler ném RuntimeError tới hết RetryPolicy |
| 07a, 07b | ActivityRejected; outcome_unknown (dòng giữ OUTCOME_UNKNOWN) |
| 08a, 08b | hold_on_failure True và DebugStageWorkflow không gọi FailVideoJob |
| 09 | lô target 1: completed 1, failed 1, allocated 2, TARGET_REACHED |
| 10 | marker `job-terminal-on-failure` trước ActivityTaskScheduled(FailVideoJob), Replayer không lỗi |

RED chạy trên mã chưa sửa: `python -m pytest tests/integration/prod_wiring/test_pw_g4_fix1_job_terminal.py -q -p no:cacheprovider` thoát 1, `18 failed, 2 passed`.

- RED KHÔNG hợp lệ làm oracle: 01, 01b, 02 (3 ca), 02b, 02c, 02d, 02e, 03 (2 ca) hỏng vì `ModuleNotFoundError: No module named 'controlplane.application.orchestration.job_terminal'` (thiếu module).
- RED hợp lệ (assert hành vi): 04 `assert 'FailVideoJob' in [...]` hỏng; 05, 06, 07a, 07b `assert 'ACTIVE' == 'FAILED_FINAL'` ở `assert_terminated`; 09 `assert ('EXHAUSTED', 0, 1, 1) == ('TARGET_REACHED', 1, 1, 2)`; 10 `assert (None is not None)` (không có marker).
- 08a và 08b đạt trên mã cũ (ca bảo vệ, đúng dự kiến).

## 5. Bằng chứng

Chạy bằng interpreter khoá, `PYTEST_DEBUG_TEMPROOT` riêng của lượt, `M2_TEST_PG_DSN` loopback.

| Lệnh | Mã thoát | Dòng tổng kết |
| --- | --- | --- |
| Bước 18: `python -m pytest tests/integration/prod_wiring/test_pw_g4_fix1_job_terminal.py -q -p no:cacheprovider` | 0 | `20 passed in 18.89s` |
| Bước 19: bộ prod_wiring (VERT, CAT2, G5, G4, G3, G2, G2-FIX1, G7) | 0 | `259 passed in 104.60s (0:01:44)` |
| Bước 20: CP6 workflow static, catalog, video flow | 0 | `30 passed in 1.60s` |
| Bước 21: W1, W2, ADAPT launch, ADAPT wire, A3 | 0 | `194 passed in 28.32s` |
| Bước 22: PW-E2E | 0 | `10 passed in 116.06s (0:01:56)` |
| Probe definitions.py (`workflow.patched(`, `FailVideoJob`) | 0 | không có AssertionError |
| Probe job_terminal.py | 0 | không có AssertionError |
| `git diff --check` | 0 | không có cảnh báo (xem lệnh cuối ở lượt hoàn tất) |

## 6. Mục mở và quyết định

D8 (lựa chọn thiết kế): chỉ dùng cạnh trạng thái có sẵn (không thêm cạnh CREATED sang FAILED_FINAL); `JobTerminator` không phải listener (test PW-W1 đòi listener chỉ có `JobLifecycleListener`); `FailVideoJob` là activity nội bộ, không qua grant hay recorder; dùng `workflow.patched` thay vì tăng `workflow_version` (CT-WF-009).

Mục mở:

- (a) Job đã FAILED_FINAL qua listener được trả suất ở giao dịch sau, không cùng giao dịch với listener.
- (b) `outcome_unknown` cho job FAILED_FINAL khi chưa reconcile: dòng giữ OUTCOME_UNKNOWN.
- (c) Tên `test_pw_g5_allocation.py:277` mô tả hành vi cũ (gateway giả).
- (d) Job hỏng ngay ở CREATED (BuildProductionSnapshot) vẫn không tới FAILED_FINAL vì thiếu cạnh CREATED sang FAILED_FINAL (quyết định của user).
- (e) Mỗi attempt một StageRun (D8-G-01) chưa nối.
- (f) Code mức job của lỗi ném là `ActivityError`.
- (g) Nhánh `hold_on_failure` True vẫn chờ người vận hành.

## 7. Xác nhận UTF-8

Tệp ghi bằng công cụ ghi tệp (UTF-8 không BOM); chữ tiếng Việt có dấu còn nguyên sau khi đọc lại.
