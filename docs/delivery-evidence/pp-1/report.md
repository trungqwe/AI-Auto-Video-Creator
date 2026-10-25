# Báo cáo bằng chứng chuyển giao: PP-1

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `src/controlplane/infrastructure/production_ports/__init__.py`: Tệp khởi tạo module cho gói `production_ports`, chỉ chứa một docstring duy nhất giới thiệu vai trò của các production adapter (`PP-1` khởi đầu với `gpu_lease`), không chứa import hay định nghĩa mã thực thi nào khác.
- `src/controlplane/infrastructure/production_ports/gpu_lease.py`: Triển khai lớp `LocalGpuLease(slots, ttl_seconds, *, lock_id=GPU_LOCK_ID, clock=time.monotonic)` thực thi giao diện `GpuLeasePort` (từ `render.ports.lease`) cho tài nguyên khóa `LOCK-DESKTOP-GPU` (`CT-RND-004`).
  * Nhận cấu hình số lượng slot (`slots`) và thời hạn thuê (`ttl_seconds`) từ nơi gọi; không định nghĩa số lượng slot dưới dạng hằng số cố định trong mã.
  * Nhận đồng hồ đo thời gian tiêm được (`clock=time.monotonic`) và định danh khóa (`lock_id=GPU_LOCK_ID`).
  * Sử dụng `threading.Lock` bảo vệ bảng quản lý lease nội bộ trong bộ nhớ một cách an toàn đa luồng.
  * Phương thức `acquire(owner_ref)` cấp `GpuLease` với `lease_id` duy nhất dạng 32 ký tự hex (`uuid.uuid4().hex`). Trước khi kiểm tra giới hạn slot, các lease đã hết hạn (`expires_at <= now`) được tự động thu hồi. Khi toàn bộ slot đang bận, ném ngoại lệ `GpuLeaseUnavailable`.
  * Phương thức `release(lease)` có tính chất idempotent, hủy đăng ký theo đúng `lease_id` mà không làm ảnh hưởng đến các lease hợp lệ khác.
  * Xác thực chặt chẽ đầu vào: từ chối `slots` không phải int dương (kể cả kiểu boolean `True`/`False`), từ chối `ttl_seconds` không phải số dương hữu hạn, từ chối `lock_id` khác `GPU_LOCK_ID`, và từ chối `owner_ref` rỗng hoặc toàn khoảng trắng bằng `ValueError`.
  * Tuyệt đối không thăm dò phần cứng (`nvidia-smi`), không đọc biến môi trường (`os.environ`), không dùng import có tiền tố `src.`, không chứa nhánh giả hay mock/fake, và không sửa đổi tệp cổng `src/render/ports/lease.py`.
- `tests/integration/prod_ports/test_pp_1_gpu_lease.py`: Bộ kiểm thử tích hợp 30 ca kiểm thử bao quát toàn bộ hành vi:
  * Kiểm tra tuân thủ giao diện `GpuLeasePort` và cấu trúc `GpuLease`.
  * Kiểm tra tranh chấp 1 slot (acquire lần hai ném `GpuLeaseUnavailable`).
  * Kiểm tra vòng đời release rồi acquire thành công, release hai lần là no-op.
  * Kiểm tra cơ chế hết hạn theo TTL: chưa hết hạn thì bị chặn, đủ TTL thì slot được cấp lại; release lease cũ đã hết hạn không giải phóng lease mới.
  * Kiểm tra trường hợp cấu hình nhiều slot (`slots=2`, `slots=3`).
  * Kiểm tra tranh chấp đồng thời từ 8 luồng (chỉ duy nhất 1 luồng thành công).
  * Kiểm tra từ chối các tham số constructor không hợp lệ (slots, ttl, lock_id) và tham số `owner_ref` rỗng.
  * Kiểm tra văn bản nguồn không chứa chuỗi cấm.
