# Danh sách slice — Phân hệ F (IMPL-PLAN-F)

Tài liệu này biên dịch `docs/implementation/f/plan.md` thành 22 work package slice độc lập, kiểm chứng được riêng. Mọi slice là `work_package_slice`; Control biên dịch trong phong bì policy.

## Quy ước chung

- Trường ownedPaths chỉ trong `src/render/**`, `tests/unit/render/**`, `tests/integration/render/**` và tệp bằng chứng `docs/delivery-evidence/<task-id viết thường>/report.md`; mục cuối luôn là report.md.
- Import root `src/`: `import render...` và `import controlplane...` (chỉ đọc), không tiền tố `src.`.
- Không sửa migration, composition root, lockfile, `tests/m2`, `ui/dist`, `App.tsx`, state machine dùng chung, control API, binding, fixture CP1 hay tài liệu ownership; không thêm thư viện; không gọi mạng hay dịch vụ thật, không đọc `Credentials/`; không chạy FFmpeg, ffprobe hay tiến trình nào (không import `subprocess`, `os`, `shutil`, `tempfile`); slice có port ngoài phải monkeypatch `socket.create_connection` và `socket.getaddrinfo` để ném lỗi trong test.
- F không xóa, đổi tên hay ghi đè tệp: không hàm tên `delete_*`, `cleanup_*`, `remove_*`; không gọi `unlink`, `rmdir`, `rmtree`, `remove`, `rename`, `truncate` (F-01 kiểm bằng `ast` trên mọi `src/render/**/*.py`).
- Fixture CP1 đọc bằng `json` và `pathlib`, gốc repo là `Path(__file__).resolve().parents[3]`; fake đặt trong tệp test (hoặc `src/render/adapters` khi slice sở hữu); dùng lại module controlplane theo plan §4, không dựng bản trùng. Media giả chỉ là metadata (dict, dataclass) và byte giả sinh trong bộ nhớ; không có tệp video thật.
- Validator binding: hằng đặc tả trường trong mã; test so hằng với binding JSON và chạy MỌI case valid và invalid của fixture đúng `expected_error` (`missing_required`, `wrong_type`, `enum_violation`, `forbidden_field`, `constraint_violation` kèm `field`); `sha256` là 64 ký tự hex thường; integer không nhận bool; trường lạ bị bỏ qua.
- Giá trị policy (output profile, khoảng thời lượng, sai số karaoke, ngưỡng audio, visual, hook, ngôn ngữ yêu cầu, năm preset) chỉ xuất hiện trong fixture test-only có nhãn; thiếu policy → `INPUT_NOT_READY`, không default ẩn (plan §7).
- Test ID chỉ lấy từ catalog `docs/10-test-strategy.md`; docstring đầu tệp test có dòng `coveredIds:` liệt kê mã CT và TST bao phủ.
- Test-first: tạo khung module tối thiểu để import được, chạy test, ghi RED do assertion sai oracle (lỗi import hay collection không phải RED hợp lệ), rồi GREEN; ghi lệnh và exit code vào report của slice. Không `__init__.py` hay `conftest.py` trong `tests/`; tên tệp test `test_fNN_*.py` duy nhất; lệnh python chạy bằng interpreter khóa của lane.

## Khuôn slice

Mỗi slice theo thứ tự: tiêu đề `### F-NN: tên`; kind; ownedPaths; dependsOn; resourceLocks; bindingRefs; acceptance (requirement, instrument, counterexample); testCommands (`git diff --check` và pytest tệp test trong ownedPaths); coveredIds. `instrument` và dòng pytest trong testCommands đều là `python -m pytest <tệp test> -q -p no:cacheprovider`; testCommands luôn có `git diff --check` đứng trước. Các mục danh sách (ownedPaths, bindingRefs, testCommands) dùng dạng hai khoảng trắng, gạch, một khoảng trắng rồi đường dẫn hoặc lệnh trong backtick, mỗi dòng một mục.

## Slice

### F-01: Khung gói render và ranh giới import
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/__init__.py`
  - `src/render/domain/__init__.py`
  - `src/render/application/__init__.py`
  - `src/render/ports/__init__.py`
  - `src/render/adapters/__init__.py`
  - `src/render/worker/__init__.py`
  - `src/render/projections/__init__.py`
  - `tests/unit/render/test_f01_package_layout.py`
  - `docs/delivery-evidence/f-01/report.md`
- dependsOn: CP1-CONTRACT-BINDING, CP2A-LAYOUT
- resourceLocks: `LOCK-SRC-RENDER`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
- acceptance:
  - requirement: tạo gói `render` và 6 gói con chỉ có docstring; test dùng `ast` và `pathlib` quét mọi `src/render/**/*.py`: import được `render` từ root `src/`; không có `import src.` hay `from src.`; không import `creative`, `voice`, `catalog`, `ingestion`, `source_ingestion`, `psycopg`, `temporalio`, `pydantic`, `socket`, `subprocess`, `os`, `shutil`, `tempfile`, `urllib.request`, `http.client`, `controlplane.infrastructure`, `controlplane.ui`, `controlplane.api`, module `controlplane.config` hay module con của nó; không có lời gọi thuộc tính `unlink`, `rmdir`, `rmtree`, `remove`, `rename`, `truncate`; không có hàm tên bắt đầu bằng `delete_`, `cleanup_`, `remove_`; không có thư mục `storage`, `orchestration`, `ui`, `config` dưới `src/render`; test vẫn đúng khi các slice sau thêm tệp.
  - instrument: `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider`
  - counterexample: dùng `from src.render`; import `subprocess` để chạy FFmpeg; hàm `cleanup_outputs`; dựng `src/render/orchestration` trùng G.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider`
- coveredIds: không

