# Báo cáo bằng chứng B-1

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `7f6c060c32c3dc545b857a1714b5fea0b445429f`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-1 trong docs/implementation/b/slices.md; D3 user duyệt Phần B ngày 18/10/2026.
- Binding refs: binding `docs/parallel-delivery/bindings/a-b-collected-document.json` 1.0.0 và fixture `tests/fixtures/contracts/a-b-collected-document/payloads.json`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` (chạy trên skeleton với các hằng rỗng, BINDING_VERSION rỗng và hai hàm stub trả [])
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `27 failed, 8 passed in 0.19s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_package_validation.py::test_constants_match_binding[CollectedDocumentPackage]`: `AssertionError: assert ({}, {}, {}, {}) == ({'collected_...s': 'object'})` (At index 0 diff: `{}` != `{'collected_document_id': 'string', ...}`)
  - `FAILED tests/unit/ingestion/test_ingestion_package_validation.py::test_binding_version_constant_matches_binding`: `AssertionError: assert '' == '1.0.0'`
  - `FAILED tests/unit/ingestion/test_ingestion_package_validation.py::test_drift_comparison_detects_mutated_binding`: `AssertionError: PACKAGE_REQUIRED must not be empty`
  - `FAILED tests/unit/ingestion/test_ingestion_package_validation.py::test_fixture_invalid_case_returns_expected_issue[missing_provenance_chain]`: `AssertionError: assert [] == [('missing_required', 'provenance_chain')]`
  - `FAILED tests/unit/ingestion/test_ingestion_package_validation.py::test_package_counterexamples_are_rejected[provenance_chain-value0-missing_required]`: `AssertionError: assert [] == [('missing_required', 'provenance_chain')]`
  - `FAILED tests/unit/ingestion/test_ingestion_package_validation.py::test_binding_version_major_other_than_one_is_unsupported[CollectedDocumentPackage]`: `AssertionError: 2.0.0 assert [] == [('unsupported_binding_version', 'binding_version')]`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; các test PASS gồm `test_ingestion_import_boundary`, `test_boundary_regex_detects_forbidden_imports`, `test_unknown_field_is_ignored`, `test_fixture_valid_payloads_have_no_issues`; 27 lỗi đều là sai oracle (AssertionError).

## Thay đổi

- `src/ingestion/__init__.py`: Package root của bounded context ingestion (module B).
- `src/ingestion/domain/__init__.py`: Package layer pure domain model cho ingestion.
- `src/ingestion/application/__init__.py`: Package layer application services cho ingestion.
- `src/ingestion/infrastructure/__init__.py`: Package layer infrastructure adapters cho ingestion.
- `src/ingestion/domain/package_validation.py`: Module kiểm tra biên schema CollectedDocumentPackage và CollectedDocumentResolution theo hợp đồng binding 1.0.0:
  - `ValidationIssue`: Dataclass biểu diễn lỗi gồm mã `code` và tên `field`.
  - Hằng số mã lỗi: `MISSING_REQUIRED`, `WRONG_TYPE`, `ENUM_VIOLATION`, `UNSUPPORTED_BINDING_VERSION`.
  - Hằng số binding: `BINDING_VERSION = '1.0.0'`, `SUPPORTED_BINDING_MAJOR = 1`.
  - Các hằng phân loại trường: `PACKAGE_REQUIRED`, `PACKAGE_OPTIONAL`, `PACKAGE_ENUM`, `PACKAGE_ITEMS`, `RESOLUTION_REQUIRED`, `RESOLUTION_OPTIONAL`, `RESOLUTION_ENUM`, `RESOLUTION_ITEMS`.
  - Hàm kiểm tra: `_is_rfc3339`, `_matches_type`, `_supports_binding_version`, `_validate`.
  - Hai hàm validation public: `validate_collected_document_package` và `validate_collected_document_resolution`.
- `tests/unit/ingestion/test_ingestion_package_validation.py`: Bộ kiểm thử đơn vị với 35 test cases:
  - `test_constants_match_binding`: Khớp 1:1 các hằng số với binding json cho cả 2 thực thể.
  - `test_binding_version_constant_matches_binding`: Khớp phiên bản binding 1.0.0.
  - `test_drift_comparison_detects_mutated_binding`: Phát hiện drift nếu binding bị thay đổi trên 5 đột biến.
  - `test_fixture_has_cases_for_both_entities`: Kiểm tra fixture chứa đủ ca kiểm thử.
  - `test_fixture_valid_payloads_have_no_issues`: Mọi payload valid trong fixture đều không có lỗi.
  - `test_fixture_invalid_case_returns_expected_issue`: 6 ca invalid trong fixture đều trả đúng mã lỗi và trường.
  - `test_each_missing_required_field_is_reported`: Thiếu từng trường required đều bị bắt.
  - `test_package_counterexamples_are_rejected`: Phản ví dụ cho provenance_chain, content_eligibility, source_revision, datetime, media_discoveries.
  - `test_rfc3339_datetimes_with_offset_are_accepted`: Định dạng RFC3339 hợp lệ có offset được chấp nhận.
  - `test_unknown_field_is_ignored`: Trường lạ được bỏ qua không gây lỗi.
  - `test_binding_version_major_other_than_one_is_unsupported`: Binding version khác major 1 trả unsupported_binding_version.
  - `test_non_mapping_payload_is_wrong_type`: Payload không phải mapping trả wrong_type tại `$`.
  - `test_boundary_regex_detects_forbidden_imports`: Kiểm tra regex phát hiện import bị cấm.
  - `test_ingestion_import_boundary`: CHECK-B quét `src/ingestion/**/*.py` đảm bảo không có import vi phạm và không tồn tại `__init__.py` cấm trong tests.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.04s |
| 2 | `git diff --check` | 0 | không output |

## Quyết định mặc định (D8)

1. Payload không có `binding_version` được coi là 1.0.0 vì fixture chuẩn không mang trường này.
2. `binding_version` không phải chuỗi SemVer hoặc major khác 1 trả duy nhất `unsupported_binding_version` và không kiểm tiếp trường (fail-closed, CT-CMN-012).
3. Trường required có giá trị `None` trả về `wrong_type`; trường optional có giá trị `None` coi như vắng mặt.
4. Payload không phải mapping trả về `wrong_type` tại trường `$`.
5. Kiểu `object` ánh xạ tới `dict`, `array` ánh xạ tới `list`, chỉ kiểm tra items cấp 1, không kiểm tra đệ quy trường con.
6. Datetime RFC3339 bắt buộc có timezone offset hợp lệ, kiểm tra bằng regex kết hợp `datetime.fromisoformat`.
7. Phân hệ B tự chứa các hằng số schema, không import từ `source_ingestion` của phân hệ A để bảo vệ ranh giới phân hệ; hiện tượng drift được phát hiện thông qua test đối chiếu trực tiếp tệp binding.
8. Không bổ sung thêm bất kỳ thư viện ngoài nào, chỉ sử dụng thư viện chuẩn của Python (re, collections.abc, dataclasses, datetime, types).

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- EG-M3-7

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa `pyproject.toml`, `uv.lock`, file binding hay fixture.
- Không gọi dịch vụ thật hay đọc bí mật.
- Không sửa HANDOFF.md, README.md, CHANGELOG.md hay checklist nằm ngoài owned paths trong slice này.
