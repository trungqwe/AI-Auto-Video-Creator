# Danh sách slice — Phân hệ A (IMPL-PLAN-A)

Tài liệu này biên dịch kế hoạch triển khai Phân hệ A từ `docs/implementation/a/plan.md` thành 19 work package slice độc lập, có thể kiểm chứng riêng biệt.

## Quy ước chung

- ownedPaths chỉ trong `src/source_ingestion/**`, `tests/unit/collection/**`, `tests/integration/collection/**` và tệp bằng chứng `docs/delivery-evidence/<task-id viết thường>/report.md`.
- Test-first: tạo khung module tối thiểu để import được, chạy test và ghi RED do assertion sai oracle; lỗi import/collection không phải RED hợp lệ; sau đó GREEN.
- Không sửa migration, composition root, lockfile, tests/m2, ui/dist, App.tsx, state machine dùng chung hay control API; không thêm thư viện; không gọi mạng hay dịch vụ thật (slice có mã fetch phải monkeypatch `socket.create_connection` và `socket.getaddrinfo` để ném lỗi trong test).
- Dùng fixture CP1 và fake cho phân hệ khác; tái dùng module controlplane trong plan §4, không dựng bản trùng.
- Không tạo `__init__.py` trong thư mục test; tên tệp test `test_aNN_*.py`; docstring đầu tệp test liệt kê mã A-RULE/TST bao phủ (dòng coveredIds).
- Lệnh python chạy bằng interpreter khoá của lane.

## Khuôn slice

Thứ tự trường bắt buộc trong từng slice:
- Tiêu đề slice dạng A-NN và tên gợi nhớ
- Trường kind là `work_package_slice`
- Danh sách ownedPaths với thụt lề 2 dấu cách và mục cuối luôn là report.md
- Trường dependsOn liệt kê slice tiền đề trên cùng một dòng
- Trường resourceLocks khóa tài nguyên tương ứng
- Danh sách bindingRefs trỏ tệp binding hoặc fixture thực tế
- Khối acceptance với requirement, instrument và counterexample
- Danh sách testCommands với git diff --check và pytest tệp test thuộc ownedPaths
- Trường coveredIds liệt kê mã quy tắc và kiểm thử bao phủ

## Slice

### A-01: Khung gói source_ingestion và ranh giới import
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/__init__.py`
  - `src/source_ingestion/domain/__init__.py`
  - `src/source_ingestion/application/__init__.py`
  - `src/source_ingestion/ports/__init__.py`
  - `src/source_ingestion/adapters/__init__.py`
  - `src/source_ingestion/worker/__init__.py`
  - `src/source_ingestion/projections/__init__.py`
  - `tests/unit/collection/test_a01_package_layout.py`
  - `docs/delivery-evidence/a-01/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-SRC-SOURCE-INGESTION`
- bindingRefs:
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
- acceptance:
  - requirement: tạo gói và 6 gói con chỉ có docstring; test dùng `ast`/`pathlib` quét mọi `src/source_ingestion/**/*.py`: import được `source_ingestion` từ root src/, không `import src.`/`from src.`, không import `ingestion`, `catalog`, `creative`, `voice`, `render`, `psycopg`, `temporalio`, `controlplane.infrastructure`, `controlplane.ui`, `controlplane.api`; không có thư mục `storage`, `orchestration`, `ui` dưới `src/source_ingestion`.
  - instrument: `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider`
  - counterexample: dùng `from src.source_ingestion`, import gói B/C hoặc driver DB, dựng `src/source_ingestion/storage` trùng I.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider`
- coveredIds: không

