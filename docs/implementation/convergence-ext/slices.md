# Slice hội tụ mở rộng — IMPL-PLAN-CONVERGENCE-EXT

Nguồn: `docs/implementation/convergence-ext/plan.md`. Mở rộng `docs/implementation/convergence/slices.md`; Control biên dịch sáu slice dưới đây. `kind` là `dependency_slice` cho `CP-2B-PACKAGES` (sở hữu `src/controlplane/pyproject.toml`) và `convergence_slice` cho các slice còn lại.

## Quy tắc chung cho mọi slice

- Chỉ sửa đúng các tệp trong `ownedPaths` và giữ khóa trong `resourceLocks`; mọi slice giữ `LOCK-CONVERGENCE` nên chạy tuần tự.
- Cấm sửa `docs/milestones/**/evidence/**`, kế hoạch phân hệ `docs/implementation/a` đến `j` và `protected-checkouts/**`. Ngoại lệ duy nhất cho `docs/09-contracts/12-state-machines.md` là `CP-3C-STATE-EDGES` (ARCHITECTURE_CHANGE do user duyệt ngày 20/10/2026, đúng hai cạnh).
- Cạnh tới adapter PostgreSQL viết `GATE-PERSIST-<X>`; cổng `GATE-CP-2D-REGISTRY`, `GATE-CP-5-COMPLETION`, `GATE-CP-6-WORKFLOW` do slice cùng mã thả khi có Auditor PASS.
- Không thêm thư viện; không gọi dịch vụ thật, không đọc `Credentials/`; import root `src/`, không tiền tố `src.`.
- Test-first: thấy RED đúng oracle rồi mới implement; bằng chứng ở `docs/delivery-evidence/<id viết thường>/report.md`.
- `testCommands` chạy bằng interpreter khoá của runtime D9.
- Mỗi slice có tiêu đề cấp 3 dạng `CP-<mã>: <tên>`, theo sau là kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance (requirement, instrument, counterexample), testCommands và tùy chọn notes.

### CP-2B-RUNTIME-PATHS: Ghi ba pin D9 đã đo vào tools/runtime/runtime.lock.json

- kind: convergence_slice
- ownedPaths:
  - `tools/runtime/runtime.lock.json`
  - `docs/delivery-evidence/cp-2b-runtime-paths/report.md`
- dependsOn: `IMPL-PLAN-CONVERGENCE`, `IMPL-PLAN-CONVERGENCE-EXT`
- resourceLocks: `LOCK-DEPENDENCY-UNIVERSE`, `LOCK-CONVERGENCE`
- bindingRefs: không có binding riêng; bám plan.md mục 3 của kế hoạch này và mục 4 của `docs/implementation/convergence/plan.md`
- acceptance:
  - requirement: Tạo `tools/runtime/runtime.lock.json` (JSON UTF-8, không BOM) đúng cấu trúc: `versions` có đúng sáu khóa `python` = `3.13.15`, `uv` = `0.12.13`, `node` = `22.17.0`, `npm` = `10.9.2`, `postgresql` = `18.6`, `temporal_server` = `1.31.2`; `pins` có đúng ba khóa `ffmpeg`, `temporal_server_binary`, `postgresql_image`, mỗi khóa có `sha256` (hex thường 64 ký tự, chép từ plan.md mục 3, cũng có trong probe dưới đây) và `status` = `PINNED`; riêng `ffmpeg` thêm `archive_name` = `2025-03-13-git-958c46800e-essentials_build` và `measured_artifact` = `ffmpeg.exe`. Giá trị lấy từ ghi chú Control ngày 20/10/2026; không ghi `null`, không đo lại, không bịa giá trị.
    instrument: probe `json` so từng pin với giá trị Control, đủ sáu khóa phiên bản, `status` = `PINNED`.
    counterexample: bịa hoặc đổi một ký tự sha256; ghi `null` cho pin đã đo; thiếu khóa phiên bản; sha256 ffmpeg tính trên archive thay vì `ffmpeg.exe`; sửa tệp ngoài ownedPaths.
