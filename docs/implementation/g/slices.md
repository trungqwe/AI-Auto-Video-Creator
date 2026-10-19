# Slice triển khai Phân hệ G — Điều phối công việc và quan sát vận hành

Nguồn: `docs/implementation/g/plan.md`. Mỗi slice là `work_package_slice`; Control biên dịch trong phong bì policy.

## Quy tắc chung cho mọi slice

- Chỉ sửa đúng các tệp liệt kê trong ownedPaths. Phong bì gồm `src/controlplane/domain/orchestration/**`, `src/controlplane/application/orchestration/**`, `src/controlplane/infrastructure/db/orchestration/**`, `tests/unit/orchestration/**`, `tests/integration/orchestration/**` và `docs/delivery-evidence/<task-id viết thường>/report.md`.
- Không sửa ba `__init__.py` của domain, application, db orchestration, `start_batch.py`, `src/controlplane/domain/statemachine/**`, migration, composition root, lockfile/`pyproject.toml`, `tests/m2/**`, `ui/dist`, `App.tsx`, state machine hay control API; nhu cầu loại này gửi IMPL-PLAN-CONVERGENCE (plan.md mục 9).
- Không thêm thư viện; chỉ stdlib và gói đã có trong runtime khoá. Không gọi mạng hay dịch vụ thật, không đọc `Credentials/` hay bí mật. Phân hệ khác được thay bằng fixture CP1 (`tests/fixtures/contracts/**`) và fake định nghĩa ngay trong tệp test. Fake chỉ chứng minh logic, không đóng gate tài nguyên thật.
- Import root `src/`, dạng `controlplane.…`, không có tiền tố `src.`. Không thêm `__init__.py` vào thư mục test.
- Test-first: viết test trước, tạo module với chữ ký đúng nhưng thân hàm `raise NotImplementedError`, chạy để thấy RED do assertion hoặc NotImplementedError; ImportError hay thiếu tệp không phải RED hợp lệ. Sau đó implement tới GREEN.
- Lệnh kiểm chạy bằng interpreter khoá của lane; ghi lệnh, exit code, kết quả RED và GREEN vào report.md của slice.
- Mọi tham số ngưỡng, timeout, retry là tham số bắt buộc, không giá trị mặc định cứng (D8-G-07). `recovery_epoch` so sánh bằng `str()` (D8-G-03).
- Mỗi slice có tiêu đề cấp 3 `G-<số>: <tên>`, tiếp theo là các mục kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance (requirement, instrument, counterexample), testCommands theo đúng thứ tự này.

### G-01: Validator binding ActivityRequest và ActivityResult

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/activity_binding.py`
  - `tests/unit/orchestration/test_g_activity_binding.py`
  - `docs/delivery-evidence/g-01/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-01`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-activity-execution.json`
    - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: Hàm `validate_activity_request(payload: dict, side_effect: bool = False) -> list[dict]` và `validate_activity_result(payload: dict) -> list[dict]` trả lỗi dạng `{code, field}` với code `missing_required`, `wrong_type`, `enum_violation`, `forbidden_field`, đúng tên, kiểu và required của BINDING-G-ACTIVITY-EXECUTION 1.0.0. `integer` không nhận bool; `datetime` phải là RFC 3339; `disposition` chỉ nhận succeeded, failed, waiting, outcome_unknown, stale; `secret_value` và `raw_blob` ở ActivityRequest là forbidden_field; trường lạ khác được bỏ qua (tương thích tiến); khi `side_effect=True` mà thiếu `execution_grant` thì `missing_required` (CT-WF-003). `recovery_epoch` là chuỗi.
    instrument: Test đọc fixture: mọi payload valid trả `[]`, mọi case invalid trả đúng `expected_error`; thêm case trường lạ vẫn hợp lệ, `execution_generation=True` bị wrong_type, `side_effect=True` thiếu grant bị missing_required.
    counterexample: disposition `done` được chấp nhận; payload có `secret_value` hợp lệ; generation dạng chuỗi được chấp nhận; thiếu grant ở thao tác side effect vẫn qua.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider`

### G-02: Validator binding CommitVideoCompletionRequest và CompletionLedgerEntry

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/completion_binding.py`
  - `tests/unit/orchestration/test_g_completion_binding.py`
  - `docs/delivery-evidence/g-02/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-02`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-c-i-completion.json`
    - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: Hàm `validate_commit_request(payload: dict) -> list[dict]` và `validate_ledger_entry(payload: dict) -> list[dict]` trả lỗi `{code, field}` với code `missing_required` hoặc `wrong_type` theo BINDING-G-C-I-COMPLETION 1.0.0 (CT-ORC-008, CT-ORC-009): `output_sha256` là 64 ký tự hex thường; `expected_variant_registry_revision` và `execution_generation` là integer không nhận bool; `completed_at` RFC 3339; `media_usage_manifest` là mảng; `output_naming_metadata`, `cost_usage_summary` là object; `cloud_location_verification_ref` bắt buộc ở request và `cleanup_policy_ref` bắt buộc ở ledger; trường lạ được bỏ qua.
    instrument: Test đọc fixture: payload valid trả `[]`, mọi case invalid trả đúng `expected_error`; thêm case hash chữ hoa bị wrong_type và trường lạ vẫn hợp lệ.
    counterexample: Completion không có `cloud_location_verification_ref` được chấp nhận; hash chữ hoa hoặc dạng khác sha256 được chấp nhận; revision dạng chuỗi được chấp nhận.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider`

