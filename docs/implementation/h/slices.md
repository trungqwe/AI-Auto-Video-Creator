# Slice triển khai Phân hệ H — Giao diện quản trị

Nguồn: `docs/implementation/h/plan.md`. Mỗi slice là `work_package_slice`; Control biên dịch trong phong bì policy.

## Quy tắc chung cho mọi slice

- Phong bì sửa: `src/controlplane/ui/src/components/**`, `src/controlplane/ui/src/features/**`, `src/controlplane/ui/src/api/**`, `src/controlplane/ui/src/types/**`, `src/controlplane/application/projections/**`, `src/controlplane/application/sse/**`, `src/controlplane/api/sse/**`, `src/controlplane/api/routes/modules/**`, `src/controlplane/infrastructure/db/projections/**`, `tests/unit/control_ui/**`, `tests/integration/control_ui/**` và tệp bằng chứng `docs/delivery-evidence/<task-id viết thường>/report.md`. Mỗi slice chỉ sửa đúng các tệp ghi ở ownedPaths của chính nó, là tệp mới đặt cạnh mã cũ.
- Không sửa: mọi tệp đã có trong các thư mục trên (`operation_view_mapper.py`, `application/sse/stream.py`, `api/sse/stream.py`, `infrastructure/db/projections/postgres.py`, `ui/src/api/client.ts`, `ui/src/types/api.ts`, các component hiện có); `App.tsx`, `index.css`, `ui/dist`, `package.json`, `package-lock.json`; migration; composition root (`src/controlplane/api/main.py`, `src/main.py`); `src/controlplane/api/routes/control.py` và control API; lockfile hoặc `pyproject.toml`; `tests/m2/**`; state machine (`src/controlplane/domain/statemachine/**`); workflow. Nhu cầu loại này gửi IMPL-PLAN-CONVERGENCE (plan.md mục 9).
- Không thêm thư viện; Python chỉ dùng stdlib và gói đã có trong runtime khoá (`fastapi`, `starlette`, `httpx` cho `TestClient`, `pytest`); TypeScript không import thư viện mới. Không gọi mạng, Drive, OAuth, PostgreSQL hay dịch vụ thật; không đọc `Credentials/` hay bí mật; secret trong test là canary hằng số. Phân hệ khác được thay bằng fixture CP1 (`tests/fixtures/contracts/**`) và fake định nghĩa ngay trong tệp test.
- Import root `src/`, dạng `controlplane.…`, không có tiền tố `src.`. Không thêm `__init__.py` vào thư mục test hay vào `src/controlplane/api/routes/modules/` (D8-H-07). Tên tệp test `test_h_<chủ đề>.py`; docstring đầu tệp test có dòng `coveredIds:`. Test chỉ đọc tệp nguồn TypeScript qua `pathlib`, không chạy node.
- Test-first: viết test trước; với module Python tạo tệp đúng chữ ký nhưng thân hàm `raise NotImplementedError`; với tệp TypeScript tạo tệp tối thiểu có export rỗng hoặc sai nội dung; chạy để thấy RED do assertion hoặc NotImplementedError. Thiếu tệp, ImportError hay lỗi cú pháp không phải RED hợp lệ. Sau đó implement tới GREEN. Không tạo test chỉ mô tả hành vi đã có sẵn.
- Dữ liệu thời gian là chuỗi ISO 8601 do caller truyền; mã slice không đọc đồng hồ hay múi giờ hệ thống. Mọi nhãn UI viết tiếng Việt đủ dấu; tệp UTF-8 không BOM.
- Lệnh kiểm chạy bằng interpreter khoá của lane; ghi lệnh, exit code, kết quả RED và GREEN vào report.md của slice.
- Khuôn slice: tiêu đề cấp 3 `H-<số>: <tên>`, tiếp theo là các mục kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance (requirement, instrument, counterexample), testCommands, coveredIds theo đúng thứ tự này. Khóa tài nguyên mỗi slice là `LOCK-H-<số>`.
- bindingRefs: seam H ↔ G chưa có binding (`docs/parallel-delivery/bindings/README.md` dòng 63); slice dùng `README.md` làm tham chiếu fail-closed, kèm binding liên quan nếu có.
- DAG: wave 1 gồm H-01, H-02, H-03, H-06, H-07, H-16; các wave sau theo dependsOn (plan.md mục 10).

## Danh sách slice