### F-02: Preset revision và bộ năm preset (CT-RND-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/preset.py`
  - `tests/unit/render/test_f02_preset_revision.py`
  - `docs/delivery-evidence/f-02/report.md`
- dependsOn: F-01
- resourceLocks: `LOCK-F-02`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
- acceptance:
  - requirement: `RenderPresetRevision` frozen gồm `preset_key`, `revision` (integer ≥ 1, không nhận bool) và các phần CT-RND-001: `visual_rhythm`, `layout_rules`, `thumbnail_overlay_style`, `typography_karaoke_style`, `hook_treatment`, `mix_rules`, `color_effect_rules`, `output_profile_ref`, `fallback_constraints`, `compatibility_requirements`, `preset_fingerprint`; thiếu phần nào → lỗi kèm `field`. `preset_fingerprint` tính bằng `controlplane.application.idempotency.canonicalization.request_hash` trên mọi trường trừ chính nó; không đổi khi đổi thứ tự khóa, đổi khi đổi bất kỳ trường nào; `verify_preset_fingerprint` ném lỗi khi lệch. `PresetCatalog` bất biến: `add_revision` trả catalog mới, không ghi đè bản cũ; `resolve_preset(catalog, preset_key, revision=None)` xác định (không chỉ định revision thì lấy cao nhất; không có → `preset_not_found`); `is_complete(catalog)` chỉ True khi có đúng 5 `preset_key` khác nhau, ngược lại False kèm `preset_count_not_five`. Test dựng 5 preset `fixture-preset-1..5` test-only (GIẢ ĐỊNH); không tên preset, style hay hằng độ phân giải trong mã.
  - instrument: `python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider`
  - counterexample: sửa preset tại chỗ; fingerprint không đổi khi đổi một phần; catalog 6 preset vẫn complete; style đặt cứng trong mã; resolve không xác định.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider`
- coveredIds: CT-RND-001, `docs/10-test-strategy.md` §12.6 (năm preset resolve deterministic)

### F-03: Validator RenderPackage theo binding (CT-RND-002)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/package_contract.py`
  - `tests/unit/render/test_f03_render_package_contract.py`
  - `docs/delivery-evidence/f-03/report.md`
- dependsOn: F-01
- resourceLocks: `LOCK-F-03`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
- acceptance:
  - requirement: hằng đặc tả 19 trường `RenderPackage` trong mã (tên, kiểu, `required`, `forbidden_fields` `shell_command` và `arbitrary_url`); test so hằng với binding JSON; `validate_render_package_payload(payload)` trả `RenderPackageRecord` frozen hoặc ném `ContractViolation` có `code` và `field`; chạy đủ case fixture `f-render-package`: valid; `missing_hook_placement` → `missing_required` field `hook_placement`; `input_artifacts_as_string` → `wrong_type` field `input_artifacts`; `ai_supplied_shell_command` → `forbidden_field` field `shell_command`; từ chối `shell_command` và `arbitrary_url` ở mọi cấp lồng (kể cả trong `materialization_manifest`, `timeline`); mỗi phần tử `input_artifacts` có `artifact_version_id`, `sha256` (64 hex thường), `size_bytes` (integer không phải bool, không âm), `media_type`; `package_fingerprint` đúng định dạng sha256; `language_validation_refs` là mảng chuỗi; trường lạ bị bỏ qua; payload đầu vào không bị sửa.
  - instrument: `python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider`
  - counterexample: chấp nhận `shell_command` lồng trong `materialization_manifest`; `size_bytes` kiểu bool hợp lệ; hash chữ hoa hợp lệ; hằng lệch binding mà test vẫn xanh.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider`
- coveredIds: CT-RND-002 (schema), TST-SEC-INV-020 (phía F)

### F-04: Fingerprint package bất biến (CT-RND-002, acceptance §8 mục 1)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/package_fingerprint.py`
  - `tests/unit/render/test_f04_package_fingerprint.py`
  - `docs/delivery-evidence/f-04/report.md`
- dependsOn: F-03
- resourceLocks: `LOCK-F-04`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
- acceptance:
  - requirement: `compute_package_fingerprint(record)` bằng `controlplane.application.idempotency.canonicalization.request_hash` trên mọi trường đã biết của `RenderPackageRecord` trừ `package_fingerprint` và `render_package_id`; `input_artifacts` và `language_validation_refs` được sắp theo khóa ổn định (`artifact_version_id`, chuỗi) trước khi băm, còn `timeline.segments` giữ thứ tự (quyết định D8); đổi một `sha256`, `size_bytes`, `preset_revision_ref`, `output_profile_revision` hay `word_timing_ref` thì fingerprint đổi; đổi thứ tự khóa dict hoặc thứ tự `input_artifacts` thì không đổi; `verify_package_fingerprint(record)` ném `package_fingerprint_mismatch` khi `package_fingerprint` không khớp; `RenderPackageRecord` frozen, gán lại trường ném lỗi; fingerprint trong fixture valid do CP1 đặt tay nên test tự tính lại và không đòi khớp giá trị đó.
  - instrument: `python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider`
  - counterexample: fingerprint không đổi khi đổi hash input; fingerprint phụ thuộc thứ tự khóa dict; package bị sửa tại chỗ sau khi resolve.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider`
- coveredIds: CT-RND-002, acceptance §8 mục 1

### F-05: Resolve render package từ refs đã khóa (CT-RND-002)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/resolve_package.py`
  - `src/render/ports/inputs.py`
  - `tests/unit/render/test_f05_resolve_package.py`
  - `docs/delivery-evidence/f-05/report.md`
