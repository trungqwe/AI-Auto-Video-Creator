# ADR-0005: Snapshot và các bất biến nội dung

**Trạng thái:** Accepted - thiết kế bảo toàn yêu cầu; thuật toán/ngưỡng còn cần G06  
**Căn cứ:** R01-R09/R14/R16/R22-R25; DR-003/004/005/006/016/017/018/019.  
**Liên quan:** [ADR-0002](./0002-authoritative-data-and-search.md), [ADR-0004](./0004-commit-idempotency-and-fencing.md).

## Tại sao phải quyết định

Nguồn và prompt đổi trong khi lô đang chạy. Bài đăng lại bổ sung media nhưng không phải diễn biến mới. Một thay đổi tên/ID không đủ tạo biến thể. Hệ thống cần tách dữ liệu mới, lịch sử đã dùng và kết quả sáng tạo để không kể sai ngữ cảnh hoặc lặp video.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Luôn đọc nguồn/prompt mới nhất | Cập nhật ngay | Job đổi đầu vào giữa chừng, không truy được bản đã dùng |
| Đóng toàn bộ cấu hình ở đầu lô | Đơn giản | Trái R16 với job chưa bắt đầu script |
| Snapshot theo job trước lần tạo script đầu tiên | Đúng R09/R16, giữ lịch sử | Cần revision và invalidation graph |

## Chọn cái gì và tại sao

Chọn snapshot theo job, commit một lần trước script call. Giữ nguồn/revision, prompt/policy/preset registry version; script/plan/asset thực chọn là các result có revision. Retry giữ snapshot; đổi voice/asset/script result làm vô hiệu hóa đúng phần phụ thuộc, không ghi đè lịch sử. Credential bị thu hồi vẫn bị thu hồi dù job giữ policy cũ.

B giữ tin đại diện và provenance bản trùng; không tạo thêm tin/script chỉ từ URL đăng lại. Media mới được nhập qua C/I với xuất xứ riêng. Chỉ `EventUpdate` có tình tiết mới cho phép dạng “từ lúc đó đến nay”; liên kết chưa chắc giữ bài riêng theo R06.

R08 chọn nguồn Tier ưu tiên. Cùng Tier thì giữ đại diện hiện có; chưa có đại diện thì phá hòa theo Source ID ổn định, chọn revision hiện hành của nguồn đó. Đây là quy tắc kỹ thuật để tái lập lựa chọn, không chứng nhận nguồn đúng hơn. Ghi cả mâu thuẫn, không thêm cổng kiểm chứng đa nguồn hoặc người dùng duyệt.

Xóa nguồn tạo tombstone để chặn crawl/rediscovery và tải bổ sung mới từ nguồn đó, nhưng không chặn khai thác tin/media đã lưu. `unknown rights` là metadata/cảnh báo theo charter, không là điều kiện tự loại tài nguyên.

Chống trùng có hai lớp: reservation phương án đang chạy và signature output thực. Trong lượt 1-3 video phải khác góc thực; giữa lượt phải khác ít nhất một yếu tố đã chốt, không hoàn toàn giống output cũ và không lặp script gần nhất theo charter. Hash chuẩn hóa text/asset content/order/timeline/audio/preset parameters phục vụ so sánh; UUID, attempt, timestamp, container metadata không phải sáng tạo mới.

Marker suy luận phải còn thể hiện ở lời kể/phụ đề; QC kiểm tra bản được dựng, không chỉ cờ trong database. Hook minh họa tách khỏi thumbnail của câu chuyện. Thumbnail là ảnh riêng và không được miễn kiểm tra ảnh nhạy cảm chỉ vì nằm trong hook.

## Điểm bất lợi

Giữ snapshot và lịch sử tăng dữ liệu; signature không tự hiểu “góc kể khác nhau”. Quy tắc phá hòa cùng Tier chỉ ổn định, không tối ưu độ đúng. Ngưỡng duplicate/event/semantic cần bộ mẫu, không tự tuyên bố chính xác từ schema.

## Kiểm chứng

G06: nguồn sửa giữa lô, bài đăng lại thêm clip, mâu thuẫn cùng Tier, xóa/rediscover, source thiếu, hai job cùng chọn asset/script, đổi voice sau subtitle, suy luận bị mất marker. Giữ các ngưỡng QR đã duyệt và mẫu ảnh lỗi trong mẫu đánh giá R25.

## Sau này đổi thì thế nào

Version hóa source-selection, signature và inference policy. Tính signature mới song song, giữ dấu cũ để đối chiếu lịch sử; không tuyên bố toàn bộ video cũ “chưa từng có” sau đổi thuật toán. Job đã snapshot giữ policy cũ; nguồn/prompt mới áp vào job chưa bắt đầu script. Đổi nghiệp vụ khác góc/nguồn cần xác nhận mới, không chỉ đổi implementation.
