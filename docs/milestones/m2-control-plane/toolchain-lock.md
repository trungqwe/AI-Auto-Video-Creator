# M2 Toolchain & Dependency Lock Specification

**Tệp:** `docs/milestones/m2-control-plane/toolchain-lock.md`  
**Trạng thái:** ACTIVE LOCK (M2-P0)  
**Ngày lập:** 13-09-2026 (Cập nhật sau Independent Audit R1: 13-09-2026)  
**Phạm vi:** Khóa chính xác phiên bản toàn bộ backend dependencies, build system và frontend toolchain của Milestone M2.

---

## 1. Đánh giá và Khóa Môi trường Runtime Hệ thống

### 1.1. Khảo sát và Đánh giá Ứng viên Node.js (Guardrail 1 & Audit Item 5)

Theo yêu cầu guardrail P0, Node.js không được coi là đã chọn sẵn mà phải đánh giá compatibility proof giữa các ứng viên LTS:

| Ứng viên Node.js | Chu kỳ Hỗ trợ | Khả năng tương thích Toolchain (Vite 6, React 18, AG Grid 32, Playwright 1.50) | Trạng thái Đánh giá |
| :--- | :--- | :--- | :--- |
| **Node.js 24.x** | Active LTS | Hỗ trợ V8 engine mới nhất. Đã đánh giá là ứng viên tương thích lý thuyết (reviewed candidate / future support target). Tuy nhiên, trạm máy Windows thực tế của người dùng chưa nâng cấp runtime lên Node 24; việc dùng Node 24 giả định sẽ vi phạm nguyên tắc kiểm chứng thực nghiệm. | **REVIEWED CANDIDATE:** Đạt điều kiện hỗ trợ tương lai; chưa kích hoạt làm live runtime. |
| **Node.js 22.x** (cụ thể `v22.17.0`) | Maintenance LTS (Hỗ trợ dài hạn đến 04-2027) | Đã chứng minh tương thích 100% với React 18.3.1, Vite 6.2.0, Playwright 1.50.1, TypeScript 5.7.3, AG Grid 32.3.9. Không có bất kỳ cảnh báo deprecation nào trên Windows. | **LIVE-TESTED SELECTED RUNTIME:** Đã kiểm chứng trực tiếp trên trạm phát triển, đi kèm `npm 10.9.2`. |

### 1.2. Khóa Machine-Readable Declaration cho Frontend (Audit Item 5)

- Thư mục Frontend duy nhất: `src/controlplane/ui/`
- Khai báo trong `src/controlplane/ui/package.json`:
  - `"packageManager": "npm@10.9.2"`
  - `"engines": { "node": ">=22.17.0 <23.0.0", "npm": "10.9.2" }`
- Tệp khóa phiên bản Node cam kết trong repository:
  - `src/controlplane/ui/.nvmrc`: `22.17.0`
  - `src/controlplane/ui/.node-version`: `22.17.0`

---

## 2. Backend Packaging Strategy & Exact Dependency Lock (Audit Item 2, 3, 4)

### 2.1. Kiến trúc Đóng gói & Build System Version Pins

- **Mô hình**: Đóng gói standard Python package theo chuẩn PEP 517/518/621 tại `src/controlplane/pyproject.toml`.
- **Build Backend Được Chọn**: `setuptools` (thay thế hoàn toàn bản nháp Hatchling cũ nhằm thống nhất một sự thật duy nhất giữa docs, pyproject, lockfile và wheel build).
- **Exact Build-System Version Pins**:
  ```toml
  [build-system]
  requires = ["setuptools==75.8.0", "wheel==0.45.1"]
  build-backend = "setuptools.build_meta"
  ```
- **Phạm vi & Phân định Claim (Không Overclaim)**:
  - `setuptools==75.8.0` và `wheel==0.45.1` là **exact build-system version pins** được khai báo tại `src/controlplane/pyproject.toml` theo PEP 518.
  - Các build dependencies này không nằm trong runtime lockfile (`requirements.lock` và `uv.lock` giải quyết 21 runtime transitive packages). Khi build package, build environment tuân thủ exact pins này.
