# Slice triển khai Phân hệ J — Cấu hình, tài khoản dịch vụ và bí mật

Nguồn: `docs/implementation/j/plan.md`. Mỗi slice là `work_package_slice`; Control biên dịch trong phong bì policy.

## Quy tắc chung cho mọi slice

- Phong bì sửa: `src/controlplane/domain/config_security/**`, `src/controlplane/application/config_security/**`, `src/controlplane/infrastructure/db/config_security/**`, `src/controlplane/infrastructure/security/**`, `src/controlplane/config/**`, `src/controlplane/security/**`, `tests/unit/security/**`, `tests/unit/config/**`, `tests/integration/config/**` và tệp bằng chứng `docs/delivery-evidence/<task-id viết thường>/report.md`. Mỗi slice chỉ sửa đúng các tệp ghi ở ownedPaths của chính nó, là tệp mới đặt cạnh mã cũ.
- Không sửa: ba `__init__.py` P5A của `config_security` (domain, application, infrastructure/db); mọi tệp `src/controlplane/config/*.py` và `src/controlplane/security/*.py` đã có; `src/controlplane/infrastructure/security/redaction.py` và `secret_scanner.py` (được `tests/m2`, `tests/unit/security` và probe P7A bảo vệ); migration, composition root, lockfile/`pyproject.toml`, `tests/m2/**`, `ui/dist`, `App.tsx`, `src/controlplane/domain/statemachine/**`, control API hay workflow. Nhu cầu loại này gửi IMPL-PLAN-CONVERGENCE (plan.md mục 9).
- Không thêm thư viện; chỉ stdlib và mã controlplane đã có. Không gọi mạng, Drive, OAuth hay AI thật; không đọc `Credentials/` hay bí mật; secret trong test là canary hằng số. Phân hệ khác được thay bằng fixture CP1 (`tests/fixtures/contracts/**`) và fake định nghĩa ngay trong tệp test. Test có đường gọi socket phải monkeypatch `socket.create_connection` và `socket.getaddrinfo` để ném lỗi.
- Import root `src/`, dạng `controlplane.…`, không có tiền tố `src.`. Không thêm `__init__.py` vào thư mục test. Tên tệp test `test_j_<chủ đề>.py`; docstring đầu tệp test có dòng `coveredIds:`.
- Test-first: viết test trước, tạo module với chữ ký đúng nhưng thân hàm `raise NotImplementedError`, chạy để thấy RED do assertion hoặc NotImplementedError; ImportError hay thiếu tệp không phải RED hợp lệ. Sau đó implement tới GREEN. Không tạo test chỉ mô tả hành vi đã có sẵn.
- Dữ liệu thời gian dùng `datetime` có múi giờ do caller truyền; mã slice không đọc đồng hồ hay múi giờ hệ thống (D8-J-06). Tiền dùng `Decimal`, không `float`.
- Lệnh kiểm chạy bằng interpreter khoá của lane; ghi lệnh, exit code, kết quả RED và GREEN vào report.md của slice.
- Khuôn slice: tiêu đề cấp 3 `J-<số>: <tên>`, tiếp theo là các mục kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance (requirement, instrument, counterexample), testCommands, coveredIds theo đúng thứ tự này. Khóa tài nguyên mỗi slice là `LOCK-J-<số>`.
- DAG: wave 1 gồm J-01, J-02, J-03, J-04, J-05, J-07, J-08; các wave sau theo dependsOn (plan.md mục 10).

## Danh sách slice


### J-01: Validator binding ProviderRoute (CT-AI-ROUTE-001)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/config_security/route_binding.py`
  - `tests/unit/config/test_j_route_binding.py`
  - `docs/delivery-evidence/j-01/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-J-01`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: Dataclass frozen `ProviderRouteRequest` (8 trường, `health_quota_ref` tùy chọn) và `ProviderRouteDecision` (10 trường, `project_ref` tùy chọn) đúng tên, kiểu, required của BINDING-J-PROVIDER-ROUTE 1.0.0. Hằng đặc tả trường trong mã: `REQUEST_FIELDS`, `DECISION_FIELDS`, `FORBIDDEN_DECISION_FIELDS`. `validate_route_request(payload: dict) -> list[dict]` và `validate_route_decision(payload: dict) -> list[dict]` trả lỗi `{"code": ..., "field": ...}` với code `missing_required`, `wrong_type`, `forbidden_field`. Decision chứa `secret_value`, `api_key`, `access_token` hoặc `refresh_token` (so khóa không phân biệt hoa thường) bị `forbidden_field`. `rationale_codes` phải là mảng chuỗi. Trường lạ khác bị bỏ qua (forward-compat). Không import `controlplane.config.router` hay `controlplane.config.adapter`.
    instrument: Test đọc fixture: mọi payload `valid` trả `[]`, mọi case `invalid` trả đúng `expected_error`; test drift so tên, kiểu, required của hằng đặc tả với tệp `j-provider-route.json`; thêm case `rationale_codes=[1]` là `wrong_type` và khóa `API_KEY` là `forbidden_field`.
    counterexample: Decision chứa api_key được chấp nhận; `fallback_order` là chuỗi được chấp nhận; thiếu trường required mà không báo; tên trường lệch binding.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider`
- coveredIds: CT-AI-ROUTE-001, TST-SEC-INV-012

### J-02: Redaction sâu và quét canary (CT-SEC-003 điều 6)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/security/secret_redaction.py`
  - `tests/unit/security/test_j_secret_redaction.py`
  - `docs/delivery-evidence/j-02/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-J-02`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: Module mới, không sửa `redaction.py`. `redact_value(value: Any) -> Any` đệ quy qua dict, list, tuple, set: khóa nhạy cảm (không phân biệt hoa thường: password, secret, token, api_key, apikey, authorization, credential, private_key, client_secret, refresh_token, access_token, session_uri, upload_session) có giá trị thay bằng `[REDACTED]`; chuỗi đi qua `redact_text` của `controlplane.infrastructure.security.redaction` rồi thêm mẫu bổ sung: `sk-` kèm từ 8 ký tự, `AIza` kèm 35 ký tự, JWT dạng `eyJ…`, token `ya29.`, URL có query `token=`, `key=`, `upload_id=` hoặc `signature=`. `redact_exception(exc) -> str` chỉ trả tên lớp và thông điệp đã redact. `find_canaries(canaries: Sequence[str], *outputs: Any) -> list[str]` trả canary xuất hiện trong str, repr hoặc JSON của outputs. Lớp `SecretValue`: `__repr__`, `__str__`, `__format__` luôn `[REDACTED]`, `reveal()` mới trả giá trị, pickle và json bị từ chối bằng `TypeError`. Lỗi bên trong redaction trả `[REDACTED]`, không trả giá trị gốc (fail-closed).
    instrument: Pytest với canary hằng số: đưa canary qua dict lồng, list, exception message, repr dataclass chứa `SecretValue`, URL có token, header Authorization; sau redact `find_canaries` trả `[]`; case đối chứng không redact thì `find_canaries` phát hiện canary; `SecretValue` không `json.dumps`, không `pickle.dumps`.
    counterexample: Canary còn trong exception message; khóa lồng bị bỏ sót; `repr(SecretValue)` lộ giá trị; redaction lỗi trả giá trị gốc.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cacheprovider`
- coveredIds: TST-SEC-INV-012, CT-SEC-003, QR-SEC-002

### J-03: Kế hoạch publish ConfigRevision, lineage và rollback (CT-CFG-001)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/publish_plan.py`
  - `tests/unit/config/test_j_publish_plan.py`
  - `docs/delivery-evidence/j-03/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-J-03`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
