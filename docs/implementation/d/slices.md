# Danh sách slice — Phân hệ D (IMPL-PLAN-D)

Tài liệu này biên dịch kế hoạch `docs/implementation/d/plan.md` thành 18 work package slice độc lập, kiểm chứng được riêng.

## Quy ước chung

- ownedPaths chỉ trong `src/creative/**`, `tests/unit/creative/**`, `tests/integration/creative/**` và tệp bằng chứng `docs/delivery-evidence/<task-id viết thường>/report.md`.
- Test-first: tạo khung module tối thiểu để import được, chạy test và ghi RED do assertion sai oracle; lỗi import/collection không phải RED hợp lệ; sau đó GREEN.
- Không sửa migration, composition root, lockfile, tests/m2, ui/dist, App.tsx, state machine dùng chung hay control API; không thêm thư viện; không gọi mạng, provider AI hay dịch vụ thật (slice có port AI phải monkeypatch `socket.create_connection` và `socket.getaddrinfo` để ném lỗi trong test).
- Dùng fixture CP1 và fake cho phân hệ khác; tái dùng module controlplane trong plan §4, không dựng bản trùng; không import `controlplane.config.router`, `controlplane.config.adapter`.
- Validator binding: hằng đặc tả trường trong mã; test so hằng với tệp binding JSON để bắt drift và chạy mọi case valid/invalid của fixture đúng `expected_error` (`missing_required`, `wrong_type`, `enum_violation` kèm `field`); `sha256` là 64 ký tự hex thường; `datetime` kiểm RFC3339 bằng `datetime.fromisoformat`; integer không nhận bool; trường lạ bị bỏ qua.
- Không tạo `__init__.py` trong thư mục test; tên tệp test `test_dNN_*.py`; docstring đầu tệp test có dòng `coveredIds:` liệt kê mã CT/TST bao phủ.
- Lệnh python chạy bằng interpreter khoá của lane.

## Khuôn slice

Thứ tự trường bắt buộc trong từng slice:
- Tiêu đề slice dạng D-NN và tên gợi nhớ
- Trường kind là `work_package_slice`
- Danh sách ownedPaths thụt lề 2 dấu cách, mục cuối luôn là report.md
- Trường dependsOn liệt kê slice tiền đề trên một dòng
- Trường resourceLocks
- Danh sách bindingRefs trỏ tệp binding hoặc fixture thực tế
- Khối acceptance với requirement, instrument và counterexample
- Danh sách testCommands với git diff --check và pytest tệp test thuộc ownedPaths
- Trường coveredIds

## Slice

### D-01: Khung gói creative và ranh giới import
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/__init__.py`
  - `src/creative/domain/__init__.py`
  - `src/creative/application/__init__.py`
  - `src/creative/ports/__init__.py`
  - `src/creative/adapters/__init__.py`
  - `src/creative/worker/__init__.py`
  - `src/creative/projections/__init__.py`
  - `tests/unit/creative/test_d01_package_layout.py`
  - `docs/delivery-evidence/d-01/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-SRC-CREATIVE`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
- acceptance:
  - requirement: tạo gói và 6 gói con chỉ có docstring; test dùng `ast`/`pathlib` quét mọi `src/creative/**/*.py`: import được `creative` từ root src/; không `import src.`/`from src.`; không import `source_ingestion`, `ingestion`, `catalog`, `voice`, `render`, `psycopg`, `temporalio`, `pydantic`, `socket`, `urllib.request`, `http.client`, `controlplane.infrastructure`, `controlplane.ui`, `controlplane.api`, module `controlplane.config` hoặc module con của nó; không có thư mục `storage`, `orchestration`, `ui`, `config` dưới `src/creative`.
  - instrument: `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider`
  - counterexample: dùng `from src.creative`; import gói E/F để gọi trực tiếp; import adapter HTTP của J; dựng `src/creative/orchestration` trùng G.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider`
- coveredIds: không

