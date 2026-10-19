# Slice hội tụ — IMPL-PLAN-CONVERGENCE

Nguồn: `docs/implementation/convergence/plan.md`. Slice hội tụ được Control biên dịch trong phong bì policy; `kind` là `dependency_slice` cho `CP-2B-DEPS` và `convergence_slice` cho các slice còn lại.

## Quy tắc chung cho mọi slice

- Chỉ sửa đúng các tệp trong `ownedPaths` của slice và giữ khóa trong `resourceLocks`; mọi slice hội tụ giữ thêm `LOCK-CONVERGENCE` nên chạy tuần tự, mỗi lúc một owner.
- Cấm sửa `docs/milestones/**/evidence/**`, kế hoạch phân hệ `docs/implementation/a` đến `j`, `docs/09-contracts/**`, `protected-checkouts/**`; nhu cầu đổi contract là `ARCHITECTURE_CHANGE`, dừng chờ user.
- `USER-CKPT-D9-D10` là điểm chờ user duyệt thư viện và cách dựng lại runtime (plan.md mục 3 và 4), không phải slice. Slice phụ thuộc trực tiếp `CP-2B-DEPS` khai `USER-CKPT-D9-D10` trong `dependsOn`; slice dùng thư viện mới phụ thuộc `CP-2B-DEPS`. `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J` là slice adapter PostgreSQL do Control mở sau khi `CP-3-MIGRATIONS` đạt Auditor PASS (plan.md mục 5.3).
- Không thêm thư viện ngoài `CP-2B-DEPS`; không gọi dịch vụ thật, không đọc `Credentials/` hay bí mật; phân hệ khác thay bằng fixture CP1 (`tests/fixtures/contracts/**`) và fake trong tệp test. Import root `src/`, không tiền tố `src.`.
- Test-first: viết test, thấy RED do assertion đúng oracle (ImportError, thiếu tệp hay thiếu binary không phải RED hợp lệ), rồi implement tới GREEN. Bằng chứng ở `docs/delivery-evidence/<id viết thường>/report.md`.
- `testCommands` chạy bằng interpreter khoá của runtime D9. Slice hội tụ chạy lại lệnh kiểm của các gói phụ thuộc trực tiếp ở mức thư mục test của phân hệ; lệnh `npm` chạy trong `src/controlplane/ui`.
- Mỗi slice có tiêu đề cấp 3 dạng `CP-<mã>: <tên>`, tiếp theo là kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance (requirement, instrument, counterexample), testCommands theo đúng thứ tự này.

### CP-2B-DEPS: Khoá thư viện, đăng ký gói và ghi pin runtime

- kind: dependency_slice
- ownedPaths:
  - `pyproject.toml`
  - `uv.lock`
  - `src/controlplane/pyproject.toml`
  - `src/controlplane/uv.lock`
  - `src/controlplane/requirements.lock`
  - `src/controlplane/ui/package.json`
  - `src/controlplane/ui/package-lock.json`
  - `src/controlplane/api/routes/modules/__init__.py`
  - `src/controlplane/api/wiring/__init__.py`
  - `src/controlplane/application/orchestration/workflows/__init__.py`
  - `tools/runtime/runtime.lock.json`
  - `docs/delivery-evidence/cp-2b-deps/report.md`
