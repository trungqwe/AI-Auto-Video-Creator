# Báo cáo bằng chứng I-01

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4f956426cf8a28182acd5cba47ceebe368f9908f`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-01 trong `docs/implementation/i/slices.md`; binding `docs/parallel-delivery/bindings/i-artifact-version.json`, fixture `tests/fixtures/contracts/i-artifact-version/payloads.json`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider` (chạy với stub ở bước 3)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `60 failed, 5 passed in 0.41s`
- Danh sách test FAILED kèm thông điệp NotImplementedError nguyên văn:
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_valid_fixture_payloads_have_no_errors[DeclareArtifactVersionRequest]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_valid_fixture_payloads_have_no_errors[DeclareArtifactVersionResult]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_invalid_fixture_cases_return_expected_error[content_hash_uppercase]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_invalid_fixture_cases_return_expected_error[missing_retention_class]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_invalid_fixture_cases_return_expected_error[matched_existing_as_text]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_unknown_fields_are_ignored[DeclareArtifactVersionRequest]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_unknown_fields_are_ignored[DeclareArtifactVersionResult]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_size_bytes_bool_is_wrong_type[True]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_size_bytes_bool_is_wrong_type[False]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_matched_existing_integer_is_wrong_type[0]`: `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_matched_existing_integer_is_wrong_type[1]`: `NotImplementedError`
  - 14 test missing_each_field (10 field của Request và 4 field required của Result): đều thất bại với `NotImplementedError`
  - 15 test wrong_type_each_field (10 field của Request và 5 field của Result): đều thất bại với `NotImplementedError`
  - 7 test test_sha256_must_be_64_lowercase_hex: đều thất bại với `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_renamed_sha256_field_is_not_accepted`: `NotImplementedError`
  - 2 test test_empty_payload_reports_all_required_fields_in_binding_order: đều thất bại với `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_required_operation_is_optional`: `NotImplementedError`
  - 8 test test_non_dict_payload_is_wrong_type (2 entity × 4 payload không phải dict: None, [], 'x', 5): đều thất bại với `NotImplementedError`
  - `FAILED tests/unit/storage/test_storage_declaration.py::test_validator_does_not_mutate_payload_and_returns_plain_dicts`: `NotImplementedError`
- Xác nhận: Toàn bộ 60 lỗi FAILED đều là NotImplementedError từ stub; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection (5 test kiểm tra hằng binding version, dataclass fields và frozen instance đều PASS).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `65 passed in 0.06s`

## Thay đổi

- `src/controlplane/domain/storage_meta/declaration.py`: Định nghĩa `DeclareArtifactVersionRequest` (10 trường, frozen dataclass) và `DeclareArtifactVersionResult` (5 trường, frozen dataclass, `required_operation` mặc định là `None`) bám sát BINDING-I-ARTIFACT-VERSION 1.0.0 (CT-STO-001). Cấu hình bộ đặc tả trường `REQUEST_FIELDS` và `RESULT_FIELDS`. Triển khai các hàm nội bộ `_has_type` (kiểm tra kiểu dữ liệu: string, sha256 với fullmatch regex `[0-9a-f]{64}`, integer loại trừ bool, boolean, array chỉ nhận list) và `_validate` (kiểm tra kiểu payload, báo missing_required theo thứ tự trường binding, báo wrong_type khi giá trị không khớp kiểu hoặc mang giá trị None đối với trường có mặt, bỏ qua các trường lạ cộng thêm). Triển khai `validate_declare_request` và `validate_declare_result` trả danh sách lỗi dạng dict thuần `{"code": ..., "field": ...}`.
- `tests/unit/storage/test_storage_declaration.py`: Bộ kiểm thử toàn diện gồm 65 test cases: hằng `BINDING_VERSION`, cấu trúc trường và tính bất biến (frozen) của 2 dataclass, kiểm thử fixture hợp lệ (valid payloads trả `[]`), kiểm thử fixture không hợp lệ (trả đúng expected_error), bỏ qua trường lạ cộng thêm, bắt lỗi bool cho integer (`size_bytes`), bắt lỗi integer cho boolean (`matched_existing`), kiểm tra missing từng trường required, kiểm tra wrong_type từng trường, kiểm tra nghiêm ngặt format 64 ký tự hex thường cho sha256 (từ chối chữ hoa, sai độ dài, ký tự ngoài hex, khoảng trắng, xuống dòng), từ chối trường đổi tên `sha256_hash`, kiểm tra thứ tự báo lỗi payload rỗng, tính tùy chọn của `required_operation`, kiểm tra payload không phải dict, và đảm bảo validator không làm biến đổi payload đầu vào.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider` | 0 | 65 passed in 0.06s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 3 | `python -c "import pathlib; fs=['src/controlplane/domain/storage_meta/declaration.py','tests/unit/storage/test_storage_declaration.py','docs/delivery-evidence/i-01/report.md']; data={f: pathlib.Path(f).read_bytes() for f in fs}; bad=[(f,i) for f in fs for i,l in enumerate(data[f].decode('utf-8').split('\n'),1) if l.rstrip('\r')!=l.rstrip()]; assert not bad, bad; assert all(d.endswith(b'\n') and not d.startswith(b'\xef\xbb\xbf') for d in data.values()); print('OK')"` | 0 | OK (UTF-8 không BOM, không trailing whitespace, kết thúc LF) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH 1: payload không phải dict trả `[{'code': 'wrong_type', 'field': 'payload'}]`.
2. GIẢ ĐỊNH 2: trường optional có mặt với giá trị `None` là `wrong_type`.
3. GIẢ ĐỊNH 3: kiểu array chỉ nhận `list`.
4. GIẢ ĐỊNH 4: lỗi trả theo thứ tự field của binding, mỗi field tối đa một lỗi.
5. GIẢ ĐỊNH 5: không kiểm giá trị enum/UUID vì binding khai kiểu string.

## Danh sách chờ user (pendingUserCheckpoint)

Không phát sinh mục mới; không mục nào được coi là đã duyệt.

## Giới hạn

- Không chạy full suite; không chạm tests/m1, tests/m2.
- Không sửa `src/controlplane/domain/storage_meta/__init__.py` P5B, binding, fixture, pyproject.toml hay lockfile.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib (`re`, `dataclasses`).
- Không gọi dịch vụ thật.
- Không tạo conftest.py hay __init__.py trong tests/.
- Không commit secret, token, credential hay dữ liệu cá nhân.
