# Kế hoạch triển khai Phân hệ I — Lưu trữ, đồng bộ và vòng đời tệp

> Task: `IMPL-PLAN-I` (planning_package). Base: `fd614627798e0882fa3afd1d3e792313296dbd4c` (bản đầu là commit `fd61462` trên `f40822e0ea258ed799fffa781c2c7b06776dd21a`; lượt này bổ sung CT-STO-002 và đối chiếu điểm mở roadmap §10).
> Nguồn quyền: D3 — user duyệt Phần B ngày 18/10/2026; M3–M7 theo ủy quyền AI_SETUP. Kích hoạt sản xuất vẫn `PRODUCTION_ACTIVATION_BLOCKED`.
> Đây là kế hoạch; mã nguồn do các slice trong `docs/implementation/i/slices.md` thực hiện.

## 1. Nguồn chuẩn

- `docs/09-contracts/10-storage-contracts.md` (CT-STO-001..011, mục 12 acceptance)
- `docs/09-contracts/12-state-machines.md` (CT-STATE-012)
- `docs/09-contracts/02-domain-events.md` (`ArtifactLocationVerified`, `CleanupCompleted`)
- `docs/adr/0006-drive-artifacts-and-local-journal.md`, `docs/adr/0010-storage-lifecycle-and-recovery.md`
- `docs/11-roadmap.md` §10 (M4: năng lực I, test bắt buộc, exit gate, điểm mở), §13, §14, §19, §23
- `docs/10-test-strategy.md` (bảng invariant INV-008, INV-009, INV-011, INV-012, INV-016)
- `docs/parallel-delivery/ownership-and-locks.yaml` (phân hệ I dòng 56–59; `PATH-SRC-STORAGE`, `LOCK-SRC-STORAGE` dòng 186–196)
- `docs/parallel-delivery/bindings/README.md` và các binding ở mục 4
- `docs/parallel-delivery/errata/m4-ci.md`

Quy tắc errata: `docs/parallel-delivery/M4-CI-*.md` là tài liệu cũ; khi mâu thuẫn, errata và nguồn chuẩn thắng. Kế hoạch này không dùng cây `src/storage/**`, không dùng test ID ngoài catalog (`TST-STO-SYNC-*`), không ghi bằng chứng vào `docs/milestones/**/evidence/**`, giữ cạnh `VERIFIED → MISSING` và không thêm recovery edge từ `MISSING`/`CORRUPT`/`OUTCOME_UNKNOWN`. Đính chính thêm: `M4-CI-execution-package.md` dòng 185 gán `QUALITY-OPEN-006` cho working set, nhưng `docs/03-quality-requirements.md` dòng 284 định nghĩa mục này là output profile video; ngưỡng byte của working set được xử lý ở PUC-I-03.

## 2. Năng lực và aggregate

Aggregate do I sở hữu (ownership-and-locks.yaml): `ArtifactVersion`, `ArtifactLocation`, `CleanupAuthorization` (đã có khung P5B) và `LocalJournalEntry` (mới, nằm trong SQLite desktop).

| # | Năng lực (roadmap §10) | Contract | Aggregate/thành phần | Slice |
|---|---|---|---|---|
| 1 | Artifact, immutable version, location | CT-STO-001, CT-STO-002 | ArtifactVersion, ArtifactLocation | I-01, I-02, I-13; CT-STO-002 do `ArtifactLocationStore.declare` P5B đáp ứng (xem đoạn dưới bảng) |
| 2 | Upload idempotent, verify integrity, reconcile `OUTCOME_UNKNOWN` | CT-STO-003 | ArtifactLocation, upload receipt | I-03, I-04 |
| 3 | Placement theo loại dữ liệu trên bốn tài khoản | CT-STO-010 | StoragePlacementPolicy (value object) | I-12 |
| 4 | Materialize gần lượt xử lý, lease, hash verification | CT-STO-004 | ArtifactLocation local, staging root | I-06, I-07 |
| 5 | SQLite local journal, recovery checkpoint | CT-STO-005 | LocalJournalEntry | I-05 |
| 6 | Working set khoảng năm video, prefetch có admission | CT-STO-004 | WorkingSetPolicy | I-07 |
| 7 | Cleanup authorization theo ledger, lease, path, recovery epoch | CT-STO-007, CT-STO-008, CT-STO-009 | CleanupAuthorization | I-08, I-09, I-10 |
| 8 | Output path allocator, sanitize title/hashtag, folder session | CT-STO-011 | OutputName (value object) | I-11 |

