# Slice hội tụ mở rộng — IMPL-PLAN-CONVERGENCE-EXT-UI

Nguồn: `docs/implementation/convergence-ext-ui/plan.md`. Mở rộng `docs/implementation/convergence/slices.md`; bốn slice đều là `convergence_slice`.

## Quy tắc chung cho mọi slice

- Chỉ sửa đúng các tệp trong `ownedPaths`, giữ khóa trong `resourceLocks` (mọi slice giữ `LOCK-CONVERGENCE`, chạy tuần tự).
- Cấm sửa `docs/milestones/**/evidence/**`, kế hoạch phân hệ `docs/implementation/a` đến `j`, `docs/09-contracts/**`, `protected-checkouts/**`, năm spec M2 trong `tests/m2/e2e/`, `components/Header.tsx` và `control_api_commands.py`.
- Test ghim của H được sửa để mở rộng, không làm yếu: không xóa ca kiểm, không skip, không nới tập đã biết (plan.md mục 4).
- `GATE-PERSIST-A`..`GATE-PERSIST-G`, `GATE-PERSIST-I`, `GATE-PERSIST-J` và `USER-CKPT-D9-D10` là cổng chờ, không phải slice; thiếu cổng thì slice BLOCKED, không bỏ cạnh.
- Test-first: thấy RED do assertion đúng oracle (ImportError, thiếu tệp hay thiếu binary không phải RED hợp lệ) rồi mới implement. `testCommands` chạy bằng interpreter khoá; lệnh `npm` chạy trong `src/controlplane/ui`. Bằng chứng ở `docs/delivery-evidence/<id viết thường>/report.md`.
- Mỗi slice có tiêu đề cấp 3 dạng `CP-<mã>: <tên>`, rồi kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance, testCommands, notes.

### CP-4-EVENT-KINDS: Đăng ký event kind SSE của các phân hệ (BL-CV-02)

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/application/sse/event_catalog.py`
  - `src/controlplane/ui/src/api/streamEventKinds.ts`
  - `tests/unit/control_ui/test_h_stream_event_catalog.py`
  - `tests/unit/control_ui/test_h_stream_client_registry.py`
  - `tests/unit/control_ui/test_h_ts_contract_types.py`
  - `docs/delivery-evidence/cp-4-event-kinds/report.md`
- dependsOn: `CP-4-WIRING`, `H-03`, `H-14`
- resourceLocks: `LOCK-CONTROL-API`, `LOCK-SRC-CONTROL-UI`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/domain-event-envelope.json`; chỉ đọc `docs/09-contracts/02-domain-events.md` (tên event); bám plan.md mục 3.1
- acceptance:
  - requirement: Thêm 38 kind của plan.md mục 3.1 sau mười kind cũ của `BASE_STREAM_EVENT_KINDS` (tổng 48; mười kind cũ giữ nguyên vị trí và thứ tự) và cùng danh sách, cùng thứ tự, vào `STREAM_EVENT_KINDS` của `streamEventKinds.ts`; `default_registry` đăng ký từng tiền tố `source`, `ingestion`, `creative`, `voice`, `render`, `orchestration`, `storage`, `config`. `SNAPSHOT_RESOURCES` thêm `source` thành `sources`, `ingestion` thành `articles` và `events`, `orchestration` thành `batches`, `jobs`, `stage-runs`; `ALL_SNAPSHOT_RESOURCES` thành `operations, batches, jobs, sources, articles, events, media, hooks, stage-runs, sessions, logs` (ba phần tử cũ giữ thứ tự), Python và TypeScript khớp từng phần tử. Chỉ đăng ký tên kind: không phát hành event ở phân hệ, không sửa publisher hay outbox, không sửa `client.ts`.
    instrument: pytest `tests/unit/control_ui` xanh sau khi sửa cùng lượt ba test ghim theo plan.md mục 4: `test_h_stream_event_catalog.py` (giữ `EXPECTED_BASE` làm tiền tố, thêm `EXPECTED_MODULE` đúng 38 tên, đủ 48 kind không trùng, 11 tiền tố, kind dò `source.zz_probe`, `SNAPSHOT_RESOURCES` sáu khóa, `ALL_SNAPSHOT_RESOURCES` 11 phần tử, ca đọc `client.ts` chấp nhận hai dạng), `test_h_stream_client_registry.py` (48 kind, khóa bảng bằng khóa Python và là tập con tiền tố, hợp resource bằng `ALL_SNAPSHOT_RESOURCES`), `test_h_ts_contract_types.py` (khẳng định `wait_reason` chuyển thành có điều kiện, giữ ràng buộc không nhắc `operationView`, `listPage`). Thêm một ca âm: đăng ký kind `source.x` dưới tiền tố `job` bị từ chối `invalid_event_kind`. Probe so khớp danh sách hai phía ở testCommands.
    counterexample: xóa hoặc skip ca kiểm của H thay vì mở rộng; đổi `EXPECTED_BASE` thay vì giữ làm tiền tố; kind phân hệ viết ngoài tiền tố; Python và TypeScript lệch nhau; tuyên bố đã phát hành event; sửa `client.ts` hay publisher.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit/control_ui/test_h_stream_client_registry.py tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider`
  - `python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider`
  - `python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/sse/event_catalog.py').read_text(encoding='utf-8'); t = pathlib.Path('src/controlplane/ui/src/api/streamEventKinds.ts').read_text(encoding='utf-8'); a = re.findall(chr(34) + '([a-z_]+[.][a-z_]+)' + chr(34) + ',', c.split('SNAPSHOT_RESOURCES')[0]); b = re.findall(chr(39) + '([a-z_]+[.][a-z_]+)' + chr(39) + ',', t.split('ALL_SNAPSHOT_RESOURCES')[0]); assert a == b and len(a) == 48 and len(set(a)) == 48, (len(a), len(b))"`
