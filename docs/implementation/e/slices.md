# Danh sách slice — Phân hệ E (IMPL-PLAN-E)

Tài liệu này biên dịch `docs/implementation/e/plan.md` thành 20 work package slice độc lập, kiểm chứng được riêng. Mọi slice là `work_package_slice`; Control biên dịch trong phong bì policy.

## Quy ước chung

- Trường ownedPaths chỉ trong `src/voice/**`, `tests/unit/voice/**`, `tests/integration/voice/**` và tệp bằng chứng `docs/delivery-evidence/<task-id viết thường>/report.md`; mục cuối luôn là report.md.
- Import root `src/`: `import voice...` và `import controlplane...` (chỉ đọc), không tiền tố `src.`.
- Không sửa migration, composition root, lockfile, `tests/m2`, `ui/dist`, `App.tsx`, state machine dùng chung, control API, binding, fixture CP1 hay tài liệu ownership; không thêm thư viện; không gọi mạng, dịch vụ thật hay đọc `Credentials/`; không chạy FFmpeg, ffprobe, TTS hay aligner thật. Slice có port ngoài phải monkeypatch `socket.create_connection` và `socket.getaddrinfo` để ném lỗi trong test.
- Dùng fixture CP1 (đọc bằng `json` và `pathlib`, gốc repo là `Path(__file__).resolve().parents[3]`) và fake đặt trong tệp test; tái dùng module controlplane trong plan §4, không dựng bản trùng. Âm thanh giả sinh bằng `wave` và `struct` của stdlib trong bộ nhớ hoặc `tmp_path`.
- Validator binding: hằng đặc tả trường trong mã; test so hằng với tệp binding JSON và chạy mọi case valid và invalid của fixture đúng `expected_error` (`missing_required`, `wrong_type`, `enum_violation`, `forbidden_field`, `constraint_violation` kèm `field`); `sha256` là 64 ký tự hex thường; integer không nhận bool; trường lạ bị bỏ qua.
- Giá trị policy (khoảng thời lượng voice, sai số timing, loudness, ngưỡng safety, tokenization) chỉ xuất hiện trong fixture của test, gắn nhãn test-only; thiếu policy thì trả `INPUT_NOT_READY`, không có default ẩn (plan §7).
- Test ID chỉ lấy từ catalog `docs/10-test-strategy.md`; không dùng tiền tố `TST-VOI-`, `TST-MED-`, `TST-RND-`, `TST-EF-`. Docstring đầu tệp test có dòng `coveredIds:` liệt kê mã CT và TST bao phủ.
- Test-first: tạo khung module tối thiểu để import được, chạy test và ghi RED do assertion sai oracle (lỗi import hoặc collection không phải RED hợp lệ), sau đó GREEN; ghi lệnh và exit code vào report của slice.
- Không tạo `__init__.py` hay `conftest.py` trong `tests/`; tên tệp test `test_eNN_*.py` duy nhất; lệnh python chạy bằng interpreter khóa của lane.

## Khuôn slice

Mỗi slice theo thứ tự: tiêu đề E-NN kèm tên; kind; ownedPaths; dependsOn; resourceLocks; bindingRefs; acceptance (requirement, instrument, counterexample); testCommands (`git diff --check` và pytest tệp test trong ownedPaths); coveredIds.

## Slice

### E-01: Khung gói voice và ranh giới import
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/__init__.py`
  - `src/voice/domain/__init__.py`
  - `src/voice/application/__init__.py`
  - `src/voice/ports/__init__.py`
  - `src/voice/adapters/__init__.py`
  - `src/voice/worker/__init__.py`
  - `src/voice/projections/__init__.py`
  - `tests/unit/voice/test_e01_package_layout.py`
  - `docs/delivery-evidence/e-01/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-SRC-VOICE`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- acceptance:
  - requirement: tạo gói `voice` và 6 gói con chỉ có docstring; test dùng `ast` và `pathlib` quét mọi `src/voice/**/*.py`: import được `voice` từ root `src/`; không có `import src.` hay `from src.`; không import `creative`, `render`, `catalog`, `ingestion`, `source_ingestion`, `psycopg`, `temporalio`, `pydantic`, `socket`, `subprocess`, `urllib.request`, `http.client`, `controlplane.infrastructure`, `controlplane.ui`, `controlplane.api`, module `controlplane.config` hoặc module con của nó; không có thư mục `storage`, `orchestration`, `ui`, `config` dưới `src/voice`.
  - instrument: `python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider`
  - counterexample: dùng `from src.voice`; import gói F hay D để gọi trực tiếp; import `subprocess` để chạy FFmpeg trong slice; dựng `src/voice/orchestration` trùng G.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider`
