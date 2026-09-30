# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để toàn bộ 2 phát hiện độc lập từ đợt audit của Sol trên exact candidate b85c240d466c1624966c36bb9148c10d2112b4ae (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Thẩm quyền host capability hoàn toàn ngoài tiến trình: Loại bỏ vĩnh viễn `_SENTINEL_HOST_TOKEN` khỏi candidate module `delivery_engine.py`; thẩm quyền host boundary được cấp phát độc lập qua biến môi trường host (`ORCA_HOST_BOUNDARY_TOKEN`) và kiểm tra mật mã HMAC thời gian thực; ngăn chặn triệt để kịch bản `COUNTEREXAMPLE_CANDIDATE_BOOTSTRAPS_AUTHORITY`. Bổ sung fixture phân biệt `11s` trong `test_negative_fixtures.py`.
  2. Bền vững hóa sổ đăng ký tiêu thụ & chống đầu độc singleton: `DurableConsumptionRegistry.get_default` cấm tuyệt đối cấu hình `db_path=':memory:'` hoặc `allow_ephemeral=True` fail-closed với `ProtocolViolationError`; `OrcaDeliveryAdapter` từ chối fail-closed nếu singleton registry mặc định bị can thiệp thành dạng ephemeral trong bộ nhớ; ngăn chặn triệt để kịch bản `COUNTEREXAMPLE_EPHEMERAL_DEFAULT_ACCEPTED`. Bổ sung fixture phân biệt `15d` trong `test_negative_fixtures.py`.
  3. Dọn dẹp toàn bộ residue khoảng trắng tại `CHANGELOG.md:30` và `docs/parallel-delivery/README.md:348,367`.
  4. Bộ kiểm thử tự động đạt **392/392 tests PASS (100%)**.
  5. Trạng thái kích hoạt production tiếp tục bị khóa chặt fail-closed: `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (`PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- docs/parallel-delivery/security-performance-recovery.md (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix, Prerequisites Inventory)
- docs/parallel-delivery/delivery_engine.py (TrustedKeyStore, KeyStoreHostIssuer, KeyStoreHostHandoff, DurableConsumptionRegistry, OrcaDeliveryAdapter, SignedIntegrationEnvelope)
- docs/parallel-delivery/test_negative_fixtures.py (TestSolTrustBoundaryRootCauseRemediation)

## Điểm tiếp tục

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu.
- Commit thay đổi theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (python docs/parallel-delivery/validate.py --generate-report).
- Commit tệp .validation-report.json và push lên origin/trungqwe/parallel-architecture-revolution.
- Gửi worker_done với --outcome succeeded.
