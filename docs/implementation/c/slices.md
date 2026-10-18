# Slice triển khai Phân hệ C — Danh mục media và hook

> Nguồn: `docs/implementation/c/plan.md`. Mọi slice là `work_package_slice`; Control biên dịch trong phong bì policy.

## Ràng buộc chung

- ownedPaths chỉ trong `src/catalog/**`, `tests/unit/catalog/**` và tệp bằng chứng `docs/delivery-evidence/<task-id viết thường>/report.md`.
- Import root `src/`: import `catalog...` và `controlplane...` (chỉ đọc), không tiền tố `src.`.
- Không sửa migration, composition root, lockfile, `tests/m2`, `ui/dist`, `App.tsx`, state machine dùng chung, control API, binding hay fixture CP1; không thêm thư viện; không gọi mạng, dịch vụ thật hay đọc `Credentials/`.
- Dùng fixture CP1 (đọc bằng `json` và `pathlib`, gốc repo là `Path(__file__).resolve().parents[3]`) và fake đặt trong chính tệp test cho phân hệ khác; không tạo `conftest.py` hay `__init__.py` trong `tests/`.
- Test-first: tạo stub tối thiểu rồi chứng kiến RED là AssertionError đúng oracle (không phải ImportError) trước khi cài đặt; ghi RED, lệnh, exit code vào report của slice.
- testCommands chạy bằng interpreter khoá của lane.

## Danh sách slice

### C-01: Khung gói catalog và định danh media

- kind: work_package_slice
- phạm vi: tạo package `catalog`; `src/catalog/domain/identity.py` gồm `MediaKind` (StrEnum `image`, `clip`, `audio`), `CanonicalFingerprint` (64 ký tự hex thường, sai thì `ValueError`), `RightsStatus` (`known`, `unknown`, `disputed`) và `RightsAssessment` (frozen: `status`, `evidence_refs`), `ProvenanceRelation` (`hero_image`, `inline_image`, `embedded_clip`, `official_social_clip`, `user_imported`), `ProvenanceEntry` (frozen: `source_ref`, `article_ref`, `event_ref`, `original_locator`, `observed_at`, `relation`), `MediaAsset` (frozen: `media_asset_id`, `kind`, `fingerprint: CanonicalFingerprint | None`, `provenance: tuple[ProvenanceEntry, ...]`, `rights`, `index_revision: int`) với `with_provenance(entry)` (trả bản mới, chỉ append, bỏ qua entry trùng) và `with_fingerprint(fp)` (chỉ khi đang `None`, ngược lại `ValueError`); `src/catalog/ports/repositories.py` khai báo `MediaAssetRepository(Protocol)` với `get(media_asset_id)`, `find_by_fingerprint(fingerprint)`, `find_by_discovery_id(discovery_id)`, `save(asset, discovery_id=None)`.
- ownedPaths:
  - `src/catalog/__init__.py`
  - `src/catalog/domain/__init__.py`
  - `src/catalog/application/__init__.py`
  - `src/catalog/ports/__init__.py`
  - `src/catalog/domain/identity.py`
  - `src/catalog/ports/repositories.py`
  - `tests/unit/catalog/test_catalog_identity.py`
  - `docs/delivery-evidence/c-01/report.md`
- dependsOn: `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`
- resourceLocks: `LOCK-SRC-CATALOG`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: fingerprint bất biến sau khi đặt (gán thuộc tính gây `dataclasses.FrozenInstanceError`, `with_fingerprint` lần hai gây `ValueError`); `with_provenance` giữ mọi entry cũ; `content_sha256` của payload valid trong fixture được nhận làm fingerprint, case `content_hash_uppercase` bị từ chối; rights `unknown` được lưu, không chặn.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider`
  - counterexample: gán lại fingerprint; thêm provenance làm mất entry cũ; nhận hash in hoa; dựng `src/storage` hoặc import `src.catalog`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider`

### C-02: Trục trạng thái đọc và phân loại usability

