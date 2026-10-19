# Báo cáo bằng chứng A-18

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `49a6b2cd63f58127a65fa105b13ced917a842f2d`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS (slice A-18 trong `docs/implementation/a/slices.md`, phụ thuộc A-11).

## RED

- Lệnh thực thi: `python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider`
- Trạng thái mã lúc RED: `handle_collect_source_activity` là stub trả dict failed rỗng (`'execution_generation': -1`, `'disposition': 'failed'`), chưa có validation request/grant hay logic gọi UoW/collect_source.
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `22 failed, 6 passed in 0.36s`
- Test FAILED tiêu biểu nguyên văn:
  - `FAILED tests/integration/collection/test_a18_worker_activity.py::test_current_grant_collects_and_returns_a_succeeded_activity_result` (AssertionError: assert 'failed' == 'succeeded')
  - `FAILED tests/integration/collection/test_a18_worker_activity.py::test_stale_grant_is_rejected_without_any_commit[old_generation]` (AssertionError: assert 'failed' == 'stale')
  - `FAILED tests/integration/collection/test_a18_worker_activity.py::test_invalid_request_raises_before_any_lookup_or_write[missing_operation_key]` (Failed: DID NOT RAISE ActivityRequestError)
  - `FAILED tests/integration/collection/test_a18_worker_activity.py::test_invalid_grant_raises_validation_error[not_an_execution_grant]` (Failed: DID NOT RAISE ActivityRequestError)
- Xác nhận: 0 lỗi import/collection; lỗi RED là assert sai oracle từ stub.

## Thay đổi

- `src/source_ingestion/worker/activity_handler.py`: module handler activity `CollectSource` cho workflow G (A-18, A-RULE-014, A-RULE-016). Định nghĩa `ActivityRequestError`, `InMemoryActivityResultStore`, `CollectActivityDeps`, `validate_collect_request`, `_problem`, `_activity_result`, `_collection_result` và hàm `handle_collect_source_activity`. Nhận `ActivityRequest` cùng `controlplane.domain.orchestration.ExecutionGrant`, xác thực grant qua `ActivityGrantPort`, gọi `collect_source` (A-11), trả `ActivityResult` đã redacted. Grant/generation cũ bị từ chối trả về `stale` không commit; request lặp cùng `operation_key` trả kết quả đã lưu.
- `tests/integration/collection/test_a18_worker_activity.py`: 28 test (bao gồm các ca tham số hoá), FakeAdapter, fixture autouse chặn kết nối mạng socket, docstring ghi `coveredIds: A-RULE-014, A-RULE-016`. Bao phủ toàn bộ các yêu cầu chức năng, phản ví dụ an toàn, và kiểm tra AST xác nhận không import temporalio, controlplane.ui, render, voice, desktop.

## Ánh xạ yêu cầu → test

