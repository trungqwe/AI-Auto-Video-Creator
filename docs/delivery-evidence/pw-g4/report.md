# Báo cáo chuyển giao: CapabilityReader, trạng thái job và batch (PW-G4)

- Task: PW-G4
- Milestone: M7
- Trạng thái: IMPLEMENTED

## 1. Tóm tắt

Gói công việc PW-G4 hoàn thành việc triển khai các thành phần đọc năng lực hệ thống (capability view), quản lý trạng thái công việc (`cp_video_jobs`) và vòng đời đợt sản xuất (`cp_production_batches`) trên cơ sở dữ liệu PostgreSQL thực tế:
- `CapabilityReader(probes)`: Xây dựng capability view cho `desktop_production` từ các probe được tiêm vào (`app_session_active`, `ffmpeg_pinned`, `gpu_lease_ready`). Bảng chân trị tuân thủ nghiêm ngặt: trả về `available` chỉ khi cả ba probe đều đạt (`True`); trả về `degraded` khi chỉ thiếu khe GPU nhưng còn CPU (`app_session_active` và `ffmpeg_pinned` đều `True`, `gpu_lease_ready` là `False`); trả về `unavailable` với mọi tổ hợp còn lại. Theo nguyên tắc an toàn đóng (fail-closed), bất kỳ probe nào ném ngoại lệ hoặc trả giá trị không phải boolean đều làm trạng thái trở thành `unknown` (không bao giờ trả về `available`), khiến workflow tạm dừng chờ đợi (`Wait(WaitReason.DESKTOP_OFFLINE)`). `CapabilityReader` hoạt động đồng bộ thuần túy và được activity `ReadCapabilityView` của PW-G3 gọi thông qua `asyncio.to_thread` nhằm không chặn vòng lặp sự kiện (event loop).
- `PostgresJobStates(connection, workspace_id)`: Quản lý cột trạng thái `status`, `revision`, `wait_reason` của bảng `cp_video_jobs` trên kết nối do bên gọi sở hữu. Sử dụng state machine thuần túy (`plan_job_transition` và `transition_job`), tăng số hiệu `revision` đơn điệu và từ chối mọi cạnh chuyển trạng thái nằm ngoài hợp đồng CT-STATE bằng `ForbiddenTransitionError` mà không ghi bất kỳ thay đổi nào xuống cơ sở dữ liệu.
- `PostgresBatchStates(connection, workspace_id)`: Hiện thực phương thức `finish(batch_id, outcome, reason, now)` cập nhật các trường `status`, `stop_reason`, `stopped_at` của bảng `cp_production_batches` theo đúng quy chuẩn CT-ORC-010. Đảm bảo tính idempotent: nếu trạng thái hiện hành đã bằng kết quả đích thì trả về `False` và không sửa đổi dòng.
- `JobLifecycleListener(connection_factory, workspace_id)`: Cài đặt giao diện `ResultListener` của PW-G2, chuyển trạng thái job theo chuỗi SNAPSHOTTED → ACTIVE → WAITING (kèm `wait_reason`) → ACTIVE → READY_FOR_COMPLETION. Mỗi kết quả activity được xử lý trong đúng một giao dịch riêng biệt, tự động commit.
- `BatchLifecycle(connection_factory, clock, workspace_id)`: Cung cấp API `finish(batch_id, status, reason)` khóa dòng và cập nhật trạng thái đợt sản xuất trong một giao dịch duy nhất.

## 2. Tệp đã đổi (Owned paths)

1. `src/controlplane/application/orchestration/capability_view.py`: Triển khai `CapabilityReader` fail-closed, thuần đồng bộ, không import `asyncio`, không sử dụng mock/fake hay `from src.`.
2. `src/controlplane/infrastructure/db/orchestration/job_states.py`: Triển khai `PostgresJobStates` và `PostgresBatchStates` tương tác PostgreSQL trên kết nối của caller, sử dụng pure state machine.
3. `src/controlplane/application/orchestration/job_lifecycle.py`: Triển khai `JobLifecycleListener` (cài đặt `ResultListener` PW-G2) và `BatchLifecycle` với giao dịch cô lập cho mỗi lần chuyển trạng thái.
4. `tests/integration/prod_wiring/test_pw_g4_job_states.py`: Bộ kiểm thử tích hợp toàn diện 98 test trên PostgreSQL thực tế kiểm chứng capability truth table, state machine invariants, chuỗi lifecycle listener và tính idempotent của batch finish.
5. `docs/delivery-evidence/pw-g4/report.md`: Báo cáo chuyển giao kỹ thuật UTF-8 đầy đủ dấu tiếng Việt.

