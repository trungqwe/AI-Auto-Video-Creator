# ADAPT-E-MEDIA-FIX2: Bộ dò an toàn ảnh chấm điểm từng danh mục theo ngưỡng của hồ sơ

## 1. Phạm vi và tệp đã sửa
Danh sách 6 tệp thuộc owned paths được phép thay đổi:
- `src/voice/adapters/real_llm_image_safety.py`
- `src/voice/adapters/activity_inputs.py`
- `src/controlplane/api/wiring/voice.py`
- `tests/integration/adapt/e_media/test_adapt_e_media_safety_scores.py`
- `tests/integration/adapt/wire/test_adapt_wire_services.py`
- `docs/delivery-evidence/adapt-e-media-fix2/report.md`

Cam kết không sửa bất kỳ tệp nào ngoài danh sách trên:
- Không sửa `src/controlplane/api/wiring/production_profile.py` hay `tools/launcher/prod/profile.json`.
- Không sửa `src/voice/domain/**`, `src/voice/ports/**`, `runtime.lock.json`.
- Không sửa các tệp test ngoài owned paths như `tests/integration/prod_ports/test_pp_7_vision_route.py`, `tests/unit/**`, `tests/integration/prod_wiring/**`.

## 2. Thiết kế và giả định D8
- Định danh phiên bản prompt: `PROMPT_REVISION = 'image-safety-prompt-v2'`. Prompt gồm đúng 12 dòng nguyên văn định nghĩa đầy đủ 5 danh mục an toàn (`minor_child`, `nudity_sexual`, `graphic_violence`, `weapon`, `hate_symbol`), yêu cầu trả về điểm số xác suất cho từng danh mục (`scores`), các phát hiện có toạ độ chuẩn hoá (`detections`), và độ tin cậy khi không có yếu tố nhạy cảm (`confidence`).
- Thuật toán tổng hợp chứng cứ: Với mỗi danh mục $c$, bằng chứng $e_c = \max(\text{scores}[c], \text{confidence lớn nhất của detection thuộc } c)$.
- Xác định tập nghi ngờ $F$:
  - Khi có `uncertain_min`: $F = \{c \in \text{categories} : e_c \ge \text{uncertain\_min}\}$.
  - Khi `uncertain_min is None`: $F = \{c \in \text{categories} : e_c > 0.0\}$.
- Xác định kết quả phát hiện:
  - Nếu $F \ne \emptyset$: `ImageDetection(status=COMPLETED, categories=sorted(F), confidence=min(e_c \text{ với } c \in F))`, các vùng `regions` được lọc chỉ giữ lại những vùng có category thuộc $F$.
  - Nếu $F = \emptyset$: `ImageDetection(status=COMPLETED, categories=(), confidence=overall_confidence)`, `regions = ()`.
- Quy tắc tương thích ngược: Nếu phản hồi từ mô hình không có khoá `'scores'`, parser áp dụng logic cũ từ danh sách `detections` và `confidence` tổng; thuộc tính `detector.scores` được đặt về `None`.
- Xử lý lỗi theo nguyên tắc fail-closed:
  - Nếu `scores` thiếu khoá danh mục trong `categories`: sinh mã lỗi `'incomplete_scores'`.
  - Nếu `scores` chứa khoá lạ: sinh mã lỗi `'unknown_category'`.
  - Nếu `scores` không phải `dict`, hoặc giá trị không phải số thực hữu hạn trong đoạn $[0.0, 1.0]$, hoặc là kiểu `bool`: sinh mã lỗi `'wrong_type'`.
  - Mọi lỗi phân tích đều chuyển trạng thái sang `DetectionStatus.FAILED` (`DETECTION_FAILED`), xoá `scores = None` và `regions = ()`.
- Cấu hình ngưỡng từ hồ sơ production: Cả hai điểm khởi tạo `LlmImageSafetyDetector` ở `src/voice/adapters/activity_inputs.py` (trong `_assess`) và `src/controlplane/api/wiring/voice.py` (trong `detector_factory`) đều truyền tham số `uncertain_min` được đọc từ `build_image_safety_rules(profile.parameters).uncertain_min` (giá trị 0.3) theo đúng đặc tả ADAPT mục 7.3 (docs/implementation/adapt/plan.md:193).
- Phân hệ E chạy phía desktop theo R18 (docs/07-data-flow.md:40); bản sửa không đổi điều đó.

