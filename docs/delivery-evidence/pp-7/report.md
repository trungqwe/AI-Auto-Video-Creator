# Báo cáo bằng chứng chuyển giao: PP-7

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `src/controlplane/infrastructure/production_ports/vision_route.py`: Triển khai `RouterVisionRoute` (cài đặt cổng `VisionRoutePort`) gửi yêu cầu thị giác tới 9Router theo hồ sơ production (CT-AI-ROUTE-001, INV-012, QR-SEC-009):
  * `RouterVisionRoute`: Nhận `(endpoint, model_refs, credentials, account_ref)`. Kiểm tra tính hợp lệ và chuẩn hóa `endpoint` qua `ApprovedEndpointRegistry.from_config([endpoint])`. Sao chép bất biến `model_refs`, kiểm tra hợp lệ các tham số đầu vào bằng `ValueError`. Cấu hình `urllib.request.build_opener` với `ProxyHandler({})` và `_NoRedirectHandler()` để tuyệt đối không qua proxy và không theo redirect.
  * `invoke_vision(ai_role, instructions, image_base64, media_type, timeout_seconds)`: Xác thực vai trò `ai_role` có trong `model_refs` và kiểm tra tham số đầu vào nghiêm ngặt trước khi gọi mạng (từ chối ngay bằng `VisionRouteError('unknown_role')` hoặc `ValueError`).
  * Thu nhận khóa bảo mật chỉ trong phạm vi một cuộc gọi duy nhất thông qua `credentials.acquire(CREDENTIAL_METHOD, self._account_ref)`. Khóa không bao giờ được cache, log hay đưa vào ngoại lệ.
  * Gửi yêu cầu `POST <endpoint>/chat/completions` với thân kiểu OpenAI (gồm model tương ứng vai trò, tin nhắn chứa văn bản hướng dẫn và data URL ảnh định dạng `data:<media_type>;base64,<image_base64>`), header `Authorization: Bearer <key>`.
  * Trả về nội dung `choices[0].message.content`. Giới hạn độ dài phản hồi tối đa theo `MAX_RESPONSE_BYTES = 1048576` (1 MiB).
  * Quy đổi mọi lỗi mạng, lỗi HTTP (từ 401/403 sang `unauthorized`, 429 sang `rate_limited` và 5xx sang `server_error`, các mã HTTP khác sang `http_error`), lỗi timeout (`VisionRouteTimeoutError('timeout')`), lỗi thân phản hồi (`bad_response`) thành `VisionRouteError` với mã cố định, không để lộ khóa bí mật trong thông điệp, traceback hay biểu diễn chuỗi.
