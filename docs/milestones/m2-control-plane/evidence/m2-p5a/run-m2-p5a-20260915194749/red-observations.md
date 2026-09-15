# M2-P5A RED observations

Prerequisites succeeded: imports with `PYTHONPATH=src`, PostgreSQL 18.6 with `CREATEDB=true`, exact production migrations 0001--0003, workspace setup, and disposable cleanup (`orphan=0`). No DSN, import, collection, setup, or closed-connection failure occurred.

| ID | Observed failure | Classification |
|---|---|---|
| P5A-001 | `ConfigRevisionService` raises `NotImplementedError` | `VALID_BEHAVIORAL_RED` |
| P5A-002 | `SecretHandleStore` raises `NotImplementedError` | `VALID_BEHAVIORAL_RED` |
| P5A-003 | `ConfigEventFactory` raises `NotImplementedError` | `VALID_BEHAVIORAL_RED` |
| P5A-004 | Production 0004 forward/rollback absent after exact 0001--0003 baseline | `VALID_BEHAVIORAL_RED` |
| P5A-005 | Production-facing `ConfigRevisionService` creation raises `NotImplementedError` | `VALID_BEHAVIORAL_RED` |

Exact result: 5 collected, 5 failed, 0 errors, 0 skipped.