## 3. Bằng chứng RED

- Lệnh chạy kiểm thử chứng kiến RED (bước 13):
  `python -m pytest tests/integration/prod_wiring/test_pw_g4_job_states.py -q -p no:cacheprovider`
- Mã thoát: `1`
- Kết quả kiểm thử: `97 failed, 1 passed in 31.35s`
  - Thu thập test thành công, không gặp lỗi cú pháp hay thiếu fixture cơ sở dữ liệu.
  - Test `test_only_available_and_degraded_let_a_desktop_stage_run` đạt vì chỉ kiểm thử logic domain có sẵn.
  - 97 test còn lại thất bại đúng dự kiến với ngoại lệ `NotImplementedError: PW-G4` từ các stub của CapabilityReader, PostgresJobStates, JobLifecycleListener, BatchLifecycle hoặc `AssertionError` kiểm tra mã nguồn.
- Dòng lỗi đại diện:
  - `E   NotImplementedError: PW-G4` (xuất phát từ `capability_view.py:7: NotImplementedError`)
  - `E   NotImplementedError: PW-G4` (xuất phát từ `job_states.py:10: NotImplementedError`)
  - `E   NotImplementedError: PW-G4` (xuất phát từ `job_lifecycle.py:10: NotImplementedError`)
  - `E   assert 'connection.transaction()' in SOURCES[1].read_text(encoding='utf-8')` (tại `test_sources_are_synchronous_and_use_the_state_machine`)

## 4. Lệnh đã chạy và kết quả xác minh

| Bước | Lệnh kiểm thử | Mã thoát | Kết quả xác minh |
| --- | --- | --- | --- |
| Bước 13 | `python -m pytest tests/integration/prod_wiring/test_pw_g4_job_states.py -q -p no:cacheprovider` | 1 | `97 failed, 1 passed in 31.35s` (chứng kiến RED hợp lệ từ stub) |
| Bước 19 | `python -m pytest tests/integration/prod_wiring/test_pw_g4_job_states.py -q -p no:cacheprovider` | 0 | `98 passed in 32.84s` (toàn bộ 98 test của PW-G4 xanh hoàn toàn) |
| Bước 20 | `python -m pytest tests/integration/prod_wiring/test_pw_g4_job_states.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 0 | `154 passed in 38.78s` (98 test PW-G4 + 43 test completion UoW + 13 test persist G đều đạt, không skip) |
| Bước 21 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/capability_view.py').read_text(encoding='utf-8').lower(); assert 'desktop_production' in t and 'fake' not in t and 'from src.' not in t, 'PW-G4'"` | 0 | Quét mã nguồn đạt: chứa `desktop_production`, không chứa `fake` và không chứa `from src.`. |
| Bước 23 | `git diff --check` | 0 | Sạch, không có khoảng trắng thừa hay lỗi định dạng dòng. |

## 5. Quyết định thiết kế

1. **Bảng chân trị và tính chất fail-closed của CapabilityReader**:
   - Trả về `available` khi và chỉ khi cả ba probe (`app_session_active`, `ffmpeg_pinned`, `gpu_lease_ready`) đều là `True`.
   - Trả về `degraded` khi `app_session_active` và `ffmpeg_pinned` đều `True` nhưng `gpu_lease_ready` là `False` (hệ thống thiếu khe GPU nhưng còn tài nguyên CPU để xử lý).
   - Trả về `unavailable` cho mọi tổ hợp còn lại.
   - Bất kỳ probe nào ném ngoại lệ hoặc trả về giá trị không phải boolean (`None`, số nguyên, chuỗi, danh sách, từ điển) đều lập tức đưa trạng thái về `unknown`.
   - `CapabilityReader` hoạt động đồng bộ hoàn toàn; activity `ReadCapabilityView` của PW-G3 gọi nó thông qua `asyncio.to_thread` nhằm bảo đảm probe chậm không làm nghến vòng lặp sự kiện.
