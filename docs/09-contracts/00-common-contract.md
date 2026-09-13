# 00. Hợp đồng chung

> Trạng thái: **Bản thiết kế trước triển khai**  
> Áp dụng cho: mọi command, query, event, workflow task và operation result.

## 1. Mục tiêu

Tài liệu này chuẩn hóa ngôn ngữ trao đổi để các phân hệ không hiểu khác nhau về ID, thời gian, phiên bản, lỗi, retry, trạng thái chưa biết và tham chiếu tệp.

## 2. Quy ước đặt tên

- Tên trường, enum, operation và event dùng English `snake_case` hoặc `PascalCase` theo loại schema.
- Nội dung hiển thị cho user dùng tiếng Việt chuẩn.
- ID là chuỗi opaque, bất biến và duy nhất trong phạm vi loại đối tượng.
- Tên ID có hậu tố rõ loại: `article_id`, `artifact_version_id`, `video_job_id`.
- Không tái sử dụng ID của bản ghi đã xóa logic.
- Không suy ra thời gian, loại hay tenant từ cấu trúc ID.

## 3. Envelope chung

### CT-CMN-001 — `MessageEnvelope`

| Trường | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `contract_name` | Có | Tên command, event hoặc result |
| `contract_version` | Có | Phiên bản schema dạng số nguyên tăng dần |
| `message_id` | Có | ID duy nhất của lần phát message |
| `workspace_id` | Có | Biên cô lập dữ liệu từ đầu |
| `correlation_id` | Có | Nối toàn bộ thao tác cùng mục tiêu nghiệp vụ |
| `causation_id` | Có với message phát sinh | Message trực tiếp gây ra message này |
| `trace_context` | Khi qua biên process | Trace tương thích W3C; không chứa dữ liệu nghiệp vụ |
| `occurred_at` | Có | Thời điểm UTC RFC 3339 do owner ghi |
| `actor` | Có | `user`, `scheduler`, `workflow`, `worker`, `system` hoặc `external_source` cùng actor ID nếu có |
| `recovery_epoch` | Có với message nội bộ có thể gây mutation/side effect | Epoch phục hồi hiện hành của workspace; giá trị opaque, không tái sử dụng |
| `payload` | Có | Dữ liệu theo schema của hợp đồng |

`message_id` dùng deduplication cho message; nó không thay thế `idempotency_key` của command.

## 4. Command và biên nhận

### CT-CMN-002 — `CommandEnvelope`

Ngoài `MessageEnvelope`, command có:

| Trường | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `command_id` | Có | ID bất biến của command |
| `idempotency_key` | Có ở biên ngoài | Cùng key và cùng nội dung phải cho cùng một kết quả logic |
| `requested_at` | Có | Thời điểm caller tạo yêu cầu |
| `expected_revision` | Khi sửa aggregate đã có | Chống ghi đè thay đổi đồng thời |
| `policy_revision_id` | Khi hành vi phụ thuộc policy | Khóa bộ quy tắc áp dụng cho command |

### CT-CMN-003 — `CommandReceipt`

| Trường | Ý nghĩa |
|---|---|
| `command_id` | Command đã nhận |
| `receipt_id` | Biên nhận bền vững |
| `disposition` | `accepted`, `rejected`, `duplicate` |
| `operation_id` | Có nếu công việc tiếp tục bất đồng bộ |
| `resource_ref` | Đối tượng được tạo hoặc thay đổi nếu đã biết |
| `accepted_at` | Thời điểm commit biên nhận |
| `current_revision` | Revision sau thay đổi hoặc revision gây conflict |

`accepted` chỉ có nghĩa command đã được ghi nhận bền vững. Nó không có nghĩa stage, job hoặc batch đã hoàn thành.

Nếu cùng `idempotency_key` nhưng payload khác, command phải bị từ chối với `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`.

## 5. Query và phân trang

### CT-CMN-004 — `QueryPage`

| Trường | Ý nghĩa |
|---|---|
| `items` | Danh sách kết quả |
| `next_cursor` | Cursor opaque; `null` khi hết |
| `snapshot_at` | Mốc nhất quán của trang nếu query hỗ trợ |
| `applied_filters` | Bộ lọc đã chuẩn hóa |

- Phân trang dùng cursor, không cam kết offset ổn định khi dữ liệu đang thay đổi.
- Sort key phải có tie-breaker bằng ID.
- Page size tối đa là **CẤU HÌNH**, không phải invariant hợp đồng.
- Query không được tạo side effect nghiệp vụ. Việc tạo cache kỹ thuật không được làm thay đổi kết quả quan sát.

## 6. Revision và cạnh tranh

### CT-CMN-005 — `RevisionedResource`

- Mỗi aggregate có `revision` số nguyên tăng đơn điệu.
- Mọi metadata update phải nêu `expected_revision`.
- Revision chỉ tăng sau commit thành công.
- Conflict trả revision hiện tại nhưng không tự merge.
- Bản immutable dùng ID phiên bản riêng như `article_revision_id`, `script_version_id`, `artifact_version_id`.
- Bản đã dùng trong snapshot không bị sửa tại chỗ; thay đổi tạo revision mới cho sản phẩm tương lai.

