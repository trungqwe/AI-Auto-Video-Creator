# Báo cáo PW-F4-FIX2

Nới test hợp đồng RenderVideo của F-20 để chấp nhận khoá sha256 đã xác minh trong ref render_output.

## Lý do

PW-F4-FIX1 (R8) thêm khoá `sha256` đã xác minh vào ref `render_output` của `output_refs`; các khẳng định so khớp tuyệt đối `result['output_refs']` của test F-20/PW-F4 vì vậy hỏng. Gói này chỉ nới đúng khẳng định đó, không đổi mã production (src không bị sửa).

## Khẳng định đã đổi

Liệt kê hai vị trí trong `tests/integration/render/test_f20_worker_activity.py`:
- `test_render_activity_runs_only_the_render_and_never_the_inspection`
- `test_reconcile_activity_settles_an_unknown_attempt_with_its_output`

Cả hai vị trí nay gọi hàm dùng chung `assert_render_attempt_and_output_refs`.
Quy tắc của hàm:
- `output_refs` có đúng 2 phần tử theo thứ tự.
- Ref `render_attempt` so khớp tuyệt đối với `ref_id` `op-render-1`.
- Ref `render_output` (sau khi bỏ qua khoá `sha256`) so khớp tuyệt đối với `ref_type` và `ref_id` = `out_ref(1)`.
- Nếu có khoá `sha256`, giá trị phải là chuỗi 64 ký tự hex thường (`0123456789abcdef`).
- Ref không có `sha256` vẫn đạt (test chạy hợp lệ trên cả mã trước và sau PW-F4-FIX1).
- Không thay đổi bất kỳ khẳng định nào khác trong tệp.

## Lệnh kiểm đã chạy

| Lệnh kiểm | Mã thoát | Kết quả |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_worker_activity.py').read_text(encoding='utf-8'); assert t.count(chr(39) + 'render_output' + chr(39) + ', ' + chr(39) + 'ref_id' + chr(39)) == 1, 'abs'; assert t.count('assert_render_attempt_and_output_refs(result[' + chr(39) + 'output_refs' + chr(39) + '])') == 2, 'calls')"` | 0 | Đạt: chuỗi `'render_output', 'ref_id'` xuất hiện đúng 1 lần, hàm chung được gọi đúng 2 lần. |
| `python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider` | 0 | Đạt: `57 passed in 0.30s`. |
| `git diff --check` | 0 | Đạt: không có lỗi khoảng trắng hay định dạng diff. |
| `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f4-fix2/report.md').read_text(encoding='utf-8'); assert 'PW-F4-FIX2' in t and 'sha256' in t, 'report')"` | 0 | Đạt: báo cáo tồn tại, đọc UTF-8 chứa chuỗi `PW-F4-FIX2` và `sha256`. |

## Phạm vi

Chỉ sửa và tạo đúng hai tệp thuộc owned paths được giao:
- `tests/integration/render/test_f20_worker_activity.py`
- `docs/delivery-evidence/pw-f4-fix2/report.md`

Không thay đổi mã nguồn trong `src/`, không sửa `migrations/`, không chạm `.ai-pm/**`, `docs/milestones/**/evidence/**`, hay các cây được bảo vệ.
