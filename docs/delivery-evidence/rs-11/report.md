# RS-11: Service cost chỉ đọc (module J)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/cost.py`
- `tests/integration/read_screens/test_rs_11_cost.py`
- `docs/delivery-evidence/rs-11/report.md`

## RED
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_11_cost.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `32 failed, 10 passed in 0.99s`
- Mọi lỗi trong lần chạy trên stub rỗng đều là assertion/DID NOT RAISE (`assert [] == ['cost-d', 'cost-b', 'cost-a', 'cost-c', 'cost-e', 'cost-f', 'cost-g']`, `KeyError: 'cost-g'`, `DID NOT RAISE ValueError`), không có lỗi import, lỗi cú pháp hay lỗi thu thập test.

## GREEN
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_11_cost.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `42 passed in 0.67s`
- Toàn bộ 42 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/cost.py').read_text(encoding='utf-8').lower(); assert 'float(' not in t and 'operation_ref' not in t and 'batch_ref' not in t and 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'os.environ' not in t, 'RS-11'"` | Quét mã nguồn cost.py bảo đảm không chứa chuỗi cấm (bước 9) | 0 |
| `git diff --check` | Kiểm tra diff và khoảng trắng thừa cuối dòng (bước 12) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `CostModuleService(connection_scope)` cung cấp đầy đủ hai phương thức `fetch_page` và `fetch_one`. Câu truy vấn SQL thực thi trên bảng `controlplane.cp_cost_records c` với id `record_id` ánh xạ sang `cost_id`; sắp xếp theo `c.occurred_at` (ánh xạ sang khóa sắp `recorded_at` kèm `record_id` làm tie-break trong keyset); lọc theo `provider` qua `c.provider = %s` và `job_id` qua `c.job_ref = %s`. Dòng kết quả trả về có đúng bảy khóa: `cost_id`, `job_id` (giá trị `None` khi không gắn job), `provider`, `amount`, `currency`, `amount_basis`, `recorded_at`. Trường `amount` là chuỗi số thập phân được định dạng bằng `format(value, 'f')` để giữ nguyên mọi chữ số thập phân và tránh dạng khoa học; bằng `actual_cost` nếu có (kể cả khi `actual_cost = 0`), ngược lại bằng `estimated_cost`; `amount_basis` phản ánh chính xác nguồn giá trị là `'actual'` hoặc `'estimated'`. Các giá trị thập phân dài như `0.000123`, `0.0000001` và `12345678901234567890.123456789` được giữ nguyên vẹn toàn bộ chữ số.
2. Kiểm thử tuân thủ đầy đủ quy tắc chung (a)–(h): Phân trang keyset hai chiều không trùng lặp và không sót dòng cho cả hai chiều `asc` và `desc`, hỗ trợ chính xác trường hợp các bản ghi chi phí chia sẻ cùng mốc thời gian `occurred_at` (`cost-b` và `cost-d`). Phương thức `fetch_one` xử lý đúng 3 trường hợp: trả về dòng hợp lệ khi tồn tại, trả `None` khi không tìm thấy hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn giữa các tenant kể cả khi cố ý dùng trùng id `cost-a`. Lọc `provider` lạ (`unknown`, `ROUTER`, `router `, rỗng) và `job_id` lạ (`job-9`, `JOB-1`, `job-1 `, rỗng, `'None'`) trả về danh sách rỗng (các bản ghi không gắn job như `cost-b`, `cost-f` không bao giờ khớp bộ lọc job). Số hàng của bảng nguồn `cp_cost_records` (9 hàng) không đổi sau tất cả các thao tác đọc. Cursor lạ, sai định dạng hoặc cố tình truyền bộ lọc lạ/sort lạ đều ném `ValueError` fail-closed (và tầng API ném `ListQueryError` khi parse bộ lọc không hỗ trợ). Dữ liệu được seed thông qua `PostgresCostLedger.append`; mã nguồn service hoàn toàn không thực hiện INSERT, UPDATE hay DELETE.
3. Không trả trường `operation_ref`, `batch_ref`, `source`, `service`, `quantity`, `unit`, `cost_category` ra khỏi service; toàn bộ token canary `CANARIES` (`OPERATION_CANARY`, `BATCH_CANARY`, `SOURCE_CANARY`, `SERVICE_CANARY`, `UNIT_CANARY`) không bao giờ xuất hiện trong `json.dumps(dòng)`. Mọi câu truy vấn SQL do service sinh ra chỉ chọn bảy cột registry (`c.record_id`, `c.job_ref`, `c.provider`, `c.estimated_cost`, `c.actual_cost`, `c.currency`, `c.occurred_at`) với điều kiện `workspace_id = %s::uuid`, hoàn toàn không tham chiếu tới các cột nhạy cảm hay thông tin định danh nội bộ. Mã nguồn `cost.py` sạch hoàn toàn các chuỗi cấm (`float(`, `operation_ref`, `batch_ref`, `source`, `insert into`, `update controlplane`, `delete from`, `os.environ`).

## Ghi chú
- Bản ghi chi phí được seed qua `PostgresCostLedger.append`, service chỉ đọc và không bao giờ ghi dữ liệu.
- Sắp xếp chỉ hỗ trợ `recorded_at`, sort lạ hoặc filter lạ ném `ValueError` fail-closed.
- Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.