CT-STO-006 (`PersistVideoOutput`) không có slice trong kế hoạch này vì seam F → I chưa có binding (mục 4, YC-HT-I-07).

CT-STO-002 (`RegisterArtifactLocation`) không có slice riêng: `ArtifactLocationStore.declare` của P5B (`src/controlplane/application/storage_meta/__init__.py`) đã khai báo location và từ chối ref rỗng hoặc không an toàn qua `_UNSAFE_REFERENCE` (đường tuyệt đối, `..`, `file://`, `token=`, `secret=`, `password=`…), đáp ứng điều "không đưa raw credential vào location". Các trường CT-STO-002 mà dataclass `ArtifactLocation` và bảng `cp_artifact_locations` của P5B chưa có (device ref cho location local, thời điểm verify gần nhất, trạng thái lease/retention/cleanup) là migration của hội tụ (YC-HT-I-01); slice I chỉ đọc `ArtifactLocation` hiện có, không dựng aggregate location thứ hai.

## 3. Vị trí mã theo D1

I mở rộng các gói đã có trong `src/controlplane`; không dựng `src/storage/**`, `src/controlplane/storage/**` hay cây trùng aggregate nào khác.

| Đường dẫn | Vai trò |
|---|---|
| `src/controlplane/domain/storage_meta/**` | Value object, validator binding, chính sách thuần (I-01, I-03, I-11, I-12, I-13) |
| `src/controlplane/application/storage_meta/**` | Use case và port (I-02, I-04, I-07, I-08, I-10) |
| `src/controlplane/infrastructure/db/storage_meta/**` | Adapter PostgreSQL P5B; chỉ mở rộng sau migration của hội tụ (YC-HT-I-01) |
| `src/controlplane/infrastructure/storage/` | Gói mới cho adapter desktop: SQLite journal, staging path, cleanup executor (I-05, I-06, I-09) |
| `tests/unit/storage/**` | Test đơn vị, tên `test_storage_*.py` |
| `tests/integration/storage/**` | Test tích hợp hệ tệp/SQLite cục bộ, tên `test_storage_*.py` |

Mã P5B hiện có (slice chỉ đọc): `src/controlplane/domain/storage_meta/__init__.py` (dataclass `ArtifactVersion`, `ArtifactLocation`, `CleanupAuthorization`), `src/controlplane/application/storage_meta/__init__.py` (`ArtifactVersionStore`, `ArtifactLocationStore`, `CleanupAuthorizationStore`), `src/controlplane/infrastructure/db/storage_meta/__init__.py` (`PostgresStorageMetaRepository`). Ba tệp này được `tests/m2/test_p5b_artifact_metadata.py` (cần PostgreSQL) bảo vệ, nên slice chỉ thêm module mới bên cạnh và import chỉ đọc. `ArtifactLocationState` và `transition_artifact_location` nằm ở `src/controlplane/domain/statemachine` (tài nguyên dùng chung): slice chỉ import.

Import dùng một root `src/` (pytest `pythonpath = ["src"]` trong `pyproject.toml`), dạng `controlplane.…`; không dùng tiền tố `src.`. Thư mục test không thêm `__init__.py`; tiền tố `test_storage_` giữ tên tệp test duy nhất trong toàn repo.

## 4. Contract dùng và cung cấp

### 4.1. I cung cấp

