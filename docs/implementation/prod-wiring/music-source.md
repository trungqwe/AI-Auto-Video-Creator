# Khảo sát nguồn nhạc nền, chọn nguồn chính và dự phòng (PW-E4 phần 1)

## 1. Căn cứ

Căn cứ theo đặc tả kỹ thuật và yêu cầu kiến trúc của hệ thống:
- FR-AUD-007 (hệ thống tự tìm và thu thập nhạc nền, ghi xuất xứ, không AI sáng tác, R11, docs/01-product-spec.md:212): Nhạc nền trong giai đoạn đầu do hệ thống tự tìm và thu thập từ các kho nhạc ngoài có nguồn gốc rõ ràng, không sử dụng nhạc do mô hình AI tạo ra.
- FR-AUD-004 (AI chọn nhạc nền theo cảm xúc và nhịp kể, docs/01-product-spec.md:209): Hệ thống AI lựa chọn nhạc nền phù hợp dựa trên thông tin siêu dữ liệu về cảm xúc (mood), thể loại (genre) và nhịp điệu (tempo) của từng tác phẩm để khớp với nhịp kể video.
- DQ-12 và OI-PW-06: Xác định nguồn dữ liệu âm nhạc tin cậy, phân định rõ nguồn chính và dự phòng, đảm bảo tính toàn vẹn và bản quyền thương mại.

## 2. Bốn tiêu chí

Hệ thống đánh giá các nguồn ứng viên theo bốn tiêu chí định lượng (mỗi tiêu chí đạt được tính 1 điểm, tối đa 4 điểm):
1. Giấy phép nội dung: Cho phép sử dụng thương mại, không có điều khoản hạn chế phi thương mại (không NC) và không cấm tác phẩm phái sinh (không ND - do việc ghép nhạc nền vào video là một dạng tác phẩm phái sinh/đồng bộ).
2. Tính ổn định của URL và API: Cung cấp API hoặc URL tệp tải trực tiếp qua HTTPS ổn định, truy cập công khai mà không đòi hỏi khoá API bí mật hay tài khoản trả phí.
3. Siêu dữ liệu (metadata): Cung cấp đầy đủ thông tin về giấy phép, tên tác giả, tiêu đề và các thuộc tính hỗ trợ lựa chọn nhạc (cảm xúc, nhịp điệu, thể loại).
4. Tần suất thay đổi: Kho dữ liệu có tính ổn định cao, đảm bảo URL và nội dung không biến mất hoặc thay đổi băm sha256 thất thường.

## 3. Khảo sát

Các nguồn ứng viên được khảo sát và đánh giá chi tiết theo bốn tiêu chí trên:

candidate: Openverse ; giấy phép: Lọc được CC0 và CC-BY cho phép dùng thương mại, không NC và không ND (1/1) ; ổn định không bí mật: REST API công khai và URL ổn định, không cần API key bí mật (1/1) ; metadata: Đầy đủ tên tác giả, giấy phép, thẻ cảm xúc (mood) và nhịp điệu (tempo) phục vụ FR-AUD-004 (1/1) ; tần suất thay đổi: Kho động cập nhật mở rộng thường xuyên (1/1) ; điểm: 4/4 ; kết luận: Đạt, chọn làm nguồn chính
candidate: Incompetech ; giấy phép: Cấp phép CC-BY 4.0 dùng thương mại tự do, không NC và không ND (1/1) ; ổn định không bí mật: OpenAPI và URL tệp MP3 tĩnh cố định qua HTTPS, không cần khóa bí mật (1/1) ; metadata: Đầy đủ tác giả Kevin MacLeod, BPM (nhịp), feel (cảm xúc) và genre phục vụ FR-AUD-004 (1/1) ; tần suất thay đổi: Kho bán tĩnh lưu trữ ổn định dài hạn (1/1) ; điểm: 4/4 ; kết luận: Đạt, chọn làm nguồn dự phòng
candidate: Free Music Archive ; giấy phép: Đa số mang giấy phép NC hoặc ND cấm đồng bộ video thương mại (0/1) ; ổn định không bí mật: Đã đóng cửa API công khai cho app developer do quá tải máy chủ (0/1) ; metadata: Có trên web nhưng thiếu API mở tự động truy xuất thể loại và nhịp điệu (0/1) ; tần suất thay đổi: Kho động cộng đồng (1/1) ; điểm: 1/4 ; kết luận: Loại do thiếu API mở và giấy phép không đảm bảo
candidate: ccMixter ; giấy phép: Đa số cấp phép CC-BY-NC cấm dùng thương mại, thương mại phải mua bản quyền CCPlus (0/1) ; ổn định không bí mật: API ccHost cũ qua PHP, URL tải không đồng nhất (0/1) ; metadata: Có thẻ nhãn cơ bản nhưng cấu trúc không chuẩn hóa để phân loại nhịp tự động (1/1) ; tần suất thay đổi: Kho động cộng đồng (1/1) ; điểm: 2/4 ; kết luận: Loại do ràng buộc phi thương mại NC
candidate: Pixabay Music ; giấy phép: Cho phép dùng thương mại miễn phí nhưng có điều khoản hạn chế phân phối tệp (0/1) ; ổn định không bí mật: Bắt buộc dùng API key bí mật, truy cập web bị Cloudflare chặn bot (0/1) ; metadata: Cung cấp thời lượng và thể loại qua API nhưng đòi hỏi xác thực (0/1) ; tần suất thay đổi: Kho động phát triển liên tục (1/1) ; điểm: 1/4 ; kết luận: Loại do bắt buộc khóa bí mật và cơ chế chống bot

