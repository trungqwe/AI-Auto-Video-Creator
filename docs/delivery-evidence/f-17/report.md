# Báo cáo bằng chứng F-17

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 5c8e6691fb622d08054ca24cca359cf4f5f302b5
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-17 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider (trên stub trung tính: ba phương thức công khai của PackagePipeline raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 34 failed, 2 passed in 0.68s
- Các dòng FAILED tiêu biểu: FAILED tests/integration/render/test_f17_resolve_validate_pipeline.py::test_resolve_stores_one_package_with_succeeded_receipt_and_trace; FAILED tests/integration/render/test_f17_resolve_validate_pipeline.py::test_same_key_and_payload_replays_the_first_receipt_without_a_second_package; FAILED tests/integration/render/test_f17_resolve_validate_pipeline.py::test_valid_package_passes_is_stored_and_reaches_the_renderer_once
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED hợp lệ do hành vi chưa có ở stub trung tính.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 36 passed in 0.16s

## Thay đổi

- src/render/application/package_pipeline.py: PackagePipeline với resolve_render_package, validate_render_package, require_renderable; DTO command, receipt, trace, outcome; GrantCurrencyPort; InMemoryPackageUnitOfWork mở rộng UoW F-16 với bảng reports, receipts, traces; lỗi IdempotencyConflict và StaleGrant mang ProblemDetail.
- tests/integration/render/test_f17_resolve_validate_pipeline.py: 36 ca kiểm thử.
- docs/delivery-evidence/f-17/report.md: báo cáo bằng chứng này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider | 0 | 36 passed in 0.16s |
| 2 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider | 0 | 12 passed, 75 subtests passed in 0.19s |
| 3 | python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider | 0 | 38 passed in 0.16s |
| 4 | python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider | 0 | 62 passed in 0.13s |
| 5 | python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider | 0 | 55 passed in 0.16s |
| 6 | probe không còn marker STUB-F17 | 0 | PASS (không có output, không còn marker STUB-F17) |
| 7 | probe tiếng Việt của report.md | 0 | PASS (UTF-8 không BOM, tiếng Việt đầy đủ dấu, không ký tự thay thế) |
| 8 | git diff --check | 0 | PASS (không có output, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Receipt chỉ được ghi khi command hoàn tất: state SUCCEEDED đi qua transition_operation (PREPARED sang STARTED sang SUCCEEDED, revision 2). Report validate không đạt vẫn là kết quả SUCCEEDED của command, kết luận nằm ở PackageValidationReport.passed.
2. ResolveError, RenderPackageNotFound, StaleGrant và IdempotencyConflict không ghi receipt, bản ghi hay trace; UoW rollback.
3. Khoá idempotency là (workspace_id, command, operation_key); request_hash là request_hash của {command, workspace_id, request} với request là bản sao thuần của đầu vào. ExecutionGrant không nằm trong hash.
4. Grant được kiểm trước mọi lượt đọc hoặc ghi, kể cả replay, qua GrantCurrencyPort; G sở hữu hết hạn, generation và recovery epoch. Khác workspace hoặc không phải ExecutionGrant cũng bị từ chối.
5. Dấu vết là bảng traces của F chỉ chứa id và kết quả. GIẢ ĐỊNH: registry chưa có sự kiện cho resolve hay validate nên không phát outbox event; outbox giữ rỗng.
6. Khoá operation_key mới với đầu vào giống hệt không tạo package thứ hai (render_package_id suy ra từ fingerprint); chỉ ghi receipt và trace mới.
7. Report được lưu append-only theo package_fingerprint; hai report liền nhau có cùng report_id chỉ lưu một.
8. require_renderable dựa trên report mới nhất của package. script_fingerprint và voice_hash không nằm trong package nên F-18 phải chạy lại validate với context hiện hành ngay trước khi render.
9. F-16 không có kind cho report, receipt, trace và memory.py nằm ngoài owned paths nên InMemoryPackageUnitOfWork trong package_pipeline.py kế thừa UoW F-16 (dùng lớp nền nội bộ _Table). Hợp nhất vào adapter lưu trữ khi làm CONV-F-01.

## Ánh xạ phản ví dụ

- Gửi lặp tạo package thứ hai: test_same_key_and_payload_replays_the_first_receipt_without_a_second_package và test_new_key_with_same_inputs_reuses_the_package.
- Validate sau khi hash input đổi vẫn pass: test_changed_script_fingerprint_or_voice_hash_after_the_package_fails_validation.
- Ghi ngoài UoW: test_tables_refuse_writes_outside_a_unit_of_work và test_failure_after_the_record_write_rolls_back_record_receipt_and_trace.
- Package lỗi vẫn tới renderer: test_invalid_package_gives_failed_report_and_the_renderer_is_never_called.
- Khác payload cùng key: test_same_key_with_another_payload_is_idempotency_conflict_problem.
- Grant hết hạn hoặc generation cũ: test_refused_grant_blocks_both_commands_before_any_read_or_write.
- Resolve ghi bảng phân hệ khác: test_resolve_and_validate_write_only_f_tables_and_no_outbox_event và test_module_imports_only_f_and_controlplane_contracts.

## coveredIds

- TST-CTR-INV-001, TST-INT-INV-008, TST-MEDIA-INV-007, CT-RND-002, CT-RND-003, TST-E2E-001 (đoạn resolve và validate).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không thay đổi binding, fixture, pyproject.toml, uv.lock, src/render/adapters/memory.py hay src/render/ports.
- Không gọi dịch vụ thật, không truy cập tài nguyên ngoài vùng cho phép.
