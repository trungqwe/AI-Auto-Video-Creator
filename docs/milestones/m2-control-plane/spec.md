# M2 — Control Plane và Nền tảng Có thể Quan sát: Đặc tả Kỹ thuật (Technical Specification)

**Tệp:** `docs/milestones/m2-control-plane/spec.md`  
**Trạng thái:** BẢN THẢO TRÌNH DUYỆT (AUTHORIZED FOR PLANNING)  
**Ngày lập:** 13-09-2026 (Cập nhật sau phản hồi User Checkpoint)  
**Căn cứ kiến trúc:**
- [Roadmap, Mục 8 — M2 Control Plane](../../11-roadmap.md)
- [08-architecture.md](../../08-architecture.md)
- Hợp đồng: [00-common-contract.md](../../09-contracts/00-common-contract.md), [01-control-api-and-stream.md](../../09-contracts/01-control-api-and-stream.md), [02-domain-events.md](../../09-contracts/02-domain-events.md), [09-orchestration-contracts.md](../../09-contracts/09-orchestration-contracts.md), [10-storage-contracts.md](../../09-contracts/10-storage-contracts.md), [11-configuration-security-contracts.md](../../09-contracts/11-configuration-security-contracts.md), [12-state-machines.md](../../09-contracts/12-state-machines.md).
- ADR liên quan: [ADR-0001](../../adr/0001-hybrid-modular-monolith.md), [ADR-0002](../../adr/0002-authoritative-data-and-search.md), [ADR-0004](../../adr/0004-commit-idempotency-and-fencing.md), [ADR-0005](../../adr/0005-snapshots-and-content-invariants.md), [ADR-0007](../../adr/0007-runtime-and-admin-ui.md), [ADR-0009](../../adr/0009-trust-boundaries-and-secrets.md), [ADR-0010](../../adr/0010-storage-lifecycle-and-recovery.md), [ADR-0011](../../adr/0011-observability-capacity-and-cost.md).
- Chiến lược kiểm thử: [10-test-strategy.md](../../10-test-strategy.md).

---

## 1. Mục tiêu và Ý nghĩa Nghiệp vụ

Milestone M2 xây dựng lõi điều khiển (**Control Plane**) và nền tảng có thể quan sát (**Observability**) cho toàn bộ hệ thống theo kiến trúc Modular Monolith ([ADR-0001](../../adr/0001-hybrid-modular-monolith.md)). Mục tiêu bao gồm:
1. **Thiết lập nền móng dữ liệu PostgreSQL nghiệp vụ**: Quản lý connection pool `psycopg`, transaction nguyên tử (Unit of Work), cơ chế migration có kỷ luật và phân vùng dữ liệu nghiêm ngặt theo `workspace_id`.
2. **Cơ chế xác thực, danh tính và phiên (Workspace, Identity, Session)**: Thực thi xác thực actor (`user`, `scheduler`, `system`), quản lý phiên desktop (`session_id`), ràng buộc workspace và bảo mật HTTP (Host, Origin, CSRF, local HTTPS).
3. **Chuẩn hóa giao tiếp Envelope & Invariant**: Thực thi `MessageEnvelope`, `CommandEnvelope`, `CommandReceipt`, `ProblemDetail` (RFC 9457), timestamps RFC 3339 UTC, kiểm soát đồng thời lạc quan (`expected_revision`) và idempotent command execution với `cp_idempotency_records`.
4. **Hiện thực hóa Transactional Outbox & Event Engine**: Cam kết tính nguyên tử giữa bản ghi nghiệp vụ và outbox event; cơ chế publisher phát at-least-once và consumer deduplication bền vững; cập nhật projection cho read models.
5. **Máy trạng thái phân hệ cốt lõi**: Hiện thực hóa state machine chuẩn theo CT-STATE-008..012 cho Operation, Production Batch, Video Job, Stage Run và Artifact Location, ngăn chặn tuyệt đối các transition cấm (`FORBIDDEN_TRANSITION`).
6. **Nền tảng Phân hệ J (Configuration & Security)**: Quản lý bản sửa đổi cấu hình bất biến (`ConfigRevision`), phân tách `SecretHandle` (tuyệt đối không lưu plaintext secret trong cơ sở dữ liệu nghiệp vụ, tuân thủ ADR-0009).
7. **Nền tảng Phân hệ I (Storage Metadata)**: Quản lý metadata `ArtifactVersion`, `ArtifactLocation` và trạng thái verification (CT-STATE-012).
8. **Nền tảng Phân hệ G (Orchestration Shell)**: Cấp phát `ExecutionGrant` có `recovery_epoch`, quản lý `BatchCapacityReservation`, `VariantReservation` (AUD2-B01 / CT-ORC-012) chống trùng lặp góc kể/biến thể, và khung ghi sổ hoàn thành nguyên tử `CompletionLedger`.
9. **Nền tảng Phân hệ H (Control API & Admin UI Shell)**:
   - Backend: FastAPI HTTP server cung cấp REST Control API `/v1` và luồng Server-Sent Events (SSE) `/v1/operations/stream` có cursor reconnect/resync.
   - Frontend: **React + TypeScript + AG Grid Community** theo đúng [ADR-0007](../../adr/0007-runtime-and-admin-ui.md), giao diện bảng tiếng Việt 1080p+, tích hợp thật vào Control API/SSE, kiểm thử Browser E2E thật từ Browser → API → DB → Outbox → SSE → DOM (không dùng JS fixture giả lập).