| Contract | Binding | Ghi chú |
|---|---|---|
| CT-STO-001 `DeclareArtifactVersion` | `docs/parallel-delivery/bindings/i-artifact-version.json` (BINDING-I-ARTIFACT-VERSION 1.0.0; consumer A, C, E, F, G); fixture `tests/fixtures/contracts/i-artifact-version/payloads.json` | Slice I-01, I-02 |
| CT-STO-002..005, CT-STO-007..011 | Chưa có binding seam | Dùng nội bộ I hoặc qua workflow G; phân hệ khác cần gọi trực tiếp thì phải mở binding slice trước (bindings/README.md, mục seam chưa có binding) |
| CT-STO-006 `PersistVideoOutput` | Chưa có (seam F → I, bindings/README.md dòng 66) | Fail-closed: không lập slice; YC-HT-I-07 |
| Event `ArtifactLocationVerified`, `CleanupCompleted` | `docs/parallel-delivery/bindings/domain-event-envelope.json` | Phát qua outbox là wiring của hội tụ (YC-HT-I-08) |

### 4.2. I dùng

| Binding | Trường I dùng | Slice |
|---|---|---|
| `docs/parallel-delivery/bindings/g-c-i-completion.json` (CT-ORC-008, CT-ORC-009) | `output_artifact_version_id`, `output_sha256`, `cloud_location_ref`, `cloud_location_verification_ref`, `cleanup_policy_ref`, `recovery_epoch` (string), `output_naming_metadata` | I-05, I-08, I-09, I-10, I-11 |
| `docs/parallel-delivery/bindings/f-render-package.json` (CT-RND-002) | `input_artifacts` (artifact_version_id, sha256, size_bytes), `materialization_manifest`, `output_path_ref` | I-06, I-07 |
| `docs/parallel-delivery/bindings/g-activity-execution.json` (CT-WF-003, CT-WF-006) | Grant/generation cho activity storage | Wiring hội tụ (YC-HT-I-06) |
| `docs/parallel-delivery/bindings/j-provider-route.json` | Không dùng trực tiếp; account/credential Drive đi qua secret broker J ở CP7 | — |

### 4.3. Tên trường lệch giữa P5B và binding

| P5B (`domain/storage_meta/__init__.py`, bảng `cp_artifact_versions`) | Binding |
|---|---|
| `sha256_hash` | `content_sha256` |
| `mime_type` | `media_type` |
| `owner_ref` | `owner_resource_ref` |
| `lineage_ref` (một giá trị) | `lineage_refs` (mảng) |
| `retention_ref` | `retention_class` |
| `sensitivity_ref` | `sensitivity_class` |
| (không có) | `intended_storage_class`, `producer_operation_ref` |
| `CleanupAuthorization.recovery_epoch: int` | `recovery_epoch: string` (g-c-i-completion) |

Slice ánh xạ trong module mới của mình; đổi cột hoặc kiểu dữ liệu là migration của hội tụ (YC-HT-I-01). Khi mâu thuẫn, binding thắng; slice không sửa binding.

## 5. Exit gate roadmap và cách kiểm

### 5.1. Exit gate M4 (roadmap §10)

| Mã | Exit gate | Slice | Cách kiểm |
|---|---|---|---|
| EG-M4-I-1 | Không location nào thành verified nếu chưa có integrity evidence | I-03, I-04 | `tests/unit/storage/test_storage_verification.py`, `tests/unit/storage/test_storage_cloud_persist.py` |
| EG-M4-I-2 | Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified | I-08, I-09 | `tests/unit/storage/test_storage_cleanup_evaluation.py`, `tests/integration/storage/test_storage_cleanup_executor.py` (phần I của TST-E2E-INV-009, TST-DR-INV-011) |
| EG-M4-I-3 | Render tương lai chỉ có thể lấy artifact local đã verify | I-06, I-07 | `tests/unit/storage/test_storage_materialization.py`, `tests/integration/storage/test_storage_staging_paths.py` (phần I của TST-INT-INV-008) |
| EG-M4-I-4 | UI phân biệt original, processed, uncertain, failed và unavailable | I-13 (uncertain/failed/unavailable); original/processed thuộc C; màn hình thuộc H | `tests/unit/storage/test_storage_availability.py`; phần UI là YC-HT-I-05 |
| EG-M4-I-5 | Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật | Không có slice; CP7-I-01 | Chỉ đóng bằng evidence tài khoản thật; cấm dùng fake/mock (roadmap §13 Điều cấm) |
| EG-M4-I-6 | User duyệt C-I và `R2 Media Alpha` | Không có slice | PUC-I-04 |

