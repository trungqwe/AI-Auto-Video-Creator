# Kế hoạch triển khai Phân hệ E — Phân tích và xử lý media, âm thanh

- **Mã gói**: IMPL-PLAN-E
- **Ngày lập**: 19/10/2026
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`) và chỉ thị user duyệt Phần B ngày 18/10/2026 (D0–D10).
- **Trạng thái**: kế hoạch; kích hoạt sản xuất vẫn bị chặn (`PRODUCTION_ACTIVATION_BLOCKED`). Kế hoạch không cấp quyền sửa mã ngoài các slice trong `docs/implementation/e/slices.md`.
- **Danh sách slice**: `docs/implementation/e/slices.md` (E-01..E-20).

## 1. Nguồn chuẩn

- `docs/modules/capability-e-voice.md` (chỉ dùng sau khi áp dụng đính chính ở §2)
- `docs/11-roadmap.md` §10 (mục Năng lực E nền tảng), §12 (mục Năng lực E — Processing, voice và timing), §19 (G06, G07) và §23
- `docs/09-contracts/07-media-processing-contracts.md` (CT-PROC-001..008, CT-TTS-001, CT-SUB-001, CT-AUD-001, §10 acceptance)
- `docs/09-contracts/08-render-quality-contracts.md` (CT-RND-002, CT-RND-003, CT-QC-001 và yêu cầu bằng chứng ngôn ngữ)
- `docs/09-contracts/05-content-media-contracts.md` (CT-MED-003)
- `docs/09-contracts/11-configuration-security-contracts.md` (CT-AI-ROUTE-001, CT-AI-ROUTE-002)
- `docs/09-contracts/02-domain-events.md` (event của phân hệ E, CT-EVT-002, CT-EVT-003)
- `docs/09-contracts/03-workflow-and-execution.md` (CT-WF-003, CT-WF-006) và `docs/09-contracts/10-storage-contracts.md` (CT-STO-001), đọc qua binding
- `docs/09-contracts/12-state-machines.md` (CT-STATE-005, CT-STATE-006, CT-STATE-008, CT-STATE-011)
- `docs/10-test-strategy.md` (§14.2 bảng INV, §15 E2E, §30 mục mở TEST-OPEN-*)
- `docs/05-technology-research.md` (media, STT, TTS; TECH-POC-004, TECH-POC-005; TECH-OPEN-004, TECH-OPEN-012)
- `docs/parallel-delivery/bindings/README.md` và các binding ở §5
- `docs/parallel-delivery/errata/m6-ef.md`
- `docs/parallel-delivery/ownership-and-locks.yaml` (`modules.E`, `PATH-SRC-VOICE`, `LOCK-SRC-VOICE`, `LOCK-CONTRACT-MEDIA-PROCESSING`, `PATH-IMPLEMENTATION-PLANS`)
- Kế hoạch tham chiếu bố cục: `docs/implementation/c/plan.md`, `docs/implementation/d/plan.md`
- Mã đã có, chỉ đọc: `src/controlplane/domain/interfaces/uow.py` (`IUnitOfWork`), `src/controlplane/domain/interfaces/outbox.py` (`IOutboxWriter`), `src/controlplane/domain/events/contracts.py` (`DomainEvent`, `ensure_safe_event_payload`), `src/controlplane/domain/concurrency.py` (`RevisionConflictError`), `src/controlplane/domain/common/contracts.py` (`ProblemDetail`), `src/controlplane/domain/orchestration/__init__.py` (`ExecutionGrant`), `src/controlplane/application/idempotency/canonicalization.py` (`request_hash`)

Thứ tự ưu tiên khi mâu thuẫn: `docs/09-contracts` → binding và fixture CP1 → `docs/parallel-delivery/errata/m6-ef.md` → `docs/modules/capability-e-voice.md`. Ba tệp `docs/parallel-delivery/M6-EF-contract-freeze.md`, `M6-EF-execution-package.md`, `M6-EF-test-plan.md` bị hỏng dấu tiếng Việt: không dùng làm nguồn, oracle hay bằng chứng và không chép.

## 2. Đính chính áp dụng

Errata CP1 (`docs/parallel-delivery/errata/m6-ef.md`):

- (a) Không có state machine riêng cho VoiceTrack và WordTiming (errata #1): dùng CT-STATE-005 (Rendition), CT-STATE-006 (image safety), CT-STATE-008 (stage) và CT-STATE-011 (receipt). Timing hết hiệu lực theo CT-SUB-001 bất biến 3. Slice chỉ khai báo giá trị enum đọc, không có hàm chuyển trạng thái.
- (b) Mã invariant theo catalog `docs/10-test-strategy.md` §14.2 (errata #2): INV-007 là timing gắn exact script/voice (`TST-MEDIA-INV-007`), INV-008 là render package chỉ nhận artifact đã verify (`TST-INT-INV-008`), INV-012 là canary secret (`TST-SEC-INV-012`), INV-019 là bằng chứng tiếng Anh theo exact revision (`TST-QC-INV-019`).
- (c) Thumbnail cố định 0–3 giây là quy tắc tự đặt (errata #3); thumbnail thuộc D, C và F, không thuộc E.
- (d) Chỉ dùng test ID có trong catalog (errata #4): `TST-MEDIA-INV-007`, `TST-INT-INV-008`, `TST-QC-INV-019`, `TST-SEC-INV-012`, `TST-E2E-001`, `TST-E2E-011`, `TST-E2E-014`. Không dùng các tiền tố `TST-MED-`, `TST-VOI-`, `TST-RND-`, `TST-EF-`.
- (e) Bằng chứng theo D4 tại `docs/delivery-evidence/<task-id viết thường>/report.md`; không ghi vào thư mục evidence đã nghiệm thu dưới `docs/milestones`.

Đính chính bổ sung cho `docs/modules/capability-e-voice.md` (đối chiếu `docs/09-contracts`; sửa tài liệu qua CONV-E-08):

- (f) §5: INV-007 không phải mốc từ tăng đơn điệu, INV-008 không phải độ dài audio khớp 61–70 giây, INV-019 không phải phủ đủ từ kịch bản. Tăng đơn điệu, không âm và nằm trong thời lượng voice là CT-SUB-001 bất biến 1 cùng ràng buộc `monotonic_word_timings` của binding; phủ đủ từ là test bắt buộc của roadmap §12, không có mã INV.
- (g) §4 mục 2: 61–70 giây là `DURATION_RANGE` của video (CT-QC-001), kiểm ở F trên video thật. E ghi `actual_duration_ms` và có validator so với khoảng do policy truyền vào, không có hằng trong mã.
- (h) §4 mục 3: sai số ±100ms và tổng thời lượng timing khớp độ dài audio là hằng tự đặt. CT-SUB-001 chỉ yêu cầu timing nằm trong thời lượng voice; sai số là ROADMAP-OPEN-008/TEST-OPEN-006, chưa chốt.
- (i) §4 mục 4: EBU R128 từ -14 đến -16 LUFS là hằng tự đặt và lẫn tên chuẩn. Mục tiêu loudness và mix lấy từ preset audio policy (CT-AUD-001); ngưỡng audio là mục mở của roadmap §12.
- (j) §2: CT-AUD-001 là `PrepareAudioBed`, không phải cổng gọi TTS. Gọi TTS qua route của J (CT-AI-ROUTE-001, binding `j-provider-route`) để thực hiện CT-TTS-001. `VoiceTrackRequest` chỉ mang `script_version_id`, `script_fingerprint` và `pronunciation_hints`, không mang văn bản; chưa có binding đọc văn bản script từ D nên E dùng port E-local và fake (CONV-E-07).
- (k) §1, §2: tài liệu chỉ nói voice và timing; ownership (`modules.E`) và `docs/09-contracts/07-media-processing-contracts.md` §1 còn giao cho E probe, analyze, image safety, transform, normalize và audio bed (CT-PROC-001..008, CT-AUD-001). `ProcessedMedia` gồm cả ảnh và clip đã xử lý; việc lọc tạp âm không có trong contract.
- (l) §6: thiếu `tests/integration/voice/**` so với D1 (CONV-E-08).
- (m) §7: lệnh `python -m unittest tests/unit/voice/test_word_timing_alignment.py -k test_monotonic_timestamps` không dùng; mỗi slice có lệnh pytest riêng.
- (n) §8: hủy VoiceTrack và WordTiming lỗi, đổi tốc độ hoặc engine dự phòng trái nguyên tắc, trừ đúng một ngoại lệ (E-16-FIX2, quyết định của user 31/10/2026 cho RG-09): khi giọng lần đầu lệch khoảng thời lượng, một lần đọc lại trong cùng CreateVoiceTrack với hệ số tốc độ kẹp theo khoá profile voice.speed_fit (0,85-1,15); mọi lượt đều là invocation được ghi lại; output bất biến, lỗi ghi thành attempt thất bại và không xóa lịch sử; retry và fallback provider vẫn do G và J quyết; engine dự phòng chỉ theo `fallback_order` của J (CT-AI-ROUTE-002); E không cleanup (CT-PROC-008); operation đã terminal không mở lại (CT-STATE-011).
- (o) §3 mục 3 và §7: kiểm không rò rỉ bộ nhớ với thư viện thật là việc CP7; slice dùng WAV sinh bằng `wave` của stdlib và fake.

## 3. Năng lực và aggregate

| Năng lực roadmap §10 (E nền tảng) và §12 (E) | Contract | Slice |
| --- | --- | --- |
| Job xử lý chung; output chỉ ready sau khi I verify; phân loại retention | CT-PROC-001, CT-PROC-002, CT-PROC-008 | E-02 |
| Probe media thật, không tin extension/MIME; technical metadata và corruption | CT-PROC-003 | E-03 |
| Phân tích media có version, model mới không ghi đè | CT-PROC-004 | E-04 |
| Image safety assessment (chỉ ảnh) | CT-PROC-005 | E-05 |
| Transform ảnh nhạy cảm cơ bản, giữ ảnh gốc, lineage | CT-PROC-006 | E-06 |
| Crop, resize, normalize, transcode, extract-frame có lineage; clip chỉ xử lý kỹ thuật | CT-PROC-007 | E-07 |
| TTS gắn exact script fingerprint | CT-TTS-001 | E-08, E-14, E-16 |
| Word timing gắn exact script/voice hash, confidence và gap report | CT-SUB-001 | E-09, E-10, E-16 |
| Invalidation downstream khi script, voice hoặc artifact revision đổi | CT-SUB-001 bất biến 2–3 | E-11 |
| Bằng chứng ngôn ngữ gắn exact revision cho F | CT-RND-002 | E-12 |
| Music/SFX preparation, loudness, mix constraints | CT-AUD-001 | E-13 |
| Lưu bất biến, unit of work, outbox, event của E | CT-EVT-002, CT-EVT-003 | E-15 |
| Command xử lý media, activity cho G, truy vết, ma trận test | CT-WF-003, CT-WF-006 | E-17, E-18, E-19, E-20 |

Aggregate E sở hữu (`modules.E` trong `docs/parallel-delivery/ownership-and-locks.yaml`): `ProcessedMedia`, `VoiceTrack`, `WordTiming`. Bản ghi nội bộ của E (tên là GIẢ ĐỊNH, chưa có trong contract): ProbeReport, AnalysisResult, ImageSafetyAssessment, TtsInvocationRecord, TimingValidationReport, LanguageEvidence, AudioBedResult. E không sở hữu: MediaAsset, MediaAnalysis đã lưu, Hook, MediaUsage (C); ScriptVersion, ProductionPlan (D); RenderPackage, QualityReport, VideoOutput (F); VideoJob, ExecutionGrant, CompletionLedger (G); ArtifactVersion, ArtifactLocation, cleanup (I); route, secret, quota (J). E không ghi bảng của phân hệ khác, không nhận secret và không tự cleanup.

## 4. Vị trí mã theo D1

| Đường dẫn | Nội dung |
| --- | --- |
| `src/voice/domain/` | value object, validator, fingerprint thuần |
| `src/voice/application/` | command handler, pipeline |
| `src/voice/ports/` | Protocol: nội dung script, probe, công cụ media, TTS, aligner, repository |
| `src/voice/adapters/` | fake và in-memory |
| `src/voice/worker/` | activity handler cho G |
| `src/voice/projections/` | query truy vết read-only |
| `tests/unit/voice/` | unit |
| `tests/integration/voice/` | tích hợp in-process |

Quy tắc: import root `src/` (`import voice...`), cấm tiền tố `src.`; không tạo `src/voice/storage`, `src/voice/orchestration`, `src/voice/ui`, `src/voice/config` và không tạo `src/storage`, `src/orchestration`, `src/ui`; không tạo persistence PostgreSQL và adapter FFmpeg, TTS, aligner thật cho tới khi CONV-E-01 và CONV-E-02 có migration và wiring. Test không có `__init__.py`; tên tệp `test_eNN_*.py` duy nhất. Không import `creative`, `render`, `catalog` hay gói của phân hệ khác; phối hợp chỉ qua binding, port E-local và fake.

| Module controlplane tái dùng (chỉ import) | Dùng cho |
| --- | --- |
| `controlplane.domain.interfaces.uow.IUnitOfWork` | UoW in-memory (E-15) |
| `controlplane.domain.interfaces.outbox.IOutboxWriter` | outbox dedup theo `deduplication_id` (E-15) |
| `controlplane.domain.events.contracts.DomainEvent`, `ensure_safe_event_payload` | event của E (E-15) |
| `controlplane.domain.concurrency.RevisionConflictError` | expected revision (E-15) |
| `controlplane.domain.common.contracts.ProblemDetail` | lỗi có cấu trúc (E-16, E-17, E-18) |
| `controlplane.application.idempotency.canonicalization.request_hash` | fingerprint và idempotency (E-02, E-07, E-12, E-16) |
| `controlplane.domain.orchestration.ExecutionGrant` | grant của G (E-18) |

E chỉ import, không sửa, không dựng bản trùng; không import `controlplane.config.router` và `controlplane.config.adapter` của J (CONV-E-11).

## 5. Contract dùng và cung cấp

| Contract | Vai trò E | Binding và fixture |
| --- | --- | --- |
| CT-TTS-001 `VoiceTrackRequest`/`VoiceTrackResult` | cung cấp (producer); D là input provider | `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`; `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json` |
| CT-SUB-001 `WordTiming` | cung cấp; F là consumer | cùng binding và fixture trên |
| CT-AI-ROUTE-001 `ProviderRouteRequest`/`ProviderRouteDecision` | consumer, không nhận secret | `docs/parallel-delivery/bindings/j-provider-route.json`; `tests/fixtures/contracts/j-provider-route/payloads.json` |
| CT-STO-001 `DeclareArtifactVersion` | consumer: giữ ref và `content_sha256` do I cấp | `docs/parallel-delivery/bindings/i-artifact-version.json`; `tests/fixtures/contracts/i-artifact-version/payloads.json` |
| CT-RND-002/003 `RenderPackage` | input provider (`voice_artifact_ref`, `word_timing_ref`, `language_validation_refs`, `mix_plan`) | `docs/parallel-delivery/bindings/f-render-package.json`; `tests/fixtures/contracts/f-render-package/payloads.json` |
| CT-EVT-002/003 `DomainEvent` | cung cấp 4 event của E | `docs/parallel-delivery/bindings/domain-event-envelope.json`; `tests/fixtures/contracts/domain-event-envelope/payloads.json` |
| CT-WF-003/006 `ActivityRequest`/`ActivityResult` | dùng request, cung cấp result | `docs/parallel-delivery/bindings/g-activity-execution.json`; `tests/fixtures/contracts/g-activity-execution/payloads.json` |
| CT-PROC-001..008, CT-AUD-001 | E sở hữu | chưa có binding riêng; slice bám văn bản `docs/09-contracts/07-media-processing-contracts.md` |

1. Seam chưa có binding, xử lý fail-closed: D→E đọc văn bản script theo `script_version_id` (CT-TTS-001), E→C CT-MED-003 `RegisterRendition`, E→F bằng chứng ngôn ngữ (CT-RND-002 `language_validation_refs`), G→E CT-PROC-001/002, E↔F CT-AUD-001 `PrepareAudioBed`, và `ai_role` cho TTS (fixture `j-provider-route` chỉ có `script_generation`). Slice dùng port E-local và fake, không wiring thật; mở binding qua CONV-E-07.
2. Event E phát qua transactional outbox, at-least-once, consumer tự dedup: `ImageSafetyAssessed`, `MediaProcessingCompleted`, `VoiceReady`, `WordTimingReady` (`docs/09-contracts/02-domain-events.md`); payload chỉ mang ref, hash, revision; không chứa byte âm thanh, secret hay văn bản script dài. Contract không có event vô hiệu hóa timing; E chỉ tính kết quả invalidation (E-11), event mới qua CONV-E-10.
3. Tương thích `additive_optional_only`; consumer bỏ qua trường lạ; binding version không hỗ trợ thì fail-closed theo CT-CMN-012; đổi phá vỡ phải tăng major binding qua MIGRATE.

## 6. Ánh xạ exit gate roadmap sang slice

Bảng nêu exit gate và test bắt buộc của roadmap §10 (M4, mục E nền tảng) và §12 (M6) mà phân hệ E phục vụ. Gate không thuộc E ghi rõ để không bỏ sót.

| Exit gate / test bắt buộc | Vai trò E | Slice | Cách kiểm |
| --- | --- | --- | --- |
| M4: render tương lai chỉ lấy artifact đã verify; `TST-INT-INV-008` phần E | output chỉ ready và chỉ phát event sau khi I verify | E-02, E-15 | pytest: `succeeded` chưa có verify evidence thì không ready; builder event từ chối `artifact_verified=False` |
| M4: UI phân biệt original, processed, uncertain, failed, unavailable | cung cấp safety outcome và lineage; màn hình thuộc H | E-05, E-06 | pytest: sáu outcome CT-PROC-005 và lineage; màn hình ở CONV-E-04 |
| M4: không location verified thiếu integrity; không cleanup khi chưa cloud verified | thuộc I; E chỉ gắn retention intent | E-02 | pytest: `retention_intent`; module không có hàm cleanup |
| M4: G04 Drive/OAuth/integrity thật | không thuộc E | CP7 | không dùng mock để tuyên bố PASS |
| M4 test: Sensitive Image Set; `TST-E2E-011` | phân loại, dùng được theo CT-PROC-005, lỗi không ghi thành safe hay processed | E-05, E-06, E-17 | pytest với bộ ảnh giả định sẵn (safe, trẻ em, máu me, vũ khí, uncertain, detector/transform failure, unreadable); detector thật ở CP7-E-03 |
| M4 test: clip không bị safety transform | từ chối safety và transform cho clip; chỉ xử lý kỹ thuật | E-05, E-06, E-07, E-17 | pytest: clip với blur hoặc recolor bị từ chối |
| M4 test: probe thật, không tin extension/MIME; corruption | probe report, mâu thuẫn khai báo | E-03, E-17 | pytest với JSON probe giả; ffprobe thật ở CP7-E-04 |
| M4 test: original tách rendition; reusable khác temporary | rendition mới có lineage; phân loại retention | E-02, E-07 | pytest: output ref khác input ref |
| M4/M6: `INV-012` (`TST-SEC-INV-012`) | route TTS không nhận secret; lỗi được redact | E-14 | pytest với canary secret trong lỗi của fake |
| M6: `INV-007` (`TST-MEDIA-INV-007`), exact binding và invalidation | timing gắn script/voice; đổi thì timing cũ bị từ chối | E-11, E-16 | pytest: đổi script hoặc voice thì `check_timing_binding` invalid và command timing cũ bị từ chối |
| M6: word timing monotonic, coverage, confidence và gap | validator và báo cáo | E-09, E-10 | pytest: mọi case fixture `WordTiming`; từ thiếu, đảo thứ tự, vượt thời lượng |
| M6: TTS voice gắn exact script fingerprint | request/result đúng binding, fingerprint khớp | E-08, E-14, E-16 | pytest: fingerprint lệch thì 0 lượt gọi TTS |
| M6: music/SFX, loudness, mix; đo âm thanh kết hợp user nghe mẫu | validator loudness theo policy; không đổi bài ngoài fallback | E-13 | pytest; đo và nghe thật ở CP7-E-05 |
| M6: `INV-008` render package phần E; thiếu voice hoặc timing thì fail sớm | cung cấp ref đã verify và kiểm binding cho F | E-11, E-15 | pytest như hai dòng trên; validator render ở F |
| M6: FFmpeg crash, partial file, timeout sau side effect, output corrupt | outcome `failed` hoặc `outcome_unknown` theo CT-STATE-011 | E-17 | pytest tiêm lỗi trước, trong và sau side effect; FFmpeg thật ở CP7-E-04 |
| M6: `INV-019` (`TST-QC-INV-019`) phần E | bằng chứng gắn exact script, voice, subtitle | E-12 | pytest: revision lệch thì evidence bị từ chối |
| M6: 61–70 giây, tiếng Anh, hook, thumbnail, subtitle đạt trên 100% output | thuộc F (CT-QC-001); E ghi `actual_duration_ms` | E-08 | pytest: validator so với khoảng policy |
| M6: R4 Video Alpha theo luồng giám sát; `TST-E2E-001` đoạn voice/timing; `TST-E2E-014` | stage E chạy độc lập qua activity | E-16, E-17, E-18 | pytest in-process; luồng đầu-cuối sau CONV-E-02, CONV-E-05 |
| M6: G06 phần TTS/timing/media, G07 phần output/QC | logic xác định có test; chất lượng cần đánh giá thật | E-20 | E-20 kiểm phủ test ID; ngưỡng chất lượng ở CP7-E-01..CP7-E-05; không tuyên bố G06 hay G07 |
| M6: `INV-009`, `INV-010`, `INV-011` | thuộc F, G, I; E không đếm completion hay cleanup | — | ghi nhận, không có slice E |
| M6: user duyệt E-F và 5 preset | không tự quyết | — | pendingUserCheckpoint (§7) |

Mọi mục CT-PROC-001..008, CT-TTS-001, CT-SUB-001, CT-AUD-001 và acceptance §10 của `docs/09-contracts/07-media-processing-contracts.md` có test trực tiếp, kiểm bằng E-20.

## 7. Mục mở và mặc định (D8)

| Mục | Mặc định cho slice | Lý do | Trạng thái |
| --- | --- | --- | --- |
| ROADMAP-OPEN-008, TEST-OPEN-006 sai số word timing | `tolerance` là input policy; thiếu → `INPUT_NOT_READY`; hằng ±100ms của tài liệu cũ bị bỏ | roadmap §23 cấm default ẩn | pendingUserCheckpoint |
| ROADMAP-OPEN-007, TEST-OPEN-005, TECH-OPEN-012 output profile, build FFmpeg | `expected_output_profile` là input của `ProcessingRequest`; E không định nghĩa profile | CT-PROC-001 | pendingUserCheckpoint |
| Ngưỡng audio (loudness, peak, mix) | lấy từ preset audio policy; thiếu → `INPUT_NOT_READY`; hằng -14..-16 LUFS bị bỏ | CT-AUD-001, roadmap §12 mục mở | pendingUserCheckpoint (cùng ROADMAP-OPEN-009) |
| TECH-OPEN-004 TTS primary/fallback | route do J quyết; slice dùng fake; không chọn engine | docs/05 yêu cầu benchmark trước | pendingUserCheckpoint, CP7-E-01 |
| Công cụ aligner (TECH-POC-005) | chỉ định nghĩa `AlignerPort` và fake; chưa chọn công cụ | docs/05 chưa chốt | pendingUserCheckpoint, CP7-E-02 |
| TEST-OPEN-003 timeout, retry, backoff | số lần thử và hạn là input policy; E không tự retry provider, G quyết; lượt đọc lại với tốc độ khớp (E-16-FIX2, voice.speed_fit) không phải retry provider | roadmap §23 | pendingUserCheckpoint |
| Policy image safety (category, ngưỡng confidence, hành động transform theo category) | policy revision là input; thiếu → `INPUT_NOT_READY`; không hằng blur cho vũ khí | CT-PROC-006 | pendingUserCheckpoint, CP7-E-03; ROADMAP-OPEN-006 cho mẫu đánh giá |
| ROADMAP-OPEN-010 retention | E chỉ gắn intent theo CT-PROC-008: rendition và analysis → reusable; voice, word timing, mix tạm → per-video; frame, log, report debug → diagnostic | I quyết định cleanup | quyết định D8 của kế hoạch; retention thật thuộc I |
| Khoảng thời lượng voice | 61–70 giây là input policy; E ghi `actual_duration_ms`, F kiểm trên video thật | CT-QC-001 | quyết định D8 của kế hoạch |
| D8 Khớp tốc độ voice | khoá voice.speed_fit (min_scale, max_scale, duration_slope) của profile; khi giọng lần đầu lệch khoảng thì đọc lại đúng một lần với hệ số tốc độ kẹp 0,85-1,15, tính từ trung điểm khoảng và độ dốc đo 0,56; không có lượt ba; lệch lần hai thì VoiceDurationRejected | quyết định của user 31/10/2026 (RG-09, CLOSURE_NOTE CP7) | quyết định D8 của kế hoạch |
| Quy tắc chồng lấn word timing | từ sau không bắt đầu sớm hơn từ trước kết thúc; chồng lấn là `constraint_violation` (chặt hơn binding); GIẢ ĐỊNH, nới khi TEST-OPEN-006 chốt | capability E §5 (không chồng chéo) | quyết định D8; pendingUserCheckpoint khi nới |
| Tokenization để phủ từ | `tokenization_policy_revision` là input; fixture dùng tách theo khoảng trắng, chuẩn hóa NFC, casefold, bỏ dấu câu hai đầu (GIẢ ĐỊNH, tiếng Anh) | CT-SUB-001 yêu cầu language/tokenization policy | quyết định D8 |
| Nội dung script cho TTS | port E-local `ScriptTextPort` trả văn bản kèm fingerprint do D tính; E không tự tính lại fingerprint | binding chỉ có ID và fingerprint | quyết định D8; CONV-E-07 |
| Bằng chứng ngôn ngữ | E ghi locale do provider báo, hash phụ đề và revision; E không tự tuyên bố tiếng Anh hợp lệ, F kiểm `ENGLISH_OUTPUT_VALID` | CT-RND-002 | quyết định D8 |
| `ai_role` cho TTS | tên `voice_synthesis` trong test là GIẢ ĐỊNH; vai trò thật do J đăng ký | binding để `ai_role` là string | CONV-E-07, CONV-E-11 |
| State machine | không có máy VoiceTrack, WordTiming; không sửa `src/controlplane/domain/statemachine` | errata m6-ef #1 | quyết định D8; CONV-E-06 |
| Persistence | UoW in-memory; PostgreSQL sau CONV-E-01 | migration là tài nguyên dùng chung | quyết định D8 |
| Bố cục test | không `__init__.py`; tên tệp `test_eNN_*.py` | tránh trùng tên module | quyết định D8 |

### Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-007/TEST-OPEN-005, ROADMAP-OPEN-008/TEST-OPEN-006, ROADMAP-OPEN-009 (preset và ngưỡng audio), TEST-OPEN-003, ROADMAP-OPEN-006 (mẫu đánh giá).
- TTS primary/fallback (TECH-OPEN-004), công cụ aligner, policy image safety.
- USER-CKPT-D9-D10: thư viện ở §8 và cách dựng lại runtime.
- CP7 theo D5: các việc ở §9.
- Exit gate M6: user duyệt E-F, 5 preset và `R4 Video Alpha`; G06 phần TTS/timing/media chỉ đóng sau đánh giá của user.

Không mục nào ở trên được ghi là đã duyệt; slice chỉ dùng giá trị fixture trong test và trả `INPUT_NOT_READY` khi thiếu policy thật.

## 8. Thư viện (D10)

Slice E-01..E-20 không thêm thư viện; chỉ dùng stdlib (`dataclasses`, `enum`, `hashlib`, `json`, `re`, `unicodedata`, `datetime`, `typing`, `ast`, `wave`, `struct`, `math`) và module controlplane ở §4. Không dùng `pydantic==2.13.5` hay `temporalio==1.32.0` trong E dù đã có trong lock (giữ domain thuần; đăng ký activity Temporal thuộc G). Kết luận D10: domain E không cần thư viện mới.

Đề xuất cho USER-CKPT-D9-D10 (trước CP-2b), chỉ cho adapter ở biên. Phiên bản lấy từ `docs/05-technology-research.md` và phải xác minh lại trên registry tại checkpoint; không dùng `latest`:

| Thư viện hoặc công cụ | Phiên bản cố định | Lý do |
| --- | --- | --- |
| FFmpeg/ffprobe (binary, qua adapter mỏng, mục 5.14) | build khóa theo TECH-OPEN-012 (chưa chốt) | probe, normalize, transcode, đo loudness bằng bộ lọc `ebur128`; không thêm gói Python |
| `av` (PyAV) | `av==18.1.0` | đọc frame và timestamp trong tiến trình khi cần; chỉ thêm nếu CP7-E-04 chứng minh cần; BSD-3-Clause |
| `faster-whisper` | `faster-whisper==1.2.1` | ứng viên transcript và timestamp chi phí thấp; MIT |
| `whisperx` | `whisperx==3.8.6` | ứng viên forced alignment từng từ; BSD-2-Clause; thêm dependency, model và VRAM |
| OpenCV | phiên bản xác minh tại checkpoint (GIẢ ĐỊNH: tên gói và wheel chưa đối chiếu với release 5.0.0 trong tài liệu) | detector, mask, blur, đổi màu cho ảnh nhạy cảm; Apache-2.0; model detector cần cấp phép riêng |

Chọn aligner bằng TECH-POC-005 (faster-whisper, WhisperX, whisper.cpp); whisper.cpp là binary ngoài dùng làm fallback, không phải gói Python. Chưa đề xuất thư viện TTS: TECH-POC-004 (Gemini TTS, ElevenLabs, Piper, Kokoro) phải benchmark trước, TTS gọi qua route của J. Không đề xuất `pyloudnorm` vì FFmpeg đã đo loudness; không đề xuất `ffmpeg-python`, Coqui TTS, MeloTTS (`docs/05-technology-research.md`, bảng không ưu tiên).

## 9. Việc cần tài nguyên thật (CP7)

Chỉ chạy sau khi user duyệt D5; tài khoản và credential chỉ qua secret broker của J, không mở, chép hay in bí mật.

- CP7-E-01: benchmark TTS mù (TECH-POC-004) trên 20 đoạn thoại, năm phong cách, nhiều lần tạo lại; đo tự nhiên, phát âm tên riêng, cảm xúc, ổn định, tốc độ, VRAM, chi phí và license voice/model; chọn primary và fallback.
- CP7-E-02: benchmark aligner (TECH-POC-005): sai timestamp và WER giữa faster-whisper, WhisperX, whisper.cpp với nhạc/SFX nhiều mức; user chốt sai số word timing (ROADMAP-OPEN-008) và duyệt mẫu karaoke (RM-RISK-006).
- CP7-E-03: Sensitive Image Set thật (safe, trẻ em, máu me, vũ khí, uncertain, detector/transform failure, unreadable); detector và transform thật; user chấm mẫu (ROADMAP-OPEN-006); không tuyên bố tỷ lệ phát hiện khi chưa đo.
- CP7-E-04: FFmpeg/ffprobe build khóa (TECH-OPEN-012) với corpus media thật gồm tệp hỏng, tệp cắt dở, crash, timeout sau side effect; kiểm rò rỉ bộ nhớ theo DoR của `docs/modules/capability-e-voice.md` §3.
- CP7-E-05: đo loudness thật và user nghe mẫu (roadmap §12); chốt ngưỡng audio.
- CP7-E-06: GPU contention trên RTX 4070 SUPER 12 GB giữa STT, TTS local và render.
- CP7-E-07: cung cấp `actual_duration_ms` thật để hiệu chỉnh tốc độ đọc của D (CP7-D-04).

## 10. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

| Mã | Tài nguyên dùng chung | Yêu cầu | Slice E liên quan |
| --- | --- | --- | --- |
| CONV-E-01 | migration | bảng processed_media, image_safety_assessment, voice_track, word_timing, timing_validation_report, tts_invocation_record, language_evidence, audio_bed_result, probe_report, analysis_result và receipt; append-only; unique theo `voice_hash` và `timing_artifact_ref`; index theo `script_version_id`, `stage_run_id`; sau đó mở slice E tạo `src/voice/persistence` | E-15 |
| CONV-E-02 | composition root (`src/main.py`, `src/controlplane/api/main.py`) và adapter thật | wiring command, worker, query của E; adapter FFmpeg/ffprobe, aligner, TTS thay fake; gọi tiến trình an toàn, không ghép chuỗi lệnh | E-16, E-17, E-18, E-19 |
| CONV-E-03 | control API | route chạy và xem từng stage E (TST-E2E-014), query truy vết; cần binding H↔G | E-18, E-19 |
| CONV-E-04 | UI shell (H, `ui/dist`, `App.tsx`) | xem voice, word timing, báo cáo, safety outcome (original, processed, uncertain, failed, unavailable); chạy lại một stage | E-05, E-06, E-19 |
| CONV-E-05 | workflow G | đăng ký activity xử lý media, tạo voice, tạo timing, chuẩn bị audio bed; `WAITING_CAPABILITY` cho desktop; quyết retry và fallback; kích hoạt tạo lại timing khi script hoặc voice đổi | E-11, E-16, E-18 |
| CONV-E-06 | state machine dùng chung | xác nhận E không cần máy riêng cho VoiceTrack, WordTiming; đồ thị CT-STATE-005/006 do CONV-C-07 | E-02, E-05 |
| CONV-E-07 | registry binding | mở binding D→E đọc văn bản script, E→C CT-MED-003, E→F `language_validation_refs`, G→E CT-PROC-001/002, E↔F CT-AUD-001; thêm `ai_role` TTS vào fixture `j-provider-route` | E-02, E-08, E-12, E-13, E-14 |
| CONV-E-08 | ownership registry và tài liệu | thêm `tests/integration/voice/**` vào `PATH-SRC-VOICE`; sửa `docs/modules/capability-e-voice.md` theo §2 (f)–(o); cập nhật `TASK-CAP-E-VOICE` trong `docs/parallel-delivery/acceptance-matrix.yaml` (tên test suite, `contract_refs` đang rỗng) | E-16, E-17 |
| CONV-E-09 | catalog test và corpus | Sensitive Image Set, corpus word timing, tập đoạn thoại TTS có version dưới `tests/fixtures`; test ID mới cho phủ từ và loudness nếu cần vào `docs/10-test-strategy.md` | E-20 |
| CONV-E-10 | outbox và event catalog | đăng ký 4 event của E với publisher dùng chung; xem xét event vô hiệu hóa timing | E-15 |
| CONV-E-11 | route provider J | adapter từ `VoiceRoutePort` và `TtsEnginePort` sang resolver CT-AI-ROUTE-001 và `controlplane.config.router.ProviderRouter` qua secret broker; đăng ký `ai_role` TTS | E-14 |
| CONV-E-12 | storage I | khai báo artifact của E qua CT-STO-001 (`artifact_kind`, `retention_class`, `lineage_refs`); ánh xạ retention intent của E sang chính sách cleanup; xác nhận verify trước khi E đánh dấu ready | E-02, E-15 |
| CONV-E-13 | lockfile và runtime | thêm thư viện được duyệt ở USER-CKPT-D9-D10 và khóa build FFmpeg dưới dạng dependency_slice | E-17 |
| CONV-E-14 | phân hệ F | F gọi kiểm binding timing và language evidence khi resolve render package; F kiểm `ENGLISH_OUTPUT_VALID` và 61–70 giây | E-11, E-12 |

## 11. Thứ tự slice (DAG)

- Đợt 1: E-01.
- Đợt 2 (song song): E-02, E-08, E-09.
- Đợt 3 (song song): E-03, E-04, E-05, E-07, E-10, E-11, E-12, E-13, E-14.
- Đợt 4 (song song): E-06, E-15.
- Đợt 5 (song song): E-16, E-17, E-19.
- Đợt 6: E-18.
- Đợt 7: E-20.

E-01 giữ `LOCK-SRC-VOICE` vì tạo cây gói; các slice khác giữ `LOCK-<taskId>` và sở hữu tệp riêng nên chạy song song được. `dependsOn` chi tiết nằm trong `docs/implementation/e/slices.md`.

## 12. Ngoài phạm vi

Chọn góc kể và script (D), catalog media và hook (C), render, QC, thời lượng video thật và đếm completion (F, G), UI (H), lưu trữ, upload, verify và cleanup (I), route, secret, quota (J); xử lý nhạy cảm trên clip (roadmap §10 cấm); thay script hoặc chọn media ngoài refs và fallback đã cho (`docs/09-contracts/07-media-processing-contracts.md` §1).
