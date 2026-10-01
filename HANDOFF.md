# Bàn giao phiên làm việc

## Đã quyết định

- Giữ nguyên ranh giới thẩm quyền: M2-P1..P7B_ACCEPTED_CLOSED; M2-P8/P9 LOCKED; M3/Phân hệ A NOT AUTHORIZED; ProductionActivationGate duy trì PRODUCTION_ACTIVATION_BLOCKED.
- Khắc phục triệt để phát hiện ROOT_ARCHITECTURE từ Sol Audit trên exact candidate 6a6972f43c4f8b87b3b3553907ba9a73c15b2a8b (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  1. Đóng gói hoàn toàn Host Daemon Runtime: Chuyển toàn bộ runtime và credentials vào closure `_init_harness_runtime()`; loại bỏ hoàn toàn `_private_host_state`, `token`, `authkey`, `port`, `proc`, `_state` và các helper khỏi module namespace và `raw ModuleType.__dict__`.
  2. Phân quyền đăng ký Candidate fail-closed: `TrustedHostRegisterDispatch` và daemon ngoài tiến trình bắt buộc `candidate_commit` phải thuộc authorized candidates do supervisor ủy quyền; từ chối candidate tùy ý (như `0123456789abcdef...`) fail-closed.
  3. Cấp phát biên nhận supervisor mờ: Trả về `disp_receipt_<hex>` thay vì capability token; daemon từ chối phát hành envelope cho dispatch chưa đăng ký.
  4. Nghiệm thu kiểm thử: Mở rộng `test_20` kiểm tra trực tiếp `raw_dict` và tái hiện counterexample an toàn; toàn bộ 404 test fixtures đạt PASS 100%.

## Chưa quyết định

- Milestone M2-P8, M2-P9 và Milestone M3/Phân hệ A tiếp tục bị khóa chặt tới khi có quyết định phê duyệt và user checkpoint riêng.

## Tệp cần đọc tiếp

- docs/parallel-delivery/README.md (Mục 38: Khắc phục triệt để phát hiện Sol Audit trên 6a6972f).
- docs/parallel-delivery/test_host_boundary_harness.py (Bảo vệ thông tin xác thực Host Daemon qua closure runtime và kiểm soát đăng ký candidate).
- docs/parallel-delivery/test_negative_fixtures.py (Test 20 kiểm chứng raw dict và counterexample).
- CHANGELOG.md (Nhật ký thay đổi chi tiết).

## Điểm tiếp tục

- Chờ đợt đánh giá độc lập tiếp theo từ reviewer Sol trên exact candidate SHA mới sau khi commit, tái tạo attestation và push.
