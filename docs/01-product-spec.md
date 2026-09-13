# AI Auto Video Creator - Đặc tả sản phẩm

**Giai đoạn:** 04 - Viết Đặc tả sản phẩm  
**Ngày lập:** 12-09-2026  
**Trạng thái:** Đã được người dùng phê duyệt; cập nhật yêu cầu theo R01-R25 trước bước 09  
**Tài liệu nguồn:** [00-project-charter.md](./00-project-charter.md)

## 1. Mục đích

Tài liệu này mô tả AI Auto Video Creator phải có khả năng làm gì và người dùng quan sát được hành vi nào. Tài liệu không mô tả cách xây dựng, kiến trúc, công nghệ, schema dữ liệu, API, thư viện hoặc kế hoạch triển khai.

Các từ khóa trong tài liệu:

- **Phải:** yêu cầu bắt buộc để sản phẩm được chấp nhận.
- **Nên:** yêu cầu quan trọng nhưng có thể hoàn thiện theo giai đoạn.
- **Có thể cấu hình:** giá trị có thể thay đổi mà không làm thay đổi mục đích của sản phẩm.
- **CHƯA QUYẾT ĐỊNH:** không được tự suy diễn thành yêu cầu chính thức.

Quyết định làm rõ R01-R25 được ghi tại [07-data-flow.md](./07-data-flow.md), mục 2. Mã yêu cầu cũ được giữ để truy vết; yêu cầu bị thay thế được đánh dấu, không tái sử dụng mã cho chức năng khác.

## 2. Mô tả sản phẩm

AI Auto Video Creator là công cụ dành cho một người vận hành, thực hiện chuỗi công việc từ thu thập tin, phân loại, làm giàu tài nguyên, tạo kịch bản, chọn hook, chọn cách trình bày, tạo âm thanh, render, kiểm tra khả năng phát và lưu video hoàn chỉnh.

Sản phẩm phục vụ việc tạo số lượng lớn video ngắn bằng tiếng Anh cho khán giả Mỹ. Giao diện điều khiển bằng tiếng Việt, chạy trên desktop và ưu tiên khả năng quan sát, chạy lại từng công đoạn trong giai đoạn debug trước khi vận hành tự động hàng loạt.

## 3. Vai trò sử dụng

### 3.1. Người vận hành

Người vận hành là người dùng duy nhất trong phiên bản đầu và phải có khả năng:

- Quản lý nguồn tin và kho hook.
- Theo dõi tin, sự kiện, tài nguyên và công việc sản xuất.
- Chạy riêng từng công đoạn.
- Tạo lại kết quả của một công đoạn.
- Chọn cấu hình chung cho một lô.
- Bắt đầu hoặc tiếp tục xử lý tự động.
- Quan sát trạng thái hoàn thành và lỗi.

### 3.2. Chế độ tự động

Chế độ tự động không phải người dùng độc lập. Đây là chế độ được người vận hành khởi chạy để hệ thống tự chọn tin, góc kể, tài nguyên, hook, âm thanh và preset trong giới hạn cấu hình của lô.

## 4. Luồng sử dụng chính

### 4.1. Luồng chuẩn bị nguồn

1. Hệ thống duy trì danh sách nguồn do hệ thống tìm thấy hoặc người dùng bổ sung.
2. Nguồn được phân nhóm và xếp `Tier 1/2/3`.
3. Hệ thống quét theo Tier và ngưỡng tin mới không trùng mỗi ngày cho từng chủ đề; nguồn ở Tier sau có thể không được quét khi đã đủ dữ liệu.
4. Tin mới được phân loại theo chủ đề và đánh giá mức phù hợp với khán giả Mỹ.
5. Văn bản, ảnh và clip có sẵn trong nguồn được ghi nhận để dùng cho các bước tiếp theo.

### 4.2. Luồng debug thủ công

1. Người dùng chọn một tin hoặc sự kiện.
2. Người dùng chạy riêng công đoạn cần kiểm tra.
3. Giao diện hiển thị trạng thái và kết quả của công đoạn.
4. Người dùng có thể yêu cầu tạo lại kết quả.
5. Người dùng tiếp tục công đoạn kế tiếp hoặc dừng để kiểm tra lỗi.

### 4.3. Luồng sản xuất hàng loạt

1. Người dùng chọn các thông số chung của lô.
2. Người dùng khởi chạy chế độ tự động.
3. Hệ thống lần lượt chọn tin, tạo 1-3 phiên bản cho mỗi lượt, chuẩn bị tài nguyên và render.
4. Một video lỗi được đánh dấu và bỏ qua mà không làm dừng lô.
5. Video hợp lệ được đồng bộ lên kho lưu trữ dài hạn.
6. Sau khi xác nhận đồng bộ thành công, dữ liệu cục bộ của video được xóa.
7. Lô tiếp tục đến số video hoàn thành mục tiêu do người dùng đặt, bị người dùng dừng hoặc không còn công việc đủ điều kiện. Việc đang chờ AI/mạng/desktop phải được phân biệt với việc đã hết ứng viên có thể khai thác.

### 4.4. Luồng tiếp tục sau gián đoạn

1. Trạng thái tiến độ gần nhất phải được giữ khi máy render tắt hoặc ứng dụng dừng ngoài ý muốn.
2. Hoạt động thu thập và làm giàu trên môi trường luôn hoạt động vẫn tiếp tục khi máy render tắt.
3. Khi máy render hoạt động lại, hệ thống tiếp tục từ công việc chưa hoàn thành gần nhất.
4. Hệ thống không được tự quay về xử lý lại từ tin đầu tiên.

