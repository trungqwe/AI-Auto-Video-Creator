# CP7-11-FIX2 — RG-10.failure_isolated chỉ tính lượt thu thập từ lúc launcher của phép đo khởi động

## 1. Nhóm lỗi: OI-CP7-11-Q6

- `OvernightDb.collection_runs` chỉ lọc `r.business_date >= business_date_vn(window_start)`, nên tính cả lượt thu thập tạo trước phép đo. Lô `f132d43a` tạo 07:48Z ngày 03/11, còn lượt của business_date 03/11 tạo 17:13Z ngày 02/11, tức trước 14,5 giờ.
- `videos_completed_after_source_failure` lấy `max(updated_at)` của mọi lượt `FAILED_FINAL` của nguồn, kể cả ngày trước, nên `completed_after_failure` luôn bằng số video của lô.
- Bằng chứng PASS cũ của `RG-10.failure_isolated` trong CP7-11 là mượn lượt của ngày trước, không phải lượt chạy trong phép đo; cần đo lại.

## 2. Tệp đã sửa

Hai tệp được chép nguyên văn từ bản tham chiếu Control `D:/AIAVC_IMGPROTO/ref/cp7-11-fix2/`:

- `tools/real/cp7_overnight_monitor.py` (sha256 `d7b2ebec140fc8b4b35ad559b95e7b8ea25cb8e39182a0958f001f24fad0974d`)
- `tests/real/test_cp7_overnight.py` (sha256 `f988874e6cae6da7e886a53a9d06100c9dd3479a7759af0f119b3df44aabbd32`)

## 3. Cách sửa

- Mốc `collection_since = db.db_now()` được lấy trong `run_overnight` ngay sau `d.require_no_other_workflows()` và trước `d.start_capturing(work_dir, 'first')`, vì launcher khởi chu kỳ bù ngay khi lên (lô `875e2e7d`: lượt đầu tạo 18:04:28Z, lô tạo 18:04:29Z, `window_start` lấy sau khi launcher lên).
- `collection_runs` và `videos_completed_after_source_failure` lọc thêm `r.created_at >= collection_since`.
- `audit_run` dùng `collection_since`, dự phòng `window_start` khi mốc là `None`.

## 4. Lệnh kiểm đã chạy

Không đặt `CP7_RG10_LIVE`, nên 15 test `test_rg10_*` bị bỏ qua và không chạy lô thật.

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| Baseline HEAD 8e7d112: `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider` | 0 | `43 passed, 15 skipped in 0.59s` |
| Sau sửa: `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider` | 0 | `45 passed, 15 skipped in 0.34s` |
| `git diff --check` | 0 | không có lỗi khoảng trắng |
| probe sha256 hai tệp so với bản tham chiếu | 0 | khớp |
| probe AST (chữ ký, điều kiện `created_at`, thứ tự mốc, `audit_run`, trường `OvernightRun`) | 0 | đạt |
| probe tên ba test | 0 | đạt |
| probe không có CR | 0 | đạt |
| probe report.md có `CP7-11-FIX2` và `OI-CP7-11-Q6` | 0 | đạt |

## 5. Giới hạn

- Lô không trùm chu kỳ thu thập (không khởi lại launcher và không qua nửa đêm giờ Việt Nam) sẽ ra `BLOCKED` với `target_runs=0` trung thực thay vì PASS mượn.
- Muốn đo `RG-10.failure_isolated` cần lô có chu kỳ thu thập chạy trong phép đo và `PW-CAT2-FIX2` đã gộp.
- `report.md` của CP7-11 không đổi; bằng chứng RG-10 cũ cần đo lại.
