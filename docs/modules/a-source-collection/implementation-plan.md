# Kế hoạch triển khai chi tiết — Phân hệ A: Nguồn và thu thập nội dung

**Tên kỹ thuật:** `a-source-collection`  
**Trạng thái:** Đã được user phê duyệt làm baseline; chưa được triển khai vì M1/M2 chưa đạt dependency gate  
**Đặc tả đầu vào:** [spec.md](./spec.md)  
**Milestone:** M3 trong [11-roadmap.md](../../11-roadmap.md)  
**Điều kiện tuyệt đối:** chưa được thực hiện bất kỳ bước code/cài đặt nào trước khi M0 cho phép

## 1. Mục tiêu triển khai

Xây phân hệ A thành một module cloud có thể kiểm thử độc lập, có adapter nguồn thay thế được và cung cấp `CollectedDocumentPackage` idempotent cho B, media discovery cho C/I, trạng thái/lỗi cho G/H và audit/config an toàn từ J.

Kết quả cuối của kế hoạch là lát cắt:

`User/G → Source/Collection command → fetch/extract → package/artifact refs → outbox → B/C/G/H`

Phân hệ A không được trở thành nơi giữ Article/Event, media catalog, storage lifecycle hoặc workflow state toàn hệ thống.

## 2. Điều kiện bắt đầu

Trước work package có code đầu tiên phải có:

1. M0 của roadmap đã được user phê duyệt/CLOSED; quyền code hiện chỉ cho M1, chưa mở implementation Phân hệ A.
2. M1 proof xác nhận workflow/outbox/receipt và Drive/artifact contract đủ dùng.
3. M2 cung cấp envelope, error, revision, outbox, config, secret, artifact metadata, operation/state và UI shell.
4. `spec.md`, `CT-SRC-*`, source/run state và test cases liên quan được review.
5. Fixture/schema SourceCandidate bám `CT-SRC-003A` và `CT-STATE-002A` trước khi code auto-discovery.
6. Runtime/dependency/test-tool versions được phê duyệt; không tự cài trong kế hoạch này.
7. Fixture nguồn không chứa secret production và có snapshot ổn định.

Nếu M1/M2 thay đổi contract nền, kế hoạch này phải được rebase theo contract revision mới trước RED test đầu tiên.

## 3. Quyết định đã khóa

- Module A có tên logic `source_ingestion` và chạy ở cloud worker.
- Modular monolith trong monorepo; chưa tách A thành repo/service riêng.
- PostgreSQL là nguồn sự thật nghiệp vụ; raw byte nằm qua I/Drive; không dùng Google Sheets làm lõi.
- G sở hữu cycle/schedule liên nguồn; A sở hữu Source và per-source CollectionRun.
- A chỉ tạo observation/package; B quyết định Article/revision/duplicate/event.
- Command mutation có idempotency; metadata edit có expected revision.
- Event phát at-least-once qua transactional outbox.
- Worker result có grant/generation; side effect dùng operation receipt.
- Periodic, source-test và supplemental là các purpose khác nhau; retry kỹ thuật là attempt của run hiện có.
- Tombstone chặn fetch/rediscovery mới nhưng không xóa dữ liệu lịch sử.
- Fetch boundary phải chống SSRF ở mọi redirect.
- Desktop offline không chặn cloud collection.

## 4. Điều chưa được khóa

Không work package nào được tự quyết định:

- source kinds chính thức;
- danh sách nguồn baseline;
- tiêu chí Tier;
- ngưỡng bài mới theo chủ đề;
- giá trị timezone/giờ chạy;
- ngưỡng độ dài/chất lượng nội dung để `content_eligibility=candidate`;
- adapter/social integrations baseline;
- timeout/retry/backoff/concurrency;
- raw snapshot retention;
- daily cycle maximum duration.

Các giá trị này phải tới từ policy/config revision hoặc được đóng trước work package liên quan.

## 5. Kiến trúc nội bộ dự kiến

Đây là ranh giới logic, chưa phải thư mục hoặc source file đã tạo.

| Khu vực | Trách nhiệm | Không được làm |
|---|---|---|
| Source Domain | Source lifecycle, revision, tombstone, eligibility rules thuần | Fetch mạng hoặc ghi module khác |
| Collection Domain | Run/attempt/checkpoint/disposition và counters | Sở hữu schedule/cycle của G |
| Application Commands | Validate command, idempotency, transaction, outbox | Chứa parser theo từng website |
| Source Adapter Port | Discover/list/fetch/extract theo capability chuẩn | Commit Article/MediaAsset |
| Adapter Implementations | RSS/web/official-source behavior cụ thể | Bỏ SSRF/resource policy |
| Fetch Security Boundary | URL resolution, redirect, size/type/time limits | Tin metadata từ nguồn |
| Package Builder | Tạo package/provenance/fingerprint/warnings | Quyết định duplicate/event |
| Persistence | Source/run/checkpoint/observation/outbox records | Đọc/ghi trực tiếp bảng B-J |
| Artifact Gateway | Giao raw/media bytes cho I và nhận `ArtifactRef` | Tự quản lý Drive path/cleanup |
| Worker Entry | Nhận activity grant, heartbeat, receipt và trả result | Tự đổi workflow state của G |
| Query Projection | Source/run/health/summary cho H | Kích hoạt fetch khi query |