## 5. Yêu cầu chức năng

### 5.1. Quản lý nguồn tin

- **FR-SRC-001:** Sản phẩm phải duy trì được danh sách các nguồn tin cần quét.
- **FR-SRC-002:** Người dùng phải có thể bổ sung nguồn thủ công từ giao diện.
- **FR-SRC-003 - ĐÃ BỎ theo R15:** Không còn yêu cầu tệp văn bản riêng để quản lý nguồn; thao tác trực tiếp trên UI.
- **FR-SRC-004:** Sản phẩm phải có khả năng tự phát hiện nguồn mới mà không yêu cầu người dùng duyệt từng nguồn.
- **FR-SRC-005:** Mỗi nguồn phải được gắn một mức ưu tiên `Tier 1`, `Tier 2` hoặc `Tier 3`.
- **FR-SRC-006:** Khi cần thu thập thêm dữ liệu, hệ thống phải ưu tiên nguồn ở Tier cao trước rồi mới mở rộng sang Tier tiếp theo.
- **FR-SRC-007:** Giao diện phải cho phép người dùng xem và quản lý danh sách nguồn.
- **FR-SRC-008:** Việc một nguồn lỗi không được làm dừng quá trình quét các nguồn còn lại.
- **FR-SRC-009:** Trạng thái lỗi nguồn phải được ghi vào nhật ký của phiên thu thập tương ứng.
- **FR-SRC-010:** UI phải cho thêm, xóa, khôi phục nguồn và sửa metadata quản trị. Xóa nguồn ngừng thu thập, ngăn tự thêm lại tới khi người dùng khôi phục; không cấm tái dùng tin/media đã lưu (R14, R15, R24).
- **FR-SRC-011:** Hệ thống phải dùng lượng tin mới không trùng theo từng chủ đề và ngưỡng ngày để quyết định mở rộng Tier. Con số ngưỡng và quy tắc nguồn đa chủ đề chưa chốt (R04, R23).

### 5.2. Thu thập tin

- **FR-COL-001:** Sản phẩm quét định kỳ theo Tier, mỗi nguồn được chọn tối đa một lượt định kỳ/ngày; có thể không quét nguồn đang bật nếu đã đạt ngưỡng tin mới của chủ đề. Retry phục hồi lượt lỗi phải được phân biệt với lượt định kỳ mới (R04, R23).
- **FR-COL-002:** Quá trình thu thập phải có khả năng hoạt động khi máy render cá nhân đang tắt.
- **FR-COL-003:** Sản phẩm phải có khả năng thu thập tin toàn cầu có tiềm năng thu hút khán giả Mỹ.
- **FR-COL-004:** Khi nguồn cung cấp văn bản, ảnh hoặc clip liên quan, hệ thống phải ghi nhận các thành phần hiện có.
- **FR-COL-005:** Khi bài có clip phù hợp, hệ thống phải ưu tiên đưa clip cùng ảnh vào tập tài nguyên ứng viên sau phần hook.
- **FR-COL-006:** Với người nổi tiếng, sản phẩm phải có khả năng ghi nhận clip ngắn từ trang cá nhân chính thức như nguồn tài nguyên ứng viên.
- **FR-COL-007:** Một lỗi thu thập phải có thông tin đủ cụ thể để người dùng biết nguồn nào, thời điểm nào và công việc nào bị lỗi.
- **FR-COL-008:** Khi nguồn sửa bài, những lần sản xuất sau phải sử dụng nội dung mới nhất đã thu thập.
- **FR-COL-009:** Video đã hoàn thành trước khi nguồn sửa không phải tự động tạo lại.
- **FR-COL-010:** Khi thiếu tài nguyên, được tìm và tải bổ sung ngay theo nhu cầu video; không tính đây là lượt quét định kỳ. Nguồn người dùng đã loại bỏ không được tự kích hoạt lại (R05, R24).
- **FR-COL-011:** Khi desktop tắt, vẫn thu thập/làm giàu tin, media và chỉ mục trên cloud. Tạo script, kế hoạch và voice chờ desktop hoạt động (R18).
- **FR-COL-012:** Kiểm tra thu thập chỉ xác nhận dữ liệu đủ và có nguồn truy vết, không bắt buộc kiểm chứng sự thật đa nguồn (R01).

### 5.3. Phân loại tin và nguồn

- **FR-CLS-001:** Mỗi tin phải được gắn ít nhất một nhóm chủ đề.
- **FR-CLS-002:** Một tin phải có thể thuộc nhiều nhóm chủ đề khi nội dung giao nhau.
- **FR-CLS-003:** Các nhóm ban đầu phải bao gồm người nổi tiếng, tin gây sốc, chính trị đang thịnh hành, tội ác, tai nạn, tội phạm, cảnh sát, bản án và hồ sơ nổi bật.
- **FR-CLS-004:** Sản phẩm phải cho phép bổ sung nhóm chủ đề mới sau này.
- **FR-CLS-005:** Các nhóm bổ sung do nghiên cứu đề xuất phải chờ người dùng phê duyệt trước khi trở thành nhóm chính thức.
- **FR-CLS-006:** Hệ thống phải có khả năng phân biệt tin đang thịnh hành với chủ đề có sức hút lâu dài.
- **FR-CLS-007:** Kết quả phân loại phải hỗ trợ việc tìm tin và chọn tài nguyên phù hợp ở các bước sau.

