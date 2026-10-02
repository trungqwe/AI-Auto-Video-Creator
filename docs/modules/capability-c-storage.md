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
- **Port Truy vấn Hook cho Kịch bản:** Cung cấp danh sách hook phù hợp cho Module D qua `CONTRACT-CONTENT-MEDIA` (`CT-HOOK-001`).
- **Port Khóa & Ghi nhận Lượt dùng (Media Usage):** Tham gia vào Unit of Work hoàn tất của Orchestration (Module G) để tăng số đếm sử dụng nguyên tử qua `CONTRACT-STORAGE` (`CT-STO-002`).

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
2. Kiểm tra tính bất biến của Media Hash: Mỗi `MediaAsset` có một mã băm SHA-256 duy nhất, không thể sửa đổi sau khi đã lưu.
3. Nguyên tắc không xóa metadata: Xóa file vật lý ở tầng I không được làm mất lịch sử metadata và provenance ở tầng C.
4. Đảm bảo phân loại hook chính xác: 100% video phải có visual hook, audio hook và thumbnail ứng viên theo yêu cầu nghiệp vụ.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-006` (Media Provenance & Immutability):** Nguồn gốc xuất xứ và giấy phép sử dụng của media phải được lưu vết vĩnh viễn trong metadata.
- **`INV-012` (Atomic Usage Counter):** Số lượt sử dụng media chỉ được tăng trong transaction hoàn tất video, không bị tăng trùng khi chạy lại (retry).

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/catalog/**`
  - `tests/unit/catalog/**`
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
  python -m unittest tests/unit/catalog/test_media_catalog.py -k test_hook_classification
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Revert các bản ghi metadata lỗi trong transaction; cô lập các media asset bị lỗi phân tích để xử lý lại mà không chặn quy trình chung.
