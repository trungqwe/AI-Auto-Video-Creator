# Báo cáo bằng chứng D-07

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `170b96b2748929758f96d9b5a54726be29fb7600`
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-07 trong docs/implementation/d/slices.md, ủy quyền AI_SETUP.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider` (chạy với khung chưa có logic cấp quyền)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `17 failed, 15 passed in 0.27s`
- Chi tiết các test FAILED kèm thông điệp nguyên văn:
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_event_update_with_revision_authorizes_timeline`: `AssertionError: assert [] == [{'ref_type': 'event_update_accepted', 'ref_id': 'u-1', 'revision_id': 'rev-1'}]`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_refs_without_event_update_are_policy_violation[repost_only]`: `Failed: DID NOT RAISE TimelinePolicyViolation`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_refs_without_event_update_are_policy_violation[new_source_only]`: `Failed: DID NOT RAISE TimelinePolicyViolation`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_refs_without_event_update_are_policy_violation[new_media_only]`: `Failed: DID NOT RAISE TimelinePolicyViolation`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_refs_without_event_update_are_policy_violation[article_revision_only]`: `Failed: DID NOT RAISE TimelinePolicyViolation`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_refs_without_event_update_are_policy_violation[all_non_update_types]`: `Failed: DID NOT RAISE TimelinePolicyViolation`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_accepted_type_name_comes_only_from_policy`: `Failed: DID NOT RAISE TimelinePolicyViolation`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_accepted_ref_without_usable_revision_is_policy_violation`: `Failed: DID NOT RAISE TimelinePolicyViolation`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_only_event_updates_with_revision_are_returned`: `AssertionError: assert [] == ['u-1']`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_violation_never_changes_the_mode`: `Failed: DID NOT RAISE TimelinePolicyViolation`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_malformed_arguments_raise_value_error`: `AttributeError: 'dict' object has no attribute 'snapshot_id'`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_policy_requires_non_empty_frozenset_of_names[types0]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_policy_requires_non_empty_frozenset_of_names[types1]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_policy_requires_non_empty_frozenset_of_names[types2]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_policy_requires_non_empty_frozenset_of_names[event_update_accepted]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_policy_requires_non_empty_frozenset_of_names[types4]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/creative/test_d07_timeline_authorization.py::test_policy_requires_non_empty_frozenset_of_names[types5]`: `Failed: DID NOT RAISE ValueError`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (RED sử dụng khung chưa có logic, quyết định D8).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `32 passed in 0.05s`

## Thay đổi

- Ba tệp thuộc owned paths:
  - `src/creative/domain/timeline_mode.py`: triển khai `authorize_timeline_narrative`, `TimelinePolicy`, `TimelineAuthorization`, `TimelinePolicyViolation`, `POLICY_VIOLATION`, `EVENT_UPDATE_MISSING`, `EVENT_UPDATE_REVISION_MISSING`, `TIMELINE_MODE`.
  - `tests/unit/creative/test_d07_timeline_authorization.py`: bộ kiểm thử đơn vị gồm 32 test bao phủ toàn bộ các yêu cầu nghiệm thu, AST ranh giới import/chuỗi, tính bất biến, và các phản ví dụ.
  - `docs/delivery-evidence/d-07/report.md`: báo cáo bằng chứng chuyển giao.
- Ánh xạ phản ví dụ sang test:
  - Nguồn mới, repost, media mới hoặc article revision kích hoạt timeline: bị loại trừ bởi `test_refs_without_event_update_are_policy_violation` (ném `TimelinePolicyViolation` kèm reason `EVENT_UPDATE_MISSING`).
  - Tự hạ mode không ghi quyết định: bị loại trừ bởi `test_violation_never_changes_the_mode` (snapshot mode và payload giữ nguyên sau vi phạm) và `test_module_has_no_fallback_mode_or_mode_rewrite` (AST kiểm tra module không chứa chuỗi `'single_article'`, `'multi_article_event'` và không import `'replace'`).
  - `single_article` / `multi_article_event` không bị ảnh hưởng: kiểm chứng bởi `test_other_modes_are_not_affected` (trả về `TimelineAuthorization` giữ nguyên mode và `event_update_refs=()`).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider` | 0 | 32 passed in 0.05s |
| 2 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 9 passed, 46 subtests passed in 0.06s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Tên loại event update do `TimelinePolicy` truyền vào, không có default ẩn; fixture dùng `event_update_accepted` (GIẢ ĐỊNH).
2. `POLICY_VIOLATION` là `TimelinePolicyViolation.code`, reason ổn định `event_update_accepted_missing` / `event_update_revision_missing`.
3. Tình tiết mới của `EventUpdateAccepted` không kiểm được ở mức ref nên chỉ kiểm `ref_type` + `revision_id` (GIẢ ĐỊNH).
4. Mode khác `from_then_to_now` trả `TimelineAuthorization` không đổi, không kiểm event update.
5. Tham số sai → `ValueError`.
6. Module không đổi mode.

## CT-CNT-005 / CONV-D-07

Ghi rõ CT-CNT-005 `EventUpdateAccepted` chưa có binding; slice dùng `ref_type` do policy truyền vào; mở binding B→D qua CONV-D-07.

## coveredIds

`CT-AI-005`, `TST-CTR-INV-006` (khai báo trong docstring của module `src/creative/domain/timeline_mode.py` và tệp test `tests/unit/creative/test_d07_timeline_authorization.py`).

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không thêm thư viện (chỉ dùng Python stdlib: `collections.abc`, `dataclasses`, và model nội bộ `creative.domain.snapshot`).
- Không gọi dịch vụ thật.
- Kết quả `git diff --check --cached` sau khi stage ghi trong `worker_done`.