- coveredIds: không

### E-02: Job xử lý chung và điều kiện ready (CT-PROC-001, CT-PROC-002, CT-PROC-008)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/processing.py`
  - `tests/unit/voice/test_e02_processing_contract.py`
  - `docs/delivery-evidence/e-02/report.md`
- dependsOn: `E-01`
- resourceLocks: `LOCK-E-02`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: `Disposition` (StrEnum `succeeded`, `failed`, `waiting`, `outcome_unknown`), `OutputClass` (StrEnum `reusable`, `per_video`, `diagnostic`), `ProcessingRequest` và `ProcessingResult` frozen đủ trường CT-PROC-001/002 (thiếu trường bắt buộc hoặc thiếu `processor_identity` → lỗi kèm `field`); `input_fingerprint` tính bằng `controlplane.application.idempotency.canonicalization.request_hash` trên input refs và spec, không đổi khi đổi thứ tự khóa dict, đổi khi đổi một hash; `is_ready(result, verified_refs)` chỉ True khi `succeeded` và mọi output ref nằm trong tập ref đã được I verify (tham số), còn `waiting`, `failed`, `outcome_unknown` không bao giờ ready; `retention_intent(output_kind)` theo plan §7 (rendition và analysis → `reusable`; voice, word timing, mix tạm → `per_video`; frame, log, report debug → `diagnostic`); output ref phải khác input ref; hash đầu ra dùng sha256 hex thường như fixture `i-artifact-version`, case `content_hash_uppercase` bị từ chối. Module không có hàm xóa hay cleanup.
  - instrument: `python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider`
  - counterexample: coi `succeeded` là ready khi I chưa verify; thiếu processor identity vẫn hợp lệ; output ghi đè input; voice xếp `reusable`; E có hàm cleanup.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider`
- coveredIds: CT-PROC-001, CT-PROC-002, CT-PROC-008, TST-INT-INV-008 (phía E, mức domain)

### E-03: ProbeMedia — báo cáo kỹ thuật thực tế (CT-PROC-003)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/probe.py`
  - `src/voice/ports/probe.py`
  - `tests/unit/voice/test_e03_probe_media.py`
  - `docs/delivery-evidence/e-03/report.md`
- dependsOn: `E-02`
- resourceLocks: `LOCK-E-03`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: `ProbePort` (Protocol `probe(artifact_ref)` trả dict mô phỏng đầu ra ffprobe) và `parse_probe_output(raw, declared_extension, declared_mime, observed_sha256, observed_size)` dựng `ProbeReport` frozen gồm media type và container quan sát, danh sách stream video/audio/image (duration_ms, width, height, frame_rate, sample_rate, channels, codec, pixel_format), tín hiệu đọc được (`readable`, `corrupt`, `unreadable`), cờ hỏng, orientation và color metadata, sha256 và size đã quan sát. Extension hoặc MIME khai báo mâu thuẫn với stream quan sát thì giữ giá trị quan sát và thêm warning `declared_type_mismatch`; thiếu stream, duration âm hoặc không hữu hạn → `corrupt`; dict rỗng → `unreadable`; `observed_sha256` sai định dạng → lỗi. Không gọi ffprobe hay subprocess.
  - instrument: `python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider`
  - counterexample: tin extension png khi stream là video; tệp hỏng được ghi `readable`; duration NaN được chấp nhận; module import `subprocess`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider`
- coveredIds: CT-PROC-003

### E-04: AnalyzeMedia có version (CT-PROC-004)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/media_analysis.py`
  - `tests/unit/voice/test_e04_media_analysis.py`
  - `docs/delivery-evidence/e-04/report.md`
- dependsOn: `E-02`
- resourceLocks: `LOCK-E-04`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: `AnalysisResult` frozen gồm analysis_id, input artifact ref và hash, loại phân tích (StrEnum `keyframes_shots`, `transcript_ocr`, `entities_faces_objects`, `motion_scene_audio_energy`, `semantic_tags`), model hoặc tool và version, confidence trong [0,1] (ngoài khoảng → lỗi), coverage trong [0,1] và `failure_flags`; `AnalysisHistory` append-only: `append(result)` trả lịch sử mới; cùng input, model, version và spec → trả bản cũ (không tạo trùng); model hoặc version mới → revision mới, bản cũ giữ nguyên và vẫn truy được; không có hàm sửa hay xóa. Phân tích transcript hoặc OCR của clip không tạo trạng thái safety.
  - instrument: `python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider`
  - counterexample: model mới ghi đè kết quả cũ; confidence 1.5 hợp lệ; lịch sử bị rút gọn; analysis clip gắn safety state.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider`
- coveredIds: CT-PROC-004

### E-05: AssessImageSafety — chỉ áp dụng cho ảnh (CT-PROC-005)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/image_safety.py`
  - `tests/unit/voice/test_e05_image_safety.py`
  - `docs/delivery-evidence/e-05/report.md`
