# Báo cáo bằng chứng I-11

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d3b0cff0a6c39bb4cce7451ff61435358b50a768`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-11 trong `docs/implementation/i/slices.md`, CT-STO-011, D8-I-07, D8-I-08, binding `g-c-i-completion`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `98 failed, 10 passed, 21 subtests passed in 0.49s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn rút từ output bước 6:
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFolderTests::test_first_second_third_session`: `AssertionError: None != '26-10-19'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFolderTests::test_negative_count_is_rejected`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFolderTests::test_year_month_day_are_zero_padded`: `AssertionError: None != '27-01-05'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_control_characters_are_removed`: `AssertionError: 'a\x00b\tc\nd\x7fe.mp4' != 'abcde #one #two #three.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_emoji_is_kept`: `AssertionError: '\U0001f3ac Vlog.mp4' != '\U0001f3ac Vlog #one #two #three.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_empty_stem_falls_back_to_underscore`: `AssertionError: '.mp4' != '_.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_extension_is_sanitized`: `AssertionError: 'Hello..mp4' != 'Hello #one #two #three.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_forbidden_characters_become_underscore`: `AssertionError: 'a<b>c:d"e/f\\g|h?i*j.mp4' != 'a_b_c_d_e_f_g_h_i_j #one #two #three.mp4'`
  - `SUBFAILED(title='COM0'..'CONN') tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_non_reserved_lookalikes_are_untouched`: `AssertionError: '<title>.mp4' != '<title> #one #two #three.mp4'`
  - `SUBFAILED(title='../etc/passwd') tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_path_traversal_never_survives`: `AssertionError: '../etc/passwd.mp4' != '.._etc_passwd #one #two #three.mp4'`
  - `SUBFAILED(title='..\\..\\x') tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_path_traversal_never_survives`: `AssertionError: '..\\..\\x.mp4' != '.._.._x #one #two #three.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_plain_title`: `AssertionError: OutputName(sanitized_filename='Hello.mp4', collision_sequence=1, display_title='Hello', display_hashtags=('#one', '#two', '#three'), hash_mapping=()) != OutputName(sanitized_filename='Hello #one #two #three.mp4', collision_sequence=1, display_title='Hello', display_hashtags=('#one', '#two', '#three'), hash_mapping=())`
  - `SUBFAILED(title='CON'..'lpt9') tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_reserved_names_get_underscore_suffix`: `AssertionError: '<title>.mp4' != '<title>_ #one #two #three.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_trailing_dots_and_spaces_are_stripped`: `AssertionError: 'Hello.mp4' != 'Hello #one #two #three.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_vietnamese_is_nfc_but_display_keeps_original`: `AssertionError: 'Việt Nam.mp4' != 'Việt Nam #one #two #three.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameRulesTests::test_collision_appends_sequence_before_extension`: `AssertionError: Tuples differ: ('Hello.mp4', 1) != ('Hello #one #two #three (2).mp4', 2)`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameRulesTests::test_collision_ignores_case_and_normalization`: `AssertionError: 1 != 2`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameRulesTests::test_existing_names_accept_any_iterable_and_any_order`: `AssertionError: 1 != 3`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameRulesTests::test_hash_is_kept_when_supported`: `AssertionError: '#' not found in 'Hello.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameRulesTests::test_hash_is_replaced_and_mapped_when_unsupported`: `AssertionError: 'Hello.mp4' != 'Hello _hash_one _hash_two _hash_three.mp4'`
  - `SUBFAILED(count=0..6) tests/unit/storage/test_storage_output_naming.py::OutputFilenameRulesTests::test_hashtag_count_must_be_three_or_four`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameLimitTests::test_collision_suffix_fits_inside_limit`: `AssertionError: Tuples differ: ('abcdefghij.mp4', 1) != ('abcd (2).mp4', 2)`
  - `SUBFAILED(limit=5..22) tests/unit/storage/test_storage_output_naming.py::OutputFilenameLimitTests::test_filename_never_exceeds_limit_for_any_limit`: `AssertionError: 23 not less than or equal to <limit>`
  - `SUBFAILED(limit=0, 4) tests/unit/storage/test_storage_output_naming.py::OutputFilenameLimitTests::test_limit_too_small_is_rejected`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameLimitTests::test_truncation_cannot_recreate_reserved_name`: `AssertionError: 'CONSOLE.mp4' != 'CO.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameLimitTests::test_truncation_never_splits_a_character`: `AssertionError: '\U0001f3ac\U0001f3ac\U0001f3ac\U0001f3ac.mp4' != '\U0001f3ac\U0001f3ac.mp4'`
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameLimitTests::test_truncation_respects_limit_and_strips_trailing_dot_or_space`: `AssertionError: 'abcdefghij.mp4' != 'abcdefgh.mp4'`
- Xác nhận: output_naming.py ban đầu là stub nên mọi lỗi FAILED/SUBFAILED đều là AssertionError; không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` (chạy sau khi cài đặt đầy đủ)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `32 passed, 97 subtests passed in 0.07s`