- kind: work_package_slice
- phạm vi: `src/catalog/domain/states.py` gồm StrEnum đúng tên contract: `DiscoveryState` (`DISCOVERED`, `ACQUIRING`, `CATALOGED`, `FAILED`), `RenditionState` (`DECLARED`, `PROCESSING`, `READY`, `FAILED`, `OUTCOME_UNKNOWN`), `Availability` (`AVAILABLE`, `MISSING`, `CORRUPT`, `RECOVERING`, `UNAVAILABLE_SOURCE`), `ImageSafetyState` (`NOT_ASSESSED`, `ASSESSING`, `SAFE`, `TRANSFORM_REQUIRED`, `UNCERTAIN`, `DETECTION_FAILED`, `UNREADABLE`, `TRANSFORMING`, `PROCESSED_READY`, `TRANSFORM_FAILED`), `Usability` (`usable`, `usable_with_warning`, `not_usable`); hàm `classify_safety(kind, safety)` theo D8-C-05 (chỉ `image`; `clip`/`audio` trả `usable` khi `safety is None`, ngược lại `ValueError`) và `classify_availability(availability)` (`AVAILABLE`, `UNAVAILABLE_SOURCE` → `usable`; `MISSING`, `CORRUPT`, `RECOVERING` → `not_usable`). Không có hàm chuyển trạng thái (D8-C-04, CONV-C-07).
- ownedPaths:
  - `src/catalog/domain/states.py`
  - `tests/unit/catalog/test_catalog_states.py`
  - `docs/delivery-evidence/c-02/report.md`
- dependsOn: `C-01`
- resourceLocks: `LOCK-C-02`
- bindingRefs:
  - `docs/parallel-delivery/bindings/c-d-media-candidates.json`
  - `tests/fixtures/contracts/c-d-media-candidates/payloads.json`
- acceptance:
  - requirement: tập giá trị mỗi enum bằng đúng tập tên trong CT-STATE-005/006; `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED` → `usable_with_warning`, không bao giờ `usable`; `UNREADABLE` → `not_usable`; `UNAVAILABLE_SOURCE` → `usable`; module không có tên nào bắt đầu bằng `transition`.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider`
  - counterexample: ánh xạ `UNCERTAIN` thành `SAFE` hoặc `usable`; nguồn bị remove làm media mất eligibility; thêm đồ thị chuyển trạng thái trùng `controlplane.domain.statemachine`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider`

### C-03: Hợp nhất media discovery và provenance

- kind: work_package_slice
- phạm vi: `src/catalog/application/discovery.py` gồm `DiscoveryObservation` (frozen: `discovery_id`, `kind: MediaKind`, `provenance: ProvenanceEntry`, `fingerprint: CanonicalFingerprint | None`, `locator_validated: bool`), `Disposition` (StrEnum `new_asset`, `new_provenance`, `duplicate_observation`, `rejected`), `DiscoveryResult` (frozen: `media_asset_id: str | None`, `disposition`, `acquisition_required: bool`) và `register_discovery(repo: MediaAssetRepository, observation, new_asset_id: str) -> DiscoveryResult`. Quy tắc theo CT-MED-001: `locator_validated` sai → `rejected`, không gọi `repo.save`; `discovery_id` đã ghi → `duplicate_observation` với cùng asset (idempotent); fingerprint trùng asset có sẵn và provenance mới → `new_provenance` (append qua `with_provenance`); fingerprint và provenance đều trùng → `duplicate_observation`; còn lại → `new_asset` (`acquisition_required` đúng khi fingerprint là `None`). Fake `MediaAssetRepository` trong bộ nhớ đặt trong tệp test.
- ownedPaths:
  - `src/catalog/application/discovery.py`
  - `tests/unit/catalog/test_catalog_discovery.py`
  - `docs/delivery-evidence/c-03/report.md`
- dependsOn: `C-01`
- resourceLocks: `LOCK-C-03`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: bài repost cùng fingerprint, khác `article_ref` → `new_provenance` và asset giữ cả hai provenance (phần C của `TST-INT-INV-005`, `TST-E2E-002`); gửi lại cùng `discovery_id` không tạo asset mới; locator chưa validate không ghi gì; fingerprint lấy từ `content_sha256` của payload valid trong fixture.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider`
  - counterexample: tạo asset mới cho byte đã có; ghi đè provenance cũ; lặp discovery tạo bản ghi trùng; nhận locator chưa qua safety validation.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider`

### C-04: Rendition bất biến và chặn safety transform cho clip

