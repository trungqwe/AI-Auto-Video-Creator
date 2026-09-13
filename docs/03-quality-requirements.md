# AI Auto Video Creator - Yêu cầu chất lượng hệ thống

**Đối chiếu sau audit kiến trúc:** [ADR index](./adr/README.md) ánh xạ các gate kiểm chứng tới yêu cầu bên dưới. Không có QR hoặc QUALITY-PROPOSED đã duyệt nào được hạ ngưỡng. `Accepted` trong ADR là trạng thái thiết kế, không phải kết quả nghiệm thu.

**Giai đoạn:** 06 - Xác định yêu cầu chất lượng hệ thống  
**Ngày lập:** 12-09-2026  
**Trạng thái:** Đã được người dùng phê duyệt ngày 12-09-2026; tất cả `QUALITY-PROPOSED-*` đã trở thành yêu cầu chính thức  
**Tài liệu nguồn:** [00-project-charter.md](./00-project-charter.md), [01-product-spec.md](./01-product-spec.md), [02-data-model.md](./02-data-model.md)

**Cập nhật làm rõ:** R01-R25 được xác nhận sau bản đầu; xem [07-data-flow.md](./07-data-flow.md), mục 2. Các ngưỡng QUALITY-PROPOSED đã duyệt vẫn có hiệu lực. Thay đổi phạm vi được ghi rõ dưới đây, chưa phải bằng chứng benchmark.

## 1. Mục đích

Tài liệu này xác định hệ thống phải thực hiện các chức năng đã mô tả tốt đến mức nào. Các yêu cầu tập trung vào tốc độ, độ ổn định, khả năng phục hồi, chất lượng dữ liệu, khả năng quan sát, chi phí, bảo mật, khả năng mở rộng và trải nghiệm người dùng.

Tài liệu không lựa chọn kiến trúc, cơ sở dữ liệu, dịch vụ, framework, thư viện, giao thức hoặc cách triển khai.

## 2. Trạng thái yêu cầu

- **ĐÃ XÁC NHẬN:** xuất phát trực tiếp từ charter, product spec hoặc câu trả lời của người dùng.
- **ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT:** ngưỡng chất lượng ban đầu do kỹ sư trưởng đề xuất và đã được người dùng phê duyệt ngày 12-09-2026; có hiệu lực như yêu cầu chính thức.
- **CHƯA QUYẾT ĐỊNH:** chưa đủ dữ liệu để đưa ra ngưỡng hợp lý.

Các yêu cầu đã được phê duyệt được dùng làm tiêu chí nghiệm thu chính thức. Các mục `CHƯA QUYẾT ĐỊNH` vẫn chưa được tự động dùng làm tiêu chí nghiệm thu.

## 3. Bối cảnh đo chất lượng

Các phép đo hiệu năng và độ ổn định phải ghi rõ bối cảnh:

- Máy render mục tiêu: AMD Ryzen 9 7950X, RAM 32 GB, NVIDIA RTX 4070 SUPER 12 GB VRAM.
- Video đầu ra dài 61-70 giây.
- Sản lượng tính cả các biến thể của cùng một tin hoặc sự kiện.
- Máy render không có lịch hoạt động cố định.
- Thu thập và làm giàu tài nguyên phải hoạt động được khi máy render tắt.
- Tài nguyên gần lượt xử lý của khoảng năm video được giữ cục bộ.
- Video đầu ra được giữ cục bộ cho đến khi đồng bộ thành công lên Google Drive.
- Ngân sách mục tiêu của giai đoạn đầu dưới 50 USD mỗi tháng.

Kết quả đo không ghi đủ cấu hình, tập dữ liệu, thời gian chạy và phạm vi chi phí không được dùng để tuyên bố hệ thống đạt yêu cầu.

## 4. Cấp độ kiểm soát chất lượng

### 4.1. Hard gate

Vi phạm hard gate làm video hoặc công việc không được tính là hoàn thành:

- Video không phát được.
- Video ngắn hơn 61 giây hoặc dài hơn 70 giây.
- Thiếu video hook, âm thanh hook hoặc thumbnail câu chuyện trong hook.
- Nội dung/lời dẫn không phải tiếng Anh.
- Thiếu phụ đề tiếng Anh gắn vào video hoặc không có timing từng từ phục vụ karaoke (R03). Ngưỡng sai số chữ/timing định lượng còn mở, không tự thêm con số nghiệm thu.
- Video chưa đồng bộ thành công nhưng bản cục bộ đã bị xóa.
- Công việc sau gián đoạn bị chạy lại từ đầu dù đã có trạng thái hoàn thành hợp lệ.

### 4.2. Lỗi công việc

Lỗi công việc làm một video hoặc một công đoạn thất bại, nhưng không được làm dừng các công việc độc lập còn lại trong lô.

### 4.3. Cảnh báo

Cảnh báo không làm dừng công việc nhưng phải được ghi nhật ký và hiển thị để debug. Danh sách cảnh báo cụ thể sẽ được xác định trong thiết kế từng phân hệ.

