# Slice triển khai Phân hệ B

Nguồn: docs/implementation/b/plan.md. Control biên dịch từng mục `### B-<số>: <tên>` thành work package trong phong bì policy; mọi lệnh python chạy bằng interpreter khoá của lane.

## Quy tắc chung

1. Chỉ sửa ownedPaths của slice. Không sửa migration, composition root (src/main.py, src/controlplane/api/main.py), pyproject.toml, uv.lock, tests/m2, ui/dist, App.tsx, state machine, control API, docs/09-contracts, binding hay registry.
2. Không thêm thư viện; chỉ stdlib và mã có sẵn trong src/. Không gọi mạng hay dịch vụ thật, không đọc Credentials/ hay bí mật.
3. Dùng fixture CP1 trong tests/fixtures/contracts và fake cho A, C, D, G, J. Test đọc binding/fixture bằng json và pathlib từ gốc repo `Path(__file__).resolve().parents[3]`.
4. Import root src/ (`from ingestion...`), không tiền tố `src.`. Không tạo __init__.py trong tests/unit/ingestion hoặc tests/integration/ingestion; tên tệp test bắt đầu `test_ingestion_`.
5. Test-first: viết test, tạo skeleton import được, chứng kiến RED bằng AssertionError đúng oracle (ImportError hay collection error không hợp lệ) rồi mới implement.
6. Bằng chứng ghi vào `docs/delivery-evidence/<slice viết thường>/report.md`: lệnh, exit code, kết quả RED và GREEN.
7. Một commit local theo Conventional Commits; không push, không merge.
8. Lệnh kiểm chung CHECK-B, mỗi slice chép nguyên văn vào testCommands: `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-1: Nền gói ingestion và kiểm tra biên CollectedDocumentPackage

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/__init__.py`, `src/ingestion/domain/__init__.py`, `src/ingestion/application/__init__.py`, `src/ingestion/infrastructure/__init__.py`, `src/ingestion/domain/package_validation.py`, `tests/unit/ingestion/test_ingestion_package_validation.py`, `docs/delivery-evidence/b-1/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-SRC-INGESTION`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `tests/fixtures/contracts/a-b-collected-document/payloads.json`
- Mô tả: Tạo gói src/ingestion và bộ kiểm tra cấu trúc package tại biên B (CT-SRC-006 lớp 1).
- acceptance:
  - requirement: validate_collected_document_package(payload) và validate_collected_document_resolution(payload) trả danh sách lỗi (code ∈ missing_required, wrong_type, enum_violation; field) theo hằng REQUIRED/OPTIONAL/ENUM trong mã; datetime phải RFC3339; trường lạ bị bỏ qua; binding_version major khác 1 trả lỗi unsupported_binding_version. Test: mọi payload valid của fixture không lỗi; mỗi case invalid trả đúng code và field của expected_error; hằng số trong mã khớp tệp binding (phát hiện drift); thêm trường lạ vẫn hợp lệ.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider`
  - counterexample: payload thiếu provenance_chain được chấp nhận; content_eligibility complete lọt; source_revision dạng chuỗi được nhận; hằng số lệch binding mà test vẫn xanh.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-2: Chuẩn hóa nội dung, fingerprint và phân loại chủ đề

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/domain/normalization.py`, `src/ingestion/domain/fingerprint.py`, `src/ingestion/domain/topic.py`, `tests/unit/ingestion/test_ingestion_normalization.py`, `tests/unit/ingestion/test_ingestion_fingerprint.py`, `docs/delivery-evidence/b-2/report.md`
- dependsOn: `B-1`
- resourceLocks: `LOCK-B-2`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `tests/fixtures/contracts/a-b-collected-document/payloads.json`
- Mô tả: Chuẩn hóa văn bản bài báo, tính fingerprint chính xác và near-duplicate, phân loại chủ đề bài theo luật từ khóa.
- acceptance:
  - requirement: normalize_text (NFC, bỏ ký tự điều khiển, gộp khoảng trắng, strip) tất định; exact_fingerprint = SHA-256 hex của văn bản chuẩn hóa; shingles(text, size), jaccard(a, b), is_near_duplicate(a, b, policy) đọc policy['near_duplicate_jaccard'] và policy['shingle_size'] (test dùng 0.90 và 5 theo D8-B-01, không hard-code trong hàm); classify_topic(text, topic_rules) trả (topic, uncertain). Test: chuỗi tiếng Việt dạng NFC và NFD cùng fingerprint; chạy hai lần cùng kết quả; biên đúng 0.90; không khớp luật → ('unclassified', True).
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cacheprovider`
  - counterexample: fingerprint đổi theo khoảng trắng hoặc dạng Unicode; ngưỡng viết cứng; luật rỗng vẫn gán chủ đề.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-3: Aggregate Article/ArticleRevision, port và unit of work in-memory

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/domain/article.py`, `src/ingestion/application/ports.py`, `src/ingestion/infrastructure/memory.py`, `tests/unit/ingestion/test_ingestion_article_aggregate.py`, `tests/unit/ingestion/test_ingestion_memory_unit_of_work.py`, `docs/delivery-evidence/b-3/report.md`
- dependsOn: `B-1`
- resourceLocks: `LOCK-B-3`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`
- Mô tả: Aggregate Article và ArticleRevision bất biến, giao diện cổng trừu tượng và adapter InMemoryUnitOfWork nguyên tử.
- acceptance:
  - requirement: dataclass frozen ArticleRevision đủ trường CT-CNT-003 (article_revision_id, article_id; title lấy từ extracted_content_candidate.title, B-6 truyền chuỗi rỗng khi thiếu; normalized_text; provenance gồm source_id, source_revision, collection_run_id, collected_document_id, requested_url, final_url, provenance_chain, raw_snapshot_ref; published_at kèm confidence, fetched_at; topic, topic_uncertain; exact_fingerprint; media_discovery_refs; extractor_version, normalizer_version; completeness flags); Article có article_id, identity_key, representative_source_id, revisions với số revision tăng 1, thêm revision trả Article mới. ports.py: Protocol ArticleRepository, ResolutionRepository, EventRepository, SourceTierLookup, UnitOfWork. memory.py: InMemoryUnitOfWork lưu bản ghi theo loại; commit ghi aggregate và outbox event cùng lúc; ngoại lệ trước commit không lưu gì; deduplication_id trùng không ghi lần hai. Test: dựng ArticleRevision thiếu article_revision_id, title hoặc requested_url ném TypeError; thêm revision mới không đổi các trường này ở revision cũ.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -p no:cacheprovider`
  - counterexample: revision cũ bị sửa; lỗi giữa chừng để lại aggregate không event hoặc event không aggregate; cùng deduplication_id ghi hai lần.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-4: Dựng domain event của Phân hệ B

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/domain/events.py`, `tests/unit/ingestion/test_ingestion_domain_events.py`, `docs/delivery-evidence/b-4/report.md`
- dependsOn: `B-1`
- resourceLocks: `LOCK-B-4`
- bindingRefs: `docs/parallel-delivery/bindings/domain-event-envelope.json`, `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- Mô tả: Xây dựng envelope DomainEvent an toàn cho 4 domain event của Phân hệ B theo binding và catalog contract.
- acceptance:
  - requirement: build_event(event_name, aggregate_type, aggregate_id, aggregate_revision, payload, recovery_epoch, event_id) chỉ nhận ArticleRevisionAccepted, DuplicateDocumentResolved, EventLinkResolved, EventUpdateAccepted; producer 'B'; schema_version '1.0.0'; sensitivity 'internal'; payload chỉ mang ID, revision, ref (không văn bản bài); gọi controlplane.domain.events.contracts.ensure_safe_event_payload; không có forbidden_fields của binding. Test: output đủ trường required của binding đúng kiểu; tên event lạ → ValueError; payload có khóa token → ValueError; payload có khóa normalized_text → ValueError.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider`
  - counterexample: dựng được event ArticleIngested; payload chứa toàn văn bài hoặc canary secret; thiếu recovery_epoch.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`