### G-03: Đánh giá fencing generation và recovery epoch

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/fencing.py`
  - `tests/unit/orchestration/test_g_fencing.py`
  - `docs/delivery-evidence/g-03/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-03`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-activity-execution.json`
    - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: Dataclass frozen `GrantClaims(grant_id, stage_run_id, execution_generation: int, recovery_epoch: str, worker_lease_id, issued_at, expires_at, allowed_operation, input_fingerprint)` (CT-WF-004) và hàm `claims_from_execution_grant` ánh xạ từ `ExecutionGrant` P6 (import chỉ đọc, `operation_id` làm `grant_id`, epoch qua `str()`). `evaluate_result_fencing(claims, current_generation, current_recovery_epoch, result: dict, input_fingerprint, now, has_conflicting_success_receipt) -> FencingDecision(accepted, code)`. Thứ tự kiểm: epoch khác → `STALE_RECOVERY_EPOCH` (kể cả generation trùng); generation khác → `STALE_EXECUTION_GENERATION`; `grant_id` hoặc `stage_run_id` lệch → `GRANT_MISMATCH`; `now >= expires_at` → `GRANT_EXPIRED`, còn `expires_at` không parse được hoặc thiếu múi giờ hay `now` naive → `INVALID_EXPIRY` và không raise; fingerprint lệch → `INPUT_FINGERPRINT_MISMATCH`; có receipt thành công khác biệt → `OPERATION_CONFLICT`. Chỉ khi đủ 5 điều kiện CT-WF-004 mới `accepted=True`. Hàm thuần, không mutation (INV-003, INV-016).
    instrument: Pytest bảng case cho từng code; case sau restore: generation trùng nhưng epoch cũ bị từ chối (TST-WF-INV-016); `recovery_epoch` int ở `ExecutionGrant` và chuỗi ở result vẫn so khớp qua `str()`; fixture ActivityResult valid dùng làm result hợp lệ.
    counterexample: Result generation cũ được chấp nhận; epoch cũ generation trùng được chấp nhận; grant hết hạn vẫn commit; `expires_at` hỏng làm hàm raise.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider`

### G-04: Cấp grant đơn điệu và một lease hoạt động mỗi stage

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/grant_issuance.py`
  - `tests/unit/orchestration/test_g_grant_issuance.py`
  - `docs/delivery-evidence/g-04/report.md`
- dependsOn: `G-03`
- resourceLocks: `LOCK-G-04`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-activity-execution.json`
    - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: Protocol `GrantStorePort` (`latest_generation(stage_run_id)`, `active_grant(stage_run_id, now)`, `insert(claims)`, `revoke(grant_id)`) và `RecoveryEpochPort.current()`. `GrantIssuer.issue(stage_run_id, allowed_operation, input_fingerprint, worker_lease_id, ttl_seconds, now) -> GrantClaims` (`ttl_seconds` bắt buộc): generation = latest+1 đơn điệu, không bao giờ giảm hay tái dùng; còn grant chưa hết hạn của lease khác thì raise `ActiveGrantExistsError`; grant hết hạn bị revoke trước khi cấp mới (tăng generation); epoch lấy từ port tại thời điểm cấp; grant đã revoke không được chấp nhận lại (DoR 4 của module, CT-WF-004).
    instrument: Pytest với fake store có khóa luồng: 8 luồng cùng issue một stage cho đúng một grant hoạt động; reissue sau hết hạn tăng generation; sau khi đổi epoch grant mới mang epoch mới; kết hợp `evaluate_result_fencing` của G-03 từ chối result của grant cũ.
    counterexample: Hai worker cùng giữ lease một stage; generation lặp lại sau retry; grant mới mang epoch cũ.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider`

