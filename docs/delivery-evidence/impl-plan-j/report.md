# Báo cáo bằng chứng IMPL-PLAN-J

- Task: IMPL-PLAN-J (planning_package), trigger INITIAL, base 5646473e81669af7143ea98e81869927ec761f5f.
- Tệp tạo mới: docs/implementation/j/plan.md, docs/implementation/j/slices.md (18 slice J-01..J-18), docs/delivery-evidence/impl-plan-j/report.md.

## Nguồn đã đọc

- docs/modules/capability-j-providers.md
- docs/09-contracts/11-configuration-security-contracts.md
- docs/09-contracts/12-state-machines.md
- docs/11-roadmap.md
- docs/10-test-strategy.md
- docs/03-quality-requirements.md
- docs/adr/0008-ai-routing-and-quota.md
- docs/adr/0009-trust-boundaries-and-secrets.md
- docs/parallel-delivery/ownership-and-locks.yaml
- docs/parallel-delivery/bindings/README.md
- docs/parallel-delivery/bindings/j-provider-route.json
- docs/parallel-delivery/bindings/b-d-production-snapshot.json
- docs/parallel-delivery/bindings/g-activity-execution.json
- docs/parallel-delivery/bindings/domain-event-envelope.json
- tests/fixtures/contracts/j-provider-route/payloads.json
- docs/parallel-delivery/errata/m4-ci.md
- docs/parallel-delivery/errata/m5-d.md
- docs/parallel-delivery/errata/m7-integration.md
- docs/implementation/d/plan.md
- docs/implementation/e/plan.md
- docs/implementation/i/plan.md
- docs/implementation/i/slices.md
- docs/delivery-evidence/impl-plan-i/report.md
- docs/parallel-delivery/task-dag.yaml
- src/controlplane/domain/config_security/__init__.py
- src/controlplane/application/config_security/__init__.py
- src/controlplane/infrastructure/db/config_security/__init__.py
- src/controlplane/config/models.py
- src/controlplane/config/adapter.py
- src/controlplane/config/router.py
- src/controlplane/config/accounting.py
- src/controlplane/config/capability_view.py
- src/controlplane/security/interfaces.py
- src/controlplane/security/broker.py
- src/controlplane/security/dpapi.py
- src/controlplane/security/sanitizer.py
- src/controlplane/infrastructure/security/redaction.py
- src/controlplane/infrastructure/security/secret_scanner.py
- src/controlplane/domain/interfaces/vault.py
- src/controlplane/infrastructure/db/migrations/0004_config_and_secrets.sql
- src/controlplane/pyproject.toml
- src/controlplane/requirements.lock
- pyproject.toml
- uv.lock
- tests/unit/security/test_import_root.py

## Quyết định D8

