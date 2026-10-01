# Bàn giao phiên làm việc

## Đã quyết định

- Authority hiện hành giữ nguyên: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED.
- Khắc phục triệt để phát hiện độc lập từ đợt audit của Sol trên exact candidate 8003c13bd76e49cbd562dc6ab785299cd68161c7 (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Niêm phong hoàn toàn 4 helper `TrustedHostReviewerHandoff`, `TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore`, `TrustedHostProvisionKeyStore` trong `_SealedFixtureModule`, chặn mọi thuộc tính bắt đầu bằng `TrustedHost` fail-closed (`AttributeError`), loại bỏ khỏi `__dict__` và `dir()`, ném `ImportError` khi `from-import`.
  2. Loại bỏ side-effect tự khởi động daemon của 4 helper; yêu cầu context runner đã được khởi tạo trong `setUpModule` (`_InternalHostBoundaryVault.token` và `_InternalHostBoundaryVault.proc is not None`), ném `ProtocolViolationError` nếu gọi ngoài lifecycle kiểm thử.
  3. Bổ sung bài kiểm thử `test_18y` chứng minh fresh subprocess candidate không thể nhận diện hay gọi helper để mint keystore với public key tự chọn, `CANDIDATE_PUBLIC_HELPER_CUSTOM_KEY_ACCEPTED == False`, và phát sinh bằng chứng `SOL_CUSTOM_KEY_AUTHORITY_REJECTED_PASS`.
  4. Toàn bộ bộ kiểm thử tự động đạt **401/401 tests PASS (100%)**.
  5. Trạng thái kích hoạt production tiếp tục bị khóa chặt fail-closed: `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (NOT_PROVISIONED).

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (`PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới sau remediation.

## Tệp cần đọc tiếp

- `docs/parallel-delivery/security-performance-recovery.md` (Mục 8: Threat Model, Out-of-Process Trust Boundary, Closure Matrix, Prerequisites Inventory)
- `docs/parallel-delivery/delivery_engine.py` (`HostBoundaryBootstrapCapability.pin_trusted_host_public_key`, `HostBoundaryChannel`, `HostBoundaryTicket`, `HostBoundaryTicketIssuer`)
- `docs/parallel-delivery/test_negative_fixtures.py` (`test_18y_sol_finding_candidate_custom_key_authority_rejected_in_fresh_subprocess`, `_SealedFixtureModule`, `_InternalHostBoundaryVault`)

## Điểm tiếp tục

- Chạy toàn bộ gate kiểm thử và kiểm tra mã hóa/toàn vẹn dữ liệu (`validate.py`).
- Commit thay đổi code/docs theo Conventional Commits.
- Tái tạo báo cáo attestation chính xác (`python docs/parallel-delivery/validate.py --generate-report --base 4a7c8c921b7e05066505d51b168a02c3fde61317 --candidate <NEW_HEAD>`).
