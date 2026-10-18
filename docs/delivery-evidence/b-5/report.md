# Báo cáo bằng chứng B-5

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `be1fa2ef1c1cfa31173aee1c6dff878ac2793b02`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-5 trong `docs/implementation/b/slices.md`; D3 user duyệt Phần B ngày 18/10/2026; Contract: CT-CNT-002 (`docs/09-contracts/04-source-content-contracts.md`), D8-B-05 (`docs/implementation/b/plan.md`).

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider` (chạy trên skeleton của `representative.py`)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `26 failed, 1 passed in 0.16s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_representative.py::test_lower_tier_replaces_incumbent_for_future_production: AssertionError: assert RepresentativeSelection(representative=RepresentativeCandidate(source_id='', tier=0), selection_reason='', changed=False, applies_to_future_production_only=False) == RepresentativeSelection(representative=RepresentativeCandidate(source_id='src-z', tier=1), selection_reason='higher_tier', changed=True, applies_to_future_production_only=True)`
  - `FAILED tests/unit/ingestion/test_ingestion_representative.py::test_tier_three_never_beats_tier_one: AssertionError: assert RepresentativeSelection(representative=RepresentativeCandidate(source_id='', tier=0), selection_reason='', changed=False, applies_to_future_production_only=False) == RepresentativeSelection(representative=RepresentativeCandidate(source_id='src-z', tier=1), selection_reason='keep_incumbent_same_tier', changed=False, applies_to_future_production_only=False)`
  - `FAILED tests/unit/ingestion/test_ingestion_representative.py::test_same_tier_keeps_incumbent_even_with_smaller_source_id: AssertionError: assert RepresentativeSelection(representative=RepresentativeCandidate(source_id='', tier=0), selection_reason='', changed=False, applies_to_future_production_only=False) == RepresentativeSelection(representative=RepresentativeCandidate(source_id='src-m', tier=2), selection_reason='keep_incumbent_same_tier', changed=False, applies_to_future_production_only=False)`
  - `FAILED tests/unit/ingestion/test_ingestion_representative.py::test_without_incumbent_tie_break_uses_string_order: AssertionError: assert RepresentativeCandidate(source_id='', tier=0) == RepresentativeCandidate(source_id='src-10', tier=2)`
  - `FAILED tests/unit/ingestion/test_ingestion_representative.py::test_invalid_input_fails_closed[None-candidates0]: Failed: DID NOT RAISE <class 'ValueError'>`
- Xác nhận: Hoàn toàn không có `ImportError`, `ModuleNotFoundError` hay lỗi collection; duy nhất `test_selection_reasons_are_the_contract_values` PASS trên skeleton; 26 test còn lại FAILED do `AssertionError` hoặc `Failed: DID NOT RAISE <class 'ValueError'>`.

## Thay đổi

- `src/ingestion/domain/representative.py`:
  - Hằng số: `MIN_TIER = 1`, `MAX_TIER = 3`, `HIGHER_TIER = 'higher_tier'`, `KEEP_INCUMBENT_SAME_TIER = 'keep_incumbent_same_tier'`, `TIE_BREAK_SOURCE_ID = 'tie_break_source_id'`, `SELECTION_REASONS = (HIGHER_TIER, KEEP_INCUMBENT_SAME_TIER, TIE_BREAK_SOURCE_ID)`.
  - Data models: `RepresentativeCandidate(source_id: str, tier: int)` và `RepresentativeSelection(representative: RepresentativeCandidate, selection_reason: str, changed: bool, applies_to_future_production_only: bool)` kế thừa `NamedTuple`.
  - Hàm `_candidate(value: object) -> RepresentativeCandidate`: xác thực kiểu tuple độ dài 2, kiểm tra `source_id` là chuỗi không rỗng, `tier` là số nguyên trong khoảng 1..3 (từ chối `bool`), ném `ValueError` khi dữ liệu sai định dạng (fail-closed).
  - Hàm `select_representative(incumbent, candidates)`: lựa chọn đại diện cụm duplicate bất biến theo thứ tự candidate; gộp pool, phát hiện mâu thuẫn tier cho cùng `source_id`; tìm phần tử tối ưu theo khoá `(tier, source_id)`; xử lý logic thay thế incumbent khi tier nhỏ hơn (`changed=True`, `applies_to_future_production_only=True`), giữ incumbent khi cùng hoặc kém tier (`keep_incumbent_same_tier`), và phá hoà theo `source_id` nhỏ nhất khi chưa có incumbent.
- `tests/unit/ingestion/test_ingestion_representative.py`:
  - 27 test items bao quát toàn diện các yêu cầu:
    - Kiểm tra danh sách lý do lựa chọn theo contract `SELECTION_REASONS`.
    - Tier nhỏ hơn thay thế incumbent và bật cờ `applies_to_future_production_only=True`.
    - Tier 3 không bao giờ thắng Tier 1 (cả khi có incumbent lẫn khi không có incumbent).
    - Cùng Tier giữ incumbent kể cả khi candidate có `source_id` nhỏ hơn.
    - Ổn định khi nhiều candidate cùng Tier tới liên tiếp không làm dao động representative.
    - Candidate có Tier kém hơn giữ nguyên incumbent.
    - Danh sách candidate rỗng giữ nguyên incumbent.
    - Cùng Tier cao hơn phá hoà bằng `source_id` nhỏ nhất.
    - Chưa có incumbent: `source_id` nhỏ nhất thắng trong tier tốt nhất.
    - Chưa có incumbent: phá hoà theo thứ tự chuỗi ký tự (`'src-10' < 'src-9'`).
    - Chưa có incumbent: hoạt động chính xác với duy nhất 1 candidate.
    - Chấp nhận tuple thô `(source_id, tier)` chuyển đổi thành `RepresentativeCandidate`.
    - 3 kịch bản kiểm thử độc lập thứ tự đầu vào (`itertools.permutations`) cho cả list và iterator.
    - 12 ca kiểm thử fail-closed từ chối input không hợp lệ (rỗng không incumbent, tier ngoài khoảng, kiểu dữ liệu sai, candidate trùng `source_id` nhưng khác tier).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider` | 0 | 27 passed in 0.03s |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.04s |

