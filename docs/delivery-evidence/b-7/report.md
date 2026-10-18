# Báo cáo bằng chứng B-7

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `ec66302c0da0adcc0f99de10a983a393563851de`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-7 trong `docs/implementation/b/slices.md`; D3 user duyệt Phần B ngày 18/10/2026; Contract: CT-CNT-004 (`docs/09-contracts/04-source-content-contracts.md`), CT-STATE-004 (`docs/09-contracts/12-state-machines.md`), D8-B-06 (`docs/implementation/b/plan.md`).

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider` (chạy trên skeleton của `event_link.py` và `resolve_event_link.py`)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `42 failed, 3 passed in 0.41s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_event_link.py::test_title_keywords_are_casefolded_nfc_words: AssertionError: assert frozenset() == frozenset({'l...ng\u1eadp', 'ph\u1ed1'})`
  - `FAILED tests/unit/ingestion/test_ingestion_event_link.py::test_first_article_opens_new_event_candidate_kept_separate: AssertionError: assert 0 == 1`
  - `FAILED tests/unit/ingestion/test_ingestion_event_link.py::test_similar_title_same_topic_within_window_is_linked: AssertionError: assert 0 == 2`
  - `FAILED tests/unit/ingestion/test_ingestion_event_link.py::test_linking_never_merges_or_deletes_articles: AssertionError: assert 0 == 2`
  - `FAILED tests/unit/ingestion/test_ingestion_event_link.py::test_invalid_policy_fails_closed_without_writes[overrides2]: Failed: DID NOT RAISE <class 'ValueError'>`
- Xác nhận: Hoàn toàn không có `ImportError`, `ModuleNotFoundError` hay lỗi collection; ba test PASS trên skeleton là `test_dispositions_map_to_ct_state_004`, `test_thresholds_are_not_hard_coded_in_source` và `test_new_modules_respect_check_b_import_boundary`; 42 test còn lại FAILED do `AssertionError` hoặc `Failed: DID NOT RAISE`.

## Thay đổi

- `src/ingestion/domain/event_link.py`:
  - Hằng số: `LINKED = 'linked'`, `KEPT_SEPARATE = 'kept_separate'`, `NEEDS_MORE_EVIDENCE = 'needs_more_evidence'`, `DISPOSITIONS = (LINKED, KEPT_SEPARATE, NEEDS_MORE_EVIDENCE)`, `STATE_PROPOSED = 'PROPOSED'`, `STATE_BY_DISPOSITION`, `RELATION_BY_DISPOSITION`, `POLICY_REVISION`, `LINK_JACCARD`, `REVIEW_JACCARD`, `MAX_TIME_GAP_HOURS`, `NO_COMPARABLE_EVENT`.
  - Dataclass: `EventLinkPolicy(revision: str, link_jaccard: float, review_jaccard: float, max_time_gap_hours: float)` frozen; `PairAssessment(disposition: str, confidence: float, explanation: tuple[str, ...])` frozen; `EventLinkResolution(...)` frozen kw_only.
  - Hàm: `_number(policy, key)` kiểm tra số hợp lệ (từ chối bool); `parse_event_link_policy(policy)` xác thực fail-closed phạm vi ngưỡng; `title_keywords(title)` sinh frozenset từ ngữ `\w+` sau normalize NFC và casefold; `parse_rfc3339(value)` parse aware datetime UTC; `revision_time(revision)` ưu tiên published_at hợp lệ, fallback fetched_at; `assess_pair(subject, member, policy)` thực thi luật D8-B-06 (thiếu evidence không bao giờ LINKED); `rank(assessment)` sắp xếp ưu tiên LINKED > NEEDS_MORE_EVIDENCE > KEPT_SEPARATE theo sau bởi confidence.
- `src/ingestion/application/resolve_event_link.py`:
  - Hằng số: `EVENT_LINK_CANDIDATE_KIND = 'event_link_candidate'`, `EVENT_LINK_RESOLVED = 'EventLinkResolved'`, `EVENT_AGGREGATE_TYPE = 'Event'`, `EVENT_STATUS_CANDIDATE = 'candidate'`.
  - Helper private: `_token`, `_refs`, `_now`, `_load_revision`, `_time_range`, `_stored_resolution`, `_best_match`, `_resolve_one`.
  - Use case public: `resolve_event_link(article_revision_refs, event_link_policy, uow, clock, id_factory, *, recovery_epoch) -> tuple[EventLinkResolution, ...]`. Mỗi ref chạy một transaction `with uow:`. Idempotency qua `_stored_resolution`. Tuyệt đối không gọi `articles.save`, không gộp hay xóa Article. Phát `EventLinkResolved` qua `build_event` với payload chỉ chứa ID/ref.
- `tests/unit/ingestion/test_ingestion_event_link.py`:
  - 45 test items bao quát toàn diện các yêu cầu CT-CNT-004, CT-STATE-004, D8-B-06, import boundary CHECK-B, không hardcode ngưỡng trong mã nguồn, tính độc lập bất biến của Article, phát EventLinkResolved và idempotency replay.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider` | 0 | 45 passed in 0.08s |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.06s |

