# ADAPT-E-FIX3 — Aligner chia mốc cụm số cùng giá trị và đo lại RG-05

Ngày kiểm: 31/10/2026
HEAD nền tích hợp: 7e91c5bee7955e5c8c9fe00ea89f3effc74c6240
HEAD sau commit mã (A–C): d19f4cf3ca5b304dc1c230f7a294c2326b7ff6f4 (candidate cuối do Control ghi nhận sau commit báo cáo)
Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`
Gốc tạm pytest: `C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\ADAPT-E-FIX3-implement-r0-ac1b5c0961`

## Nhóm lỗi

R28: aligner không khớp cụm số cùng giá trị viết khác dạng (kịch bản "one hundred fifty-six" ↔ token nghe được "156"), làm `word_coverage_incomplete` ở RG-09.

## Tệp đã sửa

- `src/voice/adapters/real_whisper_aligner.py`: thêm `ERROR_SPLIT_RATIO_EXCEEDED`, `AlignmentReport.split_word_count`, `_cardinal`, `_same_number`; `_match_script` trả bộ bốn; `align` chia mốc theo tỷ lệ ký tự và kiểm trần `split_count / len(expected)`.
- `tests/integration/adapt/e/test_adapt_e_aligner_numbers.py`: tệp mới, 17 ca, không monkeypatch.
- `docs/implementation/adapt/plan.md`: sửa dòng 115 và 188, vẫn 343 dòng.
- `docs/delivery-evidence/adapt-e-fix3/report.md`: báo cáo này.

## Lệnh kiểm

- Lệnh (RED, chạy trước khi sửa src/): `python -m pytest tests/integration/adapt/e/test_adapt_e_aligner_numbers.py tests/integration/adapt/e/test_adapt_e_aligner_edges.py tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` — mã thoát 1 (đúng kỳ vọng RED: ca mới hỏng do thiếu `split_word_count`/mốc, ca cũ đạt). Dòng tổng pytest: `17 failed, 48 passed in 1.26s`
- Lệnh: `python -m pytest tests/integration/adapt/e/test_adapt_e_aligner_numbers.py tests/integration/adapt/e/test_adapt_e_aligner_edges.py tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` (sau khi sửa) — mã thoát 0. Dòng tổng pytest: `65 passed in 1.03s`
- Lệnh: `git diff --check` (sau A–C) — mã thoát 0.
- Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_e2_voice_ports.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` — mã thoát 0. Dòng tổng pytest: `26 passed, 89 subtests passed in 2.32s`
- Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` — mã thoát 0. Dòng tổng pytest: `10 passed, 1 warning in 123.03s (0:02:03)`
- Lệnh: probe VAD literal (lệnh kiểm số 6) — mã thoát 0.
- Lệnh: probe băm 23 dòng nhánh rescued và dấu hiệu FIX3 (lệnh kiểm số 7) — mã thoát 0.
- Lệnh: probe `plan.md` (lệnh kiểm số 8) — mã thoát 0.
- Lệnh: probe tên test, không monkeypatch (lệnh kiểm số 9) — mã thoát 0.
- Lệnh: `python -m pytest tests/real/test_cp7_voice_real.py -q -p no:cacheprovider` (RG-05 thật) — mã thoát 0. Dòng tổng pytest: `7 passed in 400.49s (0:06:40)`
- Lệnh: probe báo cáo so băm bốn dòng RG-05 với cp7-6 (lệnh kiểm số 10) — mã thoát 0.
- Lệnh: probe báo cáo nêu mã gói và R28 (lệnh kiểm số 11) — mã thoát 0.
- Lệnh: `git diff --check` (cuối) — mã thoát 0.

## Kết quả RG-05 (chép nguyên văn từ output lượt đo lại)

RG-05.weights_pinned: PASS
RG-05.tts_valid_wav: PASS
RG-05.aligner_unmatched: PASS
RG-05.aligner_timing: PASS
RG-05.speech_rate_calibrated: PASS
RG-05.vram_peak: PASS
RG-05.secret_scan: PASS

## Chi tiết đo RG-05 (chép nguyên văn)

- weights_pinned: kokoro-v1.0.onnx sha256=7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5 group=kokoro-onnx
- weights_pinned: voices-v1.0.bin sha256=bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d group=kokoro-onnx
- weights_pinned: config.json sha256=666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae group=faster-whisper-small.en
- weights_pinned: model.bin sha256=62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a group=faster-whisper-small.en
- weights_pinned: tokenizer.json sha256=929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df group=faster-whisper-small.en
- weights_pinned: vocabulary.txt sha256=ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf group=faster-whisper-small.en
- tts_valid_wav: valid=25/25 format=24000Hz mono 16-bit voice=af_heart speed=1.0
- tts_valid_wav: words_and_actual_duration_ms={"dialogue-00": [24, 11541], "dialogue-01": [22, 10858], "dialogue-02": [21, 10944], "dialogue-03": [22, 11306], "dialogue-04": [23, 10581], "dialogue-05": [26, 13376], "dialogue-06": [26, 13013], "dialogue-07": [27, 12565], "dialogue-08": [26, 12778], "dialogue-09": [26, 12778], "dialogue-10": [46, 21184], "dialogue-11": [47, 22976], "dialogue-12": [46, 21888], "dialogue-13": [48, 24277], "dialogue-14": [47, 22570], "dialogue-15": [51, 24938], "dialogue-16": [53, 25344], "dialogue-17": [51, 24405], "dialogue-18": [51, 23808], "dialogue-19": [51, 24896], "script-20": [155, 80734], "script-21": [159, 82183], "script-22": [169, 83361], "script-23": [163, 82191], "script-24": [167, 82712]}
- tts_valid_wav: synth_latency_ms_max=12988 total_audio_s=767.2
- aligner_unmatched: passages_ok=25/25 cap=0.05 max_ratio=0.0476 aligner_errors=[]
- aligner_unmatched: ratio_by_passage={"dialogue-00": 0.0, "dialogue-01": 0.0, "dialogue-02": 0.0476, "dialogue-03": 0.0, "dialogue-04": 0.0, "dialogue-05": 0.0, "dialogue-06": 0.0, "dialogue-07": 0.0, "dialogue-08": 0.0, "dialogue-09": 0.0, "dialogue-10": 0.0, "dialogue-11": 0.0, "dialogue-12": 0.0, "dialogue-13": 0.0, "dialogue-14": 0.0, "dialogue-15": 0.0, "dialogue-16": 0.0, "dialogue-17": 0.0, "dialogue-18": 0.0, "dialogue-19": 0.0, "script-20": 0.0, "script-21": 0.0032, "script-22": 0.0059, "script-23": 0.0, "script-24": 0.0}
- aligner_unmatched: audio=voice + music -20.0 dB + 3 SFX at -12.0 dB; aligner device=cpu
- aligner_unmatched: model=real faster-whisper small.en weights pinned; audio decoded by the production path (faster_whisper.decode_audio inside RealWhisperAligner, no test-side decode) with av==18.1.0; adapter unchanged
- aligner_timing: diag signed start_delta_ms p10/p50/p90=32/52/106 end_delta_ms p10/p50/p90=-44/-10/88 scored=110/110
- aligner_timing: diag spans_sentences_lead_trail_ms_by_passage={"dialogue-00": [2, 2, [0, 1]], "dialogue-01": [2, 2, [0, 1]], "dialogue-02": [2, 2, [0, 147]], "dialogue-03": [2, 2, [0, 0]], "dialogue-04": [2, 2, [0, 148]], "dialogue-05": [2, 2, [0, 0]], "dialogue-06": [2, 2, [0, 0]], "dialogue-07": [2, 2, [0, 0]], "dialogue-08": [2, 2, [0, 104]], "dialogue-09": [2, 2, [0, 0]], "dialogue-10": [3, 3, [0, 111]], "dialogue-11": [3, 3, [0, 0]], "dialogue-12": [3, 3, [0, 1]], "dialogue-13": [3, 3, [0, 113]], "dialogue-14": [3, 3, [0, 0]], "dialogue-15": [3, 3, [0, 1]], "dialogue-16": [3, 3, [0, 1]], "dialogue-17": [3, 3, [0, 1]], "dialogue-18": [3, 3, [0, 141]], "dialogue-19": [3, 3, [0, 1]], "script-20": [12, 12, [0, 0]], "script-21": [12, 12, [0, 0]], "script-22": [12, 12, [0, 0]], "script-23": [12, 12, [0, 125]], "script-24": [12, 12, [0, 0]]}
- aligner_timing: diag deltas_ms_by_passage={"dialogue-00": [[64, 43], [74, -203]], "dialogue-01": [[288, 16], [42, 1]], "dialogue-02": [[32, 44], [63, 147]], "dialogue-03": [[192, -21], [63, 0]], "dialogue-04": [[32, -10], [42, 148]], "dialogue-05": [[32, 34], [84, 0]], "dialogue-06": [[32, 38], [52, 0]], "dialogue-07": [[32, -32], [84, 0]], "dialogue-08": [[64, 91], [84, 104]], "dialogue-09": [[32, -32], [52, 0]], "dialogue-10": [[128, 77], [31, -43], [72, 111]], "dialogue-11": [[32, 82], [84, -12], [40, 0]], "dialogue-12": [[96, -21], [31, -22], [62, 1]], "dialogue-13": [[64, 56], [106, -11], [72, 113]], "dialogue-14": [[32, -32], [52, -44], [40, 0]], "dialogue-15": [[64, -42], [42, -54], [94, 1]], "dialogue-16": [[64, 72], [31, -22], [30, 1]], "dialogue-17": [[64, 61], [42, 54], [94, 1]], "dialogue-18": [[32, 56], [52, 80], [94, 141]], "dialogue-19": [[32, -32], [212, -33], [51, 1]], "script-20": [[96, -53], [127, -150], [94, -12], [39, -35], [48, -26], [58, -27], [88, -18], [66, 90], [86, -10], [42, -54], [30, -175], [92, 0]], "script-21": [[32, -21], [63, -1], [115, -34], [50, 198], [38, -36], [47, 60], [56, 17], [98, -40], [43, 57], [42, -11], [40, -13], [71, 0]], "script-22": [[160, -32], [52, -33], [51, -45], [39, -151], [48, -48], [36, -17], [35, -39], [44, -20], [32, 71], [106, 76], [51, -23], [60, 0]], "script-23": [[64, -32], [52, -33], [51, 88], [50, -119], [48, -37], [79, -27], [88, 40], [55, 52], [43, -21], [127, 78], [104, 52], [50, 125]], "script-24": [[32, -21], [63, -43], [40, -34], [6, 56], [38, 63], [90, -27], [56, -18], [34, -212], [43, -42], [138, -11], [40, 88], [39, 0]]}
- aligner_timing: diag sentences_ok_by_reference_noise_db={"-40": 106, "-35": 106, "-30": 106} primary_db=-30 total=110
- aligner_timing: diag clean_voice_rms_dbfs_median=-22.5
- aligner_timing: diag gap_midpoint_within_tolerance=85/85 (mean of end delta of sentence n and start delta of sentence n+1; diagnostic only, not the verdict)
- aligner_timing: sentences_ok=106/110 tolerance_ms=200 max_delta_ms=288 median_delta_ms=63
- aligner_timing: reference=ffmpeg silencedetect (pinned ffmpeg) noise=-30dB d=0.1s run on each sentence clip synthesized separately by the real Kokoro adapter; clips joined with 300 ms digital silence then mixed with music -20.0 dB and 3 SFX at -12.0 dB; sentence start/end = clip edges outside leading/trailing silence + join offset; ffmpeg_sha256=f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480
- speech_rate_calibrated: suggested_speech_rate_wpm=121 within_10pct=25/25 max_deviation=0.078
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1890 limit_mib=11264 samples=379 interval=1s first_mib=1613 elapsed_s=400
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Đối chiếu với CP7-6

Bốn dòng `passages_ok`, `ratio_by_passage`, `deltas_ms_by_passage`, `sentences_ok` trùng nguyên văn `docs/delivery-evidence/cp7-6/report.md` dòng 28, 29, 34, 38 (kiểm bằng sha256 ở probe báo cáo). Kết quả 7/7 PASS.

## Phạm vi và ranh giới R28

Chỉ sửa 4 tệp sở hữu, chỉ dùng stdlib; không sửa prompt lệnh D, wiring, profile hay test đã có. Nhánh rescued (Silero VAD) giữ nguyên, băm 23 dòng khớp. Nhánh chia mốc mới không thể chạy trên RG-05 (kho câu chỉ gồm chữ, không có token chữ số) nên không ảnh hưởng mốc cũ. Chi phí 0 USD.

Backlog MINOR (không sửa trong gói này): `tools/launcher/prod/profile.json:268` (reason ghi "không thực hiện nội suy") và `docs/implementation/adapt/slices.md:88`.
