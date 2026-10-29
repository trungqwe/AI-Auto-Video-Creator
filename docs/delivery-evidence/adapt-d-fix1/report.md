# ADAPT-D-FIX1: adapter 9Router gọi đúng /v1/chat/completions

## Nhóm lỗi
- Mã gói: ADAPT-D-FIX1
- Nhóm lỗi: R15
- Finding: F-CP7-4-01 (OI-PP-01). URL `/v1/v1/chat` trả HTTP 404 do endpoint cấu hình production mang đuôi `/v1` cộng với đường dẫn cứng `/v1/chat`; thân request mang `{"prompt": ...}` không đúng giao thức chat completions tương thích OpenAI mà 9Router phục vụ, khiến ứng dụng thật không gọi được AI.

## Tệp đã sửa
1. `src/controlplane/config/adapter.py`: Bổ sung lớp `ChatAIRequest(AIRequest)` mang trường `model`; chuẩn hóa URL gửi tới `<gốc>/v1/chat/completions` (loại bỏ đuôi `/v1` nếu endpoint đã có đuôi `/v1`); tạo thân request OpenAI-compatible gồm `model` (từ request nếu có) và `messages: [{"role": "user", "content": prompt}]`.
2. `src/creative/adapters/real_route_executor.py`: Nhập `ChatAIRequest` từ `controlplane.config.adapter`, loại bỏ import `AIRequest`; trong `NineRouterExecutor.execute` truyền `decision.model_ref` vào `ChatAIRequest(prompt=prompt, config_revision_id=decision.route_revision, model=decision.model_ref)`; cập nhật chú thích D8.
3. `tests/integration/adapt/d/test_adapt_d_ai.py`: Nới lỏng fixture `isolate_network_and_sleep` cho phép kết nối loopback `127.0.0.1`; sửa các khẳng định URL `/v1/chat` thành `/v1/chat/completions` và kiểm tra thân request; bổ sung fixture `fake_router` cùng các test HTTP loopback thực tế (`test_loopback_pipeline_posts_chat_completions_for_origin_and_v1_endpoint`, `test_loopback_path_is_never_doubled_for_v1_endpoint`).
4. `tests/unit/security/test_http_router_adapter.py`: Sửa URL trong test 429 thành `/v1/chat/completions`; bổ sung hai test HTTP loopback xác minh endpoint origin và endpoint có đuôi `/v1` đều dispatch đúng `/v1/chat/completions` và giữ nguyên kiểm tra registry/drift.
5. `src/creative/adapters/real_ai_invocation.py`: Không cần sửa vì hàm `_model_mapping` đã đọc `choices[0].message.content`, được xác nhận đạt bởi test tích hợp loopback.

## Lệch so với yêu cầu
- `AIRequest` tại `src/controlplane/config/models.py` nằm ngoài danh sách owned paths nên không thể sửa trực tiếp tệp đó; trường `model` được đặt tại lớp con `ChatAIRequest` trong `src/controlplane/config/adapter.py`. `AIRequest` gốc giữ nguyên vẹn; đề xuất gói sau gộp trường `model` vào `AIRequest` nếu cần.

