# Kế hoạch triển khai Phân hệ J — Cấu hình, tài khoản dịch vụ và bí mật

> Task: `IMPL-PLAN-J` (planning_package), trigger INITIAL. Base: `5646473e81669af7143ea98e81869927ec761f5f`.
> Nguồn quyền: D3 — user duyệt Phần B ngày 18/10/2026; M3–M7 theo ủy quyền AI_SETUP. Kích hoạt sản xuất vẫn `PRODUCTION_ACTIVATION_BLOCKED`.
> Đây là kế hoạch; mã nguồn do các slice trong `docs/implementation/j/slices.md` thực hiện.

## 1. Nguồn chuẩn

- `docs/modules/capability-j-providers.md` (module spec, có lỗi, xem mục 1.1)
- `docs/09-contracts/11-configuration-security-contracts.md` (CT-CFG-001/002, CT-SEC-001..004, CT-ACC-001/002, CT-AI-ROUTE-001/002, CT-CAP-001..003, CT-COST-001, mục 11 acceptance)
- `docs/09-contracts/12-state-machines.md` (CT-STATE-013, mục 15)
- `docs/11-roadmap.md` §8 (M2, năng lực J), §11 (M5), §13 (M7, nguồn chính của phân hệ J), §14, §19, danh sách ROADMAP-OPEN
- `docs/10-test-strategy.md` §14.2 (catalog INV-*)
- `docs/adr/0008-ai-routing-and-quota.md`, `docs/adr/0009-trust-boundaries-and-secrets.md`
- `docs/03-quality-requirements.md` (QR-SEC-001..009, QR-COST-001, QUALITY-OPEN-003/004/009/014)
- `docs/parallel-delivery/ownership-and-locks.yaml` (phân hệ J dòng 60–63; `PATH-SRC-CONFIG-SECURITY` dòng 197–205; `LOCK-SRC-CONFIG-SECURITY` dòng 445–450)
- `docs/parallel-delivery/bindings/README.md` và các binding: `j-provider-route.json` (BINDING-J-PROVIDER-ROUTE 1.0.0), `b-d-production-snapshot.json`, `g-activity-execution.json`, `domain-event-envelope.json`
- `tests/fixtures/contracts/j-provider-route/payloads.json`
- `docs/parallel-delivery/errata/m4-ci.md`, `m5-d.md`, `m7-integration.md`
- Kế hoạch lân cận để đồng bộ: `docs/implementation/d/plan.md`, `e/plan.md`, `i/plan.md`
- Mã J đã có (chỉ đọc, xem mục 3): `src/controlplane/domain|application|infrastructure/db/config_security`, `src/controlplane/config/*.py`, `src/controlplane/security/*.py`, `src/controlplane/infrastructure/security/*.py`, `src/controlplane/infrastructure/db/migrations/0004_config_and_secrets.sql`, `src/controlplane/pyproject.toml`, `pyproject.toml`

### 1.1. Đính chính tài liệu cũ (errata)

Khi mâu thuẫn, contract, catalog test, ADR và errata CP1 thắng `docs/modules/capability-j-providers.md`. Kế hoạch không chép lại các điểm sai dưới đây.

