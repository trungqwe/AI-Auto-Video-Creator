# ADR-0002: PostgreSQL và chỉ mục có phiên bản

**Trạng thái:** Accepted - baseline thiết kế; hiệu năng/phiên bản chưa kiểm chứng  
**Căn cứ:** DR-001/002/011/016, QR-DATA-001/007, QR-SCALE-003; ARCH-005/007.  
**Liên quan:** [ADR-0004](./0004-commit-idempotency-and-fencing.md), [ADR-0007](./0007-runtime-and-admin-ui.md).

## Tại sao phải quyết định

Cloud và desktop phải cùng nhìn thấy một lịch sử bài, sự kiện, biến thể và tiến độ. Cần transaction để giữ suất lô, chống commit trùng và đóng snapshot. Danh mục phải truy hồi lâu dài sau khi byte local đã dọn.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Google Sheets làm lõi | Quan sát/sửa bảng trực tiếp | Khó bảo vệ quan hệ, transaction và quyền ghi; quota tham gia đường chạy |
| SQLite desktop + đồng bộ cloud | Nhẹ, thao tác local nhanh | Xung đột multi-writer/offline và khó giữ nguồn sự thật |
| PostgreSQL + FTS + pgvector | Giao dịch, quan hệ, metadata và retrieval cùng một nền tảng | Cần vận hành DB và kiểm soát tải index |
| PostgreSQL + search/vector service riêng | Scale retrieval độc lập | Thêm đồng bộ index, dịch vụ, chi phí và tình trạng dữ liệu lệch |

## Chọn cái gì và tại sao

PostgreSQL `app_core` là nguồn sự thật nghiệp vụ; Temporal persistence và visibility ở database/role riêng trong cùng cluster ban đầu. Desktop không có DB credential. Drive giữ binary; PostgreSQL giữ normalized source text, revision, provenance, script, kế hoạch, metadata, checksum và receipt.

Chọn PostgreSQL FTS cho từ khóa, pgvector cho tìm semantic; fuzzy matching cụ thể chốt khi thiết kế retrieval. Chưa chốt index approximate hoặc embedding model. pgvector hỗ trợ exact/approximate search và có đánh đổi recall khi dùng approximate index; phải đo cùng bộ lọc thực của dự án. [pgvector chính thức](https://github.com/pgvector/pgvector).

Mỗi embedding space có model revision/dimension/normalization/metric. Index mới được xây song song khi đổi model, kiểm tra trước khi đổi active revision. Không trộn vector khác không gian và không xóa index cũ đang phục vụ query.

Raw snapshot được dùng để sản xuất phải được bảo toàn trên Drive, liên kết từ revision; raw HTML của mọi bài bị loại không mặc định lưu vô hạn. JSONB vẫn có schema/version được validation.

## Điểm bất lợi

Giao dịch, FTS, vector, Temporal và log summary chia sẻ tài nguyên host. Dung lượng index/WAL và độ trễ truy vấn chưa biết khi thiếu workload tháng. Một database riêng cho Temporal không tạo isolation phần cứng.

## Kiểm chứng

G02/G03/G07: đo query với filter topic/asset status/workspace, metadata pagination, rebuild index, contention với workflow và dung lượng backup. Không được tải toàn bộ catalog vào UI rồi lọc phía client để giả rằng truy vấn nhanh.

## Sau này đổi thì thế nào

Thêm search service như read projection từ outbox có version và rebuild được. PostgreSQL tiếp tục sở hữu dữ liệu; đổi search không đổi Article/MediaAsset ID. Chuyển DB chính là thay đổi chi phí cao, cần migration và đối chiếu completion ledger. Chuyển self-host sang managed có thể giữ model dữ liệu nhưng phải kiểm tra pgvector, Temporal support và backup.
