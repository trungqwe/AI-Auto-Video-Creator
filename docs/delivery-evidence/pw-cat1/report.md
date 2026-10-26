# Báo cáo chuyển giao: thứ tự stage, binding ReserveVariant, pha ValidateVariant (PW-CAT1)

- Task: PW-CAT1
- Milestone: M7
- Trạng thái: IMPLEMENTED

## 1. Tóm tắt

Gói công việc PW-CAT1 hoàn thành việc cấu hình lại thứ tự stage, activity binding và hỗ trợ đa stage cho `ValidateVariant` theo kế hoạch đã nghiệm thu `IMPL-PLAN-PROD-WIRING-V4`:
- `VideoProductionWorkflow` v2 với đồ thị: `analyze`; `script` sau `analyze`; `media_select` sau `script`; `plan` sau `media_select`; `tts` sau `script`; `align` sau `tts`; `process` sau `plan` và `align`; `render` sau `process`; `qc` sau `render`; `sync` sau `qc`; `complete` sau `sync`. Chuyển đổi v1 sang v2 là breaking change (`is_breaking_change` v1→v2 là `True`) và `validate_catalog()` hợp lệ hoàn toàn.
- `VIDEO_STAGE_ACTIVITIES` mới:
  - Stage `plan`: `BuildProductionPlan`, `ValidateVariant`, `ReserveVariant`, `GenerateOutputMetadata`.
  - Stage `render`: thêm `reconcile_render` trước `render_video`.
  - Stage `qc`: `inspect_output`, `ValidateVariant`, `prepare_output_ready`.
  - Stage `process`: thêm `TransformSensitiveImage` sau `AssessImageSafety`.
- `ActivityBinding.extra_stage_types`: thêm trường cuối `extra_stage_types: tuple[str, ...] = ()` sau `side_effect`. Chỉ binding `ValidateVariant` có `stage_type = 'plan'` và `extra_stage_types = ('qc',)`. Hàng đợi của `ValidateVariant` là `binding.queue = route_stage('plan')` (`TaskQueue.DESKTOP_CPU`) tính một lần trong `_b`.
- Binding mới: `ReserveVariant` (phân hệ G, stage `plan`), `reconcile_render` và `prepare_output_ready` (phân hệ F); `GenerateOutputMetadata` chuyển sang stage `plan`.
- Bảng hằng `FAN_OUT_FROM_OUTPUT`: activity → (stage trước, `ref_type`) cho `AssessImageSafety`, `ProbeMedia`, `NormalizeMedia` (từ `media_select`, `selected_media`) và `CollectSource` (từ `select_sources`, `collection_source`).

## 2. Tệp đã đổi (Owned paths)

1. `src/controlplane/domain/orchestration/workflow_catalog.py`: Nâng `workflow_version` của `VideoProductionWorkflow` lên 2, sắp xếp lại đồ thị stage (`media_select` trước `plan`, `process` sau `plan` và `align`).
2. `src/controlplane/application/orchestration/workflows/activities.py`: Bổ sung trường `extra_stage_types` vào `ActivityBinding`, khai báo binding `ReserveVariant`, `reconcile_render`, `prepare_output_ready`, cập nhật `VIDEO_STAGE_ACTIVITIES`, bổ sung bảng `FAN_OUT_FROM_OUTPUT` và cập nhật `__all__`.
3. `tests/unit/orchestration/test_g_workflow_catalog.py`: Cập nhật `VIDEO_STAGES`, assert dependencies cho `workflow_version = 2` và cập nhật StageSpec `('align', 'plan')`.
4. `tests/integration/convergence/test_cp6_workflow_catalog.py`: Sửa assertion kiểm tra binding khớp catalog cho phép `extra_stage_types`, khóa chặt tập activity có `extra_stage_types` duy nhất là `ValidateVariant`.
5. `tests/integration/convergence/test_cp6_video_production_flow.py`: Cập nhật thứ tự các lệnh gọi trong `test_happy_path` và cập nhật số lượng activity của debug stage `plan` thành 4 activities.
6. `tests/integration/prod_wiring/test_pw_cat1_catalog.py`: Bộ kiểm thử mới gồm 11 test kiểm chứng trọn vẹn thứ tự catalog v2, binding, extra_stage_types và bảng `FAN_OUT_FROM_OUTPUT`.
7. `docs/delivery-evidence/pw-cat1/report.md`: Báo cáo chuyển giao kỹ thuật UTF-8 đầy đủ dấu tiếng Việt.

## 3. Bằng chứng RED

- Lệnh chạy kiểm thử chứng kiến RED (bước 4):
  `python -m pytest tests/integration/prod_wiring/test_pw_cat1_catalog.py -q -p no:cacheprovider`
