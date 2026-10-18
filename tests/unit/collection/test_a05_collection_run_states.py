"""A-05: CollectionRun and CollectionAttempt state machine (CT-STATE-002).

coveredIds: TST-COL-END-001..004 (TST-COL-END-001, TST-COL-END-002, TST-COL-END-003, TST-COL-END-004), A-RULE-004, A-RULE-005
"""
from __future__ import annotations

import dataclasses
import datetime
import unittest

from source_ingestion.domain.collection_run import (
    AttemptOutcome,
    CollectionAttempt,
    CollectionPurpose,
    CollectionRun,
    DuplicatePeriodicRunError,
    InvalidTransitionError,
    ReconciliationRecord,
    ReconciliationResult,
    RetryPolicy,
    RunStatus,
    TerminalDecision,
    TerminalReason,
    TerminalRunError,
    deactivate_source,
    ensure_periodic_unique,
    flag_reconciliation_overdue,
    reconcile,
    record_attempt_outcome,
    record_committed_packages,
    resume_retry,
    schedule_run,
    start_run,
)

POLICY = RetryPolicy(revision='retry-policy-r7', max_attempts=2)
DAY = datetime.date(2026, 10, 18)
CP = 'checkpoint-ref-1'
CP2 = 'checkpoint-ref-2'


def _run(
    purpose: CollectionPurpose = CollectionPurpose.PERIODIC,
    policy: RetryPolicy = POLICY,
    run_id: str = 'run-1',
    day: datetime.date = DAY,
) -> CollectionRun:
    return schedule_run(
        run_id=run_id,
        workspace_id='ws-1',
        source_id='src-1',
        business_date=day,
        purpose=purpose,
        retry_policy=policy,
    )


def _running(policy: RetryPolicy = POLICY, packages: int = 0) -> CollectionRun:
    run = start_run(_run(policy=policy), source_active=True, checkpoint_ref=CP)
    if packages > 0:
        run = record_committed_packages(run, packages)
    return run


def _fail(run: CollectionRun, *, active: bool = True, deadline: bool = False) -> CollectionRun:
    return record_attempt_outcome(
        run,
        AttemptOutcome.FAILED_RETRYABLE,
        source_active=active,
        deadline_passed=deadline,
        checkpoint_ref=CP,
    )


def _unknown(policy: RetryPolicy = POLICY, packages: int = 0) -> CollectionRun:
    return record_attempt_outcome(
        _running(policy, packages),
        AttemptOutcome.OUTCOME_UNKNOWN,
        source_active=True,
        deadline_passed=False,
        checkpoint_ref=CP,
    )


class PurposeAndKeyTests(unittest.TestCase):
    def test_purposes_are_exactly_three(self) -> None:
        self.assertEqual({p.value for p in CollectionPurpose}, {'PERIODIC', 'SOURCE_TEST', 'SUPPLEMENTAL'})

    def test_periodic_key_excludes_policy_revision(self) -> None:
        a = _run()
        b = _run(policy=RetryPolicy(revision='retry-policy-r8', max_attempts=5), run_id='run-2')
        self.assertEqual(a.unique_key, ('ws-1', 'src-1', DAY, CollectionPurpose.PERIODIC))
        self.assertEqual(a.unique_key, b.unique_key)
        self.assertNotIn('retry-policy-r7', a.unique_key)
        self.assertNotIn('retry-policy-r8', a.unique_key)

    def test_second_periodic_run_same_day_rejected(self) -> None:
        a = _run()
        b = _run(run_id='run-2')
        with self.assertRaises(DuplicatePeriodicRunError):
            ensure_periodic_unique([a], b)

    def test_other_purposes_and_days_allowed(self) -> None:
        a = _run()
        self.assertIsNotNone(a.unique_key)
        for p in (CollectionPurpose.SOURCE_TEST, CollectionPurpose.SUPPLEMENTAL):
            with self.subTest(purpose=p):
                self.assertIsNone(_run(purpose=p).unique_key)
                ensure_periodic_unique([a], _run(purpose=p, run_id='run-3'))
        ensure_periodic_unique([a], _run(run_id='run-4', day=datetime.date(2026, 10, 19)))

    def test_schedule_rejects_non_enum_purpose(self) -> None:
        with self.assertRaises(TypeError):
            schedule_run(
                run_id='run-1',
                workspace_id='ws-1',
                source_id='src-1',
                business_date=DAY,
                purpose='RETRY',  # type: ignore[arg-type]
                retry_policy=POLICY,
            )