### G-05: Chính sách retry theo operation receipt

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/operation_receipt.py`
  - `tests/unit/orchestration/test_g_operation_receipt.py`
  - `docs/delivery-evidence/g-05/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-05`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-activity-execution.json`
    - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: `decide_retry(receipt_state: OperationState | None, receipt_fingerprint, new_fingerprint, retryable: bool) -> RetryDecision` (CT-WF-005): không receipt → `EXECUTE`; fingerprint khác → `NEW_OPERATION_KEY_REQUIRED`; `SUCCEEDED` → `RETURN_PREVIOUS_OUTPUT`; `OUTCOME_UNKNOWN` → `RECONCILE_FIRST` (không bao giờ `EXECUTE`); `FAILED` và retryable → `NEW_ATTEMPT_SAME_KEY`; `FAILED` không retryable → `FAIL_FINAL`; `PREPARED`/`STARTED` → `WAIT_IN_FLIGHT`. `apply_reconcile(state, revision, evidence_ref, outcome)` gọi `transition_operation` (import chỉ đọc) và phải có evidence để rời `OUTCOME_UNKNOWN`; thiếu evidence raise `ForbiddenTransitionError` (CT-STATE-011).
    instrument: Pytest bảng case cho từng trạng thái; `OUTCOME_UNKNOWN → SUCCEEDED` không evidence bị từ chối, có evidence được nhận; terminal không mở lại STARTED.
    counterexample: Timeout sau side effect thực hiện lại mù; retry từ OUTCOME_UNKNOWN; fingerprint khác dùng lại operation key cũ.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider`

### G-06: StageRun theo attempt, job waiting và cổng R18

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/stage_run_plan.py`
  - `src/controlplane/domain/orchestration/job_waiting.py`
  - `tests/unit/orchestration/test_g_stage_run_plan.py`
  - `tests/unit/orchestration/test_g_job_waiting.py`
  - `docs/delivery-evidence/g-06/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-06`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-activity-execution.json`
    - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: stage_run_plan.py: `plan_attempt(previous, new_stage_run_id)` tạo StageRun mới attempt+1 ở `PENDING` (D8-G-01), giữ job, stage_type, input_refs; `dependencies_ready(stage, runs)` chỉ đúng khi mọi dependency `SUCCEEDED`; `apply_activity_result(current_state, revision, disposition, fencing_accepted, owner_commit_confirmed, evidence_ref)` qua `transition_stage_run`: `succeeded` chỉ khi fencing_accepted và owner xác nhận commit, nếu không `STAGE_NOT_COMMITTED`; `failed` → `FAILED_RETRYABLE` hoặc `FAILED_FINAL` theo cờ retryable; `outcome_unknown` → `OUTCOME_UNKNOWN`; `stale` → `STALE`; `waiting` khi RUNNING không đổi stage (D8-G-02). job_waiting.py: `WaitReason` đúng 8 giá trị CT-ORC-007; `stage_requires_desktop(stage_type)` đúng cho `script`, `plan`, `tts` (R18), sai cho collect, normalize, dedup, media, index; `evaluate_wait(stage_type, capability_view: dict)` trả `Proceed` hoặc `Wait(reason)`, trạng thái `unavailable`, `unknown` không đủ để chạy (fail-closed), không bao giờ dẫn tới `FAILED_FINAL` hay tự thêm provider trả phí; `plan_job_transition` dùng `transition_job` ACTIVE ↔ WAITING; `on_capability_restored` chỉ trả đúng stage cần chạy lại, không restart pipeline.
    instrument: Pytest: attempt 2 là hàng mới; succeeded không có owner commit bị từ chối; stage collection chạy khi desktop offline còn script bị chờ `desktop_offline`; waiting không bao giờ thành failed; `READY_FOR_COMPLETION` khác `COMPLETED` (bốn mốc render, QC, upload, completion).
    counterexample: Stage SUCCEEDED chỉ vì worker báo xong; capability mất làm job FAILED_FINAL; script chạy khi desktop offline; resume chạy lại stage đã SUCCEEDED.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider`