## Thay đổi

- `src/controlplane/domain/storage_meta/output_naming.py`:
  - `OutputName`: frozen dataclass chứa 5 trường dữ liệu: `sanitized_filename`, `collision_sequence`, `display_title`, `display_hashtags`, `hash_mapping`.
  - Hằng số cấu hình: `HASH_REPLACEMENT = '_hash_'`, `MIN_HASHTAGS = 3`, `MAX_HASHTAGS = 4`, `_FORBIDDEN`, `_RESERVED` (CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9), `_ZWJ`, `_FALLBACK_STEM = '_'`.
  - Helper private:
    - `_width(text)`: tính độ dài theo đơn vị UTF-16, phù hợp giới hạn tên tệp NTFS.
    - `_is_joiner(char)`: kiểm tra ký tự nối (dấu tổ hợp Unicode category M, ZWJ, modifier màu da).
    - `_truncate(text, limit)`: cắt chuỗi theo giới hạn UTF-16 mà không chia cắt ký tự hoặc cụm ký tự nối.
    - `_strip_tail(text)`: loại bỏ dấu chấm và khoảng trắng ở cuối chuỗi.
    - `_clean(text, supports_hash)`: chuẩn hoá NFC, lọc ký tự điều khiển Cc, chuyển ký tự cấm thành `_`, và thay `#` nếu hệ thống không hỗ trợ hash.
    - `_guard_reserved(stem)`: thêm hậu tố `_` vào tên thiết bị reserved của Windows (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
    - `_fit_stem(stem, budget)`: tìm độ dài stem tối ưu trong budget cho phép, đảm bảo không vi phạm reserved sau khi cắt.
    - `_collision_key(name)`: chuẩn hoá NFC và casefold để so trùng tên tệp không phân biệt hoa thường.
  - `allocate_output_folder(session_date, completed_sessions_before_today, session_has_completed_video) -> str | None`:
    - Trả về `YY-MM-DD` cho phiên đầu có video hoàn thành (`completed_sessions_before_today == 0`).
    - Trả về `YY-MM-DD (n)` cho phiên thứ n+1 (`completed_sessions_before_today == n`).
    - Trả về `None` khi phiên không có video hoàn thành.
    - Ném `ValueError` khi `completed_sessions_before_today < 0`.
    - Không đọc đồng hồ hệ thống (`time`, `datetime.now()`, `date.today()`).
  - `allocate_output_filename(title, hashtags, extension, existing_names, supports_hash, max_filename_length) -> OutputName`:
    - Kiểm tra số lượng hashtag bắt buộc từ 3 đến 4 (khác thì ném `ValueError`).
    - Kiểm tra kiểu dữ liệu: `hashtags` không phải chuỗi đơn lẻ (`isinstance(hashtags, str)` thì ném `ValueError`).
    - Kiểm tra `max_filename_length >= 1`.
    - Chuẩn hoá NFC, loại bỏ ký tự điều khiển, thay ký tự cấm bằng `_`, loại bỏ dấu chấm và khoảng trắng ở cuối.
    - Xử lý tên reserved bằng hậu tố `_`.
    - Thay `#` bằng `_hash_` và lập `hash_mapping` khi `supports_hash == False`.
    - Cắt theo ngân sách độ dài UTF-16 mà không cắt giữa ký tự.
    - Xử lý va chạm tên bằng hậu tố ` (2)`, ` (3)` đặt trước phần mở rộng.
    - Giữ nguyên `display_title` và `display_hashtags` theo bản gốc caller truyền vào.
    - Thuần tuý và deterministic: cùng input luôn cho cùng output.
- `tests/unit/storage/test_storage_output_naming.py`:
  - `OutputFolderTests` (6 tests):
    - `test_first_second_third_session`: kiểm tra folder của phiên 1, 2, 3.
    - `test_session_without_completed_video_has_no_folder`: kiểm tra session không có video trả về `None`.
    - `test_year_month_day_are_zero_padded`: kiểm tra padding số 0 cho năm, tháng, ngày.
    - `test_negative_count_is_rejected`: kiểm tra ném `ValueError` khi số phiên âm.
    - `test_same_input_same_output`: kiểm tra tính xác định của hàm folder.
    - `test_module_does_not_read_system_clock`: dùng AST kiểm tra module không import hoặc gọi đồng hồ hệ thống.
  - `OutputFilenameSanitizeTests` (11 tests):
    - `test_plain_title`: kiểm tra cấu trúc tên cơ bản với hashtag và extension.
    - `test_path_traversal_never_survives`: loại trừ hoàn toàn path traversal (dấu gạch chéo xuôi và ngược).
    - `test_forbidden_characters_become_underscore`: chuyển các ký tự cấm thành `_`.
    - `test_control_characters_are_removed`: loại bỏ hoàn toàn ký tự điều khiển.
    - `test_trailing_dots_and_spaces_are_stripped`: loại bỏ dấu chấm và khoảng trắng ở đuôi.
    - `test_reserved_names_get_underscore_suffix`: kiểm tra hậu tố `_` cho toàn bộ danh sách reserved (cả hoa lẫn thường).
    - `test_non_reserved_lookalikes_are_untouched`: tên gần giống reserved (COM0, COM10, CONSOLE...) không bị đổi.
    - `test_empty_stem_falls_back_to_underscore`: stem rỗng fallback thành `_`.
    - `test_emoji_is_kept`: bảo toàn ký tự emoji trong tên.
    - `test_vietnamese_is_nfc_but_display_keeps_original`: chuẩn hoá NFC cho tên tệp nhưng display title giữ nguyên dạng gốc (NFD).
    - `test_extension_is_sanitized`: phần mở rộng được sanitize đúng quy cách.
  - `OutputFilenameRulesTests` (7 tests):
    - `test_hashtag_count_must_be_three_or_four`: kiểm tra ràng buộc 3-4 hashtag và từ chối các số lượng khác.
    - `test_hash_is_kept_when_supported`: giữ nguyên `#` khi `supports_hash=True`.
    - `test_hash_is_replaced_and_mapped_when_unsupported`: thay thế `#` bằng `_hash_` và sinh mapping khi `supports_hash=False`.
    - `test_display_metadata_keeps_original`: display metadata giữ nguyên bản gốc và kiểu tuple.
    - `test_collision_appends_sequence_before_extension`: đánh số thứ tự va chạm ` (2)`, ` (3)` trước phần mở rộng.
    - `test_collision_ignores_case_and_normalization`: so trùng tên không phân biệt hoa thường và chuẩn hoá NFC.
    - `test_existing_names_accept_any_iterable_and_any_order`: chấp nhận mọi iterable cho `existing_names`.
  - `OutputFilenameLimitTests` (8 tests):
    - `test_truncation_respects_limit_and_strips_trailing_dot_or_space`: cắt chuỗi tuân thủ giới hạn và loại bỏ dấu chấm/khoảng trắng cuối sau khi cắt.
    - `test_truncation_never_splits_a_character`: không cắt đôi emoji hoặc ký tự có dấu tổ hợp.
    - `test_truncation_cannot_recreate_reserved_name`: cắt ngắn không tạo ra tên reserved.
    - `test_limit_too_small_is_rejected`: từ chối giới hạn độ dài không đủ chỗ cho tên.
    - `test_collision_suffix_fits_inside_limit`: hậu tố va chạm vừa vặn trong giới hạn cho phép.
    - `test_filename_never_exceeds_limit_for_any_limit`: kiểm tra vét cạn giới hạn độ dài từ 5 đến 40 đơn vị UTF-16.
    - `test_same_input_gives_same_output`: tính xác định của hàm đặt tên tệp.
    - `test_output_name_is_immutable`: tính bất biến của dataclass `OutputName`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` (RED) | 1 | 98 failed, 10 passed, 21 subtests passed in 0.49s |
| 2 | `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` (GREEN) | 0 | 32 passed, 97 subtests passed in 0.07s |
| 3 | `python -c "import pathlib; fs=['src/controlplane/domain/storage_meta/output_naming.py','tests/unit/storage/test_storage_output_naming.py']; bad=[(f,i) for f in fs for i,l in enumerate(pathlib.Path(f).read_text(encoding='utf-8').splitlines(),1) if l!=l.rstrip()]; assert not bad, bad; assert all(pathlib.Path(f).read_bytes()[:3]!=bytes([239,187,191]) for f in fs); print('OK')"` | 0 | OK (UTF-8 không BOM, LF, không trailing whitespace) |
| 4 | `git diff --check` | 0 | PASS (không output, không trailing whitespace) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: `collision_sequence=1` nghĩa là không trùng, n >= 2 thêm ` (n)` trước phần mở rộng;
2. GIẢ ĐỊNH: `HASH_REPLACEMENT` là `_hash_`, `hash_mapping` là tuple các cặp `(chuỗi thay thế, '#')` và là tuple rỗng nếu không có ký tự `#` nào bị thay thế;
3. GIẢ ĐỊNH: độ dài tính theo đơn vị UTF-16 theo giới hạn NTFS, không cắt giữa ký tự (không tách dấu kết hợp, ZWJ, bộ điều chỉnh tông da; chưa xử lý cờ regional indicator);
4. GIẢ ĐỊNH: tên reserved được kiểm tra theo đoạn trước dấu chấm đầu tiên, không phân biệt hoa thường, ở cả phần title ban đầu và tên cuối sau khi cắt ngắn;
5. GIẢ ĐỊNH: tên tệp đầy đủ = `title + ' ' + các hashtag cách nhau bằng khoảng trắng`, hashtag dạng nguyên vẹn;
6. GIẢ ĐỊNH: so trùng tên không phân biệt hoa thường (`casefold`) và theo chuẩn Unicode NFC;
7. GIẢ ĐỊNH: stem rỗng sau sanitize fallback thành `_`; `max_filename_length` quá nhỏ hoặc `completed_sessions_before_today` âm ném `ValueError`.

## Danh sách chờ user (pendingUserCheckpoint)

- Không phát sinh mục chờ user mới; không mục nào được coi là đã duyệt.

## Giới hạn

- Không chạy full suite; không chạy tests/m1, tests/m2.
- Không sửa `__init__.py`, migration, lockfile, pyproject.toml.
- Không thêm thư viện ngoài stdlib (chỉ dùng `unicodedata`, `dataclasses`, `datetime`, `collections.abc`).
- Không gọi dịch vụ thật và không đọc đồng hồ hệ thống (`time`, `random`, `os`, `uuid`, `datetime.now()`, `date.today()`).
- Không tạo `conftest.py` hay `__init__.py` trong `tests/`.
- Chỉ sửa đúng 3 owned paths được phân quyền:
  - `src/controlplane/domain/storage_meta/output_naming.py`
  - `tests/unit/storage/test_storage_output_naming.py`
  - `docs/delivery-evidence/i-11/report.md`
