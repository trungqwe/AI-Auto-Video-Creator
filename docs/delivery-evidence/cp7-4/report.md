# CP7-4 — AI qua 9Router thật và chi phí (RG-03)

Ngày đo: 30/10/2026, trên lane lane-cp7-4, bằng interpreter khoá .local-tools/runtime/1ca840a7/venv, dưới quyền thường.

Đo lại sau khi rebase nhánh lên integration head 67b01f25ae729e39774d4e4a6adb9c20c805482c; lượt trước bị Control thu hồi vì pytest không trả mã thoát (exit null).

Lệnh: python -m pytest tests/real/test_cp7_ai_real.py -q -p no:cacheprovider bằng interpreter khoá .local-tools/runtime/1ca840a7/venv. Kết quả: 9 passed, 0 failed, mã thoát 0. Trần chi phí đã dùng: 60 lời gọi logic đã dùng (59/60 hợp lệ, 0 waiting), 60 HTTP hit thật (status 200), 0 lần chờ quota (không gặp 429 hoặc BUDGET_BLOCKED thật), tổng ledger 0.60 USD ghi sổ.

## Kết quả

RG-03.six_roles_valid: PASS
RG-03.router_host_only: PASS
RG-03.ledger_recorded: PASS
RG-03.record_no_secret: PASS
RG-03.latency_p95: PASS
RG-03.budget_guard: PASS
RG-03.warn_80: PASS
RG-03.quota_wait: NOT_OBSERVED
RG-03.secret_scan: PASS

## Chi tiết đo

- six_roles_valid: valid_by_role={"analysis": 10, "angle": 10, "script": 9, "selection": 10, "metadata": 10, "image_safety": 10} waiting=0 total_valid=59/60
- router_host_only: hits=60 hosts=[('127.0.0.1', 20128)] paths=['/v1/chat/completions'] statuses=['200']
- ledger_recorded: j18_records=50 vision_test_records=10 logical_calls=60 total_cost=0.60 USD (bản ghi vision do test ghi, không phải sản phẩm)
- record_no_secret: scanned_records=60 leak_count=0 key_present=False
- latency_p95: p95=33.6s max=39.0s logical_calls=60 retries=0 ledger_total=0.60 USD
- budget_guard: hard_stop=True monthly_limit=50 USD policy_check_blocked=True (pure policy test, not quota_wait)
- warn_80: ratio=0.8 limit=50 USD warn_threshold=40 USD at_40=WARN_80 at_39.99=OK
- quota_wait: không gặp 429 hoặc BUDGET_BLOCKED thật
- secret_scan: match_count=0 secret_version_exists=True

## Giới hạn và GIẢ ĐỊNH

- (a) executor của test _ChatCompletionsExecutor gửi OpenAI chat/completions HTTP thật tới http://127.0.0.1:20128/v1/chat/completions vì NineRouterExecutor của sản phẩm gửi {prompt} tới /v1/v1/chat và nhận 404 ở lượt đo trước (OI-PP-01); phần J-18, RoutedAIInvocation, pipeline và validator của D là mã sản phẩm, chỉ bước HTTP cuối là của test;
- (b) sổ chi phí để trong bộ nhớ vì mật khẩu PostgreSQL ngoài phạm vi D5, ngưỡng ledger tháng >= 40 USD chưa đo (NOT_MEASURED);
- (c) launcher.py:577 đặt route_cost_per_request = 0, test dùng ước tính 0.01 USD nên ledger_recorded chứng minh J-18 ghi sổ khi chi phí dương, không chứng minh cấu hình sản xuất;
- (d) image_safety đi qua RouterVisionRoute thật, không qua J-18; bản ghi chi phí vision do _LedgeredVisionRoute của test ghi (source vision_route_test), không phải bằng chứng ghi sổ của sản phẩm;
- (e) tiền đề snapshot/analysis/angle/script dựng bằng FakeAIAdapter, không tính vào 60 lời gọi;
- (f) trần 60 theo lời gọi logic, chờ quota tối đa 2 lần mỗi lời gọi và 6 lần cả slice;
- (g) vision dùng 10 ảnh seed bg-01..bg-05 và bg-08..bg-12 sinh trong bộ nhớ bằng make_png;
- (h) job_ref mỗi lượt job-m{i} để record_id J-18 không trùng.
- (i) test nối thêm quy tắc lược đồ (_SCHEMA_RULES) vào cuối DEFAULT_PROMPTS vì prompt mặc định của D không nêu lược đồ evidence_refs/event_relation (F-CP7-4-03); validator của D không bị nới; lần đo này không chứng minh DEFAULT_PROMPTS nguyên bản đạt validator.

## Finding

- F-CP7-4-01: Lệch giao thức OI-PP-01 tại src/controlplane/config/adapter.py:216-217 và src/creative/adapters/real_route_executor.py. Endpoint trong cấu hình production là http://127.0.0.1:20128/v1, adapter nối thêm /v1/chat tạo thành URL http://127.0.0.1:20128/v1/v1/chat trả về HTTP 404 Not Found từ 9Router, đồng thời payload gửi đi chỉ chứa {prompt} thay vì cấu trúc tương thích với model. Hành động đề xuất: Chủ gói ADAPT-D sửa URL endpoint và payload request để chuẩn hóa giao tiếp với 9Router.
- F-CP7-4-02: Tuyến vision không có sổ chi phí (OI-PP-04, chủ gói PP-7). image_safety đi qua RouterVisionRoute độc lập thay vì qua RoutedInvocationService (J-18), dẫn đến các lời gọi kiểm duyệt an toàn ảnh không phát sinh bản ghi chi phí trong cost ledger của sản phẩm.
- F-CP7-4-03: Lệch lược đồ prompt mặc định của Phân hệ D tại src/creative/application/prompts.py so với bộ kiểm tra tính hợp lệ domain tại src/creative/domain/analysis.py (chủ gói CREAT-D). Prompt DEFAULT_PROMPTS['content_analysis'] không quy định chi tiết cấu trúc đối tượng cho evidence_refs (yêu cầu dict ref_type/ref_id/revision_id), uncertainties/contradictions (yêu cầu dict id/text/evidence_refs) và enum event_relation, khiến mô hình Gemini 3.8 Flash thật trả về danh sách chuỗi dẫn tới ngoại lệ AnalysisRejected: ai_output_schema_violation. Chủ gói CREAT-D cần bổ sung lược đồ vào DEFAULT_PROMPTS.

## Ghi chú

- Test không in token, khóa hay file ID; chi tiết terminal là ASCII, chữ có dấu chỉ nằm trong báo cáo.
- Báo cáo không chứa mẫu bí mật.
