# HANDOFF

- Đã quyết định:
  1. M1 là `ACCEPTED / CLOSED` (93/93 hồi quy PASS); M2-P0 là `ACCEPTED / CLOSED` (33/33 P0, 93/93 M1, 6/6 gates PASS).
  2. Behavioral RED M2-P1 đã được independent audit xác nhận trước implementation; không có thay đổi oracle, không sửa P0 và không mở P2.
  3. M2-P1 implementation/evidence đã hoàn tất trong Allowed File Scope: raw SQL migration runner, safety guard, UoW/pool, repositories, identity use cases và P1 evidence profile/synthesizer.
- Bằng chứng mới: `docs/milestones/m2-control-plane/evidence/m2-p1/status.json`, `m2-p1-tests.xml`, `m2-p0-regression.xml`, `m1-regression.xml`, `secret-scan.json`, `hashes.sha256`; verifier `python -m controlplane.infrastructure.evidence.synthesizer_p1 --verify-only` đạt `VALIDATION: PASS`.
- Tệp cần đọc tiếp: `docs/12-pre-code-checklist.md`, `docs/milestones/m2-control-plane/implementation-plan.md`, `docs/milestones/m2-control-plane/evidence/m2-p1/status.md`, `src/controlplane/infrastructure/db/migration_runner.py`, `uow.py`, `repositories.py`, `src/controlplane/infrastructure/evidence/profile_p1.py` và `synthesizer_p1.py`.
- Điểm tiếp tục: dừng tại `M2-P1_READY_FOR_REVIEW` để independent audit review evidence. Không bắt đầu P2, M3 hoặc Phân hệ A.