### 5.2. Test bắt buộc M4 phần I

- INV-008 → I-07; INV-009 (phần I) và INV-011 → I-08, I-09; INV-012 (phần I) → I-05 (journal chỉ giữ secret reference), I-12 (ref không chứa credential); INV-016 → I-10.
- INV-015 không thuộc I (errata m4-ci.md mục 5).
- Upload gián đoạn trước/trong/sau side effect → I-04; same byte retry, byte khác thành version mới, hash mismatch, object missing → I-02, I-03, I-04.
- Path traversal, symlink/junction, reserved name, hashtag, Unicode, collision → I-06, I-11.
- Desktop restart/reconcile và cleanup authorization cũ bị từ chối → I-05, I-10, I-08, I-09.
- Source removed, Sensitive Image Set, clip không bị safety transform → thuộc C/E, ngoài phạm vi I.

### 5.3. Gate sau M4 mà I phục vụ

- M6 (roadmap §14 "Output sync/cleanup"): CT-STO-006 chờ binding F → I (YC-HT-I-07); dùng lại khối cleanup I-08/I-09.
- M7 `R5 Unattended Beta` ("Resume, retry, reconcile và cleanup qua fault suite"): I-05, I-09, I-10 cung cấp khối nền; fault suite end-to-end thuộc hội tụ/M7.
- G04 đầy đủ (M7) và G05 restore (roadmap §19): CP7-I-01, CP7-I-04; PUC-I-06.

## 6. Mục mở và quyết định mặc định (D8)

| Mã | Chủ đề | Mặc định đã chọn | Lý do |
|---|---|---|---|
| D8-I-01 | Giá trị `policy_decision` | `new_version`, `matched_existing` (chuỗi) | Binding khai `string`; fixture dùng `new_version`; bindings/README.md D8 mục 2 |
| D8-I-02 | Integrity khi Drive thiếu checksum (roadmap §10 điểm mở 4) | SHA-256 byte cục bộ là identity; verify cloud bằng checksum metadata của provider nếu có, nếu không thì tải lại và tính SHA-256 | ADR-0006 ("nếu metadata hash không đủ thì tải kiểm tra"); phương pháp cụ thể chốt ở G04 qua CP7-I-01 |
| D8-I-03 | Working set | `max_video_sets = 5`; `max_bytes` là cấu hình bắt buộc, không có mặc định | CT-STO-004; ngưỡng byte phải đo trên máy mục tiêu (PUC-I-03) |
| D8-I-04 | Kiểu `recovery_epoch` | Chuỗi opaque ở tầng application; với P5B tạm so bằng `str()` | CT-STO-009 "opaque"; binding g-c-i-completion kiểu string; đổi cột qua YC-HT-I-01 |
| D8-I-05 | Schema local journal | I tự tạo bảng trong tệp SQLite desktop, `journal_mode=WAL`, `synchronous=FULL` | CT-STO-005; không phải migration PostgreSQL; ưu tiên độ bền khi crash |
| D8-I-06 | Ngữ nghĩa retention class | `original`, `reusable`, `output` luôn giữ, bản local chỉ dọn khi đã cloud verified; `per_video`/`temporary` dọn được sau completion | CT-STO mục 12 điểm 7, ADR-0010; thời hạn cụ thể chờ PUC-I-01 |
| D8-I-07 | Sanitize tên tệp | Luật Windows: ký tự cấm, tên reserved, bỏ dấu chấm/khoảng trắng cuối, chuẩn hoá NFC; độ dài tối đa là tham số cấu hình | CT-STO-011 yêu cầu deterministic; máy mục tiêu là desktop Windows |
| D8-I-08 | Ngày đặt tên folder | Caller truyền ngày; allocator không đọc đồng hồ hệ thống | Múi giờ production chưa chốt (ROADMAP-OPEN-004, PUC-I-02) |
| D8-I-09 | Placement | Theo rule cấu hình; quota tính theo quota domain; không có tỷ lệ mặc định | CT-STO-010, RM-RISK-007; ROADMAP-OPEN-010 chờ PUC-I-01 |
| D8-I-10 | Cách thêm mã | Module mới cạnh P5B, không sửa ba `__init__.py` P5B; test đặt tên `test_storage_*.py` | Giữ tests/m2 xanh; các slice chạy song song mà không đụng tệp nhau |
| D8-I-11 | Availability của `CLEANUP_ELIGIBLE`/`CLEANUP_AUTHORIZED` | Xếp `unavailable` cho consumer mới | Tránh lease mới trên bản sắp dọn (CT-STO-008 điều 2) |
| D8-I-12 | `intended_storage_class` | Chỉ `local_staging`, `local_cache` là lớp dọn được; giá trị khác coi là không dọn được | Fixture i-artifact-version dùng `local_staging`; binding khai `string` |

