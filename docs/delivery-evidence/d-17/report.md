# Báo cáo bằng chứng D-17

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: bb8fe184f25fbe36ed0bdefa1bbffb162c1d4634
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-17 trong docs/implementation/d/slices.md, ủy quyền AI_SETUP.

## RED

- Lệnh thực thi: python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider (chạy với khung skeleton ở bước 1-4)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 20 failed, 2 passed in 0.48s
- Vài test FAILED tiêu biểu kèm thông điệp NotImplementedError:
  - FAILED tests/unit/creative/test_d17_trace_projection.py::test_trace_walks_output_back_to_every_origin[script-script-key]: NotImplementedError: D-17 RED skeleton: trace_output
  - FAILED tests/unit/creative/test_d17_trace_projection.py::test_trace_payload_is_json_safe_immutable_and_fresh: NotImplementedError: D-17 RED skeleton: trace_output
  - FAILED tests/unit/creative/test_d17_trace_projection.py::test_revision_history_keeps_every_revision_without_overwrite: NotImplementedError: D-17 RED skeleton: list_output_revisions
  - FAILED tests/unit/creative/test_d17_trace_projection.py::test_workspace_filter_never_returns_another_workspaces_output: NotImplementedError: D-17 RED skeleton: list_outputs
  - FAILED tests/unit/creative/test_d17_trace_projection.py::test_chain_from_another_workspace_is_rejected[plan-plan-key-analysis.trace.prompt_ref]: NotImplementedError: D-17 RED skeleton: trace_output
  - FAILED tests/unit/creative/test_d17_trace_projection.py::test_broken_chain_fails_closed_with_fixed_codes[over0-snapshot_missing-snapshot]: NotImplementedError: D-17 RED skeleton: trace_output
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test AST/docstring (test_module_is_pure_read_only_code, test_test_module_declares_covered_ids) đã PASS; 20 test nghiệp vụ FAILED đúng oracle với NotImplementedError('D-17 RED skeleton: ...').

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 22 passed in 0.18s

## Thay đổi

- Ba tệp thuộc owned paths và vai trò từng tệp:
  - src/creative/projections/trace_queries.py: Khai báo InvocationRef, TraceLink, RevisionEntry, InvocationTrace, OutputTrace; các hàm công khai trace_output, list_output_revisions, list_outputs; các helper truy vết read-only (_index, _check_query, _repository, _fingerprint, _stored, _require, _same_workspace, _snapshot_section, _analysis_section, _angle_section, _invocation), không gọi AI, không ghi kho, lọc nghiêm ngặt theo workspace, mã lỗi cố định không rò rỉ dữ liệu lưu trữ, và luôn redact lỗi invocation.
  - tests/unit/creative/test_d17_trace_projection.py: Bộ kiểm thử đơn vị gồm 22 test cases kiểm tra toàn diện: truy vết output về snapshot, analysis, angle, AI invocations; tính bất biến và JSON-safe của payload; bảo toàn lịch sử revision không ghi đè; lọc theo workspace và từ chối truy vết chuỗi khác workspace; xử lý chuỗi đứt và thiếu prompt revision fail-closed; từ chối đầu vào không hợp lệ; bảo đảm không gọi AI và không mở socket; bảo đảm không lộ canary secret hay lỗi chưa redact; bảo đảm chỉ gọi các API đọc (get, latest, revisions) và không thay đổi trạng thái UoW; kiểm tra tĩnh AST không có lời gọi mutation/write hay import cấm; xác nhận docstring coveredIds.
  - docs/delivery-evidence/d-17/report.md: Báo cáo bằng chứng nghiệm thu theo đúng quy chuẩn.

## Ánh xạ phản ví dụ -> test

- Trả output workspace khác -> test_workspace_filter_never_returns_another_workspaces_output và test_chain_from_another_workspace_is_rejected
- Trace thiếu prompt revision -> test_trace_without_prompt_revision_is_rejected và test_broken_chain_fails_closed_with_fixed_codes
- Query kích hoạt AI -> test_query_never_invokes_ai_and_opens_no_connection (số lượt gọi fake không đổi sau truy vấn, socket bị chặn) và test_module_is_pure_read_only_code
- Kết quả chứa canary secret -> test_trace_never_exposes_secret_or_unredacted_error
- Ghi repository -> test_query_is_read_only

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider | 0 | 22 passed in 0.18s |
| 2 | python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider | 0 | 9 passed, 46 subtests passed in 0.09s |
| 3 | git diff --check | 0 | PASS (không output, không lỗi khoảng trắng) |

## Quyết định mặc định (D8)

1. TraceLink do caller cấp (GIẢ ĐỊNH, vì ScriptVersion, ProductionPlan, VariantValidationResult, OutputMetadata chưa mang ref ngược; D-14/CONV-D-02 sẽ điền khi dựng pipeline);
2. angle set được tìm theo repository key và revision vì port không có API liệt kê;
3. lọc workspace theo TraceLink, kiểm chéo bằng workspace của prompt_ref analysis, evidence_refs của angle, source_refs của script;
4. lỗi trace dùng mã cố định, không chứa giá trị lưu;
5. error invocation luôn qua redact_error lần nữa;
6. trace không chứa nội dung output;
7. không persistence PostgreSQL, không đăng ký catalog (CONV-D-01, CONV-D-10).

## coveredIds

- acceptance §12 mục 7, exit gate G1.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane.
- Chỉ stdlib và domain/ports của creative.
- Không gọi dịch vụ thật.