- acceptance:
  - requirement: Hàm thuần `plan_publish(existing: Sequence[ConfigRevision], request: PublishRequest) -> PublishPlan`. `ConfigRevision` import chỉ đọc từ `controlplane.domain.config_security`. `PublishRequest(workspace_id, scope_kind, scope_key, base_config_revision_number: int | None, payload: dict, effective_at: str | None, actor_ref, change_reason, rollback_of_number: int | None = None)` và `PublishPlan(config_revision_number, superseded_config_revision_id: str | None, content_hash, validation: tuple[str, ...], effective_at)` là dataclass frozen. Luật: `scope_kind` thuộc `workspace`, `module`, `provider`, `preset`, `policy`, `prompt` (khác thì `ValueError` mã `invalid_scope_kind`); chỉ xét revision cùng `(workspace_id, scope_kind, scope_key)`; `base_config_revision_number` phải bằng số lớn nhất của scope, hoặc None khi scope trống (sai thì `StaleBaseRevisionError`); số mới là max cộng một; `superseded_config_revision_id` là revision PUBLISHED hiện hành của scope; `content_hash` bằng `request_hash(payload)` của `controlplane.application.idempotency`; payload có khóa nhạy cảm ở bất kỳ độ sâu nào (password, secret, token, api_key, private_key, credential) thì `SecretInConfigError`. Rollback (D8-J-11): `rollback_of_number=N` yêu cầu hash payload bằng hash revision N và thêm `ROLLBACK_OF:N` vào `validation`; revision đích INVALIDATED thì `RollbackTargetInvalidError`. Không mutate input, không ghi DB, không trộn `config_revision_number` với `revision`.
    instrument: Pytest: scope trống cho số 1; scope có 1..3 revision cho số 4 và supersede đúng revision PUBLISHED; base cũ gây `StaleBaseRevisionError`; revision workspace khác không lẫn; payload có `api_key` lồng gây `SecretInConfigError`; rollback với payload khác bị từ chối; đích INVALIDATED bị từ chối; hash bằng `request_hash`.
    counterexample: Số revision trùng hoặc giảm; base lấy từ scope khác; sửa payload tại chỗ; rollback bằng cách sửa revision cũ; secret lọt vào payload config.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider`
- coveredIds: CT-CFG-001, CT-STATE-013, TST-INT-INV-004

### J-04: Đồ thị trạng thái ConfigRevision và ExternalAccount (CT-STATE-013)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/config_security/status_graph.py`
  - `tests/unit/config/test_j_status_graph.py`
  - `docs/delivery-evidence/j-04/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-J-04`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: `CONFIG_REVISION_EDGES` là frozenset đúng 5 cạnh của `ConfigRevisionStatus` (import chỉ đọc): DRAFT→PUBLISHED, PUBLISHED→SUPERSEDED, DRAFT→INVALIDATED, PUBLISHED→INVALIDATED, SUPERSEDED→INVALIDATED. `ExternalAccountStatus(StrEnum)` gồm ENABLED, DISABLED, DEGRADED, INVALID, REVOKED; `ACCOUNT_EDGES` đúng 5 cạnh: DISABLED→ENABLED, ENABLED→DISABLED, ENABLED→DEGRADED, ENABLED→INVALID, ENABLED→REVOKED (văn bản CT-STATE-013; D8-J-09). Hàm `can_transition_config(current, requested) -> bool`, `can_transition_account(current, requested) -> bool`, `require_config_transition(...)` và `require_account_transition(...)`; hai hàm `require_*` raise `ForbiddenTransitionError` (import chỉ đọc từ `controlplane.domain.statemachine`, dùng đúng chữ ký đang được `controlplane.application.config_security` gọi) kèm `aggregate_type` là `config_revision` hoặc `external_account`. `account_status_view(status) -> str` trả chữ thường (`enabled`, `disabled`, `degraded`, `revoked`, `invalid`) theo CT-ACC-001. Self-transition bị cấm; INVALIDATED là terminal; DEGRADED, INVALID, REVOKED không có cạnh thoát.
    instrument: Pytest tham số hóa trên mọi cặp (current, requested) của từng enum: cạnh cho phép đúng bộ trên, mọi cặp khác bị từ chối; so khớp với `_allowed_transition` của `controlplane.application.config_security` để bắt drift; enum có thành viên chưa khai báo thì test fail; `ForbiddenTransitionError` mang đúng `aggregate_type`.
    counterexample: DRAFT→SUPERSEDED, SUPERSEDED→PUBLISHED, INVALIDATED→bất kỳ hay self-transition được phép; REVOKED→ENABLED chạy được trực tiếp bằng đồ thị trạng thái.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider`
- coveredIds: CT-STATE-013, CT-ACC-001

### J-05: Resolve configuration bundle có provenance (CT-CFG-002)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/bundle_resolution.py`
  - `tests/unit/config/test_j_bundle_resolution.py`
  - `docs/delivery-evidence/j-05/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-J-05`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- acceptance:
  - requirement: `resolve_bundle(revisions: Sequence[ConfigRevision], request: BundleRequest) -> ConfigBundle`. `BundleRequest(workspace_id, job_ref, stage_ref, evaluation_time: datetime có múi giờ, required_scopes: tuple[tuple[str, str], ...], snapshot_state: str, pinned_revision_ids: Mapping[tuple[str, str], str] = {})` với `snapshot_state` là `NOT_COMMITTED` hoặc `COMMITTED`. `ConfigBundle(revision_refs: tuple[str, ...], values: dict, provenance: dict[str, str], bundle_fingerprint: str, warnings: tuple[str, ...])`. Luật: `COMMITTED` thì dùng đúng revision đã pin, bỏ qua revision mới hơn (INV-004), thiếu pin thì `MissingPinError`, pin đã INVALIDATED thì `PinnedRevisionInvalidatedError`; `NOT_COMMITTED` thì chọn revision PUBLISHED có `effective_at` không muộn hơn `evaluation_time` và mới nhất của mỗi scope (`effective_at` None là hiệu lực ngay); revision của workspace khác bị bỏ qua, không báo lỗi lộ sự tồn tại; thiếu scope bắt buộc thì `MissingScopeError`; merge theo D8-J-10 (GIẢ ĐỊNH `workspace < module < provider < preset < policy`, dict merge sâu), scope `prompt` không vào `values` mà chỉ vào `revision_refs`; payload có khóa nhạy cảm thì `BundleSecretError`; `bundle_fingerprint` là SHA-256 (`hashlib`) của JSON chuẩn hóa (sort_keys, separators gọn) của `revision_refs` đã sắp và `values`, không phụ thuộc thứ tự input. Hàm thuần, không đọc đồng hồ.
    instrument: Pytest: publish revision mới sau khi snapshot COMMITTED thì bundle của job cũ giữ nguyên revision và fingerprint, job mới nhận revision mới; `effective_at` tương lai bị bỏ qua; pin INVALIDATED gây lỗi; revision workspace khác bị bỏ qua; kiểm thứ tự ghi đè; prompt không vào values; khóa secret gây `BundleSecretError`; gọi hai lần cùng input cho cùng fingerprint.
    counterexample: Job đã snapshot nhận revision mới; revision tương lai áp dụng sớm; revision workspace khác lọt vào bundle; bundle chứa secret; fingerprint đổi theo thứ tự input.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider`
- coveredIds: CT-CFG-002, TST-INT-INV-004, TST-SEC-INV-020

### J-06: Aggregate ExternalAccount và ExternalAccountView (CT-ACC-001)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/config_security/external_account.py`
  - `tests/unit/config/test_j_external_account.py`
  - `docs/delivery-evidence/j-06/report.md`
