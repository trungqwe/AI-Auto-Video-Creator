# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, sau khi rebase lên 4a411bc79df8b9471c72dcf28b947eaa4de29d85, đo qua đường giải mã production với guard av==18.1.0.

Trạng thái: 5/7 mục PASS, 2/7 mục BLOCKED. Bị chặn tại Bước 2 do môi trường runtime khoá 1ca840a7 vẫn cài đặt av==19.0.2 trong khi pyproject.toml ràng buộc av==18.1.0; guard av dừng sớm an toàn trước khi đo aligner, không mất thời gian chạy lỗi.

## Kết quả

RG-05.weights_pinned: PASS
RG-05.tts_valid_wav: PASS
RG-05.aligner_unmatched: BLOCKED
RG-05.aligner_timing: BLOCKED
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
- speech_rate_calibrated: suggested_speech_rate_wpm=122 within_10pct=25/25 max_deviation=0.069
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1276 limit_mib=11264 samples=124 interval=1s first_mib=1237 elapsed_s=132
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)
- (Ghi chú: Các chỉ số của tts_valid_wav, speech_rate_calibrated, vram_peak và secret_scan được ghi nhận từ lượt chạy đo trước tại commit 4a8801ef647ca230d171794a9d4579a81f594f9e bằng cùng mã TTS và trọng số Kokoro thật; chưa đo lại trong lượt này vì guard av chặn sớm ở setup của fixture measurement).

## Phương pháp mốc tham chiếu

Mốc tham chiếu được xác định trực tiếp trên file âm thanh giọng sạch (clean voice) bằng công cụ FFmpeg silencedetect đã ghim (sha256 theo runtime.lock.json). Ranh giới giữa các câu được chọn là khoảng im dài nhất nằm trong cửa sổ ±35% (tối thiểu 1000 ms) quanh vị trí kỳ vọng suy từ tỉ lệ số ký tự của các câu còn lại (tính lại sau mỗi lần cắt); độc lập với aligner. Điểm bắt đầu câu đầu tiên được tính từ cuối khoảng im đầu file (nếu có); điểm kết thúc câu cuối cùng được tính từ đầu khoảng im cuối file (nếu khoảng im này kết thúc sát độ dài file trong phạm vi dung sai 50 ms). Toàn bộ quá trình tạo mốc tham chiếu hoàn toàn độc lập với kết quả của aligner.

## Đường giải mã

Đo qua đường giải mã production của RealWhisperAligner (faster_whisper.decode_audio). Nhánh lane đã rebase lên tích hợp 4a411bc79df8b9471c72dcf28b947eaa4de29d85 (ADAPT-DEPS-FIX1 đã ghim av==18.1.0). Trước khi thực hiện đo, fixture measurement kiểm tra phiên bản av cài trong runtime so với ràng buộc uv trong pyproject.toml (av==18.1.0). Do runtime khoá 1ca840a7 hiện vẫn cài đặt av==19.0.2, guard assertion đã chặn sớm ngay tại setup fixture để bảo vệ tài nguyên và thời gian; không còn bất kỳ đường giải mã thay thế nào ngoài faster_whisper.decode_audio và không bọc model_factory hay monkeypatch.

## Phân tích aligner_timing

Runtime khoá 1ca840a7 chứa `av-19.0.2.dist-info`, ràng buộc đã gộp là av==18.1.0 (pyproject.toml:28), cần Control dựng lại/cấp runtime khoá có av==18.1.0 rồi chạy lại lệnh kiểm; đây là điều kiện môi trường nằm ngoài owned paths, Worker không tự cài, không tạo workaround.

## Giới hạn

Không sửa profile cấu hình, không sửa src/**, chi phí 0 USD, aligner chạy trên thiết bị theo profile.
