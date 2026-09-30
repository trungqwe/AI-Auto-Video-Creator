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

1. **Quản lý Khóa Bất đối xứng Ngoài tiến trình (Out-of-Process Key Custody & TrustedKeyStore)**:
   - Private signing keys tuyệt đối không được lưu trữ trong repository, biến môi trường của worker, log, hay fixture chạy cùng tiến trình. Khóa riêng chỉ thuộc sở hữu của phiên Reviewer độc lập (`rev_key_lead_v1`) và Integration Runner độc lập (`integ_gatekeeper_v1`).
   - Cấp phát khóa ngoài tiến trình (Out-of-Process Pinned Key Provisioning): TrustedKeyStore được cấp phát bất biến thông qua KeyStoreHostHandoff và KeyStoreHostIssuer từ trusted external host boundary với unforgeable capability (KeyStoreHostIssuerCapability).
   - Pinned public keys được bọc trong MappingProxyType bất biến.
   - Thẩm quyền host capability được quản lý nghiêm ngặt ngoài tiến trình thông qua HostBoundaryChannel độc lập (daemon chạy trong tiến trình con riêng biệt, trao đổi khóa qua private pipe và socket IPC cục bộ 127.0.0.1; không tin biến môi trường mutable `os.environ` hay inspect/module-name; cấp endpoint/auth qua HostBoundaryTicket bất biến có xác thực provenance, chữ ký HMAC và chống replay ngoài tiến trình).
   - Candidate module (`delivery_engine.py`) tuyệt đối không lưu trữ, không xuất và không rò rỉ bất kỳ sentinel token hay host capability nào trong module globals (loại bỏ hoàn toàn `_SENTINEL_HOST_TOKEN`).
   - Caller trong cùng tiến trình (candidate worker) bị cấm gọi trực tiếp `register_pinned_public_key` (fail-closed với ProtocolViolationError), cấm khởi tạo TrustedKeyStore với custom pinned keys, cấm thay thế hay sửa đổi các khóa đã ghim (Cannot replace or mutate existing pinned key authority), cấm tự bootstrap authority qua public host APIs (`get_default_host_issuer`, `issue_handoff`, `issue_isolated_keystore`, `provision_from_host`) khi không có host boundary capability hợp lệ, và cấm tiêm keystore tự chọn vào OrcaDeliveryAdapter.
   - Hỗ trợ cơ chế thu hồi khóa tức thời (`revoke_key`): một phong bì ký bởi khóa đã thu hồi sẽ bị từ chối fail-closed ngay lập tức.

2. **Phong bì Ký số Bất đối xứng (SignedReviewEnvelope & SignedIntegrationEnvelope)**:
   - Phân tách miền ký (Domain Separation): `PARALLEL_DELIVERY_REVIEW_ENVELOPE_V1` và `PARALLEL_DELIVERY_INTEGRATION_ENVELOPE_V1`.
   - Chuẩn hóa chuỗi dữ liệu (Canonical Serialization): Tuân thủ RFC 8785, sắp xếp key nhất quán, loại bỏ trường signature trước khi ký và băm.
   - Gắn chặt ngữ cảnh nhiệm vụ: Bắt buộc chứa đầy đủ `delivery_task_id`, `review_dispatch_id`, commit SHA ứng viên đầy đủ (40 ký tự hex), base commit, route attestation (`cx/gpt-5.6-sol`), harness (`Claude Code`), số ngẫu nhiên dùng một lần (`nonce`), thời gian phát hành/hết hạn (`issued_at`, `expires_at`), và mã rào monotonic (`fencing_token`).