- testCommands:
  - `git diff --check`
  - `python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/runtime/runtime.lock.json').read_text(encoding='utf-8')); assert d['versions'] == {'python': '3.13.15', 'uv': '0.12.13', 'node': '22.17.0', 'npm': '10.9.2', 'postgresql': '18.6', 'temporal_server': '1.31.2'}, d['versions']; p = d['pins']; assert set(p) == {'ffmpeg', 'temporal_server_binary', 'postgresql_image'}, p; e = {'ffmpeg': 'f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480', 'temporal_server_binary': 'b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da', 'postgresql_image': '4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280'}; assert all(p[k]['sha256'] == v and p[k]['status'] == 'PINNED' for k, v in e.items()), p; assert p['ffmpeg']['archive_name'] and p['ffmpeg']['measured_artifact'] == 'ffmpeg.exe', p['ffmpeg']"`
- notes: BL-CV-14 (plan.md mục 2): slice thả cổng GATE-CP-2B-DEPS-PATHS cùng CP-2B-PACKAGES. CP-2B-DEPS đã biên dịch không chứa tệp này; nếu Control mở phong bì cho CP-2B-DEPS thì phần ghi tệp vẫn chỉ có một owner. Giá trị khác ba giá trị Control là lệch và FAIL.

### CP-2B-PACKAGES: Đăng ký bốn gói trong pyproject và tạo ba __init__.py rỗng

- kind: dependency_slice
- ownedPaths:
  - `src/controlplane/pyproject.toml`
  - `src/controlplane/api/routes/modules/__init__.py`
  - `src/controlplane/api/wiring/__init__.py`
  - `src/controlplane/application/orchestration/workflows/__init__.py`
  - `docs/delivery-evidence/cp-2b-packages/report.md`
- dependsOn: `IMPL-PLAN-CONVERGENCE`, `IMPL-PLAN-CONVERGENCE-EXT`
- resourceLocks: `LOCK-DEPENDENCY-UNIVERSE`, `LOCK-CONVERGENCE`
- bindingRefs: không có binding riêng; bám mục 6 của `docs/implementation/convergence/plan.md`
- acceptance:
  - requirement: Trong `src/controlplane/pyproject.toml` khai trong cả `packages` và `[tool.setuptools.package-dir]` đúng bốn gói: `controlplane.api.routes.modules` = `api/routes/modules`, `controlplane.api.wiring` = `api/wiring`, `controlplane.application.orchestration.workflows` = `application/orchestration/workflows`, `controlplane.infrastructure.storage` = `infrastructure/storage`. Tạo ba `__init__.py` rỗng (0 byte) ở `api/routes/modules`, `api/wiring`, `application/orchestration/workflows` (thư mục `api/wiring` và `workflows` chưa tồn tại); `infrastructure/storage/__init__.py` đã có nên không tạo lại. Chỉ sửa hai bảng `packages` và `package-dir`: không thêm, không sửa, không nâng dependency nào và không sửa `uv.lock`, `requirements.lock`, `package-lock.json` (việc đó thuộc CP-2B-DEPS, chạy tuần tự dưới cùng `LOCK-DEPENDENCY-UNIVERSE`). Không có gói `controlplane.workflows`.
    instrument: pytest `tests/m2/test_p0_packaging.py` và ba probe: (1) `tomllib` mọi dependency có `==`; (2) `tomllib` bốn gói có trong cả `packages` và `package-dir` và thư mục tương ứng có `__init__.py`; (3) ba `__init__.py` mới rỗng.
    counterexample: gói mới có `__init__.py` nhưng không khai ở pyproject (thiếu trong wheel); khai ở `packages` mà thiếu `package-dir`; `__init__.py` có nội dung; đổi phiên bản thư viện hay lockfile; tạo gói `controlplane.workflows`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider`
- `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert x and all('==' in i for i in x), x"`
- `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['setuptools']; n = ['controlplane.api.routes.modules', 'controlplane.api.wiring', 'controlplane.application.orchestration.workflows', 'controlplane.infrastructure.storage']; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; assert all(k in s['packages'] and k in s['package-dir'] for k in n), n; assert all(pathlib.Path('src/controlplane', s['package-dir'][k], u).is_file() for k in n), n"`
  - `python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; b = pathlib.Path('src/controlplane'); assert all((b / d / u).read_bytes() == b'' for d in ['api/routes/modules', 'api/wiring', 'application/orchestration/workflows']), 'three new init files must be empty'"`