- kind: work_package_slice
- phạm vi: `src/catalog/domain/renditions.py` gồm `RenditionKind` (`original`, `normalized`, `blurred`, `recolored`, `thumbnail`, `extracted_frame`), `Rendition` (frozen: `rendition_ref`, `media_asset_id`, `kind`, `artifact_version_ref`, `source_artifact_version_ref`, `transformation_spec_revision`, `processor_version`, `lineage: tuple[str, ...]`), `transformation_fingerprint(rendition)` (SHA-256 bằng `hashlib` trên `json.dumps(..., sort_keys=True)` của `source_artifact_version_ref`, `kind`, `transformation_spec_revision`, `processor_version`), `RenditionRejected(ValueError)` có thuộc tính `code`, và `RenditionSet` bất biến cho một asset với `register(rendition, media_kind) -> tuple[RenditionSet, Rendition]`: cùng fingerprint trả rendition đã có (dedupe CT-MED-003), không thay rendition cũ; `blurred`/`recolored` cho `MediaKind.clip` → `RenditionRejected` mã `CLIP_SAFETY_TRANSFORM_FORBIDDEN`; `original` thứ hai khác artifact → `RenditionRejected` mã `ORIGINAL_ALREADY_REGISTERED`. Chỉ đăng ký rendition đã có output artifact.
- ownedPaths:
  - `src/catalog/domain/renditions.py`
  - `tests/unit/catalog/test_catalog_renditions.py`
  - `docs/delivery-evidence/c-04/report.md`
- dependsOn: `C-01`
- resourceLocks: `LOCK-C-04`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: original tách khỏi rendition; đăng ký lại cùng input trả cùng `rendition_ref`; clip không nhận safety transform (test bắt buộc roadmap §10); rendition cũ không bị thay artifact hay ref.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider`
  - counterexample: thay artifact của rendition cũ; tạo hai rendition cho cùng transformation; nhận `blurred` cho clip.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider`

### C-05: Kho visual hook và audio hook có revision

- kind: work_package_slice
- phạm vi: `src/catalog/domain/hooks.py` gồm `HookKind` (`visual_hook`, `audio_hook`) và `HookRevision` (frozen: `hook_id`, `revision: int`, `kind`, `artifact_version_ref`, `tags: tuple[str, ...]`, `description`, `note`, `enabled: bool`, `provenance` cố định `user_imported`, `technical_metadata: tuple[tuple[str, str], ...]`); `src/catalog/application/hooks.py` gồm `HookHistory` (lưu mọi revision trong bộ nhớ, `get(hook_id, revision)`, `latest(hook_id)`), `import_hook(history, ...)` (revision 1, CT-HOOK-001) và `update_hook_metadata(history, hook_id, expected_revision, *, tags=None, description=None, note=None, enabled=None)` (CT-HOOK-002: revision mới bằng cũ cộng 1; `expected_revision` lệch → `controlplane.domain.concurrency.RevisionConflictError`; không có tham số đổi `kind` hay `artifact_version_ref`). Visual và audio không có trường ghép cặp.
- ownedPaths:
  - `src/catalog/domain/hooks.py`
  - `src/catalog/application/hooks.py`
  - `tests/unit/catalog/test_catalog_hooks.py`
  - `docs/delivery-evidence/c-05/report.md`
- dependsOn: `C-01`
- resourceLocks: `LOCK-C-05`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
- acceptance:
  - requirement: revision cũ vẫn đọc được sau khi sửa metadata (job đã snapshot dùng revision cũ); sửa metadata không đổi `artifact_version_ref`; `expected_revision` cũ bị từ chối bằng `RevisionConflictError`; visual và audio được nhập, sửa và đọc độc lập.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider`
  - counterexample: sửa metadata ghi đè revision cũ; đổi `artifact_version_ref` tại chỗ; bắt buộc ghép cặp visual/audio; tự định nghĩa lỗi revision trùng `controlplane.domain.concurrency`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider`

### C-06: Truy vấn media candidate cho D

