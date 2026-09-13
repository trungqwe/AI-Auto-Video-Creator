# 09. Hợp đồng điều phối batch, job và stage

> Trạng thái: **Bản thiết kế trước triển khai**  
> Chủ sở hữu: G.  
> Mục tiêu: biến mục tiêu sản xuất thành workflow có thể quan sát, tiếp tục và kết thúc đúng lý do.

## 1. Đối tượng sở hữu

G sở hữu:

- `ProductionBatch`;
- `VideoJob`;
- `StageRun`;
- `ExecutionGrant`;
- `CommandReceipt` và operation projection;
- `CompletionLedger`;
- `BatchCapacityReservation`;
- `VariantReservation` và revision của sổ đối chiếu biến thể;
- quyết định waiting/retry/failure và lý do batch dừng.

G không sở hữu output nghiệp vụ của A-F/I/J và không được tự sửa chúng.

## 2. Bắt đầu lô

### CT-ORC-001 — `StartProductionBatch`

Input:

- `target_completed_videos` do user đặt;
- subject/topic scope;
- production policy/config revision;
- mode auto mặc định hoặc debug/manual selection;
- app session ref;
- cost/capacity constraints;
- idempotency key.

Output:

- batch ID/revision;
- accepted operation;
- target và effective policy refs;
- initial status.

Bất biến:

- Target tính video đã commit hoàn thành, không tính render attempt hoặc QC pass chưa sync.
- Hệ thống tái khai thác tin đủ điều kiện cho tới khi đạt target hoặc không còn việc đủ điều kiện.
- Batch không quay lại từ tin đầu tiên sau restart; dùng checkpoint/allocation ledger.

## 3. Phân bổ video job

### CT-ORC-002 — `AllocateVideoJob`

Input:

- batch ref;
- eligible article/event/update candidate;
- production mode;
- angle slot trong lượt;
- recent history/exclusions;
- policy revision.

Output:

- video job ID;
- capacity reservation ID;
- eligibility/allocation reason;
- intended source scope;
- expected variant class;
- first stage ref.

Allocation phải khóa batch và tạo `BatchCapacityReservation` trong cùng transaction. Chỉ cấp job khi `completed_count + active_capacity_reservations < target_completed_videos`. Reservation thuộc đúng một job, giữ nguyên khi job `WAITING`, được chuyển thành completion khi job hoàn thành, và chỉ được giải phóng khi job kết thúc lỗi/hủy rõ ràng hoặc allocation bị rollback. Retry cùng job không tạo reservation mới.

Một sự kiện/tin trong một lượt chỉ tạo 1-3 job và các job này phải khác góc kể. Sau khi đi hết vòng tin đủ điều kiện, G mới quay lại tái khai thác theo policy.

## 4. Stage contract

### CT-ORC-012 — `ReserveVariant` / `ReleaseVariant`

Đây là giữ chỗ nội dung, độc lập với suất số lượng `BatchCapacityReservation`. G sở hữu reservation; D sở hữu chữ ký và bằng chứng khác biệt. Không thay ownership của C đối với `MediaUsage`.

