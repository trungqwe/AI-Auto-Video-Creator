# HANDOFF

- Đã quyết định:
  1. M1 tiếp tục `ACCEPTED / CLOSED` (93/93 hồi quy PASSED); M2-P0 tiếp tục `ACCEPTED / CLOSED` tại `d84c1d7` (33/33 P0, 93/93 M1, 6/6 gates PASS).
  2. M2-P1 vẫn `AUTHORIZED TO IMPLEMENT`, nhưng independent re-audit HEAD `747d609cfdf226371e1d5b2f4b73d240cd8210de` cấm Behavioral RED trước User Approval.
  3. `implementation-plan.md` đã khóa correction cuối: P1-007 chỉ dùng read/status/revoke/expire theo workspace; đủ traceability 11 oracle; P0 regression đòi exact accepted set 33 testcase; mutation migration chỉ trong sandbox; teardown đóng target connections rồi admin drop đúng fixture database.
  4. Không code P1, không RED test, không sửa P0 implementation, không mở P2; M3/Phân hệ A vẫn `NOT AUTHORIZED`.
- Chưa quyết định: User Approval cho Behavioral RED M2-P1.
- Tệp cần đọc tiếp: `docs/milestones/m2-control-plane/spec.md`, `docs/milestones/m2-control-plane/implementation-plan.md`, `docs/12-pre-code-checklist.md`.
- Điểm tiếp tục: `M2-P1_PLAN_READY_FOR_RED_APPROVAL`. Sau User Approval, chỉ chuẩn bị structural stubs importable tối thiểu (nếu cần), rồi mới chứng kiến Behavioral RED hợp lệ của `tests/m2/test_p1_db_and_workspace.py` và lưu `red-p1-stdout.txt`.