- dependsOn: F-03, F-04
- resourceLocks: `LOCK-F-05`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: `ports/inputs.py` khai báo DTO frozen F-local `ResolveInputs` (snapshot, script, plan, preset revision, voice, word timing, language validation refs, output metadata revision, output profile revision, timeline, hook placement, mix plan, allowed fallbacks, output path ref) và `ResolvedAsset` (`artifact_version_id`, `sha256`, `size_bytes`, `media_type`, `role`), cùng Protocol `PlanAssetPort` (tập asset ref ProductionPlan cho phép) và `ArtifactInfoPort`; `resolve_render_package(inputs, plan_assets)` dựng `RenderPackageRecord` hợp lệ theo F-03 với `package_fingerprint` theo F-04 và `render_package_id` xác định bằng `uuid.uuid5` trên fingerprint; mọi asset phải nằm trong tập của plan hoặc `allowed_fallbacks`, ngoài ra → `asset_outside_plan_or_fallback`; không có trường văn bản script, caption hay URL do F tự sinh; gọi lặp cùng input trả cùng package và cùng id; input thiếu → lỗi kèm `field`; `materialization_manifest` chỉ nhận ref cục bộ do I cấp, không chuỗi đường dẫn tự do.
  - instrument: `python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider`
  - counterexample: F thay asset khác ngoài fallback; package chứa URL; hai lần resolve cho hai id khác; F tự viết lại caption.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider`
- coveredIds: CT-RND-002, acceptance §8 mục 6 (phía resolve)

### F-06: Điều kiện hook, thumbnail, voice, timing, timeline (CT-RND-003 số 1–4 và 6)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/preconditions_media.py`
  - `tests/unit/render/test_f06_preconditions_hooks_timeline.py`
  - `docs/delivery-evidence/f-06/report.md`
- dependsOn: F-03
- resourceLocks: `LOCK-F-06`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
- acceptance:
  - requirement: `Finding` frozen (`condition`, `code`, `field`); `check_hook_preconditions(record)` trả danh sách finding theo thứ tự cố định: `visual_hook_missing`, `audio_hook_missing`, `thumbnail_missing`, `thumbnail_outside_hook_range` (time range thumbnail phải nằm trong time range hook, biên bao gồm; không hằng 0–3 giây: test hook 0–8000 với thumbnail 5000–6000 hợp lệ, hook 0–3000 với thumbnail 2500–3500 sai), `time_range_invalid` (start không nhỏ hơn end, âm, bool); `check_voice_timing_binding(record, voice_info, timing_info)` với DTO theo `VoiceTrackResult` và `WordTiming` của binding `d-e-f-voice-timing`: thiếu ref → `voice_missing` hoặc `word_timing_missing`; `script_fingerprint` hoặc `voice_hash` lệch giữa package, voice và timing → `voice_timing_binding_mismatch` (`TST-MEDIA-INV-007` phía F); `check_timeline_coverage(timeline)` yêu cầu mọi segment có ít nhất một `visual_asset_refs` (thiếu → `timeline_segment_without_visual`), segment có start không nhỏ hơn end → lỗi; `segments` rỗng như fixture hợp lệ; hàm trả mọi finding, không dừng ở lỗi đầu.
  - instrument: `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider`
  - counterexample: thumbnail 0–3 giây cố định; thiếu audio hook vẫn qua; voice đổi mà timing cũ vẫn chấp nhận; segment không có visual asset vẫn qua.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider`
- coveredIds: CT-RND-003 số 1–4 và 6, TST-MEDIA-INV-007 (phía F)

### F-07: Điều kiện artifact đã verify, output path, bằng chứng tiếng Anh, tool (CT-RND-003 số 5, 7, 8, 9)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/preconditions_artifacts.py`
  - `tests/unit/render/test_f07_preconditions_artifacts_language.py`
  - `docs/delivery-evidence/f-07/report.md`
- dependsOn: F-03
- resourceLocks: `LOCK-F-07`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: khai báo kiểu `Finding` tương đương F-06 trong module này (không import module của slice khác); `check_artifacts_verified(record, verified)` với `verified` ánh xạ `artifact_version_id` sang (`sha256`, `size_bytes`, `ArtifactLocationState` của controlplane): thiếu hoặc state khác `VERIFIED` → `artifact_not_verified`, hash lệch → `artifact_hash_mismatch`, size lệch → `artifact_size_mismatch`; `voice_artifact_ref` và `word_timing_ref` phải có trong `input_artifacts` (`required_artifact_not_in_inputs`); `check_output_path(record, issued_paths)`: ref chưa được I cấp → `output_path_not_issued`; đường dẫn đã cấp phải nằm trong staging root sau chuẩn hóa từ vựng bằng `PureWindowsPath` (từ chối `..`, đường dẫn tuyệt đối khác ổ, UNC, tên thiết bị reserved, ký tự điều khiển, scheme dạng `://`) → `output_path_outside_staging_root`; kiểm symlink thật thuộc I và CP7; `check_language_evidence(record, evidence_by_ref, policy)`: `language_validation_refs` rỗng → `language_evidence_missing`, ref không resolve → `language_evidence_unresolved`, `script_fingerprint`, `voice_hash`, `subtitle_text_hash` hoặc `output_metadata_revision` lệch → `language_evidence_revision_mismatch`, locale báo cáo khác `required_language` của policy → `language_mismatch`; policy None → `INPUT_NOT_READY`; trường `language` tự khai không được xem là bằng chứng (`TST-QC-INV-019`); `check_preset_tool_compat(preset, capability)` so `compatibility_requirements` (`required_filters`, `required_encoders`, GIẢ ĐỊNH) với `ToolCapability` frozen; thiếu → `tool_capability_incompatible`, capability None → `INPUT_NOT_READY`.
  - instrument: `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider`
  - counterexample: artifact `AVAILABLE_UNVERIFIED` vẫn qua; đường dẫn `..\\x` thoát staging root; metadata `language=en` thay cho evidence; evidence của voice cũ vẫn hợp lệ; thiếu policy mà vẫn pass.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider`
- coveredIds: TST-INT-INV-008 (phía F), TST-QC-INV-019 (phía F), TST-SEC-INV-020 (phía F), CT-RND-003 số 5, 7, 8, 9, CT-RND-006 (phía F: kiểm path do I cấp)

### F-08: ValidateRenderPackage tổng hợp, fail sớm (CT-RND-003)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/validate_package.py`
  - `tests/unit/render/test_f08_validate_package.py`
  - `docs/delivery-evidence/f-08/report.md`
