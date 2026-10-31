# PW-W2-FIX5: khởi động production tự tạo staging voice và media, seed render config từ hồ sơ (nhóm lỗi R27)

## Nhóm lỗi

Nhóm lỗi R27, RG-09 thật của CP7-10 ngày 31/10/2026:

- P1: TTS Kokoro đòi `<staging>/voice` và media tool đòi `<staging>/media`, nhưng không mã production nào tạo hai thư mục này (`voice.py` chỉ tính đường dẫn).
- P2: render đòi ConfigRevision PUBLISHED của 5 preset, preset/output-profile và policy/quality, nhưng `seed_render_config` chỉ được gọi trong test (OI-PW-F3-01).
- PW-E2E vẫn đạt vì harness tự tạo thư mục và tự seed bằng hằng số test.

## Tệp đã sửa

- `tools/launcher/prod/profile.json`
- `src/controlplane/api/wiring/production_profile.py`
- `src/controlplane/api/wiring/render.py`
- `src/controlplane/api/wiring/voice.py`
- `tools/launcher/launcher.py`
- `tests/integration/prod_wiring/test_pw_w2_fix5_bootstrap.py` (mới)
- `tests/integration/adapt/config/test_adapt_config_profile.py`
- `tests/integration/adapt/wire/test_adapt_wire_services.py`
- `tests/integration/prod_wiring/pw_e2e_support.py`
- `docs/runbook/runbook-v1.md`
- `docs/delivery-evidence/pw-w2-fix5/report.md`

## Thay đổi

- `profile.json` thêm 5 tham số (`render.ass_style`, `render.layout`, `render.sections`, `render.output_stream`, `qc.quality_thresholds`), basis `CONSERVATIVE_DEFAULT`, `meta.revision` giữ 2; `REQUIRED_PARAMETERS` từ 78 thành 83.
- `render.py` thêm `render_supplements` và `seed_production_render_config`, không có giá trị literal của render.
- `launcher.seed_defaults` gọi seed render config ngay sau `seed_production_defaults`, cùng khối try, cùng manager và profile.
- `build_voice_services` nhánh production tạo `<staging>/voice` và `<staging>/media` (mkdir parents, exist_ok).
- Harness PW-E2E thôi tự tạo voice và media, thôi seed bằng hằng số test (dùng `seed_production_render_config` với `profile.json` thật).
- Runbook thêm 5 dòng cuối bảng phụ lục.

## Lệnh kiểm đã chạy

| STT | Lệnh | Mã thoát | Dòng tổng kết |
| --- | --- | --- | --- |
| 3 (RED, mã cũ) | `pytest test_pw_w2_fix5_bootstrap.py` | 1 | `2 failed, 2 passed in 2.99s` (đỏ: test (a) `test_production_voice_build_creates_voice_and_media_dirs_and_keeps_files` và test (b) `test_seed_defaults_seeds_render_config_from_the_profile_once` với RenderConfigNotSeeded; xanh: test (c) hai ca) |
| 9 | `pytest` config profile + wire services | 0 | `129 passed in 9.94s` |
| 15 | nhóm PW (fix5, w2 launcher def, w1, g1, f3, e2) | 0 | `108 passed in 43.60s` |
| 16 | nhóm ADAPT (launch, wire, config, prod) | 0 | `194 passed in 28.02s` |
| 17 | nhóm đọc hồ sơ production thật | 0 | `254 passed in 81.75s (0:01:21)` |
| 18 | `pytest test_pw_e2e_batch_video.py` | 0 | `10 passed in 120.56s (0:02:00)` |
| 19 | probe `profile.json` | 0 | không assert lỗi |
| 20 | probe `launcher.py` | 0 | không assert lỗi |
| 21 | probe runbook | 0 | không assert lỗi |
| 24 | `git diff --check` | 0 | không có lỗi khoảng trắng |

Bước 23 (probe report) chạy sau khi ghi tệp này; kết quả gửi trong `worker_done`.

## Dòng tổng kết nguyên văn của pytest

- RED: `2 failed, 2 passed in 2.99s`
- Config + wire: `129 passed in 9.94s`
- PW: `108 passed in 43.60s`
- ADAPT: `194 passed in 28.02s`
- Đọc hồ sơ production: `254 passed in 81.75s (0:01:21)`
- PW-E2E: `10 passed in 120.56s (0:02:00)`

## Mục mở

- Seed dùng `expected_revision` 0 nên đổi hồ sơ về sau không cập nhật config đã seed (đổi qua Control API).
- `render.sections` là giá trị tạm `UNSPECIFIED_V1` chờ user duyệt preset ở R4.
- Nhập media seed khi khởi động (driver CP7-10 đang tự làm) chưa thuộc gói này.

## Giới hạn

- Không chạm tệp ngoài owned paths.
- Không monkeypatch production; test mới chỉ giả biên DNS.