3. **Sổ đăng ký Tiêu thụ Bền vững & Chống đầu độc Singleton (Durable Consumption Registry & Singleton Poisoning Prevention)**:
   - Lưu trữ nguyên tử (atomic persistence) qua SQLite và khóa luồng.
   - Tiêu thụ phong bì tích hợp nguyên tử (check_and_consume_integration): TrustedIntegrationConsumer.consume_integration_envelope bắt buộc xác thực chữ ký và tiêu thụ nguyên tử qua DurableConsumptionRegistry.check_and_consume_integration, ngăn chặn tình trạng phong bì đã ký được chấp nhận nhiều lần mà không tiêu thụ.
   - Chống tấn công phát lại (Replay Protection): Bắt buộc mỗi envelope_id và mỗi `nonce` là duy nhất trên toàn hệ thống; tái sử dụng lập tức bị từ chối với lỗi ReplayAttackError.
   - Giữ vững trạng thái qua khởi động lại (Durability across restart): Dữ liệu tiêu thụ và số fencing tồn tại bền vững trên đĩa SQLite, ngăn chặn việc restart tiến trình để lách luật. OrcaDeliveryAdapter mặc định sử dụng đường dẫn SQLite bền vững DEFAULT_PRODUCTION_CONSUMPTION_DB_PATH (`runtime/orca-consumption-registry.db`) hoặc `consumption_db_path` được chỉ định.
   - Chống đầu độc Singleton Ephemeral (Fail-Closed Ephemeral Poisoning): `DurableConsumptionRegistry.get_default` cấm tuyệt đối cấu hình `db_path=':memory:'` hoặc `allow_ephemeral=True` fail-closed với `ProtocolViolationError`. Nếu singleton instance bị can thiệp thành dạng ephemeral trong bộ nhớ, `OrcaDeliveryAdapter` từ chối khởi tạo fail-closed ngay lập tức.
   - Monotonic Fencing Token: Bộ đếm fencing token cho từng task và từng domain phải tăng đơn điệu; mọi token cũ hơn hoặc bằng giá trị đã ghi nhận đều bị từ chối với FencingViolationError.
   - Cửa sổ thời gian hợp lệ: Phong bì đã hết hạn (expires_at < current_time) hoặc phát hành vượt trước thời gian thực (> 30s) đều bị từ chối fail-closed.
   - Ràng buộc định danh: Bắt buộc khớp chính xác giữa nội dung phong bì với expected_task_id, expected_candidate, và expected_base.

4. **Kiểm tra Kiểu Dữ liệu Nghiêm ngặt trong Phong bì (Strict Envelope Type Rejection)**:
   - `SignedIntegrationEnvelope.from_dict` và `SignedReviewEnvelope.from_dict` thực hiện kiểm tra kiểu dữ liệu nghiêm ngặt trước bất kỳ coercion nào: từ chối fail-closed `EnvelopeVerificationError` đối với chuỗi `'false'`, số nguyên, hoặc bất kỳ kiểu phi-bool nào ở trường `gates_pass` và `gate_results`.
   - Các trường `issued_at`, `expires_at`, `fencing_token` bắt buộc kiểu số học chuẩn xác, từ chối bool/str fail-closed.

5. **Loại bỏ Hoàn toàn Quyền hạn Cũ trong Tiến trình (In-Process Deprecation)**:
   - ReviewerHostIssuer, ReviewerHostHandoff, và ReviewerSessionBoundary chỉ còn vai trò DTO mô phỏng cho backward compatibility của test fixtures, không mang bất kỳ thẩm quyền bảo mật nào trong môi trường production.
   - Hàm khởi tạo của ReviewerHostIssuer và KeyStoreHostIssuer được bảo vệ bằng out-of-process host boundary capability, ngăn chặn triệt để caller tùy ý tạo issuer trong tiến trình.

### 8.4. Bảng đối chiếu đóng toàn bộ hệ lỗi (Root Cause Closure Matrix)

