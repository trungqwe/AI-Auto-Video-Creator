# K? Ho?ch Ki?m Th? To?n Di?n: M3-A (Comprehensive Test Plan Specification)

> **M? g?i (Package ID):** `M3-A`
> **Tr?ng th?i:** `planned_test_strategy`
> **T?i li?u ngu?n:** `docs/10-test-strategy.md` (M?c 10, 34), `docs/modules/a-source-collection/implementation-plan.md`
> **Ph??ng ph?p lu?n:** Test-First / Behavioral TDD (`SPEC` ? `PLAN` ? `RED` ? `IMPLEMENT` ? `GREEN` ? `VERIFY` ? `EVIDENCE`)

---

## 1. Nguy?n T?c & K? Lu?t Ki?m Th? B?t Bu?c

1. **Ch?ng ki?n h?ng h?c h?nh vi (Behavioral RED First):**
   - Tr??c khi vi?t m? s?n ph?m, m?i ca ki?m th? ph?i ch?y v? th?t b?i v? vi ph?m assertions nghi?p v?/h?p ??ng (`Behavioral RED`), tuy?t ??i kh?ng ch?p nh?n RED do l?i import, l?i c?u h?nh m?i tr??ng, ho?c thi?u binary (`Invalid Setup Failure`).
2. **Ki?m th? tr?n PostgreSQL Disposable Th?t (Real DB Isolation):**
   - Kh?ng d?ng SQLite hay in-memory mock ?? thay th? PostgreSQL cho c?c ki?m th? li?n quan ??n transaction, isolation, concurrency, outbox, ho?c unique indexes.
   - M?i test function ho?c test suite s? d?ng database t?m th?i ri?ng bi?t (`function-scoped disposable database`), t? ??ng d?n d?p s?ch s? sau khi ch?y xong (`0 orphan databases`).
3. **C?m d?ng Mock ?? v??t qua c?ng ki?m tra (No Mocking Gateways):**
   - Tuy?t ??i kh?ng mock ki?m tra SSRF, ki?m tra m? b?m SHA-256 to?n v?n, ho?c quy tr?nh k? ch? k? s? out-of-process.
4. **K? lu?t Targeted Test (Zero Waste Execution):**
   - Trong qu? tr?nh ph?t tri?n v? s?a l?i, ch? ch?y ??ng l?nh ki?m th? m?c ti?u ???c ch? ??nh; ch? ch?y to?n b? b? ki?m th? t?ch h?p khi b??c v?o giai ?o?n t?ng h?p h? s? evidence.

---

## 2. Danh M?c C?c Test Oracle B?t Bu?c (Mandatory Test Oracles)

### 2.1. Nh?m ??ng h?u ki?m AUD2 (Theo docs/10-test-strategy.md M?c 34)

