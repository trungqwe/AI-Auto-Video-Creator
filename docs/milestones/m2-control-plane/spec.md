# M2 — Control Plane và Nền tảng Có thể Quan sát: Đặc tả Kỹ thuật (Technical Specification)

**Tệp:** `docs/milestones/m2-control-plane/spec.md`  
**Trạng thái:** `M2-P1_ACCEPTED_CLOSED; M2-P2_ACCEPTED_CLOSED; M2-P3_ACCEPTED_CLOSED; M2-P4_ACCEPTED_CLOSED; M2-P5A_PLAN_READY_FOR_REVIEW; M2-P5B_PLAN_READY_FOR_REVIEW`.
**Ngày lập:** 13-09-2026 (Hiệu chỉnh R2 trước Behavioral RED M2-P1; chờ User Review)
**Điểm dừng bắt buộc:** P1..P4 là `ACCEPTED / CLOSED`. P5A/P5B mới được lập kế hoạch và chờ independent review; RED, implementation, migration và runtime evidence đều chưa được ủy quyền. P5B còn chờ P5A/`0004` accepted vì migration tuần tự. P6+, M3 và Phân hệ A vẫn `NOT AUTHORIZED`.
**Căn cứ kiến trúc:**
- [Roadmap, Mục 8 — M2 Control Plane](../../11-roadmap.md)
- [08-architecture.md](../../08-architecture.md)
- Hợp đồng: [00-common-contract.md](../../09-contracts/00-common-contract.md), [01-control-api-and-stream.md](../../09-contracts/01-control-api-and-stream.md), [02-domain-events.md](../../09-contracts/02-domain-events.md), [09-orchestration-contracts.md](../../09-contracts/09-orchestration-contracts.md), [10-storage-contracts.md](../../09-contracts/10-storage-contracts.md), [11-configuration-security-contracts.md](../../09-contracts/11-configuration-security-contracts.md), [12-state-machines.md](../../09-contracts/12-state-machines.md).
- ADR liên quan: [ADR-0001](../../adr/0001-hybrid-modular-monolith.md), [ADR-0002](../../adr/0002-authoritative-data-and-search.md), [ADR-0004](../../adr/0004-commit-idempotency-and-fencing.md), [ADR-0005](../../adr/0005-snapshots-and-content-invariants.md), [ADR-0007](../../adr/0007-runtime-and-admin-ui.md), [ADR-0009](../../adr/0009-trust-boundaries-and-secrets.md), [ADR-0010](../../adr/0010-storage-lifecycle-and-recovery.md), [ADR-0011](../../adr/0011-observability-capacity-and-cost.md).
- Chiến lược kiểm thử: [10-test-strategy.md](../../10-test-strategy.md).

---

## 1. Mục tiêu và Ý nghĩa Nghiệp vụ

Milestone M2 xây dựng lõi điều khiển (**Control Plane**) và nền tảng có thể quan sát (**Observability**) cho toàn bộ hệ thống theo kiến trúc Modular Monolith ([ADR-0001](../../adr/0001-hybrid-modular-monolith.md)). Mục tiêu bao gồm:
1. **Thiết lập nền móng dữ liệu PostgreSQL nghiệp vụ**: Quản lý connection pool `psycopg_pool`, transaction nguyên tử (Unit of Work), cơ chế migration có kỷ luật và phân vùng dữ liệu nghiêm ngặt theo `workspace_id`.
2. **Cơ chế xác thực, danh tính và phiên (Workspace, Identity, Session)**: Thực thi xác thực actor (`user`, `scheduler`, `system`), quản lý phiên desktop (`session_id`), ràng buộc workspace và bảo mật HTTP (Host, Origin, CSRF, local HTTPS).
3. **Chuẩn hóa giao tiếp Envelope, Idempotency & Invariant**: Thực thi `MessageEnvelope`, `CommandEnvelope`, bền vững hóa `CommandReceipt`, `ProblemDetail` (RFC 9457), timestamps RFC 3339 UTC, kiểm soát đồng thời lạc quan (`expected_revision`), idempotency record tham chiếu receipt (`cp_idempotency_records`) và business uniqueness đa tầng.
4. **Hiện thực hóa Transactional Outbox & Event Engine**: Cam kết tính nguyên tử giữa bản ghi nghiệp vụ và outbox event đầy đủ schema CT-EVT-001..005; cơ chế publisher phát at-least-once và consumer deduplication bền vững commit cùng projection; xử lý out-of-order, gap và schema quarantine; tạo durable operation stream projection có monotonic cursor.
5. **Máy trạng thái phân hệ cốt lõi**: Hiện thực hóa state machine chuẩn theo CT-STATE-008..012 cho Operation, Production Batch, Video Job, Stage Run và Artifact Location; phân biệt rõ execution state (CT-STATE-011) với projection view (CT-API-007); ngăn chặn tuyệt đối các transition cấm (`FORBIDDEN_TRANSITION`).
6. **Nền tảng Phân hệ J (Configuration & Security)**: Quản lý bản sửa đổi cấu hình bất biến (`ConfigRevision`), phân tách `SecretHandle` (tuyệt đối không lưu plaintext secret trong cơ sở dữ liệu nghiệp vụ, tuân thủ ADR-0009).
7. **Nền tảng Phân hệ I (Storage Metadata Skeleton)**: Quản lý metadata `ArtifactVersion`, `ArtifactLocation` và `CleanupAuthorization` skeleton (CT-STATE-012); không claim external Drive lifecycle hay real destructive cleanup trong M2.
8. **Nền tảng Phân hệ G (Orchestration Shell & Reservations)**: Persistence thực cho `ProductionBatch`, `VideoJob`, `StageRun`; cấp phát `ExecutionGrant` có `recovery_epoch`; quản lý `BatchCapacityReservation` riêng biệt; quản lý `VariantReservation` (AUD2-B01 / CT-ORC-012 / CAS VariantRegistryRevision); ghi sổ hoàn thành `CompletionLedger` có unique invariant. M2 chỉ claim G-side completion skeleton proven using typed test ports/fixtures.
9. **Nền tảng Phân hệ H (Control API & Admin UI Shell)**:
   - Backend: FastAPI HTTP server cung cấp REST Control API `/v1`, local HTTPS TLS, bảo mật Host/Origin/CSRF/Redaction, technical detail ref storage, và luồng SSE `/v1/operations/stream` có cursor reconnect/resync.
   - Frontend: **React + TypeScript + AG Grid Community** theo đúng [ADR-0007](../../adr/0007-runtime-and-admin-ui.md), giao diện bảng tiếng Việt 1080p+, tích hợp thật vào Control API/SSE, kiểm thử Browser E2E thật bằng Playwright TypeScript (`tests/m2/e2e/*.spec.ts`) theo dòng chảy thật Browser → API → DB → Outbox → Projection → SSE → DOM (không dùng JS mock fixture).