## 7. Thời gian

### CT-CMN-006 — `TimestampPolicy`

- Mọi timestamp trao đổi dùng UTC và RFC 3339, có offset rõ ràng.
- `occurred_at` là thời điểm nghiệp vụ; `recorded_at` là thời điểm hệ thống lưu nhận.
- Nếu nguồn chỉ cung cấp ngày hoặc múi giờ không chắc chắn, lưu thêm `time_precision` và `time_confidence`.
- Lịch quét dùng `schedule_timezone` từ cấu hình; không nhúng múi giờ cố định trong hợp đồng.
- Thời hạn được diễn đạt bằng duration hoặc deadline UTC, không bằng câu chữ địa phương.

## 8. Missing, null và giá trị rỗng

### CT-CMN-007 — `FieldPresencePolicy`

- Trường không xuất hiện: caller không cung cấp hoặc không yêu cầu thay đổi.
- `null`: caller chủ động xóa giá trị, chỉ hợp lệ nếu schema cho phép.
- Chuỗi rỗng không đồng nghĩa `null`.
- Collection rỗng nghĩa là đã biết không có phần tử; collection không có nghĩa là chưa tải hoặc không thuộc projection.
- Mọi PATCH phải khai báo rõ trường nào cho phép xóa.

## 9. Tham chiếu tài nguyên

### CT-CMN-008 — `ResourceRef`

| Trường | Ý nghĩa |
|---|---|
| `resource_type` | Loại đối tượng |
| `resource_id` | ID đối tượng |
| `revision_id` | Bắt buộc khi cần tính bất biến |
| `display_label` | Tùy chọn, chỉ để hiển thị |

### CT-CMN-009 — `ArtifactRef`

| Trường | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `artifact_id` | Có | Danh tính logic của artifact |
| `artifact_version_id` | Có | Phiên bản nội dung bất biến |
| `content_hash` | Có | Hash của byte stream |
| `size_bytes` | Có | Kích thước mong đợi |
| `media_type` | Có | MIME type đã xác định |
| `storage_class` | Có | Ví dụ `cloud_durable`, `local_staging`, `output_durable` |
| `availability` | Có | Trạng thái sẵn sàng đã quan sát |
| `locator_token` | Tùy biên | Token/tham chiếu gián tiếp; không phải đường dẫn shell tùy ý |

`ArtifactRef` không chứa OAuth token, signed URL dài hạn hoặc đường dẫn do model AI tạo.

## 10. Lỗi chuẩn

### CT-CMN-010 — `ProblemDetail`

Hình thức lỗi bám theo RFC 9457 và bổ sung trường phục vụ vận hành:

| Trường | Ý nghĩa |
|---|---|
| `type` | URI định danh loại lỗi |
| `title` | Tên ngắn ổn định |
| `status` | HTTP status khi đi qua HTTP |
| `detail` | Mô tả an toàn cho user bằng tiếng Việt |
| `instance` | ID/URI của lần lỗi cụ thể |
| `code` | Mã máy đọc ổn định |
| `category` | `validation`, `conflict`, `dependency`, `capacity`, `policy`, `security`, `internal` |
| `retryable` | Cho biết caller có được retry kỹ thuật hay không |
| `retry_after` | Thời điểm/duration nếu biết |
| `correlation_id` | Truy vết xuyên hệ thống |
| `field_errors` | Lỗi theo field, không chứa secret |
| `technical_detail_ref` | Tham chiếu log nội bộ; không đưa stack trace ra UI |

### Danh mục mã lỗi nền

