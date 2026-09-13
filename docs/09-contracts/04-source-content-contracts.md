# 04. Hợp đồng nguồn và nội dung

> Trạng thái: **Bản thiết kế trước triển khai**  
> Producer chính: A — Thu thập nội dung.  
> Consumer/chủ sở hữu nội dung: B — Kho nội dung.

## 1. Ranh giới trách nhiệm

- A sở hữu `Source`, quyết định thu thập, `CollectionRun` và bằng chứng fetch.
- B sở hữu `Article`, `ArticleRevision`, `Event`, `EventUpdate` và kết quả chống trùng/liên kết.
- G điều phối lịch và yêu cầu chạy, nhưng không tự sửa Source/Article/Event.
- C nhận media discovery/provenance sau khi B đã xác định bài đại diện.
- D chỉ phân tích các revision/snapshot được B cung cấp; không ghi lại bài gốc.

## 2. Quản lý nguồn

### CT-SRC-001 — `RegisterSource`

Input tối thiểu:

- URL/canonical locator;
- loại nguồn;
- Tier ban đầu do user hoặc policy xác định;
- nhóm chủ đề;
- collection enabled;
- ghi chú tùy chọn;
- workspace và actor.

Output: `SourceRef`, revision, trạng thái kiểm tra URL và command receipt.

Điều kiện:

- URL qua canonicalization và SSRF policy.
- Nguồn đã tombstone không được tự tạo lại; trả conflict kèm source ref đã xóa.
- Không tự nâng/giảm Tier nếu chưa có policy revision cho phép.

### CT-SRC-002 — `UpdateSourceMetadata`

Chỉ cho phép thay:

- Tier;
- nhóm chủ đề/tag;
- ghi chú;
- bật/tắt thu thập;
- metadata quản trị được schema công bố.

Không dùng operation này để sửa article, provenance lịch sử hoặc event relation.

### CT-SRC-003 — `RemoveSource` / `RestoreSource`

- Remove tạo tombstone, dừng thu thập và chặn auto-discovery thêm lại.
- Dữ liệu tin/media đã lưu vẫn được khai thác.
- Restore khôi phục trạng thái hoạt động trước khi remove nếu trạng thái đó còn hợp lệ; nếu policy không còn cho phép, nguồn về `DISABLED` với lý do.
- Mọi chuyển trạng thái có actor, thời gian và revision.

### CT-SRC-003A — `EvaluateSourceCandidate` / `RegisterSourceCandidate`

A sở hữu `SourceCandidate`. Candidate tối thiểu có candidate ID, locator quan sát/canonical candidate, discovery method/evidence, source-kind/topic candidates, matched source/tombstone ref nếu có, validation result, proposed Tier cùng policy revision, disposition, reason và audit time.

`EvaluateSourceCandidate` nhận workspace, locator quan sát, discovery method/evidence, các classification candidate, policy revision và idempotency key; trả candidate ref/revision, disposition, matched source/tombstone ref nếu có và reason. `RegisterSourceCandidate` nhận candidate ref, expected revision, policy revision và idempotency key; trả disposition, candidate revision cuối, receipt và SourceRef/tombstone ref nếu phù hợp; lỗi input/revision trả lỗi có cấu trúc không đổi state.

Lifecycle:

`DISCOVERED` → `VALIDATING` → `READY_FOR_REGISTRATION` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`

`READY_FOR_REGISTRATION` → `REGISTERED` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`. Registration kiểm tra lại canonical identity, source/tombstone và policy hiện hành trong cùng transaction với candidate, source mutation, receipt và outbox. Dùng cùng khóa identity/uniqueness với RegisterSource và RemoveSource: tombstone hiện có trả BLOCKED_TOMBSTONE; source active/disabled hiện có trả MATCHED_EXISTING; policy cấm trả REJECTED; thiếu policy/auto-registration tạm tắt giữ READY với WAITING_POLICY. Chỉ tạo Source khi còn được phép và source kind/topic/Tier đã xác định, không tự gán mặc định.

Race registration thắng trước remove thì remove phải tombstone Source vừa tạo; remove thắng trước thì registration bị chặn. Retry cùng key/input trả receipt và disposition đã commit dù ACK mất; không mở lại candidate terminal. Expected revision cũ không có receipt tương ứng trả REVISION_CONFLICT, caller đọc lại trạng thái. Chính sách thay đổi không âm thầm dùng policy cũ để đăng ký.

A phát `SourceCandidateDiscovered` khi candidate đã commit và `SourceCandidateResolved` khi có disposition terminal/registered; event chỉ mang refs, revision, disposition và reason an toàn.

## 3. Lập kế hoạch thu thập

### CT-SRC-004 — `PlanCollectionCycle`

Input:

- `business_date` được suy ra từ timezone revision đã khóa cho cycle;
- subject groups đang bật;
- `fresh_unique_article_target` theo từng chủ đề;
- source snapshot gồm Tier và trạng thái;
- collection policy revision.

Output:

- danh sách nguồn theo thứ tự deterministic;
- lý do chọn/bỏ qua;
- ngưỡng dừng mở rộng Tier cho từng chủ đề;
- cycle ID.

