# Bảo mật, hiệu năng, evidence và phục hồi

> **Trạng thái:** `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`

## 1. Bảo mật mặc định

Mọi task fail closed và chỉ có quyền tối thiểu theo execution envelope.

- Worktree, branch, path allowlist và resource lease cô lập task.
- An toàn đường dẫn: Đường dẫn trong `owned_paths`, `forbidden_paths` và lease bắt buộc là đường dẫn tương đối chuẩn tắc từ gốc repository. Nghiêm cấm đường dẫn tuyệt đối, path traversal (`..`), alias chuẩn tắc (`./`, `//`, `\`); vi phạm bị từ chối fail-closed.
- Bất biến evidence lịch sử: Tệp trong `docs/milestones/**/evidence/**` là bất biến, không thể xin mutation lease; mọi sai lệch hash đều chặn merge.
- Fencing token và hết hạn lease: Mọi lease cấp phát mang fencing token tăng đơn điệu; lock dạng capacity được phân tách theo từng live allocation slot độc lập (`LOCK_ID:slot_N`) để cô lập token giữa các worker đồng thời; kết quả mang token cũ hoặc sau khi lease hết hạn bị chặn fail-closed.
- Đóng toàn bộ mutation lease sau `worker_done`: Khi worker hoàn tất thành công (`succeeded`), toàn bộ lease ghi/mutation bị đóng lập tức; reviewer kiểm tra candidate ở trạng thái read-only.
- Bất biến định danh Orca và Dispatch: Cấm tái sử dụng Orca task ID hoặc dispatch ID trên toàn hệ thống; cấm ghi đè dispatch binding.
- Browser/desktop/API giữ Host, Origin, CSRF và local HTTPS boundary theo contract hiện hành.
- URL/path từ nguồn ngoài được xem là dữ liệu không tin cậy; chống SSRF, redirect abuse, path traversal và shell injection.
- Nội dung web, metadata, OCR, prompt hoặc artifact không bao giờ là instruction hệ thống hay authority.
- Secret chỉ tồn tại sau boundary của J/secret store. Event, log, trace, UI, Problem Detail, evidence, prompt và workflow history không chứa secret value.
- Fixture/evidence không dùng production credential hoặc dữ liệu cá nhân.
- External account chỉ dùng đúng role; quota chưa biết không được coi là vô hạn.
- Không commit token, DSN, credential, unredacted log hoặc media không rõ quyền.
- Không dùng mock để tuyên bố Drive/OAuth/Temporal/model AI/render/restore gate PASS.
- Dependency dùng exact pin trong lock có thẩm quyền; cấm `latest`, caret và tilde.

### Gate bảo mật theo task

1. threat/scope inventory;
2. static secret/canary scan;
3. malicious URL/path/payload fixtures;
4. workspace/tenant isolation;
5. log/event/history/UI redaction;
6. transport/Host/Origin/CSRF khi API/UI thay đổi;
7. real external proof khi claim external gate;
8. independent review trên exact candidate.

Finding về secret, path escape, SSRF, authorization hoặc data loss chặn merge và descendant.

### Phân biệt Fallback Sản Phẩm và Delivery Control Plane

- **Sản phẩm (Product Roadmap)**: Việc chuyển đổi/fallback giữa các AI provider (ví dụ Deepgram/Whisper/Google Cloud) trong pipeline sản xuất video là tính năng sản phẩm được thiết kế có kiểm soát.
- **Delivery Control Plane**: Trong hệ thống điều phối phát triển song song (Dely / Orca), chính sách định tuyến fail-closed tại `AGENTS.md` NGHIÊM CẤM TUYỆT ĐỐI mọi hình thức fallback giữa các agent-harness, provider, model hay account pool (đặc biệt cấm Antigravity native). Thiếu hoặc có mâu thuẫn bằng chứng định tuyến/thực thi là điều kiện hard STOP, không được phép fallback.

## 2. Hiệu năng và capacity

Mục tiêu sản phẩm giữ nguyên:

- `QR-PERF-001`: tối thiểu 100 video hợp lệ trong 12 giờ;
- `QR-REL-007`: ít nhất 95% video đủ đầu vào hoàn thành không cần thao tác sau khi bắt đầu lô;
- `QR-PERF-005`: 95% thao tác UI thường có phản hồi hữu ích trong 2 giây;
- `QR-PERF-006`: command acknowledgment trong 1 giây;
- `QR-COST-001`: chi phí phát sinh dưới 50 USD/tháng;
- `QR-COST-003`: cảnh báo trước khi forecast vượt 80% ngân sách.

Parallel delivery không phải bằng chứng đạt các mục tiêu này. Agent concurrency không được đánh đồng với pipeline throughput.

### Capacity admission

- Lock runtime có capacity token rõ thay vì “máy còn rảnh” mơ hồ.
- CPU/GPU/VRAM, PostgreSQL connection/DB, external account/quota và evidence writer được admission riêng.
- Không oversubscribe GPU hoặc external account bằng cách chạy wave lớn hơn quan sát thực tế.
- Task performance phải pin hardware, dataset, config, versions, warm/cold state và sample duration.
- p95/ratio phải được tính từ raw observations; không copy số thủ công vào status.
- Wait time dependency, lock, external provider và execution phải tách riêng.
- Khi benchmark fail, tối ưu bottleneck/re-plan; không hạ threshold hoặc bỏ hard gate.

## 3. Test-first và acceptance evidence

Chu kỳ bắt buộc:

```text
Contract/requirement → test → discriminating RED
→ implementation → GREEN → regression → evidence
```

Một acceptance row gồm requirement, instrument, counterexample “implementation hiện diện nhưng sai”, RED observation và limitation. RED vì import/setup/binary thiếu không hợp lệ. Với docs/config, parser/link/schema/diff fixture có thể là instrument; human inspection phải ghi giới hạn khi không tự động hóa được.

Test lifecycle giữ nguyên: `DRAFT`, `REVIEWED`, `READY_FOR_RED`, `RED_CONFIRMED`, `GREEN`, `BLOCKED_EXTERNAL`, `QUARANTINED`, `RETIRED`. Thiếu evidence là `NOT_PROVEN`; không có conditional pass.

## 4. Evidence protocol

Mỗi run có thư mục riêng và tối thiểu:

```text
status.json              # machine authority
status.md                # derivative
commands.jsonl           # command/result/provenance
runtime.json              # versions, platform, hardware/capability
scope.json                # base/candidate/owned/changed paths
tests/*.xml|json          # raw observations
secret-scan.json
review.json
hashes.sha256             # hash DAG, không hash chính nó
```

Quy tắc:

- `status.json` sinh từ artifact quan sát, không nhập số liệu thủ công;
- provenance nối run ID, task/dispatch ID, base/candidate SHA, tool/runtime và timestamp;
- manifest liệt kê toàn bộ file bắt buộc 1:1;
- hash dùng SHA-256 và có tamper-negative proof;
- accepted evidence immutable và source-bound;
- rejected candidate giữ lịch sử, không đổi thành accepted;
- evidence task và integration tách path/single writer;
- log phải redacted trước khi lưu;
- không ghi credential/env value nhạy cảm vào command transcript.

## 5. Failure, retry và reconciliation

Retry không thay failure handling.

- Side effect dùng stable operation ID, idempotency key, receipt, generation/recovery epoch và fencing token.
- Timeout trước/giữa external call tạo `OUTCOME_UNKNOWN`; reconcile theo provider/receipt trước retry.
- Retry kỹ thuật giữ logical input/config; tạo biến thể là command nghiệp vụ khác.
- Old generation, recovery epoch hoặc fencing token không mutation state.
- Duplicate message/event/result được dedupe nhưng vẫn có trace.
- Terminal state không được mở lại; correction tạo fact/revision mới theo contract.
- Một job lỗi không dừng job độc lập; lỗi shared resource tạo admission block quan sát được.
- Không xóa output/local bytes trước verified cloud sync và cleanup authorization.

## 6. Recovery của delivery control

| Sự cố | Hành động |
|---|---|
| Control restart | Đọc Orca run/task/message cursor, Git candidate, lock ledger; không suy từ terminal |
| Worker mất | Stop/release theo Orca, expire lease, fence result cũ, dispatch mới nếu authority còn |
| Heartbeat quá hạn | Block task, không tự nhận partial output, reconcile resource |
| Lock ledger/worker lệch | Fail closed, freeze affected resources, audit trước cấp lease mới |
| Merge bị gián đoạn | Kiểm current HEAD/index/queue receipt rồi resume hoặc rollback idempotent |
| External outcome unknown | Reconcile bằng operation receipt/provider state; không retry mù |
| Evidence synthesis gián đoạn | Bỏ run chưa finalized hoặc resume theo manifest protocol; không sửa accepted run |
| Contract đổi giữa task | Mark dependent `needs_replan`, issue exact revision mới |
| Security incident | Stop descendants, preserve redacted forensic refs, rotate/contain bởi owner có quyền |
| Harness tool namespace collapse | Kích hoạt STOP condition, đánh dấu `blocked_harness`, giải phóng và fence lease an toàn, chuyển task sang `blocked` không có mutation; nghiêm cấm tuyệt đối fallback sang Antigravity native |
| Duplicate dispatch / ID reuse | Fail-closed, từ chối ghi đè binding, bắt buộc cấp fresh dispatch ID và Orca task ID mới |
| Capacity slot stale token | Bị fence bởi bộ đếm monotonic slot độc lập, thu hồi slot và cấp token mới |

## 7. Backup và rollback

Reference trước thí nghiệm:

`D:/AI_SETUP/backups/AI-Auto-Video-Creator/20260928-175542`

Trình tự an toàn:

1. dừng writer và ghi current candidate;
2. kiểm backup metadata/checksum/provenance;
3. xác định exact docs/config cần restore;
4. không chép secret hoặc evidence lịch sử từ backup không xác minh;
5. restore vào worktree cách ly hoặc dùng Git revert;
6. chạy encoding/schema/link/authority/secret validation;
7. review diff;
8. commit rollback riêng nếu được cấp quyền.

Bản backup này không tạo claim G05. Product DB/workflow/artifact restore vẫn cần test hạ tầng thật và gate riêng.

## 8. M? h?nh ?e d?a (Threat Model) v? Ranh gi?i tin c?y Ngo?i ti?n tr?nh (Out-of-Process Trust Boundary)

### 8.1. M? h?nh ?e d?a 3 t?ng r?i ro (Threat Model Risk Tiers)

?? gi?i quy?t tri?t ?? nguy?n nh?n g?c r? (root cause) c?a finding audit trust boundary t? Sol (trong ?? caller c? th? t? bootstrap authority trong c?ng ti?n tr?nh Python th?ng qua reflection, secret constructor, ho?c monkey-patching), h? th?ng thi?t l?p m? h?nh ?e d?a 3 t?ng r? r?t:

1. **T?ng 1 - S?a nh?m th?ng th??ng (Accidental Drift / Misconfiguration)**:
   - Worker ho?c developer v? ? g?i nh?m API, truy?n thi?u tham s?, s? d?ng sai schema, nh?m l?n commit SHA ho?c dispatch ID.
   - C? ch? ph?ng v?: Strict dataclass validation, ki?u d? li?u kh?ng c? kho?ng tr?ng th?a, schema assertion, ki?m tra t?nh to?n v?n commit trong Git v? ki?m tra h?p ??ng ph?n nh?nh.

2. **T?ng 2 - Candidate / Worker kh?ng tin c?y (Hostile / Compromised Candidate Worker)**:
   - Worker ch?y m? Python t?y ? trong m?i tr??ng candidate, c? kh? n?ng s?a ??i to?n b? m? ngu?n candidate, ??c m?i t?p tin m? phi?n l?m vi?c ???c c?p quy?n, can thi?p v?o b? nh? Python runtime (monkey-patching, inspect call stack, subclassing, ghi ?? global registry, forge HMAC secret n?u n?m c?ng b? nh?).
   - Nguy?n t?c b?t bi?n: **Kh?ng m?t ??i t??ng, secret, identifier, t?n module, class, underscore private, closure, UUID, hay l?i khai t? nh?n n?o trong c?ng ti?n tr?nh c?a worker ???c coi l? b?ng ch?ng danh t?nh ho?c th?m quy?n**.
   - Quy?n quy?t ??nh ph? duy?t (verdict) v? quy?n t?ch h?p/merge ???c t?ch bi?t ho?n to?n kh?i ti?n tr?nh worker.

3. **T?ng 3 - Quy?n Qu?n tr? vi?n To?n quy?n c?a Host (Host Operating System Administrator)**:
   - Ng??i d?ng ho?c ti?n tr?nh ch?y v?i quy?n Administrator/root to?n m?y c? th? can thi?p tr?c ti?p v?o kernel, debug memory, ghi ?? ? ??a v?t l? ho?c s?a ??i registry c?a h? th?ng.
   - Tuy?n b? an ninh: **Ki?n tr?c ?ng d?ng v? sandbox ti?n tr?nh KH?NG tuy?n b? ng?n c?n ???c Administrator to?n quy?n c?a Host OS**. Vi?c c?ch ly ch?ng l?i r?i ro n?y b?t bu?c ph?i d?a tr?n ph?n quy?n t?i kho?n h? ?i?u h?nh ??c l?p (OS User Isolation), m?y ch? CI/CD bi?t l?p (Dedicated Runner) ho?c m?y ?o c?ch ly ph?n c?ng.

### 8.2. Ph?n t?ch ph??ng ?n ki?n tr?c & Quy?t ??nh (Architectural Decision Record - ADR)

??nh gi? 3 ph??ng ?n kh? thi ?? gi?i quy?t b?i to?n ranh gi?i tin c?y:

| Ti?u ch? | Ph??ng ?n 1: Reference Model + Manual External Gate | Ph??ng ?n 2: Broker ??c L?p + Ch? K? B?t ??i X?ng + OS ACL (???c ch?n) | Ph??ng ?n 3: N?n t?ng CI/CD / Isolated Runner Ho?n Ch?nh |
| :--- | :--- | :--- | :--- |
| **B?n ch?t** | Ch? gi? m? m?u, to?n b? gate chuy?n th?nh ki?m duy?t th? c?ng ngo?i h? th?ng | T?ch vai tr? Reviewer Lead v? Integration Gatekeeper, s? d?ng c?p kh?a b?t ??i x?ng Ed25519; worker ch? gi? pinned public key; verifier ch?y ??c l?p | Tri?n khai c?m server runner t? ??ng h?a ho?n to?n v?i m?y ?o ho?c container ??c l?p |
| **Kh? n?ng t??ng th?ch** | Ho?n to?n t??ng th?ch nh?ng kh?ng t? ??ng h?a ???c quy tr?nh delivery | Ho?n to?n t??ng th?ch m?i tr??ng Windows hi?n t?i m? kh?ng c?n c?i ??t h? t?ng ph?c t?p | ??i h?i h? t?ng m?y ch?, d?ch v? m?ng b?n ngo?i, v??t qu? ph?m vi d? ?n hi?n t?i |
| **M?c ?? an to?n** | Fail-closed tuy?t ??i nh?ng ph? thu?c 100% v?o thao t?c th? c?ng | ??m b?o t?nh to?n h?c m?t m? b?t ??i x?ng; worker kh?ng th? gi? m?o ch? k? d? ki?m so?t to?n b? runtime Python | C?ch ly v?t l?/OS m?nh nh?t |
| **Quy?t ??nh** | D?ng l?m c? ch? kh?a k?ch ho?t (`PRODUCTION_ACTIVATION_BLOCKED`) khi ch?a ?? ?i?u ki?n h? t?ng | **???C CH?N L?M KI?N TR?C M?C TI?U**: Tri?n khai ??y ?? adapter, Signed Envelope, Keystore, v? Durable Consumption Registry | Ghi nh?n trong l? tr?nh n?ng c?p d?i h?n (Long-term Infrastructure Roadmap) |

### 8.3. Thi?t k? Ranh gi?i tin c?y ??c l?p & Ch? k? M?t m? B?t ??i x?ng (Ed25519)

1. **Qu?n l? Kh?a B?t ??i x?ng (Out-of-Process Key Custody & TrustedKeyStore)**:
   - Private signing keys tuy?t ??i kh?ng ???c l?u tr? trong repository, bi?n m?i tr??ng c?a worker, log, hay fixture ch?y c?ng ti?n tr?nh. Kh?a ri?ng ch? thu?c s? h?u c?a phi?n Reviewer ??c l?p (`rev_key_lead_v1`) v? Integration Runner ??c l?p (`integ_gatekeeper_v1`).
   - Candidate worker ch? ???c cung c?p danh s?ch public keys ghim s?n (`TrustedKeyStore.register_pinned_public_key`).
   - H? tr? c? ch? thu h?i kh?a t?c th?i (`revoke_key`): m?t phong b? k? b?i kh?a ?? thu h?i s? b? t? ch?i fail-closed ngay l?p t?c.

2. **Phong b? K? s? B?t ??i x?ng (SignedReviewEnvelope & SignedIntegrationEnvelope)**:
   - Ph?n t?ch mi?n k? (Domain Separation): `PARALLEL_DELIVERY_REVIEW_ENVELOPE_V1` v? `PARALLEL_DELIVERY_INTEGRATION_ENVELOPE_V1`.
   - Chu?n h?a chu?i d? li?u (Canonical Serialization): Tu?n th? RFC 8785, s?p x?p key nh?t qu?n, lo?i b? tr??ng signature tr??c khi k? v? b?m.
   - G?n ch?t ng? c?nh nhi?m v?: B?t bu?c ch?a ??y ?? `delivery_task_id`, `review_dispatch_id`, commit SHA ?ng vi?n ??y ?? (40 k? t? hex), base commit, route attestation (`cx/gpt-5.6-sol`), harness (`Claude Code`), s? ng?u nhi?n d?ng m?t l?n (`nonce`), th?i gian ph?t h?nh/h?t h?n (`issued_at`, `expires_at`), v? m? r?o monotonic (`fencing_token`).

3. **S? ??ng k? Ti?u th? B?n v?ng (DurableConsumptionRegistry)**:
   - L?u tr? nguy?n t? (atomic persistence) qua SQLite v? kh?a lu?ng.
   - Ch?ng t?n c?ng ph?t l?i (Replay Protection): B?t bu?c m?i envelope v? m?i nonce l? duy nh?t tr?n to?n h? th?ng; t?i s? d?ng l?p t?c b? t? ch?i v?i l?i `ReplayAttackError`.
   - Gi? v?ng tr?ng th?i qua kh?i ??ng l?i (Durability across restart): D? li?u ti?u th? v? s? fencing t?n t?i b?n v?ng tr?n ??a, ng?n ch?n vi?c restart ti?n tr?nh ?? l?ch lu?t.
   - Monotonic Fencing Token: B? ??m fencing token cho t?ng task ph?i t?ng ??n ?i?u; m?i token c? h?n ho?c b?ng gi? tr? ?? ghi nh?n ??u b? t? ch?i v?i `FencingViolationError`.
   - C?a s? th?i gian h?p l?: Phong b? ?? h?t h?n ho?c ph?t h?nh v??t tr??c th?i gian th?c (> 30s) ??u b? t? ch?i fail-closed.

4. **Lo?i b? Ho?n to?n Quy?n h?n C? trong Ti?n tr?nh (In-Process Deprecation)**:
   - `ReviewerHostIssuer`, `ReviewerHostHandoff`, v? `ReviewerSessionBoundary` ch? c?n vai tr? DTO m? ph?ng cho backward compatibility c?a test fixtures, kh?ng mang b?t k? th?m quy?n b?o m?t n?o trong m?i tr??ng production.
   - H?m kh?i t?o c?a `ReviewerHostIssuer` ???c b?o v? b?ng private sentinel token `_SENTINEL_HOST_TOKEN`, ng?n ch?n caller t?y ? t?o issuer trong ti?n tr?nh.

### 8.4. B?ng ??i chi?u ??ng to?n b? h? l?i (Root Cause Closure Matrix)

| H? l?i b?o m?t (Vulnerability Class) | Bi?u hi?n r?i ro c? (Observed Anti-Pattern) | Gi?i ph?p Ki?n tr?c Out-of-Process (Root Cause Remediation) | Tr?ng th?i ki?m ch?ng (Verification Status) |
| :--- | :--- | :--- | :--- |
| **1. Identity Bootstrap** | Worker t? t?o issuer capability, kh?i t?o `ReviewerHostIssuer`, ho?c import fixture ?? t? c?p quy?n review | Private sentinel token c?m t?o in-process; th?m quy?n ch? ???c c?p qua ch? k? Ed25519 t? trusted keypair ??c l?p | **CLOSED** (`test_01`, `test_02`) |
| **2. Key Custody** | HMAC secret n?m trong bi?n m?i tr??ng ho?c b? nh? ti?n tr?nh worker, worker ??c ???c secret ?? t? k? | Kh?a k? b?t ??i x?ng (Ed25519 private key) n?m ngo?i t?m ki?m so?t c?a worker; candidate ch? ch?a pinned public keys | **CLOSED** (`test_03`, `test_04`) |
| **3. Verifier Ownership** | To?n b? verifier ch?y trong c?ng Python runtime c?a candidate; worker c? th? monkey-patch class ho?c bypass logic ki?m tra | Ph?n t?ch vai tr? r? r?ng: worker ch? n?p artifact/request; `TrustedReviewConsumer` v? `TrustedIntegrationConsumer` x?c minh d?a tr?n pinned keys ??c l?p | **CLOSED** (`test_02`, `test_09`) |
| **4. Replay & Fencing** | Worker g?i l?i k?t qu? review c? c?a task kh?c, d?ng l?i dispatch, ho?c restart ti?n tr?nh ?? x?a b? nh? cache | `DurableConsumptionRegistry` l?u SQLite b?n v?ng, ki?m tra nonce duy nh?t, monotonic fencing token t?ng d?n, temporal expiry window | **CLOSED** (`test_05`, `test_06`, `test_07`) |
| **5. Merge Authority** | Worker t? g?i transition sang `integrated` ho?c t? merge m? ngu?n v?o nh?nh ch?nh | Ch? `TrustedIntegrationConsumer` v?i phong b? h?p l? m?i cho ph?p ho?n t?t integration gate; worker ch? c? quy?n push feature branch | **CLOSED** (`test_08`, `test_10`) |

### 8.5. Kh?a k?ch ho?t Production & Danh m?c ?i?u ki?n ti?n quy?t (Prerequisites & Runbook)

H? th?ng ph?n ??nh r?ch r?i 3 tr?ng th?i c?a ki?n tr?c:
1. `ARCHITECTURE_IMPLEMENTED`: To?n b? l?p ki?n tr?c, data contract, validator, v? signed envelope ?? ???c hi?n th?c h?a ??y ?? trong code.
2. `REFERENCE_TESTED`: To?n b? 10/10 probe test negative/positive, m? ph?ng attacker monkey-patching, restart durability, v? fresh subprocess ?? v??t qua 100%.
3. `PRODUCTION_ACTIVATION_BLOCKED`: Tr?ng th?i k?ch ho?t production b? **KH?A CH?T (FAIL-CLOSED)** cho ??n khi to?n b? 4 ?i?u ki?n h? t?ng b?n d??i ???c cung c?p th?c t?.

#### Danh m?c ?i?u ki?n ti?n quy?t h? t?ng b?t bu?c (Infrastructure Prerequisites Inventory):
- `[ ]` **OS_USER_ISOLATION**: Thi?t l?p t?i kho?n d?ch v? h? ?i?u h?nh ri?ng bi?t (`pd_reviewer_service`, `pd_integration_service`) ho?n to?n ??c l?p v?i t?i kho?n ng??i d?ng c?a worker.
- `[ ]` **PRIVATE_KEY_ACL_RESTRICTION**: Thi?t l?p quy?n truy c?p t?p tin (NTFS ACL / POSIX permission) ?? ch? t?i kho?n d?ch v? ??c l?p m?i c? quy?n ??c private key Ed25519.
- `[ ]` **DEDICATED_RUNNER**: Thi?t l?p m?y ch? CI/CD runner bi?t l?p ch?y ngo?i m?y c?a developer/worker ?? th?c thi c?c gate t?ch h?p.
- `[ ]` **PROTECTED_BRANCH_POLICY**: C?u h?nh quy t?c b?o v? nh?nh ch?nh tr?n Git remote (ch?n push tr?c ti?p, b?t bu?c ch? k? m?t m?, b?t bu?c gate ki?m duy?t ngo?i ti?n tr?nh).

*Runbook k?ch ho?t*: Khi v? ch? khi 4 ?i?u ki?n ti?n quy?t tr?n ???c h? t?ng c?p ph?t v? nghi?m thu b?i m?t user checkpoint ri?ng bi?t, c? `ProductionActivationGate.STATUS` m?i ???c ph?p chuy?n t? `PRODUCTION_ACTIVATION_BLOCKED` sang `PRODUCTION_ACTIVE`.

---

## 9. STOP conditions chung

D?ng ngay task v? descendant khi:

- c? nguy c? m?t output ch?a sync;
- secret/cross-workspace data b? l?;
- path/URL kh?ng th? validate;
- contract owner/revision kh?ng r?;
- migration/rollback kh?ng an to?n;
- external outcome unknown ch?a reconcile;
- required runtime/provider unavailable;
- test oracle kh?ng ph?n bi?t ???c l?i;
- evidence provenance/hash kh?ng tin c?y;
- scope c?n authority m?i;
- mock l? b?ng ch?ng duy nh?t cho external claim;
- ranh gi?i tin c?y out-of-process b? can thi?p tr?i ph?p ho?c c? t?nh bypass `PRODUCTION_ACTIVATION_BLOCKED`;
- harness l?m s?p namespace c?ng c? (`functions.exec` -> `functions`) ho?c th?t b?i tool-execution smoke test.

Ghi STOP evidence v? h?i/re-plan; kh?ng ti?p t?c r?i s?a sau.
