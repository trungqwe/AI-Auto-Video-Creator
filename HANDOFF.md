# HANDOFF

- Đã commit và push oracle correction `4990eb5b37057dddce66249970a0d482c854c369` (`test(m2-p5a): correct postgres and cas closure oracles`). RED mới được ghi bất biến tại `docs/milestones/m2-control-plane/evidence/m2-p5a/run-m2-p5a-20260916000000/`; hash DAG PASS. RED có đúng 5 collect, 3 failure hành vi (CAS stale-current, side effect shared ledger, global psycopg patch), 2 pass, không error/skip.
- Đã commit và push P3 historical oracle compatibility `0dfcb09`: P3-001 dùng sandbox byte-exact migrations 0001--0003, chứng minh ledger `(1,2,3)` trước rollback và `(1,2)` sau rollback. Không đổi `MigrationRunner`, shared ledger hay P3 production source.
- Worktree hiện có source correction **chưa commit**: bỏ global `psycopg.Connection.execute` patch, đưa adapter PostgreSQL P5A sang `infrastructure/db/config_security`, sửa stale CAS trả revision hiện hành, và bỏ trigger/function tác động `cp_schema_migrations` khỏi migration 0004.
- P5A/P4/P3/P2/P1 regression đạt `47 passed` (5/9/11/11/11); architecture đạt `6 passed`; app→infra/driver-patch scan và migration-ledger scan đều CLEAN.
- `BLOCKED_BASELINE: LIVE_M2_P0_EVIDENCE_INTEGRITY`: P0 mới chạy tại corrected worktree đạt `32 passed, 1 failed`; `test_tst_m2_p0_002_live_p0_evidence_is_valid` báo status.md hash manifest expected `1b1d...` nhưng bytes hiện tại `c0df...`. Không sửa M2-P0, không chạy M1, không tạo P5A source checkpoint/final implementation evidence, không bắt đầu P5B/P6+/M3/Module A.
- Không amend/reset/force; không commit worktree P5A source khi baseline blocker chưa được giải quyết.
