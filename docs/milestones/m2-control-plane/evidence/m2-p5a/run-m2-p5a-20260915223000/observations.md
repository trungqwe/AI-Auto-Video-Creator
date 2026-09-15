# M2-P5A implementation observations

Implementation GREEN was run after source commit `0b862b9b75bbee32a61bc29b466f4d9b1f564dbf` with the frozen oracle unchanged at SHA-256 `A9C809332309A934E83DE5AB37A8A2A29261E86E3E38386878CB765C7B70A1F8`.

The five exact P5A identities collected and passed. The implementation persists canonical JCS/request hashes, keeps immutable configuration facts unchanged across the authorized state graph, performs revision CAS, emits redacted P3 outbox events on committed transitions, rejects plaintext-shaped secret inputs, and enforces workspace scoping. Migration `0004` and its rollback were exercised against disposable PostgreSQL databases; FK, unique, positive-number, lowercase-hex hash, rollback, and no-secret-column probes passed.

The final race proof has an explicit name-defined immutable snapshot and separately asserts `revision == 2` and `status == PUBLISHED`. The independent full-field snapshot remains the oracle for forbidden, stale, foreign-workspace, and rollback zero-mutation paths.

P4, P3, P2, P1 and architecture regressions were executed in this run. The frozen P0 33-test and M1 93-test reports are immutable accepted closure artifacts copied with their original PASS results; their provenance is recorded in `commands.jsonl`. Domain-to-application imports are zero, disposable database orphans are zero, and the secret scan is CLEAN/0.

No P5B/P6+/M3/Module A, HTTP/UI/Temporal/provider, `pyproject.toml`, `uv.lock`, P1-P4 source, or `MigrationRunner` changes were made. Earlier RED evidence runs remain untouched.