---

## 2. Ranh giới Phạm vi (Scope Boundaries)

### 2.1. Trong Phạm vi M2 (In-Scope)
- Quản lý database schema, connection pooling (`psycopg_pool`), transaction boundary, workspace/identity/session.
- Common envelopes, durable command receipts, idempotency store, concurrency control, RFC 9457 error format (transport-neutral domain errors mapped at API layer).
- Transactional outbox pattern (CT-EVT-001..005), event deduplication atomic with projection, durable operation stream with monotonic BIGINT cursor.
- State machines cho Operation, Batch, Job, Stage Run, Artifact Location.
- Module J configuration revision immutability & secret handle boundary.
- Module I artifact metadata skeleton (version, location, cleanup eligibility).
- Evidence protocol khóa từ P0: `status.json` machine-readable source of truth, `commands.jsonl`, `red-observations.md`, `red-<package>-stdout.txt`, `hashes.sha256` (DAG exclude itself).

### 2.2. Ngoài Phạm vi M2 (Out-of-Scope - Cấm Thực Hiện)
- **Tuyệt đối cấm**: Thu thập tin tức, quản lý RSS hay nguồn crawl (thuộc Module A - M3).
- **Tuyệt đối cấm**: Chuẩn hóa nội dung bài báo, chống trùng lặp content hay liên kết sự kiện (thuộc Module B - M3).
- **Tuyệt đối cấm**: Tải media, xử lý ảnh, tạo hook clip hay quản lý Drive storage lifecycle đầy đủ (thuộc M4).
- **Tuyệt đối cấm**: Gọi LLM sinh kịch bản/story angle hay tạo kế hoạch sản xuất AI (thuộc Module D - M5).
- **Tuyệt đối cấm**: Tổng hợp giọng nói TTS, tính toán word timing hay render FFmpeg video thực tế (thuộc M6).
- Không claim full CommitVideoCompletion end-to-end hay real destructive cleanup.
- Không xây dựng SaaS đa người dùng phức tạp hoặc cổng thanh toán.

---

## 3. Kiến trúc Thành phần & Hướng Phụ thuộc (Modular Monolith)

Theo [ADR-0001](../../adr/0001-hybrid-modular-monolith.md), mã nguồn sản phẩm M2 nằm tại `src/controlplane/`. **Quy tắc phụ thuộc một chiều bắt buộc:**
- **Domain Layer** (`domain/`) là hạt nhân nghiệp vụ thuần túy, **KHÔNG ĐƯỢC PHÉP IMPORT** bất kỳ framework hay driver ngoài nào: cấm `fastapi`, `temporalio`, `psycopg`, `psycopg_pool`, `google` hay mã prototype `src/m1proof`.
- **Application Layer** (`application/`) điều phối nghiệp vụ qua các port và interface, phụ thuộc vào Domain Layer.
- **Infrastructure / Presentation Layer** (`infrastructure/`, `api/`, `ui/`) thực thi các adapter kỹ thuật (FastAPI, psycopg connection pool, React/Vite web), phụ thuộc vào Application Layer và Domain Layer.
- **Package Layout & Runtime Strategy**:
  - `src/controlplane` được cấu hình là standard Python package trong `pyproject.toml` (editable/packaged install) để import/entrypoint hoạt động từ fresh documented environment, tuyệt đối không dùng test-only `sys.path` hacks.
  - Phải bảo toàn 100% khả năng chạy và regression của Milestone M1 (`src/m1proof` và `tests/m1`).

```
src/controlplane/
├── domain/                     # Pure domain logic & models (zero external framework imports)
│   ├── common/                 # Envelopes, transport-neutral errors, timestamps, IDs
│   ├── statemachine/           # Operation, Batch, Job, Stage, Artifact state machines
│   ├── orchestration/          # VariantReservation, CapacityReservation, Grant contracts
│   ├── config_security/        # ConfigRevision, SecretHandle models
│   └── storage_meta/           # ArtifactVersion, ArtifactLocation models
├── application/                # Business use cases & coordinators
│   ├── ports/                  # Input & Output ports / interfaces
│   ├── idempotency/            # Idempotency manager & receipt persistence logic
│   ├── outbox/                 # Outbox coordinator, event dispatcher & deduplication
│   ├── projections/            # Operation stream & session projections
│   ├── config_security/        # Config revision coordinator & secret handle resolver
│   ├── storage_meta/           # Artifact metadata coordinator
│   └── orchestration/          # Shell coordinator, variant CAS, completion ledger skeleton
├── infrastructure/             # Technical adapters & external integration
│   ├── db/                     # PostgreSQL psycopg_pool connection pool, UoW, migration runner
│   │   └── migrations/         # Forward & rollback transactional SQL scripts
│   └── security/               # Local HTTPS/TLS, Host/Origin validation, CSRF Double Submit, redactor
├── api/                        # HTTP & SSE Presentation (FastAPI)
│   ├── routes/                 # REST routes (/v1/operations, /v1/batches, /v1/configs)
│   ├── sse/                    # Server-Sent Events generator (/v1/operations/stream)
│   └── middleware/             # Idempotency, security, RFC 9457 error mapper
└── ui/                         # React + TypeScript + AG Grid Community Frontend
    ├── src/                    # React components, AG Grid setup, SSE client
    ├── package.json            # Pinned frontend dependencies
    ├── vite.config.ts          # Build configuration
    └── playwright.config.ts    # Browser E2E configuration
```

---

## 4. Chiến lược Migration Cơ sở Dữ liệu (Database Migration Strategy)

### 4.1. Quyết định & So sánh
- Chọn giải pháp **Raw SQL Native Migration Runner** bằng `psycopg 3` + `psycopg_pool`.
- Lý do: Kiểm soát trực tiếp connection và transaction boundaries, không phụ thuộc ORM SQLAlchemy cồng kềnh, tương thích hoàn toàn với kiến trúc data model thuần PostgreSQL.

