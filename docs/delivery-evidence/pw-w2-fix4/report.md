# PW-W2-FIX4: phân giải ref visual hook, audio hook và thumbnail (nhóm lỗi R10)

## Nhóm lỗi

R10: `hook_placement` mang id ứng viên của phân hệ D (`visual_hook_ref` và `audio_hook_ref` là `hook_id`, `thumbnail_ref` là `"thumb:<subject>"`) nhưng `resolve_inputs` gọi `get_asset` chỉ nhận UUID và bỏ im lặng các ref không phân giải được, dẫn tới manifest thiếu hook và thumbnail, inspector trả về `visual_hook_not_observed` và `thumbnail_not_observed`.

## Tệp đã sửa

- `src/controlplane/api/wiring/render.py`
- `tests/integration/prod_wiring/test_pw_f3_render_inputs.py`
- `docs/delivery-evidence/pw-w2-fix4/report.md`

## Thay đổi

- Ba ref hook (`visual_hook_ref`, `audio_hook_ref`, `thumbnail_ref`) không đi qua vòng `get_asset` UUID nữa.
- Hook (`visual_hook_ref` và `audio_hook_ref`) được phân giải qua bản ghi mới nhất của hook trong catalog bằng truy vấn SQL chỉ đọc `_HOOK_LATEST_SQL` (cùng điều kiện với `PostgresHookHistory.latest`), lấy `media_sha256` từ `technical_metadata` rồi tra version qua `verified_version_for_sha(..., extensions=STAGED_HOOK_EXTENSIONS)`. Không import `catalog` trong module wiring của render để giữ `test_wiring_modules_do_not_cross_import_subsystems`.
- `thumbnail_ref` dạng `"thumb:<subject>"`: nếu subject là hook id thì dùng version của hook đó; nếu subject là `media_asset_id` của một visual trong kế hoạch thì dùng `artifact_version_ref` của visual tương ứng.
- Khi ref không phân giải được (hook không có trong catalog, hook thiếu version VERIFIED, thumbnail sai tiền tố hoặc subject không tìm thấy), hệ thống ném `ActivityInputError('INPUT_NOT_READY', ...)` nêu rõ tên ref, không bỏ im lặng.
- Mỗi ref bổ sung một `ResolvedAsset(artifact_version_id=<ref>, sha256, size, mime, role)` và một `LocalMaterialRef(artifact_version_id=<ref>, local_ref=<UUID version>)` tương tự mẫu voice.
- `validation_context` dựng mục `VerifiedArtifact` trạng thái `VERIFIED` cho các ref thông qua `local_ref` từ materialization manifest khi version có location `VERIFIED`.

## Rebase

Đã rebase nhánh lên `b48d807e0f16ff061671523808def7addac0019e`. Finding của lượt trước là `test_wiring_modules_do_not_cross_import_subsystems` trong `tests/integration/adapt/wire/test_adapt_wire_services.py` bị đỏ do `from catalog.persistence.hooks import PostgresHookHistory` trong `src/controlplane/api/wiring/render.py` vi phạm quy tắc phân hệ không import chéo. Đã xử lý triệt để bằng cách thay thế import `catalog` bằng truy vấn SQL chỉ đọc `_HOOK_LATEST_SQL` tương đương trực tiếp trên bảng `cp_hooks` và `cp_hook_revisions`.

## Lệnh kiểm đã chạy

| STT | Lệnh kiểm | Mã thoát | Kết quả / Dòng tổng kết nguyên văn |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/integration/adapt/prod/test_adapt_prod_app.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` (bước 4) | 0 | `191 passed, 1 warning in 34.12s` |
| 2 | `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p no:cacheprovider` (bước 5) | 0 | `46 passed in 24.69s` |
| 3 | `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p no:cacheprovider` (bước 5 - RED) (lượt trước rebase) | 1 | `6 failed, 40 passed in 28.27s`<br>Fail: `test_hook_and_thumbnail_refs_resolve_to_verified_staged_versions` (KeyError: 'vh-1'), `test_thumbnail_of_a_plan_visual_uses_the_visual_version` (StopIteration), `test_unresolvable_hook_refs_fail_with_input_not_ready` 4 ca (DID NOT RAISE ActivityInputError) |
| 4 | `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p no:cacheprovider` (bước 10 - GREEN) (lượt trước rebase) | 0 | `46 passed in 27.38s` |
| 5 | `git diff --check` (bước 11) (lượt trước rebase) | 0 | Đạt (không có lỗi khoảng trắng) |
| 6 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix4/report.md').read_text(encoding='utf-8'); assert 'PW-W2-FIX4' in t and 'R10' in t, 'report'"` (bước 13) (lượt trước rebase) | 0 | Đạt (khớp mã gói PW-W2-FIX4 và nhóm lỗi R10) |
| 7 | `git diff --check` (bước 14) (lượt trước rebase) | 0 | Đạt (không có lỗi khoảng trắng) |

## Dòng tổng kết nguyên văn của pytest

```
46 passed in 24.69s
191 passed, 1 warning in 34.12s
```

## Giới hạn

- Không đổi hành vi nhóm R9 (lệnh render) và không chạm tệp ngoài owned paths.
- Không monkeypatch, không thay hàm hay lớp production (chỉ adapter biên được phép giả).
- Không sửa production_plan hay creative để mang UUID cho hook_placement; giữ nguyên hợp đồng phân hệ D.