- kind: work_package_slice
- phạm vi: `src/catalog/application/candidate_query.py` gồm `ContractError(ValueError)` (thuộc tính `code`, `field`); `parse_media_candidate_query(payload: dict)` kiểm trường bắt buộc và kiểu theo entity `MediaCandidateQuery` của binding (thiếu → `missing_required`, sai kiểu → `wrong_type`, bỏ qua trường lạ); `validate_media_candidate(payload: dict)` kiểm output theo entity `MediaCandidate` (cùng mã lỗi; `semantic_match_components` phải là object); `CandidateIndexEntry` (frozen: `media_asset_id`, `rendition_ref`, `artifact_version_ref`, `kind`, `roles`, `entities`, `topics`, `scenes`, `provenance`, `technical_fitness`, `availability: Availability`, `safety_rights_status`, `usage_refs`); `query_media_candidates(query, entries) -> tuple[list[dict], str | None]`: lọc theo `media_kinds` và `roles`; bỏ entry có `classify_availability` là `not_usable`; bỏ entry có `usage_refs` giao `excluded_usage_refs`; `semantic_match_components` là dict tách `entity`, `topic`, `scene` (tỉ lệ khớp 0..1 với `scene_intent.get('entities'|'topics'|'scenes', [])`), không có điểm tổng; `reason_codes` không rỗng; tối đa `limit` phần tử; `page_cursor` dạng `offset:<n>`.
- ownedPaths:
  - `src/catalog/application/candidate_query.py`
  - `tests/unit/catalog/test_catalog_candidate_query.py`
  - `docs/delivery-evidence/c-06/report.md`
- dependsOn: `C-02`
- resourceLocks: `LOCK-C-06`
- bindingRefs:
  - `docs/parallel-delivery/bindings/c-d-media-candidates.json`
  - `tests/fixtures/contracts/c-d-media-candidates/payloads.json`
- acceptance:
  - requirement: mọi payload valid của `MediaCandidateQuery` trong fixture parse được; case `missing_safety_policy_revision`, `limit_as_string` trả đúng `expected_error.code` và `field`; case `single_opaque_score`, `missing_reason_codes` của `MediaCandidate` bị `validate_media_candidate` từ chối đúng mã; mọi candidate trả về qua `validate_media_candidate`; entry `UNAVAILABLE_SOURCE` vẫn được trả (CT-SRC-003, CT-MED-009); trường lạ trong query bị bỏ qua.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider`
  - counterexample: trả một điểm tổng mơ hồ; bỏ media lịch sử khi source bị remove; trả quá `limit`; C tự chọn media thay D.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider`

### C-07: Read model MediaAssetView cho UI

- kind: work_package_slice
- phạm vi: `src/catalog/application/asset_view.py` gồm `DisplayStatus` (`original`, `processed`, `uncertain`, `failed`, `unavailable`) và `build_media_asset_view(asset, renditions, image_safety, availability, semantics, technical, usage_summary) -> dict` trả các nhóm của CT-MED-002 (`identity`, `provenance`, `semantics`, `technical`, `safety`, `rights`, `availability`, `renditions`, `usage`) và `display_status` theo D8-C-09: availability `not_usable` → `unavailable`; `UNREADABLE` hoặc `TRANSFORM_FAILED` → `failed`; `UNCERTAIN` hoặc `DETECTION_FAILED` → `uncertain`; `PROCESSED_READY` hoặc có rendition `normalized`/`blurred`/`recolored` → `processed`; còn lại → `original`. Hàm thuần, không I/O.
- ownedPaths:
  - `src/catalog/application/asset_view.py`
  - `tests/unit/catalog/test_catalog_asset_view.py`
  - `docs/delivery-evidence/c-07/report.md`
- dependsOn: `C-02`, `C-04`
- resourceLocks: `LOCK-C-07`
- bindingRefs:
  - `docs/parallel-delivery/bindings/c-d-media-candidates.json`
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: năm trạng thái hiển thị phân biệt được (phần dữ liệu của exit gate UI §10); rights `unknown`/`disputed` hiển thị kèm evidence; provenance đầy đủ mọi entry; `TRANSFORM_FAILED` không bao giờ là `processed`; `MISSING` luôn là `unavailable`.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider`
  - counterexample: gộp uncertain vào original; hiển thị processed cho transform thất bại; ẩn rights không chắc chắn; dựng màn hình UI trong slice.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider`

### C-08: Phân giải phiên bản render được

