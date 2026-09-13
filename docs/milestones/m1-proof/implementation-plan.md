# M1 — Implementation Plan cho Evidence Prototype

**Milestone:** M1 — `R0 Evidence Prototype`  
**Trạng thái:** `IN PROGRESS — M1-P0 PASS, M1-P1 NEXT; M1 CHƯA PASS`  
**Quyền implementation:** chỉ M1; M2, M3 và Phân hệ A bị khóa  
**Version set:** [M1-R1](./version-lock.md)  
**Evidence root:** [evidence](./evidence/README.md)  
**Căn cứ:** [roadmap](../../11-roadmap.md), [test strategy](../../10-test-strategy.md), [contracts](../../09-contracts/README.md), [ADR index](../../adr/README.md)

## 1. Mục tiêu và ranh giới

M1 dùng code proof nhỏ nhất để trả lời các câu hỏi kiến trúc có ảnh hưởng lớn trước khi xây product modules:

1. Contract/idempotency/outbox/receipt/fencing có giữ đúng bất biến khi crash, giao lặp và kết quả đến muộn không?
2. Temporal có ánh xạ được các semantics đó qua retry/replay/offline worker không?
3. Drive/OAuth thật có cho phép xác minh đúng byte, reconcile upload và giữ refresh token ngoài desktop không?
4. Local journal có sống qua crash/restart mà không tự commit business state hoặc cho cleanup sai không?
5. Version set M1-R1 có chạy cùng nhau trên môi trường mục tiêu không?

M1 không tạo crawler, UI sản phẩm, module A, AI/TTS, video pipeline hoặc production infrastructure. Proof code có thể được tái sử dụng sau review nhưng không mặc nhiên là production code. Không thêm FastAPI/React/Scrapy/Trafilatura/Playwright/model AI/TTS.

## 2. Trạng thái và quy tắc điều hành

Mỗi work package chỉ dùng một trong các trạng thái:

| Trạng thái | Ý nghĩa |
|---|---|
| `NOT_STARTED` | Chưa thực hiện |
| `RED_CONFIRMED` | Test đã thất bại đúng oracle vì hành vi chưa có/sai, không phải lỗi import/setup |
| `IMPLEMENTING` | Đang thêm implementation tối thiểu để giải quyết RED |
| `CORRECTION_REQUIRED` | Sau implementation, test/harness còn lỗi nhưng contract và version lock chưa bị phủ định; sửa trong cùng package và giữ toàn bộ evidence RED/GREEN/failure |
| `PASS` | Tất cả điều kiện PASS và evidence bắt buộc đã có |
| `FAIL` | Kết luận terminal: proof hợp lệ không thể đạt PASS trong phạm vi/version đã khóa sau khi loại trừ lỗi setup và implementation thông thường |
| `BLOCKED_EXTERNAL` | Không thể chạy external proof vì credential/quota/quyền ngoài dự án; không đổi thành PASS bằng mock |
| `STOPPED` | Điều kiện dừng bắt buộc đã kích hoạt; không chuyển work package phụ thuộc |

Quy tắc chung:

- Sau bootstrap/lockfile, dòng Python kiểm thử đầu tiên phải thuộc M1 proof.
- Viết test trước, chạy và lưu bằng chứng RED đúng lý do; rồi mới viết implementation tối thiểu và chạy GREEN/regression.
- Bootstrap trước test được ghi tại `evidence/m1-p0/bootstrap.json`; từ RED/GREEN P0 trở đi, mỗi test run tham chiếu `environment.json`, command, exit code, stdout/stderr đã redacted, thời gian UTC và SHA-256 artifact liên quan.
- Không sửa test oracle để hợp thức hóa hành vi. Nếu evidence root-cause cho thấy contract/kiến trúc sai, dừng và mở change control/ADR trước khi sửa test; lỗi implementation không làm thay đổi contract được sửa trong cùng package ở trạng thái `CORRECTION_REQUIRED`.
- Không dùng `latest`, không đổi version R1 hoặc lockfile âm thầm. Version delta cần R2 theo version lock.
- Không ghi secret/token/authorization code vào repository, log, workflow history, pytest output hoặc evidence.
- Setup/import/binary missing không phải RED. Chúng được ghi là setup failure và xử lý trong P0/P5; nếu vi phạm điều kiện STOP thì package chuyển `STOPPED`, nếu chưa thì `CORRECTION_REQUIRED`.
- Mỗi package kết thúc phải ghi `PASS`, `FAIL`, `BLOCKED_EXTERNAL` hoặc `STOPPED`; trạng thái chưa có evidence mặc định là `NOT_STARTED`.
- Không tự mở ADR chỉ vì có RED hoặc defect. Chỉ mở ADR khi phân tích nguyên nhân có evidence cho thấy quyết định kiến trúc không còn giữ được; nếu chỉ sai version artifact thì đề xuất R2 trước.

## 3. Dependency và thứ tự

Trạng thái thực thi hiện hành:

| Work package | Trạng thái |
|---|---|
| M1-P0 | `PASS` |
| M1-P1 | `READY` |
| M1-P2..P6 | `NOT_STARTED` |

```text
M0 CLOSED
  ↓
M1-P0 Environment + harness
  ↓
M1-P1 Contract/idempotency/outbox/receipt
  ↓
M1-P2 Temporal G01
  ├──────────────→ M1-P3 Drive/OAuth G04
  ├──────────────→ M1-P4 Local journal/recovery
  └──────────────→ M1-P5 Compatibility smoke
                         ↓
                    M1-P6 Audit/evidence
```

