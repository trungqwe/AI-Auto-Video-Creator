# Slice nối cổng ProductionRuntime — IMPL-PLAN-PROD-PORTS

Nguồn: `docs/implementation/prod-ports/plan.md`. Tám slice `PP-1` đến `PP-8`; `PP-1` đến `PP-7` là `work_package_slice`, `PP-8` là `convergence_slice` (sửa `tools/launcher/launcher.py`). Chạy tuần tự trong một lane (`LOCK-PROD-PORTS`, GIẢ ĐỊNH: Control đăng ký khóa này); `PP-8` thêm `LOCK-CONVERGENCE` và `LOCK-COMPOSITION-ROOT`, đồng thời phụ thuộc `ADAPT-LAUNCH` (chủ hiện hành của `tools/launcher/launcher.py` trong kế hoạch impl-adapt-r1; gói sửa ADAPT-LAUNCH-FIX1 đã tích hợp tại `21d99fc`), nên `PP-8` chạy sau `ADAPT-LAUNCH` và hai kế hoạch không chồng đường dẫn tại cùng một thời điểm. Kiểm thật trên tài nguyên thật làm ở CP7-1 (plan.md mục 6).

## Quy tắc chung cho mọi slice

- Chỉ sửa tệp trong `ownedPaths`; không sửa `src/**` ngoài `src/controlplane/infrastructure/production_ports/**`, migration, `docker-compose.yml`, `profile.json`, lockfile, `tests/m1`, `tests/m2`, `tests/integration/adapt/**`, `ui/dist`, `docs/milestones/**/evidence/**`. Không đổi chữ ký Protocol hay hợp đồng `ProductionRuntime`; không thêm thư viện (D10).
- Adapter production không có nhánh giả: không `fake`, `mock`, `memory`, không `os.environ`, không đọc bí mật từ tệp văn bản; bí mật chỉ qua `DpapiSecretStore`. Tham số tiêm (`http_factory`, `clock`) chỉ là điểm nối của test; máy chủ giả nằm trong `tests/`.
- Test dùng kho DPAPI tạm trong `tmp_path` và canary tổng hợp; không mở kho thật, không đọc `Credentials/`, không gọi Google, 9Router hay GPU thật; không in token hay khóa ở bất kỳ đâu.
- `tests/integration/prod_ports/` không có `__init__.py`; tên tệp test duy nhất `test_pp_<số>_<tên>.py` để không trùng basename với test khác.
- Test-first: thấy RED do assertion đúng oracle rồi mới implement tới GREEN.
- Bằng chứng ở `docs/delivery-evidence/pp-<số>/report.md`: lệnh đã chạy, mã thoát, số test pass; không ghi bí mật. Mọi `testCommands` chạy bằng interpreter khóa.

### PP-1: Khung gói production_ports và gpu_lease một GPU

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/__init__.py`
  - `src/controlplane/infrastructure/production_ports/gpu_lease.py`
  - `tests/integration/prod_ports/test_pp_1_gpu_lease.py`
  - `docs/delivery-evidence/pp-1/report.md`
- dependsOn: `IMPL-PLAN-PROD-PORTS`
- resourceLocks: `LOCK-PROD-PORTS`
- bindingRefs: `src/render/ports/lease.py:13-35`; `src/render/adapters/real_ffmpeg_renderer.py:185-191`; `tools/launcher/prod/profile.json` khóa `gpu.slots` (dòng 457-465)
- acceptance:
  - requirement: (1) `__init__.py` chỉ có docstring. (2) `gpu_lease.py`: lớp `LocalGpuLease(slots, ttl_seconds, *, lock_id=GPU_LOCK_ID, clock=time.monotonic)` cài `GpuLeasePort`; `acquire(owner_ref)` cấp `GpuLease` với `lease_id` duy nhất (`uuid.uuid4().hex`), ném `GpuLeaseUnavailable` khi đã đủ `slots` lease chưa hết hạn, thu hồi lease quá hạn trước khi đếm; `release` idempotent và so theo `lease_id` (lease cũ không giải phóng lease mới); dùng `threading.Lock`. (3) Constructor từ chối `slots` không phải int dương (kể cả bool), `ttl_seconds` không dương, `lock_id` khác `GPU_LOCK_ID`; `owner_ref` rỗng là `ValueError`. (4) Không đọc `nvidia-smi`, không biến môi trường, không hằng số slot.
    instrument: test với đồng hồ tiêm được: `slots=1` thì `acquire` lần hai ném `GpuLeaseUnavailable`; `release` rồi `acquire` được; `release` hai lần là no-op; hết hạn thì slot cấp lại và `release` lease cũ không giải phóng lease mới; `slots=2` cấp đúng hai lease; tám luồng tranh một slot chỉ một thắng.
    counterexample: số slot cố định trong mã; lease không hạn; `release` lease cũ giải phóng lease mới; nhánh giả; sửa `lease.py`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_ports/test_pp_1_gpu_lease.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/gpu_lease.py').read_text(encoding='utf-8').lower(); assert 'gpulease' in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-1'"`

