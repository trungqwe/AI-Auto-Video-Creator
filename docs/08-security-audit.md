# Security gate cho tài liệu kiến trúc

**Trạng thái:** PASS ở mức tài liệu; không phải kiểm thử bảo mật hệ thống  
**Ngày:** 12-09-2026  
**Phạm vi:** toàn bộ Markdown trong `docs/` tại thời điểm hoàn tất audit.

## Kết quả

| Nhóm kiểm tra | Kết quả |
|---|---|
| Secret pattern | Không phát hiện giá trị có dạng AWS/GitHub/Slack/Stripe/SendGrid/Twilio/Firebase/JWT/private key trong tài liệu |
| Tệp nhạy cảm | Không phát hiện `.env`, `.key`, `.pem`, `.p12` hoặc tệp credential trong workspace đã liệt kê |
| SQL injection/XSS/CSRF | Chưa có source code, route hoặc form để kiểm tra; kiến trúc yêu cầu validation/schema và không cho AI tạo shell/SQL tùy ý |
| Auth/authorization | Đã tách private network, mTLS, authorization Temporal, device identity và local session/Origin; triển khai phải qua G04/G07 |
| SSRF/path traversal | Đã yêu cầu kiểm tra scheme/DNS/redirect/địa chỉ đích và artifact path allowlist; chưa có implementation để kiểm thử |
| Dependency/CVE | Không có package manifest hoặc mã nguồn; chưa có dependency để audit |
| Destructive operation | Không có script/command triển khai hoặc lệnh xóa dữ liệu trong phạm vi tài liệu |
| Agent state | Không có thư mục `.rune/`; không có state file để chạy integrity scan |

`secret`, `token`, `password`, `api_key` xuất hiện trong tài liệu dưới dạng tên khái niệm/chính sách, không kèm giá trị bí mật. Tên ADR về `secrets` không phải tệp credential.

## Các ràng buộc bảo mật đã được đưa vào kiến trúc

1. Browser không nhận refresh token hoặc database credential; Local Agent không mở cổng Internet.
2. Loopback dùng HTTPS, session bootstrap, Host/Origin và bảo vệ command; không dựa riêng vào CORS.
3. Temporal dùng mTLS và authorization theo vai trò; desktop không có quyền admin/start tùy ý.
4. Cloud giữ Drive refresh token; desktop chỉ dùng access token ngắn hạn trong bộ nhớ theo scope đã kiểm chứng.
5. Secret không nằm trong PostgreSQL nghiệp vụ, Drive artifact, workflow history, log hoặc file cấu hình commit.
6. Crawler chặn truy cập mạng nội bộ/metadata endpoint; media/AI plan không được biến thành shell command hoặc path tùy ý.
7. Backup secret bundle được mã hóa; key phục hồi phải tồn tại ngoài host và ngoài chính bundle.

## Phạm vi chưa thể kiểm tra

Chưa thể kiểm tra secret leak khi runtime lỗi, SQL parameterization, XSS, CSRF, cookie flags, TLS/certificate, filesystem ACL, OAuth scope, dependency CVE hoặc container hardening vì chưa có implementation. G04/G07 và security scan trước commit/deploy là hard gate tương lai; báo cáo PASS này không đóng các gate đó.

## Tệp đã kiểm tra

- `docs/00-project-charter.md`
- `docs/01-product-spec.md`
- `docs/02-data-model.md`
- `docs/03-quality-requirements.md`
- `docs/05-technology-research.md`
- `docs/06-system-map.md`
- `docs/07-data-flow.md`
- `docs/08-architecture.md`
- `docs/08-architecture-audit.md`
- `docs/08-architecture-red-team.md`
- `docs/08-security-audit.md`
- `docs/adr/README.md`
- `docs/adr/0001-hybrid-modular-monolith.md`
- `docs/adr/0002-authoritative-data-and-search.md`
- `docs/adr/0003-durable-workflow-engine.md`
- `docs/adr/0004-commit-idempotency-and-fencing.md`
- `docs/adr/0005-snapshots-and-content-invariants.md`
- `docs/adr/0006-drive-artifacts-and-local-journal.md`
- `docs/adr/0007-runtime-and-admin-ui.md`
- `docs/adr/0008-ai-routing-and-quota.md`
- `docs/adr/0009-trust-boundaries-and-secrets.md`
- `docs/adr/0010-storage-lifecycle-and-recovery.md`
- `docs/adr/0011-observability-capacity-and-cost.md`
- `docs/adr/0012-evolution-and-saas-boundary.md`

## Verdict

Không có `BLOCK` hoặc `WARN` trong nội dung tài liệu hiện tại. Có các mục `INFO` do chưa tồn tại implementation/dependency; chúng đã được chuyển thành gate kiểm chứng, không bị coi là đã pass production security.
