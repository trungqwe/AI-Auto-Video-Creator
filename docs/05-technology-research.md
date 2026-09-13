# AI Auto Video Creator - Nghiên cứu công nghệ và dự án có sẵn

**Kết luận sau giai đoạn nghiên cứu:** [08-architecture.md](./08-architecture.md), [audit](./08-architecture-audit.md) và [ADR index](./adr/README.md) ghi baseline hiện hành. Mục “ứng viên/chưa chọn” trong nghiên cứu là bối cảnh lịch sử; số release/contributor không thay thế kiểm chứng version/build thực tế.

**Giai đoạn:** 07 - Nghiên cứu cái có sẵn theo từng năng lực  
**Ngày chụp dữ liệu:** 12-09-2026  
**Trạng thái:** Đã được user chấp thuận làm baseline nghiên cứu; quyết định hiện hành thuộc 08/ADR/version lock theo milestone  

**Cập nhật phạm vi theo R01-R25:** không xác minh lại ngày phát hành/license hay tự chọn ứng viên. R03 bắt buộc phụ đề karaoke từng từ; R14 cho sửa metadata quản trị; R15 bỏ tệp text nguồn; R18/R19 chốt chuẩn bị khi desktop tắt và hành vi chờ AI; R20 chốt ngân sách chỉ tính chi phí bổ sung. Xem [07-data-flow.md](./07-data-flow.md), mục 2.
**Tài liệu nguồn:** [00-project-charter.md](./00-project-charter.md), [01-product-spec.md](./01-product-spec.md), [02-data-model.md](./02-data-model.md), [03-quality-requirements.md](./03-quality-requirements.md)

## 1. Mục đích và ranh giới

Tài liệu này khảo sát các dự án, thư viện và dịch vụ có thể cung cấp từng năng lực riêng của sản phẩm. Việc nghiên cứu không bắt đầu từ một sản phẩm “AI video creator” hoàn chỉnh, vì cách đó dễ kéo theo kiến trúc, dữ liệu, chi phí và giới hạn không phù hợp với yêu cầu đã xác nhận.

Tài liệu này:

- Thu thập ít nhất ba hướng hoặc ứng viên cho mỗi quyết định có ảnh hưởng lớn.
- Đánh giá nguồn chính thức, GitHub, giấy phép, hoạt động phát triển, độ ổn định API, test, tài liệu, mức phù hợp, phần có thể dùng và lý do không dùng.
- Đưa ra **kết luận nghiên cứu** để làm đầu vào cho bước phân rã hệ thống và kiến trúc.
- Không cài thư viện, không khởi tạo framework, không viết mã và không thiết kế kiến trúc hệ thống.
- Không mặc định Google Sheets là cơ sở dữ liệu chính. Trải nghiệm dạng bảng và nơi lưu dữ liệu là hai quyết định độc lập.

Mọi tên công nghệ ở mục “ưu tiên” chỉ có nghĩa là **ứng viên nên được kiểm chứng trước**. Nó chưa trở thành quyết định chính thức cho đến khi người dùng phê duyệt ở giai đoạn phù hợp.

## 2. Ràng buộc dùng để đánh giá

- Một người vận hành ở giai đoạn đầu, nhưng cấu trúc cần dễ mở rộng về sau.
- Thu thập và làm giàu dữ liệu tiếp tục được khi máy render tắt.
- Máy render mục tiêu: Ryzen 9 7950X, RAM 32 GB, RTX 4070 SUPER 12 GB VRAM.
- Video tiếng Anh dài 61-70 giây; mục tiêu ít nhất 100 video hợp lệ trong 12 giờ.
- Một lỗi không được làm dừng toàn bộ lô; công việc phải tiếp tục được sau gián đoạn.
- Chỉ xử lý **ảnh** nhạy cảm, không xử lý clip nguồn.
- Kho Google Drive hiện có tổng dung lượng danh nghĩa 20 TB; tệp cục bộ phải được dọn sau khi đồng bộ thành công.
- Ngân sách giai đoạn đầu dưới 50 USD/tháng.
- UI cần quan sát và thao tác dữ liệu theo trải nghiệm gần Google Sheets, chủ yếu phục vụ vận hành và debug.
- Các dịch vụ AI phải có khả năng thay thế hoặc fallback mà không làm mất hàng chờ và lịch sử.

## 3. Phương pháp nghiên cứu và audit

### 3.1. Nguồn và thời điểm

- Tính năng và trạng thái API được đối chiếu với tài liệu chính thức hoặc kho mã chính thức.
- Giấy phép được đọc từ trang license chính thức hoặc tệp `LICENSE` của dự án, không suy từ tên gọi hay bài viết bên thứ ba.
- Ngày cập nhật, bản phát hành và số contributor được lấy từ GitHub API tại ngày 12-09-2026.
- Số contributor là số gần đúng theo GitHub. Với mirror như PostgreSQL và SQLite, con số này không đại diện cho toàn bộ cộng đồng phát triển.
- “Có test” nghĩa là kho mã có test suite hoặc quy trình CI có thể quan sát được. Đây chưa phải đánh giá chất lượng hay độ bao phủ test.

### 3.2. Cách đọc trạng thái hoạt động

- **Rất tích cực:** có cập nhật hoặc release trong khoảng 90 ngày gần nhất và cộng đồng còn hoạt động.
- **Tích cực:** có cập nhật trong 12 tháng gần nhất, tài liệu và issue/release vẫn được duy trì.
- **Chậm:** trên 12 tháng không có cập nhật đáng kể hoặc nhịp release không còn đều.
- **Dừng/archived:** chủ dự án đã lưu trữ kho mã hoặc công bố không còn duy trì.

### 3.3. Thang điểm

Điểm tổng hợp từ 1 đến 10 được dùng để xếp thứ tự nghiên cứu, không phải kết quả benchmark. Trọng số:

| Tiêu chí | Trọng số |
|---|---:|
| Đáp ứng đúng năng lực | 20% |
| Rủi ro tích hợp | 15% |
| Độ phức tạp triển khai | 10% |
| Hiệu năng lúc chạy | 15% |
| Độ đơn giản vận hành | 15% |
| Khả năng bảo trì | 10% |
| Chi phí và tài nguyên | 10% |
| Thời gian để kiểm chứng | 5% |

“API cao” nghĩa là giao diện được công bố, có versioning/tài liệu và lịch sử tương thích tốt. “API trung bình” nghĩa là dùng được nhưng có khả năng thay đổi hoặc phụ thuộc mô hình/runtime. “API thấp” áp dụng cho Preview, API nội bộ hoặc dự án có dấu hiệu thay đổi mạnh.

### 3.4. Kết quả audit trước khi ghi tài liệu

- Đã rà soát 73 kho mã và dịch vụ theo từng năng lực, không tìm kiếm theo cụm “best AI video creator GitHub”.
- Đã kiểm tra chéo giấy phép đặc biệt hoặc hỗn hợp của Remotion, Handsontable, AG Grid, Meilisearch, Sentry, Piper và các model giọng nói.
- Đã kiểm tra trạng thái archived của MinIO và giới hạn chính thức của Google Drive API.
- Đã kiểm tra điều kiện truy cập TikTok Research API và trạng thái Alpha của Google Trends API.
- Đã tách giấy phép phần mềm khỏi quyền sử dụng bài báo, ảnh, clip, giọng nói và model. Một thư viện có license phù hợp không tạo ra quyền tái sử dụng nội dung nguồn.
- Chưa chạy benchmark trên máy mục tiêu; mọi kết luận về chất lượng AI, tốc độ render và tỷ lệ phát hiện 95% vẫn cần kiểm chứng thực nghiệm.

## 4. Tóm tắt kết luận nghiên cứu

| Năng lực | Ứng viên ưu tiên kiểm chứng | Phương án dự phòng/bổ sung | Không ưu tiên ban đầu |
|---|---|---|---|
| RSS/Atom | feedparser | RSSHub | Miniflux làm lõi |
| Thu thập web | Scrapy | Playwright cho trang động; curl_cffi khi thật sự cần | Dùng browser cho mọi nguồn |
| Trích xuất bài | Trafilatura | Mozilla Readability; jusText | Newspaper3k làm parser chính |
| Tín hiệu trending | GDELT và tín hiệu nội bộ từ nguồn | Google Trends API khi được cấp Alpha | TikTok Research API cho mục đích thương mại |
| Lưu dữ liệu có cấu trúc | PostgreSQL | SQLite cho prototype cục bộ; DuckDB cho phân tích | DuckDB làm cơ sở dữ liệu giao dịch chính |
| Tìm kiếm | PostgreSQL Full Text Search trước | Meilisearch Community khi nhu cầu vượt ngưỡng | OpenSearch ở quy mô đầu |
| Chống trùng/liên kết sự kiện | DataSketch + Sentence Transformers | luật URL/hash và đánh giá AI | Chỉ dùng LLM để quyết định trùng |
| Quản lý media | Metadata riêng + Google Drive | MediaCMS để tham khảo mô hình | Immich/PhotoPrism làm lõi nghiệp vụ |
| Phân tích media | ffprobe/FFmpeg | PyAV, PySceneDetect, OpenCV | Một bộ AI nặng chạy trên mọi tệp |
| An toàn ảnh | Pipeline kết hợp và benchmark riêng | Rekognition hoặc Vision SafeSearch | OpenNSFW2 làm bộ lọc duy nhất |
| Nhận dạng khuôn mặt | MediaPipe/OpenCV | dịch vụ cloud nếu benchmark không đạt | DeepFace cho bài toán che mặt đơn giản |
| STT/phụ đề | faster-whisper | WhisperX khi cần timestamp từ; whisper.cpp cho fallback | Whisper gốc làm runtime mặc định |
| TTS | Chưa chốt, bắt buộc benchmark | Gemini TTS, Piper/Kokoro, ElevenLabs | ElevenLabs làm mặc định nếu vượt ngân sách |
| FFmpeg wrapper | Gọi FFmpeg/ffprobe qua adapter mỏng | PyAV cho xử lý frame | ffmpeg-python làm phụ thuộc lõi mới |
| Video composition | FFmpeg filter graph | MoviePy cho thử nghiệm; MLT nếu cần timeline engine | Remotion làm lõi ban đầu |
| Workflow/job queue | Temporal là ứng viên độ bền cao | Prefect; Celery | BullMQ nếu runtime không phải TypeScript |
| Scheduler | Scheduler của workflow đã chọn | APScheduler cho lịch đơn giản | Chạy thêm một hệ scheduler không cần thiết |
| Object storage/sync | Google Drive API + metadata riêng | rclone cho vận hành/fallback | MinIO Community mới |
| Admin grid | AG Grid Community | TanStack Table | Handsontable thương mại; Grist làm data store |
| Secrets | Secret store của hệ điều hành | Infisical khi có nhiều máy/người dùng | OpenBao ở quy mô đầu |
| Monitoring | Structured logs + OpenTelemetry | Prometheus/Grafana khi cần số liệu dài hạn | Sentry self-host ở giai đoạn đầu |
| Điều phối LLM | Adapter nhà cung cấp mỏng + schema có kiểu | PydanticAI/Instructor; LiteLLM khi cần routing lớn | LangChain làm lõi toàn hệ thống |
| AI local fallback | Ollama để vận hành thử; llama.cpp để tối ưu sâu | vLLM khi có GPU server lớn hơn | vLLM trên RTX 4070 SUPER 12 GB làm mặc định |

