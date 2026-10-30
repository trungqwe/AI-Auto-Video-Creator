# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, sau khi rebase lên 9f75162dd199db0bd192309fe2a4b4bc83f8af3e, đo qua đường giải mã production với av==18.1.0.

Trạng thái: 6/7 mục PASS, 1/7 mục BLOCKED. Runtime khoá 8715e538 đã cài đặt đúng av==18.1.0 khớp pyproject.toml; đường giải mã production faster_whisper.decode_audio đo thật thành công (aligner_unmatched đạt 25/25 đoạn PASS). Riêng mục aligner_timing chưa đạt ngưỡng 95% do số đo thực tế đạt 85/110 câu (77.3%), giữ BLOCKED kèm nguyên nhân đo thật để Control xử lý.

## Kết quả

RG-05.weights_pinned: PASS
RG-05.tts_valid_wav: PASS
RG-05.aligner_unmatched: PASS
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
- tts_valid_wav: synth_latency_ms_max=13190 total_audio_s=762.9
- aligner_unmatched: passages_ok=25/25 cap=0.05 max_ratio=0.0476 aligner_errors=[]
- aligner_unmatched: ratio_by_passage={"dialogue-00": 0.0, "dialogue-01": 0.0, "dialogue-02": 0.0476, "dialogue-03": 0.0, "dialogue-04": 0.0, "dialogue-05": 0.0, "dialogue-06": 0.0, "dialogue-07": 0.0, "dialogue-08": 0.0, "dialogue-09": 0.0, "dialogue-10": 0.0, "dialogue-11": 0.0, "dialogue-12": 0.0, "dialogue-13": 0.0, "dialogue-14": 0.0, "dialogue-15": 0.0, "dialogue-16": 0.0, "dialogue-17": 0.0, "dialogue-18": 0.0, "dialogue-19": 0.0, "script-20": 0.0, "script-21": 0.0032, "script-22": 0.0029, "script-23": 0.0, "script-24": 0.0}
- aligner_unmatched: audio=voice + music -20.0 dB + 3 SFX at -12.0 dB; aligner device=cpu
- aligner_unmatched: model=real faster-whisper small.en weights pinned; audio decoded by the production path (faster_whisper.decode_audio inside RealWhisperAligner, no test-side decode) with av==18.1.0; adapter unchanged
- aligner_timing: diag signed start_delta_ms p10/p50/p90=-148/24/96 end_delta_ms p10/p50/p90=-45/50/106 scored=110/110
- aligner_timing: diag spans_sentences_margin_ms_by_passage={"dialogue-00": [2, 2, [683, 341]], "dialogue-01": [2, 2, [729, 360]], "dialogue-02": [2, 2, [708, 367]], "dialogue-03": [2, 2, [625, 389]], "dialogue-04": [2, 2, [658, 286]], "dialogue-05": [2, 2, [774, 390]], "dialogue-06": [2, 2, [806, 383]], "dialogue-07": [2, 2, [669, 377]], "dialogue-08": [2, 2, [762, 340]], "dialogue-09": [2, 2, [647, 370]], "dialogue-10": [3, 3, [695, 395]], "dialogue-11": [3, 3, [698, 380]], "dialogue-12": [3, 3, [634, 403]], "dialogue-13": [3, 3, [728, 394]], "dialogue-14": [3, 3, [662, 407]], "dialogue-15": [3, 3, [666, 407]], "dialogue-16": [3, 3, [698, 431]], "dialogue-17": [3, 3, [722, 400]], "dialogue-18": [3, 3, [709, 402]], "dialogue-19": [3, 3, [720, 438]], "script-20": [12, 12, [180, 371]], "script-21": [12, 12, [338, 428]], "script-22": [12, 12, [203, 462]], "script-23": [12, 12, [103, 392]], "script-24": [12, 12, [222, 767]]}
- aligner_timing: diag deltas_ms_by_passage={"dialogue-00": [[64, 31], [52, 0]], "dialogue-01": [[288, 116], [27, 0]], "dialogue-02": [[32, 72], [36, 106]], "dialogue-03": [[192, 45], [-4, 0]], "dialogue-04": [[32, 58], [8, 143]], "dialogue-05": [[32, 21], [15, 0]], "dialogue-06": [[32, 66], [-4, 100]], "dialogue-07": [[32, 42], [13, 0]], "dialogue-08": [[64, 77], [115, 105]], "dialogue-09": [[64, 40], [65, 0]], "dialogue-10": [[128, 59], [22, 41], [82, 126]], "dialogue-11": [[32, 57], [7, 53], [-5, 0]], "dialogue-12": [[96, 68], [10, 59], [34, 0]], "dialogue-13": [[96, 150], [94, 64], [-5, 0]], "dialogue-14": [[64, 46], [24, 50], [5, 0]], "dialogue-15": [[64, 53], [27, 95], [-3, 0]], "dialogue-16": [[64, 93], [18, 44], [18, 0]], "dialogue-17": [[32, 52], [2, 60], [54, 0]], "dialogue-18": [[32, 72], [35, 51], [25, 112]], "dialogue-19": [[32, 31], [0, 47], [-1, 0]], "script-20": [[32, 37], [115, 28], [55, 44], [-2, 1361], [1142, 63], [7, 45], [39, 57], [14, 275], [95, 40], [-10, 55], [6, 43], [13, 0]], "script-21": [[32, 42], [18, 53], [78, 27], [47, 2404], [2025, 72], [3, 94], [5, 59], [52, -1627], [-1965, 70], [5, 13], [24, 52], [38, 0]], "script-22": [[160, 69], [15, 51], [4, 64], [-11, 1544], [1284, 67], [26, 75], [3, 50], [45, -971], [-1174, 52], [14, 49], [5, 16], [11, 0]], "script-23": [[32, 54], [25, 30], [2, 74], [2, -45], [-148, 44], [21, 55], [6, 74], [24, -1346], [-1572, 57], [73, 95], [53, 70], [19, 111]], "script-24": [[32, 50], [16, 44], [17, 60], [-3, -2240], [-2594, -2995], [-2707, -2861], [-2475, -3464], [-3305, -2600], [-2915, -4529], [-4315, -4375], [-4074, -2192], [-1847, 0]]}
- aligner_timing: diag sentences_ok_by_reference_noise_db={"-40": 83, "-35": 83, "-30": 85} primary_db=-30 total=110
- aligner_timing: diag clean_voice_rms_dbfs_median=-22.5
- aligner_timing: diag clean_voice_sentences_ok=83/110 (same aligner and same reference on the voice without music and SFX; diagnostic only, not the verdict)
- aligner_timing: diag gap_midpoint_within_tolerance=70/85 (mean of end delta of sentence n and start delta of sentence n+1; diagnostic only, not the verdict)
- speech_rate_calibrated: suggested_speech_rate_wpm=122 within_10pct=25/25 max_deviation=0.069
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1338 limit_mib=11264 samples=277 interval=1s first_mib=1324 elapsed_s=291
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Phương pháp mốc tham chiếu

