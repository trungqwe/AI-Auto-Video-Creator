# Báo cáo PERSIST-E: adapter PostgreSQL của voice

- Base HEAD (sau cấp lại grant G1): 3fe2c45381923cb139eebc88847f7c43cb87cd81; Control rebase lên cb554068e3a5838a89d67d592ca625f26e0b6397, không có xung đột
- SHA candidate: xem trong worker_done

## 1. Phạm vi và tệp đã tạo

Các tệp đã tạo trong phạm vi owned paths của task PERSIST-E:
- tests/integration/persistence/e/test_persist_e_postgres.py
- src/voice/persistence/errors.py
- src/voice/persistence/serialization.py
- src/voice/persistence/output_repository.py
- src/voice/persistence/outbox.py
- src/voice/persistence/unit_of_work.py
- src/voice/persistence/__init__.py

## 2. Thiết kế chi tiết

- một kết nối từ TransactionManager.borrow_connection() cho outputs và outbox; INSERT trong savepoint;
- ngữ cảnh workspace_id, correlation_id, actor, recovery_epoch lấy từ tham số keyword hoặc bind() của UoW vì port không có workspace_id;
- event_id = uuid5(NAMESPACE_URL, deduplication_id); aggregate_revision lấy từ phần cuối của deduplication_id (mặc định 1);
- schema_version ghi số major 1 vì cột là INTEGER;
- recovery_epoch ghi số khi chuỗi chỉ gồm chữ số, ngược lại NULL (OI-PERSIST-03).

## 3. Bằng chứng kiểm thử RED (Bước 13)

Lệnh thực thi:
python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider

Exit code: 1

Trích nguyên văn các dòng FAILED và assertion thật:
`
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_voice_round_trip_latest_and_revisions
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_word_timing_round_trip_latest_and_revisions
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_outputs_are_scoped_by_workspace
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_revision_must_advance_by_exactly_one[voice-_voice-cp_voice_tracks]
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_revision_must_advance_by_exactly_one[word_timing-_timing-cp_word_timings]
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_voice_hash_is_unique
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_timing_artifact_ref_is_unique
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_rejects_unsupported_kind_bad_arguments_and_wrong_record
FAILED tests/integration/persistence/e/test_persist_e_postgres.py::test_persist_e_commit_stores_output_and_outbox_on_one_connection
FAILED tests/integration/persistence/e/test_persist_e_failure_on_either_side_rolls_back_both
FAILED tests/integration/persistence/e/test_persist_e_outbox_deduplicates_by_deduplication_id
FAILED tests/integration/persistence/e/test_persist_e_unit_of_work_guards
FAILED tests/integration/persistence/e/test_persist_e_connections_return_to_pool
13 failed, 4 passed in 8.74s
`

Chi tiết các assertion thật từ output RED:
- test_persist_e_voice_round_trip_latest_and_revisions: assert latest is not None and latest.revision == 2 -> assert (None is not None)
- test_persist_e_word_timing_round_trip_latest_and_revisions: assert latest is not None and latest.revision == 2 -> assert (None is not None)
- test_persist_e_outputs_are_scoped_by_workspace: AssertionError: assert None is not None
- test_persist_e_revision_must_advance_by_exactly_one[voice]: Failed: DID NOT RAISE RevisionConflictError
- test_persist_e_revision_must_advance_by_exactly_one[word_timing]: Failed: DID NOT RAISE RevisionConflictError
- test_persist_e_voice_hash_is_unique: Failed: DID NOT RAISE DuplicateOutputError
- test_persist_e_timing_artifact_ref_is_unique: Failed: DID NOT RAISE DuplicateOutputError
- test_persist_e_rejects_unsupported_kind_bad_arguments_and_wrong_record: Failed: DID NOT RAISE UnsupportedKindError
- test_persist_e_commit_stores_output_and_outbox_on_one_connection: assert stored is not None and stored.record == voice -> assert (None is not None)
- test_persist_e_failure_on_either_side_rolls_back_both: Failed: DID NOT RAISE ValueError
- test_persist_e_outbox_deduplicates_by_deduplication_id: AssertionError: assert '' != ''
- test_persist_e_unit_of_work_guards: Failed: DID NOT RAISE TransactionNotActiveError
- test_persist_e_connections_return_to_pool: AssertionError: assert 0 == 4

