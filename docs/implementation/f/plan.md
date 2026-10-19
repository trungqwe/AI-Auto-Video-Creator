# Kế hoạch triển khai Phân hệ F — Preset, dựng video và kiểm tra đầu ra

- **Mã gói**: IMPL-PLAN-F
- **Ngày lập**: 19/10/2026
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`) và chỉ thị user duyệt Phần B ngày 18/10/2026 (D0–D10)
- **Trạng thái**: kế hoạch; kích hoạt sản xuất vẫn bị chặn (`PRODUCTION_ACTIVATION_BLOCKED`); kế hoạch không cấp quyền sửa mã ngoài các slice trong `docs/implementation/f/slices.md`
- **Danh sách slice**: `docs/implementation/f/slices.md` (F-01..F-22)

## 1. Nguồn chuẩn

- `docs/modules/capability-f-rendering.md` (chỉ dùng sau khi áp dụng đính chính ở §2)
- `docs/11-roadmap.md` §10 (dòng 413), §12 (năng lực F, test bắt buộc, exit gate, điểm còn mở), §19 (G06, G07), §23 (ROADMAP-OPEN-007..010)
- `docs/09-contracts/08-render-quality-contracts.md` (CT-RND-001..006, CT-QC-001, CT-QC-002, acceptance §8)
- `docs/09-contracts/07-media-processing-contracts.md` (CT-TTS-001, CT-SUB-001, CT-AUD-001: đầu vào của F)
- `docs/09-contracts/05-content-media-contracts.md` (dòng 15: F chỉ dùng asset revision đã khóa)
- `docs/09-contracts/10-storage-contracts.md` (CT-STO-001, CT-STO-004, CT-STO-006, CT-STO-007)
- `docs/09-contracts/09-orchestration-contracts.md` (CT-ORC-008, CT-ORC-009)
- `docs/09-contracts/02-domain-events.md` (event của F, CT-EVT-002, CT-EVT-003)
- `docs/09-contracts/03-workflow-and-execution.md` (CT-WF-003, CT-WF-006, đọc qua binding)
- `docs/09-contracts/12-state-machines.md` (CT-STATE-008, CT-STATE-011, CT-STATE-012)
- `docs/10-test-strategy.md` (§12.6 dòng 386–401; bảng INV dòng 524–545; E2E dòng 549–605; §20.3 dòng 862–869; dòng 833 và 837; TEST-OPEN-003, -005, -006)
- `docs/05-technology-research.md` (mục 5.14, FFmpeg filter graph dòng 274–279, TECH-OPEN-012 dòng 473)
- `docs/parallel-delivery/bindings/README.md`
- binding: `docs/parallel-delivery/bindings/f-render-package.json`, `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`, `docs/parallel-delivery/bindings/g-activity-execution.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`
- fixture CP1 của đúng sáu seam trên: `tests/fixtures/contracts/f-render-package/payloads.json`, `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`, `tests/fixtures/contracts/i-artifact-version/payloads.json`, `tests/fixtures/contracts/g-activity-execution/payloads.json`, `tests/fixtures/contracts/domain-event-envelope/payloads.json`, `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- `docs/parallel-delivery/errata/m6-ef.md`
- `docs/parallel-delivery/ownership-and-locks.yaml` (`modules.F`, `PATH-SRC-RENDER`, `LOCK-SRC-RENDER`, `LOCK-CONTRACT-RENDER-QUALITY`, `LOCK-DESKTOP-GPU`, `PATH-IMPLEMENTATION-PLANS`)
- `docs/parallel-delivery/acceptance-matrix.yaml` (R11–R13, `TASK-CAP-F-RENDERING`)
- Kế hoạch tham chiếu bố cục và seam: `docs/implementation/d/plan.md`, `docs/implementation/e/plan.md`, `docs/implementation/i/plan.md`
- Mã đã có, chỉ đọc: `src/controlplane/domain/statemachine/__init__.py` (`OperationState`, `ArtifactLocationState`, `transition_operation`, `ReconciliationEvidence`), `src/controlplane/domain/interfaces/uow.py` (`IUnitOfWork`), `src/controlplane/domain/interfaces/outbox.py` (`IOutboxWriter`), `src/controlplane/domain/events/contracts.py` (`DomainEvent`, `ensure_safe_event_payload`), `src/controlplane/domain/concurrency.py` (`RevisionConflictError`), `src/controlplane/domain/common/contracts.py` (`ProblemDetail`), `src/controlplane/domain/orchestration/__init__.py` (`ExecutionGrant`), `src/controlplane/application/idempotency/canonicalization.py` (`request_hash`)

Thứ tự ưu tiên khi mâu thuẫn: `docs/09-contracts` → binding và fixture CP1 → errata m6-ef (`docs/parallel-delivery/errata/m6-ef.md`) → `docs/modules/capability-f-rendering.md`.

Ba tệp `docs/parallel-delivery/M6-EF-contract-freeze.md`, `docs/parallel-delivery/M6-EF-execution-package.md`, `docs/parallel-delivery/M6-EF-test-plan.md` bị hỏng dấu tiếng Việt (ký tự `?` thay chữ có dấu): không dùng làm nguồn, oracle hay bằng chứng và không chép; kế hoạch được viết lại từ nguồn chuẩn.

## 2. Đính chính áp dụng