class RetryPolicyTests(unittest.TestCase):
    def test_budget_has_no_default(self) -> None:
        with self.assertRaises(TypeError):
            RetryPolicy(revision='r1')  # type: ignore[call-arg]
        for f in dataclasses.fields(RetryPolicy):
            self.assertIs(f.default, dataclasses.MISSING)
            self.assertIs(f.default_factory, dataclasses.MISSING)

    def test_invalid_policy_rejected(self) -> None:
        for rev, max_att in (('r1', 0), ('r1', -1), ('r1', True), ('r1', '2'), ('', 2)):
            with self.subTest(revision=rev, max_attempts=max_att):
                with self.assertRaises(ValueError):
                    RetryPolicy(revision=rev, max_attempts=max_att)  # type: ignore[arg-type]


class AttemptHistoryTests(unittest.TestCase):
    def test_attempt_outcomes_exact(self) -> None:
        self.assertEqual(
            {o.value for o in AttemptOutcome},
            {'SUCCEEDED', 'FAILED_RETRYABLE', 'FAILED_FINAL', 'OUTCOME_UNKNOWN'},
        )

    def test_retry_stays_in_same_run(self) -> None:
        r1 = _fail(_running())
        self.assertEqual(r1.status, RunStatus.WAITING_RETRY)
        r2 = resume_retry(r1, source_active=True, deadline_passed=False, checkpoint_ref=CP)
        self.assertEqual(r2.status, RunStatus.RUNNING)
        r3 = record_attempt_outcome(
            r2,
            AttemptOutcome.SUCCEEDED,
            source_active=True,
            deadline_passed=False,
            checkpoint_ref=CP,
        )
        self.assertEqual(r3.status, RunStatus.COMPLETED)
        self.assertEqual(r3.run_id, 'run-1')
        self.assertEqual([a.attempt_no for a in r3.attempts], [1, 2])
        self.assertEqual(
            [a.outcome for a in r3.attempts],
            [AttemptOutcome.FAILED_RETRYABLE, AttemptOutcome.SUCCEEDED],
        )
        self.assertEqual(r3.attempts[:1], r1.attempts)
        self.assertIsInstance(r3.attempts, tuple)

    def test_attempt_is_immutable(self) -> None:
        r1 = _fail(_running())
        self.assertEqual(r1.status, RunStatus.WAITING_RETRY)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r1.attempts[0].outcome = AttemptOutcome.SUCCEEDED  # type: ignore[misc]


class ScheduledTransitionTests(unittest.TestCase):
    def test_scheduled_inactive_fails_final_without_attempt(self) -> None:
        r = start_run(_run(), source_active=False, checkpoint_ref=CP)
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(r.attempts, ())
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.SOURCE_INACTIVE, 'retry-policy-r7', CP),
        )

    def test_deactivate_scheduled_fails_final_without_attempt(self) -> None:
        r = deactivate_source(_run(), checkpoint_ref=CP)
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(r.attempts, ())
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.SOURCE_INACTIVE, 'retry-policy-r7', CP),
        )

    def test_scheduled_active_starts_running(self) -> None:
        r = _running()
        self.assertEqual(r.status, RunStatus.RUNNING)
        self.assertEqual(r.attempts, ())
        self.assertIsNone(r.terminal_decision)