## 5. Hiệu năng và sản lượng

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-PERF-001 | Sản lượng ổn định | Tối thiểu 100 video hợp lệ trong 12 giờ | ĐÃ XÁC NHẬN | Chạy một lô đại diện liên tục trong 12 giờ và đếm video qua hard gate |
| QR-PERF-002 | Cách tính sản lượng | Tính biến thể/góc kể hợp lệ đã sync; không tính video lỗi, chưa đạt điều kiện, chưa sync hoặc lần thử lại kỹ thuật | ĐÃ XÁC NHẬN; làm rõ R10/R17 | Đối chiếu job/output/sync và số lần ghi nhận hoàn thành |
| QR-PERF-003 | Tận dụng thời gian chờ | Có thể chuẩn bị tài nguyên của video tiếp theo trong lúc video hiện tại render | ĐÃ XÁC NHẬN | Quan sát timeline công việc trong lô |
| QR-PERF-004 | Giới hạn staging cục bộ | Duy trì tài nguyên gần lượt xử lý của khoảng năm video, không tải toàn bộ kho về máy | ĐÃ XÁC NHẬN | Theo dõi số nhóm tài nguyên cục bộ trong lô dài |
| QR-PERF-005 | Phản hồi thao tác UI thông thường | 95% thao tác theo dõi, lọc, chọn hoặc mở chi tiết phản hồi trong 2 giây | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Đo thời gian từ thao tác đến khi giao diện phản hồi hữu ích |
| QR-PERF-006 | Phản hồi lệnh bắt đầu/tạo lại | Xác nhận đã nhận lệnh trong 1 giây; công việc dài chạy độc lập sau đó | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Đo từ khi bấm nút đến khi trạng thái công việc thay đổi |
| QR-PERF-007 | Quy mô bảng dữ liệu đại diện | Chưa có số lượng hàng và cột mục tiêu | CHƯA QUYẾT ĐỊNH | Chốt sau khi ước lượng tốc độ tăng dữ liệu |
| QR-PERF-008 | Thời gian hoàn tất một vòng thu thập hằng ngày | Chưa có ngưỡng | CHƯA QUYẾT ĐỊNH | Chốt sau nghiên cứu số nguồn và giới hạn truy cập |

Mốc 100 video/12 giờ tương đương tốc độ trung bình ít nhất 8,33 video hợp lệ mỗi giờ. Đây là phép quy đổi của mục tiêu đã xác nhận, không phải yêu cầu mới về thời gian của từng video.

## 6. Độ ổn định và cô lập lỗi

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-REL-001 | Cô lập lỗi video | Một video lỗi không làm dừng lô hoặc chuyển video độc lập khác sang lỗi | ĐÃ XÁC NHẬN | Gây lỗi có kiểm soát cho một video giữa lô |
| QR-REL-002 | Cô lập lỗi nguồn | Một nguồn lỗi không làm dừng việc quét các nguồn còn lại | ĐÃ XÁC NHẬN | Mô phỏng một nguồn không truy cập được |
| QR-REL-003 | Nhật ký lỗi | 100% công việc được đánh dấu lỗi phải có thời gian, đối tượng liên quan và mô tả lỗi | ĐÃ XÁC NHẬN | Đối chiếu công việc lỗi với nhật ký |
| QR-REL-004 | Tiếp tục sau gián đoạn | Công việc đã hoàn thành không bị chạy lại; công việc dở dang tiếp tục từ trạng thái gần nhất còn hợp lệ | ĐÃ XÁC NHẬN | Dừng ứng dụng/máy ở nhiều công đoạn rồi khởi động lại |
| QR-REL-005 | Đồng bộ lỗi | Video cục bộ không bị xóa khi chưa xác nhận đồng bộ thành công | ĐÃ XÁC NHẬN | Ngắt kết nối trong khi đồng bộ |
| QR-REL-006 | Thư mục phiên rỗng | Không để lại thư mục phiên khi chưa có video hoàn thành | ĐÃ XÁC NHẬN | Mở/đóng ứng dụng mà không tạo video |
| QR-REL-007 | Tỷ lệ lô tự động không cần can thiệp | Ít nhất 95% video đủ đầu vào hoàn thành mà không cần thao tác thủ công sau khi bắt đầu lô | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Đo trên nhiều lô đại diện sau giai đoạn ổn định |
| QR-REL-008 | Lỗi không xác định | Không có lỗi làm biến mất công việc mà không để lại trạng thái hoặc nhật ký | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Đối chiếu tổng số công việc trước và sau lô |
| QR-REL-009 | Retry và timeout | Ngưỡng riêng theo từng phân hệ | CHƯA QUYẾT ĐỊNH | Quyết định sau nghiên cứu thực tế từng dịch vụ |

