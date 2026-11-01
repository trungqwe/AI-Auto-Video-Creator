# Báo cáo PW-E4-FIX1: nhạc nền thật theo DQ-12

## 1. Mục tiêu và phạm vi

Gói PW-E4-FIX1 sửa nhóm lỗi OI-PW-E4-02 (transport thật và bộ đo MP3 của PW-E4) trên bản chép b6cc8d1. Số liệu đo được trước khi sửa: `staging/audio_library` có 28/28 tệp `bed-none`, 0 tệp `music-*`. Bốn lỗi gốc:

1. `check_music_url(url)` ở `wiring/voice.py` thiếu đối số `sources`, nên mọi lần fetch ném `TypeError` và thành `music_fetch_failed`.
2. `duration_probe=measure_wav_duration_ms` chỉ đọc WAV, trong khi hai nguồn ghim là MP3 nên ra `music_unreadable`; loudness là hằng -16/-2 thay vì số đo.
3. Cue sfx kéo cả bed về `none` (`cue_kind_not_music`); kế hoạch J có cue nhạc 31765 và 33088 ms cùng cue sfx 1100 và 1500 ms.
4. Cue không mood bị gán `calm`, nên nguồn dự phòng (carefree, upbeat) không bao giờ được thử.

Đính chính D8 của PW-E4 (`docs/delivery-evidence/pw-e4/report.md:23`, cue sfx kéo cả bed về none): căn cứ a15a18f2 và DQ-12 (`plan.md:30`: bed là `none` chỉ khi không có nhạc phù hợp), cue sfx không được kéo cue nhạc về `none`. Cue sfx nhận bản im lặng `bed-none-<sha>` đúng span, cue nhạc vẫn dùng nhạc thật.

OI-PW-E4-02 (giao wiring transport thật và bộ đo MP3) đã đóng bởi gói này.

## 2. Tệp đã đổi (owned paths)

- `src/voice/adapters/real_ffmpeg_media_tool.py`: `RealFfmpegMediaTool.prepare_music`, `_run_audio`, `_music_sample_rate`, `_measure_music`, `_loudness_target`.
- `src/voice/adapters/audio_bed_source.py`: `PreparedMusic`, `AudioBedSource` (nhận `prepare_music`, `_collect`, `_music_outcome`, `_none_outcome`, `_store_silence`), `CollectedTrack.rendition_sha256`, `track_from_sidecar`.
- `src/controlplane/api/wiring/voice.py`: `ProductionHttpsTransport`, `_PinnedTlsConnection`, `voice_activity_deps` (thêm `music_sources`, `music_transport`), `_music_loudness_target`, `PlanAudioFromPlans.plan_audio` (mood rỗng thành `None`).
- `tests/integration/prod_wiring/test_pw_e4_audio_bed.py`: chỉ khối dựng rig `rig_factory` chuyển sang `prepare_music`.
- `tests/integration/prod_wiring/test_pw_e4_fix1_music_bed.py`: tệp mới (coveredIds FR-AUD-007, FR-AUD-004, CT-AUD-001).
- `docs/delivery-evidence/pw-e4-fix1/report.md`: báo cáo này.

## 3. Quyết định D8 của gói

- Mood rỗng thành `None` để cue không mood tới được nguồn dự phòng.
- Cue sfx nhận bản im lặng `bed-none-<sha>` đúng span, không cảnh báo; `provenance['sfx']` ghi `cue_index`, `bed_kind` là `none`, `reason` là `no_sfx_source`. Cue nhạc thiếu nhạc thì cả bed `none` như cũ; không có cue nhạc thì `none` với lỗi `no_music_cue`.
- Mục tiêu loudness chỉ lấy từ `profile.parameters['audio.loudness']` (`integrated_lufs`, `true_peak_dbtp`, `lra`); thiếu hoặc sai ném `ProductionProfileError` lúc dựng. Không có hằng loudness trong mã sản xuất mới.
- `prepare_music` đo loudnorm JSON, chuẩn hoá hai pass (`linear=true`, `-ar` theo nguồn, WAV `pcm_s16le`), đo lại; true peak vượt trần thì hạ đúng một lần bằng `volume` đúng phần vượt rồi đo lại. Độ dài đọc từ header WAV; tệp `prep-*` xoá trong `finally`.
- Bản lưu là bản đã chuẩn hoá `music-<rendition_sha256>.audio`; sha256 nguồn vẫn phải khớp sha256 ghim theo URL. Sidecar cũ thiếu `rendition_sha256` bị bỏ qua.
- `ProductionHttpsTransport` tự phân giải (tiêm được `resolve`, mặc định `socket.getaddrinfo`), từ chối URL không https, có thông tin đăng nhập, cổng khác 443, phân giải rỗng hoặc có địa chỉ không global (`music_url_not_allowed`) trước mọi kết nối; kết nối đúng địa chỉ đã kiểm bằng `http.client` với TLS SNI theo host; một GET, không theo chuyển hướng.

## 4. RED và GREEN