### Tên package logic đề xuất

Khi repo được phép khởi tạo, có thể ánh xạ thành các package logic:

- `source_ingestion.domain`;
- `source_ingestion.application`;
- `source_ingestion.ports`;
- `source_ingestion.adapters`;
- `source_ingestion.persistence`;
- `source_ingestion.worker`;
- `source_ingestion.projections`.

**ĐỀ XUẤT:** tên cuối phải theo convention repository được tạo ở M1/M2. Không tạo các path này ở giai đoạn hiện tại.

## 6. Luồng thực thi mục tiêu

### 6.1. Quản lý nguồn

`H command`  
→ `Control API xác thực workspace/idempotency/revision`  
→ `A Source Domain kiểm tra lifecycle/policy`  
→ `PostgreSQL commit Source + OutboxEvent`  
→ `CommandReceipt`  
→ `H/G/J nhận projection/event`

### 6.2. Periodic collection

`G cycle còn thiếu unique articles`  
→ `A/G chọn source active Tier ưu tiên chưa có periodic run`  
→ `G cấp ActivityRequest + ExecutionGrant`  
→ `A tạo/khôi phục CollectionRun`  
→ `Adapter list/fetch từng item`  
→ `I lưu raw/media byte khi policy yêu cầu`  
→ `A commit FetchObservation + Package + Outbox`  
→ `B resolve article/duplicate`  
→ `G cập nhật unique count`  
→ `tiếp tục source/Tier hoặc kết thúc có reason`

### 6.3. Supplemental collection

`G chuyển media need từ D`  
→ `A kiểm tombstone/scope/budget`  
→ `adapter search/fetch`  
→ `A package/discovery + provenance`  
→ `B/C/I nhận kết quả`  
→ `không tăng periodic-run count`

### 6.4. Crash recovery

`Worker restart`  
→ `G kiểm generation/lease`  
→ `A đọc run + checkpoint + operation receipt`  
→ `reconcile artifact/outbox`  
→ `resume item chưa commit`  
→ `không phát package hoặc side effect lặp`

## 7. Port và handoff cần hiện thực

| Port logic | Caller/adapter | Input chính | Output chính |
|---|---|---|---|
| Source Command Port | H/API | command envelope, metadata, revision | receipt + SourceRef |
| Source Query Port | H | workspace/filter/cursor | revisioned source page |
| Collection Activity Port | G | source/config/policy/grant/checkpoint | ActivityResult + run/package refs |
| Supplemental Search Port | G | job/snapshot/scene/budget refs | discovery/acquisition refs |
| Source Adapter Port | A application | source revision + bounded request | observations/extraction candidates |
| Artifact Port | I | byte intent/hash/retention class | ArtifactRef/location operation |
| Content Handoff Port | B | CollectedDocumentPackage ref | acceptance/dedup result qua B event |
| Media Handoff Port | C | discovery refs/provenance | catalog disposition qua C event |
| Config Port | J | config/credential capability request | versioned bundle/short-lived handle |
| Operation/Event Port | G/H | run state/outbox events | projection/stream updates |

Không port nào truyền raw secret hoặc raw media byte trong workflow/event payload.

## 8. Transaction boundary và idempotency

### Source mutation transaction

Commit cùng transaction:

- Source revision/state;
- command idempotency record/receipt;
- audit record reference;
- outbox event.

### Package transaction

Sau khi raw artifact cần thiết có receipt/location đủ điều kiện, commit cùng transaction:

- FetchObservation;
- CollectedDocumentPackage metadata;
- CollectionRun counters/checkpoint an toàn;
- outbox `CollectedDocumentAvailable`.

Byte upload không nằm trong DB transaction. Timeout sau upload đi `OUTCOME_UNKNOWN` và reconcile qua I trước khi package tham chiếu location verified theo policy.

### Run completion transaction

Commit:

- terminal run state;
- counters/checkpoint;
- error/warning summary;
- completion/failure outbox event.

Run completion không rollback package đã commit riêng.

### Idempotency keys