### B-5: Quy tắc bài đại diện theo Tier

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/domain/representative.py`, `tests/unit/ingestion/test_ingestion_representative.py`, `docs/delivery-evidence/b-5/report.md`
- dependsOn: `B-1`
- resourceLocks: `LOCK-B-5`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `tests/fixtures/contracts/a-b-collected-document/payloads.json`
- Mô tả: Thuật toán tất định lựa chọn nguồn đại diện cho cụm bài trùng theo thứ tự Tier và quy tắc phá hòa.
- acceptance:
  - requirement: select_representative(incumbent, candidates) với candidate (source_id, tier 1..3) theo CT-CNT-002 và D8-B-05: Tier nhỏ hơn thắng; cùng Tier giữ incumbent; chưa có incumbent thì source_id nhỏ nhất theo thứ tự chuỗi; trả selection_reason ∈ higher_tier, keep_incumbent_same_tier, tie_break_source_id; đổi representative trả cờ applies_to_future_production_only=True. Test: hoán vị thứ tự đầu vào cho cùng kết quả.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider`
  - counterexample: representative dao động khi cùng Tier; kết quả phụ thuộc thứ tự đầu vào; Tier 3 thắng Tier 1.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-6: ResolveCollectedDocument và năm disposition

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/application/resolve_document.py`, `tests/unit/ingestion/test_ingestion_resolve_document.py`, `docs/delivery-evidence/b-6/report.md`
- dependsOn: `B-2`, `B-3`, `B-4`, `B-5`
- resourceLocks: `LOCK-B-6`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `tests/fixtures/contracts/a-b-collected-document/payloads.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`
- Mô tả: Xử lý tiếp nhận CollectedDocumentPackage, phân loại 5 disposition và quản lý trạng thái CT-STATE-003.
- acceptance:
  - requirement: resolve_collected_document(package, dedup_policy, uow, tier_lookup, clock, id_factory) trả dict CollectedDocumentResolution hợp lệ theo validator B-1; khi tạo ArticleRevision (NEW_ARTICLE, NEW_REVISION) gán article_revision_id từ id_factory, title từ package['extracted_content_candidate']['title'] (thiếu thì chuỗi rỗng), requested_url từ package['requested_url'], và resolution mang article_id, article_revision_id của revision vừa tạo; chọn NEW_ARTICLE, NEW_REVISION, DUPLICATE_MEDIA_ONLY, DUPLICATE_NO_NEW_VALUE, REJECTED_INCOMPLETE theo D8-B-01..04 và D8-B-09; đi qua trạng thái CT-STATE-003; package sai cấu trúc ném lỗi VALIDATION_ERROR và không ghi bản ghi; gọi lại cùng collected_document_id và dedup_policy_revision trả cùng kết quả, không ghi thêm (TST-CTR-INV-001); NEW_ARTICLE/NEW_REVISION phát ArticleRevisionAccepted; DUPLICATE_* không tạo Article/revision, phát DuplicateDocumentResolved (chỉ MEDIA_ONLY mang new_media_discovery_refs) và gắn media vào bài đại diện; REJECTED_INCOMPLETE không phát event; port ném lỗi hạ tầng → FAILED_RETRYABLE, không ghi dở (D8-B-11). Test: revision tạo từ payload valid của fixture có title 'Sample Title', requested_url bằng package['requested_url'] và article_revision_id trùng giá trị trong resolution.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider`
  - counterexample: repost tạo Article mới; media mới từ bài trùng bị bỏ; resubmission tạo bản ghi thứ hai; package thiếu provenance_chain vào RECEIVED.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-7: ResolveEventLink giữ bài độc lập

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/domain/event_link.py`, `src/ingestion/application/resolve_event_link.py`, `tests/unit/ingestion/test_ingestion_event_link.py`, `docs/delivery-evidence/b-7/report.md`
- dependsOn: `B-2`, `B-3`, `B-4`
- resourceLocks: `LOCK-B-7`
- bindingRefs: `docs/parallel-delivery/bindings/domain-event-envelope.json`, `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- Mô tả: Đánh giá liên kết bài viết vào Event theo luật tất định, giữ bài độc lập và phát EventLinkResolved.
- acceptance:
  - requirement: resolve_event_link(article_revision_refs, event_link_policy, uow, clock, id_factory) trả event_id hiện có hoặc event candidate mới, disposition linked/kept_separate/needs_more_evidence (CT-STATE-004 LINKED, KEPT_SEPARATE, NEEDS_MORE_EVIDENCE), confidence, explanation, relation_type, effective_time_range; luật D8-B-06 với ngưỡng đọc từ policy; liên kết không gộp hay xóa Article; phát EventLinkResolved.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider`
  - counterexample: bài bị gộp làm mất Article riêng; ngưỡng viết cứng; thiếu evidence vẫn LINKED.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-8: EvaluateEventUpdate phân biệt repost và diễn biến mới

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/domain/event_update.py`, `src/ingestion/application/evaluate_event_update.py`, `tests/unit/ingestion/test_ingestion_event_update.py`, `docs/delivery-evidence/b-8/report.md`
- dependsOn: `B-7`
- resourceLocks: `LOCK-B-8`
- bindingRefs: `docs/parallel-delivery/bindings/domain-event-envelope.json`, `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- Mô tả: Đánh giá diễn biến mới của Event qua ClaimCandidateProvider, phân biệt repost và phát EventUpdateAccepted.
- acceptance:
  - requirement: evaluate_event_update(event_id, article_revision_ref, claim_provider, policy, uow, clock, id_factory) với Protocol ClaimCandidateProvider khai trong evaluate_event_update.py; output is_new_development, danh sách claim mới, source revision refs, confidence, reason, event update revision; trạng thái ACCEPTED_NEW_DEVELOPMENT, REJECTED_REPOST, REJECTED_NO_NEW_FACT, UNCERTAIN theo D8-B-07; chỉ ACCEPTED_NEW_DEVELOPMENT tạo EventUpdate và phát EventUpdateAccepted. Test dùng fake claim provider.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider`
  - counterexample: nguồn mới đăng lại cùng tình tiết được chấp nhận; claim provider rỗng vẫn ACCEPTED; nhánh REJECTED vẫn phát EventUpdateAccepted.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`
### B-9: Bộ nguồn và điều kiện timeline cho ProductionSnapshot

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/application/source_set.py`, `tests/unit/ingestion/test_ingestion_source_set.py`, `docs/delivery-evidence/b-9/report.md`
- dependsOn: `B-3`, `B-8`
- resourceLocks: `LOCK-B-9`
- bindingRefs: `docs/parallel-delivery/bindings/b-d-production-snapshot.json`, `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- Mô tả: Tạo bộ nguồn đã ghim revision và điều kiện timeline hợp lệ cung cấp cho Phân hệ D lập ProductionSnapshot.
- acceptance:
  - requirement: build_source_set(production_mode, subject_id, uow) trả source_refs (article_id, article_revision_id, source_id, source_revision) ghim revision, source_set_fingerprint = SHA-256 hex của JSON refs đã sắp xếp, eligibility_reason; single_article cần revision đại diện; multi_article_event cần event có ≥ 2 bài LINKED; from_then_to_now chỉ khi có EventUpdate ACCEPTED_NEW_DEVELOPMENT, ngược lại từ chối với reason event_update_not_accepted (TST-CTR-INV-006); bộ refs đã trả không đổi khi có revision mới (TST-INT-INV-004). Test so tên và kiểu trường với binding.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider`
  - counterexample: timeline mode được phép khi không có update; fingerprint phụ thuộc thứ tự; bộ cũ trỏ sang revision mới.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-10: Truy vết nguồn và truy vấn tìm kiếm/lọc

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/application/queries.py`, `tests/unit/ingestion/test_ingestion_queries.py`, `docs/delivery-evidence/b-10/report.md`
- dependsOn: `B-3`, `B-7`
- resourceLocks: `LOCK-B-10`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `tests/fixtures/contracts/a-b-collected-document/payloads.json`
- Mô tả: Truy vấn truy vết nguồn provenance, tìm kiếm/lọc bài báo, sự kiện và đếm số bài theo chủ đề.
- acceptance:
  - requirement: trace_revision(article_revision_id) trả source_id, source_revision, collection_run_id, collected_document_id, requested_url, final_url, fetched_at, raw_snapshot_ref, provenance_chain; trường thiếu được liệt kê trong uncertain_fields (CT-CNT-006); search(filters) lọc theo topic, source_id, event_id, article_revision_id và chuỗi con trong title, thứ tự ổn định; count_new_articles(topic, business_date_utc) đếm NEW_ARTICLE theo ngày UTC (D8-B-10). Chỉ đọc, không ghi.
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider`
  - counterexample: revision không truy được nguồn mà không báo; truy vấn ghi dữ liệu; thứ tự kết quả không ổn định.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-11: Activity handler ResolveCollectedDocument cho G

