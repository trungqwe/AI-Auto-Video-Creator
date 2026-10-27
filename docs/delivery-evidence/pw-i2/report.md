# PW-I2: PersistVideoOutput với receipt bền và credential_unavailable

## Thay đổi

Gói công việc PW-I2 đã thực hiện đầy đủ các yêu cầu kỹ thuật trên đúng bốn tệp thuộc owned paths được phân quyền:

1. `src/controlplane/infrastructure/storage/drive_object_store.py`:
   - Thêm hằng `DRIVE_CREDENTIAL_INVALID = 'DRIVE_CREDENTIAL_INVALID'` và thuộc tính `code: str | None = None` trên lớp cơ sở `DriveObjectStoreError`.
   - Tạo lớp ngoại lệ chuyên biệt `DriveCredentialError(DriveObjectStoreError)` với `code = DRIVE_CREDENTIAL_INVALID`.
   - Trong `_failure_kind`: nhận diện mã HTTP 401 và trả về kind `'credential'`.
   - Trong `DriveObjectStore._run` và `DriveObjectStore.upload`: khi gặp kind `'credential'`, ném ngay `DriveCredentialError` với thông điệp chứa `HTTP 401`, tách biệt hoàn toàn khỏi nhánh `'fatal'` và không thực hiện retry vô ích khi credential đã hỏng.
   - Bổ sung `'DRIVE_CREDENTIAL_INVALID'` và `'DriveCredentialError'` vào `__all__`.

2. `src/controlplane/application/storage_meta/persist_handler.py`:
   - Tạo module mới chứa handler `persist_video_output_handler` bọc `PersistArtifactToCloud` theo đúng kiến trúc phân hệ I.
   - Lớp `_CommittedReceipts`: mỗi thao tác `get` hoặc `save` mượn một kết nối riêng qua `PostgresStorageMetaRepository.in_transaction`, chốt commit ngay khi ra khỏi khối, đảm bảo receipt ở trạng thái `PREPARED` đã bền vững trong cơ sở dữ liệu trước khi lệnh upload bắt đầu gửi byte tới Drive.
   - Hàm `_register_output` và `_stage_output`: xác thực tệp đầu ra có đuôi `.mp4`, đo kích thước và sha256 thực tế qua `_measure`, đăng ký `ArtifactVersion` mới (loại `video_output`, thời hạn `durable`, độ nhạy `internal`) và đặt bản sao cục bộ phẳng tại `<staging>/<artifact_version_id>` chuyển dịch tuần tự tới `VERIFIED` qua `_place_and_verify`.
   - Hàm `_persist_to_cloud`: kiểm tra receipt có sẵn theo khoá `persist-output:<artifact_version_id>`, nếu chưa `VERIFIED` thì gọi `reconcile` để xác minh đối tượng đã tồn tại trên Drive hay chưa; chỉ gọi `execute` khi Drive báo `MISSING`, tránh upload trùng lặp khi worker khởi động lại.
   - Hàm `_conclude` và `_settle_cloud_location`: cập nhật vị trí cloud tới `VERIFIED` kèm `observed_hash` và `observed_size_bytes` khi Drive báo hash/size khớp; cập nhật sang `CORRUPT` không ghi observed khi lệch nội dung và trả disposition `failed` (`CLOUD_OBJECT_CORRUPT`); trả `waiting` với `provider_unavailable` khi chưa rõ kết quả hoặc `artifact_not_ready` khi đối tượng chưa sẵn sàng.
   - Ánh xạ lỗi 401: bắt `DriveObjectStoreError` có thuộc tính `code == DRIVE_CREDENTIAL_INVALID` và chuyển thành kết quả `waiting` với mã `credential_unavailable`, cho phép công việc chờ cho tới khi token hợp lệ được cấp lại.

