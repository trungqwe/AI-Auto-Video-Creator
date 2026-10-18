# Báo cáo bằng chứng C-04

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `0ad4cbf564484cec02bbeffa18ea3796349b4a91`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-04 trong `docs/implementation/c/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `25 failed, 14 passed, 14 subtests passed in 0.15s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn từ bước 7:
  - `FAILED tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_kind_is_coerced_and_unknown_kind_rejected`: `AssertionError: 'blurred' is not <RenditionKind.BLURRED: 'blurred'>`
  - `SUBFAILED(lineage=['artifact-version-original']) tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_lineage_must_be_tuple_of_str`: `AssertionError: ValueError not raised`
  - `SUBFAILED(lineage=(1,)) tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_lineage_must_be_tuple_of_str`: `AssertionError: ValueError not raised`
  - `SUBFAILED(lineage=None) tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_lineage_must_be_tuple_of_str`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='rendition_ref', value='') tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_rendition_requires_output_artifact_and_refs`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='rendition_ref', value=None) tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_rendition_requires_output_artifact_and_refs`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='media_asset_id', value='') tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_rendition_requires_output_artifact_and_refs`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='media_asset_id', value=None) tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_rendition_requires_output_artifact_and_refs`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='artifact_version_ref', value='') tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_rendition_requires_output_artifact_and_refs`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='artifact_version_ref', value=None) tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_rendition_requires_output_artifact_and_refs`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='source_artifact_version_ref', value='') tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_rendition_requires_output_artifact_and_refs`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='source_artifact_version_ref', value=None) tests/unit/catalog/test_catalog_renditions.py::RenditionValueTests::test_rendition_requires_output_artifact_and_refs`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='source_artifact_version_ref') tests/unit/catalog/test_catalog_renditions.py::TransformationFingerprintTests::test_each_transformation_input_changes_fingerprint`: `AssertionError: '0000000000000000000000000000000000000000000000000000000000000000' == '0000000000000000000000000000000000000000000000000000000000000000'`
  - `SUBFAILED(field='kind') tests/unit/catalog/test_catalog_renditions.py::TransformationFingerprintTests::test_each_transformation_input_changes_fingerprint`: `AssertionError: '0000000000000000000000000000000000000000000000000000000000000000' == '0000000000000000000000000000000000000000000000000000000000000000'`
  - `SUBFAILED(field='transformation_spec_revision') tests/unit/catalog/test_catalog_renditions.py::TransformationFingerprintTests::test_each_transformation_input_changes_fingerprint`: `AssertionError: '0000000000000000000000000000000000000000000000000000000000000000' == '0000000000000000000000000000000000000000000000000000000000000000'`
  - `SUBFAILED(field='processor_version') tests/unit/catalog/test_catalog_renditions.py::TransformationFingerprintTests::test_each_transformation_input_changes_fingerprint`: `AssertionError: '0000000000000000000000000000000000000000000000000000000000000000' == '0000000000000000000000000000000000000000000000000000000000000000'`
  - `FAILED tests/unit/catalog/test_catalog_renditions.py::TransformationFingerprintTests::test_matches_sha256_of_sorted_json`: `AssertionError: '0000000000000000000000000000000000000000000000000000000000000000' != 'd2d72fa4e25d8c82b9f7cbf8f0699f0c82d6187c4db6f9973626e8d71483ac5d'`
  - `FAILED tests/unit/catalog/test_catalog_renditions.py::DedupeTests::test_rendition_of_other_asset_is_rejected`: `AssertionError: RenditionRejected not raised`
  - `FAILED tests/unit/catalog/test_catalog_renditions.py::DedupeTests::test_rendition_ref_reused_for_other_transformation_is_rejected`: `AssertionError: RenditionRejected not raised`
  - `FAILED tests/unit/catalog/test_catalog_renditions.py::DedupeTests::test_same_transformation_returns_existing_rendition`: `AssertionError: 'rendition-blurred-2' != 'rendition-blurred-1'`
  - `SUBFAILED(kind='blurred') tests/unit/catalog/test_catalog_renditions.py::ClipSafetyTransformTests::test_clip_rejects_blurred_and_recolored`: `AssertionError: RenditionRejected not raised`
  - `SUBFAILED(kind='recolored') tests/unit/catalog/test_catalog_renditions.py::ClipSafetyTransformTests::test_clip_rejects_blurred_and_recolored`: `AssertionError: RenditionRejected not raised`
  - `FAILED tests/unit/catalog/test_catalog_renditions.py::OriginalSeparationTests::test_same_original_is_idempotent`: `AssertionError: Rendition(rendition_ref='rendition-original', media_asset_id='asset-1', kind=<RenditionKind.ORIGINAL: 'original'>, artifact_version_ref='artifact-version-original', source_artifact_version_ref='artifact-version-original', transformation_spec_revision='none', processor_version='none', lineage=()) is not Rendition(rendition_ref='rendition-original', media_asset_id='asset-1', kind=<RenditionKind.ORIGINAL: 'original'>, artifact_version_ref='artifact-version-original', source_artifact_version_ref='artifact-version-original', transformation_spec_revision='none', processor_version='none', lineage=())`
  - `SUBFAILED(variant='other_source') tests/unit/catalog/test_catalog_renditions.py::OriginalSeparationTests::test_second_original_with_other_artifact_is_rejected`: `AssertionError: RenditionRejected not raised`
  - `SUBFAILED(variant='same_fingerprint') tests/unit/catalog/test_catalog_renditions.py::OriginalSeparationTests::test_second_original_with_other_artifact_is_rejected`: `AssertionError: RenditionRejected not raised`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, AttributeError, TypeError, NameError hay lỗi collection nào (EnumValueTests, ModuleSurfaceTests, FixtureBindingTests và các test không phụ thuộc mutation logic đều PASS).

## Thay đổi

- `src/catalog/domain/renditions.py`:
  - Định nghĩa các hằng số mã lỗi: `CLIP_SAFETY_TRANSFORM_FORBIDDEN`, `ORIGINAL_ALREADY_REGISTERED`, `RENDITION_REF_CONFLICT`, `MEDIA_ASSET_MISMATCH`.
  - Enum `RenditionKind` (StrEnum): `ORIGINAL`, `NORMALIZED`, `BLURRED`, `RECOLORED`, `THUMBNAIL`, `EXTRACTED_FRAME`.
  - Hằng số kiểm tra: `_SAFETY_TRANSFORMS` (frozenset gồm BLURRED và RECOLORED), `_REQUIRED_REFS`.
  - Lớp ngoại lệ `RenditionRejected` kế thừa `ValueError`, mang mã `code`.
  - Dataclass frozen slots `Rendition` với `__post_init__` xác thực chặt chẽ: ép kiểu và kiểm tra `kind`, bắt buộc 4 trường ref chuỗi không rỗng (`rendition_ref`, `media_asset_id`, `artifact_version_ref`, `source_artifact_version_ref`), xác thực chuỗi cho `transformation_spec_revision` và `processor_version`, và đảm bảo `lineage` là tuple các chuỗi.
  - Hàm `transformation_fingerprint(rendition)` tính SHA-256 từ chuỗi JSON đã sắp xếp khóa (`json.dumps(..., sort_keys=True)`) trên 4 thuộc tính định danh biến đổi: `source_artifact_version_ref`, `kind`, `transformation_spec_revision`, `processor_version` (loại trừ output refs và lineage).
  - Dataclass frozen slots `RenditionSet` với `__post_init__` kiểm tra tính hợp lệ của tập rendition, và phương thức `register(rendition, media_kind)` thực hiện đầy đủ thứ tự kiểm định: xác thực asset ID, chặn safety transform đối với clip, kiểm soát tính bất biến của original (idempotent nếu cùng artifact, từ chối nếu khác artifact), deduplicate theo fingerprint (trả về rendition có sẵn), phát hiện xung đột `rendition_ref`, và trả về tập mới bất biến.
- `tests/unit/catalog/test_catalog_renditions.py`:
  - 8 test class bao phủ toàn diện: `EnumValueTests`, `RenditionValueTests`, `TransformationFingerprintTests`, `DedupeTests`, `ClipSafetyTransformTests`, `OriginalSeparationTests`, `FixtureBindingTests`, `ModuleSurfaceTests`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider` | 0 | 20 passed, 33 subtests passed in 0.03s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 3 | `python -c "import pathlib; fs=['src/catalog/domain/renditions.py','tests/unit/catalog/test_catalog_renditions.py','docs/delivery-evidence/c-04/report.md']; data={f: pathlib.Path(f).read_bytes() for f in fs}; bad=[(f,i) for f in fs for i,l in enumerate(data[f].decode('utf-8').split('\n'),1) if l.rstrip('\r')!=l.rstrip()]; assert not bad, bad; assert all(d.endswith(b'\n') and not d.startswith(b'\xef\xbb\xbf') for d in data.values()); print('OK')"` | 0 | OK |

