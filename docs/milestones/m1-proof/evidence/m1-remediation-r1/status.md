# M1 audit remediation R1 - Status

Ngày kiểm tra: 13-09-2026.

Trạng thái: **PASS_REMEDIATION_REVIEW** cho các issue trong `audit-r1.md`.

Phạm vi này chỉ khắc phục và kiểm tra lại M1-P0/M1-P1. Nó không chứng minh G01, G04, G07, không mở M2/M3/Module A và không thay thế external proof.

| Issue | Kết quả | Bằng chứng chính |
|---|---|---|
| M1-AUD-B01 | CLOSED | Barrier race: đúng một command được chấp nhận; aggregate advisory lock theo workspace/aggregate |
| M1-AUD-B02 | CLOSED | Workspace epoch authority; stale command/event/fence bị từ chối trước mutation |
| M1-AUD-B03 | CLOSED | Allowlist và secret scan tại mutation/event/activity/external reconciliation boundary |
| M1-AUD-M01 | CLOSED | Live hash/runtime/uv/PostgreSQL probe; lock drift và endpoint sai fail closed |
| M1-AUD-M02 | CLOSED | Operation receipt v2 scope theo workspace/type; transition có điều kiện |
| M1-AUD-M03 | CLOSED | Activity grant bind operation/input; duplicate trả receipt cũ, conflict bị từ chối |
| M1-AUD-M04 | CLOSED_WITH_LIMITATION | Có barrier và process restart thật; acceptance command/timestamp/hash mới đầy đủ. Stdout RED lịch sử trước thư mục này không được dựng ngược |
| M1-AUD-M05 | CLOSED | Completion admission bind owner refs, exact output hash, QC/cloud state và registry revision trong cùng transaction |

Acceptance cuối: `42 passed in 5.80s`, exit `0`.

Coverage cuối: `42 passed`, tổng `93%`; module `contracts.py` đạt `95%`, `completion_admission.py` đạt `100%`.

Migration proof: `up -> 5 tables`, `down -> 0 tables`, `up -> 5 tables`, exit `0`.

Không ADR nào phải mở lại: các lỗi nằm ở implementation/evidence protocol, không phủ định topology hay quyết định kiến trúc hiện hành.
