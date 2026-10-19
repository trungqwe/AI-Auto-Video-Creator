# Báo cáo bằng chứng G-02

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `7622e01f50b6257f93a5c0b90f84880b5c9bf952`
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-02 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider` (chạy trên stub chỉ ném NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `307 failed, 20 passed, 2 subtests passed in 1.48s`
- Chi tiết 4–5 dòng FAILED tiêu biểu kèm thông điệp `NotImplementedError: G-02 RED stub: ...`:
  - `FAILED tests/unit/orchestration/test_g_completion_binding.py::FixtureTests::test_invalid_payloads_return_exactly_expected_error` (entity='CommitVideoCompletionRequest', case='missing_cloud_location_verification_ref'): `NotImplementedError: G-02 RED stub: validate_commit_request`
  - `FAILED tests/unit/orchestration/test_g_completion_binding.py::FixtureTests::test_invalid_payloads_return_exactly_expected_error` (entity='CompletionLedgerEntry', case='missing_cleanup_policy_ref'): `NotImplementedError: G-02 RED stub: validate_ledger_entry`
  - `FAILED tests/unit/orchestration/test_g_completion_binding.py::FixtureTests::test_valid_payloads_return_empty_list` (entity='CommitVideoCompletionRequest', index=0): `NotImplementedError: G-02 RED stub: validate_commit_request`
  - `FAILED tests/unit/orchestration/test_g_completion_binding.py::ShapeTests::test_all_errors_are_reported_in_binding_order` (entity='CommitVideoCompletionRequest'): `NotImplementedError: G-02 RED stub: validate_commit_request`
  - `FAILED tests/unit/orchestration/test_g_completion_binding.py::ShapeTests::test_non_mapping_payload_is_wrong_type_at_root` (entity='CommitVideoCompletionRequest', payload=None): `NotImplementedError: G-02 RED stub: validate_commit_request`
- Các test PASS trên stub: 20 passed và 2 subtests passed (`BindingDriftTests::test_field_specs_match_binding_manifest_in_order`, `FixtureTests::test_fixture_is_not_vacuous`, `PurityTests::test_module_has_no_io_or_clock`).
- Xác nhận: Hoàn toàn không có lỗi import hay collection (RED chỉ thất bại do NotImplementedError trên stub đúng oracle).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider` (chạy sau khi cài mã thật)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `22 passed, 307 subtests passed in 0.06s`

## Thay đổi

