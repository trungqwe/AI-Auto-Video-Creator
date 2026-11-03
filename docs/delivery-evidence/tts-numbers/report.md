# Báo cáo TTS-NUMBERS

## Nhóm lỗi

- Mã nhóm lỗi: `OI-CP7-11-Q3`.
- Lỗi đo được của lượt đo đêm CP7-11 ngày 02/11/2026: kịch bản viết "72,000" thì video tiếng Anh đọc "seventy-two, zero zero zero".
- Nguyên nhân gốc: `src/voice/adapters/real_kokoro_tts.py:248` gửi nguyên `script_text.text` cho `model.create`; `kokoro-onnx 0.4.9` (`tokenizer.py:57-76`) chỉ `strip()` rồi gọi `phonemizer.phonemize(..., preserve_punctuation=True)`, và `phonemizer/punctuation.py:25,113-144` cắt văn bản tại mọi dấu `, . : ; ! ?` trước khi `espeak-ng` đọc: `72` và `000` (`espeak` đọc `000` là `zero zero zero`).
- Cùng lớp lỗi (g2p `espeak` của runtime khóa): 1.5 bị đọc thành "one. five", .99 thành "dollar four. ninety-nine", €20m thành "euros twenty M", 2020-2024 đọc dash, 3km thành "K M", 1990s thành "nineteen hundred ninety z".

## Tệp đã sửa

1. `src/voice/domain/spoken_numbers.py`: tệp mới, chỉ dùng thư viện chuẩn (`__future__` và `re`), định nghĩa hằng số `SPOKEN_NUMBERS_REVISION = 'spoken-en-1'` cùng các hàm `cardinal_words`, `ordinal_words`, `year_words`, `number_words` và `speakable_english(text)` để chuẩn hoá các dạng số đứng tự do sang từ tiếng Anh tương ứng.
2. `src/voice/adapters/real_kokoro_tts.py`: chỉ chuyển đổi văn bản đưa vào `model.create`: `spoken = speakable_english(script_text.text)` khi `config.language` bắt đầu bằng `en` (casefold), ngược lại giữ nguyên; `ScriptText`, `usage_metrics['characters'] = len(script_text.text)`, aligner và phụ đề tiếp tục giữ nguyên chữ số của kịch bản để đảm bảo FR-REN-008 và QR-OUT-008; chuỗi revision bổ sung `;numbers=spoken-en-1` ngay trước `;sentence_joins=model-tail`; cập nhật docstring module với ghi chú TTS-NUMBERS.
3. `tests/integration/adapt/e/test_adapt_e_tts_numbers.py`: test mới gồm 35 ca kiểm thử, gắn thẻ `coveredIds: CT-TTS-001`, không sử dụng `monkeypatch` hay `mock`, kiểm tra g2p espeak thật của `kokoro_onnx.tokenizer` và aligner với Whisper giả khi đối chiếu lời đọc với chữ số kịch bản.
4. `docs/delivery-evidence/tts-numbers/report.md`: báo cáo nghiệm thu này.

Ba tệp mã nguồn và test (`src/voice/domain/spoken_numbers.py`, `src/voice/adapters/real_kokoro_tts.py`, `tests/integration/adapt/e/test_adapt_e_tts_numbers.py`) được chép nguyên văn từ bản tham chiếu Control tại `D:/AIAVC_IMGPROTO/ref/tts-numbers/`, có sha256 (sau chuẩn hoá xuống dòng LF) trùng khớp hoàn toàn với `SHA256SUMS` của Control.

## Lệnh đã chạy

Tất cả các lệnh pytest được thực thi với biến môi trường:
`='C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\TTS-NUMBERS-implement-r0-ac1b5c0961'`
bằng Python interpreter khóa:
`C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`

| Bước | Lệnh | Mã thoát | Dòng tổng kết pytest / Kết quả |
| --- | --- | --- | --- |
| Bước 1 | Probe kiểm hash điều kiện đầu của `real_kokoro_tts.py` (554972f0...60b8c) | 0 | không áp dụng (thoát 0) |
| Bước 2 | Tạo tệp `tests/integration/adapt/e/test_adapt_e_tts_numbers.py` từ bản tham chiếu | không áp dụng | sha256 `fcd4858aacd146bb816b003c3bb983c5ae3e85fca4df35584ec4cc0876fa1216` |
| Bước 3 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_numbers.py -q -p no:cacheprovider` (mã cũ) | 1 | `35 failed in 1.34s` |
| Bước 4 | Tạo tệp `src/voice/domain/spoken_numbers.py` từ bản tham chiếu | không áp dụng | sha256 `482600038dbc09853b251119f5840a6c6a5eefe2f3861faf94b06eb71d74c8b8` |
| Bước 5 | Sửa `src/voice/adapters/real_kokoro_tts.py` theo bản tham chiếu | không áp dụng | sha256 `1faf118d73425244e6395a6e3c351427c24b31ca9a83b875b4f07299f539e027` |
| Bước 6 | Probe đối chiếu sha256 của cả 3 tệp mã/test với bản tham chiếu | 0 | không áp dụng (thoát 0) |
| Bước 7 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_numbers.py -q -p no:cacheprovider` (mã mới) | 0 | `35 passed in 0.94s` |
| Bước 8 | `python -m pytest tests/integration/adapt/e -q -p no:cacheprovider` | 0 | `168 passed in 3.20s` |
| Bước 9 | `python -m pytest tests/unit/voice -q -p no:cacheprovider` | 0 | `1078 passed, 89 subtests passed in 4.20s` |
| Bước 10 | `python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` | 0 | `56 passed in 0.25s` |
| Bước 11 | Probe hash của 2 tệp mới (`spoken_numbers.py`, `test_adapt_e_tts_numbers.py`) | 0 | không áp dụng (thoát 0) |
| Bước 12 | Probe đầu vào TTS của `real_kokoro_tts.py` (`model.create(spoken)`, revision tag) | 0 | không áp dụng (thoát 0) |
| Bước 13 | Probe module `spoken_numbers.py` chỉ dùng stdlib (`__future__`, `re`) | 0 | không áp dụng (thoát 0) |
| Bước 14 | Probe tệp test mới (`coveredIds: CT-TTS-001`, không monkeypatch/mock) | 0 | không áp dụng (thoát 0) |
| Bước 15 | Probe ADAPT-E-FIX2 trên `real_kokoro_tts.py` | 0 | không áp dụng (thoát 0) |
| Bước 16 | Probe compose và khóa nạp `_load_lock` | 0 | không áp dụng (thoát 0) |
| Bước 17 | Probe bố cục CP2A-LAYOUT (controlplane, pytest pythonpath, không tiền tố `src.`) | 0 | không áp dụng (thoát 0) |

