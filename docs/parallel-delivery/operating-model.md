# Mô hình điều hành triển khai song song

> **Trạng thái:** `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`

## 1. Ba lớp điều khiển

| Lớp | Trách nhiệm | Không được làm |
|---|---|---|
| Project authority | User checkpoint, checklist, roadmap và milestone plan quyết định việc gì được phép | Không tự mở milestone vì DAG đã có node |
| Parallel scheduler | Orca quản lý dependency, ownership, lease, worker lifecycle và merge queue | Không phát minh requirement, contract hoặc Git truth thứ hai |
| Delivery protocol | Dely điều khiển tuần tự implement → independent review trong một task đã được cấp quyền | Không điều phối project DAG, không merge, không thay Orca |

Git là nguồn sự thật cho candidate; `docs/12-pre-code-checklist.md` là nguồn sự thật authority hiện hành; Orca là execution plane bắt buộc. Dely là protocol mỏng nằm trong task, không phải orchestrator thứ hai.

## 2. Vai trò và model routing

| Vai trò | Harness/model/effort | Quyền |
|---|---|---|
| Control | phiên hiện hành / `cx/gpt-5.6-sol` | Giữ authority, scope, dependency, ngoại lệ, merge/release decision; không đóng vai implementer/reviewer của candidate |
| Dely implement | Codex CLI / `ag/gemini-3.8-flash-high` / `high` | Thực hiện đúng một task có owned paths và acceptance instruments |
| Dely review | Claude Code / `cx/gpt-5.6-sol` / `high` | Phiên độc lập, tái chạy gate, không sửa candidate |
| Supreme independent audit | `cx/gpt-6-astra-medium` / `medium` | Gate bên ngoài Dely, chỉ dùng cho audit cực khó được Control/user định tuyến rõ |

Bảng Dely được quản lý trong `AGENTS.md` và chỉ có hai dòng `implement`/`review`. Supreme audit không được thêm thành phase Dely. Model routing không trao thêm authority và không thay security boundary.

### Cổng tương thích Harness (Harness Compatibility Gate)

- **Quan sát thực tế**: Codex CLI khi định tuyến sang `ag/gemini-3.8-flash-high` đã từng được ghi nhận hiện tượng làm sụp các công cụ có namespace (`functions.exec` -> `functions`), dẫn đến việc không thể thực thi tool call dù bước routing báo thành công.
- **Nguyên tắc fail-closed**: Thành công định tuyến (route success) không đồng nghĩa với khả năng thực thi thực tế (executable). Theo chính sách định tuyến fail-closed tại `AGENTS.md`, Antigravity native bị nghiêm cấm tuyệt đối. Khi thiếu hoặc có mâu thuẫn bằng chứng định tuyến/thực thi, hệ thống bắt buộc thực hiện hard STOP và nghiêm cấm fallback sang harness, provider, model hay direct vendor login khác.
- **Yêu cầu cổng**: Trước khi worker tiến hành thực thi tác vụ, bắt buộc phải vượt qua bài kiểm tra khói thực thi công cụ (tool-execution smoke test).
- **Cơ chế an toàn (Fail-Closed STOP / Blocked State)**: Nếu tool-execution smoke test thất bại (phát hiện sụp namespace hoặc lỗi thực thi công cụ), hệ thống kích hoạt điều kiện `STOP` / `blocked_harness`, lập tức giải phóng và fence toàn bộ tài nguyên/lease, chuyển trạng thái sang `STOP_BLOCKED`/`blocked` mà không tạo bất kỳ mutation nào trên candidate tree. Cần sự can thiệp phục hồi từ Control hoặc con người; tuyệt đối không tự ý fallback hoặc chuyển đổi harness/provider.
- **Không tuyệt đối hóa vĩnh viễn (No Overgeneralizing Permanence)**: Coi đây là một dynamic runtime check cho phiên làm việc hiện hành; không kết luận hoặc giả định Codex CLI bị lỗi vĩnh viễn trong tương lai khi có bản cập nhật tooling/harness mới.

## 3. Đơn vị lập kế hoạch

Một task chỉ được tách khi nó có thể có trọn một vòng test/evidence và reviewer có thể accept nó trong khi reject task lân cận. Task phải khai báo tối thiểu:

- `id`, `milestone`, `status`, `authority` và `authority_refs`;
- dependency bắt buộc và revision contract đã frozen;
- `requirement_refs`, `contract_refs`, `invariant_refs`;
- module/aggregate/path sở hữu và path cấm;
- resource lock cùng lease/fencing policy;
- runtime prerequisites;
- acceptance instrument, counterexample và nơi quan sát RED;
- evidence output có single writer;
- rollback/migration reference;
- route implement/review/audit;
- merge priority.

