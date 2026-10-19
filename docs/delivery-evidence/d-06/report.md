# Báo cáo bằng chứng D-06

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4aeaf9fb552e1c717c20614cbd9ab2487ff850fc`
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-06.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider` (chạy với khung angles.py chưa có hành vi)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `56 failed, 4 passed in 0.52s`
- Chi tiết các test FAILED chọn lọc kèm thông điệp assertion nguyên văn:
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_story_angle_has_exactly_the_contract_fields`: `AssertionError: assert ['City Council', 'Bridge A'] == ('City Council', 'Bridge A')`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_fingerprint_is_sha256_over_normalized_question_entities_timeframe`: `AssertionError: assert '' == '5dbb512d93ec...736648e9b8f8a'`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_fingerprint_changes_with_each_basis_field[overrides0]`: `AssertionError: assert '' != ''`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_normalization_folds_case_whitespace_unicode_form_and_entity_order`: `AssertionError: assert '  \uff21B   c ' == 'ab c'`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_diacritics_are_meaningful_and_not_stripped`: `AssertionError: assert '' != ''`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_story_angle_rejects_malformed_fields[overrides0-ValueError]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_requested_count_outside_one_to_three_is_rejected[0]`: `Failed: DID NOT RAISE AngleSetRejected`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_requested_count_one_to_three_is_accepted[1]`: `AssertionError: assert False (+ where False = isinstance(None, StoryAngleSet))`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_angle_matching_latest_script_fingerprint_is_excluded_and_recorded`: `AttributeError: 'NoneType' object has no attribute 'angles'`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_history_entry_requires_positive_integer_sequence[0]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_missing_variation_policy_revision_is_input_not_ready[None]`: `Failed: DID NOT RAISE AngleSetRejected`
  - `FAILED tests/unit/creative/test_d06_story_angles.py::test_set_is_frozen_isolated_from_input_and_serializable`: `AttributeError: 'NoneType' object has no attribute 'to_payload'`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; RED là sai oracle (fingerprint rỗng khác expected, DID NOT RAISE assertion/AngleSetRejected, NoneType không có thuộc tính, trả None).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `60 passed in 0.12s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/creative/domain/angles.py`: Triển khai thuần domain cho StoryAngle và StoryAngleSet (CT-AI-003, TST-AI-INV-013 mức góc kể), không I/O, không clock, không uuid/random. Bao gồm các hằng số cấu hình (`MIN_REQUESTED_COUNT`, `MAX_REQUESTED_COUNT`, các mã lỗi reject); ngoại lệ `AngleSetRejected`; hàm `normalize_text` (chuẩn hoá NFKC, casefold, gom khoảng trắng, giữ nguyên dấu tiếng Việt); hàm `compute_distinction_fingerprint` (tính SHA-256 qua `request_hash` trên narrative question, danh sách focus entities đã sắp xếp và khử trùng, và timeframe); frozen dataclass `StoryAngle` (kiểm tra chặt chẽ các trường bắt buộc, đóng băng tuple, suy diễn `distinction_fingerprint` trong `__post_init__`, kèm `to_payload`); frozen dataclass `AngleHistoryEntry` (kiểm tra `sequence` số nguyên dương); frozen dataclass `ExcludedAngle`; frozen dataclass `StoryAngleSet` (chứa 1-3 góc đã lọc, danh sách góc bị loại trừ, variation policy revision, kèm `to_payload`); hàm `build_story_angle_set` kiểm tra `requested_count` trong khoảng 1–3, từ chối góc trùng fingerprint trong cùng set (`SAME_RUN_ANGLE_DUPLICATE`), loại góc trùng fingerprint với script gần nhất theo sequence lớn nhất trong lịch sử, kiểm tra cổng khai thác hết set ban đầu mới cho phép set mới (`INITIAL_SET_NOT_EXHAUSTED`), ghi nhận variation policy revision, và cắt danh sách theo `requested_count`.
  - `tests/unit/creative/test_d06_story_angles.py`: Bộ kiểm thử đơn vị toàn diện với docstring khai báo `coveredIds: CT-AI-003, TST-AI-INV-013`; kiểm tra đầy đủ các trường của StoryAngle; kiểm tra tính toán fingerprint SHA-256 trên narrative question, focus entities, timeframe đã chuẩn hoá và bỏ qua angle ID, title, summary, style preset, evidence refs; kiểm tra thay đổi từng trường cơ sở; kiểm tra chuẩn hoá Unicode NFKC/NFD và giữ nguyên dấu tiếng Việt; kiểm tra kiểm thực và bất biến của StoryAngle, to_payload; kiểm tra requested_count ngoài 1–3 bị từ chối; kiểm tra trùng fingerprint trong cùng set bị từ chối (`SAME_RUN_ANGLE_DUPLICATE`); kiểm tra loại trừ góc trùng script gần nhất theo sequence lớn nhất; kiểm tra từ chối khi hết góc; kiểm tra cắt theo requested_count; kiểm tra tính hợp lệ của history sequence; kiểm tra điều kiện sinh set mới (`initial_set_not_exhausted`); kiểm tra ghi nhận variation policy revision và từ chối khi thiếu (`INPUT_NOT_READY`); kiểm tra tính đóng băng và tuần tự hoá JSON của StoryAngleSet; kiểm tra từ chối input lỗi; kiểm tra allowlist import chỉ sử dụng các module cho phép và tái sử dụng `request_hash`, `ResourceRef`.
  - `docs/delivery-evidence/d-06/report.md`: Báo cáo bằng chứng chuyển giao của task D-06.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider` | 0 | 60 passed in 0.12s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## coveredIds

`CT-AI-003, TST-AI-INV-013 (mức góc kể)`

## Quyết định mặc định (D8)

1. Fingerprint = request_hash trên {narrative_question, focus_entities sắp xếp và khử trùng, timeframe} sau chuẩn hoá NFKC, casefold, gộp khoảng trắng; không bỏ dấu tiếng Việt; không gồm angle_id, title, summary, style, evidence refs.
2. StoryAngle không có trường style riêng, ba góc chỉ khác title/style được kiểm bằng cách đổi angle_id, title, summary, planned_creative_elements.
3. Planned inference và creative tách hai tuple; suitability là chuỗi do caller cấp (GIẢ ĐỊNH), evidence_refs bắt buộc ít nhất một ResourceRef.
4. Script gần nhất là entry có sequence lớn nhất trong history truyền vào, sequence phải duy nhất, chỉ góc trùng fingerprint của script đó bị loại và ghi vào excluded.
5. Set mới chỉ được khi initial_set_fingerprints đều có trong history, thiếu thì initial_set_not_exhausted, generation ghi 'initial' hoặc 'new_set'.
6. Số góc trong set = min(số góc còn lại sau loại, requested_count), rỗng thì insufficient_distinct_angles.
7. Variation policy revision do caller cấp, thiếu thì INPUT_NOT_READY.
8. Không parse raw output của model và không gọi RefResolver trong slice này, việc đó thuộc pipeline D-08/D-14 (GIẢ ĐỊNH).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt
- Chất lượng góc kể thật để CP7-D-02
- Validator biến thể thuộc D-11

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.
