# Kế hoạch nối dây chuyền production — IMPL-PLAN-PROD-WIRING

Ngày lập: 26/10/2026. Người lập: Orchestrator (Sonnet 5.5) cho AI PM (Sonnet 5.5). Cơ sở: HEAD `de9596c`, đầu vào bắt buộc `docs/implementation/prod-wiring/inventory.md`. Danh sách slice nằm ở `docs/implementation/prod-wiring/slices.md`.

## 1. Mục tiêu và phạm vi

Một lô tạo qua `POST /v1/batches` phải được sản xuất thành video tới completion trong composition production: AppSession và recovery epoch, ghi `cp_stage_runs`, grant thật, outbox relay khởi workflow trên Temporal, các handler D/E/F/I, thu thập A/B/C và `launcher` nối đủ. Sau khi `PW-E2E` PASS thì CP7-10 (một video) và CP7-11 (một trăm video) chạy được trên tài nguyên thật. Kế hoạch không đổi kiến trúc đã duyệt: mọi mục dưới đây là sửa mã lệch hợp đồng hoặc hiện thực phần còn thiếu (inventory mục 8).

Ngoài phạm vi: giao diện (`ui/dist`), tài nguyên thật (thuộc CP7), scheduler cloud (quyết định U1: v1 chỉ chạy trên máy này), AI sáng tác nhạc.

## 2. Kiểm lại các mục CHƯA XÁC NHẬN bằng mã

- `RetryStage` (inventory mục 2): XÁC NHẬN LỖI. `src/controlplane/application/orchestration/workflows/flow.py:189-196` khi RETRY chỉ đặt `failed_stage=None`, không xoá `output_refs`; `flow.py:247-253` chạy lại mọi activity của stage; `flow.py:153-164` (`_prior_refs`) đưa output của chính stage vào `input_refs`, nên activity đã thành công chạy lại với `input_refs` khác dưới cùng `operation_key` và handler trả `OPERATION_KEY_CONFLICT` (`src/voice/worker/activity_handler.py:425`, `src/render/worker/activity_handler.py:421`, `src/source_ingestion/worker/activity_handler.py:309`). Sửa ở `PW-CAT2`.
- Ghi `observed_hash` và `observed_size_bytes` (inventory mục 5): XÁC NHẬN THIẾU. Hai cột có ở `src/controlplane/infrastructure/db/migrations/0005_artifact_metadata.sql:38-39`; `insert_location` (`src/controlplane/infrastructure/db/storage_meta/__init__.py:76-81`) và `update_location` (`:90-92`) không ghi chúng, và không migration nào có trigger (rg `observed_hash` trong thư mục migrations chỉ khớp `0005`). `src/controlplane/application/storage_meta/materialization.py:109` đòi hai giá trị này nên bản local không bao giờ qua cổng. Sửa ở `PW-I1`.
- Kiểm thêm: `cp_app_sessions.recovery_epoch` là TEXT (`0011_orchestration_extensions.sql:60-70`) và `cp_stage_runs.recovery_epoch` đã đổi sang TEXT ở `0011` (rollback của `0011` đổi lại BIGINT), nên chỉ handler D/E/F (đòi `int`) và `launcher.py:914` (epoch dạng `rec-<stamp>-<hex>`) cần đổi. Bảng của E đã đủ 11 bảng (`0016_voice.sql:9-113`), nên `PW-E1` không cần migration.

## 3. Quyết định thiết kế (D8: mặc định đơn giản đủ yêu cầu)

