# Báo cáo chuyển giao: cô lập lỗi từng nguồn của fan-out CollectSource (PW-CAT2-FIX2)

- Task: PW-CAT2-FIX2
- Milestone: CP7
- Trạng thái: IMPLEMENTED

## 1. Nhóm lỗi OI-CP7-11-Q6

`DailyCollectionWorkflow` chạy `CollectSource` tuần tự trên mỗi nguồn mà `PlanCollectionCycle` đã claim. `StageGraphFlow._run_stage` (flow.py) trả ngay outcome khác succeeded, nên một nguồn `FAILED_FINAL` (aljazeera, `ITEM_COMMIT_FAILED` từ 01/11) dừng cả stage collect và các nguồn sau mất lượt cả ngày. Đo trên bảng `cp_collection_runs` (lô 875e2e7d và f132d43a của CP7-REMEASURE): `business_date` 01/11 đến 04/11 mỗi ngày chỉ 2 lượt thay vì 7, kể cả nguồn 404 mà `RG-10.failure_isolated` đo.

## 2. Cách sửa

- `ISOLATED_FAN_OUT` chỉ chứa `CollectSource`; patch id là `fan-out-item-isolation`.
- Phần tử hỏng (sau mọi lượt thử của `_run_activity`) được ghi vào `isolated_failures` với các khoá `stage`, `activity`, `index`, `revision`, `input_refs`, `problem`; các phần tử sau vẫn chạy.
- Stage chỉ FAILED khi mọi phần tử đều hỏng; còn ít nhất một phần tử đạt thì stage chạy tiếp.
- Patch Temporal `fan-out-item-isolation` qua `TemporalGateway.patched` chỉ được hỏi khi một phần tử của activity cô lập vừa hỏng. Lịch sử cũ không có marker replay như trước.
- Hành vi không đổi: waiting, revalidate (PW-CAT2-FIX1), retry trong `_run_activity`, `VideoProductionWorkflow` và mọi activity khác, `operation_key`, `stage_run_id`, thứ tự gọi.

## 3. Tệp đã sửa

- `src/controlplane/application/orchestration/workflows/flow.py` (chép nguyên văn từ bản tham chiếu Control, sha256 `4b454d92…`).
- `tests/integration/prod_wiring/test_pw_cat2_flow.py` (chép nguyên văn từ bản tham chiếu Control, sha256 `8a272763…`).
- `docs/delivery-evidence/pw-cat2-fix2/report.md`.

Trước khi chép, sha256 của lane là `106919d4…` (flow.py) và `ef2d47cc…` (test).

## 4. Lệnh đã chạy

`PYTEST_DEBUG_TEMPROOT` đặt là `C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\PW-CAT2-FIX2-implement-r0-ac1b5c0961`.

| Bước | Lệnh | Exit | Kết quả nguyên văn |
| --- | --- | --- | --- |
| 2 (RED, mã cũ) | `python -m pytest tests/integration/prod_wiring/test_pw_cat2_flow.py -q -p no:cacheprovider` | 1 | `8 failed, 30 passed in 7.61s` |
| 4 (mã mới) | cùng lệnh | 0 | `38 passed in 5.16s` |
| 5 (nhóm 1, 11 tệp) | lệnh pytest 11 tệp prod_wiring và convergence | 0 | `171 passed in 127.59s (0:02:07)` |
| 6 (nhóm 2) | `python -m pytest tests/unit/orchestration -q -p no:cacheprovider` | 0 | `1134 passed, 307 subtests passed in 1.44s` |
| 7 | probe sha256 | 0 | không AssertionError |
| 8 | probe tĩnh flow.py | 0 | không AssertionError |
| 9 | probe tĩnh test | 0 | không AssertionError |
| 10 | probe CRLF | 0 | không AssertionError |
| 12 | probe report.md | 0 | không AssertionError |
| 13 | `git diff --check` | 0 | không cảnh báo |

Test đỏ ở bước 2 (đúng 8 test mới, lỗi do `flow.py` chưa có `ISOLATED_FAN_OUT`, không phải lỗi import hay setup):

- `test_isolated_fan_out_is_only_collect_source_and_has_its_own_patch`
- `test_a_failed_source_is_recorded_and_the_next_sources_still_run`
- `test_the_collect_stage_fails_only_when_every_source_fails`
- `test_a_waiting_source_after_an_isolated_failure_resumes_without_rerunning_the_failure`
- `test_without_the_patch_the_first_failed_source_stops_the_stage_as_before`
- `test_video_fan_out_still_stops_at_the_first_failed_image_and_never_asks_the_patch`
- `test_temporal_daily_collection_runs_the_source_after_a_failed_one_and_replays`
- `test_temporal_history_without_the_marker_replays_the_old_stop_and_breaks_if_the_patch_is_forced`

Ở bước 5, `M2_TEST_PG_DSN` không được đặt trong shell của worker. Nhóm 1 vẫn báo 171 passed và không có skip hay lỗi môi trường; số này đúng bằng kỳ vọng của nguyên mẫu.

## 5. Giới hạn còn lại

- Không sửa gốc lỗi aljazeera (`ITEM_COMMIT_FAILED` do guard `execution_generation` của checkpoint, thuộc gói A-06-FIX1). Aljazeera và các nguồn có checkpoint generation cao (bbc-tech, bbc, npr, nasa) vẫn `FAILED_FINAL` mỗi ngày nhưng không còn chặn nguồn khác.
- Phần tử trả waiting vẫn giữ stage chờ như trước.
- `DailyCollection` không có signal `RetryStage`, nên nguồn hỏng chỉ được thu lại ở chu kỳ sau.
- `isolated_failures` chỉ nằm trong kết quả workflow, chưa có bảng hay Dashboard đọc nó.

## 6. Tính toàn vẹn ký tự

Tệp này được ghi bằng công cụ ghi tệp của agent (UTF-8, LF, không BOM) và đã được đọc lại sau khi ghi; chữ tiếng Việt có dấu còn nguyên, không có ký tự `?` thay thế.
