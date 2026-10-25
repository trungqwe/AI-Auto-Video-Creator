# Kế hoạch nối sáu cổng ProductionRuntime và Drive placement — IMPL-PLAN-PROD-PORTS

- **Mã gói**: IMPL-PLAN-PROD-PORTS (planning_package)
- **Ngày lập**: 25/10/2026
- **Cơ sở**: HEAD `4b11dd042f709fb5165793cb2fd48dc275afeebe` (nhánh `trungqwe/lane-impl-plan-prod-ports`); mọi số dòng `tệp:dòng` trong tài liệu này đo tại HEAD đó.
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`), chỉ thị user duyệt Phần B ngày 18/10/2026, các quyết định của user ngày 20/10/2026 và quyết định D5 ngày 22/10/2026. `PRODUCTION_ACTIVATION_BLOCKED` còn hiệu lực tới nghiệm thu cuối; không push, không merge, không chạm main hay backup.
- **Slice**: `docs/implementation/prod-ports/slices.md` (tám slice `PP-1` đến `PP-8`). **Bằng chứng**: gói kế hoạch ở `docs/delivery-evidence/impl-plan-prod-ports/report.md`; từng slice ở `docs/delivery-evidence/pp-<số>/report.md`.

## 1. Mục tiêu và phạm vi

1. Mục tiêu: `python tools/launcher/launcher.py start` mở được ứng dụng ở `127.0.0.1:8443` bằng hồ sơ `production` trên tài nguyên thật của máy này: PostgreSQL `aiavc-postgres` (`127.0.0.1:57028`), Temporal (`7233`), 9Router `http://127.0.0.1:20128/v1` tuyến Gemini, một tài khoản Google Drive (phạm vi `drive.file`), GPU RTX 4070 SUPER 12 GB, FFmpeg đã ghim.
2. Điều đang chặn: sáu cổng của `ProductionRuntime` (`route_catalog`, `provider_credentials`, `vision_route`, `artifact_source`, `drive_token_broker`, `gpu_lease`) cùng `drive_placement` và `drive_fallback_parent_id` chưa có adapter thật. CP7-1 (cổng 57028, 7233, 8443) và mọi gói CP7 sau nó đứng vì lý do này.
3. Phạm vi sửa: adapter thật ở `src/controlplane/infrastructure/production_ports/**` (thư mục mới), test ở `tests/integration/prod_ports/**`, bằng chứng ở `docs/delivery-evidence/pp-*/**`; slice cuối thêm `tools/launcher/launcher.py` (thân `_load_runtime_ports`, `build_runtime`, `cmd_status`) và cấu hình mới ở `tools/launcher/prod/**`.
4. Ngoài phạm vi (không đổi): hợp đồng `ProductionRuntime`, mọi Protocol (`DriveTokenBrokerPort`, `ArtifactSourcePort`, `GpuLeasePort`, `RouteCatalogPort`, `VisionRoutePort`, `CredentialSourcePort`), `tools/launcher/docker-compose.yml` (thuộc `ADAPT-LAUNCH`; gói sửa ADAPT-LAUNCH-FIX1 đã tích hợp tại `21d99fc`), `profile.json`, migration, state machine, main và backup.
5. Không thêm thư viện (D10): chỉ dùng stdlib cùng `google-auth`, `google-api-python-client`, `httplib2` đã khóa trong `pyproject.toml`.
6. Adapter production không có nhánh giả: không `fake`, `mock`, `memory`, không đọc bí mật từ biến môi trường hay tệp văn bản; bí mật chỉ qua kho DPAPI (`DpapiSecretStore`). Phần thay thế duy nhất cho test là tham số tiêm (ví dụ `http_factory`, `clock`) nằm sẵn trong chữ ký, giống `DriveObjectStore.__init__` (`drive_object_store.py:151-167`); máy chủ giả cục bộ chỉ nằm trong `tests/`.

## 2. Hiện trạng đo thật (25/10/2026)

- `launcher.py start` dựng PostgreSQL rồi dừng: tiến trình `_serve` (`launcher.py:911-918`) gọi `load_app` → `build_runtime` (`launcher.py:424-449`) → `_load_runtime_ports` (`launcher.py:416-421`); hàm này chỉ `raise LauncherError('BLOCKED: thiếu adapter thật cho sáu cổng ProductionRuntime ... việc của gói J, G, I hoặc CP7')`. Cổng 8443 không mở và `cmd_start` trả 1 (`launcher.py:666-668`).
- Tài nguyên thật đã sẵn (D5): refresh token Drive trong kho DPAPI dưới alias `drive-primary-oauth` (`oauth_google_loopback.py:20`, ghi ở `:185`), kho ở `LOCALAPPDATA/AIAutoVideoCreator/vault` (`Layout.vault_dir`, `launcher.py:67-69`); OAuth client ở `LOCALAPPDATA/AIAutoVideoCreator/secrets/oauth-client.json` (`launcher.py:437`); 9Router, GPU và FFmpeg như mục 1.

