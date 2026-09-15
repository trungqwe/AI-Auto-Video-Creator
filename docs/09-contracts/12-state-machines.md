# 12. Máy trạng thái liên phân hệ

> Trạng thái: **Bản thiết kế trước triển khai**  
> Mục tiêu: loại bỏ trạng thái mơ hồ và ngăn mỗi phân hệ tự diễn giải vòng đời khác nhau.

## 1. Quy tắc chung

- Chỉ owner aggregate được commit chuyển trạng thái.
- Mỗi chuyển trạng thái có command/event nguyên nhân, expected revision và actor.
- Trạng thái terminal không mở lại tại chỗ; retry/regenerate tạo attempt/revision phù hợp.
- `WAITING` khác `FAILED`; `OUTCOME_UNKNOWN` khác cả hai.
- UI label tiếng Việt là projection; enum English dưới đây là contract ổn định.

## 2. Source

### CT-STATE-001

`ACTIVE` ↔ `DISABLED` → `REMOVED_TOMBSTONE`

Từ tombstone chỉ `RestoreSource` hợp lệ. Restore về trạng thái trước remove nếu policy còn cho phép; nếu không về `DISABLED` kèm lý do. Source removed không được auto-discovery tạo mới.

## 3. Collection cycle/run

### CT-STATE-002

Cycle: `PLANNED` → `RUNNING` → `COMPLETED` | `COMPLETED_PARTIAL` | `FAILED`

Run:

- `SCHEDULED` → `RUNNING`;
- `RUNNING` → `WAITING_RETRY` → `RUNNING`;
- `RUNNING` → `WAITING_RECONCILIATION` → `RUNNING` hoặc trạng thái terminal sau reconcile;
- `RUNNING` → `COMPLETED` | `COMPLETED_PARTIAL` | `FAILED_FINAL`.

`CollectionAttempt` ghi kết quả `SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_FINAL` hoặc `OUTCOME_UNKNOWN`. Unknown chưa phải bằng chứng kết thúc side effect: giữ observation gốc và append reconciliation result/evidence, không sửa mất lịch sử. Run projection dùng kết quả đã reconcile. Nguồn không được chọn do đủ ngưỡng có `CollectionDecision=SKIPPED_SUFFICIENT`; không tạo run giả.

| Trạng thái/điều kiện | Chuyển trạng thái run |
|---|---|
| RUNNING, attempt retryable, nguồn còn bật và còn retry budget | WAITING_RETRY; khi đến hạn tạo attempt mới trong cùng run rồi RUNNING |
| RUNNING hoặc WAITING_RETRY, hết budget/deadline hoặc nguồn disabled/removed | COMPLETED_PARTIAL nếu đã có document package hợp lệ được commit; nếu chưa có thì FAILED_FINAL; reason RETRY_EXHAUSTED hoặc SOURCE_INACTIVE |
| SCHEDULED, nguồn không còn được phép chạy | FAILED_FINAL với SOURCE_INACTIVE; không tạo attempt giả |
| RUNNING, side effect chưa biết kết quả | WAITING_RECONCILIATION; không retry hoặc kết thúc như thể side effect chưa xảy ra |
| WAITING_RECONCILIATION, reconcile xác nhận retryable | WAITING_RETRY nếu nguồn/budget cho phép; nếu không thì terminal partial/final theo hàng trên |
| WAITING_RECONCILIATION, xác nhận toàn bộ công việc xong | COMPLETED; giữ dữ liệu đã commit dù nguồn hiện bị tắt |
| WAITING_RECONCILIATION, xác nhận lỗi cuối hoặc thành công một phần nhưng không được tiếp tục | COMPLETED_PARTIAL nếu đã commit package hợp lệ, ngược lại FAILED_FINAL |
| WAITING_RECONCILIATION, xác nhận side effect xong nhưng còn công việc và được phép tiếp tục | RUNNING qua checkpoint an toàn; không lặp side effect vừa xác nhận |

