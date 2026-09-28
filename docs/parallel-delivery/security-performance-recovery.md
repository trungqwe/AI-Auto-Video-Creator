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
| Harness tool namespace collapse | Kích hoạt STOP condition, đánh dấu `blocked_harness`, trả lease, fallback an toàn sang Antigravity native |
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

## 8. STOP conditions chung

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
- harness làm sụp namespace công cụ (`functions.exec` -> `functions`) hoặc thất bại tool-execution smoke test.

Ghi STOP evidence và hỏi/re-plan; không tiếp tục rồi sửa sau.
