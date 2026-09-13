# AI Auto Video Creator - Project Charter

**Giai đoạn:** 03 - Chốt mục tiêu và phạm vi  
**Ngày xác nhận:** 12-09-2026  
**Trạng thái:** Đã được người dùng phê duyệt; cập nhật theo quyết định R01-R25 trước bước 09

**Lịch sử làm rõ:** Các quyết định R01-R25 được tổng hợp tại [07-data-flow.md](./07-data-flow.md), mục 2. Những quyết định mới thay thế phát biểu cũ có cùng phạm vi; không phê duyệt công nghệ hoặc cho phép viết code.

## 1. Mục đích tài liệu

Tài liệu này xác định mục tiêu, người dùng, phạm vi và giới hạn của AI Auto Video Creator. Đây chưa phải tài liệu thiết kế hệ thống, chưa lựa chọn công nghệ, chưa định nghĩa kiến trúc và chưa phải kế hoạch triển khai.

## 2. Tầm nhìn sản phẩm

AI Auto Video Creator là công cụ sản xuất video ngắn tiếng Anh cho khán giả Mỹ. Công cụ thu thập và phân loại tin có tiềm năng thu hút trên TikTok, làm giàu tin bằng ảnh và clip liên quan, tạo nhiều cách kể khác nhau, chọn tài nguyên nghe nhìn phù hợp và render thành video hoàn chỉnh.

Sản phẩm hướng đến một dây chuyền có thể khai thác lại kho sự kiện trong thời gian dài, tạo các phiên bản mới mà không lặp lại phiên bản gần nhất và mở rộng sản lượng theo lượng tin, tài nguyên và năng lực xử lý sẵn có.

## 3. Người dùng mục tiêu

- Giai đoạn đầu chỉ phục vụ một người dùng vận hành trên máy desktop cá nhân.
- Người dùng theo dõi trạng thái, chạy từng công đoạn để debug, tạo lại kết quả và khởi chạy xử lý hàng loạt.
- Giao diện không phải trình biên tập video, kịch bản hoặc timeline thủ công.
- Giao diện chạy cục bộ, không yêu cầu đăng nhập trong giai đoạn một.
- Giao diện hoàn toàn bằng tiếng Việt và tối ưu cho màn hình desktop từ 1080p trở lên.

## 4. Mục tiêu kinh doanh và vận hành

- Tạo nguồn video ngắn gần như liên tục từ kho tin và sự kiện có thể khai thác lại.
- Ưu tiên các chủ đề có sức hút lâu dài hoặc đang được quan tâm mạnh bởi khán giả TikTok tại Mỹ.
- Mỗi sự kiện có thể tạo nhiều góc kể và được khai thác lại sau một chu kỳ hoặc khi có diễn biến mới.
- Khi quy trình ổn định, đạt tối thiểu 100 video hợp lệ trong 12 giờ; càng nhiều càng tốt nếu vẫn duy trì độ ổn định.
- Tối ưu chi phí giai đoạn đầu trong giới hạn dưới 50 USD mỗi tháng.
- Chuẩn bị nền tảng đầy đủ để có thể phát triển thành SaaS khi người dùng yêu cầu, nhưng chưa cung cấp chức năng SaaS trong phiên bản đầu.

## 5. Định nghĩa kết quả hợp lệ

Một video được tính là hoàn thành khi:

- Render thành công và có thể phát được.
- Có thời lượng từ 61 đến 70 giây.
- Có nội dung và lời dẫn bằng tiếng Anh, hướng đến khán giả Mỹ.
- Có phụ đề tiếng Anh gắn vào video, với thời gian từng từ phục vụ hiệu ứng karaoke (R03).
- Có video hook, âm thanh hook và thumbnail liên quan đến câu chuyện trong phần hook.
- Có tên tệp gồm tiêu đề tiếng Anh không quá dài và khoảng 3-4 hashtag liên quan.
- Đã được đồng bộ lên Google Drive trước khi bản lưu trên máy render bị xóa.

Chỉ số 100 video trong 12 giờ bao gồm các biến thể và góc kể khác nhau của cùng một sự kiện.

## 6. Phạm vi nội dung

