# 03. Workflow và thực thi

> Trạng thái: **Bản thiết kế trước triển khai**  
> Chủ sở hữu điều phối: phân hệ G.  
> Worker thực thi: A, B, C, D, E, F, I, J theo capability.

## 1. Mục tiêu

Hợp đồng này bảo đảm công việc dài hạn có thể chờ, retry, tiếp tục sau desktop offline, cô lập lỗi từng video và không commit nhầm kết quả từ worker cũ.

## 2. Workflow catalog

### CT-WF-001 — Các workflow logic

| Workflow | Mục tiêu | Nơi có thể chạy khi desktop offline |
|---|---|---|
| `DailyCollectionWorkflow` | Chọn nguồn theo Tier và ngưỡng chủ đề, thu thập một lượt/ngày | Cloud |
| `ContentEnrichmentWorkflow` | Chuẩn hóa, chống trùng, liên kết sự kiện, bổ sung media/index | Cloud; bước AI có thể chờ/fallback local |
| `ProductionBatchWorkflow` | Đạt target video hoặc dừng khi hết việc đủ điều kiện | Cloud control; child job có thể chờ desktop |
| `VideoProductionWorkflow` | Một video từ snapshot đến completion | Cloud control + desktop activities |
| `DebugStageWorkflow` | Chạy một stage có quan sát, không tự đi tiếp | Theo capability stage |
| `MaintenanceWorkflow` | Reconcile artifact, quota, cleanup, backup/restore checks | Cloud + desktop khi online |

`VideoProductionWorkflow` là child workflow hoặc đơn vị cô lập tương đương để một video lỗi không làm dừng toàn bộ batch.

## 3. Task queue logic

### CT-WF-002 — Capability routing

| Task queue logic | Năng lực |
|---|---|
| `control-workflows` | Điều phối bền vững, không chạy xử lý nặng |
| `cloud-io` | RSS/web fetch, metadata, Drive/API I/O |
| `cloud-ai` | AI provider được phép chạy cloud |
| `desktop-cpu` | Phân tích/xử lý CPU local |
| `desktop-gpu` | Model local/GPU task |
| `desktop-render` | FFmpeg/render/QC trên desktop |

Tên queue vật lý là **CẤU HÌNH**. Nhiều queue có thể nằm cùng process ban đầu, nhưng capability và retry policy vẫn phải tách logic.

## 4. Lệnh thực thi

### CT-WF-003 — `ActivityRequest`

| Trường | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `workflow_id`, `workflow_run_id` | Có | Workflow gọi activity |
| `video_job_id` | Khi thuộc video | Job được xử lý |
| `stage_run_id` | Có | Lần chạy stage |
| `activity_name`, `activity_version` | Có | Năng lực cần thực thi |
| `execution_grant` | Có với side effect/commit | Quyền thực thi có fencing |
| `input_refs` | Có | Resource/artifact/config revision bất biến |
| `operation_key` | Có | Khóa idempotency của side effect |
| `deadline_at` | Khi có | Deadline UTC |
| `capability_requirements` | Có | CPU/GPU/tool/provider/storage cần thiết |
| `retry_policy_ref` | Có | Policy đã version hóa |

Payload workflow không chứa blob, secret dài hạn hoặc toàn bộ article/script nếu có thể dùng revision ref.

## 5. Execution grant và fencing

### CT-WF-004 — `ExecutionGrant`

| Trường | Ý nghĩa |
|---|---|
| `grant_id` | ID quyền thực thi |
| `stage_run_id` | Stage được phép ghi kết quả |
| `execution_generation` | Số thế hệ tăng khi reassign/retry cần fencing |
| `recovery_epoch` | Epoch opaque hiện hành khi cấp grant |
| `worker_lease_id` | Worker/lease hiện tại |
| `issued_at`, `expires_at` | Hiệu lực |
| `allowed_operation` | Loại side effect/commit được phép |
| `input_fingerprint` | Hash của toàn bộ refs/input logic |

Owner chỉ chấp nhận result khi:

1. `grant_id` còn hợp lệ;
2. `execution_generation` bằng generation hiện tại;
3. `recovery_epoch` bằng epoch hiện hành do control plane có thẩm quyền cung cấp;
4. `input_fingerprint` khớp;
5. operation chưa có receipt thành công khác biệt.

Kết quả từ generation cũ trả `STALE_EXECUTION_GENERATION` và không làm thay đổi aggregate.
Kết quả từ epoch cũ trả `STALE_RECOVERY_EPOCH`; generation trùng sau restore không làm epoch cũ hợp lệ.

## 6. Operation receipt

### CT-WF-005 — `OperationReceipt`