Trình tự bắt đầu bắt buộc là P0 → P1. P2 bắt đầu sau P1 PASS. Sau P2, P3/P4/P5 được thực hiện theo thứ tự kế hoạch; nếu P3 `BLOCKED_EXTERNAL`, có thể tiếp tục P4/P5 vì không phụ thuộc credential. P6 có thể lập báo cáo tạm, nhưng M1 không đạt exit gate và `G04_M1_SCOPE` không thể nhận `PASS_M1_SCOPE` cho tới khi P3 PASS.

## 4. Evidence contract chung

Mỗi package có thư mục `evidence/m1-pN/` khi được thực hiện. Không tạo bằng chứng giả trước khi chạy. Tối thiểu gồm:

- `status.md`: trạng thái, scope, kết luận, issue/ADR mở lại;
- `environment.json`: OS/architecture/runtime/tool versions và nguồn artifact;
- `commands.jsonl`: command đã redacted, start/end UTC, exit code;
- `test-results.xml` hoặc định dạng máy đọc tương đương;
- `stdout.log`, `stderr.log` đã redacted khi có;
- `artifacts.sha256`: hash mọi evidence/artifact được trích dẫn;
- package-specific evidence được nêu dưới đây.

Trước test Python đầu tiên, P0 tạo thủ công/bằng lệnh bootstrap `evidence/m1-p0/bootstrap.json` chứa version Python/uv, platform, metadata package, `uv.lock` hash và kết quả PostgreSQL preflight. Đây là bản ghi đầu vào bất biến của test P0, không phải output của proof và không tạo PASS. Sau RED, implementation P0 mới tạo `evidence/m1-p0/environment.json` để test validator đưa về GREEN.

`evidence/manifest.json` ở P6 mới là manifest tổng hợp toàn M1: nó lập chỉ mục toàn bộ package, version-lock revision, `uv.lock` hash, contract/ADR revisions và trạng thái gate. Manifest không tự tạo PASS; mọi mục phải trỏ artifact tồn tại và hash khớp.

## 5. M1-P0 — Khóa môi trường và test harness

**Mục tiêu:** tạo môi trường M1-R1 tái lập và một test harness đủ chạy RED/GREEN, chưa có logic product.

### Đầu vào

- M0 APPROVED/CLOSED và quyền code M1.
- [Version lock R1](./version-lock.md).
- Quy tắc evidence ở test strategy và tài liệu này.
- Máy/OS hiện tại; đường cấp binary chỉ được chọn trong bước thực thi và phải ghi bằng chứng.

### Dependency

- Không phụ thuộc credential Google.
- Không phụ thuộc M2 hoặc module A.
- Phải chờ lệnh bắt đầu triển khai tiếp theo của user dù quyền M1 đã được cấp.

### Test RED cần có

`TST-M1-P0-001` được viết sau khi metadata/lockfile và `bootstrap.json` tối thiểu tồn tại nhưng trước công cụ tạo `environment.json`:

- đọc giá trị kỳ vọng từ `bootstrap.json` bất biến và yêu cầu `environment.json` chứa đúng version R1, platform và lock hash;
- RED phải do `environment.json` chưa được tạo hoặc thiếu trường/hash, không phải do `bootstrap.json`, pytest/import hoặc setup lỗi;
- lưu command/output chứng minh RED trước implementation;
- sau GREEN, cố ý đưa fixture version/hash sai để chứng minh validator phát hiện mismatch.

`TST-M1-P0-002` yêu cầu `environment.json` chứa kết quả probe tự động: kết nối tới PostgreSQL 18.6, `SELECT 1`, transaction rollback và round-trip UTF-8 tiếng Việt. Bootstrap đã xác nhận thủ công khả năng kết nối; RED của test này phải do probe/capture output chưa được implementation tạo, không phải do thiếu binary/service/config. Thiếu setup được xử lý trước test và không được ghi là RED nghiệp vụ.

### Implementation tối thiểu

- Metadata project chỉ cho M1 proof, exact direct dependencies và `requires-python` phù hợp R1.
- `uv.lock` khóa toàn bộ dependency chuyển tiếp; sync/check dùng frozen mode.
- Cấu hình pytest tối thiểu và thư mục proof/test tách khỏi product modules.
- Công cụ nhỏ thu version/environment/hash và redaction; không thêm web framework, DI framework, migration framework hoặc CLI framework nếu standard library đủ.
- Cơ chế tạo evidence path theo package/run ID, không ghi đè run cũ.
- Preflight PostgreSQL tối thiểu: xác nhận server 18.6 khởi động, psycopg 3.3.5 kết nối được, rollback hoạt động và dữ liệu UTF-8 không hỏng.

### Failure injection

- Version executable khác R1.
- Lockfile bị sửa sau manifest hoặc thiếu transitive dependency.
- Path có khoảng trắng/ký tự Windows và timezone khác.
- Evidence file bị đổi byte sau khi lập hash.
- Canary secret trong environment; collector phải redact/allowlist, không dump toàn bộ environment.

### Bằng chứng phải lưu

- `uv.lock` và SHA-256; direct/transitive dependency listing.
- `bootstrap.json`, Python/uv/PostgreSQL version outputs và PostgreSQL preflight result; Temporal/FFmpeg outputs khi đã có artifact tương ứng.
- Nguồn/digest binary hoặc image đã dùng; riêng FFmpeg có archive/executable hash và build info khi P5 hoàn tất.
- RED và GREEN của TST-M1-P0-001; redaction negative test.
- Environment manifest schema/version.

### Điều kiện PASS

