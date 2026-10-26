# Báo cáo chuyển giao: AllocateJob, FinalizeBatch và vòng lô (PW-G5)

- Task: PW-G5
- Trạng thái: IMPLEMENTED

## 1. Tóm tắt

Gói công việc PW-G5 hoàn thành việc tích hợp cấp phát công việc (`AllocateJob`), hoàn tất đợt sản xuất (`FinalizeBatch`) và vòng lặp thực thi lô tự động của `ProductionBatchFlow` trên hệ thống PostgreSQL và Temporal:
- Triển khai hai activity nội bộ thuộc Phân hệ G: `AllocateJob` (stage `allocate`, queue `control-workflows`) và `FinalizeBatch` (stage `run_videos`, queue `control-workflows`), cập nhật `ACTIVITY_BINDINGS` và `BATCH_STAGE_ACTIVITIES`.
- Mở rộng dataclass `AllocationCandidate` thêm trường tùy chọn `source_set_ref: str | None = None` ở vị trí cuối cùng, đảm bảo tương thích hoàn toàn với các lệnh gọi vị trí cũ hai tham số; đồng thời cập nhật `PostgresAllocationStore.create_job_and_reservation` lưu đồng thời vào bảng `cp_job_candidates` và thêm phương thức `find_candidate(job_id)`.
- Hiện thực hai dịch vụ đồng bộ thuần túy trong `batch_allocation.py`: `AllocateJobService` (kiểm tra đặt chỗ cũ theo `job_id` trước khi gọi selector để bảo đảm tính idempotent khi retry, cấp job mới qua `JobAllocationService.allocate`, lưu candidate và trả `no_more_jobs` khi hết ứng viên hoặc đạt target) và `FinalizeBatchService` (gọi `BatchLifecycle.finish` cập nhật trạng thái dừng của lô).
- Nâng cấp `BatchParams` và tái cấu trúc vòng lặp `ProductionBatchFlow.run`: không bắt buộc danh sách `payload['jobs']`, tự động yêu cầu cấp grant, gọi `AllocateJob`, tính toán `input_fingerprint` là mã băm SHA-256 từ `candidate_ref` và `source_set_ref`, chạy child workflow `VideoProductionWorkflow`, và luôn gọi `FinalizeBatch` ở cuối vòng đời lô (`COMPLETED_TARGET` hoặc `COMPLETED_EXHAUSTED`). Khi có danh sách jobs tĩnh truyền vào, luồng bỏ qua việc cấp phát động nhưng vẫn đảm bảo gọi `FinalizeBatch`.
- Mở rộng `FakeBatchGateway` trong bài kiểm thử hội tụ đã nghiệm thu `test_batch_isolation` để cung cấp các phương thức `issue_grant` và `execute` tất định, ghi nhận đầy đủ lời gọi FinalizeBatch mà không làm thay đổi các assertion hiện hữu.

## 2. Tệp đã đổi (Owned paths)

1. `src/controlplane/domain/orchestration/allocation_policy.py`: Bổ sung trường `source_set_ref: str | None = None` vào cuối dataclass `AllocationCandidate`.
2. `src/controlplane/infrastructure/db/orchestration/allocation.py`: Thêm phương thức `find_candidate`, kiểm tra hợp lệ `candidate_ref`/`source_set_ref` và ghi nhận vào bảng `controlplane.cp_job_candidates`.
3. `src/controlplane/application/orchestration/workflows/activities.py`: Đăng ký hai binding nội bộ `AllocateJob` và `FinalizeBatch` vào `ACTIVITY_BINDINGS` và `BATCH_STAGE_ACTIVITIES`.
4. `src/controlplane/application/orchestration/workflows/batch.py`: Mở rộng `BatchGateway`, cập nhật `BatchParams` (cho phép `jobs` rỗng, bổ sung `worker_lease_id`, `production_mode`, `workflow_run_id`), tái cấu trúc `ProductionBatchFlow.run` cùng các phương thức trợ giúp `_lease`, `_call`, `_allocate`, `_finalize`, và xuất đầy đủ biểu tượng trong `__all__`.
5. `src/controlplane/application/orchestration/workflows/definitions.py`: Cập nhật `ProductionBatchWorkflow.run` truyền thêm `workflow_run_id` từ Temporal workflow info sang `BatchParams`.
6. `src/controlplane/application/orchestration/batch_allocation.py`: Tạo mới triển khai đồng bộ cho `AllocateJobService`, `FinalizeBatchService`, `CandidateSelectorPort` và các helper.
7. `tests/integration/prod_wiring/test_pw_g5_allocation.py`: Tạo mới bộ kiểm thử tích hợp 15 test bao phủ toàn diện hoạt động cấp phát, ghi nhận cơ sở dữ liệu, vòng đời lô và luồng Temporal.
8. `tests/integration/convergence/test_cp6_video_production_flow.py`: Mở rộng `FakeBatchGateway` trong `test_batch_isolation` hỗ trợ `issue_grant` và `execute`, bổ sung hai assertion xác minh `FinalizeBatch`.
9. `docs/delivery-evidence/pw-g5/report.md`: Báo cáo chuyển giao kỹ thuật bằng tiếng Việt đầy đủ dấu UTF-8.

