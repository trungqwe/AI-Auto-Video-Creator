# Báo cáo: Dòng stage run phản ánh kết quả của cả stage nhiều activity (PW-G2-FIX1)

Task: PW-G2-FIX1
Nhóm lỗi: R24 (kết quả activity thứ hai trở đi của stage nhiều activity bị bộ ghi bỏ)
Nguồn lỗi: CP7-10 lượt 3 và 4 (30/10/2026): job FAILED_FINAL mà không dòng cp_stage_runs nào hỏng

Trạng thái: ỨNG VIÊN SẴN SÀNG ĐỂ KIỂM, còn đúng một lệnh kiểm bắt buộc đỏ do xung đột hành vi. Mã recorder, test mới và test PW-G2 đã xong. Test test_pw_g4_job_states.py::test_job_chain_through_the_result_recording_dispatcher (dòng 335, chủ PW-G4, ngoài owned paths) hỏng vì khẳng định hành vi cũ mà yêu cầu nghiệm thu đòi đổi; chi tiết, cách tái hiện trên candidate và đề xuất ở mục 6d. Gói không sửa tệp ngoài owned paths và không làm yếu recorder.

## 1. Tóm tắt lỗi và cách sửa

Lỗi: `ResultRecordingDispatcher` chỉ chuyển PENDING sang RUNNING và chỉ ghi khi dòng còn RUNNING. Mọi activity của một stage dùng chung `stage_run_id`, nên activity succeeded đầu tiên đã đóng dòng thành SUCCEEDED và kết quả của activity sau bị bỏ. Stage analyze (BuildProductionSnapshot rồi AnalyzeContent) và script (GenerateStoryAngles rồi GenerateScript) vì vậy báo SUCCEEDED dù activity sau hỏng, còn job vẫn FAILED_FINAL.

Cách sửa trong `result_recorder.py`:

- Dòng chỉ thành SUCCEEDED ở activity cuối của stage theo `STAGE_ACTIVITIES_BY_WORKFLOW` (hàm `_closes_stage`). Activity succeeded chưa phải cuối thì giữ RUNNING.
- Kết quả failed, outcome_unknown, stale và `ActivityRejected` của activity bất kỳ ghi trạng thái tương ứng kèm problem có thêm khoá `activity` (hàm `_with_activity`).
- `waiting` giữ như cũ (dòng RUNNING và ghi wait_reason); listener vẫn được gọi sau khi ghi.
- Không đổi state machine, `stage_runs.py`, flow hay `activities.py`.

## 2. Tệp đã sửa

- `src/controlplane/application/orchestration/result_recorder.py`
- `tests/integration/prod_wiring/test_pw_g2_fix1_stage_outcome.py` (mới, 10 test: 3 test đơn, 4 ca tham số, lỗi activity đầu, ActivityRejected ở activity sau, waiting ở activity sau; work-order ghi 9 vì đếm ca tham số là một)
- `tests/integration/prod_wiring/test_pw_g2_stage_runs.py`
- `docs/delivery-evidence/pw-g2-fix1/report.md` (báo cáo này)

## 3. Từng dòng test PW-G2 đã đổi kèm lý do

Các ca dùng stage process và activity ProbeMedia, không phải activity cuối (PrepareAudioBed), nên succeeded giữ RUNNING và problem có thêm khoá `activity`.

`CASES` (8 dòng, dạng disposition, extra, status, wait_reason, problem):

1. `('succeeded', {}, 'SUCCEEDED', None, None)` -> `('succeeded', {}, 'RUNNING', None, None)`: ProbeMedia chưa phải activity cuối.
2. `('outcome_unknown', {}, 'OUTCOME_UNKNOWN', None, None)` -> problem `{'activity': 'ProbeMedia'}`.
3. `('stale', {}, 'STALE', None, None)` -> problem `{'activity': 'ProbeMedia'}`.
4. `failed` retryable: problem `{'code': 'X', 'retryable': True}` -> thêm `'activity': 'ProbeMedia'`.
5. `failed` không retryable: problem `{'code': 'X', 'retryable': False}` -> thêm `'activity': 'ProbeMedia'`.
6. `('failed', {}, 'FAILED_FINAL', None, None)` -> problem `{'activity': 'ProbeMedia'}`.
7. `waiting` có `quota_wait`: không đổi.
8. `waiting` không problem (`provider_unavailable`): không đổi.

