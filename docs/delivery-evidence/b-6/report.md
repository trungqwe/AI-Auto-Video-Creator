# Báo cáo bằng chứng B-6

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `ec66302c0da0adcc0f99de10a983a393563851de`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-6 trong `docs/implementation/b/slices.md`; D3 user duyệt Phần B ngày 18/10/2026. Contract: CT-SRC-006, CT-CNT-001, CT-CNT-002, CT-CNT-003, CT-STATE-003; D8-B-01..05, D8-B-09, D8-B-10, D8-B-11, D8-B-13.
- Ghi chú: bản báo cáo trước bị hỏng mã hoá (dấu tiếng Việt thành `?`); tệp này ghi lại bằng UTF-8 không BOM, mã nguồn và test không đổi.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider` (chạy trên skeleton của `resolve_document.py`)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `31 failed in 0.32s`
- Các test FAILED tiêu biểu (thông điệp nguyên văn):
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_new_article_revision_comes_from_fixture_and_matches_resolution - AssertionError: assert [ValidationIssue(code='missing_required', field='collected_document_id'), ValidationIssue(code='missing_required', field='dedup_policy_revision'), ValidationIssue(code='missing_required', field='disposition')] == []`
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_missing_title_is_stored_as_empty_string - ValueError: not enough values to unpack (expected 1, got 0)`
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_identity_key_normalization[HTTPS://Example.COM/a/?q=1#frag-https://example.com/a/?q=1] - AssertionError: assert '' == 'https://example.com/a/?q=1'`
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_invalid_package_raises_validation_error_before_received[missing_provenance_chain] - Failed: DID NOT RAISE ResolveDocumentError`
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_infrastructure_error_is_failed_retryable_without_partial_writes[articles-save] - Failed: DID NOT RAISE ResolveDocumentError`
- Xác nhận: không có `ImportError`, `ModuleNotFoundError` hay lỗi collection; cả 31 test FAILED do `AssertionError`, `ValueError`, `KeyError` hoặc `Failed: DID NOT RAISE ResolveDocumentError`.

## Thay đổi

- `src/ingestion/application/resolve_document.py`:
  - Hằng số disposition (`NEW_ARTICLE`, `NEW_REVISION`, `DUPLICATE_MEDIA_ONLY`, `DUPLICATE_NO_NEW_VALUE`, `REJECTED_INCOMPLETE`), trạng thái CT-STATE-003 (`RECEIVED`, `NORMALIZING`, `RESOLVING_IDENTITY`, `TERMINAL_STATES`), lý do loại bỏ D8-B-09 (`CONTENT_ELIGIBILITY_ABSENT`, `CONTENT_INCOMPLETE`, `EMPTY_MAIN_TEXT`), hằng số so khớp và lưu trữ (`MATCH_EXACT`, `MATCH_NEAR`, `DEDUP_POLICY_REVISION`, `KIND_DEDUP_EVIDENCE`, `KIND_MEDIA_ATTACHMENT`, `LOCAL_RECOVERY_EPOCH`).
  - `ResolveDocumentError`: mang `code`, `state` (None trước `RECEIVED`; trạng thái CT-STATE-003 khi lỗi xảy ra sau đó) và `issues`.
  - `identity_key(url)`: chuẩn hoá khoá định danh theo D8-B-02 bằng regex stdlib `_URL_RE` (scheme và host chữ thường, bỏ fragment và dấu `/` cuối, giữ query).
  - `_attachment`, `attached_media_refs`: gộp media của các revision với media gắn thêm từ bài trùng (record kind `article_media_attachment`).
  - `_match`: cùng khoá định danh nhưng fingerprint khác → `NEW_REVISION`, giống hệt → `MATCH_EXACT`; tra exact fingerprint; near-duplicate theo thứ tự `article_id` so với revision mới nhất.
  - `_revision`: dựng `ArticleRevision` đủ trường CT-CNT-003; `title` lấy từ `extracted_content_candidate.title` (thiếu → chuỗi rỗng và ghi vào `uncertain_fields`), `requested_url` từ package, `article_revision_id` từ `id_factory`.
  - `_resolve_duplicate`: gắn media và provenance mới vào bài đại diện, chọn representative qua `select_representative` và `SourceTierLookup`, ghi `article_media_attachment` và `dedup_evidence`, phát `DuplicateDocumentResolved` (chỉ `DUPLICATE_MEDIA_ONLY` mang `new_media_discovery_refs`).
  - `_resolve`: đi `RECEIVED` → `NORMALIZING` → `RESOLVING_IDENTITY` → trạng thái cuối; `NEW_ARTICLE`/`NEW_REVISION` phát `ArticleRevisionAccepted`; `REJECTED_INCOMPLETE` không phát event; resolution qua `validate_collected_document_resolution` trước khi lưu.
  - `resolve_collected_document(...)`: package sai cấu trúc → `VALIDATION_ERROR` trước `RECEIVED` và không ghi gì; idempotent theo (`collected_document_id`, `dedup_policy_revision`); `OSError` → `FAILED_RETRYABLE`, `LookupError` → `FAILED_FINAL`, unit of work huỷ mọi ghi dở.