Các test xanh ở bước RED và lý do:
- test_persist_e_schema_matches_migration_0016: kiểm tra schema và triggers append-only của migration 0016 đã có sẵn sau migrate_up()
- test_persist_e_history_tables_reject_update_and_delete: kiểm tra trigger append-only cấm UPDATE và DELETE trên 11 bảng của migration 0016 có sẵn trong DB
- test_persist_e_database_unique_constraints: kiểm tra unique constraint mức cơ sở dữ liệu của migration 0016
- test_persist_e_rollback_discards_output_and_outbox_together: test khẳng định sau rollback bảng không có dòng nào (count == 0), mà skeleton rỗng chưa ghi gì vào DB nên pass

## 4. Bằng chứng kiểm thử GREEN (Bước 20)

Lệnh thực thi:
python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider

Exit code: 0

Dòng tổng kết pytest:
`
.................                                                        [100%]
17 passed in 8.81s
`

## 5. Kết quả quét adapter và kiểm tra khoảng trắng (Bước 21, 22)

Lệnh quét adapter (Bước 21):
python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter E'"
Exit code: 0

Lệnh kiểm tra khoảng trắng thừa (Bước 22):
git diff --check
Exit code: 0

## 5b. Khắc phục sau thu hồi grant G1 (INTEGRATION_CHECK_FAILED)

- Nguyên nhân: fixture disposable_db trước đây chỉ đọc M2_TEST_PG_DSN, không có DSN mặc định như tests/m2/conftest.py nên thiếu biến thì cả 17 test ERROR ở fixture trong 0,60 giây.
- Thay đổi: thêm _admin_dsn(): ưu tiên M2_TEST_PG_DSN, rồi docker port ai-auto-video-m2-pg, dự phòng cổng 57027; không kết nối được thì pytest.fail BLOCKED_EXTERNAL; vẫn PostgreSQL thật, mã adapter không đổi.
- Bước 1 (lỗi thật quan sát trước khi sửa):
  - Lỗi đầu tiên: Failed: BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.
  - Dòng tổng kết: 17 errors in 0.44s
  - Exit code: 1
- Bước 5 (sau khi sửa):
  - Dòng tổng kết: 17 passed in 8.86s
  - Exit code: 0
- Bước 6 (quét adapter):
  - Exit code: 0 (không có AssertionError)

## 5c. Kiểm lại ở HEAD b979cb1 và bổ sung test tuân thủ cổng UoW

- Lý do: acceptance 2 yêu cầu PostgresVoiceUnitOfWork thỏa VoiceUnitOfWork và MediaUnitOfWork; trước đó test chỉ kiểm IUnitOfWork và IOutboxWriter.
- Thay đổi: thêm test_persist_e_unit_of_work_satisfies_voice_and_media_ports (tham số hóa theo hai Protocol, kiểm đủ thành viên outputs, outbox, commit, __enter__, __exit__ và vòng vào/ra giao dịch); mã adapter không đổi.
- Test mới xanh ngay khi thêm vì adapter đã đủ thành viên; đây là test đặc trưng, không phải RED mới. Oracle RED của adapter vẫn là mục 3.
- Bước 1 (trước khi thêm test): dòng tổng kết 17 passed in 10.04s, exit code 0.
- Bước 4 (sau khi thêm test): dòng tổng kết 19 passed in 12.47s, exit code 0.
- Bước 5 (quét adapter): exit code 0.
- git diff --check: chạy lại sau khi ghi báo cáo, kết quả xem trong worker_done.

