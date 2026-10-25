# Báo cáo bằng chứng chuyển giao: PP-5

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `src/controlplane/infrastructure/production_ports/drive_placement.py`: Triển khai các thành phần cấu trúc và khởi tạo thư mục Google Drive cho `ProductionRuntime` (CT-STO-003, ADR-0006):
  * `DrivePlacementError`: Ngoại lệ riêng của module khi khởi tạo hoặc xác minh vị trí thư mục gặp lỗi.
  * `DrivePlacement`: Dataclass đóng băng (`frozen=True`) chứa thuộc tính `placement: Mapping[str, str]` (bọc trong `MappingProxyType` để đảm bảo bất biến) và `fallback_parent_id: str` (ID thư mục gốc).
  * `_PlacementHttp`: Lớp bao HTTP viết riêng kế thừa và tương đương `_BrokerHttp`, tự động gắn tiêu đề `Authorization: Bearer <token>` thu được từ `broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF)` qua context manager `ExitStack`. Trường hợp không lấy được token hoặc token rỗng ném ngoại lệ nội bộ `_TokenUnavailableError`.
  * Các hàm tiện ích trạng thái: `_is_text`, `_is_positive`, `_read_state`, `_discard`, `_write_state` (sử dụng tệp tạm `.tmp` kèm `os.fsync` và `os.replace` để bảo đảm tính nguyên tử khi ghi tệp trạng thái, nội dung chỉ chứa tên và ID, không chứa bí mật hay token canary).
  * `DrivePlacementBootstrap`: Lớp khởi tạo cấu hình vị trí thư mục Drive nhận các tham số `(broker, state_file, root_name, namespaces, *, retry_max_attempts, backoff_base_seconds, backoff_cap_seconds, timeout_seconds, http_factory=None, sleep=time.sleep)`. Kiểm tra chặt chẽ tính hợp lệ của tham số trong hàm dựng (ném `ValueError` nếu tham số không hợp lệ).
  * Phương thức `_open_service()` gọi `build('drive', 'v3', http=..., static_discovery=True, cache_discovery=False)`.
  * Phương thức `_run(operation)` triển khai cơ chế thử lại lũy tiến (`exponential backoff`) tối đa `retry_max_attempts` lần với giới hạn trần `backoff_cap_seconds` đối với các mã lỗi HTTP có thể thử lại (408, 429, 5xx) cũng như lỗi mạng `OSError`/`HttpLib2Error`. Các lỗi 400, 401, 403, 404 trên thao tác tạo thư mục và lỗi thiếu token sẽ thất bại ngay lập tức mà không thử lại, ném `DrivePlacementError`.
  * Phương thức `ensure()` thực hiện: Lần đầu tạo thư mục gốc `root_name` rồi tạo lần lượt từng thư mục con cho mỗi namespace (với mimeType `application/vnd.google-apps.folder` và `parents` trỏ về ID thư mục gốc), ghi tệp trạng thái nguyên tử sau mỗi lần tạo; các lần chạy sau đọc tệp trạng thái và xác minh từng ID bằng `files.get(fields='id,trashed,mimeType')`; ID thiếu, 404, nằm trong thùng rác hoặc không phải thư mục sẽ được tạo lại đúng thư mục đó và ghi đè trạng thái; tuyệt đối không sử dụng `files().list`.