- Thu thập tin toàn cầu có khả năng thu hút khán giả Mỹ; đầu ra luôn bằng tiếng Anh.
- Chia nguồn thành các mức `Tier 1`, `Tier 2` và `Tier 3`; ưu tiên mức cao trước và mở rộng sang mức tiếp theo khi cần thêm dữ liệu.
- Tổ chức nguồn và tin theo các nhóm chủ đề riêng.
- Các nhóm đã xác nhận gồm: người nổi tiếng, tin gây sốc, chính trị đang thịnh hành, tội ác, tai nạn, tội phạm, cảnh sát, bản án và hồ sơ nổi bật.
- Các nhóm chủ đề bổ sung chỉ được đưa vào sau khi nghiên cứu cho thấy chúng có giá trị đối với TikTok và được người dùng phê duyệt.
- Với người nổi tiếng, phạm vi thu thập có thể bao gồm clip ngắn từ trang cá nhân chính thức.
- Ưu tiên lấy cả ảnh và clip từ bài viết khi nguồn có cung cấp.
- Một bài có thể được xử lý như một tin độc lập; nhiều bài về cùng sự kiện cũng có thể được hợp nhất thành một câu chuyện chung.
- Hệ thống lưu lịch sử sự kiện để tạo nội dung dạng "từ lúc đó đến bây giờ" khi có diễn biến mới với tình tiết mới. Nguồn mới hoặc bài đăng lại không tự tạo diễn biến mới (R07).

## 7. Nguyên tắc nội dung

- Không bắt buộc đối chiếu nhiều nguồn trước khi sản xuất video.
- Xác minh chỉ kiểm tra dữ liệu thu thập và khả năng truy nguồn. Khi các nguồn mâu thuẫn, dùng phiên bản từ nguồn được ưu tiên theo Tier (R01, R08).
- Các khẳng định được trình bày như sự thật phải dựa trên dữ liệu đã thu thập.
- AI được phép suy luận hoặc sáng tạo thêm góc diễn giải, nhưng phần đó phải thể hiện rõ là suy luận, không phải sự thật đã được xác nhận.
- Nội dung phải được kể theo cách hấp dẫn, gây tò mò và có khả năng tạo thảo luận.
- Khi nguồn sửa nội dung, dữ liệu và kịch bản dùng cho những lần sản xuất sau phải cập nhật theo nguồn mới.
- Video đã hoàn thành trước khi nguồn thay đổi vẫn được giữ nguyên.
- Job đã bắt đầu tạo script giữ bộ phiên bản nguồn đã ghi nhận tới khi xong; job chưa bắt đầu tạo script và lần sản xuất sau dùng bản cập nhật (R09).
- Bài đăng lại trùng nội dung không tạo tin/kịch bản độc lập hay được dùng để tổng hợp như thông tin mới. Vẫn lấy media mới phù hợp và ghi xuất xứ để bổ sung cho tin đại diện, phục vụ đa dạng hóa video (R07, R22).
- Khi chưa chắc hai bài thuộc cùng vụ việc, giữ riêng và vẫn có thể sản xuất theo từng bài; chỉ tổng hợp khi liên kết đủ chắc (R06).

## 8. Thu thập và quản lý nguồn

- Tự động tìm và sử dụng nguồn mà không yêu cầu người dùng duyệt từng nguồn.
- Cho phép người dùng thêm, xóa và quản lý nguồn trên giao diện.
- Quản lý nguồn trực tiếp trên UI; bỏ yêu cầu tệp text riêng (R15).
- Quét định kỳ theo thứ tự Tier, mỗi nguồn được chọn tối đa một lượt định kỳ/ngày; chỉ mở rộng Tier khi lượng tin mới không trùng theo từng chủ đề chưa đạt ngưỡng ngày. Có thể không quét nguồn đang bật nếu đã đủ dữ liệu; giá trị ngưỡng chờ nghiên cứu (R04, R23).
- Tìm và tải bổ sung theo nhu cầu video không bị giới hạn bởi lượt quét định kỳ (R05).
- Xóa nguồn trên UI ngừng thu thập và ngăn tự thêm lại cho tới khi người dùng khôi phục; tin/media đã lưu vẫn được khai thác. Đây không phải yêu cầu xóa dây chuyền dữ liệu lịch sử (R24).
- Hoạt động thu thập và làm giàu tài nguyên phải tiếp tục khi máy render cá nhân đang tắt.
- Thời điểm chạy tối ưu và tiêu chí xếp `Tier` sẽ được quyết định sau nghiên cứu, không được giả định trong charter này.

## 9. Tin, sự kiện và khả năng tái khai thác