### D-02: ProductionSnapshot bất biến (CT-AI-001)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/snapshot.py`
  - `tests/unit/creative/test_d02_production_snapshot.py`
  - `docs/delivery-evidence/d-02/report.md`
- dependsOn: `D-01`
- resourceLocks: `LOCK-D-02`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- acceptance:
  - requirement: hằng đặc tả trường cấp 1 của `ProductionSnapshot` và validator theo quy ước chung; test so hằng với binding và chạy mọi case fixture. `build_production_snapshot` nhận ref có `ref_type`, `ref_id`, `revision_id` (thiếu `revision_id` → `INPUT_NOT_READY`), production mode, tập `ref_type` nội dung do policy truyền vào, `eligibility_reason` do G/B cấp, batch/job ref, recent variant exclusions; tính `source_set_fingerprint` và `configuration_bundle_fingerprint` bằng `controlplane.application.idempotency.canonicalization.request_hash` trên tập ref đã sắp xếp; trả frozen dataclass đã qua validator. Ref ngoài tập ref nội dung (ví dụ `dedup_observation`, `collected_document`) → `NOT_ELIGIBLE`, không tạo snapshot.
  - instrument: `python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider`
  - counterexample: fingerprint đổi khi đảo thứ tự ref; gán được thuộc tính sau khi tạo; chấp nhận production mode `timeline`; hằng lệch binding mà test vẫn xanh; dùng thực thể `ArticleSnapshot`; quan sát bài trùng tạo snapshot mới.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider`
- coveredIds: CT-AI-001, TST-INT-INV-004 (mức domain), TST-INT-INV-005 (phía D)

### D-03: Biên dữ liệu không tin cậy và resolver ref (CT-AI-000)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/untrusted.py`
  - `src/creative/domain/ref_resolver.py`
  - `tests/unit/creative/test_d03_untrusted_boundary.py`
  - `docs/delivery-evidence/d-03/report.md`
- dependsOn: `D-01`
- resourceLocks: `LOCK-D-03`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- acceptance:
  - requirement: `UntrustedText` frozen mang `trust_class` `untrusted_data` và provenance ref; `PromptEnvelope` tách `instructions` (chỉ từ prompt revision có ref) và `data` (danh sách `UntrustedText`), không có API nối data vào instructions; `RefResolver` kiểm mọi ref do model đề xuất: có trong tập ref cho phép (ref của snapshot hoặc candidate set), cùng workspace, đúng revision, `ref_type` thuộc allowlist; ref sai trả lỗi có cấu trúc với reason `unknown_ref`, `workspace_mismatch`, `revision_mismatch` hoặc `not_allowlisted` và không trả ref. Văn bản trong dữ liệu giả chỉ dẫn hệ thống (ví dụ “ignore previous instructions”, “system:”, yêu cầu gọi tool hay tải URL) không đổi policy, không sinh tool intent, không thêm ref.
  - instrument: `python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider`
  - counterexample: nối nội dung bài vào instructions; chấp nhận ref của workspace khác hoặc revision cũ; tin trường `tool_call` trong output model; dựa vào typed schema thay resolver.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider`
- coveredIds: CT-AI-000, TST-SEC-INV-020

### D-04: Port định tuyến AI, fake adapter và AIInvocationRecord (CT-AI-ROUTE-001, CT-AI-010)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/ports/ai.py`
  - `src/creative/domain/invocation.py`
  - `src/creative/adapters/fake_ai.py`
  - `tests/unit/creative/test_d04_ai_route_invocation.py`
  - `docs/delivery-evidence/d-04/report.md`