| Mã | Vị trí | Nội dung sai | Nguồn chuẩn và xử lý |
|---|---|---|---|
| ERR-J-01 | capability-j-providers.md dòng 56–58 | Gán INV-013 là AI Adapter Role Routing, INV-015 là Secret Lifetime, INV-021 là Configuration Provenance | `docs/10-test-strategy.md` §14.2 (dòng 526–545): INV-013 là StoryAngle, INV-015 là tombstone nguồn, INV-012 là canary secret, INV-004 là đổi config sau snapshot, INV-020 là ref/chỉ thị giả từ nội dung; INV-021 không tồn tại. Kế hoạch dùng INV-012 (`TST-SEC-INV-012`) và INV-004 (`TST-INT-INV-004`); routing và fallback bám CT-AI-ROUTE-001/002 và mục 11 của contract. Docstring cũ trong `src/controlplane/config/*.py` và `src/controlplane/security/*.py` còn nhãn sai, không sửa trong slice (YC-HT-J-10) |
| ERR-J-02 | dòng 64–68 | Allowed paths chỉ có config, security, tests/unit/security | D1 mở rộng thêm domain, application, infrastructure `config_security`, `infrastructure/security`, `tests/unit/config`, `tests/integration/config` |
| ERR-J-03 | dòng 12 và 37 | Yêu cầu Subprocess Broker Vault | Mã hiện có `src/controlplane/security/broker.py` là `CredentialBroker` trong tiến trình, dùng DPAPI. ADR-0009: desktop dùng Windows Credential Manager cho secret nhỏ và DPAPI cho bundle; cloud giữ bundle mã hóa có version. Xử lý D8-J-02 |
| ERR-J-04 | dòng 50 | DoD 5: tự động chặn yêu cầu vượt ngân sách | ADR-0008 dòng 37: giữ cảnh báo dự báo 80%, không tự hard-stop vì ngân sách khi user chưa cấu hình. Xử lý D8-J-05, PUC-J-02 |
| ERR-J-05 | dòng 81–84 | Lệnh kiểm `python -m unittest tests/unit/security/test_provider_routing.py -k ...` | Slice dùng `python -m pytest <tệp> -q -p no:cacheprovider` (lệnh khoá của lane); kế hoạch không dùng lệnh unittest này |
| ERR-J-06 | dòng 14–17 | PromptRevision là aggregate riêng; ExternalAccount giữ khóa trong OS Vault | Contract 11 mục 2 xếp `prompt` là một scope của CT-CFG-001; khóa chỉ đi qua secret handle. Xử lý D8-J-01 |
| ERR-J-07 | bindings/README.md dòng 60–69 | Seam J → mọi phân hệ (CT-CFG-002) chưa có binding; CT-CAP-002/003, CT-ACC-001, CT-SEC-001/002 cũng chưa có | Fail-closed: slice chỉ dùng trong J; mở binding qua YC-HT-J-03 |
| ERR-J-08 | `tests/fixtures/contracts/j-provider-route/payloads.json` | Fixture chỉ có `ai_role: script_generation`; E cần vai trò TTS (`docs/implementation/e/plan.md` CONV-E-07) | `ai_role` là chuỗi mở (D8-J-12); bổ sung fixture qua YC-HT-J-03 |

## 2. Năng lực và aggregate

Aggregate do J sở hữu (ownership-and-locks.yaml dòng 60–63): `ConfigRevision`, `PromptRevision`, `ExternalAccount`, `ProviderCapacity`. Ngoài ra J giữ `SecretHandle` (metadata secret, đã có từ P5A) và các value object `CredentialGrant`, `AuditRecord`, `IncrementalCostRecord`.

| # | Năng lực | Contract | Aggregate hoặc thành phần | Slice |
|---|---|---|---|---|
| 1 | Publish revision config/prompt/policy/preset bất biến, lineage, rollback bằng revision mới | CT-CFG-001, CT-STATE-013 | ConfigRevision (PromptRevision là scope `prompt`, D8-J-01) | J-03, J-04 |
| 2 | Resolve bundle có provenance, job đã snapshot giữ revision cũ | CT-CFG-002 | ConfigRevision | J-05 |
| 3 | Secret write-only, xoay khóa bằng version, không đọc lại | CT-SEC-001 | SecretHandle | J-02, J-10, J-17 |
| 4 | Credential ngắn hạn, revoke thắng snapshot cũ | CT-SEC-002, CT-SEC-003 điều 7 | CredentialGrant | J-11 |
| 5 | Tài khoản ngoài: aggregate, view, test không tự bật | CT-ACC-001, CT-ACC-002 | ExternalAccount | J-04, J-06, J-15 |
| 6 | Resolve route provider/model/account theo role, độ nhạy, chi phí, quota domain | CT-AI-ROUTE-001 | ProviderRouteRequest/Decision | J-01, J-13 |
| 7 | Fallback có kiểm soát, không tự thêm dịch vụ trả phí | CT-AI-ROUTE-002 | Fallback outcome | J-14, J-18 |
| 8 | Quota snapshot và reservation theo quota domain thật | CT-CAP-001, CT-CAP-002 | ProviderCapacity | J-07, J-12 |
| 9 | Chi phí gia tăng và cảnh báo dự báo 80% | CT-COST-001 | IncrementalCostRecord | J-08 |
| 10 | Capability health cho G | CT-CAP-003 | CapabilityView (mã P1 có sẵn) | J-16 |
| 11 | Audit mọi thao tác nhạy cảm | CT-SEC-004 | AuditRecord | J-09 |
| 12 | Redaction và quét canary trước persistence/stream | CT-SEC-003 điều 6, INV-012 | — | J-02 |

