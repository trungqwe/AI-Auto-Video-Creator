# Báo cáo bằng chứng F-02

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4daa3e625fcac2d0d28a1bf01f925467fd958ff7`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-02 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider` (chạy trên stub trả giá trị trung tính trước khi cài mã thật)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `74 failed, 7 passed, 5 subtests passed in 0.64s`
- Chi tiết các test FAILED/SUBFAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/render/test_f02_preset_revision.py::RevisionValueTests::test_build_sets_all_thirteen_fields`: `AssertionError: Items in the second set but not the first: 'color_effect_rules', 'compatibility_requirements', 'fallback_constraints', 'hook_treatment', 'layout_rules', 'mix_rules', 'output_profile_ref', 'preset_key', 'revision', 'thumbnail_overlay_style', 'typography_karaoke_style', 'visual_rhythm'`
  - `FAILED tests/unit/render/test_f02_preset_revision.py::RevisionValueTests::test_equality_and_hash`: `AssertionError: RenderPresetRevision(preset_key=None, ...) == RenderPresetRevision(preset_key=None, ...)`
  - `FAILED tests/unit/render/test_f02_preset_revision.py::RevisionValueTests::test_later_change_to_source_payload_does_not_change_preset`: `TypeError: 'NoneType' object is not subscriptable`
  - `FAILED tests/unit/render/test_f02_preset_revision.py::RevisionValueTests::test_preset_is_frozen_and_deeply_read_only`: `TypeError: 'NoneType' object is not subscriptable`
  - `FAILED tests/unit/render/test_f02_preset_revision.py::RevisionValidationTests::test_from_payload_requires_all_thirteen_fields_and_matching_fingerprint`: `AssertionError: PresetValidationError not raised`
  - `FAILED tests/unit/render/test_f02_preset_revision.py::CatalogAddTests::test_add_revision_returns_new_catalog_and_keeps_old`: `AssertionError: Tuples differ: () != (RenderPresetRevision(...),)`
  - `FAILED tests/unit/render/test_f02_preset_revision.py::CatalogResolveTests::test_resolve_defaults_to_highest_revision_and_ignores_insertion_order`: `AttributeError: 'NoneType' object has no attribute 'revision'`
  - `FAILED tests/unit/render/test_f02_preset_revision.py::CatalogResolveTests::test_resolve_each_of_five_fixture_presets`: `AssertionError: None != RenderPresetRevision(...)`
- Các test PASS trên stub: 7 test (`FingerprintTests::test_key_order_does_not_change_fingerprint`, `FingerprintTests::test_builder_ignores_supplied_fingerprint_key`, `CatalogResolveTests::test_resolve_rejects_invalid_revision_argument`, `NoHardcodedContentTests::test_module_has_no_preset_name_style_or_resolution_literals`, `NoHardcodedContentTests::test_fingerprint_comes_from_the_shared_canonicalizer` cùng 5 subtests).
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, lỗi collection hay NotImplementedError (RED chạy trên stub trả giá trị trung tính, thất bại do assertion và hành vi chưa đúng oracle).

## Thay đổi

- Danh sách 3 tệp thuộc owned paths:
  - `src/render/domain/preset.py`: Cài đặt miền nghiệp vụ preset CT-RND-001 bao gồm:
    - `RenderPresetRevision`: `@dataclass(frozen=True, kw_only=True)` đóng băng sâu (deep-frozen) tất cả 13 trường dữ liệu; sections cấu hình được chuyển sang `MappingProxyType` và `tuple`; `preset_fingerprint` tính bằng `request_hash` trên 12 trường còn lại; phương thức `from_payload` phục hồi và kiểm tra fingerprint toàn vẹn.
    - `PresetCatalog`: Danh mục preset bất biến (`frozen=True`), lưu trữ các revision được chuẩn hóa và sắp xếp theo `(preset_key, revision)`. Phương thức `add_revision` trả về catalog mới, bảo đảm tính idempotent khi thêm cùng revision trùng nội dung, và từ chối xung đột revision khác nội dung bằng lỗi `duplicate_revision`.
    - `compute_preset_fingerprint`: Chuẩn hóa dữ liệu bằng `_thaw` và ủy quyền tính băm tới `controlplane.application.idempotency.canonicalization.request_hash`.
    - `verify_preset_fingerprint`: Xác minh tính toàn vẹn của fingerprint, ném `PresetValidationError` với mã `preset_fingerprint_mismatch` nếu phát hiện sai lệch.
    - `build_preset_revision`: Khởi dựng đối tượng revision từ mapping 12 trường đầu vào, tự động tính fingerprint và bỏ qua trường fingerprint nếu caller truyền vào.
    - `resolve_preset`: Tra cứu xác định (deterministic lookup), mặc định chọn revision cao nhất của `preset_key` hoặc revision cụ thể nếu được chỉ định; ném `PresetNotFoundError` (`preset_not_found`) khi không tồn tại.
    - `completeness_issue` và `is_complete`: Kiểm tra điều kiện catalog hoàn chỉnh khi có đúng 5 `preset_key` phân biệt (trả `preset_count_not_five` khi không thỏa mãn).
  - `tests/unit/render/test_f02_preset_revision.py`: Bộ kiểm thử toàn diện gồm 6 lớp test:
    - `RevisionValueTests` (4 test): Kiểm tra thiết lập đủ 13 trường, tính bất biến đóng băng sâu (deeply read-only), không bị ảnh hưởng khi payload nguồn bị sửa đổi sau đó, so sánh bằng (`__eq__`) và băm (`__hash__`).
    - `RevisionValidationTests` (4 test): Kiểm tra `revision` phải là số nguyên >= 1 (từ chối `bool`, chuỗi, `float`, `0`, số âm), thiếu bất kỳ trường nào ném lỗi kèm tên trường `field`, từ chối kiểu dữ liệu sai hoặc giá trị không hợp lệ (`NaN`), và khôi phục từ payload (`from_payload`) yêu cầu đủ 13 trường kèm fingerprint khớp.
    - `FingerprintTests` (8 test): Kiểm tra fingerprint khớp `request_hash`, ủy quyền hash không chứa trường fingerprint, không đổi khi hoán đổi thứ tự khóa trong mapping, thay đổi bất kỳ trường nào đều làm thay đổi fingerprint, builder bỏ qua khóa fingerprint truyền vào, tính fingerprint chấp nhận cả object lẫn mapping, `verify_preset_fingerprint` phát hiện và ném lỗi khi dữ liệu bị sửa đổi sau khi tính fingerprint, và chuyển lỗi canonicalization thành `PresetValidationError`.
    - `CatalogAddTests` (4 test): Kiểm tra `add_revision` trả catalog mới và giữ nguyên catalog cũ, giữ các revision cũ và không bao giờ ghi đè khi xung đột, từ chối dữ liệu bị chỉnh sửa sai fingerprint hoặc sai kiểu, và `is_complete` chỉ True khi có đúng 5 `preset_key` phân biệt (ngược lại False kèm `preset_count_not_five`).
    - `CatalogResolveTests` (4 test): Kiểm tra tra cứu xác định mặc định lấy revision cao nhất không phụ thuộc thứ tự thêm vào, tra cứu từng fixture preset trong bộ 5 preset, ném `PresetNotFoundError` (`preset_not_found`) khi không tìm thấy preset hoặc revision, và từ chối tham số revision không hợp lệ.
    - `NoHardcodedContentTests` (2 test): Quét AST của `src/render/domain/preset.py` bảo đảm không chứa số nào ngoài `{0, 1, 5}`, không chứa chuỗi độ phân giải hay từ khóa fixture, và hàm hash được import từ canonicalizer dùng chung (`controlplane.application.idempotency.canonicalization.request_hash`), không import `hashlib` hay `json`.
  - `docs/delivery-evidence/f-02/report.md`: Báo cáo bằng chứng thực thi gói F-02.
- Phản ví dụ được loại trừ:
  - Sửa preset tại chỗ: Bị chặn bởi `@dataclass(frozen=True)` và chuyển mapping sang `MappingProxyType`, sequence sang `tuple`.
  - Fingerprint không đổi khi đổi một phần: Bị chặn bởi `request_hash` tính trên toàn bộ 12 trường và mọi cấu trúc lồng nhau.
  - Catalog 6 preset vẫn complete hoặc ít hơn 5 preset vẫn complete: Bị chặn bởi `completeness_issue` kiểm tra chính xác `len(distinct) == 5`.
  - Style, tên preset hoặc hằng độ phân giải đặt cứng trong mã: Bị chặn bởi kiểm tra AST tĩnh trong `NoHardcodedContentTests`.
  - Resolve không xác định: Bị chặn bởi thứ tự sắp xếp cố định và chọn phần tử lớn nhất theo revision `max(..., key=lambda item: item.revision)`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider` | 0 | 26 passed, 67 subtests passed in 0.13s |
