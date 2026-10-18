# Slice triển khai Phân hệ I — Lưu trữ, đồng bộ và vòng đời tệp

Nguồn: `docs/implementation/i/plan.md`. Mỗi slice là `work_package_slice`; Control biên dịch trong phong bì policy.

## Quy tắc chung cho mọi slice

- Chỉ sửa đúng các tệp liệt kê trong ownedPaths. Phong bì gồm `src/controlplane/domain/storage_meta/**`, `src/controlplane/application/storage_meta/**`, `src/controlplane/infrastructure/db/storage_meta/**`, `src/controlplane/infrastructure/storage/**`, `tests/unit/storage/**`, `tests/integration/storage/**` và `docs/delivery-evidence/<task-id viết thường>/report.md`.
- Không sửa ba tệp `__init__.py` P5B của storage_meta, `src/controlplane/domain/statemachine/**`, migration, composition root, lockfile/`pyproject.toml`, `tests/m2/**`, `ui/dist`, `App.tsx`, control API hay workflow; nhu cầu loại này gửi IMPL-PLAN-CONVERGENCE.
- Không thêm thư viện; chỉ dùng stdlib và gói đã có trong runtime khoá. Không gọi mạng, Drive, OAuth hay dịch vụ thật; không đọc `Credentials/` hay bí mật. Phân hệ khác được thay bằng fixture CP1 (`tests/fixtures/contracts/**`) và fake định nghĩa ngay trong tệp test.
- Import root `src/`, dạng `controlplane.…`, không có tiền tố `src.`. Không thêm `__init__.py` vào thư mục test.
- Test-first: viết test trước, tạo module với chữ ký đúng nhưng thân hàm `raise NotImplementedError`, chạy để thấy RED do assertion hoặc NotImplementedError; ImportError hay thiếu tệp không phải RED hợp lệ. Sau đó implement tới GREEN.
- Lệnh kiểm chạy bằng interpreter khoá của lane; ghi lệnh, exit code, kết quả RED và GREEN vào report.md của slice.
- Mỗi slice có tiêu đề cấp 3 `I-<số>: <tên>`, tiếp theo là các mục kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance (requirement, instrument, counterexample), testCommands theo đúng thứ tự này.

### I-01: Validator yêu cầu khai báo artifact version theo binding

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/storage_meta/declaration.py`
  - `tests/unit/storage/test_storage_declaration.py`
  - `docs/delivery-evidence/i-01/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-I-01`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: Module mới định nghĩa dataclass frozen `DeclareArtifactVersionRequest` (10 trường) và `DeclareArtifactVersionResult` (5 trường) đúng tên, kiểu và required của BINDING-I-ARTIFACT-VERSION 1.0.0 (CT-STO-001). Hàm `validate_declare_request(payload: dict) -> list[dict]` và `validate_declare_result(payload: dict) -> list[dict]` trả lỗi dạng `{"code": ..., "field": ...}` với code `missing_required` hoặc `wrong_type`; kiểu `sha256` là 64 ký tự hex thường; `integer` không nhận bool; trường lạ được bỏ qua (forward-compat). Không sửa `src/controlplane/domain/storage_meta/__init__.py`.
    instrument: Test đọc fixture: mọi payload `valid` trả `[]`, mọi case `invalid` trả đúng `expected_error`; thêm case có trường lạ vẫn hợp lệ và case `size_bytes=True` bị `wrong_type`.
    counterexample: Hash chữ hoa được chấp nhận; payload có trường lạ bị từ chối; tên trường lệch binding (ví dụ `sha256_hash` thay cho `content_sha256`).
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider`

### I-02: Dịch vụ khai báo version bất biến

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/storage_meta/declare_version.py`
  - `tests/unit/storage/test_storage_declare_version.py`
  - `docs/delivery-evidence/i-02/report.md`
- dependsOn: `I-01`
- resourceLocks: `LOCK-I-02`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: `DeclareArtifactVersionService.declare(payload: dict)` dùng port Protocol `ArtifactVersionCatalogPort` (`find_matching(owner_resource_ref, artifact_kind, content_sha256)`, `find_artifact_id(owner_resource_ref, artifact_kind)`, `insert_version(...)`). Service gọi `validate_declare_request` của I-01; payload lỗi thì raise `ValueError` mang code và field. Cùng owner/kind/hash → `matched_existing=True`, `policy_decision="matched_existing"`, không gọi insert. Hash khác → version mới, giữ `artifact_id` của artifact logic đã có, `policy_decision="new_version"`, `required_operation="upload"`. Không có API ghi đè version. Kết quả qua `validate_declare_result` không có lỗi. Fake in-memory định nghĩa trong tệp test (CT-STO-001, ADR-0006, D8-I-01).
    instrument: Pytest: cùng byte gọi hai lần → một version; byte khác → version thứ hai, version cũ không đổi; mọi payload invalid của fixture → ValueError đúng field.
    counterexample: Cùng byte tạo hai version; byte khác ghi đè version cũ; `matched_existing` trả về kiểu chuỗi.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider`

