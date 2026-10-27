# PW-B1: Chọn ứng viên từ bảng B cho lô

## Phạm vi và tệp đã sửa

- `src/ingestion/application/candidate_selector.py`
- `tests/integration/prod_wiring/test_pw_b1_candidate_selector.py`
- `docs/delivery-evidence/pw-b1/report.md`

## Lệnh đã chạy

### Bước 7 (RED trên khung rỗng)

- Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_b1_candidate_selector.py tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider`
- Exit code: 1
- Dòng tóm tắt: `9 failed, 39 passed in 4.26s`
- Vài dòng failure đầu chứng minh đỏ do assert nội dung:
  ```
  FAILED tests/integration/prod_wiring/test_pw_b1_candidate_selector.py::test_hotter_news_is_chosen_first_and_source_set_comes_from_build_source_set
  AssertionError: assert None == AllocationCandidate(candidate_ref='b1-1', angle_slot='angle-1', source_set_ref='single_article:b1-1:6f955e65a62bfa96be4aaf26633eea00170ca801cad91a2b78d23f3cecdb64b7')
  FAILED tests/integration/prod_wiring/test_pw_b1_candidate_selector.py::test_two_videos_per_news_get_different_angle_slots_and_used_candidates_never_repeat
  AssertionError: assert [None, None, None, None, None, None] == ['b1-1', 'b1-1', 'b1-4', 'b1-4', 'b1-7', 'b1-7']
  FAILED tests/integration/prod_wiring/test_pw_b1_candidate_selector.py::test_selector_source_uses_build_source_set_and_keeps_the_import_boundary
  AssertionError: assert 'build_source_set' in text
  ```

### Bước 11 (GREEN sau khi cài đặt)

- Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_b1_candidate_selector.py tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider`
- Exit code: 0
- Dòng tóm tắt: `48 passed in 4.40s`

### Bước 12 (Probe kiểm tra mã nguồn)

- Lệnh: `python -c "import pathlib; t = pathlib.Path('src/ingestion/application/candidate_selector.py').read_text(encoding='utf-8'); assert 'build_source_set' in t and 'random' not in t.lower() and 'from src.' not in t, 'PW-B1'"`
- Exit code: 0
- Kết quả: Exit code 0, không có AssertionError.

### Bước 13 (Kiểm tra khoảng trắng git diff)

- Lệnh: `git diff --check`
- Exit code: 0
- Kết quả: Exit code 0, không in cảnh báo whitespace.

## Quyết định và GIẢ ĐỊNH (D8)

(1) mức nóng = 1.0 * số nguồn độc lập (đếm source_id khác nhau của các revision được ghim) + 1.0 * độ mới (tuyến tính 1→0 trong 72 giờ theo published_at, thiếu thì fetched_at) + 1.0 * điểm tier tốt nhất (tier_1=1.0, tier_2=0.5, tier_3=0.0, nguồn không có tier=0.0); trọng số là HotnessWeights, đọc qua weights_provider ở mỗi lần gọi để UI sửa được, nối UI thuộc slice khác;
(2) hoà điểm xếp theo subject_id tăng dần nên kết quả xác định với cùng dữ liệu và đồng hồ;
(3) số video đã dùng đếm trong cp_job_candidates của mọi lô trong workspace (GIẢ ĐỊNH D8) nên chủ thể đủ videos_per_news_per_round (mặc định 2, khớp profile.json batch) không lặp giữa các lô; chủ thể từng thuộc job FAILED_FINAL vẫn tính là đã dùng;
(4) angle_slot = angle-<số đã dùng + 1>;
(5) candidate_ref = article_id hoặc event_id, source_set_ref = `<production_mode>:<subject_id>:<source_set_fingerprint>`; slice nối nguồn tới SourceSetPort của D (PW-W1) phải phân giải đúng định dạng này;
(6) chủ thể bị build_source_set từ chối (SourceSetRejected hoặc LookupError) bị bỏ qua, chuyển sang chủ thể kế;
(7) single_article chỉ đếm nguồn của chính bài;
(8) selector tải toàn bộ revision của workspace mỗi lần gọi, đủ cho quy mô v1 một máy.

## Việc còn mở

nối UI cấu hình trọng số và nối vào launcher thuộc PW-W1/J; không có việc chặn.