### H-01: Mô hình OperationView đầy đủ (CT-API-007)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/projections/operation_view_model.py`
  - `tests/unit/control_ui/test_h_operation_view_model.py`
  - `docs/delivery-evidence/h-01/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-H-01`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Module mới, không sửa `operation_view_mapper.py` (import chỉ đọc `map_operation_view` và `OperationState`). Hằng `OPERATION_STATUSES = ('accepted', 'running', 'waiting', 'outcome_unknown', 'succeeded', 'failed')` và `TERMINAL_STATUSES = ('succeeded', 'failed')` (`outcome_unknown` không phải terminal). Dataclass frozen `OperationViewModel(operation_id, command_ref, status, progress, resource_refs, started_at, updated_at, finished_at, wait_reason, problem)`. Hàm `build_operation_view(*, operation_id, command_ref, execution_state, resource_refs, started_at=None, updated_at=None, finished_at=None, wait_reason=None, progress=None, problem=None) -> OperationViewModel` với `status = map_operation_view(...)`. Luật (D8-H-04): `wait_reason` chỉ hợp lệ khi status là `waiting` và phải là dict có khóa `code` là chuỗi không rỗng, sai dạng thì `ValueError('invalid_wait_reason')`, truyền khi status khác `waiting` thì `ValueError('unexpected_wait_reason')`; terminal thiếu `finished_at` thì `ValueError('missing_finished_at')`, chưa terminal mà có `finished_at` thì `ValueError('unexpected_finished_at')`; `problem` chỉ cho phép khi `failed` hoặc `outcome_unknown` (sai thì `ValueError('unexpected_problem')`), phải có `code`, `title`, `status`, `correlation_id`, và cấm khóa (không phân biệt hoa thường, mọi độ sâu kể cả trong list) `stack_trace`, `traceback`, `secret_value`, `internal_detail` hoặc giá trị chuỗi chứa `Traceback (most recent call last)` thì `ValueError('unsafe_problem')`. `to_dict()` trả đúng 10 tên khóa của CT-API-007. Hàm thuần, không đọc đồng hồ.
    instrument: Pytest tham số hóa 5 giá trị `OperationState` × `wait_reason` có hoặc không, kiểm đúng 6 trạng thái view (PREPARED→accepted, STARTED→running, STARTED có wait_reason→waiting, SUCCEEDED→succeeded, FAILED→failed, OUTCOME_UNKNOWN→outcome_unknown); `wait_reason` rỗng, không phải dict hoặc truyền khi không STARTED thì ValueError; terminal thiếu `finished_at` và running có `finished_at` thì ValueError; `problem` có `stack_trace` lồng trong list-trong-dict hoặc chuỗi `Traceback` thì ValueError, `problem` hợp lệ trên `failed` được nhận và trên `running` bị từ chối; test phân tích bảng markdown CT-API-007 trong `docs/09-contracts/01-control-api-and-stream.md` bằng regex (dòng `started_at`, `updated_at`, `finished_at` gộp trong một ô) để chứng minh khóa của `to_dict()` bằng tập tên trường trong bảng (bắt drift).
    counterexample: waiting hiển thị là running; outcome_unknown bị gộp vào failed; problem mang stack trace; finished_at xuất hiện khi còn running; `to_dict` thiếu hoặc thừa khóa so với contract.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider`
- coveredIds: CT-API-007, QR-UX-003, TST-SEC-INV-012

### H-02: Phân trang keyset, lọc và sắp xếp có whitelist

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/projections/list_query.py`
  - `tests/unit/control_ui/test_h_list_query.py`
  - `docs/delivery-evidence/h-02/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-H-02`
- bindingRefs:
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Module mới. Dataclass frozen `ListQuery(limit, cursor, sort_key, direction, filters)` (`direction` là `asc` hoặc `desc`, `filters` là dict chuỗi) và `Page(items, next_cursor)`. `ListQueryError(code, field)` với code `limit_invalid`, `sort_not_allowed`, `filter_not_allowed`, `cursor_invalid`. `parse_list_query(params: Mapping[str, str], *, allowed_sorts, allowed_filters, default_limit, max_limit) -> ListQuery`: `default_limit` và `max_limit` là tham số bắt buộc, không mặc định (D8-H-03), phải thỏa `1 <= default_limit <= max_limit`; `limit` chỉ nhận chuỗi chữ số ASCII `0-9` trong khoảng `1..max_limit`; tham số `sort`, `direction`, `cursor` và mọi tham số còn lại phải thuộc whitelist; `workspace_id` và `actor_id` trong params luôn bị `filter_not_allowed` (workspace lấy từ identity, CT-API-001). `encode_cursor(sort_value: str, row_id: str) -> str` là base64url không padding của JSON `[sort_value, row_id]`; `decode_cursor(text: str) -> tuple[str, str]` ném `cursor_invalid` với chuỗi không giải mã được, không đúng dạng hai chuỗi hoặc dài hơn 512 ký tự. `build_page(rows, *, query, sort_field, id_field) -> Page` nhận rows đã lấy với `limit + 1` phần tử: nếu `len(rows) > limit` thì cắt còn `limit` và `next_cursor` là cursor của hàng cuối trong trang, ngược lại `next_cursor` là None. Không đọc DB, không đọc đồng hồ.
    instrument: Pytest: limit `0`, `101` (khi max 100), `abc`, `-1`, `1e2` và chữ số toàn chiều rộng `５` đều là `limit_invalid`; cursor round-trip với chuỗi Unicode tiếng Việt; cursor rác, JSON sai dạng hoặc dài 513 ký tự là `cursor_invalid`; `workspace_id=x` là `filter_not_allowed`; sort ngoài whitelist là `sort_not_allowed`; `default_limit` lớn hơn `max_limit` là ValueError; `build_page` với `limit + 1` hàng có `next_cursor` khác None và `decode_cursor` trả đúng `(sort_value, id)` của hàng cuối trang; đúng `limit` hàng thì `next_cursor` là None.
    counterexample: cursor là offset số nguyên; limit vượt trần được chấp nhận; workspace_id từ query được tin; trang cuối vẫn có next_cursor; chữ số Unicode được coi là limit hợp lệ.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider`
- coveredIds: CT-API-001, CT-API-002, QR-PERF-005

### H-03: Danh mục event kind và kế hoạch resync của luồng SSE

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/sse/event_catalog.py`
  - `tests/unit/control_ui/test_h_stream_event_catalog.py`
  - `docs/delivery-evidence/h-03/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-H-03`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- acceptance:
  - requirement: Module mới, không sửa `application/sse/stream.py` hay `api/sse/stream.py`. `EVENT_KIND_PATTERN = r'[A-Za-z0-9_.-]+'` (cùng mẫu với `SseStreamPresenter._event_frame`) và `is_valid_event_kind(kind: str) -> bool` dùng `re.fullmatch` với `re.ASCII`. Lớp `StreamKindRegistry`: `register(module_prefix: str, kinds: Sequence[str]) -> None` (mỗi kind phải hợp lệ và bắt đầu bằng `<module_prefix>.`; sai mẫu thì `ValueError('invalid_event_kind')`; đăng ký lại cùng prefix với cùng kind là idempotent; kind đã thuộc prefix khác thì `ValueError('kind_owned_by_other_prefix')`), `all_kinds() -> tuple[str, ...]` sắp xếp ổn định. Hằng `BASE_STREAM_EVENT_KINDS` đúng 10 kind client đang lắng nghe ở `ui/src/api/client.ts` dòng 179–190: `operation.accepted`, `operation.running`, `operation.succeeded`, `operation.failed`, `operation.changed`, `production_batch.start_accepted`, `job.created`, `job.running`, `job.completed`, `job.failed`; `default_registry()` đăng ký ba prefix `operation`, `production_batch`, `job`. `SNAPSHOT_RESOURCES = {'operation': ('operations',), 'production_batch': ('batches', 'operations'), 'job': ('jobs',)}` và `ALL_SNAPSHOT_RESOURCES = ('operations', 'batches', 'jobs')`; `snapshot_resources_for(resource_type: str)` với `resource_type` lạ trả `ALL_SNAPSHOT_RESOURCES` (fail-safe, CT-API-008 điều 3). `resync_targets(resource_types: Iterable[str]) -> tuple[str, ...]` hợp nhất theo thứ tự xuất hiện, không trùng.
    instrument: Pytest: `default_registry().all_kinds()` bằng tập 10 kind của `BASE_STREAM_EVENT_KINDS`; test đọc `src/controlplane/ui/src/api/client.ts` bằng regex lấy mảng `eventKinds` và chứng minh nó là tập con của catalog (bắt drift với client hiện tại); đăng ký `source.registered` dưới prefix `source` được nhận, kind `source.x` dưới prefix `job` bị `invalid_event_kind`, kind chứa khoảng trắng hoặc ký tự xuống dòng bị `invalid_event_kind`, kind đã thuộc prefix `job` đăng ký lại dưới prefix khác bị `kind_owned_by_other_prefix`, đăng ký lại cùng prefix là idempotent; `resync_targets(['job', 'zzz'])` trả đủ ba tài nguyên không trùng; `resync_targets(['job'])` trả `('jobs',)`.
    counterexample: kind của phân hệ mới không có đường đăng ký nên bị bỏ rơi im lặng; kind chứa ký tự xuống dòng chèn được frame SSE; resource_type lạ không kích hoạt query lại.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider`
- coveredIds: CT-API-008, CT-EVT-002

### H-04: Dựng SQL keyset tham số hóa cho danh sách (integration với connection giả)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/projections/list_queries.py`
  - `tests/integration/control_ui/test_h_list_queries_sql.py`
  - `docs/delivery-evidence/h-04/report.md`
