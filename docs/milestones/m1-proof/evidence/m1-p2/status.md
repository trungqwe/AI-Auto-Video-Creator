# M1-P2 — Temporal G01 Proof Status

**Ngày hoàn thành:** 13-09-2026  
**Trạng thái Work Package:** `PASS_M1_SCOPE`  
**Trạng thái Cổng G01:** `PARTIALLY_PROVEN` (chỉ trong phạm vi proof M1-P2)  
**Phạm vi áp dụng:** Temporal Server 1.31.2 + Python SDK 1.32.0 tương thích với contracts P1.

## 1. Kết quả kiểm thử (Acceptance Proof)

| Test ID | Nội dung kiểm thử | Kết quả | Ghi chú & Bằng chứng |
|---|---|---|---|
| `TST-M1-P2-001` | Worker lifecycle & offline resume | **PASS** | Workflow tạm dừng khi simulated desktop offline, resume từ đúng stage khi online; Stage 1 không chạy lại. |
| `TST-M1-P2-002` | Activity retry & lost-ACK idempotency | **PASS** | Activity retry sau lost-ACK mạng sử dụng đúng receipt P1; side effect chỉ thực hiện đúng 1 lần (`len(ops) == 1`). |
| `TST-M1-P2-003` | Worker generation fencing | **PASS** | Worker mang generation cũ (1 < active 2) bị chặn với lỗi `StaleGenerationError` / `STALE_GENERATION`. |
| `TST-M1-P2-004` | Child workflow failure isolation | **PASS** | Child B thất bại có kiểm soát, Child A hoàn thành; Parent bắt exception và cô lập lỗi mà không crash parent. |
| `TST-M1-P2-005` | Workflow replay versioning & patch | **PASS** | History sinh ra bởi V1 replay thành công trên V2 qua `workflow.patched()`; thay đổi nondeterministic bị detector từ chối. |
| `TST-M1-P2-006` | Unknown outcome reconciliation routing | **PASS** | Khi gặp `UnknownExternalOutcomeError`, Temporal không retry mù mà định tuyến vào `reconcile_external_outcome_activity`. |
| `TST-M1-P2-007` | Payload boundaries & secret redaction | **PASS** | Secret canary (`ghp_...`) và binary blob thô bị chặn tại boundary; Event history Temporal được xác nhận hoàn toàn sạch. |

- Tổng số test M1 hiện hành: **49/49 PASSED** (thời gian chạy ~8.71s).
- Tổng độ bao phủ mã nguồn (Coverage): **93%**.

## 2. Giới hạn & Quyết định kiến trúc

1. **Phạm vi hoàn tất:**
   - Kết quả này xác nhận Temporal Server 1.31.2 + Python SDK 1.32.0 đáp ứng đầy đủ ngữ nghĩa workflow cần thiết cho M1.
   - Trạng thái ADR-0003 chuyển từ `Conditional` sang `PROVEN_IN_M1_SCOPE`.
2. **Giới hạn chuyển giao:**
   - Cổng G01 toàn phần vẫn ở mức `PARTIALLY_PROVEN` do các bài kiểm thử nâng cấp server dài hạn và replay trên môi trường production thực tế thuộc trách nhiệm của các milestone M2–M7.
   - Không tự ý mở quyền sang M2, M3 hoặc Phân hệ A.
   - Cổng G04 (Drive/OAuth M1-P3) tiếp tục giữ trạng thái `NOT TESTED` và bị chặn bởi `ROADMAP-OPEN-003` cho đến khi có credential thật.
