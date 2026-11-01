# PW-W2-FIX8: render theo phán quyết AssessImageSafety của E, ảnh cảnh và thumbnail lấy đúng ảnh NormalizeMedia của E dùng (DQ-11, OI-PW-RENDER-SAFETY)

## Nhóm lỗi

Render bỏ qua phán quyết AssessImageSafety của E: E chỉ thay ảnh ở đầu vào NormalizeMedia (`src/voice/adapters/activity_inputs.py:312-330`), trong khi render lấy ảnh theo `artifact_version_ref` của plan (`src/render/adapters/postgres_plan_assets.py:100-108`, `src/controlplane/api/wiring/render.py:446-461`) và thumbnail theo timeline (`render.py:374-385`), trái với yêu cầu DQ-11 (`docs/implementation/prod-wiring/plan.md:29`). Cả 6 trường hợp phán quyết (SAFE, TRANSFORM, loại theo danh mục, UNCERTAIN, hết seed, che chưa SAFE) mã cũ đều đưa ảnh gốc vào cảnh 1, thumbnail và `input_artifacts`.

- Mã nhóm lỗi: `OI-PW-RENDER-SAFETY`.
- Căn cứ hợp đồng và kế hoạch: DQ-11, OI-ADAPT-10, CT-RND-002 (`docs/09-contracts/08-render-quality-contracts.md:40,53`), CT-PROC-005.
- Render nhận media đã resolve và fallback kỹ thuật; asset ngoài plan và `allowed_fallbacks` bị từ chối; không dùng rendition của NormalizeMedia vì scale `{w}:{h}` làm méo ảnh.
- Nhóm lỗi `OI-PW-RENDER-SAFETY` (DQ-11 ở render) đã được khắc phục và đóng; `MediaUsage` của completion vẫn ghi ảnh theo selection (`completion_assembler.py:99-115`), để lại backlog.

## Tệp đã sửa

- `src/controlplane/api/wiring/workflow.py`
- `src/controlplane/api/wiring/render.py`
- `tests/integration/prod_wiring/test_pw_w2_fix8_render_image_safety.py` (tạo mới)
- `tests/integration/prod_wiring/test_pw_e2e_batch_video.py`
- `tests/integration/prod_wiring/pw_e2e_support.py`
- `docs/delivery-evidence/pw-w2-fix8/report.md` (tạo mới)

## Thay đổi

- `src/controlplane/api/wiring/workflow.py`:
  - Khai báo dataclass frozen `RenderImage(media_asset_id, artifact_version_id, reason)` và hằng `RENDER_IMAGE_TOOL_VERSION`, `REF_TYPE_SELECTED_MEDIA`.
  - Hàm `render_image_sources(manager, *, workspace_id, profile, staging_root, clock)` trả hàm `decide(refs) -> dict[str, RenderImage]`: với mỗi ref `selected_media`, sắp xếp item đó đứng đầu danh sách refs như fan-out NormalizeMedia (`flow.py:205-217`), gọi đúng `ProductionActivityInputs.normalize_source` của E với `outputs = PostgresVoiceUnitOfWork(...).outputs`, `media = ArtifactRows`, `selections = SelectionSeedFallback` (import lười trong thân hàm để tránh vòng lặp phụ thuộc với `voice.py`).
  - Khi ref trả về là `processed:<hex>` (ảnh bản che), hàm `blurred_version` tìm tệp qua `locate_media_file`, kiểm tra SHA-256 khớp với `artifact.content_sha256` của E, rồi đăng ký durable artifact qua `register_staged_artifact` với `owner_ref = media_asset_id` (trả về version id).
  - Lỗi `VoiceInputError` được chuyển đổi sang `RenderInputError` giữ nguyên mã lỗi.
  - Cập nhật `__all__` xuất `RenderImage` và `render_image_sources`.
