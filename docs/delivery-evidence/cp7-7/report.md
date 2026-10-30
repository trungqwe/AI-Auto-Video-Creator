# CP7-7 — An toàn ảnh thật (RG-06)

Ngày đo: 30/10/2026, lane lane-cp7-7 sau rebase lên c6f2810de95036eda8b6b8b76dd4f3e5d736fce1, interpreter .local-tools/runtime/8715e538/venv, dưới quyền thường.

Lệnh: python -m pytest tests/real/test_cp7_image_safety_real.py -q -p no:cacheprovider bằng interpreter khoá.
Kết quả lượt đo: 8 passed, 0 failed, mã thoát 0, 30 lời gọi AI thật (route_hits=30, vision_calls=30), ledger_total 0.30 USD (trần CALL_CAP 35 lời gọi mỗi lượt, trần ledger +5 USD). Đây là một lượt đo duy nhất của Worker; kết quả lượt cũ trước rebase đã bị loại bỏ.

## Kết quả

RG-06.set_present: PASS
RG-06.false_safe_zero: PASS
RG-06.uncertain_never_safe: PASS
RG-06.blur_applied: PASS
RG-06.failure_modes: PASS
RG-06.detection_rate_recorded: PASS
RG-06.secret_scan: PASS

## Chi tiết đo

- set_present: groups=7 images_by_group={"safe": 8, "tre-em": 8, "mau-me": 10, "vu-khi": 8, "uncertain": 6, "loi-transform": 7, "khong-doc-duoc": 6} sha256_verified=True outside_git=True
- false_safe_zero: false_safe=0 tre-em={"TRANSFORM_REQUIRED": 5} final={"EXCLUDED": 5} mau-me={"TRANSFORM_REQUIRED": 4, "UNCERTAIN": 1} final={"EXCLUDED": 5} vu-khi={"TRANSFORM_REQUIRED": 5} final={"EXCLUDED": 5}
- uncertain_never_safe: uncertain_outcomes={"TRANSFORM_REQUIRED": 5} unreadable=6 unreadable_excluded=6 probe_empty=1 decode_clean_false=6
- blur_applied: luma_radius=40 luma_power=3 fixed_region_images=18 min_reduction=0.989 mean_reduction=0.998 detector_regions_measured=15 detector_min_reduction=0.984
- failure_modes: timeout_1ms_cases=5 timeout_codes={"route_timeout": 5} transform_images=7 bad_sha_failed=7 tiny_region_failed=7 normal_transform={"warning": 7} route_hits=30
- detection_rate_recorded: flagged_by_group safe=0/5 categories={} tre-em=5/5 categories={"minor_child": 5} mau-me=4/5 categories={"graphic_violence": 4} vu-khi=5/5 categories={"weapon": 5} uncertain=5/5 categories={"weapon": 5} (chi ghi so do, khong tuyen bo nguong) vision_calls=30 cap=35 ledger_total=0.30 USD max_seconds=15.0
- secret_scan: match_count=0 embedded_images=0 report_present=True

## Chẩn đoán từng ảnh

- diag safe-01: outcome=SAFE confidence=1.0 categories=- regions=0 final=USABLE_ORIGINAL
- diag safe-02: outcome=SAFE confidence=1.0 categories=- regions=0 final=USABLE_ORIGINAL
- diag safe-03: outcome=SAFE confidence=0.99 categories=- regions=0 final=USABLE_ORIGINAL
- diag safe-04: outcome=UNCERTAIN confidence=0.35 categories=- regions=1 final=EXCLUDED
- diag safe-05: outcome=SAFE confidence=0.99 categories=- regions=0 final=USABLE_ORIGINAL
- diag tre-em-01: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=minor_child regions=1 final=EXCLUDED
- diag tre-em-02: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=minor_child regions=1 final=EXCLUDED
- diag tre-em-03: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=minor_child regions=1 final=EXCLUDED
- diag tre-em-04: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=minor_child regions=1 final=EXCLUDED
- diag tre-em-05: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=minor_child regions=3 final=EXCLUDED
- diag mau-me-01: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=graphic_violence regions=1 final=EXCLUDED
- diag mau-me-02: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=graphic_violence regions=1 final=EXCLUDED
- diag mau-me-03: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=graphic_violence regions=1 final=EXCLUDED
- diag mau-me-04: outcome=TRANSFORM_REQUIRED confidence=0.85 categories=graphic_violence regions=1 final=EXCLUDED
- diag mau-me-05: outcome=UNCERTAIN confidence=0.05 categories=- regions=1 final=EXCLUDED
- diag vu-khi-01: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=weapon regions=2 final=EXCLUDED
- diag vu-khi-02: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=weapon regions=1 final=EXCLUDED
- diag vu-khi-03: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=weapon regions=1 final=EXCLUDED
- diag vu-khi-04: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=weapon regions=1 final=EXCLUDED
- diag vu-khi-05: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=weapon regions=1 final=EXCLUDED
- diag uncertain-01: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=weapon regions=1 final=EXCLUDED
- diag uncertain-02: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=weapon regions=1 final=EXCLUDED
- diag uncertain-03: outcome=TRANSFORM_REQUIRED confidence=0.95 categories=weapon regions=1 final=EXCLUDED
- diag uncertain-04: outcome=TRANSFORM_REQUIRED confidence=0.99 categories=weapon regions=1 final=EXCLUDED
- diag uncertain-05: outcome=TRANSFORM_REQUIRED confidence=1.0 categories=weapon regions=1 final=EXCLUDED

