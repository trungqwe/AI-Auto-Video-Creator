# Báo cáo bằng chứng A-17

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d3b0cff0a6c39bb4cce7451ff61435358b50a768`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-17 trong docs/implementation/a/slices.md, coveredIds A-RULE-014; spec docs/modules/a-source-collection/spec.md mục Query cung cấp.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `43 failed, 7 passed in 0.58s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn của bước 15:
  - `FAILED tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_detail_has_metadata_and_counters`: `AssertionError: unexpectedly None`
  - `SUBFAILED(criteria={'tier': 'T1'}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-a', 's-c']`
  - `SUBFAILED(criteria={'topic': 'ai'}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-a', 's-d']`
  - `SUBFAILED(criteria={'status': <SourceStatus.DISABLED: 'DISABLED'>}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-c']`
  - `SUBFAILED(criteria={'status': <SourceStatus.REMOVED_TOMBSTONE: 'REMOVED_TOMBSTONE'>}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-d']`
  - `SUBFAILED(criteria={'source_kind': 'html_page'}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-b']`
  - `SUBFAILED(criteria={'health': <SourceHealth.HEALTHY: 'HEALTHY'>}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-a']`
  - `SUBFAILED(criteria={'health': <SourceHealth.FAILING: 'FAILING'>}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-b']`
  - `SUBFAILED(criteria={'health': <SourceHealth.DEGRADED: 'DEGRADED'>}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-c']`
  - `SUBFAILED(criteria={'health': <SourceHealth.UNKNOWN: 'UNKNOWN'>}) tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filter_by_each_field`: `AssertionError: Lists differ: [] != ['s-d']`
  - `FAILED tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_filters_combine_with_and`: `AssertionError: Lists differ: [] != ['s-a']`
  - `FAILED tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_invalid_filter_is_rejected`: `AssertionError: TypeError not raised`
  - `FAILED tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_no_filter_lists_every_status_sorted_by_source_id`: `AssertionError: Lists differ: [] != ['s-a', 's-b', 's-c', 's-d']`
  - `FAILED tests/unit/collection/test_a17_projections.py::SourceFilterTests::test_summary_fields`: `IndexError: tuple index out of range`
  - `SUBFAILED(call=...) tests/unit/collection/test_a17_projections.py::WorkspaceIsolationTests::test_blank_identifiers_are_rejected` (4 subtests): `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a17_projections.py::WorkspaceIsolationTests::test_foreign_revision_snapshots_are_dropped`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::WorkspaceIsolationTests::test_list_is_scoped_to_the_workspace`: `AssertionError: Lists differ: [] != ['s-a']`
  - `FAILED tests/unit/collection/test_a17_projections.py::WorkspaceIsolationTests::test_other_workspace_records_are_not_found`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::WorkspaceIsolationTests::test_service_filters_rows_a_leaky_repository_returns`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::RunHistoryHealthTests::test_attempts_outcomes_and_terminal_reason`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::RunHistoryHealthTests::test_counters_and_last_collection_in_detail`: `AssertionError: unexpectedly None`
  - `SUBFAILED(case='no_runs'/'in_progress_only'/'recovered'/'failing') tests/unit/collection/test_a17_projections.py::RunHistoryHealthTests::test_health_follows_latest_terminal_run_not_insertion_order`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::RunHistoryHealthTests::test_run_history_is_ordered_by_business_date`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::RunHistoryHealthTests::test_views_are_immutable`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::RevisionHistoryTests::test_detail_shows_current_revision`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::RevisionHistoryTests::test_history_is_ordered_by_revision`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::TraceRedactionTests::test_only_packages_of_the_run_and_source_are_traced`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::TraceRedactionTests::test_packages_are_ordered_by_fetch_time`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::TraceRedactionTests::test_run_without_packages_has_empty_trace`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::TraceRedactionTests::test_safe_headers_keep_only_non_sensitive_values`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::TraceRedactionTests::test_sparse_payload_does_not_raise`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::TraceRedactionTests::test_trace_exposes_allowlisted_fields_only`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::TraceRedactionTests::test_trace_has_no_secret_or_sensitive_header`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::TraceRedactionTests::test_urls_lose_userinfo_query_and_fragment`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a17_projections.py::RedactHelperTests::test_redact_headers`: `AssertionError: Tuples differ`
  - `FAILED tests/unit/collection/test_a17_projections.py::RedactHelperTests::test_redact_locator`: `AssertionError: 'https://h.test:8080/p?q=1#f' != 'https://h.test:8080/p'`
  - `FAILED tests/unit/collection/test_a17_projections.py::NoFetchReadOnlyTests::test_every_public_query_runs_without_adapter_network_or_writes`: `AssertionError: unexpectedly None`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection nào (7 test đạt gồm kiểm tra AST không import adapter/network, chữ ký constructor không nhận transport/adapter, ReadOnly guard chặn ghi, kiểm tra nguồn không tồn tại trả None, v.v.; tất cả các lỗi FAILED/SUBFAILED đều là AssertionError do khung stub chưa cài đặt logic).

## Thay đổi

- 3 tệp:
  - `src/source_ingestion/projections/source_queries.py`: Cài đặt các projection truy vấn chỉ đọc cho Source và CollectionRun.
  - `tests/unit/collection/test_a17_projections.py`: Bộ kiểm thử đơn vị cho toàn bộ các truy vấn read-only, ranh giới phân quyền workspace, tính bất biến, và khử thông tin nhạy cảm (coveredIds: A-RULE-014).
  - `docs/delivery-evidence/a-17/report.md`: Báo cáo bằng chứng thực thi TDD đầy đủ cho gói A-17.
- API và cấu trúc dữ liệu:
  - `SourceHealth`: Enum gồm HEALTHY, DEGRADED, FAILING, UNKNOWN.
  - `SourceListFilter`: Dataclass lọc nguồn theo tier, topic, status, source_kind, health (kết hợp AND).
  - `RunCounters`: Dataclass lưu trữ bộ đếm thống kê lượt chạy và gói tin của nguồn.
  - `LastCollection`: Dataclass thông tin lượt thu thập terminal gần nhất.
  - `SourceSummary`, `SourceDetail`: Dataclass biểu diễn tóm tắt và chi tiết thông tin nguồn.
  - `RevisionView`, `AttemptView`, `RunView`: Dataclass biểu diễn lịch sử sửa đổi nguồn, attempt và run.
  - `TraceStep`, `TracePackage`, `RunTrace`: Dataclass theo dõi vết gói tin đã qua kiểm duyệt và loại bỏ dữ liệu nhạy cảm.
  - `SourceRevisionReader`: Protocol đọc lịch sử snapshot aggregate của Source.
  - `SourceQueryService`: Service truy vấn chỉ đọc cung cấp `list_sources`, `get_source`, `list_source_revisions`, `list_runs`, `get_package_trace`.
  - `redact_locator`, `redact_headers`: Các hàm làm sạch URI và header an toàn.
- Ánh xạ phản ví dụ:
  - Query kích hoạt fetch -> `NoFetchReadOnlyTests`
  - Source của workspace khác -> `WorkspaceIsolationTests`
  - Trace chứa Cookie hoặc bí mật -> `TraceRedactionTests`, `RedactHelperTests`

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider` | 0 | 33 passed, 29 subtests passed in 0.11s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace) |
| 3 | `python -c "import pathlib; t=pathlib.Path('tests/unit/collection/test_a17_projections.py').read_text(encoding='utf-8'); assert 'coveredIds: A-RULE-014' in t"` | 0 | PASS (docstring test có coveredIds A-RULE-014) |
| 4 | `python -c "import pathlib; t=pathlib.Path('docs/delivery-evidence/a-17/report.md').read_text(encoding='utf-8'); assert 'B' + chr(225) + 'o c' + chr(225) + 'o' in t and chr(65533) not in t; files=['src/source_ingestion/projections/source_queries.py','tests/unit/collection/test_a17_projections.py','docs/delivery-evidence/a-17/report.md']; bad=[f for f in files for line in open(f, 'r', encoding='utf-8', newline='').read().split(chr(10)) if line != line.rstrip()]; assert not bad, bad"` | 0 | PASS (UTF-8 có dấu đầy đủ, không ký tự lạ, không trailing whitespace) |

