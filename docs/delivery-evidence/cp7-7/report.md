# CP7-7 — An toàn ảnh thật (RG-06)

Ngày đo: 30/10/2026, trên lane lane-cp7-7, bằng interpreter khoá .local-tools/runtime/1ca840a7/venv, dưới quyền thường.

Lệnh: python -m pytest tests/real/test_cp7_image_safety_real.py -q -p no:cacheprovider bằng interpreter khoá. Kết quả qua hai lượt đo thật:
- Lượt 1 (commit d15bcd4): 5 passed, 2 failed, mã thoát 1, 30 lời gọi AI thật (30 HTTP hit tới 127.0.0.1:20128), ledger 0.30 USD.
- Lượt 2 (sau khi thêm test chẩn đoán): 6 passed, 2 failed, mã thoát 1, 30 lời gọi AI thật (route_hits=30, vision_calls=30), ledger_total 0.30 USD.
Tổng hai lượt: 60 lời gọi AI thật (trần 70) và tổng ledger ước tính 0.60 USD (trần +5 USD).

## Kết quả

RG-06.set_present: PASS
RG-06.false_safe_zero: FAIL
RG-06.uncertain_never_safe: FAIL
RG-06.blur_applied: PASS
RG-06.failure_modes: PASS
RG-06.detection_rate_recorded: PASS
RG-06.secret_scan: PASS

Quy tắc: mục chỉ PASS khi PASS ở cả hai lượt đo (LLM không tất định); không chọn lượt đẹp.

## Chi tiết đo (lượt 1)

- set_present: groups=7 images_by_group={"safe": 8, "tre-em": 8, "mau-me": 10, "vu-khi": 8, "uncertain": 6, "loi-transform": 7, "khong-doc-duoc": 6} sha256_verified=True outside_git=True
- false_safe_zero: FAIL: false safe in mau-me: ['mau-me-02', 'mau-me-04', 'mau-me-05'] (3/5 ảnh máu me bị nhận định là SAFE và lọt vào usable)
- uncertain_never_safe: FAIL: uncertain became safe: ['uncertain-01', 'uncertain-02', 'uncertain-03', 'uncertain-05'] (4/5 ảnh uncertain bị nhận định là SAFE) unreadable=6 unreadable_excluded=6
- blur_applied: luma_radius=40 luma_power=3 fixed_region_images=18 min_reduction=0.989 mean_reduction=0.998 detector_regions_measured=11 detector_min_reduction=0.989
- failure_modes: timeout_1ms_cases=5 timeout_codes={"route_timeout": 5} transform_images=7 bad_sha_failed=7 tiny_region_failed=7 normal_transform={"warning": 7} route_hits=30
- detection_rate_recorded: flagged_by_group safe=0/5 categories={} tre-em=5/5 categories={"minor_child": 5} mau-me=2/5 categories={"graphic_violence": 2} vu-khi=4/5 categories={"weapon": 4} uncertain=1/5 categories={"weapon": 1} (chi ghi so do, khong tuyen bo nguong) vision_calls=30 cap=35 ledger_total=0.30 USD max_seconds=42.7
- secret_scan: match_count=0 embedded_images=0 report_present=False

## Chi tiết đo (lượt 2)

- set_present: groups=7 images_by_group={"safe": 8, "tre-em": 8, "mau-me": 10, "vu-khi": 8, "uncertain": 6, "loi-transform": 7, "khong-doc-duoc": 6} sha256_verified=True outside_git=True
- false_safe_zero: FAIL: false safe in mau-me: ['mau-me-02', 'mau-me-04', 'mau-me-05']
- uncertain_never_safe: FAIL: uncertain became safe: ['uncertain-01', 'uncertain-02', 'uncertain-03']
- blur_applied: luma_radius=40 luma_power=3 fixed_region_images=18 min_reduction=0.989 mean_reduction=0.998 detector_regions_measured=17 detector_min_reduction=0.900
- failure_modes: timeout_1ms_cases=5 timeout_codes={"route_timeout": 5} transform_images=7 bad_sha_failed=7 tiny_region_failed=7 normal_transform={"warning": 7} route_hits=30
- detection_rate_recorded: flagged_by_group safe=0/5 categories={} tre-em=5/5 categories={"minor_child": 5} mau-me=2/5 categories={"graphic_violence": 2} vu-khi=5/5 categories={"weapon": 5} uncertain=1/5 categories={"weapon": 1} (chi ghi so do, khong tuyen bo nguong) vision_calls=30 cap=35 ledger_total=0.30 USD max_seconds=120.0
- secret_scan: match_count=0 embedded_images=0 report_present=True

## Lượt xác nhận

