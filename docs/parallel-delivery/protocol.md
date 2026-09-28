# Protocol task và worker

> **Trạng thái:** `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`

## 1. Nguồn trạng thái

Orca là execution plane và communication plane bắt buộc. Trạng thái task đến từ record Orca + Git candidate + evidence machine-readable, không suy từ dòng cuối terminal. Dely chạy bên trong task được cấp quyền và không tạo worker con ngoài dispatch do Control quản lý.

### Tách biệt Delivery Ledger và Orca Execution Plane

- **Delivery Ledger Task ID** (ví dụ: `PD-PILOT-CONTROL`, `M3-A-TEMPLATE`): Định danh work package trong DAG và delivery ledger (`task-dag.yaml`). Thuộc quyền quản lý của Control.
- **Orca Execution Plane**:
  - `run_id`: Định danh run thực thi tổng thể trong Orca.
  - `task_id`: Định danh execution container / process trong Orca (ví dụ `task_576e006b5784`).
  - `dispatch_id`: Định danh phiên / attempt thực thi cụ thể của worker (ví dụ `ctx_ea3797c96ced`).
  - `worker_terminal_id`: Handle terminal của worker (ví dụ `term_299d71b8-d78c-41f9-ad72-2b25401fb60d`).
  - `dispatch_capability`: Token thẩm quyền dispatch do Orca cấp.
- **OrcaDeliveryAdapter** (do Control sở hữu): Thành phần chuyển ngữ giữa các sự kiện Orca CLI (`heartbeat`, `ask`, `escalation`, `worker_done`) và máy trạng thái delivery ledger. `worker_done` chỉ giải quyết attempt của dispatch, không trực tiếp đánh dấu `integrated`.

Mọi message qua protocol phải mang:

```yaml
protocol_version: "1.0.0"
run_id: string
delivery_task_id: string
orca_task_id: string
dispatch_id: string
worker_terminal_id: string
sequence: integer
sent_at: RFC3339
lease_id: string|null
fencing_tokens: {resource_id: integer}
type: heartbeat|status|ask|escalation|worker_done
body: object
```

Message thiếu ID, sequence lùi, dispatch không khớp hoặc fencing token cũ bị từ chối fail closed.

## 2. Máy trạng thái task

```mermaid
stateDiagram-v2
    [*] --> planned
    planned --> waiting_dependency
    waiting_dependency --> ready: authority + deps + contracts + locks + runtime + oracle
    ready --> dispatched
    dispatched --> acknowledged
    acknowledged --> running
    running --> blocked
    running --> needs_replan
    running --> review
    blocked --> ready: blocker resolved and fresh eligibility
    blocked --> stopped
    needs_replan --> planned: revised contract approved
    needs_replan --> stopped
    review --> remediation
    remediation --> review
    review --> merge_queued: accepted
    merge_queued --> integrated: gates pass on exact candidate
    merge_queued --> ready: candidate invalidated
    planned --> cancelled
    waiting_dependency --> cancelled
    ready --> cancelled
    dispatched --> stopped
    acknowledged --> stopped
    running --> stopped
```

### Ý nghĩa bắt buộc

| Trạng thái | Điều kiện |
|---|---|
| `planned` | Có proposal nhưng chưa đủ eligibility |
| `waiting_dependency` | Chờ predecessor/authority/contract/runtime có tên |
| `ready` | Predicate eligibility đã được scheduler chứng minh |
| `dispatched` | Orca đã ghi dispatch và lease, chưa có ACK |
| `acknowledged` | Worker xác nhận exact task/scope/baseline/lease |
| `running` | Worker đang làm trong owned scope |
| `blocked` | Phụ thuộc tạm thời, không cần đổi contract/scope |
| `needs_replan` | Cần đổi scope, architecture, acceptance hoặc ownership |
| `review` | Candidate task đã commit; không có worker sửa cùng tree |
| `remediation` | Original implementer sửa finding trong contract, một pass/finding |
| `merge_queued` | Review accepted; chờ tích hợp tuần tự |
| `integrated` | Merge và gate đạt trên exact integrated HEAD |
| `stopped` | Authority/safety/failure dừng có chủ ý |
| `cancelled` | Chưa tạo candidate hoặc candidate được bảo toàn riêng, không tiếp tục |

Không có cạnh `waiting_dependency → dispatched`, `blocked → running` hoặc `review → integrated` trực tiếp.