2. **Quy tắc chuyển tiếp trạng thái job trong `JobLifecycleListener`**:
   - `JobLifecycleListener` chỉ cài đặt hook `on_result`, do đó trạng thái `ACTIVE` xuất hiện ở kết quả activity kế tiếp sau khi `BuildProductionSnapshot` thành công.
   - Khi job đang ở `SNAPSHOTTED` mà gặp activity có kết quả `waiting` hoặc `failed`, listener chủ động chuyển job sang `ACTIVE` trước khi áp dụng quyết định chờ hoặc thất bại, bởi vì mô hình trạng thái CT-STATE không có cạnh chuyển trực tiếp từ `SNAPSHOTTED` sang `WAITING` hay `FAILED_FINAL`.
3. **Phân loại kết quả failed và retry**:
   - Kết quả activity `failed` không retryable (`problem.retryable is not True`, kể cả khi không có `problem`) đưa job sang `FAILED_FINAL`, nhất quán với quy chuẩn PW-G2.
   - Kết quả `failed` retryable, `outcome_unknown`, hoặc `stale` giữ job tiếp tục ở trạng thái `ACTIVE`.
4. **Bảo vệ chống kết quả đến muộn và cạnh cấm CT-STATE**:
   - Kết quả activity đến muộn khi job đã đạt trạng thái dừng cuối cùng (`READY_FOR_COMPLETION`, `COMPLETED` hoặc `FAILED_FINAL`) được coi là no-op và bỏ qua an toàn.
   - Bất kỳ nỗ lực chuyển tiếp nào vi phạm đồ thị trạng thái CT-STATE đều bị `PostgresJobStates` từ chối bằng `ForbiddenTransitionError`, đồng thời không có bất kỳ dòng dữ liệu nào bị sửa đổi.
5. **Đồng bộ hóa quy tắc ghi nhận wait_reason**:
   - `wait_reason` của `cp_video_jobs` được trích xuất theo cùng quy tắc với `cp_stage_runs`: ưu tiên mã lỗi trong `problem.code` nếu thuộc danh mục `WaitReason`, ngược lại sử dụng `DEFAULT_WAIT_REASON` (`provider_unavailable`).
6. **Đặc tả BatchLifecycle.finish và tính chất Idempotent**:
   - Phương thức `BatchLifecycle.finish` chấp nhận các trạng thái dừng hợp lệ theo CT-ORC-010: `COMPLETED_TARGET`, `COMPLETED_EXHAUSTED`, `WAITING_CAPABILITY`, `FAILED_SYSTEM` (`CONTINUE` bị từ chối bằng `INVALID_BATCH_STATUS`).
   - Idempotent: nếu trạng thái của batch đã bằng trạng thái đích yêu cầu thì phương thức trả về `False` và không cập nhật lại dòng dữ liệu.
   - Do bảng `cp_production_batches` không có cột `revision`, state machine thuần túy được vận hành với cặp revision cố định (0, 0) tương tự mẫu đã áp dụng ở PW-G2, nhưng các cạnh chuyển tiếp vẫn được thẩm định nghiêm ngặt.

## 6. Khoảng hở và Open Items

1. **ActivityRejected không kích hoạt listener**: Khi một activity bị từ chối cấp quyền (`ActivityRejected`), hệ thống không gọi qua `ResultListener`, do đó stage run chuyển sang `FAILED_FINAL` vì bị từ chối sẽ không tự động đẩy job sang `FAILED_FINAL`.
2. **Job còn ở CREATED khi stage thất bại**: Nếu stage thất bại khi job vẫn đang ở trạng thái `CREATED` (chưa có snapshot), job được giữ nguyên ở `CREATED` vì CT-STATE không hỗ trợ cạnh chuyển từ `CREATED` sang `FAILED_FINAL`.
3. **Xóa stop_reason và stopped_at khi batch tái khởi động**: Các trường `stop_reason` và `stopped_at` của batch ở trạng thái `WAITING_CAPABILITY` chưa được xóa trắng khi batch được resume quay lại `RUNNING` (hành vi này do gói công việc resume thuộc PW-CAT2/PW-G7 phụ trách).
4. **Nối vào Composition Root**: Việc kết nối `CapabilityReader`, `JobLifecycleListener` và các probe phần cứng thực tế vào composition root thuộc phạm vi triển khai của gói PW-W1.

## 7. Đọc lại và xác nhận tính toàn vẹn ký tự

Đã đọc lại toàn bộ tệp báo cáo này bằng UTF-8:
- Toàn bộ dấu tiếng Việt được giữ nguyên vẹn 100%, không có ký tự lỗi, không có dấu hỏi ? thay thế và không biến dạng bảng mã.
- Các số liệu kiểm thử và kết quả lệnh hoàn toàn khớp với thực tế kiểm thử trên PostgreSQL.
