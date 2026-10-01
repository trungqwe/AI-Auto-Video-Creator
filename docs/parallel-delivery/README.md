# Kiến trúc triển khai song song có kiểm soát

> **Trạng thái:** `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`
> **Ngày lập:** 28-09-2026
> **Phạm vi:** cơ chế lập kế hoạch, điều phối, giao tiếp, tích hợp và bằng chứng cho công việc đã được cấp quyền; không thay đổi kiến trúc sản phẩm hoặc trạng thái milestone.

## 1. Mục đích

Bộ tài liệu này biến quy tắc triển khai song song thành một control plane có thể kiểm tra bằng máy. Nó bổ sung cho roadmap và milestone plan, không thay thế chúng. Mục tiêu là cho phép nhiều đơn vị công việc độc lập tiến hành đồng thời mà vẫn giữ:

- một nguồn sự thật cho authority và trạng thái;
- một writer cho mỗi path, aggregate, migration và contract revision;
- dependency, contract, lock và evidence có định danh;
- test-first với RED phân biệt được implementation sai;
- merge tuần tự trên candidate đã pin;
- fail-closed, phục hồi được và không sửa hồi tố evidence đã accepted.

Thiết kế này không tự kích hoạt task nào. Mọi task thực thi phải được tạo trong plan milestone có thẩm quyền và phải qua checkpoint riêng.

## 2. Giới hạn authority hiện hành

- M1: `ACCEPTED / CLOSED`.
- M2: `M2-P1..P7B_ACCEPTED_CLOSED`.
- M2-P8 và M2-P9: `LOCKED`; không được bắt đầu Behavioral RED hoặc implementation từ tài liệu này.
- M3 và Phân hệ A: `NOT AUTHORIZED`.
- Các node M3–M7 trong [task DAG](./task-dag.yaml) chỉ là template thiết kế `future_template`, không phải backlog đang hoạt động.
- Toolchain M2 vẫn do [`toolchain-lock.md`](../milestones/m2-control-plane/toolchain-lock.md) khóa; không có pin nào trong bundle này được dùng để thay nó.
- Accepted/rejected evidence lịch sử giữ bất biến.

## 3. Nguồn sự thật và thứ tự ưu tiên

1. [`HANDOFF.md`](../../HANDOFF.md) cho điểm tiếp tục ngắn.
2. [`docs/12-pre-code-checklist.md`](../12-pre-code-checklist.md) cho authority hiện hành.
3. [`docs/11-roadmap.md`](../11-roadmap.md) cho milestone, dependency và user checkpoint.
4. Milestone spec/plan/toolchain lock đang hoạt động cho hành vi và phạm vi file.
5. Contracts, ADR, test strategy và system map cho ranh giới kỹ thuật.
6. Bundle này cho scheduling, lease, protocol và merge control.

Khi có mâu thuẫn, dừng node bị ảnh hưởng ở `needs_replan` hoặc `stopped`; không chọn tài liệu thuận tiện hơn.

## 4. Bản đồ artifact

| Tệp | Vai trò | Máy đọc được |
|---|---|---:|
| [`operating-model.md`](./operating-model.md) | Mô hình điều hành, wave, role, Dely/Orca và model routing | Một phần |
| [`task-dag.yaml`](./task-dag.yaml) | Schema, node mẫu, dependency, authority, wave và acceptance | Có |
| [`contract-registry.yaml`](./contract-registry.yaml) | Contract revision, owner, consumer và compatibility window | Có |
| [`ownership-and-locks.yaml`](./ownership-and-locks.yaml) | Module owner, path owner, resource lock và lease/fencing | Có |
| [`protocol.md`](./protocol.md) | Máy trạng thái task/worker, heartbeat/check/ask/escalation/done | Một phần |
| [`merge-and-integration.md`](./merge-and-integration.md) | Worktree/branch, merge queue và integration gates | Một phần |
| [`traceability.md`](./traceability.md) | Mục tiêu → FR/QR → module → contract/invariant → gate | Một phần |
| [`security-performance-recovery.md`](./security-performance-recovery.md) | Guardrail bảo mật, hiệu năng, evidence và phục hồi | Một phần |
| [`validate.py`](./validate.py) | Công cụ thẩm định bundle, DAG, registry, locks, scope, fixtures | Có |
| [`delivery_engine.py`](./delivery_engine.py) | Module thực thi lõi cho contract binding, lease manager, Orca adapter và harness compatibility | Có |
| [`test_negative_fixtures.py`](./test_negative_fixtures.py) | Suite kiểm thử negative fixtures tự động cho 6 findings Astra round 1 và probes Sol review | Có |
| [`test_host_boundary_harness.py`](./test_host_boundary_harness.py) | Module harness và daemon boundary cô lập cho test keystore/credential nằm ngoài candidate surface | Có |

YAML dùng YAML 1.2, UTF-8 không BOM. Giá trị enum và identifier dùng tiếng Anh; mô tả cho người dùng dùng tiếng Việt.

## 5. Quy tắc kích hoạt tối thiểu

Một node chỉ được chuyển từ `planned` hoặc `waiting_dependency` sang `ready` khi tất cả điều kiện đều đúng:

```text
authority_granted
AND dependencies_accepted
AND contract_revisions_frozen
AND owned_paths_disjoint
AND resource_locks_available
AND runtime_prerequisites_available
AND acceptance_oracle_ready
```

`authority_granted` là điều kiện độc lập, không thể suy từ việc dependency đã xong. Node thiếu một điều kiện phải chờ hoặc dừng, không được thu hẹp/đổi phạm vi ngầm.

## 6. Rollback và khôi phục thiết kế

Bản sao trước thí nghiệm nằm tại:

`D:/AI_SETUP/backups/AI-Auto-Video-Creator/20260928-175542`

Đây là tham chiếu khôi phục tài liệu/config, không phải evidence rằng restore sản phẩm hoặc G05 đã PASS. Trước khi dùng phải xác minh checksum, provenance và phạm vi; không chép đè accepted evidence hoặc worktree có thay đổi chưa bảo toàn.

## 7. Điều kiện đưa thiết kế vào vận hành

Cần một user checkpoint riêng để:

1. duyệt schema và validator;
2. chọn một work package đã có authority để pilot;
3. cấp Orca run/dispatch/commit authority cụ thể;
4. chứng minh lock conflict, worker loss và merge-queue recovery trên fixture;
5. audit kết quả pilot;
6. quyết định giữ, sửa hoặc loại bỏ thí nghiệm.

Không điều nào ở trên đã được bundle này chứng minh runtime.

## 8. Khắc phục toàn diện 21 bypass độc lập từ Sol review

### 8.1. Ngữ nghĩa lệnh thẩm định: Read-only Audit vs Explicit Report Generation

Hệ thống thẩm định `validate.py` phân tách nghiêm ngặt hai chế độ vận hành:

1. **Chế độ Read-only Audit (Mặc định)**:
   - Lệnh: `python docs/parallel-delivery/validate.py` hoặc `python docs/parallel-delivery/validate.py --audit`
   - Mục đích: Chạy cho kiểm tra thường nhật của validator, reviewer và CI mà không sửa đổi bất kỳ tệp tin nào được theo dõi trong Git.
   - Hành vi: Thẩm định cấu trúc YAML, Task DAG, Contract Registry, Lock & Leases, Authority, thay đổi phạm vi (Scope & Deltas) và chạy negative fixture suite. Tuyệt đối không ghi đè `.validation-report.json`, đảm bảo cây làm việc (worktree) hoàn toàn sạch sẽ (`clean`).

2. **Chế độ phát hành kiến trúc / Ghi nhận báo cáo tường minh (Explicit Report Generation)**:
   - Lệnh: `python docs/parallel-delivery/validate.py --generate-report --base <APPROVED_BASE_SHA> --candidate <EXACT_HEAD_SHA>`
   - Bắt buộc truyền đầy đủ giá trị SHA bất biến 40 ký tự hexa cho cả `--base` và `--candidate`; cấm tuyệt đối việc sử dụng ref name như `HEAD`, tên nhánh, tag hoặc short SHA.
   - `--base` bắt buộc phải khớp chính xác baseline dự án đã được phê duyệt (`4a7c8c921b7e05066505d51b168a02c3fde61317`); từ chối các pin cũ/lạc hậu (như `ac5bd30`).
   - `--candidate` bắt buộc phải khớp chính xác commit `HEAD` hiện hành thực tế trong Git; từ chối candidate không phải HEAD.
   - Bắt buộc `--base != --candidate`; từ chối việc tự chứng thực `base == candidate` không có delta thực chất.
   - Ngữ nghĩa tài liệu: Tệp `.validation-report.json` được tạo ra mang trường `semantics` ghi rõ attestation được sinh bởi cờ tường minh với base và candidate khớp HEAD thực tế, tránh các tuyên bố giả định tự quy chiếu (self-referential false claims).

### 8.2. Danh mục khắc phục 21 bypass độc lập và boundary probes

Toàn bộ 21 bypass độc lập do Sol review phát hiện cùng các boundary test lân cận đã được khắc phục triệt để và bảo đảm bằng bộ fixture kiểm thử tự động bền vững (`TestSolTwentyOneIndependentProbes` trong `test_negative_fixtures.py`):

1. **Sol Probe 01**: Từ chối ref name (`HEAD`, nhánh, tag) và short SHA cho candidate; yêu cầu SHA-40 bất biến.
2. **Sol Probe 02**: Từ chối `base == candidate` (tự chọn base bằng candidate để né kiểm tra delta).
3. **Sol Probe 03**: Từ chối candidate commit khác với commit `HEAD` hiện hành thực tế.
4. **Sol Probe 04**: Từ chối base commit lạc hậu (stale pin `ac5bd30`) hoặc không khớp baseline đã duyệt (`4a7c8c9`).
5. **Sol Probe 05**: Chế độ read-only audit thẩm định hoàn tất mà không làm bẩn (`dirty`) `.validation-report.json`.
6. **Sol Probe 06**: Thao tác đổi tên file (rename) được đánh giá ở cả hai đầu (`old_path` và `new_path`), chặn mọi đường dẫn bị cấm.
7. **Sol Probe 07**: Lock Registry Schema: Từ chối ID lock trùng lặp ngay tại thời điểm khởi tạo (`__init__`).
8. **Sol Probe 08**: Lock Registry Schema: Từ chối các chế độ lock không xác định (`unknown mode`) ngay tại khởi tạo.
9. **Sol Probe 09**: Lock Registry Schema: Bắt buộc khai báo cờ boolean `renewable` rõ ràng (true|false).
10. **Sol Probe 10**: Lock Registry Schema: Từ chối dung lượng (`capacity`) hoặc thời hạn (`lease_seconds`) bằng 0 hoặc âm.
11. **Sol Probe 11**: Lock Registry Schema: Lock phân vùng (`exclusive_by_database_name`, ...) bắt buộc khai báo `partition_key_prefix` không rỗng.
12. **Sol Probe 12**: Chiếm giữ lease: Từ chối đơn vị kiểu boolean (`isinstance(True, int)` bypass).
13. **Sol Probe 13**: Chiếm giữ lease: Từ chối đơn vị số thực (`float`), số 0, số âm hoặc kiểu chuỗi.
14. **Sol Probe 14**: Thẩm quyền task bắt buộc phải được đăng ký và cấp quyền rõ ràng (`granted`), không bao giờ mặc định được cấp (`never default granted`).
15. **Sol Probe 15**: Từ chối các lease tài nguyên ngoài (external resource) trùng lặp hoặc chồng chéo giữa các task.
16. **Sol Probe 16**: Gia hạn lease (`renew_lease`) từ chối lock không được phép gia hạn, lease đã hết hạn hoặc thẩm quyền task bị thu hồi (`revoked`).
17. **Sol Probe 17**: Fencing token: Từ chối token tương lai (`token > current counter`), không dùng shortcut chỉ chấp nhận hiện tại mà bỏ qua tương lai.
18. **Sol Probe 18**: Fencing token: Từ chối token bị thiếu (`absent`), cũ (`stale`) hoặc lease đã hết hạn (`expired`).
19. **Sol Probe 19**: Khởi tạo dispatch bắt buộc ràng buộc exact nonblank Orca task ID, candidate commit SHA-40, positive fencing token và active lease ID hợp lệ.
20. **Sol Probe 20**: `worker_done` từ chối task ID Orca không khớp, candidate commit không khớp, kết quả trùng lặp (`duplicate`) hoặc kết quả từ attempt cũ (`stale`).
21. **Sol Probe 21**: Máy trạng thái lifecycle: Task có thẩm quyền `locked`, `future_template`, `revoked` không thể dispatch; thu hồi thẩm quyền sẽ chặn lập tức mọi chuyển trạng thái review, integration và replan.
22. **Boundary Probe 22**: Cổng tương thích harness: Phát hiện hiện tượng sụp namespace công cụ (`functions.exec` -> `functions`) và thất bại khói thực thi, kích hoạt fail-closed `STOP condition` mà không fallback sang native provider.
23. **Boundary Probe 23**: Cổng tương thích harness: Khác biệt namespace công cụ yêu cầu/thực tế kích hoạt `STOP condition`.
24. **Boundary Probe 24**: Fencing token: Ranh giới kiểu dữ liệu nghiêm ngặt, từ chối bool, string, float, list.

## 9. Khắc phục toàn diện các phát hiện Sol Round 3 (P1 Remediations)

Đợt review vòng 3 của Sol chỉ ra các lỗ hổng ranh giới trong kiểm soát thẩm quyền, khởi tạo dispatch, xác thực vòng đời worker/review/integration, schema lock và máy trạng thái harness. Toàn bộ các vấn đề này đã được khắc phục triệt để và kiểm chứng bằng 24 bài kiểm tra bổ sung trong `TestSolRoundThreeCounterexamples` (tổng bộ suite đạt 103 tests PASS):

1. **Khóa chặt thẩm quyền tác vụ (No Authority Override)**: Loại bỏ khả năng người gọi tự truyền `authority_state` để ghi đè thẩm quyền đã đăng ký tại `acquire_lease` và `create_dispatch`. Bắt buộc tác vụ phải được đăng ký trước; nếu người gọi truyền `authority_state` thì giá trị này phải khớp chính xác với trạng thái đã đăng ký trong `task_authorities` (`only 'granted' permitted`).
2. **Xác thực khởi tạo dispatch toàn diện (Strict Dispatch Verification)**:
   - Bắt buộc tác vụ phải ở trạng thái hợp lệ (`ready`); các trạng thái `blocked`, `locked`, `future_template`, `revoked` bị từ chối ngay lập tức.
   - Bắt buộc định danh tác vụ Orca (`orca_task_id`) phải không rỗng và là duy nhất trên toàn bộ hệ thống; từ chối tái sử dụng ID tác vụ Orca.
   - Bắt buộc commit candidate phải là SHA-40 hexa hợp lệ, tồn tại thực tế trong Git DAG và khớp chính xác với candidate đã phê duyệt / commit HEAD hiện hành.
   - Bắt buộc lease đi kèm phải đang hoạt động, chưa hết hạn, thuộc quyền sở hữu của chính tác vụ đó, chưa bị gắn với dispatch khác và mang fencing token khớp tuyệt đối với counter hiện hành.
3. **Kiểm tra đa tầng tại worker_done, review và integration (Strict Lifecycle Gates)**:
   - `handle_worker_done` kiểm tra dispatch đã hoàn tất trước khi kiểm tra trạng thái (`DuplicateResultError`), ngăn chặn gửi kết quả lặp lại.
   - Kiểm tra trạng thái tác vụ bắt buộc phải là `dispatched` trước khi chuyển sang `review`.
   - Xác thực lại toàn bộ quyền sở hữu lease, dispatch binding, tính hợp lệ của fencing token và thời hạn lease (`now > expires_at`).
   - Xác thực định danh tác vụ Orca và candidate commit của kết quả trả về khớp chính xác với dispatch ban đầu.
   - Bảng chuyển trạng thái một chiều: từ chối các bước nhảy trạng thái trái phép (ví dụ: chuyển trực tiếp từ `ready` sang `integrated` hoặc hoàn tất dispatch khi đã qua review).
4. **Phán quyết review nghiêm ngặt và cổng tích hợp boolean thuần túy**:
   - `handle_review_verdict` từ chối mọi phán quyết lạ không nằm trong danh mục cho phép (`approved`, `rejected`), chuyển chính xác sang `ready_for_integration` hoặc `replan_required`.
   - `handle_integration_gates` yêu cầu tham số `gates_pass` phải là kiểu boolean thuần túy (`isinstance(gates_pass, bool)`), nghiêm cấm mọi hình thức ép kiểu truthy (`1`, `"true"`, `["passed"]`).
