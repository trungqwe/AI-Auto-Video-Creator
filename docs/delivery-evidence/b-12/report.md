# Báo cáo bằng chứng B-12

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `c73f90b87c3aa9bd038e9c1b71374ceb1b04a20f`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-12 trong `docs/implementation/b/slices.md`; D3 user duyệt Phần B ngày 18/10/2026.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider`
- Exit code: `1`
- Dòng tóm tắt nguyên văn: `1 failed, 14 passed in 0.22s`
- Test FAILED: `FAILED tests/integration/ingestion/test_ingestion_flow_integration.py::test_resolution_dispositions_match_the_corpus_for_every_item`
- Thông điệp assert nguyên văn:
  ```text
  AssertionError: b12-d1b
  assert 'DUPLICATE_NO_NEW_VALUE' == 'NEW_ARTICLE'
    - NEW_ARTICLE
    + DUPLICATE_NO_NEW_VALUE
  ```
- Xác nhận: RED là kỳ vọng sai có chủ đích ở mục b12-d1b (trong corpus ban đầu ghi `expected.resolution = NEW_ARTICLE` trong khi văn bản là exact duplicate chỉ đổi khoảng trắng/ký tự điều khiển nên hệ thống trả `DUPLICATE_NO_NEW_VALUE`) vì slice B-12 chỉ thêm test và fixture, không có lỗi import hay setup.

## Thay đổi

- 3 tệp thuộc owned paths:
  - `tests/integration/ingestion/fixtures/ingestion_corpus_v1.json`: Corpus dữ liệu tổng hợp (synthetic self-written, không chép báo thật, URL miền `.invalid`) gồm 18 mục thuộc 3 nhóm:
    - `news`: 8 mục (`b12-n01` đến `b12-n08`), gồm mục canary `b12-n05`, giả lệnh hệ thống `b12-n06`, incomplete paywalled `b12-n07`, empty main text `b12-n08`.
    - `duplicate_clusters`: 4 cụm với 11 mục (`b12-exact` 3 mục, `b12-near` 2 mục, `b12-repost-media` 3 mục, `b12-revision` 3 mục).
    - `event_timeline_set`: 6 mục (`b12-t01` đến `b12-t06`) với scenario lần lượt `first`, `no_new_fact`, `separate`, `first`, `repost`, `real_update`.
  - `tests/integration/ingestion/test_ingestion_flow_integration.py`: Test tích hợp chạy trọn chuỗi activity (`handle_resolve_activity`) → resolve (`resolve_document`) → event link (`resolve_event_link`) → event update (`evaluate_event_update`) → source set (`build_source_set`) với fake A/G/C/D/J và `InMemoryUnitOfWork`, gồm 15 hàm test:
    - `test_corpus_is_synthetic_and_covers_required_groups`
    - `test_every_corpus_item_has_expected_disposition`
    - `test_resolution_dispositions_match_the_corpus_for_every_item`
    - `test_chain_runs_through_every_stage_and_fake`
    - `test_duplicates_add_no_article_or_draft_and_keep_new_media`
    - `test_changed_text_at_the_same_identity_is_a_new_revision`
    - `test_event_link_dispositions_match_the_corpus`
    - `test_event_update_dispositions_match_the_corpus`
    - `test_timeline_mode_needs_an_accepted_update`
    - `test_other_production_modes_pin_the_stored_revisions`
    - `test_canary_never_reaches_outbox_events_or_results`
    - `test_canary_in_a_loader_failure_never_reaches_the_failed_result`
    - `test_system_instruction_text_changes_neither_policy_nor_disposition`
    - `test_replaying_an_activity_request_writes_nothing_new`
    - `test_integration_test_directory_is_not_a_package`
  - `docs/delivery-evidence/b-12/report.md`: Báo cáo bằng chứng nghiệm thu nhiệm vụ B-12.

## Ánh xạ mã kiểm thử

| Mã kiểm thử | Tên hàm kiểm thử tương ứng | Ghi chú |
|---|---|---|
| `TST-INT-INV-005` | `test_duplicates_add_no_article_or_draft_and_keep_new_media` | Duplicate không tạo article/draft mới, lưu trữ dedup_evidence |
| `TST-E2E-002` | `test_duplicates_add_no_article_or_draft_and_keep_new_media` | Giữ media mới từ duplicate media only |
| `TST-E2E-003` | `test_event_update_dispositions_match_the_corpus`, `test_timeline_mode_needs_an_accepted_update` | Đánh giá update bài viết mới so với event; timeline mode cần accepted update |
| `TST-E2E-004` | `test_event_update_dispositions_match_the_corpus`, `test_timeline_mode_needs_an_accepted_update` | Repost và nguồn mới không tình tiết mới không sinh EventUpdateAccepted và bị từ chối timeline |
| `TST-CTR-INV-006` | `test_timeline_mode_needs_an_accepted_update` | Kiểm tra gate from_then_to_now cần accepted update |
| `TST-SEC-INV-012` | `test_canary_never_reaches_outbox_events_or_results`, `test_canary_in_a_loader_failure_never_reaches_the_failed_result` | Chuỗi CANARY-SECRET-B12 không rò rỉ vào outbox, result hay evidence kể cả khi loader lỗi |
| `TST-SEC-INV-020` | `test_system_instruction_text_changes_neither_policy_nor_disposition` | Văn bản chứa SYSTEM INSTRUCTION giả lệnh không làm thay đổi policy revision hay disposition |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | `python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider` | 0 | `15 passed in 0.11s` |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | `35 passed in 0.05s` |

## Quyết định mặc định (D8)

(Ghi nhận dưới dạng GIẢ ĐỊNH theo quy chế D8, chưa duyệt chính thức):
1. Ngưỡng chính sách dedup near_duplicate_jaccard=0.8, shingle_size=3; event_link link_jaccard=0.5, review_jaccard=0.3, max_time_gap_hours=48; event_update repost_jaccard=0.5, shingle_size=3 được chọn trong corpus.
2. Fake A/G/C/D/J dựng ngay trong tệp test tích hợp: FakeCollector phục vụ collected_document_package; FakeClaims cung cấp ClaimCandidate cho event update; FakeCatalog ghi nhận media từ outbox DuplicateDocumentResolved; FakeCreative ghi nhận draft từ ArticleRevisionAccepted và đóng vai trò timeline gate; FakeSecretBroker kiểm tra rò rỉ canary.
3. Mọi URL trong corpus đều dùng miền `.invalid`.
4. TST-E2E-004 được kiểm bằng kịch bản repost và nguồn mới không có tình tiết mới không sinh `EventUpdateAccepted` và bị từ chối `from_then_to_now`.

## Danh sách chờ user (pendingUserCheckpoint)

- Giữ các checkpoint đã có từ trước: `USER-CKPT-D9-D10`, `REQ-B-CONV-02` (adapter PostgreSQL), `CP7` tài nguyên thật (D5).
- Không phát sinh checkpoint mới.

## Giới hạn

- Không chạy full regression suite, không chạy tests/m1, tests/m2.
- Không sửa bất kỳ tệp nào trong `src/**` hay `migrations/**`.
- Không tạo `tests/integration/ingestion/__init__.py`.
- Không gọi dịch vụ thật hay đọc bí mật.
