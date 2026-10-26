# Slice nối dây chuyền production — IMPL-PLAN-PROD-WIRING

Nguồn: `docs/implementation/prod-wiring/plan.md` và `docs/implementation/prod-wiring/inventory.md`. Ba mươi hai slice `PW-*`: năm slice chạm composition root hoặc migration (`PW-SCHEMA`, `PW-G1`, `PW-G3`, `PW-W1`, `PW-W2`) là `convergence_slice`, hai mươi bảy slice còn lại là `work_package_slice`; `PW-E2E` phụ thuộc mọi slice còn lại. CP7-10 và CP7-11 chạy sau `PW-E2E` PASS (chiều phụ thuộc đó thuộc kế hoạch CP7, không ghi trong dependsOn của slice PW).

## Quy tắc chung cho mọi slice

- Chỉ sửa tệp trong `ownedPaths`; không sửa `docs/milestones/**/evidence/**`, `ui/dist`, `tests/m1`, `tests/m2`, `docs/09-contracts/**`, lockfile. Không thêm thư viện (D10). Không import tiền tố `src.`.
- Khoá lấy từ `docs/parallel-delivery/ownership-and-locks.yaml`; hai slice cùng khoá chạy tuần tự. GIẢ ĐỊNH (D8): `tools/launcher/launcher.py` thuộc `LOCK-COMPOSITION-ROOT`.
- Loại slice (ghi chú Control về tài nguyên dùng chung: migration và composition root chỉ gói hội tụ hoặc gói phụ thuộc được sửa, mỗi lúc một owner): slice có `ownedPaths` chứa `src/controlplane/api/wiring/**`, `tools/launcher/launcher.py` hoặc `src/**/migrations/**` là `convergence_slice`, khoá `LOCK-COMPOSITION-ROOT` hoặc `LOCK-MIGRATION-SEQUENCE`; các slice khác là `work_package_slice`. Hiện có năm `convergence_slice`: `PW-SCHEMA`, `PW-G1`, `PW-G3`, `PW-W1`, `PW-W2`.
- Tránh xung đột với `ADAPT-PROD-FIX3` trên `src/controlplane/api/wiring/production.py` (`docs/implementation/read-screens/plan.md` mục 7.2; `convergence_slice`, `LOCK-COMPOSITION-ROOT`; sửa import `compose_read_screens`, dòng gán `api_app.state.module_services` trong `build_production_app` và docstring đầu tệp; test `tests/integration/adapt/prod/test_adapt_prod_app.py`): (1) hai gói cùng `LOCK-COMPOSITION-ROOT` nên chạy tuần tự, không bao giờ song song; Control giao gói sau trên HEAD đã gồm gói trước, Worker đọc lại tệp ở HEAD và neo theo tên symbol, không theo số dòng ghi trong tài liệu; (2) không thêm `dependsOn` cứng giữa `PW-W2` và `ADAPT-PROD-FIX3` để lô PW không chờ kế hoạch read-screens; (3) vùng sửa của `PW-W2` trong `production.py` chỉ gồm `_build_services` cùng import đi kèm (và `TemporalWorkerGroup` nếu cần); cấm sửa khối gán `api_app.state.module_services[...]` trong `build_production_app`, docstring đầu tệp, `SourceModuleService`, `HookModuleService` và mọi phần khác; `PW-W2` không sửa `tests/integration/adapt/prod/test_adapt_prod_app.py`; (4) lệnh kiểm của `PW-W2` chạy `test_adapt_prod_app.py` để bản sửa không làm đỏ test đã nghiệm thu.
- Mọi slice có test thật trên PostgreSQL thử (`M2_TEST_PG_DSN`; thiếu thì `pytest.fail('BLOCKED_EXTERNAL: ...')`, không skip). Slice chạm workflow dùng server test của temporalio. 9Router, Drive, GPU, Kokoro, faster-whisper chỉ được thay bằng adapter giả nằm trong `tests/integration/prod_wiring/`; không giả PostgreSQL, Temporal, FFmpeg đã ghim (sha256 `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`).
- Test-first: thấy RED do assertion đúng oracle (thiếu import, binary hay setup không phải RED hợp lệ) rồi mới implement. `tests/integration/prod_wiring/` không có `__init__.py`; tên tệp test duy nhất `test_pw_<mã>_<tên>.py`; mã test `PW-<mã>-NN` trong coveredIds ứng với hàm `test_pw_<mã>_NN_<tên>`.
- Mỗi `counterexample` phải bị ít nhất một test bắt: cài counterexample vào mà test vẫn xanh thì slice chưa đóng.
- Bằng chứng ở `docs/delivery-evidence/pw-<mã viết thường>/report.md` (lệnh, mã thoát, số test pass), không ghi bí mật, không gọi dịch vụ thật (D5). Adapter production không chứa `fake`, `mock`, `memory`, không đọc `os.environ` cho bí mật.
- Test đã nghiệm thu bị đổi hành vi (quy tắc F1 của audit): slice nào đổi hành vi mà test có sẵn ngoài `tests/integration/prod_wiring/` đang khoá hành vi cũ thì tệp test đó phải nằm trong `ownedPaths` và trong `testCommands` của chính slice; slice chỉ đổi assertion khoá hành vi cũ, không xoá test, không nới oracle, và ghi từng dòng đã đổi cùng lý do vào `report.md`. Các slice dùng chung tệp được tuần tự hoá bằng chuỗi `dependsOn` hoặc khoá chung. Bảng tệp: `PW-SCHEMA` → `tests/integration/persistence/{a,b,d,e,f,g,i,j}/test_persist_<chữ>_postgres.py` và `test_cp3_migration_sequence.py`; `PW-G1`, `PW-W1`, `PW-W2` → `tests/integration/adapt/launch/test_adapt_launch_cli.py`; `PW-CAT1`, `PW-CAT2`, `PW-G5`, `PW-A3` → `tests/integration/convergence/test_cp6_video_production_flow.py`. Lệnh tìm cho thấy hết vị trí của mẫu: `rg -n "range[(]1, ?19[)]|len[(]forward[)] == 18" tests/integration/persistence`, `rg -n "startswith[(].rec-" tests`, `rg -n "class FakeBatchGateway|flow.unbound ==" tests/integration/convergence`.
- Mở rộng quy tắc F1 (test khoá cấu trúc): test khoá cấu trúc, gồm test liệt kê tệp trong một thư mục, quét token cấm, ranh giới import theo gói và kiểm kê builder hay bảng tên, cũng thuộc quy tắc F1. Slice thêm tệp hay import vào phạm vi các test đó phải chạy chúng trong `testCommands`; chỉ được sửa test khi kế hoạch nêu đích danh (tệp nằm trong `ownedPaths` của slice và assertion được sửa nêu trong `acceptance`); miễn trừ chỉ theo đường dẫn chính xác (tập miễn trừ đóng, khoá là đúng tệp, không dùng mẫu, không miễn cả thư mục), không nới cấm khác, không xoá test, ghi từng dòng đã đổi cùng lý do vào `report.md` của slice. Lệnh tìm cho thấy hết vị trí của mẫu: `rg -n "ORCH.glob|BANNED_ADAPTER_TOKENS|ADAPTER_EXEMPTIONS|ADAPTER_IMPORT_EXEMPTIONS|OWN_SUBSYSTEM|EXPECTED_BUILDERS" tests`.

### PW-H0: Khung kiểm thử prod_wiring

- kind: work_package_slice
- ownedPaths:
  - `tests/integration/prod_wiring/conftest.py`
  - `tests/integration/prod_wiring/pw_support.py`
  - `tests/integration/prod_wiring/test_pw_h0_harness.py`
  - `docs/delivery-evidence/pw-h0/report.md`
- dependsOn: `IMPL-PLAN-PROD-WIRING`
- resourceLocks: `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `tests/integration/adapt/prod/test_adapt_prod_app.py:114-135`; `tests/m1/p2/conftest.py:1-20`; `src/controlplane/infrastructure/db/migration_runner.py` (`MigrationRunner`)
- acceptance:
  - requirement: (1) fixture `pw_database` tạo CSDL tạm `pw_<hex8>` từ `M2_TEST_PG_DSN`, chạy `MigrationRunner(..., is_test_env=True, expected_database_name=...)`, seed một workspace và một actor, `DROP DATABASE ... WITH (FORCE)` trong `finally`; thiếu DSN thì `pytest.fail('BLOCKED_EXTERNAL: ...')`. (2) fixture `pw_temporal` bọc `WorkflowEnvironment.start_time_skipping()` và trả client. (3) `pw_support.py` có adapter giả cho dịch vụ ngoài (`FakeRouter`, `FakeDrive`, `FakeKokoro`, `FakeAligner`, `FakeGpu`), mỗi adapter ghi lại lời gọi để test đếm; hàm `assert_no_support_import(root)` quét AST `src/**` không import `pw_support`.
    instrument: `test_pw_h0_harness.py`: hai test dùng hai CSDL khác tên và cả hai bị xoá sau test; workflow echo chạy trên `pw_temporal`; mỗi fake đếm đúng số lời gọi; `assert_no_support_import` đỏ khi một tệp giả định trong `tmp_path` import `pw_support`.
    counterexample: dùng chung CSDL giữa test; skip khi thiếu DSN; fake đặt trong `src/**`; DSN trỏ CSDL sản xuất.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_h0_harness.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('tests/integration/prod_wiring/conftest.py').read_text(encoding='utf-8'); assert 'BLOCKED_EXTERNAL' in t and 'pytest.skip' not in t, 'PW-H0'"`
- coveredIds: PW-H0-01..05, CT-WF-001

### PW-SCHEMA: Migration 0019 cho nối dây

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/migrations/0019_prod_wiring.sql`
  - `src/controlplane/infrastructure/db/migrations/0019_prod_wiring.rollback.sql`
  - `tests/integration/convergence/test_cp3_migration_sequence.py`
  - `tests/integration/persistence/a/test_persist_a_postgres.py`
  - `tests/integration/persistence/b/test_persist_b_postgres.py`
  - `tests/integration/persistence/d/test_persist_d_postgres.py`
  - `tests/integration/persistence/e/test_persist_e_postgres.py`
  - `tests/integration/persistence/f/test_persist_f_postgres.py`
  - `tests/integration/persistence/g/test_persist_g_postgres.py`
  - `tests/integration/persistence/i/test_persist_i_postgres.py`
  - `tests/integration/persistence/j/test_persist_j_postgres.py`
  - `tests/integration/prod_wiring/test_pw_schema_migration.py`
  - `docs/delivery-evidence/pw-schema/report.md`
- dependsOn: `PW-H0`
- resourceLocks: `LOCK-MIGRATION-SEQUENCE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql:23-35`; `src/controlplane/infrastructure/db/migrations/0011_orchestration_extensions.sql:60-70`; `src/controlplane/domain/orchestration/allocation_policy.py:24`; `tests/integration/convergence/test_cp3_migration_sequence.py:22,162,166,330`
- acceptance:
  - requirement: Migration duy nhất của kế hoạch (OI-PW-07: sửa test dãy vì 18 thành 19). (1) `cp_stage_runs.job_id` bỏ NOT NULL (khoá ngoại ghép giữ nguyên) và thêm `workflow_id TEXT NULL` cùng CHECK `job_id IS NOT NULL OR workflow_id IS NOT NULL`, để workflow Daily, Enrichment, Maintenance ghi được stage run. (2) Bảng `cp_job_candidates(workspace_id, job_id, batch_id, candidate_ref, source_set_ref, created_at)` khoá chính `(workspace_id, job_id)`, lưu `AllocationCandidate.candidate_ref`. (3) Bảng `cp_creative_selections(workspace_id, selection_id, job_id, selection_revision, content_sha256, payload JSONB, created_at)` duy nhất `(workspace_id, job_id, selection_revision)`. (4) Bảng `cp_source_cycle_marks(workspace_id, source_id, cycle_day DATE, collection_run_ref, created_at)` khoá chính `(workspace_id, source_id, cycle_day)` cho CT-SRC-004. (5) Rollback đối xứng. Không sửa migration 0001-0018. (6) Sửa các test đã nghiệm thu khoá dãy 18 migration, chỉ đổi con số, giữ nguyên tên hàm: `test_cp3_migration_sequence.py` — `NAMES` (dòng 22) thêm `19: '0019_prod_wiring'`, dòng 158 `range(1, 19)` thành `range(1, 20)`, dòng 162 `== 18` thành `== 19`, dòng 330 và 336 `assert_versions(dsn, 18)` thành `assert_versions(dsn, 19)`, docstring dòng 1 `0009..0018` thành `0009..0019`; tám test persistence — b:63, a:236, d:75, e:96, f:68, g:144, i:95, j:89 đổi `range(1, 19)` thành `range(1, 20)`, và `test_persist_d_postgres.py:306` `assert len(forward) == 18` thành `assert len(forward) == 19`. `tests/integration/persistence/c/test_persist_c_postgres.py` không khoá số migration nên không sửa.
    instrument: `test_pw_schema_migration.py` trên CSDL tạm: `migrate_up` tới 0019 và kiểm `information_schema`; INSERT stage run chỉ có `workflow_id` thành công, thiếu cả hai bị CHECK từ chối; ba bảng mới có khoá đúng; rollback về 0018 sạch; `test_cp3_migration_sequence.py` và toàn bộ `tests/integration/persistence` xanh sau khi đổi số 18 thành 19.
    counterexample: sửa migration cũ; thêm bảng ngoài danh sách; CHECK thiếu; rollback bỏ sót bảng; bỏ sót một test persistence còn khoá `range(1, 19)`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_schema_migration.py tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider`
  - `python -m pytest tests/integration/persistence -q -p no:cacheprovider`
  - `python -c "import pathlib, re; ps = sorted(pathlib.Path('tests/integration/persistence').glob('*/test_persist_*_postgres.py')); assert len(ps) == 9, ps; bad = [str(p) for p in ps if re.search('range[(]1, ?19[)]|len[(]forward[)] == 18', p.read_text(encoding='utf-8'))]; assert not bad, bad"`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/migrations/0019_prod_wiring.sql').read_text(encoding='utf-8').lower(); assert 'cp_job_candidates' in t and 'cp_creative_selections' in t and 'cp_source_cycle_marks' in t and 'workflow_id' in t, 'PW-SCHEMA'"`
- coveredIds: PW-SCHEMA-01..05, CT-ORC-003, CT-SRC-004

