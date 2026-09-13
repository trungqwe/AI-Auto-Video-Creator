# ADR-0001: Hybrid và modular monolith trong một monorepo

**Trạng thái:** Accepted - baseline thiết kế  
**Căn cứ:** R18/R19/R21; QR-AVL-001/002, QR-MNT-001, QR-SCALE-004.  
**Liên quan:** ARCH-002/003/004; [ADR-0003](./0003-durable-workflow-engine.md), [ADR-0012](./0012-evolution-and-saas-boundary.md).

## Tại sao phải quyết định

Desktop không luôn online nhưng nguồn tin/media phải tiếp tục được thu thập. Mười phân hệ đã duyệt xác định trách nhiệm, chưa xác định số repo hoặc tiến trình. Quyết định này ảnh hưởng deployment, giao dịch, cách debug và công sức duy trì nhiều năm.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Desktop giữ mọi thứ, cloud chuyển snapshot | Thử nhanh, ít dịch vụ | Trạng thái chia đôi, desktop offline làm gián đoạn điều phối |
| Hybrid với codebase module dùng chung | Cloud giữ tiến độ; desktop dùng phần cứng đã có; giao tiếp thống nhất | Cần vận hành cloud và contract giữa hai nơi |
| Microservice/repo riêng theo A-J | Scale và phát hành từng nhóm độc lập | Nhiều giao dịch phân tán, deployment và version contract ở quy mô một người |

## Chọn cái gì và tại sao

Chọn hybrid với Cloud Control Plane và Desktop Execution Plane; một monorepo chứa 10 module A-J theo tài liệu 06. Module nghiệp vụ có owner và interface; API, workflow worker, activity workers, UI và agent là các đơn vị chạy khác nhau.

Cloud có PostgreSQL, API, workflow engine, workflow worker và collection workers. Desktop chủ động kết nối, chạy script/plan/voice khi hoạt động, xử lý media và render. Gọi provider cloud từ desktop vẫn phù hợp R18. Tách tiến trình theo CPU/GPU/I/O giúp cô lập lỗi mà chưa cần mười dịch vụ độc lập.

Các module cloud ghi dữ liệu qua application service/repository của owner. Dùng chung PostgreSQL không cho module tùy ý ghi bảng của module khác. Domain không phụ thuộc SDK provider, FastAPI hoặc Temporal.

## Điểm bất lợi

- Mất cloud sẽ tạm dừng cấp việc/commit; desktop chỉ giữ kết quả chưa xác nhận.
- Một Linux host là failure domain chung. Đây là topology khởi đầu có điều kiện G03/G07, không là cam kết HA.
- Monorepo cần kỷ luật import, ownership và phát hành version tương thích; không tự tạo tính module chỉ bằng đặt tên thư mục.

## Kiểm chứng

Tắt desktop qua chu kỳ thu thập; xác minh cloud workflow còn tiến. Gây lỗi worker render và kiểm tra API/crawl độc lập. Chưa thực hiện các phép thử này. Topology chỉ được phát hành khi gate của engine, chi phí và tương thích đạt.

## Sau này đổi thì thế nào

Tách một module thành service khi có tải, quyền truy cập hoặc lịch phát hành riêng có bằng chứng. Giữ ID, contract và ownership; chuyển adapter từ gọi nội bộ sang giao tiếp từ xa có version. Tách database phải có migration/backfill và một writer chính thức tại mỗi thời điểm; không đồng bộ hai writer tạm bợ.

Mở rộng host/worker trước khi tách repo. Chi phí chuyển đổi ở mức vừa nếu boundary được tuân thủ, cao nếu cho phép truy cập chéo bảng không kiểm soát.