## 3. Dispatch và ACK

Trước dispatch, Control ghi execution envelope:

- authority ref và exact baseline commit;
- branch/worktree và protected dirty paths;
- owned/forbidden paths;
- requirement/contract/invariant refs;
- exact locks, lease expiry và fencing token;
- acceptance rows cùng counterexample;
- runtime prerequisites;
- evidence paths;
- implement/review model route;
- commit/push/publication authority riêng biệt.

Worker ACK đúng một lần, nêu exact `task_id`, `dispatch_id`, baseline và owned path digest. ACK không khớp làm dispatch `NO_ACK`; không cho worker sửa file.

### Kiểm tra khói tương thích Harness (Tool-Execution Smoke Test)

Trước khi tiến hành sửa đổi hoặc mutation dưới lease được cấp, worker hoặc harness thực thi bắt buộc phải vượt qua bài kiểm tra khói thực thi công cụ:
- Xác nhận harness gọi đúng tên công cụ đầy đủ, không làm sụp tên công cụ có namespace (`functions.exec` -> `functions`). Hiện tượng này đã được quan sát thực tế trên Codex CLI kết hợp `ag/gemini-3.8-flash-high` trong khi Antigravity native với effective model `ag/gemini-3.8-flash-high` thực thi thành công.
- Nếu smoke test thất bại: kích hoạt điều kiện `STOP` / `blocked_harness`, giải phóng lease, và fallback an toàn sang harness tương thích đã kiểm chứng (Antigravity native); không giả định route thành công là harness có thể thực thi.
- Không xem lỗi này là vĩnh viễn đối với Codex CLI; đây là một cổng kiểm tra động tại runtime (dynamic compatibility gate).

## 4. Heartbeat, check và status

### Heartbeat

Worker gửi heartbeat khi có active lease và còn chạy. Heartbeat gồm:

- phase hiện tại;
- last progress sequence;
- path đang sở hữu;
- acceptance instrument gần nhất;
- blocker nếu có;
- requested renewal duration.

Heartbeat không phải completion, không tự gia hạn lease và không thay status report. Scheduler chỉ renew sau khi kiểm authority/visibility.

### Check

Control dùng Orca inbox `check` để nhận message. Không đọc terminal rồi đoán worker hoàn tất. Check có cursor/sequence; message đã xử lý được acknowledge để không áp dụng hai lần.

### Status

Worker gửi `status` khi đổi phase quan trọng, phát hiện STOP condition hoặc đạt checkpoint lâu. `status` phải phân biệt:

- tiến độ bình thường;
- `blocked_external`;
- `blocked_dependency`;
- `needs_replan`;
- `candidate_ready_for_review`.

`blocked` không đồng nghĩa process worker lỗi. Authentication/quota/harness crash không được giả thành blocked business state.

## 5. Ask và escalation

Khi worker cần coordinator trả lời câu hỏi quyết định tiếp tục hay dừng, worker bắt buộc dùng lệnh `ask` qua Orca CLI:

```sh
orca orchestration ask --from <worker_terminal> --dispatch-capability <dcap> --question "<nội dung>" --options "<opt1,opt2>" --timeout-ms <ms>
```

Lệnh `ask` chặn worker đồng bộ cho tới khi coordinator phản hồi. Nếu timeout hoặc mất kết nối, worker không lặp lại câu hỏi trùng lặp mà resume theo message ID đã nhận.

Khi worker gặp blocker cần coordinator xử lý trước khi tiếp tục, worker gửi `escalation`:

```sh
orca orchestration send --from <worker_terminal> --dispatch-capability <dcap> --type escalation --subject "Blocked: <lý do>" --body "<chi tiết>" --task-id <orca_task_id> --dispatch-id <orca_dispatch_id>
```

Sau `ask` hoặc escalation, nếu lease hết hạn mà không có giải pháp, task chuyển `blocked`, mọi output muộn bị fence.

Escalation tự động khi:

1. heartbeat quá hạn;
2. cùng blocker lặp hai lần;
3. lock wait vượt bound;
4. worker mất visibility;
5. remediation re-review vẫn không accept;
6. security/data-loss condition xuất hiện.

Control không tự trả lời câu hỏi thuộc user authority.

## 6. Wait và worker loss