- dependsOn: `E-02`
- resourceLocks: `LOCK-E-05`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: `SafetyOutcome` (StrEnum đúng 6 trạng thái CT-PROC-005: `SAFE`, `TRANSFORM_REQUIRED`, `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED`, `UNREADABLE`), `ImageSafetyAssessment` frozen (artifact ref, outcome, categories, regions kèm confidence, `policy_revision`, detector identity, warnings) và `assess_image_safety(media_kind, detection, policy)`; `media_kind` khác `image` (clip, audio) → `SafetyNotApplicable`; thiếu policy → `INPUT_NOT_READY`; detector báo lỗi hoặc ném ngoại lệ → `DETECTION_FAILED`, độ tin cậy dưới ngưỡng policy → `UNCERTAIN`, tệp không đọc được → `UNREADABLE`; chỉ kết quả phát hiện sạch mới cho `SAFE`; `original_usable(outcome, transform_succeeded, policy_requires_transform)` đúng bảng CT-PROC-005 (`SAFE` có; `TRANSFORM_REQUIRED` chỉ sau transform thành công nếu policy yêu cầu; `UNCERTAIN` và `DETECTION_FAILED` có kèm warning; `TRANSFORM_FAILED` có nếu tệp còn đọc được; `UNREADABLE` không). Test dựng Sensitive Image Set giả trong tệp test: safe, trẻ em, máu me, vũ khí, uncertain, detector failure, unreadable.
  - instrument: `python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider`
  - counterexample: ảnh uncertain hoặc detector lỗi bị ghi `SAFE`; clip được đánh giá safety; `UNREADABLE` vẫn dùng được; policy thiếu mà vẫn ra kết quả.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider`
- coveredIds: CT-PROC-005, TST-E2E-011 (phía E, mức domain)

### E-06: TransformSensitiveImage (CT-PROC-006)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/image_transform.py`
  - `tests/unit/voice/test_e06_image_transform.py`
  - `docs/delivery-evidence/e-06/report.md`
- dependsOn: `E-05`
- resourceLocks: `LOCK-E-06`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: `TransformRequest` frozen (image artifact ref, regions hoặc mask kèm confidence, categories, `transform_policy_revision`, output technical profile) và `TransformResult` frozen (processed artifact ref, mask/evidence ref, processor version, `post_assessment` kiểu `ImageSafetyAssessment`, lineage tới ảnh gốc, trạng thái `success`, `warning` hoặc `failure`); hành động theo category (blur trẻ em, làm mờ hoặc đổi màu máu me, xử lý vùng vũ khí) lấy từ policy, category không có hành động trong policy → `INPUT_NOT_READY`, không có hằng blur; vũ khí tạo được request mang category và policy revision; `media_kind` là `clip` → `SafetyNotApplicable`; transform ném lỗi hoặc `post_assessment` vẫn `TRANSFORM_REQUIRED` → outcome `TRANSFORM_FAILED`, không bao giờ `success`, ảnh gốc vẫn được tham chiếu; visual hook do user nhập (cờ `user_visual_hook`) → bỏ qua pipeline với lý do `hook_already_blurred`, còn thumbnail lấy từ nguồn vẫn chạy; `TransformPort` (Protocol) và fake đặt trong test; ref ảnh gốc không đổi.
  - instrument: `python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider`
  - counterexample: transform lỗi vẫn ghi success; hằng blur cho vũ khí; clip bị transform; ảnh gốc bị thay bằng bản đã xử lý.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider`
- coveredIds: CT-PROC-006, TST-E2E-011 (phía E, mức domain)

### E-07: NormalizeMedia và rendition có lineage (CT-PROC-007)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/normalize.py`
  - `src/voice/ports/media_tool.py`
  - `tests/unit/voice/test_e07_normalize_media.py`
  - `docs/delivery-evidence/e-07/report.md`