- DQ-01 Thứ tự stage video: `analyze`, `script`, `media_select`, `plan`, `tts`, `align`, `process`, `render`, `qc`, `sync`, `complete`. `VideoProductionWorkflow` lên `workflow_version` 2 (CT-WF-009: breaking, chưa có workflow production nào đang chạy).
- DQ-02 Stage `plan` gồm `BuildProductionPlan`, `ValidateVariant` (pha `plan`), `ReserveVariant`, `GenerateOutputMetadata` (F cần `output_metadata_revision` trước render, `src/render/ports/inputs.py:44-46`). Stage `qc` gồm `inspect_output`, `ValidateVariant` (pha `output`), `prepare_output_ready`; `render` thêm `reconcile_render`. Pha của `ValidateVariant` suy ra từ tên stage trong `stage_run_id` vì trường request cố định (`src/controlplane/domain/orchestration/activity_binding.py:19-36`).
- DQ-03 Epoch là chuỗi thập phân, tăng 1 mỗi lần `restore`, giữ nguyên qua stop/start; mỗi `launcher start` ghi một AppSession ACTIVE trước worker và relay.
- DQ-04 Mỗi activity một grant, thu hồi ngay khi owner đã nhận kết quả (CT-WF-004); stage nhiều activity dùng chung `stage_run_id` chạy lần lượt không vướng `ActiveGrantExistsError`. TTL theo hàng đợi (giá trị mặc định ghi ở `PW-G3`, OI-PW-05).
- DQ-05 Stage run của workflow không video: migration `0019` cho `cp_stage_runs.job_id` nhận NULL và thêm `workflow_id`. Đây là migration duy nhất của kế hoạch.
- DQ-06 Cấp job động: activity nội bộ `AllocateJob` và `FinalizeBatch`; relay khởi `ProductionBatchWorkflow` với `jobs=[]`, vòng lô gọi `AllocateJob` cho từng video; video chạy tuần tự (OI-PW-02).
- DQ-07 Outbox relay chạy trong tiến trình worker (`docs/08-architecture.md` §8.3, dòng 166 và 178): claim `FOR UPDATE SKIP LOCKED`, `start_workflow` với id = `batch_id`, `id_reuse_policy` REJECT_DUPLICATE, `WorkflowAlreadyStarted` là thành công, ack sau khi khởi.
- DQ-08 Disposition `waiting` áp cho mọi stage: `WAITING_CAPABILITY` kèm `WaitReason`, chờ `capability_poll_seconds` hoặc signal rồi đánh giá lại đúng stage đó; job sang `WAITING`.
- DQ-09 Vai trò AI của D dịch tại một điểm sang khoá `ai.route_model_refs`; `production_plan` dùng khoá `selection` vì profile không có khoá `plan` (không sửa profile, OI-PW-04).
- DQ-10 Sáu prompt mặc định là `ConfigRevision(scope_kind='prompt', scope_key=<vai trò>)`, seed khi `launcher start` nếu chưa có, ghim revision vào snapshot, sửa được qua lệnh cấu hình của Control API (FR-CFG-007), giữ biên instruction–data của `PromptEnvelope`.
- DQ-11 Ảnh tải kèm bài (OI-ADAPT-10, quyết định user 25/10/2026): được chọn vào video, kèm provenance, bắt buộc qua `AssessImageSafety`; ảnh không an toàn hoặc không chắc chắn bị loại và thay bằng media seed.
- DQ-12 Nhạc nền (FR-AUD-007, quyết định user): hệ thống tự tìm và thu thập từ nguồn ngoài, không AI sáng tác, ghi provenance; `PW-E4` khảo sát rồi chọn nguồn; không có nhạc phù hợp thì chuỗi vẫn chạy (kết quả loại `none` kèm warning `AUDIO_MIX_QUALITY`).
- DQ-13 Tên tệp WAV: Kokoro ghi tạm, pipeline đặt `voice-artifact-<sha256 của WAV>` trong staging, aligner mở đúng tên đó. GPU chỉ khoá một lần mỗi render.
- DQ-14 Thu thập (U1): vòng lặp cục bộ trong worker, nhịp `collection_interval_minutes` (180) chỉ là nhịp kiểm; mỗi nguồn tối đa một lượt định kỳ mỗi ngày nhờ `cp_source_cycle_marks` (CT-SRC-004).
- DQ-15 Lỗi 401 của Drive có mã lỗi riêng ở `DriveObjectStore`; `PersistVideoOutput` trả `waiting` với mã `credential_unavailable` (CT-ORC-007) và receipt bền được commit trước khi upload.
- DQ-16 Mọi slice dùng adapter giả cho 9Router, Drive, GPU, Kokoro, faster-whisper; PostgreSQL, Temporal (server test của temporalio) và FFmpeg đã ghim là thật. Tài nguyên thật thuộc CP7.