- kind: `work_package_slice`
- ownedPaths: `src/ingestion/application/activity_handler.py`, `tests/unit/ingestion/test_ingestion_activity_handler.py`, `docs/delivery-evidence/b-11/report.md`
- dependsOn: `B-6`
- resourceLocks: `LOCK-B-11`
- bindingRefs: `docs/parallel-delivery/bindings/g-activity-execution.json`, `tests/fixtures/contracts/g-activity-execution/payloads.json`, `docs/parallel-delivery/bindings/a-b-collected-document.json`
- Mô tả: Xử lý ActivityRequest ResolveCollectedDocument từ workflow G, trả ActivityResult theo đúng binding.
- acceptance:
  - requirement: handle_resolve_activity(request, package_loader, deps, clock) kiểm ActivityRequest theo binding (đủ required; có secret_value hoặc raw_blob → từ chối); activity_name ResolveCollectedDocument; mỗi request đúng một input_ref; ActivityResult đủ required của binding, grant theo D8-B-12; resolve xong → succeeded với output_refs chứa resolution ref; lỗi retryable → failed kèm problem; cùng operation_key gọi lại trả cùng kết quả, không resolve lại. Test: hai request, một lỗi một thành công, độc lập nhau (EG-M3-5).
  - instrument: `python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider`
  - counterexample: một tài liệu lỗi làm request khác thất bại; grant_id bị bịa khi thiếu execution_grant; operation_key lặp resolve hai lần.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`

### B-12: Tích hợp luồng A→B với fake và corpus tổng hợp

- kind: `work_package_slice`
- ownedPaths: `tests/integration/ingestion/test_ingestion_flow_integration.py`, `tests/integration/ingestion/fixtures/ingestion_corpus_v1.json`, `docs/delivery-evidence/b-12/report.md`
- dependsOn: `B-6`, `B-8`, `B-9`, `B-10`, `B-11`
- resourceLocks: `LOCK-B-12`
- bindingRefs: `tests/fixtures/contracts/a-b-collected-document/payloads.json`, `tests/fixtures/contracts/domain-event-envelope/payloads.json`, `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`, `tests/fixtures/contracts/g-activity-execution/payloads.json`
- Mô tả: Tích hợp trọn luồng tiếp nhận từ A sang B với fake adapter, fixture corpus tổng hợp và kiểm tra bất biến bảo mật.
- acceptance:
  - requirement: corpus tự soạn bằng văn bản tổng hợp (không chép báo thật) gồm nhóm News, Duplicate Clusters (exact, near, repost có media mới, revision) và Event Timeline Set (gộp đúng, giữ riêng, repost, update thật), mỗi mục có expected disposition; test chạy activity → resolve → event link → event update → source set với fake A/G/C/D/J và InMemoryUnitOfWork; kiểm TST-INT-INV-005, TST-E2E-002, TST-E2E-003, TST-E2E-004, TST-CTR-INV-006, TST-SEC-INV-012 (canary CANARY-SECRET-B12 trong văn bản không xuất hiện trong outbox event) và TST-SEC-INV-020 (văn bản giả lệnh hệ thống không đổi policy revision hay disposition).
  - instrument: `python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider`
  - counterexample: corpus chép bài báo thật; test chỉ gọi từng hàm rời; canary lọt vào event.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; bad = [str(p) for p in pathlib.Path('src/ingestion').rglob('*.py') if re.search(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)', p.read_text(encoding='utf-8'))]; assert not bad, bad; assert not any(pathlib.Path(d, '__init__.py').exists() for d in ('tests/unit/ingestion', 'tests/integration/ingestion')), 'tests ingestion dirs must not be packages'"`
