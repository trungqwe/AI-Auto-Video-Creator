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

## 8. Mô hình đe dọa (Threat Model) và Ranh giới tin cậy Ngoài tiến trình (Out-of-Process Trust Boundary)

### 8.1. Mô hình đe dọa 3 tầng rủi ro (Threat Model Risk Tiers)

Để giải quyết triệt để nguyên nhân gốc rễ (root cause) của finding audit trust boundary từ Sol (trong đó caller có thể tự bootstrap authority trong cùng tiến trình Python thông qua reflection, secret constructor, hoặc monkey-patching), hệ thống thiết lập mô hình đe dọa 3 tầng rõ rệt:

1. **Tầng 1 - Sửa nhầm thông thường (Accidental Drift / Misconfiguration)**:
   - Worker hoặc developer vô ý gọi nhầm API, truyền thiếu tham số, sử dụng sai schema, nhầm lẫn commit SHA hoặc dispatch ID.
   - Cơ chế phòng vệ: Strict dataclass validation, kiểu dữ liệu không có khoảng trắng thừa, schema assertion, kiểm tra tính toàn vẹn commit trong Git và kiểm tra hợp đồng phân nhánh.

2. **Tầng 2 - Candidate / Worker không tin cậy (Hostile / Compromised Candidate Worker)**:
   - Worker chạy mã Python tùy ý trong môi trường candidate, có khả năng sửa đổi toàn bộ mã nguồn candidate, đọc mọi tệp tin mà phiên làm việc được cấp quyền, can thiệp vào bộ nhớ Python runtime (monkey-patching, inspect call stack, subclassing, ghi đè global registry, forge HMAC secret nếu nằm cùng bộ nhớ).
   - Nguyên tắc bất biến: **Không một đối tượng, secret, identifier, tên module, class, underscore private, closure, UUID, hay lời khai tự nhận nào trong cùng tiến trình của worker được coi là bằng chứng danh tính hoặc thẩm quyền**.
   - Quyền quyết định phê duyệt (verdict) và quyền tích hợp/merge được tách biệt hoàn toàn khỏi tiến trình worker.
   - Pinned public keys không thể được đăng ký, thay thế, hay sửa đổi bởi candidate worker trong cùng tiến trình; việc cấp phát khóa chỉ có thể diễn ra từ ranh giới máy chủ bên ngoài (host boundary).

3. **Tầng 3 - Quyền Quản trị viên Toàn quyền của Host (Host Operating System Administrator)**:
   - Người dùng hoặc tiến trình chạy với quyền Administrator/root toàn máy có thể can thiệp trực tiếp vào kernel, debug memory, ghi đè ổ đĩa vật lý hoặc sửa đổi registry của hệ thống.
   - Tuyên bố an ninh: **Kiến trúc ứng dụng và sandbox tiến trình KHÔNG tuyên bố ngăn cản được Administrator toàn quyền của Host OS**. Việc cách ly chống lại rủi ro này bắt buộc phải dựa trên phân quyền tài khoản hệ điều hành độc lập (OS User Isolation), máy chủ CI/CD biệt lập (Dedicated Runner) hoặc máy ảo cách ly phần cứng.

### 8.2. Phân tích phương án kiến trúc & Quyết định (Architectural Decision Record - ADR)

Đánh giá 3 phương án khả thi để giải quyết bài toán ranh giới tin cậy:

| Tiêu chí | Phương án 1: Reference Model + Manual External Gate | Phương án 2: Broker Độc Lập + Chữ Ký Bất Đối Xứng + OS ACL (Được chọn) | Phương án 3: Nền tảng CI/CD / Isolated Runner Hoàn Chỉnh |
| :--- | :--- | :--- | :--- |
| **Bản chất** | Chỉ giữ mã mẫu, toàn bộ gate chuyển thành kiểm duyệt thủ công ngoài hệ thống | Tách vai trò Reviewer Lead và Integration Gatekeeper, sử dụng cặp khóa bất đối xứng Ed25519; worker chỉ giữ pinned public key; verifier chạy độc lập | Triển khai cụm server runner tự động hóa hoàn toàn với máy ảo hoặc container độc lập |
| **Khả năng tương thích** | Hoàn toàn tương thích nhưng không tự động hóa được quy trình delivery | Hoàn toàn tương thích môi trường Windows hiện tại mà không cần cài đặt hạ tầng phức tạp | Đòi hỏi hạ tầng máy chủ, dịch vụ mạng bên ngoài, vượt quá phạm vi dự án hiện tại |
| **Mức độ an toàn** | Fail-closed tuyệt đối nhưng phụ thuộc 100% vào thao tác thủ công | Đảm bảo tính toán học mật mã bất đối xứng; worker không thể giả mạo chữ ký dù kiểm soát toàn bộ runtime Python | Cách ly vật lý/OS mạnh nhất |
| **Quyết định** | Dùng làm cơ chế khóa kích hoạt (PRODUCTION_ACTIVATION_BLOCKED) khi chưa đủ điều kiện hạ tầng | **ĐƯỢC CHỌN LÀM KIẾN TRÚC MỤC TIÊU**: Triển khai đầy đủ adapter, Signed Envelope, Keystore, và Durable Consumption Registry | Ghi nhận trong lộ trình nâng cấp dài hạn (Long-term Infrastructure Roadmap) |

### 8.3. Thiết kế Ranh giới tin cậy Độc lập & Chữ ký Mật mã Bất đối xứng (Ed25519)

1. **Qu?n l? Kh?a B?t ??i x?ng Ngo?i ti?n tr?nh (Out-of-Process Key Custody & TrustedKeyStore)**:
   - Private signing keys tuy?t ??i kh?ng ???c l?u tr? trong repository, bi?n m?i tr??ng c?a worker, log, hay fixture ch?y c?ng ti?n tr?nh. Kh?a ri?ng ch? thu?c s? h?u c?a phi?n Reviewer ??c l?p (`rev_key_lead_v1`) v? Integration Runner ??c l?p (`integ_gatekeeper_v1`).
   - C?p ph?t kh?a ngo?i ti?n tr?nh (Out-of-Process Pinned Key Provisioning): TrustedKeyStore ???c c?p ph?t b?t bi?n th?ng qua KeyStoreHostHandoff v? KeyStoreHostIssuer t? trusted external host boundary v?i unforgeable capability (KeyStoreHostIssuerCapability).
   - Pinned public keys ???c b?c trong MappingProxyType b?t bi?n.
   - Caller trong c?ng ti?n tr?nh (candidate worker) b? c?m g?i tr?c ti?p `register_pinned_public_key` (fail-closed v?i ProtocolViolationError), c?m kh?i t?o TrustedKeyStore v?i custom pinned keys, c?m thay th? hay s?a ??i c?c kh?a ?? ghim (Cannot replace or mutate existing pinned key authority), c?m t? bootstrap authority qua public host APIs (`get_default_host_issuer`, `issue_handoff`, `issue_isolated_keystore`, `provision_from_host`) khi kh?ng c? token m?y ch? `_SENTINEL_HOST_TOKEN`, v? c?m ti?m keystore t? ch?n v?o OrcaDeliveryAdapter.
   - H? tr? c? ch? thu h?i kh?a t?c th?i (`revoke_key`): m?t phong b? k? b?i kh?a ?? thu h?i s? b? t? ch?i fail-closed ngay l?p t?c.

