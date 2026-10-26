# Báo cáo Nghiệm thu PW-E2: Một quy tắc tên WAV duy nhất, LocalVoiceRoute, PostgresScriptText và thời lượng WAV

## 1. Mục tiêu và phạm vi PW-E2
- **Mục tiêu:**
  + Triển khai một quy tắc tên duy nhất cho tệp WAV (DQ-13): Kokoro chỉ ghi tạm trong `<voice root>/tmp/<sha256>.wav`, `VoicePipeline` gọi `place_artifact` (do `VoiceArtifactPlacer` cài đặt) để đổi tên tệp thành `voice-artifact-<sha256>` trong thư mục gốc `voice_root` trước khi commit UoW; `RealWhisperAligner` nhận `voice_root` qua constructor và chỉ mở đúng tên `voice-artifact-<sha256>`.
  + Cài đặt `LocalVoiceRoute` thực thi `VoiceRoutePort`: chỉ quyết định tuyến Kokoro cục bộ (`kokoro-local`, `kokoro-v1.0`, `local`), không có đường mạng, không dùng fallback, credential `none`, chi phí `free`.
  + Cài đặt `PostgresScriptText` thực thi `ScriptTextPort`: đọc bảng `controlplane.cp_script_versions` theo `workspace_id` và `script_version_id`, nối văn bản các đoạn kịch bản và tính lại `script_fingerprint` theo quy tắc phân hệ D; không lấy dữ liệu từ payload lệnh.
  + Cài đặt `wav_duration.py`: đo thời lượng WAV chính xác từ header và số lượng mẫu PCM bằng thư viện chuẩn `wave` (mili giây = số khung * 1000 // tần số), từ chối các tệp WAV hỏng, cụt, rỗng hoặc 0 khung bằng `InvalidWavError`.
  + Sửa đúng ba chỗ assertion của test đã nghiệm thu `tests/integration/adapt/e/test_adapt_e_tts_aligner.py` để khớp với quy tắc thư mục `tmp` của DQ-13.
- **Phạm vi:** 9 tệp thuộc owned paths được giao:
  + `src/voice/adapters/real_kokoro_tts.py`
  + `src/voice/adapters/real_whisper_aligner.py`
  + `src/voice/application/voice_pipeline.py`
  + `src/voice/adapters/local_voice_route.py`
  + `src/voice/adapters/postgres_script_text.py`
  + `src/voice/adapters/wav_duration.py`
  + `tests/integration/prod_wiring/test_pw_e2_voice_ports.py`
  + `tests/integration/adapt/e/test_adapt_e_tts_aligner.py`
  + `docs/delivery-evidence/pw-e2/report.md`

## 2. Tệp đã đổi
- `src/voice/adapters/real_kokoro_tts.py`: Ghi tệp WAV tạm vào thư mục `tmp`, loại bỏ tiền tố `tts-`, thêm `VoiceArtifactPlacer` để đổi tên tệp tạm thành `voice-artifact-<sha256>`.
- `src/voice/adapters/real_whisper_aligner.py`: Hỗ trợ `voice_root` trong `WhisperAlignerConfig`, mở chính xác tệp `voice-artifact-<sha256>`, từ chối các tên khác với mã lỗi `voice_unavailable`.
- `src/voice/application/voice_pipeline.py`: Bổ sung tham số tùy chọn `place_artifact`, gọi placer đặt tên artifact WAV trước khi commit UoW.
- `src/voice/adapters/local_voice_route.py`: Cài đặt `LocalVoiceRoute` chỉ trả quyết định Kokoro cục bộ, không đường mạng.
- `src/voice/adapters/postgres_script_text.py`: Cài đặt `PostgresScriptText` đọc kịch bản từ PostgreSQL thật.
- `src/voice/adapters/wav_duration.py`: Đo thời lượng tệp WAV bằng stdlib `wave` từ số khung mẫu và tần số.
- `tests/integration/prod_wiring/test_pw_e2_voice_ports.py`: Bộ test tích hợp mới kiểm chứng các cổng và quy tắc DQ-13 trên PostgreSQL thật (`coveredIds: PW-E2-01, CT-MED-007`).
- `tests/integration/adapt/e/test_adapt_e_tts_aligner.py`: Cập nhật đúng ba assertion theo quy tắc thư mục tạm mới.
- `docs/delivery-evidence/pw-e2/report.md`: Báo cáo nghiệm thu kỹ thuật bằng chứng.

## 3. Quy tắc tên DQ-13
- Adapter Kokoro (`RealKokoroTts`) chỉ ghi tệp âm thanh tạm thời vào đường dẫn `<voice root>/tmp/<sha256 của bytes WAV>.wav`. Khi bắt đầu gọi `synthesize`, thư mục `tmp` được đảm bảo tồn tại sẵn. Toàn bộ tiền tố cũ `tts-<hash>` bị loại bỏ hoàn toàn.
- `VoicePipeline` nhận hàm `place_artifact` tùy chọn (được cài đặt bởi `VoiceArtifactPlacer`). Sau khi tổng hợp âm thanh thành công, pipeline gọi `place_artifact("voice-artifact-" + voice_hash, audio_bytes)` để di chuyển / đổi tên tệp tạm thành `<voice root>/voice-artifact-<sha256>` trước khi ghi nhận giao dịch UoW. Thao tác này là idempotent: nếu tệp đích đã tồn tại với nội dung đúng hash, placer trả về ngay đường dẫn hợp lệ.
- Bộ căn chỉnh `RealWhisperAligner` khi cấu hình với `voice_root` sẽ chỉ mở tệp `<voice root>/voice-artifact-<sha256>`. Nếu tham chiếu tên tệp không khớp mẫu hoặc trỏ ra ngoài thư mục qua đường dẫn tương đối, adapter từ chối fail-closed với lỗi `voice_unavailable`.

## 4. Ba dòng đã đổi của test đã nghiệm thu `test_adapt_e_tts_aligner.py`
Không xóa test, không đổi bất kỳ assertion nào khác, không sửa docstring của tệp test. Ba vị trí thay đổi cụ thể:

1. **Dòng 145-147 trong `test_synthesize_writes_mono_pcm_wav_with_configured_parameters`:**
   - *Dòng cũ:*
     ```python
         staged = list(tts_env.staging.glob('*.wav'))
         assert len(staged) == 1 and staged[0].read_bytes() == result.audio_bytes
         assert list(tts_env.staging.glob('*.part')) == []
     ```
   - *Dòng mới:*
     ```python
         staged = list((tts_env.staging / 'tmp').glob('*.wav'))
         assert len(staged) == 1 and staged[0].read_bytes() == result.audio_bytes and staged[0].name == sha(result.audio_bytes) + '.wav'
         assert list((tts_env.staging / 'tmp').glob('*.part')) == [] and list(tts_env.staging.glob('*.wav')) == []
     ```
   - *Lý do:* Theo DQ-13, Kokoro chỉ ghi tạm trong thư mục `tmp` với tên `<sha256>.wav` và không để bất kỳ tệp `.wav` nào ở thư mục staging gốc.

2. **Dòng 179 trong `test_sha256_mismatch_is_rejected_before_loading`:**
   - *Dòng cũ:*
     ```python
         assert list(tts_env.staging.iterdir()) == []
     ```
   - *Dòng mới:*
     ```python
         assert list(tts_env.staging.iterdir()) == [tts_env.staging / 'tmp'] and list((tts_env.staging / 'tmp').iterdir()) == []
     ```
   - *Lý do:* Adapter tạo sẵn thư mục `tmp` ngay khi bắt đầu tổng hợp; khi việc nạp weights bị từ chối trước đó, staging chỉ chứa thư mục `tmp` rỗng.

3. **Dòng 225 trong `test_sample_rate_mismatch_and_empty_audio_are_rejected`:**
   - *Dòng cũ:*
     ```python
         assert list(tts_env.staging.iterdir()) == []
     ```
   - *Dòng mới:*
     ```python
         assert list(tts_env.staging.iterdir()) == [tts_env.staging / 'tmp'] and list((tts_env.staging / 'tmp').iterdir()) == []
     ```
   - *Lý do:* Tương tự như trên, thư mục `tmp` đã được tạo sẵn và bên trong không có tệp nào khi audio rỗng hoặc tần số mẫu không khớp.

## 5. Quyết định mặc định theo D8
- `LocalVoiceRoute.resolve`: Bỏ qua nội dung của trường `allowed_fallbacks` từ request vì danh sách này do thượng nguồn sinh ra và chưa có đặc tả cho việc chuyển tuyến dự phòng; tuyến luôn trả về `fallback_order=()` và chỉ định nhà cung cấp cục bộ `kokoro-local`.
- `PostgresScriptText.get_text`: Vì bảng `controlplane.cp_script_versions` lưu payload JSON mà không có cột fingerprint riêng, adapter tính lại `script_fingerprint` bằng hàm canonicalization `request_hash({'narration': narration})` theo đúng quy tắc của phân hệ D.
- `VoicePipeline.__init__`: Tham số `place_artifact` là tùy chọn (`None` theo mặc định) nhằm bảo toàn tương thích ngược cho các bài kiểm thử unit/integration hiện hành không tiêm placer.
- `measure_wav_duration_ms`: Thời lượng được tính bằng phép chia nguyên `frames * 1000 // sample_rate`, làm tròn xuống số mili giây nguyên theo chuẩn mẫu; các tệp có 0 frame hoặc dữ liệu không đủ theo header đều bị coi là không hợp lệ.
- Dọn dẹp tệp tạm: Nếu pipeline từ chối tệp âm thanh do chính sách thời lượng, tệp tạm trong `tmp/<sha>.wav` được giữ lại để tiến trình dọn dẹp của phân hệ I thu hồi sau, không gây ảnh hưởng đến tính toàn vẹn của voice root.

## 6. Mục mở
- **PW-W2 (wiring):** Cần truyền `place_artifact=VoiceArtifactPlacer(voice_root)` cho `VoicePipeline` và `voice_root=voice_root` cho `WhisperAlignerConfig` khi dựng composition root sản xuất.
- **CT-MED-007:** Gán cho slice PW-E2 theo `docs/implementation/prod-wiring/slices.md` dòng 411 để xác thực việc đo thời lượng tệp âm thanh WAV độc lập bằng số khung mẫu.

## 7. Bảng bằng chứng
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra:

| Bước | Lệnh kiểm tra | Exit Code | Kết quả thực tế | Ghi chú |
| --- | --- | --- | --- | --- |
| Bước 2 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` | 1 | 4 failed, 30 passed in 0.77s | RED đúng oracle: thất bại ở assertion thư mục `tmp` do Kokoro cũ chưa ghi vào `tmp` |
| Bước 5 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` | 0 | 34 passed in 0.49s | GREEN: Kokoro ghi tệp tạm vào `tmp`, đạt toàn bộ assertion mới |
| Bước 16 | `python -m pytest tests/integration/prod_wiring/test_pw_e2_voice_ports.py -q -p no:cacheprovider` | 1 | 6 failed, 2 passed, 2 errors in 1.72s | RED đúng oracle: bản khung ném `NotImplementedError`, `WhisperAlignerConfig` thiếu `voice_root` |
| Bước 22 | `python -m pytest tests/integration/prod_wiring/test_pw_e2_voice_ports.py tests/integration/adapt/e/test_adapt_e_tts_aligner.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 60 passed, 89 subtests passed in 2.00s | GREEN: Toàn bộ test integration cổng voice, test adapt E và package layout đạt 100% |
| Bước 23 | `python -c "import pathlib; t = pathlib.Path('src/voice/application/voice_pipeline.py').read_text(encoding='utf-8'); assert 'voice-artifact-' in t and 'from src.' not in t, 'PW-E2'"` | 0 | Đạt (PASS) | Kiểm tra tĩnh: `voice-artifact-` có mặt, không import `from src.` |
| Bước 24 | `python -c "import pathlib; a = pathlib.Path('src/voice/adapters/real_whisper_aligner.py').read_text(encoding='utf-8'); k = pathlib.Path('src/voice/adapters/real_kokoro_tts.py').read_text(encoding='utf-8'); m = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/voice/adapters/wav_duration.py', 'src/voice/adapters/local_voice_route.py', 'src/voice/adapters/postgres_script_text.py']); assert 'voice-artifact-' in a and 'voice_root' in a and 'tts-' not in a and 'voice-artifact-' in k and 'NotImplementedError' not in m and 'import wave' in m and 'cp_script_versions' in m and 'kokoro-local' in m and 'from src.' not in a + k + m, 'PW-E2 names'"` | 0 | Đạt (PASS) | Kiểm tra đọc-chỉ xác nhận toàn bộ quy tắc tên và loại bỏ bản khung |
| Bước 25 / 28 | `git diff --check` | 0 | Đạt (PASS) | Không có khoảng trắng thừa cuối dòng hay lỗi ký tự xuống dòng |

## 8. Ánh xạ coveredIds sang các test trong `test_pw_e2_voice_ports.py`

| Covered ID | Mô tả nghiệm thu | Các test tương ứng trong test_pw_e2_voice_ports.py |
| --- | --- | --- |
| `PW-E2-01` | Một quy tắc tên WAV duy nhất (DQ-13), LocalVoiceRoute, PostgresScriptText và thời lượng WAV đo từ mẫu trên PostgreSQL thật | `test_pw_e2_wav_duration_is_measured_from_samples_rate_and_channels`, `test_pw_e2_wav_duration_rejects_broken_wav`, `test_pw_e2_local_voice_route_resolves_only_local_kokoro`, `test_pw_e2_script_text_is_read_from_cp_script_versions_by_script_ref`, `test_pw_e2_pipeline_places_the_wav_as_voice_artifact_and_aligner_opens_that_name`, `test_pw_e2_replayed_command_keeps_the_single_artifact`, `test_pw_e2_aligner_opens_only_the_voice_artifact_name`, `test_pw_e2_aligner_config_requires_exactly_one_audio_source`, `test_pw_e2_placer_moves_the_temp_wav_to_the_artifact_name_and_refuses_other_names`, `test_pw_e2_voice_pipeline_names_the_artifact_and_stays_free_of_io` |
| `CT-MED-007` | Đo thời lượng WAV độc lập bằng stdlib `wave` từ số khung mẫu, tần số và số kênh; từ chối WAV hỏng, cụt, rỗng | `test_pw_e2_wav_duration_is_measured_from_samples_rate_and_channels`, `test_pw_e2_wav_duration_rejects_broken_wav` |
