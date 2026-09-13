# ADR-0012: Nâng cấp lâu dài và ranh giới SaaS

**Trạng thái:** Accepted - chuẩn bị thiết kế, chưa triển khai nhiều tenant  
**Căn cứ:** QR-MNT-001/002/003/005/006, QR-SCALE-004/005; ARCH-014.  
**Liên quan:** [ADR-0001](./0001-hybrid-modular-monolith.md), [ADR-0009](./0009-trust-boundaries-and-secrets.md).

## Tại sao phải quyết định

Job có thể kéo dài qua nhiều lần phát hành. Người dùng muốn phát triển thành SaaS về sau nhưng chưa có yêu cầu billing/tenant identity cụ thể. Tránh gắn credential global và tránh phá workflow cũ là việc cần làm ở thiết kế hiện tại.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Single-user hard-code toàn bộ | Nhanh lúc đầu | Khó tách config/account/data khi mở rộng |
| Full SaaS ngay | Nhiều tenant/role/billing sẵn | Tự bổ sung phạm vi, chi phí và rủi ro chưa được yêu cầu |
| Workspace boundary tối thiểu và versioned contracts | Giữ đường mở rộng, phù hợp v1 | Vẫn cần thiết kế/thử cách ly thật khi mở SaaS |

## Chọn cái gì và tại sao

Chọn một workspace mặc định ở v1. ID sở hữu, query scope, unique key, cache, secret lookup, provider quota và StorageArea mapping đều xét workspace. Không dùng global singleton cho cấu hình có thể thuộc khách hàng. Tenant ID không tự tạo isolation; chưa cho onboarding khách hàng khác.

Không xây billing/RBAC/public signup/subscription trong v1. Cấu hình API được quản lý qua J để sau này đổi sang nền tảng cấp key hoặc khách hàng tự mang key, chưa chốt mô hình kinh doanh đó.

Quản lý thay đổi theo artifact/contract version:

1. Pin runtime/server/SDK/DB/extension/FFmpeg/model/font và lưu build manifest; chọn tổ hợp còn được hỗ trợ sau kiểm chứng, không lấy nhãn latest làm quyết định.
2. Schema dùng expand-contract: thêm phần tương thích trước, migrate/backfill, chuyển reader/writer rồi mới loại phần cũ khi job cũ hết phụ thuộc.
3. Workflow code deterministic phải replay được history đang sống; giữ worker tương thích hoặc version routing. Pin package không tự bảo đảm replay.
4. Desktop báo capability/build; cloud không cấp việc yêu cầu contract chưa hỗ trợ. Bản cũ giữ hàng chờ và trạng thái nâng cấp, không bỏ job.
5. Prompt/preset/model revision không ghi đè kết quả đã dùng. Rollback application không được âm thầm rollback dữ liệu đã migrate không tương thích.

Quy tắc module A-J giữ nguyên: F sở hữu preset/schema render; J giữ cấu hình chọn; D chọn nội dung. Tách service sau này không đổi ownership nghiệp vụ.

## Điểm bất lợi

Giữ nhiều version trong giai đoạn chuyển tiếp tăng test, dung lượng và quy trình phát hành. Cần code review boundary và migration discipline; không có cam kết “lên SaaS không phải sửa gì”. Đổi trust model sang thiết bị của khách là thay đổi lớn.

## Kiểm chứng

G01/G07: replay history trước upgrade, migration có dữ liệu thật, desktop version cũ kết nối cloud mới, rollback rehearsal và artifact cũ còn đọc được. SaaS sau này bắt buộc kiểm thử cross-workspace data/secret leak trước public deployment.

Giữ QR-MNT-003: triển khai từng phân hệ vẫn theo trình tự và xác nhận đã thống nhất với người dùng. Việc ủy quyền ghi ADR không tự xóa quy tắc nghiệm thu phân hệ.

## Sau này đổi thì thế nào

Đổi tenant model/auth/provider-key ownership tạo ADR mới và migration dữ liệu cụ thể. Tách repo/service chỉ khi có owner hoặc chu kỳ release độc lập; giữ contract version và một writer cho mỗi miền dữ liệu. Không xóa lịch sử ADR: đánh dấu `Superseded`, liên kết quyết định thay thế và ghi hậu quả chuyển đổi.
