# Báo cáo bằng chứng F-05

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4fd21816ce8c657983f0e09d226209f381b13f5c`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-05 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider` (chạy trên stub trả None ở bước 8)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `58 failed, 4 passed in 0.65s`
- Chi tiết các dòng FAILED tiêu biểu từ bước 8:
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_resolve_builds_valid_record_with_f04_fingerprint_and_uuid5_id`: `AssertionError: assert False where False = isinstance(None, RenderPackageRecord)`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_repeated_resolve_returns_same_package_and_id`: `AssertionError: assert False where False = isinstance(None, RenderPackageRecord)`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_different_content_gives_different_fingerprint_and_id`: `AssertionError: assert False where False = isinstance(None, RenderPackageRecord)`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_asset_outside_plan_and_fallbacks_is_rejected`: `Failed: DID NOT RAISE ResolveError`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_timeline_and_hook_refs_outside_plan_are_rejected`: `Failed: DID NOT RAISE ResolveError`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_plan_port_and_inputs_type_are_checked`: `Failed: DID NOT RAISE ResolveError`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_duplicate_artifact_version_is_rejected`: `Failed: DID NOT RAISE ResolveError`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_url_anywhere_in_inputs_is_rejected[subtitle_config-value0-subtitle_config.caption]`: `Failed: DID NOT RAISE ResolveError`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_forbidden_fields_are_rejected_with_field[mix_plan-value0-shell_command]`: `Failed: DID NOT RAISE ResolveError`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_missing_input_reports_field[production_snapshot_ref]`: `Failed: DID NOT RAISE ResolveError`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_free_path_strings_are_not_accepted_as_local_refs[C:\\x\\a.mp4]`: `Failed: DID NOT RAISE ResolveError`
  - `FAILED tests/unit/render/test_f05_resolve_package.py::test_materialization_only_accepts_local_material_ref_objects`: `Failed: DID NOT RAISE ResolveError`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. Tất cả 58 test thất bại đều là `AssertionError` (stub trả `None`) hoặc `DID NOT RAISE` (chưa có logic raise `ResolveError`).
- Danh sách 4 test đã PASS sẵn trên stub:
  - `test_dtos_are_frozen_with_the_specified_fields`
  - `test_ports_are_runtime_protocols`
  - `test_ports_module_is_stdlib_only`
  - `test_module_is_pure_and_declares_covered_ids`

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider` (chạy sau khi cài đặt mã thật ở bước 12)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `62 passed in 0.11s`

## Thay đổi

- 4 tệp thuộc owned paths:
  - `src/render/ports/inputs.py`: Khai báo DTO frozen `ResolvedAsset`, `LocalMaterialRef`, `ResolveInputs` (17 trường tương ứng 17 trường băm) cùng các runtime Protocol `PlanAssetPort`, `ArtifactInfoPort`.
  - `src/render/domain/resolve_package.py`: Cài đặt hàm `resolve_render_package(inputs, plan_assets)` dựng `RenderPackageRecord` hợp lệ theo F-03 với `package_fingerprint` theo F-04 và `render_package_id` theo uuid.uuid5 trên fingerprint; kiểm tra asset thuộc tập plan hoặc allowed_fallbacks hoặc voice/word timing; từ chối chuỗi URL `://` ở bất kỳ đâu; chuẩn hóa manifest ref cục bộ; xử lý frozen và bảo toàn nguyên văn các cấu hình kịch bản.
  - `tests/unit/render/test_f05_resolve_package.py`: Bộ kiểm thử toàn diện 62 test cases bao phủ DTO frozen, runtime protocol, stdlib pure imports, happy path resolve và tính xác định lặp lại, phát hiện thay đổi nội dung, không phụ thuộc thứ tự input_artifacts/language_validation_refs, bất biến sau mutation, từ chối asset ngoài plan/fallbacks, từ chối URL ở mọi cấp, từ chối forbidden fields, báo lỗi trường thiếu hoặc sai kiểu, kiểm tra ranh giới ref materialization và coveredIds.
  - `docs/delivery-evidence/f-05/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider` | 0 | `62 passed in 0.11s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `ResolveInputs` dùng đúng 17 tên trường băm của F-03, `input_artifacts` là `ResolvedAsset` đã được I xác minh (`ArtifactInfoPort` do adapter/G dùng để dựng).
2. Tập asset cho phép = refs của plan ∪ artifact_version_id trong allowed_fallbacks ∪ voice_artifact_ref và word_timing_ref (do E cấp, không thuộc plan) — GIẢ ĐỊNH F-local, hội tụ qua CONV-F-07.
3. Kiểm cả visual_asset_refs trong `timeline.segments` và `hook_placement.*_ref` theo cùng tập asset cho phép.
4. `materialization_manifest` chỉ nhận `LocalMaterialRef`, `local_ref` là tên đơn không có dấu phân cách, không ổ đĩa, không '..', không '://', dựng thành `{artifact_version_id: {'local_ref': ...}}` khớp F-10.
5. URL: chuỗi chứa '://' ở bất kỳ đâu bị từ chối `url_not_allowed`, `shell_command`/`arbitrary_url` bị F-03 từ chối `forbidden_field`.
6. `input_artifacts` và `language_validation_refs` sắp ổn định nên đổi thứ tự đầu vào không đổi package.
7. `render_package_id = uuid5(uuid5(NAMESPACE_DNS, 'render-package.f.ai-auto-video-creator'), fingerprint)`.
8. `subtitle_config`, `timeline`, `hook_placement`, `mix_plan`, `allowed_fallbacks` được chép nguyên văn, F không thêm hay viết lại văn bản.

## Ánh xạ phản ví dụ

- F thay asset ngoài fallback → `test_asset_outside_plan_and_fallbacks_is_rejected`, `test_timeline_and_hook_refs_outside_plan_are_rejected`.
- Package chứa URL → `test_url_anywhere_in_inputs_is_rejected`.
- Hai lần resolve hai id khác → `test_repeated_resolve_returns_same_package_and_id`.
- F viết lại caption → `test_caption_text_passes_through_verbatim_and_f_adds_nothing`.

## coveredIds

- `CT-RND-002`
- `acceptance §8 mục 6 (phía resolve)`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, package_contract.py, package_fingerprint.py.
- Chỉ stdlib và module render có sẵn.
- Không gọi dịch vụ thật.