- `tests/unit/ingestion/test_ingestion_resolve_document.py`: 31 test item gồm NEW_ARTICLE (3), NEW_REVISION (1), khoá định danh (5), repost trùng hoàn toàn (2), repost có media mới (1), media đã biết từ nguồn đã biết (1), near-duplicate từ nguồn mới (1), representative Tier cao hơn (1), REJECTED_INCOMPLETE (4), VALIDATION_ERROR từ fixture invalid (4), idempotent TST-CTR-INV-001 (3), lỗi port → FAILED_RETRYABLE (3), tier lookup timeout (1), tier không xác định → FAILED_FINAL (1).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider` | 0 | 31 passed in 0.07s |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.05s |

## Quyết định mặc định (D8, GIẢ ĐỊNH, chưa duyệt)

1. Khoá định danh D8-B-02 hiện thực bằng regex stdlib trong `identity_key`, vì biên CHECK-B cấm `urllib`.
2. `NEW_REVISION` khi cùng khoá định danh và exact fingerprint không trùng revision nào của bài; trùng một revision thì vào nhánh trùng.
3. Near-duplicate quét bài theo `article_id`, so với revision mới nhất; ngưỡng và shingle đọc từ dedup policy.
4. Media ref lấy `ref`, không có thì lấy `url` của từng phần tử `media_discoveries`; schema payload `new_media_discovery_refs` chờ REQ-B-CONV-07.
5. Media gắn vào bài đại diện lưu ở record kind `article_media_attachment`; Article/ArticleRevision giữ nguyên. `DUPLICATE_MEDIA_ONLY` chỉ do provenance mới (source_id chưa biết) thì mang `new_media_discovery_refs` rỗng.
6. Bài trùng chạy lại `select_representative` qua `SourceTierLookup`; đổi representative chỉ áp dụng cho lần sản xuất sau.
7. Resolution có thêm trường additive `state`, `state_trail`, `resolved_at` (UTC hậu tố Z) và `reason` (REJECTED_INCOMPLETE); validator B-1 bỏ qua trường lạ.
8. `OSError` từ port → `FAILED_RETRYABLE`; `LookupError` (Tier không biết) → `FAILED_FINAL`; `VALIDATION_ERROR` ném trước `RECEIVED`, state None.
9. `recovery_epoch` keyword-only mặc định `epoch-local` (B-11 truyền từ execution_grant); `topic_rules` keyword-only mặc định rỗng.
10. `content_eligibility` khác `candidate` (ví dụ `incomplete`) dùng reason `content_incomplete`.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9); hiệu chỉnh ngưỡng D8-B-01/D8-B-03 (CP7); múi giờ D8-B-10; USER-CKPT-D9-D10; CP7 tài nguyên thật (D5); binding Tier A→B và payload B→C qua REQ-B-CONV-07.

## Giới hạn

- Không chạy full suite, không chạy `tests/m1`, `tests/m2`; không sửa binding, fixture, `pyproject.toml`, `uv.lock`, `HANDOFF.md`, `README.md`, `CHANGELOG.md`; không gọi dịch vụ thật, không đọc bí mật.
