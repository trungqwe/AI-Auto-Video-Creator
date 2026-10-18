# Errata M6-EF

> Nguồn đính chính hiện hành do CP1-CONTRACT-BINDING lập ngày 18/10/2026. Tệp kế hoạch cũ giữ nguyên; khi mâu thuẫn, nguồn chuẩn dưới đây thắng.

## Trạng thái tệp

Ba tệp M6-EF-contract-freeze.md, M6-EF-execution-package.md và M6-EF-test-plan.md bị hỏng dấu tiếng Việt (ký tự '?' thay chữ có dấu, ví dụ M6-EF-execution-package.md:49 'Tuy?t ??i kh?ng ghi ??'). Ba tệp này không dùng làm nguồn kế hoạch, oracle hay bằng chứng. Kế hoạch E và F được viết lại ở IMPL-PLAN-E và IMPL-PLAN-F (docs/implementation/**, PATH-IMPLEMENTATION-PLANS dòng 225–242, lock LOCK-IMPL-PLAN-E / LOCK-IMPL-PLAN-F).

## Nguồn chuẩn

- docs/09-contracts/12-state-machines.md
- docs/09-contracts/07-media-processing-contracts.md
- docs/09-contracts/08-render-quality-contracts.md
- docs/10-test-strategy.md (bảng invariant dòng 526–545, E2E dòng 549–603, nhóm AUD2 dòng 1184–1199)
- docs/parallel-delivery/ownership-and-locks.yaml
- D1/D3/D4 trong AGENTS.md, HANDOFF.md, docs/parallel-delivery/overlay-and-evidence.md dòng 67
- Binding liên quan: docs/parallel-delivery/bindings/d-e-f-voice-timing.json, docs/parallel-delivery/bindings/f-render-package.json

## Bảng đính chính

| # | Vị trí | Loại lỗi | Nội dung sai | Nguồn chuẩn thay thế |
| --- | --- | --- | --- | --- |
| 1 | M6-EF-contract-freeze.md:232-234 | STATE_MACHINE_TU_DAT | VoiceTrack INITIATED→SYNTHESIZING→NORMALIZING_LUFS→READY\|FAILED; WordTiming PENDING_VOICE→ALIGNING→VERIFYING_MONOTONIC→READY\|INVALIDATED\|FAILED | 12-state-machines.md không có hai máy này; dùng CT-STATE-005 (Rendition DECLARED→PROCESSING→READY\|FAILED\|OUTCOME_UNKNOWN), CT-STATE-008 (stage), CT-STATE-011 (receipt). Timing hết hiệu lực theo docs/09-contracts/07-media-processing-contracts.md CT-SUB-001 bất biến 3. |
| 2 | M6-EF-test-plan.md:141-150 và M6-EF-contract-freeze.md:100-187 | INVARIANT_SAI | INV-001 độ phân giải, INV-002 thời lượng, INV-008 khớp thời lượng audio, INV-009 dọn tệp render, INV-010 vô hiệu timing, INV-011 fingerprint package, INV-018 hard gate QC, INV-019 phủ từ, INV-020 thumbnail | catalog docs/10-test-strategy.md dòng 526–545: INV-001 command idempotency; INV-002 event idempotency; INV-007 timing gắn script/voice (đúng mã cho vô hiệu timing); INV-008 render package chỉ chứa artifact đã verify; INV-009 QC pass mà upload chưa verify thì không completion; INV-010 completion chỉ đếm một lần; INV-011 cleanup auth; INV-018 allocator; INV-019 bằng chứng tiếng Anh theo exact revision; INV-020 dữ liệu không tin cậy. |
| 3 | M6-EF-contract-freeze.md:150; M6-EF-test-plan.md:57,67,79 | QUY_TAC_TU_DAT | thumbnail cố định '0–3 giây' | CT-RND-003 điều kiện 3: time range của thumbnail nằm trong time range của hook. |
| 4 | M6-EF-test-plan.md:33-89 | TEST_ID_NGOAI_CATALOG | TST-MED-PRB/SAF/NRM-001, TST-VOI-*, TST-RND-*, TST-EF-* | catalog: TST-MEDIA-INV-007, TST-INT-INV-008, TST-QC-INV-019, TST-E2E-001..014. |

## Quy tắc dùng

Test ID mới phải vào catalog docs/10-test-strategy.md qua slice sở hữu tài liệu đó trước khi dùng làm oracle; bằng chứng ghi vào docs/delivery-evidence/<task-id viết thường>/report.md.