- Chờ dependency: không giữ write lock/path lease; có thể giữ queue position.
- Chờ external provider trong một operation đã gửi: giữ operation identity, chuyển outcome unknown và reconcile trước retry.
- Chờ review: implementer không sửa candidate; lease mutation được đóng.
- Chờ merge: candidate pin bằng commit SHA; thay đổi làm review invalid.
- Terminal không phản hồi: kiểm Orca worker record, process và last message; không suy completion từ output.
- Worker replacement luôn nhận dispatch/lease/fencing token mới; không tiếp tục bằng token cũ.

## 7. Exactly-once `worker_done` và Orca CLI Mapping

Lệnh Orca CLI `worker_done` chỉ hỗ trợ đúng hai giá trị outcome:
`--outcome succeeded` hoặc `--outcome failed`.

```sh
orca orchestration send --from <worker_terminal> --dispatch-capability <dcap> --type worker_done --subject "<short status>" --body "<3-sentence summary>" --task-id <orca_task_id> --dispatch-id <orca_dispatch_id> --outcome succeeded|failed
```

### Ý nghĩa và cơ chế chuyển đổi của `OrcaDeliveryAdapter`

1. **`worker_done` chỉ settle execution attempt (dispatch)**: Nó ghi nhận phiên làm việc của worker kết thúc. Nó KHÔNG tự động chuyển trạng thái delivery task sang `integrated`.
2. **Chuyển đổi thành công (`--outcome succeeded`)**:
   - `OrcaDeliveryAdapter` kiểm tra execution envelope, candidate commit SHA, committed diff + dirty overlay scope, và evidence.
   - Nếu hợp lệ, `OrcaDeliveryAdapter` lập tức giải phóng toàn bộ active mutation lease của dispatch đó (đảm bảo nguyên tắc Section 6: khi chờ review, implementer không giữ mutation lease), sau đó chuyển delivery task sang `review` (chưa phải `integrated`).
   - Sau khi reviewer độc lập xác nhận `ACCEPT`, task chuyển sang `merge_queued`.
   - Sau khi các integration gate tuần tự PASS trên exact candidate HEAD, task mới trở thành `integrated`.
3. **Chuyển đổi thất bại hoặc blocker (`--outcome failed`)**:
   - Khi worker gặp lỗi không thể phục hồi hoặc blocker cần re-plan, worker gửi `worker_done --outcome failed` (hoặc escalation).
   - `OrcaDeliveryAdapter` chuyển trạng thái delivery task sang `blocked` hoặc `needs_replan`.
   - Toàn bộ live lease của dispatch đó bị hủy / giải phóng.
4. **Tiếp tục sau blocker / re-plan cần Fresh Dispatch**:
   - Khi nguyên nhân chặn được giải quyết, delivery task được chuyển về `ready` (nếu đủ eligibility).
   - Khi dispatch lại, hệ thống cấp một **fresh dispatch** với `dispatch_id` hoàn toàn mới, active lease mới và monotonic fencing token mới. Tuyệt đối không tái sử dụng dispatch ID hoặc fencing token cũ!
5. **Từ chối kết quả trùng lặp hoặc quá hạn (Duplicate / Stale Result Rejection)**:
   - Một dispatch đã settled chỉ nhận đúng một lần `worker_done`.
   - Kết quả gửi lại từ dispatch cũ, hoặc mang fencing token cũ hơn token hiện hành, bị từ chối fail-closed.
   - Dedupe key là `(run_id, delivery_task_id, dispatch_id, type=worker_done)`.
6. **Không tái sử dụng Orca task ID và dispatch ID trên toàn hệ thống (Global Non-Reuse)**:
   - Orca task ID và dispatch ID là duy nhất trên toàn bộ vòng đời hệ thống, bao gồm cả các attempt đã hoàn tất (`settled`).
   - Nghiêm cấm ghi đè dispatch binding (`Duplicate dispatch binding overwrite`) hoặc tái sử dụng ID giữa các lần dispatch.
7. **Ràng buộc Candidate Commit với actual HEAD Git**:
   - Khởi tạo dispatch bắt buộc đối chiếu `candidate_commit` và `approved_candidate_commit` với commit `HEAD` thực tế trong Git DAG (`git rev-parse HEAD`). Sai lệch commit bị từ chối fail-closed.
8. **Ràng buộc Intended Dispatch vô điều kiện**:
   - Khi dispatch chỉ định `intended_dispatch_id`, lease liên kết bắt buộc phải khớp chính xác với `intended_dispatch_id` đó. Mọi nỗ lực bypass (như `ctx_init`) bị cấm triệt để.
