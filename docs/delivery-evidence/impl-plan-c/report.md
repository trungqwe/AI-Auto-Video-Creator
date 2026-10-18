# Báo cáo bằng chứng IMPL-PLAN-C

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `f40822e0ea258ed799fffa781c2c7b06776dd21a`

## RED

- Instrument nghiệm thu chạy trước khi tạo tệp: exit code 1; dòng cuối `FileNotFoundError: [Errno 2] No such file or directory: 'docs\\implementation\\c\\plan.md'`.

## Nguồn đã đọc

- `HANDOFF.md`, `AGENTS.md`, `pyproject.toml`
- `docs/modules/capability-c-storage.md`
- `docs/11-roadmap.md` §10, §14, §23
- `docs/09-contracts/05-content-media-contracts.md`
- `docs/09-contracts/04-source-content-contracts.md` (CT-SRC-003)
- `docs/09-contracts/10-storage-contracts.md`
- `docs/09-contracts/12-state-machines.md`
- `docs/10-test-strategy.md` §14.2, §15
- `docs/adr/0002-authoritative-data-and-search.md`
- `docs/parallel-delivery/bindings/README.md`
- `docs/parallel-delivery/bindings/c-d-media-candidates.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`, `docs/parallel-delivery/bindings/f-render-package.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`
- `tests/fixtures/contracts/c-d-media-candidates/payloads.json`, `tests/fixtures/contracts/i-artifact-version/payloads.json`, `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- `docs/parallel-delivery/errata/m4-ci.md`, `docs/parallel-delivery/M4-CI-execution-package.md`
- `docs/parallel-delivery/ownership-and-locks.yaml`
- `docs/delivery-evidence/cp1-contract-binding/report.md`
- `src/controlplane/domain/statemachine/__init__.py`, `src/controlplane/domain/interfaces/uow.py`, `src/controlplane/domain/concurrency.py`

## Tệp tạo mới

- `docs/implementation/c/plan.md`
- `docs/implementation/c/slices.md` (9 slice: C-01..C-09)
- `docs/delivery-evidence/impl-plan-c/report.md`

## Quyết định D8

Chi tiết và lý do ở `docs/implementation/c/plan.md` §7: D8-C-01 không xoá metadata/provenance; D8-C-02 repository Protocol, fake bộ nhớ và phân trang bắt buộc; D8-C-03 `index_revision` và so khớp xác định; D8-C-04 trạng thái đọc không có hàm chuyển; D8-C-05 ánh xạ safety → usability cho ảnh (GIẢ ĐỊNH fail-closed cho trạng thái chưa đánh giá xong); D8-C-06 rights không chắc chắn được lưu, không chặn; D8-C-07 checksum thuộc I; D8-C-08 media kind `image`, `clip`, `audio`; D8-C-09 thứ tự trạng thái hiển thị; D8-C-10 storage placement/quota thật thuộc I và CP7.

## Quyết định D10

Không cần thư viện mới; chỉ stdlib và `pytest==9.1.1` đã khoá. Adapter pgvector (nếu cần) do CONV-C-01 đề xuất tại USER-CKPT-D9-D10.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2, USER-CKPT-D9-D10, CP7 (D5), ROADMAP-OPEN-010, GIẢ ĐỊNH của D8-C-05.

## Yêu cầu gửi IMPL-PLAN-CONVERGENCE

- CONV-C-01..CONV-C-09 (xem `docs/implementation/c/plan.md` §10).

## Follow-up

- Đồng bộ `HANDOFF.md`, `README.md`, `CHANGELOG.md` thuộc gói hội tụ (ngoài owned paths).

## Bổ sung theo lệnh Orchestrator (HEAD a849f79)

- `docs/implementation/c/plan.md` §6: ánh xạ same byte retry/byte khác version mới sang C-03; nêu phần liên quan của `INV-012`; bổ sung Unicode/collision và cleanup authorization cũ vào nhóm ngoài phạm vi C.
- `docs/implementation/c/plan.md` §7: thêm D8-C-10 (storage placement/quota thật).
- Nguồn đối chiếu thêm: `docs/11-roadmap.md` §10 (Test bắt buộc, Điểm còn mở), `docs/10-test-strategy.md` (`TST-SEC-INV-012`).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 1 | `git diff --check` (bước 23) | 0 | Không có output (PASS) |
| 2 | Instrument nghiệm thu `python -c "import re, pathlib, unicodedata; ..."` của task (bước 24) | 0 | Không có output (PASS) |
| 3 | `git diff --check` (vòng bổ sung, bước 6) | 0 | Không có output (PASS) |
| 4 | Instrument nghiệm thu của task bằng interpreter khoá (vòng bổ sung, bước 7) | 0 | Không có output (PASS) |