## 4. Thứ tự slice và khung dọc

Khung dọc trước, mở rộng theo khối sau. Chuỗi G chạy tuần tự vì cùng khoá `LOCK-SRC-ORCHESTRATION`: `PW-H0` → `PW-SCHEMA` → `PW-G1` (AppSession) → `PW-G2` (`cp_stage_runs`) → `PW-G3` (grant) → `PW-G4` (capability, trạng thái job và batch) → `PW-CAT1` (catalog) → `PW-CAT2` (`flow.py`) → `PW-G5` (cấp job) → `PW-G6` (outbox relay) → `PW-G7` (completion, `ReserveVariant`) → `PW-VERT`. `PW-VERT` đưa một video đi hết `VideoProductionWorkflow` trên Temporal thật (server test của temporalio) và PostgreSQL thử thật; handler của D/E/F/I là adapter giả trong test.

Sau `PW-VERT` có năm nhánh song song vì khoá khác nhau: D (`PW-D1`..`PW-D3`), E (`PW-E1`..`PW-E4`), F (`PW-F1`..`PW-F4`), I (`PW-I1`, `PW-I2`), A/B/C (`PW-A1`..`PW-A3`, `PW-B1`). Mỗi nhánh thay dần adapter giả của khung dọc bằng hiện thực production. `PW-F4` và `PW-A3` cùng sửa `activities.py` nên chạy tuần tự theo khoá. Hai slice nối cuối: `PW-W1` (G, A, B, C, I vào `launcher`) và `PW-W2` (D, E, F, cùng kiểm không còn activity unbound). `PW-E2E` phụ thuộc mọi slice.

## 5. Khoá tài nguyên

Chỉ dùng khoá đã đăng ký ở `docs/parallel-delivery/ownership-and-locks.yaml`: `LOCK-SRC-ORCHESTRATION` (G), `LOCK-SRC-CREATIVE` (D), `LOCK-SRC-VOICE` (E), `LOCK-SRC-RENDER` (F), `LOCK-SRC-STORAGE` (I), `LOCK-SRC-SOURCE-INGESTION` (A), `LOCK-SRC-INGESTION` (B), `LOCK-SRC-CATALOG` (C), `LOCK-COMPOSITION-ROOT`, `LOCK-MIGRATION-SEQUENCE`, `LOCK-POSTGRES-TEST-DB`. GIẢ ĐỊNH (D8): `tools/launcher/launcher.py` thuộc `LOCK-COMPOSITION-ROOT`. Slice khác phân hệ không chung khoá nên chạy song song.

## 6. Kiểm thử và bằng chứng

Mọi slice có test thật trên PostgreSQL thử (`M2_TEST_PG_DSN`, CSDL tạm tạo và xoá như `tests/integration/adapt/prod/test_adapt_prod_app.py:114-135`; thiếu DSN thì `pytest.fail('BLOCKED_EXTERNAL: ...')`, không skip). Slice chạm workflow dùng server test của temporalio (`WorkflowEnvironment`). Test-first: phải thấy RED đúng oracle trước khi implement. Bằng chứng ở `docs/delivery-evidence/pw-<mã>/report.md`. Worker chỉ chạy lệnh kiểm mục tiêu của slice, không chạy full suite.

## 7. Phủ khoảng trống của inventory

