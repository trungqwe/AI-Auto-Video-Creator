# Báo cáo bằng chứng G-12

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline HEAD: 1aa9fb870e8a8392dbce3c22dc7392695909f4f9
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-12 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cacheprovider (chạy trên khung RED chưa có logic ở bước 9)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 64 failed, 18 passed in 0.63s
- Chi tiết các dòng FAILED tiêu biểu:
  - FAILED tests/unit/orchestration/test_g_workflow_catalog.py::test_catalog_has_exactly_the_six_ct_wf_001_workflows - AssertionError: assert [] == ['DailyCollectionWorkflow', 'ContentEnrichmentWorkflow', 'ProductionBatchWorkflow', 'VideoProductionWorkflow', 'DebugStageWorkflow', 'MaintenanceWorkflow']
  - FAILED tests/unit/orchestration/test_g_workflow_catalog.py::test_shipped_catalog_is_valid - NotImplementedError: G-12 RED stub: validate_catalog
  - FAILED tests/unit/orchestration/test_g_workflow_catalog.py::test_video_production_stage_order_and_dependencies - NotImplementedError: G-12 RED stub: get_workflow
  - FAILED tests/unit/orchestration/test_g_workflow_catalog.py::test_route_stage_maps_stage_type_to_logical_queue[collect-cloud-io] - NotImplementedError: G-12 RED stub: route_stage
  - FAILED tests/unit/orchestration/test_g_resource_admission.py::test_enough_resources_is_admitted - NotImplementedError: G-12 RED stub: decide_admission
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 18 test hợp lệ (	est_task_queue_has_exactly_the_six_ct_wf_002_values, 	est_module_imports_only_stdlib_and_controlplane_domain trong test_g_workflow_catalog; 	est_deferral_codes_are_exactly_the_four_d8_g_06_values, 	est_every_field_is_required_without_default [3 trường hợp], 	est_types_and_ranges_are_validated [3 trường hợp], 	est_cpu_percent_must_be_within_range [3 trường hợp], 	est_value_objects_are_frozen [3 trường hợp], 	est_deferred_requires_a_deferral_code, 	est_thresholds_are_not_read_from_policy_files_or_environment, 	est_module_imports_only_stdlib_and_controlplane_domain trong test_g_resource_admission) đã PASS ngay từ đầu. Tất cả 64 test thất bại đều là NotImplementedError do stub 'G-12 RED stub: ...' hoặc AssertionError do catalog rỗng ban đầu.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cacheprovider (chạy sau khi cài đặt logic ở bước 13)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 82 passed in 0.13s

## Thay đổi

- 5 tệp thuộc owned paths:
  - src/controlplane/domain/orchestration/workflow_catalog.py: Khai báo frozen cho sáu workflow theo CT-WF-001 kèm workflow_version và stage dependencies; ánh xạ STAGE_QUEUES sang sáu hàng đợi theo CT-WF-002; triển khai route_stage, get_workflow, validate_catalog (kiểm tra không chu trình, kiểm tra queue, R18 và ràng buộc isolated child/auto_advance) và is_breaking_change theo CT-WF-009.
  - src/controlplane/domain/orchestration/resource_admission.py: Khai báo value object AdmissionLimits, ResourceSnapshot, ResourceNeed bắt buộc mọi tham số không có giá trị mặc định; enum DeferralCode gồm 4 mã theo D8-G-06; triển khai decide_admission thuần túy đánh giá tuần tự theo thứ tự mạng, CPU, GPU, RAM, đĩa trả về Admitted, Deferred hoặc Wait(WaitReason.INSUFFICIENT_DISK).
  - 	ests/unit/orchestration/test_g_workflow_catalog.py: Bộ kiểm thử đơn vị toàn diện gồm 47 test cases xác minh 6 workflow, 6 hàng đợi, dữ liệu frozen, tính hợp lệ của catalog mặc định, thứ tự dependency của VideoProductionWorkflow, route_stage cho các stage type, bảo vệ R18 cho queue desktop, từ chối chu trình/stage thiếu queue/child không cô lập/debug auto_advance, phát hiện breaking changes và ranh giới import.
  - 	ests/unit/orchestration/test_g_resource_admission.py: Bộ kiểm thử đơn vị toàn diện gồm 35 test cases xác minh phân định tài nguyên đủ thì Admitted, bão hòa tài nguyên trả về Deferred mà không WAITING, 4 mã DeferralCode, ngưỡng biên chính xác, tài nguyên không cần không chặn, thiếu đĩa trả về Wait(INSUFFICIENT_DISK), thứ tự kiểm tra, bão hòa không bao giờ làm job FAILED_FINAL, mọi trường bắt buộc không có default, kiểm tra kiểu/miền giá trị, tính bất biến frozen, từ chối tham số sai, không đọc cấu hình tệp hay môi trường và ranh giới import.
  - docs/delivery-evidence/g-12/report.md: Báo cáo bằng chứng nghiệm thu lưu lại chi tiết môi trường, RED, GREEN, thay đổi, lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds và pendingUserCheckpoint.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cacheprovider | 0 | 82 passed in 0.13s |
| 2 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Map stage_type sang queue: script và tts ở desktop-gpu, plan và các stage desktop khác ở desktop-cpu, render và qc ở desktop-render, sync ở cloud-io, complete và điều phối ở control-workflows.
2. Tập stage_type mở rộng thêm select_sources, normalize, dedup, enrich_ai, media, index, allocate, run_videos, debug_observe, reconcile, cleanup, backup_check theo D8-G-05.
3. is_breaking_change so chuỗi (stage_type, dependency đã sắp xếp), retry_semantics, completion_invariant; bump version đơn thuần không phải breaking.
4. ResourceNeed là tham số bắt buộc thứ ba; ngưỡng AdmissionLimits gồm cpu_max_percent, ram_reserve_mb, disk_reserve_mb là tham số bắt buộc lấy từ cấu hình J (D8-G-07, ERR-G-07).
5. Thứ tự kiểm mạng, CPU, GPU, RAM, đĩa; CPU bão hòa khi cpu >= cpu_max_percent.
6. Wait và WaitReason.INSUFFICIENT_DISK tái dùng từ job_waiting.

## Ánh xạ phản ví dụ

- Script ở queue cloud: Được loại trừ bởi test 	est_r18_stage_on_non_desktop_queue_is_rejected.
- Breaking change không bị phát hiện: Được loại trừ bởi test 	est_stage_order_change_is_breaking và 	est_retry_semantics_or_completion_invariant_change_is_breaking.
- Bão hòa làm FAILED_FINAL: Được loại trừ bởi test 	est_saturation_never_fails_the_job_and_disk_wait_maps_to_job_waiting.
- Ngưỡng từ schedule-policy.yaml: Được loại trừ bởi test 	est_thresholds_are_not_read_from_policy_files_or_environment và 	est_every_field_is_required_without_default.

## coveredIds

- CT-WF-001
- CT-WF-002
- CT-WF-009
- D8-G-06
- D8-G-07
- EG-M7-G-6

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- PUC-G-05
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Chỉ dùng thư viện chuẩn Python (stdlib) và gói domain nội bộ controlplane.domain.
- Không gọi dịch vụ thật; không đọc cấu hình ngoài.
