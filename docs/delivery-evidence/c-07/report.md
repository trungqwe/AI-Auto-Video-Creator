# Báo cáo bằng chứng C-07

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `cbd256247045936fd2b5b07c3eca8fbfac7b737d`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-07 trong `docs/implementation/c/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `207 failed, 11 passed in 1.72s`
- Danh sách FAILED/SUBFAILED đại diện kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::ViewGroupTests::test_identity_group`: `AssertionError: 'identity' not found in {} : missing group identity`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::ViewGroupTests::test_provenance_keeps_every_entry_in_order`: `AssertionError: 'provenance' not found in {} : missing group provenance`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::ViewGroupTests::test_renditions_group_lists_every_rendition`: `AssertionError: 'renditions' not found in {} : missing group renditions`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::ViewGroupTests::test_safety_group`: `AssertionError: 'safety' not found in {} : missing group safety`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::ViewGroupTests::test_availability_group`: `AssertionError: 'availability' not found in {} : missing group availability`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::ViewGroupTests::test_pass_through_groups_are_copies`: `AssertionError: 'semantics' not found in {} : missing group semantics`
  - `SUBFAILED(group='display_status') tests/unit/catalog/test_catalog_asset_view.py::ViewGroupTests::test_view_has_every_ct_med_002_group`: `AssertionError: 'display_status' not found in {} : missing group display_status`
  - `SUBFAILED(status=<RightsStatus.UNKNOWN: 'unknown'>) tests/unit/catalog/test_catalog_asset_view.py::RightsVisibilityTests::test_uncertain_rights_are_shown_with_evidence`: `AssertionError: 'rights' not found in {} : missing group rights`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::RightsVisibilityTests::test_known_rights_keep_evidence`: `AssertionError: 'rights' not found in {} : missing group rights`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::DisplayStatusPriorityTests::test_five_statuses_are_distinguishable`: `AssertionError: 'display_status' not found in {} : missing group display_status`
  - `SUBFAILED(availability=<Availability.AVAILABLE: 'AVAILABLE'>, safety=<ImageSafetyState.UNREADABLE: 'UNREADABLE'>, kinds=(<RenditionKind.ORIGINAL: 'original'>,)) tests/unit/catalog/test_catalog_asset_view.py::DisplayStatusPriorityTests::test_matches_priority_oracle`: `AssertionError: <DisplayStatus.ORIGINAL: 'original'> != <DisplayStatus.FAILED: 'failed'>`
  - `SUBFAILED(kind=<MediaKind.IMAGE: 'image'>, safety=<ImageSafetyState.SAFE: 'SAFE'>) tests/unit/catalog/test_catalog_asset_view.py::DisplayStatusPriorityTests::test_missing_is_always_unavailable`: `AssertionError: <DisplayStatus.ORIGINAL: 'original'> != <DisplayStatus.UNAVAILABLE: 'unavailable'>`
  - `SUBFAILED(availability=<Availability.AVAILABLE: 'AVAILABLE'>) tests/unit/catalog/test_catalog_asset_view.py::DisplayStatusPriorityTests::test_transform_failed_is_never_processed`: `AssertionError: <DisplayStatus.ORIGINAL: 'original'> != <DisplayStatus.FAILED: 'failed'>`
  - `SUBFAILED(safety=<ImageSafetyState.UNCERTAIN: 'UNCERTAIN'>) tests/unit/catalog/test_catalog_asset_view.py::DisplayStatusPriorityTests::test_uncertain_is_not_merged_into_original`: `AssertionError: <DisplayStatus.ORIGINAL: 'original'> != <DisplayStatus.UNCERTAIN: 'uncertain'>`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::DisplayStatusPriorityTests::test_processing_renditions_mark_processed`: `AssertionError: <DisplayStatus.ORIGINAL: 'original'> != <DisplayStatus.PROCESSED: 'processed'>`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::InputValidationTests::test_rejects_non_asset`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::InputValidationTests::test_rejects_non_rendition_set`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::InputValidationTests::test_rejects_renditions_of_other_asset`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::InputValidationTests::test_rejects_invalid_safety_pairing`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::InputValidationTests::test_rejects_unknown_availability`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_asset_view.py::FixtureBindingTests::test_candidate_fixture_maps_into_view`: `AssertionError: 'identity' not found in {} : missing group identity`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, AttributeError, TypeError, NameError, KeyError hay lỗi collection nào (`DisplayStatusEnumTests` và `ModuleSurfaceTests` đều PASS).