| M? Ki?m Th? | T?nh hu?ng k?ch ho?t (Scenario) | H?nh vi mong ??i & Oracle b?t bu?c (Expected Oracle) |
|---|---|---|
| `TST-COL-END-001` | L?n th? (attempt) retryable cu?i c?ng g?p l?i; c? ho?c kh?ng c? package h?p l? ?? commit tr??c ?? | Kh?ng t?o attempt gi?; chuy?n `COMPLETED_PARTIAL` n?u ?? c? package, ng??c l?i `FAILED_FINAL` v?i l? do `RETRY_EXHAUSTED`; b?o to?n nguy?n v?n checkpoint v? d? li?u ?? commit |
| `TST-COL-END-002` | Ngu?n b? v? hi?u h?a (`DISABLED`) ho?c x?a (`REMOVED_TOMBSTONE`) khi l??t qu?t ?ang ? `SCHEDULED`, `RUNNING` ho?c `WAITING_RETRY` | D?ng ngay l?p t?c, kh?ng fetch ti?p; chuy?n `COMPLETED_PARTIAL` ho?c `FAILED_FINAL` theo b?ng CT-STATE-002 v?i l? do `SOURCE_INACTIVE`; khi kh?i ph?c ngu?n kh?ng m? l?i run ?? terminal |
| `TST-COL-END-003` | Reconcile x?c nh?n k?t qu? retryable / full success / partial success / final error v?i ng?n s?ch c?n ho?c h?t | Chuy?n tr?ng th?i ch?nh x?c theo ma tr?n CT-STATE-002; kh?ng l?p l?i t?c ??ng ph? (side effect); ??nh k?m ??y ?? b?ng ch?ng ??i so?t |
| `TST-COL-END-004` | K?t qu? t?c ??ng ph? v?n kh?ng x?c ??nh (`OUTCOME_UNKNOWN`) khi ?? h?t h?n h?n ch?t reconcile | Duy tr? tr?ng th?i `WAITING_RECONCILIATION` c? ghi log c?nh b?o; tuy?t ??i kh?ng retry t?c ??ng ph? m? qu?ng v? kh?ng t? ? k?t lu?n th?nh c?ng; ch? ti?p t?c khi c? b?ng ch?ng |
| `TST-SRC-RACE-001` | Candidate ? tr?ng th?i `READY`, ngu?n active/disabled c?ng ??nh danh canonical ???c ??ng k? tr??c | Tr? v? `MATCHED_EXISTING` g?n v?i ref hi?n c?; kh?ng t?o th?c th? `Source` m?i; ??m b?o t?nh nh?t qu?n gi?a candidate, receipt v? outbox |
| `TST-SRC-RACE-002` | Hai ti?n tr?nh ??ng th?i: m?t ??ng k? candidate, m?t x?a ngu?n (`RemoveSource`) v?i c? 2 th? t? commit | `SourceTombstone` cu?i c?ng ???c b?o to?n; n?u l?nh x?a th?ng th? candidate b? chuy?n sang `BLOCKED_TOMBSTONE`; kh?ng x?y ra t?nh tr?ng ngu?n h?i sinh tr?i ph?p |
| `TST-SRC-RACE-003` | Candidate ??t `READY` nh?ng policy thay ??i c?m, thi?u policy ho?c expected revision b? c? | Tr? v? t??ng ?ng: `REJECTED`, `READY` (v?i `WAITING_POLICY`), ho?c `REVISION_CONFLICT`; kh?ng t? ??ng k?ch ho?t ngu?n, kh?ng ph?t event resolved khi c?n ch? |
| `TST-SRC-RACE-004` | Giao d?ch ??ng k? commit th?nh c?ng nh?ng b? m?t g?i tin ACK; client g?i l?i c?ng idempotency key | Tr? v? ??ng receipt v? disposition ?? commit tr??c ??; kh?ng t?o th?m th?c th? `Source` hay outbox event tr?ng l?p; n?u thay ??i payload th? b?o l?i idempotency conflict |
| `TST-COL-PKG-001` | Payload thi?u tr??ng b?t bu?c (ID, source ref, run ref, provenance chain); client l?p l?i payload sai | B? t? ch?i ngay t?i bi?n A v?i `VALIDATION_ERROR`; kh?ng chuy?n giao sang B; ghi nh?n quan s?t l?i v?i correlation ID an to?n, kh?ng gi? m?o provenance |
| `TST-COL-PKG-002` | Tr?ch xu?t g?p l?i ho?c n?i dung b?i vi?t r?ng (`empty text`) nh?ng schema v? provenance ??y ?? | L?u package v?i `content_eligibility = "incomplete"` k?m l? do; B ti?p nh?n v? tr? `REJECTED_INCOMPLETE`; kh?ng t?nh v?o tin m?i |
| `TST-COL-PKG-003` | C?u h?nh ngu?n y?u c?u b?t bu?c title vs c?u h?nh ngu?n cho ph?p thi?u title | Th?m ??nh theo ??ng c?u h?nh lo?i ngu?n trong revision policy; kh?ng m?c ??nh ngu?n m?ng x? h?i ph?i c? title ri?ng |
| `TST-COL-PKG-004` | Thi?u policy lo?i ngu?n; fetch th?t b?i khi ch?a t?o ???c package | B?o l?i `INPUT_NOT_READY` khi thi?u policy; fetch th?t b?i ch? ghi nh?n quan s?t l??t qu?t v? x? l? run theo CT-STATE-002, kh?ng t?o package r?c |

---

### 2.2. Nh?m B?t Bi?n C?t L?i (Core Invariants & Rules)