- Tin từ từng bài được lưu độc lập nhưng vẫn có thể liên kết vào một sự kiện chung.
- Mỗi lượt xử lý một tin tạo từ 1 đến 3 video với các góc kể khác nhau trước khi chuyển sang tin tiếp theo.
- Sau khi đi hết hàng chờ, một sự kiện có thể được khai thác lại theo quy tắc khác biệt giữa các lượt bên dưới; không bắt buộc mỗi lượt sau phải có góc hoàn toàn mới.
- Không đặt giới hạn cố định cho tổng số video có thể tạo từ một sự kiện.
- Không được dùng lại kịch bản gần nhất của sự kiện.
- Trong cùng một lượt, 1-3 video của một tin phải khác góc kể.
- Giữa các lượt khai thác sau, video phải khác ít nhất một yếu tố và không được hoàn toàn giống video cũ.
- Các yếu tố có thể thay đổi gồm góc kể, kịch bản, giọng đọc, hook, âm thanh, nhạc nền, thứ tự và lựa chọn ảnh/clip, hiệu ứng hoặc cách dẫn dắt.

## 10. Kho tài nguyên và hook

- Có kho tài nguyên ảnh, clip, âm thanh và thông tin chỉ mục để AI chọn theo nội dung.
- Hook là kho dùng chung, không bắt buộc thuộc đúng sự kiện đang kể.
- Hook chỉ đóng vai trò minh họa và giữ chân người xem.
- Video hook do người dùng tự bổ sung và đã được làm mờ trước khi nhập kho.
- Kho video hook và kho âm thanh hook được quản lý riêng.
- Người dùng cung cấp cả video hook và audio hook; hệ thống tự tìm/thu thập nhạc nền và SFX (R11).
- AI chọn video hook và âm thanh hook tương ứng với nội dung câu chuyện.
- Khi đưa hook vào video, phải chèn thumbnail liên quan để người xem nhận biết câu chuyện nói về ai hoặc sự kiện nào.
- AI chỉ chọn một trong năm nhóm preset trình bày và được điều chỉnh tham số bên trong preset; không tự tạo một hệ layout hoàn toàn mới ngoài năm nhóm này.
- Bộ lọc nhạy cảm chỉ áp dụng cho ảnh, không áp dụng cho clip lấy từ nguồn.
- Ảnh nhạy cảm cần được xử lý gồm khuôn mặt trẻ em, máu me và vũ khí; cách xử lý có thể gồm làm mờ hoặc thay đổi màu sắc.
- Nếu nhận diện chưa chắc, kiểm tra bị lỗi hoặc xử lý ảnh thất bại, được dùng ảnh nguyên gốc còn đọc được theo chấp nhận rủi ro của người dùng. Phải giữ trạng thái chưa chắc/lỗi; không coi là đã xử lý thành công. Quy tắc này không bỏ nghĩa vụ nhận diện và thử xử lý ảnh đã xác định cần xử lý (R12, R25).
- Với clip người nổi tiếng, sản phẩm có thể thêm thumbnail, biểu tượng, mũi tên, dấu hỏi, dấu cảm thán và các lớp nhấn mạnh phục vụ cách trình bày sáng tạo.

## 11. Luồng vận hành ở cấp độ sản phẩm

- Mỗi công đoạn có nút chạy thủ công để người dùng quan sát kết quả và debug.
- Người dùng có thể tạo lại kết quả của từng công đoạn mà không cần chỉnh sửa trực tiếp nội dung trên giao diện.
- Chế độ mặc định cho lựa chọn phong cách là tự động; giao diện vẫn có danh sách để người dùng chọn khi debug.
- Trong xử lý hàng loạt, người dùng chọn các thông số chung rồi cho phép công cụ tự động hoàn toàn.
- Người dùng đặt số video hoàn thành mục tiêu cho lô; lô tái khai thác tới khi đạt mục tiêu hoặc không còn công việc đủ điều kiện. Không đồng nhất mục tiêu lô với mốc hiệu năng 100 video/12 giờ (R10).
- Tách lệnh thử lại giữ đầu vào, không tính sản phẩm mới, khỏi lệnh tạo biến thể mới phải qua quy tắc khác biệt đã chốt (R17).
- Cho sửa metadata quản trị như Tier, chủ đề/tag, ghi chú, bật/tắt nguồn hoặc hook; không sửa bài gốc, quan hệ sự kiện hoặc script trực tiếp (R02, R14).
- Cho sửa prompt nội dung/phân tích; áp dụng cho video chưa bắt đầu tạo script kể cả trong lô đang chạy. Video đã bắt đầu giữ phiên bản cấu hình cũ (R16).
- Nếu một video lỗi, hệ thống bỏ qua video đó và tiếp tục lô.
- Video lỗi được đánh dấu; nội dung lỗi chỉ hiện khi người dùng rê chuột vào vị trí tương ứng.
- Mỗi phiên mở ứng dụng có nhật ký riêng, bao gồm thời gian và lỗi cụ thể phục vụ debug.
- Trạng thái hoàn thành hoặc lỗi của video và của lô chỉ cần hiển thị trên giao diện.

