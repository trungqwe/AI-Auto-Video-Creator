# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: `M2-P1..P7B_ACCEPTED_CLOSED`; M2-P8/P9 `LOCKED`; M3/Phân hệ A `NOT AUTHORIZED`.
- Đã thêm [kiến trúc triển khai song song](./docs/parallel-delivery/README.md) ở trạng thái `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`. Bundle chỉ là docs/config và định nghĩa DAG, contract registry, ownership/lease, Orca worker protocol, merge queue, traceability, security/performance/recovery.
- Đã khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate `8ceacb41aeb67bbfd1f644b9e252df1db12f58e2`:
  1. Loại bỏ hoàn toàn literal credential `test_fixture_reviewer_secret_32b_hex!` và kho lưu trữ `_HOST_HANDOFF_VAULT` khỏi production module `docs/parallel-delivery/delivery_engine.py`.
  2. Chuyển toàn bộ việc tạo handoff authority và credential sang `TrustedHostReviewerHandoff` trực thuộc trusted host boundary trong `docs/parallel-delivery/test_negative_fixtures.py`, không callable hoặc importable bởi candidate.
  3. `ReviewerHostHandoff.__init__` và `__init_subclass__` trong `delivery_engine.py` từ chối fail-closed mọi nỗ lực khởi tạo hoặc kế thừa từ in-process candidate callers; `ReviewerSessionBoundary.provision_from_host()` từ chối fail-closed mọi authority khởi tạo trong module candidate hoặc `__main__`.
  4. Bộ kiểm thử tự động đạt 375/375 tests PASS (100%), bổ sung `test_sod_17` chứng minh caller thông thường trong tiến trình mới không thể tự tạo authority, không thể chiếm dụng ranh giới (`HANDOFF_PROVISIONED=False`, `KNOWN_CREDENTIAL=False`), default boundary giữ nguyên `_reviewer_secret = None`, và không thể mint proof/context.

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