Không dựng aggregate trùng: `ConfigRevision`, `ConfigRevisionStatus`, `SecretHandle` đã có ở `src/controlplane/domain/config_security/__init__.py`; `ConfigRevisionService`, `ConfigRevisionRepository`, `SecretHandleStore` ở `src/controlplane/application/config_security/__init__.py`; `PostgresConfigSecurityRepository` ở `src/controlplane/infrastructure/db/config_security/__init__.py` (bảng `cp_config_revisions`, `cp_secret_handles`, migration `0004_config_and_secrets.sql`). Slice J-03, J-05 chỉ import các lớp này; `ConfigRevision` không có `effective_at`, nên J-05 mang trường này bằng wrapper `EffectiveConfigRevision` định nghĩa trong `bundle_resolution.py` (ánh xạ cột là YC-HT-J-01). `ExternalAccount`, `ProviderCapacity`, `AuditRecord`, cost record chưa có bảng: slice dựng value object và port, bảng là migration của hội tụ (YC-HT-J-01).

## 3. Vị trí mã theo D1

J mở rộng các gói đã có trong `src/controlplane`; không dựng `src/config`, `src/security`, `src/secrets`, `src/providers`, `src/controlplane/providers` hay cây trùng aggregate nào. Một import root `src/`, dạng `controlplane.…`, không dùng tiền tố `src.`.

| Đường dẫn | Vai trò | Slice |
|---|---|---|
| `src/controlplane/domain/config_security/` | Value object, validator binding, chính sách thuần: `route_binding.py`, `status_graph.py`, `external_account.py`, `capacity_snapshot.py`, `incremental_cost.py`, `audit_record.py` | J-01, J-04, J-06, J-07, J-08, J-09 |
| `src/controlplane/application/config_security/` | Use case và port: `publish_plan.py`, `bundle_resolution.py`, `secret_update.py`, `credential_issuance.py`, `capacity_reservation.py`, `route_resolver.py`, `fallback_policy.py`, `account_test.py`, `capability_health.py`, `routed_invocation.py` | J-03, J-05, J-10 đến J-16, J-18 |
| `src/controlplane/infrastructure/security/` | Gói đã có (redaction, secret_scanner, loopback_certificate); thêm `secret_redaction.py`, `dpapi_secret_store.py` | J-02, J-17 |
| `src/controlplane/infrastructure/db/config_security/` | Adapter PostgreSQL P5A; chỉ mở rộng sau migration của hội tụ (YC-HT-J-01), chưa có slice | — |
| `src/controlplane/config/`, `src/controlplane/security/` | Mã P1 đã có (router, adapter, accounting, capability_view, broker, dpapi, sanitizer); chỉ import, không slice nào sửa | — |
| `tests/unit/config/`, `tests/unit/security/` | Test đơn vị `test_j_<chủ đề>.py`; `tests/unit/security/__init__.py` đã có, giữ nguyên | tất cả |
| `tests/integration/config/` | Test tích hợp cục bộ, không mạng (DPAPI, routed invocation) | J-17, J-18 |

Lý do không sửa mã cũ (D8-J-14): `tests/m2/test_p5a_config_and_secrets.py` bảo vệ ba `__init__.py` của config_security; `tests/unit/security/test_*.py` bảo vệ mã P1; `src/controlplane/infrastructure/security/redaction.py` nằm trong danh sách probe `probe_p7a_implementation.py`. Slice thêm module mới bên cạnh và import chỉ đọc.

Ba bản redaction trùng nhau đang tồn tại (`infrastructure/security/redaction.py`, `config/accounting.py`, `config/capability_view.py`); J-02 thêm một module redaction sâu dùng lại `redact_text`, việc hợp nhất ba bản là backlog J-BL-01, không làm trong vòng này.

Import root: pytest `pythonpath = ["src"]` trong `pyproject.toml`. Không thêm `__init__.py` vào thư mục test mới; tiền tố `test_j_` giữ tên tệp test duy nhất trong repo.

## 4. Contract dùng và cung cấp

### 4.1. J cung cấp

