# 11. Hợp đồng cấu hình, tài khoản, quota và bảo mật

> Trạng thái: **Bản thiết kế trước triển khai**  
> Chủ sở hữu: J.  
> Consumers: A-G và H qua các view/handle giới hạn.

## 1. Ranh giới trách nhiệm

J sở hữu:

- config/prompt/policy revision;
- external account metadata;
- secret references và credential lifecycle;
- provider/model/role routing;
- quota/capacity observations;
- project cost accounting;
- capability health projection.

J không sở hữu secret thô trong log/event/config document có thể đọc rộng.

## 2. Cấu hình có phiên bản

### CT-CFG-001 — `PublishConfigurationRevision`

Input:

- scope `workspace`, `module`, `provider`, `preset`, `policy` hoặc `prompt`;
- base revision;
- typed configuration payload;
- effective rule;
- actor và change reason.

Output:

- immutable config revision;
- validation result;
- fingerprint;
- effective time/scope;
- superseded revision ref.

Bất biến:

- Job chưa bắt đầu tạo script có thể dùng revision mới, kể cả trong batch đang chạy.
- Job đã commit production snapshot giữ revision cũ.
- Thay đổi không sửa revision tại chỗ.
- UI hiển thị revision áp dụng cho từng job.

### CT-CFG-002 — `ResolveConfigurationBundle`

Input:

- workspace/job/stage refs;
- evaluation time;
- required config capabilities;
- snapshot state.

Output:

- exact config/prompt/policy/preset revision refs;
- merged typed values;
- bundle fingerprint;
- provenance của mỗi giá trị;
- validation warnings.

Không trả secret value trong bundle.

## 3. Secret và credential

### CT-SEC-001 — `UpdateSecret`

Secret value chỉ được gửi qua kênh được bảo vệ tới secret store. Response chỉ gồm:

- secret reference/alias;
- provider/account ref;
- last updated time;
- validation state;
- fingerprint đã che hoặc version;
- actor audit.

Không có API đọc lại secret value.

### CT-SEC-002 — `IssueShortLivedCredential`

Desktop/worker nhận credential ngắn hạn, giới hạn scope và operation. Google Drive refresh token dài hạn ở cloud; desktop không lưu refresh token.

Handle/credential có:

- audience và capability;
- workspace/account scope;
- issued/expiry time;
- operation/job binding nếu có;
- revocation/version;
- least-privilege permissions.

Secret/credential không được đưa vào Temporal history, event, trace, log, prompt hoặc error detail.

## 4. Tài khoản ngoài

### CT-ACC-001 — `ExternalAccountView`

| Trường | Ý nghĩa |
|---|---|
| `external_account_id` | Identity nội bộ |
| `provider` | Gemini, Google Drive hoặc provider khác |
| `account_label` | Nhãn quản trị |
| `status` | enabled, disabled, degraded, revoked, invalid |
| `project_ref` | API project/quota domain nếu có |
| `capabilities` | Vai trò được phép |
| `quota_observation_ref` | Snapshot quota gần nhất |
| `credential_metadata` | Có/không, expiry/update; không có secret |
| `health` | Kết quả test gần nhất |

### CT-ACC-002 — `TestExternalAccount`

Test có operation receipt, dùng request nhỏ nhất cần thiết và trả kết quả đã redacted. Test không được tự bật account hoặc thay routing.

## 5. Provider routing

### CT-AI-ROUTE-001 — `ResolveProviderRoute`

Input:

- AI role/capability;
- job/snapshot/config refs;
- data sensitivity;
- quality/latency/cost bounds;
- current health/quota;
- allowed cloud/local fallback list.

Output:

- selected provider/model/account/project refs;
- route revision và rationale codes;
- allowed fallback order;
- capacity reservation ref;
- credential acquisition method;
- estimated incremental cost class.

Pool 4 tài khoản có thể chia theo vai trò hoặc batch, nhưng routing phải dựa trên quota domain thực tế. Không mặc định bốn tài khoản tạo bốn quota độc lập.