## 5d. F1 BLOCKED: miễn trừ bố cục E-01 nằm ngoài owned paths
- Trạng thái: ĐÃ GIẢI QUYẾT bằng PERSIST-LAYOUT-RULE gộp vào nhánh tích hợp 0726a84f6ad01e9413219549ebe2e906025a9970; xem mục 5e.

- (a) Kết quả bước 1: dòng FAILED và dòng tổng kết nguyên văn.
  - Dòng FAILED: FAILED tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_modules_have_no_forbidden_imports
  - Dòng tổng kết: 1 failed, 11 passed, 59 subtests passed in 0.51s
  - Exit code khác 0 (exit code: 1); AssertionError liệt kê src/voice/persistence/outbox.py (controlplane.infrastructure.db.outbox) và src/voice/persistence/output_repository.py (psycopg.errors, psycopg.types.json).
- (b) Nguyên nhân: FORBIDDEN_IMPORT_PREFIXES ở tests/unit/voice/test_e01_package_layout.py dòng 15-19 chứa 'psycopg' và 'controlplane.infrastructure'; ADAPTER_IMPORT_EXEMPTIONS ở dòng 25-27 chỉ có src/voice/adapters/real_ffmpeg_media_tool.py.
- (c) Bản sửa cần có khi Control cấp ownership tệp đó, theo mẫu PERSIST-A-LAYOUT-FIX: thêm hai khoá đường dẫn chính xác vào ADAPTER_IMPORT_EXEMPTIONS là 'src/voice/persistence/outbox.py' với frozenset({'controlplane.infrastructure.db.outbox'}) và 'src/voice/persistence/output_repository.py' với frozenset({'psycopg'}); cập nhật chú thích dẫn docs/implementation/persist/plan.md dòng 15 và 40-41; viết lại test_exemption_table_is_exact_paths_only thành so sánh với đúng ba khoá; thêm test chứng minh hai tệp persistence chỉ được miễn đúng tiền tố liệt kê (import socket, creative, subprocess vẫn bị từ chối) và các module voice khác vẫn bị từ chối psycopg. Kiểm sau sửa: python -m pytest tests/unit/voice -q -p no:cacheprovider phải đạt.
- (d) F2 (MINOR, fallback DSN m2test) đưa vào backlog, không sửa trong lượt này.

## 5e. Chạy lại sau rebase lên 0726a84f (cấp lại sau thu hồi G2)

- Lý do: Control rebase lên 0726a84f6ad01e9413219549ebe2e906025a9970, mã adapter và test PostgreSQL không đổi trong lượt này.
- Bước 1 (kiểm tra khoảng trắng): lệnh `git diff --check`, exit code 0.
- Bước 2 (kiểm tra bố cục gói voice sau khi PERSIST-LAYOUT-RULE đã gộp): lệnh `python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider`, exit code 0, dòng tổng kết: `16 passed, 89 subtests passed in 0.20s`.
- Bước 3 (kiểm thử tích hợp adapter PostgreSQL): lệnh `python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider`, exit code 0, dòng tổng kết: `19 passed in 9.76s`.
- Bước 4 (quét adapter): lệnh `python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter E'"`, exit code 0 (không có AssertionError).

## 6. Mục mở

- OI-PERSIST-E-01: chỉ cài KIND_VOICE và KIND_WORD_TIMING theo yêu cầu; các kind khác mà VoicePipeline và MediaPipeline đang dùng (receipt, receipt_by_request, tts_invocation, timing_report, language_evidence, probe_report, image_safety_assessment, processed_media, audio_bed_result) ném UnsupportedKindError nên chưa thể nối UoW này vào pipeline ở CP-4-WIRING cho tới khi có slice bổ sung; không tự thêm kind.
- OI-PERSIST-E-02: cách UoW nhận workspace_id cần được CP-4-WIRING xác nhận. Không có mục nào được ghi là đã duyệt.

## 7. Xác nhận tuân thủ

Xác nhận không sửa migration, composition root, api/wiring, lockfile, tests/m2 và không thêm thư viện.
