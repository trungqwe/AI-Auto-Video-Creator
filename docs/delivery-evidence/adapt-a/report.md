# Báo cáo ADAPT-A

## Tệp đã tạo

- `src/source_ingestion/adapters/real_http_transport.py`: Transport thật cho SecureFetcher chỉ GET, http.client nối đúng addresses đã ghim, SNI và Host là host, không theo redirect, không đọc proxy hay biến môi trường trong mã, có timeout và đọc body theo chunk.
- `src/source_ingestion/adapters/real_feed_source.py`: SourceAdapter cho rss_feed và atom_feed, feed và bài tải qua SecureFetcher, feedparser.parse và trafilatura.extract chỉ chạy trên bytes đã tải, technical_fields giữ raw_bytes cùng phiên bản feedparser và trafilatura, resume_from_checkpoint và supplemental_search trả CapabilityUnavailable, lỗi mạng và parse trả ProblemDetail.
- `src/source_ingestion/adapters/real_media_fetch.py`: Tải ảnh gắn bài qua SecureFetcher với FetchPolicy ảnh, tính sha256, ghi vào staging root từ cấu hình, dựng DiscoveryObservation cho C, từ chối ảnh quá giới hạn hoặc ngoài SSRF policy.
- `tests/integration/adapt/a/test_adapt_a_adapters.py`: Bộ kiểm thử tích hợp kiểm tra toàn diện 3 adapter: máy chủ loopback cô lập cho transport, fixture feed/HTML nhúng offline cho RSS/Atom, kiểm thử staging và DiscoveryObservation cho media, cùng kiểm tra AST vệ sinh module.
- `docs/delivery-evidence/adapt-a/report.md`: Báo cáo nghiệm thu bằng chứng phân phối của task ADAPT-A.

## Thiết kế

- (a) RealHttpTransport: GET duy nhất, http.client nối đúng addresses đã ghim, SNI và Host là host, không theo redirect, không đọc proxy hay biến môi trường trong mã, timeout theo request.timeout_seconds, đọc body theo chunk;
- (b) RealFeedSource: một lớp cho cả rss_feed và atom_feed, feedparser.parse chạy trên io.BytesIO của bytes đã tải, trafilatura.extract chạy trên bytes, raw_bytes và phiên bản thư viện nằm trong technical_fields, resume_from_checkpoint và supplemental_search trả CapabilityUnavailable, lỗi mạng và parse trả ProblemDetail;
- (c) RealMediaFetcher: ảnh qua SecureFetcher với FetchPolicy ảnh, sha256, ghi theo tên băm vào staging root, dựng DiscoveryObservation, từ chối ảnh quá lớn và địa chỉ hay redirect ngoài SSRF policy.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- |
| `git diff --check` | 0 | Không có lỗi khoảng trắng thừa hoặc xuống dòng sai định dạng |
| `python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cacheprovider` | 0 | 27 passed in 5.74s |
| `python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_http_transport.py', 'real_feed_source.py', 'real_media_fetch.py']); assert 'feedparser' in t and 'trafilatura' in t and 'SecureFetcher' in t and 'from src.' not in t, 'adapter A'"` | 0 | Exit 0: đầy đủ feedparser, trafilatura, SecureFetcher và không có tiền tố from src. |

## Mục mở

- (1) GIẢ ĐỊNH: max_images_per_article=8 là mặc định đơn giản (D8), chưa có tham số cấu hình, ADAPT-WIRE có thể truyền giá trị từ profile.json;
- (2) staging root nhận từ tham số constructor (đường dẫn tuyệt đối), việc đọc cấu hình thuộc ADAPT-WIRE;
- (3) binding A→C của GATE-CP-2D-REGISTRY còn PENDING, tới khi có chỉ giao C bằng DiscoveryObservation, gói này không tạo tệp binding;
- (4) nhánh HTTPS không có test kết nối thật vì cần chứng chỉ, chỉ kiểm tĩnh server_hostname và ssl.create_default_context; OpenSSL có thể đọc SSL_CERT_FILE cho kho chứng chỉ, đó là cấu hình tin cậy chứ không phải proxy, nằm ngoài mã Python;
- (5) thứ tự test-first: test viết sau triển khai trong lệnh làm việc này, chưa có RED trước triển khai, cần Reviewer ghi nhận;
- (6) ảnh chính phụ thuộc metadata trafilatura (og:image);

## Phạm vi

- xác nhận chỉ sửa owned paths, không gọi mạng ngoài (loopback 127.0.0.1 chỉ ở test transport), không chạm src/controlplane, pyproject.toml, uv.lock hay docs/milestones/**/evidence/**.