### I-03: Chính sách xác minh integrity của location

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/storage_meta/verification.py`
  - `tests/unit/storage/test_storage_verification.py`
  - `docs/delivery-evidence/i-03/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-I-03`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: Dataclass frozen `IntegrityObservation(object_present: bool | None, observed_sha256: str | None, observed_size_bytes: int | None, evidence_ref: str | None)`. Hàm `evaluate_integrity(expected_sha256, expected_size_bytes, observation) -> ArtifactLocationState` chỉ trả `VERIFIED` khi `object_present is True`, hash bằng expected (hex thường), size bằng nhau và `evidence_ref` không rỗng; `object_present is False` → `MISSING`; hash hoặc size lệch → `CORRUPT`; `object_present is None`, thiếu hash hoặc thiếu evidence → `OUTCOME_UNKNOWN`. Hàm `apply_integrity_outcome(current_state, current_revision, outcome)` gọi `transition_artifact_location` (import chỉ đọc từ `controlplane.domain.statemachine`) với `expected_revision=current_revision`; đi từ `MISSING`/`CORRUPT`/`OUTCOME_UNKNOWN` sang `VERIFIED` phải raise `ForbiddenTransitionError` (CT-STO-003 bước 4–5, CT-STATE-012). Không sửa statemachine.
    instrument: Pytest dạng bảng case: khớp đủ → VERIFIED; chỉ khớp size, không có hash → OUTCOME_UNKNOWN; hash lệch → CORRUPT; không có object → MISSING; MISSING→VERIFIED bị từ chối; VERIFYING→VERIFIED hợp lệ.
    counterexample: Response upload 200 không có hash vẫn thành VERIFIED; khớp tên hoặc size được coi là bằng chứng; có recovery edge từ MISSING.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider`

### I-04: Upload idempotent và reconcile OUTCOME_UNKNOWN

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/storage_meta/cloud_persist.py`
  - `tests/unit/storage/test_storage_cloud_persist.py`
  - `docs/delivery-evidence/i-04/report.md`
- dependsOn: `I-03`
- resourceLocks: `LOCK-I-04`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: Protocol `CloudObjectPort` (`reserve_object_id(namespace_ref) -> str`, `upload(object_id, artifact_version_id, content_sha256, size_bytes)`, `lookup(object_id) -> IntegrityObservation`) và `UploadReceiptPort` (`get(operation_key)`, `save(receipt)`). `PersistArtifactToCloud.execute(artifact_version_id, content_sha256, size_bytes, source_verified, namespace_ref, operation_key, grant_ref)`: (1) từ chối khi `source_verified` False hoặc `grant_ref` rỗng; (2) lưu receipt `PREPARED` gồm operation_key, artifact_version_id, content_sha256 và object_id cấp trước, TRƯỚC khi gọi upload; (3) retry cùng operation_key và cùng hash thì dùng lại object_id; cùng operation_key nhưng khác hash → ValueError; (4) upload raise `TimeoutError` → receipt `OUTCOME_UNKNOWN`, không reserve ID mới; (5) upload raise `ObjectAlreadyExistsError` (định nghĩa trong module) → lookup rồi verify, không tạo object mới; (6) sau upload luôn lookup và quyết định bằng `evaluate_integrity` của I-03; chỉ VERIFIED mới trả kết quả có `verification_evidence_ref`. `reconcile(operation_key)` lookup theo object_id đã lưu trong receipt (CT-STO-003 bước 1–3, ADR-0006).
    instrument: Pytest với fake port in-memory trong tệp test, đếm số object: timeout rồi retry → đúng một object; 409 → verify object hiện có; lookup không có hash → không VERIFIED; receipt có trước lời gọi upload.
    counterexample: Timeout rồi retry sinh object ID mới; tin response upload mà không lookup; receipt chỉ được lưu sau upload.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider`