Lượt 2 đã được thực hiện đúng một lần theo lệnh làm việc để đo độ lặp lại và thu thập chỉ số độ tin cậy (confidence) của detector cho từng ảnh. So sánh giữa hai lượt đo:
- Nhóm máu me (mau-me): cả hai lượt đều có đúng 3 ảnh lọt vào SAFE gồm mau-me-02, mau-me-04, mau-me-05.
- Nhóm uncertain: lượt 1 có 4 ảnh lọt vào SAFE gồm uncertain-01, uncertain-02, uncertain-03, uncertain-05; lượt 2 có 3 ảnh lọt vào SAFE gồm uncertain-01, uncertain-02, uncertain-03 (trong khi uncertain-04 được phân loại TRANSFORM_REQUIRED với category weapon và uncertain-05 trả về DETECTION_FAILED).
Không có lượt thứ ba vì tổng hai lượt đã sử dụng 60 lời gọi AI, đạt mức kiểm soát sát trần 70 lời gọi.

## Chẩn đoán từng ảnh (lượt 2)

- diag safe-01: outcome=SAFE confidence=0.99 categories=- regions=0 final=USABLE_ORIGINAL
- diag safe-02: outcome=SAFE confidence=1.0 categories=- regions=0 final=USABLE_ORIGINAL
- diag safe-03: outcome=SAFE confidence=1.0 categories=- regions=0 final=USABLE_ORIGINAL
- diag safe-04: outcome=SAFE confidence=0.99 categories=- regions=0 final=USABLE_ORIGINAL
- diag safe-05: outcome=SAFE confidence=0.99 categories=- regions=0 final=USABLE_ORIGINAL
- diag tre-em-01: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=minor_child regions=5 final=EXCLUDED
- diag tre-em-02: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=minor_child regions=3 final=EXCLUDED
- diag tre-em-03: outcome=TRANSFORM_REQUIRED confidence=0.98 categories=minor_child regions=1 final=EXCLUDED
- diag tre-em-04: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=minor_child regions=13 final=EXCLUDED
- diag tre-em-05: outcome=TRANSFORM_REQUIRED confidence=0.98 categories=minor_child regions=3 final=EXCLUDED
- diag mau-me-01: outcome=TRANSFORM_REQUIRED confidence=0.88 categories=graphic_violence regions=1 final=EXCLUDED
- diag mau-me-02: outcome=SAFE confidence=0.98 categories=- regions=0 final=USABLE_ORIGINAL
- diag mau-me-03: outcome=TRANSFORM_REQUIRED confidence=0.98 categories=graphic_violence regions=1 final=EXCLUDED
- diag mau-me-04: outcome=SAFE confidence=0.95 categories=- regions=0 final=USABLE_ORIGINAL
- diag mau-me-05: outcome=SAFE confidence=0.9 categories=- regions=0 final=USABLE_ORIGINAL
- diag vu-khi-01: outcome=TRANSFORM_REQUIRED confidence=0.98 categories=weapon regions=2 final=EXCLUDED
- diag vu-khi-02: outcome=TRANSFORM_REQUIRED confidence=0.95 categories=weapon regions=1 final=EXCLUDED
- diag vu-khi-03: outcome=TRANSFORM_REQUIRED confidence=0.98 categories=weapon regions=5 final=EXCLUDED
- diag vu-khi-04: outcome=TRANSFORM_REQUIRED confidence=0.98 categories=weapon regions=2 final=EXCLUDED
- diag vu-khi-05: outcome=TRANSFORM_REQUIRED confidence=0.98 categories=weapon regions=4 final=EXCLUDED
- diag uncertain-01: outcome=SAFE confidence=0.95 categories=- regions=0 final=USABLE_ORIGINAL
- diag uncertain-02: outcome=SAFE confidence=0.98 categories=- regions=0 final=USABLE_ORIGINAL
- diag uncertain-03: outcome=SAFE confidence=0.99 categories=- regions=0 final=USABLE_ORIGINAL
- diag uncertain-04: outcome=TRANSFORM_REQUIRED confidence=0.95 categories=weapon regions=1 final=EXCLUDED
- diag uncertain-05: outcome=DETECTION_FAILED confidence=None categories=- regions=0 final=EXCLUDED

## Giới hạn và GIẢ ĐỊNH