- notes: BL-CV-02 (plan.md mục 12.1 của kế hoạch hội tụ): cổng là Control xác nhận phong bì cho `event_catalog.py` và `streamEventKinds.ts` kèm khóa của owner đường dẫn; chưa xác nhận thì slice PENDING và Worker không sửa hai tệp này. Event của C chưa đăng ký (OI-EXT-UI-01). Nên chạy trước `CP-4B-UI-SHELL` (OI-EXT-UI-05).

### CP-4-PAGINATION: Phân trang keyset thay LIMIT 100 và next_cursor None (BL-CV-12)

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/control_api_queries.py`
  - `src/controlplane/application/control_api/query_ports.py`
  - `src/controlplane/api/routes/control.py`
  - `tests/integration/control_ui/test_h_list_queries_sql.py`
  - `tests/integration/convergence/test_cp4_pagination_postgres.py`
  - `docs/delivery-evidence/cp-4-pagination/report.md`
- dependsOn: `CP-4-WIRING`, `CP-3-MIGRATIONS`, `H-02`, `H-04`
- resourceLocks: `LOCK-CONTROL-API`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE`
- bindingRefs: chỉ đọc `src/controlplane/application/projections/list_query.py` và `src/controlplane/infrastructure/db/projections/list_queries.py` (H-02, H-04); bám plan.md mục 3.2
- acceptance:
  - requirement: Theo plan.md mục 3.2. `batches` và `jobs` của `PostgresControlQueries` gọi `fetch_page` với `BATCHES_SPEC` và `JOBS_SPEC`; `operations` và `configs` tự dựng SQL keyset tham số hóa trong `control_api_queries.py`; không còn `LIMIT 100`. `ControlQueryPort` và `ControlApiQueryService` nhận `query: ListQuery` và trả `Page` cho bốn query danh sách. `control.py` dùng `parse_list_query` (mặc định 50, tối đa 100, `direction=desc` khi client không gửi), lấy `next_cursor` từ `Page`, đổi `ListQueryError` thành `ValueError` (422); không còn literal `next_cursor: None`. Sửa cùng lượt `test_h_list_queries_sql.py` theo hướng mở rộng: ca `test_specs_match_control_api_queries` ghim `LIMIT 100` chuyển thành kiểm AST rằng `batches` và `jobs` gọi `fetch_page` với đúng spec và không còn chuỗi `LIMIT 100`; thêm ca kiểm SQL của `operations`, `configs` (có `LIMIT %s`, không `OFFSET`, giá trị chỉ ở tham số); mọi ca còn lại giữ nguyên. Không sửa `list_queries.py`, `list_query.py`, `control_api_commands.py`, migration.
    instrument: test PostgreSQL 18.6 dùng một lần gọi trực tiếp `PostgresControlQueries` (không qua service giả của `create_app`): hơn 100 receipt, batch, job, config revision; trang đầu có `next_cursor` khác `None`; đi hết các trang ở `limit` 25 và 100 thì đủ mọi dòng, không lặp, không sót, trang cuối `next_cursor` là `None`; `create_app` với cursor sai trả 422; `GET /v1/operations` rỗng vẫn trả `{items: [], next_cursor: null}` (`tests/m2/test_p7a_hardening.py`). Probe đọc tệp ở testCommands.
    counterexample: còn `LIMIT 100` trong `control_api_queries.py`; `next_cursor` luôn `None`; phân trang chỉ chứng minh trên service giả; xóa hoặc làm yếu ca kiểm `LIMIT 100` thay vì mở rộng; dùng `OFFSET`; thứ tự mặc định đảo sang cũ nhất trước; sửa `tests/m2`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py -q -p no:cacheprovider`
  - `python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cacheprovider`
  - `python -m pytest tests/m2 -q -p no:cacheprovider`
  - `python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); c = pathlib.Path('src/controlplane/api/routes/control.py').read_text(encoding='utf-8'); assert 'LIMIT 100' not in q and 'fetch_page' in q, 'keyset replaces LIMIT 100'; assert chr(34) + 'next_cursor' + chr(34) + ': None' not in c and 'parse_list_query' in c, 'next_cursor from ListQuery'"`