- kind: work_package_slice
- phạm vi: `src/catalog/application/renderable.py` gồm `ArtifactVersionView` (frozen, do fake I cấp: `artifact_version_ref`, `content_sha256`, `size_bytes`, `media_type`, `location_state: controlplane.domain.statemachine.ArtifactLocationState`, `is_local: bool`), `RenderableResolution` (frozen: `artifact_version_ref`, `location_state`, `content_sha256`, `size_bytes`, `media_type`, `materialization_required`, `safety_state`, `usability: Usability`, `reason_codes: tuple[str, ...]`) và `resolve_renderable_version(rendition, artifact, expected_sha256, media_kind, image_safety, availability) -> RenderableResolution`: `location_state` khác `VERIFIED` → `not_usable` với `ARTIFACT_MISSING` (MISSING), `ARTIFACT_CORRUPT` (CORRUPT) hoặc `ARTIFACT_NOT_VERIFIED` (trạng thái khác); `content_sha256` khác `expected_sha256` → `not_usable` và `HASH_MISMATCH`; kết hợp `classify_availability` và `classify_safety`, lấy mức xấu nhất (`not_usable` > `usable_with_warning` > `usable`); `materialization_required = not artifact.is_local`. Module không ghi location state.
- ownedPaths:
  - `src/catalog/application/renderable.py`
  - `tests/unit/catalog/test_catalog_renderable.py`
  - `docs/delivery-evidence/c-08/report.md`
- dependsOn: `C-02`, `C-04`
- resourceLocks: `LOCK-C-08`
- bindingRefs:
  - `docs/parallel-delivery/bindings/i-artifact-version.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
  - `docs/parallel-delivery/bindings/f-render-package.json`
- acceptance:
  - requirement: tham số hoá mọi giá trị `ArtifactLocationState`, chỉ `VERIFIED` không bị `not_usable` (phần C của `TST-INT-INV-008`); hash lệch → `HASH_MISMATCH`; `UNAVAILABLE_SOURCE` cùng `VERIFIED` → `usable`; ảnh `UNCERTAIN` → `usable_with_warning` (phần C của `TST-E2E-011`); `UNREADABLE` → `not_usable`; `content_sha256` lấy từ payload valid của fixture i-artifact-version.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider`
  - counterexample: cho render artifact `AVAILABLE_UNVERIFIED`, `MISSING` hoặc `CORRUPT`; bỏ qua hash mismatch; C tự đổi location state; source bị remove làm mất eligibility.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider`

### C-09: Ghi MediaUsage trong unit of work completion

- kind: work_package_slice
- phạm vi: `src/catalog/ports/usage.py` gồm `UsageKind` (`production`, `technical`), `MediaUsageRecord` (frozen: `completion_id`, `video_job_id`, `media_asset_id`, `role`, `usage_kind`, tuỳ chọn `rendition_ref`, `artifact_version_ref`, `selection_rationale`) và `MediaUsageRepository(Protocol)` (`exists(completion_id, media_asset_id, role, usage_kind) -> bool`, `add(record) -> None`); `src/catalog/application/usage.py` gồm `MediaUsageRecorder(repository_factory)` với `record_production_usage(uow: IUnitOfWork, completion_id: str, request: dict) -> int` (đọc `video_job_id` và `media_usage_manifest` theo entity `CommitVideoCompletionRequest` của binding; thiếu thì `ValueError` có thuộc tính `code='missing_required'`; mỗi phần tử cần `media_asset_id` và `role`; bỏ qua bản ghi đã `exists` để replay không tăng; trả số bản ghi mới; repository lấy qua `repository_factory(uow)`; không gọi `uow.commit()` hay `uow.rollback()`) và `record_technical_usage(uow, record)` chỉ nhận `UsageKind.technical`. `IUnitOfWork` import từ `controlplane.domain.interfaces.uow`. Test dùng fake `IUnitOfWork` có staging: commit mới làm bản ghi nhìn thấy, rollback bỏ staging.
- ownedPaths:
  - `src/catalog/ports/usage.py`
  - `src/catalog/application/usage.py`
  - `tests/unit/catalog/test_catalog_usage.py`
  - `docs/delivery-evidence/c-09/report.md`
- dependsOn: `C-01`
- resourceLocks: `LOCK-C-09`
- bindingRefs:
  - `docs/parallel-delivery/bindings/g-c-i-completion.json`
  - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- acceptance:
  - requirement: rollback completion → không có production usage (phần C của `TST-WF-INV-017`); replay cùng `completion_id` → số production usage không tăng (phần C của `TST-WF-INV-010`); technical usage không tăng production count; recorder không gọi commit/rollback; payload valid của fixture ghi đúng số phần tử `media_usage_manifest`.
  - instrument: `python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider`
  - counterexample: usage nhìn thấy trước commit; retry tăng đếm hai lần; C tự commit transaction của G; technical usage tính như production; G ghi trực tiếp bảng của C.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider`
