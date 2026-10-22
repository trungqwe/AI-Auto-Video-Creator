# ADAPT-I: Adapter Google Drive cho CloudObjectPort

## 1. Phạm vi và tệp đã sửa
- `src/controlplane/infrastructure/storage/drive_object_store.py` (mô-đun adapter Google Drive cài đặt `CloudObjectPort` qua `google-api-python-client`, cấp file ID trước bằng `files.generateIds`, upload resumable theo chunk vào đúng file ID, chuyển HTTP 409 thành `ObjectAlreadyExistsError`, làm mới phiên hết hạn với cùng file ID, xử lý retry/backoff và timeout thành `TimeoutError`, `lookup` kiểm tra sha256 qua metadata hoặc tải theo chunk và từ chối upload khi dự phóng dung lượng trống dưới `quota_reserve_ratio`)
- `tests/integration/adapt/i/test_adapt_i_drive.py` (32 ca kiểm thử tích hợp với dịch vụ Drive giả `FakeDriveHttp` ở tầng transport của thư viện, kiểm tra toàn bộ vòng đời cấp ID, upload chunked, retry, backoff, 409, phiên hết hạn, timeout, quota, sha256 checksum và bảo mật token)
- `docs/delivery-evidence/adapt-i/report.md` (báo cáo bằng chứng bàn giao thực thi task ADAPT-I)

## 2. Thiết kế và giả định
- Cấp file ID trước: `reserve_object_id` gọi `files.generateIds` (count=1, space='drive') theo cấu hình `placement` của `namespace_ref`.
- Upload resumable: `upload` thực hiện tải lên theo chunk `chunk_bytes` vào đúng file ID đã cấp bằng `files.create` với tham số `body={'id': object_id, ...}` và `MediaIoBaseUpload(resumable=True)`. Thử lại cùng file ID, tuyệt đối không tạo tệp thứ hai.
- Xử lý xung đột HTTP 409: Chuyển trực tiếp thành `ObjectAlreadyExistsError`, không retry; để `PersistArtifactToCloud` xử lý đối soát và tái điều hòa (`reconcile`).
- Phiên hết hạn: Khi gặp HTTP 404, 410 hoặc thời gian phiên vượt quá `session_ttl_seconds`, adapter mở phiên tải lên mới vào cùng file ID đó, không tính lỗi vào bộ đếm backoff, tối đa `retry_max_attempts` phiên liên tiếp để tránh lặp vô hạn.
- Lỗi tạm thời: Các mã HTTP 408, 429, 5xx, lỗi 403 có lý do `rateLimitExceeded`/`userRateLimitExceeded`, cùng lỗi kết nối mạng được retry theo cơ chế backoff số mũ có chặn trần (`retry_backoff_base_seconds * 2 ** (failures - 1)` giới hạn bởi `retry_backoff_cap_seconds`), xác định không jitter. Bộ đếm thất bại liên tiếp được reset về 0 ngay khi có tiến triển chunk.
- Hết lượt thử do timeout: Ném `TimeoutError` để tầng điều phối `PersistArtifactToCloud` ghi nhận trạng thái `ArtifactLocationState.OUTCOME_UNKNOWN`.
- Toàn vẹn dữ liệu: `lookup` đọc `sha256Checksum` từ metadata của Drive; nếu metadata thiếu checksum khớp sha256 hợp lệ thì tải tệp về theo từng chunk vào bộ băm tăng dần `_HashingSink` để tính toán sha256 (tuyệt đối không tin `md5Checksum`, không dùng `BytesIO`, không tải toàn bộ tệp vào RAM).
- Bảo vệ hạn mức lưu trữ: Kiểm tra dung lượng trống trước khi upload qua `about.get(fields='storageQuota')`. Nếu dự phóng dung lượng trống sau khi upload thấp hơn ngưỡng `quota_reserve_ratio * limit`, upload bị từ chối fail-closed bằng `DriveQuotaError`. Nếu tài khoản không có trường `limit` (không giới hạn), bỏ qua kiểm tra hạn mức.
- Quản trị token và bảo mật: Access token chỉ lấy cho từng request thông qua `_BrokerHttp` gọi `broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF)` của phân hệ J. Token không được gán vào thuộc tính, không xuất hiện trong log hoặc thông điệp ngoại lệ; adapter không lưu trữ token dài hạn và không chứa logic làm mới token; mọi tham số lấy từ `DriveStoreConfig` không có giá trị mặc định ẩn.
- GIẢ ĐỊNH: (a) `ArtifactSourcePort` là cổng mới do `ADAPT-WIRE` nối vì chữ ký `CloudObjectPort.upload` không nhận đường dẫn nguồn trên máy chủ;
- GIẢ ĐỊNH: (b) Cặp ánh xạ `placement` được ghi nhớ trong bộ nhớ tiến trình lúc `reserve_object_id`; khi tiến trình khởi động lại sẽ dùng `fallback_parent_id`. Việc lưu trữ bền vững `namespace_ref` và tạo cấu trúc thư mục Drive thuộc phạm vi của `ADAPT-WIRE` hoặc `I-12`;
- GIẢ ĐỊNH: (c) Dòng `drive.verify` của `plan.md` 7.5 về so khớp MD5 lúc upload KHÔNG cài đặt (ngoài phạm vi tiêu chí nghiệm thu; tính toàn vẹn được đảm bảo chặt chẽ bằng SHA-256 ở `lookup`), đưa vào backlog rà soát;
- GIẢ ĐỊNH: (d) Quyền hạn `drive.file` đối với API `about.get` và tính sẵn sàng của trường metadata `sha256Checksum` chỉ có thể được xác nhận cuối cùng với dịch vụ Google Drive thật tại slice `CP7-I-01`.

