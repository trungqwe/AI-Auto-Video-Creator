# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: `M2-P1..P7B_ACCEPTED_CLOSED`; M2-P8/P9 `LOCKED`; M3/Phân hệ A `NOT AUTHORIZED`.
- Đã khắc phục triệt để nguyên nhân gốc rễ (root cause) finding audit trust boundary của Sol trên candidate `8913b392522701f924117a234f4e0cee7fc83624` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) theo chỉ thị bắt buộc tại `D:/AI_SETUP/supervisor/generated/root-cause-trust-boundary-intervention.md`:
  1. Tái hiện RED evidence: constructor `ReviewerHostIssuer(_internal_token=b"caller_non_none_token")` cho phép caller tự tạo authority. Sửa đổi dùng private sentinel token `_SENTINEL_HOST_TOKEN`, đánh dấu deprecated các DTO in-process cũ và vô hiệu hóa hoàn toàn thẩm quyền in-process.
  2. Triển khai kiến trúc Ranh giới Tin cậy Ngoài tiến trình (Out-of-Process Trust Boundary) với chữ ký bất đối xứng Ed25519 (`SignedReviewEnvelope`, `SignedIntegrationEnvelope`) có domain separation và canonical serialization RFC 8785.
  3. Pinned Key Custody (`TrustedKeyStore`): Khóa riêng chỉ thuộc sở hữu của Reviewer Lead (`rev_key_lead_v1`) và Integration Gatekeeper (`integ_gatekeeper_v1`) độc lập; candidate chỉ chứa public keys ghim sẵn; hỗ trợ thu hồi khóa tức thời (`revoke_key`).
  4. Sổ đăng ký tiêu thụ bền vững (`DurableConsumptionRegistry`): Lưu trữ nguyên tử trên SQLite, bảo vệ chống replay, chống tái sử dụng nonce, monotonic fencing token tăng dần, và temporal expiry window bền vững qua restart.
  5. Khóa kích hoạt Production (`ProductionActivationGate`): Trạng thái `PRODUCTION_ACTIVATION_BLOCKED` (`NOT_PROVISIONED`), nghiêm cấm kích hoạt production hoặc merge khi chưa đủ 4 điều kiện hạ tầng (`OS_USER_ISOLATION`, `PRIVATE_KEY_ACL_RESTRICTION`, `DEDICATED_RUNNER`, `PROTECTED_BRANCH_POLICY`).
  6. Toàn bộ bộ kiểm thử đạt **386/386 tests PASS (100%)**, bổ sung 10 bài test tự động bao quát threat model, closure matrix và fresh subprocess isolation.

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chưa kích hoạt production mode (`PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên fail-closed).
- Chờ kết quả re-review của Sol trên exact candidate SHA mới.

## Tệp cần đọc tiếp

- `docs/parallel-delivery/security-performance-recovery.md` (Mục 8: Threat Model, ADR, Out-of-Process Trust Boundary, Closure Matrix, Prerequisites Inventory)
- `docs/parallel-delivery/delivery_engine.py` (Lớp Out-of-Process, Signed Envelopes, TrustedKeyStore, DurableConsumptionRegistry, ProductionActivationGate)
- `docs/parallel-delivery/test_negative_fixtures.py` (`TestSolTrustBoundaryRootCauseRemediation`)

## Điểm tiếp tục

- Commit thay đổi theo Conventional Commits.
- Sinh lại exact-head attestation report (`python docs/parallel-delivery/validate.py --generate-report ...`).
- Push lên nhánh `refs/heads/trungqwe/parallel-architecture-revolution`, xác minh remote identity và hoàn tất dispatch task.
