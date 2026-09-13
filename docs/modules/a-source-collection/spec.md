# Phân hệ A — Nguồn và thu thập nội dung

**Tên kỹ thuật nhất quán:** `a-source-collection`  
**Trạng thái:** Đã được user phê duyệt làm baseline; implementation vẫn bị khóa đến sau M1/M2 và checkpoint tương ứng  
**Ngày lập:** 12-09-2026  
**Owner nghiệp vụ:** Phân hệ A  
**Tiến trình mục tiêu:** cloud worker `source_ingestion` theo kiến trúc hiện hành  
**Phạm vi:** chỉ phân hệ đầu tiên; không đặc tả cách triển khai B-J

## 1. Mục đích

Phân hệ A duy trì danh sách nguồn và biến dữ liệu quan sát được từ Internet thành các gói đầu vào có thể truy vết cho kho nội dung và kho media.

Phân hệ phải:

- tiếp tục thu thập khi desktop render offline;
- ưu tiên nguồn theo Tier và ngưỡng tin mới không trùng của từng chủ đề;
- cô lập lỗi từng nguồn;
- bảo toàn provenance và bằng chứng fetch;
- phân biệt lượt quét định kỳ với tìm bổ sung cho một video;
- không tự quyết định một bài là tin mới, bài trùng, diễn biến mới hoặc sự thật đã kiểm chứng.

## 2. Nguồn yêu cầu

Đặc tả này kế thừa:

- `FR-SRC-001..011`, `FR-COL-001..012` trong [01-product-spec.md](../../01-product-spec.md);
- `Source`, `CollectionRun` và các quy tắc dữ liệu trong [02-data-model.md](../../02-data-model.md);
- `QR-REL-*`, `QR-AVL-*`, `QR-DATA-*`, `QR-SEC-*` liên quan trong [03-quality-requirements.md](../../03-quality-requirements.md);
- trách nhiệm A trong [06-system-map.md](../../06-system-map.md);
- DF-01/DF-02 trong [07-data-flow.md](../../07-data-flow.md);
- module `source_ingestion` trong [08-architecture.md](../../08-architecture.md);
- `CT-SRC-001..006` và `CT-CNT-001` trong [04-source-content-contracts.md](../../09-contracts/04-source-content-contracts.md);
- source/run state trong [12-state-machines.md](../../09-contracts/12-state-machines.md);
- chiến lược kiểm thử trong [10-test-strategy.md](../../10-test-strategy.md);
- milestone M3 trong [11-roadmap.md](../../11-roadmap.md).

Nếu tài liệu cũ và hợp đồng/ADR mới khác nhau, ADR và hợp đồng đã audit ở bước sau được ưu tiên. Ví dụ: A chuẩn hóa ở mức kỹ thuật để tạo `CollectedDocumentPackage`; B sở hữu chuẩn hóa nghiệp vụ, danh tính Article và quyết định duplicate/revision.

## 3. Người sử dụng và bên liên quan

| Bên | Nhu cầu từ A |
|---|---|
| User duy nhất | Quản lý nguồn, chạy thử/thu thập lại và xem lỗi/kết quả trên UI |
| G — Điều phối | Lập lịch/cycle, yêu cầu chạy, nhận trạng thái và tiếp tục sau lỗi |
| B — Kho nội dung | Nhận document package và bằng chứng để quyết định article/revision/duplicate |
| C — Kho media | Nhận media discovery cùng provenance sau khi quan hệ nội dung được xác định |
| I — Lưu trữ | Lưu raw snapshot/media byte và trả `ArtifactRef` |
| J — Cấu hình/bí mật | Cung cấp source policy, adapter config và credential handle giới hạn |
| H — Giao diện | Gửi command/query được phép và hiển thị trạng thái/log |

## 4. Ranh giới sở hữu

### A sở hữu và được ghi

- `Source` và revision metadata của nguồn.
- `CollectionRun` nghiệp vụ cho một nguồn.
- fetch observation, extraction result và `CollectedDocumentPackage` trước khi B nhận.
- `last_collection_at`, source access health và collection statistics.
- tombstone/chặn tự phát hiện lại nguồn đã bị user xóa.