3. `tests/integration/prod_wiring/test_pw_i2_persist_output.py`:
   - Xây dựng 11 bài kiểm thử tích hợp trên PostgreSQL 18.6 thật và Drive giả loopback ở tầng HTTP (`LoopbackDrive` bọc `httplib2`):
     - `test_success_registers_the_version_two_verified_locations_and_a_verified_receipt`: kiểm tra luồng thành công đăng ký version mp4, xác thực hai vị trí (local và cloud) tới VERIFIED với observed_hash và observed_size_bytes đo thật, ghi receipt VERIFIED, kiểm tra cổng nghiệm thu `release_for_render` chấp nhận, và xác minh tính lũy quyền khi gọi lại lần hai không upload trùng.
     - `test_the_receipt_is_committed_before_the_upload_starts`: kiểm tra qua hook kết nối DB độc lập xác nhận receipt PREPARED với object id Drive đã được commit trước khi upload bắt đầu.
     - `test_worker_dying_before_the_upload_resumes_with_a_single_upload`: kiểm tra worker chết ngay trước khi upload, khi chạy lại đọc receipt và chỉ upload đúng một đối tượng với đúng object id đã chọn.
     - `test_worker_dying_after_the_object_reached_drive_does_not_upload_twice`: kiểm tra worker chết sau khi byte đã tới Drive nhưng trước khi kịp ghi nhận DB, khi chạy lại reconcile tìm thấy đối tượng trên Drive và chuyển VERIFIED mà không upload lần hai (attempts vẫn 1, initiates vẫn 1).
     - `test_digest_mismatch_never_verifies_the_cloud_location`: kiểm tra Drive trả nội dung lệch digest, vị trí cloud chuyển sang CORRUPT, receipt FAILED, không có vị trí cloud nào VERIFIED và handler trả lỗi `CLOUD_OBJECT_CORRUPT`.
     - `test_401_waits_with_credential_unavailable_then_completes_exactly_one_object`: kiểm tra lỗi 401 đưa handler về `waiting` với `credential_unavailable`, chuyển job sang trạng thái `WAITING`, và khi token hợp lệ trở lại thì hoàn tất thành công đúng một đối tượng đưa job tới `READY_FOR_COMPLETION`.
     - `test_401_during_the_upload_keeps_the_receipt_and_resumes_without_a_second_object`: kiểm tra token hết hạn giữa chừng lúc đang upload thì receipt PREPARED vẫn được bảo toàn, khi cấp token mới chạy lại hoàn tất đúng đối tượng đó không tạo đối tượng thứ hai.
     - `test_the_store_reports_401_with_its_own_code_on_every_drive_call`: kiểm tra `DriveObjectStore` ném `DriveCredentialError` với mã riêng `DRIVE_CREDENTIAL_INVALID` trên mọi phương thức `reserve_object_id`, `upload`, `lookup` khi gặp 401 và không retry; các lỗi khác (như 403) vẫn là `DriveObjectStoreError` với mã `None`.
     - `test_the_handler_maps_the_error_code_and_not_the_message`: kiểm tra handler chỉ ánh xạ lỗi dựa trên thuộc tính `exc.code`, không nhận diện bằng khớp chuỗi thông điệp.
     - `test_input_grant_and_source_validation`: kiểm tra tính hợp lệ của execution grant, định dạng đầu vào (từ chối khi thiếu hoặc thừa `render_output`), tệp nguồn chưa sẵn sàng (`artifact_not_ready`), đuôi tệp không phải `.mp4` hoặc cố tình duyệt thư mục (`../`).
     - `test_handler_source_is_free_of_test_doubles_and_message_matching`: quét tĩnh mã nguồn của handler đảm bảo không chứa chuỗi cấm, không khớp chuỗi '401', không tự ý commit/rollback.

4. `docs/delivery-evidence/pw-i2/report.md`:
   - Báo cáo chi tiết quá trình triển khai, kết quả nghiệm thu và bằng chứng kiểm thử của gói PW-I2.

## Giả định và quyết định (D8)

- Đầu vào `input_refs` của `PersistVideoOutput` chứa đúng một tham chiếu `render_output` với `ref_id` là đường dẫn tương đối dưới staging root (ví dụ `render/out.mp4`).
- Phiên bản artifact mới của video đầu ra mang loại `video_output`, chính sách lưu trữ `retention_ref='durable'`, phân loại bảo mật `sensitivity_ref='internal'` và mime type `video/mp4`.
- Khóa receipt bền được sinh theo quy tắc `persist-output:<artifact_version_id>`, bảo đảm worker khởi động lại sau sự cố luôn tra cứu đúng receipt của phiên bản đang xử lý.
- So khớp toàn vẹn dữ liệu sử dụng sha256 và kích thước do Drive báo (`IntegrityObservation` từ `DriveObjectStore`) thay cho md5 vì tính nhất quán với cơ chế băm chung của hệ thống.
- Khi kiểm tra tính toàn vẹn phát hiện CORRUPT, handler trả về `failed` với `retryable=False` (`CLOUD_OBJECT_CORRUPT`); trạng thái `OUTCOME_UNKNOWN` trả về `waiting` với mã `provider_unavailable`; trạng thái `MISSING` sau upload trả về `waiting` với `artifact_not_ready`.
- Trường `metrics` phản hồi trả đủ thông tin theo hợp đồng `PersistVideoOutputResult` (`output_artifact_version_id`, `output_sha256`, `cloud_location_id`, `cloud_location_verification_ref`, `upload_receipt_ref`, `provider_namespace_ref`); các trường `output_metadata_ref` và `verified_at` sẽ do composition root hoặc gói tích hợp tiếp theo bổ sung khi cần.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/storage_meta/persist_handler.py').read_text(encoding='utf-8'); assert 'credential_unavailable' in t and 'from src.' not in t and 'fake' not in t.lower(), 'PW-I2'"` | 0 | Khẳng định thành công, không in lỗi |
| `python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider` | 0 | `33 passed in 1.90s` |
| `python -m pytest tests/integration/prod_wiring/test_pw_i2_persist_output.py -q -p no:cacheprovider` | 0 | `11 passed in 4.68s` |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/storage_meta/persist_handler.py').read_text(encoding='utf-8'); assert 'credential_unavailable' in t and 'from src.' not in t and 'fake' not in t.lower(), 'PW-I2'"` | 0 | Khẳng định thành công, không in lỗi |
| `git diff --check` | 0 | Không có output (sạch khoảng trắng thừa) |