- dependsOn: `USER-CKPT-D9-D10`, `IMPL-PLAN-CONVERGENCE`
- resourceLocks: `LOCK-DEPENDENCY-UNIVERSE`, `LOCK-CONVERGENCE`
- bindingRefs: không có binding riêng; bám plan.md mục 3 và 4
- acceptance:
  - requirement: Chỉ thêm thư viện user đánh dấu APPROVED tại `USER-CKPT-D9-D10` (đề xuất mặc định `temporalio==1.32.0` cho `src/controlplane/pyproject.toml`), dạng `tên==phiên bản`, không `latest`, không dải phiên bản; không đổi phiên bản gói đã khóa hay M1-R1; `cryptography` theo mục 3.3. Khai trong `[tool.setuptools]` các gói `controlplane.api.routes.modules`, `controlplane.api.wiring`, `controlplane.application.orchestration.workflows`, `controlplane.infrastructure.storage` và tạo ba `__init__.py` rỗng. Tái sinh `requirements.lock` kèm hash, `uv.lock`, `package-lock.json` theo phần đã duyệt. Ghi `tools/runtime/runtime.lock.json`: Python 3.13.15, uv 0.12.13, Node 22.17.0, npm 10.9.2, PostgreSQL 18.6, Temporal Server 1.31.2 và ba giá trị user cung cấp (FFmpeg, sha256 Temporal, digest PostgreSQL); thiếu thì ghi `null` kèm `status: BLOCKED`, không bịa.
    instrument: pytest `tests/m2/test_p0_packaging.py` và hai probe `tomllib`, `json`: mọi dependency có `==`, mọi phiên bản trong `package.json` bắt đầu bằng chữ số.
    counterexample: thư viện không ghim hoặc dùng `latest`; thư viện chưa duyệt vào lockfile; nâng phiên bản gói đã khóa; bịa sha256 FFmpeg; gói mới có `__init__.py` nhưng không khai ở pyproject.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider`
  - `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert x and all('==' in i for i in x), x"`
  - `python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/ui/package.json').read_text(encoding='utf-8')); v = list(p['dependencies'].values()) + list(p['devDependencies'].values()); assert v and all(i[0].isdigit() for i in v), v"`

### CP-2C-M2-REGRESSION: Sửa đúng hai phép kiểm của tests/m2 (D2)

- kind: convergence_slice
- ownedPaths:
  - `tests/m2/test_p9_m2_exit_gate.py`
  - `docs/delivery-evidence/cp-2c-m2-regression/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`, `IMPL-PLAN-CONVERGENCE`; Control ghi giá trị `M2_ACCEPTED_SHA` (OI-CV-01) vào lệnh làm việc trước khi dispatch