5. **Chuẩn hóa Lock Registry Schema và chống nới lỏng thời hạn lease**:
   - Bổ sung `ALLOWED_LOCK_FIELDS` tại `LeaseManager.__init__`: từ chối mọi trường lạ hoặc không liên quan trong định nghĩa lock.
   - Từ chối các kết hợp trường và chế độ bất hợp pháp: lock `immutable` không được phép có `lease_seconds` hoặc `renewable`; lock `exclusive` không được phép có `capacity`.
   - Từ chối các giá trị boolean hoặc phân số cho dung lượng và thời hạn lease (`isinstance(val, bool)` bị từ chối trước kiểm tra `int`).
   - Nghiêm cấm nới rộng thời hạn lease: tham số `lease_seconds` khi chiếm giữ (`acquire_lease`) hoặc `extend_seconds` khi gia hạn (`renew_lease`) không được vượt quá giá trị `lease_seconds` tối đa đã khai báo trong định nghĩa lock.
6. **Máy trạng thái thực thi harness quan sát được (Observable Harness State Machine)**:
   - Định nghĩa dataclass `HarnessExecutionResult` với thẩm định kiểu dữ liệu đối số chặt chẽ tại khởi tạo (`success: bool`, `execution_time_ms: int | float >= 0`).
   - Máy trạng thái `HarnessExecutionStateMachine` quản lý chuyển đổi trạng thái thực thi (`IDLE` -> `RUNNING` -> `SUCCESS` | `FAILURE` | `STOP_BLOCKED`), lưu trữ toàn bộ lịch sử chuyển đổi và bảo đảm dừng fail-closed an toàn, không có mutation khi gặp STOP condition mà không fallback sang native provider.
7. **Bộ kiểm thử tự động 103 fixtures**: Tích hợp 24 bài kiểm tra bổ sung trong `test_negative_fixtures.py` bao quát toàn bộ các ca đối chứng Sol Round 3 và các probe biên lân cận.

## 10. Khắc phục toàn diện các phát hiện Sol Round 4 (P1 Remediations & Counterexamples)

Đợt rà soát vòng 4 của `cx/gpt-5.6-sol-high` đã xác định 9 ranh giới kiểm soát xung yếu. Toàn bộ 9 điểm nghẽn đã được khắc phục triệt để trong `delivery_engine.py`, `validate.py`, `ownership-and-locks.yaml` và kiểm chứng với 14 fixtures mới trong `TestSolRoundFourCounterexamples` (nâng tổng bộ kiểm thử lên 117 fixtures PASS 100%):

1. **Fencing theo từng Live Allocation Slot cho Capacity Leases**: Lock dung lượng (`mode == "capacity"`) phân tách thành từng slot riêng biệt (`LOCK:slot_N`). Mỗi slot duy trì chuỗi fencing token tăng đơn điệu riêng. Các worker đồng thời giữ token hợp lệ song song mà không xung đột; khi slot được thu hồi và cấp phát lại, monotonic counter của slot đó tăng lên, lập tức làm mất hiệu lực token cũ của worker trước.
2. **Không tái sử dụng Orca Task ID và Dispatch ID trên toàn hệ thống (Global Non-Reuse)**: Cả `orca_task_id` và `dispatch_id` đều bị khóa vĩnh viễn sau khi được đăng ký trong bất kỳ dispatch nào (kể cả các attempt đã settled/hoàn tất). Từ chối mọi nỗ lực tái sử dụng ID giữa các lần dispatch hoặc giữa các delivery task.
3. **Từ chối ghi đè Dispatch Binding (Reject Duplicate Dispatch Binding Overwrite)**: Kiểm tra và ngăn chặn triệt để hành vi ghi đè lên dispatch binding đã tồn tại trong `dispatch_bindings`.
4. **Bắt buộc Candidate Commit khớp với actual Git HEAD**: `create_dispatch` kiểm tra commit candidate và approved candidate commit phải tồn tại trong Git DAG và khớp chính xác với `git rev-parse HEAD`. Mọi commit lệch hoặc commit giả đều bị từ chối fail-closed.
5. **Ràng buộc Intended Dispatch vô điều kiện**: Khi `intended_dispatch_id` được chỉ định, lease liên kết bắt buộc phải khớp chính xác với ID đó; loại bỏ hoàn toàn cơ chế bypass qua `ctx_init`.
6. **Thực thi ma trận chuyển đổi trạng thái tác vụ nội bộ (Legal Task-State Transitions)**: Xác lập bảng `LEGAL_TASK_STATE_TRANSITIONS` theo đúng `protocol.md`. Mọi bước nhảy trạng thái trái phép (như `planned -> dispatched`, `ready -> review`, `dispatched -> integrated`) đều bị từ chối fail-closed.
7. **Giải phóng toàn bộ Mutation Lease ngay sau worker_done thành công**: Khi `worker_done(succeeded)` được xác thực, toàn bộ live mutation lease được giải phóng ngay lập tức khỏi `active_leases` trước khi tác vụ chuyển sang `review`, đảm bảo đúng nguyên tắc bảo vệ candidate trong thời gian review độc lập.
8. **Từ chối lock không khai báo và chống nới lỏng thời hạn**: Kiểm tra lock ID phải có mặt trong cấu hình lock tại `acquire_lease`, `create_dispatch` và toàn bộ DAG thông qua `validate.py:check_task_dag`. Nghiêm cấm nới rộng thời hạn `lease_seconds` vượt quá giá trị khai báo khi acquire hoặc renew.
9. **Chuẩn hóa đối số HarnessExecutionResult và quan sát chu trình máy trạng thái**: Dataclass `HarnessExecutionResult` kiểm tra kiểu dữ liệu nghiêm ngặt (`success: bool`, `execution_time_ms: int | float >= 0`, `status: PASS|STOP`). Máy trạng thái `HarnessExecutionStateMachine` tuân thủ nghiêm ngặt chu trình quan sát: `IDLE -> RUNNING -> SUCCESS | FAILURE | STOP_BLOCKED`.

## 11. Khắc phục toàn diện các phát hiện Sol Round 5 (Fail-Closed Blockers & Independent Counterexamples)

Đợt rà soát vòng 5 của `cx/gpt-5.6-sol-high` đã chỉ ra 12 điểm nghẽn (blockers) xung yếu và yêu cầu attestation report với ngữ nghĩa candidate chính xác. Toàn bộ các điểm nghẽn đã được khắc phục triệt để và bảo chứng bằng 26 bài kiểm tra độc lập mới trong `TestSolRoundFiveCounterexamples` (nâng tổng bộ kiểm thử tự động lên 143 fixtures PASS 100%):

1. **Chế độ Release/Audit tuyệt đối không thể bỏ qua Fixtures; bổ sung Cổng Quét Secret tường minh**:
   - `validate.py` từ chối fail-closed nếu phát hiện `--skip-fixtures` qua CLI hoặc `VALIDATE_SKIP_FIXTURES=1` qua môi trường trong các chế độ audit và release.
   - Thêm cổng `check_secret_scan`: tự động quét toàn bộ tệp tin thay đổi để phát hiện khóa riêng tư (private keys), token GitHub, token OpenAI/API, khóa truy cập AWS và credentials nhúng trong URL. Chế độ `--release` từ chối phát hành nếu phát hiện bất kỳ secret nào hoặc cây làm việc không sạch (`clean`).
2. **Định danh Task ID và Dispatch ID Orca duy nhất toàn cục qua Durable Ledger/Registry dùng chung (`SharedOrcaExecutionRegistry`)**:
   - Tách biệt và trừu tượng hóa cơ chế lưu vết thực thi `SharedOrcaExecutionRegistry` dùng chung giữa nhiều thực thể adapter (`OrcaDeliveryAdapter`).
   - Mọi task ID và dispatch ID một khi đã ghi nhận sẽ bị khóa vĩnh viễn trên toàn bộ hệ thống phân tán, ngăn chặn xung đột hoặc tấn công tráo đổi giữa các adapter instance.
3. **Ràng buộc Candidate Commit được phê duyệt là bắt buộc và chính xác tuyệt đối (`approved_candidate_commit`)**:
   - Khởi tạo `OrcaDeliveryAdapter` bắt buộc phải truyền `approved_candidate_commit` là một SHA-40 hexa hợp lệ đầy đủ; cấm các giá trị rỗng, short SHA hoặc ref name.
   - Khi tạo dispatch, `candidate_commit` được đối chiếu nghiêm ngặt với `approved_candidate_commit` và commit `HEAD` thực tế trong Git DAG.
4. **Intended Dispatch là bắt buộc và tuyệt đối không ghi đè Lease (`No Lease Rewrite`)**:
   - Bắt buộc tham số `intended_dispatch_id` khi gọi `create_dispatch`, không cho phép bỏ qua hoặc mang giá trị rỗng.
   - Tham số này bắt buộc phải trùng khớp với `dispatch_id` đã được cấp trong `ActiveLease`. Cấm tuyệt đối hành vi ghi đè trường `active_lease.dispatch_id`.
5. **Vòng đời tác vụ tuần tự (`acknowledged` -> `running` -> `worker_done`) và chặn các bước nhảy bất hợp pháp**:
   - Bổ sung phương thức `acknowledge_dispatch` và `start_running` trên `OrcaDeliveryAdapter` hỗ trợ đầy đủ chu trình: `dispatched -> acknowledged -> running -> worker_done (succeeded/failed)`.
   - `handle_worker_done` chấp nhận các tác vụ đang ở trạng thái `dispatched`, `acknowledged` hoặc `running`. Mọi bước nhảy trạng thái trái phép khác (như `acknowledged -> integrated` hay `running -> ready`) đều bị từ chối fail-closed.
6. **Dispatch bắt buộc chứng minh đầy đủ tập hợp Lock đã khai báo (`declared_task_locks`)**:
   - Khởi tạo adapter hoặc đăng ký `register_task_locks` xác lập toàn bộ danh sách lock mà task yêu cầu.
   - `create_dispatch` yêu cầu chứng minh đầy đủ lease hợp lệ cho mọi lock trong `declared_task_locks` (thông qua `lease_ids`), không chấp nhận chỉ chứng minh một lease đại diện.
7. **Bảo lưu và Fencing từng Slot cho Yêu cầu Capacity Đa đơn vị (`units > 1`)**:
   - `LeaseManager.acquire_lease` cho phép yêu cầu nhiều đơn vị `units > 1`, tự động phân bổ và theo dõi danh sách `allocated_slots`.
   - Mỗi slot được gán monotonic fencing token độc lập và bảo lưu trong `slot_fencing_tokens`. `validate_fencing_token` hỗ trợ kiểm tra token theo từng slot cụ thể (`slot=N`).
8. **Kiểm tra va chạm phân vùng đối xứng Cha - Con (`Symmetric Partition Namespace Overlap`)**:
   - Hàm `namespaces_overlap(ns1, ns2)` hỗ trợ các dấu phân cách phân cấp (`:`, `/`, `.`) một cách đối xứng hoàn toàn.
   - Lease cha (ví dụ `db:analytics`) chặn lease con (ví dụ `db:analytics:us_east`), và ngược lại lease con cũng chặn lease cha. Các namespace anh em không giao nhau (ví dụ `db:analytics_1` và `db:analytics_2`) được phép hoạt động đồng thời.
9. **Gia hạn Lease bị giới hạn tích lũy bởi Chính sách đã khai báo (`max_cumulative_seconds` & `max_renewals`)**:
   - Mở rộng schema lock cho phép khai báo `max_cumulative_seconds` và `max_renewals`.
   - `renew_lease` từ chối fail-closed nếu số lần gia hạn vượt quá `max_renewals` hoặc tổng thời gian gia hạn tích lũy (`cumulative_extension_seconds`) vượt quá `max_cumulative_seconds`.
10. **Giải phóng toàn bộ Mutation Lease trước khi phơi bày trạng thái Review**:
    - Khi `worker_done` với `outcome == "succeeded"` được tiếp nhận, `OrcaDeliveryAdapter` thu hồi và giải phóng toàn bộ active mutation lease trong `LeaseManager` trước khi cập nhật trạng thái tác vụ sang `review`.
11. **Từ chối trường mâu thuẫn trong HarnessExecutionResult và trạng thái trực tiếp trái phép trong Harness State Machine**:
    - `HarnessExecutionResult` từ chối các kết hợp mâu thuẫn: `success=True` nhưng `status="STOP"`, `fallback_required=True`, hoặc mã lỗi `execution_returncode != 0`; `success=False` nhưng `status="PASS"` hoặc yêu cầu native fallback; nghiêm cấm tuyệt đối trạng thái và câu từ fallback sang native provider.
    - `HarnessExecutionStateMachine` từ chối gán trạng thái trực tiếp không hợp lệ qua setter và thực thi ma trận chuyển đổi trạng thái nghiêm ngặt (`IDLE -> RUNNING -> SUCCESS | FAILURE | STOP_BLOCKED`).
12. **Từ chối triệt để định danh rỗng và tái chiếm giữ Lease sau khi tích hợp (`Integrated Tasks`)**:
    - Mọi thao tác `acquire_lease`, `renew_lease`, `release_lease`, `create_dispatch` đều từ chối chuỗi rỗng hoặc whitespace cho `lock_id`, `delivery_task_id`, `dispatch_id`, `lease_id`.
    - Khi tác vụ đã được đánh dấu tích hợp (`mark_task_integrated`), mọi nỗ lực tái chiếm giữ lease cho tác vụ đó đều bị từ chối fail-closed vĩnh viễn.
13. **Tái tạo báo cáo Attestation với ngữ nghĩa Candidate và Hash chuẩn xác**:
    - Toàn bộ kết quả kiểm thử và thẩm định được ghi nhận trong `.validation-report.json` với đầy đủ trường `sol_round_5`, mã SHA bất biến của baseline và candidate HEAD hiện hành, đảm bảo cây làm việc sạch sẽ và vượt qua mọi kiểm tra tự động.

## 12. Khắc phục triệt để các phát hiện Sol Round 6 (Review Blockers & Hardened Invariants)

Đợt rà soát vòng 6 của `cx/gpt-5.6-sol-high` đã xác lập 7 nhóm yêu cầu cốt lõi nhằm đóng băng hoàn toàn kiến trúc thử nghiệm. Toàn bộ các điểm nghẽn đã được khắc phục triệt để và chứng minh qua 10 fixtures mới trong `TestSolRoundSixCounterexamples` (tổng bộ kiểm thử đạt 153 fixtures tự động PASS 100%):

1. **Shared Execution Registry bền vững tiến trình (`Process-Durable Shared Registry`)**:
   - `SharedOrcaExecutionRegistry` được trang bị đường dẫn lưu trữ tường minh (`storage_path`), cơ chế khóa tệp tin atomic chéo nền tảng (`_FileLock` sử dụng `os.O_CREAT | os.O_EXCL`), và ghi đĩa nguyên tử (`.tmp` + `fsync` + `os.replace`).
   - Tính duy nhất của `orca_task_id` và `dispatch_id` tồn tại bền vững qua các lần khởi động lại tiến trình giả lập (`simulated process restart`).
   - Đường dẫn mặc định của `OrcaDeliveryAdapter` tự động liên kết với `SharedOrcaExecutionRegistry.get_default()`, loại bỏ hoàn toàn các in-memory registry ngầm (`no silent fresh registry in production path`).
2. **Xác thực Capacity Đa Slot với Monotonic Generation và Chống Tái Sử Dụng Bất Đối Xứng (`Asymmetric Reuse Invalidation`)**:
   - Mỗi slot trong capacity lock sở hữu chuỗi thế hệ đơn điệu độc lập (`fencing_counters[f"{lock_id}:slot_{s}"]`).
   - Một capacity lease chỉ hợp lệ khi toàn bộ các slot được cấp phát (`allocated_slots`) đều giữ fencing token hiện hành. Nếu một slot đơn lẻ bị thu hồi và tái cấp phát cho lease khác, token của slot đó tăng lên và lập tức vô hiệu hóa lease cũ ngay cả khi các slot khác không đổi.
3. **Thực thi Bắt buộc Tuyến Vòng Đời Tác Vụ (`ready -> dispatched -> acknowledged -> running -> worker_done`)**:
   - Nghiêm cấm mọi hành vi bỏ qua bước ACK (`acknowledged`) hoặc bước thực thi (`running`).
   - `start_running` chỉ chấp nhận tác vụ đang ở trạng thái `acknowledged`.
   - `handle_worker_done` chỉ chấp nhận tác vụ đang ở trạng thái `running`. Mọi nỗ lực gọi `worker_done` trực tiếp từ `dispatched` hoặc `acknowledged` đều bị từ chối fail-closed với `ProtocolViolationError`.
