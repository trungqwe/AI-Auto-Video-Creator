# Báo cáo bằng chứng C-03

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `5b5d282e1862f8ff9a19831147bcf3ceec7fcf7e`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-03 trong `docs/implementation/c/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider` (chạy với stub ở bước 1-5)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `9 failed, 6 passed, 7 subtests passed in 0.10s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/catalog/test_catalog_discovery.py::RepostProvenanceTests::test_repost_same_fingerprint_other_article_appends_provenance`: `AssertionError: Disco[21 chars]t_id=None, disposition=<Disposition.REJECTED: [35 chars]alse) != Disco[21 chars]t_id='asset-1', disposition=<Disposition.NEW_A[42 chars]alse)`
  - `FAILED tests/unit/catalog/test_catalog_discovery.py::RepostProvenanceTests::test_same_fingerprint_and_provenance_is_duplicate_observation`: `AssertionError: 0 != 1`
  - `SUBFAILED(fingerprint=CanonicalFingerprint(value='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef')) tests/unit/catalog/test_catalog_discovery.py::DiscoveryIdempotencyTests::test_resent_discovery_id_returns_same_asset_without_new_record`: `AssertionError: <Disposition.REJECTED: 'rejected'> != <Disposition.NEW_ASSET: 'new_asset'>`
  - `SUBFAILED(fingerprint=None) tests/unit/catalog/test_catalog_discovery.py::DiscoveryIdempotencyTests::test_resent_discovery_id_returns_same_asset_without_new_record`: `AssertionError: <Disposition.REJECTED: 'rejected'> != <Disposition.NEW_ASSET: 'new_asset'>`
  - `FAILED tests/unit/catalog/test_catalog_discovery.py::LocatorValidationTests::test_unvalidated_repost_does_not_touch_existing_asset`: `AssertionError: 0 != 1`
  - `FAILED tests/unit/catalog/test_catalog_discovery.py::NewAssetTests::test_different_fingerprint_creates_new_asset`: `AssertionError: Disco[21 chars]t_id=None, disposition=<Disposition.REJECTED: [35 chars]alse) != Disco[21 chars]t_id='asset-2', disposition=<Disposition.NEW_A[42 chars]alse)`
  - `SUBFAILED(fingerprint=CanonicalFingerprint(value='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef')) tests/unit/catalog/test_catalog_discovery.py::NewAssetTests::test_new_asset_acquisition_required_only_without_fingerprint`: `AssertionError: Disco[21 chars]t_id=None, disposition=<Disposition.REJECTED: [35 chars]alse) != Disco[21 chars]t_id='asset-1', disposition=<Disposition.NEW_A[42 chars]alse)`
  - `SUBFAILED(fingerprint=None) tests/unit/catalog/test_catalog_discovery.py::NewAssetTests::test_new_asset_acquisition_required_only_without_fingerprint`: `AssertionError: Disco[21 chars]t_id=None, disposition=<Disposition.REJECTED: [35 chars]alse) != Disco[21 chars]t_id='asset-1', disposition=<Disposition.NEW_A[41 chars]True)`
  - `FAILED tests/unit/catalog/test_catalog_discovery.py::NewAssetTests::test_unfingerprinted_discoveries_never_merge`: `AssertionError: <Disposition.REJECTED: 'rejected'> != <Disposition.NEW_ASSET: 'new_asset'>`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, TypeError, AttributeError, NameError hay lỗi collection nào (DispositionEnumTests, ObservationValidationTests và test_unvalidated_locator_is_rejected_without_save PASS).

## Thay đổi

- `src/catalog/application/discovery.py`: Định nghĩa `Disposition` (StrEnum: new_asset, new_provenance, duplicate_observation, rejected), `DiscoveryObservation` (frozen slots dataclass với runtime validation), `DiscoveryResult` (frozen slots dataclass) và hàm nghiệp vụ `register_discovery` triển khai đầy đủ 5 nhánh theo CT-MED-001.
- `tests/unit/catalog/test_catalog_discovery.py`: Tệp kiểm thử đơn vị với fake repository nội bộ `FakeMediaAssetRepository` ghi nhận các cuộc gọi get/find/save và 6 test suite: `DispositionEnumTests`, `RepostProvenanceTests`, `DiscoveryIdempotencyTests`, `LocatorValidationTests`, `NewAssetTests`, `ObservationValidationTests`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider` | 0 | 11 passed, 11 subtests passed in 0.03s |
| 2 | `python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider` | 0 | 20 passed, 37 subtests passed in 0.04s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Thứ tự quy tắc: locator_validated → discovery_id → fingerprint → new_asset; rejected không gọi bất kỳ phương thức repo nào.
2. duplicate_observation theo discovery_id trả acquisition_required = (asset.fingerprint is None) để retry trả cùng kết quả như lần đầu.
3. Fingerprint và provenance cùng trùng → duplicate_observation, không gọi save và không gắn discovery_id mới.
4. Không bao giờ hợp nhất theo fingerprint None; mỗi discovery chưa có fingerprint là asset riêng chờ acquisition.
5. Asset mới có rights `unknown` không evidence (D8-C-06), index_revision = 1; kind của asset có sẵn được giữ khi thêm provenance.
6. Không kiểm trùng new_asset_id; cấp ID là trách nhiệm caller; adapter seam A→C CT-MED-001 chờ binding CONV-C-05.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-010
- ROADMAP-OPEN-011
(Không tự ý ghi nhận bất kỳ mục nào ở trên là đã được người dùng phê duyệt.)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa pyproject.toml, uv.lock, migration, fixture, port repositories.py.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib.
- Không gọi dịch vụ thật.
- Không tạo conftest.py hay __init__.py trong tests/.
