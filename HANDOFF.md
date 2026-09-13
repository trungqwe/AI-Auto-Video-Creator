# HANDOFF

- Đã quyết định: M1, M2-P0 và M2-P1 là `ACCEPTED / CLOSED`. M2-P2 là `M2-P2_PLAN_READY_FOR_RED_APPROVAL_R2`: scope contracts, schema `0002`, RFC 8785 JCS property sort theo raw/unescaped unsigned UTF-16 code units, replay receipt, PostgreSQL CAS, exact 11 oracle, sáu gates và evidence protocol đã khóa.
- Semantics khóa: ProblemDetail transport-neutral đủ 12 field với required/nullability rõ; persisted receipt chỉ `accepted`/`rejected`, replay trả cùng receipt và `duplicate` transient; CAS là `UPDATE ... WHERE revision = expected_revision` qua P1 UoW, aggregate probe relation test-only.
- Chưa được phép: Behavioral RED hay implementation P2, P3, M3 và Phân hệ A.
- Tệp cần đọc tiếp: `docs/12-pre-code-checklist.md`, `docs/milestones/m2-control-plane/spec.md`, `docs/milestones/m2-control-plane/implementation-plan.md`, `docs/09-contracts/00-common-contract.md`, `docs/10-test-strategy.md`, `docs/adr/0004-commit-idempotency-and-fencing.md`.
- Điểm tiếp tục: independent review/approval plan P2; chỉ sau đó mới tạo Behavioral RED P2 và raw evidence trên PostgreSQL disposable thật.