| Operation | Khóa logic |
|---|---|
| Source mutation | workspace + command idempotency key |
| Periodic run creation | workspace + source + business date + periodic purpose; policy revision chỉ là metadata |
| Fetch observation | run + canonical item identity + observation fingerprint |
| Raw artifact upload | operation key + content hash |
| Document package | source + canonical locator + observation fingerprint |
| Event publish | event ID + consumer checkpoint |

Khóa cụ thể phải được contract test; không dùng filename hoặc mutable title.

## 9. Persistence plan

### Aggregate/record logic

| Record | Owner | Tính chất |
|---|---|---|
| Source | A | Revisioned aggregate |
| Source tombstone/locator identity | A | Bền vững, không bị xóa khi remove |
| CollectionRun | A | Một source, một purpose |
| CollectionAttempt | A | Append-only theo retry |
| CollectionCheckpoint | A | Versioned, chỉ tiến sau durable handoff |
| FetchObservation | A | Append-only theo lần quan sát |
| CollectedDocumentPackage | A trước handoff | Immutable metadata/ref |
| Source health observation | A | Time-series/projection theo retention |
| Command receipt | Core/G theo kiến trúc | A tham chiếu |
| Outbox event | Shared infrastructure, producer A | Append-only đến publish/checkpoint |

### Constraint/index cần thiết

- Unique canonical source identity trong workspace, bao gồm tombstone check.
- Unique periodic run key theo workspace/source/business-date/periodic-purpose, độc lập policy revision.
- Unique command idempotency key trong scope.
- Unique package fingerprint trong source/run scope theo policy.
- Index source theo workspace/status/Tier/topic/kind/last collection.
- Index run theo source/status/purpose/time/cycle.
- Index package theo source/run/canonical locator/fingerprint/time.
- Index outbox theo publish state/sequence.

Tên bảng/index vật lý được quyết định trong phase plan sau khi database convention ở M2 tồn tại.

## 10. Adapter contract plan

### Capability cần mô tả

Mỗi adapter khai báo:

- source kinds/protocols hỗ trợ;
- listing/discovery/fetch/extraction capabilities;
- auth requirement;
- cursor/checkpoint semantics;
- rate-limit hints;
- supported media discovery;
- maximum safe response assumptions từ policy;
- version và compatibility;
- health check behavior.

### Operation chuẩn

| Operation | Ý nghĩa |
|---|---|
| Probe source | Kiểm tra locator/capability mà không tạo periodic run |
| List candidates | Lấy item locators từ feed/listing |
| Fetch document | Lấy byte/HTTP observation qua security boundary |
| Extract candidate | Tạo trường kỹ thuật, text và media discoveries |
| Resume from checkpoint | Tiếp tục theo semantics adapter đã version hóa |
| Supplemental search | Tìm theo intent nếu adapter hỗ trợ |

Adapter không hỗ trợ operation phải trả capability-unavailable có cấu trúc, không giả success rỗng.

### Adapter acceptance suite

Mọi adapter phải chạy cùng suite:

- canonical/redirect/provenance;
- pagination/checkpoint/resume;
- duplicate item within listing;
- timeout/rate limit/auth failure;
- malformed/oversized response;
- HTML/encoding/media edge cases;
- SSRF redirect;
- partial result;
- deterministic fixture replay;
- no-secret logging.

Real integration test bổ sung, không thay contract suite.

## 11. Work package dependency map

`A0 Contract closure`  
→ `A1 Source domain/lifecycle`  
→ `A2 Collection run/checkpoint core`  
→ `A3 Secure fetch + first adapter`  
→ `A4 Extraction/package/artifact handoff`  
→ `A5 Periodic Tier workflow`  
→ `A6 Supplemental + auto-discovery`  
→ `A7 UI, observability, hardening và acceptance`

A1 và fixture preparation của A3 có thể song song sau A0. A6 auto-registration production không được bắt đầu nếu Tier/discovery policy chưa khóa; contract `SourceCandidate` đã có và được kiểm tra fixture ở A0.

## 12. A0 — Đóng contract và chuẩn bị test

Hậu kiểm AUD2-M01..003 đã bổ sung contract nguồn có thẩm quyền. A0 phải kiểm fixture các ID test mới trong test strategy; A2 exit yêu cầu terminal/reconcile cases, A4 exit yêu cầu schema-versus-content boundary, A6 exit yêu cầu registration races. “Đã đóng ở tài liệu” không miễn các exit test hoặc cho phép bỏ qua policy source kind/Tier còn mở.

### Mục tiêu

Biến spec thành input thực thi không còn khoảng trống blocking cho A1-A5; tách rõ điều có thể hoãn tới A6/A7.

### Công việc

