# PW-W2-FIX4: phân giải ref visual hook, audio hook và thumbnail (nhóm lỗi R10)

## Nhóm lỗi

R10: `hook_placement` mang id ứng viên của phân hệ D (`visual_hook_ref` và `audio_hook_ref` là `hook_id`, `thumbnail_ref` là `"thumb:<subject>"`) nhưng `resolve_inputs` gọi `get_asset` chỉ nhận UUID và bỏ im lặng các ref không phân giải được, dẫn tới manifest thiếu hook và thumbnail, inspector trả về `visual_hook_not_observed` và `thumbnail_not_observed`.

## Tệp đã sửa

- `src/controlplane/api/wiring/render.py`
- `tests/integration/prod_wiring/test_pw_f3_render_inputs.py`
- `docs/delivery-evidence/pw-w2-fix4/report.md`

## Thay đổi

- Ba ref hook (`visual_hook_ref`, `audio_hook_ref`, `thumbnail_ref`) không đi qua vòng `get_asset` UUID nữa.
- Hook (`visual_hook_ref` và `audio_hook_ref`) được phân giải qua phiên bản mới nhất trong catalog (`PostgresHookHistory.latest(hook_id)`), lấy `media_sha256` từ `technical_metadata` và tra version qua `verified_version_for_sha(..., extensions=STAGED_HOOK_EXTENSIONS)`.
- `thumbnail_ref` dạng `"thumb:<subject>"`: nếu subject là hook id thì dùng version của hook đó; nếu subject là `media_asset_id` của một visual trong kế hoạch thì dùng `artifact_version_ref` của visual tương ứng.
- Khi ref không phân giải được (hook không có trong catalog, hook thiếu version VERIFIED, thumbnail sai tiền tố hoặc subject không tìm thấy), hệ thống ném `ActivityInputError('INPUT_NOT_READY', ...)` nêu rõ tên ref, không bỏ im lặng.
- Mỗi ref bổ sung một `ResolvedAsset(artifact_version_id=<ref>, sha256, size, mime, role)` và một `LocalMaterialRef(artifact_version_id=<ref>, local_ref=<UUID version>)` tương tự mẫu voice.
- `validation_context` dựng mục `VerifiedArtifact` trạng thái `VERIFIED` cho các ref thông qua `local_ref` từ materialization manifest khi version có location `VERIFIED`.

## Lệnh kiểm đã chạy

| STT | Lệnh kiểm | Mã thoát | Kết quả / Dòng tổng kết nguyên văn |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p no:cacheprovider` (bước 5 - RED) | 1 | `6 failed, 40 passed in 28.27s`<br>Fail: `test_hook_and_thumbnail_refs_resolve_to_verified_staged_versions` (KeyError: 'vh-1'), `test_thumbnail_of_a_plan_visual_uses_the_visual_version` (StopIteration), `test_unresolvable_hook_refs_fail_with_input_not_ready` 4 ca (DID NOT RAISE ActivityInputError) |
| 2 | `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p no:cacheprovider` (bước 10 - GREEN) | 0 | `46 passed in 27.38s` |
| 3 | `git diff --check` (bước 11) | 0 | Đạt (không có lỗi khoảng trắng) |
| 4 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix4/report.md').read_text(encoding='utf-8'); assert 'PW-W2-FIX4' in t and 'R10' in t, 'report'"` (bước 13) | 0 | Đạt (khớp mã gói PW-W2-FIX4 và nhóm lỗi R10) |
| 5 | `git diff --check` (bước 14) | 0 | Đạt (không có lỗi khoảng trắng) |

## Dòng tổng kết nguyên văn của pytest

```
46 passed in 27.38s
```

## Giới hạn

- Không đổi hành vi nhóm R9 (lệnh render) và không chạm tệp ngoài owned paths.
- Không monkeypatch, không thay hàm hay lớp production (chỉ adapter biên được phép giả).
- Không sửa production_plan hay creative để mang UUID cho hook_placement; giữ nguyên hợp đồng phân hệ D.