## 5. Đánh giá chi tiết theo năng lực

### 5.1. Thu thập RSS/Atom

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [feedparser](https://feedparser.readthedocs.io/en/stable/) / [GitHub](https://github.com/kurtmckee/feedparser) | BSD-style | Push 07-09-2026; release 6.0.14 ngày 30-07-2026; khoảng 62 contributor; rất tích cực | API cao; có test, CI và tài liệu đầy đủ; hỗ trợ nhiều phiên bản RSS/Atom | 9.0 | Phù hợp nhất cho việc parse feed trong pipeline riêng. Không cung cấp scheduler hay quản lý nguồn, đúng với ranh giới năng lực này. |
| [RSSHub](https://docs.rsshub.app/) / [GitHub](https://github.com/DIYgod/RSSHub) | AGPL-3.0 | Push 11-09-2026; khoảng 1.712 contributor; rất tích cực; không duy trì release GitHub đều | API route ở mức trung bình; có test, CI và tài liệu lớn | 7.7 | Hữu ích để tạo feed cho website không có RSS. Không nên là phụ thuộc duy nhất vì route dễ hỏng khi trang nguồn đổi và AGPL cần được xem xét khi triển khai dịch vụ. |
| [Miniflux](https://miniflux.app/docs/) / [GitHub](https://github.com/miniflux/v2) | Apache-2.0 | Push 12-09-2026; release 2.3.3 ngày 24-07-2026; khoảng 333 contributor; rất tích cực | REST API cao; CI và tài liệu tốt | 6.8 | Là ứng dụng đọc feed hoàn chỉnh. Có thể tham khảo cách quản lý feed nhưng chồng lấn với dữ liệu, trạng thái và UI riêng của dự án. |

**Kết luận nghiên cứu:** ưu tiên kiểm chứng `feedparser` cho feed chuẩn; chỉ dùng RSSHub như adapter nguồn có kiểm soát. RSS không thay thế crawler vì nhiều nguồn không cung cấp đủ nội dung hoặc media trong feed.

### 5.2. Tải trang và crawl web

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [Scrapy](https://docs.scrapy.org/en/latest/) / [GitHub](https://github.com/scrapy/scrapy) | BSD-3-Clause | Push và release 2.19.0 ngày 10-09-2026; khoảng 745 contributor; rất tích cực | API cao; có test, CI, selector, retry, throttle, item pipeline và tài liệu sâu | 8.9 | Ứng viên chính cho crawl nhiều nguồn theo lịch. Cho phép cô lập logic theo nguồn và xuất dữ liệu có cấu trúc. |
| [Playwright](https://playwright.dev/) / [GitHub](https://github.com/microsoft/playwright) | Apache-2.0 | Push 11-09-2026; release 1.63.0 ngày 04-09-2026; khoảng 806 contributor; rất tích cực | API cao nhưng bám theo browser; test và tài liệu rất tốt | 7.8 | Dùng fallback cho trang cần JavaScript, đăng nhập hợp lệ hoặc tương tác DOM. Không nên chạy cho mọi URL vì tốn RAM/CPU và phức tạp vận hành. |
| [curl_cffi](https://curl-cffi.readthedocs.io/) / [GitHub](https://github.com/lexiforest/curl_cffi) | MIT | Push 04-09-2026; release 0.16.3 ngày 02-09-2026; khoảng 69 contributor; rất tích cực | API trung bình; có test, CI và tài liệu | 7.1 | Có thể dùng khi HTTP client thông thường không tương thích một nguồn. Khả năng mô phỏng browser không tạo ra quyền truy cập và có rủi ro bảo trì theo thay đổi chống bot. |

**Kết luận nghiên cứu:** mô hình phù hợp là HTTP crawler trước, browser automation sau. Việc ưu tiên nguồn Tier 1/2/3 và chính sách retry phải nằm ngoài crawler để không khóa nghiệp vụ vào một công cụ.

### 5.3. Trích xuất và làm sạch bài báo

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [Trafilatura](https://trafilatura.readthedocs.io/) / [GitHub](https://github.com/adbar/trafilatura) | Apache-2.0 | Push 11-09-2026; release 2.2.0 ngày 31-07-2026; khoảng 74 contributor; rất tích cực | API trung bình-cao; có test, CI, docs; trả text, metadata, JSON, Markdown và XML | 9.0 | Ứng viên chính để lấy nội dung, metadata và liên kết từ HTML. Cần giữ raw HTML/phiên bản nguồn vì thuật toán trích xuất có thể thay đổi. |
| [Mozilla Readability](https://github.com/mozilla/readability) | Apache-2.0 | Push 04-08-2026; khoảng 99 contributor; tích cực | API cao và nhỏ; có test tự động, changelog và README; cần DOM và sanitizer riêng | 8.1 | Fallback tốt cho trang mà Trafilatura lấy thiếu. Đầu ra từ HTML không tin cậy phải được sanitize trước khi hiển thị. |
| [jusText](https://github.com/miso-belica/jusText) | BSD-2-Clause | Push 18-08-2026; release 3.0.2 ngày 25-02-2025; khoảng 5 contributor; tích cực nhưng cộng đồng nhỏ | API trung bình; có test, CI và docs | 7.3 | Hữu ích làm bộ so sánh hoặc fallback cho boilerplate removal, nhưng metadata và hệ sinh thái nhỏ hơn Trafilatura. |
| [Newspaper3k](https://github.com/codelucas/newspaper) | MIT | Push 31-08-2026; release gần nhất 0.0.9 ngày 17-12-2014; khoảng 103 contributor | Có test/docs nhưng release hygiene yếu; API trung bình-thấp | 5.8 | Không ưu tiên làm parser chính vì khoảng cách quá lớn giữa release công bố và mã hiện tại, làm tăng rủi ro tái lập môi trường. |

**Kết luận nghiên cứu:** dùng bộ dữ liệu trang thật để so sánh Trafilatura, Readability và jusText; không tin tuyệt đối một extractor. Phần làm sạch phải giữ dấu vết từ nội dung đã trích ngược về raw source.

### 5.4. Tín hiệu hot/trending

| Ứng viên và nguồn | License/quyền truy cập | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [GDELT](https://www.gdeltproject.org/data.html) | Dữ liệu mở theo điều kiện công bố của GDELT; phải kiểm tra quyền của nội dung gốc | Dịch vụ dữ liệu còn hoạt động; không có contributor GitHub đại diện | API/dataset trung bình; tài liệu chính thức có, nhưng schema và khối lượng dữ liệu cần thử nghiệm | 7.8 | Có giá trị như tín hiệu sự kiện và độ phủ toàn cầu, không phải nguồn cấp toàn văn thay cho bài gốc. |
| Tín hiệu nội bộ từ nguồn Tier 1/2/3 | Quyền tùy từng nguồn | Phụ thuộc danh sách nguồn và lịch quét | API do dự án định nghĩa sau; có thể kiểm thử bằng dữ liệu đã thu thập | 8.4 | Phù hợp nhất với tiêu chí của chính sản phẩm: độ mới, số nguồn cùng đưa tin, tốc độ tăng bài và nhóm chủ đề. Chưa phải thiết kế thuật toán. |
| [Google Trends API](https://developers.google.com/search/apis/trends) | Dịch vụ Google; cần đăng ký Alpha | API Alpha tại ngày nghiên cứu | API thấp do Alpha; tài liệu chính thức có; quyền truy cập không được bảo đảm | 5.6 | Có thể bổ sung tín hiệu nhu cầu tìm kiếm nếu được cấp quyền. Không được dùng làm phụ thuộc bắt buộc ở phiên bản đầu. |
| [TikTok Research API](https://developers.tiktok.com/products/research-api) | Chỉ dành cho nhà nghiên cứu đủ điều kiện và mục đích phi thương mại vì lợi ích công | Dịch vụ hoạt động | API có tài liệu nhưng quyền truy cập không phù hợp use case thương mại | 2.2 | Loại khỏi nguồn tín hiệu sản xuất hiện tại. Không được thiết kế hệ thống dựa vào khả năng truy cập này. |

**Kết luận nghiên cứu:** chưa có API chính thức, ổn định và phù hợp quyền truy cập để đại diện trực tiếp cho “đang viral trên TikTok Mỹ”. `QUALITY-OPEN-005` chưa thể đóng; proxy nên được kiểm chứng bằng tín hiệu đa nguồn và dữ liệu nội bộ.

### 5.5. Lưu dữ liệu có cấu trúc

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [PostgreSQL](https://www.postgresql.org/docs/current/) / [GitHub mirror](https://github.com/postgres/postgres) | PostgreSQL License, tương tự BSD/MIT | Push 12-09-2026; release theo lịch ổn định; GitHub mirror khoảng 58 contributor, trang dự án ghi nhận hơn 725 contributor toàn lịch sử | SQL/API rất cao; test và tài liệu sâu; giao dịch, JSON, index, full-text search | 9.2 | Ứng viên mạnh nhất cho nguồn sự thật có cấu trúc, trạng thái workflow và truy vết. Chi phí vận hành phải được so sánh giữa self-host và managed ở bước kiến trúc. |
| [SQLite](https://www.sqlite.org/docs.html) / [GitHub mirror](https://github.com/sqlite/sqlite) | Public domain | Push 11-09-2026; khoảng 38 contributor trên mirror; rất tích cực | API rất cao; test nổi tiếng và tài liệu đầy đủ; một tệp, vận hành nhẹ | 7.6 | Rất phù hợp cho prototype hoặc dữ liệu cục bộ một tiến trình. Không phù hợp làm nơi phối hợp cloud và desktop đồng thời nếu có nhiều writer. |
| [DuckDB](https://duckdb.org/docs/) / [GitHub](https://github.com/duckdb/duckdb) | MIT | Push 11-09-2026; release 1.5.5 ngày 22-07-2026; khoảng 880 contributor; rất tích cực | SQL/API cao; có test, CI và docs; tối ưu phân tích cột | 7.0 | Hữu ích cho phân tích offline, báo cáo và benchmark. Không ưu tiên làm cơ sở dữ liệu giao dịch/hàng chờ chính. |

**Kết luận nghiên cứu:** PostgreSQL là ứng viên ưu tiên, chưa phải quyết định. Vai trò Google Sheets, gồm nơi lưu chính, giao diện phụ, đồng bộ hoặc xuất/nhập, vẫn phải được đánh giá ở bước kiến trúc theo yêu cầu người dùng. Không loại vai trò lưu chính trước kết luận kiến trúc được duyệt.

### 5.6. Tìm kiếm và lập chỉ mục

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [PostgreSQL Full Text Search](https://www.postgresql.org/docs/current/textsearch.html) | PostgreSQL License | Cùng vòng đời PostgreSQL | API cao; có index GIN/GiST, ranking, parser và dictionary; test/docs đầy đủ | 8.9 | Đủ để bắt đầu tìm bài, sự kiện và metadata mà không thêm dịch vụ. Cần benchmark tiếng Anh, fuzzy match và quy mô dữ liệu thật. |
| [Meilisearch](https://www.meilisearch.com/docs/) / [GitHub](https://github.com/meilisearch/meilisearch) | Community MIT; Enterprise BUSL-1.1 | Push 10-09-2026; release 1.53.2 ngày 07-09-2026; khoảng 258 contributor; rất tích cực | HTTP API cao; docs/CI tốt; tìm kiếm typo-tolerant dễ tích hợp | 8.0 | Ứng viên mở rộng nếu trải nghiệm tìm kiếm hoặc tốc độ vượt khả năng PostgreSQL. Phải tránh vô tình phụ thuộc tính năng Enterprise. |
| [Typesense](https://typesense.org/docs/) / [GitHub](https://github.com/typesense/typesense) | GPL-3.0 | Push 01-09-2026; release 30.2 ngày 19-04-2026; khoảng 58 contributor; rất tích cực | API cao; test/docs tốt | 7.3 | Nhẹ hơn OpenSearch và có search-as-you-type tốt, nhưng GPL cần đánh giá cách phân phối và không cần thiết trước khi PostgreSQL được benchmark. |
| [OpenSearch](https://docs.opensearch.org/latest/) / [GitHub](https://github.com/opensearch-project/OpenSearch) | Apache-2.0 | Push 11-09-2026; release 3.8.0 ngày 05-08-2026; khoảng 2.207 contributor; rất tích cực | API cao; test/docs phong phú | 6.1 | Mạnh và mở rộng tốt nhưng tốn RAM, vận hành và chi phí quá mức cho giai đoạn đầu một người dùng. |

**Kết luận nghiên cứu:** bắt đầu đánh giá bằng PostgreSQL FTS; chỉ thêm search engine riêng khi benchmark chứng minh có khoảng thiếu cụ thể.

### 5.7. Phát hiện trùng và liên kết bài thành sự kiện

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [DataSketch](https://ekzhu.com/datasketch/) / [GitHub](https://github.com/ekzhu/datasketch) | MIT | Push 09-08-2026; release 2.0.0 ngày 05-07-2026; khoảng 36 contributor; rất tích cực | API trung bình-cao; có test, CI và docs; MinHash/LSH | 8.3 | Phù hợp lọc nhanh văn bản gần trùng trước khi chạy embedding hoặc AI tốn chi phí. Không tự hiểu cùng một sự kiện được kể khác từ. |
| [Sentence Transformers](https://www.sbert.net/) / [GitHub](https://github.com/huggingface/sentence-transformers) | Apache-2.0 cho mã; model có license riêng | Push 11-09-2026; release 6.0.1 ngày 31-08-2026; khoảng 305 contributor; rất tích cực | API trung bình-cao; test/docs tốt; nhiều model embedding | 8.8 | Phù hợp đo gần nghĩa, nhóm bài và tìm tài nguyên liên quan. Phải chọn model tiếng Anh phù hợp và lưu version model. |
| [dedupe](https://docs.dedupe.io/) / [GitHub](https://github.com/dedupeio/dedupe) | MIT | Push 29-07-2025; khoảng 72 contributor; hoạt động chậm hơn | API trung bình; có test, CI và docs; thiên về entity resolution có huấn luyện | 6.5 | Có giá trị tham khảo cho liên kết bản ghi, nhưng nhu cầu gắn bài-sự kiện theo thời gian và ngữ nghĩa không khớp hoàn toàn. |
| LLM-only | Phụ thuộc nhà cung cấp/model | Hoạt động và API thay đổi theo dịch vụ | Khó tái lập; test được nếu khóa model/prompt nhưng chi phí và độ bất định cao | 5.0 | Không nên là lớp duy nhất vì có thể gộp nhầm, khó giải thích và tốn chi phí. Chỉ phù hợp làm lớp quyết định cuối cho trường hợp mơ hồ. |

**Kết luận nghiên cứu:** ứng viên ưu tiên là pipeline nhiều tầng: chuẩn hóa URL/hash, MinHash/LSH, embedding, rồi AI cho trường hợp khó. R06 chốt giữ riêng khi liên kết chưa chắc, không thêm bước duyệt bắt buộc. R07/R22 loại bài đăng lại khỏi tin độc lập nhưng vẫn lấy media mới; ngưỡng DATA-OPEN-005/006 còn cần benchmark.

### 5.8. Quản lý media và metadata

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| Metadata nghiệp vụ riêng + kho tệp tách biệt | Không phụ thuộc license dự án ngoài | Được kiểm soát bởi dự án | Contract chỉ được định nghĩa ở bước 11; test được theo `MediaAsset`, `AssetAssociation`, checksum và provenance | 9.0 | Phù hợp nhất với mô hình dữ liệu đã duyệt: tệp lớn ở kho tệp, metadata/trạng thái ở nguồn dữ liệu có cấu trúc. Đây là hướng nghiên cứu, chưa chọn nơi lưu. |
| [MediaCMS](https://github.com/mediacms-io/mediacms) | AGPL-3.0 | Push 11-09-2026; release 8.4.0 ngày 25-08-2026; khoảng 47 contributor; rất tích cực | API trung bình; có test/docs; cung cấp ingest, transcode và catalog | 6.7 | Có thể tham khảo mô hình quản lý video. Không khớp hoàn toàn vì sản phẩm cần provenance bài-sự kiện-hook-preset và vòng đời staging riêng. |
| [Immich](https://immich.app/docs/) / [GitHub](https://github.com/immich-app/immich) | AGPL-3.0 | Push 12-09-2026; release 3.2.0 ngày 10-09-2026; khoảng 997 contributor; rất tích cực | API ứng dụng ở mức trung bình; test/docs tốt | 5.9 | Mạnh về thư viện ảnh/video cá nhân và tìm kiếm. Không nên làm lõi nghiệp vụ vì schema, lifecycle và mục tiêu sản phẩm khác. |
| [PhotoPrism](https://docs.photoprism.app/) / [GitHub](https://github.com/photoprism/photoprism) | AGPL-3.0 | Push 12-09-2026; release 260728 ngày 28-07-2026; khoảng 196 contributor; rất tích cực | API trung bình; có test/docs | 5.6 | Có thể tham khảo indexing và thumbnail, nhưng chồng lấn UI/catalog và không giải quyết quan hệ sản xuất video. |

**Kết luận nghiên cứu:** không dùng một digital asset manager có sẵn làm nguồn sự thật. Có thể tái sử dụng công cụ xử lý media, nhưng metadata nghiệp vụ cần giữ độc lập để thay kho lưu trữ mà không mất lịch sử.

### 5.9. Phân tích video, audio và ảnh

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [FFmpeg/ffprobe](https://ffmpeg.org/documentation.html) / [GitHub](https://github.com/FFmpeg/FFmpeg) | LGPL-2.1+ mặc định; build có thành phần GPL làm toàn bộ build thành GPL | Push 12-09-2026; khoảng 2.723 contributor; rất tích cực | CLI/API rất cao; có FATE test và tài liệu rộng | 9.3 | Ưu tiên cho duration, stream, codec, frame rate, kiểm tra file và trích frame. Phải khóa build và ghi lại cấu hình license của binary dùng thật. |
| [PyAV](https://pyav.org/docs/stable/) / [GitHub](https://github.com/PyAV-Org/PyAV) | BSD-3-Clause; vẫn phụ thuộc license build FFmpeg | Push 02-09-2026; release 18.1.0 ngày 12-08-2026; khoảng 119 contributor; rất tích cực | API trung bình-cao; có test, CI và docs; bám sát cấu trúc FFmpeg | 8.1 | Phù hợp khi cần đọc frame/timestamp trực tiếp trong tiến trình AI. Không thay FFmpeg CLI cho render/filter graph phức tạp. |
| [PySceneDetect](https://www.scenedetect.com/docs/latest/) / [GitHub](https://github.com/Breakthrough/PySceneDetect) | BSD-3-Clause | Push 12-09-2026; release 0.7.1 ngày 22-07-2026; khoảng 47 contributor; rất tích cực | API trung bình-cao; có test, CI và docs | 8.5 | Hữu ích phát hiện cảnh để chọn đoạn clip, thumbnail hoặc tránh cắt giữa cảnh. Không nhận biết ý nghĩa câu chuyện. |
| [OpenCV](https://docs.opencv.org/) / [GitHub](https://github.com/opencv/opencv) | Apache-2.0 | Push 11-09-2026; release 5.0.0 ngày 06-06-2026; khoảng 2.570 contributor; rất tích cực | API cao nhưng lớn; test/docs sâu | 7.8 | Phù hợp cho frame analysis, face box, màu, blur và computer vision tùy biến. Không nên dùng để thay encoder/compositor chuyên dụng. |

**Kết luận nghiên cứu:** ffprobe là lớp kiểm tra đầu vào/đầu ra ưu tiên; PySceneDetect và OpenCV chỉ chạy khi nghiệp vụ cần để tiết kiệm thời gian và VRAM.

### 5.10. Nhận dạng khuôn mặt và xử lý ảnh nhạy cảm

Không có ứng viên đơn lẻ nào trong khảo sát chứng minh sẵn khả năng đạt đồng thời 95% recall cho khuôn mặt trẻ em, máu me và vũ khí trên tập ảnh tin tức của dự án. Các API moderation chủ yếu phân loại toàn ảnh; việc che đúng vùng vẫn cần detector/segmentation hoặc người dùng sửa.

| Ứng viên và nguồn | License/quyền sử dụng | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/guide) / [GitHub](https://github.com/google-ai-edge/mediapipe) | Apache-2.0; model/task có điều kiện riêng nếu tải ngoài | Push 11-09-2026; release 1.0.0 ngày 28-07-2026; khoảng 116 contributor; rất tích cực | API trung bình-cao; có test/docs; face detection/landmarks | 8.0 | Phù hợp để tìm vùng mặt nhằm blur. Không tự xác định chắc chắn người trong ảnh là trẻ em. |
| [OpenCV](https://opencv.org/) | Apache-2.0 | Như mục 5.9 | API cao; test/docs đầy đủ | 7.7 | Phù hợp thực hiện blur, mask, đổi màu và chạy detector ONNX. Model nhận diện phải được đánh giá và cấp phép riêng. |
| [Google Cloud Vision SafeSearch](https://docs.cloud.google.com/vision/docs/detecting-safe-search) | Dịch vụ trả phí của Google Cloud | Dịch vụ hoạt động; không áp dụng contributor | REST API cao; docs chính thức; trả mức likelihood cho adult, spoof, medical, violence, racy | 7.2 | Tốt làm tín hiệu phân loại toàn ảnh. Không có nhãn chuyên biệt cho tuổi khuôn mặt hay vị trí máu/vũ khí; không đủ làm pipeline duy nhất. |
| [Amazon Rekognition Moderation](https://docs.aws.amazon.com/rekognition/latest/dg/moderation-api.html) | Dịch vụ trả phí AWS | Dịch vụ hoạt động; model moderation có version | API cao; docs chính thức; taxonomy nhiều tầng, confidence và custom adapter | 7.4 | Phạm vi moderation chi tiết hơn, có thể làm lớp cloud fallback. Vẫn cần benchmark label và tọa độ cho đúng use case ảnh tin tức. |
| [OpenNSFW2](https://github.com/bhky/opennsfw2) | MIT cho mã; cần kiểm tra model/data | Push 29-08-2026; release 0.18.0 ngày 05-05-2026; 2 contributor; tích cực nhưng bus factor cao | API trung bình; có test/docs | 5.6 | Chỉ phù hợp tín hiệu NSFW hẹp. Không bao phủ trẻ em, máu me và vũ khí. |
| [NudeNet](https://github.com/notAI-tech/NudeNet) | AGPL-3.0; weights cần audit riêng | Push 09-06-2026; release weights gần nhất 30-06-2024; khoảng 7 contributor | API trung bình; docs/test hạn chế hơn | 5.1 | Phạm vi nudity không khớp trọng tâm đã xác nhận; AGPL và weights tăng rủi ro. |

**Kết luận nghiên cứu:** ưu tiên một pipeline kết hợp detector vùng mặt/vật thể, classifier toàn ảnh và phép biến đổi deterministic; cloud moderation chỉ là ứng viên fallback. `QUALITY-PROPOSED-010` đã được phê duyệt nên lựa chọn cuối phải qua bộ mẫu gắn nhãn của chính dự án, không dựa vào benchmark công bố chung.

### 5.11. Nhận dạng tiếng nói và tạo phụ đề

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT; model Whisper có license riêng được công bố | Push 19-11-2025; release 1.2.1 ngày 31-10-2025; khoảng 47 contributor; tích cực | API trung bình-cao; có test/CI/docs; batching, VAD và word timestamps | 9.0 | Ứng viên runtime chính để tạo transcript/timestamp với chi phí local thấp. Cần benchmark chia sẻ GPU với các bước AI khác trên 12 GB VRAM. |
| [WhisperX](https://github.com/m-bain/whisperX) | BSD-2-Clause; model alignment/diarization có license riêng | Push 30-08-2026; release 3.8.6 ngày 25-05-2026; khoảng 118 contributor; rất tích cực | API trung bình; có test/CI/docs; forced alignment và word-level timestamps | 8.6 | Dùng khi phụ đề cần đồng bộ từng từ chính xác hơn. Tăng dependency, model và VRAM; diarization không cần thiết cho lời dẫn một giọng. |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | MIT; model riêng | Push và release 1.9.4 ngày 11-09-2026; khoảng 997 contributor; rất tích cực | C/C++ API và CLI cao; có test/CI/docs; nhiều backend | 8.2 | Fallback tốt, triển khai gọn và có thể chạy CPU/GPU. Tích hợp alignment nâng cao kém trực tiếp hơn WhisperX. |
| [OpenAI Whisper](https://github.com/openai/whisper) | MIT; model được công bố cùng dự án | Push 31-08-2026; release 20250625; khoảng 83 contributor; tích cực | API trung bình; có test/CI/README; implementation tham chiếu | 7.5 | Là baseline chính xác để đối chiếu. Không ưu tiên runtime mặc định vì hiệu năng thường kém hơn các implementation tối ưu. |

**Kết luận nghiên cứu sau R03:** phụ đề tiếng Anh gắn vào video với timing từng từ đã bắt buộc. faster-whisper và WhisperX vẫn là ứng viên cần đối chiếu với script/voice thực dùng; yêu cầu này không tự chọn WhisperX. Ngưỡng timestamp và phương án căn lời phải được kiểm chứng.

### 5.12. Text-to-Speech

Chất lượng giọng kể, cảm xúc, chi phí và quyền dùng voice/model xung đột trực tiếp. Vì chưa có benchmark giọng tiếng Anh theo năm preset, năng lực này **chưa đủ dữ liệu để chốt một nhà cung cấp**.

| Ứng viên và nguồn | License/chi phí | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [Gemini TTS](https://ai.google.dev/gemini-api/docs/speech-generation) | Dịch vụ Google; giá/quota theo API; TTS đang ở Preview | Dịch vụ được cập nhật trong 09-2026; không áp dụng contributor | API thấp-trung bình vì Preview; docs chính thức; điều khiển style, accent, pace và tone bằng ngôn ngữ tự nhiên | 8.0 | Rất phù hợp nhu cầu nhiều phong cách nếu chất lượng và chi phí đạt. Không được làm phụ thuộc duy nhất khi API còn Preview và tài khoản thuê bao không mặc nhiên đồng nghĩa có quota API miễn phí. |
| [ElevenLabs TTS](https://elevenlabs.io/docs/overview/capabilities/text-to-speech) / [Pricing](https://elevenlabs.io/pricing/api) | Dịch vụ thương mại; khoảng 0,05-0,10 USD/1.000 ký tự tùy model tại ngày nghiên cứu | Dịch vụ tích cực | API cao; tài liệu đầy đủ; model biểu cảm, nhiều voice, có request/cost metadata | 7.7 | Chất lượng tiềm năng cao nhưng 100 video/ngày có thể vượt ngân sách 50 USD/tháng. Phù hợp làm benchmark chất lượng hoặc fallback có hạn mức, không mặc định toàn bộ sản lượng. |
| [Piper](https://github.com/OHF-Voice/piper1-gpl) / [Voice docs](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md) | GPL-3.0 cho engine; mỗi voice có model card và có thể mang điều kiện hạn chế | Push 09-09-2026; release 1.8.0 ngày 04-09-2026; khoảng 16 contributor; rất tích cực | API trung bình; CLI, Python/C++ API, server, test và docs | 7.5 | Local, nhanh, chi phí biên thấp và phù hợp fallback. Chất lượng/cảm xúc có thể không đạt preset chuyên nghiệp; từng voice phải audit license trước khi dùng. |
| [Kokoro](https://github.com/hexgrad/kokoro) | Apache-2.0 cho mã; model/voice cần kiểm tra riêng | Push 06-08-2025; khoảng 23 contributor; không có release GitHub; hoạt động chậm | API thấp-trung bình; có test/CI/README nhưng release/versioning yếu | 7.0 | Nhẹ và có tiềm năng chất lượng local tốt. Rủi ro vòng đời và packaging cao hơn Piper; chỉ nên vào benchmark, chưa làm mặc định. |
| [MeloTTS](https://github.com/myshell-ai/MeloTTS) | MIT cho mã; model/data riêng | Push 24-12-2024; release 0.1.2 ngày 01-03-2024; khoảng 7 contributor; chậm | API trung bình-thấp; docs/test có nhưng hoạt động yếu | 5.7 | Không ưu tiên cho nền tảng duy trì nhiều năm khi có ứng viên local tích cực hơn. |
| [Coqui TTS](https://github.com/coqui-ai/TTS) | MPL-2.0; model riêng | Push 16-08-2024; release 0.22.0 ngày 12-12-2023; khoảng 166 contributor; chậm | API từng khá rộng; có test/docs nhưng kho chính không còn nhịp cập nhật phù hợp | 5.4 | Không ưu tiên cho dự án mới do maintenance risk. |

**Kết luận nghiên cứu:** tổ chức một benchmark mù giữa Gemini TTS, ElevenLabs, Piper và Kokoro trên cùng 20 đoạn thoại, năm phong cách và nhiều lần tạo lại. Đo mức tự nhiên, phát âm tên riêng, cảm xúc, ổn định, thời gian, VRAM và chi phí thực. Chỉ sau benchmark mới chọn primary/fallback.

### 5.13. Biến đổi ảnh và tạo thumbnail

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [ImageMagick](https://imagemagick.org/) / [GitHub](https://github.com/ImageMagick/ImageMagick) | ImageMagick License, permissive | Push 12-09-2026; release 7.1.2-31 ngày 03-09-2026; khoảng 228 contributor; rất tích cực | CLI/API cao; test và docs sâu | 8.8 | Phù hợp resize, crop, color transform, composite, text/icon và tạo thumbnail deterministic. Cần kiểm soát resource limits khi xử lý tệp không tin cậy. |
| [OpenCV](https://docs.opencv.org/) | Apache-2.0 | Như mục 5.9 | API cao; test/docs đầy đủ | 8.5 | Phù hợp mask theo vùng phát hiện, blur, đổi màu và xử lý pixel. Tạo chữ/composition đồ họa không thuận tiện bằng công cụ chuyên dụng. |
| [FFmpeg image filters](https://ffmpeg.org/ffmpeg-filters.html) | LGPL/GPL tùy build | Như mục 5.9 | Filter API/CLI cao; test/docs rộng | 7.9 | Hữu ích khi ảnh đã nằm trong timeline video, tránh thêm bước encode. Không phải công cụ thuận tiện nhất để dựng thumbnail phức tạp. |

**Kết luận nghiên cứu:** ImageMagick và OpenCV bổ sung nhau, không phải lựa chọn loại trừ. Bộ icon/mũi tên/dấu cảm thán phải có nguồn và quyền sử dụng rõ riêng; phần mềm composite không giải quyết quyền của asset.

### 5.14. FFmpeg wrapper

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| FFmpeg/ffprobe CLI qua adapter mỏng | LGPL/GPL tùy build | Như mục 5.9 | CLI rất ổn định; log và exit code rõ; test/docs chính thức | 9.2 | Giữ đầy đủ tính năng, dễ tái hiện lệnh và debug theo module. Adapter phải tránh ghép chuỗi lệnh không an toàn và phải lưu version/build. |
| [PyAV](https://pyav.org/docs/stable/) | BSD-3-Clause + FFmpeg build | Như mục 5.9 | API trung bình-cao; test/docs tốt | 8.0 | Dùng cho frame-level processing trong cùng tiến trình. Không thay thế toàn bộ filter graph và CLI diagnostics. |
| [python-ffmpeg](https://github.com/jonghwanhyeon/python-ffmpeg) | MIT | Push 03-09-2026; release GitHub 2.0.12 ngày 15-04-2024; khoảng 14 contributor; tích cực | API trung bình; có test, CI và docs | 7.3 | Wrapper gọn, có progress/event. Cộng đồng nhỏ và vẫn cần hiểu FFmpeg; giá trị hơn adapter mỏng phải được chứng minh. |
| [ffmpeg-python](https://github.com/kkroening/ffmpeg-python) | Apache-2.0 | Push gần nhất 04-08-2024; không có release gần đây; khoảng 25 contributor; chậm | API trung bình; có test/docs nhưng maintenance yếu | 5.5 | Không ưu tiên làm phụ thuộc lõi mới dù phổ biến, do nhịp duy trì và giới hạn khi filter graph phức tạp. |

**Kết luận nghiên cứu:** gọi FFmpeg trực tiếp qua adapter mỏng là ứng viên ưu tiên. Wrapper không loại bỏ nhu cầu hiểu codec/filter/version và có thể che mất thông tin debug cần thiết.

### 5.15. Video composition và render

| Ứng viên và nguồn | License/chi phí | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [FFmpeg filter graph](https://ffmpeg.org/ffmpeg-filters.html) | LGPL/GPL tùy build | Như mục 5.9 | API/CLI cao; test/docs sâu; hỗ trợ overlay, concat, drawtext, audio mix, transition | 9.1 | Phù hợp nhất cho throughput, hardware encoding và render deterministic. Độ phức tạp filter graph phải được cô lập sau contract rõ. |
| [MoviePy](https://zulko.github.io/moviepy/) / [GitHub](https://github.com/Zulko/moviepy) | MIT | Push 26-08-2026; release 2.2.1 ngày 21-05-2025; khoảng 193 contributor; rất tích cực | API trung bình-cao; test, CI và docs tốt | 7.2 | Dễ thử nghiệm composition và preset. Cần benchmark bộ nhớ/tốc độ trước mục tiêu 100 video/12 giờ; không nên giả định đạt throughput. |
| [MLT](https://www.mltframework.org/docs/) / [GitHub](https://github.com/mltframework/mlt) | LGPL-2.1 | Push 09-09-2026; release 7.40.0 ngày 25-06-2026; khoảng 140 contributor; rất tích cực | API trung bình-cao; có test/docs; timeline engine lâu năm | 6.9 | Có giá trị nếu sau này cần timeline/project model phong phú. Giai đoạn đầu có thể quá nặng so với video template 61-70 giây. |
| [Remotion](https://www.remotion.dev/) / [GitHub](https://github.com/remotion-dev/remotion) / [License](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) | License riêng; miễn phí cho cá nhân/tổ chức lợi nhuận tối đa 3 người theo điều khoản hiện tại; automation/commercial cần kiểm tra gói và điều khoản | Push 11-09-2026; release 4.0.523 ngày 09-09-2026; khoảng 421 contributor; rất tích cực | API trung bình-cao; test/docs rất tốt; composition bằng React | 6.3 | Trải nghiệm phát triển tốt nhưng tạo thêm browser/render stack và rủi ro license/chi phí khi sản phẩm tự động hóa mở rộng. Không ưu tiên dưới ngân sách hiện tại. |

**Kết luận nghiên cứu:** FFmpeg là ứng viên render lõi; MoviePy chỉ nên dùng trong proof-of-capability nếu rút ngắn thời gian thử. Remotion không bị loại vĩnh viễn, nhưng chưa phù hợp làm mặc định khi ngân sách và mô hình automation còn nhạy cảm với license.

### 5.16. Workflow bền vững và job queue

Yêu cầu “tiếp tục từ trạng thái gần nhất”, tách cloud collection khỏi desktop render và không mất công việc sau gián đoạn khiến đây không chỉ là hàng đợi message đơn giản.

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [Temporal](https://docs.temporal.io/) / [GitHub](https://github.com/temporalio/temporal) | MIT | Push 12-09-2026; release 1.32.0 ngày 11-09-2026; khoảng 302 contributor; rất tích cực | API cao, versioned SDK; test/docs sâu; durable execution, retry, timeout, timer và resume | 8.8 | Khớp nhất với workflow dài, có checkpoint và desktop offline. Đổi lại cần vận hành server/worker và học determinism; phải proof-of-capability trước khi chọn. |
| [Prefect](https://docs.prefect.io/v3/) / [GitHub](https://github.com/PrefectHQ/prefect) | Apache-2.0 cho bản open-source | Push 11-09-2026; release 3.8.5 ngày 03-09-2026; khoảng 474 contributor; rất tích cực | API trung bình-cao; test/docs tốt; retries, deployments, schedules, UI | 8.1 | Dễ quan sát data workflow và thử nghiệm hơn Temporal. Cần kiểm tra hành vi resume ở cấp bước, offline worker và ranh giới tính năng cloud. |
| [Celery](https://docs.celeryq.dev/en/stable/) / [GitHub](https://github.com/celery/celery) | BSD-3-Clause | Push 10-09-2026; release 5.6.3 ngày 26-03-2026; khoảng 1.556 contributor; rất tích cực | API cao; test/docs trưởng thành; retry, routing và ecosystem lớn | 7.5 | Tốt cho task queue, nhưng trạng thái workflow dài/checkpoint phải tự thiết kế nhiều hơn. Windows worker và broker/backend làm tăng rủi ro vận hành cục bộ. |
| [BullMQ](https://docs.bullmq.io/) / [GitHub](https://github.com/taskforcesh/bullmq) | MIT | Push 12-09-2026; release 1.2.9 ngày 10-09-2026; khoảng 208 contributor; rất tích cực | API cao; test/docs tốt; Redis-based queue | 7.4 | Tốt nếu runtime chính được chọn là TypeScript/Node. Chưa thể ưu tiên vì ngôn ngữ và runtime chưa được quyết định. |
| [Dramatiq](https://dramatiq.io/) / [GitHub](https://github.com/Bogdanp/dramatiq) | LGPL-3.0 | Push 02-09-2026; release 2.2.1; khoảng 132 contributor; rất tích cực | API cao và gọn; test/docs tốt | 7.0 | Nhẹ hơn Celery nhưng vẫn là task queue, không tự giải quyết toàn bộ durable workflow nhiều bước. |

**Kết luận nghiên cứu:** Temporal là ứng viên dẫn đầu về độ bền; Prefect là ứng viên dẫn đầu về tốc độ kiểm chứng và quan sát. Đây là một quyết định kiến trúc lớn chưa được chốt. Cần thử tình huống mất điện, worker offline, retry từng bước và chạy lại có tính idempotent.

### 5.17. Scheduler

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| Schedule/timer của Temporal | MIT | Cùng vòng đời Temporal | API cao; lưu timer bền vững và gắn với workflow | 8.7 | Ưu tiên nếu Temporal được chọn, vì tránh hai nguồn sự thật cho lịch và retry. |
| Schedule/deployment của Prefect | Apache-2.0 | Cùng vòng đời Prefect | API trung bình-cao; UI/docs tốt | 8.2 | Ưu tiên nếu Prefect được chọn. Cần xác minh lịch vẫn chạy khi desktop tắt trên topology triển khai thực. |
| [APScheduler](https://apscheduler.readthedocs.io/) / [GitHub](https://github.com/agronholm/apscheduler) | MIT | Push 10-09-2026; release 3.11.3 ngày 28-06-2026; khoảng 69 contributor; rất tích cực | API cao; test/CI/docs tốt; cron, interval và persistent data store | 8.4 | Phù hợp khi chỉ cần lịch quét một lần/ngày và workflow engine không cung cấp scheduler. Không nên tạo scheduler thứ hai nếu nền tảng workflow đã đảm nhiệm tốt. |

**Kết luận nghiên cứu:** scheduler nên đi cùng nguồn trạng thái workflow đã chọn. Thời điểm chạy cụ thể vẫn chưa được chốt; lựa chọn “lúc có nhiều tin mới nhất” cần dữ liệu nguồn thực tế, múi giờ và đo nhiều tuần.

### 5.18. Object storage, Google Drive và đồng bộ

| Ứng viên và nguồn | License/giới hạn | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [Google Drive API v3](https://developers.google.com/drive/api/reference/rest/v3) / [Limits](https://developers.google.com/workspace/drive/api/guides/limits) | Dịch vụ Google; quota chính thức. Tại ngày nghiên cứu: tối đa 750 GB upload/người dùng/ngày, tệp tối đa 5 TB và giới hạn quota request theo project/user | Dịch vụ hoạt động; tài liệu giới hạn cập nhật 03-09-2026 | REST API cao; docs đầy đủ; resumable upload, folder và file metadata | 8.7 | Khớp tài nguyên hiện có và yêu cầu đồng bộ rồi xóa local. Không phải cơ sở dữ liệu giao dịch; phải lưu file ID, checksum, trạng thái và retry ở data store riêng. |
| [rclone](https://rclone.org/drive/) / [GitHub](https://github.com/rclone/rclone) | MIT | Push 11-09-2026; release 1.75.1 ngày 04-09-2026; khoảng 1.202 contributor; rất tích cực | CLI/config API cao; test/CI/docs rộng; hỗ trợ Drive và nhiều backend | 8.6 | Phù hợp công cụ vận hành, sao chép, kiểm tra và fallback sync. Với transaction cấp video, app vẫn cần xác nhận checksum/trạng thái thay vì chỉ dựa vào lệnh copy. |
| [SeaweedFS](https://github.com/seaweedfs/seaweedfs) | Apache-2.0 | Push 12-09-2026; release 4.46 ngày 08-09-2026; khoảng 591 contributor; rất tích cực | API trung bình-cao; test/docs; S3-compatible và phân tán | 6.2 | Có thể dùng khi sau này cần object store tự quản lý. Hiện tăng chi phí vận hành và chưa tận dụng 20 TB Drive sẵn có. |
| [MinIO Community](https://github.com/minio/minio) | AGPL-3.0; bản/community distribution đã thay đổi | Kho chính archived ngày 25-04-2026 và ghi rõ không còn duy trì; khoảng 535 contributor lịch sử | API S3 từng ổn định, docs lớn, nhưng lifecycle cộng đồng hiện không phù hợp dự án mới | 3.1 | Loại khỏi shortlist cho adoption mới. Nếu cần S3-compatible sau này, phải nghiên cứu lại lựa chọn còn được duy trì. |

**Kết luận nghiên cứu:** Google Drive API là ứng viên lưu/sync phù hợp tài nguyên đã có; rclone là công cụ bổ sung, không phải nguồn sự thật. Cách chia bốn tài khoản, quota API, điều khoản tài khoản và quy tắc xác nhận upload vẫn phải thiết kế sau.

### 5.19. Admin UI và trải nghiệm dạng bảng

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [AG Grid Community](https://www.ag-grid.com/license-pricing/) / [GitHub](https://github.com/ag-grid/ag-grid) | Community MIT; Enterprise thương mại trong cùng repo/packages | Push 11-09-2026; release 36.1.0 ngày 05-08-2026; khoảng 208 contributor; rất tích cực | API cao; test/docs rất tốt; grid dựng sẵn, virtualization, filter/sort/edit | 8.7 | Nhanh đạt trải nghiệm gần Sheets. Chỉ được dùng tính năng Community nếu chưa mua license; cần lập danh sách tính năng để tránh nhập nhằng Enterprise. |
| [TanStack Table](https://tanstack.com/table/latest/docs/overview) / [GitHub](https://github.com/TanStack/table) | MIT | Push 10-09-2026; release 9.2.4 ngày 28-08-2026; khoảng 499 contributor; rất tích cực | API cao; test/docs tốt; headless, hỗ trợ selection/filter/sort/pinning; virtualization qua thư viện bổ sung | 8.2 | Kiểm soát UI và license tốt, nhưng phải tự xây nhiều hành vi spreadsheet hơn. Phù hợp nếu thao tác bảng thực tế hẹp. |
| [Grist Core](https://support.getgrist.com/self-managed/) / [GitHub](https://github.com/gristlabs/grist-core) | Apache-2.0 | Push 11-09-2026; release 1.7.19 ngày 06-09-2026; khoảng 197 contributor; rất tích cực | API trung bình; test/docs tốt; spreadsheet-database hoàn chỉnh | 6.4 | Có thể tham khảo UX hoặc dùng như công cụ phụ. Không nên mặc định là data store/UI lõi vì mang theo model quyền, công thức và persistence riêng. |
| [Handsontable](https://handsontable.com/docs/javascript-data-grid/) / [License](https://handsontable.com/static/licenses/non-commercial/v4/handsontable-non-commercial-license.pdf) / [GitHub](https://github.com/handsontable/handsontable) | Dual license; giấy phép miễn phí giới hạn mục đích phi thương mại/đánh giá, dùng thương mại cần license | Push 11-09-2026; release 18.1.0 ngày 01-09-2026; khoảng 169 contributor; rất tích cực | API cao; test/docs tốt; spreadsheet UX mạnh | 5.9 | Kỹ thuật phù hợp nhưng license không phù hợp mặc định cho sản phẩm kiếm tiền dưới ngân sách hiện tại. Chỉ xem xét khi chấp nhận chi phí license. |

**Kết luận nghiên cứu:** AG Grid Community dẫn đầu nếu phạm vi nằm trong MIT; TanStack Table dẫn đầu nếu cần toàn quyền UI và chức năng bảng hẹp. R14/R15/R24 đã chốt sửa metadata và quản lý nguồn trên UI; còn danh sách cột/thao tác, quy mô và benchmark trước khi chọn thư viện.

### 5.20. Secrets management

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| Secret store gốc của hệ điều hành | Thuộc nền tảng Windows/cloud được chọn | Được nhà cung cấp hệ điều hành duy trì | API cao ở phạm vi nền tảng; không có một repo chung | 9.0 | Phù hợp nhất cho ứng dụng một người dùng: token không nằm trong bảng dữ liệu hoặc log. Contract ứng dụng phải tránh phụ thuộc trực tiếp một provider cụ thể. |
| [keyring](https://keyring.readthedocs.io/) / [GitHub](https://github.com/jaraco/keyring) | License dự án cần xác minh ở phiên bản khóa; metadata GitHub không khai báo rõ | Push 13-04-2026; release 25.7.0 ngày 16-11-2025; khoảng 130 contributor; tích cực | API cao; test/CI/docs tốt; cầu nối tới native credential stores | 8.1 | Ứng viên adapter nếu runtime Python được chọn. Chưa thể chọn khi runtime chưa quyết định và cần audit tệp license chính xác. |
| [Infisical](https://infisical.com/docs/documentation/getting-started/introduction) / [GitHub](https://github.com/Infisical/infisical) | MIT cho core; có thư mục/tính năng Enterprise riêng | Push 12-09-2026; release 0.165.10 ngày 11-09-2026; khoảng 278 contributor; rất tích cực | API cao; test/docs tốt; nhiều môi trường, audit và rotation | 7.8 | Phù hợp khi có cloud worker, nhiều máy hoặc nhiều người dùng. Giai đoạn đầu có thể là một dịch vụ vận hành thừa. |
| [OpenBao](https://openbao.org/docs/) / [GitHub](https://github.com/openbao/openbao) | MPL-2.0 | Push 11-09-2026; release 2.6.2 ngày 18-08-2026; khoảng 1.582 contributor theo lịch sử repo; rất tích cực | API cao; test/docs sâu; dynamic secrets và policy | 6.1 | Mạnh nhưng quá nặng cho quy mô một người dùng và ngân sách thấp. Chỉ đáng xem xét khi có hạ tầng nhiều service/người dùng. |

**Kết luận nghiên cứu:** native secret store trước, secret manager mạng sau. Bất kể công cụ nào, log và bảng quan sát chỉ lưu reference/account role, không lưu token thô.

### 5.21. Logging, metrics và monitoring

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| Structured application logs + [OpenTelemetry](https://opentelemetry.io/docs/) / [Collector GitHub](https://github.com/open-telemetry/opentelemetry-collector) | Apache-2.0 | Push 11-09-2026; release 0.160.0 ngày 02-09-2026; khoảng 638 contributor; rất tích cực | API/semantic conventions cao; test/docs sâu; vendor-neutral traces, metrics, logs | 9.0 | Phù hợp làm nền quan sát và correlation theo session/batch/job/stage. Có thể bắt đầu bằng structured log rồi thêm collector khi cần. |
| [Prometheus](https://prometheus.io/docs/introduction/overview/) / [GitHub](https://github.com/prometheus/prometheus) + [Grafana](https://grafana.com/docs/grafana/latest/) / [GitHub](https://github.com/grafana/grafana) | Prometheus Apache-2.0; Grafana AGPL-3.0 | Cả hai cập nhật 11-12/09-2026; release Prometheus 3.14.0 ngày 18-08-2026, Grafana 13.2.1; khoảng 1.476 và 3.117 contributor | API cao; test/docs rất sâu | 7.5 | Phù hợp khi cần dashboard throughput, lỗi, queue depth, chi phí và tài nguyên theo thời gian. Giai đoạn đầu có thể tốn vận hành hơn giá trị. |
| [Sentry](https://develop.sentry.dev/self-hosted/) / [GitHub](https://github.com/getsentry/sentry) | Functional Source License 1.1 với chuyển đổi tương lai sang Apache-2.0 | Push 12-09-2026; release 26.8.0; khoảng 1.084 contributor; rất tích cực | API cao; test/docs tốt; error tracking và tracing | 6.7 | Sentry SaaS có thể hữu ích nếu giá phù hợp; self-host khá nặng và license không phải permissive thuần. UI nội bộ vẫn phải hiển thị lỗi theo yêu cầu sản phẩm. |

**Kết luận nghiên cứu:** mọi job/stage cần structured log trước; OpenTelemetry là nền tảng không khóa vendor. Prometheus/Grafana hoặc Sentry chỉ thêm khi nhu cầu vận hành và chi phí được chứng minh.

### 5.22. Điều phối LLM, schema đầu ra và fallback nhà cung cấp

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| Adapter nhà cung cấp mỏng do dự án sở hữu | Không phụ thuộc license framework; phụ thuộc SDK/API nhà cung cấp | Do dự án kiểm soát | Contract được định nghĩa sau; dễ test bằng fake và schema cố định | 8.9 | Giữ nghiệp vụ phân loại, kịch bản, suy luận và fallback khỏi framework. Không có nghĩa tự xây HTTP client nếu SDK chính thức phù hợp. |
| [PydanticAI](https://ai.pydantic.dev/) / [GitHub](https://github.com/pydantic/pydantic-ai) | MIT | Push 12-09-2026; release 2.43.0; khoảng 579 contributor; rất tích cực | API trung bình-cao nhưng thay đổi nhanh; test/docs tốt; typed output, model providers, evals | 8.5 | Phù hợp nếu runtime Python và cần output có schema, retry/validation. Cần khóa version và không để domain model phụ thuộc trực tiếp framework. |
| [Instructor](https://python.useinstructor.com/) / [GitHub](https://github.com/567-labs/instructor) | MIT | Push 11-09-2026; release 1.17.0 ngày 09-09-2026; khoảng 267 contributor; rất tích cực | API cao; test/docs tốt; structured output trên nhiều provider | 8.2 | Phù hợp cho parse/validate đầu ra có kiểu với footprint nhỏ hơn framework agent. Không tự giải quyết routing, quota và workflow. |
| [LiteLLM](https://docs.litellm.ai/) / [GitHub](https://github.com/BerriAI/litellm) | MIT core; enterprise features riêng | Push 12-09-2026; release 1.100.1 ngày 10-09-2026; khoảng 1.705 contributor; rất tích cực nhưng issue/API surface lớn | API trung bình; test/CI/docs tốt; proxy/router, budget, fallback nhiều provider | 7.9 | Có ích khi số provider/tài khoản đủ lớn để justify một gateway. Nhịp thay đổi và diện tích cấu hình lớn làm tăng rủi ro ở giai đoạn đầu. |
| [LangChain](https://python.langchain.com/docs/) / [GitHub](https://github.com/langchain-ai/langchain) | MIT | Push 12-09-2026; khoảng 3.737 contributor; rất tích cực | API trung bình; test/docs lớn; ecosystem rộng nhưng có lịch sử thay đổi nhanh | 6.6 | Không ưu tiên làm lõi vì dự án cần pipeline xác định, quan sát được hơn là agent framework rộng. Có thể dùng component riêng nếu chứng minh giá trị. |

**Kết luận nghiên cứu:** contract nghiệp vụ và schema phải thuộc dự án; PydanticAI hoặc Instructor chỉ là công cụ biên. LiteLLM được giữ làm ứng viên khi thực sự cần điều phối bốn tài khoản/nhiều provider, không được dùng để lách điều khoản hay hạn mức dịch vụ.

### 5.23. AI local fallback

| Ứng viên và nguồn | License | Hoạt động tại 12-09-2026 | API, test, tài liệu | Điểm | Phù hợp và kết luận |
|---|---|---|---|---:|---|
| [Ollama](https://docs.ollama.com/) / [GitHub](https://github.com/ollama/ollama) | MIT | Push 11-09-2026; release 0.34.0; khoảng 615 contributor; rất tích cực | HTTP API cao; CI/docs tốt; quản lý model và runtime đơn giản | 8.6 | Ứng viên tốt nhất để kiểm chứng fallback vận hành nhanh trên desktop. Model cụ thể, quantization và license phải audit riêng. |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT | Push 12-09-2026; release 0.4.0 ngày 04-09-2026; khoảng 1.991 contributor; rất tích cực | CLI/server API cao; test/CI/docs sâu; nhiều backend và quantization | 8.8 | Ứng viên mạnh nhất khi cần kiểm soát hiệu năng/VRAM sâu. Vận hành trực tiếp phức tạp hơn Ollama; có thể là runtime nền chứ không phải contract ứng dụng. |
| [vLLM](https://docs.vllm.ai/) / [GitHub](https://github.com/vllm-project/vllm) | Apache-2.0 | Push 12-09-2026; release 0.29.0; khoảng 3.432 contributor; rất tích cực | OpenAI-compatible API cao; test/docs sâu; throughput server lớn | 6.3 | Rất mạnh cho serving nhiều request/GPU, nhưng RTX 4070 SUPER 12 GB và một người dùng không phải profile lý tưởng. Chỉ xem xét khi có GPU server lớn hơn. |

**Kết luận nghiên cứu:** Ollama giúp proof nhanh, llama.cpp giúp tối ưu sâu. Không thể ghi “model mạnh nhất tính đến 09-2026” như một lựa chọn cố định; model phải là cấu hình có version và được benchmark theo từng vai trò trên đúng 12 GB VRAM.

## 6. Audit chéo các ứng viên dẫn đầu

### 6.1. Tính đầy đủ so với yêu cầu sản phẩm

| Yêu cầu có ảnh hưởng lớn | Ứng viên có khả năng đáp ứng | Khoảng thiếu phải kiểm chứng |
|---|---|---|
| Thu thập khi desktop tắt | Scrapy/feedparser + workflow/cloud runtime chưa chọn | Topology, chi phí chạy liên tục, điều khoản nguồn và thời gian quét |
| Tiếp tục sau gián đoạn | Temporal hoặc Prefect; trạng thái bền ở data store | Hành vi khi mất điện giữa upload/render, idempotency và thời gian phục hồi 5 phút |
| 100 video/12 giờ | FFmpeg, hardware encoder, prefetch 5 video | Chưa có benchmark preset, TTS, I/O Drive và contention GPU |
| Không mất dữ liệu khi sync lỗi | Drive resumable upload + checksum/status riêng | Cách xác nhận hoàn tất, quota bốn tài khoản và xử lý file trùng |
| 95% phát hiện ảnh nhạy cảm | MediaPipe/OpenCV + classifier/cloud moderation | Chưa có tập mẫu đại diện; không ứng viên đơn lẻ nào chứng minh đạt |
| Chống lặp video | DataSketch, embedding, `VariantSignature` và lịch sử | Định nghĩa “hoàn toàn giống”, ngưỡng semantic và cách so media/audio |
| UI giống trải nghiệm Sheets | AG Grid Community hoặc TanStack Table | Chưa chốt thao tác sửa, số hàng/cột và tính năng bắt buộc |
| TTS biểu cảm trong ngân sách | Gemini, ElevenLabs, Piper, Kokoro | Chất lượng thực, quota API, license voice/model và chi phí ở sản lượng thật |
| AI fallback không mất hàng chờ | Adapter mỏng + Ollama/llama.cpp + workflow bền | Model theo vai trò, VRAM, thời gian chuyển đổi và chất lượng tối thiểu |

### 6.2. Rủi ro tích hợp xuyên năng lực

1. **GPU contention:** STT, TTS local, embedding, image detection và render có thể cùng cần RTX 4070 SUPER. Điểm mạnh riêng của từng thư viện không bảo đảm throughput tổng thể.
2. **Version drift:** FFmpeg build, model AI, prompt, preset và API cloud phải được version hóa cùng output; nếu không sẽ không tái hiện được video cũ.
3. **License drift:** dự án có thể đổi license hoặc tách Community/Enterprise. Version khóa phải đi kèm bản ghi license đã audit.
4. **Cloud account limits:** bốn tài khoản không mặc nhiên cho phép gộp quota hoặc chia tải theo cách tùy ý. Thiết kế phải tuân thủ điều khoản từng dịch vụ.
5. **Source drift:** route RSS, selector và extractor sẽ hỏng theo thay đổi website. Cần test fixture và tỷ lệ lỗi theo nguồn, không chỉ test thư viện.
6. **False confidence in moderation:** nhãn toàn ảnh không đồng nghĩa có bounding box đủ chính xác để blur. Tuổi khuôn mặt là bài toán khác với phát hiện khuôn mặt.
7. **UI/data coupling:** grid hoặc Google Sheets không được trở thành nơi lưu chính chỉ vì dễ quan sát. Source of truth phải được quyết định bằng yêu cầu giao dịch, đồng bộ và phục hồi.

### 6.3. Ứng viên bị loại hoặc hoãn rõ ràng

| Ứng viên | Trạng thái nghiên cứu | Lý do |
|---|---|---|
| TikTok Research API | Loại cho luồng thương mại hiện tại | Điều kiện chính thức giới hạn nhà nghiên cứu đủ điều kiện và mục đích phi thương mại vì lợi ích công |
| MinIO Community repo | Loại cho adoption mới | Kho chính archived và ghi rõ không còn duy trì |
| Remotion làm render lõi | Hoãn | License đặc biệt và mô hình automation có thể tạo chi phí/ràng buộc; FFmpeg phù hợp ngân sách và throughput hơn |
| Handsontable làm grid mặc định | Hoãn | Dùng thương mại cần license; chưa chứng minh lợi ích vượt AG Grid Community/TanStack |
| OpenSearch ở quy mô đầu | Hoãn | Tốn tài nguyên và vận hành khi PostgreSQL FTS chưa được chứng minh là thiếu |
| Immich/PhotoPrism làm data store | Loại khỏi lõi | Domain và vòng đời dữ liệu không khớp; AGPL và coupling lớn |
| Newspaper3k làm extractor chính | Không ưu tiên | Release hygiene yếu so với Trafilatura/Readability |
| ffmpeg-python làm wrapper lõi | Không ưu tiên | Nhịp duy trì chậm; adapter trực tiếp dễ debug hơn |
| Coqui TTS/MeloTTS làm mặc định | Không ưu tiên | Kho chính cập nhật chậm, trong khi TTS là năng lực có rủi ro chất lượng cao |
| vLLM trên desktop hiện tại | Hoãn | Tối ưu cho serving throughput lớn; không khớp 12 GB VRAM và quy mô một người dùng |

## 7. Chương trình kiểm chứng được đề xuất

Các mục dưới đây là **ĐỀ XUẤT NGHIÊN CỨU**, không phải yêu cầu đã xác nhận và không cho phép bắt đầu viết code ở giai đoạn hiện tại.

| Mã | Năng lực cần kiểm chứng | Dữ liệu/cách thử | Kết quả cần thu |
|---|---|---|---|
| TECH-POC-001 | RSS, crawl, extraction | Một tập URL đại diện cho nguồn Tier 1/2/3, gồm RSS đầy đủ, RSS rút gọn, HTML tĩnh, trang động và trang lỗi | Tỷ lệ lấy được title/body/date/media, thời gian, lỗi theo nguồn và mức cần Playwright |
| TECH-POC-002 | Trùng bài và liên kết sự kiện | Cặp bài đã được người dùng gắn nhãn: trùng URL, gần trùng, cùng sự kiện khác bài và khác sự kiện | Precision/recall từng tầng, false merge, chi phí embedding/AI và ngưỡng đề xuất |
| TECH-POC-003 | An toàn ảnh | Bộ ảnh tin tức gắn nhãn theo trẻ em, máu me, vũ khí, vùng cần xử lý và mẫu âm tính khó | Recall phải đối chiếu ngưỡng 95% đã duyệt; precision, vùng blur sai, thời gian và chi phí |
| TECH-POC-004 | TTS | Cùng tập lời dẫn tiếng Anh, tên riêng khó và năm phong cách; tạo nhiều lần với Gemini, ElevenLabs, Piper, Kokoro | Đánh giá mù về tự nhiên, cảm xúc, phát âm, ổn định, tốc độ, chi phí và license voice/model |
| TECH-POC-005 | Subtitle | Audio do các ứng viên TTS tạo, có nhạc/SFX ở nhiều mức | Word error rate, sai timestamp, thời gian và VRAM giữa faster-whisper, WhisperX, whisper.cpp |
| TECH-POC-006 | Composition/render | Năm preset đầy đủ với ảnh, clip, hook, subtitle, nhạc, SFX và hardware encode | Throughput 12 giờ, lỗi phát, duration 61-70 giây, GPU/CPU/RAM/I/O và chất lượng nghe nhìn |
| TECH-POC-007 | Durable workflow | Cố ý dừng cloud worker, desktop, mạng và ứng dụng ở từng stage; lặp lại retry | Không mất job/log, không chạy lại stage hoàn thành, khôi phục trong 5 phút và không tạo output trùng ngoài ý muốn |
| TECH-POC-008 | Drive sync | Upload resumable, ngắt mạng, file lớn, quota gần ngưỡng và bốn tài khoản | Checksum, retry, xác nhận upload, chỉ xóa local sau xác nhận và xử lý rate limit |
| TECH-POC-009 | UI grid | Dataset đại diện sau khi chốt số hàng/cột và thao tác | 95% thao tác dưới 2 giây, không chồng lấn ở 1080p+, phạm vi Community license và effort triển khai |
| TECH-POC-010 | Local AI fallback | Mỗi vai trò AI chạy model phù hợp trên 12 GB VRAM trong lúc render hoặc theo lịch chia sẻ tài nguyên | Chất lượng theo vai trò, tokens/s, VRAM, thời gian chuyển fallback và tác động throughput video |

Số lượng URL, cặp bài, ảnh và script cụ thể chưa được ấn định để tránh biến quy mô benchmark chưa có dữ liệu thành yêu cầu chính thức.

## 8. Kết luận theo lớp quyết định

### 8.1. Có thể mang sang bước kiến trúc như ứng viên ưu tiên

- feedparser cho RSS/Atom.
- Scrapy cho crawl chính; Playwright cho fallback trang động.
- Trafilatura cho trích xuất chính; Readability/jusText cho fallback và đối chiếu.
- PostgreSQL cho dữ liệu có cấu trúc và full-text search ban đầu.
- DataSketch + Sentence Transformers cho chống trùng/liên kết nhiều tầng.
- FFmpeg/ffprobe cho kiểm tra, composition và render; PyAV/PySceneDetect/OpenCV cho nhu cầu chuyên biệt.
- Google Drive API cho lưu/sync theo tài nguyên hiện có; rclone cho công cụ vận hành và fallback.
- OpenTelemetry/structured logs làm nền quan sát.
- Adapter AI do dự án sở hữu; framework structured-output chỉ nằm ở biên tích hợp.

### 8.2. Phải có proof-of-capability trước khi quyết định

- Temporal so với Prefect cho durable workflow.
- AG Grid Community so với TanStack Table cho UI dạng bảng.
- Gemini TTS, ElevenLabs, Piper và Kokoro cho primary/fallback TTS.
- MediaPipe/OpenCV/model local so với cloud moderation cho ảnh nhạy cảm.
- Ollama so với llama.cpp và model cụ thể cho từng vai trò fallback.
- PostgreSQL FTS so với Meilisearch khi dữ liệu và thao tác tìm kiếm đã đo được.

### 8.3. Chỉ thêm khi có bằng chứng cần thiết

- Search service riêng, object store riêng, secret manager mạng và monitoring stack đầy đủ.
- Một LLM gateway như LiteLLM.
- WhisperX thay cho timestamp cơ bản.
- Một digital asset manager hoàn chỉnh.

## 9. Các vấn đề CHƯA QUYẾT ĐỊNH sau nghiên cứu

- **TECH-OPEN-001 - ĐÃ CHỌN BASELINE:** Python/FastAPI và TypeScript/React theo ADR-0007; phiên bản cụ thể còn G07.
- **TECH-OPEN-002 - ĐÃ CHỌN BASELINE:** hybrid với cloud workflow worker riêng theo ADR-0001/0003; sizing host còn G03.
- **TECH-OPEN-003 - CONDITIONAL:** Temporal ưu tiên theo ADR-0003, chưa qua G01/G03/G07; Prefect là ứng viên đánh giá lại đầu tiên nếu gate thất bại.
- **TECH-OPEN-004:** TTS primary/fallback sau benchmark chất lượng, chi phí và license voice/model.
- **TECH-OPEN-005:** Bộ model và ngưỡng đạt 95% cho ảnh nhạy cảm; cách xác định tuổi/khuôn mặt trẻ em.
- **TECH-OPEN-006 - ĐÃ CHỌN BASELINE:** AG Grid Community theo ADR-0007; không mặc định các tính năng Enterprise, vẫn cần benchmark UI.
- **TECH-OPEN-007 - ĐÓNG MỘT PHẦN:** PostgreSQL cloud là lõi, desktop qua API; một host self-host còn gate chi phí/khôi phục; Sheets không vào đường chạy v1 theo ADR-0001/0002/0007.
- **TECH-OPEN-008 - ĐÃ CHỌN BASELINE:** PostgreSQL FTS + pgvector theo ADR-0002; search service riêng chỉ xét khi benchmark có khoảng thiếu.
- **TECH-OPEN-009:** Cách chia file/quota giữa bốn Google Drive mà vẫn tuân thủ điều khoản và không tạo single point of failure.
- **TECH-OPEN-010:** Model local theo từng vai trò, quantization, giới hạn VRAM và chính sách ưu tiên GPU so với render.
- **TECH-OPEN-011 - CÒN MỘT PHẦN:** R03 chốt phụ đề bắt buộc và timing từng từ; công cụ căn lời và kiểm tra chất lượng chưa chọn.
- **TECH-OPEN-012:** Build FFmpeg cụ thể, codec/hardware encoder, độ phân giải, tỷ lệ khung hình, frame rate và container đầu ra.
- **TECH-OPEN-013 - CÒN MỘT PHẦN:** R20 chốt chỉ tính chi phí phát sinh thêm trong ngân sách; hạn mức theo công đoạn và tính khả thi còn cần nghiên cứu/đo.
- **TECH-OPEN-014:** Mức chuẩn bị SaaS ngay từ phiên bản đầu đối với auth, tenant, audit và secret management.
- **TECH-OPEN-015:** Nguồn tín hiệu trending thay thế khi TikTok Research API không phù hợp và Google Trends API còn Alpha.

## 10. Giả định

**Không có GIẢ ĐỊNH nào trong tài liệu này được dùng làm quyết định công nghệ chính thức.**

Điểm số là kết quả sàng lọc nghiên cứu dựa trên thông tin công khai tại ngày 12-09-2026, không phải benchmark trên máy mục tiêu. Các nhận định về chất lượng, tốc độ, chi phí và khả năng đạt ngưỡng chỉ trở thành bằng chứng sau chương trình kiểm chứng.

## 11. Lưu ý giấy phép và quyền sử dụng

- MIT, Apache-2.0, BSD, PostgreSQL License và public domain thường dễ dùng hơn cho sản phẩm thương mại, nhưng vẫn phải giữ notice và tuân thủ điều khoản cụ thể.
- LGPL, MPL, GPL và AGPL có nghĩa vụ khác nhau tùy cách liên kết, sửa đổi, phân phối và cung cấp qua mạng. Cần audit phiên bản/build thực tế trước khi phát hành; tài liệu này không phải tư vấn pháp lý.
- License của engine không tự động bao phủ model, weights, voice, dataset, font, icon, nhạc, ảnh hoặc clip đi kèm.
- API key hoặc gói thuê bao người dùng có không bảo đảm quyền tự động hóa, chia tải qua nhiều tài khoản hoặc sử dụng thương mại. Điều khoản dịch vụ của từng nhà cung cấp vẫn có hiệu lực.
- Khả năng kỹ thuật để crawl không đồng nghĩa có quyền sao chép, lưu, chỉnh sửa hoặc phát hành lại nội dung. Mỗi nguồn và asset vẫn cần provenance và trạng thái quyền như bản đồ dữ liệu đã quy định.

## 12. Nguồn chính thức trọng yếu

- Thu thập và extraction: [feedparser](https://feedparser.readthedocs.io/en/stable/), [Scrapy](https://docs.scrapy.org/en/latest/), [Trafilatura](https://trafilatura.readthedocs.io/), [Mozilla Readability](https://github.com/mozilla/readability).
- Dữ liệu và tìm kiếm: [PostgreSQL](https://www.postgresql.org/docs/current/), [PostgreSQL Full Text Search](https://www.postgresql.org/docs/current/textsearch.html), [Meilisearch Community/Enterprise](https://www.meilisearch.com/docs/resources/self_hosting/enterprise_edition).
- Trending: [GDELT data](https://www.gdeltproject.org/data.html), [Google Trends API Alpha](https://developers.google.com/search/apis/trends), [TikTok Research API](https://developers.tiktok.com/products/research-api), [TikTok Research API FAQ](https://developers.tiktok.com/docs/en/research-api-faq).
- Media: [FFmpeg documentation](https://ffmpeg.org/documentation.html), [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html), [PyAV](https://pyav.org/docs/stable/), [PySceneDetect](https://www.scenedetect.com/docs/latest/), [OpenCV](https://docs.opencv.org/).
- An toàn ảnh: [Google Vision SafeSearch](https://docs.cloud.google.com/vision/docs/detecting-safe-search), [Amazon Rekognition Moderation](https://docs.aws.amazon.com/rekognition/latest/dg/moderation-api.html), [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/guide).
- Âm thanh: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [WhisperX](https://github.com/m-bain/whisperX), [Gemini TTS](https://ai.google.dev/gemini-api/docs/speech-generation), [ElevenLabs TTS](https://elevenlabs.io/docs/overview/capabilities/text-to-speech), [ElevenLabs API pricing](https://elevenlabs.io/pricing/api), [Piper voices và license](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md).
- Workflow: [Temporal](https://docs.temporal.io/), [Prefect retries](https://docs.prefect.io/v3/how-to-guides/workflows/retries), [Prefect deployments/schedules](https://docs.prefect.io/v3/concepts/deployments), [Celery](https://docs.celeryq.dev/en/stable/), [APScheduler](https://apscheduler.readthedocs.io/).
- Lưu trữ: [Google Drive API v3](https://developers.google.com/drive/api/reference/rest/v3), [Google Drive usage limits](https://developers.google.com/workspace/drive/api/guides/limits), [rclone Google Drive](https://rclone.org/drive/), [MinIO repository status](https://github.com/minio/minio).
- UI và license: [AG Grid licensing](https://www.ag-grid.com/license-pricing/), [TanStack Table](https://tanstack.com/table/latest/docs/overview), [Handsontable Non-Commercial License](https://handsontable.com/static/licenses/non-commercial/v4/handsontable-non-commercial-license.pdf), [Remotion license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md).
- Vận hành và AI: [OpenTelemetry](https://opentelemetry.io/docs/), [Prometheus](https://prometheus.io/docs/introduction/overview/), [PydanticAI](https://ai.pydantic.dev/), [LiteLLM](https://docs.litellm.ai/), [Ollama](https://docs.ollama.com/), [llama.cpp](https://github.com/ggml-org/llama.cpp), [vLLM](https://docs.vllm.ai/).

## 13. Điều kiện phê duyệt bước 07

Tài liệu được phê duyệt khi người dùng xác nhận:

1. Danh sách năng lực nghiên cứu đã bao phủ đúng sản phẩm.
2. Các ứng viên ưu tiên, ứng viên dự phòng và các loại trừ phản ánh đúng mức chấp nhận chi phí/rủi ro.
3. Các mục `TECH-OPEN-*` được phép giữ lại cho bước phân hệ, luồng dữ liệu và kiến trúc.
4. Chương trình `TECH-POC-*` chỉ được dùng theo milestone đã cấp quyền. Hiện quyền code giới hạn M1; việc chấp thuận nghiên cứu không tự mở M2–M7 hoặc công nghệ chưa khóa.

Sau khi được phê duyệt, bước tiếp theo là **08 - Chia hệ thống thành các phân hệ**. Bước này vẫn chưa phải thiết kế kiến trúc chi tiết và chưa phải bắt đầu code.
