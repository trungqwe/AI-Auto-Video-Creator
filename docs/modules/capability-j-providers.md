# Đặc tả Kỹ thuật Capability J: Quản trị Cấu hình, Bảo mật & Định tuyến AI (Configuration, Security & AI Routing)

> **Mã Capability:** `CAP-J-PROVIDERS`
> **Chủ quản:** Module J
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-CONFIG-SECURITY`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability J là chốt chặn bảo mật và điều phối dịch vụ bên thứ ba của hệ thống, chịu trách nhiệm quản lý cấu hình tập trung (`ConfigRevision`), quản lý các mẫu prompt (`PromptRevision`), cách ly an toàn thông tin nhạy cảm và secret ở cấp hệ điều hành (Windows DPAPI / Subprocess Broker Vault), định tuyến thông minh giữa các nhà cung cấp mô hình AI (`CT-AI-ROUTE-*`), kiểm soát hạn ngạch chi phí và năng lực gọi API (`ProviderCapacity`).

### Aggregates do Module J sở hữu độc quyền (Single-Writer):
- `ConfigRevision`: Bản ghi cấu hình hệ thống theo phiên bản có lưu vết lịch sử.
- `PromptRevision`: Các phiên bản mẫu prompt dùng cho kịch bản, tóm tắt và phân tích hook.
- `ExternalAccount`: Metadata tài khoản dịch vụ ngoài (Google Drive, AI providers, TTS services); khóa truy cập được bảo vệ an toàn trong OS Vault.
- `ProviderCapacity`: Hạn ngạch gọi API, giới hạn tốc độ (rate limits) và bộ đếm chi phí phát sinh thời gian thực.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Cập nhật Cấu hình:** Nhận yêu cầu thay đổi cấu hình hoặc prompt từ Admin UI (Module H) qua `CONTRACT-CONFIG-SECURITY` (`CT-CFG-001`, `CT-SEC-001`).

### Outbound Ports:
- **Port Cung cấp AI Adapter Typed:** Cung cấp giao diện gọi mô hình AI cho Module D, Module E, Module B qua `CONTRACT-CONFIG-SECURITY` (`CT-AI-ROUTE-001`).
- **Port Kiểm soát Hạn ngạch & Chi phí:** Cung cấp thông tin quota và chặn gọi dịch vụ khi vượt ngân sách quy định qua `CONTRACT-CONFIG-SECURITY` (`CT-COST-001`, `CT-CAP-001`).

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability J phải thỏa mãn:
1. `CONTRACT-CONFIG-SECURITY` đã được đóng băng phiên bản (`frozen revision`). Ràng buộc tuyệt đối: `CT-AI-ROUTE-*` thuộc quyền sở hữu của Module J, không thuộc Module D.
2. Cơ chế cách ly Subprocess Broker Vault đã được cấu hình và kiểm chứng an toàn trên nền tảng Windows DPAPI.
3. Stub/Mock định tuyến AI không dùng mạng thật đã sẵn sàng trong test suite.
4. Ranh giới đường dẫn sở hữu được khóa, không cho phép module khác đọc trực tiếp file cấu hình nhạy cảm.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability J chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. 100% unit tests và mock adapter routing tests đạt `PASS`.
2. Kiểm chứng cách ly bí mật (Zero Secret Leakage): Không có bất kỳ API key, token hoặc private key nào bị rò rỉ vào log, exceptions, code repository hoặc database bảng thường.
3. Tính bất biến của phiên bản cấu hình và prompt: Thay đổi cấu hình cho lô sản xuất mới không làm thay đổi lịch sử và thông số cấu hình đã sử dụng cho các video cũ.
4. Cơ chế Fallback có kiểm soát: Khi một provider gặp sự cố (rate limit hoặc timeout), hệ thống tự động chuyển sang mô hình fallback đã được phê duyệt mà không làm gián đoạn hàng chờ công việc.
5. Kiểm soát chi phí (Cost Guardrails): Tự động chặn các yêu cầu vượt ngưỡng ngân sách được ấn định trong Project Charter.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-012`** (`TST-SEC-INV-012`): canary secret không xuất hiện trong log, event, history hay lỗi; **`INV-004`** (`TST-INT-INV-004`): đổi cấu hình sau snapshot không đổi job đã snapshot; **`INV-020`** (`TST-SEC-INV-020`): ref hoặc chỉ thị giả từ nội dung không có hiệu lực.
- Định tuyến và fallback bám `CT-AI-ROUTE-001`, `CT-AI-ROUTE-002` và mục 11 của `docs/09-contracts/11-configuration-security-contracts.md`; adapter AI qua Module J không có mã INV riêng.
- `INV-013` là StoryAngle (`TST-AI-INV-013`), `INV-015` là tombstone nguồn (`TST-INT-INV-015`) và `INV-021` không tồn tại, các nhãn đó không thuộc J; docstring cũ trong `src/controlplane/config/*.py` và `src/controlplane/security/*.py` còn nhãn sai, không sửa trong slice này (YC-HT-J-10).

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/controlplane/config/**`
  - `src/controlplane/security/**`
  - `tests/unit/security/**`
  - `docs/modules/capability-j-providers.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/creative/**`
  - `src/render/**`
  - `src/ingestion/**`
  - `docs/09-contracts/**`

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Bảo mật & Định tuyến:** Kiểm tra việc mã hóa/giải mã qua DPAPI, kiểm tra router tự động chuyển sang model fallback khi gặp lỗi HTTP 429 giả lập, và kiểm tra cơ chế chặn secret leakage.
- **Quan sát RED:** Kiểm thử fail rõ ràng khi cố tình truy cập secret handle không hợp lệ hoặc khi xuất hiện API key dạng văn bản rõ trong đối tượng trả về.
- **Targeted Test Command:**
  ```bash
  python -m unittest tests/unit/security/test_provider_routing.py -k test_fallback_and_secret_isolation
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Nếu phiên bản cấu hình hoặc prompt mới gây lỗi suy luận, khôi phục ngay lập tức phiên bản `ConfigRevision` đã được kiểm chứng trước đó (`ActiveAccepted`); các tác vụ đang chạy trên revision cũ tiếp tục hoạt động mà không bị ảnh hưởng.