- Exact R1 được resolve/sync frozen trên môi trường proof.
- Test harness chạy được và RED/GREEN đúng oracle.
- PostgreSQL 18.6 + psycopg 3.3.5 vượt preflight kết nối, `SELECT 1`, rollback và UTF-8; P1 không phụ thuộc kết luận P5 tương lai.
- Lock hash/evidence hash tái kiểm tra khớp.
- Không có dependency ngoài danh sách trực tiếp được duyệt; dependency chuyển tiếp đều nằm trong lock.
- Không secret/canary xuất hiện trong evidence.

### Điều kiện STOP

- Một direct version R1 không resolve/cài/chạy được trên platform mục tiêu.
- Resolver buộc thay direct version hoặc dùng Python 3.14.
- Không thể tạo lock tái lập hoặc evidence collector làm lộ secret.
- Chỉ có thể tiếp tục bằng cách thêm công nghệ ngoài phạm vi M1 mà chưa có quyết định.

### ADR/change path nếu thất bại

- Mismatch runtime/tooling có thể mở [ADR-0007](../../adr/0007-runtime-and-admin-ui.md) trong phần runtime/FFmpeg.
- Nếu failure chỉ là version cụ thể, trước tiên tạo đề xuất M1-R2; không mở ADR kiến trúc khi chưa có bằng chứng quyết định kiến trúc sai.

## 6. M1-P1 — Contract, idempotency, outbox và receipt proof

**Mục tiêu:** chứng minh application semantics độc lập workflow engine trước khi quy trách nhiệm cho Temporal.

### Đầu vào

- P0 PASS và version-lock/hash cố định.
- CT-CMN-001..013, CT-EVT-001..005, CT-WF-004..006, CT-STATE-011.
- ADR-0002, ADR-0004, ADR-0009 và các invariant `INV-001/002/003/010/012/016/017` ở phạm vi proof.

### Dependency

- P0 PASS, trong đó PostgreSQL 18.6 và psycopg 3.3.5 đã vượt preflight tối thiểu.
- Không phụ thuộc Temporal hoặc Google credential.

### Test RED cần có

- `TST-M1-P1-001`: hai command cùng idempotency key/payload chỉ tạo một mutation và trả cùng receipt.
- `TST-M1-P1-002`: cùng key nhưng payload fingerprint khác bị từ chối.
- `TST-M1-P1-003`: business mutation và outbox cùng commit/rollback qua crash boundary.
- `TST-M1-P1-004`: event giao lặp/reorder không tạo side effect thứ hai.
- `TST-M1-P1-005`: lost ACK sau commit trả receipt cũ, không làm lại operation.
- `TST-M1-P1-006`: generation hoặc recovery epoch cũ bị stale/quarantine, không mutation.
- `TST-M1-P1-007`: outcome unknown buộc reconcile trước retry side effect.
- `TST-M1-P1-008`: canary secret không xuất hiện trong row/event/problem/log/evidence.
- `TST-M1-P1-009`: một completion Unit of Work đại diện ghi nguyên tử completion ledger, chuyển `BatchCapacityReservation` thành completed/count đúng một lần, ghi `MediaUsage` qua owner port của C và tạo outbox; crash tại từng boundary phải hoặc rollback toàn bộ hoặc commit toàn bộ.
- `TST-M1-P1-010`: mất ACK hoặc giao lặp cùng completion command trả đúng receipt cũ; ledger, batch count/reservation conversion và `MediaUsage` chỉ xuất hiện một lần.

Mỗi test phải RED do invariant chưa được implementation giữ; schema/migration không tồn tại có thể là RED đầu của từng lát cắt, nhưng test phải chỉ ra expectation nghiệp vụ, không dừng ở import error.

### Implementation tối thiểu

- PostgreSQL schema proof nhỏ nhất cho aggregate revision, idempotency record, command/operation receipt, outbox, consumer checkpoint, recovery epoch và completion Unit of Work đại diện.
- Transaction boundary/ports đủ thực hiện các test; không xây API/UI hoặc generic framework.
- Port giả lập đúng ownership cho G completion/batch reservation và C `MediaUsage`; không dựng video pipeline hoặc ghi trực tiếp chéo bảng owner.
- Canonical input fingerprint và expected revision theo common contract.
- Outbox dispatcher test adapter có crash hooks; consumer dedupe/checkpoint.
- Structured problem/result và log allowlist/redaction.

### Failure injection

- Crash trước mutation, giữa mutation/outbox, sau commit trước ACK, sau dispatch trước checkpoint.
- Hai transaction đồng thời cùng key/revision.
- Event duplicate, reorder và consumer restart.
- Worker cũ gửi result sau generation/epoch mới.
- Receipt row bị đọc lại sau process restart.
- Crash trước/sau từng bước của completion Unit of Work; lost ACK sau commit và duplicate completion delivery.
- Canary secret ở input/error từ adapter.

### Bằng chứng phải lưu

- RED/GREEN test reports và transaction-state snapshots trước/sau injection.
- SQL migration/schema proof hash và PostgreSQL version/config tối thiểu liên quan.
- Receipt/outbox/checkpoint rows đã redacted cho từng case.
- Fault timeline chỉ rõ điểm crash và expected/actual commit.
- Secret scan result trên DB export/log/evidence fixture.

### Điều kiện PASS