- D8-J-01: PromptRevision — Là `ConfigRevision` với `scope_kind='prompt'`, không bảng hay aggregate mới
- D8-J-02: Secret broker và nơi lưu — Desktop: DPAPI theo tài khoản OS qua `controlplane.security.dpapi` và `CredentialBroker` trong tiến trình (J-17). Credential Manager, broker subprocess và bundle mã hóa phía cloud nằm ngoài slice
- D8-J-03: Fingerprint của secret — Chỉ chuỗi version `v<N>`; không hash, không bốn ký tự cuối
- D8-J-04: Thứ tự cost class và độ nhạy — `free < low < medium < high`; `public < internal < confidential`; giá trị lạ coi là vượt (fail-closed); thiếu `max_cost_class` trong bound thì chỉ nhận `free`
- D8-J-05: Ngân sách — Cảnh báo dự báo 80%; `hard_stop` mặc định tắt và chỉ chặn khi user đã cấu hình `monthly_limit`; không hard-code 50 USD
- D8-J-06: Cửa sổ tháng ngân sách và đồng hồ — Caller truyền `window_start`, `window_end`, `now` có múi giờ; mã J không đọc đồng hồ hay múi giờ hệ thống
- D8-J-07: TTL của reservation và backoff — `ttl_seconds`, `base`, `cap` là tham số bắt buộc, không mặc định
- D8-J-08: TTL credential ngắn hạn — Trần `max_ttl_seconds` là tham số bắt buộc của issuer; mỗi lần cấp phải `0 < ttl <= trần`; không mặc định
- D8-J-09: Cạnh trạng thái ExternalAccount — Chỉ các cạnh văn bản CT-STATE-013: `DISABLED`↔`ENABLED`, `ENABLED`→`DEGRADED`/`INVALID`/`REVOKED`; `DEGRADED`, `INVALID`, `REVOKED` không có cạnh thoát; `REVOKED` chỉ kích hoạt lại bằng credential version mới (J-06)
- D8-J-10: Thứ tự merge bundle — GIẢ ĐỊNH: `workspace < module < provider < preset < policy`; scope cụ thể hơn ghi đè; dict merge sâu, kiểu khác thay hoàn toàn; scope `prompt` không merge mà trả ref riêng
- D8-J-11: Rollback config — Publish revision mới có payload bằng payload revision đích kèm mã `ROLLBACK_OF:<số>`; không sửa tại chỗ
- D8-J-12: Danh mục `ai_role` và provider/model theo vai trò — `ai_role` là chuỗi mở, danh mục là cấu hình; không khóa provider/model cụ thể
- D8-J-13: Quota không chắc chắn — `confidence` ∈ `observed`, `estimated`, `unknown`; quan sát hết hạn hoặc không phân tích được coi là `unknown`; route vẫn có thể chọn nhưng thêm rationale `QUOTA_UNCERTAIN` và reservation đánh dấu `UNCERTAIN`
- D8-J-14: Cách thêm mã — Module mới cạnh mã P5A/P1; không sửa `__init__.py` P5A, `config/*.py`, `security/*.py`, `redaction.py`
- D8-J-15: Đặt tên test — `test_j_<chủ đề>.py`, không `__init__.py` mới

## Quyết định D10

Không thêm thư viện cho slice; đề xuất cryptography==46.0.5 (đã khai báo ở src/controlplane, uv.lock gốc ghi 50.0.1 nên cần thống nhất, YC-HT-J-09), google-api-python-client==2.200.0, google-auth-oauthlib==1.4.1, psycopg[binary]==3.3.5, tzdata==2026.4 cho các bước sau; không đề xuất keyring khi chưa có PUC-J-07.

## Danh sách chờ user (chưa duyệt)

- PUC-J-01 — ROADMAP-OPEN-004, QUALITY-OPEN-014: múi giờ production cho cửa sổ tháng ngân sách và lịch. Hạn: trước khi bật lịch production và trước G03.
- PUC-J-02 — Giá trị `monthly_limit` (mục tiêu QR-COST-001 dưới 50 USD/tháng) và có bật `hard_stop` hay chỉ cảnh báo 80% (ADR-0008 so với DoD 5 của module spec). Hạn: trước R6.
- PUC-J-03 — CT-STATE-013 không có cạnh thoát cho `DEGRADED`/`INVALID` của ExternalAccount; cần quyết định cạnh phục hồi (thay đổi contract thuộc Control). Hạn: trước M5 routing thật.
- PUC-J-04 — Provider/model/prompt cụ thể theo vai trò và tham số retry/timeout sau benchmark G06/G03 (roadmap §11, QUALITY-OPEN-003/004).
- PUC-J-05 — QUALITY-OPEN-009: thời hạn lưu nhật ký và audit record.
- PUC-J-06 — D5 cho CP7 (tài khoản thật) và USER-CKPT-D9-D10 trước CP-2b.
- PUC-J-07 — Nơi lưu secret: Windows Credential Manager hay DPAPI-file trên desktop; vị trí root key và khóa phục hồi phía cloud (ADR-0009). Hạn: trước CP-2b/CP7.
- PUC-J-08 — User duyệt màn hình cấu hình, tài khoản, chi phí (phân hệ H) trước R6.

## Yêu cầu gửi IMPL-PLAN-CONVERGENCE