### 4.2. Thiết kế Chi tiết 8 Tiêu chuẩn Migration Runner
1. **Dedicated Connection & Bounded Session-Level Advisory Lock**:
   - Migration runner mở **một connection chuyên biệt (dedicated connection)** tồn tại trong suốt phiên chạy migration.
   - Chiếm khóa session-level advisory lock có chặn thời gian (bounded lock acquisition): Dùng `SELECT pg_try_advisory_lock(hashtext('controlplane_migrations'));` kết hợp deadline đồng hồ đơn điệu (`monotonic clock deadline`, mặc định timeout 5.0 giây, có thể cấu hình). Nếu hết timeout không chiếm được khóa -> Ném lỗi fail-closed `MigrationLockTimeoutError`.
   - Giải phóng khóa bằng `SELECT pg_advisory_unlock(hashtext('controlplane_migrations'));` trong khối `finally`. Khóa này **không bị giải phóng** khi mỗi migration kết thúc transaction nội bộ.
2. **Version Table (`cp_schema_migrations`)**:
   ```sql
   CREATE TABLE IF NOT EXISTS controlplane.cp_schema_migrations (
       version INT PRIMARY KEY,
       name VARCHAR(255) NOT NULL,
       checksum_sha256 CHAR(64) NOT NULL,
       applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
       execution_ms INT NOT NULL
   );
   ```
3. **Checksum Verification & Tamper Detection**:
   - Mỗi tệp migration forward được băm SHA-256 nội dung.
   - Khi khởi chạy, runner kiểm tra toàn bộ migration đã áp dụng trong DB xem checksum có khớp tệp tương ứng trên đĩa không. Nếu phát hiện tệp bị sửa đổi hoặc tệp đã apply bị xóa khỏi đĩa -> Ném lỗi fail-closed `MigrationChecksumMismatchError` / `MigrationMissingFileError` ngay lập tức.
4. **Strict Ordering, Regex Discovery & Gap Detection**:
   - Forward migration filename pattern: `^\d{4}_[a-z0-9_]+\.sql$` (ví dụ `0001_initial_controlplane.sql`).
   - Rollback migration filename pattern: `^\d{4}_[a-z0-9_]+\.rollback\.sql$`.
   - Cơ chế discovery chỉ quét các tệp khớp regex forward, tuyệt đối không để tệp rollback bị nhận diện nhầm thành forward migration.
   - Runner từ chối chạy và fail-closed nếu phát hiện trùng lặp version (`DuplicateMigrationVersionError`) hoặc có khoảng trống giữa các version (`MigrationVersionGapError`).
5. **Transactional SQL Only & Fail-Closed**:
   - Mọi tệp migration M2 bắt buộc chỉ chứa DDL/DML có thể bọc trong transaction (`BEGIN ... COMMIT`).
   - Nếu migration thất bại: transaction `ROLLBACK` sạch sẽ; không ghi nhận bản ghi `applied` trong DB; ghi nhận execution evidence `FAIL`; runner dừng lại và ứng dụng startup fail-closed. Không cần persisted dirty state vì transaction đã rollback hoàn toàn.
6. **Forward Migration**: Từng tệp migration chạy trong transaction riêng; chỉ commit sau khi lệnh SQL thành công và đã ghi bản ghi vào `cp_schema_migrations`.
7. **Rollback Migration & Disposable Test Database Protocol**:
   - Mỗi migration `XXXX_name.sql` bắt buộc có `XXXX_name.rollback.sql` tương ứng.
   - Migration `0001` rollback đưa cơ sở dữ liệu về trạng thái tiền-0001: dọn dẹp toàn bộ owned objects và xóa schema `controlplane` bằng `DROP SCHEMA IF EXISTS controlplane CASCADE;`.
   - **Disposable Test Database (Không Parameterized Schema)**:
     * Kiểm thử chu trình rollback full down/up và integration tests **bắt buộc chạy trên disposable test database** độc lập được tạo mới cho mỗi run (`m2_p1_test_<uuid>`).
     * Admin test DSN chỉ được nạp từ biến môi trường `M2_TEST_PG_DSN`; tuyệt đối không hard-code hay suy đoán credential trong source, docs, stdout hoặc evidence. Không có local/dev-safe fallback.
     * Thiếu `M2_TEST_PG_DSN`, không kết nối được server, hoặc DSN không có quyền tạo disposable database là prerequisite `FAIL` hoặc `BLOCKED_EXTERNAL` theo evidence policy; không được thay bằng credential mặc định hay một database khác.
     * Chạy migration production thật với schema cố định `controlplane` (tuyệt đối không template hoặc thay thế schema name bên trong production SQL).
     * Dọn dẹp sạch sẽ bằng `DROP DATABASE` trong teardown của test suite.
     * **Destructive Guard**: Chỉ ủy quyền rollback/drop destructive sau khi dedicated migration connection đang giữ advisory lock chứng minh `current_database()` đúng bằng expected database do chính fixture tạo, tên database khớp chính xác `^m2_p1_test_[0-9a-f]+$`, và marker môi trường kiểm thử hợp lệ (`is_test_env=True`) đã được xác nhận. Thiếu hoặc mismatch expected identity đều bị chặn. `DROP DATABASE` chỉ nhắm database fixture đã được xác minh này; cấm mọi nhánh tên tổng quát `*_test` và cấm cờ free-form `allow_destructive=True`.
8. **Interrupted Migration Recovery**: Nếu tiến trình migration bị ngắt đột ngột (killed), connection bị đóng sẽ tự động giải phóng session-level advisory lock; transaction đang dở dang tự động rollback an toàn.

---

## 5. Evidence Authority & Hash DAG Protocol

1. **Machine-Readable Authority (`status.json`)**:
   - Tệp `status.json` có schema và version cụ thể (`m2_package_status_v1`) là nguồn sự thật duy nhất về trạng thái của package.
   - Tệp `status.md` chỉ là bản chuyển đổi hiển thị cho con người (human-readable derivative); các parser và gate rule engine **tuyệt đối không dùng `status.md`** để quyết định PASS.