Điều kiện xong của kế hoạch: sáu cổng và `drive_placement` đều có adapter thật kèm test thật nằm trong phong bì; kiểm thật cuối làm ở CP7-1 (mục 6).

## 3. Khảo sát hợp đồng và nơi dùng

### 3.1. Sáu cổng và hai giá trị placement

| Trường `ProductionRuntime` | Protocol hoặc hình dạng đòi hỏi | Nơi dùng | Adapter thật đã có |
| --- | --- | --- | --- |
| `route_catalog` | `RouteCatalogPort.candidates(workspace_id, ai_role) -> Sequence[RouteCandidate]` (`route_resolver.py:58-59`; `RouteCandidate` ở `:45-55`) | `creative.py:163` `ProviderRouteResolver(runtime.route_catalog, book, lambda domain_key: None, rev)`; resolver gọi ở `route_resolver.py:157` | Không có |
| `provider_credentials` | `CredentialSourcePort.acquire(credential_method, account_ref)` trả context manager của `str` (`real_route_executor.py:100-101`) | `creative.py:155` `NineRouterExecutor(executor_config, store, runtime.provider_credentials)`; executor gọi `acquire` ở `real_route_executor.py:136` với `decision.account_ref` | Không có |
| `vision_route` | `VisionRoutePort.invoke_vision(ai_role, instructions, image_base64, media_type, timeout_seconds)` trả `str` hoặc `Mapping` (`real_llm_image_safety.py:31-40`) | `voice.py:131-137` (`LlmImageSafetyDetector(runtime.vision_route, ...)`), gọi ở `real_llm_image_safety.py:177` | Không có |
| `artifact_source` | `ArtifactSourcePort.open(artifact_version_id) -> BinaryIO` (`drive_object_store.py:39-40`) | `storage.py:81` `DriveObjectStore(drive_config, runtime.drive_token_broker, runtime.artifact_source)`; `upload` mở nguồn ở `drive_object_store.py:277` | Không có |
| `drive_token_broker` | `DriveTokenBrokerPort.acquire(credential_method, account_ref)` trả context manager của `str` (`drive_object_store.py:43-44`) | `_BrokerHttp.request` gọi `acquire(CREDENTIAL_METHOD, ACCOUNT_REF)` ở `drive_object_store.py:128` | `DriveAccessTokenBroker` (`oauth_drive_token.py:70-155`) đã đúng chữ ký nhưng cần `AccountStatusPort` (xem 3.3) |
| `gpu_lease` | `GpuLeasePort.acquire(owner_ref) -> GpuLease`, `release(lease)`; lỗi `GpuLeaseUnavailable` (`lease.py:16-35`) | `render.py:42` `RealFfmpegRenderer(lease=runtime.gpu_lease, ...)`; renderer gọi `acquire` ở `real_ffmpeg_renderer.py:185`, `release` ở `:191`; pipeline bắt `GpuLeaseUnavailable` ở `render_video.py:325` | Không có (docstring `lease.py:3-4` ghi chờ LeaseManager) |
| `drive_placement` | `Mapping[str, str]` không rỗng; khóa là `namespace_ref`, giá trị là ID thư mục cha Drive | `storage.py:78` `placement=dict(runtime.drive_placement)`; tra ở `drive_object_store.py:211` (thiếu khóa thì `DriveObjectStoreError`); người gọi truyền `namespace_ref` ở `cloud_persist.py:86` | Không có |
| `drive_fallback_parent_id` | Chuỗi không rỗng | `storage.py:79`; dùng ở `drive_object_store.py:275` khi `object_id` chưa có cha | Không có |

`ProductionRuntime.__post_init__` (`production_profile.py:447-467`) kiểm: `drive_placement` là `Mapping` không rỗng với khóa và giá trị là chuỗi không rỗng, `drive_fallback_parent_id` là chuỗi không rỗng, sáu cổng khác `None`. Lớp `ProductionRuntime` nằm ở `production_profile.py:393-414`; hợp đồng này không đổi và là đích của mọi adapter.

