# Báo cáo bằng chứng IMPL-PLAN-CONVERGENCE

- Task: IMPL-PLAN-CONVERGENCE (planning_package), trigger INITIAL, cơ sở HEAD e613e7e1ba9eb7f35f225ff49f972b2836d9173a.
- Tệp tạo mới: `docs/implementation/convergence/plan.md`, `docs/implementation/convergence/slices.md` (9 slice CP-2B-DEPS, CP-2C-M2-REGRESSION, CP-2D-REGISTRY, CP-3-MIGRATIONS, CP-3B-STATE-MACHINE, CP-4-WIRING, CP-4B-UI-SHELL, CP-5-COMPLETION, CP-6-WORKFLOW), `docs/delivery-evidence/impl-plan-convergence/report.md`.
- Không sửa kế hoạch phân hệ, `docs/milestones/**/evidence/**`, `src/**`, `migrations/**`, `.ai-pm/**`.
- Nguồn đọc thêm: `docs/parallel-delivery/ownership-and-locks.yaml`, `tests/m2/test_p9_m2_exit_gate.py`, `docs/milestones/m2-control-plane/evidence/manifest.json` (chỉ đọc), `pyproject.toml`, `src/controlplane/pyproject.toml`, `src/controlplane/requirements.lock`, `src/controlplane/ui/package.json`, `src/controlplane/api/main.py`, `src/controlplane/application/orchestration/commit_completion.py`, `src/controlplane/infrastructure/db/migrations/` (0001–0008), `src/controlplane/infrastructure/evidence/ast_checker.py`.

## Mười kế hoạch phân hệ đã đọc

sha256 tính trên byte tệp `plan.md` trong worktree tại HEAD nêu trên.

| Phân hệ | Đường dẫn | sha256 |
| --- | --- | --- |
| A | `docs/implementation/a/plan.md` | 9e4890e7e80ca7f4a6ba0d41a81f5e25f7470c41c519b40a09fe67b8185e4b38 |
| B | `docs/implementation/b/plan.md` | 3103b516cab627fd064df30f8af358e025bbd2617eaedbc2f64ea08e0e034bfb |
| C | `docs/implementation/c/plan.md` | 0594e6bf6ba887bcc5f79d5a4fe13624714027faf89deb49a833dcecd0ebf197 |
| D | `docs/implementation/d/plan.md` | b03bfa87b78f4b2b6263b8776d903903c531b95852a9da5a738c234bba5eb9ac |
| E | `docs/implementation/e/plan.md` | 5964e271759fbbe97dacca12058424066b3dc28b3f670892657c2b63a25ac2e2 |
| F | `docs/implementation/f/plan.md` | 3d4240949670472c76349d83b7702a4ef294d2daf206a6e50b07646c6e6cf3fb |
| G | `docs/implementation/g/plan.md` | 8fc9b2c9ed4afc3b56401c337098ab38e579499710615c356f5e4d192c0abc45 |
| H | `docs/implementation/h/plan.md` | aba210d4573a61ff5a6f0967baab17ec326876ad3c20473b085e4cae334c15d9 |
| I | `docs/implementation/i/plan.md` | bfa2a1fa655c09c2290cddf0e1a586718665ca89b3b18af6bb538b3bd949cb79 |
| J | `docs/implementation/j/plan.md` | b196ef3869970e600bb71495a223d5db0d3356e1c456158193dc5b13bc1edbe9 |

## Yêu cầu hội tụ đã gom từ mỗi kế hoạch

Tổng cộng 106 yêu cầu gốc; ánh xạ chi tiết sang slice ở `plan.md` mục 2.

