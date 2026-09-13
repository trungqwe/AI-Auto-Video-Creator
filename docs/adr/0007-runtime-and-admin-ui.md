# ADR-0007: Runtime, UI bảng và vai trò Google Sheets

**Trạng thái:** Accepted - baseline thiết kế; pin phiên bản và profile output chờ G07  
**Căn cứ:** R02/R03/R14/R15/R16; QR-UX-001/002, QR-PERF-005/006, QR-COMP-006; ARCH-006/011.  
**Liên quan:** [ADR-0001](./0001-hybrid-modular-monolith.md), [ADR-0009](./0009-trust-boundaries-and-secrets.md).

## Tại sao phải quyết định

Người dùng cần UI tiếng Việt dạng bảng và debug từng công đoạn; phần nặng thuộc hệ sinh thái AI/media. Chọn runtime và UI quyết định số toolchain cần duy trì, tốc độ tích hợp và khả năng bảo vệ metadata được sửa.

## Các lựa chọn

| Năng lực | Lựa chọn | Đánh đổi |
|---|---|---|
| Backend | Python; TypeScript; phối hợp nhiều runtime | Python hợp ứng viên crawl/AI/media đã nghiên cứu; TypeScript giảm khác biệt UI nhưng cần thêm bridge cho nhiều tác vụ; nhiều runtime tăng tích hợp |
| UI | React web + Local Agent; Electron/Tauri; desktop native | Web dùng lại cho SaaS, agent truy GPU/file; shell đóng gói thêm runtime; native tăng công sức UI bảng |
| Bảng | AG Grid Community; TanStack Table; Google Sheets | AG Grid có UI dựng sẵn; TanStack linh hoạt nhưng phải xây thêm tương tác; Sheets thêm sync/quota và rủi ro write-back |
| Render | FFmpeg adapter; wrapper dựng cấp cao; renderer browser | FFmpeg kiểm soát media tốt; wrapper cần giữ tương thích; browser tăng runtime và cần benchmark riêng |

## Chọn cái gì và tại sao

Python cho backend/worker, FastAPI cho Control API/Local Agent; React + TypeScript và AG Grid Community cho UI. FFmpeg/ffprobe qua adapter I/O có typed result và process isolation. Chỉ pin runtime/build sau kiểm tra hệ điều hành, GPU, font, subtitle và license.

Google Sheets không là lõi và không nằm trong đường chạy v1. Dữ liệu bảng lấy qua API có pagination/filter/sort phía server. Dùng các tương tác Community; không ngầm cần Enterprise clipboard, Excel export hoặc row grouping. [AG Grid Community và Enterprise](https://www.ag-grid.com/react-data-grid/community-vs-enterprise/).

Metadata write qua allowlist và version check, nhận giá trị đã commit từ API; không sửa script/bài gốc/event link. Các view job/media/source/hook/prompt có lệnh stage và trạng thái theo product spec, không có bước duyệt mới.

UI gửi command HTTP, nhận event SSE một chiều; Local Agent giữ credential thay browser. SSE là tín hiệu cập nhật: có revision/cursor, reconnect thì đọc lại trạng thái, không làm command bus. FastAPI hỗ trợ SSE; phiên bản tích hợp vẫn phải pin qua G07. [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/).

## Điểm bất lợi

Hai ngôn ngữ, browser và native Python agent cần đóng gói tương thích. Loopback HTTPS/certificate tăng công việc cài đặt. Community không phải Google Sheets đầy đủ; các thao tác spreadsheet chưa được yêu cầu không mặc nhiên có sẵn.

## Kiểm chứng

G07: UI tiếng Việt trên desktop 1080p+, p95 2 giây trên dataset đã chốt, command ACK 1 giây, reconnect không mất trạng thái. G02/G07: FFmpeg build, phụ đề burn-in/từng từ, hook/thumb, tiếng Anh, 61-70 giây, âm thanh và file phát được. Đếm thẻ fence trong Markdown không phải kiểm thử UI hoặc render.

## Sau này đổi thì thế nào

Thay grid giữ API contract/metadata rule; thử TanStack nếu Community không đủ nhưng chưa cần mua Enterprise. Đóng gói web UI bằng shell hoặc đưa UI lên cloud giữ application boundary; mở SaaS cần ADR-0012. Thêm Sheets adapter sau này là thay đổi phạm vi tích hợp phải có contract; write-back luôn qua validation, không tạo writer thứ hai.
