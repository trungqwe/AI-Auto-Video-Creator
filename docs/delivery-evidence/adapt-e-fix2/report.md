# ADAPT-E-FIX2: TTS giữ khoảng nghỉ câu do model sinh ở chỗ nối lô Kokoro

## 1. Phạm vi và tệp đã sửa
Ba tệp thuộc danh sách owned paths được phép thay đổi trong gói ADAPT-E-FIX2:
- `src/voice/adapters/real_kokoro_tts.py`
- `tests/integration/adapt/e/test_adapt_e_tts_joins.py`
- `docs/delivery-evidence/adapt-e-fix2/report.md`

Cam kết không sửa đổi bất kỳ tệp nào ngoài 3 đường dẫn trên:
- Không sửa `tests/integration/adapt/e/test_adapt_e_tts_aligner.py` hay `tests/integration/adapt/e/test_adapt_e_aligner_edges.py`.
- Không sửa `profile.json`, `voice.py`, `src/voice/adapters/real_whisper_aligner.py`.
- Không sửa composition root và wiring tại `src/controlplane/api/wiring/**`.
- Không sửa domain tại `src/voice/domain/**` hay ports tại `src/voice/ports/**`.
- Không sửa hồ sơ production, `runtime.lock.json`, `model-weights.lock.json`, `pyproject.toml`, `requirements.txt` hay lockfile.
- Không sửa các tệp test ngoài owned paths như `tests/integration/prod_wiring/**`, `tests/unit/**`.

## 2. Lỗi gốc (CP7-6, RG-05, đo trên CPU 30/10/2026)
- Lỗi production gốc: `src/voice/adapters/real_kokoro_tts.py` gọi một lần `Kokoro.create(text, voice, speed, lang)` với tham số mặc định `trim=True`. Thư viện `kokoro-onnx` 0.4.9 chia kịch bản thành các lô tại dấu câu (dưới 510 phoneme), sau đó cắt khoảng im đầu và cuối mỗi lô (`trim` kiểu librosa, `top_db=60`) rồi nối liền (`kokoro_onnx/__init__.py:194-207`).
- Mỗi kịch bản production 61-70 s có khoảng 3 lô, trong đó 2 chỗ nối rơi đúng vào dấu chấm kết thúc câu. Do bị cắt im cả hai đầu trước khi nối, khoảng im tại chỗ nối chỉ còn 100-292 ms, ngắn hơn cả chỗ ngắt hơi trong câu (lên tới 481 ms) và ranh giới giữa các câu trong cùng một lô (573-808 ms). Hậu quả: âm thanh nghe dính câu, Silero VAD không tách được chỗ nối nào (0/10), mốc `silencedetect` của kiểm chuẩn RG-05 chọn sai 8/10 chỗ nối.
- Thí nghiệm đã xác nhận: Khi giữ lại đuôi im do mô hình sinh ở chỗ nối câu, khoảng im tại chỗ nối đạt 515-720 ms, dạng sóng âm thanh tiếng nói không đổi, Silero VAD và `silencedetect` tách đúng 10/10, bộ căn chỉnh aligner đã sửa (ADAPT-E-FIX1) nâng độ chính xác từ 96/110 lên khoảng 105-106/110 câu thay vì 96/110.

## 3. Thiết kế kỹ thuật đã thực hiện
- Bọc mô hình bằng lớp cấp module `SentencePauseKokoro(kokoro)`:
  - Cung cấp phương thức `create(self, text, voice, speed, lang) -> tuple[object, int]` nhận đúng 4 tham số mà adapter truyền vào.
  - Tái tạo chính xác vòng lặp của `Kokoro.create` phiên bản 0.4.9 (`kokoro_onnx/__init__.py:184-207`), chỉ thay đổi duy nhất ở bước cắt tỉa âm thanh:
    - Xác thực `voice` tồn tại trong `kokoro.voices`, lấy `style = kokoro.get_voice_style(voice)`.
    - Phân lô phoneme: `batches = kokoro._split_phonemes(kokoro.tokenizer.phonemize(text, lang))`.
    - Duyệt từng lô qua `enumerate(batches)`: sinh âm thanh `audio, rate = kokoro._create_audio(batch, style, speed)`, lấy khoảng cắt `start, end = (int(value) for value in trim(audio)[1])` với thiết lập mặc định của thư viện, không truyền tham số.
    - Quy tắc nối: nếu lô không phải lô cuối (`index < len(batches) - 1`) và ký tự không trắng cuối của lô thuộc nhóm kết thúc câu `('.', '!', '?')`, mảnh âm thanh giữ nguyên đuôi do model sinh: `audio[start:]`. Trong mọi trường hợp khác (lô cuối cùng hoặc kết thúc bằng dấu phẩy, chấm phẩy, ký tự khác), cắt tỉa cả hai đầu giống thư viện: `audio[start:end]`.
    - Nối các mảnh và trả về: `np.concatenate(pieces), rate`.
  - Nhập khẩu lười (`import numpy as np; from kokoro_onnx.trim import trim`) ngay bên trong phương thức `create`, không nạp ở cấp module.
  - Tuyệt đối không thêm hằng số thời gian hay ngưỡng cứng nào; không dùng `create_stream` hay `asyncio`.
