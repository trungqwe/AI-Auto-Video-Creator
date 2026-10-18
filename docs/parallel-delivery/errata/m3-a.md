# Errata M3-A

> Nguồn đính chính hiện hành do CP1-CONTRACT-BINDING lập ngày 18/10/2026. Tệp kế hoạch cũ giữ nguyên; khi mâu thuẫn, nguồn chuẩn dưới đây thắng.

## Nguồn chuẩn

- docs/09-contracts/12-state-machines.md
- docs/09-contracts/04-source-content-contracts.md
- docs/10-test-strategy.md (bảng invariant dòng 526–545, E2E dòng 549–603, nhóm AUD2 dòng 1184–1199)
- docs/parallel-delivery/ownership-and-locks.yaml
- D1/D3/D4 trong AGENTS.md, HANDOFF.md, docs/parallel-delivery/overlay-and-evidence.md dòng 67
- Binding liên quan: docs/parallel-delivery/bindings/a-b-collected-document.json

## Bảng đính chính

| # | Vị trí | Loại lỗi | Nội dung sai | Nguồn chuẩn thay thế |
| --- | --- | --- | --- | --- |
| 1 | M3-A-contract-freeze.md:183 | STATE_MACHINE_TU_DAT | `ACTIVE -> DISABLED -> REMOVED_TOMBSTONE`, mất cạnh DISABLED→ACTIVE | 12-state-machines.md CT-STATE-001: `ACTIVE ↔ DISABLED → REMOVED_TOMBSTONE`; restore theo CT-SRC-003. |
| 2 | M3-A-contract-freeze.md:186-193 | STATE_MACHINE_TU_DAT | chỉ chép Run, bỏ vòng đời Cycle và bảng terminal | CT-STATE-002 đầy đủ: Cycle `PLANNED → RUNNING → COMPLETED\|COMPLETED_PARTIAL\|FAILED`; bảng RETRY_EXHAUSTED/SOURCE_INACTIVE. |
| 3 | M3-A-contract-freeze.md:97-165 | SCHEMA_TU_DAT | enum extraction_disposition SUCCESS/PARTIAL/FAILED/EMPTY_CONTENT; trường con bắt buộc http_observation.status_code/content_type/safe_headers; enum media_type và provenance_chain.step; trường eligibility_reason | docs/09-contracts/04-source-content-contracts.md CT-SRC-006 và bindings/a-b-collected-document.json (khoá trường cấp 1 và kiểu; giá trị enum extraction do policy A quyết, ghi GIẢ ĐỊNH). |
| 4 | M3-A-contract-freeze.md:24,27 | REGISTRY_SAI | owner CONTRACT-STATE-MACHINES ghi CROSS-CUTTING; prefix CONFIG-SECURITY thiếu CT-ACC-*, CT-COST-* | contract-registry.yaml: owner G cùng co-owners; đủ 6 prefix. |
| 5 | M3-A-test-plan.md:51-54 | TEST_ID_NGOAI_CATALOG | TST-RULE-A001/A004/A013/A014 | catalog: TST-INT-INV-015, TST-SEC-INV-020, TST-COL-END-001..004, TST-SRC-RACE-001..004, TST-COL-PKG-001..004. |
| 6 | M3-A-test-plan.md:62-66 | TEST_ID_NGOAI_CATALOG | TST-SEC-SSRF-001..005 | SSRF theo CT-SRC-001 và CT-SEC-003; dùng mô tả hành vi tới khi catalog bổ sung ID. |
| 7 | M3-A-test-plan.md:121-127 | DUONG_DAN_BANG_CHUNG_CAM, MAU_BANG_CHUNG_DIEN_SAN | docs/milestones/m3-collection/evidence/m3-a/ và status.json mẫu {"status": "PASS"} | D4: docs/delivery-evidence/<task-id>/report.md (PATH-DELIVERY-EVIDENCE); chỉ ghi PASS khi có output lệnh thật. |
| 8 | M3-A-test-plan.md:93-99 | NGUON_QUYEN_CU | path/lock ghi là chưa đăng ký; gate USER-CKPT-M3 | ownership-and-locks.yaml dòng 119–126 (PATH-SRC-SOURCE-INGESTION, src/source_ingestion/**); D3: ủy quyền AI_SETUP và user duyệt Phần B ngày 18/10/2026. |

## Quy tắc dùng

Test ID mới phải vào catalog docs/10-test-strategy.md qua slice sở hữu tài liệu đó trước khi dùng làm oracle; bằng chứng ghi vào docs/delivery-evidence/<task-id viết thường>/report.md.