- dependsOn: `E-02`
- resourceLocks: `LOCK-E-07`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: `NormalizeOperation` (StrEnum `crop`, `resize`, `pad`, `color_conversion`, `transcode`, `audio_normalize`, `extract_frame`, `duration_trim`), `NormalizeSpec` frozen (operations có thứ tự, tham số, `tool_version`, `spec_revision`, `seed` tùy chọn) và `spec_fingerprint` bằng `request_hash`; `plan_rendition(input_ref, spec, media_kind, focus_region)` trả `RenditionPlan` frozen có lineage tới input, output ref mới khác input (trùng → lỗi) và `spec_fingerprint`; cùng input, spec, `tool_version` → cùng fingerprint (dedup được), khác `tool_version` hoặc `seed` → khác; crop làm mất `focus_region` của plan → `focus_rule_violation`; `media_kind` là `clip` mà spec có `blur` hoặc `recolor` → từ chối; `MediaToolPort` (Protocol `run(plan)` trả `ToolOutcome` gồm `status`, `output_ref`, `output_sha256`, `error`). Plan không chứa chuỗi lệnh shell.
  - instrument: `python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider`
  - counterexample: rendition ghi đè bản gốc; đổi `tool_version` mà fingerprint giữ nguyên; crop mất chủ thể vẫn hợp lệ; clip bị blur; plan chứa lệnh shell.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider`
- coveredIds: CT-PROC-007

### E-08: VoiceTrack và ràng buộc script (CT-TTS-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/voice_track.py`
  - `src/voice/ports/script_text.py`
  - `tests/unit/voice/test_e08_voice_track.py`
  - `docs/delivery-evidence/e-08/report.md`
- dependsOn: `E-01`
- resourceLocks: `LOCK-E-08`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
- acceptance:
  - requirement: hằng đặc tả trường `VoiceTrackRequest` và `VoiceTrackResult` trong mã, validator chạy đủ case fixture (`missing_script_fingerprint` → `missing_required`; `duration_as_text` và `duration_as_boolean` → `wrong_type` field `actual_duration_ms`); `ScriptTextPort.get_text(script_version_id)` trả văn bản và fingerprint do D tính (Protocol ở `src/voice/ports/script_text.py`, fake trong test), `verify_script_binding(request, script_text)` từ chối khi fingerprint lệch (`script_fingerprint_mismatch`); `compute_voice_hash(audio_bytes)` là sha256 hex thường; `VoiceTrack` frozen gồm trường của `VoiceTrackResult` và `retention_class` `per_video`; `check_duration(actual_duration_ms, policy_range)`: policy `None` → `INPUT_NOT_READY`, ngoài khoảng → finding `voice_duration_out_of_range` (fixture test-only 61000–70000 ms, không hằng trong mã); `pronunciation_hints` và `style_parameters` tùy chọn được giữ nguyên.
  - instrument: `python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider`
  - counterexample: hằng 61000–70000 trong mã; chấp nhận fingerprint lệch; duration kiểu bool hợp lệ; E tự tính lại fingerprint script bằng quy tắc riêng.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider`
- coveredIds: CT-TTS-001 (phía E)

### E-09: Validator WordTiming theo binding (CT-SUB-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/word_timing.py`
  - `tests/unit/voice/test_e09_word_timing.py`
  - `docs/delivery-evidence/e-09/report.md`
- dependsOn: `E-01`
- resourceLocks: `LOCK-E-09`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
- acceptance:
  - requirement: hằng đặc tả trường `WordTiming` trong mã và `validate_word_timing(payload)` chạy đủ case fixture (`words_out_of_order` và `word_beyond_voice_duration` → `constraint_violation` field `words`; `missing_voice_hash` → `missing_required`; case valid); mỗi từ có `start_ms`, `end_ms` là integer không phải bool và `0 <= start_ms < end_ms`; từ sau không bắt đầu sớm hơn từ trước kết thúc (chồng lấn là `constraint_violation`, plan §7); `end_ms <= voice_duration_ms` khi trường này có; `segment_boundaries` có thứ tự và nằm trong `[0, voice_duration_ms]`; `words` rỗng → `constraint_violation`; `confidence` nếu có nằm trong [0,1]; `script_fingerprint` và `voice_hash` là sha256 hex thường; trường lạ bị bỏ qua; kết quả hợp lệ là `WordTimingRecord` frozen.
  - instrument: `python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider`
  - counterexample: từ có `end_ms <= start_ms` được chấp nhận; từ vượt `voice_duration_ms`; hai từ chồng lấn được chấp nhận; hằng lệch binding mà test vẫn xanh.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider`
- coveredIds: CT-SUB-001 bất biến 1

### E-10: Phủ từ, confidence và báo cáo gap (CT-SUB-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/timing_coverage.py`
  - `tests/unit/voice/test_e10_timing_coverage.py`
  - `docs/delivery-evidence/e-10/report.md`
