# ADAPT-E-FIX1: Aligner phục hồi phủ từ bằng mốc model và chỉnh mép câu theo Silero VAD

## 1. Phạm vi và tệp đã sửa
Bốn tệp thuộc danh sách owned paths được phép thay đổi trong gói ADAPT-E-FIX1:
- `src/voice/adapters/real_whisper_aligner.py`
- `tests/integration/adapt/e/test_adapt_e_aligner_edges.py`
- `tests/integration/adapt/e/test_adapt_e_tts_aligner.py`
- `docs/delivery-evidence/adapt-e-fix1/report.md`

Cam kết không sửa đổi bất kỳ tệp nào ngoài 4 đường dẫn trên:
- Không sửa `src/voice/adapters/real_kokoro_tts.py`.
- Không sửa composition root và wiring tại `src/controlplane/api/wiring/**`.
- Không sửa domain tại `src/voice/domain/**` hay ports tại `src/voice/ports/**`.
- Không sửa hồ sơ production, `runtime.lock.json`, `model-weights.lock.json`, `requirements.txt` hay lockfile.
- Không sửa các tệp test ngoài owned paths như `tests/integration/prod_wiring/**`, `tests/unit/**`.

## 2. Lỗi gốc và thiết kế đã thực hiện (A-F)
- Lỗi production gốc (ghi nhận tại CP7-6, kiểm chuẩn RG-05 đo trên CPU ngày 30/10/2026): `real_whisper_aligner.py` ban đầu loại bỏ mọi từ mô hình trả về có độ dài 0 ms và chỉ nhận các khối khớp nguyên văn của `difflib.SequenceMatcher.get_matching_blocks()`. Do đó, 17/25 đoạn giọng Kokoro thật bị thiếu ít nhất 1 từ (tổng cộng 36 từ bị mất mốc, trong đó có 28 từ đầu câu dài 0 ms cùng các từ số/tách từ như `localised`/`localized`, `30`/`thirty`, `multi` + `-year`, `well` + `-being`). Khi thiếu mốc từ, domain ném lỗi `TimingCoverageIncomplete` khiến pipeline sinh activity failure `COMMAND_REJECTED` không thử lại, làm hỏng quy trình tạo video thật ở bước word timing. Ngoài ra, mốc mép câu giữ nguyên DTW của Whisper khiến cuối câu bị sớm và đầu segment nuốt khoảng lặng.
- Thiết kế cải tiến đã triển khai đầy đủ (A-F):
  - (A) Phục hồi phủ từ: Thay `_matching_pairs` bằng hàm `_match_script` duyệt qua `difflib.SequenceMatcher.get_opcodes()`. Trong khối `replace`, nếu một token kịch bản khớp với chuỗi nối các từ nghe liên tiếp (ví dụ `multi` + `-year` -> `multiyear`), hoặc khối có cùng số lượng token ở hai phía (ví dụ `localised`/`localized`, `30`/`thirty`), các từ sẽ nhận mốc thời gian tương ứng từ mô hình; các trường hợp khác vẫn giữ `unmatched`.
  - (B) Cứu từ dài 0 ms: Sau bước kẹp, nếu `end <= start`, từ được xác định là dài 0 ms. Gán `end := mốc model t`, `start := max(onset của đoạn tiếng nói VAD chứa t - 1 ms, previous_end)`. Chỉ giữ từ khi `start < end`; nếu không có bằng chứng tiếng nói hoặc không thoả mãn thì từ vẫn ở trạng thái `unmatched`.
  - (C) Chỉnh mép câu theo đoạn tiếng nói: Hàm `_refine_edges` chỉ dịch chuyển mép từ ở chỗ mô hình để hở trước hoặc sau từ vào khoảng lặng, với giới hạn biên chặt chẽ `lo` và `hi` từ các từ láng giềng (hoặc `voice_duration_ms`). Nếu từ nằm trong tiếng nói, mép kẹp theo onset/offset của đoạn; nếu nằm trong lặng, mép tiến tới onset kế tiếp hoặc lùi về offset trước đó. Từ chồng lấn từ 2 đoạn tiếng nói trở lên được kẹp vào đoạn có độ chồng lấn lớn nhất. Kết quả luôn bảo đảm tính đơn điệu (`start >= previous_end`) và không rỗng (`start < end`).
  - (D) Bộ dò mặt nạ tiếng nói: Hàm `_default_speech_detector` ở mức module đọc tệp WAV bằng thư viện chuẩn `wave`, xác thực định dạng 16-bit mono PCM (ném `AlignerError` mã `aligner_runtime_error` nếu sai định dạng), nội suy tuyến tính sang 16 kHz bằng `numpy.interp`, sau đó gọi `faster_whisper.vad.get_speech_timestamps(samples, VadOptions(threshold=0.5, min_speech_duration_ms=0, min_silence_duration_ms=100, speech_pad_ms=0))`. Đổi mẫu sang ms bằng cách chia 16. Mọi lỗi phát sinh trong detector đều được che thông tin nhạy cảm (`redact_error`) và trả về `AlignerError` không thử lại (`retryable=False`). Cho phép tiêm tham số `speech_detector` tuỳ chọn khi khởi tạo `RealWhisperAligner`.
  - (E) Giữ nguyên hoàn toàn lời gọi `model.transcribe(..., vad_filter=False, condition_on_previous_text=False)`, cấu trúc `segment_boundaries`, `AlignmentResult`, định dạng `aligner_revision`, ý nghĩa của `AlignmentReport` và ngưỡng `max_unmatched_word_ratio`.
  - (F) Cập nhật docstring đầu tệp phản ánh trung thực nguyên tắc: Mốc lấy từ mô hình (Whisper và Silero VAD), không nội suy, không chia đều thời gian, không bịa mốc.

