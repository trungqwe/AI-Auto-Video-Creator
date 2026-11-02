# Báo cáo IMGGEN-CAT

## Nhóm lỗi

Mã gói IMGGEN-CAT, nhóm lỗi OI-CP7-11-Q2: ảnh minh hoạ AI sinh trên máy (quyết định D4) chưa vào ứng viên media của SelectCreativeAssets, và enum `ProvenanceRelation` thiếu `ai_generated` nên `_load` của `PostgresMediaAssetRepository` sẽ ném `ValueError` khi đọc asset AI.

## Tệp đã sửa

- `src/catalog/domain/identity.py`: thêm `AI_GENERATED = "ai_generated"` vào `ProvenanceRelation`.
- `src/creative/adapters/media_candidates.py`: bảy hằng mới, `_ai_model_ref`, nhánh `ai_generated` của `_provenance_of`, `_index_entry`, thứ tự ảnh bài → ảnh AI → seed.
- `src/creative/adapters/thumbnail_candidates.py`: bỏ ảnh AI khỏi ứng viên thumbnail.
- `tests/unit/catalog/test_catalog_identity.py`: thêm `ai_generated` vào tập enum và test mới của identity.
- `tests/integration/prod_wiring/test_imggen_cat_candidates.py`: tệp mới, 11 test offline.
- `docs/delivery-evidence/imggen-cat/report.md`: báo cáo này.

## Lệnh đã chạy

| Lệnh (bước) | Exit code | Dòng tổng kết |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_imggen_cat_candidates.py tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider` (bước 9, RED, trước khi sửa src) | 1 | `13 failed, 19 passed, 37 subtests passed in 0.46s` |
| Cùng lệnh (bước 16, GREEN) | 0 | `32 passed, 37 subtests passed in 0.18s` |
| `python -m pytest tests/unit/catalog tests/unit/creative/test_d01_package_layout.py tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider` (bước 17) | 0 | `332 passed, 533 subtests passed in 0.96s` |
| `python -m pytest tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider` (bước 18) | 0 | `70 passed in 0.54s` |
| `python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` (bước 19) | 0 | `40 passed, 62 subtests passed in 6.35s` |
| `python -m pytest tests/unit -q -p no:cacheprovider` (bước 20) | 0 | `7648 passed, 2561 subtests passed in 30.40s` |
| Probe bước 21 (hằng, thứ tự, biên adapter, thumbnail) | 0 | không áp dụng |
| Probe bước 22 (tên 11 test, offline) | 0 | không áp dụng |
| Probe bước 23 (join, biên ingestion/psycopg) | 0 | không áp dụng |
| Probe bước 24 (PW-D3) | 0 | không áp dụng |
| Probe bước 25 (controlplane, pythonpath, import src.) | 0 | không áp dụng |
| `git diff --check` (bước 26) | 0 | không áp dụng |

Test Postgres của chủ (`test_pw_d3_candidates`, `test_pw_d3_fix2_article_join`) không chạy trong gói này vì cần DB.

## Số ca test mới

- Hỏng trước (bước 9): 13 ca, gồm 11 test mới của prod_wiring và 2 của identity (một sửa, một mới), đều hỏng vì thiếu `ProvenanceRelation.AI_GENERATED` và các hằng mới (`AttributeError`/oracle), không có lỗi import hay collection.
- Đạt sau (bước 16): cả 13 ca đạt, tổng 32 passed.

## Ứng viên ảnh AI theo bài

- Thứ tự: ảnh bài tối đa `MAX_ARTICLE_IMAGES = 24`, rồi ảnh AI tối đa `MAX_AI_IMAGES = 8`, rồi seed. `SCAN_LIMIT = 200` và số lần `search` không đổi: một lần `'seed png'`, rồi mỗi key một lần.
- Cờ: `needs_image_safety` True, `ai_image_rights_status` `SELF_GENERATED`, `rights_cleared` True, `rights_basis` `D4`, `topics` là article id.
- Provenance: bảy khoá cũ (`source_url` là locator `aigen://...`) cộng `model_ref` dạng `model@revision` và `label` `ai_illustration`.
- Điều kiện nhận: relation `ai_generated`, `article_ref` thuộc bài của snapshot, locator khớp `AI_LOCATOR`, digest bằng fingerprint, có version đã xác minh. Asset có cả provenance bài và AI chỉ tính ảnh bài.

## Bằng chứng catalog tìm thấy ảnh AI theo article_ref

`_FTS` của `assets.py` là `string_to_array(search_text, ' ') @> %s::text[]`; `asset_search_text` của `mapping.py` gồm `article_ref` và `relation` của mọi provenance; `_UPSERT` ghi lại `search_text` mỗi lần save. Hai test đầu của tệp mới chứng minh `search(article_id)` tìm được asset AI (một test đăng ký bằng `register_discovery` thật).

## Thumbnail không nhận ảnh AI

`test_thumbnail_candidates_never_use_an_ai_still`; thumbnail loại ảnh AI tới đợt 44.

## Mục mở

OI-CP7-11-Q2: phần sinh ảnh và ghi vào catalog thuộc IMGGEN-PIPE (locator `aigen://<model>/<12 hex revision>/<sha256 của byte>` là hợp đồng với IMGGEN-PIPE); ảnh AI gắn theo bài, không theo bản duyệt; `MAX_AI_IMAGES = 8` gấp đôi trần 4 ảnh mỗi video của thiết kế; căn cứ quyết định D4 và `docs/plans/CREATIVE_QUALITY_PLAN_20261102.md`. Không thêm thư viện, không migration.