### PP-2: provider_credentials, nhập khóa 9Router vào kho DPAPI và cấu hình cổng

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/credentials.py`
  - `src/controlplane/infrastructure/production_ports/router_key_entry.py`
  - `src/controlplane/infrastructure/production_ports/ports_config.py`
  - `tools/launcher/prod/ports.json`
  - `tools/launcher/prod/set_router_key.py`
  - `tests/integration/prod_ports/test_pp_2_credentials.py`
  - `docs/delivery-evidence/pp-2/report.md`
- dependsOn: `PP-1`
- resourceLocks: `LOCK-PROD-PORTS`
- bindingRefs: `src/creative/adapters/real_route_executor.py:100-142`; `src/controlplane/application/config_security/route_resolver.py:28`; `src/controlplane/infrastructure/security/dpapi_secret_store.py:16-112`; `src/controlplane/infrastructure/security/oauth_drive_token.py:51-67`
- acceptance:
  - requirement: (1) `ports.json` (UTF-8): `revision`, `router` (`account_ref` `router-primary`, `secret_ref` `router-primary-api-key`), `gpu_lease` (`grace_seconds` 60), `drive` (`placement_state_file` `drive-placement.json`, `artifact_namespaces` `original`, `reusable`, `output`); `ports_config.py` có `PortsConfig` (dataclass frozen) và `load_ports_config(path)` kiểm chặt, thiếu hoặc sai kiểu thì `ValueError`, không mặc định ngầm. (2) `credentials.py`: `ProviderCredentialError` và `RouterKeyCredentials(store, router_account_ref, router_secret_ref)` cài `CredentialSourcePort`: `acquire` là `contextmanager`, kiểm `credential_method == CREDENTIAL_METHOD` và `account_ref` đúng (sai thì `ValueError`), đọc khóa bằng `DpapiRefreshTokenReader(store).read`; thiếu hoặc giải mã lỗi thì `ProviderCredentialError` không chứa giá trị; `__repr__` che. (3) `router_key_entry.py`: `store_router_key(store, secret_ref, read_value)` (bỏ khoảng trắng đầu cuối, từ chối rỗng, gọi `store.put`, trả phiên bản) và `run(vault_dir, ports_config_path, read_value, out)` chỉ in `Đã lưu khóa 9Router qua kho DPAPI: <alias> (v<n>)`. (4) `set_router_key.py`: tập lệnh mỏng thêm `src` và `tools/launcher` vào `sys.path`, gọi `launcher.resolve_layout(os.environ)` rồi `run(layout.vault_dir, <ports.json>, getpass.getpass, print)`; không nhận khóa qua đối số.
    instrument: kho DPAPI tạm: `store_router_key` rồi `acquire` trả đúng giá trị canary; `credential_method` hay `account_ref` lạ thì `ValueError`; thiếu alias hoặc sau `revoke` thì `ProviderCredentialError`; giá trị rỗng hoặc toàn khoảng trắng bị từ chối; canary 0 lần trong `capsys`, `caplog`, `repr` và `str` của ngoại lệ; dòng in của `run` đúng mẫu; `load_ports_config` nhận `ports.json` thật và từ chối bản thiếu khóa; `ast.parse` `set_router_key.py` có `getpass.getpass` và không chứa `sys.argv`.
    counterexample: đọc khóa từ biến môi trường hay tệp văn bản; nhận khóa qua đối số dòng lệnh; in giá trị; thêm lệnh con vào `launcher.COMMANDS` (làm đỏ `test_adapt_launch_cli.py:232-233`); mặc định ngầm trong `ports_config.py`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_ports/test_pp_2_credentials.py -q -p no:cacheprovider`
  - `python -c "import pathlib, json; d = pathlib.Path('src/controlplane/infrastructure/production_ports'); t = ' '.join((d / n).read_text(encoding='utf-8').lower() for n in ['credentials.py', 'router_key_entry.py', 'ports_config.py']); assert 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-2'; j = json.loads(pathlib.Path('tools/launcher/prod/ports.json').read_text(encoding='utf-8')); assert j['router']['secret_ref'] != 'drive-primary-oauth', 'alias'"`