Thiếu trường bắt buộc làm task `invalid`, không tự điền từ tên task.

## 4. Đồ thị và concurrency wave

DAG chỉ biểu diễn dependency kỹ thuật. Authority là gate độc lập trên từng node. Một wave là tập node đồng thời thỏa cả sáu trục độc lập:

1. predecessor đã accepted;
2. contract revision không bị hai writer sửa;
3. owned path không giao nhau;
4. resource/migration/schema lock không xung đột;
5. evidence output không giao nhau;
6. runtime capacity đáp ứng admission policy.

Scheduler phải tính wave từ registry hiện hành; số wave trong `task-dag.yaml` là kế hoạch dự kiến, không là quyền dispatch. Nếu conflict xuất hiện sau dispatch, task có priority thấp hơn chuyển `blocked` và trả lease; không để cả hai tiếp tục rồi chọn diff sau.

### Ví dụ thiết kế, chưa active

```text
W0: authority/contract freeze
W1: module-local domain + deterministic tests ở các owner độc lập
W2: adapter/UI fixture theo contract đã frozen
W3: cross-module integration
W4: serialized migration/merge/evidence synthesis
```

Không được dùng ví dụ này để mở M2-P8/P9 hoặc M3+.

## 5. Single-writer và contract freeze

- Mỗi path có tối đa một active write lease.
- Mỗi aggregate có một owner logic theo `docs/09-contracts/README.md`.
- Mỗi migration sequence, lockfile, state machine và contract revision dùng exclusive lock.
- **Khai báo lock khác Active Lease**: Việc khai báo `resource_locks` trong định nghĩa task chỉ là danh mục yêu cầu tĩnh. Chỉ có active lease đang sống (chưa hết hạn) mới chiếm giữ tài nguyên. Task ở trạng thái `integrated` hoặc đã đóng không giữ active lease nào và không chặn các task tiếp theo.
- **Tài nguyên phân vùng (Partitionable) và Capacity**:
  - `LOCK-POSTGRES-TEST-DB` (`exclusive_by_database_name`): Các task dùng namespace database tách rời (`db:ns1` và `db:ns2`) được cấp lease đồng thời không xung đột. Kiểm tra va chạm phân vùng là đối xứng hai chiều (`namespaces_overlap`): namespace cha (ví dụ `db:analytics`) chặn namespace con (ví dụ `db:analytics:us_east`) và ngược lại.
  - `LOCK-DESKTOP-GPU` (`capacity`): Cấp phát theo đơn vị định mức (unit); vượt quá tổng dung lượng (over-capacity) sẽ bị từ chối fail-closed. Khi yêu cầu đa đơn vị (`units > 1`), hệ thống bảo lưu và cấp phát monotonic fencing token độc lập cho từng slot trong mảng `allocated_slots`. Mỗi slot duy trì thế hệ tăng đơn điệu độc lập; một lease chỉ hợp lệ khi toàn bộ các slot được cấp phát giữ đúng token hiện hành, ngăn chặn triệt để tái sử dụng bất đối xứng (asymmetric reuse).
- **Chính sách gia hạn tích lũy, đăng ký lock bắt buộc và cấm tái chiếm giữ lease**:
  - Tác vụ bắt buộc phải đăng ký danh sách `declared_task_locks` trước khi dispatch; khi dispatch bắt buộc chứng minh chính xác và đầy đủ toàn bộ tập hợp lock này thông qua active leases.
  - Gia hạn lease không được vượt quá thời gian gia hạn tích lũy tối đa (`max_cumulative_seconds`) hoặc số lần gia hạn tối đa (`max_renewals`) đã quy định trong cấu hình lock.
  - Task đã hoàn tất tích hợp (`integrated`) bị cấm vĩnh viễn không được tái chiếm giữ lease. Mọi thao tác quản lý lease từ chối chuỗi định danh rỗng/whitespace fail-closed.
  - Tính duy nhất của Orca task ID và dispatch ID được bảo toàn bền vững xuyên suốt tiến trình thông qua `SharedOrcaExecutionRegistry` với cơ chế khóa atomic và ghi đĩa bền vững.
- **Exact Contract Binding**: Mỗi contract ID ràng buộc chặt chẽ với registry có source file định nghĩa nó. `CT-AI-ROUTE-*` thuộc về `CONTRACT-CONFIG-SECURITY` (owner `J`), tuyệt đối không bị chiếm bởi `CONTRACT-CREATIVE-AI` (owner `D`).
- Contract owner phát hành revision frozen trước consumer task.
- Consumer chỉ implement trên exact revision; unsupported version phải fail closed.
- Thay đổi contract sau freeze làm dependent task `needs_replan`, không âm thầm cập nhật fixture.
- Cross-owner atomic use case do caller-owned PostgreSQL Unit of Work điều phối qua typed owner ports; coordinator không ghi bảng owner khác.