- dependsOn: `J-04`
- resourceLocks: `LOCK-J-06`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: Dataclass frozen `ExternalAccount(external_account_id, workspace_id, provider, account_label, status: ExternalAccountStatus, project_ref: str | None, capabilities: frozenset[str], credential_version: int, credential_updated_at: str | None, credential_expires_at: str | None, quota_observation_ref: str | None, health: str | None, revision: int)` (`ExternalAccountStatus` import từ J-04). `to_view(account) -> dict` trả đúng 9 khóa của CT-ACC-001: `external_account_id`, `provider`, `account_label`, `status` (chữ thường), `project_ref`, `capabilities` (list đã sắp), `quota_observation_ref`, `credential_metadata` (`{"present": bool, "updated_at": ..., "expires_at": ...}`), `health`; không khóa nào mang secret hay handle. `account_allows_role(account, workspace_id, ai_role) -> bool` chỉ True khi status ENABLED, workspace khớp và role có trong `capabilities` (so khớp chính xác, không wildcard; QR-SEC-009). `rotate_credential(account, new_version, now_iso)` yêu cầu `new_version` lớn hơn version hiện tại, ghi `credential_updated_at`, tăng `revision`. `reactivate_with_new_credential(account, new_version, now_iso)` chỉ chấp nhận account `REVOKED` và `new_version` lớn hơn version cũ, trả account `ENABLED` mới (không hồi sinh secret cũ). Mọi hàm trả đối tượng mới, không mutate.
    instrument: Pytest: view có đúng 9 khóa, status chữ thường, không khóa secret; role chưa cấp hoặc account DISABLED, DEGRADED, REVOKED cho False; workspace khác cho False; reactivate với version cũ hoặc bằng bị `ValueError`; reactivate từ ENABLED bị từ chối; rotate giảm version bị `ValueError`.
    counterexample: Account REVOKED dùng lại credential version cũ; view lộ secret hay handle; role ngoài `capabilities` được phép; account DISABLED vẫn được route.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider`
- coveredIds: CT-ACC-001, QR-SEC-009, CT-STATE-013

### J-07: ProviderCapacitySnapshot và quota domain (CT-CAP-001)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/config_security/capacity_snapshot.py`
  - `tests/unit/config/test_j_capacity_snapshot.py`
  - `docs/delivery-evidence/j-07/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-J-07`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: Dataclass frozen `ProviderCapacitySnapshot(snapshot_id, provider, model, project, account, capability, limit_requests: int | None, limit_tokens: int | None, limit_storage_bytes: int | None, used_requests: int, used_tokens: int, used_storage_bytes: int, reset_at: str | None, backoff_until: str | None, health: str, latency_ms: int | None, error_rate: float | None, confidence: str, source: str, observed_at: str, expires_at: str | None)`; số âm hoặc bool bị `ValueError`; `confidence` thuộc `observed`, `estimated`, `unknown` (khác thì `ValueError`, D8-J-13). `quota_domain_key(provider, project, model) -> str` không chứa account (ADR-0008). `is_expired(snapshot, now: datetime) -> bool`: `expires_at` None là chưa hết hạn; không phân tích được hoặc không có múi giờ thì coi là hết hạn (fail-closed). `effective_confidence(snapshot, now) -> str` trả `unknown` khi hết hạn. `remaining(snapshot, kind, now) -> int | None` với `kind` thuộc `requests`, `tokens`, `storage_bytes`, trả None khi limit None hoặc confidence hiệu lực là `unknown`. `DomainCapacity(domain_key, limit_requests, used_requests, remaining_requests, health, confidence, reset_at, observed_at)` và `merge_quota_domain(snapshots, now) -> dict[str, DomainCapacity]`: các account cùng quota domain không cộng limit; lấy snapshot mới nhất theo `observed_at` của domain. Không có trường secret.
    instrument: Pytest: bốn snapshot cùng provider, project, model nhưng khác account cho một `DomainCapacity` có limit bằng limit của một snapshot, không nhân bốn; khác project cho hai domain; snapshot hết hạn cho `unknown` và `remaining` None; thời gian naive bị coi hết hạn; số âm, bool, confidence lạ bị `ValueError`.
    counterexample: Bốn tài khoản nhân thành bốn quota độc lập; quota hết hạn vẫn dùng như guarantee; remaining suy ra từ confidence unknown.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider`
- coveredIds: CT-CAP-001, RM-RISK-007

### J-08: IncrementalCostRecord và dự báo ngân sách 80% (CT-COST-001)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/config_security/incremental_cost.py`
  - `tests/unit/config/test_j_incremental_cost.py`
  - `docs/delivery-evidence/j-08/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-J-08`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: Dataclass frozen `IncrementalCostRecord(record_id, provider, service, operation_ref, job_ref: str | None, batch_ref: str | None, quantity: Decimal, unit, estimated_cost: Decimal, actual_cost: Decimal | None, currency, source, occurred_at: str, cost_category: str)`; `cost_category` thuộc `api_paid`, `background_service`, `extra_storage`, `other_direct`; giá trị `existing_plan`, `electricity`, `internet`, `hardware` bị `NotIncrementalCostError`; số tiền chỉ nhận `Decimal`, float, bool, âm hoặc NaN bị `InvalidAmountError`. `BudgetPolicy(monthly_limit: Decimal | None, warn_ratio: Decimal = Decimal('0.8'), hard_stop: bool = False, currency: str = 'USD')`. `evaluate_budget(records, policy, window_start, window_end, now) -> BudgetStatus(spent, forecast, level, reason_codes)`: `spent` cộng `actual_cost` nếu có, ngược lại `estimated_cost`, trong `[window_start, window_end)` và cùng currency (khác thì `CurrencyMismatchError`); `forecast = spent * độ dài cửa sổ / thời gian đã trôi` (thời gian đã trôi không dương thì None); `level` là `NO_LIMIT` khi `monthly_limit` None, `WARN_80` khi forecast hoặc spent đạt `limit * warn_ratio` (reason `FORECAST_80` hoặc `SPENT_80`), `EXCEEDED` khi spent đạt limit (reason `LIMIT_REACHED`), còn lại `OK`. `should_block(status, policy, additional_estimated: Decimal) -> bool` chỉ True khi `policy.hard_stop` và `spent + additional_estimated > monthly_limit` (D8-J-05). Không hard-code 50 USD; thời gian và cửa sổ do caller truyền (D8-J-06).
    instrument: Pytest: spent chỉ tính trong cửa sổ; forecast tuyến tính (cửa sổ 30 ngày, nửa kỳ chi 20 cho forecast 40); limit 50 với forecast 41 cho `WARN_80`; spent 50 cho `EXCEEDED`; limit None cho `NO_LIMIT` và `should_block` False; `hard_stop` False không chặn dù vượt; `hard_stop` True chặn khi vượt; category `electricity` bị từ chối; float bị `InvalidAmountError`; limit 100 cũng chạy đúng (không hard-code 50).
    counterexample: Tính gói Gemini, Drive hay điện vào chi phí; hard-stop khi user chưa cấu hình ngân sách; cộng chi phí khác currency; hard-code 50 USD; dùng float.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider`
- coveredIds: CT-COST-001, QR-COST-001

### J-09: AuditRecord append-only (CT-SEC-004)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/config_security/audit_record.py`
  - `tests/unit/security/test_j_audit_record.py`
  - `docs/delivery-evidence/j-09/report.md`
