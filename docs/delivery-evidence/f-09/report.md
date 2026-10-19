# Báo cáo bằng chứng F-09

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `a461b76e086b8d41ce4f0607da1e2c2460d3c90f`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-09 trong `docs/implementation/f/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider` (chạy trên stub trả giá trị trung tính ở bước 10)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `108 failed, 3 passed, 1 skipped in 1.49s`
- Vài FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/render/test_f09_karaoke_plan.py::test_constants_match_binding`: `AssertionError: assert ({}, {}, {}) == ({'script_ver...s': 'object'})`
  - `FAILED tests/unit/render/test_f09_karaoke_plan.py::test_fixture_valid_payload_parses`: `assert False where False = isinstance(None, ConsumerWordTiming)`
  - `FAILED tests/unit/render/test_f09_karaoke_plan.py::test_fixture_invalid_payload_reports_expected_error[words_out_of_order]`: `AssertionError: assert [] == [('constraint_violation', 'words')]`
  - `FAILED tests/unit/render/test_f09_karaoke_plan.py::test_fixture_invalid_payload_reports_expected_error[missing_voice_hash]`: `AssertionError: assert [] == [('missing_required', 'voice_hash')]`
  - `FAILED tests/unit/render/test_f09_karaoke_plan.py::test_plan_is_frozen_hashable_and_keeps_marks`: `AssertionError: assert False where False = isinstance(None, KaraokePlan)`
  - `FAILED tests/unit/render/test_f09_karaoke_plan.py::test_missing_section_is_input_not_ready[typography]`: `Failed: DID NOT RAISE KaraokePlanRejected`
  - `FAILED tests/unit/render/test_f09_karaoke_plan.py::test_fixture_payload_renders_exact_ass_text`: `AssertionError: assert '' == '[Script Info...{\\k48}news\n'`
  - `FAILED tests/unit/render/test_f09_karaoke_plan.py::test_word_text_cannot_inject_overrides_or_lines`: `AssertionError: assert 0 == (13 + 8)`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection (RED chạy trên stub trả giá trị trung tính, thất bại do assertion và hành vi chưa cài đặt).

## Thay đổi

- Ba tệp thuộc owned paths:
  - `src/render/domain/karaoke_plan.py`: Cài đặt miền nghiệp vụ kế hoạch karaoke và render văn bản ASS:
    - `parse_word_timing` và `word_timing_issues`: Kiểm tra tính hợp lệ của payload WordTiming ở ranh giới consumer (hằng chép từ E-09 vì render không được phép import module voice; test đối chiếu với binding JSON); kiểm tra các trường bắt buộc, kiểu dữ liệu, thứ tự thời gian đơn điệu, từ sau không bắt đầu trước khi từ trước kết thúc, và không vượt `voice_duration_ms`; trả về `ConsumerWordTiming` frozen.
    - `build_karaoke_plan`: Tiếp nhận words (hoặc `ConsumerWordTiming`), `typography`, `safe_area`, `profile`; kiểm tra tính sẵn sàng của đầu vào (thiếu trả về `KaraokePlanRejected` với mã `INPUT_NOT_READY`, sai kiểu trả về `INVALID_INPUT`); chia dòng tham lam theo `max_words_per_line` và `max_chars_per_line`, giữ nguyên mốc highlight từng từ; trả về `KaraokePlan` frozen.
    - `render_ass`: Sinh chuỗi định dạng ASS v4.00+ xác định gồm 3 phần `[Script Info]`, `[V4+ Styles]`, `[Events]`; mốc thời gian làm tròn nửa lên sang centisecond; thẻ `{\k}` tính từ hiệu mốc đã làm tròn bảo đảm tổng thẻ khớp chính xác khoảng thời gian của dòng mà không trôi sai số tích lũy; khoảng trống giữa các từ mã hóa bằng thẻ `\k` rỗng; thoát các ký tự override `{`, `}`, `\` bằng ký tự fullwidth và thay ký tự điều khiển bằng dấu cách.
  - `tests/unit/render/test_f09_karaoke_plan.py`: Bộ kiểm thử toàn diện gồm 118 test:
    - Nhóm 1 (test binding và fixture WordTiming): kiểm tra khớp hằng với binding JSON, đầy đủ các ca lỗi fixture (`words_out_of_order`, `word_beyond_voice_duration`, `missing_voice_hash`), ca hợp lệ, kiểu dữ liệu không phải object, thiếu trường bắt buộc, bỏ qua trường lạ, không mutate payload.
    - Nhóm 2 (test chi tiết từng từ): kiểm tra từ kết thúc trước hoặc bằng thời điểm bắt đầu, start âm, hai từ chồng lấn, span trùng lặp, vượt duration, danh sách rỗng, kiểu bool/float, text rỗng/khoảng trắng rơi về `normalized_text`, segment boundaries.
    - Nhóm 3 (cấu trúc KaraokePlan và xác thực đầu vào): kiểm tra tính bất biến frozen và băm hashable, chia dòng theo số từ tối đa, chia dòng theo số ký tự tối đa, từ quá dài đứng riêng một dòng, chấp nhận `ConsumerWordTiming`, không alias đầu vào, thiếu section hoặc key ném `INPUT_NOT_READY`, giá trị sai ném `INVALID_INPUT`, safe area vượt giới hạn PlayRes, từ không hợp lệ.
    - Nhóm 4 (render ASS và thẻ k): kiểm tra render chính xác với fixture payload, thẻ k tính từ hiệu mốc đã làm tròn, tổng thẻ k bằng thời lượng dialogue với mốc bất thường, khoảng trống là thẻ k rỗng, mốc thời gian làm tròn nửa lên, mỗi dòng một dialogue event riêng.
    - Nhóm 5 (chống chèn override và tính xác định): kiểm tra thoát mã chèn `{\an8}`, ngắt dòng, ký tự điều khiển; tính xác định cùng input cho cùng kết quả; đọc style từ input; từ chối đối tượng không phải plan.
    - Nhóm 6 (kiểm tra tĩnh AST): kiểm tra module chỉ import thư viện chuẩn cho phép (`re`, `unicodedata`, `collections.abc`, `dataclasses`, `types`), không chứa hằng font, màu hoặc kích thước đặt cứng.
  - `docs/delivery-evidence/f-09/report.md`: Báo cáo bằng chứng thực thi gói F-09.
- Phản ví dụ được loại trừ:
  - Từ chứa `{\an8}` chèn override bị thoát bằng ký tự fullwidth U+FF5B, U+FF3C, U+FF5D (`｛＼an8｝`).
  - Tổng thẻ `\k` lệch mốc cuối do làm tròn từng từ: Đã được xử lý bằng cách tính mốc từ hiệu mốc đã làm tròn nửa lên sang centisecond (test 14ms x 3 cho ra 4 centisecond thay vì 3 centisecond nếu cộng dồn làm tròn riêng lẻ).
  - Hai từ chồng lấn vẫn được chấp nhận: Bị chặn bởi kiểm tra `start < previous_end` trả `constraint_violation` trường `words`.
  - Font, màu, kích thước đặt cứng trong mã: Đã được kiểm chứng qua test AST tĩnh (chỉ cho phép các số `{0, 1, 2, 10, 60, 100}`, không có chuỗi mã màu `&H...`, không có tên font đặt cứng) và kiểm thử động đổi typography sinh ASS khác biệt.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider` | 0 | 118 passed in 0.13s |