- dependsOn: `H-02`
- resourceLocks: `LOCK-H-04`
- bindingRefs:
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Module mới, không sửa `postgres.py`, không import `psycopg`. `ListSpec(table, id_column, sort_columns, filter_columns, select_columns)` là dataclass frozen: `table` và tên cột chỉ chứa `[a-z_.]` (sai thì `ValueError('invalid_identifier')`), `sort_columns` và `filter_columns` là Mapping từ khóa công khai sang tên cột. `build_list_sql(spec, query, *, workspace_id) -> tuple[str, tuple]` trả SQL tham số hóa `%s`: điều kiện đầu tiên luôn là `workspace_id = %s`; mỗi filter là `<cột> = %s`; keyset khi có cursor: `desc` dùng `(<cột sort>, <cột id>) < (%s, %s)`, `asc` dùng `>`; kết thúc bằng `ORDER BY <cột sort> <DIR>, <cột id> <DIR> LIMIT %s` với giá trị LIMIT là `query.limit + 1`; giá trị do người dùng chỉ nằm trong tuple tham số, không bao giờ trong chuỗi SQL; `sort_key` hoặc filter ngoài whitelist thì `ValueError('column_not_allowed')`. `fetch_page(connection, spec, query, *, workspace_id) -> Page` gọi `connection.execute(sql, params).fetchall()`, ánh xạ mỗi hàng thành dict theo `select_columns` và dùng `build_page` của H-02. Hai spec khai báo sẵn khớp bảng hiện có: `BATCHES_SPEC` (`controlplane.cp_production_batches`, cột `batch_id`, `status`, `target_count`, `created_at`, filter `status`) và `JOBS_SPEC` (`controlplane.cp_video_jobs`, cột `job_id`, `batch_id`, `status`, `snapshot_ref`, `revision`, `created_at`, filter `batch_id` và `status`). Spec cho operations (có JOIN) thuộc hội tụ (YC-HT-H-04).
    instrument: Pytest dùng connection giả ghi lại `(sql, params)`: giá trị lọc độc hại `x'; DROP TABLE controlplane.cp_video_jobs; --` chỉ có trong params, không có trong sql; `workspace_id = %s` đứng đầu mệnh đề WHERE; keyset `desc` có `<` và `asc` có `>`; không có `OFFSET`; `sort_key` chứa `created_at; DROP` hoặc filter lạ thì `column_not_allowed`; `limit=50` cho tham số cuối là 51; `fetch_page` với 51 hàng giả trả 50 items và `next_cursor` khác None; test đọc `src/controlplane/infrastructure/db/control_api_queries.py` để chứng minh `BATCHES_SPEC` và `JOBS_SPEC` dùng đúng tên bảng và cột của `batches()` và `jobs()` hiện có.
    counterexample: nối chuỗi giá trị người dùng vào SQL; thiếu điều kiện workspace; dùng OFFSET; cột sort ngoài whitelist chạy được.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider`
- coveredIds: CT-API-001, CT-API-002, QR-PERF-005

### H-05: Read model vận hành: stage run, session, log, capability và bốn mốc hoàn thành của job

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/projections/ops_read_models.py`
  - `tests/unit/control_ui/test_h_ops_read_models.py`
  - `docs/delivery-evidence/h-05/report.md`
