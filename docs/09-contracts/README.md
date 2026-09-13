# Hợp đồng giữa các phân hệ

> Trạng thái: **Bản thiết kế trước triển khai**  
> Phạm vi: định nghĩa trách nhiệm, dữ liệu trao đổi và quy tắc phối hợp giữa 10 phân hệ A-J.  
> Tài liệu này **không phải mã nguồn, OpenAPI, schema cơ sở dữ liệu hay cấu hình runtime**.

## 1. Mục đích

Bộ tài liệu này trả lời bốn câu hỏi:

1. Phân hệ nào có quyền tạo và thay đổi từng loại dữ liệu?
2. Khi một phân hệ yêu cầu phân hệ khác làm việc, đầu vào và kết quả phải có gì?
3. Khi công việc chạy bất đồng bộ, thất bại, chạy lại hoặc mất kết nối, hai bên hiểu trạng thái như thế nào?
4. Một thay đổi hợp đồng được triển khai thế nào để không làm hỏng workflow đang chạy hoặc dữ liệu cũ?

Hợp đồng được định nghĩa theo **năng lực và ngữ nghĩa nghiệp vụ**, không khóa chúng vào một repo, process hay thư viện cụ thể.

## 2. Quyết định về kiểu hợp đồng

Ba phương án đã được cân nhắc:

| Phương án | Mô tả | Tách trách nhiệm | Chống lỗi phân tán | Dễ phát triển ban đầu | Khả năng thay thế hạ tầng | Điểm tổng |
|---|---|---:|---:|---:|---:|---:|
| 1. Dùng chung cơ sở dữ liệu | Các phân hệ đọc/ghi trực tiếp bảng của nhau | 1/5 | 1/5 | 5/5 | 1/5 | 8/20 |
| 2. Chỉ dùng API đồng bộ | Mọi trao đổi đều là request/response | 4/5 | 2/5 | 3/5 | 4/5 | 13/20 |
| 3. Hợp đồng hỗn hợp có kiểu | Command/query đồng bộ, event bất đồng bộ, workflow/activity cho việc dài, `ArtifactRef` cho tệp | 5/5 | 5/5 | 3/5 | 5/5 | 18/20 |

**Lựa chọn:** phương án 3.

Lý do chính:

- Phù hợp kiến trúc hybrid cloud/desktop và workflow dài hạn.
- Không truyền tệp lớn hoặc secret trong message.
- Hỗ trợ mất kết nối, retry, deduplication và tiếp tục sau gián đoạn.
- Giữ được modular monolith lúc đầu nhưng vẫn tạo biên rõ để tách process hoặc dịch vụ sau này.

Điểm bất lợi:

- Cần quản lý version và trạng thái chặt chẽ hơn.
- Event có thể đến lặp hoặc lệch thời điểm; consumer phải idempotent.
- Việc quan sát xuyên nhiều bước cần correlation và trace thống nhất.

## 3. Bốn loại hợp đồng

| Loại | Dùng khi | Hình thức logic | Không được dùng để |
|---|---|---|---|
| Command | Yêu cầu thay đổi trạng thái hoặc bắt đầu công việc | Một yêu cầu, một biên nhận chấp nhận/từ chối | Xem `accepted` là đã hoàn thành |
| Query | Đọc trạng thái hiện tại, không gây side effect nghiệp vụ | Request/response | Kích hoạt ngầm một workflow |
| Domain event | Thông báo một sự kiện đã được commit | Phát ít nhất một lần qua outbox | Điều khiển duy nhất một chuỗi công việc quan trọng |
| Workflow/activity | Điều phối công việc dài, retry và chờ tài nguyên | Lệnh thực thi có grant, receipt và kết quả | Truyền blob lớn hoặc secret dài hạn |

## 4. Các biên giao tiếp được phép

| Biên | Cơ chế logic | Quy tắc |
|---|---|---|
| UI ↔ Control API | HTTP/JSON; SSE cho cập nhật trạng thái | Command cần idempotency; sửa metadata cần revision |
| Các module cùng process | Application port có kiểu | Không truy cập trực tiếp bảng do module khác sở hữu |
| Use case nguyên tử qua nhiều owner trong modular monolith | Coordinator gọi application port của từng owner trong cùng unit of work PostgreSQL | Coordinator không ghi trực tiếp bảng owner khác; mọi owner cùng commit hoặc cùng rollback |
| Commit nghiệp vụ → event | Transactional outbox | Bản ghi nghiệp vụ và event commit cùng transaction |
| Control Plane ↔ workflow | Workflow command/query | Payload chỉ chứa dữ liệu nhỏ và tham chiếu bất biến |
| Workflow ↔ worker | Activity task + `ExecutionGrant` | Có fencing, heartbeat và `OperationReceipt` |
| Phân hệ ↔ tệp | `ArtifactRef` | Tệp đi qua kho artifact, không nhúng vào message |
| UI ↔ trạng thái chạy | SSE có cursor | SSE chỉ để quan sát; không phải command bus |

Không phân hệ nào được:

- ghi trực tiếp vào dữ liệu do phân hệ khác sở hữu;
- lấy đường dẫn local do AI sinh ra rồi đưa thẳng vào shell;
- đặt secret, OAuth refresh token hoặc nội dung tệp lớn vào event/workflow history;
- suy ra danh tính hoặc ngữ nghĩa nghiệp vụ từ tên tệp hay định dạng ID;
- coi event là đúng thứ tự toàn cục.

