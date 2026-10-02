# Quy trình Preflight Kiểm tra Tĩnh & Đóng gói Hồ sơ Nghiệm thu (DOC-09)

> **Mã Tài liệu:** `DOC-09`
> **Chủ quản:** Control / Technical Reviewer / Supreme Auditor
> **Trạng thái:** `ACTIVE_ACCEPTED`
> **Thuộc chiến dịch:** Triển khai Kiến trúc 2 (Parallel Wave/DAG Architecture)

---

## 1. Mục tiêu và Quy trình Preflight Tĩnh

Trước khi bàn giao ứng viên (candidate commit) cho Sol-Lead rà soát kỹ thuật độc lập và Astra-Lead kiểm toán kiến trúc tối cao, hệ thống bắt buộc phải thực thi quy trình tiền kiểm tra tĩnh (Preflight Static Check) nhằm phát hiện sớm mọi lỗi sai sót về định dạng, cấu trúc dữ liệu hoặc ranh giới quyền hạn.

### Năm Bước Tiền Kiểm tra Bắt buộc:
1. **Kiểm tra Hiện diện Toàn vẹn DOC-00..DOC-10:** Xác minh sự tồn tại đầy đủ của toàn bộ 11 tài liệu và tệp quy hoạch cấu thành Bộ 2.
2. **Kiểm tra Cú pháp Dữ liệu Cấu trúc (YAML Validation):** Tải và xác thực cú pháp bằng bộ phân tích chuẩn (PyYAML SafeLoader) cho toàn bộ các tệp cấu hình:
   - `task-dag.yaml`
   - `contract-registry.yaml`
   - `ownership-and-locks.yaml`
   - `schedule-policy.yaml`
   - `acceptance-matrix.yaml`
3. **Kiểm tra Tính Không Chu trình của Đồ thị (DAG Acyclicity Check):** Duyệt toàn bộ các node và cạnh phụ thuộc (`depends_on`) bằng thuật toán Topological Sort / DFS để chứng minh đồ thị hoàn toàn phi chu trình (no cycles).
4. **Kiểm tra Chuẩn Định dạng Byte & Whitespace:**
   - Bắt buộc dùng mã hóa UTF-8 chuẩn không có BOM.
   - Bắt buộc dùng ký tự xuống dòng kiểu UNIX LF (`\n`), cấm tuyệt đối CRLF (`\r\n`).
   - Không có khoảng trắng thừa ở cuối dòng (trailing whitespace). Lệnh `git diff --check` phải trả về Exit Code 0.
5. **Kiểm tra Ranh giới Quyền hạn & Chốt An toàn:**
   - Đảm bảo `M2-P8/P9` duy trì `LOCKED`.
   - Đảm bảo `M3` và Phân hệ A duy trì `NOT AUTHORIZED`.
   - Đảm bảo `PRODUCTION_ACTIVATION_BLOCKED` duy trì trạng thái khóa fail-closed.

---

## 2. Hồ sơ Provenance và Đóng gói Nghiệm thu

Mỗi lượt nghiệm thu của chiến dịch phải tạo một hồ sơ kiểm chứng chứa đựng thông tin rõ ràng:
- **Base Commit SHA:** Mã băm của commit nền tảng đã được phê duyệt (`17dfe2b61e282a2e22e9eeefa7448ae49a1d0622`).
- **Candidate Commit SHA:** Mã băm của commit ứng viên tại HEAD nhánh `DAG-implement-plan`.
- **Change Profile:** Danh mục chính xác các tệp đã tạo mới và chỉnh sửa.
- **Validator Version:** Kết quả kiểm tra từ `validate-docs-plan.py`.
- **Attestation Verdict:** Kết luận đánh giá từ Reviewer Lead (`ACCEPT`) và Supreme Auditor (`PASS`).

---

## 3. Tiêu chí Dừng Khẩn cấp (STOP Conditions)

Nếu preflight phát hiện bất kỳ điều kiện nào sau đây, tiến trình lập tức dừng lại ở trạng thái `BLOCKED` fail-closed:
- Phát hiện chu trình phụ thuộc trong `task-dag.yaml`.
- Phát hiện lỗi cú pháp YAML hoặc thiếu trường bắt buộc theo schema.
- Phát hiện lỗi mã hóa ký tự (mojibake) hoặc tồn tại BOM trên tệp văn bản.
- Phát hiện lỗi trailing whitespace trên tệp tài liệu mới.
- Phát hiện chỉnh sửa trái phép vào mã nguồn `src/**` hoặc bằng chứng lịch sử.