- dependsOn: `E-09`
- resourceLocks: `LOCK-E-10`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
- acceptance:
  - requirement: `TokenizationPolicy` frozen (`revision` và quy tắc fixture test-only: tách theo khoảng trắng, chuẩn hóa NFC, casefold, bỏ dấu câu hai đầu; thiếu policy → `INPUT_NOT_READY`), `tokenize_script(text, policy)` và `check_coverage(script_text, words, policy)` trả `CoverageReport` frozen (số từ kỳ vọng, số khớp, chỉ số thiếu, chỉ số dư, `complete`); `complete` chỉ khi 100% từ của script có timing đúng thứ tự và không dư; `normalized_text` của từng từ phải bằng token chuẩn hóa tương ứng. `build_gap_report(words, voice_duration_ms, policy)` trả `alignment_gaps` (khoảng trống giữa các từ, đầu và cuối so với thời lượng voice, lớn hơn `gap_tolerance_ms` của policy) và danh sách từ có confidence dưới `min_confidence` của policy; policy hoặc `gap_tolerance_ms` bằng `None` → `INPUT_NOT_READY` (ROADMAP-OPEN-008), không có hằng 100 ms trong mã.
  - instrument: `python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider`
  - counterexample: script bỏ sót một từ vẫn `complete`; từ dư không bị phát hiện; hằng 100 ms; viết hoa hoặc dấu câu làm lệch coverage.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider`
- coveredIds: CT-SUB-001 (phủ từ, gap, confidence)

### E-11: Ràng buộc timing với script và voice, invalidation (CT-SUB-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/timing_binding.py`
  - `tests/unit/voice/test_e11_timing_binding.py`
  - `docs/delivery-evidence/e-11/report.md`
- dependsOn: `E-08`, `E-09`
- resourceLocks: `LOCK-E-11`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
- acceptance:
  - requirement: `TimingBinding` frozen (`script_version_id`, `script_fingerprint`, `voice_hash`, `timing_artifact_ref`); `check_timing_binding(timing, current_script_fingerprint, current_voice_hash)` trả `valid` hoặc `invalid` kèm reason `script_changed`, `voice_changed` hoặc cả hai; `require_valid_timing` ném `TimingBindingError` khi invalid; `invalidate_downstream(change, voice_tracks, timings)` với change là script đổi, voice đổi hoặc revision artifact voice đổi trả `InvalidationResult` frozen liệt kê voice track và timing bị stale cùng reason, không sửa hay xóa bản cũ; script đổi làm cả voice track gắn fingerprint cũ lẫn timing stale, voice đổi chỉ làm timing stale; bản mới sau invalidation phải là bản ghi mới.
  - instrument: `python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider`
  - counterexample: timing cũ vẫn hợp lệ sau khi đổi script hoặc voice; invalidation sửa tại chỗ bản cũ; đổi voice mà không làm timing stale.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider`
- coveredIds: TST-MEDIA-INV-007 (mức domain), CT-SUB-001 bất biến 2 và 3

### E-12: Bằng chứng ngôn ngữ gắn exact revision (CT-RND-002)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/language_evidence.py`
  - `tests/unit/voice/test_e12_language_evidence.py`
  - `docs/delivery-evidence/e-12/report.md`
- dependsOn: `E-08`, `E-09`
- resourceLocks: `LOCK-E-12`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `docs/parallel-delivery/bindings/f-render-package.json`
- acceptance:
  - requirement: `LanguageEvidence` frozen (script_version_id, script_fingerprint, voice_hash, `voice_locale_reported` do adapter báo cáo từ output provider, `subtitle_text_hash` là sha256 chuỗi `text` của các từ theo thứ tự, `timing_artifact_ref`, `expected_language`, `evidence_ref` tính bằng `request_hash`); `build_language_evidence(request, voice_track, locale_report, timing)` ném `revision_mismatch` khi `script_fingerprint` hoặc `voice_hash` giữa request, voice track và timing không khớp; thiếu `locale_report` → `INPUT_NOT_READY`; locale khác `expected_language` vẫn tạo evidence kèm finding `language_mismatch`, không bị bỏ; E không tự tuyên bố tiếng Anh hợp lệ (F kiểm `ENGLISH_OUTPUT_VALID`).
  - instrument: `python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider`
  - counterexample: evidence tin `expected_language` khi locale báo khác; evidence cho timing khớp script nhưng voice khác; evidence tự ghi English valid.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider`
- coveredIds: TST-QC-INV-019 (phía E), CT-RND-002 `language_validation_refs`

### E-13: PrepareAudioBed — music, SFX, loudness, mix (CT-AUD-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/domain/audio_bed.py`
  - `tests/unit/voice/test_e13_audio_bed.py`
  - `docs/delivery-evidence/e-13/report.md`