Đối chiếu bốn điểm còn mở của roadmap §10:

| Điểm mở roadmap §10 | Xử lý trong kế hoạch I |
|---|---|
| Storage placement/quota thật của bốn tài khoản sau G04 | D8-I-09 (rule cấu hình, không hard-code); giá trị thật chờ PUC-I-01, đo ở CP7-I-02 |
| Retention original, reusable, temporary, log và evidence | D8-I-06 cho artifact; thời hạn cụ thể và retention của log/evidence chờ PUC-I-01 |
| Scale dataset cho catalog/index | Thuộc phân hệ C (catalog/index), ngoài phạm vi I; kế hoạch I không chọn mặc định |
| Checksum/integrity khi Drive không có cùng checksum cho mọi tệp | D8-I-02; phương pháp cụ thể chốt ở G04 qua CP7-I-01 |

### 6.1. Danh sách chờ user (pendingUserCheckpoint)

Không mục nào dưới đây được coi là đã duyệt.

- PUC-I-01 — ROADMAP-OPEN-010: thời hạn retention (original, reusable, temporary, output, log và evidence) và placement/quota thật của bốn tài khoản Drive. Hạn: trước unattended cleanup.
- PUC-I-02 — ROADMAP-OPEN-004: múi giờ production dùng cho tên folder `YY-MM-DD`. Hạn: trước khi bật lịch production.
- PUC-I-03 — Ngưỡng byte của working set và disk reserve trên máy mục tiêu (đo ở CP7-I-03). Hạn: trước khi nghiệm thu hiệu năng render.
- PUC-I-04 — User duyệt C-I và `R2 Media Alpha` (EG-M4-I-6).
- PUC-I-05 — D5 cho CP7 (tài khoản Drive thật) và USER-CKPT-D9-D10 trước CP-2b.
- PUC-I-06 — ROADMAP-OPEN-012: phạm vi backup/restore (G05). Hạn: trước khi bật writer/cleanup sau restore.

## 7. Thư viện (D10)

Các slice không cần thư viện mới; chỉ dùng stdlib `hashlib`, `sqlite3`, `pathlib`, `os`, `unicodedata`, `dataclasses`, `datetime`, `re`, `typing`. Adapter Drive thật (CP7) dùng các phiên bản đã khoá trong `pyproject.toml` gốc: `google-api-python-client==2.200.0`, `google-auth-oauthlib==1.4.1` (đã khoá cho proof M1-P3, không đổi M1-R1). Persistence PostgreSQL dùng `psycopg[binary]==3.3.5` đã có. Kế hoạch không đề xuất thêm gói; nếu CP7 cần gói khác thì phải trình USER-CKPT-D9-D10, không thêm âm thầm.

## 8. Việc cần tài nguyên thật (CP7)

