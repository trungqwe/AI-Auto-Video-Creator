# HANDOFF

- Đã quyết định:
  1. M1 là `ACCEPTED / CLOSED` (93/93 hồi quy PASS); M2-P0 là `ACCEPTED / CLOSED` tại `d84c1d7` (33/33 P0, 93/93 M1, 6/6 gates PASS).
  2. User đã chấp thuận M2-P1 Plan tại HEAD `5ba3a1601f0e1402e54a82feb5b44fe94cda9197` và ủy quyền Behavioral RED, không ủy quyền implementation trước RED evidence hợp lệ.
  3. Có đúng 11 oracle tại `tests/m2/test_p1_db_and_workspace.py`; collection 11/11 không lỗi import/cú pháp. Chỉ có structural stubs `NotImplementedError`, không có business/DB behavior, P0 không đổi, P2/M3/Phân hệ A vẫn `NOT AUTHORIZED`.
  4. P1-008 RED hợp lệ: `DestructiveRollbackGuard.assert_allowed` ném `NotImplementedError`; stdout ở evidence P1.
- Chưa quyết định / blocker: `M2_TEST_PG_DSN` không có trong môi trường. Mười oracle PostgreSQL chưa chạy và không tính RED; không dùng fallback credential hoặc mock.
- Tệp cần đọc tiếp: `docs/milestones/m2-control-plane/implementation-plan.md`, `tests/m2/test_p1_db_and_workspace.py`, `docs/milestones/m2-control-plane/evidence/m2-p1/red-observations.md`.
- Điểm tiếp tục: `M2-P1_BEHAVIORAL_RED_BLOCKED_EXTERNAL`. Khi `M2_TEST_PG_DSN` được cấp với quyền `CREATEDB`, chạy đủ 11 oracle trên disposable PostgreSQL DB; chỉ sau 11 RED hợp lệ mới chuyển `M2-P1_RED_CONFIRMED`.
