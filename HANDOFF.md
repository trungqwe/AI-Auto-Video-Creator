# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate 0032962130d21dc9b2ddc5f51260cfffb40e9acd (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Vô hiệu hóa khởi tạo trực tiếp và kế thừa HostBoundaryTicket: Chuyển `HostBoundaryTicket` thành lớp thẩm quyền bất biến; cấm gọi `__init__`, `__init_subclass__`, và serialize/deserialize `__reduce__` fail-closed với `ProtocolViolationError`; chỉ khởi tạo qua factory method nội bộ có xác thực `_create_authenticated`.
  2. Ràng buộc chữ ký mật mã HMAC và năng lực HostBoundaryTicketIssuerCapability: Cấp phát ticket gắn chặt với `HostBoundaryTicketIssuerCapability` có chữ ký HMAC-SHA256 liên kết với `ticket_id`, `port`, `authkey_hash`, authority id, và timestamp kiểm tra độ tươi (freshness window 300s). Phương thức `issue_ticket` yêu cầu token nội bộ và xác thực với daemon máy chủ ngoài tiến trình trước khi cấp phát.
  3. Xác minh provenance hai chiều qua daemon máy chủ ngoài tiến trình trong provision_channel: `HostBoundaryChannel.provision_channel` kết nối trực tiếp tới daemon máy chủ tại `(127.0.0.1, port)` với `authkey` để xác minh secret của issuer trước khi chấp nhận cấu hình kênh; từ chối fail-closed mọi issuer tự sinh hoặc token không khớp (`FORGED_TICKET_ACCEPTED == False`).
  4. Chống replay ticket đơn dụng đa tầng: `HostBoundaryTicket` tự đánh dấu `_consumed = True`, `HostBoundaryTicketIssuer` lưu vết `_consumed_tickets`, và `HostBoundaryChannel` duy trì `_consumed_ticket_ids`, ngăn chặn tuyệt đối mọi nỗ lực tái sử dụng ticket đã cấp.
  5. Bổ sung bộ fixture kiểm thử chuyên sâu test_18: 13 trường hợp kiểm thử (18a-18m) bao quát từ chối trực tiếp, kế thừa, bypass bằng `object.__new__`, issuer giả mạo, can thiệp chữ ký, sai cổng/authkey, hết hạn timestamp, replay attack, pickle serialization và chuỗi exploit trong tiến trình con độc lập.
  6. Bộ kiểm thử tự động đạt **394/394 tests PASS (100%)**.
  7. Trạng thái kích hoạt production tiếp tục bị khóa chặt fail-closed: `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (`PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- docs/parallel-delivery/security-performance-recovery.md (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix, Prerequisites Inventory)
- docs/parallel-delivery/delivery_engine.py (HostBoundaryChannel, HostBoundaryTicket, HostBoundaryTicketIssuer, HostBoundaryTicketIssuerCapability, KeyStoreHostIssuer, KeyStoreHostHandoff, TrustedKeyStore, DurableConsumptionRegistry)
- docs/parallel-delivery/test_negative_fixtures.py (TestSolTrustBoundaryRootCauseRemediation)

## Điểm tiếp tục

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu.
- Commit thay đổi theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (python docs/parallel-delivery/validate.py --generate-report).
- Commit tệp .validation-report.json và push lên origin/trungqwe/parallel-architecture-revolution.
- Gửi worker_done với --outcome succeeded.