## Trước và sau bản sửa

- Bước 3 (mã chưa sửa): `35 failed in 1.34s`. 34 ca thất bại do `ModuleNotFoundError: No module named 'voice.domain.spoken_numbers'` và 1 ca thất bại do model Kokoro nhận nguyên chuỗi số chữ số "72,000".
- Bước 7 (mã đã sửa): `35 passed in 0.94s`. Toàn bộ 35 ca kiểm thử mới đạt tuyệt đối.

## Văn bản model nhận cho các dạng số trong test và revision giọng mới

Văn bản chuyển đổi thực tế qua `speakable_english(text)` được cấp vào `model.create(spoken, ...)` cho các dạng số tiêu biểu:
- `72,000` -> `seventy-two thousand` (hàng nghìn)
- `1.5` -> `one point five` (thập phân, phần trăm: `1.5%` -> `one point five percent`)
- `.99` -> `four dollars and ninety-nine cents` (tiền tệ có cents)
- `2020-2024` -> `twenty twenty to twenty twenty-four` (khoảng năm)
- `3km` -> `three kilometers` (đơn vị đo)

Revision giọng mới:
- Khi cấu hình giọng tiếng Anh (`config.language` bắt đầu bằng `'en'`), chuỗi revision của Kokoro adapter được bổ sung thẻ `;numbers=spoken-en-1` ngay trước `;sentence_joins=model-tail`:
  `kokoro-onnx=={_library_version()};model={pins[MODEL_FILE]};voices={pins[VOICES_FILE]};voice={self._config.voice};numbers=spoken-en-1;sentence_joins=model-tail`
- Đối với các ngôn ngữ khác không bắt đầu bằng `'en'`, thẻ `;numbers=...` không được gắn và văn bản kịch bản được giữ nguyên vẹn.

## Số đo của Control (không chạy lại trong lane)

- Nguyên mẫu Control đo được 35 passed trên mã mới, 35 failed trên mã cũ.
- G2P espeak của runtime khóa: '72,000' trước đây phát ra ba lần zero, với bản chuẩn hoá không còn hiện tượng đọc từng chữ số zero.
- Aligner có sẵn (ADAPT-E-FIX3, FIX4, FIX7, FIX8, FIX10) đủ năng lực phủ 16 dạng số khi Whisper xuất lời nói hoặc chữ số.

## Giới hạn

- Kịch bản và phụ đề giữ nguyên chữ số như đã duyệt (tuân thủ FR-REN-008 và QR-OUT-008: phụ đề phải khớp kịch bản); chỉ lời đọc cấp cho mô hình TTS được chuyển đổi.
- Aligner không sửa đổi: Whisper thường viết lại chữ số (khớp trực tiếp); khi Whisper viết lời thì các dạng tiền có đơn vị, khoảng, độ, đơn vị đo, thập niên, số âm, giờ được phủ qua luật lấp FIX7/FIX8 (tính vào `unmatched_ratio`, mỗi cụm 1-3 từ), do đó kịch bản dày đặc các dạng này vẫn có thể chạm trần 5% như thiết kế trước.
- Các trường hợp chưa xử lý trong gói này: phân số và 24/7 (espeak đọc slash), ngày định dạng ISO 2024-05-01, số La Mã, số điện thoại, năm 1000-1099 (đọc như số đếm).
- Các test yêu cầu PostgreSQL (`test_pw_e2_voice_ports.py`, `test_adapt_wire_services.py`, `test_pw_e3_media_inputs.py`, `test_pw_e2e_batch_video.py`) không chạy trong lane do không có môi trường database cục bộ; các kịch bản e2e giả lập không chứa chữ số nên văn bản mô hình nhận không thay đổi.
- Các file giọng đã tạo trước đó không tạo lại; voice_revision mới tách biệt cache giọng sau gói.

## Kết luận

Gói `TTS-NUMBERS` đã giải quyết dứt điểm nhóm lỗi `OI-CP7-11-Q3`, loại bỏ hiện tượng đọc từng chữ số zero ("zero zero zero") cho các số đứng tự do trong video tiếng Anh, đồng thời bảo toàn tính toàn vẹn của kịch bản, phụ đề và cơ chế căn thời gian của aligner.