- **Tên package**: `controlplane`, version `0.2.0`.
- **CLI Entrypoint**: `controlplane = "controlplane.entrypoint:main"`.
- **Reproducible Fresh-Environment Proof**:
  - Không dựa vào `.pth` làm bằng chứng package gate.
  - Kiểm chứng tự động tạo clean virtual environment bằng `uv venv` (dynamic binary resolver qua `resolve_uv_executable()`, không hardcode đường dẫn, fail-closed không silent skip).
  - Cài đặt dependency graph đóng băng từ `src/controlplane/requirements.lock`, xác nhận các gói cốt lõi khớp exact lock (`psycopg-pool==3.3.1`, `fastapi==0.141.1`, `pydantic-core==2.46.5`).
  - Build wheel và cài đặt với cờ `--no-deps` vào clean venv để chứng minh tính độc lập và khớp với locked dependencies.
  - Thực thi thành công CLI entrypoint trong môi trường cô lập.

### 2.2. Toàn bộ Resolved Dependency Graph của Control Plane (src/controlplane/requirements.lock & uv.lock)

Toàn bộ 21 packages trong transitive graph đã được resolve và khóa cố định (frozen) không phụ thuộc floating version:

| Gói thư viện | Phiên bản Khóa Exact | Vai trò trong Graph & Nguồn gốc |
| :--- | :--- | :--- |
| `fastapi` | `0.141.1` | Native async framework; native SSE (>= 0.135.0). Khai báo direct. |
| `uvicorn` | `0.52.4` | ASGI loopback server daemon. Khai báo direct. |
| `httpx` | `0.28.1` | HTTP async client & test client. Khai báo direct. |
| `psycopg` | `3.3.5` | PostgreSQL driver native. Khai báo direct. |
| `psycopg-binary` | `3.3.5` | Prebuilt binary driver C-extension cho Windows x86_64. |
| `psycopg-pool` | `3.3.1` | Connection pool chuyên biệt, được giải quyết cố định qua lockfile. |
| `pydantic` | `2.13.5` | Data validation và domain envelopes. Khai báo direct. |
| `pydantic-core` | `2.46.5` | Core Rust-engine của Pydantic v2. |
| `starlette` | `1.6.0` | ASGI core underlying FastAPI. |
| `anyio` | `4.15.1` | Structured concurrency backend cho HTTPX & Starlette. |
| `click` | `8.5.0` | CLI command toolkit cho Uvicorn. |
| `h11` | `0.16.0` | Pure-Python HTTP/1.1 protocol engine. |
| `httpcore` | `1.0.9` | Low-level HTTP transport layer của HTTPX. |
| `idna` | `3.19` | Internationalized domain names. |
| `certifi` | `2026.7.22` | Root CA bundles cho HTTP requests an toàn. |
| `annotated-doc` | `0.0.5` | Type docstring processing. |
| `annotated-types` | `0.8.0` | Reusable constraint annotations. |
| `typing-extensions` | `4.16.0` | Backported typing features. |
| `typing-inspection` | `0.4.4` | Runtime type inspection. |
| `tzdata` | `2026.4` | IANA time zone database. |

### 2.3. Bảo toàn Milestone M1 Regression

- Root `pyproject.toml` và root `uv.lock` tiếp tục đóng băng cho `ai-auto-video-creator-m1-proof` (SHA-256 hash giữ nguyên `31bae731c8ec80e52fbd9a75b3969d0d556e7489f48fc13d151c0c0cfe4e9380`).
- Không cài đặt đè các package mới vào workspace `.venv` làm trôi `uv sync --frozen --check`.
- Kết nối phát triển cục bộ cho phép import `controlplane` qua `.venv/Lib/site-packages/controlplane.pth` nhằm phục vụ developer convenience mà không làm hỏng M1 suite.

### 2.4. Single-Pipeline Deterministic Evidence Synthesis & Profile Registry Pattern

- **Profile Registry Pattern**:
  - `PackageSemanticProfile` và `SemanticProfileRegistry` quản lý việc đánh giá ngữ nghĩa cho từng package.
  - `M2P0SemanticProfile` quản lý policy cho `M2-P0` (30 unit tests PASS, M1 93 passed, secret scan CLEAN).
  - Khóa chặt fail-closed: Profile không xác định hoặc profile giả mạo giữa các package (`Cross-package profile spoofing`) sẽ bị BLOCK.
  - Các package P1-P8 mở rộng qua extension point `register_semantic_profile` mà không sửa đổi core validator logic.
