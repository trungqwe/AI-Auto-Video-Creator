# M1-P1 — Trace matrix

| Test ID | Test code | Contract/invariant | Evidence chính |
|---|---|---|---|
| TST-M1-P1-001 | duplicate tuần tự và đồng thời | CT-CMN idempotency, INV-001 | `final-test-results.xml` |
| TST-M1-P1-002 | reused key, payload khác | CT-CMN conflict | `green-1-test-results.xml` |
| TST-M1-P1-003 | crash sau mutation trước outbox | ADR-0004 atomic outbox | `green-1-test-results.xml` |
| TST-M1-P1-004 | duplicate/reorder và crash sau dispatch | CT-EVT, INV-002 | `green-2-test-results.xml`, `green-4-test-results.xml` |
| TST-M1-P1-005 | lost ACK, service mới đọc receipt | CT-WF receipt | `green-2-test-results.xml` |
| TST-M1-P1-006 | generation/epoch cũ | CT-WF-004/006, INV-003/016 | `green-2-test-results.xml` |
| TST-M1-P1-007 | outcome unknown | operation receipt/reconcile | `green-2-test-results.xml` |
| TST-M1-P1-008 | sensitive canary | CT-CMN-013, INV-012 | `final-test-results.xml`, `secret-scan.md` |
| TST-M1-P1-009 | completion crash ở bảy boundary | CT-ORC-008/009, CT-MED-008, INV-010/017 | `green-3-test-results.xml` |
| TST-M1-P1-010 | completion lost ACK/giao lặp | CT-ORC-008/009, INV-001/010/017 | `green-3-test-results.xml`, `state-after-completion.txt` |