- `tests/integration/prod_ports/test_pp_7_vision_route.py`: Bộ kiểm thử tích hợp toàn diện gồm 87 ca kiểm thử trên máy chủ loopback HTTP `127.0.0.1` đóng vai 9Router và kho bí mật `DpapiSecretStore` tạm trong `tmp_path`. Bao quát gửi request chuẩn OpenAI, kiểm tra header Bearer canary, tích hợp qua `parse_vision_output`, từ chối vai trò lạ và đối số sai trước mạng, sao chép bất biến `model_refs`, xử lý khóa thu hồi / sai định dạng, chặn redirect, đổi lỗi HTTP an toàn, kiểm soát kích thước thân và kiểm tra tĩnh AST/mã nguồn.
- `docs/delivery-evidence/pp-7/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ
Tại Bước 10, sau khi tạo khung tạm (stub) ném `NotImplementedError('PP-7')` tại `vision_route.py` và hoàn thiện bộ kiểm thử `test_pp_7_vision_route.py`, lệnh pytest được thực thi với Python interpreter đã khóa của lane để chứng kiến oracle RED hợp lệ:
```text
87 failed in 36.81s
```
- **Exit Code:** `1`
- **5 tên test FAILED đầu tiên:**
  1. `tests/integration/prod_ports/test_pp_7_vision_route.py::test_posts_openai_body_with_bearer_canary_and_returns_content`
  2. `tests/integration/prod_ports/test_pp_7_vision_route.py::test_model_follows_role`
  3. `tests/integration/prod_ports/test_pp_7_vision_route.py::test_credentials_are_acquired_with_method_and_account`
  4. `tests/integration/prod_ports/test_pp_7_vision_route.py::test_endpoint_is_normalized_and_path_appended[/v1-/v1]`
  5. `tests/integration/prod_ports/test_pp_7_vision_route.py::test_endpoint_is_normalized_and_path_appended[/v1/-/v1]`
- **Xác thực Oracle RED:**
  * Các ca kiểm thử thất bại do `NotImplementedError: PP-7`, `AttributeError: 'RouterVisionRoute' object has no attribute 'endpoint'`, `DID NOT RAISE ValueError` hoặc `AssertionError`.
  * Hoàn toàn không có lỗi collection, `ImportError` hay `ModuleNotFoundError`.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 14) | `git diff --check` | 0 | Thoát 0, không có cảnh báo khoảng trắng hay định dạng dòng |
| Lệnh kiểm 2 (Bước 13) | `python -m pytest tests/integration/prod_ports/test_pp_7_vision_route.py -q -p no:cacheprovider` | 0 | `87 passed in 36.43s` |
| Lệnh kiểm 3 (Bước 15) | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/vision_route.py').read_text(encoding='utf-8').lower(); assert 'chat/completions' in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-7'"` | 0 | Thoát 0, probe tĩnh đạt chuẩn, không có AssertionError |

## 4. Ánh xạ yêu cầu nghiệm thu

### Yêu cầu 1: RouterVisionRoute cài đặt invoke_vision với 9Router và OpenAI payload
- **Yêu cầu:** `RouterVisionRoute(endpoint, model_refs, credentials, account_ref)` cài `VisionRoutePort.invoke_vision(ai_role, instructions, image_base64, media_type, timeout_seconds)`: `ai_role` phải có trong `model_refs`; khóa lấy qua `credentials.acquire(CREDENTIAL_METHOD, account_ref)`; gửi `POST <endpoint>/chat/completions` bằng `urllib.request` với thân kiểu OpenAI (model, `messages` gồm `instructions` và ảnh `data:<media_type>;base64,<image_base64>`), `Authorization: Bearer`; trả `choices[0].message.content`.
- **Các test chứng minh:**
  * `test_posts_openai_body_with_bearer_canary_and_returns_content`: Xác nhận gửi HTTP POST đúng `/v1/chat/completions`, header Bearer chứa canary từ kho DPAPI, thân JSON đúng cấu trúc OpenAI với data URL ảnh, trả về nội dung `choices[0].message.content`.
  * `test_model_follows_role`: Model trong thân JSON đi theo đúng vai trò được định cấu hình (`script` -> model tương ứng).
  * `test_credentials_are_acquired_with_method_and_account`: Thu nhận khóa thông qua `credentials.acquire` với đúng phương thức `CREDENTIAL_METHOD` và tài khoản `ACCOUNT`.
  * `test_endpoint_is_normalized_and_path_appended`: Đường dẫn endpoint được chuẩn hóa và nối thêm hậu tố `/chat/completions` chính xác cho các dạng tiền tố khác nhau (`/v1`, `/v1/`, `''`).
  * `test_content_goes_through_parse_vision_output`: Nội dung trả về qua `parse_vision_output` giải mã thành công thành đối tượng `ImageDetection` và các vùng bounding box hợp lệ.
  * `test_unknown_role_is_rejected_before_network`: Vai trò `ai_role` lạ, rỗng hoặc sai kiểu bị từ chối ngay lập tức trước khi gọi mạng (không gửi HTTP request, không acquire khóa).
- **Phản ví dụ đã loại trừ:** Gọi host khác 9Router; nhánh giả trong mã production.