## 3. Lệnh đã chạy
Kết quả chạy thực tế trên worktree với interpreter khóa `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`:

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 8 (RED) | python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider | 1 | 22 failed, 10 passed in 1.37s (22 test hành vi thất bại do NotImplementedError từ stub) |
| Bước 13 (GREEN) | python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider | 0 | 32 passed in 1.50s (toàn bộ 32 ca kiểm thử passed, không skip, không xfail) |
| Bước 14 (Probe) | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/storage/drive_object_store.py').read_text(encoding='utf-8'); assert 'CloudObjectPort' in t and 'ObjectAlreadyExistsError' in t and 'generateIds' in t and 'from src.' not in t, 'adapter I'" | 0 | Đạt, probe kiểm tra các symbol bắt buộc và không có 'from src.' |
| Bước 15 | git diff --check | 0 | Sạch, không có lỗi khoảng trắng thừa |
| Bước 17 | git diff --check | 0 | Sạch, không có lỗi khoảng trắng thừa |

## 4. RED/GREEN
- Chứng kiến RED hợp lệ tại bước 8: Pytest chạy ra 22 failed, 10 passed. Toàn bộ 22 ca thất bại đều do `NotImplementedError` phát ra từ các phương thức stub của `DriveObjectStore` (`reserve_object_id`, `upload`, `lookup`), hoàn toàn không có lỗi import hay lỗi thu thập test. 10 ca passed gồm 9 ca kiểm tra cấu hình `DriveStoreConfig` và 1 ca kiểm tra cấu trúc tĩnh không chứa token/refresh/from src.
- Chứng kiến GREEN tại bước 13: Toàn bộ 32/32 ca kiểm thử passed, không có skip hay xfail.

## 5. Việc còn lại (backlog, không làm trong slice này)
- `CP7-I-01`: Kiểm chứng với dịch vụ Google Drive thật và tài khoản thật.
- `CP7-I-02`: Đo đạc thực tế hạn mức quota và kiểm tra tương thích trường metadata Drive thật.
- Nối dây `ADAPT-WIRE`: Kết nối broker phân hệ J, `ArtifactSourcePort`, và lưu trữ bền vững ánh xạ placement.
- Rà soát cài đặt so khớp MD5 lúc upload nếu sản phẩm có yêu cầu bổ sung.
