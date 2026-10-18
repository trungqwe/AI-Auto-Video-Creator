# Báo cáo bằng chứng C-01

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `815bebb15b565c4a750854b4218a3296c7be2904`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-01 trong `docs/implementation/c/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider` (chạy với stub ở bước 5-6)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `29 failed, 10 passed, 16 subtests passed in 0.17s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn từ bước 12:
  - `FAILED tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_fingerprint_is_frozen`: `AssertionError: FrozenInstanceError not raised`
  - `SUBFAILED(value='0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF') tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_rejects_non_canonical_values`: `AssertionError: ValueError not raised`
  - `SUBFAILED(value='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcde') tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_rejects_non_canonical_values`: `AssertionError: ValueError not raised`
  - `SUBFAILED(value='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0') tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_rejects_non_canonical_values`: `AssertionError: ValueError not raised`
  - `SUBFAILED(value='gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg') tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_rejects_non_canonical_values`: `AssertionError: ValueError not raised`
  - `SUBFAILED(value='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcde\n') tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_rejects_non_canonical_values`: `AssertionError: ValueError not raised`
  - `SUBFAILED(value='') tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_rejects_non_canonical_values`: `AssertionError: ValueError not raised`
  - `SUBFAILED(value=None) tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_rejects_non_canonical_values`: `AssertionError: ValueError not raised`
  - `SUBFAILED(value=123) tests/unit/catalog/test_catalog_identity.py::CanonicalFingerprintTests::test_rejects_non_canonical_values`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::FixtureBindingTests::test_uppercase_content_hash_case_is_rejected`: `AssertionError: ValueError not raised`
  - `SUBFAILED(content_sha256='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef') tests/unit/catalog/test_catalog_identity.py::FixtureBindingTests::test_valid_payload_content_sha256_is_accepted`: `AssertionError: None != CanonicalFingerprint(value='0123456789abc[48 chars]def')`
  - `SUBFAILED(field='media_asset_id') tests/unit/catalog/test_catalog_identity.py::MediaAssetFingerprintTests::test_attribute_assignment_raises_frozen_instance_error`: `AssertionError: FrozenInstanceError not raised`
  - `SUBFAILED(field='kind') tests/unit/catalog/test_catalog_identity.py::MediaAssetFingerprintTests::test_attribute_assignment_raises_frozen_instance_error`: `AssertionError: FrozenInstanceError not raised`
  - `SUBFAILED(field='fingerprint') tests/unit/catalog/test_catalog_identity.py::MediaAssetFingerprintTests::test_attribute_assignment_raises_frozen_instance_error`: `AssertionError: FrozenInstanceError not raised`
  - `SUBFAILED(field='provenance') tests/unit/catalog/test_catalog_identity.py::MediaAssetFingerprintTests::test_attribute_assignment_raises_frozen_instance_error`: `AssertionError: FrozenInstanceError not raised`
  - `SUBFAILED(field='rights') tests/unit/catalog/test_catalog_identity.py::MediaAssetFingerprintTests::test_attribute_assignment_raises_frozen_instance_error`: `AssertionError: FrozenInstanceError not raised`
  - `SUBFAILED(field='index_revision') tests/unit/catalog/test_catalog_identity.py::MediaAssetFingerprintTests::test_attribute_assignment_raises_frozen_instance_error`: `AssertionError: FrozenInstanceError not raised`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::MediaAssetFingerprintTests::test_raw_string_fingerprint_is_rejected`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::MediaAssetFingerprintTests::test_with_fingerprint_sets_once_and_never_overwrites`: `AssertionError: None != CanonicalFingerprint(value='0123456789abc[48 chars]def')`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::ProvenanceTests::test_provenance_entry_is_frozen`: `AssertionError: FrozenInstanceError not raised`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::ProvenanceTests::test_with_provenance_returns_new_copy_and_appends`: `AssertionError: unexpectedly identical: MediaAsset(...)`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::ProvenanceTests::test_with_provenance_skips_duplicate_entry`: `AssertionError: 1 != 2`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::RightsTests::test_rights_assessment_is_frozen`: `AssertionError: FrozenInstanceError not raised`
  - `SUBFAILED(method='get') tests/unit/catalog/test_catalog_identity.py::RepositoryPortTests::test_method_signatures`: `AssertionError: unexpectedly None : MediaAssetRepository.get is missing`
  - `SUBFAILED(method='find_by_fingerprint') tests/unit/catalog/test_catalog_identity.py::RepositoryPortTests::test_method_signatures`: `AssertionError: unexpectedly None : MediaAssetRepository.find_by_fingerprint is missing`
  - `SUBFAILED(method='find_by_discovery_id') tests/unit/catalog/test_catalog_identity.py::RepositoryPortTests::test_method_signatures`: `AssertionError: unexpectedly None : MediaAssetRepository.find_by_discovery_id is missing`
  - `SUBFAILED(method='save') tests/unit/catalog/test_catalog_identity.py::RepositoryPortTests::test_method_signatures`: `AssertionError: unexpectedly None : MediaAssetRepository.save is missing`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::RepositoryPortTests::test_method_signatures`: `AssertionError: unexpectedly None : MediaAssetRepository.save is missing`
  - `FAILED tests/unit/catalog/test_catalog_identity.py::RepositoryPortTests::test_protocol_members`: `AssertionError: Items in the second set but not the first: 'get', 'find_by_fingerprint', 'find_by_discovery_id', 'save'`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, NotImplementedError, AttributeError, TypeError hay lỗi collection nào (EnumValueTests, test_accepts_64_lowercase_hex và PackageLayoutTests PASS).

## Thay đổi

- 7 tệp mã nguồn và kiểm thử đã tạo:
  - `src/catalog/__init__.py`: docstring package catalog.
  - `src/catalog/domain/__init__.py`: docstring domain subpackage.
  - `src/catalog/application/__init__.py`: docstring application subpackage.
  - `src/catalog/ports/__init__.py`: docstring ports subpackage.
  - `src/catalog/domain/identity.py`: các domain symbol gồm `MediaKind` (StrEnum: IMAGE, CLIP, AUDIO), `CanonicalFingerprint` (frozen slots dataclass bọc SHA-256 hex thường 64 ký tự), `RightsStatus` (StrEnum: KNOWN, UNKNOWN, DISPUTED), `RightsAssessment` (frozen slots dataclass), `ProvenanceRelation` (StrEnum: HERO_IMAGE, INLINE_IMAGE, EMBEDDED_CLIP, OFFICIAL_SOCIAL_CLIP, USER_IMPORTED), `ProvenanceEntry` (frozen slots dataclass), `MediaAsset` (aggregate root frozen slots dataclass với `with_provenance` append-only bỏ qua entry trùng và `with_fingerprint` đặt một lần không ghi đè).
  - `src/catalog/ports/repositories.py`: port `MediaAssetRepository` (typing.Protocol gồm 4 phương thức `get`, `find_by_fingerprint`, `find_by_discovery_id`, `save(asset, discovery_id=None)`).
  - `tests/unit/catalog/test_catalog_identity.py`: 8 class kiểm thử bao phủ toàn bộ invariant: `EnumValueTests`, `CanonicalFingerprintTests`, `FixtureBindingTests`, `MediaAssetFingerprintTests`, `ProvenanceTests`, `RightsTests`, `RepositoryPortTests`, `PackageLayoutTests`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider` | 0 | 20 passed, 37 subtests passed in 0.04s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `CanonicalFingerprint` là frozen dataclass bọc `value`, không kế thừa `str`, để chuỗi thô không lọt vào `MediaAsset`.
2. `observed_at` là chuỗi ISO-8601 do nguồn cấp, chưa parse.
3. `source_ref`, `article_ref`, `event_ref` có thể `None` (user_imported, official social clip).
4. `with_provenance` với entry trùng trả lại chính asset, không tăng `index_revision`; `with_provenance` không đổi `index_revision`.
5. `with_fingerprint` lần hai raise `ValueError` kể cả cùng giá trị.
6. Protocol không `runtime_checkable`; fake repository để C-03.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-010
- ROADMAP-OPEN-011
(Không tự ý ghi nhận bất kỳ mục nào ở trên là đã được người dùng phê duyệt.)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa `pyproject.toml`, `uv.lock`, migration, fixture.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib.
- Không gọi dịch vụ thật.
- Không tạo `src/storage`, `conftest.py` hay `__init__.py` trong `tests/`.