- Tất cả P1 tests GREEN lặp lại được sau restart.
- Không có partial business/outbox commit ở các điểm injection.
- Duplicate/lost ACK trả cùng logical result; stale epoch/generation không ghi.
- Completion ledger, batch count/reservation conversion, `MediaUsage` và outbox cùng commit/rollback; retry/lost ACK không nhân bất kỳ thành phần nào.
- Unknown không bị retry mù.
- Không canary secret trong evidence surfaces đã kiểm tra.

### Điều kiện STOP

- Contract chỉ đạt bằng cách bỏ expected revision/fencing/outbox hoặc dùng at-most-once giả.
- Không thể xác định transaction owner/commit boundary.
- Test race không ổn định đến mức không chứng minh được oracle bằng barrier/transaction control.
- Secret bắt buộc phải nằm trong event/receipt để vận hành proof.

### ADR/change path nếu thất bại

- [ADR-0004](../../adr/0004-commit-idempotency-and-fencing.md) cho commit/idempotency/fencing.
- [ADR-0002](../../adr/0002-authoritative-data-and-search.md) nếu PostgreSQL không giữ được vai trò nguồn sự thật như thiết kế.
- [ADR-0009](../../adr/0009-trust-boundaries-and-secrets.md) nếu trust/secret boundary không khả thi.

## 7. M1-P2 — Temporal G01 proof

**Mục tiêu:** kiểm chứng Temporal 1.31.2 + SDK 1.32.0 có ánh xạ được contract P1 và workflow sống qua retry/replay/offline worker.

### Đầu vào

- P0 và P1 PASS.
- CT-WF-001..009, CT-STATE-008..011.
- ADR-0003/0004; G01 oracle tại test strategy.
- Temporal distribution/digest và persistence config ghi trong environment evidence.

### Dependency

- PostgreSQL/contract proof P1; Temporal server và SDK exact R1.
- Không phụ thuộc Drive credential.

### Test RED cần có

- `TST-M1-P2-001`: workflow chờ khi desktop worker offline rồi resume đúng stage, không restart từ đầu.
- `TST-M1-P2-002`: activity retry sau failure trước side effect; lost ACK sau commit dùng P1 receipt và không lặp side effect.
- `TST-M1-P2-003`: worker generation cũ trả sau worker mới bị stale.
- `TST-M1-P2-004`: child failure bị cô lập, sibling/parent policy vẫn đúng.
- `TST-M1-P2-005`: workflow history tạo bởi revision workflow v1 replay thành công bằng revision v2 tương thích trên cùng Temporal Server/SDK R1, dùng cơ chế versioning/patch phù hợp; fixture thay đổi không tương thích phải bị detector từ chối.
- `TST-M1-P2-006`: unknown external outcome vào reconciliation path, không bị Temporal retry policy làm lại mù.
- `TST-M1-P2-007`: payload/history không chứa secret hoặc blob cấm.

### Implementation tối thiểu

- Một workflow proof và child workflow nhỏ đại diện control flow; activity adapter gọi ports P1.
- Task queues logic tối thiểu cho control và simulated desktop capability; không tạo production queue topology.
- Workflow code deterministic, payload chỉ chứa refs/IDs nhỏ.
- Retry/wait/signal/reconciliation behavior đủ test; không xây scheduler, crawler hay video job hoàn chỉnh.
- Worker lifecycle harness để start/stop/restart có kiểm soát.

### Failure injection

- Kill worker/workflow process trước/sau activity commit.
- Desktop worker offline trong lúc task chờ, rồi online lại.
- Activity timeout, heartbeat loss, duplicate delivery và delayed stale result.
- Child workflow failure và parent restart.
- Replay history v1 sau khi worker chạy workflow revision v2 tương thích; cố ý nondeterministic/incompatible fixture để chứng minh detector hoạt động.
- Temporal server restart với persistence giữ nguyên.

### Bằng chứng phải lưu

- RED/GREEN reports, workflow/run IDs, sanitized event histories và replay output.
- Fault timeline cho từng kill point; P1 receipt/DB diff tương ứng.
- Server/SDK/Python/PostgreSQL versions và Temporal distribution digest/config.
- Worker offline/resume timestamps và stage transition.
- Scan history/log/evidence không có secret/blob canary.

### Điều kiện PASS

- Mọi G01 case trong scope P2 đạt lặp lại trên exact R1; kết luận là `G01_M1_SCOPE=PASS_M1_SCOPE`, không phải G01 toàn phần.
- Restart/offline/retry không mất checkpoint, commit stale hoặc nhân side effect đã biết thành công.
- Replay history xác định; child failure đúng policy; payload boundary được giữ.
- Evidence đủ phân biệt Temporal behavior với application receipt behavior.
- Replay qua thay đổi workflow code tương thích đã được chứng minh; upgrade Temporal Server/SDK và replay production-path tiếp tục thuộc M2–M7, nên G01 tổng thể chỉ chuyển sang `PARTIALLY_PROVEN` sau P2 PASS.

### Điều kiện STOP

- Không thể bảo toàn grant/receipt/replay semantics mà phải hạ invariant.
- Temporal retry gây side effect lặp không thể chặn/reconcile qua contract.
- Workflow history buộc chứa secret/blob hoặc workflow không replay được với thiết kế tối thiểu.
- Resource/operation requirement rõ ràng vượt constraint M1 đến mức hướng self-hosted không còn khả thi; ghi số đo, không suy đoán.

### ADR/change path nếu thất bại

- [ADR-0003](../../adr/0003-durable-workflow-engine.md) bắt buộc mở lại khi Temporal không đạt G01 semantics.
- [ADR-0004](../../adr/0004-commit-idempotency-and-fencing.md) chỉ mở lại nếu failure thuộc application protocol chứ không phải engine adapter.
- [ADR-0011](../../adr/0011-observability-capacity-and-cost.md) nếu evidence tài nguyên phủ định baseline vận hành.