### A không sở hữu

- `CollectionCycle`, lịch liên nguồn, target chủ đề và batch/job state: G sở hữu.
- `Article`, `ArticleRevision`, duplicate cluster, representative và `EventUpdate`: B sở hữu.
- `MediaAsset`, rendition, index và usage: C sở hữu.
- byte, cloud/local location, retention và cleanup: I sở hữu.
- topic classification cuối của bài, script, StoryAngle hoặc production plan: B/D sở hữu theo hợp đồng.
- secret, provider account, quota và credential lifecycle: J sở hữu.

### Quy tắc ghi chéo

A không ghi trực tiếp bảng/aggregate của B, C, G, I hoặc J. A gửi command/result/event qua hợp đồng đã định nghĩa.

## 5. Phạm vi chức năng

### 5.1. Quản lý nguồn thủ công

A phải hỗ trợ:

- đăng ký nguồn từ UI;
- xem danh sách/chi tiết/lịch sử revision;
- sửa Tier, nhóm chủ đề/tag, ghi chú, trạng thái bật/tắt và metadata quản trị được phép;
- xóa logic thành tombstone;
- khôi phục nguồn;
- chạy kiểm tra một nguồn mà không tính là lượt định kỳ;
- optimistic concurrency để hai thao tác không ghi đè im lặng.

Không còn file text riêng làm nguồn dữ liệu quản trị.

### 5.2. Tự phát hiện nguồn

A phải có khả năng tự phát hiện nguồn mới mà không yêu cầu user duyệt từng nguồn theo `FR-SRC-004`.

Tuy nhiên:

- nguồn đã tombstone không được tự thêm lại;
- candidate phải đi qua canonicalization, SSRF validation và duplicate-source check;
- việc gán Tier phải theo policy revision đã được duyệt;
- tự phát hiện không được mặc định biến mọi URL tìm thấy thành source active;
- mọi source tự thêm phải có `discovery_method`, evidence và audit reason.

`SourceCandidate`, disposition, command và event tự đăng ký được khóa tại `CT-SRC-003A`, `CT-STATE-002A` và event catalog. A6 chỉ bắt đầu khi Tier/discovery policy có revision được duyệt; không còn khoảng trống ownership của candidate.

### 5.3. Chọn nguồn theo cycle

A phối hợp G để:

- nhận source/config snapshot cho một ngày và chủ đề;
- chỉ xét nguồn `ACTIVE`, đúng scope và chưa có lượt định kỳ trong ranh giới ngày;
- ưu tiên Tier 1, rồi Tier 2, rồi Tier 3;
- dừng mở Tier sau khi G/B xác nhận đạt ngưỡng tin mới không trùng cho chủ đề;
- ghi lý do nguồn được chọn, bỏ qua hoặc chưa được quét;
- không coi `SKIPPED_SUFFICIENT` là lượt scheduler bị mất.

G sở hữu quyết định/counter toàn cycle. A sở hữu kết quả mỗi source run.

### 5.4. Thu thập định kỳ

Mỗi source được chọn có tối đa một `CollectionRun` định kỳ trong một ngày theo timezone cấu hình. Retry kỹ thuật là attempt của cùng run, không phải lượt định kỳ mới.

A phải:

- đọc source feed/listing theo adapter;
- xác định item/URL ứng viên;
- fetch article/document;
- ghi redirect, HTTP observation, thời gian và content type;
- tạo raw snapshot khi policy yêu cầu;
- trích xuất title, body candidate, author, language, publication time candidate và media discoveries;
- tạo fingerprint kỹ thuật để B hỗ trợ resolve identity;
- bàn giao từng document bền vững, không chờ toàn run mới commit;
- hoàn tất run với thống kê và checkpoint/cursor.

### 5.5. Thu thập bổ sung theo video

Khi D/G xác định thiếu media cho một job, A được tìm/tải bổ sung:

