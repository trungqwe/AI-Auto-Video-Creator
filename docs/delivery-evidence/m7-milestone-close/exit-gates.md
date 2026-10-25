# M7-MILESTONE-CLOSE-R2: đối chiếu exit gate Milestone M7 (revision 2)

Đối chiếu các exit gate của Milestone M7 theo tài liệu chuẩn `docs/11-roadmap.md` mục 13, phần `### Exit gate cho R5 Unattended Beta` và `### Exit gate cho R6 Operational Baseline` (dòng 578-595).

| Mã gate | Nội dung theo roadmap | Trạng thái | Bằng chứng |
| --- | --- | --- | --- |
| M7-R5-EG1 | Batch chạy không giám sát trên workload đại diện với nhà cung cấp thật (CP7) | PENDING_USER_CHECKPOINT | Cần tài nguyên thật (Google Drive OAuth, GPU render, AI trả phí) và workload thật tại gói CP7; test giả lập/fixture không thay thế bằng chứng tài nguyên thật theo nguyên tắc D5. |
| M7-R5-EG2 | Một video/nguồn/provider lỗi không làm dừng việc độc lập | GHI CHÚ (rộng hơn kế hoạch đã duyệt) | Đã kiểm chứng qua các test đạt exit 0: `tests/unit/orchestration/test_g_batch_outcome.py` (Chuỗi 14, thứ tự 36: `test_outcome_has_exactly_five_values`, `test_target_reached_by_ledger_count`, `test_exhausted_only_when_no_candidate_and_no_active_reservation`) và `tests/integration/creative/test_d15_provider_failure.py` (Chuỗi 13, thứ tự 15: `test_failure_kinds_become_redacted_problems_with_recorded_attempt`). |
| M7-R5-EG3 | Không job biến mất không trạng thái/log | GHI CHÚ (rộng hơn kế hoạch đã duyệt) | Đã kiểm chứng qua các test đạt exit 0: `tests/unit/orchestration/test_g_consistency_audit.py` (Chuỗi 14, thứ tự 34: `test_finding_codes_are_the_six_spec_codes_in_order`, `test_consistent_snapshot_returns_empty_tuple`, `test_batch_counter_differing_from_ledger_is_reported`) và `tests/unit/orchestration/test_g_recovery_scan.py` (Chuỗi 14, thứ tự 35: `test_resume_kind_has_exactly_six_values`, `test_succeeded_and_failed_final_are_never_rerun`, `test_online_again_resumes_only_waiting_stage`). |
| M7-R5-EG4 | Resume, retry, reconcile và cleanup qua fault suite | GHI CHÚ (rộng hơn kế hoạch đã duyệt) | Đã kiểm chứng qua các test đạt exit 0: `tests/unit/orchestration/test_g_retry_policy.py` (Chuỗi 14, thứ tự 31: `test_delay_sequence_is_exponential_and_capped`, `test_delay_is_deterministic`), `tests/unit/storage/test_storage_reconciliation.py` (Chuỗi 15, thứ tự 25: `test_consistent_snapshot_returns_empty_tuple`, `test_cloud_object_missing`, `test_hash_mismatch`), `tests/integration/storage/test_storage_cleanup_executor.py` (Chuỗi 15, thứ tự 24: `test_valid_authorization_deletes_only_target`, `test_unauthorized_deletion_keeps_file`, `test_path_outside_staging_is_rejected`), và `tests/integration/convergence/test_cp5_completion_uow.py` (Chuỗi 5, thứ tự 12: `test_commit_is_one_transaction_on_one_connection`, `test_failure_at_any_point_rolls_back_everything`). |
| M7-R5-EG5 | Không P0/P1 mở và không hard-gate/INV test bị quarantine | GHI CHÚ (rộng hơn kế hoạch đã duyệt) | Kế hoạch đã duyệt không định nghĩa registry P0/P1; toàn bộ 309 lệnh kiểm bắt buộc và các invariant/boundary test của milestone đều chạy đạt exit 0 trên candidate, không có test nào bị quarantine hay bỏ qua trái phép. |
| M7-R6 | Mọi exit gate R6 Operational Baseline: G01–G07, 100 video trong 12 giờ, ≥95% hoàn thành, ngưỡng hiệu năng và chất lượng, chi phí dưới 50 USD/tháng, runbook/rollback, user nghiệm thu (CP7) | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành thực tế tại gói CP7: chạy thử 100 video trong 12 giờ không giám sát trên máy mục tiêu, chạy mẫu 10 video và người dùng duyệt trên Dashboard. Bằng chứng giả lập đã đạt exit 0: `tests/unit/config/test_j_incremental_cost.py` (Chuỗi 15, thứ tự 36: kiểm soát chi phí < 50 USD/tháng và cảnh báo 80%), `tests/unit/config/test_j_capacity_snapshot.py` (Chuỗi 15, thứ tự 35: snapshot năng lực và tài nguyên), và `docs/runbook/runbook-v1.md` (bao phủ 6 quy trình vận hành và rollback). |