## Thay đổi

- `src/catalog/application/asset_view.py`:
  - Enum `DisplayStatus` (StrEnum): `ORIGINAL`, `PROCESSED`, `UNCERTAIN`, `FAILED`, `UNAVAILABLE`.
  - Các tập hằng số kiểm tra: `_FAILED_SAFETY`, `_UNCERTAIN_SAFETY`, `_PROCESSED_RENDITIONS`, `_UNCERTAIN_RIGHTS`.
  - Hàm `resolve_display_status(kind, image_safety, availability, renditions)` thuần không I/O: kiểm tra tính hợp lệ của renditions và cặp `(kind, image_safety)` qua `classify_safety`; phân giải trạng thái hiển thị theo đúng thứ tự ưu tiên D8-C-09 (`unavailable` > `failed` > `uncertain` > `processed` > `original`).
  - Hàm `build_media_asset_view(asset, renditions, image_safety, availability, semantics, technical, usage_summary)`: kiểm tra hợp lệ kiểu và ràng buộc dữ liệu đầu vào (asset phải là `MediaAsset`, renditions phải là `RenditionSet` và cùng `media_asset_id`, các nhóm mapping là `Mapping`); tổng hợp đủ 9 nhóm CT-MED-002 (`identity`, `provenance`, `semantics`, `technical`, `safety`, `rights`, `availability`, `renditions`, `usage`) cùng `display_status`. Mọi giá trị trả về là kiểu JSON thuần túy, an toàn tuần tự hóa.
- `tests/unit/catalog/test_catalog_asset_view.py`:
  - 8 lớp test bao phủ toàn diện: `DisplayStatusEnumTests`, `ViewGroupTests`, `RightsVisibilityTests`, `DisplayStatusPriorityTests`, `InputValidationTests`, `FixtureBindingTests`, `ModuleSurfaceTests`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider` | 0 | 31 passed, 189 subtests passed in 0.07s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace) |
| 3 | `python -c "import pathlib; fs=['src/catalog/application/asset_view.py','tests/unit/catalog/test_catalog_asset_view.py','docs/delivery-evidence/c-07/report.md']; data={f: pathlib.Path(f).read_bytes() for f in fs}; bad=[(f,i) for f in fs for i,l in enumerate(data[f].decode('utf-8').split('\n'),1) if l.rstrip('\r')!=l.rstrip()]; assert not bad, bad; assert all(d.endswith(b'\n') and not d.startswith(b'\xef\xbb\xbf') for d in data.values()); print('OK')"` | 0 | OK |

## Quyết định mặc định (D8)

1. Thứ tự D8-C-09: availability `not_usable` (MISSING, CORRUPT, RECOVERING) → unavailable; `UNAVAILABLE_SOURCE` vẫn usable nên không thành unavailable (CT-SRC-003).
2. `NOT_ASSESSED`, `ASSESSING`, `TRANSFORM_REQUIRED`, `TRANSFORMING` không có rendition xử lý → `original` theo nhánh "còn lại" của D8-C-09; nhóm safety vẫn hiển thị usability `not_usable`. Ghi GIẢ ĐỊNH, xem lại khi E chốt pipeline safety và H dựng màn hình (CONV-C-04).
3. `thumbnail`/`extracted_frame` không làm thành `processed`.
4. Rights không ảnh hưởng `display_status` (D8-C-06); nhóm rights có `evidence_refs` và cờ `uncertain`.
5. CT-MED-002 chưa có binding seam (plan §5, CONV-C-05) nên `semantics`/`technical`/`usage_summary` được truyền nguyên dạng Mapping (bản sao nông). Reasons và model/reviewer revision của nhóm safety chờ binding E→C. Vị trí cloud/local thuộc I (D8-C-10); nhóm availability chỉ có trạng thái CT-STATE-005 và usability.
6. `resolve_display_status` là hàm public để CONV-C-03 tái dùng.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-010
- ROADMAP-OPEN-011
- GIẢ ĐỊNH D8-C-05
(Ghi rõ không mục nào được coi là đã duyệt.)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa domain C-01/C-02/C-04, fixture, ui/, App.tsx, migration, state machine, pyproject.toml, lockfile.
- Không thêm thư viện ngoài stdlib (`collections`, `enum`).
- Không gọi dịch vụ thật.
- Không tạo conftest.py/__init__.py trong tests/.