- theo scene/entity/topic intent đã cho;
- trong resource/time budget;
- không tính vào lượt quét định kỳ;
- không làm thay đổi daily source-run count;
- vẫn tôn trọng source tombstone;
- vẫn tạo provenance, media discovery và artifact acquisition record;
- dữ liệu bài mới phát hiện vẫn phải đi qua B trước khi thành Article.

### 5.6. Nguồn chính thức của người nổi tiếng

A có thể ghi nhận clip ngắn từ trang cá nhân chính thức của người nổi tiếng như media candidate. A phải lưu evidence cho trạng thái “chính thức”; không tự suy từ display name hoặc nội dung bài.

Phương thức truy cập từng nền tảng phụ thuộc adapter và quyền thật; không được né cơ chế xác thực hoặc hạn chế kỹ thuật bằng cách không được duyệt.

### 5.7. Technical normalization

A chuẩn hóa để trao đổi dữ liệu ổn định:

- URL và redirect chain;
- encoding và text extraction candidate;
- timestamp cùng precision/confidence;
- language candidate;
- MIME/media kind candidate;
- whitespace/boilerplate ở mức extractor;
- provenance và fingerprint.

A không:

- quyết định Article identity;
- chọn bài đại diện;
- kết luận bài là duplicate/revision;
- gộp event;
- xác nhận tính đúng sự thật;
- viết hoặc chọn nội dung video.

### 5.8. Phát hiện media

Mỗi media discovery phải có:

- locator quan sát được;
- source/document/run refs;
- vị trí/vai trò trong trang;
- media kind candidate;
- caption/alt/context nếu có;
- observed time;
- redirect/provenance chain;
- hash/technical metadata nếu đã tải;
- relation candidate như hero, inline, embedded clip hoặc official social clip.

A không quyết định media phù hợp để render; C/D chịu trách nhiệm catalog và chọn.

### 5.9. Kiểm tra “đủ dữ liệu”

Kiểm tra của A chỉ xác nhận:

- fetch/extraction đạt trường tối thiểu theo policy;
- raw/source evidence còn truy được;
- package đúng schema;
- phần thiếu/không chắc chắn được ghi rõ.

Không có hard gate fact-check đa nguồn.

## 6. Đối tượng dữ liệu logic

### 6.1. `Source`

| Nhóm | Trường bắt buộc hoặc có điều kiện |
|---|---|
| Identity | `source_id`, canonical root location, name |
| Classification | `source_kind`, Tier, language, topic scope, market relevance |
| Lifecycle | status, revision, rediscovery blocked, previous operational state |
| Discovery | manual/system method, evidence, discovered/registered time |
| Collection | adapter type/version ref, last collection time, checkpoint ref |
| Risk | rights status, access restrictions, notes |
| Audit | workspace, actor, created/updated time |

`source_kind` và tiêu chí Tier hiện chưa có danh sách/thuật toán chính thức.

### 6.2. `SourceCandidate`

Đối tượng logic theo `CT-SRC-003A` để đáp ứng tự phát hiện nguồn:

- candidate ID;
- discovered locator/canonical candidate;
- discovery evidence/method;
- source kind/topic/market candidates cùng confidence;
- matched existing/tombstoned source ref nếu có;
- proposed Tier policy result nếu policy tồn tại;
- safety/access validation;
- disposition và reason;
- observed time/config revision.

Các disposition hợp lệ là `READY_FOR_REGISTRATION`, `MATCHED_EXISTING`, `BLOCKED_TOMBSTONE`, `REJECTED` và `REGISTERED`; trạng thái chờ policy không được tự biến thành source active.

### 6.3. `CollectionRun`

Một run thuộc đúng một source trong kiến trúc hiện hành:

- run ID, source ID/revision;
- purpose: periodic, supplemental hoặc source-test; retry kỹ thuật nằm ở `CollectionAttempt`, không phải purpose mới;
- cycle/job refs theo purpose;
- configuration/policy/adapter revisions;
- scheduled/started/finished timestamps;
- status và attempt count;
- cursor/checkpoint trước-sau;
- item/discovery/fetch/package counters;
- error/warning summary;
- correlation/trace refs.

