# B?o c?o b?ng ch?ng I-11

## M?i tr??ng

- Interpreter kho?: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d3b0cff0a6c39bb4cce7451ff61435358b50a768`
- Ngu?n quy?n: IMPL-PLAN-I Auditor PASS, slice I-11 trong `docs/implementation/i/slices.md`, CT-STO-011, D8-I-07, D8-I-08, binding `g-c-i-completion`.

## RED

- L?nh th?c thi: `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` (ch?y v?i stub ? b??c 1)
- Exit code th?c t?: 1
- D?ng t?m t?t nguy?n v?n: `98 failed, 10 passed, 21 subtests passed in 0.49s`
- Chi ti?t c?c test FAILED/SUBFAILED k?m th?ng ?i?p AssertionError nguy?n v?n r?t t? output b??c 6:
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
  - `FAILED tests/unit/storage/test_storage_output_naming.py::OutputFilenameSanitizeTests::test_vietnamese_is_nfc_but_display_keeps_original`: `AssertionError: 'Vi?t Nam.mp4' != 'Vi?t Nam #one #two #three.mp4'`
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
- X?c nh?n: output_naming.py ban ??u l? stub n?n m?i l?i FAILED/SUBFAILED ??u l? AssertionError; kh?ng c? ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay l?i collection.

## GREEN

- L?nh th?c thi: `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` (ch?y sau khi c?i ??t ??y ??)
- Exit code th?c t?: 0
- D?ng t?m t?t nguy?n v?n: `32 passed, 97 subtests passed in 0.07s`

## Thay ??i

- `src/controlplane/domain/storage_meta/output_naming.py`:
  - `OutputName`: frozen dataclass ch?a 5 tr??ng d? li?u: `sanitized_filename`, `collision_sequence`, `display_title`, `display_hashtags`, `hash_mapping`.
  - H?ng s? c?u h?nh: `HASH_REPLACEMENT = '_hash_'`, `MIN_HASHTAGS = 3`, `MAX_HASHTAGS = 4`, `_FORBIDDEN`, `_RESERVED` (CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9), `_ZWJ`, `_FALLBACK_STEM = '_'`.
  - Helper private:
    - `_width(text)`: t?nh ?? d?i theo ??n v? UTF-16, ph? h?p gi?i h?n t?n t?p NTFS.
    - `_is_joiner(char)`: ki?m tra k? t? n?i (d?u t? h?p Unicode category M, ZWJ, modifier m?u da).
    - `_truncate(text, limit)`: c?t chu?i theo gi?i h?n UTF-16 m? kh?ng chia c?t k? t? ho?c c?m k? t? n?i.
    - `_strip_tail(text)`: lo?i b? d?u ch?m v? kho?ng tr?ng ? cu?i chu?i.
    - `_clean(text, supports_hash)`: chu?n ho? NFC, l?c k? t? ?i?u khi?n Cc, chuy?n k? t? c?m th?nh `_`, v? thay th? `#` n?u h? th?ng kh?ng h? tr? hash.
    - `_guard_reserved(stem)`: th?m h?u t? `_` v?o t?n thi?t b? reserved c?a Windows (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
    - `_fit_stem(stem, budget)`: t?m ?? d?i stem t?i ?u trong budget cho ph?p, ??m b?o kh?ng vi ph?m reserved sau khi c?t.
    - `_collision_key(name)`: chu?n ho? NFC v? casefold ?? so s?nh tr?ng t?n t?p kh?ng ph?n bi?t hoa th??ng.
  - `allocate_output_folder(session_date, completed_sessions_before_today, session_has_completed_video) -> str | None`:
    - Tr? v? `YY-MM-DD` cho phi?n ??u c? video ho?n th?nh (`completed_sessions_before_today == 0`).
    - Tr? v? `YY-MM-DD (n)` cho phi?n th? n+1 (`completed_sessions_before_today == n`).
    - Tr? v? `None` khi phi?n kh?ng c? video ho?n th?nh (`session_has_completed_video == False`).
    - N?m `ValueError` khi `completed_sessions_before_today < 0`.
    - Kh?ng ??c ??ng h? h? th?ng (`time`, `datetime.now()`, `date.today()`).
  - `allocate_output_filename(title, hashtags, extension, existing_names, supports_hash, max_filename_length) -> OutputName`:
    - Ki?m tra s? l??ng hashtag b?t bu?c t? 3 ??n 4 (kh?c ? n?m `ValueError`).
    - Ki?m tra ki?u d? li?u `hashtags` kh?ng ph?i chu?i ??n l? (`isinstance(hashtags, str) ? ValueError`).
    - Ki?m tra `max_filename_length >= 1`.
    - Chu?n ho? NFC, lo?i b? k? t? ?i?u khi?n, thay k? t? c?m b?ng `_`, lo?i b? d?u ch?m/kho?ng tr?ng cu?i.
    - X? l? t?n reserved b?ng h?u t? `_`.
    - Thay `#` b?ng `_hash_` v? l?p `hash_mapping` khi `supports_hash == False`.
    - C?t theo ng?n s?ch ?? d?i UTF-16 m? kh?ng c?t gi?a k? t?.
    - X? l? va ch?m t?n b?ng h?u t? ` (2)`, ` (3)` ??t tr??c ph?n m? r?ng.
    - Gi? nguy?n `display_title` v? `display_hashtags` theo b?n g?c caller truy?n v?o.
    - Thu?n t?y v? deterministic: c?ng input lu?n cho c?ng output.
- `tests/unit/storage/test_storage_output_naming.py`:
  - `OutputFolderTests` (6 tests):
    - `test_first_second_third_session`: ki?m tra folder c?a phi?n 1, 2, 3.
    - `test_session_without_completed_video_has_no_folder`: ki?m tra session kh?ng c? video tr? v? `None`.
    - `test_year_month_day_are_zero_padded`: ki?m tra padding s? 0 cho n?m, th?ng, ng?y.
    - `test_negative_count_is_rejected`: ki?m tra n?m `ValueError` khi s? phi?n ?m.
    - `test_same_input_same_output`: ki?m tra t?nh ??n ??nh c?a h?m folder.
    - `test_module_does_not_read_system_clock`: d?ng AST ki?m tra module kh?ng import ho?c g?i ??ng h? h? th?ng.
  - `OutputFilenameSanitizeTests` (11 tests):
    - `test_plain_title`: ki?m tra c?u tr?c t?n c? b?n v?i hashtag v? extension.
    - `test_path_traversal_never_survives`: lo?i tr? ho?n to?n path traversal (`/` v? `\`).
    - `test_forbidden_characters_become_underscore`: chuy?n c?c k? t? c?m th?nh `_`.
    - `test_control_characters_are_removed`: lo?i b? ho?n to?n k? t? ?i?u khi?n.
    - `test_trailing_dots_and_spaces_are_stripped`: lo?i b? d?u ch?m v? kho?ng tr?ng ? ?u?i.
    - `test_reserved_names_get_underscore_suffix`: ki?m tra h?u t? `_` cho to?n b? danh s?ch reserved (c? hoa l?n th??ng).
    - `test_non_reserved_lookalikes_are_untouched`: t?n g?n gi?ng reserved (COM0, COM10, CONSOLE...) kh?ng b? ??i.
    - `test_empty_stem_falls_back_to_underscore`: stem r?ng fallback th?nh `_`.
    - `test_emoji_is_kept`: b?o t?n k? t? emoji trong t?n.
    - `test_vietnamese_is_nfc_but_display_keeps_original`: chu?n ho? NFC cho t?n t?p nh?ng display title gi? nguy?n d?ng g?c (NFD).
    - `test_extension_is_sanitized`: ph?n m? r?ng ???c sanitize ??ng quy c?ch.
  - `OutputFilenameRulesTests` (7 tests):
    - `test_hashtag_count_must_be_three_or_four`: ki?m tra r?ng bu?c 3-4 hashtag v? t? ch?i c?c s? l??ng kh?c.
    - `test_hash_is_kept_when_supported`: gi? nguy?n `#` khi `supports_hash=True`.
    - `test_hash_is_replaced_and_mapped_when_unsupported`: thay th? `#` b?ng `_hash_` v? sinh mapping khi `supports_hash=False`.
    - `test_display_metadata_keeps_original`: display metadata gi? nguy?n b?n g?c v? ki?u tuple.
    - `test_collision_appends_sequence_before_extension`: ??nh s? th? t? va ch?m ` (2)`, ` (3)` tr??c ph?n m? r?ng.
    - `test_collision_ignores_case_and_normalization`: so tr?ng t?n kh?ng ph?n bi?t hoa th??ng v? chu?n ho? NFC.
    - `test_existing_names_accept_any_iterable_and_any_order`: ch?p nh?n m?i iterable cho `existing_names`.
  - `OutputFilenameLimitTests` (8 tests):
    - `test_truncation_respects_limit_and_strips_trailing_dot_or_space`: c?t chu?i tu?n th? gi?i h?n v? lo?i b? d?u ch?m/kho?ng tr?ng cu?i sau khi c?t.
    - `test_truncation_never_splits_a_character`: kh?ng c?t ??i emoji ho?c k? t? c? d?u t? h?p.
    - `test_truncation_cannot_recreate_reserved_name`: c?t ng?n kh?ng t?o ra t?n reserved.
    - `test_limit_too_small_is_rejected`: t? ch?i gi?i h?n ?? d?i kh?ng ?? ch? cho t?n.
    - `test_collision_suffix_fits_inside_limit`: h?u t? va ch?m v?a v?n trong gi?i h?n cho ph?p.
    - `test_filename_never_exceeds_limit_for_any_limit`: ki?m tra v?t c?n gi?i h?n ?? d?i t? 5 ??n 40 ??n v? UTF-16.
    - `test_same_input_gives_same_output`: t?nh ??n ??nh c?a h?m ??t t?n t?p.
    - `test_output_name_is_immutable`: t?nh b?t bi?n c?a dataclass OutputName.

## L?nh ki?m

| # | L?nh | Exit code | K?t qu? |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` (RED) | 1 | 98 failed, 10 passed, 21 subtests passed in 0.49s |
| 2 | `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` (GREEN) | 0 | 32 passed, 97 subtests passed in 0.07s |
| 3 | `python -c "import pathlib; fs=['src/controlplane/domain/storage_meta/output_naming.py','tests/unit/storage/test_storage_output_naming.py']; bad=[(f,i) for f in fs for i,l in enumerate(pathlib.Path(f).read_text(encoding='utf-8').splitlines(),1) if l!=l.rstrip()]; assert not bad, bad; assert all(pathlib.Path(f).read_bytes()[:3]!=bytes([239,187,191]) for f in fs); print('OK')"` | 0 | OK (UTF-8 kh?ng BOM, LF, kh?ng trailing whitespace) |
| 4 | `git diff --check` | 0 | PASS (kh?ng output, kh?ng trailing whitespace) |

## Quy?t ??nh m?c ??nh (D8)

1. GI? ??NH: `collision_sequence=1` ngh?a l? kh?ng tr?ng, n >= 2 th?m ` (n)` tr??c ph?n m? r?ng;
2. GI? ??NH: `HASH_REPLACEMENT` l? `_hash_`, `hash_mapping` l? tuple c?c c?p `(chu?i thay th?, '#')` v? l? tuple r?ng n?u kh?ng c? k? t? `#` n?o b? thay th?;
3. GI? ??NH: ?? d?i t?nh theo ??n v? UTF-16 theo gi?i h?n NTFS, kh?ng c?t gi?a k? t? (kh?ng t?ch d?u k?t h?p, ZWJ, b? ?i?u ch?nh t?ng da; ch?a x? l? c? regional indicator);
4. GI? ??NH: t?n reserved ???c ki?m tra theo ?o?n tr??c d?u ch?m ??u ti?n, kh?ng ph?n bi?t hoa th??ng, ? c? ph?n title ban ??u v? t?n cu?i sau khi c?t ng?n;
5. GI? ??NH: t?n t?p ??y ?? = `title + ' ' + c?c hashtag c?ch nhau b?ng kho?ng tr?ng`, hashtag d?ng nguy?n v?n;
6. GI? ??NH: so tr?ng t?n kh?ng ph?n bi?t hoa th??ng (`casefold`) v? theo chu?n Unicode NFC;
7. GI? ??NH: stem r?ng sau sanitize fallback th?nh `_`; `max_filename_length` qu? nh? ho?c `completed_sessions_before_today` ?m n?m `ValueError`.

## Danh s?ch ch? user (pendingUserCheckpoint)

- Kh?ng ph?t sinh m?c ch? user m?i; kh?ng m?c n?o ???c coi l? ?? duy?t.

## Gi?i h?n

- Kh?ng ch?y full suite; kh?ng ch?y tests/m1, tests/m2.
- Kh?ng s?a `__init__.py`, migration, lockfile, pyproject.toml.
- Kh?ng th?m th? vi?n ngo?i stdlib (ch? d?ng `unicodedata`, `dataclasses`, `datetime`, `collections.abc`).
- Kh?ng g?i d?ch v? th?t v? kh?ng ??c ??ng h? h? th?ng (`time`, `random`, `os`, `uuid`, `datetime.now()`, `date.today()`).
- Kh?ng t?o `conftest.py` hay `__init__.py` trong `tests/`.
- Ch? s?a ??ng 3 owned paths ???c ph?n quy?n:
  - `src/controlplane/domain/storage_meta/output_naming.py`
  - `tests/unit/storage/test_storage_output_naming.py`
  - `docs/delivery-evidence/i-11/report.md`
