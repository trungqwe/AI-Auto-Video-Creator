# ADR-0003: Temporal là engine ưu tiên có điều kiện

**Trạng thái:** Conditional - G01/G03/G07 chưa chạy  
**Căn cứ:** R17-R19, QR-REL-001/004/008, QR-AVL-001/004; ARCH-001/009.  
**Liên quan:** [ma trận kiến trúc](../08-architecture.md), [ADR-0004](./0004-commit-idempotency-and-fencing.md).

## Tại sao phải quyết định

Job có nhiều stage, chờ desktop/provider và tiếp tục qua nhiều phiên. Chọn engine ảnh hưởng semantics retry, lỗi, versioning và công sức phục hồi lâu dài.

## Các lựa chọn và đánh giá

| Lựa chọn | Cơ chế/lợi ích | Bất lợi | Điểm kiến trúc |
|---|---|---|---:|
| Desktop-centric | Local điều phối, cloud sync | Không khớp yêu cầu chạy nền và trạng thái chung | 6,05 |
| PostgreSQL state machine tự xây | Transaction/lease do dự án tự quản | Tự xây nhiều cơ chế phục hồi, timer và debug | 7,35 |
| Prefect self-hosted | Flow/task/deployment và worker Python | Cần proof semantics resume/offline; thêm vận hành server | 7,90 |
| Temporal self-hosted | Durable workflow history và worker polling | Determinism, migration, vận hành và tài nguyên phức tạp | 8,15 |

Trọng số và từng điểm nằm ở mục 3 tài liệu 08. Đây là đánh giá chuyên môn, không phải test. Đổi 10% trọng số từ đúng đắn sang vận hành làm Prefect 7,80 và Temporal 7,65; lựa chọn không bền vững trước mọi ưu tiên. Hiệu năng thực chưa có bằng chứng để phân biệt engine.

## Chọn cái gì và tại sao

Giữ Temporal làm hướng ưu tiên vì phục hồi là ưu tiên đã duyệt. Chưa coi Temporal đủ nhẹ hoặc đủ rẻ trước G03. Prefect là lựa chọn đánh giá lại đầu tiên nếu proof thất bại, không tự chuyển công nghệ khi chưa ghi ADR thay thế.

Cloud Workflow Worker poll `control-workflows`, chạy code deterministic và tồn tại khi desktop tắt. Activity I/O/AI/render chạy trên queue riêng theo capability/device. Temporal phân biệt workflow và activity queues; handler của worker phải phù hợp queue. [Temporal Task Queues](https://docs.temporal.io/task-queue).

Batch giữ mục tiêu, video child giữ một sản phẩm; collection không đợi toàn bộ AI enrichment. Manual debug gọi cùng handler/validation như auto nhưng dừng sau stage. Chờ desktop/provider là trạng thái bền; timeout thực thi và timeout chờ năng lực được tách. Child lỗi không làm lỗi sibling; policy đóng parent/continue-as-new phải bảo toàn child còn chạy.

Activity dùng tệp local phải giữ device affinity; thêm worker không tự chia sẻ được filesystem. Workflow history chỉ mang ID/revision/result nhỏ, không chứa secret/blob. Outbox dispatcher và host supervisor tồn tại độc lập engine.

## Điểm bất lợi

Engine không cung cấp exactly-once side effect, không bảo đảm chất lượng AI, không tự xác minh Drive sync và không thay quy tắc nội dung. Phải giữ worker/code version tương thích history cũ. Retry và heartbeat có chi phí thực cần đo.

## Kiểm chứng và điều kiện đổi

G01 gồm mất điện tại stage, lost ACK, stale worker, child lỗi, desktop offline, manual resume và replay history sau upgrade. M1-P2 chỉ chứng minh lát cắt crash/retry/offline/stale/child cùng replay history qua thay đổi workflow code tương thích trên Temporal Server/SDK R1 đã khóa. Nếu đạt, kết quả là `G01_M1_SCOPE=PASS_M1_SCOPE`; upgrade Server/SDK và production-path replay tiếp tục được kiểm chứng ở M2-M7, nên G01 tổng thể vẫn `PARTIALLY_PROVEN`. G03 đo host cost/RAM/WAL. G07 kiểm tra tổ hợp SDK/server/PostgreSQL.

Nếu thất bại, so lại Prefect và state machine với cùng kịch bản. Chuyển engine bằng quiesce/hoàn tất workflow cũ hoặc migration từ stage đã commit; không hứa chuyển trực tiếp Temporal history sang engine khác. Business ID/receipt/snapshot giữ nguyên, không chạy lại side effect đã biết hoàn thành.