## Quyết định mặc định (D8)

(Ghi nhận dưới dạng GIẢ ĐỊNH theo quy chế D8, không phải đã duyệt chính thức):
1. `tier` là số nguyên trong khoảng 1..3, Tier 1 là mức ưu tiên cao nhất; kiểu `bool`, sai kiểu hoặc ngoài khoảng gây lỗi `ValueError`.
2. Có `incumbent` mà không có candidate nào có Tier nhỏ hơn hẳn (cùng hoặc kém hơn) → giữ nguyên `incumbent`, gán lý do `keep_incumbent_same_tier` vì tập enum chỉ có 3 giá trị contract.
3. Có `incumbent` và có nhiều candidate cùng Tier tốt hơn → chọn candidate có `source_id` nhỏ nhất, gán lý do `higher_tier`.
4. Chưa có `incumbent`: gán `higher_tier` khi có đúng một candidate ở Tier tốt nhất và có candidate Tier kém hơn trong pool; ngược lại gán `tie_break_source_id` (kể cả trường hợp chỉ có một candidate); `changed=False` và `applies_to_future_production_only=False` vì đây là lượt chọn ban đầu, không phải hành động thay thế.
5. Thứ tự chuỗi là so sánh chuỗi `str` mặc định của Python theo giá trị Unicode code point (ví dụ `'src-10' < 'src-9'`).
6. Cùng `source_id` nhưng xuất hiện với `tier` mâu thuẫn (kể cả mâu thuẫn với `incumbent`) → ném `ValueError` fail-closed; các bản ghi trùng lặp hoàn toàn cả `source_id` và `tier` được gom hợp nhất tự động.
7. `tier` được tra cứu qua port `SourceTierLookup` thuộc slice B-6; module `representative.py` tiếp nhận `tier` đã được giải quyết sẵn.
8. Không thêm bất kỳ thư viện bên ngoài nào, chỉ sử dụng module chuẩn của Python (`collections.abc`, `typing`).

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Binding Tier A→B qua REQ-B-CONV-07

## Giới hạn

- Không chạy full test suite, không chạy `tests/m1`, `tests/m2`.
- Không sửa `pyproject.toml`, `uv.lock`, file binding hay fixture.
- Không gọi dịch vụ thật hay đọc bí mật.
- Không sửa `HANDOFF.md`, `README.md`, `CHANGELOG.md` hay checklist nằm ngoài owned paths trong slice này.