## 8. M1-P3 — Google Drive/OAuth G04 proof

**Mục tiêu:** dùng tài khoản/quota/OAuth thật để kiểm chứng identity, resumable upload, byte integrity, revoke/refresh và secret boundary.

### Đầu vào

- P0/P1/P2 PASS; exact Google libraries R1.
- Credential/quota thật được cấp phù hợp môi trường test E3.
- CT-STO-001..006/009, ADR-0006/0009; G04 oracle.

### Dependency

- `ROADMAP-OPEN-003` phải có external account/quota/OAuth access thật.
- Nếu thiếu, ghi `BLOCKED_EXTERNAL`; mock chỉ chạy unit tests và không đóng G04.

### Test RED cần có

- `TST-M1-P3-001`: pre-generated Drive ID + resumable upload giữ một object qua retry/lost ACK.
- `TST-M1-P3-002`: timeout trước/sau server nhận byte phân biệt retryable/unknown và reconcile.
- `TST-M1-P3-003`: file cùng tên khác byte không được nhận là artifact đúng; verify ID/size/hash/download khi cần.
- `TST-M1-P3-004`: session hết hạn hoặc ID conflict đi đúng reconciliation path, không tạo file lặp mù.
- `TST-M1-P3-005`: token refresh khi desktop không giữ refresh token dài hạn; revoke/invalid scope chuyển capability/waiting rõ ràng.
- `TST-M1-P3-006`: rate limit/quota không tạo retry storm hoặc trạng thái verified giả.
- `TST-M1-P3-007`: token/canary không xuất hiện trong log, receipt, history hoặc evidence.

Unit RED có thể dùng fake transport để định hình adapter. External run RED/GREEN phải dùng E3 và lưu evidence redacted; không biến test fake thành G04 result.

### Implementation tối thiểu

- Drive adapter proof cho generate ID/create/resumable upload/get/download verify và reconciliation.
- OAuth/token-broker boundary proof đủ chứng minh desktop chỉ nhận access capability ngắn hạn; không xây Admin UI.
- Artifact/location/operation receipt integration nhỏ nhất với P1.
- Bounded retry/backoff theo response; giá trị cụ thể ghi trong test config/evidence, chưa phải production default.

### Failure injection

- Ngắt mạng/client trước và sau chunk/final response.
- Làm hết hạn resumable session; dùng ID đã tồn tại; object metadata sai.
- Revoke token, scope thiếu, refresh failure, rate limit và quota exhausted.
- Kill process sau Drive side effect trước PostgreSQL receipt/ACK.
- Canary secret qua mọi error path.

### Bằng chứng phải lưu

- Account identity đã băm/redact, scope/consent mode, quota observations và thời điểm test.
- Drive file IDs redacted khi cần, request/response metadata an toàn, size/hash/download verification.
- Upload/reconcile timeline và DB receipt/location diff.
- Token placement diagram/observation chứng minh desktop không lưu refresh token dài hạn.
- RED/GREEN external results và security scan; không lưu credential.

### Điều kiện PASS

- External E3 tests đạt trên tài khoản/quota thật.
- Lost ACK/timeout không tạo object logic trùng hoặc verified giả.
- Byte đúng được xác minh trước khi location đủ điều kiện completion/cleanup.
- Refresh/revoke/scope/quota có trạng thái và retry behavior đúng; secret boundary giữ được.
- Kết luận chỉ là `G04_M1_SCOPE=PASS_M1_SCOPE`; local HTTPS/Origin, Temporal authorization và production account-pool path còn phải kiểm chứng ở M2–M7. G04 tổng thể chuyển `PARTIALLY_PROVEN`, không phải PASS toàn phần.

### Điều kiện STOP

- Thiếu credential/quota/quyền thật: `BLOCKED_EXTERNAL`, không FAIL kiến trúc và không PASS G04.
- Chỉ có thể vận hành bằng refresh token dài hạn trên desktop trái ADR-0009.
- Không thể xác minh đúng byte/object identity trước cleanup.
- API/account behavior buộc bỏ artifact/receipt invariant hoặc tự mua provider khác.

### ADR/change path nếu thất bại

- [ADR-0006](../../adr/0006-drive-artifacts-and-local-journal.md) nếu Drive identity/integrity/reconcile không khả thi.
- [ADR-0009](../../adr/0009-trust-boundaries-and-secrets.md) nếu OAuth/token boundary không khả thi.
- Không mở ADR chỉ vì `BLOCKED_EXTERNAL`; ghi dependency và chờ user/external state.

## 9. M1-P4 — Local journal và recovery proof

**Mục tiêu:** chứng minh journal desktop giữ operation/receipt chưa gửi qua crash/restart, tách cache có thể bỏ và không tự commit business state.

### Đầu vào

- P0/P1/P2 PASS; P3 có thể PASS hoặc BLOCKED_EXTERNAL.
- CT-STO-005/008/009, CT-WF-004..006, ADR-0004/0006/0010.
- Recovery epoch và cleanup invariants.

### Dependency

- Python standard `sqlite3` được ưu tiên; không thêm ORM/database package nếu proof không yêu cầu.
- Fake storage receipt được phép cho local recovery logic nhưng không đóng G04/G05.

### Test RED cần có

