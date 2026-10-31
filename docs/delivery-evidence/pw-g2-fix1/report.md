# Báo cáo: Dòng stage run phản ánh kết quả của cả stage nhiều activity (PW-G2-FIX1)

Task: PW-G2-FIX1
Nhóm lỗi: R24 (kết quả activity thứ hai trở đi của stage nhiều activity bị bộ ghi bỏ)
Nguồn lỗi: CP7-10 lượt 3 và 4 (30/10/2026): job FAILED_FINAL mà không dòng cp_stage_runs nào hỏng

## 1. Trạng thái

ỨNG VIÊN SẴN SÀNG ĐỂ KIỂM: mọi lệnh kiểm bắt buộc xanh trên mã đã rebase lên 1197b045edef2a3f479c80e8e01b08cfd4db0089 (kết quả thật ở mục 5).

## 2. Ngữ nghĩa mới

Vị trí activity lấy theo `STAGE_ACTIVITIES_BY_WORKFLOW`, stage lấy từ `stage_run_id`.

- Dòng chỉ thành SUCCEEDED ở activity cuối của stage (`_closes_stage`). `succeeded` của activity chưa cuối: không ghi, dòng giữ RUNNING.
- `failed` có `problem.retryable` là True và `stale`: không ghi, dòng giữ RUNNING (`_retried_in_place`). Lý do: CT-STATE-008 không có cạnh ra khỏi FAILED_RETRYABLE hay STALE, còn flow thử lại tại chỗ trên cùng `stage_run_id`.
- `failed` còn lại (không retryable, thiếu khoá hoặc không có problem): RUNNING sang FAILED_FINAL; problem cộng khoá `activity`.
- `outcome_unknown` (kể cả retryable True): RUNNING sang OUTCOME_UNKNOWN; problem cộng khoá `activity`.
- `ActivityRejected`: RUNNING sang FAILED_FINAL với `{code, retryable: False, activity}`, rồi ném lại; listener không chạy.
- `waiting`: giữ như cũ (dòng RUNNING, ghi wait_reason).
- Dòng không còn ở RUNNING lúc ghi: không ghi gì. Listener vẫn được gọi sau bước ghi hoặc bỏ ghi.
- Không đổi state machine, `stage_runs.py`, flow, `activities.py`, `job_lifecycle.py`.

## 3. Tệp đã sửa

- `src/controlplane/application/orchestration/result_recorder.py` (thêm `_retried_in_place` và đúng một lệnh gọi trong `_record`)
- `tests/integration/prod_wiring/test_pw_g2_fix1_stage_outcome.py` (14 test)
- `tests/integration/prod_wiring/test_pw_g2_stage_runs.py`
- `tests/integration/prod_wiring/test_pw_g4_job_states.py` (đúng dòng 335)
- `docs/delivery-evidence/pw-g2-fix1/report.md` (báo cáo này)

## 4. Từng dòng test đã đổi kèm lý do

`test_pw_g4_job_states.py`, dòng 335 (`test_job_chain_through_the_result_recording_dispatcher`): `runs` thành `[('job-1:analyze:r1', 'RUNNING'), ('job-1:process:r1', 'RUNNING'), ('job-1:process:r2', 'RUNNING'), ('job-1:process:r3', 'RUNNING'), ('job-1:sync:r1', 'SUCCEEDED')]`. Lý do: BuildProductionSnapshot và ProbeMedia không phải activity cuối của stage analyze và process nên dòng giữ RUNNING; sync chỉ có PersistVideoOutput nên SUCCEEDED.

`test_pw_g2_stage_runs.py` so với bản nghiệm thu b510f96:

- CASES `('succeeded', {}, 'SUCCEEDED', None, None)` thành `'RUNNING'`: ProbeMedia chưa phải activity cuối (PrepareAudioBed).
- CASES `outcome_unknown`: problem mong đợi `{'activity': 'ProbeMedia'}`.
- CASES `stale` thành `('stale', {}, 'RUNNING', None, None)`: flow thử lại tại chỗ, CT-STATE-008 không có cạnh ra khỏi STALE.
- CASES `failed` retryable thành `('failed', {'problem': {'code': 'X', 'retryable': True}}, 'RUNNING', None, None)`: cùng lý do với stale.
- CASES `failed` không retryable: FAILED_FINAL, problem có thêm `'activity': 'ProbeMedia'`; `failed {}`: FAILED_FINAL, problem `{'activity': 'ProbeMedia'}`.
- Khẳng định `finished_at`: `(row[11] is not None) == (status != 'RUNNING')`, vì dòng RUNNING chưa có finished_at.
- Problem của `ActivityRejected` thêm `'activity': 'ProbeMedia'`; ca listener dùng `failed` không retryable và kỳ vọng `FAILED_FINAL`.
- `test_second_dispatch_of_a_finished_stage_run_keeps_the_row`: tham số thành `[('succeeded', 'SUCCEEDED'), ('failed', 'FAILED_FINAL')]` và `extra` dùng `retryable: False`, để có dòng đã kết thúc thật; hai lần dispatch dùng activity cuối `PrepareAudioBed`.
- Các ca `waiting`: không đổi.

