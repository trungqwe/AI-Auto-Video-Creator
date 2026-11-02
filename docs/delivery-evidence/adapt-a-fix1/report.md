# Báo cáo ADAPT-A-FIX1

## Nhóm lỗi
- Mã gói ADAPT-A-FIX1, nhóm lỗi OI-CP7-11-Q1 (CLOSURE_NOTE CP7/RG-13): chỉ lấy một ảnh trafilatura, trần tải 8, không đọc kích thước; thẻ chia sẻ mang logo đóng sẵn (Guardian query overlay-*, BBC /ace/branded_news/) trong khi thân bài có ảnh sạch cùng path hay UUID.

## Tệp đã sửa
- `src/source_ingestion/adapters/image_header.py` (mới): `read_image_size` đọc kích thước từ đầu tệp JPEG (SOF0..SOF15, bỏ APPn theo độ dài), PNG IHDR, WebP VP8, VP8L, VP8X; hỏng, thiếu hay cạnh bằng 0 trả None, không ném.
- `src/source_ingestion/adapters/article_images.py` (mới): `decode_html`, `page_images` gom og, twitter, JSON-LD và img/picture trong vùng chính, mỗi ảnh một lần, trần 12.
- `src/source_ingestion/adapters/real_media_fetch.py`: `MAX_IMAGES_PER_ARTICLE = 12`, `MIN_SHORT_SIDE = 360`; `fetch_image` đọc kích thước trước băm và ghi staging, trả `IMAGE_HEADER_UNREADABLE` hoặc `IMAGE_TOO_SMALL`.
- `src/source_ingestion/adapters/real_feed_source.py`: bỏ ảnh trafilatura, thêm ảnh từ `page_images` (cảnh báo `page_images_failed` khi lỗi), khử trùng theo locator.
- `tests/integration/adapt/a/test_adapt_a_adapters.py`: thêm `png_header`, `jpeg_header`; ảnh giả có đầu tệp hợp lệ 640x480.
- `tests/integration/adapt/a/test_adapt_a_fix1_article_images.py` (mới): 68 ca offline, không mạng, không DB.
- `tests/integration/prod_wiring/test_pw_w1_launcher_core.py`: `PNG_BYTES` có IHDR 640x480.
- `docs/delivery-evidence/adapt-a-fix1/report.md` (mới): báo cáo này.

## Lệnh đã chạy
| Lệnh | Exit code | Dòng tổng kết nguyên văn của pytest |
| --- | --- | --- |
| Bước 17 (RED): `python -m pytest tests/integration/adapt/a/test_adapt_a_fix1_article_images.py -q -p no:cacheprovider` | 1 | `44 failed, 24 passed in 1.86s` |
| Bước 29 (GREEN): cùng lệnh | 0 | `68 passed in 1.21s` |
| Bước 30: `python -m pytest tests/integration/adapt/a -q -p no:cacheprovider` | 0 | `95 passed in 6.43s` |
| Bước 31: `python -m pytest tests/unit tests/integration/collection -q -p no:cacheprovider` | 0 | `7782 passed, 2586 subtests passed in 39.97s` |
| Bước 32: `python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py tests/integration/prod_wiring/test_pw_a2_collect_resolve.py tests/integration/prod_wiring/test_pw_d3_fix2_article_join.py -q -p no:cacheprovider` | 0 | `33 passed in 32.96s` |
| Bước 33: probe ba mô-đun adapters | 0 | không áp dụng |
| Bước 34: probe `real_feed_source.py` | 0 | không áp dụng |
| Bước 35: probe tệp test | 0 | không áp dụng |
| Bước 36: probe bố cục gói và import không tiền tố src | 0 | không áp dụng |
| Bước 37: probe adapter A (feedparser, trafilatura, SecureFetcher) | 0 | không áp dụng |
| Bước 39: probe báo cáo | 0 | không áp dụng |
| Bước 40: `git diff --check` (lần kiểm cuối) | 0 | không áp dụng |

## Số ca test mới
- Hỏng trước khi triển khai (bước 17): 44 failed (toàn lỗi AssertionError của oracle, không có lỗi import); đạt sau (bước 29): 68 passed.

## Số ảnh trang bài lấy được trên trang mẫu (trước và sau)
- Fixture offline Guardian: trước 1 ảnh (ảnh trafilatura lấy từ og có overlay); sau 2 ảnh thân bài sạch (picture và img), og, twitter, JSON-LD có overlay bị thay, beacon noscript bị bỏ.
- Fixture offline BBC: trước 1 ảnh (og branded_news); sau 2 ảnh trong article, og bị thay vì cùng UUID.
- Số liệu chạy thật do Control đo (Worker không gọi mạng): bài đầu mỗi nguồn media/staged BBC world 3/2, BBC tech 4/3, NPR 5/3, Guardian 6/6, Al Jazeera 4/4, NASA 2/2; trước khi giới hạn vùng chính BBC 13/11, NPR 12/3, NASA 12/12.

## Ảnh bị loại và lý do
- Ngoài vùng chính (article, articleBody hay main).
- Tải sau phần thân bài khi vượt trần 12.
- Thẻ có tham số overlay hay watermark khi có biến thể sạch cùng khoá ảnh.
- Cùng khoá ảnh (UUID, hex 32 ký tự, path có đuôi ảnh) chỉ giữ một.
- Đuôi svg, svgz, gif, avif, ico, bmp, tif, tiff.
- Path có logo, icon, avatar, sprite, pixel, spacer, badge, emoji, placeholder, blank hay 1x1.
- width hay height khai báo dưới 200.
- Query w, width, h, height, resize là số 1..199.
- Ảnh trong noscript không có đuôi ảnh.
- Không phải http hay https.
- Ở bước tải: đầu tệp không đọc được (IMAGE_HEADER_UNREADABLE) và cạnh ngắn dưới 360 px (IMAGE_TOO_SMALL).

## Ưu tiên ảnh
- Ảnh trong thân bài được ưu tiên hơn ảnh chia sẻ có logo: thân bài hơn JSON-LD hơn og và twitter; biến thể không overlay hơn biến thể có overlay.
- Trần 12 ảnh mỗi trang và mỗi bài; Content-Type không quyết định kích thước (kích thước đọc từ đầu tệp).

## Mục mở
- OI-CP7-11-Q1: còn mở các giới hạn đã chấp nhận: ảnh chính nằm ngoài article (Guardian: ảnh đầu bài) mất, chỉ còn khung cắt của JSON-LD hay og; một ảnh ở hai khung cắt vẫn là hai ảnh; ảnh bài nhỏ thay thẻ og lớn cùng khoá bị loại ở bước tải nếu dưới 360 px. Việc che mờ logo và tạo ảnh AI theo quyết định user 02/11/2026 thuộc gói khác, gói này không làm.
- Quy ước đã chốt: article đầu rỗng ảnh thì không nhảy sang article thứ hai.
- Không thêm thư viện, không đổi ADAPTER_VERSION, không đổi vai trò ảnh feed.