class RetryExhaustionTests(unittest.TestCase):
    def test_retryable_with_budget_and_active_source_waits_retry(self) -> None:
        r = _fail(_running())
        self.assertEqual(r.status, RunStatus.WAITING_RETRY)
        self.assertIsNone(r.terminal_decision)
        self.assertEqual(len(r.attempts), 1)

    def test_last_retryable_without_package_fails_final(self) -> None:
        r = _fail(resume_retry(_fail(_running()), source_active=True, deadline_passed=False, checkpoint_ref=CP))
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(len(r.attempts), 2)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.RETRY_EXHAUSTED, 'retry-policy-r7', CP),
        )
        self.assertEqual(r.checkpoint_ref, CP)

    def test_last_retryable_with_committed_package_is_partial(self) -> None:
        r = _fail(
            resume_retry(_fail(_running(packages=1)), source_active=True, deadline_passed=False, checkpoint_ref=CP)
        )
        self.assertEqual(r.status, RunStatus.COMPLETED_PARTIAL)
        self.assertEqual(r.committed_package_count, 1)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.COMPLETED_PARTIAL, TerminalReason.RETRY_EXHAUSTED, 'retry-policy-r7', CP),
        )

    def test_budget_comes_from_policy(self) -> None:
        p3 = RetryPolicy(revision='retry-policy-r9', max_attempts=3)
        r = _fail(_running(policy=p3))
        self.assertEqual(r.status, RunStatus.WAITING_RETRY)
        r = _fail(resume_retry(r, source_active=True, deadline_passed=False, checkpoint_ref=CP))
        self.assertEqual(r.status, RunStatus.WAITING_RETRY)

        p1 = RetryPolicy(revision='retry-policy-r1', max_attempts=1)
        r_single = _fail(_running(policy=p1))
        self.assertEqual(r_single.status, RunStatus.FAILED_FINAL)
        self.assertEqual(
            r_single.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.RETRY_EXHAUSTED, 'retry-policy-r1', CP),
        )

    def test_deadline_passed_exhausts_retry(self) -> None:
        r = _fail(_running(), deadline=True)
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.RETRY_EXHAUSTED, 'retry-policy-r7', CP),
        )
        self.assertEqual(len(r.attempts), 1)

    def test_resume_after_deadline_exhausts_without_new_attempt(self) -> None:
        w = _fail(_running())
        self.assertEqual(w.status, RunStatus.WAITING_RETRY)
        r = resume_retry(w, source_active=True, deadline_passed=True, checkpoint_ref=CP)
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.RETRY_EXHAUSTED, 'retry-policy-r7', CP),
        )
        self.assertEqual(r.attempts, w.attempts)

    def test_final_failure_outcome(self) -> None:
        for pkg, expected_status in ((0, RunStatus.FAILED_FINAL), (1, RunStatus.COMPLETED_PARTIAL)):
            with self.subTest(packages=pkg):
                r = record_attempt_outcome(
                    _running(packages=pkg),
                    AttemptOutcome.FAILED_FINAL,
                    source_active=True,
                    deadline_passed=False,
                    checkpoint_ref=CP,
                )
                self.assertEqual(r.status, expected_status)
                self.assertEqual(
                    r.terminal_decision,
                    TerminalDecision(expected_status, TerminalReason.FINAL_ERROR, 'retry-policy-r7', CP),
                )


class SourceInactiveTests(unittest.TestCase):
    def test_running_source_deactivated(self) -> None:
        for pkg, expected_status in ((0, RunStatus.FAILED_FINAL), (1, RunStatus.COMPLETED_PARTIAL)):
            with self.subTest(packages=pkg):
                r = deactivate_source(_running(packages=pkg), checkpoint_ref=CP)
                self.assertEqual(r.status, expected_status)
                self.assertEqual(
                    r.terminal_decision,
                    TerminalDecision(expected_status, TerminalReason.SOURCE_INACTIVE, 'retry-policy-r7', CP),
                )
                self.assertEqual(r.attempts, ())

    def test_waiting_retry_source_deactivated(self) -> None:
        w = _fail(_running())
        self.assertEqual(w.status, RunStatus.WAITING_RETRY)
        r = deactivate_source(w, checkpoint_ref=CP)
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.SOURCE_INACTIVE, 'retry-policy-r7', CP),
        )
        self.assertEqual(r.attempts, w.attempts)

    def test_retryable_with_inactive_source_stops(self) -> None:
        r = _fail(_running(), active=False)
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.SOURCE_INACTIVE, 'retry-policy-r7', CP),
        )

    def test_resume_with_inactive_source_stops_without_attempt(self) -> None:
        w = _fail(_running())
        self.assertEqual(w.status, RunStatus.WAITING_RETRY)
        r = resume_retry(w, source_active=False, deadline_passed=False, checkpoint_ref=CP)
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.SOURCE_INACTIVE, 'retry-policy-r7', CP),
        )
        self.assertEqual(r.attempts, w.attempts)

    def test_restored_source_does_not_reopen_terminal(self) -> None:
        t = deactivate_source(_running(), checkpoint_ref=CP)
        self.assertEqual(t.status, RunStatus.FAILED_FINAL)
        with self.assertRaises(TerminalRunError):
            start_run(t, source_active=True, checkpoint_ref=CP)
        with self.assertRaises(TerminalRunError):
            resume_retry(t, source_active=True, deadline_passed=False, checkpoint_ref=CP)