1. Review `spec.md` với contracts 00/01/02/03/04/12.
2. Xác nhận fixture/schema bám `CT-SRC-003A` và `CT-STATE-002A` cho SourceCandidate.
3. Xác nhận required/conditional fields và `content_eligibility` bám `CT-SRC-006`.
4. Xác nhận run purpose và periodic unique-key bám `CT-SRC-004`/`CT-STATE-002`.
5. Chốt boundary A technical normalization/B business normalization.
6. Lập initial Contract Fixtures, News Corpus và malicious URL corpus.
7. Tạo test catalog ánh xạ `A-RULE-001..016`, user stories và QR liên quan.
8. Phân loại open item thành block A1-A5, block A6 hoặc chỉ block claim.

### RED tests phải thiết kế trước implementation

- Source lifecycle/idempotency/revision.
- Tombstone canonical-match và rediscovery block.
- Periodic run uniqueness/purpose separation.
- Checkpoint không vượt durable package.
- Package schema/provenance.
- Event/outbox duplicate/replay.

### Exit

- Không còn undefined owner hoặc contract cho A1-A5.
- Auto-discovery contract được duyệt hoặc A6 phần đó bị tách trạng thái `NOT_READY`.
- Fixture có version và oracle.
- User/architecture audit xác nhận không mở rộng scope.

## 13. A1 — Source domain và quản lý vòng đời

### Mục tiêu

Hiện thực Source aggregate và command/query lifecycle không phụ thuộc fetch adapter.

### Trình tự test-first

1. Viết RED tests cho register, duplicate command, canonical duplicate locator và tombstone conflict.
2. RED tests cho metadata update/expected revision/concurrent conflict.
3. RED tests cho enable/disable/remove/restore transitions.
4. RED tests cho workspace isolation và audit/outbox atomicity.
5. Hiện thực tối thiểu để GREEN; chạy regression và migration tests.

### Hành vi cần hiện thực

- canonical identity service theo policy;
- Source aggregate/repository port;
- command handlers và receipt;
- state transitions và previous operational state;
- source query/projection;
- outbox events;
- audit refs;
- UI contract integration qua H shell.

### Failure cases

- invalid/unsafe root locator;
- same locator active/disabled/tombstone;
- stale revision;
- config/Tier enum không hỗ trợ;
- DB commit/outbox failure;
- query cursor invalid;
- unauthorized workspace.

### Exit

- `CT-SRC-001..003` và Source state tests GREEN.
- Mutation lặp/concurrent không tạo state sai.
- Tombstone bền vững và UI quan sát được.
- User chạy được manual source lifecycle trên môi trường tích hợp.

## 14. A2 — CollectionRun, attempt và checkpoint core

### Mục tiêu

Hiện thực state/idempotency nền cho mọi kiểu collection trước khi nối mạng thật.

### Trình tự test-first

1. RED tests cho periodic unique key và purpose separation.
2. RED tests cho run/attempt transitions, partial/failure và terminal immutability.
3. RED tests cho execution grant/generation stale.
4. RED tests cho item commit/checkpoint atomic boundary.
5. RED tests cho restart/replay với fake adapter/clock.

### Hành vi cần hiện thực

- run creation/resume application service;
- attempt append-only history;
- heartbeat/progress/counters;
- checkpoint versioning;
- operation receipts;
- package commit coordination shell;
- run completion event/outbox;
- source health projection.

### Failure cases

- worker chết trước/sau item commit;
- stale worker trả checkpoint mới hơn;
- duplicate ActivityRequest;
- run `WAITING_RETRY` được attempt mới tiếp tục, còn run terminal bị yêu cầu resume;
- `TST-COL-END-001..004`: hết retry với/không có package đã commit; source inactive lúc SCHEDULED/WAITING_RETRY; reconcile retryable nhưng hết budget; unknown quá hạn vẫn chờ có cảnh báo, không giả định thất bại side effect. Oracle theo CT-STATE-002, không tạo attempt giả để terminal.
- checkpoint adapter version không tương thích;
- DB unavailable khi heartbeat/completion.

### Exit

- Run không mất/đếm lặp qua crash/replay fixture.
- Checkpoint chỉ tiến khi package bền vững.
- Stale generation không commit.
- Periodic, source-test và supplemental được phân biệt trong state/query.

## 15. A3 — Secure fetch và adapter đầu tiên

### Mục tiêu

Chứng minh adapter port với một năng lực nguồn baseline được duyệt, qua fetch security boundary đầy đủ.

### Điều kiện

Adapter đầu tiên chỉ được chọn từ source baseline sau nghiên cứu/duyệt; kế hoạch này không tự chọn RSS hay website cụ thể làm production baseline.

### Ứng viên đã được nghiên cứu

Theo [05-technology-research.md](../../05-technology-research.md), shortlist để proof gồm:

| Năng lực | Ứng viên ưu tiên nghiên cứu | Vai trò dự kiến, chưa phải dependency đã chốt |
|---|---|---|
| Parse RSS/Atom | `feedparser` | Parser feed chuẩn, không sở hữu lịch/Tier |
| HTTP crawl | `Scrapy` | Crawler chính cho nhiều nguồn |
| Trang động | `Playwright` | Fallback có kiểm soát, không dùng cho mọi URL |
| Trích xuất chính | `Trafilatura` | Text/metadata/link candidate từ HTML |
| Trích xuất fallback | Mozilla Readability hoặc `jusText` | Đối chiếu/fallback khi extractor chính thiếu |
| Feed cho site không có RSS | RSSHub | Adapter tùy chọn; phải đánh giá AGPL và độ ổn định route |

`Newspaper3k` không được ưu tiên làm extractor chính theo audit công nghệ hiện hành. Mọi ứng viên vẫn phải qua `TECH-POC-001`, compatibility/license/security review và khóa version ở M1/A0 trước khi cài.

POC phải dùng URL/fixture đại diện cho RSS đầy đủ, RSS rút gọn, HTML tĩnh, trang động và trang lỗi; đo khả năng lấy title/body/date/media, latency, resource use, failure mode và tỷ lệ cần browser fallback.

### Trình tự test-first

1. RED tests cho URL scheme, DNS result, redirect và private/link-local/metadata blocks.
2. RED tests cho timeout, response limit, MIME mismatch và redirect loop.
3. RED adapter contract tests bằng fixture server/snapshot.
4. RED tests cho credential handle/redaction nếu adapter cần auth.
5. Hiện thực port, security boundary và adapter; chạy integration sandbox.

### Hành vi cần hiện thực

- source probe;
- bounded HTTP fetch;
- redirect/DNS validation mỗi hop;
- response streaming/size enforcement;
- safe header/log representation;
- listing/item extraction theo adapter;
- capability/health report;
- rate-limit signal và retry-after mapping.

### Failure cases

- DNS rebinding/alternate IP notation;
- public URL redirect private;
- slow response/connection reset;
- oversized/compression expansion;
- malformed encoding/content;
- auth expired/revoked;
- provider robots/access restriction theo policy;
- adapter parser không còn tương thích.

### Exit

- Security corpus và adapter suite GREEN.
- Source lỗi không ảnh hưởng run nguồn khác.
- Không secret/raw authorization trong log/event/history.
- Real integration evidence ghi version/quota/limitations.

## 16. A4 — Extraction, package và artifact handoff

### Mục tiêu

Biến fetch observation thành package bất biến đủ để B resolve identity và C/I nhận media/provenance.

### Trình tự test-first

1. RED schema tests cho required/missing/null/time confidence.
2. RED tests cho URL/provenance/redirect chain preservation.
3. RED tests cho article text candidate, media discoveries và fingerprints.
4. RED tests cho raw artifact upload success/failure/outcome unknown.
5. RED tests cho package idempotency và outbox delivery lặp.
6. Hiện thực extraction/package builder và ports B/C/I.

### Hành vi cần hiện thực

- technical text/time/language normalization;
- extractor version/fingerprint;
- media candidate context;
- raw snapshot/media artifact intents;
- package validation;
- atomic metadata/checkpoint/outbox commit;
- B/C handoff projections/events;
- warnings/partial completeness.

### Failure cases

- empty body/title/time missing;
- `TST-COL-PKG-001..004`: sai ID/source/run refs bị VALIDATION_ERROR không có document event; extraction fail đủ provenance thành incomplete; title theo policy source kind; policy thiếu thì INPUT_NOT_READY. Tách missing publication time (conditional) khỏi missing cấu trúc; retry payload sai không nhân đôi dữ liệu.
- parse output vượt schema limits;
- media locator unsafe;
- I upload timeout after object creation;
- B consumer unavailable;
- duplicate event/package;
- extractor upgrade đổi fingerprint.

### Exit

- `CT-SRC-006` fixtures và contract tests GREEN.
- Package không bị nhầm thành Article trong ownership/persistence.
- B nhận lặp không tạo side effect lặp.
- Media discovery giữ provenance dù B kết luận bài duplicate.
- Partial run giữ package đã commit.

## 17. A5 — Periodic collection theo Tier

### Mục tiêu

Nối A với G/B/J để quét theo cycle, Tier và unique-new-article feedback mà không chạy quá nguồn/ngày.

### Điều kiện

- Timezone/range ngày và source/topic policy có revision.
- Ngưỡng chủ đề có config; không hard-code.
- G/B feedback cho unique article count có contract/version.

### Trình tự test-first