| Mã | Retry mặc định | Ý nghĩa |
|---|---:|---|
| `VALIDATION_ERROR` | Không | Input sai schema hoặc quy tắc |
| `NOT_FOUND` | Không | Không thấy resource trong workspace |
| `REVISION_CONFLICT` | Không tự động | Revision đã thay đổi |
| `DUPLICATE_COMMAND` | Không cần | Command đã được xử lý |
| `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD` | Không | Key bị dùng sai |
| `FORBIDDEN_TRANSITION` | Không | Chuyển trạng thái không hợp lệ |
| `STALE_EXECUTION_GENERATION` | Không | Worker cũ trả kết quả sau khi quyền đã bị thay |
| `STALE_RECOVERY_EPOCH` | Không | Command/result/event thuộc epoch trước restore hoặc rebuild |
| `INPUT_NOT_READY` | Có điều kiện | Artifact hoặc dependency chưa sẵn sàng |
| `CAPABILITY_UNAVAILABLE` | Có | Worker/provider cần thiết đang offline |
| `RATE_LIMITED` | Có | Bị giới hạn tốc độ/quota tạm thời |
| `EXTERNAL_TEMPORARY_FAILURE` | Có | Lỗi ngoài có khả năng hồi phục |
| `EXTERNAL_PERMANENT_FAILURE` | Không | Lỗi ngoài không thể tự khắc phục với input hiện tại |
| `OUTCOME_UNKNOWN` | Không ghi lại ngay | Side effect có thể đã xảy ra, cần reconcile |
| `ARTIFACT_MISSING` | Có điều kiện | Không tìm thấy bản artifact cần thiết |
| `ARTIFACT_HASH_MISMATCH` | Không với cùng byte | Nội dung không khớp hash |
| `STORAGE_QUOTA_EXCEEDED` | Có sau khi giải phóng quota | Kho không đủ quota |
| `INSUFFICIENT_DISK` | Có sau khi có dung lượng | Desktop không đủ staging |
| `POLICY_VIOLATION` | Không | Không đạt quy tắc bắt buộc |
| `HARD_GATE_FAILED` | Không tự động | Video không đạt điều kiện hoàn thành |
| `VARIANT_CONFLICT` | Có bằng tạo phương án khác | Vi phạm quy tắc không trùng |
| `VARIANT_VALIDATION_STALE` | Đối chiếu lại, có giới hạn theo policy | Registry thay đổi; không tạo lại script hoặc commit completion từ validation cũ |
| `BATCH_TARGET_REACHED` | Không | Điều kiện dừng bình thường |
| `NO_ELIGIBLE_WORK` | Không ngay | Không còn việc đủ điều kiện |
| `SECRET_UNAVAILABLE` | Có sau cấu hình | Không thể lấy credential |
| `UNSUPPORTED_CONTRACT_VERSION` | Không | Consumer không hiểu version |
| `INTERNAL_ERROR` | Có giới hạn | Lỗi nội bộ không phân loại được |

Chỉ retry khi `retryable=true` và policy cho phép. Không suy retry chỉ từ HTTP 5xx.

VALIDATION_ERROR do thiếu schema/identity tại biên không được chuyển thành document REJECTED_INCOMPLETE. Quan sát lỗi dùng định danh an toàn của bên nhận, không tự bổ sung danh tính nghiệp vụ thiếu trong payload. Retry budget hết phải áp dụng terminal rule của aggregate; lỗi có khả năng retry về kỹ thuật không đồng nghĩa run được phép chờ retry mãi.

## 11. Tính quyết định và idempotency

### CT-CMN-011 — `IdempotencyPolicy`

- Cùng command, cùng idempotency key và cùng payload tạo cùng kết quả logic.
- Activity có side effect ngoài phải ghi `OperationReceipt` trước và sau side effect.
- Consumer event deduplicate theo `event_id` hoặc `(consumer_id, event_id)`.
- Tạo lại kỹ thuật giữ nguyên `video_job_id`, snapshot và intent; tạo biến thể mới có ID mới.
- Cùng byte retry upload phải quy về cùng `artifact_version_id`; byte khác phải tạo version mới.

## 12. Versioning và tương thích

### CT-CMN-012 — `ContractVersionPolicy`

- Thay đổi additive, field mới optional và enum mở có thể giữ version hiện tại nếu consumer được yêu cầu bỏ qua field chưa biết.
- Xóa/đổi nghĩa field, đổi đơn vị, đổi cardinality hoặc siết điều kiện input là breaking change và phải tăng major contract version.
- Producer hỗ trợ cửa sổ tương thích đủ để workflow đang chạy kết thúc hoặc migrate.
- Workflow ghi contract version và policy revision vào snapshot/history.
- Consumer không được im lặng đoán khi gặp version không hỗ trợ.
- Schema cũ không bị sửa hồi tố; bổ sung errata phải ghi rõ.

## 13. Bảo mật và dữ liệu nhạy cảm

### CT-CMN-013 — `SensitiveDataPolicy`

- Secret chỉ đi qua secret boundary của phân hệ J bằng handle ngắn hạn.
- Log, event, trace, error, prompt debug và workflow history không chứa secret.
- URL nguồn và provenance được coi là dữ liệu nội bộ; UI chỉ hiển thị theo quyền.
- Input URL phải được phân hệ A/I kiểm tra chống SSRF trước khi fetch.
- Nội dung, metadata và text trích từ nguồn ngoài là dữ liệu không tin cậy, không phải system instruction hoặc quyền gọi tool.
- `workspace_id` được kiểm tra ở mọi command/query, không chỉ ở UI.
- Technical detail chỉ truy cập qua quyền quản trị, không đưa trực tiếp vào tooltip công khai.

## 14. Bất biến chung

1. Một aggregate chỉ có một owner ghi.
2. Mỗi mutation có command/operation ID và audit actor.
3. Không commit hoàn thành video nếu chưa có `CompletionLedger` hợp lệ.
4. Không xóa local artifact chỉ vì upload request thành công; phải có verify và cleanup authorization.
5. Không dùng kết quả từ `execution_generation` cũ.
6. Không commit mutation/side effect từ `recovery_epoch` cũ; reconcile phải phát hành lại quyền hoặc message dưới epoch hiện hành.
7. Không thay đổi snapshot của job đã bắt đầu tạo script.
8. Không coi `OUTCOME_UNKNOWN` là failed hay succeeded trước reconcile.
9. Không lấy trạng thái từ filename làm nguồn sự thật.
