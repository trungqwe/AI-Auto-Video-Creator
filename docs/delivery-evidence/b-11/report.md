# Báo cáo bằng chứng B-11

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d3b0cff0a6c39bb4cce7451ff61435358b50a768`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-11 trong `docs/implementation/b/slices.md`; D3 user duyệt Phần B ngày 18/10/2026; CT-WF-003, CT-WF-006, D8-B-11, D8-B-12.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider` (chạy trên skeleton stub của `activity_handler.py`)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `61 failed, 6 passed in 0.58s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_activity_handler.py::test_fixture_valid_payloads_have_no_binding_issues[ActivityResult] - AssertionError: assert [('wrong_type', '$')] == []`
  - `FAILED tests/unit/ingestion/test_ingestion_activity_handler.py::test_fixture_invalid_case_returns_expected_issue[missing_operation_key] - AssertionError: assert [] == [('missing_required', 'operation_key')]`
  - `FAILED tests/unit/ingestion/test_ingestion_activity_handler.py::test_rejected_request_never_loads_resolves_or_builds_a_result[other_activity] - Failed: DID NOT RAISE ActivityRequestError`
  - `FAILED tests/unit/ingestion/test_ingestion_activity_handler.py::test_succeeded_result_has_every_required_field_and_grant_from_request - AssertionError: assert [ValidationIssue(code='wrong_type', field='$')] == []`
  - `FAILED tests/unit/ingestion/test_ingestion_activity_handler.py::test_failed_attempt_is_not_stored_so_the_same_key_resolves_again - AssertionError: assert None == 'failed'`
- Xác nhận: Hoàn toàn không có `ImportError`, `ModuleNotFoundError`, `SyntaxError` hay lỗi collection; 6 test PASS trên skeleton là các test so khớp constants binding, forbidden fields, fixture hợp lệ của ActivityRequest, non-mapping payload của ActivityResult và kiểm tra biên import của source; 61 test còn lại FAILED do `AssertionError` hoặc `Failed: DID NOT RAISE`.

## Thay đổi

- `src/ingestion/application/activity_handler.py`:
  - Hằng số: `ACTIVITY_NAME`, `FORBIDDEN_FIELD`, `INVALID_VALUE`, `OPERATION_KEY_CONFLICT`, `KIND_ACTIVITY_RESULT`, `REF_TYPE_RESOLUTION`, `SUCCEEDED`, `FAILED`, `REQUEST_REQUIRED`, `REQUEST_OPTIONAL`, `REQUEST_FORBIDDEN`, `RESULT_REQUIRED`, `RESULT_OPTIONAL`, `RESULT_ENUM`, `GRANT_FIELDS`, `_PROBLEM_MESSAGES`.
  - Exception & Dataclass:
    - `ActivityRequestError`: lỗi thẩm tra request `VALIDATION_ERROR`, từ chối ngay trước khi tra cứu, tải package hay ghi dữ liệu; không dựng `ActivityResult` (D8-B-12).
    - `ResolveActivityDeps`: chứa `uow`, `tier_lookup`, `id_factory`, `dedup_policy`, `topic_rules`.
  - Helpers private: `_RFC3339_RE`, `_is_rfc3339`, `_matches`, `_is_token`, `_field_issues`, `_is_ref`, `_grant_issues`, `_utc`, `_problem`, `_stored_result`, `_store_result`.
  - Hàm kiểm tra và xử lý activity:
    - `validate_activity_request(payload)`: kiểm tra ActivityRequest theo binding `g-activity-execution` (các trường bắt buộc, kiểu dữ liệu, cấm `secret_value` và `raw_blob`).
    - `validate_resolve_request(payload)`: kiểm tra luật ResolveCollectedDocument (`activity_name == ResolveCollectedDocument`, `operation_key` không rỗng, đúng 1 `input_ref`, `execution_grant` đầy đủ hợp lệ).
    - `validate_activity_result(payload)`: kiểm tra ActivityResult theo binding `g-activity-execution`.
    - `handle_resolve_activity(request, package_loader, deps, clock)`: thực thi activity resolve một document trong unit of work độc lập; trả về kết quả `succeeded` kèm `output_refs` dạng `collected_document_resolution` khi thành công; xử lý lỗi retryable (`OSError`) và non-retryable (`LookupError`, lỗi cấu trúc package); lưu và tái sử dụng kết quả succeeded theo `operation_key`, phát hiện xung đột key.
- `tests/unit/ingestion/test_ingestion_activity_handler.py`:
  - 67 test items bao quát toàn diện các yêu cầu binding CT-WF-003, CT-WF-006, luật nghiệm thu D8-B-12, kịch bản lỗi độc lập giữa hai request EG-M3-5, tính lũy quyền theo operation_key và biên import CHECK-B.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider` | 0 | 67 passed in 0.11s |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.05s |

## Quyết định mặc định (D8)

(Ghi nhận dưới dạng GIẢ ĐỊNH theo quy chế D8, chưa duyệt chính thức):
1. `package_loader` nhận `input_ref` và trả package, `deps` là `ResolveActivityDeps(uow, tier_lookup, id_factory, dedup_policy, topic_rules)`.
2. Output ref là ref_type `collected_document_resolution`, ref_id `<collected_document_id>:<dedup_policy_revision>`, ref_type của input_ref không bị ràng buộc giá trị.
3. Request không hợp lệ hoặc thiếu `execution_grant` ném `ActivityRequestError` `VALIDATION_ERROR`, không dựng result, không bịa `grant_id`.
4. `OSError` là failed `FAILED_RETRYABLE` retryable=true, `LookupError` là `FAILED_FINAL`, package sai cấu trúc là `VALIDATION_ERROR` retryable=false, problem không chứa nội dung exception.
5. Chỉ result succeeded được lưu trong `uow.records` kind `activity_result` theo `operation_key`, cùng key khác input_ref là `OPERATION_KEY_CONFLICT`.
6. `recovery_epoch` của event lấy từ `execution_grant`.

## Danh sách chờ user (pendingUserCheckpoint)

- G xác nhận D8-B-12 và giá trị ref_type/ref_id khi nối workflow (REQ-B-CONV-04).
- Adapter PostgreSQL REQ-B-CONV-02.
- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).

## Giới hạn

- Không chạy full suite, không chạy tests/m1, tests/m2.
- Không sửa `ports.py`, `memory.py`, `resolve_document.py`, `package_validation.py`, binding, fixture, `pyproject.toml`, `uv.lock`, `HANDOFF.md`, `README.md`, `CHANGELOG.md`.
- Không gọi dịch vụ thật hay đọc bí mật.
