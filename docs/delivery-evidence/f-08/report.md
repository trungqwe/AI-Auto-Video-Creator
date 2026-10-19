# Báo cáo bằng chứng F-08

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `0591304d66208f1b9c445a437d793b1c1bb7210b`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-08 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider` (chạy trên khung API bước 1 chưa cài logic nghiệp vụ)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `45 failed, 10 passed in 0.47s`
- Chi tiết các dòng FAILED tiêu biểu từ bước 9:
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_valid_package_passes_with_report_id_from_request_hash`: `AssertionError: assert '' == '99e9af54a2d8c666cbda0a599c4667f4bf50a8583dc10ac4b0b7e6bd227bf9e1'`
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_single_missing_condition_gives_exactly_one_finding[1]`: `AssertionError: assert [] == [Finding(condition=1, code='visual_hook_missing', field='hook_placement.visual_hook_ref')]`
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_several_missing_conditions_give_several_findings[conditions0]`: `AssertionError: assert [] == [Finding(condition=1, code='visual_hook_missing', field='hook_placement.visual_hook_ref'), Finding(condition=2, code='audio_hook_missing', field='hook_placement.audio_hook_ref')]`
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_findings_are_ordered_by_condition_then_code_then_field`: `AssertionError: assert [] == [1, 2, 3, 4, 5, 6, 7, 8, 9]`
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_missing_context_is_input_not_ready_and_never_passes`: `AssertionError: assert [] == [Finding(condition=4, code='voice_missing', field='voice_artifact_ref'), ...]`
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_non_record_input_is_rejected`: `AttributeError: 'dict' object has no attribute 'package_fingerprint'`
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_report_rejects_inconsistent_construction`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_require_valid_package_raises_with_the_report`: `Failed: DID NOT RAISE PackageNotRenderable`
  - `FAILED tests/unit/render/test_f08_validate_package.py::test_invalid_package_makes_zero_renderer_calls[1]`: `Failed: DID NOT RAISE PackageNotRenderable`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hoặc lỗi collection. 10 test passed gồm các kiểm tra DTO frozen, ranh giới import (chỉ các module trong danh sách cho phép) và khai báo coveredIds. Toàn bộ 45 test thất bại đều là AssertionError, Failed: DID NOT RAISE hoặc AttributeError do khung chưa cài đặt logic nghiệp vụ.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider` (chạy sau khi hoàn tất cài đặt logic nghiệp vụ)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `55 passed in 0.13s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/render/domain/validate_package.py`: Triển khai hàm tổng hợp tiền điều kiện gói render `ValidateRenderPackage` theo CT-RND-003 mục 1-9:
    - Định nghĩa DTO `Finding(condition, code, field)` độc lập và chuẩn hóa thứ tự theo `(condition, code, field)`.
    - Định nghĩa `ValidationContext` chứa thông tin ngữ cảnh tiền điều kiện (voice, word_timing, verified, issued_paths, language_evidence, language_policy, preset, capability).
    - `PackageValidationReport`: DTO frozen chứa `package_fingerprint`, bộ tuple `findings`, cờ `passed` (chỉ True khi findings rỗng) và `report_id` được băm bất biến từ `package_fingerprint` cùng danh sách `findings` bằng `request_hash`. Lớp tự kiểm tra tính hợp lệ và thứ tự lúc khởi tạo (`__post_init__`).
    - `PackageNotRenderable`: Ngoại lệ mang thuộc tính `report` chứa toàn bộ finding, được ném ra bởi `require_valid_package`.
    - `validate_render_package(record, context)`: Chạy tuần tự và gộp đầy đủ các phép kiểm tra từ F-06 và F-07 (`check_hook_preconditions`, `check_voice_timing_binding`, `check_timeline_coverage`, `check_language_evidence`, `check_artifacts_verified`, `check_output_path`, `check_preset_tool_compat`), sắp xếp kết quả theo thứ tự từ điển, không bỏ sót bất kỳ vi phạm nào; ngữ cảnh thiếu hoặc sai kiểu dẫn đến `INPUT_NOT_READY`.
    - `require_valid_package(report)`: Cổng kiểm soát bắt buộc trước khi gọi renderer thật, ném `PackageNotRenderable` nếu gói không hợp lệ.
  - `tests/unit/render/test_f08_validate_package.py`: Bộ kiểm thử đơn vị toàn diện bao gồm 55 test cases:
    - Kiểm thử gói hợp lệ trả về report thành công với `report_id` tính từ `request_hash`.
    - Kiểm thử 9 điều kiện CT-RND-003 đơn lẻ và tổ hợp nhiều điều kiện đồng thời.
    - Kiểm thử thứ tự sắp xếp finding, tính xác định và bất biến của `report_id`.
    - Kiểm thử các trường hợp thiếu context hoặc context sai kiểu dẫn đến `INPUT_NOT_READY`.
    - Kiểm thử tính đóng băng (frozen) và tính toàn vẹn của `PackageValidationReport`.
    - Kiểm thử `require_valid_package` ném ngoại lệ khi có lỗi.
    - Kiểm thử `FakeRenderer` xác nhận 0 lượt gọi renderer khi gói không hợp lệ và 1 lượt gọi khi gói hợp lệ.
    - Kiểm thử ranh giới import cho phép và khai báo coveredIds.
  - `docs/delivery-evidence/f-08/report.md`: Báo cáo bằng chứng thực thi chi tiết gói F-08.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider` | 0 | `55 passed in 0.13s` |
| 2 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | `12 passed, 75 subtests passed in 0.10s` |
| 3 | `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider` | 0 | `104 passed in 0.14s` |
| 4 | `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider` | 0 | `97 passed in 0.14s` |
| 5 | `git diff --check` | 0 | PASS (không output, không lỗi trailing whitespace, làm việc sạch) |

## Quyết định mặc định (D8)

1. F-08 khai báo `Finding(condition, code, field)` riêng và chuyển đổi finding từ F-06/F-07 sang kiểu này để đảm bảo tính tự chủ và nhất quán trong domain F-08.
2. `ValidationContext` là DTO F-local, tên là GIẢ ĐỊNH (mở qua CONV-F-07), gồm các trường: voice, word_timing, verified, issued_paths, language_evidence, language_policy, preset, capability.
3. Context không phải `ValidationContext` hoặc phần context sai kiểu coi như thiếu → `INPUT_NOT_READY`; voice/word_timing None đi qua F-06 cho `voice_missing`/`word_timing_missing`.
4. Thứ tự findings sắp xếp theo bộ `(condition, code, field)` theo thứ tự từ điển, không loại trùng lặp.
5. `PackageValidationReport` tự kiểm `passed`, thứ tự và `report_id` khi dựng trong `__post_init__`; `report_id` = `request_hash` của `package_fingerprint` và `findings` (`passed` là dẫn xuất, không nằm trong cơ sở băm).
6. Tham số `record` không phải `RenderPackageRecord` sẽ ném `TypeError` (bảo vệ lỗi lập trình).
7. `FakeRenderer` chỉ nằm trong test suite để chứng minh tính chất fail-early; tầng domain hoàn toàn không gọi renderer thật, không I/O và không phụ thuộc đồng hồ.

## Ánh xạ phản ví dụ

- Gói thiếu hook vẫn gọi renderer → Loại trừ bằng `test_invalid_package_makes_zero_renderer_calls` và `test_missing_hook_never_reaches_renderer_and_all_findings_are_reported`.
- Chỉ báo lỗi đầu tiên → Loại trừ bằng `test_several_missing_conditions_give_several_findings`.
- Context thiếu mà report vẫn pass → Loại trừ bằng `test_missing_context_is_input_not_ready_and_never_passes` và `test_each_missing_context_part_gives_exactly_one_input_not_ready`.
- Report không xác định thứ tự → Loại trừ bằng `test_findings_are_ordered_by_condition_then_code_then_field`, `test_sort_overrides_the_natural_order_of_the_f06_check` và `test_report_is_deterministic_and_report_id_tracks_findings`.

## coveredIds

- `CT-RND-003`
- `TST-INT-INV-008 (phía F)`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: Thư viện đề xuất cố định phiên bản cho toàn bộ runtime.
- CP7 tài nguyên thật (D5): Tài nguyên thực tế GPU/dịch vụ qua secret broker phân hệ J.
- Mở binding qua CONV-F-07 cho context (staging root, output path, language evidence).
- User checkpoint M2 (P8/P9) — đã triển khai và có Auditor PASS nhưng chưa ghi user checkpoint duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không thay đổi pyproject.toml, uv.lock, binding, contract registry hay test fixtures.
- Không gọi dịch vụ ngoài thật.
