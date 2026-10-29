# ADAPT-D-FIX2: adapter 9Router xin phản hồi JSON không stream

## Nhóm lỗi
- Mã gói: ADAPT-D-FIX2
- Nhóm lỗi: R16
- Finding: CP7-4 trên 9Router thật 29/10/2026 20:11Z sau ADAPT-D-FIX1: 9Router trả text/event-stream (SSE) với HTTP 200 vì request thiếu `"stream": false` trong thân và thiếu header `Accept: application/json`. Khi nhận SSE, NineRouterHTTPAdapter gặp lỗi thô `JSONDecodeError` (`PipelineRejected ai_invocation_failed provider_failed`), khiến ứng dụng thật không gọi được AI.

## Tệp đã sửa
1. `src/controlplane/config/adapter.py`:
   - Bổ sung hàm module-level `_response_content_type(resp: Any) -> str` để trích xuất `Content-Type` một cách an toàn kể cả khi phản hồi giả không có header hoặc header rỗng.
   - Trong `send_request`, thêm `"stream": False` vào payload thân request và thêm header `"Accept": "application/json"`.
   - Kiểm tra `Content-Type` ngay khi nhận phản hồi; nếu chứa `text/event-stream`, lập tức raise `ProviderHTTPError` nêu rõ chi tiết mà không đọc hay ghép body SSE, không retry.
   - Cập nhật docstring của `NineRouterHTTPAdapter` với bullet R16.
2. `tests/integration/adapt/d/test_adapt_d_ai.py`:
   - Bổ sung `ProviderHTTPError` vào import từ `controlplane.config.adapter`.
   - Cập nhật `_FakeRouterHandler.do_POST` đóng vai 9Router thật: trả SSE khi thiếu `"stream": false` hoặc thiếu `Accept: application/json` hoặc khi `force_sse=True`; chỉ trả JSON khi thỏa mãn đầy đủ cả hai điều kiện.
   - Cập nhật fixture `fake_router` hỗ trợ cờ `force_sse=False`.
   - Cập nhật các khẳng định trong `test_loopback_pipeline_posts_chat_completions_for_origin_and_v1_endpoint`, `test_loopback_path_is_never_doubled_for_v1_endpoint` và `test_executor_takes_timeout_retry_backoff_and_endpoint_from_config` để kiểm tra `"stream": False` và header `Accept: application/json`.
   - Bổ sung 2 test mới: `test_loopback_sse_reply_from_router_becomes_clear_provider_error` và `test_loopback_pipeline_sse_reply_is_final_provider_failed`.
3. `tests/unit/security/test_http_router_adapter.py`:
   - Bổ sung `ProviderHTTPError` vào import từ `controlplane.config.adapter`.
   - Cập nhật `_RecordingHandler.do_POST` trả SSE khi thiếu `"stream": false` hoặc header `Accept` hoặc khi `force_sse=True`.
   - Cập nhật `_start_router(force_sse=False)` hỗ trợ cờ `force_sse`.
   - Cập nhật `test_http_adapter_posts_chat_completions_for_origin_and_v1_endpoint` kiểm tra `"stream": False` và header `Accept: application/json`.
   - Bổ sung 2 test unit mới: `test_http_adapter_requests_non_stream_json` và `test_http_adapter_sse_reply_raises_clear_provider_error`.

## Lệnh kiểm đã chạy
1. **Lệnh RED bước 3** (chứng kiến thất bại trước khi sửa mã production):
   - Lệnh: `python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider`
   - Mã thoát (exit code): `1`
   - Danh sách test hỏng:
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_executor_takes_timeout_retry_backoff_and_endpoint_from_config` (AssertionError: Right contains 1 more item: {'stream': False})
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_loopback_pipeline_posts_chat_completions_for_origin_and_v1_endpoint[]` (AssertionError: assert 'provider_failed: JSONDecodeError: Expecting value: line 1 column 1 (char 0)' is None)
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_loopback_pipeline_posts_chat_completions_for_origin_and_v1_endpoint[/v1]` (AssertionError: assert 'provider_failed: JSONDecodeError: Expecting value: line 1 column 1 (char 0)' is None)
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_loopback_path_is_never_doubled_for_v1_endpoint` (AssertionError: assert False is True)
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_loopback_sse_reply_from_router_becomes_clear_provider_error` (AssertionError: assert False where False = isinstance(JSONDecodeError(...), ProviderHTTPError))
     - `tests/unit/security/test_http_router_adapter.py::TestHTTPRouterAdapter::test_http_adapter_posts_chat_completions_for_origin_and_v1_endpoint` (JSONDecodeError: Expecting value: line 1 column 1 (char 0))
     - `tests/unit/security/test_http_router_adapter.py::TestHTTPRouterAdapter::test_http_adapter_requests_non_stream_json` (JSONDecodeError: Expecting value: line 1 column 1 (char 0))
     - `tests/unit/security/test_http_router_adapter.py::TestHTTPRouterAdapter::test_http_adapter_sse_reply_raises_clear_provider_error` (JSONDecodeError: Expecting value: line 1 column 1 (char 0))
   - Dòng tổng kết nguyên văn: `8 failed, 21 passed in 4.60s`
2. **Lệnh GREEN bước 5** (chạy lại pytest sau khi sửa production):
   - Lệnh: `python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider`
   - Mã thoát (exit code): `0`
   - Dòng tổng kết nguyên văn: `29 passed in 4.28s`
3. **Lệnh git diff --check (bước 7)**:
   - Lệnh: `git diff --check`
   - Mã thoát (exit code): `0`
4. **Lệnh probe report (bước 8)**:
   - Lệnh: `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-d-fix2/report.md').read_text(encoding='utf-8'); assert 'ADAPT-D-FIX2' in t and 'R16' in t, 'report'"`
   - Mã thoát (exit code): `0`

## Phản ví dụ đã loại trừ
- Ghép SSE thành JSON trong adapter thay vì xin không stream: Adapter loại trừ hoàn toàn việc đọc và ghép body SSE; khi nhận Content-Type text/event-stream thì lập tức raise `ProviderHTTPError` mà không đọc hay phân tích payload SSE.
- Chỉ thêm header mà không thêm stream false (hoặc ngược lại): Test xác nhận cả hai điều kiện: thân request phải mang `"stream": false` và header phải mang `Accept: application/json`.
- Nuốt lỗi: Adapter raise `ProviderHTTPError` rõ ràng với thông điệp chứa `text/event-stream`, qua pipeline được ghi nhận thành `provider_failed: ...`, không bị nuốt hay retry.
- Test không hỏng với mã cũ: Đã chứng kiến và ghi nhận bước RED với 8 test hỏng ở bước 3 trước khi sửa code production.

## Giới hạn
- Sử dụng máy chủ HTTP loopback cục bộ để đóng vai 9Router thay vì gọi tới 9Router thật bên ngoài môi trường test; CP7-4 sẽ đo kiểm lại trên 9Router thật sau khi tích hợp.
- Không thay đổi URL, model, messages, header provenance (`X-Route-Provenance`, `X-Config-Revision-ID`), `Authorization`, cơ chế kiểm registry, retry hay phân loại lỗi cho các trường hợp khác.
