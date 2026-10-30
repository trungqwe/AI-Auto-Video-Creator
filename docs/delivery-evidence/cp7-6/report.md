# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, trên mã đã rebase lên đầu tích hợp c6f2810de95036eda8b6b8b76dd4f3e5d736fce1 (kết quả của lượt trước không còn dùng).

Trạng thái: 6/7 mục PASS, 1/7 mục BLOCKED. Đo qua đường giải mã production faster_whisper.decode_audio với av==18.1.0 và trọng số đã ghim. Mục aligner_timing đo được 101/110 câu (91.8%) đạt dung sai 150 ms, nhưng chưa đạt ngưỡng nghiệm thu 95% (tối thiểu 105/110 câu). Worker giữ nguyên trạng thái đo thực tế trung thực và báo cáo BLOCKED để Control và Orchestrator xem xét.

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
- tts_valid_wav: words_and_actual_duration_ms={"dialogue-00": [24, 11541], "dialogue-01": [22, 10858], "dialogue-02": [21, 10944], "dialogue-03": [22, 11306], "dialogue-04": [23, 10581], "dialogue-05": [26, 13376], "dialogue-06": [26, 13013], "dialogue-07": [27, 12565], "dialogue-08": [26, 12778], "dialogue-09": [26, 12778], "dialogue-10": [46, 21184], "dialogue-11": [47, 22976], "dialogue-12": [46, 21888], "dialogue-13": [48, 24277], "dialogue-14": [47, 22570], "dialogue-15": [51, 24938], "dialogue-16": [53, 25344], "dialogue-17": [51, 24405], "dialogue-18": [51, 23808], "dialogue-19": [51, 24896], "script-20": [155, 80734], "script-21": [159, 82183], "script-22": [169, 83361], "script-23": [163, 82191], "script-24": [167, 82712]}
- tts_valid_wav: synth_latency_ms_max=14177 total_audio_s=767.2
- aligner_unmatched: passages_ok=25/25 cap=0.05 max_ratio=0.0476 aligner_errors=[]
- aligner_unmatched: ratio_by_passage={"dialogue-00": 0.0, "dialogue-01": 0.0, "dialogue-02": 0.0476, "dialogue-03": 0.0, "dialogue-04": 0.0, "dialogue-05": 0.0, "dialogue-06": 0.0, "dialogue-07": 0.0, "dialogue-08": 0.0, "dialogue-09": 0.0, "dialogue-10": 0.0, "dialogue-11": 0.0, "dialogue-12": 0.0, "dialogue-13": 0.0, "dialogue-14": 0.0, "dialogue-15": 0.0, "dialogue-16": 0.0, "dialogue-17": 0.0, "dialogue-18": 0.0, "dialogue-19": 0.0, "script-20": 0.0, "script-21": 0.0032, "script-22": 0.0059, "script-23": 0.0, "script-24": 0.0}
- aligner_unmatched: audio=voice + music -20.0 dB + 3 SFX at -12.0 dB; aligner device=cpu
- aligner_unmatched: model=real faster-whisper small.en weights pinned; audio decoded by the production path (faster_whisper.decode_audio inside RealWhisperAligner, no test-side decode) with av==18.1.0; adapter unchanged
- aligner_timing: diag signed start_delta_ms p10/p50/p90=32/52/106 end_delta_ms p10/p50/p90=-44/-10/88 scored=110/110
- aligner_timing: diag spans_sentences_lead_trail_ms_by_passage={"dialogue-00": [2, 2, [0, 1]], "dialogue-01": [2, 2, [0, 1]], "dialogue-02": [2, 2, [0, 147]], "dialogue-03": [2, 2, [0, 0]], "dialogue-04": [2, 2, [0, 148]], "dialogue-05": [2, 2, [0, 0]], "dialogue-06": [2, 2, [0, 0]], "dialogue-07": [2, 2, [0, 0]], "dialogue-08": [2, 2, [0, 104]], "dialogue-09": [2, 2, [0, 0]], "dialogue-10": [3, 3, [0, 111]], "dialogue-11": [3, 3, [0, 0]], "dialogue-12": [3, 3, [0, 1]], "dialogue-13": [3, 3, [0, 113]], "dialogue-14": [3, 3, [0, 0]], "dialogue-15": [3, 3, [0, 1]], "dialogue-16": [3, 3, [0, 1]], "dialogue-17": [3, 3, [0, 1]], "dialogue-18": [3, 3, [0, 141]], "dialogue-19": [3, 3, [0, 1]], "script-20": [12, 12, [0, 0]], "script-21": [12, 12, [0, 0]], "script-22": [12, 12, [0, 0]], "script-23": [12, 12, [0, 125]], "script-24": [12, 12, [0, 0]]}
- aligner_timing: diag deltas_ms_by_passage={"dialogue-00": [[64, 43], [74, -203]], "dialogue-01": [[288, 16], [42, 1]], "dialogue-02": [[32, 44], [63, 147]], "dialogue-03": [[192, -21], [63, 0]], "dialogue-04": [[32, -10], [42, 148]], "dialogue-05": [[32, 34], [84, 0]], "dialogue-06": [[32, 38], [52, 0]], "dialogue-07": [[32, -32], [84, 0]], "dialogue-08": [[64, 91], [84, 104]], "dialogue-09": [[32, -32], [52, 0]], "dialogue-10": [[128, 77], [31, -43], [72, 111]], "dialogue-11": [[32, 82], [84, -12], [40, 0]], "dialogue-12": [[96, -21], [31, -22], [62, 1]], "dialogue-13": [[64, 56], [106, -11], [72, 113]], "dialogue-14": [[32, -32], [52, -44], [40, 0]], "dialogue-15": [[64, -42], [42, -54], [94, 1]], "dialogue-16": [[64, 72], [31, -22], [30, 1]], "dialogue-17": [[64, 61], [42, 54], [94, 1]], "dialogue-18": [[32, 56], [52, 80], [94, 141]], "dialogue-19": [[32, -32], [212, -33], [51, 1]], "script-20": [[96, -53], [127, -150], [94, -12], [39, -35], [48, -26], [58, -27], [88, -18], [66, 90], [86, -10], [42, -54], [30, -175], [92, 0]], "script-21": [[32, -21], [63, -1], [115, -34], [50, 198], [38, -36], [47, 60], [56, 17], [98, -40], [43, 57], [42, -11], [40, -13], [71, 0]], "script-22": [[160, -32], [52, -33], [51, -45], [39, -151], [48, -48], [36, -17], [35, -39], [44, -20], [32, 71], [106, 76], [51, -23], [60, 0]], "script-23": [[64, -32], [52, -33], [51, 88], [50, -119], [48, -37], [79, -27], [88, 40], [55, 52], [43, -21], [127, 78], [104, 52], [50, 125]], "script-24": [[32, -21], [63, -43], [40, -34], [6, 56], [38, 63], [90, -27], [56, -18], [34, -212], [43, -42], [138, -11], [40, 88], [39, 0]]}
- aligner_timing: diag sentences_ok_by_reference_noise_db={"-40": 102, "-35": 102, "-30": 101} primary_db=-30 total=110
- aligner_timing: diag clean_voice_rms_dbfs_median=-22.5
- aligner_timing: diag gap_midpoint_within_tolerance=85/85 (mean of end delta of sentence n and start delta of sentence n+1; diagnostic only, not the verdict)
- speech_rate_calibrated: suggested_speech_rate_wpm=121 within_10pct=25/25 max_deviation=0.078
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1622 limit_mib=11264 samples=421 interval=1s first_mib=1519 elapsed_s=447
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Phương pháp mốc tham chiếu