Run `COMPLETED_PARTIAL` giữ mọi document đã commit.

### 6.4. `FetchObservation`

- requested/final/canonical URL candidate;
- fetch time và HTTP observation an toàn;
- redirect chain;
- response media type/size;
- raw artifact ref nếu lưu;
- source/adapter/version;
- problem/warnings;
- operation receipt ref nếu có side effect.

### 6.5. `CollectedDocumentPackage`

Schema phải tuân `CT-SRC-006`, gồm các trường cấu trúc bắt buộc, trường có điều kiện và `content_eligibility`. Title/main text rỗng không được đánh dấu `candidate`; ngưỡng nội dung chi tiết vẫn do policy revision quyết định.

Package là observation, không phải `Article`.

### 6.6. `CollectionCheckpoint`

- source/adapter revision;
- cursor/watermark/last item identity theo adapter;
- recorded time;
- run/attempt ref;
- completeness state;
- fingerprint.

Checkpoint chỉ tiến qua dữ liệu đã được ghi nhận bền vững. Adapter đổi semantics phải tạo checkpoint version mới hoặc migration rõ ràng.

## 7. Command và query

### Command nhận

| Command | Caller | Kết quả |
|---|---|---|
| `RegisterSource` | H | Source revision + receipt |
| `UpdateSourceMetadata` | H | Source revision mới |
| `RemoveSource` | H | Tombstone revision |
| `RestoreSource` | H | Revision khôi phục hoặc disabled có lý do |
| `TestSource` | H/G | Operation/run ref, không tính periodic |
| `CollectSource` | G | Run result và package refs |
| `RequestSupplementalMedia` | G/D qua G | Discovery/acquisition refs |

`RequestSupplementalMedia` có contract ở phân hệ media; A chỉ thực hiện phần tìm/fetch theo yêu cầu được G cấp quyền.

### Query cung cấp

- danh sách/chi tiết Source;
- source revision history;
- collection run và attempt history;
- collection result/counters;
- source health và last collection;
- fetch/package trace đã redacted;
- reason nguồn được chọn/bỏ qua qua projection phối hợp G.

Query không tự kích hoạt fetch.

## 8. Event

A phát qua transactional outbox:

- `SourceRegistered`;
- `SourceMetadataUpdated`;
- `SourceRemoved`;
- `SourceRestored`;
- `SourceCandidateDiscovered`;
- `SourceCandidateResolved`;
- `CollectionRunStarted`;
- `CollectedDocumentAvailable`;
- `CollectionRunCompleted`;
- `CollectionRunFailed`.

Event dùng at-least-once; consumer deduplicate. Không event nào chứa secret, raw byte hoặc signed URL dài hạn.

Event source auto-discovery dùng payload tối thiểu theo `CT-SRC-003A`; không chứa locator/token nhạy cảm ngoài provenance được phép.

## 9. Máy trạng thái

### Source

`ACTIVE ↔ DISABLED → REMOVED_TOMBSTONE`

- Tombstone chỉ rời bằng `RestoreSource`.
- Restore về trạng thái trước remove nếu policy còn cho phép; nếu không về `DISABLED` kèm lý do.
- Auto-discovery gặp locator tombstone phải trả disposition bị chặn, không tạo Source mới.

### CollectionRun

Các nhánh run:

- `SCHEDULED` → `RUNNING`;
- `RUNNING` → `WAITING_RETRY` → `RUNNING`;
- `RUNNING` → `WAITING_RECONCILIATION` → `RUNNING` hoặc terminal sau reconcile;
- `RUNNING` → `COMPLETED` | `COMPLETED_PARTIAL` | `FAILED_FINAL`.