2. **Evidence Validator Thực thi từ P0**:
   - Evidence validator và package gate rule engine được lập trình và kiểm thử ngay tại **M2-P0**.
   - Mỗi package từ P1 đến P8 bắt buộc phải chạy validator ngay sau khi hoàn thành để xác nhận trạng thái `PASS`.
   - Work package P9 chỉ re-run validator, kiểm tra băm và tổng hợp; không đến P9 mới phát minh PASS semantics.
   - Registry semantic profile là **process-local**. Với M2-P1, không được khởi chạy generic `python -m controlplane.infrastructure.evidence.validator .../m2-p1` trong process mới rồi kỳ vọng profile đã đăng ký còn tồn tại. `synthesizer_p1.py` là P1-aware entry point cho cả synthesis và final read-only verification; mỗi mode phải đăng ký profile P1 trước khi gọi validator core.
3. **Cấu trúc Hash DAG Không Tự Tham Chiếu**:
   - Các tệp bằng chứng thô (`commands.jsonl`, `status.json`, `red-observations.md`, `red-stdout.txt`, `capability_evidence.json`).
   - Tệp `hashes.sha256`: Chứa mã băm SHA-256 của tất cả các tệp trên trong thư mục package (**loại trừ chính tệp `hashes.sha256`** để tránh self-reference).
   - Tệp `docs/milestones/m2-control-plane/evidence/manifest.json` (tổng hợp tại P9): Tổng hợp băm của tất cả tệp evidence từ các package.
4. **Không Hard-code / Không Mock**:
   - Tuyệt đối cấm hard-code PASS trong validator.
   - Không suy diễn PASS từ sự tồn tại của thư mục.
   - Không dùng mock để nâng cấp external/integration capability.

---

## 6. Đặc tả Chi tiết Các Phân hệ Cốt lõi

### 6.0. Nền tảng Định danh, Workspace & Phiên Xác thực (M2-P1)
- **Phân biệt `AuthSession` vs `AppSession`**:
  * M2-P1 chỉ thiết lập nền tảng định danh cốt lõi: `Workspace`, `Actor`, và `AuthSession` (phiên xác thực / điều khiển control plane). Bảng dữ liệu tương ứng là `controlplane.cp_auth_sessions`.
  * `AppSession` (bảng `controlplane.cp_app_sessions`) được dự lưu cho phiên mở ứng dụng desktop theo Data Model (`started_at`, `ended_at`, `output_folder`, `completed_count`, `operational_status`) và không nằm trong phạm vi hoàn thiện của M2-P1.
  * P1 chỉ persistence `AuthSession` với `session_id`, `workspace_id`, `actor_id`, `status`, `created_at`, `expires_at`. Credential, cookie, token hoặc token representation/binding cụ thể thuộc M2-P7A; P1 không thêm `token_hash` khi chưa có quyết định kỹ thuật hiện hành phê duyệt nó.
- **Repository Interface & Workspace-Scoped Context**:
  * M2-P1 cung cấp đầy đủ: `IWorkspaceRepository`, `IActorRepository`, `IAuthSessionRepository` và các Postgres adapters tương ứng.
  * Mọi aggregate/entity thuộc sở hữu của workspace bắt buộc phải liên kết workspace server-side.
  * Tuyệt đối không cung cấp hàm unscoped `get_by_id(id)` cho actor hay session business access. Mọi truy vấn và thao tác bắt buộc thông qua workspace scope: `get_by_id(workspace_id, entity_id)` hoặc workspace-bound repository instance.
  * Ports P1 chỉ phản ánh use case nền tảng: tạo, lấy, liệt kê, cập nhật trạng thái; `AuthSession` có revoke/expire. Không expose generic hard-delete method cho `Workspace` hoặc `Actor` chỉ vì tiện cho CRUD.
- **Ràng buộc Bất biến ở Tầng Cơ sở Dữ liệu (DB-Level Invariants)**:
  * Ngăn chặn cross-workspace ở tầng DB schema, không phụ thuộc duy nhất vào filter mã nguồn Python:
    1. Các trường quan hệ sở hữu workspace (`workspace_id`) bắt buộc `NOT NULL`.
    2. Bảng `controlplane.cp_actors` có unique constraint `UNIQUE (workspace_id, actor_id)`.
    3. Bảng `controlplane.cp_auth_sessions` có composite foreign key:
       ```sql
       FOREIGN KEY (workspace_id, actor_id) 
       REFERENCES controlplane.cp_actors(workspace_id, actor_id) 
       ON DELETE RESTRICT
       ```
       Đảm bảo DB tự động từ chối bất kỳ session nào cố tình gắn với actor thuộc workspace khác.
  * Không mặc định hard-delete business identity: quan hệ `Workspace → Actor` và `Actor → AuthSession` dùng `RESTRICT`/`NO ACTION`; vòng đời dùng status, revoke hoặc expire cho tới khi có contract khác phê duyệt.
- **Transaction Ownership & Unit of Work**:
  * `SqlUnitOfWork` sở hữu duy nhất **một pooled connection** và **một DB transaction** trong mỗi phiên UoW.
  * Repositories nhận và sử dụng connection từ UoW, không tự lấy connection từ pool, không tự `commit()` hoặc `rollback()`.
  * `TransactionManager` đóng vai trò factory/coordinator tạo UoW, không phải là transaction owner thứ hai.
  * Đảm bảo tính nguyên tử: Tạo Workspace + Actor + AuthSession trong 1 UoW commit đồng thời; xảy ra lỗi thì rollback toàn bộ và connection trả về pool ở trạng thái hoàn toàn sạch sẽ.
- **Ranh giới contract P1 và evidence profile**:
  * Traceability P1 chỉ bao gồm nền tảng PostgreSQL/identity của `ARCH-002`, `ADR-0002`, `QR-MNT-002`, `CT-API-001` với qualifier *workspace persistence/binding foundation*, và `CT-API-010` với qualifier *auth-session persistence foundation*. P1 không claim common envelope đầy đủ, semantics command/event duplicate, stale generation commit, hay compliance API/auth/Host/Origin/CSRF đầy đủ; các phần đó thuộc package sau, đặc biệt M2-P7A.
  * `M2P1SemanticProfile` phải implement đúng `PackageSemanticProfile`: `profile_id -> "m2-p1"`, `target_package -> "M2-P1"`, và `evaluate(package_dir, status_data)`. Không có `package_id` hoặc `target_gate_id` trong extension contract.
  * `synthesizer_p1.py` cung cấp synthesis mode và `--verify-only`; cả hai explicit gọi `register_semantic_profile(M2P1SemanticProfile())` trước validator core. Final read-only validation bắt buộc đi qua `--verify-only`, không qua validator generic trong process mới.
  * Evidence P1 bắt buộc chứa và semantic profile trực tiếp kiểm tra `m2-p1-tests.xml`, `m2-p0-regression.xml`, `m2-p0-regression-report.txt`, `m1-regression.xml`, `m1-regression-report.txt`, `runtime-capability.json`, `secret-scan.json`, cùng provenance/hash DAG. Runtime phải khóa Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1 (`psycopg_pool.ConnectionPool`), PostgreSQL 18.6, CREATEDB=true và orphan DB=0 trong cùng `run_id`; thiếu, skipped, failed/error, sai metrics, regression không đạt, runtime mismatch, secret scan dirty hoặc provenance mismatch đều fail-closed.