## Đối chiếu từng gạch đầu dòng của roadmap (docs/11-roadmap.md dòng 578-595)

### R5 Unattended Beta (dòng 580-584)

| Gạch đầu dòng roadmap | Mã exit gate | Trạng thái | Ghi chú / Dẫn chứng |
| --- | --- | --- | --- |
| Batch chạy không giám sát trên workload đại diện. | M7-R5-EG1 | PENDING_USER_CHECKPOINT | Cần tài nguyên thật và workload thật tại gói CP7 |
| Một video/nguồn/provider lỗi không làm dừng việc độc lập. | M7-R5-EG2 | GHI CHÚ | Rộng hơn kế hoạch đã duyệt; đã kiểm chứng bằng unit/integration test đạt exit 0 |
| Không job biến mất không trạng thái/log. | M7-R5-EG3 | GHI CHÚ | Rộng hơn kế hoạch đã duyệt; đã kiểm chứng bằng unit test audit/recovery đạt exit 0 |
| Resume, retry, reconcile và cleanup qua fault suite. | M7-R5-EG4 | GHI CHÚ | Rộng hơn kế hoạch đã duyệt; đã kiểm chứng bằng fault suite test đạt exit 0 |
| Không P0/P1 mở và không hard-gate/INV test bị quarantine. | M7-R5-EG5 | GHI CHÚ | Rộng hơn kế hoạch đã duyệt; 309 lệnh kiểm bắt buộc đều đạt exit 0 |

### R6 Operational Baseline (dòng 588-595)

| Gạch đầu dòng roadmap | Mã exit gate | Trạng thái | Ghi chú / Dẫn chứng |
| --- | --- | --- | --- |
| G01-G07 có evidence đạt hoặc gate không thuộc claim được ghi rõ và user chấp nhận phạm vi. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| Tối thiểu 100 video hợp lệ đã sync trong 12 giờ trên máy mục tiêu. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| Ít nhất 95% video đủ đầu vào hoàn thành không cần thao tác sau khi bắt đầu lô. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| UI p95, command ACK, resume và scheduler đạt ngưỡng đã duyệt trên workload đã khóa. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| Chất lượng topic/event/media/hook/safety đạt ngưỡng đã duyệt. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7 |
| Incremental cost dưới 50 USD/tháng theo phạm vi R20 và có cảnh báo 80%. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7; test giả lập test_j_incremental_cost đạt exit 0 |
| Runbook, recovery, credential rotation, capacity, upgrade và rollback được kiểm thử. | M7-R6 | PENDING_USER_CHECKPOINT | Thuộc phạm vi nghiệm thu vận hành CP7; runbook-v1.md và test năng lực đạt exit 0 |
| User nghiệm thu baseline. | M7-R6 | PENDING_USER_CHECKPOINT | Người dùng trực tiếp nghiệm thu vận hành tại gói CP7 |

## Ghi chú theo quyết định của user (2026-10-22)

«Exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú trong báo cáo đóng mốc, không phải FAIL và không hỏi user. Việc kế hoạch đã duyệt có mà chưa nối do Control tự lập gói sửa.»

## Mục mở (không phải exit gate)

Căn cứ bảng open items tại `docs/11-roadmap.md` mục 23:
- `ROADMAP-OPEN-011`: Scale workload (dòng 775, hạn trước performance/scale claim). Đây là open decision item kỹ thuật, không phải exit gate và không đưa vào pendingUserCheckpoint.
- `ROADMAP-OPEN-010`: Retention/storage placement (dòng 774, hạn trước unattended cleanup). Đây là open decision item kỹ thuật, không phải exit gate và không đưa vào pendingUserCheckpoint.

## Ghi chú bổ sung revision 2

Gói `IMPL-PLAN-PROD-PORTS` chỉ lập kế hoạch (`docs/implementation/prod-ports/plan.md` và `slices.md`, slice `PP-1` đến `PP-8`). Thư mục `src/controlplane/infrastructure/production_ports/` và `docs/delivery-evidence/pp-*/` chưa tồn tại, nên sáu cổng ProductionRuntime và Drive placement chưa nối; theo quyết định của user (2026-10-22) đây chỉ là ghi chú, không phải FAIL, không hỏi user, và Control tự lập gói nối; việc này không làm đổi tập pendingUserCheckpoint (vẫn chỉ M7-R5-EG1 và M7-R6).