### A-02: Validator CollectedDocumentPackage hai lớp (CT-SRC-006)
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/domain/package.py`
  - `tests/unit/collection/test_a02_collected_document_package.py`
  - `docs/delivery-evidence/a-02/report.md`
- dependsOn: `A-01`
- resourceLocks: `LOCK-A-02`
- bindingRefs:
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
  - `tests/fixtures/contracts/a-b-collected-document/payloads.json`
- acceptance:
  - requirement: hằng đặc tả trường cấp 1 (tên, kiểu, required, enum); lớp 1 trả lỗi `code` thuộc `missing_required`/`wrong_type`/`enum_violation` kèm `field` (datetime kiểm RFC3339 bằng `datetime.fromisoformat`, integer không nhận bool/chuỗi); test so hằng với binding JSON để bắt drift và chạy mọi case valid/invalid của fixture đúng `expected_error`. Lớp 2 nhận ExtractionPolicy có revision: text rỗng → `incomplete` kèm reason; title bắt buộc theo source kind trong policy; thiếu policy → INPUT_NOT_READY; thiếu `published_at_candidate` không là lỗi schema; `extraction_disposition` chỉ kiểm chuỗi không rỗng.
  - instrument: `python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider`
  - counterexample: chấp nhận payload thiếu `provenance_chain`; khoá enum extraction tự đặt; mặc định title bắt buộc khi thiếu policy; `candidate` khi text rỗng; hằng lệch binding mà test vẫn xanh.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider`
- coveredIds: TST-COL-PKG-001..004, A-RULE-010

### A-03: Aggregate Source và vòng đời (CT-STATE-001, CT-SRC-001..003)
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/domain/source.py`
  - `tests/unit/collection/test_a03_source_lifecycle.py`
  - `docs/delivery-evidence/a-03/report.md`
- dependsOn: `A-01`
- resourceLocks: `LOCK-A-03`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: Source frozen dataclass, status ACTIVE/DISABLED/REMOVED_TOMBSTONE; ACTIVE↔DISABLED, ACTIVE/DISABLED→REMOVED_TOMBSTONE; rời tombstone chỉ bằng restore về trạng thái trước remove nếu policy cho phép, ngược lại DISABLED kèm reason; mỗi mutation tăng revision, ghi actor/thời điểm; expected revision cũ ném `controlplane.domain.concurrency.RevisionConflictError`; update chỉ đổi Tier, topic/tag, ghi chú, bật/tắt, metadata quản trị; Tier/source_kind kiểm theo tập giá trị policy truyền vào.
  - instrument: `python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider`
  - counterexample: thiếu cạnh DISABLED→ACTIVE; restore luôn về ACTIVE; revision cũ ghi đè im lặng; source_kind hard-code.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider`
- coveredIds: CT-STATE-001, A-RULE-003

### A-04: Chuẩn hoá locator và chặn SSRF
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/domain/locator.py`
  - `tests/unit/collection/test_a04_locator_ssrf.py`
  - `docs/delivery-evidence/a-04/report.md`
- dependsOn: `A-01`
- resourceLocks: `LOCK-A-04`
- bindingRefs:
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
- acceptance:
  - requirement: `canonicalize_locator` bằng `urllib.parse`: chỉ http/https, host chữ thường, IDNA, bỏ fragment và cổng mặc định; `validate_destination(host, resolved_ips)` bằng `ipaddress` chặn loopback, private, link-local, multicast, reserved, unspecified, metadata 169.254.169.254, IPv4-mapped IPv6 và dạng IP thay thế (`2130706433`, `0x7f000001`, `127.1`); resolver tiêm vào, test không gọi DNS thật.
  - instrument: `python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider`
  - counterexample: chấp nhận `file://`, `http://127.1/`, `http://[::ffff:127.0.0.1]/`, `http://0x7f000001/`; test gọi `socket.getaddrinfo` thật.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider`
- coveredIds: A-RULE-013, CT-SRC-001, CT-SEC-003

### A-05: CollectionRun và CollectionAttempt (CT-STATE-002)
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/domain/collection_run.py`
  - `tests/unit/collection/test_a05_collection_run_states.py`
  - `docs/delivery-evidence/a-05/report.md`
- dependsOn: `A-01`
- resourceLocks: `LOCK-A-05`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: purpose PERIODIC/SOURCE_TEST/SUPPLEMENTAL; khoá periodic `(workspace_id, source_id, business_date, periodic)` không chứa policy revision; attempt append-only với SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL/OUTCOME_UNKNOWN; đủ mọi dòng bảng CT-STATE-002 (WAITING_RETRY khi còn budget và nguồn bật; RETRY_EXHAUSTED/SOURCE_INACTIVE → COMPLETED_PARTIAL nếu đã commit package, ngược lại FAILED_FINAL; SCHEDULED gặp nguồn inactive → FAILED_FINAL không tạo attempt; OUTCOME_UNKNOWN → WAITING_RECONCILIATION; 4 nhánh reconcile); terminal không mở lại; quyết định terminal ghi policy revision, reason, checkpoint; retry budget nhận từ policy, không số mặc định.
  - instrument: `python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider`
  - counterexample: retry tạo run mới; attempt giả cho SCHEDULED inactive; unknown hết hạn bị đổi thành FAILED_FINAL hoặc retry; terminal quay lại RUNNING; policy revision trong khoá duy nhất.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider`
