# CP7-8 — Render, QC và tranh GPU thật (RG-07)

Ngày kiểm: 30/10/2026, trên lane lane-cp7-8, bằng interpreter khoá của lane, trên mã đã rebase lên HEAD dca5439 (integrate(CP7-6): lane lane-cp7-6 candidate 989b01189f4b).

Hai lệnh pytest đã chạy:
1. python -m pytest tests/real/test_cp7_render_real.py -q -p no:cacheprovider (17/17 test đạt, 0 failed)
2. python -m pytest tests/real/test_cp7_gpu_contention.py -q -p no:cacheprovider (4/4 test đạt, 0 failed)
Tổng số: 21/21 test đạt (20 mục nghiệm thu RG-07 và 1 kiểm tra chẩn đoán deadline kill).

Trạng thái: 20/20 mục RG-07 PASS. Render thật 11 video qua RealFfmpegRenderer (5 preset x 2 video NVENC + 1 libx264 dự phòng), kiểm tra toàn bộ tiêu chuẩn container, kích thước, thời lượng, khả năng phát, burn-in phụ đề, độ lệch karaoke, hook visual/audio và đo loudness. Bốn kịch bản lỗi thật (kill giữa chừng, cắt cụt đầu ra, timeout sau side effect, output hỏng) và chốt chặn đĩa hoạt động đúng. Tranh chấp GPU 2 khe hoạt động ổn định, 0 OOM, đỉnh VRAM 1812 MiB dưới ngưỡng 11 GiB.

## Kết quả

RG-07.ffmpeg_pin_used: PASS
RG-07.nvenc_presets: PASS
RG-07.libx264_fallback: PASS
RG-07.container_spec: PASS
RG-07.duration_61_70: PASS
RG-07.size_cap: PASS
RG-07.playable: PASS
RG-07.subtitle_visible: PASS
RG-07.karaoke_timing: PASS
RG-07.hook_checks: PASS
RG-07.loudness_recorded: PASS
RG-07.crash_recovery: PASS
RG-07.partial_output: PASS
RG-07.timeout_outcome_unknown: PASS
RG-07.corrupt_qc_fail: PASS
RG-07.disk_guard: PASS
RG-07.gpu_two_slots: PASS
RG-07.vram_peak: PASS
RG-07.render_p95: PASS
RG-07.secret_scan: PASS

## Chi tiết đo

