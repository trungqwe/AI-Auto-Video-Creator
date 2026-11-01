# Báo cáo PW-D3-FIX2

Gói: PW-D3-FIX2 (CP7). Nhóm lỗi: `OI-PW-D3-ARTICLE-JOIN`.

## 1. Tóm tắt lỗi

- `article_ref` của ảnh bài lưu trong provenance là `collected_document_id` (UUID v5), còn `PostgresMediaCandidates` chỉ nhận `article_ref` thuộc tập `article_id` của snapshot (UUID v4). Hai tập không giao nên 44/44 lượt SelectCreativeAssets chỉ chọn `seed-bg-01..N`.
- Lỗi ngủ DQ-11: `fallback_candidates` gồm mọi ứng viên chưa dùng, nên ảnh chưa qua AssessImageSafety (`needs_image_safety` True) có thể thay ảnh bị loại.
- Cách sửa ở đầu đọc: không backfill, không ghi DB.

## 2. Thay đổi theo tệp

- `src/creative/adapters/media_candidates.py`: `resolve_documents(article_id, revision_id)` là keyword bắt buộc (không callable: TypeError; kết quả không phải tuple/list chuỗi: TypeError), chạy trước `open_assets`. Khoá nhận gồm `article_id` và các `collected_document_id` của revision đã ghim, ánh xạ về `article_id`. `assets.search` theo từng khoá; topics là `article_id`. Giữ nguyên provenance đã lưu, `MAX_ARTICLE_IMAGES = 24`, `SCAN_LIMIT`, thứ tự ảnh bài trước seed, `seed_media_missing`.
- `tools/launcher/launcher.py` `build_media_candidates`: resolver đọc qua `PostgresIngestionUnitOfWork`, trả `collected_document_id` của revision có `article_revision_id` khớp, không có thì `()`; lỗi DB không bị nuốt.
- `src/creative/domain/asset_selection.py`: `fallback_candidates` bỏ media chưa dùng có `needs_image_safety` True; ảnh cờ True vẫn chọn được cho cảnh.
- Test: `test_pw_d3_fix2_article_join.py` (mới), `test_d09_asset_selection.py` (3 ca mới), `test_pw_d3_candidates.py` (ca constructor, ca boundary), `test_pw_e2e_batch_video.py` (kiểm ảnh cảnh 1 lô đầu), `pw_e2e_support.py` (lộ `E2ERig.runtime`).
- Ghi chú dựng bài trong test mới: `build_package` cần `extraction_policy=DEFAULT_EXTRACTION_POLICY` và `source_kind='rss_feed'` (production_deps), nếu không bài bị `REJECTED_INCOMPLETE`.

## 3. Lệnh đã chạy

| Bước | Lệnh | Exit | Dòng tổng kết pytest |
| --- | --- | --- | --- |
| 15 (RED) | pytest article_join + d3_candidates + d01_package_layout | 1 | `8 failed, 35 passed, 70 subtests passed in 20.45s` |
| 16 (RED) | pytest d09, d10, d11, d14, d16 | 1 | `1 failed, 338 passed in 1.05s` |
| 22 (GREEN) | như bước 15 | 0 | `43 passed, 70 subtests passed in 16.88s` |
| 23 (GREEN) | như bước 16 | 0 | `339 passed in 0.60s` |
| 24 | pytest PW-W1-FIX1, PW-W1, PW-A3, PW-D2, launcher def | 0 | `65 passed in 99.49s (0:01:39)` |
| 25 | pytest test_pw_e2e_batch_video.py | 0 | `10 passed in 129.26s (0:02:09)` |
| 26 | pytest tests/unit | 0 | `7610 passed, 2561 subtests passed in 24.54s` |
| 28 | `git diff --check` | 0 | không cảnh báo |
| probe 7-11 | các lệnh `python -c` của task | 0 | đạt |

Ca hỏng trước sửa (bước 15, 8 ca, đúng oracle): ảnh bài vào trước seed (`{'seed-bg-01','seed-bg-02'}` thay vì ảnh bài); cùng byte ở A và B; 30 ảnh còn 24 (0 ảnh bài); cảnh 1 với fallback chỉ seed; resolve_documents TypeError (tham số lạ); `test_media_port_requires_a_callable_resolve_version`; `test_media_port_requires_a_callable_resolve_documents`; `test_adapters_keep_the_boundary_to_c_and_name_their_ports`. Bước 16: `test_fallback_candidates_exclude_unused_images_that_still_need_image_safety` hỏng. Sau sửa: 43 và 339 ca đạt.

Trong `test_pw_d3_fix2_article_join.py` (kiểm bằng assert): ứng viên có 2 ảnh bài rồi 12 seed (ca 30 ảnh: 24 ảnh bài rồi 12 seed, tổng 36); `article_ref` = `collected_document_id` (UUID v5) khác `article_id` (UUID v4); ảnh bài B không vào; ảnh cùng byte mang provenance của bài trong snapshot; revision lạ và article_id không tồn tại chỉ ra 12 seed; `fallback_candidates` khi ảnh bài ở cảnh 1 đúng bằng 12 seed.

PW-E2E lô đầu (dòng `PW_D3_FIX2_EVIDENCE` ở lần chạy cuối): `media_asset_id` ảnh cảnh 1 = `ma-56c1262f-594d-5645-9acd-ecaf58706f58`, sha256 = `3fb42dd6020f81bc4f09e93394b909f75fa43160e1fab800b8b109aaab5393d0`, là ảnh enclosure feed của bài trong snapshot, có `article_ref` = `collected_document_id` `c1d442c5-8a2e-56fb-b0aa-d779dc7c6ff1`. Vision giả nhận đúng byte đó. Job có 2 bản ghi AssessImageSafety (`...:video:0:process:AssessImageSafety:0:r1` và `:1:r1`, outcome UNCERTAIN). Payload bản ghi không mang tham chiếu ảnh nên bằng chứng là cặp (vision nhận byte ảnh cảnh 1, số bản ghi >= 1). Không khẳng định ảnh được render.

## 4. Quyết định và giới hạn

- Chỉ nối revision đã ghim; ảnh của tài liệu trùng (FR-AST-009) chưa vào.
- Render vẫn dùng ảnh gốc trong timeline của plan, chưa theo kết quả AssessImageSafety (gói render riêng do Control lập).
- 92/410 ảnh bài chỉ 240x134-135 bị phóng to; 7 ảnh trên 3 MP làm render chậm.
- Không backfill, không ghi `cp_media_provenance` hay `cp_article_revisions`.

## 5. Mục mở

- `OI-PW-D3-ARTICLE-JOIN` đóng bằng gói PW-D3-FIX2 vì mọi lệnh kiểm đạt.
- Mở: render theo kết quả AssessImageSafety (gói render riêng). Không giả định phê duyệt user nào.
