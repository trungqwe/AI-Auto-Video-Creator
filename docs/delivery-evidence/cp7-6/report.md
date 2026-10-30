# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, sau khi hiệu chỉnh mốc tham chiếu silencedetect trên giọng sạch bằng lưới cố định REFERENCE_GRID ghép theo thứ tự câu.

Trạng thái: 6/7 mục PASS, riêng mục aligner_timing FAIL do số đo thực tế không đạt ngưỡng 95% (đo được 21/110 câu đạt độ lệch <= 150 ms).

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
- tts_valid_wav: synth_latency_ms_max=13025 total_audio_s=762.9
- aligner_unmatched: passages_ok=24/25 cap=0.05 max_ratio=0.0952 aligner_errors=[]
- aligner_unmatched: ratio_by_passage={"dialogue-00": 0.0, "dialogue-01": 0.0455, "dialogue-02": 0.0952, "dialogue-03": 0.0, "dialogue-04": 0.0435, "dialogue-05": 0.0385, "dialogue-06": 0.0, "dialogue-07": 0.037, "dialogue-08": 0.0385, "dialogue-09": 0.0, "dialogue-10": 0.0, "dialogue-11": 0.0213, "dialogue-12": 0.0323, "dialogue-13": 0.0, "dialogue-14": 0.0213, "dialogue-15": 0.0196, "dialogue-16": 0.0, "dialogue-17": 0.0, "dialogue-18": 0.0196, "dialogue-19": 0.0, "script-20": 0.0194, "script-21": 0.0158, "script-22": 0.0118, "script-23": 0.0184, "script-24": 0.0328}
- aligner_unmatched: audio=voice + music -20.0 dB + 3 SFX at -12.0 dB; aligner device=cpu
- aligner_unmatched: model=real faster-whisper small.en weights pinned; audio decoded by pinned ffmpeg to 16 kHz float32 mono because av==19.0.2 breaks faster_whisper.decode_audio (adapter unchanged)
- aligner_timing: diag signed start_delta_ms p10/p50/p90=-3490/0/370 end_delta_ms p10/p50/p90=-308/-87/3661 scored=110/110
- aligner_timing: diag spans_sentences_ref_by_passage={"dialogue-00": [2, 2, "-40dB/0.4s"], "dialogue-01": [2, 2, "-40dB/0.4s"], "dialogue-02": [2, 2, "-40dB/0.4s"], "dialogue-03": [2, 2, "-40dB/0.4s"], "dialogue-04": [2, 2, "-40dB/0.3s"], "dialogue-05": [2, 2, "-40dB/0.4s"], "dialogue-06": [2, 2, "-40dB/0.4s"], "dialogue-07": [2, 2, "-40dB/0.4s"], "dialogue-08": [2, 2, "-40dB/0.4s"], "dialogue-09": [2, 2, "-40dB/0.4s"], "dialogue-10": [3, 3, "-40dB/0.4s"], "dialogue-11": [3, 3, "-40dB/0.4s"], "dialogue-12": [3, 3, "-40dB/0.4s"], "dialogue-13": [3, 3, "-40dB/0.4s"], "dialogue-14": [3, 3, "-40dB/0.4s"], "dialogue-15": [3, 3, "-40dB/0.4s"], "dialogue-16": [9, 3, "-40dB/0.15s"], "dialogue-17": [3, 3, "-40dB/0.4s"], "dialogue-18": [3, 3, "-40dB/0.4s"], "dialogue-19": [3, 3, "-40dB/0.4s"], "script-20": [31, 12, "-40dB/0.15s"], "script-21": [31, 12, "-40dB/0.15s"], "script-22": [30, 12, "-40dB/0.15s"], "script-23": [31, 12, "-40dB/0.15s"], "script-24": [32, 12, "-40dB/0.15s"]}
- aligner_timing: diag deltas_ms_by_passage={"dialogue-00": [[0, -106], [141, -281]], "dialogue-01": [[0, -38], [279, -338]], "dialogue-02": [[0, -131], [180, -124]], "dialogue-03": [[0, -128], [77, -346]], "dialogue-04": [[0, -148], [331, -221]], "dialogue-05": [[0, -16], [484, -216]], "dialogue-06": [[0, -55], [-3, -273]], "dialogue-07": [[0, -52], [400, -245]], "dialogue-08": [[0, -15], [431, -298]], "dialogue-09": [[0, -201], [164, -298]], "dialogue-10": [[0, -73], [-18, -88], [191, -184]], "dialogue-11": [[0, -40], [402, -276], [95, -296]], "dialogue-12": [[0, -165], [-5, -93], [90, -308]], "dialogue-13": [[0, -85], [98, -113], [68, -197]], "dialogue-14": [[0, -161], [-52, -151], [434, -290]], "dialogue-15": [[0, -171], [34, -56], [316, -378]], "dialogue-16": [[-1198, 1488], [-2048, 2030], [136, 4422]], "dialogue-17": [[0, -93], [-16, -102], [126, -305]], "dialogue-18": [[0, -49], [216, -54], [64, -288]], "dialogue-19": [[0, -25], [114, -138], [61, -256]], "script-20": [[0, 3116], [-1741, 2046], [-2633, -130], [-2581, 1363], [1743, 3661], [420, 1970], [-3086, -91], [-1311, 2362], [-2764, -228], [-1647, 1991], [-1820, 2394], [-1178, 1035]], "script-21": [[-1867, -55], [-2934, -244], [469, 3777], [-4635, -1409], [-1443, 1812], [338, 3738], [92, 2387], [-1116, 2771], [-1956, 1199], [27, 1857], [-2720, -364], [-3969, -424]], "script-22": [[-1799, -54], [-2912, -98], [2, 3612], [309, 3743], [-3547, -18], [-3673, -195], [26, 2842], [-2963, -1339], [-3557, 1985], [-3649, 3], [-2240, -126], [-3881, -337]], "script-23": [[-1946, 1860], [-4163, -42], [-2492, -87], [-4205, -3610], [2115, 2830], [70, 3930], [349, 2976], [-2658, -1717], [-3671, -109], [180, 3872], [124, 2534], [-2505, 1127]], "script-24": [[-3910, -164], [-1008, 2601], [-1677, 2144], [123, 4162], [-2592, -159], [370, 3903], [-2037, -204], [-3286, -3770], [3534, 3890], [244, 4012], [105, 2308], [-3490, -254]]}
- speech_rate_calibrated: suggested_speech_rate_wpm=122 within_10pct=25/25 max_deviation=0.069
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1081 limit_mib=11264 samples=193 interval=1s first_mib=1078 elapsed_s=204
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Phương pháp mốc tham chiếu

