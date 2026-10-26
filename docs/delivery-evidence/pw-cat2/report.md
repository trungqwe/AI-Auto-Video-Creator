# Báo cáo chuyển giao: flow.py xử lý waiting, RetryStage và fan-out (PW-CAT2)

- Task: PW-CAT2
- Trạng thái: IMPLEMENTED

## 1. Tóm tắt: disposition waiting thành WAITING_CAPABILITY với wait_reason từ problem.code (mã lạ hoặc thiếu mã thì dependency_wait), _drive chờ bằng workflow.wait_condition có timeout; RetryStage bỏ qua activity đã thành công theo (stage, activity, index, revision); fan-out theo FAN_OUT_FROM_OUTPUT.

## 2. Tệp đã đổi: flow.py, definitions.py, test_pw_cat2_flow.py (mới), report.md; test_cp6_video_production_flow.py nếu không sửa thì ghi rõ không đổi.
- `src/controlplane/application/orchestration/workflows/flow.py`
- `src/controlplane/application/orchestration/workflows/definitions.py`
- `tests/integration/prod_wiring/test_pw_cat2_flow.py` (mới)
- `docs/delivery-evidence/pw-cat2/report.md`
- `tests/integration/convergence/test_cp6_video_production_flow.py` (không đổi)

## 3. Bằng chứng RED: lệnh bước 8, exit code, số failed/passed thật và tên các test đỏ.
- Lệnh bước 8: `python -m pytest tests/integration/prod_wiring/test_pw_cat2_flow.py -q -p no:cacheprovider`
- Exit code: 1
- Số lượng: 29 failed, 1 passed in 3.38s
- Danh sách 29 test đỏ chứng kiến đúng oracle:
  1. `test_waiting_sets_the_wait_reason_from_the_problem_code[desktop_offline-desktop_offline]`
  2. `test_waiting_sets_the_wait_reason_from_the_problem_code[local_ai_unavailable-local_ai_unavailable]`
  3. `test_waiting_sets_the_wait_reason_from_the_problem_code[provider_unavailable-provider_unavailable]`
  4. `test_waiting_sets_the_wait_reason_from_the_problem_code[quota_wait-quota_wait]`
  5. `test_waiting_sets_the_wait_reason_from_the_problem_code[artifact_not_ready-artifact_not_ready]`
  6. `test_waiting_sets_the_wait_reason_from_the_problem_code[insufficient_disk-insufficient_disk]`
  7. `test_waiting_sets_the_wait_reason_from_the_problem_code[dependency_wait-dependency_wait]`
  8. `test_waiting_sets_the_wait_reason_from_the_problem_code[credential_unavailable-credential_unavailable]`
  9. `test_waiting_sets_the_wait_reason_from_the_problem_code[SOMETHING_ELSE-dependency_wait]`
  10. `test_waiting_sets_the_wait_reason_from_the_problem_code[None-dependency_wait]`
  11. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[analyze]`
  12. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[script]`
  13. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[plan]`
  14. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[media_select]`
  15. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[tts]`
  16. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[align]`
  17. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[process]`
  18. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[render]`
  19. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[qc]`
  20. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[sync]`
  21. `test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage[complete]`
  22. `test_retry_stage_reruns_only_the_failed_activity_and_keeps_received_output`
  23. `test_fan_out_runs_once_per_selected_image_with_its_own_index`
  24. `test_payload_item_refs_are_kept_over_fan_out`
  25. `test_fan_out_without_matching_output_runs_zero_times`
  26. `test_fan_out_item_waiting_reruns_only_that_item`
  27. `test_daily_collection_fans_out_from_collection_sources`
  28. `test_flow_source_is_deterministic_and_drive_waits_on_condition_with_timeout`
  29. `test_waiting_waits_on_the_temporal_timer_and_resumes_at_the_same_stage`

## 4. Lệnh đã chạy: bảng gồm lệnh, exit code, kết quả thật của các bước 8, 17, 18, 19, 20.
| Bước | Lệnh thực thi | Exit Code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 8 (RED) | `python -m pytest tests/integration/prod_wiring/test_pw_cat2_flow.py -q -p no:cacheprovider` | 1 | 29 failed, 1 passed in 3.38s |
| Bước 17 (GREEN mới) | `python -m pytest tests/integration/prod_wiring/test_pw_cat2_flow.py -q -p no:cacheprovider` | 0 | 30 passed in 2.38s |
| Bước 18 (GREEN cả suite) | `python -m pytest tests/integration/prod_wiring/test_pw_cat2_flow.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 0 | 39 passed in 2.45s |
| Bước 19 (Kiểm tra whitespace) | `git diff --check` | 0 | Không có trailing whitespace hoặc lỗi định dạng |
| Bước 20 (Probe tĩnh bắt buộc) | `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/workflows/flow.py').read_text(encoding='utf-8'); assert 'waiting' in t and 'time.sleep' not in t and 'datetime.now' not in t, 'PW-CAT2'"` | 0 | Exit code 0, không có AssertionError |