### 3.2. Adapter thật đã có của gói J, G, I (tái dùng, không viết lại)

| Thành phần | Tệp:dòng | Dùng cho |
| --- | --- | --- |
| `DpapiSecretStore` (`put`, `current_version`, `export_vault`; không có API đọc plaintext) | `dpapi_secret_store.py:16-112` (`put` `:45`, `current_version` `:95`, `export_vault` `:100`) | kho khóa; alias router mới dùng cùng kho |
| `DpapiRefreshTokenReader.read(secret_ref) -> SecretValue` | `oauth_drive_token.py:51-67` | giải mã DPAPI một alias |
| `DriveAccessTokenBroker` (đổi refresh token lấy access token, giới hạn TTL; `acquire` chỉ nhận `secret_broker_handle` và `drive-primary`) | `oauth_drive_token.py:70-155` | `drive_token_broker` |
| `ACCOUNT_REF = 'drive-primary'`, `SECRET_REF = 'drive-primary-oauth'`, `SCOPE` drive.file, `run_consent` | `oauth_google_loopback.py:18-20`, `:141-189` | OAuth một lần (`launcher.py:405-413`; `cmd_oauth` `:873-908`) |
| `DriveObjectStore`, `DriveStoreConfig` | `drive_object_store.py:47-80`, `:150-176` | đã nối ở `storage.py:81`, không đổi |
| `NineRouterExecutor`, `RouteExecutorConfig`, `InvocationPayloadStore` | `real_route_executor.py:30-142` | đã nối ở `creative.py:146-155`, không đổi |
| `NineRouterHTTPAdapter`, `ApprovedEndpointRegistry.from_config` | `config/adapter.py:157-258`, `:96-110` | gọi 9Router; endpoint duyệt từ cấu hình |
| `PostgresAccountStatusPort` | `config_security.py:80-93` | trạng thái tài khoản theo CSDL |
| `CredentialBroker.acquire_secret(alias)` | `security/broker.py:60-91` | **không** khớp Protocol (chữ ký `acquire_secret(alias)`, không có `acquire(credential_method, account_ref)`), nên không dùng làm `provider_credentials` |

Quy tắc tái dùng: slice chỉ import và bọc các lớp trên, không sửa tệp của gói J, G, I (thuộc phân hệ khác).

### 3.3. Điểm không khớp phát hiện khi khảo sát

1. **Trạng thái tài khoản Drive**: `build_config_security_services` dựng `DriveAccessTokenBroker` với `PostgresAccountStatusPort` (`config_security.py:119-130`); cổng này trả `REVOKED` khi không có hàng `cp_external_accounts` (`:91-92`). `ensure_identity` chỉ tạo workspace và actor (`launcher.py:391-402`), không tạo hàng tài khoản. Vì `runtime_factory(profile)` chạy trước khi có `manager` CSDL (`launcher.py:455`), `drive_token_broker` của runtime phải dùng cổng trạng thái dựa trên kho DPAPI (có phiên bản hiện hành của `drive-primary-oauth` thì `ENABLED`, không thì `REVOKED`), không dựa CSDL (PP-3).
2. **Lệnh nhập khóa không thể là lệnh con của launcher**: `tests/integration/adapt/launch/test_adapt_launch_cli.py:232-233` khẳng định `launcher.COMMANDS` đúng bảy lệnh; thêm lệnh thứ tám làm đỏ test đã nghiệm thu nằm ngoài owned paths. Nhập khóa 9Router dùng tập lệnh riêng `tools/launcher/prod/set_router_key.py` (PP-2).
3. **Import đầu tệp của launcher** chỉ được là stdlib (`test_adapt_launch_cli.py:207-229`), nên mọi import `production_ports` trong `launcher.py` phải nằm trong thân hàm, sau `ensure_src_on_path()` (`launcher.py:378-381`).
4. **Đường dẫn 9Router**: `NineRouterHTTPAdapter.send_request` ghép `{endpoint}/v1/chat` với thân `{'prompt': ...}` (`adapter.py:216-217`), còn endpoint của profile là `http://127.0.0.1:20128/v1` (`profile.json:117-121`) nên URL thành `.../v1/v1/chat`; 9Router thật thường nói giao thức OpenAI `/v1/chat/completions`. Đây là mục mở OI-ADAPT-05 của D (đã ghi ở `real_route_executor.py:5`), nằm ngoài phong bì của kế hoạch này; ghi thành OI-PP-01 (mục 7).
5. **Khai báo gói**: `src/controlplane/pyproject.toml` liệt kê gói tường minh (bảng `package-dir` quanh dòng 68-71 và danh sách `packages` từ dòng 74), nên `controlplane.infrastructure.production_ports` chưa được khai; tệp này nằm ngoài owned paths, ghi thành OI-PP-07 cho Control.

