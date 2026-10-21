# Đặc tả Kỹ thuật Capability C: Quản lý Kho Media & Phân tích Hook (Media Catalog & Hook Provenance)

> **Mã Capability:** `CAP-C-STORAGE`
> **Chủ quản:** Module C
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-CONTENT-MEDIA`, `CONTRACT-STORAGE`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability C chịu trách nhiệm quản lý danh mục tài nguyên truyền thông (hình ảnh, video clip ngắn, audio), gắn thẻ nhận diện, phân loại hook tiềm năng (visual hook, audio hook, thumbnail candidate), theo dõi nguồn gốc bản quyền (provenance) và ghi nhận số lượt tái sử dụng media (`MediaUsage`).

### Tách biệt Ranh giới Danh mục (C) và Lưu trữ Vật lý (I):
- **Module C sở hữu Metadata Catalog:** Thông tin mô tả, kích thước, độ phân giải, tỷ lệ khung hình, điểm đánh giá chất lượng, nhãn đối tượng, phân loại hook và số lần sử dụng.
- **Module I sở hữu Byte Store:** Lưu trữ file nhị phân trên đĩa cục bộ, kiểm tra toàn vẹn mã băm SHA-256, đồng bộ hóa lên Google Drive và xử lý dọn dẹp vật lý theo lệnh ủy quyền.

### Aggregates do Module C sở hữu độc quyền (Single-Writer):
- `MediaAsset`: Bản ghi metadata của tài nguyên media kèm chỉ số băm kiểm tra.
- `MediaAnalysis`: Kết quả phân tích thị giác/thính giác (nhận diện chủ thể, độ sắc nét, vùng an toàn 9:16).
- `Hook`: Các ứng viên hook được phân loại (Visual Hook, Audio Hook, Thumbnail candidate).
- `MediaUsage`: Sổ ghi nhận lượt sử dụng media cho từng video job để tránh lặp tài nguyên.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Đăng ký Media:** Nhận thông báo phát hiện media từ Ingestion (Module B) hoặc bộ phận thu thập (Module A) qua `CONTRACT-CONTENT-MEDIA` (`CT-MED-001`).

### Outbound Ports:
- **Port Truy vấn Media và Hook cho Kịch bản:** `CT-MED-005` (truy vấn media, binding `c-d-media-candidates`) và `CT-MED-006` (truy vấn hook) của `CONTRACT-CONTENT-MEDIA`; `CT-HOOK-001` là `ImportHook`, không phải port truy vấn.
- **Port Ghi nhận Lượt dùng (MediaUsage):** `CT-MED-008` trong cùng Unit of Work PostgreSQL với completion của Module G (`CT-ORC-008`, `CT-ORC-009`); `CT-STO-002` là `RegisterArtifactLocation` của Module I, không phải đường ghi lượt dùng.

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability C phải thỏa mãn:
1. `CONTRACT-CONTENT-MEDIA` đã đóng băng phiên bản revision.
2. Interface C-I đã được phê duyệt: Quy chuẩn rõ ràng về việc C không trực tiếp thao tác ghi/xóa file byte trên filesystem của I.
3. Bộ fixtures dữ liệu ảnh/video mẫu đã sẵn sàng trong test suite.
4. Quyền sở hữu đường dẫn đã được phân định tách bạch khỏi Module I.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability C chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. Toàn bộ unit tests và contract verification tests đạt `PASS`.
2. Byte và SHA-256 thuộc artifact version của Module I (CT-STO-001); `MediaAsset` giữ canonical fingerprint bất biến; một byte có thể có nhiều provenance và một media logic có nhiều rendition (CT-MED-001..003).
3. Nguyên tắc không xóa metadata: Xóa file vật lý ở tầng I không được làm mất lịch sử metadata và provenance ở tầng C.
4. C cung cấp truy vấn và candidate độc lập (CT-MED-004, CT-MED-006); ràng buộc mỗi plan có visual hook, audio hook và thumbnail trong vùng hook thuộc Module D.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-005`, `INV-008`, `INV-010`, `INV-017`:** C phục vụ phần C của các invariant này (catalog `docs/10-test-strategy.md` §14.2) và `CT-SRC-003`; `INV-006` là timeline mode và `INV-012` là canary secret, không phải provenance hay bộ đếm lượt dùng.
- Bộ đếm lượt dùng chỉ tăng trong transaction completion (`CT-MED-008`) và không tăng lặp khi retry (`TST-WF-INV-010`, `TST-WF-INV-017`).

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/catalog/**`
  - `tests/unit/catalog/**`
  - `tests/integration/catalog/**`
  - `docs/modules/capability-c-storage.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/storage/bytes/**` (thuộc quyền Module I)
  - `src/controlplane/**`
  - `src/render/**`
  - `docs/09-contracts/**`

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Metadata Integrity:** Xác minh việc ghi dữ liệu media không gây ra side-effect xóa byte vật lý hoặc làm sai lệch provenance hash.
- **Quan sát RED:** Kiểm thử fail khi hook không có điểm đánh giá chất lượng hoặc khi cố tình tăng lượt sử dụng ngoài PostgreSQL Unit of Work.
- **Targeted Test Command:**
  ```bash
  python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Revert các bản ghi metadata lỗi trong transaction; cô lập các media asset bị lỗi phân tích để xử lý lại mà không chặn quy trình chung.

## 9. Đính chính từ nguồn chuẩn

- State machine CT-STATE-005, CT-STATE-006 và migration PostgreSQL là tài nguyên dùng chung của gói hội tụ (CONV-C-07, CONV-C-01); C không chứa `lifecycle.py` hay repository PostgreSQL riêng.
- Test ID lấy từ catalog `docs/10-test-strategy.md` (không dùng `TST-CAT-*`); bằng chứng ghi tại `docs/delivery-evidence/<task-id>/report.md`; media lịch sử theo CT-SRC-003 (errata m4-ci mục 3, 4, 5).
- CT-STATE-012 có cạnh `VERIFIED → MISSING` và không có cạnh phục hồi từ `MISSING`, `CORRUPT`, `OUTCOME_UNKNOWN` (errata m4-ci mục 6).