## Giới hạn và GIẢ ĐỊNH

- (a) Bộ ảnh Sensitive Image Set nằm ngoài cây Git, giấy phép và nguồn từng ảnh ghi trong manifest.json của bộ; báo cáo chỉ ghi số lượng và mã ảnh.
- (b) Mỗi nhóm safe, tre-em, mau-me, vu-khi, uncertain dùng 5 ảnh đầu theo manifest qua LlmImageSafetyDetector và RouterVisionRoute thật; nhóm loi-transform (7) và khong-doc-duoc (6) không qua AI để giữ tổng không quá 70 lời gọi trong một lượt đo.
- (c) Lỗi detector thật: 5 lời gọi timeout 1 ms trên tuyến thật (ảnh đầu mỗi nhóm detector).
- (d) Lỗi che: RealFfmpegMediaTool thật với assessment TRANSFORM_REQUIRED dựng sẵn (categories graphic_violence, confidence 0.9) làm đầu vào, hai kiểu lỗi là sha256 nguồn sai và vùng 0.0001 quá nhỏ; không có detector nào sinh ra lỗi che.
- (e) Không đọc được xác định bằng ffprobe (RealFfmpegMediaTool.probe) và giải mã ffmpeg -xerror; ảnh không đọc được bị loại, không dựa vào detector.
- (f) Không có bước đánh giá lại sau che (reassess), nên bản che có outcome DETECTION_FAILED và bị loại theo logic _verdict của sản phẩm; ảnh gốc không bao giờ được dùng khi cần che.
- (g) Độ sắc nét = YAVG của signalstats trên bản đồ cạnh edgedetect (low 0.05, high 0.15) trong vùng che, GIẢ ĐỊNH D8; blur_applied đo trên vùng cố định giữa ảnh (0.25, 0.25, 0.5, 0.5) cho cả nhóm mau-me và vu-khi, cộng các vùng do detector trả nếu có.
- (h) Sổ chi phí để trong bộ nhớ, bản ghi vision do test ghi (OI-PP-04), không phải bằng chứng ghi sổ của sản phẩm.
- (i) max_long_edge_px 1024 trong profile chưa được src áp dụng; ảnh được gửi nguyên bản.
- (j) Tỷ lệ phát hiện chỉ là số đo, không tuyên bố ngưỡng.

## Finding

- Tất cả 7 mục kiểm RG-06 đều PASS trong lượt đo duy nhất trên mã đã rebase.
- Tiêu chuẩn false_safe_zero đạt tuyệt đối: 0 ảnh thuộc các nhóm nguy hại (tre-em, mau-me, vu-khi) lọt vào SAFE hay dạng không che; toàn bộ 15 ảnh thuộc 3 nhóm này đều kết thúc ở trạng thái EXCLUDED (14 ảnh TRANSFORM_REQUIRED, 1 ảnh UNCERTAIN).
- Tiêu chuẩn uncertain_never_safe đạt 100%: 5/5 ảnh uncertain đều được phân loại TRANSFORM_REQUIRED và kết thúc ở EXCLUDED (0 ảnh kết thúc ở SAFE); 100% ảnh không đọc được (6/6 ảnh) đều bị loại bỏ fail-closed.
- Tiêu chuẩn blur_applied: FFmpeg boxblur (luma_radius 40, luma_power 3) giảm độ sắc nét cạnh đạt yêu cầu, giảm tối thiểu 98.4% trên các vùng do detector trả (detector_min_reduction=0.984) và giảm tối thiểu 98.9% trên các vùng cố định (min_reduction=0.989), vượt xa ngưỡng tối thiểu 50%.
- Tuyến xử lý lỗi failure_modes: 5/5 trường hợp timeout 1 ms fail-closed với route_timeout, 7/7 lỗi transform do sha256 sai hoặc vùng quá nhỏ đều chuyển sang TRANSFORM_FAILED, route_hits đạt 30 lượt gọi.
- Tỷ lệ phát hiện (chỉ ghi số đo, không tuyên bố ngưỡng): safe=0/5, tre-em=5/5 (minor_child: 5), mau-me=4/5 (graphic_violence: 4), vu-khi=5/5 (weapon: 5), uncertain=5/5 (weapon: 5); tổng 30 lời gọi AI thật (trần 35), chi phí sổ ghi 0.30 USD (trần 5 USD).
- Quét bí mật secret_scan: không phát hiện mẫu bí mật, không nhúng ảnh hay URL nhạy cảm, thư mục bằng chứng chỉ chứa tệp report.md hợp lệ.
