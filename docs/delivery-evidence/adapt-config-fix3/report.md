# Báo cáo ADAPT-CONFIG-FIX3

Mã gói: ADAPT-CONFIG-FIX3 (milestone CP7).

## Nhóm lỗi R32

`voice.speech_rate_wpm` 150 (CONSERVATIVE_DEFAULT) nhanh hơn tốc độ đọc thật của Kokoro af_heart trên script tin production (128-158 từ/phút, gộp khoảng 136 trên 15 lượt TTS thật ngày 31/10/2026), nên D cho script dài hơn khoảng 61-70 s. Sửa theo CP7-D-04 và quyết định user (CLOSURE_NOTE CP7/RG-09), không theo corpus RG-05 (giá trị 121 không áp).

## Các tệp đã sửa

- `tools/launcher/prod/profile.json`: `voice.speech_rate_wpm` 136, basis MEASURED; `meta.revision` 3 lên 4.
- `tests/integration/prod_wiring/pw_e2e_support.py`: rig tự suy số từ đích `target = round((min + max) / 2000 * wpm / 60)` = 148; seg4 cắt từ 38 xuống 21 từ; mốc 65500 của Kokoro giả giữ nguyên.
- `docs/runbook/runbook-v1.md`, `docs/implementation/adapt/plan.md`, `docs/implementation/d/plan.md`, `docs/implementation/cp7/plan.md`.

## Lệnh kiểm đã chạy

| Bước | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 9 | `git diff --check` | 0 | Không có lỗi khoảng trắng |
| 10 | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | `10 passed in 128.71s (0:02:08)` |
| 11 | `python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider` | 0 | `176 passed in 12.21s` |
| 12 | probe profile (136, MEASURED, revision >= 3) | 0 | đạt |
| 13 | probe rig có `voice.speech_rate_wpm` | 0 | đạt |
| 14 | probe bốn tài liệu | 0 | đạt |
| 16 | probe report.md (có ADAPT-CONFIG-FIX3 và R32) | 0 | đạt |
| 17 | `git diff --cached --check` lần cuối (sau khi có report.md) | 0 | Không có lỗi khoảng trắng |

## Mục mở

- Đổi `speech_rate_wpm` đổi băm idempotency của GenerateScript (`language_policy.speech_rate` vào request hash); job đang ở giữa stage script lúc gộp sẽ gặp IdempotencyConflict khi phát lại.
- Kẹp `speed_fit` chỉ cứu lượt đầu khoảng 55-75,6 s; ngoài đó job vẫn FAILED_FINAL.
- PW-W2-FIX5 từng ghim revision cũ (thuộc Control).
