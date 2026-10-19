# Báo cáo bằng chứng G-13

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe\n- Baseline HEAD: aa9fb870e8a8392dbce3c22dc7392695909f4f9\n- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-13.

## RED

- Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cacheprovider\n- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: Q failed, 54 passed in 0.94s\n- Chi tiết các dòng FAILED tiêu biểu:
  - FAILED tests/unit/orchestration/test_g_event_payloads.py::test_valid_event_has_every_required_envelope_field[BatchStarted]\n  - FAILED tests/unit/orchestration/test_g_event_payloads.py::test_envelope_constants_follow_d8_g_10[BatchStarted]\n  - FAILED tests/unit/orchestration/test_g_event_payloads.py::test_unknown_event_name_is_rejected[RenderCompleted]\n  - FAILED tests/unit/orchestration/test_g_event_payloads.py::test_forbidden_field_is_rejected[secret_value]\n  - FAILED tests/unit/orchestration/test_g_consistency_audit.py::test_batch_counter_differing_from_ledger_is_reported[0]\n  - FAILED tests/unit/orchestration/test_g_consistency_audit.py::test_active_reservation_for_missing_job_is_orphan\n  - FAILED tests/unit/orchestration/test_g_consistency_audit.py::test_running_stage_without_active_grant_is_reported[no_grant]\n  - FAILED tests/unit/orchestration/test_g_consistency_audit.py::test_job_without_valid_state_is_reported[None]\n- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection. 54 test kiểm tra hằng số, chữ ký, record dataclass, tính thuần và import đã PASS ngay từ đầu. Tất cả 121 test thất bại đều là AssertionError, KeyError trên payload rỗng hoặc DID NOT RAISE do khung hàm stub cố ý trả {} và () theo đúng thiết kế phản ví dụ.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cacheprovider\n- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: } passed in 0.21s\n
## Thay đổi

- 5 tệp thuộc owned paths:
  - src/controlplane/application/orchestration/event_payloads.py: Triển khai hàm pure application uild_g_event dựng dict DomainEvent envelope của G theo BINDING-DOMAIN-EVENT-ENVELOPE (CT-EVT-002, CT-EVT-003, TST-SEC-INV-012 phần G), nhận đúng 8 tên event của G, trả đủ 10 trường envelope chuẩn với producer \x27G\x27, schema_version \x271\x27, sensitivity \x27internal\x27, recovery_epoch dạng chuỗi token, aggregate_type theo bảng định sẵn; xác thực payload an toàn qua ensure_safe_event_payload, cấm các trường nhạy cảm (secret_value, aw_oauth_response, stack_trace, lob), kiểm tra cấu trúc khóa/giá trị payload và yêu cầu bắt buộc completion_id đối với VideoCompleted.
  - src/controlplane/domain/orchestration/consistency_audit.py: Triển khai hàm pure domain udit_consistency(snapshot) (R5 no-silent-failure; INV-010, INV-017, INV-018) chỉ đọc trên ConsistencySnapshot, phát hiện và báo cáo 6 mã finding bất thường: LEDGER_COUNT_MISMATCH, ORPHAN_ACTIVE_RESERVATION, LEDGER_WITHOUT_COMPLETED_JOB, WAITING_JOB_WITHOUT_REASON, RUNNING_STAGE_WITHOUT_ACTIVE_GRANT, JOB_WITHOUT_STATE_OR_LOG; kết quả sắp xếp ổn định theo (code, ref), rỗng khi snapshot nhất quán.
  - 	ests/unit/orchestration/test_g_event_payloads.py: Bộ kiểm thử đơn vị toàn diện gồm 90 test cases cho uild_g_event, kiểm tra đầy đủ 10 trường envelope, 8 tên event hợp lệ, hằng số producer/schema/sensitivity, tính tất định không đột biến input, chuyển đổi tuple thành list, từ chối tên lạ, epoch int/trắng, aggregate_id không hợp lệ, payload không phải mapping, trường cấm, canary secret token, stack trace, khóa không phải ID/revision, giá trị không hợp lệ, ràng buộc completion_id của VideoCompleted, chữ ký 5 tham số và tính thuần module (chỉ import read-only ensure_safe_event_payload).
  - 	ests/unit/orchestration/test_g_consistency_audit.py: Bộ kiểm thử đơn vị toàn diện gồm 85 test cases cho udit_consistency, kiểm tra danh sách 6 mã finding chuẩn, snapshot nhất quán trả tuple rỗng, phát hiện từng mã vi phạm (batch đếm lệch ledger, reservation mồ côi khi job vắng hoặc terminal, ledger cho job chưa hoàn thành, job waiting thiếu reason, stage running không có active grant, job thiếu state hoặc logs, job biến mất trong batch), thứ tự sắp xếp ổn định (code, ref), tính độc lập thứ tự input, gọi hai lần bằng nhau không đổi snapshot, tính bất biến frozen của record/snapshot và tính thuần domain (không I/O, không đồng hồ).
  - docs/delivery-evidence/g-13/report.md: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds, pendingUserCheckpoint và giới hạn kỹ thuật.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cacheprovider | 0 | } passed in 0.21s |