### G-07: Allocation theo target, 1–3 job mỗi lượt và capacity

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/allocation_policy.py`
  - `src/controlplane/application/orchestration/job_allocation.py`
  - `tests/unit/orchestration/test_g_allocation_policy.py`
  - `tests/unit/orchestration/test_g_job_allocation.py`
  - `docs/delivery-evidence/g-07/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-07`
- bindingRefs:
    - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
    - `docs/parallel-delivery/bindings/g-c-i-completion.json`
- acceptance:
  - requirement: allocation_policy.py: `can_allocate(target, completed_count, active_reservations)` đúng khi `completed + active < target` (completed lấy từ số ledger, không từ số tệp); `plan_round(candidates, slots_left)` cấp 1–3 job cho một sự kiện/tin trong lượt, mỗi job một `angle_slot` khác nhau, yêu cầu nhiều hơn 3 hoặc trùng angle_slot raise `ValueError`; `reservation_action(job_state)` trả `HOLD` cho WAITING, `RELEASE` cho FAILED_FINAL, `CONVERT` cho COMPLETED, `NONE` cho retry (retry cùng job không tạo reservation mới). job_allocation.py: `JobAllocationService.allocate(batch_id, job_id, candidate)` qua port `AllocationStorePort` (`lock_batch`, `count_ledger`, `count_active`, `find_reservation(job_id)`, `create_job_and_reservation`) trong một khối nguyên tử; job_id đã có reservation trả lại reservation cũ; vượt target raise `BatchTargetReachedError`.
    instrument: Pytest với fake store có khóa luồng: 8 luồng tranh suất cuối cho đúng một reservation, batch không vượt target (TST-WF-INV-018 mức logic); lỗi giữa chừng sau khi tạo job không để job mồ côi (cả hai hoặc không); retry cùng job_id không thêm suất; job WAITING giữ suất; FAILED_FINAL trả suất.
    counterexample: Hai allocator cùng nhận suất cuối; retry tạo reservation thứ hai; đếm số tệp thay cho ledger; hai job cùng angle_slot.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cacheprovider`

### G-08: Luồng VariantReservation và registry revision

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/variant_reservation_flow.py`
  - `tests/unit/orchestration/test_g_variant_reservation_flow.py`
  - `docs/delivery-evidence/g-08/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-08`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-c-i-completion.json`
    - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: `VariantReservationFlow` dùng port `VariantRegistryPort` (`current_revision(workspace)`, `find_by_job`, `find_active_by_fingerprint`, `save`, `bump_revision`) với fake trong test. `reserve(request)` (CT-ORC-012): revision khác expected → `VARIANT_VALIDATION_STALE`, không tạo reservation; fingerprint đang ACTIVE hoặc CONVERTED của job khác → `VARIANT_CONFLICT`; cùng idempotency key và cùng input trả receipt cũ, khác input là `VARIANT_CONFLICT`; tối đa một ACTIVE mỗi job; mỗi tạo/release/convert tăng revision đúng một lần. `release(job_id)` chỉ khi job terminal lỗi đã ghi nhận; `convert(job_id)` khi completion. `on_wait`, `on_desktop_offline`, `on_lease_expired` không đổi trạng thái (không TTL). Receipt reserve cũ không hồi sinh ACTIVE sau khi RELEASED/CONVERTED. Dùng `ReservationState` P6 (import chỉ đọc).
    instrument: Pytest theo TST-WF-VAR-001 (hai job cùng chữ ký, một thắng, bên kia stale rồi conflict), VAR-003 (mất ACK, offline, lease hết hạn, terminal release, completed convert một lần, receipt cũ không hồi sinh), VAR-004 phía G (hai phương án khác nhau cùng được sau refresh revision).
    counterexample: Hai job cùng giữ chỗ một biến thể; lease hết hạn làm release; retry tạo reservation thứ hai; revision không tăng khi release.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider`

### G-09: Cổng điều kiện completion

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/completion_gate.py`
  - `tests/unit/orchestration/test_g_completion_gate.py`
  - `docs/delivery-evidence/g-09/report.md`