- ffmpeg_pin_used: sha256=f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480 verified=true stdlib_only=true
- nvenc_presets: runs=10 presets=5 (2 videos each) distinct_colours=5 nvenc_preset=p5
- libx264_fallback: runs=1 name=bold-yellow-A-libx264 wall_ms=7776 qc_ok=True
- container_spec: count=11 width=1080 height=1920 fps=30.0 video=h264 audio=aac@48000 format=mp4
- duration_61_70: min_s=65.820 max_s=67.523 count=11 in_range=[61, 70]
- size_cap: max_bytes=4100430 cap=157286400 staging_bytes=47460934 staging_cap=5368709120
- playable: count=11 decode_check_playable=true sha256_matched=true
- subtitle_visible: min_share=1.000 threshold=0.9 details=["bold-yellow-A-nvenc: 20/20", "bold-yellow-B-nvenc: 20/20", "clean-white-A-nvenc: 20/20", "clean-white-B-nvenc: 20/20", "neon-cyan-A-nvenc: 20/20", "neon-cyan-B-nvenc: 20/20", "news-red-A-nvenc: 20/20", "news-red-B-nvenc: 20/20", "soft-shadow-A-nvenc: 20/20", "soft-shadow-B-nvenc: 20/20", "bold-yellow-A-libx264: 20/20"]
- karaoke_timing: min_share=1.0000 threshold=0.95 max_delta_ms=4 tolerance_ms=150 profile_tolerance_ms=200 note=ass_aligned_against_aligner_markers
- hook_checks: min_sim=0.9972 (>= 0.85) min_audio_db=-21.30 (>= -40.0) min_continuity=0.9848 (>= 0.6)
- loudness_recorded: total=11 warn_count=11 target=-16.0LUFS tol=1.5LU max_tp=-1.5dBTP
- loudness_recorded: bold-yellow-A-nvenc: I=-22.4LUFS TP=-4.5dBTP LRA=2.8 warn=True
- loudness_recorded: bold-yellow-B-nvenc: I=-22.3LUFS TP=-6.2dBTP LRA=2.9 warn=True
- loudness_recorded: clean-white-A-nvenc: I=-22.4LUFS TP=-4.5dBTP LRA=2.8 warn=True
- loudness_recorded: clean-white-B-nvenc: I=-22.3LUFS TP=-6.2dBTP LRA=2.9 warn=True
- loudness_recorded: neon-cyan-A-nvenc: I=-22.4LUFS TP=-4.5dBTP LRA=2.8 warn=True
- loudness_recorded: neon-cyan-B-nvenc: I=-22.3LUFS TP=-6.2dBTP LRA=2.9 warn=True
- loudness_recorded: news-red-A-nvenc: I=-22.4LUFS TP=-4.5dBTP LRA=2.8 warn=True
- loudness_recorded: news-red-B-nvenc: I=-22.3LUFS TP=-6.2dBTP LRA=2.9 warn=True
- loudness_recorded: soft-shadow-A-nvenc: I=-22.4LUFS TP=-4.5dBTP LRA=2.8 warn=True
- loudness_recorded: soft-shadow-B-nvenc: I=-22.3LUFS TP=-6.2dBTP LRA=2.9 warn=True
- loudness_recorded: bold-yellow-A-libx264: I=-22.4LUFS TP=-4.5dBTP LRA=2.8 warn=True
- render_p95: p95_ms=7617 median_ms=7305.0 max_ms=7617 libx264_ms=7776 cap_ms=900000 note=G02_metric_reference_7min_video_for_comparison_only
- crash_recovery: attempt_state=FAILED problem=render_attempt_failed retry_state=SUCCEEDED retry_qc_ok=true lease_released=true
- partial_output: marker_bytes=262192 no_part_files=true kill_a_absent=true remaining_count=12
- timeout_outcome_unknown: scenario_a_reconciled_succeeded=true qc_ok=true scenario_b_reconciled_failed=true error=reconcile_output_missing
- corrupt_qc_fail: pipeline_corrupt_reasons=['ffprobe_rejected', 'decode_errors', 'size', 'fps', 'video_codec', 'audio_codec', 'container', 'duration', 'bytes'] truncated_reasons=['decode_errors'] baseline_ok=true
- disk_guard: free_bytes=55287148544 reserve_bytes=32212254720 margin_bytes=23074893824 need_ok_mib=4 need_block_mib=22006 bytes_written_by_test=65074471 note=khong lap day dia
- gpu_two_slots: round 0: max_held=2 max_active=2 refused=4 waiting=['stt'] oom=0
- gpu_two_slots: round 1: max_held=2 max_active=2 refused=4 waiting=['stt'] oom=0
- gpu_two_slots: aligner_device=cpu note=aligner_on_cpu_gpu_shared_by_render_and_tts
- vram_peak: peak_mib=1812 limit_mib=11264 samples=10 first_mib=1509 elapsed_s=9.7 tmp_bytes=126560626
- secret_scan: match_count=0; khong dung credential; chi phi 0 USD
- deadline_kill: child_pid_gone=True elapsed_s=1.51

## Giới hạn trung thực

1. Kill FFmpeg dùng command_prefix của adapter chạy FFmpeg thật dưới wrapper Python kill sau khi tệp .part đạt 256 KiB;
2. Kịch bản timeout sau side effect dùng bao bọc LateTimeoutRenderer quanh renderer thật (render xong rồi ném RendererTimeout), kịch bản timeout 2 giây là timeout thật;
3. Pipeline dùng InMemoryRenderUnitOfWork, không PostgreSQL;
4. Lệch karaoke đo giữa tệp ASS và mốc aligner (dung sai 150 ms theo nghiệm thu, chặt hơn hồ sơ 200 ms) cộng lấy mẫu khung hình cho phụ đề, không đo độ lệch tiếng-chữ độc lập;
5. Visual continuity là định nghĩa GIẢ ĐỊNH của slice (cặp khung YDIF <= 20 ở 5 fps) vì repo chưa có phép đo chuẩn;
6. Aligner chạy trên thiết bị theo hồ sơ (cpu) nên tranh GPU chủ yếu giữa render NVENC và TTS;
7. Hook và ảnh seed tự sinh bằng lavfi, kịch bản tự soạn 126 và 128 từ (được điều chỉnh lên 164 và 163 từ để đạt thời lượng chuẩn 65–68 s), giọng do RealKokoroTts và aligner của CP7-6;
8. Lệnh pytest ở bước 20 chỉ xác nhận lại, số đo trong báo cáo là của lượt 17 và 18.

## Chi phí

Chi phí: 0 USD; tài nguyên GPU cục bộ dùng dưới 1 giờ (giới hạn tối đa 4 giờ); dung lượng thư mục đĩa tạm ~126 MiB (dưới trần 5 GiB). Không sử dụng credential ngoài; không có bí mật.