- dependsOn: F-06, F-07
- resourceLocks: `LOCK-F-08`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
- acceptance:
  - requirement: `validate_render_package(record, context)` chạy các kiểm tra của F-06 và F-07, trả `PackageValidationReport` frozen (`package_fingerprint`, `findings` sắp theo số điều kiện CT-RND-003 từ 1 đến 9 rồi theo mã, `passed`, `report_id` bằng `request_hash`); thiếu một phần `context` (policy, evidence, danh sách verified) → finding `INPUT_NOT_READY`, không bao giờ pass; `require_valid_package(report)` ném `PackageNotRenderable` mang report; test dùng `FakeRenderer` đếm lượt gọi để chứng minh package lỗi thì 0 lượt gọi renderer; mỗi điều kiện thiếu cho đúng một finding, nhiều điều kiện cùng thiếu cho nhiều finding.
  - instrument: `python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider`
  - counterexample: package thiếu hook vẫn gọi renderer; chỉ báo lỗi đầu tiên; context thiếu mà report pass; report không xác định thứ tự.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider`
- coveredIds: CT-RND-003, TST-INT-INV-008 (phía F)

### F-09: Kế hoạch karaoke và văn bản ASS (CT-SUB-001 phía consumer, CT-RND-002 `subtitle_config`)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/karaoke_plan.py`
  - `tests/unit/render/test_f09_karaoke_plan.py`
  - `docs/delivery-evidence/f-09/report.md`
- dependsOn: F-01, F-02
- resourceLocks: `LOCK-F-09`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
  - `docs/parallel-delivery/bindings/f-render-package.json`
- acceptance:
  - requirement: `parse_word_timing(payload)` kiểm lại `WordTiming` phía consumer: hằng trường so với binding JSON, chạy đủ case fixture (`words_out_of_order` và `word_beyond_voice_duration` → `constraint_violation` field `words`; `missing_voice_hash` → `missing_required`; case valid), mỗi từ có `start_ms`, `end_ms` integer không bool, `0 <= start_ms < end_ms`, từ sau không bắt đầu sớm hơn từ trước kết thúc, `end_ms <= voice_duration_ms` khi có; `build_karaoke_plan(words, typography, safe_area, profile)` trả `KaraokePlan` frozen gồm các dòng chữ chia theo `max_words_per_line` và `max_chars_per_line` của typography preset và mốc highlight từng từ; typography, safe area, kích thước `PlayRes` (từ output profile) là input, thiếu → `INPUT_NOT_READY`; `render_ass(plan)` sinh văn bản ASS xác định (`[Script Info]`, `[V4+ Styles]`, `[Events]`): mỗi từ có thẻ karaoke `{\k}` với N là centisecond tính từ hiệu của mốc đã làm tròn (không trôi sai số tích lũy), khoảng trống giữa hai từ mã hóa bằng thẻ `\k` rỗng; văn bản từ được thoát để `{`, `}`, `\`, xuống dòng và ký tự điều khiển không chèn được thẻ override; cùng input cho cùng văn bản; không hằng font, màu hay kích thước trong mã.
  - instrument: `python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider`
  - counterexample: từ chứa `{\an8}` chèn được override; tổng thẻ `\k` lệch mốc cuối do làm tròn từng từ; hai từ chồng lấn vẫn được chấp nhận; font đặt cứng trong mã.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider`
- coveredIds: CT-SUB-001 (phía F), CT-QC-001 `KARAOKE_TIMING_VALID` (đầu vào), acceptance §8 mục 4 (phía dựng)

### F-10: Đặc tả lệnh render có cấu trúc, không shell (CT-RND-004)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/render_command.py`
  - `tests/unit/render/test_f10_render_command_spec.py`
  - `docs/delivery-evidence/f-10/report.md`
- dependsOn: F-02, F-03, F-09
- resourceLocks: `LOCK-F-10`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
- acceptance:
  - requirement: `OutputProfile` frozen (width, height, fps, video_codec, audio_codec, container, pixel_format, encoder, bitrate tùy chọn; mọi trường là input, thiếu → `INPUT_NOT_READY`; giá trị 1080x1920, 30fps, H.264, AAC chỉ nằm trong fixture test-only); `build_render_command(record, preset, profile, ass_ref, tool_identity, materialized)` trả `RenderCommandSpec` frozen gồm `argv` (tuple chuỗi), `redacted_argv` (đường dẫn thay bằng token), `spec_fingerprint` bằng `request_hash`, `tool_identity`; đường dẫn chỉ lấy từ ref cục bộ trong `materialization_manifest` và staging root; mọi phần tử argv có ký tự `;`, `|`, `&`, `<`, `>`, backtick, dấu đô la, xuống dòng, scheme `://` hay `..` → `unsafe_argument`; filter graph dựng từ các phần có cấu trúc với tham số số đã kiểm; chữ phụ đề chỉ đi qua tệp ASS, không chèn trực tiếp; `build_thumbnail_command` chọn thời điểm trích ảnh nằm trong `thumbnail_time_range`; spec không có khóa `shell`, không có chuỗi lệnh nguyên; canary secret đặt trong metadata đầu vào không xuất hiện trong `redacted_argv`, `repr`, dict hay JSON của spec (`TST-SEC-INV-012`); asset ngoài `materialization_manifest` bị từ chối (F không đổi media ngoài fallback).
  - instrument: `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider`
  - counterexample: title chứa `; rm -rf` lọt vào argv; URL tùy ý làm input; spec đặt cứng 1920x1080; canary lộ trong redacted_argv.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider`
- coveredIds: CT-RND-004, TST-SEC-INV-012, TST-SEC-INV-020 (phía F), acceptance §8 mục 6

### F-11: RenderAttempt, receipt và reconcile OUTCOME_UNKNOWN (CT-RND-004, CT-STATE-011)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/render_attempt.py`
  - `tests/unit/render/test_f11_render_attempt.py`
  - `docs/delivery-evidence/f-11/report.md`
