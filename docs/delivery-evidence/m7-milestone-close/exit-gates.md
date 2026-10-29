# M7-MILESTONE-CLOSE-R6: đối chiếu exit gate Milestone M7 (revision 6)

Đối chiếu các exit gate của Milestone M7 theo tài liệu chuẩn `docs/11-roadmap.md` mục 13, phần `### Exit gate cho R5 Unattended Beta` và `### Exit gate cho R6 Operational Baseline` (dòng 578-595).

Cách đọc revision 6: Control đo toàn bộ 474 lệnh kiểm của milestone trên candidate sau worker_done; Worker không chạy bộ lệnh này nên các bảng dưới không công bố số lệnh đạt hay exit code. Cột bằng chứng chỉ nêu tệp test hoặc tài liệu liên quan nằm trong bộ lệnh kiểm; kết luận đạt hay không đạt của từng lệnh lấy từ bản đo của Control mà Reviewer (Sonnet 5.5) và Auditor rủi ro (Opus 5.5) đối chiếu.

| Mã gate | Nội dung theo roadmap | Trạng thái | Bằng chứng |
| --- | --- | --- | --- |
| M7-R5-EG1 | Batch chạy không giám sát trên workload đại diện với nhà cung cấp thật (CP7) | PENDING_USER_CHECKPOINT | Cần tài nguyên thật (Google Drive OAuth, GPU render, AI trả phí) và workload thật tại gói CP7; test giả lập/fixture không thay thế bằng chứng tài nguyên thật theo nguyên tắc D5. docs/implementation/cp7/plan.md dòng 44 gán M7-R5-EG1 cho RG-10; trong cây hiện chỉ có báo cáo cp7-1, cp7-2, cp7-3 (RG-01, RG-02) và cp7-real-resources, chưa có báo cáo RG-10. |
| M7-R5-EG2 | Một video/nguồn/provider lỗi không làm dừng việc độc lập | GHI CHÚ (rộng hơn kế hoạch đã duyệt) | Test liên quan nằm trong bộ lệnh kiểm do Control đo: tests/unit/orchestration/test_g_batch_outcome.py và tests/integration/creative/test_d15_provider_failure.py; kết quả theo bản đo của Control. |
| M7-R5-EG3 | Không job biến mất không trạng thái/log | GHI CHÚ (rộng hơn kế hoạch đã duyệt) | Test liên quan nằm trong bộ lệnh kiểm do Control đo: tests/unit/orchestration/test_g_consistency_audit.py và tests/unit/orchestration/test_g_recovery_scan.py; kết quả theo bản đo của Control. |
| M7-R5-EG4 | Resume, retry, reconcile và cleanup qua fault suite | GHI CHÚ (rộng hơn kế hoạch đã duyệt) | Test liên quan nằm trong bộ lệnh kiểm do Control đo: tests/unit/orchestration/test_g_retry_policy.py, tests/unit/storage/test_storage_reconciliation.py, tests/integration/storage/test_storage_cleanup_executor.py và tests/integration/convergence/test_cp5_completion_uow.py; kết quả theo bản đo của Control. |
| M7-R5-EG5 | Không P0/P1 mở và không hard-gate/INV test bị quarantine | GHI CHÚ (rộng hơn kế hoạch đã duyệt) | Kế hoạch đã duyệt không định nghĩa registry P0/P1. Bộ lệnh kiểm của milestone (474 lệnh) do Control đo trên candidate sau worker_done; Reviewer và Auditor rủi ro đối chiếu bản đo đó. Worker không tuyên bố số lệnh đạt hay việc không có test bị quarantine; mục này chốt theo bản đo của Control. |
| M7-R6 | Mọi exit gate R6 Operational Baseline: G01–G07, 100 video trong 12 giờ, ≥95% hoàn thành, ngưỡng hiệu năng và chất lượng, chi phí dưới 50 USD/tháng, runbook/rollback, user nghiệm thu (CP7) | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành thực tế tại gói CP7: chạy thử 100 video trong 12 giờ không giám sát trên máy mục tiêu, chạy mẫu 10 video và người dùng duyệt trên Dashboard. Bằng chứng giả lập nằm trong bộ lệnh kiểm do Control đo: tests/unit/config/test_j_incremental_cost.py, tests/unit/config/test_j_capacity_snapshot.py và probe tài liệu docs/runbook/runbook-v1.md; chỉ là bằng chứng giả lập, không thay bằng chứng tài nguyên thật. docs/implementation/cp7/plan.md dòng 45 gán M7-R6 cho RG-10 đến RG-13 và nghiệm thu của user. |

## Đối chiếu từng gạch đầu dòng của roadmap (docs/11-roadmap.md dòng 578-595)