2. **Phong b? K? s? B?t ??i x?ng (SignedReviewEnvelope & SignedIntegrationEnvelope)**:
   - Ph?n t?ch mi?n k? (Domain Separation): `PARALLEL_DELIVERY_REVIEW_ENVELOPE_V1` v? `PARALLEL_DELIVERY_INTEGRATION_ENVELOPE_V1`.
   - Chu?n h?a chu?i d? li?u (Canonical Serialization): Tu?n th? RFC 8785, s?p x?p key nh?t qu?n, lo?i b? tr??ng signature tr??c khi k? v? b?m.
   - G?n ch?t ng? c?nh nhi?m v?: B?t bu?c ch?a ??y ?? `delivery_task_id`, `review_dispatch_id`, commit SHA ?ng vi?n ??y ?? (40 k? t? hex), base commit, route attestation (`cx/gpt-5.6-sol`), harness (`Claude Code`), s? ng?u nhi?n d?ng m?t l?n (`nonce`), th?i gian ph?t h?nh/h?t h?n (`issued_at`, `expires_at`), v? m? r?o monotonic (`fencing_token`).

3. **S? ??ng k? Ti?u th? B?n v?ng (DurableConsumptionRegistry)**:
   - L?u tr? nguy?n t? (atomic persistence) qua SQLite v? kh?a lu?ng.
   - Ti?u th? phong b? t?ch h?p nguy?n t? (check_and_consume_integration): TrustedIntegrationConsumer.consume_integration_envelope b?t bu?c x?c th?c ch? k? v? ti?u th? nguy?n t? qua DurableConsumptionRegistry.check_and_consume_integration, ng?n ch?n t?nh tr?ng phong b? ?? k? ???c ch?p nh?n nhi?u l?n m? kh?ng ti?u th?.
   - Ch?ng t?n c?ng ph?t l?i (Replay Protection): B?t bu?c m?i envelope_id v? m?i `nonce` l? duy nh?t tr?n to?n h? th?ng; t?i s? d?ng l?p t?c b? t? ch?i v?i l?i ReplayAttackError.
   - Gi? v?ng tr?ng th?i qua kh?i ??ng l?i (Durability across restart): D? li?u ti?u th? v? s? fencing t?n t?i b?n v?ng tr?n ??a SQLite, ng?n ch?n vi?c restart ti?n tr?nh ?? l?ch lu?t. OrcaDeliveryAdapter m?c ??nh s? d?ng ???ng d?n SQLite b?n v?ng DEFAULT_PRODUCTION_CONSUMPTION_DB_PATH (`runtime/orca-consumption-registry.db`) ho?c `consumption_db_path` ???c ch? ??nh; c?m ti?m registry b? nh? t?m th?i (`:memory:`) fail-closed.
   - Monotonic Fencing Token: B? ??m fencing token cho t?ng task v? t?ng domain ph?i t?ng ??n ?i?u; m?i token c? h?n ho?c b?ng gi? tr? ?? ghi nh?n ??u b? t? ch?i v?i FencingViolationError.
   - C?a s? th?i gian h?p l?: Phong b? ?? h?t h?n (expires_at < current_time) ho?c ph?t h?nh v??t tr??c th?i gian th?c (> 30s) ??u b? t? ch?i fail-closed.
   - R?ng bu?c ??nh danh: B?t bu?c kh?p ch?nh x?c gi?a n?i dung phong b? v?i expected_task_id, expected_candidate, v? expected_base.

4. **Ki?m tra Ki?u D? li?u Nghi?m ng?t trong Phong b? (Strict Envelope Type Rejection)**:
   - `SignedIntegrationEnvelope.from_dict` v? `SignedReviewEnvelope.from_dict` th?c hi?n ki?m tra ki?u d? li?u nghi?m ng?t tr??c b?t k? coercion n?o: t? ch?i fail-closed `EnvelopeVerificationError` ??i v?i chu?i `'false'`, s? nguy?n, ho?c b?t k? ki?u phi-bool n?o ? tr??ng `gates_pass` v? `gate_results`.
   - C?c tr??ng `issued_at`, `expires_at`, `fencing_token` b?t bu?c ki?u s? h?c chu?n x?c, t? ch?i bool/str fail-closed.