| M? Ki?m Th? | Invariant / Rule | M?c ti?u ki?m ch?ng | Oracle b?t bu?c |
|---|---|---|---|
| `TST-INT-INV-015` | `INV-015` | X?a ngu?n r?i auto-discovery qu?t l?i ??ng URL ?? | Ngu?n v?n ? tr?ng th?i `REMOVED_TOMBSTONE`; auto-discovery b? ch?n, tr? v? `BLOCKED_TOMBSTONE` |
| `TST-SEC-INV-020` | `INV-020` | D? li?u b?i vi?t/HTML ch?a c?u l?nh ??c h?i gi? m?o h??ng d?n h? th?ng (prompt injection) | Kh?ng l?m thay ??i ch?nh s?ch thu th?p, kh?ng k?ch ho?t tool ?n, d? li?u ???c escape/sanitize an to?n |
| `TST-RULE-A001` | `A-RULE-001` | M?i thao t?c s?a ??i ngu?n ph?i c? idempotency key v? expected revision | Tr?ng idempotency key tr? l?i receipt c?; sai expected revision tr? v? `REVISION_CONFLICT` |
| `TST-RULE-A004` | `A-RULE-004` | M?t ngu?n qu?t ??nh k? t?i ?a 1 l?n trong c?ng `business_date` | L??t qu?t th? hai trong ng?y v?i purpose `periodic` b? t? ch?i v?i l? do `ALREADY_RUN_TODAY` |
| `TST-RULE-A013` | `A-RULE-013` | Fetch HTTP(S) b?t bu?c ki?m tra SSRF t?i m?i b??c chuy?n h??ng (redirect) | Ch?n ngay l?p t?c n?u redirect tr? v? IP n?i b? ho?c loopback |
| `TST-RULE-A014` | `A-RULE-014` | Secret / token kh?ng bao gi? xu?t hi?n trong log, event payload ho?c database | Ki?m tra b? l?c d? li?u nh?y c?m (sanitizer) l?c s?ch 100% header Authorization, token |

---

### 2.3. Nh?m Ph?ng Th? Bi?n B?o M?t Thu Th?p (SSRF Defense Suite)

| M? Ki?m Th? | T?nh hu?ng t?n c?ng (Attack Vector) | Oracle b?o m?t b?t bu?c |
|---|---|---|
| `TST-SEC-SSRF-001` | URL ch?a ??a ch? Loopback (`http://127.0.0.1`, `http://localhost`, `http://[::1]`) | N?m l?i `SSRFSecurityViolationError`, t? ch?i k?t n?i fail-closed |
| `TST-SEC-SSRF-002` | URL ch?a d?i m?ng ri?ng t? RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) | N?m l?i `SSRFSecurityViolationError`, kh?ng g?i request ra card m?ng |
| `TST-SEC-SSRF-003` | URL tr? t?i d?ch v? metadata m?y ch? ??m m?y (`http://169.254.169.254/...`) | N?m l?i `SSRFSecurityViolationError`, ghi log vi ph?m b?o m?t |
| `TST-SEC-SSRF-004` | T?n c?ng DNS Rebinding (DNS tr? IP c?ng c?ng ? l?n ph?n gi?i ??u nh?ng tr? IP n?i b? ? l?n hai) | Th?m tra IP ngay tr??c khi m? socket k?t n?i th?c s? (`pre-connect IP check`), ch?n ??ng k?t n?i |
| `TST-SEC-SSRF-005` | Giao th?c kh?ng ph?i HTTP/HTTPS (`file:///etc/passwd`, `gopher://`, `ftp://`) | N?m l?i `UnsupportedSchemeError`, ch? cho ph?p `http` v? `https` |

---

## 3. Ma Tr?n Ph?n R? G?i C?ng Vi?c (Work Packages A0..A7)

```
A0 (Contract & Fixtures)
 ??? A1 (Source Domain & Lifecycle)
 ??? A2 (CollectionRun & Checkpoint Core)
 ??? A3 (SSRF Fetch & Adapters) ?? A4 (Extraction & Package Builder)
                                      ??? A5 (Periodic Tier Workflow)
                                           ??? A6 (Supplemental & Auto-Discovery)
                                                ??? A7 (UI & Hardening)
```

