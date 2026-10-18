# Errata M7-Integration

> Nguồn đính chính hiện hành do CP1-CONTRACT-BINDING lập ngày 18/10/2026. Tệp kế hoạch cũ giữ nguyên; khi mâu thuẫn, nguồn chuẩn dưới đây thắng.

## Nguồn chuẩn

- docs/09-contracts/12-state-machines.md
- docs/09-contracts/02-domain-events.md
- docs/09-contracts/03-workflow-and-execution.md
- docs/09-contracts/09-orchestration-contracts.md
- docs/09-contracts/11-configuration-security-contracts.md
- docs/10-test-strategy.md (bảng invariant dòng 526–545, E2E dòng 549–603, nhóm AUD2 dòng 1184–1199)
- docs/parallel-delivery/ownership-and-locks.yaml
- D1/D3/D4 trong AGENTS.md, HANDOFF.md, docs/parallel-delivery/overlay-and-evidence.md dòng 67
- Binding liên quan: docs/parallel-delivery/bindings/g-activity-execution.json, docs/parallel-delivery/bindings/g-c-i-completion.json, docs/parallel-delivery/bindings/domain-event-envelope.json, docs/parallel-delivery/bindings/j-provider-route.json

## Bảng đính chính

| # | Vị trí | Loại lỗi | Nội dung sai | Nguồn chuẩn thay thế |
| --- | --- | --- | --- | --- |
| 1 | M7-integration-execution-package.md:102-120 | CAY_THU_MUC_TRUNG | src/orchestration/**, src/control_api, src/ui/**, src/storage/** | D1 và ownership-and-locks.yaml: G ở src/controlplane/{domain,application,infrastructure/db}/orchestration/** (dòng 167–177); H ở src/controlplane/ui/** (178–185); I ở storage_meta (186–196); J ở config/security (197–205). Một import root src/, không dùng tiền tố 'src.'. |
| 2 | M7-integration-test-plan.md:132-180 | MAU_BANG_CHUNG_DIEN_SAN | manifest mẫu điền sẵn 24/24 passed, INV-001..020 'VERIFIED_*', G01–G07 PASS, 102 video/12h, 0.961, 42.50 USD, timestamp 2026-10-09 | Mẫu này không phải bằng chứng và không được trích làm kết quả. Bằng chứng thật theo D4 (report.md có lệnh, exit code, output). Gate tài nguyên thật (Drive, GPU, 12 giờ, AI trả phí) thuộc CP7 sau khi user duyệt D5. AGENTS.md: không tuyên bố PASS khi thiếu evidence; không dùng mock cho external gate. |
| 3 | M7-integration-test-plan.md:28 | INVARIANT_SAI | TST-INT-BAT-001 gán INV-010 cho phân bổ 1–3 video | INV-010 là completion lặp chỉ tăng ledger/count một lần (docs/10-test-strategy.md dòng 535); 1–3 video khác góc kể là INV-013 (dòng 538); trần target là INV-018. |
| 4 | M7-integration-test-plan.md:37 | INVARIANT_SAI, STATE_MACHINE_TU_DAT | TST-INT-REC-001 gán INV-003 cho desktop mất mạng; trạng thái viết thường 'waiting_capability' | INV-003 là result của generation cũ thành stale (dòng 528); mất capability theo docs/09-contracts/03-workflow-and-execution.md CT-WF-007, CT-STATE-010 RUNNING→WAITING_CAPABILITY→RUNNING (batch) và CT-STATE-008 WAITING_CAPABILITY (stage). |
| 5 | M7-integration-test-plan.md:45 | STATE_MACHINE_TU_DAT | trạng thái job 'qc_passed', 'completed', 'cloud_verified' | CT-STATE-009: READY_FOR_COMPLETION (render/QC đạt, chưa sync) → COMPLETED chỉ qua CT-ORC-008 có cloud_location_verification_ref; VERIFIED là trạng thái location theo CT-STATE-012. |
| 6 | M7-integration-test-plan.md:27-74 | TEST_ID_NGOAI_CATALOG | TST-INT-E2E/BAT/VAR/FLT/RPL/REC/FNC/IDM/DRV/CLN/MED/RST/SEC/SAN/SSE/CTL/OBS/CST/CAP/BMK/AUT-* | catalog: TST-E2E-001..014 (dòng 549–603), TST-CTR-INV-001/002, TST-WF-INV-003/010/016/017/018, TST-DR-INV-011, TST-SEC-INV-012/020, TST-E2E-INV-009, TST-WF-VAR-001..004. |

## Quy tắc dùng

Test ID mới phải vào catalog docs/10-test-strategy.md qua slice sở hữu tài liệu đó trước khi dùng làm oracle; bằng chứng ghi vào docs/delivery-evidence/<task-id viết thường>/report.md.
