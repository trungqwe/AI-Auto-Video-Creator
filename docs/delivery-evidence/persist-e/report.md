# Báo cáo PERSIST-E: adapter PostgreSQL của voice

- Base HEAD: a3d84e838a0937515eb62eb5c3a35016ab88e7df
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

## 6. Mục mở

- OI-PERSIST-E-01: chỉ cài KIND_VOICE và KIND_WORD_TIMING theo yêu cầu; các kind khác mà VoicePipeline và MediaPipeline đang dùng (receipt, receipt_by_request, tts_invocation, timing_report, language_evidence, probe_report, image_safety_assessment, processed_media, audio_bed_result) ném UnsupportedKindError nên chưa thể nối UoW này vào pipeline ở CP-4-WIRING cho tới khi có slice bổ sung; không tự thêm kind.
- OI-PERSIST-E-02: cách UoW nhận workspace_id cần được CP-4-WIRING xác nhận. Không có mục nào được ghi là đã duyệt.

## 7. Xác nhận tuân thủ

Xác nhận không sửa migration, composition root, api/wiring, lockfile, tests/m2 và không thêm thư viện.
