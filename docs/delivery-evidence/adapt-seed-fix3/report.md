# ADAPT-SEED-FIX3: quyền ảnh bài theo quyết định của user

## 1. Nhóm lỗi

OI-CP7-11-Q1 (CLOSURE_NOTE CP7/RG-13 ngày 02/11/2026 và OI-ADAPT-10 ngày 25/10/2026): `hooks.json`, kiểm của `import_seed` và tài liệu kế hoạch còn luật cũ (ảnh UNVERIFIED không vào video, chỉ tài sản seed).

## 2. Các tệp đã sửa

- `tools/launcher/prod/hooks.json`: khối `rights` ghi `article_images_in_sample_video` là true, bỏ `pending_user_checkpoint`, thêm `article_image_decision_refs`; giữ `SELF_GENERATED` và `UNVERIFIED`.
- `tools/launcher/prod/seed/import_seed.py`: thêm `ARTICLE_IMAGE_DECISION_REFS`, viết lại `_require_rights`.
- `tests/integration/adapt/seed/test_adapt_seed_rights.py` (mới): năm test về khối rights (17 ca tham số hoá cho khối sai).
- `tests/integration/adapt/seed/test_adapt_seed_import.py`: test ghim giá trị cũ nay ghim `is True` và không còn `pending_user_checkpoint`.
- `tests/integration/adapt/config/test_adapt_config_profile.py`: thêm hai assert tương ứng vào `test_hooks_structure_and_recipes`.
- `docs/implementation/cp7/plan.md`, `docs/implementation/cp7/slices.md`, `docs/implementation/adapt/plan.md`, `docs/implementation/adapt/slices.md`, `docs/implementation/prod-wiring/inventory.md`, `docs/implementation/prod-wiring/plan.md`: sửa câu chữ tại chỗ, giữ nguyên số dòng.
- `docs/delivery-evidence/adapt-seed-fix3/report.md`: báo cáo này.

## 3. Lệnh kiểm đã chạy

Interpreter khoá của lane, `PYTEST_DEBUG_TEMPROOT` riêng của lượt. Các probe `python -c` của bước 18–26 được chạy bằng một script tạm ngoài repo (scratchpad) chứa đúng nội dung assert của từng lệnh, không phải chép nguyên dòng lệnh.

| Lệnh | Mã thoát | Dòng tổng kết nguyên văn |
| --- | --- | --- |
| Bước 5 (RED, trước khi sửa hooks.json và import_seed.py): `python -m pytest tests/integration/adapt/seed/test_adapt_seed_rights.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` | 1 | `22 failed, 12 passed in 1.40s` |
| Bước 9 (GREEN): cùng lệnh | 0 | `34 passed in 1.22s` |
| Bước 10: `python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider` | 0 | `20 passed in 56.39s` |
| Bước 17: `git diff --check` | 0 | không có lỗi khoảng trắng |
| Bước 18: probe hooks.json và import_seed.py | 0 | đạt |
| Bước 19: probe tên test và nội dung test | 0 | đạt |
| Bước 20: probe tài liệu | 0 | đạt (lần đầu đỏ ở `probe key kept` vì `cp7/plan.md` chưa có tên khoá `rights_unverified_excluded`; đã thêm tên khoá vào câu RG-13, không đổi số dòng, chạy lại đạt) |
| Bước 21: probe `import_seed_media` | 0 | đạt |
| Bước 22: probe `register_discovery` và `import_hook` | 0 | đạt |
| Bước 23: probe runbook và số 136 | 0 | đạt |
| Bước 24: probe Aligner thứ nhất | 0 | đạt |
| Bước 25: probe Aligner thứ hai | 0 | đạt |
| Bước 26: probe bố cục CP2A-LAYOUT | 0 | đạt |
| Bước 28: probe `report.md` | 0 | đạt yêu cầu kiểm tra mã gói và mã nhóm lỗi |

## 4. Câu chữ RG-13 và OI-PW-03 đã sửa

- `cp7/plan.md`: mục 3 (dòng OI-ADAPT-10), ngưỡng RG-13 (kèm tên khoá `rights_unverified_excluded`), R2 Media Alpha, mục 9 Ngoài phạm vi.
- `cp7/slices.md`: CP7-14 (requirement (1), instrument, counterexample); giữ nguyên probe `python -c` và khoá `rights_unverified_excluded`.
- `adapt/plan.md`: mục 7.8, đầu mục 9, hàng OI-ADAPT-10 (đúng 5 dấu `|`), mục 9.1.
- `adapt/slices.md`: ADAPT-SEED.
- `prod-wiring/inventory.md`: mục 8, mục 9; bỏ chỗ trỏ số dòng cũ của `adapt/plan.md`.
- `prod-wiring/plan.md`: DQ-11 bổ sung 02/11/2026; OI-PW-03 ĐÃ XONG.

## 5. Kiểm của import_seed

`_require_rights` chạy trước khi ghi dòng nào, ném `SeedError` theo thứ tự: (1) không có khối rights dạng dict; (2) nhãn khác UNVERIFIED; (3) `article_images_in_sample_video` không phải True; (4) còn khoá `pending_user_checkpoint`, kể cả null; (5) `article_image_decision_refs` không phải list chuỗi hoặc thiếu mã nào của `ARTICLE_IMAGE_DECISION_REFS`. Khối cũ bị từ chối; nhãn UNVERIFIED giữ nguyên (`SeedImportReport` vẫn trả `UNVERIFIED`).

## 6. Phản ví dụ đã loại trừ

- Test mới hỏng với mã cũ (bước 5: 22 failed) rồi đạt sau khi sửa (bước 9).
- Khối cũ (cờ false kèm `pending_user_checkpoint`) và khối thiếu `article_image_decision_refs` bị từ chối (test tham số hoá và `test_import_seed_checks_the_rights_before_it_touches_the_database`).

## 7. OI-CP7-11-Q1

GIẢ ĐỊNH: tài liệu hiện hành không định nghĩa mã này (như báo cáo adapt-e-media-fix4); dùng làm nhãn nhóm lỗi quyền và che mờ ảnh bài. Gói này chỉ sửa cấu hình, kiểm nhập seed, test và câu chữ; hành vi ảnh bài nằm ở ADAPT-A-FIX1, ADAPT-E-MEDIA-FIX4, PW-D3-FIX3. Câu hỏi chờ user về ảnh DETECTION_FAILED/TRANSFORM_FAILED vẫn mở, gói không đóng. Định nghĩa CP7-14 đã biên dịch trong Portfolio (compiled/impl-cp7.json) còn câu chữ cũ, Control xử lý khi mở gói.