| G?i | N?i dung th?c thi ch?nh | T?p tin ki?m th? m?c ti?u (Targeted Test File) | L?nh ch?y ki?m th? m?c ti?u |
|---|---|---|---|
| `A0` | ??ng contract, validate schema JSON v? chu?n b? fixtures | `tests/unit/collection/test_a0_contract_fixtures.py` | `python -m unittest tests/unit/collection/test_a0_contract_fixtures.py` |
| `A1` | Source aggregate, v?ng ??i CT-STATE-001, idempotency | `tests/unit/collection/test_a1_source_lifecycle.py` | `python -m unittest tests/unit/collection/test_a1_source_lifecycle.py` |
| `A2` | CollectionRun, attempt, checkpoint CT-STATE-002 | `tests/unit/collection/test_a2_run_checkpoints.py` | `python -m unittest tests/unit/collection/test_a2_run_checkpoints.py` |
| `A3` | SSRF guard, HTTP client, RSS parser adapter | `tests/unit/collection/test_a3_secure_fetch.py` | `python -m unittest tests/unit/collection/test_a3_secure_fetch.py` |
| `A4` | Tr?ch xu?t n?i dung, Package builder, Outbox handoff | `tests/unit/collection/test_a4_package_builder.py` | `python -m unittest tests/unit/collection/test_a4_package_builder.py` |
| `A5` | L?p l?ch cycle ??nh k?, ?i?u ph?i theo Tier | `tests/unit/collection/test_a5_tier_workflow.py` | `python -m unittest tests/unit/collection/test_a5_tier_workflow.py` |
| `A6` | T?m ki?m b? sung, auto-discovery candidate CT-STATE-002A | `tests/unit/collection/test_a6_candidate_discovery.py` | `python -m unittest tests/unit/collection/test_a6_candidate_discovery.py` |
| `A7` | Projections cho UI Admin, SSE stream, hardening & gate G06 | `tests/integration/collection/test_a7_acceptance_gate.py` | `python -m unittest tests/integration/collection/test_a7_acceptance_gate.py` |

---

## 4. Ki?m Th? H?i Quy To?n H? Th?ng (Regression Invariants)

B?t k? thay ??i n?o trong Ph?n h? A c?ng b?t bu?c ph?i v??t qua c?c b?i ki?m th? h?i quy:
1. **Ki?m tra h?i quy Milestone M1:**
   - ??m b?o 93/93 b?i test M1 ??t `PASS` (`93 passed, 0 skipped`).
2. **Ki?m tra h?i quy Milestone M2:**
   - B? ki?m th? `tests/m2/**` ??t `PASS`.
   - Admin UI build s?ch s?, kh?ng c? trailing whitespace.
3. **Qu?t d? li?u nh?y c?m (Secret Scanner):**
   - Kh?ng ch?a b?t k? kh?a b? m?t, private key, token d?ng plain-text n?o trong m? ngu?n v? d? li?u test fixture.

---

## 5. B?ng Ch?ng Nghi?m Thu C?n Sinh Ra (Required Evidence Artifacts)

Khi m?t g?i c?ng vi?c ho?c to?n b? M3-A ho?n t?t, h? s? nghi?m thu b?t bu?c ph?i ch?a c?c t?p tin c? m? b?m x?c th?c:

```
docs/milestones/m3-collection/evidence/m3-a/
 ??? red-observations.md       # Quan s?t b?ng ch?ng c?c test b? fail tr??c khi code
 ??? targeted-test-report.txt  # K?t qu? ch?y b? targeted test sau khi ho?n thi?n code
 ??? m1-regression-report.txt  # B?o c?o 93/93 tests M1 ??t GREEN
 ??? secret-scan.json          # B?o c?o qu?t 0 credentials
 ??? hashes.sha256             # B?ng b?m SHA-256 to?n v?n c?a m?i artifacts
 ??? status.json               # Tr?ng th?i m?y ??c: {"status": "PASS", "gate": "G06"}
```

---

## 6. Ti?u Ch? Ho?n Th?nh (Definition of Done)

G?i c?ng vi?c Ph?n h? A ch? ???c xem l? ho?n t?t khi:
1. 100% c?c b?i ki?m th? unit v? integration t??ng ?ng ??t `GREEN`.
2. Kh?ng vi ph?m b?t k? invariant n?o (`INV-015`, `INV-020`, `A-RULE-001..016`).
3. 100% c?c ca ki?m th? SSRF ??t chu?n an to?n tuy?t ??i.
4. Ki?m th? h?i quy M1 v? M2 ??t `PASS` 100%.
5. C?y l?m vi?c git s?ch s? (`git diff --check` kh?ng c? trailing whitespace ho?c CRLF).
6. Sol-Lead review read-only g?i `ACCEPT`.
7. Astra-Lead supreme audit read-only g?i `PASS`.