## 4. Thiết kế từng cổng (adapter ở `src/controlplane/infrastructure/production_ports/`)

Tên alias và tên tài khoản không phải bí mật; đặt trong `tools/launcher/prod/ports.json` (PP-2) và truyền vào adapter qua tham số, không có hằng số ẩn trong adapter. Mặc định (GIẢ ĐỊNH theo D8): `router_account_ref` = `router-primary`, `router_secret_ref` = `router-primary-api-key`.

### 4.1. `provider_credentials` — `RouterKeyCredentials` (PP-2)

- Cài `CredentialSourcePort.acquire(credential_method, account_ref)` là `contextmanager` trả khóa 9Router dạng `str`. Kiểm `credential_method == CREDENTIAL_METHOD` (`route_resolver.py:28`) và `account_ref == router_account_ref`; sai thì `ValueError`.
- Khóa lấy từ kho DPAPI qua alias riêng `router_secret_ref` bằng `DpapiRefreshTokenReader(store).read` (tái dùng `oauth_drive_token.py:58-67`); thiếu hoặc giải mã lỗi thì ném `ProviderCredentialError` (lớp mới, thông điệp không chứa giá trị). `NineRouterExecutor` bắt lỗi này và trả `ExecutionResult(False, ...)` (`real_route_executor.py:139-140`).
- Không đọc biến môi trường, không ghi đệm khóa ra đĩa, không đưa khóa vào log hay `repr`.
- **Nhập khóa vào kho**: hàm `store_router_key(store, secret_ref, read_value)` trong `router_key_entry.py` nhận giá trị qua `read_value()` (tập lệnh `tools/launcher/prod/set_router_key.py` truyền `getpass.getpass`, không hiện ký tự), bỏ khoảng trắng đầu cuối, từ chối giá trị rỗng, gọi `DpapiSecretStore.put(secret_ref, SecretValue(value))` (`dpapi_secret_store.py:45`) và chỉ in `Đã lưu khóa 9Router qua kho DPAPI: <alias> (v<phiên bản>)`. Giá trị không đi qua đối số dòng lệnh, log hay `report.md`.
- Test dùng kho DPAPI tạm trong `tmp_path` (DPAPI thật của Windows, không đụng kho thật ở `LOCALAPPDATA`) và canary tổng hợp; kiểm canary 0 lần xuất hiện trong `capsys`, `caplog`, `repr` và thông điệp ngoại lệ.

### 4.2. `route_catalog` — `ProfileRouteCatalog` (PP-6)

- Cài `candidates(workspace_id, ai_role)`: trả danh sách rỗng khi `ai_role` không có trong `route_model_refs` của profile (`profile.json:122-133`, sáu vai trò); ngược lại trả đúng một `RouteCandidate` cho tuyến 9Router: `provider_ref='9router'`, `model_ref = route_model_refs[ai_role]`, `candidate_ref = '9router:' + model_ref`, `cost_class='free'` (U1: không phát sinh chi phí), `max_data_sensitivity='internal'` (khớp `DATA_SENSITIVITY` ở `pipeline.py:49`), `local=False`, `quota_domain_key='9router-gemini'`, `roles` là tập vai trò.
- `ExternalAccount` dựng tại chỗ (`external_account.py:16-29`) với `external_account_id = router_account_ref`, `workspace_id` đúng tham số vừa nhận, `capabilities` là tập vai trò, `credential_version` lấy từ `store.current_version(router_secret_ref)`. Khi chưa có khóa trong kho thì `status=REVOKED` để resolver loại với `ACCOUNT_NOT_ELIGIBLE` (`route_resolver.py:99-102`) và dừng bằng `NoRouteError`, thay vì đi tới 9Router không khóa; có khóa thì `ENABLED`.
- Không đọc CSDL, không gọi mạng, không giữ bí mật.

### 4.3. `vision_route` — `RouterVisionRoute` (PP-7)