- dependsOn: F-10
- resourceLocks: `LOCK-F-11`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: `RenderAttempt` frozen đủ trường CT-RND-004 (`render_attempt_id`, `package_fingerprint`, `output_artifact_ref`, tool và build version, started và finished do tham số truyền vào, `wall_time_ms`, metrics CPU và GPU, `peak_disk_bytes`, command spec đã redacted, warnings, `receipt_state` kiểu `controlplane.domain.statemachine.OperationState`, `receipt_ref`, `revision`); `start_attempt`, `succeed_attempt`, `fail_attempt`, `mark_outcome_unknown` đi qua `transition_operation` (PREPARED → STARTED → SUCCEEDED, FAILED hoặc OUTCOME_UNKNOWN), cạnh cấm ném `ForbiddenTransitionError`, `RevisionConflictError` khi sai expected revision; mỗi attempt có `output_artifact_ref` riêng, attempt mới không ghi đè attempt cũ; `reconcile_attempt(attempt, probe)` chỉ cho `OUTCOME_UNKNOWN` với `ProbeEvidence` (tệp tồn tại, sha256, phát được) và `ReconciliationEvidence`: đủ và khớp → SUCCEEDED, thiếu hoặc hỏng → FAILED, không kết luận được → vẫn OUTCOME_UNKNOWN; `can_retry_directly(attempt)` luôn False với OUTCOME_UNKNOWN (retry chỉ bằng attempt mới sau reconcile); lỗi được redact (canary secret và đường dẫn tuyệt đối không còn); attempt không có trường hay hàm `completed`.
  - instrument: `python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider`
  - counterexample: retry trực tiếp từ OUTCOME_UNKNOWN; attempt mới ghi đè output cũ; terminal mở lại STARTED; lỗi chứa canary; render thành công bị coi là video hoàn thành.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider`
- coveredIds: CT-RND-004, CT-STATE-011, TST-SEC-INV-012

### F-12: QualityReport, nhóm gate và kết luận pass (CT-QC-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/quality_report.py`
  - `tests/unit/render/test_f12_quality_report.py`
  - `docs/delivery-evidence/f-12/report.md`
- dependsOn: F-01
- resourceLocks: `LOCK-F-12`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
- acceptance:
  - requirement: `GateName` (StrEnum đúng 13 gate: `FILE_PLAYABLE`, `DURATION_RANGE`, `VISUAL_HOOK_PRESENT`, `AUDIO_HOOK_PRESENT`, `THUMBNAIL_PRESENT`, `SUBTITLE_BURNED_IN`, `KARAOKE_TIMING_VALID`, `VOICE_AUDIBLE`, `ENGLISH_OUTPUT_VALID`, `OUTPUT_PROFILE_VALID`, `INFERENCE_DISCLOSURE_PRESENT`, `VISUAL_CONTINUITY`, `AUDIO_MIX_QUALITY`), `GateKind` (`hard`, `hard_conditional`, `warning`) đúng bảng CT-QC-001, `GateStatus` (`passed`, `failed`, `not_applicable`, `not_evaluated`); `GateResult` frozen (gate, status, evidence_ref hoặc time_range, measured_value, `threshold_revision`, reason); `QualityPolicy` frozen (revision, ngưỡng dạng ánh xạ); `build_quality_report(results, applicability)` trả `QualityReport` frozen có `report_id` bằng `request_hash`; `passed` chỉ True khi mọi gate hard đều `passed`, gate `hard_conditional` chỉ tính khi áp dụng, thiếu kết quả của bất kỳ gate hard nào → False; gate warning không bao giờ làm `passed` thành False; warning thiếu ngưỡng → `not_evaluated` kèm `INPUT_NOT_READY`; gate trùng hay tên lạ → lỗi.
  - instrument: `python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider`
  - counterexample: report pass khi thiếu một hard gate; warning làm fail; disclosure không áp dụng vẫn bị tính; gate trùng được chấp nhận.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider`
- coveredIds: CT-QC-001, CT-QC-002

### F-13: Gate kỹ thuật của output (CT-QC-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/technical_gates.py`
  - `src/render/ports/output_probe.py`
  - `tests/unit/render/test_f13_technical_gates.py`
  - `docs/delivery-evidence/f-13/report.md`