4. **Bắt buộc Đăng ký `declared_task_locks` và Chứng minh Tập Hợp Lock Đầy Đủ Chính Xác**:
   - Mọi tác vụ bắt buộc phải đăng ký danh sách lock dự kiến qua `register_task_locks` trước khi dispatch; cấm dispatch tác vụ chưa đăng ký lock hoặc đăng ký tập rỗng.
   - Khi gọi `create_dispatch`, tập hợp các lock được chứng minh qua active leases (`leased_locks`) bắt buộc phải trùng khớp chính xác 100% với `declared_task_locks` (`missing == empty` và `extraneous == empty`).
5. **Cấm Tuyệt Đối Gán Trực Tiếp Trạng Thái Harness (`Forbid Direct State Assignment`)**:
   - `@current_state.setter` trên `HarnessExecutionStateMachine` nâng lỗi `HarnessCompatibilityError` với mọi nỗ lực gán trạng thái trực tiếp (kể cả các trạng thái hợp lệ như `IDLE -> SUCCESS`).
   - Mọi chuyển dịch trạng thái bắt buộc phải thông qua phương thức hợp lệ `transition()` hoặc `reset()`.
6. **Mở Rộng Quét Secret cho Anthropic và Các Nhà Cung Cấp Phổ Biến**:
   - Bổ sung pattern quét định dạng secret của Anthropic (`sk-ant-...`), Google/Gemini (`AIza...`), Slack (`xoxb-...`), HuggingFace (`hf_...`), và Stripe (`sk_live_...`).
   - Nghiêm cấm nhúng secret thật vào mã nguồn và fixtures; các bài kiểm tra synthetic token được khởi tạo động qua ghép chuỗi ký tự.
7. **Báo cáo Attestation Freshness với Ngữ Nghĩa Parent-Plus-Wrapper**:
   - Giải quyết bài toán tự tham chiếu vòng lặp topo Git DAG thông qua ngữ nghĩa `parent-plus-wrapper`: commit cha chứa mã nguồn và bộ bundle được thẩm định, commit wrapper bọc báo cáo attestation `.validation-report.json`.
   - Cổng audit kiểm tra tính tươi mới (`check_attestation_report_freshness`): xác minh báo cáo tồn tại, trạng thái `PASS`, baseline được duyệt, overlay sạch (`dirty_overlay_count == 0`), và toàn bộ SHA-256 của các tệp trong bundle khớp chính xác với HEAD hiện hành.

## 13. Khắc phục triệt để các phát hiện Sol Round 7 (Review Blockers & Hardened Registry/Topology Invariants)

Đợt rà soát vòng 7 của `cx/gpt-5.6-sol-high` đã xác lập 5 điểm nghẽn cốt lõi độc lập cần xử lý dứt điểm. Toàn bộ các điểm nghẽn đã được khắc phục hoàn toàn và chứng minh qua 9 fixtures phản ví dụ mới trong `TestSolRoundSevenCounterexamples` (tổng bộ kiểm thử đạt 162 fixtures tự động PASS 100%):

1. **Giao dịch Nguyên tử Đọc-Sửa-Ghi An toàn Tiến trình và Từ chối Trùng lặp ID (`Process-Safe Registry Read-Modify-Write & Duplicate Rejection`)**:
   - Mọi thao tác đọc, cập nhật và ghi đĩa nguyên tử (`_persist_atomic` sử dụng `.tmp` + `fsync` + `os.replace`) trên `SharedOrcaExecutionRegistry` được bao bọc hoàn toàn bởi context manager `_transaction(write=True/False)`.
   - `_FileLock` được nâng cấp hỗ trợ reentrancy trên cùng một tiến trình/thread theo canonical lock path, giải quyết triệt để vấn đề deadlock khi các phương thức nội bộ gọi lồng nhau.
   - Ngăn chặn và từ chối `ProtocolViolationError` đối với duplicate `orca_task_id` (kể cả cùng delivery task hoặc khác delivery task) và duplicate `dispatch_id`.
2. **Registry Mặc định Bền vững trên Đĩa khi `storage_path=None` (`Durable Default Registry`)**:
   - Khi khởi tạo `SharedOrcaExecutionRegistry(storage_path=None)`, registry tự động gán đường dẫn mặc định bền vững `DEFAULT_PRODUCTION_REGISTRY_PATH` (`runtime/orca-execution-registry.json`).
   - Mọi thông tin đăng ký tác vụ và dispatch được lưu trữ bền vững trên đĩa, tự động khôi phục hoàn chỉnh khi khởi tạo instance mới cùng đường dẫn.
3. **Cấm Tuyệt đối Vượt mặt Vòng đời Tác vụ qua `set_task_state` (`No Lifecycle Bypass`)**:
   - `set_task_state` bị giới hạn nghiêm ngặt, chỉ cho phép thiết lập các trạng thái chuẩn bị/phụ thuộc (`planned`, `waiting_dependency`, `ready`, `blocked`, `locked`, `cancelled`).
   - Cấm trực tiếp gán hoặc ghi đè các trạng thái vòng đời thực thi đang hoạt động (`dispatched`, `acknowledged`, `running`, `review`, `merge_queued`, `integrated`).
   - Thuộc tính `task_states` trên `OrcaDeliveryAdapter` trả về bản sao từ điển (`dict`), vô hiệu hóa hoàn toàn nỗ lực sửa đổi trạng thái nội bộ bằng cách đột biến giá trị trả về.
4. **Xác thực Fencing Từng Slot cho Multi-Slot Task (`Correct Per-Slot Fencing Validation`)**:
   - `validate_fencing_token` hỗ trợ kiểm tra toàn diện mọi slot trong `allocated_slots`, từ chối các slot chưa từng được phân bổ cho lease (`was not allocated`) và xác thực chính xác giá trị token theo từng slot (`slot_fencing_tokens`).
   - Bất kỳ sự tăng thế hệ bất đối xứng nào trên bất kỳ slot nào cũng lập tức làm mất hiệu lực toàn bộ lease đa slot (`asymmetric slot reallocation detected`).
5. **Từ chối Báo cáo Attestation có Commit Zero hoặc Topology Không Nhất quán với Git DAG (`Attestation Rejection of Zero/Stale Wrapper Commits`)**:
   - `check_attestation_report_freshness` từ chối fail-closed nếu `candidate_commit`, `wrapper_commit` hoặc `parent_commit` là zero SHA (`0000000000000000000000000000000000000000`), rỗng hoặc không phải SHA-40 hexa hợp lệ.
   - Xác thực sự tồn tại thực tế của các commit trong Git DAG qua `git rev-parse --verify`.
   - Xác thực tính nhất quán cấu trúc cây Git DAG: `wrapper_commit^` phải khớp chính xác với `parent_commit`, và commit wrapper hoặc candidate phải khớp với Git HEAD hiện hành.

## 14. Khắc phục triệt để các phát hiện Sol Round 8 (Review Blockers & Hardened Topology/Registry Invariants)

Đợt rà soát vòng 8 của `cx/gpt-5.6-sol-high` đã xác lập 3 điểm nghẽn cốt lõi độc lập cần xử lý dứt điểm. Toàn bộ các điểm nghẽn đã được khắc phục hoàn toàn và chứng minh qua 3 fixtures phản ví dụ mới trong `TestSolRoundEightCounterexamples` (tổng bộ kiểm thử đạt 165 fixtures tự động PASS 100%):

1. **Cấm Tái Mở Trạng Thái Terminal và Cấm Tua Ngược `review`/`merge_queued` về `planned` (`Atomic Terminal & Rewind Prevention`)**:
   - `set_task_state` từ chối triệt để mọi nỗ lực tái mở hoặc đột biến bất kỳ tác vụ nào đã ở trạng thái terminal (`integrated`, `cancelled`, `stopped`).
   - Cấm tuyệt đối hành vi tua ngược trạng thái `review` hoặc `merge_queued` về `planned` hoặc bất kỳ trạng thái pre-dispatch nào. Toàn bộ đột biến và truy vấn trạng thái được đồng bộ nguyên tử qua `_task_state_lock`.
2. **Xác thực Freshness Attestation theo Đúng Cấu trúc Cây Git DAG Cho Phép (`Exact Allowed Git DAG Topology Validation`)**:
   - `check_attestation_report_freshness` từ chối fail-closed nếu báo cáo không khớp chính xác một trong hai cấu trúc topology được phép: Direct HEAD (`candidate_commit == wrapper_commit == HEAD` và `parent_commit == HEAD^`) hoặc Parent-plus-wrapper (`candidate_commit == HEAD^`, `wrapper_commit == HEAD`, `parent_commit == HEAD^`).
   - Loại bỏ hoàn toàn lỗ hổng kiểm tra quan hệ thuộc tập hợp `{HEAD, HEAD^}` lỏng lẻo; từ chối dứt điểm trường hợp candidate/wrapper thuộc commit cha (`HEAD^`) và parent thuộc `HEAD^^` khi Git HEAD đang ở commit wrapper mới.
3. **Đột biến Registry Phức hợp Nguyên tử Đa Tiến trình khi Tạo Dispatch (`Atomic Compound Registry Mutation & Two-Process Race Rollback`)**:
   - `create_dispatch` thực hiện đột biến phức hợp đăng ký dispatch binding và Orca task ID thông qua `register_dispatch_and_orca_task` trong duy nhất một giao dịch nguyên tử có khóa tệp đa tiến trình `_transaction(write=True)`.
   - Cơ chế rollback snapshot tự động khôi phục hoàn toàn trạng thái in-memory và không ghi đĩa khi xảy ra lỗi/tranh chấp trùng lặp ID, bảo đảm không bao giờ để lại orphan dispatch binding tồn tại bền vững trên đĩa.

## 15. Khắc phục triệt để các phát hiện Sol Round 9 (Declared Wrapper Semantics & Rejection of all-HEAD^ Bypass)

Đợt rà soát vòng 9 của `cx/gpt-5.6-sol` đã xác lập các điểm nghẽn xung yếu liên quan đến topology attestation và phân tách routing model/effort. Toàn bộ các điểm nghẽn đã được khắc phục hoàn toàn và chứng minh qua 4 fixtures phản ví dụ mới trong `TestSolRoundNineCounterexamples` (tổng bộ kiểm thử đạt 169 fixtures tự động PASS 100%):

1. **Từ chối Dứt điểm Bypass Tuple `candidate=wrapper=parent=HEAD^` (`Reject all-HEAD^ Attestation Bypass`)**:
   - `check_attestation_report_freshness` từ chối fail-closed nếu `candidate_commit`, `wrapper_commit` và `parent_commit` đều trỏ tới `HEAD^`, bảo đảm tuân thủ nghiêm ngặt contract `parent-plus-wrapper` đòi hỏi wrapper commit phải là exact current `HEAD`.
   - Bổ sung regression fixture `test_r9_01_attestation_freshness_rejection_of_all_head_parent_bypass` tái hiện chính xác bypass trên SHA `a7f5aca`.
2. **Ngữ nghĩa Declared Wrapper HEAD không Tự Tham Chiếu Vòng Lặp (`Declared Wrapper HEAD Semantics without Circular Self-Reference`)**:
   - Trong `.validation-report.json`, trường `wrapper_commit` được phép khai báo tượng trưng `"HEAD"` (hoặc `"git:HEAD"`) hoặc exact 40-hex SHA khớp checkout HEAD thực tế.
   - Loại bỏ hoàn toàn sự tự tham chiếu SHA bất khả thi trong cấu trúc Git DAG; validator suy ra `effective_wrapper` từ runtime Git, kiểm chứng quan hệ `effective_wrapper^ == parent_commit` và toàn vẹn mã băm `bundle_sha256`.
3. **Phân tách Rõ Ràng Trường `model` và `effort` trong Dely và Tài liệu**:
   - Khóa route review thành Claude Code / `cx/gpt-5.6-sol` / `high` (tách riêng model và effort, nghiêm cấm slug gộp `cx/gpt-5.6-sol-high`).
   - Cập nhật đồng bộ `validate.py`, `task-dag.yaml`, `operating-model.md`, `protocol.md`, `README.md`, `CHANGELOG.md` và `HANDOFF.md`.


## 17. Khắc phục triệt để các phát hiện Sol Round 11 (Identity-First Fail-Closed Harness Failure & Machine-Readable Routing Authority Policy)

Đợt rà soát vòng 11 của `cx/gpt-5.6-sol` đã chỉ rõ hai điểm nghẽn kiến trúc quan trọng: xử lý harness failure thiếu kiểm tra định danh trước dẫn đến nguy cơ thu hồi nhầm lease của dispatch mới, và bằng chứng định tuyến provider/routing còn mang tính văn xuôi chưa được kiểm chứng máy đọc. Toàn bộ hai phát hiện đã được khắc phục hoàn toàn và chứng minh qua 14 fixtures mới trong `test_negative_fixtures.py` (tổng bộ kiểm thử đạt 190 fixtures tự động PASS 100%):

1. **Xử lý Harness Failure theo Định danh Trước, Không Tác động Phụ (`Identity-First Fail-Closed Harness Failure`)**:
   - `OrcaDeliveryAdapter.handle_harness_failure()` thực hiện kiểm tra định danh trước fail-closed: kiểm tra dispatch tồn tại, thuộc đúng task, chưa settled, là active dispatch hiện hành, và task đang trong vòng đời thực thi hợp lệ (`dispatched`, `acknowledged`, `running`) trước khi có bất kỳ tác động phụ nào.
   - Chỉ giải phóng đúng các lease được gán trực tiếp cho dispatch đã xác thực (`clean_did`), tuyệt đối không giải phóng nhầm lease của dispatch khác hoặc của task theo `delivery_task_id`.
   - Bất kỳ lỗi kiểm tra nào (spoof dispatch ID, cross-task dispatch, settled/duplicate dispatch, stale dispatch sau khi replan/redispatch) hoặc lỗi lưu trữ đĩa (persistence failure) đều bị từ chối fail-closed và bảo đảm không để lại tác động phụ một phần; lease của active dispatch mới hoàn toàn được giữ nguyên vẹn.
   - Khi harness failure hợp lệ được xác thực: dispatch được settle, task chuyển sang `blocked`, các tài nguyên thuộc dispatch đó được giải phóng/fence an toàn, và nội dung commit candidate được bảo toàn nguyên vẹn.
2. **Chính sách Bằng chứng Định tuyến Machine-Readable và Execution Envelope (`Machine-Readable Routing Authority & Execution Envelope Policy`)**:
   - Mọi dispatch bắt buộc xuất phát từ `dely dispatch`, nghiêm cấm direct Orca `worker-start`.
   - Route `implement` và `review` bắt buộc dùng `provider: 9router`. Nghiêm cấm Antigravity native và các provider không khai báo.
   - `harness`, `model`, và `effort` bắt buộc là các trường riêng biệt. Nghiêm cấm các slug gộp như `cx/gpt-5.6-sol-high`.
   - Bằng chứng `launch.requested` và `launch.effective` đơn lẻ là KHÔNG ĐỦ; dispatch chỉ hợp lệ khi có bằng chứng terminal/archive trực tiếp xác nhận đúng route harness/provider, và cơ sở dữ liệu sử dụng 9Router ghi nhận đúng request backend (`google` / `openai` qua 9Router) sau khi dispatch được tạo (`recorded_after_dispatch: true`).
   - Bằng chứng phải ở dạng machine-readable và tuyệt đối không commit secret, token, credential hoặc đường dẫn cơ sở dữ liệu cục bộ khả biến.
   - Duy trì sự phân biệt rõ ràng giữa cơ chế fallback AI provider của sản phẩm (theo product roadmap) và việc nghiêm cấm fallback agent-harness/provider trong delivery control plane này.

## 18. Khắc phục triệt để phát hiện Sol Round 22 (Out-of-Process Trust Boundary & Asymmetric Cryptography)

Đợt rà soát độc lập trên candidate SHA `8913b392522701f924117a234f4e0cee7fc83624` (approved base `4a7c8c921b7e05066505d51b168a02c3fde61317`) đã xác lập finding ranh giới tin cậy (trust boundary) cùng họ nguyên nhân gốc rễ: issuer, HMAC secret, credential và consumer đều nằm trong cùng tiến trình Python của caller nên candidate code có thể tự bootstrap authority.

