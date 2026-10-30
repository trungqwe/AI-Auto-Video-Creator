# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, sau khi cập nhật mốc tham chiếu ranh giới câu bằng (số câu − 1) khoảng im dài nhất của giọng sạch từ FFmpeg silencedetect (-30 dB, d=0.1 s).

Trạng thái: 6/7 mục PASS, riêng mục aligner_timing FAIL do số đo thực tế đạt 37/110 câu (33.6%), chưa đạt ngưỡng yêu cầu 95%.

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
- tts_valid_wav: synth_latency_ms_max=13106 total_audio_s=762.9
- aligner_unmatched: passages_ok=24/25 cap=0.05 max_ratio=0.0952 aligner_errors=[]
- aligner_unmatched: ratio_by_passage={"dialogue-00": 0.0, "dialogue-01": 0.0455, "dialogue-02": 0.0952, "dialogue-03": 0.0, "dialogue-04": 0.0435, "dialogue-05": 0.0385, "dialogue-06": 0.0, "dialogue-07": 0.037, "dialogue-08": 0.0385, "dialogue-09": 0.0, "dialogue-10": 0.0, "dialogue-11": 0.0213, "dialogue-12": 0.0323, "dialogue-13": 0.0, "dialogue-14": 0.0213, "dialogue-15": 0.0196, "dialogue-16": 0.0, "dialogue-17": 0.0, "dialogue-18": 0.0196, "dialogue-19": 0.0, "script-20": 0.0194, "script-21": 0.0158, "script-22": 0.0118, "script-23": 0.0184, "script-24": 0.0328}
- aligner_unmatched: audio=voice + music -20.0 dB + 3 SFX at -12.0 dB; aligner device=cpu
- aligner_unmatched: model=real faster-whisper small.en weights pinned; audio decoded by pinned ffmpeg to 16 kHz float32 mono because av==19.0.2 breaks faster_whisper.decode_audio (adapter unchanged)
- aligner_timing: diag signed start_delta_ms p10/p50/p90=-6671/0/431 end_delta_ms p10/p50/p90=-6548/-142/-7 scored=110/110
- aligner_timing: diag spans_sentences_margin_ms_by_passage={"dialogue-00": [2, 2, [683, 341]], "dialogue-01": [2, 2, [729, 360]], "dialogue-02": [2, 2, [708, 367]], "dialogue-03": [2, 2, [625, 389]], "dialogue-04": [2, 2, [658, 286]], "dialogue-05": [2, 2, [774, 390]], "dialogue-06": [2, 2, [806, 383]], "dialogue-07": [2, 2, [669, 377]], "dialogue-08": [2, 2, [762, 340]], "dialogue-09": [2, 2, [647, 370]], "dialogue-10": [3, 3, [695, 395]], "dialogue-11": [3, 3, [698, 380]], "dialogue-12": [3, 3, [634, 403]], "dialogue-13": [3, 3, [728, 394]], "dialogue-14": [3, 3, [662, 407]], "dialogue-15": [3, 3, [666, 407]], "dialogue-16": [3, 3, [698, 431]], "dialogue-17": [3, 3, [722, 400]], "dialogue-18": [3, 3, [709, 402]], "dialogue-19": [3, 3, [720, 438]], "script-20": [12, 12, [354, 352]], "script-21": [12, 12, [391, 385]], "script-22": [12, 12, [396, 394]], "script-23": [12, 12, [392, 384]], "script-24": [12, 12, [426, 391]]}
- aligner_timing: diag deltas_ms_by_passage={"dialogue-00": [[0, -97], [140, -281]], "dialogue-01": [[0, -4], [227, -338]], "dialogue-02": [[0, -92], [180, -18]], "dialogue-03": [[0, -119], [76, -346]], "dialogue-04": [[0, -134], [328, -78]], "dialogue-05": [[0, 13], [439, -216]], "dialogue-06": [[0, -26], [-12, -173]], "dialogue-07": [[0, -34], [397, -245]], "dialogue-08": [[0, -7], [431, -193]], "dialogue-09": [[0, -192], [161, -298]], "dialogue-10": [[0, -33], [-18, -78], [186, -58]], "dialogue-11": [[0, -19], [399, -267], [95, -296]], "dialogue-12": [[0, -152], [-6, -85], [90, -308]], "dialogue-13": [[0, -54], [98, -100], [67, -197]], "dialogue-14": [[0, -150], [-52, -142], [433, -290]], "dialogue-15": [[0, -163], [31, -49], [285, -378]], "dialogue-16": [[0, -47], [-78, -48], [134, -284]], "dialogue-17": [[0, -76], [-18, -80], [126, -305]], "dialogue-18": [[0, -16], [215, -45], [53, -176]], "dialogue-19": [[0, -13], [112, -121], [59, -256]], "script-20": [[0, -15], [367, 4410], [4836, 6360], [6531, 7160], [7086, -61], [419, 1982], [2531, 6825], [6999, 6505], [6114, -216], [106, -53], [130, -109], [89, -289]], "script-21": [[0, -46], [74, -235], [458, -89], [11, -5692], [-6085, -6930], [-6671, -6509], [-6392, -14090], [-13935, -13283], [-13616, -9854], [-9465, -7572], [-7026, -4641], [-3969, -424]], "script-22": [[0, -39], [103, -85], [0, -152], [305, -6801], [-7418, -4178], [-3674, -177], [23, -38], [297, -7492], [-8202, -7103], [-6807, -2675], [-2317, -120], [-113, -337]], "script-23": [[0, -66], [381, -26], [98, -46], [-14, -6548], [-7211, -3018], [-2570, -49], [346, -58], [-8, -6163], [-6787, -5648], [-5140, -5], [117, -66], [483, -110]], "script-24": [[0, -154], [356, -160], [37, -4], [81, -5768], [-6191, -7316], [-6786, -6953], [-6265, -3688], [-3289, -7750], [-7185, -4665], [-4171, -97], [105, -39], [34, -254]]}
- aligner_timing: diag sentences_ok_by_reference_noise_db={"-40": 35, "-35": 37, "-30": 37} primary_db=-30 total=110
- aligner_timing: diag clean_voice_rms_dbfs_median=-22.5
- speech_rate_calibrated: suggested_speech_rate_wpm=122 within_10pct=25/25 max_deviation=0.069
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1095 limit_mib=11264 samples=193 interval=1s first_mib=1077 elapsed_s=204
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Phương pháp mốc tham chiếu