- dependsOn: `H-01`
- resourceLocks: `LOCK-H-05`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-activity-execution.json`
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Module mới. Dataclass frozen: `StageRunView(stage_run_id, job_id, module, status, attempt, input_refs, output_refs, problem)` (`attempt` là int >= 1, hai refs là tuple chuỗi, `problem` là dict hoặc None), `SessionView(session_id, started_at, ended_at, output_folder_label, status)`, `LogEntryView(log_id, severity, occurred_at, summary, correlation_id, technical_detail_ref)`, `CapabilityHealthView(capability_kind, name, availability, checked_at)`, `JobMilestonesView(render_succeeded, qc_passed, upload_verified, completed)` (bốn bool riêng). Hàm: `safe_summary(text: str, max_len: int = 300) -> str` thay xuống dòng và tab bằng khoảng trắng, cắt tới `max_len`, và `ValueError('unsafe_summary')` nếu chứa `Traceback (most recent call last)` hoặc `stack trace` (không phân biệt hoa thường; cùng tinh thần `_ensure_safe` ở `infrastructure/db/projections/postgres.py` dòng 99–102); `build_log_entry(...)` kiểm `severity` thuộc `debug`, `info`, `warning`, `error` (GIẢ ĐỊNH D8-H-04), `summary` đi qua `safe_summary`, `technical_detail_ref` là None hoặc chuỗi UUID hợp lệ (`uuid.UUID`); `build_stage_run_view(...)` kiểm `attempt >= 1` và `problem` không chứa khóa `stack_trace`, `traceback`, `internal_detail` (không phân biệt hoa thường, mọi độ sâu); `build_job_milestones(*, render_succeeded, qc_passed, upload_verified, completed)` ném `ValueError('completed_without_upload_verified')` khi `completed` True mà `upload_verified` False (CT-ORC-008, errata m7 mục 5) và không gộp bốn mốc thành một cờ.
    instrument: Pytest: log có `Traceback (most recent call last)` bị từ chối; summary 1000 ký tự bị cắt còn 300 và không còn xuống dòng; severity `fatal` bị từ chối; `technical_detail_ref='abc'` bị từ chối và UUID `00000000-0000-0000-0000-000000000999` được nhận; `attempt=0` bị từ chối; `problem` có `internal_detail` lồng sâu bị từ chối; `completed=True` với `upload_verified=False` là ValueError; bộ mốc (render_succeeded True, qc_passed False, upload_verified False, completed False) hợp lệ và bốn trường đọc độc lập; gán lại trường của dataclass frozen gây `FrozenInstanceError`.
    counterexample: log summary mang stack trace; completion khi chưa verify upload; bốn mốc gộp thành một cờ; attempt bằng 0; technical_detail_ref không phải UUID làm hỏng truy vấn `/v1/errors/{ref}`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider`
- coveredIds: CT-API-002, CT-STATE-009, QR-UX-003, TST-E2E-INV-009

### H-06: View cấu hình, tài khoản và revision hiệu lực của job (secret an toàn)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/projections/config_account_views.py`
  - `tests/unit/control_ui/test_h_config_account_views.py`
  - `docs/delivery-evidence/h-06/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-H-06`
- bindingRefs:
  - `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- acceptance:
  - requirement: Module mới. `ConfigRevisionView(config_revision_id, scope_kind, scope_key, config_revision_number, revision, status, content_hash, created_at)` có đúng 8 trường trùng 8 khóa dict của `configs()` ở `src/controlplane/infrastructure/db/control_api_queries.py` dòng 150–160; `build_config_revision_view(row: Mapping)` bỏ qua khóa lạ và ném `ValueError('missing_field')` khi thiếu một trong 8 khóa. `ExternalAccountView(account_ref, provider, account_label, status, updated_at)` với `status` thuộc `enabled`, `disabled`, `degraded`, `revoked`, `invalid` (chữ thường, GIẢ ĐỊNH D8-H-04); `build_account_view(payload: Mapping)` ném `ValueError('secret_field_present')` nếu payload có khóa ở mọi độ sâu (không phân biệt hoa thường) thuộc `secret`, `secret_value`, `api_key`, `access_token`, `refresh_token`, `password`, `private_key`, `client_secret`, `authorization`, `credential` (CT-API-010: chỉ hiển thị provider, account label, trạng thái, thời điểm cập nhật). `JobConfigRevisionView(job_id, snapshot_state, configuration_revision_refs, configuration_bundle_fingerprint)`: `snapshot_state` là `NOT_COMMITTED` hoặc `COMMITTED`; hai tên trường còn lại đúng `b-d-production-snapshot.json`; khi `COMMITTED` thì `configuration_revision_refs` không rỗng và fingerprint là 64 ký tự hex thường, khi `NOT_COMMITTED` được phép rỗng (CT-API-009: hiển thị revision hiệu lực của từng job; INV-004: job đã snapshot giữ revision cũ). Hàm thuần.
    instrument: Pytest: test đọc nguồn `control_api_queries.py` bằng regex để chứng minh 8 khóa dict của `configs()` bằng 8 trường dataclass; payload account có `refresh_token` lồng sâu hoặc khóa `API_KEY` chữ hoa bị từ chối; `status='ENABLED'` chữ hoa bị từ chối; job `COMMITTED` với refs rỗng bị từ chối; fingerprint 63 ký tự hoặc có chữ hoa bị từ chối; job `NOT_COMMITTED` refs rỗng hợp lệ; test đọc `docs/parallel-delivery/bindings/b-d-production-snapshot.json` chứng minh hai tên trường có trong binding.
    counterexample: view account mang refresh_token; job đã commit không hiển thị revision; trạng thái viết hoa lẫn thường; tên trường lệch binding.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider`
- coveredIds: CT-API-006, CT-API-009, CT-API-010, TST-INT-INV-004, TST-SEC-INV-012