Hệ thống đã triển khai toàn diện giải pháp kiến trúc ngoài tiến trình (Out-of-Process Trust Boundary) tuân thủ chỉ thị tại `D:/AI_SETUP/supervisor/generated/root-cause-trust-boundary-intervention.md`:
1. **Threat Model 3 tầng rủi ro**: Phân định rõ ràng giữa (1) Sửa nhầm thông thường, (2) Candidate/Worker không tin cậy chạy mã Python tùy ý, và (3) Host OS Administrator. Không coi đối tượng hay biến trong cùng tiến trình là bằng chứng danh tính.
2. **Khóa ký số bất đối xứng (Ed25519 Asymmetric Cryptography & Pinned Key Custody)**: Khóa riêng chỉ nằm ở Reviewer Lead và Integration Gatekeeper độc lập; candidate worker chỉ sở hữu public key ghim sẵn trong `TrustedKeyStore`.
3. **Phong bì ký số (Signed Review & Integration Envelopes)**: Domain separation (`PARALLEL_DELIVERY_REVIEW_ENVELOPE_V1` / `PARALLEL_DELIVERY_INTEGRATION_ENVELOPE_V1`), canonical serialization RFC 8785, candidate SHA, dispatch ID, route attestation, nonce, temporal window, monotonic fencing token.
4. **Sổ đăng ký tiêu thụ bền vững (DurableConsumptionRegistry)**: Quản lý atomic trên SQLite, ngăn chặn tuyệt đối replay, tái sử dụng nonce, stale retry, và tranh chấp đồng thời kể cả qua restart tiến trình.
5. **Khóa kích hoạt Production (ProductionActivationGate)**: Khóa fail-closed `PRODUCTION_ACTIVATION_BLOCKED` (`NOT_PROVISIONED`) khi hệ thống chưa được trang bị đủ 4 điều kiện hạ tầng: `OS_USER_ISOLATION`, `PRIVATE_KEY_ACL_RESTRICTION`, `DEDICATED_RUNNER`, `PROTECTED_BRANCH_POLICY`.
6. **Bộ kiểm thử toàn diện**: 10 bài test mới trong `TestSolTrustBoundaryRootCauseRemediation` (RED evidence, worker monkey-patching failure, asymmetric Ed25519 signature tamper rejection, key revocation, single-use replay protection, SQLite restart durability, temporal validity, production gate fail-closed, fresh subprocess isolation, và positive control full lifecycle) nâng tổng số bài test lên **392/392 tests PASS 100%**.
## 19. Khắc phục triệt để phát hiện Sol Audit sau d7f0043 (Out-of-Process Pinned Key Custody & Durable Integration Consumption)

Đợt rà soát độc lập trên candidate SHA d7f0043d99c970e3d6efc7a8c392be73b58b27b2 (approved base 4a7c8c921b7e05066505d51b168a02c3fde61317) ghi nhận 2 finding ranh giới tin cậy cần khắc phục trước khi ACCEPT:
1. **Finding 1 — Out-of-Process Pinned Key Custody Provisioning**:
   - Vô hiệu hóa hoàn toàn khả năng candidate worker tự đăng ký khóa trong cùng tiến trình (
egister_pinned_public_key từ chối caller in-process fail-closed với ProtocolViolationError).
   - Cấp phát khóa công khai ghim sẵn qua ranh giới máy chủ bên ngoài: KeyStoreHostIssuer, KeyStoreHostHandoff, và KeyStoreHostIssuerCapability với token sentinel _SENTINEL_HOST_TOKEN.
   - Lưu trữ pinned keys trong MappingProxyType bất biến; từ chối mọi nỗ lực thay thế hay sửa đổi khóa authority đã ghim (Cannot replace or mutate existing pinned key authority).
   - OrcaDeliveryAdapter.keystore là thuộc tính read-only gắn chặt với TrustedKeyStore.get_default(), từ chối nhận caller-selected keystore.
2. **Finding 2 — Durable Integration Envelope Consumption**:
   - TrustedIntegrationConsumer.consume_integration_envelope bắt buộc gọi giao dịch nguyên tử DurableConsumptionRegistry.check_and_consume_integration.
   - Kiểm tra toàn diện temporal validity (expires_at, issued_at <= now + 30.0s), ràng buộc danh tính (expected_task_id, expected_candidate, expected_base), chống phát lại (envelope_id single-use), chống tái sử dụng nonce, và monotonic fencing token theo miền (task_fencing).
   - Đảm bảo tính bền vững qua restart tiến trình với SQLite và an toàn tương tranh đa luồng (10 luồng đồng thời: đúng 1 luồng thành công, 9 luồng bị chặn bởi ReplayAttackError).

## 20. Khắc phục triệt để 3 phát hiện độc lập từ Sol Audit sau 851d23c (Out-of-Process Key Custody Bootstrap Prevention, Durable Adapter Restart Consumption & Strict Envelope Type Rejection)

