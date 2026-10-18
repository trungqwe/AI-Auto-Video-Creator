# Báo cáo bằng chứng IMPL-PLAN-B

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: f40822e0ea258ed799fffa781c2c7b06776dd21a

## Nguồn đã đọc

- AGENTS.md
- HANDOFF.md
- docs/12-pre-code-checklist.md
- docs/modules/capability-b-ingestion.md
- docs/11-roadmap.md (§9, §14, §23)
- docs/01-product-spec.md (FR-SRC-005, FR-SRC-006)
- docs/09-contracts/04-source-content-contracts.md
- docs/09-contracts/02-domain-events.md
- docs/09-contracts/12-state-machines.md
- docs/10-test-strategy.md (dòng 194–196, §14.2, §15, dòng 1059)
- docs/parallel-delivery/bindings/README.md
- docs/parallel-delivery/bindings/a-b-collected-document.json
- docs/parallel-delivery/bindings/b-d-production-snapshot.json
- docs/parallel-delivery/bindings/domain-event-envelope.json
- docs/parallel-delivery/bindings/g-activity-execution.json
- tests/fixtures/contracts/a-b-collected-document/payloads.json
- tests/fixtures/contracts/domain-event-envelope/payloads.json
- docs/parallel-delivery/errata/m3-a.md
- docs/parallel-delivery/ownership-and-locks.yaml
- docs/parallel-delivery/task-dag.yaml (TASK-CAP-B-INGESTION)
- src/controlplane/domain/events/contracts.py
- src/controlplane/domain/interfaces/outbox.py
- pyproject.toml
- docs/delivery-evidence/cp1-contract-binding/report.md
- docs/delivery-evidence/cp2a-layout/report.md

## RED

- Exit code: 1
- Dòng lỗi cuối: FileNotFoundError: [Errno 2] No such file or directory: 'docs\\implementation\\b\\plan.md'

## Thay đổi

- docs/implementation/b/plan.md
- docs/implementation/b/slices.md
- docs/delivery-evidence/impl-plan-b/report.md

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 1 | instrument nghiệm thu | 0 | PASS (không output) |
| 2 | kiểm cấu trúc slices.md | 0 | PASS (không output) |
| 3 | kiểm nội dung plan/report | 0 | PASS (không output) |
| 4 | kiểm vệ sinh văn bản | 0 | PASS (không output) |
| 5 | `git diff --check` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

- D8-B-01: Tiêu chí trùng gồm exact SHA-256 hex và near Jaccard trên shingle 5 từ ≥ 0.90 theo policy dedup-policy-r1.
- D8-B-02: Khóa định danh bài ưu tiên canonical_url_candidate, fallback
inal_url đã chuẩn hóa scheme/host và bỏ fragment/slash cuối.
- D8-B-03: Cùng khóa định danh và exact fingerprint khác thì xếp vào NEW_REVISION; giống hệt xếp vào nhánh trùng.
- D8-B-04: Bài trùng có media ref mới hoặc source_id mới thì phát DUPLICATE_MEDIA_ONLY; còn lại DUPLICATE_NO_NEW_VALUE.
- D8-B-05: Nguồn Tier 1 ưu tiên cao nhất, tra cứu qua port SourceTierLookup (slice dùng fake).
- D8-B-06: Luật liên kết event tất định trong event-link-policy-r1: cùng chủ đề, thời gian ≤ 72h, Jaccard từ khóa tiêu đề ≥ 0.5 → LINKED; 0.3 ≤ Jaccard < 0.5 → NEEDS_MORE_EVIDENCE; còn lại KEPT_SEPARATE; luôn giữ bài riêng.
- D8-B-07: Diễn biến mới ACCEPTED_NEW_DEVELOPMENT chỉ khi bài không phải repost và có ≥ 1 claim mới không trùng claim đã có kèm evidence ref; ngược lại REJECTED_REPOST, REJECTED_NO_NEW_FACT hoặc UNCERTAIN.
- D8-B-08: Phân loại chủ đề theo luật từ khóa từ config revision; không khớp trả unclassified kèm cờ không chắc chắn.
- D8-B-09: Thiếu content_eligibility hoặc main text rỗng bị từ chối REJECTED_INCOMPLETE với lý do tương ứng, không tạo article.
- D8-B-10: Thời gian lưu UTC RFC3339 hậu tố Z; ngày nghiệp vụ đếm theo UTC tới khi chốt múi giờ.
- D8-B-11: Mỗi collected document một transaction cô lập; lỗi hạ tầng trả FAILED_RETRYABLE, lỗi tất định trả FAILED_FINAL; không ảnh hưởng tài liệu khác.
- D8-B-12: ActivityResult lấy grant_id, execution_generation, recovery_epoch từ execution_grant của ActivityRequest; thiếu thì từ chối VALIDATION_ERROR.
- D8-B-13: Slice dùng adapter InMemoryUnitOfWork ghi aggregate và outbox nguyên tử; migration PostgreSQL là tài nguyên dùng chung.

