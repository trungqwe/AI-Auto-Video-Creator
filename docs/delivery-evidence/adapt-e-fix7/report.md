# Báo cáo ADAPT-E-FIX7

Nhóm lỗi: `OI-CP7-10-F16` (lô 30292531-3092-44d3-8d37-71ec28831749, lượt RG-09 của CP7-10 ngày 01/11/2026: align FAILED_FINAL `word_coverage_incomplete` vì từ kịch bản Vice-Chair, CARICOM, MP không có từ nghe khớp một-một; `_match_script` bỏ dãy còn lại không có mốc).

## Tệp đã sửa

- `src/voice/adapters/real_whisper_aligner.py`: thêm `FALLBACK_MAX_SCRIPT = 4`, `FALLBACK_MAX_HEARD = 6`, hàm `_cover_gaps`, đổi dòng return cuối của `_match_script` thành `_cover_gaps(sorted(matches), expected, heard)`, thêm câu ADAPT-E-FIX7 vào docstring module. Không đổi ngưỡng, profile, `align()`, nhánh rescued, khối ADAPT-E-FIX6.
- `tests/integration/adapt/e/test_adapt_e_aligner_gaps.py` (mới): 9 mục test, không DB, không dùng patch hay giả lập hàm.
- `docs/delivery-evidence/adapt-e-fix7/report.md` (mới): báo cáo này.

## Lệnh đã chạy

| Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- |
| `python -m pytest tests/integration/adapt/e/test_adapt_e_aligner_gaps.py -q -p no:cacheprovider` | 0 | `9 passed in 0.16s` |
| `python -m pytest tests/integration/adapt/e -q -p no:cacheprovider` | 0 | `121 passed in 2.79s` |
| `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_e2_voice_ports.py -q -p no:cacheprovider` | 0 | `149 passed in 12.53s` |
| `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7638 passed, 1 warning, 2561 subtests passed in 24.27s` |
| Probe dấu vết FIX7 trong aligner (bước 11) | 0 | không áp dụng |
| Probe dấu vết test mới (bước 12) | 0 | không áp dụng |
| Probe VAD và tham số Silero (bước 13) | 0 | không áp dụng |
| Probe hash rescued và dấu vết FIX3 (bước 14) | 0 | không áp dụng |
| Probe hash rescued và dấu vết FIX4 (bước 15) | 0 | không áp dụng |
| Probe compose và khoá nạp (bước 16) | 0 | không áp dụng |
| Probe dấu vết FIX5 (bước 17) | 0 | không áp dụng |
| Probe dấu vết FIX6 (bước 18) | 0 | không áp dụng |
| Probe cấu trúc package và cấm tiền tố `src.` (bước 19) | 0 | không áp dụng |
| `git diff --check` | 0 | không có output |

## Trước và sau bản sửa

- Trước (HEAD 4943c61, mã aligner chưa sửa): `7 failed, 2 passed in 0.36s`. Ca hỏng do assert về spans, missing hoặc split_group_count: `test_cp7_10_acronym_and_hyphen_take_model_times`, `test_hyphen_word_heard_as_two_words`, `test_script_word_without_heard_word_shares_the_next_word_span`, `test_name_heard_as_three_pieces`, `test_trailing_acronym_joins_the_word_before`, `test_gap_groups_count_under_the_cap[0.05-False]`, `test_gap_groups_count_under_the_cap[0.2-True]`. Hai ca đạt vì ghim hành vi cũ: `test_number_run_keeps_the_fix3_rule`, `test_run_longer_than_four_words_stays_missing`.
- Sau bản sửa: `9 passed in 0.16s`.

## Ca CP7-10

Kết quả do `test_cp7_10_acronym_and_hyphen_take_model_times` xác nhận (đạt, 11 từ đều có mốc):

- caricom: (25120, 25594)
- reparations: (25594, 26340)
- vice-chair: (26760, 27497)
- verene: (27497, 27940)
- `split_group_count` = 2, `split_word_count` = 4, không từ nào missing.

## Kết luận

Mọi lệnh kiểm ở trên đã đạt (mã thoát 0). `OI-CP7-10-F16` đã đóng.