Chỉ chạy sau khi user duyệt D5. Tài khoản thật chỉ được dùng qua secret broker J; không mở, chép hay in bí mật.

- CP7-I-01 — Drive adapter thật trong `src/controlplane/infrastructure/storage/`: upload resumable với file ID cấp trước, `409`, session hết hạn, thiếu checksum/tải kiểm, token revoked; đóng phần M4 của G04 (EG-M4-I-5).
- CP7-I-02 — Đo quota và API project thật của bốn tài khoản, lập cấu hình placement cho I-12 (PUC-I-01).
- CP7-I-03 — Đo byte/disk/I-O của working set trên máy mục tiêu (PUC-I-03).
- CP7-I-04 — G05 restore drill: recovery epoch mới, journal cũ, output Drive mới hơn bản backup, worker cũ reconnect, cleanup sau restore.
- CP7-I-05 — Kiểm cleanup/staging trên desktop thật (junction, symlink, quyền tệp, ổ đĩa khác).

## 9. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

Tài nguyên dùng chung chỉ gói hội tụ được sửa; slice I không chạm vào.

- YC-HT-I-01 — Migration: thêm vào `cp_artifact_versions` các cột `intended_storage_class`, `producer_operation_ref` và `lineage_refs` dạng mảng; bảng upload receipt (operation_key, artifact_version_id, object_id cấp trước, trạng thái có `OUTCOME_UNKNOWN`) được ghi trước upload theo ADR-0006; lease materialization; revision của placement và working set policy; đổi `cp_cleanup_authorizations.recovery_epoch` sang text opaque; thêm vào `cp_artifact_locations` và dataclass `ArtifactLocation` các trường CT-STO-002 còn thiếu: device ref cho location local, thời điểm verify gần nhất, trạng thái lease/retention/cleanup.
- YC-HT-I-02 — Đăng ký gói `controlplane.infrastructure.storage` trong `src/controlplane/pyproject.toml` (package-dir/packages; manifest thuộc LOCK-DEPENDENCY-UNIVERSE).
- YC-HT-I-03 — Composition root (`src/controlplane/api/main.py`, `src/main.py`): wiring service I; đường dẫn SQLite journal và staging root lấy từ cấu hình J.
- YC-HT-I-04 — State machine: giữ nguyên CT-STATE-012; quyết định caller và đường ghi `CLEANUP_AUTHORIZED → DELETED` sau khi cleanup executor chạy, vì `ArtifactLocationStore.validate_transition` của P5B đang chặn `DELETED`.
- YC-HT-I-05 — UI shell và control API (H): màn hình C-I (upload, verify, lỗi, cleanup state) và hiển thị availability của I-13 qua read model.
- YC-HT-I-06 — Workflow G: activity Persist/Materialize/Cleanup/Reconcile theo `g-activity-execution.json`; completion chỉ commit sau khi có kết quả CT-STO-006.
- YC-HT-I-07 — Binding seam F → I cho CT-STO-006 `PersistVideoOutput` (bindings/README.md dòng 66); khi chưa có binding thì I không lập slice.
- YC-HT-I-08 — Outbox/event: phát `ArtifactLocationVerified` và `CleanupCompleted` theo `domain-event-envelope.json`.
- YC-HT-I-09 — Catalog `docs/10-test-strategy.md`: đăng ký test ID mới của slice I nếu cần dùng làm oracle (errata m4-ci, quy tắc dùng).

## 10. DAG slice và song song

- Wave 1 (song song): I-01, I-03, I-05, I-08, I-11, I-12, I-13.
- Wave 2: I-02 (sau I-01); I-04, I-07, I-10 (sau I-03); I-06 (sau I-05).
- Wave 3: I-09 (sau I-06 và I-08).

Mỗi slice sở hữu tệp riêng nên dùng lock `LOCK-I-<số>`; `LOCK-SRC-STORAGE` để dành cho việc sửa tệp P5B chung, do hội tụ thực hiện. Gốc của mọi slice là `CP1-CONTRACT-BINDING` và `CP2A-LAYOUT` (đã tích hợp).
