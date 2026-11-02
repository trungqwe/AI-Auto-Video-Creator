# PW-D3-FIX3

Báo cáo bằng chứng của gói PW-D3-FIX3 (milestone CP7). Mọi kết quả dưới đây lấy từ lần chạy thật trong worktree `lane-pw-d3-fix3`, bằng interpreter khoá của lane.

## Nhóm lỗi

Mã nhóm lỗi: **OI-CP7-11-Q1** — video chỉ có ảnh nền (CLOSURE_NOTE CP7/RG-13, quyết định của user ngày 2026-11-02: tuyệt đối không để toàn bộ video chỉ có ảnh nền).

Ghi rõ: OI-CP7-11-Q1 được xử lý bằng ba tầng luật "không toàn nền" bên dưới. Seed là ảnh có `provenance.origin == 'seed'`; mọi ảnh khác (article, ai_generated của đợt 42, cả ứng viên không có origin) là ảnh minh hoạ. Mã không so `origin == 'article'`.

## Luật không toàn nền

1. **Lúc chọn** (`asset_selection.select_creative_assets`): khi có ứng viên media đủ điều kiện có origin khác `seed`, cảnh nào chọn seed bị `SelectionRejected(invalid_proposal, seed_scene_while_illustration_eligible, scenes[i].ref)`. Ảnh `ai_generated` và ứng viên không có origin tính là ảnh minh hoạ. `SceneAssignment.origin` mang origin của ứng viên, `to_payload` chỉ có khoá `origin` khi khác `None`. `fallback_candidates` giữ nguyên. Prompt `ROLE_SELECTION` được bổ sung ba câu về ảnh seed và ảnh không phải seed; hash prompt cũ được thêm vào `PREVIOUS_DEFAULT_PROMPT_HASHES`.
2. **Trên timeline** (`production_plan`): visual nhận `origin` của assignment khi có; seed tối đa 15% thời lượng (`SEED_SHARE_MAX_PERCENT = 15`). Hàm công khai `seed_time_ms(segments, shows_seed)` và `seed_share_within_limit`. Khi selection có ảnh không phải seed mà seed vượt mức thì `PlanRejected(seed_share_exceeded, seed_share_above_max, timeline.segments)`. Selection toàn seed không bị giới hạn ở tầng kế hoạch.
3. **Trước render** (`wiring/render.require_illustration`, gọi trong `resolve_inputs` ngay sau vòng `image_version_not_verified`, trước voice): visual là seed khi `RenderImage.reason == 'seed_fallback'` hoặc `visual['origin'] == 'seed'`; seed vượt 15% (kể cả toàn seed) thì `ActivityInputError(no_illustration_available, seed_share_above_max:...)`.

## Mã no_illustration_available

`NO_ILLUSTRATION_AVAILABLE = 'no_illustration_available'` (render.py). Mã này đi qua render worker thành `COMMAND_REJECTED`, `retryable` là False, ghi vào stage run `FAILED_FINAL`, nên không có retry; batch đi tiếp ứng viên khác. Hằng mã của cổng đầu vào F nằm ở `src/render/adapters/activity_inputs.py` (ngoài owned paths).

## Ảnh bị loại ở E

`normalize_source` (voice) cho ảnh bị loại lấy `usable[position % len(usable)]` (ảnh gốc hoặc bản che của selected_media khác có verdict USABLE hoặc TRANSFORM, theo thứ tự `ordered`, `position` là hạng trong danh sách bị loại) với reason `image_fallback`. Không còn ảnh dùng được thì lấy seed cùng hạng (reason `seed_fallback`), không có seed thì `(None, reason)`. `_verdict`, `_assess`, `image_disposition` không đổi.

## Tệp đã sửa

- `src/creative/domain/asset_selection.py`
- `src/creative/application/prompts.py`
- `src/creative/domain/production_plan.py`
- `src/voice/adapters/activity_inputs.py`
- `src/controlplane/api/wiring/render.py`
- `tests/integration/prod_wiring/test_pw_d3_fix3_illustration.py` (mới, 15 test, offline; 14 ở lượt đầu, thêm `test_wiring_render_seed_rule_matches_creative` sau rebase)
- `tests/unit/creative/test_d09_asset_selection.py` (3 test mới)
- `tests/integration/prod_wiring/test_pw_d3_candidates.py`
- `tests/integration/prod_wiring/test_pw_e2e_batch_video.py`
- `tests/integration/prod_wiring/pw_e2e_support.py`
- `tests/integration/prod_wiring/test_pw_w2_fix8_render_image_safety.py`
- `tests/integration/prod_wiring/test_pw_e3_media_inputs.py` (ngoài bước 19, sửa thêm test `test_pw_e3_second_job_on_the_same_images_normalizes_and_blurs_again`: ảnh `media-failed` nay có đầu ra từ ảnh khác của job, assert đổi thành `source_ref_id == ['media-failed']`)
- `docs/delivery-evidence/pw-d3-fix3/report.md`

Hai điều chỉnh nhỏ so với lệnh: `seed_time_ms` và `require_illustration` chấp nhận cả `list` lẫn `tuple` cho danh sách cảnh/visual, vì kế hoạch đã dựng là bản đóng băng (tuple); nếu chỉ nhận `list` thì `seed_time_ms` trên `plan.timeline` luôn trả 0.

## Lệnh kiểm đã chạy

