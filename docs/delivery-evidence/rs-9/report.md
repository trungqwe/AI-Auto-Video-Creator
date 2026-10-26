# RS-9: Service sessions chỉ đọc (module G)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/sessions.py`
- `tests/integration/read_screens/test_rs_9_sessions.py`
- `docs/delivery-evidence/rs-9/report.md`

## RED
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_9_sessions.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `30 failed, 6 passed in 0.77s`
- Mọi lỗi trong lần chạy trên stub rỗng đều là assertion/DID NOT RAISE (`assert [] == ['ses-d', 'ses-c', 'ses-b', 'ses-a']`, `DID NOT RAISE ValueError`, `KeyError: 'ses-a'`), không có lỗi import hay lỗi thu thập test.

## GREEN
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_9_sessions.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `36 passed in 0.67s`
- Toàn bộ 36 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/sessions.py').read_text(encoding='utf-8').lower(); assert 'cp_auth_sessions' not in t and 'token_hash' not in t and 'recovery_epoch' not in t and 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'os.environ' not in t, 'RS-9'"` | Quét mã nguồn sessions.py bảo đảm không chứa chuỗi cấm (bước 11) | 0 |
| `git diff --check` | Kiểm tra diff và khoảng trắng thừa cuối dòng (bước 13) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `SessionModuleService(connection_scope)` cung cấp đầy đủ hai phương thức `fetch_page` và `fetch_one`. Câu truy vấn SQL thực thi trên bảng `controlplane.cp_app_sessions s` với id `session_ref`; sắp xếp theo `s.started_at` (kèm `session_ref` làm tie-break trong keyset); lọc theo `status` (`ACTIVE`, `ENDED`, `ABANDONED`) qua `s.status = %s`, giá trị status lạ tự trả về danh sách rỗng (do bảng có CHECK ràng buộc ba giá trị hợp lệ). Dòng kết quả trả về có đúng bốn khóa: `session_id`, `status`, `started_at`, `finished_at`. Trường `finished_at` ánh xạ từ `ended_at`, nhận giá trị `None` (`null`) khi phiên còn đang chạy (`ended_at IS NULL`), tuyệt đối không phải chuỗi rỗng.
2. Kiểm thử tuân thủ đầy đủ quy tắc chung (a)–(h): Phân trang keyset hai chiều không trùng lặp và không sót dòng cho cả hai chiều `asc` và `desc`, hỗ trợ chính xác trường hợp các phiên chia sẻ cùng mốc thời gian bắt đầu `started_at` (`ses-b` và `ses-d`). Phương thức `fetch_one` xử lý đúng 3 trường hợp: trả về dòng hợp lệ khi tồn tại, trả `None` khi không tìm thấy hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn giữa các tenant kể cả khi cố ý dùng trùng id `ses-a`. Lọc `status` lạ (`RUNNING`, `FINISHED`, `active`, `ACTIVE `, rỗng) trả về danh sách rỗng. Số hàng của bảng nguồn `cp_app_sessions` (6 hàng) và bảng xác thực `cp_auth_sessions` (1 hàng) không đổi sau tất cả các thao tác đọc. Cursor lạ, sai định dạng hoặc cố tình truyền bộ lọc lạ/sort lạ đều ném `ValueError` fail-closed (và tầng API ném `ListQueryError` khi parse bộ lọc không hỗ trợ). Chỉ test suite thực hiện INSERT SQL tối thiểu để seed dữ liệu do `src/` chưa có hàm ghi phiên ứng dụng (BL-RS-04); mã nguồn service hoàn toàn không thực hiện INSERT, UPDATE hay DELETE.
3. Không trả trường `recovery_epoch` ra khỏi service; toàn bộ token canary `EPOCH_CANARY` (`CANARY-EPOCH`) và các token xác thực `CANARY-AUTH-ACTOR`, `AUTH_ACTOR_ID`, `AUTH_SESSION_ID`, `AUTH_TOKEN_HASH` không bao giờ xuất hiện trong `json.dumps(dòng)`. Hàng trong `cp_auth_sessions` chứa canary không bao giờ bị truy vấn: test ghi lại toàn bộ câu lệnh SQL được service thực thi và xác nhận 100% câu lệnh chỉ truy vấn `controlplane.cp_app_sessions` với điều kiện `workspace_id = %s::uuid`, hoàn toàn không tham chiếu tới `cp_auth_sessions`, `cp_actors`, `token_hash` hay `recovery_epoch`. Mã nguồn `sessions.py` sạch hoàn toàn các chuỗi cấm (`cp_auth_sessions`, `token_hash`, `recovery_epoch`, `insert into`, `update controlplane`, `delete from`, `os.environ`).

## Ghi chú
- BL-RS-04: `src/` hiện chưa có writer cho `cp_app_sessions`; môi trường production có thể rỗng cho tới khi có nơi ghi.
- Sắp xếp chỉ hỗ trợ `started_at`, sort lạ hoặc filter lạ ném `ValueError` fail-closed.
- Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.