- `tests/integration/prod_ports/test_pp_5_drive_placement.py`: Bộ kiểm thử tích hợp toàn diện gồm 16 hàm kiểm thử (bao quát 54 ca kiểm thử) sử dụng máy chủ Drive giả lập loopback (`ThreadingHTTPServer`) trên `127.0.0.1`, chuyển hướng HTTP qua `LoopbackHttp`, bao quát toàn bộ các kịch bản tạo mới, tái sử dụng, phục hồi khi hỏng hóc, thử lại lỗi tạm thời, từ chối tham số sai, xử lý tệp trạng thái hỏng (fail-closed), tích hợp với `DriveObjectStore.reserve_object_id` và kiểm tra tĩnh AST/mã nguồn.
- `docs/delivery-evidence/pp-5/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ (Bước 9)
Tại Bước 9, sau khi tạo khung tạm (stub) ném `NotImplementedError('PP-5')` tại `drive_placement.py` và hoàn thành bộ kiểm thử `test_pp_5_drive_placement.py`, lệnh pytest được thực thi với Python interpreter đã khóa để chứng kiến oracle RED hợp lệ:
```text
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_first_run_creates_root_then_one_folder_per_namespace
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_state_file_has_only_names_and_ids
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_state_is_written_through_temp_file_and_os_replace
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_second_run_verifies_each_id_without_creating
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_unusable_namespace_folder_is_recreated_alone[trashed]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_unusable_namespace_folder_is_recreated_alone[missing]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_unusable_namespace_folder_is_recreated_alone[not_folder]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_unusable_root_recreates_root_and_every_namespace[trashed]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_unusable_root_recreates_root_and_every_namespace[missing]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_state_for_another_root_name_creates_a_new_root
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_transient_status_is_retried_then_succeeds[408]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_transient_status_is_retried_then_succeeds[429]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_transient_status_is_retried_then_succeeds[500]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_transient_status_is_retried_then_succeeds[502]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_transient_status_is_retried_then_succeeds[503]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_transient_status_is_retried_then_succeeds[504]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_transient_status_gives_up_after_retry_max_attempts
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_backoff_is_capped
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_non_retryable_status_fails_at_once[400]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_non_retryable_status_fails_at_once[401]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_non_retryable_status_fails_at_once[403]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_non_retryable_status_fails_at_once[404]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_missing_or_empty_token_fails_before_any_drive_request[RefusingBroker]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_missing_or_empty_token_fails_before_any_drive_request[EmptyBroker]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_network_error_is_retried_then_fails
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[{]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[[]]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[null]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[\xff\xfe\x00]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[{"root": {"name": "AI-Auto-Video-Creator", "id": "folder-1"}}]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[{"root": null, "namespaces": {}}]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[{"root": {"name": "AI-Auto-Video-Creator", "id": "folder-1", "x": 1}, "namespaces": {}}]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[{"root": {"name": "AI-Auto-Video-Creator", "id": ""}, "namespaces": {}}]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[{"root": {"name": "AI-Auto-Video-Creator", "id": "folder-1"}, "namespaces": {"original": 5}}]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_corrupt_state_file_fails_closed[{"root": {"name": "AI-Auto-Video-Creator", "id": "folder-1"}, "namespaces": {"original": ""}}]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_atomic_write_failure_keeps_previous_state
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_reserve_object_id_receives_its_parent_from_placement
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override0]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override1]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override2]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override3]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override4]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override5]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override6]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override7]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override8]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override9]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override10]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override11]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override12]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override13]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_constructor_rejects_bad_arguments[override14]
FAILED tests/integration/prod_ports/test_pp_5_drive_placement.py::test_source_is_clean_and_uses_required_calls
54 failed in 27.38s
```
- **Exit Code:** `1`
- **Xác thực Oracle RED:**
  * 38 ca kiểm thử thất bại do `NotImplementedError: PP-5` phát ra từ phương thức `ensure()` của khung tạm.
  * 15 ca kiểm thử tham số hóa của `test_constructor_rejects_bad_arguments` thất bại do `Failed: DID NOT RAISE ValueError` vì hàm dựng của khung tạm chỉ có lệnh `pass`.
  * 1 ca kiểm thử `test_source_is_clean_and_uses_required_calls` thất bại do `AssertionError: Missing required token: static_discovery=true` vì mã nguồn khung tạm chưa chứa cấu hình khám phá tĩnh bắt buộc.
  * Hoàn toàn không có lỗi collection, `ImportError` hay `ModuleNotFoundError`.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm tra
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 17) | `git diff --check` | 0 | Thoát 0, không có lỗi khoảng trắng thừa hay định dạng dòng |
| Lệnh kiểm 2 (Bước 14) | `python -m pytest tests/integration/prod_ports/test_pp_5_drive_placement.py -q -p no:cacheprovider` | 0 | `54 passed in 28.78s` |
| Lệnh kiểm 3 (Bước 15) | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/drive_placement.py').read_text(encoding='utf-8').lower(); assert 'static_discovery=true' in t and 'files().list' not in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-5'"` | 0 | Thoát 0, probe tĩnh đạt chuẩn, không có AssertionError |

## 4. Ánh xạ các yêu cầu nghiệm thu (Acceptance Criteria)

