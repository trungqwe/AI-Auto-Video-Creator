# Báo cáo bằng chứng A-08

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `bad89e191f3ddd653febc2626eb80d813c93f8b8`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-08 trong `docs/implementation/a/slices.md`; phụ thuộc A-02/A-03/A-05/A-06/A-07 đã tích hợp.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider`
- Trạng thái mô phỏng RED: ports + test hoàn chỉnh, `memory.py` là stub.
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `26 failed, 9 passed in 0.35s`
- Test FAILED tiêu biểu:
  - `FAILED tests/unit/collection/test_a08_ports_memory.py::UnitOfWorkTests::test_writes_outside_unit_of_work_are_rejected` (AssertionError: TransactionNotActiveError not raised)
  - `FAILED tests/unit/collection/test_a08_ports_memory.py::CollectionRunRepositoryTests::test_two_periodic_runs_with_same_key_cannot_coexist` (AssertionError: DuplicatePeriodicRunError not raised)
  - `FAILED tests/unit/collection/test_a08_ports_memory.py::ConfigPortTests::test_fake_config_port_refuses_raw_secret` (AssertionError: TypeError not raised by FakeConfigPort)
- Xác nhận: 0 error, không có ModuleNotFoundError, ImportError hay collection error; mọi lỗi RED là AssertionError sai oracle.

## Thay đổi

- `src/source_ingestion/ports/repositories.py`: DTO `PackageRecord`, `CommandReceipt`; các lỗi trùng khoá/không tìm thấy (`DuplicateRecordError`, `DuplicateSourceIdentityError`, `DuplicatePackageError`, `DuplicateReceiptError`, `RecordNotFoundError`); 6 Protocol `@runtime_checkable` (`SourceRepository`, `SourceCandidateRepository`, `CollectionRunRepository`, `PackageRepository`, `CheckpointRepository`, `ReceiptStore`).
- `src/source_ingestion/ports/partners.py`: bảng trường `DECLARE_ARTIFACT_VERSION_REQUEST_FIELDS`, `DECLARE_ARTIFACT_VERSION_RESULT_FIELDS` theo binding `1.0.0`; DTO `PolicyRevisionRef`; 4 Protocol `@runtime_checkable` (`ArtifactPort`, `ContentHandoffPort`, `ConfigPort`, `ActivityGrantPort`).
- `src/source_ingestion/adapters/memory.py`: `InMemoryUnitOfWork` kế thừa `controlplane.domain.interfaces.uow.IUnitOfWork` (snapshot/rollback huỷ mọi ghi, bảo vệ transaction active); `InMemoryOutboxWriter` kế thừa `controlplane.domain.interfaces.outbox.IOutboxWriter` (dedup theo `deduplication_id`); 6 repository in-memory giữ ràng buộc nghiệp vụ (identity gồm tombstone, unique periodic key, unique package, revision guard); các fake đối tác (`FakeArtifactPort`, `FakeContentHandoffPort`, `FakeConfigPort`, `FakeActivityGrantPort`, `contract_errors`).
- `tests/unit/collection/test_a08_ports_memory.py`: docstring `coveredIds: A-RULE-004`; 13 lớp test, 32 test case.
- `docs/delivery-evidence/a-08/report.md`: khôi phục mã hoá UTF-8 và dấu tiếng Việt (bản trước bị thay chữ có dấu bằng dấu hỏi); không đổi nội dung kỹ thuật.

## Ánh xạ yêu cầu → test

| Yêu cầu / phản ví dụ | Test |
|---|---|
| Protocol 6 repository + 4 port đối tác | `test_memory_adapters_satisfy_ports`, `test_memory_adapters_reuse_controlplane_interfaces` |
| Không tạo IUnitOfWork/IOutboxWriter/IRepository/DomainEvent mới | `test_no_duplicate_interfaces_or_shared_types_defined` |
| UoW implement IUnitOfWork, rollback huỷ mọi ghi (source, outbox, ...) | `test_rollback_discards_every_write`, `test_exception_inside_context_discards_source_and_outbox`, `test_leaving_context_without_commit_rolls_back`, `test_commit_persists_and_later_rollback_restores_committed_state`, `test_writes_outside_unit_of_work_are_rejected`, `test_begin_twice_is_rejected` |
| Outbox implement IOutboxWriter dedup theo deduplication_id | `test_append_dedups_by_deduplication_id`, `test_payload_is_read_only_copy`, `test_rejects_blank_deduplication_id` |
| Identity gồm tombstone (A-07) và workspace scope | `test_identity_lookup_includes_tombstone`, `test_identity_is_scoped_by_workspace`, `test_save_guards_revision_key_and_existence` |
| Candidate add, find và revision guard | `test_candidate_add_find_and_revision_guard` |
| Hai periodic run cùng khoá cùng tồn tại bị loại trừ (A-RULE-004) | `test_two_periodic_runs_with_same_key_cannot_coexist`, `test_periodic_key_excludes_policy_revision_and_other_purposes`, `test_save_updates_state_but_not_key` |
| Package unique theo source + canonical locator + observation fingerprint | `test_package_unique_by_source_locator_and_fingerprint`, `test_package_record_validates_and_freezes_payload` |
| Checkpoint repository chỉ tiến qua item bền vững | `test_checkpoint_advances_only_over_durable_items` |
| ReceiptStore unique theo workspace + idempotency key | `test_receipt_unique_per_workspace_and_key`, `test_receipt_validates_fields` |
| Fake ArtifactPort khớp fixture và binding i-artifact-version | `test_field_tables_match_binding`, `test_fake_returns_payload_matching_fixture`, `test_fake_rejects_fixture_invalid_payloads` |
| Fake ContentHandoffPort chỉ nhận package layer 1 hợp lệ | `test_fake_hands_off_layer1_valid_package_only` |
| ConfigPort không trả secret thô, từ chối raw secret | `test_config_port_contract_returns_handle_not_raw_secret`, `test_fake_config_port_refuses_raw_secret`, `test_fake_config_port_returns_refs` |
| ActivityGrantPort kiểm tra grant hiện hành | `test_fake_grant_port_checks_current_grant` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider | 0 | 32 passed, 3 subtests passed in 0.10s |
| 2 | python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider | 0 | 8 passed, 31 subtests passed in 0.07s |
| 3 | git diff --check | 0 | passed (clean, no output) |
| 4 | git diff --check | 0 | passed (clean, no output) |

## Quyết định mặc định (D8)

1. Protocol không kế thừa IRepository vì port không có delete; tombstone giữ identity.
2. Thoát context không commit thì rollback; ghi/commit/rollback ngoài UoW ném TransactionNotActiveError.
3. event_id outbox = 'evt-' + 32 ký tự đầu sha256(deduplication_id); trùng deduplication_id trả event_id cũ, giữ payload đầu.
4. ConfigPort là port A-local tới khi CONV-A-07 mở binding J→A CT-CFG-002, chỉ trả PolicyRevisionRef và controlplane SecretHandle.
5. ActivityGrantPort dùng controlplane ExecutionGrant.
6. CheckpointRepository.advance uỷ quyền advance_checkpoint của A-06.
7. PostgreSQL chờ CONV-A-01.
8. Không thêm thư viện.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- CONV-A-01
- CONV-A-07

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật.