- dependsOn: `D-01`, `D-03`
- resourceLocks: `LOCK-D-04`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: Protocol `ProviderRoutePort.resolve(request)` trả decision và `AIInvocationPort.invoke(decision, envelope)`; validator `ProviderRouteRequest`/`ProviderRouteDecision` theo quy ước chung và từ chối decision chứa `forbidden_fields` (`secret_value`, `api_key`, `access_token`, `refresh_token`) ở mọi cấp lồng; `FakeProviderRoute`/`FakeAIAdapter` trả phản hồi định sẵn theo `ai_role`, đếm lượt gọi, không mở mạng; `AIInvocationRecord` frozen ghi role, provider/model/account/project ref, route revision, prompt/config revision, input/output fingerprint sha256, usage, latency, attempt, fallback path, validation result, lỗi đã redact; canary secret đặt trong lỗi của fake không xuất hiện trong `repr`, dict hay JSON của record.
  - instrument: `python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider`
  - counterexample: decision có `api_key` được chấp nhận; record thiếu prompt revision; fake mở socket; record chứa canary.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider`
- coveredIds: CT-AI-010, CT-AI-ROUTE-001, TST-SEC-INV-012

### D-05: ContentAnalysis (CT-AI-002)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/analysis.py`
  - `tests/unit/creative/test_d05_content_analysis.py`
  - `docs/delivery-evidence/d-05/report.md`
- dependsOn: `D-02`, `D-03`
- resourceLocks: `LOCK-D-05`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- acceptance:
  - requirement: `parse_content_analysis(raw, snapshot, resolver)` dựng `ContentAnalysis` frozen có ID/revision, snapshot ref, chủ đề, entities, timeline, locations, facts/claims kèm evidence refs, uncertainties/contradictions, event relation và update context, risk flags, narrative opportunities, media needs, model/prompt trace; output model sai schema, thiếu trường bắt buộc hoặc sai kiểu → `ai_output_schema_violation` kèm field, không chấp nhận một phần; evidence ref không qua resolver D-03 → `hallucinated_ref`; uncertainty giữ nguyên, không thành fact; provenance và `trust_class` giữ nguyên; trường tự đánh giá của model không dùng để quyết định hợp lệ.
  - instrument: `python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cacheprovider`
  - counterexample: thiếu field vẫn lưu analysis; claim không có evidence thành fact; ref bịa được chấp nhận.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cacheprovider`
- coveredIds: CT-AI-002, TST-SEC-INV-020 (phần ref)

### D-06: StoryAngleSet 1–3 góc khác nhau (CT-AI-003)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/angles.py`
  - `tests/unit/creative/test_d06_story_angles.py`
  - `docs/delivery-evidence/d-06/report.md`
- dependsOn: `D-03`, `D-05`
- resourceLocks: `LOCK-D-06`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- acceptance:
  - requirement: `StoryAngle` có angle ID, title, summary, narrative question, focus entities, timeframe, evidence refs, planned inference/creative elements, distinction fingerprint (sha256 trên narrative question, focus entities và timeframe đã chuẩn hoá; không dùng ID, title hay style), suitability và risk flags; `StoryAngleSet` từ chối requested count ngoài 1–3; hai góc cùng distinction fingerprint trong một set → `same_run_angle_duplicate`; góc trùng fingerprint của script gần nhất trong lịch sử truyền vào bị loại; khi mọi góc của set ban đầu đã khai thác thì cho phép sinh set mới; ghi variation policy revision.
  - instrument: `python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider`
  - counterexample: ba góc chỉ khác title/style được chấp nhận; requested count 4; fingerprint dựa trên angle ID.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider`
- coveredIds: CT-AI-003, TST-AI-INV-013 (mức góc kể)

### D-07: Chặn narrative “từ lúc đó đến nay” (CT-AI-005)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/timeline_mode.py`
  - `tests/unit/creative/test_d07_timeline_authorization.py`
  - `docs/delivery-evidence/d-07/report.md`