- coveredIds: TST-COL-END-001..004, A-RULE-004, A-RULE-005

### A-06: CollectionCheckpoint chỉ tiến qua item bền vững
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/domain/checkpoint.py`
  - `tests/unit/collection/test_a06_checkpoint.py`
  - `docs/delivery-evidence/a-06/report.md`
- dependsOn: `A-01`
- resourceLocks: `LOCK-A-06`
- bindingRefs:
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
- acceptance:
  - requirement: checkpoint có version, source/adapter revision, cursor, run/attempt ref, completeness, fingerprint; `advance_checkpoint(current, durable_item_ids, proposed)` chỉ tiến qua item đã commit bền vững; checkpoint_version khác semantics adapter bị từ chối; generation cũ không được tiến.
  - instrument: `python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider`
  - counterexample: checkpoint vượt item chưa commit; checkpoint cũ nạp vào adapter mới; worker generation cũ đẩy checkpoint.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider`
- coveredIds: A-RULE-009

### A-07: SourceCandidate (CT-SRC-003A, CT-STATE-002A)
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/domain/source_candidate.py`
  - `tests/unit/collection/test_a07_source_candidate.py`
  - `docs/delivery-evidence/a-07/report.md`
- dependsOn: `A-01`
- resourceLocks: `LOCK-A-07`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: DISCOVERED→VALIDATING→READY_FOR_REGISTRATION|MATCHED_EXISTING|BLOCKED_TOMBSTONE|REJECTED; READY→REGISTERED|MATCHED_EXISTING|BLOCKED_TOMBSTONE|REJECTED; thiếu policy giữ READY với WAITING_POLICY; terminal không mở lại; expected revision cũ → REVISION_CONFLICT không đổi state; identity trùng tombstone → BLOCKED_TOMBSTONE; không tự gán source kind/topic/Tier.
  - instrument: `python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider`
  - counterexample: candidate trùng tombstone thành REGISTERED; thiếu policy tự gán Tier; terminal bị đánh giá lại.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider`
- coveredIds: A-RULE-002, TST-INT-INV-015 (mức domain)

### A-08: Port và adapter in-memory
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/ports/repositories.py`
  - `src/source_ingestion/ports/partners.py`
  - `src/source_ingestion/adapters/memory.py`
  - `tests/unit/collection/test_a08_ports_memory.py`
  - `docs/delivery-evidence/a-08/report.md`
- dependsOn: `A-02`, `A-03`, `A-05`, `A-06`, `A-07`
- resourceLocks: `LOCK-A-08`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: Protocol SourceRepository (tra canonical identity gồm tombstone), SourceCandidateRepository, CollectionRunRepository (unique periodic key), PackageRepository (unique source + canonical locator + observation fingerprint), CheckpointRepository, ReceiptStore; port đối tác ArtifactPort (I), ContentHandoffPort (B), ConfigPort (policy revision và credential handle, không trả secret thô; seam J chưa có binding nên port A-local), ActivityGrantPort (G); UoW in-memory implement `controlplane.domain.interfaces.uow.IUnitOfWork` (rollback huỷ mọi ghi), outbox implement `controlplane.domain.interfaces.outbox.IOutboxWriter` dedup theo `deduplication_id`; fake ArtifactPort trả payload khớp fixture I.
  - instrument: `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider`
  - counterexample: tạo IUnitOfWork/IOutboxWriter/DomainEvent mới; rollback để lại source/outbox; hai periodic run cùng khoá; port trả secret thô.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider`
- coveredIds: A-RULE-004 (ràng buộc unique)