Test đích danh khác:

- `test_second_dispatch_of_a_finished_stage_run_keeps_the_row`: dùng activity cuối PrepareAudioBed (dựng `ResultRecordingDispatcher` với `ActivityDispatcher({last: handler})`), vì activity không cuối giữ RUNNING nên không tạo dòng đã kết thúc để kiểm "dispatch lần hai không đổi dòng".

Thay đổi ngoài danh sách đích danh (hệ quả bắt buộc của hành vi mới):

- `test_each_disposition_is_committed_in_its_own_transaction`: `(row[11] is not None) == (disposition != 'waiting')` -> `(row[11] is not None) == (status != 'RUNNING')`. Lý do: dòng RUNNING (waiting hoặc succeeded chưa cuối) chưa có finished_at; mọi dòng đã rời RUNNING phải có.
- `test_activity_rejected_passes_through_and_fails_the_stage_run`: problem mong đợi thêm `'activity': 'ProbeMedia'`. Lý do: yêu cầu nghiệm thu đòi problem của ActivityRejected có tên activity.
- `test_listeners_run_after_the_write_with_request_and_result`: kết quả đổi từ succeeded sang `failed` không retryable và `status_at_call == 'FAILED_FINAL'`. Lý do: ProbeMedia succeeded giờ giữ RUNNING; dùng failed để vẫn chứng minh listener thấy trạng thái đã ghi (khác RUNNING).

## 4. Bằng chứng RED (mã production cũ)

Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_g2_fix1_stage_outcome.py -q -p no:cacheprovider` (interpreter khoá, PYTEST_DEBUG_TEMPROOT của lượt).

- Mã thoát: 1.
- Dòng tổng kết nguyên văn: `9 failed, 1 passed in 4.70s`
- Test hỏng bằng AssertionError ở khẳng định trạng thái dòng stage (ví dụ `At index 0 diff: 'SUCCEEDED' != 'RUNNING'`): test_analyze_failure_after_the_snapshot_fails_the_stage_row_and_the_job, test_script_stage_row_stays_running_until_the_last_activity_succeeds, 4 ca test_every_non_success_result_of_the_second_activity_is_recorded, test_failure_of_the_first_activity_fails_the_row_with_its_name, test_activity_rejected_on_the_second_activity_fails_the_row, test_waiting_on_the_second_activity_keeps_the_row_running_with_the_wait_reason.
- Chỉ test_single_activity_stage_keeps_the_old_behaviour đạt.

## 5. Lệnh đã chạy

| Bước | Lệnh | Mã thoát | Dòng tổng kết nguyên văn |
| --- | --- | --- | --- |
| 7 | `pytest tests/integration/prod_wiring/test_pw_g2_fix1_stage_outcome.py -q -p no:cacheprovider` | 0 | `10 passed in 4.49s` |
| 13 | `pytest tests/integration/prod_wiring/test_pw_g2_stage_runs.py -q -p no:cacheprovider` | 0 | `33 passed in 11.97s` |
| 14 | lệnh pytest bắt buộc (G2-FIX1, G2, G4, CAT2, CP5 completion UoW, PERSIST-G) | 1 | `1 failed, 233 passed in 56.44s` (hỏng duy nhất: test_pw_g4_job_states.py::test_job_chain_through_the_result_recording_dispatcher, dòng 335) |
| 15 | probe PW-G2 (không `from src.`, fake, mock trong stage_runs.py và result_recorder.py) | 0 | không có AssertionError |
| 19 | `git diff --check` | 0 | không có cảnh báo |

### Lượt chạy lại sau lệnh làm việc lập lại (trên cùng candidate)

| Bước | Lệnh | Mã thoát | Dòng tổng kết nguyên văn |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/integration/prod_wiring/test_pw_g4_job_states.py -q -p no:cacheprovider` | 1 | `1 failed, 97 passed in 30.25s` (hỏng duy nhất: test_job_chain_through_the_result_recording_dispatcher; `At index 0 diff: ('job-1:analyze:r1', 'RUNNING') != ('job-1:analyze:r1', 'SUCCEEDED')`, test_pw_g4_job_states.py:335) |
| 2 | lệnh pytest bắt buộc đủ 6 tệp (G2-FIX1, G2, G4, CAT2, CP5 completion UoW, PERSIST-G) | 1 | `1 failed, 233 passed in 55.41s` (hỏng duy nhất: test_pw_g4_job_states.py::test_job_chain_through_the_result_recording_dispatcher) |
| 3 | `git diff --check` | 0 | không có cảnh báo |
| 4 | probe PW-G2 | 0 | không có AssertionError |
| 5 | probe report có CP7-10 | 0 | không có AssertionError |
| 6 | probe report có PW-G2-FIX1 và R24 | 0 | không có AssertionError |

