# Báo cáo bằng chứng B-8

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `2233e36f669f9ea4d8ffdd9b0724aa8c9fe19753`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-8 trong `docs/implementation/b/slices.md`; D3 user duyệt Phần B ngày 18/10/2026; Contract: CT-CNT-005 (`docs/09-contracts/04-source-content-contracts.md`), CT-STATE-004 (`docs/09-contracts/12-state-machines.md`), D8-B-07 (`docs/implementation/b/plan.md`).

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider` (chạy trên skeleton của `event_update.py` và `evaluate_event_update.py`)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `50 failed, 11 passed in 0.46s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_event_update.py::test_new_claim_from_non_repost_is_accepted: AssertionError: assert ('UNCERTAIN',...im_candidate') == ('ACCEPTED_NE..._claim_found')`
  - `FAILED tests/unit/ingestion/test_ingestion_event_update.py::test_exact_repost_from_new_source_is_rejected_even_with_new_claim: AssertionError: assert ('UNCERTAIN',...im_candidate') == ('REJECTED_RE...event_member')`
  - `FAILED tests/unit/ingestion/test_ingestion_event_update.py::test_near_duplicate_repost_is_rejected: AssertionError: assert 'UNCERTAIN' == 'REJECTED_REPOST'`
  - `FAILED tests/unit/ingestion/test_ingestion_event_update.py::test_event_without_baseline_revision_is_uncertain: AssertionError: assert ('UNCERTAIN',...im_candidate') == ('UNCERTAIN',...ine_revision')`
  - `FAILED tests/unit/ingestion/test_ingestion_event_update.py::test_invalid_policy_fails_closed_without_writes[overrides0]: Failed: DID NOT RAISE <class 'ValueError'>`
  - `FAILED tests/unit/ingestion/test_ingestion_event_update.py::test_unknown_event_or_revision_raises_lookup_error_without_writes: Failed: DID NOT RAISE <class 'LookupError'>`
- Xác nhận: Hoàn toàn không có `ImportError`, `ModuleNotFoundError`, `NameError` hay lỗi collection; 11 test PASS trên skeleton gồm: `test_states_follow_ct_state_004`, `test_empty_claim_provider_is_uncertain`, `test_claims_without_evidence_on_subject_revision_are_ignored`, `test_evaluation_never_changes_articles_or_event`, `test_thresholds_are_not_hard_coded_in_source`, 4 ca của `test_claim_candidate_rejects_invalid_refs`, `test_fake_provider_satisfies_protocol`, và `test_new_modules_respect_check_b_import_boundary`; 50 test còn lại FAILED do `AssertionError` hoặc `Failed: DID NOT RAISE`.

## Thay đổi

- `src/ingestion/domain/event_update.py`:
  - Hằng số: `ACCEPTED_NEW_DEVELOPMENT = 'ACCEPTED_NEW_DEVELOPMENT'`, `REJECTED_REPOST = 'REJECTED_REPOST'`, `REJECTED_NO_NEW_FACT = 'REJECTED_NO_NEW_FACT'`, `UNCERTAIN = 'UNCERTAIN'`, `STATES = (ACCEPTED_NEW_DEVELOPMENT, REJECTED_REPOST, REJECTED_NO_NEW_FACT, UNCERTAIN)`, `STATE_PROPOSED = 'PROPOSED'`, `POLICY_REVISION = 'event_update_policy_revision'`, `REPOST_JACCARD = 'repost_jaccard'`, `SHINGLE_SIZE = 'shingle_size'`, `REASON_NEW_CLAIM = 'new_claim_found'`, `REASON_REPOST = 'repost_of_event_member'`, `REASON_ALL_CLAIMS_KNOWN = 'all_claims_known'`, `REASON_NO_CLAIM_CANDIDATE = 'no_claim_candidate'`, `REASON_NO_BASELINE = 'no_baseline_revision'`, `_TOKEN_RE`.
  - Dataclass: `EventUpdatePolicy(revision: str, repost_jaccard: float, shingle_size: int)` frozen; `ClaimCandidate(claim_ref: str, evidence_article_revision_id: str)` frozen với validation token trong `__post_init__`; `EventUpdateDecision(state: str, new_claim_refs: tuple[str, ...], confidence: float, reason: str)` frozen; `EventUpdateEvaluation(...)` frozen kw_only.
  - Hàm: `parse_event_update_policy(policy)` xác thực mapping và các trường policy (repost_jaccard trong (0, 1], shingle_size int ≥ 1); `repost_score(subject, member, policy)` trả 1.0 khi trùng exact_fingerprint, ngược lại tính Jaccard shingle của normalized_text; `decide(subject, baseline, candidates, known_claim_refs, policy)` thực thi luật D8-B-07 theo thứ tự: thiếu baseline → repost → thiếu claim candidate → claim cũ toàn bộ → accepted_new_development.
- `src/ingestion/application/evaluate_event_update.py`:
  - Hằng số: `EVENT_UPDATE_CANDIDATE_KIND = 'event_update_candidate'`, `EVENT_UPDATE_KIND = 'event_update'`, `EVENT_UPDATE_ACCEPTED = 'EventUpdateAccepted'`, `EVENT_UPDATE_AGGREGATE_TYPE = 'EventUpdate'`, `_TOKEN_RE`.
  - Protocol: `ClaimCandidateProvider` runtime_checkable với phương thức `claim_candidates(revision: ArticleRevision) -> Sequence[ClaimCandidate]`.
  - Helper: `_token`, `_revision_ref`, `_now`, `_load_revision`, `_claims`, `_stored_evaluation`, `_baseline`, `_event_updates`, `_accept`, `_evaluate_one`.
  - Use case public: `evaluate_event_update(event_id, article_revision_ref, claim_provider, policy, uow, clock, id_factory, *, recovery_epoch) -> EventUpdateEvaluation`. Chạy trong 1 transaction `with uow:`. Idempotent replay theo bộ ba `(event_id, article_revision_id, policy_revision)`. Mọi kết quả đều ghi `event_update_candidate`; chỉ `ACCEPTED_NEW_DEVELOPMENT` ghi `event_update` và outbox `EventUpdateAccepted`. Không gọi `articles.save`, không gọi `events.save`.
- `tests/unit/ingestion/test_ingestion_event_update.py`:
  - 61 test items bao quát toàn diện các yêu cầu CT-CNT-005, CT-STATE-004, D8-B-07, CHECK-B import boundary, không hardcode ngưỡng trong mã nguồn, outbox EventUpdateAccepted mang refs only, replay idempotent, fail-closed khi thiếu key hoặc sai định dạng.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider` | 0 | 61 passed in 0.08s |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.05s |

## Quyết định mặc định (D8)

(Ghi nhận dưới dạng GIẢ ĐỊNH theo quy chế D8, không phải đã duyệt chính thức):
1. Khoá policy event_update_policy_revision, repost_jaccard, shingle_size; giá trị r1 (0.75/3) chỉ có trong test; src không viết cứng.
2. Repost = exact_fingerprint trùng hoặc Jaccard shingle normalized_text ≥ repost_jaccard với revision baseline.
3. Baseline = thành viên đứng trước subject trong member_refs, subject ngoài event thì so mọi thành viên; không có baseline → UNCERTAIN no_baseline_revision (fail-closed CT-CNT-005).
4. Claim là ref mờ claim_ref, khớp = trùng claim_ref; claim đã có = claim baseline qua provider ∪ new_claim_refs của EventUpdate đã chấp nhận; candidate có evidence_article_revision_id khác subject bị bỏ qua.
5. Thứ tự quyết định: no baseline → repost → no claim → all known → accepted.
6. Confidence: accepted = số claim mới / số claim hợp lệ của subject; repost = điểm repost cao nhất; còn lại 0.0.
7. Source_revision_refs = subject rồi đến các baseline members.
8. Event_update_revision = số EventUpdate đã chấp nhận của event + 1; EventUpdate là aggregate riêng (aggregate_revision 1); không sửa Event hay Article.
9. Payload EventUpdateAccepted chỉ gồm event_update_id, event_id, event_update_revision, article_revision_id, new_claim_refs, source_revision_refs, event_update_policy_revision.
10. Recovery_epoch keyword-only bắt buộc theo build_event contract.
11. Replay theo (event_id, article_revision_id, policy revision) trả kết quả đã lưu mà không ghi; policy revision mới không chấp nhận lại claim đã chấp nhận.
12. Output provider sai kiểu → ValueError, không ghi gì vào uow.
13. Caller chọn event_id từ kết quả của B-7.

## Danh sách chờ user (pendingUserCheckpoint)

- Hiệu chỉnh ngưỡng D8-B-07 trên dữ liệu thật (CP7).
- Bộ trích claim thật thuộc D/CP7.
- Schema payload 4 event B qua REQ-B-CONV-07.
- User checkpoint M2 (P8/P9).
- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).

## Giới hạn

- Không chạy full suite, không chạy tests/m1, tests/m2.
- Không sửa events.py, ports.py, memory.py, resolve_event_link.py, binding, fixture, pyproject.toml, uv.lock, HANDOFF.md, README.md, CHANGELOG.md.
- Không gọi dịch vụ thật hay đọc bí mật.