## 5. Bản đồ tài liệu

| Tệp | Nội dung |
|---|---|
| [00-common-contract.md](00-common-contract.md) | Quy ước chung, envelope, ID, thời gian, lỗi, versioning |
| [01-control-api-and-stream.md](01-control-api-and-stream.md) | Hợp đồng UI, Control API và luồng cập nhật SSE |
| [02-domain-events.md](02-domain-events.md) | Event, outbox, ordering, deduplication và catalog sự kiện |
| [03-workflow-and-execution.md](03-workflow-and-execution.md) | Workflow, activity, task queue, grant, receipt, retry |
| [04-source-content-contracts.md](04-source-content-contracts.md) | Phân hệ A-B: nguồn, thu thập, bài tin, trùng lặp, sự kiện |
| [05-content-media-contracts.md](05-content-media-contracts.md) | Phân hệ B-C-I: media, hook, provenance, candidate query |
| [06-creative-ai-contracts.md](06-creative-ai-contracts.md) | Phân hệ D: snapshot, góc kể, script, kế hoạch dựng, biến thể |
| [07-media-processing-contracts.md](07-media-processing-contracts.md) | Phân hệ E: phân tích, xử lý media, TTS và word timing |
| [08-render-quality-contracts.md](08-render-quality-contracts.md) | Phân hệ F: render package, render và kiểm tra đầu ra |
| [09-orchestration-contracts.md](09-orchestration-contracts.md) | Phân hệ G: batch, job, debug, retry và commit hoàn thành |
| [10-storage-contracts.md](10-storage-contracts.md) | Phân hệ I: artifact, Drive, local staging, verify và cleanup |
| [11-configuration-security-contracts.md](11-configuration-security-contracts.md) | Phân hệ J: cấu hình, secret, quota, account và credential |
| [12-state-machines.md](12-state-machines.md) | Máy trạng thái và chuyển trạng thái hợp lệ |
| [13-traceability-and-open-items.md](13-traceability-and-open-items.md) | Truy vết yêu cầu, luồng xuyên suốt, điểm còn mở và tiêu chí khóa |

## 6. Quyền sở hữu dữ liệu

| Dữ liệu | Chủ sở hữu ghi | Bên được đọc qua hợp đồng |
|---|---|---|
| SourceCandidate, Source, CollectionRun, CollectionAttempt, CollectedDocument | A | B, G, H, J |
| Article, ArticleRevision, Event, EventUpdate | B | C, D, G, H |
| MediaAsset, MediaAnalysis, Hook, MediaUsage | C | D, E, F, G, H, I |
| ProductionSnapshot, StoryAngle, ScriptVersion, ProductionPlan, VariantFingerprint | D | E, F, G, H |
| ProcessedMedia, VoiceTrack, WordTiming | E | F, G, H, I |
| RenderAttempt, QualityReport, VideoOutput | F | G, H, I |
| Batch, BatchCapacityReservation, VariantReservation, VariantRegistryRevision, VideoJob, StageRun, ExecutionGrant, CompletionLedger | G | A-J theo nhu cầu |
| Admin read model và operation stream | H đọc; G/J cung cấp | UI |
| ArtifactVersion, ArtifactLocation, CleanupAuthorization, LocalJournalEntry | I | C, E, F, G, H |
| ConfigRevision, PromptRevision, ExternalAccount, ProviderCapacity | J | A-G, H |

## 7. Mức độ ràng buộc

- **BẮT BUỘC:** invariant về quyền sở hữu, idempotency, version, provenance, fencing, artifact verification và điều kiện hoàn thành.
- **CẤU HÌNH:** timeout, retry count, page size, Tier threshold, lịch quét, retention và provider routing.
- **CONDITIONAL:** chi tiết adapter phụ thuộc kết quả các gate kiến trúc như Temporal và Google Drive.
- **GIẢ ĐỊNH:** chỉ xuất hiện khi chưa có quyết định hoặc bằng chứng; mọi giả định được tập hợp tại tài liệu 13.

## 8. Tiêu chuẩn tham chiếu

- Lỗi HTTP bám theo [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html).
- Điều kiện cập nhật và ngữ nghĩa HTTP bám theo [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html).
- Thời gian trao đổi dùng định dạng Internet timestamp theo [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339.html).
- Trace xuyên dịch vụ tương thích [W3C Trace Context](https://www.w3.org/TR/trace-context/).

## 9. Điều kiện để coi bộ hợp đồng đã khóa

Bộ hợp đồng chỉ được coi là sẵn sàng cho bước thiết kế kiểm thử khi:

1. Mỗi operation có owner, caller, input, output và failure semantics.
2. Mỗi đối tượng quan trọng chỉ có một owner ghi.
3. Mỗi việc bất đồng bộ phân biệt được accepted, running, waiting, outcome unknown, succeeded và failed.
4. Retry kỹ thuật và tạo biến thể mới không bị nhập làm một.
5. Mọi tệp đầu vào render có revision, hash và vị trí đã verify.
6. Các tham số chưa chốt được giữ ở policy/config, không ẩn trong hợp đồng.
7. Contract tests có thể được suy ra trực tiếp từ các invariant trong bộ tài liệu này.