- Hàm khởi tạo mặc định `_default_factory` trả về `SentencePauseKokoro(Kokoro(model_path, voices_path))`, giữ nguyên `from kokoro_onnx import Kokoro` bên trong thân hàm.
- Đánh dấu phiên bản trong `RealKokoroTts._load`: khi `model` là thể hiện của `SentencePauseKokoro`, `voice_revision` bổ sung hậu tố `;sentence_joins=model-tail` để phân biệt nguồn gốc với các tệp WAV sinh bởi mã cũ; mô hình tiêm từ ngoài qua `model_factory` giữ nguyên chuỗi revision ban đầu không có thẻ này.
- Cập nhật docstring đầu tệp ghi rõ hai điều: lớp bọc dùng API riêng `_split_phonemes` và `_create_audio` của `kokoro-onnx==0.4.9` (ghim trong `pyproject.toml`), và `model_factory` tiêm vào thì thay toàn bộ model, kể cả luật nối.
- Giữ nguyên toàn bộ: phương thức `synthesize` (vẫn gọi `model.create(...)` một lần duy nhất), hàm chuyển đổi `_to_pcm16`, cấu hình `KokoroConfig`, logic kiểm tra sha256 của trọng số, mọi mã lỗi và danh sách xuất `__all__`.

## 4. Ghi chú vận hành
- Thời lượng âm thanh: mỗi kịch bản dài thêm khoảng 0,5-0,9 s (khoảng thời lượng tổng `duration_range_ms` từ 61 đến 70 s vẫn áp; tốc độ nói `speech_rate_wpm` do CP7-6 đo lại sau gói này).
- Trường hợp biên hiếm gặp: nếu một lô mới bắt đầu bằng dấu chấm, đầu lô vẫn bị cắt như cũ theo mặc định của thư viện.
- Lớp bọc phụ thuộc vào API riêng `_split_phonemes` và `_create_audio` của thư viện `kokoro-onnx==0.4.9` (đã được ghim chặt trong `pyproject.toml`).
- Mô hình tiêm qua `model_factory` thay thế toàn bộ model, kể cả luật nối câu.

## 5. Bảng 4 ca test mới trong `test_adapt_e_tts_joins.py`

| STT | Tên ca kiểm thử | Điều kiện khẳng định |
| --- | --- | --- |
| 1 | `test_sentence_joins_keep_model_tail_through_default_factory` | Kịch bản 3 câu kết thúc bằng dấu chấm sinh 3 lô: (i) có đúng 2 khoảng im $\ge 10800$ mẫu giữa các đoạn tiếng; (ii) dãy mẫu khác 0 bằng của `create(text, voice, speed, lang)` thật (`trim=True`), tức tiếng nói không đổi; (iii) số mẫu 0 ở đầu và cuối bằng của bản thư viện; (iv) số khung bằng khung của bản thư viện cộng $\Sigma(\text{len}(\text{lô}) - \text{end\_trim})$ trên các lô không cuối. |
| 2 | `test_comma_join_and_single_batch_unchanged` (2 tham số) | Với văn bản nối tại dấu phẩy (`COMMA_TEXT`) và văn bản đơn một lô (`SINGLE_TEXT`), dữ liệu PCM đầu ra giống từng byte với `create` thật (`trim=True`), bảo đảm không áp dụng luật nối ra ngoài dấu `.!?` và giữ nguyên thoại. |
| 3 | `test_wrapper_keeps_voice_speed_lang_and_batching` | Chứng minh không đổi voice, speed, lang hay cách chia lô: `tokenizer.phonemize` gọi đúng 1 lần với `(text, language)`; `_create_audio` gọi đúng 1 lần cho mỗi lô theo thứ tự `_split_phonemes`, với style có hình dạng của `voices[voice]` và speed bằng `config.speed`. |
| 4 | `test_revision_marks_join_policy_and_injected_model_path_unchanged` | Với model mặc định qua `_default_factory`, `voice_revision` chứa `;sentence_joins=model-tail`, sha256 của model, sha256 của voices và `af_heart`. Với model 4 tham số tiêm qua `model_factory`, `create` được gọi đúng 1 lần với văn bản nguyên vẹn, PCM giữ nguyên, và `voice_revision` không có thẻ `sentence_joins`. |