### Yêu cầu 1: Cấu trúc DrivePlacement và DrivePlacementBootstrap trả về kết quả hợp lệ cho DriveObjectStore
- **Yêu cầu:** `DrivePlacementError` và `DrivePlacementBootstrap(broker, state_file, root_name, namespaces, *, retry_max_attempts, backoff_base_seconds, backoff_cap_seconds, timeout_seconds, http_factory=None, sleep=time.sleep)` có `ensure()` trả `DrivePlacement` (dataclass frozen: `placement: Mapping[str, str]`, `fallback_parent_id: str`); `fallback_parent_id` là ID thư mục gốc, `placement` không rỗng.
- **Các test chứng minh:**
  * `test_first_run_creates_root_then_one_folder_per_namespace`: Lần đầu tạo thư mục gốc với tên cấu hình rồi tạo các thư mục con cho mỗi namespace, trả về đối tượng `DrivePlacement` bất biến với `fallback_parent_id` là ID thư mục gốc và `placement` ánh xạ đúng ID từng namespace.
  * `test_reserve_object_id_receives_its_parent_from_placement`: Kiểm chứng tích hợp với `DriveObjectStore.reserve_object_id` (sử dụng cấu hình `DriveStoreConfig` với `placement` và `fallback_parent_id` sinh từ bootstrap), nhận được thư mục cha chính xác từ `placement` tương ứng với namespace 'output'.
- **Phản ví dụ đã loại trừ:** Trả về placement giả hoặc rỗng khi Drive gặp sự cố.

### Yêu cầu 2: Cơ chế tạo thư mục, xác minh ID và ghi tệp trạng thái nguyên tử
- **Yêu cầu:** Lần đầu tạo thư mục gốc `root_name` rồi một thư mục con cho mỗi namespace (mimeType `application/vnd.google-apps.folder`, `parents` đúng) và ghi `state_file` nguyên tử (UTF-8, tệp tạm rồi `os.replace`) chỉ gồm tên và ID; lần sau đọc tệp và xác minh từng ID bằng `files.get(fields='id,trashed,mimeType')`; ID thiếu, 404 hay đã vào thùng rác thì tạo lại đúng thư mục đó và ghi đè; không `files.list`.
- **Các test chứng minh:**
  * `test_state_file_has_only_names_and_ids`: Tệp trạng thái chỉ chứa cấu trúc tên và ID của gốc cùng các namespace, tuyệt đối không chứa token canary, không để lại tệp tạm.
  * `test_state_is_written_through_temp_file_and_os_replace`: Xác nhận tệp trạng thái được ghi tuần tự qua tệp tạm `.tmp` kèm `os.replace` (đúng 4 lần ghi tương ứng với việc tạo gốc và 3 namespace).
  * `test_second_run_verifies_each_id_without_creating`: Lần chạy thứ hai xác minh từng ID bằng lệnh `files.get(fields='id,trashed,mimeType')`, không gọi lệnh tạo mới nào và không gọi `files.list`.
  * `test_unusable_namespace_folder_is_recreated_alone`: Khi một thư mục namespace bị hỏng (trashed, 404 missing, hoặc đổi mimeType khác thư mục), hệ thống chỉ tạo lại duy nhất thư mục đó và cập nhật tệp trạng thái.
  * `test_unusable_root_recreates_root_and_every_namespace`: Khi thư mục gốc bị hỏng (trashed hoặc missing), hệ thống tự động tạo mới thư mục gốc và toàn bộ các thư mục con namespace trực thuộc.
  * `test_atomic_write_failure_keeps_previous_state`: Khi thao tác `os.replace` thất bại, hệ thống bảo toàn nguyên vẹn nội dung tệp trạng thái trước đó, dọn dẹp tệp tạm và ném `DrivePlacementError`.
- **Phản ví dụ đã loại trừ:** Tạo thư mục mới vô tội vạ mỗi lần chạy; gọi `files.list` quét toàn bộ Drive; rò rỉ token truy cập vào tệp trạng thái; ghi đè tệp trạng thái không nguyên tử.