5. **Lo?i b? Ho?n to?n Quy?n h?n C? trong Ti?n tr?nh (In-Process Deprecation)**:
   - ReviewerHostIssuer, ReviewerHostHandoff, v? ReviewerSessionBoundary ch? c?n vai tr? DTO m? ph?ng cho backward compatibility c?a test fixtures, kh?ng mang b?t k? th?m quy?n b?o m?t n?o trong m?i tr??ng production.
   - H?m kh?i t?o c?a ReviewerHostIssuer v? KeyStoreHostIssuer ???c b?o v? b?ng private sentinel token `_SENTINEL_HOST_TOKEN`, ng?n ch?n caller t?y ? t?o issuer trong ti?n tr?nh.

### 8.4. B?ng ??i chi?u ??ng to?n b? h? l?i (Root Cause Closure Matrix)

| H? l?i b?o m?t (Vulnerability Class) | Bi?u hi?n r?i ro c? (Observed Anti-Pattern) | Gi?i ph?p Ki?n tr?c Out-of-Process (Root Cause Remediation) | Tr?ng th?i ki?m ch?ng (Verification Status) |
| :--- | :--- | :--- | :--- |
| **1. Identity Bootstrap** | Worker t? t?o issuer capability, kh?i t?o ReviewerHostIssuer, ho?c import fixture ?? t? c?p quy?n review | Private sentinel token c?m t?o in-process; th?m quy?n ch? ???c c?p qua ch? k? Ed25519 t? trusted keypair ??c l?p | **CLOSED** (`test_01`, `test_02`) |
| **2. Key Custody & Provisioning** | Worker t? ??ng k? public key t?y ? v?o TrustedKeyStore.register_pinned_public_key, t? sinh keypair Ed25519 ?? k?, ho?c g?i public host API bootstrap in-process | Key custody chuy?n sang host boundary; c?p ph?t b?t bi?n qua KeyStoreHostHandoff v? KeyStoreHostIssuerCapability; to?n b? API public c?a host issuer y?u c?u `_SENTINEL_HOST_TOKEN`; in-process caller c?m ??ng k?/s?a/thay th?/bootstrap kh?a | **CLOSED** (`test_03`, `test_04`, `test_11`) |
| **3. Verifier Ownership** | To?n b? verifier ch?y trong c?ng Python runtime c?a candidate; worker c? th? monkey-patch class ho?c bypass logic ki?m tra | Ph?n t?ch vai tr? r? r?ng: worker ch? n?p artifact/request; TrustedReviewConsumer v? TrustedIntegrationConsumer x?c minh d?a tr?n pinned keys ??c l?p | **CLOSED** (`test_02`, `test_09`) |
| **4. Replay & Durable Consumption** | Worker g?i l?i k?t qu? review/integration c?, d?ng l?i nonce, adapter restart m?t cache :memory:, ho?c SignedIntegrationEnvelope kh?ng ???c ghi nh?n ti?u th? | DurableConsumptionRegistry l?u SQLite b?n v?ng, OrcaDeliveryAdapter d?ng DEFAULT_PRODUCTION_CONSUMPTION_DB_PATH, c?m :memory:, check_and_consume_integration nguy?n t? ki?m tra replay, nonce single-use, monotonic fencing, restart durability | **CLOSED** (`test_05`, `test_06`, `test_07`, `test_12`, `test_13`, `test_14`, `test_15`) |
| **5. Merge Authority** | Worker t? g?i transition sang integrated ho?c t? merge m? ngu?n v?o nh?nh ch?nh | Ch? TrustedIntegrationConsumer v?i phong b? h?p l? m?i cho ph?p ho?n t?t integration gate; worker ch? c? quy?n push feature branch | **CLOSED** (`test_08`, `test_10`) |
| **6. Strict Type Validation** | Payload phong b? ch?a chu?i 'false' b? ?p ki?u bool('false') == True, l?t qua gate ki?m duy?t | Strict type rejection trong from_dict t? ch?i chu?i, s? nguy?n v? ki?u kh?ng t??ng th?ch tr??c coercion | **CLOSED** (`test_16`) |

