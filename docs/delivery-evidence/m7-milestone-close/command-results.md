# Ghi nhận lệnh kiểm M7 (revision 6)

## 1. Bộ lệnh kiểm của milestone do Control đo

- Control đo toàn bộ 474 lệnh kiểm của milestone M7 trên candidate sau worker_done. Worker không chạy bộ lệnh này và không dẫn mã bản đo.
- Tệp này không công bố số lệnh đạt, exit code hay thời gian chạy của 474 lệnh đó. Reviewer (Sonnet 5.5) và Auditor rủi ro (Opus 5.5) đối chiếu bản đo mà đề bài của Control nêu.
- Revision 5 ghi 470 lệnh do Worker tự chạy; nhật ký và số liệu của revision đó đã được thay bằng tệp này và không còn dùng cho revision 6.
- Các tệp packages.md, gate-releases.md và exit-gates.md chỉ dẫn tên tệp test hoặc tài liệu liên quan, không dẫn số thứ tự chuỗi lệnh.

## 2. Lệnh Worker tự chạy trong revision 6

Worker chỉ chạy các lệnh sau bằng interpreter khoá của lane, sau khi ghi xong mọi tệp; exit code từng lệnh được Worker báo trong worker_done, không ghi lại ở đây.

1. Probe đọc gate-releases.md: đủ 16 cổng GATE-* kèm recordHash 64 hex đúng với đề bài.
2. Probe đọc packages.md: mọi mã gói trong yêu cầu nghiệm thu có hàng kèm SHA tích hợp 40 hex, có PW-D1-FIX1 và ADAPT-D-FIX1 (SHA integration head 32e335249dad5b390e05d7212b22e1718bb14d72), hai gói retire vẫn được nêu.
3. Probe đọc năm tệp .md của thư mục này: UTF-8 không BOM, không có ký tự thay thế U+FFFD, còn chữ tiếng Việt có dấu.
4. Probe đọc report.md và exit-gates.md: không còn số liệu hay mã tham chiếu cũ của revision 5, có đủ mã gate cần đối chiếu.
5. git diff --check.

## 3. Giới hạn

- Không chạy pytest, npm hay bộ lệnh kiểm của milestone trong lượt này.
- Không có kết quả giả: mọi kết luận đạt hay không đạt của 474 lệnh thuộc bản đo của Control.
