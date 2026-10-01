# B�n giao phi�n l�m vi?c

## �� quy?t d?nh

- Authority hi?n h�nh gi? nguy�n: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Ph�n h? A NOT AUTHORIZED.
- Kh?c ph?c tri?t d? ph�t hi?n d?c l?p t? d?t audit c?a Sol tr�n exact candidate b5af69c7b81733df99ace98731bbd06ffee1bd1a (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Host boundary trong `test_host_boundary_harness.py` d?c quy?n c?p ph�t v� luu k� pinned key material b?t bi?n (`_InternalHostBoundaryVault.fixture_keypairs` v� `_InternalHostBoundaryVault.fixture_public_keys` d?ng `MappingProxyType`) cho to�n b? `ALLOWED_FIXTURE_KEY_IDS` (`rev_key_lead_v1`, `integ_gatekeeper_v1`, `control_authority_v1`).
  2. B? sung `_validate_and_resolve_fixture_pinned_keys`: t? ch?i tuy?t d?i m?i caller-selected public key bytes v?i `ProtocolViolationError` fail-closed; kh�ng cho ph�p candidate t? ch?n key authority d� key ID thu?c whitelist.
  3. B? sung helper `get_fixture_authority_keypair` v� `get_fixture_authority_public_key` (c�ng b� danh `TrustedHostFixturePrivateKey` / `TrustedHostFixturePublicKey`) ph?c v? test harness l?y key material ch�nh danh.
  4. C?p nh?t 11 test fixture trong `test_negative_fixtures.py` l?y key material ch�nh danh t? host boundary thay v� t? sinh public key bytes.
  5. B? sung regression counterexample an to�n c?a Sol trong `test_18y` (fresh subprocess): ch?ng minh n? l?c truy?n public key bytes t? ch?n cho `rev_key_lead_v1` b? t? ch?i fail-closed (`ALLOWED_ID_ATTACKER_KEY_ACCEPTED == False`), v� ch? k� host-owned x�c minh th�nh c�ng (positive control).
  6. Ni�m phong to�n di?n c�c helper m?i trong `_SealedFixtureModule` (`_SEALED_ATTRS` v� ti?n t? l?c).
  7. To�n b? b? ki?m th? t? d?ng d?t **401/401 tests PASS (100%)**, 12/12 checks PASS.
  8. Tr?ng th�i k�ch ho?t production ti?p t?c b? kh�a ch?t fail-closed: `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (NOT_PROVISIONED).

## Chua quy?t d?nh

- Chua m? implementation authority cho Milestone M2-P8/P9 ho?c Milestone M3.
- Chua k�ch ho?t production mode (`PRODUCTION_ACTIVATION_BLOCKED` gi? nguy�n fail-closed).
- Ch? k?t qu? re-review c?a Sol tr�n exact candidate SHA m?i sau remediation.

## T?p c?n d?c ti?p

- `docs/parallel-delivery/test_host_boundary_harness.py` (Module harness d?c l?p ch?a out-of-process daemon, pinned key custody b?t bi?n v� trusted keystore/reviewer handoff helpers)
- `docs/parallel-delivery/test_negative_fixtures.py` (`test_18y_sol_finding_candidate_custom_key_authority_rejected_in_fresh_subprocess`, `_SealedFixtureModule`)
- `docs/parallel-delivery/validate.py` (`run_negative_fixture_suite`, `check_attestation_report_freshness`)
- `docs/parallel-delivery/security-performance-recovery.md` (M?c 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix)

## �i?m ti?p t?c

- Ch?y to�n b? gate ki?m th? v� ki?m tra m� h�a/to�n v?n d? li?u (`validate.py`).
- Commit thay d?i code/docs theo Conventional Commits.
- T�i t?o b�o c�o attestation ch�nh x�c (`python docs/parallel-delivery/validate.py --generate-report --base 4a7c8c921b7e05066505d51b168a02c3fde61317 --candidate <NEW_HEAD>`).