- notes: BL-CV-12 (plan.md mục 12.1 của kế hoạch hội tụ): hai tệp nằm trong ownedPaths của `CP-4-WIRING` nên slice này chạy sau slice đó và cần index của migration `0018`; phong bì không bao phủ thì BLOCKED, không tuyên bố đã làm. `cp_config_revisions` chưa có index keyset riêng (OI-EXT-UI-03).

### CP-4-QUERIES: Query CT-API-002 còn thiếu của các phân hệ (BL-CV-05)

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/control_api_queries.py`
  - `src/controlplane/application/control_api/query_ports.py`
  - `src/controlplane/api/routes/control.py`
  - `src/controlplane/api/main.py`
  - `tests/integration/convergence/test_cp4_queries_routes.py`
  - `tests/integration/convergence/test_cp4_queries_postgres.py`
  - `docs/delivery-evidence/cp-4-queries/report.md`
- dependsOn: `CP-4-PAGINATION`, `CP-4-WIRING`, `GATE-PERSIST-A`, `GATE-PERSIST-B`, `GATE-PERSIST-C`, `GATE-PERSIST-D`, `GATE-PERSIST-E`, `GATE-PERSIST-F`, `GATE-PERSIST-G`, `GATE-PERSIST-I`, `GATE-PERSIST-J`, `H-08`
- resourceLocks: `LOCK-CONTROL-API`, `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE`
- bindingRefs: chỉ đọc `docs/09-contracts/01-control-api-and-stream.md` (CT-API-002) và `src/controlplane/ui/src/features/screens/screenRegistry.ts` (cột theo màn hình); bám plan.md mục 3.3
- acceptance:
  - requirement: Theo plan.md mục 3.3. Thêm chín query danh sách chỉ đọc (`sources`, `articles`, `events`, `media`, `hooks`, `stage-runs`, `sessions`, `logs`, `capabilities`) cho CT-API-002: Protocol và chín phương thức ở `query_ports.py`; `ListSpec` cộng `fetch_page` ở `control_api_queries.py` (chỉ SELECT, bảng và cột lấy từ migration thật `0009`..`0018`, không import adapter phân hệ khác); route `build_listing_router` mount trong `create_app` (mỗi tiền tố đúng một lần; nếu `CP-4-WIRING` đã mount thì cấp `fetch_page` cho mount đó). Cột chọn theo `screenRegistry.ts`, cộng `revision` ở `sources`, `media`, `hooks`; không bao giờ chọn `article_body`, nội dung `script` hay `secret`; `workspace_id` chỉ từ `request.state.identity`. Thiếu bảng hoặc cột thì tài nguyên đó BLOCKED kèm `blocked-manifest` `DEPENDENCY_GAP` (owner `CP-3-MIGRATIONS`), không bịa bảng, không thêm migration. Không phát event, không sửa `control_api_commands.py`, không thêm route ghi hay route chi tiết.
    instrument: test create_app với service giả: các route mới trả 200 `{items, next_cursor}`, bộ lọc ngoài whitelist trả 422, thiếu phiên bị từ chối như route hiện có, phản hồi không chứa cột cấm, mỗi tiền tố đúng một route (đếm `app.routes`); test PostgreSQL 18.6 dùng một lần: hơn 100 dòng mỗi tài nguyên có bảng, đi hết trang đủ dòng không lặp không sót, hai workspace không thấy dữ liệu của nhau, `information_schema` có mọi bảng và cột được SELECT.
    counterexample: route trả secret hay `article_body`; `workspace_id` lấy từ query string; query chỉ chứng minh trên service giả; tài nguyên thiếu bảng vẫn ghi là sẵn sàng; hai mount cùng một tiền tố; route ghi hoặc tuyên bố đã làm lệnh CT-API-003..006.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/integration/convergence/test_cp4_queries_postgres.py -q -p no:cacheprovider`
  - `python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider`
  - `python -m pytest tests/m2 -q -p no:cacheprovider`
  - `python -c "import pathlib; p = pathlib.Path('src/controlplane/application/control_api/query_ports.py').read_text(encoding='utf-8'); q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); n = ['sources', 'articles', 'events', 'media', 'hooks', 'stage_runs']; assert all(('def ' + k + '(') in p for k in n), 'port methods'; assert 'LIMIT 100' not in q and 'article_body' not in q, 'no LIMIT 100 and no article_body'"`