- Cài `invoke_vision(ai_role, instructions, image_base64, media_type, timeout_seconds)`: kiểm `ai_role` có trong `route_model_refs`; lấy khóa qua `RouterKeyCredentials.acquire`; gửi một yêu cầu `POST` tới `<endpoint>/chat/completions` (endpoint là `route_endpoint` của profile, đã kết thúc bằng `/v1`) bằng `urllib.request`, thân kiểu OpenAI `messages` gồm `instructions` và phần ảnh `data:<media_type>;base64,<image_base64>`; trả chuỗi `choices[0].message.content` cho `parse_vision_output` (`real_llm_image_safety.py:62`).
- Endpoint phải thuộc `ApprovedEndpointRegistry.from_config([route_endpoint])` (`adapter.py:96-110`); không theo redirect, không proxy; timeout theo tham số; mọi lỗi mạng hoặc HTTP đổi thành ngoại lệ không chứa khóa để detector fail-closed.
- GIẢ ĐỊNH (D8): chi phí vision không đi qua `RoutedInvocationService` vì tuyến 9Router Gemini miễn phí theo U1 (OI-PP-04).
- Test dùng máy chủ HTTP loopback đóng vai 9Router trong `tests/`; adapter không có nhánh giả.

### 4.4. `drive_token_broker` — `VaultAccountStatusPort` và `build_drive_token_broker` (PP-3)

- Tái dùng `DriveAccessTokenBroker` (`oauth_drive_token.py:70-155`); không viết lại luồng đổi token. PP-3 thêm `VaultAccountStatusPort.account_status(account_ref)` cài `AccountStatusPort` (`oauth_drive_token.py:41-43`): trả `ENABLED` khi `account_ref == ACCOUNT_REF` và `DpapiSecretStore.current_version(SECRET_REF)` khác `None`, ngược lại `REVOKED`.
- `build_drive_token_broker(client_secrets_path, max_ttl_seconds, store, clock)` ráp `DpapiRefreshTokenReader`, cổng trạng thái trên và `DriveAccessTokenBroker`; `max_ttl_seconds` lấy từ `profile.credential_max_ttl_seconds` (`production_profile.py:383`).
- Chỉ nhận `credential_method='secret_broker_handle'` và `account_ref='drive-primary'`; refresh token không rời broker, access token không vào log. Phạm vi `drive.file` do `run_consent` bảo đảm (`oauth_google_loopback.py:177-178`).
- Test: máy chủ HTTP loopback làm `token_uri` trong một `oauth-client.json` tạm; refresh token canary ghi vào kho DPAPI tạm. Kiểm: đổi token đúng một lần trong TTL, alias thiếu thì `DriveTokenDeniedError`, máy chủ trả lỗi thì `DriveTokenRefreshError`, canary 0 lần trong log và `repr`.

### 4.5. `artifact_source` — `StagingArtifactSource` (PP-4)

- Cài `open(artifact_version_id) -> BinaryIO`: mở tệp `rb` tại `staging_root / artifact_version_id` (`staging_root = layout.staging_dir`, `production_profile.py:401`). `artifact_version_id` phải khớp `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` và đường dẫn sau `resolve()` phải nằm trong `staging_root`; vi phạm thì `ValueError('INVALID_ARTIFACT_REF')`, thiếu tệp thì `FileNotFoundError`. Luồng trả về hỗ trợ `seek` và `tell` như `drive_object_store.py:278-281` cần.
- Kiểm chứa đường dẫn viết riêng trong tệp mới, không import `resolve_under_root` từ tầng `api` (`_shared.py:54-64`) để hạ tầng không phụ thuộc ngược vào `api`.
- GIẢ ĐỊNH (D8): quy ước tên tệp là chính `artifact_version_id`; bên ghi vào staging phải theo quy ước này, xác nhận ở CP7-3 (OI-PP-03).
- Test: tệp tạm trong `tmp_path`: đọc đúng nội dung, `seek` và `tell`, từ chối `..`, đường dẫn tuyệt đối, `C:` và tên có ký tự lạ, thiếu tệp.

### 4.6. `drive_placement` và `drive_fallback_parent_id` — `DrivePlacementBootstrap` (PP-5)

