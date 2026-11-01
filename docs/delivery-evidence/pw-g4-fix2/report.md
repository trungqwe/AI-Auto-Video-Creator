# Báo cáo: Lô chuyển CREATED -> RUNNING khi ProductionBatchWorkflow bắt đầu (PW-G4-FIX2)

## 1. Trạng thái

ỨNG VIÊN SẴN SÀNG ĐỂ KIỂM trên HEAD 7d682931d7fa32a96db7584d05c8a6982c633d74. Mọi lệnh kiểm ở mục 6 đều thoát 0 (kết quả chạy thật trong lượt này).

OI-PW-E2E-01 và OI-PW-VERT-01 đã đóng: `pw_e2e_support.py` và `pw_vertical.py` không còn UPDATE trạng thái lô (probe quét `cp_production_batches SET status` trên toàn bộ `tests` thoát 0).

Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.
PYTEST_DEBUG_TEMPROOT: `C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\PW-G4-FIX2-implement-r0-ac1b5c0961`.
PostgreSQL thử: DSN loopback 127.0.0.1 do môi trường Control cấp (`M2_TEST_PG_DSN`).

## 2. Lỗi gốc (nhóm lỗi OI-PW-E2E-01)

9/15 ProductionBatchWorkflow đã đóng có FinalizeBatch thất bại `FORBIDDEN_TRANSITION` (finalized False). Nguyên nhân: không writer nào ghi RUNNING cho lô. `start_batch` chỉ ghi CREATED; `finish` chỉ nhận RUNNING và WAITING_CAPABILITY. Rig PW-E2E và PW-VERT từng lách bằng UPDATE.

## 3. Ngữ nghĩa mới

- `PostgresBatchStates.start(batch_id) -> bool`: SELECT status FOR UPDATE; thiếu dòng -> `BATCH_NOT_FOUND`; RUNNING và WAITING_CAPABILITY -> False, không ghi; CREATED -> `transition_batch` sang RUNNING rồi UPDATE kèm điều kiện status cũ -> True; lô đã kết thúc -> `ForbiddenTransitionError`, không ghi.
- `BatchLifecycle.start(batch_id) -> bool`: đồng bộ, giao dịch riêng như `finish`.
- Activity nội bộ `StartBatch` (control-workflows): không binding, không grant, không stage run.
- `ProductionBatchWorkflow.run`: dựng gateway một lần; chỉ khi `workflow.patched('batch-running-on-start')` mới `await gateway.start_batch(params.batch_id)` trước `ProductionBatchFlow`. Không bắt ActivityError: lỗi làm workflow FAILED, không cấp job.
- Mã lỗi non_retryable: `BATCH_LIFECYCLE_UNBOUND`, `INVALID_ACTIVITY_REQUEST`, mã của `OrchestrationContractError`, `FORBIDDEN_TRANSITION`. Lỗi khác để Temporal thử lại.
- Không đổi state machine, `finish`, `start_batch.py`, `outbox_relay.py`.

## 4. Tệp đã sửa (10 owned paths)

- `src/controlplane/infrastructure/db/orchestration/job_states.py`
- `src/controlplane/application/orchestration/job_lifecycle.py`
- `src/controlplane/application/orchestration/workflows/activities.py`
- `src/controlplane/application/orchestration/workflows/definitions.py`
- `src/controlplane/api/wiring/workflow.py`
- `tests/integration/prod_wiring/test_pw_g4_fix2_batch_start.py` (mới)
- `tests/integration/prod_wiring/pw_e2e_support.py`
- `tests/integration/prod_wiring/pw_vertical.py`
- `tests/integration/prod_wiring/test_pw_g5_allocation.py`
- `docs/delivery-evidence/pw-g4-fix2/report.md` (mới)

## 5. Test và RED

`test_pw_g4_fix2_batch_start.py` (15 ca): lifecycle `start` (CREATED True rồi False; WAITING_CAPABILITY False; ba trạng thái kết thúc bị từ chối; thiếu dòng `BATCH_NOT_FOUND`); luồng chính; hết ứng viên; lịch sử tắt patch; thử lại sau commit; ba ca fail-closed; hai ca lô RUNNING/WAITING_CAPABILITY sẵn.

RED trên mã chưa sửa, dòng tổng kết nguyên văn: `12 failed, 3 passed in 80.30s (0:01:20)`.

