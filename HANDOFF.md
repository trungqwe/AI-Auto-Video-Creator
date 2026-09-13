# HANDOFF

- Đã quyết định:
  1. Milestone M1 tiếp tục `ACCEPTED / CLOSED` (93/93 tests hồi quy PASSED 100%, 0 skipped, 0 failed).
  2. Milestone M2-P0 đã được Người dùng CHẤP THUẬN chính thức (`ACCEPTED / CLOSED`) tại commit `d84c1d7` (33/33 tests PASSED, deterministic provenance 1:1, SHA-256 DAG hợp lệ).
  3. M2-P1 được ủy quyền triển khai (`M2-P1 = AUTHORIZED TO IMPLEMENT`).
  4. Hoàn tất hiệu chỉnh kế hoạch M2-P1 (docs-only correction) bám sát 10 điểm kỹ thuật hẹp của Người dùng trước khi bắt đầu Behavioral RED:
     - Đồng bộ metadata: M2 = `IMPLEMENTATION IN PROGRESS`, M2-P0 = `ACCEPTED / CLOSED`, M2-P1 = `AUTHORIZED` trong `spec.md` và `implementation-plan.md`.
     - Allowed File Scope của P1 được bổ sung chính xác `profile_p1.py` và `synthesizer_p1.py`; cấm sửa core evaluator/validator.
     - Dùng disposable TEST DATABASE (`m2_p1_test_<uuid>`), không parameterized schema; schema cố định `controlplane`; admin test DSN từ environment; destructive guard yêu cầu tên DB hợp lệ test KÈM `is_test_env=True` (cấm generic `allow_destructive=True`).
     - Phân biệt rõ `AuthSession` (`cp_auth_sessions`) phục vụ identity/control plane foundation với `AppSession` (`cp_app_sessions` dành cho desktop app data model).
     - Đầy đủ `IWorkspaceRepository`, `IActorRepository`, `IAuthSessionRepository`; workspace-scoped methods (zero unscoped get_by_id); composite FK DB-level invariants ngăn cross-workspace.
     - Khóa transaction ownership: `SqlUnitOfWork` sở hữu đúng một pooled connection và một DB transaction; repository không tự acquire pool connection, không commit/rollback; `TransactionManager` chỉ là UoW factory/coordinator.
     - Siết migration runner oracle: forward regex `^\d{4}_[a-z0-9_]+\.sql$`, rollback regex `^\d{4}_[a-z0-9_]+\.rollback\.sql$`; bounded advisory lock timeout 5s với `pg_try_advisory_lock` và monotonic deadline; fail-closed khi gap, missing file, duplicate, tamper; 0001 rollback dọn dẹp và drop schema `controlplane`.
     - Loại bỏ vòng tự tham chiếu: không đưa live evidence test vào `m2-p1-tests.xml`; lưu stdout RED thô vào `red-p1-stdout.txt`.
     - Đăng ký semantic profile tất định qua extension point `register_semantic_profile(M2P1SemanticProfile())`.
     - Khóa 6 machine-readable gates (`GATE-P1-01` .. `GATE-P1-06`) trước khi viết test RED.
  5. M3 và Phân hệ A tiếp tục bị khóa hoàn toàn (`NOT AUTHORIZED`).
- Chưa quyết định: Chưa viết code implementation và chưa viết test RED của M2-P1 (chờ Người dùng rà soát plan correction).
- Tệp cần đọc tiếp: `docs/milestones/m2-control-plane/spec.md`, `docs/milestones/m2-control-plane/implementation-plan.md`.
- Điểm tiếp tục: Dừng tại `M2-P1_PLAN_READY_FOR_RED_REVIEW`. Sau khi Người dùng duyệt plan correction, bắt đầu bước đầu tiên của M2-P1: viết bài test Behavioral RED (`tests/m2/test_p1_db_and_workspace.py`) và lưu log `red-p1-stdout.txt`.