- `src/controlplane/api/wiring/render.py`:
  - Import `RenderImage`, `render_handler`, `render_image_sources` từ `workflow.py`; tuyệt đối không import subsystem `voice`.
  - Thêm helper `_visual_version_refs`, `_image_safe_timeline`, `_image_fallback_rule`.
  - `ProductionRenderSources`: khởi tạo `self._image_sources = None` trong `__init__` (không đọc DB khi lắp handler). Phương thức `_image_decisions` chỉ khởi tạo và gọi `render_image_sources` lười khi `input_refs` thực sự chứa `selected_media`.
  - `ProductionRenderSources.resolve_inputs`: khi có `selected_media`, cập nhật timeline với version an toàn từ `_image_safe_timeline`; nếu thiếu phán quyết ném `INPUT_NOT_READY image_not_assessed:<media>`; nếu loại mà không còn seed ném `INPUT_NOT_READY image_excluded:<reason>:<media>`. Thêm quy tắc vào `allowed_fallbacks` với `rule_id` `image-safety:<media>`, `kind` `replace_asset`, `replaced_artifact_version_ref`, `artifact_version_id`, `reason`.
  - Cập nhật `input_artifacts`: loại bỏ ảnh gốc bị thay khỏi `input_artifacts` (trừ khi visual khác còn dùng), bổ sung ảnh thay thế đã đăng ký; nếu ảnh thay thế chưa VERIFIED ném `INPUT_NOT_READY image_version_not_verified:<media>`. Manifest và thumbnail `thumb:<media>` tự động đồng bộ theo timeline đã thay thế.
  - Khi không có `selected_media`, toàn bộ hành vi cũ được giữ nguyên 100%. Không sửa `src/voice/**`, `src/render/**`, `voice.py`, `launcher.py`.
- `tests/integration/prod_wiring/pw_e2e_support.py`:
  - `FakeVisionRoute` bổ sung tham số `excluded_sha256: frozenset[str] = frozenset()`. Mặc định trả `confidence: 0.9` (SAFE) để các ca e2e cũ giữ nguyên khẳng định; chỉ trả `confidence: 0.0` (UNCERTAIN) khi SHA-256 của ảnh nằm trong tập `excluded_sha256`.
- `tests/integration/prod_wiring/test_pw_w2_fix8_render_image_safety.py`:
  - Bộ kiểm thử tích hợp đầy đủ trên PostgreSQL thật và FFmpeg ghim kiểm chứng cả 6 trường hợp phán quyết của E, bảo đảm ảnh render theo đúng lựa chọn của `normalize_source`, ảnh gốc bị loại không xuất hiện trong `input_artifacts`, `materialization_manifest`, timeline hay command argv.
- `tests/integration/prod_wiring/test_pw_e2e_batch_video.py`:
  - Thêm ca kiểm thử e2e `test_an_article_image_e_excludes_is_rendered_as_the_seed_of_its_rank` kiểm chứng chu trình đầu cuối khi vision loại ảnh bài viết, render tự động thay bằng seed tương ứng của E, ảnh bài viết bị loại khỏi toàn bộ gói render, và khung hình 15s khớp với màu seed.

## Chi tiết từng phán quyết trong test_pw_w2_fix8_render_image_safety.py

1. **SAFE (ảnh an toàn)**:
   - Version ảnh cảnh 1: ảnh gốc `world.v1.id`.
   - Thumbnail: `world.v1.id`.
   - Ảnh gốc có trong `input_artifacts`: CÓ (`world.v1.id in ids`).
   - Mục `image-safety`: không có rule nào bắt đầu bằng `image-safety:`.
2. **TRANSFORM (vũ khí được che mờ và an toàn sau che)**:
   - Version ảnh cảnh 1: bản che đã đăng ký durable `media/processed_<hex>.png` (khác `world.v1.id`).
   - Thumbnail: bản che đã đăng ký.
   - Ảnh gốc có trong `input_artifacts`: KHÔNG (`world.v1.id not in ids`, không có trong manifest hay argv).
   - Bản ghi durable: `owner_ref = 'm-1'`, `retention_ref = 'durable'`, SHA-256 tệp trên đĩa khớp `source.artifact.content_sha256`.
   - Mục `image-safety`: `rule_id = 'image-safety:m-1'`, `kind = 'replace_asset'`, `reason = 'blurred'`, `replaced_artifact_version_ref = world.v1.id`.