---

## 2. Ranh giới Phạm vi (Scope Boundaries)

### 2.1. Trong Phạm vi M2 (In-Scope)
- Quản lý database schema, transaction boundary, workspace/identity/session.
- Common envelopes, idempotency store, concurrency control, RFC 9457 error format.
- Transactional outbox pattern, event deduplication, operation projection.
- State machines cho Operation, Batch, Job, Stage Run, Artifact Location.
- Module J configuration revision & secret handle boundary.
- Module I artifact metadata lifecycle store.
- Module G orchestration shell, execution grants, variant reservations, completion ledger skeleton.
- Module H Control API REST `/v1`, local HTTPS, security middleware (Host, Origin, CSRF, secret redaction, safe technical detail ref).
- Module H SSE `/v1/operations/stream` với cursor-based resume và resync handling.
- Module H Admin UI: React, TypeScript, AG Grid Community, hiển thị tiếng Việt, bảng dữ liệu, form gửi command mẫu, live stream SSE, error modal.
- Kiểm thử toàn diện: Unit, Contract, Concurrency, Fault-injection, Security, Migration rollback, Browser E2E thật (Playwright).
- Evidence synthesis và exit gate audit cho M2.

### 2.2. Ngoài Phạm vi M2 (Out-of-Scope - Cấm Thực Hiện)
- **Tuyệt đối cấm**: Thu thập tin tức, quản lý RSS hay nguồn crawl (thuộc Module A - M3).
- **Tuyệt đối cấm**: Chuẩn hóa nội dung bài báo, chống trùng lặp content hay liên kết sự kiện (thuộc Module B - M3).
- **Tuyệt đối cấm**: Tải media, xử lý ảnh, tạo hook clip hay quản lý Drive storage lifecycle đầy đủ (thuộc M4).
- **Tuyệt đối cấm**: Gọi LLM sinh kịch bản/story angle hay tạo kế hoạch sản xuất AI (thuộc Module D - M5).
- **Tuyệt đối cấm**: Tổng hợp giọng nói TTS, tính toán word timing hay render FFmpeg video thực tế (thuộc M6).
- Không xây dựng SaaS đa người dùng phức tạp hoặc cổng thanh toán.

---

## 3. Kiến trúc Thành phần & Hướng Phụ thuộc (Modular Monolith)

Theo [ADR-0001](../../adr/0001-hybrid-modular-monolith.md), mã nguồn sản phẩm M2 nằm tại `src/controlplane/`. **Quy tắc phụ thuộc một chiều bắt buộc:**
- **Domain Layer** (`common`, `statemachine`) là hạt nhân thuần túy, **KHÔNG ĐƯỢC PHÉP IMPORT** bất kỳ thư viện ngoài nào như `fastapi`, `temporalio`, `psycopg`, `google` hay mã prototype `src/m1proof`.
- **Application Layer** (`orchestration`, `outbox`, `config_security`, `storage_meta`) điều phối nghiệp vụ qua các port và interface, phụ thuộc vào Domain Layer.
- **Infrastructure / Presentation Layer** (`db`, `api`, `ui`) thực thi các adapter kỹ thuật (FastAPI, psycopg connection pool, React/Vite web), phụ thuộc vào Application Layer và Domain Layer.