### Yêu cầu 3: Giao thức kết nối, quản lý Bearer token, thử lại lỗi tạm và fail-closed
- **Yêu cầu:** Gọi Drive bằng `build('drive', 'v3', http=..., static_discovery=True, cache_discovery=False)` với http gắn `Authorization: Bearer` từ `broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF)` (lớp http tương đương `_BrokerHttp`, viết riêng); lỗi tạm (408, 429, 5xx) thử lại tối đa `retry_max_attempts` rồi `DrivePlacementError`; 401, 403 hoặc thiếu token thì `DrivePlacementError` ngay; tệp trạng thái hỏng thì `DrivePlacementError` (fail-closed).
- **Các test chứng minh:**
  * `test_transient_status_is_retried_then_succeeds`: Lỗi tạm thời (408, 429, 500, 502, 503, 504) được tự động thử lại theo lũy tiến và thành công khi dịch vụ hồi phục.
  * `test_transient_status_gives_up_after_retry_max_attempts`: Lỗi tạm thời kéo dài quá số lần thử lại tối đa sẽ dừng và ném `DrivePlacementError` không chứa token.
  * `test_backoff_is_capped`: Khoảng thời gian chờ giữa các lần thử lại tuân thủ đúng trần `backoff_cap_seconds`.
  * `test_non_retryable_status_fails_at_once`: Các lỗi không thể thử lại (400, 401, 403, 404) thất bại ngay lập tức ở lần gọi đầu tiên mà không thử lại và không tạo placement giả.
  * `test_missing_or_empty_token_fails_before_any_drive_request`: Broker từ chối cấp token hoặc trả token rỗng khiến hệ thống ném `DrivePlacementError` trước khi gửi bất kỳ yêu cầu nào tới Drive.
  * `test_network_error_is_retried_then_fails`: Lỗi kết nối mạng cấp socket/HTTP được thử lại tối đa theo cấu hình rồi dừng an toàn.
  * `test_corrupt_state_file_fails_closed`: Tệp trạng thái bị hỏng, rỗng, sai định dạng JSON hoặc sai cấu trúc schema sẽ kích hoạt fail-closed (ném `DrivePlacementError`, không gửi request ra Drive và không ghi đè dữ liệu hỏng).
  * `test_source_is_clean_and_uses_required_calls`: Quét tĩnh AST và văn bản mã nguồn xác nhận mã nguồn hoàn toàn sạch: sử dụng `static_discovery=True`, `cache_discovery=False`, `os.replace`, không gọi `files().list`, không import `from src.`, không chứa chuỗi cấm `mock`, `fake`, `os.environ`, và không import thành phần private từ các module khác.
- **Phản ví dụ đã loại trừ:** Thử lại vô hạn gây nghẽn; nuốt mã lỗi 403 rồi trả placement giả; lộ bí mật qua chuỗi thông điệp ngoại lệ.

## 5. Giới hạn và GIẢ ĐỊNH (Limitations)
- (a) Giả định thiết kế D8/OI-PP-02: Sử dụng duy nhất một thư mục con `output` dùng chung cho toàn bộ sản phẩm xuất ra, không phân cấp thư mục con theo ngày.
- (b) Khi thư mục gốc Drive bị hỏng (thiếu hoặc vào thùng rác), hệ thống chọn giải pháp mặc định đơn giản là tái tạo lại thư mục gốc mới cùng toàn bộ các thư mục con namespace (các thư mục con của gốc cũ không còn dùng được).
- (c) Bất kỳ định danh thư mục nào trên Drive bị thay đổi `mimeType` khác `application/vnd.google-apps.folder` cũng được coi là không hợp lệ và được tái tạo lại.
- (d) Khi thao tác `POST` tạo thư mục gặp lỗi mạng tạm thời, việc thử lại có thể tạo ra các thư mục trùng tên trên Google Drive (do Google Drive cho phép tồn tại nhiều đối tượng trùng tên trong cùng một thư mục cha); hệ thống không tự động dọn dẹp các thư mục mồ côi này.
- (e) Nếu tệp trạng thái đã tồn tại nhưng có `root.name` khác với `root_name` được cấu hình, hệ thống coi như chưa có thư mục gốc cho ứng dụng này và khởi tạo cây thư mục mới.
- (f) Kiểm thử tích hợp được thực hiện 100% trên máy chủ giả lập loopback nội bộ (`127.0.0.1`), tuyệt đối không gửi yêu cầu ra Google Drive thật và không sử dụng tài khoản thật (việc kiểm thử với tài khoản thật sẽ do các tác vụ nghiệm thu môi trường thật CP7-1 đảm nhiệm).
- (g) Không thực hiện chạy full regression suite; tuân thủ nghiêm ngặt nguyên tắc kỷ luật thực thi mục tiêu (`targetedCommand`). Không tự ý `git push` hay `git merge`, không chạm vào nhánh `main` hay `backup`. Cổng kích hoạt sản xuất thực tế vẫn giữ nguyên trạng thái khóa an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