## Quyết định mặc định (D8)

(Ghi nhận dưới dạng GIẢ ĐỊNH theo quy chế D8, không phải đã duyệt chính thức):
1. Khóa policy: event_link_policy_revision, link_jaccard, review_jaccard, max_time_gap_hours. Giá trị event-link-policy-r1 (0.5/0.3/72) chỉ được truyền vào trong test; src không viết cứng.
2. Từ khóa tiêu đề là tập từ `\w+` sau normalize_text và casefold; chưa dùng stopword.
3. Thiếu evidence (published_at thiếu hoặc không parse được, topic_uncertain) thì không bao giờ LINKED: Jaccard ≥ review thì NEEDS_MORE_EVIDENCE, còn lại KEPT_SEPARATE.
4. KEPT_SEPARATE mở event candidate mới chỉ chứa bài đó. NEEDS_MORE_EVIDENCE trả event_id của event được đề xuất nhưng không thêm bài vào event.
5. relation_type nhận same_event, separate_event hoặc possible_same_event. confidence là Jaccard từ khóa tiêu đề của cặp tốt nhất, bằng 0.0 khi chưa có event để so.
6. effective_time_range là min/max published_at (fallback fetched_at) của các thành viên event.
7. Chọn event theo thứ tự LINKED > NEEDS_MORE_EVIDENCE > KEPT_SEPARATE, rồi Jaccard cao hơn; nếu hòa thì lấy event_id nhỏ hơn.
8. EventLinkResolved phát cho cả 3 disposition. Payload chỉ mang event_link_candidate_id, event_id, article_id, article_revision_id, event_link_policy_revision; disposition đọc từ bản ghi event_link_candidate vì allow-list payload của B-4 giữ nguyên.
9. recovery_epoch là tham số keyword-only bắt buộc, vì build_event yêu cầu và không được bịa giá trị.
10. Mỗi ref chạy một transaction. Replay cùng article_revision_id và cùng policy revision trả kết quả đã lưu, không ghi thêm.
11. resolve_event_link không gọi articles.save, không gộp hay xóa Article.

## Danh sách chờ user (pendingUserCheckpoint)

- Hiệu chỉnh ngưỡng D8-B-06 trên dữ liệu thật (CP7-B-1).
- Schema payload 4 event B qua REQ-B-CONV-07.
- User checkpoint M2 (P8/P9).
- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).

## Giới hạn

- Không chạy full suite, không chạy tests/m1, tests/m2.
- Không sửa events.py, ports.py, memory.py, binding, fixture, pyproject.toml, uv.lock, HANDOFF.md, README.md, CHANGELOG.md.
- Không gọi dịch vụ thật hay đọc bí mật.