- YC-HT-J-01 — Migration: bảng `cp_external_accounts` (status, project_ref, capabilities, credential_version, quota_observation_ref, health), `cp_provider_capacity_snapshots`, `cp_capacity_reservations` (có expiry), `cp_cost_records`, `cp_audit_records` (append-only); mở rộng `cp_secret_handles` với credential version và revocation version; ràng buộc CHECK cho `scope_kind` của `cp_config_revisions`; adapter PostgreSQL trong `infrastructure/db/config_security` cho các port của J-03, J-05, J-09, J-10, J-12.
- YC-HT-J-02 — Composition root (`src/controlplane/api/main.py`, `src/main.py`): wiring các service J; đường dẫn secret store desktop từ cấu hình; thay `DEFAULT_APPROVED_ENDPOINTS` trong `config/adapter.py` đang chứa host mock (`mock-9router`) bằng danh sách theo cấu hình production (backlog J-BL-02).
- YC-HT-J-03 — Registry và binding: mở binding cho CT-CFG-002 (J → mọi phân hệ), CT-CAP-002/003 (G), CT-ACC-001 và CT-SEC-001 (H); thêm `ai_role` TTS vào fixture `j-provider-route` (CONV-E-07).
- YC-HT-J-04 — State machine: giữ CT-STATE-013; quyết định có đăng ký `status_graph` của J-04 vào `controlplane.domain.statemachine` hay giữ cục bộ (một nguồn sự thật); cạnh phục hồi account theo PUC-J-03.
- YC-HT-J-05 — Control API và UI shell (H): màn hình revision config/prompt, tài khoản, cập nhật secret chỉ ghi (không API đọc lại), test account, chi phí và health.
- YC-HT-J-06 — Workflow G: activity ResolveProviderRoute, ReserveProviderCapacity, IssueShortLivedCredential; waiting/resume theo CapabilityView; grant theo `g-activity-execution.json`.
- YC-HT-J-07 — Outbox/event: phát event config revision, account, secret theo `domain-event-envelope.json` với payload đã qua `ensure_safe_event_payload`.
- YC-HT-J-08 — Adapter D/E sang J: CONV-D-11 và CONV-E-11 dùng `RoutedInvocationService` (J-18); `controlplane.config.router.ProviderRouter` giữ vai trò dispatch mức thấp.
- YC-HT-J-09 — Thống nhất phiên bản `cryptography` giữa `uv.lock` gốc (50.0.1) và `src/controlplane` (46.0.5) tại USER-CKPT-D9-D10; dựng lại runtime khoá nếu cần.
- YC-HT-J-10 — Catalog `docs/10-test-strategy.md`: đăng ký test ID cho CT-AI-ROUTE, CT-CAP, CT-COST nếu cần làm oracle; sửa nhãn INV trong `docs/modules/capability-j-providers.md` (ERR-J-01) bằng slice sở hữu tài liệu đó.
- YC-HT-J-11 — Backlog sau hội tụ: J-BL-01 hợp nhất ba bản redaction; J-BL-02 tách host mock khỏi registry endpoint mặc định; J-BL-03 chuyển ba module `config/accounting.py`, `config/capability_view.py` sang dùng kiểu của J-07.
- CP7-J-01 — OAuth/Drive thật: refresh token dài hạn phía cloud, access token ngắn hạn cho desktop, refresh, revoke, desktop không lưu refresh token; đóng phần J của G04 (EG-M4-J-1).
- CP7-J-02 — Drill xoay secret và revoke credential thật; job chuyển waiting khi credential bị revoke (EG-M7-J-3).
- CP7-J-03 — Quan sát quota, entitlement và API project thật của bốn tài khoản để cấp dữ liệu cho J-07, J-12 (Gemini tính quota theo project, ADR-0008).
- CP7-J-04 — Workload tháng thật để kiểm incremental cost dưới 50 USD và cảnh báo 80% (G03, EG-M7-J-2).
- CP7-J-05 — AI trả phí thật qua route J; benchmark provider/model theo vai trò (G06; PUC-J-04).
- CP7-J-06 — Kiểm DPAPI/Credential Manager khi đổi tài khoản OS hoặc máy (ADR-0009).

## Đính chính tài liệu cũ