1. RED tests cho Tier order và active/disabled/tombstone eligibility.
2. RED tests cho one periodic run/source/day và retry attempt.
3. RED tests cho stop/expand Tier theo unique count, không URL count.
4. RED tests cho source skip reason và scheduler availability.
5. RED tests cho AI/B feedback chờ và backpressure.
6. Hiện thực workflow activities/projections; chạy cloud-desktop-offline E2E.

### Hành vi cần hiện thực

- source eligibility query;
- deterministic Tier ordering;
- periodic run reservation;
- feedback-driven continuation;
- no-fake-run skip decision;
- source failure isolation;
- cloud schedule integration;
- metrics cho scheduler/Tier/cycle.

### Failure cases

- hai scheduler instance tranh cùng source;
- cycle retry sau process crash;
- B chưa xử lý xong duplicate outcomes;
- threshold/config đổi giữa cycle;
- source bị disable/remove sau reservation;
- không còn source/Tier nhưng chưa đủ target;
- desktop offline toàn cycle.

### Exit

- `CT-SRC-004/005`, `A-RULE-004..009/012/016` GREEN.
- Không source periodic bị chạy hai lần do race/retry.
- Tier sau không mở khi đã đủ; thiếu thì mở theo policy.
- Scheduler cloud chạy khi desktop offline.
- UI hiển thị run/skip/shortfall reason.

## 18. A6 — Supplemental collection và auto-discovery

### Mục tiêu

Bổ sung media theo job và tự tìm nguồn mới mà không phá tombstone, periodic counters hoặc source governance.

### A6.1. Supplemental

Test-first cases:

- request có scene/job/budget refs hợp lệ;
- không tăng periodic count;
- source tombstone bị chặn;
- result vẫn qua B/C/I;
- duplicate media/source evidence được giữ;
- deadline/budget hết trả partial/not-found rõ.

### A6.2. Auto-discovery

Chỉ bắt đầu khi:

- `SourceCandidate` contract được duyệt;
- Tier assignment policy có revision;
- allowed discovery methods/source kinds được chốt;
- audit/disposition UI tồn tại.

Test-first cases:

- candidate mới hợp lệ;
- canonical duplicate active/disabled;
- canonical match tombstone;
- unsafe locator/SSRF;
- insufficient evidence;
- policy revision đổi;
- concurrent discovery cùng candidate;
- `TST-SRC-RACE-001..004`: READY rồi nguồn được đăng ký, READY rồi tombstone, policy thay đổi, commit mất ACK. Assert disposition/ref/receipt/outbox đúng và terminal không mở lại; hai thứ tự register/remove đều giữ tombstone cuối cùng.
- auto-added source có audit/discovery evidence.

### Failure cases

- search/provider unavailable;
- candidate flood;
- false official account;
- source requires unsupported auth;
- policy không thể gán Tier;
- candidate được remove đồng thời lúc auto-register.

### Exit

- Supplemental và periodic metrics/state hoàn toàn tách.
- Auto-discovery không thể hồi sinh tombstone.
- Không auto-add nếu policy không cho quyết định Tier/source kind.
- User thấy source origin/evidence và có thể remove/restore.

## 19. A7 — UI, quan sát, hardening và nghiệm thu A

### Mục tiêu

Hoàn thiện lát cắt user, contract integration, reliability/security/performance trong phạm vi A và chuẩn bị handoff sang B.

### Công việc

1. Hoàn thiện Source/Run screens trên H theo spec.
2. SSE reconnect/resync, duplicate stream event và error detail.
3. Debug command cho source-test, collect/retry và package inspection.
4. Full adapter/contract/integration/E2E regression.
5. Fault injection DB/outbox/worker/I/B unavailable.
6. Security SSRF/XSS/secret/workspace/source-test proxy checks.
7. Scheduler/offline/99% measurement instrumentation.
8. Performance baseline cho source list/query/fetch/package/outbox.
9. Migration/rollback/adapter-disable drill.
10. Evidence report và user acceptance.

### E2E scenarios

- manual source → test → collect → package → B handoff;
- duplicate source command và concurrent metadata edit;
- remove → rediscovery blocked → restore;
- source partial failure giữa nhiều source;
- periodic Tier stop/expand;
- supplemental media request;
- source content revised;
- desktop offline cycle;
- worker crash/resume checkpoint;
- raw artifact upload outcome unknown;
- adapter version/config change.

### Exit

- Mọi mục trong `spec.md` mục 17 đạt hoặc được user chấp nhận là ngoài phạm vi release A.
- Không P0/P1 hoặc hard-gate/INV test fail/quarantine.
- UI p95/ACK được đo trên workload đã khóa; chưa claim nếu scale dataset chưa chốt.
- Scheduler instrumentation đủ cho monthly 99% claim; không dùng test tăng tốc thay vận hành thật.
- Known limitations/open items có owner và deadline.
- User duyệt phân hệ A trước khi B được coi là milestone tiếp theo.