- dependsOn: `D-02`
- resourceLocks: `LOCK-D-07`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- acceptance:
  - requirement: `authorize_timeline_narrative(snapshot, policy)` chỉ cho phép `from_then_to_now` khi `source_refs` có ref thuộc loại event update đã chấp nhận (tên loại do policy truyền vào; fixture `event_update_accepted`) kèm revision; chỉ có repost, nguồn mới, media mới hoặc article revision → `POLICY_VIOLATION` kèm reason; không tự đổi mode; mode `single_article`, `multi_article_event` không bị ảnh hưởng. CT-CNT-005 chưa có binding (CONV-D-07).
  - instrument: `python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider`
  - counterexample: nguồn mới hoặc repost kích hoạt timeline; tự hạ mode sang `single_article` không ghi quyết định.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider`
- coveredIds: CT-AI-005, TST-CTR-INV-006

### D-08: ScriptVersion, claim_mode và disclosure (CT-AI-004)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/script.py`
  - `tests/unit/creative/test_d08_script_version.py`
  - `docs/delivery-evidence/d-08/report.md`
- dependsOn: `D-03`, `D-05`
- resourceLocks: `LOCK-D-08`
- bindingRefs:
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
- acceptance:
  - requirement: `ScriptVersion` frozen gồm narration segments có thứ tự, `claim_mode` thuộc đúng `source_backed`, `inference`, `creative_hypothesis`, `transition`; `source_backed` phải có source ref qua resolver; `inference` và `creative_hypothesis` phải có disclosure tường minh (test duyệt 100% segment); hook intent, thumbnail transition, scene intents, estimated timing, pronunciation hints, script fingerprint sha256 trên lời dẫn đã chuẩn hoá theo thứ tự segment; thời lượng ước lượng = số từ chia `speech_rate` của language/voice policy; thiếu policy hoặc target range → `INPUT_NOT_READY`; ngoài target range (fixture 61–70 giây) → `duration_out_of_range`; ngôn ngữ theo language policy (fixture `en`); validator xác định, không dùng model làm bên duy nhất xác nhận disclosure/ref; `to_voice_track_inputs()` trả `script_version_id`, `script_fingerprint`, `pronunciation_hints` đúng kiểu trường cùng tên của `VoiceTrackRequest` trong binding.
  - instrument: `python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider`
  - counterexample: segment inference không có disclosure; hằng 140–165 từ; ước lượng 45 giây vẫn hợp lệ; fingerprint đổi khi chỉ đổi ID.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider`
- coveredIds: CT-AI-004, CT-TTS-001 (phía D)

### D-09: Chọn hook, media và âm thanh (CT-AI-006, CT-MED-005)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/asset_selection.py`
  - `tests/unit/creative/test_d09_asset_selection.py`
  - `docs/delivery-evidence/d-09/report.md`
- dependsOn: `D-03`
- resourceLocks: `LOCK-D-09`
- bindingRefs:
  - `docs/parallel-delivery/bindings/c-d-media-candidates.json`
  - `tests/fixtures/contracts/c-d-media-candidates/payloads.json`
- acceptance:
  - requirement: `build_media_candidate_query` trả `MediaCandidateQuery` qua validator binding; `MediaCandidate` đọc từ fixture qua validator; `select_creative_assets` chỉ chọn ref thuộc candidate set đã nhận (resolver D-03), bắt buộc visual hook, audio hook và thumbnail (thiếu → `missing_required_hook`); candidate bị chặn theo safety/rights policy truyền vào bị loại; kết quả có scene-to-media assignments theo thứ tự, music/SFX intents, fallback candidates, rationale, score components và selection fingerprint sha256. Hook/thumbnail candidate (CT-MED-004/006) chưa có binding nên dùng value object D-local và fake (CONV-D-07).
  - instrument: `python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider`
  - counterexample: model đề xuất `media_asset_id` ngoài candidate set được dùng; thiếu audio hook vẫn hợp lệ; bỏ qua safety status.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider`
- coveredIds: CT-AI-006, CT-MED-005 (phía D)

### D-10: ProductionPlan (CT-AI-007)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/production_plan.py`
  - `tests/unit/creative/test_d10_production_plan.py`
  - `docs/delivery-evidence/d-10/report.md`