### I-05: SQLite local journal trên desktop

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/storage/__init__.py`
  - `src/controlplane/infrastructure/storage/local_journal.py`
  - `tests/integration/storage/test_storage_local_journal.py`
  - `docs/delivery-evidence/i-05/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-I-05`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
- acceptance:
  - requirement: `__init__.py` chỉ chứa docstring một dòng (gói adapter desktop của I). `SqliteLocalJournal(db_path)` dùng `sqlite3` stdlib với `PRAGMA journal_mode=WAL` và `PRAGMA synchronous=FULL`, tự tạo bảng `local_journal_entries` (không phải migration PostgreSQL) gồm các cột theo CT-STO-005: device_ref, session_ref, job_ref, stage_ref, artifact_version_id, local_location_ref, operation_key (UNIQUE), generation, lease_ref, state, checkpoint, content_sha256, upload_session_ref, observed_at, cleanup_eligible, recovery_epoch (TEXT opaque). API: `record(entry)` upsert theo operation_key và từ chối generation nhỏ hơn bản đang có (`StaleGenerationError`); `get(operation_key)`; `list_unfinished()`; `mark_state(operation_key, generation, state, checkpoint)`; `entries_from_other_epoch(current_epoch)`. `upload_session_ref` từ chối giá trị bắt đầu bằng `http://` hoặc `https://`, chỉ lưu secret reference (ADR-0006, INV-012). Không có hàm xoá entry; không phát `VideoCompleted`; mỗi lần ghi nằm trong một transaction.
    instrument: Pytest dùng `tmp_path`: ghi, đóng, mở lại đọc đủ; transaction dở bị rollback không để lại entry; generation cũ bị từ chối; session URI dạng https bị từ chối; entry của epoch cũ được liệt kê.
    counterexample: Journal mất entry sau khi mở lại; generation cũ ghi đè generation mới; lưu session URI thô.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider`

### I-06: Staging root và an toàn đường dẫn

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/storage/staging_paths.py`
  - `tests/integration/storage/test_storage_staging_paths.py`
  - `docs/delivery-evidence/i-06/report.md`
- dependsOn: `I-05`
- resourceLocks: `LOCK-I-06`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
- acceptance:
  - requirement: `resolve_staging_path(staging_root: Path, relative_path: str) -> Path` raise `StagingPathError` khi: chuỗi rỗng; đường tuyệt đối, có ký tự ổ đĩa hoặc UNC; có thành phần `..`; có ký tự NUL hoặc ký tự cấm Windows; thành phần trùng tên reserved (CON, PRN, AUX, NUL, COM1–COM9, LPT1–LPT9, không phân biệt hoa thường, kể cả khi có phần mở rộng); bất kỳ thành phần nào đã tồn tại trên đường từ root tới đích là symlink (`Path.is_symlink()`) hoặc junction (`Path.is_junction()`); kết quả `resolve()` không nằm trong `staging_root.resolve()` (`is_relative_to`). Trả về đường tuyệt đối đã resolve (CT-STO-004, CT-STO-008 điều 5). Dùng gói `controlplane.infrastructure.storage` do I-05 tạo, không sửa `__init__.py`.
    instrument: Pytest dùng `tmp_path`: `../../x`, `C:/x`, `//server/share/x`, `CON.mp4` bị từ chối; symlink trỏ ra ngoài (tạo bằng `os.symlink`; nếu OSError do thiếu quyền thì `pytest.skip` kèm lý do); junction trỏ ra ngoài (`_winapi.CreateJunction` khi `sys.platform == "win32"`, nền tảng khác thì skip); đường hợp lệ lồng nhau được chấp nhận.
    counterexample: `..` thoát khỏi root được chấp nhận; junction trỏ ra ngoài root được chấp nhận.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider`

### I-07: Admission materialize, working set và release cho render

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/storage_meta/materialization.py`
  - `tests/unit/storage/test_storage_materialization.py`
  - `docs/delivery-evidence/i-07/report.md`