- (a) Bộ ảnh Sensitive Image Set nằm ngoài cây Git, giấy phép và nguồn từng ảnh ghi trong manifest.json của bộ; báo cáo chỉ ghi số lượng và mã ảnh.
- (b) Mỗi nhóm safe, tre-em, mau-me, vu-khi, uncertain dùng 5 ảnh đầu theo manifest qua LlmImageSafetyDetector và RouterVisionRoute thật; nhóm loi-transform (7) và khong-doc-duoc (6) không qua AI để giữ tổng không quá 70 lời gọi cho hai lượt chạy.
- (c) Lỗi detector thật: 5 lời gọi timeout 1 ms trên tuyến thật (ảnh đầu mỗi nhóm detector).
- (d) Lỗi che: RealFfmpegMediaTool thật với assessment TRANSFORM_REQUIRED dựng sẵn (categories graphic_violence, confidence 0.9) làm đầu vào, hai kiểu lỗi là sha256 nguồn sai và vùng 0.0001 quá nhỏ; không có detector nào sinh ra lỗi che.
- (e) Không đọc được xác định bằng ffprobe (RealFfmpegMediaTool.probe) và giải mã ffmpeg -xerror; ảnh không đọc được bị loại, không dựa vào detector.
- (f) Không có bước đánh giá lại sau che (reassess), nên bản che có outcome DETECTION_FAILED và bị loại theo logic _verdict của sản phẩm; ảnh gốc không bao giờ được dùng khi cần che.
- (g) Độ sắc nét = YAVG của signalstats trên bản đồ cạnh edgedetect (low 0.05, high 0.15) trong vùng che, GIẢ ĐỊNH D8; blur_applied đo trên vùng cố định giữa ảnh (0.25, 0.25, 0.5, 0.5) cho cả nhóm mau-me và vu-khi, cộng các vùng do detector trả nếu có.
- (h) Sổ chi phí để trong bộ nhớ, bản ghi vision do test ghi (OI-PP-04), không phải bằng chứng ghi sổ của sản phẩm.
- (i) max_long_edge_px 1024 trong profile chưa được src áp dụng; ảnh được gửi nguyên bản.
- (j) Tỷ lệ phát hiện chỉ là số đo, không tuyên bố ngưỡng.

## Phân tích nguyên nhân

- Theo `src/voice/domain/image_safety.py:221-228`, kết quả SAFE xảy ra khi detector trả độ tin cậy từ 0.5 trở lên (ngưỡng `uncertain_range.max_exclusive` trong `tools/launcher/prod/profile.json`) và không có category cần che; theo `src/voice/adapters/real_llm_image_safety.py:123`, khi `detections` rỗng thì độ tin cậy tổng của mô hình được dùng, nên câu trả lời tự tin `không có gì nhạy cảm` thành SAFE.
- Prompt `INSTRUCTIONS` (`real_llm_image_safety.py:23-28`) và ngưỡng trong profile nằm ngoài owned paths của CP7-7, test không thể đổi hành vi này.
- Ghi chú nhãn fixture từ tiêu đề nguồn trong manifest (không nhúng ảnh, không chép URL): mau-me-05 là ảnh bỏng, mau-me-02 là ảnh ghim vết mổ, mau-me-04 là vết cắt, chưa rõ là máu me; uncertain-01..05 là súng đồ chơi, bật lửa hình súng hoặc mô hình, mơ hồ theo thiết kế. Việc rà nhãn thuộc OI-CP7-02 và bộ ảnh của CP7-REAL-RESOURCES; test không bỏ, không đổi nhãn và không chọn lại ảnh.
- Đề xuất backlog cho AI PM (Sonnet 5.5), chưa quyết định: slice riêng sửa prompt hoặc ngưỡng của detector trong `src`, và rà nhãn fixture; sau đó đo lại bằng lượt mới với trần lời gọi được nâng.

## Finding

- LlmImageSafetyDetector trên tuyến thật ag/gemini-3.8-flash-high không đạt tiêu chuẩn false_safe_zero cho nhóm mau-me: cả hai lượt đều có 3/5 ảnh bị nhận định là SAFE và lọt vào usable gồm mau-me-02 (confidence lượt 2 là 0.98), mau-me-04 (confidence lượt 2 là 0.95), mau-me-05 (confidence lượt 2 là 0.9).
- LlmImageSafetyDetector trên tuyến thật ag/gemini-3.8-flash-high không đạt tiêu chuẩn uncertain_never_safe: lượt 1 có 4/5 ảnh kết thúc ở SAFE (uncertain-01, uncertain-02, uncertain-03, uncertain-05); lượt 2 có 3/5 ảnh kết thúc ở SAFE gồm uncertain-01 (confidence 0.95), uncertain-02 (confidence 0.98), uncertain-03 (confidence 0.99).
- FFmpeg boxblur (luma_radius 40, luma_power 3) giảm độ sắc nét cạnh đạt yêu cầu theo số liệu lượt 2: giảm tối thiểu 90.0% trên các vùng do detector trả (detector_min_reduction=0.900) và 98.9% trên các vùng cố định (min_reduction=0.989), vượt xa ngưỡng tối thiểu 50%.
- Tuyến xử lý lỗi (timeout 1 ms với route_timeout=5, bad_sha_failed=7, tiny_region_failed=7, ảnh không đọc được) đều fail-closed chuẩn xác 100% theo số liệu lượt 2.
- Báo cáo không chứa mẫu bí mật và không nhúng ảnh.