| Trường | Ý nghĩa |
|---|---|
| `operation_key` | ID idempotency của side effect |
| `operation_type` | upload, provider call, render, write output... |
| `input_fingerprint` | Hash input logic |
| `recovery_epoch` | Epoch tại lúc operation được cấp quyền |
| `state` | `prepared`, `started`, `outcome_unknown`, `succeeded`, `failed` |
| `external_operation_ref` | ID ngoài đã redacted nếu có |
| `output_refs` | Kết quả đã verify |
| `attempt` | Số lần thử kỹ thuật |
| `started_at`, `observed_at`, `finished_at` | Thời gian |
| `problem` | Lỗi chuẩn nếu có |

Trước khi retry một operation có side effect:

- nếu receipt `succeeded`, trả lại output cũ;
- nếu `outcome_unknown`, reconcile trước, không thực hiện lại mù;
- nếu `failed` và retryable, tạo attempt mới cùng operation key;
- nếu input fingerprint khác, phải tạo operation key mới.

## 7. Kết quả activity

### CT-WF-006 — `ActivityResult`

| Trường | Ý nghĩa |
|---|---|
| `stage_run_id`, `grant_id`, `execution_generation`, `recovery_epoch` | Fencing identity |
| `disposition` | `succeeded`, `failed`, `waiting`, `outcome_unknown`, `stale` |
| `output_refs` | Revision/artifact/report refs |
| `metrics` | Duration, usage, throughput, kích thước |
| `warnings` | Cảnh báo có mã, không thay cho failure |
| `problem` | Lỗi chuẩn |
| `operation_receipt_ref` | Receipt của side effect nếu có |
| `completed_at` | Thời điểm worker quan sát kết thúc |

Workflow chỉ chuyển stage thành `SUCCEEDED` sau khi owner của output xác nhận commit.

## 8. Heartbeat, timeout và waiting

### CT-WF-007 — Quy tắc sống còn

- Heartbeat báo tiến độ và checkpoint kỹ thuật; không phải commit nghiệp vụ.
- Timeout schedule-to-start phản ánh thiếu capability; không nên đốt hết retry bằng cách khởi chạy giả.
- Khi desktop/provider unavailable, stage chuyển `WAITING_CAPABILITY` và workflow chờ signal/event phù hợp.
- Theo R18, các stage tạo script, production plan và voice chỉ bắt đầu khi desktop production capability đang hoạt động; tin, media và chỉ mục vẫn có thể tiếp tục được thu thập/làm giàu trên cloud.
- Timeout start-to-close và heartbeat là **CẤU HÌNH theo activity**, không dùng một giá trị chung.
- Worker mất lease không được commit dù tiếp tục chạy ở nền.
- Chờ dài không giữ tệp staging chưa cần thiết; materialize gần lượt chạy.

## 9. Retry, tạo lại và tạo biến thể

### CT-WF-008 — Ba ngữ nghĩa khác nhau

| Hành động | Giữ job | Giữ snapshot | Giữ intent | Output revision |
|---|---:|---:|---:|---:|
| Retry kỹ thuật | Có | Có | Có | Có thể tạo attempt/version kỹ thuật mới |
| Tạo lại từ stage | Có | Có | Có | Tạo revision downstream mới, vô hiệu refs cũ |
| Tạo biến thể mới | Không | Có thể dùng cùng nguồn snapshot nhưng snapshot job mới | Không | Tạo script/plan/output mới |

Tạo lại không được âm thầm đổi provider/prompt/config nếu điều đó làm thay đổi intent. Mọi fallback có khả năng thay đổi nội dung phải được ghi trong snapshot hoặc tạo revision mới theo policy.

## 10. Versioning workflow

### CT-WF-009 — Tương thích khi triển khai

- Workflow đang chạy phải tiếp tục theo version logic đã ghi.
- Activity result có version riêng; worker mới phải hiểu version đang còn hiệu lực.
- Thay đổi thứ tự stage, retry semantics hoặc completion invariant là breaking workflow change.
- Thay Temporal bằng công cụ khác chỉ được phép khi vẫn giữ các application contract, grant, receipt và state semantics này.

## 11. Acceptance contract

1. Desktop tắt ở bất kỳ stage local nào, job chờ và tiếp tục đúng stage khi online.
2. Worker cũ hoàn thành muộn không ghi đè output của generation mới.
3. Timeout sau external side effect không tạo side effect lần hai trước reconcile.
4. Một child video lỗi không dừng các video còn lại trong batch.
5. Debug stage không tự kích hoạt stage kế tiếp.
6. Retry kỹ thuật không được tính là video/biến thể mới.
7. Sau restore, result có grant/generation trùng nhưng epoch cũ vẫn bị từ chối cho tới khi reconcile cấp grant mới.