- Retryable failure chỉ đưa run sang WAITING_RETRY khi nguồn/budget còn cho phép. Hết retry/deadline hoặc nguồn inactive: từ RUNNING/WAITING_RETRY tới COMPLETED_PARTIAL nếu đã commit package hợp lệ, ngược lại FAILED_FINAL; SCHEDULED gặp nguồn inactive kết thúc FAILED_FINAL không tạo attempt giả.
- `OUTCOME_UNKNOWN` đưa run sang `WAITING_RECONCILIATION`; không retry side effect trước khi reconcile.
- Run terminal không quay lại running.
- Source không được chọn do đủ ngưỡng có CollectionDecision do G ghi; A không tạo run giả.

CT-STATE-002 là bảng đầy đủ: reconcile retryable đi WAITING_RETRY nếu còn được phép, ngược lại partial/final; reconcile xác nhận xong đi COMPLETED; unknown chưa đủ bằng chứng tiếp tục chờ có log/cảnh báo, không retry mù. Reconciliation result được append, không xóa attempt observation.

### Quy tắc biên candidate và package sau hậu kiểm

- CT-SRC-003A: READY có thể kết thúc REGISTERED/MATCHED_EXISTING/BLOCKED_TOMBSTONE/REJECTED theo kiểm tra lại nguyên tử lúc đăng ký. Thiếu policy giữ WAITING_POLICY, revision cũ trả conflict; receipt/outbox/candidate/source nhất quán và retry sau mất ACK không đăng ký lần hai.
- CT-SRC-006: thiếu ID/source/run/provenance bắt buộc là VALIDATION_ERROR tại biên, chỉ ghi quan sát lỗi bằng định danh an toàn, không chuyển B như tin incomplete. Đủ schema nhưng thiếu main text hoặc không đạt source-kind policy mới lưu incomplete để B trả REJECTED_INCOMPLETE.
- Title bắt buộc/tùy chọn là trường của source-kind extraction policy có revision, chưa tự chốt giá trị cho các source kind đang mở. Thiếu policy trả INPUT_NOT_READY; không ảnh hưởng title/hashtag video bắt buộc.

## 10. Quy tắc nghiệp vụ bắt buộc

| Mã | Quy tắc |
|---|---|
| `A-RULE-001` | Mọi Source mutation có idempotency key và expected revision khi sửa |
| `A-RULE-002` | Source tombstone không được auto-add hoặc fetch mới cho supplemental work |
| `A-RULE-003` | Dữ liệu tin/media đã lưu không bị xóa hoặc mất eligibility chỉ vì Source bị remove |
| `A-RULE-004` | Một source có tối đa một periodic run trong một `business_date`; policy revision không thuộc unique identity |
| `A-RULE-005` | Retry là attempt của run cũ; supplemental/source-test là purpose riêng |
| `A-RULE-006` | Tier sau chỉ mở khi G/B chưa xác nhận đủ unique new articles cho chủ đề |
| `A-RULE-007` | URL/item count không được dùng thay unique article count |
| `A-RULE-008` | Document được bàn giao bền vững từng item; partial run không rollback item đã commit |
| `A-RULE-009` | Checkpoint không vượt qua item chưa được ghi nhận bền vững |
| `A-RULE-010` | Mọi package/media discovery có source/run/provenance refs |
| `A-RULE-011` | A không kết luận duplicate, event update hoặc truth verification |
| `A-RULE-012` | Một source lỗi không làm dừng source độc lập khác |
| `A-RULE-013` | Fetch chỉ cho phép HTTP(S) và phải qua SSRF validation ở mỗi redirect |
| `A-RULE-014` | Secret/credential không vào event, log, package hoặc workflow history |
| `A-RULE-015` | Raw byte được giao I; A không quản lý storage lifecycle dài hạn |
| `A-RULE-016` | Desktop offline không ngăn periodic collection trên cloud |

## 11. User stories và acceptance criteria

### US-A-001 — Quản lý nguồn thủ công

User muốn thêm và quản lý nguồn trên UI để không phụ thuộc file text.

