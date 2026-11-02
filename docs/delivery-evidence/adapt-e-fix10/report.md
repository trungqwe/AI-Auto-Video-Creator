# Báo cáo ADAPT-E-FIX10

## Nhóm lỗi

- Mã nhóm lỗi: `OI-CP7-11-Q3`, lô `71973394`, CP7-11 lượt 3.
- Video 30 hỏng `alignment_unmatched_ratio_exceeded`, video 31 hỏng `word_coverage_incomplete`.
- Whisper không bỏ sót từ nào. Kịch bản viết số bằng chữ (434/480 token số của 92 kịch bản đạt) còn Whisper viết chữ số cho tỉ số và giờ: "sixty-six to forty-five" / "66-45", "five and oh" / "5-0", "thirteen-to-nothing" / "13-0", "one hundred twenty-four to one hundred three" / "124-103".
- ADAPT-E-FIX3 và ADAPT-E-FIX4 chỉ ghép một số hay một số tiền, nên dãy từ hai số trở lên vẫn lọt ngưỡng.

## Tệp đã sửa

1. `src/voice/adapters/real_whisper_aligner.py`: thêm `SPOKEN_NUMBER_WORDS`, `SPOKEN_ZERO_WORDS`, `SPOKEN_LINK_WORDS`, `SPOKEN_UNITS`, `SPOKEN_MAX_READINGS`, `_words_value`, `_split_cardinals`, `_digit_readings`, `_spoken`, `_spoken_runs` (cùng các hàm phụ `_spoken_names`, `_link_only`, `_readable`, `_has_number`, `_count_numbers`), `_heard_slice`, `_spoken_groups`; tham số `groups` của `_match_script`; trường `spoken_group_count` của `AlignmentReport`; lời gọi `_spoken_groups` trong `align()` và câu ADAPT-E-FIX10 trong docstring module. Không đổi ngưỡng, `profile.json`, nhánh `rescued`, `_cover_gaps`, `_fill_stragglers`, `_relisten`.
2. `tests/integration/adapt/e/test_adapt_e_aligner_spoken.py`: test mới, 4 ca, không monkeypatch, không mock.
3. `docs/delivery-evidence/adapt-e-fix10/report.md`: báo cáo này.

Một điều chỉnh hành vi so với khối mã trong lệnh làm việc: `_readable` chấp nhận thêm token chỉ gồm từ số (`SPOKEN_NUMBER_WORDS`), vì token đơn `hundred` không đọc được riêng và làm đứt dãy "one hundred twenty-four to one hundred three" (ca 4 của `test_clock_times_in_words_match_whisper_digits` hỏng khi chưa sửa). Số đơn lẻ vẫn không bị ghép vì `_spoken_groups` chỉ nhận dãy có từ hai số trở lên.

## Lệnh đã chạy

| Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- |
| Bước 3: `python -m pytest tests/integration/adapt/e/test_adapt_e_aligner_spoken.py -q -p no:cacheprovider` (mã chưa sửa) | 1 | `4 failed in 0.26s` |
| Bước 12 lần đầu (sau sửa, trước chỉnh `_readable`) | 1 | `1 failed, 3 passed in 0.42s` |
| Bước 12: cùng lệnh sau chỉnh `_readable` | 0 | `4 passed in 0.21s` |
| Bước 13: `python -m pytest tests/integration/adapt/e -q -p no:cacheprovider` | 0 | `133 passed in 5.65s` |
| Bước 14: `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_e2_voice_ports.py -q -p no:cacheprovider` | 0 | `149 passed in 13.73s` |
| Bước 15: `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7784 passed, 1 warning, 2561 subtests passed in 26.77s` |
| Bước 16: probe FIX10 và ngưỡng 0,05 | 0 | không áp dụng |
| Bước 17: probe test mới | 0 | không áp dụng |
| Bước 18: probe VAD và Silero | 0 | không áp dụng |
| Bước 19: probe hash `rescued` và FIX3 | 0 | không áp dụng |
| Bước 20: probe hash `rescued` và FIX4 | 0 | không áp dụng |
| Bước 21: probe compose và khoá nạp | 0 | không áp dụng |
| Bước 22: probe FIX5 | 0 | không áp dụng |
| Bước 23: probe FIX6 | 0 | không áp dụng |
| Bước 24: probe FIX7 | 0 | không áp dụng |
| Bước 25: probe FIX8 | 0 | không áp dụng |
| Bước 26: probe FIX9 | 0 | không áp dụng |
| Bước 27: probe controlplane, pythonpath, tiền tố `src.` | 0 | không áp dụng |
| Bước 28: `git diff --check` | 0 | không áp dụng |

Bước 13 không có ca nào hỏng (kể cả hai ca kiểm cây git).

## Trước và sau bản sửa

- Bước 3 (mã chưa sửa): `4 failed`. Hai ca `test_other_values_are_not_grouped` và `test_first_pass_within_the_gates_is_not_regrouped` hỏng do `AttributeError: 'AlignmentReport' object has no attribute 'spoken_group_count'`. Hai ca còn lại (`test_score_words_share_the_span_of_the_heard_digits`, `test_clock_times_in_words_match_whisper_digits`) cũng hỏng; phần đuôi log đã thấy chỉ gồm hai ca đầu nên lý do chi tiết của hai ca này không được ghi lại ở đây.
- Bước 12 (sau sửa): `4 passed`.

## Kết quả từng tiêu chí

- Tiêu chí 1 (mã và test): đạt. Bốn ca mới hỏng trên mã cũ và đạt trên mã mới; pytest adapt/e, wire + PW-E2, tests/unit đều thoát 0; các probe FIX3 đến FIX10, VAD, compose, controlplane thoát 0 (bảng trên).
- Tiêu chí 2 (báo cáo): báo cáo này nêu mã gói `ADAPT-E-FIX10` và mã nhóm lỗi `OI-CP7-11-Q3`, kèm lệnh và mã thoát thật (probe báo cáo chạy sau khi ghi tệp).

## Số đo của Control (không chạy lại trong lane)

Lane không có Whisper thật nên các số sau là của Control, từ nguyên mẫu trên tệp giọng thật của lô 71973394, kịch bản S2: video 30 và 31 hỏng với mã cũ (tỷ lệ 0,0602 / 0,0862), mã mới đạt (0,0 / 0,0; với Whisper thật 0,0367 / 0,0203). Sáu job với kịch bản S1 đều đạt. 92 job đạt của cùng lô trùng 92/92 với HEAD về từ, mốc, mã và tỷ lệ.

## Giới hạn

- Kịch bản thật của video 30, 31 chỉ có trong DB; S2 là giả định có căn cứ.
- Video 35 vẫn chưa rõ nguyên nhân.
- Nhóm số tính vào `split_group_count` dưới trần 5%.
- Số đơn lẻ giữ cho FIX3, FIX4.
- Bước nhóm chỉ chạy khi sau lượt nghe lại job vẫn trượt cổng.

## Kết luận

`OI-CP7-11-Q3` được xử lý cho lớp số nói trong tỉ số, giờ, số thập phân, khoảng. Phần còn mở: video 35.
