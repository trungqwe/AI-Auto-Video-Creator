# Báo cáo bằng chứng G-08

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `9dd3efea87d4172a55ae0bdd8e8b8f93025dc57c`
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-08 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider` (chạy trên khung stub chưa có logic ở bước 8)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `45 failed, 2 passed, 10 warnings in 0.57s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/orchestration/test_g_variant_reservation_flow.py::test_reserve_creates_active_reservation_and_bumps_revision_once - NotImplementedError: G-08 RED stub: reserve`
  - `FAILED tests/unit/orchestration/test_g_variant_reservation_flow.py::test_stale_expected_revision_creates_nothing_and_keeps_revision - NotImplementedError: G-08 RED stub: reserve`
  - `FAILED tests/unit/orchestration/test_g_variant_reservation_flow.py::test_var_001_two_jobs_same_fingerprint_one_wins_other_stale_then_conflict - NotImplementedError: G-08 RED stub: reserve`
  - `FAILED tests/unit/orchestration/test_g_variant_reservation_flow.py::test_release_requires_recorded_terminal_failure - NotImplementedError: G-08 RED stub: release`
  - `FAILED tests/unit/orchestration/test_g_variant_reservation_flow.py::test_convert_only_on_completion_and_only_once - NotImplementedError: G-08 RED stub: convert`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; mọi test fail đều là NotImplementedError do stub; 2 test đã pass sẵn kiểm tra ranh giới giao diện và import tĩnh:
  - `test_port_exposes_exactly_the_five_registry_methods`
  - `test_module_imports_only_stdlib_and_controlplane_domain`

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider` (sau khi cài đặt logic ở bước 10-13)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `47 passed in 0.06s`

## Thay đổi

- `src/controlplane/application/orchestration/variant_reservation_flow.py`: Định nghĩa các cấu trúc dữ liệu (`ReserveVariantRequest`, `VariantReservationRecord`, `VariantReceipt`), giao diện `VariantRegistryPort` (5 phương thức: `current_revision`, `find_by_job`, `find_active_by_fingerprint`, `save`, `bump_revision`), và lớp điều phối `VariantReservationFlow` với các phương thức `reserve` (kiểm tra CAS revision và conflict), `release`, `convert` qua helper `_settle`, cùng các hook chỉ đọc `on_wait`, `on_desktop_offline`, `on_lease_expired`.
- `tests/unit/orchestration/test_g_variant_reservation_flow.py`: Cung cấp `FakeRegistry` an toàn luồng với các assertion bất biến (không cho phép mở lại reservation đã terminal, không cho phép hai dòng reservation cho cùng một job), cùng 47 test case bao quát đầy đủ kịch bản VAR-001 (stale rồi conflict), VAR-003 (mất ACK, offline, hết hạn lease không đổi trạng thái, terminal release/convert không bump thêm), VAR-004 (hai biến thể khác nhau cùng thành công sau khi làm mới revision), kiểm tra bất biến thread-safety, tính bất biến của receipt và giới hạn import chỉ dùng stdlib và controlplane.domain.
- `docs/delivery-evidence/g-08/report.md`: Báo cáo bằng chứng thực thi chu kỳ test-first RED-GREEN với số liệu thực tế, bảng lệnh kiểm tra, ghi nhận các quyết định mặc định (D8), ánh xạ phản ví dụ và danh sách chờ checkpoint.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider` | 0 | `47 passed in 0.06s` |
| 2 | `git diff --check` | 0 | Đạt, không có lỗi định dạng hay khoảng trắng thừa |

## Quyết định mặc định (D8)

1. `release`/`convert` nhận `workspace_id`, `job_id`, `job_state` (JobState đã ghi nhận): release chỉ với FAILED_FINAL, convert chỉ với COMPLETED; ngoài ra FORBIDDEN_TRANSITION; job chưa có reservation là NOT_FOUND.
2. Thứ tự reserve: replay/conflict theo job, rồi stale (revision khác expected), rồi conflict fingerprint ACTIVE/CONVERTED của job khác, vì TST-WF-VAR-001 yêu cầu bên thua gặp stale trước rồi conflict sau refresh (khác thứ tự trong adapter PostgreSQL P6, vốn chỉ là hạ tầng).
3. Mọi input (kể cả idempotency_key và expected revision) phải khớp để trả receipt cũ; khác bất kỳ trường nào cho cùng job là VARIANT_CONFLICT; mỗi job tối đa một dòng reservation, trạng thái cuối không mở lại.
4. Receipt trả lại luôn phản ánh trạng thái hiện tại của reservation (RELEASED/CONVERTED), không bao giờ hồi sinh ACTIVE và không bump revision.
5. save trước, bump_revision sau; save lỗi thì không bump. Khoá `_FLOW_LOCK` toàn cục, phù hợp D8-G-08/D8-G-12.
6. on_wait, on_desktop_offline, on_lease_expired chỉ đọc, không TTL.

## Ánh xạ phản ví dụ

Bốn phản ví dụ của slice (hai job cùng giữ chỗ một biến thể; lease hết hạn làm release; retry tạo reservation thứ hai; revision không tăng khi release) trỏ tới tên test đã chạy:
- `test_var_001_two_jobs_same_fingerprint_one_wins_other_stale_then_conflict`
- `test_concurrent_jobs_with_same_fingerprint_exactly_one_wins`
- `test_wait_offline_and_lease_expiry_do_not_change_reservation`
- `test_lost_ack_retry_returns_old_receipt_without_new_reservation`
- `test_concurrent_identical_reserve_creates_single_reservation`
- `test_release_after_failed_final_bumps_revision_once_and_is_idempotent`
- `test_each_create_release_convert_bumps_revision_exactly_once`
- `test_old_receipt_never_resurrects_active`

## coveredIds

- `CT-ORC-012`, `TST-WF-VAR-001`, `TST-WF-VAR-003`, `TST-WF-VAR-004` (phía G). Không đóng TST-WF-VAR-002 (thuộc G-09/G-10).

## Danh sách chờ user (pendingUserCheckpoint)

- `PUC-G-02`, `USER-CKPT-D9-D10`, `CP7 tài nguyên thật (D5)`

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2. Chỉ stdlib và controlplane.domain (đọc). Fake in-memory, chưa có adapter PostgreSQL (thuộc YC-HT-G-01). Không gọi dịch vụ thật.
