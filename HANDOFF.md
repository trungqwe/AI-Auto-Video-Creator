# Bàn giao phiên làm việc

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate `2eb47f67b69445e38275f193aeab835731b52ced` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`):
  1. Loại bỏ hoàn toàn private key material khỏi candidate-readable và in-process APIs: xóa bỏ `_InternalHostBoundaryVault.fixture_keypairs`, `get_fixture_authority_keypair`, `TrustedHostFixturePrivateKey`.
  2. Toàn bộ khóa riêng tư Ed25519 cho fixture authorities (`rev_key_lead_v1`, `integ_gatekeeper_v1`, `control_authority_v1`) được tạo và lưu trữ độc quyền trong tiến trình con daemon ngoài tiến trình; client/harness chỉ sở hữu immutable public keys (`fixture_public_keys` dạng `MappingProxyType`).
  3. Bổ sung giao thức IPC ký mờ `SIGN_FIXTURE_PAYLOAD` trong daemon với xác thực HMAC host token; cung cấp các helper ký mờ: `host_sign_fixture_payload`, `host_sign_review_envelope`, `host_sign_integration_envelope` (cùng các bí danh `TrustedHostSign*`).
  4. Cập nhật toàn bộ các bài kiểm thử ký phong bì trong `test_negative_fixtures.py` sang sử dụng helper IPC ký mờ.
  5. Bổ sung `test_18z` kiểm chứng toàn diện các tiêu chí nghiệm thu của Sol: từ chối import/export private key trong tiến trình con mới, từ chối phong bì do candidate tự ký, xác minh chữ ký do host phát hành, bảo vệ chống replay đơn lẻ và đồng thời, dọn dẹp sạch tiến trình khi dừng, duy trì `PRODUCTION_ACTIVATION_BLOCKED`.
  6. Niêm phong các helper ký mờ mới trong `_SealedFixtureModule` (`_SEALED_ATTRS`).
  7. Trạng thái kích hoạt production tiếp tục bị khóa chặt fail-closed: `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (`PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- `docs/parallel-delivery/test_host_boundary_harness.py` (Harness độc lập quản lý out-of-process daemon, key custody ngoài tiến trình, và helper ký mờ IPC)
- `docs/parallel-delivery/test_negative_fixtures.py` (`test_18z_sol_finding_fixture_authority_private_key_custody_remediated`, `_SealedFixtureModule`)
- `docs/parallel-delivery/validate.py` (`run_negative_fixture_suite`, `check_attestation_report_freshness`)
- `docs/parallel-delivery/security-performance-recovery.md` (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix)

## Điểm tiếp tục

- Chạy toàn bộ suite validation và test fixtures (`validate.py`).
- Commit thay đổi code/docs theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (`python docs/parallel-delivery/validate.py --generate-report --base 4a7c8c921b7e05066505d51b168a02c3fde61317 --candidate <NEW_HEAD>`).
- Push lên remote branch `trungqwe/parallel-architecture-revolution` và gửi worker_done.
