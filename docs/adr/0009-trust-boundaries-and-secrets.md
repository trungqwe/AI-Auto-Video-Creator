# ADR-0009: Ranh giới truy cập và vòng đời bí mật

**Trạng thái:** Accepted - yêu cầu thiết kế; cấu hình thực phải qua G04/G07  
**Căn cứ:** QR-SEC-001 tới QR-SEC-009; R14/R16/R19; ARCH-013.  
**Liên quan:** [ADR-0006](./0006-drive-artifacts-and-local-journal.md), [ADR-0012](./0012-evolution-and-saas-boundary.md).

## Tại sao phải quyết định

Browser, agent, cloud workers, Temporal và bốn tài khoản có quyền khác nhau. Người dùng không muốn đăng nhập UI cục bộ; điều đó không cho phép website khác ra lệnh cho agent hoặc cho mọi worker quyền admin.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Public service + một shared token | Ít bước cấu hình | Quyền quá rộng, khó thu hồi từng máy và cô lập |
| Private network + identity theo vai trò | Phù hợp một chủ vận hành, kiểm soát đường truy cập | Phải vận hành network/certificate/secret lifecycle |
| Full IAM/Vault/SaaS identity ngay | Quản trị tập trung mạnh | Thêm chi phí và scope khi chưa có nhiều người dùng |

## Chọn cái gì và tại sao

Chọn private network cho desktop/cloud; không public PostgreSQL, Temporal UI hoặc cổng admin. Cơ chế mạng riêng cụ thể chốt ở triển khai, chưa cài VPN. Kênh tới API dùng HTTPS/device identity; Temporal dùng mTLS và authorization theo vai trò, desktop chỉ quyền worker cần thiết. Temporal tách mTLS khỏi ClaimMapper/Authorizer, nên mã hóa kết nối chưa đủ để suy quyền API. [Temporal security](https://docs.temporal.io/self-hosted-guide/security).

Local Agent phục vụ UI trên loopback HTTPS, bootstrap phiên tự động để không thêm màn đăng nhập. Kiểm tra session/Host/Origin và command protection chống website khác; không xem CORS hoặc bind loopback là đủ. Browser không giữ provider refresh token; preview chỉ đọc tệp được manifest cho phép.

Crawler kiểm tra HTTP(S), DNS và redirect để chặn loopback/private/link-local/metadata endpoint; nguồn web không được đọc cloud control network. Plan AI chỉ tham chiếu artifact và tham số trong allowlist, không là shell command/đường dẫn tùy ý. Process giải mã/render cần giới hạn tài nguyên và không được cấp secret không cần thiết.

Desktop giữ secret nhỏ trong Windows Credential Manager; bundle/private key lớn được DPAPI theo tài khoản OS bảo vệ cùng ACL. DPAPI gắn việc giải mã với ngữ cảnh Windows phù hợp; cần kiểm chứng khi đổi account/máy. [Microsoft CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).

Cloud giữ encrypted secret bundle có version và ACL trên volume riêng; root key cấp ngoài DB/image. Database/workflow/log giữ reference, không giữ secret thô. Upload session URI cũng được xử lý như bí mật. Thay key, thu hồi và health là use case của J.

J cloud sở hữu Drive refresh token, serialize refresh theo account/client. Desktop chỉ xin access token ngắn hạn để truyền byte trực tiếp; token ở bộ nhớ và quyền thực theo OAuth scope. Không tuyên bố token chỉ dùng được cho một file nếu Google không cấp quyền như vậy. Consent/refresh phải thử khi desktop tắt; External/Testing có giới hạn refresh token bảy ngày trong trường hợp Google nêu. [OAuth lifecycle](https://developers.google.com/identity/protocols/oauth2#expiration).

## Điểm bất lợi

Private network, TLS, local certificate và token rotation tăng công sức vận hành. Desktop được tin cậy trong phạm vi một người dùng và vẫn có thể dùng access token theo scope được cấp. Thiết kế này chưa đủ cho desktop không tin cậy của khách SaaS.

Mất key có thể làm secret/backup không giải mã được. Khóa phục hồi phải giữ ngoài host và ngoài bundle mã hóa; không ghi secret vào ADR hoặc repo.

## Kiểm chứng

G04: credential revoked, token expiry, cloud refresh khi desktop tắt, role worker không gọi admin, cross-origin request tới local agent, log/error không lộ token. G07 kiểm tra certificate provisioning và compatibility. Chưa có kiểm thử tấn công hoặc audit hạ tầng thực tế.

## Sau này đổi thì thế nào

Thay secret store qua port của J, giữ secret reference và version; đổi quyền phải migrate/re-authorize OAuth khi cần. Khi SaaS, thiết kế lại identity/tenant/token delivery theo threat model của nhiều khách hàng trước khi mở public endpoint. Không mang shared cloud credential sang browser hoặc desktop của khách.