Mốc tham chiếu được xác định trực tiếp trên file âm thanh giọng sạch (clean voice) bằng công cụ FFmpeg silencedetect đã ghim (sha256 theo runtime.lock.json). Ranh giới giữa các câu được chọn là (số câu − 1) khoảng im dài nhất nằm giữa hai đoạn nói (do văn bản kiểm thử chỉ chứa dấu chấm kết câu, không có dấu phẩy, nên các khoảng nghỉ dài nhất giữa các đoạn nói tương ứng với vị trí chuyển câu). Điểm bắt đầu câu đầu tiên được tính từ cuối khoảng im đầu file (nếu có); điểm kết thúc câu cuối cùng được tính từ đầu khoảng im cuối file (nếu khoảng im này kết thúc sát độ dài file trong phạm vi dung sai 50 ms). Toàn bộ quá trình tạo mốc tham chiếu hoàn toàn độc lập với kết quả của aligner.

Ngưỡng phát hiện khoảng im được khai báo trước lần chạy là REFERENCE_NOISE_DB = -30 dB và độ dài im tối thiểu REFERENCE_MIN_SILENCE_S = 0.1 s. Mức -30 dB nằm dưới trung vị RMS giọng nói đo được (-22.5 dBFS) khoảng 7.5 dB, gần ranh giới nghe được của tai người hơn mức -40 dB. Người thực hiện trung thực ghi nhận đã quan sát chẩn đoán ở lượt chạy trước khi ấn định -30 dB. Ngoài ra, kiểm thử tính thêm chẩn đoán độ nhạy tại các ngưỡng -40 dB và -35 dB để ghi nhận dữ liệu đối sánh; các ngưỡng này chỉ phục vụ chẩn đoán, không dùng để chọn lại sau khi chạy. Dung sai thời gian 150 ms và tỷ lệ đạt yêu cầu 95% từ profile giọng được giữ nguyên tuyệt đối.

## Phân tích aligner_timing