- RED (bước 7, trên HEAD chưa sửa mã nguồn), lệnh `python -m pytest tests/integration/prod_wiring/test_pw_e4_fix1_music_bed.py -q -p no:cacheprovider`: exit 1, dòng tổng kết `15 failed, 1 passed in 5.90s`.
  - Nhóm dùng `voice_activity_deps` (sfx/music, hai ca loud và wide_lra, fallback 500, MP3 im lặng, thiếu lra): hỏng vì `TypeError: voice_activity_deps() got an unexpected keyword argument 'music_sources'`.
  - Chín ca transport: hỏng vì `ProductionHttpsTransport` chưa nhận `resolve`.
  - Ca duy nhất đạt: docstring khai báo coveredIds.
- GREEN (bước 18, sau khi sửa): cả 16 ca của tệp mới đạt; dòng tổng kết của lệnh ba tệp: `56 passed, 89 subtests passed in 15.60s`, exit 0.

### LUFS và dBTP trước và sau chuẩn hoá (mục tiêu hồ sơ: -16 LUFS, TP -1,5, LRA 11; cửa sổ -17,5..-14,5 LUFS, TP tối đa -1,5)

Đo bằng loudnorm print_format=json độc lập trên FFmpeg ghim:

| MP3 thử | Trước (LUFS / dBTP / LRA) | Sau (LUFS / dBTP / LRA) |
| --- | --- | --- |
| loud (sine 55 Hz, volume 7.6) | -7,95 / -0,89 / 0,00 | -15,95 / -8,85 / 0,00 |
| wide_lra (nhiễu hồng, nửa sau giảm 0,15) | -23,27 / -9,44 / 16,60 | -16,37 / -1,50 / 11,60 |
| tone_220 (ca sfx, sine 220 Hz, volume 0.3) | -32,95 / -28,96 / 0,00 | -16,05 / -12,06 / 0,00 |

Báo cáo loudness của `prepare_music` khớp số đo độc lập (trong 0,05); không còn tệp `prep-*` sau mọi ca.

## 5. Lệnh kiểm đã chạy

Interpreter khoá của lane, `PYTEST_DEBUG_TEMPROOT` riêng của lượt.

| Lệnh | Exit | Kết quả thật |
| --- | --- | --- |
| `git diff --check` | 0 | Không có lỗi khoảng trắng |
| pytest test_pw_e4_fix1_music_bed + test_pw_e4_audio_bed + test_e01_package_layout | 0 | `56 passed, 89 subtests passed in 15.60s` |
| pytest test_pw_w2_launcher_def + test_pw_e3_media_inputs + test_pw_e1_persistence | 0 | `31 passed in 16.52s` |
| pytest ADAPT-E-MEDIA (tools, safety_scores) + E-17 + E-18 | 0 | `196 passed in 0.88s` |
| pytest ADAPT-WIRE + ADAPT-CONFIG | 0 | `152 passed in 9.87s` |
| pytest test_pw_e2e_batch_video | 0 | `10 passed, 1 warning in 126.47s (0:02:06)` |
| pytest tests/unit | 0 | `7607 passed, 1 warning, 2561 subtests passed in 23.18s` |
| probe wiring voice.py | 0 | Không assert nào đỏ |
| probe audio_bed_source.py | 0 | Không assert nào đỏ |
| probe real_ffmpeg_media_tool.py (I=-16 đúng một lần) | 0 | Không assert nào đỏ |
| probe test_pw_e4_fix1_music_bed.py | 0 | Không có monkeypatch, loudness_meter |
| probe quét mẫu cũ toàn repo | 0 | Danh sách vi phạm rỗng |
| probe bố cục CP2A-LAYOUT | 0 | Không assert nào đỏ |
| probe báo cáo (PW-E4-FIX1, OI-PW-E4-02) | 0 | Chạy sau khi ghi báo cáo |

## 6. GIẢ ĐỊNH và giới hạn

- Hai URL ghim thật chưa kiểm vì không có mạng: chuyển hướng hay lệch sha256 vẫn ra `none`. Lượt RG-09 sau phải đo `bed_kind`.
- Đường kết nối TLS thật của `ProductionHttpsTransport` chưa chạy được offline; test chỉ phủ đường từ chối chính sách và địa chỉ không global.
- SFX vẫn im lặng vì kế hoạch chưa có nguồn SFX.
- Render chưa trộn bed vào mp4 (`mix_plan={}` ở `wiring/render.py:527`; `render_command.py:305-306` chỉ trộn giọng và hook): video chỉ có nhạc sau một gói render riêng. Đó là việc của gói render riêng, không thuộc gói này.
- e2e vẫn trả WAV im lặng nên đi đường `none`; đường nhạc do test mới phủ.
- MP3 loud dựng bằng sine 55 Hz vì nhiễu hồng không đạt -8 LUFS cùng -0,9 dBTP (bão hoà quanh -10 LUFS); hằng được chỉnh một lần ngoại tuyến và cố định trong test, cửa sổ hồ sơ không bị nới.

## 7. Mục mở còn lại

- OI-PW-E4-02: ĐÃ ĐÓNG bởi PW-E4-FIX1.
- OI-PW-E4-01 và OI-PW-E4-03 giữ nguyên.
