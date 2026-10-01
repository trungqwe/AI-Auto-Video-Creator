# Bàn giao phiên làm việc

## Đã quyết định

- Giữ nguyên ranh giới thẩm quyền: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED; ProductionActivationGate duy trì PRODUCTION_ACTIVATION_BLOCKED.
- Khắc phục triệt để phát hiện ROOT_ARCHITECTURE từ Sol Audit trên exact candidate f4ad8d5516ec9935de718f4cc6b4621f162140a5 (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Thiết lập SupervisorDispatchCapability: Bổ sung capability bất biến, unforgeable có chữ ký số Ed25519 do host daemon cấp phát độc quyền cho supervisor; nghiêm cấm candidate caller tự tạo hoặc giả mạo fail-closed.
  2. Phân quyền đăng ký dispatch ngoài tiến trình: REGISTER_DISPATCH daemon IPC và TrustedHostRegisterDispatch bắt buộc phải có SupervisorDispatchCapability hợp lệ; xác minh chữ ký, binding tham số, freshness và single-use consumption.
  3. Chặn triệt để candidate caller đăng ký exact HEAD: Caller không thể tự ý đăng ký dispatch hay tự tạo provenance để xin cấp phong bì duyệt ACCEPT từ ExternalReviewProducer.
  4. Nghiệm thu kiểm thử: Toàn bộ 404 test fixtures đạt PASS 100%; cổng kích hoạt sản xuất duy trì PRODUCTION_ACTIVATION_BLOCKED.

## Chưa quyết định

- Milestone M2-P8, M2-P9 và Milestone M3/Phân hệ A tiếp tục bị khóa chặt tới khi có quyết định phê duyệt và user checkpoint riêng.

## Tệp cần đọc tiếp

- docs/parallel-delivery/README.md (Mục 40: Khắc phục triệt để phát hiện Sol Audit trên f4ad8d5).
- docs/parallel-delivery/delivery_engine.py (SupervisorDispatchCapability và cơ chế xác minh chữ ký host).
- docs/parallel-delivery/test_host_boundary_harness.py (Bảo vệ REGISTER_DISPATCH IPC và phát hành SupervisorDispatchCapability).
- docs/parallel-delivery/test_negative_fixtures.py (Test 20 kiểm chứng ma trận âm cho SupervisorDispatchCapability và counterexample từ chối đăng ký candidate caller).
- CHANGELOG.md (Nhật ký thay đổi chi tiết).

## Điểm tiếp tục

- Chờ đợt đánh giá độc lập tiếp theo từ reviewer Sol trên exact candidate SHA mới sau khi commit, tái tạo attestation và push.