- GIVEN locator hợp lệ chưa tồn tại, WHEN đăng ký, THEN tạo đúng một Source revision và event.
- GIVEN cùng idempotency key/payload, WHEN gửi lặp, THEN trả receipt/resource cũ.
- GIVEN Source tombstone cùng locator, WHEN đăng ký lại, THEN bị từ chối và trả source ref đã xóa.
- GIVEN hai tab sửa cùng revision, WHEN tab sau commit, THEN nhận revision conflict.

### US-A-002 — Xóa và khôi phục nguồn

- GIVEN Source active, WHEN remove, THEN chuyển tombstone, dừng fetch mới và chặn rediscovery.
- GIVEN dữ liệu lịch sử từ Source đã remove, WHEN hệ thống khai thác, THEN dữ liệu vẫn tồn tại và không bị A xóa.
- GIVEN restore hợp lệ, WHEN user khôi phục, THEN trạng thái trước remove được phục hồi hoặc disabled có reason nếu policy không còn cho phép.

### US-A-003 — Quét theo Tier và ngưỡng chủ đề

- GIVEN chủ đề chưa đủ unique articles, WHEN G yêu cầu chọn nguồn, THEN A/G xét source Tier cao trước.
- GIVEN chủ đề đã đủ, WHEN cycle tiếp tục, THEN không mở Tier sau và ghi `SKIPPED_SUFFICIENT` ở G.
- GIVEN source active chưa được chọn vì đủ ngưỡng, THEN không tạo CollectionRun giả và không tính scheduler miss.

### US-A-004 — Thu thập một nguồn

- GIVEN source/adapter/config hợp lệ, WHEN collect, THEN tạo run, package có provenance và checkpoint đúng.
- GIVEN một item fetch lỗi, WHEN các item khác hợp lệ, THEN run có thể partial và item hợp lệ vẫn được bàn giao.
- GIVEN source lỗi hoàn toàn, THEN lỗi có source/run/time/problem và source khác vẫn chạy.

### US-A-005 — Phân biệt retry và lượt mới

- GIVEN periodic run lỗi retryable, WHEN retry, THEN attempt tăng trong cùng run và không tăng periodic run count.
- GIVEN source-test hoặc supplemental request, THEN purpose riêng và không làm source có vẻ đã quét thêm một ngày.

### US-A-006 — Nguồn sửa bài

- GIVEN URL đã từng thu thập có nội dung thay đổi, WHEN fetch lại, THEN A tạo observation/package/fingerprint mới cho B quyết định revision.
- GIVEN video cũ dùng revision trước, THEN A không yêu cầu tái tạo hoặc sửa video cũ.

### US-A-007 — Thu thập media

- GIVEN bài có ảnh/clip, WHEN extract, THEN media discovery giữ locator, context và provenance.
- GIVEN trang chính thức người nổi tiếng có clip, WHEN adapter được phép truy cập, THEN clip được ghi là official-source candidate có evidence.
- GIVEN media download thất bại, THEN document package vẫn có thể được bàn giao với warning/error theo policy.

### US-A-008 — Desktop offline

- GIVEN desktop tắt, WHEN tới lịch cloud, THEN collection vẫn bắt đầu và dữ liệu được lưu cloud.
- GIVEN desktop online lại, THEN A không quét lại toàn bộ chỉ vì desktop từng offline.

### US-A-009 — Tự phát hiện nguồn

- GIVEN candidate mới qua policy và không tombstone, WHEN auto-registration được bật, THEN Source được tạo cùng discovery evidence và Tier policy revision.
- GIVEN candidate trùng/tombstone/SSRF unsafe, THEN không tạo Source active.
- Feature này chưa `READY_FOR_IMPLEMENTATION` cho tới khi Tier/discovery policy được đóng; contract candidate đã có.

## 12. UI và quan sát

H phải cho user quan sát/thao tác với A qua contract:

- bảng Source: name, root location, kind, Tier, topic scope, status, health, last collection, origin, notes;
- lọc theo Tier/topic/status/kind/health;
- thêm, sửa metadata, bật/tắt, remove, restore và test source;
- bảng CollectionRun: purpose, source, schedule/start/end, status, attempt, counters, checkpoint và config revision;
- click/hover lỗi thấy source/run/time/code/detail an toàn;
- xem document package summary và provenance, không chỉnh article body;
- stream accepted/running/partial/failed/completed qua SSE;
- không hiển thị secret hoặc raw authorization header.