- dependsOn: `J-02`
- resourceLocks: `LOCK-J-09`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: Dataclass frozen `AuditRecord(audit_id, workspace_id, actor_ref, action, resource_ref, revision_before: str | None, revision_after: str | None, occurred_at: str, correlation_id, outcome, redacted_reason)`. `AUDIT_REQUIRED_ACTIONS` là frozenset 22 mã ứng với 7 nhóm của CT-SEC-004: `config_change`, `prompt_change`, `policy_change`, `preset_change`; `source_add`, `source_disable`, `source_remove`, `source_restore`; `hook_metadata_edit`; `account_update`, `account_test`, `account_enable`, `account_disable`, `secret_update`; `debug_run`, `retry`, `variant_create`; `cleanup`, `restore`, `recovery`; `technical_detail_view`, `sensitive_operation`. `build_audit_record(...)` kiểm: `action` thuộc tập (khác thì `UnknownAuditActionError`, fail-closed); `outcome` thuộc `succeeded`, `failed`, `denied`; `reason` đi qua `redact_value` của J-02 (`controlplane.infrastructure.security.secret_redaction`); `revision_before` và `revision_after` là chuỗi ref hoặc số revision, dict hoặc payload bị `TypeError`; `occurred_at` là ISO-8601 có múi giờ (naive thì `ValueError`); `correlation_id` không rỗng. Protocol `AuditSinkPort` chỉ có `append(record) -> None`, không có phương thức update hay delete.
    instrument: Pytest: reason chứa canary thì `redacted_reason` không còn canary; build được cả 22 action; action lạ bị `UnknownAuditActionError`; revision dạng dict bị `TypeError`; thời gian naive bị `ValueError`; `AuditSinkPort` không có thuộc tính update hay delete; record frozen không gán lại được.
    counterexample: Audit chứa secret thô trong reason; thiếu hành động bắt buộc; record sửa được sau khi ghi; revision trước/sau là toàn bộ payload.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider`
- coveredIds: CT-SEC-004, TST-SEC-INV-012

### J-10: UpdateSecret chỉ ghi và SecretStorePort (CT-SEC-001)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/secret_update.py`
  - `tests/unit/security/test_j_secret_update.py`
  - `docs/delivery-evidence/j-10/report.md`