## Lệnh kiểm đã chạy
1. **Lệnh RED bước 4** (chứng kiến thất bại trước khi sửa mã production):
   - Lệnh: `python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py -q -p no:cacheprovider`
   - Mã thoát (exit code): `1`
   - Danh sách test hỏng:
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_executor_takes_timeout_retry_backoff_and_endpoint_from_config` (AssertionError: assert 'http://127.0.0.1:20128/v1/chat' == 'http://127.0.0.1:20128/v1/chat/completions')
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_loopback_pipeline_posts_chat_completions_for_origin_and_v1_endpoint[]` (AssertionError: assert '/v1/chat' == '/v1/chat/completions')
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_loopback_pipeline_posts_chat_completions_for_origin_and_v1_endpoint[/v1]` (AssertionError: assert '/v1/v1/chat' == '/v1/chat/completions')
     - `tests/integration/adapt/d/test_adapt_d_ai.py::test_loopback_path_is_never_doubled_for_v1_endpoint` (AssertionError: assert '/v1/v1/chat' == '/v1/chat/completions')
   - Dòng tổng kết nguyên văn: `4 failed, 16 passed in 1.78s`
2. **Lệnh GREEN bước 7** (chạy lại test tích hợp sau khi sửa production adapter và executor):
   - Lệnh: `python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py -q -p no:cacheprovider`
   - Mã thoát (exit code): `0`
   - Dòng tổng kết nguyên văn: `20 passed in 1.67s`
3. **Lệnh pytest bắt buộc bước 9**:
   - Lệnh: `python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider`
   - Mã thoát (exit code): `0`
   - Dòng tổng kết nguyên văn: `72 passed in 9.65s`
4. **Lệnh git diff --check (bước 12)**:
   - Lệnh: `git diff --check`
   - Mã thoát (exit code): `0`
5. **Probe quét mẫu bước 10**:
   - Lệnh: `python -c "import pathlib, re; files = ['src/controlplane/config/adapter.py','src/creative/adapters/real_route_executor.py','tests/integration/adapt/d/test_adapt_d_ai.py','tests/unit/security/test_http_router_adapter.py']; bad = [f for f in files if re.search(r'/v1/chat(?!/completions)', pathlib.Path(f).read_text(encoding='utf-8'))]; assert not bad, bad; assert 'json.dumps({"prompt"' not in pathlib.Path(files[0]).read_text(encoding='utf-8')"`
   - Mã thoát (exit code): `0`
6. **Probe report (bước 13)**:
   - Lệnh: `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-d-fix1/report.md').read_text(encoding='utf-8'); assert 'ADAPT-D-FIX1' in t and 'R15' in t, 'report'"`
   - Mã thoát (exit code): `0`

## Phản ví dụ đã loại trừ
- Thân `{"prompt": ...}`: Loại trừ hoàn toàn, thay bằng `{"model": ..., "messages": [{"role": "user", "content": ...}]}`, chứng minh qua test `test_loopback_pipeline_posts_chat_completions_for_origin_and_v1_endpoint` và `test_executor_takes_timeout_retry_backoff_and_endpoint_from_config`.
- Đường dẫn `/v1/chat` và trùng lặp `/v1/v1/chat`: Loại trừ hoàn toàn bằng logic cắt đuôi `/v1` trước khi nối `/v1/chat/completions`, chứng minh qua test `test_loopback_path_is_never_doubled_for_v1_endpoint` và `test_http_adapter_posts_chat_completions_for_origin_and_v1_endpoint`.
- Bỏ kiểm registry hoặc header provenance: Giữ nguyên vẹn toàn bộ cơ chế xác thực registry, chống drift endpoint, và các header `X-Config-Revision-ID`, `X-Route-Provenance`, `Authorization`, chứng minh qua test `test_http_adapter_endpoint_registry_and_drift_checks_still_apply_with_v1_suffix` và `test_http_adapter_route_provenance_stamping`.
- Test chỉ giả `urlopen` mà không kiểm tra đường dẫn và thân thật: Đã bổ sung các test dùng máy chủ HTTP loopback thật (`_FakeRouterHandler` và `_RecordingHandler`) ghi nhận path, headers, body thật.
- Test mới không hỏng với mã cũ: Đã chứng kiến và ghi nhận bước RED với 4 test hỏng ở bước 4 trước khi sửa code production.

## Giới hạn
- Gói thuộc phạm vi nhóm lỗi R15: không thay đổi route J-18, không sửa cấu hình endpoint trong các tệp config, không thay đổi prompt hay validator.
- Các bài kiểm thử sử dụng máy chủ HTTP loopback cục bộ, không gọi tới 9Router thật bên ngoài môi trường test. CP7-4 sẽ tiến hành đo kiểm lại trên 9Router thật sau khi tích hợp.