| Contract | Binding | Ghi chú |
|---|---|---|
| CT-AI-ROUTE-001 `ProviderRouteRequest`/`ProviderRouteDecision` | `docs/parallel-delivery/bindings/j-provider-route.json` (BINDING-J-PROVIDER-ROUTE 1.0.0; consumer D, E); fixture `tests/fixtures/contracts/j-provider-route/payloads.json` | Slice J-01 (validator), J-13 (resolver). Decision cấm `secret_value`, `api_key`, `access_token`, `refresh_token` |
| CT-CFG-002 `ResolveConfigurationBundle` | Chưa có binding (bindings/README.md dòng 67) | J-05 sinh `configuration_revision_refs` và `configuration_bundle_fingerprint` mà `docs/parallel-delivery/bindings/b-d-production-snapshot.json` yêu cầu; cung cấp cho phân hệ khác phải mở binding trước (YC-HT-J-03) |
| CT-CFG-001, CT-SEC-001..004, CT-ACC-001/002, CT-AI-ROUTE-002, CT-CAP-001..003, CT-COST-001 | Chưa có binding seam | Dùng nội bộ J hoặc qua workflow G/control API của H sau hội tụ; fail-closed theo bindings/README.md |
| Event config/account/secret | `docs/parallel-delivery/bindings/domain-event-envelope.json` | Phát qua outbox là wiring của hội tụ (YC-HT-J-07) |

### 4.2. J dùng

| Binding hoặc mã | Trường J dùng | Slice |
|---|---|---|
| `domain-event-envelope.json` | Hình dạng event, `sensitivity`, payload không chứa secret | J-02, J-09, J-10 |
| `g-activity-execution.json` (CT-WF-003, CT-WF-006) | `execution_grant`, `capability_requirements`; thực thể cấm `secret_value` | J-11, J-15, J-16; wiring YC-HT-J-06 |
| `b-d-production-snapshot.json` | `configuration_revision_refs`, `configuration_bundle_fingerprint` | J-03, J-05, J-18 |
| `controlplane.application.idempotency.request_hash` | Fingerprint nội dung ConfigRevision giống P5A | J-03 |
| `controlplane.config.capability_view.build_capability_view` | Dựng CapabilityView từ observation | J-16 |
| `controlplane.config.models` (`RateLimitError`) và `controlplane.config.adapter` (`ProviderTimeoutError`, `ProviderAuthenticationError`) | Phân loại lỗi provider (chỉ import lớp ngoại lệ) | J-14 |
| `controlplane.security.broker.CredentialBroker`, `controlplane.security.dpapi` | Giải mã trong phạm vi handle | J-17 |

### 4.3. Tên và kiểu lệch cần giữ

- `config_revision_number` (version nghiệp vụ, tăng đơn điệu theo scope) khác `revision` (concurrency revision) theo CT-CFG-001; J-03 không trộn hai namespace.
- `ConfigRevisionStatus` và trạng thái account của CT-STATE-013 viết hoa; view CT-ACC-001 viết thường (`enabled`, `disabled`, `degraded`, `revoked`, `invalid`); J-04, J-06 ánh xạ một chiều.
- `SecretHandle.redacted_fingerprint_or_version` của P5A nhận chuỗi `v<N>` (D8-J-03).
- Binding khai `ai_role`, `data_sensitivity`, `estimated_cost_class`, `credential_acquisition_method` là `string`; thứ tự giá trị là GIẢ ĐỊNH theo bindings/README.md D8 mục 2 (xem D8-J-04, D8-J-12). Khi mâu thuẫn, binding thắng; slice không sửa binding.

## 5. Exit gate roadmap và cách kiểm

Phân hệ J là năng lực xuyên suốt (roadmap §14: M2 core, M3 source policy, M4 storage accounts, M5 AI routing, M6 preset/tool config, M7 cost/health/rotation). Nguồn chính là §13 (M7), kèm các gate M2, M4, M5 mà J phục vụ.

### 5.1. Exit gate J phục vụ