### PP-3: drive_token_broker trên kho DPAPI

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/drive_token.py`
  - `tests/integration/prod_ports/test_pp_3_drive_token.py`
  - `docs/delivery-evidence/pp-3/report.md`
- dependsOn: `PP-1`
- resourceLocks: `LOCK-PROD-PORTS`
- bindingRefs: `src/controlplane/infrastructure/storage/drive_object_store.py:43-44,114-130`; `src/controlplane/infrastructure/security/oauth_drive_token.py:41-155`; `src/controlplane/infrastructure/security/oauth_google_loopback.py:18-20,141-189`; `src/controlplane/api/wiring/config_security.py:80-93,119-130`
- acceptance:
  - requirement: (1) `VaultAccountStatusPort(store)` cài `AccountStatusPort`: `account_status(account_ref)` trả `ExternalAccountStatus.ENABLED` khi `account_ref == ACCOUNT_REF` và `store.current_version(SECRET_REF)` khác `None`, ngược lại `REVOKED`; không đọc CSDL. (2) `build_drive_token_broker(client_secrets_path, max_ttl_seconds, store, clock)` trả `DriveAccessTokenBroker` ráp từ `DpapiRefreshTokenReader(store)`, cổng trạng thái trên và `clock`; tái dùng lớp có sẵn, không viết lại luồng đổi token, không sửa `oauth_drive_token.py`. (3) Chỉ nhận `secret_broker_handle` và `drive-primary`; lỗi không chứa token.
    instrument: máy chủ HTTP loopback trong test làm `token_uri` của một `oauth-client.json` tạm (ngoài cây Git); refresh token canary ghi bằng `DpapiSecretStore` tạm: hai lần `acquire` trong TTL chỉ gọi máy chủ một lần, qua TTL thì gọi lại; kho không có alias thì `DriveTokenDeniedError` và máy chủ 0 lần gọi; máy chủ trả 400 thì `DriveTokenRefreshError`; phương thức hay `account_ref` lạ thì `ValueError`; canary và access token 0 lần trong `caplog`, `capsys`, `repr` và thông điệp lỗi; `VaultAccountStatusPort` đủ hai nhánh.
    counterexample: đọc trạng thái từ CSDL; đọc token từ biến môi trường; ghi đệm token ra đĩa; bỏ kiểm `account_ref`; sửa `oauth_drive_token.py`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_ports/test_pp_3_drive_token.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/drive_token.py').read_text(encoding='utf-8').lower(); assert 'driveaccesstokenbroker' in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-3'"`

### PP-4: artifact_source đọc tệp từ thư mục staging

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/artifact_source.py`
  - `tests/integration/prod_ports/test_pp_4_artifact_source.py`
  - `docs/delivery-evidence/pp-4/report.md`
- dependsOn: `PP-1`
- resourceLocks: `LOCK-PROD-PORTS`
- bindingRefs: `src/controlplane/infrastructure/storage/drive_object_store.py:39-40,265-282`; `src/controlplane/api/wiring/production_profile.py:401`; `tools/launcher/launcher.py:71-73`; `src/controlplane/api/wiring/_shared.py:54-64` (chỉ để đối chiếu, không import)
- acceptance:
  - requirement: `StagingArtifactSource(staging_root)` cài `ArtifactSourcePort`: `staging_root` phải là `Path` tuyệt đối; `open(artifact_version_id)` kiểm `artifact_version_id` khớp `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`, đường dẫn `(staging_root / id).resolve()` nằm trong `staging_root.resolve()` và là tệp thường, rồi mở `rb`; sai thì `ValueError('INVALID_ARTIFACT_REF')`, thiếu thì `FileNotFoundError`. Kiểm chứa đường dẫn viết riêng, không import `resolve_under_root` từ tầng `api`; không ghi, không xóa tệp. GIẢ ĐỊNH (D8, OI-PP-03): tên tệp là `artifact_version_id`.
    instrument: tệp tạm trong `tmp_path`: đọc đúng nội dung và băm sha256 khớp; `seek(0, 2)`, `tell()` rồi `seek(0)` như `drive_object_store.py:278-281`; từ chối `..`, `a/b`, đường dẫn tuyệt đối, `C:x`, chuỗi rỗng, độ dài 129, ký tự điều khiển; thiếu tệp; `staging_root` tương đối bị từ chối; thư mục thay cho tệp bị từ chối.
    counterexample: import `resolve_under_root` từ `controlplane.api`; cho phép thoát khỏi staging; ghi hay xóa tệp; nhánh giả.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_ports/test_pp_4_artifact_source.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/artifact_source.py').read_text(encoding='utf-8').lower(); assert 'controlplane.api' not in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-4'"`