```
src/controlplane/
├── domain/                     # Pure domain logic & models
│   ├── common/                 # Envelopes, RFC 9457 errors, RFC 3339 timestamps, IDs
│   └── statemachine/           # Operation, Batch, Job, Stage, Artifact state machines
├── application/                # Business use cases & coordinators
│   ├── idempotency/            # Idempotency manager & deduplication logic
│   ├── outbox/                 # Outbox coordinator & event dispatcher
│   ├── config_security/        # Config revision manager & secret handle resolver
│   ├── storage_meta/           # Artifact metadata coordinator
│   └── orchestration/          # Shell coordinator, variant reservations, completion ledger
├── infrastructure/             # Technical adapters & external integration
│   ├── db/                     # PostgreSQL connection pool, UoW, migration runner
│   │   └── migrations/         # Forward & rollback SQL scripts
│   └── security/               # Host/Origin validation, CSRF token, local TLS/HTTPS, redaction
├── api/                        # HTTP & SSE Presentation (FastAPI)
│   ├── routes/                 # REST routes (/v1/operations, /v1/batches, /v1/configs)
│   ├── sse/                    # Server-Sent Events generator (/v1/operations/stream)
│   └── middleware/             # Idempotency, security, error handling RFC 9457
└── ui/                         # React + TypeScript + AG Grid Community Frontend
    ├── src/                    # React components, grid setup, SSE client
    ├── package.json            # Pinned frontend dependencies
    └── vite.config.ts          # Build configuration
```

---

## 4. Chiến lược Migration Cơ sở Dữ liệu (Database Migration Strategy)

### 4.1. So sánh & Đánh giá Giải pháp
- **Phương án A: Thư viện ORM-based (Alembic / SQLAlchemy)**: Alembic là tiêu chuẩn vàng trong hệ sinh thái Python, tuy nhiên Alembic được tối ưu cho SQLAlchemy ORM. Dự án AI Auto Video Creator đã chốt kiến trúc sử dụng `psycopg 3` native connection pool, mô hình dữ liệu tường minh bằng SQL schema thuần (Raw SQL) để kiểm soát 100% transaction boundary, locking và hiệu năng. Sử dụng Alembic kéo theo dependency nặng SQLAlchemy và tăng nguy cơ xung đột connection pool.
- **Phương án B: Raw SQL Native Migration Runner (Được lựa chọn)**: Xây dựng một migration runner chuyên biệt bằng Python thuần + `psycopg 3`, thực thi các tệp SQL thuần (`.sql`) với kiểm soát giao dịch nghiêm ngặt.

### 4.2. Thiết kế Chi tiết 8 Tiêu chuẩn Bắt buộc của Custom Migration Runner
1. **Version Table (`cp_schema_migrations`)**:
   ```sql
   CREATE TABLE IF NOT EXISTS controlplane.cp_schema_migrations (
       version INT PRIMARY KEY,
       name VARCHAR(255) NOT NULL,
       checksum_sha256 CHAR(64) NOT NULL,
       applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
       execution_ms INT NOT NULL,
       state VARCHAR(32) NOT NULL -- 'APPLIED', 'FAILED', 'DIRTY'
   );
   ```
2. **Checksum Verification**: Mỗi file migration có mã băm SHA-256 tính từ nội dung file. Khi khởi chạy, runner đối soát checksum của các migration đã áp dụng; nếu phát hiện file bị sửa đổi (tampered) -> dừng ngay lập tức (fail-closed).
3. **Strict Ordering**: Migration được đặt tên có số thứ tự tăng dần (`0001_initial_controlplane.sql`, `0002_add_variant_reservations.sql`). Runner từ chối chạy nếu có khoảng trống (gap) hoặc sai thứ tự.
4. **Concurrent Migration Lock**: Sử dụng PostgreSQL transaction advisory lock native: `SELECT pg_advisory_xact_lock(hashtext('controlplane_migrations'));` tại thời điểm bắt đầu migration session, đảm bảo không bao giờ có 2 runner chạy đồng thời.
5. **Failed / Dirty Migration Handling**: Khi một migration bị lỗi cú pháp/logic, trạng thái được ghi nhận là `DIRTY`/`FAILED` (nếu script có DDL không thể rollback) hoặc toàn bộ transaction bị rollback và dừng hệ thống. Hệ thống chặn mọi khởi động tiếp theo cho đến khi trạng thái dirty được khắc phục.
6. **Forward Migration**: Mỗi bước thực thi trong một `transaction block` riêng biệt; chỉ khi câu lệnh SQL thành công 100% thì bản ghi trong `cp_schema_migrations` mới được commit kèm thời gian thực thi.
7. **Rollback Migration**: Mỗi tệp migration `XXXX_name.sql` bắt buộc phải có tệp đảo ngược tương ứng `XXXX_name.rollback.sql`. Script rollback được kiểm thử tự động trong pipeline CI/test để đảm bảo hạ schema về trạng thái ban đầu sạch sẽ.
8. **Interrupted Migration Recovery**: Nếu tiến trình migration bị kill đột ngột, khóa advisory lock tự động giải phóng bởi PostgreSQL; runner lần khởi động sau kiểm tra tính toàn vẹn của bảng và phục hồi an toàn.