- `docs/delivery-evidence/pp-1/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ (Bước 5)
Tại Bước 5, sau khi tạo khung `__init__.py`, khung tạm `LocalGpuLease` (ném `NotImplementedError`) và bộ kiểm thử `test_pp_1_gpu_lease.py`, lệnh kiểm thử được thực thi với Python interpreter đã khóa để chứng kiến oracle RED hợp lệ:
```text
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_implements_port_and_lease_fields
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_one_slot_second_acquire_raises
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_release_then_acquire_succeeds
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_release_twice_is_noop_and_keeps_new_lease
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_not_reclaimed_before_ttl_and_reclaimed_at_ttl
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_stale_release_does_not_free_new_lease
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_two_slots_grant_exactly_two_unique_leases
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_slot_count_is_taken_from_constructor
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_eight_threads_one_slot_single_winner
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_slots[0]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_slots[-1]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_slots[True]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_slots[False]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_slots[1.5]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_slots[1]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_slots[None]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_ttl[0]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_ttl[-1]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_ttl[0.0]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_ttl[nan]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_ttl[inf]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_ttl[True]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_ttl[5]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_bad_ttl[None]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_constructor_rejects_other_lock_id
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_acquire_rejects_bad_owner_ref[]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_acquire_rejects_bad_owner_ref[   ]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_acquire_rejects_bad_owner_ref[None]
FAILED tests/integration/prod_ports/test_pp_1_gpu_lease.py::test_acquire_rejects_bad_owner_ref[7]
29 failed, 1 passed, 8 warnings in 0.25s
```
- **Exit Code:** `1`
- **Xác thực Oracle RED:**
  * 8 test hành vi thất bại do `NotImplementedError` từ khung tạm của `acquire` và `release`.
  * 1 test đa luồng (`test_eight_threads_one_slot_single_winner`) thất bại do `AssertionError` khi các luồng gặp `NotImplementedError`.
  * 16 test kiểm tra constructor (tham số `slots`, `ttl`, `lock_id`) thất bại do `DID NOT RAISE ValueError`.
  * 4 test kiểm tra `owner_ref` thất bại do `NotImplementedError` tại lệnh `acquire`.
  * 1 test kiểm tra văn bản nguồn tĩnh (`test_source_has_no_hardware_probe_environment_or_branches`) PASS ngay từ đầu.
  * Hoàn toàn không có lỗi collection, `ImportError` hay `ModuleNotFoundError`.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm tra
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 10) | `git diff --check` | 0 | Thoát 0, không có lỗi khoảng trắng thừa hay định dạng |
| Lệnh kiểm 2 (Bước 7) | `python -m pytest tests/integration/prod_ports/test_pp_1_gpu_lease.py -q -p no:cacheprovider` | 0 | `30 passed in 0.04s` |
| Lệnh kiểm 3 (Bước 8) | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/gpu_lease.py').read_text(encoding='utf-8').lower(); assert 'gpulease' in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-1'"` | 0 | Thoát 0, probe tĩnh đạt chuẩn, không có AssertionError |

## 4. Ánh xạ các yêu cầu nghiệm thu (Acceptance Criteria)

### Yêu cầu 1: Gói production_ports và lớp LocalGpuLease
- **Yêu cầu:** `__init__.py` chỉ có docstring. `gpu_lease.py` có lớp `LocalGpuLease(slots, ttl_seconds, *, lock_id=GPU_LOCK_ID, clock=time.monotonic)` cài `GpuLeasePort`; `acquire(owner_ref)` cấp `GpuLease` với `lease_id` duy nhất (`uuid.uuid4().hex`), ném `GpuLeaseUnavailable` khi đã đủ `slots` lease chưa hết hạn và thu hồi lease quá hạn trước khi đếm; `release` idempotent, so theo `lease_id`; dùng `threading.Lock`.
- **Các test chứng minh:**
  * `test_implements_port_and_lease_fields`: Xác minh đối tượng tuân thủ giao thức `GpuLeasePort`, trả về phiên bản `GpuLease` hợp lệ với `lock_id=GPU_LOCK_ID` và `lease_id` dạng 32 ký tự hex hợp lệ.
  * `test_one_slot_second_acquire_raises`: Xác minh khi cấu hình 1 slot, lần `acquire` thứ hai ném `GpuLeaseUnavailable`.
  * `test_release_then_acquire_succeeds`: Giải phóng slot cho phép `acquire` lần kế tiếp và cấp `lease_id` mới.
  * `test_release_twice_is_noop_and_keeps_new_lease`: Gọi `release` hai lần là no-op không gây lỗi và không ảnh hưởng đến lease đang hoạt động.
  * `test_not_reclaimed_before_ttl_and_reclaimed_at_ttl`: Lease không bị thu hồi trước khi hết TTL; đúng mốc TTL slot tự động được giải phóng khi có yêu cầu mới.
  * `test_stale_release_does_not_free_new_lease`: Gọi `release` trên lease cũ đã hết hạn không giải phóng lease mới đang hoạt động.
  * `test_two_slots_grant_exactly_two_unique_leases`: Cấu hình 2 slot cho phép cấp đúng 2 lease duy nhất trước khi ném `GpuLeaseUnavailable`.
  * `test_slot_count_is_taken_from_constructor`: Số lượng slot được nhận trực tiếp từ tham số khởi tạo (ví dụ `slots=3`).
  * `test_eight_threads_one_slot_single_winner`: Kiểm tra đồng bộ bằng `threading.Lock` với rào chắn `threading.Barrier(8)`; duy nhất 1 luồng lấy được lease, 7 luồng còn lại nhận `GpuLeaseUnavailable`.