## 12. Lưu trữ và vòng đời tệp

- Google Drive là nơi lưu lâu dài tin, tài nguyên và video đầu ra.
- Tổng dung lượng Google Drive hiện được người dùng xác định là bốn tài khoản, mỗi tài khoản 5 TB.
- Tệp trung gian trên cloud không cần giữ lâu dài.
- Giữ media gốc và bản xử lý dùng lại được như ảnh đã che mờ, clip chuẩn hóa. Voice/subtitle riêng từng video có thể dọn khi hoàn tất và không còn cần cho phục hồi; vẫn giữ lịch sử và tham chiếu phiên bản (R13).
- Máy render chỉ tải tài nguyên khi công việc đã gần tới lượt xử lý.
- Máy giữ tài nguyên cục bộ cho khoảng năm video sắp render.
- Trong lúc render một video, hệ thống chuẩn bị tài nguyên cho video tiếp theo để giảm thời gian chờ.
- Sau khi video hoàn thành và đồng bộ thành công lên Google Drive, dữ liệu cục bộ của tin đó được xóa.
- Khi máy bị tắt hoặc gián đoạn, lần chạy tiếp theo tiếp tục từ trạng thái trước đó, không quay lại tin đầu tiên.
- Dữ liệu có thể mất trong sự cố nghiêm trọng; sao lưu bổ sung không phải ưu tiên cao ở giai đoạn đầu.

## 13. Giới hạn chi phí và tài nguyên hiện có

- Ngân sách vận hành mục tiêu dưới 50 USD mỗi tháng trong giai đoạn đầu.
- Ngân sách chỉ tính chi phí phát sinh thêm cho dự án; không tính các gói Gemini/Drive đã có, điện, Internet và phần cứng (R20).
- Có thể gửi toàn bộ bài viết và media tới dịch vụ AI hoặc cloud bên ngoài.
- Máy render: AMD Ryzen 9 7950X, RAM 32 GB và NVIDIA RTX 4070 SUPER 12 GB VRAM.
- Có bốn tài khoản Gemini Pro và bốn kho Google Drive 5 TB theo thông tin người dùng cung cấp.
- Có thể sử dụng nhiều tài khoản cho các vai trò hoặc batch khác nhau nếu cách sử dụng đó phù hợp với điều khoản dịch vụ.
- Phải có phương án fallback khi dịch vụ AI chính gặp lỗi; lựa chọn fallback chưa được quyết định.
- Khi desktop tắt, chuẩn bị tin, media và chỉ mục trên cloud; script, kế hoạch dựng và voice chờ desktop hoạt động. Đây là điều kiện vận hành, chưa quy định tất cả tác vụ đó phải thực thi cục bộ (R18).
- Nếu AI chính lỗi khi desktop tắt, việc không cần AI vẫn tiếp tục; việc cần AI chờ dịch vụ phục hồi hoặc desktop online để dùng local fallback. Không tự thêm dịch vụ trả phí (R19).

## 14. Quyền sử dụng và giới hạn cam kết

- Người dùng cho phép hệ thống tự do thu thập tài nguyên và chấp nhận rủi ro quyền sử dụng.
- Sản phẩm không bắt buộc chặn tài nguyên chỉ vì chưa xác minh được giấy phép.
- Việc lưu nguồn, quyền sử dụng và lịch sử tài nguyên sẽ được đề xuất sau nghiên cứu.
- Sản phẩm không cam kết rằng một tài nguyên được phép sử dụng chỉ vì tài nguyên đó truy cập công khai.
- Sản phẩm không cam kết tránh được khiếu nại bản quyền, hạn chế nền tảng, hoặc bảo đảm khả năng viral và kiếm tiền.
- Các lớp phủ và biến đổi hình ảnh phục vụ trình bày sáng tạo, không được mô tả như cơ chế bảo đảm né tránh hệ thống bản quyền.

## 15. Ngoài phạm vi hiện tại