- dependsOn: `E-02`
- resourceLocks: `LOCK-E-13`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: `AudioBedRequest` frozen (cue plan: danh sách cue có `kind` music hoặc sfx, `start_ms < end_ms`, ref artifact hoặc intent đã resolve; voice artifact ref; `preset_audio_policy_revision`; ràng buộc loudness và mix; cờ `fallback_allowed`) và `AudioBedResult` frozen (rendition refs đã chuẩn bị, cue timing, báo cáo loudness và peak, provenance và risk metadata, warnings, `substitutions`); `validate_loudness_report(report, constraints)`: constraints `None` → `INPUT_NOT_READY`, ngoài mục tiêu → `loudness_out_of_target`; thay bài hoặc đổi mood khi `fallback_allowed` sai → `substitution_not_allowed`, khi được phép thì ghi vào `substitutions` để F đưa vào render package; cue không hợp lệ (start không nhỏ hơn end, giá trị âm) → lỗi; trường integer không nhận bool. Không chọn bài mới ngoài refs đã cho; giá trị loudness chỉ nằm trong fixture test-only.
  - instrument: `python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider`
  - counterexample: hằng -14 đến -16 LUFS trong mã; đổi bài khi plan không cho fallback; thay thế không được ghi lại; cue có start lớn hơn end.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider`
- coveredIds: CT-AUD-001

### E-14: Port TTS, route J, fake adapter và TtsInvocationRecord (CT-AI-ROUTE-001, CT-AI-ROUTE-002)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/ports/tts.py`
  - `src/voice/domain/tts_invocation.py`
  - `src/voice/adapters/fake_tts.py`
  - `tests/unit/voice/test_e14_tts_route_invocation.py`
  - `docs/delivery-evidence/e-14/report.md`
- dependsOn: `E-08`
- resourceLocks: `LOCK-E-14`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: `VoiceRoutePort.resolve(request)` và `TtsEnginePort.synthesize(decision, script_text, request)` (Protocol); validator `ProviderRouteRequest` và `ProviderRouteDecision` theo binding `j-provider-route` (case `missing_data_sensitivity`, `api_key_leaked` → `forbidden_field`, `missing_route_revision`, `fallback_order_as_string`), từ chối decision chứa `forbidden_fields` ở mọi cấp lồng; `FakeVoiceRoute` và `FakeTtsEngine` trả WAV sinh bằng `wave` có thời lượng định sẵn, đếm lượt gọi, không mở mạng; lỗi timeout và rate limit giả → `TtsProviderError` có `retryable` và thông điệp đã redact; `TtsInvocationRecord` frozen ghi provider, model, account, project ref, route revision, voice revision, input fingerprint, usage_metrics, latency, attempt, fallback path, kết quả validation và lỗi đã redact; canary secret đặt trong lỗi của fake không xuất hiện trong `repr`, dict hay JSON của record; fallback chỉ theo `fallback_order` của decision và `allowed_fallbacks` của request, provider ngoài danh sách bị từ chối; số lần thử lấy từ policy input (thiếu → `INPUT_NOT_READY`), hết budget trả lỗi cuối, không lặp vô hạn. `ai_role` `voice_synthesis` trong test là GIẢ ĐỊNH.
  - instrument: `python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider`
  - counterexample: decision có `api_key` được chấp nhận; fallback sang provider ngoài danh sách; fake mở socket; record chứa canary; retry vô hạn.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider`
- coveredIds: TST-SEC-INV-012, CT-AI-ROUTE-001, CT-AI-ROUTE-002 (phía E)

### E-15: Port lưu trữ, UoW in-memory, outbox và event của E
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/ports/repositories.py`
  - `src/voice/adapters/memory.py`
  - `tests/unit/voice/test_e15_ports_memory.py`
  - `docs/delivery-evidence/e-15/report.md`
- dependsOn: `E-02`, `E-05`, `E-08`, `E-09`
- resourceLocks: `LOCK-E-15`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- acceptance:
  - requirement: Protocol `OutputRepository` append-only (`append(kind, key, revision, record)`, `latest`, `revisions`; revision mới không ghi đè, không xóa bản cũ; `voice_hash` và `timing_artifact_ref` duy nhất); UoW in-memory implement `controlplane.domain.interfaces.uow.IUnitOfWork` (đọc chữ ký thật trong tệp; rollback hủy mọi ghi kể cả outbox); outbox implement `controlplane.domain.interfaces.outbox.IOutboxWriter` dedup theo `deduplication_id`; hàm dựng event `ImageSafetyAssessed`, `MediaProcessingCompleted`, `VoiceReady`, `WordTimingReady` bằng `controlplane.domain.events.contracts.DomainEvent` và `ensure_safe_event_payload`, payload chỉ chứa ref, hash, revision (không byte âm thanh, không secret); builder của `MediaProcessingCompleted`, `VoiceReady`, `WordTimingReady` từ chối khi `artifact_verified` sai (CT-PROC-002, phần E của `TST-INT-INV-008`); envelope khớp case valid và invalid của fixture `domain-event-envelope` (`producer_outside_modules`, `aggregate_revision_as_string`, `stack_trace_in_event`, `missing_recovery_epoch`).
  - instrument: `python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider`
  - counterexample: tạo `IUnitOfWork`, `IOutboxWriter` hay `DomainEvent` mới; ghi đè voice cũ; rollback để lại outbox; phát `VoiceReady` khi chưa verify; payload chứa byte âm thanh.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider`
- coveredIds: CT-EVT-002, CT-EVT-003 (phía E), TST-INT-INV-008 (phía E)

### E-16: Command tạo voice và word timing (integration)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/application/voice_pipeline.py`
  - `src/voice/ports/aligner.py`
  - `src/voice/adapters/fake_aligner.py`
  - `tests/integration/voice/test_e16_voice_timing_pipeline.py`
  - `docs/delivery-evidence/e-16/report.md`