Mốc câu được đo trên âm thanh ghép từ các clip Kokoro thật do RealKokoroTts tổng hợp riêng từng câu, ghép cách nhau 300 ms im lặng số rồi trộn nhạc nền -20 dB và 3 SFX -12 dB. Mốc tham chiếu mỗi câu = đầu/cuối tiếng nói do silencedetect của FFmpeg ghim (sha256 theo runtime.lock.json) đo trên clip riêng của câu đó cộng offset ghép; ranh giới câu xác định chính xác theo cách dựng, không phỏng đoán từ độ dài văn bản, hoàn toàn độc lập với aligner. Các mục tts_valid_wav, aligner_unmatched và speech_rate vẫn đo trên âm thanh cả đoạn như trước. Giới hạn trung thực: âm thanh dùng đo timing là âm thanh ghép từ từng câu độc lập, không phải một lượt tổng hợp liền mạch duy nhất.

## Đường giải mã

Đã đo qua đường giải mã production của RealWhisperAligner (faster_whisper.decode_audio) với av==18.1.0 trên runtime khoá 8715e538 sau khi rebase lên integration head c6f2810de95036eda8b6b8b76dd4f3e5d736fce1. Guard assertion kiểm tra av==18.1.0 đạt chuẩn hoàn toàn. Toàn bộ 25 đoạn audio được giải mã trực tiếp qua faster_whisper.decode_audio bên trong RealWhisperAligner thật mà không có bất kỳ đường giải mã thay thế nào và không monkeypatch.

## Phân tích aligner_timing

Ở lượt đo mới trên mã đã rebase lên c6f2810de95036eda8b6b8b76dd4f3e5d736fce1 với mốc tham chiếu ghép từng câu:
- Tỷ lệ câu đạt chuẩn (|start_delta| <= 150 ms và |end_delta| <= 150 ms): 101/110 câu (91.8%), chưa đạt ngưỡng nghiệm thu 95% (tối thiểu 105/110 câu).
- Phân vị độ lệch bắt đầu câu: p10 = 32 ms, p50 = 52 ms, p90 = 106 ms.
- Phân vị độ lệch kết thúc câu: p10 = -44 ms, p50 = -10 ms, p90 = 88 ms.
- Số câu đạt theo từng ngưỡng noise silencedetect: noise -40 dB đạt 102/110 câu; noise -35 dB đạt 102/110 câu; noise -30 dB (ngưỡng chính) đạt 101/110 câu.
- Cụ thể có 9 câu không đạt dung sai 150 ms: dialogue-00 câu 2 ([74, -203]), dialogue-01 câu 1 ([288, 16]), dialogue-03 câu 1 ([192, -21]), dialogue-19 câu 2 ([212, -33]), script-20 câu 11 ([30, -175]), script-21 câu 4 ([50, 198]), script-22 câu 1 ([160, -32]), script-22 câu 4 ([39, -151]), script-24 câu 8 ([34, -212]).
- Do quy định lệnh làm việc không sửa test, không sửa src/voice/adapters, không sửa profile hay hạ ngưỡng nghiệm thu, Worker ghi nhận số đo thực tế trung thực và giữ trạng thái BLOCKED để Control / Orchestrator xử lý tiếp.

## Giới hạn

Không sửa profile cấu hình, không sửa src/**, chi phí 0 USD, aligner chạy trên thiết bị theo profile.
