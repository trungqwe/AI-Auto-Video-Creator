# Báo cáo chuyển giao: Ghi cp_stage_runs và bộ ghi kết quả activity (PW-G2)

- Task: PW-G2
- Milestone: M7
- Trạng thái: IMPLEMENTED

## 1. Tóm tắt

Gói công việc PW-G2 triển khai bộ lưu trữ PostgreSQL `PostgresStageRuns` cho bảng `cp_stage_runs` và bộ điều phối bao bọc `ResultRecordingDispatcher` để ghi nhận trạng thái và kết quả thực thi các activity theo đúng state machine của hệ thống:
- `PostgresStageRuns`: Thao tác trên kết nối do caller quản lý (không tự quản lý giao dịch hay commit/rollback), hỗ trợ phương thức `ensure(...)` idempotent chèn hàng `PENDING` dựa trên định dạng `stage_run_id` `<owner>:<stage>:r<revision>`, phân biệt `job_id` và `workflow_id`; phương thức `transition(...)` chuyển đổi trạng thái qua máy trạng thái thuần `transition_stage_run` với kiểm tra cạnh cấm ném `ForbiddenTransitionError`; phương thức `record_wait(...)` cập nhật `wait_reason` cho hàng đang `RUNNING`.
- `ResultRecordingDispatcher`: Bao bọc `ActivityDispatcher.dispatch`, ghi nhận trạng thái `PENDING -> RUNNING` trước khi ủy quyền thực thi cho handler bên trong, và sau đó ghi nhận trạng thái kết quả tương ứng với từng `disposition` (`succeeded` -> `SUCCEEDED`, `outcome_unknown` -> `OUTCOME_UNKNOWN`, `stale` -> `STALE`, `failed` -> `FAILED_RETRYABLE` hoặc `FAILED_FINAL`, `waiting` cập nhật `wait_reason`). Mỗi lần ghi là một giao dịch riêng biệt độc lập được commit thông qua `connection_factory`. Xử lý ngoại lệ `ActivityRejected` fail-closed (ghi nhận `FAILED_FINAL` và ném lại nguyên vẹn); kích hoạt danh sách `listeners` sau khi ghi nhận thành công.

## 2. Tệp đã đổi (Owned paths)

1. `src/controlplane/infrastructure/db/orchestration/stage_runs.py`: Hiện thực kho `PostgresStageRuns`, hàm phân tích `parse_stage_run_id`, hằng số trạng thái và kiểm tra ràng buộc.
2. `src/controlplane/application/orchestration/result_recorder.py`: Hiện thực `ResultRecordingDispatcher`, giao thức `ResultListener` và các hàm phân tích kết quả, grant, lý do chờ.
3. `tests/integration/prod_wiring/test_pw_g2_stage_runs.py`: Bộ kiểm thử tích hợp 33 test bao gồm store, 8 trường hợp disposition, ActivityRejected, listeners, xử lý lỗi handler, dispatch lần hai và quét token cấm.
4. `docs/delivery-evidence/pw-g2/report.md`: Báo cáo chuyển giao kỹ thuật đầy đủ dấu tiếng Việt.

## 3. Bằng chứng RED

- Lệnh chạy kiểm thử chứng kiến RED (bước 7):
  `python -m pytest tests/integration/prod_wiring/test_pw_g2_stage_runs.py -q -p no:cacheprovider`
- Mã thoát: `1`
- Kết quả kiểm thử: `32 failed, 1 passed in 11.44s`
  - 1 passed: `test_sources_have_no_forbidden_tokens_and_stay_synchronous`
  - 32 failed: Các test store và dispatcher đều đỏ vì `NotImplementedError: PW-G2` (oracle hành vi stub).
- Dòng lỗi đại diện:
  `E       NotImplementedError: PW-G2`
  xuất phát từ `src/controlplane/infrastructure/db/orchestration/stage_runs.py:24: NotImplementedError` và `src/controlplane/application/orchestration/result_recorder.py:15: NotImplementedError`.

## 4. Lệnh đã chạy và kết quả xác minh

