# 02. Domain event và transactional outbox

> Trạng thái: **Bản thiết kế trước triển khai**  
> Mục tiêu: phát thay đổi đã commit để projection, quan sát và phân hệ liên quan phản ứng an toàn.

## 1. Ngữ nghĩa chuyển phát

### CT-EVT-001 — Delivery contract

- Event được chuyển phát **at least once**.
- Không có thứ tự toàn cục.
- Thứ tự chỉ được kỳ vọng theo một aggregate và `aggregate_revision`.
- Consumer phải idempotent và lưu checkpoint/deduplication.
- Event chỉ được phát sau khi thay đổi nghiệp vụ đã commit.
- Transactional outbox ghi thay đổi nghiệp vụ và outbox record trong cùng transaction.
- Việc publish thất bại không rollback dữ liệu đã commit; publisher tiếp tục từ outbox.

Event không phải nguồn sự thật thay thế aggregate hiện tại, trừ khi một ADR tương lai chọn event sourcing.

## 2. Event envelope

### CT-EVT-002 — `DomainEvent`

Ngoài `MessageEnvelope`, event có:

| Trường | Ý nghĩa |
|---|---|
| `event_id` | ID duy nhất, bất biến |
| `event_name` | Tên sự kiện ở thì quá khứ |
| `aggregate_type` | Loại aggregate |
| `aggregate_id` | ID aggregate |
| `aggregate_revision` | Revision sau commit |
| `producer` | Phân hệ owner |
| `schema_version` | Version payload |
| `recovery_epoch` | Epoch tại thời điểm event được commit |
| `payload` | Dữ liệu tối thiểu cần để phản ứng |
| `sensitivity` | Mức phân loại dữ liệu |

Không event nào chứa blob, secret, raw OAuth response, signed URL dài hạn, transcript đầy đủ nếu chỉ cần một reference, hoặc log stack trace.

## 3. Quy tắc thiết kế payload

### CT-EVT-003 — Payload policy

- Mang ID và revision của đối tượng đã thay đổi.
- Chỉ mang snapshot nhỏ khi consumer cần tránh race và dữ liệu đó không nhạy cảm.
- Với nội dung lớn, dùng `ResourceRef` hoặc `ArtifactRef`.
- Field mới phải optional đối với consumer cũ.
- Enum được xem là open set; consumer gặp giá trị mới phải dùng nhánh `unknown`, không crash.
- Event đã phát không được sửa. Sửa sai bằng event hiệu chỉnh mới.

## 4. Catalog sự kiện

### Phân hệ A — Thu thập nguồn

| Event | Khi phát | Consumer chính |
|---|---|---|
| `SourceRegistered` | Nguồn được tạo | G, H, J |
| `SourceMetadataUpdated` | Tier/tag/trạng thái thay đổi | G, H |
| `SourceRemoved` | Nguồn thành tombstone | G, H |
| `SourceRestored` | Nguồn được khôi phục | G, H |
| `SourceCandidateDiscovered` | Candidate được lưu để đánh giá | G, H |
| `SourceCandidateResolved` | Candidate được đăng ký, trùng, tombstone hoặc bị loại | G, H |
| `CollectionRunStarted` | Lượt thu thập bắt đầu | G, H |
| `CollectedDocumentAvailable` | Có document package đủ điều kiện giao B | B, G |
| `CollectionRunCompleted` | Lượt kết thúc, có thống kê | G, H |
| `CollectionRunFailed` | Lượt thất bại hoặc partial | G, H |

`SourceCandidateResolved` bao gồm kết quả kiểm tra lại từ READY tại registration (CT-SRC-003A), chứa candidate ref/revision, disposition, source/tombstone ref có điều kiện và reason. Ghi cùng transaction với receipt và source/candidate mutation; giao lặp cùng event không giải quyết lại candidate. WAITING_POLICY hoặc REVISION_CONFLICT không phát terminal event. Package sai schema không phát sự kiện document accepted; chỉ package hợp lệ về cấu trúc mới được giao sang B theo CT-SRC-006.

### Phân hệ B — Kho nội dung

| Event | Khi phát | Consumer chính |
|---|---|---|
| `ArticleRevisionAccepted` | Revision bài đại diện được lưu | C, D, G, H |
| `DuplicateDocumentResolved` | Bài trùng được gắn với bài đại diện | C, G, H |
| `EventLinkResolved` | Bài được gắn/tách sự kiện | D, G, H |
| `EventUpdateAccepted` | Có tình tiết/diễn biến mới thật sự | D, G, H |

`DuplicateDocumentResolved` có thể mang `new_media_discovery_refs`; nó không kích hoạt script mới chỉ vì có nguồn đăng lại.

### Phân hệ C — Kho media và hook

| Event | Khi phát | Consumer chính |
|---|---|---|
| `MediaDiscovered` | Phát hiện media cùng provenance | C, I |
| `MediaCataloged` | Asset logic được định danh | D, E, H |
| `MediaAnalysisAccepted` | Metadata phân tích được commit | D, H |
| `MediaRenditionReady` | Có phiên bản sẵn sàng dùng | D, F, G, H |
| `MediaAvailabilityChanged` | Tệp mất/khôi phục/thay trạng thái | D, F, G, H, I |
| `HookImported` | Hook visual/audio được nhập | D, H, I |
| `HookMetadataUpdated` | Tag/trạng thái hook thay đổi | D, H |
| `HookEnabled` | Hook được phép chọn | D, H |
| `HookDisabled` | Hook không được chọn cho job mới | D, H |

