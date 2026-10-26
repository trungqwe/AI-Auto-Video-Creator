# Báo cáo khảo sát nguồn nhạc nền (PROD-WIRING-MUSIC-SURVEY)

## Kiểm điều khoản giấy phép

- ngày kiểm: 2026-10-26, nguồn: Openverse, trang đã đọc: https://api.openverse.org/v1/schema/, kết luận bốn tiêu chí: (a) giấy phép lọc được CC0 và CC-BY cho phép dùng thương mại tự do, không NC và không ND; (b) URL và REST API công khai ổn định, truy cập không cần khoá bí mật hay token xác thực (có hạn mức rate limit ẩn danh); (c) metadata chi tiết và chuẩn hóa gồm id, tiêu đề, tác giả, giấy phép, thẻ nhịp điệu và cảm xúc, chuỗi ghi công có sẵn; (d) kho động cập nhật liên tục từ nhiều nguồn lưu trữ mở (Jamendo, Wikimedia Commons).
- ngày kiểm: 2026-10-26, nguồn: Incompetech, trang đã đọc: https://incompetech.com/music/royalty-free/licenses/, kết luận bốn tiêu chí: (a) giấy phép Creative Commons By Attribution 4.0 (CC BY 4.0) cho phép dùng thương mại tự do, không NC, không ND, chỉ yêu cầu ghi công chuẩn; (b) URL tệp âm thanh MP3 và danh mục JSON tĩnh cố định qua HTTPS, truy cập không cần khoá bí mật hay đăng nhập; (c) metadata đầy đủ và chuẩn hóa qua OpenAPI và pieces.json gồm tác giả Kevin MacLeod, tiêu đề, thời lượng, BPM, cảm xúc (feel/mood), thể loại, mã ISRC; (d) kho bán tĩnh được tuyển chọn và duy trì ổn định dài hạn qua nhiều năm.
- ngày kiểm: 2026-10-26, nguồn: Free Music Archive (FMA), trang đã đọc: https://freemusicarchive.org/License_Guide và https://freemusicarchive.org/app-developers, kết luận bốn tiêu chí: (a) nhiều bản nhạc mang giấy phép NC (phi thương mại) hoặc ND (cấm phái sinh và cấm đồng bộ vào video), không đảm bảo bộ lọc thương mại tự động; (b) đã chính thức đóng cửa API công khai cho nhà phát triển ứng dụng do quá tải máy chủ (thông báo tại trang app-developers); (c) có metadata hiển thị trên web nhưng thiếu API mở tự động; (d) kho động do cộng đồng tải lên.
- ngày kiểm: 2026-10-26, nguồn: ccMixter, trang đã đọc: https://ccmixter.org/terms, kết luận bốn tiêu chí: (a) phần lớn tác phẩm sử dụng giấy phép CC-BY-NC (phi thương mại), mục đích thương mại bắt buộc phải mua giấy phép riêng qua CCPlus / TuneTrack; (b) API truy vấn ccHost cũ kỹ qua PHP, cấu trúc URL tải tệp không đồng nhất; (c) có metadata cơ bản nhưng cấu trúc không chuẩn hóa; (d) kho động phối âm remix cộng đồng.
- ngày kiểm: 2026-10-26, nguồn: Pixabay Music, trang đã đọc: https://pixabay.com/api/docs/, kết luận bốn tiêu chí: (a) Content License cho phép sử dụng thương mại miễn phí nhưng có các điều khoản hạn chế phân phối lại tệp âm thanh độc lập; (b) API bắt buộc phải có khoá API bí mật (tham số key), trong khi truy cập web trực tiếp bị tường lửa Cloudflare chặn tự động (HTTP 403 Forbidden); (c) có metadata âm nhạc qua API nhưng đòi hỏi xác thực bằng khoá; (d) kho động phát triển liên tục.

## Lựa chọn

Căn cứ vào kết quả kiểm tra điều khoản thực tế và chấm điểm theo bốn tiêu chí:
- Nguồn chính (primary): Openverse (api.openverse.org). Đạt trọn vẹn 4/4 tiêu chí với số điểm cao nhất: hỗ trợ lọc chính xác các bản nhạc có giấy phép CC0 và CC-BY (cho phép dùng thương mại, không NC, không ND); cung cấp REST API công khai có tài liệu OpenAPI chuẩn hóa, không yêu cầu khoá bí mật; cung cấp siêu dữ liệu đầy đủ bao gồm thông tin tác giả, đường dẫn giấy phép và thẻ phân loại cảm xúc/nhịp điệu; kho động phong phú với hàng nghìn bản nhạc nền.
- Nguồn dự phòng (fallback): Incompetech (incompetech.com). Đạt trọn vẹn 4/4 tiêu chí và thuộc nhà cung cấp độc lập hoàn toàn với Openverse: toàn bộ kho nhạc royalty-free của nhạc sĩ Kevin MacLeod được phát hành theo giấy phép CC BY 4.0 cho phép khai thác thương mại tự do (không NC, không ND); cung cấp danh mục pieces.json và tệp MP3 cố định qua HTTPS không cần khoá bí mật; có OpenAPI 3.0.3 mô tả chi tiết các trường BPM (tempo), feel (mood), instruments; kho tĩnh/bán tĩnh có độ tin cậy và ổn định tuyệt đối về đường dẫn tệp.

## Đo sha256 tệp mẫu

### Tệp mẫu openverse
command: curl.exe -sS -L --fail --proto =https --proto-redir =https --max-filesize 52428800 --max-time 300 -o sample.mp3 "https://prod-1.storage.jamendo.com/?trackid=23557&format=mp32"
exit_code: 0
size_bytes: 5618636
sha256: a2baee1fb967c9a24e97307f61517a88e6e60d1abe2cd7d99ccfcaa873e6caf1
url: https://prod-1.storage.jamendo.com/?trackid=23557&format=mp32
lần tải thứ hai: khớp
tác giả: Zeropage
tiêu đề: Ambient Dance
giấy phép: CC BY 3.0
ngày đăng: 2021-12-23

### Tệp mẫu incompetech
command: curl.exe -sS -L --fail --proto =https --proto-redir =https --max-filesize 52428800 --max-time 300 -o sample.mp3 "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3"
exit_code: 0
size_bytes: 6566713
sha256: 8433b770a630d9b1594fd484442c677907ece899a4d149954cd2e74fd733e311
url: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3
lần tải thứ hai: khớp
tác giả: Kevin MacLeod
tiêu đề: Carefree
giấy phép: CC BY 4.0
ngày đăng: 2014-08-16