class ReconciliationTests(unittest.TestCase):
    def test_outcome_unknown_waits_reconciliation(self) -> None:
        u = _unknown()
        self.assertEqual(u.status, RunStatus.WAITING_RECONCILIATION)
        self.assertIsNone(u.terminal_decision)
        self.assertEqual(len(u.attempts), 1)
        self.assertEqual(u.attempts[0].outcome, AttemptOutcome.OUTCOME_UNKNOWN)

    def test_waiting_reconciliation_rejects_retry_and_deactivate(self) -> None:
        u = _unknown()
        self.assertEqual(u.status, RunStatus.WAITING_RECONCILIATION)
        with self.assertRaises(InvalidTransitionError):
            resume_retry(u, source_active=True, deadline_passed=False, checkpoint_ref=CP)
        with self.assertRaises(InvalidTransitionError):
            record_attempt_outcome(
                u,
                AttemptOutcome.FAILED_RETRYABLE,
                source_active=True,
                deadline_passed=False,
                checkpoint_ref=CP,
            )
        with self.assertRaises(InvalidTransitionError):
            deactivate_source(u, checkpoint_ref=CP)

    def test_reconcile_retryable_with_budget_waits_retry(self) -> None:
        r = reconcile(
            _unknown(),
            ReconciliationResult.RETRYABLE,
            evidence_ref='evidence-1',
            source_active=True,
            deadline_passed=False,
            checkpoint_ref=CP,
        )
        self.assertEqual(r.status, RunStatus.WAITING_RETRY)
        self.assertEqual(len(r.attempts), 1)
        self.assertEqual(r.attempts[0].outcome, AttemptOutcome.OUTCOME_UNKNOWN)
        self.assertEqual(
            r.reconciliations,
            (ReconciliationRecord(1, ReconciliationResult.RETRYABLE, 'evidence-1'),),
        )

    def test_reconcile_retryable_budget_exhausted(self) -> None:
        p1 = RetryPolicy(revision='retry-policy-r1', max_attempts=1)
        for pkg, expected_status in ((0, RunStatus.FAILED_FINAL), (1, RunStatus.COMPLETED_PARTIAL)):
            with self.subTest(packages=pkg):
                r = reconcile(
                    _unknown(p1, pkg),
                    ReconciliationResult.RETRYABLE,
                    evidence_ref='evidence-1',
                    source_active=True,
                    deadline_passed=False,
                    checkpoint_ref=CP,
                )
                self.assertEqual(r.status, expected_status)
                self.assertEqual(
                    r.terminal_decision,
                    TerminalDecision(expected_status, TerminalReason.RETRY_EXHAUSTED, 'retry-policy-r1', CP),
                )

    def test_reconcile_retryable_source_inactive(self) -> None:
        r = reconcile(
            _unknown(),
            ReconciliationResult.RETRYABLE,
            evidence_ref='evidence-1',
            source_active=False,
            deadline_passed=False,
            checkpoint_ref=CP,
        )
        self.assertEqual(r.status, RunStatus.FAILED_FINAL)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.FAILED_FINAL, TerminalReason.SOURCE_INACTIVE, 'retry-policy-r7', CP),
        )

    def test_reconcile_all_done_completes_even_if_source_inactive(self) -> None:
        r = reconcile(
            _unknown(packages=2),
            ReconciliationResult.ALL_WORK_DONE,
            evidence_ref='evidence-1',
            source_active=False,
            deadline_passed=False,
            checkpoint_ref=CP,
        )
        self.assertEqual(r.status, RunStatus.COMPLETED)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.COMPLETED, TerminalReason.ALL_WORK_DONE, 'retry-policy-r7', CP),
        )
        self.assertEqual(r.committed_package_count, 2)

    def test_reconcile_final_stop(self) -> None:
        for pkg, expected_status in ((0, RunStatus.FAILED_FINAL), (1, RunStatus.COMPLETED_PARTIAL)):
            with self.subTest(packages=pkg):
                r = reconcile(
                    _unknown(packages=pkg),
                    ReconciliationResult.FINAL_STOP,
                    evidence_ref='evidence-1',
                    source_active=True,
                    deadline_passed=False,
                    checkpoint_ref=CP,
                )
                self.assertEqual(r.status, expected_status)
                self.assertEqual(
                    r.terminal_decision,
                    TerminalDecision(expected_status, TerminalReason.FINAL_ERROR, 'retry-policy-r7', CP),
                )

    def test_reconcile_done_continue_resumes_from_checkpoint(self) -> None:
        u = _unknown()
        self.assertEqual(u.status, RunStatus.WAITING_RECONCILIATION)
        r = reconcile(
            u,
            ReconciliationResult.DONE_CONTINUE,
            evidence_ref='evidence-1',
            source_active=True,
            deadline_passed=False,
            checkpoint_ref=CP2,
        )
        self.assertEqual(r.status, RunStatus.RUNNING)
        self.assertEqual(r.checkpoint_ref, CP2)
        self.assertEqual(r.attempts, u.attempts)
        s = record_attempt_outcome(
            r,
            AttemptOutcome.SUCCEEDED,
            source_active=True,
            deadline_passed=False,
            checkpoint_ref=CP2,
        )
        self.assertEqual(s.status, RunStatus.COMPLETED)
        self.assertEqual([a.attempt_no for a in s.attempts], [1, 2])

    def test_reconcile_done_continue_source_inactive_stops(self) -> None:
        for pkg, expected_status in ((0, RunStatus.FAILED_FINAL), (1, RunStatus.COMPLETED_PARTIAL)):
            with self.subTest(packages=pkg):
                r = reconcile(
                    _unknown(packages=pkg),
                    ReconciliationResult.DONE_CONTINUE,
                    evidence_ref='evidence-1',
                    source_active=False,
                    deadline_passed=False,
                    checkpoint_ref=CP,
                )
                self.assertEqual(r.status, expected_status)
                self.assertEqual(
                    r.terminal_decision,
                    TerminalDecision(expected_status, TerminalReason.SOURCE_INACTIVE, 'retry-policy-r7', CP),
                )

    def test_reconcile_requires_evidence(self) -> None:
        with self.assertRaises(ValueError):
            reconcile(
                _unknown(),
                ReconciliationResult.ALL_WORK_DONE,
                evidence_ref='',
                source_active=True,
                deadline_passed=False,
                checkpoint_ref=CP,
            )


