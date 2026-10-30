# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, sau khi cập nhật mốc tham chiếu ranh giới câu bằng khoảng im dài nhất trong cửa sổ quanh vị trí kỳ vọng theo tỉ lệ độ dài văn bản (CUT_WINDOW_FRACTION=0.35, CUT_WINDOW_MIN_MS=1000) từ FFmpeg silencedetect (-30 dB, d=0.1 s).

Trạng thái: 6/7 mục PASS, riêng mục aligner_timing FAIL do số đo thực tế đạt 44/110 câu (40.0%), chưa đạt ngưỡng yêu cầu 95%.

## Kết quả

RG-05.weights_pinned: PASS
RG-05.tts_valid_wav: PASS
RG-05.aligner_unmatched: PASS
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
- tts_valid_wav: synth_latency_ms_max=16538 total_audio_s=762.9
- aligner_unmatched: passages_ok=24/25 cap=0.05 max_ratio=0.0952 aligner_errors=[]
- aligner_unmatched: ratio_by_passage={"dialogue-00": 0.0, "dialogue-01": 0.0455, "dialogue-02": 0.0952, "dialogue-03": 0.0, "dialogue-04": 0.0435, "dialogue-05": 0.0385, "dialogue-06": 0.0, "dialogue-07": 0.037, "dialogue-08": 0.0385, "dialogue-09": 0.0, "dialogue-10": 0.0, "dialogue-11": 0.0213, "dialogue-12": 0.0323, "dialogue-13": 0.0, "dialogue-14": 0.0213, "dialogue-15": 0.0196, "dialogue-16": 0.0, "dialogue-17": 0.0, "dialogue-18": 0.0196, "dialogue-19": 0.0, "script-20": 0.0194, "script-21": 0.0158, "script-22": 0.0118, "script-23": 0.0184, "script-24": 0.0328}
- aligner_unmatched: audio=voice + music -20.0 dB + 3 SFX at -12.0 dB; aligner device=cpu
- aligner_unmatched: model=real faster-whisper small.en weights pinned; audio decoded by pinned ffmpeg to 16 kHz float32 mono because av==19.0.2 breaks faster_whisper.decode_audio (adapter unchanged)
- aligner_timing: diag signed start_delta_ms p10/p50/p90=-148/67/397 end_delta_ms p10/p50/p90=-424/-103/-4 scored=110/110
- aligner_timing: diag spans_sentences_margin_ms_by_passage={"dialogue-00": [2, 2, [683, 341]], "dialogue-01": [2, 2, [729, 360]], "dialogue-02": [2, 2, [708, 367]], "dialogue-03": [2, 2, [625, 389]], "dialogue-04": [2, 2, [658, 286]], "dialogue-05": [2, 2, [774, 390]], "dialogue-06": [2, 2, [806, 383]], "dialogue-07": [2, 2, [669, 377]], "dialogue-08": [2, 2, [762, 340]], "dialogue-09": [2, 2, [647, 370]], "dialogue-10": [3, 3, [695, 395]], "dialogue-11": [3, 3, [698, 380]], "dialogue-12": [3, 3, [634, 403]], "dialogue-13": [3, 3, [728, 394]], "dialogue-14": [3, 3, [662, 407]], "dialogue-15": [3, 3, [666, 407]], "dialogue-16": [3, 3, [698, 431]], "dialogue-17": [3, 3, [722, 400]], "dialogue-18": [3, 3, [709, 402]], "dialogue-19": [3, 3, [720, 438]], "script-20": [12, 12, [180, 371]], "script-21": [12, 12, [338, 428]], "script-22": [12, 12, [203, 462]], "script-23": [12, 12, [103, 392]], "script-24": [12, 12, [222, 767]]}
- aligner_timing: diag deltas_ms_by_passage={"dialogue-00": [[0, -97], [140, -281]], "dialogue-01": [[0, -4], [227, -338]], "dialogue-02": [[0, -92], [180, -18]], "dialogue-03": [[0, -119], [76, -346]], "dialogue-04": [[0, -134], [328, -78]], "dialogue-05": [[0, 13], [439, -216]], "dialogue-06": [[0, -26], [-12, -173]], "dialogue-07": [[0, -34], [397, -245]], "dialogue-08": [[0, -7], [431, -193]], "dialogue-09": [[0, -192], [161, -298]], "dialogue-10": [[0, -33], [-18, -79], [186, -58]], "dialogue-11": [[0, -19], [399, -267], [95, -296]], "dialogue-12": [[0, -152], [-6, -85], [90, -308]], "dialogue-13": [[0, -54], [98, -100], [67, -197]], "dialogue-14": [[0, -150], [-52, -142], [433, -290]], "dialogue-15": [[0, -163], [31, -49], [285, -378]], "dialogue-16": [[0, -47], [-78, -48], [134, -284]], "dialogue-17": [[0, -76], [-18, -80], [126, -305]], "dialogue-18": [[0, -16], [215, -45], [53, -176]], "dialogue-19": [[0, -13], [112, -121], [59, -256]], "script-20": [[0, -15], [367, 0], [71, -120], [106, 1381], [1742, -61], [419, -215], [59, -75], [94, 15], [95, -216], [106, -53], [130, -109], [89, -289]], "script-21": [[0, -46], [74, -235], [458, -89], [11, 2144], [1985, -72], [335, -10], [89, 11], [128, -1987], [-1965, -50], [25, -123], [384, -352], [94, -424]], "script-22": [[0, -39], [103, -85], [0, -152], [305, 1544], [1284, -1], [282, -177], [23, -38], [297, -1331], [-1534, -92], [178, 17], [153, -120], [-113, -337]], "script-23": [[0, -66], [381, -26], [98, -46], [-14, -45], [-148, -108], [69, -49], [346, -58], [-8, -1706], [-1932, -103], [173, -5], [117, -66], [483, -110]], "script-24": [[0, -154], [356, -160], [37, -4], [81, -2480], [-2594, -3171], [-2375, -3157], [-2039, -3688], [-3289, -3760], [-2915, -4665], [-4171, -4539], [-3966, -2280], [-1831, -254]]}
- aligner_timing: diag sentences_ok_by_reference_noise_db={"-40": 40, "-35": 41, "-30": 44} primary_db=-30 total=110
- aligner_timing: diag clean_voice_rms_dbfs_median=-22.5
- aligner_timing: diag clean_voice_sentences_ok=41/110 (same aligner and same reference on the voice without music and SFX; diagnostic only, not the verdict)
- aligner_timing: diag gap_midpoint_within_tolerance=63/85 (mean of end delta of sentence n and start delta of sentence n+1; diagnostic only, not the verdict)
- speech_rate_calibrated: suggested_speech_rate_wpm=122 within_10pct=25/25 max_deviation=0.069
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1088 limit_mib=11264 samples=324 interval=1s first_mib=1072 elapsed_s=345
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Phương pháp mốc tham chiếu

