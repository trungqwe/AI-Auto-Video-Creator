# Bàn giao phiên làm việc — Khắc phục Finding Sol-Lead về Contract Registry (Wave/DAG)

## Đã quyết định

- Khắc phục triệt để finding của Sol-Lead về sự không tương thích prefix CT-BAT-* trong docs/parallel-delivery/contract-registry.yaml:
  1. **Khôi phục phạm vi prefix hợp đồng nguồn:** Trả CONTRACT-CONTROL-API-STREAM.id_prefixes về đúng [CT-API-*] như approved base, khớp 100% ID nguồn trong docs/09-contracts/01-control-api-and-stream.md. Tuyệt đối không sửa tệp nguồn để bảo toàn khóa bất biến LOCK-CONTRACT-SOURCE.
  2. **Chuẩn hóa provenance cho Batches Query Contract:** Cập nhật defining_source của batches_query_contract (CONTRACT-BATCHES-QUERY) trỏ về docs/parallel-delivery/contract-registry.yaml kèm parent_contract_ref: CONTRACT-CONTROL-API-STREAM, định vị chính xác nguồn định nghĩa các endpoint CT-BAT-001..004 thuộc DOC-02.
  3. **Đồng bộ hóa Inbound Port Module G:** Cập nhật docs/modules/capability-g-orchestration.md phân định rõ cổng nhận lệnh từ CONTRACT-CONTROL-API-STREAM (CT-API-001) và CONTRACT-BATCHES-QUERY (CT-BAT-001).
- Bằng chứng kiểm thử mục tiêu (Targeted Verification):
  - Lệnh kiểm tra registry check_registries chuyển từ RED (CONTRACT-CONTROL-API-STREAM: prefix CT-BAT-* matches no source contract) sang GREEN (REGISTRIES_OK, 0 lỗi).
  - Bộ kiểm tra tĩnh docs/parallel-delivery/validate-docs-plan.py đạt PASS 100% (4/4 nhóm kiểm tra).
  - git diff --check đạt sạch hoàn toàn, không có lỗi định dạng hay trailing whitespace.
- Duy trì các chốt an toàn bất biến fail-closed:
  - M2-P8/P9: Duy trì LOCKED.
  - M3 và Phân hệ A: Duy trì NOT AUTHORIZED.
  - Kích hoạt sản xuất: Duy trì PRODUCTION_ACTIVATION_BLOCKED.

## Chưa quyết định

- Chưa cấp quyền implementation hay viết test RED cho Milestone M2-P8, M2-P9 hoặc Milestone M3 / Phân hệ A. Mọi mở rộng thẩm quyền yêu cầu checkpoint độc lập và phê duyệt từ người dùng.

## Tệp cần đọc tiếp

- DAG-implement-plan.md (Kế hoạch tổng thể chiến dịch Bộ 2).
- docs/parallel-delivery/contract-registry.yaml (Danh mục contracts đã khóa và Batches query).
- docs/parallel-delivery/validate-docs-plan.py (Script kiểm tra tĩnh đạt PASS 100%).
- docs/modules/capability-g-orchestration.md (Đặc tả cổng giao tiếp Module G).

## Điểm tiếp tục

- Sol-Lead tiến hành rà soát kỹ thuật độc lập (ACCEPT) và Astra-Lead kiểm toán kiến trúc tối cao (PASS) trên candidate commit mới của worktree DAG-implement-plan.