- dependsOn: F-12
- resourceLocks: `LOCK-F-13`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
- acceptance:
  - requirement: `OutputProbePort.probe(output_ref)` (Protocol, fake trong test) trả `OutputMeasurements` frozen (`decodable`, `duration_ms`, width, height, fps, video_codec, audio_codec, container, `has_audio_stream`, mức âm thanh, danh sách lỗi âm thanh nghiêm trọng); các hàm gate trả `GateResult` theo F-12 (khai báo kiểu tương đương trong module này, không import slice khác): `FILE_PLAYABLE` (không đọc được hoặc thiếu số đo → failed); `DURATION_RANGE` theo `duration_range_ms` của policy, hai đầu bao gồm, test biên 60999 (failed), 61000, 70000 (passed), 70001 (failed), giá trị không phải integer hoặc là bool hoặc NaN → failed; `OUTPUT_PROFILE_VALID` so container, codec, kích thước, fps với `expected_profile` (dict input): output 1920x1080 ngang khi profile dọc → failed (RED oracle của capability F); `VOICE_AUDIBLE` (có luồng audio, mức trên `min_voice_level` của policy, không có lỗi nghiêm trọng); thiếu ngưỡng hoặc profile → `not_evaluated` kèm `INPUT_NOT_READY`; không hằng 61, 70, 1080, 1920 hay 30 trong mã.
  - instrument: `python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider`
  - counterexample: video 70001 ms được pass; output ngang pass cho profile dọc; hằng 61000 đặt cứng trong mã; số đo thiếu mà gate pass.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider`
- coveredIds: CT-QC-001 (`FILE_PLAYABLE`, `DURATION_RANGE`, `OUTPUT_PROFILE_VALID`, `VOICE_AUDIBLE`), acceptance §8 mục 5

### F-14: Gate nội dung của output và bằng chứng tiếng Anh (CT-QC-001, CT-QC-002)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/content_gates.py`
  - `src/render/ports/output_inspector.py`
  - `tests/unit/render/test_f14_content_gates.py`
  - `docs/delivery-evidence/f-14/report.md`
- dependsOn: F-12
- resourceLocks: `LOCK-F-14`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- acceptance:
  - requirement: `OutputInspectorPort.inspect(output_ref, package)` (Protocol, fake trong test) trả evidence frozen: hook visual (khoảng thời gian, độ tương đồng), hook audio (mức âm thanh trong vùng hook), thumbnail (thời điểm, asset tham chiếu), phụ đề burn-in (số khung có chữ), karaoke (thời điểm highlight quan sát từng từ), bằng chứng ngôn ngữ (script_fingerprint, voice_hash, subtitle_text_hash, output_metadata_revision, locale của script, voice, subtitle, title, hashtag), disclosure hiển thị; các hàm gate: `VISUAL_HOOK_PRESENT`, `AUDIO_HOOK_PRESENT` (nằm trong `hook_time_range` và đạt ngưỡng policy), `THUMBNAIL_PRESENT` (thời điểm nằm trong `hook_time_range` của package, không hằng 0–3 giây), `SUBTITLE_BURNED_IN`, `KARAOKE_TIMING_VALID` (lệch quan sát so với mốc `WordTiming` không quá `tolerance_ms` của policy; thiếu → `not_evaluated`), `ENGLISH_OUTPUT_VALID` (cả năm thành phần phải có evidence khớp exact revision với package và locale bằng `required_language` của policy; chỉ metadata `language=en` tự khai → failed, `TST-QC-INV-019`), `INFERENCE_DISCLOSURE_PRESENT` (`not_applicable` khi không có segment `inference` hay `creative_hypothesis`; ngược lại mọi segment phải có disclosure hiển thị).
  - instrument: `python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider`
  - counterexample: thumbnail ngoài vùng hook vẫn pass; evidence voice cũ vẫn pass; chỉ `language=en` tự khai vẫn pass; segment suy luận không có disclosure vẫn pass; karaoke lệch quá `tolerance_ms` vẫn pass.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider`
- coveredIds: CT-QC-001, CT-QC-002, TST-QC-INV-019, acceptance §8 mục 3, 4, 7

### F-15: VideoOutput, output ready và bốn mốc riêng (CT-RND-005)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/domain/output_ready.py`
  - `tests/unit/render/test_f15_output_ready.py`
  - `docs/delivery-evidence/f-15/report.md`
- dependsOn: F-11, F-12
- resourceLocks: `LOCK-F-15`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
- acceptance:
  - requirement: `VideoOutput` frozen (`video_output_id`, `output_artifact_ref`, `output_sha256`, `quality_report_ref`, `render_attempt_ref`, `package_fingerprint`, revision output metadata); `evaluate_output_ready(attempt, observed_sha256, report, refs_committed, grant_valid)` theo CT-RND-005: chỉ ready khi receipt `SUCCEEDED`, output tồn tại và hash khớp, mọi hard gate đạt (`report.passed`), report và artifact refs đã commit, grant còn hợp lệ; ngược lại `NotReady` kèm danh sách lý do; `create_video_output` ném `quality_not_passed` khi QC fail; `MilestoneState` gồm bốn mốc độc lập `render_succeeded`, `qc_passed`, `upload_verified` (fact do I cung cấp), `completion_committed` (fact do G cung cấp); QC pass mà `upload_verified` sai → output ready nhưng `completion_eligible` False (`TST-E2E-INV-009`); render thành công mà QC fail → `render_succeeded` True, `qc_passed` False, không output ready (acceptance §8 mục 2); module không có hàm tạo completion, ledger, xóa hay cleanup.
  - instrument: `python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider`
  - counterexample: QC fail vẫn tạo `VideoOutput`; hash lệch vẫn ready; grant hết hạn vẫn ready; upload chưa verify vẫn eligible; render success bị tính là completion.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider`
- coveredIds: CT-RND-005, TST-E2E-INV-009, acceptance §8 mục 2

### F-16: Port lưu trữ, UoW in-memory, outbox và event của F
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/ports/repositories.py`
  - `src/render/adapters/memory.py`
  - `src/render/domain/events.py`
  - `tests/unit/render/test_f16_ports_memory_events.py`
  - `docs/delivery-evidence/f-16/report.md`
