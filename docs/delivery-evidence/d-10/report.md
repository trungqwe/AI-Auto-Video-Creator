# Báo cáo bằng chứng D-10

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `f54199a752a19475f567738a7c70eb108d583316`
- Nguồn quyền: user duyệt Phần B ngày 18/10/2026, ủy quyền AI_SETUP, slice D-10.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider` (chạy với khung production_plan.py chưa có hành vi)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `92 failed, 2 passed in 1.33s`
- Chi tiết các test FAILED chọn lọc kèm thông điệp assertion nguyên văn:
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_module_imports_stay_inside_allowlist`: `AssertionError: assert None is <function request_hash at 0x...>`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_valid_plan_records_all_contract_fields`: `assert False where False = isinstance(None, ProductionPlan)`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_every_time_range_is_integer_ms_with_start_before_end`: `AttributeError: 'NoneType' object has no attribute 'to_payload'`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_plan_is_frozen_and_isolated_from_input`: `AttributeError: 'NoneType' object has no attribute 'to_payload'`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_fingerprint_is_sha256_over_content`: `AttributeError: 'NoneType' object has no attribute 'plan_fingerprint'`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_timeline_rejections[path0-8000.5-expected0]`: `Failed: DID NOT RAISE PlanRejected`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_thumbnail_outside_hook_is_rejected[hook0-thumb0]`: `Failed: DID NOT RAISE PlanRejected`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_forbidden_field_names_are_rejected[path2-shell_command-shell_command]`: `Failed: DID NOT RAISE PlanRejected`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_binding_constants_match_binding`: `AssertionError: assert set() == {'allowed_fallbacks', 'hook_placement', 'production_plan_ref', 'script_version_ref', 'timeline'}`
  - `FAILED tests/unit/creative/test_d10_production_plan.py::test_to_render_package_inputs_matches_binding_field_types`: `AttributeError: 'NoneType' object has no attribute 'to_render_package_inputs'`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection; RED là sai oracle (AttributeError trên None, DID NOT RAISE PlanRejected, assert hằng khác binding).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `94 passed in 0.29s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/creative/domain/production_plan.py`: Triển khai các mã lỗi và ngoại lệ `PlanRejected`, hằng `BINDING_ENTITY`, `RENDER_PACKAGE_INPUT_TYPES` khớp hoàn toàn với binding `f-render-package`, `FORBIDDEN_FIELDS`, `FALLBACK_KINDS`; helper `_scan_intent_only` từ chối triệt để `shell_command`, URL, đường dẫn tệp ở mọi cấp lồng; helper kiểm tra schema và time range `_range_object`, `_parse_visuals` và `_parse_timeline` đảm bảo timeline liên tục từ 0, không khoảng trống/chồng lấn, visual phủ kín cảnh và lấy ref từ `CreativeAssetSelection`; `_parse_hook_placement` bảo đảm thumbnail nằm trọn trong hook range và không dùng hằng 0–3 giây; `_parse_text_object`, `_parse_subtitle`, `_parse_cues`, `_parse_fallbacks`; frozen dataclass `ProductionPlan` với đóng băng sâu (`_freeze`), `to_payload`, `fingerprint_basis`, `compute_fingerprint` (SHA-256 qua `request_hash`), `to_render_package_inputs` trả đúng 5 trường và kiểu tương ứng binding `RenderPackage`; hàm `build_production_plan` kiểm tra tính sẵn sàng của context, script_ref khớp, intent-only và gán fingerprint.
  - `tests/unit/creative/test_d10_production_plan.py`: Bộ kiểm thử đơn vị toàn diện bao gồm: khai báo coveredIds trong docstring; kiểm tra allowlist import; kiểm tra toàn bộ trường hợp lệ của plan; kiểm tra mọi time range là int ms nguyên với start < end; kiểm tra tính bất biến frozen và cô lập dữ liệu; kiểm tra tính xác định của SHA-256 plan_fingerprint và sự thay đổi khi sửa bất kỳ nội dung nào; bảng test từ chối timeline (sai kiểu, âm ms, start >= end, timeline không từ 0, gap, overlap, thiếu visual, visual không phủ kín); test hook và thumbnail nằm trọn trong hook (chứng minh không có hằng 0–3 giây hay 3000 ms); test intent-only từ chối trường cấm, URL, file path ở mọi cấp lồng; test context, schema, cues, fallbacks và metadata; test đối chiếu trực tiếp binding `f-render-package` và fixture, kiểm tra phát hiện drift và không rò rỉ forbidden fields.
  - `docs/delivery-evidence/d-10/report.md`: Báo cáo bằng chứng nghiệm thu của task D-10.
## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider` | 0 | 94 passed in 0.29s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## coveredIds

`CT-AI-007, CT-RND-003 điều kiện 1–3 phía D`

## Quyết định mặc định (D8)

1. Ref asset/rendition/hook/thumbnail và cue lấy từ `CreativeAssetSelection` D-09, raw chỉ cấp time range và intent.
2. `hook_time_range` và `thumbnail_time_range` do caller cấp, không dùng hằng 0–3 giây vì acceptance của task ưu tiên hơn ghi chú 0–3 giây trong `M5-D-contract-freeze`.
3. `duration_ms` suy ra từ cảnh cuối, timeline liên tục từ 0, mỗi cảnh phải có visual phủ kín.
4. Bốn nhóm fallback mặc định `replace_asset`, `drop_overlay_effect`, `simplify_transition` là lựa chọn đơn giản do D8, GIẢ ĐỊNH chờ `ROADMAP-OPEN-009`.
5. `plan_fingerprint` = `request_hash` trên nội dung (`fingerprint_basis`), loại trừ `production_plan_id` và `plan_fingerprint`.
6. Intent-only: cấm triệt để khoá `shell_command`, `arbitrary_url`, `url`, `uri`, `command`, `path`, `file_path` và giá trị chuỗi là URL hoặc đường dẫn tệp.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt
- ROADMAP-OPEN-009

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.
- Chưa có binding riêng cho CT-AI-007 ngoài f-render-package.