- **Phản ví dụ đã loại trừ:** Số slot cố định trong mã; lease không có thời hạn; `release` lease cũ giải phóng lease mới.

### Yêu cầu 2: Xác thực tham số đầu vào và tính thuần túy
- **Yêu cầu:** Constructor từ chối `slots` không phải int dương (kể cả bool), `ttl_seconds` không dương, `lock_id` khác `GPU_LOCK_ID`; `owner_ref` rỗng là `ValueError`. Không đọc `nvidia-smi`, không biến môi trường, không hằng số slot, không nhánh giả; không sửa `src/render/ports/lease.py`.
- **Các test chứng minh:**
  * `test_constructor_rejects_bad_slots`: Từ chối `0`, `-1`, `True`, `False`, số thực `1.5`, chuỗi `'1'`, và `None`.
  * `test_constructor_rejects_bad_ttl`: Từ chối `0`, `-1`, `0.0`, `nan`, `inf`, `True`, chuỗi `'5'`, và `None`.
  * `test_constructor_rejects_other_lock_id`: Từ chối `lock_id` khác giá trị quy ước `GPU_LOCK_ID`.
  * `test_acquire_rejects_bad_owner_ref`: Từ chối chuỗi rỗng `""`, chuỗi toàn khoảng trắng `"   "`, `None`, và kiểu số `7`.
  * `test_source_has_no_hardware_probe_environment_or_branches` và Lệnh kiểm 3: Quét mã nguồn xác nhận không chứa `nvidia`, `os.environ`, `getenv`, `subprocess`, `from src.`, `mock`, hay `fake`.
  * Tệp `src/render/ports/lease.py` hoàn toàn không bị chỉnh sửa.
- **Phản ví dụ đã loại trừ:** Chấp nhận `slots=True`; đọc `nvidia-smi`; tạo nhánh giả; sửa đổi cổng `lease.py`.

### Yêu cầu 3: Bằng chứng minh bạch, trung thực và đầy đủ
- **Yêu cầu:** Bằng chứng ở `docs/delivery-evidence/pp-1/report.md`: lệnh đã chạy, mã thoát, số test pass, đã thấy RED đúng oracle trước khi implement; không ghi bí mật.
- **Các bằng chứng chứng minh:**
  * Báo cáo ghi nhận đầy đủ câu lệnh kiểm thử, exit code, và toàn bộ 30/30 test cases PASS.
  * Ghi nhận đầy đủ thông tin oracle RED tại Bước 5 với lỗi `NotImplementedError` và `DID NOT RAISE`.
  * Tiếng Việt có dấu đầy đủ, định dạng UTF-8 không BOM.
- **Phản ví dụ đã loại trừ:** Báo cáo tuyên bố PASS mà không có lệnh và mã thoát; thiếu bằng chứng RED; chứa thông tin nhạy cảm.

## 5. Giới hạn và an toàn (Limitations)
- Không ghi nhận hay xuất hiện bất kỳ bí mật, token, API key hoặc thông tin nhạy cảm nào trong mã nguồn và báo cáo.
- Không thực hiện chạy full regression suite; tuân thủ đúng nguyên tắc kỷ luật thực thi mục tiêu (chỉ chạy 3 lệnh kiểm thử được chỉ định cho gói `PP-1`).
- Tuyệt đối không can thiệp vào các nhánh `main` hay `backup`, không tự ý thực hiện `git push` hay `git merge`.
- Cổng kích hoạt sản xuất thực tế vẫn giữ nguyên trạng thái khóa an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
