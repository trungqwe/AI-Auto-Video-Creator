# Tái kiểm 98bd27e và ebf3d58 theo D1 (CP0-GOVERNANCE)

## Ràng buộc hash

- Lệnh thực thi: `git diff 0a3f707 ebf3d58 -- docs/parallel-delivery/ownership-and-locks.yaml`
- Base commit: `0a3f707` (`0a3f707ffa08b3a5737be6fa30769933d2cf475d`)
- Các commit kiểm tra: `98bd27e` (`98bd27e8137ebd6c63b1a2981c4d7ff93ea646b5`) và `ebf3d58` (`ebf3d583adc63e7068f08e2fd101df85d1bc6389`)
- Số byte của đầu ra diff: 1771 byte
- SHA-256 của đúng đầu ra diff: `6bf6dbe28ab8727bc4945ee3708f606bbc6c857a78eb43af04c1617f7f26af8f`

## Mục được thêm hoặc đổi

| # | Commit | Mục (id hoặc khoá YAML) | Thay đổi | Phán quyết | Lý do |
|---|---|---|---|---|---|
| 1 | 98bd27e | `PATH-SRC-SOURCE-INGESTION` | Thêm path ownership cho Module A: `src/source_ingestion/**`, `tests/unit/collection/**`, `tests/integration/collection/**` | GIỮ | Khớp bố cục D1: Module A phát triển tại `src/source_ingestion` cùng các thư mục test tương ứng. |
| 2 | 98bd27e | `PATH-SRC-STORAGE` | Thêm path ownership cho Module I: `src/storage/**`, `tests/unit/storage/**`, `tests/integration/storage/**` | SỬA Ở CP0 | Pattern `src/storage/**` là cây trùng không tồn tại theo D1 (Module I mở rộng `src/controlplane`). Tại CP0 đã sửa thành các gói thực tế: `src/controlplane/domain/storage_meta/**`, `src/controlplane/application/storage_meta/**`, `src/controlplane/infrastructure/db/storage_meta/**`, `src/controlplane/infrastructure/storage/**` cùng `tests/unit/storage/**`, `tests/integration/storage/**`. |
| 3 | 98bd27e | `LOCK-SRC-SOURCE-INGESTION` | Thêm lock tài nguyên cho Module A (`scope: capability_a_source_collection_code`) | GIỮ | Khớp D1: Resource lock cho mã nguồn Module A. |
| 4 | 98bd27e | `LOCK-SRC-STORAGE` | Thêm lock tài nguyên cho Module I (`scope: capability_i_storage_code`) | GIỮ | Khớp D1: Resource lock cho mã nguồn Module I (Storage). |
| 5 | 98bd27e, ebf3d58 | `docs/modules/a-source-collection/**` | Thêm trong 98bd27e rồi bị xoá trong ebf3d58 | BỎ | Thư mục tài liệu `docs/modules/a-source-collection/**` không tồn tại trên đĩa; commit ebf3d58 đã loại bỏ chính xác. |
| 6 | 98bd27e, ebf3d58 | `modules.A.aggregates` (`SourceTombstone`) | Thêm trong 98bd27e rồi revert trong ebf3d58 | BỎ | Aggregate `SourceTombstone` chưa có contract tương ứng và đã được hoàn nguyên về danh sách 5 aggregate chuẩn tại commit ebf3d58. |

## Sửa thêm ở CP0 ngoài hai commit

1. `PATH-SRC-ORCHESTRATION`: Thay đổi các pattern từ đường dẫn không tồn tại `src/controlplane/orchestration/**` sang đúng 5 gói con trong `src/controlplane` theo D1:
   - `src/controlplane/domain/orchestration/**`
   - `src/controlplane/application/orchestration/**`
   - `src/controlplane/infrastructure/db/orchestration/**`
   - `tests/unit/orchestration/**`
   - `tests/integration/orchestration/**`
2. Bổ sung các path và lock mới trong `ownership-and-locks.yaml`:
   - `PATH-DELIVERY-EVIDENCE` (`docs/delivery-evidence/**`, lock `LOCK-DELIVERY-EVIDENCE`)
   - `PATH-IMPLEMENTATION-PLANS` (`docs/implementation/**`, lock `LOCK-IMPL-PLAN-CONVERGENCE`)
   - 16 lock mới: `LOCK-DELIVERY-EVIDENCE`, `LOCK-IMPL-PLAN-A`..`J`, `LOCK-IMPL-PLAN-CONVERGENCE`, `LOCK-CONVERGENCE`, `LOCK-M2-REGRESSION`, `LOCK-UI-SHELL`, `LOCK-CONTROL-API`.
3. Cập nhật `as_of: "2026-10-18"`.

## Kết luận

Gói `M3-OWNERSHIP-LOCKS` đã void và được gộp hoàn toàn vào `CP0-GOVERNANCE`. Mọi mục đăng ký ownership và locks hiện hành đều tuân thủ nghiêm ngặt nguyên tắc bố cục D1 và vị trí bằng chứng D4.
