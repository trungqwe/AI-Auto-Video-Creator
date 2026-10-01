# Bàn giao phiên làm việc

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate a7d982095108f7028ec208117d95231a62d55988 (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Tách toàn bộ cơ chế trusted host boundary test harness, lifecycle authority, credentials và các helper (`_InternalHostBoundaryVault`, `_ensure_internal_host_boundary_harness`, `_stop_internal_host_boundary_harness`, `TrustedHostReviewerHandoff`, `TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore`, `TrustedHostProvisionKeyStore`, `TEST_FIXTURE_REVIEWER_SECRET`) ra khỏi module candidate-readable `test_negative_fixtures.py`, chuyển sang module riêng biệt `test_host_boundary_harness.py`.
  2. Xóa bỏ hoàn toàn `setUpModule`, `tearDownModule`, các helper và credential khỏi `test_negative_fixtures.py`, vô hiệu hóa triệt để kỹ thuật bypass qua base descriptor `types.ModuleType.__getattribute__(f, '__dict__')`.
  3. Bổ sung whitelist bất biến `ALLOWED_FIXTURE_KEY_IDS` từ chối fail-closed bất kỳ custom key ID nào (`'custom_key'`).
  4. Khởi tạo harness ở cấp test runner trong `validate.py:run_negative_fixture_suite` và CLI entrypoint.
  5. Cập nhật regression `test_18y` trong fresh subprocess chứng minh raw module dictionary bypass không thể lấy được bất kỳ lifecycle hay helper authority nào, `RAW_MODULE_DICT_CUSTOM_KEY_ACCEPTED == False`, và phát sinh bằng chứng `SOL_CUSTOM_KEY_AUTHORITY_REJECTED_PASS`.
  6. Toàn bộ bộ kiểm thử tự động đạt **401/401 tests PASS (100%)**.
  7. Trạng thái kích hoạt production tiếp tục bị khóa chặt fail-closed: `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (`PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- `docs/parallel-delivery/test_host_boundary_harness.py` (Module harness độc lập chứa out-of-process daemon và trusted keystore/reviewer handoff helpers)
- `docs/parallel-delivery/test_negative_fixtures.py` (`test_18y_sol_finding_candidate_custom_key_authority_rejected_in_fresh_subprocess`, `_SealedFixtureModule`)
- `docs/parallel-delivery/validate.py` (`run_negative_fixture_suite`, `check_attestation_report_freshness`)
- `docs/parallel-delivery/security-performance-recovery.md` (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix)

## Điểm tiếp tục

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu (`validate.py`).
- Commit thay đổi code/docs theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (`python docs/parallel-delivery/validate.py --generate-report --base 4a7c8c921b7e05066505d51b168a02c3fde61317 --candidate <NEW_HEAD>`).