### PP-5: drive_placement và drive_fallback_parent_id

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/drive_placement.py`
  - `tests/integration/prod_ports/test_pp_5_drive_placement.py`
  - `docs/delivery-evidence/pp-5/report.md`
- dependsOn: `PP-3`
- resourceLocks: `LOCK-PROD-PORTS`
- bindingRefs: `src/controlplane/infrastructure/storage/drive_object_store.py:47-80,114-130,150-176,208-224,265-277`; `src/controlplane/api/wiring/storage.py:64-83`; `src/controlplane/api/wiring/production_profile.py:447-455`; `tools/launcher/prod/profile.json:477-487`
- acceptance:
  - requirement: (1) `DrivePlacementError` và `DrivePlacementBootstrap(broker, state_file, root_name, namespaces, *, retry_max_attempts, backoff_base_seconds, backoff_cap_seconds, timeout_seconds, http_factory=None, sleep=time.sleep)` có `ensure()` trả `DrivePlacement` (dataclass frozen: `placement: Mapping[str, str]`, `fallback_parent_id: str`). (2) Lần đầu tạo thư mục gốc `root_name` rồi một thư mục con cho mỗi namespace (mimeType `application/vnd.google-apps.folder`, `parents` đúng) và ghi `state_file` nguyên tử (UTF-8, tệp tạm rồi `os.replace`) chỉ gồm tên và ID; lần sau đọc tệp và xác minh từng ID bằng `files.get(fields='id,trashed,mimeType')`, ID thiếu, 404 hay đã vào thùng rác thì tạo lại đúng thư mục đó và ghi đè; không `files.list`. (3) Gọi Drive bằng `build('drive', 'v3', http=..., static_discovery=True, cache_discovery=False)` với http gắn `Authorization: Bearer` từ `broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF)` (lớp http tương đương `_BrokerHttp`, viết riêng); lỗi tạm (408, 429, 5xx) thử lại tối đa `retry_max_attempts` rồi `DrivePlacementError`; 401, 403 hoặc thiếu token thì `DrivePlacementError` ngay; tệp trạng thái hỏng thì `DrivePlacementError` (fail-closed). (4) `fallback_parent_id` là ID thư mục gốc; `placement` không rỗng.
    instrument: máy chủ Drive giả loopback trong test (xử lý `POST /drive/v3/files` và `GET /drive/v3/files/<id>`), `http_factory` của test chuyển `https://www.googleapis.com` sang loopback và máy chủ kiểm có `Authorization`: lần đầu tạo đúng 4 thư mục với `parents` đúng và ghi tệp trạng thái; lần hai 0 lần tạo; thùng rác và 404 tạo lại đúng một thư mục; 503 hai lần rồi 200 thành công; 403 thì lỗi ngay; tệp trạng thái hỏng thì lỗi; tệp trạng thái không chứa token (canary); `DriveObjectStore.reserve_object_id` nhận được cha từ `placement` (dùng `DriveStoreConfig`).
    counterexample: tạo thư mục mới mỗi lần chạy; `files.list` toàn Drive; token vào tệp trạng thái; placement giả khi Drive lỗi; ghi tệp trạng thái không nguyên tử.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_ports/test_pp_5_drive_placement.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/drive_placement.py').read_text(encoding='utf-8').lower(); assert 'static_discovery=true' in t and 'files().list' not in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-5'"`