- ERR-J-01 (capability-j-providers.md dòng 56–58): Gán INV-013 là AI Adapter Role Routing, INV-015 là Secret Lifetime, INV-021 là Configuration Provenance — `docs/10-test-strategy.md` §14.2 (dòng 526–545): INV-013 là StoryAngle, INV-015 là tombstone nguồn, INV-012 là canary secret, INV-004 là đổi config sau snapshot, INV-020 là ref/chỉ thị giả từ nội dung; INV-021 không tồn tại. Kế hoạch dùng INV-012 (`TST-SEC-INV-012`) và INV-004 (`TST-INT-INV-004`); routing và fallback bám CT-AI-ROUTE-001/002 và mục 11 của contract. Docstring cũ trong `src/controlplane/config/*.py` và `src/controlplane/security/*.py` còn nhãn sai, không sửa trong slice (YC-HT-J-10)
- ERR-J-02 (dòng 64–68): Allowed paths chỉ có config, security, tests/unit/security — D1 mở rộng thêm domain, application, infrastructure `config_security`, `infrastructure/security`, `tests/unit/config`, `tests/integration/config`
- ERR-J-03 (dòng 12 và 37): Yêu cầu Subprocess Broker Vault — Mã hiện có `src/controlplane/security/broker.py` là `CredentialBroker` trong tiến trình, dùng DPAPI. ADR-0009: desktop dùng Windows Credential Manager cho secret nhỏ và DPAPI cho bundle; cloud giữ bundle mã hóa có version. Xử lý D8-J-02
- ERR-J-04 (dòng 50): DoD 5: tự động chặn yêu cầu vượt ngân sách — ADR-0008 dòng 37: giữ cảnh báo dự báo 80%, không tự hard-stop vì ngân sách khi user chưa cấu hình. Xử lý D8-J-05, PUC-J-02
- ERR-J-05 (dòng 81–84): Lệnh kiểm `python -m unittest tests/unit/security/test_provider_routing.py -k ...` — Slice dùng `python -m pytest <tệp> -q -p no:cacheprovider` (lệnh khoá của lane); kế hoạch không dùng lệnh unittest này
- ERR-J-06 (dòng 14–17): PromptRevision là aggregate riêng; ExternalAccount giữ khóa trong OS Vault — Contract 11 mục 2 xếp `prompt` là một scope của CT-CFG-001; khóa chỉ đi qua secret handle. Xử lý D8-J-01
- ERR-J-07 (bindings/README.md dòng 60–69): Seam J → mọi phân hệ (CT-CFG-002) chưa có binding; CT-CAP-002/003, CT-ACC-001, CT-SEC-001/002 cũng chưa có — Fail-closed: slice chỉ dùng trong J; mở binding qua YC-HT-J-03
- ERR-J-08 (`tests/fixtures/contracts/j-provider-route/payloads.json`): Fixture chỉ có `ai_role: script_generation`; E cần vai trò TTS (`docs/implementation/e/plan.md` CONV-E-07) — `ai_role` là chuỗi mở (D8-J-12); bổ sung fixture qua YC-HT-J-03

## Lệnh kiểm

| Lệnh | Exit code | Kết quả |
|---|---|---|
| git diff --check | 0 | không có output |
| python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/j'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (J-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'" | 0 | không có output |
| python -c "import re, pathlib; s = pathlib.Path('docs/implementation/j/slices.md').read_text(encoding='utf-8'); bt = chr(96); ids = re.findall(r'(?m)^### (J-[0-9]+):', s); assert len(ids) == 18, ids; ok = ('src/controlplane/domain/config_security/', 'src/controlplane/application/config_security/', 'src/controlplane/infrastructure/security/', 'tests/unit/config/', 'tests/unit/security/', 'tests/integration/config/', 'docs/delivery-evidence/j-'); blocks = re.findall(r'(?s)- ownedPaths:(.*?)- dependsOn:', s); assert len(blocks) == 18, len(blocks); paths = [p for b in blocks for p in re.findall(bt + '([^' + bt + ']+)' + bt, b)]; bad = [p for p in paths if not p.startswith(ok)]; assert not bad, bad; ev = [p for p in paths if p.startswith('docs/')]; assert len(ev) == 18 and all(re.fullmatch(r'docs/delivery-evidence/j-[0-9]+/report[.]md', p) for p in ev), ev" | 0 | không có output |

Interpreter: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