- dependsOn: F-11, F-12
- resourceLocks: `LOCK-F-16`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- acceptance:
  - requirement: Protocol `RenderRepository` append-only (`append(kind, key, revision, record)`, `latest`, `revisions`; revision mới không ghi đè, không xóa bản cũ; `package_fingerprint`, `render_attempt_id`, `output_artifact_ref` duy nhất); UoW in-memory implement `controlplane.domain.interfaces.uow.IUnitOfWork` (đọc chữ ký thật trong tệp; rollback hủy mọi ghi kể cả outbox); outbox implement `controlplane.domain.interfaces.outbox.IOutboxWriter` dedup theo `deduplication_id`; `domain/events.py` dựng `RenderCompleted` và `OutputQualityChecked` bằng `controlplane.domain.events.contracts.DomainEvent` và `ensure_safe_event_payload`, payload chỉ chứa ref, hash, revision và tóm tắt trạng thái gate (không byte video, argv, đường dẫn tuyệt đối hay secret); builder `RenderCompleted` từ chối khi attempt không `SUCCEEDED`; `OutputQualityChecked` được phát cả khi QC fail; envelope khớp mọi case valid và invalid có trong fixture `domain-event-envelope` (đọc tệp để chạy hết các case); canary secret không lọt vào event.
  - instrument: `python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider`
  - counterexample: tạo `IUnitOfWork`, `IOutboxWriter` hay `DomainEvent` mới; ghi đè attempt cũ; rollback để lại outbox; `RenderCompleted` cho attempt lỗi; event chứa argv.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider`
- coveredIds: CT-EVT-002, CT-EVT-003 (phía F), TST-CTR-INV-002, TST-SEC-INV-012

### F-17: Command ResolveRenderPackage và ValidateRenderPackage (integration)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/application/package_pipeline.py`
  - `tests/integration/render/test_f17_resolve_validate_pipeline.py`
  - `docs/delivery-evidence/f-17/report.md`
- dependsOn: F-05, F-08, F-16
- resourceLocks: `LOCK-F-17`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: command `ResolveRenderPackage` (F-05, lưu package bất biến qua F-16) và `ValidateRenderPackage` (F-08, lưu `PackageValidationReport`), mỗi command một UoW gồm bản ghi, receipt `OperationState` và dấu vết; idempotency theo `operation_key` với `request_hash`: cùng key và payload → trả receipt cũ, khác payload → `IDEMPOTENCY_CONFLICT` bằng `ProblemDetail` (`TST-CTR-INV-001`); `ExecutionGrant` hết hạn hay generation cũ → từ chối, không ghi; package lỗi (thiếu hook, audio hook, thumbnail trong vùng hook, voice, timing, artifact chưa verify, output path ngoài staging root, evidence tiếng Anh lệch) → report fail, `FakeRenderer` 0 lượt gọi; đổi `script_fingerprint` hoặc `voice_hash` sau khi có package → validate fail (`TST-MEDIA-INV-007`); resolve không ghi bảng của phân hệ khác.
  - instrument: `python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider`
  - counterexample: gửi lặp tạo package thứ hai; validate sau khi hash input đổi vẫn pass; ghi ngoài UoW; package lỗi vẫn tới renderer.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider`
- coveredIds: TST-CTR-INV-001, TST-INT-INV-008, TST-MEDIA-INV-007, CT-RND-002, CT-RND-003, TST-E2E-001 (đoạn resolve và validate)

### F-18: Command RenderVideo, lease GPU và reconcile (integration)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/application/render_video.py`
  - `src/render/ports/renderer.py`
  - `src/render/ports/lease.py`
  - `src/render/adapters/fake_renderer.py`
  - `tests/integration/render/test_f18_render_video_pipeline.py`
  - `docs/delivery-evidence/f-18/report.md`
- dependsOn: F-10, F-11, F-13, F-16, F-17
- resourceLocks: `LOCK-F-18`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: `RendererPort.run(spec)` trả `RendererOutcome` (trạng thái, output ref, sha256, metrics, lỗi), `GpuLeasePort` (acquire, release, cho `LOCK-DESKTOP-GPU`) và `FakeRenderer` tiêm lỗi trước, trong, sau side effect; command `RenderVideo` yêu cầu report validate pass đúng `package_fingerprint` (nếu không → `package_not_validated`), giữ lease và luôn trả lease khi thành công, lỗi hay ngoại lệ; thành công → attempt SUCCEEDED và outbox `RenderCompleted`; crash trước hoặc trong side effect → FAILED, không output ready; timeout sau side effect trước receipt → `OUTCOME_UNKNOWN`, `ReconcileRender` dùng `OutputProbePort` của F-13 trước mọi retry, retry trực tiếp bị từ chối; retry sau reconcile FAILED tạo attempt mới với output artifact mới, attempt cũ không đổi; tệp partial hoặc hash lệch → không ready, không event; không có lần xóa nào trong fake lưu trữ; canary secret trong lỗi renderer không có trong attempt, event, `ProblemDetail`.
  - instrument: `python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider`
  - counterexample: lease không trả khi renderer ném lỗi; retry trực tiếp từ OUTCOME_UNKNOWN; attempt mới ghi đè output cũ; xóa tệp partial; render package chưa validate.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider`
- coveredIds: CT-RND-004, CT-STATE-011, TST-SEC-INV-012, TST-E2E-001 (đoạn render), TST-CTR-INV-001

### F-19: Command InspectOutput và output ready (integration)
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/application/inspect_output.py`
  - `tests/integration/render/test_f19_inspect_output_pipeline.py`
  - `docs/delivery-evidence/f-19/report.md`
