# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để hai phát hiện trust-boundary từ đợt independent audit của Sol trên exact candidate d7f0043d99c970e3d6efc7a8c392be73b58b27b2 (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Vô hiệu hóa key custody bootstrap trong tiến trình: TrustedKeyStore.register_pinned_public_key từ chối caller in-process fail-closed; chuyển cấp phát khóa sang KeyStoreHostIssuer, KeyStoreHostHandoff, và KeyStoreHostIssuerCapability từ ranh giới máy chủ bên ngoài; pinned keys lưu trong MappingProxyType bất biến; OrcaDeliveryAdapter.keystore là read-only property trỏ về TrustedKeyStore.get_default().
  2. Tiêu thụ nguyên tử SignedIntegrationEnvelope qua DurableConsumptionRegistry.check_and_consume_integration: kiểm tra temporal validity, ràng buộc danh tính task/candidate/base, chống phát lại phong bì, chống tái sử dụng nonce, monotonic fencing token theo miền, bền vững qua restart SQLite và tương tranh đa luồng.
  3. Bộ kiểm thử đạt **390/390 tests PASS (100%)**, bổ sung 4 bài test probe (	est_11, 	est_12, 	est_13, 	est_14) trong TestSolTrustBoundaryRootCauseRemediation.
  4. Trạng thái kích hoạt production tiếp tục bị khóa fail-closed: ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (PRODUCTION_ACTIVATION_BLOCKED giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- docs/parallel-delivery/security-performance-recovery.md (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix, Prerequisites Inventory)
- docs/parallel-delivery/delivery_engine.py (TrustedKeyStore, KeyStoreHostIssuer, KeyStoreHostHandoff, DurableConsumptionRegistry, TrustedIntegrationConsumer)
- docs/parallel-delivery/test_negative_fixtures.py (TestSolTrustBoundaryRootCauseRemediation)

## Điểm tiếp tục

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu.
- Commit thay đổi theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (python docs/parallel-delivery/validate.py --generate-report).
- Commit tệp .validation-report.json và push lên origin/trungqwe/parallel-architecture-revolution.
- Gửi worker_done với --outcome succeeded.