### 5.4. Quản lý bài viết và sự kiện

- **FR-EVT-001:** Mỗi bài không trùng được chấp nhận vào kho có thể tồn tại như tin độc lập. Bài đăng lại trùng nội dung không tạo thêm tin/kịch bản độc lập; giữ tin đại diện và dấu vết xuất xứ cần thiết (R07).
- **FR-EVT-002:** Nhiều bài nói về cùng một vụ việc phải có khả năng được liên kết thành một sự kiện chung.
- **FR-EVT-003:** Việc liên kết bài không được làm mất nguồn hoặc nội dung riêng của từng bài.
- **FR-EVT-004:** Một sự kiện chung phải có khả năng tạo kịch bản tổng hợp từ nhiều bài.
- **FR-EVT-005:** Cùng một sự kiện phải có thể tạo các góc kể độc lập dựa trên từng bài hoặc toàn bộ nhóm bài.
- **FR-EVT-006:** Chỉ diễn biến mới có tình tiết mới tạo cập nhật đủ điều kiện kể “từ lúc đó đến nay”. Thêm nguồn hoặc bài đăng lại không tự kích hoạt cập nhật này; tái khai thác thông thường vẫn theo FR-BAT-008 (R07).
- **FR-EVT-007:** Sản phẩm phải ghi nhớ các lần khai thác trước để tránh dùng lại kịch bản gần nhất.
- **FR-EVT-008:** Khi liên kết sự kiện chưa đủ chắc, giữ bài riêng và vẫn cho sản xuất theo từng bài; không bắt người dùng duyệt liên kết và không tổng hợp các bài chưa đủ chắc (R06).
- **FR-EVT-009:** Khi nội dung các nguồn mâu thuẫn, dùng phiên bản từ nguồn được ưu tiên theo Tier. Giữ xuất xứ và không coi lựa chọn ưu tiên là kết quả kiểm chứng sự thật; cách phân xử cùng Tier chờ nghiên cứu (R08).
- **FR-EVT-010:** Job đã bắt đầu tạo script giữ tập phiên bản nguồn tới khi hoàn tất. Cập nhật nguồn chỉ tác động job chưa bắt đầu tạo script và lần sản xuất sau (R09).

### 5.5. Làm giàu tài nguyên

- **FR-AST-001:** Sản phẩm phải tạo được tập tài nguyên ứng viên cho từng tin hoặc sự kiện.
- **FR-AST-002:** Tập tài nguyên phải có thể chứa ảnh từ bài gốc, ảnh liên quan, clip trong bài và clip từ nguồn chính thức liên quan.
- **FR-AST-003:** Mỗi tài nguyên phải có đủ thông tin mô tả để AI có thể đánh giá mức phù hợp với câu chuyện.
- **FR-AST-004:** AI phải có khả năng chọn tài nguyên theo chủ đề, nhân vật, sự kiện, cảm xúc hoặc mục đích của đoạn kể.
- **FR-AST-005:** Hệ thống phải có khả năng thay đổi lựa chọn và thứ tự ảnh/clip giữa các lần tạo.
- **FR-AST-006:** Tài nguyên dài hạn phải được lưu trên kho cloud theo loại dữ liệu.
- **FR-AST-007:** Máy render chỉ giữ tập tài nguyên cục bộ cần thiết cho khoảng năm video gần lượt xử lý.
- **FR-AST-008:** Trong lúc một video đang render, hệ thống phải có khả năng chuẩn bị tài nguyên cho video tiếp theo.
- **FR-AST-009:** Bài trùng vẫn có thể bổ sung ảnh/clip mới phù hợp cho tin đại diện; phải ghi xuất xứ, không biến media mới thành tình tiết mới của sự kiện (R22).

### 5.6. Kho hook

- **FR-HOOK-001:** Sản phẩm phải có kho video hook do người dùng bổ sung thủ công.
- **FR-HOOK-002:** Sản phẩm không phải làm mờ lại video hook đã nhập.
- **FR-HOOK-003:** Video hook và âm thanh hook phải được quản lý như hai kho riêng.
- **FR-HOOK-004:** Mỗi hook phải có thông tin chỉ mục để AI đánh giá mức phù hợp với câu chuyện.
- **FR-HOOK-005:** AI phải chọn được một video hook và một âm thanh hook phù hợp cho mỗi video.
- **FR-HOOK-006:** Hook có thể không thuộc sự kiện thật nhưng chỉ được dùng với vai trò minh họa.
- **FR-HOOK-007:** Phần hook của mỗi video phải có thumbnail liên quan trực tiếp đến câu chuyện.
- **FR-HOOK-008:** Nếu không tìm được hook đủ điều kiện, công việc phải được đánh dấu rõ thay vì âm thầm render thiếu hook.
- **FR-HOOK-009:** Người dùng phải có khả năng xem và quản lý các mục trong kho hook từ giao diện.
- **FR-HOOK-010:** Người dùng cung cấp audio hook, cũng như video hook; hệ thống không tự bổ sung nghĩa vụ tạo/cào audio hook (R11).

### 5.7. Tạo kịch bản và góc kể