Errata CP1 (`docs/parallel-delivery/errata/m6-ef.md`):

- (a) Không có state machine riêng cho Preset hay RenderAttempt (nguyên tắc errata #1): receipt của RenderAttempt dùng CT-STATE-011 qua `OperationState` và `transition_operation` có sẵn ở `src/controlplane/domain/statemachine/__init__.py`; stage dùng CT-STATE-008 (thuộc G); location artifact dùng CT-STATE-012 (thuộc I). Slice F không thêm máy trạng thái.
- (b) Mã invariant theo catalog `docs/10-test-strategy.md` (errata #2): INV-007 `TST-MEDIA-INV-007` timing gắn script/voice; INV-008 `TST-INT-INV-008` render package chỉ chứa artifact đã verify; INV-009 `TST-E2E-INV-009` QC pass mà upload chưa verify thì không completion, không xóa local; INV-010 `TST-WF-INV-010` và INV-011 `TST-DR-INV-011` thuộc G và I; INV-012 `TST-SEC-INV-012` canary secret; INV-019 `TST-QC-INV-019` bằng chứng tiếng Anh theo exact revision; INV-020 `TST-SEC-INV-020` dữ liệu không tin cậy (path, shell metacharacter).
- (c) Thumbnail cố định 0–3 giây là quy tắc tự đặt (errata #3): dùng CT-RND-003 điều kiện 3, time range của thumbnail nằm trong time range của hook.
- (d) Chỉ dùng test ID có trong catalog (errata #4): không dùng tiền tố `TST-MED-`, `TST-VOI-`, `TST-RND-`, `TST-EF-`; test ID mới phải vào catalog qua slice sở hữu tài liệu đó (CONV-F-09).
- (e) Bằng chứng theo D4 tại `docs/delivery-evidence/<task-id viết thường>/report.md`; không ghi vào thư mục evidence đã nghiệm thu dưới `docs/milestones`.

Đính chính bổ sung cho `docs/modules/capability-f-rendering.md` (đối chiếu `docs/09-contracts`; sửa tài liệu qua CONV-F-08):

- (f) §5: INV-001 là command idempotency (`TST-CTR-INV-001`), INV-002 là event idempotency (`TST-CTR-INV-002`), INV-009 không phải dọn tệp tạm (là `TST-E2E-INV-009`), INV-018 là allocator (`TST-WF-INV-018`), không phải cổng QC. Kích thước và thời lượng là gate `OUTPUT_PROFILE_VALID` và `DURATION_RANGE` (CT-QC-001); điều kiện chuyển giao là CT-RND-005.
- (g) §1 và §4 mục 2: 1080x1920, 30fps, H.264, AAC là hằng tự đặt; output profile là ROADMAP-OPEN-007, QUALITY-OPEN-006, TEST-OPEN-005 và TECH-OPEN-012, tham số hóa theo `output_profile_revision`. 61–70 giây là `DURATION_RANGE` (CT-QC-001), khoảng nằm trong quality policy revision.
- (h) §4 mục 4: 'lệch tiếng không quá 50ms' và 'không dropped frames bất thường' là hằng tự đặt; sai số karaoke là ROADMAP-OPEN-008, QUALITY-OPEN-007, TEST-OPEN-006 chưa chốt; `VISUAL_CONTINUITY` và `AUDIO_MIX_QUALITY` là warning/score.
- (i) §4 mục 4: thumbnail trích từ 3 giây đầu là quy tắc tự đặt; thumbnail phải nằm trong time range hook (CT-RND-003 điều kiện 3, gate `THUMBNAIL_PRESENT`).
- (j) §2: cổng vào là `RenderPackage` do F resolve từ ref của C, D, E, I (CT-RND-002, binding `f-render-package`), D chỉ là input provider. F không gửi video thẳng cho I: F trả output ready cho G (CT-RND-005), G yêu cầu I đồng bộ và verify (CT-STO-006) rồi mới commit completion (CT-ORC-008). CT-QC-001 là `InspectOutput`, không phải cổng bàn giao.
- (k) §3 mục 3 và §8: slot `LOCK-DESKTOP-GPU` do LeaseManager và G cấp; F chỉ giữ qua port lease và trả khi xong hoặc lỗi. 'Hủy RenderAttempt' và 'xóa sạch tệp tạm' trái nguyên tắc: attempt bất biến, lỗi ghi thành attempt thất bại, retry dùng attempt và artifact mới (CT-RND-004, CT-STATE-011); F không xóa tệp, cleanup thuộc I (CT-STO-007, CT-STO-008) và exit gate M6.
- (l) §3 mục 2 và §6: binary ffmpeg, ffprobe khóa theo toolchain là việc của CONV-F-13 và CP7, slice dùng metadata giả; thiếu `tests/integration/render/**` so với D1 (CONV-F-08); 'Forbidden `src/controlplane/**`' nghĩa là không sửa, F vẫn import module có sẵn ở chế độ chỉ đọc.
- (m) §7: lệnh `python -m unittest tests/unit/render/test_video_pipeline.py -k test_output_specs_and_karaoke` và ba tên test của `TASK-CAP-F-RENDERING` (`test_video_pipeline.py`, `test_karaoke_subtitle.py`, `test_qc_verification.py`) không dùng; mỗi slice có tệp `test_fNN_*.py` và lệnh pytest riêng; cập nhật acceptance-matrix qua CONV-F-08.
- (n) §1: 'tự động loại video ngoài 61–70 giây' hiểu theo CT-QC-001: gate fail thì không tạo `VideoOutput` ready; F không tự cắt hay kéo video cho vừa khoảng vì F không đổi nội dung.

## 3. Năng lực và aggregate

| Năng lực roadmap §12 (Năng lực F) | Contract | Slice |
|---|---|---|
| Thiết kế chi tiết đúng năm preset, mỗi preset có revision, resolve deterministic | CT-RND-001 | F-02 |
| Resolve immutable render package với exact artifact refs/hash | CT-RND-002 | F-03, F-04, F-05, F-17 |
| Validate input sớm trước render nặng | CT-RND-003 | F-06, F-07, F-08, F-17 |
| Render attempt, receipt và outcome-unknown reconciliation | CT-RND-004, CT-STATE-011 | F-10, F-11, F-18 |
| QC tự động: playability, duration, output profile, hook, thumbnail, voice, subtitle, bằng chứng tiếng Anh của exact revision | CT-QC-001, CT-QC-002 | F-12, F-13, F-14, F-19 |
| Burn-in subtitle tiếng Anh và karaoke từng từ | CT-RND-002 (`subtitle_config`), CT-SUB-001 (đầu vào), CT-QC-001 | F-09, F-10, F-14 |
| Kiểm tra disclosure đầu ra khi có inference/creative segment | CT-QC-001 `INFERENCE_DISCLOSURE_PRESENT` | F-14 |
| Output ready cho G; đồng bộ cloud và verify thuộc I, completion thuộc G | CT-RND-005, CT-STO-006, CT-ORC-008 | F-15, F-19 |
| Lưu bất biến, unit of work, outbox, event của F | CT-EVT-002, CT-EVT-003 | F-16 |
| Activity cho G, truy vết, ma trận test | CT-WF-003, CT-WF-006 | F-20, F-21, F-22 |

Aggregate F sở hữu theo `modules.F` trong `docs/parallel-delivery/ownership-and-locks.yaml`: `Preset` (`RenderPresetRevision`), `RenderAttempt`, `QualityReport`, `VideoOutput`; bản ghi nội bộ của F (tên là GIẢ ĐỊNH, chưa có trong contract): `RenderPackage` bất biến (producer theo binding), `PackageValidationReport`, `OutputInspectionEvidence`.

F không sở hữu: MediaAsset, Hook, MediaUsage (C); ScriptVersion, ProductionPlan, OutputMetadata (D); ProcessedMedia, VoiceTrack, WordTiming (E); VideoJob, StageRun, ExecutionGrant, CompletionLedger (G); ArtifactVersion, ArtifactLocation, path allocator, sanitize filename, cleanup (I); ConfigRevision, secret, route (J). F không ghi bảng của phân hệ khác và không nhận secret.

Không dựng cây trùng aggregate đã có trong `src/controlplane`: `RenderPresetRevision` chỉ định nghĩa trong `src/render/domain`, không đặt vào `controlplane.config_security` (ConfigRevision thuộc J); đồng bộ với cấu hình của J qua CONV-F-06; receipt dùng `OperationState` có sẵn.

## 4. Vị trí mã theo D1

| Đường dẫn | Nội dung |
|---|---|
| `src/render/domain/` | value object, validator, fingerprint, cổng gate thuần |
| `src/render/application/` | command handler, pipeline |
| `src/render/ports/` | Protocol cho đầu vào resolve, lease GPU, renderer, probe và inspector output, repository |
| `src/render/adapters/` | fake và in-memory |
| `src/render/worker/` | activity handler cho G |
| `src/render/projections/` | query truy vết read-only |
| `tests/unit/render/` | unit |
| `tests/integration/render/` | tích hợp in-process |

Quy tắc: import root `src/` (`import render...`), cấm tiền tố `src.`; không tạo `src/render/storage`, `src/render/orchestration`, `src/render/ui`, `src/render/config` và không tạo `src/storage`, `src/orchestration`, `src/ui`; không tạo persistence PostgreSQL và adapter FFmpeg, ffprobe, inspector thật cho tới khi CONV-F-01 và CONV-F-02 có migration và wiring; test không có `__init__.py`, tên tệp `test_fNN_*.py` duy nhất; không import `creative`, `voice`, `catalog` hay gói của phân hệ khác, phối hợp chỉ qua binding, port F-local và fake; F không có hàm xóa, đổi tên hay ghi đè tệp và không import `subprocess`, `os`, `shutil`, `tempfile` (F-01 kiểm bằng `ast`).

| Module controlplane tái dùng (chỉ import) | Dùng cho | Slice |
|---|---|---|
| `controlplane.domain.statemachine` (`OperationState`, `transition_operation`, `ReconciliationEvidence`, `ForbiddenTransitionError`) | receipt RenderAttempt | F-11, F-18 |
| `controlplane.domain.statemachine.ArtifactLocationState` | điều kiện artifact `VERIFIED` | F-07 |
| `controlplane.domain.interfaces.uow.IUnitOfWork` | UoW in-memory | F-16 |
| `controlplane.domain.interfaces.outbox.IOutboxWriter` | outbox dedup | F-16 |
| `controlplane.domain.events.contracts` (`DomainEvent`, `ensure_safe_event_payload`) | event của F | F-16 |
| `controlplane.domain.concurrency.RevisionConflictError` | expected revision | F-16 |
| `controlplane.domain.common.contracts.ProblemDetail` | lỗi có cấu trúc | F-17..F-20 |
| `controlplane.application.idempotency.canonicalization.request_hash` | fingerprint, idempotency | F-02, F-04, F-10, F-17 |
| `controlplane.domain.orchestration.ExecutionGrant` | grant của G | F-17..F-20 |

F chỉ import, không sửa, không dựng bản trùng; không import `controlplane.config.router` và `controlplane.config.adapter` của J (CONV-F-11).

## 5. Contract dùng và cung cấp

| Contract | Vai trò F | Binding và fixture |
|---|---|---|
| CT-RND-002/003 `RenderPackage` | cung cấp (producer); C, D, E, I là input provider; F, G là consumer | `docs/parallel-delivery/bindings/f-render-package.json`; `tests/fixtures/contracts/f-render-package/payloads.json` |
| CT-TTS-001 `VoiceTrackResult`, CT-SUB-001 `WordTiming` | consumer: F kiểm lại binding khi resolve và khi dựng karaoke | `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`; `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json` |
| CT-STO-001 `DeclareArtifactVersion` | consumer: giữ `artifact_version_id`, `content_sha256`, `size_bytes`, `media_type` của input; output của F được I khai báo | `docs/parallel-delivery/bindings/i-artifact-version.json`; `tests/fixtures/contracts/i-artifact-version/payloads.json` |
| CT-EVT-002/003 `DomainEvent` | cung cấp 2 event của F: `RenderCompleted`, `OutputQualityChecked` | `docs/parallel-delivery/bindings/domain-event-envelope.json`; `tests/fixtures/contracts/domain-event-envelope/payloads.json` |
| CT-WF-003/006 `ActivityRequest`/`ActivityResult` | dùng request, cung cấp result | `docs/parallel-delivery/bindings/g-activity-execution.json`; `tests/fixtures/contracts/g-activity-execution/payloads.json` |
| CT-ORC-008/009 | F là input provider (`render_attempt_ref`, `quality_report_ref`, `preset_revision_ref`) cho `CommitVideoCompletionRequest` và `CompletionLedgerEntry` của G | `docs/parallel-delivery/bindings/g-c-i-completion.json`; `tests/fixtures/contracts/g-c-i-completion/payloads.json` |
| CT-RND-001, CT-RND-004, CT-RND-005, CT-RND-006, CT-QC-001, CT-QC-002 | F sở hữu | chưa có binding riêng; slice bám văn bản `docs/09-contracts/08-render-quality-contracts.md` |

1. Seam chưa có binding, xử lý fail-closed: D→F hình dạng `timeline.segments` và disclosure (binding chỉ khai `timeline` là object); E→F nội dung `language_validation_refs` và `mix_plan` (CT-AUD-001); F→I CT-STO-006 `PersistVideoOutput` (README bindings nêu F→I chưa có binding); I→F staging root, output path (CT-STO-004, CT-STO-011); J→F cấu hình preset và tool capability (CT-CFG-002); F→G output ready (CT-RND-005). Slice dùng port F-local và fake, không wiring thật; mở binding qua CONV-F-07.
2. Event F phát qua transactional outbox, at-least-once, consumer tự dedup; payload chỉ mang ref, hash, revision, tóm tắt trạng thái gate; không chứa byte video, argv, đường dẫn tuyệt đối hay secret. `RenderCompleted` chỉ phát khi attempt `SUCCEEDED`; `OutputQualityChecked` phát cả khi QC fail. Không event nào là `VideoCompleted` (thuộc G).
3. Tương thích `additive_optional_only`; consumer bỏ qua trường lạ; binding version không hỗ trợ thì fail-closed theo CT-CMN-012; đổi phá vỡ phải tăng major binding qua MIGRATE.
4. Output của F chỉ là artifact đã verify sau khi I verify; F không tự đánh dấu verified.

## 6. Ánh xạ exit gate roadmap sang slice

Bảng dưới đây ánh xạ các exit gate và test bắt buộc của roadmap §10 (M4) và §12 (M6) mà Phân hệ F phục vụ; các gate không thuộc phạm vi của F được ghi rõ để đảm bảo không bỏ sót trách nhiệm.

| Exit gate / test bắt buộc | Vai trò F | Slice | Cách kiểm |
|---|---|---|---|
| M4 (§10 dòng 413): render tương lai chỉ lấy artifact local đã verify; `TST-INT-INV-008` | điều kiện CT-RND-003 số 7 | F-07, F-08 | pytest: artifact không `VERIFIED`, hash hoặc size lệch → finding; renderer fake 0 lượt gọi |
| M6 `INV-007` (`TST-MEDIA-INV-007`) phần F | consumer: voice, timing, package khớp exact script fingerprint và voice hash | F-06, F-17 | pytest: đổi `voice_hash` hoặc `script_fingerprint` giữa WordTiming, VoiceTrack, package → fail sớm |
| M6 `INV-008` (`TST-INT-INV-008`) | package gồm voice và timing chỉ chứa artifact đã verify | F-07, F-08, F-17 | pytest như hàng 1 |
| M6 `INV-009` (`TST-E2E-INV-009`) | QC pass nhưng upload chưa verify thì output ready mà `completion_eligible` sai; F không xóa local | F-15, F-19 | pytest; `ast` không có hàm xóa |
| M6 `INV-010`, `INV-011` | thuộc G và I; F không đếm completion, không cleanup | — | ghi nhận, không có slice F |
| `INV-012` (`TST-SEC-INV-012`) | canary secret trong lỗi renderer, command spec, event | F-10, F-11, F-16, F-18 | pytest: canary không xuất hiện trong repr, dict, JSON |
| `INV-019` (`TST-QC-INV-019`) | F kiểm lại binding và gate `ENGLISH_OUTPUT_VALID` | F-07, F-14 | pytest: revision lệch hoặc chỉ `language=en` tự khai → hard fail |
| `INV-020` (`TST-SEC-INV-020`) phần F | path, shell, URL trong package và command spec bị từ chối | F-03, F-07, F-10 | pytest: `shell_command`, `arbitrary_url`, `..`, UNC |
| M6: word timing monotonic, coverage, exact binding, invalidation | F kiểm lại WordTiming khi resolve; karaoke theo mốc | F-06, F-09, F-14 | pytest: mọi case fixture `WordTiming` |
| M6: package thiếu hook, audio hook, thumbnail trong vùng hook, voice, timing phải fail sớm | CT-RND-003 số 1–4 | F-06, F-08, F-17 | pytest: mỗi thiếu một finding riêng; renderer fake 0 lượt |
| M6: FFmpeg crash, partial file, timeout sau side effect, output corrupt | attempt `failed` hoặc `OUTCOME_UNKNOWN`; reconcile bằng probe trước retry | F-11, F-13, F-18 | pytest tiêm lỗi trước, trong, sau side effect; FFmpeg thật ở CP7-F-03 |
| M6: 100% output hoàn thành: phát được, 61–70 giây, tiếng Anh, đủ hook, thumbnail trong vùng hook, subtitle, cloud verified | hard gate CT-QC-001; cloud verified thuộc I và G | F-13, F-14, F-15, F-19 | pytest trên số đo và evidence của fake; byte thật ở CP7-F-01, CP7-F-02 |
| M6: đo audio kết hợp user nghe mẫu; review visual và karaoke | warning/score | F-12, F-13 | pytest; CP7-F-04, CP7-F-05 |
| M6: output filename và folder đúng policy trên desktop và Drive | thuộc I (path allocator, sanitize); F chỉ kiểm path nằm trong staging root | F-07 | pytest path; folder và Drive ở CP7-F-08 |
| M6: render success, QC pass, upload success, completion là bốn mốc riêng | `MilestoneState` | F-15 | pytest: bốn mốc độc lập |
| `docs/10-test-strategy.md` §12.6: năm preset có revision, resolve deterministic | CT-RND-001 | F-02 | pytest |
| M6 exit: tạo `R4 Video Alpha` theo luồng giám sát; `TST-E2E-001` đoạn render/QC; `TST-E2E-014` | stage F chạy độc lập qua activity | F-17..F-20 | pytest in-process; đầu-cuối sau CONV-F-02, CONV-F-05, CP7-F-08 |
| M6 exit: không output nào được đếm trước cloud verification | F không tạo completion hay ledger | F-15, F-19 | pytest; completion thuộc G (CT-ORC-008) |
| M6 exit: không local output bị xóa khi sync hoặc completion chưa đủ | F không có hàm xóa | F-01, F-15, F-18 | `ast`; fake lưu trữ đếm 0 lần xóa |
| M6 exit: F không tự đổi script, góc, media ngoài fallback plan | asset ngoài plan và `allowed_fallbacks` bị từ chối | F-05, F-10 | pytest |
| M6 exit: G06 phần TTS/timing/media và G07 phần output/QC có evidence | logic xác định có test; chất lượng cần đánh giá thật | F-22 | F-22 kiểm phủ test ID; ngưỡng ở CP7-F-01..CP7-F-07; không tuyên bố G06 hay G07 |
| M6 exit: user duyệt E-F và 5 preset mẫu | không tự quyết | — | pendingUserCheckpoint (§7) |
| G02 throughput 100 video trong 12 giờ | không thuộc slice | CP7-F-07 | không ngoại suy từ benchmark ngắn |

Mọi mục CT-RND-001..006, CT-QC-001, CT-QC-002 và acceptance §8 (1–7) của `docs/09-contracts/08-render-quality-contracts.md` có test trực tiếp, kiểm bằng F-22; ánh xạ acceptance: mục 1 → F-04; mục 2 → F-15, F-19; mục 3 → F-14; mục 4 → F-09, F-14; mục 5 → F-13; mục 6 → F-05, F-10; mục 7 → F-07, F-14.

## 7. Mục mở và mặc định (D8)

| Mục | Mặc định cho slice | Lý do | Trạng thái |
|---|---|---|---|
| ROADMAP-OPEN-007, QUALITY-OPEN-006, TEST-OPEN-005, TECH-OPEN-012: output profile (độ phân giải, tỷ lệ, fps, codec, bitrate, container, encoder, build FFmpeg) | `OutputProfileRevision` là input; thiếu → `INPUT_NOT_READY`; 1080x1920, 30fps, H.264, AAC chỉ là giá trị fixture test-only (GIẢ ĐỊNH) | roadmap §23 cấm default ẩn; `docs/10-test-strategy.md` dòng 837 yêu cầu parameter hóa | pendingUserCheckpoint |
| ROADMAP-OPEN-008, QUALITY-OPEN-007, TEST-OPEN-006: sai số word timing cho karaoke | `tolerance_ms` nằm trong quality policy; thiếu → gate `not_evaluated` kèm `INPUT_NOT_READY` và report không pass; bỏ hằng 50ms | dòng 833 test-strategy: không tự đặt ngưỡng | pendingUserCheckpoint |
| ROADMAP-OPEN-009: tên, style, thông số năm preset | F-02 chỉ cài cấu trúc `RenderPresetRevision` và bộ chứa; `is_complete` chỉ True khi có đúng 5 `preset_key` khác nhau; fixture `fixture-preset-1..5` test-only | CT-RND-001 chỉ khóa số lượng và tính versioned | pendingUserCheckpoint; duyệt 5 preset là exit gate M6 |
| Ngưỡng audio mix và visual continuity (hard hay warning) | warning/score đúng bảng CT-QC-001, không chặn; ngưỡng là input policy; thiếu → `not_evaluated`; nâng thành hard gate phải do user | roadmap §12 điểm còn mở | pendingUserCheckpoint |
| Khoảng `DURATION_RANGE` | 61–70 giây là `duration_range_ms` trong quality policy; hai đầu bao gồm (GIẢ ĐỊNH); kiểm biên 60999, 61000, 70000, 70001 ms | CT-QC-001 | quyết định D8; pendingUserCheckpoint nếu user muốn loại biên |
| TEST-OPEN-003: timeout, retry, backoff | F không tự retry; attempt thất bại hoặc `OUTCOME_UNKNOWN`, G quyết retry bằng attempt mới | CT-STATE-011, CT-RND-004 | pendingUserCheckpoint |
| ROADMAP-OPEN-010: retention và cleanup | F không xóa gì; mỗi attempt có output artifact riêng; cleanup do I | CT-STO-007, CT-STO-008, exit gate M6 | I quyết định |
| Cách burn-in subtitle và karaoke | tệp ASS với thẻ `\k` và bộ lọc `subtitles` (libass) của FFmpeg; F-09 chỉ sinh văn bản ASS thuần | không thêm thư viện; đổi màu theo mốc ms; `docs/05-technology-research.md` chọn FFmpeg filter graph; điều kiện: build có libass (TECH-OPEN-012) | quyết định D8; xác minh ở CP7-F-02; nếu build thiếu libass thì mở lại quyết định, chờ user |
| Vùng an toàn phụ đề, font, màu highlight, thumbnail overlay style, hook treatment | thuộc preset (typography, overlay, hook) là input; thiếu → `INPUT_NOT_READY` | CT-RND-001 | thuộc ROADMAP-OPEN-009 |
| Hình dạng `timeline.segments` và `hook_placement` | binding chỉ khai kiểu object; F-local GIẢ ĐỊNH: segment có `start_ms`, `end_ms`, `visual_asset_refs`, `claim_mode`, `disclosure_ref`; `hook_placement` theo fixture CP1 (`visual_hook_ref`, `audio_hook_ref`, `thumbnail_ref`, `hook_time_range`, `thumbnail_time_range`); thêm trường chỉ theo kiểu additive | binding `additive_optional_only` | quyết định D8; CONV-F-07 |
| Phát hiện `INFERENCE_DISCLOSURE_PRESENT` | mọi segment có `claim_mode` là `inference` hoặc `creative_hypothesis` phải có `disclosure_ref` và evidence của inspector xác nhận hiển thị; không có segment như vậy thì gate `not_applicable`; phát hiện trên byte thật (OCR, ASR) ở CP7-F-02 | CT-QC-001, roadmap §12 năng lực F mục 7 | quyết định D8; pendingUserCheckpoint |
| Phát hiện hook, thumbnail, phụ đề thực sự trong output | `OutputInspectorPort` trả evidence (khung hình, độ tương đồng, khoảng thời gian, mức âm thanh); ngưỡng tương đồng và mức âm thanh là input policy; đo thật ở CP7-F-01, CP7-F-02 | CT-QC-001 | pendingUserCheckpoint |
| Ngôn ngữ yêu cầu của `ENGLISH_OUTPUT_VALID` | `required_language` là input quality policy (fixture `en`); metadata tự khai `language` không đủ làm bằng chứng | CT-QC-002, INV-019 | quyết định D8 |
| Output path, filename, thư mục `YY-MM-DD` | do I cấp (CT-STO-011, kế hoạch I mục D8-I-07); F chỉ kiểm `output_path_ref` đã được cấp và nằm trong staging root, mang display title và hashtag nguyên bản; múi giờ là ROADMAP-OPEN-004 của I | CT-RND-006; I sở hữu sanitize | quyết định D8; CONV-F-12 |
| State machine | không có máy mới; receipt dùng `OperationState` và `transition_operation` (CT-STATE-011); stage run thuộc G | errata m6-ef #1; tài nguyên dùng chung | quyết định D8; CONV-F-06 |
| Persistence | UoW in-memory; PostgreSQL sau CONV-F-01 | migration là tài nguyên dùng chung | quyết định D8 |
| GPU slot | F giữ `LOCK-DESKTOP-GPU` qua `GpuLeasePort` và trả khi xong hoặc lỗi; không hằng số slot trong mã; thiếu slot → G đặt `WAITING_CAPABILITY` | `docs/parallel-delivery/ownership-and-locks.yaml`, DoR của capability F | quyết định D8; CP7-F-06 |
| Bố cục test | không `__init__.py`; tên tệp `test_fNN_*.py` | tránh trùng tên module | quyết định D8 |

### Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-007, QUALITY-OPEN-006, TEST-OPEN-005, TECH-OPEN-012: output profile, build FFmpeg, encoder
- ROADMAP-OPEN-008, QUALITY-OPEN-007, TEST-OPEN-006: sai số karaoke
- ROADMAP-OPEN-009: năm preset
- TEST-OPEN-003: timeout, retry, backoff
- Ngưỡng audio mix, visual continuity, hook, thumbnail
- Biên khoảng 61–70 giây
- libass và cách burn-in
- USER-CKPT-D9-D10: thư viện ở §8 và cách dựng lại runtime
- CP7 theo D5: các việc ở §9
- Exit gate M6: user duyệt E-F, 5 preset và `R4 Video Alpha`, G06 và G07 chỉ đóng sau đánh giá của user

Không mục nào ở trên được ghi là đã duyệt; slice chỉ dùng giá trị fixture trong test và trả `INPUT_NOT_READY` khi thiếu policy thật.

## 8. Thư viện (D10)

Slice F-01..F-22 không thêm thư viện; chỉ dùng stdlib (`dataclasses`, `enum`, `hashlib`, `json`, `re`, `unicodedata`, `datetime`, `typing`, `ast`, `uuid`, `pathlib` (chỉ `PurePath`, không I/O), `math`) và module controlplane ở §4. Không dùng `pydantic==2.13.5` hay `temporalio==1.32.0` trong F dù đã có trong lock (giữ domain thuần; đăng ký activity Temporal thuộc G). Kết luận D10: domain F không cần thư viện mới.

Đề xuất cho USER-CKPT-D9-D10 (trước CP-2b), chỉ cho adapter ở biên; phiên bản xác minh lại trên registry tại checkpoint, không dùng latest:

| Thư viện hoặc công cụ | Phiên bản cố định | Lý do |
|---|---|---|
| FFmpeg/ffprobe (binary qua adapter mỏng, mục 5.14) | build khóa theo TECH-OPEN-012 (chưa chốt), phải ghi cấu hình license LGPL hoặc GPL, có libass và encoder | render bằng filter graph, burn-in ASS, trích thumbnail, probe, đo `ebur128`, `volumedetect`, so khung hình bằng `ssim`; không thêm gói Python |
| `av` (PyAV) | `av==18.1.0` | chỉ thêm nếu CP7-F-02 chứng minh cần đọc frame và timestamp trong tiến trình để kiểm hook hoặc karaoke; BSD-3-Clause; release 18.1.0 ngày 12-08-2026 theo `docs/05-technology-research.md`; không thay FFmpeg CLI cho render |

Không đề xuất `ffmpeg-python` (bảo trì yếu), MoviePy (chỉ proof), Remotion (license, hoãn), `pyloudnorm` (FFmpeg đã đo), Pillow và OpenCV (chưa cần; thumbnail overlay làm bằng FFmpeg).

## 9. Việc cần tài nguyên thật (CP7)

Chỉ chạy sau khi user duyệt D5; tài khoản và credential chỉ qua secret broker của J, không mở, chép hay in bí mật.

- CP7-F-01: render thật từng preset trên RTX 4070 SUPER 12 GB bằng build FFmpeg khóa, đo độ phân giải, codec, thời lượng, phát được; chốt output profile (ROADMAP-OPEN-007).
- CP7-F-02: kiểm byte output thật: hook visual và audio, thumbnail trong vùng hook, subtitle burn-in, karaoke từng từ, disclosure; xác minh libass; user duyệt mẫu karaoke và visual (RM-RISK-006).
- CP7-F-03: lỗi thật: FFmpeg crash, partial file, timeout sau side effect, output corrupt, đầy ổ đĩa trên bộ media thật; reconcile.
- CP7-F-04: đo audio thật và user nghe mẫu; chốt ngưỡng `AUDIO_MIX_QUALITY`.
- CP7-F-05: user duyệt năm preset mẫu (ROADMAP-OPEN-009) và ngưỡng visual continuity.
- CP7-F-06: GPU contention giữa STT, TTS và render (cùng CP7-E-06) với `LOCK-DESKTOP-GPU` 2 slot.
- CP7-F-07: đo throughput render cho G02, không ngoại suy benchmark ngắn.
- CP7-F-08: luồng thật render → sync → verify → completion cùng I và G, 100% output hợp lệ (G04 Drive và OAuth qua broker của J).

## 10. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

| Mã | Tài nguyên dùng chung và yêu cầu | Slice F liên quan |
|---|---|---|
| CONV-F-01 | migration: bảng render_preset_revision, render_package, package_validation_report, render_attempt, quality_report, quality_gate_result, video_output, operation_receipt; append-only; unique theo `package_fingerprint`, `render_attempt_id`, `output_artifact_ref`; index theo `render_package_id`, `stage_run_id`; sau đó mở slice F tạo `src/render/persistence` | F-16 |
| CONV-F-02 | composition root (`src/main.py`, `src/controlplane/api/main.py`) và adapter thật: wiring command, worker, query của F; adapter FFmpeg, ffprobe, inspector, lease thật (LeaseManager) thay fake; gọi tiến trình bằng argv có cấu trúc, không ghép chuỗi | F-17..F-21 |
| CONV-F-03 | control API: route chạy và xem từng stage F (resolve, validate, render, inspect), xem QualityReport, tạo lại stage (`TST-E2E-014`); cần binding H↔G | F-20, F-21 |
| CONV-F-04 | UI shell (H, `ui/dist`, `App.tsx`): màn hình preset, render package, attempt, từng gate QC, xem video, bốn mốc render/QC/upload/completion, chạy lại một stage | F-15, F-21 |
| CONV-F-05 | workflow G: đăng ký activity resolve, validate, render, inspect; `WAITING_CAPABILITY` cho desktop và slot GPU; quyết retry và fallback; reconcile `OUTCOME_UNKNOWN`; commit completion chỉ sau khi I verify (CT-ORC-008) | F-18, F-19, F-20 |
| CONV-F-06 | state machine dùng chung và cấu hình J: xác nhận F dùng `OperationState` có sẵn và không cần máy riêng cho RenderAttempt, Preset; J đăng ký `RenderPresetRevision` và tool capability làm cấu hình (Preset/tool config ở M6) | F-02, F-11 |
| CONV-F-07 | registry binding: mở binding D→F hình dạng `timeline` và disclosure, E→F `language_validation_refs` và `mix_plan`, F→I CT-STO-006 `PersistVideoOutput`, I→F staging root và output path (CT-STO-004, CT-STO-011), J→F preset và tool config, F→G output ready (CT-RND-005); thêm F vào `modules` của binding cần | F-05, F-06, F-07, F-14, F-15 |
| CONV-F-08 | ownership registry và tài liệu: thêm `tests/integration/render/**` vào `PATH-SRC-RENDER`; sửa `docs/modules/capability-f-rendering.md` theo §2 (f)–(n); cập nhật `TASK-CAP-F-RENDERING` (R11–R13: tên test suite và `evidence_path` đang là `docs/delivery-evidence/task-cap-f-rendering/report.md`) trong `docs/parallel-delivery/acceptance-matrix.yaml` | F-17, F-22 |
| CONV-F-09 | catalog test và corpus: corpus video và audio ngắn, golden frame có tolerance, corpus karaoke dưới `tests/fixtures`; test ID mới cho từng quality gate nếu cần vào `docs/10-test-strategy.md` | F-22 |
| CONV-F-10 | outbox và event catalog: đăng ký `RenderCompleted`, `OutputQualityChecked` với publisher dùng chung | F-16 |
| CONV-F-11 | cấu hình J: preset và tool capability lấy từ ConfigRevision; adapter không nhận secret; không import `controlplane.config.router` | F-02, F-07 |
| CONV-F-12 | storage I: khai báo artifact output, thumbnail, report qua CT-STO-001 (`artifact_kind`, `retention_class`, `lineage_refs`); path allocator và sanitize filename (CT-STO-011); materialize đã verify (CT-STO-004); `PersistVideoOutput` CT-STO-006; F không tự sanitize | F-07, F-15, F-18, F-19 |
| CONV-F-13 | lockfile và runtime: thêm thư viện được duyệt ở USER-CKPT-D9-D10 và khóa build FFmpeg dưới dạng dependency_slice | F-18 |
| CONV-F-14 | phân hệ C, D, E: E cung cấp `language_validation_refs` và bằng chứng locale; D cung cấp `OutputMetadata` revision và disclosure; C cung cấp rendition refs; F không import các gói này | F-05, F-14 |

## 11. Thứ tự slice (DAG)

- Đợt 1: F-01
- Đợt 2 (song song): F-02, F-03, F-12
- Đợt 3 (song song): F-04, F-06, F-07, F-09, F-13, F-14
- Đợt 4 (song song): F-05, F-08, F-10
- Đợt 5: F-11
- Đợt 6 (song song): F-15, F-16
- Đợt 7 (song song): F-17, F-21
- Đợt 8: F-18
- Đợt 9: F-19
- Đợt 10: F-20
- Đợt 11: F-22

F-01 giữ `LOCK-SRC-RENDER` vì tạo cây gói; các slice khác giữ `LOCK-F-NN` và sở hữu tệp riêng nên chạy song song được; `dependsOn` chi tiết nằm trong `docs/implementation/f/slices.md`.

## 12. Ngoài phạm vi

Các nội dung nằm ngoài phạm vi của Phân hệ F:

- Chọn góc kể, script, ProductionPlan, OutputMetadata (thuộc D)
- Catalog media, hook, rendition candidate (thuộc C)
- Voice, word timing, audio bed, image safety (thuộc E)
- Điều phối, grant, retry, completion ledger, đếm completion (thuộc G)
- Giao diện người dùng UI shell (thuộc H)
- Lưu trữ, path allocator, sanitize filename, upload, verify, cleanup (thuộc I)
- Route AI, secret broker, quota, cấu hình hệ thống (thuộc J)
- Chọn asset ngoài refs và fallback đã cho; tự viết lại script hay góc kể
- Xác minh sự thật nội dung (CT-QC-002)
- Thiết kế nội dung chi tiết năm preset (ROADMAP-OPEN-009)
- Safety blur hay recolor cho clip và xuất bản nền tảng (roadmap §25)
