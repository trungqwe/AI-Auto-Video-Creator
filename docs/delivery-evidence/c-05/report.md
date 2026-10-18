# Báo cáo bằng chứng C-05

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `0ad4cbf564484cec02bbeffa18ea3796349b4a91`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-05 trong `docs/implementation/c/slices.md`, contract CT-HOOK-001/002 trong `docs/09-contracts/05-content-media-contracts.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider` (chạy với stub ở bước 2)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `7 failed, 13 passed, 24 subtests passed in 0.11s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/catalog/test_catalog_hooks.py::ImportHookTests::test_import_existing_hook_id_is_rejected`: `AssertionError: RevisionConflictError not raised`
  - `SUBFAILED(stale=1) tests/unit/catalog/test_catalog_hooks.py::UpdateHookMetadataTests::test_stale_or_future_expected_revision_raises_revision_conflict`: `AssertionError: RevisionConflictError not raised`
  - `SUBFAILED(stale=3) tests/unit/catalog/test_catalog_hooks.py::UpdateHookMetadataTests::test_stale_or_future_expected_revision_raises_revision_conflict`: `AssertionError: RevisionConflictError not raised`
  - `FAILED tests/unit/catalog/test_catalog_hooks.py::UpdateHookMetadataTests::test_unspecified_fields_are_kept`: `AssertionError: 1 != 2`
  - `FAILED tests/unit/catalog/test_catalog_hooks.py::UpdateHookMetadataTests::test_update_appends_next_revision_and_keeps_old`: `AssertionError: 1 != 2`
  - `FAILED tests/unit/catalog/test_catalog_hooks.py::HookIndependenceTests::test_audio_hook_alone_needs_no_visual`: `AssertionError: 1 != 2`
  - `FAILED tests/unit/catalog/test_catalog_hooks.py::HookIndependenceTests::test_visual_and_audio_are_imported_updated_and_read_independently`: `AssertionError: Tuples differ: (1, 1) != (2, 2)`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, TypeError, AttributeError, NameError hay lỗi collection nào (HookKindTests, HookRevisionTests, các test domain, chữ ký, TypeError kind/artifact, KeyError hook lạ và RevisionErrorReuseTests PASS).

## Thay đổi

- `src/catalog/domain/hooks.py`: Định nghĩa `HookKind` (StrEnum: `visual_hook`, `audio_hook`), `HookRevision` (frozen slots dataclass gồm đúng 10 trường theo thứ tự với runtime validation chặt chẽ; `provenance` mặc định `user_imported`, không có trường ghép cặp visual/audio; không định nghĩa exception mới).
- `src/catalog/application/hooks.py`: Triển khai `HookHistory` (append-only in-memory revision store, `get(hook_id, revision)`, `latest(hook_id)`, `append(revision)` kiểm tra thứ tự revision và từ chối xung đột bằng `RevisionConflictError`), `import_hook` (nhập hook revision 1 với `user_imported`), và `update_hook_metadata` (tăng revision cũ + 1, giữ nguyên `kind` và `artifact_version_ref`, từ chối `expected_revision` sai lệch bằng `RevisionConflictError`).
- `tests/unit/catalog/test_catalog_hooks.py`: Bộ kiểm thử đơn vị bao phủ CT-HOOK-001 và CT-HOOK-002 gồm 6 test class: `HookKindTests`, `HookRevisionTests`, `ImportHookTests`, `UpdateHookMetadataTests`, `HookIndependenceTests`, `RevisionErrorReuseTests`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider` | 0 | 18 passed, 31 subtests passed in 0.04s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `HookRevision.provenance` dùng lại `ProvenanceRelation` của C-01, mặc định `user_imported`, giá trị khác → `ValueError`; đặt trường cuối vì có default.
2. `import_hook` với `hook_id` đã có → `RevisionConflictError` (lớp của controlplane) qua `HookHistory.append`, không định nghĩa lỗi mới.
3. `update_hook_metadata` mọi tham số `None` vẫn tạo revision mới (đúng quy tắc cũ + 1).
4. `get`/`latest` không tìm thấy → `KeyError`.
5. `artifact_version_ref` trong test lấy từ `artifact_version_id` của `DeclareArtifactVersionResult` valid trong fixture i-artifact-version.
6. Adapter seam CT-HOOK-001/002, persistence, control API và UI chờ CONV-C-01, CONV-C-03, CONV-C-04, CONV-C-05.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-010
- ROADMAP-OPEN-011
(Không mục nào được coi là đã duyệt.)

## Giới hạn

- Không chạy full suite; không chạy tests/m1, tests/m2.
- Không sửa pyproject.toml, uv.lock, migration, fixture, src/controlplane.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib.
- Không gọi dịch vụ thật.
- Không tạo conftest.py hay __init__.py trong tests/.
- Không ghi secret, đường dẫn Credentials/ hay dữ liệu cá nhân.