- dependsOn: `J-02`, `J-09`
- resourceLocks: `LOCK-J-10`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: Protocol `SecretStorePort` gồm `put(secret_ref: str, value: SecretValue) -> int` (version tăng đơn điệu), `revoke(secret_ref: str, version: int) -> None`, `current_version(secret_ref: str) -> int | None`; không có phương thức get, read hay reveal (INV-012). `UpdateSecretService(store, audit_sink, clock)` với `update(workspace_id, account_ref, alias_ref, value, actor_ref, correlation_id, validator=None) -> SecretUpdateReceipt`. `value` phải là `SecretValue` của J-02; chuỗi thô gây `TypeError` mà thông báo không chứa giá trị. `validator` tùy chọn cho `validation_state` thuộc `unvalidated`, `valid`, `invalid` (mặc định `unvalidated`; validator raise thì `invalid` và lỗi đã redact). `SecretUpdateReceipt(secret_ref, account_ref, alias_ref, version, fingerprint, last_updated_at, validation_state, actor_ref)` với `fingerprint = 'v<version>'` (D8-J-03). `secret_ref = '<workspace_id>/<account_ref>/<alias_ref>'`; thành phần chứa `://`, `token=` hoặc `secret=` bị `ValueError`. Mỗi lần update ghi một `AuditRecord` action `secret_update` (J-09) với outcome tương ứng; receipt và audit không chứa giá trị. Store raise thì `SecretUpdateError` có thông điệp đã redact và audit outcome `failed`. Fake store in-memory định nghĩa trong tệp test.
    instrument: Pytest với fake store: hai lần update cho version 1, 2 và fingerprint `v1`, `v2`; canary không có trong receipt, audit, thông điệp lỗi kể cả khi store raise lỗi chứa canary; service không có get, read, reveal; chuỗi thô bị `TypeError`; ref chứa `://` bị từ chối; validator raise cho `invalid`.
    counterexample: Receipt hoặc audit chứa giá trị secret hay bốn ký tự cuối; có API đọc lại secret; chuỗi thô được nhận và log; fingerprint là hash của giá trị.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovider`
- coveredIds: CT-SEC-001, TST-SEC-INV-012, QR-SEC-001, QR-SEC-003

### J-11: Credential ngắn hạn và revocation (CT-SEC-002)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/credential_issuance.py`
  - `tests/unit/security/test_j_credential_issuance.py`
  - `docs/delivery-evidence/j-11/report.md`
- dependsOn: `J-02`, `J-06`
- resourceLocks: `LOCK-J-11`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: Dataclass frozen `CredentialGrant(grant_id, audience, capability, workspace_id, account_ref, issued_at, expires_at, operation_ref: str | None, job_ref: str | None, credential_version: int, revocation_version: int, permissions: frozenset[str])`, không có trường token hay secret. Port `TokenMinterPort.mint(grant) -> SecretValue` và `RevocationPort.revocation_version(account_ref) -> int` (fake trong tệp test). `CredentialIssuer(minter, revocations, max_ttl_seconds: int)` với `issue(account: ExternalAccount, audience, capability, permissions, ttl_seconds, now, operation_ref=None, job_ref=None) -> IssuedCredential(grant, token: SecretValue)`. Từ chối khi: account không ENABLED hoặc workspace khác; capability không thuộc `account.capabilities`; `ttl_seconds <= 0` hoặc lớn hơn `max_ttl_seconds` (trần bắt buộc, D8-J-08); `now` không có múi giờ; audience `desktop` mà `permissions` chứa `oauth.refresh` (`RefreshTokenNotAllowedError`: refresh token dài hạn ở cloud). `validate_grant(grant, account, now, revocations, operation_ref=None) -> None` raise `GrantExpiredError`; `GrantRevokedError` khi `revocation_version(account_ref)` lớn hơn của grant hoặc account ở trạng thái REVOKED, INVALID, DISABLED (revoke thắng snapshot cũ, CT-SEC-003 điều 7); `GrantBindingError` khi `operation_ref` lệch. `repr` của grant và `IssuedCredential` không chứa token.
    instrument: Pytest: issue hợp lệ cho `expires_at` đúng; ttl vượt trần bị từ chối; desktop kèm `oauth.refresh` bị từ chối; account REVOKED không được cấp; revoke sau khi cấp thì `validate_grant` raise `GrantRevokedError` dù chưa hết hạn; operation lệch cho `GrantBindingError`; canary token không có trong `repr`.
    counterexample: Desktop nhận refresh token; credential đã revoke vẫn dùng vì snapshot cũ; TTL không giới hạn; grant có trường token; capability ngoài account được cấp.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider`
- coveredIds: CT-SEC-002, CT-SEC-003, TST-SEC-INV-012, QR-SEC-009

### J-12: Reservation capacity theo quota domain (CT-CAP-002)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/capacity_reservation.py`
  - `tests/unit/config/test_j_capacity_reservation.py`
  - `docs/delivery-evidence/j-12/report.md`
