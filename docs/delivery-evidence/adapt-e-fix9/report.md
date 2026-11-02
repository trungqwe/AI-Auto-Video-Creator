# Báo cáo ADAPT-E-FIX9

## Nhóm lỗi

`OI-CP7-11-Q3`, lô `71973394`, đêm CP7-11 lượt 3, mã `7fa09bf` (có FIX5 tới FIX8): video 94, 96, 107 hỏng align `word_coverage_incomplete` vì Whisper bỏ sót cả một mệnh đề (11, 11, 10 từ). Dãy thiếu vượt trần FIX7 (4 từ) và trần FIX8 (5% số từ), nên các quy tắc cũ không cứu được.

## Tệp đã sửa

- `src/voice/adapters/real_whisper_aligner.py`: thêm `RELISTEN_CONTEXT`, `RELISTEN_MAX_WINDOWS`, `RELISTEN_MAX_MS`, `_covered_count`, `_uncovered_runs`, `_relisten_window`, `_short_of_gates`, `RealWhisperAligner._relisten`, trường `relisten_count`, lời gọi trong `align()` và câu `ADAPT-E-FIX9` trong docstring module. Không đổi ngưỡng, `profile.json`, nhánh `rescued`, `_match_script`, `_cover_gaps`, `_fill_stragglers`.
- `tests/integration/adapt/e/test_adapt_e_aligner_relisten.py`: tệp mới, 4 ca test.
- `docs/delivery-evidence/adapt-e-fix9/report.md`: báo cáo này.

## Lệnh đã chạy

Mọi lệnh pytest chạy bằng interpreter khoá của lane và `PYTEST_DEBUG_TEMPROOT` riêng của lượt.

| Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- |
| Bước 3, trước bản sửa: `python -m pytest tests/integration/adapt/e/test_adapt_e_aligner_relisten.py -q -p no:cacheprovider` | 1 | `4 failed in 0.31s` |
| Bước 10, sau bản sửa: cùng lệnh | 0 | `4 passed in 0.11s` |
| `python -m pytest tests/integration/adapt/e -q -p no:cacheprovider` | 0 | `129 passed in 2.99s` |
| `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_e2_voice_ports.py -q -p no:cacheprovider` | 0 | `149 passed in 16.00s` |
| `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7784 passed, 1 warning, 2561 subtests passed in 30.62s` |
| Probe dấu vết FIX9 và ngưỡng 0,05 (bước 14) | 0 | không áp dụng |
| Probe dấu vết test mới (bước 15) | 0 | không áp dụng |
| Probe VAD và tham số Silero (bước 16) | 0 | không áp dụng |
| Probe hash 23 dòng `rescued` và dấu vết FIX3 (bước 17) | 0 | không áp dụng |
| Probe hash `rescued` và dấu vết FIX4 (bước 18) | 0 | không áp dụng |
| Probe compose và khoá nạp (bước 19) | 0 | không áp dụng |
| Probe dấu vết FIX5 (bước 20) | 0 | không áp dụng |
| Probe dấu vết FIX6 (bước 21) | 0 | không áp dụng |
| Probe dấu vết FIX7 (bước 22) | 0 | không áp dụng |
| Probe dấu vết FIX8 (bước 23) | 0 | không áp dụng |
| Probe package controlplane, pythonpath, cấm tiền tố `src.` (bước 24) | 0 | không áp dụng |
| Probe bước 26 (báo cáo nêu mã gói và mã nhóm lỗi) | 0 | không áp dụng |
| `git diff --check` | 0 | không áp dụng |

## Trước và sau bản sửa

Trước bản sửa (HEAD aa3f735, bước 3): `4 failed in 0.31s`. Lý do hỏng: ca `test_skipped_clause_is_heard_again_in_its_window`, `test_second_pass_that_hears_nothing_new_keeps_the_first_pass` và `test_failed_second_pass_keeps_the_first_pass` hỏng ở assert `model.clips == CLIP` (mã cũ không gọi mô hình lần hai, clips rỗng); ca `test_runs_of_four_words_or_less_are_not_heard_again` hỏng vì `AttributeError: 'AlignmentReport' object has no attribute 'relisten_count'`. Không có lỗi import hay collection.

Sau bản sửa (bước 10): `4 passed in 0.11s`.

## Ba job bỏ sót mệnh đề (94, 96, 107)

Đây là số đo của Control trên nguyên mẫu (bản sao HEAD 3705465, Whisper thật, kịch bản = lời chép theo khúc); lane này không có Whisper thật nên không chạy lại. Mã cũ thiếu đúng mệnh đề 11, 11, 10 từ; mã mới phủ đủ các từ đó, `unmatched_ratio` 0,0 / 0,0035 / 0,0033, mốc từ lệch trung vị 10 ms so với một lượt chép theo khúc độc lập.

Phần chạy trong lane: ca `test_skipped_clause_is_heard_again_in_its_window` cho thấy mệnh đề 10 từ được phủ thêm, clips `[[5.8, 9.8]]`, `relisten_count` 1, không còn từ thiếu, `unmatched_ratio` 0.0.

## Job đạt ở lượt đầu đi đúng đường cũ

Control đo 92 job đạt của cùng lô: cổng nghe lại kích hoạt 0/92; từ, mốc, mã và tỷ lệ trùng 92/92 với mã cũ. Trong lane, các ca aligner cũ của `tests/integration/adapt/e` đạt (`129 passed in 2.99s`) và ca `test_runs_of_four_words_or_less_are_not_heard_again` có `clips == []`.

## Giới hạn

- Chỉ chữa lớp lỗi Whisper bỏ sót mệnh đề (3/6 job align hỏng của lô 71973394).
- Video 30, 31, 35 không bỏ sót; nghi do số viết bằng chữ trong kịch bản (như sixty-six to forty-five) khác chữ số của Whisper, cần gói riêng.
- Lượt hai tốn thêm tối đa 3 lần giải mã đoạn tối đa 28 s, chỉ trên job đã trượt cổng ở lượt đầu.
- RG-05 và cổng tỷ lệ giữ nguyên.

## Kết luận

Các lệnh trong bảng đều có mã thoát 0 (trừ dòng trước bản sửa ở bước 3, dự kiến hỏng). `OI-CP7-11-Q3` được xử lý cho lớp bỏ sót mệnh đề; phần số viết bằng chữ còn mở.
