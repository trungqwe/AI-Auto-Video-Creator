# HOOK-QC — Báo cáo bằng chứng

Mã gói: **HOOK-QC**
Mã yêu cầu chức năng: **FR-HOOK-008**
Mốc nghiệm thu: **CP7**

## 1. Nhóm lỗi

Mã nhóm lỗi: **OI-CP7-11-Q4**

Mô tả: Đo được 100/100 video qua cổng VISUAL_HOOK_PRESENT với gradient giữ chỗ vh-01..05 vì check_visual_hook_present (src/render/domain/content_gates.py) chỉ đo khoảng thời gian và SSIM với chính tài nguyên hook, còn ProductionRenderSources._hook_source (src/controlplane/api/wiring/render.py) chỉ đọc media_sha256 của bản hook mới nhất. Gói này là lớp chặn thứ hai ở render và QC sau PW-D3-FIX4.

## 2. Các tệp đã sửa

Bốn tệp đã được cập nhật nguyên văn từ bản tham chiếu Control tại D:/AIAVC_IMGPROTO/ref/hook-qc/ với mã băm sha256 hoàn toàn trùng khớp:

1. src/controlplane/api/wiring/render.py:
   - Thêm hằng _HOOK_PLACEHOLDER_KEY = 'recipe_template' và HOOK_PLACEHOLDER_REASON = 'hook_placeholder' cạnh _HOOK_MEDIA_SHA_KEY.
   - Thêm nhánh kiểm tra trong ProductionRenderSources._hook_source: nếu cặp khóa trong technical_metadata chứa recipe_template thì tung ngoại lệ raise _hook_not_ready(hook_id, HOOK_PLACEHOLDER_REASON) (tức ActivityInputError mã INPUT_NOT_READY với chi tiết hook_placeholder:<hook_id>), không tra cứu version.
   - Chặn thumbnail lấy từ hook qua _thumbnail_source gọi _hook_source.
   - Hook không chứa recipe_template giữ nguyên toàn bộ hành vi cũ.

2. src/render/domain/content_gates.py:
   - Thêm hằng VISUAL_HOOK_PLACEHOLDER = 'visual_hook_placeholder'.
   - Trong check_visual_hook_present: ngay sau dòng gate = GateName.VISUAL_HOOK_PRESENT, kiểm tra sớm if _placement(package).get(VISUAL_HOOK_PLACEHOLDER) is True: thì trả về _failed(gate, VISUAL_HOOK_PLACEHOLDER) trước khi kiểm tra khoảng thời gian và SSIM.
   - Giá trị khác True (False, chuỗi, 1, thiếu khóa) giữ nguyên hành vi cũ; không thêm import ngoài danh sách cho phép.

3. tests/unit/render/test_f14_content_gates.py:
   - Thêm hàm kiểm thử VisualHookTests.test_placeholder_hook_fails_before_similarity kiểm tra gói mang cờ visual_hook_placeholder = True trả về FAILED với lý do visual_hook_placeholder cả khi có evidence lẫn evidence None, và cờ False thì PASSED.

4. tests/integration/prod_wiring/test_hook_qc_placeholder.py:
   - Tệp kiểm thử tích hợp mới bao phủ FR-HOOK-008 (không cần PostgreSQL, dùng kết nối giả lập):
     - test_render_refuses_a_placeholder_hook_with_input_not_ready: hook có recipe_template (vh-01, ah-01) trả về lỗi hook_placeholder:<id> và không chạy truy vấn version.
     - test_thumbnail_from_a_placeholder_hook_frame_is_refused: thumbnail thumb:vh-02 từ hook giữ chỗ bị từ chối với hook_placeholder:vh-02.
     - test_licensed_hook_goes_on_to_the_verified_version_lookup: hook có hook_license tiếp tục đi tới bước tra cứu version (hook_version_not_verified:<id>).
     - test_visual_hook_gate_fails_a_package_marked_as_placeholder: cổng VISUAL_HOOK_PRESENT trả về FAILED với lý do visual_hook_placeholder khi cờ là True.

## 3. Hành vi

