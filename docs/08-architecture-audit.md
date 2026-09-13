# Kiểm toán kiến trúc trước khi ghi ADR

**Ngày:** 12-09-2026  
**Phạm vi:** docs/00, 01, 02, 03, 05, 06, 07 và bản đầu docs/08; tài liệu chính thức về các cơ chế có ảnh hưởng tới kết luận.  
**Kết quả:** bản đầu chưa đủ chặt chẽ để làm hồ sơ quyết định. Đã sửa thiết kế và ghi [ADR](./adr/README.md); các gate thực nghiệm còn mở. Đây là audit tài liệu, không phải kiểm thử hệ thống.

## 1. Phát hiện và cách xử lý

Mức cao là lỗi thiết kế có thể làm mất dữ liệu, sai sản lượng, bỏ quyền truy cập hoặc phá yêu cầu đã duyệt. Mức vừa là thiếu cơ chế/bằng chứng có khả năng gây khó vận hành hoặc buộc đổi thiết kế. Vị trí bản đầu dùng số mục vì số dòng thay đổi sau sửa.

| Mã | Mức | Vị trí bản đầu và tình huống cụ thể | Điều chỉnh đã ghi | Hồ sơ |
|---|---|---|---|---|
| AUD-01 | Cao | 3.4, 14, 16: gọi Temporal đã chọn/đóng dù chưa chứng minh tài nguyên và chi phí; mọi open bị nói là không cản trở | `Conditional`; phân tích độ nhạy điểm; gate trước production, không mở code sớm để làm proof | ADR-0003, 0011 |
| AUD-02 | Cao | 5.1, 8.2: có Temporal Server nhưng không chỉ rõ worker chạy workflow; desktop tắt có thể không còn ai chạy logic điều phối | Cloud Workflow Worker và queue riêng, tách Workflow Tasks khỏi Activity Tasks | ADR-0003 |
| AUD-03 | Cao | 8.3: worker A mất mạng, B nhận retry; A về muộn ghi đè B hoặc xóa file | Execution generation, device scope, conditional commit, artifact mỗi attempt bất biến | ADR-0004 |
| AUD-04 | Cao | 7.4, 9.2: xóa ngay sau SYNCED; workflow ACK trước commit nghiệp vụ; crash gây lệch trạng thái và đếm lại | Commit stage trước ACK; completion ledger/gate/biến thể/counter nguyên tử; cleanup cần authorization | ADR-0004, 0006 |
| AUD-05 | Cao | 5.2, 7.1: gọi SQLite là cache tái dựng được, nhưng receipt chưa gửi chỉ tồn tại tại đó | Tách journal bền với cache bỏ được; giữ receipt/output chưa reconcile | ADR-0006 |
| AUD-06 | Cao | 7.4: artifact ID nội bộ không tự chống upload Drive trùng; checksum mô tả mơ hồ | Pre-generated Drive ID, mapping bền trước upload, verify hash và reconcile trạng thái không rõ | ADR-0006 |
| AUD-07 | Cao | 7.3: lọc quyền/trạng thái nguồn dễ chặn historical data sau xóa nguồn hoặc unknown rights | Tách quyền thu thập mới và khai thác tài nguyên đã có; giữ R24 và charter | ADR-0005 |
| AUD-08 | Cao | 12.3: dump riêng app/Temporal/visibility không cùng snapshot; restore có thể replay side effect đã xảy ra ở Drive | Backup cluster + WAL; restore cách ly, recovery epoch và reconcile ngoài database | ADR-0010 |
| AUD-09 | Cao | 11: mTLS chưa là authorization; loopback chưa chặn website khác gửi lệnh; cloud refresh token chưa có chủ sở hữu | Worker permission, local HTTPS/session/Origin, secret bundle và J cloud quản refresh | ADR-0009 |
| AUD-10 | Vừa | 10.1: rate limit theo account không đủ; nhiều key cùng project có thể bị tính riêng | Quota scope provider/project/model; ledger dùng chung cloud/desktop; không suy quyền API từ thuê bao | ADR-0008 |
| AUD-11 | Vừa | 8.1: thiếu workflow chạy riêng từng stage, dễ auto chạy hết hoặc tạo đường debug bỏ gate | Manual/auto dùng cùng stage handler; debug dừng sau stage; child lỗi không giết sibling | ADR-0003 |
| AUD-12 | Vừa | 8.2, 13: queue theo CPU/GPU chưa gắn device; thêm máy có thể nhận việc cần file trên máy khác | Device affinity và resource arbitration chung, không hứa scale chỉ bằng thêm worker | ADR-0003, 0011 |
| AUD-13 | Vừa | 7.5, 8.3: snapshot chưa có mốc transaction; thay provider/voice có thể giữ subtitle cũ | Snapshot trước script call, result revision riêng, ghi fallback thực và vô hiệu hóa phần phụ thuộc | ADR-0005, 0008 |
| AUD-14 | Cao | 8, 10.3: UUID/attempt khác có thể bị tính là biến thể; gate cuối không nhắc tiếng Anh, suy luận, âm thanh và hook thực | Signature theo nội dung thực + giữ chỗ + kiểm tra lại; giữ đầy đủ QR/DR đã duyệt | ADR-0004, 0005 |
| AUD-15 | Vừa | 7.3: đổi embedding model dễ trộn các vector không cùng không gian | Versioned embedding space, index mới song song, chuyển active revision và rollback | ADR-0002 |
| AUD-16 | Cao | 12, 13: năm video không giới hạn được byte; spool cloud có thể lấp ổ chứa PostgreSQL | Byte admission cho desktop/cloud, giữ reference tệp dùng chung, dừng cấp việc phụ thuộc khi thiếu chỗ | ADR-0010, 0011 |
| AUD-17 | Vừa | 12: maintenance nằm trong engine lỗi; toàn log vào PostgreSQL có thể làm phình kho | Host supervisor/backup độc lập, log detail có giới hạn, durable status riêng | ADR-0010, 0011 |
| AUD-18 | Vừa | 11.3 và pin version: workspace ID không bảo đảm SaaS isolation; thiếu cách nâng workflow/schema đang chạy | Scope trên query/key/secret; expand-contract, replay compatibility và rollout có rollback | ADR-0012 |