Mốc tham chiếu được đo bằng FFmpeg silencedetect chạy trực tiếp trên giọng sạch (clean voice), thử lần lượt qua lưới tham số cố định REFERENCE_GRID (từ -40dB/0.15s đến -45dB/0.3s). Bộ tham số đầu tiên trong lưới cho số khoảng nói bằng đúng số câu của đoạn thoại được chọn làm tham chiếu và các khoảng nói được ghép trực tiếp theo thứ tự câu; nếu không có bộ tham số nào trong lưới cho số khoảng nói bằng số câu, bộ đầu lưới (-40dB/0.15s) được dùng làm dự phòng và câu được ghép theo khoảng có độ trùng lớn nhất. Toàn bộ việc chọn mốc tham chiếu hoàn toàn độc lập với kết quả của aligner; các ngưỡng dung sai 150 ms và tỷ lệ đạt 95% từ profile được giữ nguyên.

## Phân tích aligner_timing

Kết quả đo đạc độ lệch có dấu giữa mốc aligner và mốc silencedetect:
- Phân vị độ lệch bắt đầu câu: p10 = -3490 ms, p50 (trung vị) = 0 ms, p90 = 370 ms.
- Phân vị độ lệch kết thúc câu: p10 = -308 ms, p50 (trung vị) = -87 ms, p90 = 3661 ms.
- Tỷ lệ câu đạt chuẩn (|start_delta| <= 150 ms và |end_delta| <= 150 ms): 21/110 câu (19.1%), chưa đạt ngưỡng yêu cầu 95%.
- Nhận định về sai lệch hệ thống:
  1. Ở 19/20 đoạn thoại ngắn (dialogue-00..15, 17..19), việc hiệu chỉnh tham chiếu giúp tìm được đúng số khoảng nói (2 hoặc 3 khoảng, dùng cấu hình -40dB/0.4s). Mốc bắt đầu câu rất chính xác (đa số lệch 0 ms, p50 = 0 ms). Tuy nhiên, mốc kết thúc câu có xu hướng âm hệ thống (p50 = -87 ms, nhiều câu lệch từ -150 ms đến -378 ms), cho thấy mốc kết thúc từ cuối cùng do faster-whisper nhận diện thường đóng sớm hơn khoảng nghỉ âm thanh do silencedetect phát hiện.
  2. Ở 5 kịch bản dài (script-20..24, mỗi kịch bản 12 câu), do cấu trúc câu phức tạp và nhiều chỗ ngắt hơi nhỏ giữa câu, silencedetect phát hiện từ 30 đến 32 khoảng nói tại mọi cấu hình trong lưới, không thể khớp 1:1 với 12 câu. Thuật toán fallback sang ghép theo độ trùng lớn nhất dẫn đến sai lệch rất lớn (start_delta lệch âm tới -3490 ms và end_delta lệch dương tới +3661 ms) do faster-whisper gộp hoặc kéo dài mốc từ qua nhiều khoảng nói.
  3. Nguyên nhân căn bản nằm ở thuật toán phân đoạn từ và gán nhãn thời gian của faster_whisper trong src/voice/adapters/real_whisper_aligner.py (hoặc giới hạn năng lực của mô hình nhỏ small.en). Do adapter này nằm ngoài owned paths của CP7-6, việc xử lý cần quyết định kiến trúc từ Orchestrator và Control.

## Cách xử lý tương thích av

Runtime khoá có av==19.0.2, faster_whisper/audio.py:46 gọi av.open(..., metadata_errors='ignore') gây TypeError; adapter src/voice/adapters/real_whisper_aligner.py không bị sửa; test giải mã WAV bằng FFmpeg ghim (sha256 theo runtime.lock.json) thành float32 16 kHz mono rồi đưa cho WhisperModel thật qua model_factory; đề xuất Control đưa vào backlog việc ghim av tương thích hoặc cho adapter tự giải mã (ngoài phạm vi CP7-6).

## Giới hạn

Không sửa profile cấu hình, không sửa src/**, chi phí 0 USD, aligner chạy trên cpu theo profile.