| Phân hệ | Yêu cầu đã gom | Nơi xử lý |
| --- | --- | --- |
| A | CONV-A-01..09 (9): migration, composition root, control API, UI shell, state machine, workflow, binding, catalog test, event | CP-3, PERSIST-A, CP-4, CP-4B, CP-3B, CP-6, CP-2D |
| B | REQ-B-CONV-01..09 (9): migration, adapter và UoW chung outbox, composition root, workflow, API và UI, registry, binding, catalog test, tài liệu | CP-3, PERSIST-B, CP-4, CP-4B, CP-6, CP-2D |
| C | CONV-C-01..09 (9): migration và FTS, MediaUsage cùng completion, API, UI, binding, registry, state machine, workflow, spec | CP-3, PERSIST-C, CP-5, CP-4, CP-4B, CP-3B, CP-6, CP-2D |
| D | CONV-D-01..11 (11): migration, composition root, API, UI, workflow, state machine, binding, registry, corpus, event, route J | CP-3, PERSIST-D, CP-4, CP-4B, CP-6, CP-3B, CP-2D |
| E | CONV-E-01..14 (14): migration, composition root và adapter thật, API, UI, workflow, state machine, binding, registry, corpus, event, route J, storage I, lockfile và FFmpeg, phân hệ F | CP-3, PERSIST-E, CP-4, ADAPT-E, CP-4B, CP-6, CP-3B, CP-2D, CP-2B |
| F | CONV-F-01..14 (14): như E cộng cấu hình J | CP-3, PERSIST-F, CP-4, ADAPT-F, CP-4B, CP-6, CP-3B, CP-2D, CP-2B |
| G | YC-HT-G-01..10 (10): migration, composition root và UoW completion, registry, state machine, workflow, API, event, UI, tài liệu, GrantClaims của A-18 | CP-3, PERSIST-G, CP-4, CP-5, CP-2D, CP-3B, CP-6, CP-4B |
| H | YC-HT-H-01..10 (10): ownership, composition root, UI shell, control API, index keyset, state machine, binding, workflow, packaging, catalog và e2e | CP-2D, CP-4, CP-4B, CP-3, CP-3B, CP-6, CP-2B |
| I | YC-HT-I-01..09 (9): migration, đăng ký gói storage, composition root, state machine, UI và API, workflow, binding F→I, event, catalog | CP-3, PERSIST-I, CP-2B, CP-4, CP-3B, CP-4B, CP-6, CP-2D |
| J | YC-HT-J-01..11 (11): migration và `effective_at`, composition root, binding, state machine, API và UI, workflow, event, adapter D/E, phiên bản `cryptography`, catalog, backlog | CP-3, PERSIST-J, CP-4, CP-2D, CP-3B, CP-4B, CP-6, CP-2B |

## Thư viện và runtime đã gom

- Đã khóa, giữ nguyên: fastapi, uvicorn, httpx, pydantic, psycopg, psycopg-pool, cryptography, tzdata, google-api-python-client, google-auth-oauthlib, pytest và các gói UI, mỗi mục `tên==phiên bản` ở `plan.md` mục 3.1.
- Đề xuất thêm (mục 3.2): `temporalio==1.32.0` (đề xuất duyệt ngay), `feedparser==6.0.14`, `trafilatura==2.2.0`, `jusText==3.0.2`, `Scrapy==2.19.0`, `playwright==1.63.0`, `pydantic-ai==2.43.0`, `instructor==1.17.0`, `av==18.1.0`, `faster-whisper==1.2.1`, `whisperx==3.8.6` (hoãn).
- Chưa ghim được nên không vào danh sách: OpenCV, build FFmpeg, test runner TypeScript, `keyring`, pgvector, HTTP client biên của A. Xung đột `cryptography` 46.0.5 và 50.0.1: đề xuất giữ hai universe độc lập, chờ user.

## Mục mở và danh sách chờ user

- `USER-CKPT-D9-D10` (thư viện, cách dựng lại runtime, ba giá trị FFmpeg, sha256 Temporal, digest PostgreSQL).
- OI-CV-01: `M2_ACCEPTED_SHA` chưa có trong tài liệu hiện hành; Orchestrator đọc bằng git khi lập lệnh cho CP-2C. User checkpoint M2 vẫn chưa ghi.
- PUC-G-02, PUC-J-03, YC-HT-I-04 (state machine) giữ nguyên chờ user. Không mục nào được ghi là đã duyệt; mọi mục `CP7-*` (tài nguyên thật, D5) nằm ngoài gói này.

## Lệnh kiểm

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| git diff --check | 0 | không output |
| probe bắt buộc của task (plan.md và slices.md) | 0 | không output |
| probe tổng hợp (chín id, kind, USER-CKPT-D9-D10, độ phủ mã yêu cầu, sha256 trong report) | 0 | không output |
| probe mã hóa và định dạng ba tệp | 0 | không output |

Interpreter: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
