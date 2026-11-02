# Báo cáo IMGGEN-ROUTE

## Nhóm lỗi

Mã gói: `IMGGEN-ROUTE`. Nhóm lỗi: `OI-CP7-11-Q2` (theo spec của task: thiếu đường gọi chat có system prompt cho vai trò minh hoạ và luật chú thích bằng mã để IMGGEN-PIPE ghép). Định nghĩa gốc của Q2 không nằm trong repo; nội dung trên là `GIẢ ĐỊNH` theo spec của task.

## Tệp đã sửa

| Tệp | Mô tả |
| --- | --- |
| `src/controlplane/infrastructure/production_ports/vision_route.py` | Thêm `MAX_CHAT_IMAGES = 4` (có trong `__all__`), import `Sequence`, `_chat_image_parts` và `RouterVisionRoute.invoke_chat` đặt ngay sau `invoke_vision`. |
| `tests/integration/prod_ports/test_pp_7_vision_route.py` | Thêm các test `test_chat_*` vào cuối tệp; không đổi test cũ. |
| `src/creative/domain/illustration.py` (mới) | Mô-đun thuần: hằng, `StyleCard`, `ShotRequest`, `IllustrationPlan`, `CaptionProblem`, `IllustrationPlanError`, `parse_plan`, `caption_message`, `check_caption`, `explain`. |
| `tests/unit/creative/test_imggen_illustration.py` (mới) | Test luật minh hoạ thuần, docstring `coveredIds: OI-CP7-11-Q1`, không dùng monkeypatch. |
| `docs/delivery-evidence/imggen-route/report.md` (mới) | Báo cáo này. |

## Lệnh đã chạy

| Lệnh | Exit code | Dòng tổng kết nguyên văn của pytest |
| --- | --- | --- |
| Bước 5 (RED PP-7): `python -m pytest tests/integration/prod_ports/test_pp_7_vision_route.py -q -p no:cacheprovider` (chưa đụng `vision_route.py`) | 1 | `84 failed, 87 passed in 81.75s (0:01:21)` |
| Bước 11 (RED illustration): `python -m pytest tests/unit/creative/test_imggen_illustration.py -q -p no:cacheprovider` | 2 | `1 error in 0.21s` (lỗi thiếu mô-đun: `ModuleNotFoundError: No module named 'creative.domain.illustration'`, ngắt ở bước thu thập, không test nào đạt) |
| Bước 17 (GREEN PP-7): cùng lệnh bước 5 | 0 | `171 passed in 83.05s (0:01:23)` |
| Bước 23 (GREEN illustration): cùng lệnh bước 11 | 0 | `133 passed in 0.14s` |
| Bước 24: `python -m pytest tests/unit/creative/test_imggen_illustration.py tests/integration/prod_ports/test_pp_7_vision_route.py -q -p no:cacheprovider` | 0 | `304 passed in 84.26s (0:01:24)` |
| Bước 25: `python -m pytest tests/unit/creative/test_d01_package_layout.py tests/integration/prod_ports/test_pp_8_assembly.py -q -p no:cacheprovider` | 0 | `36 passed, 70 subtests passed in 21.07s` |
| Bước 26: `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7780 passed, 1 warning, 2561 subtests passed in 28.71s` |
| Bước 27: probe băm `invoke_vision` và chữ ký `invoke_chat` | 0 | không áp dụng |
| Bước 28: probe mô-đun `illustration.py` | 0 | không áp dụng |
| Bước 29: probe hai tệp test | 0 | không áp dụng |
| Bước 30: probe nguồn PP-7 | 0 | không áp dụng |
| Bước 31: probe bố cục gói và import không tiền tố `src.` | 0 | không áp dụng |
| Bước 32: `git diff --check` (trước báo cáo) | 0 | không áp dụng |
| Bước 34: probe báo cáo (có `IMGGEN-ROUTE` và `OI-CP7-11-Q2`) | 0 | không áp dụng |
| Bước 35: `git diff --check` (lần cuối, sau báo cáo) | 0 | không áp dụng |

## Số ca test mới

- `test_pp_7_vision_route.py`: 84 ca `test_chat_*` (đã tính ca tham số) hỏng với mã cũ; 87 test cũ vẫn đạt. Kết quả RED chỉ ghi dòng tổng kết `84 failed, 87 passed`; nguyên nhân kỳ vọng là mã cũ thiếu `invoke_chat` và `MAX_CHAT_IMAGES` (lỗi thiếu tính năng, không phải lỗi oracle). Sau khi sửa: 171 passed (87 cũ + 84 mới).
- `test_imggen_illustration.py`: với mã cũ không có mô-đun (`ModuleNotFoundError`, lỗi thu thập); sau khi sửa: 133 passed.

## invoke_chat

- Chữ ký: `invoke_chat(self, ai_role, system, text, images=(), *, timeout) -> str`, đặt ngay sau `invoke_vision`.
- Thứ tự kiểm trước mạng và trước credentials: `ai_role` không thuộc `model_refs` thì `VisionRouteError('unknown_role')`; rồi `system`, `text` (chuỗi không rỗng); rồi `images` (Sequence, không phải str, bytes, Mapping; tối đa `MAX_CHAT_IMAGES = 4` cặp `(image_base64, media_type)`, mỗi cặp qua cùng regex như `invoke_vision`); rồi `timeout` (số hữu hạn dương, không bool). Sai thì `ValueError`.
- Body: message `system` rồi message `user`; không có ảnh thì `content` là text, có ảnh thì text trước rồi mỗi ảnh là phần `image_url` dạng data URI.
- Dùng chung URL `chat/completions`, `credentials.acquire(CREDENTIAL_METHOD, account_ref)`, `_post`, `_extract_content` và mã lỗi như `invoke_vision`; khoá không lọt vào body, log hay ngoại lệ (có test canary).

## Luật caption

- Độ dài: tối thiểu 80 từ (`MIN_CAPTION_WORDS`), tối đa 350 từ (`MAX_CAPTION_WORDS`).
- Từ cấm `BANNED_WORDS` (cả dạng thêm s, es, ed, ing); `texture`, `context` không bị gắn cờ nhờ ranh giới từ.
- Nháy kép: cả `"`, `“`, `”`, `„`, `«`, `»`.
- Ngôn ngữ: chữ cái không ASCII quá 2% hoặc từ chức năng dưới 20% thì `not_english`.
- Tên thực thể: khớp đúng chuỗi bên gọi đưa vào; tên tới 3 ký tự phân biệt hoa thường.
- Thứ tự vấn đề: độ dài, ngôn ngữ, nháy kép, từ cấm, tên thực thể. Khoá payload của kế hoạch: `style_card` và `requests` (`GIẢ ĐỊNH` theo mặc định D8, IMGGEN-PIPE dùng khi viết lời nhắc kế hoạch).

## invoke_vision không đổi

Probe băm sha256 của đoạn từ `    def invoke_vision(` tới `    def invoke_chat(` khớp `05fbc76dfea4fb3417c30df8e59e80eeba61537cb0f8cecdb6f98b1f2d6f08f6` (bước 27, exit code 0).

## Mục mở

- `OI-CP7-11-Q2` vẫn mở phần ghép (IMGGEN-PIPE): lời nhắc kế hoạch, thử lại một lần có lý do, bỏ ảnh sau lần hai, đọc `system_prompts.json`.
- Kiểm tiếng Anh chỉ theo tỉ lệ ký tự và từ chức năng, không nhận biết ngôn ngữ thật.
- Danh sách từ cấm là danh sách của Control.
- Không thêm thư viện.