## 3. Bằng chứng RED

- Lệnh chạy kiểm thử chứng kiến RED (bước 9):
  `python -m pytest tests/integration/prod_wiring/test_pw_g5_allocation.py -q -p no:cacheprovider`
- Mã thoát: `1`
- Kết quả kiểm thử: `15 failed in 4.68s`
  - Thu thập test thành công 15/15 test, không có lỗi cú pháp hoặc lỗi import fixture cơ sở dữ liệu.
  - Cả 15 test đều thất bại chính xác theo đúng oracle mong đợi:
    - `KeyError: 'AllocateJob'` do chưa đăng ký binding hoạt động.
    - `AssertionError: Right contains one more item: 'source_set_ref'` do `AllocationCandidate` chưa có trường `source_set_ref`.
    - `TypeError: AllocationCandidate.__init__() takes 3 positional arguments but 4 were given` do khởi tạo ứng viên với 3 tham số vị trí.
    - `NotImplementedError: PW-G5` từ khung stub ban đầu của `AllocateJobService`.
    - `AssertionError: Regex pattern did not match. Expected regex: 'worker_lease_id', Actual message: 'missing batch parameter: jobs'` do `BatchParams` cũ bắt buộc trường `jobs`.
    - `AssertionError: joballocationservice not in text` do mã nguồn `batch_allocation.py` mới chỉ là stub.
- Dòng lỗi đại diện:
  - `KeyError: 'AllocateJob'` (tại `test_bindings_are_internal_g_bindings_on_the_control_queue`, `test_pw_g5_allocation.py:102`)
  - `TypeError: AllocationCandidate.__init__() takes 3 positional arguments but 4 were given` (tại `cands`, `test_pw_g5_allocation.py:68`)
  - `NotImplementedError: PW-G5` (tại `batch_allocation.py:15`)

## 4. Lệnh đã chạy và kết quả xác minh

| Bước | Lệnh kiểm thử | Mã thoát | Kết quả xác minh |
| --- | --- | --- | --- |
| Bước 9 | `python -m pytest tests/integration/prod_wiring/test_pw_g5_allocation.py -q -p no:cacheprovider` | 1 | `15 failed in 4.68s` (chứng kiến RED hợp lệ) |
| Bước 27 | `python -m pytest tests/integration/prod_wiring/test_pw_g5_allocation.py tests/integration/convergence/test_cp6_video_production_flow.py tests/integration/convergence/test_cp6_workflow_catalog.py -q -p no:cacheprovider` | 0 | `36 passed in 7.48s` (toàn bộ 15 test PW-G5 + 9 test CP6 flow + 12 test CP6 catalog xanh hoàn toàn) |
| Bước 28 | `python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 0 | `104 passed in 4.71s` (toàn bộ 104 test hồi quy cũ với AllocationCandidate 2 tham số vị trí đều đạt, không sửa test) |
| Bước 29 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/batch_allocation.py').read_text(encoding='utf-8').lower(); assert 'allocatejob' in t and 'fake' not in t and 'from src.' not in t, 'PW-G5'"` | 0 | Quét mã nguồn đạt: chứa `allocatejob`, không chứa `fake` và không chứa `from src.`. |
| Bước 31 | `git diff --check` | 0 | Sạch, không có khoảng trắng thừa hay lỗi xuống dòng. |

## 5. Quyết định thiết kế

1. **Định danh công việc tất định**:
   - `job_id` được sinh theo mẫu tất định `<batch_id>:job:<thứ tự>` (ví dụ `batch-1:job:1`, `batch-1:job:2`).
   - Handler `AllocateJobService` chủ động kiểm tra đặt chỗ cũ trong cơ sở dữ liệu theo `job_id` trước khi gọi bộ chọn `selector`. Khi Temporal thử lại (retry) một activity cấp job đã thực hiện trước đó, service trả lại đúng đặt chỗ cũ mà không gọi `selector.next_candidate` để chọn ứng viên mới, loại trừ triệt để nguy cơ sinh công việc đôi.