- `TST-M1-P4-001`: crash sau local artifact complete trước gửi receipt; restart tìm và gửi lại đúng operation.
- `TST-M1-P4-002`: crash giữa file write/rename không coi partial byte là artifact hoàn tất.
- `TST-M1-P4-003`: cloud đã commit nhưng desktop mất ACK; reconcile trả receipt cũ, không commit lần hai.
- `TST-M1-P4-004`: recovery epoch/generation cũ bị quarantine, không mutation/cleanup.
- `TST-M1-P4-005`: cache có thể dọn nhưng unsent journal/reference active không bị xóa.
- `TST-M1-P4-006`: file missing/hash mismatch giữ trạng thái lỗi/unknown, không báo success.

### Implementation tối thiểu

- SQLite journal schema/version nhỏ nhất, append/update state có transaction và fsync behavior được ghi.
- Atomic local file finalize bằng temp + checksum + rename phù hợp Windows.
- Startup reconciliation đọc journal, kiểm file/hash và hỏi cloud receipt qua P1 port.
- Cleanup evaluator chỉ tạo/tiêu thụ authorization hợp lệ; không triển khai toàn storage lifecycle.
- Secret chỉ lưu reference, không token/session plaintext.

### Failure injection

- Kill process tại từng boundary file/SQLite/cloud ACK.
- Journal transaction rollback, DB locked, disk full và file bị sửa/mất.
- Restart với epoch mới và pending entry epoch cũ.
- Duplicate startup/reconcile process.
- Cleanup request cũ/sai hash/reference active.

### Bằng chứng phải lưu

- RED/GREEN reports, journal state dumps đã redacted và file hashes.
- Crash matrix/timeline cho từng boundary.
- Reconcile decisions và cloud receipt diff.
- Cleanup denial evidence cho stale/unknown/reference-active cases.
- Giới hạn proof: không tuyên bố G05 restore toàn hệ thống PASS.

### Điều kiện PASS

- Unsent receipt/artifact được phục hồi hoặc báo lỗi có bằng chứng, không mất âm thầm.
- Duplicate startup/reconcile không nhân business mutation.
- Epoch/generation cũ không commit/cleanup.
- Partial/corrupt/missing file không được nâng thành available/verified.
- Journal bền được phân biệt rõ khỏi cache.

### Điều kiện STOP

- Thiết kế phải lưu refresh token/secret plaintext ở desktop.
- Crash window cho phép xóa bản duy nhất hoặc commit business state từ journal cũ.
- Không thể phân biệt partial byte với artifact hoàn tất.
- Recovery chỉ đạt bằng cách bỏ epoch/fencing hoặc chạy lại side effect mù.

### ADR/change path nếu thất bại

- [ADR-0006](../../adr/0006-drive-artifacts-and-local-journal.md) cho journal/artifact identity.
- [ADR-0010](../../adr/0010-storage-lifecycle-and-recovery.md) cho cleanup/recovery.
- [ADR-0004](../../adr/0004-commit-idempotency-and-fencing.md) nếu receipt/fencing protocol sai.

## 10. M1-P5 — Compatibility smoke

**Mục tiêu:** chứng minh các artifact R1 thực sự khởi động và giao tiếp ở mức M1; không tuyên bố G07 production PASS.

### Đầu vào

- P0 PASS; dùng artifact/version/hash thực tế của P1–P4.
- Version lock R1 và compatibility test requirements.
- FFmpeg binary/build được chọn có nguồn và hash.

### Dependency

- Có thể chạy song song chuẩn bị evidence sau P0, nhưng kết luận chỉ sau P1/P2 và P4.
- P3 BLOCKED_EXTERNAL không chặn smoke library import; phần Drive/OAuth thực vẫn “not tested”, không PASS.

### Test RED cần có

- `TST-M1-P5-001`: exact Python/uv/direct/transitive lock và frozen sync.
- `TST-M1-P5-002`: PostgreSQL connect, transaction rollback, concurrent uniqueness và encoding UTF-8.
- `TST-M1-P5-003`: Temporal SDK ↔ Server handshake, persistence, workflow start/replay smoke.
- `TST-M1-P5-004`: import/construct Google clients không credential và phân loại missing credential; không gọi external để giả G04.
- `TST-M1-P5-005`: FFmpeg version/buildconf/license capture, decode fixture và deterministic structural output checks.
- `TST-M1-P5-006`: evidence hash mismatch và unsupported version bị detector từ chối.

RED đầu tiên của mỗi smoke phải do capability/validator chưa có hoặc fixture incompatibility mong đợi, không chấp nhận “binary not found” là proof đầy đủ. Binary missing là setup/STOP cần xử lý theo version lock.

### Implementation tối thiểu

- Compatibility runner gọi executable/client trực tiếp và ghi structured result.
- Fixture nhỏ không thuộc sản phẩm: Unicode/Vietnamese DB row; workflow/activity; media/audio-video ngắn do dự án tự tạo hoặc có quyền rõ.
- FFmpeg invocation an toàn bằng argument array, không shell interpolation.
- Không viết wrapper media/render tổng quát hoặc production deployment scripts.

### Failure injection

- Wrong binary first on PATH, wrong server port/version, PostgreSQL disconnect.
- Lockfile hash sai hoặc transitive package thiếu.
- FFmpeg build thiếu codec/container cần cho fixture; corrupt input.
- Google credential absent/revoked được phân loại, không leak stack secret.
- Process locale/path có khoảng trắng và tiếng Việt.

### Bằng chứng phải lưu

- Compatibility matrix gồm requested/observed version, source, digest, result và limitation.
- Full `ffmpeg -version`/`-buildconf`, archive/executable SHA-256 và license/configuration build.
- PostgreSQL/Temporal/Python/uv outputs; lock hash.
- Smoke RED/GREEN results, fixture hashes và output probe.
- Drive/OAuth column ghi `NOT_TESTED_EXTERNAL` nếu P3 chưa có credential.

