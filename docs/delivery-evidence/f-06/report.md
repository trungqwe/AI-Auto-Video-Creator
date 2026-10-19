# Báo cáo bằng chứng F-06

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `5795450216f7b989a15d6b4c3db78276b594f113`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-06 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `93 failed, 11 passed in 0.85s`
- Chi tiết các dòng FAILED tiêu biểu từ bước 6:
  - `FAILED tests/unit/render/test_f06_preconditions_hooks_timeline.py::test_visual_hook_missing[value0]`: `AssertionError: assert () == (Finding(condition=1, code='visual_hook_missing', field='hook_placement.visual_hook_ref'),)`
  - `FAILED tests/unit/render/test_f06_preconditions_hooks_timeline.py::test_audio_hook_missing[value0]`: `AssertionError: assert () == (Finding(condition=2, code='audio_hook_missing', field='hook_placement.audio_hook_ref'),)`
  - `FAILED tests/unit/render/test_f06_preconditions_hooks_timeline.py::test_thumbnail_missing[value0]`: `AssertionError: assert () == (Finding(condition=3, code='thumbnail_missing', field='hook_placement.thumbnail_ref'),)`
  - `FAILED tests/unit/render/test_f06_preconditions_hooks_timeline.py::test_missing_voice_or_timing[None-timing0-expected0]`: `AssertionError: assert [] == [('voice_missing', 'voice_artifact_ref')]`
  - `FAILED tests/unit/render/test_f06_preconditions_hooks_timeline.py::test_segment_without_visual[value0]`: `AssertionError: assert () == (Finding(condition=6, code='timeline_segment_without_visual', field='timeline.segments[0].visual_asset_refs'),)`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 11 test hợp lệ (fixture hợp lệ trả (), frozen, hằng, import stdlib, coveredIds) đã PASS ngay từ đầu. Tất cả 93 test thất bại đều là `AssertionError` do khung skeleton chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `104 passed in 0.15s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/render/domain/preconditions_media.py`: Cài đặt các hằng số điều kiện (1, 2, 3, 4, 6), các hằng số mã lỗi, dataclass frozen `Finding`, hai DTO `VoiceTrackInfo` và `WordTimingInfo`, cùng ba hàm kiểm tra tiền điều kiện thuần domain không I/O `check_hook_preconditions`, `check_voice_timing_binding`, `check_timeline_coverage`.
  - `tests/unit/render/test_f06_preconditions_hooks_timeline.py`: Bộ kiểm thử toàn diện gồm 104 test cases kiểm tra đầy đủ các điều kiện hook, thumbnail (biên bao gồm, không hằng 0-3 giây), kiểm tra time range hợp lệ/bất hợp lệ, thứ tự cố định của findings, ràng buộc voice/timing với render package (thiếu ref, lệch fingerprint/hash/version), và kiểm tra độ phủ timeline (yêu cầu visual assets cho từng segment, start < end, xử lý segments rỗng/sai kiểu) cùng ranh giới import stdlib.
  - `docs/delivery-evidence/f-06/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider` | 0 | `104 passed in 0.15s` |
| 2 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | `12 passed, 75 subtests passed in 0.09s` |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Finding.condition là số điều kiện CT-RND-003 (1 visual hook, 2 audio hook, 3 thumbnail và time range, 4 voice và timing, 6 timeline).
2. thumbnail_missing chỉ khi thumbnail_ref trống; range thumbnail chỉ kiểm khi có ref; hook_time_range luôn kiểm.
3. Range hợp lệ: Mapping có start_ms và end_ms là int không phải bool, start >= 0, start < end (độ dài 0 là sai).
4. Một trong hai range sai thì không phát thumbnail_outside_hook_range, chỉ phát time_range_invalid (hook trước thumbnail).
5. RenderPackageRecord không mang script_fingerprint hay voice_hash: package đối chiếu qua voice_artifact_ref, word_timing_ref, script_version_ref; fingerprint và hash so giữa voice và timing; mỗi trường lệch một finding; chuỗi rỗng hai bên không khớp; voice/timing không phải DTO hoặc package thiếu ref coi là missing.
6. timeline_segments_invalid là mã bổ sung fail-closed cho segments thiếu hoặc sai kiểu (GIẢ ĐỊNH shape, CONV-F-07); phần tử segment không phải Mapping coi như thiếu visual và range sai.
7. Không đặt giá trị policy hay hằng 0-3 giây trong mã.

## Ánh xạ phản ví dụ

- Thumbnail 0-3 giây cố định -> `test_thumbnail_range_is_inside_hook_range_not_fixed_three_seconds`
- Thiếu audio hook vẫn qua -> `test_audio_hook_missing`
- Voice đổi mà timing cũ vẫn chấp nhận -> `test_changed_hash_or_fingerprint_is_mismatch`
- Segment không visual vẫn qua -> `test_segment_without_visual`

## coveredIds

- `CT-RND-003 (1-4, 6)`
- `TST-MEDIA-INV-007 (phía F)`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Mở rộng shape hook_placement và timeline.segments qua CONV-F-07
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Chỉ stdlib.
- Không gọi dịch vụ thật.
