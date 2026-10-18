# Errata M4-CI

> Nguồn đính chính hiện hành do CP1-CONTRACT-BINDING lập ngày 18/10/2026. Tệp kế hoạch cũ giữ nguyên; khi mâu thuẫn, nguồn chuẩn dưới đây thắng.

## Nguồn chuẩn

- docs/09-contracts/12-state-machines.md
- docs/09-contracts/04-source-content-contracts.md
- docs/09-contracts/05-content-media-contracts.md
- docs/09-contracts/10-storage-contracts.md
- docs/10-test-strategy.md (bảng invariant dòng 526–545, E2E dòng 549–603, nhóm AUD2 dòng 1184–1199)
- docs/parallel-delivery/ownership-and-locks.yaml
- D1/D3/D4 trong AGENTS.md, HANDOFF.md, docs/parallel-delivery/overlay-and-evidence.md dòng 67
- Binding liên quan: docs/parallel-delivery/bindings/c-d-media-candidates.json, docs/parallel-delivery/bindings/i-artifact-version.json

## Bảng đính chính

| # | Vị trí | Loại lỗi | Nội dung sai | Nguồn chuẩn thay thế |
| --- | --- | --- | --- | --- |
| 1 | M4-CI-execution-package.md:109-121 | CAY_THU_MUC_TRUNG | cây src/storage/** (domain/application/ports/adapters/infrastructure) | D1 và ownership-and-locks.yaml dòng 186–196: I mở rộng src/controlplane/domain/storage_meta/**, application/storage_meta/**, infrastructure/db/storage_meta/**, infrastructure/storage/**; không dựng src/storage. |
| 2 | M4-CI-execution-package.md:77,148,187 | NGUON_QUYEN_CU | PATH-SRC-STORAGE và LOCK-SRC-STORAGE ghi là chưa đăng ký; gate GATE-M4-I-OWNERSHIP-LOCK | đã đăng ký ở dòng 186–196 (CP0-GOVERNANCE); quyền theo D3. |
| 3 | M4-CI-test-plan.md:125 | DUONG_DAN_BANG_CHUNG_CAM | docs/milestones/m4-media/evidence/m4-ci/ | D4: docs/delivery-evidence/<task-id>/report.md. |
| 4 | M4-CI-test-plan.md:33-64 | TEST_ID_NGOAI_CATALOG | TST-STO-SYNC-001..008, TST-CAT-MED-001/002, TST-CAT-HOOK-001/002, TST-CAT-USG-001, TST-CAT-QRY-001, TST-CAT-SUP-001, TST-MED-SFT-001/002, TST-MED-PRB-001 | catalog docs/10-test-strategy.md: TST-MEDIA-INV-007, TST-INT-INV-008, TST-E2E-INV-009, TST-DR-INV-011, TST-SEC-INV-012, TST-E2E-001..014. |
| 5 | M4-CI-test-plan.md:49 | INVARIANT_SAI | TST-CAT-MED-002 gán INV-015 cho 'media lịch sử vẫn dùng được khi nguồn DISABLED/REMOVED' | INV-015 là remove rồi auto-discovery cùng URL thì vẫn tombstone (10-test-strategy.md dòng 540); hành vi media lịch sử thuộc docs/09-contracts/04-source-content-contracts.md CT-SRC-003. |
| 6 | M4-CI-contract-freeze.md:200-203 | STATE_MACHINE_TU_DAT | CT-STATE-012 bỏ cạnh VERIFIED → MISSING và hàm ý có cạnh phục hồi từ MISSING/CORRUPT 'khi verify lại' | 12-state-machines.md CT-STATE-012: có VERIFIED → MISSING; không có recovery edge từ MISSING, CORRUPT, OUTCOME_UNKNOWN; cũng không có cleanup shortcut. |

## Quy tắc dùng

Test ID mới phải vào catalog docs/10-test-strategy.md qua slice sở hữu tài liệu đó trước khi dùng làm oracle; bằng chứng ghi vào docs/delivery-evidence/<task-id viết thường>/report.md.
