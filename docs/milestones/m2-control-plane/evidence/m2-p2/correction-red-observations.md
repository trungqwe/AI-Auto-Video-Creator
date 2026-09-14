# M2-P2 correction RED observations

Candidate `32cb427` was observed before production fixes. Existing mandatory identities were hardened without renaming or adding identities.

- P2-001: invalid RFC3339 calendar/time values and non-integer `contract_version` were accepted; observed `DID NOT RAISE ValueError`.
- P2-002: non-URI `type` was accepted; observed `DID NOT RAISE ValueError`.
- P2-004: the hardened numeric vectors and supplied `command_id` preservation were added before the correction. The prior implementation used Python number rendering and generated a replacement command ID; this was the correction target.

Raw P2-001/P2-002 output is preserved in `correction-red-contracts-stdout.txt`. Historical original RED evidence is unchanged.
