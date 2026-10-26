# Báo cáo PW-VERT

## 1. Phạm vi
Thực hiện trong ba tệp thuộc owned paths của nhiệm vụ PW-VERT:
- `tests/integration/prod_wiring/pw_vertical.py`: dựng khung dọc tích hợp ráp các thành phần thực của phân hệ G (PostgresAppSessions, ResultRecordingDispatcher, GrantRevokingDispatcher, build_grant_issuer, CapabilityReader, OutboxRelay, AllocateJobService, FinalizeBatchService, reserve_variant_handler, commit_video_completion_handler) vào build_workflow_services và build_temporal_registration; cùng các adapter giả DesktopAdapters cho các phân hệ D, E, F, I chỉ ghi dữ kiện tối thiểu vào CSDL thực.
- `tests/integration/prod_wiring/test_pw_vert_video_flow.py`: tạo bộ 8 ca kiểm thử chạy trên Temporal server test và PostgreSQL 18.6 thử nghiệm bao phủ toàn bộ vòng đời sản xuất video.
- `docs/delivery-evidence/pw-vert/report.md`: tệp báo cáo bằng chứng nghiệm thu này.

Không sửa hay chạm vào bất kỳ tệp nào ngoài ba owned paths trên. Không chạm mã nguồn sản phẩm trong src/, không sửa migration, không sửa conftest.py, không import pw_support.py và không thay đổi composition root.

## 2. Thiết kế
- Thành phần G thực được ráp:
  - PostgresAppSessions: quản lý session ứng dụng và recovery epoch trong CSDL thực.
  - ResultRecordingDispatcher: bọc dispatcher hoạt động để ghi nhận kết quả và phát sự kiện tiến độ cho listener.
  - JobLifecycleListener: lắng nghe kết quả từng stage để cập nhật trạng thái video job.
  - JobStatusTrace: bọc listener để theo dõi chính xác lịch sử chuyển đổi trạng thái của job (SNAPSHOTTED, ACTIVE, WAITING, READY_FOR_COMPLETION, COMPLETED).
  - GrantRevokingDispatcher: bọc ngoài cùng quanh dispatcher để tự động thu hồi grant ngay sau khi activity kết thúc thành công, ngăn chặn lỗi ActiveGrantExistsError ở các stage có nhiều activity liên tiếp.
  - build_grant_issuer: phát hành grant thực thi với fencing epoch vào bảng cp_execution_grants.
  - CapabilityReader: kiểm tra năng lực với probe app_session_active đọc trực tiếp từ bảng cp_app_sessions trên CSDL PostgreSQL thực, cùng các probe ffmpeg_pinned và gpu_lease_ready.
  - OutboxRelay: quét và chuyển tiếp sự kiện outbox production_batch.start_accepted để khởi chạy ProductionBatchWorkflow.
  - AllocateJobService và FinalizeBatchService: các dịch vụ phân bổ job và chốt đợt sản xuất thực của phân hệ G.
  - reserve_variant_handler và commit_video_completion_handler: hai dịch vụ nghiệp vụ đặt chỗ biến thể và xác nhận hoàn tất video thực, được bọc qua service_handler.
- Adapter giả của D, E, F, I (DesktopAdapters):
  - Chỉ ghi dữ kiện tối thiểu vào các bảng thực mà quy trình hoàn tất video (CommitVideoCompletion) đòi hỏi:
    - ValidateVariant: ghi bản ghi kiểm định biến thể vào cp_variant_validations (pha plan ghi revision 1, pha output ghi revision 2).
    - GenerateOutputMetadata: ghi siêu dữ liệu xuất bản vào cp_output_metadata.
    - SelectCreativeAssets: ghi lựa chọn sáng tạo vào cp_creative_selections, trả đúng một ref selected_media.
    - render_video: ghi phiên bản video artifact mp4 vào cp_artifact_versions.
    - inspect_output: ghi báo cáo QC đạt chuẩn (passed = True) vào cp_quality_reports.
    - PersistVideoOutput: ghi vị trí lưu trữ đám mây ở trạng thái VERIFIED vào cp_artifact_locations.
  - Các activity giả còn lại trong sáu stage không có writer riêng chỉ trả về ref đại diện theo bảng REFS mà không ghi CSDL.
  - Hỗ trợ tiêm lỗi mô phỏng: fail_plan_validation (mô phỏng validator bận gây retry trong stage plan) và drop_capability_on (mô phỏng mất kết nối desktop trong lúc chạy activity).