Danh sách cột cuối và quy mô bảng vẫn là open item của UI; spec này chỉ khóa trường nghiệp vụ cần quan sát.

## 13. Failure semantics

| Tình huống | Kết quả |
|---|---|
| URL/source invalid | Command rejected, không tạo Source |
| Source tombstone | Conflict/blocked, không auto-add |
| DNS/SSRF unsafe | Security rejection, có audit/log an toàn |
| Feed/article timeout | Retryable problem theo policy; source khác tiếp tục |
| Redirect loop/private destination | Fetch bị chặn |
| HTML/encoding parse lỗi | Item warning/failure; run có thể partial |
| Content quá lớn | Từ chối/giới hạn theo policy; không làm cạn tài nguyên worker |
| Raw snapshot upload outcome unknown | Reconcile qua I trước retry side effect |
| Event publish lỗi sau DB commit | Outbox phát lại khi hồi phục |
| Worker chết giữa run | Run/attempt được phục hồi; checkpoint không vượt item chưa commit |
| B chưa trả duplicate outcome | Chủ đề chưa được tính “đủ”; G áp backpressure theo policy |
| Config/adapter revision không hỗ trợ | Fail rõ, không tự dùng config khác |

## 14. Yêu cầu chất lượng áp dụng

| Yêu cầu | Mức phải đạt |
|---|---|
| QR-REL-002 | Một source lỗi không dừng các source khác |
| QR-REL-003/008, QR-OBS-004 | Mọi failure có state/time/object/log; không mất việc im lặng |
| QR-REL-004 | Run đã commit không chạy lại từ đầu sau restart |
| QR-AVL-001 | Collection cloud chạy khi desktop offline |
| QR-AVL-003 | Ít nhất 99% schedule hợp lệ được bắt đầu trong tháng |
| QR-DATA-001 | Mọi package/article downstream truy được source/revision |
| QR-PERF-005/006 | UI p95 2 giây; durable command acceptance 1 giây |
| QR-SEC-001/002/007/008 | Không lộ secret; kênh có dữ liệu/secret được bảo vệ |
| QR-SCALE-001/002 | Thêm source/topic không phá dữ liệu cũ |
| QR-MNT-001/002 | Adapter/source module thay đổi và kiểm thử độc lập được |

Thời gian tối đa một collection cycle và retry/timeout từng adapter chưa có ngưỡng chính thức.

## 15. Security boundary

- Chỉ HTTP(S) theo allow policy; chặn loopback/private/link-local/metadata endpoint sau DNS resolution ở mỗi redirect.
- Giới hạn redirect, response size, content type, duration và concurrency theo config.
- Không tin URL, header, HTML, filename hoặc metadata từ nguồn.
- Sanitize/escape nội dung khi hiển thị trên H.
- Credential chỉ nhận bằng handle ngắn hạn/adapter-bound từ J.
- Không log Authorization/Cookie/token/raw secret.
- Không cho AI cung cấp path hoặc shell command cho fetcher.
- Workspace được kiểm tra ở command/query/event.
- Source test không được trở thành đường proxy tùy ý từ UI.

## 16. Metrics và audit

### Metrics tối thiểu

- source/cycle/run/adapter counts theo status;
- fetch latency, bytes và error category;
- item found/fetched/packaged/rejected;
- run completed/partial/failed;
- retry attempts và backoff;
- checkpoint lag;
- source skipped reason;
- Tier expansion và unique-article counter do G/B cung cấp;
- outbox lag;
- raw snapshot/media acquisition result;
- source health trend.

### Audit bắt buộc

- register/update/enable/disable/remove/restore source;
- Tier/topic/adapter config change;
- source test và manual collection;
- auto-discovery/auto-registration decision;
- credential/account reference change;
- override hoặc retry do user kích hoạt.

## 17. Điều kiện nghiệm thu phân hệ A