### PP-6: route_catalog theo hồ sơ production

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/route_catalog.py`
  - `tests/integration/prod_ports/test_pp_6_route_catalog.py`
  - `docs/delivery-evidence/pp-6/report.md`
- dependsOn: `PP-2`
- resourceLocks: `LOCK-PROD-PORTS`
- bindingRefs: `src/controlplane/application/config_security/route_resolver.py:21-59,99-102,119-214`; `src/controlplane/domain/config_security/external_account.py:16-29,63-70`; `src/controlplane/api/wiring/creative.py:142-172`; `src/creative/application/pipeline.py:49`; `tools/launcher/prod/profile.json:116-133`
- acceptance:
  - requirement: `ProfileRouteCatalog(model_refs, account_ref, secret_ref, store)` cài `RouteCatalogPort.candidates(workspace_id, ai_role)`: vai trò không có trong `model_refs` thì trả danh sách rỗng; ngược lại trả đúng một `RouteCandidate` với `provider_ref='9router'`, `model_ref=model_refs[ai_role]`, `candidate_ref='9router:' + model_ref`, `cost_class='free'`, `max_data_sensitivity='internal'`, `local=False`, `quota_domain_key='9router-gemini'`, `roles` là tập vai trò, và `ExternalAccount` có `external_account_id=account_ref`, `workspace_id` đúng tham số gọi, `capabilities` là tập vai trò, `status=ENABLED` khi `store.current_version(secret_ref)` khác `None`, ngược lại `REVOKED`. Thuần: không mạng, không CSDL, không đọc giá trị bí mật.
    instrument: dùng `ProviderRouteResolver` và `CapacityReservationBook` thật với `InMemoryReservationStore` của wiring (chỉ trong test): cả sáu vai trò `analysis`, `angle`, `script`, `selection`, `metadata`, `image_safety` cho decision có `account_ref='router-primary'`, `model_ref` đúng profile và `credential_acquisition_method='secret_broker_handle'`; chưa có khóa thì `NoRouteError` mã `NO_ELIGIBLE_ROUTE` kèm `ACCOUNT_NOT_ELIGIBLE`; vai trò lạ thì `NO_ELIGIBLE_ROUTE`; sau `revoke` khóa thì bị loại; `workspace_id` của account khớp tham số.
    counterexample: đọc CSDL hay gọi mạng; hard-code tên model; cho tuyến chạy khi thiếu khóa; sửa `route_resolver.py`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_ports/test_pp_6_route_catalog.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/route_catalog.py').read_text(encoding='utf-8').lower(); assert 'routecandidate' in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-6'"`

### PP-7: vision_route qua 9Router

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/vision_route.py`
  - `tests/integration/prod_ports/test_pp_7_vision_route.py`
  - `docs/delivery-evidence/pp-7/report.md`
- dependsOn: `PP-2`
- resourceLocks: `LOCK-PROD-PORTS`
- bindingRefs: `src/voice/adapters/real_llm_image_safety.py:20-40,62-120,177`; `src/controlplane/api/wiring/voice.py:123-137`; `src/controlplane/config/adapter.py:96-110`; `tools/launcher/prod/profile.json:116-133,290-301`
- acceptance:
  - requirement: `RouterVisionRoute(endpoint, model_refs, credentials, account_ref)` cài `VisionRoutePort.invoke_vision(ai_role, instructions, image_base64, media_type, timeout_seconds)`: `ai_role` phải có trong `model_refs`; khóa lấy qua `credentials.acquire(CREDENTIAL_METHOD, account_ref)`; gửi `POST <endpoint>/chat/completions` bằng `urllib.request` với thân kiểu OpenAI (model, `messages` gồm `instructions` và ảnh `data:<media_type>;base64,<image_base64>`), `Authorization: Bearer`; trả `choices[0].message.content`. `endpoint` phải thuộc `ApprovedEndpointRegistry.from_config([endpoint])`; không theo redirect, không proxy, timeout theo tham số; lỗi mạng hay HTTP (401, 429, 5xx) và phản hồi sai dạng đổi thành ngoại lệ không chứa khóa.
    instrument: máy chủ HTTP loopback đóng vai 9Router: kiểm đường dẫn, thân JSON có data URL, header Bearer là canary từ kho DPAPI tạm; nội dung trả về qua `parse_vision_output` ra `ImageDetection` đúng; 401, 429, 500, thân hỏng, 302 (không theo), timeout đều là ngoại lệ không lộ canary; `ai_role` lạ bị từ chối trước khi gọi mạng; endpoint ngoài danh sách bị từ chối.
    counterexample: gọi host khác 9Router; theo redirect; khóa vào log hay ngoại lệ; nhánh giả trong mã production.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_ports/test_pp_7_vision_route.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/vision_route.py').read_text(encoding='utf-8').lower(); assert 'chat/completions' in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-7'"`