- Input giữ chỗ: job/snapshot, tập article/event refs và round ID đã khóa, script/plan revisions, chữ ký nội dung chuẩn hóa của D, variation policy revision, validation ref theo CT-AI-008, expected variant registry revision, idempotency key và grant hợp lệ.
- Output: reservation ID/revision, trạng thái `ACTIVE`, registry revision sau commit và receipt; hoặc `VARIANT_CONFLICT`/`VARIANT_VALIDATION_STALE` không tạo reservation.
- Sổ đối chiếu có revision do G quản lý trong workspace. Mọi tạo/chuyển/release reservation và completion làm tăng revision trong cùng transaction. Baseline khóa ngắn hàng revision theo workspace để kiểm tra compare-and-swap; không gọi AI hoặc giữ khóa trong lúc render. Revision này là token đồng thời, không phải bản sao lịch sử hay một database mới.
- D lấy tập completed và active reservations liên quan article/event, kể cả lô khác, tại một registry revision nhất quán. So sánh thêm góc kể trong round; không tính reservation của chính job là trùng với nó. G chỉ giữ chỗ nếu validation hợp lệ và revision vẫn khớp. Nếu revision thay đổi, trả stale để D đối chiếu lại, không tái tạo script.
- Mỗi job có tối đa một active reservation, ràng buộc đúng đầu vào. Retry cùng key/input trả receipt cũ; input khác bị conflict. Snapshot cố định tập phạm vi so sánh; việc B liên kết lại sự kiện không âm thầm đổi phạm vi của job đang chạy.
- Reserve sau vòng điều chỉnh plan và trước render; các bản draft trước mốc này chưa có reservation. Thay đầu vào sau reserve phải theo lệnh biến thể mới/terminal, không giả làm retry kỹ thuật.
- `ACTIVE` giữ nguyên khi chờ, desktop offline hoặc lease thực thi hết hạn. Không có TTL tự giải phóng nội dung. Terminal lỗi/hủy đã được G ghi nhận mới chuyển `RELEASED` trong cùng transaction với job và trả capacity; completion chuyển `CONVERTED`. Receipt cũ không có nghĩa reservation đã release/convert trở lại ACTIVE.
- Trước completion, D đối chiếu chữ ký thực tế của script/voice/media/timeline/output với lịch sử và active reservations ở revision mới nhất. Bằng chứng gắn exact output hash và reservation ID. G kiểm tra revision bằng compare-and-swap trong chính completion transaction; stale không ghi ledger, usage, count hoặc cleanup và job tiếp tục chờ đối chiếu.
- Nếu đối chiếu xác nhận trùng thực, G kết thúc job `FAILED_FINAL` với `VARIANT_CONFLICT`, release hai loại reservation; lô tiếp tục bằng job biến thể mới. Không đổi script/plan âm thầm trong retry kỹ thuật. Bằng chứng unavailable chờ theo policy; lỗi cuối cùng kết thúc job, không bỏ qua kiểm tra.

Khóa revision workspace là lựa chọn bảo thủ cho baseline một người dùng; chỉ tối ưu thành nhiều scope khóa nếu vẫn chứng minh cùng bất biến với article/event chồng lấn. Không cần thay topology.

### CT-ORC-003 — `StageRun`

| Trường | Ý nghĩa |
|---|---|
| `stage_run_id` | ID lần chạy stage |
| `stage_type` | collect, analyze, script, media_select, TTS, align, process, render, QC, sync, complete... |
| `job_id` | Job sở hữu |
| `input_refs` | Input bất biến |
| `state` | Theo state machine tài liệu 12 |
| `attempt` | Retry kỹ thuật |
| `execution_generation` | Fencing generation |
| `dependency_refs` | Stage cần hoàn thành trước |
| `output_refs` | Output đã commit |
| `wait_reason` | Capability/dependency/quota/disk |
| `problem` | Lỗi chuẩn |
| `timing` | Created/started/heartbeat/finished |

G chỉ đánh stage succeeded khi owner output xác nhận commit và result grant hợp lệ.

## 5. Debug từng module

### CT-ORC-004 — `RunDebugStage`

Input:

- stage type;
- explicit input refs;
- config revision;
- app session/user actor;
- `auto_advance=false` bắt buộc;
- optional existing job ref.

Output: stage run và operation ref.

Debug output dùng cùng schema/validation với auto pipeline. Debug không tạo production completion trừ khi user bắt đầu một production command riêng đáp ứng toàn bộ chuỗi invariant.

## 6. Retry và tạo biến thể

### CT-ORC-005 — `RetryStage`

- Giữ `video_job_id`, snapshot, intent và input fingerprint.
- Tăng attempt; có thể tăng execution generation.
- Không tăng completed count.
- Nếu input logic cần đổi, operation này bị từ chối và phải dùng regenerate/variant command thích hợp.

### CT-ORC-006 — `CreateNewVariant`

- Tạo `video_job_id` mới.
- Ghi parent article/event và prior variant refs.
- D bắt buộc validate quy tắc khác biệt.
- Chỉ sau completion mới ghi usage và tính vào target.

## 7. Waiting và phục hồi

### CT-ORC-007 — `SetJobWaiting`

Wait reason có cấu trúc:

- `desktop_offline`;
- `local_ai_unavailable`;
- `provider_unavailable`;
- `quota_wait`;
- `artifact_not_ready`;
- `insufficient_disk`;
- `dependency_wait`;
- `credential_unavailable`.

Công việc không cần AI/desktop vẫn tiếp tục. G không tự thêm provider trả phí. Khi capability hồi phục, scheduler đánh giá lại đúng stage, không restart toàn pipeline.

Theo R18, G không bắt đầu stage tạo script, production plan hoặc voice khi desktop production capability chưa hoạt động. Việc thu thập, chuẩn hóa, chống trùng, lưu media và tạo chỉ mục trên cloud không bị chặn bởi điều kiện này.