## 6. Eligibility và admission

Control đánh giá predicate sau từ machine records, không từ lời nói terminal:

```text
eligible(task) =
  task.authority.state == granted
  and task.authority.state not in (locked, future_template, revoked)
  and all(required predecessors are accepted or integrated)
  and all(required contracts are frozen at exact revision and bound to defining source)
  and no active path/aggregate/evidence conflict
  and all requested locks are declared in ownership registry and can be acquired atomically
  and candidate commit matches exact current git HEAD
  and runtime prerequisites are observed available
  and every deterministic acceptance row has a reviewed oracle
  and task.acceptance has no empty, missing or 'unknown' red_observation
  and all referenced IDs (requirements, invariants, contracts, owners) are real
```

Task có `authority.state` là `locked` hoặc `future_template` tuyệt đối không thể ở trạng thái `ready` (chuyển sang `ready` sẽ bị validator từ chối). Với task behavior, RED phải fail vì counterexample/behavior seam đã nêu, không vì import, setup hoặc binary thiếu. Với docs/config, parser, link checker, fixture hoặc diff inspection có thể là instrument phù hợp nhưng phải phân biệt implementation hiện diện mà sai. Mọi red observation mang giá trị `unknown` đều không đủ điều kiện `ready`.

## 7. Safe automation qua nhiều milestone

Automation được phép tạo proposal cho milestone tương lai nhưng không dispatch. Chuyển `future_template` thành task thực thi cần:

1. milestone trước đạt exit gate;
2. audit và user checkpoint được ghi ở authority source;
3. plan milestone xác định scope/dependency/file ownership;
4. contract và open item chặn đã frozen hoặc có STOP gate;
5. task registry được review;
6. authority được đổi bằng commit riêng có provenance.

Scheduler không tự suy authority từ `accepted` predecessor, calendar, branch name, label, terminal output hoặc existence của test.

## 8. STOP và re-plan

Dừng task và mọi descendant chưa dispatch khi:

- authority thiếu hoặc bị rút;
- contract/requirement mâu thuẫn;
- cần sửa ngoài owned scope;
- lock/lease mất hiệu lực hoặc fencing token cũ;
- phát hiện lock không khai báo trong lock registry hoặc task DAG;
- nỗ lực tái sử dụng Orca task ID hoặc dispatch ID đã tồn tại/settled;
- nới rộng thời hạn lease vượt quá giới hạn đã khai báo hoặc vượt giới hạn gia hạn tích lũy;
- candidate commit không khớp với commit HEAD thực tế;
- nỗ lực bỏ qua fixture trong chế độ release/audit (--skip-fixtures hoặc VALIDATE_SKIP_FIXTURES);
- phát hiện secret/token/private key trong tệp tin thay đổi tại cổng release;
- runtime bắt buộc không khả dụng;
- external outcome không xác định;
- RED không phân biệt đúng lỗi;
- security/data-loss invariant có nguy cơ bị phá;
- candidate identity thay đổi sau review;
- tool-execution smoke test thất bại hoặc phát hiện harness làm sụp namespace công cụ (`functions.exec` -> `functions`);
- phát hiện bất kỳ sự tăng thế hệ bất đối xứng nào trên capacity lock đa slot;
- nỗ lực can thiệp, tái mở trạng thái terminal hoặc tua ngược review/merge_queued về planned qua `set_task_state`;
- báo cáo attestation chứa zero commit, commit không tồn tại hoặc topology không nhất quán với Git DAG (từ chối quan hệ thuộc tập hợp `{HEAD, HEAD^}` lỏng lẻo);
- xung đột tranh chấp tạo dispatch bỏ sót rollback hoặc để lại durable orphan dispatch binding trên đĩa.

Task trả `blocked` nếu phụ thuộc có thể được giải quyết không đổi contract; trả `needs_replan` nếu scope/architecture/acceptance cần đổi; trả `stopped` khi authority hoặc safety yêu cầu kết thúc. Không giao phần còn lại cho worker khác dưới cùng lease.

## 9. Metrics của thí nghiệm

Pilot chỉ đánh giá cơ chế delivery, không claim quality gate sản phẩm. Tối thiểu đo:

- số conflict ngăn trước mutation;
- thời gian chờ dependency/lock/external riêng biệt;
- lease expiry và stale result bị từ chối;
- tỷ lệ task phải re-plan;
- queue time, gate time và số rebase/review invalidation;
- trace coverage từ task đến requirement/contract/evidence;
- duplicate `worker_done` bị từ chối;
- số lần coordinator cần can thiệp.

Không tối ưu throughput agent bằng cách giảm review, evidence hoặc security gate.
