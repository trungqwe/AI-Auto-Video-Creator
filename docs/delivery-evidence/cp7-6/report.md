# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, sau khi rebase lên 4a411bc79df8b9471c72dcf28b947eaa4de29d85, đo qua đường giải mã production với av==19.0.2.

Trạng thái: 5/7 mục PASS, 2/7 mục FAIL. Bị chặn BLOCKED tại Bước 4 do DEPENDENCY_GAP: runtime khoá 1ca840a7 vẫn cài đặt av==19.0.2 khiến faster_whisper.decode_audio hỏng TypeError (metadata_errors) trên toàn bộ 25 đoạn đo qua đường giải mã production của RealWhisperAligner.

## Kết quả

RG-05.weights_pinned: PASS
RG-05.tts_valid_wav: PASS
RG-05.aligner_unmatched: FAIL
RG-05.aligner_timing: FAIL
RG-05.speech_rate_calibrated: PASS
RG-05.vram_peak: PASS
RG-05.secret_scan: PASS

## Chi tiết đo

- weights_pinned: kokoro-v1.0.onnx sha256=7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5 group=kokoro-onnx
- weights_pinned: voices-v1.0.bin sha256=bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d group=kokoro-onnx
- weights_pinned: config.json sha256=666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae group=faster-whisper-small.en
- weights_pinned: model.bin sha256=62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a group=faster-whisper-small.en
- weights_pinned: tokenizer.json sha256=929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df group=faster-whisper-small.en
- weights_pinned: vocabulary.txt sha256=ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf group=faster-whisper-small.en
- tts_valid_wav: valid=25/25 format=24000Hz mono 16-bit voice=af_heart speed=1.0
- tts_valid_wav: words_and_actual_duration_ms={"dialogue-00": [24, 11541], "dialogue-01": [22, 10858], "dialogue-02": [21, 10944], "dialogue-03": [22, 11306], "dialogue-04": [23, 10581], "dialogue-05": [26, 13376], "dialogue-06": [26, 13013], "dialogue-07": [27, 12565], "dialogue-08": [26, 12778], "dialogue-09": [26, 12778], "dialogue-10": [46, 21184], "dialogue-11": [47, 22976], "dialogue-12": [46, 21888], "dialogue-13": [48, 24277], "dialogue-14": [47, 22570], "dialogue-15": [51, 24938], "dialogue-16": [53, 25344], "dialogue-17": [51, 24405], "dialogue-18": [51, 23808], "dialogue-19": [51, 24896], "script-20": [155, 79829], "script-21": [159, 81344], "script-22": [169, 82517], "script-23": [163, 81301], "script-24": [167, 81834]}
- tts_valid_wav: synth_latency_ms_max=13634 total_audio_s=762.9
- aligner_timing: diag signed start_delta_ms p10/p50/p90=None/None/None end_delta_ms p10/p50/p90=None/None/None scored=0/110
- aligner_timing: diag spans_sentences_margin_ms_by_passage={"dialogue-00": [2, 2, [683, 341]], "dialogue-01": [2, 2, [729, 360]], "dialogue-02": [2, 2, [708, 367]], "dialogue-03": [2, 2, [625, 389]], "dialogue-04": [2, 2, [658, 286]], "dialogue-05": [2, 2, [774, 390]], "dialogue-06": [2, 2, [806, 383]], "dialogue-07": [2, 2, [669, 377]], "dialogue-08": [2, 2, [762, 340]], "dialogue-09": [2, 2, [647, 370]], "dialogue-10": [3, 3, [695, 395]], "dialogue-11": [3, 3, [698, 380]], "dialogue-12": [3, 3, [634, 403]], "dialogue-13": [3, 3, [728, 394]], "dialogue-14": [3, 3, [662, 407]], "dialogue-15": [3, 3, [666, 407]], "dialogue-16": [3, 3, [698, 431]], "dialogue-17": [3, 3, [722, 400]], "dialogue-18": [3, 3, [709, 402]], "dialogue-19": [3, 3, [720, 438]], "script-20": [12, 12, [180, 371]], "script-21": [12, 12, [338, 428]], "script-22": [12, 12, [203, 462]], "script-23": [12, 12, [103, 392]], "script-24": [12, 12, [222, 767]]}
- aligner_timing: diag deltas_ms_by_passage={"dialogue-00": [[null, null], [null, null]], "dialogue-01": [[null, null], [null, null]], "dialogue-02": [[null, null], [null, null]], "dialogue-03": [[null, null], [null, null]], "dialogue-04": [[null, null], [null, null]], "dialogue-05": [[null, null], [null, null]], "dialogue-06": [[null, null], [null, null]], "dialogue-07": [[null, null], [null, null]], "dialogue-08": [[null, null], [null, null]], "dialogue-09": [[null, null], [null, null]], "dialogue-10": [[null, null], [null, null], [null, null]], "dialogue-11": [[null, null], [null, null], [null, null]], "dialogue-12": [[null, null], [null, null], [null, null]], "dialogue-13": [[null, null], [null, null], [null, null]], "dialogue-14": [[null, null], [null, null], [null, null]], "dialogue-15": [[null, null], [null, null], [null, null]], "dialogue-16": [[null, null], [null, null], [null, null]], "dialogue-17": [[null, null], [null, null], [null, null]], "dialogue-18": [[null, null], [null, null], [null, null]], "dialogue-19": [[null, null], [null, null], [null, null]], "script-20": [[null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null]], "script-21": [[null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null]], "script-22": [[null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null]], "script-23": [[null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null]], "script-24": [[null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null], [null, null]]}
- aligner_timing: diag sentences_ok_by_reference_noise_db={"-40": 0, "-35": 0, "-30": 0} primary_db=-30 total=110
- aligner_timing: diag clean_voice_rms_dbfs_median=-22.5
- aligner_timing: diag clean_voice_sentences_ok=0/110 (same aligner and same reference on the voice without music and SFX; diagnostic only, not the verdict)
- aligner_timing: diag gap_midpoint_within_tolerance=0/0 (mean of end delta of sentence n and start delta of sentence n+1; diagnostic only, not the verdict)
- speech_rate_calibrated: suggested_speech_rate_wpm=122 within_10pct=25/25 max_deviation=0.069
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1276 limit_mib=11264 samples=124 interval=1s first_mib=1237 elapsed_s=132
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Phương pháp mốc tham chiếu