`test_pw_g2_fix1_stage_outcome.py`:

- `LATER_RESULTS`: dòng đầu thành `outcome_unknown` retryable kỳ vọng `OUTCOME_UNKNOWN` kèm `{'code': 'X', 'retryable': True, 'activity': ANALYZE}`; bỏ bộ `stale` (nay giữ RUNNING, đã có test riêng).
- Đổi tên test thành `test_final_results_of_the_second_activity_are_recorded`.
- Thêm (1) `test_a_result_the_flow_retries_in_place_keeps_the_row_running_until_the_retry_is_recorded` (failed retryable và stale giữ RUNNING, job ACTIVE, lần sau SUCCEEDED).
- Thêm (2) `test_a_final_failure_after_a_retryable_failure_fails_the_row_and_the_job` (failed retryable rồi failed không retryable: FAILED_FINAL kèm `activity`, job FAILED_FINAL).
- Thêm (3) `test_a_row_that_left_running_as_failed_retryable_or_stale_is_not_rewritten` (dòng đã rời RUNNING không bị ghi lại).

## 5. Bằng chứng (chạy bằng interpreter khoá, PYTEST_DEBUG_TEMPROOT riêng của lượt)

- Bước 1, rebase: `git rebase 1197b045edef2a3f479c80e8e01b08cfd4db0089` xong, không xung đột; ba commit của lane nằm trên 1197b04.

| Lượt | Lệnh | Mã thoát | Dòng tổng kết |
| --- | --- | --- | --- |
| RED (recorder chưa sửa) | `python -m pytest tests/integration/prod_wiring/test_pw_g2_fix1_stage_outcome.py -q -p no:cacheprovider` | 1 | `3 failed, 11 passed in 6.83s` |
| GREEN | cùng lệnh | 0 | `14 passed in 6.49s` |
| Lệnh kiểm 1 (6 tệp: fix1, PW-G2, PW-G4, PW-CAT2, CP5 UoW, PERSIST-G) | `python -m pytest ... -q -p no:cacheprovider` | 0 | `238 passed in 57.17s` |
| Lệnh kiểm 2 (PW-VERT, PW-G3) | `python -m pytest tests/integration/prod_wiring/test_pw_vert_video_flow.py tests/integration/prod_wiring/test_pw_g3_grants.py -q -p no:cacheprovider` | 0 | `49 passed in 42.28s` |
| Lệnh kiểm 3 (PW-E2E) | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | `10 passed, 1 warning in 118.92s (0:01:58)` |
| Probe PW-G2 | `python -c "..."` (không `from src.`, `fake`, `mock`) | 0 | không có AssertionError |
| Probe report CP7-10 | `python -c "..."` | 0 | không có AssertionError |
| Probe report PW-G2-FIX1, R24 | `python -c "..."` | 0 | không có AssertionError |
| `git diff --check` | `git diff --check` | 0 | không có cảnh báo |

Ba test hỏng ở lượt RED: hai ca của test (1) (`failed-extra0`, `stale-extra1`) và test (2), đều AssertionError ở trạng thái dòng cp_stage_runs (FAILED_RETRYABLE/STALE thay vì RUNNING hoặc FAILED_FINAL).

## 6. Mục mở

- Đây là ngữ nghĩa tạm vì flow chưa nối D8-G-01. Khi hết lượt thử lại (`failed` retryable hoặc `stale` ở lần thứ `maximum_attempts`), dòng giữ RUNNING không có problem, job giữ ACTIVE và workflow con kết thúc FAILED. Terminal rule CT-CMN-010 (`docs/09-contracts/00-common-contract.md:197`) và D8-G-01 thuộc gói sửa riêng, không làm trong gói này.
- Nơi đọc cp_stage_runs (UI, projection) sẽ thấy RUNNING tới activity cuối.
- Stage `debug_observe` của DebugStageWorkflow có bảng rỗng nên activity đầu đóng dòng; stage `collect` còn đóng dòng sớm (activity cuối chạy fan-out cùng `stage_run_id`).
- Control đã chọn hướng A trong đính chính ngày 31/10/2026; dòng 335 của PW-G4 đổi theo.

## 7. Xác nhận UTF-8

Tệp ghi bằng công cụ ghi tệp (UTF-8 không BOM); chữ tiếng Việt có dấu còn nguyên sau khi đọc lại.