- dependsOn: `G-02`, `G-03`
- resourceLocks: `LOCK-G-09`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-c-i-completion.json`
    - `docs/parallel-delivery/bindings/i-artifact-version.json`
    - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: `check_completion(job_state, request: dict, fencing: FencingDecision, reservation, current_registry_revision, existing_ledger) -> GateDecision(code, action)` (CT-ORC-008 bước 1–2). Thứ tự: payload lỗi theo G-02 → `INVALID_REQUEST`; đã có ledger cùng input → `ALREADY_COMPLETED` (trả ledger cũ), khác input → `CONFLICT`; job khác `READY_FOR_COMPLETION` → `JOB_NOT_READY`; fencing không accepted → mã fencing; thiếu `cloud_location_verification_ref` → `CLOUD_VERIFICATION_MISSING`; reservation không ACTIVE hoặc không thuộc đúng job/hash → `RESERVATION_INVALID`; `current_registry_revision` khác `expected_variant_registry_revision` → `VARIANT_REGISTRY_STALE` (action `KEEP_WAITING`, không ghi gì); đối chiếu xác nhận trùng thực → `VARIANT_CONFLICT_FINAL` (action `FAIL_JOB_RELEASE`). Chỉ khi đủ mới `PROCEED`.
    instrument: Pytest bảng case cho từng code, payload valid lấy từ fixture g-c-i-completion; stale không có hành động ghi; QC pass nhưng chưa cloud verified thì không `PROCEED` (phần G của TST-E2E-INV-009).
    counterexample: Job ACTIVE được hoàn thành thẳng; completion không có cloud verification; revision stale vẫn ghi ledger; completion lặp tạo ledger thứ hai.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider`

### G-10: CommitVideoCompletion trong một unit of work

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/commit_completion.py`
  - `tests/integration/orchestration/test_g_commit_completion.py`
  - `docs/delivery-evidence/g-10/report.md`
- dependsOn: `G-09`, `G-13`
- resourceLocks: `LOCK-G-10`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-c-i-completion.json`
    - `docs/parallel-delivery/bindings/domain-event-envelope.json`
    - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: `CommitVideoCompletion.execute(request, context)` chạy trong một unit of work (hình dạng `IUnitOfWork`, fake có snapshot và rollback định nghĩa trong test) theo CT-ORC-008: cổng G-09; tạo ledger duy nhất; job `READY_FOR_COMPLETION → COMPLETED` qua `transition_job`; convert capacity reservation và VariantReservation sang `CONVERTED`; tăng revision registry; tăng bộ đếm batch đúng một lần; gọi port `MediaUsagePort.record(manifest)` của C (G không ghi bảng C); ghi outbox `VideoCompleted` (payload từ G-13) trong cùng unit of work chỉ sau các bước trên; tạo cleanup eligibility dạng bản ghi, không phát lệnh xóa. Lỗi ở bất kỳ bước nào rollback toàn bộ (không ledger, usage, count, outbox). Gọi lặp cùng input trả ledger cũ, count tăng một lần; khác input là `CONFLICT`. Trường ledger ngoài request lấy từ `context` (D8-G-14).
    instrument: Pytest tích hợp in-process: lỗi tiêm ở mọi bước (trước/sau ledger, trước/sau usage, trước outbox) cho trạng thái trước-sau bằng nhau (TST-WF-INV-017 mức logic); gọi lặp 5 lần count = 1 (TST-WF-INV-010); stale registry không ghi gì; không có lệnh xóa nào được phát.
    counterexample: Ledger commit nhưng MediaUsage mất; completion lặp tăng count hai lần; VideoCompleted phát khi unit of work rollback; completion phát lệnh xóa local trực tiếp.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider`

### G-11: Ngữ nghĩa retry, biến thể, debug và chính sách retry/backoff

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/command_semantics.py`
  - `src/controlplane/domain/orchestration/retry_policy.py`
  - `tests/unit/orchestration/test_g_command_semantics.py`
  - `tests/unit/orchestration/test_g_retry_policy.py`
  - `docs/delivery-evidence/g-11/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-11`