### Điều kiện PASS

- Exact R1 artifacts chạy được cho smoke M1 trên platform đã ghi.
- PostgreSQL/Temporal/Python SDK interaction tối thiểu đạt và frozen lock tái lập.
- FFmpeg fixture đọc/xuất/kiểm cấu trúc được; build/license evidence đầy đủ cho binary thực tế.
- Mọi phần chưa external-tested được ghi rõ, không nâng thành G04/G07 PASS.

### Điều kiện STOP

- Exact R1 không thể chạy cùng nhau hoặc chỉ chạy khi đổi version/dependency âm thầm.
- FFmpeg binary không xác định được nguồn/hash/build/license.
- SDK/server/database mismatch phủ định P2 evidence.
- Smoke có secret leak, command injection hoặc kết quả phụ thuộc PATH không xác định.

### ADR/change path nếu thất bại

- Trước hết đề xuất M1-R2 nếu chỉ là version artifact.
- [ADR-0003](../../adr/0003-durable-workflow-engine.md) nếu Temporal incompatibility mang tính kiến trúc.
- [ADR-0007](../../adr/0007-runtime-and-admin-ui.md) cho runtime/FFmpeg baseline.
- [ADR-0009](../../adr/0009-trust-boundaries-and-secrets.md) nếu compatibility chỉ đạt bằng cách hạ security boundary.

## 11. M1-P6 — Tổng hợp evidence và audit

**Mục tiêu:** tạo kết luận có thể kiểm tra về từng proof, giữ hoặc mở lại ADR và trình user checkpoint; không biến “tests ran” thành “gate PASS”.

### Đầu vào

- P0/P1/P2/P4/P5 có trạng thái terminal cùng evidence.
- P3 PASS, FAIL hoặc BLOCKED_EXTERNAL với evidence dependency.
- Version lock, `uv.lock`, contract/ADR revisions và mọi deviation record.

### Dependency

- Không bắt đầu kết luận trước khi các package độc lập đã kết thúc.
- P3 BLOCKED_EXTERNAL cho phép audit tạm nhưng chặn M1 exit, `G04_M1_SCOPE=PASS_M1_SCOPE` và M2.

### Test RED cần có

- `TST-M1-P6-001`: manifest thiếu package/status/hash/version/contract revision bị từ chối.
- `TST-M1-P6-002`: artifact bị sửa sau hash hoặc trỏ file không tồn tại bị từ chối.
- `TST-M1-P6-003`: rule engine/report không cho M1 PASS khi P3 BLOCKED_EXTERNAL/FAIL hoặc package bắt buộc chưa PASS.
- `TST-M1-P6-004`: report chỉ cho G01/G04 nhận `PASS_M1_SCOPE` khi đủ case M1 và không cho G01/G04/G07 nhận PASS toàn phần nếu thiếu evidence class/case của gate tổng thể.
- `TST-M1-P6-005`: secret/canary scan trên toàn evidence fail closed.

### Implementation tối thiểu

- Evidence manifest builder/validator và status summarizer nhỏ; không làm dashboard/UI.
- Máy trạng thái kết luận package/M1: `PASS`, `FAIL`, `BLOCKED_EXTERNAL`, `STOPPED`; trạng thái gate: `NOT_TESTED`, `PASS_M1_SCOPE`, `PARTIALLY_PROVEN`, `PASS`, `FAIL` hoặc `BLOCKED_EXTERNAL`.
- Trace map từ test → invariant/gate → artifact → ADR decision.
- Audit report template ghi limitation, deviation, unresolved dependency và recommendation.

### Failure injection

- Xóa/sửa evidence file, giả exit code, duplicate run ID và hash mismatch.
- Đặt P3 BLOCKED_EXTERNAL nhưng cố gán G04 M1-scope hoặc M1 PASS.
- Missing RED evidence nhưng có GREEN result.
- Version manifest khác R1 hoặc lock hash không khớp.
- Chèn canary secret vào log/evidence.

### Bằng chứng phải lưu

- `evidence/manifest.json` và detached SHA-256 index.
- Trace matrix M1, package status reports, deviation list và secret scan.
- Audit report với G01/G04 tách trạng thái M1-scope khỏi gate tổng thể; trước test là `NOT_TESTED`, sau proof M1 đạt là `PASS_M1_SCOPE` và gate tổng thể là `PARTIALLY_PROVEN`, không phải PASS. G07 chỉ ghi trạng thái theo evidence thật.
- ADR decision note: giữ Conditional, chuyển trạng thái hoặc mở ADR mới; không sửa lịch sử evidence.
- User checkpoint package; chưa ghi user approved trước khi nhận xác nhận.

### Điều kiện PASS

- Mọi artifact trong manifest tồn tại, hash khớp và trace được tới test/contract/gate.
- P0/P1/P2/P3/P4/P5 PASS; `G01_M1_SCOPE` và `G04_M1_SCOPE` đạt `PASS_M1_SCOPE`; không secret leak.
- Failure/deviation đã xử lý hoặc có ADR/user decision rõ ràng.
- User duyệt kết quả proof. Chỉ khi đó M1 PASS và mới xem xét mở M2.

### Điều kiện STOP

