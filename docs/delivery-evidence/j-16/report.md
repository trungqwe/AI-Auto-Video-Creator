# Báo cáo bằng chứng J-16

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 379c232fd55c67c60dfd23333cdd0e2589cc5d96
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-16 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider (chạy khi capability_health.py là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 33 failed, 2 passed in 0.25s
- Danh sách test PASSED kèm lý do (2 passed do stub đã khai báo coveredIds và cấu trúc import cho phép):
  - 	ests/unit/config/test_j_capability_health.py::test_module_docstring_declares_covered_ids (docstring test khai báo coveredIds: CT-CAP-003, CT-CAP-001)
  - 	ests/unit/config/test_j_capability_health.py::test_module_is_pure_and_imports_only_allowed_modules (stub chỉ import các module trong tập cho phép)
- Danh sách nhóm test FAILED kèm thông điệp nguyên văn (33 failed):
  - 17 test failed do NotImplementedError: J-16 snapshot_to_observation:
    - 	est_observation_maps_every_key_from_snapshot
    - 	est_missing_limit_omits_the_limit_key_and_is_never_available
    - 	est_observation_does_not_mutate_the_snapshot
    - 	est_confidence_comes_from_effective_confidence
    - 	est_datetime_values_become_iso_text
    - 	est_backoff_active_only_while_backoff_until_is_after_now (8 tham số: None, 2026-10-20T10:31:00+00:00, 2026-10-20T17:31:00+07:00, 2026-10-20T10:30:00+00:00, 2026-10-20T10:00:00+00:00, datetime(2026, 10, 20, 10, 45, tzinfo=timezone.utc), 2026-10-20T10:45:00, not-a-date)
    - 	est_expired_or_unknown_confidence_marks_quota_uncertain
    - 	est_location_is_passed_through_and_defaults_to_cloud
    - 	est_naive_now_is_rejected
    - 	est_non_snapshot_input_is_type_error
  - 16 test failed do NotImplementedError: J-16 project_capability_health:
    - 	est_status_projection (8 trạng thái overrides: available, degraded expired, degraded backoff, unknown missing limit, unavailable health down, unknown health unknown, degraded confidence unknown, unavailable limit exhausted)
    - 	est_expired_quota_is_never_available
    - 	est_healthy_view_fields
    - 	est_latest_snapshot_of_the_same_scope_wins (2 thứ tự newer_first False và True)
    - 	est_different_accounts_give_separate_views_sorted_by_capability_id
    - 	est_empty_input_gives_empty_list
    - 	est_view_and_observation_have_no_sensitive_key_or_source_canary
    - 	est_module_has_no_grant_function_and_views_expose_none
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection khi module là stub; RED chạy và thất bại hợp lệ do NotImplementedError đúng oracle.

## Thay đổi

- src/controlplane/application/config_security/capability_health.py: adapter thuần túy ánh xạ ProviderCapacitySnapshot sang observation và CapabilityView; gồm hai hàm snapshot_to_observation và project_capability_health; không mutation snapshot, không I/O, không gọi hàm đồng hồ, không tạo quyền thực thi (không grant), không sửa src/controlplane/config/*.py.
- 	ests/unit/config/test_j_capability_health.py: 35 test bao phủ toàn bộ các yêu cầu của adapter (ánh xạ khóa, limit None bỏ khóa, không mutate snapshot, effective_confidence, iso text datetime, backoff_until fail-closed, uncertain quota, location pass-through, naive now rejection, type error, 5 trạng thái CapabilityView, deduplicate snapshot mới nhất theo scope, sắp xếp theo capability_id, không khóa nhạy cảm, không hàm grant, chỉ import tập cho phép); docstring có dòng coveredIds: CT-CAP-003, CT-CAP-001.
- docs/delivery-evidence/j-16/report.md: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider | 0 | 35 passed in 0.06s |
| 2 | python -c "import pathlib; t = pathlib.Path('tests/unit/config/test_j_capability_health.py').read_text(encoding='utf-8'); assert 'coveredIds: CT-CAP-003, CT-CAP-001' in t; r = pathlib.Path('docs/delivery-evidence/j-16/report.md').read_text(encoding='utf-8'); assert 'RED' in r and 'GREEN' in r and 'Exit code' in r and 'NotImplementedError' in r" | 0 | PASS (assert qua) |
| 3 | git diff --check | 0 | PASS (không output) |

## Quyết định mặc định (D8)

- Thêm khóa is_quota_uncertain=True khi effective_confidence là unknown vì uild_capability_view không xem expires_at nên hết hạn sẽ thành vailable nếu thiếu khóa này.
- Giá trị datetime chuyển sang chuỗi isoformat().
- ackoff_until dạng naive hoặc không parse được coi là còn hiệu lực backoff (fail-closed).
- ccount_scope định dạng <account>:<project>.
- Chỉ dùng limit_requests và used_requests cho observation capacity.
- capability_health.py nằm dưới src/controlplane/application/config_security/ là owned path được giao của slice.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật.
- Chỉ chạm 3 owned paths được phân quyền (không chạm src/controlplane/config/*.py, kiểm bằng git diff --name-only).