- dependsOn: `J-07`
- resourceLocks: `LOCK-J-12`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: `CapacityReservationBook` in-memory với Protocol `ReservationStorePort` định nghĩa trong module (fake trong tệp test). `reserve(domain_key: str, units: int, ttl_seconds: int, operation_key: str, now: datetime, domain_capacity: DomainCapacity | None) -> Reservation(reservation_ref, domain_key, units, expires_at, operation_key, confidence_flag)`; `DomainCapacity` import từ J-07. `ttl_seconds > 0` bắt buộc, không mặc định (D8-J-07); `units` là số nguyên dương, bool hoặc không dương bị `ValueError`. Idempotent theo `operation_key`: gọi lại trả reservation cũ; khác `units` hoặc `domain_key` thì `ReservationConflictError`. Chỉ reservation chưa hết hạn được tính: tổng đang giữ cộng `units` vượt `remaining_requests` (khi biết) thì `CapacityUnavailableError` mã `NO_CAPACITY` mang `retry_after` lấy từ `reset_at`; khi `remaining_requests` là None (unknown hoặc hết hạn) vẫn cấp nhưng `confidence_flag='UNCERTAIN'` (chỉ là hint, D8-J-13). `release(reservation_ref)` và `expire(now)` giải phóng chỗ. Reservation tính theo quota domain, không theo account. Không sleep, không retry (G xử lý backoff).
    instrument: Pytest: hai reservation cùng domain, khác account, tổng vượt remaining thì lần hai bị `NO_CAPACITY`; cùng `operation_key` cho cùng ref; hết hạn thì chỗ được trả; remaining None cho `UNCERTAIN`; `release` hoạt động; `units` 0, âm, bool bị `ValueError`; `ttl_seconds` 0 bị `ValueError`.
    counterexample: Reservation tính theo account nên bốn tài khoản nhân bốn chỗ; reservation hết hạn vẫn chiếm chỗ; retry cùng operation tạo reservation thứ hai; reservation coi là cam kết của provider.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider`
- coveredIds: CT-CAP-002, RM-RISK-007

### J-13: ProviderRouteResolver (CT-AI-ROUTE-001)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/route_resolver.py`
  - `tests/unit/config/test_j_route_resolver.py`
  - `docs/delivery-evidence/j-13/report.md`
- dependsOn: `J-01`, `J-06`, `J-07`, `J-12`
- resourceLocks: `LOCK-J-13`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: `RouteCandidate(candidate_ref, provider_ref, model_ref, account: ExternalAccount, quota_domain_key, cost_class, max_data_sensitivity, roles: frozenset[str], local: bool)`; Protocol `RouteCatalogPort.candidates(workspace_id, ai_role) -> Sequence[RouteCandidate]` (fake trong tệp test). `ProviderRouteResolver(catalog, reservations: CapacityReservationBook, capacities: Callable[[str], DomainCapacity | None], route_revision: str)` với `resolve(request: ProviderRouteRequest, workspace_id, now, units, ttl_seconds, desktop_online) -> ProviderRouteDecision` hoặc raise `NoRouteError(code, rationale_codes)`; kiểu request và decision từ J-01. Loại candidate khi: account không ENABLED hoặc `account_allows_role` False (J-06); `data_sensitivity` của request cao hơn `max_data_sensitivity` (thứ tự và giá trị lạ theo D8-J-04, fail-closed); `cost_class` vượt `quality_latency_cost_bounds['max_cost_class']` (thiếu bound thì chỉ nhận `free`); candidate `local` khi `desktop_online` False; capacity của quota domain có health `unavailable` hoặc `remaining_requests == 0`. `remaining_requests` None thì giữ candidate và thêm rationale `QUOTA_UNCERTAIN`. Chọn theo cost_class tăng dần rồi `candidate_ref` tăng dần (xác định). `fallback_order` chỉ gồm candidate hợp lệ còn lại có ref trong `allowed_fallbacks`; ref lạ bị bỏ qua (resolver độc lập với nội dung model, INV-020). Gọi `reserve` với `operation_key = '<job_ref>:<ai_role>'`. Decision có `rationale_codes` (`ROLE_OK`, `QUOTA_AVAILABLE` hoặc `QUOTA_UNCERTAIN`, `COST_WITHIN_BOUND`), `credential_acquisition_method='secret_broker_handle'`, `estimated_cost_class` bằng cost_class, `project_ref` từ account, `route_revision` do caller truyền; qua `validate_route_decision` không có lỗi và không chứa khóa cấm. Không candidate hợp lệ thì `NoRouteError('NO_ELIGIBLE_ROUTE')`; không bao giờ chọn dịch vụ ngoài catalog hoặc vượt bound chi phí.
    instrument: Pytest với catalog fake: chọn candidate rẻ nhất còn khả dụng; account DISABLED hoặc thiếu role bị loại; độ nhạy vượt bị loại; chi phí vượt bound cho `NoRouteError` dù là candidate duy nhất; `local` khi desktop offline bị loại; hai account cùng quota domain hết remaining thì cả hai bị loại; `fallback_order` chỉ chứa ref thuộc `allowed_fallbacks`; ref lạ bị bỏ qua; cùng input cho cùng decision; payload `valid` của fixture qua `validate_route_request`.
    counterexample: Tự chọn provider trả phí vượt bound; coi bốn account là bốn quota độc lập; chọn local khi desktop offline; dùng ref ngoài catalog do request đề xuất; decision lộ api_key.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider`
- coveredIds: CT-AI-ROUTE-001, CT-CAP-001, TST-SEC-INV-020

### J-14: Chính sách fallback có kiểm soát (CT-AI-ROUTE-002)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/fallback_policy.py`
  - `tests/unit/config/test_j_fallback_policy.py`
  - `docs/delivery-evidence/j-14/report.md`