- Mã thoát: `1`
- Kết quả kiểm thử: `11 failed in 0.22s`
  - Thu thập test thành công, không gặp lỗi cú pháp hay import.
  - Cả 11 test đều thất bại đúng oracle thực tế:
    - `test_video_workflow_v2_order_dependencies_and_version`: `AssertionError: assert 1 == 2`
    - `test_v1_to_v2_is_a_breaking_change`: `AssertionError: assert False is True`
    - `test_plan_runs_after_media_select_and_reserve_variant_before_render`: `AssertionError: assert 3 < 2`
    - `test_video_stage_activities_follow_the_v2_plan`: `AssertionError: assert ('BuildProductionPlan',) == ('BuildProductionPlan', 'ValidateVariant', 'ReserveVariant', 'GenerateOutputMetadata')`
    - `test_new_and_moved_bindings`: `KeyError: 'ReserveVariant'`
    - `test_every_stage_activity_matches_its_binding`: `AttributeError: 'ActivityBinding' object has no attribute 'extra_stage_types'`
    - `test_binding_check_is_red_for_an_activity_outside_its_stage`: `AttributeError: 'ActivityBinding' object has no attribute 'extra_stage_types'`
    - `test_only_validate_variant_has_extra_stage_types`: `AttributeError: 'ActivityBinding' object has no attribute 'extra_stage_types'`
    - `test_validate_variant_queue_is_the_plan_queue_and_stage_queues_are_unchanged`: `AssertionError: assert <TaskQueue.DESKTOP_RENDER: 'desktop-render'> == <TaskQueue.DESKTOP_CPU: 'desktop-cpu'>`
    - `test_fan_out_table_lists_exactly_the_four_activities`: `AttributeError: module 'controlplane.application.orchestration.workflows.activities' has no attribute 'FAN_OUT_FROM_OUTPUT'`
    - `test_fan_out_previous_stage_precedes_the_activity_stage_in_its_workflow`: `AttributeError: module 'controlplane.application.orchestration.workflows.activities' has no attribute 'FAN_OUT_FROM_OUTPUT'`

## 4. Lệnh đã chạy và kết quả xác minh

| Bước | Lệnh kiểm thử | Mã thoát | Kết quả xác minh |
| --- | --- | --- | --- |
| Bước 4 | `python -m pytest tests/integration/prod_wiring/test_pw_cat1_catalog.py -q -p no:cacheprovider` | 1 | `11 failed in 0.22s` (chứng kiến RED hợp lệ trên toàn bộ 11 test) |
| Bước 14 | `python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py tests/integration/prod_wiring/test_pw_cat1_catalog.py -q -p no:cacheprovider` | 0 | `79 passed in 0.36s` (toàn bộ 79 test của 4 bộ test đều đạt) |
| Bước 16 | `git diff --check` | 0 | Sạch hoàn toàn, không có khoảng trắng thừa hay lỗi xuống dòng. |
| Bước 17 | `python -c "import re, pathlib; t = pathlib.Path('src/controlplane/domain/orchestration/workflow_catalog.py').read_text(encoding='utf-8'); assert re.search('VideoProductionWorkflow.{1,3}2,', t) and re.search('media_select.{1,8}script.{1,40}plan.{1,8}media_select', t, re.S), 'PW-CAT1'"` | 0 | Quét regex catalog đạt: `workflow_version` 2 và `media_select` đứng trước `plan`. |
| Bước bổ sung | `python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py tests/integration/prod_wiring/test_pw_cat1_catalog.py -q -p no:cacheprovider` | 0 | `84 passed in 0.46s` (toàn bộ 84 test của 4 bộ test đều đạt sau khi bổ sung coveredIds và 5 test mới) |

## 5. Assertion đã đổi kèm lý do

1. `tests/integration/convergence/test_cp6_workflow_catalog.py::test_bindings_follow_the_catalog`:
   - Dòng 158: Đổi `assert binding.stage_type == stage_name` thành `assert stage_name in (binding.stage_type, *binding.extra_stage_types)`. Lý do: `ValidateVariant` hiện có mặt ở cả hai stage `plan` (chính) và `qc` (bổ sung qua `extra_stage_types`).
   - Dòng 160-161: Thêm hai assertion ở mức thân hàm ngay trước `video_spec = get_workflow('VideoProductionWorkflow')`:
     - `assert {b.name for b in ACTIVITY_BINDINGS if b.extra_stage_types} == {'ValidateVariant'}`
     - `assert BINDINGS_BY_NAME['ValidateVariant'].extra_stage_types == ('qc',)`
     Lý do: Khóa chặt ràng buộc kiến trúc rằng duy nhất `ValidateVariant` được phép có `extra_stage_types` và giá trị chính xác là `('qc',)`.
