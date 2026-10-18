# Báo cáo bằng chứng A-05

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `14a2b92677ebf47724fab8a6229b340f45a1a3a7`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-05 trong docs/implementation/a/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `48 failed, 10 passed in 0.30s`
- Chi tiết các test FAILED kèm thông điệp AssertionError:
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::PurposeAndKeyTests::test_other_purposes_and_days_allowed`: `AssertionError: unexpectedly None`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::PurposeAndKeyTests::test_periodic_key_excludes_policy_revision`: `AssertionError: None != ('ws-1', 'src-1', datetime.date(2026, 10, 18), <CollectionPurpose.PERIODIC: 'PERIODIC'>)`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::PurposeAndKeyTests::test_schedule_rejects_non_enum_purpose`: `AssertionError: TypeError not raised`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::PurposeAndKeyTests::test_second_periodic_run_same_day_rejected`: `AssertionError: DuplicatePeriodicRunError not raised`
  - `SUBFAILED(revision='r1', max_attempts=0) tests/unit/collection/test_a05_collection_run_states.py::RetryPolicyTests::test_invalid_policy_rejected`: `AssertionError: ValueError not raised`
  - `SUBFAILED(revision='r1', max_attempts=-1) tests/unit/collection/test_a05_collection_run_states.py::RetryPolicyTests::test_invalid_policy_rejected`: `AssertionError: ValueError not raised`
  - `SUBFAILED(revision='r1', max_attempts=True) tests/unit/collection/test_a05_collection_run_states.py::RetryPolicyTests::test_invalid_policy_rejected`: `AssertionError: ValueError not raised`
  - `SUBFAILED(revision='r1', max_attempts='2') tests/unit/collection/test_a05_collection_run_states.py::RetryPolicyTests::test_invalid_policy_rejected`: `AssertionError: ValueError not raised`
  - `SUBFAILED(revision='', max_attempts=2) tests/unit/collection/test_a05_collection_run_states.py::RetryPolicyTests::test_invalid_policy_rejected`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::AttemptHistoryTests::test_attempt_is_immutable`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RETRY: 'WAITING_RETRY'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::AttemptHistoryTests::test_retry_stays_in_same_run`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RETRY: 'WAITING_RETRY'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ScheduledTransitionTests::test_deactivate_scheduled_fails_final_without_attempt`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ScheduledTransitionTests::test_scheduled_active_starts_running`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.RUNNING: 'RUNNING'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ScheduledTransitionTests::test_scheduled_inactive_fails_final_without_attempt`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::RetryExhaustionTests::test_budget_comes_from_policy`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RETRY: 'WAITING_RETRY'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::RetryExhaustionTests::test_deadline_passed_exhausts_retry`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `SUBFAILED(packages=0) tests/unit/collection/test_a05_collection_run_states.py::RetryExhaustionTests::test_final_failure_outcome`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `SUBFAILED(packages=1) tests/unit/collection/test_a05_collection_run_states.py::RetryExhaustionTests::test_final_failure_outcome`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.COMPLETED_PARTIAL: 'COMPLETED_PARTIAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::RetryExhaustionTests::test_last_retryable_with_committed_package_is_partial`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.COMPLETED_PARTIAL: 'COMPLETED_PARTIAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::RetryExhaustionTests::test_last_retryable_without_package_fails_final`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::RetryExhaustionTests::test_resume_after_deadline_exhausts_without_new_attempt`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RETRY: 'WAITING_RETRY'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::RetryExhaustionTests::test_retryable_with_budget_and_active_source_waits_retry`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RETRY: 'WAITING_RETRY'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::SourceInactiveTests::test_restored_source_does_not_reopen_terminal`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::SourceInactiveTests::test_resume_with_inactive_source_stops_without_attempt`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RETRY: 'WAITING_RETRY'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::SourceInactiveTests::test_retryable_with_inactive_source_stops`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `SUBFAILED(packages=0) tests/unit/collection/test_a05_collection_run_states.py::SourceInactiveTests::test_running_source_deactivated`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `SUBFAILED(packages=1) tests/unit/collection/test_a05_collection_run_states.py::SourceInactiveTests::test_running_source_deactivated`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.COMPLETED_PARTIAL: 'COMPLETED_PARTIAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::SourceInactiveTests::test_waiting_retry_source_deactivated`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RETRY: 'WAITING_RETRY'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_outcome_unknown_waits_reconciliation`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RECONCILIATION: 'WAITING_RECONCILIATION'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_all_done_completes_even_if_source_inactive`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.COMPLETED: 'COMPLETED'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_done_continue_resumes_from_checkpoint`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RECONCILIATION: 'WAITING_RECONCILIATION'>`
  - `SUBFAILED(packages=0) tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_done_continue_source_inactive_stops`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `SUBFAILED(packages=1) tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_done_continue_source_inactive_stops`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.COMPLETED_PARTIAL: 'COMPLETED_PARTIAL'>`
  - `SUBFAILED(packages=0) tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_final_stop`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `SUBFAILED(packages=1) tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_final_stop`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.COMPLETED_PARTIAL: 'COMPLETED_PARTIAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_requires_evidence`: `AssertionError: ValueError not raised`
  - `SUBFAILED(packages=0) tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_retryable_budget_exhausted`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `SUBFAILED(packages=1) tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_retryable_budget_exhausted`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.COMPLETED_PARTIAL: 'COMPLETED_PARTIAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_retryable_source_inactive`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.FAILED_FINAL: 'FAILED_FINAL'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_reconcile_retryable_with_budget_waits_retry`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RETRY: 'WAITING_RETRY'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationTests::test_waiting_reconciliation_rejects_retry_and_deactivate`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RECONCILIATION: 'WAITING_RECONCILIATION'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationOverdueTests::test_overdue_only_from_waiting_reconciliation`: `AssertionError: InvalidTransitionError not raised`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationOverdueTests::test_overdue_then_evidence_continues`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RECONCILIATION: 'WAITING_RECONCILIATION'>`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::ReconciliationOverdueTests::test_overdue_unknown_keeps_waiting_with_warning`: `AssertionError: <RunStatus.SCHEDULED: 'SCHEDULED'> != <RunStatus.WAITING_RECONCILIATION: 'WAITING_RECONCILIATION'>`
  - `SUBFAILED(count=0) tests/unit/collection/test_a05_collection_run_states.py::TerminalDecisionTests::test_record_committed_packages_rejects_invalid_count`: `AssertionError: ValueError not raised`
  - `SUBFAILED(count=-1) tests/unit/collection/test_a05_collection_run_states.py::TerminalDecisionTests::test_record_committed_packages_rejects_invalid_count`: `AssertionError: ValueError not raised`
  - `SUBFAILED(count=True) tests/unit/collection/test_a05_collection_run_states.py::TerminalDecisionTests::test_record_committed_packages_rejects_invalid_count`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a05_collection_run_states.py::TerminalDecisionTests::test_terminal_requires_checkpoint_ref`: `AssertionError: ValueError not raised`
- Xác nhận: 0 error, không có ModuleNotFoundError, ImportError hay collection error. Toàn bộ lỗi RED đều do sai oracle AssertionError.

## Thay đổi

- `src/source_ingestion/domain/collection_run.py`:
  - Enums kế thừa `(str, enum.Enum)`: `CollectionPurpose` (PERIODIC, SOURCE_TEST, SUPPLEMENTAL), `RunStatus` (SCHEDULED, RUNNING, WAITING_RETRY, WAITING_RECONCILIATION, COMPLETED, COMPLETED_PARTIAL, FAILED_FINAL), `AttemptOutcome` (SUCCEEDED, FAILED_RETRYABLE, FAILED_FINAL, OUTCOME_UNKNOWN), `TerminalReason` (ALL_WORK_DONE, RETRY_EXHAUSTED, SOURCE_INACTIVE, FINAL_ERROR), `ReconciliationResult` (RETRYABLE, ALL_WORK_DONE, FINAL_STOP, DONE_CONTINUE).
  - Hằng số: `TERMINAL_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.COMPLETED_PARTIAL, RunStatus.FAILED_FINAL})`.
  - Ngoại lệ: `InvalidTransitionError(ValueError)`, `TerminalRunError(InvalidTransitionError)`, `DuplicatePeriodicRunError(ValueError)`.
  - Dataclasses:
    - `RetryPolicy(revision, max_attempts)`: không có giá trị mặc định, kiểm tra hợp lệ kiểu và ràng buộc trong `__post_init__`.
    - `CollectionAttempt(attempt_no, outcome)`: cấu trúc bất biến cho từng attempt.
    - `ReconciliationRecord(attempt_no, result, evidence_ref)`: ghi nhận kết quả và bằng chứng đối soát.
    - `TerminalDecision(status, reason, policy_revision, checkpoint_ref)`: bản ghi quyết định terminal chứa đầy đủ metadata.
    - `CollectionRun`: entity lưu trạng thái run, lịch sử attempts và reconciliations dưới dạng tuple append-only.
  - Property `unique_key`: trả về `(workspace_id, source_id, business_date, CollectionPurpose.PERIODIC)` cho run PERIODIC (không chứa policy revision theo A-RULE-004); trả về `None` cho mục đích khác.
  - Các hàm chuyển trạng thái: `schedule_run`, `ensure_periodic_unique`, `start_run`, `record_committed_packages`, `record_attempt_outcome`, `resume_retry`, `deactivate_source`, `reconcile`, `flag_reconciliation_overdue`.
- `tests/unit/collection/test_a05_collection_run_states.py`:
  - 9 test class: `PurposeAndKeyTests`, `RetryPolicyTests`, `AttemptHistoryTests`, `ScheduledTransitionTests`, `RetryExhaustionTests`, `SourceInactiveTests`, `ReconciliationTests`, `ReconciliationOverdueTests`, `TerminalDecisionTests`.
  - Docstring nguyên văn chứa `coveredIds: TST-COL-END-001..004 (TST-COL-END-001, TST-COL-END-002, TST-COL-END-003, TST-COL-END-004), A-RULE-004, A-RULE-005`.

## Ánh xạ CT-STATE-002

| Dòng CT-STATE-002 | Trạng thái/Điều kiện | Chuyển trạng thái | Test phủ |
|---|---|---|---|
| 1 | RUNNING, attempt retryable, nguồn còn bật và còn retry budget | WAITING_RETRY; tạo attempt mới trong cùng run | `test_retryable_with_budget_and_active_source_waits_retry`, `test_retry_stays_in_same_run` |
| 2 | RUNNING hoặc WAITING_RETRY, hết budget/deadline hoặc nguồn inactive | COMPLETED_PARTIAL nếu có package commit, ngược lại FAILED_FINAL; reason RETRY_EXHAUSTED / SOURCE_INACTIVE | `test_last_retryable_without_package_fails_final`, `test_last_retryable_with_committed_package_is_partial`, `test_deadline_passed_exhausts_retry`, `test_resume_after_deadline_exhausts_without_new_attempt`, `test_running_source_deactivated`, `test_waiting_retry_source_deactivated`, `test_retryable_with_inactive_source_stops`, `test_resume_with_inactive_source_stops_without_attempt` |
| 3 | SCHEDULED, nguồn không còn được phép chạy | FAILED_FINAL với SOURCE_INACTIVE; không tạo attempt giả | `test_scheduled_inactive_fails_final_without_attempt`, `test_deactivate_scheduled_fails_final_without_attempt` |
| 4 | RUNNING, side effect chưa biết kết quả | WAITING_RECONCILIATION; không retry hay kết thúc sớm | `test_outcome_unknown_waits_reconciliation`, `test_waiting_reconciliation_rejects_retry_and_deactivate` |
| 5 | WAITING_RECONCILIATION, reconcile xác nhận retryable | WAITING_RETRY nếu nguồn/budget cho phép; nếu không thì terminal partial/final | `test_reconcile_retryable_with_budget_waits_retry`, `test_reconcile_retryable_budget_exhausted`, `test_reconcile_retryable_source_inactive` |
| 6 | WAITING_RECONCILIATION, xác nhận toàn bộ công việc xong | COMPLETED; giữ dữ liệu đã commit dù nguồn tắt; reason ALL_WORK_DONE | `test_reconcile_all_done_completes_even_if_source_inactive` |
| 7 | WAITING_RECONCILIATION, xác nhận lỗi cuối hoặc dừng | COMPLETED_PARTIAL nếu đã commit package, ngược lại FAILED_FINAL; reason FINAL_ERROR | `test_reconcile_final_stop` |
| 8 | WAITING_RECONCILIATION, xác nhận side effect xong nhưng còn việc | RUNNING qua checkpoint mới; không lặp attempt side effect cũ | `test_reconcile_done_continue_resumes_from_checkpoint`, `test_reconcile_done_continue_source_inactive_stops` |
| Invariant 1 | Reconcile quá hạn | Giữ WAITING_RECONCILIATION, ghi warning và log, không bịa terminal/retry | `test_overdue_unknown_keeps_waiting_with_warning`, `test_overdue_then_evidence_continues`, `test_overdue_only_from_waiting_reconciliation` |
| Invariant 2 | Run terminal không mở lại | Ném TerminalRunError | `test_restored_source_does_not_reopen_terminal` |
| Invariant 3 | Quyết định terminal | Ghi policy revision, reason, checkpoint_ref | `test_terminal_requires_checkpoint_ref`, các assertion TerminalDecision |

| Covered ID / Rule | Ý nghĩa | Test class |
|---|---|---|
| `TST-COL-END-001` | Chuyển trạng thái khi hết lượt retry (budget/deadline) | `RetryExhaustionTests` |
| `TST-COL-END-002` | Chuyển trạng thái khi nguồn bị vô hiệu hóa (SCHEDULED, RUNNING, WAITING_RETRY) | `ScheduledTransitionTests`, `SourceInactiveTests` |
| `TST-COL-END-003` | Quản lý đối soát OUTCOME_UNKNOWN và 4 nhánh reconcile | `ReconciliationTests` |
| `TST-COL-END-004` | Quá hạn đối soát không đổi trạng thái mù quáng, cảnh báo log | `ReconciliationOverdueTests` |
| `A-RULE-004` | Khoá duy nhất run PERIODIC không chứa policy revision | `PurposeAndKeyTests` |
| `A-RULE-005` | Retry là attempt append-only trong cùng một run duy nhất | `PurposeAndKeyTests`, `AttemptHistoryTests` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider` | 0 | 40 passed, 20 subtests passed in 0.05s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.03s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `max_attempts` là tổng số attempt gồm attempt đầu, lấy từ RetryPolicy, không có default.
2. Deadline retry là cờ `deadline_passed` do caller (G) cung cấp, domain không đọc đồng hồ.
3. `business_date` nhận từ G, A không tự tính (MODULE-A-OPEN-004).
4. Reason ALL_WORK_DONE và FINAL_ERROR do A-05 đặt tên cho nhánh hoàn tất/lỗi cuối, RETRY_EXHAUSTED/SOURCE_INACTIVE theo CT-STATE-002.
5. Deactivate ở WAITING_RECONCILIATION bị từ chối bằng `InvalidTransitionError`, trạng thái nguồn áp dụng khi reconcile qua tham số `source_active`.
6. Unknown quá hạn chỉ ghi warning + log, không retry/terminal.
7. Chưa có persistence, event/outbox, unique index DB (thuộc A-08/CONV-A-01) và đăng ký state machine dùng chung (thuộc CONV-A-05).
8. Toàn bộ triển khai chỉ dùng Python stdlib.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Giá trị retry count/deadline cụ thể phải khoá trước production (CT-STATE-002)
- Múi giờ business_date (MODULE-A-OPEN-004)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật.