### CT-AI-ROUTE-002 — Fallback

- Công việc không cần AI vẫn chạy khi AI unavailable.
- Stage AI chờ provider phục hồi hoặc desktop online cho local fallback được cấu hình.
- Không tự thêm dịch vụ trả phí.
- Fallback có thể thay model nhưng phải ghi model/prompt/config revision và chạy validation tương ứng.
- Nếu fallback làm thay đổi intent sau snapshot ngoài policy, phải tạo output revision mới hoặc chờ; không âm thầm thay.

## 6. Quota và capacity

### CT-CAP-001 — `ProviderCapacitySnapshot`

Ghi theo provider/model/project/account và capability:

- observed limits nếu biết;
- request/token/storage usage;
- reset window;
- rate-limit/backoff state;
- health/latency/error rate;
- confidence/source của số liệu;
- observed time/expiry.

Không suy quota từ số tài khoản đơn thuần. Dữ liệu quota không chắc phải có confidence và không được dùng như guarantee.

### CT-CAP-002 — `ReserveProviderCapacity`

Reservation là hint điều phối có expiry, không phải cam kết từ provider. G phải xử lý rate limit thực tế bằng waiting/backoff, không tạo storm retry.

## 7. Chi phí

### CT-COST-001 — `RecordIncrementalCost`

Chỉ tính chi phí phát sinh thêm cho dự án:

- API/dịch vụ trả thêm;
- dịch vụ chạy nền;
- lưu trữ bổ sung;
- các khoản trực tiếp khác được cấu hình.

Không tính gói Gemini/Drive đã có, điện, Internet và phần cứng theo quyết định user.

Record gồm provider/service, operation/job/batch refs, quantity/unit, estimated/actual cost, currency, source và time. Mục tiêu dưới 50 USD/tháng là quality/cost gate, không phải guarantee của một operation riêng.

## 8. Capability health

### CT-CAP-003 — `CapabilityView`

Capability có:

- capability ID/type;
- cloud/desktop/provider location;
- status `available`, `degraded`, `unavailable`, `unknown`;
- compatible activity/tool/model versions;
- capacity indicators;
- last heartbeat/observation;
- reason và next check.

G dùng capability view để chuyển waiting/resume. Worker heartbeat không tự cấp quyền thực thi nếu không có execution grant.

## 9. Biên bảo mật

### CT-SEC-003 — Trust rules

1. Mọi caller được xác thực và ràng buộc workspace.
2. Local agent kết nối cloud qua kênh xác thực; cloud không tin device chỉ theo hostname.
3. Workflow UI/worker endpoint không để public không kiểm soát; dùng private network, mTLS/authorization theo kiến trúc.
4. URL ngoài qua SSRF validation, giới hạn redirect/protocol/address range.
5. File path từ AI/UI không được đưa trực tiếp vào shell.
6. Error/log redaction được áp dụng trước persistence và stream.
7. Credential bị revoke có hiệu lực cao hơn snapshot cũ; job chuyển waiting/failure phù hợp, không dùng secret đã revoke.

## 10. Audit

### CT-SEC-004 — `AuditRecord`

Các thao tác bắt buộc audit:

- thay config/prompt/policy/preset;
- thêm/tắt/xóa/khôi phục nguồn;
- nhập/sửa metadata hook;
- cập nhật/test/enable/disable account và secret;
- chạy debug/retry/tạo biến thể;
- cleanup/restore/recovery;
- xem technical detail hoặc thao tác nhạy cảm.

Audit record có actor, action, resource/revisions trước-sau, time, correlation, outcome và redacted reason; không chứa secret value.

## 11. Acceptance contract

1. UI không đọc lại secret đã lưu.
2. Desktop không giữ Drive refresh token dài hạn.
3. Job snapshot dùng đúng config revision dù config thay trong batch.
4. Pool tài khoản được điều phối theo quota/project thực, không theo giả định.
5. AI unavailable không dừng công việc không cần AI và không tự mua dịch vụ.
6. Mọi thay đổi cấu hình/tài khoản nhạy cảm có audit trail.