### A-09: Command quản lý nguồn
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/application/source_commands.py`
  - `tests/integration/collection/test_a09_source_commands.py`
  - `docs/delivery-evidence/a-09/report.md`
- dependsOn: `A-04`, `A-08`
- resourceLocks: `LOCK-A-09`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- acceptance:
  - requirement: RegisterSource, UpdateSourceMetadata, RemoveSource, RestoreSource trong một UoW gồm source revision, receipt, outbox event SourceRegistered/SourceMetadataUpdated/SourceRemoved/SourceRestored dựng bằng `DomainEvent`; cùng idempotency key và payload trả receipt cũ, khác payload → idempotency conflict (`request_hash`); locator trùng tombstone → conflict kèm source ref đã xoá; locator unsafe (A-04) bị từ chối không tạo Source; remove không xoá package đã lưu; workspace khác không thấy source; event không chứa secret.
  - instrument: `python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider`
  - counterexample: gửi lặp tạo hai Source; tab sau ghi đè revision; outbox ghi ngoài UoW; event chứa URL có token.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider`
- coveredIds: A-RULE-001, A-RULE-002, A-RULE-003, A-RULE-014

### A-10: Đăng ký SourceCandidate và race
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/application/candidate_registration.py`
  - `tests/integration/collection/test_a10_candidate_registration.py`
  - `docs/delivery-evidence/a-10/report.md`
- dependsOn: `A-07`, `A-09`
- resourceLocks: `LOCK-A-10`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: EvaluateSourceCandidate/RegisterSourceCandidate kiểm lại nguyên tử canonical identity, source/tombstone, policy trong cùng UoW với candidate, source, receipt, outbox; phát SourceCandidateDiscovered/SourceCandidateResolved chỉ mang ref, revision, disposition, reason; test mô phỏng hai thứ tự commit register/remove tuần tự (không thread); auto-registration production giữ NOT_READY khi chưa có Tier policy.
  - instrument: `python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider`
  - counterexample: READY đăng ký sau khi nguồn đã tombstone; mất ACK gửi lại tạo Source thứ hai; thiếu policy vẫn REGISTERED; phát Resolved khi còn WAITING_POLICY.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider`
- coveredIds: TST-SRC-RACE-001..004, TST-INT-INV-015, A-RULE-002

### A-11: Thu thập một nguồn (CT-SRC-005)
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/application/collect_source.py`
  - `tests/integration/collection/test_a11_collect_source.py`
  - `docs/delivery-evidence/a-11/report.md`
- dependsOn: `A-02`, `A-05`, `A-06`, `A-08`
- resourceLocks: `LOCK-A-11`
- bindingRefs:
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
  - `tests/fixtures/contracts/a-b-collected-document/payloads.json`
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: tạo/khôi phục run theo khoá periodic; mỗi item hợp lệ commit một UoW gồm FetchObservation, package, counters, checkpoint an toàn, outbox CollectedDocumentAvailable; item lỗi thành warning, run có thể COMPLETED_PARTIAL; chạy nhiều nguồn tuần tự, một nguồn ném lỗi không chặn nguồn khác; CollectionRunResult có counters, package refs, cursor mới, lỗi redacted; package không qua lớp 1 A-02 không handoff; chạy lại sau commit không phát lại package; adapter là fake.
  - instrument: `python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider`
  - counterexample: một nguồn lỗi dừng vòng lặp; partial rollback package đã commit; chạy lại tạo periodic run thứ hai cùng business_date.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider`
- coveredIds: A-RULE-004, A-RULE-008, A-RULE-012

### A-12: Port adapter nguồn và secure fetch
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/ports/source_adapter.py`
  - `src/source_ingestion/adapters/secure_fetch.py`
  - `tests/unit/collection/test_a12_secure_fetch.py`
  - `docs/delivery-evidence/a-12/report.md`
- dependsOn: `A-04`
- resourceLocks: `LOCK-A-12`
- bindingRefs:
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
- acceptance:
  - requirement: Protocol SourceAdapter (probe, list_candidates, fetch_document, extract_candidate, resume_from_checkpoint, supplemental_search) và kết quả CapabilityUnavailable có cấu trúc; SecureFetcher nhận transport và resolver tiêm vào, kiểm A-04 ở mọi hop redirect, giới hạn redirect/kích thước/MIME/thời gian theo FetchPolicy truyền vào (thiếu policy → INPUT_NOT_READY), phát hiện vòng redirect, map timeout và 429 Retry-After thành problem retryable, header an toàn loại Authorization/Cookie/Set-Cookie/token.
  - instrument: `python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider`
  - counterexample: redirect public→127.0.0.1 được theo; body quá giới hạn vẫn đọc hết; Authorization trong observation/log; năng lực thiếu trả list rỗng như thành công; test mở socket thật.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider`