### PW-G1: AppSession và recovery epoch thập phân

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/orchestration/app_session.py`
  - `tools/launcher/launcher.py`
  - `tests/integration/prod_wiring/test_pw_g1_app_session.py`
  - `tests/integration/adapt/launch/test_adapt_launch_cli.py`
  - `tests/integration/convergence/test_cp5_completion_uow.py`
  - `docs/delivery-evidence/pw-g1/report.md`
- dependsOn: `PW-SCHEMA`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `tools/launcher/launcher.py:122,533-603,914`; `src/controlplane/infrastructure/db/orchestration/grants.py:96-110`; `src/controlplane/infrastructure/db/migrations/0011_orchestration_extensions.sql:60-70`; `src/controlplane/application/orchestration/workflows/activities.py:186-198`
- acceptance:
  - requirement: (1) `PostgresAppSessions(connection, workspace_id)` có `begin(session_ref, recovery_epoch)` (một giao dịch: đặt phiên ACTIVE cũ thành ABANDONED rồi INSERT phiên ACTIVE mới; epoch phải là chuỗi chữ số thập phân, từ chối `rec-...`) và `end(session_ref)` (ENDED). (2) Launcher: epoch trong `state/recovery-epoch.json` là số thập phân, ghi `1` ở lần đầu (lần ghi đầu tiên khi chưa có tệp, kể cả `restore` đầu tiên), tăng đúng 1 mỗi lần `restore`, giữ nguyên qua stop/start; giá trị cũ `rec-<stamp>-<hex>` được đọc là (epoch số lớn nhất trong `cp_app_sessions`) cộng 1; thứ tự ghi epoch trước khi đổi `state/active-db` giữ nguyên. (3) `launcher start` gọi `begin` sau migrate và `ensure_identity`, trước `start_worker` và relay; tiến trình `serve` thoát êm thì gọi `end`. (4) `PostgresRecoveryEpoch.current()` trả chuỗi thập phân mà `to_execution_grant` nhận. (5) Test đã nghiệm thu `tests/integration/adapt/launch/test_adapt_launch_cli.py`: trong `test_restore_creates_new_database_and_new_recovery_epoch` dòng 548 `assert last_hist["epoch"].startswith("rec-20261022030405-")` đổi thành `assert last_hist["epoch"] == "1"` và sau dòng 557 thêm `assert epoch_data2["history"][-1]["epoch"] == "2"`; nếu `launcher start` thêm trường vào `Deps` thì `make_fx` (dòng 140-159) cung cấp fake ghi sự kiện `begin_session` và `end_session` vào `events`, để mọi test `cmd_start`, `cmd_serve` còn xanh. (6) Test khoá cấu trúc đã nghiệm thu `tests/integration/convergence/test_cp5_completion_uow.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; quy tắc F1 mở rộng): assertion ở dòng 583-585 `assert sorted(p.name for p in ORCH.glob('*.py')) == ['__init__.py', 'allocation.py', 'grants.py', 'postgres_completion.py', 'start_batch.py', 'variants.py']` liệt kê cứng đúng sáu tệp của `src/controlplane/infrastructure/db/orchestration` nên thêm `app_session.py` làm đỏ; đổi đích danh assertion đó thành kiểm tập con: sáu tên cũ là tập con của `{p.name for p in ORCH.glob('*.py')}` (dạng `assert {...sáu tên...} <= {p.name for p in ORCH.glob('*.py')}`), không liệt kê cứng tệp mới, không đổi assertion nào khác của tệp; `PW-G2`, `PW-G4`, `PW-G6`, `PW-A3` chạy tệp này (mỗi slice thêm một tệp vào thư mục đó). `tests/integration/persistence/g/test_persist_g_postgres.py` chỉ chạy ở PW-G1 (PW-G6 sở hữu). `report.md` ghi dòng đã đổi cùng lý do.
    instrument: test trên CSDL tạm: `begin` hai lần còn đúng một phiên ACTIVE; epoch `rec-1-ab` bị từ chối; sau `restore` giả lập epoch tăng đúng 1; spy ghi thứ tự gọi chứng minh `begin` trước `start_worker`; `to_execution_grant` nhận epoch lấy từ `current()` và ra `int`. `test_adapt_launch_cli.py` xanh với epoch `1` rồi `2`.
    counterexample: epoch không phải chuỗi thập phân; hai phiên ACTIVE; `start_worker` chạy trước `begin`; epoch đổi sau khi đổi `active-db`; test launcher đã nghiệm thu vẫn khoá epoch `rec-...`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_g1_app_session.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/orchestration/app_session.py').read_text(encoding='utf-8').lower(); assert 'from src.' not in t and 'fake' not in t and 'mock' not in t, 'PW-G1'"`
- coveredIds: PW-G1-01..06, CT-WF-004

### PW-G2: Ghi cp_stage_runs và bộ ghi kết quả

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/orchestration/stage_runs.py`
  - `src/controlplane/application/orchestration/result_recorder.py`
  - `tests/integration/prod_wiring/test_pw_g2_stage_runs.py`
  - `docs/delivery-evidence/pw-g2/report.md`
- dependsOn: `PW-G1`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql:23-35`; `src/controlplane/application/orchestration/workflows/activities.py:201-237`; `src/controlplane/application/orchestration/workflows/flow.py:255-316`; `src/controlplane/domain/orchestration/job_waiting.py:15-24`; `src/controlplane/domain/orchestration/stage_run_plan.py`
- acceptance:
  - requirement: (1) `PostgresStageRuns(connection, workspace_id)`: `ensure(...)` INSERT idempotent một dòng `PENDING` cho `stage_run_id` dạng `<owner>:<stage>:r<revision>` (owner có trong `cp_video_jobs` thì ghi `job_id`, không thì ghi `workflow_id`); `transition(...)` đi qua state machine StageRun hiện có của G (cạnh cấm ném `ForbiddenTransitionError`, không ghi) và cập nhật `started_at`, `finished_at`, `wait_reason`, `problem`, `execution_generation`. (2) `ResultRecordingDispatcher(inner, connection_factory, clock, listeners=())` bao `ActivityDispatcher.dispatch`: trước handler `ensure` rồi PENDING→RUNNING; sau kết quả ghi theo `disposition`: succeeded→SUCCEEDED, waiting→WAITING_CAPABILITY kèm `WaitReason`, outcome_unknown→OUTCOME_UNKNOWN, stale→STALE, failed có `retryable`→FAILED_RETRYABLE, còn lại FAILED_FINAL; mỗi lần ghi một giao dịch riêng và commit; `ActivityRejected` truyền nguyên vẹn; `listeners` (Protocol `ResultListener.on_result(request, result)`) được gọi sau khi ghi để `PW-G4` gắn trạng thái job. (3) Đồng bộ, chạy trong `to_thread` sẵn có của `_activity_fn`.
    instrument: test trên CSDL tạm: một dòng cho mỗi (stage, revision) sau hai lần `ensure`; mỗi `disposition` ra đúng trạng thái; stage run của workflow không có job ghi được qua `workflow_id`; `FAILED_FINAL`→`RUNNING` bị từ chối và không đổi dòng; `ActivityRejected` ra nguyên mã; listener nhận đúng kết quả.
    counterexample: ghi ngoài giao dịch; nuốt `ActivityRejected`; cạnh cấm vẫn ghi; stage run không job bị từ chối.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_g2_stage_runs.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/controlplane/infrastructure/db/orchestration/stage_runs.py', 'src/controlplane/application/orchestration/result_recorder.py']); assert 'from src.' not in t and 'fake' not in t and 'mock' not in t, 'PW-G2'"`
- coveredIds: PW-G2-01..06, CT-ORC-003, CT-STATE-009

### PW-G3: grant_issuer thật, thu hồi sau kết quả, adapter hiệu lực

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/grant_runtime.py`
  - `src/controlplane/api/wiring/workflow.py`
  - `tests/integration/prod_wiring/test_pw_g3_grants.py`
  - `docs/delivery-evidence/pw-g3/report.md`
- dependsOn: `PW-G2`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/application/orchestration/grant_issuance.py:61-100`; `src/controlplane/infrastructure/db/orchestration/grants.py:39-110`; `src/controlplane/api/wiring/workflow.py:157-164,237-249`; `src/controlplane/application/orchestration/workflows/activities.py:186-198`; `src/controlplane/infrastructure/db/migrations/0011_orchestration_extensions.sql:30`; `docs/09-contracts/03-workflow-and-execution.md:60-84`
- acceptance:
  - requirement: (1) `build_grant_issuer(connection_factory, workspace_id, ttl_by_queue, clock)` trả hàm `(stage_run_id, allowed_operation, input_fingerprint, worker_lease_id) -> GrantClaims`: một giao dịch gồm `PostgresStageRuns.ensure`, `PostgresRecoveryEpoch.current`, `GrantIssuer` với `PostgresGrantStore` cùng một kết nối, commit khi xong. TTL theo hàng đợi, mặc định `control-workflows` 300, `cloud-io` 900, `cloud-ai` 900, `desktop-cpu` 900, `desktop-gpu` 1800, `desktop-render` 3600 giây (GIẢ ĐỊNH D8, OI-PW-05), ghi đè bằng tham số profile nếu có. (2) `GrantRevokingDispatcher(inner, connection_factory, workspace_id)` bao dispatcher của `PW-G2`: sau mỗi kết quả (mọi `disposition`, kể cả khi handler ném lỗi) thu hồi grant của request trong giao dịch riêng, nên hai activity cùng `stage_run_id` chạy lần lượt không vướng `ActiveGrantExistsError` (CT-WF-004). (3) `ExecutionGrantCurrency(connection_factory, workspace_id, clock)` cài `is_grant_current(ExecutionGrant)`: so `operation_id` với `grant_id`, `execution_generation`, `recovery_epoch` hiện hành, `revoked_at` rỗng và `expires_at` lớn hơn now; thay `StoreBackedClaimsCurrency` trong production. (4) `_issue_grant_activity` và `_read_capability_view_activity` của `workflow.py` gọi qua `asyncio.to_thread`.
    instrument: test trên PostgreSQL thật (không dùng `InMemoryGrantStore`): hai activity liên tiếp của một stage đều được cấp grant; grant còn sống sau kết quả bằng 0; grant hết hạn bị `ExecutionGrantCurrency` từ chối; epoch cũ bị từ chối; vòng lặp sự kiện không bị chặn khi PG chậm (kiểm bằng heartbeat).
    counterexample: grant còn sống sau kết quả; PG đồng bộ chạy trên event loop; so `GrantClaims` với `ExecutionGrant`; epoch kiểu `int` lệch kiểu `str`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_g3_grants.py tests/integration/convergence/test_cp6_workflow_catalog.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/grant_runtime.py').read_text(encoding='utf-8').lower(); assert 'grantissuer' in t and 'inmemory' not in t and 'from src.' not in t, 'PW-G3'"`
- coveredIds: PW-G3-01..06, CT-WF-004, INV-003, INV-016

### PW-G4: capability_reader, trạng thái job và batch

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/capability_view.py`
  - `src/controlplane/application/orchestration/job_lifecycle.py`
  - `src/controlplane/infrastructure/db/orchestration/job_states.py`
  - `tests/integration/prod_wiring/test_pw_g4_job_states.py`
  - `docs/delivery-evidence/pw-g4/report.md`
- dependsOn: `PW-G3`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/domain/orchestration/job_waiting.py:26-27,47-78`; `src/controlplane/application/orchestration/workflows/flow.py:221-231`; `src/controlplane/infrastructure/db/migrations/0011_orchestration_extensions.sql` (cột `wait_reason`, `stop_reason`, `stopped_at`); `docs/09-contracts/09-orchestration-contracts.md` (CT-ORC-007, CT-ORC-010)
- acceptance:
  - requirement: (1) `CapabilityReader(probes)` trả `{'desktop_production': {'status': ...}}`: `available` chỉ khi mọi probe tiêm vào (`app_session_active`, `ffmpeg_pinned`, `gpu_lease_ready`) đạt; `degraded` khi thiếu khe GPU nhưng còn CPU; `unavailable` khi ngược lại; probe ném lỗi thì `unknown` (fail-closed, không bao giờ `available`); gọi qua `to_thread`. (2) `JobLifecycleListener` cài `ResultListener` của `PW-G2` và chuyển `cp_video_jobs.status` bằng `plan_job_transition` cùng state machine job: SNAPSHOTTED sau `BuildProductionSnapshot` thành công, ACTIVE khi stage chạy, WAITING kèm `wait_reason` khi `waiting`, READY_FOR_COMPLETION sau `PersistVideoOutput` thành công, FAILED_FINAL khi stage FAILED_FINAL; cạnh ngoài CT-STATE bị từ chối. (3) `BatchLifecycle.finish(batch_id, status, reason)` ghi `cp_production_batches.status`, `stop_reason`, `stopped_at` theo CT-ORC-010 trong một giao dịch, idempotent.
    instrument: test trên CSDL tạm: ba probe đạt cho `available`, một probe lỗi cho `unknown` và workflow chờ; chuỗi trạng thái job đi đúng SNAPSHOTTED→ACTIVE→WAITING→ACTIVE→READY_FOR_COMPLETION; cạnh cấm bị từ chối; `finish` hai lần không đổi dòng.
    counterexample: `unknown` bị coi là `available`; job bỏ qua READY_FOR_COMPLETION; batch không có trạng thái dừng; probe chạy trên event loop.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_g4_job_states.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/capability_view.py').read_text(encoding='utf-8').lower(); assert 'desktop_production' in t and 'fake' not in t and 'from src.' not in t, 'PW-G4'"`
- coveredIds: PW-G4-01..05, CT-ORC-007, CT-ORC-010, CT-WF-007

### PW-CAT1: Thứ tự stage, binding ReserveVariant, pha ValidateVariant

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/orchestration/workflow_catalog.py`
  - `src/controlplane/application/orchestration/workflows/activities.py`
  - `tests/unit/orchestration/test_g_workflow_catalog.py`
  - `tests/integration/convergence/test_cp6_workflow_catalog.py`
  - `tests/integration/convergence/test_cp6_video_production_flow.py`
  - `tests/integration/prod_wiring/test_pw_cat1_catalog.py`
  - `docs/delivery-evidence/pw-cat1/report.md`
- dependsOn: `PW-G4`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`
- bindingRefs: `src/controlplane/domain/orchestration/workflow_catalog.py:98-106`; `src/controlplane/application/orchestration/workflows/activities.py:38-93`; `docs/09-contracts/06-creative-ai-contracts.md:211`; `docs/09-contracts/09-orchestration-contracts.md:78-89`; `docs/09-contracts/03-workflow-and-execution.md` (CT-WF-009)
- acceptance:
  - requirement: (1) `VideoProductionWorkflow` `workflow_version` 2 với đồ thị: `analyze`; `script` sau `analyze`; `media_select` sau `script`; `plan` sau `media_select`; `tts` sau `script`; `align` sau `tts`; `process` sau `plan` và `align`; `render` sau `process`; `qc` sau `render`; `sync` sau `qc`; `complete` sau `sync`. (2) `VIDEO_STAGE_ACTIVITIES`: `plan` = `BuildProductionPlan`, `ValidateVariant`, `ReserveVariant`, `GenerateOutputMetadata`; `render` thêm `reconcile_render` trước `render_video`; `qc` = `inspect_output`, `ValidateVariant`, `prepare_output_ready`; `process` thêm `TransformSensitiveImage` sau `AssessImageSafety`. Binding mới: `ReserveVariant` (G, stage `plan`), `reconcile_render` và `prepare_output_ready` (F); `GenerateOutputMetadata` chuyển sang stage `plan`; `ValidateVariant` là activity duy nhất chạy ở hai stage: `ActivityBinding` (dataclass trong `src/controlplane/application/orchestration/workflows/activities.py`) thêm trường cuối cùng `extra_stage_types: tuple[str, ...] = ()` (có giá trị mặc định, đặt sau `side_effect`), binding `ValidateVariant` có `stage_type` = `plan` và `extra_stage_types` = `('qc',)`, mọi binding khác có `extra_stage_types` rỗng; hàng đợi của `ValidateVariant` ở cả hai stage là `binding.queue`, tính một lần trong `_b` bằng `route_stage('plan')` (`TaskQueue.DESKTOP_CPU`); không đổi hàng đợi theo stage đang chạy, vì `definitions.py:84` (`BINDINGS_BY_NAME[name].queue`), `flow.py:277` (`binding.queue.value`) và `workflow.py:235` (`binding.queue.value` khi đăng ký activity) đều đọc `binding.queue` và nằm ngoài ownedPaths của PW-CAT1; pha của lần chạy lấy từ `stage_run_id` (plan hoặc output) như PW-D2. (3) Bảng hằng `FAN_OUT_FROM_OUTPUT` trong `activities.py`: activity → (stage trước, `ref_type`) cho `AssessImageSafety`, `ProbeMedia`, `NormalizeMedia` (từ `media_select`, `selected_media`) và `CollectSource` (từ `select_sources`, `collection_source`). (4) `is_breaking_change` v1→v2 là True; `validate_catalog` vẫn xanh; sửa các test catalog và test flow cp6 theo thứ tự mới. (5) Được sửa đích danh một assertion của test đã nghiệm thu `tests/integration/convergence/test_cp6_workflow_catalog.py::test_bindings_follow_the_catalog`: neo bằng `rg -n "binding.stage_type == stage_name" tests` (hiện ở dòng 158, trong vòng lặp `for name in activity_names`, dưới điều kiện `if wf_name != 'DebugStageWorkflow'`), thay `assert binding.stage_type == stage_name` bằng `assert stage_name in (binding.stage_type, *binding.extra_stage_types)` (giữ nguyên điều kiện `if wf_name != 'DebugStageWorkflow'`), và thêm hai assertion chặt ở mức thụt lề của thân hàm, ngay sau cả hai vòng lặp `for wf_name`/`for stage_name` và trước dòng `video_spec = get_workflow('VideoProductionWorkflow')`: `assert {b.name for b in ACTIVITY_BINDINGS if b.extra_stage_types} == {'ValidateVariant'}` và `assert BINDINGS_BY_NAME['ValidateVariant'].extra_stage_types == ('qc',)`. Ngoại lệ được liệt kê đóng, không nới oracle: không sửa assertion nào khác của tệp đó ngoài các assertion khoá thứ tự stage cũ (hiện chỉ có dòng 158 nêu trên); `report.md` của PW-CAT1 ghi dòng đã đổi kèm lý do.
    instrument: test catalog: thứ tự và phụ thuộc đúng; `ReserveVariant` đứng trước `render`; mỗi activity của `STAGE_ACTIVITIES_BY_WORKFLOW` khớp `BINDINGS_BY_NAME` theo `stage_type` hoặc `extra_stage_types`; chỉ `ValidateVariant` có `extra_stage_types` và đúng `('qc',)`; hàng đợi của binding `ValidateVariant` bằng `route_stage('plan')` và `binding.queue == route_stage(binding.stage_type)` vẫn đúng cho mọi binding, không có nhánh đổi hàng đợi theo stage `qc`; version 2.
    counterexample: `plan` trước `media_select`; `ValidateVariant` chỉ ở `qc`; `ReserveVariant` sau render; quên tăng version; activity khác ngoài `ValidateVariant` xuất hiện ở stage không phải `stage_type` của nó; nới assertion của `test_bindings_follow_the_catalog` ngoài ngoại lệ đóng; đòi hàng đợi riêng ở `qc` cho `ValidateVariant` (phải sửa `definitions.py`, `flow.py`, `workflow.py` ngoài ownedPaths) thay vì `binding.queue` = `route_stage('plan')`. `test_pw_cat1_catalog.py` có test bắt các phản ví dụ này: một test đặt một activity khác (không phải `ValidateVariant`) vào stage không phải `stage_type` của nó rồi khẳng định kiểm khớp binding báo đỏ; một test khẳng định tập binding có `extra_stage_types` đúng bằng `{'ValidateVariant'}` và giá trị đúng `('qc',)`; một test khẳng định `BINDINGS_BY_NAME['ValidateVariant'].queue == route_stage('plan')`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py tests/integration/prod_wiring/test_pw_cat1_catalog.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('src/controlplane/domain/orchestration/workflow_catalog.py').read_text(encoding='utf-8'); assert re.search('VideoProductionWorkflow.{1,3}2,', t) and re.search('media_select.{1,8}script.{1,40}plan.{1,8}media_select', t, re.S), 'PW-CAT1'"`
