# CP7-4 — AI qua 9Router thật và chi phí (RG-03)

Ngày đo: 29/10/2026, trên lane lane-cp7-4, bằng interpreter khoá .local-tools/runtime/1ca840a7/venv, dưới quyền thường.

Lệnh: python -m pytest tests/real/test_cp7_ai_real.py -q -p no:cacheprovider bằng interpreter khoá .local-tools/runtime/1ca840a7/venv. Kết quả: 9 failed (9 errors), mã thoát 1. Trần chi phí đã dùng: 0 lời gọi logic hoàn tất (dừng ngay tại canary i=0), 1 HTTP hit thật (status 200), 0 lần thử lại chờ quota, 0.00 USD ghi sổ.

## Kết quả

RG-03.six_roles_valid: BLOCKED
RG-03.router_host_only: BLOCKED
RG-03.ledger_recorded: BLOCKED
RG-03.record_no_secret: BLOCKED
RG-03.latency_p95: BLOCKED
RG-03.budget_guard: BLOCKED
RG-03.warn_80: BLOCKED
RG-03.quota_wait: NOT_OBSERVED
RG-03.secret_scan: BLOCKED

## Chi tiết đo

- six_roles_valid: Bị chặn ngay lời gọi đầu tiên (analysis, i=0) bởi canary đo lường: 9Router trả mã HTTP 200 trên /chat/completions nhưng CreativePipeline từ chối kết quả do lỗi cấu trúc lược đồ AnalysisRejected: ai_output_schema_violation: facts[0].evidence_refs[0] (wrong_type); không có lời gọi logic nào hoàn tất.
- router_host_only: Bị chặn trước khi kiểm tra toàn bộ suite; canary gửi yêu cầu tới http://127.0.0.1:20128/v1/chat/completions và nhận mã HTTP 200 thành công từ 9Router (lỗi lệch đường dẫn OI-PP-01 tại adapter.py đã được khắc phục bởi _ChatCompletionsExecutor cục bộ trong test).
- ledger_recorded: Bị chặn trước khi kiểm tra; không có lời gọi logic thành công nào đưồc ghi sổ.
- record_no_secret: Bị chặn trước khi thu thập bản ghi; khóa bảo mật DPAPI không xuất hiện trong log hoặc bản ghi.
- latency_p95: Bị chặn; không thể tính toán p95 độ trễ do pipeline dừng sớm tại canary.
- budget_guard: Bị chặn do toàn bộ suite dừng tại fixture measurement; chính sách cấu hình hard_stop = True và monthly_limit = 50 USD chưa được nghiệm thu qua measurement.
- warn_80: Bị chặn do toàn bộ suite dừng tại fixture measurement; ngưỡng cảnh báo 80% (40 USD) chưa được nghiệm thu qua measurement.
- quota_wait: NOT_OBSERVED; không gặp lỗi 429 hoặc BUDGET_BLOCKED thật (canary ngắt sớm do AnalysisRejected).
- secret_scan: Bị chặn do fixture measurement dừng sớm; kiểm tra tĩnh cho thấy báo cáo không chứa mẫu secret.

## Giới hạn và GIẢ ĐỊNH

- (a) executor của test _ChatCompletionsExecutor gửi OpenAI chat/completions HTTP thật tới http://127.0.0.1:20128/v1/chat/completions vì NineRouterExecutor của sản phẩm gửi {prompt} tới /v1/v1/chat và nhận 404 ở lượt đo trước (OI-PP-01); phần J-18, RoutedAIInvocation, pipeline và validator của D là mã sản phẩm, chỉ bước HTTP cuối là của test;
- (b) sổ chi phí để trong bộ nhớ vì mật khẩu PostgreSQL ngoài phạm vi D5, ngưỡng ledger tháng >= 40 USD chưa đo (NOT_MEASURED);
- (c) launcher.py:577 đặt route_cost_per_request = 0, test dùng ước tính 0.01 USD nên ledger_recorded chứng minh J-18 ghi sổ khi chi phí dương, không chứng minh cấu hình sản xuất;
- (d) image_safety đi qua RouterVisionRoute thật, không qua J-18; bản ghi chi phí vision do _LedgeredVisionRoute của test ghi (source vision_route_test), không phải bằng chứng ghi sổ của sản phẩm;
- (e) tiền đề snapshot/analysis/angle/script dựng bằng FakeAIAdapter, không tính vào 60 lời gọi;
- (f) trần 60 theo lời gọi logic, chờ quota tối đa 2 lần mỗi lời gọi và 6 lần cả slice;
- (g) vision dùng 10 ảnh seed bg-01..bg-05 và bg-08..bg-12 sinh trong bộ nhớ bằng make_png;
- (h) job_ref mỗi lượt job-m{i} để record_id J-18 không trùng.

## Finding

- F-CP7-4-01: Lệch giao thức OI-PP-01 tại src/controlplane/config/adapter.py:216-217 và src/creative/adapters/real_route_executor.py. Endpoint trong cấu hình production là http://127.0.0.1:20128/v1, adapter nối thêm /v1/chat tạo thành URL http://127.0.0.1:20128/v1/v1/chat trả về HTTP 404 Not Found từ 9Router, đồng thời payload gửi đi chỉ chứa {prompt} thay vì cấu trúc tương thích với model. Hành động đề xuất: Chủ gói ADAPT-D sửa URL endpoint và payload request để chuẩn hóa giao tiếp với 9Router.
- F-CP7-4-02: Tuyến vision không có sổ chi phí (OI-PP-04, chủ gói PP-7). image_safety đi qua RouterVisionRoute độc lập thay vì qua RoutedInvocationService (J-18), dẫn đến các lời gọi kiểm duyệt an toàn ảnh không phát sinh bản ghi chi phí trong cost ledger của sản phẩm.
- F-CP7-4-03: Lệch lược đồ prompt mặc định của Phân hệ D tại src/creative/application/prompts.py so với bộ kiểm tra tính hợp lệ domain tại src/creative/domain/analysis.py (chủ gói CREAT-D). Prompt DEFAULT_PROMPTS['content_analysis'] không quy định chi tiết cấu trúc đối tượng cho evidence_refs (yêu cầu dict ref_type/ref_id/revision_id), uncertainties/contradictions (yêu cầu dict id/text/evidence_refs) và enum event_relation, khiến mô hình Gemini 3.8 Flash thật trả về danh sách chuỗi dẫn tới ngoại lệ AnalysisRejected: ai_output_schema_violation.

## Ghi chú

- Test không in token, khoá hay file ID; chi tiết terminal là ASCII, chữ có dấu chỉ nằm trong báo cáo.
- Báo cáo không chứa mẫu bí mật AIza... hay dòng BEGIN khóa riêng.