- coveredIds: A-RULE-013, A-RULE-014

### A-13: Trích xuất và dựng package
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/application/package_builder.py`
  - `src/source_ingestion/adapters/stdlib_html_extractor.py`
  - `tests/unit/collection/test_a13_package_builder.py`
  - `docs/delivery-evidence/a-13/report.md`
- dependsOn: `A-02`, `A-12`
- resourceLocks: `LOCK-A-13`
- bindingRefs:
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
  - `tests/fixtures/contracts/a-b-collected-document/payloads.json`
- acceptance:
  - requirement: extractor tham chiếu chỉ dùng `html.parser`, version `stdlib-html-0`, ghi rõ chỉ cho fixture, không phải extractor production; package builder chuẩn hoá kỹ thuật (whitespace, encoding, timestamp kèm confidence, language candidate), `content_fingerprints` gồm sha256 của text chuẩn hoá, `media_discoveries` có locator, vai trò, context, provenance; package không có trường quyết định của B (`disposition`, `article_id`); kết quả luôn qua validator A-02; nội dung đổi khi fetch lại tạo package và fingerprint mới; HTML hỏng thành warning, không ném ra ngoài.
  - instrument: `python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider`
  - counterexample: package chứa `disposition` hoặc `article_id`; media discovery thiếu provenance; fingerprint dựa trên title; HTML hỏng làm crash.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider`
- coveredIds: A-RULE-010, A-RULE-011

### A-14: Bàn giao raw snapshot cho I
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/application/artifact_handoff.py`
  - `tests/integration/collection/test_a14_artifact_handoff.py`
  - `docs/delivery-evidence/a-14/report.md`
- dependsOn: `A-08`
- resourceLocks: `LOCK-A-14`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: DeclareArtifactVersionRequest qua ArtifactPort giả có content_sha256, size_bytes, media_type, retention_class lấy từ policy, producer_operation_ref = operation key; thành công gắn `raw_snapshot_ref`; timeout sau khi tạo object → OUTCOME_UNKNOWN, run sang WAITING_RECONCILIATION, không upload lại trước reconcile; cùng operation key và hash trả kết quả cũ (`matched_existing`); A không giữ đường dẫn lưu trữ.
  - instrument: `python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider`
  - counterexample: retry upload mù sau timeout; package tham chiếu đường dẫn tệp cục bộ; A tự đặt retention.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider`
- coveredIds: A-RULE-015

### A-15: Thứ tự nguồn theo Tier và điều kiện dừng
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/application/source_eligibility.py`
  - `tests/unit/collection/test_a15_source_eligibility.py`
  - `docs/delivery-evidence/a-15/report.md`
- dependsOn: `A-03`, `A-05`
- resourceLocks: `LOCK-A-15`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: hàm thuần xếp nguồn deterministic Tier 1→2→3, phá hòa bằng `source_id`, chỉ ACTIVE, đúng topic scope, chưa có periodic run trong business_date, kèm reason chọn/bỏ qua; quyết định mở Tier sau chỉ dựa trên bộ đếm unique article do G/B cung cấp, không nhận URL/item count; đủ ngưỡng thì trả quyết định dừng để G ghi SKIPPED_SUFFICIENT, A không tạo run giả và không ghi CollectionDecision; ngưỡng là input. CT-SRC-004 chưa có binding; wiring cycle ở CONV-A-06.
  - instrument: `python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider`
  - counterexample: thứ tự phụ thuộc thứ tự dict; nguồn DISABLED được chọn; dùng số URL thay số unique; tạo CollectionRun cho nguồn bị bỏ qua.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider`
- coveredIds: A-RULE-006, A-RULE-007