## 7. Khả năng sẵn sàng và phục hồi

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-AVL-001 | Thu thập khi máy render tắt | Lịch thu thập vẫn hoạt động khi desktop không trực tuyến | ĐÃ XÁC NHẬN | Tắt máy render qua một chu kỳ thu thập |
| QR-AVL-002 | Khôi phục khi desktop trở lại | Công việc mới xuất hiện trong hàng chờ và không yêu cầu quét lại toàn bộ nguồn | ĐÃ XÁC NHẬN | Kết nối lại sau một chu kỳ offline |
| QR-AVL-003 | Mức sẵn sàng của hoạt động thu thập | Ít nhất 99% số lần chạy theo lịch hợp lệ trong tháng được bắt đầu; nguồn không được chọn do đã đủ ngưỡng chủ đề không phải lượt bị mất | NGƯỠNG ĐÃ DUYỆT; làm rõ phạm vi theo R04/R23 | Đối chiếu lịch đủ điều kiện, số lần bắt đầu và lý do không mở rộng Tier; không dùng lý do đủ dữ liệu để che lỗi scheduler |
| QR-AVL-004 | Thời gian tiếp tục sau khi mở lại ứng dụng | Trong vòng 5 phút, hệ thống khôi phục trạng thái và có thể tiếp tục công việc | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Đo từ lúc mở ứng dụng đến lúc hàng chờ sẵn sàng |
| QR-AVL-005 | Mất dữ liệu chấp nhận được | Không cần cam kết khôi phục sau mất toàn bộ kho; sao lưu bổ sung có ưu tiên thấp | ĐÃ XÁC NHẬN | Kiểm tra phạm vi cam kết, không phải cam kết backup |
| QR-AVL-006 | Khả năng phục hồi dịch vụ AI | Phải có fallback nhưng thời gian chuyển đổi và mức chất lượng tối thiểu chưa chốt | CHƯA QUYẾT ĐỊNH | Nghiên cứu ở bước 07 và thiết kế sau khi được duyệt |

R18/R19: khi desktop tắt, tin/media/chỉ mục vẫn được chuẩn bị khi dịch vụ sẵn sàng; nếu AI lỗi thì chỉ phần cần AI được chờ phục hồi hoặc local khi desktop online. Phần không cần AI tiếp tục. Không tự thêm dịch vụ trả phí; không đòi hỏi dịch vụ đã hỏng vẫn hoàn thành làm giàu. Ngưỡng phục hồi và model cụ thể còn mở.

## 8. Toàn vẹn và chất lượng dữ liệu

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-DATA-001 | Truy vết nguồn | Mọi bài phải truy ngược được về nguồn và phiên bản nội dung đã dùng | ĐÃ XÁC NHẬN | Chọn mẫu video và lần ngược đến bài/phiên bản |
| QR-DATA-002 | Bảo toàn bài độc lập | Liên kết bài vào sự kiện không làm mất dữ liệu hoặc danh tính riêng của bài | ĐÃ XÁC NHẬN | Kiểm tra bài trước và sau liên kết |
| QR-DATA-003 | Cập nhật nguồn | Lần sản xuất sau dùng phiên bản mới; video cũ không tự thay đổi | ĐÃ XÁC NHẬN | Tạo bản sửa nguồn và so sánh hai lượt sản xuất |
| QR-DATA-004 | Gắn nhãn suy luận | 100% đoạn suy luận/sáng tạo phải phân biệt được với thông tin lấy từ nguồn | ĐÃ XÁC NHẬN | Rà soát các `ScriptSegment` của mẫu kịch bản |
| QR-DATA-005 | Khác góc trong cùng lượt | 100% nhóm 1-3 video của cùng lượt dùng các góc kể khác nhau | ĐÃ XÁC NHẬN | So sánh `StoryAngle` trong lượt |
| QR-DATA-006 | Khác biệt giữa các lượt | Video mới khác ít nhất một yếu tố được theo dõi và không hoàn toàn giống video cũ | ĐÃ XÁC NHẬN | So sánh dấu hiệu biến thể |
| QR-DATA-007 | Không mất dấu vết khi xóa staging | Xóa tệp cục bộ không làm mất nguồn, lịch sử công việc, kịch bản hoặc dấu hiệu biến thể | ĐÃ XÁC NHẬN | Kiểm tra dữ liệu sau dọn staging |
| QR-DATA-008 | Độ chính xác phân loại chủ đề | Ít nhất 90% mẫu được người dùng đánh giá là đúng hoặc chấp nhận được | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Lấy mẫu định kỳ và người dùng đánh giá |
| QR-DATA-009 | Độ chính xác liên kết sự kiện | Ít nhất 95% liên kết tự động trong mẫu không gộp nhầm hai sự kiện khác nhau | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Rà soát mẫu liên kết bài-sự kiện |
| QR-DATA-010 | Trùng bài | Cách đo và ngưỡng chưa quyết định | CHƯA QUYẾT ĐỊNH | Nghiên cứu dữ liệu nguồn thực tế |

