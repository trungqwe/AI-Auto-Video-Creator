# Báo cáo bằng chứng A-06-FIX1

## 1. Môi trường

- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.
- HEAD trước khi sửa: `8e7d112` (nhánh `trungqwe/lane-a-06-fix1`).
- `PYTEST_DEBUG_TEMPROOT=C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\A-06-FIX1-implement-r0-ac1b5c0961`.
- Bản tham chiếu (chỉ đọc): `D:/AIAVC_IMGPROTO/ref/a-06-fix1/`.

## 2. Nhóm lỗi

- Mã nhóm lỗi: **OI-CP7-11-Q6**.
- Nguồn `aljazeera` ở trạng thái FAILED_FINAL mỗi ngày từ business_date 01/11 tới 04/11: 25/25 item `ITEM_COMMIT_FAILED`, 0 gói.
- Các nguồn bbc-tech, bbc, npr, nasa sẽ hỏng y hệt khi tới lượt.

## 3. Gốc lỗi

- `GrantIssuer` cấp `execution_generation` theo lần cấp thứ n trong một `stage_run_id`. Fan-out collect dùng chung một `stage_run_id` dạng `<workflow>:collect:r<revision>`, nên generation của một nguồn bằng vị trí của nó cộng số lần thử trước đó và đếm lại từ đầu ở mỗi workflow.
- Lượt 31/10 ghi checkpoint `aljazeera` generation 4 (revision 74). Từ 01/11 `aljazeera` nhận grant generation 2, nên `advance_checkpoint` ném `CHECKPOINT_STALE_GENERATION` (2 < 4) trong UoW của từng item.
- `collect_source._collect_item` đổi lỗi đó thành `ITEM_COMMIT_FAILED`.

## 4. Điều kiện mới của CHECKPOINT_STALE_GENERATION

- `advance_checkpoint` thêm `same_attempt = proposed.run_id == current.run_id and proposed.attempt_id == current.attempt_id`.
- `CHECKPOINT_STALE_GENERATION` chỉ ném khi `same_attempt` và generation thấp hơn (`if same_attempt and proposed.execution_generation < current.execution_generation:`).
- Giữ nguyên: kiểm lineage, chuỗi revision (`current.revision + 1`), `CHECKPOINT_ITEM_NOT_DURABLE`, và kiểm `is_grant_current` / `STALE_GRANT`.

## 5. Test A-18 được thay

- Bị thay: `test_old_generation_checkpoint_write_is_rejected_even_if_the_grant_port_wrongly_accepts_it`.
- Thay bằng: `test_a_later_daily_run_with_a_lower_grant_generation_still_commits_after_the_previous_run` (run `op-key-2` ngày 2026-10-19 với `OLD_GENERATION` (2) sau run generation 3 thành công thì commit 1 gói, checkpoint revision tăng, generation 2, `run_id` `run:op-key-2`).
- Lý do: test cũ ghim hành vi sai (run ngày khác với generation thấp hơn bị từ chối), chính là lỗi production ở mức handler. `test_stale_grant_is_rejected_without_any_commit` giữ nguyên.

## 6. Tệp đã sửa

Ba tệp được chép nguyên văn từ bản tham chiếu (sha256 sau chuẩn hoá LF khớp `SHA256SUMS`):

- `src/source_ingestion/domain/checkpoint.py` (294af64f57b1a57ab35927c8ff59a8c96e47811be159c9696c75ccdc1ea1d4ff)
- `tests/unit/collection/test_a06_checkpoint.py` (ad6307d0e0a35e7e16e5d74876292d7812920b247cc9eeff4857b276bce8559f)
- `tests/integration/collection/test_a18_worker_activity.py` (27e218159a9f8678369fe7b04be075a919f3810ee2f6c8aef4f0924ce8230ba8)

Cùng `docs/delivery-evidence/a-06-fix1/report.md` (báo cáo này).

## 7. Lệnh đã chạy

| Bước | Lệnh | Exit | Dòng tổng kết pytest nguyên văn |
| --- | --- | --- | --- |
| 1 (baseline HEAD) | `pytest tests/unit/collection tests/integration/collection -q -p no:cacheprovider` | 0 | `600 passed, 403 subtests passed in 1.60s` |
| 4 (RED, test mới trên mã cũ) | `pytest tests/unit/collection/test_a06_checkpoint.py tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider` | 1 | `5 failed, 49 passed, 22 subtests passed in 0.27s` |
| 6 (GREEN hai tệp) | cùng lệnh bước 4 | 0 | `50 passed, 26 subtests passed in 0.18s` |
| 7 (nhóm bắt buộc) | như bước 1 | 0 | `603 passed, 407 subtests passed in 0.92s` |
| 8 (Postgres) | `pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider` | 0 | `22 passed in 18.16s` |
| 9 | probe sha256 với `want` điền sẵn | 0 | không áp dụng |
| 10 | probe cấu trúc `advance_checkpoint` | 0 | không áp dụng |
| 11 | probe tên test | 0 | không áp dụng |
| 12 | probe không có CR | 0 | không áp dụng |
| 15 | `git diff --check` | 0 | không output |

RED đúng oracle: `AssertionError: 'CHECKPOINT_STALE_GENERATION' != 'CHECKPOINT_REVISION_CONFLICT'` ở unit và `assert 'failed' == 'succeeded'` ở test A-18 mới (25/25 item `ITEM_COMMIT_FAILED`); không phải lỗi import.

## 8. Giới hạn và backlog

- Thông điệp `CheckpointRejected` chưa đọc trực tiếp vì `_finish` chỉ lưu `code:locator` trong warnings; backlog gói A-11: ghi mẫu thông điệp lỗi item đã che.
- Run cùng ngày được khôi phục bởi workflow mới mà vẫn cùng attempt vẫn so generation như cũ.
- Generation vẫn đếm theo `stage_run_id` dùng chung; đổi cách cấp là việc của G-04.
- Sau khi gộp cần một chu kỳ thu thập thật để xác nhận aljazeera, bbc-tech, bbc, npr, nasa đều COMPLETED.