### PP-8: Đấu nối launcher, trạng thái cổng runtime và kiểm hợp đồng ProductionRuntime

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/assembly.py`
  - `tools/launcher/launcher.py`
  - `tests/integration/prod_ports/test_pp_8_launcher_ports.py`
  - `docs/delivery-evidence/pp-8/report.md`
- dependsOn: `PP-1`, `PP-2`, `PP-3`, `PP-4`, `PP-5`, `PP-6`, `PP-7`, `ADAPT-LAUNCH`
- resourceLocks: `LOCK-PROD-PORTS`, `LOCK-COMPOSITION-ROOT`, `LOCK-CONVERGENCE`
- bindingRefs: `tools/launcher/launcher.py:416-449,725-756,378-381`; `src/controlplane/api/wiring/production_profile.py:393-467`; `tests/integration/adapt/launch/test_adapt_launch_cli.py:207-233`; `tools/launcher/prod/ports.json`; `docs/implementation/adapt/slices.md` mục `ADAPT-LAUNCH` (ownedPaths gồm `tools/launcher/launcher.py`, khóa `LOCK-COMPOSITION-ROOT`)
- acceptance:
  - requirement: (1) `assembly.py`: `build_production_ports(profile, *, vault_dir, staging_dir, state_dir, oauth_client_secrets_path, ports_config, http_factory=None)` trả đúng tám khóa `route_catalog`, `provider_credentials`, `vision_route`, `artifact_source`, `drive_token_broker`, `gpu_lease`, `drive_placement`, `drive_fallback_parent_id`: `LocalGpuLease` với slot từ `profile.parameters['gpu.slots']` và TTL `ceil(profile.render.timeout_seconds) + grace_seconds`; `DrivePlacementBootstrap` với tên gốc từ `profile.parameters['drive.folders']` và retry từ `profile.drive.retry`; các adapter PP-2 đến PP-7 với `profile.ai.route_endpoint` và `profile.ai.route_model_refs`; và `describe_runtime_ports(...)` trả danh sách (tên, sẵn sàng, lý do) chỉ kiểm sự tồn tại của alias, tệp OAuth client, thư mục staging và tệp trạng thái placement, không giải mã, không mạng. (2) `launcher.py`: thân `_load_runtime_ports` nhận `(profile, layout, environ, *, http_factory=None)`, import `production_ports` trong thân hàm sau `ensure_src_on_path()`, tải `tools/launcher/prod/ports.json`, gọi `build_production_ports`, đổi mọi lỗi cổng (`DrivePlacementError`, `DriveTokenError`, `ProviderCredentialError`, `ValueError`) thành `LauncherError` bắt đầu bằng `BLOCKED:` bằng tiếng Việt, không chứa bí mật; `build_runtime` gọi `_load_runtime_ports(profile, layout, environ)`; `cmd_status` thêm sau ba dòng cổng (`launcher.py:747-749`) các dòng `Cổng runtime <tên>: sẵn sàng` hoặc `Cổng runtime <tên>: thiếu (<lý do an toàn>)`, lỗi khi mô tả thì in `không xác định`. Không đổi `COMMANDS`, `docker-compose.yml` hay hàm khác. (3) Quan hệ sở hữu `launcher.py`: `PP-8` chỉ bắt đầu sau khi `ADAPT-LAUNCH` (kể cả gói sửa ADAPT-LAUNCH-FIX1, tích hợp tại `21d99fc`) đã nằm trong HEAD cơ sở của lane, giữ `LOCK-COMPOSITION-ROOT` suốt slice, và là writer duy nhất của `tools/launcher/launcher.py` trong kế hoạch này; chỉ thay thân `_load_runtime_ports`, `build_runtime`, `cmd_status`.
    instrument: kho DPAPI tạm có refresh token canary, `oauth-client.json` tạm có `token_uri` loopback, máy chủ loopback cho token và Drive (`http_factory`): `_load_runtime_ports` trả tám khóa và `ProductionRuntime(...)` dựng được với chúng (kiểm `__post_init__`); lần hai dùng lại tệp trạng thái, 0 lần tạo thư mục; thiếu refresh token thì `LauncherError` bắt đầu `BLOCKED:`; `cmd_status` in đủ sáu dòng cổng cộng `drive_placement` và không lộ canary; `test_adapt_launch_cli.py` vẫn xanh nguyên vẹn (kể cả `test_commands_are_the_seven` và kiểm import đầu tệp).
    counterexample: import `production_ports` ở đầu `launcher.py`; thêm lệnh con; đổi `ProductionRuntime`; placement giả khi Drive lỗi; sửa `docker-compose.yml`; in bí mật ở `status`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/prod_ports/test_pp_8_launcher_ports.py tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('tools/launcher/launcher.py').read_text(encoding='utf-8'); assert 'thi' + chr(7871) + 'u adapter' not in t and 'build_production_ports' in t and 'from src.' not in t, 'PP-8'"`
