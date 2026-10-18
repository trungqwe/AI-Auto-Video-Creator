# Báo cáo bằng chứng IMPL-PLAN-D

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `fb154e9f0433d45bef1994e292a948231b18d112`
- Nhánh: `trungqwe/lane-impl-plan-d`

## Nguồn đã đọc

- `HANDOFF.md`, `AGENTS.md`
- `docs/modules/capability-d-scripting.md`
- `docs/11-roadmap.md` (§11 dòng 425–485, §14, §19, §23)
- `docs/09-contracts/06-creative-ai-contracts.md`
- `docs/09-contracts/02-domain-events.md`
- `docs/09-contracts/04-source-content-contracts.md`
- `docs/09-contracts/05-content-media-contracts.md`
- `docs/09-contracts/07-media-processing-contracts.md`
- `docs/09-contracts/08-render-quality-contracts.md`
- `docs/09-contracts/09-orchestration-contracts.md`
- `docs/09-contracts/11-configuration-security-contracts.md`
- `docs/09-contracts/12-state-machines.md`
- `docs/10-test-strategy.md` (dòng 522–605, 1097–1108, 1180–1201)
- `docs/05-technology-research.md` (dòng 92–108, 348–368)
- `docs/parallel-delivery/bindings/README.md`
- `docs/parallel-delivery/bindings/b-d-production-snapshot.json`, `docs/parallel-delivery/bindings/c-d-media-candidates.json`, `docs/parallel-delivery/bindings/j-provider-route.json`, `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`, `docs/parallel-delivery/bindings/f-render-package.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`, `docs/parallel-delivery/bindings/g-activity-execution.json`
- `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- `docs/parallel-delivery/errata/m5-d.md`
- `docs/parallel-delivery/ownership-and-locks.yaml`
- `docs/parallel-delivery/task-dag.yaml` (`pending_user_checkpoint`)
- `docs/implementation/a/plan.md`, `docs/implementation/a/slices.md` (khuôn kế hoạch)
- `docs/delivery-evidence/cp2a-layout/report.md`, `docs/delivery-evidence/impl-plan-a/report.md`
- `pyproject.toml`
- `src/controlplane/domain/orchestration/__init__.py`, `src/controlplane/domain/config_security/__init__.py`, `src/controlplane/application/orchestration/__init__.py`, `src/controlplane/application/idempotency/canonicalization.py`, `src/controlplane/config/models.py`, `src/controlplane/config/router.py`

## RED

- Tại HEAD `fb154e9f0433d45bef1994e292a948231b18d112` chưa có `docs/implementation/d/`; lệnh kiểm bắt buộc NFC/slice chạy ở bước 1 trước khi tạo tệp trả exit code 1 với dòng lỗi cuối `FileNotFoundError: [Errno 2] No such file or directory: 'docs\implementation\d\plan.md'`.

## Quyết định D8

Chi tiết ở `docs/implementation/d/plan.md` §7.

- ROADMAP-OPEN-006/TEST-OPEN-001: slice chỉ kiểm logic xác định, không tuyên bố G06 (pendingUserCheckpoint).
- Ngưỡng dedup, event-link confidence: thuộc B, ghi nhận.
- ROADMAP-OPEN-005/QUALITY-OPEN-005/TEST-OPEN-004: `eligibility_reason` là input từ G/B (pendingUserCheckpoint).
- Provider/model/prompt theo vai trò: input từ J, slice dùng fake (pendingUserCheckpoint, CP7-D-01).
- TEST-OPEN-003: số lần thử và hạn là policy input (pendingUserCheckpoint).
- Tốc độ đọc: `speech_rate` từ policy, thiếu → `INPUT_NOT_READY`; bỏ hằng 140–165 từ (pendingUserCheckpoint, CP7-D-04).
- ROADMAP-OPEN-009 preset; music/SFX và safety/rights policy: input ref (pendingUserCheckpoint).
- Quyết định D8 của kế hoạch: 61–70 giây là input CT-AI-004, F kiểm trên video thật; thumbnail so time range trong hook, không hằng 0–3 giây; yếu tố khác biệt theo CT-AI-008; schema output model D-local `creative-ai-output/v1` (tên là GIẢ ĐỊNH); `ref_type` là input policy, fixture `article_revision`, `event_update_accepted` (GIẢ ĐỊNH); filename-safe qua port của I; không state machine riêng; persistence in-memory tới CONV-D-01; tệp test `test_dNN_*.py`, không `__init__.py`; không khẳng định tái lập bằng seed.

Không mục nào trong danh sách pendingUserCheckpoint được ghi là đã duyệt.

## Quyết định D10

- Slice D-01..D-18 không thêm thư viện; chỉ dùng stdlib và module controlplane đã có; không dùng `pydantic`, `temporalio` dù đã có trong lock.
- Đề xuất tùy chọn chờ USER-CKPT-D9-D10 cho adapter provider (chọn một sau POC): `pydantic-ai==2.43.0` hoặc `instructor==1.17.0`; không đề xuất LiteLLM, LangChain, vLLM ở baseline; Ollama/llama.cpp là runtime ngoài (CP7-D-03).

## Danh sách chờ user (pendingUserCheckpoint)

- Mục mở ở plan §7, USER-CKPT-D9-D10, CP7 theo D5 (plan §9), exit gate G7 (user duyệt D và `R3 Creative Alpha`).

## Tệp trong commit

- `docs/implementation/d/plan.md`
- `docs/implementation/d/slices.md`
- `docs/delivery-evidence/impl-plan-d/report.md`

## Việc chuyển Control

- `HANDOFF.md`, `README.md`, `CHANGELOG.md` nằm ngoài owned paths; đề nghị Control cập nhật.
- CONV-D-01..CONV-D-11 (plan §10) gửi IMPL-PLAN-CONVERGENCE.

## Kết quả lệnh kiểm

Lệnh python chạy bằng interpreter khoá ở mục Môi trường.

| Bước | Lệnh | Exit code | Output |
| --- | --- | --- | --- |
| 1 | lệnh kiểm bắt buộc NFC/slice (RED, trước khi tạo tệp) | 1 | `FileNotFoundError: [Errno 2] No such file or directory: 'docs\implementation\d\plan.md'` |
| 27 | lệnh kiểm bắt buộc NFC/slice | 0 | (không có output) |
| 28 | kiểm phong bì slices.md | 0 | 18 slices ok 36 binding refs |
| 29 | kiểm nội dung plan.md | 0 | plan ok 18 slices 35 paths |
| 30 | kiểm vệ sinh tệp | 0 | hygiene ok [234, 397, 73] |
| 31 | kiểm report.md | 0 | report ok 42 paths |
| 32 | git diff --check | 0 | (không có output) |
