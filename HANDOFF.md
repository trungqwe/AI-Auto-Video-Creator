# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate bd382390340b0495d6a725bc97aa9f623720185e (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Loại bỏ hoàn toàn _HOST_BOUNDARY_BOOTSTRAP_SECRET khỏi candidate module delivery_engine.py, ghim khóa công khai Ed25519 bất biến _HOST_BOUNDARY_BOOTSTRAP_PUBLIC_KEY; candidate không thể tự ký hay truy cập secret.
  2. Khóa fail-closed toàn bộ API candidate-side minting: HostBoundaryBootstrapCapability._create_authenticated ném ProtocolViolationError; bổ sung from_host_signed_payload nhận DTO đã ký từ host và xác thực bằng Ed25519.
  3. Tách biệt factory và signing key sang trusted host test boundary (TrustedHostBootstrapCapability trong test_negative_fixtures.py), không thể gọi hay import từ candidate module. Cập nhật _launch_test_host_boundary_daemon và test_sod_18.
  4. Mở rộng test_18s và bổ sung test_18t: Chứng minh trong fresh subprocess và in-process candidate không thể đọc secret, không thể mint capability, không thể forge chữ ký, và chuỗi rogue listener -> issuer -> ticket -> provision hoàn toàn fail-closed (FULL_CHAIN_ACCEPTED == False, HostBoundaryChannel._started == False).
  5. Bộ kiểm thử tự động đạt **396/396 tests PASS (100%)**.
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