### 6.1. Common Envelopes & Idempotency Store (M2-P2)
- **Phạm vi contract chính xác**: `CT-CMN-001/002/003/005/006/010/011`, `CT-API-001` chỉ cho nền tảng idempotency/expected-revision/conflict semantics, và `ADR-0004`. Không triển khai `CT-CMN-004`, HTTP API, FastAPI mapper, outbox hoặc state machine ở P2.
- **Envelope và lỗi**: Envelope matrix khóa unconditional `contract_name`, `contract_version`, `message_id`, `workspace_id`, `correlation_id`, `occurred_at`, `actor`, `payload`, `command_id`, `requested_at`; conditional `causation_id` (message phát sinh), `trace_context` (process boundary), `recovery_epoch` (internal mutation/side effect), `idempotency_key` (external boundary), `expected_revision` (update existing aggregate), `policy_revision_id` (policy-dependent behavior). `ProblemDetail` transport-neutral theo RFC 9457 required/non-null `type`, `title`, `detail`, `instance`, `code`, `category`, `retryable`, `correlation_id`; optional/nullable `status`, `retry_after`, `field_errors`, `technical_detail_ref`. `status` chỉ là HTTP integer khi adapter sau này gán; technical reference opaque/an toàn, không raw secret/stack trace. HTTP mapping 409 nằm ở P7/API.
- **Schema P2 (`0002_idempotency_and_receipts`)**: `cp_command_receipts` có `receipt_id` PK, `workspace_id`, `command_id`, `disposition` (`accepted`/`rejected`), `operation_id` nullable, `resource_ref` JSONB nullable, `accepted_at`, `current_revision` nullable và unique `(workspace_id, command_id)` cùng composite unique `(workspace_id, receipt_id)`. `cp_idempotency_records` có PK `(workspace_id, command_name, idempotency_key)`, `request_hash`, `receipt_id`, `created_at`, `expires_at` nullable và composite FK `(workspace_id, receipt_id)` về receipt. Rollback chỉ gỡ objects `0002`, không sửa `0001` hay P1.
- **Idempotency semantics**: SHA-256 chạy trên RFC 8785 JCS bytes UTF-8: property name raw/unescaped sort đệ quy theo lexicographic unsigned UTF-16 code-unit arrays (locale-independent), kể cả object trong array; array element order giữ nguyên. Không dùng Unicode code-point, UTF-8 hay UTF-32 ordering. Unicode string giữ nguyên/no normalization, JCS escaping/numeric representation, reject NaN/Infinity và normalize negative zero theo JCS/ECMAScript thành `0`. Identity gồm workspace, command name, canonical payload, `expected_revision` khi có và `policy_revision_id` khi có; loại trừ message/command/correlation/causation IDs cùng timestamps. Cùng workspace/key/command/hash trả cùng persisted `receipt_id`, operation/resource/current revision và logical result; persisted receipt không mutate/create do replay, nhưng caller nhận `duplicate` transient. Hash khác trả `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`; workspace khác độc lập, restart không reset state và M2 không auto-purge.
- **Optimistic revision**: `RevisionedMutationPort` dùng PostgreSQL CAS adapter trên connection P1 UoW và disposable aggregate probe relation: create revision 1; matching update atomically tăng một; stale zero-row trả `RevisionConflictError(current_revision=...)`; rollback không tăng revision; hai writer cùng revision có đúng một commit. Không thêm aggregate nghiệp vụ và không gọi Python-only helper là production proof.

### 6.2. Transactional Outbox & Operation Stream Projection (M2-P3)
- **Outbox schema (`0003_outbox_and_projections`)**: `cp_outbox_events` phải reconstruct được đầy đủ `DomainEvent` (mở rộng `MessageEnvelope`) sau process restart: MessageEnvelope gồm `contract_name`, `contract_version`, `message_id`, `workspace_id` NOT NULL/FK P1, `correlation_id`, `causation_id` nullable/conditional, `trace_context` nullable/conditional, `occurred_at`, `actor`, `recovery_epoch` nullable/conditional và `payload JSONB`; DomainEvent bổ sung `event_id` UUID PK bất biến, `event_name`, `aggregate_type`, `aggregate_id`, `aggregate_revision`, `producer`, `schema_version`, `sensitivity`; metadata outbox gồm `recorded_at`, `published BOOLEAN NOT NULL DEFAULT false`, `published_at`. Tất cả field envelope vô điều kiện, DomainEvent addition và `recorded_at` là NOT NULL; chỉ `causation_id`, `trace_context`, `recovery_epoch` và `published_at` được nullable theo điều kiện trên. `contract_version` là version MessageEnvelope còn `schema_version` là version payload DomainEvent; hai semantics độc lập. Không suy diễn `producer == actor`, `event_id == message_id` hoặc `event_name == contract_name`. `event_id` là identity dedupe; aggregate revision chỉ dùng ordering qua index không-unique, ví dụ `(workspace_id, aggregate_type, aggregate_id, aggregate_revision, recorded_at, event_id)`, không tạo invariant một event trên mỗi revision. Index unpublished tối thiểu `(recorded_at, event_id) WHERE published=false`. Check bắt buộc `published=false AND published_at IS NULL` hoặc `published=true AND published_at IS NOT NULL`.
- **Atomicity và publisher**: mutation nghiệp vụ + outbox insert dùng đúng active P1 `SqlUnitOfWork` transaction: commit có cả hai, rollback không có cái nào. Publisher là at-least-once: claim/read unpublished → dispatch attempt → durable `published=true` ACK. Crash sau dispatch nhưng trước ACK phải redispatch; không claim exactly-once publisher.
- **Consumer/ordering/quarantine**: `cp_event_checkpoints` có PK `(consumer_id, event_id)` và representation durable cho `workspace_id`, aggregate identity, observed `aggregate_revision`, expected/current applied revision, checkpoint timestamp, cùng trạng thái/disposition phân biệt tối thiểu `APPLIED`, duplicate/deduplicated, `GAP_BLOCKED`/`SNAPSHOT_REQUIRED` và older/out-of-order non-application. Checkpoint + projection mutation cùng một transaction; adapter PostgreSQL future serialize theo `consumer_id + workspace_id + aggregate identity` (ví dụ advisory transaction lock), không dùng process-local mutex làm correctness authority. Forward gap không apply event, phải ghi durable reconcile/snapshot-required fact và không đánh dấu thành công; older/out-of-order không overwrite projection mới hơn. `cp_event_quarantine` scope theo consumer, có `consumer_id`, `event_id`, `workspace_id`, original envelope hoặc durable reference đủ reconcile, `reason_code`, `quarantined_at`, reconcile metadata/status và unique tối thiểu `(consumer_id, event_id)`; unsupported schema dùng `QUARANTINED_UNSUPPORTED_SCHEMA`, stale epoch dùng `STALE_RECOVERY_EPOCH`, không silent drop hay mutate historical event.
- **Operation stream và retention**: `cp_operation_stream` có `stream_event_id BIGINT` unique/monotonic, `workspace_id`, `operation_id` nullable khi projection không gắn operation, `resource_type`, `resource_id`, `resource_revision`, `event_kind`, `occurred_at`, `recorded_at`, safe/redacted `summary`, `correlation_id`; trừ `operation_id` conditional, các field này là NOT NULL. Khi cursor dùng cùng durable value, khóa `cursor == stream_event_id`; thứ tự không dùng wall-clock. `cp_operation_stream_retention_watermarks` giữ watermark bền vững theo workspace gồm minimum available cursor và timestamp. P3 chỉ persist cursor/watermark facts foundation cho `CT-API-008`; `resync_required` sẽ được derive từ requested cursor + watermark tại API boundary P7 và không được implement ở P3; không tạo HTTP/SSE route hoặc reconnect mapper.
- **Boundary**: application/domain không chứa SQL, tên bảng, psycopg hoặc transaction ownership. PostgreSQL adapter chỉ dùng connection active của P1 UoW, không tự acquire pool, commit, rollback hoặc mở transaction ẩn. Không sửa `MigrationRunner`.