- P3 BLOCKED_EXTERNAL: M1=`BLOCKED_EXTERNAL`, `G04_M1_SCOPE=BLOCKED_EXTERNAL`, G04 tổng thể vẫn chưa PASS; không mở M2.
- Bất kỳ package FAIL/STOPPED hoặc evidence integrity/secret scan fail.
- Có GREEN không có RED đúng lý do đối với test-first bắt buộc.
- Báo cáo không phân biệt mock/smoke/external evidence hoặc cố nâng G07 production từ compatibility smoke.

### ADR/change path nếu thất bại

- ADR tương ứng package P1–P5 theo bảng dưới.
- Nếu evidence protocol tự không đủ tin cậy, cập nhật test strategy/roadmap trước khi kết luận; không cần redesign product architecture.

## 12. Bảng STOP và ADR tổng hợp

| Package | STOP chính | ADR mở lại/đánh giá |
|---|---|---|
| P0 | R1 không resolve/tái lập; PostgreSQL preflight không đạt; secret leak từ harness | M1-R2 trước; ADR-0007/0002 chỉ khi root cause phủ định quyết định tương ứng |
| P1 | Không giữ atomicity/idempotency/fencing/receipt/completion UoW | ADR-0002/0004/0009 chỉ sau root-cause evidence |
| P2 | Temporal không giữ G01 semantics trong phạm vi M1 | ADR-0003; phối hợp 0004/0011 theo nguyên nhân có bằng chứng |
| P3 | Không xác minh byte/OAuth boundary; credential thiếu là BLOCKED_EXTERNAL | ADR-0006/0009 khi proof fail; không mở chỉ vì dependency thiếu |
| P4 | Journal mất pending result hoặc cho stale cleanup/commit | ADR-0004/0006/0010 |
| P5 | R1 incompatibility hoặc FFmpeg build không truy vết | M1-R2; ADR-0003/0007/0009 nếu mang tính kiến trúc |
| P6 | Evidence không toàn vẹn, gate bị nâng sai hoặc package chưa PASS | ADR của package nguồn; cập nhật evidence protocol nếu cần |

Điều kiện STOP có hiệu lực ngay. Không đi tiếp vào package phụ thuộc chỉ để thu thêm kết quả đẹp. `RED_CONFIRMED` là trạng thái test-first mong đợi, không phải FAIL/STOP. `CORRECTION_REQUIRED` cho phép sửa defect trong cùng package khi contract/version không đổi. Chỉ kết luận `FAIL` hoặc `STOPPED` sau phân tích nguyên nhân có evidence; package độc lập chỉ được tiếp tục khi plan nói rõ, ví dụ P4/P5 sau P3 BLOCKED_EXTERNAL.

## 13. Trạng thái open item trong M1

| Mục | Trạng thái | Ảnh hưởng M1 |
|---|---|---|
| PCC-026 | CLOSED | Baseline đã được user chấp thuận |
| PCC-027 | CLOSED — M1 ONLY | Có quyền code M1; hiện chờ lệnh kích hoạt tiếp theo |
| PCC-028 / ROADMAP-OPEN-002 | CLOSED_FOR_M1_R1 | P0 phải materialize lock/hash; không đồng nghĩa proof PASS |
| G01 Temporal | NOT TESTED | P2 chưa chạy; không có trạng thái scoped hoặc gate PASS |
| G04 Drive/OAuth | NOT TESTED | P3 chưa chạy; không có trạng thái scoped hoặc gate PASS |
| ROADMAP-OPEN-003 | OPEN — BLOCKS M1-P3 ONLY | Không chặn P0/P1/P2; thiếu credential thật sẽ làm P3 và M1 BLOCKED_EXTERNAL |
| Module A/timezone/Tier/source baseline | OPEN theo milestone cũ | Không giải quyết hoặc code trong M1 |
| AI/TTS/output profile/preset/retention/throughput | OPEN theo milestone/gate cũ | Không bị M1-R1 đóng |

## 14. Definition of Done cho M1

M1 chỉ `PASS` khi:

1. P0–P6 đáp ứng điều kiện PASS, gồm P3 trên external environment thật.
2. `G01_M1_SCOPE` và `G04_M1_SCOPE` đạt `PASS_M1_SCOPE`; G01/G04 tổng thể chỉ được ghi `PARTIALLY_PROVEN` cho tới khi đủ evidence các milestone sau. Compatibility smoke được gọi đúng phạm vi, không gắn nhãn G07 production PASS.
3. Không có secret leak, stale commit, duplicate known side effect hoặc cleanup trái quyền trong proof scope.
4. Evidence manifest/hash/trace hoàn chỉnh và audit kết luận không còn STOP chưa xử lý.
5. ADR Conditional được giữ bằng evidence hoặc mở lại với quyết định mới.
6. User duyệt checkpoint M1.

Nếu P3 BLOCKED_EXTERNAL, kết quả hợp lệ là `M1 BLOCKED_EXTERNAL`, không phải FAIL và không phải PASS. M2/M3/Phân hệ A vẫn khóa.

## 15. Lệnh bắt đầu và giới hạn hiện tại

User đã cấp quyền implementation cho M1 nhưng yêu cầu lượt hiện tại chỉ hoàn tất tài liệu và báo sẵn sàng. Vì vậy:

- chưa tạo project metadata, lockfile, test code hoặc source code trong lượt này;
- chưa cài runtime, dependency, PostgreSQL, Temporal hoặc FFmpeg;
- chưa tạo evidence run giả;
- khi có lệnh bắt đầu tiếp theo, thực hiện đúng `M1-P0 → M1-P1`, báo trạng thái và evidence sau từng package;
- không tự mở M2/M3/Phân hệ A dù M1 code đã được phép.
