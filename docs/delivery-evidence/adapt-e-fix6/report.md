# Báo cáo ADAPT-E-FIX6

Nhóm lỗi: `OI-CP7-10-F15` (lô 7150f8a9, RG-09 F10d của CP7-10): job FAILED_FINAL ở align, `word_coverage_incomplete`, do từ Whisper cho độ dài 0 ngay sau từ trước (từ "can" 25,60-25,60 s sau "there" 25,20-25,60 s) bị bỏ.

## Tệp đã sửa

- `src/voice/adapters/real_whisper_aligner.py`: thêm khối chia khoảng của từ trước cho từ kết thúc đúng chỗ từ trước kết thúc (ngay trước `rescued = end <= start`), cập nhật docstring. Không đổi ngưỡng, profile, nhánh rescued.
- `tests/integration/adapt/e/test_adapt_e_aligner_zero_length.py` (mới), `test_adapt_e_aligner_edges.py`, `test_adapt_e_tts_aligner.py`.

## Lệnh đã chạy

| Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- |
| `git diff --check` | 0 | - |
| `python -m pytest tests/integration/adapt/e -q -p no:cacheprovider` | 0 | `112 passed in 2.41s` |
| `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_e2_voice_ports.py -q -p no:cacheprovider` | 0 | `149 passed in 12.75s` |
| `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7638 passed, 2561 subtests passed in 24.54s` |
| probe lệnh 5, 6, 9 (python -c) | 0 | - |

## Trước và sau bản sửa

Với mã cũ (HEAD 4ca228c) cùng bộ test mới: `6 failed, 106 passed`; sáu ca hỏng là 4 ca trong test_adapt_e_aligner_zero_length.py (cp7_10, two_zero_length_words_in_a_row, hai ca tham số của zero_length_groups_count_under_the_cap), `test_zero_length_word_ending_with_the_word_before_shares_its_span` và `test_overlap_zero_length_and_overrun_are_bounded_not_invented`. Với mã mới: `112 passed`, 0 ca hỏng.

## Ca CP7-10

spans: there (25200, 25450), can (25450, 25600), be (25600, 25740); đủ 8 từ, không missing, `split_group_count` = 1, `split_word_count` = 2.

## Kết luận

`OI-CP7-10-F15` đã đóng.
