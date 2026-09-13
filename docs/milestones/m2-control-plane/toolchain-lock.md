# M2 Toolchain & Dependency Lock Specification

**Tệp:** `docs/milestones/m2-control-plane/toolchain-lock.md`  
**Trạng thái:** ACTIVE LOCK (M2-P0)  
**Ngày lập:** 13-09-2026  
**Phạm vi:** Khóa chính xác phiên bản toàn bộ backend dependencies và frontend toolchain của Milestone M2.

---

## 1. Đánh giá và Khóa Môi trường Runtime Hệ thống

### 1.1. Khảo sát và Đánh giá Ứng viên Node.js (Guardrail 1)

Theo yêu cầu guardrail P0, Node.js không được mặc định chọn sẵn mà phải đánh giá compatibility proof giữa các phiên bản LTS được hỗ trợ trước khi exact-pin:

| Ứng viên Node.js | Chu kỳ Hỗ trợ | Khả năng tương thích Toolchain (Vite 6, React 18, AG Grid 32, Playwright 1.50) | Đánh giá & Quyết định |
| :--- | :--- | :--- | :--- |
| **Node.js 24.x** | Active LTS | Hỗ trợ V8 engine mới nhất. Tuy nhiên, một số native binding / binary download của Playwright trên môi trường Windows x86_64 có rủi ro cảnh báo tương thích deprecation và chưa phải là runtime mặc định trên trạm làm việc của người dùng. | **DỰ PHÒNG:** Chưa chọn vì runtime trạm làm việc chưa nâng lên Node 24. |
| **Node.js 22.x** (cụ thể `v22.17.0`) | Maintenance LTS (Hỗ trợ dài hạn đến 04-2027) | Đã chứng minh tương thích 100% với React 18.3.1, Vite 6.2.0, Playwright 1.50.1, TypeScript 5.7.3, AG Grid 32.3.9. Không có bất kỳ cảnh báo deprecation nào trên Windows. | **CHỌN CHÍNH THỨC (EXACT-PIN):** `v22.17.0` đi kèm `npm 10.9.2`. Đã được kiểm chứng trực tiếp trên trạm phát triển, đảm bảo tính tái lập (reproducibility) cao nhất. |

### 1.2. Khóa Runtime Hệ thống

| Thành phần | Phiên bản Khóa Exact | Cơ sở Kỹ thuật & Ghi chú |
| :--- | :--- | :--- |
| **Python** | `==3.13.15` (CPython 3.13.12+ runtime) | Kế thừa từ Milestone M1. Đảm bảo compatibility với Pydantic 2.13.5 và C-extensions. |
| **Node.js** | `v22.17.0` | Node 22 LTS (Maintenance LTS). Đã xác nhận trên trạm máy. |
| **npm** | `10.9.2` | Bộ công cụ đóng gói duy nhất cho frontend universe tại `src/controlplane/ui/`. |
| **Package Manager (Python)** | `uv==0.12.13` | Trình quản lý dependency hỗ trợ frozen lockfile resolution. |

---

## 2. Backend Packaging Strategy & Dependency Lock (Guardrail 2 & 5)

### 2.1. Kiến trúc Đóng gói (Production Packaging Strategy)

- **Mô hình**: Đóng gói standard Python package theo chuẩn PEP 517/518/621 tại `src/controlplane/pyproject.toml` với build backend `hatchling>=1.26.0`.
- **Tên package**: `controlplane`, version `0.2.0`.
- **Entrypoint**: `controlplane = "controlplane.entrypoint:main"`.
- **Bảo toàn M1 Regression**: Root `pyproject.toml` và root `uv.lock` tiếp tục đóng băng cho M1-proof (`name = "ai-auto-video-creator-m1-proof"`), giữ nguyên SHA-256 hash của `uv.lock` (`31bae731c8ec80e52fbd9a75b3969d0d556e7489f48fc13d151c0c0cfe4e9380`) để 93/93 tests M1 luôn PASS 100%.
- **Workspace Integration**: Cấu hình `.venv/Lib/site-packages/controlplane.pth` trỏ tới `src/`, cho phép import `import controlplane` trực tiếp trong môi trường workspace mà không dùng test-only `sys.path.insert()` hacks.
- **Fresh Documented Environment**: Trong một môi trường Python 3.13 mới, việc cài đặt và import được thực hiện qua:
  ```powershell
  python -m venv .venv
  pip install -e src/controlplane
  # hoặc uv pip install -e src/controlplane
  ```

### 2.2. Đánh giá và Khóa Exact Backend Dependencies (FastAPI Native SSE >= 0.135.0)

FastAPI hỗ trợ native Server-Sent Events (SSE) bắt đầu từ phiên bản `>= 0.135.0`. Bản phát hành ổn định `0.141.1` được kiểm chứng tương thích trọn vẹn với Python 3.13.15, Pydantic 2.13.5 và HTTPX 0.28.1. Tuyệt đối không dùng floating version.

| Gói thư viện | Phiên bản Khóa Exact | Vai trò trong Milestone M2 & Cơ sở Tương thích |
| :--- | :--- | :--- |
| `fastapi` | `0.141.1` | Native async framework; hỗ trợ native SSE (yêu cầu >= 0.135.0); tích hợp Pydantic v2. |
| `uvicorn` | `0.52.4` | ASGI web server cho Control API loopback daemon. |
| `psycopg` | `3.3.5` | PostgreSQL driver native. |
| `psycopg-binary` | `3.3.5` | C-extension prebuilt binary cho Windows x86_64. |
| `psycopg-pool` | `3.3.1` | Dedicated connection pooling cho TransactionManager và UoW (P1+). |
| `httpx` | `0.28.1` | HTTP client async hỗ trợ streaming SSE và API test client. |
| `pydantic` | `2.13.5` | Data validation và serialization cho domain envelopes & models (kế thừa từ M1). |
| `temporalio` | `1.32.0` | Kế thừa từ M1 cho regression suite. |
| `google-api-python-client` | `2.200.0` | Kế thừa từ M1 cho regression suite. |
| `google-auth-oauthlib` | `1.4.1` | Kế thừa từ M1 cho regression suite. |
| `pytest` | `9.1.1` | Test framework. |
| `pytest-asyncio` | `1.4.0` | Async testing engine. |
| `pytest-cov` | `7.1.0` | Báo cáo test coverage. |

---

## 3. Frontend Toolchain & Dependencies (src/controlplane/ui/)

Duy nhất **một package universe** tại `src/controlplane/ui/package.json` và `src/controlplane/ui/package-lock.json`. Tuyệt đối không tạo file lock ở root.

| Thư viện / Công cụ | Phiên bản Khóa Exact | Lý do Lựa chọn & Cơ sở Kỹ thuật |
| :--- | :--- | :--- |
| `react` | `18.3.1` | Bản phát hành ổn định dài hạn của React 18, tương thích 100% với AG Grid Community. |
| `react-dom` | `18.3.1` | Thư viện render DOM cho React 18. |
| `ag-grid-community` | `32.3.9` | Nhánh `v32-lts` maintained patch chính thức (theo dist-tags của AG Grid). Có tính ổn định cao nhất, đầy đủ tài liệu, không có breaking changes về theme và tương thích hoàn toàn kiến trúc bảng ADR-0007. |
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
3. **Domain Layer Purity**: Mọi module trong `src/controlplane/domain` cấm import bất kỳ framework ngoài nào (`fastapi`, `psycopg`, `temporalio`, `google`) hoặc mã `m1proof`.
4. **Advisory Lock ở P1**: Migration runner ở P1 phải dùng session-level advisory lock trên dedicated connection với bounded wait timeout.
