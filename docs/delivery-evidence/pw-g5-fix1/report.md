# Báo cáo chuyển giao: lô chạy tối đa K video con cùng lúc (PW-G5-FIX1)

Task: PW-G5-FIX1
Mã tham chiếu R34 (nêu trong lệnh kiểm của task)
Trạng thái: IMPLEMENTED

## 1. Tóm tắt và nhóm lỗi R34

Lô trước đây chạy nối tiếp: `batch.py` gọi `run_child` và chờ con xong mới cấp job kế. Nay `BatchParams` có `max_concurrent_videos` (mặc định 1). K <= 1 đi nhánh `_run_sequential` (thân cũ chuyển nguyên văn); K > 1 đi `_run_concurrent(K)`, giữ tối đa K video con chạy cùng lúc. `AllocateJob` vẫn tuần tự và luôn await xong trước `start_child` và trước lần cấp sau. Đã sửa mọi vị trí của mẫu này: chỉ có một nhánh `run` duy nhất trong `ProductionBatchFlow`.

## 2. Tệp đã đổi (chỉ 5 owned paths)

- `src/controlplane/application/orchestration/workflows/batch.py`: `BatchParams.max_concurrent_videos` và kiểm hợp lệ trong `from_payload`; `ChildHandle`; `BatchGateway.start_child` / `wait_first`; `ProductionBatchFlow.run` / `_run_sequential` / `_run_concurrent`; `__all__`.
- `src/controlplane/application/orchestration/workflows/definitions.py`: `BATCH_CONCURRENCY_PATCH_ID = 'batch-concurrent-videos'`; `TemporalGateway.start_child` / `wait_first`; `ProductionBatchWorkflow.run`.
- `tests/unit/orchestration/test_g_batch_concurrency.py` (mới).
- `tests/integration/prod_wiring/test_pw_g5_fix1_batch_concurrency.py` (mới).
- `docs/delivery-evidence/pw-g5-fix1/report.md` (mới).

## 3. Bằng chứng RED (mã cũ)

- Bước 6: `python -m pytest tests/unit/orchestration/test_g_batch_concurrency.py -q`, exit code 1, `17 failed, 3 passed`. Thất bại gồm: từ chối `0, -1, True, False, '4', 1.5, None` (không ném ValueError), `test_k4_target10_peak_exactly_4`, `test_two_consecutive_jobs_with_same_candidate_run_together`, `test_cancel_while_waiting_cancels_every_running_child` (`assert 'returned' == 'cancelled'`).
- Bước 9: `python -m pytest tests/integration/prod_wiring/test_pw_g5_fix1_batch_concurrency.py -q`, exit code 1, `1 failed, 1 passed in 51.65s`. `test_k4_runs_four_children_at_once_and_replays` hỏng vì `threading.BrokenBarrierError` (mã nối tiếp chỉ có một bên tới Barrier(4) nên hết hạn); `test_k1_without_key_has_no_marker_and_replays` đạt.

## 4. Lệnh đã chạy trên mã mới

| Lệnh | Exit code | Dòng tổng kết pytest / kết quả |
| --- | --- | --- |
| probe `definitions.py` (bước 18) | 0 | assert đạt |
| probe `batch.py` (bước 19) | 0 | assert đạt |
| unit mới + CP-6 tĩnh + catalog + video flow | 0 | `50 passed in 1.80s` |
| `test_pw_g5_fix1_batch_concurrency.py` + PW-G5 + PW-G6 + PW-G4-FIX1 | 0 | `51 passed in 44.99s` |
| `test_pw_e2e_batch_video.py` | 0 | `10 passed, 1 warning in 123.90s (0:02:03)` |
| hồi quy rộng (orchestration, collection, ingestion, creative, voice, render, config, catalog, storage) | 0 | `3438 passed, 1034 subtests passed in 5.52s` |
| `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7544 passed, 1 warning, 2561 subtests passed in 21.83s` |
| probe `report.md` và `git diff --check` | xem mục 7 | chạy sau khi ghi báo cáo |

## 5. Quyết định thiết kế

- K <= 1 gọi `_run_sequential`, thân cũ chuyển nguyên văn; chỉ đổi dòng định nghĩa.
- `workflow.patched(BATCH_CONCURRENCY_PATCH_ID)` chỉ được gọi khi K > 1. Lô K=1 không ghi marker nên lịch sử cũ (không có khoá `max_concurrent_videos`, không có marker) vẫn phát lại tuần tự như trước. Nếu K > 1 mà chưa patched (replay history cũ), K bị hạ về 1 bằng `dataclasses.replace`.
- `AllocateJob` luôn tuần tự.
- Hai job liên tiếp cùng tin chạy đồng thời là hợp lệ; không hoãn hay lọc theo `candidate_ref`.
- Con hỏng khi khởi chạy (`start_child` ném lỗi) ghi `STATUS_FAILED`, không chiếm suất.
- Huỷ khi chờ thì `cancel` mọi handle đang chạy rồi raise lại.
- `FinalizeBatch` đúng một lần sau con cuối; kết quả cùng khoá như nhánh tuần tự.
- Test tích hợp xác nhận: K=4 có marker `batch-concurrent-videos`, đỉnh handler 4, tối đa 4 child mở, Replayer đạt; K=1 không marker, Replayer đạt.

## 6. Giới hạn

- Số 10 luồng và mặc định 6 là tính toán của Control, chưa đo 10 luồng thật.
- Gói này chưa làm K > 1 xảy ra trong production: relay chỉ gửi khoá khi PW-G6-FIX1 gộp.
- Phát lại history của mã cũ không kiểm bằng fixture.
- Rollback mã sau khi đã có lô K > 1 đang chạy thì patched không che được.
- Cấp phát song song giữa hai lô khác nhau vẫn có thể đua (có từ trước); CP7-11 chỉ nên chạy một lô.

## 7. Kiểm tra cuối

Đã đọc lại báo cáo này sau khi ghi và xác nhận chữ có dấu tiếng Việt còn nguyên. Kết quả `git diff --check` và probe `report.md` ghi trong thông báo `worker_done`.