## Quyết định mặc định (D8)

1. Thứ tự kiểm register: asset → clip safety → original → dedupe fingerprint → xung đột ref; đảm bảo phát hiện vi phạm sớm nhất theo quy chuẩn domain.
2. Original lặp cùng artifact trả original cũ (idempotent), khác artifact bị từ chối kể cả khi trùng fingerprint (chặn thay đổi gốc ban đầu).
3. Mã bổ sung `RENDITION_REF_CONFLICT`, `MEDIA_ASSET_MISMATCH` là GIẢ ĐỊNH để chặn thay artifact qua tái dùng ref và chặn gán nhầm asset.
4. Chỉ nhận rendition có `artifact_version_ref` không rỗng; `RenditionState` không gắn vào `Rendition` (đồ thị trạng thái chờ gói hội tụ CONV-C-07).
5. `media_kind` truyền theo lời gọi, không lưu trong `RenditionSet`; quality report và safety state của CT-MED-003 chờ binding E→C (CONV-C-05).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-010
- ROADMAP-OPEN-011
(Không tự ý ghi nhận bất kỳ mục nào ở trên là đã được người dùng phê duyệt.)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa fixture, migration, state machine, pyproject.toml, lockfile.
- Không thêm thư viện ngoài stdlib (`dataclasses`, `enum`, `hashlib`, `json`).
- Không gọi dịch vụ thật.
- Không tạo `conftest.py` hay `__init__.py` trong `tests/`.