- **Single-Pipeline Evidence Synthesis**:
  - Toàn bộ bằng chứng của package được sinh ra qua script tuần tự duy nhất `src/controlplane/infrastructure/evidence/synthesizer.py`.
  - Chuỗi thực thi tuyến tính theo một `run_id` duy nhất:
    1. Chạy M1 regression suite -> trích xuất `m1-regression.xml` và `m1-regression-report.txt`.
    2. Chạy M2-P0 test suite -> trích xuất `m2-p0-tests.xml` và `p0-test-report.txt`.
    3. Thực hiện Secret Scan trên toàn bộ source code, tests và evidence -> `secret-scan.json`.
    4. Trích xuất verified metrics từ machine-readable artifacts.
    5. Sinh `status.json` từ observed metrics (tuyệt đối không nhập số liệu thủ công).
    6. Sinh `status.md` từ `status.json`.
    7. Ghi `commands.jsonl` với schema chuẩn (`run_id`, `created_artifacts`, `summary` khớp từng file đã quét).
    8. Sinh `hashes.sha256` tạo acyclic DAG loại trừ chính nó.
    9. Chạy kiểm chứng cuối cùng qua Two-Tier Evidence Validator ở chế độ read-only.


---

## 3. Frontend Toolchain & Dependencies (src/controlplane/ui/)

Duy nhất **một package universe** tại `src/controlplane/ui/package.json` và `src/controlplane/ui/package-lock.json`. Tuyệt đối không tạo file lock ở root.

| Thư viện / Công cụ | Phiên bản Khóa Exact | Lý do Lựa chọn & Cơ sở Kỹ thuật |
| :--- | :--- | :--- |
| `react` | `18.3.1` | Bản phát hành ổn định dài hạn của React 18, tương thích 100% với AG Grid Community. |
| `react-dom` | `18.3.1` | Thư viện render DOM cho React 18. |
| `ag-grid-community` | `32.3.9` | Nhánh `v32-lts` maintained patch chính thức (theo dist-tags của AG Grid). Tương thích hoàn toàn kiến trúc bảng ADR-0007. |
| `ag-grid-react` | `32.3.9` | React wrapper cho AG Grid Community v32-lts. |
| `typescript` | `5.7.3` | Trình biên dịch TypeScript hiện đại, kiểm tra kiểu tĩnh nghiêm ngặt (`tsconfig.json`). |
| `vite` | `6.2.0` | Build tool và dev server siêu tốc dựa trên ESM native (`vite.config.ts`). |
| `@vitejs/plugin-react` | `4.3.4` | Plugin chính thức hỗ trợ JSX/TSX và Fast Refresh cho React. |
| `@types/react` | `18.3.18` | Type definitions cho React 18. |
| `@types/react-dom` | `18.3.5` | Type definitions cho React DOM 18. |
| `@playwright/test` | `1.50.1` | Browser automation và E2E testing framework chạy trong Node toolchain (`playwright.config.ts`). |

---

## 4. Quy định Ràng buộc và Guardrails (M2-P0)

1. **Cấm tuyệt đối sử dụng `latest`**, `^`, `~` trong cả backend lock và frontend `package.json`.
2. **Không tạo `package-lock.json` thứ hai** ở thư mục gốc repo.
3. **Domain Layer Purity**: Mọi module trong `src/controlplane/domain` cấm import danh sách managed boundary: `fastapi`, `starlette`, `uvicorn`, `psycopg`, `psycopg_pool`, `temporalio`, `google`, `httpx`, `flask`, `django`, `sqlalchemy`.
4. **Cấm triệt để Prototype M1**: Cấm bất kỳ code nào của M2 import `m1proof` hoặc prefix `m1proof.*`, `src.m1proof.*`.
5. **Advisory Lock ở P1**: Migration runner ở P1 phải dùng session-level advisory lock trên dedicated connection với bounded wait timeout.