- Render từ chối hook có recipe_template bằng ActivityInputError mã INPUT_NOT_READY chi tiết hook_placeholder:<hook_id> (áp dụng cho cả thumbnail thumb:<hook_id>).
- Hook có hook_license tiếp tục đi tới bước tra cứu hook_version_not_verified:<id>.
- Cổng VISUAL_HOOK_PRESENT trả về FAILED với lý do visual_hook_placeholder khi hook_placement['visual_hook_placeholder'] is True.
- Các giá trị khác True giữ nguyên hành vi kiểm tra thông thường.

## 4. Kết quả kiểm thử thực tế

| Bước | Lệnh kiểm thử | Mã thoát | Kết quả / Dòng tổng kết nguyên văn của pytest |
| --- | --- | --- | --- |
| 3 (RED) | python -m pytest tests/integration/prod_wiring/test_hook_qc_placeholder.py tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider | 1 | 5 failed, 52 passed, 67 subtests passed in 4.14s |
| 6 (GREEN) | python -m pytest tests/integration/prod_wiring/test_hook_qc_placeholder.py tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider | 0 | 57 passed, 67 subtests passed in 1.50s |
| 7 | Probe sha256 4 tệp tham chiếu | 0 | Khớp 100% 4 tệp sha256 tham chiếu |
| 8 | git diff --check | 0 | Không có lỗi khoảng trắng |
| 9 | python -m pytest tests/unit/render -q -p no:cacheprovider | 0 | 1373 passed, 487 subtests passed in 12.60s |
| 10 | python -m pytest tests/integration/render/test_f10_fix6_frame_placement.py tests/integration/render/test_f19_inspect_output_pipeline.py tests/integration/prod_wiring/test_d10_fix1_hook_lead.py tests/integration/prod_wiring/test_pw_d3_fix3_illustration.py tests/integration/prod_wiring/test_pw_w2_fix6_qc_probe.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider | 0 | 144 passed, 4 warnings in 51.53s |
| 11 | python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/prod_wiring/test_pw_w2_fix8_render_image_safety.py -q -p no:cacheprovider | 0 | 72 passed in 82.79s (0:01:22) (PostgreSQL cục bộ đang hoạt động trong container) |
| 12 | Probe sha256 test mới | 0 | Khớp mã sha256 tham chiếu |
| 13 | Probe cấu trúc cổng và hằng của gói | 0 | Kiểm tra hằng và logic phân nhánh đạt |
| 14 | Probe tên các hàm test của gói | 0 | Có đủ 4 hàm test và coveredIds |
| 15 | Probe CRLF trong 4 tệp | 0 | Không có byte CR (13) |
| 16 | Probe waiting_port | 0 | Bảo toàn thay đổi của gói chủ render.py khác |
| 17 | Probe build_qc_probe | 0 | Bảo toàn thay đổi qc probe |
| 18 | Probe voice_duration | 0 | Bảo toàn render plan |
| 19 | Probe AudioMixGate | 0 | Bảo toàn AudioMixGate |
| 20 | Probe settings overlay/subtitle | 0 | Bảo toàn settings overlay/subtitle |
| 21 | Probe render_image_sources | 0 | Bảo toàn ranh giới render_image_sources |
| 22 | Probe audio_bed_cue | 0 | Bảo toàn audio_bed_cue wiring |
| 23 | Probe require_illustration | 0 | Bảo toàn require_illustration |
| 24 | Probe illustration_windows | 0 | Bảo toàn illustration_windows |
| 25 | Probe pyproject package-dir và import src. | 0 | Không có import prefix src. và pyproject đầy đủ |

## 5. Giới hạn

- Wiring production chặn ngay ở _hook_source nên hệ thống không bao giờ dựng gói có cờ visual_hook_placeholder; cổng QC là hợp đồng phòng thủ cho mọi bộ dựng gói khác.
- Hook âm thanh giữ chỗ bị chặn ở render; AUDIO_HOOK_PRESENT không thêm cờ.
- Gói không thể chạy thành công nếu kho hook chỉ toàn hook giữ chỗ: môi trường sản xuất cần HOOK-HARVEST thu thập hook thật trước. Do đó, nhóm lỗi OI-CP7-11-Q4 hiện tại chỉ bổ sung lớp chặn render và QC, chưa tuyên bố đóng bằng lô dữ liệu sản xuất thật.