| Hệ lỗi bảo mật (Vulnerability Class) | Biểu hiện rủi ro cũ (Observed Anti-Pattern) | Giải pháp Kiến trúc Out-of-Process (Root Cause Remediation) | Trạng thái kiểm chứng (Verification Status) |
| :--- | :--- | :--- | :--- |
| **1. Identity Bootstrap** | Worker tự tạo issuer capability, khởi tạo ReviewerHostIssuer, caller __main__ tự start host boundary, hoặc import fixture để tự cấp quyền review | Host capability chuyển hoàn toàn ra kênh ngoài tiến trình (HostBoundaryChannel daemon với HostBoundaryTicket); loại bỏ hoàn toàn việc tin tưởng biến môi trường mutable `os.environ` và inspect/module-name; thẩm quyền chỉ được cấp qua chữ ký Ed25519 từ trusted keypair độc lập | **CLOSED** (`test_01`, `test_02`, `test_11s`, `test_11t`, `test_11u`, `test_11v`, `test_17h`, `test_17i`, `test_17j`, `test_18`) |
| **2. Key Custody & Provisioning** | Worker tự đăng ký public key tùy ý vào TrustedKeyStore.register_pinned_public_key, tự sinh keypair Ed25519 để ký, hoặc tự đặt biến môi trường ORCA_HOST_BOUNDARY_TOKEN để bootstrap in-process | Key custody chuyển sang host boundary; cấp phát bất biến qua KeyStoreHostHandoff và KeyStoreHostIssuerCapability; kiểm chứng capability ủy thác 100% cho HostBoundaryChannel ngoài tiến trình; candidate worker cấm đăng ký/sửa/thay thế/bootstrap khóa và không thể giả mạo bằng cách tự set env hay bootstrap caller __main__; chặn đứng toàn bộ counterexample | **CLOSED** (`test_03`, `test_04`, `test_11`, `test_11s`, `test_11t`, `test_11u`, `test_11v`, `test_17h`, `test_17i`, `test_17j`, `test_18`) |
| **3. Verifier Ownership** | Toàn bộ verifier chạy trong cùng Python runtime của candidate; worker có thể monkey-patch class hoặc bypass logic kiểm tra | Phân tách vai trò rõ ràng: worker chỉ nộp artifact/request; TrustedReviewConsumer và TrustedIntegrationConsumer xác minh dựa trên pinned keys độc lập | **CLOSED** (`test_02`, `test_09`) |
| **4. Replay & Durable Consumption** | Worker gửi lại kết quả review/integration cũ, dùng lại nonce, adapter restart mất cache :memory:, gọi get_default(':memory:') đầu độc singleton, hoặc SignedIntegrationEnvelope không được ghi nhận tiêu thụ | DurableConsumptionRegistry lưu SQLite bền vững, OrcaDeliveryAdapter dùng DEFAULT_PRODUCTION_CONSUMPTION_DB_PATH, cấm :memory:, get_default từ chối ephemeral fail-closed, adapter từ chối poisoned singleton fail-closed, check_and_consume_integration nguyên tử kiểm tra replay, nonce single-use, monotonic fencing, restart durability | **CLOSED** (`test_05`, `test_06`, `test_07`, `test_12`, `test_13`, `test_14`, `test_15`, `test_15d`) |
| **5. Merge Authority** | Worker tự gọi transition sang integrated hoặc tự merge mã nguồn vào nhánh chính | Chỉ TrustedIntegrationConsumer với phong bì hợp lệ mới cho phép hoàn tất integration gate; worker chỉ có quyền push feature branch | **CLOSED** (`test_08`, `test_10`) |
| **6. Strict Type Validation** | Payload phong bì chứa chuỗi 'false' bị ép kiểu bool('false') == True, lọt qua gate kiểm duyệt | Strict type rejection trong from_dict từ chối chuỗi, số nguyên và kiểu không tương thích trước coercion | **CLOSED** (`test_16`) |

### 8.5. Khóa kích hoạt Production & Danh mục điều kiện tiên quyết (Prerequisites & Runbook)

Hệ thống phân định rạch ròi 3 trạng thái của kiến trúc:
1. ARCHITECTURE_IMPLEMENTED: Toàn bộ lớp kiến trúc, data contract, validator, và signed envelope đã được hiện thực hóa đầy đủ trong code.
2. REFERENCE_TESTED: Toàn bộ 17/17 probe test negative/positive trong TestSolTrustBoundaryRootCauseRemediation (RED evidence, monkey-patching, chữ ký Ed25519, thu hồi khóa, replay, restart SQLite, temporal validity, production gate fail-closed, fresh subprocess, positive control full lifecycle, key custody bootstrap prevention, integration durable consumption, restart durability, concurrency race, adapter restart SQLite durability, strict envelope type rejection, out-of-process host boundary channel rejection của mutable env và __main__ bootstrap, cùng các fixture phân biệt counterexample 11s, 11t, 11u, 11v, 15d, và 17h, 17i, 17j) đã vượt qua 100%.
3. PRODUCTION_ACTIVATION_BLOCKED: Trạng thái kích hoạt production bị **KHÓA CHẶT (FAIL-CLOSED)** cho đến khi toàn bộ 4 điều kiện hạ tầng bên dưới được cung cấp thực tế.



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
