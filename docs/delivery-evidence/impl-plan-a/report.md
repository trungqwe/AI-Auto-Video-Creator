# Báo cáo bằng chứng IMPL-PLAN-A

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `f40822e0ea258ed799fffa781c2c7b06776dd21a`
- Nhánh: `trungqwe/lane-impl-plan-a`

## Nguồn đã đọc

- `HANDOFF.md`, `AGENTS.md`
- `docs/modules/a-source-collection/spec.md`
- `docs/modules/a-source-collection/implementation-plan.md`
- `docs/11-roadmap.md` (§9 dòng 287–350, §23)
- `docs/09-contracts/04-source-content-contracts.md`
- `docs/09-contracts/12-state-machines.md`
- `docs/10-test-strategy.md` (dòng 526–545, 1184–1199)
- `docs/05-technology-research.md` (dòng 116–139)
- `docs/parallel-delivery/bindings/README.md`
- `docs/parallel-delivery/bindings/a-b-collected-document.json`
- `docs/parallel-delivery/bindings/domain-event-envelope.json`
- `docs/parallel-delivery/bindings/g-activity-execution.json`
- `docs/parallel-delivery/bindings/i-artifact-version.json`
- `tests/fixtures/contracts/a-b-collected-document/payloads.json`
- `docs/parallel-delivery/errata/m3-a.md`
- `docs/parallel-delivery/ownership-and-locks.yaml`
- `docs/delivery-evidence/cp1-contract-binding/report.md`
- `pyproject.toml`
- `src/controlplane/domain/interfaces/uow.py`, `src/controlplane/domain/interfaces/outbox.py`, `src/controlplane/domain/events/contracts.py`, `src/controlplane/domain/concurrency.py`, `src/controlplane/domain/orchestration/__init__.py`, `src/controlplane/application/idempotency/canonicalization.py`

## RED

- Tại HEAD `f40822e0ea258ed799fffa781c2c7b06776dd21a` chưa có `docs/implementation/a/` (chỉ tồn tại dạng untracked trong worktree), nên lệnh kiểm bắt buộc NFC/slice ở HEAD gặp `FileNotFoundError` với `docs/implementation/a/plan.md`.
- Bản nháp untracked trước khi sửa (bước 1): `plan.md` chứa ký tự điều khiển do escape backtick của PowerShell, làm gãy dòng bảng và mất định dạng code; `report.md` mất dấu tiếng Việt thành dấu hỏi. Kết quả bước 1 ghi ở mục Kết quả lệnh kiểm.

## Quyết định D8

Chi tiết ở `docs/implementation/a/plan.md` §7.

- MODULE-A-OPEN-001 (`source_kind`): tập giá trị là input policy; `rss_feed`, `web_page` chỉ dùng trong fixture test; thiếu policy → `INPUT_NOT_READY` (pendingUserCheckpoint).
- MODULE-A-OPEN-002 (nguồn baseline, tiêu chí Tier): Tier nhận từ user/policy; thiếu Tier policy thì candidate giữ `WAITING_POLICY`, auto-registration production `NOT_READY` (pendingUserCheckpoint).
- MODULE-A-OPEN-003 (ngưỡng tin mới từng chủ đề): A nhận ngưỡng/bộ đếm từ G, không lưu hằng (pendingUserCheckpoint).
- MODULE-A-OPEN-004, ROADMAP-OPEN-004, QUALITY-OPEN-014, TEST-OPEN-009 (múi giờ): A nhận `business_date` do G suy ra (pendingUserCheckpoint trước lịch production).
- MODULE-A-OPEN-005 (ngưỡng nội dung, policy title): ExtractionPolicy có revision là input (pendingUserCheckpoint).
- MODULE-A-OPEN-006: đã đóng theo CT-SRC-003A/CT-STATE-002A.
- MODULE-A-OPEN-007, ROADMAP-OPEN-010 (retention): `retention_class` lấy từ policy, I quyết (pendingUserCheckpoint).
- MODULE-A-OPEN-008 (adapter thật): transport giả và extractor stdlib tham chiếu chỉ cho fixture (pendingUserCheckpoint, CP7).
- MODULE-A-OPEN-009 (timeout/retry/backoff/concurrency): policy là input, không số mặc định (pendingUserCheckpoint, CP7).
- MODULE-A-OPEN-010, QUALITY-OPEN-002 (thời gian cycle): không tuyên bố hiệu năng (pendingUserCheckpoint, CP7).
- ROADMAP-OPEN-005, QUALITY-OPEN-005 (hot/trending): ngoài A.
- Quyết định D8 của kế hoạch: enum `extraction_disposition` A-local là GIẢ ĐỊNH, validator chỉ kiểm chuỗi không rỗng; transition Source/Run/Candidate đặt trong `src/source_ingestion/domain`, đăng ký chung qua CONV-A-05; persistence in-memory tới CONV-A-01; thư mục test không có `__init__.py`, tên tệp `test_aNN_*.py`.

Không mục nào trong danh sách pendingUserCheckpoint được ghi là đã duyệt.

## Quyết định D10

- Slice A-01..A-19 không thêm thư viện; chỉ dùng stdlib và module controlplane đã có.
- Đề xuất chờ USER-CKPT-D9-D10: `feedparser==6.0.14`, `trafilatura==2.2.0`, `jusText==3.0.2`, `Scrapy==2.19.0` (chỉ khi POC cần), `playwright==1.63.0` (cần browser binary).
- HTTP client cho fetch boundary: mở `IMPL-PLAN-A-OPEN-001`, chọn qua TECH-POC-001.

## Tệp trong commit

- `docs/implementation/a/plan.md` (viết lại sạch: bỏ ký tự điều khiển, khôi phục định dạng code, CT-CNT-001 ghi đúng `ResolveCollectedDocument`, composition root theo `PATH-COMPOSITION-ROOT`)
- `docs/implementation/a/slices.md` (19 slice A-01..A-19, giữ nguyên bản nháp đã qua kiểm phong bì ở bước 12)
- `docs/delivery-evidence/impl-plan-a/report.md`

## Việc chuyển Control

- `HANDOFF.md`, `README.md`, `CHANGELOG.md` nằm ngoài owned paths; đề nghị Control cập nhật.
- CONV-A-01..CONV-A-09 (plan §10) gửi IMPL-PLAN-CONVERGENCE.

## Kết quả lệnh kiểm

Lệnh python chạy bằng interpreter khoá ở mục Môi trường.

| Bước | Lệnh | Exit code | Output |
| --- | --- | --- | --- |
| 1 | kiểm khuyết tật bản nháp | 0 | plan_control_chars ['0x7', '0x8', '0x9']; report_question_marks 280 |
| 10 | kiểm nội dung và vệ sinh plan.md | 0 | plan ok 200 lines 87 table rows |
| 11 | lệnh kiểm bắt buộc NFC/slice | 0 | (không có output) |
| 12 | kiểm phong bì slices.md | 0 | 19 slices ok 30 binding refs |
| 13 | `git diff --check` | 0 | (không có output) |
