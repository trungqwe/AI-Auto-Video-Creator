# ADAPT-D: AIInvocationPort trên RoutedInvocationService qua 9Router

## 1. Phạm vi và tệp đã sửa
- `src/controlplane/config/adapter.py` (thêm `ApprovedEndpointRegistry.from_config` và thuộc tính `config_owned`; `NineRouterHTTPAdapter` chấp nhận registry `config_owned`; `DEFAULT_APPROVED_ENDPOINTS` giữ nguyên)
- `src/creative/adapters/real_route_executor.py` (mô-đun mới)
- `src/creative/adapters/real_ai_invocation.py`
- `tests/integration/adapt/d/test_adapt_d_ai.py`
- `docs/delivery-evidence/adapt-d/report.md`
Không sửa `tests/unit/security/test_http_router_adapter.py`.
Rebase: HEAD d28aefd là con trực tiếp của integration head 258b993, không có xung đột, không đổi mã sản phẩm ở lượt cấp lại này.

## 2. Thiết kế và giả định D8
- RoutedAIInvocation gọi RoutedInvocationService.invoke (J-18), không tự resolve; WAITING_PROVIDER do RATE_LIMIT hoặc TIMEOUT (hoặc chưa có route) và BUDGET_BLOCKED thành WaitingAIInvocationResult (retryable=True); WAITING_PROVIDER sau lỗi AUTH hoặc UNKNOWN là lỗi cuối provider_failed để thông tin xác thực sai không chờ vô hạn.
- monthly_limit và hard_stop lấy từ cấu hình qua budget_policy_from_config, không có mặc định.
- GIẢ ĐỊNH: request_for (capacity_reservation_ref sang ProviderRouteRequest) do ADAPT-WIRE cấp; prompt và đầu ra đi qua InvocationPayloadStore theo ref vì J-18 chỉ đưa payload ref cho executor; config_revision_id gửi 9Router là route_revision; endpoint cấu hình là origin vì NineRouterHTTPAdapter tự nối /v1/chat (kế hoạch mục 7.2 ghi dạng có /v1, Control xác nhận ở CP7, OI-ADAPT-05).
- should_block của J chặn khi chi đã tiêu lớn hơn hạn mức (bằng đúng hạn mức chưa chặn); đây là hành vi J-18 hiện có, không đổi ở slice này.

## 3. Lệnh đã chạy
Kết quả chạy trên baseline đã rebase (stdout/stderr và exit code thực tế):

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| Lệnh 1 | git diff --check | 0 | Sạch |
| Lệnh 2 | python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider | 0 | 20 passed (17 test tích hợp D, 3 test unit security) |
| Lệnh 3 | probe adapter D (RoutedInvocationService có, mock-9router và from src. không có) | 0 | Đạt |

## 4. RED/GREEN
Nêu trung thực: RED hợp lệ chỉ chứng kiến cho phần registry (AttributeError). Phần real_* được viết sau test registry nên không có RED riêng của phần AI; không tuyên bố ngược lại.

## 5. Việc còn lại (backlog, không làm trong slice này)
ADAPT-WIRE cấp request_for và nguồn credential thật; xác nhận cổng và đường dẫn 9Router ở CP7; không gọi dịch vụ thật trong slice này.
