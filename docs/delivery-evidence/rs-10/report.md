# RS-10: Service accounts chỉ đọc (module J)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/accounts.py`
- `tests/integration/read_screens/test_rs_10_accounts.py`
- `docs/delivery-evidence/rs-10/report.md`

## RED
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_10_accounts.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `34 failed, 9 passed in 1.05s`
- Mọi lỗi trong lần chạy trên stub rỗng đều là assertion/DID NOT RAISE (`assert [] == ['acc-d', 'acc-b', 'acc-a', 'acc-c', 'acc-e', 'acc-f']`, `KeyError: 'acc-c'`, `DID NOT RAISE ValueError`), không có lỗi import hay lỗi thu thập test.

## GREEN
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_10_accounts.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `43 passed in 0.64s`
- Toàn bộ 43 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/accounts.py').read_text(encoding='utf-8').lower(); assert 'capabilities_json' not in t and 'credential_' not in t and 'project_ref' not in t and 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'os.environ' not in t, 'RS-10'"` | Quét mã nguồn accounts.py bảo đảm không chứa chuỗi cấm (bước 9) | 0 |
| `git diff --check` | Kiểm tra diff và khoảng trắng thừa cuối dòng (bước 11) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `AccountModuleService(connection_scope)` cung cấp đầy đủ hai phương thức `fetch_page` và `fetch_one`. Câu truy vấn SQL thực thi trên bảng `controlplane.cp_external_accounts a` với id `external_account_id` ánh xạ sang `account_ref`; sắp xếp theo `a.updated_at` (kèm `external_account_id` làm tie-break trong keyset); lọc theo `provider` (`drive`, `router`) qua `a.provider = %s` và `status` qua `a.status = %s` bằng so khớp chính xác. Giá trị lọc lạ tự trả về danh sách rỗng (dù cột status có ràng buộc CHECK enum, service không bao giờ bỏ qua bộ lọc). Dòng kết quả trả về có đúng năm khóa: `account_ref`, `provider`, `account_label`, `status`, `updated_at`.
2. Kiểm thử tuân thủ đầy đủ quy tắc chung (a)–(h): Phân trang keyset hai chiều không trùng lặp và không sót dòng cho cả hai chiều `asc` và `desc`, hỗ trợ chính xác trường hợp các tài khoản chia sẻ cùng mốc thời gian cập nhật `updated_at` (`acc-b` và `acc-d`). Phương thức `fetch_one` xử lý đúng 3 trường hợp: trả về dòng hợp lệ khi tồn tại, trả `None` khi không tìm thấy hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn giữa các tenant kể cả khi cố ý dùng trùng id `acc-a`. Lọc `provider` lạ (`unknown`, `DRIVE`, `drive `, rỗng) và `status` lạ (`PENDING`, `enabled`, `ENABLED `, rỗng) trả về danh sách rỗng. Số hàng của bảng nguồn `cp_external_accounts` (8 hàng) không đổi sau tất cả các thao tác đọc. Cursor lạ, sai định dạng hoặc cố tình truyền bộ lọc lạ/sort lạ đều ném `ValueError` fail-closed (và tầng API ném `ListQueryError` khi parse bộ lọc không hỗ trợ). Chỉ test suite thực hiện INSERT SQL tối thiểu để seed dữ liệu do `src/` chưa có hàm ghi tài khoản ngoài (BL-RS-04); mã nguồn service hoàn toàn không thực hiện INSERT, UPDATE hay DELETE.
3. Không trả trường `capabilities_json`, `credential_version`, `credential_updated_at`, `credential_expires_at`, `quota_observation_ref`, `project_ref`, `health` ra khỏi service; toàn bộ token canary `CANARIES` (`PROJECT_CANARY`, `CAPABILITY_CANARY`, `HEALTH_CANARY`, `QUOTA_CANARY`) không bao giờ xuất hiện trong `json.dumps(dòng)`. Mọi câu truy vấn SQL do service sinh ra chỉ chọn năm cột registry (`a.external_account_id`, `a.provider`, `a.account_label`, `a.status`, `a.updated_at`) với điều kiện `workspace_id = %s::uuid`, hoàn toàn không tham chiếu tới các cột nhạy cảm hay thông tin định danh nội bộ. Mã nguồn `accounts.py` sạch hoàn toàn các chuỗi cấm (`capabilities_json`, `credential_`, `project_ref`, `quota_observation_ref`, `health`, `insert into`, `update controlplane`, `delete from`, `os.environ`).

## Ghi chú
- BL-RS-04: `src/` hiện chưa có writer cho `cp_external_accounts`; môi trường production có thể rỗng cho tới khi có nơi ghi (OI-RS-02).
- Sắp xếp chỉ hỗ trợ `updated_at`, sort lạ hoặc filter lạ ném `ValueError` fail-closed.
- Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.
