# Correction RED observation: persisted receipt result on replay

- **Mandatory oracle:** `test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt`
- **Phase:** correction RED, before the repository correction.
- **Expected failure:** a same-key/same-hash replay must return the persisted receipt logical-result fields after the durable receipt is updated directly in the test database.
- **Observed failure:** the replay result contained only `receipt_id`, `command_id`, and transient `disposition="duplicate"`; reading `operation_id` raised `KeyError`.
- **Raw source evidence:** `correction-red-replay-receipt-stdout.txt`.

This is a direct repository-oracle failure. PostgreSQL setup, disposable database creation, JCS canonicalization, and the first accepted submission completed before the failed replay assertion.