## 9. Chất lượng lựa chọn nội dung và tài nguyên

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-CONT-001 | Phù hợp thị trường | Tin được chọn phải thuộc nhóm có khả năng thu hút khán giả Mỹ | ĐÃ XÁC NHẬN | Kiểm tra nhóm chủ đề và lý do lựa chọn |
| QR-CONT-002 | Thumbnail trong hook | Thumbnail phải liên quan trực tiếp đến nhân vật hoặc câu chuyện | ĐÃ XÁC NHẬN | Rà soát mẫu video |
| QR-CONT-003 | Hook minh họa | Hook có thể không thuộc sự kiện nhưng phải được dùng với vai trò minh họa | ĐÃ XÁC NHẬN | Đối chiếu kế hoạch nội dung và video |
| QR-CONT-004 | Mức phù hợp của tài nguyên tự chọn | Ít nhất 90% thumbnail, ảnh và clip trong mẫu được người dùng đánh giá là phù hợp | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Người dùng đánh giá mẫu theo thang đạt/không đạt |
| QR-CONT-005 | Mức phù hợp của hook | Ít nhất 90% tổ hợp video hook và audio hook trong mẫu phù hợp cảm xúc/ngữ cảnh | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Người dùng đánh giá mẫu |
| QR-CONT-006 | Chất lượng “hot/trending” | Chưa có thước đo vì sản phẩm không đo hiệu quả sau đăng | CHƯA QUYẾT ĐỊNH | Xác định proxy trong nghiên cứu thị trường |
| QR-CONT-007 | Khả năng viral | Không cam kết | ĐÃ XÁC NHẬN | Ghi rõ ngoài phạm vi cam kết |

## 10. Chất lượng xử lý ảnh nhạy cảm

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-SAFE-001 | Phạm vi | Chỉ xử lý ảnh; không xử lý clip lấy từ nguồn | ĐÃ XÁC NHẬN | Kiểm tra phạm vi công việc |
| QR-SAFE-002 | Khuôn mặt trẻ em | Ảnh đã nhận diện có trẻ em phải tạo được yêu cầu che mặt | ĐÃ XÁC NHẬN | Dùng bộ mẫu đã gắn nhãn |
| QR-SAFE-003 | Máu me | Ảnh đã nhận diện có máu me phải tạo được yêu cầu làm mờ hoặc đổi màu | ĐÃ XÁC NHẬN | Dùng bộ mẫu đã gắn nhãn |
| QR-SAFE-004 | Vũ khí | Ảnh đã nhận diện có vũ khí phải tạo được yêu cầu xử lý theo cấu hình | ĐÃ XÁC NHẬN | Dùng bộ mẫu đã gắn nhãn |
| QR-SAFE-005 | Tỷ lệ bỏ sót yếu tố nhạy cảm | Tỷ lệ phát hiện ít nhất 95% trên bộ mẫu đại diện | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | So sánh với bộ ảnh được người dùng gắn nhãn |
| QR-SAFE-006 | Lỗi ảnh riêng lẻ | Một ảnh xử lý lỗi không được làm dừng lô | ĐÃ XÁC NHẬN | Gây lỗi một ảnh giữa lô |

**Ngoại lệ sử dụng được xác nhận R12/R25:** ảnh nguyên gốc còn đọc được vẫn có thể được dùng khi nhận diện chưa chắc, kiểm tra lỗi hoặc xử lý thất bại. Phải ghi đúng trạng thái và lý do dùng nguyên gốc; không ghi thành xử lý thành công. Đây là chính sách sử dụng chấp nhận rủi ro, không hạ ngưỡng phát hiện 95%, không được loại mẫu lỗi khỏi mẫu đánh giá để nâng kết quả. Ảnh xác định cần xử lý vẫn phải được đưa qua công đoạn xử lý; clip không thuộc phạm vi.

## 11. Chất lượng video và âm thanh đầu ra

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-OUT-001 | Khả năng phát | 100% video được tính hoàn thành phải mở và phát được | ĐÃ XÁC NHẬN | Kiểm tra mọi video trước khi tính hoàn thành |
| QR-OUT-002 | Thời lượng | 100% video hợp lệ nằm trong 61-70 giây | ĐÃ XÁC NHẬN | Đo thời lượng đầu ra |
| QR-OUT-003 | Thành phần hook | 100% video hợp lệ có video hook, audio hook và thumbnail câu chuyện | ĐÃ XÁC NHẬN | Kiểm tra kế hoạch và đầu ra |
| QR-OUT-004 | Ngôn ngữ | Nội dung và lời dẫn của video hợp lệ phải bằng tiếng Anh | ĐÃ XÁC NHẬN | Kiểm tra kịch bản và lời đọc |
| QR-OUT-005 | Khả năng nghe lời dẫn | Lời dẫn phải nghe hiểu được khi có nhạc nền, hook audio và hiệu ứng | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Người dùng nghe mẫu trong điều kiện thông thường |
| QR-OUT-006 | Lỗi âm thanh rõ ràng | Không có đoạn im lặng ngoài chủ ý, âm thanh vỡ nghiêm trọng hoặc mất lời dẫn | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Kiểm tra tự động kết hợp nghe mẫu |
| QR-OUT-007 | Định dạng hình ảnh/video cụ thể | Độ phân giải, tỷ lệ khung hình, frame rate và định dạng tệp chưa được chốt | CHƯA QUYẾT ĐỊNH | Xác định ở đặc tả đầu ra trước kiến trúc render |
| QR-OUT-008 | Phụ đề karaoke | Bắt buộc tiếng Anh gắn vào video, timing từng từ khớp script/voice thực dùng; ngưỡng sai số còn mở | PHẠM VI ĐÃ XÁC NHẬN R03 | Kiểm tra phụ đề trên output thực, từ/thời gian/voice version; đo sai số theo bộ mẫu ở bước kiểm thử |

