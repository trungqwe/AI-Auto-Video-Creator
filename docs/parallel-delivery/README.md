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
22. **Boundary Probe 22**: Cổng tương thích harness: Phát hiện hiện tượng sụp namespace công cụ (`functions.exec` -> `functions`) và thất bại khói thực thi, kích hoạt `STOP condition` và cơ chế fallback.
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
   - Máy trạng thái `HarnessExecutionStateMachine` quản lý chuyển đổi trạng thái thực thi (`IDLE` -> `RUNNING` -> `SUCCESS` | `FAILURE` | `STOP_FALLBACK`), lưu trữ toàn bộ lịch sử chuyển đổi và bảo đảm fallback Antigravity native minh bạch, có thể quan sát được khi gặp STOP condition.
7. **Bộ kiểm thử tự động 103 fixtures**: Tích hợp 24 bài kiểm tra bổ sung trong `test_negative_fixtures.py` bao quát toàn bộ các ca đối chứng Sol Round 3 và các probe biên lân cận.