Mọi quyết định terminal ghi policy revision, reason và checkpoint; không mở lại terminal. Chỉ FAILED_FINAL là lỗi terminal của run; partial không xóa kết quả đã commit. Retry count/deadline cụ thể vẫn là cấu hình phải khóa trước production. Reconcile chưa có bằng chứng vẫn WAITING_RECONCILIATION; hết thời gian reconcile thì log/cảnh báo và chờ phục hồi có bằng chứng, không retry mù hoặc bịa terminal thành công. Cycle chỉ terminal khi mọi run đã terminal; có run bị dừng/lỗi và có kết quả thì COMPLETED_PARTIAL, không có kết quả thì FAILED; mọi run hoàn tất bình thường thì COMPLETED.

### CT-STATE-002A — Source candidate

`DISCOVERED` → `VALIDATING` → `READY_FOR_REGISTRATION` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`

`READY_FOR_REGISTRATION` → `REGISTERED` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED` sau kiểm tra lại nguyên tử tại registration theo CT-SRC-003A. Thiếu policy giữ READY với WAITING_POLICY; policy cấm trả REJECTED. Expected revision cũ trả conflict không chuyển trạng thái. `MATCHED_EXISTING`, `BLOCKED_TOMBSTONE`, `REJECTED` và `REGISTERED` là terminal cho cùng candidate observation; phát hiện mới tạo candidate mới nhưng vẫn phải đối chiếu source/tombstone hiện hành.

## 4. Collected document resolution

### CT-STATE-003

`RECEIVED` → `NORMALIZING` → `RESOLVING_IDENTITY` → một trong:

- `NEW_ARTICLE_ACCEPTED`;
- `NEW_REVISION_ACCEPTED`;
- `DUPLICATE_MEDIA_ONLY`;
- `DUPLICATE_NO_NEW_VALUE`;
- `REJECTED_INCOMPLETE`;
- `FAILED_RETRYABLE`;
- `FAILED_FINAL`.

Các disposition terminal không được đổi hồi tố; quan sát mới tạo collected document mới.

Payload sai schema/thiếu định danh bắt buộc bị từ chối tại biên CT-SRC-006 trước RECEIVED; không có document resolution giả. Package hợp lệ về cấu trúc nhưng thiếu nội dung mới đi vào REJECTED_INCOMPLETE.

## 5. Event link/update

### CT-STATE-004

Event link candidate: `PROPOSED` → `LINKED` | `KEPT_SEPARATE` | `NEEDS_MORE_EVIDENCE`.

Event update candidate: `PROPOSED` → `ACCEPTED_NEW_DEVELOPMENT` | `REJECTED_REPOST` | `REJECTED_NO_NEW_FACT` | `UNCERTAIN`.

Chỉ `ACCEPTED_NEW_DEVELOPMENT` cấp điều kiện cho narrative “từ lúc đó đến nay”.

## 6. Media acquisition và rendition

### CT-STATE-005

Media discovery: `DISCOVERED` → `ACQUIRING` → `CATALOGED` | `FAILED`.

Rendition: `DECLARED` → `PROCESSING` → `READY` | `FAILED` | `OUTCOME_UNKNOWN`.

Availability là trục riêng: `AVAILABLE`, `MISSING`, `CORRUPT`, `RECOVERING`, `UNAVAILABLE_SOURCE`. Không trộn availability với safety.

## 7. Image safety

### CT-STATE-006

`NOT_ASSESSED` → `ASSESSING` → `SAFE` | `TRANSFORM_REQUIRED` | `UNCERTAIN` | `DETECTION_FAILED` | `UNREADABLE`.

Nếu cần transform: `TRANSFORM_REQUIRED` → `TRANSFORMING` → `PROCESSED_READY` | `TRANSFORM_FAILED`.

`UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED` có thể `usable_with_warning` nếu ảnh đọc được. Không ánh xạ chúng thành `SAFE`.

