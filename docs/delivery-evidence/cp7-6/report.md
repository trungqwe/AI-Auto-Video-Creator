# CP7-6 — TTS Kokoro và aligner faster-whisper thật (RG-05)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-6, bằng interpreter khoá của lane, sau khi giải mã audio qua FFmpeg ghim cho WhisperModel thật.

Trạng thái: 6/7 mục PASS, riêng mục aligner_timing FAIL do số đo thực tế không đạt ngưỡng 95% (đo được 1/110 câu đạt độ lệch <= 150 ms).

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
- tts_valid_wav: words_and_actual_duration_ms={"dialogue-00":[24,11541],"dialogue-01":[22,10858],"dialogue-02":[21,10944],"dialogue-03":[22,11306],"dialogue-04":[23,10581],"dialogue-05":[26,13376],"dialogue-06":[26,13013],"dialogue-07":[27,12565],"dialogue-08":[26,12778],"dialogue-09":[26,12778],"dialogue-10":[46,21184],"dialogue-11":[47,22976],"dialogue-12":[46,21888],"dialogue-13":[48,24277],"dialogue-14":[47,22570],"dialogue-15":[51,24938],"dialogue-16":[53,25344],"dialogue-17":[51,24405],"dialogue-18":[51,23808],"dialogue-19":[51,24896],"script-20":[155,79829],"script-21":[159,81344],"script-22":[169,82517],"script-23":[163,81301],"script-24":[167,81834]}
- tts_valid_wav: synth_latency_ms_max=13198 total_audio_s=762.9
- aligner_unmatched: passages_ok=24/25 cap=0.05 max_ratio=0.0952 aligner_errors=[]
- aligner_unmatched: ratio_by_passage={"dialogue-00":0,"dialogue-01":0.0455,"dialogue-02":0.0952,"dialogue-03":0,"dialogue-04":0.0435,"dialogue-05":0.0385,"dialogue-06":0,"dialogue-07":0.037,"dialogue-08":0.0385,"dialogue-09":0,"dialogue-10":0,"dialogue-11":0.0213,"dialogue-12":0.0323,"dialogue-13":0,"dialogue-14":0.0213,"dialogue-15":0.0196,"dialogue-16":0,"dialogue-17":0,"dialogue-18":0.0196,"dialogue-19":0,"script-20":0.0194,"script-21":0.0158,"script-22":0.0118,"script-23":0.0184,"script-24":0.0328}
- aligner_unmatched: audio=voice + music -20.0 dB + 3 SFX at -12.0 dB; aligner device=cpu
- aligner_unmatched: model=real faster-whisper small.en weights pinned; audio decoded by pinned ffmpeg to 16 kHz float32 mono because av==19.0.2 breaks faster_whisper.decode_audio (adapter unchanged)
- aligner_timing: sentences_ok=1/110 tolerance_ms=150 max_delta_ms=3774 median_delta_ms=540
- speech_rate_calibrated: suggested_speech_rate_wpm=122 within_10pct=25/25 max_deviation=0.069
- speech_rate_calibrated: held_out calibrated_on_dialogues_wpm=124 scripts_within_10pct=5/5
- speech_rate_calibrated: profile_wpm=150 within_10pct=0/25 (before calibration; profile not modified)
- vram_peak: peak_mib=1081 limit_mib=11264 samples=197 interval=1s first_mib=1081 elapsed_s=208
- vram_peak: nvidia-smi memory.used of the whole GPU (includes other processes); aligner device=cpu
- secret_scan: report, test and corpus match_count=0; no credential used (local models only, cost 0 USD)

## Cách xử lý tương thích av

Runtime khoá có av==19.0.2, faster_whisper/audio.py:46 gọi av.open(..., metadata_errors='ignore') gây TypeError; adapter src/voice/adapters/real_whisper_aligner.py không bị sửa; test giải mã WAV bằng FFmpeg ghim (sha256 theo runtime.lock.json) thành float32 16 kHz mono rồi đưa cho WhisperModel thật qua model_factory; đề xuất Control đưa vào backlog việc ghim av tương thích hoặc cho adapter tự giải mã (ngoài phạm vi CP7-6).

## Giới hạn

Không sửa profile cấu hình, không sửa src/**, chi phí 0 USD, aligner chạy trên cpu theo profile.
