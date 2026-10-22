# Báo cáo bằng chứng chuyển giao: ADAPT-SEED

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới trong phạm vi quyền sở hữu (owned paths):
- `tools/launcher/prod/seed/make_seed_media.py`: Sinh 22 tệp media seed tự tạo (12 ảnh PNG 1080x1920 qua zlib, 5 âm thanh hook WAV 24000 Hz qua wave, 5 video hook MP4 h264 1080x1920 30 fps qua FFmpeg đã ghim SHA-256 với nguồn lavfi và seed cố định) vào thư mục dữ liệu ngoài cây Git; in SHA-256 từng tệp và xuất manifest `seed-manifest.json`.
- `tools/launcher/prod/seed/import_seed.py`: Nhập 7 nguồn RSS cơ sở kèm Tier từ `sources.json` qua `SourceCommandHandler` (dịch vụ ứng dụng Phân hệ A) trên UoW của `build_collection_services`, và 10 hook cùng 22 tài sản seed từ `hooks.json` qua `register_discovery` và `import_hook` (dịch vụ ứng dụng Phân hệ C) trực tiếp trên kho dữ liệu PostgreSQL; kiểm tra HTTPS, quyền bài viết và media trước khi ghi; bảo đảm tính bất biến khi chạy lặp lại (idempotent).
- `tests/integration/adapt/seed/test_adapt_seed_import.py`: Bộ kiểm thử tích hợp 13 test cases bao gồm tính ổn định của SHA-256 giữa các lần chạy, kiểm tra định dạng media, thư mục seed ngoài cây Git, xác thực ghim FFmpeg, kiểm tra nhập lặp lại không nhân đôi bản ghi, kiểm tra giữ quyền và nguồn gốc tài sản, từ chối nguồn HTTP, từ chối thiếu media, từ chối hồ sơ không phải production, và kiểm tra tĩnh không dùng mạng hay urllib.
- `docs/delivery-evidence/adapt-seed/report.md`: Báo cáo bằng chứng thực thi này.

## 2. Sai lệch tiền đề và quyết định
- (a) `ADAPT-WIRE` chỉ cung cấp `build_collection_services` cho Phân hệ A, không có `build_catalog_services`; Phân hệ C dùng trực tiếp `PostgresMediaAssetRepository` và `PostgresHookHistory` của `GATE-PERSIST-C` trên kết nối của `manager.borrow_connection()`, kết hợp các hàm ứng dụng `register_discovery` và `import_hook`; không sửa bất kỳ mã nguồn nào trong `src/**`.
- (b) `RightsStatus` của C chỉ có các giá trị `known`, `unknown`, `disputed`; `register_discovery` luôn thiết lập trạng thái là `unknown`, do đó giá trị `'UNVERIFIED'` trong `hooks.json` được bảo toàn thông qua hằng số `ARTICLE_IMAGE_RIGHTS_STATUS` kiểm tra nghiêm ngặt lúc nhập (từ chối nếu sai khác) và tài sản seed mang quyền `unknown`, nhãn `SELF_GENERATED` được lưu trong `technical_metadata` của hook; đây là mục mở để Control xác nhận ánh xạ này.
- (c) `hooks.json` thuộc sở hữu của `ADAPT-CONFIG` nên không ghi đè SHA-256 vào tệp đó; các mã SHA-256 được in ra màn hình console và ghi vào `seed-manifest.json` trong thư mục dữ liệu nằm ngoài cây Git.
- (d) Thêm các cờ `-threads 1`, `-fflags +bitexact`, `-flags:v +bitexact`, `-map_metadata -1` sau `output_args`, cùng với tham số `seed=1` cho bộ lọc lavfi `gradients`, để giá trị băm SHA-256 của các video MP4 hoàn toàn ổn định và đồng nhất giữa hai lần chạy.
- (e) Chủ đề (`topics`) của các nguồn RSS mặc định là `('news',)` theo quy tắc D8 do `sources.json` không khai báo trường `topics`.
- (f) `resolver` mặc định là `system_dns_resolver` chỉ thực hiện phân giải DNS phục vụ kiểm tra chống SSRF của `validate_locator`, không thực hiện tải RSS qua mạng; bộ kiểm thử sử dụng `Resolver` giả lập và chặn `RealHttpTransport.send`.

## 3. Bằng chứng RED hợp lệ (Bước 9)
Khi chạy kiểm thử lần đầu tại Bước 9 trên khung rỗng (chưa cài đặt), test suite đã ghi nhận oracle RED hợp lệ với 13 kiểm thử thất bại do assertion và không ném ngoại lệ mong muốn trên khung:
```text
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_seed_media_sha256_is_stable_between_runs
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_seed_media_prints_sha256_per_file
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_seed_media_formats
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_make_seed_media_is_stdlib_only_without_network
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_seed_dir_is_outside_git_tree
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_ffmpeg_pin_mismatch_is_rejected_before_any_output
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_import_seed_twice_does_not_duplicate_rows
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_sources_registered_with_tier_and_https
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_assets_and_hooks_keep_rights_and_provenance
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_http_source_is_rejected_before_any_write
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_missing_media_is_rejected_before_any_write
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_non_production_profile_is_rejected
FAILED tests/integration/adapt/seed/test_adapt_seed_import.py::test_import_seed_uses_application_services_only
13 failed in 2.32s
```
Exit code: 1.

## 4. Bằng chứng GREEN và kết quả các lệnh kiểm tra
- **Bước 20 (`test_adapt_seed_import.py`):**
  - Lệnh: `python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider`
  - Exit code: 0
  - Dòng tóm tắt nguyên văn: `13 passed in 36.08s`
  - Kết quả: Toàn bộ 13 test cases đều đạt (PASS), bao gồm xác thực tính ổn định của SHA-256 media seed giữa hai lần chạy độc lập, kiểm tra nhập lặp lại trên cơ sở dữ liệu PostgreSQL dùng một lần không làm thay đổi số lượng bản ghi (7 nguồn, 7 định danh nguồn, 10 hook, 10 phiên bản hook, 22 tài sản media, 22 bản ghi provenance), từ chối nguồn HTTP, từ chối thiếu media, từ chối profile sai.
- **Bước 21 (kiểm tra tĩnh probe bắt buộc):**
  - Lệnh: `python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_seed.py').read_text(encoding='utf-8'); assert 'register_discovery' in t and 'import_hook' in t and 'urllib' not in t, 'seed'"`
  - Exit code: 0
  - Kết quả: PASS, không có lỗi AssertionError, xác nhận `import_seed.py` chứa `register_discovery`, `import_hook` và không chứa chuỗi `urllib`.
- **Bước 23 (kiểm tra định dạng diff `git diff --check`):**
  - Lệnh: `git diff --check`
  - Exit code: 0
  - Kết quả: PASS, không có lỗi khoảng trắng thừa hay kết thúc dòng.

## 5. Mục mở còn lại
- **OI-ADAPT-10**: Quyền sử dụng ảnh từ bài viết (`rights_status` của ảnh trích xuất từ RSS bài viết được giữ ở mức `UNVERIFIED`, nằm trong danh sách chờ kiểm duyệt `pendingUserCheckpoint`).
- **CP7-ADAPT-07**: Kiểm tra kết nối sống và xác thực thực tế với 7 nguồn RSS công khai (được thực hiện trong checkpoint CP7 theo quyết định ủy quyền của user).
