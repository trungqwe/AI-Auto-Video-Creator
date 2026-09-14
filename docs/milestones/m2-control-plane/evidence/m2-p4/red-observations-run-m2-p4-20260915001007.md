# M2-P4 Behavioral RED observations

- Run ID: `run-m2-p4-20260915001007`.
- Authoritative accepted-plan SHA: `0cff8d77ffed71dcceffce73b1fbb372f5a48425`.
- Interpreter: `.venv\\Scripts\\python.exe`, Python 3.13.15; suite is pure Python and did not require PostgreSQL, `M2_TEST_PG_DSN`, Docker, Temporal, network, or filesystem fixtures.
- Collection: exact 9 identities. Full execution: 9 failed, 0 errors, 0 skips. Every failure reached the final P4 structural seam and observed `NotImplementedError`; no import, syntax, fixture, or collection failure occurred.
- Architecture regression: accepted P0 architecture subset 6 passed. Secret scan: `CLEAN`, 0 findings across the changed P4 source, test, and P4 evidence paths.
- Scope: only P4 structural source/test/evidence and narrow P4 status documentation are changed. Contracts, migrations, DB/API/UI/Temporal, P1/P2/P3, P5..P7, M3, and Module A remain untouched.

| Test ID | Expected behavioral RED | Observed failure | Classification |
|---|---|---|---|
| P4-001 | Operation transition behavior and immutable revision result absent | `NotImplementedError` from `transition_operation` | `VALID_BEHAVIORAL_RED` |
| P4-002 | Forbidden transition error semantics absent | `NotImplementedError` from `transition_job` | `VALID_BEHAVIORAL_RED` |
| P4-003 | OperationView pure mapper absent | `NotImplementedError` from `map_operation_view` | `VALID_BEHAVIORAL_RED` |
| P4-004 | Artifact transition behavior absent | `NotImplementedError` from `transition_artifact_location` | `VALID_BEHAVIORAL_RED` |
| P4-005 | Batch transition behavior absent | `NotImplementedError` from `transition_batch` | `VALID_BEHAVIORAL_RED` |
| P4-006 | Job transition behavior absent | `NotImplementedError` from `transition_job` | `VALID_BEHAVIORAL_RED` |
| P4-007 | Stage Run transition/reconcile behavior absent | `NotImplementedError` from `transition_stage_run` | `VALID_BEHAVIORAL_RED` |
| P4-008 | Operation forbidden-transition behavior absent | `NotImplementedError` from `transition_operation` | `VALID_BEHAVIORAL_RED` |
| P4-009 | Pure stale-revision behavior absent | `NotImplementedError` from `transition_operation` | `VALID_BEHAVIORAL_RED` |

Classification totals: `VALID_BEHAVIORAL_RED=9`; `UPSTREAM_PATH_RED=0`; `INVALID_SETUP_FAILURE=0`; `ORACLE_MISMATCH=0`; `UNEXPECTED_PASS=0`.

Raw source artifacts:

- `red-p4-run-m2-p4-20260915001007-prerequisite-stdout.txt`
- `red-p4-run-m2-p4-20260915001007-collect-stdout.txt`
- `red-p4-run-m2-p4-20260915001007-stdout.txt`
- `red-p4-run-m2-p4-20260915001007-architecture-stdout.txt`
- `red-p4-run-m2-p4-20260915001007-secret-scan-final-stdout.txt` (final scope; earlier raw scan is retained)
