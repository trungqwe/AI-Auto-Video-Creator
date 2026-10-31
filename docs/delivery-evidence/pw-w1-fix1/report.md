# PW-W1-FIX1: launcher start tự sinh và nhập bộ media seed

Gói PW-W1-FIX1 xử lý nhóm lỗi R30: lỗi production P4 lộ ra ở RG-09 thật của CP7-10 ngày 31/10/2026. Bộ media seed tự tạo (ảnh nền bg-01..12, hook hình vh-01..05, hook âm thanh ah-01..05, `SELF_GENERATED`) là nguồn dự phòng bắt buộc của mọi video, nhưng không mã production nào sinh và nhập nó, nên thiếu seed thì `media_select` dừng `FAILED_FINAL INPUT_NOT_READY`. Nay `launcher start` tự sinh (khi cần) và nhập bộ seed, idempotent.

## Tệp đã sửa

- `tools/launcher/launcher.py`: trường `Deps.seed_media` (mặc định None), hàm `seed_media`, bước gọi trong `cmd_start` ngay sau `seed_defaults`, và `main` gắn bản thật.
- `tools/launcher/prod/seed/import_seed.py`: `import_seed_media`, `_stage_items`, `_import_media` (dùng chung với `import_seed`), hằng `SEED_RIGHTS_STATUS`.
- `docs/runbook/runbook-v1.md`: mục 1 (điều kiện tiên quyết 3, bước khởi động 6 mới, đánh số lại 7 đến 9) và mục 6 (hàng `Nạp media seed thất bại`).
- `tests/integration/prod_wiring/test_pw_w1_fix1_seed_media.py`: năm test ca (a) đến (d).
- `docs/delivery-evidence/pw-w1-fix1/report.md`: báo cáo này.

## Lệnh đã chạy

Interpreter khoá của lane; `PYTEST_DEBUG_TEMPROOT` đặt theo hướng dẫn.

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| Bước 6 (RED, trước khi sửa mã): `python -m pytest tests/integration/prod_wiring/test_pw_w1_fix1_seed_media.py -q -p no:cacheprovider` | 1 | `5 failed in 1.61s` (hỏng ở assertion `launcher.seed_media chưa có` và kiểm `seed_media` trong `dataclasses.fields`) |
| Bước 17: `python -m pytest tests/integration/prod_wiring/test_pw_w1_fix1_seed_media.py tests/integration/adapt/seed/test_adapt_seed_import.py tests/integration/prod_wiring/test_pw_d3_candidates.py -q -p no:cacheprovider` | 0 | `43 passed in 116.91s (0:01:56)` |
| Bước 18: `python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/prod_wiring/test_pw_w1_launcher_core.py tests/integration/prod_wiring/test_pw_w2_fix5_bootstrap.py tests/integration/prod_wiring/test_pw_g1_app_session.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/integration/prod_ports/test_pp_2_credentials.py -q -p no:cacheprovider` | 0 | `173 passed in 18.88s` |
| Bước 19: `python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py tests/integration/adapt/config/test_adapt_config_profile.py tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/integration/prod_wiring/test_pw_e3_media_inputs.py -q -p no:cacheprovider` | 0 | `94 passed, 1 warning in 43.66s` |
| Bước 20: `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | `10 passed, 1 warning in 119.41s (0:01:59)` |
| Bước 21: probe `launcher.py` (`def seed_media(`, `import_seed_media`, `generate_seed_media`, không `from src.`, không `from tools`) | 0 | không có output |
| Bước 22: probe `import_seed.py` (`def import_seed_media(`, không `urllib`) | 0 | không có output |
| Bước 23: probe `runbook-v1.md` (`media seed`, `AIAVC_FFMPEG_PATH`, `seed-manifest.json`, không có chuỗi dấu hỏi lặp) | 0 | không có output |
| Bước 24: `git diff --check` | 0 | không có output |

## Quyết định

- Bước nạp media seed nằm trong `cmd_start`, sau `seed_defaults` và trước bước chứng chỉ và spawn; không nằm trong `seed_defaults`, `_serve` hay `build_app`; không thêm lệnh launcher.
- Manifest lệch (thiếu, không đọc được, khác tập id của `hooks.json`, sha256 lệch hoặc thiếu tệp) thì sinh lại cả 22 tệp cùng sha256; manifest khớp thì không sinh lại.
- Hành vi đổi có chủ ý: start lần đầu cần FFmpeg ghim; thiếu thì dừng với `LauncherError` (bắt đầu bằng `Nạp media seed thất bại`, không in DSN) thay vì để job hỏng muộn ở `media_select`.
- Không xoá hay sửa dòng seed đã có trong CSDL và không xoá tệp trong staging; `import_seed` giữ nguyên chữ ký, kết quả và hành vi.

## Mục mở

- `hooks.json` để sha256 null.
- Rig PW-E2E tự nạp hook và ảnh (chạy nguyên trạng, không đổi).
- Driver CP7-10 phải bỏ `ensure_seed_media` sau khi gói gộp.
