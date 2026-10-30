# CP7-7 — An toàn ảnh thật (RG-06)

Ngày đo: 30/10/2026, trên lane lane-cp7-7, bằng interpreter khoá .local-tools/runtime/1ca840a7/venv, dưới quyền thường.

Lệnh: python -m pytest tests/real/test_cp7_image_safety_real.py -q -p no:cacheprovider bằng interpreter khoá. Kết quả lượt đo: 5 passed, 2 failed, mã thoát 1. Trần chi phí đã dùng: 30 lời gọi AI thật (trần 35 mỗi lượt, tối đa 2 lượt nên không quá 70), 30 HTTP hit tới 127.0.0.1:20128, tổng ledger 0.30 USD (ước tính 0.01 USD mỗi lời gọi).

## Kết quả

RG-06.set_present: PASS
RG-06.false_safe_zero: FAIL
RG-06.uncertain_never_safe: FAIL
RG-06.blur_applied: PASS
RG-06.failure_modes: PASS
RG-06.detection_rate_recorded: PASS
RG-06.secret_scan: PASS

## Chi tiết đo

- set_present: groups=7 images_by_group={"safe": 8, "tre-em": 8, "mau-me": 10, "vu-khi": 8, "uncertain": 6, "loi-transform": 7, "khong-doc-duoc": 6} sha256_verified=True outside_git=True
- false_safe_zero: FAIL: false safe in mau-me: ['mau-me-02', 'mau-me-04', 'mau-me-05'] (3/5 ảnh máu me bị nhận định là SAFE và lọt vào usable)
- uncertain_never_safe: FAIL: uncertain became safe: ['uncertain-01', 'uncertain-02', 'uncertain-03', 'uncertain-05'] (4/5 ảnh uncertain bị nhận định là SAFE) unreadable=6 unreadable_excluded=6
- blur_applied: luma_radius=40 luma_power=3 fixed_region_images=18 min_reduction=0.989 mean_reduction=0.998 detector_regions_measured=11 detector_min_reduction=0.989
- failure_modes: timeout_1ms_cases=5 timeout_codes={"route_timeout": 5} transform_images=7 bad_sha_failed=7 tiny_region_failed=7 normal_transform={"warning": 7} route_hits=30
- detection_rate_recorded: flagged_by_group safe=0/5 categories={} tre-em=5/5 categories={"minor_child": 5} mau-me=2/5 categories={"graphic_violence": 2} vu-khi=4/5 categories={"weapon": 4} uncertain=1/5 categories={"weapon": 1} (chi ghi so do, khong tuyen bo nguong) vision_calls=30 cap=35 ledger_total=0.30 USD max_seconds=42.7
- secret_scan: match_count=0 embedded_images=0 report_present=False

## Lượt xác nhận

Không chạy lượt xác nhận vì lượt thứ nhất đã đỏ: RG-06.false_safe_zero (mau-me: 3/5 ảnh lọt vào safe gồm mau-me-02, mau-me-04, mau-me-05) và RG-06.uncertain_never_safe (uncertain: 4/5 ảnh thành safe gồm uncertain-01, uncertain-02, uncertain-03, uncertain-05).

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

## Finding

- LlmImageSafetyDetector trên tuyến thật ag/gemini-3.8-flash-high không đạt tiêu chuẩn false_safe_zero cho nhóm mau-me: 3/5 ảnh bị nhận định là safe và không được che (mau-me-02, mau-me-04, mau-me-05).
- LlmImageSafetyDetector trên tuyến thật ag/gemini-3.8-flash-high không đạt tiêu chuẩn uncertain_never_safe: 4/5 ảnh thuộc nhóm uncertain kết thúc ở SAFE (uncertain-01, uncertain-02, uncertain-03, uncertain-05).
- FFmpeg boxblur (luma_radius 40, luma_power 3) hoạt động rất tốt, giảm độ sắc nét cạnh >= 98.9% (vượt xa ngưỡng yêu cầu >= 50%).
- Tuyến xử lý lỗi (timeout 1 ms, sha256 sai, vùng che quá nhỏ, ảnh không đọc được) hoạt động chuẩn xác 100% fail-closed không bao giờ để lọt ảnh hỏng thành safe.

## Ghi chú

- Báo cáo không chứa mẫu bí mật và không nhúng ảnh.