## Thư viện (D10)

Không thêm thư viện; xem plan.md §9.

## Danh sách chờ user (pendingUserCheckpoint)

- QUALITY-OPEN-005/ROADMAP-OPEN-005 proxy hot/trending (B chỉ cung cấp dữ liệu, không chọn)
- ROADMAP-OPEN-004, QUALITY-OPEN-014/TEST-OPEN-009 múi giờ
- hiệu chỉnh ngưỡng D8-B-01, D8-B-03, D8-B-06, D8-B-07 trên mẫu chất lượng (docs/10-test-strategy.md dòng 1059)
- user duyệt phân hệ A-B và R1 Content Alpha
- USER-CKPT-D9-D10 (B không đề xuất thư viện)
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9)

## Yêu cầu gửi IMPL-PLAN-CONVERGENCE

- REQ-B-CONV-01: Migration schema ingestion: bảng articles, article_revisions, collected_document_resolutions, dedup_evidence, events, event_link_candidates, event_updates, event_update_candidates kèm rollback; dùng outbox chung của migration 0003_outbox_and_projections.
- REQ-B-CONV-02: Adapter PostgreSQL cho các port trong src/ingestion/application/ports.py và unit of work chung transaction với outbox controlplane (CT-EVT-001); phụ thuộc REQ-B-CONV-01; kiểm bằng PostgreSQL harness của M2.
- REQ-B-CONV-03: Wiring composition root (src/main.py, src/controlplane/api/main.py) đăng ký dịch vụ ingestion.
- REQ-B-CONV-04: Workflow G: đăng ký activity ResolveCollectedDocument (B-11) trong collection workflow và subscription CollectedDocumentAvailable → B; một activity cho mỗi collected document.
- REQ-B-CONV-05: Control API và UI shell (H): endpoint đọc và màn hình tìm kiếm/lọc dựa trên B-10, theo dõi disposition; không thêm field ngoài contract.
- REQ-B-CONV-06: Registry: thêm tests/integration/ingestion/** vào PATH-SRC-INGESTION trong docs/parallel-delivery/ownership-and-locks.yaml.
- REQ-B-CONV-07: Binding: seam A→B tra Tier nguồn; producer theo thực thể cho CollectedDocumentResolution; schema payload 4 event B (gồm new_media_discovery_refs cho C); thống nhất kiểu schema_version/recovery_epoch giữa binding (string) và src/controlplane/domain/events/contracts.py (int).
- REQ-B-CONV-08: Catalog test: thêm test ID mới của B vào docs/10-test-strategy.md trước khi dùng làm oracle chính thức.
- REQ-B-CONV-09: Cập nhật docs/modules/capability-b-ingestion.md theo §3 (owner PATH-SRC-INGESTION); đồng bộ README.md, CHANGELOG.md, HANDOFF.md ở gói hội tụ.

## Giới hạn

Kế hoạch là tài liệu, chưa có mã; không sửa ngoài owned paths; git diff --check chỉ xét thay đổi của tệp đã theo dõi nên tệp mới được kiểm thêm bằng lệnh vệ sinh văn bản (bước 25).