### Phân hệ D — Bộ não nội dung AI

| Event | Khi phát | Consumer chính |
|---|---|---|
| `ProductionSnapshotCommitted` | Job khóa nguồn và cấu hình | G, H |
| `StoryAnglesGenerated` | Bộ góc kể được lưu | G, H |
| `ScriptVersionCreated` | Script revision được lưu | E, G, H |
| `ProductionPlanCreated` | Kế hoạch dựng có refs cụ thể | E, F, G, H |
| `VariantValidated` | Biến thể đạt quy tắc khác biệt | G, H |
| `OutputMetadataCreated` | Title và hashtag được tạo | F, G, H |

### Phân hệ E — Xử lý media

| Event | Khi phát | Consumer chính |
|---|---|---|
| `ImageSafetyAssessed` | Ảnh có trạng thái safety | C, D, F, H |
| `MediaProcessingCompleted` | Rendition xử lý được lưu | C, F, G, H, I |
| `VoiceReady` | Voice artifact sẵn sàng | F, G, H, I |
| `WordTimingReady` | Word timing gắn đúng voice/script | F, G, H, I |

### Phân hệ F — Dựng và kiểm tra video

| Event | Khi phát | Consumer chính |
|---|---|---|
| `RenderCompleted` | Render tạo artifact và report | G, H, I |
| `OutputQualityChecked` | Hard gates đã được đánh giá | G, H, I |

### Phân hệ G — Điều phối

| Event | Khi phát | Consumer chính |
|---|---|---|
| `BatchStarted` | Batch bắt đầu | H |
| `JobAllocated` | Video job được tạo | D, H |
| `StageStateChanged` | Stage đổi trạng thái | H |
| `JobWaiting` | Job chờ capability/dependency | H, J |
| `JobFailed` | Job kết thúc lỗi | H |
| `VideoCompleted` | Completion transaction đã commit | H, I |
| `BatchTargetReached` | Đạt số video mục tiêu | H |
| `BatchExhausted` | Không còn việc đủ điều kiện | H |

### Phân hệ I — Lưu trữ

| Event | Khi phát | Consumer chính |
|---|---|---|
| `ArtifactLocationVerified` | Location/hash đã verify | C, E, F, G, H |
| `CleanupAuthorized` | Artifact local được phép xóa | I, H |
| `CleanupCompleted` | Đã xóa hoặc giải phóng local | G, H |
| `StorageHealthChanged` | Quota/availability đổi | G, H, J |

### Phân hệ J — Cấu hình và tích hợp

| Event | Khi phát | Consumer chính |
|---|---|---|
| `ConfigurationRevisionPublished` | Revision mới có hiệu lực | A-G, H |
| `ProviderHealthChanged` | Provider khả dụng/thất bại | G, H |
| `QuotaObserved` | Có quan sát quota/capacity mới | G, H |
| `CredentialChanged` | Secret/account đổi metadata | G, H |

`CredentialChanged` chỉ mang account ID, trạng thái và revision; không mang secret.

## 5. Subscriber và quyền hành động

### CT-EVT-004 — Subscription policy

- Event cho phép consumer biết “đã xảy ra”, không tự trao quyền sửa aggregate producer.
- Consumer muốn thay đổi dữ liệu của producer phải gửi command về owner.
- Projection H có thể rebuild từ dữ liệu owner và event checkpoint.
- G dùng event để đánh thức/tiếp tục workflow nhưng workflow state vẫn là nguồn điều phối bền vững.
- Event lỗi không được đưa thẳng thành user notification nếu chưa qua mapping an toàn.

## 6. Gap, replay và poison event

### CT-EVT-005 — Recovery policy

1. Consumer phát hiện thiếu `aggregate_revision` phải dừng áp dụng aggregate đó và query snapshot hiện tại.
2. Event lặp trả kết quả deduplicated, không tạo side effect lần hai.
3. Event schema không hỗ trợ được đưa vào dead-letter/quarantine có cảnh báo; không bỏ im lặng.
4. Replay dùng cùng `event_id`; side effect ngoài phải kiểm tra receipt cũ.
5. Sau restore, event từ epoch cũ bị quarantine/reconcile và không được mutation trực tiếp. Event an toàn cần áp dụng lại phải được owner tái phát hành hoặc đánh dấu đã reconcile dưới epoch mới; không sửa event lịch sử tại chỗ.

## 7. Acceptance contract

1. Commit dữ liệu nhưng publisher tắt ngay sau đó vẫn phát được event khi hồi phục.
2. Phát cùng event hai lần không tạo hai job hoặc hai artifact.
3. Event đến lệch thứ tự không làm revision cũ ghi đè revision mới.
4. Consumer gặp field/enum mới không crash và không tự đoán hành vi nguy hiểm.
5. Không event nào chứa secret hoặc byte tệp.
6. Bài đăng lại chỉ bổ sung provenance/media, không tự tạo script mới.
7. Event có epoch cũ không được ghi đè trạng thái sau restore dù aggregate revision tình cờ trùng.