| 2 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định D8

1. event_id được sinh tất định theo công thức \x27{event_name}:{aggregate_id}:{aggregate_revision}\x27 vì chữ ký uild_g_event không nhận tham số event_id.
2. ggregate_type: Ánh xạ Batch cho BatchStarted, BatchTargetReached, BatchExhausted; VideoJob cho JobAllocated, JobWaiting, JobFailed, VideoCompleted; StageRun cho StageStateChanged (GIẢ ĐỊNH, do contract chưa nêu chi tiết).
3. Khóa payload chỉ cho phép dạng *_id, *_ids, *_revision, *_revisions; giá trị là số nguyên không âm hoặc chuỗi một token (không khoảng trắng) độ dài tối đa 256 ký tự (hoặc danh sách các giá trị này).
4. ggregate_revision cho phép từ 0 (số nguyên không âm).
5. Hình dạng ConsistencySnapshot do G-13 định nghĩa gồm 6 bảng record (atches, jobs, eservations, ledgers, stage_runs, grants) (GIẢ ĐỊNH, nguồn dữ liệu snapshot thật nối ở hội tụ/G-14).
6. ORPHAN_ACTIVE_RESERVATION được kích hoạt khi reservation ở trạng thái ACTIVE nhưng job tương ứng không tồn tại trong snapshot hoặc job đang ở trạng thái terminal (COMPLETED, FAILED_FINAL).
7. JOB_WITHOUT_STATE_OR_LOG được kích hoạt khi job được liệt kê trong BatchRecord.job_ids nhưng vắng mặt trong danh sách jobs, hoặc state của job không hợp lệ / None, hoặc job không có bất kỳ log_refs nào.

## Ánh xạ phản ví dụ

- Event mang secret hoặc stack trace: Được loại trừ bởi test 	est_forbidden_field_is_rejected và 	est_canary_secret_or_stack_trace_value_is_rejected trong 	ests/unit/orchestration/test_g_event_payloads.py.
- Epoch dạng int lọt ra envelope: Được loại trừ bởi test 	est_int_or_blank_recovery_epoch_never_reaches_the_envelope trong 	ests/unit/orchestration/test_g_event_payloads.py.
- Job biến mất không trạng thái không bị báo: Được loại trừ bởi test 	est_job_vanished_from_jobs_but_listed_in_batch_is_reported trong 	ests/unit/orchestration/test_g_consistency_audit.py.
- Bộ đếm batch lệch ledger không bị báo: Được loại trừ bởi test 	est_batch_counter_differing_from_ledger_is_reported trong 	ests/unit/orchestration/test_g_consistency_audit.py.

## coveredIds

- CT-EVT-002
- CT-EVT-003
- TST-SEC-INV-012 (phần G)
- R5

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: Phê duyệt thư viện cố định và cách dựng lại runtime.
- CP7 tài nguyên thật (D5): Phê duyệt dịch vụ thật và tài khoản bên ngoài.
- YC-HT-G-07: Đăng ký 8 event của G vào outbox (thuộc gói hội tụ).

## Giới hạn

- Không chạy full test suite, chỉ chạy các test mục tiêu của G-13.
- Chỉ dùng thư viện chuẩn Python (stdlib) và gói nội bộ controlplane.domain.
- Helper ensure_safe_event_payload từ P3 có phạm vi kiểm tra đặc thù nên các giá trị token đơn không chứa dấu \x27=\x27 hoặc \x27:\x27 (như \x27canary-secret-token\x27) không bị coi là unsafe secret (ghi nhận theo hành vi hiện có của helper, không tự ý sửa helper ngoài phạm vi).
- Hàm thuần domain và application, không thực hiện I/O, không gọi đồng hồ hệ thống và không ghi dữ liệu ra ngoài.