- dependsOn: `I-03`
- resourceLocks: `LOCK-I-07`
- bindingRefs:
  - `docs/parallel-delivery/bindings/f-render-package.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
- acceptance:
  - requirement: Dataclass `WorkingSetPolicy(max_bytes: int, policy_revision: str, max_video_sets: int = 5)`; `max_bytes` bắt buộc, không có mặc định (D8-I-03, PUC-I-03). `admit_materialization(policy, active_sets, request) -> AdmissionDecision` trả `ADMITTED` hoặc `DEFERRED` kèm reason: DEFERRED khi số set đang hoạt động (tính cả output chưa sync, ADR-0006) ≥ `max_video_sets` hoặc tổng expected bytes vượt `max_bytes`; request prefetch (`is_prefetch=True`) chỉ ADMITTED khi sau khi nhận vẫn không vượt cả hai giới hạn. `release_for_render(input_artifacts: list[dict], local_locations: dict[str, ArtifactLocation]) -> list[ArtifactLocation]`: mỗi phần tử input_artifacts (artifact_version_id, sha256, size_bytes theo RenderPackage) phải có location state `VERIFIED` với `observed_hash == sha256` và `observed_size_bytes == size_bytes`; nếu không thì raise `RenderInputNotVerifiedError` nêu artifact_version_id (CT-STO-004, INV-008). `ArtifactLocation` import chỉ đọc từ `controlplane.domain.storage_meta`.
    instrument: Pytest: set thứ 6 bị DEFERRED; vượt byte bị DEFERRED; prefetch bị DEFERRED khi đầy; input_artifacts lấy từ payload valid của fixture, location AVAILABLE_UNVERIFIED hoặc hash sai bị từ chối, VERIFIED khớp được nhận.
    counterexample: Render nhận location chưa verify; working set vượt 5 set; output chưa sync không bị tính vào hạn mức.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider`

### I-08: Đánh giá cleanup và kiểm tra authorization

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/storage_meta/cleanup_evaluation.py`
  - `tests/unit/storage/test_storage_cleanup_evaluation.py`
  - `docs/delivery-evidence/i-08/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-I-08`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
  - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: `evaluate_cleanup(request: CleanupEvaluationRequest) -> CleanupEvaluation` (CT-STO-007) trả decision `eligible`/`deferred`/`forbidden`, tuple `reason_codes` và `earliest_cleanup_at` tuỳ chọn. Quy tắc: storage class khác `local_staging`/`local_cache` → forbidden `NOT_LOCAL_STAGING`; location không ở `VERIFIED` hoặc `CLEANUP_ELIGIBLE` → forbidden `LOCATION_NOT_VERIFIED`; retention `original`/`reusable`/`output` mà `cloud_copy_verified` False → forbidden `DURABLE_COPY_NOT_VERIFIED` (INV-009); có lease/consumer hoạt động → deferred `ACTIVE_LEASE`; thiếu cả completion_ref lẫn superseded_ref → deferred `NO_COMPLETION_EVIDENCE`; request epoch khác current epoch → forbidden `STALE_RECOVERY_EPOCH`. `check_cleanup_authorization(authorization, location, current_recovery_epoch: str, now: datetime, path_within_staging: bool, active_lease: bool) -> tuple[bool, tuple[str, ...]]` yêu cầu đủ điều kiện CT-STO-008: location_id, artifact_version_id và hash khớp; location state `CLEANUP_AUTHORIZED`; không có lease; `now < datetime.fromisoformat(authorization.expires_at)` (P5B khai `expires_at: str`, không so trực tiếp chuỗi với `datetime`), nếu `now` bằng hoặc sau hạn thì reason `EXPIRED`; `expires_at` không parse được hoặc không có tzinfo, hoặc `now` không có tzinfo → trả `(False, ("INVALID_EXPIRY",))`, không raise (fail-closed); cùng epoch (so `str(authorization.recovery_epoch) == current_recovery_epoch`, D8-I-04); `path_within_staging` True. Dataclass P5B `CleanupAuthorization`, `ArtifactLocation` chỉ import.
    instrument: Pytest bảng case cho từng reason code và từng điều kiện authorization; dùng `output_sha256` và `recovery_epoch` lấy từ payload valid của fixture. Thêm case `expires_at` là chuỗi ISO 8601 có múi giờ (ví dụ `2026-10-18T10:00:00+00:00`): `now` trước hạn → hợp lệ; `now` bằng hoặc sau hạn → `EXPIRED`; `expires_at` không parse được, `expires_at` không có múi giờ hoặc `now` naive → `INVALID_EXPIRY` và không raise.
    counterexample: Output chưa cloud verified vẫn eligible; authorization hết hạn, sai epoch, sai hash hoặc khác location vẫn hợp lệ; original bị coi là tệp trung gian; so sánh trực tiếp chuỗi `expires_at` với `datetime` (TypeError) hoặc so theo thứ tự chuỗi; `expires_at` hỏng làm hàm raise thay vì trả không hợp lệ.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider`