- dependsOn: `D-08`, `D-09`
- resourceLocks: `LOCK-D-10`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
  - `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- acceptance:
  - requirement: plan ghi exact script version và fingerprint, preset revision ref, timeline/scene list, asset/rendition refs với intended time range (ms nguyên, start < end), visual và audio hook placement, thumbnail placement có time range nằm trọn trong time range hook (không có hằng 0–3 giây), crop/overlay/effect intents, voice profile intent, music/SFX cues, subtitle/karaoke style intent, fallback rules được phép, output metadata ref hoặc requirement, plan fingerprint sha256; mọi khoảng timeline yêu cầu có ít nhất một visual; plan chỉ chứa intent, không có `shell_command`, `arbitrary_url` hay đường dẫn tệp; `to_render_package_inputs()` trả `production_plan_ref`, `script_version_ref`, `hook_placement`, `timeline`, `allowed_fallbacks` đúng kiểu trường cùng tên trong binding `f-render-package`.
  - instrument: `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider`
  - counterexample: thumbnail ngoài vùng hook; plan chứa `shell_command`; khoảng timeline trống; hằng 3000 ms.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider`
- coveredIds: CT-AI-007, CT-RND-003 điều kiện 1–3 (phía D)

### D-11: VariantValidation (CT-AI-008, CT-ORC-012 phía D)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/variant.py`
  - `tests/unit/creative/test_d11_variant_validation.py`
  - `docs/delivery-evidence/d-11/report.md`
- dependsOn: `D-06`, `D-10`
- resourceLocks: `LOCK-D-11`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- acceptance:
  - requirement: `VariantFingerprint` tính từ nội dung thực tế của script, plan và selection cùng các yếu tố khác biệt theo CT-AI-008 bất biến 3 (giọng, âm thanh, hook, thứ tự/chọn media, hiệu ứng, nội dung, cách dẫn, nhạc nền, góc khai thác), không từ seed hay ID; `validate_variant` nhận candidate fingerprints, lịch sử completed và active reservations (kiểu `controlplane.domain.orchestration.VariantReservation`) tại một registry revision, video cùng lượt, variation policy revision, phase `plan` hoặc `output`, reservation ID của chính job; trả kết quả bất biến gồm `valid`, `same_run_angle_distinct`, `exact_duplicate`, yếu tố khác biệt, nearest prior refs, reason codes, input hashes, registry revision, phase; cùng lượt trùng góc → invalid; giữa các lượt exact duplicate hoặc không có yếu tố khác → invalid; loại reservation của chính job khỏi đối chứng nhưng vẫn tính reservation của job khác; phase `output` bắt buộc exact output hash và không dùng lại kết quả phase `plan`; registry revision mới làm kết quả cũ stale. Không gọi AI, không tạo hay release reservation (thuộc G).
  - instrument: `python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider`
  - counterexample: hai biến thể chỉ khác seed được coi là khác; bỏ qua reservation của job khác; dùng validation phase plan để xác nhận output.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider`
- coveredIds: CT-AI-008, TST-AI-INV-013, TST-AI-INV-014, TST-WF-VAR-004 (phía D)

### D-12: OutputMetadata (CT-AI-009)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/domain/output_metadata.py`
  - `tests/unit/creative/test_d12_output_metadata.py`
  - `docs/delivery-evidence/d-12/report.md`
- dependsOn: `D-01`
- resourceLocks: `LOCK-D-12`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: `OutputMetadata` frozen gồm title/caption tiếng Anh, 3–4 hashtag (2 hoặc 5 → lỗi), language, source job/output refs, metadata revision; giữ original display representation; filename-safe representation lấy qua `FilenameSanitizerPort` (storage contract của I, chưa có binding nên port D-local và fake trong test); D không tự đặt quy tắc filename; bản hiển thị gốc không đổi sau sanitize.
  - instrument: `python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider`
  - counterexample: 5 hashtag được chấp nhận; mất bản hiển thị gốc; D tự sanitize bằng quy tắc riêng.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider`
- coveredIds: CT-AI-009

### D-13: Port lưu trữ, UoW in-memory và outbox
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/ports/repositories.py`
  - `src/creative/adapters/memory.py`
  - `tests/unit/creative/test_d13_ports_memory.py`
  - `docs/delivery-evidence/d-13/report.md`
