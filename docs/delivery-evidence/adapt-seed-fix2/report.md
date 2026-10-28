# ADAPT-SEED-FIX2: hook seed (clip và âm thanh) vào staging và version VERIFIED

## 1. Nhóm lỗi

- Nhóm lỗi xử lý: `R10` (phân giải hook trong gói `ADAPT-SEED-FIX2`). Hook seed có artifact_version_ref `seed:<id>:sha256:<sha>` nhưng `_stage_images` chỉ xử lý IMAGE nên tệp hook không có trong staging và không có version; artifact_version_ref của hook không đổi được (CT-HOOK-002, catalog/application/hooks.py:94).
- Cách sửa:
  - `_stage_images` xử lý cả visual_hooks và audio_hooks, chép sang `<staging>/media/<sha>.<hậu tố chữ thường>`.
  - Gọi `register_staged_artifact` với owner_ref `adapt-seed` và retention_ref `durable`, kể cả hook đã có (chạy lại thì bù).
  - Không đổi `import_hook`, không đổi `artifact_version_ref`, giữ `media_sha256` trong technical_metadata.

## 2. Các tệp đã sửa

- `tools/launcher/prod/seed/import_seed.py`: Bỏ điều kiện lọc MediaKind.IMAGE trong `_stage_images` để chép và đăng ký artifact version VERIFIED cho cả visual_hooks và audio_hooks với owner_ref `adapt-seed` và retention_ref `durable`; cập nhật docstring `import_seed`.
- `tests/integration/adapt/seed/test_adapt_seed_import.py`: Cập nhật kỳ vọng 12 thành 22 ở ba test ảnh nền; thêm 4 test kiểm tra hook được chép vào staging và đăng ký version VERIFIED, tính lũy đạo khi chạy lại, bù hook đã có và bảo toàn artifact_version_ref cùng media_sha256.
- `docs/delivery-evidence/adapt-seed-fix2/report.md`: Báo cáo bằng chứng nghiệm thu gói ADAPT-SEED-FIX2.

## 3. Lệnh kiểm đã chạy

| Lệnh kiểm | Mã thoát | Dòng tổng kết nguyên văn / Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | Không có lỗi khoảng trắng (whitespace) |
| `python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider` | 0 | `20 passed in 52.37s` |
| `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-seed-fix2/report.md').read_text(encoding='utf-8'); assert 'ADAPT-SEED-FIX2' in t and 'R10' in t, 'report'"` | 0 | Chạy ở bước 11 đạt yêu cầu kiểm tra mã gói và mã nhóm lỗi |

## 4. Phản ví dụ đã loại trừ

- Tạo hook revision mới để đổi artifact_version_ref: loại bởi test `test_hook_revisions_keep_artifact_version_ref_and_media_sha256` và so sánh `hook_revisions` trước/sau khi chạy lại.
- Chỉ đăng ký hook mới: loại bởi `test_rerun_registers_hooks_that_already_exist_without_new_hook_revision`.
- Retention per_video: loại bởi kiểm `retention_ref == 'durable'` trong `test_hooks_are_staged_and_registered_as_verified_versions`.
- Chạy lại sinh version hay location thứ hai: loại bởi `test_rerun_keeps_one_version_and_one_location_per_hook` (22 version, 22 location).
