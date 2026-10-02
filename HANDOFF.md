# Bàn giao phiên làm việc — Triển khai Bộ File Kỹ thuật cho Bộ Kiến trúc 2 (Wave/DAG Architecture)

## Đã quyết định

- Hoàn tất triển khai toàn bộ gói kỹ thuật DOC-00..DOC-10 cho Bộ kiến trúc 2 (Parallel Wave/DAG Architecture) theo kế hoạch đã được phê duyệt:
  1. **Chính sách & ADR (DOC-00, DOC-01):** Tạo `docs/adr/0013-wave-dag-development.md`, cập nhật `docs/adr/README.md` và `docs/parallel-delivery/operating-model.md`. Phân định rõ Wave (lộ trình, thẩm quyền) vs DAG (thực thi kỹ thuật); định nghĩa 4 trạng thái thẩm quyền (`planned`, `implementation_authorized`, `integration_authorized`, `production_activation_authorized`); chuẩn hóa điều chỉnh quy định `QR-MNT-003`.
  2. **Biên Giao tiếp & Contracts (DOC-02):** Cập nhật `docs/parallel-delivery/contract-registry.yaml`. Bổ sung Batches query contract (`CONTRACT-BATCHES-QUERY`, `CT-BAT-*`), mô hình Operation execution state (tách biên nhận `accepted` khỏi trạng thái thực thi `running`/`succeeded`/`failed`), và khóa các interface cốt lõi: A–B (DocumentPackage), B–D (Article snapshot), C–I (Metadata catalog vs Artifact byte integrity), D–E–F (Script, Voice, Word Timing, Render Package), G–C–I (Completion UoW), J–Provider.
  3. **Phân rã Capability & Spec Độc lập (DOC-03):** Tạo đầy đủ 7 đặc tả kỹ thuật độc lập trong `docs/modules/capability-*.md` (B, C, D, E, F, G, J) với đầy đủ DoR, DoD, invariants (INV-xxx), allowed/forbidden paths, targeted tests và rollback criteria.
  4. **Ownership, Resource Policy & DAG Executable (DOC-04):** Cập nhật `docs/parallel-delivery/task-dag.yaml` với đồ thị task chi tiết Wave 0 đến Wave 4; cập nhật `docs/parallel-delivery/ownership-and-locks.yaml` với phân quyền path mịn và khóa single-writer (composition root, contract source, migration sequence, dependency lockfiles); tạo mới `docs/parallel-delivery/schedule-policy.yaml` quy định hạn ngạch tài nguyên CPU, RAM, GPU, DB connections.
  5. **Acceptance Matrix & Traceability (DOC-05):** Tạo mới `docs/parallel-delivery/acceptance-matrix.yaml` ánh xạ 100% yêu cầu R01–R25 sang Capability, Task, Contract, Test, Evidence, Gate; cập nhật `docs/parallel-delivery/traceability.md`.
  6. **Đồng bộ Lộ trình & Checklist (DOC-06):** Cập nhật `docs/11-roadmap.md`, `docs/12-pre-code-checklist.md`, `README.md` ghi nhận Bộ kiến trúc 2 đã được hiện thực hóa.
  7. **Hạ tầng, Quy chế & Validator Riêng (DOC-07, DOC-08, DOC-09, DOC-10):** Tạo các tài liệu quy chế `overlay-and-evidence.md` (DOC-08), `preflight-and-acceptance.md` (DOC-09), `runtime-compatibility.md` (DOC-10); tạo script kiểm tra tĩnh độc lập `docs/parallel-delivery/validate-docs-plan.py` (DOC-07) đạt PASS 100%.
- Giữ nguyên các chốt an toàn bất biến fail-closed:
  - `M2-P8/P9`: Duy trì `LOCKED`.
  - `M3` và Phân hệ A: Duy trì `NOT AUTHORIZED`.
  - Kích hoạt sản xuất: Duy trì `PRODUCTION_ACTIVATION_BLOCKED`.

## Chưa quyết định

- Chưa cấp quyền implementation hay viết test RED cho Milestone M2-P8, M2-P9 hoặc Milestone M3 / Phân hệ A. Mọi mở rộng thẩm quyền yêu cầu checkpoint độc lập và phê duyệt từ người dùng.

## Tệp cần đọc tiếp

- `DAG-implement-plan.md` (Kế hoạch tổng thể chiến dịch Bộ 2).
- `docs/adr/0013-wave-dag-development.md` (Quyết định kiến trúc Wave/DAG và amendment QR-MNT-003).
- `docs/parallel-delivery/contract-registry.yaml` (Danh mục contracts đã khóa và Batches query).
- `docs/parallel-delivery/task-dag.yaml` (Đồ thị DAG các task và single-writer restrictions).
- `docs/parallel-delivery/schedule-policy.yaml` (Chính sách phân bổ tài nguyên phần cứng).
- `docs/parallel-delivery/acceptance-matrix.yaml` (Ma trận nghiệm thu R01–R25).
- `docs/parallel-delivery/validate-docs-plan.py` (Script kiểm tra tĩnh đạt PASS 100%).

## Điểm tiếp tục

- Chờ Sol-Lead tiến hành rà soát kỹ thuật độc lập (`ACCEPT`) và Astra-Lead kiểm toán kiến trúc tối cao (`PASS`) trên exact candidate commit của worktree `DAG-implement-plan`.
