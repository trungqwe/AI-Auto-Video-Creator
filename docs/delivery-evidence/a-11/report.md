# Báo cáo bằng chứng A-11

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d3b0cff0a6c39bb4cce7451ff61435358b50a768`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-11 trong `docs/implementation/a/slices.md`; phụ thuộc A-02, A-05, A-06, A-08 đã tích hợp.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider`
- Trạng thái mã lúc RED: `collect_source` trả `CollectionRunResult` FAILED_FINAL rỗng, `collect_sources` trả tuple rỗng.
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `16 failed, 2 passed in 0.32s`
- Test FAILED tiêu biểu nguyên văn:
  - `FAILED tests/integration/collection/test_a11_collect_source.py::test_new_periodic_run_commits_each_item_in_its_own_uow` (AssertionError: assert <RunStatus.FAILED_FINAL: 'FAILED_FINAL'> is <RunStatus.COMPLETED: 'COMPLETED'>)
  - `FAILED tests/integration/collection/test_a11_collect_source.py::test_rerun_same_business_date_reuses_run_and_emits_nothing` (AssertionError: assert 'run-other' == 'run-1')
  - `FAILED tests/integration/collection/test_a11_collect_source.py::test_crashed_run_resumes_without_replaying_committed_packages` (Failed: DID NOT RAISE Crash)
- Xác nhận: 0 error import/collection; lỗi RED là assert sai oracle.

## Thay đổi

- `src/source_ingestion/application/collect_source.py`: use case CollectSource (CT-SRC-005): `CollectSourceRequest`, `SourceCollectionJob`, `CollectionRunResult`, `ItemError`, `collect_source`, `collect_sources`. Tạo/khôi phục run theo khoá periodic trong một UoW; mỗi item hợp lệ commit một UoW gồm package (kèm `http_observation`), counters, checkpoint an toàn và outbox `CollectedDocumentAvailable`; gate lớp 1 A-02 (`validate_package_schema`) trước handoff; item đã commit không phát lại; lỗi item thành warning; lỗi nguồn được cô lập và redacted.
- `tests/integration/collection/test_a11_collect_source.py`: 18 test, adapter fake, chặn `socket.create_connection` và `socket.getaddrinfo` (cùng gethostbyname*) bằng fixture autouse, docstring ghi `coveredIds: A-RULE-004, A-RULE-008, A-RULE-012`.

## Ánh xạ yêu cầu → test

| Yêu cầu / phản ví dụ | Test |
|---|---|
| Tạo run periodic, mỗi item commit một UoW đủ package, counters, checkpoint, outbox | `test_new_periodic_run_commits_each_item_in_its_own_uow` |
| Phản ví dụ: run periodic thứ hai cùng business_date | `test_rerun_same_business_date_reuses_run_and_emits_nothing` |
| Khôi phục run, chạy lại sau commit không phát lại package | `test_crashed_run_resumes_without_replaying_committed_packages`, `test_next_day_run_skips_committed_items_and_advances_cursor` |
| Package không qua lớp 1 A-02 không handoff | `test_package_failing_layer_one_is_not_handed_off` |
| Phản ví dụ: partial rollback package đã commit | `test_failed_item_unit_of_work_rolls_back_only_that_item` |
| Item lỗi thành warning, COMPLETED_PARTIAL, FAILED_FINAL khi không commit được gì | `test_item_failure_is_a_warning_and_run_is_partial`, `test_run_without_any_committed_package_fails_final` |
| Nhiều nguồn tuần tự, một nguồn lỗi không chặn nguồn khác | `test_one_source_raising_does_not_stop_other_sources`, `test_exception_escaping_a_source_is_contained_by_collect_sources` |
| Lỗi trả về đã redacted, không lộ secret | `test_item_errors_are_redacted`, `test_one_source_raising_does_not_stop_other_sources` |
| Retry, capability, nguồn inactive/không tồn tại | `test_retryable_listing_problem_waits_then_same_run_resumes`, `test_unsupported_listing_capability_fails_final_without_retry`, `test_inactive_source_fails_final_without_fetching`, `test_unknown_source_returns_failure_without_creating_a_run` |
| Ranh giới import, request hợp lệ, chặn mạng | `test_module_imports_only_stdlib_domain_ports_and_application`, `test_request_rejects_invalid_values`, `test_network_is_blocked_for_the_whole_suite` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider` | 0 | 18 passed in 0.11s |
| 2 | `python -c` probe coveredIds | 0 | passed |
| 3 | `git diff --check` | 0 | passed (không output) |

## Quyết định mặc định (D8)

1. FetchObservation được lưu trong `http_observation` của `PackageRecord.payload` vì A-08 chưa có repository FetchObservation riêng và `memory.py` nằm ngoài owned paths.
2. `observation_fingerprint` = `content_fingerprints.raw_body_sha256`; canonical locator = `canonicalize_locator(final_url)`; identity package = (source_id, canonical locator, fingerprint) theo spec §8.
3. Checkpoint theo từng item: `item_ids=(canonical|fingerprint,)`, cursor giữ nguyên cursor đầu lượt (`cursor:start` khi chưa có, được dịch thành `None` khi gọi adapter). Cursor chỉ tiến tới `listing.cursor` qua checkpoint cuối `item_ids=()` khi mọi item của listing bền vững (không có item lỗi); item lỗi giữ cursor để lần sau thử lại.
4. Item lỗi thành warning và outcome FAILED_FINAL của domain (COMPLETED_PARTIAL nếu run đã commit ít nhất một package, ngược lại FAILED_FINAL). Lỗi listing có `retryable=True` thành FAILED_RETRYABLE (WAITING_RETRY); lỗi không retry được hoặc ngoại lệ adapter thành FAILED_FINAL.
5. Run periodic đã terminal hoặc đang WAITING_RECONCILIATION được trả lại (`replayed=True`) không fetch; RUNNING và WAITING_RETRY tiếp tục cùng run, package đã commit được bỏ qua theo identity.
6. Redaction làm cục bộ trong `collect_source.py` vì `controlplane.infrastructure` bị cấm import theo ranh giới A-01: bỏ userinfo/query/fragment khỏi URL, che password/secret/token/api key/Bearer/private key, cắt message 200 ký tự.
7. Deadline và giới hạn tài nguyên do `FetchPolicy` (timeout, kích thước) ở adapter đảm nhiệm; QUALITY-OPEN-002 (ngân sách thời gian một chu kỳ) vẫn mở.
8. Event `CollectionRunStarted`, `CollectionRunCompleted`, `CollectionRunFailed` phát qua outbox cùng UoW tạo/hoàn tất run; payload không chứa secret hay raw byte.
9. Chỉ `committed_package_count` được lưu trên run; các counter urls/fetched/skipped/failed nằm trong `CollectionRunResult` của lần gọi (replay trả 0).

## Mục mở / follow-up

- Persistence PostgreSQL và repository FetchObservation riêng chờ CONV-A-01.
- Đăng ký 10 event của A với publisher dùng chung chờ CONV-A-09.
- Cycle G và workflow gọi `collect_sources` thuộc CONV-A-06.
- Giao raw byte sang I qua ArtifactPort chưa nằm trong slice này.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full test suite, `tests/m1` hay `tests/m2`.
- Không thay đổi `pyproject.toml`, `uv.lock`, không thêm thư viện.
- Không gọi mạng hay DNS thật; adapter là fake và socket bị chặn trong test.