## 12. Trải nghiệm người dùng

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-UX-001 | Ngôn ngữ và dấu tiếng Việt | 100% nội dung UI do sản phẩm cung cấp hiển thị đúng tiếng Việt, không lỗi dấu hoặc ký tự | ĐÃ XÁC NHẬN | Rà soát toàn bộ màn hình và trạng thái |
| QR-UX-002 | Màn hình mục tiêu | Sử dụng được trên desktop từ 1080p trở lên | ĐÃ XÁC NHẬN | Kiểm tra các kích thước desktop mục tiêu |
| QR-UX-003 | Quan sát trạng thái | Nguồn, tin, tài nguyên, công đoạn, video và lô đều có trạng thái dễ nhận biết | ĐÃ XÁC NHẬN | Kiểm tra các trạng thái chính |
| QR-UX-004 | Chi tiết lỗi | Rê chuột vào mục lỗi hiển thị được lỗi cụ thể | ĐÃ XÁC NHẬN | Kiểm tra lỗi của từng loại công việc |
| QR-UX-005 | Thao tác debug | Mỗi công đoạn chính có thể chạy và tạo lại riêng từ giao diện | ĐÃ XÁC NHẬN | Thực hiện luồng debug đầu-cuối |
| QR-UX-006 | Giao diện dạng bảng | Phải có trải nghiệm quan sát/thao tác gần Google Sheets nhưng không phụ thuộc Google Sheets làm nơi lưu chính | ĐÃ XÁC NHẬN | Đánh giá luồng sử dụng bảng dữ liệu |
| QR-UX-007 | Không che khuất hoặc tràn nội dung | Không có nút, cột trạng thái hoặc thông báo quan trọng chồng lấn ở màn hình mục tiêu | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Kiểm tra trực quan trên các kích thước mục tiêu |
| QR-UX-008 | Khả năng thao tác bảng | R14 cho sửa metadata quản trị; không sửa bài gốc, script hoặc liên kết sự kiện. Chi tiết cột, lọc/nhóm/chọn nhiều còn mở | ĐÃ CHỐT MỘT PHẦN | Kiểm tra phạm vi dữ liệu sửa được và các ngưỡng UI đã duyệt |

## 13. Khả năng quan sát và debug

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-OBS-001 | Nhật ký theo phiên | Mỗi phiên mở ứng dụng có nhật ký riêng | ĐÃ XÁC NHẬN | Đóng/mở ứng dụng nhiều lần và đối chiếu log |
| QR-OBS-002 | Truy vết công việc | Từ video hoặc lỗi phải lần ngược được tới lô, công đoạn và nguồn liên quan | ĐÃ XÁC NHẬN | Thực hiện truy vết mẫu |
| QR-OBS-003 | Phân biệt cảnh báo và lỗi | Nhật ký phải phân biệt lỗi dừng công việc với cảnh báo không dừng | ĐÃ XÁC NHẬN | Kiểm tra các tình huống đại diện |
| QR-OBS-004 | Không có thất bại im lặng | Công việc không hoàn thành phải có trạng thái và nguyên nhân quan sát được | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Đối chiếu mọi công việc không hoàn thành |
| QR-OBS-005 | Chỉ số vận hành | Phải quan sát được thời gian, lỗi và trạng thái theo phiên; các chỉ số sâu hơn chưa chốt | ĐÃ XÁC NHẬN | Kiểm tra bảng phiên và nhật ký |
| QR-OBS-006 | Thời hạn lưu log | Chưa quyết định | CHƯA QUYẾT ĐỊNH | Chốt sau khi ước lượng dung lượng và nhu cầu debug |