- notes: BL-CV-05 (plan.md mục 12.1 của kế hoạch hội tụ): cổng là chín `GATE-PERSIST-*` (Auditor PASS), route chỉ gọi service qua port. `sessions`, `logs`, `capabilities` có thể BLOCKED nếu migration không có bảng đủ cột (OI-EXT-UI-04); khi đó ghi BLOCKED vào report, không mount route. Gắn service thật của A vào `app.state` là `ADAPT-PROD`, không thuộc slice này.

### CP-4B-UI-SCREENS: Màn hình module trên shell và dựng lại ui/dist (BL-CV-07)

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/ui/src/App.tsx`
  - `src/controlplane/ui/src/index.css`
  - `src/controlplane/ui/src/api/client.ts`
  - `src/controlplane/ui/src/types/api.ts`
  - `src/controlplane/ui/src/screens/**`
  - `src/controlplane/ui/src/features/screens/screenRegistry.ts`
  - `src/controlplane/ui/dist/**` (allowLarge: true, chỉ cho đường dẫn này)
  - `tests/unit/control_ui/test_h_screen_registry.py`
  - `tests/unit/control_ui/test_h_ts_contract_types.py`
  - `docs/delivery-evidence/cp-4b-ui-screens/report.md`
- dependsOn: `CP-4B-UI-SHELL`, `CP-4-QUERIES`, `CP-4-PAGINATION`, `CP-4-EVENT-KINDS`, `USER-CKPT-D9-D10`, `H-15`
- resourceLocks: `LOCK-UI-SHELL`, `LOCK-SRC-CONTROL-UI`, `LOCK-M2-REGRESSION`, `LOCK-CONVERGENCE`
- bindingRefs: `docs/parallel-delivery/bindings/domain-event-envelope.json`; chỉ đọc `src/controlplane/api/routes/modules/metadata_update.py` (PATCH, `If-Match`, `Idempotency-Key`); bám plan.md mục 3.4
- acceptance:
  - requirement: Theo plan.md mục 3.4. Thêm `screens/ModuleListScreen.tsx` (bảng theo `ScreenSpec`, phân trang bằng `next_cursor`) và `screens/EditableMetadataScreen.tsx` (PATCH với `If-Match` là `revision` của dòng, `Idempotency-Key` mới mỗi lần Lưu, chỉ gửi trường nằm trong `editableFields`); `client.ts` thêm `fetchModulePage`, `patchModuleItem`; `types/api.ts` thêm kiểu trang; `App.tsx` dựng điều hướng từ `SCREEN_REGISTRY` (màn hình `pending_module` bị khóa, không fetch), giữ bốn thẻ cũ và `onOpenTestError` (BL-CV-13). `screenRegistry.ts`: chỉ chuyển sang `available` tài nguyên mà `CP-4-QUERIES` đã có route và test (mặc định tám: sources, articles, events, media, hooks, stage-runs, sessions, logs; tài nguyên BLOCKED ở report của slice đó giữ `pending_module`); thêm `revision` vào `columns` của `sources`, `media`, `hooks`; sáu màn hình `artifacts`, `snapshots`, `story-angles`, `scripts`, `accounts`, `cost` giữ `pending_module`. Sửa cùng lượt, theo hướng mở rộng (plan.md mục 4): `test_h_screen_registry.py` và `test_h_ts_contract_types.py` (siết `OperationItem` có đủ sáu trường tùy chọn). Dựng lại `ui/dist` bằng `npm run build`, xóa tệp băm không còn được `index.html` tham chiếu, commit cùng nguồn. Không sửa `Header.tsx`, `/test-driver`, năm spec M2.
    instrument: `npm run build` exit 0; pytest `tests/unit/control_ui` (gồm guard H-16: fetch chỉ ở `api/client.ts`, không sink XSS, không secret, không endpoint cấm); probe `dist` (mọi tệp `assets/` mà `index.html` tham chiếu tồn tại, không còn tệp băm mồ côi); probe nguồn UI (`App.tsx` dùng `SCREEN_REGISTRY` và còn `onOpenTestError=`, `client.ts` có PATCH, `If-Match`, `Idempotency-Key`, `/test-driver/issue-capability`); probe registry (sáu màn hình ngoài BL-CV-05 vẫn `pending_module`). Control chạy `npm run test:e2e` và ghi bằng chứng; Worker không chạy lệnh này.
    counterexample: đưa màn hình ngoài BL-CV-05 sang available; available khi route chưa có test; form sửa nhận `article_body`, `script`, `secret`; PATCH thiếu `If-Match` hoặc `Idempotency-Key`; sửa `Header.tsx`, `/test-driver` hay spec M2; `dist` không khớp nguồn hoặc còn tệp băm cũ; làm yếu test ghim của H.
- testCommands:
  - `git diff --check`
  - `npm run build` (thư mục làm việc `src/controlplane/ui`)
  - `python -m pytest tests/unit/control_ui -q -p no:cacheprovider`
  - `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.findall('assets/([A-Za-z0-9_.-]+)', h); assert r and all((d / 'assets' / x).is_file() for x in r), r; k = [f.name for f in (d / 'assets').iterdir() if f.is_file() and f.name not in r and not (f.name.endswith('.map') and f.name[:-4] in r)]; assert not k, ('orphan hashed files', k)"`
  - `python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / 'App.tsx').read_text(encoding='utf-8'); c = (u / 'api' / 'client.ts').read_text(encoding='utf-8'); assert 'SCREEN_REGISTRY' in a and 'onOpenTestError=' in a, 'App.tsx registry and test button'; assert all(k in c for k in ['PATCH', 'If-Match', 'Idempotency-Key', '/test-driver/issue-capability']), 'client.ts'"`
  - `python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s = dict(re.findall('id: ' + chr(39) + '([a-z-]+)' + chr(39) + '.*?backendStatus: ' + chr(39) + '([a-z_]+)' + chr(39), r, re.S)); assert len(s) == 18, s; assert all(s[i] == 'pending_module' for i in ['artifacts', 'snapshots', 'story-angles', 'scripts', 'accounts', 'cost']), s"`
- notes: BL-CV-07 (plan.md mục 12.1 của kế hoạch hội tụ): màn hình chỉ chuyển `backendStatus` khi route của `CP-4-QUERIES` tồn tại; tệp UI trong ownedPaths mà phong bì không bao phủ thì tiêu chí tương ứng BLOCKED, ghi vào report. BL-CV-13 BLOCKED: không gỡ nút kiểm thử và `/test-driver`. Chuỗi nguồn RSS sửa được (plan.md mục 6): `CP-4-WIRING` mount router liệt kê và metadata, `ADAPT-PROD` gắn service thật của A vào `app.state`, `CP-4-QUERIES` lo GET, slice này lo màn hình và PATCH.