### H-07: Builder ProblemDetail cho route module

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/api/routes/modules/problem_detail.py`
  - `tests/unit/control_ui/test_h_problem_detail.py`
  - `docs/delivery-evidence/h-07/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-H-07`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Module mới trong thư mục không có `__init__.py` (D8-H-07). `PROBLEM_SPECS` là dict `code -> (status, category, retryable, detail)` với detail tiếng Việt đủ dấu cho đúng bốn mã (D8-H-06): `VALIDATION_FAILED` (422, `validation`, False), `FORBIDDEN_FIELD` (422, `validation`, False), `REVISION_CONFLICT` (409, `conflict`, False), `NOT_FOUND` (404, `not_found`, False). `problem_body(code, *, correlation_id, field_errors=None, technical_detail_ref=None) -> dict` trả đúng bộ khóa của `SseStreamPresenter._problem` ở `src/controlplane/api/sse/stream.py` (`type` là `about:blank`, `title` là `code.replace('_', ' ').title()`, `status`, `detail`, `instance` bằng `correlation_id`, `code`, `category`, `retryable`, `correlation_id`, `field_errors` mặc định `{}`) và thêm `technical_detail_ref` chỉ khi có. `problem_response(request, code, *, field_errors=None, technical_detail_ref=None) -> JSONResponse` dùng `request.state.correlation_id`, `status_code` theo bảng và `media_type='application/problem+json'`. Mã lạ thì `ValueError('unknown_problem_code')`; mọi giá trị của `field_errors` phải là chuỗi (khác thì `ValueError('field_errors_must_be_strings')`); `detail` luôn lấy từ bảng, không bao giờ từ ngoại lệ.
    instrument: Pytest: `problem_body` cho từng mã có đúng 10 khóa (11 khi có `technical_detail_ref`) và `instance == correlation_id`; `problem_response` với `starlette.requests.Request` dựng từ scope có `state.correlation_id` trả status và `content-type` đúng; mã `X` lạ thì ValueError; `field_errors={'a': {'b': 1}}` thì ValueError; JSON thân không chứa `Traceback`; test đọc `api/sse/stream.py` bằng regex để chứng minh bộ khóa khớp `_problem`.
    counterexample: detail lấy từ `str(exc)`; thiếu correlation_id; status không khớp bảng; field_errors lồng object có thể nhúng stack trace.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider`
- coveredIds: CT-API-001, CT-API-010, QR-UX-004

### H-08: Router liệt kê chỉ đọc, workspace lấy từ identity

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/api/routes/modules/read_only_listing.py`
  - `tests/unit/control_ui/test_h_read_only_listing.py`
  - `docs/delivery-evidence/h-08/report.md`
- dependsOn: `H-02`, `H-07`
- resourceLocks: `LOCK-H-08`
- bindingRefs:
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Module mới. `build_listing_router(*, prefix, fetch_page, allowed_sorts, allowed_filters, default_limit, max_limit, fetch_one=None) -> APIRouter` (FastAPI). `prefix` phải bắt đầu bằng `/v1/` (sai thì `ValueError('prefix_must_be_versioned')`). Route `GET {prefix}` gọi `parse_list_query` của H-02 rồi `fetch_page(request, workspace_id, query) -> Page` và trả `{'items': [...], 'next_cursor': ...}`; `ListQueryError` thành 422 `VALIDATION_FAILED` qua `problem_response` của H-07 với `field_errors` dạng `{field: code}`. Nếu có `fetch_one`, route `GET {prefix}/{item_id}` trả dict hoặc 404 `NOT_FOUND`. `workspace_id` luôn lấy từ `request.state.identity['workspace_id']`, không từ query. Router chỉ có method GET (không POST, PUT, PATCH, DELETE), không đọc body.
    instrument: Pytest dùng `fastapi.testclient.TestClient` với app dựng trong test, thêm middleware đặt `request.state.identity` và `request.state.correlation_id`, và `fetch_page` giả ghi lại workspace nhận được: gọi `?workspace_id=other` thì 422 và fake không được gọi; `?limit=1000` khi max 100 thì 422; truy vấn hợp lệ gọi fake đúng một lần với workspace của identity và trả `next_cursor`; POST, PUT, PATCH, DELETE vào prefix trả 405; mọi route trong `router.routes` có `methods` bằng `{'GET'}` (kể cả HEAD nếu Starlette thêm); `fetch_one` trả None thì 404 với `content-type` `application/problem+json`; prefix `/api/x` bị ValueError.
    counterexample: tin workspace từ query; có route ghi; trả 200 thân trống khi không tìm thấy; lỗi 500 lộ ngoại lệ.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider`
- coveredIds: CT-API-001, CT-API-002, CT-API-010

### H-09: Router cập nhật metadata theo allowlist (If-Match, Idempotency-Key)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/api/routes/modules/metadata_update.py`
  - `tests/unit/control_ui/test_h_metadata_update.py`
  - `docs/delivery-evidence/h-09/report.md`