- RED hợp lệ (assert hành vi hỏng): luồng chính (`('TARGET_REAC..., 0, 2, False) == (... 2, 0, 2, True)`, tức finalized False); hết ứng viên (finalized không True); ba ca fail-closed (`assert isinstance(outcome, WorkflowFailureError)` hỏng, tức workflow không FAILED).
- Không phải RED hợp lệ: 6 ca lifecycle (`AttributeError: 'BatchLifecycle' object has no attribute 'start'`) và ca thử lại (`TypeError: WorkflowServices.__init__() got an unexpected keyword argument 'batch_lifecycle'`).
- 3 ca đạt sẵn trên mã cũ, đúng kỳ vọng: lịch sử tắt patch (mã cũ vốn không có StartBatch) và hai ca RUNNING/WAITING_CAPABILITY sẵn.

Trạng thái lô (test luồng chính, `start_batch` target 2, OutboxRelay.run_once): sau POST/`start_batch` là `CREATED`; khi AllocateJob chạy là `['RUNNING', 'RUNNING']`; sau FinalizeBatch là `COMPLETED_TARGET` có `stop_reason` và `stopped_at`, kết quả `(TARGET_REACHED, 2, 0, 2, True)`. Hết ứng viên: `EXHAUSTED`, finalized True, `COMPLETED_EXHAUSTED`.

Vị trí trong history: test khẳng định marker `batch-running-on-start` < `StartBatch` < `IssueExecutionGrant` đầu và đúng một `StartBatch`. (Số thứ tự sự kiện marker@4, StartBatch@6, IssueExecutionGrant@12 là số đo của Control, không phải đo lại trong lượt này.)

Replayer: lịch sử tắt patch (không marker, không StartBatch, FinalizeBatch FORBIDDEN_TRANSITION, lô còn CREATED) được Replayer mã mới phát lại không lỗi (test đạt). Lịch sử luồng chính cũng phát lại không lỗi.

## 6. Bằng chứng (lệnh | mã thoát | dòng tổng kết)

| Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- |
| Nhóm 2: test_pw_g4_fix2_batch_start, test_pw_g4_job_states, test_cp5_completion_uow, test_persist_g_postgres | 0 | `176 passed in 89.71s (0:01:29)` |
| Nhóm 3: g5_allocation, g5_fix1_batch_concurrency, g4_fix1_job_terminal, g6_outbox_relay, g6_fix1_batch_settings | 0 | `92 passed, 1 warning in 54.61s` |
| Nhóm 4: vert_video_flow, g3_grants, cat2_flow | 0 | `79 passed in 45.41s` |
| Nhóm 5: cp6 static, catalog, video_production_flow | 0 | `30 passed in 1.68s` |
| Nhóm 6: launcher, adapt | 0 | `231 passed, 1 warning in 38.79s` |
| Nhóm 7: test_pw_e2e_batch_video | 0 | `10 passed, 1 warning in 120.40s (0:02:00)` |
| Nhóm 8: unit và tích hợp rộng | 0 | `3463 passed, 1034 subtests passed in 8.17s` |
| Nhóm 9: `tests/unit` | 0 | `7572 passed, 1 warning, 2561 subtests passed in 21.68s` |
| Probe definitions (bước 26) | 0 | không AssertionError |
| Probe wiring/internal/store/lifecycle (bước 27) | 0 | không AssertionError |
| Probe quét UPDATE trạng thái lô (bước 28) | 0 | danh sách rỗng |
| Probe nội dung test mới (bước 29) | 0 | không AssertionError |
| Probe bố cục CP2A-LAYOUT (bước 30) | 0 | không AssertionError |
| Probe báo cáo (bước 32) | 0 | không AssertionError |
| `git diff --check` (bước 33) | 0 | không in lỗi whitespace |

## 7. Giới hạn

- Không tự sửa dữ liệu cũ: các lô đã đóng còn CREATED và các ProductionBatchWorkflow cũ đang chạy không được sửa trong gói này (patched ghi nhớ False khi phát lại nên FinalizeBatch của chúng vẫn FORBIDDEN_TRANSITION); Control dọn riêng.
- Workflow cũ phát lại an toàn nhờ `workflow.patched`. Lịch sử có marker mới không phát lại được bằng mã trước bản sửa (không rollback mã khi còn workflow chạy).
- Cạnh RUNNING <-> WAITING_CAPABILITY của lô chưa có writer và sự kiện BatchStarted chưa phát qua outbox: backlog.
- Không push, không merge.