9. **Fencing theo từng Live Allocation Slot cho Capacity Lock**:
   - Lock dạng `capacity` phân bổ vị trí theo từng slot riêng biệt (`LOCK_ID:slot_N`).
   - Mỗi slot có bộ đếm monotonic fencing token độc lập. Các holder song song giữ token hợp lệ đồng thời mà không xung đột; khi slot được thu hồi và tái cấp phát, bộ đếm slot tăng lên ngăn chặn worker cũ gửi kết quả quá hạn.
10. **Chống nới rộng thời hạn và từ chối lock không khai báo**:
    - Không được vượt quá thời hạn `lease_seconds` đã công bố trong cấu hình lock tại thời điểm chiếm giữ hoặc gia hạn.
    - Mọi lock chưa khai báo trong registry đều bị từ chối tại `acquire_lease`, `create_dispatch` và toàn bộ DAG.
11. **Máy trạng thái thực thi Harness quan sát được**:
    - Harness tuân thủ chu trình: `IDLE -> RUNNING -> SUCCESS | FAILURE | STOP_FALLBACK`.
    - Đối số trong `HarnessExecutionResult` được thẩm định kiểu dữ liệu nghiêm ngặt (`success: bool`, `execution_time_ms >= 0`, `status: PASS|STOP`).
    - Từ chối các trường mâu thuẫn (`success=True` với `status="STOP"` hoặc `fallback_required=True`; `success=False` với `status="PASS"` hoặc `fallback_required=False`).
12. **Durable Ledger/Registry dùng chung (`SharedOrcaExecutionRegistry`)**:
    - Task ID và dispatch ID của Orca được lưu vết qua registry dùng chung giữa các adapter instance, bảo đảm tính duy nhất toàn cục và chống tái sử dụng ID trên toàn hệ thống.
13. **Intended Dispatch bắt buộc không rewrite lease (`No Lease Rewrite`)**:
    - Tham số `intended_dispatch_id` là bắt buộc khi tạo dispatch; bắt buộc phải khớp chính xác với `active_lease.dispatch_id`. Cấm tuyệt đối hành vi ghi đè lease dispatch ID.
14. **Chứng minh đầy đủ tập hợp Lock đã khai báo (`declared_task_locks`)**:
    - Khi tạo dispatch, worker bắt buộc phải chứng minh đầy đủ lease hợp lệ cho mọi lock trong `declared_task_locks` của task (qua `lease_ids`), cấm dùng một lease đại diện.
15. **Slot Reservation và Fencing cho Capacity đa đơn vị (`units > 1`)**:
    - Phân bổ, bảo lưu và cấp monotonic fencing token riêng cho từng slot trong mảng `allocated_slots`.
16. **Kiểm tra va chạm phân vùng đối xứng (`Symmetric Namespace Overlap`)**:
    - Va chạm phân vùng được kiểm tra đối xứng hai chiều: namespace cha chặn namespace con và namespace con chặn namespace cha (`namespaces_overlap`).
17. **Giới hạn gia hạn tích lũy (`max_cumulative_seconds` và `max_renewals`)**:
    - Gia hạn lease bị chặn nếu tổng thời gian gia hạn tích lũy vượt quá `max_cumulative_seconds` hoặc số lần gia hạn vượt quá `max_renewals`.
18. **Cấm tái chiếm giữ lease cho task đã tích hợp và từ chối ID rỗng**:
    - Task đã được đánh dấu tích hợp (`mark_task_integrated`) bị cấm vĩnh viễn không được tái chiếm giữ lease. Từ chối fail-closed mọi định danh rỗng/whitespace ở mọi thao tác lock/lease/dispatch.
19. **Bền vững tiến trình qua Shared Execution Registry lưu đĩa nguyên tử**:
    - `SharedOrcaExecutionRegistry` hỗ trợ lưu đĩa bền vững (`storage_path`) với ghi đĩa atomic (`.tmp` + `fsync` + `os.replace`) và khóa tệp cross-process (`_FileLock`).
    - Tính duy nhất của task ID và dispatch ID tồn tại qua quá trình restart tiến trình; đường dẫn mặc định luôn dùng shared registry, cấm tạo registry in-memory mới ngầm trong production path.
