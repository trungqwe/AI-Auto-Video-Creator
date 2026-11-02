# Báo cáo ADAPT-E-FIX8

## Nhóm lỗi

`OI-CP7-10-F17`: lô `bc5a2847-f28b-4cf4-82c0-9c73b5a6aac2`, lượt RG-09 thật của Reviewer CP7-10 ngày 01/11/2026: align FAILED_FINAL `word_coverage_incomplete`, kịch bản 157 từ, ba lượt liền nhau hỏng cùng mã. Gốc chung: aligner chấp nhận tới 5% từ không khớp nhưng pipeline đòi `check_coverage` trùng khít. Cụm 6 từ viết khác (tên tiếng Tây Ban Nha) vẫn thiếu cả 6 từ với FIX7 vì dãy dài hơn 4.

## Tệp đã sửa

- `src/voice/adapters/real_whisper_aligner.py`: thêm `FILL_MIN_MS`, `FILL_MAX_RATIO`, `_fill_stragglers`, lời gọi trong `align()`, `ratio` cộng `filled`, câu ADAPT-E-FIX8 trong docstring module. Không đổi ngưỡng, profile, `_match_script`, nhánh rescued, khối FIX6, `_cover_gaps`.
- `tests/integration/adapt/e/test_adapt_e_aligner_fill.py` (mới, 4 ca, không DB).
- `docs/delivery-evidence/adapt-e-fix8/report.md` (báo cáo này).

## Lệnh đã chạy

| Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- |
| `python -m pytest tests/integration/adapt/e/test_adapt_e_aligner_fill.py -q -p no:cacheprovider` (trước bản sửa, bước 2) | 1 | `2 failed, 2 passed in 0.24s` |
| cùng lệnh (sau bản sửa, bước 6) | 0 | `4 passed in 0.23s` |
| `python -m pytest tests/integration/adapt/e -q -p no:cacheprovider` | 0 | `125 passed in 2.54s` |
| `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_e2_voice_ports.py -q -p no:cacheprovider` | 0 | `149 passed in 10.82s` |
| `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7638 passed, 1 warning, 2561 subtests passed in 19.23s` |
| Probe bước 10 (dấu vết FIX8, ngưỡng profile 0,05) | 0 | không áp dụng |
| Probe bước 11 (dấu vết test mới) | 0 | không áp dụng |
| Probe bước 12 (VAD và tham số Silero) | 0 | không áp dụng |
| Probe bước 13 (hash 23 dòng rescued, FIX3) | 0 | không áp dụng |
| Probe bước 14 (hash rescued, FIX4) | 0 | không áp dụng |
| Probe bước 15 (compose, khoá nạp) | 0 | không áp dụng |
| Probe bước 16 (FIX5) | 0 | không áp dụng |
| Probe bước 17 (FIX6) | 0 | không áp dụng |
| Probe bước 18 (FIX7) | 0 | không áp dụng |
| Probe bước 19 (package, cấm tiền tố `src.`) | 0 | không áp dụng |
| `git diff --check` | 0 | không áp dụng |
| Probe bước 22 (báo cáo nêu mã gói và mã nhóm lỗi) | 0 | không áp dụng |

Mọi lệnh pytest chạy với `PYTEST_DEBUG_TEMPROOT` riêng của lượt và interpreter khoá của lane.

## Trước và sau bản sửa

- Trước bản sửa (HEAD 0e974e5, aligner chưa sửa): `2 failed, 2 passed in 0.24s`. Hai ca hỏng vì assert: `test_six_word_run_takes_the_time_between_its_neighbours` (không có từ nào confidence 0.0) và `test_number_run_without_room_shares_the_word_before` (thiếu `eighty-four`). Hai ca đạt vì ghim hành vi giữ nguyên: `test_filled_words_still_count_as_unmatched` và `test_more_missing_words_than_the_cap_stay_missing`.
- Sau bản sửa: `4 passed in 0.23s`.

## Ca cụm 6 từ

Cụm `sociedad espanola de biologia del desarrollo` (max_ratio 0.05): mốc đầu `sociedad` = 6000 ms, mốc cuối `desarrollo` = 6900 ms, sáu từ confidence 0.0, `unmatched_ratio` = 9/237, `split_group_count` = 1, `split_word_count` = 6, không từ nào missing, `assert_contract` đạt. Cụm 7 từ (thêm `sevilla`) vượt trần 5% nên vẫn missing 60..66 và `split_group_count` = 0.

## Kết luận

Mọi lệnh kiểm đạt (mã thoát 0).

OI-CP7-10-F17 đã đóng.
