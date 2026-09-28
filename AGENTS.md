# Quy tắc làm việc trong repository

## Ngôn ngữ và encoding

- Nội dung người dùng và tài liệu viết bằng tiếng Việt đầy đủ dấu.
- Tệp văn bản dùng UTF-8 không BOM; code, identifier, schema và log dùng tiếng Anh.

## Nguồn sự thật và phạm vi

- Bắt đầu phiên bằng `HANDOFF.md`, sau đó đọc checklist, roadmap và plan của milestone đang hoạt động.
- Không suy diễn trạng thái từ tài liệu lịch sử. Trạng thái hiện hành nằm trong `docs/12-pre-code-checklist.md`.
- Milestone M1 đã ACCEPTED / CLOSED. Milestone M2 được phép planning và implementation theo kế hoạch được duyệt. M3 và Phân hệ A tiếp tục bị khóa chặt tới khi M2 qua exit gate, audit và user checkpoint riêng.
- Không ghi giả định thành quyết định. Nội dung chưa được xác nhận phải ghi `GIẢ ĐỊNH` hoặc open item với gate rõ ràng.

## Định tuyến skill

- Không chạy hoặc sử dụng global skill router trong repository này để tránh xung đột hướng dẫn.
- Khi tác vụ liên quan Orca, dùng trực tiếp skill mặc định theo phiên bản hiện hành qua `orca skills get orca-cli --json`.
- Với các tác vụ khác, ưu tiên skill cục bộ của repository; nếu không có, chọn trực tiếp skill phù hợp từ catalog hiện hành mà không tạo hoặc làm mới router.

## Quy tắc implementation

- Tuân thủ test-first và evidence protocol của milestone plan đang hoạt động.
- Phải chứng kiến RED đúng oracle trước implementation; setup/import/binary missing không phải RED hợp lệ.
- Không dùng `latest`, không đổi M1-R1 âm thầm và không dùng mock để tuyên bố external gate PASS.
- Không commit secret, token, credential, dữ liệu cá nhân, log chưa redacted hoặc media không rõ quyền sử dụng.
- Khi có STOP condition, dừng work package phụ thuộc và ghi evidence; không đi tiếp rồi sửa sau.

## Kết thúc mỗi phiên sửa đổi hoặc checkpoint quan trọng

1. Đồng bộ tài liệu nguồn sự thật bị ảnh hưởng.
2. Xóa giả định/suy nghĩ trung gian đã hết giá trị.
3. Ghi quyết định mới và open item còn lại.
4. Cập nhật tiến độ/tính năng trong `README.md` và `CHANGELOG.md` khi có thay đổi đáng chú ý.
5. Thay nội dung `HANDOFF.md` bằng bản ngắn gồm: đã quyết định, chưa quyết định, tệp cần đọc tiếp và điểm tiếp tục.
6. Chạy test/validation phù hợp và không tuyên bố PASS thiếu evidence.
7. Kiểm tra secret, commit theo Conventional Commits và push lên `origin` để sao lưu/rollback/đối chiếu.

<!-- dely:begin -->
## Dely

Bounded or Architectural work invokes `dely:delivery`; Spike starts no
delivery run.

| Phase | Harness | Model | Effort |
| --- | --- | --- | --- |
| `implement` | Codex CLI | ag/gemini-3.8-flash-high | high |
| `review` | Claude Code | cx/gpt-5.6-sol-high | high |
<!-- dely:end -->