### Yêu cầu 2: An toàn endpoint, không redirect, không proxy, che giấu khóa khi lỗi
- **Yêu cầu:** `endpoint` phải thuộc `ApprovedEndpointRegistry.from_config([endpoint])`; không theo redirect, không proxy, timeout theo tham số; lỗi mạng hay HTTP (401, 429, 5xx) và phản hồi sai dạng đổi thành ngoại lệ không chứa khóa.
- **Các test chứng minh:**
  * `test_http_error_becomes_safe_exception`: Các mã lỗi HTTP (400, 401, 403, 404, 429, 500, 502, 503) đều được chuyển đổi thành `VisionRouteError` với mã cố định, không lộ chuỗi canary dù thân phản hồi lỗi của máy chủ chứa canary.
  * `test_redirect_is_not_followed`: Các phản hồi chuyển hướng 301, 302, 303, 307, 308 bị chặn hoàn toàn, máy chủ đích không nhận bất kỳ request nào, chuyển thành `VisionRouteError('http_error')`.
  * `test_malformed_response_is_rejected`: Phản hồi không phải JSON, JSON rỗng, thiếu trường `choices`, `choices` rỗng, nội dung null hoặc rỗng, chuỗi byte sai bảng mã đều bị từ chối với mã `bad_response`.
  * `test_timeout_parameter_is_applied`: Tham số timeout được áp dụng chính xác cho socket timeout, ném `VisionRouteTimeoutError('timeout')` kế thừa `TimeoutError`.
  * `test_proxy_environment_is_ignored`: Bỏ qua hoàn toàn các biến môi trường proxy (`http_proxy`, `https_proxy`, `all_proxy`), kết nối trực tiếp đến endpoint loopback.
  * `test_constructor_rejects_unapproved_endpoint`: Endpoint không hợp lệ hoặc ngoài danh sách được duyệt bị từ chối ngay trong hàm dựng bởi `UnapprovedEndpointError`.
  * `test_canary_never_reaches_logs_output_or_repr`: Khóa canary tuyệt đối không rò rỉ vào log, stdout, stderr, biểu diễn `repr` hay `str` của route.
  * `test_source_has_no_forbidden_text_and_only_expected_imports`: Kiểm tra tĩnh AST và văn bản mã nguồn xác nhận mã thuần, chỉ import các module cho phép, không chứa chuỗi cấm (`from src.`, `mock`, `fake`, `os.environ`, `getenv`, `subprocess`, `logging`, `print(`, `import requests`, `httpx`, `socket`, `http://`, `https://`), bắt buộc có `chat/completions`, `authorization`, `ProxyHandler`, `redirect_request`.
- **Phản ví dụ đã loại trừ:** Theo redirect; khóa vào log hay ngoại lệ.

## 5. Giới hạn và GIẢ ĐỊNH
- (a) Tham số timeout được áp dụng cho từng thao tác socket (connect/read timeout qua urllib) chứ không phải tổng thời gian toàn bộ tiến trình.
- (b) Endpoint do cấu hình cấp và đã bao gồm tiền tố `/v1` nếu dịch vụ 9Router yêu cầu.
- (c) Không thực hiện cơ chế tự động thử lại (retry); lỗi được báo cáo ngay lập tức cho caller xử lý.
- (d) Chỉ tiếp nhận nội dung phản hồi dạng chuỗi ký tự hợp lệ; các trường hợp rỗng hoặc sai kiểu bị từ chối bằng `bad_response`.
- (e) Không thực hiện chạy full regression suite; tuân thủ nghiêm ngặt nguyên tắc kỷ luật thực thi mục tiêu (`targetedCommand`). Không tự ý `git push` hay `git merge`, không chạm vào nhánh `main` hay `backup`. Cổng kích hoạt sản xuất thực tế vẫn giữ nguyên trạng thái khóa an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
