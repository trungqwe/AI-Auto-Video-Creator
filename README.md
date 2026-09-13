# AI Auto Video Creator

Hệ thống tự động hóa việc thu thập tin và media, tạo nhiều góc kể tiếng Anh, dựng video ngắn 61–70 giây và đồng bộ đầu ra lên cloud. Dự án được phát triển theo từng milestone có evidence gate; không coi việc chương trình chạy một lần là bằng chứng kiến trúc đã đạt.

## Trạng thái hiện hành

| Hạng mục | Trạng thái |
|---|---|
| M0 Design | `APPROVED` |
| M1 Evidence Prototype | `ACCEPTED / CLOSED` |
| G01 Temporal | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G04 Drive/OAuth | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G07 Compatibility | `SMOKE_COMPATIBILITY_PASS_M1_SCOPE` |
| M2 Control Plane | `IMPLEMENTATION IN PROGRESS (M2-P0 ACCEPTED / CLOSED, M2-P1 AUTHORIZED)` |
| M3 / Module A | `NOT AUTHORIZED` |

Toàn bộ các work package M1 (`M1-P0 → M1-P6`) đã được Người dùng CHẤP THUẬN chính thức tại User Checkpoint ngày 13-09-2026 sau independent re-audit HEAD `08c857c`: M1 chuyển sang `ACCEPTED / CLOSED` (93 passed, 0 skipped, coverage 83%, Audit R5 + R5.1 ACCEPTED). M2-P0 đã được Người dùng CHẤP THUẬN chính thức (`ACCEPTED / CLOSED`) tại HEAD commit `d84c1d7`. M2-P1 được ủy quyền triển khai và đã hoàn tất hiệu chỉnh kế hoạch kỹ thuật (docs-only) trước Behavioral RED. Toàn bộ Milestone M3 và Phân hệ A tiếp tục bị khóa chặt (`NOT AUTHORIZED`).

## Bắt đầu một phiên làm việc

Đọc theo thứ tự:

1. [HANDOFF.md](./HANDOFF.md) — trạng thái ngắn của phiên gần nhất.
2. [Checklist trước code](./docs/12-pre-code-checklist.md) — quyền và gate hiện hành.
3. [Roadmap](./docs/11-roadmap.md) — milestone và dependency.
4. [M1 implementation plan](./docs/milestones/m1-proof/implementation-plan.md) — work package đang được phép thực hiện.
5. [M1-R1 version lock](./docs/milestones/m1-proof/version-lock.md) — phiên bản bắt buộc.

Chỉ đọc sâu contracts/ADR được work package hiện tại trích dẫn; không remap toàn bộ dự án nếu `HANDOFF` và tài liệu nguồn sự thật còn nhất quán.

## Tài liệu nền

- [Project charter](./docs/00-project-charter.md)
- [Product specification](./docs/01-product-spec.md)
- [Data model](./docs/02-data-model.md)
- [Quality requirements](./docs/03-quality-requirements.md)
- [Technology research](./docs/05-technology-research.md)
- [System map](./docs/06-system-map.md)
- [Data flow](./docs/07-data-flow.md)
- [Architecture](./docs/08-architecture.md)
- [ADR index](./docs/adr/README.md)
- [Contracts](./docs/09-contracts/README.md)
- [Test strategy](./docs/10-test-strategy.md)
- [Audit](./AUDIT.md)

## Quy tắc lưu vết

- `CHANGELOG.md` ghi tiến độ và thay đổi có giá trị lâu dài.
- `HANDOFF.md` chỉ giữ trạng thái ngắn cần cho phiên tiếp theo; thay nội dung cũ thay vì tích lũy nhật ký dài.
- Kết thúc mỗi phiên sửa đổi hoặc giai đoạn quan trọng: đồng bộ tài liệu, chạy kiểm tra phù hợp, commit theo Conventional Commits và push lên repository này.
- Không commit secret, token, credential, dữ liệu cá nhân, log chưa redacted hoặc artifact không rõ quyền sử dụng.

## Repository

Remote chính: <https://github.com/trungqwe/AI-Auto-Video-Creator>