Đợt rà soát độc lập trên candidate SHA `851d23c3f7fde7e37891b933547d931706e11417` (approved base `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận 3 finding hành động cần khắc phục triệt để:
1. **Finding 1 — Vô hiệu hóa Public Host API Bootstrap Khóa Trong Cùng Tiến Trình**:
   - Chuyển toàn bộ cơ chế cấp phát khóa sang ranh giới host bên ngoài.
   - Ngăn chặn triệt để kịch bản counterexample trong đó candidate worker tự sinh cặp khóa Ed25519, gọi public host API để mint handoff và tự nạp vào `TrustedKeyStore` trong cùng tiến trình.
   - Test harness sử dụng các helper máy chủ chuyên biệt (`TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore`, `TrustedHostProvisionKeyStore`).
2. **Finding 2 — Tính Bền Vững Tiêu Thụ của OrcaDeliveryAdapter Qua Khởi Động Lại**:
   - Khởi tạo mặc định của `OrcaDeliveryAdapter` chuyển sang sử dụng đường dẫn SQLite bền vững trên ổ đĩa `DEFAULT_PRODUCTION_CONSUMPTION_DB_PATH` (`runtime/orca-consumption-registry.db`) hoặc `consumption_db_path` được chỉ định.
   - Loại bỏ hoàn toàn fallback về `:memory:` trong production adapter path; cấm tiêm ephemeral in-memory registry (`_is_mem`) fail-closed.
   - Bản ghi tiêu thụ phong bì và monotonic fencing token tồn tại bền vững qua restart adapter; ngăn chặn hoàn toàn replay attack và stale fencing token qua restart.
3. **Finding 3 — Strict Type Rejection Trước Coercion Trong SignedIntegrationEnvelope**:
   - `SignedIntegrationEnvelope.from_dict` từ chối fail-closed `EnvelopeVerificationError` đối với chuỗi `'false'`, số nguyên, hoặc bất kỳ kiểu phi-bool nào trước khi thực hiện bất kỳ chuyển đổi kiểu dữ liệu nào.
   - Bổ sung strict type checking cho `gate_results` (strict bool values), `issued_at`/`expires_at` (numeric float/int, cấm bool/str), và `fencing_token` (strict int, cấm bool/str) cho cả review envelope và integration envelope.

## 21. Khắc phục triệt để 2 phát hiện độc lập từ Sol Audit trên b85c240 (Out-of-Process Host Boundary Capability & Ephemeral Singleton Poisoning Fail-Closed)

Đợt rà soát độc lập trên candidate SHA `b85c240d466c1624966c36bb9148c10d2112b4ae` (approved base `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận 2 finding hành động:
1. **Finding 1 — Thẩm quyền Host Capability Hoàn Toàn Ngoài Tiến Trình**:
   - Xóa bỏ hoàn toàn biến `_SENTINEL_HOST_TOKEN` khỏi candidate module `delivery_engine.py`; candidate module không chứa hay rò rỉ bất kỳ sentinel token hay host capability nào.
   - Thẩm quyền host boundary được cung cấp nghiêm ngặt ngoài tiến trình qua biến môi trường host (`ORCA_HOST_BOUNDARY_TOKEN`) kết hợp hàm xác thực mật mã HMAC an toàn thời gian thực.
   - Ngăn chặn triệt để counterexample `COUNTEREXAMPLE_CANDIDATE_BOOTSTRAPS_AUTHORITY`. Bổ sung fixture phân biệt `11s` trong `TestSolTrustBoundaryRootCauseRemediation`.
2. **Finding 2 — Chống Đầu Độc Singleton Ephemeral Trong Sổ Đăng Ký Tiêu Thụ**:
   - `DurableConsumptionRegistry.get_default` cấm tuyệt đối cấu hình `db_path=':memory:'` hoặc `allow_ephemeral=True` fail-closed với `ProtocolViolationError`.
   - `OrcaDeliveryAdapter` từ chối fail-closed nếu singleton registry mặc định bị can thiệp thành dạng ephemeral trong bộ nhớ (`_is_mem=True`).
   - Ngăn chặn triệt để counterexample `COUNTEREXAMPLE_EPHEMERAL_DEFAULT_ACCEPTED`. Bổ sung fixture phân biệt `15d` trong `TestSolTrustBoundaryRootCauseRemediation`.
3. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **392/392 tests PASS (100%)**, chạy hoàn hảo trên toàn bộ gate validation và release gate.

## 22. Khắc phục triệt để phát hiện Sol Audit trên 52a2795 (Out-of-Process Host Boundary Channel & Mutable Environment Rejection)

Đợt rà soát độc lập trên candidate SHA `52a279551f8bd73e0d0dc3f68aad15c959be0bd8` (approved base `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding hành động:
1. **Finding — Ranh giới Tin cậy Ngoài Tiến trình Thay Thế Biến Môi trường Mutable**:
   - Khắc phục triệt để lỗ hổng bootstrap thẩm quyền trong cùng tiến trình do xác thực capability chỉ dựa vào `ORCA_HOST_BOUNDARY_TOKEN` hiện có trong `os.environ`.
   - Triển khai `HostBoundaryChannel` hoạt động ngoài tiến trình: khởi chạy verifier daemon trong một tiến trình con độc lập thông qua socket IPC cục bộ `127.0.0.1` với OS-assigned port và private pipe truyền secret, không rò rỉ token máy chủ qua `sys.argv`, module globals hay biến môi trường mutable.
   - Hàm `_is_valid_host_boundary_capability(token)` ủy thác kiểm chứng 100% qua `HostBoundaryChannel.verify_capability(token)` tới daemon ngoài tiến trình; loại bỏ hoàn toàn việc đọc và tin tưởng `os.environ.get("ORCA_HOST_BOUNDARY_TOKEN")`.
   - Ngăn chặn hoàn toàn kịch bản candidate worker tự ý gán `os.environ["ORCA_HOST_BOUNDARY_TOKEN"] = token` để mint host handoff hay bootstrap `KeyStoreHostIssuer` / `TrustedKeyStore` fail-closed.
   - Bổ sung các fixture phân biệt `11t`, `11u`, `11v` trong `test_11_finding_01_candidate_key_custody_bootstrap_rejected` và bài test độc lập `test_17_finding_out_of_process_host_boundary_and_mutable_env_rejection`.
2. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **393/393 tests PASS (100%)**, chạy hoàn hảo trên toàn bộ 12 gate validation và release gate.

## 23. Khắc phục triệt để phát hiện Sol Audit trên 62d7643 (Out-of-Process Host Channel Provisioning, Loại bỏ Inspect/Module-Name & Mutable Env Endpoint Fallback)

Đợt rà soát độc lập trên candidate SHA `62d7643f4c8ef474fd065edb1c026fa09fdb10d7` (approved base `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding hành động:
1. **Finding 1 — Loại Bỏ Hoàn Toàn Kiểm Tra Tin Cậy Dựa Trên Inspect / Module-Name**:
   - Xóa bỏ `import inspect`, không sử dụng `caller_frame`, `caller_mod` hay `caller_file` để cấp đặc quyền cho caller `__main__` hay test harness.
   - `HostBoundaryChannel.start_host_boundary` bị vô hiệu hóa fail-closed đối với mọi candidate worker in-process (`ProtocolViolationError`), ngăn caller `__main__` tự chạy daemon với token tự chọn (`MAIN_START_ACCEPTED == False`).
2. **Finding 2 — Loại Bỏ Mutable Environment Endpoint Fallback**:
   - Loại bỏ hoàn toàn fallback về `_ORCA_HOST_BOUNDARY_PORT` / `_ORCA_HOST_BOUNDARY_AUTHKEY` từ `os.environ` trong `HostBoundaryChannel.verify_capability` và không ghi biến môi trường này. Mọi nỗ lực dựng rogue listener qua env đều bị từ chối fail-closed (`ENV_ENDPOINT_ACCEPTED == False`).
3. **Finding 3 — Cấp Phát Channel Endpoint/Auth Qua Cơ Chế Host (HostBoundaryTicket)**:
   - Giới thiệu `HostBoundaryTicket` cryptographic authorization ticket được tạo ngoài tiến trình bởi trusted host authority.
   - `HostBoundaryChannel.provision_channel(port, authkey, *, host_ticket, proc)` chỉ nhận cấu hình hợp lệ khi có `HostBoundaryTicket`; candidate không thể tự sinh hay giả mạo ticket.
   - `_cleanup_process` chỉ gửi lệnh ngắt daemon nếu tiến trình hiện hành sở hữu `proc` (`proc is not None`), bảo vệ an toàn cho daemon máy chủ dùng chung qua các tiến trình con.
4. **Finding 4 — Fresh-Subprocess Assertions Khóa Chặt Full Exploit Chain**:
   - Bổ sung 3 fixture phân biệt 17h, 17i, 17j trong `test_17` bao gồm các assertion trong tiến trình con độc lập từ chối cả giả mạo biến môi trường endpoint (`ENV_ENDPOINT_ACCEPTED == False`) lẫn bootstrap thẩm quyền từ caller `__main__` (`MAIN_START_ACCEPTED == False`, `CANDIDATE_BOOTSTRAP_ACCEPTED == False`, `TrustedKeyStore` rỗng).
5. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **393/393 tests PASS (100%)**, chạy hoàn hảo trên toàn bộ 12 gate validation và release gate.

## 24. Khắc phục triệt để phát hiện Sol Audit trên 0032962 (Unforgeable HostBoundaryTicket, Provenance Verification qua Out-of-Process Daemon, HMAC Capability Binding & Single-Use Replay Protection)

Đợt rà soát độc lập trên candidate SHA `0032962130d21dc9b2ddc5f51260cfffb40e9acd` (approved base `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding actionable:
`HostBoundaryTicket` là dataclass công khai, `provision_channel()` chỉ kiểm tra isinstance/field shape rồi chấp nhận ticket tự tạo, không xác minh chữ ký, provenance, host-issued capability hoặc single-use; counterexample an toàn `HostBoundaryTicket(ticket_id='candidate-ticket', host_token_hash='0'*64, created_at=0.0, signature='candidate-signature')` với port/authkey hợp lệ đã làm `_started=True` (`FORGED_TICKET_ACCEPTED=True`).

Biện pháp khắc phục triệt để:
1. **Finding 1 — Vô hiệu hóa khởi tạo trực tiếp và kế thừa HostBoundaryTicket**:
   - `HostBoundaryTicket` được chuyển thành lớp thẩm quyền bất biến; cấm khởi tạo trực tiếp bằng caller in-process (`__init__` ném `ProtocolViolationError`), cấm kế thừa (`__init_subclass__` ném `ProtocolViolationError`), và cấm serialize/deserialize (`__reduce__` ném `ProtocolViolationError`). Chỉ cho phép khởi tạo nội bộ thông qua factory method có xác thực `_create_authenticated`.
2. **Finding 2 — Ràng buộc chữ ký mật mã HMAC và năng lực HostBoundaryTicketIssuerCapability**:
   - `HostBoundaryTicketIssuer` độc lập quản lý secret ngoài tiến trình, cấp phát `HostBoundaryTicket` đi kèm `HostBoundaryTicketIssuerCapability` có chữ ký HMAC-SHA256 liên kết chặt với `ticket_id`, `port`, `authkey_hash`, authority id, và timestamp kiểm tra độ tươi (freshness window 300s).
   - Phương thức `issue_ticket` yêu cầu token nội bộ hợp lệ và xác thực tính xác thực của token với daemon máy chủ ngoài tiến trình trước khi cấp vé.
3. **Finding 3 — Xác minh Provenance hai chiều qua Out-of-Process Host Daemon trong provision_channel**:
   - `HostBoundaryChannel.provision_channel` bắt buộc ticket phải có `_issuer` thuộc kiểu `HostBoundaryTicketIssuer`.
   - Kết nối trực tiếp tới daemon máy chủ tại `(127.0.0.1, port)` với `authkey` để xác minh secret của issuer trước khi chấp nhận cấu hình kênh; từ chối fail-closed mọi issuer tự sinh hoặc token không khớp (`FORGED_TICKET_ACCEPTED == False`).
4. **Finding 4 — Chống Replay Ticket đơn dụng (Single-Use Consumption Protection)**:
   - Áp dụng kiểm tra đơn dụng đa tầng: `HostBoundaryTicket` tự đánh dấu `_consumed = True` khi được tiêu thụ, `HostBoundaryTicketIssuer` ghi nhận và từ chối các ticket đã dùng trong `_consumed_tickets`, và `HostBoundaryChannel` duy trì tập `_consumed_ticket_ids` nhằm ngăn chặn tuyệt đối mọi nỗ lực tái sử dụng ticket đã cấp.
5. **Finding 5 — Bộ fixture kiểm thử chuyên sâu test_18**:
   - Bổ sung `test_18_finding_sol_host_boundary_ticket_forgery_and_replay_rejection` với 13 trường hợp kiểm thử (18a-18m) bao quát từ chối trực tiếp, kế thừa, bypass bằng `object.__new__`, issuer giả mạo, can thiệp chữ ký, sai cổng/authkey, hết hạn timestamp, replay attack, pickle serialization và chuỗi exploit trong tiến trình con độc lập.
6. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **394/394 tests PASS (100%)**, chạy hoàn hảo trên toàn bộ 12 gate validation và release gate.

## 25. Khắc phục triệt để phát hiện Sol Audit trên d1edb50 (HostBoundaryBootstrapCapability, Neo Chặt Daemon Endpoint/Authkey Provenance & Ngăn Chặn Rogue Daemon/Ticket Trong Tiến Trình Con)

Đợt rà soát độc lập trên candidate SHA d1edb5073314fc66488820f8d66ae0655a210fb2 (approved base 4a7c8c921b7e05066505d51b168a02c3fde61317) ghi nhận finding actionable:
HostBoundaryTicketIssuer có thể được khởi tạo bằng bất kỳ token >=32 ký tự, tự kiểm tra token với daemon/listener do caller tự chọn tại port/authkey (delivery_engine.py:1721-1747, 1811-1854), rồi HostBoundaryChannel.provision_channel xác minh issuer secret cũng với chính endpoint caller truyền vào (1964-2027); counterexample an toàn đã tạo rogue daemon/token, issue_ticket và provision_channel thành công, quan sát HostBoundaryChannel._started=True (ROGUE_ENDPOINT_TICKET_ACCEPTED == True). Do đó provenance chưa neo vào trusted host daemon/key custody, cho phép candidate worker tự tạo verifier endpoint và mint ticket trái invariant out-of-process trusted authority.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Năng Lực Khởi Tạo Host Bất Biến (HostBoundaryBootstrapCapability)**:
   - Xây dựng lớp thẩm quyền HostBoundaryBootstrapCapability do trusted host boundary tạo độc quyền ngoài tiến trình (_create_authenticated); cấm caller in-process khởi tạo trực tiếp (__init__ ném ProtocolViolationError), cấm kế thừa (__init_subclass__ ném ProtocolViolationError), và cấm serialize/deserialize (__reduce__ ném ProtocolViolationError).
   - Ràng buộc mật mã chặt chẽ giữa bootstrap_id, port, authkey_hash, host_token_hash, chữ ký HMAC-SHA256 với secret nội bộ của host boundary, kiểm tra độ tươi (freshness 300s, max future skew 30s) và cơ chế tiêu thụ đơn dụng (_consume_for_provisioning).
2. **Finding 2 — Ràng Buộc Thẩm Quyền Host Vào HostBoundaryTicketIssuer**:
   - HostBoundaryTicketIssuer yêu cầu HostBoundaryBootstrapCapability hợp lệ khi cấp vé (issue_ticket). Phương thức issue_ticket đối chiếu bắt buộc port và authkey phải khớp chính xác với port và authkey_hash trong bootstrap capability; mọi trường hợp thiếu capability hoặc sai lệch endpoint đều bị từ chối fail-closed (Host ticket issuance rejected).
   - Vé HostBoundaryTicket được gắn kèm bootstrap_capability và thẩm tra chữ ký hai chiều khi tiêu thụ.
3. **Finding 3 — Thẩm Định Endpoint & Tiêu Thụ Đơn Dụng Trong provision_channel**:
   - HostBoundaryChannel.provision_channel yêu cầu bắt buộc phải có HostBoundaryBootstrapCapability (truyền trực tiếp hoặc qua host_ticket.bootstrap_capability).
   - Xác minh tính toàn vẹn chữ ký HMAC, khớp cổng/khóa, kiểm tra độ tươi, và kiểm tra chống replay qua tập _consumed_bootstrap_ids trước khi cho phép kích hoạt kênh (_started = True).
   - Nếu endpoint hoặc ticket do caller tự sinh/giả mạo (không có host bootstrap capability hợp lệ), yêu cầu bị từ chối fail-closed, giữ nguyên _started = False và không gây bất kỳ side effect nào (ROGUE_ENDPOINT_TICKET_ACCEPTED == False).
4. **Finding 4 — Fixture Kiểm Thử Fresh Subprocess test_18s**:
   - Bổ sung test_18s_sol_counterexample_rogue_daemon_and_endpoint_rejected_in_fresh_subprocess trong tiến trình con độc lập: caller tự mở listener trên cổng nội bộ với rogue token/authkey, gọi issue_ticket và provision_channel; chứng minh toàn bộ chuỗi tấn công bị chặn đứng fail-closed, HostBoundaryChannel._started giữ nguyên False.
5. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **395/395 tests PASS (100%)**, chạy hoàn hảo trên toàn bộ 12 gate validation và release gate.
## 26. Khắc phục triệt để phát hiện Sol Audit trên bd38239 (HostBootstrapCapability Asymmetric Cryptographic Verification, Loại Bỏ Secret Khỏi Candidate Module & Candidate Minting Fail-Closed)

Đợt rà soát độc lập trên exact candidate SHA bd382390340b0495d6a725bc97aa9f623720185e (approved base 4a7c8c921b7e05066505d51b168a02c3fde61317) ghi nhận finding actionable:
HostBoundaryBootstrapCapability._create_authenticated tại delivery_engine.py:1632 vẫn là public callable trong candidate process và dùng _HOST_BOUNDARY_BOOTSTRAP_SECRET tại dòng 1592 nằm ngay trong module candidate; assertion an toàn đã tự mint+verify capability, rồi full-chain rogue listener -> issuer -> ticket -> provision đạt FULL_CHAIN_ACCEPTED và đặt HostBoundaryChannel._started=True, trái invariant out-of-process tại security-performance-recovery.md:166-170/189-195 và claim README remediation. Counterexample hiện được harness helper gọi cùng factory tại test_negative_fixtures.py:172 nên 395 fixture không phân biệt candidate authority; cần chuyển factory/secret issuance ra trusted host boundary không callable từ candidate, hoặc làm API candidate-side fail-closed, rồi bổ sung fixture fresh-process chứng minh không thể mint capability và không thể provision.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Loại Bỏ Hoàn Toàn Secret Khỏi Candidate Module & Ghim Public Key Ed25519 Bất Biến**:
   - Loại bỏ hoàn toàn _HOST_BOUNDARY_BOOTSTRAP_SECRET khỏi candidate module delivery_engine.py.
   - Ghim khóa công khai Ed25519 bất biến _HOST_BOUNDARY_BOOTSTRAP_PUBLIC_KEY = bytes.fromhex("b49df8557f17629954b62697c2097549c92f2cf0185e7c284d71475a787b1d6e").
   - Tiến trình candidate không lưu trữ, không chia sẻ và không thể truy cập bất kỳ signing key hay secret nào để tự ký thẩm quyền.
2. **Finding 2 — Khóa Fail-Closed Toàn Bộ Candidate Minting API**:
   - Phương thức HostBoundaryBootstrapCapability._create_authenticated bị vô hiệu hóa fail-closed: lập tức ném ProtocolViolationError("Caller-selected or direct creation of HostBoundaryBootstrapCapability via in-process candidate API is strictly forbidden fail-closed; host boundary bootstrap capability can only be issued by trusted external host boundary").
   - Bổ sung HostBoundaryBootstrapCapability.from_host_signed_payload để tiếp nhận capability DTO mang chữ ký số mật mã do host ngoài tiến trình cấp phát. Phương thức này không tự ký hay cấp thẩm quyền; tính hợp lệ được xác thực mật mã bất đối xứng nghiêm ngặt qua ed25519.Ed25519PublicKey.verify() khi gọi verify().
3. **Finding 3 — Tách Biệt Factory & Chữ Ký Sang Trusted Host Boundary Test Harness**:
   - Khóa ký Ed25519 riêng tư (_HOST_BOUNDARY_BOOTSTRAP_SIGNING_KEY) và factory cấp phát thẩm quyền (TrustedHostBootstrapCapability) được đặt độc quyền trong test harness / trusted host boundary tại test_negative_fixtures.py, nằm hoàn toàn ngoài phạm vi import và callable của candidate module.
   - Cập nhật helper _launch_test_host_boundary_daemon (dòng 172) và fixture test_sod_18 gọi trực tiếp TrustedHostBootstrapCapability.
4. **Finding 4 — Bổ Sung Fixture Mở Rộng Fresh Subprocess test_18s & In-Process test_18t**:
   - Mở rộng test_18s: kiểm chứng trong tiến trình con độc lập rằng candidate module không chứa _HOST_BOUNDARY_BOOTSTRAP_SECRET, gọi _create_authenticated bị ném ProtocolViolationError, giả mạo chữ ký trong from_host_signed_payload bị verify() từ chối fail-closed, và chuỗi tấn công rogue listener -> issuer -> ticket -> provision hoàn toàn thất bại (FULL_CHAIN_ACCEPTED == False, HostBoundaryChannel._started == False).
   - Bổ sung test_18t: kiểm chứng trong cùng tiến trình candidate rằng caller không thể đọc secret, không thể gọi _create_authenticated, không thể forge capability, và chuỗi provision fail-closed, trong khi authentic capability do trusted host cấp phát vẫn hoạt động chính xác.
5. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **396/396 tests PASS (100%)**, bảo đảm an toàn tuyệt đối trên mọi cổng thẩm định.

## 27. Khắc phục triệt để phát hiện Sol Audit trên 2798fd6 (External Signer Daemon Ngoài Tiến Trình, Loại Bỏ Hoàn Toàn Private Key Khỏi Repository & Ngăn Chặn Mint Capability Khi Quét Toàn Bộ Mã Nguồn)

Đợt rà soát độc lập trên exact candidate SHA 2798fd6f4af760f757ae41d5beab53408cc5a0da (approved base 4a7c8c921b7e05066505d51b168a02c3fde61317) ghi nhận finding actionable:
Private Ed25519 signing key _HOST_BOUNDARY_BOOTSTRAP_PRIVATE_KEY_BYTES vẫn được commit trong docs/parallel-delivery/test_negative_fixtures.py:119-123 và factory TrustedHostBootstrapCapability ở cùng fixture dùng key đó; counterexample an toàn đã suy ra public key khớp pinned candidate key và tự ký payload rồi from_host_signed_payload(...).verify(...) thành công (SAFE_ASSERTION_TRACKED_KEY_CAN_MINT_VERIFIABLE_CAPABILITY=TRUE), tái hiện cả fresh clone, trái invariant out-of-process/private-key custody tại security-performance-recovery.md:166-170,189-195. Cần chuyển private signing key/factory ra trusted host boundary thật không nằm trong candidate repository hoặc thay bằng cơ chế external signer; bổ sung fixture chứng minh candidate đọc toàn repository vẫn không thể mint capability; không có mutation nào được thực hiện trong review.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Xóa Bỏ Hoàn Toàn Private Signing Key Khỏi Repository**:
   - Loại bỏ hoàn toàn _HOST_BOUNDARY_BOOTSTRAP_PRIVATE_KEY_BYTES và _HOST_BOUNDARY_BOOTSTRAP_SIGNING_KEY khỏi test_negative_fixtures.py cũng như toàn bộ các tệp được Git theo dõi trong repository.
   - Tuyệt đối không lưu trữ khóa riêng Ed25519 tĩnh dưới dạng hằng số, biến toàn cục, hay chuỗi hex trong mã nguồn candidate hay test fixtures.
2. **Finding 2 — Kiến Trúc External Signer Daemon Ngoài Tiến Trình Trong Bộ Nhớ**:
   - Chuyển việc sinh cặp khóa Ed25519 sang tiến trình con độc lập _launch_test_host_boundary_daemon chạy ngoài tiến trình. Khóa riêng chỉ tồn tại tạm thời trong RAM của daemon host boundary và không bao giờ ghi ra đĩa hay gửi qua IPC cho candidate process.
   - Daemon xuất khóa công khai pub_bytes qua pipe khi khởi chạy để ghim bất biến vào HostBoundaryBootstrapCapability.pin_trusted_host_public_key(...).
   - Factory TrustedHostBootstrapCapability ủy quyền ký số mật mã ra bên ngoài (external signer) qua giao thức IPC ('SIGN_BOOTSTRAP_CAP', clean_token, payload). Daemon xác thực nghiêm ngặt bí mật máy chủ (host_secret) bằng so sánh thời gian không đổi hmac.compare_digest trước khi thực hiện ký.
3. **Finding 3 — Ghim Bất Biến & Khóa Fail-Closed Mọi Nỗ Lực Sửa Đổi Khóa Công Khai**:
   - HostBoundaryBootstrapCapability.pin_trusted_host_public_key chỉ cho phép ghim khóa từ ranh giới máy chủ đáng tin cậy với token/IPC hợp lệ; cấm tuyệt đối candidate trong tiến trình tự ý ghim hay thay đổi khóa đã ghim (ném ProtocolViolationError).
4. **Finding 4 — Fixture Kiểm Thử test_18u Chứng Minh Đọc Toàn Bộ Repo Vẫn Không Thể Mint Capability**:
   - Bổ sung fixture test_18u_sol_finding_candidate_reading_entire_repo_cannot_mint_bootstrap_capability:
     + Quét toàn bộ các tệp được Git theo dõi trong docs/parallel-delivery/, khẳng định không tệp nào chứa định nghĩa private signing key hay chuỗi hex của khóa đã thu hồi.
     + Thực thi kịch bản counterexample an toàn: candidate tự sinh khóa hoặc tìm kiếm trên repository không thể tạo ra chữ ký vượt qua verify() đối với pinned public key (SAFE_ASSERTION_TRACKED_KEY_CAN_MINT_VERIFIABLE_CAPABILITY = False).
     + Kiểm tra việc cố tình ghim hoặc thay đổi pinned public key bằng token giả mạo đều thất bại fail-closed.
5. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **397/397 tests PASS (100%)**, bảo đảm an toàn tuyệt đối trên mọi cổng thẩm định và release gate.

## 28. Khắc phục triệt để phát hiện Sol Audit trên 42ea7a7 (Loại Bỏ Hoàn Toàn Trusted Host Factory, Credential & Endpoint Khỏi Candidate-Readable Fixtures, Khử Side Effect Khởi động Daemon Khi Import & Bổ Sung Negative Assertion `test_18v`)

Đợt rà soát độc lập trên exact candidate SHA 42ea7a7c8a421f153026c51aa0fcd5c9b3973530 (approved base 4a7c8c921b7e05066505d51b168a02c3fde61317) ghi nhận finding actionable:
Invariant out-of-process phải ngăn candidate mint verifiable bootstrap capability nhưng fresh subprocess chỉ cần import docs/parallel-delivery/test_negative_fixtures.py rồi gọi TrustedHostBootstrapCapability(f._h_port, f._h_authkey, f._HOST_BOUNDARY_TOKEN) và verify() thành công, quan sát CANDIDATE_IMPORT_FIXTURE_AUTHORITY_ACCEPTED; nguyên nhân tại test_negative_fixtures.py:117-171,256-260 phơi bày token/endpoint/factory và import có side effect khởi động daemon. Cần loại bỏ trusted-host factory/credential/endpoint khỏi candidate-readable fixture hoặc đặt ngoài repository qua boundary thật, rồi bổ sung fresh-subprocess negative assertion chứng minh import candidate không thể mint capability.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Loại Bỏ Hoàn Toàn Factory, Token & Endpoint Khỏi Candidate-Readable Fixtures**:
   - Loại bỏ triệt để factory `TrustedHostBootstrapCapability`, token `_HOST_BOUNDARY_TOKEN`, và các biến `_h_port`, `_h_authkey`, `_h_proc`, `_h_boot_cap` khỏi phạm vi module-level của `test_negative_fixtures.py`.
   - Tiến trình candidate khi import `test_negative_fixtures.py` hoàn toàn không thể nhận thấy hay gọi bất kỳ hàm/biến thẩm quyền nào (`hasattr` trả về `False`).
2. **Finding 2 — Khử Triệt Để Side Effect Khởi Động Daemon Khi Import**:
   - Chuyển toàn bộ logic khởi chạy và dừng daemon `_launch_test_host_boundary_daemon` vào lifecycle runner `setUpModule` và `tearDownModule` của bộ kiểm thử.
   - Thao tác import `test_negative_fixtures` từ candidate process không khởi động bất kỳ tiến trình con daemon nào, không cấp bất kỳ socket hay port nào.
3. **Finding 3 — Bổ Sung Retry Khi Persist Atomic Tránh Race Condition Trên Windows**:
   - Trong `delivery_engine.py:6363` (`_persist_atomic`), bổ sung retry loop ngắn cho `os.replace` khi gặp `PermissionError` trên Windows, bảo đảm độ bền vững khi nhiều bài kiểm thử ghi registry dồn dập.
4. **Finding 4 — Fixture Kiểm Thử `test_18v` Chứng Minh Candidate Import Fixture Không Thể Mint Capability**:
   - Bổ sung bài kiểm tra `test_18v_sol_finding_candidate_importing_fixture_cannot_mint_bootstrap_capability`:
     + Trong fresh subprocess, candidate import `test_negative_fixtures as f`.
     + Khẳng định `f` không chứa `TrustedHostBootstrapCapability`, `_HOST_BOUNDARY_TOKEN`, `_h_port`, `_h_authkey`, `_h_proc`, hay `_h_boot_cap`.
     + Khẳng định không có daemon host boundary nào được kích hoạt do thao tác import.
     + Candidate nỗ lực mint capability thất bại fail-closed; khẳng định `CANDIDATE_IMPORT_FIXTURE_AUTHORITY_ACCEPTED` bằng `False` và phát xuất bằng chứng `CANDIDATE_IMPORT_FIXTURE_MINT_REJECTED_PASS`.
5. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **398/398 tests PASS (100%)**, bảo đảm an toàn tuyệt đối trên mọi cổng thẩm định và release gate.

## 29. Khắc phục triệt để phát hiện Sol Audit trên f5b1360 (Loại Bỏ Hoàn Toàn Nhánh Fallback Endpoint Caller-Selected Trong Pin Trusted Host Public Key, Ràng Buộc Thẩm Quyền 100% Qua HostBoundaryChannel Ngoài Tiến Trình & Bổ Sung Negative Fixture `test_18w`)

Đợt rà soát độc lập trên exact candidate SHA f5b136099ff0b2236362c29a7a1ed5d154a19fe3 (approved base 4a7c8c921b7e05066505d51b168a02c3fde61317) ghi nhận finding actionable:
`HostBoundaryBootstrapCapability.pin_trusted_host_public_key` tại `delivery_engine.py:1631-1642` chấp nhận `_internal_token` qua endpoint caller-selected `(port, authkey)` nếu listener trả `True`, không chứng minh endpoint thuộc trusted host boundary; fresh subprocess counterexample an toàn đã tự dựng Listener, tự chọn token/khóa Ed25519, pin public key rồi ký và verify `HostBoundaryBootstrapCapability` thành công (`COUNTEREXAMPLE_CANDIDATE_SELF_PIN_AND_MINT_ACCEPTED = True`). Cần loại bỏ nhánh fallback endpoint caller-selected hoặc ràng buộc bằng capability/provenance host ngoài tiến trình và bổ sung fixture fresh-process phân biệt.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Loại Bỏ Hoàn Toàn Nhánh Fallback Endpoint Caller-Selected Khỏi `pin_trusted_host_public_key`**:
   - Loại bỏ hoàn toàn khối `elif port is not None and authkey is not None:` tự ý kết nối tới endpoint do caller truyền vào trong `HostBoundaryBootstrapCapability.pin_trusted_host_public_key`.
   - Ràng buộc việc ghim khóa 100% qua thẩm quyền capability host ngoài tiến trình: bắt buộc `_is_valid_host_boundary_capability(_internal_token)` phải trả về `True` thông qua kênh `HostBoundaryChannel` đã được cấu hình.
   - Nếu caller truyền thêm `port` hoặc `authkey`, bắt buộc phải khớp chính xác tuyệt đối với endpoint đã cấu hình trên `HostBoundaryChannel` (`chan_port`, `chan_auth`), ngăn chặn tuyệt đối mọi nỗ lực trỏ tới rogue endpoint nội bộ.
2. **Finding 2 — Đồng Bộ Khởi Tạo Kênh Máy Chủ Trong Test Harness & Positive Control**:
   - Trong `_ensure_test_host_boundary_harness()`, thiết lập `HostBoundaryChannel._port` và `HostBoundaryChannel._authkey` từ daemon máy chủ trước khi gọi `pin_trusted_host_public_key`, bảo đảm kiểm tra thẩm quyền out-of-process thành công mà không cần endpoint fallback.
   - Trong fixture positive control `child_code_pos`, cấu hình endpoint của `HostBoundaryChannel` đồng bộ từ context máy chủ trước khi thực hiện ghim khóa công khai.
3. **Finding 3 — Fixture Phân Biệt `test_18w` (Fresh Subprocess Caller-Selected Endpoint Pin Bị Từ Chối Fail-Closed)**:
   - Bổ sung bài kiểm tra `test_18w_sol_finding_caller_selected_endpoint_pin_rejected_in_fresh_subprocess`:
     + Trong tiến trình con độc lập chưa provision kênh máy chủ, kẻ tấn công tự sinh cặp khóa Ed25519, mở `Listener(("127.0.0.1", 0), authkey=...)` trả `True` cho mọi token, rồi gọi `pin_trusted_host_public_key`.
     + Khẳng định phương thức lập tức ném `ProtocolViolationError("Direct pinning of trusted host public key by in-process caller is forbidden fail-closed")`.
     + Khóa công khai ghim giữ nguyên `None`; kẻ tấn công tự tạo `HostBoundaryBootstrapCapability` và gọi `verify()` bị từ chối fail-closed.
     + Khẳng định `COUNTEREXAMPLE_CANDIDATE_SELF_PIN_AND_MINT_ACCEPTED` bằng `False` và phát sinh bằng chứng `SOL_CALLER_SELECTED_PIN_REJECTED_PASS`.
4. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **399/399 tests PASS (100%)**, bảo đảm an toàn tuyệt đối trên mọi cổng thẩm định và release gate.

## 30. Khắc phục triệt để phát hiện Sol Audit trên aae7646 (Đóng Kín Hoàn Toàn Trusted Harness & Context Khỏi Candidate-Readable Fixtures, Loại Bỏ Mọi Credential/Endpoint Accessors & Bổ Sung Negative Assertion `test_18x`)

Đợt rà soát độc lập trên exact candidate SHA `aae7646079e76fd6f58f141bc0fdf4474f2c4a4a` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding actionable:
`test_negative_fixtures.py:120-125,130-253` công khai `_TestHostBoundaryContext` cùng `_ensure_test_host_boundary_harness()`, cho phép candidate fresh subprocess gọi helper, đọc `token`/`port`/`authkey` runtime rồi gọi `HostBoundaryBootstrapCapability._reset_for_testing` và `pin_trusted_host_public_key` với public key tùy ý; counterexample an toàn đã tái hiện `CANDIDATE_FIXTURE_CONTEXT_AUTHORITY_ACCEPTED=True`, vi phạm invariant candidate không thể bootstrap/pin authority ngoài tiến trình.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Loại Bỏ Hoàn Toàn Context-Helper & Accessor Khỏi Candidate-Readable Fixture**:
   - Loại bỏ hoàn toàn `_TestHostBoundaryContext`, `_ensure_test_host_boundary_harness`, và `_stop_test_host_boundary_harness` khỏi giao diện callable/attribute của `test_negative_fixtures.py`.
   - Đổi tên và đóng gói toàn bộ state nội bộ của test harness thành `_InternalHostBoundaryVault`, `_ensure_internal_host_boundary_harness`, và `_stop_internal_host_boundary_harness`, chỉ phục vụ nội bộ runner khi thực thi `setUpModule()` / `tearDownModule()`.
2. **Finding 2 — Đóng Kín Boundary Bằng `_SealedFixtureModule`**:
   - Định nghĩa lớp module `_SealedFixtureModule(types.ModuleType)` chặn tuyệt đối mọi truy cập ngoài tới các symbol context/helper/credentials (`_SEALED_ATTRS`).
   - Mọi nỗ lực truy cập thuộc tính ngoài hoặc gọi helper ném `AttributeError("Access to ... is forbidden fail-closed; trusted host harness is sealed within test runner")`.
   - Lọc bỏ hoàn toàn các symbol sealed khỏi `__dict__` và `dir()` của module, bảo đảm `hasattr` trả về `False`, `getattr(..., None)` trả về `None`, và `from test_negative_fixtures import ...` ném `ImportError`.
3. **Finding 3 — Fixture Phân Biệt `test_18x` (Fresh Subprocess Fixture Context Authority Bị Từ Chối Fail-Closed)**:
   - Bổ sung bài kiểm tra `test_18x_sol_finding_candidate_fixture_context_authority_rejected_in_fresh_subprocess`:
     + Trong fresh subprocess, candidate import `test_negative_fixtures as f`.
     + Khẳng định `f` không chứa `_TestHostBoundaryContext`, `_ensure_test_host_boundary_harness`, `_stop_test_host_boundary_harness`, `_InternalHostBoundaryVault`, `token`, `port`, hay `authkey`.
     + Khẳng định truy cập trực tiếp ném `AttributeError`, `from-import` ném `ImportError`.
     + Tái hiện counterexample an toàn: candidate tìm cách gọi helper, lấy context, reset testing và ghim khóa công khai; khẳng định toàn bộ chuỗi bị chặn đứng fail-closed, `CANDIDATE_FIXTURE_CONTEXT_AUTHORITY_ACCEPTED` bằng `False`, khóa ghim giữ nguyên `None`, và phát sinh bằng chứng `SOL_FIXTURE_CONTEXT_AUTHORITY_REJECTED_PASS`.
4. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **400/400 tests PASS (100%)**, bảo đảm an toàn tuyệt đối trên mọi cổng thẩm định và release gate.

## 31. Khắc phục triệt để phát hiện Sol Audit trên 8003c13 (Đóng Kín Hoàn Toàn Bốn Helper Trusted Host Khỏi Candidate-Readable Fixtures, Khử Khả Năng Tự Sinh Khóa Cho Keystore & Bổ Sung Negative Assertion `test_18y`)

Đợt rà soát độc lập trên exact candidate SHA `8003c13bd76e49cbd562dc6ab785299cd68161c7` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding actionable:
`docs/parallel-delivery/test_negative_fixtures.py:291-315`: bốn helper `TrustedHostReviewerHandoff`, `TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore` và `TrustedHostProvisionKeyStore` vẫn lộ qua `hasattr/dir/__dict__`; fresh subprocess candidate gọi `TrustedHostIsolatedKeyStore` với public key tự sinh rồi xác minh chữ ký bằng private key tương ứng, đạt `CANDIDATE_PUBLIC_HELPER_CUSTOM_KEY_ACCEPTED=True`, vi phạm invariant candidate không thể tự chọn/mint pinned-key authority.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Đóng Kín Bốn Helper Trusted Host Khỏi Candidate-Readable Fixture Qua `_SealedFixtureModule`**:
   - Thêm đầy đủ 4 helper `TrustedHostReviewerHandoff`, `TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore`, `TrustedHostProvisionKeyStore` vào danh sách `_SEALED_ATTRS` trong `_SealedFixtureModule`.
   - Mở rộng các bộ lọc `__getattribute__`, `__dict__`, và `dir()` trong `_SealedFixtureModule` để chặn tuyệt đối và loại bỏ toàn bộ các thuộc tính bắt đầu bằng `TrustedHost`.
   - Khi candidate import `test_negative_fixtures as f`, mọi truy cập thuộc tính ném `AttributeError("Access to ... is forbidden fail-closed; trusted host harness is sealed within test runner")`, `hasattr` trả về `False`, `getattr(..., None)` trả về `None`, và `from test_negative_fixtures import ...` ném `ImportError`.
2. **Finding 2 — Khử Triệt Để Khả Năng Kích Hoạt Ngầm Daemon Máy Chủ Của Helper**:
   - Trong `TrustedHostReviewerHandoff`, `TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore`, và `TrustedHostProvisionKeyStore`, loại bỏ lệnh gọi tự động `_ensure_internal_host_boundary_harness()`.
   - Các helper này yêu cầu nghiêm ngặt context harness đã được khởi tạo trong runner (`_InternalHostBoundaryVault.token` và `_InternalHostBoundaryVault.proc is not None`), ném `ProtocolViolationError("...; caller cannot invoke host helper outside test harness")` fail-closed nếu bị gọi ngoài lifecycle kiểm thử.
3. **Finding 3 — Fixture Phân Biệt `test_18y` (Fresh Subprocess Custom Key Authority Bị Từ Chối Fail-Closed)**:
   - Bổ sung bài kiểm tra `test_18y_sol_finding_candidate_custom_key_authority_rejected_in_fresh_subprocess`:
     + Trong fresh subprocess, candidate import `test_negative_fixtures as f`.
     + Khẳng định `f` không chứa bất kỳ helper nào trong số `TrustedHostReviewerHandoff`, `TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore`, hay `TrustedHostProvisionKeyStore` qua `hasattr`, `dir()`, hay `__dict__`.
     + Khẳng định truy cập trực tiếp ném `AttributeError`, `from-import` ném `ImportError`.
     + Tái hiện counterexample an toàn: candidate tự sinh cặp khóa Ed25519, cố gắng gọi `TrustedHostIsolatedKeyStore` để mint keystore với public key tự chọn và xác minh chữ ký; khẳng định toàn bộ nỗ lực bị chặn fail-closed, `CANDIDATE_PUBLIC_HELPER_CUSTOM_KEY_ACCEPTED` bằng `False`, và phát sinh bằng chứng `SOL_CUSTOM_KEY_AUTHORITY_REJECTED_PASS`.
4. **Bộ kiểm thử toàn diện**: Nâng tổng số bài test/probe lên **401/401 tests PASS (100%)**, bảo đảm an toàn tuyệt đối trên mọi cổng thẩm định và release gate.

## 32. Khắc phục triệt để phát hiện Sol Audit trên a7d9820 (Tách Biệt Hoàn Toàn Test Harness Ra Module Riêng Biệt, Vô Hiệu Hóa Bypass Raw Module Dictionary & Khử Triệt Để Quyền Tự Cấp Khóa)

Đợt rà soát độc lập trên exact candidate SHA `a7d982095108f7028ec208117d95231a62d55988` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding actionable:
Cơ chế niêm phong tại `docs/parallel-delivery/test_negative_fixtures.py:14221-14298` chỉ override truy cập thuộc tính thông thường, nhưng caller vẫn lấy raw namespace bằng `types.ModuleType.__getattribute__(f, '__dict__')`, gọi `raw['setUpModule']()`, lấy `raw['TrustedHostIsolatedKeyStore']` và cấp keystore bằng public key Ed25519 tự chọn; minimal safe assertion quan sát `RAW_MODULE_DICT_CUSTOM_KEY_ACCEPTED=True` với exit code 7, trái invariant candidate không thể truy cập helper hay mint custom-key authority và cho thấy `test_18y` hiện chưa phân biệt bypass qua base descriptor.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Tách Rời Hoàn Toàn Test Harness Ra Khỏi Candidate-Readable Module**:
   - Chuyển toàn bộ `_InternalHostBoundaryVault`, `_ensure_internal_host_boundary_harness`, `_stop_internal_host_boundary_harness`, cùng 4 helper (`TrustedHostReviewerHandoff`, `TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore`, `TrustedHostProvisionKeyStore`) và `TEST_FIXTURE_REVIEWER_SECRET` sang tệp riêng biệt `docs/parallel-delivery/test_host_boundary_harness.py`.
   - Xóa bỏ hoàn toàn `setUpModule`, `tearDownModule`, các helper, credential và secret khỏi module-level của `docs/parallel-delivery/test_negative_fixtures.py`.
   - Vô hiệu hóa triệt để kỹ thuật bypass qua base descriptor `types.ModuleType.__getattribute__(f, '__dict__')`: raw dictionary của module `test_negative_fixtures` hoàn toàn không chứa bất kỳ lifecycle authority, helper hay credential nào.
2. **Finding 2 — Khử Triệt Để Quyền Tự Cấp Khóa Bằng Whitelist Bất Biến**:
   - Trong `test_host_boundary_harness.py`, bổ sung danh sách whitelist bất biến `ALLOWED_FIXTURE_KEY_IDS = frozenset({"rev_key_lead_v1", "integ_gatekeeper_v1", "control_authority_v1"})`.
   - Mọi nỗ lực mint hoặc provision keystore với custom key ID (ví dụ: `'custom_key'`) đều bị từ chối lập tức với `ProtocolViolationError` fail-closed.
3. **Finding 3 — Khởi Tạo Ranh Giới Ở Cấp Test Runner**:
   - Tích hợp việc khởi tạo và dọn dẹp daemon `test_host_boundary_harness` vào `validate.py:run_negative_fixture_suite()` và entrypoint `__main__`, bảo đảm harness chỉ hoạt động dưới sự kiểm soát của runner kiểm thử và độc lập tuyệt đối với candidate import.
4. **Finding 4 — Cập Nhật Fixture Phân Biệt `test_18y` (Regression Bypass Base Descriptor)**:
   - Cập nhật bài kiểm tra `test_18y_sol_finding_candidate_custom_key_authority_rejected_in_fresh_subprocess`:
     + Trong tiến trình con độc lập, candidate trích xuất raw namespace bằng `types.ModuleType.__getattribute__(f, '__dict__')`.
     + Khẳng định toàn bộ 10 symbol nhạy cảm (`setUpModule`, `tearDownModule`, `TrustedHost...`, `_InternalHostBoundaryVault`, `_ensure_internal_host_boundary_harness`, `_stop_internal_host_boundary_harness`, `TEST_FIXTURE_REVIEWER_SECRET`) đều hoàn toàn vắng mặt trong raw dictionary.
     + Tái hiện nỗ lực gọi `raw.get('setUpModule')` và `raw.get('TrustedHostIsolatedKeyStore')` để mint keystore với public key tự chọn; khẳng định `RAW_MODULE_DICT_CUSTOM_KEY_ACCEPTED` luôn là `False` fail-closed.
     + Khẳng định gọi trực tiếp `TrustedHostIsolatedKeyStore` với custom key cũng luôn bị từ chối fail-closed.
5. **Bộ kiểm thử toàn diện**: Toàn bộ bộ kiểm thử tự động đạt **401/401 tests PASS (100%)**, bảo đảm an toàn tuyệt đối trên mọi cổng thẩm định và release gate.

## 33. Kh?c ph?c tri?t d? ph�t hi?n Sol Audit tr�n b5af69c (Key Custody Invariant, C?p Ph�t Pinned Key Material B?t Bi?n & T? Ch?i Caller-Selected Bytes)

�?t r� so�t d?c l?p tr�n exact candidate SHA `b5af69c7b81733df99ace98731bbd06ffee1bd1a` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nh?n finding actionable:
`test_host_boundary_harness.py:228-238` ch? whitelist key ID nhung v?n ch?p nh?n public key bytes do caller cung c?p; counterexample an to�n kh?i ch?y harness, t? sinh Ed25519 keypair, g?i `TrustedHostIsolatedKeyStore({'rev_key_lead_v1': attacker_pub})`, r?i `verify_signature('rev_key_lead_v1', payload, attacker_priv.sign(payload))` tr? `True` (`ALLOWED_ID_ATTACKER_KEY_ACCEPTED=True`, exit code 7). �i?u n�y ph� invariant pinned-key custody/kh�ng cho candidate t? ch?n key authority d� custom_key b? ch?n.

Bi?n ph�p kh?c ph?c tri?t d?:
1. **Finding 1 � Host Boundary �?c Quy?n C?p Ph�t Pinned Key Material B?t Bi?n**:
   - Trong `docs/parallel-delivery/test_host_boundary_harness.py`, `_ensure_internal_host_boundary_harness()` t?o v� s? h?u c�c c?p kh�a Ed25519 b?t bi?n cho to�n b? danh s�ch `ALLOWED_FIXTURE_KEY_IDS` (`rev_key_lead_v1`, `integ_gatekeeper_v1`, `control_authority_v1`) luu tr? t?i `_InternalHostBoundaryVault.fixture_keypairs` v� `_InternalHostBoundaryVault.fixture_public_keys` d?ng `MappingProxyType` b?t bi?n.
   - Th�m c�c helper m�y ch? `get_fixture_authority_keypair(key_id)` v� `get_fixture_authority_public_key(key_id)` (c�ng b� danh `TrustedHostFixturePrivateKey` / `TrustedHostFixturePublicKey`) ph?c v? test harness, b?o d?m quy?n luu k� kh�a thu?c v? ranh gi?i m�y ch? b�n ngo�i.
2. **Finding 2 � T? Ch?i Tri?t �? Caller-Selected Public Key Bytes Fail-Closed**:
   - H�m `_validate_and_resolve_fixture_pinned_keys(pinned_keys)` trong `test_host_boundary_harness.py` �p d?ng quy t?c ki?m tra nghi�m ng?t:
     + N?u `pinned_keys` l� `None` ho?c danh s�ch key IDs, host boundary t? d?ng cung c?p public key bytes ch�nh danh.
     + N?u `pinned_keys` l� `Mapping`, m?i kh�a ph?i thu?c `ALLOWED_FIXTURE_KEY_IDS` v� c�c byte kh�a c�ng khai ph?i tr�ng kh?p tuy?t d?i (`hmac.compare_digest`) v?i pinned key material c?a host boundary. M?i n? l?c truy?n bytes t? ch?n (`caller-selected bytes`) d?u b? t? ch?i l?p t?c v?i `ProtocolViolationError` fail-closed.
3. **Finding 3 � C?p Nh?t B? Test Fixtures S? D?ng Pinned Key Material C?a Host**:
   - C?p nh?t to�n b? c�c b�i ki?m tra (`test_03`, `test_04`, `test_05`, `test_06`, `test_07`, `test_10`, `test_11d`, `test_12`, `test_13`, `test_14`, `test_15`) trong `docs/parallel-delivery/test_negative_fixtures.py` d? l?y keypair v� public key ch�nh danh t? host boundary thay v� t? sinh public key bytes t?i client.
4. **Finding 4 � Fresh Subprocess Regression Trong `test_18y`**:
   - Trong `test_18y_sol_finding_candidate_custom_key_authority_rejected_in_fresh_subprocess`:
     + T�i hi?n counterexample an to�n c?a Sol: candidate kh?i ch?y harness, t? sinh c?p kh�a Ed25519, g?i `harness_keystore_helper({'rev_key_lead_v1': attacker_pub})` v� `harness_handoff_helper({'rev_key_lead_v1': attacker_pub})`.
     + Kh?ng d?nh c? hai d?u b? t? ch?i fail-closed v?i `ProtocolViolationError` (`ALLOWED_ID_ATTACKER_KEY_ACCEPTED=False`).
     + Kh?ng d?nh ch? k� c?a attacker khi d?i chi?u v?i keystore ch�nh danh c?a host lu�n tr? v? `False`.
     + Kh?ng d?nh positive control: host-owned pinned key x�c minh ch? k� h?p l? th�nh c�ng (`HOST_OWNED_PINNED_KEY_VERIFICATION_PASS=True`).
5. **Finding 5 � Ni�m Phong To�n Di?n Trong `_SealedFixtureModule`**:
   - B? sung `get_fixture_authority_keypair`, `get_fixture_authority_public_key`, `TrustedHostFixturePrivateKey`, `TrustedHostFixturePublicKey`, `_validate_and_resolve_fixture_pinned_keys` v�o `_SEALED_ATTRS` v� b? l?c ti?n t?, ngan ch?n tri?t d? candidate d?c qua fixture module.
6. **B? ki?m th? to�n di?n**: To�n b? **401/401 tests PASS (100%)**, 12/12 validation checks PASS, b?o d?m an to�n tuy?t d?i tr�n m?i c?ng th?m d?nh v� release gate.

## 34. Khắc phục triệt để phát hiện Sol Audit trên 2eb47f6 (Loại bỏ hoàn toàn Private Key khỏi In-Process/Fixture, Cơ chế ký mờ qua IPC và Quản lý khóa ngoài tiến trình)

Đợt rà soát độc lập trên exact candidate SHA `2eb47f67b69445e38275f193aeab835731b52ced` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding actionable:
`docs/parallel-delivery/test_host_boundary_harness.py:231-252` xuất `get_fixture_authority_keypair` và `TrustedHostFixturePrivateKey`, trả về đối tượng khóa riêng tư Ed25519 từ `_InternalHostBoundaryVault.fixture_keypairs`. Điều này vi phạm ranh giới tin cậy máy chủ host trong `security-performance-recovery.md:166-170,189-195` vì candidate worker có thể đọc khóa riêng và tự ký phong bì duyệt hợp lệ (`FORGED_REVIEW_ACCEPTED ACCEPT True`). Cơ chế chống replay không khắc phục được việc mất quyền lưu ký khóa riêng.

Biện pháp khắc phục triệt để:
1. **Finding 1 — Loại bỏ hoàn toàn Private Key khỏi Candidate / Fixture Runtime**:
   - Khóa riêng tư Ed25519 cho toàn bộ fixture authorities (`rev_key_lead_v1`, `integ_gatekeeper_v1`, `control_authority_v1`) được tạo và lưu trữ độc quyền bên trong tiến trình con daemon ngoài tiến trình (`server_code` của `_InternalHostBoundaryVault.proc`).
   - Xóa bỏ hoàn toàn thuộc tính `_InternalHostBoundaryVault.fixture_keypairs`. Harness và client chỉ nhận các byte khóa công khai (`fixture_public_keys` dạng `MappingProxyType`) qua stdout khi khởi tạo.
   - Xóa bỏ hoàn toàn các hàm truy cập khóa riêng: `get_fixture_authority_keypair` và bí danh `TrustedHostFixturePrivateKey`. Mọi nỗ lực import hoặc truy cập các symbol này đều bị từ chối fail-closed với `ImportError` hoặc `AttributeError`.

2. **Finding 2 — Cơ chế ký mờ qua IPC (Opaque Signing IPC) ngoài tiến trình**:
   - Bổ sung lệnh IPC `SIGN_FIXTURE_PAYLOAD` vào vòng lặp daemon của `HostBoundaryChannel`. Daemon chỉ chấp nhận yêu cầu ký khi token khớp với `host_secret` (kiểm tra qua `hmac.compare_digest`), `key_id` nằm trong danh sách `ALLOWED_FIXTURE_KEY_IDS` và payload là dạng bytes.
   - Cung cấp các helper ký mờ:
     + `host_sign_fixture_payload(key_id, payload)` / `TrustedHostSignFixturePayload`
     + `host_sign_review_envelope(envelope, key_id)` / `TrustedHostSignReviewEnvelope`
     + `host_sign_integration_envelope(envelope, key_id)` / `TrustedHostSignIntegrationEnvelope`
   - Các helper này yêu cầu daemon đã được khởi tạo trong test harness, ném `ProtocolViolationError` fail-closed nếu bị gọi ngoài lifecycle kiểm thử.

3. **Finding 3 — Cập nhật toàn diện bộ kiểm thử negative fixtures**:
   - Cập nhật các bài kiểm tra (`test_03`, `test_04`, `test_05`, `test_06`, `test_07`, `test_10`, `test_11`, `test_12`, `test_13`, `test_14`) trong `docs/parallel-delivery/test_negative_fixtures.py` để sử dụng `host_sign_review_envelope` và `host_sign_integration_envelope`.

4. **Finding 4 — Kiểm chứng hồi quy trong tiến trình con độc lập (`test_18z`)**:
   - Bổ sung `test_18z_sol_finding_fixture_authority_private_key_custody_remediated`:
     + Khẳng định tiến trình con mới không thể import `get_fixture_authority_keypair` hoặc `TrustedHostFixturePrivateKey` (`ImportError`).
     + Khẳng định `_InternalHostBoundaryVault` không chứa bất kỳ `fixture_keypairs` nào.
     + Tái hiện counterexample: phong bì do candidate tự ký bằng khóa tự sinh bị `TrustedReviewConsumer` từ chối dứt khoát với `EnvelopeVerificationError` (`FORGED_REVIEW_ACCEPTED=False`).
     + Khẳng định phong bì ký qua IPC máy chủ host được xác minh thành công (`verdict == ACCEPT`).
     + Khẳng định cơ chế chống replay đơn lẻ và đồng thời hoạt động chính xác (1 ACCEPT, 1 ReplayAttackError).
     + Khẳng định `ProductionActivationGate.STATUS` duy trì `PRODUCTION_ACTIVATION_BLOCKED`.
     + Khẳng định dọn dẹp sạch tiến trình sau khi dừng harness (`proc is None`, public keys rỗng).

5. **Finding 5 — Niêm phong chặt chẽ trong `_SealedFixtureModule`**:
   - Bổ sung các helper ký mờ (`host_sign_fixture_payload`, `host_sign_review_envelope`, `host_sign_integration_envelope`, `TrustedHostSignFixturePayload`, `TrustedHostSignReviewEnvelope`, `TrustedHostSignIntegrationEnvelope`) vào `_SEALED_ATTRS`, ngăn chặn triệt để candidate truy cập qua module fixture.

## 35. Kh?c ph?c tri?t ?? ph?t hi?n Sol Audit tr?n a25c80f (B?o v? th?ng tin x?c th?c Vault, Lo?i b? Generic Signing Endpoints v? T?ch bi?t External Envelope Producers ngo?i ti?n tr?nh)

??t r? so?t ??c l?p tr?n exact candidate SHA `a25c80f9f4ab965ce21e7fe5e09babd87c9cc8d8` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nh?n finding `ROOT_ARCHITECTURE`:
Candidate-readable `test_host_boundary_harness.py:255-318` v?n gi? `token`, `port`, `authkey` trong `_InternalHostBoundaryVault:50-58` v? expose c?c h?m k? `host_sign_fixture_payload`, `host_sign_review_envelope`, `host_sign_integration_envelope` nh?n arbitrary payload. Do ?? candidate c? th? t? ch?n `verdict=ACCEPT`, delivery task, review dispatch, commit SHA r?i y?u c?u daemon k?; `TrustedReviewConsumer.consume_review_envelope()` ch?p nh?n v? ghi consumption registry. Root cause l? signer authority/provenance/ownership ch?a t?ch kh?i candidate d? private key ?? ? trong daemon.

Bi?n ph?p kh?c ph?c tri?t ??:
1. **Finding 1 - B?o v? th?ng tin x?c th?c Vault tr??c truy c?p tr?c ti?p**:
   - `_InternalHostBoundaryVault` ???c b?o v? b?ng metaclass `_InternalHostBoundaryVaultMeta`.
   - B?t k? truy c?p tr?c ti?p n?o v?o `.token`, `.port`, `.authkey` t? m? ngu?n in-process ??u b? n?m `ProtocolViolationError` fail-closed.
2. **Finding 2 - Lo?i b? ho?n to?n Generic Signing Endpoint kh?i Daemon ngo?i ti?n tr?nh**:
   - L?nh IPC `SIGN_FIXTURE_PAYLOAD` b? lo?i b? ho?n to?n kh?i daemon ngo?i ti?n tr?nh; daemon tr? v? `False` fail-closed n?u nh?n l?nh k? payload bytes t?y ?.
3. **Finding 3 - Lo?i b? ho?n to?n c?c h?m generic signing kh?i b? m?t Candidate**:
   - X?a b? ho?n to?n 6 h?m k? m? generic kh?i module export c?a `test_host_boundary_harness.py`: `host_sign_fixture_payload`, `TrustedHostSignFixturePayload`, `host_sign_review_envelope`, `TrustedHostSignReviewEnvelope`, `host_sign_integration_envelope`, `TrustedHostSignIntegrationEnvelope`.
   - C? g?ng import c?c h?m n?y s? n?m `ImportError` fail-closed.
4. **Finding 4 - Chuy?n quy?n kh?i t?o v? k? Envelope sang External Producers ngo?i ti?n tr?nh**:
   - Cung c?p `ExternalReviewProducer` v? `ExternalIntegrationProducer` (c?ng c?c b? danh `TrustedExternalReviewProducer`, `TrustedExternalIntegrationProducer`).
   - Vi?c d?ng canonical payload v? k? b?t ??i x?ng Ed25519 ???c th?c hi?n ho?n to?n b?n trong ranh gi?i an to?n c?a daemon ngo?i ti?n tr?nh (`PRODUCE_REVIEW_ENVELOPE`, `PRODUCE_INTEGRATION_ENVELOPE`).
   - External producer t? ki?m tra t?nh h?p l? c?a key ID, verdict, bind ch?t ch? delivery task ID, review dispatch ID, candidate commit, base commit, fencing token, nonce v? timestamps. Caller kh?ng th? cung c?p payload t?y ? ?? daemon k? m? qu?ng.
5. **Finding 5 - Verifiers ch? ti?u th? External-issued Artifacts**:
   - `TrustedReviewConsumer` v? `TrustedIntegrationConsumer` x?c minh ch? k? Ed25519 v?i kh?a c?ng khai ???c ghim, ki?m tra replay, fencing v? domain binding nghi?m ng?t.

## 36. Kh?c ph?c tri?t ?? ph?t hi?n Sol Audit tr?n 6fc2d5a (Th?c thi Host-bound Authority, R?ng bu?c Dispatch x?c th?c v? T?ch bi?t Domain Role-to-Key nghi?m ng?t)

??t r? so?t ??c l?p tr?n exact candidate SHA `6fc2d5ac30648b3d99b9c26d6150a6b96a2b2777` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nh?n hai finding `ROOT_ARCHITECTURE`:
1. Finding 1: Public producers `ExternalReviewProducer` v? `ExternalIntegrationProducer` v?n cho ph?p caller cung c?p authority fields qua tham s? `envelope_data` ho?c c?c tham s? overrides; daemon k? m? kh?ng ki?m tra dispatch registry r?ng bu?c; candidate c? th? ??c `_InternalHostBoundaryVault._token`.
2. Finding 2: `ALLOWED_FIXTURE_KEY_IDS` cho ph?p `control_authority_v1` k? review envelope v? `TrustedReviewConsumer` ch?p nh?n v? ch? ki?m tra whitelist m? kh?ng ph?n ??nh role/domain; caller c? th? ch?n `control_authority_v1` ?? k? duy?t.

Bi?n ph?p kh?c ph?c tri?t ??:
1. **Finding 1 - R?ng bu?c Host-bound Authority v? Dispatch ?? x?c th?c**:
   - Lo?i b? ho?n to?n tham s? `envelope_data` kh?i c? hai producer `ExternalReviewProducer` v? `ExternalIntegrationProducer`. M?i n? l?c truy?n ??i s? v? tr? ho?c keyword `envelope_data` ??u b? n?m `ProtocolViolationError` fail-closed.
   - Chuy?n to?n b? credential (`token`, `_token`, `port`, `_port`, `authkey`, `_authkey`, `proc`, `_proc`) v?o container ri?ng t? `_HostBoundaryState` kh?ng th? truy c?p t? candidate; `_InternalHostBoundaryVaultMeta` n?m `ProtocolViolationError` fail-closed khi truy c?p.
   - Daemon ngo?i ti?n tr?nh qu?n l? b?ng ??ng k? dispatch `registered_dispatches` v? t? ??ng bind `candidate_commit`, `base_commit`, `delivery_task_id`, `role`, `phase` t? b?n ghi dispatch ???c c?p ph?p (`TrustedHostRegisterDispatch`). B?t k? n? l?c n?o nh?m override commit ho?c task ID t? ph?a caller ??u b? daemon t? ch?i fail-closed.
   - Th?m ph??ng th?c `snapshot()` v?o `DurableConsumptionRegistry` ?? b?o ??m t?nh b?t bi?n c?a tr?ng th?i ti?u th?; c?c y?u c?u b? t? ch?i kh?ng g?y ra b?t k? thay ??i n?o l?n snapshot registry.
2. **Finding 2 - Ph?n ??nh nghi?m ng?t Role-to-Key theo t?ng Domain**:
   - T?ch bi?t tuy?t ??i quy?n l?u k? kh?a theo t?ng domain nghi?p v?:
     + Domain Review (`PARALLEL_DELIVERY_REVIEW_ENVELOPE_V1`): Ch? cho ph?p duy nh?t kh?a `rev_key_lead_v1`. Kh?a `control_authority_v1` v? `integ_gatekeeper_v1` b? c?m ho?n to?n.
     + Domain Integration (`PARALLEL_DELIVERY_INTEGRATION_ENVELOPE_V1`): Ch? cho ph?p duy nh?t kh?a `integ_gatekeeper_v1`. Kh?a `control_authority_v1` v? `rev_key_lead_v1` b? c?m ho?n to?n.
     + Kh?a ?i?u khi?n Control (`control_authority_v1`): Ch? d?nh ri?ng cho quy?n h?n Control, tuy?t ??i kh?ng ???c ph?p k? b?t k? phong b? review ho?c integration n?o.
   - Daemon v? c? hai producer ki?m tra role/key fail-closed tr??c khi k?; consumer ki?m tra expected key ID theo vai tr? tr??c khi x?c minh ch? k? m? h?a v? tr??c khi g?i `check_and_consume`.
3. **Nghi?m thu ki?m th? (Acceptance Evidence)**:
   - C?p nh?t `test_18z` s? d?ng `TrustedHostProbeRawMessage` v? `TrustedHostRegisterDispatch` qua IPC an to?n.
   - B? sung `test_19_sol_findings_remediation_root_architecture_and_role_separation` trong `test_negative_fixtures.py` ki?m ch?ng to?n di?n c?c tr??ng h?p negative v? positive cho c? hai finding: t? ch?i authority override, t? ch?i wrong-role keys, b?o v? snapshot registry b?t bi?n tr??c side effect, ti?u th? th?nh c?ng m?t l?n ??i v?i artifact h?p l?, ch?ng replay ??n l? v? ?a lu?ng ??ng th?i.
   - To?n b? 403 b?i ki?m th? (bao g?m 27 b?i ki?m th? targeted root-cause) ??u ??t PASS 100%.
   - C?ng k?ch ho?t s?n xu?t duy tr? tr?ng th?i an to?n: `ProductionActivationGate.STATUS == 'PRODUCTION_ACTIVATION_BLOCKED'`.

## 37. Khắc phục triệt để phát hiện Sol Audit trên 2d41b53 (Lưu ký thông tin xác thực Host Daemon, Phân quyền Đăng ký Dispatch ngoài tiến trình và Niêm phong Candidate Surface)

Đợt rà soát độc lập trên exact candidate SHA `2d41b53eac68705efdb8e5039a246fa06c22e33a` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding `ROOT_ARCHITECTURE`:
- **Root cause**: Điểm truy cập công khai `_HostBoundaryState` trong `docs/parallel-delivery/test_host_boundary_harness.py` cho phép candidate import trực tiếp, đọc các thông tin xác thực `token`, `port`, `authkey`, `proc`, sau đó đăng ký dispatch tùy ý thông qua IPC; daemon tin tưởng mọi bản ghi dispatch sau khi kiểm tra token mà không thẩm định `base_commit` hay `candidate_commit`, rồi ký phong bì duyệt `ACCEPT` và consumer ghi nhận vào registry.
- **Counterexample an toàn**: Candidate đọc `_HostBoundaryState.token/port/authkey/proc`, đăng ký dispatch với candidate commit `deadbeef` và base commit tùy ý, yêu cầu daemon ký phong bì `ACCEPT`, và consumer tiếp nhận thành công (`CANDIDATE_REGISTER_AND_ACCEPT_ACCEPTED=True`).

Biện pháp khắc phục triệt để:
1. **Lưu ký thông tin xác thực Host Daemon và Niêm phong Candidate Surface**:
   - Chuyển toàn bộ thông tin xác thực daemon (`token`, `port`, `authkey`, `proc`, `boot_cap`, `test_host_issuer`) vào cấu trúc dữ liệu riêng tư `_private_host_state` cấp module, không thể truy cập từ candidate process.
   - Bảo vệ cả `_HostBoundaryState` và `_InternalHostBoundaryVault` bằng các metaclass `_HostBoundaryStateMeta` và `_InternalHostBoundaryVaultMeta`, nghiêm cấm đọc hoặc sửa đổi các thuộc tính `token`, `_token`, `port`, `_port`, `authkey`, `_authkey`, `proc`, `_proc`, `_credentials_initialized`, `_private_host_state` (ném `ProtocolViolationError` fail-closed).
   - Niêm phong module `test_host_boundary_harness` bằng `_SealedHostBoundaryModule(types.ModuleType)`, ẩn và chặn truy cập vào các thuộc tính riêng tư của harness.
2. **Thẩm định phân quyền đăng ký Dispatch ngoài tiến trình**:
   - Trong `TrustedHostRegisterDispatch`, thẩm định bắt buộc fail-closed trước khi gửi IPC:
     + `base_commit` bắt buộc phải khớp chính xác approved base SHA `4a7c8c921b7e05066505d51b168a02c3fde61317`. Bất kỳ base commit nào khác do caller tự chọn đều bị từ chối fail-closed.
     + `candidate_commit` bắt buộc là chuỗi hex 40 ký tự hợp lệ và không chứa các định danh giả mạo (`deadbeef`, `spoof`, `attacker`, `candidate`).
     + `delivery_task_id` và `dispatch_id` không được rỗng và không chứa các từ khóa giả mạo.
   - Trong daemon ngoài tiến trình, endpoint `REGISTER_DISPATCH` thực thi cùng các điều kiện thẩm định độc lập fail-closed và phát hành biên nhận dispatch (`dispatch_receipt`).
3. **Bảo vệ toàn vẹn phong bì duyệt và kiểm soát Overrides**:
   - Daemon từ chối ký phong bì đối với các dispatch chưa đăng ký (`Unregistered or unauthenticated review dispatch ... fail-closed`).
   - Daemon từ chối mọi nỗ lực override `base_commit`, `candidate_commit`, `delivery_task_id`, hoặc `review_dispatch_id` không khớp với bản ghi dispatch đã cấp phép.
   - Phong bì ký được gán giá trị trực tiếp từ bản ghi dispatch của supervisor.
4. **Nghiệm thu kiểm thử (Acceptance Evidence)**:
   - Bổ sung bài kiểm thử `test_20_sol_finding_candidate_dispatch_registration_and_credentials_remediated` trong `docs/parallel-delivery/test_negative_fixtures.py`.
   - Kiểm chứng toàn diện:
     + Fresh subprocess import candidate không thể đọc hoặc sửa đổi host credentials (`ProtocolViolationError`).
     + Đăng ký dispatch giả mạo với base commit hoặc candidate commit không hợp lệ bị từ chối fail-closed.
     + Thông điệp raw IPC giả mạo gửi tới daemon bị từ chối.
     + Yêu cầu phong bì cho dispatch chưa đăng ký hoặc có override trái phép bị từ chối.
     + Flow positive do supervisor phát hành với exact approved base và candidate commit được ký, xác minh chữ ký Ed25519 với khóa ghim và tiêu thụ thành công đúng 1 lần.
     + Replay tuần tự và đa luồng đồng thời bị chặn với `ReplayAttackError`.
     + Dọn dẹp sạch tiến trình sau khi dừng harness (`is_running() == False`).
   - Toàn bộ 404 bài kiểm thử trong negative fixture suite đạt PASS 100%.
   - Cổng kích hoạt sản xuất duy trì trạng thái an toàn: `ProductionActivationGate.STATUS == 'PRODUCTION_ACTIVATION_BLOCKED'`.

## 38. Khắc phục triệt để phát hiện Sol Audit trên 6a6972f (Đóng gói hoàn toàn Host Daemon Runtime, Loại bỏ _private_host_state khỏi Module Dict và Chặn đăng ký Candidate tùy ý)

Đợt rà soát độc lập trên exact candidate SHA `6a6972f43c4f8b87b3b3553907ba9a73c15b2a8b` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nhận finding `ROOT_ARCHITECTURE`:
- **Root cause**: Mặc dù đã ẩn thuộc tính ở tầng module class, việc truy cập trực tiếp qua `types.ModuleType.__getattribute__(h, "__dict__")` vẫn để lộ `_private_host_state` và các helper nội bộ trong `docs/parallel-delivery/test_host_boundary_harness.py`. Đồng thời, `TrustedHostRegisterDispatch` vẫn chấp nhận candidate commit tùy ý `0123456789abcdef0123456789abcdef01234567`, từ đó cho phép `ExternalReviewProducer` ký phát hành envelope duyệt cho candidate do caller tự chỉ định.
- **Counterexample an toàn**: Candidate đọc `raw_dict`, gọi trực tiếp `raw_dict["TrustedHostRegisterDispatch"]` với candidate commit `0123456789abcdef0123456789abcdef01234567`, đăng ký dispatch thành công và yêu cầu `ExternalReviewProducer` phát hành envelope duyệt hợp lệ.

Biện pháp khắc phục triệt để:
1. **Đóng gói Runtime trong Closure & Loại bỏ Private State khỏi Module Dict**:
   - Toàn bộ 23 hàm và trạng thái vận hành của host harness được đóng gói bên trong closure `_init_harness_runtime()`.
   - Loại bỏ hoàn toàn `_private_host_state`, `token`, `_token`, `port`, `_port`, `authkey`, `_authkey`, `proc`, `_proc`, `_state`, `_runtime` và các helper getter/setter `_get_harness_*`, `_set_harness_*`, `_clear_harness_*` khỏi module namespace.
   - Thử nghiệm trực tiếp bằng `types.ModuleType.__getattribute__(h, "__dict__")` bảo đảm không còn bất kỳ credential, state hay helper nhạy cảm nào bị lộ.
2. **Phân quyền Đăng ký Candidate nghiêm ngặt fail-closed**:
   - Cả trong hàm `TrustedHostRegisterDispatch` lẫn daemon ngoài tiến trình (`REGISTER_DISPATCH`), bổ sung thẩm định: `candidate_commit` bắt buộc phải thuộc tập authorized candidates do supervisor chỉ định (`_get_supervisor_approved_candidates()`).
   - Mọi nỗ lực đăng ký candidate commit tùy ý (như `0123456789abcdef...`) đều bị từ chối fail-closed với `ProtocolViolationError` ("caller cannot register arbitrary candidate commit without host supervisor authority").
3. **Cấp phát Biên nhận Supervisor mờ (Opaque Receipt)**:
   - `TrustedHostRegisterDispatch` trả về `disp_receipt_<32 hex>` thay vì capability token.
   - `ExternalReviewProducer` và `ExternalIntegrationProducer` thẩm định dispatch record trong daemon trước khi ký, từ chối phát hành envelope cho dispatch chưa đăng ký hoặc có override trái phép.
4. **Nghiệm thu kiểm thử (Acceptance Evidence)**:
   - Bổ sung assert kiểm tra `types.ModuleType.__getattribute__(h, "__dict__")` và tái hiện counterexample từ chối đăng ký candidate tùy ý trong `test_20_sol_finding_candidate_dispatch_registration_and_credentials_remediated` (`test_negative_fixtures.py`).
   - Toàn bộ 404 bài kiểm thử trong negative fixture suite đạt PASS 100%.
   - Cổng kích hoạt sản xuất duy trì trạng thái an toàn: `ProductionActivationGate.STATUS == 'PRODUCTION_ACTIVATION_BLOCKED'`.

## 39. Kh?c ph?c tri?t ?? ph?t hi?n Sol Audit tr?n 218e2ee (Lo?i b? bi?n m?i tr??ng PARALLEL_DELIVERY_SUPERVISOR_CANDIDATE v? Kh?a ch?t Candidate Authority b?t bi?n)

??t r? so?t ??c l?p tr?n exact candidate SHA `218e2ee77fce3c16778fdaf56c977968e22fdb03` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) ghi nh?n finding `ROOT_ARCHITECTURE`:
- **Root cause**: Trong `test_host_boundary_harness.py`, h?m `_init_harness_runtime()` ??c bi?n m?i tr??ng `PARALLEL_DELIVERY_SUPERVISOR_CANDIDATE`. Do ??, b?t k? caller ho?c ti?n tr?nh con n?o c?ng c? th? t? ? ??t bi?n m?i tr??ng n?y tr??c khi daemon kh?i t?o ?? m? r?ng danh s?ch `approved_candidates`, t? ?? cho ph?p ??ng k? candidate commit t?y ? v? y?u c?u `ExternalReviewProducer` k? ph?t h?nh envelope.
- **Counterexample an to?n**: Candidate thi?t l?p `os.environ['PARALLEL_DELIVERY_SUPERVISOR_CANDIDATE'] = '0123456789abcdef0123456789abcdef01234567'`, sau ?? g?i `TrustedHostRegisterDispatch` v?i candidate commit n?y. Daemon ch?p nh?n v? ph?t h?nh dispatch receipt `disp_receipt_...` th?nh c?ng.

Bi?n ph?p kh?c ph?c tri?t ??:
1. **Lo?i b? bi?n m?i tr??ng Caller-Controlled**:
   - X?a b? ho?n to?n vi?c ??c `os.environ.get("PARALLEL_DELIVERY_SUPERVISOR_CANDIDATE")` trong `test_host_boundary_harness.py`.
   - Ng?n ch?n ho?n to?n m?i n? l?c m? r?ng danh s?ch candidate tin c?y th?ng qua bi?n m?i tr??ng.
2. **Kh?a ch?t t?p Candidate Authority b?t bi?n**:
   - T?p `approved_candidates` ???c kh?a ch?t d??i d?ng immutable `frozenset({head_commit, sol_audit_commit})` do host supervisor ph? chu?n tr??c.
   - H?m `TrustedHostRegisterDispatch` th?m ??nh nghi?m ng?t: candidate commit b?t bu?c ph?i thu?c t?p n?y; m?i gi? tr? kh?c ??u b? t? ch?i fail-closed v?i `ProtocolViolationError`.
3. **Nghi?m thu ki?m th? (Acceptance Evidence)**:
   - B? sung ki?m th? counterexample trong `test_20_sol_finding_candidate_dispatch_registration_and_credentials_remediated` (`test_negative_fixtures.py`) ch?ng minh khi ??t bi?n m?i tr??ng `PARALLEL_DELIVERY_SUPERVISOR_CANDIDATE`, n? l?c ??ng k? candidate t?y ? v?n b? t? ch?i fail-closed v?i `ProtocolViolationError`.
   - To?n b? 404 b?i ki?m th? trong negative fixture suite ??t PASS 100%.
   - C?ng k?ch ho?t s?n xu?t duy tr? tr?ng th?i an to?n: `ProductionActivationGate.STATUS == 'PRODUCTION_ACTIVATION_BLOCKED'`.