- dependsOn: `D-02`, `D-04`, `D-05`, `D-06`, `D-08`, `D-10`, `D-11`, `D-12`
- resourceLocks: `LOCK-D-13`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- acceptance:
  - requirement: Protocol repository cho snapshot, analysis, angle set, script, plan, variant validation, output metadata, invocation record, receipt; append-only (revision mới không ghi đè, không xoá bản cũ; `snapshot_id` duy nhất); UoW in-memory implement `controlplane.domain.interfaces.uow.IUnitOfWork` (rollback huỷ mọi ghi kể cả outbox); outbox implement `controlplane.domain.interfaces.outbox.IOutboxWriter` dedup theo `deduplication_id`; event dựng bằng `controlplane.domain.events.contracts.DomainEvent` và `ensure_safe_event_payload`, envelope khớp fixture `domain-event-envelope`.
  - instrument: `python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider`
  - counterexample: tạo IUnitOfWork/IOutboxWriter/DomainEvent mới; ghi đè script cũ; rollback để lại outbox; hai snapshot cùng ID.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider`
- coveredIds: acceptance §12 mục 1 (lưu bất biến)

### D-14: Chuỗi command sáng tạo
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/application/pipeline.py`
  - `tests/integration/creative/test_d14_creative_pipeline.py`
  - `docs/delivery-evidence/d-14/report.md`
- dependsOn: `D-07`, `D-09`, `D-13`
- resourceLocks: `LOCK-D-14`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: command `BuildProductionSnapshot`, `AnalyzeContent`, `GenerateStoryAngles`, `GenerateScript`, `SelectCreativeAssets`, `BuildProductionPlan`, `ValidateVariant`, `GenerateOutputMetadata`; mỗi command một UoW gồm output mới, AIInvocationRecord (nếu gọi AI), receipt và outbox event (`ProductionSnapshotCommitted`, `StoryAnglesGenerated`, `ScriptVersionCreated`, `ProductionPlanCreated`, `VariantValidated`, `OutputMetadataCreated`); `GenerateScript` khi chưa có snapshot đã commit bị từ chối và fake AI có 0 lượt gọi; đổi config/source sau snapshot thì job cũ giữ ref cũ, job mới nhận revision mới; cùng idempotency key và payload trả receipt cũ, khác payload → idempotency conflict (`request_hash`); `from_then_to_now` đi qua D-07; mọi output mang ref snapshot, model, prompt, config và input revision; dùng `FakeProviderRoute`/`FakeAIAdapter`.
  - instrument: `python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider`
  - counterexample: gọi AI trước khi commit snapshot; config mới làm đổi job cũ; outbox ghi ngoài UoW; gửi lặp tạo script thứ hai.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider`
- coveredIds: TST-INT-INV-004, TST-INT-INV-005 (phía D), acceptance §12 mục 1 và 7

### D-15: Lỗi provider và fallback (CT-AI-ROUTE-002)
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/application/provider_failure.py`
  - `tests/integration/creative/test_d15_provider_failure.py`
  - `docs/delivery-evidence/d-15/report.md`
- dependsOn: `D-04`, `D-14`
- resourceLocks: `LOCK-D-15`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: timeout, rate limit, output sai schema và hallucinated ref từ fake AI → problem có cấu trúc đã redact và AIInvocationRecord ghi attempt; output và lịch sử cũ không bị xoá hay sửa; stage trả kết quả chờ để G quyết định retry hoặc chờ provider; fallback chỉ theo `fallback_order` của `ProviderRouteDecision` và `allowed_fallbacks` của request, không thêm provider ngoài danh sách (không tự thêm dịch vụ trả phí); output fallback qua cùng validator và ghi model/prompt/config revision; số lần thử lấy từ policy input, không số mặc định; hết budget trả problem cuối, không lặp vô hạn; fallback làm đổi intent sau snapshot ngoài policy thì tạo output revision mới hoặc chờ, không âm thầm thay.
  - instrument: `python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider`
  - counterexample: fallback sang provider ngoài danh sách; lỗi xoá script cũ; retry vô hạn; output fallback bỏ qua validator.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider`
- coveredIds: CT-AI-ROUTE-002, CT-AI-010

### D-16: Worker activity cho G
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/worker/activity_handler.py`
  - `tests/integration/creative/test_d16_worker_activity.py`
  - `docs/delivery-evidence/d-16/report.md`