Interpreter khoá của lane, `PYTEST_DEBUG_TEMPROOT` đặt đúng như lệnh làm việc.

| Lệnh | Mã thoát | Dòng tổng kết pytest (nguyên văn) |
| --- | --- | --- |
| `git diff --check` | 0 | (không có output) |
| nhóm creative: test_pw_d3_fix3_illustration, test_d09, test_d10, test_d11, test_d14, test_d16, test_d01 | 0 | `400 passed, 70 subtests passed in 2.54s` |
| nhóm voice/E: test_adapt_e_media_fix4_rg13, test_e07, test_e17, test_e18, test_e01 | 0 | `226 passed, 89 subtests passed in 4.91s` |
| nhóm d1/d3/d3_fix2 (Postgres) | 0 | `57 passed in 30.62s` |
| nhóm e3/fix8 (Postgres, FFmpeg ghim) | 0 | `23 passed in 20.60s` |
| nhóm f3/f20 (Postgres) | 0 | `104 passed in 29.33s` |
| e2e `test_pw_e2e_batch_video.py` (Postgres, Temporal, FFmpeg ghim) | 0 | `11 passed, 1 warning in 206.05s (0:03:26)` |
| `tests/unit` | 0 | `7650 passed, 1 warning, 2561 subtests passed in 25.22s` |
| 25 lệnh `python -c` probe của danh sách "Lệnh kiểm" (selection/prompt, plan, rotation, gate, tests, launcher, lead-in, image safety v2, E3, policy, waiting_port, qc probe, render plan, audio mix, settings, render sources, bed cue, e2e pins, FIX4 pins, fix8 chain, layout) | 0 cả 25 | (probe không in dòng pytest) |
| probe `report.md` | 0 | (chạy sau khi ghi tệp này) |

Lần chạy nhóm e3/fix8 đầu tiên thất bại 1 test (`test_pw_e3_second_job_on_the_same_images_normalizes_and_blurs_again`, mã thoát 1, `1 failed, 22 passed`) do hành vi mới; đã sửa test như nêu ở mục Tệp đã sửa và chạy lại đạt như bảng trên.

Test e2e loại ảnh `test_an_article_image_e_excludes_is_rendered_as_the_seed_of_its_rank` (giữ tên hàm) nay chờ batch `EXHAUSTED`, stage `FAILED_FINAL` chứa `no_illustration_available`, job `FAILED_FINAL`, không có video, không có upload; các assert này đạt với giá trị dự kiến, không phải sửa theo giá trị quan sát khác.

## Sửa sau rebase (OI-CP7-11-Q1)

Grant G1 của PW-D3-FIX3 bị thu hồi vì `test_wiring_modules_do_not_cross_import_subsystems` hỏng: `render.py` import `creative.domain.asset_selection` và `creative.domain.production_plan`. Cách sửa: bỏ hai import, đặt hằng `_SEED_ORIGIN`, `_SEED_SHARE_MAX_PERCENT` và các hàm `seed_time_ms`, `seed_share_within_limit` (cùng `_union_ms`, `_int_ms`) ngay trong `render.py`, giữ khớp bản của creative; thêm test `test_wiring_render_seed_rule_matches_creative` để hai bản không lệch. Rebase lên `60cde6406d382712a89afe1a8e7a5c62306d072d` là no-op (`Current branch trungqwe/lane-pw-d3-fix3 is up to date.`).

| Lệnh | Mã thoát | Dòng tổng kết pytest (nguyên văn) |
| --- | --- | --- |
| adapt/wire `test_adapt_wire_services.py` + `test_pw_w2_launcher_def.py` | 0 | `152 passed in 21.64s` |
| nhóm creative (gồm test mới) | 0 | `401 passed, 70 subtests passed in 2.51s` |
| nhóm e3/fix8 (Postgres) | 0 | `23 passed in 19.76s` |
| nhóm f3/f20 (Postgres) | 0 | `104 passed in 25.79s` |
| e2e `test_pw_e2e_batch_video.py` (Postgres, Temporal) | 0 | `11 passed, 1 warning in 173.61s (0:02:53)` |
| probe cổng `render.py` (NO_ILLUSTRATION_AVAILABLE, thứ tự, ranh giới voice) | 0 | (probe không in dòng pytest) |
| probe `render.py` không import creative/voice, không còn `ORIGIN_SEED` | 0 | (probe không in dòng pytest) |
| `git diff --check` | 0 | (không có output) |

## Giới hạn đã biết

- `normalize_source` không biết origin: ảnh thay lấy từ ảnh đã chọn của job, đều không phải seed khi job có ảnh như vậy nhờ luật lúc chọn; job toàn seed vẫn bị render từ chối.
- Kế hoạch dựng trước gói này (visual không có origin) chỉ nhận diện seed qua `seed_fallback`.
- Renderer hiện chỉ hiện visual đầu của mỗi cảnh, còn tỉ lệ seed đo theo khoảng visual (luật lúc chọn không cho trộn).
- Trước đợt 42, bài không có ảnh nào thì job FAILED `no_illustration_available`, đúng quyết định của user; batch đi tiếp ứng viên khác.
- Hằng mã của cổng đầu vào F nằm ở `src/render/adapters/activity_inputs.py` (ngoài owned paths); `docs/09-contracts/00-common-contract.md` chỉ có mã nền, sản phẩm không có danh mục mã thất bại job.