### R5 Unattended Beta (dòng 580-584)

| Gạch đầu dòng roadmap | Mã exit gate | Trạng thái | Ghi chú / Dẫn chứng |
| --- | --- | --- | --- |
| Batch chạy không giám sát trên workload đại diện. | M7-R5-EG1 | PENDING_USER_CHECKPOINT | Cần tài nguyên thật và workload thật tại gói CP7 |
| Một video/nguồn/provider lỗi không làm dừng việc độc lập. | M7-R5-EG2 | GHI CHÚ | Rộng hơn kế hoạch đã duyệt; kiểm chứng bằng unit/integration test |
| Không job biến mất không trạng thái/log. | M7-R5-EG3 | GHI CHÚ | Rộng hơn kế hoạch đã duyệt; kiểm chứng bằng unit test audit/recovery |
| Resume, retry, reconcile và cleanup qua fault suite. | M7-R5-EG4 | GHI CHÚ | Rộng hơn kế hoạch đã duyệt; kiểm chứng bằng fault suite test |
| Không P0/P1 mở và không hard-gate/INV test bị quarantine. | M7-R5-EG5 | GHI CHÚ | Rộng hơn kế hoạch đã duyệt; chốt theo bản đo 474 lệnh của Control, Worker không công bố số liệu |

### R6 Operational Baseline (dòng 588-595)

| Gạch đầu dòng roadmap | Mã exit gate | Trạng thái | Ghi chú / Dẫn chứng |
| --- | --- | --- | --- |
| G01-G07 có evidence đạt hoặc gate không thuộc claim được ghi rõ và user chấp nhận phạm vi. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| Tối thiểu 100 video hợp lệ đã sync trong 12 giờ trên máy mục tiêu. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| Ít nhất 95% video đủ đầu vào hoàn thành không cần thao tác sau khi bắt đầu lô. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| UI p95, command ACK, resume và scheduler đạt ngưỡng đã duyệt trên workload đã khóa. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| Chất lượng topic/event/media/hook/safety đạt ngưỡng đã duyệt. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| Incremental cost dưới 50 USD/tháng theo phạm vi R20 và có cảnh báo 80%. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7; test giả lập tests/unit/config/test_j_incremental_cost.py nằm trong bộ lệnh kiểm của Control |
| Runbook, recovery, credential rotation, capacity, upgrade và rollback được kiểm thử. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7; docs/runbook/runbook-v1.md và tests/unit/config/test_j_capacity_snapshot.py nằm trong bộ lệnh kiểm của Control |
| User nghiệm thu baseline. | M7-R6 | PENDING_USER_CHECKPOINT | Người dùng trực tiếp nghiệm thu vận hành tại gói CP7 |

## Ghi chú theo quyết định của user (2026-10-22)

«Exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú trong báo cáo đóng mốc, không phải FAIL và không hỏi user. Việc kế hoạch đã duyệt có mà chưa nối do Control tự lập gói sửa.»

## Mục mở (không phải exit gate)

Căn cứ bảng open items tại `docs/11-roadmap.md` mục 23:
- `ROADMAP-OPEN-011`: Scale workload (dòng 775, hạn trước performance/scale claim). Đây là open decision item kỹ thuật, không phải exit gate và không đưa vào pendingUserCheckpoint.
- `ROADMAP-OPEN-010`: Retention/storage placement (dòng 774, hạn trước unattended cleanup). Đây là open decision item kỹ thuật, không phải exit gate và không đưa vào pendingUserCheckpoint.

## Ghi chú bổ sung revision 6

production_ports và các báo cáo pp-* (PP-1..PP-8), các gói PW-* (kể cả PW-D1-FIX1 mới ở revision 6), PW-E2E (dùng fixture, không thay bằng chứng tài nguyên thật nên M7-R5-EG1 vẫn chờ CP7) và RS-1..RS-13 đều nằm trong bộ lệnh kiểm do Control đo; Worker không dẫn số chuỗi hay kết quả của chúng. PW-D1-FIX1 (nhóm lỗi R14) chưa gọi lại AI thật; việc gọi AI thật thuộc slice CP7-4 theo docs/delivery-evidence/pw-d1-fix1/report.md mục 4, nên không đổi trạng thái M7-R5-EG1 và M7-R6. ADAPT-D-FIX1 (hàng mới sau khi lane rebase lên 32e335249dad5b390e05d7212b22e1718bb14d72) cũng nằm trong bộ lệnh kiểm do Control đo; Worker không dẫn kết quả của gói này và không đổi trạng thái hai gate trên. Kết luận tập pendingUserCheckpoint chỉ gồm đúng 2 gate: M7-R5-EG1 và M7-R6.