- resourceLocks: `LOCK-M2-REGRESSION`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE`
- bindingRefs: chỉ đọc `docs/milestones/m2-control-plane/evidence/manifest.json`; bám plan.md mục 8
- acceptance:
  - requirement: Chỉ sửa `test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db` và `test_tst_m2_p9_001_m2_manifest_and_gate_evaluation` (cùng hàm `validate_manifest_dict` mà phép 001 gọi). Phép 005: N là số tệp `NNNN_*.sql` không phải rollback; hai lần `migrate_up` cho phiên bản `[1..N]` và `len == N`; tám migration đầu có tên và sha256 của 16 tệp (`0001`..`0008` cùng rollback) bằng blob tại hằng `M2_ACCEPTED_SHA`. Phép 001: `validate_manifest_dict` nhận `baseline_commit` và `baseline_prefixes` (`src/controlplane/ui/dist/`, `tests/m2/e2e/`); artifact thuộc tiền tố được so `sha256` trong manifest với sha256 của `git show <baseline_commit>:<đường dẫn>`, artifact khác vẫn so với cây làm việc; mặc định `None` giữ nguyên hành vi cho test 002 và các ca fake. Git gọi bằng danh sách đối số, không shell; thiếu commit hoặc blob thì FAIL, không skip. Không sửa `docs/milestones/**/evidence/**`, không sửa test khác của `tests/m2`.
    instrument: `tests/m2/test_p9_m2_exit_gate.py` xanh trên PostgreSQL 18.6 ở trạng thái cây hiện tại (8 migration, `dist` cũ); thêm hai ca âm trong chính tệp: sửa `sha256` của một artifact thuộc tiền tố trong manifest giả thì FAIL, `baseline_commit` không tồn tại thì FAIL (không skip); probe xác nhận hằng `M2_ACCEPTED_SHA` có 40 ký tự hex.
    counterexample: sửa `manifest.json` hoặc bằng chứng M2; nới `== 8` thành `>= 8` mà không ghim tám migration đầu; bỏ kiểm hash của `ui/dist` hoặc `tests/m2/e2e`; skip khi không có git; sửa test M2 khác.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider`
  - `python -m pytest tests/m2 -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.py').read_text(encoding='utf-8'); assert re.search('M2_ACCEPTED_SHA = [^0-9a-f]*[0-9a-f]{40}', t), 'pin M2_ACCEPTED_SHA'"`

### CP-2D-REGISTRY: Registry, binding, fixture, catalog test và tài liệu module

- kind: convergence_slice
- ownedPaths:
  - `docs/parallel-delivery/ownership-and-locks.yaml`
  - `docs/parallel-delivery/contract-registry.yaml`
  - `docs/parallel-delivery/acceptance-matrix.yaml`
  - `docs/parallel-delivery/bindings/**`
  - `tests/fixtures/contracts/**`
  - `docs/10-test-strategy.md`
  - `docs/modules/capability-*.md`
  - `README.md`
  - `CHANGELOG.md`
  - `HANDOFF.md`
  - `docs/delivery-evidence/cp-2d-registry/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`, `IMPL-PLAN-CONVERGENCE`
- resourceLocks: `LOCK-PARALLEL-REGISTRY`, `LOCK-DOC-AUTHORITY`, `LOCK-DOC-INDEX`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/README.md`, `docs/parallel-delivery/ownership-and-locks.yaml`, `docs/parallel-delivery/contract-registry.yaml`
- acceptance:
  - requirement: Xử lý các yêu cầu nhóm CP-2D của plan.md mục 2. (1) Ownership: thêm `tests/integration/{ingestion,catalog,creative,voice,render}/**` vào `PATH-SRC-INGESTION`, `PATH-SRC-CATALOG`, `PATH-SRC-CREATIVE`, `PATH-SRC-VOICE`, `PATH-SRC-RENDER`; thêm mẫu YC-HT-H-01 vào `PATH-SRC-CONTROL-UI` và khai `LOCK-H-01`..`LOCK-H-16` hoặc quy ước thay thế; thêm `src/controlplane/api/wiring/**` vào `PATH-COMPOSITION-ROOT`. (2) Mỗi seam chưa có binding nêu ở các kế hoạch (A→C, J→mọi phân hệ, H↔G, H↔J, A→B Tier, B→D, C→D, E→C, D→E, E→F, G→E, D↔G, D→I, F→I, I→F, J→F, F→G, J→G) có một binding JSON và `tests/fixtures/contracts/<seam>/payloads.json` theo `bindings/README.md`; thêm `ai_role` TTS vào fixture `j-provider-route`; `schema_version` và `recovery_epoch` là chuỗi (D8-G-10). (3) Catalog `docs/10-test-strategy.md`: đăng ký test ID SSRF của A và test ID mới đang dùng làm oracle; corpus có version dưới `tests/fixtures`. (4) Sửa `docs/modules/capability-*.md` theo mục «Đính chính» của từng kế hoạch (B mục 3, C mục 2, D mục 2 (g)–(l), E mục 2 (f)–(o), F mục 2 (f)–(n), G ERR-G-01..08, J ERR-J-01) và `TASK-CAP-E-VOICE`, `TASK-CAP-F-RENDERING` trong `acceptance-matrix.yaml`. (5) Đồng bộ `README.md`, `CHANGELOG.md`, `HANDOFF.md`. Không sửa `docs/09-contracts/**`; binding cần đổi contract thì BLOCKED.
    instrument: `tests/contract/test_bindings.py` xanh với binding và fixture mới; probe xác nhận `src/controlplane/api/wiring/**` và `tests/integration/catalog/**` có trong `ownership-and-locks.yaml`.
    counterexample: binding không có fixture; mẫu path trùng với owner khác; sửa `docs/09-contracts/**`; ghi giả định thành quyết định; test ID ngoài catalog dùng làm oracle.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/controlplane/api/wiring/**' in t and 'tests/integration/catalog/**' in t"`

### CP-3B-STATE-MACHINE: Đồ thị CT-STATE-005, CT-STATE-006 và kiểm tương đương của A

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/domain/statemachine/catalog_states.py`
  - `tests/unit/statemachine/test_cp3b_catalog_graphs.py`
  - `tests/unit/statemachine/test_cp3b_source_parity.py`
  - `docs/delivery-evidence/cp-3b-state-machine/report.md`
- dependsOn: `CP-2D-REGISTRY`, `A-03`, `A-05`, `A-07`, `C-02`
- resourceLocks: `LOCK-CONTRACT-STATE-MACHINES`, `LOCK-CONVERGENCE`
- bindingRefs: chỉ đọc `docs/09-contracts/12-state-machines.md` (CT-STATE-001, CT-STATE-002, CT-STATE-002A, CT-STATE-005, CT-STATE-006)
- acceptance:
  - requirement: Thêm module mới cạnh `__init__.py` (không sửa `__init__.py` và đồ thị đã có) chứa đồ thị CT-STATE-005 (discovery, rendition, availability) và CT-STATE-006 (image safety) đúng văn bản contract, cùng kiểu `transition_*` và `ForbiddenTransitionError` như các đồ thị hiện có. A giữ bảng chuyển trạng thái cục bộ; test tương đương kiểm bảng của A khớp danh sách cạnh CT-STATE-001, CT-STATE-002, CT-STATE-002A viết nội tuyến trong test. D, E, F không thêm máy trạng thái. G (PUC-G-02), I (`CLEANUP_AUTHORIZED` sang `DELETED`), J (CT-STATE-013), H giữ nguyên đồ thị chờ user; ghi từng quyết định này vào report.
    instrument: pytest bảng cạnh hợp lệ và cạnh bị cấm cho từng đồ thị mới; test tương đương so tập cạnh của A với tập cạnh trong contract.
    counterexample: thêm cạnh ngoài văn bản contract; sửa đồ thị đã nghiệm thu; hai nguồn sự thật cho cùng một đồ thị; đăng ký trạng thái view của H vào `controlplane.domain.statemachine`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/statemachine -q -p no:cacheprovider`
  - `python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_statemachines.py -q -p no:cacheprovider`

### CP-3-MIGRATIONS: Migration 0009 đến 0018

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/migrations/0009_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0010_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0011_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0012_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0013_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0014_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0015_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0016_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0017_*.sql`
  - `src/controlplane/infrastructure/db/migrations/0018_*.sql`
  - `tests/integration/migrations/test_cp3_migration_sequence.py`
  - `docs/delivery-evidence/cp-3-migrations/report.md`
- dependsOn: `CP-2C-M2-REGRESSION`, `A-08`, `B-3`, `C-09`, `D-13`, `E-15`, `F-16`, `G-10`, `H-04`, `I-04`, `J-09`
- resourceLocks: `LOCK-MIGRATION-SEQUENCE`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: Mỗi mẫu `NNNN_*.sql` khớp đúng hai tệp (`.sql` và `.rollback.sql`); tạo đúng mười cặp theo bảng plan.md mục 5.2 (tên tệp ở cột hai), số liên tục `0009`..`0018`, một owner; rollback chỉ gỡ đối tượng của chính nó; bảng lịch sử append-only chặn UPDATE và DELETE; `recovery_epoch` ở các bảng của 0010 và 0011 là text; không có pgvector. Không sửa `0001`..`0008`, `MigrationRunner` hay tệp `src/**` khác.
    instrument: test tích hợp: (a) tĩnh: tên tệp liên tục, đủ rollback, tên bảng và cột của plan.md có trong SQL; (b) PostgreSQL 18.6 dùng một lần: up tới 18, down về rỗng, up lại, phiên bản `[1..18]`, UPDATE vào bảng append-only bị từ chối, `recovery_epoch` kiểu text.
    counterexample: số nhảy hoặc trùng; thiếu rollback; slice phân hệ tạo migration; sửa `0001`..`0008`; append-only cho phép UPDATE; `recovery_epoch` còn integer; pgvector nằm trong `0014`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/migrations/test_cp3_migration_sequence.py -q -p no:cacheprovider`
  - `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider`
  - `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/storage tests/unit/security tests/integration/orchestration tests/integration/control_ui -q -p no:cacheprovider`

### CP-4-WIRING: Composition root, wiring theo phân hệ, route và event

- kind: convergence_slice
- ownedPaths:
  - `src/main.py`
  - `src/controlplane/api/main.py`
  - `src/controlplane/api/wiring/*.py` (một mô-đun mỗi phân hệ, trừ `__init__.py` của `CP-2B-DEPS`)
  - `src/controlplane/api/routes/control.py`
  - `src/controlplane/api/routes/modules/*.py`
  - `src/controlplane/application/control_api/**`
  - `src/controlplane/infrastructure/db/control_api_queries.py`
  - `src/controlplane/infrastructure/db/control_api_commands.py`
  - `src/controlplane/config/adapter.py`
  - `tests/integration/convergence/test_cp4_wiring.py`
  - `docs/delivery-evidence/cp-4-wiring/report.md`
- dependsOn: `USER-CKPT-D9-D10`, `CP-2B-DEPS`, `CP-3-MIGRATIONS`, `CP-3B-STATE-MACHINE`, `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J`, `A-17`, `B-10`, `C-07`, `D-17`, `E-19`, `F-21`, `H-08`, `H-09`, `J-18`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTROL-API`, `LOCK-SRC-CONFIG-SECURITY`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/g-activity-execution.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`, `docs/parallel-delivery/bindings/j-provider-route.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`; binding H↔G và H↔J do `CP-2D-REGISTRY` tạo
- acceptance:
  - requirement: Theo plan.md mục 6. `src/main.py` (tạo mới) chỉ đọc cấu hình, dựng `TransactionManager`, gọi `build_<phân hệ>_services(manager, config)` trong `api/wiring` rồi `create_app`; `create_app` mount `build_listing_router` và `build_metadata_router`. Route lệnh CT-API-003..006 trả receipt `accepted`, bắt buộc `Idempotency-Key` hoặc `If-Match`, ProblemDetail theo D8-H-06; `control.py` phân trang keyset bằng `ListQuery`; không có route đọc lại secret. Đăng ký event của A, B, D, E, F, G, I, J với publisher chung và `STREAM_EVENT_KINDS`. `RoutedInvocationService` (J-18) là adapter route J cho D và E; thay `DEFAULT_APPROVED_ENDPOINTS` có host `mock-9router` bằng danh sách từ cấu hình. Phân hệ chỉ nhận phụ thuộc qua port, không import chéo.
    instrument: test tích hợp dựng `create_app` với service giả của mọi phân hệ, gọi từng route mới (thiếu header thì 422, trùng khóa idempotency trả cùng receipt, revision sai thì 409), kiểm danh mục event kind và AST kiểm không import chéo giữa các gói phân hệ.
    counterexample: composition root phình thành logic nghiệp vụ; import `src.`; route trả secret; route lệnh trả `succeeded` thay vì `accepted`; host `mock-9router` còn trong danh sách mặc định.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider`
  - `python -m pytest tests/m2 tests/integration -q -p no:cacheprovider`
  - `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/control_ui -q -p no:cacheprovider`

### CP-4B-UI-SHELL: Nối màn hình vào App shell và dựng lại ui/dist

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/ui/src/App.tsx`
  - `src/controlplane/ui/src/index.css`
  - `src/controlplane/ui/src/api/client.ts`
  - `src/controlplane/ui/src/components/OperationsGrid.tsx`
  - `src/controlplane/ui/src/components/BatchesGrid.tsx`
  - `src/controlplane/ui/src/components/JobsGrid.tsx`
  - `src/controlplane/ui/src/types/api.ts`
  - `src/controlplane/ui/src/screens/**`
  - `src/controlplane/ui/dist/**` (allowLarge: true, chỉ cho đường dẫn này)
  - `tests/m2/e2e/cp4b-*.spec.ts`
  - `docs/delivery-evidence/cp-4b-ui-shell/report.md`
- dependsOn: `CP-4-WIRING`, `H-10`, `H-11`, `H-12`, `H-13`, `H-14`, `H-15`, `H-16`
- resourceLocks: `LOCK-UI-SHELL`, `LOCK-SRC-CONTROL-UI`, `LOCK-M2-REGRESSION`, `LOCK-CONVERGENCE`
- bindingRefs: binding H↔G và H↔J do `CP-2D-REGISTRY` tạo; `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: Theo plan.md mục 7. Nối `StatusPill`, `ErrorHoverDetail`, `screenRegistry`, `streamEventKinds`, `boundedEventDeduper` vào shell; thay logic pill, danh sách `eventKinds` và `Set`; thêm CSS `pill-waiting`, `pill-outcome-unknown`, `pill-unknown`; mở rộng `OperationItem`, `JobItem`; gỡ hoặc khóa nút `handleTriggerTestError` và đường `/test-driver` khỏi bản sản xuất; màn hình chỉ chuyển `backendStatus` từ `pending_module` sang sẵn sàng khi route tương ứng của CP-4 tồn tại; không cấp quyền sửa `article_body`, `script`, `secret`. Dựng lại `ui/dist` bằng `npm run build` trên runtime D9, xóa ba tệp băm cũ và thêm tệp mới; `allowLarge: true` chỉ cho `src/controlplane/ui/dist/**`. Năm spec M2 trong `tests/m2/e2e/` giữ nguyên byte; spec mới đặt tên `cp4b-*.spec.ts`.
    instrument: `npm run build` exit 0; pytest tĩnh `tests/unit/control_ui` (gồm guard H-16); probe xác nhận mọi tệp mà `dist/index.html` tham chiếu tồn tại và tệp băm cũ đã bị xóa. Control chạy thêm `npm run test:e2e` (cần PostgreSQL và Chromium của D9) và ghi bằng chứng; Worker không chạy lệnh này.
    counterexample: sửa spec M2 cũ; sửa `docs/milestones/**/evidence/**` hay manifest M2; `dist` không khớp mã nguồn vừa build; nút lỗi thử nghiệm hoặc `/test-driver` còn mở ở bản sản xuất; tệp lớn ngoài `dist` vượt 1024 KB.
- testCommands:
  - `git diff --check`
  - `npm run build` (thư mục làm việc `src/controlplane/ui`)
  - `python -m pytest tests/unit/control_ui -q -p no:cacheprovider`
  - `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.findall('assets/[A-Za-z0-9_.-]+', h); assert r and all((d / x).is_file() for x in r), r; assert not (d / 'assets' / 'index-Dd0WysB0.js').exists(), 'old hashed bundle must be gone'"`

### CP-5-COMPLETION: Completion unit-of-work trên PostgreSQL

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/orchestration/postgres_completion.py`
  - `src/controlplane/api/wiring/completion.py`
  - `tests/integration/convergence/test_cp5_completion_uow.py`
  - `docs/delivery-evidence/cp-5-completion/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `CP-4-WIRING`, `PERSIST-C`, `PERSIST-G`, `PERSIST-I`, `G-10`, `C-09`, `I-04`, `F-15`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/g-c-i-completion.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`, `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: Theo plan.md mục 9 (CT-ORC-008, `TST-WF-INV-017`). `PostgresCompletionUnitOfWork` cài `CompletionUnitOfWork` và `CompletionStorePort` của `commit_completion.py` trên một kết nối mượn từ `TransactionManager`; adapter `MediaUsagePort` gọi `MediaUsageRecorder.record_production_usage(uow, completion_id, request)` với `repository_factory` gắn cùng `uow` (kho PostgreSQL của PERSIST-C), không mở kết nối thứ hai. Thứ tự trong giao dịch: cổng G-09, ledger duy nhất, `transition_job` sang `COMPLETED`, chuyển capacity và VariantReservation sang `CONVERTED`, CAS revision registry, tăng bộ đếm batch, `MediaUsage`, outbox `VideoCompleted`, bản ghi cleanup eligibility (không lệnh xóa). Khóa dòng job bằng `FOR UPDATE`; ledger unique theo `video_job_id`; gọi lặp cùng input trả ledger cũ, khác input là `CONFLICT`; thiếu `cloud_location_verification_ref` thì `CLOUD_VERIFICATION_MISSING`; `recovery_epoch` so bằng `str()`. Nối vào composition root bằng `api/wiring/completion.py`.
    instrument: test tích hợp trên PostgreSQL 18.6 dùng một lần: tiêm lỗi trước và sau từng bước thì trạng thái trước và sau bằng nhau; gọi lặp 5 lần thì count bằng 1 (`TST-WF-INV-010`); registry stale không ghi gì; hai worker song song cùng job chỉ một thắng; không phát `VideoCompleted` khi rollback. Kết quả chỉ chứng minh logic và PostgreSQL cục bộ, không đóng G04 hay fault suite thật (CP7-G-03).
    counterexample: ledger commit nhưng MediaUsage mất; usage ghi bằng kết nối riêng; count tăng hai lần khi gọi lặp; `VideoCompleted` phát khi rollback; completion phát lệnh xóa local; completion không có cloud verification.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider`
  - `python -m pytest tests/integration/orchestration tests/integration/catalog tests/integration/storage tests/unit/catalog tests/unit/storage tests/unit/render -q -p no:cacheprovider`

### CP-6-WORKFLOW: Workflow Temporal, đăng ký activity và signal

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/workflows/*.py` (trừ `__init__.py` của `CP-2B-DEPS`)
  - `src/controlplane/api/wiring/workflow.py`
  - `src/source_ingestion/worker/activity_handler.py`
  - `tests/integration/collection/test_a18_worker_activity.py`
  - `tests/integration/convergence/test_cp6_workflow_static.py`
  - `tests/integration/convergence/test_cp6_workflow_catalog.py`
  - `tests/integration/convergence/test_cp6_video_production_flow.py`
  - `docs/delivery-evidence/cp-6-workflow/report.md`
- dependsOn: `USER-CKPT-D9-D10`, `CP-2B-DEPS`, `CP-5-COMPLETION`, `G-11`, `G-12`, `G-14`, `A-18`, `B-11`, `C-03`, `D-16`, `E-18`, `F-20`, `I-04`, `J-18`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-SRC-SOURCE-INGESTION`, `LOCK-COMPOSITION-ROOT`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/g-activity-execution.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`, `docs/parallel-delivery/bindings/j-provider-route.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: Theo plan.md mục 10. Cài sáu workflow của catalog G-12 bằng `temporalio==1.32.0`, sáu task queue, stage script, plan, tts chỉ ở queue desktop; đăng ký activity của A, B, C, D, E, F, I, J; signal `RunDebugStage`, `RetryStage`, `CreateNewVariant`, `RegenerateFromStage`; thiếu capability thì `WAITING_CAPABILITY` rồi resume theo `CapabilityView`; subscription `CollectedDocumentAvailable` sang B. Mọi timeout, retry, backoff lấy từ cấu hình J, không hằng số cứng. Đổi A-18 sang `GrantClaims` (YC-HT-G-10) bằng thay đổi tối thiểu trong `activity_handler.py` và test A-18, giữ test A-18 xanh. Lịch cloud giữ `NOT_READY` tới khi user duyệt múi giờ (PUC-G-01).
    instrument: test tĩnh AST: module workflow không import `time`, `random`, `socket`, không gọi `datetime.now`; test catalog: mọi stage có queue và mọi activity có handler; test luồng: `VideoProductionWorkflow` chạy bằng bộ chạy trong tiến trình với fake cho từng phân hệ và đi qua completion của CP-5. Replay trên Temporal Server thật thuộc CP7-G-03, không tuyên bố ở slice này.
    counterexample: workflow đọc đồng hồ hoặc mạng; timeout hoặc retry viết cứng; stage script chạy ở queue cloud; activity có side effect chạy khi thiếu `execution_grant`; DebugStage tự chạy stage kế; lịch production bật khi múi giờ chưa duyệt.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider`
  - `python -m pytest tests/unit/orchestration tests/integration/collection tests/unit/ingestion tests/integration/creative tests/integration/voice tests/integration/render tests/integration/config tests/unit/catalog tests/unit/storage -q -p no:cacheprovider`