Mốc tham chiếu được xác định trực tiếp trên file âm thanh giọng sạch (clean voice) bằng công cụ FFmpeg silencedetect đã ghim (sha256 theo runtime.lock.json). Ranh giới giữa các câu được chọn là khoảng im dài nhất nằm trong cửa sổ ±35% (tối thiểu 1000 ms) quanh vị trí kỳ vọng suy từ tỉ lệ số ký tự của các câu còn lại (tính lại sau mỗi lần cắt); độc lập với aligner. Điểm bắt đầu câu đầu tiên được tính từ cuối khoảng im đầu file (nếu có); điểm kết thúc câu cuối cùng được tính từ đầu khoảng im cuối file (nếu khoảng im này kết thúc sát độ dài file trong phạm vi dung sai 50 ms). Toàn bộ quá trình tạo mốc tham chiếu hoàn toàn độc lập với kết quả của aligner.

## Đường giải mã

Đo qua đường giải mã production của RealWhisperAligner (faster_whisper.decode_audio). Nhánh lane đã rebase lên tích hợp 4a411bc79df8b9471c72dcf28b947eaa4de29d85 (ADAPT-DEPS-FIX1 đã ghim av==18.1.0). Tuy nhiên, môi trường runtime khoá 1ca840a7 mà Control giao cho lane hiện vẫn cài đặt av==19.0.2 (do quá trình dựng runtime 8715e538 của Runtime Keeper bị FAILED tại RUNTIME_VERIFY_FAILED). Test đã bỏ toàn bộ đường giải mã tạm bằng FFmpeg, không bọc model_factory giả lập. FFmpeg ghim chỉ còn dùng cho silencedetect tham chiếu.

## Phân tích aligner_timing

Kết quả đo đạc độ lệch có dấu giữa mốc thời gian của aligner và mốc silencedetect tham chiếu:
- Toàn bộ 25 đoạn đo đều bị lỗi aligner_runtime_error khi gọi faster_whisper.decode_audio do PyAV av==19.0.2 không nhận tham số metadata_errors.
- Do toàn bộ aligner gặp runtime error, số câu đạt chuẩn là 0/110 (0.0%).
- Nguyên nhân thuộc về môi trường runtime khoá (ngoài owned paths), cần Control kích hoạt runtime khoá với av==18.1.0 cho lane.

## Bằng chứng BLOCKED (DEPENDENCY_GAP)

- Lệnh chạy: python -m pytest tests/real/test_cp7_voice_real.py -q -p no:cacheprovider
- Kết quả: 2 failed, 5 passed.
- Lỗi xuất hiện tại test_rg05_aligner_unmatched: AssertionError: aligner runtime error: production decode path failed
- Lỗi tại adapter: src.voice.ports.aligner.AlignerError: aligner_runtime_error: TypeError: open() got an unexpected keyword argument 'metadata_errors'
- Tệp gây lỗi: môi trường runtime khoá 1ca840a7 (chứa av==19.0.2) và phụ thuộc gián tiếp của faster-whisper==1.2.1.

```blocked-manifest
{"step": 4, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["ADAPT-DEPS-FIX1"], "paths": ["pyproject.toml", "uv.lock"], "ids": ["av==18.1.0"]}
```

## Giới hạn

Không sửa profile cấu hình, không sửa src/**, chi phí 0 USD, aligner chạy trên thiết bị theo profile.
