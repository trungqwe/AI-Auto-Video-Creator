# Báo cáo bằng chứng D-09

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `170b96b2748929758f96d9b5a54726be29fb7600`
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-09.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider` (chạy với khung asset_selection.py chưa có hành vi)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `104 failed, 6 passed in 1.42s`
- Chi tiết các test FAILED chọn lọc kèm thông điệp assertion nguyên văn:
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_constants_match_binding[MediaCandidateQuery]`: `AssertionError: assert ({}, {}, {}) == ({'production...s': 'string'})`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_constants_match_binding[MediaCandidate]`: `AssertionError: assert ({}, {}, {}) == ({'media_asse...s': 'string'})`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_binding_version_matches_binding_and_fixture`: `AssertionError: assert '' == '1.0.0'`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_fixture_invalid_case_returns_expected_issue[MediaCandidateQuery-missing_safety_policy_revision]`: `AssertionError: assert [] == [('missing_re...cy_revision')]`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_fixture_invalid_case_returns_expected_issue[MediaCandidate-missing_reason_codes]`: `AssertionError: assert [] == [('missing_re...eason_codes')]`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_selection_returns_assignments_intents_fallbacks_rationale_scores_and_fingerprint`: `AssertionError: assert isinstance(None, CreativeAssetSelection)`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_every_proposed_ref_goes_through_the_d03_resolver`: `AssertionError: assert [] == [('visual_hook', 'vh-1'), ('audio_hook', 'ah-1'), ('thumbnail', 'th-1'), ('media_asset', 'm-2'), ('media_asset', 'm-1')]`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_missing_required_hook_is_rejected[absent-visual_hook]`: `Failed: DID NOT RAISE SelectionRejected`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_ref_outside_candidate_set_is_rejected_as_hallucinated[scene-unknown_ref-0]`: `Failed: DID NOT RAISE SelectionRejected`
  - `FAILED tests/unit/creative/test_d09_asset_selection.py::test_fingerprint_is_sha256_of_basis_and_stable_across_candidate_order`: `AttributeError: 'NoneType' object has no attribute 'fingerprint_basis'`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; RED là sai oracle (hằng khác binding, validator không báo lỗi, select_creative_assets trả None, DID NOT RAISE SelectionRejected).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `110 passed in 0.16s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/creative/domain/asset_selection.py`: Triển khai hằng `QUERY_REQUIRED`, `QUERY_OPTIONAL`, `QUERY_ITEMS`, `CANDIDATE_REQUIRED`, `CANDIDATE_OPTIONAL`, `CANDIDATE_ITEMS` so với binding `c-d-media-candidates`; `ValidationIssue`, `matches_type`, `validate_media_candidate_query`, `validate_media_candidate`; frozen dataclass `MediaCandidateQuery` (kèm `to_payload`) và hàm `build_media_candidate_query`; mixin `_RefMixin`, frozen dataclass `MediaCandidate` (kèm `to_payload`) và hàm `parse_media_candidate`; value object D-local `HookCandidate` và `ThumbnailCandidate` (theo CONV-D-07); `SafetyRightsPolicy`, `ScoringWeights`, `SceneAssignment`, `FallbackCandidate`, `CreativeAssetSelection` (tính fingerprint xác định SHA-256 qua `request_hash`, kèm `to_payload`); hàm `select_creative_assets` tích hợp `RefResolver` D-03 để giải quyết toàn bộ ref qua candidate hợp lệ, loại bỏ candidate bị policy chặn, bắt buộc hook visual/audio và thumbnail (thiếu báo `missing_required_hook`), gán media cho scene theo thứ tự, xử lý intent âm thanh, tính `score_components` và xếp hạng `fallback_candidates`.
  - `tests/unit/creative/test_d09_asset_selection.py`: Bộ kiểm thử đơn vị gồm kiểm tra hằng khớp binding `c-d-media-candidates` và drift comparison, kiểm tra fixture valid/invalid, kiểm tra validate trường bắt buộc/sai kiểu/trường lạ, kiểm tra `build_media_candidate_query` bất biến và trả frozen query, parse `MediaCandidate` từ fixture, kiểm tra `select_creative_assets` với assignments, intents, fallback, rationale, score components và fingerprint sha256 xác định, kiểm tra `RefResolver` D-03 cho mọi ref, kiểm tra candidate bị policy chặn bị loại bỏ, kiểm tra thiếu hook trả `missing_required_hook`, ref lạ trả `hallucinated_ref`, proposal sai cấu trúc trả `invalid_proposal`, kiểm tra tính bất biến và allowlist import.
  - `docs/delivery-evidence/d-09/report.md`: Báo cáo bằng chứng chuyển giao của task D-09.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider` | 0 | 110 passed in 0.16s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## coveredIds

`CT-AI-006, CT-MED-005 (phía D)`

## Quyết định mặc định (D8)

1. CONV-D-07: hook/thumbnail candidate (CT-MED-004/006) chưa có binding nên dùng value object D-local HookCandidate/ThumbnailCandidate và fake trong test, không wiring thật.
2. Safety/rights policy, music/SFX policy revision, preset registry revision và ScoringWeights là input của caller, thiếu thì INPUT_NOT_READY; tập availability 'AVAILABLE' và cờ 'rights_cleared' trong test là GIẢ ĐỊNH theo fixture.
3. Proposal của model là dữ liệu không tin cậy dạng D-local (visual_hook, audio_hook, thumbnail, scenes[].ref, music_intents, sfx_intents, rationale); mọi ref qua RefResolver D-03 dựng từ candidate đủ điều kiện; lỗi thành hallucinated_ref, candidate_blocked, missing_required_hook hoặc invalid_proposal.
4. Mỗi media_asset_id một candidate (GIẢ ĐỊNH C trả rendition tốt nhất), trùng thì ValueError.
5. Điểm = semantic*w + technical*w - times_used*penalty, làm tròn 6 chữ số, chỉ dùng xếp fallback và ghi score components.
6. Fingerprint = request_hash trên ref, thứ tự, intent, fallback và revision, không gồm rationale hay điểm.
7. Loại trừ usage gần đây do query excluded_usage_refs xử lý ở C, select chỉ phạt theo times_used.
8. Intent chuẩn hoá chỉ giữ cue và description, bỏ khoá lạ như tool_call, url.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt
- ROADMAP-OPEN-009 năm preset và music/SFX policy (pendingUserCheckpoint)
- Chất lượng chọn media/hook T7 từ 90% để CP7-D-02

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.
