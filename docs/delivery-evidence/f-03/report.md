# Báo cáo bằng chứng F-03

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4daa3e625fcac2d0d28a1bf01f925467fd958ff7`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-03 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `163 failed, 6 passed in 1.71s`
- Chi tiết các dòng FAILED tiêu biểu từ bước 6:
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_valid_fixture_returns_frozen_record[payload0]`: `AssertionError: assert False where False = isinstance(None, RenderPackageRecord)`
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_fixture_invalid_cases[missing_hook_placement]`: `Failed: DID NOT RAISE ContractViolation`
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_fixture_invalid_cases[input_artifacts_as_string]`: `Failed: DID NOT RAISE ContractViolation`
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_fixture_invalid_cases[ai_supplied_shell_command]`: `Failed: DID NOT RAISE ContractViolation`
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_missing_each_required_field[render_package_id]`: `Failed: DID NOT RAISE ContractViolation`
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_package_fingerprint_must_be_lowercase_sha256[AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA]`: `Failed: DID NOT RAISE ContractViolation`
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_forbidden_field_is_rejected_at_every_level[ffmpeg -i x-shell_command-path0]`: `Failed: DID NOT RAISE ContractViolation`
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_input_artifact_must_be_object[voice.wav]`: `Failed: DID NOT RAISE ContractViolation`
  - `FAILED tests/unit/render/test_f03_render_package_contract.py::test_input_artifact_size_bytes_wrong_type[True]`: `Failed: DID NOT RAISE ContractViolation`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 6 test quét hằng, binding, record và import (`test_constants_match_binding`, `test_binding_comparison_detects_drift`, `test_record_fields_follow_binding`, `test_fixture_invalid_cases_are_the_known_three`, `test_module_imports_only_pure_stdlib`, `test_module_declares_covered_ids`) đã PASS ngay từ đầu. Tất cả 163 test thất bại đều là `AssertionError` hoặc `DID NOT RAISE` do khung skeleton chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic validator)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `169 passed in 0.15s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/render/domain/package_contract.py`: Định nghĩa 19 trường FieldSpec khớp binding `f-render-package.json`, record frozen `InputArtifactRecord` và `RenderPackageRecord`, ngoại lệ `ContractViolation`, và hàm `validate_render_package_payload` kiểm tra payload, quét trường cấm ở mọi cấp lồng, xác thực kiểu dữ liệu và đóng băng bất biến sâu.
  - `tests/unit/render/test_f03_render_package_contract.py`: Bộ kiểm thử toàn diện 169 test cases bao phủ đối chiếu hằng và phát hiện trôi dạt binding, kiểm tra hợp lệ/không hợp lệ từ fixture, kiểm tra từng trường required, sai kiểu, định dạng lowercase sha256, mảng chuỗi `language_validation_refs`, mảng rỗng, payload không bị sửa đổi, record không alias, từ chối trường cấm ở mọi cấp lồng kèm đường dẫn chính xác, xác thực chi tiết trường con `input_artifacts` và ranh giới import stdlib.
  - `docs/delivery-evidence/f-03/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider` | 0 | `169 passed in 0.15s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Thứ tự kiểm: non-mapping → forbidden quét mọi cấp (trước mọi kiểm khác, fail-closed) → từng trường theo thứ tự binding → từng phần tử input_artifacts, ném lỗi đầu tiên.
2. sha256 sai định dạng (chữ hoa, sai độ dài) → wrong_type theo tests/contract/binding_validator.py, size_bytes âm → constraint_violation với field `input_artifacts` và path `input_artifacts[i].size_bytes`.
3. Giá trị None của trường required → wrong_type.
4. Mảng rỗng hợp lệ vì binding không đặt minItems, việc thiếu input kiểm ở F-06/F-07.
5. Record bất biến sâu (object → MappingProxyType, array → tuple), không alias payload gốc.
6. package_fingerprint chỉ kiểm định dạng, tính và so khớp thuộc F-04; forbidden so khớp đúng tên khóa, không quét giá trị chuỗi.
7. Bốn trường con của input_artifacts lấy từ spec F-03 (GIẢ ĐỊNH: binding chưa liệt kê, mở qua CONV-F-07), media_type chỉ kiểm kiểu string.

## Ánh xạ phản ví dụ

- shell_command lồng materialization_manifest → `test_forbidden_field_is_rejected_at_every_level`
- size_bytes bool → `test_input_artifact_size_bytes`
- hash chữ hoa → `test_package_fingerprint_must_be_lowercase_sha256` và `test_input_artifact_sha256_format`
- hằng lệch binding → `test_binding_comparison_detects_drift`

## coveredIds

- `CT-RND-002 (schema)`
- `TST-SEC-INV-020 (phía F)`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Mở rộng binding sub-field input_artifacts qua CONV-F-07
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Chỉ stdlib.
- Không gọi dịch vụ thật.
