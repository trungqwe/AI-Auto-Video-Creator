# Kế hoạch triển khai Phân hệ B — Kho nội dung và tri thức sự kiện

> Task IMPL-PLAN-B · baseline f40822e0ea258ed799fffa781c2c7b06776dd21a · tài liệu kế hoạch, chưa có mã. Nguồn quyền D3: ủy quyền AI_SETUP và user duyệt Phần B ngày 18/10/2026; PRODUCTION_ACTIVATION_BLOCKED vẫn giữ.

## 1. Mục đích và phạm vi

Phân hệ B nhận CollectedDocumentPackage hợp lệ từ Phân hệ A, chuẩn hóa, chống trùng, quản lý Article/ArticleRevision, liên kết Event, đánh giá EventUpdate và cung cấp bộ nguồn đã ghim revision cho Phân hệ D lập ProductionSnapshot; phục vụ M3 (docs/11-roadmap.md §9, dòng 287–350).

Ngoài phạm vi: quản lý nguồn và thu thập (A), media (C), sinh snapshot và kịch bản (D), workflow (G), giao diện (H), lưu trữ artifact (I), cấu hình và bí mật (J).

## 2. Nguồn chuẩn và thứ tự ưu tiên

1. docs/09-contracts/04-source-content-contracts.md (CT-SRC-006, CT-CNT-001..006);
2. docs/09-contracts/02-domain-events.md (CT-EVT-001..003, catalog Phân hệ B);
3. docs/09-contracts/12-state-machines.md (CT-STATE-003, CT-STATE-004);
4. binding CP1: docs/parallel-delivery/bindings/a-b-collected-document.json, docs/parallel-delivery/bindings/b-d-production-snapshot.json, docs/parallel-delivery/bindings/domain-event-envelope.json, docs/parallel-delivery/bindings/g-activity-execution.json cùng fixture tests/fixtures/contracts/<seam>/payloads.json và quy tắc docs/parallel-delivery/bindings/README.md;
5. docs/10-test-strategy.md (§14.2 catalog INV, §15 E2E, bộ dữ liệu dòng 194–196);
6. docs/11-roadmap.md §9 và §23;
7. docs/parallel-delivery/ownership-and-locks.yaml (PATH-SRC-INGESTION, LOCK-SRC-INGESTION);
8. docs/modules/capability-b-ingestion.md (chỉ tham khảo, có lỗi, xem §3).

Khi mâu thuẫn, nguồn số nhỏ hơn thắng; không chép nội dung tài liệu cũ khi chưa đối chiếu với nguồn 1–5.

## 3. Đính chính so với docs/modules/capability-b-ingestion.md