### I-09: Thực thi cleanup local có fencing

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/storage/cleanup_executor.py`
  - `tests/integration/storage/test_storage_cleanup_executor.py`
  - `docs/delivery-evidence/i-09/report.md`
- dependsOn: `I-06`, `I-08`
- resourceLocks: `LOCK-I-09`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
  - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: `LocalCleanupExecutor(staging_root: Path).execute(authorization, location, relative_path, current_recovery_epoch, now, active_lease) -> CleanupResult(deleted: bool, reason_codes: tuple[str, ...])`. Thứ tự xử lý: `resolve_staging_path` của I-06 (lỗi → không xoá, reason `PATH_OUTSIDE_STAGING`); `check_cleanup_authorization` của I-08 với `path_within_staging=True`; xác nhận đích là tệp thường (thư mục → `NOT_A_FILE`); đọc tệp tính SHA-256 bằng `hashlib`, so với `authorization.artifact_hash` (lệch → `HASH_MISMATCH`); cuối cùng `Path.unlink()`. OSError khi xoá → `deleted=False`, reason `DELETE_FAILED`, không raise, vì lỗi xoá không đảo completion ledger. Không dùng `shutil.rmtree`, không xoá thư mục, không ghi state DB (YC-HT-I-04) (CT-STO-008, ADR-0010, INV-011).
    instrument: Pytest dùng `tmp_path`: authorization hợp lệ xoá đúng tệp; tệp ngoài root, hash khác, epoch cũ, đã hết hạn, lease đang hoạt động → tệp còn nguyên; đích là thư mục → không xoá.
    counterexample: Xoá tệp có hash khác authorization; xoá ngoài staging root; ném exception làm caller rollback completion.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider`

### I-10: Reconciliation sau restart/restore và recovery epoch

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/application/storage_meta/reconciliation.py`
  - `tests/unit/storage/test_storage_reconciliation.py`
  - `docs/delivery-evidence/i-10/report.md`
- dependsOn: `I-03`
- resourceLocks: `LOCK-I-10`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
  - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: Hàm thuần `reconcile(snapshot: ReconcileSnapshot) -> tuple[ReconcileFinding, ...]` (CT-STO-009). Input gồm: versions (artifact_version_id, content_sha256, size_bytes); cloud locations (location_id, artifact_version_id, provider_object_ref); cloud objects quan sát được (provider_object_ref, observed_sha256, observed_size_bytes); journal entries (operation_key, artifact_version_id, generation, recovery_epoch); stage generation hiện hành (operation_key → generation); completion ledger (video_job_id, output_artifact_version_id, output_sha256, cloud_location_ref); current_recovery_epoch. Finding code: `CLOUD_OBJECT_MISSING`, `HASH_MISMATCH`, `ORPHAN_PROVIDER_OBJECT`, `DUPLICATE_PROVIDER_OBJECT`, `JOURNAL_GENERATION_MISMATCH`, `STALE_EPOCH_ENTRY`, `COMPLETION_WITHOUT_VERIFIED_OUTPUT`. Entry của epoch cũ luôn là `STALE_EPOCH_ENTRY` kể cả khi generation trùng (INV-016), chỉ được gắn action `REISSUE_UNDER_NEW_EPOCH`. Hàm không mutation, không xoá, không cấp grant. Kết quả sắp xếp ổn định theo (code, ref).
    instrument: Pytest mỗi code một case; input không lệch → tuple rỗng; gọi hai lần cùng input → kết quả bằng nhau; ledger lấy trường từ payload valid của fixture.
    counterexample: Entry epoch cũ trùng generation được áp dụng; ledger báo completed nhưng không có cloud object khớp hash mà không bị báo; reconcile tự xoá object trùng.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider`

