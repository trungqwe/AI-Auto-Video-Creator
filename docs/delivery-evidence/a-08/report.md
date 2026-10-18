# B?o c?o b?ng ch?ng A-08

## M?i tr??ng

- Interpreter kho?: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `bad89e191f3ddd653febc2626eb80d813c93f8b8`
- Ngu?n quy?n: IMPL-PLAN-A Auditor PASS, slice A-08 trong `docs/implementation/a/slices.md`; ph? thu?c A-02/A-03/A-05/A-06/A-07 ?? t?ch h?p.

## RED

- L?nh th?c thi: `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider`
- Tr?ng th?i m? l?c RED: ports + test ho?n ch?nh, `memory.py` l? stub.
- Exit code th?c t?: 1
- D?ng t?m t?t nguy?n v?n: `26 failed, 9 passed in 0.35s`
- Test FAILED ti?u bi?u:
  - `FAILED tests/unit/collection/test_a08_ports_memory.py::UnitOfWorkTests::test_writes_outside_unit_of_work_are_rejected` (AssertionError: TransactionNotActiveError not raised)
  - `FAILED tests/unit/collection/test_a08_ports_memory.py::CollectionRunRepositoryTests::test_two_periodic_runs_with_same_key_cannot_coexist` (AssertionError: DuplicatePeriodicRunError not raised)
  - `FAILED tests/unit/collection/test_a08_ports_memory.py::ConfigPortTests::test_fake_config_port_refuses_raw_secret` (AssertionError: TypeError not raised by FakeConfigPort)
- X?c nh?n: 0 error, kh?ng c? ModuleNotFoundError, ImportError hay collection error; m?i l?i RED l? AssertionError sai oracle.

## Thay ??i

- `src/source_ingestion/ports/repositories.py`: DTO `PackageRecord`, `CommandReceipt`, c?c l?i tr?ng kho?/kh?ng t?m th?y (`DuplicateRecordError`, `DuplicateSourceIdentityError`, `DuplicatePackageError`, `DuplicateReceiptError`, `RecordNotFoundError`), 6 Protocol `@runtime_checkable` (`SourceRepository`, `SourceCandidateRepository`, `CollectionRunRepository`, `PackageRepository`, `CheckpointRepository`, `ReceiptStore`).
- `src/source_ingestion/ports/partners.py`: B?ng tr??ng `DECLARE_ARTIFACT_VERSION_REQUEST_FIELDS`, `DECLARE_ARTIFACT_VERSION_RESULT_FIELDS` theo binding `1.0.0`, DTO `PolicyRevisionRef`, 4 Protocol `@runtime_checkable` (`ArtifactPort`, `ContentHandoffPort`, `ConfigPort`, `ActivityGrantPort`).
- `src/source_ingestion/adapters/memory.py`: `_Table`, `InMemoryUnitOfWork` (k? th?a `controlplane.domain.interfaces.uow.IUnitOfWork`, snapshot/rollback hu? m?i ghi, b?o v? transaction active), `InMemoryOutboxWriter` (k? th?a `controlplane.domain.interfaces.outbox.IOutboxWriter`, dedup theo `deduplication_id`), 6 repository adapter in-memory b?o to?n r?ng bu?c nghi?p v? (identity g?m tombstone, unique periodic key, unique package, revision guard), c?c fake ??i t?c (`FakeArtifactPort`, `FakeContentHandoffPort`, `FakeConfigPort`, `FakeActivityGrantPort`, `contract_errors`).
- `tests/unit/collection/test_a08_ports_memory.py`: Docstring `coveredIds: A-RULE-004`, 13 test case ki?m tra t?i s? d?ng interface, UnitOfWork, Outbox dedup, c?c repository port v? partner fake.

## ?nh x? y?u c?u ? test