- bindingRefs:
    - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
    - `docs/parallel-delivery/bindings/g-activity-execution.json`
    - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: command_semantics.py: `decide_retry_stage(job, stage, new_input_fingerprint)` giữ `video_job_id`, snapshot_ref, intent, fingerprint, tăng attempt, không đổi completed count; fingerprint đổi → `USE_REGENERATE_OR_VARIANT` (CT-ORC-005); `decide_new_variant(parent_job, prior_variant_refs, new_job_id)` tạo job mới có parent article/event refs, không tính vào target trước completion (CT-ORC-006); `decide_regenerate(stage, dependency_graph)` tạo revision downstream mới, không sửa lịch sử; `validate_debug_request(auto_advance)` bắt buộc `False`, sau debug không stage nào tự chạy (CT-ORC-004). retry_policy.py: `RetryPolicy(max_attempts, initial_delay_seconds, multiplier, max_delay_seconds)` mọi tham số bắt buộc; `next_delay(attempt, policy)` tăng mũ có trần, xác định; `should_retry(attempt, problem_retryable, policy)`; timeout schedule-to-start không tiêu thụ attempt (CT-WF-007); giá trị mặc định cứng không tồn tại.
    instrument: Pytest: retry không đổi job_id và không tăng completed count; variant có job_id mới; debug `auto_advance=True` bị từ chối (TST-E2E-010, TST-E2E-014); chuỗi delay 1, 2, 4 có trần; policy thiếu tham số raise TypeError.
    counterexample: Retry coi như biến thể mới; variant tính vào target trước completion; debug tự chạy stage kế; backoff vô hạn hoặc hard-code 10/300/3 của schedule-policy.yaml.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider`

### G-12: Workflow catalog, task queue và resource admission

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/workflow_catalog.py`
  - `src/controlplane/domain/orchestration/resource_admission.py`
  - `tests/unit/orchestration/test_g_workflow_catalog.py`
  - `tests/unit/orchestration/test_g_resource_admission.py`
  - `docs/delivery-evidence/g-12/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-12`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-activity-execution.json`
    - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: workflow_catalog.py: định nghĩa dữ liệu khai báo (frozen) cho sáu workflow CT-WF-001 (`DailyCollectionWorkflow`, `ContentEnrichmentWorkflow`, `ProductionBatchWorkflow`, `VideoProductionWorkflow`, `DebugStageWorkflow`, `MaintenanceWorkflow`) với `workflow_version`, danh sách stage kèm dependency; `route_stage(stage_type)` ánh xạ sang sáu task queue logic CT-WF-002 (`control-workflows`, `cloud-io`, `cloud-ai`, `desktop-cpu`, `desktop-gpu`, `desktop-render`); `validate_catalog()` kiểm không chu trình, mọi stage có queue, stage script/plan/tts nằm ở queue desktop theo R18, VideoProduction là child cô lập, DebugStage `auto_advance=False`; `is_breaking_change(old, new)` đúng khi đổi thứ tự stage, retry semantics hoặc completion invariant (CT-WF-009). resource_admission.py: `AdmissionLimits` và `ResourceSnapshot` (cpu, gpu_slots_free, ram_free_mb, disk_free_mb, network_ok) đều bắt buộc, không mặc định; `decide_admission(limits, snapshot, need)` trả `Admitted`, `Deferred(code)` (`CPU_SATURATED`, `GPU_BUSY`, `RAM_LOW`, `NETWORK_DOWN`) hoặc `Wait(insufficient_disk)` (D8-G-06).
    instrument: Pytest: catalog hợp lệ; thêm chu trình hoặc stage không có queue bị từ chối; đổi thứ tự stage là breaking; RAM thấp hoặc GPU bận là Deferred (job không WAITING); thiếu đĩa là `insufficient_disk`; limits thiếu tham số raise TypeError.
    counterexample: Stage script chạy ở queue cloud; resource bão hòa làm job FAILED_FINAL; ngưỡng đọc từ schedule-policy.yaml; breaking change không bị phát hiện.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cacheprovider`