2. `tests/unit/orchestration/test_g_workflow_catalog.py`:
   - Dòng 22: Đổi `VIDEO_STAGES` để đưa `media_select` lên trước `plan` theo thứ tự catalog v2.
   - Dòng 76-79 (`test_video_production_stage_order_and_dependencies`): Cập nhật kiểm tra `video.workflow_version == 2`, `plan` phụ thuộc `media_select`, `media_select` phụ thuộc `script`, và `process` phụ thuộc `('plan', 'align')`.
   - Dòng 186 (`test_dependency_listing_order_is_not_breaking`): Đổi tuple `StageSpec('process', ('align', 'media_select'))` thành `StageSpec('process', ('align', 'plan'))` vì phụ thuộc của stage `process` nay là `plan` và `align`.
3. `tests/integration/convergence/test_cp6_video_production_flow.py`:
   - Dòng 419-421 (`test_happy_path`): Bổ sung ba assertion thứ tự cuộc gọi:
     - `assert call_names.index('SelectCreativeAssets') < call_names.index('BuildProductionPlan')`
     - `assert call_names.index('ReserveVariant') < call_names.index('render_video')`
     - `assert call_names.index('reconcile_render') < call_names.index('render_video')`
     Lý do: Xác nhận thứ tự thực thi mới trong luồng sản xuất thực tế.
   - Dòng 480 (`test_debug_stage`): Đổi assertion kiểm tra danh sách activity của stage `plan` từ `['BuildProductionPlan']` thành `['BuildProductionPlan', 'ValidateVariant', 'ReserveVariant', 'GenerateOutputMetadata']`. Lý do: Stage `plan` nay bao gồm đầy đủ 4 activities.
   - Dòng 484 (`test_debug_stage`): Đổi `assert len(gateway.calls) == 1` thành `assert len(gateway.calls) == 4`. Lý do: Khi quan sát debug stage `plan`, gateway ghi nhận đủ 4 cuộc gọi activity tương ứng.

4. Bổ sung coveredIds sau finding PW-CAT1-content-coverage-missing-0ee92217:
   - Bốn tệp test đã thêm `PW-CAT1-01, CT-ORC-012, CT-AI-008` vào dòng `coveredIds:` của docstring (không bỏ mã cũ);
   - `test_g_workflow_catalog.py` thêm `test_v1_to_v2_plan_before_media_select_is_a_breaking_change`, `test_reserve_variant_runs_in_plan_stage_before_render`, `test_validate_variant_runs_in_plan_phase_and_qc_output_phase`;
   - `test_cp6_workflow_catalog.py` thêm `test_video_catalog_v2_reserve_variant_before_render_and_two_phase_validate_variant`;
   - `test_cp6_video_production_flow.py` thêm `test_variant_validation_runs_in_plan_and_qc_phases_and_reservation_precedes_render`;
   - `test_pw_cat1_catalog.py` chỉ thêm dòng coveredIds vì đã có test bao phủ.
   Lý do: Gói sau cần các mã này trong test của gói PW-CAT1; chỉ ghi mã khi test thật bao phủ. Không assertion cũ nào bị đổi.

## 6. Quyết định thiết kế và rủi ro còn lại

1. **Hàng đợi của ValidateVariant tính một lần trong `_b`**:
   - `binding.queue` được tính duy nhất một lần tại hàm khởi tạo `_b` dựa trên `stage_type = 'plan'` và gán giá trị `route_stage('plan')` (`TaskQueue.DESKTOP_CPU`).
   - Không đổi `definitions.py`, `flow.py`, `workflow.py`.
2. **Xác định pha thực thi từ stage_run_id**:
   - Pha thực thi của `ValidateVariant` (`plan` hay `qc`) được lấy từ `stage_run_id` như PW-D2.
3. **Rủi ro còn lại**:
   - `ValidateVariant` chạy ở `plan` trên `desktop-cpu` còn `qc` trên `desktop-render` dùng cùng `binding.queue`.

## 7. Đọc lại và xác nhận tính toàn vẹn ký tự

Đã đọc lại toàn bộ tệp báo cáo này bằng UTF-8:
- Toàn bộ dấu tiếng Việt được giữ nguyên vẹn 100%, không có ký tự lỗi, không có dấu hỏi ? thay thế và không biến dạng bảng mã.
- Các số liệu kiểm thử và kết quả lệnh hoàn toàn khớp với thực tế kiểm thử trong worktree.