| Y?u c?u / ph?n v? d? | Test |
|---|---|
| Protocol 6 repository + 4 port ??i t?c | `test_memory_adapters_satisfy_ports`, `test_memory_adapters_reuse_controlplane_interfaces` |
| Kh?ng t?o IUnitOfWork/IOutboxWriter/IRepository/DomainEvent m?i | `test_no_duplicate_interfaces_or_shared_types_defined` |
| UoW implement IUnitOfWork, rollback hu? m?i ghi (source, outbox, ...) | `test_rollback_discards_every_write`, `test_exception_inside_context_discards_source_and_outbox`, `test_leaving_context_without_commit_rolls_back`, `test_commit_persists_and_later_rollback_restores_committed_state`, `test_writes_outside_unit_of_work_are_rejected`, `test_begin_twice_is_rejected` |
| Outbox implement IOutboxWriter dedup theo deduplication_id | `test_append_dedups_by_deduplication_id`, `test_payload_is_read_only_copy`, `test_rejects_blank_deduplication_id` |
| Identity g?m tombstone (A-07) v? workspace scope | `test_identity_lookup_includes_tombstone`, `test_identity_is_scoped_by_workspace`, `test_save_guards_revision_key_and_existence` |
| Candidate add, find v? revision guard | `test_candidate_add_find_and_revision_guard` |
| Hai periodic run c?ng kho? c?ng t?n t?i b? lo?i tr? (A-RULE-004) | `test_two_periodic_runs_with_same_key_cannot_coexist`, `test_periodic_key_excludes_policy_revision_and_other_purposes`, `test_save_updates_state_but_not_key` |
| Package unique theo source + canonical locator + observation fingerprint | `test_package_unique_by_source_locator_and_fingerprint`, `test_package_record_validates_and_freezes_payload` |
| Checkpoint repository ch? ti?n qua item b?n v?ng | `test_checkpoint_advances_only_over_durable_items` |
| ReceiptStore unique theo workspace + idempotency key | `test_receipt_unique_per_workspace_and_key`, `test_receipt_validates_fields` |
| Fake ArtifactPort kh?p fixture v? binding i-artifact-version | `test_field_tables_match_binding`, `test_fake_returns_payload_matching_fixture`, `test_fake_rejects_fixture_invalid_payloads` |
| Fake ContentHandoffPort ch? nh?n package layer 1 h?p l? | `test_fake_hands_off_layer1_valid_package_only` |
| ConfigPort kh?ng tr? secret th?, t? ch?i raw secret | `test_config_port_contract_returns_handle_not_raw_secret`, `test_fake_config_port_refuses_raw_secret`, `test_fake_config_port_returns_refs` |
| ActivityGrantPort ki?m tra grant hi?n h?nh | `test_fake_grant_port_checks_current_grant` |

## L?nh ki?m

| # | L?nh | Exit code | K?t qu? |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider` | 0 | 32 passed, 3 subtests passed in 0.09s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.05s |
| 3 | `git diff --check` | 0 | passed (clean, no output) |

## Quy?t ??nh m?c ??nh (D8)

1. Protocol kh?ng k? th?a IRepository v? port kh?ng c? delete, tombstone gi? identity;
2. Tho?t context kh?ng commit th? rollback; ghi/commit/rollback ngo?i UoW n?m TransactionNotActiveError;
3. event_id outbox = 'evt-' + 32 k? t? ??u sha256(deduplication_id), tr?ng deduplication_id tr? event_id c?, gi? payload ??u;
4. ConfigPort l? port A-local t?i khi CONV-A-07 m? binding J?A CT-CFG-002, ch? tr? PolicyRevisionRef v? controlplane SecretHandle;
5. ActivityGrantPort d?ng controlplane ExecutionGrant;
6. CheckpointRepository.advance u? quy?n advance_checkpoint c?a A-06;
7. PostgreSQL ch? CONV-A-01;
8. Kh?ng th?m th? vi?n.

## Danh s?ch ch? user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 t?i nguy?n th?t (D5)
- CONV-A-01
- CONV-A-07

## Gi?i h?n

- Kh?ng ch?y full suite, tests/m1, tests/m2.
- Kh?ng ??i `pyproject.toml`, `uv.lock`.
- Kh?ng g?i d?ch v? th?t.