## 6. Bằng chứng RED/GREEN trung thực

### 6.1. Bằng chứng RED (Bước 6)
Chạy trên mã nguồn cũ trước khi thêm `SentencePauseKokoro`:
- Lệnh thực thi:
  ```powershell
  $env:PYTEST_DEBUG_TEMPROOT='C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\ADAPT-E-FIX2-implement-r0-ac1b5c0961'
  python -m pytest tests/integration/adapt/e/test_adapt_e_tts_joins.py -q -p no:cacheprovider
  ```
- Exit code: 1
- Đầu ra nguyên văn:
  ```text
  F...F                                                                    [100%]
  ================================== FAILURES ===================================
  _________ test_sentence_joins_keep_model_tail_through_default_factory _________

  tts_env = namespace(config=KokoroConfig(weights_dir=WindowsPath('C:/Users/Admin/AppData/Local/Temp/ai-setup-pytest/ADAPT-E-FIX2-...i-setup-pytest/ADAPT-E-FIX2-implement-r0-ac1b5c0961/pytest-of-Admin/pytest-0/test_sentence_joins_keep_model0/staging'))

      def test_sentence_joins_keep_model_tail_through_default_factory(tts_env):
          result = synth(tts_env, SENTENCE_TEXT)
          pcm = wav_pcm(result)
          ref = reference_pcm(SENTENCE_TEXT)
          gaps, lead, trail = shape_of(pcm)
          _, ref_lead, ref_trail = shape_of(ref)
          batches = LibraryKokoro._split_phonemes(FakeKokoro.instances[-1], SENTENCE_TEXT)
          assert len(batches) == 3

  >       assert len([int(g) for g in gaps if g >= TAIL]) == 2
  E       assert 0 == 2
  E        +  where 0 = len([])

  tests\integration\adapt\e\test_adapt_e_tts_joins.py:176: AssertionError
  ______ test_revision_marks_join_policy_and_injected_model_path_unchanged ______

  tts_env = namespace(config=KokoroConfig(weights_dir=WindowsPath('C:/Users/Admin/AppData/Local/Temp/ai-setup-pytest/ADAPT-E-FIX2-...i-setup-pytest/ADAPT-E-FIX2-implement-r0-ac1b5c0961/pytest-of-Admin/pytest-0/test_revision_marks_join_polic0/staging'))

      def test_revision_marks_join_policy_and_injected_model_path_unchanged(tts_env):
          result = synth(tts_env, SINGLE_TEXT)
  >       assert result.voice_revision.endswith(';sentence_joins=model-tail')
  E       AssertionError: assert False
  E        +  where False = <built-in method endswith of str object at 0x00000171BFC24FF0>(';sentence_joins=model-tail')
  E        +    where <built-in method endswith of str object at 0x00000171BFC24FF0> = 'kokoro-onnx==0.4.9;model=bb723fd6f645163ecea6427700c41c994aa2d1dfe8a0d4cffc17292d30b162a0;voices=151e9cfa05cd26060d78ddf481a97333bc51aadfae2506c34b13aa82261d124a;voice=af_heart'.endswith
  E        +      where 'kokoro-onnx==0.4.9;model=bb723fd6f645163ecea6427700c41c994aa2d1dfe8a0d4cffc17292d30b162a0;voices=151e9cfa05cd26060d78ddf481a97333bc51aadfae2506c34b13aa82261d124a;voice=af_heart' = TtsSynthesis(voice_revision='kokoro-onnx==0.4.9;model=bb723fd6f645163ecea6427700c41c994aa2d1dfe8a0d4cffc17292d30b162a0...ae2506c34b13aa82261d124a;voice=af_heart', usage_metrics=UsageMetrics({'characters': 12, 'audio_ms': 85}), latency_ms=3).voice_revision

  tests\integration\adapt\e\test_adapt_e_tts_joins.py:221: AssertionError
  =========================== short test summary info ===========================
  FAILED tests/integration/adapt/e/test_adapt_e_tts_joins.py::test_sentence_joins_keep_model_tail_through_default_factory
  FAILED tests/integration/adapt/e/test_adapt_e_tts_joins.py::test_revision_marks_join_policy_and_injected_model_path_unchanged
  2 failed, 3 passed in 1.26s
  ```
