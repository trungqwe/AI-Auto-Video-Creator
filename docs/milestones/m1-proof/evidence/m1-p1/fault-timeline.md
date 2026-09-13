# M1-P1 — Fault timeline

| Điểm lỗi | Trạng thái trước retry | Kết quả sau retry |
|---|---|---|
| Sau business mutation, trước outbox | Transaction rollback; aggregate/receipt/outbox đều 0 | Command hợp lệ có thể chạy lại một lần |
| Sau commit, trước ACK | Aggregate/receipt/outbox đã commit đúng một lần | Service mới trả receipt cũ, không mutation lại |
| Sau dispatch, trước `published_at` checkpoint | Consumer đã commit; outbox vẫn pending | Giao lại cùng event; consumer dedupe, projection không tăng lần hai |
| Generation hoặc recovery epoch cũ | Không có accepted activity result | Bị từ chối có cấu trúc, không mutation |
| External outcome unknown | Receipt giữ `outcome_unknown` | Cấm retry mù; reconcile rồi mới trả result cũ |
| Sau từng bước completion UoW | Ledger/job/capacity/variant/usage/outbox/cleanup cùng rollback | Retry sạch commit toàn bộ đúng một lần |
| Completion commit xong, mất ACK | Toàn bộ completion đã commit | Trả completion receipt cũ; mọi count/usage/event vẫn đúng một lần |