- dependsOn: `E-10`, `E-11`, `E-12`, `E-14`, `E-15`
- resourceLocks: `LOCK-E-16`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: command `CreateVoiceTrack` (kiểm binding script qua `ScriptTextPort` giả, gọi route và TTS giả của E-14, kiểm duration policy của E-08, ghi VoiceTrack, `TtsInvocationRecord`, receipt và outbox `VoiceReady` trong một UoW của E-15) và `CreateWordTiming` (yêu cầu VoiceTrack đã commit; gọi `AlignerPort` giả; chạy validator E-09, E-10, kiểm binding E-11, dựng `LanguageEvidence` E-12; ghi WordTiming, báo cáo, evidence, receipt và outbox `WordTimingReady` trong một UoW); `AlignerPort` (Protocol) ở `src/voice/ports/aligner.py` và fake ở `src/voice/adapters/fake_aligner.py`. Kiểm: `script_fingerprint` lệch văn bản của `ScriptTextPort` → từ chối và 0 lượt gọi TTS; timeout hoặc rate limit của fake → không có VoiceTrack, không event, invocation record ghi attempt thất bại, lịch sử cũ không đổi; cùng `operation_key` và payload → trả receipt cũ, khác payload → idempotency conflict (`request_hash`); `CreateWordTiming` khi chưa có voice → từ chối và aligner 0 lượt; aligner trả từ đảo thứ tự hoặc thiếu từ → không `WordTimingReady`; đổi script hoặc voice sau khi có timing → timing cũ bị từ chối (`TST-MEDIA-INV-007`) và timing mới chỉ tạo qua command mới.
  - instrument: `python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider`
  - counterexample: gọi TTS trước khi kiểm fingerprint; outbox ghi ngoài UoW; gửi lặp tạo voice thứ hai; timing cũ vẫn được chấp nhận sau khi đổi voice; timing được tạo khi chưa có voice.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider`
- coveredIds: TST-MEDIA-INV-007, TST-E2E-001 (đoạn voice và timing, phía E), CT-TTS-001, CT-SUB-001

### E-17: Command xử lý media và audio bed (integration)
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/application/media_pipeline.py`
  - `tests/integration/voice/test_e17_media_processing_pipeline.py`
  - `docs/delivery-evidence/e-17/report.md`
- dependsOn: `E-03`, `E-04`, `E-06`, `E-07`, `E-13`, `E-15`
- resourceLocks: `LOCK-E-17`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: command `ProbeMedia`, `AssessImageSafety`, `TransformSensitiveImage`, `NormalizeMedia`, `PrepareAudioBed`; mỗi command một UoW gồm output mới, receipt và outbox (`ImageSafetyAssessed`, `MediaProcessingCompleted`); dùng `ProbePort`, `MediaToolPort`, `TransformPort` giả. Kiểm: ảnh `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED` đi tiếp kèm warning và không được ghi `SAFE` hay processed thành công, lô không dừng (`TST-E2E-011`, phần E); ảnh `UNREADABLE` không dùng được; clip gửi vào `AssessImageSafety` hoặc `TransformSensitiveImage` bị từ chối còn `NormalizeMedia` chạy được; tiêm lỗi crash trước và trong side effect → `failed`, sau side effect nhưng trước receipt → `outcome_unknown` và không retry trực tiếp (CT-STATE-011); tệp partial, hash lệch hoặc output corrupt → không ready, không `MediaProcessingCompleted`; ref bản gốc không đổi sau mọi command; `MediaProcessingCompleted` chỉ phát khi có verify evidence của I (tham số).
  - instrument: `python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider`
  - counterexample: ảnh lỗi detector được ghi safe; clip bị blur; retry trực tiếp từ `outcome_unknown`; bản gốc bị thay; phát event khi output chưa verify.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider`
- coveredIds: TST-E2E-011 (phía E), CT-PROC-003..CT-PROC-007, CT-AUD-001

### E-18: Worker activity cho G
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/worker/activity_handler.py`
  - `tests/integration/voice/test_e18_worker_activity.py`
  - `docs/delivery-evidence/e-18/report.md`
