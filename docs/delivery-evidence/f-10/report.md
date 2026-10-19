# Báo cáo bằng chứng F-10

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `23a1c347fc8abac60f20946be6e4c6155747995d`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-10 trong `docs/implementation/f/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider` (chạy trên stub trung tính ở bước 2)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `151 failed, 3 passed in 2.14s`
- Các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/render/test_f10_render_command_spec.py::test_render_command_structure`: `AssertionError: assert () == ('C:/tools/ffmpeg.exe',)`
  - `FAILED tests/unit/render/test_f10_render_command_spec.py::test_filter_graph_is_built_from_structured_parts`: `AssertionError: assert '-filter_complex' in ()`
  - `FAILED tests/unit/render/test_f10_render_command_spec.py::test_missing_profile_field_is_input_not_ready[width]`: `Failed: DID NOT RAISE RenderCommandRejected`
  - `FAILED tests/unit/render/test_f10_render_command_spec.py::test_unsafe_argument_text_is_rejected_everywhere[a;b]`: `Failed: DID NOT RAISE RenderCommandRejected`
  - `FAILED tests/unit/render/test_f10_render_command_spec.py::test_thumbnail_command_uses_the_middle_of_the_thumbnail_range`: `AssertionError: assert ()`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED do assertion hoặc DID NOT RAISE.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `154 passed in 0.20s`

## Thay đổi

- `src/render/domain/render_command.py`: OutputProfile, ToolIdentity, MaterializedPaths, RenderCommandSpec (frozen; to_dict và to_json chỉ xuất redacted_argv), RenderCommandRejected, build_render_command, build_thumbnail_command.
- `tests/unit/render/test_f10_render_command_spec.py`: 20 hàm test, 154 test cases đã chạy (gồm các cases tham số hoá cho profile, tool, unsafe texts, outside paths, manifest, thumbnail).
- `docs/delivery-evidence/f-10/report.md`: báo cáo này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider` | 0 | 154 passed in 0.20s |
| 2 | `python -m pytest tests/unit/render -q -p no:cacheprovider` | 0 | 763 passed, 370 subtests passed in 1.12s |
| 3 | probe không còn marker STUB- | 0 | PASS (không AssertionError, không còn marker STUB-) |
| 4 | `git diff --check` | 0 | PASS (không có output, không lỗi định dạng diff) |
| 5 | probe tiếng Việt của report.md (bước 24) | 0 | PASS (tiếng Việt đầy đủ dấu, không có ký tự thay thế) |

## Quyết định mặc định (D8)

1. `materialization_manifest` là ánh xạ ref → mapping có `local_ref` (đường dẫn tương đối hoặc tuyệt đối nằm trong staging root); hình dạng này là GIẢ ĐỊNH F-local, hội tụ qua CONV-F-07.
2. `MaterializedPaths` mang staging_root, output_path, thumbnail_path do I cấp; kiểm lexical bằng `_inside_staging_root` của F-07, kiểm symlink thật thuộc I và CP7.
3. Mỗi segment lấy rendition đầu tiên làm đầu vào; mọi ref trong segment đều phải có trong manifest; GIẢ ĐỊNH các rendition đã cắt đúng độ dài và cùng kích thước nên dùng concat không trim.
4. Filter graph là một chuỗi duy nhất, không dùng dấu chấm phẩy (argv cấm dấu chấm phẩy); đường dẫn ASS giới hạn ký tự an toàn và được thoát dấu hai chấm.
5. Chỉ dựng track voice; mix_plan, nhạc, SFX và các section của preset chưa được dựng thành tham số (preset chỉ gắn vào fingerprint); đây là mục mở, phụ thuộc ROADMAP-OPEN-009.
6. Dùng `-n` (không ghi đè) và không dùng `-y`, vì mỗi attempt có artifact mới.
7. width, height, bitrate là số nguyên dương; fps là số nguyên hoặc số thực hữu hạn dương; chuỗi codec, container, pixel_format, encoder phải khớp định danh an toàn và không bắt đầu bằng dấu gạch ngang.
8. Thumbnail lấy thời điểm giữa thumbnail_time_range (số nguyên ms), bắt buộc nằm trong hook_time_range.
9. `argv` không nằm trong repr, to_dict, to_json; fingerprint tính bằng request_hash trên redacted_argv, fingerprint của package và preset, profile, tool name/version/build, không chứa đường dẫn attempt.

## Ánh xạ phản ví dụ

- Title chứa `; rm -rf` lọt vào argv → `test_text_metadata_never_reaches_argv_and_subtitles_go_only_through_ass`, `test_unsafe_argument_text_is_rejected_everywhere`.
- URL tùy ý làm input → `test_assets_outside_the_manifest_are_rejected`, `test_unsafe_argument_text_is_rejected_everywhere`.
- Spec đặt cứng 1920x1080 → `test_profile_values_come_only_from_the_profile_input`, `test_module_holds_no_profile_values_and_builds_no_command_string`.
- Canary lộ trong redacted_argv → `test_canary_metadata_never_appears_in_any_view`, `test_canary_in_a_path_is_redacted_in_every_view_except_argv`.

## coveredIds

- `CT-RND-004`, `TST-SEC-INV-012`, `TST-SEC-INV-020` (phía F), acceptance §8 mục 6.

## Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-007 (output profile), ROADMAP-OPEN-009 (preset), TECH-OPEN-012 (ffmpeg, xác minh ở CP7).
- USER-CKPT-D9-D10.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Không chạy ffmpeg thật, không gọi dịch vụ thật; chỉ dựng đặc tả lệnh.
