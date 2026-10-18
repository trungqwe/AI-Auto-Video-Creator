# Kế hoạch triển khai Phân hệ A — Nguồn và thu thập nội dung

- **Mã gói**: IMPL-PLAN-A
- **Ngày lập**: 18/10/2026
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`) và chỉ thị user duyệt Phần B ngày 18/10/2026 (D0–D10).
- **Trạng thái**: kế hoạch; kích hoạt sản xuất vẫn bị chặn (`PRODUCTION_ACTIVATION_BLOCKED`).
- **Danh sách slice**: `docs/implementation/a/slices.md`.

## 1. Nguồn chuẩn

- `docs/modules/a-source-collection/spec.md`
- `docs/modules/a-source-collection/implementation-plan.md`
- `docs/11-roadmap.md` §9 (dòng 287–350) và §23
- `docs/09-contracts/04-source-content-contracts.md` (CT-SRC-001..006, CT-SRC-003A, CT-CNT-001)
- `docs/09-contracts/12-state-machines.md` (CT-STATE-001, CT-STATE-002, CT-STATE-002A)
- `docs/09-contracts/02-domain-events.md` (CT-EVT-002, CT-EVT-003)
- `docs/09-contracts/03-workflow-and-execution.md` (CT-WF-003, CT-WF-006)
- `docs/09-contracts/10-storage-contracts.md` (CT-STO-001)
- `docs/10-test-strategy.md` (dòng 526–545 và 1184–1199)
- `docs/parallel-delivery/bindings/README.md` và các binding ở §5
- `docs/parallel-delivery/errata/m3-a.md`
- `docs/parallel-delivery/ownership-and-locks.yaml` (`PATH-SRC-SOURCE-INGESTION`, `LOCK-SRC-SOURCE-INGESTION`, `PATH-COMPOSITION-ROOT`)
- `docs/05-technology-research.md` (dòng 116–139)

Khi mâu thuẫn, thứ tự ưu tiên: `docs/09-contracts` → binding và fixture CP1 → errata m3-a → spec và implementation-plan của A. `docs/parallel-delivery/M3-A-contract-freeze.md`, `M3-A-execution-package.md`, `M3-A-test-plan.md` chỉ là lịch sử, không chép.

## 2. Đính chính áp dụng (errata CP1)

- (a) Source theo CT-STATE-001 `ACTIVE ↔ DISABLED → REMOVED_TOMBSTONE`, có cạnh DISABLED→ACTIVE; restore theo CT-SRC-003 (về trạng thái trước remove nếu policy cho phép, ngược lại DISABLED kèm lý do).
- (b) CollectionRun dùng bảng đầy đủ CT-STATE-002, gồm `WAITING_RECONCILIATION`, `RETRY_EXHAUSTED`, `SOURCE_INACTIVE`; vòng đời Cycle `PLANNED → RUNNING → COMPLETED / COMPLETED_PARTIAL / FAILED` thuộc G.
- (c) Package chỉ khoá trường cấp 1 và kiểu theo `docs/parallel-delivery/bindings/a-b-collected-document.json`; không khoá enum `extraction_disposition`, trường con của `http_observation`, enum loại media hay bước của `provenance_chain`.
- (d) Chỉ dùng test ID có trong catalog: TST-INT-INV-015, TST-SEC-INV-020, TST-COL-END-001..004, TST-COL-PKG-001..004, TST-SRC-RACE-001..004; SSRF mô tả theo hành vi CT-SRC-001 và CT-SEC-003 tới khi catalog có ID.
- (e) Bằng chứng theo D4 tại `docs/delivery-evidence/<task-id viết thường>/report.md`; không ghi vào thư mục evidence đã nghiệm thu dưới `docs/milestones`; không dùng tệp trạng thái PASS điền sẵn.
- (f) Path/lock đã đăng ký: `PATH-SRC-SOURCE-INGESTION`, `LOCK-SRC-SOURCE-INGESTION`.
- (g) Câu “chưa được thực hiện bước code” trong implementation-plan cũ và câu “quyền code chỉ áp dụng M1” ở roadmap §27 đã được D3 thay; tên package logic ĐỀ XUẤT ở §5 implementation-plan được chốt theo D1 tại §4.

## 3. Năng lực và aggregate

| Năng lực roadmap §9 (A) | Slice | Ghi chú |
| --- | --- | --- |
| 1. Thêm/sửa/bật tắt/remove/restore nguồn trên UI | A-03, A-09, A-17 | Màn hình và route: CONV-A-03, CONV-A-04 |
| 2. Tombstone chặn auto-discovery | A-07, A-10, A-09 | Ngăn tái phát hiện hoặc tái đăng ký nguồn đã xoá |
| 3. Cycle theo chủ đề, Tier, ngưỡng | A-15 | Phía A; cycle và CollectionDecision thuộc G (CONV-A-06) |
| 4. SourceCandidate/auto-registration, package tối thiểu, multi-topic count | A-07, A-10, A-02 | Bộ đếm đa chủ đề thuộc G/B theo CT-SRC-004 |
| 5. RSS/trang nguồn theo adapter được duyệt | A-12, A-13, A-11 | Adapter thật: CP7 |
| 6. Snapshot bằng chứng, extraction candidate, media discovery | A-13, A-14 | Handoff media sang C chờ binding CT-MED-001 (CONV-A-07) |
| 7. Partial run, checkpoint, retry, lỗi nguồn độc lập | A-05, A-06, A-11 | Checkpoint chỉ tiến qua item bền vững |
| 8. Scheduler cloud khi desktop offline | A-18 | Độc lập mã; chạy thật: CP7 |

Aggregate A sở hữu (theo `modules.A` trong `ownership-and-locks.yaml`): SourceCandidate, Source, CollectionRun, CollectionAttempt, CollectedDocument; bản ghi nội bộ A: CollectionCheckpoint, FetchObservation, source health observation. A không sở hữu: CollectionCycle/CollectionDecision (G), Article/ArticleRevision/Event/EventUpdate (B), MediaAsset (C), ArtifactVersion/ArtifactLocation (I), ConfigRevision/SecretHandle/ExternalAccount (J). A không ghi bảng của phân hệ khác.

## 4. Vị trí mã theo D1

| Đường dẫn | Nội dung |
| --- | --- |
| `src/source_ingestion/domain/` | aggregate, transition, validator thuần |
| `src/source_ingestion/application/` | command handler và service |
| `src/source_ingestion/ports/` | Protocol |
| `src/source_ingestion/adapters/` | secure fetch, extractor tham chiếu, in-memory |
| `src/source_ingestion/worker/` | activity handler |
| `src/source_ingestion/projections/` | query read-only |
| `tests/unit/collection/` | unit |
| `tests/integration/collection/` | tích hợp in-process |

Quy tắc: import root `src/` (`import source_ingestion...`), cấm tiền tố `src.`; không tạo `src/source_ingestion/storage`, `orchestration`, `ui` và không tạo `src/storage`, `src/orchestration`, `src/ui`; gói persistence (PostgreSQL) chưa tạo cho tới khi CONV-A-01 có migration.

| Module controlplane tái dùng | Dùng cho |
| --- | --- |
| `controlplane.domain.interfaces.uow.IUnitOfWork` | UoW in-memory (A-08) |
| `controlplane.domain.interfaces.outbox.IOutboxWriter` | outbox dedup theo `deduplication_id` |
| `controlplane.domain.interfaces.repository.IRepository` | repository |
| `controlplane.domain.events.contracts.DomainEvent`, `ensure_safe_event_payload` | event của A |
| `controlplane.domain.concurrency.RevisionConflictError` | expected revision |
| `controlplane.domain.common.contracts.ProblemDetail` | lỗi có cấu trúc |
| `controlplane.application.idempotency.canonicalization.request_hash` | idempotency |
| `controlplane.domain.orchestration.ExecutionGrant` | grant của G |
| `controlplane.domain.config_security.SecretHandle` | credential handle của J |

A chỉ import, không sửa, không dựng bản trùng.

## 5. Contract dùng và cung cấp

| Contract | Vai trò A | Binding/fixture |
| --- | --- | --- |
| CT-SRC-006 `CollectedDocumentPackage` | cung cấp (producer) | `docs/parallel-delivery/bindings/a-b-collected-document.json`; `tests/fixtures/contracts/a-b-collected-document/payloads.json` |
| CT-CNT-001 `ResolveCollectedDocument` | dùng (B quyết định và trả kết quả, A không quyết định) | cùng hai tệp trên |
| CT-EVT-002/CT-EVT-003 DomainEvent | cung cấp event của A | `docs/parallel-delivery/bindings/domain-event-envelope.json`; `tests/fixtures/contracts/domain-event-envelope/payloads.json` |
| CT-WF-003/CT-WF-006 ActivityRequest/ActivityResult | dùng request, cung cấp result | `docs/parallel-delivery/bindings/g-activity-execution.json`; `tests/fixtures/contracts/g-activity-execution/payloads.json` |
| CT-STO-001 DeclareArtifactVersionRequest/Result | dùng (I) | `docs/parallel-delivery/bindings/i-artifact-version.json`; `tests/fixtures/contracts/i-artifact-version/payloads.json` |
| CT-SRC-001..005, CT-SRC-003A | A sở hữu command | chưa có binding riêng; slice bám văn bản `docs/09-contracts/04-source-content-contracts.md` |

1. Seam chưa có binding, xử lý fail-closed: A→C media discovery (CT-MED-001), J→A configuration bundle (CT-CFG-002), H↔G control API (`CONTRACT-CONTROL-API-STREAM`). Slice chỉ dùng port A-local và fake, không wiring thật; mở binding qua CONV-A-07.
2. Event A phát qua transactional outbox, at-least-once, consumer tự dedup: SourceRegistered, SourceMetadataUpdated, SourceRemoved, SourceRestored, SourceCandidateDiscovered, SourceCandidateResolved, CollectionRunStarted, CollectedDocumentAvailable, CollectionRunCompleted, CollectionRunFailed (spec §8); không chứa secret, raw byte hay signed URL dài hạn.
3. Tương thích: `additive_optional_only`; consumer bỏ qua trường lạ; binding version không hỗ trợ thì fail-closed theo CT-CMN-012; đổi phá vỡ phải tăng major binding qua MIGRATE.

## 6. Ánh xạ exit gate roadmap §9 sang slice

G1–G7 là exit gate của roadmap §9; T1–T4 là mục “Test và dữ liệu bắt buộc” liên quan tới A.

| Exit gate / dữ liệu bắt buộc | Vai trò A | Slice | Cách kiểm |
| --- | --- | --- | --- |
| G1. User thêm nguồn và theo dõi lượt/stage/lỗi trên UI | command, query, event phía A | A-09, A-17, A-05 | pytest của A-09, A-17, A-05; màn hình/route ở CONV-A-03, CONV-A-04; E2E UI chạy ở gói hội tụ |
| G2. Article/Event truy ngược source, fetch evidence, revision | package có `source_revision`, `provenance_chain`, `raw_snapshot_ref` | A-02, A-13, A-14 | pytest A-02/A-13/A-14 với fixture a-b-collected-document; phần Article thuộc kế hoạch B |
| G3. Bài repost không tạo article/script mới | B quyết định; A chỉ tạo package và fingerprint mới mỗi lần quan sát | A-13 | pytest A-13 khẳng định package không có trường quyết định của B |
| G4. Event update không đồng nhất với nguồn đăng lại | ngoài A (A-RULE-011) | A-13, A-19 | như G3; A-19 kiểm A-RULE-011 có test trực tiếp |
| G5. Một nguồn lỗi không dừng cycle | cô lập lỗi từng source run | A-11, A-18 | pytest A-11 nhiều nguồn có một nguồn lỗi; cycle G ở CONV-A-06 |
| G6. Test contract/integration/failure/security A-B đạt | phía A | A-02, A-04, A-05, A-10, A-11, A-12, A-14, A-19 | TST-COL-PKG-001..004 → A-02; TST-COL-END-001..004 → A-05; TST-SRC-RACE-001..004 và TST-INT-INV-015 → A-10; SSRF → A-04, A-12; tích hợp PostgreSQL sau CONV-A-01 |
| G7. User duyệt A-B và `R1 Content Alpha` | không tự quyết | — | pendingUserCheckpoint (§7) |
| T1. SSRF, redirect, MIME giả, HTML lỗi, timeout, nguồn không truy cập được | A | A-04, A-12, A-13 | pytest với transport và resolver giả |
| T2. Scheduler đủ ngưỡng không mở Tier tiếp | A cung cấp thứ tự và quyết định dừng | A-15 | pytest A-15; ghi SKIPPED_SUFFICIENT ở G (CONV-A-06) |
| T3. Desktop offline không dừng collection cloud | A không phụ thuộc mã desktop | A-18 | pytest A-18 kiểm import; chạy thật ở CP7 |
| T4. News Corpus version đầu tiên | corpus dùng chung | A-13 (HTML mẫu nội tuyến trong test) | corpus có version ở CONV-A-08 |

Mọi A-RULE-001..016 có test trực tiếp, kiểm bằng A-19 (spec §17 mục 1).

## 7. Mục mở và mặc định (D8)

| Mục | Mặc định cho slice | Lý do | Trạng thái |
| --- | --- | --- | --- |
| MODULE-A-OPEN-001 `source_kind` | tập giá trị là input policy; `rss_feed`, `web_page` chỉ dùng trong fixture test; thiếu policy → `INPUT_NOT_READY` | spec §18 cấm default ẩn | pendingUserCheckpoint |
| MODULE-A-OPEN-002 nguồn baseline, tiêu chí Tier | Tier nhận từ user/policy; thiếu Tier policy thì candidate giữ `WAITING_POLICY`, auto-registration production `NOT_READY` | CT-SRC-003A | pendingUserCheckpoint |
| MODULE-A-OPEN-003 ngưỡng tin mới từng chủ đề | A nhận ngưỡng/bộ đếm từ G, không lưu hằng | CT-SRC-004; roadmap §9 cấm hard-code | pendingUserCheckpoint |
| MODULE-A-OPEN-004, ROADMAP-OPEN-004, QUALITY-OPEN-014, TEST-OPEN-009 múi giờ | A nhận `business_date` do G suy ra, không tự tính | CT-SRC-004 | pendingUserCheckpoint trước lịch production |
| MODULE-A-OPEN-005 ngưỡng nội dung, policy title theo source kind | ExtractionPolicy có revision là input; policy fixture chỉ trong test | CT-SRC-006; roadmap §9 | pendingUserCheckpoint |
| MODULE-A-OPEN-006 | đã đóng theo CT-SRC-003A/CT-STATE-002A | spec §18 | không còn chặn |
| MODULE-A-OPEN-007, ROADMAP-OPEN-010 retention | `retention_class` lấy từ policy, I quyết | A-RULE-015 | pendingUserCheckpoint |
| MODULE-A-OPEN-008 adapter/quyền truy cập thật | transport giả và extractor stdlib tham chiếu chỉ cho fixture | implementation-plan §15 | pendingUserCheckpoint, CP7 |
| MODULE-A-OPEN-009 timeout/retry/backoff/concurrency | FetchPolicy/RetryPolicy là input, không số mặc định | spec §18 | pendingUserCheckpoint, đo ở CP7 |
| MODULE-A-OPEN-010, QUALITY-OPEN-002 thời gian cycle | không tuyên bố hiệu năng | roadmap §9 | pendingUserCheckpoint, CP7 |
| ROADMAP-OPEN-005, QUALITY-OPEN-005 hot/trending | ngoài A (B/D) | roadmap §9 | ghi nhận, không xử lý |
| Enum `extraction_disposition` | giá trị A-local `SUCCESS`, `PARTIAL`, `FAILED` ghi GIẢ ĐỊNH; validator chỉ kiểm chuỗi không rỗng; fixture CP1 dùng `SUCCESS` | binding chỉ khoá kiểu (errata #3) | quyết định D8 của kế hoạch |
| State machine Source/Run/Candidate | bảng transition đặt trong `src/source_ingestion/domain`, không sửa `src/controlplane/domain/statemachine` | A sở hữu aggregate; state machine dùng chung là tài nguyên hội tụ | quyết định D8; đăng ký chung qua CONV-A-05 |
| Persistence | UoW in-memory implement `IUnitOfWork`; PostgreSQL sau CONV-A-01 | migration là tài nguyên dùng chung | quyết định D8 |
| Bố cục test | không tạo `__init__.py` trong thư mục test; tên tệp `test_aNN_*.py` duy nhất | tránh trùng tên module test (đã có gói `tests/unit/security`) | quyết định D8 |

### Danh sách chờ user (pendingUserCheckpoint)

- MODULE-A-OPEN-001, 002, 003, 004, 005, 007, 008, 009, 010 (giá trị policy/config thật).
- USER-CKPT-D9-D10: thư viện ở §8 và cách dựng lại runtime.
- CP7 theo D5: các việc ở §9.
- Checkpoint A-CP1..A-CP6 của implementation-plan §28.
- Exit gate G7: user duyệt phân hệ A-B và `R1 Content Alpha`.

Không mục nào ở trên được ghi là đã duyệt; slice chỉ dùng giá trị fixture trong test và trả `INPUT_NOT_READY`/`NOT_READY` khi thiếu policy thật.

## 8. Thư viện (D10)

Slice A-01..A-19 không thêm thư viện; chỉ dùng stdlib (`dataclasses`, `enum`, `ipaddress`, `urllib.parse`, `html.parser`, `hashlib`, `json`, `datetime`, `ast`) và module controlplane ở §4. Không dùng `pydantic` hay `temporalio` trong A dù đã có trong lock (giữ domain thuần; đăng ký activity Temporal thuộc G).

Thư viện đề xuất cho USER-CKPT-D9-D10 (trước CP-2b, sau TECH-POC-001); phiên bản lấy từ `docs/05-technology-research.md` dòng 116–139:

| Thư viện đề xuất | Lý do | Ghi chú |
| --- | --- | --- |
| `feedparser==6.0.14` | parse RSS/Atom, BSD-style | đề xuất cho USER-CKPT-D9-D10 |
| `trafilatura==2.2.0` | extractor chính, Apache-2.0 | đề xuất cho USER-CKPT-D9-D10 |
| `jusText==3.0.2` | fallback/đối chiếu boilerplate, BSD-2-Clause | đề xuất cho USER-CKPT-D9-D10 |
| `Scrapy==2.19.0` | crawler nhiều nguồn, BSD-3-Clause | chỉ khi POC chứng minh cần |
| `playwright==1.63.0` | fallback trang động, Apache-2.0 | cần browser binary nên ảnh hưởng cách dựng runtime |

Không đề xuất RSSHub (dịch vụ AGPL-3.0, không phải gói Python), Mozilla Readability (JavaScript), Newspaper3k (release 0.0.9 từ 2014). HTTP client cho fetch boundary chưa đề xuất phiên bản; mở `IMPL-PLAN-A-OPEN-001` để chọn qua TECH-POC-001 (cần kiểm soát DNS từng hop). Phiên bản phải xác minh lại ở checkpoint; không dùng `latest`.

## 9. Việc cần tài nguyên thật (CP7)

Chỉ chạy sau khi user duyệt D5; tài khoản/credential chỉ qua secret broker của J, không mở, chép hay in bí mật.

- CP7-A-01: fetch nguồn thật cho TECH-POC-001 (RSS đầy đủ, RSS rút gọn, HTML tĩnh, trang động, trang lỗi).
- CP7-A-02: adapter cần đăng nhập và nguồn chính thức của người nổi tiếng (US-A-007).
- CP7-A-03: raw snapshot lên Drive thật qua I (`LOCK-EXTERNAL-DRIVE`).
- CP7-A-04: scheduler cloud chạy khi desktop tắt (US-A-008, QR-AVL-001) và đo 99% schedule/tháng (QR-AVL-003), chạy dài từ 12 giờ.
- CP7-A-05: benchmark timeout/retry/concurrency/thời gian cycle (MODULE-A-OPEN-009/010, QR-PERF-005/006/008).

## 10. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

| Mã | Tài nguyên dùng chung | Yêu cầu | Slice A liên quan |
| --- | --- | --- | --- |
| CONV-A-01 | migration | bảng source, định danh locator/tombstone, source_candidate, collection_run (unique workspace + source + business_date + periodic, không chứa policy revision), collection_attempt, collection_checkpoint, fetch_observation, collected_document_package; index theo implementation-plan §9; sau đó mở slice A tạo `src/source_ingestion/persistence` | A-08 |
| CONV-A-02 | composition root (`PATH-COMPOSITION-ROOT`: `src/main.py`, `src/controlplane/api/main.py`) | wiring command handler, query, worker A | A-09, A-17, A-18 |
| CONV-A-03 | control API | route RegisterSource, UpdateSourceMetadata, RemoveSource, RestoreSource, TestSource và query; cần binding H↔G | A-09, A-17 |
| CONV-A-04 | UI shell (H, `ui/dist`, `App.tsx`) | bảng Source, bảng CollectionRun, SSE theo spec §12 | A-17 |
| CONV-A-05 | state machine dùng chung | xác nhận/đăng ký transition Source, CollectionRun, SourceCandidate của A (`LOCK-CONTRACT-STATE-MACHINES`) | A-03, A-05, A-07 |
| CONV-A-06 | workflow G | PlanCollectionCycle (CT-SRC-004), CollectionDecision SKIPPED_SUFFICIENT, bộ đếm unique từ B, đăng ký activity A, lịch cloud | A-15, A-18 |
| CONV-A-07 | registry binding | mở binding A→C CT-MED-001, J→A CT-CFG-002, H↔G control API | A-08, A-16 |
| CONV-A-08 | catalog test và corpus dùng chung | thêm ID SSRF vào `docs/10-test-strategy.md`; News Corpus và malicious URL corpus có version dưới `tests/fixtures` | A-04, A-12, A-13 |
| CONV-A-09 | outbox/event catalog | đăng ký 10 event của A với publisher dùng chung | A-09, A-10, A-11 |

## 11. Thứ tự slice (DAG)

- Đợt 1: A-01.
- Đợt 2 (song song): A-02, A-03, A-04, A-05, A-06, A-07.
- Đợt 3: A-08, A-12, A-15.
- Đợt 4: A-09, A-11, A-13, A-14, A-17.
- Đợt 5: A-10, A-16, A-18.
- Đợt 6: A-19.

A-01 giữ `LOCK-SRC-SOURCE-INGESTION` vì tạo cây gói; các slice khác giữ `LOCK-<taskId>` và sở hữu tệp riêng nên chạy song song được. dependsOn chi tiết nằm trong `docs/implementation/a/slices.md`.

## 12. Ngoài phạm vi

Quyết định Article/revision/duplicate, phân loại chủ đề cuối, fact-check đa nguồn, media catalog, script, render, Google Sheets làm nguồn dữ liệu (spec §20).
