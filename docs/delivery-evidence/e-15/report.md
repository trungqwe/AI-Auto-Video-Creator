# Báo cáo bằng chứng E-15

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 6945c76b1b309084663e2e0a6b2b668bebad88fc
- Nguồn quyền: IMPL-PLAN-E Auditor PASS và slice E-15 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider (chạy với khung stub ở bước 1 và 2)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 41 failed, 6 passed in 0.93s
- Chi tiết các test FAILED tiêu biểu kèm thông điệp:
  - FAILED tests/unit/voice/test_e15_ports_memory.py::test_append_latest_and_revisions: NotImplementedError trong InMemoryUnitOfWork.__enter__
  - FAILED tests/unit/voice/test_e15_ports_memory.py::test_write_outside_transaction_is_rejected: NotImplementedError trong InMemoryOutputRepository.append
  - FAILED tests/unit/voice/test_e15_ports_memory.py::test_builder_returns_controlplane_domain_event[ImageSafetyAssessed]: NotImplementedError trong build_image_safety_assessed
  - FAILED tests/unit/voice/test_e15_ports_memory.py::test_fixture_valid_envelope_has_no_issues: NotImplementedError trong envelope_issues
  - FAILED tests/unit/voice/test_e15_ports_memory.py::test_deduplication_id_for_is_stable: NotImplementedError trong build_voice_ready
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 6 test (các test kiểm tra frozen instance và ràng buộc binding tĩnh) đã PASS. Tất cả 41 test thất bại đều do method stub ném NotImplementedError.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider (chạy sau khi cài đặt logic hoàn chỉnh)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 47 passed in 0.08s

## Thay đổi

- Bốn tệp thuộc owned paths và vai trò từng tệp:
  - src/voice/ports/repositories.py: Định nghĩa protocol OutputRepository append-only (append, latest, revisions), dataclass StoredOutput, EventContext có xác thực ISO-8601 timestamp và trường không rỗng, hàm envelope_issues kiểm tra cấu trúc phong bì và an toàn payload, deduplication_id_for, và 4 event builder build_image_safety_assessed, build_media_processing_completed, build_voice_ready, build_word_timing_ready trả DomainEvent của controlplane.
  - src/voice/adapters/memory.py: Triển khai InMemoryOutputRepository append-only với ràng buộc đơn điệu revision và tính duy nhất theo voice_hash / timing_artifact_ref; InMemoryOutboxWriter kế thừa controlplane.domain.interfaces.outbox.IOutboxWriter và dedup theo deduplication_id; InMemoryUnitOfWork kế thừa controlplane.domain.interfaces.uow.IUnitOfWork quản lý transaction active và rollback toàn bộ kho outputs và outbox.
  - tests/unit/voice/test_e15_ports_memory.py: Bộ kiểm thử 47 test cases bao quát: Phần 1 (OutputRepository append-only, từ chối ghi đè/xóa, kiểm tra kiểu bản ghi, duy nhất hash/ref, freeze StoredOutput); Phần 2 (UoW và outbox triển khai interface controlplane, commit bền vững, rollback hủy toàn bộ cả outputs và outbox, dedup outbox, từ chối payload không an toàn hoặc bytes); Phần 3 (4 builder trả DomainEvent chuẩn, chỉ ref/hash/revision, kiểm tra cờ artifact_verified bắt buộc True, spy payload guard); Phần 4 (EventContext, dedup id ổn định, fixture envelope hợp lệ và 4 case không hợp lệ, hằng số khớp binding, ranh giới import cô lập không I/O).
  - docs/delivery-evidence/e-15/report.md: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Ánh xạ phản ví dụ -> test:
  - Tạo IUnitOfWork/IOutboxWriter/DomainEvent mới: test_sources_reuse_controlplane_types_and_respect_boundaries
  - Ghi đè voice cũ: test_same_or_skipped_revision_is_rejected_and_keeps_old và test_repository_has_no_overwrite_or_delete_api
  - Rollback để lại outbox: test_exit_without_commit_rolls_back_outputs_and_outbox và test_explicit_rollback_removes_new_revision_but_keeps_committed
  - Phát VoiceReady khi chưa verify: test_unverified_artifact_is_rejected
  - Payload chứa byte âm thanh: test_audio_bytes_or_bad_hash_in_payload_is_rejected

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider | 0 | 47 passed in 0.08s |
| 2 | python -m pytest tests/unit/voice -q -p no:cacheprovider | 0 | 650 passed, 49 subtests passed in 1.16s |
| 3 | git diff --check | 0 | PASS (không output, không trailing whitespace) |

## Quyết định mặc định (D8)

1. kind 'voice' và 'word_timing' có chỉ mục duy nhất voice_hash/timing_artifact_ref trên mọi key và revision, kind khác nhận chuỗi không rỗng;
2. revision mới phải bằng revision mới nhất + 1, sai thì RevisionConflictError của controlplane;
3. payload chỉ ref/hash/revision, ImageSafetyAssessed không mang outcome (GIẢ ĐỊNH, consumer đọc assessment qua ref);
4. aggregate_type ImageSafetyAssessment/ProcessingOperation/VoiceTrack/WordTiming, contract_name 'voice.events', contract_version 1, producer 'E' là GIẢ ĐỊNH đến khi đăng ký catalog ở CONV-E-10;
5. builder và validator envelope nằm trong src/voice/ports/repositories.py vì owned paths chỉ có hai tệp nguồn;
6. id và thời điểm sự kiện do EventContext cung cấp, không dùng clock hay uuid;
7. deduplication_id = workspace_id:event_name:aggregate_id:aggregate_revision;
8. không có persistence PostgreSQL (CONV-E-01) và không phát event vô hiệu hóa timing.

## coveredIds

- CT-EVT-002, CT-EVT-003 (phía E)
- TST-INT-INV-008 (phía E)

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane.
- Chỉ dùng stdlib và controlplane domain.
- Không gọi dịch vụ thật.
