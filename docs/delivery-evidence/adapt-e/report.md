# ADAPT-E: TTS Kokoro cục bộ và aligner faster-whisper

## 1. Phạm vi và tệp đã sửa
- `src/voice/adapters/real_kokoro_tts.py`
- `src/voice/adapters/real_whisper_aligner.py`
- `tests/integration/adapt/e/test_adapt_e_tts_aligner.py`
- `docs/delivery-evidence/adapt-e/report.md`

Không sửa bất kỳ tệp nào ngoài 4 tệp thuộc owned paths ở trên (không sửa `tools/launcher/prod/model-weights.lock.json`, `pyproject.toml`, `uv.lock`, `src/voice/domain/**`, `src/voice/ports/**` hay `src/voice/adapters/__init__.py`).

## 2. Thiết kế và giả định D8
- `RealKokoroTts` kiểm tra cây Git (`_inside_git_tree`), đọc pin từ lock (`tools/launcher/prod/model-weights.lock.json`), kiểm tra SHA-256 của hai tệp `kokoro-v1.0.onnx` và `voices-v1.0.bin` trước khi nạp, nạp một lần duy nhất; nếu thiếu tệp, lệch mã băm, chưa ghim hoặc nằm trong cây Git thì trả về `TtsProviderError` với `retryable=False`, tuyệt đối không tải ngầm từ mạng và không kết nối Internet.
- Giọng đọc, tốc độ, ngôn ngữ và tần số lấy mẫu (`sample_rate`) lấy trực tiếp từ `KokoroConfig`; các trường `pronunciation_hints` và `style_parameters` của request chưa áp dụng trong slice này; lỗi runtime đều có `retryable=False` và được redact các giá trị nhạy cảm; âm thanh WAV mono PCM 16-bit được ghi vào thư mục staging qua tệp tạm `.part` rồi hoán đổi nguyên tử (`replace`) sang `.wav`.
- `RealWhisperAligner` kiểm tra khóa theo nhóm `faster-whisper-small.en`, nạp `faster_whisper.WhisperModel` với `local_files_only=True`, gọi `transcribe` với `word_timestamps=True`; so khớp mốc từ phiên âm với văn bản kịch bản bằng `difflib.SequenceMatcher` trên các token đã chuẩn hóa theo `TokenizationPolicy`.
- Tỷ lệ từ không khớp được tính theo công thức: `unmatched_ratio = (từ script thiếu + từ model thừa) / (số từ script + số từ model)`; nếu vượt ngưỡng `max_unmatched_word_ratio` thì trả về `AlignerError` mã `'alignment_unmatched_ratio_exceeded'`, tuyệt đối không nội suy hay chia đều mốc thời gian; các mốc thời gian được kẹp vào khoảng `[mốc cuối từ trước, voice_duration_ms]`, từ không còn khoảng hợp lệ được xem là không khớp; `voice_locale_reported` là locale thư viện trả về tương ứng với ngôn ngữ cấu hình, không phải bộ nhận diện ngôn ngữ độc lập; `aligner_revision` ghi nhận phiên bản thư viện `faster-whisper` và mã băm SHA-256 của `model.bin`; `last_report` lưu trữ `AlignmentReport` chi tiết đánh dấu và đếm các chỉ mục từ không khớp vì `AlignmentResult` không có trường riêng.

## 3. Trạng thái trọng số
Tệp `tools/launcher/prod/model-weights.lock.json` hiện còn SHA-256 null kèm trạng thái `BLOCKED` (theo mục mở `OI-ADAPT-06`). Do đó, hai adapter khi chạy với lock hiện tại trên môi trường thật sẽ fail-closed với lỗi `weights_unpinned` cho tới khi Control ghi nhận mã băm chính thức; slice này tuyệt đối không tự ý bịa hash.

## 4. Lệnh đã chạy
Bảng ghi nhận kết quả thực tế trên worktree:

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 14 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` | 1 | `34 failed in 1.31s` (toàn bộ 34 test thất bại vì `NotImplementedError` từ stub hoặc assertion mã nguồn; 3 lỗi đầu: `test_synthesize_writes_mono_pcm_wav_with_configured_parameters`, `test_model_is_verified_and_loaded_once`, `test_sha256_mismatch_is_rejected_before_loading[kokoro-v1.0.onnx]`) |
| Bước 25 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` | 0 | `34 passed in 0.49s` |
| Bước 26 | `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_kokoro_tts.py', 'real_whisper_aligner.py']); assert 'kokoro_onnx' in t and 'faster_whisper' in t and 'sha256' in t and 'from src.' not in t, 'adapter E'"` | 0 | Đạt toàn bộ assertion (chứa `kokoro_onnx`, `faster_whisper`, `sha256`, không chứa tiền tố `from src.`) |
| Bước 27 | `git diff --check` | 0 | Sạch, không có lỗi khoảng trắng cuối dòng |

## 5. RED/GREEN
Quy trình tuân thủ nghiêm ngặt nguyên tắc test-first:
- RED: Chứng kiến RED hành vi thực tế ở Bước 14 với 34/34 test thất bại do `NotImplementedError` từ stub và kiểm tra tĩnh mã nguồn, hoàn toàn không có lỗi `ImportError` hay cú pháp.
- GREEN: Sau khi hoàn tất triển khai logic adapter ở Bước 15-24 (và hiệu chỉnh lỗi gõ `access_token` tại một test case che giấu secret), toàn bộ 34/34 test đã chuyển sang GREEN ở Bước 25 với exit code 0 trong 0.49s.

## 6. Việc còn lại (backlog)
- Nạp ONNX và phonemizer của `kokoro_onnx` trên môi trường máy chủ thật, thẩm định chất lượng nghe thử giọng đọc, độ chính xác căn mốc từ và locale phát hiện độc lập thuộc phạm vi CP7.
- Control cập nhật SHA-256 và commit Hugging Face chính thức vào `model-weights.lock.json` theo `OI-ADAPT-06`.
- Tầng tích hợp `ADAPT-WIRE` kết nối hàm `resolve_audio`, thư mục staging và cấu hình sản xuất thực tế.