## 3. Giả định D8 và lý do kỹ thuật
- Từ nghe có `normalized is None` (từ phân tách thành nhiều token) không bao giờ được ghép trong khối `replace` để tránh gán sai mốc kịch bản.
- Độ tin cậy (`confidence`) của từ kịch bản ghép từ nhiều từ nghe liền nhau được lấy bằng giá trị nhỏ nhất (`min`) giữa các từ thành phần.
- Giới hạn láng giềng: `lo` của từ thứ $k$ được xác định là `max(slots[k-1].end_ms, final_end)` và `hi` là `slots[k+1].start_ms` (hoặc `voice_duration_ms` cho từ cuối), bảo đảm các từ luôn đơn điệu tuyệt đối và không vượt qua mốc gốc của từ bên cạnh.
- Từ được cứu ở bước dài 0 ms (`rescued is True`) không qua chỉnh mép lần hai (`_refine_edges`) nhưng vẫn đóng vai trò chặn biên cho các từ láng giềng.
- Khi từ chồng lấn từ 2 đoạn tiếng nói trở lên, từ được kẹp vào đoạn có độ dài giao nhau lớn nhất (nếu bằng nhau thì chọn đoạn xuất hiện sớm hơn).
- Mọi khoảng tiếng nói từ VAD được chuẩn hoá kẹp vào đoạn $[0, \text{voice\_duration\_ms}]$, và mẫu VAD được đổi sang ms qua công thức `int(round(sample / 16))`.

## 4. Bằng chứng Silero VAD
- Tệp mô hình: `faster_whisper/assets/silero_vad_v6.onnx`.
- Mã băm SHA-256 đã xác minh độc lập: `4cbf549b8326f60f80f2536d9eefeb450a9abe83365a098031c89719f1be17d2`.
- Mô hình Silero VAD và thư viện `onnxruntime` đã có sẵn trong môi trường runtime khoá của dự án; gói không cài đặt thêm bất kỳ thư viện ngoài nào.

## 5. Chi phí và hạn mức (R20)
- Toàn bộ quá trình căn chỉnh Whisper và phát hiện tiếng nói Silero VAD chạy cục bộ hoàn toàn trên CPU máy trạm.
- Không gọi bất kỳ dịch vụ đám mây hay API trả phí nào, không phát sinh chi phí phụ trội, tuân thủ nghiêm ngặt chính sách chi phí R20 (ngân sách dưới 50 USD/tháng).

## 6. Bảng lệnh đã chạy thực tế

