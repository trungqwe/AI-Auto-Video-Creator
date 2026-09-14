# Correction RED observation: RFC 8785 Number serialization

- **Mandatory oracle:** `test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt`
- **Phase:** correction RED, before the Number serializer source change.
- **Expected failure:** a general fixed-decimal conversion must retain meaningful trailing integer zeroes for the RFC 8785 Appendix B binary64 value near `2^68`; the expected canonical bytes are `295147905179352830000`.
- **Observed failure:** `canonicalize_json(value)` returned `b'2951479051793528'` rather than `b'295147905179352830000'` because the pre-correction fixed-format path stripped all trailing `0` characters.
- **Raw source evidence:** `correction-red-jcs-numbers-stdout.txt`.

The direct failure is an oracle failure in JCS Number serialization, not a fixture, PostgreSQL prerequisite, import, or setup failure. The RFC vector was subsequently corrected to use the exact binary64 value represented by `0x1.0p+68`; the prior hexadecimal literal represented a different adjacent value.