| Mã | Exit gate (nguồn) | Slice | Cách kiểm |
|---|---|---|---|
| EG-M2-J-1 | Secret không xuất hiện trong DB view rộng, UI, event, log hoặc workflow history (§8) | J-02, J-09, J-10, J-17 | `tests/unit/security/test_j_secret_redaction.py`, `test_j_audit_record.py`, `test_j_secret_update.py`, `tests/integration/config/test_j_dpapi_secret_store.py` (phần J của `TST-SEC-INV-012`) |
| EG-M5-J-1 | Mọi output D truy được model, prompt, config revision (§11) | J-05, J-13, J-18 | `tests/unit/config/test_j_bundle_resolution.py`, `test_j_route_resolver.py`, `tests/integration/config/test_j_routed_invocation.py` |
| EG-M5-J-2 | Provider lỗi không làm mất job/history và không tự thêm dịch vụ trả phí (§11) | J-13, J-14, J-18 | `tests/unit/config/test_j_fallback_policy.py`, `tests/integration/config/test_j_routed_invocation.py` |
| EG-M5-J-3 | Config đổi sau snapshot không làm job cũ thay đổi (§11, INV-004) | J-03, J-05 | `tests/unit/config/test_j_publish_plan.py`, `test_j_bundle_resolution.py` (phần J của `TST-INT-INV-004`) |
| EG-M4-J-1 | Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật (§10): J cấp credential và refresh phía cloud | Không có slice; CP7-J-01 | Chỉ đóng bằng evidence tài khoản thật; cấm fake/mock (§13 Điều cấm) |
| EG-M7-J-1 | Năng lực 8: routing, quota, health, cảnh báo dự báo 80% (§13) | J-07, J-08, J-12, J-13, J-16, J-18 | `tests/unit/config/test_j_capacity_snapshot.py`, `test_j_incremental_cost.py`, `test_j_capacity_reservation.py`, `test_j_route_resolver.py`, `test_j_capability_health.py` |
| EG-M7-J-2 | R6: incremental cost dưới 50 USD/tháng có cảnh báo 80% (§13) | J-08 (cơ chế) | Cơ chế do `test_j_incremental_cost.py`; con số 50 USD chỉ đóng bằng workload tháng thật: CP7-J-04 (G03) |
| EG-M7-J-3 | R6: credential rotation, revocation, rollback được kiểm thử (§13) | J-03, J-10, J-11 | `test_j_publish_plan.py` (rollback bằng revision mới), `test_j_secret_update.py` (xoay bằng version), `test_j_credential_issuance.py` (revoke thắng snapshot cũ); drill thật: CP7-J-02 |
| EG-M7-J-4 | Hardening 4: security test secret, OAuth, workspace (§13) | J-02, J-05, J-09, J-17 | Test canary và workspace isolation của các slice; OAuth thật: CP7-J-01 |
| EG-M7-J-5 | Không dùng mock để đóng gate Drive/OAuth/AI (§13 Điều cấm) | Không có slice | Fake của J-13, J-18 chỉ chứng minh logic; không được trích làm bằng chứng gate |

### 5.2. Test bắt buộc phần J

- INV-012 (`TST-SEC-INV-012`, canary secret qua lỗi, log, event, history): J-02, J-09, J-10, J-11, J-15, J-17, J-18.
- INV-004 (`TST-INT-INV-004`, đổi nguồn/config sau snapshot): J-03, J-05, J-18 (record giữ config revision và prompt revision).
- INV-020 phần J (`TST-SEC-INV-020`, ref sai workspace hoặc ref do model đề xuất bị resolver độc lập từ chối): J-05 (revision workspace khác bị bỏ qua), J-13 (ref ngoài catalog bị bỏ qua).
- Contract mục 11 điều 1–6: điều 1 và 6 → J-10, J-09; điều 2 (desktop không giữ Drive refresh token) → J-11, CP7-J-01; điều 3 → J-05; điều 4 (pool theo quota/project thực) → J-07, J-12, J-13; điều 5 (AI unavailable không dừng việc không cần AI, không tự mua dịch vụ) → J-14, J-18.
- Rate limit 429 và timeout giả lập, không mạng thật: J-14, J-18 (monkeypatch socket).
- Revocation cao hơn snapshot cũ (CT-SEC-003 điều 7): J-11.
- Không có test ID catalog riêng cho CT-AI-ROUTE, CT-CAP, CT-COST: slice chỉ liệt kê mã CT làm oracle trong `coveredIds`; muốn tạo test ID mới phải đăng ký vào `docs/10-test-strategy.md` trước (YC-HT-J-10, errata m7-integration mục Quy tắc dùng).

### 5.3. Gate sau M5 mà J phục vụ

- M6 (Preset/tool config): scope `preset` và `policy` của CT-CFG-001 dùng lại J-03, J-05; không cần slice mới.
- M7 `R5 Unattended Beta`: waiting/resume theo capability dùng J-16 qua workflow G (YC-HT-J-06); fault suite end-to-end thuộc hội tụ/M7.
- G03 (cost) và G04 (Drive/OAuth/Security) theo roadmap §19: cơ chế ở J-08, J-11, J-17; kết luận gate chỉ bằng evidence thật ở CP7-J-01, CP7-J-03, CP7-J-04.

## 6. Mục mở và quyết định mặc định (D8)