- dependsOn: `D-14`
- resourceLocks: `LOCK-D-16`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: nhận `ActivityRequest` kèm `controlplane.domain.orchestration.ExecutionGrant` (không tạo lớp grant mới; trường lệch binding ghi vào report và CONV-D-05), gọi command D-14 theo `activity_name`, trả `ActivityResult` với `output_refs`, `metrics`, `warnings`, `problem` đã redact; generation hoặc recovery epoch cũ bị từ chối, không commit; lặp `operation_key` trả kết quả cũ; precondition desktop capability do G kiểm (`WAITING_CAPABILITY`), D không tự chờ; test `ast` khẳng định handler không import `temporalio`, `controlplane.ui`, `controlplane.api`, `voice`, `render`.
  - instrument: `python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider`
  - counterexample: generation cũ ghi script mới; ActivityResult chứa secret; handler đăng ký workflow Temporal trực tiếp.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider`
- coveredIds: CT-WF-003, CT-WF-006 (phía D)

### D-17: Projection truy vết read-only
- kind: `work_package_slice`
- ownedPaths:
  - `src/creative/projections/trace_queries.py`
  - `tests/unit/creative/test_d17_trace_projection.py`
  - `docs/delivery-evidence/d-17/report.md`
- dependsOn: `D-13`
- resourceLocks: `LOCK-D-17`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: query truy vết từ output (plan, script, metadata, validation) ngược về snapshot, analysis, angle, model/provider/prompt/config revision và input revision; liệt kê lịch sử revision không ghi đè; query không gọi AI (fake đếm 0 lượt); lọc theo workspace; không lộ secret hay lỗi chưa redact.
  - instrument: `python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider`
  - counterexample: query kích hoạt AI; trả output của workspace khác; trace thiếu prompt revision.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider`
- coveredIds: acceptance §12 mục 7, exit gate G1

### D-18: Ma trận test ID và acceptance contract
- kind: `work_package_slice`
- ownedPaths:
  - `tests/unit/creative/test_d18_coverage_catalog.py`
  - `docs/delivery-evidence/d-18/report.md`
- dependsOn: `D-01`, `D-02`, `D-03`, `D-04`, `D-05`, `D-06`, `D-07`, `D-08`, `D-09`, `D-10`, `D-11`, `D-12`, `D-13`, `D-14`, `D-15`, `D-16`, `D-17`
- resourceLocks: `LOCK-D-18`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
- acceptance:
  - requirement: test chỉ dùng stdlib đọc docstring module của `tests/unit/creative/test_d*.py` và `tests/integration/creative/test_d*.py` (trừ chính D-18), khẳng định mỗi mã TST-INT-INV-004, TST-INT-INV-005, TST-CTR-INV-006, TST-AI-INV-013, TST-AI-INV-014, TST-SEC-INV-012, TST-SEC-INV-020, TST-WF-VAR-004 và CT-AI-000..CT-AI-010 có trong ít nhất một tệp và tệp đó có ít nhất một hàm `test_`; không tệp nào dùng mã tiền tố `TST-CRE-`; report ghi bảng ánh xạ.
  - instrument: `python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider`
  - counterexample: một CT-AI không có test trực tiếp; mã chỉ xuất hiện trong D-18; dùng test ID ngoài catalog.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider`
- coveredIds: acceptance §12 mục 1–8
