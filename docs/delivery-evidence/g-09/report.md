# Báo cáo bằng chứng G-09

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline HEAD: 9dd3efea87d4172a55ae0bdd8e8b8f93025dc57c
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-09.

## RED

- Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 79 failed, 7 passed in 0.53s
- Chi tiết các dòng FAILED tiêu biểu:
  - FAILED tests/unit/orchestration/test_g_completion_gate.py::test_invalid_fixture_payload_is_invalid_request[missing_cloud_location_verification_ref]
  - FAILED tests/unit/orchestration/test_g_completion_gate.py::test_ledger_with_different_input_is_conflict[video_job_id]
  - FAILED tests/unit/orchestration/test_g_completion_gate.py::test_job_not_ready_state_is_rejected[ACTIVE]
  - FAILED tests/unit/orchestration/test_g_completion_gate.py::test_blank_cloud_verification_ref_is_missing[]
  - FAILED tests/unit/orchestration/test_g_completion_gate.py::test_registry_revision_mismatch_is_stale_and_keeps_waiting[11]
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 7 test hợp lệ (kiểm tra ca valid fixture request proceed, trường so sánh ledger, tính bất biến input, frozen decision, chữ ký hàm không có cổng ghi, 5 enum GateAction, và tính thuần import) đã PASS ngay từ đầu. Tất cả 79 test thất bại đều là AssertionError hoặc DID NOT RAISE do khung check_completion ban đầu trả PROCEED vô điều kiện theo đúng thiết kế phản ví dụ.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 86 passed in 0.10s

## Thay đổi

- 3 tệp thuộc owned paths:
  - src/controlplane/domain/orchestration/completion_gate.py: Triển khai cổng thuần domain check_completion (CT-ORC-008 bước 1–2, CT-ORC-012, INV-010) thực thi kiểm tra theo thứ tự bất biến: payload lỗi -> INVALID_REQUEST; ledger cùng input -> ALREADY_COMPLETED (trả ledger cũ), khác/thiếu input -> CONFLICT; job state khác READY_FOR_COMPLETION -> JOB_NOT_READY; fencing không accepted -> mã fencing; cloud_location_verification_ref rỗng/trắng -> CLOUD_VERIFICATION_MISSING; reservation không ACTIVE hoặc sai job/reservation_id/hash -> RESERVATION_INVALID; revision khác expected -> VARIANT_REGISTRY_STALE (action KEEP_WAITING); trùng thực xác nhận -> VARIANT_CONFLICT_FINAL (action FAIL_JOB_RELEASE); chỉ khi đủ mọi điều kiện mới trả PROCEED. Định nghĩa GateAction, GateDecision, ReservationBinding, LEDGER_COMPARED_FIELDS.
  - 	ests/unit/orchestration/test_g_completion_gate.py: Bộ kiểm thử đơn vị toàn diện gồm 86 test cases bao gồm kiểm tra fixture invalid payloads, non-mapping request, idempotency ledger (9 trường so sánh), từ chối job state ngoài READY_FOR_COMPLETION, kiểm tra mã fencing, cloud location verification, tính hợp lệ của reservation binding, variant registry revision mismatch / stale, confirmed conflict, bất biến input và tính thuần ranh giới domain.
  - docs/delivery-evidence/g-09/report.md: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds và pendingUserCheckpoint.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider | 0 | 86 passed in 0.10s |
| 2 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Thứ tự kiểm cố định theo CT-ORC-008: payload -> existing ledger -> job state -> fencing -> cloud location verification -> reservation -> variant registry revision -> confirmed conflict -> PROCEED.
2. Thiếu khóa cloud_location_verification_ref là INVALID_REQUEST theo thứ tự bước 1 (bắt bởi validate_commit_request), còn chuỗi rỗng/trắng là CLOUD_VERIFICATION_MISSING.
3. 'Cùng input' của ledger là bằng nhau trên 9 trường chung LEDGER_COMPARED_FIELDS, trường thiếu hoặc lệch là CONFLICT.
4. ReservationBinding(reservation_id, job_id, output_sha256, state) do G-09 định nghĩa cục bộ vì VariantReservation P6 không có hash output, RESERVATION_INVALID khi không ACTIVE hoặc sai job_id/reservation_id/output_sha256.
5. 'Trùng thực' nhận qua tham số keyword-only ariant_conflict_confirmed (kết quả đối chiếu D ở revision mới nhất), stale thắng conflict.
6. Action mapping: stale là KEEP_WAITING, conflict thực là FAIL_JOB_RELEASE, ALREADY_COMPLETED là RETURN_EXISTING_LEDGER, còn lại là REJECT.
7. job_state ngoài JobState hoặc None là JOB_NOT_READY (fail-closed).

## Ánh xạ phản ví dụ

- Job ACTIVE được hoàn thành thẳng -> Được loại trừ bởi test 	est_active_job_is_never_completed_directly và 	est_job_not_ready_state_is_rejected.
- Completion không có cloud verification -> Được loại trừ bởi test 	est_qc_passed_but_not_cloud_verified_never_proceeds và 	est_blank_cloud_verification_ref_is_missing.
- Revision stale vẫn ghi ledger -> Được loại trừ bởi test 	est_registry_revision_mismatch_is_stale_and_keeps_waiting và 	est_stale_registry_never_proceeds_even_with_confirmed_conflict.
- Completion lặp tạo ledger thứ hai -> Được loại trừ bởi test 	est_repeated_completion_never_proceeds_or_creates_second_ledger và 	est_same_input_ledger_returns_existing_ledger.

## coveredIds

- CT-ORC-008
- CT-ORC-012
- INV-010
- TST-E2E-INV-009 (phần G)

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Chỉ dùng thư viện chuẩn Python (stdlib) và gói domain nội bộ controlplane.domain.
- Không có cổng ghi, I/O, đồng hồ; không thực hiện ghi ledger/job/reservation (việc ghi do G-10 phụ trách).
- Không gọi dịch vụ thật; không đọc thông tin bảo mật hay credentials.