- Danh sách 3 tệp thuộc owned paths:
  - `src/controlplane/domain/orchestration/completion_binding.py`: Cài đặt bộ xác thực biên cho `CommitVideoCompletionRequest` (CT-ORC-008) và `CompletionLedgerEntry` (CT-ORC-009) theo chuẩn BINDING-G-C-I-COMPLETION 1.0.0:
    - `FieldSpec`: Dataclass bất biến biểu diễn thông tin trường gồm `name`, `type`, `required`.
    - `COMMIT_REQUEST_FIELDS`: Khai báo 17 trường bắt buộc của request đúng thứ tự binding.
    - `LEDGER_ENTRY_FIELDS`: Khai báo 19 trường bắt buộc của ledger đúng thứ tự binding.
    - `_validate`: Hàm dùng chung lặp qua danh sách spec, kiểm tra payload mapping, kiểm tra trường thiếu (`missing_required`) và kiểu dữ liệu (`wrong_type`), trả về danh sách lỗi theo thứ tự trường binding.
    - `validate_commit_request`: Xác thực `CommitVideoCompletionRequest`, trả `[]` khi hợp lệ hoặc danh sách lỗi `{code, field}`.
    - `validate_ledger_entry`: Xác thực `CompletionLedgerEntry`, trả `[]` khi hợp lệ hoặc danh sách lỗi `{code, field}`.
    - Không I/O, không clock (`Pure domain`), chỉ phụ thuộc stdlib.
  - `tests/unit/orchestration/test_g_completion_binding.py`: Bộ kiểm thử toàn diện gồm 9 lớp test:
    - `FixtureTests`: Kiểm tra fixture hợp lệ trả `[]`, fixture không hợp lệ trả đúng mã lỗi và trường dự kiến.
    - `BindingDriftTests`: Kiểm tra thứ tự, kiểu và tính bắt buộc của 17 trường request và 19 trường ledger khớp 100% với file schema binding JSON.
    - `ShapeTests`: Kiểm tra payload không phải mapping trả `wrong_type` tại `$`, trường lạ phụ thêm được bỏ qua, payload không bị sửa đổi (immutability), và báo lỗi theo đúng thứ tự trường binding.
    - `Sha256Tests`: Kiểm tra hash đúng định dạng 64 ký tự hex thường, từ chối hash chữ hoa, chuỗi sai độ dài, ký tự ngoài hex và các kiểu khác.
    - `RequiredFieldTests`: Kiểm tra từng trường bắt buộc khi thiếu trả `missing_required`, khi null trả `wrong_type`, các trường chuỗi từ chối kiểu khác; kiểm tra `cloud_location_verification_ref` chỉ bắt buộc ở request, `cleanup_policy_ref` chỉ bắt buộc ở ledger.
    - `IntegerTests`: Kiểm tra các trường integer (`expected_variant_registry_revision`, `execution_generation`) từ chối bool, string, float, null và chấp nhận số nguyên.
    - `DatetimeTests`: Kiểm tra `completed_at` tuân thủ nghiêm ngặt RFC 3339 (ngày giờ hợp lệ, offset hợp lệ, chấp nhận giây nhuận 60, từ chối giá trị sai hoặc chuỗi không đúng định dạng).
    - `ContainerTests`: Kiểm tra `media_usage_manifest` phải là mảng (`list`), `output_naming_metadata` và `cost_usage_summary` phải là đối tượng (`Mapping`).
    - `PurityTests`: Phân tích tĩnh cú pháp AST bảo đảm module thuần túy, không chứa I/O (không `open`, `read_text`), không chứa clock (không `now`, `utcnow`, `today`), chỉ import các module cho phép.
  - `docs/delivery-evidence/g-02/report.md`: Báo cáo bằng chứng thực thi gói G-02.

## Phản ví dụ được loại trừ

- Completion không có `cloud_location_verification_ref` được chấp nhận: Bị loại trừ và kiểm chứng bởi test `RequiredFieldTests::test_cloud_location_verification_ref_is_required_only_by_request` và fixture test.
- Hash chữ hoa hoặc dạng khác sha256 được chấp nhận: Bị loại trừ và kiểm chứng bởi test `Sha256Tests::test_bad_hashes_are_wrong_type_including_uppercase` với bộ `BAD_HASHES`.
- Revision dạng chuỗi hoặc bool được chấp nhận: Bị loại trừ và kiểm chứng bởi test `IntegerTests::test_integer_fields_reject_bool_string_float_and_null` với bộ `BAD_INTEGERS`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 2 | `python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider` | 0 | 22 passed, 307 subtests passed in 0.06s |

## Quyết định mặc định (D8)

1. Giá trị `null` của trường bắt buộc là `wrong_type`.
2. Chuỗi rỗng được chấp nhận vì binding chỉ khai kiểu `string`.
3. `completed_at` khớp regex RFC 3339 chỉ với `T` và `Z` chữ hoa như `tests/contract/binding_validator.py`, kiểm ngày giờ hợp lệ thật, chấp nhận giây 60.
4. Integer không ràng buộc dấu/miền vì binding không khai.
5. Phần tử của `media_usage_manifest` không bị kiểm vì binding không khai items.
6. Trả mọi lỗi theo thứ tự trường binding, payload không phải mapping trả `wrong_type` tại `$`.
7. Trường lạ được bỏ qua theo `bindings/README.md`.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không thêm thư viện ngoài (chỉ dùng stdlib).
- Không gọi dịch vụ thật.
- Chưa nối với G-09/G-10.
