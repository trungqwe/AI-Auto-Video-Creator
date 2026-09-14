# HANDOFF

- Đã quyết định: M1, M2-P0, M2-P1 và M2-P2 là `ACCEPTED / CLOSED`. M2-P3 ở `M2-P3_IMPLEMENTATION_READY_FOR_REVIEW`: exact 11 GREEN, frozen regressions và closure evidence đã hoàn tất; chờ independent audit. M2-P4..P7, M3 và Module A vẫn bị khóa.
- P3 đã triển khai migration `0003`/rollback, adapter PostgreSQL qua active P1 UoW, outbox, checkpoint/quarantine, ordering và operation stream. `p3_projection_effects` vẫn chỉ là probe test được inject; không có API/UI/P4.
- P3 persistence chỉ qua active P1 UoW: application/domain không SQL/psycopg/tên bảng; adapters tại `infrastructure/db/outbox/**` và `infrastructure/db/projections/**` không pool/commit/rollback/transaction ẩn. Có đúng 11 test identities bất biến.
- Runtime future P3: Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, PostgreSQL 18.6, `CREATEDB=true`, `psycopg_pool.ConnectionPool`; disposable DB `^m2_p3_test_[0-9a-f]+$`, orphan=0.
- Closure hiện hành: P3 11/11; frozen P2 11/11, P1 11/11, P0 33/33 bao gồm architecture 6/6, M1 93/93/0 skipped; P3 evidence profile/synthesizer PASS, orphan=0, secret scan CLEAN.
- Tệp cần đọc tiếp: `docs/milestones/m2-control-plane/spec.md`, `implementation-plan.md`, `docs/09-contracts/02-domain-events.md`, `docs/12-pre-code-checklist.md`.
- Điểm tiếp tục: independent audit P3 closure evidence. Không mở M2-P4/M3/Module A.
