# ADR-0011: Quan sát, tài nguyên và bằng chứng chi phí

**Trạng thái:** Conditional - chưa chứng minh G02/G03/G07  
**Căn cứ:** R10/R20/R23, QR-PERF-001/003/004/005/006, QR-COST-001/003, QR-OBS-*; ARCH-015.  
**Liên quan:** [ADR-0003](./0003-durable-workflow-engine.md), [ADR-0010](./0010-storage-lifecycle-and-recovery.md).

## Tại sao phải quyết định

Render nhanh chưa đủ đạt 100 output đã sync trong 12 giờ. GPU, VRAM, download, TTS, DB và provider quota có thể là nút nghẽn. Thêm mọi công cụ monitoring hoặc mọi dòng log vào DB có thể làm chính việc quan sát gây tốn tài nguyên.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Log file và concurrency cố định cao | Ít thiết kế | Khó truy vết, dễ đầy VRAM/ổ đĩa và tranh GPU |
| Full monitoring stack + nhiều host ngay | Nhiều biểu đồ, scale sớm | Chi phí/công vận hành khi chưa có tải thật |
| Structured status/receipt + log giới hạn + admission theo tài nguyên | Đủ debug, kiểm soát backpressure, mở rộng theo bằng chứng | Cần metric, ownership và bộ workload đại diện |

## Chọn cái gì và tại sao

Chọn phương án ba. PostgreSQL giữ trạng thái nghiệp vụ/error summary/audit để UI đọc. Log chi tiết và trace có quota/rotation; OpenTelemetry correlation chuẩn hóa ID, chưa bắt buộc một backend giám sát trả phí hoặc full Prometheus/Grafana. Exporter lỗi không làm mất business receipt hoặc dừng lô độc lập.

Mỗi video/lần thử truy được batch/session/workflow/stage/device/provider khi áp dụng. Cloud background có run ID riêng, không bịa AppSession. Health supervisor và backup không phụ thuộc Temporal còn sống.

G cấp việc theo CPU/GPU/VRAM/RAM/disk/network; một resource arbiter trên desktop quản local AI, transcode và render xuyên các queue. Không chỉ đặt concurrency riêng cho từng process rồi cộng vượt RAM. Cloud spool có budget riêng và không được làm đầy ổ database.

Staging giữ khoảng năm video gần lượt, chia sẻ file bằng reference; output chờ sync tính vào byte budget riêng. Low-disk dừng cấp thêm việc phụ thuộc, giữ output hiện hữu và tiếp tục việc độc lập. Số concurrent và ngưỡng byte cụ thể chờ thực đo.

Ngân sách theo R20. Cảnh báo dự báo 80% theo QR-COST-003; không tự dừng runtime nếu chưa cấu hình. Chưa biết giá/usage phải ghi chưa biết, không 0. Không tự thêm dịch vụ trả phí khi AI lỗi.

## Hồ sơ kiểm chứng bắt buộc

- G02: ≥100 video hợp lệ đã sync trong 12 giờ; cùng output có đủ hook/thumb/audio, tiếng Anh, phụ đề karaoke, duration và biến thể; đo đầu-cuối, cả retry/sync.
- G03: số nguồn/bài/media/GB hằng ngày, giờ sản xuất mỗi tháng, usage AI/TTS, traffic/egress, dung lượng DB/index/WAL/log/backup và giá host. Tổng chi phí bổ sung dưới 50 USD/tháng; chưa có bảng số thì chưa đạt gate.
- G07: UI p95 2 giây, command ACK 1 giây, resume 5 phút, lịch đủ điều kiện được bắt đầu 99% theo tài liệu 03. Bộ dữ liệu và mốc đo phải chốt trước thử; không sửa ngưỡng sau khi nhìn kết quả.

Mốc 100/12 giờ tương đương trung bình 8,33 output/giờ nhưng không quy định độ trễ từng video hoặc số video tháng. Không thể suy giá tháng chỉ từ tốc độ encode.

## Điểm bất lợi

Admission làm một số công việc chờ dù worker còn rảnh CPU; đó là hệ quả của giới hạn disk/GPU/quota. Một host tiết kiệm công vận hành nhưng còn điểm lỗi chung. Chưa có benchmark nên không tuyên bố hiệu năng/chi phí thắng giải pháp khác.

## Sau này đổi thì thế nào

Tăng worker hoặc tách dịch vụ chỉ khi metric xác định nút nghẽn. Đổi concurrency/TTL/resource policy có revision; giữ log đủ để so trước/sau. Nếu Temporal/host vượt ngân sách, mở lại ADR-0003/0001 với Prefect hoặc topology khác; không hạ hard gate hay xóa output để đạt số lượng.