---

## 5. Đặc tả Giao thức Evidence M2 (Evidence Protocol)

Mọi work package của M2 (từ M2-P0 đến M2-P9) phải tự sinh và lưu trữ đầy đủ bằng chứng kiểm chứng trong thư mục `docs/milestones/m2-control-plane/evidence/<package-id>/`:
1. **`commands.jsonl`**: Ghi nhận toàn bộ các lệnh kiểm thử thực tế đã chạy, tham số, thời gian thực thi UTC, exit code và hash kết quả.
2. **`status.md`**: Tệp trạng thái machine-readable ghi nhận:
   - `package_id`, `milestone = "M2"`
   - `status`: `NOT_STARTED` | `RED_CONFIRMED` | `IN_PROGRESS` | `PASS` | `FAIL` | `STOPPED`
   - `test_counts`: total, passed, failed, skipped
   - `coverage_pct`
   - `evidence_hashes`
3. **`red-observations.md`**: Ghi nhận chi tiết nguyên nhân RED hợp lệ, oracle mong đợi và tham chiếu tới tệp log thô.
4. **`red-<package>-stdout.txt`**: File log thô UTF-8 không BOM ghi lại toàn bộ output của lần chạy test RED đầu tiên chứng minh assertion thất bại đúng oracle.
5. **`hashes.sha256`**: Danh sách mã băm SHA-256 của toàn bộ tệp bằng chứng trong thư mục của package.
6. **Capability Evidence**: Khi liên quan đến external/integration runtime (PostgreSQL 18.6, HTTPS TLS cert, Browser E2E trace), tệp JSON tương ứng phải được tạo và lưu trữ.
- **Quy tắc Gate P9**: Work package M2-P9 (Exit Audit) chỉ có nhiệm vụ kiểm tra chéo, xác thực băm và tổng hợp evidence đã tồn tại. **Tuyệt đối cấm hard-code PASS, không suy đoán PASS từ sự tồn tại của thư mục, và không dùng mock để nâng cấp capability gate.**

---

## 6. Bảo mật, Workspace, Danh tính và Phiên làm việc (Module H & Infrastructure)

Theo CT-API-001/010 và [ADR-0009](../../adr/0009-trust-boundaries-and-secrets.md):
1. **Workspace Boundary**: Mọi bảng dữ liệu, query và command đều gắn liền với `workspace_id`. Không có query nào được phép đọc xuyên workspace mà không có chỉ định rõ ràng.
2. **Actor Identity**: Mọi request mang định danh actor:
   - `actor_type`: `USER`, `SCHEDULER`, `SYSTEM`, `WORKFLOW`
   - `actor_id`: Định danh người dùng hoặc service account
3. **Desktop Session Management**: Quản lý phiên làm việc máy trạm (`session_id`), thời gian bắt đầu, trạng thái hoạt động, ghi log session an toàn.
4. **Local HTTPS / TLS**: Control API hỗ trợ chạy trên HTTPS qua TLS certificate cục bộ (tự sinh self-signed loopback certificate cho localhost), đảm bảo truyền thông mã hóa an toàn giữa browser và local server.
5. **Host & Origin Validation**:
   - `Host` header bắt buộc phải thuộc allowlist: `localhost`, `127.0.0.1`, hoặc domain nội bộ đã cấu hình; từ chối mọi host lạ để chặn DNS rebinding.
   - `Origin` header kiểm tra chặt chẽ cho các mutation requests; từ chối mọi origin bên ngoài.