- dependsOn: `H-07`
- resourceLocks: `LOCK-H-09`
- bindingRefs:
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Module mới. `FORBIDDEN_METADATA_FIELDS = frozenset({'article_body', 'body', 'script', 'script_text', 'event_relation', 'event_links', 'secret', 'secret_value'})`; `RevisionConflictError(Exception)`. `build_metadata_router(*, prefix, allowed_fields, apply_update) -> APIRouter` với `apply_update(request, item_id, expected_revision: int, changes: dict, idempotency_key: str) -> dict`; nếu `allowed_fields` giao với `FORBIDDEN_METADATA_FIELDS` thì `ValueError('forbidden_field_allowed')` ngay khi dựng router; `prefix` phải bắt đầu bằng `/v1/`. Route duy nhất `PATCH {prefix}/{item_id}`: thiếu hoặc rỗng `Idempotency-Key`, thiếu `If-Match` hoặc `If-Match` không phải chuỗi chữ số ASCII, body không phải JSON object hoặc rỗng thì 422 `VALIDATION_FAILED` kèm `field_errors`; khóa ngoài `allowed_fields` thì 422 `FORBIDDEN_FIELD` với `field_errors` liệt kê khóa vi phạm và `apply_update` không được gọi; `RevisionConflictError` thì 409 `REVISION_CONFLICT`; thành công trả 200 với dict `apply_update` trả về (giá trị đã commit). Lỗi khác để lan ra (handler chung ở composition root, YC-HT-H-02). Dùng `problem_response` của H-07.
    instrument: Pytest dùng `TestClient` với middleware đặt `request.state.identity` và `correlation_id`: PATCH hợp lệ gọi `apply_update` đúng một lần với `expected_revision` là int; thiếu `If-Match` thì 422; `If-Match: abc` thì 422; thiếu `Idempotency-Key` thì 422; body `{'article_body': 'x'}` thì 422 `FORBIDDEN_FIELD` và fake không được gọi; `allowed_fields=['notes', 'script']` thì ValueError khi dựng; `apply_update` ném `RevisionConflictError` thì 409; GET, PUT, DELETE vào prefix trả 405; chỉ có đúng một route PATCH.
    counterexample: cho phép sửa script hoặc article body; If-Match bị bỏ qua; ghi âm thầm khi revision cũ; thiếu Idempotency-Key vẫn ghi.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider`
- coveredIds: CT-API-001, CT-API-003, CT-API-004, CT-API-009

### H-10: Kiểu TypeScript cho OperationView và ListPage

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/ui/src/types/operationView.ts`
  - `src/controlplane/ui/src/types/listPage.ts`
  - `tests/unit/control_ui/test_h_ts_contract_types.py`
  - `docs/delivery-evidence/h-10/report.md`
- dependsOn: `H-01`, `H-02`
- resourceLocks: `LOCK-H-10`
- bindingRefs:
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: `operationView.ts` export `OPERATION_STATUSES = ['accepted', 'running', 'waiting', 'outcome_unknown', 'succeeded', 'failed'] as const`, `type OperationStatus` suy ra từ mảng, và `interface OperationView` với đủ 10 trường CT-API-007 (`operation_id`, `command_ref`, `status: OperationStatus`, `progress?`, `resource_refs`, `started_at?`, `updated_at?`, `finished_at?`, `wait_reason?`, `problem?`; `problem` dùng `import type { ProblemDetail } from './api.ts'`). `listPage.ts` export `interface ListPage<T> { items: T[]; next_cursor: string | null }`. Không sửa `types/api.ts`, không dùng `any`.
    instrument: Pytest đọc hai tệp bằng `pathlib`: tập trạng thái TypeScript bằng `OPERATION_STATUSES` của `controlplane.application.projections.operation_view_model` (H-01); mỗi tên trường trong bảng CT-API-007 của `docs/09-contracts/01-control-api-and-stream.md` xuất hiện trong `interface OperationView`; `ListPage` có `next_cursor: string | null`; regex cấm `: any` và `as any`; `types/api.ts` không bị đổi nội dung so với bản đã có (kiểm bằng việc `OperationItem` vẫn không có `wait_reason`).
    counterexample: thiếu waiting hoặc outcome_unknown; status kiểu string; dùng any; trường lệch tên so với contract.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider`
- coveredIds: CT-API-007, QR-UX-003

### H-11: Trình bày trạng thái operation và trạng thái artifact (tiếng Việt)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/ui/src/features/operations/statusPresentation.ts`
  - `tests/unit/control_ui/test_h_status_presentation.py`
  - `docs/delivery-evidence/h-11/report.md`
- dependsOn: `H-10`
- resourceLocks: `LOCK-H-11`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Export `STATUS_PRESENTATION: Record<OperationStatus, { label: string; cssClass: string; terminal: boolean; attention: boolean }>` đủ 6 trạng thái, nhãn tiếng Việt đủ dấu và khác nhau: accepted `Đã tiếp nhận`, running `Đang chạy`, waiting `Đang chờ`, outcome_unknown `Chưa xác định kết quả`, succeeded `Thành công`, failed `Thất bại`; `cssClass` duy nhất (`pill-accepted`, `pill-running`, `pill-waiting`, `pill-outcome-unknown`, `pill-succeeded`, `pill-failed`); `terminal` true chỉ với succeeded và failed; `attention` true với waiting, outcome_unknown, failed. `presentStatus(value: string | null | undefined)` chuẩn hóa chữ thường và trả presentation; giá trị lạ hoặc rỗng trả `{ label: 'Không nhận diện được', cssClass: 'pill-unknown', terminal: false, attention: true }`, không rơi về accepted (D8-H-02, khắc phục GAP-H-01). Thêm `ARTIFACT_AVAILABILITY_PRESENTATION` cho năm trạng thái M4 `original` (`Bản gốc`), `processed` (`Đã xử lý`), `uncertain` (`Chưa chắc chắn`), `failed` (`Lỗi`), `unavailable` (`Không khả dụng`) và `presentArtifactAvailability(value)` với giá trị lạ thì trả nhãn `Không nhận diện được`. CSS cho lớp mới là YC-HT-H-03.
    instrument: Pytest đọc tệp TypeScript: trích đúng 6 khóa trạng thái và bằng tập `OPERATION_STATUSES` của H-01; nhãn đôi một khác nhau và mỗi nhãn có ít nhất một ký tự có dấu tiếng Việt; `cssClass` đôi một khác nhau; có nhánh `pill-unknown`; không có chuỗi `?? 'ACCEPTED'` hay `|| 'ACCEPTED'`; có đủ 5 khóa trạng thái artifact với nhãn đã nêu; không chứa `any` và không chứa U+FFFD.
    counterexample: waiting hiển thị như accepted; giá trị lạ thành accepted; nhãn không dấu; thiếu một trong năm trạng thái artifact.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider`
- coveredIds: QR-UX-001, QR-UX-003, CT-API-007

### H-12: Component StatusPill

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/ui/src/components/StatusPill.tsx`
  - `tests/unit/control_ui/test_h_status_pill.py`
  - `docs/delivery-evidence/h-12/report.md`
