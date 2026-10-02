# Đặc tả Kỹ thuật Capability B: Phân tích & Quản lý Bài viết (Ingestion & Content Normalization)

> **Mã Capability:** `CAP-B-INGESTION`
> **Chủ quản:** Module B
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-SOURCE-CONTENT`, `CONTRACT-DOMAIN-EVENTS`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability B chịu trách nhiệm tiếp nhận các gói tài liệu thô (`DocumentPackage`) từ Capability A, thực hiện bóc tách, chuẩn hóa nội dung, phát hiện trùng lặp (deduplication), quản lý các phiên bản bài viết (`ArticleRevision`), theo dõi diễn biến sự kiện (`Event`, `EventUpdate`) và xuất bản bản chụp bài viết (`ArticleSnapshot`) phục vụ cho khâu tạo kịch bản (Capability D).

### Aggregates do Module B sở hữu độc quyền (Single-Writer):
- `Article`: Thực thể bài viết chuẩn hóa, định danh duy nhất theo URL gốc và khóa chống trùng.
- `ArticleRevision`: Lịch sử các phiên bản nội dung khi bài viết có cập nhật từ nguồn.
- `Event`: Nhóm các bài viết thuộc cùng một sự kiện thời sự/tin tức.
- `EventUpdate`: Các diễn biến, tình tiết mới phát sinh của sự kiện theo thời gian.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Tiếp nhận DocumentPackage:** Nhận dữ liệu thu thập thô từ Module A qua `CONTRACT-SOURCE-CONTENT` (`CT-SRC-001`, `CT-CNT-001`). Module B là consumer, thực thi idempotency dựa trên `provenance_hash`.

### Outbound Ports:
- **Port Cung cấp ArticleSnapshot:** Cung cấp bản chụp bài viết sạch (clean markdown, tóm tắt, entities, fingerprint nội dung) cho Module D qua `CONTRACT-SOURCE-CONTENT` (`CT-CNT-002`).
- **Port Phát sự kiện miền:** Phát `ArticleIngested`, `ArticleUpdated`, `EventDiscovered` tới hàng đợi transactional outbox qua `CONTRACT-DOMAIN-EVENTS` (`CT-EVT-001`).

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability B phải thỏa mãn:
1. `CONTRACT-SOURCE-CONTENT` và `CONTRACT-DOMAIN-EVENTS` đã được đóng băng phiên bản (`frozen revision`).
2. Bộ fixture mẫu cho `DocumentPackage` (hợp lệ, trùng lặp, thiếu trường, định dạng lỗi) đã được review độc lập.
3. Namespace cơ sở dữ liệu `db:ingestion` và bảng schema cục bộ đã được khai báo cô lập trong test harness.
4. Đã phân định rõ ranh giới đường dẫn sở hữu (`owned_paths`), không giao cắt với Module A hoặc Module D.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability B chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. 100% các unit test và contract verification tests đạt `PASS`.
2. Kiểm chứng tính tất định (determinism): Cùng một `DocumentPackage` đầu vào sinh ra cùng một `Article` và fingerprint không đổi.
3. Chống trùng lặp tuyệt đối: Phát hiện chính xác bài đăng lại (repost), không tạo tin mới trùng lặp khi không có tình tiết diễn biến mới.
4. Transactional Outbox: Mọi cập nhật trạng thái bài viết được lưu trữ nguyên tử cùng domain event trong PostgreSQL transaction.
5. Không có lỗi rò rỉ bộ nhớ hoặc tài nguyên; tuân thủ hạn ngạch kết nối cơ sở dữ liệu.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-005` (Content Snapshot & Invariant Evolution):** Bản chụp nội dung bài viết một khi đã chốt phục vụ sản xuất kịch bản là bất biến; các bản cập nhật sau chỉ được ghi dưới dạng `EventUpdate`.
- **`INV-010` (Transaction Atomicity & Outbox):** Cập nhật dữ liệu bài viết và lưu event outbox phải diễn ra trong cùng một transaction.
- **`INV-011` (Deduplication Integrity):** Bài viết trùng lặp URL hoặc trùng fingerprint nội dung >95% phải được liên kết vào bài viết gốc, không sinh entity mới.

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/ingestion/**`
  - `tests/unit/ingestion/**`
  - `docs/modules/capability-b-ingestion.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/controlplane/**`
  - `src/storage/**`
  - `src/creative/**`
  - `docs/09-contracts/**`
  - `src/**/migrations/**` (chỉ migration owner được sửa)

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Contract:** Sử dụng schema validator để kiểm tra tính tương thích của `DocumentPackage` nhận được và `ArticleSnapshot` sinh ra.
- **Quan sát RED:** Kiểm thử thất bại rõ ràng khi đưa vào bài viết trùng lặp mà hệ thống vẫn tạo ID mới, hoặc khi thiếu trường `provenance_hash`.
- **Targeted Test Command:**
  ```bash
  python -m unittest tests/unit/ingestion/test_article_normalization.py -k test_deduplication
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Nếu phát hiện sai lệch schema hoặc lỗi giải mã trong quá trình xử lý lô, toàn bộ lô công việc bị rollback fail-closed; dữ liệu bài viết đã ghi nhận hợp lệ trước đó được giữ nguyên.
- **Khôi phục trạng thái:** Hạ phiên bản mã nguồn, khôi phục snapshot database trước lô xử lý thông qua cơ chế snapshot PostgreSQL disposable namespace.