| 2 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 75 subtests passed in 0.08s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Phần rỗng hoặc mapping rỗng coi là thiếu (`missing_required`).
2. Các sections cấu hình CT-RND-001 bị đóng băng sâu (`MappingProxyType`, `tuple`).
3. `add_revision` cùng `(preset_key, revision)` và nội dung bằng nhau trả lại chính catalog (idempotent), nếu khác nội dung ném `duplicate_revision`.
4. `build_preset_revision` bỏ qua khóa `preset_fingerprint` truyền vào từ caller và luôn tính lại từ nội dung 12 trường.
5. Catalog xác minh fingerprint của mọi revision khi khởi dựng (`__post_init__`).
6. `completeness_issue` trả `preset_count_not_five` để đi kèm `is_complete` trả False khi catalog không có đúng 5 `preset_key` phân biệt.
7. `fixture-preset-1..5` là GIẢ ĐỊNH test-only; mã nguồn không chứa tên preset thật (ROADMAP-OPEN-009).

## Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-009 (tên, style, thông số 5 preset chính thức; duyệt ở CP7-F-05/exit gate M6).
- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).
- CONV-F-06 và CONV-F-11 (đăng ký preset vào cấu hình J).
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không thêm thư viện ngoài (chỉ dùng stdlib và canonicalizer đã có).
- Không gọi dịch vụ thật.
