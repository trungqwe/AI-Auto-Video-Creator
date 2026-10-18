# Kế hoạch triển khai Phân hệ D — Trí tuệ nội dung và kế hoạch sáng tạo

- **Mã gói**: IMPL-PLAN-D
- **Ngày lập**: 18/10/2026
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`) và chỉ thị user duyệt Phần B ngày 18/10/2026 (D0–D10).
- **Trạng thái**: kế hoạch; kích hoạt sản xuất vẫn bị chặn (`PRODUCTION_ACTIVATION_BLOCKED`).
- **Danh sách slice**: `docs/implementation/d/slices.md` (D-01..D-18).

## 1. Nguồn chuẩn

- `docs/modules/capability-d-scripting.md`
- `docs/11-roadmap.md` §11 (dòng 425–485), §14, §19 (G06) và §23
- `docs/09-contracts/06-creative-ai-contracts.md` (CT-AI-000..CT-AI-010, acceptance §12)
- `docs/09-contracts/04-source-content-contracts.md` (CT-CNT-001, CT-CNT-003, CT-CNT-004, CT-CNT-005)
- `docs/09-contracts/05-content-media-contracts.md` (CT-MED-004, CT-MED-005, CT-MED-006)
- `docs/09-contracts/07-media-processing-contracts.md` (CT-TTS-001)
- `docs/09-contracts/08-render-quality-contracts.md` (CT-RND-002, CT-RND-003, CT-QC-001)
- `docs/09-contracts/09-orchestration-contracts.md` (CT-ORC-012)
- `docs/09-contracts/11-configuration-security-contracts.md` (CT-AI-ROUTE-001, CT-AI-ROUTE-002, CT-CFG-002)
- `docs/09-contracts/02-domain-events.md` (CT-EVT-002, CT-EVT-003, event của D)
- `docs/09-contracts/03-workflow-and-execution.md` (CT-WF-003, CT-WF-006)
- `docs/09-contracts/12-state-machines.md` (VariantReservation thuộc G)
- `docs/10-test-strategy.md` (dòng 522–545, 1097–1108, 1180–1201)
- `docs/05-technology-research.md` (dòng 92–108, 348–368)
- `docs/parallel-delivery/bindings/README.md` và các binding ở §5
- `docs/parallel-delivery/errata/m5-d.md`
- `docs/parallel-delivery/ownership-and-locks.yaml` (`modules.D`, `PATH-SRC-CREATIVE`, `LOCK-SRC-CREATIVE`, `LOCK-CONTRACT-CREATIVE-AI`, `PATH-COMPOSITION-ROOT`)

Khi mâu thuẫn, thứ tự ưu tiên: `docs/09-contracts` → binding và fixture CP1 → errata m5-d → `docs/modules/capability-d-scripting.md`. `docs/parallel-delivery/M5-D-contract-freeze.md`, `M5-D-execution-package.md`, `M5-D-test-plan.md` chỉ là lịch sử, không chép.

## 2. Đính chính áp dụng

Errata CP1 (`docs/parallel-delivery/errata/m5-d.md`):

- (a) INV-014 là tái khai thác không exact duplicate (`TST-AI-INV-014`), không phải thời lượng. Thời lượng 61–70 giây được kiểm trên video thật ở F (CT-QC-001 `DURATION_RANGE`); ước lượng của D chỉ là validator đầu vào, không phải oracle INV.
- (b) INV-020 là dữ liệu không tin cậy (CT-AI-000, `TST-SEC-INV-020`). Thumbnail theo CT-MED-004 và CT-RND-003 điều kiện 3: time range của thumbnail nằm trong time range của hook; không có hằng 0–3 giây.
- (c) Không có thực thể `ArticleSnapshot`; D nhận ref revision của B qua CT-AI-001 `ProductionSnapshot` và CT-CNT-003 `ArticleRevisionAccepted` (`docs/parallel-delivery/bindings/b-d-production-snapshot.json`).
- (d) Chỉ dùng test ID có trong catalog: `TST-INT-INV-004`, `TST-INT-INV-005`, `TST-CTR-INV-006`, `TST-AI-INV-013`, `TST-AI-INV-014`, `TST-SEC-INV-012`, `TST-SEC-INV-020`, `TST-WF-VAR-004` (phía D); `TST-WF-VAR-001..003` thuộc G, `TST-QC-INV-019` thuộc F. Không dùng `TST-CRE-*`.
- (e) Canary secret thuộc INV-012 (`TST-SEC-INV-012`); bản ghi lời gọi AI theo CT-AI-010.
- (f) Bằng chứng theo D4 tại `docs/delivery-evidence/<task-id viết thường>/report.md`; không ghi vào thư mục evidence đã nghiệm thu dưới `docs/milestones`.

Đính chính bổ sung cho `docs/modules/capability-d-scripting.md` (đối chiếu `docs/09-contracts`; sửa tài liệu qua CONV-D-08):

- (g) §5: INV-004 là snapshot bất biến (`TST-INT-INV-004`), INV-013 là 1–3 video cùng lượt khác StoryAngle (`TST-AI-INV-013`); không phải “fingerprint duy nhất” hay “temperature/seed”.
- (h) §2: D nhận nội dung bài qua CT-AI-001/CT-CNT-003, không qua CT-CNT-002 (quy tắc bài đại diện của B). Với F, D là input provider của `RenderPackage` (CT-RND-002/003, binding `f-render-package`), không phát hành gói render.
- (i) §4: “khoảng 140–165 từ tiếng Anh” là hằng tự đặt; tốc độ đọc lấy từ policy (§7).
- (j) §6: thiếu `tests/integration/creative/**` so với D1.
- (k) §7: lệnh `python -m unittest tests/unit/creative/test_script_generator.py -k test_duration_and_hook_constraints` không dùng; mỗi slice có lệnh pytest riêng.
- (l) §8: release giữ chỗ biến thể là quyền của G (CT-ORC-012); fallback prompt chỉ qua revision do J định tuyến (CT-AI-ROUTE-002), D không tự đổi.

## 3. Năng lực và aggregate

| Năng lực roadmap §11 (D) | Slice | Ghi chú |
| --- | --- | --- |
| 1. `ProductionSnapshot` khoá exact revision trước script | D-02, D-14 | CT-AI-001; commit trước lần gọi AI tạo script đầu tiên |
| 2. Content analysis: entities, timeline, claim/evidence, uncertainty, media needs | D-05 | CT-AI-002 |
| 3. StoryAngle 1–3 góc khác nhau trong cùng lượt | D-06, D-11 | CT-AI-003 |
| 4. Script tiếng Anh, 61–70 giây mục tiêu, pronunciation hints | D-08 | CT-AI-004; thời lượng thật kiểm ở F |
| 5. `source_backed`, `inference`, `creative_hypothesis`, `transition` theo segment | D-08 | `claim_mode` |
| 6. Disclosure bắt buộc cho inference/creative | D-08 | 100% segment |
| 7. `from_then_to_now` chỉ khi có `EventUpdateAccepted` | D-07 | CT-AI-005 |
| 8. Chọn visual hook, audio hook, thumbnail, media, music/SFX intent | D-09 | CT-AI-006, CT-MED-005 |
| 9. Production plan có scene/timeline/fallback/preset intent | D-10 | CT-AI-007 |
| 10. Variant validation trong lượt và giữa các lượt | D-11 | CT-AI-008; reservation thuộc G |
| 11. Title/caption tiếng Anh, 3–4 hashtag, representation an toàn cho filename | D-12 | CT-AI-009; sanitize thuộc I |
| 12. J điều phối provider/model/account/project/role, quota, fallback | D-04, D-15 | D chỉ là consumer CT-AI-ROUTE-001/002 |
| 13. Biên instruction-data, resolver/allowlist cho ref do model đề xuất | D-03 | CT-AI-000 |

Aggregate D sở hữu (theo `modules.D` trong `docs/parallel-delivery/ownership-and-locks.yaml`): ProductionSnapshot, StoryAngle, ScriptVersion, ProductionPlan, VariantFingerprint; bản ghi nội bộ D: ContentAnalysis, StoryAngleSet, VariantValidation, OutputMetadata, AIInvocationRecord. D không sở hữu: Article/ArticleRevision/Event/EventUpdate (B), MediaAsset/MediaAnalysis/Hook/MediaUsage (C), ProcessedMedia/VoiceTrack/WordTiming (E), Preset/RenderAttempt/QualityReport/VideoOutput (F), VariantReservation/VariantRegistryRevision/VideoJob/ExecutionGrant/CompletionLedger (G), ArtifactVersion/ArtifactLocation (I), ConfigRevision/PromptRevision/ExternalAccount/ProviderCapacity (J). D không ghi bảng của phân hệ khác và không nhận secret.

## 4. Vị trí mã theo D1

| Đường dẫn | Nội dung |
| --- | --- |
| `src/creative/domain/` | value object, validator, fingerprint thuần |
| `src/creative/application/` | command handler, xử lý lỗi provider |
| `src/creative/ports/` | Protocol: AI route/invocation, repository, đối tác |
| `src/creative/adapters/` | fake AI, in-memory |
| `src/creative/worker/` | activity handler cho G |
| `src/creative/projections/` | query truy vết read-only |
| `tests/unit/creative/` | unit |
| `tests/integration/creative/` | tích hợp in-process |

Quy tắc: import root `src/` (`import creative...`), cấm tiền tố `src.`; không tạo `src/creative/storage`, `src/creative/orchestration`, `src/creative/ui`, `src/creative/config` và không tạo `src/storage`, `src/orchestration`, `src/ui`; gói persistence (PostgreSQL) chưa tạo cho tới khi CONV-D-01 có migration.

| Module controlplane tái dùng | Dùng cho |
| --- | --- |
| `controlplane.domain.interfaces.uow.IUnitOfWork` | UoW in-memory (D-13) |
| `controlplane.domain.interfaces.outbox.IOutboxWriter` | outbox dedup theo `deduplication_id` |
| `controlplane.domain.interfaces.repository.IRepository` | repository |
| `controlplane.domain.events.contracts.DomainEvent`, `ensure_safe_event_payload` | event của D |
| `controlplane.domain.concurrency.RevisionConflictError` | expected revision |
| `controlplane.domain.common.contracts.ProblemDetail` | lỗi có cấu trúc |
| `controlplane.application.idempotency.canonicalization.request_hash` | fingerprint và idempotency |
| `controlplane.domain.orchestration.ExecutionGrant` | grant của G (D-16) |
| `controlplane.domain.orchestration.VariantReservation` | kiểu dữ liệu đọc reservation của G làm input đối chiếu (D-11); D không tạo hay release |
| `controlplane.domain.config_security.ConfigRevision`, `SecretHandle` | chỉ dùng ref; D không nhận secret |

D chỉ import, không sửa, không dựng bản trùng (không tạo VariantReservation/VariantRegistryRevision của G, ConfigRevision/PromptRevision/ProviderCapacity của J, ArtifactVersion của I). Không import `controlplane.config.router`, `controlplane.config.adapter` (adapter HTTP thật của J); nối route thật qua CONV-D-11.

## 5. Contract dùng và cung cấp

| Contract | Vai trò D | Binding/fixture |
| --- | --- | --- |
| CT-AI-001 `ProductionSnapshot` | cung cấp (producer); B, C, J cấp input | `docs/parallel-delivery/bindings/b-d-production-snapshot.json`; `tests/fixtures/contracts/b-d-production-snapshot/payloads.json` |
| CT-MED-005 `MediaCandidateQuery`/`MediaCandidate` | gửi query, dùng candidate | `docs/parallel-delivery/bindings/c-d-media-candidates.json`; `tests/fixtures/contracts/c-d-media-candidates/payloads.json` |
| CT-AI-ROUTE-001 `ProviderRouteRequest`/`ProviderRouteDecision` | gửi request, dùng decision; không nhận secret | `docs/parallel-delivery/bindings/j-provider-route.json`; `tests/fixtures/contracts/j-provider-route/payloads.json` |
| CT-TTS-001 `VoiceTrackRequest` | input provider (`script_version_id`, `script_fingerprint`, `pronunciation_hints`) | `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`; `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json` |
| CT-RND-002/003 `RenderPackage` | input provider (`production_plan_ref`, `script_version_ref`, `hook_placement`, `timeline`, `allowed_fallbacks`) | `docs/parallel-delivery/bindings/f-render-package.json`; `tests/fixtures/contracts/f-render-package/payloads.json` |
| CT-EVT-002/003 `DomainEvent` | cung cấp event của D | `docs/parallel-delivery/bindings/domain-event-envelope.json`; `tests/fixtures/contracts/domain-event-envelope/payloads.json` |
| CT-WF-003/006 `ActivityRequest`/`ActivityResult` | dùng request, cung cấp result | `docs/parallel-delivery/bindings/g-activity-execution.json`; `tests/fixtures/contracts/g-activity-execution/payloads.json` |
| CT-AI-000, CT-AI-002..CT-AI-010 | D sở hữu | chưa có binding riêng; slice bám văn bản `docs/09-contracts/06-creative-ai-contracts.md` |

1. Seam chưa có binding, xử lý fail-closed: B→D CT-CNT-003/CT-CNT-005 (`ArticleRevisionAccepted`, `EventUpdateAccepted`), C→D CT-MED-004/CT-MED-006 (thumbnail, hook candidate), J→D CT-CFG-002 (configuration bundle, prompt revision), D↔G CT-ORC-012 (chữ ký biến thể, reservation), D→I sanitize filename và lưu artifact AI (binding `i-artifact-version` chưa có D trong `modules`). Slice chỉ dùng port D-local và fake, không wiring thật; mở binding qua CONV-D-07.
2. Event D phát qua transactional outbox, at-least-once, consumer tự dedup: ProductionSnapshotCommitted, StoryAnglesGenerated, ScriptVersionCreated, ProductionPlanCreated, VariantValidated, OutputMetadataCreated (`docs/09-contracts/02-domain-events.md`); payload chỉ mang ref, revision, fingerprint; không chứa secret, prompt thô hay nội dung nguồn dài.
3. Tương thích: `additive_optional_only`; consumer bỏ qua trường lạ; binding version không hỗ trợ thì fail-closed theo CT-CMN-012; đổi phá vỡ phải tăng major binding qua MIGRATE.

## 6. Ánh xạ exit gate roadmap §11 sang slice

G1–G7 là exit gate của roadmap §11; T1–T9 là mục “Test và đánh giá bắt buộc”.

| Exit gate / test bắt buộc | Vai trò D | Slice | Cách kiểm |
| --- | --- | --- | --- |
| G1. Mọi output D truy được snapshot, model, prompt, config và input revision | AIInvocationRecord, ref trong mọi output, query truy vết | D-04, D-14, D-17 | pytest D-04 (trường bắt buộc của record), D-14 (mỗi output mang ref), D-17 (truy ngược từ plan tới snapshot) |
| G2. Ba video cùng lượt thật sự khác StoryAngle, không chỉ đổi style | distinction fingerprint và validator cùng lượt | D-06, D-11 | pytest D-06, D-11 (`TST-AI-INV-013`): ba góc chỉ khác style bị từ chối |
| G3. Variant lượt sau không exact duplicate, khác biệt thực tế được ghi | chữ ký nội dung, yếu tố khác biệt | D-11, D-14 | pytest D-11 (`TST-AI-INV-014`, `TST-WF-VAR-004` phía D); CAS reservation ở G (CONV-D-05) |
| G4. Narrative timeline bị chặn khi chỉ có repost/nguồn mới | authorize timeline | D-07 | pytest D-07 (`TST-CTR-INV-006`) |
| G5. Provider lỗi không mất job/history, không tự thêm dịch vụ trả phí | xử lý lỗi, fallback theo decision của J | D-15, D-04 | pytest D-15 với fake timeout, rate limit, sai schema; fallback ngoài `fallback_order` bị từ chối |
| G6. G06 phần content đạt hoặc có defect/gap rõ | logic xác định có test; chất lượng cần đánh giá thật | D-18 | D-18 kiểm phủ test ID; ngưỡng 90%/95% ở CP7-D-02; không tuyên bố G06 |
| G7. User duyệt D và `R3 Creative Alpha` | không tự quyết | — | pendingUserCheckpoint (§7) |

| T1. RED/GREEN `INV-004`, `INV-005`, `INV-006`, `INV-013`, `INV-014` | phía D | D-02, D-14, D-07, D-06, D-11 | `TST-INT-INV-004` → D-02/D-14; `TST-INT-INV-005` → D-02/D-14 (phía D, quyết định dedup ở B); `TST-CTR-INV-006` → D-07; `TST-AI-INV-013` → D-06/D-11; `TST-AI-INV-014` → D-11 |
| T2. Config/source đổi sau snapshot không làm job cũ thay đổi | snapshot bất biến | D-02, D-14 | pytest D-14 với hai job trước/sau đổi revision |
| T3. AI response sai schema, thiếu field, hallucinated ref, timeout/rate limit | validator và xử lý lỗi | D-03, D-05, D-08, D-15 | pytest với fake AI trả phản hồi lỗi định sẵn |
| T4. 100% inference/creative segment có disclosure | validator script | D-08 | pytest D-08 duyệt mọi segment |
| T5. Topic classification ít nhất 90% trên mẫu user đánh giá | phân loại chủ đề thuộc B (CT-CNT-003); D dùng lại | — | CP7-D-02, kế hoạch B; TEST-OPEN-001 |
| T6. Event links ít nhất 95% không gộp nhầm | ngoài D (CT-CNT-004 thuộc B) | — | kế hoạch B |
| T7. Media/thumbnail ít nhất 90%; hook combination ít nhất 90% | chất lượng lựa chọn | D-09 (logic) | CP7-D-02 với model thật và mẫu user chấm |
| T8. Không dùng model tự tạo làm judge duy nhất | validator xác định, độc lập model | D-03, D-05, D-08, D-11 | pytest khẳng định quyết định hợp lệ không đọc trường tự đánh giá của model |
| T9. Locked holdout set tách khỏi prompt-development set | corpus dùng chung | — | CONV-D-09, TEST-OPEN-001 |

Mọi CT-AI-000..CT-AI-010 và mục 1–8 của acceptance §12 trong `docs/09-contracts/06-creative-ai-contracts.md` có test trực tiếp, kiểm bằng D-18.

## 7. Mục mở và mặc định (D8)

| Mục | Mặc định cho slice | Lý do | Trạng thái |
| --- | --- | --- | --- |
| ROADMAP-OPEN-006, TEST-OPEN-001 sampling plan 90%/95% | slice chỉ kiểm logic xác định; không tuyên bố G06 | roadmap §11, §19 | pendingUserCheckpoint trước khi khoá holdout |
| Ngưỡng dedup, event-link confidence | thuộc B; D chỉ nhận ref đã quyết | CT-CNT-001, CT-CNT-004 | ghi nhận, thuộc kế hoạch B |
| ROADMAP-OPEN-005, QUALITY-OPEN-005, TEST-OPEN-004 hot/trending | `eligibility_reason` là input từ G/B; D không tự tính | CT-AI-001 | pendingUserCheckpoint trước content-selection acceptance |
| Provider/model/prompt theo vai trò | route và prompt revision là input từ J; slice dùng fake | roadmap §11 cấm khoá bằng suy đoán | pendingUserCheckpoint, CP7-D-01 |
| TEST-OPEN-003 timeout/retry/backoff provider | số lần thử và hạn là policy input, không số mặc định | roadmap §23 cấm default ẩn | pendingUserCheckpoint, CP7-D-01 |
| Tốc độ đọc để ước lượng thời lượng | `speech_rate` từ language/voice policy; giá trị chỉ có trong fixture test; thiếu → `INPUT_NOT_READY` | bỏ hằng 140–165 từ (§2 i) | pendingUserCheckpoint, hiệu chỉnh ở CP7-D-04 |
| Khoảng thời lượng mục tiêu | 61–70 giây là input CT-AI-004 truyền qua policy; D ước lượng, F kiểm trên video thật | CT-AI-004, CT-QC-001 | quyết định D8 của kế hoạch |
| Thumbnail trong hook | so time range thumbnail nằm trong time range hook; không hằng 0–3 giây | errata m5-d #2 | quyết định D8 của kế hoạch |
| ROADMAP-OPEN-009 năm preset | preset registry revision là input ref; D không định nghĩa preset | CT-AI-006, CT-AI-007 | pendingUserCheckpoint (M6) |

| Music/SFX policy, safety/rights policy khi chọn asset | policy revision là input; thiếu → `INPUT_NOT_READY` | CT-AI-006 | pendingUserCheckpoint |
| Yếu tố khác biệt biến thể | tập yếu tố lấy nguyên văn CT-AI-008 bất biến 3; tên hằng D-local là GIẢ ĐỊNH; ghi variation policy revision | CT-AI-008 | quyết định D8 của kế hoạch |
| Schema output model | typed schema D-local `creative-ai-output/v1` (tên là GIẢ ĐỊNH); model chỉ đề xuất, validator quyết định | CT-AI-010 | quyết định D8 của kế hoạch |
| `ref_type` trong `source_refs` | binding chỉ khoá mảng object; tập `ref_type` là input policy; fixture dùng `article_revision`, `event_update_accepted` (GIẢ ĐỊNH) | binding b-d-production-snapshot | quyết định D8; binding B→D qua CONV-D-07 |
| Filename-safe | qua port sanitize của I (chưa có binding), fake trong test | CT-AI-009 | quyết định D8; CONV-D-07 |
| State machine | output D bất biến, không có bảng riêng trong CT-STATE; không sửa `src/controlplane/domain/statemachine` | `docs/09-contracts/12-state-machines.md` | quyết định D8; CONV-D-06 |
| Persistence | UoW in-memory implement `IUnitOfWork`; PostgreSQL sau CONV-D-01 | migration là tài nguyên dùng chung | quyết định D8 |
| Bố cục test | không tạo `__init__.py` trong thư mục test; tên tệp `test_dNN_*.py` duy nhất | tránh trùng tên module test | quyết định D8 |
| Tái lập lời gọi AI | không khẳng định tái lập bằng temperature/seed; truy vết bằng model/prompt/config revision và fingerprint; khác biệt không tính từ seed | CT-AI-008 bất biến 4, CT-AI-010 | quyết định D8 |

### Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-006/TEST-OPEN-001, ROADMAP-OPEN-005/QUALITY-OPEN-005/TEST-OPEN-004, TEST-OPEN-003, ROADMAP-OPEN-009.
- Provider/model/prompt theo vai trò; giá trị policy tốc độ đọc, music/SFX, safety/rights.
- USER-CKPT-D9-D10: thư viện ở §8 và cách dựng lại runtime.
- CP7 theo D5: các việc ở §9.
- Exit gate G7: user duyệt D và `R3 Creative Alpha`; G06 phần content chỉ đóng sau đánh giá của user.

Không mục nào ở trên được ghi là đã duyệt; slice chỉ dùng giá trị fixture trong test và trả `INPUT_NOT_READY`/`NOT_READY` khi thiếu policy thật.

## 8. Thư viện (D10)

Slice D-01..D-18 không thêm thư viện; chỉ dùng stdlib (`dataclasses`, `enum`, `hashlib`, `json`, `re`, `unicodedata`, `datetime`, `typing`, `ast`) và module controlplane ở §4. Không dùng `pydantic==2.13.5` hay `temporalio==1.32.0` trong D dù đã có trong lock (giữ domain thuần; đăng ký activity Temporal thuộc G). Kết luận D10: domain D không cần thư viện mới.

Đề xuất tùy chọn cho USER-CKPT-D9-D10 (trước CP-2b), chỉ dành cho adapter provider ở biên, phiên bản lấy từ `docs/05-technology-research.md` dòng 348–368:

| Thư viện đề xuất | Lý do | Ghi chú |
| --- | --- | --- |
| `pydantic-ai==2.43.0` | typed output, retry/validation ở biên adapter, MIT | chọn một trong hai sau POC; domain không phụ thuộc |
| `instructor==1.17.0` | structured output gọn hơn, MIT | phương án thay thế |

Không đề xuất ở baseline: LiteLLM (chỉ khi số provider/tài khoản đủ lớn, thuộc J), LangChain (không làm lõi), vLLM (không hợp GPU 12 GB). Ollama/llama.cpp là runtime ngoài cho local fallback (CP7-D-03), không phải gói Python của D. Sentence Transformers không cần cho D vì exact duplicate dùng fingerprint. Phiên bản phải xác minh lại ở checkpoint; không dùng `latest`.

## 9. Việc cần tài nguyên thật (CP7)

Chỉ chạy sau khi user duyệt D5; tài khoản/credential chỉ qua secret broker của J, không mở, chép hay in bí mật.

- CP7-D-01: gọi provider/model thật qua route J cho từng vai trò (analysis, angle, script, selection, metadata); benchmark chất lượng, latency, chi phí, timeout/retry (roadmap §11 mục mở 4, TEST-OPEN-003).
- CP7-D-02: đánh giá G06 phần content: topic, media/thumbnail, hook combination đạt ngưỡng 90% trên mẫu user chấm; locked holdout tách prompt-development set; không dùng model tự tạo làm judge duy nhất.
- CP7-D-03: local fallback Ollama/llama.cpp trên desktop GPU 12 GB, giữ queue/history.
- CP7-D-04: đối chiếu thời lượng ước lượng với `actual_duration_ms` của voice thật (E) để hiệu chỉnh policy tốc độ đọc.
- CP7-D-05: quota/chi phí thật theo route J (G03); không tự thêm dịch vụ trả phí.

## 10. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

| Mã | Tài nguyên dùng chung | Yêu cầu | Slice D liên quan |
| --- | --- | --- | --- |
| CONV-D-01 | migration | bảng production_snapshot (unique `snapshot_id`, bất biến), content_analysis, story_angle_set, story_angle, script_version, production_plan, variant_validation, output_metadata, ai_invocation_record, receipt; append-only; index theo job, snapshot, phạm vi article/event; sau đó mở slice D tạo `src/creative/persistence` | D-13 |
| CONV-D-02 | composition root (`PATH-COMPOSITION-ROOT`: `src/main.py`, `src/controlplane/api/main.py`) | wiring command, worker, query của D và route adapter J thay fake | D-14, D-16, D-17 |
| CONV-D-03 | control API | route chạy/xem từng stage D (TST-E2E-014) và query truy vết; cần binding H↔G | D-14, D-17 |
| CONV-D-04 | UI shell (H, `ui/dist`, `App.tsx`) | màn hình D của M5: snapshot, angle, script kèm `claim_mode`/disclosure, plan, variant, trace | D-17 |
| CONV-D-05 | workflow G | creative workflow (CT-WF-001), `WAITING_CAPABILITY` trước CT-AI-004/007, ReserveVariant CT-ORC-012 dùng chữ ký của D, CAS registry trước completion, đăng ký activity D | D-11, D-16 |
| CONV-D-06 | state machine dùng chung | xác nhận D không cần bảng transition riêng; nếu G cần trạng thái stage creative thì thêm qua `LOCK-CONTRACT-STATE-MACHINES` | D-14 |
| CONV-D-07 | registry binding | mở binding B→D CT-CNT-003/CT-CNT-005, C→D CT-MED-004/CT-MED-006, J→D CT-CFG-002, D↔G CT-ORC-012, D→I (thêm D vào `i-artifact-version`, sanitize filename) | D-02, D-07, D-09, D-11, D-12 |
| CONV-D-08 | tài liệu và registry ownership | thêm `tests/integration/creative/**` vào `PATH-SRC-CREATIVE`; sửa `docs/modules/capability-d-scripting.md` theo §2 (g)–(l) | D-14, D-15, D-16 |
| CONV-D-09 | catalog test và corpus dùng chung | prompt-development set và locked holdout có version dưới `tests/fixtures`; test ID mới (nếu cần) vào `docs/10-test-strategy.md` | D-18 |
| CONV-D-10 | outbox/event catalog | đăng ký 6 event của D với publisher dùng chung | D-13, D-14 |
| CONV-D-11 | route provider J | adapter từ `ProviderRoutePort`/`AIInvocationPort` của D sang resolver CT-AI-ROUTE-001 và `controlplane.config.router.ProviderRouter` của J, qua secret broker | D-04, D-15 |

## 11. Thứ tự slice (DAG)

- Đợt 1: D-01.
- Đợt 2 (song song): D-02, D-03, D-12.
- Đợt 3 (song song): D-04, D-05, D-07, D-09.
- Đợt 4 (song song): D-06, D-08.
- Đợt 5: D-10.
- Đợt 6: D-11.
- Đợt 7: D-13.
- Đợt 8 (song song): D-14, D-17.
- Đợt 9 (song song): D-15, D-16.
- Đợt 10: D-18.

D-01 giữ `LOCK-SRC-CREATIVE` vì tạo cây gói; các slice khác giữ `LOCK-<taskId>` và sở hữu tệp riêng nên chạy song song được. dependsOn chi tiết nằm trong `docs/implementation/d/slices.md`.

## 12. Ngoài phạm vi

Quyết định Article/revision/dedup/event link (B), media catalog và hook import (C), voice và word timing (E), render/QC và thời lượng thật (F), reservation/completion/batch (G), UI (H), lưu trữ và sanitize filename (I), route/secret/quota (J); script edit/approval (v1 không có theo CT-AI-004); fact-check đa nguồn bắt buộc và xuất bản YouTube (roadmap §25).