| Mã | Chủ đề | Mặc định đã chọn | Lý do |
|---|---|---|---|
| D8-J-01 | PromptRevision | Là `ConfigRevision` với `scope_kind='prompt'`, không bảng hay aggregate mới | Contract 11 mục 2 liệt kê `prompt` là một scope của CT-CFG-001; bảng `cp_config_revisions` đã có; tránh migration (ERR-J-06) |
| D8-J-02 | Secret broker và nơi lưu | Desktop: DPAPI theo tài khoản OS qua `controlplane.security.dpapi` và `CredentialBroker` trong tiến trình (J-17). Credential Manager, broker subprocess và bundle mã hóa phía cloud nằm ngoài slice | ERR-J-03; ADR-0009 yêu cầu kiểm chứng DPAPI khi đổi account/máy (CP7-J-06); lựa chọn cuối chờ PUC-J-07 |
| D8-J-03 | Fingerprint của secret | Chỉ chuỗi version `v<N>`; không hash, không bốn ký tự cuối | CT-SEC-001 chấp nhận version; hash hoặc ký tự cuối của secret ngắn là rò rỉ một phần (QR-SEC-001) |
| D8-J-04 | Thứ tự cost class và độ nhạy | `free < low < medium < high`; `public < internal < confidential`; giá trị lạ coi là vượt (fail-closed); thiếu `max_cost_class` trong bound thì chỉ nhận `free` | Binding khai `string`; GIẢ ĐỊNH theo bindings/README.md D8 mục 2; không tự mua dịch vụ (CT-AI-ROUTE-002) |
| D8-J-05 | Ngân sách | Cảnh báo dự báo 80%; `hard_stop` mặc định tắt và chỉ chặn khi user đã cấu hình `monthly_limit`; không hard-code 50 USD | ADR-0008 dòng 37, QR-COST-001; ERR-J-04; xác nhận ở PUC-J-02 |
| D8-J-06 | Cửa sổ tháng ngân sách và đồng hồ | Caller truyền `window_start`, `window_end`, `now` có múi giờ; mã J không đọc đồng hồ hay múi giờ hệ thống | ROADMAP-OPEN-004 và QUALITY-OPEN-014 chưa chốt múi giờ; PUC-J-01 |
| D8-J-07 | TTL của reservation và backoff | `ttl_seconds`, `base`, `cap` là tham số bắt buộc, không mặc định | QUALITY-OPEN-003 (retry/timeout theo phân hệ) còn mở; giá trị đo sau benchmark (CP7-J-05) |
| D8-J-08 | TTL credential ngắn hạn | Trần `max_ttl_seconds` là tham số bắt buộc của issuer; mỗi lần cấp phải `0 < ttl <= trần`; không mặc định | ADR-0009 yêu cầu token ngắn hạn; giá trị trần phụ thuộc provider, đo ở CP7-J-01 |

| Mã | Chủ đề | Mặc định đã chọn | Lý do |
|---|---|---|---|
| D8-J-09 | Cạnh trạng thái ExternalAccount | Chỉ các cạnh văn bản CT-STATE-013: `DISABLED`↔`ENABLED`, `ENABLED`→`DEGRADED`/`INVALID`/`REVOKED`; `DEGRADED`, `INVALID`, `REVOKED` không có cạnh thoát; `REVOKED` chỉ kích hoạt lại bằng credential version mới (J-06) | Fail-closed theo contract; thiếu cạnh phục hồi từ `DEGRADED`/`INVALID` là điểm mở PUC-J-03 |
| D8-J-10 | Thứ tự merge bundle | GIẢ ĐỊNH: `workspace < module < provider < preset < policy`; scope cụ thể hơn ghi đè; dict merge sâu, kiểu khác thay hoàn toàn; scope `prompt` không merge mà trả ref riêng | CT-CFG-002 yêu cầu merged typed values và provenance nhưng không nêu thứ tự |
| D8-J-11 | Rollback config | Publish revision mới có payload bằng payload revision đích kèm mã `ROLLBACK_OF:<số>`; không sửa tại chỗ | CT-STATE-013 cấm `SUPERSEDED → PUBLISHED`; CT-CFG-001 cấm sửa revision tại chỗ; module spec mục 8 |
| D8-J-12 | Danh mục `ai_role` và provider/model theo vai trò | `ai_role` là chuỗi mở, danh mục là cấu hình; không khóa provider/model cụ thể | Roadmap §11: provider/model/prompt theo vai trò sau benchmark, không khóa bằng suy đoán; PUC-J-04; ERR-J-08 |
| D8-J-13 | Quota không chắc chắn | `confidence` ∈ `observed`, `estimated`, `unknown`; quan sát hết hạn hoặc không phân tích được coi là `unknown`; route vẫn có thể chọn nhưng thêm rationale `QUOTA_UNCERTAIN` và reservation đánh dấu `UNCERTAIN` | CT-CAP-001/002: số liệu không chắc không được dùng như guarantee; reservation chỉ là hint |
| D8-J-14 | Cách thêm mã | Module mới cạnh mã P5A/P1; không sửa `__init__.py` P5A, `config/*.py`, `security/*.py`, `redaction.py` | `tests/m2`, `tests/unit/security`, probe P7A bảo vệ các tệp này; slice chạy song song không đụng tệp nhau |
| D8-J-15 | Đặt tên test | `test_j_<chủ đề>.py`, không `__init__.py` mới | Tên tệp test duy nhất trong repo (không dùng `__init__.py`) |