- **FR-SCR-001:** Kịch bản đầu ra phải bằng tiếng Anh và hướng đến khán giả Mỹ.
- **FR-SCR-002:** Kịch bản phải được tạo với thời lượng mục tiêu để video hoàn chỉnh nằm trong khoảng 61-70 giây.
- **FR-SCR-003:** Mỗi lượt xử lý một tin phải tạo từ 1 đến 3 video trước khi chuyển sang tin tiếp theo.
- **FR-SCR-004:** Các video trong cùng lượt phải khai thác các góc kể khác nhau.
- **FR-SCR-005:** Không đặt giới hạn cố định cho tổng số lần một sự kiện có thể được khai thác.
- **FR-SCR-006:** Sau khi đi hết hàng chờ, sự kiện cũ có thể được chọn lại theo quy tắc khác biệt giữa các lượt; không bắt buộc lượt sau phải có góc hoàn toàn mới. Không dùng nguyên trạng script gần nhất.
- **FR-SCR-007:** Kịch bản gần nhất của sự kiện không được dùng lại nguyên trạng.
- **FR-SCR-008:** Những câu được trình bày như sự thật phải dựa trên dữ liệu đã thu thập.
- **FR-SCR-009:** AI có thể suy luận hoặc sáng tạo thêm góc diễn giải, nhưng nội dung đó phải được thể hiện rõ là suy luận.
- **FR-SCR-010:** AI không được biến suy luận thành một khẳng định đã được xác nhận.
- **FR-SCR-011:** Kịch bản phải có hook nội dung, nhịp kể và điểm nhấn nhằm duy trì sự chú ý.
- **FR-SCR-012:** Người dùng phải có thể chọn một phong cách kịch bản từ danh sách khi debug.
- **FR-SCR-013:** Chế độ mặc định phải cho phép AI tự chọn phong cách.
- **FR-SCR-014:** Người dùng phải có thể yêu cầu tạo lại kịch bản mà không cần chỉnh sửa trực tiếp.

### 5.8. Đa dạng hóa và chống lặp

- **FR-VAR-001:** Sản phẩm phải lưu đủ lịch sử để so sánh lần tạo mới với các lần tạo trước của cùng một tin hoặc sự kiện.
- **FR-VAR-002:** Sản phẩm phải có khả năng thay đổi góc kể, kịch bản, giọng đọc, hook, âm thanh hook, nhạc nền, hiệu ứng, thứ tự và lựa chọn ảnh/clip.
- **FR-VAR-003:** Trong cùng một lượt, 1-3 video của một tin phải khác nhau về góc kể.
- **FR-VAR-004:** Giữa các lượt khai thác sau, video mới phải khác video cũ ít nhất một trong các yếu tố được theo dõi.
- **FR-VAR-005:** Video mới không được hoàn toàn giống một video cũ của cùng tin hoặc sự kiện.
- **FR-VAR-006:** Khi một phương án hoàn toàn giống video cũ, hệ thống phải tạo phương án khác hoặc đánh dấu không thể tạo biến thể mới.

### 5.9. Preset và chỉ dẫn trình bày

- **FR-PRS-001:** Sản phẩm phải cung cấp đúng năm nhóm preset trình bày được chuẩn bị bài bản.
- **FR-PRS-002:** Mỗi video phải sử dụng một trong năm preset.
- **FR-PRS-003:** Chế độ tự động phải cho phép AI chọn preset phù hợp với câu chuyện.
- **FR-PRS-004:** Người dùng phải có thể chọn preset từ danh sách khi debug.
- **FR-PRS-005:** AI không được tạo một hệ layout hoàn toàn mới ngoài năm preset đã được phê duyệt.
- **FR-PRS-006:** Chỉ dẫn sản xuất phải xác định nội dung nào xuất hiện ở từng đoạn, tài nguyên nào được dùng và điểm nhấn nào được áp dụng.
- **FR-PRS-007:** Với clip người nổi tiếng, chỉ dẫn có thể yêu cầu thumbnail, biểu tượng, mũi tên, dấu hỏi, dấu cảm thán hoặc lớp nhấn mạnh liên quan đến câu chuyện.

### 5.10. Nội dung nhạy cảm

- **FR-SEN-001:** Sản phẩm phải nhận biết ảnh có khuôn mặt trẻ em, máu me hoặc vũ khí.
- **FR-SEN-002:** Ảnh có khuôn mặt trẻ em phải được đánh dấu để che mặt.
- **FR-SEN-003:** Ảnh có máu me phải có khả năng được làm mờ hoặc thay đổi màu sắc.
- **FR-SEN-004:** Ảnh có vũ khí phải có khả năng được xử lý theo quy tắc nhạy cảm đã cấu hình.
- **FR-SEN-005:** Xử lý ảnh nhạy cảm không được làm mất khả năng tiếp tục sản xuất cả lô nếu một ảnh riêng lẻ bị lỗi.
- **FR-SEN-006:** Ảnh nhận diện chưa chắc, kiểm tra lỗi hoặc xử lý thất bại vẫn được dùng nguyên gốc nếu đọc được, theo chấp nhận rủi ro R12/R25. Phải ghi đúng trạng thái chưa chắc/lỗi và lý do dùng nguyên gốc; không đánh dấu đã an toàn hoặc đã xử lý thành công. Ảnh không đọc được vẫn là lỗi đầu vào; ảnh đã nhận diện cần xử lý vẫn phải được đưa qua bước xử lý.

### 5.11. Tạo âm thanh