- dependsOn: `H-11`
- resourceLocks: `LOCK-H-12`
- bindingRefs:
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: `export const StatusPill: React.FC<{ status: string | null | undefined; testIdPrefix?: string }>` import `presentStatus` từ `../features/operations/statusPresentation.ts`. Render `<span>` với `className` là `pill ` cộng `cssClass`, `role='status'`, `aria-label` là nhãn, `data-testid` là `${testIdPrefix ?? 'status'}-${giá trị chuẩn hóa}` (truyền `testIdPrefix='operation-status'` giữ tương thích mẫu `operation-status-<val>` của e2e hiện có) và nội dung là nhãn chữ (trạng thái không chỉ phân biệt bằng màu). Nội dung chỉ qua JSX. Không import `ag-grid-*`, không import `api/client`.
    instrument: Pytest đọc tệp TSX: có dòng import từ `../features/operations/statusPresentation.ts`; có `role='status'`, `aria-label`, `data-testid`, `testIdPrefix`; không có `dangerouslySetInnerHTML`, `innerHTML`, `ag-grid`, `api/client`; nhãn được render làm nội dung (có `{presentation.label}` hoặc tương đương).
    counterexample: render HTML thô; trạng thái chỉ khác nhau bằng màu; component tự gọi API.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider`
- coveredIds: QR-UX-003, CT-API-010

### H-13: Component ErrorHoverDetail (hover và focus, không stack trace)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/ui/src/components/ErrorHoverDetail.tsx`
  - `tests/unit/control_ui/test_h_error_hover_detail.py`
  - `docs/delivery-evidence/h-13/report.md`
- dependsOn: `H-10`
- resourceLocks: `LOCK-H-13`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: `export const ErrorHoverDetail: React.FC<{ problem: { title?: string; code?: string; correlation_id?: string; technical_detail_ref?: string; detail?: string } | null | undefined; onOpenTechnicalDetail?: (ref: string) => void }>`. Khi `problem` là null hoặc undefined thì trả null. Phần tử kích hoạt có `tabIndex={0}` và `aria-describedby` trỏ tới tooltip; tooltip hiện khi `onMouseEnter` hoặc `onFocus`, ẩn khi `onMouseLeave`, `onBlur` hoặc phím `Escape` (QR-UX-004: rê chuột hoặc focus bàn phím). Tooltip chỉ hiển thị `title`, `code`, `correlation_id` và `detail` đã cắt tối đa `MAX_DETAIL_CHARS = 300` ký tự; không có trường nào khác. Nếu có `technical_detail_ref` thì chỉ có nút gọi `onOpenTechnicalDetail(ref)`; component không import `api/client` và không tự fetch. Nội dung chỉ qua JSX.
    instrument: Pytest đọc tệp TSX: có `tabIndex={0}`, `aria-describedby`, `onMouseEnter`, `onMouseLeave`, `onFocus`, `onBlur`, `Escape`, `MAX_DETAIL_CHARS = 300`, `onOpenTechnicalDetail`; không có `dangerouslySetInnerHTML`, `innerHTML`, `api/client`, `fetch(`, `internal_detail`, `stack`; có ký tự tiếng Việt có dấu trong nhãn nút.
    counterexample: chỉ hover mà không focus được bằng bàn phím; tooltip nhúng internal_detail hoặc stack trace; component tự gọi API.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider`
- coveredIds: QR-UX-004, QR-UX-001, CT-API-010

### H-14: Danh mục event kind phía client và deduper có giới hạn

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/ui/src/api/streamEventKinds.ts`
  - `src/controlplane/ui/src/features/stream/boundedEventDeduper.ts`
  - `tests/unit/control_ui/test_h_stream_client_registry.py`
  - `docs/delivery-evidence/h-14/report.md`
- dependsOn: `H-03`
- resourceLocks: `LOCK-H-14`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: `streamEventKinds.ts` export `STREAM_EVENT_KINDS = [...] as const` bằng đúng `BASE_STREAM_EVENT_KINDS` của H-03 (10 kind), `RESYNC_SNAPSHOT_RESOURCES: Record<string, readonly string[]>` bằng `SNAPSHOT_RESOURCES` của H-03 và `snapshotResourcesFor(resourceType: string): readonly string[]` trả `['operations', 'batches', 'jobs']` với `resource_type` lạ. `boundedEventDeduper.ts` export `DEFAULT_MAX_SEEN = 5000` và `createBoundedEventDeduper(maxSeen: number = DEFAULT_MAX_SEEN)` trả `{ seenBefore(id: string): boolean; clear(): void; size(): number }`: `seenBefore` trả true nếu id đã thấy, ngược lại ghi nhận và trả false; khi số id vượt `maxSeen` thì xóa id cũ nhất (FIFO, dùng thứ tự chèn của `Set` hoặc `Map`); `maxSeen < 1` hoặc không nguyên thì `throw new RangeError(...)`. Khắc phục GAP-H-03. Cả hai tệp thuần: không `fetch(`, không `EventSource`, không `any`.
    instrument: Pytest đọc tệp TypeScript: tập `STREAM_EVENT_KINDS` bằng `BASE_STREAM_EVENT_KINDS` của `controlplane.application.sse.event_catalog`; bảng `RESYNC_SNAPSHOT_RESOURCES` bằng `SNAPSHOT_RESOURCES` của Python và mảng fallback bằng `ALL_SNAPSHOT_RESOURCES`; deduper có `DEFAULT_MAX_SEEN = 5000`, `RangeError`, thao tác xóa phần tử cũ nhất (có `.delete(` cùng `.keys().next()` hoặc tương đương); không có `fetch(`, `EventSource`, `: any`.
    counterexample: danh sách kind lệch giữa server và client; Set tăng vô hạn khi UI chạy 12 giờ; resource_type lạ không kích hoạt tải lại.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider`
- coveredIds: CT-API-008

### H-15: Registry màn hình theo milestone và quy tắc trường được sửa

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/ui/src/features/screens/screenRegistry.ts`
  - `tests/unit/control_ui/test_h_screen_registry.py`
  - `docs/delivery-evidence/h-15/report.md`