Đối chiếu điểm mở của roadmap và quality:

| Điểm mở | Xử lý trong kế hoạch J |
|---|---|
| ROADMAP-OPEN-003 (tài khoản test, quota, OAuth thật) | Không slice nào dùng tài khoản thật; CP7-J-01, CP7-J-03 |
| ROADMAP-OPEN-004 / QUALITY-OPEN-014 (múi giờ) | D8-J-06; PUC-J-01 |
| ROADMAP-OPEN-010 (retention) | Retention audit và log: PUC-J-05 (QUALITY-OPEN-009); placement storage thuộc phân hệ I |
| ROADMAP-OPEN-012 (backup/restore) | Backup bundle secret và khóa phục hồi ngoài host (ADR-0009): PUC-J-07 |
| Roadmap §11: provider/model/prompt theo vai trò sau benchmark | D8-J-12; PUC-J-04 |
| QUALITY-OPEN-003, QUALITY-OPEN-004 (retry, timeout, ngưỡng chờ khi AI lỗi) | J-12, J-14 chỉ dựng cơ chế với tham số bắt buộc (D8-J-07); giá trị chờ benchmark |

### 6.1. Danh sách chờ user (pendingUserCheckpoint)

Không mục nào dưới đây được coi là đã duyệt.

- PUC-J-01 — ROADMAP-OPEN-004, QUALITY-OPEN-014: múi giờ production cho cửa sổ tháng ngân sách và lịch. Hạn: trước khi bật lịch production và trước G03.
- PUC-J-02 — Giá trị `monthly_limit` (mục tiêu QR-COST-001 dưới 50 USD/tháng) và có bật `hard_stop` hay chỉ cảnh báo 80% (ADR-0008 so với DoD 5 của module spec). Hạn: trước R6.
- PUC-J-03 — CT-STATE-013 không có cạnh thoát cho `DEGRADED`/`INVALID` của ExternalAccount; cần quyết định cạnh phục hồi (thay đổi contract thuộc Control). Hạn: trước M5 routing thật.
- PUC-J-04 — Provider/model/prompt cụ thể theo vai trò và tham số retry/timeout sau benchmark G06/G03 (roadmap §11, QUALITY-OPEN-003/004).
- PUC-J-05 — QUALITY-OPEN-009: thời hạn lưu nhật ký và audit record.
- PUC-J-06 — D5 cho CP7 (tài khoản thật) và USER-CKPT-D9-D10 trước CP-2b.
- PUC-J-07 — Nơi lưu secret: Windows Credential Manager hay DPAPI-file trên desktop; vị trí root key và khóa phục hồi phía cloud (ADR-0009). Hạn: trước CP-2b/CP7.
- PUC-J-08 — User duyệt màn hình cấu hình, tài khoản, chi phí (phân hệ H) trước R6.

## 7. Thư viện (D10)

Các slice J không cần thư viện mới: chỉ dùng stdlib (`dataclasses`, `decimal`, `datetime`, `hashlib`, `json`, `re`, `pathlib`, `os`, `typing`, `enum`) và mã controlplane đã có; DPAPI dùng `ctypes` qua `controlplane.security.dpapi`.

Đề xuất cho các bước sau (không slice nào import, chờ USER-CKPT-D9-D10):

