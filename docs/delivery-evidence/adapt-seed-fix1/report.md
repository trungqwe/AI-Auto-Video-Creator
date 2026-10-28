# ADAPT-SEED-FIX1: ảnh nền seed vào staging và version VERIFIED

## 1. Nhóm lỗi

- Nhóm lỗi xử lý: `R3` (cụ thể lỗi R3b: ảnh seed trước đây chỉ được ghi vào catalog tại `tools/launcher/prod/seed/import_seed.py`, không được chép vào staging và không đăng ký version, dẫn đến việc ứng viên seed không bao giờ có UUID).
- Cách sửa:
  - Với mỗi mục `background_images` (`MediaKind.IMAGE`), chép tệp seed sang `<runtime.staging_root>/media/<sha>.<suffix>` thông qua tệp tạm `.part` rồi dùng `os.replace` (giữ nguyên nếu tệp đích đã tồn tại và đúng kích thước).
  - Gọi `register_staged_artifact(manager, workspace_id=..., staging_root=..., owner_ref='adapt-seed', relative_ref='media/<sha>.<suffix>', retention_ref='durable')` theo chuẩn PW-I1-FIX1.
  - Áp dụng cho cả tài sản mới và tài sản đã có (`assets_existing`) để khi chạy lại có thể bù (catch-up) đầy đủ các ảnh nền còn thiếu.
  - Giữ nguyên các hook visual/audio, không đăng ký artifact version cho hook clip hay hook audio.

## 2. Các tệp đã sửa

- `tools/launcher/prod/seed/import_seed.py`: Bổ sung chép ảnh nền seed vào staging và đăng ký artifact version VERIFIED với owner_ref 'adapt-seed' và retention_ref 'durable'.
- `tests/integration/adapt/seed/test_adapt_seed_import.py`: Chuyển sang fixture `pw_database` (harness PW) chạy trên PostgreSQL 18.6 thật; thêm 3 test xác minh ảnh nền được chép vào staging và đăng ký đúng 12 version/location VERIFIED, kiểm tra tính lũy đạo (idempotency) khi chạy lại và kiểm tra bù ảnh nền cho tài sản đã có trong catalog; không monkeypatch mã production.
- `docs/delivery-evidence/adapt-seed-fix1/report.md`: Báo cáo bằng chứng nghiệm thu gói ADAPT-SEED-FIX1.

## 3. Lệnh kiểm đã chạy

| Lệnh kiểm | Mã thoát | Dòng tổng kết nguyên văn / Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | Không có lỗi khoảng trắng (whitespace) |
| `python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider` | 0 | `16 passed in 40.58s` |
| `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-seed-fix1/report.md').read_text(encoding='utf-8'); assert 'ADAPT-SEED-FIX1' in t and 'R3' in t, 'report'"` | 0 | Chạy ở bước 10 đạt yêu cầu kiểm tra mã gói và mã nhóm lỗi |
| `python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_seed.py').read_text(encoding='utf-8'); assert 'register_staged_artifact' in t and 'os.replace' in t and 'adapt-seed' in t and 'durable' in t, 'import_seed'"` | 0 | Xác nhận các ký hiệu cốt lõi đã có trong import_seed.py |

## 4. Phản ví dụ đã loại trừ

- Chỉ đăng ký tài sản mới: Đã kiểm chứng qua test bù (catch-up) `test_rerun_registers_backgrounds_for_assets_that_already_exist`, các tài sản đã có trong catalog trước đó vẫn được bù đủ 12 version VERIFIED khi import lại.
- Đăng ký nhầm hook clip hoặc audio: Đã kiểm chứng `artifact_counts` trả về đúng 12 version và 12 location, các mục visual/audio hook không bị đăng ký artifact.
- Dùng nhầm retention `per_video`: Đã kiểm chứng thuộc tính `retention_ref` của mọi version ảnh nền seed đều là `durable`.
- Chạy lại sinh version trùng: Đã kiểm chứng qua `test_rerun_keeps_one_version_and_one_location_per_background_image`, số lượng version và location giữ nguyên 12, không sinh thêm bản ghi nào.