Mốc tham chiếu được xác định trực tiếp trên file âm thanh giọng sạch (clean voice) bằng công cụ FFmpeg silencedetect đã ghim (sha256 theo runtime.lock.json). Ranh giới giữa các câu được chọn là khoảng im dài nhất nằm trong cửa sổ ±35% (tối thiểu 1000 ms) quanh vị trí kỳ vọng suy từ tỉ lệ số ký tự của các câu còn lại (tính lại sau mỗi lần cắt); độc lập với aligner. Điểm bắt đầu câu đầu tiên được tính từ cuối khoảng im đầu file (nếu có); điểm kết thúc câu cuối cùng được tính từ đầu khoảng im cuối file (nếu khoảng im này kết thúc sát độ dài file trong phạm vi dung sai 50 ms). Toàn bộ quá trình tạo mốc tham chiếu hoàn toàn độc lập với kết quả của aligner.

Trước đây, phương pháp cũ chọn (số câu − 1) khoảng im dài nhất toàn cục chỉ đạt 37/110 câu đạt chuẩn và mắc lỗi nghiêm trọng ở 5 kịch bản 12 câu (script-20..24) do margin phân tách giữa các khoảng im rất nhỏ (354 ms so với 352 ms, 391 ms so với 385 ms, 396 ms so với 394 ms), khiến việc chọn toàn cục bị cắt nhầm sang chỗ ngắt hơi nội câu và làm lệch dây chuyền toàn bộ các câu phía sau hàng giây. Ngưỡng phát hiện khoảng im REFERENCE_NOISE_DB = -30 dB (d=0.1 s) được ấn định sau khi đã xem chẩn đoán ở lượt trước. Hai hằng số CUT_WINDOW_FRACTION = 0.35 và CUT_WINDOW_MIN_MS = 1000 được khai báo trước lần chạy này và không chỉnh lại sau khi thấy kết quả. Dung sai thời gian 150 ms và tỷ lệ đạt yêu cầu 95% được giữ nguyên tuyệt đối.

