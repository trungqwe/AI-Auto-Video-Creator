# Báo cáo bằng chứng D-13

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 1f6f35d6bfb9063eb24c83d688e22821842c5e67
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-13 trong docs/implementation/d/slices.md, ủy quyền AI_SETUP.

## RED

- Lệnh thực thi: python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider (chạy với khung stub ở bước 1-3)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 58 failed, 7 passed in 1.07s
- Chi tiết các test FAILED tiêu biểu kèm thông điệp NotImplementedError:
  - FAILED tests/unit/creative/test_d13_ports_memory.py::test_snapshot_id_is_unique: NotImplementedError: D-13 RED skeleton trong InMemoryUnitOfWork.__enter__
  - FAILED tests/unit/creative/test_d13_ports_memory.py::test_append_only_keeps_every_revision[analyses]: NotImplementedError: D-13 RED skeleton trong InMemoryUnitOfWork.__enter__
  - FAILED tests/unit/creative/test_d13_ports_memory.py::test_begin_twice_and_finish_without_begin: NotImplementedError: D-13 RED skeleton trong InMemoryUnitOfWork.begin
  - FAILED tests/unit/creative/test_d13_ports_memory.py::test_builder_returns_controlplane_domain_event[ProductionSnapshotCommitted]: NotImplementedError: D-13 RED skeleton trong build_production_snapshot_committed
  - FAILED tests/unit/creative/test_d13_ports_memory.py::test_fixture_valid_envelope_has_no_issues: NotImplementedError: D-13 RED skeleton trong envelope_issues
  - FAILED tests/unit/creative/test_d13_ports_memory.py::test_deduplication_id_for_is_stable: NotImplementedError: D-13 RED skeleton trong build_script_version_created
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 7 test kiểm tra frozen instance, cấu trúc protocol, bindings tĩnh và ranh giới import tĩnh đã PASS. Các test thất bại đều do method/hàm skeleton ném NotImplementedError('D-13 RED skeleton').

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider (chạy sau khi cài đặt logic hoàn chỉnh)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 65 passed in 0.13s

## Thay đổi

- Bốn tệp thuộc owned paths và vai trò từng tệp:
  - src/creative/ports/repositories.py: Định nghĩa các protocol kho append-only (SnapshotRepository, AppendOnlyRepository, AnalysisRepository, AngleSetRepository, ScriptRepository, PlanRepository, VariantValidationRepository, OutputMetadataRepository, InvocationRecordRepository, ReceiptStore), dataclass StoredRecord và CommandReceipt, EventContext có xác thực ISO-8601 timestamp và trường không rỗng, hàm envelope_issues kiểm tra cấu trúc phong bì và an toàn payload theo fixture/binding, deduplication_id_for, và 6 event builder trả DomainEvent của controlplane (build_production_snapshot_committed, build_story_angles_generated, build_script_version_created, build_production_plan_created, build_variant_validated, build_output_metadata_created) với producer 'D'.
  - src/creative/adapters/memory.py: Triển khai InMemorySnapshotRepository (snapshot_id duy nhất toàn kho), InMemoryAppendOnlyRepository (append-only theo kind/key, revision tăng dần nghiêm ngặt, chỉ mục duy nhất set_id/script_version_id/production_plan_id, khớp định danh analysis_id/revision và source_job_ref/metadata_revision), InMemoryReceiptStore (idempotent theo workspace_id và idempotency_key), InMemoryOutboxWriter (kế thừa controlplane IOutboxWriter, dedup theo deduplication_id), và InMemoryUnitOfWork (kế thừa controlplane IUnitOfWork, quản lý giao dịch active và rollback nguyên tử toàn bộ 10 kho dữ liệu kể cả outbox).
  - tests/unit/creative/test_d13_ports_memory.py: Bộ kiểm thử đơn vị gồm 65 test cases bao quát: Phần 1 (Kho bản ghi append-only, từ chối ghi đè/xóa, kiểm tra kiểu bản ghi, duy nhất snapshot_id, chỉ mục duy nhất bản ghi, freeze StoredRecord); Phần 2 (ReceiptStore append-only, CommandReceipt validation, protocol compliance, không có API overwrite/delete); Phần 3 (UoW và outbox triển khai interface controlplane, commit bền vững, rollback hủy toàn bộ kể cả outbox, dedup outbox, từ chối payload không an toàn hoặc chuỗi rỗng); Phần 4 (6 event builder trả DomainEvent chuẩn của controlplane, payload chỉ ref/revision/fingerprint, spy payload guard, từ chối record sai kiểu hoặc variant không valid); Phần 5 (EventContext, dedup id ổn định, fixture envelope hợp lệ và 4 case không hợp lệ, hằng số khớp binding, ranh giới import cô lập không I/O).
  - docs/delivery-evidence/d-13/report.md: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Ánh xạ phản ví dụ -> test:
  - Ghi đè script cũ: test_new_script_revision_never_overwrites_old và test_repositories_have_no_overwrite_or_delete_api
  - Hai snapshot cùng ID được lưu: test_snapshot_id_is_unique và test_rollback_restores_snapshot_id_uniqueness_slot
  - Tạo IUnitOfWork/IOutboxWriter/DomainEvent mới: test_sources_reuse_controlplane_types_and_respect_boundaries
  - Rollback để lại outbox: test_exit_without_commit_rolls_back_everything, test_exception_in_block_rolls_back_everything_including_outbox và test_explicit_rollback_keeps_committed_revision_only
  - envelope khớp fixture: test_fixture_valid_envelope_has_no_issues, test_fixture_invalid_envelopes, test_builder_envelopes_are_valid_for_all_events

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider | 0 | 65 passed in 0.13s |
| 2 | python -m pytest tests/unit/creative -q -p no:cacheprovider | 0 | 699 passed, 176 subtests passed in 1.32s |
| 3 | git diff --check | 0 | PASS (không output, không trailing whitespace) |

## Quyết định mặc định (D8)

1. append-only theo (kind, key), revision mới phải bằng revision mới nhất + 1, sai thì RevisionConflictError của controlplane;
2. snapshot_id duy nhất toàn kho, lưu bất biến, không có API sửa/xoá;
3. set_id, script_version_id, production_plan_id duy nhất trên mọi key; analysis và output_metadata phải khớp key và revision với chính bản ghi;
4. CommandReceipt là kiểu D-local đặt trong src/creative/ports/repositories.py (GIẢ ĐỊNH, vì D chưa có binding receipt riêng; bảng receipt thật thuộc CONV-D-01), khoá (workspace_id, idempotency_key), put lặp ném DuplicateReceiptError;
5. payload event chỉ chứa ref, revision, fingerprint; contract_name 'creative.events', contract_version 1, producer 'D', aggregate_type theo EVENT_AGGREGATE_TYPES là GIẢ ĐỊNH đến khi đăng ký catalog ở CONV-D-10;
6. recovery_epoch và schema_version là chuỗi theo binding và fixture, dù DomainEvent của controlplane khai báo kiểu int (không ép kiểu lúc chạy);
7. id và thời điểm event do EventContext cung cấp, không dùng clock hay uuid;
8. deduplication_id = workspace_id:event_name:aggregate_id:aggregate_revision;
9. không có persistence PostgreSQL (CONV-D-01), không đăng ký catalog (CONV-D-10).

## coveredIds

- acceptance §12 mục 1 (lưu bất biến)

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane.
- Chỉ dùng stdlib và controlplane domain.
- Không gọi dịch vụ thật.