- coveredIds: PW-CAT1-01..05, CT-WF-009, CT-ORC-012, CT-AI-008

### PW-CAT2: flow.py xử lý waiting, RetryStage và fan-out

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/workflows/flow.py`
  - `src/controlplane/application/orchestration/workflows/definitions.py`
  - `tests/integration/prod_wiring/test_pw_cat2_flow.py`
  - `tests/integration/convergence/test_cp6_video_production_flow.py`
  - `docs/delivery-evidence/pw-cat2/report.md`
- dependsOn: `PW-CAT1`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`
- bindingRefs: `src/controlplane/application/orchestration/workflows/flow.py:153-164,182-253,297-316`; `src/controlplane/application/orchestration/workflows/definitions.py:105-138`; `src/controlplane/domain/orchestration/job_waiting.py:15-24`; `docs/09-contracts/03-workflow-and-execution.md:117` (CT-WF-006, CT-WF-007)
- acceptance:
  - requirement: (1) Disposition `waiting` trong `_run_activity` không còn là thất bại: `StageGraphFlow` đặt `status=WAITING_CAPABILITY`, `waiting_stage` là stage đang chạy, `wait_reason` lấy từ `problem.code` nếu thuộc `WaitReason` (gồm `credential_unavailable`, `quota_wait`, `artifact_not_ready`, `insufficient_disk`, `provider_unavailable`, `local_ai_unavailable`, `desktop_offline`), mã lạ thì `dependency_wait`; `_drive` chờ `capability_poll_seconds` hoặc signal (`workflow.wait_condition` có timeout) rồi `advance()` đánh giá lại đúng stage đó, không chạy lại stage đã xong; áp cho mọi stage. (2) `RetryStage`: ghi nhận activity đã thành công theo `(stage, activity, index, revision)` và bỏ qua khi chạy lại; `_prior_refs` không đưa output chưa hoàn tất của chính stage vào `input_refs` của activity đã chạy; RETRY không xoá output đã nhận, nên không còn `OPERATION_KEY_CONFLICT`. (3) Fan-out: khi payload không có `item_refs` cho activity, lấy danh sách item từ `output_refs` của stage trước theo `FAN_OUT_FROM_OUTPUT`; mỗi item một lần chạy với `index` riêng; payload có `item_refs` thì giữ nguyên. (4) Mã trong workflow vẫn xác định (không I/O, không đồng hồ). (5) Test đã nghiệm thu `tests/integration/convergence/test_cp6_video_production_flow.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó): chỉ đổi assertion nào đỏ vì `waiting`, `RetryStage` hay fan-out theo (1)-(3), không xoá test; ghi từng dòng đã đổi cùng lý do vào `report.md`.
    instrument: test trên server test của temporalio và PostgreSQL thử: activity trả `waiting` thì stage chờ rồi chạy tiếp ở đúng stage, số attempt của stage trước không tăng; stage có hai activity, activity thứ hai fail rồi `RetryStage` chỉ chạy lại activity thứ hai và `operation_key` activity thứ nhất không lặp; fan-out ba ảnh sinh ba lần chạy.
    counterexample: `waiting` coi là FAILED; RETRY chạy lại activity đã thành công; fan-out từ payload cố định; chờ bằng `time.sleep` hay đồng hồ thật.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_cat2_flow.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/workflows/flow.py').read_text(encoding='utf-8'); assert 'waiting' in t and 'time.sleep' not in t and 'datetime.now' not in t, 'PW-CAT2'"`
- coveredIds: PW-CAT2-01..06, CT-WF-006, CT-WF-007, CT-ORC-007

### PW-G5: Cấp job, ứng viên và vòng lô

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/batch_allocation.py`
  - `src/controlplane/infrastructure/db/orchestration/allocation.py`
  - `src/controlplane/application/orchestration/workflows/batch.py`
  - `src/controlplane/application/orchestration/workflows/definitions.py`
  - `src/controlplane/application/orchestration/workflows/activities.py`
  - `src/controlplane/domain/orchestration/allocation_policy.py`
  - `tests/integration/prod_wiring/test_pw_g5_allocation.py`
  - `tests/integration/convergence/test_cp6_video_production_flow.py`
  - `docs/delivery-evidence/pw-g5/report.md`
- dependsOn: `PW-CAT2`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/application/orchestration/job_allocation.py:41-60`; `src/controlplane/infrastructure/db/orchestration/allocation.py:17`; `src/controlplane/domain/orchestration/allocation_policy.py:24`; `src/controlplane/application/orchestration/workflows/batch.py:55-137`; `src/controlplane/application/orchestration/workflows/activities.py:108-111`
- acceptance:
  - requirement: (1) Binding nội bộ `AllocateJob` (G, stage `allocate`, queue `control-workflows`) và `FinalizeBatch` (stage `run_videos`); `BATCH_STAGE_ACTIVITIES` đổi từ rỗng thành hai activity đó. (2) Handler `AllocateJob`: `CandidateSelectorPort.next_candidate(batch_id, production_mode)` (hiện thực production ở `PW-B1`) → `JobAllocationService.allocate` với `job_id` xác định theo `(batch_id, thứ tự)` để retry không tạo job đôi → lưu `cp_job_candidates` (`PostgresAllocationStore.create_job_and_reservation` ghi `candidate_ref`); `BatchTargetReachedError` hoặc hết ứng viên trả kết quả `no_more_jobs`. (3) `ProductionBatchFlow.run` không còn dựa vào `payload['jobs']` dựng sẵn (vẫn nhận nếu có): mỗi vòng cấp grant, gọi `AllocateJob`, dựng payload video (`video_job_id`, `input_fingerprint` là sha256 của `candidate_ref` và `source_set_ref`, `worker_lease_id`, `input_refs`), chạy child workflow; hết vòng gọi `FinalizeBatch` (`BatchLifecycle.finish` của `PW-G4`) với TARGET_REACHED hoặc EXHAUSTED. (4) Khi `payload['jobs']` có phần tử thì vòng chỉ dùng danh sách đó (không gọi `AllocateJob`, không cấp grant) nhưng vẫn gọi `FinalizeBatch` cuối vòng. (5) Test đã nghiệm thu `tests/integration/convergence/test_cp6_video_production_flow.py`: `test_batch_isolation` (dòng 589-639) dùng `FakeBatchGateway` (dòng 590-601) chỉ có `run_child` và payload `jobs`; mở rộng lớp này đúng các phương thức mới mà `BatchGateway` (`workflows/batch.py:99,116`) đòi để chạy `FinalizeBatch` (trả kết quả tất định, ghi lời gọi), giữ nguyên mọi assertion `BATCH_TARGET_REACHED`, `completed == 1`, `failed == 1`, `BATCH_EXHAUSTED` và lời gọi `DebugStageWorkflow`. `tests/integration/convergence/test_cp6_workflow_catalog.py` chỉ chạy, không sửa: hai binding mới phải thoả `binding.stage_type == stage_name` và `binding.queue == route_stage(stage_type)`. (6) `AllocationCandidate` (dataclass frozen ở dòng 23-26 của `src/controlplane/domain/orchestration/allocation_policy.py`, hiện chỉ có `candidate_ref` và `angle_slot`) thêm trường cuối `source_set_ref: str | None = None` (có mặc định, đặt sau `angle_slot`) vì `PW-B1` trả `source_set_ref` do `build_source_set` dựng và `PostgresAllocationStore.create_job_and_reservation` lưu nó vào `cp_job_candidates.source_set_ref`; các lời gọi hai tham số vị trí `AllocationCandidate('cand-1', 'angle-1')` trong `tests/integration/persistence/g/test_persist_g_postgres.py`, `tests/unit/orchestration/test_g_allocation_policy.py` và `tests/unit/orchestration/test_g_job_allocation.py` phải chạy được không cần sửa test. Chỉ thêm trường, không đổi `plan_round` hay logic khác.
    instrument: test trên PostgreSQL thật và server test của temporalio, selector giả trong test: batch target 2 cấp đúng 2 job, `cp_job_candidates` có hai dòng, batch ghi trạng thái dừng; retry `AllocateJob` cùng `job_id` trả reservation cũ; hết ứng viên trước target cho EXHAUSTED. `test_batch_isolation` vẫn xanh và `test_cp6_workflow_catalog.py` xanh.
    counterexample: job đôi khi retry; `candidate_ref` không lưu; batch không bao giờ dừng; vượt target; `FakeBatchGateway` cũ làm test đã nghiệm thu đỏ.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_g5_allocation.py tests/integration/convergence/test_cp6_video_production_flow.py tests/integration/convergence/test_cp6_workflow_catalog.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/batch_allocation.py').read_text(encoding='utf-8').lower(); assert 'allocatejob' in t and 'fake' not in t and 'from src.' not in t, 'PW-G5'"`
- coveredIds: PW-G5-01..05, CT-ORC-002, CT-ORC-010, INV-018