## 8. Production snapshot và creative outputs

### CT-STATE-007

Snapshot: `BUILDING` → `COMMITTED` | `REJECTED`.

Script/plan revision: `GENERATING` → `VALIDATING` → `READY` | `REJECTED` | `FAILED`.

Revision `READY` là immutable. Tạo lại sinh revision mới; không có trạng thái user-approved trong v1.

VariantReservation (G, CT-ORC-012): tạo ACTIVE nguyên tử sau validation hợp lệ; ACTIVE → CONVERTED khi completion hoặc RELEASED khi job terminal lỗi/hủy. WAITING/retry/lease hết hạn không release. Stale validation giữ job/reservation hiện tại và đối chiếu lại; conflict thực kết thúc job FAILED_FINAL, biến thể khác dùng job mới. Hai trạng thái cuối không mở lại.

## 9. Stage run

### CT-STATE-008

`PENDING` → `WAITING_DEPENDENCY` | `WAITING_CAPABILITY` | `RUNNING`

Từ `RUNNING`:

- → `SUCCEEDED`;
- → `FAILED_RETRYABLE`;
- → `FAILED_FINAL`;
- → `OUTCOME_UNKNOWN`;
- → `STALE` khi generation không còn hiệu lực.

`OUTCOME_UNKNOWN` → `SUCCEEDED` | `FAILED_RETRYABLE` | `FAILED_FINAL` sau reconcile. Không retry side effect trực tiếp từ `OUTCOME_UNKNOWN`.

Không có cạnh contract từ `WAITING_DEPENDENCY`, `WAITING_CAPABILITY` hoặc `FAILED_RETRYABLE` trong state machine này. Không tự suy diễn recovery/retry edge từ các trạng thái đó.

## 10. Video job

### CT-STATE-009

Các cạnh hợp lệ duy nhất:

- `CREATED` → `SNAPSHOTTED`;
- `SNAPSHOTTED` → `ACTIVE`;
- `ACTIVE` → `WAITING`;
- `WAITING` → `ACTIVE`;
- `ACTIVE` → `READY_FOR_COMPLETION`;
- `WAITING` → `READY_FOR_COMPLETION`;
- `READY_FOR_COMPLETION` → `COMPLETED`;
- `ACTIVE` | `WAITING` | `READY_FOR_COMPLETION` → `FAILED_FINAL`.

- Job retry kỹ thuật không rời identity hiện tại.
- `COMPLETED` và `FAILED_FINAL` là terminal. Không terminal nào mở lại; biến thể mới là job mới.
- `READY_FOR_COMPLETION` yêu cầu render/QC đạt nhưng chưa chắc đã sync/commit.

## 11. Production batch

### CT-STATE-010

Các cạnh hợp lệ duy nhất:

- `CREATED` → `RUNNING`;
- `RUNNING` → `WAITING_CAPABILITY`;
- `WAITING_CAPABILITY` → `RUNNING`;
- `RUNNING` → `COMPLETED_TARGET` | `COMPLETED_EXHAUSTED` | `FAILED_SYSTEM`;
- `WAITING_CAPABILITY` → `COMPLETED_TARGET` | `COMPLETED_EXHAUSTED` | `FAILED_SYSTEM`.

`COMPLETED_TARGET`, `COMPLETED_EXHAUSTED` và `FAILED_SYSTEM` là terminal; không có cạnh khác.

Job riêng lẻ `FAILED_FINAL` không buộc batch `FAILED_SYSTEM`.

## 12. Operation receipt

### CT-STATE-011

Các cạnh hợp lệ duy nhất:

- `PREPARED` → `STARTED`;
- `STARTED` → `SUCCEEDED` | `FAILED` | `OUTCOME_UNKNOWN`;
- `OUTCOME_UNKNOWN` → `SUCCEEDED` | `FAILED` chỉ sau reconciliation evidence.

