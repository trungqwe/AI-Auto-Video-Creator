# M1-P1 — Trạng thái proof

**Ngày:** 13-09-2026  
**Trạng thái:** `PASS`  
**Phạm vi:** contract, idempotency, outbox/consumer dedupe, receipt/reconciliation, fencing và completion Unit of Work trong PostgreSQL 18.6  
**Không phải:** G01 Temporal, G04 Drive/OAuth, production schema hoặc video pipeline

## Kết quả

| Kiểm tra | Kết quả |
|---|---|
| Bộ P1 tổng hợp | 18/18 test PASS |
| Chạy lặp trong process mới | 18/18 test PASS |
| Coverage `contracts.py` + `media_usage.py` | 94% |
| PostgreSQL | 18.6, `synchronous_commit=on` |
| Completion snapshot | `1|completed|1|converted|converted|2|2|1|1` |
| Canary trong evidence P1 | Không tìm thấy |

Completion snapshot lần lượt là: ledger, job state, batch completed count, capacity state, variant state, registry revision, media usage count, `VideoCompleted` outbox count và cleanup eligibility count.

## Kỷ luật RED/GREEN

- `red-1` là harness RED không hợp lệ vì fixture yêu cầu schema trước oracle; được thay bằng `red-1b`, thất bại đúng vì schema/service chưa tồn tại.
- `red-2`, `red-3`, `red-4` thất bại đúng vì recovery, completion và dispatch-checkpoint behavior chưa được triển khai.
- `correction-1` là lỗi fixture psycopg do gửi nhiều statement có tham số trong một prepared statement; chỉ tách seed command, không đổi oracle nghiệp vụ.
- `green-1` đến `green-4`, bộ tổng hợp và lần chạy lặp đều giữ nguyên contract đã duyệt.

## Kết luận kiến trúc

Không có điều kiện STOP của P1 xảy ra. PostgreSQL transaction, owner port dùng chung connection, idempotency receipt, generation/recovery fencing và at-least-once consumer dedupe giữ được các invariant trong phạm vi proof. Không mở lại ADR-0002, ADR-0004 hoặc ADR-0009.

## Giới hạn

- Schema và service chỉ là M1 proof, chưa phải migration/API production.
- External side effect được mô phỏng bằng callback; behavior Temporal và Drive chưa được kiểm tra.
- Kết quả P1 không nâng G01, G04 hoặc G07 khỏi `NOT TESTED`.
