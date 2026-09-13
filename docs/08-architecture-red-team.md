# Red-team kiến trúc trước triển khai

**Tài liệu phân tích:** [08-architecture.md](./08-architecture.md) và [ADR index](./adr/README.md)  
**Chiều kiểm tra:** edge case, bảo mật, khả năng mở rộng, lan truyền lỗi và rủi ro tích hợp  
**Phát hiện còn lại:** 0 Critical, 0 High, 5 Medium  
**Kết luận:** **PROCEED tới bước thiết kế giao tiếp; chưa được chuyển sang code hoặc production.**

Bản red-team này được thực hiện sau khi 18 phát hiện ở [báo cáo audit](./08-architecture-audit.md) đã được đưa vào thiết kế. Các mục bên dưới là thách thức còn phải giữ trong gate, không phải lỗi đã được chứng minh trong phần mềm.

## MEDIUM

### ADV-001 - Edge case: lô không thể đạt mục tiêu

- **Thách thức:** mục 8.5 có giới hạn thử và phân biệt job chờ với hết việc, nhưng ngưỡng thử/chờ chưa chốt. Với target lớn, không còn ứng viên hợp lệ hoặc provider dừng dài ngày, lô có thể nằm `RUNNING` vô hạn hoặc kết thúc quá sớm.
- **Tác động:** UI báo sai tiến độ; lô chiếm reservation và không chuyển vòng hợp lý.
- **Ràng buộc hiện có:** trạng thái phải phân biệt `WAITING_CAPABILITY`, `EXHAUSTED_ELIGIBLE_WORK`, `FAILED` và `COMPLETED_TARGET`; timeout không được biến việc đang chờ thành cạn tin.
- **Xử lý tiếp:** bước 11 định nghĩa state/command; G01 kiểm tra resume và giới hạn thử. Giá trị timeout cụ thể vẫn `ARCH-OPEN-008`, không tự điền.

### ADV-002 - Bảo mật: access token Drive trên desktop có phạm vi rộng hơn một artifact

- **Vector:** máy desktop hoặc process local bị chiếm quyền trong thời gian token còn hiệu lực.
- **Điểm vào:** mục 11.2 và ADR-0009 cho desktop nhận access token ngắn hạn để upload trực tiếp.
- **Tác động:** attacker có thể thao tác trong phạm vi OAuth được Google cấp, không chỉ file đang upload.
- **Ràng buộc hiện có:** token ở bộ nhớ, TTL ngắn, scope tối thiểu khả thi, device identity, không lưu qua SQLite/Temporal, thu hồi/rotation và audit; không mô tả token là file-scoped khi không có bằng chứng.
- **Xử lý tiếp:** G04 phải kiểm tra scope/quyền thật và threat test. Nếu phạm vi vẫn quá rộng cho SaaS, thay bằng upload broker/signed mechanism được provider hỗ trợ hoặc redesign trust boundary trước mở nhiều tenant.

### ADV-003 - Khả năng mở rộng: một PostgreSQL host chịu nhiều loại tải

- **Nút nghẽn:** mục 5.1/7.3/12/13 đặt app transaction, Temporal persistence/visibility, FTS, pgvector, WAL và summary log cùng cluster/host ban đầu.
- **Ở tải cao:** crawl burst, rebuild vector index hoặc workflow history có thể làm chậm commit completion và UI; backup có thể cạnh tranh disk I/O.
- **Ràng buộc hiện có:** database/role tách, log chi tiết không vào bảng nghiệp vụ, admission theo byte/tài nguyên, search projection có thể tách và gate đo workload.
- **Xử lý tiếp:** G02/G03/G07 đo contention, WAL/index/backup. Không thêm search/monitoring service chỉ vì dự báo; tách đúng thành phần khi metric xác định bottleneck.

### ADV-004 - Lan truyền lỗi: trạng thái lệch giữa PostgreSQL, Temporal và Drive

- **Điểm lỗi:** sau Drive upload, sau business commit hoặc trước Temporal ACK ở mục 7.4/8.3/9.2.
- **Lan truyền:** retry tạo file/result trùng, worker cũ ghi đè, lô đếm hai lần hoặc cleanup xóa bằng chứng.
- **Ràng buộc hiện có:** pre-generated file ID cho cùng byte, artifact bất biến, outbox, operation receipt, execution generation, completion ledger và cleanup authorization.
- **Trải nghiệm lỗi:** UI phải hiện trạng thái chưa rõ/chờ đối chiếu; không báo hoàn thành hoặc tự render lại.
- **Xử lý tiếp:** G01/G04/G05 phải gây crash ở từng ranh giới. Cho tới khi test đạt, ADR-0003/0006/0010 giữ `Conditional`.

### ADV-005 - Rủi ro tích hợp: tổ hợp version và nâng cấp workflow chưa được chứng minh

- **Xung đột:** mục 5.3/9.1/11/12 phụ thuộc Python SDK, Temporal Server, PostgreSQL/pgvector, FFmpeg, GPU driver và Local Agent; chưa có source code hoặc build manifest để kiểm tra tương thích.
- **Tác động:** worker mới không replay được history cũ, DB extension/build lệch hoặc desktop cũ nhận activity không hỗ trợ.
- **Ràng buộc hiện có:** pin version, capability/build handshake, expand-contract, replay compatibility, worker version routing và rollback theo ADR-0012.
- **Xử lý tiếp:** G07 khóa compatibility matrix và replay history trước phát hành. Vì chưa có codebase, không thể đối chiếu interface hay migration thực; phần integration code được hoãn đúng giai đoạn.

## Strength Notes

- Nguồn sự thật nghiệp vụ, workflow history và byte storage có owner khác nhau; thiết kế không dùng một công cụ cho ba vai trò.
- Retry kỹ thuật, biến thể mới và completion đã có danh tính/bằng chứng riêng.
- Thiết kế bao phủ lost ACK, stale worker, restore cũ hơn side effect, shared-file cleanup và quyền dùng dữ liệu lịch sử sau khi xóa nguồn.
- Các lựa chọn chưa đủ bằng chứng được ghi `Conditional` và có gate, thay vì trình bày như kết quả đã đạt.

## Verdict

Không còn Critical/High chưa có hướng xử lý trong tài liệu. Năm điểm Medium phải đi vào contract và test plan; chúng không cản trở viết bước 11. Bất kỳ triển khai nào bỏ operation generation, completion ledger, OAuth scope test, device affinity hoặc replay test sẽ làm verdict quay lại `REVISE`.

Chưa có mã nguồn để chạy kiểm tra integration với implementation. Security review riêng nằm tại [08-security-audit.md](./08-security-audit.md).
