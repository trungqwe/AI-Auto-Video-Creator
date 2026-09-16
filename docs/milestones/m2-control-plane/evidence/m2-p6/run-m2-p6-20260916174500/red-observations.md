# M2-P6 corrected Behavioral RED

Exact four tests reach the intended application seams and fail only with capability-specific `NotImplementedError`. The corrected oracle uses the actual capacity-race winner, locks idempotent duplicate completion to one ledger identity, and keeps future parent seeding test-only behind the presence of migration `0006`. PostgreSQL 18.6 prerequisites and migrations `0001..0005` pass; migration `0006` is absent. No P6 persistence behavior is implemented.