- **FR-AUD-001:** Mỗi video phải có lời đọc phù hợp với kịch bản.
- **FR-AUD-002:** Sản phẩm phải có khả năng thay đổi giọng đọc giữa các biến thể.
- **FR-AUD-003:** Mỗi video phải có âm thanh hook phù hợp với video hook và nội dung.
- **FR-AUD-004:** AI phải có khả năng chọn nhạc nền theo cảm xúc và nhịp kể.
- **FR-AUD-005:** Chỉ dẫn âm thanh có thể bao gồm hiệu ứng ngắn như nhịp tim, nhịp đập hoặc âm thanh đơn phục vụ điểm nhấn.
- **FR-AUD-006:** Âm thanh hook, lời đọc, nhạc nền và hiệu ứng phải cùng tồn tại mà không làm video mất khả năng nghe hiểu lời dẫn.
- **FR-AUD-007:** Hệ thống phải tự tìm/thu thập nhạc nền và SFX, ghi xuất xứ và chỉ mục để lựa chọn theo ngữ cảnh; không tự bổ sung chức năng AI sáng tác âm thanh (R11).

### 5.12. Điều khiển theo công đoạn

- **FR-CTL-001:** Mỗi công đoạn chính phải có thao tác khởi chạy thủ công riêng trên giao diện.
- **FR-CTL-002:** Người dùng phải xem được trạng thái của từng công đoạn.
- **FR-CTL-003:** Người dùng phải có khả năng tạo lại kết quả của từng công đoạn.
- **FR-CTL-004:** Việc tạo lại một công đoạn không được bắt buộc chạy lại toàn bộ quy trình từ đầu khi đầu vào cần thiết vẫn còn hợp lệ.
- **FR-CTL-005:** Giao diện không phải cung cấp chỉnh sửa trực tiếp kịch bản, timeline, ảnh hoặc clip.
- **FR-CTL-006:** Chế độ thủ công phải phục vụ quan sát và debug, không làm mất khả năng chạy tự động sau đó.
- **FR-CTL-007:** Tách lệnh thử lại giữ đầu vào/cấu hình với lệnh tạo biến thể mới. Lần thử kỹ thuật không tăng số sản phẩm; biến thể mới phải đạt quy tắc FR-VAR-* và không sửa output đã hoàn thành (R17).

### 5.13. Xử lý hàng loạt và hàng chờ

- **FR-BAT-001:** Người dùng phải có thể chọn thông số chung trước khi bắt đầu một lô.
- **FR-BAT-002:** Sau khi bắt đầu, hệ thống phải có khả năng xử lý lô tự động theo cấu hình đã chọn.
- **FR-BAT-003:** Hệ thống phải lần lượt chuyển sang tin tiếp theo sau khi tạo 1-3 video cho tin hiện tại.
- **FR-BAT-004:** Một video lỗi phải bị bỏ qua và không được làm dừng cả lô.
- **FR-BAT-005:** Video lỗi phải được đánh dấu để có thể xử lý lại sau.
- **FR-BAT-006:** Tiến độ hàng chờ phải được giữ qua việc đóng/mở ứng dụng hoặc máy render gián đoạn.
- **FR-BAT-007:** Khi tiếp tục, công việc đã hoàn thành không được tự động chạy lại.
- **FR-BAT-008:** Khi không còn tin mới, hệ thống có thể quay lại kho sự kiện theo quy tắc tái khai thác.
- **FR-BAT-009:** Người dùng đặt số video hoàn thành mục tiêu của lô; lỗi, lần thử và video chưa đồng bộ không được tính để đạt mục tiêu. Có thể kết thúc thiếu mục tiêu khi không còn công việc đủ điều kiện và phải ghi rõ lý do (R10).

### 5.14. Render và kiểm tra đầu ra

- **FR-REN-001:** Sản phẩm phải tạo được video hoàn chỉnh từ kịch bản, tài nguyên, hook, âm thanh và preset đã chọn.
- **FR-REN-002:** Video phải có thời lượng từ 61 đến 70 giây.
- **FR-REN-003:** Video phải có thể mở và phát được sau khi render.
- **FR-REN-004:** Video thiếu video hook, âm thanh hook hoặc thumbnail trong hook không được tính là hoàn thành.
- **FR-REN-005:** Render và khả năng phát là điều kiện kỹ thuật, không thay cho kiểm tra thời lượng/hook/tiếng Anh và phụ đề bắt buộc theo R03; chỉ hoàn thành sau sync. Không có bước đánh giá hiệu quả TikTok sau khi xuất.
- **FR-REN-006:** Mục tiêu sản lượng sau khi quy trình ổn định là ít nhất 100 video hợp lệ trong 12 giờ.
- **FR-REN-007:** Các biến thể của cùng một sự kiện được tính vào tổng sản lượng.
- **FR-REN-008:** Mọi video hoàn thành phải có phụ đề tiếng Anh gắn vào video và timing từng từ để thể hiện karaoke, khớp phiên bản script và voice thực dùng. Chưa chốt ngưỡng sai số chữ/timing (R03).

### 5.15. Đồng bộ và dọn dữ liệu cục bộ

