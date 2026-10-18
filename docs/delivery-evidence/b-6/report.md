# B?o c?o b?ng ch?ng B-6

## M?i tr??ng

- Interpreter kho?: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `ec66302c0da0adcc0f99de10a983a393563851de`
- Ngu?n quy?n: IMPL-PLAN-B Auditor PASS; slice B-6 trong `docs/implementation/b/slices.md`; D3 user duy?t Ph?n B ng?y 18/10/2026. Contract: CT-SRC-006, CT-CNT-001, CT-CNT-002, CT-CNT-003, CT-STATE-003; D8-B-01..05, D8-B-09, D8-B-10, D8-B-11, D8-B-13.

## RED

- L?nh th?c thi: `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider` (ch?y tr?n skeleton c?a `resolve_document.py`)
- Exit code th?c t?: `1`
- D?ng t?m t?t nguy?n v?n: `31 failed in 0.32s`
- Chi ti?t c?c test FAILED ti?u bi?u k?m th?ng ?i?p nguy?n v?n:
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_new_article_revision_comes_from_fixture_and_matches_resolution - AssertionError: assert [ValidationIssue(code='missing_required', field='collected_document_id'), ValidationIssue(code='missing_required', field='dedup_policy_revision'), ValidationIssue(code='missing_required', field='disposition')] == []`
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_missing_title_is_stored_as_empty_string - ValueError: not enough values to unpack (expected 1, got 0)`
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_identity_key_normalization[HTTPS://Example.COM/a/?q=1#frag-https://example.com/a?q=1] - AssertionError: assert '' == 'https://example.com/a?q=1'`
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_invalid_package_raises_validation_error_before_received[missing_provenance_chain] - Failed: DID NOT RAISE ResolveDocumentError`
  - `FAILED tests/unit/ingestion/test_ingestion_resolve_document.py::test_infrastructure_error_is_failed_retryable_without_partial_writes[articles-save] - Failed: DID NOT RAISE ResolveDocumentError`
- X?c nh?n: Ho?n to?n kh?ng c? `ImportError`, `ModuleNotFoundError` hay l?i collection; to?n b? 31 test FAILED do `AssertionError`, `ValueError`, `KeyError` ho?c `Failed: DID NOT RAISE ResolveDocumentError`.

## Thay ??i

- `src/ingestion/application/resolve_document.py`:
  - H?ng s?: disposition (`NEW_ARTICLE`, `NEW_REVISION`, `DUPLICATE_MEDIA_ONLY`, `DUPLICATE_NO_NEW_VALUE`, `REJECTED_INCOMPLETE`), tr?ng th?i CT-STATE-003 (`RECEIVED`, `NORMALIZING`, `RESOLVING_IDENTITY`, `TERMINAL_STATES`), l? do lo?i b? D8-B-09 (`CONTENT_ELIGIBILITY_ABSENT`, `CONTENT_INCOMPLETE`, `EMPTY_MAIN_TEXT`), h?ng s? so kh?p v? l?u tr? (`MATCH_EXACT`, `MATCH_NEAR`, `DEDUP_POLICY_REVISION`, `KIND_DEDUP_EVIDENCE`, `KIND_MEDIA_ATTACHMENT`, `LOCAL_RECOVERY_EPOCH`).
  - L?p ngo?i l? `ResolveDocumentError`: mang `code`, `state` (None tr??c `RECEIVED`, tr?ng th?i CT-STATE-003 khi l?i sau `RECEIVED`), v? `issues` chi ti?t.
  - H?m `identity_key(url: str) -> str`: chu?n h?a URL ??nh danh theo D8-B-02 b?ng regex stdlib `_URL_RE` (lowercase scheme v? host, b? fragment v? d?u g?ch ch?o cu?i, gi? nguy?n query params).
  - H?m tra c?u media: `_attachment(uow, article_id)` v? `attached_media_refs(uow, article_id)` g?p media t? revision c?a Article v? media g?n th?m t? c?c b?n ghi tr?ng l?p l?u t?i `article_media_attachment`.
  - H?m so kh?p `_match(uow, key, fingerprint, normalized_text, policy)`: t?m ki?m theo identity key (kh?c fingerprint -> `NEW_REVISION`, tr?ng -> `MATCH_EXACT`), theo exact fingerprint (`MATCH_EXACT`), v? theo near-duplicate Jaccard tr?n revision m?i nh?t c?a c?c b?i ?? s?p x?p theo `article_id` (`MATCH_NEAR`).
  - H?m d?ng revision `_revision(...)`: kh?i t?o `ArticleRevision` v?i ??y ?? c?c tr??ng theo CT-CNT-003, tr?ch xu?t title (thi?u -> chu?i r?ng), g?n `uncertain_fields`, ph?n lo?i topic qua `classify_topic`, chu?n h?a th?i gian UTC.
  - H?m x? l? b?i tr?ng `_resolve_duplicate(...)`: g?n media m?i v? provenance v?o b?i ??i di?n, ??nh gi? representative qua `select_representative` v? `SourceTierLookup`, ghi `article_media_attachment` v? `dedup_evidence`, ph?t s? ki?n `DuplicateDocumentResolved` (ch? `DUPLICATE_MEDIA_ONLY` ch?a `new_media_discovery_refs`).
  - H?m nghi?p v? `_resolve(...)`: duy?t tu?n t? qua c?c tr?ng th?i `RECEIVED -> NORMALIZING -> RESOLVING_IDENTITY -> terminal`, ph?n nh?nh `REJECTED_INCOMPLETE`, `NEW_ARTICLE`/`NEW_REVISION`, ho?c duplicate; ki?m tra t?nh h?p l? qua `validate_collected_document_resolution` tr??c khi l?u v?o UoW.
  - H?m entry point `resolve_collected_document(...)`: x?c th?c c?u tr?c package tr??c `RECEIVED` (n?m `VALIDATION_ERROR` n?u sai v? kh?ng ghi b?n ghi), ??m b?o t?nh idempotent theo `(collected_document_id, dedup_policy_revision)`, qu?n l? transaction UoW, b?t l?i `OSError` -> `FAILED_RETRYABLE` v? `LookupError` -> `FAILED_FINAL` m? kh?ng ghi d? dang.
- `tests/unit/ingestion/test_ingestion_resolve_document.py`:
  - 31 test item bao qu?t to?n b? 5 disposition v? r?ng bu?c giao th?c:
    - `NEW_ARTICLE`: revision t?o t? fixture ??y ?? tr??ng (title 'Sample Title', requested_url, article_revision_id tr?ng resolution), title thi?u l?u chu?i r?ng v? ghi nh?n uncertain field, ph?t event `ArticleRevisionAccepted` kh?ng ch?a n?i dung text (3 test).
    - `NEW_REVISION`: c?p nh?t n?i dung c?ng URL ??nh danh t?ng revision number v? ph?t event v?i aggregate_revision t??ng ?ng (1 test).
    - Kh?a ??nh danh: ?u ti?n `canonical_url_candidate`, chu?n h?a URL kh?ng ph?n bi?t hoa th??ng host/scheme, lo?i b? fragment v? trailing slash (5 test).
    - Repost tr?ng l?p ho?n to?n: `DUPLICATE_NO_NEW_VALUE` kh?ng t?o Article/revision m?i, ph?t `DuplicateDocumentResolved` kh?ng ch?a `new_media_discovery_refs`, l?u `dedup_evidence` (2 test).
    - Repost c? media m?i: `DUPLICATE_MEDIA_ONLY` g?n media v?o b?i ??i di?n, ph?t `DuplicateDocumentResolved` mang danh s?ch media m?i (1 test).
    - Media ?? bi?t t? ngu?n ?? bi?t: `DUPLICATE_NO_NEW_VALUE` (1 test).
    - Near-duplicate t? ngu?n m?i: `DUPLICATE_MEDIA_ONLY` v?i provenance m?i, l?u b?ng ch?ng near match (1 test).
    - Ngu?n tr?ng l?p c? Tier cao h?n: thay th? `representative_source_id` cho l?n s?n xu?t t??ng lai (1 test).
    - `REJECTED_INCOMPLETE`: v?ng m?t `content_eligibility`, `content_eligibility='incomplete'`, n?i dung text ch? ch?a k? t? tr?ng/U+200B, ho?c thi?u candidate content; kh?ng t?o Article v? kh?ng ph?t event (4 test).
    - Package sai c?u tr?c: n?m `ResolveDocumentError` v?i m? `VALIDATION_ERROR` tr??c `RECEIVED`, state None, snapshot UoW ho?n to?n r?ng (4 test t? fixture invalid).
    - Idempotent TST-CTR-INV-001: g?i l?i c?ng `collected_document_id` v? `dedup_policy_revision` tr? c?ng k?t qu? resolution, kh?ng ghi th?m b?n ghi cho c? new article, duplicate v? rejected (3 test).
    - Kh? n?ng ph?c h?i h? t?ng D8-B-11: `ConnectionError` (OSError) khi l?u article/outbox/resolution chuy?n th?nh `FAILED_RETRYABLE` v? rollback to?n b? thay ??i (3 test).
    - S? c? Tier lookup: `TimeoutError` (OSError) th?nh `FAILED_RETRYABLE` (1 test).
    - Tier kh?ng x?c ??nh: `LookupError` th?nh `FAILED_FINAL` (1 test).

## L?nh ki?m

| # | L?nh | Exit code | K?t qu? |
|---|---|---|---|
| 1 | `git diff --check` | 0 | kh?ng output |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider` | 0 | 31 passed in 0.08s |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.05s |

## Quy?t ??nh m?c ??nh (D8, GI? ??NH, ch?a duy?t)

1. Kh?a ??nh danh D8-B-02 hi?n th?c b?ng regex stdlib trong `identity_key`, v? bi?n CHECK-B c?m `urllib`.
2. NEW_REVISION khi c?ng kh?a ??nh danh v? exact fingerprint kh?ng tr?ng revision n?o c?a b?i; tr?ng m?t revision ? nh?nh tr?ng.
3. Near-duplicate qu?t b?i theo `article_id`, so v?i revision m?i nh?t; ng??ng v? shingle ??c t? dedup policy.
4. Media ref l?y `ref`, kh?ng c? th? l?y `url` c?a t?ng ph?n t? `media_discoveries`; schema payload `new_media_discovery_refs` ch? REQ-B-CONV-07.
5. Media g?n v?o b?i ??i di?n l?u ? record kind `article_media_attachment`, Article/ArticleRevision gi? nguy?n; DUPLICATE_MEDIA_ONLY ch? do provenance m?i th? mang `new_media_discovery_refs` r?ng.
6. B?i tr?ng ch?y l?i `select_representative` qua `SourceTierLookup`; ??i representative ch? ?p d?ng cho l?n s?n xu?t sau.
7. Resolution c? th?m tr??ng additive `state`, `state_trail`, `resolved_at` (UTC h?u t? Z) v? `reason` (REJECTED_INCOMPLETE); validator B-1 b? qua tr??ng l?.
8. OSError t? port ? `FAILED_RETRYABLE`; LookupError (Tier kh?ng bi?t) ? `FAILED_FINAL`; VALIDATION_ERROR n?m tr??c RECEIVED, state None.
9. `recovery_epoch` keyword-only m?c ??nh `epoch-local`, B-11 truy?n t? execution_grant; `topic_rules` keyword-only m?c ??nh r?ng ? `unclassified`.
10. `content_eligibility=incomplete` d?ng reason `content_incomplete`.

## Danh s?ch ch? user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9); hi?u ch?nh ng??ng D8-B-01/D8-B-03 (CP7); m?i gi? D8-B-10; USER-CKPT-D9-D10; CP7 t?i nguy?n th?t (D5); binding Tier A?B v? payload B?C qua REQ-B-CONV-07.

## Gi?i h?n

- Kh?ng ch?y full suite, kh?ng ch?y tests/m1, tests/m2; kh?ng s?a binding, fixture, pyproject.toml, uv.lock, HANDOFF.md, README.md, CHANGELOG.md; kh?ng g?i d?ch v? th?t, kh?ng ??c b? m?t.
