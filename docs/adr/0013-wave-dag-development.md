# ADR-0013: Phát triển song song theo mô hình Wave và DAG

**Trạng thái:** Accepted - cơ sở cho mô hình phát triển song song Bộ 2
**Căn cứ:** QR-MNT-001, QR-MNT-002, QR-MNT-003, QR-SCALE-004, QR-SCALE-005; ARCH-002, ARCH-003, ARCH-004; DAG-implement-plan.md.
**Liên quan:** [ADR-0001](./0001-hybrid-modular-monolith.md), [ADR-0003](./0003-durable-workflow-engine.md), [ADR-0012](./0012-evolution-and-saas-boundary.md).

## Tại sao phải quyết định

Lộ trình phát triển ban đầu của hệ thống được tổ chức tuần tự nghiêm ngặt theo các milestone tuyến tính (`M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7`). Cách tiếp cận này giúp bảo toàn chặt chẽ các ranh giới kiểm thử ban đầu, nhưng nảy sinh ba nhược điểm lớn khi mở rộng quy mô phát triển:

1. **Nút thắt cổ chai phụ thuộc nhân tạo (Artificial Dependency Bottlenecks):** Các capability có thể phát triển hoàn toàn độc lập dựa trên hợp đồng giao tiếp (contracts) đã khóa vẫn buộc phải chờ đợi toàn bộ milestone phía trước hoàn tất. Ví dụ: việc xây dựng bộ sinh kịch bản (Capability D) hoặc xử lý âm thanh/voice (Capability E) phải chờ toàn bộ thu thập dữ liệu nguồn (Capability A) dù cấu trúc dữ liệu đầu vào đã được chuẩn hóa.
2. **Thời gian tích hợp muộn và rủi ro dồn cục:** Việc dồn toàn bộ tích hợp vào cuối kỳ khiến các sai lệch giao tiếp giữa producer và consumer bị phát hiện muộn, làm tăng chi phí sửa lỗi và kéo dài chu kỳ lặp.
3. **Hiệu suất điều phối đa tác nhân (Multi-Agent Delivery):** Trong môi trường tự động hóa điều phối của Orca, việc giới hạn một luồng công việc duy nhất làm lãng phí năng lực tính toán và token, không tận dụng được tính độc lập của các phân hệ.

Tuy nhiên, việc chuyển đổi sang phát triển song song không được phép phá vỡ các chốt an toàn kiến trúc cốt lõi, đặc biệt là quy tắc nghiệm thu phân hệ `QR-MNT-003` và các ranh giới phân quyền bất biến.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Giữ nguyên phát triển tuần tự tuyến tính | Đơn giản, rủi ro xung đột nhánh thấp | Tốc độ chậm, nút thắt cổ chai lớn, không tận dụng được năng lực đa worker |
| Phát triển song song tự do (No Fencing / Ad-hoc Concurrency) | Khởi tạo công việc nhanh chóng | Xung đột mã nguồn nghiêm ngặt, vỡ giao tiếp, vi phạm ranh giới thẩm quyền, không thể kiểm soát chất lượng |
| Phát triển song song theo mô hình phân tách Wave và DAG | Tối ưu hóa song song dựa trên hợp đồng đã khóa; kiểm soát chặt chẽ bằng single-writer và 4 trạng thái thẩm quyền; bảo toàn tính toàn vẹn hệ thống | Cần hạ tầng điều phối kiểm tra tĩnh (DAG validator), quản lý lease/fencing và kỷ luật hợp đồng chặt chẽ |

## Chọn cái gì và tại sao

Hệ thống quyết định áp dụng **Mô hình phối hợp Wave và DAG (Parallel Wave/DAG Delivery Architecture)**:

### 1. Phân định rõ ràng giữa Wave và DAG
- **Wave (Phân kỳ thẩm quyền & Lộ trình):** Dùng để trình bày lộ trình tổng thể cho người dùng và các bên liên quan, xác định các mốc phê duyệt phạm vi chiến lược (Scope Approval). Wave trả lời câu hỏi: *"Hệ thống đang ở giai đoạn nào về mặt thẩm quyền và mục tiêu kinh doanh?"*
- **DAG (Đồ thị thực thi kỹ thuật):** Quyết định việc nào thực sự có thể chạy đồng thời dựa trên các điều kiện tiên quyết kỹ thuật (Technical Prerequisites). DAG trả lời câu hỏi: *"Work package nào có hợp đồng độc lập, tài nguyên sẵn sàng và đường dẫn không xung đột để thực thi ngay bây giờ?"*
- **Nguyên tắc cốt lõi:** Không bắt cả một Wave phải chờ hạng mục chậm nhất mới cho phép các nhánh độc lập của Wave tiếp theo khởi chạy, miễn là các phụ thuộc kỹ thuật trên DAG đã được giải phóng đầy đủ.

