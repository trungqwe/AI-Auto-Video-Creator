# Tương thích Hạ tầng Điều phối Runtime & Tuyến Mô hình Đa Tác nhân (DOC-10)

> **Mã Tài liệu:** `DOC-10`
> **Chủ quản:** Control / Supervisor Infrastructure Lead
> **Trạng thái:** `ACTIVE_ACCEPTED`
> **Thuộc chiến dịch:** Triển khai Kiến trúc 2 (Parallel Wave/DAG Architecture)

---

## 1. Đối chiếu Tuyến Mô hình Điều phối (Model Routing Alignment)

Trong quá trình tiến hóa của nền tảng Orca và hạ tầng điều phối đa tác nhân, hệ thống ghi nhận sự chuyển dịch về tuyến mô hình kiểm định kỹ thuật:

| Vai trò | Harness | Tuyến Model Tài liệu M2 cũ | Tuyến Model Runtime Hiện hành | Ghi chú tương thích |
|---|---|---|---|---|
| **Worker (Implementer)** | Codex CLI | `ag/gemini-3.8-flash-high` | `ag/gemini-3.8-flash-high` | Giữ nguyên effort `high`; model chính thức duy nhất sở hữu quyền mutation |
| **Sol-Lead (Technical Reviewer)** | Claude Code | `cx/gpt-5.6-sol` | `cx/gpt-6.1-sol` | `AI_SETUP` hiện hành vận hành với GPT-6.1 Sol; hoàn toàn Read-Only |
| **Astra-Lead (Supreme Auditor)** | Claude Code | `cx/gpt-6-astra-medium` | `cx/gpt-6-astra` | Trọng tài kiến trúc tối cao; hoàn toàn Read-Only; effort `medium` |

### Nguyên tắc Xử lý Tương thích:
- Bộ kiểm tra tĩnh mới (`validate-docs-plan.py`) chấp nhận cấu hình runtime thực tế hiện hành (`cx/gpt-6.1-sol` và `cx/gpt-6-astra`) trong khi bảo toàn các bài kiểm tra lịch sử của M2 mà không làm phát sinh mâu thuẫn.
- Ranh giới kỷ luật bất biến: Worker là thực thể duy nhất sở hữu quyền sửa đổi file (`single-writer`); Reviewer và Auditor tuyệt đối không chạy lệnh shell chỉnh sửa mã nguồn hoặc tự tạo commit.

---

## 2. Năng lực Hỗ trợ Đa Nhiệm của Supervisor (Multi-Task Infrastructure)

Để hiện thực hóa việc thực thi song song theo đồ thị DAG, hạ tầng Supervisor trong `D:\AI_SETUP` được thiết kế với 4 cơ chế an toàn cốt lõi:

1. **Quản lý Trạng thái Bền vững Ngoài Tiến trình (Process-Durable State):**
   - Trạng thái điều phối, hàng đợi merge và danh sách active lease được ghi nhận bền vững xuống đĩa (`SharedOrcaExecutionRegistry`), không bị mất khi worker hoặc tiến trình điều phối khởi động lại.
2. **Cơ chế Phục hồi Luồng Truyền phát (Stream Recovery & Nudge):**
   - Khi luồng stream LLM của worker bị ngắt tạm thời do mạng hoặc quá tải, Supervisor thực hiện tối đa 3 lần nhắc (`nudge`) trên cùng session/capability trước khi chuyển sang xử lý sự cố.
3. **Cơ chế Ngắt mạch Bảo vệ (Circuit Breaker):**
   - Nếu cùng một lỗi gốc bị lặp lại quá 2 lần remediation mà không có tiến triển, Supervisor tự động kích hoạt trạng thái ngắt mạch (`circuit_open` / `blocked`) để yêu cầu can thiệp từ người dùng, ngăn ngừa lãng phí token.
4. **Hàng đợi Tích hợp Tuần tự (Serialized Merge Queue):**
   - Khi nhiều worker độc lập hoàn thành trong cùng một Wave, các candidate commit được đưa vào hàng đợi tích hợp tuần tự dựa trên `merge_priority` để giải quyết rebase và chạy kiểm thử tích hợp đơn luồng.
