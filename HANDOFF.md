# HANDOFF

- Đã quyết định: M1, M2-P0, M2-P1 và M2-P2 là `ACCEPTED / CLOSED`. M2-P3 ở `M2-P3_PLAN_READY_FOR_REVIEW`; chỉ planning và chuẩn bị Behavioral RED được ủy quyền. M2-P4..P7, M3 và Module A vẫn bị khóa.
- P3 plan khóa đúng 11 mandatory identities trong `implementation-plan.md`: migration/schema `0003`, UoW outbox atomicity, at-least-once crash/re-dispatch, dedupe/concurrency/checkpoint atomicity, schema/epoch quarantine, aggregate ordering, operation stream cursor/safe projection.
- Future P3 persistence chỉ qua active P1 UoW: application/domain không SQL/psycopg/tên bảng; adapters được phép tại `infrastructure/db/outbox/**` và `infrastructure/db/projections/**`, không pool/commit/rollback/transaction ẩn. Chưa có source, test harness, migration hoặc runtime RED P3.
- Runtime future P3: Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, PostgreSQL 18.6, `CREATEDB=true`, `psycopg_pool.ConnectionPool`; disposable DB `^m2_p3_test_[0-9a-f]+$`, orphan=0.
- Future closure giữ P3 11/11; frozen P2 11/11, P1 11/11, P0 33/33 bao gồm architecture 6/6, M1 93/93/0 skipped; P3 evidence profile/synthesizer fail-closed.
- Tệp cần đọc tiếp: `docs/milestones/m2-control-plane/spec.md`, `implementation-plan.md`, `docs/09-contracts/02-domain-events.md`, `docs/12-pre-code-checklist.md`.
- Điểm tiếp tục: independent review P3 plan. Không tạo P3 RED harness hoặc bắt đầu implementation trước approval riêng.