### 6.3. Operation Semantics Mapping (M2-P4)
**Trạng thái P4:** `ACCEPTED / CLOSED`; implementation pure-domain và mapper đã được chứng kiến GREEN, closure evidence đã qua independent audit. Không có persistence, transport hay work package kế tiếp trong checkpoint này.

**Traceability bắt buộc:** `CT-STATE-008` (Stage Run), `CT-STATE-009` (Video Job), `CT-STATE-010` (Production Batch), `CT-STATE-011` (Operation), `CT-STATE-012` (Artifact Location), `CT-API-007` (`OperationView`), `CT-CMN-005` (revision) và danh mục lỗi `FORBIDDEN_TRANSITION`/`REVISION_CONFLICT` của `CT-CMN-010`. `ADR-0004` chỉ là căn cứ fencing/reconcile; P4 không triển khai CAS PostgreSQL hay owner persistence.

P4 sẽ cung cấp logic domain thuần, xác định bởi input, dưới `src/controlplane/domain/statemachine/**`; mapper application thuần tại `src/controlplane/application/projections/operation_view_mapper.py`. Các hàm không đọc clock, sinh ID, gọi mạng, thực hiện SQL, acquire UoW hay import psycopg/FastAPI/Temporal/infrastructure/UI.

| Máy trạng thái | Các transition hợp đồng duy nhất được P4 cho phép | Terminal tại chỗ |
|---|---|---|
| Stage Run — `CT-STATE-008` | `PENDING → WAITING_DEPENDENCY | WAITING_CAPABILITY | RUNNING`; `RUNNING → SUCCEEDED | FAILED_RETRYABLE | FAILED_FINAL | OUTCOME_UNKNOWN | STALE`; `OUTCOME_UNKNOWN → SUCCEEDED | FAILED_RETRYABLE | FAILED_FINAL` qua reconcile | `SUCCEEDED`, `FAILED_FINAL`, `STALE`; `OUTCOME_UNKNOWN` không retry side effect trực tiếp. Hợp đồng không định nghĩa lối ra từ `WAITING_*` hoặc `FAILED_RETRYABLE`; P4 phải reject chúng thay vì tự suy diễn retry/recovery. |
| Job — `CT-STATE-009` | `CREATED → SNAPSHOTTED → ACTIVE`; `ACTIVE ↔ WAITING`; `ACTIVE | WAITING → READY_FOR_COMPLETION`; `READY_FOR_COMPLETION → COMPLETED`; `ACTIVE | WAITING | READY_FOR_COMPLETION → FAILED_FINAL` | `COMPLETED`, `FAILED_FINAL` |
| Batch — `CT-STATE-010` | `CREATED → RUNNING`; `RUNNING ↔ WAITING_CAPABILITY`; `RUNNING | WAITING_CAPABILITY → COMPLETED_TARGET | COMPLETED_EXHAUSTED | FAILED_SYSTEM` | `COMPLETED_TARGET`, `COMPLETED_EXHAUSTED`, `FAILED_SYSTEM` |
| Operation — `CT-STATE-011` | `PREPARED → STARTED`; `STARTED → SUCCEEDED | FAILED | OUTCOME_UNKNOWN`; `OUTCOME_UNKNOWN → SUCCEEDED | FAILED` chỉ với reconciliation evidence; reconcile inconclusive giữ `OUTCOME_UNKNOWN` | `SUCCEEDED`, `FAILED`; không mở lại `STARTED`, không self-transition. Retry/re-attempt dùng attempt/revision mới ngoài reopen. |
| Artifact Location — `CT-STATE-012` | `DECLARED → MATERIALIZING → AVAILABLE_UNVERIFIED → VERIFYING → VERIFIED | CORRUPT | MISSING | OUTCOME_UNKNOWN`; `VERIFIED → MISSING` ở lần verify sau; cleanup chỉ `VERIFIED → CLEANUP_ELIGIBLE → CLEANUP_AUTHORIZED → DELETED` | `CORRUPT`, `MISSING`, `OUTCOME_UNKNOWN`, `DELETED`; cạnh `VERIFIED → MISSING` không phải cleanup shortcut. |

