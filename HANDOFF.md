# HANDOFF

- Đã quyết định:
  1. M1 là `ACCEPTED / CLOSED` (93/93 hồi quy PASS); M2-P0 là `ACCEPTED / CLOSED` tại `d84c1d7` (33/33 P0, 93/93 M1, 6/6 gates PASS).
  2. Independent audit đối chiếu commit `e42bd90e8cd8ff0e688a2db78407ef9e32d660b9` xác nhận `M2-P1_RED_CONFIRMED`: PostgreSQL 18.6 chạy exact 11 oracle function-scoped, 11/11 Behavioral RED cấp package (5 direct-target, 6 upstream-path), 0 setup failure, 0 unexpected pass, 0 orphan database.
  3. M2-P1 implementation được ủy quyền đúng Allowed File Scope: migration raw SQL, safety guard, UoW/pool, repositories và identity use cases, P1 evidence extension. P0 không đổi; P2/M3/Phân hệ A vẫn `NOT AUTHORIZED`.
- Tệp cần đọc tiếp: `docs/12-pre-code-checklist.md`, `docs/milestones/m2-control-plane/implementation-plan.md`, `docs/milestones/m2-control-plane/evidence/m2-p1/red-observations.md`, `tests/m2/test_p1_db_and_workspace.py`, `src/controlplane/infrastructure/db/migration_runner.py`, `uow.py`, `safety.py` và identity ports.
- Điểm tiếp tục: triển khai P1 theo `RED → IMPLEMENT → RUN → TEST → FIX → VERIFY → EVIDENCE → COMMIT`; không hạ/đổi 11 oracle. Sau 11/11 GREEN, frozen P0 33/33, M1 93/93, six P1 gates/evidence verifier PASS thì dừng `M2-P1_READY_FOR_REVIEW`; không mở P2.