- dependsOn: `E-16`, `E-17`
- resourceLocks: `LOCK-E-18`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: `handle_activity(request, grant, deps)` nhận `ActivityRequest` (dict theo binding `g-activity-execution`) kèm `controlplane.domain.orchestration.ExecutionGrant` (không tạo lớp grant mới; trường lệch binding ghi vào report và CONV-E-05), gọi command của E-16 hoặc E-17 theo `activity_name`, trả `ActivityResult` với `output_refs`, `metrics`, `warnings`, `problem` đã redact; generation hoặc recovery epoch cũ → disposition `stale`, không commit; lặp `operation_key` trả kết quả cũ; `activity_name` chưa biết → problem có cấu trúc; precondition desktop do G kiểm (`WAITING_CAPABILITY`), E không tự chờ; chỉ chạy đúng activity được yêu cầu, stage sau không tự chạy (`TST-E2E-014`, đoạn E); test `ast` khẳng định handler không import `temporalio`, `controlplane.ui`, `controlplane.api`, `creative`, `render`, `catalog`.
  - instrument: `python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider`
  - counterexample: generation cũ ghi voice mới; `ActivityResult` chứa secret; handler đăng ký workflow Temporal trực tiếp; chạy tiếp stage sau khi xong stage trước.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider`
- coveredIds: CT-WF-003, CT-WF-006 (phía E), TST-E2E-014 (đoạn E)

### E-19: Projection truy vết read-only
- kind: `work_package_slice`
- ownedPaths:
  - `src/voice/projections/trace_queries.py`
  - `tests/unit/voice/test_e19_trace_projection.py`
  - `docs/delivery-evidence/e-19/report.md`
- dependsOn: `E-15`
- resourceLocks: `LOCK-E-19`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: `trace_voice`, `trace_timing`, `trace_processed_media`: từ VoiceTrack truy ngược script fingerprint, route, provider, model, voice revision và receipt; từ WordTiming truy `voice_hash`, script fingerprint, validation report và language evidence; từ ProcessedMedia truy input refs, spec revision và processor identity (acceptance §10 mục 1); liệt kê lịch sử revision không ghi đè; phân loại `per_video` hay `reusable`; query không gọi provider (fake đếm 0 lượt); lọc theo workspace; không lộ secret hay lỗi chưa redact.
  - instrument: `python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider`
  - counterexample: query kích hoạt TTS; trả output của workspace khác; trace thiếu processor identity.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider`
- coveredIds: acceptance §10 mục 1 của contract 07

### E-20: Ma trận test ID và acceptance contract
- kind: `work_package_slice`
- ownedPaths:
  - `tests/unit/voice/test_e20_coverage_catalog.py`
  - `docs/delivery-evidence/e-20/report.md`
- dependsOn: `E-01`, `E-02`, `E-03`, `E-04`, `E-05`, `E-06`, `E-07`, `E-08`, `E-09`, `E-10`, `E-11`, `E-12`, `E-13`, `E-14`, `E-15`, `E-16`, `E-17`, `E-18`, `E-19`
- resourceLocks: `LOCK-E-20`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- acceptance:
  - requirement: test chỉ dùng stdlib đọc docstring của `tests/unit/voice/test_e*.py` và `tests/integration/voice/test_e*.py` (trừ chính E-20), khẳng định mỗi mã TST-MEDIA-INV-007, TST-INT-INV-008, TST-QC-INV-019, TST-SEC-INV-012, TST-E2E-001, TST-E2E-011, TST-E2E-014 và CT-PROC-001..CT-PROC-008, CT-TTS-001, CT-SUB-001, CT-AUD-001 có trong ít nhất một tệp và tệp đó có ít nhất một hàm `test_`; không tệp nào dùng mã tiền tố `TST-VOI-`, `TST-MED-`, `TST-RND-`, `TST-EF-`; report ghi bảng ánh xạ từng mục acceptance §10 (1 đến 6) của contract 07 sang slice và test.
  - instrument: `python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider`
  - counterexample: một CT-PROC không có test trực tiếp; mã chỉ xuất hiện trong E-20; dùng test ID ngoài catalog.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider`
- coveredIds: acceptance §10 mục 1 đến 6 của contract 07