| Bước | Lệnh thực thi | Exit code | Kết quả thực tế nguyên văn |
| --- | --- | --- | --- |
| Bước 9 | `python -m pytest tests/integration/adapt/e/test_adapt_e_aligner_edges.py -q -p no:cacheprovider` | 1 | `12 failed, 2 passed in 0.83s` (RED hợp lệ trên mã cũ) |
| Bước 19 | `python -m pytest tests/integration/adapt/e/test_adapt_e_aligner_edges.py tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` | 0 | `48 passed in 0.96s` (GREEN toàn diện) |
| Bước 20 | `python -m pytest tests/integration/prod_wiring/test_pw_e2_voice_ports.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | `26 passed, 89 subtests passed in 3.20s` |
| Bước 21 | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | `10 passed, 1 warning in 136.62s (0:02:16)` |
| Bước 22 | `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_kokoro_tts.py', 'real_whisper_aligner.py']); assert 'kokoro_onnx' in t and 'faster_whisper' in t and 'sha256' in t and 'from src.' not in t, 'adapter E'"` | 0 | Đạt assertions kiểm tra adapter E |
| Bước 23 | `python -c "import pathlib, re; t = pathlib.Path('src/voice/adapters/real_whisper_aligner.py').read_text(encoding='utf-8'); assert 'get_speech_timestamps' in t and 'vad_filter=False' in t and 'from src.' not in t, 'aligner'; bad = [p for p in ['threshold *= *0[.]5[^0-9]', 'min_speech_duration_ms *= *0[^0-9.]', 'min_silence_duration_ms *= *100[^0-9.]', 'speech_pad_ms *= *0[^0-9.]'] if not re.search(p, t)]; assert not bad, bad"` | 0 | Đạt assertions kiểm tra aligner và các tham số VadOptions literal |
| Bước 24 | `python -c "import hashlib, pathlib; p = pathlib.Path('C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/1ca840a7/venv/Lib/site-packages/faster_whisper/assets/silero_vad_v6.onnx'); print(hashlib.sha256(p.read_bytes()).hexdigest())"` | 0 | In mã băm `4cbf549b8326f60f80f2536d9eefeb450a9abe83365a098031c89719f1be17d2` |
| Lệnh kiểm cuối | `git diff --check` | 0 | Sạch hoàn toàn, không có lỗi khoảng trắng |

## 7. Báo cáo RED/GREEN trung thực
- Lượt chạy RED (Bước 9): Khi chạy trên mã cũ trước khi sửa đổi, có 12 ca thất bại và 2 ca thành công (`12 failed, 2 passed in 0.83s`).
  - Hai ca canh `test_zero_length_word_without_speech_evidence_stays_unmatched` (cả 2 kịch bản tham số) đạt kết quả PASS trên mã cũ đúng như dự kiến.
  - Ca kiểm thử `test_injected_speech_detector_receives_the_verified_wav_path` thất bại do `TypeError: RealWhisperAligner.__init__() got an unexpected keyword argument 'speech_detector'`. Báo cáo xác nhận đây là lỗi chữ ký tham số mới, không phải RED hành vi.
  - Chín ca kiểm thử còn lại đều thất bại đúng oracle hành vi trên mã cũ (bằng `AssertionError` hoặc `DID NOT RAISE AlignerError`), không bị lỗi import hay thiết lập môi trường.
- Lượt chạy GREEN (Bước 19): Sau khi cập nhật mã nguồn adapter, toàn bộ 48 ca kiểm thử của cả 2 tệp đều đạt PASS (`48 passed in 0.96s`).

## 8. Việc còn lại (CP7-6)
- Đo lại 110 câu chuẩn đạt ngưỡng sai số $\le 150\text{ ms}$ và đo kiểm độ phủ từ trên 25 đoạn giọng đọc Kokoro thật thuộc phạm vi kiểm chuẩn CP7-6 (RG-05).
- Slice ADAPT-E-FIX1 chỉ tập trung sửa chữa adapter trong phạm vi được giao, không đưa ra tuyên bố về số đo thực tế và không dùng dữ liệu giả lập để tuyên bố hoàn thành các cổng kiểm chuẩn bên ngoài.
