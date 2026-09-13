# ADR-0008: AI theo vai trò, quota chung và fallback

**Trạng thái:** Conditional - chưa có model/provider bundle vượt G03/G04/G06  
**Căn cứ:** R09/R16/R18/R19/R20, QR-MNT-006, QR-SEC-009, QR-COST-003; ARCH-012.  
**Liên quan:** [ADR-0005](./0005-snapshots-and-content-invariants.md), [ADR-0009](./0009-trust-boundaries-and-secrets.md).

## Tại sao phải quyết định

Dùng nhiều tài khoản không tự tạo quota độc lập hoặc fallback hợp lệ. Cloud vẫn phải chạy khi desktop tắt; script/plan/voice chỉ bắt đầu khi desktop hoạt động. AI có thể trả dữ liệu khác khi retry và có thể tính phí dù client không nhận kết quả.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Gọi SDK trực tiếp từ từng module | Nhanh lúc đầu | Rải credential/retry, khó thay model và giữ quota chung |
| Gateway service riêng | Routing tập trung, dễ nhiều provider | Thêm dịch vụ và failure domain sớm |
| Port nội bộ theo vai trò + adapter worker | Cô lập provider, giữ typed contract, ít dịch vụ | Phải thiết kế capability và quota coordination |

## Chọn cái gì và tại sao

Chọn port nội bộ cho phân tích nội dung, lập chỉ mục, script, TTS, vision và embedding. D/E/B/C giữ ý nghĩa kết quả; J giữ account/policy/secret reference và quota. Worker tại nơi phù hợp gọi adapter, không đưa raw credential vào workflow.

Quota coordination đặt trên cloud, scope theo provider/project/model và account nếu provider áp dụng. Gemini quota tính theo project, không theo API key; nhiều key cùng project chia cùng bộ giới hạn. [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

Cloud AI lỗi khi desktop tắt: công việc không cần AI tiếp tục, việc AI chờ. Khi desktop online có thể route sang local adapter đã qua kiểm chứng. Script/plan/voice được desktop worker khởi chạy nhưng vẫn có thể dùng API từ xa. Không tự thêm provider trả phí hoặc coi tài khoản Gemini Pro là chứng cứ API đã có.

Job giữ policy/model role revision khi snapshot. Provider thực, model build, prompt/schema version và usage ghi ở mỗi accepted result. Revocation áp dụng ngay; không gọi secret cũ vì snapshot. Fallback dùng policy đã giữ; đổi voice cần timing/timeline/QC mới.

AI response qua schema và domain validation, có provenance/inference marker. Nội dung cào là dữ liệu không tin cậy; không cho nó thay chỉ thị hệ thống, gọi tool, lấy secret hay sửa cấu hình. Render plan AI không được trở thành shell command tùy ý.

## Điểm bất lợi

Typed output không chứng minh nội dung đúng. Request fingerprint không bảo đảm provider exactly-once. Với response mất, ghi outcome unknown, tìm receipt nếu provider hỗ trợ, rồi retry giới hạn theo policy; usage chưa biết không ghi bằng 0. Chờ dịch vụ có thể giảm sản lượng và không đạt thời gian mong muốn dù không mất job.

## Kiểm chứng

G04 kiểm tra entitlement/quota thật; G06 chọn model/TTS/local fallback từ bộ mẫu và máy 12 GB VRAM. G03 đo token, giá/usage thực, retry và số giờ chạy tháng. Giữ cảnh báo dự báo 80%; không tự hard-stop runtime vì ngân sách khi người dùng chưa cấu hình.

## Sau này đổi thì thế nào

Thêm/thay adapter sau benchmark cùng bộ mẫu, license model/voice và capability contract. Có thể tách gateway thành service khi quota/routing nhiều worker chứng minh cần thiết. Giữ result version, snapshot và cost ledger; không đổi model rồi coi vector/voice/script cũ tương thích mặc định.
