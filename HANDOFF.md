# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate 62d7643f4c8ef474fd065edb1c026fa09fdb10d7 (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Loại bỏ hoàn toàn kiểm tra tin cậy dựa trên inspect/module-name: Xóa bỏ `import inspect` và việc tin cậy `caller_mod in ("test_negative_fixtures", "validate", "__main__")`; vô hiệu hóa `HostBoundaryChannel.start_host_boundary` fail-closed với `ProtocolViolationError` đối với mọi candidate caller (`MAIN_START_ACCEPTED == False`).
  2. Loại bỏ hoàn toàn fallback endpoint/auth từ biến môi trường mutable: Xóa bỏ `_ORCA_HOST_BOUNDARY_PORT` và `_ORCA_HOST_BOUNDARY_AUTHKEY` trong `HostBoundaryChannel.verify_capability`, từ chối mọi rogue listener qua env fail-closed (`ENV_ENDPOINT_ACCEPTED == False`).
  3. Cấp phát channel endpoint/auth qua cơ chế host bất biến ngoài tiến trình (HostBoundaryTicket): Định nghĩa `HostBoundaryTicket` do host ngoài tiến trình tạo ra; `HostBoundaryChannel.provision_channel(port, authkey, *, host_ticket, proc)` yêu cầu ticket hợp lệ; candidate caller không thể giả mạo ticket hay rebind channel; `_cleanup_process` chỉ gửi lệnh dừng khi tiến trình sở hữu `proc`.
  4. Bổ sung fresh-subprocess assertions: 3 fixture phân biệt 17h, 17i, 17j trong `test_17` bao gồm các assertion trong tiến trình con độc lập từ chối giả mạo env endpoint (`ENV_ENDPOINT_ACCEPTED == False`) và bootstrap caller `__main__` (`MAIN_START_ACCEPTED == False`, `CANDIDATE_BOOTSTRAP_ACCEPTED == False`, `TrustedKeyStore` rỗng).
  5. Bộ kiểm thử tự động đạt **393/393 tests PASS (100%)**.
  6. Trạng thái kích hoạt production tiếp tục bị khóa chặt fail-closed: `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (`PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- docs/parallel-delivery/security-performance-recovery.md (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix, Prerequisites Inventory)
- docs/parallel-delivery/delivery_engine.py (HostBoundaryChannel, HostBoundaryTicket, KeyStoreHostIssuer, KeyStoreHostHandoff, TrustedKeyStore, DurableConsumptionRegistry)
- docs/parallel-delivery/test_negative_fixtures.py (TestSolTrustBoundaryRootCauseRemediation)

## Điểm tiếp tục

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu.
- Commit thay đổi theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (python docs/parallel-delivery/validate.py --generate-report).
- Commit tệp .validation-report.json và push lên origin/trungqwe/parallel-architecture-revolution.
- Gửi worker_done với --outcome succeeded.