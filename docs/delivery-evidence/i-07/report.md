# Báo cáo bằng chứng I-07

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `68e2ae94f4aafb49345a02583208516271e7e05e`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS + slice I-07 trong `docs/implementation/i/slices.md` + binding `docs/parallel-delivery/bindings/f-render-package.json`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `27 failed, 12 passed, 12 subtests passed in 0.22s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/storage/test_storage_materialization.py::AdmitMaterializationTests::test_byte_overflow_is_deferred_and_exact_fit_is_admitted`: `AssertionError: <AdmissionStatus.ADMITTED: 'ADMITTED'> is not <AdmissionStatus.DEFERRED: 'DEFERRED'>`
  - `FAILED tests/unit/storage/test_storage_materialization.py::AdmitMaterializationTests::test_custom_max_video_sets_is_honoured`: `AssertionError: <AdmissionStatus.ADMITTED: 'ADMITTED'> is not <AdmissionStatus.DEFERRED: 'DEFERRED'>`
  - `FAILED tests/unit/storage/test_storage_materialization.py::AdmitMaterializationTests::test_prefetch_is_admitted_only_when_both_limits_hold_after_admission`: `AssertionError: <AdmissionStatus.ADMITTED: 'ADMITTED'> is not <AdmissionStatus.DEFERRED: 'DEFERRED'>`
  - `FAILED tests/unit/storage/test_storage_materialization.py::AdmitMaterializationTests::test_prefetch_is_deferred_when_full`: `AssertionError: <AdmissionStatus.ADMITTED: 'ADMITTED'> is not <AdmissionStatus.DEFERRED: 'DEFERRED'>`
  - `FAILED tests/unit/storage/test_storage_materialization.py::AdmitMaterializationTests::test_set_limit_has_priority_when_both_limits_are_hit`: `AssertionError: <AdmissionStatus.ADMITTED: 'ADMITTED'> is not <AdmissionStatus.DEFERRED: 'DEFERRED'>`
  - `FAILED tests/unit/storage/test_storage_materialization.py::AdmitMaterializationTests::test_sixth_set_is_deferred`: `AssertionError: <AdmissionStatus.ADMITTED: 'ADMITTED'> is not <AdmissionStatus.DEFERRED: 'DEFERRED'>`
  - `FAILED tests/unit/storage/test_storage_materialization.py::AdmitMaterializationTests::test_unsynced_output_bytes_count_toward_byte_limit`: `AssertionError: <AdmissionStatus.ADMITTED: 'ADMITTED'> is not <AdmissionStatus.DEFERRED: 'DEFERRED'>`
  - `FAILED tests/unit/storage/test_storage_materialization.py::AdmitMaterializationTests::test_unsynced_output_counts_toward_set_limit`: `AssertionError: <AdmissionStatus.ADMITTED: 'ADMITTED'> is not <AdmissionStatus.DEFERRED: 'DEFERRED'>`
  - `SUBFAILED(state=<ArtifactLocationState.DECLARED: 'DECLARED'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.MATERIALIZING: 'MATERIALIZING'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.AVAILABLE_UNVERIFIED: 'AVAILABLE_UNVERIFIED'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.VERIFYING: 'VERIFYING'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.CORRUPT: 'CORRUPT'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.MISSING: 'MISSING'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.CLEANUP_ELIGIBLE: 'CLEANUP_ELIGIBLE'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.CLEANUP_AUTHORIZED: 'CLEANUP_AUTHORIZED'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(state=<ArtifactLocationState.DELETED: 'DELETED'>) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_every_non_verified_state_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `FAILED tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_location_bound_to_other_artifact_version_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `FAILED tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_malformed_input_item_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `FAILED tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_missing_location_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `FAILED tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_one_unverified_input_blocks_whole_release_and_is_named`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `FAILED tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_verified_matching_location_is_released`: `AssertionError: Lists differ: [] != [ArtifactLocation(...)]`
  - `SUBFAILED(observed_hash='ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff') tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_wrong_or_missing_observed_hash_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(observed_hash=None) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_wrong_or_missing_observed_hash_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(observed_size_bytes=1025) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_wrong_or_missing_observed_size_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
  - `SUBFAILED(observed_size_bytes=None) tests/unit/storage/test_storage_materialization.py::ReleaseForRenderTests::test_wrong_or_missing_observed_size_is_rejected`: `AssertionError: RenderInputNotVerifiedError not raised`
- Xác nhận: Toàn bộ lỗi FAILED/SUBFAILED đều là AssertionError từ stub (admit_materialization trả ADMITTED và release_for_render trả []); hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `25 passed, 26 subtests passed in 0.04s`

## Thay đổi

- `src/controlplane/application/storage_meta/materialization.py`: Định nghĩa dataclass frozen `WorkingSetPolicy` (bắt buộc `max_bytes: int > 0`, `policy_revision: str` không rỗng, `max_video_sets: int > 0 = 5`), dataclass frozen `ActiveVideoSet` (`video_set_id: str`, `expected_bytes: int >= 0`, `inputs_materialized: bool = True`, `unsynced_output_bytes: int >= 0`), dataclass frozen `MaterializationRequest` (`video_set_id: str`, `expected_bytes: int >= 0`, `is_prefetch: bool = False`), enum `AdmissionStatus` (`ADMITTED`, `DEFERRED`), dataclass frozen `AdmissionDecision` (`status: AdmissionStatus`, `reason: str | None`), exception `RenderInputNotVerifiedError` (`artifact_version_id`, `reason`), hàm `admit_materialization(policy, active_sets, request) -> AdmissionDecision` (tính set chiếm slot nếu `inputs_materialized` hoặc `unsynced_output_bytes > 0`; từ chối `MAX_VIDEO_SETS_REACHED` nếu số slot >= `max_video_sets`; từ chối `MAX_BYTES_EXCEEDED` nếu tổng byte giữ + `expected_bytes` > `max_bytes`; ngược lại chấp thuận `ADMITTED`), và hàm `release_for_render(input_artifacts, local_locations) -> list[ArtifactLocation]` (kiểm tra chặt chẽ từng input artifact với format hợp lệ, có location khớp `artifact_version_id`, ở trạng thái `VERIFIED`, và `observed_hash == sha256`, `observed_size_bytes == size_bytes`; fail-closed nếu có bất kỳ sai lệch nào).
- `tests/unit/storage/test_storage_materialization.py`: Bộ kiểm thử đơn vị gồm 3 lớp: `WorkingSetPolicyTests` (kiểm tra tham số bắt buộc, giá trị mặc định, kiểm tra tính bất biến frozen và validation), `AdmitMaterializationTests` (11 test case kiểm tra hạn mức set, byte, thứ tự ưu tiên khi chạm cả 2 giới hạn, tính toán output chưa sync, cơ chế prefetch và tính frozen của decision), và `ReleaseForRenderTests` (kiểm tra contract fixture `f-render-package/payloads.json`, xác minh location hợp lệ được giải phóng, từ chối mọi trạng thái non-VERIFIED, từ chối sai lệch hash/size, thiếu location, sai liên kết id hoặc input sai định dạng).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider` (RED) | 1 | 27 failed, 12 passed, 12 subtests passed in 0.22s |
| 2 | `python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider` (GREEN) | 0 | 25 passed, 26 subtests passed in 0.04s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 4 | `python -c "import pathlib; fs=['src/controlplane/application/storage_meta/materialization.py','tests/unit/storage/test_storage_materialization.py','docs/delivery-evidence/i-07/report.md']; bad=[(f,i) for f in fs for i,l in enumerate(pathlib.Path(f).read_text(encoding='utf-8').splitlines(),1) if l!=l.rstrip()]; assert not bad, bad; assert all(pathlib.Path(f).read_bytes().endswith(b'\n') and not pathlib.Path(f).read_bytes().startswith(b'\xef\xbb\xbf') and '\ufffd' not in pathlib.Path(f).read_text(encoding='utf-8') for f in fs); print('OK')"` | 0 | OK (UTF-8 không BOM, không trailing whitespace, kết thúc LF, không ký tự hỏng) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: active_sets là list[ActiveVideoSet]; set chiếm slot khi inputs_materialized hoặc unsynced_output_bytes > 0 (ADR-0006), byte giữ = expected_bytes nếu inputs_materialized cộng unsynced_output_bytes.
2. GIẢ ĐỊNH: reason là MAX_VIDEO_SETS_REACHED hoặc MAX_BYTES_EXCEEDED, set limit ưu tiên khi vượt cả hai.
3. GIẢ ĐỊNH: 'sau khi nhận không vượt' nghĩa là số set + 1 <= max_video_sets và tổng byte <= max_bytes, trùng điều kiện non-prefetch nên is_prefetch không đổi kết quả.
4. GIẢ ĐỊNH: caller không gửi request cho set đã có trong active_sets.
5. GIẢ ĐỊNH: max_bytes >= 1, max_video_sets >= 1, byte là int không âm không bool.
6. GIẢ ĐỊNH: input_artifacts sai dạng hoặc location thiếu/không khớp artifact_version_id đều raise RenderInputNotVerifiedError, fail-closed.

## Danh sách chờ user (pendingUserCheckpoint)

- PUC-I-03 — ngưỡng byte của working set và disk reserve trên máy mục tiêu (đo ở CP7-I-03), chưa được duyệt.
(Không mục nào được coi là đã duyệt.)

## Giới hạn

- Không chạy full suite; không chạy tests/m1, tests/m2.
- Không sửa statemachine, storage_meta/__init__.py, fixture, migration, pyproject.toml, lockfile.
- Không thêm thư viện ngoài stdlib.
- Không gọi dịch vụ thật.
- Không tạo conftest.py hay __init__.py trong tests/.
- ArtifactLocation chỉ import đọc từ controlplane.domain.storage_meta; không sửa domain.