| 2 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 75 subtests passed in 0.10s |
| 3 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/f-09/report.md').read_text(encoding='utf-8'); assert t.startswith('# ') and chr(65533) not in t and sum(ord(c) > 127 for c in t) > 100"` | 0 | PASS (không AssertionError, tiếng Việt đầy đủ dấu) |
| 4 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. typography gồm 19 khóa tương ứng trường style ASS, safe_area gồm margin_left, margin_right, margin_vertical, profile gồm max_words_per_line, max_chars_per_line, play_res_x, play_res_y; thiếu là INPUT_NOT_READY, sai kiểu là INVALID_INPUT.
2. chia dòng tham lam, từ dài hơn max_chars_per_line đứng riêng một dòng.
3. text rỗng thì lấy normalized_text, cả hai trống thì missing_required field words.
4. làm tròn nửa lên sang centisecond, thẻ k là hiệu mốc làm tròn, khoảng trống là thẻ k rỗng.
5. thoát bằng ký tự fullwidth thay cho { } và backslash, ký tự điều khiển Cc, Zl, Zp thành dấu cách.
6. WrapStyle 2 và Layer 0 là cấu trúc ASS cố định, không phải font, màu hay kích thước.
7. PrimaryColour là màu đã hát, SecondaryColour là màu chưa hát theo libass.
8. render_ass tin KaraokePlan do build_karaoke_plan tạo.

## Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-009
- ROADMAP-OPEN-008 (tolerance_ms karaoke)
- TECH-OPEN-012 (libass, xác minh ở CP7-F-02)
- USER-CKPT-D9-D10
- user checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- không chạy full suite, tests/m1, tests/m2;
- không đổi pyproject.toml, uv.lock;
- không thêm thư viện;
- không gọi dịch vụ thật;
- chưa dựng ASS bằng libass thật (CP7-F-02).
