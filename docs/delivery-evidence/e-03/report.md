# Báo cáo bằng chứng E-03

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: dd68637ba76c9e3213de9b564226e2e69f35f230
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-03 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 134 failed, 10 passed in 1.44s
- Chi tiết các nhóm test FAILED kèm thông điệp (tất cả do sai oracle, chưa hiện thực logic):
  - test_video_report_keeps_observed_technical_fields: AssertionError: assert <MediaType.UNKNOWN: 'unknown'> is <MediaType.VIDEO: 'video'>
  - test_audio_only_report: AssertionError: assert <MediaType.UNKNOWN: 'unknown'> is <MediaType.AUDIO: 'audio'>
  - test_image_report_without_duration: AssertionError: assert <MediaType.UNKNOWN: 'unknown'> is <MediaType.IMAGE: 'image'>
  - test_media_type_priority_video_then_audio_then_image: AssertionError: assert <MediaType.UNKNOWN: 'unknown'> is <MediaType.VIDEO: 'video'>
  - test_report_stream_and_color_are_frozen: IndexError: tuple index out of range (do khung tối thiểu trả streams=())
  - test_declared_type_never_overrides_observed_streams (12 ca): AssertionError: assert <MediaType.UNKNOWN: 'unknown'> is expected_type
  - test_missing_supported_streams_is_corrupt (4 ca): AssertionError: assert <Readability.READABLE: 'readable'> is <Readability.CORRUPT: 'corrupt'>
  - test_invalid_stream_duration_is_corrupt (15 ca bad duration): AssertionError: assert <Readability.READABLE: 'readable'> is <Readability.CORRUPT: 'corrupt'>
  - test_invalid_format_duration_is_corrupt (15 ca bad duration): AssertionError: assert <Readability.READABLE: 'readable'> is <Readability.CORRUPT: 'corrupt'>
  - test_zero_duration_is_valid_and_missing_duration_is_none: AssertionError: assert None == 0
  - test_invalid_stream_field_is_corrupt (16 ca trường số không hợp lệ): AssertionError: assert <Readability.READABLE: 'readable'> is <Readability.CORRUPT: 'corrupt'>
  - test_numeric_strings_and_zero_over_zero_frame_rate_are_accepted: IndexError: tuple index out of range
  - test_empty_dict_is_unreadable: AssertionError: assert <Readability.READABLE: 'readable'> is <Readability.UNREADABLE: 'unreadable'>
  - test_bad_observed_sha256_is_error (18 ca): Failed: DID NOT RAISE ProcessingContractError
  - test_bad_observed_size_is_error (5 ca): Failed: DID NOT RAISE ProcessingContractError
  - test_malformed_raw_or_declared_values_are_errors (13 ca): Failed: DID NOT RAISE ProcessingContractError
  - test_orientation_from_first_visual_stream (7 ca rotation hợp lệ): AssertionError: assert 0 == expected
  - test_invalid_rotation_is_corrupt (5 ca rotation sai): AssertionError: assert <Readability.READABLE: 'readable'> is <Readability.CORRUPT: 'corrupt'>
  - test_color_metadata_from_visual_streams: AssertionError: assert ColorMetadata(...) == ColorMetadata(...)
  - test_report_constructor_coerces_enums_and_tuples: Failed: DID NOT RAISE ProcessingContractError
  - test_report_constructor_rejects_inconsistent_values (15 ca bất biến sai): Failed: DID NOT RAISE ProcessingContractError
  - test_fake_probe_output_feeds_parse_probe_output: AssertionError: assert <MediaType.UNKNOWN: 'unknown'> is <MediaType.VIDEO: 'video'>
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (RED đạt chuẩn test-first).

## Thay đổi

- 4 tệp owned:
  - src/voice/domain/probe.py
  - src/voice/ports/probe.py
  - tests/unit/voice/test_e03_probe_media.py
  - docs/delivery-evidence/e-03/report.md
