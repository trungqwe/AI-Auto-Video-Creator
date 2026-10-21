# Đặc tả Kỹ thuật Capability B: Phân tích & Quản lý Bài viết (Ingestion & Content Normalization)

> **Mã Capability:** `CAP-B-INGESTION`
> **Chủ quản:** Module B
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-SOURCE-CONTENT`, `CONTRACT-DOMAIN-EVENTS`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability B chịu trách nhiệm tiếp nhận các gói tài liệu đã thu thập (`CollectedDocumentPackage`, CT-SRC-006) từ Capability A, thực hiện bóc tách, chuẩn hóa nội dung, phát hiện trùng lặp (deduplication), quản lý các phiên bản bài viết (`ArticleRevision`), theo dõi diễn biến sự kiện (`Event`, `EventUpdate`) và cung cấp bộ nguồn đã ghim revision, làm input_provider cho `ProductionSnapshot` (CT-AI-001) do Capability D sinh.

### Aggregates do Module B sở hữu độc quyền (Single-Writer):
- `Article`: Thực thể bài viết chuẩn hóa, định danh duy nhất theo URL gốc và khóa chống trùng.
- `ArticleRevision`: Lịch sử các phiên bản nội dung khi bài viết có cập nhật từ nguồn.
- `Event`: Nhóm các bài viết thuộc cùng một sự kiện thời sự/tin tức.
- `EventUpdate`: Các diễn biến, tình tiết mới phát sinh của sự kiện theo thời gian.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Tiếp nhận CollectedDocumentPackage:** Nhận gói thu thập từ Module A qua `CONTRACT-SOURCE-CONTENT` (`CT-SRC-006`) và trả `CollectedDocumentResolution` (`CT-CNT-001`) theo binding `a-b-collected-document`. Module B là consumer, idempotency theo `collected_document_id` + `dedup_policy_revision`.

### Outbound Ports:
- **Port Cung cấp đầu vào cho ProductionSnapshot:** B không phát hành `ArticleSnapshot`; `ProductionSnapshot` (`CT-AI-001`) do Module D sinh, B là input_provider qua `ArticleRevisionAccepted` (`CT-CNT-003`) theo binding `b-d-production-snapshot`; `CT-CNT-002` chỉ là quy tắc bài đại diện.
- **Port Phát sự kiện miền:** Phát `ArticleRevisionAccepted`, `DuplicateDocumentResolved`, `EventLinkResolved`, `EventUpdateAccepted` tới transactional outbox theo envelope `CT-EVT-002`, `CT-EVT-003` (`CONTRACT-DOMAIN-EVENTS`); `CT-EVT-001` là ngữ nghĩa chuyển phát.

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability B phải thỏa mãn:
1. `CONTRACT-SOURCE-CONTENT` và `CONTRACT-DOMAIN-EVENTS` đã được đóng băng phiên bản (`frozen revision`).
2. Bộ fixture `tests/fixtures/contracts/a-b-collected-document/payloads.json` cho `CollectedDocumentPackage` (hợp lệ, trùng lặp, thiếu trường, định dạng lỗi) đã được review độc lập.
3. Schema PostgreSQL của B do migration của gói hội tụ cấp (REQ-B-CONV-01); slice B dùng adapter in-memory, không dùng namespace `db:ingestion`.
4. Đã phân định rõ ranh giới đường dẫn sở hữu (`owned_paths`), không giao cắt với Module A hoặc Module D.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability B chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. 100% các unit test và contract verification tests đạt `PASS`.
2. Kiểm chứng tính tất định (determinism): Cùng một `CollectedDocumentPackage` đầu vào sinh ra cùng một `Article` và fingerprint không đổi.
3. Chống trùng lặp tuyệt đối: Phát hiện chính xác bài đăng lại (repost), không tạo tin mới trùng lặp khi không có tình tiết diễn biến mới.
4. Transactional Outbox: Mọi cập nhật trạng thái bài viết được lưu trữ nguyên tử cùng domain event trong PostgreSQL transaction.
5. Không có lỗi rò rỉ bộ nhớ hoặc tài nguyên; tuân thủ hạn ngạch kết nối cơ sở dữ liệu.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-005`** (`TST-INT-INV-005`): bài đăng lại không tạo article hoặc script mới, vẫn giữ media mới; **`INV-004`** (`TST-INT-INV-004`): job đã snapshot giữ refs; **`INV-006`** (`TST-CTR-INV-006`): nội dung «từ lúc đó đến nay» chỉ khi có `EventUpdateAccepted`.
- Tính nguyên tử của outbox theo `CT-EVT-001`; `INV-010` là ledger completion (`TST-WF-INV-010`) và `INV-011` là cleanup authorization (`TST-DR-INV-011`), không thuộc B.
- Ngưỡng trùng fingerprint nằm trong dedup policy revision (D8-B-01), không có hằng số trong đặc tả.

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/ingestion/**`
  - `tests/unit/ingestion/**`
  - `tests/integration/ingestion/**`
  - `docs/modules/capability-b-ingestion.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/controlplane/**`
  - `src/storage/**`
  - `src/creative/**`
  - `docs/09-contracts/**`
  - `src/**/migrations/**` (chỉ migration owner được sửa)

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Contract:** Sử dụng schema validator để kiểm tra tính tương thích của `CollectedDocumentPackage` nhận được và `CollectedDocumentResolution` sinh ra.
- **Quan sát RED:** Kiểm thử thất bại rõ ràng khi đưa vào bài viết trùng lặp mà hệ thống vẫn tạo ID mới, hoặc khi thiếu `collected_document_id`.
- **Targeted Test Command:**
  ```bash
  python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Mỗi collected document một transaction riêng (CT-STATE-003, D8-B-11); lỗi một tài liệu chỉ rollback tài liệu đó, dữ liệu đã ghi hợp lệ được giữ nguyên.
- **Khôi phục trạng thái:** Hạ phiên bản mã nguồn; schema khôi phục qua migration và rollback của gói hội tụ (REQ-B-CONV-01), không dùng snapshot database namespace.