- Mặc định đơn giản (D8): lần chạy đầu tạo một thư mục gốc trong Drive test (tên lấy từ `drive.folders.root` của profile, hiện là `AI-Auto-Video-Creator`, `profile.json:477-487`; yêu cầu của gói ghi `AI Auto Video Creator` nên đây là OI-PP-02) và các thư mục con theo loại artifact `original`, `reusable`, `output`; lưu ID vào `<data_dir>/state/drive-placement.json` (ngoài Git, `Layout.state_dir` `launcher.py:83-85`); các lần sau đọc tệp và dùng lại.
- `drive_placement = {'original': <id>, 'reusable': <id>, 'output': <id>}` (khóa là các `namespace_ref`; thiếu khóa thì `DriveObjectStore` từ chối ở `drive_object_store.py:211-213`, đó là hành vi đúng). `drive_fallback_parent_id` là ID thư mục gốc.
- Gọi Drive bằng `googleapiclient` `build('drive', 'v3', http=..., static_discovery=True, cache_discovery=False)` đúng kiểu `drive_object_store.py:169-176`, với http gắn `Authorization: Bearer` từ `drive_token_broker` như `_BrokerHttp` (`:114-130`; viết lớp tương đương riêng, không import tên private); tham số `http_factory` cho phép test chuyển hướng tới máy chủ loopback. Với `drive.file` chỉ thấy tệp do chính ứng dụng tạo, nên xác minh bằng `files.get` theo ID đã lưu (`fields='id,trashed,mimeType'`); thiếu, đã vào thùng rác hoặc 404 thì tạo lại đúng thư mục đó và ghi đè tệp trạng thái; không dùng `files.list` toàn Drive.
- Ghi tệp trạng thái nguyên tử (tệp tạm rồi `os.replace`), UTF-8, chỉ chứa tên và ID thư mục, không chứa token. Thiếu token hoặc Drive lỗi thì ném `DrivePlacementError`; launcher dừng ở bước dựng cổng với thông điệp tiếng Việt an toàn (fail-closed), không tạo giá trị placement giả (OI-PP-06).
- Thư mục `output/YY-MM-DD` theo ngày (`profile.json:482`) cần ID mới mỗi ngày nên không đặt được trong ánh xạ tĩnh; v1 dùng một thư mục `output` (OI-PP-02).

### 4.7. `gpu_lease` — `LocalGpuLease` (PP-1)

- Cài `GpuLeasePort` (`lease.py:27-35`) trong một tiến trình: `acquire(owner_ref)` cấp `GpuLease(lease_id, owner_ref)` (`lock_id` mặc định `LOCK-DESKTOP-GPU`, `lease.py:13,20-24`) hoặc ném `GpuLeaseUnavailable` khi mọi slot đang bận; `release(lease)` trả slot, gọi lần hai là không làm gì.
- Một GPU: chỉ một khóa `LOCK-DESKTOP-GPU` cho một thiết bị RTX 4070 SUPER; số slot đồng thời đọc từ profile `gpu.slots` (`profile.json:457-465`, hiện `slots: 2`, xem OI-PP-05), không có hằng số trong adapter; constructor từ chối `lock` khác `GPU_LOCK_ID` và `slots` không phải số nguyên dương.
- Lease có thời hạn: `ttl_seconds = ceil(profile.render.timeout_seconds) + gpu_lease.grace_seconds` (`ports.json`, GIẢ ĐỊNH 60 giây); lease quá hạn bị thu hồi khi có `acquire` kế tiếp để tiến trình render chết không giữ slot vĩnh viễn; `release` lease đã quá hạn hoặc đã trả là no-op và không giải phóng lease mới. Renderer bị dừng cứng ở `render.timeout_seconds` nên một lần render sống không mất lease giữa chừng.
- An toàn luồng bằng `threading.Lock` (worker Temporal chạy trong luồng cùng tiến trình, `launcher.py:504-512`); đồng hồ `time.monotonic` tiêm được qua tham số `clock`; adapter không đọc `nvidia-smi` (kiểm GPU thật thuộc CP7-1).
- Test: đồng hồ tiêm được; hai lease trên một slot; lease quá hạn; tám luồng tranh một slot.

## 5. Chia slice (chi tiết ở `slices.md`)

| Slice | Cổng | Tệp adapter mới | Phụ thuộc |
| --- | --- | --- | --- |
| `PP-1` | `gpu_lease` và khung gói | `production_ports/__init__.py`, `gpu_lease.py` | `IMPL-PLAN-PROD-PORTS` |
| `PP-2` | `provider_credentials`, nhập khóa 9Router, cấu hình cổng | `credentials.py`, `router_key_entry.py`, `ports_config.py`, `tools/launcher/prod/ports.json`, `tools/launcher/prod/set_router_key.py` | `PP-1` |
| `PP-3` | `drive_token_broker` | `drive_token.py` | `PP-1` |
| `PP-4` | `artifact_source` | `artifact_source.py` | `PP-1` |
| `PP-5` | `drive_placement`, `drive_fallback_parent_id` | `drive_placement.py` | `PP-3` |
| `PP-6` | `route_catalog` | `route_catalog.py` | `PP-2` |
| `PP-7` | `vision_route` | `vision_route.py` | `PP-2` |
| `PP-8` | đấu nối launcher | `assembly.py`, sửa `tools/launcher/launcher.py` | `PP-1` đến `PP-7`, `ADAPT-LAUNCH` |