## Phân tích aligner_timing

Kết quả đo đạc độ lệch có dấu giữa mốc thời gian của aligner và mốc silencedetect tham chiếu:
- Phân vị độ lệch bắt đầu câu (start_delta_ms): p10 = -148 ms, p50 (trung vị) = 67 ms, p90 = 397 ms.
- Phân vị độ lệch kết thúc câu (end_delta_ms): p10 = -424 ms, p50 (trung vị) = -103 ms, p90 = -4 ms.
- Tỷ lệ câu đạt chuẩn (|start_delta| <= 150 ms và |end_delta| <= 150 ms): 44/110 câu (40.0%), chưa đạt ngưỡng yêu cầu 95% (tuy đã tăng so với 37/110 câu ở lượt trước).
- Chẩn đoán độ nhạy theo ngưỡng khoảng im:
  + Tại -40 dB: 40/110 câu đạt chuẩn.
  + Tại -35 dB: 41/110 câu đạt chuẩn.
  + Tại -30 dB (ngưỡng chính): 44/110 câu đạt chuẩn.
- Chẩn đoán bổ sung (chỉ để xem, không thay phán quyết):
  + clean_voice_sentences_ok: 41/110 câu đạt chuẩn trên giọng sạch không có nhạc nền và SFX (cùng aligner và cùng mốc tham chiếu). Kết quả này cho thấy trên giọng sạch hoàn toàn không bị nhiễu âm thanh, tỷ lệ đạt chuẩn (41/110) cũng tương đương giọng có nhạc nền và SFX (44/110).
  + gap_midpoint_within_tolerance: 63/85 ranh giới câu (74.1%) có điểm giữa khe nghỉ giữa hai câu liên tiếp (trung bình cộng giữa end_delta của câu n và start_delta của câu n+1) nằm trong dung sai 150 ms.
- Nhận định về sai lệch hệ thống:
  1. Phương pháp cửa sổ theo độ dài văn bản đã giải quyết được lỗi cắt nhầm khoảng ngắt hơi toàn cục ở các kịch bản dài (độ lệch tích lũy giảm rõ rệt so với mức lệch âm -14 giây của lượt trước; nhiều câu trong script-20..23 đã rơi về phạm vi vài chục đến vài trăm ms).
  2. Tuy nhiên, ở các đoạn thoại ngắn và các câu đơn lẻ, mốc đầu câu sau thường có xu hướng muộn (p50 = 67 ms, p90 = 397 ms) và mốc cuối câu thường sớm hơn silencedetect (p50 = -103 ms, p10 = -424 ms). Đây là đặc tính căn bản của thuật toán gán nhãn thời gian từ (word timestamp alignment) của mô hình faster-whisper small.en trong src/voice/adapters/real_whisper_aligner.py (ngoài owned paths).
  3. Vì nguyên nhân còn lại nằm ở mô hình và adapter của phân hệ voice (ngoài owned paths của CP7-6), Worker không thể tự ý khắc phục bằng cách nới dung sai hay sửa adapter. Cần quyết định từ Control và Orchestrator (đổi cấu hình mô hình aligner, bổ sung thuật toán hậu xử lý mốc câu, hoặc điều chỉnh tiêu chí nghiệm thu) để giải quyết dứt điểm.

## Cách xử lý tương thích av

Runtime khoá có av==19.0.2, faster_whisper/audio.py:46 gọi av.open(..., metadata_errors='ignore') gây TypeError; adapter src/voice/adapters/real_whisper_aligner.py không bị sửa; test giải mã WAV bằng FFmpeg ghim (sha256 theo runtime.lock.json) thành float32 16 kHz mono rồi đưa cho WhisperModel thật qua model_factory; đề xuất Control đưa vào backlog việc ghim av tương thích hoặc cho adapter tự giải mã (ngoài phạm vi CP7-6).

## Giới hạn

Không sửa profile cấu hình, không sửa src/**, chi phí 0 USD, aligner chạy trên cpu theo profile.