### G-13: Event payload của G và audit nhất quán

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/event_payloads.py`
  - `src/controlplane/domain/orchestration/consistency_audit.py`
  - `tests/unit/orchestration/test_g_event_payloads.py`
  - `tests/unit/orchestration/test_g_consistency_audit.py`
  - `docs/delivery-evidence/g-13/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-13`
- bindingRefs:
    - `docs/parallel-delivery/bindings/domain-event-envelope.json`
    - `docs/parallel-delivery/bindings/g-c-i-completion.json`
- acceptance:
  - requirement: event_payloads.py: `build_g_event(event_name, aggregate_id, aggregate_revision, recovery_epoch, payload)` chỉ nhận 8 tên event của G (`BatchStarted`, `JobAllocated`, `StageStateChanged`, `JobWaiting`, `JobFailed`, `VideoCompleted`, `BatchTargetReached`, `BatchExhausted`), trả dict có đủ trường bắt buộc của BINDING-DOMAIN-EVENT-ENVELOPE (`producer` là `G`, `schema_version` chuỗi `1`, `sensitivity` là `internal`, `recovery_epoch` chuỗi); payload chỉ mang ID và revision, qua `ensure_safe_event_payload` (import chỉ đọc) và từ chối trường cấm `secret_value`, `raw_oauth_response`, `stack_trace`, `blob`; `VideoCompleted` yêu cầu `completion_id`. consistency_audit.py: `audit_consistency(snapshot) -> tuple[Finding, ...]` chỉ đọc, sắp xếp ổn định theo (code, ref), code `LEDGER_COUNT_MISMATCH`, `ORPHAN_ACTIVE_RESERVATION`, `LEDGER_WITHOUT_COMPLETED_JOB`, `WAITING_JOB_WITHOUT_REASON`, `RUNNING_STAGE_WITHOUT_ACTIVE_GRANT`, `JOB_WITHOUT_STATE_OR_LOG`.
    instrument: Pytest: mỗi event hợp lệ; tên lạ và payload có canary secret (TST-SEC-INV-012 phần G) bị từ chối; mỗi finding một case; snapshot nhất quán trả tuple rỗng; gọi hai lần cho kết quả bằng nhau và không đổi snapshot.
    counterexample: Event mang secret hoặc stack trace; epoch dạng int lọt ra envelope; job biến mất không trạng thái không bị báo; bộ đếm batch lệch ledger không bị báo.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cacheprovider`

### G-14: Resume sau restart, lý do dừng batch và app session

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/recovery_scan.py`
  - `src/controlplane/domain/orchestration/batch_outcome.py`
  - `src/controlplane/domain/orchestration/app_session.py`
  - `tests/unit/orchestration/test_g_recovery_scan.py`
  - `tests/unit/orchestration/test_g_batch_outcome.py`
  - `tests/unit/orchestration/test_g_app_session.py`
  - `docs/delivery-evidence/g-14/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-G-14`
- bindingRefs:
    - `docs/parallel-delivery/bindings/g-activity-execution.json`
    - `docs/parallel-delivery/bindings/g-c-i-completion.json`
    - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: recovery_scan.py: hàm thuần `plan_resume(snapshot) -> tuple[ResumeAction, ...]` từ trạng thái stage, hạn grant, epoch hiện hành, capability view và con trỏ cấp phát, trả hành động xác định `RESUME_STAGE`, `CREATE_NEW_ATTEMPT`, `RECONCILE_OUTCOME_UNKNOWN`, `QUARANTINE_OLD_EPOCH_RESULT`, `REISSUE_GRANT_NEW_EPOCH`, `KEEP_WAITING`; không bao giờ chạy lại stage đã SUCCEEDED và không quay về tin đầu tiên. batch_outcome.py: `decide_batch_outcome(ledger_count, target, active_reservations, eligible_remaining, capability_blocked_work, system_fault)` (CT-ORC-010) → `COMPLETED_TARGET`, `COMPLETED_EXHAUSTED` (chỉ khi hết candidate và không còn reservation ACTIVE), `WAITING_CAPABILITY`, `FAILED_SYSTEM`, `CONTINUE`, chuyển qua `transition_batch`; job FAILED_FINAL riêng lẻ không làm `FAILED_SYSTEM`. app_session.py: `AppSession` bất biến; `close_session(session, completed_video_count)` chỉ đặt `output_folder_intent` khi count lớn hơn 0 (TST-E2E-013); `resume_session` giữ checkpoint batch/job; `log_ref` bắt buộc đủ session, job, stage, correlation (CT-ORC-011).
    instrument: Pytest: result epoch cũ generation trùng bị quarantine (TST-WF-INV-016); desktop online lại chỉ resume stage đang chờ; batch còn job WAITING không bị COMPLETED_EXHAUSTED; một job lỗi, batch tiếp tục (TST-E2E-007); session không video không có folder intent.
    counterexample: Resume chạy lại từ đầu; batch kết thúc EXHAUSTED khi còn job chờ; một job lỗi làm batch FAILED_SYSTEM; session rỗng tạo output folder.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orchestration/test_g_batch_outcome.py tests/unit/orchestration/test_g_app_session.py -q -p no:cacheprovider`