### 8.5. Kh?a k?ch ho?t Production & Danh m?c ?i?u ki?n ti?n quy?t (Prerequisites & Runbook)

H? th?ng ph?n ??nh r?ch r?i 3 tr?ng th?i c?a ki?n tr?c:
1. ARCHITECTURE_IMPLEMENTED: To?n b? l?p ki?n tr?c, data contract, validator, v? signed envelope ?? ???c hi?n th?c h?a ??y ?? trong code.
2. REFERENCE_TESTED: To?n b? 16/16 probe test negative/positive trong TestSolTrustBoundaryRootCauseRemediation (RED evidence, monkey-patching, ch? k? Ed25519, thu h?i kh?a, replay, restart SQLite, temporal validity, production gate fail-closed, fresh subprocess, positive control full lifecycle, key custody bootstrap prevention, integration durable consumption, restart durability, concurrency race, adapter restart SQLite durability, v? strict envelope type rejection) ?? v??t qua 100%.
3. PRODUCTION_ACTIVATION_BLOCKED: Tr?ng th?i k?ch ho?t production b? **KH?A CH?T (FAIL-CLOSED)** cho ??n khi to?n b? 4 ?i?u ki?n h? t?ng b?n d??i ???c cung c?p th?c t?.


#### Danh mục điều kiện tiên quyết hạ tầng bắt buộc (Infrastructure Prerequisites Inventory):
- [ ] **OS_USER_ISOLATION**: Thiết lập tài khoản dịch vụ hệ điều hành riêng biệt (pd_reviewer_service, pd_integration_service) hoàn toàn độc lập với tài khoản người dùng của worker.
- [ ] **PRIVATE_KEY_ACL_RESTRICTION**: Thiết lập quyền truy cập tệp tin (NTFS ACL / POSIX permission) để chỉ tài khoản dịch vụ độc lập mới có quyền đọc private key Ed25519.
- [ ] **DEDICATED_RUNNER**: Thiết lập máy chủ CI/CD runner biệt lập chạy ngoài máy của developer/worker để thực thi các gate tích hợp.
- [ ] **PROTECTED_BRANCH_POLICY**: Cấu hình quy tắc bảo vệ nhánh chính trên Git remote (chặn push trực tiếp, bắt buộc chữ ký mật mã, bắt buộc gate kiểm duyệt ngoài tiến trình).

*Runbook kích hoạt*: Khi và chỉ khi 4 điều kiện tiên quyết trên được hạ tầng cấp phát và nghiệm thu bởi một user checkpoint riêng biệt, cờ ProductionActivationGate.STATUS mới được phép chuyển từ PRODUCTION_ACTIVATION_BLOCKED sang PRODUCTION_ACTIVE.

---

## 9. STOP conditions chung

Dừng ngay task và descendant khi:

- có nguy cơ mất output chưa sync;
- secret/cross-workspace data bị lộ;
- path/URL không thể validate;
- contract owner/revision không rõ;
- migration/rollback không an toàn;
- external outcome unknown chưa reconcile;
- required runtime/provider unavailable;
- test oracle không phân biệt được lỗi;
- evidence provenance/hash không tin cậy;
- scope cần authority mới;
- mock là bằng chứng duy nhất cho external claim;
- ranh giới tin cậy out-of-process bị can thiệp trái phép hoặc cố tình bypass PRODUCTION_ACTIVATION_BLOCKED;
- harness làm sụp namespace công cụ (unctions.exec -> unctions) hoặc thất bại tool-execution smoke test.

Ghi STOP evidence và hỏi/re-plan; không tiếp tục rồi sửa sau.