| Bước | Lệnh kiểm thử | Mã thoát | Kết quả xác minh |
| --- | --- | --- | --- |
| Bước 12 | `python -m pytest tests/integration/prod_wiring/test_pw_g2_stage_runs.py -q -p no:cacheprovider` | 0 | `33 passed in 12.11s` (toàn bộ 33 test chức năng và tích hợp xanh) |
| Bước 13 | `python -m pytest tests/integration/prod_wiring/test_pw_g2_stage_runs.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 0 | `89 passed in 19.41s` (33 test PW-G2 + 40 test CP5 completion UoW + 16 test persist G postgres) |
| Bước 14 | `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/controlplane/infrastructure/db/orchestration/stage_runs.py', 'src/controlplane/application/orchestration/result_recorder.py']); assert 'from src.' not in t and 'fake' not in t and 'mock' not in t, 'PW-G2'"` | 0 | Đạt yêu cầu không chứa các token cấm `from src.`, `fake`, `mock`. |
| Bước 16 | `git diff --check` | 0 | Không có cảnh báo định dạng hay khoảng trắng thừa. |

## 5. Quyết định thiết kế D8 và các khoảng hở kiến trúc

1. **Khoảng hở CT-STATE-008 đối với disposition `waiting`**:
   Máy trạng thái `CT-STATE-008` không có cạnh chuyển trạng thái từ `RUNNING` sang `WAITING_CAPABILITY`, và người dùng đã phê duyệt giữ nguyên mọi cạnh của `CT-STATE`. Do đó, khi activity trả về disposition `waiting`, dispatcher thực hiện cập nhật `wait_reason` (lấy từ `problem.code` nếu thuộc tập `WaitReason`, mặc định là `provider_unavailable`), trong khi trạng thái của hàng vẫn giữ nguyên `RUNNING`. Phương thức `transition(...)` vẫn hỗ trợ chuyển trạng thái hợp lệ sang `WAITING_CAPABILITY` từ `PENDING`. Yêu cầu nghiệm thu nguyên văn `waiting -> WAITING_CAPABILITY` được ghi nhận khoảng hở này để AI PM và kiến trúc xem xét.
2. **Tái sử dụng `stage_run_id` trong `flow.py`**:
   `flow.py` hiện tại sử dụng lại cùng một `stage_run_id` cho nhiều activity trong cùng một stage và cho các lần retry, trong khi quy tắc G-06 / D8-G-01 yêu cầu mỗi attempt cần một hàng riêng biệt. Hiện thực của `ResultRecordingDispatcher` đảm bảo hàng đã rời khỏi `RUNNING` sẽ không bị mở lại, kết quả của activity sau đó không ghi đè vào hàng đã hoàn tất, và `listeners` vẫn được gọi đầy đủ. Việc điều chỉnh `stage_run_id` theo attempt thuộc phạm vi của task `PW-CAT2`.
3. **Bổ sung tham số `workspace_id` trong chữ ký khởi tạo**:
   Chữ ký mô tả trong brief ban đầu chưa có `workspace_id`, tuy nhiên `PostgresStageRuns` bắt buộc cần `workspace_id` để cách ly dữ liệu nhiều người thuê. Do đó, tham số keyword-only `workspace_id: str` đã được bổ sung vào cuối hàm `ResultRecordingDispatcher.__init__`.
4. **Xử lý `ActivityRejected`**:
   Khi `inner.dispatch` ném ngoại lệ `ActivityRejected`, dispatcher ghi nhận trạng thái hàng từ `RUNNING` sang `FAILED_FINAL` với `problem = {'code': exc.code, 'retryable': False}`, sau đó `raise` lại nguyên vẹn ngoại lệ để caller xử lý. Các request không chứa `stage_run_id` hợp lệ sẽ bị bỏ qua không ghi hàng.
5. **Trích xuất `recovery_epoch`**:
   `recovery_epoch` được đọc từ trường `execution_grant` trong `request`, mặc định là `'0'` nếu không có grant hợp lệ.
6. **Mô hình revision trong state machine**:
   Bảng `cp_stage_runs` không có cột `revision` riêng biệt, do đó việc gọi máy trạng thái thuần `transition_stage_run` sử dụng cặp revision cố định `0/0` để đảm bảo logic chuyển trạng thái và các cạnh cấm được áp dụng chính xác.
7. **Số lần thử (`attempt`) và quản lý giao dịch**:
   Số `attempt` được trích xuất từ phần revision của chuỗi `stage_run_id` (`:r<revision>`). Mỗi thao tác ghi nhận dữ liệu trong dispatcher được thực hiện trong một giao dịch độc lập thông qua context manager `with connection.transaction():` từ kết nối mới của `connection_factory`.

## 6. Đọc lại và xác nhận tính toàn vẹn ký tự

Đã đọc lại toàn bộ tệp báo cáo này bằng UTF-8:
- Toàn bộ dấu tiếng Việt được giữ nguyên vẹn, không có ký tự lỗi hoặc biến dạng bảng mã.
- Các số liệu kiểm thử và kết quả khớp chính xác với kết quả thực thi thực tế trong môi trường.