Về khía cạnh phục vụ FR-AUD-004, Openverse cung cấp hệ thống thẻ phân loại nhịp điệu và sắc thái cảm xúc, trong khi Incompetech cung cấp chỉ số BPM (nhịp) định lượng chính xác cùng trường cảm xúc (feel/mood) và thể loại (genre) giúp mô hình AI dễ dàng ánh xạ vào cấu trúc cảm xúc và nhịp dựng của kịch bản video.

## 4. Quyết định

Căn cứ vào kết quả đánh giá, hệ thống lựa chọn Openverse làm nguồn nhạc nền chính (primary) và Incompetech làm nguồn dự phòng (fallback) từ nhà cung cấp độc lập. Thông tin tệp mẫu đã được tải và đo băm sha256 thực tế qua kết nối HTTPS như sau:

role: primary source_id: openverse url: https://prod-1.storage.jamendo.com/?trackid=23557&format=mp32 license: CC BY 3.0 attribution: "Ambient Dance" by Zeropage is licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/) author: Zeropage sha256: a2baee1fb967c9a24e97307f61517a88e6e60d1abe2cd7d99ccfcaa873e6caf1
role: fallback source_id: incompetech url: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3 license: CC BY 4.0 attribution: Carefree by Kevin MacLeod | License: CC BY 4.0 | https://incompetech.com author: Kevin MacLeod sha256: 8433b770a630d9b1594fd484442c677907ece899a4d149954cd2e74fd733e311

## 5. Ràng buộc cho PW-E4 phần (2)-(4)

Triển khai phần (2)–(4) của PW-E4 cần tuân thủ nghiêm ngặt các nguyên tắc sau:
1. Tệp cấu hình tools/launcher/prod/music_sources.json chỉ được cấu hình đúng hai nguồn từ hai dòng role ở trên (openverse làm primary và incompetech làm fallback).
2. Danh sách allowlist host cho cơ chế phòng vệ SSRF chỉ bao gồm host của hai URL trên (prod-1.storage.jamendo.com và incompetech.com) cùng host API (api.openverse.org).
3. Sau khi tải tệp âm thanh qua HTTPS, bắt buộc phải tính băm SHA-256 và so khớp với giá trị đã ghim; nếu sai lệch phải từ chối và ghi log cảnh báo ngay lập tức.
4. Ghi nhận đầy đủ nguồn gốc (provenance) của tệp âm thanh bao gồm: URL nguồn, giấy phép, tác giả, thời điểm thu thập và mã băm sha256.
5. Tuyệt đối không thu thập hoặc tích hợp các tệp nhạc do trí tuệ nhân tạo (AI) sáng tác.
6. Trường hợp không tìm thấy bản nhạc phù hợp hoặc nguồn nhạc gặp sự cố, hệ thống phải trả kết quả audio_bed_result loại none kèm cảnh báo AUDIO_MIX_QUALITY, chuỗi xử lý vẫn tiếp tục hoàn thành video mà không bị dừng đột ngột.

## 6. Giả định và mục mở

- GIẢ ĐỊNH: Điều khoản giấy phép và cơ chế truy cập công khai của các nguồn ứng viên được xác nhận chính xác tại ngày kiểm 2026-10-26 ghi trong báo cáo khảo sát và có thể thay đổi trong tương lai theo chính sách của nhà cung cấp.
- OI-PW-06: Mục mở về việc mở rộng thêm các kho nhạc nền bổ sung vẫn ở trạng thái chờ xác nhận của người dùng (pendingUserCheckpoint), chưa được coi là đã duyệt.
