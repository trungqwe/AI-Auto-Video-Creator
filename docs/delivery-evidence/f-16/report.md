# Báo cáo bằng chứng F-16

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 1f92cf4e3edb03004573fffcc020f5a1b2bc3da6
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-16 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider (ở bước 10 trên stub trung tính)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 37 failed, 1 passed in 0.65s
- Các dòng FAILED tiêu biểu:
  - FAILED tests/unit/render/test_f16_ports_memory_events.py::test_append_latest_and_revisions: TypeError: 'InMemoryUnitOfWork' object does not support the context manager protocol
  - FAILED tests/unit/render/test_f16_ports_memory_events.py::test_repository_has_no_overwrite_or_delete_api: AssertionError: assert False where False = isinstance(InMemoryRenderRepository, RenderRepository)
  - FAILED tests/unit/render/test_f16_ports_memory_events.py::test_uow_and_outbox_implement_controlplane_interfaces: AssertionError: assert False where False = issubclass(InMemoryUnitOfWork, IUnitOfWork)
  - FAILED tests/unit/render/test_f16_ports_memory_events.py::test_render_completed_is_a_controlplane_domain_event: AssertionError: assert NoneType is DomainEvent
  - FAILED tests/unit/render/test_f16_ports_memory_events.py::test_output_quality_checked_input_validation: Failed: DID NOT RAISE AttemptNotSucceededError
  - FAILED tests/unit/render/test_f16_ports_memory_events.py::test_fixture_envelopes: AssertionError: Failed case producer_outside_modules: expected enum_violation producer, got empty
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED hợp lệ do assertion và thiếu hành vi ở stub trung tính.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 38 passed in 0.12s

## Thay đổi

- src/render/ports/repositories.py: Protocol RenderRepository append-only (append, latest, revisions), RECORD_TYPES ba kind, DuplicateRecordError, ImmutableFieldError, StoredRecord frozen.
- src/render/domain/events.py: EventContext frozen có validate, envelope_issues kiểm tra theo binding, deduplication_id_for, builder build_render_completed và build_output_quality_checked trả DomainEvent của controlplane sau khi qua ensure_safe_event_payload.
- src/render/adapters/memory.py: InMemoryUnitOfWork kế thừa IUnitOfWork, InMemoryOutboxWriter kế thừa IOutboxWriter, InMemoryRenderRepository với kiểm tra trùng lặp và tính bất biến, rollback hoàn tác đồng thời bản ghi và outbox.
- tests/unit/render/test_f16_ports_memory_events.py: 35 hàm test với 38 ca kiểm thử bao phủ toàn diện repository append-only, UoW in-memory, outbox dedup, builder event an toàn và envelope fixture.
- docs/delivery-evidence/f-16/report.md: báo cáo bằng chứng này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider | 0 | 38 passed in 0.12s |
| 2 | probe không còn marker STUB-F16 | 0 | PASS (không còn STUB-F16 trong ba tệp nguồn) |
| 3 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider | 0 | 12 passed, 75 subtests passed in 0.17s |
| 4 | probe tiếng Việt của report.md | 0 | PASS (tiếng Việt đầy đủ dấu, không ký tự thay thế, không dấu hỏi chấm) |
| 5 | git diff --check | 0 | PASS (không có output, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Ba kind được hỗ trợ là render_package, render_attempt và quality_report theo thiết kế kiến trúc của phân hệ F.
2. Revision lưu là chuỗi số nguyên tăng dần từ 1 của repository, độc lập với RenderAttempt.revision (bắt đầu từ 0).
3. Khoá key phải bằng render_package_id hoặc render_attempt_id, package là bất biến (một revision duy nhất), attempt giữ nguyên package_fingerprint và output_artifact_ref qua các revision, output_artifact_ref không dùng chung giữa hai attempt khác nhau.
4. GIẢ ĐỊNH: OutputQualityChecked cũng yêu cầu attempt ở trạng thái SUCCEEDED vì quy trình kiểm định chất lượng cần tệp output tồn tại, sự kiện vẫn được phát khi kết quả kiểm định báo không đạt (QC fail).
5. Tên các trường payload là GIẢ ĐỊNH, builder không bao giờ sao chép error, warnings hay command_spec vào payload sự kiện.
6. aggregate_revision của RenderCompleted lấy từ attempt.revision, còn của OutputQualityChecked do bên gọi cung cấp.
7. recovery_epoch là chuỗi ký tự theo quy định của binding domain-event-envelope.
8. EventContext và envelope_issues được viết cục bộ trong F vì F không được phép import chéo sang voice hay creative; đề xuất hợp nhất về controlplane tại thời điểm CONV-F-10.
9. Tầng lưu trữ lâu dài PostgreSQL thuộc phạm vi CONV-F-01 và cơ chế đăng ký publisher dùng chung thuộc CONV-F-10, không triển khai trong slice này.

## Ánh xạ phản ví dụ

- Tạo IUnitOfWork, IOutboxWriter hay DomainEvent mới -> test_sources_reuse_controlplane_types_and_respect_boundaries.
- Ghi đè attempt cũ -> test_same_or_skipped_revision_is_rejected_and_keeps_old và test_new_revision_cannot_change_identity_fields.
- Rollback để lại outbox -> test_exit_without_commit_rolls_back_records_and_outbox và test_explicit_rollback_removes_new_revision_but_keeps_committed.
- RenderCompleted cho attempt lỗi -> test_render_completed_rejects_attempt_that_is_not_succeeded.
- Event chứa argv hoặc bí mật -> test_payload_holds_only_refs_hashes_revisions_and_gate_summary và test_canary_never_reaches_events_or_outbox.

## coveredIds

- CT-EVT-002, CT-EVT-003, TST-SEC-INV-012.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không thay đổi binding, fixture, pyproject.toml hay uv.lock.
- Không gọi dịch vụ thật, không truy cập tài nguyên ngoài vùng cho phép.
