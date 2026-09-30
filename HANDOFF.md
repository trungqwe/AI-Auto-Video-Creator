# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate d1edb5073314fc66488820f8d66ae0655a210fb2 (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Năng lực khởi tạo host bất biến HostBoundaryBootstrapCapability: Xây dựng lớp thẩm quyền HostBoundaryBootstrapCapability được cấp độc quyền ngoài tiến trình bởi host boundary (_create_authenticated); cấm caller in-process khởi tạo trực tiếp, kế thừa, hoặc deserialize fail-closed với ProtocolViolationError. Ràng buộc mật mã HMAC-SHA256 với secret nội bộ của host boundary, kiểm tra độ tươi (freshness 300s, max skew 30s) và tiêu thụ đơn dụng (_consume_for_provisioning).
  2. Ràng buộc thẩm quyền host vào HostBoundaryTicketIssuer: Yêu cầu HostBoundaryBootstrapCapability khi cấp phát ticket (issue_ticket), đối chiếu bắt buộc port và authkey phải khớp chính xác với bootstrap capability; từ chối fail-closed mọi trường hợp thiếu capability hoặc sai lệch endpoint (Host ticket issuance rejected).
  3. Thẩm định endpoint và tiêu thụ đơn dụng trong provision_channel: Bắt buộc phải có HostBoundaryBootstrapCapability hợp lệ (qua ticket hoặc trực tiếp); xác minh chữ ký HMAC, khớp cổng/authkey, và tiêu thụ đơn dụng chống replay qua _consumed_bootstrap_ids trước khi gán _started = True. Mọi endpoint/ticket do caller tự tạo đều bị từ chối fail-closed với ROGUE_ENDPOINT_TICKET_ACCEPTED == False.
  4. Bổ sung fixture fresh subprocess test_18s: Chứng minh trong tiến trình con độc lập, caller tự mở listener trên cổng nội bộ với rogue token/authkey và rogue ticket đều bị từ chối fail-closed, HostBoundaryChannel._started giữ nguyên False.
  5. Bộ kiểm thử tự động đạt **395/395 tests PASS (100%)**.
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

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu.
- Commit thay đổi theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (python docs/parallel-delivery/validate.py --generate-report).
- Commit tệp .validation-report.json và push lên origin/trungqwe/parallel-architecture-revolution.
- Gửi worker_done với --outcome succeeded.
