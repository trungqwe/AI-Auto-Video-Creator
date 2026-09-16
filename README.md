# AI Auto Video Creator

> Cập nhật hiện hành: M2-P1..P6 là `ACCEPTED / CLOSED`; M2-P7A correction đạt `READY_FOR_REVIEW` với source `6c3a52b` và GREEN evidence `run-m2-p7a-green-20260916224033`. Candidate trước tại `d5032eb` bị independent review từ chối về governance; evidence cũ được giữ nguyên. P7A chưa ACCEPTED/CLOSED; P7B/P8/P9 vẫn khóa, M3 và Phân hệ A `NOT AUTHORIZED`.

Hệ thống tự động hóa việc thu thập tin và media, tạo nhiều góc kể tiếng Anh, dựng video ngắn 61–70 giây và đồng bộ đầu ra lên cloud. Dự án được phát triển theo từng milestone có evidence gate; không coi việc chương trình chạy một lần là bằng chứng kiến trúc đã đạt.

## Trạng thái hiện hành

| Hạng mục | Trạng thái |
|---|---|
| M0 Design | `APPROVED` |
| M1 Evidence Prototype | `ACCEPTED / CLOSED` |
| G01 Temporal | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G04 Drive/OAuth | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G07 Compatibility | `SMOKE_COMPATIBILITY_PASS_M1_SCOPE` |
| M2 Control Plane | `M2-P1..P6_ACCEPTED_CLOSED; M2-P7A_IMPLEMENTATION_READY_FOR_REVIEW` |
| M3 / Module A | `NOT AUTHORIZED` |

Toàn bộ M1 đã được Người dùng chấp thuận tại checkpoint ngày 13-09-2026 (93 passed, 0 skipped). M2-P1..P6 đã được chấp thuận/đóng; P6 dùng corrected evidence `run-m2-p6-20260916084617`. P7A có GREEN evidence correction mới: accepted oracle 4/4, exact H01–H36 36/36, toàn bộ hồi quy PASS, secret scan sạch và hash DAG PASS. Đây là candidate chờ independent review, không phải acceptance. M3 và Phân hệ A tiếp tục `NOT AUTHORIZED`.

## Bắt đầu một phiên làm việc

Đọc theo thứ tự:

1. [HANDOFF.md](./HANDOFF.md) — trạng thái ngắn của phiên gần nhất.
2. [Checklist trước code](./docs/12-pre-code-checklist.md) — quyền và gate hiện hành.
3. [Roadmap](./docs/11-roadmap.md) — milestone và dependency.
4. [M2 implementation plan](./docs/milestones/m2-control-plane/implementation-plan.md) — package/gate đang được phép thực hiện.
5. [M2 toolchain lock](./docs/milestones/m2-control-plane/toolchain-lock.md) — phiên bản bắt buộc.

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

## Trạng thái M2-P1

Milestone M2-P1 (PostgreSQL Foundation, Raw SQL Migrations & Workspace/Identity/Session Foundation) đã được User chấp thuận plan sau independent re-audit HEAD `5ba3a1601f0e1402e54a82feb5b44fe94cda9197`. Có đúng 11 behavioral oracle importable. Correction R2 sau audit `2541c58a85c301c9499d7179f54b4f6607b2c524` dùng production migration để xác minh composite FK P1-006, chứng minh rollback side-effect P1-010, bổ sung crash-release P1-004, khóa `psycopg_pool.ConnectionPool` và exact fixture identity.

Trạng thái hiện hành: `M2-P1_ACCEPTED_CLOSED; M2-P2_RED_READY_FOR_REVIEW`. P2 full exact 11 Behavioral RED đã chạy trên PostgreSQL 18.6 Docker với `CREATEDB=true` và orphan=0; evidence chờ independent audit. Implementation P2 vẫn khóa. M3 và Phân hệ A tiếp tục bị khóa hoàn toàn (`NOT AUTHORIZED`).