### 2. Bốn trạng thái thẩm quyền độc lập (Four Authority States)
Để ngăn chặn tình trạng tự cấp quyền trái phép (Zero Hallucinated Authority), mọi work package trong hệ thống phải tuân thủ 4 trạng thái thẩm quyền riêng biệt:

1. **`planned` (Được lập kế hoạch):** Gói công việc đã có đặc tả kỹ thuật (spec), xác định DoR/DoD và các hợp đồng giao tiếp, nhưng chưa được phép chỉnh sửa mã nguồn sản phẩm.
2. **`implementation_authorized` (Được phép implementation):** Gói công việc được cấp quyền viết mã và kiểm thử đơn vị cục bộ trong phạm vi các thư mục được phân quyền (`owned_paths`), trên worktree độc lập, sau khi toàn bộ contract phụ thuộc đã được khóa (`frozen`).
3. **`integration_authorized` (Được phép integration):** Gói công việc đã vượt qua toàn bộ unit test và kiểm tra biên giao tiếp, được cấp quyền đưa vào hàng đợi tích hợp (Merge Queue) để kiểm thử liên module.
4. **`production_activation_authorized` (Được phép kích hoạt sản xuất):** Gói công việc đã vượt qua các cổng kiểm thử tích hợp thực tế. Trạng thái này hiện tại tiếp tục bị **KHÓA CHẶT** (`PRODUCTION_ACTIVATION_BLOCKED`) theo chốt an toàn toàn cục.

### 3. Điều chỉnh quy định QR-MNT-003 (Amendment to QR-MNT-003)
- **Nội dung điều chỉnh:** Quy định `QR-MNT-003` được chuẩn hóa với cơ chế phân tách phạm vi:
  - Cho phép phát triển song song các work package thuộc các capability khác nhau khi chúng đã được cấp quyền implementation và các contract giao tiếp liên quan đã được đóng băng ở phiên bản cụ thể.
  - Duy trì bắt buộc: Việc chính thức nghiệm thu một phân hệ tổng thể và mở thẩm quyền cho milestone mới vẫn đòi hỏi biên bản kiểm toán độc lập và checkpoint phê duyệt từ người dùng.

### 4. Quy tắc Single-Writer và Kỷ luật Lease
- Mỗi đường dẫn tệp tin (`path`), cấu hình chung (Composition Root), tập tin định nghĩa hợp đồng (`docs/09-contracts/**`), chuỗi migration (`src/**/migrations/**`) và tập tin khóa phụ thuộc (`uv.lock`, `package-lock.json`) chỉ có **DUY NHẤT MỘT writer** tại một thời điểm tích hợp.
- Mọi tương tác ghi chéo giữa các capability phải thông qua caller-owned PostgreSQL Unit of Work và typed ports; tuyệt đối cấm can thiệp trực tiếp vào bảng cơ sở dữ liệu của aggregate khác.

## Điểm bất lợi

- Đòi hỏi kỷ luật cao trong việc định nghĩa và đóng băng các bản hợp đồng giao tiếp (Contract Freeze) trước khi bắt đầu implementation.
- Cần duy trì bộ công cụ kiểm tra tĩnh (DAG Validator) để đảm bảo không phát sinh chu trình phụ thuộc (cycles) hoặc xung đột đường dẫn sở hữu.
- Tăng độ phức tạp của bảng ma trận nghiệm thu (Acceptance Matrix) và kiểm tra phân bổ tài nguyên phần cứng (CPU, GPU, RAM, Database Connections).

## Kiểm chứng

- Kiểm tra tĩnh bằng `docs/parallel-delivery/validate-docs-plan.py` để đảm bảo đồ thị DAG hoàn toàn không có chu trình (acyclic), hợp đồng ánh xạ chính xác và phân quyền đường dẫn không xung đột.
- Mọi thay đổi tài liệu và kế hoạch phải tuân thủ chuẩn UTF-8 đầy đủ dấu tiếng Việt, không có lỗi định dạng trailing whitespace (`git diff --check` đạt Exit Code 0).
- Giữ nguyên các chốt an toàn fail-closed: `M2-P8/P9` duy trì `LOCKED`, `M3` và Phân hệ A duy trì `NOT AUTHORIZED`, và `PRODUCTION_ACTIVATION_BLOCKED` duy trì hiệu lực tuyệt đối.

## Sau này đổi thì thế nào

Nếu cần điều chỉnh đồ thị phụ thuộc hoặc bổ sung capability mới, phải tạo bản đề xuất sửa đổi DAG kèm phân tích tác động trên ma trận nghiệm thu (`acceptance-matrix.yaml`), được Sol-Lead rà soát kỹ thuật và Astra-Lead kiểm toán kiến trúc trước khi áp dụng. Không cho phép tự ý nới lỏng quyền hạn hoặc sửa đổi hợp đồng ngầm bên trong các task của consumer.