### PW-G6: Outbox relay trong tiến trình worker

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/orchestration/outbox_relay.py`
  - `tests/integration/prod_wiring/test_pw_g6_outbox_relay.py`
  - `tests/integration/persistence/g/test_persist_g_postgres.py`
  - `docs/delivery-evidence/pw-g6/report.md`
- dependsOn: `PW-G5`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/infrastructure/db/outbox/postgres.py:42-60`; `src/controlplane/application/control_api/commands.py:80-132`; `src/controlplane/application/orchestration/workflows/settings.py`; `docs/08-architecture.md` §8.3 (dòng 166, 178)
- acceptance:
  - requirement: `OutboxRelay(connection_factory, temporal_client, workspace_id, settings, clock)`. (1) `run_once()`: trong một giao dịch chọn `cp_outbox_events` có `published=false` và `event_name='production_batch.start_accepted'` theo `recorded_at` với `FOR UPDATE SKIP LOCKED`; với mỗi sự kiện gọi `client.start_workflow('ProductionBatchWorkflow', payload, id=batch_id, task_queue='control-workflows', id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)` với payload `batch_id`, `target_videos` (từ `target_count`), `jobs=[]`, `settings` đúng định dạng `WorkflowSettings.from_payload`, `worker_lease_id` là phiên AppSession ACTIVE; `WorkflowAlreadyStartedError` được coi là thành công; chỉ sau khi khởi mới `UPDATE published=true, published_at` rồi commit; lỗi khởi thì rollback, giữ `published=false` để lần sau thử lại. (2) Sự kiện khác tên bị bỏ qua, không ack. (3) `run_forever(stop_event, interval_seconds)` chạy trong tiến trình worker và dừng êm khi `launcher stop`; PG đồng bộ chạy qua `to_thread`. Không dùng `PostgresOutboxPublisher` stub. (4) Test khoá cấu trúc đã nghiệm thu `tests/integration/persistence/g/test_persist_g_postgres.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; quy tắc F1 mở rộng): `BANNED_ADAPTER_TOKENS` (dòng 44-49) cấm `.commit(`, `.rollback(`, `connect(` và các token khác trong mọi tệp của `src/controlplane/infrastructure/db/orchestration` trừ `postgres_completion.py` (`EXT_COMPLETION_ADAPTER`, dòng 43; vòng `for banned in BANNED_ADAPTER_TOKENS` ở dòng 701-710), mà `outbox_relay.py` phải tự commit và rollback. Chỉ được: thêm hằng `EXT_RELAY_ADAPTER = 'outbox_relay.py'` cùng tập miễn trừ đóng `EXT_RELAY_ALLOWED_TOKENS = ('.commit(', '.rollback(')`; sửa hàm quét để tệp đó chỉ được miễn đúng hai token này (mọi token khác của `BANNED_ADAPTER_TOKENS`, gồm `connect(`, `TransactionManager`, `CREATE TABLE`, `from src.`, vẫn bị báo ở `outbox_relay.py`; `postgres_completion.py` giữ nguyên miễn cả tệp); thêm test mới, không xoá test cũ: `outbox_relay.py` chứa `.commit(` và `.rollback(` thì không bị báo, chứa `connect(` hoặc `TransactionManager` thì vẫn bị báo, còn `.commit(` trong tệp khác (`grants.py`, `collection_scheduler.py` của PW-A3) vẫn bị báo. Không nới token khác, không miễn tệp nào khác. `PW-G1`, `PW-G2`, `PW-G4`, `PW-A3` chạy tệp này; PW-G6 cũng chạy `tests/integration/convergence/test_cp5_completion_uow.py` (PW-G1 sở hữu). `report.md` ghi dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật và server test của temporalio: `start_batch` rồi `run_once` khởi đúng một workflow id = `batch_id`; hai relay song song (hai kết nối) chỉ một khởi, workflow chỉ chạy một lần; client ném lỗi giữa chừng thì sự kiện còn `published=false` và lần sau khởi được; `WorkflowAlreadyStarted` thì vẫn ack; sự kiện khác tên giữ nguyên.
    counterexample: ack trước khi khởi; hai workflow cho một batch; mất sự kiện khi lỗi khởi; dùng stub publisher.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_g6_outbox_relay.py tests/integration/persistence/g/test_persist_g_postgres.py tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/orchestration/outbox_relay.py').read_text(encoding='utf-8'); assert 'SKIP LOCKED' in t and 'REJECT_DUPLICATE' in t and 'from src.' not in t, 'PW-G6'"`
- coveredIds: PW-G6-01..05, ARCH-009, CT-WF-001

### PW-G7: Completion với fencing thật và ReserveVariant

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/completion_assembler.py`
  - `src/controlplane/application/orchestration/variant_handlers.py`
  - `tests/integration/prod_wiring/test_pw_g7_completion.py`
  - `docs/delivery-evidence/pw-g7/report.md`
- dependsOn: `PW-G6`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/application/orchestration/commit_completion.py:35-130`; `src/controlplane/infrastructure/db/orchestration/postgres_completion.py:106`; `src/controlplane/application/orchestration/variant_reservation_flow.py:89`; `src/controlplane/api/wiring/completion.py:20`; `docs/09-contracts/09-orchestration-contracts.md:78-92`
- acceptance:
  - requirement: (1) `CompletionAssembler` dựng `CompletionContext` từ dữ liệu thật: grant hiện hành, `execution_generation` và epoch đọc từ `PostgresGrantStore` và `PostgresRecoveryEpoch` (không `InMemory`), `variant_reservation_id` từ reservation ACTIVE của job, artifact version của mp4 và location đã VERIFIED, tham chiếu báo cáo QC và validation pha `output`. (2) `reserve_variant_handler` bọc `VariantReservationFlow` thành handler của `ReserveVariant`: cùng key và input trả receipt cũ, input khác ra `VARIANT_CONFLICT`, registry đổi ra `VARIANT_VALIDATION_STALE` (disposition `waiting`, không tạo reservation). (3) `commit_video_completion_handler` bọc `CommitVideoCompletion` qua `PostgresCompletionUnitOfWork`: thành công thì ledger một dòng, job COMPLETED, reservation CONVERTED trong cùng giao dịch; stale thì không ghi ledger; `VARIANT_CONFLICT` thì job FAILED_FINAL và release reservation.
    instrument: test trên PostgreSQL thật: completion đúng ghi một ledger và đổi job, reservation; chạy lại cùng request không ghi đôi; grant epoch cũ bị từ chối; revision registry lệch thì không ghi gì; reserve retry cùng key trả receipt cũ.
    counterexample: ledger ghi khi location chưa VERIFIED; fencing đọc từ bộ nhớ; hai ledger cho một job; reserve sau render.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_g7_completion.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/controlplane/application/orchestration/completion_assembler.py', 'src/controlplane/application/orchestration/variant_handlers.py']); assert 'inmemory' not in t and 'fake' not in t and 'from src.' not in t, 'PW-G7'"`
- coveredIds: PW-G7-01..05, CT-ORC-012, CT-AI-008, INV-003

### PW-VERT: Khung dọc, một video đi hết VideoProductionWorkflow

- kind: work_package_slice
- ownedPaths:
  - `tests/integration/prod_wiring/pw_vertical.py`
  - `tests/integration/prod_wiring/test_pw_vert_video_flow.py`
  - `docs/delivery-evidence/pw-vert/report.md`
- dependsOn: `PW-G7`
- resourceLocks: `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/application/orchestration/workflows/definitions.py:141-228`; `src/controlplane/api/wiring/workflow.py:175-270`; `tests/m1/p2/conftest.py:1-20`; `tests/integration/prod_wiring/pw_support.py` (PW-H0)
- acceptance:
  - requirement: `pw_vertical.py` ráp thành phần G thật (AppSession, `ResultRecordingDispatcher`, `GrantRevokingDispatcher`, `grant_issuer`, `CapabilityReader`, `OutboxRelay`, `AllocateJob`, `ReserveVariant`, `CommitVideoCompletion`) vào `build_workflow_services` và `build_temporal_registration`; handler của D, E, F, I là adapter giả trong test, mỗi handler chỉ ghi dữ kiện tối thiểu vào bảng thật mà completion đòi (selection, artifact version, location VERIFIED, báo cáo QC). Test chạy trên server test của temporalio và PostgreSQL thử: (1) một lô 1 video khởi bằng `start_batch` và relay đi hết 11 stage tới COMPLETED; (2) mỗi `cp_stage_runs` của video SUCCEEDED, mỗi activity một grant và không grant nào còn sống; job đi SNAPSHOTTED, ACTIVE, READY_FOR_COMPLETION, COMPLETED; batch TARGET_REACHED; ledger đúng một dòng; (3) capability `unavailable` thì job WAITING rồi chạy tiếp khi `available`, không stage nào chạy lại; (4) `RetryStage` sau khi activity thứ hai của một stage fail chỉ chạy lại activity đó; (5) dừng rồi dựng worker mới trên cùng CSDL giữa hai stage thì stage đã xong không chạy lại.
    instrument: `test_pw_vert_video_flow.py` đếm `attempt`, grant còn sống, trạng thái job, batch, ledger; kiểm không có `InMemory` của G trong assembly bằng quét AST `pw_vertical.py` phần G.
    counterexample: `InMemoryGrantStore`; stage hai activity vướng `ActiveGrantExistsError`; relay khởi workflow hai lần; epoch dạng `rec-...`; handler G là fake.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_vert_video_flow.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('tests/integration/prod_wiring/pw_vertical.py').read_text(encoding='utf-8'); assert 'InMemoryGrantStore' not in t and 'OutboxRelay' in t and 'GrantRevokingDispatcher' in t, 'PW-VERT'"`
- coveredIds: PW-VERT-01..05, CT-WF-004, CT-WF-007, CT-ORC-010

### PW-D1: Vai trò AI khớp profile và sáu prompt mặc định

- kind: work_package_slice
- ownedPaths:
  - `src/creative/application/roles.py`
  - `src/creative/application/prompts.py`
  - `src/creative/application/pipeline.py`
  - `src/creative/adapters/prompt_source.py`
  - `tests/integration/prod_wiring/test_pw_d1_roles_prompts.py`
  - `tests/integration/creative/test_d14_creative_pipeline.py`
  - `tests/integration/creative/test_d16_worker_activity.py`
  - `docs/delivery-evidence/pw-d1/report.md`
- dependsOn: `PW-VERT`
- resourceLocks: `LOCK-SRC-CREATIVE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/creative/application/pipeline.py:207-239`; `src/controlplane/infrastructure/production_ports/route_catalog.py:38-40`; `tools/launcher/prod/profile.json:122-130`; `src/controlplane/api/wiring/production_profile.py:277`; `src/controlplane/application/control_api/commands.py:134`; `docs/01-product-spec.md:295` (FR-CFG-007)
- acceptance:
  - requirement: (1) `route_key(role)` trong `roles.py` là điểm duy nhất dịch sáu vai trò pipeline (`content_analysis`, `story_angles`, `script_generation`, `asset_selection`, `production_plan`, `output_metadata`) sang khoá `analysis`, `angle`, `script`, `selection`, `selection`, `metadata`; `pipeline.py` gọi nó khi tạo yêu cầu route; vai trò lạ ném lỗi. (2) `prompts.py` có sáu prompt mặc định bằng tiếng Anh, chỉ chứa chỉ dẫn (không chèn nội dung bài), giữ biên instruction–data của `PromptEnvelope`; `seed_default_prompts(config_service)` publish `ConfigRevision(scope_kind='prompt', scope_key=<vai trò>)` nếu chưa có (idempotent); `BuildProductionSnapshot` ghim revision prompt vào snapshot (`pipeline.py` khoảng :207-239). (3) Sửa prompt qua lệnh cấu hình của Control API (`put_config`, `scope_kind='prompt'`) tạo revision mới; snapshot mới ghim revision mới, snapshot cũ giữ revision cũ. (4) Test đã nghiệm thu `tests/integration/creative/test_d14_creative_pipeline.py` và `tests/integration/creative/test_d16_worker_activity.py` (thuộc `ownedPaths`, lệnh kiểm chạy chúng) khoá `ai_role` cũ: khi `route_key(role)` thay `ai_role` làm khoá route thì `FakeAIAdapter` ném `NoScriptedResponse` và `calls_by_role` lệch (finding MAJOR F1 của Auditor rủi ro job impl-prod-wiring-v3; lệnh tìm `rg -n "AI_ROLES|calls_by_role|'content_analysis'" tests/integration/creative`). Chỉ đổi đích danh: ở `test_d14_creative_pipeline.py` hàm `_responses` (dòng 186-190, khoá phản hồi) và hai assertion `calls_by_role` (dòng 313 và 463); ở `test_d16_worker_activity.py` khoá phản hồi (dòng 133) và assertion `calls_by_role` (dòng 308); khoá phản hồi và `calls_by_role` đổi sang khoá route (`analysis`, `angle`, `script`, `selection`, `metadata`). Vì `asset_selection` và `production_plan` cùng ra khoá `selection` nên `calls_by_role['selection']` bằng 2 và hai phản hồi được phân biệt bằng lớp bọc cục bộ trong tệp test (không sửa `src/creative/adapters/fake_ai.py`, ngoài ownedPaths). Các tham chiếu revision prompt theo vai trò pipeline (`content_analysis-r1` ở dòng 337, 421, 443, 447) giữ nguyên. Không xoá test, không nới oracle nào khác; `report.md` ghi từng dòng đã đổi cùng lý do. `tests/unit/creative/test_d01_package_layout.py` chỉ chạy ở PW-D1 (PW-D3 sở hữu).
    instrument: test trên PostgreSQL thật với `ProfileRouteCatalog` thật và `profile.json` thật: sáu vai trò đều ra route (trước đây `candidates()` rỗng); seed hai lần còn một revision mỗi vai trò; sửa prompt qua `put_config` thì snapshot sau ghim revision mới, snapshot trước không đổi; quét prompt mặc định không chứa placeholder nội dung bài.
    counterexample: vai trò không khớp profile nên `candidates()` rỗng; prompt đặt trong mã không qua `ConfigRevision`; snapshot không ghim prompt; nội dung bài trộn vào instruction.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/creative/application/roles.py').read_text(encoding='utf-8'); assert all(k in t for k in ['analysis', 'angle', 'script', 'selection', 'metadata']) and 'from src.' not in t, 'PW-D1'"`
- coveredIds: PW-D1-01..05, FR-CFG-007, CT-AI-ROUTE-001, CT-SEC-002

### PW-D2: Ngữ cảnh cho mô hình, lưu selection và ActivityInputPort D

- kind: work_package_slice
- ownedPaths:
  - `src/creative/adapters/article_context.py`
  - `src/creative/adapters/postgres_selection.py`
  - `src/creative/adapters/activity_inputs.py`
  - `src/creative/application/pipeline.py`
  - `tests/integration/prod_wiring/test_pw_d2_context_selection.py`
  - `tests/integration/creative/test_d14_creative_pipeline.py`
  - `tests/integration/creative/test_d16_worker_activity.py`
  - `docs/delivery-evidence/pw-d2/report.md`
- dependsOn: `PW-D1`
- resourceLocks: `LOCK-SRC-CREATIVE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/creative/application/pipeline.py:207-239,502-537`; `src/creative/worker/activity_handler.py`; `src/creative/adapters/real_ai_invocation.py`; `src/controlplane/infrastructure/db/migrations/0019_prod_wiring.sql` (`cp_creative_selections`); `docs/09-contracts/06-creative-ai-contracts.md:145-185,211`
- acceptance:
  - requirement: (1) `ArticleContextPort` đọc nội dung bài đã chuẩn hoá từ `cp_articles` và `cp_article_revisions` theo source set của snapshot; kết quả vào khối dữ liệu của `PromptEnvelope`, không vào chỉ dẫn. (2) Kết quả stage trước (phân tích, góc kể, script, selection, plan) đọc theo `input_refs` và đưa vào khối dữ liệu của lời gọi kế tiếp; `_invoke` không còn chỉ gửi ID. (3) `SelectionStore` lưu `CreativeAssetSelection` vào `cp_creative_selections` (idempotent theo job và revision, kèm `content_sha256`); `BuildProductionPlan` đọc selection từ bảng, không từ bộ nhớ; `SelectCreativeAssets` trả một `output_ref` kiểu `selected_media` cho mỗi ảnh được chọn (đầu vào fan-out của `PW-CAT2`). (4) `ActivityInputPort` D production phân giải `input_refs` thành đầu vào có kiểu cho `BuildProductionSnapshot`, `AnalyzeContent`, `GenerateStoryAngles`, `GenerateScript`, `SelectCreativeAssets`, `BuildProductionPlan`, `ValidateVariant` (pha lấy từ tên stage trong `stage_run_id`: `plan` hoặc `output`) và `GenerateOutputMetadata`. (5) Test đã nghiệm thu `tests/integration/creative/test_d14_creative_pipeline.py` và `tests/integration/creative/test_d16_worker_activity.py` (thuộc `ownedPaths`, lệnh kiểm chạy chúng) vì D2 cũng sửa `pipeline.py` (`_invoke` gửi khối dữ liệu thay vì chỉ ID) và `route_key(role)` của PW-D1 đã thay `ai_role` cũ làm khoá route (finding MAJOR F1 của Auditor rủi ro job impl-prod-wiring-v3): khoá phản hồi của `FakeAIAdapter` và `calls_by_role` đã được PW-D1 đổi theo khoá route, D2 phải giữ chúng xanh (không đảo lại); D2 chỉ được đổi thêm đích danh các assertion về nội dung yêu cầu gửi tới route (`SpyRoute.requests`) và payload lời gọi AI mà đỏ vì khối dữ liệu mới (vị trí tìm: `rg -n "requests|payload" tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py`). Không xoá test, không nới oracle nào khác; `report.md` ghi từng dòng đã đổi cùng lý do. `tests/unit/creative/test_d01_package_layout.py` chỉ chạy ở PW-D2 (PW-D3 sở hữu).
    instrument: test trên PostgreSQL thật, `FakeRouter` ghi lại yêu cầu: yêu cầu gửi đi chứa nội dung bài và kết quả stage trước trong khối dữ liệu, không trong chỉ dẫn; selection còn sau khi dựng lại bộ nhớ; plan đọc đúng selection từ bảng; `ValidateVariant` đúng pha theo stage; retry cùng input trả cùng selection.
    counterexample: selection chỉ ở bộ nhớ; mô hình không nhận nội dung bài; pha `ValidateVariant` mặc định cứng; nội dung bài lọt vào chỉ dẫn.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/creative/adapters/postgres_selection.py').read_text(encoding='utf-8').lower(); assert 'cp_creative_selections' in t and 'memory' not in t and 'from src.' not in t, 'PW-D2'"`
- coveredIds: PW-D2-01..05, CT-AI-008, CT-AI-009

### PW-D3: Nguồn ứng viên media, hook, thumbnail từ DB

- kind: work_package_slice
- ownedPaths:
  - `src/creative/adapters/media_candidates.py`
  - `src/creative/adapters/hook_candidates.py`
  - `src/creative/adapters/thumbnail_candidates.py`
  - `tests/integration/prod_wiring/test_pw_d3_candidates.py`
  - `tests/unit/creative/test_d01_package_layout.py`
  - `docs/delivery-evidence/pw-d3/report.md`
- dependsOn: `PW-D2`
- resourceLocks: `LOCK-SRC-CREATIVE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/catalog/application/candidate_query.py`; `src/catalog/application/discovery.py:52`; `tools/launcher/prod/hooks.json`; `docs/implementation/adapt/plan.md:274,321`; `docs/00-project-charter.md:155`; `docs/09-contracts/05-content-media-contracts.md` (CT-MED-006)
- acceptance:
  - requirement: (1) `PostgresMediaCandidates`, `PostgresHookCandidates`, `ThumbnailCandidates` cài các port ứng viên của `SelectCreativeAssets`, đọc từ bảng của C qua `candidate_query.py` (không viết SQL vào bảng của C): media seed `bg-01..12`, hook hình `vh-01..05`, hook tiếng `ah-01..05`, ảnh tải kèm bài. (2) Ảnh tải kèm bài (OI-ADAPT-10) được đưa vào danh sách ứng viên kèm provenance (URL nguồn, bài, sha256, thời điểm tải) và cờ `needs_image_safety`; không còn loại ảnh theo `UNVERIFIED`. (3) Thumbnail theo CT-MED-006: ứng viên là khung hình hợp lệ từ hook hoặc ảnh đã chọn, kèm lý do. (4) Selection luôn có ít nhất một media seed dự phòng để chuỗi chạy khi ảnh bài bị loại sau `AssessImageSafety`. (5) Test khoá cấu trúc đã nghiệm thu `tests/unit/creative/test_d01_package_layout.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; PW-D1, PW-D2 chạy tệp này; quy tắc F1 mở rộng): `FORBIDDEN_IMPORT_PREFIXES` (dòng 15-19) cấm `catalog`, mà `PostgresMediaCandidates` và `PostgresHookCandidates` đọc bảng của C qua `src/catalog/application/candidate_query.py` nên phải import `catalog.application.candidate_query` (dạng `from catalog.application.candidate_query import ...`). Chỉ được: thêm vào `ADAPTER_IMPORT_EXEMPTIONS` (dòng 25-27) đúng hai khoá đường dẫn chính xác `src/creative/adapters/media_candidates.py` và `src/creative/adapters/hook_candidates.py`, mỗi khoá `frozenset({'catalog.application.candidate_query'})` (tiền lệ `tests/unit/collection/test_a01_package_layout.py:23-27`); sửa assertion tập miễn trừ ở `AdapterExemptionTests.test_exemption_table_is_exact_paths_only` (dòng 134-136) cho khớp bảng ba khoá; thêm test mới (không xoá test cũ) rằng hai adapter đó chỉ được import đúng mô-đun trên và mọi mô-đun cấm khác (`voice`, `psycopg`, `catalog.domain`) vẫn bị báo. Không đổi `FORBIDDEN_IMPORT_PREFIXES`, không miễn cả thư mục `adapters`, không miễn cả gói `catalog`, không miễn tệp nào khác. `report.md` ghi dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật với seed `hooks.json` và ảnh bài đăng ký bằng `register_discovery`: ảnh bài xuất hiện trong ứng viên kèm provenance; ảnh bài không có provenance bị loại; selection có media seed dự phòng; thumbnail có lý do.
    counterexample: ảnh bài bị loại vì UNVERIFIED (trái quyết định user); ảnh không provenance vào video; viết SQL trực tiếp vào bảng của C; không có media dự phòng.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_d3_candidates.py tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/creative/adapters/media_candidates.py', 'src/creative/adapters/hook_candidates.py', 'src/creative/adapters/thumbnail_candidates.py']); assert 'needs_image_safety' in t and 'fake' not in t and 'from src.' not in t, 'PW-D3'"`
- coveredIds: PW-D3-01..04, OI-ADAPT-10, CT-MED-006

### PW-E1: Lưu bền mọi kind của VoicePipeline và MediaPipeline

- kind: work_package_slice
- ownedPaths:
  - `src/voice/persistence/output_repository.py`
  - `src/voice/persistence/unit_of_work.py`
  - `tests/integration/prod_wiring/test_pw_e1_persistence.py`
  - `tests/integration/persistence/e/test_persist_e_postgres.py`
  - `docs/delivery-evidence/pw-e1/report.md`
- dependsOn: `PW-VERT`
- resourceLocks: `LOCK-SRC-VOICE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/voice/persistence/output_repository.py:17,24-29`; `src/voice/application/voice_pipeline.py:183`; `src/voice/application/media_pipeline.py:301`; `src/controlplane/infrastructure/db/migrations/0016_voice.sql:9-113`; `docs/implementation/e/plan.md:211` (CONV-E-01)
- acceptance:
  - requirement: `PostgresOutputRepository` hỗ trợ mọi kind mà hai pipeline ghi: `voice`, `word_timing`, `tts_invocation`, `receipt`, `timing_report`, `language_evidence`, `probe_report`, `image_safety_assessment`, `processed_media`, `audio_bed_result`, `receipt_by_request`, ánh xạ vào 11 bảng của `0016_voice.sql` (không migration mới; thiếu bảng hay cột thì báo BLOCKED kèm `blocked-manifest` DEPENDENCY_GAP về `PW-SCHEMA`). Mỗi activity E chạy trong một đơn vị công việc: ghi tất cả kind rồi commit; lỗi giữa chừng rollback sạch. `outputs.latest(KIND_RECEIPT, ...)` ở đầu `VoicePipeline` hoạt động trên CSDL (idempotency sau khi restart), thay `InMemory`. (2) Test đã nghiệm thu `tests/integration/persistence/e/test_persist_e_postgres.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó): trong `test_persist_e_rejects_unsupported_kind_bad_arguments_and_wrong_record`, dòng 299 `uow.outputs.append('receipt', 'k', 1, object())` và dòng 301 `uow.outputs.latest('receipt', 'k')` dùng kind `receipt` làm ví dụ kind không hỗ trợ, mà PW-E1 làm `receipt` thành kind hợp lệ; đổi đích danh chuỗi `'receipt'` ở đúng hai dòng đó thành `'no_such_kind'` (kind chắc chắn không hợp lệ), giữ nguyên `pytest.raises(UnsupportedKindError)` và mọi assertion khác. Không xoá test, không nới oracle; `report.md` ghi hai dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật: chạy `VoicePipeline` và `MediaPipeline` với TTS, aligner, route và detector giả (`FakeKokoro`, `FakeAligner`): đủ 11 kind có dòng; chạy lại cùng request sau khi dựng lại đối tượng trả receipt cũ và không ghi đôi; lỗi sau ghi nửa chừng không để lại dòng.
    counterexample: kind bị bỏ qua hoặc ném `KeyError`; receipt chỉ ở bộ nhớ; ghi nửa chừng vẫn commit; migration mới ngoài `PW-SCHEMA`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_e1_persistence.py tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/voice/persistence/output_repository.py').read_text(encoding='utf-8'); assert all(k in t for k in ['probe_report', 'processed_media', 'audio_bed_result', 'tts_invocation']) and 'from src.' not in t, 'PW-E1'"`
- coveredIds: PW-E1-01..04, CONV-E-01, CT-MED-001

### PW-E2: Tên tệp WAV, VoiceRoutePort Kokoro, ScriptTextPort, thời lượng WAV

- kind: work_package_slice
- ownedPaths:
  - `src/voice/adapters/real_kokoro_tts.py`
  - `src/voice/adapters/real_whisper_aligner.py`
  - `src/voice/application/voice_pipeline.py`
  - `src/voice/adapters/local_voice_route.py`
  - `src/voice/adapters/postgres_script_text.py`
  - `src/voice/adapters/wav_duration.py`
  - `tests/integration/prod_wiring/test_pw_e2_voice_ports.py`
  - `tests/integration/adapt/e/test_adapt_e_tts_aligner.py`
  - `docs/delivery-evidence/pw-e2/report.md`
- dependsOn: `PW-E1`
- resourceLocks: `LOCK-SRC-VOICE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/voice/adapters/real_kokoro_tts.py:171-185`; `src/voice/application/voice_pipeline.py:258`; `src/voice/adapters/real_whisper_aligner.py:237-245`; `src/controlplane/api/wiring/voice.py:88-89,108`; `src/controlplane/infrastructure/db/migrations/0015_creative.sql` (`cp_script_versions`)
- acceptance:
  - requirement: (1) Một quy tắc tên duy nhất (DQ-13): Kokoro ghi tạm trong thư mục tạm của voice root; `VoicePipeline` đặt tệp thành `voice-artifact-<sha256 của bytes WAV>` trong thư mục voice của staging và ghi artifact; `real_whisper_aligner.py` mở đúng tên đó, root truyền qua constructor (wiring chọn root ở `PW-W2`). (2) `LocalVoiceRoute` cài `VoiceRoutePort` chỉ cho Kokoro cục bộ (không có đường mạng). (3) `PostgresScriptText` cài `ScriptTextPort` đọc `cp_script_versions` theo `script_ref`. (4) `wav_duration.py` đo thời lượng WAV bằng stdlib `wave` (mẫu, tần số, số kênh), từ chối WAV hỏng. (5) Test đã nghiệm thu `tests/integration/adapt/e/test_adapt_e_tts_aligner.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó): các assertion khoá quy tắc tên staging cũ ở dòng 145-147, 179 và 225 đổi đích danh theo quy tắc (1): Kokoro ghi tạm trong thư mục tạm của voice root, tên tệp cuối là `voice-artifact-<sha256 của bytes WAV>` trong thư mục voice của staging; chỉ ba chỗ đó, không xoá test, không nới oracle nào khác. `tests/unit/voice/test_e01_package_layout.py` chỉ chạy ở PW-E2 và PW-E3 (PW-E4 sở hữu). `report.md` ghi từng dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật, Kokoro và aligner giả ghi tệp thật: WAV do Kokoro giả ghi được pipeline đổi tên đúng `voice-artifact-<sha256>` và aligner giả mở được; thời lượng đo khớp số mẫu; script đọc đúng phiên bản; WAV cụt bị từ chối; route cục bộ không nhận provider khác.
    counterexample: aligner mở `tts-<hash>.wav` hay tên khác; thời lượng ước lượng thay vì đo; script đọc từ payload; route đi mạng.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_e2_voice_ports.py tests/integration/adapt/e/test_adapt_e_tts_aligner.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/voice/application/voice_pipeline.py').read_text(encoding='utf-8'); assert 'voice-artifact-' in t and 'from src.' not in t, 'PW-E2'"`
- coveredIds: PW-E2-01..05, CT-MED-007

### PW-E3: ImageSafetyPolicy, NormalizeSpec và ActivityInputPort E

- kind: work_package_slice
- ownedPaths:
  - `src/voice/adapters/profile_media_policy.py`
  - `src/voice/adapters/activity_inputs.py`
  - `tests/integration/prod_wiring/test_pw_e3_media_inputs.py`
  - `docs/delivery-evidence/pw-e3/report.md`
- dependsOn: `PW-E2`
- resourceLocks: `LOCK-SRC-VOICE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/voice/application/media_pipeline.py:176-181,301`; `src/voice/worker/activity_handler.py:411-425`; `tools/launcher/prod/profile.json` (khoá media; tìm bằng rg `normalize` và `safety`); `src/voice/adapters/real_llm_image_safety.py`
- acceptance:
  - requirement: (1) `ImageSafetyPolicy` và `NormalizeSpec` dựng từ tham số profile production (khoá đã có; khoá thiếu thì ghi vào evidence và báo BLOCKED về Control, không bịa số). (2) `ActivityInputPort` E production phân giải `input_refs` thành đầu vào có kiểu cho `CreateVoiceTrack`, `CreateWordTiming`, `ProbeMedia`, `AssessImageSafety`, `TransformSensitiveImage`, `NormalizeMedia`, `PrepareAudioBed`: script từ `ScriptTextPort`, ảnh từ từng item `selected_media` của fan-out, cue từ plan. (3) `AssessImageSafety` trả cho mỗi ảnh một `output_ref` kiểu `image_safety_assessment`; ảnh cần che ra thêm item cho `TransformSensitiveImage`; ảnh không an toàn hoặc không chắc chắn không bao giờ thành safe và bị loại khỏi `NormalizeMedia` (DQ-11). Thiếu ảnh sau khi loại thì media seed dự phòng của selection được dùng.
    instrument: test trên PostgreSQL thật, `FakeRouter` làm detector: ảnh bài bị đánh dấu uncertain bị loại, ảnh safe qua `NormalizeMedia`; ảnh cần che đi qua `TransformSensitiveImage` (FFmpeg `boxblur` đã ghim); mỗi activity E nhận đúng đầu vào từ port; khoá profile thiếu thì BLOCKED.
    counterexample: ảnh uncertain thành safe; ngưỡng cố định trong mã; ảnh không qua kiểm vẫn vào `NormalizeMedia`; item fan-out bị bỏ sót.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/voice/adapters/profile_media_policy.py', 'src/voice/adapters/activity_inputs.py']); assert 'fake' not in t and 'os.environ' not in t and 'from src.' not in t, 'PW-E3'"`
- coveredIds: PW-E3-01..05, CT-MED-001, CT-MED-007

### PW-E4: Nhạc nền tự tìm và thu thập từ nguồn ngoài (FR-AUD-007)

- kind: work_package_slice
- ownedPaths:
  - `docs/implementation/prod-wiring/music-source.md`
  - `tools/launcher/prod/music_sources.json`
  - `src/voice/adapters/audio_bed_source.py`
  - `tests/integration/prod_wiring/test_pw_e4_audio_bed.py`
  - `tests/unit/voice/test_e01_package_layout.py`
  - `docs/delivery-evidence/pw-e4/report.md`
- dependsOn: `PW-E3`
- resourceLocks: `LOCK-SRC-VOICE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/voice/application/media_pipeline.py:176-181`; `docs/01-product-spec.md:209,212` (FR-AUD-004, FR-AUD-007); `docs/implementation/prod-wiring/inventory.md` mục 9; `src/source_ingestion/adapters/real_feed_source.py` (SecureFetcher, chỉ để đối chiếu)
- acceptance:
  - requirement: (1) Khảo sát trong `music-source.md`: tối thiểu bốn nguồn ứng viên cần kiểm (ví dụ API âm thanh của Openverse, Free Music Archive, ccMixter, Incompetech, Pixabay Music) chấm theo: giấy phép cho phép dùng thương mại không NC, URL và API ổn định không cần bí mật, có metadata giấy phép và tác giả, tần suất thay đổi; chọn một nguồn chính và một dự phòng, ghi URL https cố định của hai tệp mẫu kèm sha256 đo thật. Runtime khoá không có mạng thì BLOCKED kèm số bước, không bịa sha256. (2) `music_sources.json` có khoá gốc `sources` với đúng hai phần tử, một phần tử `role` = `primary` và một phần tử `role` = `fallback`; mỗi phần tử có `source_id`, `role`, `url` (https cố định của tệp mẫu), `license` (không chứa NC), `attribution` (chuỗi khác rỗng; ghi `không yêu cầu` khi giấy phép không đòi ghi công), `author`, `sha256` (64 ký tự hex đo thật của tệp mẫu). (3) `AudioBedPort` production: tìm theo mood và thời lượng trong nhạc đã thu thập, thu thập mới qua HTTPS với chính sách SSRF, ghi provenance (URL, giấy phép, tác giả, thời điểm, sha256); không AI sáng tác. (4) Không có nhạc phù hợp hoặc nguồn lỗi thì trả `audio_bed_result` loại `none` kèm warning `AUDIO_MIX_QUALITY`, chuỗi vẫn chạy. (5) Test khoá cấu trúc đã nghiệm thu `tests/unit/voice/test_e01_package_layout.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; PW-E2, PW-E3 chạy tệp này; quy tắc F1 mở rộng): `FORBIDDEN_IMPORT_PREFIXES` (dòng 15-19) cấm `socket`, `subprocess`, `urllib.request`, `http.client`, mà adapter tải HTTPS kèm chính sách SSRF `src/voice/adapters/audio_bed_source.py` cần một số import đó. Chỉ được: thêm vào `ADAPTER_IMPORT_EXEMPTIONS` (dòng 25-27) đúng một khoá mới `src/voice/adapters/audio_bed_source.py` với `frozenset` đóng liệt kê đúng các tên mô-đun cấm mà tệp đó thực sự import (không dùng tiền tố rộng; tiền lệ `src/voice/adapters/real_ffmpeg_media_tool.py` ứng với `frozenset({'subprocess'})`); sửa `AdapterExemptionTests.test_exemption_table_is_exact_paths_only` (dòng 148-154) cho khớp bảng hai khoá; thêm test mới (không xoá test cũ) rằng tệp đó chỉ được import đúng các mô-đun trong tập và mọi mô-đun cấm khác vẫn bị báo. Phương án thay thế được phép: tiêm transport HTTP từ wiring vào `audio_bed_source.py` để tệp không import mô-đun cấm, khi đó không sửa `test_e01_package_layout.py`. Không nới cấm khác, không miễn cả thư mục. `report.md` ghi dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật, transport HTTP giả phục vụ tệp WAV mẫu: tìm thấy thì thu thập và ghi provenance đủ trường; sha256 sai bị từ chối; hết nguồn thì kết quả `none` và pipeline vẫn ra video; URL ngoài danh sách bị chặn. `test_pw_e4_audio_bed.py` đọc `music_sources.json` và kiểm đúng hai nguồn đủ trường.
    counterexample: nhạc không giấy phép; thiếu provenance; AI sáng tác; hết nhạc thì dừng chuỗi; URL tuỳ ý.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_e4_audio_bed.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import json, pathlib, re; j = json.loads(pathlib.Path('tools/launcher/prod/music_sources.json').read_text(encoding='utf-8')); s = j['sources']; assert len(s) == 2 and sorted(x['role'] for x in s) == ['fallback', 'primary'], 'music_sources: need exactly two sources'; assert all(re.fullmatch('https://[^ ]+', x['url']) and x['license'] and 'nc' not in x['license'].lower().replace('-', ' ').split() and x['attribution'] and x['author'] and re.fullmatch('[0-9a-f]{64}', x['sha256']) for x in s), 'music_sources: missing fields'; t = pathlib.Path('docs/implementation/prod-wiring/music-source.md').read_text(encoding='utf-8'); assert 'FR-AUD-007' in t, 'PW-E4'"`
- coveredIds: PW-E4-01..05, FR-AUD-007, FR-AUD-004, R11

### PW-F1: Inspector QC đo thật các cổng hình

- kind: work_package_slice
- ownedPaths:
  - `src/render/adapters/real_output_inspector.py`
  - `src/render/adapters/frame_probe.py`
  - `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py`
  - `tests/unit/render/test_f01_package_layout.py`
  - `docs/delivery-evidence/pw-f1/report.md`
- dependsOn: `PW-VERT`
- resourceLocks: `LOCK-SRC-RENDER`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/render/ports/output_inspector.py:98`; `src/render/domain/quality_report.py:72-86`; `src/render/adapters/real_ffprobe_probe.py`; `docs/09-contracts/08-render-quality-contracts.md:117-129` (CT-QC-001); `src/render/ports/output_inspector.py:76-99` (`DisclosureObservation`, `DisclosureEvidence`, `OutputEvidence`); `src/render/domain/content_gates.py:277-303`
- acceptance:
  - requirement: `RealOutputInspector` cài `OutputInspectorPort` bằng FFmpeg đã ghim (sha256 `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`, trích khung hình và các bộ lọc `ssim`, `signalstats`); đo thật năm cổng cứng: `VISUAL_HOOK` (độ giống giữa khung đầu của output và hook hình đã chọn, ngưỡng cấu hình), `THUMBNAIL` (khung thumbnail giải mã được và đúng khung đã lên kế hoạch), `SUBTITLE_BURNED_IN` (phụ đề thấy được ở các mốc lấy mẫu so với khung không phụ đề), `KARAOKE_TIMING` (lệch giữa tệp ASS và mốc aligner, ngưỡng cấu hình), và cổng cứng có điều kiện `INFERENCE_DISCLOSURE_PRESENT` (CT-QC-001; `src/render/domain/content_gates.py:277-303`): với mỗi segment có `claim_mode` thuộc `INFERENCE_CLAIM_MODES` (`inference`, `creative_hypothesis`), `inspect` trả `OutputEvidence.disclosure` là `DisclosureEvidence` có `evidence_ref` và một `DisclosureObservation(segment_id, visible)` cho từng segment đó; cửa sổ thời gian của segment lấy từ các dòng `Dialogue` style `Disclosure` (trường Name = `segment_id`) trong tệp ASS mà `PW-F3` sinh; `visible=True` chỉ khi khung ở giữa cửa sổ có dải chữ disclosure khác khung mốc lấy ngoài mọi cửa sổ disclosure (cách đo giống `SUBTITLE_BURNED_IN`), không chỉ vì tệp ASS có dòng chữ. Video không có segment suy luận thì inspector không bịa observation (cổng NOT_APPLICABLE do `check_inference_disclosure_present`). Không cổng nào mặc định PASS khi thiếu phép đo; thiếu dữ liệu đầu vào thì FAIL có lý do. (2) Test khoá cấu trúc đã nghiệm thu `tests/unit/render/test_f01_package_layout.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; PW-F2 sở hữu cùng tệp, PW-F3 và PW-F4 chạy nó; quy tắc F1 mở rộng): `real_output_inspector.py` và `frame_probe.py` phải chạy tiến trình con FFmpeg nên `scan_package` báo `import:subprocess`. Chỉ được mở rộng `ADAPTER_EXEMPTIONS` (dòng 27-30) và bản chép trong `test_exemption_table_is_exact_paths_only` (dòng 238-241) thêm đúng hai khoá đường dẫn chính xác `adapters/real_output_inspector.py` và `adapters/frame_probe.py`, mỗi khoá `frozenset({'import:subprocess'})` cộng đúng các chuỗi phát hiện khác mà `scan_package` thực sự báo cho tệp đó (ví dụ `call:unlink` nếu xoá khung hình tạm), mỗi tập đóng; mỗi khoá phải trỏ tới tệp đã tồn tại (test kiểm `is_file`). Không nới `FORBIDDEN_IMPORT_PREFIXES`, `FORBIDDEN_CALL_ATTRS` hay cấm khác, không miễn cả thư mục `adapters`, không đổi hai khoá đã có. `report.md` ghi dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật, video mẫu nhỏ sinh bằng FFmpeg đã ghim (lavfi) trong `tmp_path`: mẫu đúng PASS cả năm cổng (mẫu có một segment `inference` kèm dải disclosure); mẫu thay hook, thiếu phụ đề, thumbnail hỏng, karaoke lệch vượt ngưỡng, thiếu dải disclosure của segment suy luận lần lượt FAIL đúng cổng (cổng disclosure FAIL với lý do `DISCLOSURE_MISSING:<segment_id>`); mẫu không có segment suy luận cho `INFERENCE_DISCLOSURE_PRESENT` NOT_APPLICABLE; kiểm sha256 FFmpeg trước khi chạy.
    counterexample: cổng PASS khi không đo; ngưỡng cố định trong mã; dùng FFmpeg không phải bản ghim; ghi PASS bằng mock; bỏ cổng `INFERENCE_DISCLOSURE_PRESENT`; coi disclosure có mặt vì tệp ASS có dòng chữ mà không đo khung hình.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/render/adapters/real_output_inspector.py').read_text(encoding='utf-8'); assert 'VISUAL_HOOK' in t and 'KARAOKE_TIMING' in t and 'DisclosureEvidence' in t and 'from src.' not in t, 'PW-F1'"`
- coveredIds: PW-F1-01..06, CT-QC-001

### PW-F2: Inspector QC đo thật các cổng tiếng, tiếng Anh, profile đầu ra

- kind: work_package_slice
- ownedPaths:
  - `src/render/adapters/real_output_inspector.py`
  - `src/render/adapters/real_ffprobe_probe.py`
  - `src/render/adapters/ffmpeg_capability.py`
  - `tests/integration/prod_wiring/test_pw_f2_inspector_audio.py`
  - `tests/unit/render/test_f01_package_layout.py`
  - `docs/delivery-evidence/pw-f2/report.md`
- dependsOn: `PW-F1`
- resourceLocks: `LOCK-SRC-RENDER`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/render/adapters/real_ffprobe_probe.py` (`audio_level`, `severe_audio_errors` hiện là `None`); `src/render/domain/quality_report.py:72-86`; `src/render/ports/inputs.py:44-46`; `docs/09-contracts/08-render-quality-contracts.md:117-129`
- acceptance:
  - requirement: (1) `RealFfprobeProbe` đo `audio_level` và `severe_audio_errors` bằng FFmpeg đã ghim (`volumedetect` hoặc `ebur128`, `astats`). (2) `RealOutputInspector` thêm bốn cổng cứng: `AUDIO_HOOK` (mức âm trong cửa sổ hook), `VOICE_AUDIBLE` (mức giọng ở các đoạn có lời), `ENGLISH_OUTPUT` (bằng chứng ngôn ngữ của E và metadata của D), `OUTPUT_PROFILE` (1080x1920, 30 fps, H.264, AAC, MP4, thời lượng và dung lượng theo profile); loudness và true peak chỉ ghi số đo (warn). (3) `ffmpeg_capability.py` đọc `ToolCapability` (filters, encoders gồm `libass`, `subtitles`, `h264_nvenc`, `libx264`, `loudnorm`) từ FFmpeg đã ghim. (4) Test khoá cấu trúc đã nghiệm thu `tests/unit/render/test_f01_package_layout.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; quy tắc F1 mở rộng): `ffmpeg_capability.py` phải chạy tiến trình con để đọc bộ lọc và encoder nên `scan_package` báo `import:subprocess`. Chỉ được thêm vào `ADAPTER_EXEMPTIONS` (dòng 27-30) và bản chép trong `test_exemption_table_is_exact_paths_only` (dòng 238-241) đúng một khoá đường dẫn chính xác `adapters/ffmpeg_capability.py` với `frozenset({'import:subprocess'})` cộng đúng các chuỗi phát hiện khác mà `scan_package` thực sự báo cho tệp đó (tập đóng); giữ nguyên các khoá của PW-F1 và hai khoá đã có (`real_ffprobe_probe.py` đã miễn `import:subprocess`, không mở rộng). Không nới cấm khác. `tests/integration/adapt/f/test_adapt_f_render.py` chỉ chạy ở PW-F2 (PW-F4 sở hữu). `report.md` ghi dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật, video mẫu sinh bằng FFmpeg đã ghim: mẫu đúng PASS; mẫu câm, giọng quá nhỏ, tiếng sai ngôn ngữ, sai độ phân giải hoặc codec lần lượt FAIL đúng cổng; `ToolCapability` liệt kê đúng bộ lọc và encoder của bản ghim; loudness lệch chỉ thành warning.
    counterexample: `audio_level=None` vẫn PASS; bỏ cổng tiếng Anh; đọc encoder từ danh sách cố định; loudness làm FAIL.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_f2_inspector_audio.py tests/integration/adapt/f/test_adapt_f_render.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/render/adapters/real_output_inspector.py').read_text(encoding='utf-8'); assert all(k in t for k in ['AUDIO_HOOK', 'VOICE_AUDIBLE', 'ENGLISH_OUTPUT']) and 'from src.' not in t, 'PW-F2'"`
- coveredIds: PW-F2-01..05, CT-QC-001

### PW-F3: Nguồn preset, output profile, QualityPolicy và tệp ASS

- kind: work_package_slice
- ownedPaths:
  - `src/render/adapters/config_render_sources.py`
  - `src/render/adapters/ass_manifest.py`
  - `src/render/adapters/postgres_plan_assets.py`
  - `tests/integration/prod_wiring/test_pw_f3_render_inputs.py`
  - `docs/delivery-evidence/pw-f3/report.md`
- dependsOn: `PW-F2`
- resourceLocks: `LOCK-SRC-RENDER`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/render/ports/inputs.py:40-70`; `src/render/domain/render_command.py:181-215`; `src/render/domain/karaoke_plan.py` (`build_karaoke_plan`, `render_ass`); `docs/09-contracts/08-render-quality-contracts.md`; `src/creative/domain/script.py:110-121,238-270,338-369` (`ScriptSegment`, `claim_mode`, `disclosure` bắt buộc cho `inference` và `creative_hypothesis`); `src/render/ports/inputs.py:39,43` (`script_version_ref`, `word_timing_ref`); `src/render/domain/content_gates.py:277-303`
- acceptance:
  - requirement: (1) `RenderPresetRevision`, `output_profile_revision` và `QualityPolicy` đọc từ `ConfigRevision` (scope `preset` và `policy`) của J, seed từ profile production khi chưa có; không hằng số trong mã. (2) `ass_manifest.py` sinh tệp `.ass` từ `build_karaoke_plan` và `render_ass` (mốc từ aligner của E), ghi vào staging và đưa vào `materialization_manifest` với `local_ref` kết thúc `.ass` đúng điều kiện của `build_render_command`. (3) `PlanAssetPort` (tập `artifact_version_id` mà plan cho phép, đọc từ bảng plan của D) và `ArtifactInfoPort` (đọc `cp_artifact_versions` và `cp_artifact_locations`) hiện thực production. (4) Disclosure (CT-AI-004, CT-QC-001): `postgres_plan_assets.py` thêm hàm đọc `segments` (`segment_id`, `order`, `claim_mode`, `disclosure`, `word_count`) từ `payload` của `cp_script_versions` theo `script_version_ref` của render package (cấu trúc payload ở `src/creative/domain/script.py:238-270`). `ass_manifest.py` thêm vào cùng tệp `.ass` (không sửa `karaoke_plan.py`, nằm ngoài ownedPaths) một style `Disclosure` (dải chữ cố định trong safe area, tách khỏi karaoke) ở cuối mục styles và một dòng `Dialogue` cho mỗi segment có `claim_mode` thuộc `inference` hoặc `creative_hypothesis` ở cuối mục events, trường Name = `segment_id`, nội dung = `disclosure` của segment; cửa sổ thời gian của segment tính bằng cách cộng dồn `word_count` của các segment theo `order` trên danh sách từ của aligner (`word_timing_ref`): start là `start_ms` của từ đầu, end là `end_ms` của từ cuối của segment. Segment suy luận thiếu `disclosure` hoặc tổng `word_count` không khớp số từ của aligner thì `ass_manifest` từ chối (lỗi có mã, không render).
    instrument: test trên PostgreSQL thật: đổi revision preset qua `ConfigRevision` thì lần render sau ghim revision mới; tệp ASS sinh ra có đủ sự kiện karaoke cho từng từ và nằm trong manifest; `build_render_command` nhận manifest không lỗi; asset ngoài plan bị từ chối; asset chưa biết trả `None`; script có một segment `inference` kèm `disclosure` thì tệp ASS có dòng `Dialogue` style `Disclosure` với Name = `segment_id` đúng cửa sổ cộng dồn `word_count`, và `build_render_command` vẫn nhận manifest không lỗi; segment suy luận thiếu `disclosure` hoặc lệch `word_count` bị từ chối; script chỉ `source_backed` không sinh dòng `Disclosure`.
    counterexample: preset hay profile hằng số; ASS không vào manifest; asset ngoài plan vẫn render; port đọc bộ nhớ; disclosure không vào ASS; cửa sổ disclosure lệch khỏi segment.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/render/adapters/config_render_sources.py', 'src/render/adapters/ass_manifest.py', 'src/render/adapters/postgres_plan_assets.py']); assert 'fake' not in t and 'memory' not in t and 'from src.' not in t, 'PW-F3'"`
- coveredIds: PW-F3-01..05, CT-QC-001, CT-REN-001, CT-AI-004

### PW-F4: Khoá GPU một lần, route reconcile_render và prepare_output_ready, ActivityInputPort F

- kind: work_package_slice
- ownedPaths:
  - `src/render/application/render_video.py`
  - `src/render/adapters/real_ffmpeg_renderer.py`
  - `src/render/worker/activity_handler.py`
  - `src/render/adapters/activity_inputs.py`
  - `src/controlplane/application/orchestration/workflows/activities.py`
  - `tests/integration/prod_wiring/test_pw_f4_render_worker.py`
  - `tests/integration/render/test_f20_worker_activity.py`
  - `tests/integration/adapt/f/test_adapt_f_render.py`
  - `docs/delivery-evidence/pw-f4/report.md`
- dependsOn: `PW-F3`
- resourceLocks: `LOCK-SRC-RENDER`, `LOCK-SRC-ORCHESTRATION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/api/wiring/render.py:37-42`; `src/render/application/render_video.py:249`; `src/render/adapters/real_ffmpeg_renderer.py:185-191`; `src/render/worker/activity_handler.py:356-361,407-421`; `src/render/ports/inputs.py:40-70`; `src/render/application/inspect_output.py:88-101` (`InspectOutputCommand.segments`, `word_timings`); `src/render/domain/content_gates.py:277-303`
- acceptance:
  - requirement: (1) Một render chỉ `acquire` một lần `LocalGpuLease`: `RenderPipeline.render_video` giữ lease và `RealFfmpegRenderer.run` nhận lease đã giữ, không `acquire` lần hai (với `gpu.slots: 2` một render ăn đúng một khe). (2) `handle_activity` định tuyến `reconcile_render` (xử lý attempt `STARTED` bị bỏ lại sau khi worker chết, thành kết quả xác định thay vì `outcome_unknown` mãi mãi) và `prepare_output_ready` (F-19); hai binding đã thêm ở `PW-CAT1`, `activities.py` chỉ sửa nếu thiếu trong `FAN_OUT_FROM_OUTPUT` hay danh sách stage. (3) `ActivityInputPort` F production phân giải `input_refs` thành đầu vào có kiểu cho `resolve_render_package`, `validate_render_package`, `reconcile_render`, `render_video`, `inspect_output`, `prepare_output_ready`. Riêng `inspect_output`: `ActivityInputPort` F dựng `InspectOutputCommand` với `segments` (`segment_id`, `claim_mode`) đọc từ `cp_script_versions` qua hàm của `PW-F3` theo `script_version_ref`, và `word_timings` đọc theo `word_timing_ref` của render package; thiếu một trong hai thì activity trả lỗi rõ ràng, không truyền danh sách rỗng khi script có segment suy luận, để cổng cứng có điều kiện `INFERENCE_DISCLOSURE_PRESENT` (CT-QC-001) được đánh giá thật (PASSED khi mọi segment `inference` và `creative_hypothesis` có dải disclosure thấy được; FAILED khi thiếu; NOT_APPLICABLE chỉ khi script không có segment suy luận). (4) Test đã nghiệm thu bị đổi hành vi (quy tắc F1): `tests/integration/render/test_f20_worker_activity.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó) ở dòng 328-342: `reconcile_render` và `prepare_output_ready` nay là activity hợp lệ nên ca activity không hỗ trợ không được dùng hai tên đó và `ACTIVITY_NAMES` đổi theo bộ tên mới (có hai tên này); `tests/integration/adapt/f/test_adapt_f_render.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó): `FakeLease` và các assertion sự kiện lease ở dòng 87-99 và 199-309 khoá việc `RealFfmpegRenderer.run` tự `acquire`, mà `run` nay nhận lease đã giữ và không `acquire` lần hai nên đổi đích danh các assertion đó; ca lease không có chuyển lên mức `RenderPipeline`, đã có ở `tests/integration/render/test_f18_render_video_pipeline.py:322` (PW-F4 chạy tệp đó, không sửa). `tests/unit/render/test_f01_package_layout.py` chỉ chạy ở PW-F3 và PW-F4. Không xoá test, không nới oracle nào khác; `report.md` ghi từng dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật với `FakeGpu` đếm `acquire` và FFmpeg đã ghim render clip nhỏ: một render đúng một `acquire` với `slots=2`; hai render đồng thời dùng hai khe, render thứ ba chờ; attempt `STARTED` mồ côi được `reconcile_render` kết luận; `prepare_output_ready` chạy sau QC; mỗi activity F nhận đầu vào đúng; với script có một segment `inference` kèm `disclosure`, `inspect_output` nhận `segments` đủ và `QualityReport` có `INFERENCE_DISCLOSURE_PRESENT` PASSED; bỏ dòng `Disclosure` khỏi ASS thì QC FAILED; script chỉ `source_backed` thì NOT_APPLICABLE.
    counterexample: hai lần `acquire` một render; attempt `STARTED` treo vĩnh viễn; route thiếu `reconcile_render`; fake renderer thay FFmpeg; truyền `segments` rỗng để cổng disclosure thành NOT_APPLICABLE trong khi script có segment suy luận.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/render/test_f20_worker_activity.py tests/integration/adapt/f/test_adapt_f_render.py tests/integration/render/test_f18_render_video_pipeline.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/render/worker/activity_handler.py').read_text(encoding='utf-8'); a = pathlib.Path('src/render/adapters/activity_inputs.py').read_text(encoding='utf-8'); assert 'reconcile_render' in t and 'prepare_output_ready' in t and 'segments' in a and 'from src.' not in t, 'PW-F4'"`
- coveredIds: PW-F4-01..06, CT-QC-001, F-19

### PW-I1: MaterializeArtifactSet, ghi artifact và location, ReconcileStorage, RequestCleanupEvaluation

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/storage_meta/handlers.py`
  - `src/controlplane/infrastructure/db/storage_meta/__init__.py`
  - `tests/integration/prod_wiring/test_pw_i1_materialize.py`
  - `docs/delivery-evidence/pw-i1/report.md`
- dependsOn: `PW-VERT`
- resourceLocks: `LOCK-SRC-STORAGE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/application/storage_meta/materialization.py:109`; `src/controlplane/infrastructure/db/storage_meta/__init__.py:76-92`; `src/controlplane/application/storage_meta/reconciliation.py`; `src/controlplane/application/storage_meta/cleanup_evaluation.py:95`; `src/controlplane/infrastructure/production_ports/artifact_source.py`; `src/controlplane/api/wiring/voice.py:88-89`
- acceptance:
  - requirement: (1) `update_location` ghi `observed_hash` và `observed_size_bytes` (đo thật từ tệp) khi chuyển sang VERIFIED; `PostgresStorageMetaRepository` có đường commit riêng cho handler (không tự commit trong repository). (2) Handler `MaterializeArtifactSet`: đăng ký `cp_artifact_versions` cho mọi output E và F mà render cần, đặt bản local phẳng `<staging>/<artifact_version_id>` (regex của `StagingArtifactSource` không cho `:`), ghi `cp_artifact_locations` DECLARED→VERIFIED với hash và size đo thật, trả `materialization_manifest`; tệp thiếu hay hash lệch thì `waiting` với `artifact_not_ready`. (3) Handler `ReconcileStorage` và `RequestCleanupEvaluation` bọc `reconciliation.py` và `cleanup_evaluation.py` thành handler thật cho `MaintenanceWorkflow`.
    instrument: test trên PostgreSQL thật, tệp trong `tmp_path`: sau materialize có hàng version và location VERIFIED với `observed_hash` đúng sha256 và `observed_size_bytes` đúng; `release_for_render` (cổng của `materialization.py:109`) chấp nhận; tệp bị sửa sau khi đăng ký thì bị từ chối; reconcile phát hiện location lệch; cleanup evaluation không cấp quyền khi chưa VERIFIED cloud.
    counterexample: `observed_hash` rỗng khiến cổng render fail; ghi location không đo hash; cleanup khi chưa verified; repository tự commit.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_i1_materialize.py tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/storage_meta/__init__.py').read_text(encoding='utf-8'); assert 'observed_hash' in t and 'observed_size_bytes' in t and t.count('UPDATE controlplane.cp_artifact_locations') >= 1, 'PW-I1'"`
- coveredIds: PW-I1-01..05, CT-STO-004, CT-STO-006, CT-STO-007

### PW-I2: PersistVideoOutput với receipt bền và credential_unavailable

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/storage_meta/persist_handler.py`
  - `src/controlplane/infrastructure/storage/drive_object_store.py`
  - `tests/integration/prod_wiring/test_pw_i2_persist_output.py`
  - `docs/delivery-evidence/pw-i2/report.md`
- dependsOn: `PW-I1`
- resourceLocks: `LOCK-SRC-STORAGE`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/application/storage_meta/cloud_persist.py`; `src/controlplane/infrastructure/storage/drive_object_store.py` (`_failure_kind`, `reserve_object_id`); `src/controlplane/api/wiring/storage.py` (`StorageServices.cloud_store`); `docs/09-contracts/09-orchestration-contracts.md:159-161` (CT-ORC-007); `docs/delivery-evidence/cp7-3/report.md` (F-CP7-3-01)
- acceptance:
  - requirement: (1) Handler `PersistVideoOutput` bọc `PersistArtifactToCloud`: receipt bền (đã chọn object id Drive và trạng thái bắt đầu) được commit TRƯỚC khi upload; worker chết giữa upload thì lần sau đọc receipt, xác minh object đã có thay vì upload đôi. (2) Khai artifact version của mp4 nếu chưa có và hai location: local và cloud, đi tới VERIFIED sau khi md5 và size của Drive khớp, ghi `observed_hash` và `observed_size_bytes`. (3) `DriveObjectStore` có mã lỗi riêng cho 401 (ví dụ `DRIVE_CREDENTIAL_INVALID`) tách khỏi `fatal`; handler ánh xạ mã đó (không khớp chuỗi thông điệp) sang `disposition: waiting` với `problem.code` là `credential_unavailable`; job sang WAITING và chạy tiếp khi credential hợp lệ lại, không tạo upload đôi.
    instrument: test trên PostgreSQL thật với Drive giả loopback (kiểu `FakeDrive` của `PW-H0`): upload thành công ghi version, hai location VERIFIED và receipt; chết sau commit receipt rồi chạy lại không upload thứ hai; 401 ra `waiting` `credential_unavailable`, đổi sang token hợp lệ thì hoàn tất đúng một object; md5 lệch không VERIFIED.
    counterexample: upload trước khi commit receipt; 401 gộp vào `fatal` làm job FAILED_FINAL; nhận diện 401 bằng khớp chuỗi; upload đôi sau restart.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_i2_persist_output.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/storage_meta/persist_handler.py').read_text(encoding='utf-8'); assert 'credential_unavailable' in t and 'from src.' not in t and 'fake' not in t.lower(), 'PW-I2'"`
- coveredIds: PW-I2-01..05, CT-STO-004, CT-ORC-007, F-CP7-3-01

### PW-A1: Nạp bảy nguồn seed và PlanCollectionCycle

- kind: work_package_slice
- ownedPaths:
  - `src/source_ingestion/application/seed_sources.py`
  - `src/source_ingestion/application/plan_cycle.py`
  - `tests/integration/prod_wiring/test_pw_a1_plan_cycle.py`
  - `docs/delivery-evidence/pw-a1/report.md`
- dependsOn: `PW-VERT`
- resourceLocks: `LOCK-SRC-SOURCE-INGESTION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `tools/launcher/prod/sources.json`; `src/source_ingestion/application/source_commands.py:233-250`; `docs/09-contracts/04-source-content-contracts.md:74-100` (CT-SRC-004); `docs/implementation/a/plan.md:181` (CONV-A-06); `src/controlplane/infrastructure/db/migrations/0019_prod_wiring.sql` (`cp_source_cycle_marks`)
- acceptance:
  - requirement: (1) `seed_sources(handler, path)` nạp bảy nguồn của `sources.json` qua `SourceCommandHandler.register_source` (idempotent: chạy lại không tạo nguồn đôi). (2) `PlanCollectionCycle` (service và handler theo CT-SRC-004): với `cp_source_cycle_marks`, mỗi nguồn tối đa một lượt định kỳ mỗi ngày (múi giờ Asia/Ho_Chi_Minh, lưu UTC), áp ngưỡng Tier, sắp theo tier và độ ưu tiên; trả `output_refs` kiểu `collection_source` (mỗi nguồn đến hạn một ref) để stage `collect` fan-out; ghi mark trong cùng giao dịch với kế hoạch. (3) Gọi lại trong cùng ngày không trả nguồn đã có mark.
    instrument: test trên PostgreSQL thật: seed hai lần còn đúng 7 nguồn; lượt đầu trả 7 ref, lượt hai cùng ngày trả 0, sang ngày sau trả lại 7 (đồng hồ tiêm được); nguồn tier thấp bị chặn theo ngưỡng; mark và kế hoạch cùng commit.
    counterexample: hai lượt định kỳ cho một nguồn trong ngày; nguồn nạp đôi; mark ghi ngoài giao dịch; bỏ qua Tier.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_a1_plan_cycle.py tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/source_ingestion/application/seed_sources.py', 'src/source_ingestion/application/plan_cycle.py']); assert 'register_source' in t and 'cp_source_cycle_marks' in t and 'from src.' not in t, 'PW-A1'"`
- coveredIds: PW-A1-01..04, CT-SRC-004, CONV-A-06, FR-COL-001

### PW-A2: Wiring CollectSource và ResolveCollectedDocument

- kind: work_package_slice
- ownedPaths:
  - `src/source_ingestion/worker/production_deps.py`
  - `src/ingestion/application/production_deps.py`
  - `tests/integration/prod_wiring/test_pw_a2_collect_resolve.py`
  - `docs/delivery-evidence/pw-a2/report.md`
- dependsOn: `PW-A1`
- resourceLocks: `LOCK-SRC-SOURCE-INGESTION`, `LOCK-SRC-INGESTION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/source_ingestion/worker/activity_handler.py:58,294-309`; `src/ingestion/application/activity_handler.py:66`; `src/controlplane/api/wiring/collection.py:72-75`; `src/controlplane/api/wiring/workflow.py:46-61,216-231`
- acceptance:
  - requirement: (1) `production_deps.py` của A dựng `CollectActivityDeps` theo từng lời gọi: `adapter_for(source_id)` (chọn adapter theo nguồn, không theo kind), `extraction_policy`, `retry_policy`, `adapter_revision`. (2) `production_deps.py` của B dựng `ResolveActivityDeps`: `tier_lookup` đọc PostgreSQL, `dedup_policy` có mặc định ghi rõ, `package_loader` tra theo `collected_document_id`. (3) Hàm bọc `ActivityRequestError` thành `ActivityRejected` không thử lại cho cả hai handler (hiện `_activity_fn` chỉ bắt `ActivityRejected`).
    instrument: test trên PostgreSQL thật với nguồn feed giả loopback: `CollectSource` thu một bài và ảnh kèm, ghi `CollectedDocument`; `ResolveCollectedDocument` tạo bài và revision; lỗi yêu cầu ra `ApplicationError` không thử lại thay vì thử lại vô hạn; nguồn 404 không dừng nguồn khác.
    counterexample: adapter khoá theo kind khiến mọi nguồn dùng một adapter; `ActivityRequestError` làm activity retry vô hạn; deps dựng một lần dùng chung cho mọi nguồn.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_a2_collect_resolve.py tests/unit/collection/test_a01_package_layout.py tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/source_ingestion/worker/production_deps.py', 'src/ingestion/application/production_deps.py']); assert 'activityrequesterror' in t and 'fake' not in t and 'from src.' not in t, 'PW-A2'"`
- coveredIds: PW-A2-01..04, CT-SRC-004, CT-SRC-005, CT-CNT-001

### PW-A3: Vòng lặp thu thập cục bộ, khởi enrichment, RegisterMediaDiscovery

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/orchestration/collection_scheduler.py`
  - `src/controlplane/application/orchestration/workflows/activities.py`
  - `src/catalog/application/media_discovery_handler.py`
  - `tests/integration/prod_wiring/test_pw_a3_scheduler.py`
  - `tests/integration/convergence/test_cp6_video_production_flow.py`
  - `docs/delivery-evidence/pw-a3/report.md`
- dependsOn: `PW-A2`
- resourceLocks: `LOCK-SRC-SOURCE-INGESTION`, `LOCK-SRC-ORCHESTRATION`, `LOCK-SRC-CATALOG`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `tools/launcher/prod/profile.json:95-99` (`collection_interval_minutes`); `src/controlplane/application/orchestration/workflows/activities.py:95-106,132-146`; `src/catalog/application/discovery.py:52`; `docs/implementation/cp7/plan.md:23,206` (U1, OI-CP7-03); `docs/01-product-spec.md:98` (FR-COL-001)
- acceptance:
  - requirement: (1) `CollectionScheduler.run_forever(stop_event)` trong tiến trình worker (quyết định U1, không Temporal Schedule): mỗi `collection_interval_minutes` (180) kiểm các nguồn đến hạn theo `cp_source_cycle_marks`; còn nguồn đến hạn thì khởi `DailyCollectionWorkflow` với id xác định theo ngày và lượt kiểm (`REJECT_DUPLICATE`, `WorkflowAlreadyStarted` là thành công); nhịp 180 phút không làm một nguồn bị quét quá một lượt định kỳ mỗi ngày. (2) Consumer của `CollectedDocumentAvailable` (`SUBSCRIPTIONS`): với mỗi tài liệu mới khởi `ContentEnrichmentWorkflow` id `enrich:<document_id>` kèm `item_refs` từ `document_input_refs`. (3) `ENRICHMENT_STAGE_ACTIVITIES['media']` gồm `RegisterMediaDiscovery`; handler bọc `register_discovery` của C đăng ký ảnh tải kèm bài kèm provenance (URL, bài, sha256, thời điểm), không tự cấp quyền dùng. (4) Test đã nghiệm thu `tests/integration/convergence/test_cp6_video_production_flow.py` (`test_enrichment_subscription`, dòng 669): `assert flow.unbound == ['dedup', 'enrich_ai', 'media', 'index']` đổi thành `assert flow.unbound == ['dedup', 'enrich_ai', 'index']` vì stage `media` có `RegisterMediaDiscovery` nên không còn vào `unbound` (`flow.py:241-246`); `InProcessGateway` (dòng 297) xử lý activity mới như các activity khác, giữ nguyên assertion `ResolveCollectedDocument` ba lần. `tests/integration/convergence/test_cp6_workflow_catalog.py` chỉ chạy, không sửa.
    instrument: test trên PostgreSQL thật và server test của temporalio, đồng hồ tiêm được và feed giả: bốn lần kiểm trong một ngày chỉ một lượt thu mỗi nguồn; có tài liệu mới thì đúng một enrichment khởi và không khởi đôi khi consumer chạy lại; ảnh bài được đăng ký kèm provenance; dừng êm khi `stop_event`. `test_enrichment_subscription` xanh với `unbound` mới.
    counterexample: quét mỗi nguồn mỗi 180 phút; enrichment khởi đôi; ảnh đăng ký không provenance; Temporal Schedule cloud; test cp6 đã nghiệm thu vẫn khoá `media` là unbound.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_a3_scheduler.py tests/integration/convergence/test_cp6_video_production_flow.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/orchestration/collection_scheduler.py').read_text(encoding='utf-8'); assert 'REJECT_DUPLICATE' in t and 'collection_interval_minutes' in t and 'from src.' not in t, 'PW-A3'"`
- coveredIds: PW-A3-01..05, CT-SRC-004, FR-COL-001, U1

### PW-B1: Chọn ứng viên từ bảng B cho lô

- kind: work_package_slice
- ownedPaths:
  - `src/ingestion/application/candidate_selector.py`
  - `tests/integration/prod_wiring/test_pw_b1_candidate_selector.py`
  - `docs/delivery-evidence/pw-b1/report.md`
- dependsOn: `PW-VERT`
- resourceLocks: `LOCK-SRC-INGESTION`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/ingestion/application/source_set.py:138` (`build_source_set`); `src/controlplane/domain/orchestration/allocation_policy.py:24`; `src/controlplane/application/orchestration/batch_allocation.py` (`CandidateSelectorPort`, PW-G5); `tools/launcher/prod/profile.json` (`batch`)
- acceptance:
  - requirement: `PostgresCandidateSelector` cài `CandidateSelectorPort.next_candidate(batch_id, production_mode)`: đọc `cp_articles`, `cp_article_revisions`, `cp_events`, loại bài hay sự kiện đã đủ số video mỗi tin mỗi vòng trong `cp_job_candidates` của lô (`videos_per_news_per_round`, mặc định 2), xếp theo mức nóng = số nguồn độc lập + độ mới + tier (mặc định của Control, sửa được trên UI), trả `AllocationCandidate` kèm `angle_slot` khác nhau trong cùng vòng và `source_set_ref` do `build_source_set` dựng; kết quả xác định với cùng dữ liệu; hết ứng viên thì trả `None`.
    instrument: test trên PostgreSQL thật với bài và sự kiện seed: hai video cùng tin có `angle_slot` khác nhau; tin nóng hơn được chọn trước; ứng viên đã dùng không lặp lại; hết dữ liệu trả `None`; `build_source_set` được gọi đúng và `source_set_ref` lưu được vào `cp_job_candidates`.
    counterexample: chọn ngẫu nhiên không xác định; hai video cùng góc; ứng viên lặp giữa các lô; không dùng `build_source_set`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_b1_candidate_selector.py tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/ingestion/application/candidate_selector.py').read_text(encoding='utf-8'); assert 'build_source_set' in t and 'random' not in t.lower() and 'from src.' not in t, 'PW-B1'"`
- coveredIds: PW-B1-01..04, CT-ORC-002, CT-CNT-001

### PW-W1: Nối G, A, B, C, I vào launcher

- kind: convergence_slice
- ownedPaths:
  - `tools/launcher/launcher.py`
  - `src/controlplane/api/wiring/workflow.py`
  - `src/controlplane/api/wiring/ingestion.py`
  - `src/controlplane/api/wiring/collection.py`
  - `src/controlplane/api/wiring/storage.py`
  - `src/controlplane/api/wiring/completion.py`
  - `tests/integration/prod_wiring/test_pw_w1_launcher_core.py`
  - `tests/integration/adapt/launch/test_adapt_launch_cli.py`
  - `tests/integration/adapt/wire/test_adapt_wire_services.py`
  - `docs/delivery-evidence/pw-w1/report.md`
- dependsOn: `PW-A3`, `PW-B1`, `PW-D1`, `PW-I2`, `PW-VERT`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `tools/launcher/launcher.py:533-603` (`start_worker`); `src/controlplane/api/wiring/workflow.py:175-270`; `src/controlplane/api/wiring/storage.py` (`StorageServices.cloud_store`); `src/controlplane/api/wiring/completion.py:20`; `src/controlplane/api/wiring/collection.py:72-75`
- acceptance:
  - requirement: (1) `start_worker` thay `handlers={}` bằng bảng handler thật cho `PlanCollectionCycle`, `CollectSource`, `ResolveCollectedDocument`, `RegisterMediaDiscovery`, `AllocateJob`, `FinalizeBatch`, `ReserveVariant`, `CommitVideoCompletion`, `MaterializeArtifactSet`, `PersistVideoOutput`, `RequestCleanupEvaluation`, `ReconcileStorage`. (2) Thay `_grant_issuer` và `_capability_reader` ném `LauncherError` bằng `build_grant_issuer` (`PW-G3`) và `CapabilityReader` (`PW-G4`) với probe thật (AppSession ACTIVE, sha256 FFmpeg ghim, `LocalGpuLease`). (3) Bọc dispatcher theo thứ tự `GrantRevokingDispatcher(ResultRecordingDispatcher(ActivityDispatcher))` với `JobLifecycleListener`. (4) Khởi `OutboxRelay` và `CollectionScheduler` trong tiến trình worker, dừng êm cùng `launcher stop`; `StorageServices.cloud_store` và `PersistArtifactToCloud` được dùng. (5) Seed bảy nguồn (`seed_sources` của `PW-A1`) và sáu prompt (`seed_default_prompts` do `PW-D1` tạo, vì vậy `dependsOn` có `PW-D1`) khi `launcher start`, sau AppSession và trước worker. (6) Test đã nghiệm thu `tests/integration/adapt/launch/test_adapt_launch_cli.py`: `test_worker_stop_waits_for_the_worker_thread_not_a_lost_future` (dòng 384-427) gọi `launcher.start_worker(SimpleNamespace(), None)` với `build_workflow_services` và `build_temporal_registration` bị monkeypatch; bổ sung monkeypatch hoặc tiêm cho `build_grant_issuer`, `CapabilityReader`, `OutboxRelay`, `CollectionScheduler` và mọi cổng DB mới để test vẫn kiểm `stop` xong dưới 2 giây và `connect` đúng `('127.0.0.1:7233', 'default')`; thêm fake cho trường `Deps` mới (nếu có) vào `make_fx` để mọi test `cmd_start`, `cmd_serve` giữ xanh. (7) Test khoá bảng tên đã nghiệm thu `tests/integration/adapt/wire/test_adapt_wire_services.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; PW-W2 sở hữu cùng tệp; quy tắc F1 mở rộng): mô-đun wiring mới `src/controlplane/api/wiring/ingestion.py` làm đỏ phép kiểm kê builder; chỉ được thêm đích danh mục `ingestion` vào `OWN_SUBSYSTEM` (dòng 76-86) và vào `EXPECTED_BUILDERS` (dòng 67-75, kèm tên builder thật của `ingestion.py`), theo đúng định dạng các mục đang có, và test dựng builder đó trong vùng dòng 153-197 nếu bảng đòi; không đổi mục nào đã có, không nới oracle khác. `tests/integration/adapt/prod/test_adapt_prod_app.py` chỉ chạy, không sửa (thuộc `ADAPT-PROD-FIX3`). `report.md` ghi dòng đã đổi cùng lý do.
    instrument: test trên PostgreSQL thật và server test của temporalio, dịch vụ ngoài là adapter giả: `start_worker` dựng không ném lỗi chưa nối; các activity liệt kê đều có handler khác `unbound_handler`; `launcher start` ghi AppSession, seed nguồn và prompt rồi mới khởi worker (spy thứ tự); `stop` dừng relay và scheduler trong thời hạn.
    counterexample: còn `LauncherError` báo chưa nối; relay hay scheduler không dừng; handler `unbound` còn sót; seed chạy trước AppSession; seed prompt chạy khi `PW-D1` chưa có `seed_default_prompts`; test launcher đã nghiệm thu đỏ vì `start_worker` đổi.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('tools/launcher/launcher.py').read_text(encoding='utf-8'); assert 'OutboxRelay' in t and 'build_grant_issuer' in t and 'CapabilityReader' in t, 'PW-W1'"`
- coveredIds: PW-W1-01..05, CT-WF-004, CT-WF-007, ARCH-009

### PW-W2: Nối D, E, F và kiểm không còn activity unbound

- kind: convergence_slice
- ownedPaths:
  - `tools/launcher/launcher.py`
  - `src/controlplane/api/wiring/creative.py`
  - `src/controlplane/api/wiring/voice.py`
  - `src/controlplane/api/wiring/render.py`
  - `src/controlplane/api/wiring/production.py`
  - `tests/integration/prod_wiring/test_pw_w2_launcher_def.py`
  - `tests/integration/adapt/launch/test_adapt_launch_cli.py`
  - `tests/integration/adapt/wire/test_adapt_wire_services.py`
  - `docs/delivery-evidence/pw-w2/report.md`
- dependsOn: `PW-W1`, `PW-D3`, `PW-E4`, `PW-F4`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: `src/controlplane/api/wiring/creative.py:142-172`; `src/controlplane/api/wiring/voice.py:88-108`; `src/controlplane/api/wiring/render.py:37-42`; `src/controlplane/api/wiring/workflow.py:64-100`; `src/controlplane/application/orchestration/workflows/activities.py:123-130`; `src/controlplane/api/wiring/production.py` (`_build_services` dòng 88-96; chỉ đọc khối gán `module_services` trong `build_production_app` dòng 394-395); `tests/integration/adapt/prod/test_adapt_prod_app.py` (chỉ chạy, không sửa); `docs/implementation/read-screens/plan.md` mục 7.2 (ADAPT-PROD-FIX3)
- acceptance:
  - requirement: (1) Ráp deps production cho D (`PW-D1`..`PW-D3`), E (`PW-E1`..`PW-E4`, root WAV và aligner khớp tên của `PW-E2`), F (`PW-F1`..`PW-F4`, một `LocalGpuLease`) và đăng ký qua `creative_handler`, `voice_handler`, `render_handler` với `ExecutionGrantCurrency` của `PW-G3`. (2) Quét tĩnh: mọi activity trong `STAGE_ACTIVITIES_BY_WORKFLOW` của sáu workflow có handler khác `unbound_handler` trong composition dựng từ hồ sơ `production`. (3) Quét AST `src/controlplane/api/wiring` và `tools/launcher`: 0 lớp hay adapter tên `Fake*`, `InMemory*`, `Memory*` trong đường production. (4) Ràng buộc với `ADAPT-PROD-FIX3` (cùng `LOCK-COMPOSITION-ROOT`, chạy tuần tự, không `dependsOn` cứng): trong `production.py` chỉ sửa `_build_services` (và `TemporalWorkerGroup` nếu cần) cùng import tương ứng, neo theo tên symbol sau khi đọc lại tệp ở HEAD; giữ nguyên khối gán `api_app.state.module_services[...]` trong `build_production_app`, docstring đầu tệp, `SourceModuleService`, `HookModuleService` và mọi phần khác; không sửa `tests/integration/adapt/prod/test_adapt_prod_app.py`.  (5) Test đã nghiệm thu `tests/integration/adapt/launch/test_adapt_launch_cli.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; khác `test_adapt_prod_app.py` của `ADAPT-PROD-FIX3` là tệp không được sửa): chỉ đổi assertion hay monkeypatch đỏ vì phần nối D, E, F trong `launcher.py`, không xoá test. (6) Test khoá bảng tên đã nghiệm thu `tests/integration/adapt/wire/test_adapt_wire_services.py` (thuộc `ownedPaths`, lệnh kiểm chạy nó; PW-W1 đã thêm mục `ingestion` vào `OWN_SUBSYSTEM` và `EXPECTED_BUILDERS`; quy tắc F1 mở rộng): chỉ được đổi đích danh phần bảng tên và assertion đỏ vì việc nối D, E, F của PW-W2 (`EXPECTED_BUILDERS`, `OWN_SUBSYSTEM`, `test_creative_production_uses_real_adapters`, `test_voice_production_uses_real_adapters` và test render tương ứng); hồ sơ test của `build_creative_services` vẫn dựng `InMemoryUnitOfWork` và `FakeAIAdapter` (dòng 456-460 giữ nguyên), không xoá test, không nới oracle nào khác. (7) Kiểm không có Fake hoặc InMemory trong production của `creative.py` là quét AST phần production của `build_creative_services` (lệnh kiểm thứ 3), không cấm chuỗi `InMemory` trên cả tệp. `report.md` ghi dòng đã đổi cùng lý do.
    instrument: `test_pw_w2_launcher_def.py` dựng composition production với dịch vụ ngoài là adapter giả của test, kiểm danh sách activity không `unbound` và quét AST; một handler cố ý gỡ thì test đỏ. Quét AST `production.py` cho thấy hai dòng gán `module_services['sources']` và `module_services['hooks']` trong `build_production_app` còn nguyên; `test_adapt_prod_app.py` vẫn xanh.
    counterexample: activity còn `ACTIVITY_SERVICE_UNBOUND`; `InMemory` trong composition production; hai lần `acquire` GPU; aligner mở sai root; `PW-W2` sửa khối `module_services`, docstring đầu tệp hay `test_adapt_prod_app.py` của `ADAPT-PROD-FIX3`; hai gói cùng sửa `production.py` song song.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/integration/adapt/prod/test_adapt_prod_app.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider`
  - `python -c "import ast, pathlib; t = pathlib.Path('src/controlplane/api/wiring/creative.py').read_text(encoding='utf-8'); fs = [n for n in ast.parse(t).body if isinstance(n, ast.FunctionDef) and n.name == 'build_creative_services']; assert len(fs) == 1, 'build_creative_services missing'; body = fs[0].body; branches = [s for s in body if isinstance(s, ast.If)]; assert branches, 'test branch missing'; rest = [s for s in body if s is not branches[0]]; names = [x.id for s in rest for x in ast.walk(s) if isinstance(x, ast.Name)] + [x.attr for s in rest for x in ast.walk(s) if isinstance(x, ast.Attribute)]; bad = [x for x in names if x.startswith(('Fake', 'InMemory', 'Memory'))]; assert not bad, bad; assert 'from src.' not in t, 'PW-W2'"`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/api/wiring/production.py').read_text(encoding='utf-8'); assert 'compose_sources_module(services, config)' in t and 'compose_hooks_module(manager)' in t, 'PW-W2 module_services'"`
- coveredIds: PW-W2-01..04, CT-WF-004, CT-WF-006

### PW-E2E: Một lô qua POST /v1/batches thành video tới completion

- kind: work_package_slice
- ownedPaths:
  - `tests/integration/prod_wiring/pw_e2e_support.py`
  - `tests/integration/prod_wiring/test_pw_e2e_batch_video.py`
  - `docs/delivery-evidence/pw-e2e/report.md`
- dependsOn: `PW-H0`, `PW-SCHEMA`, `PW-G1`, `PW-G2`, `PW-G3`, `PW-G4`, `PW-CAT1`, `PW-CAT2`, `PW-G5`, `PW-G6`, `PW-G7`, `PW-VERT`, `PW-D1`, `PW-D2`, `PW-D3`, `PW-E1`, `PW-E2`, `PW-E3`, `PW-E4`, `PW-F1`, `PW-F2`, `PW-F3`, `PW-F4`, `PW-I1`, `PW-I2`, `PW-A1`, `PW-A2`, `PW-A3`, `PW-B1`, `PW-W1`, `PW-W2`
- resourceLocks: `LOCK-POSTGRES-TEST-DB`, `LOCK-COMPOSITION-ROOT`
- bindingRefs: `tools/launcher/launcher.py:533-603`; `src/controlplane/api/routes/control.py:92`; `src/controlplane/application/control_api/commands.py:80-132`; `docs/implementation/cp7/slices.md` (CP7-10, CP7-11); `docs/implementation/prod-wiring/inventory.md` mục 10
- acceptance:
  - requirement: Trong composition production dựng bởi `launcher` (không dùng assembly riêng của test), trên server test của temporalio và PostgreSQL thử, 9Router, Drive, Kokoro, faster-whisper và GPU là adapter giả, còn FFmpeg đã ghim là thật. (1) `POST /v1/batches` với `target_completed_videos=1` rồi outbox relay khởi workflow, một video đi hết 11 stage (AppSession, grant, `cp_stage_runs`, handler D, E, F, I thật) tới `CommitVideoCompletion`: job COMPLETED, batch TARGET_REACHED, một ledger, mp4 có location local và cloud VERIFIED. Script của 9Router giả có một segment `claim_mode=inference` kèm `disclosure`: `QualityReport` của job có cổng `INFERENCE_DISCLOSURE_PRESENT` ở trạng thái PASSED (dải disclosure burn-in đo trên mp4 do FFmpeg đã ghim render), và một lô phụ có script chỉ `source_backed` cho cổng này NOT_APPLICABLE. (2) Mọi activity mà workflow gọi đều có handler thật (0 `unbound`, 0 Fake hoặc Memory trong composition production). (3) Lỗi 401 của Drive giả đưa job sang WAITING `credential_unavailable`, đổi token thì chạy tiếp đúng một upload và stage render không chạy lại. (4) Dừng rồi bật lại worker giữa render và upload: stage đã xong không chạy lại (`attempt` không tăng) và sẵn sàng trong hạn. (5) Một lượt kiểm thu thập với feed giả sinh tài liệu, rồi enrichment, rồi ứng viên cho lô thứ hai. (6) `report.md` ghi thời gian từng stage (đầu vào của OI-PW-02) và liệt kê điều kiện để CP7-10, CP7-11 chạy.
    instrument: `test_pw_e2e_batch_video.py` đếm `attempt`, grant còn sống, trạng thái job, batch, ledger, location và danh sách handler `unbound`; quét AST composition tìm `Fake*`, `InMemory*`, `Memory*`; đọc `QualityReport` của job và kiểm trạng thái `INFERENCE_DISCLOSURE_PRESENT`.
    counterexample: video chỉ tới stage `analyze`; handler `unbound`; epoch dạng `rec-...`; chạy lại stage đã xong sau resume; mất việc khi 401; assembly riêng của test thay composition production; video có segment suy luận mà QC không đo disclosure hoặc bỏ qua cổng.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e2e/report.md').read_text(encoding='utf-8'); assert 'PW-E2E' in t and 'CP7-10' in t and 'CP7-11' in t, 'PW-E2E'"`
- coveredIds: PW-E2E-01..06, CT-QC-001, CT-WF-004, CT-WF-006, CT-WF-007, CT-ORC-007, CT-ORC-010, CT-SRC-004