- Bảng 11 stage và số lượng activity (tổng cộng 26 activity):
  - analyze: 2 activity (BuildProductionSnapshot, AnalyzeContent).
  - script: 2 activity (GenerateStoryAngles, GenerateScript).
  - plan: 4 activity (BuildProductionPlan, ValidateVariant, ReserveVariant, GenerateOutputMetadata).
  - media_select: 1 activity (SelectCreativeAssets).
  - tts: 1 activity (CreateVoiceTrack).
  - align: 1 activity (CreateWordTiming).
  - process: 5 activity (ProbeMedia, AssessImageSafety, TransformSensitiveImage, NormalizeMedia, PrepareAudioBed).
  - render: 5 activity (MaterializeArtifactSet, resolve_render_package, render_video, validate_render_package, reconcile_render).
  - qc: 3 activity (inspect_output, ValidateVariant, prepare_output_ready).
  - sync: 1 activity (PersistVideoOutput).
  - complete: 1 activity (CommitVideoCompletion).
- ScriptedCandidateSelector: đóng vai trò adapter giả cổng chọn ứng viên của phân hệ B, cung cấp ứng viên mẫu cho đợt sản xuất.
- Ánh xạ 8 ca kiểm thử:
  - Ca 1 (test_one_video_batch_runs_all_eleven_stages_to_completed): kiểm tra đợt 1 video khởi chạy qua relay đi hết 11 stage tới COMPLETED, batch đạt TARGET_REACHED, ledger ghi đúng một dòng. Bao phủ yêu cầu 1, 2 và mã PW-VERT-01, CT-ORC-010.
  - Ca 2 (test_capability_unavailable_holds_before_the_desktop_stage_then_resumes): kiểm tra capability unavailable khiến workflow tạm giữ trước stage desktop và tự tiếp tục khi available, không có stage nào chạy lại. Bao phủ yêu cầu 3 và mã CT-WF-007.
  - Ca 3 (test_a_capability_drop_during_an_activity_marks_the_job_waiting_then_it_resumes): kiểm tra capability bị ngắt giữa activity khiến job chuyển trạng thái WAITING kèm lý do desktop_offline, sau đó hồi phục và chạy tiếp tới COMPLETED. Bao phủ yêu cầu 3 và mã CT-WF-007.
  - Ca 4 (test_retry_stage_after_the_second_activity_failed_reruns_only_that_activity): kiểm tra tín hiệu RetryStage sau khi activity thứ hai của stage plan thất bại ba lần chỉ chạy lại đúng activity đó, không chạy lại activity đầu, không phát sinh lỗi grant tồn tại. Bao phủ yêu cầu 3 và mã CT-WF-004.
  - Ca 5 (test_stopping_the_worker_between_two_stages_and_starting_a_new_one_reruns_nothing): kiểm tra việc dừng worker giữa hai stage rồi dựng worker mới trên cùng CSDL với epoch mới không làm chạy lại stage đã hoàn thành. Bao phủ yêu cầu 3 và mã CT-WF-007.
  - Ca 6 (test_without_grant_revocation_the_second_activity_hits_active_grant_exists): đối chứng phản ví dụ khi tắt thu hồi grant (revoke_grants = False), stage hai activity lập tức gặp lỗi ActiveGrantExistsError làm child FAILED tại stage analyze. Bao phủ mã CT-WF-004.
  - Ca 7 (test_pw_vertical_assembles_the_real_g_components_without_in_memory_stores): kiểm tra AST mã nguồn ráp đủ thành phần thực của G, không dùng kho InMemory nào, không tạo handler giả. Bao phủ yêu cầu 1 và mã PW-VERT-01.
  - Ca 8 (test_module_docstring_declares_covered_ids): xác nhận docstring tệp kiểm thử khai báo đầy đủ các mã yêu cầu.

## 3. Mục mở
- OI-PW-VERT-01: Lệnh start_batch khởi tạo batch ở trạng thái CREATED và hiện tại trong mã nguồn sản xuất chưa có writer nào chuyển trạng thái từ CREATED sang RUNNING, trong khi hoạt động FinalizeBatch đòi hỏi trạng thái batch phải là RUNNING hoặc WAITING_CAPABILITY. Do đó phương thức Vertical.start_batch thực hiện cập nhật status = 'RUNNING' như một bước thiết lập của môi trường kiểm thử. Mục này cần được bổ sung bởi gói sở hữu vòng đời đợt sản xuất (phân hệ G hoặc PW-W1).
- OI-PW-VERT-02: Cổng kiểm tra năng lực (capability gate) của workflow ở các stage desktop chỉ làm workflow tạm chờ trong Temporal mà không cập nhật bản ghi cp_video_jobs sang trạng thái WAITING. Bản ghi job chỉ chuyển sang WAITING khi chính activity trả về disposition là waiting kèm lý do chờ. Ca kiểm thử số 2 đã xác nhận job giữ trạng thái ACTIVE trong thời gian chờ cổng, và ca kiểm thử số 3 xác nhận job chuyển sang WAITING khi activity trả về waiting.
- GIẢ ĐỊNH: Thiết lập chu kỳ kiểm tra hạn mức và năng lực ai.quota_wait_poll_seconds: 0.2 giây trong cấu hình kiểm thử để các ca kiểm tra năng lực diễn ra nhanh chóng mà không phải chờ 60 giây thực.