### A-16: Thu thập bổ sung theo video
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/application/supplemental.py`
  - `tests/integration/collection/test_a16_supplemental.py`
  - `docs/delivery-evidence/a-16/report.md`
- dependsOn: `A-11`
- resourceLocks: `LOCK-A-16`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
- acceptance:
  - requirement: purpose SUPPLEMENTAL nhận job/scene/intent/budget refs qua grant của G; kiểm tombstone trước mọi fetch; không tạo hay đếm periodic run; hết budget/deadline trả partial/not-found có cấu trúc; kết quả thành package/media discovery có provenance; dữ liệu bài mới vẫn qua handoff B; handoff C chờ binding CT-MED-001 (CONV-A-07).
  - instrument: `python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider`
  - counterexample: supplemental tăng periodic count; fetch nguồn tombstone; hết budget trả thành công rỗng.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider`
- coveredIds: A-RULE-002, A-RULE-005

### A-17: Query và projection read-only
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/projections/source_queries.py`
  - `tests/unit/collection/test_a17_projections.py`
  - `docs/delivery-evidence/a-17/report.md`
- dependsOn: `A-08`
- resourceLocks: `LOCK-A-17`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: danh sách/chi tiết Source lọc theo Tier, topic, status, kind, health; revision history; run/attempt history, counters, last collection; trace package đã redacted; query không gọi adapter (test bằng adapter giả đếm lượt gọi bằng 0); kiểm workspace; không lộ header nhạy cảm.
  - instrument: `python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider`
  - counterexample: query kích hoạt fetch; trả source của workspace khác; trace chứa Cookie.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider`
- coveredIds: A-RULE-014 (redaction trace)

### A-18: Worker activity cho G
- kind: `work_package_slice`
- ownedPaths:
  - `src/source_ingestion/worker/activity_handler.py`
  - `tests/integration/collection/test_a18_worker_activity.py`
  - `docs/delivery-evidence/a-18/report.md`
- dependsOn: `A-11`
- resourceLocks: `LOCK-A-18`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: nhận ActivityRequest kèm `controlplane.domain.orchestration.ExecutionGrant` (không tạo lớp grant mới; trường lệch binding thì ghi vào report và CONV-A-06), gọi CollectSource, trả ActivityResult với output_refs, metrics, warnings, problem đã redacted; grant/generation cũ bị từ chối, không commit; request lặp cùng operation_key trả kết quả cũ; test `ast` khẳng định handler không import `temporalio`, `controlplane.ui`, gói `render`, `voice` hay mã desktop (bằng chứng phần mã cho A-RULE-016; chạy cloud thật ở CP7).
  - instrument: `python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider`
  - counterexample: worker generation cũ ghi checkpoint mới; ActivityResult chứa secret; handler đăng ký workflow Temporal trực tiếp.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider`
- coveredIds: A-RULE-014, A-RULE-016

### A-19: Ma trận A-RULE và test ID
- kind: `work_package_slice`
- ownedPaths:
  - `tests/unit/collection/test_a19_rule_catalog.py`
  - `docs/delivery-evidence/a-19/report.md`
- dependsOn: `A-02`, `A-03`, `A-04`, `A-05`, `A-06`, `A-07`, `A-08`, `A-09`, `A-10`, `A-11`, `A-12`, `A-13`, `A-14`, `A-15`, `A-16`, `A-17`, `A-18`
- resourceLocks: `LOCK-A-19`
- bindingRefs:
  - `docs/parallel-delivery/bindings/a-b-collected-document.json`
- acceptance:
  - requirement: test chỉ dùng stdlib đọc docstring module của `tests/unit/collection/test_a*.py` và `tests/integration/collection/test_a*.py` (trừ chính A-19), khẳng định mỗi mã A-RULE-001..A-RULE-016, TST-COL-END-001..004, TST-COL-PKG-001..004, TST-SRC-RACE-001..004, TST-INT-INV-015 có trong ít nhất một tệp test và tệp đó có ít nhất một hàm `test_`; report ghi bảng ánh xạ.
  - instrument: `python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider`
  - counterexample: một A-RULE không có test trực tiếp; mã chỉ xuất hiện trong A-19.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider`
- coveredIds: spec §17 mục 1
