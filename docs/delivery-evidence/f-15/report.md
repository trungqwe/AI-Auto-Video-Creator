# Báo cáo bằng chứng F-15

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `1f92cf4e3edb03004573fffcc020f5a1b2bc3da6`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-15 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider` (chạy trên stub trung tính ở bước 9)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `40 failed, 33 passed in 0.37s`
- Các dòng FAILED tiêu biểu:
  1. `test_ready_only_when_every_condition_holds`: `AssertionError: assert (False) where False = isinstance(NotReady(reasons=('STUB-NEUTRAL',)), OutputReady)`
  2. `test_hash_compare_ignores_case_and_stores_lower_case`: `AttributeError: 'NotReady' object has no attribute 'output_sha256'`
  3. `test_single_failure_is_not_ready_with_its_reason[receipt_prepared]`: `AssertionError: assert ('STUB-NEUTRAL',) == ('receipt_not_succeeded',)`
  4. `test_create_video_output_copies_the_verified_facts`: `render.domain.output_ready.OutputReadyError: STUB-NEUTRAL`
  5. `test_render_success_with_qc_fail_is_not_ready_and_not_complete`: `AssertionError: assert (False, False, False, False) == (True, False, False, False)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy hoàn toàn trên stub trung tính.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `73 passed in 0.13s`

## Thay đổi

- `src/render/domain/output_ready.py`: triển khai đầy đủ các cấu trúc và hàm pure domain:
  - `VideoOutput`: dataclass frozen, `kw_only=True` với 7 trường (`video_output_id`, `output_artifact_ref`, `output_sha256`, `quality_report_ref`, `render_attempt_ref`, `package_fingerprint`, `output_metadata_revision`), kiểm tra không rỗng và chuẩn hóa `output_sha256` chữ thường.
  - `OutputReady`: verdict mang các tham chiếu cần thiết cho G khi mọi điều kiện nghiệm thu CT-RND-005 thỏa mãn, thuộc tính `ready = True`.
  - `NotReady`: verdict khi có ít nhất một điều kiện thất bại, chứa danh sách `reasons` theo thứ tự cố định, thuộc tính `ready = False`.
  - `OutputReadyError`: ngoại lệ với `code` máy đọc và danh sách `reasons`.
  - `evaluate_output_ready`: kiểm tra tuần tự 5 điều kiện (receipt SUCCEEDED, output hash khớp, QC report passed, refs committed, grant valid).
  - `create_video_output`: dựng `VideoOutput` duy nhất từ phán quyết `OutputReady`, ném `quality_not_passed` nếu QC fail và `output_not_ready` cho các vi phạm khác.
  - `MilestoneState`: dataclass frozen lưu 4 mốc độc lập (`render_succeeded`, `qc_passed`, `upload_verified`, `completion_committed`), thuộc tính suy diễn `completion_eligible = render_succeeded and qc_passed and upload_verified`.
  - `derive_milestones`: đọc sự thật từ `RenderAttempt` và `QualityReport`, tiếp nhận fact của I (`upload_verified`) và G (`completion_committed`).
- `tests/unit/render/test_f15_output_ready.py`: 73 ca kiểm thử bao quát toàn bộ hợp đồng CT-RND-005, TST-E2E-INV-009, 16 tổ hợp mốc độc lập, kiểm tra kiểu nghiêm ngặt và 2 bài kiểm tra vệ sinh AST (không completion, không ledger, không delete/cleanup, pure domain không I/O).
- `docs/delivery-evidence/f-15/report.md`: báo cáo bằng chứng này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider` | 0 | 73 passed in 0.13s |
| 2 | `python -c "import pathlib; assert 'STUB-' not in pathlib.Path('src/render/domain/output_ready.py').read_text(encoding='utf-8'); assert 'STUB-' not in pathlib.Path('tests/unit/render/test_f15_output_ready.py').read_text(encoding='utf-8')"` | 0 | Sạch mọi marker stub |
| 3 | `git diff --check` | 0 | Không có lỗi định dạng hay khoảng trắng thừa |
| 4 | `git diff --check` (lần cuối) | 0 | Không có cảnh báo khoảng trắng |

## Quyết định mặc định (D8)

1. `evaluate_output_ready` thêm tham số keyword-only bắt buộc `expected_sha256` ngoài năm tham số của acceptance, vì `RenderAttempt` không mang hash kỳ vọng; thiếu hoặc sai dạng thì `NotReady` trả mã lý do `expected_sha256_invalid` (GIẢ ĐỊNH, mở binding qua CONV-F-07).
2. `quality_report_ref` được gán từ `report.report_id`, `render_attempt_ref` được gán từ `attempt.render_attempt_id`.
3. Mã lý do cố định theo thứ tự: `receipt_not_succeeded`, `output_missing` / `expected_sha256_invalid` / `output_hash_mismatch`, `quality_not_passed`, `refs_not_committed`, `grant_invalid`.
4. `refs_committed` và `grant_valid` chỉ chấp nhận đúng `True` (`is not True` dẫn đến `NotReady`).
5. `create_video_output` đi qua `evaluate_output_ready`, khi thất bại QC có mã lỗi `quality_not_passed`, điều kiện khác có mã `output_not_ready`.
6. `completion_eligible = render_succeeded and qc_passed and upload_verified`, `completion_committed` là fact độc lập từ phân hệ G và không làm thay đổi eligibility.
7. Chưa có binding F→G nên dùng kiểu F-local, không wiring thật.

## Ánh xạ phản ví dụ

- QC fail vẫn tạo VideoOutput: loại trừ bởi `test_qc_fail_never_creates_a_video_output` (ném `OutputReadyError` với mã `quality_not_passed`).
- Hash lệch vẫn ready: loại trừ bởi `hash_mismatch` trong `test_single_failure_is_not_ready_with_its_reason` (trả `NotReady` với lý do `output_hash_mismatch`).
- Grant hết hạn vẫn ready: loại trừ bởi `grant_expired` trong `test_single_failure_is_not_ready_with_its_reason` (trả `NotReady` với lý do `grant_invalid`).
- Upload chưa verify vẫn eligible: loại trừ bởi `test_qc_pass_without_upload_verified_is_ready_but_not_eligible` (`completion_eligible` là `False`).
- Render success bị tính là completion: loại trừ bởi `test_render_success_is_never_counted_as_completion` (`completion_committed` luôn là `False`).

## coveredIds

- `CT-RND-005`
- `TST-E2E-INV-009`
- `acceptance §8 mục 2`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.
- Binding F→G output ready qua CONV-F-07.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Không sửa quality_report.py hay render_attempt.py.
- Chỉ stdlib, không gọi dịch vụ thật.
- Module không có hàm tạo completion, ledger, xóa hay cleanup.
