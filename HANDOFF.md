# HANDOFF

- Đã quyết định:
  1. M1 là `ACCEPTED / CLOSED` (93/93 hồi quy PASS); M2-P0 là `ACCEPTED / CLOSED` tại `d84c1d7` (33/33 P0, 93/93 M1, 6/6 gates PASS).
  2. User đã chấp thuận M2-P1 Plan tại HEAD `5ba3a1601f0e1402e54a82feb5b44fe94cda9197` và ủy quyền Behavioral RED, không ủy quyền implementation trước RED evidence hợp lệ.
  3. Audit `65af9f84f881e03e7be95d1dda44243030aca1f6` đã xác nhận 11 oracle/stub-only/P1-008 RED lịch sử. Correction tiếp theo: fixture PostgreSQL function-scoped từng oracle; P1-005 commit+rollback DB proof; P1-007 seed B non-vacuous; P1-011 `pool_max_size=1` + backend PID; application ports chỉ injected UoW factory; raw collect/prerequisite outputs đã lưu.
  4. Chỉ có structural stubs `NotImplementedError`, không có business/DB behavior, P0 không đổi, P2/M3/Phân hệ A vẫn `NOT AUTHORIZED`.
- Chưa quyết định / blocker: `M2_TEST_PG_DSN` không có trong môi trường. Sau correction, cả 11 oracle phải rerun và chưa oracle nào được tính vào `M2-P1_RED_CONFIRMED`; không dùng fallback credential hoặc mock.
- Tệp cần đọc tiếp: `docs/milestones/m2-control-plane/implementation-plan.md`, `tests/m2/test_p1_db_and_workspace.py`, `docs/milestones/m2-control-plane/evidence/m2-p1/red-observations.md`, `red-p1-collect-stdout.txt`, `red-p1-prerequisite-stdout.txt`.
- Điểm tiếp tục: `M2-P1_BEHAVIORAL_RED_BLOCKED_EXTERNAL`. Khi `M2_TEST_PG_DSN` được cấp với quyền `CREATEDB`, chạy đủ 11 oracle trên PostgreSQL database function-scoped, lưu raw stdout từng run rồi đối chiếu expected-vs-observed; chỉ sau 11 RED hợp lệ mới chuyển `M2-P1_RED_CONFIRMED`.