### I-11: Cấp phát folder và tên tệp output

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/storage_meta/output_naming.py`
  - `tests/unit/storage/test_storage_output_naming.py`
  - `docs/delivery-evidence/i-11/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-I-11`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
  - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: `allocate_output_folder(session_date: date, completed_sessions_before_today: int, session_has_completed_video: bool) -> str | None`: phiên đầu tiên có video hoàn thành → `YY-MM-DD`; phiên hợp lệ thứ n+1 → `YY-MM-DD (n)`; session không có video hoàn thành → None. `allocate_output_filename(title, hashtags, extension, existing_names, supports_hash, max_filename_length) -> OutputName` (sanitized_filename, collision_sequence, display_title, display_hashtags, hash_mapping): chuẩn hoá NFC; bỏ ký tự điều khiển; thay ký tự cấm Windows `< > : " / \ | ? *` bằng `_`; bỏ dấu chấm và khoảng trắng ở cuối; tên reserved (CON, PRN, AUX, NUL, COM1–COM9, LPT1–LPT9) được thêm hậu tố `_`; yêu cầu 3–4 hashtag (số khác → ValueError); giữ `#` khi `supports_hash`, nếu không thì thay bằng chuỗi cố định và ghi `hash_mapping`; cắt theo `max_filename_length` mà không cắt giữa ký tự; trùng tên → thêm ` (2)`, ` (3)` trước phần mở rộng; display metadata giữ nguyên bản gốc. Cùng input luôn cho cùng output. Ngày do caller truyền, không đọc đồng hồ hệ thống (CT-STO-011, D8-I-07, D8-I-08).
    instrument: Pytest: folder của phiên 1/2/3; session rỗng → None; title chứa `../`, `CON`, emoji, tiếng Việt dạng tổ hợp; 2 hoặc 5 hashtag → ValueError; `supports_hash=False` có mapping; va chạm tên.
    counterexample: Tạo folder cho session không có video; tên `CON.mp4` lọt qua; filename chứa `/`; hai lần chạy cùng input ra tên khác.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider`

### I-12: Chính sách placement theo loại dữ liệu

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/storage_meta/placement.py`
  - `tests/unit/storage/test_storage_placement.py`
  - `docs/delivery-evidence/i-12/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-I-12`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: Dataclass `PlacementRule(artifact_kind, namespace_ref, primary_account_ref, fallback_account_refs: tuple[str, ...])` và `StoragePlacementPolicy(policy_revision, rules, quota_domain_by_account: dict[str, str], reserve_ratio: float)`. `decide_placement(policy, artifact_kind, size_bytes, used_bytes_by_quota_domain, capacity_bytes_by_quota_domain) -> PlacementDecision` (account_ref, namespace_ref, policy_revision, used_fallback) hoặc raise `PlacementRejected(code)`. Kind không có rule → `NO_RULE` (fail-closed); account thiếu quota domain → `UNKNOWN_QUOTA_DOMAIN`; chọn primary nếu `used + size ≤ capacity × (1 − reserve_ratio)` của quota domain, nếu không thì thử fallback theo thứ tự; các account cùng quota domain dùng chung một capacity (không cộng); hết chỗ → `NO_CAPACITY`. Không hard-code tỷ lệ, dung lượng hay số account; ref chỉ là chuỗi tham chiếu, từ chối ref chứa `token=`, `secret` hoặc `://` (CT-STO-010, D8-I-09, INV-012).
    instrument: Pytest: kind `voice` lấy từ fixture có rule; kind lạ bị từ chối; 4 account cùng quota domain không cộng capacity; fallback khi primary chạm reserve; ref chứa credential bị từ chối.
    counterexample: Coi 4 tài khoản là một ổ gộp quota; kind lạ rơi vào account mặc định; tỷ lệ phân bổ hoặc 20 TB bị hard-code.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider`

### I-13: Phân loại availability cho read model

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/domain/storage_meta/availability.py`
  - `tests/unit/storage/test_storage_availability.py`
  - `docs/delivery-evidence/i-13/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-I-13`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: `classify_location(state: ArtifactLocationState) -> str` ánh xạ đủ 11 trạng thái: `VERIFIED` → `available`; `DECLARED`, `MATERIALIZING`, `AVAILABLE_UNVERIFIED`, `VERIFYING`, `OUTCOME_UNKNOWN` → `uncertain`; `CORRUPT` → `failed`; `MISSING`, `CLEANUP_ELIGIBLE`, `CLEANUP_AUTHORIZED`, `DELETED` → `unavailable` (D8-I-11); giá trị không biết → ValueError. `classify_artifact(states: list[ArtifactLocationState]) -> str` theo thứ tự ưu tiên available > uncertain > failed > unavailable; danh sách rỗng → `unavailable`. Phân biệt original/processed thuộc C; module chỉ cung cấp availability cho read model H (EG-M4-I-4, YC-HT-I-05). `ArtifactLocationState` import chỉ đọc.
    instrument: Pytest tham số hoá trên mọi thành viên của `ArtifactLocationState` (nếu enum có thêm thành viên chưa ánh xạ thì test fail) và kiểm thứ tự ưu tiên khi tổng hợp.
    counterexample: OUTCOME_UNKNOWN hiển thị là available; CORRUPT bị gộp vào unavailable khiến UI không phân biệt được failed.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cacheprovider`