## 14. Bảo mật

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-SEC-001 | Bí mật trên giao diện | Không hiển thị giá trị đầy đủ của khóa, token hoặc mật khẩu | ĐÃ XÁC NHẬN | Rà soát UI và thông báo lỗi |
| QR-SEC-002 | Bí mật trong nhật ký | Không có khóa, token hoặc mật khẩu trong log | ĐÃ XÁC NHẬN | Quét toàn bộ log của các tình huống lỗi |
| QR-SEC-003 | Thay đổi bí mật | Có thể thay thông tin xác thực mà không sửa mã nguồn | ĐÃ XÁC NHẬN | Thay tham chiếu bí mật và kiểm tra vận hành |
| QR-SEC-004 | Xác thực giao diện cục bộ | Không yêu cầu đăng nhập trong phiên bản một người dùng | ĐÃ XÁC NHẬN | Kiểm tra phạm vi truy cập cục bộ |
| QR-SEC-005 | Truy cập từ xa | Không nằm trong phạm vi hiện tại | ĐÃ XÁC NHẬN | Kiểm tra phạm vi sản phẩm |
| QR-SEC-006 | Truyền dữ liệu tới cloud | Người dùng cho phép gửi toàn bộ bài viết và media | ĐÃ XÁC NHẬN | Kiểm tra cấu hình quyền dữ liệu |
| QR-SEC-007 | Mã hóa dữ liệu khi truyền | Mọi kết nối mang bí mật hoặc dữ liệu người dùng phải được mã hóa | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Kiểm tra kênh truyền ở giai đoạn triển khai |
| QR-SEC-008 | Bảo vệ bí mật khi lưu | Bí mật phải được bảo vệ khỏi việc đọc trực tiếp từ bảng dữ liệu hoặc tệp log | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Kiểm tra quyền truy cập và dữ liệu lưu |
| QR-SEC-009 | Phân quyền tài khoản bên ngoài | Mỗi tài khoản chỉ được dùng cho vai trò đã được phép | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Đối chiếu vai trò và lịch sử sử dụng |

## 15. Chi phí và hiệu quả tài nguyên

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-COST-001 | Ngân sách giai đoạn đầu | Dưới 50 USD mỗi tháng | ĐÃ XÁC NHẬN | Tổng hợp chi phí thực tế trong tháng |
| QR-COST-002 | Chi phí có thể quan sát | Ghi nhận được chi phí theo dịch vụ, công đoạn hoặc lô khi dịch vụ cung cấp dữ liệu | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Đối chiếu báo cáo vận hành với hóa đơn |
| QR-COST-003 | Bảo vệ khỏi vượt ngân sách | Cảnh báo trước khi dự báo chi phí tháng vượt 80% ngân sách; không tự dừng nếu chưa được cấu hình | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Mô phỏng chi phí tích lũy |
| QR-COST-004 | Phạm vi ngân sách | Chỉ chi phí phát sinh thêm cho dự án: API, chạy nền, lưu trữ bổ sung; không tính Gemini/Drive đã có, điện, Internet, phần cứng | ĐÃ XÁC NHẬN R20 | Tách chi phí bổ sung khỏi tài nguyên đã sở hữu trong báo cáo |
| QR-COST-005 | Chi phí trên mỗi video | Chưa có ngưỡng độc lập | CHƯA QUYẾT ĐỊNH | Tính sau khi biết sản lượng thực tế và phạm vi chi phí |
| QR-COST-006 | Dung lượng desktop | Chỉ tải tài nguyên gần lượt render và xóa sau khi hoàn thành/đồng bộ | ĐÃ XÁC NHẬN | Theo dõi dung lượng trong lô dài |

## 16. Khả năng mở rộng và tăng trưởng dữ liệu

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-SCALE-001 | Thêm nguồn | Có thể thêm nguồn mới mà không làm mất hoặc phải tạo lại dữ liệu nguồn cũ | ĐÃ XÁC NHẬN | Thêm nguồn vào kho đang có dữ liệu |
| QR-SCALE-002 | Thêm chủ đề | Có thể thêm nhóm chủ đề mới mà không làm hỏng phân loại cũ | ĐÃ XÁC NHẬN | Thêm chủ đề và kiểm tra dữ liệu hiện có |
| QR-SCALE-003 | Kho sự kiện dài hạn | Dữ liệu cũ vẫn tìm và tái khai thác được khi kho tăng lên | ĐÃ XÁC NHẬN | Kiểm tra truy xuất trên tập dữ liệu đại diện |
| QR-SCALE-004 | Tăng tài nguyên xử lý | Có thể tăng năng lực xử lý/lưu trữ mà không thay thế toàn bộ sản phẩm | ĐÃ XÁC NHẬN | Đánh giá kiến trúc ở bước sau |
| QR-SCALE-005 | Chuẩn bị SaaS | Có thể phát triển thành SaaS nhưng phạm vi chất lượng cần chuẩn bị ngay chưa được chốt | CHƯA QUYẾT ĐỊNH | Làm rõ trước thiết kế kiến trúc |
| QR-SCALE-006 | Quy mô kiểm thử dữ liệu | Số nguồn, bài, sự kiện, tài nguyên và video dùng làm mốc chưa được chốt | CHƯA QUYẾT ĐỊNH | Ước lượng sau bước nghiên cứu nguồn |

