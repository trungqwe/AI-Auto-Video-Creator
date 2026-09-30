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
6. **Bộ kiểm thử toàn diện**: 10 bài test mới trong `TestSolTrustBoundaryRootCauseRemediation` (RED evidence, worker monkey-patching failure, asymmetric Ed25519 signature tamper rejection, key revocation, single-use replay protection, SQLite restart durability, temporal validity, production gate fail-closed, fresh subprocess isolation, và positive control full lifecycle) nâng tổng số bài test lên **390/390 tests PASS 100%**.
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
   - Kiểm tra toàn diện temporal validity (expires_at, issued_at <= now + 30.0s), ràng buộc danh tính (expected_task_id, expected_candidate, expected_base), chống phát lại (envelope_id single-use), chống tái sử dụng 
once, và monotonic fencing token theo miền (	ask_fencing).
   - Đảm bảo tính bền vững qua restart tiến trình với SQLite và an toàn tương tranh đa luồng (10 luồng đồng thời: đúng 1 luồng thành công, 9 luồng bị chặn bởi ReplayAttackError).
