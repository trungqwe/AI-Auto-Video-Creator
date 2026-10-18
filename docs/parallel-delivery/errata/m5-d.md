# Errata M5-D

> Nguồn đính chính hiện hành do CP1-CONTRACT-BINDING lập ngày 18/10/2026. Tệp kế hoạch cũ giữ nguyên; khi mâu thuẫn, nguồn chuẩn dưới đây thắng.

## Nguồn chuẩn

- docs/09-contracts/12-state-machines.md
- docs/09-contracts/05-content-media-contracts.md
- docs/09-contracts/06-creative-ai-contracts.md
- docs/09-contracts/08-render-quality-contracts.md
- docs/09-contracts/11-configuration-security-contracts.md
- docs/10-test-strategy.md (bảng invariant dòng 526–545, E2E dòng 549–603, nhóm AUD2 dòng 1184–1199)
- docs/parallel-delivery/ownership-and-locks.yaml
- D1/D3/D4 trong AGENTS.md, HANDOFF.md, docs/parallel-delivery/overlay-and-evidence.md dòng 67
- Binding liên quan: docs/parallel-delivery/bindings/b-d-production-snapshot.json, docs/parallel-delivery/bindings/c-d-media-candidates.json, docs/parallel-delivery/bindings/j-provider-route.json

## Bảng đính chính

| # | Vị trí | Loại lỗi | Nội dung sai | Nguồn chuẩn thay thế |
| --- | --- | --- | --- | --- |
| 1 | M5-D-contract-freeze.md:85 và M5-D-test-plan.md:44 | INVARIANT_SAI | gán INV-014 cho ràng buộc thời lượng script 61–70 giây | INV-014 là tái khai thác không trùng (10-test-strategy.md dòng 539). Thời lượng 61–70 giây được kiểm trên video thực tế của F (docs/09-contracts/08-render-quality-contracts.md CT-QC-001); ước lượng của D không phải oracle INV. |
| 2 | M5-D-contract-freeze.md:105,116 và M5-D-test-plan.md:54 | INVARIANT_SAI, QUY_TAC_TU_DAT | gán INV-020 cho hook/thumbnail; cố định thumbnail ở '0–3 giây' | INV-020 là dữ liệu không tin cậy (dòng 545, CT-AI-000). Quy tắc thumbnail theo CT-MED-004 và CT-RND-003 điều kiện 3 (time range của thumbnail nằm trong time range của hook); không có hằng 0–3 giây. |
| 3 | M5-D-contract-freeze.md:156-159 | SCHEMA_TU_DAT | thực thể ArticleSnapshot (lấy từ key_interface_boundaries.interface_b_d) gán cho CT-CNT-002 | 09-contracts không có ArticleSnapshot; D nhận refs revision của B qua CT-AI-001 ProductionSnapshot và CT-CNT-003 ArticleRevisionAccepted; xem bindings/b-d-production-snapshot.json. |
| 4 | M5-D-test-plan.md:33-75 | TEST_ID_NGOAI_CATALOG | TST-CRE-SNP-001/002, ANA-001, ANG-001, SCR-001/002, NAR-001, AST-001, PLN-001/002, VAR-001..003, MET-001, INV-001 | catalog: TST-INT-INV-004, TST-CTR-INV-006, TST-AI-INV-013, TST-AI-INV-014, TST-SEC-INV-020, TST-QC-INV-019, TST-WF-VAR-001..004. |
| 5 | M5-D-test-plan.md:75 | INVARIANT_SAI | TST-CRE-INV-001 mang tên invariant nhưng nội dung kiểm AIInvocationRecord | canary secret thuộc INV-012 / TST-SEC-INV-012 (dòng 537); bản ghi lời gọi theo CT-AI-010. |
| 6 | M5-D-test-plan.md:131 | DUONG_DAN_BANG_CHUNG_CAM | docs/milestones/m5-script/evidence/m5-d/ | D4. |

## Quy tắc dùng

Test ID mới phải vào catalog docs/10-test-strategy.md qua slice sở hữu tài liệu đó trước khi dùng làm oracle; bằng chứng ghi vào docs/delivery-evidence/<task-id viết thường>/report.md.