- Nhận xét: Ca 1 và Ca 4 thất bại đúng oracle khẳng định hành vi (khoảng im chỗ nối bị cắt còn khoảng 2017 mẫu nên điều kiện (i) có 2 khoảng im $\ge 10800$ mẫu không thỏa mãn; và revision chưa gắn thẻ). Ca 2 và Ca 3 đạt PASS đóng vai trò chặn hồi quy. Không có lỗi import hay lỗi thiết lập môi trường.

### 6.2. Bằng chứng GREEN ba tệp test phân hệ E (Bước 9)
- Lệnh thực thi:
  ```powershell
  $env:PYTEST_DEBUG_TEMPROOT='C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\ADAPT-E-FIX2-implement-r0-ac1b5c0961'
  python -m pytest tests/integration/adapt/e/test_adapt_e_tts_joins.py tests/integration/adapt/e/test_adapt_e_tts_aligner.py tests/integration/adapt/e/test_adapt_e_aligner_edges.py -q -p no:cacheprovider
  ```
- Exit code: 0
- Đầu ra nguyên văn:
  ```text
  .....................................................                    [100%]
  53 passed in 1.70s
  ```

### 6.3. Bằng chứng GREEN test wiring và layout (Bước 10)
- Lệnh thực thi:
  ```powershell
  $env:PYTEST_DEBUG_TEMPROOT='C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\ADAPT-E-FIX2-implement-r0-ac1b5c0961'
  python -m pytest tests/integration/prod_wiring/test_pw_e2_voice_ports.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider
  ```
- Exit code: 0
- Đầu ra nguyên văn:
  ```text
  .....................                              [100%]
  26 passed, 89 subtests passed in 9.17s
  ```

### 6.4. Bằng chứng probes tĩnh (Bước 11 và 12)
- Probe 1 (Bước 11 - kiểm tra `real_kokoro_tts.py`):
  - Lệnh: `python -c "import pathlib; t = pathlib.Path('src/voice/adapters/real_kokoro_tts.py').read_text(encoding='utf-8'); assert 'kokoro_onnx' in t and 'sha256' in t and '_split_phonemes' in t and 'sentence_joins=model-tail' in t and 'from src.' not in t, 'ADAPT-E-FIX2'"`
  - Exit code: 0 (không ném AssertionError).
- Probe 2 (Bước 12 - kiểm tra cả hai adapter phân hệ E):
  - Lệnh: `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_kokoro_tts.py', 'real_whisper_aligner.py']); assert 'kokoro_onnx' in t and 'faster_whisper' in t and 'sha256' in t and 'from src.' not in t, 'adapter E'"`
  - Exit code: 0 (không ném AssertionError).

### 6.5. Kiểm tra khoảng trắng thừa `git diff --check`
- Lệnh: `git diff --check`
- Exit code: 0 (sạch hoàn toàn, không có lỗi khoảng trắng thừa).

## 7. Ranh giới R21 và chi phí
- Ranh giới R21: Thay đổi chỉ giới hạn nghiêm ngặt trong phân hệ E (`src/voice`) và các đường dẫn được giao quyền sở hữu (owned paths: `src/voice/adapters/real_kokoro_tts.py`, `tests/integration/adapt/e/test_adapt_e_tts_joins.py`, `docs/delivery-evidence/adapt-e-fix2/report.md`). Không tác động đến các phân hệ khác (A, B, C, D, F, G, H, I, J) và không thay đổi ranh giới hay thẩm quyền sở hữu module.
- Chi phí vận hành: Toàn bộ quá trình tổng hợp giọng đọc và căn chỉnh chạy cục bộ hoàn toàn trên CPU máy trạm, không thực hiện bất kỳ cuộc gọi dịch vụ bên ngoài hay API đám mây nào, chi phí phát sinh bằng 0 USD.

## 8. Việc còn lại (CP7-6)
- Việc đo đạc lại độ chính xác trên 110 câu chuẩn và kiểm chuẩn độ bao phủ từ trên 25 đoạn giọng đọc Kokoro thật (RG-05) thuộc trách nhiệm và phạm vi kiểm thử của CP7-6 khi cấp lại sau gói này.
- Gói ADAPT-E-FIX2 chỉ thực hiện đúng và đủ việc sửa chữa kỹ thuật theo chỉ đạo, không tuyên bố số đo thực tế thay cho CP7-6.