Mọi transition không nằm trong bảng trên, bao gồm terminal regression và cleanup shortcut, ném `ForbiddenTransitionError` với `code="FORBIDDEN_TRANSITION"`, `aggregate_type`, `current_state`, `requested_next_state` và `current_revision` khi có; không có side effect. P4 tái sử dụng `RevisionConflictError(current_revision=...)` đã được chấp thuận ở P2. Hàm transition nhận `(current_state, current_revision, expected_revision, requested_next_state, reconciliation_evidence/explicit condition khi hợp đồng yêu cầu)`; revision stale trả conflict và không đổi state/revision, transition thành công tăng đúng một lần. CAS durable vẫn thuộc adapter P2/persistence sau này.

Phân biệt rõ ràng giữa execution state và projection view:
| CT-STATE-011 Execution State | API CT-API-007 `OperationView` | Diễn giải |
| :--- | :--- | :--- |
| `PREPARED` | `accepted` | Lệnh đã ghi nhận biên nhận bền vững |
| `STARTED` | `running` | Đang thực thi trong tiến trình / worker |
| `STARTED` (chờ capability/grant) | `waiting` | Đang chờ tài nguyên / quota / recovery epoch |
| `SUCCEEDED` | `succeeded` | Hoàn thành thành công |
| `FAILED` | `failed` | Thất bại terminal kèm error detail |
| `OUTCOME_UNKNOWN` | `outcome_unknown` | Side effect chưa rõ kết quả, chờ reconciliation |

- Mapper nhận `wait_reason` có cấu trúc của `CT-API-007` làm input thẩm quyền: `STARTED` với `wait_reason` vắng mặt là `running`; `STARTED` với `wait_reason` hiện diện là `waiting`. Không được suy waiting từ timestamp, progress hoặc presentation state. Các execution state khác không được map thành `waiting` chỉ vì caller truyền `wait_reason`.
- **Artifact Cleanup Lifecycle**:
  Tuân thủ nghiêm ngặt CT-STATE-012: `VERIFIED → CLEANUP_ELIGIBLE → CLEANUP_AUTHORIZED → DELETED`. Không có chuyển trạng thái tắt.

**Catalogue RED P4 đề xuất, cố định để audit plan:** `test_tst_m2_p4_001_valid_lifecycle_transitions`, `test_tst_m2_p4_002_forbidden_transition_completed_to_running_rejected`, `test_tst_m2_p4_003_operation_execution_to_projection_mapping`, `test_tst_m2_p4_004_artifact_cleanup_strict_transition_order`, `test_tst_m2_p4_005_batch_waiting_resume_and_terminal_transitions`, `test_tst_m2_p4_006_job_waiting_resume_and_completion_admission`, `test_tst_m2_p4_007_stage_run_reconcile_and_terminal_transitions`, `test_tst_m2_p4_008_operation_forbidden_transition_classes_rejected`, `test_tst_m2_p4_009_stale_expected_revision_rejected_without_mutation`. Identity `P4-002` diễn đạt acceptance rule tổng quát “completed không về running”; implementation oracle phải kiểm `Job COMPLETED → ACTIVE` (trạng thái chạy tương đương) và không được bịa enum `RUNNING` cho Job.

### 6.4. Orchestration Shell, Variant & Capacity Reservations (M2-P6)
Theo đúng `CT-ORC-002` và `CT-ORC-012` (AUD2-B01):
1. **Persistence Bền vững**:
   - `cp_production_batches`: `batch_id`, `workspace_id`, `status`, `target_count`, `created_at`.
   - `cp_video_jobs`: `job_id`, `batch_id`, `workspace_id`, `status`, `snapshot_ref`, `revision`.
   - `cp_stage_runs`: `stage_run_id`, `job_id`, `stage_name`, `attempt`, `status`, `recovery_epoch`.
2. **`BatchCapacityReservation` Riêng biệt**:
   - Bảng `cp_batch_capacity_reservations`: `reservation_id`, `workspace_id`, `batch_id`, `job_id`, `state` (`ACTIVE`, `CONVERTED`, `RELEASED`), `created_at`, `released_at`.
   - Invariant: Một reservation đúng một job; cấp phát capacity nguyên tử; không mô hình bằng counter đơn giản.
3. **`VariantReservation` & VariantRegistryRevision CAS**:
   - Bảng `cp_variant_reservations`: `reservation_id`, `workspace_id`, `job_id`, `fingerprint`, `snapshot_scope`, `validation_ref`, `variation_policy_revision`, `expected_registry_revision`, `committed_registry_revision`, `state` (`ACTIVE`, `CONVERTED`, `RELEASED`), `created_at`.
   - Bảng `cp_variant_registry`: `workspace_id`, `current_registry_revision`.
   - Invariant: Mỗi job tối đa 1 active reservation; kiểm tra CAS trên `current_registry_revision`.
   - Contract errors chuẩn: `VARIANT_CONFLICT` (trùng fingerprint) và `VARIANT_VALIDATION_STALE` (registry revision đã bị thay đổi).
4. **`CompletionLedger` Skeleton**:
   - Bảng `cp_completion_ledger`: `ledger_id`, `workspace_id`, `batch_id`, `job_id`, `capacity_reservation_id`, `variant_reservation_id`, `output_artifact_ref`, `output_hash`, `committed_at`, `actor_id`.
   - Invariant: Unique completion trên mỗi `job_id`.
   - Phạm vi claim của M2: *"G-side completion skeleton/invariants proven using typed test ports/fixtures."* Tuyệt đối không claim full CommitVideoCompletion end-to-end vì C/D/F và render media thực tế chưa thuộc M2.

### 6.5. Module J Config & Secret Boundary Foundation (M2-P5A)

P5A chỉ là target đã plan, không là behavior hiện hữu. `ConfigRevision` có identity immutable, workspace scope, scope key, revision monotonic, canonical content hash, typed payload, effective/audit/change-reason refs và state. PostgreSQL phải giữ FK/unique/check structural; application chịu trách nhiệm canonicalization, typed validation, policy/effective rule và CAS. Contract xác nhận `DRAFT → PUBLISHED → SUPERSEDED`; published không update tại chỗ và `SUPERSEDED` terminal theo terminal rule chung.

