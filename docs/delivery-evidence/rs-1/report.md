# RS-1: Khung gói read_screens, hàm dùng chung và hỗ trợ test PostgreSQL

## Phạm vi
Triển khai đúng 5 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/__init__.py`
- `src/controlplane/infrastructure/read_screens/common.py`
- `tests/integration/read_screens/rs_support.py`
- `tests/integration/read_screens/test_rs_1_common.py`
- `docs/delivery-evidence/rs-1/report.md`

## RED (bước 8)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_1_common.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `28 failed, 13 passed in 1.77s`
- Không có lỗi ImportError, ModuleNotFoundError hoặc lỗi thu thập (collection error). 13 test pass tại thời điểm RED gồm toàn bộ 4 test PostgreSQL và 4 test cấu trúc.
- Danh sách 28 test FAILED:
  - `test_utc_text_converts_offset_to_utc_with_microseconds`
  - `test_utc_text_pads_zero_microseconds`
  - `test_parse_cursor_time_accepts_rfc3339[2026-10-25T01:02:03.000004Z-expected0]`
  - `test_parse_cursor_time_accepts_rfc3339[2026-10-25T08:02:03.000004+07:00-expected1]`
  - `test_parse_cursor_time_accepts_rfc3339[2026-10-25T01:02:03Z-expected2]`
  - `test_parse_cursor_time_accepts_rfc3339[2026-10-25T01:02:03.5Z-expected3]`
  - `test_parse_cursor_time_accepts_rfc3339[2026-10-25t01:02:03z-expected4]`
  - `test_parse_cursor_time_rejects_non_timestamps[]`
  - `test_parse_cursor_time_rejects_non_timestamps[garbage]`
  - `test_parse_cursor_time_rejects_non_timestamps[2026-10-25]`
  - `test_parse_cursor_time_rejects_non_timestamps[2026-10-25T01:02:03]`
  - `test_parse_cursor_time_rejects_non_timestamps[2026-13-45T01:02:03Z]`
  - `test_parse_cursor_time_rejects_non_timestamps[ 2026-10-25T01:02:03Z]`
  - `test_parse_cursor_time_rejects_non_timestamps[2026-10-25T01:02:03Z\n]`
  - `test_parse_cursor_time_rejects_non_timestamps[0001-01-01T00:00:00+07:00]`
  - `test_parse_cursor_time_rejects_non_timestamps[None]`
  - `test_effective_direction_defaults_to_desc_without_direction_param`
  - `test_keyset_asc_without_cursor`
  - `test_keyset_desc_without_cursor`
  - `test_keyset_asc_with_cursor_compares_greater`
  - `test_keyset_desc_with_cursor_compares_less`
  - `test_keyset_rejects_cursor_that_is_not_a_timestamp[cursor0]`
  - `test_keyset_rejects_cursor_that_is_not_a_timestamp[cursor1]`
  - `test_keyset_rejects_cursor_that_is_not_a_timestamp[cursor2]`
  - `test_keyset_rejects_unknown_direction`
  - `test_page_of_returns_next_cursor_when_more_rows`
  - `test_page_of_has_no_cursor_on_last_page`
  - `test_pick_reads_nested_keys`
- Dòng trích assertion hoặc DID NOT RAISE đại diện cho từng nhóm:
  - `utc_text`: `AssertionError: assert '' == '2026-10-25T01:30:15.123456Z'`
  - `parse_cursor_time`: `AssertionError: assert None == datetime.datetime(2026, 10, 25, 1, 2, 3, 4, tzinfo=datetime.timezone.utc)` và `Failed: DID NOT RAISE ValueError`
  - `effective_direction`: `AssertionError: assert 'asc' == 'desc'`
  - `keyset`: `AssertionError: assert ('', []) == ('TRUE', [])` và `Failed: DID NOT RAISE ValueError`
  - `page_of`: `assert False where False = isinstance(None, Page)`
  - `pick`: `AssertionError: assert None == 'm1'`

## GREEN (bước 10)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_1_common.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `41 passed in 1.77s`
- Toàn bộ 41 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/common.py').read_text(encoding='utf-8').lower(); assert 'os.environ' not in t and 'from src.' not in t and 'production' not in t and 'insert into' not in t, 'RS-1'"` | Quét văn bản common.py cấm chuỗi cấm (bước 11) | 0 |
| `git diff --check` | Kiểm tra diff/khoảng trắng cuối dòng trước khi stage (bước 12) | 0 |
| `git diff --check --cached` | Kiểm tra staging của 5 owned paths (bước 14) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `__init__.py` chỉ chứa docstring; `common.py` triển khai đầy đủ `ConnectionScope`, `utc_text`, `parse_cursor_time`, `effective_direction`, `keyset`, `page_of`, `pick` và toàn bộ test thuần đạt.
2. `rs_support.py` cung cấp context manager `temp_database()` tạo CSDL tạm qua `M2_TEST_PG_DSN`, migrate schema, seed 2 workspace, tự động dọn sạch database khi hoàn tất kể cả khi thân with raise lỗi; `FakeRequest` mô phỏng đủ `state.identity` và `query_params`; thiếu DSN thì fail rõ ràng với `BLOCKED_EXTERNAL: thiếu M2_TEST_PG_DSN` mà không skip.
3. Ranh giới kiến trúc: `common.py` là pure module không truy cập database hay biến môi trường, không import `production`, không `from src.`, không `insert into`; `os.environ` chỉ xuất hiện tại `rs_support.py`; `tests/integration/read_screens/` không có `__init__.py` và `conftest.py`.

## Ghi chú
Hàm keyset trả `where_sql` là 'TRUE' khi không có cursor, `params` là list, `order_sql` gồm cả 'ORDER BY'. Không ghi DSN, mật khẩu hay bất kỳ bí mật nào trong báo cáo, test hoặc mã nguồn.