- Mục 2 (G): AppSession, epoch → `PW-G1`; `cp_stage_runs`, bộ ghi kết quả → `PW-G2`; grant, thu hồi, adapter hiệu lực → `PW-G3`; capability_reader, trạng thái job và batch → `PW-G4`; thứ tự stage, `ValidateVariant`, `ReserveVariant` → `PW-CAT1`, `PW-G7`; `waiting`, `RetryStage`, fan-out → `PW-CAT2`; cấp job → `PW-G5`, `PW-B1`; outbox relay → `PW-G6`; completion → `PW-G7`.
- Mục 3 (D) → `PW-D1`..`PW-D3`. Mục 4 (E) → `PW-E1`..`PW-E4`. Mục 5 (F: inspector QC thật, ASS, GPU) → `PW-F1`..`PW-F4`; (I: `PersistVideoOutput`, `MaterializeArtifactSet`) → `PW-I1`, `PW-I2`.
- Mục 6 (A, B, C: `PlanCollectionCycle`, `RegisterMediaDiscovery`) → `PW-A1`..`PW-A3`, `PW-B1`. Nối vào `launcher` → `PW-W1`, `PW-W2`. Nghiệm thu → `PW-VERT`, `PW-E2E`.

## 8. Mục mở và danh sách chờ

- OI-PW-01: OI-CP7-03 (bỏ scheduler cloud theo U1) vẫn chờ user ghi nhận ở R1; không chặn kế hoạch.
- OI-PW-02: vòng lô chạy video tuần tự. 100 video trong 12 giờ cần trung bình tối đa 7,2 phút mỗi video. `PW-E2E` ghi số đo thời gian từng stage; nếu vượt thì Control lập slice chạy song song hai video theo 2 khe GPU.
- OI-PW-03: quyết định OI-ADAPT-10 làm hết hiệu lực mặc định UNVERIFIED ở `docs/implementation/adapt/plan.md:274,321` và mục `rights_unverified_excluded` của CP7-14; Control sửa các chỗ đó trước khi chạy CP7-14.
- OI-PW-04: nếu muốn khoá route riêng cho `production_plan` thì Control thêm khoá `plan` vào `ai.route_model_refs` (`tools/launcher/prod/profile.json:122-130`) bằng slice riêng.
- OI-PW-05: TTL grant theo hàng đợi dùng giá trị mặc định do `PW-G3` ghi; Control đưa vào profile nếu muốn chỉnh.
- OI-PW-06: nguồn nhạc nền do `PW-E4` khảo sát và chọn; cách hiểu lời user "giai đoạn đầu tự tìm nguồn sinh nhạc nền" (hệ thống tự tìm và thu thập nhạc, không AI sáng tác) đã báo user và chờ user sửa nếu sai.
- OI-PW-07: `PW-SCHEMA` sửa `tests/integration/convergence/test_cp3_migration_sequence.py` vì số migration đổi từ 18 sang 19; Control xác nhận quyền sửa khi giao slice.
- pendingUserCheckpoint: không có mục mới do kế hoạch này tạo; OI-CP7-03 vẫn chờ.

## 9. Điều kiện để CP7 chạy được

`PW-E2E` PASS nghĩa là, với dịch vụ ngoài là adapter giả: `POST /v1/batches` sinh một video đi hết 11 stage trên Temporal và PostgreSQL thật tới `CommitVideoCompletion`; mọi activity mà workflow gọi đều có handler thật (0 `unbound`, 0 adapter Fake hoặc Memory trong composition production); resume sau khi dừng và bật lại worker không chạy lại stage đã xong; lỗi 401 của Drive đưa job sang chờ `credential_unavailable` rồi chạy tiếp, không mất việc. Khi đó CP7-10 và CP7-11 chỉ còn thay adapter giả bằng tài nguyên thật. Thứ tự đóng kế hoạch: `PW-VERT` trước, rồi năm nhánh, rồi `PW-W1`, `PW-W2`, cuối cùng `PW-E2E`.
