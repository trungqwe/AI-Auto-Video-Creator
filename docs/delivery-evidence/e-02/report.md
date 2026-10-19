# Báo cáo bằng chứng E-02

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: c8514bd1ba916e7be55561659dce0661e7c7e81e
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-02 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 57 failed, 8 passed in 0.47s
- Chi tiết các test FAILED kèm thông điệp:
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_input_fingerprint_uses_controlplane_request_hash: AssertionError: assert '' == '49d1d31eb95ca5105b77cebf23678f0817c1086ab5b9366ee5b0ab0bab517a7c'
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_input_fingerprint_changes_with_one_hash_or_revision: AssertionError: assert '' != ''
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_artifact_ref_rejects_uppercase_sha256_from_fixture: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_artifact_ref_rejects_bad_sha256[...-wrong_type]: Failed: DID NOT RAISE ProcessingContractError (5 ca biến thể sha sai độ dài hoặc không phải hex thường)
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_artifact_ref_rejects_bad_sha256[None-missing_required]: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_request_missing_field_from_mapping[...]: Failed: DID NOT RAISE ProcessingContractError (8 ca cho đủ 8 trường REQUEST_FIELDS)
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_request_none_field_in_constructor[...]: Failed: DID NOT RAISE ProcessingContractError (8 ca cho đủ 8 trường REQUEST_FIELDS)
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_result_missing_field_from_mapping[...]: Failed: DID NOT RAISE ProcessingContractError (8 ca cho đủ 8 trường RESULT_FIELDS)
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_result_none_field_in_constructor[...]: Failed: DID NOT RAISE ProcessingContractError (8 ca cho đủ 8 trường RESULT_FIELDS)
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_processor_identity_rules: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_disposition_coercion_and_enum_violation: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_models_are_frozen: AssertionError: assert [ArtifactRef(...), ArtifactRef(...)] is tuple
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_result_cross_field_constraints: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_validate_result_for_request: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_is_ready_only_when_succeeded_and_all_outputs_verified: AssertionError: assert True is False
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_is_ready_rejects_bare_string_verified_refs: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_retention_intent_plan_section_7[...]: AssertionError: assert <OutputClass.REUSABLE: 'reusable'> != <OutputClass.REUSABLE: 'reusable'> (voice ra reusable thay vì per_video)
  - FAILED tests/unit/voice/test_e02_processing_contract.py::test_retention_intent_invalid_kind: Failed: DID NOT RAISE ProcessingContractError
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (RED là sai oracle trên khung tối thiểu).

## Thay đổi

- 3 tệp owned:
  - src/voice/domain/processing.py
  - 	ests/unit/voice/test_e02_processing_contract.py
  - docs/delivery-evidence/e-02/report.md
- Danh mục API đã triển khai trong src/voice/domain/processing.py:
  - Disposition: enum.StrEnum (SUCCEEDED, FAILED, WAITING, OUTCOME_UNKNOWN)
  - OutputClass: enum.StrEnum (REUSABLE, PER_VIDEO, DIAGNOSTIC)
  - ArtifactRef: frozen dataclass (ef, content_sha256) kiểm tra sha256 64 ký tự hex thường
  - ProcessingRequest: frozen dataclass đủ 8 trường CT-PROC-001 kèm rom_mapping và property input_fingerprint
  - ProcessingResult: frozen dataclass đủ 8 trường CT-PROC-002 kèm rom_mapping, ràng buộc chéo và kiểm tra processor_identity
  - compute_input_fingerprint: tính canonical request_hash từ controlplane, bất biến theo thứ tự khóa
  - is_ready: kiểm tra điều kiện ready fail-closed (chỉ True khi succeeded, có output và toàn bộ output refs đã verify bởi I)
  - etention_intent: phân loại vòng đời lưu trữ theo đúng kế hoạch §7
  - alidate_result_for_request: kiểm tra đối chiếu request/result, cấm trùng lặp output ref với input ref và kiểm tra fingerprint khớp
  - RETENTION_INTENT_BY_KIND: mapping bất biến ánh xạ loại output sang OutputClass

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider | 0 | 65 passed in 0.11s |
| 2 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 9 passed, 49 subtests passed in 0.06s |
| 3 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Phản ví dụ đã loại trừ

1. **Succeeded ready khi I chưa verify:** Loại trừ bởi 	est_is_ready_only_when_succeeded_and_all_outputs_verified; is_ready chỉ trả về True khi mọi output ref đều nằm trong tập erified_refs do I cấp, nếu thiếu hoặc tập rỗng lập tức trả False.
2. **Thiếu processor_identity vẫn hợp lệ:** Loại trừ bởi 	est_processor_identity_rules; processor_identity bắt buộc phải là Mapping có đủ hai khóa 	ool và ersion không rỗng, nếu thiếu hoặc rỗng sẽ ném ProcessingContractError mã missing_required.
3. **Output ghi đè input:** Loại trừ bởi 	est_validate_result_for_request; hàm đối chiếu phát hiện output ref có ID trùng với bất kỳ input ref nào và ném lỗi constraint_violation trên trường output_artifact_refs.
4. **Voice xếp reusable:** Loại trừ bởi 	est_retention_intent_plan_section_7; etention_intent('voice') trả về OutputClass.PER_VIDEO, tuyệt đối khác OutputClass.REUSABLE.
5. **E có hàm cleanup:** Loại trừ bởi 	est_module_has_no_delete_or_cleanup; module được kiểm tra AST toàn diện, không có bất kỳ hàm, phương thức, biến hay thuộc tính nào chứa các từ khóa cấm liên quan đến xóa hay dọn dẹp tài nguyên.

## Quyết định mặc định (D8)

1. output_storage_intent là chuỗi không rỗng, không dựng enum mới vì CT-PROC-001 chưa chốt tập giá trị cố định.
2. ArtifactRef(ref, content_sha256) mang hash để tính input_fingerprint.
3. processor_identity bắt buộc hai khóa 	ool và ersion kiểu chuỗi không rỗng.
4. operation_receipt_ref chỉ được phép là None khi disposition khác SUCCEEDED; khi SUCCEEDED bắt buộc phải có receipt ref.
5. Disposition SUCCEEDED bắt buộc có ít nhất một output artifact ref (output_artifact_refs không được rỗng).
6. is_ready nhận tập ref ID đã verify từ I (E không tự verify) và trả False khi không có output ref nào.
7. etention_intent thực hiện fail-closed: loại kind lạ chưa định nghĩa sẽ ném constraint_violation.
8. Bảng retention tuân thủ đúng kế hoạch IMPL-PLAN-E §7 (RETENTION_INTENT_BY_KIND).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-007 cho expected_output_profile
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, không chạy tests/m1, tests/m2.
- Không sửa đổi pyproject.toml hay uv.lock.
- Không gọi dịch vụ thật hay FFmpeg.
- Không sửa đổi migration hay composition root.