- notes: BL-CV-14 (plan.md mục 2): slice thả cổng GATE-CP-2B-DEPS-PATHS cùng CP-2B-RUNTIME-PATHS; CP-4-WIRING và CP-6-WORKFLOW cần `api/wiring/__init__.py` và `workflows/__init__.py` từ slice này. Hai dòng chép từ kế hoạch gốc phải là bản nguyên văn, không gõ lại.

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
- dependsOn: CP1-CONTRACT-BINDING, CP2A-LAYOUT, IMPL-PLAN-CONVERGENCE, IMPL-PLAN-CONVERGENCE-EXT
- resourceLocks: `LOCK-PARALLEL-REGISTRY`, `LOCK-DOC-AUTHORITY`, `LOCK-DOC-INDEX`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/README.md`, `docs/parallel-delivery/ownership-and-locks.yaml`, `docs/parallel-delivery/contract-registry.yaml`
- acceptance:
  - requirement: Xử lý các yêu cầu nhóm CP-2D của plan.md mục 2. (1) Ownership: thêm `tests/integration/{ingestion,catalog,creative,voice,render}/**` vào `PATH-SRC-INGESTION`, `PATH-SRC-CATALOG`, `PATH-SRC-CREATIVE`, `PATH-SRC-VOICE`, `PATH-SRC-RENDER`; thêm mẫu YC-HT-H-01 vào `PATH-SRC-CONTROL-UI` và khai `LOCK-H-01`..`LOCK-H-16` hoặc quy ước thay thế; thêm `src/controlplane/api/wiring/**` vào `PATH-COMPOSITION-ROOT`. (2) Mỗi seam chưa có binding nêu ở các kế hoạch (A→C, J→mọi phân hệ, H↔G, H↔J, A→B Tier, B→D, C→D, E→C, D→E, E→F, G→E, D↔G, D→I, F→I, I→F, J→F, F→G, J→G) có một binding JSON và `tests/fixtures/contracts/<seam>/payloads.json` theo `bindings/README.md`; thêm `ai_role` TTS vào fixture `j-provider-route`; `schema_version` và `recovery_epoch` là chuỗi (D8-G-10). (3) Catalog `docs/10-test-strategy.md`: đăng ký test ID SSRF của A và test ID mới đang dùng làm oracle; corpus có version dưới `tests/fixtures`. (4) Sửa `docs/modules/capability-*.md` theo mục «Đính chính» của từng kế hoạch (B mục 3, C mục 2, D mục 2 (g)–(l), E mục 2 (f)–(o), F mục 2 (f)–(n), G ERR-G-01..08, J ERR-J-01) và `TASK-CAP-E-VOICE`, `TASK-CAP-F-RENDERING` trong `acceptance-matrix.yaml`. (5) Đồng bộ `README.md`, `CHANGELOG.md`, `HANDOFF.md`. Không sửa `docs/09-contracts/**`; binding cần đổi contract thì BLOCKED. Không sửa mục CONTRACT-STATE-MACHINES của contract-registry.yaml (thuộc CP-3C-STATE-EDGES, chạy sau slice này).
    instrument: `tests/contract/test_bindings.py` xanh với binding và fixture mới; probe xác nhận `src/controlplane/api/wiring/**` và `tests/integration/catalog/**` có trong `ownership-and-locks.yaml`.
    counterexample: binding không có fixture; mẫu path trùng với owner khác; sửa `docs/09-contracts/**`; ghi giả định thành quyết định; test ID ngoài catalog dùng làm oracle.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/controlplane/api/wiring/**' in t and 'tests/integration/catalog/**' in t"`
- notes: BL-CV-01 và BL-CV-06 (plan.md mục 2): slice thả cổng GATE-CP-2D-REGISTRY khi có Auditor PASS; CP-3B-STATE-MACHINE, CP-3C-STATE-EDGES, CP-4-WIRING và CP-4B-UI-SHELL chờ cổng này (cần binding H↔G, H↔J và mẫu src/controlplane/api/wiring/** trong PATH-COMPOSITION-ROOT). Thiếu gate thì BLOCKED; Worker không sửa tệp ngoài ownedPaths đã cấp.

### CP-3C-STATE-EDGES: Hai cạnh state machine đã duyệt (PUC-J-03, YC-HT-I-04) và đồng bộ registry

- kind: convergence_slice
- ownedPaths:
  - `docs/09-contracts/12-state-machines.md`
  - `docs/parallel-delivery/contract-registry.yaml`
  - `src/controlplane/domain/config_security/status_graph.py`
  - `src/controlplane/domain/config_security/external_account.py`
  - `src/controlplane/application/config_security/account_recovery.py` (tạo mới)
  - `src/controlplane/application/storage_meta/__init__.py`
  - `tests/unit/config/test_j_status_graph.py`
  - `tests/unit/config/test_j_account_recovery.py` (tạo mới)
  - `tests/unit/storage/test_i_cleanup_deleted.py` (tạo mới)
  - `docs/delivery-evidence/cp-3c-state-edges/report.md`
- dependsOn: `CP-3B-STATE-MACHINE`, `CP-2D-REGISTRY`, `IMPL-PLAN-CONVERGENCE-EXT`
- resourceLocks: `LOCK-CONTRACT-STATE-MACHINES`, `LOCK-CONTRACT-SOURCE`, `LOCK-PARALLEL-REGISTRY`, `LOCK-SRC-STORAGE`, `LOCK-SRC-CONFIG-SECURITY`, `LOCK-CONVERGENCE`
- bindingRefs: chỉ đọc `docs/09-contracts/12-state-machines.md` (CT-STATE-012, CT-STATE-013) và mục CONTRACT-STATE-MACHINES của `docs/parallel-delivery/contract-registry.yaml`
- acceptance:
  - requirement: Cơ sở: ARCHITECTURE_CHANGE do user duyệt ngày 20/10/2026 (quyết định 3), đúng hai cạnh; giữ nguyên PUC-G-02 và mọi cạnh khác. (1) PUC-J-03: thêm đúng hai cạnh `(DEGRADED, ENABLED)` và `(INVALID, ENABLED)` vào `ACCOUNT_EDGES` của `status_graph.py` (5 thành 7 cạnh) và sửa docstring; `REVOKED` vẫn không có cạnh thoát. `external_account.py` thêm hàm thuần `recover_after_passing_test(account)`: chỉ từ `DEGRADED` hoặc `INVALID`, dùng `require_account_transition`, trả tài khoản `ENABLED` với `revision` + 1. `account_recovery.py` thêm `AccountRecoveryService.recover(account, receipt, expected_revision)`: chỉ phục hồi khi `receipt.ok is True`, `receipt.external_account_id` khớp tài khoản và `expected_revision == account.revision` (lệch thì `RevisionConflictError`); lần kiểm không đạt hoặc trạng thái khác `DEGRADED`/`INVALID` thì trả tài khoản cũ; không tự probe, không chạm secret. (2) YC-HT-I-04: thêm `ArtifactLocationStore.record_cleanup_deleted(**kwargs)`, đường ghi duy nhất sang `DELETED`: location đang `CLEANUP_AUTHORIZED`, `expected_revision` khớp, `CleanupAuthorization` khớp location, artifact version và hash, `cleanup_deleted is True` (kết quả `CleanupResult.deleted` của `LocalCleanupExecutor`), `cleanup_receipt_ref` không rỗng và không khớp `_UNSAFE_REFERENCE`; gọi `transition_artifact_location(requested_state=DELETED)` rồi `update_location` với `evidence=None` để không đè `verification_evidence_ref`. `transition` và `validate_transition` vẫn từ chối `DELETED`; không thêm phương thức tên `delete`; không sửa đồ thị `statemachine`, migration hay `infrastructure/db/storage_meta`. (3) `test_j_status_graph.py` đổi sang 7 cạnh; không sửa test M2.
    instrument: pytest: bảng cặp trạng thái tài khoản chỉ cho phép đúng 7 cạnh; `test_j_account_recovery.py`: `DEGRADED` và `INVALID` với receipt đạt về `ENABLED` (revision + 1), còn receipt không đạt, tài khoản `REVOKED`, `DISABLED`, `ENABLED`, receipt của tài khoản khác và `expected_revision` lệch đều không phục hồi; `test_i_cleanup_deleted.py` (repository giả trong test): ghi `DELETED` chỉ khi đủ bằng chứng; thiếu `cleanup_receipt_ref`, `cleanup_deleted` sai, hash lệch hoặc location không ở `CLEANUP_AUTHORIZED` đều bị từ chối; `transition(requested_state=DELETED)` vẫn bị từ chối.
    counterexample: mở cạnh ngoài hai cạnh (ví dụ `REVOKED` → `ENABLED`, `DISABLED` → `DEGRADED`, `DELETED` từ trạng thái khác); phục hồi khi lần kiểm không đạt; cho `transition` chung ghi `DELETED`; đổi PUC-G-02, CT-STATE-008 hay CT-STATE-010; sửa test M2.
  - requirement: Sửa `docs/09-contracts/12-state-machines.md` đúng hai mục: CT-STATE-013 (thêm cạnh phục hồi PUC-J-03: `DEGRADED` hoặc `INVALID` về `ENABLED` chỉ khi lần kiểm CT-ACC-002 của chính tài khoản đạt; thay câu «graph dưới đây không cấp quyền mở rộng lifecycle account» bằng câu nêu ngoại lệ này; giữ dòng `REVOKED` là terminal cho credential version) và CT-STATE-012 (thêm đoạn: cạnh `CLEANUP_AUTHORIZED` → `DELETED` (YC-HT-I-04) chỉ được ghi qua đường ghi có bằng chứng cleanup, không có đường khác). Cập nhật trong `docs/parallel-delivery/contract-registry.yaml`, mục CONTRACT-STATE-MACHINES, hai dòng `current_revision` (dạng `sha256:<hex>`) và `source_sha256` thành sha256 byte của tệp contract sau khi sửa, tính bằng probe in ra, không gõ tay, cùng slice; giá trị cũ là `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28`. Không sửa mục nào khác của contract hay registry.
    instrument: probe so sha256 byte tệp contract với hai giá trị của registry và xác nhận giá trị cũ đã biến mất; probe xác nhận contract nêu `PUC-J-03` và `YC-HT-I-04`; `tests/contract/test_bindings.py` vẫn xanh.
    counterexample: sửa contract mà không cập nhật `source_sha256` và `current_revision`; sha256 gõ tay hoặc tính trên bản đã chuẩn hóa dòng; mở thêm cạnh ngoài hai cạnh đã duyệt; sửa mục contract khác trong registry.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config tests/unit/storage tests/unit/statemachine -q -p no:cacheprovider`
  - `python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/contract/test_bindings.py -q -p no:cacheprovider`
  - `python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery/contract-registry.yaml').read_text(encoding='utf-8'); h = hashlib.sha256(pathlib.Path('docs/09-contracts/12-state-machines.md').read_bytes()).hexdigest(); m = re.search('id: CONTRACT-STATE-MACHINES[^@]*?current_revision: sha256:([0-9a-f]{64})[^@]*?source_sha256: ([0-9a-f]{64})', t); assert m is not None and m.group(1) == h and m.group(2) == h, h; assert '2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28' not in t, 'old hash must be gone'"`
  - `python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines.md').read_text(encoding='utf-8'); assert 'PUC-J-03' in t and 'YC-HT-I-04' in t, 'contract names both approved edges'"`
- notes: Cạnh đã duyệt duy nhất là PUC-J-03 và YC-HT-I-04; PUC-G-02 giữ nguyên. `CP-3B-STATE-MACHINE` và `CP-2D-REGISTRY` là cạnh bắt buộc (cùng sửa registry và khóa state machine). Control chạy `tests/m2` (gồm `test_p5b_artifact_metadata.py`) trên PostgreSQL 18.6 sau slice; Worker không đổi test M2. OI-EXT-01: nơi lưu `cleanup_receipt_ref` ngoài receipt của cleanup executor, không thêm cột hay migration trong slice này.

### CP-5-COMPLETION: Completion unit-of-work trên PostgreSQL

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/orchestration/postgres_completion.py`
  - `src/controlplane/api/wiring/completion.py`
  - `tests/integration/convergence/test_cp5_completion_uow.py`
  - `docs/delivery-evidence/cp-5-completion/report.md`
- dependsOn: CP-3-MIGRATIONS, CP-4-WIRING, GATE-PERSIST-C, GATE-PERSIST-G, GATE-PERSIST-I, G-10, C-09, I-04, F-15, CP-2D-REGISTRY, CP-2B-PACKAGES
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/g-c-i-completion.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`, `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: Theo plan.md mục 9 (CT-ORC-008, `TST-WF-INV-017`). `PostgresCompletionUnitOfWork` cài `CompletionUnitOfWork` và `CompletionStorePort` của `commit_completion.py` trên một kết nối mượn từ `TransactionManager`; adapter `MediaUsagePort` gọi `MediaUsageRecorder.record_production_usage(uow, completion_id, request)` với `repository_factory` gắn cùng `uow` (kho PostgreSQL của GATE-PERSIST-C), không mở kết nối thứ hai. Thứ tự trong giao dịch: cổng G-09, ledger duy nhất, `transition_job` sang `COMPLETED`, chuyển capacity và VariantReservation sang `CONVERTED`, CAS revision registry, tăng bộ đếm batch, `MediaUsage`, outbox `VideoCompleted`, bản ghi cleanup eligibility (không lệnh xóa). Khóa dòng job bằng `FOR UPDATE`; ledger unique theo `video_job_id`; gọi lặp cùng input trả ledger cũ, khác input là `CONFLICT`; thiếu `cloud_location_verification_ref` thì `CLOUD_VERIFICATION_MISSING`; `recovery_epoch` so bằng `str()`. Nối vào composition root bằng `api/wiring/completion.py`. Adapter đặt đúng `src/controlplane/infrastructure/db/orchestration/postgres_completion.py` (gói `controlplane.infrastructure.db.orchestration` đã khai ở `pyproject.toml`); không tạo gói mới `infrastructure/db/completion` và không có `__init__.py` mới (BL-CV-11). Kho PostgreSQL của `GATE-PERSIST-C` là điều kiện: không viết kho tạm hay fake thay cho nó trong phép kiểm giao dịch.
    instrument: test tích hợp trên PostgreSQL 18.6 dùng một lần: tiêm lỗi trước và sau từng bước thì trạng thái trước và sau bằng nhau; gọi lặp 5 lần thì count bằng 1 (`TST-WF-INV-010`); registry stale không ghi gì; hai worker song song cùng job chỉ một thắng; không phát `VideoCompleted` khi rollback. Kết quả chỉ chứng minh logic và PostgreSQL cục bộ, không đóng G04 hay fault suite thật (CP7-G-03).
    counterexample: ledger commit nhưng MediaUsage mất; usage ghi bằng kết nối riêng; count tăng hai lần khi gọi lặp; `VideoCompleted` phát khi rollback; completion phát lệnh xóa local; completion không có cloud verification; adapter dời sang gói mới không khai đóng gói (thiếu trong wheel); dependsOn bỏ `GATE-PERSIST-C`, `GATE-PERSIST-G`, `GATE-PERSIST-I` nên phép kiểm chạy trên kho tạm hay fake.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider`
  - `python -m pytest tests/integration/orchestration tests/integration/storage tests/unit/catalog tests/unit/storage tests/unit/render -q -p no:cacheprovider`
  - `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['setuptools']; k = 'controlplane.infrastructure.db.orchestration'; assert k in s['packages'] and k in s['package-dir'], k; assert pathlib.Path('src/controlplane/infrastructure/db/orchestration/postgres_completion.py').is_file(), 'adapter path'; assert not pathlib.Path('src/controlplane/infrastructure/db/completion').exists(), 'no new package db/completion'"`
- notes: BL-CV-08 và BL-CV-11 (plan.md mục 2): slice thả cổng GATE-CP-5-COMPLETION khi có Auditor PASS. api/wiring/completion.py nối được vì BL-CV-06 đã đóng bởi CP-2D-REGISTRY và api/wiring/__init__.py do CP-2B-PACKAGES tạo. Adapter ở infrastructure/db/orchestration/ (gói đã khai trong pyproject), không dời sang gói khác; thiếu phong bì ở thư mục này thì BLOCKED. GATE-PERSIST-C, GATE-PERSIST-G, GATE-PERSIST-I là cạnh bắt buộc, không bỏ khỏi dependsOn.

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
- dependsOn: `USER-CKPT-D9-D10`, `CP-2B-DEPS`, `CP-5-COMPLETION`, `G-11`, `G-12`, `G-14`, `A-18`, `B-11`, `C-03`, `D-16`, `E-18`, `F-20`, `I-04`, `J-18`, CP-2D-REGISTRY, CP-2B-PACKAGES
- resourceLocks: `LOCK-SRC-ORCHESTRATION`, `LOCK-SRC-SOURCE-INGESTION`, `LOCK-COMPOSITION-ROOT`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/g-activity-execution.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`, `docs/parallel-delivery/bindings/j-provider-route.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: Theo plan.md mục 10. Cài sáu workflow của catalog G-12 bằng `temporalio==1.32.0`, sáu task queue, stage script, plan, tts chỉ ở queue desktop; đăng ký activity của A, B, C, D, E, F, I, J; signal `RunDebugStage`, `RetryStage`, `CreateNewVariant`, `RegenerateFromStage`; thiếu capability thì `WAITING_CAPABILITY` rồi resume theo `CapabilityView`; subscription `CollectedDocumentAvailable` sang B. Mọi timeout, retry, backoff lấy từ cấu hình J, không hằng số cứng. Đổi A-18 sang `GrantClaims` (YC-HT-G-10) bằng thay đổi tối thiểu trong `activity_handler.py` và test A-18, giữ test A-18 xanh. Lịch cloud giữ `NOT_READY` tới khi user duyệt múi giờ (PUC-G-01).
    instrument: test tĩnh AST: module workflow không import `time`, `random`, `socket`, không gọi `datetime.now`; test catalog: mọi stage có queue và mọi activity có handler; test luồng: `VideoProductionWorkflow` chạy bằng bộ chạy trong tiến trình với fake cho từng phân hệ và đi qua completion của CP-5. Replay trên Temporal Server thật thuộc CP7-G-03, không tuyên bố ở slice này.
    counterexample: workflow đọc đồng hồ hoặc mạng; timeout hoặc retry viết cứng; stage script chạy ở queue cloud; activity có side effect chạy khi thiếu `execution_grant`; DebugStage tự chạy stage kế; lịch production bật khi múi giờ chưa duyệt.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider`
  - `python -m pytest tests/unit/orchestration tests/integration/collection tests/unit/ingestion tests/integration/creative tests/integration/voice tests/integration/render tests/unit/config tests/unit/catalog tests/unit/storage -q -p no:cacheprovider`
- notes: BL-CV-09, BL-CV-10, BL-CV-15 (plan.md mục 2): slice thả cổng GATE-CP-6-WORKFLOW khi có Auditor PASS. BL-CV-09: đổi A-18 sang GrantClaims (src/controlplane/domain/orchestration/fencing.py) bằng thay đổi tối thiểu ở activity_handler.py và test A-18, giữ test A-18 xanh; cần khóa LOCK-SRC-SOURCE-INGESTION do Control xác nhận. BL-CV-10: api/wiring/workflow.py chờ CP-2D-REGISTRY (BL-CV-06), CP-2B-PACKAGES và CP-5-COMPLETION PASS. BL-CV-15: không loại CP-6 khỏi kế hoạch; replay Temporal thật thuộc CP7-G-03. Đổi contract là ARCHITECTURE_CHANGE, chờ user.