## 5. Assertion đã đổi trong test cp6: liệt kê từng dòng đã đổi kèm lý do; nếu không đổi dòng nào thì ghi đúng một câu `Không đổi dòng nào của test_cp6_video_production_flow.py: toàn bộ test đã nghiệm thu vẫn xanh sau thay đổi` kèm số test passed của tệp đó.
Không đổi dòng nào của test_cp6_video_production_flow.py: toàn bộ test đã nghiệm thu vẫn xanh sau thay đổi (9 passed).

## 6. Quyết định thiết kế: (a) input_refs của mỗi activity được tính một lần và đóng băng theo (stage, activity, index, revision) nên chạy lại không còn OPERATION_KEY_CONFLICT; input_refs khử trùng lặp theo (ref_type, ref_id); (b) fan-out: payload item_refs thắng; stage trước chưa từng chạy (debug flow) thì chạy một lần không item như cũ; stage trước đã chạy mà không có item đúng ref_type thì không chạy lần nào (handler fan-out chỉ nhận item thật); (c) waiting không tính là thất bại, không sleep trong flow, _drive chờ timer hoặc signal; (d) stage_run_id không đổi (DQ-04, mọi activity cùng stage dùng chung).

## 7. Đọc lại tính toàn vẹn ký tự: sau khi ghi, đọc lại tệp bằng công cụ đọc tệp và xác nhận chữ có dấu còn nguyên, không có ký tự ? thay thế.
- Tệp báo cáo được ghi với mã hóa UTF-8 không BOM, định dạng xuống dòng LF.
- Đã đọc lại tệp bằng công cụ đọc tệp và xác nhận chữ có dấu còn nguyên, không có ký tự ? thay thế.

## 8. Vá sau thu hồi grant G1 (rebase lên 23f547c6)
- **Finding**: Lệnh canh CP-6-WORKFLOW exit 1 vì `test_workflow_modules_are_deterministic[definitions.py]` thấy `import asyncio`.
- **Thay đổi đã làm ở definitions.py**:
  - Xoá `import asyncio` (dòng 3) cùng dòng trống ngay sau nó, để phần đầu tệp còn `from __future__ import annotations`, một dòng trống, rồi `from datetime import timedelta`.
  - Trong hàm `_drive`, đổi `except asyncio.TimeoutError:` thành `except TimeoutError:`.
  - Lý do: Python 3.13.15 coi `asyncio.TimeoutError` là bí danh của `TimeoutError` dựng sẵn, nên `workflow.wait_condition(..., timeout=...)` vẫn bị bắt đúng ngoại lệ và hành vi chờ timer của `workflow.wait_condition` không đổi.
- **Sửa dòng coveredIds của test_pw_cat2_flow.py**:
  - Sửa dòng 3 của docstring đầu tệp: thay `coveredIds: PW-CAT2-01..06, CT-WF-006, CT-WF-007, CT-ORC-007` bằng đúng `coveredIds: PW-CAT2-01, CT-WF-006, CT-WF-007, CT-ORC-007` để Control đọc đủ từng mã. Thân test không đổi.
- **Bảng lệnh đã chạy ở bước 4, 5, 7, 8, 9**:

| Bước | Lệnh thực thi | Exit Code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 4 | `python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 0 | 30 passed in 0.72s (test_workflow_modules_are_deterministic[definitions.py] xanh) |
| Bước 5 | `python -m pytest tests/integration/prod_wiring/test_pw_cat2_flow.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 0 | 39 passed in 2.41s (test chờ trên timer Temporal xanh) |
| Bước 7 | `git diff --check` | 0 | Exit code 0, không có lỗi whitespace |
| Bước 8 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/workflows/flow.py').read_text(encoding='utf-8'); assert 'waiting' in t and 'time.sleep' not in t and 'datetime.now' not in t, 'PW-CAT2'"` | 0 | Exit code 0, không có AssertionError |
| Bước 9 | `python -c "import pathlib; d = 'src/controlplane/application/orchestration/workflows/'; assert all('asyncio' not in pathlib.Path(d + n).read_text(encoding='utf-8') for n in ('definitions.py', 'flow.py')), 'asyncio'"` | 0 | Exit code 0: không còn chuỗi asyncio trong hai tệp |