## 20. Ma trận test theo work package

| Work package | Unit/domain | Contract | Integration | Fault/security | User/UI |
|---|---:|---:|---:|---:|---:|
| A0 | Thiết kế | Schema fixtures | Không | Threat corpus | Review spec |
| A1 | Source lifecycle | CT-SRC-001..003 | DB/outbox/API | concurrency/workspace | Source management |
| A2 | Run/checkpoint | WF/result/state | DB/journal/fake adapter | crash/stale generation | Run state |
| A3 | URL/policy | Adapter contract | Fixture/real source sandbox | SSRF/timeout/secret | Source test |
| A4 | Package/fingerprint | CT-SRC-006/B-C-I | Artifact/outbox/consumer | outcome unknown/duplicate | Package trace |
| A5 | Tier/eligibility | G/B/J feedback | Workflow/scheduler | race/offline/backpressure | Cycle progress |
| A6 | Candidate/supplemental | SourceCandidate/media request | Search/provider adapters | tombstone/flood/unsafe URL | Origin/evidence |
| A7 | Regression | Full A contracts | Full A E2E | Full fault/security | Acceptance |

## 21. Migration và rollback

### Schema migration

- Expand trước: thêm field/table/index optional.
- Migrate/backfill có checkpoint và metrics.
- Consumer/producer chạy tương thích hai version trong cửa sổ chuyển đổi.
- Contract switch qua config/version.
- Contract cũ chỉ bỏ sau khi workflow/run cũ kết thúc hoặc migrate.

### Adapter rollout

- Adapter/version mới mặc định không nhận toàn bộ source ngay.
- Chạy fixture + sandbox + canary source set.
- So sánh package/provenance/error với version cũ.
- Tăng phạm vi theo evidence.
- Rollback bằng adapter/config revision, không sửa lịch sử package.

### Rollback constraints

- Không rollback làm mất Source tombstone/revision/outbox/package đã commit.
- Không đưa checkpoint mới vào adapter cũ nếu semantics không tương thích.
- Không xóa observation/package chỉ vì adapter release bị thu hồi.
- Security incident ưu tiên disable adapter/source capability và rotate credential.

## 22. Quan sát và cảnh báo triển khai

Dashboard/alert trong phạm vi A cần phân biệt:

- source unavailable/degraded/disabled/tombstone;
- scheduler miss so với skipped sufficient;
- run waiting/running/partial/failed;
- fetch/extract/artifact/B-handoff failure;
- retry/backoff/rate limit;
- checkpoint lag/stall;
- outbox lag;
- package reject/incomplete trend;
- adapter error spike/version regression;
- SSRF/security rejection;
- credential unavailable, không hiển thị secret.

Ngưỡng alert cụ thể là config sau baseline; event critical như secret leak suspicion hoặc tombstone bypass không chờ statistical threshold.

## 23. Resource và performance plan

Trước production cần đo:

- fetch concurrency theo source/domain;
- response byte/parse memory;
- connection pool và DB write/outbox load;
- artifact upload bandwidth;
- queue wait và cycle duration;
- package throughput;
- source error/rate-limit pattern;
- index/query latency trên scale dataset;
- cloud cost phát sinh trong phạm vi R20.

Admission control phải tách theo adapter/domain để một nguồn chậm không chiếm toàn worker. Không đặt concurrency/timeout số cụ thể trước benchmark.

## 24. Security completion checklist

- URL được normalize và resolve an toàn ở mọi redirect.
- Source-test endpoint không trở thành open proxy.
- Network destination policy test cả IPv4/IPv6/alternate representation.
- Response size/time/content-type limits có test.
- HTML/text/media metadata được coi không tin cậy.
- UI escape nội dung nguồn.
- Credential handle scope đúng adapter/source/workspace.
- Secret canary scan sạch ở log/event/trace/history/error.
- Workspace isolation test dương/âm.
- Dependency/adapter version có vulnerability/license evidence ở release.

## 25. Handoff sang các phân hệ khác

### Sang B

- immutable package ref/schema/version;
- source/run/provenance/fingerprint;
- raw artifact ref/warnings;
- at-least-once event semantics;
- B deduplicate và trả outcomes mà G dùng cho threshold.

### Sang C/I

- media discovery/provenance;
- raw byte intent/hash/type;
- artifact operation/receipt;
- không tạo MediaAsset hoặc tự quản Drive path.

### Sang G/H

- run state/counters/checkpoint/error;
- command receipt/operation/correlation;
- events/projections cho cycle/UI;
- source skip/health reason.

### Sang J

- adapter capability/config requirements;
- credential handle request;
- quota/rate-limit/health observations;
- không gửi secret trong record.

Handoff contract thay đổi breaking phải qua versioning và consumer test trước rollout.