`CT-STATE-013` nói revision có thể `INVALIDATED` do lỗi bảo mật nhưng không xác định source state. Đây là **contract clarification required before P5A RED**: không encode cạnh vào `INVALIDATED` hay mở external-account lifecycle trong P5A. `SecretHandle` chỉ giữ workspace/provider/account/alias, redacted fingerprint-or-version, validation/revocation/expiry/audit metadata; không có secret value, raw credential hoặc read-secret-value port. Mọi event/audit chỉ chứa safe ID/ref/revision/status/reason đã redacted theo CT-EVT/CT-SEC; secret store nằm ngoài PostgreSQL business boundary của ADR-0009.

### 6.6. Module I Artifact Metadata & Cleanup Authorization Skeleton (M2-P5B)

P5B là target đã plan, logical sibling P5A sau P4 nhưng migration `0005` chỉ hợp lệ sau `0004` P5A được accept. `ArtifactVersion` là immutable workspace-scoped version có logical artifact identity, SHA-256 64 ký tự, size dương, MIME không rỗng và metadata/ref CT-STO-001. `ArtifactLocation` thuộc cùng workspace/version bằng FK, giữ opaque provider/storage locator không credential/token/signed URL dài hay path có traversal; state/revision mutation tái sử dụng chính xác ArtifactLocationState P4/CT-STATE-012.

P5B phải hỗ trợ `VERIFIED → MISSING` khi verify sau phát hiện mất; không thêm recovery từ `MISSING`, `CORRUPT` hay `OUTCOME_UNKNOWN`. Cleanup metadata luôn theo `VERIFIED → CLEANUP_ELIGIBLE → CLEANUP_AUTHORIZED → DELETED`; authorization immutable giữ version/hash/evidence/policy/epoch/owner/audit refs. Nó không thực thi delete, upload, Drive lifecycle, local journal hoặc claim external byte integrity.

---

## 7. Giao thức Bảo mật, Xác thực & Local HTTPS (M2-P7A)

1. **Bootstrap-Session Protocol (Phù hợp ADR-0009)**:
   - Không xây dựng màn hình login phức tạp; hệ thống đơn người dùng vận hành qua Local Agent.
   - Khi khởi động, Control API server sinh bootstrap session token gắn chặt với `workspace_id` và actor mặc định.
   - Session được thiết lập qua cookie an toàn: `HttpOnly; Secure; SameSite=Strict; Path=/`.
   - Browser không được tự khai báo `workspace_id` đáng tin cậy; mọi request tự động liên kết với workspace từ session cookie đã xác thực.
2. **CSRF Protocol**:
   - Áp dụng cơ chế **Double Submit Cookie**: Server cấp cookie `csrf_token` (`SameSite=Strict; Secure; Path=/`). Mọi request có mutation (`POST`, `PUT`, `DELETE`) từ browser bắt buộc phải đọc cookie này và gửi kèm trong header `X-CSRF-Token`. Server so khớp hai giá trị trước khi cho phép đi qua. Không coi `X-Requested-With` một mình là bằng chứng bảo mật.
3. **Host & Origin Validation**:
   - Host header allowlist: `localhost`, `127.0.0.1`. Từ chối mọi host lạ với HTTP 403 (chống DNS rebinding).
   - Origin header allowlist: Kiểm tra nghiêm ngặt origin của local UI server.
4. **Local HTTPS & Certificate Trust Protocol**:
   - Control API hỗ trợ TLS qua chứng chỉ tự sinh (self-signed loopback certificate).
   - Phân biệt minh bạch:
     * *TLS handshake works*: Kiểm chứng qua HTTP client có nạp CA cert cục bộ.
     * *Browser certificate trust/provisioning*: Được ghi nhận là dependency cấu hình desktop packager ở milestone sau; không dùng `ignoreHTTPSErrors` rồi tuyên bố certificate provisioning PASS.
5. **Durable Technical-Detail Storage**:
   - Bảng `controlplane.cp_technical_details`: `detail_ref` (UUID), `workspace_id`, `correlation_id`, `error_type`, `stack_trace`, `sanitized_context`, `created_at`.
   - Response lỗi API chỉ trả về `technical_detail_ref`. Endpoint `/v1/errors/{detail_ref}` yêu cầu session hợp lệ cùng workspace mới được truy xuất.
6. **Idempotency Trên Mọi Mutation**:
   - Bắt buộc header `Idempotency-Key` cho cả `POST /v1/batches`, `PUT /v1/configs/{scope}` và mọi thao tác thay đổi trạng thái.

---

## 8. Toolchain & Kiểm thử Browser E2E Đích thực (M2-P0 & M2-P8)

### 8.1. Dependency Candidates & Lựa chọn tại M2-P0
- **Backend Candidate**:
  - `fastapi >= 0.135.0` (nghiên cứu phiên bản hỗ trợ native SSE response và Pydantic v2).
  - `uvicorn` (ASGI server).
  - `psycopg_pool` (thư viện connection pool chính thức của psycopg, bắt buộc cài đặt cùng `psycopg[binary]==3.3.5`).
  - `httpx==0.28.1` (phục vụ async client và TestClient).
- **Frontend Toolchain Candidate**:
  - Runtime: Node.js v22 LTS (Active LTS hiện hành).
  - Package Manager: `npm` (khóa exact version trong `toolchain-lock.md`).
  - UI Library: React (khóa exact version tương thích AG Grid Community).
  - Data Table: AG Grid Community (khóa exact version maintained patch).
  - Language: TypeScript (exact version).
  - Build tool: Vite (exact version).
  - E2E Test Tool: `@playwright/test` TypeScript (chạy trong toolchain Node).

### 8.2. Kiến trúc E2E Playwright (Không Mock)
- Tệp test E2E duy nhất: `tests/m2/e2e/*.spec.ts` (chạy qua Node Playwright runner, không tạo Python Playwright trùng lặp).
- **Dòng chảy thực tế**:
  `Playwright Browser → Control API → Application/UoW → PostgreSQL → Outbox → Projection → SSE → AG Grid DOM`.
- **Test-Only Application Driver**: Định nghĩa test driver nội bộ để advance các state của Batch/Job/Operation qua application ports; driver không phải frontend mock, không direct-write DB, không public production endpoint.
- **Tiêu chuẩn Hiệu năng Đã Phê duyệt**:
  - `QR-PERF-005`: 95% thao tác UI thông thường phản hồi hữu ích <= 2 giây.
  - `QR-PERF-006`: Command acknowledgment <= 1 giây.
  - (Bỏ yêu cầu chưa phê duyệt "page load < 1s"; dataset scale giữ trạng thái OPEN theo charter).