Kết quả đo đạc độ lệch có dấu giữa mốc thời gian của aligner và mốc silencedetect tham chiếu:
- Phân vị độ lệch bắt đầu câu (start_delta_ms): p10 = -6671 ms, p50 (trung vị) = 0 ms, p90 = 431 ms.
- Phân vị độ lệch kết thúc câu (end_delta_ms): p10 = -6548 ms, p50 (trung vị) = -142 ms, p90 = -7 ms.
- Tỷ lệ câu đạt chuẩn (|start_delta| <= 150 ms và |end_delta| <= 150 ms): 37/110 câu (33.6%), chưa đạt ngưỡng yêu cầu 95% (tuy đã tăng so với 21/110 ở cấu hình cũ).
- Chẩn đoán độ nhạy theo ngưỡng khoảng im:
  + Tại -40 dB: 35/110 câu đạt chuẩn.
  + Tại -35 dB: 37/110 câu đạt chuẩn.
  + Tại -30 dB (ngưỡng chính): 37/110 câu đạt chuẩn.
  Kết quả cho thấy số câu đạt chuẩn gần như bão hoà giữa -35 dB và -30 dB, chứng minh sai lệch không bắt nguồn từ việc chọn ngưỡng im.
- Margin phân tách khoảng im giữa câu:
  + Ở 20 đoạn thoại ngắn (dialogue-00..19), margin giữa khoảng im ngắn nhất được chọn và khoảng im dài nhất không được chọn rất lớn (khoảng im được chọn dài 625–806 ms, khoảng im không được chọn dài 286–438 ms; độ tách biệt an toàn trên 200 ms). Số khoảng nói tạo ra luôn khớp đúng 100% số câu (2 hoặc 3 câu).
  + Ở 5 kịch bản dài (script-20..24, mỗi bài 12 câu), margin gần như triệt tiêu (script-20 là 354 ms so với 352 ms, script-21 là 391 ms so với 385 ms, script-22 là 396 ms so với 394 ms). Trong lời đọc liên tục, khoảng ngắt câu và khoảng ngắt hơi giữa các cụm từ có độ dài xấp xỉ nhau, khiến silencedetect không thể tách bạch ranh giới câu một cách hoàn hảo nếu chỉ dựa vào thời lượng ngắt âm.
- Nhận định về sai lệch hệ thống:
  1. Ở các đoạn thoại ngắn, mốc bắt đầu câu của faster-whisper rất chuẩn xác (trung vị p50 = 0 ms). Tuy nhiên, mốc kết thúc câu có xu hướng âm hệ thống (trung vị p50 = -142 ms, nhiều câu lệch từ -150 ms đến -378 ms). Điều này phản ánh đặc tính của mô hình Whisper: mốc thời gian của từ cuối cùng thường kết thúc ngay khi âm vị cuối dứt, trong khi silencedetect tính trọn vẹn phần suy hao âm thanh đến khi mức năng lượng giảm xuống dưới ngưỡng im.
  2. Ở 5 kịch bản dài, khi trộn thêm nhạc nền -20 dB và 3 hiệu ứng SFX -12 dB, faster-whisper bị trượt mốc tích lũy nghiêm trọng trên một số đoạn (start_delta lệch âm tới -6671 ms và -13935 ms, end_delta lệch tới -14090 ms), dẫn tới sai lệch hàng giây giữa mốc phụ đề và giọng đọc thực tế.
  3. Độ lệch hệ thống này bắt nguồn từ thuật toán gán nhãn thời gian từ (word timestamp alignment) của faster-whisper và mô hình nhỏ small.en trong src/voice/adapters/real_whisper_aligner.py. Vì adapter này nằm ngoài owned paths của CP7-6, việc xử lý dứt điểm cần quyết định từ Orchestrator và Control.

## Cách xử lý tương thích av

Runtime khoá có av==19.0.2, faster_whisper/audio.py:46 gọi av.open(..., metadata_errors='ignore') gây TypeError; adapter src/voice/adapters/real_whisper_aligner.py không bị sửa; test giải mã WAV bằng FFmpeg ghim (sha256 theo runtime.lock.json) thành float32 16 kHz mono rồi đưa cho WhisperModel thật qua model_factory; đề xuất Control đưa vào backlog việc ghim av tương thích hoặc cho adapter tự giải mã (ngoài phạm vi CP7-6).

## Giới hạn

Không sửa profile cấu hình, không sửa src/**, chi phí 0 USD, aligner chạy trên cpu theo profile.