Tất cả mục trên đã được xử lý ở mức thiết kế trong tài liệu 08 và ADR. Không đánh dấu là lỗi triển khai đã sửa hoặc test đã pass.

## 2. Bằng chứng làm thay đổi kết luận

- Temporal phân biệt Workflow Task và Activity Task, worker phải có handler đúng với queue. Suy ra cần cloud worker chạy workflow độc lập với desktop. [Temporal Task Queues](https://docs.temporal.io/task-queue).
- `pg_dumpall` tạo snapshot từng database không đồng bộ. Vì thế không dùng dump riêng để tuyên bố phục hồi chung app/workflow. [PostgreSQL SQL Dump](https://www.postgresql.org/docs/current/backup-dump.html).
- Drive cho phép dùng ID cấp trước để tránh tạo file mới khi retry; API vẫn cần kiểm tra đối tượng khi kết quả không rõ. [Drive uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads#use_a_pre-generated_id_to_upload_files).
- Gemini áp quota theo project; số API key không đại diện số quota độc lập. [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
- OAuth External/Testing có refresh token hết hạn sau bảy ngày trong trường hợp Google mô tả. Đăng nhập một lần không chứng minh cloud chạy nền lâu dài. [Google OAuth](https://developers.google.com/identity/protocols/oauth2#expiration).
- Temporal tách TLS, authentication và authorization; chỉ có mTLS chưa đủ để kết luận desktop chỉ có quyền worker. [Temporal security](https://docs.temporal.io/self-hosted-guide/security).

## 3. Những điều chưa thể kết luận

1. Chưa chứng minh toàn bộ pipeline và cloud host nằm dưới 50 USD/tháng. Chưa có profile workload tháng, hóa đơn API hoặc benchmark RAM/CPU.
2. Chưa kiểm tra bốn tài khoản có quyền API và dung lượng như thông tin cung cấp; chưa chứng minh vòng refresh token và quota độc lập.
3. Chưa có bộ output profile, preset, model/TTS/word alignment đã đo trên máy mục tiêu; chưa chứng minh 100 video hoàn thành gồm sync trong 12 giờ.
4. Chưa có kết quả crash/retry/restore hoặc workflow replay. Cơ chế mới là thiết kế cần kiểm chứng.
5. Chưa chốt số nguồn/bài/media và quy mô bảng, nên chưa chứng minh p95 UI, độ chính xác retrieval hoặc tăng trưởng PostgreSQL.
6. Chưa render sơ đồ bằng Mermaid engine. Kiểm tra văn bản/fence không chứng minh sơ đồ hiển thị đúng; tuyên bố “Mermaid hợp lệ” ở lần bàn giao trước mạnh hơn bằng chứng thực có.

Các số release, contributor, ngày push trong tài liệu 05 là ảnh chụp nghiên cứu cũ, không dùng để chứng minh phiên bản triển khai tương thích. ADR không khóa dependency theo các con số đó; danh mục pin/build/license phải kiểm chứng ở bước triển khai.

## 4. Kịch bản phản biện sau sửa

| Kịch bản | Bất biến thiết kế phải giữ | Cần thử sau khi được code |
|---|---|---|
| Result đã commit, ACK thất lạc | Trả receipt cũ, không render/đếm lại | Ngắt kết nối ngay sau commit |
| Hai attempt cùng trả kết quả | Chỉ generation hợp lệ commit; artifact cũ không overwrite | Cho worker cũ về muộn |
| Drive nhận file, app chưa nhận phản hồi | Giữ cùng file ID, verify rồi commit | Ngắt từng đoạn upload/metadata |
| Restore DB cũ trong khi Drive có file mới hơn | Dừng side effect và cleanup tới khi reconcile xong | Restore cách ly với Drive test |
| Desktop tắt, cloud AI lỗi | Crawl không cần AI tiếp tục; việc AI chờ | Tắt desktop qua lịch quét |
| Nguồn đã xóa được tìm lại | Chặn thu thập mới, vẫn dùng media lịch sử | Rediscovery + search lịch sử |
| Có voice/subtitle nhưng script thay revision | Không render timing từ voice cũ | Thay result trong debug |
| Cửa sổ năm job chứa tệp quá lớn | Giảm admission theo byte, giữ output chưa sync | Giả lập low-disk cả cloud/desktop |
| Lô còn một suất, hai video về cùng lúc | Reservation + completion transaction không vượt mục tiêu | Commit đồng thời |
| Temporal upgrade trong lô đang chờ | Workflow cũ replay được hoặc có worker tương thích | Replay history trên bản mới |
| Website khác gọi local API | Không nhận command hoặc secret | Kiểm tra Origin/session/Host |
| Cùng topic đạt ngưỡng, Tier sau bị bỏ qua | Không báo là mất lịch, cũng không che lịch lỗi thật | Đối chiếu lịch/CollectionRun |

## 5. Kết luận chuyển bước

Đủ căn cứ ghi ADR cho hướng kiến trúc và tiếp tục định nghĩa giao tiếp. Chưa đủ căn cứ đóng tính khả thi production. Không còn câu hỏi bắt buộc người dùng trả lời ngay để viết hồ sơ quyết định; phần chưa biết được giữ thành gate có chủ sở hữu và bằng chứng cần nộp trong ADR index.

Việc hoàn thành audit này không thay bước 14 kiểm toán trước code. Không có source code, thư viện, tài khoản, hạ tầng hoặc dịch vụ mới được khởi tạo.

## 6. Kiểm tra tài liệu đã thực hiện

- Kiểm tra 24 tệp Markdown sau khi thêm báo cáo red-team/security: UTF-8 strict, không BOM, fence đóng, số cột từng bảng nhất quán và liên kết nội bộ tồn tại; không phát hiện lỗi trong các kiểm tra này.
- Kiểm tra đủ 12 ADR có trạng thái, bối cảnh cần quyết định, lựa chọn, quyết định/lý do, bất lợi, cách kiểm chứng và đường thay đổi. Có 7 `Accepted` và 5 `Conditional`.
- Tính lại ma trận trọng số: P1 6,05; P2 7,35; P3 7,90; P4 8,15. Phân tích độ nhạy cho thấy không được xem thứ hạng là bằng chứng thực nghiệm.
- Đối chiếu các quy tắc R01-R25, DR và ngưỡng QR được nhắc trong thiết kế; bổ sung đường dẫn baseline và cập nhật trạng thái kỹ thuật liên quan trong 02/03/05/06/07.
- Không chạy Mermaid renderer, product test, benchmark, kiểm tra tài khoản thật hoặc restore drill. Các gate trong ADR index còn nguyên trạng thái chưa thực hiện.