| Yêu cầu / phản ví dụ | Test |
|---|---|
| Nhận ActivityRequest và ExecutionGrant, gọi CollectSource, trả ActivityResult đầy đủ metrics, warnings, output_refs | `test_current_grant_collects_and_returns_a_succeeded_activity_result` |
| Phản ví dụ: Grant hoặc generation cũ trả stale trước mọi tra cứu hay ghi, không commit | `test_stale_grant_is_rejected_without_any_commit` |
| Phản ví dụ: Generation cũ ghi checkpoint mới bị từ chối dù grant port chấp nhận nhầm | `test_old_generation_checkpoint_write_is_rejected_even_if_the_grant_port_wrongly_accepts_it` |
| Lặp request cùng operation_key trả kết quả cũ đã lưu mà không collect lại | `test_same_operation_key_returns_the_stored_result_without_collecting_again` |
| Grant cũ không nhận kết quả đã lưu của generation mới hơn | `test_stale_grant_does_not_receive_the_stored_result_of_a_newer_generation` |
| Cùng operation_key nhưng input_refs khác nhau trả lỗi OPERATION_KEY_CONFLICT | `test_same_operation_key_with_different_input_refs_is_a_conflict` |
| Kết quả waiting không được lưu và cho phép retry cùng operation_key | `test_waiting_result_is_not_stored_and_the_same_key_can_retry` |
| Item lỗi chuyển thành warning và partial run trả disposition succeeded | `test_item_failure_is_a_warning_and_the_partial_run_is_succeeded` |
| Run FAILED_FINAL trả về disposition failed kèm problem chuẩn | `test_failed_final_run_returns_a_failed_result_with_a_standard_problem` |
| Phản ví dụ: ActivityResult chứa secret từ lỗi adapter | `test_result_never_contains_a_secret_from_adapter_errors` |
| Ngoại lệ thoát khỏi collect_source được bắt và chuyển thành failed redacted | `test_exception_escaping_collect_source_becomes_a_redacted_failed_result` |
| Request không hợp lệ bị từ chối bằng VALIDATION_ERROR trước khi tra cứu hay ghi | `test_invalid_request_raises_before_any_lookup_or_write` |
| Grant không hợp lệ bị từ chối bằng VALIDATION_ERROR | `test_invalid_grant_raises_validation_error` |
| Dùng lại ExecutionGrant từ controlplane, không định nghĩa lớp grant mới | `test_handler_uses_the_controlplane_execution_grant_and_defines_no_grant_class` |
| Handler không import temporalio, controlplane.ui, gói render, voice hay desktop (A-RULE-016) | `test_handler_imports_no_workflow_runtime_ui_render_voice_or_desktop_code` |
| Handler chỉ import stdlib, domain, ports và application | `test_handler_imports_only_stdlib_domain_ports_and_application` |
| Không đăng ký workflow hay activity thông qua decorators | `test_handler_registers_no_workflow_or_activity_through_decorators` |
| Docstring test ghi nhận coveredIds A-RULE-014, A-RULE-016 | `test_module_docstring_lists_the_covered_rule_ids` |
| Toàn bộ suite bị chặn kết nối mạng/DNS | `test_network_is_blocked_for_the_whole_suite` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider` | 0 | 28 passed in 0.14s |
| 2 | `git diff --check` | 0 | passed (không output) |

## Trường lệch binding g-activity-execution (chuyển CONV-A-06)

1. `ExecutionGrant` (`workspace_id`, `operation_id`, `job_id`, `stage_run_id`, `execution_generation: int`, `recovery_epoch: int`) không có `grant_id` nhưng `ActivityResult` bắt buộc `grant_id` kiểu string: handler dùng `operation_id` làm `grant_id` (GIẢ ĐỊNH).
2. `recovery_epoch` là `int` trong `ExecutionGrant` nhưng là `string` trong `ActivityResult`: handler dùng `str(grant.recovery_epoch)`.
3. `workspace_id`, `operation_id`, `job_id` của `ExecutionGrant` không có field tương ứng trong binding `execution_grant`.
4. `ActivityRequest` không có field `source_id`, `business_date`, `workspace_id`: handler lấy `workspace_id` từ `ExecutionGrant`, `source_id` và `business_date` từ hai `input_refs` (`ref_type` `collection_source` và `business_date`) (GIẢ ĐỊNH).
5. Trường tuỳ chọn `ActivityRequest.execution_grant` (`object`) không dùng, grant kiểu `ExecutionGrant` truyền riêng.
6. Binding chưa cố định `activity_name` và `activity_version`: dùng `CollectSource`, `activity_version` chỉ kiểm là string (GIẢ ĐỊNH).

## Quyết định mặc định (D8)

1. `run_id` = `run:<operation_key>`.
2. Chỉ kết quả succeeded (`COMPLETED`, `COMPLETED_PARTIAL`) được lưu theo `(workspace_id, operation_key)`, các kết quả failed, waiting, stale không được lưu.
3. Kiểm tra stale grant trước khi tra cứu kết quả đã lưu.
4. Store in-memory (`InMemoryActivityResultStore`) vì `memory.py` ngoài owned paths, việc lưu bền chờ CONV-A-01 / CONV-A-06.
5. Problem chỉ dùng mã token chuẩn và thông điệp cố định từ `_PROBLEM_MESSAGES`, không bao giờ chứa exception text, URL hay secret. Warnings dạng `CODE:locator` lấy từ ItemError đã redacted của A-11.

## Mục mở / follow-up

- Đăng ký activity với Temporal, lịch cloud, tra grant hiện hành thật thuộc CONV-A-06.
- Chạy cloud thật ở CP7.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full test suite, `tests/m1`, `tests/m2`.
- Không đổi `pyproject.toml` hay `uv.lock`.
- Không gọi mạng thật; adapter là fake và socket bị chặn trong test.