6. **CSRF Protection**: Áp dụng cơ chế Double Submit Cookie hoặc Custom Request Header (`X-Requested-With` / `X-CSRF-Token`) cho tất cả các HTTP methods có mutation (`POST`, `PUT`, `PATCH`, `DELETE`).
7. **Secret Redaction & Safe Error Inspection**:
   - Bộ lọc `SecretRedactor` quét mọi response JSON và log để loại bỏ chuỗi token, credential hoặc private key.
   - Không nhúng stack trace hay chi tiết hệ thống thô vào response lỗi chung.
   - Khi xảy ra lỗi, server cấp một mã tham chiếu an toàn `technical_detail_ref`. Chỉ user có quyền trong cùng workspace mới có thể gọi endpoint `/v1/errors/{technical_detail_ref}` để tra cứu chẩn đoán chi tiết.

---

## 7. Khóa Công nghệ & Toolchain (Dependency & Toolchain Locks)

### 7.1. Backend Dependency Candidates (M2-P0 Selection & Lock)
Không tự ý khóa phiên bản cũ. Trong M2-P0, thực hiện compatibility proof trên các candidate hiện hành:
- **Python**: CPython 3.13.15 (đã khóa tại M1).
- **PostgreSQL Driver**: `psycopg[binary]==3.3.5` (đã khóa tại M1).
- **Core Models**: `pydantic==2.13.5` (đã khóa tại M1).
- **Web Framework Candidate**: `fastapi` (đánh giá phiên bản hỗ trợ native SSE và Pydantic v2 tốt nhất trên Python 3.13, ví dụ >= 0.115.8).
- **ASGI Server Candidate**: `uvicorn` (phiên bản ổn định trên Windows loopback).
- **Async HTTP Client**: `httpx==0.28.1` (phục vụ TestClient và SSE testing).
*Sau khi M2-P0 hoàn tất compatibility proof, các phiên bản chính xác (exact pinned) sẽ được ghi vào `pyproject.toml` và `uv.lock`.*

### 7.2. Frontend Toolchain Locks (ADR-0007 React + TypeScript + AG Grid)
- **Runtime & Package Manager**: Node.js v22 LTS (hoặc v20 LTS đã cài đặt trên máy), `npm` / `pnpm`.
- **Framework & UI Library**:
  - `react==18.3.1` (hoặc React 19 nếu tương thích AG Grid Community)
  - `react-dom==18.3.1`
  - `@types/react==18.3.12`, `@types/react-dom==18.3.1`
- **Data Table**:
  - `ag-grid-community==32.3.3`
  - `ag-grid-react==32.3.3`
- **Language & Build Tool**:
  - `typescript==5.7.3`
  - `vite==6.2.0` (Build tool nhẹ, dev server nhanh)
- **Unit & Component Testing**:
  - `vitest==3.0.7`
  - `@testing-library/react==16.2.0`
- **Browser E2E Testing**:
  - `@playwright/test==1.50.1` (Automated browser testing Chrome/Chromium headless)
*Tuyệt đối không dùng `latest` trong bất kỳ cấu hình nào.*

---

## 8. Lát cắt Người dùng Thực tế & Kiểm thử E2E Đích thực

Giao diện Admin UI không được dùng dữ liệu giả lập (mock/fixture) hard-code trong JavaScript để tự nhận là E2E. Quy trình kiểm chứng E2E của M2 phải kích hoạt một dòng chảy thực sự xuyên suốt toàn hệ thống:
```
[Browser Action (Playwright)]
       │
       ▼ (HTTP POST /v1/batches với Idempotency-Key)
[Control API (FastAPI)]
       │
       ▼ (Atomic Transaction: Batch + Outbox Event)
[PostgreSQL Database (cp_batches + cp_outbox_events)]
       │
       ▼ (Background Event Dispatcher)
[Operation Projection & SSE Stream Service]
       │
       ▼ (Server-Sent Events: text/event-stream)
[Browser DOM (React / AG Grid State Update)]
```
- **Xác thực**: Playwright kiểm tra trực tiếp DOM của AG Grid cập nhật trạng thái từ `ACCEPTED` sang `RUNNING` và `SUCCEEDED` thông qua stream SSE thật.
- **Tiếng Việt**: Giao diện hiển thị tiếng Việt có dấu 100%, hỗ trợ độ phân giải màn hình desktop từ 1080p (1920x1080) trở lên, Dark Mode hiện đại.