- **FR-SYN-001:** Mọi video hoàn thành phải được đồng bộ lên Google Drive.
- **FR-SYN-002:** Sản phẩm chỉ được xóa video cục bộ sau khi xác nhận bản đồng bộ đã hoàn thành.
- **FR-SYN-003:** Tin và tài nguyên dùng lâu dài phải được giữ trên cloud theo loại dữ liệu.
- **FR-SYN-004:** Tệp trung gian không cần được giữ lâu dài sau khi công việc hoàn tất.
- **FR-SYN-005:** Lỗi đồng bộ phải giữ lại bản cục bộ và đánh dấu công việc chưa hoàn thành việc lưu trữ.
- **FR-SYN-006:** Khi kết nối trở lại, công việc đồng bộ chưa hoàn tất phải có khả năng tiếp tục.
- **FR-SYN-007:** Cloud giữ media gốc và bản xử lý dùng lại được. Voice/subtitle riêng từng video có thể dọn sau khi hoàn tất, không còn được công việc dở dang dùng; dọn tệp không xóa script, lịch sử hay dấu biến thể (R13).

### 5.16. Tên tệp và thư mục đầu ra

- **FR-OUT-001:** Thư mục đầu ra của phiên đầu tiên trong ngày phải dùng định dạng `YY-MM-DD`.
- **FR-OUT-002:** Các phiên tiếp theo trong cùng ngày phải dùng `YY-MM-DD (1)`, `YY-MM-DD (2)` và tiếp tục tăng hậu tố.
- **FR-OUT-003:** Không được để lại thư mục phiên rỗng khi người dùng đóng ứng dụng mà chưa tạo video hoàn thành.
- **FR-OUT-004:** Tên tệp phải chứa một tiêu đề tiếng Anh liên quan đến nội dung.
- **FR-OUT-005:** Tên tệp phải chứa khoảng 3-4 hashtag liên quan.
- **FR-OUT-006:** Dấu `#` được giữ khi nơi lưu trữ đích hỗ trợ.
- **FR-OUT-007:** Nếu tên dự kiến không hợp lệ hoặc quá dài, sản phẩm phải xử lý theo quy tắc được người dùng phê duyệt ở giai đoạn sau.

### 5.17. Giao diện giám sát

- **FR-UI-001:** Toàn bộ nội dung giao diện dành cho người dùng phải bằng tiếng Việt có đầy đủ dấu.
- **FR-UI-002:** Giao diện phải sử dụng tốt trên màn hình desktop từ 1080p trở lên.
- **FR-UI-003:** Người dùng phải xem được trạng thái của nguồn, tin, tài nguyên, công đoạn, video và lô.
- **FR-UI-004:** Giao diện phải thể hiện rõ trạng thái đang chờ, đang xử lý, hoàn thành, lỗi hoặc bị bỏ qua.
- **FR-UI-005:** Với mục lỗi, thông tin lỗi chi tiết phải xuất hiện khi người dùng rê chuột.
- **FR-UI-006:** Giao diện phải thông báo trên màn hình khi video hoặc lô hoàn thành.
- **FR-UI-007:** Không yêu cầu gửi thông báo qua email hoặc ứng dụng nhắn tin trong phiên bản đầu.
- **FR-UI-008:** Giao diện cục bộ không yêu cầu đăng nhập trong phiên bản đầu.
- **FR-UI-009:** Cho sửa ô metadata quản trị như Tier, chủ đề/tag, ghi chú, bật/tắt nguồn hoặc hook. Không cho sửa bài gốc, quan hệ sự kiện hoặc script trực tiếp; danh sách cột chi tiết chờ thiết kế UI (R02, R14).

### 5.18. Nhật ký vận hành

- **FR-LOG-001:** Mỗi phiên mở ứng dụng phải có nhật ký riêng.
- **FR-LOG-002:** Nhật ký phải ghi thời gian và công việc liên quan đến từng lỗi.
- **FR-LOG-003:** Lỗi phải có mô tả đủ cụ thể để phục vụ debug.
- **FR-LOG-004:** Nhật ký phải phân biệt lỗi đã làm công việc thất bại với cảnh báo không làm dừng công việc.
- **FR-LOG-005:** Nhật ký không được hiển thị hoặc lưu giá trị bí mật của tài khoản và dịch vụ.

### 5.19. Cấu hình sản phẩm

- **FR-CFG-001:** Các nhóm chủ đề, nguồn, lịch chạy, số video mỗi tin, phong cách, preset và giới hạn vận hành phải có khả năng cấu hình sau này.
- **FR-CFG-002:** Mặc định AI tự chọn phong cách, preset, giọng đọc, nhạc, hiệu ứng và tài nguyên.
- **FR-CFG-003:** Người dùng phải có thể chọn phong cách hoặc preset cụ thể khi debug.
- **FR-CFG-004:** Thay đổi cấu hình của lô mới không được làm thay đổi kết quả của video đã hoàn thành.
- **FR-CFG-005:** Sản phẩm phải có khả năng sử dụng phương án AI dự phòng khi phương án chính không sẵn sàng.
- **FR-CFG-006:** Cách phân phối công việc giữa các tài khoản hoặc phương án AI phải tuân theo điều khoản sử dụng tương ứng.
- **FR-CFG-007:** Cho sửa prompt nội dung/phân tích trên UI. Thay đổi áp dụng cho video chưa bắt đầu tạo script, kể cả trong lô đang chạy; video đã bắt đầu giữ phiên bản cấu hình cũ. Thử lại không âm thầm thay prompt (R16, R17).
- **FR-CFG-008:** Nếu AI chính lỗi khi desktop tắt, công việc không cần AI tiếp tục; công việc cần AI chờ dịch vụ phục hồi hoặc desktop online để dùng fallback local phù hợp. Không tự thêm dịch vụ trả phí (R19).