## 4. Lệnh đã chạy
| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_vert_video_flow.py -q -p no:cacheprovider` (bước 14) | 1 | 6 failed, 2 passed in 174.15s (chứng kiến RED oracle nghiệp vụ do thiếu GrantRevokingDispatcher) |
| `python -m pytest tests/integration/prod_wiring/test_pw_vert_video_flow.py -q -p no:cacheprovider` (bước 16) | 0 | 8 passed in 28.01s (toàn bộ 8 ca kiểm thử GREEN sau khi ráp GrantRevokingDispatcher) |
| `git diff --check` (bước 18) | 0 | PASS: không có lỗi khoảng trắng thừa |
| `python -c "import pathlib; t = pathlib.Path('tests/integration/prod_wiring/pw_vertical.py').read_text(encoding='utf-8'); assert 'InMemoryGrantStore' not in t and 'OutboxRelay' in t and 'GrantRevokingDispatcher' in t, 'PW-VERT'"` (bước 19) | 0 | PASS: kiểm chứng AST không có InMemoryGrantStore, có OutboxRelay và GrantRevokingDispatcher |
| `python -c "import pathlib, re; t = pathlib.Path('tests/integration/prod_wiring/test_pw_vert_video_flow.py').read_text(encoding='utf-8'); m = re.search(r'coveredIds: (.+)', t); assert m is not None, 'coveredIds'; ids = set(x.strip() for x in m.group(1).split(',')); assert {'PW-VERT-01', 'CT-WF-004', 'CT-WF-007', 'CT-ORC-010'} <= ids, ids"` (bước 20) | 0 | PASS: docstring test khai báo đủ 4 coveredIds |
| `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-vert/report.md').read_text(encoding='utf-8'); v = pathlib.Path('tests/integration/prod_wiring/pw_vertical.py').read_text(encoding='utf-8'); assert 'PW-VERT' in t and chr(63) not in t and chr(65533) not in t and any(ord(c) > 127 for c in t), 'report'; assert 'from src.' not in v and 'import src' not in v and 'InMemory' not in v, 'vertical'"` (bước 21) | 0 | PASS: báo cáo tiếng Việt đầy đủ dấu và không có ký tự hỏi chấm |

## 5. Oracle
- RED (bước 14):
  - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_vert_video_flow.py -q -p no:cacheprovider`
  - Kết quả: Exit code 1; 6 failed, 2 passed trong 174.15 giây.
  - Danh sách ca kiểm thử thất bại:
    - test_one_video_batch_runs_all_eleven_stages_to_completed
    - test_capability_unavailable_holds_before_the_desktop_stage_then_resumes
    - test_a_capability_drop_during_an_activity_marks_the_job_waiting_then_it_resumes
    - test_retry_stage_after_the_second_activity_failed_reruns_only_that_activity
    - test_stopping_the_worker_between_two_stages_and_starting_a_new_one_reruns_nothing
    - test_pw_vertical_assembles_the_real_g_components_without_in_memory_stores
  - Dòng assert đầu tiên của ca kiểm thử thứ nhất thất bại:
    assert (result['status'], result['completed'], result['failed'], result['allocated'], result['finalized']) == ('TARGET_REACHED', 1, 0, 1, True), result
    Ném lỗi AssertionError: {'allocated': 1, 'children': [{'child_id': 'a3afd4d7-fbe7-4f50-a750-5cb531618074:video:0', 'status': 'FAILED'}], 'completed': 0, 'failed': 1, ...} do child workflow thất bại tại stage analyze vì ném lỗi ActiveGrantExistsError: ACTIVE_GRANT_EXISTS: ...:analyze:r1.
  - Ca kiểm thử AST thất bại do thiếu lời gọi GrantRevokingDispatcher.
  - Ca kiểm thử đối chứng số 6 đạt (test_without_grant_revocation_the_second_activity_hits_active_grant_exists PASS).
- GREEN (bước 16):
  - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_vert_video_flow.py -q -p no:cacheprovider`
  - Kết quả: Exit code 0; toàn bộ 8 ca kiểm thử đạt (8 passed in 28.01s).
  - Sau khi nối GrantRevokingDispatcher bọc ngoài ResultRecordingDispatcher, các grant được thu hồi ngay sau khi activity hoàn tất, stage hai activity chạy thông suốt và toàn bộ 11 stage của video hoàn thành mỹ mãn tới COMPLETED.

## 6. Giới hạn
- Chỉ chạy trên máy chủ kiểm thử thời gian của temporalio (WorkflowEnvironment.start_time_skipping) và cơ sở dữ liệu PostgreSQL 18.6 cục bộ (loopback).
- Các handler của phân hệ D, E, F, I là adapter giả (DesktopAdapters), chỉ ghi nhận dữ liệu tối thiểu phục vụ kiểm thử hoàn tất video mà không thực thi tính toán media hay render thực tế.
- Chưa kích hoạt môi trường sản xuất (PRODUCTION_ACTIVATION_BLOCKED).