## 17. Khả năng bảo trì và thay đổi

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-MNT-001 | Vòng đời nhiều năm | Thay đổi một nguồn, preset hoặc dịch vụ bên ngoài không buộc thay thế toàn bộ hệ thống | ĐÃ XÁC NHẬN | Đánh giá ở giai đoạn kiến trúc và kiểm thử thay đổi |
| QR-MNT-002 | Kiểm thử từng phân hệ | Mỗi phân hệ phải có khả năng được kiểm tra độc lập trước khi nối vào quy trình chung | ĐÃ XÁC NHẬN | Kiểm tra kế hoạch kiểm thử ở bước 12 |
| QR-MNT-003 | Phê duyệt theo phân hệ | Chỉ chuyển sang phân hệ tiếp theo sau khi người dùng xác nhận phân hệ hiện tại | ĐÃ XÁC NHẬN | Đối chiếu lộ trình và biên bản phê duyệt |
| QR-MNT-004 | Thay đổi cấu hình | Thay cấu hình cho lô mới không làm thay đổi lịch sử video đã hoàn thành | ĐÃ XÁC NHẬN | Thay cấu hình và kiểm tra đầu ra cũ |
| QR-MNT-005 | Phiên bản dữ liệu và preset | Thay đổi phải truy ra được phiên bản đã dùng cho video cũ | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Lần ngược từ video tới cấu hình/preset |
| QR-MNT-006 | Thay thế thành phần AI | Có thể dùng fallback mà không mất hàng chờ và lịch sử công việc | ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT | Mô phỏng thành phần chính không sẵn sàng |
| QR-MNT-007 | Mức dễ bảo trì định lượng | Chưa có ngưỡng về thời gian thêm nguồn, chủ đề, preset hoặc thay dịch vụ | CHƯA QUYẾT ĐỊNH | Chốt sau khi phân hệ và giao tiếp được xác định |

## 18. Tính tương thích và ngôn ngữ

| Mã | Yêu cầu | Mục tiêu chất lượng | Trạng thái | Cách đánh giá |
|---|---|---|---|---|
| QR-COMP-001 | Máy render mục tiêu | Hoạt động trên cấu hình phần cứng đã xác nhận | ĐÃ XÁC NHẬN | Kiểm thử trực tiếp trên máy mục tiêu |
| QR-COMP-002 | Màn hình | Giao diện dùng được từ 1080p trở lên | ĐÃ XÁC NHẬN | Kiểm thử nhiều kích thước desktop |
| QR-COMP-003 | Tiếng Việt | Tài liệu và UI dùng UTF-8, hiển thị đúng dấu tiếng Việt | ĐÃ XÁC NHẬN | Kiểm tra bộ ký tự tiếng Việt đầy đủ |
| QR-COMP-004 | Tiếng Anh đầu ra | Kịch bản, lời đọc, tiêu đề và hashtag đầu ra dùng tiếng Anh | ĐÃ XÁC NHẬN | Kiểm tra mẫu đầu ra |
| QR-COMP-005 | Nơi lưu trữ | Tên tệp và thư mục phải hợp lệ trên máy render và nơi đồng bộ | ĐÃ XÁC NHẬN | Kiểm tra tên có hashtag, ký tự đặc biệt và độ dài biên |
| QR-COMP-006 | Google Sheets | Trải nghiệm dạng bảng không được buộc dữ liệu chính phụ thuộc Google Sheets | ĐÃ XÁC NHẬN | Đánh giá kiến trúc ở bước 10 |

## 19. Ma trận ưu tiên chất lượng

Khi hai mục tiêu xung đột, thứ tự ưu tiên hiện tại là:

1. Không mất video cục bộ trước khi đồng bộ thành công.
2. Không làm dừng cả lô vì lỗi của một công việc độc lập.
3. Có thể tiếp tục sau gián đoạn mà không chạy lại từ đầu.
4. Video qua hard gate và phát được.
5. Tối ưu sản lượng hướng tới 100 video trong 12 giờ.
6. Giữ chi phí giai đoạn đầu dưới 50 USD mỗi tháng.
7. Tăng mức tự động và giảm nhu cầu can thiệp thủ công.
8. Cải thiện độ phù hợp nội dung, tài nguyên và trải nghiệm giao diện.

Thứ tự này đã được người dùng phê duyệt cùng toàn bộ tài liệu ngày 12-09-2026.

## 20. Các đề xuất đã được người dùng phê duyệt