- dependsOn: `H-10`
- resourceLocks: `LOCK-H-15`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Export `type Milestone = 'M2' | 'M3' | 'M4' | 'M5' | 'M6' | 'M7'`, `type ScreenSpec = { id: string; titleVi: string; milestone: Milestone; module: string; resourcePath: string; columns: readonly string[]; editableFields: readonly string[]; readOnly: boolean; backendStatus: 'available' | 'pending_module' }`, `FORBIDDEN_EDITABLE_FIELDS = ['article_body', 'body', 'script', 'script_text', 'event_relation', 'event_links', 'secret', 'secret_value'] as const`, `SCREEN_REGISTRY: readonly ScreenSpec[]` và `screensForMilestone(m: Milestone)`. Registry có đúng 18 màn hình: M2 `operations` (`/v1/operations`), `batches` (`/v1/batches`), `jobs` (`/v1/jobs`), `configs` (`/v1/configs`) với `backendStatus: 'available'`; M3 `sources` (A), `articles` (B), `events` (B); M4 `media` (C), `hooks` (C), `artifacts` (I); M5 `snapshots` (D), `story-angles` (D), `scripts` (D); M6 `stage-runs` (G); M7 `sessions` (G), `logs` (G), `accounts` (J), `cost` (J) với `pending_module` (D8-H-08). Mỗi màn hình có ít nhất 3 cột. Quy tắc (D8-H-05): `editableFields` không giao `FORBIDDEN_EDITABLE_FIELDS`; `articles`, `events`, `snapshots`, `story-angles`, `scripts` có `readOnly: true` và `editableFields: []`; `sources` chỉ `tier`, `topic_tags`, `notes`, `enabled` (CT-API-003); `hooks` chỉ `tags`, `description`, `enabled`, `notes` (CT-API-004); `media` chỉ `tags`, `notes` (GIẢ ĐỊNH, QUALITY-OPEN-008); `id` duy nhất; `titleVi` tiếng Việt có dấu; `resourcePath` bắt đầu bằng `/v1/`.
    instrument: Pytest đọc tệp TypeScript và tách từng khối đối tượng của `SCREEN_REGISTRY` bằng regex: đúng 18 id duy nhất; mỗi milestone M2 đến M7 có ít nhất một màn hình (khớp roadmap §14); giao `editableFields` với tập cấm rỗng trên mọi màn hình (kiểm cả trên một khối giả dựng trong test có `script`, phải bị phát hiện); `scripts`, `articles`, `events` là `readOnly: true`; bốn màn hình `available` có `resourcePath` trùng đúng các decorator `@router.get('/operations')`, `@router.get('/batches')`, `@router.get('/jobs')`, `@router.get('/configs')` trong `src/controlplane/api/routes/control.py` với prefix `/v1`; mọi màn hình còn lại là `pending_module`; `titleVi` có ký tự có dấu; không `any`.
    counterexample: màn hình scripts cho sửa script; màn hình chưa có backend bị đánh available; thiếu màn hình của một milestone theo roadmap §14; resourcePath trỏ endpoint không tồn tại.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider`
- coveredIds: QR-UX-008, QR-UX-001, CT-API-010

### H-16: Guard tĩnh nguồn UI (XSS sink, secret, fetch, endpoint cấm)

- kind: work_package_slice
- ownedPaths:
  - `tests/unit/control_ui/test_h_ui_source_guard.py`
  - `docs/delivery-evidence/h-16/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-H-16`
- bindingRefs:
  - `docs/parallel-delivery/bindings/domain-event-envelope.json`
  - `docs/parallel-delivery/bindings/README.md`
- acceptance:
  - requirement: Slice chỉ thêm test (không có module sản phẩm). Hàm `scan_ui_source(path: str, text: str) -> list[str]` định nghĩa ngay trong tệp test, trả danh sách vi phạm: `dangerouslySetInnerHTML`, `.innerHTML`, `eval(`, `new Function(`, `document.write`, `localStorage`, `sessionStorage`; `fetch(` ngoài thư mục `src/api/`; khóa tên chứa `api_key`, `secret` hoặc `token` được gán bằng một chuỗi hằng dài từ 16 ký tự chữ hoặc số; ký tự U+FFFD; chuỗi `/scripts`, `/event-relations`, `/article-body` trong `src/api/` và `src/features/`. Test quét mọi `.ts` và `.tsx` dưới `src/controlplane/ui/src/` (chỉ đọc, không quét `dist` và `node_modules`) và yêu cầu không có vi phạm; mọi tệp phải là UTF-8 không BOM.
    instrument: Pytest: (1) các chuỗi mẫu vi phạm dựng trong test (một cho mỗi loại ở trên) đều bị `scan_ui_source` báo; (2) chuỗi sạch không bị báo; (3) quét cây `src/controlplane/ui/src` hiện có trả danh sách rỗng (`fetch(` chỉ nằm trong `api/client.ts`); (4) tệp có BOM giả lập bị báo. RED: viết `scan_ui_source` trả `[]` trước rồi chạy để thấy các mẫu vi phạm không bị báo (fail bằng assertion), sau đó implement.
    counterexample: component dùng dangerouslySetInnerHTML với dữ liệu nguồn ngoài; fetch trực tiếp trong component; secret hằng trong mã UI; endpoint sửa script hoặc quan hệ event.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider`
- coveredIds: CT-API-010, TST-SEC-INV-012, QR-UX-001
