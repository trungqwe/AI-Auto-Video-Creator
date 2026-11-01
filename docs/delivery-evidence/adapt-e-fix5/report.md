# Báo cáo ADAPT-E-FIX5

- Gói: ADAPT-E-FIX5 (milestone CP7), phụ thuộc ADAPT-E-FIX4 đã tích hợp.
- Nhóm lỗi: OI-CP7-10-F13 (`alignment_split_ratio_exceeded` ở stage align, activity CreateWordTiming; lô 1d6d3c1f-94d7-477a-af7f-94a78fe8906a, HEAD 9eaedbf).

## Nguyên nhân và cách sửa

Kịch bản 148 từ có ba số đọc bằng chữ; Whisper nghe `100 ,000` / `300 ,000` / `100`. Mỗi cụm dùng chung một khoảng nghe được, nhưng trần `max_unmatched_word_ratio = 0,05` áp lên số TỪ bị chia: 8/148 = 0,054 > 0,05. Hai đầu mỗi cụm vẫn là mốc của mô hình; chỉ mép bên trong cụm được chia, nên trần được áp lên số cụm bị chia.

Sửa một chỗ ở aligner, không đổi ngưỡng, không đổi `tools/launcher/prod/profile.json`:

- `AlignmentReport.split_group_count: int = 0` (ngay sau `split_word_count`); `split_word_count` giữ nghĩa cũ (bằng chứng).
- `align()` thêm `split_groups`, tăng 1 cho mỗi khoảng nghe được bị chia; trần `split_groups / len(expected) > config.max_unmatched_word_ratio`, mã `alignment_split_ratio_exceeded`, `retryable=False`.
- Docstring module và `AlignmentReport` cập nhật. Không đổi `_match_script`, cách chia theo số ký tự, kiểm unmatched ratio, nhánh rescued (băm 23 dòng giữ nguyên).

## Tệp đã sửa

- `src/voice/adapters/real_whisper_aligner.py`
- `tests/integration/adapt/e/test_adapt_e_aligner_numbers.py` (`test_split_counts_groups_not_words`, `test_split_groups_capped`, `test_cp7_10_three_number_groups_pass`)
- `tests/integration/adapt/e/test_adapt_e_aligner_forms.py` (`test_forms_split_counts_one_group`, `test_forms_split_groups_capped`)
- `docs/delivery-evidence/adapt-e-fix5/report.md`

## Ca CP7-10 (sau sửa)

`script_token_count` = 148, `split_word_count` = 8, `split_group_count` = 3; không missing, không extra; qua `assert_contract`.

## Số ca hỏng trước và đạt sau

Trên HEAD 9eaedbf (aligner cũ, test mới): 8 ca hỏng / 33 đạt trong hai tệp aligner (`numbers`: 3 ca `test_split_counts_groups_not_words`, `test_split_groups_capped`, `test_cp7_10_three_number_groups_pass`; `forms`: `test_forms_split_counts_one_group[38]`, `[37]`, `test_forms_split_groups_capped[34]`). Ca CP7-10 hỏng ở `real_whisper_aligner.py:601`. Sau sửa: 41 đạt, 0 hỏng.

## Lệnh kiểm đã chạy (thật)

| # | Lệnh | Mã thoát | Dòng tổng kết pytest nguyên văn |
| --- | --- | --- | --- |
| 1 | `git diff --check` | 0 | (không có đầu ra) |
| 2 | `python -m pytest tests/integration/adapt/e -q -p no:cacheprovider` | 0 | `107 passed in 5.69s` |
| 3 | `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_e2_voice_ports.py -q -p no:cacheprovider` | 0 | `149 passed in 10.99s` |
| 4 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7638 passed, 2561 subtests passed in 22.80s` |
| 5-11 | Các probe `python -c` (nhóm, test, VAD, băm nhánh rescued FIX3/FIX4, compose/load lock, bố cục CP2A) | 0 | không áp dụng |
| 12 | Probe báo cáo | xem lệnh cuối | không áp dụng |

## Kết luận

OI-CP7-10-F13 đã đóng. Backlog B24 N4 (đếm theo cụm) đã làm. Ngưỡng 0,05 và `profile.json` không đổi (CONSERVATIVE_DEFAULT của Control); job đã hỏng trước bản sửa không chạy lại.