## Trạng thái sau User Checkpoint M1 & Kích hoạt Milestone M2
Milestone M1 (`M1-P0 → M1-P6`) đã hoàn tất 100% và được Người dùng phê duyệt chính thức (`ACCEPTED / CLOSED`) với **93 passed, 0 skipped** tests, Audit R5 + R5.1 ACCEPTED. Milestone M2 chính thức chuyển sang `AUTHORIZED_FOR_PLANNING_AND_IMPLEMENTATION`. Milestone M3 và Phân hệ A tiếp tục `NOT AUTHORIZED`.

## Trạng thái Hoàn tất Milestone M2-P0
Milestone M2-P0 (Authorization Sync, Toolchain Lock, Evidence Protocol & Architecture Rules) đã được Người dùng CHẤP THUẬN chính thức (`ACCEPTED / CLOSED`) tại commit `d84c1d7`:
- Khóa chính xác 100% Backend (FastAPI 0.141.1 native SSE, Uvicorn 0.52.4, HTTPX 0.28.1, psycopg-pool 3.3.1, Pydantic 2.13.5; exact build-system version pins setuptools 75.8.0, wheel 0.45.1) và Frontend (Node v22.17.0 LTS, npm 10.9.2, React 18.3.1, AG Grid Community 32.3.9 v32-lts, Vite 6.2.0, Playwright 1.50.1).
- Single package universe tại `src/controlplane/ui/package.json` với machine-lock `packageManager: npm@10.9.2`, `engines`, `.nvmrc`, `.node-version`.
- Standard Python package tại `src/controlplane/pyproject.toml`, resolved graph tại `requirements.lock` & `uv.lock`. Chứng minh kép sạch: Proof A (Frozen environment install) và Proof B (Wheel clean install with `--no-deps`) qua dynamic uv resolver, không dùng `.pth` làm package gate foundation.
- AST boundary checker bảo vệ Domain Purity và chặn triệt để `m1proof.*`, `src.m1proof.*`.
- Evidence Validator hai tầng (Integrity + Semantic Profile Registry) trích xuất trực tiếp từ JUnit XML (`m2-p0-tests.xml`, `m1-regression.xml`) và `secret-scan.json`, chống triệt để false-PASS và chặn cross-package spoofing.
- Single-pipeline synthesis (`synthesizer.py`) bảo đảm toàn bộ bằng chứng được sinh ra tuyến tính, tất định và loại bỏ hash cycles.
- Toàn bộ **33/33 tests M2-P0 PASSED**; **93/93 tests hồi quy M1 PASSED**; 6/6 Package Gates PASSED; 0 secret leaks; xác thực provenance 1:1 tuyệt đối.

## Trạng thái Chuẩn bị M2-P1 (Hiệu chỉnh Kế hoạch Kỹ thuật)
Milestone M2-P1 (PostgreSQL Foundation, Raw SQL Migrations & Workspace/Identity/Session Foundation) đã được ủy quyền triển khai (`AUTHORIZED TO IMPLEMENT`) và hoàn tất 100% việc chuẩn hóa tài liệu đặc tả và kế hoạch thực thi (docs-only correction) trước Behavioral RED:
- Hoàn thiện 10 điểm kỹ thuật: Dùng disposable test database `m2_p1_test_<uuid>`, không parameterized schema; 8 tiêu chuẩn migration runner với bounded advisory lock timeout 5s; phân biệt AuthSession (`cp_auth_sessions`) với AppSession; composite FK DB-level invariants ngăn cross-workspace; SqlUnitOfWork sở hữu đúng 1 pooled connection và 1 DB transaction; loại bỏ chu trình tự tham chiếu evidence; đăng ký deterministic semantic profile; chốt 6 machine-readable gates trước RED (`GATE-P1-01` .. `GATE-P1-06`).
- Trạng thái hiện hành: `M2-P1_PLAN_READY_FOR_RED_REVIEW`. Dừng lại chờ Người dùng rà soát kế hoạch trước khi bắt đầu Behavioral RED. M3 và Phân hệ A tiếp tục bị khóa hoàn toàn (`NOT AUTHORIZED`).