## 6. Trạng thái người dùng cần quan sát

Đây là các trạng thái sản phẩm cần thể hiện trên giao diện, chưa phải thiết kế dữ liệu nội bộ:

- **Tin/sự kiện:** mới, đã phân loại, đủ tài nguyên, chờ xử lý, đang xử lý, đã khai thác, có diễn biến mới, lỗi.
- **Tài nguyên:** đã phát hiện, đang tải, sẵn sàng, nhạy cảm, lỗi, đã xóa cục bộ.
- **Công đoạn:** chưa chạy, đang chạy, hoàn thành, cảnh báo, lỗi, bị bỏ qua.
- **Video:** chờ, đang chuẩn bị, đang render, đang đồng bộ, hoàn thành, lỗi.
- **Lô:** chưa bắt đầu, đang chạy, đang chờ tài nguyên, hoàn thành một phần, hoàn thành, đã dừng.

Tên trạng thái cuối cùng sẽ được chuẩn hóa trong bước xác định dữ liệu và đối tượng.

## 7. Tình huống nghiệm thu chính

### AC-01: Thu thập khi máy render tắt

- Khi máy render đang tắt và đến lịch thu thập, hệ thống vẫn ghi nhận được tin và tài nguyên mới trên môi trường luôn hoạt động.
- Khi máy render hoạt động lại, các công việc mới phải xuất hiện trong danh sách chờ.

### AC-02: Debug từng công đoạn

- Người dùng chọn một tin và chạy riêng một công đoạn.
- Giao diện hiển thị trạng thái và kết quả của công đoạn đó.
- Người dùng có thể yêu cầu tạo lại mà không phải chỉnh trực tiếp kết quả.

### AC-03: Chạy lô không bị dừng bởi một video lỗi

- Khi một video trong lô lỗi, video đó được đánh dấu và ghi nhật ký.
- Hệ thống tiếp tục video tiếp theo.
- Người dùng xem được lỗi chi tiết bằng cách rê chuột vào mục bị lỗi.

### AC-04: Tiếp tục sau gián đoạn

- Khi ứng dụng hoặc máy render dừng giữa lô, tiến độ đã hoàn thành được giữ lại.
- Lần mở tiếp theo tiếp tục từ công việc chưa hoàn thành gần nhất.
- Tin đã hoàn thành không tự động chạy lại từ đầu.

### AC-05: Video hợp lệ

- Video có thời lượng 61-70 giây và phát được.
- Video có video hook, âm thanh hook và thumbnail câu chuyện trong phần hook.
- Video có nội dung và lời đọc tiếng Anh.
- Video có phụ đề tiếng Anh gắn vào hình và timing từng từ khớp voice/script thực dùng.
- Video chỉ được tính hoàn thành sau khi đồng bộ lên Google Drive thành công.

### AC-06: Đồng bộ thất bại

- Nếu đồng bộ thất bại, video cục bộ không bị xóa.
- Công việc được đánh dấu lỗi đồng bộ và có thể tiếp tục sau.

### AC-07: Tạo biến thể

- Mỗi lượt của một tin tạo 1-3 video theo các góc kể khác nhau.
- Lần khai thác lại không dùng nguyên trạng kịch bản gần nhất.
- Nếu kết quả hoàn toàn giống video cũ, hệ thống tạo lại hoặc đánh dấu không thể tạo thêm biến thể.

### AC-08: Thư mục phiên

- Khi một phiên không tạo được video hoàn thành, không tồn tại thư mục đầu ra rỗng của phiên đó.
- Khi có video hoàn thành, thư mục được đặt theo `YY-MM-DD` và hậu tố phiên trong ngày nếu cần.

## 8. Yêu cầu chất lượng sản phẩm đã được xác nhận

Phần này chỉ ghi các mức đã được người dùng chốt. Yêu cầu chất lượng hệ thống đầy đủ sẽ được xác định ở bước 06.

- **Sản lượng:** ít nhất 100 video hợp lệ trong 12 giờ sau khi quy trình ổn định.
- **Chi phí:** dưới 50 USD/tháng cho chi phí phát sinh thêm; không tính gói Gemini/Drive đã có, điện, Internet và phần cứng (R20).
- **Khả năng tiếp tục:** không bắt đầu lại từ đầu sau khi máy hoặc ứng dụng bị gián đoạn.
- **Cô lập lỗi:** một video hoặc một nguồn lỗi không làm dừng toàn bộ lô.
- **Tính quan sát:** trạng thái và lỗi phải xem được trên giao diện.
- **Lưu trữ cục bộ:** chỉ duy trì tài nguyên gần lượt xử lý của khoảng năm video.
- **Ngôn ngữ:** giao diện tiếng Việt; video và nội dung xuất bản tiếng Anh.
- **Bảo mật cơ bản:** thông tin bí mật không xuất hiện trong giao diện hoặc nhật ký.
- **Khả năng mở rộng:** có thể phát triển thành SaaS mà không phải thay thế toàn bộ cấu trúc sản phẩm.

## 9. Ngoài phạm vi

- Tự động đăng video.
- Đo lường lượt xem, retention, doanh thu hoặc hiệu quả sau khi đăng.
- Hỗ trợ YouTube.
- Trình biên tập kịch bản, ảnh, clip hoặc timeline trực tiếp.
- Hệ thống nhiều người dùng, thanh toán và quản trị thuê bao trong phiên bản đầu.
- Quy trình kiểm chứng đa nguồn bắt buộc cho mọi tin.
- Cam kết video sẽ viral, được kiếm tiền hoặc không bị khiếu nại bản quyền.
- Làm mờ lại video hook do người dùng nhập.