- Tự động đăng video lên TikTok hoặc nền tảng khác.
- Đo lường lượt xem, retention, doanh thu hoặc hiệu quả sau khi đăng.
- Hỗ trợ YouTube.
- Giao diện chỉnh sửa trực tiếp kịch bản, ảnh, clip hoặc timeline.
- Hệ thống nhiều người dùng, thanh toán, gói thuê bao và quản trị khách hàng SaaS ở phiên bản đầu.
- Bảo đảm tính đúng tuyệt đối của tin bằng quy trình kiểm chứng đa nguồn bắt buộc.
- Xử lý làm mờ lại video hook do người dùng nhập, vì hook được yêu cầu xử lý sẵn.

## 16. Quy tắc đầu ra và thư mục

- Thư mục đầu ra của phiên đầu tiên trong ngày dùng định dạng `YY-MM-DD`.
- Các phiên tiếp theo trong cùng ngày dùng `YY-MM-DD (1)`, `YY-MM-DD (2)` và tiếp tục tăng hậu tố.
- Chỉ tạo hoặc giữ thư mục phiên khi có ít nhất một video hoàn thành.
- Tên tệp video gồm tiêu đề tiếng Anh không quá dài và khoảng 3-4 hashtag liên quan đến nội dung.
- Dấu `#` được phép giữ trong tên tệp nếu hệ thống lưu trữ đích hỗ trợ.
- Quy tắc rút gọn, thay thế ký tự không hợp lệ và giới hạn độ dài sẽ được xác định trong đặc tả sản phẩm.

## 17. Yêu cầu khả năng mở rộng

- Kiến trúc tương lai phải cho phép phát triển thành nền tảng SaaS đầy đủ khi được yêu cầu.
- Việc chuẩn bị cho SaaS không làm thay đổi phạm vi một người dùng của phiên bản đầu.
- Nguồn tin, nhóm chủ đề, preset, phong cách kể, lịch chạy và giới hạn vận hành phải có khả năng mở rộng hoặc cấu hình sau này.
- Hệ thống phải có khả năng tăng năng lực lưu trữ hoặc xử lý mà không buộc xây dựng lại toàn bộ sản phẩm.

## 18. Các vấn đề chưa quyết định

Các mục dưới đây đã được người dùng ủy quyền nghiên cứu hoặc đề xuất. Chúng chưa phải quyết định chính thức:

- Danh sách nhóm chủ đề bổ sung có giá trị nhất đối với TikTok Mỹ.
- Danh sách nguồn ban đầu và tiêu chí xếp nguồn vào `Tier 1/2/3`.
- Thời điểm chạy thu thập tin hằng ngày.
- Cách phát hiện, liên kết và hợp nhất nhiều bài viết thành cùng một sự kiện.
- Mô hình lưu bằng chứng nguồn, lịch sử và thông tin quyền sử dụng.
- Cách phân bổ dữ liệu giữa bốn tài khoản Google Drive.
- Phương án sao lưu tối thiểu phù hợp với mức ưu tiên thấp của dữ liệu dự phòng.
- Phạm vi cụ thể của nền tảng "SaaS-ready" cần chuẩn bị ngay từ đầu.
- Cách phân phối vai trò giữa các tài khoản AI trong giới hạn điều khoản dịch vụ.
- AI cục bộ hoặc phương án khác dùng làm fallback.
- Số công việc đồng thời, giới hạn chi phí, retry và timeout của từng phân hệ.
- Cách nhận diện một video hoàn toàn giống video cũ trên các yếu tố được theo dõi.
- Quy tắc rút gọn caption và xử lý ký tự không hợp lệ trong tên tệp.

Mỗi quyết định trên phải được nghiên cứu, trình bày lựa chọn và xin người dùng xác nhận trước khi trở thành quyết định thiết kế.

## 19. Giả định

**Không có giả định nào được dùng làm quyết định chính thức trong tài liệu này.**

Thông tin về dung lượng tài khoản, quyền truy cập dịch vụ, khả năng API, điều khoản sử dụng, nguồn tin và tài nguyên công khai đều là dữ liệu do người dùng cung cấp hoặc vấn đề đang chờ kiểm chứng.

## 20. Điều kiện chuyển sang bước 04

Chỉ chuyển sang bước **04 - Viết Đặc tả sản phẩm** khi người dùng:

1. Xác nhận mục tiêu và phạm vi trong charter này phản ánh đúng sản phẩm mong muốn.
2. Chỉ ra mọi nội dung cần sửa, bổ sung hoặc loại bỏ.
3. Đồng ý rằng các mục ở phần "Các vấn đề chưa quyết định" được phép tiếp tục tồn tại để xử lý trong đúng giai đoạn nghiên cứu tương ứng.
