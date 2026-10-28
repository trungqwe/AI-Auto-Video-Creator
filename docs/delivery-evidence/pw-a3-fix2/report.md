# PW-A3-FIX2: ảnh tải kèm bài được đăng ký artifact version VERIFIED

- Mã gói: `PW-A3-FIX2`
- Nhóm lỗi: `R3` (R3b, ảnh bài)

## 1. Mô tả lỗi

Handler `RegisterMediaDiscovery` trước đây chỉ gọi `register_discovery` của catalog (`catalog/application/media_discovery_handler.py:119-128`), nên ảnh nạp được lưu tại `staging/media/<sha>.<ext>` (`source_ingestion/adapters/real_media_fetch.py:98-110`) mà không bao giờ có artifact version trong storage metadata. Các giai đoạn tiếp theo (`ArtifactRows` trong `controlplane/api/wiring/voice.py:203-207`, render `postgres_plan_assets.py:18-26`) đòi hỏi UUID version của artifact.

## 2. Các tệp đã sửa

- `src/catalog/application/media_discovery_handler.py`: Thêm trường `register_artifact` vào `MediaDiscoveryDeps` (mặc định `None`); handler gọi đăng ký sau khi đóng transaction catalog cho mọi ảnh catalog đã nhận (có `media_asset_id` khác `None`, kể cả `DUPLICATE_OBSERVATION`); lỗi đăng ký trả về `failed` retryable.
- `src/controlplane/api/wiring/workflow.py`: Bổ sung hàm `staged_artifact_registrar` với retention `durable`, tính `relative_ref` bằng `relative_to(staging_root).as_posix()` rồi gọi `register_staged_artifact`; truyền registrar vào `MediaDiscoveryDeps` trong `assemble_activity_handlers`.
- `tests/integration/prod_wiring/test_pw_w1_launcher_core.py`: Bổ sung 3 integration test `test_pw_a3_fix2_r3_*` kiểm chứng đăng ký ảnh staged thành verified version, cơ chế retryable khi lỗi đăng ký kèm replay bù được, và loại trừ ảnh bị catalog từ chối.
- `docs/delivery-evidence/pw-a3-fix2/report.md`: Báo cáo nghiệm thu kỹ thuật của gói sửa lỗi PW-A3-FIX2.

## 3. Bằng chứng kiểm thử RED (trước khi sửa mã production)

- Lệnh chạy: `python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py -q -p no:cacheprovider`
- Mã thoát: `1`
- Dòng tổng kết pytest nguyên văn: `2 failed, 9 passed in 7.44s`
- Tên các test fail theo đúng oracle mong đợi:
  - `tests/integration/prod_wiring/test_pw_w1_launcher_core.py::test_pw_a3_fix2_r3_register_media_discovery_registers_the_staged_image_as_a_verified_version` (AssertionError: `assert None is not None` do ảnh chưa được đăng ký artifact version)
  - `tests/integration/prod_wiring/test_pw_w1_launcher_core.py::test_pw_a3_fix2_r3_a_failed_registration_is_retryable_and_a_replay_compensates` (AssertionError: `assert ('succeeded' == 'failed')` do handler chưa gọi đăng ký artifact và chưa trả lỗi retryable khi ghi thất bại)

## 4. Bằng chứng kiểm thử GREEN (sau khi sửa mã production)

- Lệnh chạy: `python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py -q -p no:cacheprovider`
- Mã thoát: `0`
- Dòng tổng kết pytest nguyên văn: `11 passed in 7.08s`
- Kết quả: Toàn bộ 11/11 test trong suite đều PASS, bao gồm 3 test mới `test_pw_a3_fix2_r3_*` và 8 test ban đầu.

## 5. Các lệnh kiểm bắt buộc khác

- Lệnh kiểm tra khoảng trắng: `git diff --check`
  - Mã thoát: `0`
  - Kết quả: Không có cảnh báo khoảng trắng thừa hay lệch định dạng dòng.
- Lệnh probe kiểm tra report: `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-a3-fix2/report.md').read_text(encoding='utf-8'); assert 'PW-A3-FIX2' in t and 'R3' in t, 'report'"`
  - Mã thoát: `0`
  - Kết quả: Khẳng định báo cáo tồn tại, đọc được bằng UTF-8 và chứa mã gói `PW-A3-FIX2` cùng mã nhóm lỗi `R3`.

## 6. Phản ví dụ đã loại trừ và kiểm chứng tương ứng

- Wiring không truyền `register_artifact`: Đã loại trừ qua `test_pw_a3_fix2_r3_register_media_discovery_registers_the_staged_image_as_a_verified_version` (sẽ fail nếu wiring thiếu registrar).
- Ảnh catalog từ chối vẫn được đăng ký: Đã loại trừ qua `test_pw_a3_fix2_r3_an_image_the_catalog_rejects_is_not_registered_as_an_artifact` (kiểm tra `cp_artifact_versions` có 0 bản ghi và `verified_version_for_sha` trả `None`).
- Đăng ký với retention tạm: Đã loại trừ qua assertion `version.retention_ref == 'durable'` trong test 1.
- Test gọi `register_staged_artifact` thay cho handler: Đã loại trừ do test dựng handler bằng đúng `assemble_activity_handlers` của `workflow_wiring` và chỉ gọi qua giao diện handler của activity `handler(MEDIA_REQUEST, MEDIA_CLAIMS)`.

## 7. Giới hạn

- Gói chỉ sửa đúng nhóm lỗi R3 (R3b, ảnh bài), không đổi hành vi khác.
- Media fetcher thật chạy trên transport giả (stub transport), không dùng mạng bên ngoài.
- Không chạy full regression suite theo quy tắc quản trị tiết kiệm tài nguyên.