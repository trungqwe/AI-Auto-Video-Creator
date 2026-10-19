# Báo cáo bằng chứng G-14

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline HEAD: 1aa9fb870e8a8392dbce3c22dc7392695909f4f9
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-14

## RED

- test_g_batch_outcome.py:
  - Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_batch_outcome.py -q -p no:cacheprovider
  - Exit code thực tế: 1
  - Dòng tóm tắt nguyên văn: 77 failed, 14 passed in 0.40s
  - Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. Tất cả thất bại đều là AssertionError hoặc DID NOT RAISE khi chạy đối chiếu khung ban đầu.

- test_g_recovery_scan.py:
  - Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_recovery_scan.py -q -p no:cacheprovider
  - Exit code thực tế: 1
  - Dòng tóm tắt nguyên văn: 16 failed, 7 passed in 0.28s
  - Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. Tất cả thất bại đều là AssertionError, IndexError (tuple rỗng) hoặc DID NOT RAISE.

- test_g_app_session.py:
  - Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_app_session.py -q -p no:cacheprovider
  - Exit code thực tế: 1
  - Dòng tóm tắt nguyên văn: 39 failed, 4 passed in 0.34s
  - Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. Tất cả thất bại đều là AssertionError hoặc DID NOT RAISE.

## GREEN

- test_g_batch_outcome.py (Bước 6):
  - Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_batch_outcome.py -q -p no:cacheprovider
  - Exit code thực tế: 0
  - Dòng tóm tắt nguyên văn: 91 passed in 0.13s

- test_g_recovery_scan.py (Bước 13):
  - Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_recovery_scan.py -q -p no:cacheprovider
  - Exit code thực tế: 0
  - Dòng tóm tắt nguyên văn: 23 passed in 0.08s

- test_g_app_session.py (Bước 19):
  - Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_app_session.py -q -p no:cacheprovider
  - Exit code thực tế: 0
  - Dòng tóm tắt nguyên văn: 43 passed in 0.09s

## Thay đổi

- 7 tệp thuộc owned paths:
  - src/controlplane/domain/orchestration/batch_outcome.py: Định nghĩa BatchOutcome enum 5 giá trị, hàm thuần decide_batch_outcome phân định trạng thái dừng/tiếp tục của batch (CT-ORC-010) và plan_batch_transition chuyển đổi trạng thái batch an toàn qua transition_batch.
  - src/controlplane/domain/orchestration/recovery_scan.py: Định nghĩa ResumeKind 6 giá trị, ResumeAction, GrantView, PendingResult, ResumeSnapshot và hàm thuần plan_resume lập kế hoạch tái tục sau khởi động lại với cơ chế quarantine epoch cũ (INV-016), grant validation và bảo đảm không chạy lại stage SUCCEEDED.
  - src/controlplane/domain/orchestration/app_session.py: Định nghĩa AppSession bất biến và log_ref (CT-ORC-011, TST-E2E-013), JobCheckpoint, SessionCheckpoint, OutputFolderIntent, cùng các hàm thuần close_session, resume_session và make_log_ref kèm mã lỗi định danh chi tiết.
  - tests/unit/orchestration/test_g_batch_outcome.py: 91 test cases kiểm tra toàn diện 5 kết quả BatchOutcome, xác thực tham số số, quy tắc EXHAUSTED khi hết việc/reservation, cách ly lỗi job cá lẻ và chuyển đổi trạng thái statemachine.
  - tests/unit/orchestration/test_g_recovery_scan.py: 23 test cases kiểm tra kế hoạch resume, cách ly kết quả epoch cũ, grant hết hạn/lệch epoch, khôi phục stage chờ capability và tính bất biến thuần tuý.
  - tests/unit/orchestration/test_g_app_session.py: 43 test cases kiểm tra tính bất biến AppSession, chỉ sinh OutputFolderIntent khi có video, bảo lưu checkpoint khi resume, bắt buộc đủ 4 thành phần log_ref và AST import thuần stdlib.
  - docs/delivery-evidence/g-14/report.md: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds và pendingUserCheckpoint.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | git diff --check | 0 | PASS (không output, không trailing whitespace) |
| 2 | python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orchestration/test_g_batch_outcome.py tests/unit/orchestration/test_g_app_session.py -q -p no:cacheprovider | 0 | 157 passed in 0.20s |

## Quyết định mặc định (D8)

1. ResumeAction là dataclass frozen (kind, stage_run_id, job_id, result_id) vì cần chỉ rõ stage/result; ResumeKind là enum sáu giá trị.
2. Quarantine chỉ so epoch, generation trùng không cứu epoch cũ (INV-016).
3. RUNNING + grant epoch cũ => REISSUE_GRANT_NEW_EPOCH, RUNNING + grant hết hạn hoặc thiếu => RECONCILE_OUTCOME_UNKNOWN (fail-closed, không chạy lại mù).
4. FAILED_RETRYABLE/STALE => CREATE_NEW_ATTEMPT khi dependency xong và capability cho phép, ngân sách retry/backoff thuộc G-11.
5. allocation_cursor chỉ được kiểm tra hợp lệ, không action nào quay về candidate đầu.
6. capability_blocked_work là số job/candidate đang bị chặn capability; chỉ khi không còn candidate eligible mới WAITING_CAPABILITY; system_fault thắng ledger target (fail-closed).
7. plan_batch_transition là đường chuyển qua transition_batch, chỉ nhận RUNNING/WAITING_CAPABILITY.
8. close_session nhận thêm ended_at keyword-only vì domain không có đồng hồ; OutputFolderIntent chỉ tồn tại khi count > 0 và session đã đóng; tên thư mục thuộc storage allocator của I.

## Ánh xạ phản ví dụ

- Resume chạy lại từ đầu / stage SUCCEEDED bị chạy lại: Loại trừ bởi test_succeeded_and_failed_final_are_never_rerun và test_online_again_resumes_only_waiting_stage trong test_g_recovery_scan.py.
- Batch kết thúc EXHAUSTED khi còn job chờ: Loại trừ bởi test_waiting_job_holding_reservation_is_never_exhausted và test_blocked_work_is_never_exhausted trong test_g_batch_outcome.py.
- Một job lỗi làm batch FAILED_SYSTEM: Loại trừ bởi test_single_failed_final_job_keeps_batch_running và test_failed_system_only_with_fault_flag_and_exact_exhausted_rule trong test_g_batch_outcome.py.
- Session rỗng tạo output folder: Loại trừ bởi test_empty_session_has_no_output_folder_intent và test_intent_requires_video_and_closed_session trong test_g_app_session.py.

## coveredIds

- CT-ORC-010
- CT-ORC-011
- CT-WF-004
- CT-WF-006
- TST-WF-INV-016
- TST-E2E-007
- TST-E2E-008
- TST-E2E-013

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Chỉ dùng thư viện chuẩn Python (stdlib) và các gói domain nội bộ controlplane.domain.
- Thời gian 5 phút resume chỉ đo ở CP7-G-02; slice này chỉ xử lý thuần giải thuật và domain logic.
- Không gọi dịch vụ thật; không đọc thông tin bảo mật hay credentials.