## 3. Bảng lệnh đã chạy
Dưới đây là kết quả thực tế trên worktree (mã thoát và kết quả kiểm thử):

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 19 | `python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_safety_scores.py tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q -p no:cacheprovider` | 0 | 98 passed in 0.67s (57 test mới đạt, 41 test công cụ E cũ đạt) |
| Bước 20 | `python -m pytest tests/integration/prod_ports/test_pp_7_vision_route.py tests/unit/voice/test_e05_image_safety.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 153 passed, 89 subtests passed in 37.88s (giao tiếp cổng thị giác, kiểm tra bố cục gói cấm import mạng/subprocess đạt) |
| Bước 21 | `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` | 0 | 113 passed in 16.22s (gồm kiểm tra detector_factory production mang uncertain_min = 0.3) |
| Bước 22 | `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider` | 0 | 22 passed in 16.31s (chuỗi nhập E và launcher tương thích hoàn toàn) |
| Bước 23 | `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_media_tool.py', 'real_llm_image_safety.py']); assert 'boxblur' in t and 'runtime.lock.json' in t and 'shell=True' not in t and 'from src.' not in t, 'adapter E media'"` | 0 | Đạt assertions kiểm tra adapter E (boxblur, runtime.lock.json, không shell=True, không 'from src.') |
| Bước 24 | `python -c "import pathlib; t = pathlib.Path('src/voice/adapters/real_llm_image_safety.py').read_text(encoding='utf-8'); assert 'Empty detections when nothing sensitive' not in t, 'old prompt'; assert all(k in t for k in ['image-safety-prompt-v2', 'uncertain_min', 'incomplete_scores', 'gun-shaped lighters', 'surgical incisions', 'counts as 0']), 'v2'; assert all('uncertain_min' in pathlib.Path(f).read_text(encoding='utf-8') for f in ['src/voice/adapters/activity_inputs.py', 'src/controlplane/api/wiring/voice.py']), 'floor wired'"` | 0 | Đạt assertions kiểm tra prompt v2 và nối sàn uncertain_min tại hai nơi khởi tạo |
| Bước 25 | `git diff --check` | 0 | Sạch, không có lỗi khoảng trắng hay dòng thừa |

## 4. RED/GREEN
- Kết quả chạy RED ở Bước 5: Trước khi sửa đổi mã nguồn, bộ test mới được chạy trên mã cũ với lệnh `python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_safety_scores.py -q -p no:cacheprovider`, trả về exit code 1 với kết quả: `56 failed, 1 passed in 0.66s`.
- Báo cáo trung thực: Phần lớn các lỗi thất bại trong lượt chạy này bắt nguồn từ việc thiếu thuộc tính hoặc đối số (`AttributeError: module 'voice.adapters.real_llm_image_safety' has no attribute 'PROMPT_REVISION'`, `TypeError: LlmImageSafetyDetector.__init__() got an unexpected keyword argument 'uncertain_min'`, `TypeError: parse_vision_output() got an unexpected keyword argument 'uncertain_min'`, `AttributeError: 'LlmImageSafetyDetector' object has no attribute 'uncertain_min'`). Theo quy chuẩn AGENTS.md, các lỗi về chữ ký và thiếu symbol không được coi là RED hợp lệ theo oracle hành vi; tuy nhiên, các ca kiểm thử hành vi (như `stitched-wound-score-only` với điểm graphic_violence 0.8 nhưng detections rỗng trước đây bị ra SAFE thay vì TRANSFORM_REQUIRED, hay `band-is-uncertain` với weapon 0.4 trước đây bị ra SAFE thay vì UNCERTAIN) đã được định nghĩa chuẩn xác và xác nhận thất bại trước khi bổ sung bộ xử lý scores.
- Test wiring bổ sung tại Bước 18 (`test_voice_production_uses_real_adapters` kiểm tra sàn `uncertain_min == 0.3`) không có lượt chạy RED riêng trước đó.

## 5. Việc còn lại (backlog, không làm trong slice này)
- Đo lại 10 ảnh kiểm thử RG-06 trên tuyến AI thị giác thật `ag/gemini-3.8-flash-high` thuộc gói nghiệm thu CP7; slice này không đưa ra tuyên bố đo kiểm trên môi trường thật.
- Tuyệt đối không sử dụng kết quả mock/fake để tự ý tuyên bố PASS cho các cổng nghiệm thu bên ngoài (external gates).