- **QUALITY-PROPOSED-001:** 95% thao tác UI thông thường phản hồi trong 2 giây.
- **QUALITY-PROPOSED-002:** Lệnh bắt đầu hoặc tạo lại được xác nhận trong 1 giây.
- **QUALITY-PROPOSED-003:** Ít nhất 95% video đủ đầu vào hoàn thành tự động sau khi hệ thống ổn định.
- **QUALITY-PROPOSED-004:** Không có công việc biến mất mà không để lại trạng thái hoặc log.
- **QUALITY-PROPOSED-005:** Ít nhất 99% lượt thu thập theo lịch được bắt đầu trong tháng.
- **QUALITY-PROPOSED-006:** Hàng chờ sẵn sàng tiếp tục trong 5 phút sau khi mở lại ứng dụng.
- **QUALITY-PROPOSED-007:** Ít nhất 90% phân loại chủ đề trong mẫu được người dùng chấp nhận.
- **QUALITY-PROPOSED-008:** Ít nhất 95% liên kết sự kiện trong mẫu không gộp nhầm.
- **QUALITY-PROPOSED-009:** Ít nhất 90% tài nguyên và tổ hợp hook trong mẫu được người dùng đánh giá phù hợp.
- **QUALITY-PROPOSED-010:** Phát hiện ít nhất 95% yếu tố ảnh nhạy cảm trong bộ mẫu đại diện.
- **QUALITY-PROPOSED-011:** Lời dẫn nghe hiểu được và không có lỗi âm thanh nghiêm trọng.
- **QUALITY-PROPOSED-012:** Không có nội dung quan trọng chồng lấn ở màn hình desktop mục tiêu.
- **QUALITY-PROPOSED-013:** Mã hóa dữ liệu khi truyền và bảo vệ bí mật khi lưu.
- **QUALITY-PROPOSED-014:** Theo dõi chi phí và cảnh báo khi dự báo đạt 80% ngân sách tháng.
- **QUALITY-PROPOSED-015:** Lưu phiên bản cấu hình và preset đã dùng cho video cũ.
- **QUALITY-PROPOSED-016:** Fallback AI không làm mất hàng chờ hoặc lịch sử công việc.

Người dùng đã phê duyệt toàn bộ các mục trên ngày 12-09-2026. Các mã `QUALITY-PROPOSED-*` được giữ nguyên để bảo toàn khả năng truy vết lịch sử, nhưng nội dung của chúng hiện là yêu cầu chính thức.

## 21. Các vấn đề chất lượng CHƯA QUYẾT ĐỊNH

- **QUALITY-OPEN-001:** Quy mô hàng/cột mục tiêu cho giao diện dạng bảng.
- **QUALITY-OPEN-002:** Thời gian tối đa cho một vòng thu thập hằng ngày.
- **QUALITY-OPEN-003:** Retry và timeout theo từng phân hệ.
- **QUALITY-OPEN-004 - CÒN MỘT PHẦN:** R19 chốt hành vi chờ khi desktop tắt và AI lỗi; thời gian/ngưỡng theo vai trò còn mở.
- **QUALITY-OPEN-005:** Cách đo tin “hot/trending” khi không thu thập số liệu sau đăng.
- **QUALITY-OPEN-006:** Độ phân giải, tỷ lệ khung hình, frame rate và định dạng video đầu ra.
- **QUALITY-OPEN-007 - CÒN MỘT PHẦN:** R03 chốt bắt buộc phụ đề karaoke từng từ; còn độ chính xác chữ/timing và tiêu chí đo.
- **QUALITY-OPEN-008 - CÒN MỘT PHẦN:** R14 chốt sửa metadata quản trị; còn chi tiết thao tác và tập dữ liệu đo hiệu năng.
- **QUALITY-OPEN-009:** Thời hạn lưu nhật ký.
- **QUALITY-OPEN-010 - ĐÃ ĐÓNG:** Phạm vi chi phí theo R20 và QR-COST-004.
- **QUALITY-OPEN-011:** Quy mô dữ liệu dùng làm mốc kiểm thử tăng trưởng.
- **QUALITY-OPEN-012 - CÒN MỘT PHẦN:** ADR-0012 chọn workspace boundary tối thiểu; mức cách ly, SLA và phép đo SaaS nhiều khách vẫn chưa chốt, không thuộc v1.
- **QUALITY-OPEN-013:** Thời gian tối đa để thêm nguồn, chủ đề, preset hoặc thay dịch vụ.
- **QUALITY-OPEN-014:** Múi giờ chuẩn cho lịch chạy, log và tên thư mục.
- **QUALITY-OPEN-015 - ĐÃ CHỐT MỨC CAM KẾT:** Theo charter và QR-AVL-005, sao lưu bổ sung ưu tiên thấp, không cam kết khôi phục khi mất toàn kho. Phương án backup cụ thể còn để kiến trúc; tuyệt đối không diễn giải thành được xóa output chưa sync.

## 22. Giả định

**Không có GIẢ ĐỊNH nào được dùng làm yêu cầu chất lượng chính thức trong tài liệu này.**

Các con số từng do kỹ sư trưởng đề xuất đã được người dùng phê duyệt và được đánh dấu `ĐÃ PHÊ DUYỆT TỪ ĐỀ XUẤT`. Những mục thiếu dữ liệu vẫn được giữ ở trạng thái `CHƯA QUYẾT ĐỊNH`.

## 23. Kết quả phê duyệt

Ngày 12-09-2026, người dùng đã:

1. Phê duyệt toàn bộ các hard gate và yêu cầu `ĐÃ XÁC NHẬN`.
2. Phê duyệt toàn bộ các mục `QUALITY-PROPOSED-*` mà không sửa ngưỡng.
3. Cho phép các mục `QUALITY-OPEN-*` tiếp tục chờ nghiên cứu hoặc giai đoạn thiết kế phù hợp.

Bước tiếp theo là **07 - Nghiên cứu công nghệ và dự án có sẵn**.