Bất biến:

1. Mỗi nguồn được quét định kỳ tối đa một lần trong cycle ngày.
2. Tier tiếp theo chỉ được mở khi số tin mới không trùng của chủ đề chưa đạt ngưỡng.
3. Có thể có nguồn đang bật không được quét trong ngày nếu Tier trước đã đủ.
4. Tìm/tải bổ sung theo từng video không tính vào giới hạn quét định kỳ.
5. Một article đại diện được B chấp nhận chỉ tăng tối đa một lần cho mỗi topic mà nó thuộc trong cùng `business_date`; article nhiều topic có thể tăng từng bộ đếm topic độc lập, nhưng các bộ đếm không được cộng lại thành số tin duy nhất toàn hệ thống.
6. Khóa một lượt định kỳ là `workspace_id + source_id + business_date + periodic`; policy revision là metadata của lượt, không thuộc danh tính duy nhất và đổi policy trong ngày không mở lượt thứ hai.

Thời điểm chạy, timezone và ngưỡng từng chủ đề là **CẤU HÌNH**. Timezone revision đã khóa không đổi `business_date` của cycle đang tồn tại; policy mới chỉ áp dụng cycle ngày tiếp theo. Catch-up nếu được cấu hình vẫn là periodic run của `business_date` đã bỏ lỡ và dùng cùng unique key, không tạo purpose né giới hạn.

## 4. Thu thập một nguồn

### CT-SRC-005 — `CollectSource`

Input:

- source revision;
- collection cycle/run ID;
- fetch policy revision;
- cursor/checkpoint của nguồn;
- giới hạn tài nguyên và deadline.

Output `CollectionRunResult`:

- trạng thái `COMPLETED`, `COMPLETED_PARTIAL` hoặc `FAILED_FINAL`;
- số URL thấy, tải thành công, bị bỏ qua và lỗi;
- document package refs;
- cursor/checkpoint mới;
- lỗi theo URL đã redacted;
- thống kê media discovery.

Partial success không làm mất các document đã commit. Cursor chỉ tiến qua mốc đã ghi nhận bền vững.

## 5. Giao bài thu thập sang kho nội dung

### CT-SRC-006 — `CollectedDocumentPackage`

| Trường | Ý nghĩa |
|---|---|
| `collected_document_id` | ID duy nhất của lần quan sát |
| `source_id`, `source_revision` | Nguồn và Tier tại thời điểm lấy |
| `collection_run_id` | Lượt thu thập |
| `requested_url`, `final_url`, `canonical_url_candidate` | Chuỗi URL có provenance |
| `fetched_at`, `published_at_candidate` | Thời gian và confidence |
| `http_observation` | status, media type, headers an toàn |
| `raw_snapshot_ref` | Artifact ref của bằng chứng gốc nếu lưu |
| `extraction_disposition`, `extractor_version` | Kết quả trích xuất và phiên bản adapter/extractor |
| `extracted_content_candidate` | title, text, author, language và extractor version |
| `content_eligibility` | `candidate` hoặc `incomplete` cùng reason |
| `content_fingerprints` | exact/near-duplicate fingerprints |
| `media_discoveries` | URL/ref, loại, vị trí trong bài, provenance |
| `provenance_chain` | Redirect, source page và extraction evidence |
| `warnings` | Thiếu trường, encoding, parse uncertainty |

Các trường cấu trúc bắt buộc cho mọi package là ID/source/run refs, requested/final URL, fetched time, HTTP observation, extraction disposition cùng extractor version, provenance chain và warnings (có thể rỗng). `canonical_url_candidate`, publication/author/language, raw snapshot, fingerprint và media là có điều kiện; nếu policy yêu cầu raw snapshot mà không có thì package phải ghi lỗi.

Tách hai lớp validation:

1. Thiếu/sai trường cấu trúc bắt buộc: từ chối với VALIDATION_ERROR tại biên A và kiểm tra phòng vệ tại B; không tạo CollectedDocument/Article hoặc event package accepted. Ghi quan sát lỗi bằng request/correlation ID do bên nhận cấp và source/run ref chỉ khi đã xác thực; không bịa provenance hoặc ID còn thiếu. Payload sửa là submission mới; gửi lại cùng payload sai không tạo bản ghi tin.
2. Package đúng schema nhưng nội dung không đủ: A lưu với `content_eligibility=incomplete`, reason và provenance; B trả REJECTED_INCOMPLETE. `candidate` cần main text không rỗng và đạt policy trích xuất có revision. Title bắt buộc hay tùy chọn được xác định theo source kind trong policy, không mặc định mọi social source có title riêng. Chưa có policy thì INPUT_NOT_READY, không tự chọn mặc định; giá trị policy vẫn thuộc gate cấu hình trước production. Metadata title của video đầu ra không bị thay đổi bởi quy tắc này.

Extraction lỗi nhưng có đủ trường cấu trúc thuộc lớp hai. Transport/HTTP thất bại chưa tạo được package hợp lệ chỉ ghi fetch/attempt observation và xử lý run theo CT-STATE-002, không nhét vào B như bài thiếu nội dung. Schema rejection không có nghĩa operation bên ngoài chưa xảy ra: receipt/outcome unknown vẫn phải reconcile trước retry side effect.

