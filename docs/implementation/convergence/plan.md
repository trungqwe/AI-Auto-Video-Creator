# Kế hoạch hội tụ kỹ thuật — IMPL-PLAN-CONVERGENCE

- **Mã gói**: IMPL-PLAN-CONVERGENCE (planning_package)
- **Ngày lập**: 20/10/2026
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`) và chỉ thị user duyệt Phần B ngày 18/10/2026 (D0–D10).
- **Trạng thái**: kế hoạch; `PRODUCTION_ACTIVATION_BLOCKED` vẫn hiệu lực. Không push, không merge, không chạm main hay backup.
- **Cơ sở**: HEAD `e613e7e1ba9eb7f35f225ff49f972b2836d9173a`; migration cuối là `0008`; chưa có `src/main.py`; điểm dựng ứng dụng hiện có là `src/controlplane/api/main.py`.
- **Slice**: `docs/implementation/convergence/slices.md`. **Bằng chứng**: `docs/delivery-evidence/impl-plan-convergence/report.md`.
- **Sửa lần 2 (IMPL-PLAN-CONVERGENCE-FIX2)**: giữ nguyên mọi cạnh phụ thuộc của kế hoạch (mục 11.1); slice hay phần việc nằm ngoài phong bì không bị loại khỏi kế hoạch mà ghi `BLOCKED` hoặc `PENDING` kèm mã `BL-CV-*` (mục 12.1, BL-CV-01..BL-CV-15).

## 1. Phạm vi và nguyên tắc

Kế hoạch gom mọi mục «Yêu cầu gửi IMPL-PLAN-CONVERGENCE» của mười kế hoạch phân hệ (`docs/implementation/a` đến `j`) thành các slice hội tụ. Tài nguyên dùng chung (migration, composition root, lockfile, nguồn contract, registry, tài liệu quyền, `tests/m2`, `ui/dist`, state machine, control API) chỉ gói hội tụ hoặc dependency_slice được sửa, mỗi lúc một owner.

1. Mỗi slice chỉ sửa trong `ownedPaths` của nó, giữ `LOCK-CONVERGENCE` cùng khóa tài nguyên tương ứng (`docs/parallel-delivery/ownership-and-locks.yaml`).
2. `docs/milestones/**/evidence/**` là bằng chứng đã nghiệm thu, bất biến (`LOCK-ACCEPTED-EVIDENCE`); không slice nào sửa, kể cả manifest M2.
3. Không sửa kế hoạch phân hệ A–J; mâu thuẫn ghi thành mục mở.
4. Fake và fixture CP1 chỉ chứng minh logic, không đóng gate tài nguyên thật; việc cần Drive/OAuth, GPU, AI trả phí hoặc chạy 12 giờ thuộc CP7 sau khi user duyệt D5.
5. Import root là `src/`, không dùng tiền tố `src.`; không dựng cây trùng `src/storage`, `src/orchestration`, `src/ui`.
6. Slice hội tụ chạy lại lệnh kiểm của các gói phụ thuộc trực tiếp; slice dùng thư viện mới phụ thuộc `CP-2B-DEPS`; slice phụ thuộc `CP-2B-DEPS` khai thêm `USER-CKPT-D9-D10`.
7. Mục chưa được user duyệt ghi `pendingUserCheckpoint`, không ghi là đã duyệt.

## 2. Bảng gom yêu cầu «gửi IMPL-PLAN-CONVERGENCE»

Gom 106 yêu cầu gốc: A `CONV-A-01..09` (mục 10 của `a/plan.md`), B `REQ-B-CONV-01..09` (mục 11), C `CONV-C-01..09` (mục 10), D `CONV-D-01..11` (mục 10), E `CONV-E-01..14` (mục 10), F `CONV-F-01..14` (mục 10), G `YC-HT-G-01..10` (mục 9), H `YC-HT-H-01..10` (mục 9), I `YC-HT-I-01..09` (mục 9), J `YC-HT-J-01..11` (mục 9). Bảng dưới xếp theo slice xử lý; viết tắt `A-01` là `CONV-A-01`, `B-01` là `REQ-B-CONV-01`, `C-01`, `D-01`, `E-01`, `F-01` tương tự, `G-01` là `YC-HT-G-01`, `H-01`, `I-01`, `J-01` tương tự. Mỗi mã xuất hiện ít nhất một lần.

`PERSIST-<X>` là slice adapter PostgreSQL của phân hệ X (A–G, I, J; H không thêm bảng), Control mở sau khi CP-3 đạt Auditor PASS (mục 5.3). `ADAPT-E`, `ADAPT-F` là adapter FFmpeg, aligner, TTS thật, mở sau CP-2B và D9 (mục 4). Hai nhóm này không nằm trong slices.md.

| Slice | Yêu cầu được xử lý |
| --- | --- |
| `CP-2B-DEPS` | E-13, F-13 (lockfile, FFmpeg); H-09, I-02 (đăng ký gói); J-09 (phiên bản `cryptography`) |
| `CP-2C-M2-REGRESSION` | sửa hai phép kiểm của `tests/m2` (D2) để CP-3 và CP-4B không làm M2 hỏng |
| `CP-2D-REGISTRY` | A-07, A-08; B-06..B-09; C-05, C-06, C-09; D-07, D-08, D-09; E-07, E-08, E-09, E-14; F-07, F-08, F-09, F-14; G-03, G-09; H-01, H-07, H-10; I-07, I-09; J-03, J-10 |
| `CP-3-MIGRATIONS` | A-01, B-01, C-01, D-01, E-01, F-01, G-01, H-05, I-01, J-01 |
| `CP-3B-STATE-MACHINE` | A-05, C-07, D-06, E-06, F-06, G-04, H-06, I-04, J-04 |
| `CP-4-WIRING` | A-02, A-03, A-09; B-03, B-05 (API); C-03; D-02, D-03, D-10, D-11; E-02, E-03, E-10, E-11, E-12; F-02, F-03, F-10, F-11, F-12; G-02, G-06, G-07; H-02, H-04; I-03, I-05 (API), I-08; J-02, J-05 (API), J-07, J-08 |
| `CP-4B-UI-SHELL` | A-04; B-05 (UI); C-04; D-04; E-04; F-04; G-08; H-03, H-10 (e2e); I-05 (UI); J-05 (UI) |
| `CP-5-COMPLETION` | C-02 (MediaUsage cùng completion); G-02 (UoW completion) |
| `CP-6-WORKFLOW` | A-06; B-04; C-08; D-05; E-05; F-05; G-05, G-10; H-08; I-06; J-06 |
| `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J` | B-02 và phần adapter PostgreSQL của A-01, C-01, D-01, E-01, F-01, G-01, I-01, J-01 (gồm ánh xạ cột `effective_at` của J-01) |
| `ADAPT-E`, `ADAPT-F` | phần adapter thật của E-02, F-02 |
| backlog | J-11 (J-BL-01..03) |

Ghi chú: C-02 và G-02 cùng đòi unit of work completion nên gộp ở CP-5. Các mục `CP7-*` (tài nguyên thật) của từng kế hoạch không thuộc gói này, xem mục 12. State machine của G, H, I, J giữ nguyên chờ user (mục 12); CP-3B chỉ xác nhận và ghi quyết định.

## 3. Danh sách thư viện hợp nhất (D10)

Quy tắc: mỗi mục là `tên==phiên bản` cố định, không dùng `latest`, không dùng dải phiên bản. Phiên bản lấy từ lockfile hiện hành hoặc `docs/05-technology-research.md` và được Control xác minh lại trên registry tại `USER-CKPT-D9-D10`. Giấy phép nhóm đã khóa lấy từ metadata gói; Control đối chiếu bằng `uv pip show` và `npm ls` ở checkpoint, nếu sai khác thì bảng này không có hiệu lực. Slice phân hệ A–J không thêm thư viện (đã xác nhận ở mục D10 của từng kế hoạch).

### 3.1. Đã khóa, giữ nguyên

| Thư viện (`tên==phiên bản`) | Giấy phép | Mục đích | Phân hệ dùng |
| --- | --- | --- | --- |
| `fastapi==0.141.1` | MIT | API control, route module | H và mọi route phân hệ |
| `uvicorn==0.52.4` | BSD-3-Clause | chạy ASGI loopback TLS | H |
| `httpx==0.28.1` | BSD-3-Clause | TestClient, HTTP client | H, A (biên) |
| `pydantic==2.13.5` | MIT | schema API ở biên | H (domain A–J không dùng) |
| `psycopg[binary,pool]==3.3.5` (kèm `psycopg-pool==3.3.1`) | LGPL-3.0 | PostgreSQL | A–J (persistence) |
| `cryptography==46.0.5` | Apache-2.0 hoặc BSD-3-Clause | AES-256-GCM cho bundle secret | J (xem 3.3) |
| `tzdata==2026.4` | Apache-2.0 | dữ liệu múi giờ do caller truyền | J, G, I |
| `google-api-python-client==2.200.0` | Apache-2.0 | Drive API (CP7) | I, J |
| `google-auth-oauthlib==1.4.1` | Apache-2.0 | OAuth (CP7) | J |
| `pytest==9.1.1`, `pytest-asyncio==1.4.0`, `pytest-cov==7.1.0` | MIT | kiểm thử | mọi phân hệ |
| `react==18.3.1`, `react-dom==18.3.1` | MIT | UI | H |
| `ag-grid-community==32.3.9`, `ag-grid-react==32.3.9` | MIT | lưới dữ liệu | H |
| `vite==6.2.0`, `@vitejs/plugin-react==4.3.4` | MIT | build UI | H |
| `typescript==5.7.3`, `@types/react==18.3.18`, `@types/react-dom==18.3.5` | Apache-2.0 và MIT | kiểu TypeScript | H |
| `@playwright/test==1.50.1` | Apache-2.0 | E2E trình duyệt | H |

### 3.2. Đề xuất thêm mới (cần user duyệt ở `USER-CKPT-D9-D10`)

| Thư viện (`tên==phiên bản`) | Giấy phép | Mục đích | Phân hệ dùng | Đề xuất của Control |
| --- | --- | --- | --- | --- |
| `temporalio==1.32.0` | MIT | SDK workflow cho CP-6 (ADR-0003); đã khóa ở `pyproject.toml` gốc, chưa có trong `src/controlplane` | G | duyệt ngay |
| `feedparser==6.0.14` | BSD-2-Clause | parse RSS và Atom | A | hoãn tới CP7-A-01 |
| `trafilatura==2.2.0` | Apache-2.0 | extractor nội dung chính | A | hoãn tới CP7-A-01 |
| `jusText==3.0.2` | BSD-2-Clause | đối chiếu boilerplate | A | hoãn tới CP7-A-01 |
| `Scrapy==2.19.0` | BSD-3-Clause | crawler nhiều nguồn | A | hoãn, chỉ khi POC chứng minh cần |
| `playwright==1.63.0` | Apache-2.0 | trang động (cần browser binary, đổi cách dựng runtime) | A | hoãn |
| `pydantic-ai==2.43.0` | MIT | output có kiểu ở biên adapter AI | D | hoãn; chọn một trong hai sau POC |
| `instructor==1.17.0` | MIT | phương án thay `pydantic-ai` | D | hoãn |
| `av==18.1.0` | BSD-3-Clause | đọc frame và timestamp trong tiến trình | E, F | hoãn tới CP7-E-04 hoặc CP7-F-02 |
| `faster-whisper==1.2.1` | MIT | transcript và timestamp | E | hoãn tới TECH-POC-005 |
| `whisperx==3.8.6` | BSD-2-Clause | forced alignment từng từ | E | hoãn tới TECH-POC-005 |

Phiên bản các mục A, D, E lấy từ `docs/05-technology-research.md` và phải được Control xác minh lại trên registry ở checkpoint. Đề xuất của Control: chỉ duyệt ngay `temporalio==1.32.0` vì mọi slice từ CP-2B đến CP-6 không import gói nào khác; các gói còn lại chỉ vào lockfile khi POC hoặc CP7 chứng minh cần, bằng dependency_slice riêng. Quyết định thuộc user.

### 3.3. Phiên bản `cryptography`

`src/controlplane/pyproject.toml` và `requirements.lock` khóa `cryptography==46.0.5` (M2 xanh trên bản này); `uv.lock` gốc (proof M1) ghi `50.0.1` (YC-HT-J-09). Đề xuất: giữ hai universe độc lập, mỗi bên một phiên bản cố định, không nâng `46.0.5` và không đổi M1-R1; `CP-2B-DEPS` ghi quyết định vào report. Nếu user chọn thống nhất về một phiên bản thì dựng lại runtime (mục 4) và chạy lại `tests/m2`.

### 3.4. Chưa đủ điều kiện (không có phiên bản cố định đã xác minh)

Các mục sau không nằm trong danh sách duyệt vì chưa ghim được `tên==phiên bản`: OpenCV (tên gói và wheel chưa đối chiếu), build FFmpeg (TECH-OPEN-012, ghim ở mục 4 bằng sha256 archive), test runner TypeScript và thư viện render component (PUC-H-05), `keyring` hoặc thư viện Credential Manager (PUC-J-07), adapter pgvector (ADR-0002), HTTP client cho fetch biên của A (IMPL-PLAN-A-OPEN-001). Mỗi mục chỉ vào danh sách khi Control xác minh phiên bản trên registry. Đã loại theo mục D10 của kế hoạch A, D, E, F: RSSHub, Mozilla Readability, Newspaper3k, `ffmpeg-python`, MoviePy, Remotion, `pyloudnorm`, Coqui TTS, MeloTTS, LiteLLM, LangChain, vLLM, Sentence Transformers.

## 4. Dựng lại runtime khoá (D9)

Control (không phải Worker) dựng và kiểm runtime. Chạy một lần sau khi user duyệt `USER-CKPT-D9-D10`, rồi chạy lại mỗi khi hash của `pyproject.toml`, `uv.lock`, `src/controlplane/requirements.lock` hoặc `src/controlplane/ui/package-lock.json` đổi (tức sau `CP-2B-DEPS`). Phải xong trước khi dispatch CP-4B (cần Node) và mọi slice dùng thư viện mới. Nơi đặt: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/<8 ký tự đầu của sha256 gộp bốn lockfile>/`, ngoài cây Git, không commit. Cú pháp `uv` dưới đây là GIẢ ĐỊNH; Control đối chiếu bằng `uv --help` ở checkpoint trước khi chạy.

| Bước | Lệnh hoặc hành động | Kiểm hash và kết quả mong đợi |
| --- | --- | --- |
| R1 Công cụ | `uv --version`, `node --version`, `npm --version` | đúng `0.12.13`, `v22.17.0`, `10.9.2` (khớp `.nvmrc` và `engines`) |
| R2 Python venv | `uv venv --python 3.13.15 <runtime>/venv` | `python --version` ra `3.13.15` |
| R3 Gói Python | `uv sync --frozen --no-install-project` với `UV_PROJECT_ENVIRONMENT=<runtime>/venv` (nhóm dev cho pytest), rồi `uv pip sync --require-hashes src/controlplane/requirements.lock` | `uv.lock` có sha256 từng wheel; `requirements.lock` hiện chưa có hash nên `CP-2B-DEPS` tái sinh bằng `uv pip compile src/controlplane/pyproject.toml --generate-hashes`; `uv pip freeze` so với hai lockfile không lệch |
| R4 node_modules UI | sao chép `src/controlplane/ui` (không `node_modules`, không `dist`) vào `<runtime>/ui/`, chạy `npm ci` | `npm ci` kiểm `integrity` trong `package-lock.json`; `npm ls --depth=0` khớp phiên bản cố định của `package.json` |
| R5 Nối vào worktree | tạo junction `src/controlplane/ui/node_modules` trỏ `<runtime>/ui/node_modules`; thêm `node_modules/` vào `.git/info/exclude` của worktree | `git status` không liệt kê `node_modules` |
| R6 FFmpeg | đặt build đã duyệt vào `<runtime>/ffmpeg/` | sha256 archive khớp giá trị user duyệt; `ffmpeg -version` và `-buildconf` lưu vào `runtime-manifest.json` (license LGPL hoặc GPL, có `libass`) |
| R7 Temporal | đặt `temporal-server.exe` bản `1.31.2` vào `<runtime>/temporal/`; SDK `temporalio==1.32.0` nằm trong venv | sha256 binary khớp bản phát hành chính thức; chỉ chạy khi cần (CP7-G-03), loopback `7233` |
| R8 PostgreSQL | container Docker `postgres:18.6` ghim digest, cổng `57027`, user `m2test` có `CREATEDB` (đúng DSN mặc định `postgresql://m2test:m2test@127.0.0.1:57027/postgres` của `tests/m2`) | `SELECT version()` chứa `18.6`; giữ khóa `LOCK-POSTGRES-TEST-DB` khi chạy |
| R9 Tái lập | xuất `src/controlplane/ui` ở commit M2 đã nghiệm thu vào `<runtime>/ui/`, `npm run build`, so hash bốn tệp `ui/dist` với manifest M2; chạy `python -m pytest tests/m2 -q -p no:cacheprovider` | bốn hash khớp manifest và M2 xanh; nếu lệch thì STOP, ghi bằng chứng, không sửa manifest |
| R10 Ghi nhận | ghi `<runtime>/runtime-manifest.json` | chứa sha256 bốn lockfile, phiên bản công cụ, digest PostgreSQL, sha256 FFmpeg và Temporal |

Ba giá trị chưa có trong tài liệu hiện hành, user phải cung cấp ở checkpoint: build FFmpeg (tên archive và sha256, TECH-OPEN-012), sha256 binary Temporal 1.31.2, digest image PostgreSQL 18.6. Tới khi có, slice cần FFmpeg (`ADAPT-E`, `ADAPT-F`) và replay Temporal thật bị chặn (`BLOCKED`); CP-2C, CP-3, CP-5 chỉ cần PostgreSQL harness của M2 và không phụ thuộc ba giá trị này. Giá trị đã biết nằm trong `tools/runtime/runtime.lock.json` do `CP-2B-DEPS` ghi; giá trị thiếu ghi `null` kèm `status: BLOCKED`, không bịa. Cấu trúc tệp: `versions` (đúng sáu khóa `python`, `uv`, `node`, `npm`, `postgresql`, `temporal_server`) và `pins` (đúng ba khóa `ffmpeg`, `temporal_server_binary`, `postgresql_image`, mỗi khóa có `sha256` là hex 64 ký tự kèm `status` = `PINNED`, hoặc `null` kèm `BLOCKED`); probe `json` trong `testCommands` của `CP-2B-DEPS` kiểm đúng cấu trúc này.

## 5. Migration từ 0009 (CP-3)

### 5.1. Quy tắc

- Một owner duy nhất: slice `CP-3-MIGRATIONS` giữ `LOCK-MIGRATION-SEQUENCE`. Không slice phân hệ nào tạo migration; số mới sau `0018` chỉ qua slice hội tụ mới.
- Số thứ tự liên tục từ `0009`, không bỏ số, không dùng lại số. Mỗi tệp `NNNN_<tên>.sql` đi kèm `NNNN_<têên>.rollback.sql` (như `0001`..`0008`); rollback chỉ gỡ đối tượng do chính migration đó tạo và chạy theo thứ tự ngược.
- Thứ tự theo phụ thuộc dữ liệu: mở rộng bảng đã có của J, I, G trước (các phân hệ khác tham chiếu), rồi A trước B (B tham chiếu `collected_document_package`), B trước D, D trước E, E trước F, H cuối (chỉ index).
- Bảng lịch sử là append-only (chặn UPDATE và DELETE bằng trigger theo mẫu migration hiện có); mọi khóa duy nhất và index nêu trong kế hoạch phân hệ phải có trong đúng migration tương ứng.
- `recovery_epoch` đổi sang `text` opaque (D8-G-03, D8-I-04) trong 0010 và 0011; adapter so sánh bằng `str()`.
- Không sửa `MigrationRunner`; không dùng `CREATE INDEX CONCURRENTLY` vì GIẢ ĐỊNH runner chạy mỗi migration trong một giao dịch (slice kiểm lại).

### 5.2. Bảng migration

| Số | Tệp (kèm `.rollback.sql`) | Nguồn yêu cầu | Nội dung |
| --- | --- | --- | --- |
| 0009 | `0009_config_security_extensions` | YC-HT-J-01 | `cp_external_accounts`, `cp_provider_capacity_snapshots`, `cp_capacity_reservations` (có expiry), `cp_cost_records`, `cp_audit_records` append-only; thêm credential version và revocation version cho `cp_secret_handles`; CHECK `scope_kind` của `cp_config_revisions`. Cột `effective_at` đã có từ 0004, adapter ánh xạ vào `EffectiveConfigRevision`, không tạo migration |
| 0010 | `0010_storage_meta_extensions` | YC-HT-I-01 | `cp_artifact_versions`: `intended_storage_class`, `producer_operation_ref`, `lineage_refs`; upload receipt (có `OUTCOME_UNKNOWN`); lease materialization; revision placement và working set policy; `cp_cleanup_authorizations.recovery_epoch` sang text; trường CT-STO-002 còn thiếu của `cp_artifact_locations` |
| 0011 | `0011_orchestration_extensions` | YC-HT-G-01 | bảng grant; cột `cp_stage_runs` (`stage_type`, `input_refs`, `dependency_refs`, `wait_reason`, `problem`, mốc thời gian, `superseded_by`); `cp_video_jobs` (`wait_reason`, parent và prior variant refs); trường CT-ORC-009 còn thiếu của `cp_completion_ledger`; receipt, cleanup eligibility, app session, lý do dừng batch; `recovery_epoch` sang text |
| 0012 | `0012_source_ingestion` | CONV-A-01 | source, định danh locator và tombstone, source_candidate, collection_run (unique workspace, source, business_date, periodic), collection_attempt, collection_checkpoint, fetch_observation, collected_document_package; index theo `a/plan.md` |
| 0013 | `0013_ingestion` | REQ-B-CONV-01 | articles, article_revisions, collected_document_resolutions, dedup_evidence, events, event_link_candidates, event_updates, event_update_candidates; dùng outbox của 0003 |
| 0014 | `0014_catalog` | CONV-C-01 | media_assets, media_provenance, media_renditions, hooks, hook_revisions, media_usage (`usage_kind` tách production và technical); index FTS. Không có pgvector (D8-CV-02) |
| 0015 | `0015_creative` | CONV-D-01 | production_snapshot (unique `snapshot_id`, bất biến), content_analysis, story_angle_set, story_angle, script_version, production_plan, variant_validation, output_metadata, ai_invocation_record, receipt; append-only |
| 0016 | `0016_voice` | CONV-E-01 | processed_media, image_safety_assessment, voice_track, word_timing, timing_validation_report, tts_invocation_record, language_evidence, audio_bed_result, probe_report, analysis_result, receipt; unique `voice_hash` và `timing_artifact_ref` |
| 0017 | `0017_render` | CONV-F-01 | render_preset_revision, render_package, package_validation_report, render_attempt, quality_report, quality_gate_result, video_output, operation_receipt; unique `package_fingerprint`, `render_attempt_id`, `output_artifact_ref` |
| 0018 | `0018_control_ui_indexes` | YC-HT-H-05 | index keyset `(workspace_id, created_at DESC, id DESC)` cho `cp_production_batches` và `cp_video_jobs`, `(workspace_id, accepted_at DESC, receipt_id DESC)` cho `cp_command_receipts`; không thêm bảng |

### 5.3. Kiểm và slice sau CP-3

Kiểm trên cơ sở dữ liệu dùng một lần (PostgreSQL 18.6, `LOCK-POSTGRES-TEST-DB`): `migrate_up` tới 18, `migrate_down` về rỗng, `migrate_up` lại, danh sách phiên bản là `[1..18]`; mọi bảng và cột ở bảng trên tồn tại; bảng append-only từ chối UPDATE; `recovery_epoch` là text. Sau khi CP-3 đạt Auditor PASS, Control mở chín slice `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J`. Mỗi slice có ownedPaths nằm trong phân hệ (`src/<phân hệ>/persistence/**`, hoặc adapter trong `infrastructure/db/<gói>` của G, I, J, cùng test PostgreSQL), dependsOn `CP-3-MIGRATIONS`, khóa của phân hệ, lệnh kiểm chạy trên PostgreSQL dùng một lần; riêng `PERSIST-J` đọc cột `effective_at` rồi dựng `EffectiveConfigRevision(revision, effective_at)` khi gọi `resolve_bundle` (F1 của IMPL-PLAN-J). Các slice này do Control biên dịch từ kế hoạch này, không nằm trong slices.md.

## 6. Wiring vào composition root, route và event (CP-4)

- **Composition root**: `src/controlplane/api/main.py` (`create_app` hiện dựng router `session`, `sse`, `control` và service của H) và `src/main.py` (chưa có; CP-4 tạo mới, chỉ đọc cấu hình, dựng `TransactionManager`, gọi hàm wiring rồi `create_app`). CP-2D thêm mẫu `src/controlplane/api/wiring/**` vào `PATH-COMPOSITION-ROOT`; CP-4 tạo mỗi phân hệ một mô-đun `api/wiring/<phân hệ>.py` với `build_<phân hệ>_services(manager, config)` trả service gắn vào `app.state`. Phân hệ nhận phụ thuộc qua port, không import chéo; không dùng tiền tố `src.`.
- **Control API** (`LOCK-CONTROL-API`): mount `build_listing_router` và `build_metadata_router` của `api/routes/modules/` (H-08, H-09); `control.py` phân trang keyset bằng `ListQuery` thay `next_cursor: None` và `LIMIT 100`; thêm query CT-API-002 còn thiếu (sources, articles, events, media, hooks, stage runs, sessions, logs, capabilities) và lệnh CT-API-003..006 (`RegisterSource`, `UpdateSourceMetadata`, `RemoveSource`, `RestoreSource`, `TestSource`, `ImportVisualHook`, `ImportAudioHook`, `StartProductionBatch`, `RunDebugStage`, `RetryStage`, `CreateNewVariant`, `RegenerateFromStage`, `PublishConfigurationRevision`, `UpdateSecret` chỉ ghi, `TestExternalAccount`, `EnableExternalAccount`, `DisableExternalAccount`). Lệnh trả receipt `accepted` khác trạng thái thực thi; lỗi theo ProblemDetail D8-H-06; service do phân hệ chủ sở hữu cung cấp, H chỉ trình bày. `control_api_queries.py` và `control_api_commands.py` nằm trong ownedPaths của CP-4, nên việc bỏ `LIMIT 100` (`control_api_queries.py` dòng 33, 92, 118, 147) và `next_cursor: None` (`control.py` dòng 23, 45, 81, 103) phải được chứng minh bằng test PostgreSQL thật trên `PostgresControlQueries` (không chỉ bằng service giả của `create_app`) và bằng probe đọc tệp; nếu phong bì lúc biên dịch không bao phủ hai tệp này thì phần phân trang là `BLOCKED` theo BL-CV-12 và không được tuyên bố đã làm.
- **Outbox và event**: đăng ký với publisher chung và `STREAM_EVENT_KINDS` các event của A (10), B (4), D (6), E (4), F (`RenderCompleted`, `OutputQualityChecked`), G (8), I (`ArtifactLocationVerified`, `CleanupCompleted`), J (config revision, account, secret); payload qua `ensure_safe_event_payload`. Artifact của E và F khai qua CT-STO-001 theo `i-artifact-version.json`; F lấy preset và tool capability từ `ConfigRevision`, không nhận secret.
- **Route J cho D và E**: `RoutedInvocationService` (J-18) là adapter cho `ProviderRoutePort`, `AIInvocationPort` (D), `VoiceRoutePort`, `TtsEnginePort` (E); `controlplane.config.router.ProviderRouter` giữ vai trò dispatch mức thấp. Thay `DEFAULT_APPROVED_ENDPOINTS` có host `mock-9router` trong `src/controlplane/config/adapter.py` bằng danh sách từ cấu hình; đường dẫn secret store, SQLite journal và staging root lấy từ cấu hình J.
- **Đóng gói**: `CP-2B-DEPS` tạo ba `__init__.py` rỗng cho `controlplane.api.routes.modules`, `controlplane.api.wiring`, `controlplane.application.orchestration.workflows` và khai chúng cùng `controlplane.infrastructure.storage` trong `src/controlplane/pyproject.toml` (YC-HT-H-09, YC-HT-I-02); CP-4 đến CP-6 không tạo `__init__.py` mới. Ba `__init__.py` nằm trong ownedPaths của `CP-2B-DEPS` (`api/routes/modules`, `api/wiring`, `application/orchestration/workflows`); `infrastructure/storage/__init__.py` đã có sẵn. Không có gói `controlplane.workflows` ở `src/controlplane/workflows`: mã workflow nằm ở `application/orchestration/workflows` (mục 10). Mỗi gói mới phải khai ở cả `packages` và `package-dir`, và probe `tomllib` trong `testCommands` của `CP-2B-DEPS` kiểm điều đó.
- **Kiểm**: chạy lại test của gói phụ thuộc trực tiếp (mọi `PERSIST-*`, A-17, B-10, C-07, D-17, E-19, F-21, H-08, H-09, J-18) và `tests/m2`; test mới dựng `create_app` với service giả, mọi route lệnh yêu cầu `Idempotency-Key` hoặc `If-Match`, không có route đọc lại secret. Thêm test PostgreSQL 18.6 dùng một lần gọi `PostgresControlQueries` với hơn 100 receipt, batch và job: trang đầu có `next_cursor` khác `None`, đi hết các trang thì đủ mọi dòng, không lặp, không sót (cần index keyset của migration `0018`); `control_api_queries.py` không còn `LIMIT 100` và `control.py` không còn `next_cursor: None`.

## 7. UI shell và dựng lại `ui/dist` (CP-4B)

- **Nối màn hình** (`LOCK-UI-SHELL`, `LOCK-SRC-CONTROL-UI`): sửa `src/controlplane/ui/src/App.tsx`, `index.css`, `api/client.ts`, `components/OperationsGrid.tsx`, `BatchesGrid.tsx`, `JobsGrid.tsx`, `types/api.ts`; nối `StatusPill`, `ErrorHoverDetail`, `screenRegistry`, `streamEventKinds`, `boundedEventDeduper` (H-10..H-15) vào shell; thay logic pill ở `OperationsGrid.tsx` (dòng 27–34), danh sách `eventKinds` ở `client.ts` (dòng 179–196) và `Set` ở `client.ts` dòng 143 cùng `App.tsx` dòng 29; thêm CSS `pill-waiting`, `pill-outcome-unknown`, `pill-unknown`; mở rộng `OperationItem`, `JobItem`.
- **Đường kiểm thử (`handleTriggerTestError`, `/test-driver`)**: yêu cầu gốc (YC-HT-H-03, GAP-H-06) là gỡ hoặc khóa nút `handleTriggerTestError` (`App.tsx` dòng 151–164) và đường `/test-driver/issue-capability` (`client.ts` dòng 67–95). Trong cây hiện hành việc này chưa làm được trong phong bì của CP-4B vì: (1) nút nằm ở `components/Header.tsx` (prop bắt buộc `onOpenTestError`, `data-testid="test-error-modal-btn"`), tệp này ngoài ownedPaths; (2) hai spec M2 giữ nguyên byte `tests/m2/e2e/safe-error-modal.spec.ts` và `tests/m2/e2e/performance-budget.spec.ts` bấm nút đó, còn `tests/m2/e2e/auth-helper.ts`, `tests/m2/e2e/operations-sse.spec.ts` và `src/controlplane/ui/playwright.config.ts` dùng `/test-driver`; (3) đường cấp phiên cho bản sản xuất chưa có (PUC-H-06, CP7-H-05). Vì vậy việc này ghi `BL-CV-13` (BLOCKED): Worker CP-4B không gỡ và không khóa, giữ `onOpenTestError` ở `App.tsx` và đường `/test-driver/issue-capability` ở `client.ts`, và ghi BLOCKED vào report. Kích hoạt sản xuất vẫn bị chặn (`PRODUCTION_ACTIVATION_BLOCKED`) nên chưa có bản sản xuất nào dùng `dist` này.
- **Màn hình theo phân hệ**: mỗi màn hình đổi `backendStatus` từ `pending_module` sang sẵn sàng chỉ khi route tương ứng của CP-4 tồn tại: Source và CollectionRun (A), tìm kiếm bài và disposition (B), media, hook, rendition, safety (C), snapshot, angle, script, plan, variant, trace (D), voice, word timing, báo cáo (E), preset, render package, attempt, gate QC, bốn mốc (F), batch, job, stage, session, log (G), upload, verify, cleanup (I), config revision, tài khoản, cập nhật secret chỉ ghi, chi phí (J). Trường sửa được theo D8-H-05; `article_body`, `script`, `secret` không bao giờ được cấp.
- **Dựng lại `ui/dist`**: chạy `npm run build` (`tsc && vite build`) bằng Node và `node_modules` của runtime D9 (mục 4, R4, R5); xóa ba tệp băm cũ (`index-CNmdI0B1.css`, `index-Dd0WysB0.js`, `index-Dd0WysB0.js.map`), thêm tệp băm mới và `index.html`. Slice khai `allowLarge: true` chỉ cho `src/controlplane/ui/dist/**` (tên băm đổi, tệp `.map` có thể lớn hơn 1024 KB); các tệp khác vẫn bị giới hạn 1024 KB. Người tạo diff `dist/**` là Worker của `CP-4B-UI-SHELL` (chạy `npm run build`, xóa ba tệp băm cũ nếu còn sót, commit cùng mã nguồn); Control không tạo hay sửa tay `dist`, chỉ chạy `npm run test:e2e` và ghi bằng chứng. Probe `dist` (mọi tệp `index.html` tham chiếu tồn tại và ba tệp băm cũ đã xóa) nằm trong `testCommands` của slice.
- **E2E**: năm spec M2 trong `tests/m2/e2e/` giữ nguyên byte; spec mới đặt tên `tests/m2/e2e/cp4b-<màn hình>.spec.ts`. `npm run test:e2e` (cần PostgreSQL và Chromium của D9) là cổng do Control chạy và ghi bằng chứng, không nằm trong `testCommands` của Worker.
- **Kiểm Worker**: `npm run build` exit 0; pytest tĩnh `tests/unit/control_ui` (gồm guard H-16: không XSS sink, không secret, không endpoint cấm); probe xác nhận mọi tệp mà `dist/index.html` tham chiếu tồn tại; bốn probe đọc tệp nguồn (không chạy trình duyệt): (a) `App.tsx` nối `boundedEventDeduper` và `screenRegistry`, không còn `new Set`, còn `onOpenTestError=` (BL-CV-13); (b) `client.ts` dùng `streamEventKinds`, không còn danh sách `const eventKinds = [` và `new Set<string>`, còn `/test-driver/issue-capability` (BL-CV-13); (c) `OperationsGrid.tsx` dùng `StatusPill` hoặc `presentStatus` và không còn `pill-accepted`, `index.css` có `.pill-waiting`, `.pill-outcome-unknown`, `.pill-unknown`; (d) `types/api.ts` có các trường `progress`, `wait_reason`, `started_at`, `updated_at`, `finished_at`, `problem` và `JobItem` có trường chứa `config_revision`. Cả bốn nằm trong `testCommands` của slice.

## 8. Sửa hai phép kiểm của `tests/m2` (D2, CP-2C)

Hội tụ làm hai phép kiểm của M2 hỏng có chủ đích: thêm migration `0009..0018` và dựng lại `ui/dist` cùng spec mới trong `tests/m2/e2e`. Chỉ đúng hai phép kiểm trong `tests/m2/test_p9_m2_exit_gate.py` được sửa; mọi tệp test khác của `tests/m2` giữ nguyên byte.

| Phép kiểm | Vị trí hiện tại | Vì sao hỏng | Cách sửa |
| --- | --- | --- | --- |
| Đúng 8 migration | `test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db`: `len(applied) == 8`, danh sách `[1..8]` (dòng 235–236) và `len(reapplied) == 8` (dòng 250–251) | sau CP-3 có 18 migration | đếm tệp `NNNN_*.sql` không phải rollback làm giá trị N; khẳng định phiên bản áp dụng là `[1..N]` và `len == N` cho cả hai lần `migrate_up`; thêm khẳng định tám migration đầu: tên và sha256 của 16 tệp (`0001`..`0008` cùng rollback) bằng blob tại `M2_ACCEPTED_SHA` |
| Hash `ui/dist` và `tests/m2/e2e` trong manifest | `test_tst_m2_p9_001_m2_manifest_and_gate_evaluation` gọi `validate_manifest_file`, hash mọi artifact với tệp trong cây làm việc; manifest có 4 tệp `src/controlplane/ui/dist/**` và 5 tệp `tests/m2/e2e/*` | CP-4B dựng lại `dist` (tên băm đổi) | trong `validate_manifest_dict` thêm tham số `baseline_commit` và `baseline_prefixes` (`src/controlplane/ui/dist/`, `tests/m2/e2e/`); artifact thuộc tiền tố được so `sha256` trong manifest với sha256 của `git show <baseline_commit>:<đường dẫn>`; artifact khác vẫn so với cây làm việc; test `002`, ca fake và ca self-reference dùng mặc định `None` |

Nguyên tắc: giữ bằng chứng M2 bất biến. Không sửa `docs/milestones/m2-control-plane/evidence/manifest.json` hay tệp nào dưới `docs/milestones/**/evidence/**` (diff của slice trên đường dẫn này phải rỗng). Manifest vẫn được kiểm là trung thực với commit M2 đã nghiệm thu, còn cây làm việc được phép tiến hóa. Git được gọi bằng danh sách đối số (`subprocess.run([...])`, không shell) với `cwd` là gốc repo; không tìm thấy commit hoặc blob thì test FAIL (fail-closed), không skip. Hai phép kiểm này cần PostgreSQL 18.6 (D9, R8).

`M2_ACCEPTED_SHA` là commit đã nghiệm thu của M2. Giá trị chưa được ghi trong tài liệu hiện hành nên là mục mở OI-CV-01: khi lập lệnh cho CP-2C, Orchestrator đọc commit cuối cùng chạm `docs/milestones/m2-control-plane/evidence/manifest.json` (đối chiếu bốn hash `ui/dist` bằng `git cat-file`) và ghi giá trị vào hằng `M2_ACCEPTED_SHA` của test; không xác định được thì dừng (`BLOCKED`) tới khi Control xác nhận. M2-P8/P9 có Auditor PASS nhưng user chưa ghi checkpoint M2, nên SHA này là mốc kỹ thuật, không phải sự phê duyệt của user.

## 9. Completion unit-of-work (CP-5)

Mục tiêu (CT-ORC-008, `TST-WF-INV-017`): ledger, `MediaUsage`, bộ đếm batch, chuyển reservation, outbox `VideoCompleted` và bản ghi cleanup eligibility cùng commit hoặc cùng rollback trong một giao dịch PostgreSQL.

- `CommitVideoCompletion` (G-10) và các port `CompletionStorePort`, `MediaUsagePort`, `CompletionUnitOfWork` đã có ở `src/controlplane/application/orchestration/commit_completion.py`; CP-5 chỉ thêm adapter thật.
- `src/controlplane/infrastructure/db/orchestration/postgres_completion.py`: `PostgresCompletionUnitOfWork` mượn một kết nối từ `TransactionManager`, cài `CompletionStorePort` trên các bảng của 0011 và outbox của 0003; mọi bước dùng đúng kết nối đó. Gói `controlplane.infrastructure.db.orchestration` đã khai ở cả `packages` và `package-dir` của `src/controlplane/pyproject.toml` nên CP-5 không tạo gói mới (không có `infrastructure/db/completion`, không có `__init__.py` mới) và không sửa `pyproject.toml`; nếu phong bì lúc biên dịch không cho ghi vào `infrastructure/db/orchestration/` thì CP-5 là `BLOCKED` theo BL-CV-11, không dời adapter sang thư mục khác. Probe `tomllib` trong `testCommands` của CP-5 kiểm điều này.
- Adapter `MediaUsagePort` gọi `catalog.application.usage.MediaUsageRecorder.record_production_usage(uow, completion_id, request)` với `repository_factory` gắn vào cùng `uow` (kho PostgreSQL của `PERSIST-C`); không mở kết nối thứ hai.
- Thứ tự trong giao dịch: cổng G-09, ledger duy nhất, `transition_job` sang `COMPLETED`, chuyển capacity và VariantReservation sang `CONVERTED`, CAS revision registry theo `expected_variant_registry_revision`, tăng bộ đếm batch, `MediaUsage`, outbox, cleanup eligibility (chỉ bản ghi, không lệnh xóa). Khóa `FOR UPDATE` trên dòng job; ledger unique theo `video_job_id`; gọi lặp cùng input trả ledger cũ và đếm một lần, khác input là `CONFLICT`.
- `cloud_location_verification_ref` bắt buộc, lấy từ kết quả `PersistVideoOutput` của I (CT-STO-006); thiếu thì `CLOUD_VERIFICATION_MISSING`. `recovery_epoch` so bằng `str()`. Nối vào composition root bằng `src/controlplane/api/wiring/completion.py`.
- Kiểm trên PostgreSQL dùng một lần: tiêm lỗi trước và sau từng bước (trước ledger, sau ledger, trước và sau usage, trước outbox) thì trạng thái trước và sau bằng nhau; gọi lặp 5 lần thì count bằng 1 (`TST-WF-INV-010`); registry stale không ghi gì; hai worker song song cùng job chỉ một thắng; không phát `VideoCompleted` khi rollback. Đây vẫn là logic và PostgreSQL cục bộ, không đóng G04 Drive hay fault suite thật (CP7-G-03).

## 10. Workflow (CP-6)

- **Vị trí**: `src/controlplane/application/orchestration/workflows/**` (trong `PATH-SRC-ORCHESTRATION`, tầng application nên được phép import `temporalio`). Dùng `temporalio==1.32.0` (cần `CP-2B-DEPS`); module workflow chỉ import `temporalio` và mã domain thuần, không đọc đồng hồ, ngẫu nhiên hay mạng; mọi timeout, retry và backoff lấy từ cấu hình J (D8-G-07), không hằng số cứng.
- **Sáu workflow** theo catalog G-12 (CT-WF-001): `DailyCollectionWorkflow`, `ContentEnrichmentWorkflow`, `ProductionBatchWorkflow`, `VideoProductionWorkflow` (child cô lập lỗi), `DebugStageWorkflow` (`auto_advance=False`), `MaintenanceWorkflow`; sáu task queue `control-workflows`, `cloud-io`, `cloud-ai`, `desktop-cpu`, `desktop-gpu`, `desktop-render`; stage script, plan, tts chỉ ở queue desktop (R18).
- **Đăng ký activity**: A (`PlanCollectionCycle`, activity A-18), B (`ResolveCollectedDocument`, một activity cho mỗi collected document), C (media discovery, `RequestSupplementalMedia`), D (D-16), E (E-18), F (F-20), I (Persist, Materialize, Cleanup, Reconcile), J (`ResolveProviderRoute`, `ReserveProviderCapacity`, `IssueShortLivedCredential`). Mọi activity nhận `ActivityRequest` và trả `ActivityResult` đúng `g-activity-execution.json`; thiếu `execution_grant` ở thao tác có side effect thì từ chối.
- **Signal**: `RunDebugStage`, `RetryStage`, `CreateNewVariant`, `RegenerateFromStage` (G-11); thiếu capability thì đặt `WAITING_CAPABILITY` rồi resume theo `CapabilityView`; subscription `CollectedDocumentAvailable` sang B.
- **Grant và lịch**: đổi A-18 từ `ExecutionGrant` P6 sang `GrantClaims` (G-03) trong cùng slice, giữ test A-18 xanh (YC-HT-G-10). Lịch cloud (PUC-G-01): múi giờ chưa duyệt nên lịch production ở trạng thái `NOT_READY`, không bật.
- **Kiểm không cần máy chủ Temporal**: AST kiểm module workflow không import `time`, `random`, `socket` và không gọi `datetime.now`; mọi stage của catalog có queue và mọi activity có handler; chạy `VideoProductionWorkflow` bằng bộ chạy trong tiến trình với fake cho từng phân hệ và đi qua completion thật của CP-5. Replay trên Temporal Server 1.31.2 thật thuộc CP7-G-03 (cần D5), không tuyên bố ở gói này.

## 11. Thứ tự, khóa và DAG

| Slice | dependsOn chính | Khóa tài nguyên |
| --- | --- | --- |
| `CP-2B-DEPS` | `USER-CKPT-D9-D10` | `LOCK-DEPENDENCY-UNIVERSE`, `LOCK-CONVERGENCE` |
| `CP-2C-M2-REGRESSION` | OI-CV-01 (`M2_ACCEPTED_SHA`) | `LOCK-M2-REGRESSION`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE` |
| `CP-2D-REGISTRY` | không | `LOCK-PARALLEL-REGISTRY`, `LOCK-DOC-AUTHORITY`, `LOCK-DOC-INDEX`, `LOCK-CONVERGENCE` |
| `CP-3-MIGRATIONS` | `CP-2C-M2-REGRESSION`, PostgreSQL harness của M2 | `LOCK-MIGRATION-SEQUENCE`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE` |
| `CP-3B-STATE-MACHINE` | `CP-2D-REGISTRY` | `LOCK-CONTRACT-STATE-MACHINES`, `LOCK-CONVERGENCE` |
| `CP-4-WIRING` | `USER-CKPT-D9-D10`, `CP-2B-DEPS`, `CP-2D-REGISTRY`, `CP-3-MIGRATIONS`, `CP-3B-STATE-MACHINE`, `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J` | `LOCK-COMPOSITION-ROOT`, `LOCK-CONTROL-API`, `LOCK-SRC-CONFIG-SECURITY`, `LOCK-CONVERGENCE` |
| `CP-4B-UI-SHELL` | `CP-2D-REGISTRY`, `CP-4-WIRING`, runtime Node (D9) | `LOCK-UI-SHELL`, `LOCK-SRC-CONTROL-UI`, `LOCK-M2-REGRESSION`, `LOCK-CONVERGENCE` |
| `CP-5-COMPLETION` | `CP-3-MIGRATIONS`, `CP-4-WIRING`, `PERSIST-C`, `PERSIST-G`, `PERSIST-I` | `LOCK-SRC-ORCHESTRATION`, `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE` |
| `CP-6-WORKFLOW` | `USER-CKPT-D9-D10`, `CP-2B-DEPS`, `CP-5-COMPLETION` | `LOCK-SRC-ORCHESTRATION`, `LOCK-SRC-SOURCE-INGESTION`, `LOCK-COMPOSITION-ROOT`, `LOCK-CONVERGENCE` |

`CP-2C` và `CP-2D` không dùng thư viện mới nên chạy được trước `USER-CKPT-D9-D10`. Các slice giữ `LOCK-CONVERGENCE` chạy tuần tự (mỗi lúc một owner); `PERSIST-*` chạy song song trong khóa riêng của phân hệ. `CP-4-WIRING` và `CP-4B-UI-SHELL` tách vì khóa và chu kỳ audit khác nhau.

### 11.1. Cạnh phụ thuộc bắt buộc và quy tắc biên dịch

Control biên dịch kế hoạch này thành các gói làm việc; bản biên dịch phải giữ nguyên các cạnh dưới đây. Đã có lần biên dịch bỏ `CP-2D-REGISTRY` rồi gỡ luôn cạnh của `CP-3B-STATE-MACHINE` (kéo theo `CP-4-WIRING` và `CP-4B-UI-SHELL`), và bỏ `PERSIST-*` khỏi `CP-4-WIRING` và `CP-5-COMPLETION`; điều đó không được phép.

| Gói | Cạnh bắt buộc (không được bỏ) | Lý do |
| --- | --- | --- |
| `CP-3B-STATE-MACHINE` | `CP-2D-REGISTRY` | BL-CV-01: binding H↔G, H↔J và mẫu `api/wiring/**` do CP-2D tạo |
| `CP-4-WIRING` | `CP-2D-REGISTRY`, `CP-3B-STATE-MACHINE`, `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J` | route và wiring cần kho PostgreSQL thật của từng phân hệ và binding của CP-2D |
| `CP-4B-UI-SHELL` | `CP-2D-REGISTRY`, `CP-4-WIRING` | màn hình chỉ sẵn sàng khi route CP-4 và binding H↔G, H↔J tồn tại |
| `CP-5-COMPLETION` | `CP-3-MIGRATIONS`, `CP-4-WIRING`, `PERSIST-C`, `PERSIST-G`, `PERSIST-I` | ledger, MediaUsage và outbox cùng một giao dịch phải chứng minh trên kho PostgreSQL thật, không trên kho tạm hay fake |
| `CP-6-WORKFLOW` | `CP-5-COMPLETION` | workflow đi qua completion thật |

Quy tắc:

1. `USER-CKPT-D9-D10` và `PERSIST-*` không nằm trong slices.md nhưng vẫn là cạnh thật: bản biên dịch ghi chúng là cổng chờ (như `USER-CKPT-D9-D10`), không được bỏ chỉ vì chúng không phải slice.
2. Gói hay phần việc nằm ngoài phong bì policy lúc biên dịch không bị loại khỏi kế hoạch. Gói đó giữ trong danh sách với trạng thái `BLOCKED` hoặc `PENDING` và mã `BL-CV-*` ở mục 12.1; mọi gói phụ thuộc vào nó (trực tiếp hoặc gián tiếp) dừng theo, không dispatch.
3. Muốn mở gói thì Control mở rộng phong bì và khóa tương ứng rồi ghi vào report; không bỏ cạnh để làm cho gói dispatch được.
4. Bỏ hoặc đổi cạnh là đổi kế hoạch đã duyệt; chỉ qua lần lập lại kế hoạch, và đổi kiến trúc đã duyệt là `ARCHITECTURE_CHANGE`, chờ user.
5. Mọi lệnh kiểm trong `testCommands` phải chạy trên tệp thật của gói; test chỉ dùng service giả hoặc kho tạm không chứng minh phần acceptance đòi chứng minh trên kho PostgreSQL thật.

## 12. Mục mở và danh sách chờ user (pendingUserCheckpoint)

Không mục nào dưới đây được ghi là đã duyệt.

- `USER-CKPT-D9-D10`: danh sách thư viện (mục 3), cách dựng lại runtime (mục 4), ba giá trị cần cung cấp (FFmpeg, Temporal, digest PostgreSQL), phiên bản `cryptography` (mục 3.3).
- OI-CV-01: `M2_ACCEPTED_SHA` (mục 8). User checkpoint M2 (P8/P9) vẫn chưa ghi.
- PUC-G-02 (khoảng trống CT-STATE-008), PUC-J-03 (cạnh phục hồi ExternalAccount), YC-HT-I-04 (đường ghi `CLEANUP_AUTHORIZED` sang `DELETED`): `CP-3B-STATE-MACHINE` giữ nguyên đồ thị hiện hành tới khi user quyết; đổi state machine đã đóng băng là `ARCHITECTURE_CHANGE`.
- PUC-J-07 (nơi lưu secret), PUC-G-01 và ROADMAP-OPEN-004 (múi giờ), PUC-H-05 (test runner TypeScript), ADR-0002 (embedding và pgvector), TECH-OPEN-012 (build FFmpeg).
- CP7 theo D5 (Drive, OAuth, GPU, AI trả phí, chạy 12 giờ): mọi mục `CP7-*` của mười kế hoạch phân hệ nằm ngoài gói này.

### 12.1. Việc nằm ngoài phong bì và backlog có mã (BL-CV)

Mỗi mục là việc mà ownedPaths của slice không bao phủ hoặc còn cần gate; không ghi là đã làm và không đổi thiết kế đã duyệt. PENDING = chưa mở; BLOCKED = dừng tới khi gate đạt. Mở rộng phong bì do Control quyết; bỏ một phần thiết kế đã duyệt là `ARCHITECTURE_CHANGE`, chờ user.

| Mã | Slice | Việc nằm ngoài phong bì | Trạng thái | Gate |
| --- | --- | --- | --- | --- |
| BL-CV-01 | CP-2D-REGISTRY | Toàn bộ ownedPaths của slice (`docs/parallel-delivery/**`, `tests/fixtures/contracts/**`, `docs/10-test-strategy.md`, `docs/modules/capability-*.md`, `README.md`, `CHANGELOG.md`, `HANDOFF.md`) nằm ngoài ownedPaths của gói kế hoạch này | PENDING | Control xác nhận phong bì policy cho các đường dẫn đó lúc biên dịch; không được thì slice BLOCKED và `CP-3B-STATE-MACHINE`, `CP-4-WIRING`, `CP-4B-UI-SHELL` dừng theo (cần binding H↔G, H↔J và mẫu `api/wiring/**`) |
| BL-CV-02 | CP-4-WIRING | Đăng ký event kind: `src/controlplane/application/sse/event_catalog.py` (`BASE_STREAM_EVENT_KINDS`) và publisher/outbox không thuộc ownedPaths của CP-4 | PENDING | Control mở rộng ownedPaths của CP-4 kèm khóa của owner đường dẫn (xác minh trong `ownership-and-locks.yaml`) hoặc mở slice riêng; tới đó Worker CP-4 ghi PENDING và không sửa các tệp này |
| BL-CV-03 | CP-4-WIRING | `RoutedInvocationService` (J-18) chưa có trong `src/` (tìm bằng rg không thấy); CP-4 chỉ nối qua `api/wiring`, không tạo lớp này | BLOCKED | J-18 đạt Auditor PASS và lớp có trong `src/` |
| BL-CV-04 | CP-4-WIRING | Thay host `mock-9router` trong `DEFAULT_APPROVED_ENDPOINTS` (`src/controlplane/config/adapter.py` dòng 58–64) làm hỏng `tests/unit/security/test_http_router_adapter.py` (dòng 45, 58, 63, 84 dùng `http://mock-9router:8000`), tệp này ngoài ownedPaths | BLOCKED | Control mở rộng ownedPaths của CP-4 để sửa test đó, hoặc danh sách từ cấu hình J giữ test xanh; `tests/unit/security` nằm trong lệnh kiểm của CP-4 để bắt hồi quy |
| BL-CV-05 | CP-4-WIRING | Query CT-API-002 còn thiếu (sources, articles, events, media, hooks, stage runs, sessions, logs, capabilities) cần kho `PERSIST-*` của từng phân hệ | PENDING | `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J` đạt Auditor PASS; route chỉ gọi service qua port |
| BL-CV-06 | CP-4-WIRING | Mẫu `src/controlplane/api/wiring/**` (D8-CV-05) chưa nằm trong `PATH-COMPOSITION-ROOT` | BLOCKED | `CP-2D-REGISTRY` thêm mẫu vào `ownership-and-locks.yaml`; bỏ `api/wiring` khỏi phong bì trái D8-CV-05 là `ARCHITECTURE_CHANGE`, chờ user (hoặc Control mở rộng phong bì); không âm thầm đổi thiết kế đã duyệt |
| BL-CV-07 | CP-4B-UI-SHELL | Tệp UI (`index.css`, `api/client.ts`, `types/api.ts`, `components/*Grid.tsx`, `screens/**`, `App.tsx`) chỉ nối màn hình khi route CP-4 tương ứng tồn tại; tệp UI ngoài ownedPaths (ví dụ `api/streamEventKinds.ts`, `components/Header.tsx`) không được sửa; nếu phong bì lúc biên dịch không bao phủ một tệp trong danh sách này thì tiêu chí tương ứng (CSS pill ở `index.css`, `eventKinds` và `Set` ở `client.ts`, `OperationItem` và `JobItem` ở `types/api.ts`, logic pill ở `*Grid.tsx`, nối shell ở `App.tsx`) là BLOCKED và phải ghi vào report, không được bỏ im lặng; nút kiểm thử và `/test-driver` xem BL-CV-13 | PENDING | `CP-4-WIRING` PASS, runtime Node sau `USER-CKPT-D9-D10`; màn hình chưa có route giữ `backendStatus` = `pending_module`; mở rộng phong bì do Control quyết |
| BL-CV-08 | CP-5-COMPLETION | `src/controlplane/api/wiring/completion.py` (nối completion vào composition root) | BLOCKED | BL-CV-06 đạt gate và `CP-2B-DEPS` đã tạo `api/wiring/__init__.py`; tới đó Worker làm `postgres_completion.py` cùng test và ghi phần nối là PENDING trong report |
| BL-CV-09 | CP-6-WORKFLOW | A-18 sang `GrantClaims` (YC-HT-G-10) ở `src/source_ingestion/worker/activity_handler.py` và `tests/integration/collection/test_a18_worker_activity.py` (Phân hệ A, khóa `LOCK-SRC-SOURCE-INGESTION`) | PENDING | `GrantClaims` có ở `src/controlplane/domain/orchestration/fencing.py`; Control xác nhận khóa của A; test A-18 giữ xanh; đổi contract là `ARCHITECTURE_CHANGE` |
| BL-CV-10 | CP-6-WORKFLOW | `src/controlplane/api/wiring/workflow.py` (nối workflow vào composition root) | BLOCKED | BL-CV-06 đạt gate và `CP-5-COMPLETION` PASS; tới đó Worker làm workflow và test, ghi phần nối là PENDING |
| BL-CV-11 | CP-5-COMPLETION | `src/controlplane/infrastructure/db/orchestration/postgres_completion.py` và `tests/integration/convergence/test_cp5_completion_uow.py`: gói `controlplane.infrastructure.db.orchestration` đã khai trong `src/controlplane/pyproject.toml` (`packages` và `package-dir`); không tạo gói `infrastructure/db/completion` vì sẽ thiếu trong wheel và không gói nào khai nó | PENDING | Nếu phong bì lúc biên dịch không bao phủ `infrastructure/db/orchestration/` thì CP-5 BLOCKED; Control mở rộng ownedPaths tới thư mục đó kèm khóa `LOCK-SRC-ORCHESTRATION`; không dời adapter sang thư mục khác để lách phong bì (dời gói cần `CP-2B-DEPS` khai gói mới và Control duyệt) |
| BL-CV-12 | CP-4-WIRING | Bỏ `LIMIT 100` và phân trang keyset ở `src/controlplane/infrastructure/db/control_api_queries.py` (dòng 33, 92, 118, 147) và `src/controlplane/api/routes/control.py` (`next_cursor: None` ở dòng 23, 45, 81, 103) | PENDING | Hai tệp có trong ownedPaths của CP-4; nếu phong bì lúc biên dịch không bao phủ thì phần phân trang BLOCKED và Worker không tuyên bố đã làm; lệnh kiểm gồm test PostgreSQL thật trên `PostgresControlQueries` và probe đọc tệp; cần index keyset của migration `0018` (CP-3) |
| BL-CV-13 | CP-4B-UI-SHELL | Gỡ hoặc khóa nút `handleTriggerTestError` (`App.tsx`) và đường `/test-driver/issue-capability` (`client.ts`): nút nằm ở `components/Header.tsx` (ngoài ownedPaths); hai spec M2 đóng băng `safe-error-modal.spec.ts`, `performance-budget.spec.ts` bấm nút đó; `auth-helper.ts`, `operations-sse.spec.ts`, `playwright.config.ts` dùng `/test-driver`; đường cấp phiên sản xuất chưa có | BLOCKED | PUC-H-06 và CP7-H-05 (cơ chế cấp phiên sản xuất) được quyết; Control mở rộng phong bì tới `components/Header.tsx` và quyết cách xử lý spec M2 đã đóng băng (sửa spec M2 cần xác nhận riêng vì M2 đã nghiệm thu); tới đó Worker giữ nguyên và ghi BLOCKED vào report |
| BL-CV-14 | CP-2B-DEPS | Ghi `tools/runtime/runtime.lock.json`, tạo ba `__init__.py` (`api/routes/modules`, `api/wiring`, `application/orchestration/workflows`) và khai bốn gói trong `src/controlplane/pyproject.toml`, nếu phong bì lúc biên dịch không bao phủ các đường dẫn này (`tools/runtime/**`, `src/controlplane/api/**`, `src/controlplane/application/**`, `src/controlplane/pyproject.toml`) | PENDING | Control mở rộng phong bì; không bỏ `runtime.lock.json` hay hai gói `api.wiring`, `orchestration.workflows` khỏi kế hoạch vì CP-4, CP-4B, CP-5, CP-6 và dựng lại runtime (mục 4) cần chúng; thiếu thì các gói đó BLOCKED; bốn probe trong `testCommands` của CP-2B-DEPS là cổng |
| BL-CV-15 | CP-6-WORKFLOW | Toàn bộ ownedPaths của slice (`src/controlplane/application/orchestration/workflows/*.py`, `src/controlplane/api/wiring/workflow.py`, `src/source_ingestion/worker/activity_handler.py`, ba test `tests/integration/convergence/test_cp6_*.py`, `tests/integration/collection/test_a18_worker_activity.py`) nếu phong bì lúc biên dịch không bao phủ | PENDING | Control mở rộng phong bì kèm khóa `LOCK-SRC-ORCHESTRATION`, `LOCK-SRC-SOURCE-INGESTION`, `LOCK-COMPOSITION-ROOT`; không loại CP-6 khỏi kế hoạch; tới đó CP-6 BLOCKED, chi tiết từng phần ở BL-CV-09 và BL-CV-10 |

## 13. Quyết định D8 của kế hoạch này

- D8-CV-01: thứ tự migration theo phụ thuộc dữ liệu (mục 5.1); một owner cho toàn bộ `0009..0018`.
- D8-CV-02: pgvector không nằm trong `0014`; nếu user duyệt gói pgvector thì thêm bằng migration `0019` ở slice hội tụ mới (ADR-0002 chưa chốt embedding).
- D8-CV-03: runtime đặt ngoài cây Git; `node_modules` nối vào worktree bằng junction và loại khỏi Git qua `.git/info/exclude`.
- D8-CV-04: phép kiểm M2 so với blob của commit đã nghiệm thu thay vì cây làm việc; không sửa bằng chứng M2.
- D8-CV-05: wiring chia theo phân hệ ở `src/controlplane/api/wiring/**`; hai tệp composition root chỉ gọi.
- D8-CV-06: adapter PostgreSQL của từng phân hệ là slice `PERSIST-*` riêng, mở sau CP-3, không gộp vào CP-3.
- D8-CV-07: Control đề xuất chỉ duyệt ngay `temporalio==1.32.0` trong mục 3.2; các gói A, D, E hoãn tới POC hoặc CP7; quyết định thuộc user.
- D8-CV-08: CP-3B chỉ thêm đồ thị CT-STATE-005 và CT-STATE-006 (C) vào `controlplane.domain.statemachine`; A giữ bảng cục bộ kèm test tương đương với danh sách cạnh trong contract (một nguồn sự thật); D, E, F xác nhận không cần máy mới; G, H, I, J giữ nguyên chờ user.

## 14. Ngoài phạm vi

Mã nguồn `src/**`, migration thật, sửa kế hoạch phân hệ, sửa `docs/milestones/**/evidence/**`, tài nguyên thật (CP7), kích hoạt sản xuất, push và merge.
