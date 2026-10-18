# Báo cáo bằng chứng IMPL-PLAN-I

- Task: `IMPL-PLAN-I` (planning_package), trigger INITIAL. Bản đầu: commit `fd61462` trên base `f40822e0ea258ed799fffa781c2c7b06776dd21a`; lượt bổ sung: base `fd614627798e0882fa3afd1d3e792313296dbd4c`.
- Tệp tạo mới: `docs/implementation/i/plan.md`, `docs/implementation/i/slices.md` (13 slice I-01..I-13), `docs/delivery-evidence/impl-plan-i/report.md`.

## Nguồn đã đọc

- `docs/09-contracts/10-storage-contracts.md`
- `docs/09-contracts/12-state-machines.md`
- `docs/09-contracts/02-domain-events.md`
- `docs/adr/0006-drive-artifacts-and-local-journal.md`
- `docs/adr/0010-storage-lifecycle-and-recovery.md`
- `docs/11-roadmap.md`
- `docs/10-test-strategy.md`
- `docs/03-quality-requirements.md`
- `docs/parallel-delivery/ownership-and-locks.yaml`
- `docs/parallel-delivery/bindings/README.md`
- `docs/parallel-delivery/bindings/i-artifact-version.json`
- `docs/parallel-delivery/bindings/g-c-i-completion.json`
- `docs/parallel-delivery/bindings/f-render-package.json`
- `tests/fixtures/contracts/i-artifact-version/payloads.json`
- `tests/fixtures/contracts/f-render-package/payloads.json`
- `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- `docs/parallel-delivery/errata/m4-ci.md`
- `docs/parallel-delivery/M4-CI-execution-package.md` (chỉ để đối chiếu; bị errata thay thế)
- `src/controlplane/domain/storage_meta/__init__.py`
- `src/controlplane/application/storage_meta/__init__.py`
- `src/controlplane/infrastructure/db/storage_meta/__init__.py`
- `src/controlplane/domain/statemachine/__init__.py`
- `pyproject.toml`
- `HANDOFF.md`

## Quyết định D8 (chi tiết ở plan.md mục 6)

- D8-I-01 `policy_decision`: `new_version`/`matched_existing`.
- D8-I-02 Integrity: SHA-256 cục bộ; dùng checksum provider nếu có, nếu không thì tải lại để kiểm.
- D8-I-03 Working set: 5 set; `max_bytes` là cấu hình bắt buộc.
- D8-I-04 `recovery_epoch` là chuỗi opaque; P5B int chờ YC-HT-I-01.
- D8-I-05 Journal SQLite tự tạo schema, WAL + synchronous FULL.
- D8-I-06 Retention: original/reusable/output được giữ; per_video/temporary dọn sau completion.
- D8-I-07 Sanitize theo luật Windows, NFC, độ dài là tham số.
- D8-I-08 Ngày folder do caller truyền.
- D8-I-09 Placement theo rule cấu hình và quota domain.
- D8-I-10 Module mới cạnh P5B, test `test_storage_*.py`.
- D8-I-11 `CLEANUP_*` xếp `unavailable`.
- D8-I-12 Chỉ `local_staging`/`local_cache` dọn được.

## Quyết định D10

Không thêm thư viện. Slice chỉ dùng stdlib. CP7 dùng `google-api-python-client==2.200.0`, `google-auth-oauthlib==1.4.1`, `psycopg[binary]==3.3.5` đã khoá trong `pyproject.toml`.

## Danh sách chờ user (chưa duyệt)

PUC-I-01 (ROADMAP-OPEN-010), PUC-I-02 (ROADMAP-OPEN-004), PUC-I-03 (ngưỡng byte working set), PUC-I-04 (duyệt C-I, R2), PUC-I-05 (D5/CP7, USER-CKPT-D9-D10), PUC-I-06 (ROADMAP-OPEN-012).

## Yêu cầu gửi IMPL-PLAN-CONVERGENCE

YC-HT-I-01..YC-HT-I-09 (plan.md mục 9). CT-STO-006 bị chặn tới khi có binding F → I (YC-HT-I-07).

## Đính chính tài liệu cũ

`M4-CI-execution-package.md` dòng 185 gán sai `QUALITY-OPEN-006` cho working set (`docs/03-quality-requirements.md` dòng 284 định nghĩa đó là output profile video).

## Lượt bổ sung trên base fd61462

- `plan.md` mục 2: ghi rõ CT-STO-002 do `ArtifactLocationStore.declare` P5B đáp ứng; trường còn thiếu (device ref, thời điểm verify gần nhất, trạng thái lease/retention/cleanup) chuyển vào YC-HT-I-01.
- `plan.md` mục 6: thêm bảng đối chiếu bốn điểm mở roadmap §10; "Scale dataset cho catalog/index" thuộc phân hệ C; PUC-I-01 mở rộng sang retention log và evidence.
- `slices.md` không đổi (13 slice I-01..I-13).
- Nguồn đọc thêm: `src/controlplane/application/storage_meta/__init__.py` (`ArtifactLocationStore.declare`, `_UNSAFE_REFERENCE`), `src/controlplane/infrastructure/db/storage_meta/__init__.py` (bảng `cp_artifact_locations`), `docs/11-roadmap.md` §10 "Điểm còn mở phải chốt trước hoặc trong M4".

## Lượt sửa I-08 trên base c474224

- `slices.md` mục I-08: P5B khai `CleanupAuthorization.expires_at: str` (`src/controlplane/domain/storage_meta/__init__.py`), nên điều kiện hạn đổi thành `now < datetime.fromisoformat(authorization.expires_at)`; hết hạn → `EXPIRED`; `expires_at` không parse được hoặc thiếu múi giờ, hoặc `now` naive → `INVALID_EXPIRY`, không raise (fail-closed). Bổ sung instrument và counterexample tương ứng.
- `plan.md` không đổi; các slice khác không đổi.

## Lệnh kiểm

| Lệnh | Exit code | Kết quả |
|---|---|---|
| git diff --check | 0 | không có output |
| Lệnh kiểm bắt buộc python -c (plan/slices) | 0 | không có output |

Interpreter: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