Nếu reconcile vẫn chưa xác định được kết quả, operation giữ `OUTCOME_UNKNOWN`; không bịa transition. Không có retry/re-execution trực tiếp từ `OUTCOME_UNKNOWN`. `SUCCEEDED` và `FAILED` đều terminal cho cùng operation key/input fingerprint; không state terminal nào mở lại `STARTED`, và không có self-transition. Retry/re-attempt được phép dùng attempt/revision mới phù hợp, không mở lại terminal.

## 13. Artifact location

### CT-STATE-012

`DECLARED` → `MATERIALIZING` → `AVAILABLE_UNVERIFIED` → `VERIFYING` → `VERIFIED` | `CORRUPT` | `MISSING` | `OUTCOME_UNKNOWN`

Từ `VERIFIED`: → `CLEANUP_ELIGIBLE` → `CLEANUP_AUTHORIZED` → `DELETED`. `VERIFIED` cũng có thể → `MISSING` khi lần verify sau phát hiện location mất.

Location có thể bị đánh `MISSING` sau lần verify trước; artifact version vẫn tồn tại logic và có thể có location khác. Không có recovery edge P4 từ `MISSING`, `CORRUPT` hoặc `OUTCOME_UNKNOWN`, và không có cleanup shortcut.

## 14. Configuration và external account

### CT-STATE-013

ConfigRevision có đúng các cạnh sau: `DRAFT → PUBLISHED`; `PUBLISHED → SUPERSEDED`; và `DRAFT | PUBLISHED | SUPERSEDED → INVALIDATED` khi owner J xác nhận security defect. `INVALIDATED` là terminal. `SUPERSEDED` không terminal tuyệt đối: không có cạnh nghiệp vụ thường nào đi ra, nhưng vẫn có cạnh security-invalidation tường minh đến `INVALIDATED` để lưu sự kiện security của revision lịch sử. Mọi cạnh không được liệt kê đều bị cấm, gồm `DRAFT → SUPERSEDED`, `SUPERSEDED → PUBLISHED`, `INVALIDATED → *`, mọi self-transition và mọi cạnh từ `DRAFT`/`PUBLISHED` khác các cạnh nêu trên. Cạnh cấm trả `FORBIDDEN_TRANSITION` và không có side effect.

Security invalidation không sửa payload, content hash, identity hay revision của ConfigRevision bất biến; nó chỉ commit state/audit/evidence security theo owner J. Job phụ thuộc phải chờ hoặc đánh giá lại theo policy. ExternalAccount tiếp tục là aggregate riêng; graph dưới đây không cấp quyền mở rộng lifecycle account.

External account: `DISABLED` ↔ `ENABLED` → `DEGRADED` | `INVALID` | `REVOKED`.

`REVOKED` là terminal cho credential version; account có thể được kích hoạt bằng credential version mới, không hồi sinh secret cũ.

## 15. Bảng quyền chuyển trạng thái

| Aggregate | Owner | Caller được yêu cầu | Bằng chứng bắt buộc |
|---|---|---|---|
| Source | A | H/G | command + expected revision |
| Article/Event | B | A/D/G | document/evidence refs |
| Media/Hook | C | A/B/D/E/H | provenance/output refs |
| Creative outputs | D | G | snapshot + AI invocation/validation |
| Processing output | E/C/I | G | grant + artifact/report refs |
| Render/QC | F | G | package + attempt/evidence |
| Batch/Job/Stage/Ledger | G | H/workflow/workers | grant/result/completion evidence |
| Artifact location | I | C/E/F/G | operation receipt + hash/verify |
| Config/Account | J | H/G | command + audit + validation |

## 16. Acceptance contract

1. Mọi status trên UI ánh xạ về đúng một enum và owner.
2. Không có transition từ completed về running.
3. Không đồng nhất waiting, failed và outcome unknown.
4. Mọi terminal state có reason/evidence.
5. State transition không hợp lệ trả `FORBIDDEN_TRANSITION` và không có side effect.