## 26. Rejection criteria

Không chấp nhận implementation nếu:

- A ghi trực tiếp Article/Event/MediaAsset/workflow/storage tables của module khác;
- one-run/day được tính bằng timestamp không có timezone/policy revision;
- URL count được dùng thay unique article count;
- retry tạo periodic run mới;
- source remove bị xóa vật lý hoặc có thể auto-add lại;
- query/UI tự kích hoạt fetch ngầm;
- package không có provenance hoặc tham chiếu byte bằng path tùy ý;
- raw secret/authorization nằm trong log/event/history;
- fetcher cho phép private/link-local/metadata destination;
- checkpoint tiến trước durable package;
- event publish ngoài outbox làm mất event sau crash;
- adapter parser nằm trong domain core;
- test chỉ dùng happy path hoặc mock để đóng integration gate;
- implementation được viết trước RED test;
- open policy bị hard-code bằng default không được duyệt.

## 27. Definition of Done cho phân hệ A

1. `spec.md` được user phê duyệt.
2. A0-A7 đạt exit gate trong phạm vi release đã chọn.
3. Mọi `A-RULE-001..016`, Source/Run transition và acceptance criteria có test.
4. Contract fake và real adapter cùng đạt adapter suite.
5. Package/event handoff với B/C/I/G/H/J idempotent và versioned.
6. Fault injection không gây mất package, duplicate side effect hoặc checkpoint sai.
7. Security checklist đạt, không có P0/P1.
8. UI/debug/observability đủ để user kiểm tra từng source/run.
9. Migration/rollback/adapter disable đã thử.
10. Evidence record, known limitations và open items cập nhật.
11. User nghiệm thu phân hệ A trước khi chuyển sang kế hoạch chi tiết B.

## 28. Kế hoạch phê duyệt theo lát cắt

| Checkpoint | User duyệt gì | Không cần duyệt lại |
|---|---|---|
| A-CP1 | Source fields, lifecycle, UI management và tombstone | Chính sách R15/R24 đã chốt |
| A-CP2 | Run purpose, trạng thái, log và debug | Một nguồn lỗi không dừng lô đã chốt |
| A-CP3 | Package/provenance hiển thị và handoff | Không fact-check đa nguồn đã chốt |
| A-CP4 | Tier/cycle behavior với config thật | R04/R23 đã chốt; chỉ duyệt giá trị/config còn mở |
| A-CP5 | Supplemental và source discovery | R05/FR-SRC-004 đã chốt; duyệt contract/Tier policy |
| A-CP6 | Full A acceptance/evidence | Chuyển sang B |

## 29. Các blocker trước implementation

| Blocker | Mức | Cách giải quyết |
|---|---|---|
| M0/approval | ĐÃ ĐÓNG ngày 13-09-2026 | Không còn là blocker; quyền hiện tại vẫn chỉ giới hạn M1 |
| M1/M2 nền chưa tồn tại | Dependency | Hoàn thành proof và core contracts/infrastructure |
| SourceCandidate contract | ĐÃ ĐÓNG ở tài liệu; A6 production vẫn cần Tier/discovery policy | Kiểm tra fixture bám `CT-SRC-003A`/`CT-STATE-002A` ở A0 |
| Tier/source baseline chưa chốt | Chặn production discovery/cycle acceptance | Nghiên cứu + policy revision/user duyệt |
| Giá trị timezone/ngưỡng chủ đề chưa chốt | Chặn production schedule/Tier acceptance, không chặn core state | Xuất bản config revision trước A5 exit; semantics đã khóa ở `CT-SRC-004` |
| Adapter access/quota chưa kiểm chứng | Chặn real integration | Provider/source proof theo từng adapter |

## 30. GIẢ ĐỊNH

**Không có GIẢ ĐỊNH chưa được xác nhận nào được dùng để cam kết kế hoạch sẽ chạy hoặc đạt lịch.**

Các package names, adapter count, schema/table names vật lý và tool versions trong implementation tương lai chưa phải quyết định nếu chưa được M1/M2 khóa. Mọi ví dụ cấu trúc trong tài liệu này là **ĐỀ XUẤT**, không phải mã nguồn hoặc chỉ thị cài đặt.

## 31. Kết luận

Kế hoạch chia phân hệ A thành tám work package có dependency rõ. A1-A5 có thể được chuẩn bị trên các contract đã chốt sau M0-M2; A6 auto-registration production bị chặn có chủ đích cho tới khi Tier/discovery policy được quyết định, còn `SourceCandidate` đã có contract. Không phần nào cho phép A chiếm trách nhiệm của B/C/G/H/I/J hoặc bỏ qua test-first, provenance, outbox, fencing, SSRF và cleanup safety.
