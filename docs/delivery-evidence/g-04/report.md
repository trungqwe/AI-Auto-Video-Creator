# Báo cáo bằng chứng G-04

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `4dc0964ce286447d5d95987b402d08b9e99cdfa5` (4dc0964)
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-04 trong `docs/implementation/g/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 7)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `43 failed, 2 passed in 0.50s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/orchestration/test_g_grant_issuance.py::test_first_issue_returns_claims_and_inserts - NotImplementedError: G-04 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_grant_issuance.py::test_claims_are_frozen - NotImplementedError: G-04 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_grant_issuance.py::test_other_lease_with_live_grant_raises - NotImplementedError: G-04 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_grant_issuance.py::test_same_lease_same_request_is_idempotent - NotImplementedError: G-04 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_grant_issuance.py::test_reissue_after_expiry_increments_generation_and_revokes_old_grant - NotImplementedError: G-04 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_grant_issuance.py::test_fencing_rejects_result_of_old_grant_after_reissue - NotImplementedError: G-04 RED skeleton`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test hợp lệ (`test_ttl_seconds_is_required`, `test_module_imports_only_stdlib_and_g03_fencing`) đã PASS ngay từ đầu. Tất cả 43 test thất bại đều là `NotImplementedError` do khung skeleton chưa cài logic xử lý (hoặc assertion đồng thời kiểm tra kết quả khi skeleton raise `NotImplementedError`).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 10)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `45 passed in 0.09s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/application/orchestration/grant_issuance.py`: Cài đặt ngoại lệ `ActiveGrantExistsError`, các protocol `GrantStorePort`, `RecoveryEpochPort`, và lớp `GrantIssuer` với phương thức `issue(stage_run_id, allowed_operation, input_fingerprint, worker_lease_id, ttl_seconds, now)` bảo đảm thế hệ tăng đơn điệu `generation = latest + 1`, duy nhất một lease hoạt động mỗi stage, cấp mới khi hết hạn hoặc đổi epoch, tuần tự hóa chuỗi đọc-revoke-ghi bằng khóa `_ISSUE_LOCK`.
  - `tests/unit/orchestration/test_g_grant_issuance.py`: Bộ kiểm thử toàn diện gồm 45 test cases bao gồm kiểm tra cấp grant hợp lệ, tính bất biến của `GrantClaims`, bắt buộc `ttl_seconds`, từ chối lease khác khi grant còn hạn, tính lũy thừa khi cùng lease cùng request, kiểm thử đồng thời 8 luồng (TST-WF-INV-003) với 1 issuer và 8 issuer dùng chung store, tái cấp sau khi hết hạn tăng thế hệ và revoke grant cũ, thế hệ đơn điệu độc lập theo từng stage, tự động coi expiry hỏng là hết hạn, đọc epoch từ port lúc cấp, chuỗi hóa epoch int, thay thế grant khi cùng lease nhưng đổi epoch, kết hợp `evaluate_result_fencing` của G-03 từ chối grant cũ và epoch cũ, grant đã revoke không bao giờ trả lại, kiểm tra validation đối số đầu vào, kiểm tra rejection khi store/port trả giá trị không hợp lệ, không tiêu tốn generation khi store insert thất bại, và ranh giới import chỉ dùng stdlib và module fencing G-03.
  - `docs/delivery-evidence/g-04/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider` | 0 | `45 passed in 0.09s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `active_grant` trả grant chưa revoke kể cả đã hết hạn, issuer tự xét hạn, hạn tại biên `now == expires_at` là đã hết.
2. Cùng lease còn hạn cùng epoch cùng operation+fingerprint thì trả lại grant cũ, khác operation/fingerprint thì `ActiveGrantExistsError`.
3. Cùng lease nhưng epoch cũ thì revoke và cấp mới theo epoch hiện hành, lease khác vẫn `ActiveGrantExistsError`.
4. Expiry hỏng coi là hết hạn (fail-closed, grant đó cũng bị `evaluate_result_fencing` từ chối `INVALID_EXPIRY`).
5. Khóa `_ISSUE_LOCK` mức module chỉ bảo đảm trong một tiến trình, đa tiến trình cần ràng buộc duy nhất ở store thật (YC-HT-G-01, GIẢ ĐỊNH chưa kiểm).
6. Epoch int đổi sang chuỗi bằng `str()` (D8-G-03), bool/rỗng/None bị từ chối.
7. `grant_id` là uuid4.

## Ánh xạ phản ví dụ

- Hai worker cùng giữ lease một stage -> `test_eight_threads_issue_one_active_grant`, `test_eight_issuers_sharing_one_store_issue_one_active_grant`
- Generation lặp lại sau retry -> `test_reissue_after_expiry_increments_generation_and_revokes_old_grant`, `test_generation_continues_after_latest_grant_was_revoked`, `test_revoked_grant_is_never_active_or_returned_again`
- Grant mới mang epoch cũ -> `test_epoch_is_read_from_port_at_issue_time`, `test_same_lease_with_stale_epoch_gets_replacement_grant`, `test_fencing_rejects_old_epoch_result_after_epoch_change`
- Result của grant cũ được chấp nhận -> `test_fencing_rejects_result_of_old_grant_after_reissue`

## coveredIds

- `CT-WF-004`
- `INV-003`
- `INV-016`
- `TST-WF-INV-003`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`
- `YC-HT-G-01 bảng grant và ràng buộc duy nhất ở store thật`

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, ExecutionGrant, fencing.py.
- Chỉ stdlib.
- Không gọi dịch vụ thật.