## Phản ví dụ đã loại trừ

- Upload trước khi commit receipt: Đã kiểm chứng qua test `test_the_receipt_is_committed_before_the_upload_starts`, hook kiểm tra thấy bản ghi PREPARED với id Drive đã commit ngay trong lúc upload chuẩn bị bắt đầu.
- Upload đôi sau khi worker khởi động lại: Đã kiểm chứng qua hai test `test_worker_dying_before_the_upload_resumes_with_a_single_upload` và `test_worker_dying_after_the_object_reached_drive_does_not_upload_twice`, xác nhận không bao giờ có lần upload thứ hai khi byte đã tới Drive hoặc id đã chọn.
- Lỗi 401 bị gộp vào fatal làm job thất bại vĩnh viễn: Đã kiểm chứng qua test `test_401_waits_with_credential_unavailable_then_completes_exactly_one_object`, lỗi 401 đưa job vào trạng thái `WAITING` và tiếp tục hoàn tất khi token phục hồi.
- Nhận diện lỗi 401 bằng khớp chuỗi: Đã kiểm chứng qua test `test_the_handler_maps_the_error_code_and_not_the_message`, xác nhận handler phân biệt bằng mã lỗi `exc.code == DRIVE_CREDENTIAL_INVALID`, chuỗi chứa '401' nhưng không có code bị loại trừ.
- Vị trí cloud VERIFIED khi nội dung lệch: Đã kiểm chứng qua test `test_digest_mismatch_never_verifies_the_cloud_location`, khẳng định khi nội dung Drive lệch thì vị trí cloud trở thành CORRUPT và không có vị trí cloud nào được VERIFIED.

## Mã test phủ

coveredIds: PW-I2-01, CT-STO-004, CT-ORC-007, F-CP7-3-01

- `PW-I2-01`: Được bao phủ bởi `test_success_registers_the_version_two_verified_locations_and_a_verified_receipt`, `test_the_receipt_is_committed_before_the_upload_starts`, `test_worker_dying_before_the_upload_resumes_with_a_single_upload`, `test_worker_dying_after_the_object_reached_drive_does_not_upload_twice`.
- `CT-STO-004`: Được bao phủ bởi `test_success_registers_the_version_two_verified_locations_and_a_verified_receipt` và `test_digest_mismatch_never_verifies_the_cloud_location` (xác thực `observed_hash` và `observed_size_bytes` cho cả hai vị trí local và cloud).
- `CT-ORC-007`: Được bao phủ bởi `test_401_waits_with_credential_unavailable_then_completes_exactly_one_object` và `test_401_during_the_upload_keeps_the_receipt_and_resumes_without_a_second_object` (chuyển đổi trạng thái job qua `JobLifecycleListener` sang `WAITING`).
- `F-CP7-3-01`: Được bao phủ bởi `test_the_store_reports_401_with_its_own_code_on_every_drive_call` và `test_the_handler_maps_the_error_code_and_not_the_message` (mã lỗi `DRIVE_CREDENTIAL_INVALID` riêng biệt cho 401 và ánh xạ sang `credential_unavailable`).

## Mục mở

- Handler `PersistVideoOutput` chưa được đấu nối vào composition root (thuộc gói tích hợp tiếp theo PW-W1).
- Các trường `output_metadata_ref` và `verified_at` chưa có trong `metrics` của handler, sẽ do composition root cấp khi wiring.
- Cổng quan sát đối tượng cloud (`observe`) phục vụ cho `ReconcileStorage` tiếp tục chờ cấp từ composition root.