- dependsOn: `J-13`
- resourceLocks: `LOCK-J-14`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- acceptance:
  - requirement: `classify_failure(error: BaseException) -> str` trả `RATE_LIMIT` (lỗi có `code == 429` hoặc thuộc `RateLimitError` của `controlplane.config.models`), `TIMEOUT` (`TimeoutError` hoặc `ProviderTimeoutError` của `controlplane.config.adapter`), `AUTH` (`ProviderAuthenticationError`), còn lại `UNKNOWN`; chỉ import lớp ngoại lệ, không import `ProviderRouter` hay `NineRouterHTTPAdapter`. `FallbackIntentPolicy(snapshot_committed: bool, fallback_allowed_after_snapshot: bool)`. `decide_fallback(decision: ProviderRouteDecision, failure_kind: str, attempted: Sequence[str], intent_policy, desktop_online: bool, local_candidate_refs: frozenset[str], ai_required: bool) -> FallbackOutcome(action, next_candidate_ref: str | None, provenance_required: tuple[str, ...], reason_codes: tuple[str, ...])` với `action` thuộc `SWITCH`, `WAIT`, `CONTINUE_WITHOUT_AI`, `NEW_OUTPUT_REVISION_REQUIRED`. Quy tắc: `ai_required` False thì `CONTINUE_WITHOUT_AI`; `AUTH` và `UNKNOWN` thì `WAIT`; `RATE_LIMIT` và `TIMEOUT` thì `SWITCH` sang candidate đầu tiên trong `decision.fallback_order` chưa có trong `attempted` (bỏ candidate thuộc `local_candidate_refs` khi `desktop_online` False); hết candidate thì `WAIT`; nếu `snapshot_committed` và không `fallback_allowed_after_snapshot` thì không `SWITCH` âm thầm mà trả `NEW_OUTPUT_REVISION_REQUIRED`. `provenance_required` luôn là `('model_ref', 'prompt_revision', 'config_revision')`. `backoff_seconds(attempt: int, base: int, cap: int) -> int` bằng `min(cap, base * 2 ** attempt)`, không random, không sleep; tham số bắt buộc (D8-J-07). Không bao giờ chọn candidate ngoài `fallback_order`.
    instrument: Pytest: 429 cho `SWITCH` sang candidate đầu của `fallback_order`; hết fallback hoặc AUTH cho `WAIT`; `ai_required` False cho `CONTINUE_WITHOUT_AI`; snapshot đã commit mà không cho phép cho `NEW_OUTPUT_REVISION_REQUIRED`; local bị bỏ qua khi desktop offline; backoff cho 1, 2, 4 rồi bị chặn bởi cap; đối tượng lỗi giả lập dùng lớp ngoại lệ thật, không mạng.
    counterexample: Fallback sang provider ngoài danh sách; đổi intent sau snapshot mà không tạo revision mới; retry storm không backoff; công việc không cần AI bị dừng; fallback không ghi model, prompt, config revision.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider`
- coveredIds: CT-AI-ROUTE-002

### J-15: Test tài khoản ngoài có operation receipt (CT-ACC-002)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/account_test.py`
  - `tests/unit/security/test_j_account_test.py`
  - `docs/delivery-evidence/j-15/report.md`
- dependsOn: `J-02`, `J-06`
- resourceLocks: `LOCK-J-15`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: Protocol `AccountProbePort.probe(account_ref: str, minimal: bool) -> ProbeResult(ok: bool, latency_ms: int | None, error_class: str | None, detail: str | None)` và `ReceiptStorePort` (`get(operation_key)`, `save(receipt)`), fake trong tệp test. Lớp `ExternalAccountTester(probe, receipts, clock)` (không đặt tên bắt đầu bằng `Test` để pytest không thu thập nhầm) có `run(account: ExternalAccount, operation_key: str) -> AccountTestReceipt(receipt_id, operation_key, external_account_id, ok, latency_ms, error_class, redacted_detail, tested_at)`. Idempotent theo `operation_key`: lần hai trả receipt cũ và không probe lại. Luôn gọi probe với `minimal=True`. `redacted_detail` đi qua `redact_value` của J-02. Probe raise thì receipt `ok=False`, `error_class` là tên lớp lỗi, chi tiết đã redact, không raise ra ngoài. Account `REVOKED` không bị probe (receipt `ok=False`, `error_class='REVOKED'`). Dịch vụ không đổi status hay capabilities của account, không có phương thức enable, disable hay set_route, không gọi route catalog (CT-ACC-002).
    instrument: Pytest: hai lần `run` cùng `operation_key` chỉ gọi probe một lần với `minimal=True`; account sau `run` bằng account trước (`==`); probe raise lỗi chứa canary thì receipt không chứa canary; account REVOKED không gọi probe; `redacted_detail` không còn mẫu token; `ExternalAccountTester` không có phương thức enable, disable hay set_route.
    counterexample: Test tự bật account hoặc đổi routing; probe không dùng request nhỏ nhất; lỗi probe lộ credential; test lặp tạo nhiều lời gọi tới provider.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider`
- coveredIds: CT-ACC-002, TST-SEC-INV-012

### J-16: Adapter capability health từ capacity snapshot (CT-CAP-003)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/capability_health.py`
  - `tests/unit/config/test_j_capability_health.py`
  - `docs/delivery-evidence/j-16/report.md`
- dependsOn: `J-07`
- resourceLocks: `LOCK-J-16`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `tests/fixtures/contracts/g-activity-execution/payloads.json`
- acceptance:
  - requirement: `snapshot_to_observation(snapshot: ProviderCapacitySnapshot, now: datetime, location: str = 'cloud') -> dict` ánh xạ snapshot của J-07 sang observation mà `controlplane.config.capability_view.build_capability_view` (import chỉ đọc, không sửa) nhận: `provider`, `capability_type` lấy từ `capability`, `account_scope` là `'<account>:<project>'`, `limit` lấy từ `limit_requests` (None thì bỏ khóa để view báo `unknown`), `used` lấy từ `used_requests`, `health`, `confidence` lấy từ `effective_confidence`, `observed_at`, `expires_at`, `reset_at`, `backoff_active` (True khi `backoff_until` còn sau `now`), `location`. `project_capability_health(snapshots, now, location='cloud') -> list[CapabilityView]` dùng `project_latest_capability_views`. Kết quả: snapshot khỏe và còn hạn là `available`; hết hạn không là `available`; đang backoff là `degraded`; `limit` None là `unknown`; health `down` là `unavailable`. Module không tạo execution grant (heartbeat không tự cấp quyền thực thi, CT-CAP-003) và không chứa secret.
    instrument: Pytest: snapshot khỏe cho `available`; hết hạn không `available`; backoff cho `degraded`; limit None cho `unknown`; health `down` cho `unavailable`; hai snapshot cùng scope thì lấy snapshot mới nhất; input không bị mutate; `to_dict()` của view không có khóa nhạy cảm; module không có hàm tạo grant.
    counterexample: Quota hết hạn vẫn `available`; thiếu limit vẫn `available`; heartbeat tạo execution grant.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider`
- coveredIds: CT-CAP-003, CT-CAP-001

### J-17: DpapiSecretStore trên desktop (INV-012)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/security/dpapi_secret_store.py`
  - `tests/integration/config/test_j_dpapi_secret_store.py`
  - `docs/delivery-evidence/j-17/report.md`