Thứ tự chạy tuần tự `PP-1` → `PP-8` trong một lane (khóa `LOCK-PROD-PORTS`, GIẢ ĐỊNH Control đăng ký). Mỗi slice có test ở `tests/integration/prod_ports/test_pp_<số>_*.py` và bằng chứng ở `docs/delivery-evidence/pp-<số>/report.md`. `PP-8` là slice duy nhất của kế hoạch này sửa `tools/launcher/launcher.py` nên giữ một owner (quy tắc single-writer cho tài nguyên chung). Tệp này cũng nằm trong `ownedPaths` của `ADAPT-LAUNCH` (kế hoạch impl-adapt-r1, khóa `LOCK-COMPOSITION-ROOT`); để hai kế hoạch không chồng đường dẫn, `PP-8` khai `dependsOn` `ADAPT-LAUNCH` (chạy sau khi `ADAPT-LAUNCH` và gói sửa ADAPT-LAUNCH-FIX1 đã tích hợp, hiện ở `21d99fc`) và giữ thêm `LOCK-COMPOSITION-ROOT` cùng `LOCK-CONVERGENCE`, nên mỗi lúc chỉ một writer sửa `launcher.py`. `PP-8` chỉ thay thân ba hàm `_load_runtime_ports`, `build_runtime`, `cmd_status`.

## 6. Kiểm thật cuối (CP7-1 khi chạy lại)

Không slice PP nào gọi dịch vụ thật (D4, D5). Sau `PP-8`, Control chạy lại CP7-1 với điều kiện:

1. `python tools/launcher/launcher.py start`: docker compose dựng `aiavc-postgres` cổng 57028 và Temporal cổng 7233, migration chạy, `_serve` dựng đủ sáu cổng (lần đầu tạo thư mục Drive và ghi `state/drive-placement.json`), cổng `127.0.0.1:8443` mở (`wait_tcp`, `launcher.py:666`) và in `Đã khởi động`.
2. `python tools/launcher/launcher.py status` in `Cổng 57028 (PostgreSQL): Mở`, `Cổng 7233 (Temporal): Mở`, `Cổng 8443 (Application): Mở` (`launcher.py:747-749`) và sáu dòng `Cổng runtime <tên>: sẵn sàng` cho `route_catalog`, `provider_credentials`, `vision_route`, `artifact_source`, `drive_token_broker`, `gpu_lease` cùng một dòng cho `drive_placement` (PP-8 thêm các dòng này).
3. Điều kiện của user: alias `drive-primary-oauth` đã có trong kho (D5, đã làm); alias `router-primary-api-key` do user nhập một lần bằng `python tools/launcher/prod/set_router_key.py` nếu 9Router đòi khóa. Thiếu khóa thì `route_catalog` loại tuyến với `ACCOUNT_NOT_ELIGIBLE`: ứng dụng vẫn mở 8443 nhưng lời gọi AI chờ.
4. Quét bí mật của CP7-1 trên `serve.log` và `report.md`: 0 lần khớp.

Nếu `start` vẫn chặn thì báo BLOCKED kèm dòng `serve.log` đã che bí mật; CP7 không sửa `src/**`.

## 7. Mục mở và rủi ro (mặc định theo D8; không ghi là đã duyệt)

