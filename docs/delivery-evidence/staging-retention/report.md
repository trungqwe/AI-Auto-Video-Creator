# Báo cáo STAGING-RETENTION (CP7, nhóm lỗi OI-CP7-11-Q6)

## 1. Lỗi và nhóm lỗi

Nhóm lỗi: **OI-CP7-11-Q6**. Lô f132d43a của CP7-REMEASURE (HEAD a8a9246, 03/11/2026): RG-10 `working_set_cap` trượt, `max_working_set_bytes` 23,05 GB > 20 GiB. Số đo là `dir_size_bytes(staging)` và tăng khoảng 1 GB mỗi 40 phút vì production không có đường nào dọn staging (`VideoProductionWorkflow` dừng ở stage complete, `MaintenanceWorkflow` không ai khởi, `request_cleanup_evaluation_handler` không cấp authorization, `LocalCleanupExecutor` chỉ có test).

Chính sách đã duyệt: `retention.output.local_cleanup = only_after_cloud_verified`; `retention.temporary` = 24 giờ từ `checked_and_completed`; original và reusable (`media/`) giữ.

## 2. Tệp đã đổi

Chép nguyên văn từ bản tham chiếu Control `D:/AIAVC_IMGPROTO/ref/staging-retention/`, khớp sha256 (probe băm đạt):

- `src/controlplane/infrastructure/storage/staging_retention.py` (mới)
- `tools/launcher/prod/retire_staging.py` (mới)
- `tests/integration/storage/test_storage_staging_retention.py` (mới)
- `tools/launcher/launcher.py`: đúng ba chỗ, `STAGING_RETENTION_INTERVAL_SECONDS = 300.0`, hàm `build_staging_retention`, và nối vòng dọn `retention.run_forever(...)` vào `start_worker`. `git diff` chỉ thêm 25 dòng; `COMMANDS` và các vòng nền khác không đổi.
- `docs/delivery-evidence/staging-retention/report.md` (báo cáo này, do Worker viết)

## 3. Hành vi

- Điều kiện dời: job COMPLETED có dòng `cp_completion_ledger`. `out/<id>.mp4` và bản phẳng `<staging>/<artifact_version_id>` chỉ dời khi version có location cloud VERIFIED. `voice/voice-artifact-<sha256>`, bản phẳng và `voice/tmp/<sha256>.wav` dời sau 24 giờ. `media/` và `audio_library/` giữ.
- Dời, không xoá: tệp được chuyển sang thùng rác; mỗi tệp kiểm kích thước và SHA-256, bản ghi nằm ở `<trash>/<YYYYMMDD>/retired.jsonl`. Thùng rác nằm ngoài staging.
- Trần mỗi lượt: 200 tệp và 4 GiB.
- Idempotent: lượt thứ hai không dời thêm.
- CSDL chỉ đọc, đúng một câu SELECT (`RETENTION_SQL`).
- Lệnh `tools/launcher/prod/retire_staging.py` chạy khô theo mặc định; `--apply` không được chạy trong lane (Worker không chạy script này).

## 4. Lệnh kiểm đã chạy (trên HEAD a8a9246 cộng thay đổi gói)

| Lệnh | Mã thoát |
| --- | --- |
| `git diff --check` | 0 |
| pytest nhóm 1 (7 tệp test, `-q -p no:cacheprovider`) | 0 |
| `python -m pytest tests/unit/storage -q -p no:cacheprovider` | 0 |
| Probe 4-20 và 22-23 (sha256 chuẩn hoá LF, sha256 thô, RETENTION_SQL, start_worker, không CR, launch-fix2, PW-W2-FIX5, PW-W1-FIX1, worker caps, imagegen, relay, hooks, CP2A-LAYOUT, pyproject) | 0 |
| Probe báo cáo (STAGING-RETENTION, OI-CP7-11-Q6) | 0 |

Dòng tổng kết nguyên văn của pytest:

- Nhóm 1: `495 passed, 7 skipped in 13.97s` (7 skip là symlink cần quyền)
- Nhóm 2 (`tests/unit/storage`): `356 passed, 239 subtests passed in 0.52s`

## 5. Giới hạn đã biết

- Trạng thái location local trong CSDL giữ VERIFIED sau khi dời; bản ghi dời nằm ở `retired.jsonl`, không phát `CleanupCompleted`. Đường `CleanupAuthorization` đầy đủ của CT-STO-008 và việc xoá hẳn thùng rác để backlog.
- Không dọn tệp của job FAILED_FINAL, render thử lại không ghi version, `voice/tmp` mồ côi, phụ đề `.ass`, beds trong `audio_library`; `media/` giữ nên vẫn tăng.
- Câu SELECT chưa chạy trên PostgreSQL thật; Control chạy `retire_staging.py` chạy khô trên CSDL của launcher sau khi gộp làm phép thử đầu.
