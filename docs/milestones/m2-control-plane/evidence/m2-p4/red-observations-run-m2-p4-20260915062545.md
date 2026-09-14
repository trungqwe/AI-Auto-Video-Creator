# M2-P4 hardened Behavioral RED observations

- Run ID: `run-m2-p4-20260915062545`.
- Authoritative accepted-plan SHA: `0cff8d77ffed71dcceffce73b1fbb372f5a48425`.
- Interpreter: `.venv\\Scripts\\python.exe`, Python 3.13.15. The suite remains pure Python: no PostgreSQL, `M2_TEST_PG_DSN`, Docker, Temporal, network, or filesystem fixture.
- Collection: exact 9 identities. Full execution: 9 failed, 0 errors, 0 skips. Each failure reached a P4 structural seam and observed `NotImplementedError`; no import, syntax, fixture, or collection failure occurred.
- Architecture regression: accepted P0 architecture subset 6 passed. Secret scan: `CLEAN`, 0 findings.
- Scope: only the existing P4 test harness, new immutable P4 run evidence, and narrow P4 RED handoff/changelog wording changed. Structural production seams are byte-identical and behaviorless.

Hardening retained the exact nine identities while adding future-GREEN assertions for safe `aggregate_type`, evidence-gated Stage Run reconciliation, no outgoing edges from Stage Run wait/retry/terminal states, artifact cleanup eligibility and no-recovery closure, and every-target terminal closure for Batch, Job, and Operation.

| Test ID | Expected behavioral RED | Observed failure | Classification |
|---|---|---|---|
| P4-001 | Operation lifecycle/revision behavior absent | `NotImplementedError` from `transition_operation` | `VALID_BEHAVIORAL_RED` |
| P4-002 | Job/Batch forbidden-transition behavior absent | `NotImplementedError` from `transition_job` | `VALID_BEHAVIORAL_RED` |
| P4-003 | OperationView pure mapper absent | `NotImplementedError` from `map_operation_view` | `VALID_BEHAVIORAL_RED` |
| P4-004 | Artifact lifecycle/cleanup behavior absent | `NotImplementedError` from `transition_artifact_location` | `VALID_BEHAVIORAL_RED` |
| P4-005 | Batch lifecycle/terminal behavior absent | `NotImplementedError` from `transition_batch` | `VALID_BEHAVIORAL_RED` |
| P4-006 | Job lifecycle/terminal behavior absent | `NotImplementedError` from `transition_job` | `VALID_BEHAVIORAL_RED` |
| P4-007 | Stage Run reconcile/no-outgoing behavior absent | `NotImplementedError` from `transition_stage_run` | `VALID_BEHAVIORAL_RED` |
| P4-008 | Operation forbidden/evidence-gate behavior absent | `NotImplementedError` from `transition_operation` | `VALID_BEHAVIORAL_RED` |
| P4-009 | Pure stale-revision behavior absent | `NotImplementedError` from `transition_operation` | `VALID_BEHAVIORAL_RED` |

Classification totals: `VALID_BEHAVIORAL_RED=9`; `UPSTREAM_PATH_RED=0`; `INVALID_SETUP_FAILURE=0`; `ORACLE_MISMATCH=0`; `UNEXPECTED_PASS=0`.

Raw source artifacts:

- `red-p4-run-m2-p4-20260915062545-prerequisite-stdout.txt`
- `red-p4-run-m2-p4-20260915062545-collect-stdout.txt`
- `red-p4-run-m2-p4-20260915062545-stdout.txt`
- `red-p4-run-m2-p4-20260915062545-architecture-stdout.txt`
- `red-p4-run-m2-p4-20260915062545-secret-scan-final-stdout.txt` (final scope; earlier raw scan is retained)