3. **NUDITY_SEXUAL (loại theo danh mục cấm)**:
   - Version ảnh cảnh 1: seed hạng 0 `world.seed_ids[0]`.
   - Thumbnail: `world.seed_ids[0]`.
   - Ảnh gốc có trong `input_artifacts`: KHÔNG.
   - Bản che đăng ký: 0 (không đăng ký bản che thừa).
   - Mục `image-safety`: `rule_id = 'image-safety:m-1'`, `kind = 'replace_asset'`, `reason = 'seed_fallback'`, `replaced_artifact_version_ref = world.v1.id`.
4. **UNCERTAIN (độ tin cậy thấp / không chắc chắn)**:
   - Version ảnh cảnh 1: seed hạng 0 `world.seed_ids[0]`.
   - Thumbnail: `world.seed_ids[0]`.
   - Ảnh gốc có trong `input_artifacts`: KHÔNG.
   - Bản che đăng ký: 0.
   - Mục `image-safety`: `rule_id = 'image-safety:m-1'`, `kind = 'replace_asset'`, `reason = 'seed_fallback'`, `replaced_artifact_version_ref = world.v1.id`.
5. **BLUR_NOT_SAFE (che xong vẫn bị phát hiện nhạy cảm)**:
   - Version ảnh cảnh 1: seed hạng 0 `world.seed_ids[0]`.
   - Thumbnail: `world.seed_ids[0]`.
   - Ảnh gốc có trong `input_artifacts`: KHÔNG.
   - Bản che đăng ký: 0.
   - Mục `image-safety`: `rule_id = 'image-safety:m-1'`, `kind = 'replace_asset'`, `reason = 'seed_fallback'`, `replaced_artifact_version_ref = world.v1.id`.
6. **HẾT SEED**:
   - Khi E loại ảnh và không có seed thay thế (`seed_mode='none'`), render dừng fail-closed với `ActivityInputError('INPUT_NOT_READY', 'image_excluded:uncertain:m-1')`.
7. **CHƯA ĐƯỢC ĐÁNH GIÁ (thiếu quyết định E)**:
   - Ném lỗi `ActivityInputError('INPUT_NOT_READY', 'image_not_assessed:m-1')`.
8. **SEED CHƯA VERIFIED**:
   - Ném lỗi `ActivityInputError('INPUT_NOT_READY', 'image_version_not_verified:m-1')`.
9. **KHÔNG CÓ SELECTED_MEDIA**:
   - Giữ nguyên ảnh và cấu trúc gói như thiết kế gốc, `validate_render_package` đạt.

## Chi tiết trong ca e2e mới (test_an_article_image_e_excludes_is_rendered_as_the_seed_of_its_rank)

- `media_asset_id` ảnh bài viết cảnh 1: `scene1_id` (`rig.router.selected_media[0]`).
- SHA-256 ảnh bài viết: khớp với mã băm trong `feed_sha`.
- `artifact_version_ref` gốc của bài viết: `original1` (có trong `article_versions`).
- `artifact_version_ref` thay thế: `scene1` (seed đỏ đã đăng ký của catalog).
- Khớp nối NormalizeMedia của E: `scene1 == expected.pop()` và `scene1 not in article_versions`.
- Ảnh bài viết vắng mặt hoàn toàn: không có trong `input_artifacts`, `materialization_manifest`, timeline hay lệnh ffmpeg argv của `render_attempts`.
- Allowed fallback: `image-safety:{scene1_id}` với `kind = 'replace_asset'`, `reason = 'seed_fallback'`, `artifact_version_id = scene1`, `replaced_artifact_version_ref = original1`.
- Bằng chứng đo màu khung hình 15s:
  - Khung hình trích xuất tại giây thứ 15: RGB `(0, 0, 255)`.
  - Màu seed đỏ catalog: RGB `(1, 0, 255)`.
  - Màu hai ảnh bài viết feed: `[(1, 129, 2), (255, 0, 255)]`.
  - Khoảng cách màu Euclidean tới seed: `1.0` (ngưỡng cho phép `<= 60`).
  - Khoảng cách màu Euclidean tối thiểu tới ảnh bài viết: `255.0` (ngưỡng cho phép `>= 150`).

## Lệnh kiểm đã chạy