20. **Xác thực thế hệ từng slot trong Capacity đa slot và chặn tái sử dụng bất đối xứng**:
    - Mỗi slot sở hữu thế hệ tăng đơn điệu độc lập. Lease đa slot chỉ hợp lệ khi toàn bộ các slot đều giữ đúng token hiện hành.
    - Bất kỳ sự tái cấp phát bất đối xứng của một slot đơn lẻ đều lập tức vô hiệu hóa lease cũ.
21. **Bắt buộc tuyến vòng đời tác vụ đầy đủ (Không bỏ qua ACK hoặc Running)**:
    - Bắt buộc tuân thủ đúng thứ tự: `ready -> dispatched -> acknowledged -> running -> worker_done`.
    - Cấm nhảy trực tiếp từ `dispatched` sang `running` hoặc sang `worker_done`. `handle_worker_done` chỉ chấp nhận tác vụ ở trạng thái `running`.
22. **Bắt buộc đăng ký `declared_task_locks` và chứng minh tập hợp lock khớp chính xác**:
    - Mọi tác vụ bắt buộc phải đăng ký `declared_task_locks` trước khi dispatch; cấm dispatch tác vụ chưa khai báo lock.
    - Tập hợp lock được chứng minh qua active leases bắt buộc phải trùng khớp hoàn toàn với `declared_task_locks` (không thiếu, không thừa).
23. **Cấm gán trực tiếp trạng thái trên Harness Execution State Machine**:
    - Thuộc tính `@current_state.setter` từ chối mọi nỗ lực gán trạng thái trực tiếp bằng cách raise `HarnessCompatibilityError`.
    - Mọi chuyển dịch trạng thái bắt buộc thông qua phương thức hợp lệ `transition()` hoặc `reset()`.

## 8. Review/remediation protocol

Reviewer là phiên mới, không implement và không edit. Reviewer nhận approved contract, baseline, candidate SHA, diff và acceptance rows; tự tái chạy instrument và counterexample. Kết quả duy nhất:

- `ACCEPT`;
- `CHANGES_REQUESTED`;
- `BLOCKED`.

Finding trong contract đi một remediation pass bởi original implementer với lease mới; reviewer ban đầu re-review fix-only diff. Nếu không accept, task `needs_replan`; không lặp repair vô hạn. Architectural delivery thêm integration review độc lập sau khi mọi task review accepted.

## 9. Protocol invariants

- Một dispatch chỉ có một active worker.
- Một task không có hai state terminal.
- Sequence tăng đơn điệu theo dispatch.
- Old lease/recovery epoch/fencing token không mutation.
- Toàn bộ mutation lease phải được đóng ngay khi worker_done thành công, trước khi vào review.
- Không tái sử dụng Orca task ID hoặc dispatch ID trên toàn hệ thống (kể cả settled attempts) thông qua SharedOrcaExecutionRegistry bền vững tiến trình.
- Candidate commit bắt buộc khớp tuyệt đối với approved candidate và HEAD hiện hành của repository Git.
- Intended dispatch ID là bắt buộc và không ghi đè active lease dispatch ID.
- Dispatch bắt buộc chứng minh chính xác và đầy đủ toàn bộ tập hợp lock đã khai báo cho task (`declared_task_locks`).
- Bắt buộc tuân thủ chu trình vòng đời: `ready -> dispatched -> acknowledged -> running -> worker_done` mà không bỏ qua bước ACK hoặc running.
- Mọi capacity lease đa slot bắt buộc bảo lưu và xác thực thế hệ đơn điệu cho từng slot; phát hiện và từ chối tái cấp phát bất đối xứng.
- Không nới rộng thời hạn lease vượt quá định nghĩa đã khai báo và không gia hạn vượt quá max_cumulative_seconds hoặc max_renewals.
- Không cho phép lock không khai báo trong lock registry hoặc task DAG.
- Cấm tái chiếm giữ lease cho các task đã ở trạng thái integrated.
- Cấm các trường mâu thuẫn trong HarnessExecutionResult và cấm gán trực tiếp trạng thái bất hợp pháp trong HarnessExecutionStateMachine (chỉ chuyển qua transition hoặc reset).
- Không heartbeat sau `worker_done`.
- Không review cùng working tree khi worker đang mutation.
- Không merge nếu candidate SHA khác SHA được review.
- Không chuyển task future/locked thành ready chỉ bằng message.
- Route success không thay thế khả năng thực thi thực tế; bắt buộc vượt qua tool-execution smoke test trước mutation.
