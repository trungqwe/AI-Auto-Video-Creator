# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane.

Trạng thái: BLOCKED. Điều kiện (1) của OI-CP7-01 chưa đạt nên không chạy TTS, aligner, đo tốc độ nói hay đo VRAM. Không ghi PASS cho bất kỳ mục nào.

## Kết quả

RG-05.weights_pinned: BLOCKED
RG-05.tts_valid_wav: NOT_OBSERVED
RG-05.aligner_unmatched: NOT_OBSERVED
RG-05.aligner_timing: NOT_OBSERVED
RG-05.speech_rate_calibrated: NOT_OBSERVED
RG-05.vram_peak: NOT_OBSERVED
RG-05.secret_scan: NOT_OBSERVED

## Bằng chứng BLOCKED

- tools/launcher/prod/model-weights.lock.json: 6 mục (kokoro-v1.0.onnx, voices-v1.0.bin, config.json, model.bin, tokenizer.json, vocabulary.txt) đều có status BLOCKED và sha256 null; commit Hugging Face của faster-whisper small.en cũng null.
- Probe chỉ đọc kiểm status PINNED và sha256 khác rỗng cho từng mục: thoát khác 0, liệt kê đủ 6 tên tệp.
- Thư mục LOCALAPPDATA/AIAutoVideoCreator/models chưa tồn tại khi Orchestrator lập lệnh.
- Theo docs/implementation/cp7/plan.md (OI-CP7-01): Control ghi hash trước CP7-6; thiếu thì CP7-6 BLOCKED, không bịa hash.

## Việc Control cần làm để mở khoá

- Tải trọng số vào LOCALAPPDATA/AIAutoVideoCreator/models (ngoài cây Git), tính sha256 từng tệp, điền commit Hugging Face của Systran/faster-whisper-small.en, rồi ghi sha256 và status PINNED vào tools/launcher/prod/model-weights.lock.json (tệp ngoài owned paths của CP7-6).
- Xác nhận kokoro-onnx và faster-whisper có trong runtime khoá của lane (hiện Orchestrator không thấy trong site-packages của interpreter khoá).
- Sau đó Orchestrator lập lại lệnh làm việc cho CP7-6 để viết tests/real/test_cp7_voice_real.py và chạy đo thật.

## Giới hạn

- Slice không sửa lock, không sửa src/**, không sửa profile cấu hình, không tải trọng số vào cây Git.
- Không chép mẫu khoá bí mật vào báo cáo.
