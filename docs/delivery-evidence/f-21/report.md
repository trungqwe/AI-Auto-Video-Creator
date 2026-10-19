# Báo cáo bằng chứng F-21

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 5c8e6691fb622d08054ca24cca359cf4f5f302b5
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-21 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider (ở bước 14 trên stub trung tính)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 16 failed, 1 passed in 0.36s
- Các dòng FAILED tiêu biểu:
  - FAILED tests/unit/render/test_f21_trace_projection.py::test_trace_output_walks_back_to_attempt_package_inputs_tool_command_and_gates: NotImplementedError: F-21 RED skeleton: trace_output
  - FAILED tests/unit/render/test_f21_trace_projection.py::test_history_lists_every_revision_and_attempt_without_overwriting: NotImplementedError: F-21 RED skeleton: trace_attempt
  - FAILED tests/unit/render/test_f21_trace_projection.py::test_four_milestones_stay_four_independent_facts[False-False]: NotImplementedError: F-21 RED skeleton: trace_output
  - FAILED tests/unit/render/test_f21_trace_projection.py::test_every_query_returns_not_found_for_another_workspace: NotImplementedError: F-21 RED skeleton: trace_render_package
  - FAILED tests/unit/render/test_f21_trace_projection.py::test_queries_never_call_renderer_or_probe_and_only_read: NotImplementedError: F-21 RED skeleton: trace_render_package
  - FAILED tests/unit/render/test_f21_trace_projection.py::test_trace_quality_report_lists_gates_with_evidence_and_blocking_gates: NotImplementedError: F-21 RED skeleton: trace_quality_report
- Xác nhận: không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection; RED hợp lệ do stub NotImplementedError 'F-21 RED skeleton'.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 17 passed in 0.09s

## Thay đổi

- src/render/projections/trace_queries.py: Cung cấp các dataclass view bất biến và bốn query truy vết read-only (trace_render_package, trace_attempt, trace_quality_report, trace_output), đọc qua TraceStore và TraceLink, lọc theo workspace, bốn mốc độc lập và redact dữ liệu nhạy cảm.
- tests/unit/render/test_f21_trace_projection.py: 17 ca kiểm thử bao phủ toàn diện việc truy vết ngược từ output, lịch sử revision/attempt không ghi đè, bốn mốc độc lập, phân tách workspace an toàn, không gọi renderer/probe và kiểm tra AST không có quyền mutation.
- docs/delivery-evidence/f-21/report.md: Báo cáo bằng chứng thực thi này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider | 0 | 17 passed in 0.09s |
| 2 | git diff --check | 0 | PASS (không có output, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Bản ghi F không có workspace nên TraceLink mang workspace_id, quality_report_key, upload_verified (I), completion_committed (G), đây là GIẢ ĐỊNH chờ CONV-F-01.
2. Package chưa có attempt thì chưa có link nên chưa truy vết được.
3. Preset chỉ hiển thị preset_revision_ref vì F chưa có cổng tra preset theo ref, GIẢ ĐỊNH.
4. Nguồn truy vết là TraceStore phía đọc của RenderRepository (InMemoryUnitOfWork có cùng hình dạng), không import adapter.
5. Text được redact lại bằng _redact của F-11 rồi che hẳn nếu còn giống secret hay traceback, command spec chỉ lấy redacted_argv.
6. Bốn mốc là bốn cờ tách biệt, không có cờ gộp.
7. Mỗi package chỉ có một revision vì repository F-16 chặn trùng package_fingerprint, lịch sử revision của package vì vậy có một phần tử, attempt có nhiều revision.

## Ánh xạ phản ví dụ

- Query kích hoạt render -> test_queries_never_call_renderer_or_probe_and_only_read và test_source_has_no_write_render_or_probe_capability.
- Trả output của workspace khác -> test_every_query_returns_not_found_for_another_workspace và test_workspace_b_trace_holds_nothing_of_workspace_a.
- Trace lộ argv chưa redact -> test_unredacted_stored_values_never_reach_a_trace.
- Gộp bốn mốc thành một cờ -> test_four_milestones_stay_four_independent_facts và test_render_succeeded_qc_failed_and_failed_render_are_reported_separately.

## coveredIds

- CT-RND-004, CT-QC-001 (truy vết), TST-E2E-001 (truy vết ngược từ output).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không thay đổi binding, fixture, pyproject.toml hay uv.lock.
- Không gọi dịch vụ thật, không truy cập tài nguyên ngoài vùng cho phép.
