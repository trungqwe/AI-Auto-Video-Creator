# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: `M2-P1..P7B_ACCEPTED_CLOSED`; M2-P8/P9 `LOCKED`; M3/Phân hệ A `NOT AUTHORIZED`.
- Đã thêm [kiến trúc triển khai song song](./docs/parallel-delivery/README.md) ở trạng thái `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`. Bundle chỉ là docs/config và định nghĩa DAG, contract registry, ownership/lease, Orca worker protocol, merge queue, traceability, security/performance/recovery.
- Đã khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate `6731c156e09b06f991a1ed523f318c0c24c0005b`:
  1. Loại bỏ hoàn toàn cơ chế kiểm tra tin cậy dựa trên tên module `cls.__module__ in ("delivery_engine", "__main__")`.
  2. `ReviewerHostHandoff.__init_subclass__` từ chối fail-closed vô điều kiện mọi nỗ lực subclass hóa trên toàn bộ các module (kể cả module ngoài như `attacker_module`).
  3. `ReviewerHostIssuer` và `ReviewerHostIssuerCapability` ràng buộc xuất xứ tin cậy của host handoff bằng chữ ký HMAC không thể làm giả; caller cùng tiến trình không thể tự khởi tạo host issuer hay giả mạo capability.
  4. `ReviewerSessionBoundary.provision_from_host()` bắt buộc `type(authority) is ReviewerHostHandoff`, thẩm định chữ ký và tiêu thụ nguyên tử `ReviewerHostIssuerCapability` từ `ReviewerHostIssuer` trước khi tiếp nhận credential.
  5. Bộ kiểm thử tự động đạt 376/376 tests PASS (100%), bổ sung `test_sod_18` chứng minh subclass ở module ngoài, unauthenticated object, raw instance thiếu capability và capability giả mạo chữ ký đều bị từ chối fail-closed, boundary giữ nguyên unprovisioned và cấm mint proof; đồng thời positive control với authentic host handoff hoàn tất provisioning an toàn.

## Chưa quyết định

- Chưa mở implementation authority cho Milestone M2-P8/P9 hoặc Milestone M3.
- Chờ kết quả re-review của Sol trên candidate mới.

## Tệp cần đọc tiếp

- `docs/parallel-delivery/delivery_engine.py`
- `docs/parallel-delivery/test_negative_fixtures.py`
- `docs/parallel-delivery/validate.py`

## Điểm tiếp tục

- Chạy toàn bộ validation và gate kiểm toán (`python docs/parallel-delivery/validate.py --audit`).
- Commit thay đổi theo Conventional Commits.
- Tái tạo báo cáo attestation exact-head (`python docs/parallel-delivery/validate.py --generate-report ...`).
- Push lên nhánh `refs/heads/trungqwe/parallel-architecture-revolution`, xác minh remote identity và hoàn tất dispatch task.