- Danh mục API đã triển khai:
  - ProbePort: typing.Protocol runtime_checkable với phương thức probe(self, artifact_ref: ArtifactRef) -> dict[str, object]
  - MediaType: enum.StrEnum (VIDEO, AUDIO, IMAGE, UNKNOWN)
  - StreamKind: enum.StrEnum (VIDEO, AUDIO, IMAGE)
  - Readability: enum.StrEnum (READABLE, CORRUPT, UNREADABLE)
  - ProbeStream: frozen dataclass (kind, codec, duration_ms, width, height, frame_rate, sample_rate, channels, pixel_format)
  - ColorMetadata: frozen dataclass (color_space, color_range, color_transfer, color_primaries)
  - ProbeReport: frozen dataclass (media_type, container, streams, duration_ms, readability, corruption_flags, orientation_degrees, color, observed_sha256, observed_size, warnings) kèm __post_init__ kiểm tra bất biến nghiêm ngặt (coercion enum/tuple, kiểm tra tính hợp lệ của cờ và streams theo readability, sha256 hex 64 ký tự, kích thước không âm, orientation trong ROTATIONS)
  - parse_probe_output: hàm thuần túy phân tích dữ liệu ffprobe giả lập không I/O, không gọi subprocess, trả về ProbeReport đông kết; phát hiện mâu thuẫn declared type/extension/mime mà không ghi đè dữ liệu quan sát

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider | 0 | 144 passed in 0.14s |
| 2 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 9 passed, 49 subtests passed in 0.05s |
| 3 | python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider | 0 | 65 passed in 0.07s |
| 4 | git diff --check | 0 | PASS (không output, không trailing whitespace) |

## Phản ví dụ đã loại trừ

1. **Tin extension png khi stream là video:** Loại trừ bởi `test_declared_type_never_overrides_observed_streams`; extension png hay mime image/png không bao giờ ghi đè kiểu stream thật (video), kết quả media_type giữ đúng MediaType.VIDEO và bổ sung cảnh báo `declared_type_mismatch`.
2. **Tệp hỏng ghi readable:** Loại trừ bởi `test_missing_supported_streams_is_corrupt` và `test_invalid_*_is_corrupt`; thiếu stream hỗ trợ, trường số bất thường hoặc duration sai khiến readability chuyển sang CORRUPT và đính kèm cờ lỗi tương ứng.
3. **Duration NaN/inf/âm được chấp nhận:** Loại trừ bởi `test_invalid_stream_duration_is_corrupt` và `test_invalid_format_duration_is_corrupt`; các giá trị NaN, vô cực (inf/-inf), số âm hoặc chuỗi không thể phân tích đều bị từ chối, duration chuyển thành None và cờ `invalid_duration` được bật.
4. **Module import subprocess:** Loại trừ bởi `test_module_has_no_subprocess_or_io`; AST audit tĩnh chứng minh cả src/voice/domain/probe.py và src/voice/ports/probe.py không import subprocess, os, sys, open hay bất kỳ lệnh I/O nào.

## Quyết định mặc định (D8)

- (a) raw mô phỏng ffprobe JSON gồm format.format_name, format.duration và streams[] với codec_type video/audio/image, codec_name, duration (giây), width, height, r_frame_rate, sample_rate, channels, pix_fmt, rotation, color_space, color_range, color_transfer, color_primaries; stream có codec_type khác bị bỏ qua.
- (b) duration đổi sang duration_ms làm tròn, duration báo cáo ưu tiên format rồi tới max của stream.
- (c) media type ưu tiên video > audio > image.
- (d) bảng extension→media type bỏ webm, ogg, gif vì mơ hồ; MIME chỉ xét phần trước dấu gạch chéo.
- (e) trường số stream sai (<=0, không hữu hạn, sai kiểu), rotation ngoài 0/90/180/270 → corrupt với cờ invalid_stream_field; duration sai → cờ invalid_duration; không có stream hỗ trợ → cờ no_streams; r_frame_rate '0/0' coi là vắng mặt.
- (f) orientation_degrees và color lấy từ stream hình ảnh/video đầu tiên có giá trị.
- (g) sha256 sai định dạng → wrong_type, thiếu → missing_required, size âm → constraint_violation (cùng quy ước E-02).
- (h) raw sai kiểu cấu trúc → ProcessingContractError chứ không thành corrupt.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: Phê duyệt thư viện cố định và cách dựng lại runtime.
- CP7-E-04 (ffprobe thật): Gọi nhị phân ffprobe thực tế khi phân hệ chuyển sang tầng infrastructure thật.
- CP7 tài nguyên thật (D5): Phê duyệt dịch vụ thật và tài nguyên external.
- User checkpoint M2 (P8/P9): Chưa ghi là đã duyệt từ phía user.

## Giới hạn

- Không chạy full suite, không chạy tests/m1, tests/m2.
- Không sửa đổi pyproject.toml hay uv.lock.
- Không gọi ffprobe, subprocess hay dịch vụ thật.
- Không sửa đổi migration hay composition root hay processing.py.
- Toàn bộ số liệu trong báo cáo là kết quả chạy thật trên môi trường hiện hành.