Phân hệ A chỉ được user duyệt khi:

1. Mọi `A-RULE-*` có test trực tiếp.
2. Manual source lifecycle chạy qua UI và optimistic concurrency đúng.
3. Tombstone chặn rediscovery nhưng dữ liệu lịch sử không bị xóa.
4. Periodic, source-test và supplemental purpose không bị nhập làm một; retry là attempt của run cũ.
5. Source lỗi không dừng source khác; partial run giữ package đã commit.
6. Package có provenance/raw refs/warnings và B nhận idempotent.
7. Desktop offline không làm mất schedule cloud.
8. SSRF/redirect/size/secret tests đạt.
9. UI/log/session/trace cho phép debug từng run.
10. Auto-discovery chỉ được nghiệm thu sau khi Tier/discovery policy được đóng và fixture chứng minh contract candidate.
11. User xác nhận lát cắt A trước khi chuyển sang nghiệm thu B.

## 18. Vấn đề chưa quyết định

| Mã | Vấn đề | Loại | Chặn gì |
|---|---|---|---|
| `MODULE-A-OPEN-001` | Danh sách `source_kind` chính thức | Cấu hình/schema | Adapter registry và UI filter cuối |
| `MODULE-A-OPEN-002` | Danh sách nguồn baseline và tiêu chí Tier 1/2/3 | Nghiệp vụ/nghiên cứu | Auto-discovery/production source set |
| `MODULE-A-OPEN-003` | Giá trị ngưỡng tin mới từng chủ đề; cách đếm đa chủ đề đã khóa theo `CT-SRC-004` | Nghiệp vụ/config | Production Tier expansion |
| `MODULE-A-OPEN-004` | Giá trị timezone và giờ chạy; semantics `business_date` đã khóa theo `CT-SRC-004` | Vận hành | Schedule production |
| `MODULE-A-OPEN-005` | Ngưỡng độ dài/chất lượng nội dung; trường package tối thiểu đã khóa theo `CT-SRC-006` | Policy | Rejected-incomplete oracle |
| `MODULE-A-OPEN-006` | ĐÃ ĐÓNG: `SourceCandidate` theo `CT-SRC-003A`/`CT-STATE-002A` | Contract | Không còn chặn ownership/lifecycle; Tier policy vẫn chặn auto-registration production |
| `MODULE-A-OPEN-007` | Raw snapshot/duplicate full-text retention | Storage/data | Storage cost và audit depth |
| `MODULE-A-OPEN-008` | Adapter nguồn/social baseline và quyền truy cập thật | Integration | Phạm vi M3/R1 Content Alpha |
| `MODULE-A-OPEN-009` | Timeout/retry/backoff/concurrency từng adapter | Benchmark | Reliability/performance claim |
| `MODULE-A-OPEN-010` | Thời gian tối đa cho daily collection cycle | Quality | QR-PERF-008 claim |

Các mục này không được hard-code bằng default ẩn. Chúng phải là policy/config revision hoặc được quyết định trước work package bị chặn.

## 19. GIẢ ĐỊNH

**Không có GIẢ ĐỊNH chưa được xác nhận nào được dùng làm yêu cầu chính thức trong đặc tả này.**

Khả năng truy cập từng nguồn, API/social platform, quota, HTML stability và chất lượng extractor hiện là **CHƯA KIỂM CHỨNG**; chúng phải được chứng minh theo adapter bằng fixture và integration proof.

## 20. Ngoài phạm vi

- Quyết định Article/revision/duplicate representative.
- Phân loại chủ đề cuối và liên kết Event/EventUpdate.
- Fact-check đa nguồn bắt buộc.
- Media catalog/index/rendition/selection.
- AI script, StoryAngle và production plan.
- Image safety transform ngoài probe/discovery handoff.
- TTS, subtitle, render và video QC.
- Batch production và completion ledger.
- Google Sheets làm source database.
- Sửa article body/script/event relation trên UI.
- Bỏ hạn chế nguồn hoặc truy cập trái policy của nền tảng.
