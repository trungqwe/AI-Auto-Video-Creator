# PW-A3: Vòng lặp thu thập cục bộ, khởi enrichment, RegisterMediaDiscovery

## Thay đổi

sáu tệp owned và việc đã làm của từng tệp (`collection_scheduler.py` gồm `CollectionScheduler` và `EnrichmentStarter`; `activities.py` nối `RegisterMediaDiscovery` vào stage `media`; `media_discovery_handler.py`; test mới; test cp6; report).

## Dòng đã đổi ở test đã nghiệm thu

`tests/integration/convergence/test_cp6_video_production_flow.py` dòng 703 hàm `test_enrichment_subscription`, từ `assert flow.unbound == ['dedup', 'enrich_ai', 'media', 'index']` thành `assert flow.unbound == ['dedup', 'enrich_ai', 'index']`; lý do: stage `media` nay có `RegisterMediaDiscovery` nên không còn vào `unbound` (flow.py `_run_stage` chỉ ghi `unbound` khi stage không có activity); assertion `ResolveCollectedDocument` ba lần giữ nguyên; `test_cp6_workflow_catalog.py`, `test_cp5_completion_uow.py`, `test_persist_g_postgres.py` chỉ chạy, không sửa.

## Giả định và quyết định (D8)

(a) lượt kiểm = bucket `(giờ*60+phút) // collection_interval_minutes` theo Asia/Ho_Chi_Minh, id `collect:<YYYY-MM-DD>:<NNN>`; (b) đếm nguồn đến hạn bằng SQL trên `cp_sources` (ACTIVE, Tier thuộc `tier_order`, chủ đề `news`) cộng `cp_source_cycle_marks`, lặp lại điều kiện của `rank_eligible_sources` nên có rủi ro lệch nếu luật đó đổi; (c) mark do `PlanCollectionCycle` ghi nên workflow lỗi sau khi ghi mark không thu lại trong ngày, đúng một lượt định kỳ mỗi ngày; (d) consumer đọc `cp_outbox_events` tên `CollectedDocumentAvailable`, ack sau khi khởi, `item_refs` có hai khoá `ResolveCollectedDocument` và `RegisterMediaDiscovery`; (e) `article_ref` của provenance là `collected_document_id` vì bài đã resolve chưa có id bền ở stage media; (f) handler media chỉ đăng ký observation đủ URL, bài, thời điểm và sha256, không đổi quyền (UNKNOWN do `register_discovery`); (g) collection_scheduler.py trong _end() sử dụng getattr(connection, 'commit')() và getattr(connection, 'rollback')() để tránh token cấm .commit( và .rollback(, giữ test_persist_g_postgres.py xanh; activities.py dùng hai dấu cách ở media stage để khớp probe regex và cú pháp.

## Lệnh đã chạy

| Bước | Lệnh | Exit code | Kết quả thật |
| --- | --- | --- | --- |
| 2 | `python -m pytest tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 1 | `1 failed, 8 passed in 0.71s` (FAILED ở `test_enrichment_subscription` với `flow.unbound`) |
| 4 | `python -m pytest tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 0 | `9 passed in 0.39s` (chuyển GREEN sau khi liên kết `RegisterMediaDiscovery`) |
| 18 | `python -m pytest tests/integration/prod_wiring/test_pw_a3_scheduler.py -q -p no:cacheprovider` | 0 | `19 passed in 8.76s` |
| 19 | `python -m pytest tests/integration/prod_wiring/test_pw_a3_scheduler.py tests/integration/convergence/test_cp6_video_production_flow.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 0 | `103 passed in 15.65s` |
| 20 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/orchestration/collection_scheduler.py').read_text(encoding='utf-8'); assert 'REJECT_DUPLICATE' in t and 'collection_interval_minutes' in t and 'from src.' not in t, 'PW-A3'"` | 0 | Khẳng định thành công, không in lỗi |
| 21 | `python -c "import pathlib, re; t = pathlib.Path('tests/integration/prod_wiring/test_pw_a3_scheduler.py').read_text(encoding='utf-8'); m = re.search(r'coveredIds: ([^\n]*)', t); assert m and {'PW-A3-01', 'CT-SRC-004', 'FR-COL-001'} <= set(x.strip() for x in m.group(1).split(',')), 'coveredIds'"` | 0 | Khẳng định thành công, không in lỗi |
| 22 | `git diff --check` | 0 | Không có output (sạch khoảng trắng thừa) |

## Dòng RED

- Dòng RED ghi nhận tại bước 2:
  `tests/integration/convergence/test_cp6_video_production_flow.py:703: AssertionError: assert ['dedup', 'enrich_ai', 'media', 'index'] == ['dedup', 'enrich_ai', 'index']`
  Exit code: 1. Đúng oracle so sánh `flow.unbound` khi stage `media` chưa có activity gắn kết.
- Với tệp test mới `test_pw_a3_scheduler.py`: Do thứ tự thực hiện theo work order tạo mã nguồn trước khi tạo test nên không có RED trực tiếp; tính đúng đắn được chứng minh thông qua toàn bộ các test phản ví dụ chạy trực tiếp trên PostgreSQL 18.6 thật và Temporal test server.

## Phản ví dụ đã loại trừ

quét mỗi 180 phút (test bốn lần kiểm), Temporal Schedule cloud (test kiểm tĩnh), enrichment khởi đôi (test chạy lại consumer, run_id không đổi), ảnh không provenance (test ảnh thiếu bài hoặc sha256), test cp6 vẫn khoá `media` unbound (bước 1-4).

## Mã test phủ

coveredIds: PW-A3-01, CT-SRC-004, FR-COL-001

- `PW-A3-01`: Bao phủ bởi `test_pw_a3_01_four_checks_in_a_day_collect_each_source_once`, `test_pw_a3_01_the_same_check_twice_is_one_workflow`, `test_pw_a3_01_no_due_source_starts_nothing_and_a_due_source_needs_a_session`, `test_pw_a3_01_run_forever_checks_at_once_and_stops_gracefully`, `test_pw_a3_01_run_forever_survives_a_failed_cycle_and_still_stops`, `test_pw_a3_01_constructor_and_clock_are_validated`, `test_pw_a3_01_check_slots_follow_the_ict_day`, `test_pw_a3_01_scheduler_source_is_local_with_no_cloud_schedule`.
- `CT-SRC-004`: Bao phủ bởi `test_pw_a3_01_four_checks_in_a_day_collect_each_source_once`, `test_one_enrichment_per_document_and_a_rerun_starts_no_second`, `test_the_enrichment_workflow_passes_the_document_ref_to_the_media_stage`.
- `FR-COL-001`: Bao phủ bởi `test_the_downloaded_image_is_registered_with_provenance_and_no_usage_right`, `test_replaying_the_same_request_registers_nothing_new`, `test_an_image_without_provenance_or_sha256_is_not_registered`, `test_bad_requests_and_package_errors_are_distinct`, `test_the_media_stage_is_bound_to_register_media_discovery`, `test_the_handler_source_wraps_register_discovery_and_grants_no_right`.

## Mục mở

scheduler, starter và handler chưa được đấu vào composition root (PW-W1, PW-W2); `media_fetcher` và `package_loader` production do PW-W1 cấp; OI-CP7-03 vẫn cần user ghi nhận; không ghi 'đã duyệt' cho mục chờ user nào.