## 8. Commit video hoàn thành

### CT-ORC-008 — `CommitVideoCompletion`

Input:

- job/snapshot/script/plan/render attempt refs;
- QualityReport đạt hard gates;
- output artifact version/hash;
- cloud location verification ref;
- output metadata revision;
- variant validation ref;
- variant reservation ID và expected variant registry revision, validation gắn exact output hash;
- usage manifests;
- execution grant/generation/recovery epoch.

Completion transaction phải nguyên tử về mặt nghiệp vụ:

1. kiểm tra job chưa hoàn thành;
2. kiểm tra mọi revision/hash/grant/recovery epoch còn đúng; khóa registry revision theo CT-ORC-012, kiểm tra validation cuối cùng còn hiệu lực, reservation ACTIVE thuộc đúng job và output hash;
3. tạo `CompletionLedger` duy nhất;
4. đánh job completed;
5. chuyển `BatchCapacityReservation` của job thành completion, `VariantReservation` thành `CONVERTED`, tăng registry revision và batch completed count đúng một lần;
6. gọi application port của C để ghi `MediaUsage` trong cùng unit of work; G không ghi trực tiếp bảng C, còn content/variant refs được giữ trong ledger;
7. phát outbox event `VideoCompleted`;
8. tạo cleanup eligibility, chưa phải lệnh xóa trực tiếp.

Nếu retry cùng input sau commit, trả ledger cũ. Nếu input khác, trả conflict.

Vì baseline là modular monolith dùng chung PostgreSQL, G và C tham gia cùng unit of work và cùng commit/rollback. `VideoCompleted` chỉ phát sau khi ledger và `MediaUsage` đã commit; event không phải cơ chế bù cho usage còn thiếu. Nếu sau này tách service/database, phải mở ADR-0004 và thay bằng protocol duy trì cùng bất biến trước khi tách.

### CT-ORC-009 — `CompletionLedger`

Ledger tối thiểu chứa:

- completion ID và job/batch/session refs;
- video output artifact/hash/cloud location;
- snapshot/script/plan/preset refs;
- QualityReport và variant validation refs;
- content/variant refs và media usage manifest dùng để tái lập lịch sử lựa chọn;
- completed time;
- output naming metadata;
- cost/usage summary;
- audit actor/system;
- cleanup policy ref.

Ledger là bằng chứng đếm target và điều kiện cấp quyền dọn local.

## 9. Kết thúc batch

### CT-ORC-010 — Lý do dừng

| Trạng thái | Điều kiện |
|---|---|
| `COMPLETED_TARGET` | Completed ledger count đạt target |
| `COMPLETED_EXHAUSTED` | Không còn candidate đủ điều kiện theo policy hiện tại |
| `WAITING_CAPABILITY` | Vẫn có việc nhưng capability cần thiết chưa có |
| `FAILED_SYSTEM` | Lỗi điều phối/hạ tầng không thể tiếp tục an toàn |

Video/job riêng lẻ lỗi không làm batch thành `FAILED_SYSTEM` nếu vẫn còn candidate khác.

## 10. Phiên app và thư mục

### CT-ORC-011 — `AppSession`

Mỗi lần bật/tắt tool có session ID, start/end time, desktop identity, log scope và output folder intent.

- Không tạo output folder “hợp lệ” nếu session chưa có video hoàn thành.
- Session restart không reset batch/job checkpoint.
- Tên folder có thể trùng ngày và được thêm `(1)`, `(2)` theo storage allocator.
- Log lỗi/hoàn thành trên UI luôn liên kết session, job, stage và correlation ID.

## 11. Acceptance contract

1. Batch đạt target bằng ledger count, không bằng số file nhìn thấy.
2. Restart app tiếp tục từ checkpoint và không chạy lại tin đầu tiên.
3. Job lỗi bị đánh dấu/log nhưng batch tiếp tục với job khác.
4. Retry và tạo biến thể là hai command, hai ngữ nghĩa khác nhau.
5. Job chờ desktop/provider không bị báo failed chỉ vì capability tạm mất.
6. Completion chỉ commit một lần dù command/result được giao lặp.
7. Hai allocator đồng thời ở suất cuối chỉ một bên tạo được capacity reservation; batch không vượt target.
8. Hai job khác nhau cùng chọn biến thể trùng không thể cùng giữ chỗ/hoàn thành qua validation cũ; stale trả về để đối chiếu, không sinh side effect completion.
