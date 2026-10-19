# Báo cáo bằng chứng C-08

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `cbd256247045936fd2b5b07c3eca8fbfac7b737d`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-08 trong `docs/implementation/c/slices.md`; binding `docs/parallel-delivery/bindings/i-artifact-version.json`, `tests/fixtures/contracts/i-artifact-version/payloads.json`, `docs/parallel-delivery/bindings/f-render-package.json`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `72 failed, 11 passed, 24 subtests passed in 0.41s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `SUBFAILED(location_state='DECLARED') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='MATERIALIZING') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='AVAILABLE_UNVERIFIED') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='VERIFYING') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='CORRUPT') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='MISSING') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='OUTCOME_UNKNOWN') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='CLEANUP_ELIGIBLE') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='CLEANUP_AUTHORIZED') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='DELETED') tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_every_location_state_only_verified_is_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='AVAILABLE_UNVERIFIED', is_local=True) tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_unverified_missing_or_corrupt_never_render`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='AVAILABLE_UNVERIFIED', is_local=False) tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_unverified_missing_or_corrupt_never_render`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='MISSING', is_local=True) tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_unverified_missing_or_corrupt_never_render`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='MISSING', is_local=False) tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_unverified_missing_or_corrupt_never_render`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='CORRUPT', is_local=True) tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_unverified_missing_or_corrupt_never_render`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(location_state='CORRUPT', is_local=False) tests/unit/catalog/test_catalog_renderable.py::LocationStateTests::test_unverified_missing_or_corrupt_never_render`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::HashTests::test_hash_mismatch_is_not_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::HashTests::test_location_and_hash_reasons_are_both_reported`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::HashTests::test_uppercase_hash_from_fixture_is_mismatch`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(is_local=False) tests/unit/catalog/test_catalog_renderable.py::MaterializationTests::test_materialization_required_is_not_is_local`: `AssertionError: False is not True`
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::CombinationTests::test_clip_and_audio_have_no_image_safety_axis`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::CombinationTests::test_missing_availability_is_not_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::CombinationTests::test_uncertain_image_is_usable_with_warning`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.USABLE_WITH_WARNING: 'usable_with_warning'>`
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::CombinationTests::test_unreadable_image_is_not_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::CombinationTests::test_warning_never_hides_unverified_location`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - Các SUBFAILED của `CombinationTests::test_worst_of_safety_and_availability_for_every_pair`: đều là `AssertionError` khi kiểm tra kết hợp mức xấu nhất giữa safety và availability.
  - `FAILED tests/unit/catalog/test_catalog_renderable.py::ReadOnlyTests::test_rendition_must_reference_artifact`: `AssertionError: ValueError not raised`
- Xác nhận: Toàn bộ lỗi FAILED/SUBFAILED đều là AssertionError từ stub; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection (các test frozen, AST, validation ArtifactVersionView PASS).

## Thay đổi

- `src/catalog/application/renderable.py`: Định nghĩa `ArtifactVersionView` (frozen slots dataclass với runtime validation `location_state` là `ArtifactLocationState` và `is_local` là `bool`), `RenderableResolution` (frozen slots dataclass mang đầy đủ trường của artifact, `materialization_required`, `safety_state`, `usability`, `reason_codes`), các hằng mã lỗi (`ARTIFACT_MISSING`, `ARTIFACT_CORRUPT`, `ARTIFACT_NOT_VERIFIED`, `HASH_MISMATCH`), và hàm `resolve_renderable_version` (kiểm tra `rendition.artifact_version_ref == artifact.artifact_version_ref`, chỉ `VERIFIED` mới không bị downgrade, hạ hash mismatch, kết hợp availability và image safety theo mức xấu nhất, `materialization_required = not is_local`; module chỉ đọc `ArtifactLocationState`, tuyệt đối không ghi location state).
- `tests/unit/catalog/test_catalog_renderable.py`: Bộ kiểm thử đơn vị toàn diện gồm 6 nhóm: helper `make_rendition`/`make_artifact`/`resolve`, `LocationStateTests` (duyệt mọi trạng thái của ArtifactLocationState qua subTest, loại trừ phản ví dụ AVAILABLE_UNVERIFIED, MISSING, CORRUPT), `HashTests` (khớp hash fixture, mismatch hash, hash in hoa, kết hợp location và hash), `MaterializationTests` (`materialization_required = not is_local`), `CombinationTests` (UNAVAILABLE_SOURCE cùng VERIFIED, UNCERTAIN usable_with_warning, UNREADABLE not_usable, toàn bộ cặp safety × availability lấy mức xấu nhất, cảnh báo không che unverified), `ReadOnlyTests` (rendition lệch artifact, artifact không đổi sau resolve, frozen instance, và AST audit đảm bảo module không ghi location state).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider` | 0 | 20 passed, 87 subtests passed in 0.06s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 3 | `python -c "import pathlib; fs=['src/catalog/application/renderable.py','tests/unit/catalog/test_catalog_renderable.py','docs/delivery-evidence/c-08/report.md']; data={f: pathlib.Path(f).read_bytes() for f in fs}; bad=[(f,i) for f in fs for i,l in enumerate(data[f].decode('utf-8').split('\n'),1) if l.rstrip('\r')!=l.rstrip()]; assert not bad, bad; assert all(d.endswith(b'\n') and not d.startswith(b'\xef\xbb\xbf') for d in data.values()); print('OK')"` | 0 | OK (UTF-8 không BOM, không trailing whitespace, kết thúc LF) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: Mã bổ sung `AVAILABILITY_<giá trị>` và `IMAGE_SAFETY_<giá trị>` khi trục đó không usable để giải thích đầy đủ nguyên nhân hạ mức trong `reason_codes`.
2. GIẢ ĐỊNH: `reason_codes` ghi theo thứ tự ưu tiên: location, hash, availability, safety.
3. GIẢ ĐỊNH: So sánh chuỗi hash chính xác từng ký tự (case-sensitive), hash in hoa từ fixture case `content_hash_uppercase` coi là không khớp (`HASH_MISMATCH`).
4. GIẢ ĐỊNH: `rendition.artifact_version_ref != artifact.artifact_version_ref` bị từ chối bằng `ValueError`.
5. GIẢ ĐỊNH: `ArtifactVersionView` bắt buộc `location_state` là kiểu `ArtifactLocationState` và `is_local` là kiểu `bool`, kiểm tra chặt chẽ tại `__post_init__`, không ép kiểu ngầm định.
6. GIẢ ĐỊNH: `materialization_required` phản ánh nhu cầu tải/materialize của I (`not artifact.is_local`), không làm hạ `usability` vì materialize là việc của hạ tầng I.
7. GIẢ ĐỊNH: Adapter `CT-RND-002`/`003` và fake I thật chờ các gói hội tụ liên phân hệ.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-010
- ROADMAP-OPEN-011
- GIẢ ĐỊNH D8-C-05
(Không mục nào được coi là đã duyệt.)

## Giới hạn

- Không chạy full suite; không chạy tests/m1, tests/m2.
- Không sửa fixture, state machine, migration, pyproject.toml, lockfile.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib.
- Không gọi dịch vụ thật.
- Không tạo conftest.py hay __init__.py trong tests/.
- Module không ghi location state.
- Không commit secret, đường dẫn Credentials/ hay dữ liệu cá nhân.
