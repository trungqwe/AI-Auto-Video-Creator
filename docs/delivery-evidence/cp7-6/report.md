# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, sau khi rebase lên 08a9ebe0dfaa6822058b856a91331f1afc6b52a0 (ADAPT-CONFIG-FIX1 đã ghim trọng số).

Trạng thái: BLOCKED tại Bước 12 (DEPENDENCY_GAP). Runtime khoá của lane cài đặt thư viện av==19.0.2 không tương thích với faster-whisper==1.2.1. Khi gọi RealWhisperAligner.align(), faster_whisper/audio.py:46 gọi av.open(input_file, mode="r", metadata_errors="ignore") gây lỗi TypeError: open() got an unexpected keyword argument 'metadata_errors'.

## Kết quả

RG-05.weights_pinned: PASS
RG-05.tts_valid_wav: PASS
RG-05.aligner_unmatched: BLOCKED
RG-05.aligner_timing: BLOCKED
RG-05.speech_rate_calibrated: BLOCKED
RG-05.vram_peak: PASS
RG-05.secret_scan: PASS

## Chi tiết đo các mục đã chạy đạt

- weights_pinned: kokoro-v1.0.onnx sha256=7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5 group=kokoro-onnx
- weights_pinned: voices-v1.0.bin sha256=bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d group=kokoro-onnx
- weights_pinned: config.json sha256=666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae group=faster-whisper-small.en
- weights_pinned: model.bin sha256=62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a group=faster-whisper-small.en
- weights_pinned: tokenizer.json sha256=929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df group=faster-whisper-small.en
- weights_pinned: vocabulary.txt sha256=ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf group=faster-whisper-small.en
- tts_valid_wav: valid=25/25 format=24000Hz mono 16-bit voice=af_heart speed=1.0
- tts_valid_wav: words_and_actual_duration_ms={"dialogue-00": [24, 11541], "dialogue-01": [22, 10858], "dialogue-02": [21, 10944], "dialogue-03": [22, 11306], "dialogue-04": [23, 10581], "dialogue-05": [26, 13376], "dialogue-06": [26, 13013], "dialogue-07": [27, 12565], "dialogue-08": [26, 12778], "dialogue-09": [26, 12778], "dialogue-10": [46, 21184], "dialogue-11": [47, 22976], "dialogue-12": [46, 21888], "dialogue-13": [48, 24277], "dialogue-14": [47, 22570], "dialogue-15": [51, 24938], "dialogue-16": [53, 25344], "dialogue-17": [51, 24405], "dialogue-18": [51, 23808], "dialogue-19": [51, 24896], "script-20": [155, 79829], "script-21": [159, 81344], "script-22": [169, 82517], "script-23": [163, 81301], "script-24": [167, 81834]}
- tts_valid_wav: synth_latency_ms_max=13364 total_audio_s=764.0
- vram_peak: peak_mib=1087 limit_mib=11264 samples=121 interval=1s first_mib=1080 elapsed_s=129
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Bằng chứng BLOCKED (DEPENDENCY_GAP)

- Lệnh chạy: python -m pytest tests/real/test_cp7_voice_real.py -q -p no:cacheprovider
- Lỗi xuất hiện: voice.ports.aligner.AlignerError: aligner_runtime_error: TypeError: open() got an unexpected keyword argument "metadata_errors"
- Nguyên nhân gốc: faster-whisper==1.2.1 phụ thuộc av>=11. Runtime khoá cài đặt av==19.0.2. Từ phiên bản PyAV 14.0.0 trở lên, tham số metadata_errors bị loại bỏ khỏi av.open(). Khi RealWhisperAligner.align() gọi model.transcribe(), hàm decode_audio trong faster_whisper/audio.py:46 gọi av.open(input_file, mode="r", metadata_errors="ignore") dẫn đến lỗi TypeError.
- Tệp gây lỗi: src/voice/adapters/real_whisper_aligner.py (thuộc phân hệ E / CP7-2, ngoài owned paths của CP7-6) và môi trường runtime pyproject.toml (thuộc sở hữu của gói ADAPT-DEPS).

## Việc Control cần làm để mở khoá

- Gói ADAPT-DEPS cần ghim av<14 (ví dụ av==13.1.0) vào pyproject.toml và cập nhật uv.lock, sau đó dựng lại runtime khoá của lane.
- Hoặc cập nhật adapter src/voice/adapters/real_whisper_aligner.py để xử lý tương thích với PyAV mới.
- Sau khi dependency được khắc phục, Orchestrator lập lại lệnh để CP7-6 chạy nghiệm thu toàn diện.

## Giới hạn

- Worker không tự cài đặt thư viện (pip install, uv pip install bị cấm).
- Worker không sửa tệp ngoài owned paths (src/**, pyproject.toml, uv.lock).
- Không tạo workaround hay monkeypatch giả lập để bypass gate kiểm thử thực tế.

```blocked-manifest
{"step":12,"kind":"DEPENDENCY_GAP","ownerTaskIds":["ADAPT-DEPS"],"paths":["pyproject.toml","uv.lock"],"ids":["av<14"]}
```