| STT | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 12 (RED) | `python -m pytest tests/integration/prod_wiring/test_pw_w2_fix8_render_image_safety.py tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` | 1 | 7 failed, 141 passed in 21.11s (AssertionError do ảnh gốc vào timeline, DID NOT RAISE khi thiếu seed/đánh giá) |
| 13 (RED) | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 1 | 1 failed, 10 passed in 158.87s (0:02:38) (`test_an_article_image_e_excludes_is_rendered_as_the_seed_of_its_rank` hỏng do render vẫn dùng ảnh bài viết) |
| 23 (GREEN) | `python -m pytest tests/integration/prod_wiring/test_pw_w2_fix8_render_image_safety.py tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` | 0 | 148 passed in 17.68s |
| 24 | `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider` | 0 | 87 passed in 70.39s (0:01:10) |
| 25 | `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/integration/prod_wiring/test_f10_fix3_render_length.py tests/integration/prod_wiring/test_pw_e3_media_inputs.py -q -p no:cacheprovider` | 0 | 62 passed in 33.51s |
| 26 | `python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/integration/prod_wiring/test_pw_w2_fix5_bootstrap.py tests/integration/prod_wiring/test_pw_w2_fix6_qc_probe.py tests/integration/prod_wiring/test_pw_w2_fix7_audio_mix.py -q -p no:cacheprovider` | 0 | 28 passed in 13.33s |
| 27 | `python -m pytest tests/integration/prod_wiring/test_pw_g3_grants.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/prod_wiring/test_pw_w1_launcher_core.py tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider` | 0 | 102 passed in 23.22s |
| 28 (GREEN) | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | 11 passed in 156.05s (0:02:36) |
| 29 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | 7610 passed, 2561 subtests passed in 23.23s |
| 30 | Probe render.py boundary | 0 | Đạt |
| 31 | Probe workflow.py contracts | 0 | Đạt |
| 32 | Probe test_pw_w2_fix8_render_image_safety.py fixture | 0 | Đạt |
| 33 | Probe test_pw_e2e_batch_video.py & pw_e2e_support.py vision | 0 | Đạt |
| 34 | Probe CP2A-LAYOUT package configuration | 0 | Đạt |
| 35 | Probe AudioMixGate wiring | 0 | Đạt |
| 37 | Probe report.md | 0 | Đạt |
| 38 | `git diff --check` | 0 | Sạch, không có cảnh báo khoảng trắng hay lỗi định dạng |

## Dòng tổng kết nguyên văn của pytest

- Bước 12 (RED): `7 failed, 141 passed in 21.11s`
- Bước 13 (RED): `1 failed, 10 passed in 158.87s (0:02:38)`
- Bước 23 (GREEN): `148 passed in 17.68s`
- Bước 24 (GREEN): `87 passed in 70.39s (0:01:10)`
- Bước 25 (GREEN): `62 passed in 33.51s`
- Bước 26 (GREEN): `28 passed in 13.33s`
- Bước 27 (GREEN): `102 passed in 23.22s`
- Bước 28 (GREEN): `11 passed in 156.05s (0:02:36)`
- Bước 29 (GREEN): `7610 passed, 2561 subtests passed in 23.23s`

## Bằng chứng khung giữa e2e

```text
FIX8_FRAME_EVIDENCE frame=(0, 0, 255) seed=(1, 0, 255) article=[(1, 129, 2), (255, 0, 255)] dist_seed=1.0 dist_article=255.0
```

## Giới hạn và backlog

- Render dựng `ProductionActivityInputs` của E chỉ nhằm mục đích gọi `normalize_source` (với các cổng không liên quan đặt thành `None`). Nếu hệ thống E trong tương lai thay đổi hợp đồng `normalize_source` sang các cổng khác ngoài `outputs`, `media`, `selections`, render sẽ dừng fail-closed, tuyệt đối không làm lộ ảnh vi phạm an toàn.
- Bản che được đăng ký bền vững (durable) bởi I tại thời điểm `resolve_inputs` của render khi kiểm tra SHA-256 khớp với đầu ra của E, thay vì đăng ký sớm lúc E sinh tệp tạm.
- `MediaUsage` của completion hiện tại vẫn ghi nhận ảnh dựa trên selection gốc (`completion_assembler.py:99-115`), được ghi nhận lưu lại backlog tiếp tục hoàn thiện ở các milestone kế tiếp.