| Mã | Nội dung | Mặc định của kế hoạch | Chủ xử lý |
| --- | --- | --- | --- |
| OI-PP-01 | `NineRouterHTTPAdapter` gọi `{endpoint}/v1/chat` với thân `{'prompt': ...}` (`adapter.py:216-217`), lệch endpoint profile `.../v1` và giao thức OpenAI của 9Router | Không sửa `adapter.py`; `vision_route` (PP-7) dùng `<endpoint>/chat/completions`. Lời gọi văn bản (script, hook) có thể lệch cho tới khi chủ D sửa | Control lập gói sửa cho D; lộ ra ở CP7-4 (RG-03) |
| OI-PP-02 | Tên thư mục gốc: yêu cầu của gói ghi `AI Auto Video Creator`, profile ghi `AI-Auto-Video-Creator` (`profile.json:479`); thư mục `output/YY-MM-DD` theo ngày không đặt được trong ánh xạ tĩnh | Lấy tên từ profile (nguồn có revision, CP7-3 dùng `AI-Auto-Video-Creator`); một thư mục `output` | Control xác nhận; đổi tên chỉ là đổi một giá trị cấu hình |
| OI-PP-03 | Từ vựng `namespace_ref` không cố định trong mã (`handlers={}` ở `launcher.py:470`, người gọi ở `cloud_persist.py:86`); quy ước tên tệp staging theo `artifact_version_id` | Ba khóa `original`, `reusable`, `output` (khớp `profile.json:477-487`); tên tệp là `artifact_version_id`; khóa lạ làm `DriveObjectStore` từ chối (fail-closed, đúng) | Gói handler và materialization; xác nhận ở CP7-3 |
| OI-PP-04 | Chi phí gọi vision không qua `RoutedInvocationService` và `CostLedgerPort` | 9Router Gemini miễn phí theo U1; không ghi sổ; `hard_stop` 50 USD không bao phủ vision | Control; theo dõi ở CP7-4 |
| OI-PP-05 | Yêu cầu «đúng một GPU» và profile `gpu.slots: 2` (`profile.json:457-465`) | Một khóa `LOCK-DESKTOP-GPU`, số slot đọc từ profile; muốn tuần tự tuyệt đối thì Control đổi profile sang `slots: 1` bằng revision mới | Control |
| OI-PP-06 | Dựng `drive_placement` cần Drive ở mỗi lần `start` (xác minh ID đã lưu bằng `files.get`) | Fail-closed: mất mạng hoặc thiếu token thì `start` không mở 8443 và báo thông điệp tiếng Việt an toàn | Control chấp nhận; dựng lazy cần đổi hợp đồng `ProductionRuntime` nên bị cấm |
| OI-PP-07 | `src/controlplane/pyproject.toml` chưa khai gói `controlplane.infrastructure.production_ports` | Test và launcher chạy từ cây nguồn (`pythonpath = ['src']`, `ensure_src_on_path`) nên không chặn PP-1 đến PP-7; Control khai (bảng `package-dir` và `packages`) trước khi đóng gói và trước PP-8 | Control (dependency slice) |

## 8. Đối chiếu counterexample của gói

1. Bỏ sót một cổng hay `drive_placement`: mục 3.1 liệt kê đủ sáu cổng cùng `drive_placement` và `drive_fallback_parent_id`; mục 5 gán từng cổng cho đúng một slice.
2. Slice sở hữu đường dẫn ngoài phong bì: mọi `ownedPaths` nằm trong `src/controlplane/infrastructure/production_ports/**`, `tests/integration/prod_ports/**`, `docs/delivery-evidence/pp-*/**`, `tools/launcher/prod/**`; riêng `PP-8` thêm `tools/launcher/launcher.py` (chồng đường dẫn với `ADAPT-LAUNCH` được giải bằng `dependsOn` `ADAPT-LAUNCH` và khóa `LOCK-COMPOSITION-ROOT`, xem mục 5). Không có `src/**` ngoài thư mục mới, không migration, không `docker-compose.yml`.
3. Adapter có nhánh giả hay đọc biến môi trường thay cho kho DPAPI: khóa và token chỉ qua `DpapiSecretStore`; mỗi slice có probe cấm `mock`, `fake`, `os.environ` trong tệp adapter.
4. Slice không có test thật: mỗi slice có tệp `test_pp_<số>_*.py` với oracle riêng; Google và 9Router thay bằng máy chủ loopback trong `tests/`.
5. Cần thư viện mới: không; chỉ stdlib và các gói đã khóa (`google-auth`, `google-api-python-client`, `httplib2`, `pytest`).
6. Đổi hợp đồng `ProductionRuntime` hay Protocol: không; adapter cài đúng chữ ký, và `PP-8` dựng `ProductionRuntime` nguyên trạng bằng tám giá trị cổng.

## 9. Giới hạn

Gói này lập kế hoạch theo quyền điều phối user giao ngày 22/10/2026; nội dung do Worker (Gemini 3.8 Flash) viết, Auditor rủi ro (Opus 5.5) duyệt trước khi biên dịch. Kiểm thật trên Drive, 9Router và GPU làm ở CP7; kế hoạch không gọi dịch vụ thật và không đọc bí mật.