- dependsOn: `J-10`
- resourceLocks: `LOCK-J-17`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: `DpapiSecretStore(root: Path, entropy: bytes | None = None)` hiện thực `SecretStorePort` của J-10. `put(secret_ref, value)` mã hóa bằng `dpapi_encrypt` của `controlplane.security.dpapi` (import chỉ đọc), ghi tệp `<root>/<sha256 của secret_ref>/v<N>.bin` nguyên tử (tệp `.tmp` rồi `os.replace`), version tăng đơn điệu; đường dẫn dựng từ hash nên ref chứa `..` hay dấu gạch chéo không thoát khỏi `root`. `revoke(secret_ref, version)` xóa ciphertext và ghi marker `v<N>.revoked`. `current_version` trả version lớn nhất chưa revoke hoặc None. `export_vault(secret_refs) -> dict[str, bytes]` trả bản mã (không bao giờ plaintext) của version hiện hành để nạp `CredentialBroker(vault=...)`; secret đã revoke không được export. Không có plaintext trên đĩa. Chỉ chạy khi `sys.platform == 'win32'`, nền tảng khác `pytest.skip` kèm lý do. DPAPI là API cục bộ của OS, không gọi mạng; secret trong test là canary hằng số.
    instrument: Pytest dùng `tmp_path`: hai lần `put` cho version 1, 2 và hai tệp; quét mọi byte dưới `root` không thấy canary; `export_vault` rồi `CredentialBroker.acquire_secret` trả đúng giá trị trong scope và handle hết hạn sau scope (`is_expired()` True); sau `revoke` thì không export và broker raise `UnauthorizedSecretAccessError`; không còn tệp `.tmp` sau `put`; ref chứa `..` vẫn ghi trong `root`.
    counterexample: Plaintext secret trong tệp hoặc log; secret đã revoke vẫn export được; handle còn dùng được sau khi thoát scope.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider`
- coveredIds: TST-SEC-INV-012, QR-SEC-008

### J-18: RoutedInvocation: route, fallback, ngân sách và provenance (CT-AI-ROUTE-002)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/config_security/routed_invocation.py`
  - `tests/integration/config/test_j_routed_invocation.py`
  - `docs/delivery-evidence/j-18/report.md`
- dependsOn: `J-08`, `J-12`, `J-13`, `J-14`
- resourceLocks: `LOCK-J-18`
- bindingRefs:
  - `docs/parallel-delivery/bindings/j-provider-route.json`
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
- acceptance:
  - requirement: `RoutedInvocationService(resolver: ProviderRouteResolver, executor: ProviderExecutorPort, budget_policy: BudgetPolicy, cost_ledger: CostLedgerPort, window_provider: Callable[[datetime], tuple[datetime, datetime]])`; `ProviderExecutorPort.execute(decision, candidate_ref: str, request_payload_ref: str, credential_method: str) -> ExecutionResult(ok, output_ref: str | None, usage_cost: Decimal, error: BaseException | None)` (fake trong tệp test; executor chỉ nhận phương thức lấy credential, không bao giờ nhận secret). `invoke(request, workspace_id, now, units, ttl_seconds, desktop_online, intent_policy, ai_required, config_revision_id, prompt_revision_id, local_candidate_refs) -> InvocationRecord(route_decision, attempts, outcome, config_revision_id, prompt_revision_id, cost_status)`. Luật: `config_revision_id` hoặc `prompt_revision_id` rỗng thì `ValueError` (provenance bắt buộc, INV-004); trước mỗi lần gọi chạy `evaluate_budget` và `should_block` của J-08, chặn bằng outcome `BUDGET_BLOCKED` chỉ khi `hard_stop` đã cấu hình, `WARN_80` hoặc `EXCEEDED` chỉ gắn `cost_status`; resolve rồi execute, lỗi thì `classify_failure` và `decide_fallback` của J-14; `SWITCH` thử candidate kế (mỗi lần ghi `AttemptRecord(candidate_ref, model_ref, config_revision_id, prompt_revision_id, outcome)`); `WAIT` trả outcome `WAITING_PROVIDER` và không raise (không mất job hay history); `CONTINUE_WITHOUT_AI` trả `SKIPPED_AI_NOT_REQUIRED`; `NEW_OUTPUT_REVISION_REQUIRED` trả outcome cùng tên. Ghi vào `cost_ledger` chỉ khi `usage_cost > 0`. Record và lỗi đi qua `redact_value` của J-02. Không import `controlplane.config.router` hay `controlplane.config.adapter`.
    instrument: Pytest tích hợp với fake: executor 429 lần đầu thì attempt hai `SWITCH` thành công, record có hai attempt mang đủ revision; mọi candidate lỗi cho `WAITING_PROVIDER` không raise; `hard_stop` True và vượt ngân sách cho `BUDGET_BLOCKED` mà executor không được gọi; `hard_stop` False vượt ngân sách vẫn chạy với `cost_status` cảnh báo; thiếu `prompt_revision_id` bị `ValueError`; `ai_required` False khi provider lỗi cho `SKIPPED_AI_NOT_REQUIRED`; canary trong lỗi của executor không có trong record hay repr; monkeypatch `socket.create_connection` và `socket.getaddrinfo` ném lỗi để chứng minh không dùng mạng.
    counterexample: Provider lỗi làm mất job hoặc ném exception lên hàng đợi; fallback sang dịch vụ trả phí ngoài danh sách; hard-stop khi user chưa cấu hình ngân sách; record thiếu config revision hoặc prompt revision; secret trong record.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider`
- coveredIds: CT-AI-ROUTE-002, CT-COST-001, TST-INT-INV-004, TST-SEC-INV-012