2. **Cơ chế cấp quyền và hoàn tất đợt sản xuất (FinalizeBatch)**:
   - `FinalizeBatch` vẫn cần cấp grant riêng của chính nó với stage run id là `<batch_id>:run_videos:r1` vì kết quả activity theo hợp đồng bắt buộc phải gắn kèm `grant_id`.
   - Khi payload của lô có chứa danh sách tĩnh các `jobs`, workflow không gọi `AllocateJob` và không cấp grant cấp job, nhưng vẫn đảm bảo cấp grant và gọi `FinalizeBatch` để cập nhật trạng thái kết thúc lô.
3. **Quản lý worker lease**:
   - Lease của batch được trích xuất từ payload `worker_lease_id`. Trong trường hợp khuyết thiếu giá trị này, workflow sử dụng `batch_id` làm giá trị thay thế (chỉ được phép khi lô đã có sẵn danh sách `jobs`).
4. **Chế độ sản xuất mặc định**:
   - Trường `production_mode` nhận giá trị mặc định là `single_article` (tuân thủ mục mở D8 theo phương án đơn giản hóa đã được duyệt).
5. **Khả năng phục hồi và xử lý lỗi không ném ngoại lệ**:
   - Các lỗi phát sinh trong quá trình cấp job hoặc hoàn tất lô không bị ném ra ngoài workflow nhằm tránh việc Temporal rơi vào vòng lặp thử lại vô tận. Kết quả trả về của workflow được bổ sung các trường `allocated`, `finalized` và thông tin chi tiết `problem`.
   - Nếu quá trình cấp job gặp lỗi hoặc hết ứng viên, vòng lặp dừng an toàn với trạng thái `EXHAUSTED`.
6. **Dấu vân tay ứng viên**:
   - `candidate_fingerprint` được tính toán bằng mã băm SHA-256 dạng hex từ chuỗi JSON chuẩn hóa `[candidate_ref, source_set_ref]` (với `ensure_ascii=False` và dấu phân cách gọn).

## 6. Khoảng hở và Open Items

1. **Kết nối Composition Root**: Việc nối trực tiếp các handler của `AllocateJobService` và `FinalizeBatchService` vào composition root sản xuất sẽ được thực hiện tại gói công việc PW-W1.
2. **Hiện thực Candidate Selector thực tế**: Hiện thực hoàn chỉnh của `CandidateSelectorPort` truy vấn từ nguồn catalog thuộc phạm vi triển khai của gói PW-B1.
3. **Giải phóng đặt chỗ khi child workflow gặp lỗi**: Việc giải phóng đặt chỗ (`cp_batch_capacity_reservations`) của các child workflow bị lỗi phụ thuộc vào cơ chế cleanup của các gói phân hệ khác. Do đó, nếu một child bị lỗi mà đặt chỗ chưa được giải phóng, đợt sản xuất có thể dừng lại sớm với trạng thái `EXHAUSTED` do chạm trần target quy định.

## 7. Dòng đã đổi trong test đã nghiệm thu

Trong tệp `tests/integration/convergence/test_cp6_video_production_flow.py` tại kiểm thử `test_batch_isolation`:
- Khối lớp `FakeBatchGateway` được mở rộng thêm hai thuộc tính danh sách `self.grants = []` và `self.executed = []`.
- Bổ sung hai phương thức bất đồng bộ `issue_grant` và `execute` tất định ngay sau phương thức `run_child`.
- Thêm hai dòng assertion ngay sau dòng `assert res['failed'] == 1`:
  `python
  assert gateway.grants == [('batch-1:run_videos:r1', 'FinalizeBatch')]
  assert [name for name, _ in gateway.executed] == ['FinalizeBatch']
  `
- Toàn bộ các assertion hiện có (`BATCH_TARGET_REACHED`, `completed == 1`, `failed == 1`, `BATCH_EXHAUSTED`, lời gọi `DebugStageWorkflow`) và docstring đầu tệp được giữ nguyên vẹn 100%.

## 8. Đọc lại và xác nhận tính toàn vẹn ký tự

Đã đọc lại toàn bộ tệp báo cáo này bằng UTF-8:
- Toàn bộ dấu tiếng Việt được giữ nguyên vẹn 100%, không bị mất dấu, không có ký tự ? thay thế và không bị lỗi chuyển đổi bảng mã.
- Các số liệu kiểm thử, mã thoát và kết quả đo đạc hoàn toàn khớp với thực tế thực thi các lệnh kiểm tra.