class ReconciliationOverdueTests(unittest.TestCase):
    def test_overdue_unknown_keeps_waiting_with_warning(self) -> None:
        u = _unknown()
        self.assertEqual(u.status, RunStatus.WAITING_RECONCILIATION)
        with self.assertLogs('source_ingestion.domain.collection_run', level='WARNING'):
            o = flag_reconciliation_overdue(u, warning='reconcile deadline passed')
        self.assertEqual(o.status, RunStatus.WAITING_RECONCILIATION)
        self.assertEqual(o.warnings, ('reconcile deadline passed',))
        self.assertEqual(o.attempts, u.attempts)
        self.assertIsNone(o.terminal_decision)

    def test_overdue_then_evidence_continues(self) -> None:
        u = _unknown()
        self.assertEqual(u.status, RunStatus.WAITING_RECONCILIATION)
        with self.assertLogs('source_ingestion.domain.collection_run', level='WARNING'):
            o = flag_reconciliation_overdue(u, warning='reconcile deadline passed')
        r = reconcile(
            o,
            ReconciliationResult.ALL_WORK_DONE,
            evidence_ref='evidence-late',
            source_active=True,
            deadline_passed=True,
            checkpoint_ref=CP,
        )
        self.assertEqual(r.status, RunStatus.COMPLETED)
        self.assertEqual(
            r.terminal_decision,
            TerminalDecision(RunStatus.COMPLETED, TerminalReason.ALL_WORK_DONE, 'retry-policy-r7', CP),
        )

    def test_overdue_only_from_waiting_reconciliation(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            flag_reconciliation_overdue(_running(), warning='x')


class TerminalDecisionTests(unittest.TestCase):
    def test_terminal_requires_checkpoint_ref(self) -> None:
        with self.assertRaises(ValueError):
            start_run(_run(), source_active=False, checkpoint_ref='')

    def test_record_committed_packages_rejects_invalid_count(self) -> None:
        for n in (0, -1, True):
            with self.subTest(count=n):
                with self.assertRaises(ValueError):
                    record_committed_packages(_running(), n)  # type: ignore[arg-type]