## Quyết định mặc định (D8)

1. Health suy ra từ run terminal mới nhất (theo business_date, run_id): COMPLETED=HEALTHY, COMPLETED_PARTIAL=DEGRADED, FAILED_FINAL=FAILING, chưa có run terminal=UNKNOWN; chưa có kho health riêng.
2. Last collection = run terminal mới nhất (CollectionRun chưa có timestamp, chỉ có business_date); không đọc checkpoint.
3. Revision history đọc qua port SourceRevisionReader do caller cấp; lưu bền chờ CONV-A-01.
4. Danh sách mặc định gồm cả DISABLED và REMOVED_TOMBSTONE, sắp theo source_id; lọc là AND.
5. Trace dựng lại bằng allowlist; URL bỏ userinfo, query, fragment (xử lý đề xuất A-12 về token trong redirect_chain ở lớp query); header nhạy cảm bị bỏ; warning không khớp mẫu mã an toàn bị thay bằng [redacted]; không trả body trích xuất.
6. canonical_locator của Source hiển thị nguyên (do user đăng ký), không redact.
7. Bản ghi workspace khác trả None (không lộ sự tồn tại); id rỗng ném ValueError.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- MODULE-A-OPEN-002 tiêu chí Tier

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.
- redirect_chain lưu trong package chưa redact ở nguồn (builder A-13 ngoài owned paths): ghi nhận follow-up cho CONV-A-08.