- `cryptography==46.0.5`: mã hóa AES-256-GCM cho bundle secret có version phía cloud (ADR-0009). Đã khai báo trong `src/controlplane/pyproject.toml` và `src/controlplane/requirements.lock`. Lưu ý `uv.lock` ở gốc ghi `cryptography` 50.0.1, lệch với 46.0.5: hội tụ phải thống nhất khi dựng lại runtime (YC-HT-J-09).
- `google-api-python-client==2.200.0`, `google-auth-oauthlib==1.4.1`: đã khoá trong `pyproject.toml` gốc (proof M1-P3), dùng cho refresh token phía cloud ở CP7-J-01; không đổi M1-R1.
- `psycopg[binary]==3.3.5`: đã có, dùng cho adapter PostgreSQL sau migration.
- `tzdata==2026.4`: đã khoá trong `src/controlplane/requirements.lock`, dành cho caller truyền múi giờ (D8-J-06).
- Không đề xuất `keyring` hay thư viện Credential Manager khi chưa có PUC-J-07; nếu user chọn, phiên bản phải được xác minh tại thời điểm duyệt, không ghi suy đoán.

## 8. Việc cần tài nguyên thật (CP7)

Chỉ chạy sau khi user duyệt D5. Tài khoản thật chỉ được dùng qua secret broker của J; không mở, chép hay in bí mật.

- CP7-J-01 — OAuth/Drive thật: refresh token dài hạn phía cloud, access token ngắn hạn cho desktop, refresh, revoke, desktop không lưu refresh token; đóng phần J của G04 (EG-M4-J-1).
- CP7-J-02 — Drill xoay secret và revoke credential thật; job chuyển waiting khi credential bị revoke (EG-M7-J-3).
- CP7-J-03 — Quan sát quota, entitlement và API project thật của bốn tài khoản để cấp dữ liệu cho J-07, J-12 (Gemini tính quota theo project, ADR-0008).
- CP7-J-04 — Workload tháng thật để kiểm incremental cost dưới 50 USD và cảnh báo 80% (G03, EG-M7-J-2).
- CP7-J-05 — AI trả phí thật qua route J; benchmark provider/model theo vai trò (G06; PUC-J-04).
- CP7-J-06 — Kiểm DPAPI/Credential Manager khi đổi tài khoản OS hoặc máy (ADR-0009).

## 9. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

Tài nguyên dùng chung chỉ gói hội tụ được sửa; slice J không chạm vào.

- YC-HT-J-01 — Migration: bảng `cp_external_accounts` (status, project_ref, capabilities, credential_version, quota_observation_ref, health), `cp_provider_capacity_snapshots`, `cp_capacity_reservations` (có expiry), `cp_cost_records`, `cp_audit_records` (append-only); mở rộng `cp_secret_handles` với credential version và revocation version; ràng buộc CHECK cho `scope_kind` của `cp_config_revisions`; ánh xạ cột `effective_at` (nullable, migration 0004) của `cp_config_revisions` vào `EffectiveConfigRevision(revision, effective_at)` của J-05 vì `ConfigRevision` P5A không có trường `effective_at` và `_REVISION_COLUMNS` không đọc cột này (adapter hội tụ đọc cột rồi dựng wrapper khi gọi `resolve_bundle`); adapter PostgreSQL trong `infrastructure/db/config_security` cho các port của J-03, J-05, J-09, J-10, J-12.
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

## 10. DAG slice và song song

Có 18 slice J-01..J-18 trong `docs/implementation/j/slices.md`. Gốc của mọi slice là `CP1-CONTRACT-BINDING` và `CP2A-LAYOUT` (đã tích hợp).

- Wave 1 (song song, không phụ thuộc slice J khác): J-01, J-02, J-03, J-04, J-05, J-07, J-08.
- Wave 2: J-06 (sau J-04); J-09 (sau J-02); J-12 và J-16 (sau J-07).
- Wave 3: J-10 (sau J-02, J-09); J-11 (sau J-02, J-06); J-13 (sau J-01, J-06, J-07, J-12); J-15 (sau J-02, J-06).
- Wave 4: J-14 (sau J-13); J-17 (sau J-10); J-18 (sau J-08, J-12, J-13, J-14).

Mỗi slice sở hữu tệp riêng nên dùng lock `LOCK-J-<số>`; `LOCK-SRC-CONFIG-SECURITY` để dành cho việc sửa tệp dùng chung của J (ba `__init__.py` P5A, `config/*.py`, `security/*.py`), do hội tụ thực hiện.

Rủi ro đã biết: (1) `DpapiSecretStore` (J-17) chỉ chạy trên Windows, nền tảng khác `pytest.skip` kèm lý do; (2) J-13 và J-18 chạy với fake nên không được trích làm bằng chứng đóng gate AI/Drive/OAuth (EG-M7-J-5); (3) mọi mục ghi `GIẢ ĐỊNH` ở mục 6 cần user hoặc Control xác nhận trước khi dùng làm cơ sở nghiệm thu.
