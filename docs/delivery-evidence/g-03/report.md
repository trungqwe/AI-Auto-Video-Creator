# Báo cáo bằng chứng G-03

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `7622e01f50b6257f93a5c0b90f84880b5c9bf952`
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-03 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `43 failed, 2 passed in 0.33s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/orchestration/test_g_fencing.py::test_decision_table[valid] - NotImplementedError: G-03 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_fencing.py::test_restore_same_generation_old_epoch_rejected - NotImplementedError: G-03 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_fencing.py::test_stale_generation_rejected - NotImplementedError: G-03 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_fencing.py::test_claims_from_execution_grant_maps_fields - NotImplementedError: G-03 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_fencing.py::test_invalid_expiry_never_raises[None] - NotImplementedError: G-03 RED skeleton`
  - `FAILED tests/unit/orchestration/test_g_fencing.py::test_evaluation_is_pure - NotImplementedError: G-03 RED skeleton`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test hợp lệ (`test_dataclasses_are_frozen`, `test_module_imports_only_stdlib_and_p6_domain`) đã PASS ngay từ đầu. Tất cả 43 test thất bại đều là `NotImplementedError` do khung skeleton chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `45 passed in 0.07s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/domain/orchestration/fencing.py`: Cài đặt dataclass frozen `GrantClaims` và `FencingDecision`, các hằng số mã kết quả fencing (`ACCEPTED`, `STALE_RECOVERY_EPOCH`, `STALE_EXECUTION_GENERATION`, `GRANT_MISMATCH`, `GRANT_EXPIRED`, `INVALID_EXPIRY`, `INPUT_FINGERPRINT_MISMATCH`, `OPERATION_CONFLICT`), hàm ánh xạ `claims_from_execution_grant` và hàm thuần `evaluate_result_fencing` kiểm theo thứ tự epoch -> generation -> grant -> expiry -> fingerprint -> receipt.
  - `tests/unit/orchestration/test_g_fencing.py`: Bộ kiểm thử toàn diện gồm 45 test cases bao gồm bảng quyết định 27 cases, kiểm tra phục hồi thế hệ trùng nhưng epoch cũ bị từ chối (TST-WF-INV-016), thế hệ cũ bị từ chối (TST-WF-INV-003), epoch kiểu int ở grant khớp chuỗi ở result, ánh xạ trường GrantClaims, tính bất biến của dataclass frozen, kiểm tra expiry sai/thiếu không raise, result không phải Mapping, tính thuần của hàm đánh giá và ranh giới import stdlib.
  - `docs/delivery-evidence/g-03/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider` | 0 | `45 passed in 0.07s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Mã chấp nhận là `ACCEPTED`.
2. `issued_at`/`expires_at` là chuỗi ISO 8601, ký tự `Z` được đổi thành `+00:00` trước khi parse.
3. `claims_from_execution_grant` nhận `worker_lease_id`, `issued_at`, `expires_at`, `allowed_operation`, `input_fingerprint` qua tham số keyword vì `ExecutionGrant` P6 không mang các trường này (D8-G-04).
4. Epoch so sánh bằng `str()` cho cả result, claims và current (D8-G-03); bool không coi là int/epoch hợp lệ.
5. Result không phải Mapping hoặc thiếu trường bị từ chối bằng `STALE_RECOVERY_EPOCH`, không raise.
6. Epoch của cả result và claims phải bằng epoch hiện hành, generation của cả result và claims phải bằng generation hiện hành.

## Ánh xạ phản ví dụ

- Result generation cũ được chấp nhận -> `test_decision_table[result_generation_old]` và `test_stale_generation_rejected`
- Epoch cũ generation trùng được chấp nhận -> `test_restore_same_generation_old_epoch_rejected`
- Grant hết hạn vẫn commit -> `test_decision_table[expired_at_boundary]`, `test_decision_table[expired_after]`
- `expires_at` hỏng làm hàm raise -> `test_invalid_expiry_never_raises`

## coveredIds

- `CT-WF-004`
- `CT-WF-006`
- `INV-003`
- `INV-016`
- `TST-WF-INV-003`
- `TST-WF-INV-016`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`
- `YC-HT-G-10 (A-18 đổi sang GrantClaims do hội tụ)`

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, ExecutionGrant.
- Chỉ stdlib.
- Không gọi dịch vụ thật.
