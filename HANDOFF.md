# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate 52a279551f8bd73e0d0dc3f68aad15c959be0bd8 (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Thẩm quyền host capability hoạt động ngoài tiến trình qua HostBoundaryChannel: Loại bỏ hoàn toàn sự tin tưởng vào biến môi trường mutable `os.environ["ORCA_HOST_BOUNDARY_TOKEN"]`; verifier daemon chạy trong tiến trình con độc lập kết nối qua socket nội bộ 127.0.0.1 và private pipe truyền secret; candidate caller trong cùng tiến trình cấm khởi động lại daemon fail-closed (`ProtocolViolationError`).
  2. Từ chối toàn diện nỗ lực tự đặt biến môi trường của candidate: Mọi counterexample trong đó candidate gán `os.environ["ORCA_HOST_BOUNDARY_TOKEN"] = token` để mint handoff hoặc bootstrap `KeyStoreHostIssuer` / `TrustedKeyStore` đều bị từ chối fail-closed.
  3. Bổ sung các fixture phân biệt 11t, 11u, 11v trong `test_11_finding_01_candidate_key_custody_bootstrap_rejected` và bài test độc lập `test_17_finding_out_of_process_host_boundary_and_mutable_env_rejection`.
  4. Bộ kiểm thử tự động đạt **393/393 tests PASS (100%)**.
  5. Trạng thái kích hoạt production tiếp tục bị khóa chặt fail-closed: `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (`PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- docs/parallel-delivery/security-performance-recovery.md (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix, Prerequisites Inventory)
- docs/parallel-delivery/delivery_engine.py (HostBoundaryChannel, KeyStoreHostIssuer, KeyStoreHostHandoff, TrustedKeyStore, DurableConsumptionRegistry)
- docs/parallel-delivery/test_negative_fixtures.py (TestSolTrustBoundaryRootCauseRemediation)

## Điểm tiếp tục

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu.
- Commit thay đổi theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (python docs/parallel-delivery/validate.py --generate-report).
- Commit tệp .validation-report.json và push lên origin/trungqwe/parallel-architecture-revolution.
- Gửi worker_done với --outcome succeeded.