## 10. Giới hạn và phụ thuộc đã biết

- Máy cá nhân dùng để render không có lịch hoạt động cố định.
- Thu thập và làm giàu tài nguyên phụ thuộc vào một môi trường có thể hoạt động khi máy render tắt.
- Nguồn bên ngoài có thể thay đổi, giới hạn truy cập hoặc ngừng cung cấp dữ liệu.
- Tài nguyên truy cập công khai không đồng nghĩa với quyền sử dụng không giới hạn.
- Người dùng chấp nhận rủi ro quyền sử dụng; sản phẩm không bảo đảm tránh khiếu nại.
- Ngân sách giai đoạn đầu giới hạn dưới 50 USD mỗi tháng.
- Sản lượng phụ thuộc vào khả năng cung cấp tin, tài nguyên, dịch vụ bên ngoài và máy render.
- Bốn tài khoản Gemini Pro và bốn kho Google Drive 5 TB là tài nguyên do người dùng khai báo, chưa được kiểm chứng về API, hạn mức hoặc cách gộp dung lượng.

## 11. Các vấn đề CHƯA QUYẾT ĐỊNH

### 11.1. Các điểm đã được người dùng giải quyết

- **RESOLVED-001 - Phạm vi lọc nhạy cảm:** Chỉ xử lý ảnh nhạy cảm; không xử lý clip lấy từ nguồn.
- **RESOLVED-002 - Nội dung "từ lúc đó đến nay":** R07 làm rõ chỉ tình tiết/diễn biến mới có ý nghĩa mới đủ điều kiện; nguồn mới và bài đăng lại không đủ.
- **RESOLVED-003 - Điều kiện không trùng:** Trong cùng lượt, 1-3 video phải khác góc kể. Giữa các lượt sau, video chỉ cần khác ít nhất một yếu tố nhưng không được hoàn toàn giống video cũ.

### 11.2. Các quyết định được ủy quyền nghiên cứu

- **OPEN-004:** Nhóm chủ đề bổ sung có giá trị nhất đối với TikTok Mỹ.
- **OPEN-005:** Danh sách nguồn ban đầu và tiêu chí xếp `Tier 1/2/3`.
- **OPEN-006:** Thời điểm chạy thu thập hằng ngày.
- **OPEN-007:** Cách xác định nhiều bài thuộc cùng một sự kiện.
- **OPEN-008:** Mức thông tin nguồn và quyền sử dụng cần lưu.
- **OPEN-009:** Cách chia dữ liệu theo loại giữa bốn kho Google Drive.
- **OPEN-010:** Phương án AI dự phòng và phạm vi xử lý cục bộ.
- **OPEN-011:** Cách phân phối công việc giữa các tài khoản trong giới hạn điều khoản dịch vụ.
- **OPEN-012:** Số công việc đồng thời, retry, timeout và giới hạn chi phí cho từng công đoạn.
- **OPEN-013:** Mức chuẩn bị SaaS cần có ngay từ đầu.
- **OPEN-014:** Cách xác định một video hoàn toàn giống video cũ trên các yếu tố được theo dõi.
- **OPEN-015:** Quy tắc rút gọn tiêu đề, hashtag và ký tự không hợp lệ trong tên tệp.
- **OPEN-016 - ĐÃ ĐÓNG ở mức nghiệp vụ:** R14/R15/R24 chốt thao tác UI và ngừng/khôi phục nguồn; không còn tệp text. Chi tiết cột, xác nhận thao tác và trình bày thuộc thiết kế UI.

Các phần đã chốt trong OPEN-005/007/010/012 được áp dụng theo R04-R09, R18-R20, R23; chỉ tiêu chí Tier, ngưỡng phát hiện trùng/liên kết, model, lịch cụ thể và hạn mức kỹ thuật còn mở. Không hỏi lại chính sách nghiệp vụ đã xác nhận.

Các mục `OPEN-*` không được xem là quyết định kiến trúc hoặc công nghệ.

## 12. Giả định

**Không có GIẢ ĐỊNH nào được dùng làm yêu cầu chính thức trong tài liệu này.**

Những nội dung chưa đủ thông tin được ghi rõ bằng mã `OPEN-*`. Chúng chỉ trở thành yêu cầu chính thức sau khi người dùng xác nhận hoặc phê duyệt kết quả nghiên cứu ở giai đoạn phù hợp.

## 13. Tiêu chí phê duyệt đặc tả

Đặc tả được phê duyệt khi người dùng xác nhận:

1. Các yêu cầu `FR-*` mô tả đúng những khả năng sản phẩm phải có.
2. Phạm vi ngoài sản phẩm là đầy đủ và đúng mong muốn.
3. Các điểm `RESOLVED-001`, `RESOLVED-002` và `RESOLVED-003` đã được ghi nhận đúng.
4. Các vấn đề được ủy quyền nghiên cứu có thể tiếp tục ở trạng thái chưa quyết định.

Sau khi tài liệu được phê duyệt, bước tiếp theo là **05 - Xác định dữ liệu và đối tượng**. Việc phê duyệt tài liệu này không đồng nghĩa với phê duyệt kiến trúc, công nghệ hoặc kế hoạch triển khai.
