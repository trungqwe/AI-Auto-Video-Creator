# ADR-0006: Drive, artifact bất biến và journal desktop

**Trạng thái:** Conditional - G04/G05 chưa kiểm chứng trên tài khoản thật  
**Căn cứ:** R13/R18/R24, DR-009/010/011/020, QR-REL-005; ARCH-008.  
**Liên quan:** [ADR-0004](./0004-commit-idempotency-and-fencing.md), [ADR-0010](./0010-storage-lifecycle-and-recovery.md).

## Tại sao phải quyết định

Drive phải giữ output lâu dài; desktop dọn sau sync. Timeout upload có thể xảy ra sau khi Drive đã nhận đủ byte. Nếu nhận nhầm file hoặc mất receipt, lần chạy sau có thể upload trùng, đếm lại hoặc xóa bản duy nhất.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Thư mục Drive sync và kiểm tra tên tệp | Ít API trực tiếp | Không đủ bằng chứng byte đã sync hoặc file thuộc đúng attempt |
| Mỗi retry tạo file mới qua API | Dễ bắt đầu | Nhân bản output, khó reconcile và đếm sản lượng |
| Drive API với ID cấp trước, manifest và checksum | Danh tính ổn định, retry có đối chiếu | Cần OAuth, journal, trạng thái upload và kiểm chứng |
| Object storage khác làm chính | API object chuyên dụng | Thêm chi phí, không tận dụng kho Drive đã yêu cầu |

## Chọn cái gì và tại sao

Chọn Drive API qua I. Mỗi account là StorageArea riêng; routing theo loại dữ liệu được cấu hình, không coi bốn quota thành một ổ nguyên tử. Không tự thay Drive chính bằng provider trả phí.

Với binary output, xin file ID trước và lưu mapping `artifact/version -> StorageArea/file_id` vào PostgreSQL trước upload. Retry giữ ID; resumable session hết hạn thì mở session phù hợp cho cùng danh tính sau đối chiếu. Drive hỗ trợ chống tạo trùng với pre-generated ID; `409` vẫn phải đọc và verify file hiện hữu. [Drive upload](https://developers.google.com/workspace/drive/api/guides/manage-uploads#use_a_pre-generated_id_to_upload_files).

Receipt phải gắn ID đích, artifact revision, size và hash của byte thực; nếu metadata hash không đủ thì tải kiểm tra. Tên/size đơn thuần không là bằng chứng sync. Hash nội dung không là bằng chứng quyền sử dụng.

Giữ file ID chỉ áp dụng retry cùng artifact revision/byte. Render lại ra byte khác tạo artifact revision và file ID khác; không update nội dung đối tượng đã sync. Chỉ một artifact được completion ledger chấp nhận cho một job, nên nhiều attempt artifact không làm tăng sản lượng.

SQLite có hai loại dữ liệu: cache đã có bản chính trên cloud, và journal/receipt chưa gửi cần giữ bền. Không được xóa journal với lý do “tái dựng được”. File tạm ghi có manifest và hoàn tất local trước khi nhận là artifact; sau crash đối chiếu cả file tồn tại và checksum. Session URI mã hóa, SQLite giữ secret reference. Token refresh thuộc J cloud theo ADR-0009.

Chỉ dọn local sau completion commit/cleanup authorization và hết reference active. Output chưa sync ở ngoài cửa sổ khoảng năm bộ tài nguyên, nhưng vẫn tính trong hạn mức byte và backpressure.

## Điểm bất lợi

Drive không tham gia transaction PostgreSQL. Mất/revoke account có thể làm artifact không truy cập được; không hứa cứu byte chưa có bản sao khác. Việc kiểm chứng hash hoặc tải lại tăng I/O; direct upload vẫn cần token hợp lệ và mạng.

## Kiểm chứng

G04: create/upload mất ACK, session expired, conflict ID, file cùng tên khác byte, thiếu checksum, token revoked, quota chung, desktop offline lâu, local HTTPS/Origin và Temporal authorization. M1-P3 chỉ kiểm chứng Drive/OAuth trên tài khoản thật, upload/integrity/reconcile và refresh/revoke trong phạm vi proof. Nếu đạt, kết quả là `G04_M1_SCOPE=PASS_M1_SCOPE`; local HTTPS/Origin, Temporal authorization, account pool và production path thuộc M2-M7, nên G04 tổng thể vẫn `PARTIALLY_PROVEN`. G05: journal mất hoặc DB restore cũ phải có trạng thái không chắc; cấm dọn bản duy nhất tới khi đối chiếu xong.

## Sau này đổi thì thế nào

Thay StorageAdapter giữ nguyên artifact ID/checksum; copy, verify, đổi location mapping rồi mới dọn đích cũ khi đủ điều kiện. Nhiều location không biến thành nhiều video. Nếu account không dùng API được, giữ gate chặn, báo dữ liệu thiếu; không tự mua kho mới hoặc coi sync folder đã đủ proof.