| # | Nội dung cũ | Lỗi | Thay bằng |
| --- | --- | --- | --- |
| 1 | `DocumentPackage`, `CT-SRC-001` | tên và mục tự đặt | `CollectedDocumentPackage` (CT-SRC-006) và `CollectedDocumentResolution` (CT-CNT-001) theo binding a-b-collected-document |
| 2 | idempotency theo `provenance_hash` | trường không có trong contract | idempotency theo `collected_document_id` + `dedup_policy_revision` |
| 3 | ArticleSnapshot cấp cho D qua CT-CNT-002 | CT-CNT-002 là quy tắc bài đại diện | `ProductionSnapshot` (CT-AI-001) do D sinh; B là input_provider (binding b-d-production-snapshot) |
| 4 | event `ArticleIngested`, `ArticleUpdated`, `EventDiscovered` qua CT-EVT-001 | không có trong catalog | `ArticleRevisionAccepted`, `DuplicateDocumentResolved`, `EventLinkResolved`, `EventUpdateAccepted`; envelope CT-EVT-002/003; CT-EVT-001 là ngữ nghĩa chuyển phát |
| 5 | INV-005 là bản chụp nội dung bất biến | sai định nghĩa | INV-005: repost không tạo article/script, giữ media mới (TST-INT-INV-005); INV-004: job đã snapshot giữ refs (TST-INT-INV-004); INV-006: timeline cần EventUpdateAccepted (TST-CTR-INV-006) |
| 6 | INV-010 outbox, INV-011 chống trùng | sai mã | INV-010 là ledger completion (TST-WF-INV-010), INV-011 là cleanup authorization (TST-DR-INV-011), không thuộc B; tính nguyên tử outbox theo CT-EVT-001 |
| 7 | ngưỡng trùng fingerprint >95% | số tự đặt | ngưỡng nằm trong dedup policy revision (D8-B-01) |
| 8 | §8 rollback toàn lô khi một tài liệu lỗi | trái CT-STATE-003 và EG-M3-5 | mỗi collected document một transaction (D8-B-11) |
| 9 | path scope thiếu tests/integration/ingestion/** | lệch D1 | dùng theo D1; đăng ký registry qua REQ-B-CONV-06 |
| 10 | lệnh `python -m unittest ... -k test_deduplication`, namespace `db:ingestion`, snapshot PostgreSQL disposable | lệnh và tài nguyên chưa tồn tại | lệnh pytest theo từng tệp trong slices.md; schema qua REQ-B-CONV-01 |

TASK-CAP-B-INGESTION trong docs/parallel-delivery/task-dag.yaml là future_template với invariant_refs INV-010/INV-011 sai như dòng 6; không dùng làm dependsOn hay nguồn quyền.

## 4. Năng lực và aggregate

| Năng lực roadmap §9 | Slice |
| --- | --- |
| B1 Chuẩn hóa article revision và provenance | B-2, B-3, B-6 |
| B2 Exact/near duplicate và representative theo Tier | B-2, B-5, B-6 |
| B3 Bài trùng chỉ bổ sung media/provenance | B-6 |
| B4 Giữ bài độc lập khi liên kết event | B-7 |
| B5 Phân biệt repost, nguồn mới và diễn biến mới | B-8 |
| B6 Chỉ EventUpdateAccepted cấp narrative "từ lúc đó đến nay" | B-8, B-9 |
| B7 Tìm kiếm/lọc bài, event, topic, source, revision | B-10 (truy vấn); màn hình qua REQ-B-CONV-05 |

Aggregate B sở hữu (single-writer): `Article`, `ArticleRevision` (bất biến sau khi lưu, trường theo CT-CNT-003), `Event`, `EventUpdate`; bản ghi phụ `CollectedDocumentResolution` (CT-STATE-003), `DedupEvidence`, `EventLinkCandidate` và `EventUpdateCandidate` (CT-STATE-004).

Không sở hữu, không dựng lại: Source, CollectionRun, CollectedDocumentPackage (A, src/source_ingestion); media (C); ProductionSnapshot (D); DomainEvent envelope và transactional outbox đã có ở src/controlplane/domain/events/contracts.py, src/controlplane/domain/interfaces/outbox.py, src/controlplane/infrastructure/db/outbox/; artifact/storage (I) và config revision (J) trong src/controlplane.

## 5. Vị trí mã theo D1

- Import root duy nhất src/: `from ingestion.domain import ...`, `from controlplane.domain.events.contracts import ensure_safe_event_payload`; không tiền tố `src.`.
- Cây mã: src/ingestion/__init__.py; src/ingestion/domain/ (package_validation.py, normalization.py, fingerprint.py, topic.py, article.py, events.py, representative.py, event_link.py, event_update.py); src/ingestion/application/ (ports.py, resolve_document.py, resolve_event_link.py, evaluate_event_update.py, source_set.py, queries.py, activity_handler.py); src/ingestion/infrastructure/memory.py (adapter in-memory; adapter PostgreSQL thuộc REQ-B-CONV-02); tests/unit/ingestion/test_ingestion_*.py; tests/integration/ingestion/test_ingestion_flow_integration.py và tests/integration/ingestion/fixtures/.
- Quy tắc test: không tạo __init__.py trong tests/unit/ingestion và tests/integration/ingestion, vì pytest (rootdir, pythonpath src trong pyproject.toml) sẽ chèn tests/unit vào sys.path và gói `ingestion` trong tests che gói src/ingestion; tên tệp test bắt đầu `test_ingestion_` để không trùng basename.
- Tái dùng: B-4 gọi `ensure_safe_event_payload`; port outbox của B tương thích `IOutboxWriter.append_event(event_type, aggregate_id, payload, deduplication_id)`. Không tạo src/storage, src/orchestration, src/ui hay outbox riêng.

## 6. Contract dùng và cung cấp

| Vai trò | Seam / thực thể | Tệp binding | Fixture | Mục contract | Slice |
| --- | --- | --- | --- | --- | --- |
| Dùng | a-b-collected-document / CollectedDocumentPackage | docs/parallel-delivery/bindings/a-b-collected-document.json | tests/fixtures/contracts/a-b-collected-document/payloads.json | CT-SRC-006 | B-1, B-6 |
| Cung cấp | a-b-collected-document / CollectedDocumentResolution | docs/parallel-delivery/bindings/a-b-collected-document.json | tests/fixtures/contracts/a-b-collected-document/payloads.json | CT-CNT-001 | B-6 |
| Cung cấp | domain-event-envelope / DomainEvent cho 4 event B | docs/parallel-delivery/bindings/domain-event-envelope.json | tests/fixtures/contracts/domain-event-envelope/payloads.json | CT-EVT-002, CT-EVT-003 | B-4 |
| Dùng | domain-event-envelope / CollectedDocumentAvailable từ A | docs/parallel-delivery/bindings/domain-event-envelope.json | tests/fixtures/contracts/domain-event-envelope/payloads.json | CT-EVT-001..003 | B-11 (subscription qua REQ-B-CONV-04) |
| Cung cấp đầu vào (input_provider) | b-d-production-snapshot / ProductionSnapshot: source_refs, source_set_fingerprint, eligibility_reason, production_mode được phép | docs/parallel-delivery/bindings/b-d-production-snapshot.json | tests/fixtures/contracts/b-d-production-snapshot/payloads.json | CT-AI-001 | B-9 |
| Dùng ActivityRequest, trả ActivityResult | g-activity-execution | docs/parallel-delivery/bindings/g-activity-execution.json | tests/fixtures/contracts/g-activity-execution/payloads.json | CT-WF-003, CT-WF-006 | B-11 |

- Consumer bỏ qua trường lạ; gặp binding_version major khác 1 thì fail-closed (bindings/README.md, CT-CMN-012).
- Manifest a-b khai producer A cho cả hai thực thể, nhưng CollectedDocumentResolution do B sinh theo CT-CNT-001 → REQ-B-CONV-07.
- DomainEvent trong src/controlplane/domain/events/contracts.py dùng schema_version kiểu int và recovery_epoch int hoặc None, binding khai string; B-4 dựng dict theo binding, chuyển đổi khi nối outbox thuộc REQ-B-CONV-07.
- Seam B cần nhưng chưa có binding: tra Tier nguồn A→B, payload `new_media_discovery_refs` B→C, truy vấn B→H. Slice chỉ dùng port và fake; kết nối thật chờ binding (fail-closed theo docs/parallel-delivery/bindings/README.md).

## 7. Ánh xạ exit gate M3 sang slice

| Mã | Exit gate (roadmap §9) | Phần B phục vụ | Slice | Cách kiểm |
| --- | --- | --- | --- | --- |
| EG-M3-1 | User thêm nguồn và theo dõi lượt/stage/error trên UI | disposition và event quan sát được của stage resolve; màn hình thuộc A/G/H | B-4, B-6, B-11 | tests/unit/ingestion/test_ingestion_resolve_document.py kiểm disposition/event; UI qua REQ-B-CONV-05 |
| EG-M3-2 | Article/Event truy ngược source, fetch evidence, revision | CT-CNT-003, CT-CNT-006 | B-3, B-10 | tests/unit/ingestion/test_ingestion_queries.py: mọi revision truy ra source_id, source_revision, collection_run_id, collected_document_id, final_url, provenance_chain; thiếu thì vào uncertain_fields |
| EG-M3-3 | Bài repost không tạo article/script candidate mới | INV-005, CT-CNT-001, CT-CNT-002 | B-2, B-5, B-6 | tests/unit/ingestion/test_ingestion_resolve_document.py; tích hợp TST-INT-INV-005, TST-E2E-002 |
| EG-M3-4 | Event update không bị đồng nhất với nguồn đăng lại | CT-CNT-005, CT-STATE-004, INV-006 | B-8, B-9 | tests/unit/ingestion/test_ingestion_event_update.py; tích hợp TST-E2E-003, TST-E2E-004, TST-CTR-INV-006 |
| EG-M3-5 | Một nguồn lỗi không dừng cycle còn lại | một transaction và một activity cho mỗi collected document | B-6, B-11 | tests/unit/ingestion/test_ingestion_activity_handler.py: request lỗi trả failed, request khác vẫn succeeded |
| EG-M3-6 | A-B contract, integration, failure, security tests đạt | kiểm biên binding, tích hợp với fake A/G/C/D/J, TST-SEC-INV-012, TST-SEC-INV-020 | B-1, B-4, B-12 | test_ingestion_package_validation.py, test_ingestion_domain_events.py, tests/integration/ingestion/test_ingestion_flow_integration.py; PostgreSQL thật qua REQ-B-CONV-02 |
| EG-M3-7 | User duyệt phân hệ A-B và R1 Content Alpha | không tự quyết | — | pendingUserCheckpoint ở §8 |

Thứ tự lát cắt roadmap:
- 1 → B-1, B-3, B-6
- 2 → B-2, B-5, B-6
- 3 → B-6
- 4 → B-7
- 5 → B-8
- 6 → thuộc A/G (scheduler, Tier expansion), B chỉ cung cấp số đếm NEW_ARTICLE theo chủ đề ở B-10.

Test và dữ liệu bắt buộc:
- năm disposition → B-6
- representative cùng Tier ổn định, phá hòa bằng source_id → B-5
- không fact-check đa nguồn nhưng provenance bắt buộc → B-3, B-10
- News Corpus, Duplicate Clusters, Event Timeline Set version đầu → bản tổng hợp nhỏ tự soạn tests/integration/ingestion/fixtures/ingestion_corpus_v1.json (B-12), bản dữ liệu thật thuộc CP7
- SSRF, redirect, MIME giả, timeout → thuộc A.

Test ID mới của B chỉ thành oracle chính thức sau khi vào catalog qua REQ-B-CONV-08; trước đó slice dùng mô tả hành vi và ID catalog sẵn có.

## 8. Mục mở và mặc định (D8)

Mọi giá trị dưới đây là GIẢ ĐỊNH, truyền vào qua policy/config revision, không hard-code; thay đổi đi qua revision mới.

| Mã | Vấn đề | Mặc định đã chọn | Lý do | Gate xác nhận |
| --- | --- | --- | --- | --- |
| D8-B-01 | Tiêu chí trùng | exact: SHA-256 hex của văn bản đã chuẩn hóa; near: Jaccard trên shingle 5 từ ≥ 0.90; giá trị nằm trong policy `dedup-policy-r1` | đơn giản, tất định, chỉ stdlib; contract giao ngưỡng cho policy revision | hiệu chỉnh trên Duplicate Clusters thật (CP7) và mẫu chất lượng của user |
| D8-B-02 | Khóa định danh bài | `canonical_url_candidate` nếu có, ngược lại `final_url`; chuẩn hóa scheme/host chữ thường, bỏ fragment, bỏ / cuối, giữ query | không đoán tham số tracking | policy URL sau dữ liệu thật |
| D8-B-03 | NEW_REVISION | cùng khóa định danh và exact fingerprint khác → NEW_REVISION; giống hệt → nhánh trùng | "thay đổi có ý nghĩa" chưa định lượng; không làm mất revision | hiệu chỉnh CP7 |
| D8-B-04 | Media-only | bài trùng có media ref chưa gắn vào bài đại diện hoặc source_id chưa có trong provenance → DUPLICATE_MEDIA_ONLY; còn lại DUPLICATE_NO_NEW_VALUE; cả hai phát DuplicateDocumentResolved, chỉ MEDIA_ONLY mang new_media_discovery_refs | khớp CT-CNT-001 "provenance/media mới" và 02-domain-events | — |
| D8-B-05 | Tier | Tier 1 ưu tiên cao nhất (docs/01-product-spec.md FR-SRC-005, FR-SRC-006); Tier lấy qua port `SourceTierLookup`, slice dùng fake | package CT-SRC-006 không mang Tier | binding A→B qua REQ-B-CONV-07 |
| D8-B-06 | Liên kết event | luật tất định trong `event-link-policy-r1`: cùng chủ đề, chênh thời gian xuất bản ≤ 72 giờ và Jaccard từ khóa tiêu đề ≥ 0.5 → LINKED; 0.3 ≤ Jaccard < 0.5 → NEEDS_MORE_EVIDENCE; còn lại KEPT_SEPARATE; bài luôn giữ Article riêng | CT-CNT-004 mặc định giữ riêng; không dùng AI | liên kết bằng mô hình AI thuộc D/CP7 |
| D8-B-07 | Diễn biến mới | ACCEPTED_NEW_DEVELOPMENT chỉ khi bài không phải repost của bài trong event và có ≥ 1 claim candidate (port `ClaimCandidateProvider`) không khớp claim đã có, kèm evidence ref tới revision; repost → REJECTED_REPOST; mọi claim đã có → REJECTED_NO_NEW_FACT; không có claim candidate → UNCERTAIN | fail-closed: không cấp narrative timeline khi thiếu bằng chứng (CT-CNT-005) | bộ trích claim thật (AI) thuộc D/CP7 |
| D8-B-08 | Phân loại chủ đề | luật từ khóa từ topic config revision truyền vào; không khớp → `unclassified` kèm cờ không chắc chắn | CT-CNT-003 bắt buộc topic; không thêm thư viện | danh mục chủ đề do J và user |
| D8-B-09 | Thiếu content_eligibility hoặc main text rỗng | REJECTED_INCOMPLETE với reason `content_eligibility_absent` hoặc `empty_main_text`; không tạo article | phòng vệ tại B theo CT-SRC-006 lớp 2 | — |
| D8-B-10 | Thời gian | lưu UTC RFC3339 hậu tố Z; ngày nghiệp vụ đếm theo UTC tới khi chốt múi giờ | ROADMAP-OPEN-004, QUALITY-OPEN-014/TEST-OPEN-009 chưa chốt | pendingUserCheckpoint |
| D8-B-11 | Cô lập lỗi | một transaction cho mỗi collected document; lỗi hạ tầng → FAILED_RETRYABLE, lỗi tất định → FAILED_FINAL; tài liệu khác không bị ảnh hưởng | CT-STATE-003, EG-M3-5 | — |
| D8-B-12 | Grant của activity | ActivityResult lấy grant_id, execution_generation, recovery_epoch từ execution_grant của ActivityRequest; thiếu thì từ chối VALIDATION_ERROR, không dựng kết quả | không bịa định danh (CT-SRC-006, CT-WF-006) | G xác nhận khi nối workflow (REQ-B-CONV-04) |
| D8-B-13 | Lưu trữ | slice dùng adapter in-memory và unit of work ghi aggregate cùng outbox nguyên tử | migration là tài nguyên dùng chung | REQ-B-CONV-01, REQ-B-CONV-02 |

### Danh sách chờ user (pendingUserCheckpoint)

- QUALITY-OPEN-005/ROADMAP-OPEN-005 proxy hot/trending (B chỉ cung cấp dữ liệu, không chọn)
- ROADMAP-OPEN-004, QUALITY-OPEN-014/TEST-OPEN-009 múi giờ
- hiệu chỉnh ngưỡng D8-B-01, D8-B-03, D8-B-06, D8-B-07 trên mẫu chất lượng (docs/10-test-strategy.md dòng 1059)
- user duyệt phân hệ A-B và R1 Content Alpha
- USER-CKPT-D9-D10 (B không đề xuất thư viện)
- CP7 tài nguyên thật (D5)

QUALITY-OPEN-002 (thời gian tối đa một cycle) thuộc A/G, không chặn slice B.
Ngưỡng tin mới không trùng theo chủ đề là config revision của J/G; B chỉ cung cấp số đếm (B-10). Không mục nào ở đây được ghi là đã duyệt.

## 9. Thư viện (D10)

Không cần thư viện mới. Slice B chỉ dùng stdlib (hashlib, unicodedata, re, dataclasses, json, datetime, uuid, typing) và mã có sẵn trong src/controlplane. Adapter PostgreSQL (REQ-B-CONV-02) dùng psycopg==3.3.5 và psycopg-pool==3.3.1 đã có trong pyproject.toml gốc. B không có mục đề xuất cho USER-CKPT-D9-D10; nếu sau CP7 cần thuật toán near-duplicate mạnh hơn thì mở đề xuất riêng kèm phiên bản cố định.

## 10. Việc cần tài nguyên thật (CP7)

- CP7-B-1 hiệu chỉnh ngưỡng D8-B-01/03/06/07 trên News Corpus, Duplicate Clusters, Event Timeline Set dữ liệu thật thu qua A, rõ quyền dùng;
- CP7-B-2 trích claim và liên kết event bằng AI trả phí qua route J (docs/parallel-delivery/bindings/j-provider-route.json) và secret broker của J;
- CP7-B-3 đo hiệu năng resolve trên tải thật (liên quan QUALITY-OPEN-002);
- CP7-B-4 chạy E2E 12 giờ có B.

Chỉ làm sau khi user duyệt D5; dùng tài khoản thật chỉ qua secret broker của J, không mở, chép hay in bí mật. Slice B-1..B-12 không cần tài nguyên thật.

## 11. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

Các việc sau chạm tài nguyên dùng chung; slice B không làm, gói hội tụ hoặc gói phụ thuộc thực hiện, mỗi lúc một owner.

- REQ-B-CONV-01 Migration schema ingestion: bảng articles, article_revisions, collected_document_resolutions, dedup_evidence, events, event_link_candidates, event_updates, event_update_candidates kèm rollback; dùng outbox chung của migration 0003_outbox_and_projections.
- REQ-B-CONV-02 Adapter PostgreSQL cho các port trong src/ingestion/application/ports.py và unit of work chung transaction với outbox controlplane (CT-EVT-001); phụ thuộc REQ-B-CONV-01; kiểm bằng PostgreSQL harness của M2.
- REQ-B-CONV-03 Wiring composition root (src/main.py, src/controlplane/api/main.py) đăng ký dịch vụ ingestion.
- REQ-B-CONV-04 Workflow G: đăng ký activity `ResolveCollectedDocument` (B-11) trong collection workflow và subscription `CollectedDocumentAvailable` → B; một activity cho mỗi collected document.
- REQ-B-CONV-05 Control API và UI shell (H): endpoint đọc và màn hình tìm kiếm/lọc dựa trên B-10, theo dõi disposition; không thêm field ngoài contract.
- REQ-B-CONV-06 Registry: thêm tests/integration/ingestion/** vào PATH-SRC-INGESTION trong docs/parallel-delivery/ownership-and-locks.yaml.
- REQ-B-CONV-07 Binding: seam A→B tra Tier nguồn; producer theo thực thể cho CollectedDocumentResolution; schema payload 4 event B (gồm new_media_discovery_refs cho C); thống nhất kiểu schema_version/recovery_epoch giữa binding (string) và src/controlplane/domain/events/contracts.py (int).
- REQ-B-CONV-08 Catalog test: thêm test ID mới của B vào docs/10-test-strategy.md trước khi dùng làm oracle chính thức.
- REQ-B-CONV-09 Cập nhật docs/modules/capability-b-ingestion.md theo §3 (owner PATH-SRC-INGESTION); đồng bộ README.md, CHANGELOG.md, HANDOFF.md ở gói hội tụ.

State machine CT-STATE-003/004 được B hiện thực cục bộ trong src/ingestion; không sửa state machine dùng chung hay control API.

## 12. DAG, wave và lock

- W1: B-1
- W2: B-2, B-3, B-4, B-5 song song
- W3: B-6, B-7
- W4: B-8, B-10, B-11
- W5: B-9
- W6: B-12

B-1 giữ LOCK-SRC-INGESTION vì tạo các tệp __init__.py của src/ingestion; các slice khác giữ LOCK-B-<số> với ownedPaths rời nhau nên chạy song song được.
dependsOn chỉ trỏ slice trước trong slices.md hoặc gói đã có CP1-CONTRACT-BINDING, CP2A-LAYOUT.
Mỗi slice: RED bằng AssertionError đúng oracle trước implementation (ImportError hay collection error không hợp lệ); bằng chứng ở docs/delivery-evidence/b-<số>/report.md; lệnh kiểm chạy bằng interpreter khoá của lane.
Chi tiết từng slice: docs/implementation/b/slices.md.