## 6. Mục mở

- (a) Stage collect: activity duy nhất CollectSource chạy fan-out với cùng `stage_run_id`, nên dòng thành SUCCEEDED sau lần đầu và kết quả hỏng của các lần fan-out sau vẫn bị bỏ. Chưa xử lý trong gói này.
- (b) Dòng FAILED_RETRYABLE không mở lại khi activity retry thành công (hành vi PW-G2 giữ nguyên).
- (c) Nơi đọc `cp_stage_runs` (UI, projection) sẽ thấy RUNNING tới activity cuối của stage.
- (d) XUNG ĐỘT HÀNH VI với test PW-G4 (cần quyết định của Control)
  - (i) Tệp `tests/integration/prod_wiring/test_pw_g4_job_states.py:335` trong test_job_chain_through_the_result_recording_dispatcher mong `('job-1:analyze:r1', 'SUCCEEDED')`, `('job-1:process:r1', 'SUCCEEDED')`, `('job-1:process:r3', 'SUCCEEDED')` sau khi chỉ chạy BuildProductionSnapshot và ProbeMedia. Theo `STAGE_ACTIVITIES_BY_WORKFLOW` (activities.py dòng 91 và 97), analyze còn AnalyzeContent và process còn bốn activity sau ProbeMedia, nên acceptance đòi các dòng này giữ RUNNING. Cùng một request (stage analyze, BuildProductionSnapshot, succeeded) không thể vừa RUNNING theo acceptance vừa SUCCEEDED theo dòng 335, nên recorder không thể thoả cả hai.
  - (ii) Vì sao Control không tái hiện: chạy trên HEAD tích hợp dùng recorder cũ (đóng dòng ở activity succeeded đầu tiên) nên test đạt; lỗi chỉ xuất hiện khi chạy trên candidate có bản sửa. Cách tái hiện: checkout candidate rồi chạy `python -m pytest tests/integration/prod_wiring/test_pw_g4_job_states.py -q -p no:cacheprovider`; kết quả thật: mã thoát 1, `1 failed, 97 passed in 30.25s`, đúng một test hỏng, với dòng `At index 0 diff: ('job-1:analyze:r1', 'RUNNING') != ('job-1:analyze:r1', 'SUCCEEDED')`.
  - (iii) Giá trị đúng mới của dòng 335: `[('job-1:analyze:r1', 'RUNNING'), ('job-1:process:r1', 'RUNNING'), ('job-1:process:r2', 'RUNNING'), ('job-1:process:r3', 'RUNNING'), ('job-1:sync:r1', 'SUCCEEDED')]`, với sync đúng vì PersistVideoOutput là activity duy nhất của stage sync. Các test PW-G4 khác (ADVANCE_CASES, listener) đạt vì chỉ đi qua JobLifecycleListener.
  - (iv) Hai hướng cho Control: A) mở ownership PW-G4 chỉ cho literal ở dòng 335 rồi giao sửa một dòng; B) ghi nhận ngoại lệ có chủ đích của lệnh kiểm bắt buộc cho test này.

## 7. Xác nhận UTF-8

Tệp được ghi bằng công cụ ghi tệp của agent (UTF-8, không qua PowerShell) và đã đọc lại: chữ tiếng Việt có dấu còn nguyên.