- dependsOn: F-13, F-14, F-15, F-16, F-18
- resourceLocks: `LOCK-F-19`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
- acceptance:
  - requirement: command `InspectOutput` dùng `OutputProbePort` và `OutputInspectorPort` giả, chạy gate F-13 và F-14 cùng gate warning, dựng `QualityReport` (F-12) và lưu trong một UoW cùng receipt và outbox `OutputQualityChecked` (phát cả khi fail); command `PrepareOutputReady` dùng F-15: QC pass và đủ điều kiện → tạo `VideoOutput` và trả output ready cho G, QC fail → không `VideoOutput`; render kỹ thuật thành công nhưng QC fail không tạo video hoàn thành (acceptance §8 mục 2); QC pass nhưng `upload_verified` sai → ready và `completion_eligible` False, F không xóa gì (`TST-E2E-INV-009`); các kịch bản fail: video 61000 ms pass và 70001 ms fail, thumbnail ngoài vùng hook, thiếu phụ đề burn-in, karaoke lệch quá `tolerance_ms`, evidence tiếng Anh lệch revision, output ngang; idempotent theo `operation_key`; grant cũ → `stale`, không ghi.
  - instrument: `python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider`
  - counterexample: QC fail vẫn tạo output ready; QC pass tính là completion; phát event chỉ khi pass; ghi report ngoài UoW; xóa local khi upload chưa verify.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider`
- coveredIds: CT-QC-001, CT-RND-005, TST-E2E-INV-009, TST-QC-INV-019, TST-E2E-001 (đoạn QC)

### F-20: Worker activity cho G
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/worker/activity_handler.py`
  - `tests/integration/render/test_f20_worker_activity.py`
  - `docs/delivery-evidence/f-20/report.md`
- dependsOn: F-17, F-18, F-19
- resourceLocks: `LOCK-F-20`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: `handle_activity(request, grant, deps)` nhận `ActivityRequest` (dict theo binding `g-activity-execution`) cùng `controlplane.domain.orchestration.ExecutionGrant` (không tạo lớp grant mới; trường lệch binding ghi vào report và CONV-F-05), gọi command của F-17, F-18, F-19 theo `activity_name` (`resolve_render_package`, `validate_render_package`, `render_video`, `inspect_output`), trả `ActivityResult` với `output_refs`, `metrics`, `warnings`, `problem` đã redact; generation hoặc recovery epoch cũ → disposition `stale`, không commit (`TST-WF-INV-003`); lặp `operation_key` trả kết quả cũ; `activity_name` lạ → problem có cấu trúc; precondition desktop và GPU do G kiểm (`WAITING_CAPABILITY`), F không tự chờ; chỉ chạy đúng activity được yêu cầu, stage sau không tự chạy (`TST-E2E-014`, đoạn F); test `ast` khẳng định handler không import `temporalio`, `controlplane.ui`, `controlplane.api`, `creative`, `voice`, `catalog`.
  - instrument: `python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider`
  - counterexample: generation cũ ghi attempt mới; `ActivityResult` chứa secret; handler đăng ký workflow Temporal trực tiếp; render xong tự chạy inspect.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider`
- coveredIds: CT-WF-003, CT-WF-006 (phía F), TST-WF-INV-003, TST-E2E-014 (đoạn F)

### F-21: Projection truy vết read-only
- kind: `work_package_slice`
- ownedPaths:
  - `src/render/projections/trace_queries.py`
  - `tests/unit/render/test_f21_trace_projection.py`
  - `docs/delivery-evidence/f-21/report.md`
- dependsOn: F-16
- resourceLocks: `LOCK-F-21`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: `trace_render_package`, `trace_attempt`, `trace_quality_report`, `trace_output`: từ output truy ngược attempt → `package_fingerprint` → preset revision, script, plan, voice, word timing, language validation refs, hash từng input artifact, tool và build version, command spec đã redacted, từng gate với evidence; liệt kê lịch sử revision và attempt không ghi đè; hiển thị bốn mốc render, QC, upload, completion riêng; query không gọi renderer hay probe (fake đếm 0 lượt); lọc theo workspace; không lộ secret hay lỗi chưa redact.
  - instrument: `python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider`
  - counterexample: query kích hoạt render; trả output của workspace khác; trace lộ argv chưa redact; gộp bốn mốc thành một cờ.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider`
- coveredIds: CT-RND-004, CT-QC-001 (truy vết), TST-E2E-001 (truy vết ngược từ output)

### F-22: Ma trận test ID và acceptance contract
- kind: `work_package_slice`
- ownedPaths:
  - `tests/unit/render/test_f22_coverage_catalog.py`
  - `docs/delivery-evidence/f-22/report.md`
- dependsOn: F-01, F-02, F-03, F-04, F-05, F-06, F-07, F-08, F-09, F-10, F-11, F-12, F-13, F-14, F-15, F-16, F-17, F-18, F-19, F-20, F-21
- resourceLocks: `LOCK-F-22`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
- acceptance:
  - requirement: test chỉ dùng stdlib đọc docstring của `tests/unit/render/test_f*.py` và `tests/integration/render/test_f*.py` (trừ chính F-22), khẳng định mỗi mã CT-RND-001..CT-RND-006, CT-QC-001, CT-QC-002, TST-MEDIA-INV-007, TST-INT-INV-008, TST-E2E-INV-009, TST-SEC-INV-012, TST-QC-INV-019, TST-SEC-INV-020, TST-E2E-001, TST-E2E-014, TST-CTR-INV-001, TST-CTR-INV-002, TST-WF-INV-003 có trong ít nhất một tệp và tệp đó có ít nhất một hàm `test_`; khẳng định cả 13 tên gate của CT-QC-001 xuất hiện trong test của F-12, F-13 hoặc F-14; không tệp nào dùng mã tiền tố `TST-MED-`, `TST-VOI-`, `TST-RND-`, `TST-EF-`; report ghi bảng ánh xạ từng mục acceptance §8 (1 đến 7) của `docs/09-contracts/08-render-quality-contracts.md` sang slice và test.
  - instrument: `python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider`
  - counterexample: một gate QC không có test trực tiếp; mã chỉ xuất hiện trong F-22; dùng test ID ngoài catalog.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider`
- coveredIds: acceptance §8 mục 1 đến 7 của contract 08