Mốc tham chiếu được xác định trực tiếp trên file âm thanh giọng sạch (clean voice) bằng công cụ FFmpeg silencedetect đã ghim (sha256 theo runtime.lock.json). Ranh giới giữa các câu được chọn là khoảng im dài nhất nằm trong cửa sổ ±35% (tối thiểu 1000 ms) quanh vị trí kỳ vọng suy từ tỉ lệ số ký tự của các câu còn lại (tính lại sau mỗi lần cắt); độc lập với aligner. Điểm bắt đầu câu đầu tiên được tính từ cuối khoảng im đầu file (nếu có); điểm kết thúc câu cuối cùng được tính từ đầu khoảng im cuối file (nếu khoảng im này kết thúc sát độ dài file trong phạm vi dung sai 50 ms). Toàn bộ quá trình tạo mốc tham chiếu hoàn toàn độc lập với kết quả của aligner.

## Đường giải mã

Đã đo qua đường giải mã production của RealWhisperAligner (faster_whisper.decode_audio) với av==18.1.0 trên runtime khoá 8715e538 sau khi rebase lên integration head 9f75162dd199db0bd192309fe2a4b4bc83f8af3e. Guard assertion kiểm tra av==18.1.0 đạt chuẩn hoàn toàn. Toàn bộ 25 đoạn audio được giải mã trực tiếp qua faster_whisper.decode_audio bên trong RealWhisperAligner thật mà không có bất kỳ đường giải mã thay thế nào và không monkeypatch.

## Phân tích aligner_timing

Kết quả đo đạc độ lệch thời gian mốc câu giữa aligner faster-whisper và mốc tham chiếu silencedetect trên runtime khoá có av==18.1.0:
- Tỷ lệ câu đạt chuẩn (|start_delta| <= 150 ms và |end_delta| <= 150 ms): 85/110 câu (77.3%), chưa đạt ngưỡng yêu cầu 95% (tuy đã tăng đáng kể so với các lượt trước).
- Phân vị độ lệch bắt đầu câu: p10 = -148 ms, p50 = 24 ms, p90 = 96 ms.
- Phân vị độ lệch kết thúc câu: p10 = -45 ms, p50 = 50 ms, p90 = 106 ms.
- Trên 20 đoạn thoại ngắn (dialogue-00..19), 48/50 câu (96.0%) đạt dung sai 150 ms. Trên 5 kịch bản dài (script-20..24), độ lệch mốc câu tại các đoạn văn bản dài đạt 37/60 câu (61.7%) do sai lệch vị trí khoảng ngắt câu của thuật toán tham chiếu hoặc đặc tính mô hình.
- Do quy định lệnh làm việc không sửa test, không sửa src/voice/adapters hay profile, Worker giữ nguyên trạng thái đo thực tế trung thực và báo cáo BLOCKED để Control / Orchestrator xử lý.

## Giới hạn

Không sửa profile cấu hình, không sửa src/**, chi phí 0 USD, aligner chạy trên thiết bị theo profile.