Package không khẳng định đây là bài mới hoặc thông tin đúng. B quyết định identity và trạng thái.

## 6. Chống trùng và chọn bài đại diện

### CT-CNT-001 — `ResolveCollectedDocument`

Input: document package ref và dedup policy revision.

Output disposition:

| Disposition | Ý nghĩa | Tác động |
|---|---|---|
| `NEW_ARTICLE` | Chưa có nội dung tương đương | Tạo Article và revision |
| `NEW_REVISION` | Cùng bài nhưng nội dung nguồn thay đổi có ý nghĩa | Tạo ArticleRevision mới |
| `DUPLICATE_MEDIA_ONLY` | Nội dung trùng; có provenance/media mới | Không tạo article/script; bổ sung media cho bài đại diện |
| `DUPLICATE_NO_NEW_VALUE` | Trùng và không có dữ liệu mới | Chỉ ghi quan sát/dedup evidence |
| `REJECTED_INCOMPLETE` | Không đủ dữ liệu tối thiểu | Ghi lý do; không tạo article |

### CT-CNT-002 — Quy tắc bài đại diện

- Ưu tiên nguồn theo Tier.
- Nếu cùng Tier, giữ bài đại diện hiện có để tránh dao động; khi chưa có bài đại diện, phá hòa bằng thứ tự `source_id` ổn định và lưu `selection_reason`.
- Khi xuất hiện nguồn Tier cao hơn, có thể tạo revision/đổi representative cho lần sản xuất sau; không đổi snapshot job đã bắt đầu tạo script.
- Bài trùng không tạo tin hoặc kịch bản mới.
- Media mới từ bài trùng vẫn được ghi provenance và gắn vào bài đại diện để tăng khả năng tạo biến thể.

## 7. Bài, sự kiện và diễn biến mới

### CT-CNT-003 — `ArticleRevisionAccepted`

Revision phải có:

- nội dung chuẩn hóa;
- source/provenance refs;
- publication/fetch time cùng confidence;
- topic classification;
- dedup fingerprints;
- media discovery refs;
- extractor/normalizer version;
- trạng thái đầy đủ/không chắc chắn.

### CT-CNT-004 — `ResolveEventLink`

Input: article revision refs, event-link policy/model revision và evidence.

Output:

- `event_id` hiện có hoặc event candidate mới;
- disposition `linked`, `kept_separate`, `needs_more_evidence`;
- confidence và explanation refs;
- relation type;
- effective time range.

Mặc định giữ bài riêng và vẫn cho phép video từng bài. Chỉ tổng hợp khi liên kết đủ chắc theo policy.

### CT-CNT-005 — `EvaluateEventUpdate`

Nguồn mới hoặc bài đăng lại **không tự động** là diễn biến mới. `EventUpdate` chỉ được tạo khi có tình tiết mới về vụ việc theo policy và evidence refs.

Output:

- `is_new_development`;
- danh sách claim/tình tiết mới được đối chiếu với event hiện có;
- source revision refs;
- confidence và reason;
- event update revision nếu được chấp nhận.

Chỉ `EventUpdateAccepted` mới cho phép tạo nội dung “từ lúc đó đến nay”.

## 8. Xác minh theo phạm vi đã chốt

### CT-CNT-006 — `SourceTraceabilityCheck`

Hard requirements:

- lấy đủ dữ liệu tối thiểu cho pipeline;
- truy được nguồn/provenance;
- ghi trạng thái thiếu hoặc không chắc chắn.

Không có hard gate kiểm chứng sự thật đa nguồn. Claim suy luận/sáng tạo được phép nhưng phải được D đánh dấu là suy luận trong nội dung đầu ra.

## 9. Acceptance contract

1. Nguồn bị remove không được auto-discovery thêm lại.
2. Đạt ngưỡng tin mới không trùng thì không mở Tier tiếp theo.
3. Bài đăng lại không tạo Article/Script mới nhưng media mới không bị mất.
4. Job đã bắt đầu tạo script giữ bộ nguồn đã snapshot dù representative đổi sau đó.
5. Nội dung “từ lúc đó đến nay” chỉ xuất hiện khi có `EventUpdateAccepted`.
6. Mọi article revision truy ngược được source và bằng chứng fetch.
7. Candidate trùng/tombstone/rejected không tạo Source; auto-registration luôn có policy revision và audit reason.
8. Đổi collection policy trong cùng business date không tạo periodic run thứ hai cho source.
9. Package sai cấu trúc bị VALIDATION_ERROR trước khi B nhận document; package đúng cấu trúc nhưng thiếu nội dung theo source-kind policy mới được lưu incomplete và REJECTED_INCOMPLETE.

Run/attempt sử dụng đầy đủ bảng CT-STATE-002, bao gồm hết retry, source inactive và reconcile; không tạo attempt giả để đạt terminal. Candidate registration dùng các nhánh READY terminal và idempotent receipt ở CT-SRC-003A.
