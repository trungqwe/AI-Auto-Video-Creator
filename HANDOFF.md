# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate 2798fd6f4af760f757ae41d5beab53408cc5a0da (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Loại bỏ hoàn toàn _HOST_BOUNDARY_BOOTSTRAP_PRIVATE_KEY_BYTES và _HOST_BOUNDARY_BOOTSTRAP_SIGNING_KEY khỏi test_negative_fixtures.py và toàn bộ repository.
  2. Triển khai cơ chế external signer daemon ngoài tiến trình (_launch_test_host_boundary_daemon): cặp khóa Ed25519 được sinh trong RAM của daemon, chỉ xuất khóa công khai qua pipe để ghim bất biến; factory TrustedHostBootstrapCapability ủy quyền ký số mật mã qua IPC với xác thực HMAC host_secret.
  3. Ghim khóa công khai bất biến qua HostBoundaryBootstrapCapability.pin_trusted_host_public_key; cấm tuyệt đối candidate worker trong tiến trình tự ý ghim hay thay đổi khóa đã ghim (ProtocolViolationError).
  4. Bổ sung fixture test_18u: chứng minh quét toàn bộ tệp được Git theo dõi trong repository không tìm thấy private key hay chuỗi hex của khóa đã thu hồi, và candidate không thể mint bất kỳ verifiable bootstrap capability nào (SAFE_ASSERTION_TRACKED_KEY_CAN_MINT_VERIFIABLE_CAPABILITY = False).
  5. Bộ kiểm thử tự động đạt **397/397 tests PASS (100%)**.
  6. Trạng thái kích hoạt production tiếp tục bị khóa chặt fail-closed: ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (PRODUCTION_ACTIVATION_BLOCKED giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- docs/parallel-delivery/security-performance-recovery.md (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix, Prerequisites Inventory)
- docs/parallel-delivery/delivery_engine.py (HostBoundaryChannel, HostBoundaryTicket, HostBoundaryTicketIssuer, HostBoundaryBootstrapCapability, KeyStoreHostIssuer, KeyStoreHostHandoff, TrustedKeyStore, DurableConsumptionRegistry)
- docs/parallel-delivery/test_negative_fixtures.py (TestSolTrustBoundaryRootCauseRemediation)

## Điểm tiếp tục

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu (validate.py).
- Commit thay đổi code/docs theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (python docs/parallel-delivery/validate.py --generate-report --base 4a7c8c921b7e05066505d51b168a02c3fde61317 --candidate <NEW_HEAD>).
- Commit tệp .validation-report.json và push lên origin/trungqwe/parallel-architecture-revolution.
- Gửi worker_done với --outcome succeeded.
