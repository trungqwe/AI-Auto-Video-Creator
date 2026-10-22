# Báo cáo CP-5-COMPLETION

## 1. Phạm vi

Các tệp đã tạo trong gói nhiệm vụ CP-5-COMPLETION, tuân thủ đúng danh sách owned paths được giao:
- `src/controlplane/infrastructure/db/orchestration/postgres_completion.py`: Cài đặt `PostgresCompletionUnitOfWork` (thực thi `CompletionUnitOfWork` và `CompletionStorePort` của `commit_completion.py` trên một kết nối mượn duy nhất từ `TransactionManager`), `PostgresMediaUsagePort` (gọi `MediaUsageRecorder.record_production_usage(uow, completion_id, request)` với `repository_factory` gắn cùng kết nối UoW, không mở kết nối thứ hai) và `CompletionStoreError`. Tệp không chứa bất kỳ lệnh xóa nào (`DELETE`, `unlink`, `rmtree`, `os.remove`, `shutil`), không chứa DDL và giữ khóa `FOR UPDATE` trên dòng job đến hết giao dịch.
- `src/controlplane/api/wiring/completion.py`: Mô-đun mỏng nối completion vào composition root, cung cấp lớp `CompletionService` và hàm factory `build_completion_service(transactions, workspace_id)`. Mỗi lần gọi `complete` khởi tạo mới toàn bộ đối tượng, không lưu trạng thái dùng chung giữa các lần gọi (an toàn khi chạy đa luồng) và không mở kết nối thứ hai.
- `tests/integration/convergence/test_cp5_completion_uow.py`: Bộ kiểm thử tích hợp toàn diện 36 test cases chạy trên PostgreSQL 18.6 thật (khởi tạo database riêng biệt theo UUID, chạy migration tự động, dọn dẹp sạch sẽ sau kiểm thử). Bao phủ toàn bộ 19 điểm tiêm lỗi trước/sau từng bước ghi để chứng minh tính nguyên tử và rollback hoàn toàn; kiểm thử tính idempotent gọi lặp 5 lần trả đúng 1 bản ghi duy nhất; kiểm thử phát hiện xung đột khi thay đổi input; kiểm thử từ chối khi thiếu `cloud_location_verification_ref`; kiểm thử registry stale; kiểm thử tranh chấp đồng thời giữa 2 worker cùng job và 2 job cùng revision registry; kiểm thử khóa dòng job bằng `FOR UPDATE NOWAIT`; kiểm thử so sánh `recovery_epoch` dạng chuỗi và 3 bài kiểm thử tĩnh về vị trí adapter, an toàn lệnh xóa và phân phối kết nối.
- `docs/delivery-evidence/cp-5-completion/report.md`: Báo cáo chuyển giao và bằng chứng nghiệm thu kỹ thuật này.

Khẳng định tuyệt đối:
- Không sửa đổi hoặc tạo bất kỳ tệp nào ngoài 4 owned paths được giao.
- Không thêm bất kỳ tệp `__init__.py` mới nào (thư mục `infrastructure/db/orchestration` và `api/wiring` đã có `__init__.py` từ trước).
- Không tạo gói mới `src/controlplane/infrastructure/db/completion`. Adapter đặt đúng vị trí gói `controlplane.infrastructure.db.orchestration` đã khai báo trong `pyproject.toml`.

## 2. RED

Thực hiện kiểm thử test-first tại Bước 11 trước khi viết phần cài đặt thực tế của adapter:
- Lệnh: `python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider`
- Oracle RED hợp lệ: Toàn bộ các kiểm thử cơ sở dữ liệu thất bại do ngoại lệ `NotImplementedError: CP-5-COMPLETION` từ phương thức `begin()` của `PostgresCompletionUnitOfWork`. Không có lỗi thu thập (`collection error`), không có `ImportError`, không bị `BLOCKED_EXTERNAL` (kết nối PostgreSQL 18.6 hoạt động bình thường).
- Nguyên văn dòng tóm tắt kết quả:
```text
35 failed, 1 passed, 4 warnings in 2.47s
```
- Nguyên văn 3 dòng FAILED đầu tiên:
```text
FAILED tests/integration/convergence/test_cp5_completion_uow.py::test_commit_is_one_transaction_on_one_connection
FAILED tests/integration/convergence/test_cp5_completion_uow.py::test_failure_at_any_point_rolls_back_everything[before:insert_ledger]
FAILED tests/integration/convergence/test_cp5_completion_uow.py::test_failure_at_any_point_rolls_back_everything[after:insert_ledger]
```
*(1 test đã PASS tại pha RED là `test_adapter_placement_and_packaging` do kiểm tra cấu hình đóng gói tĩnh đã thỏa mãn).*

## 3. GREEN

### 3.1. Kết quả kiểm thử bộ hội tụ CP-5-COMPLETION (Bước 16)
- Lệnh: `python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider`
- Exit code: 0
- Dòng tóm tắt:
```text
36 passed in 3.54s
```

### 3.2. Kết quả kiểm thử hồi quy bắt buộc (Bước 17)
- Lệnh: `python -m pytest tests/integration/orchestration tests/integration/storage tests/unit/catalog tests/unit/storage tests/unit/render -q -p no:cacheprovider`
- Exit code: 0
- Dòng tóm tắt:
```text
2306 passed, 7 skipped, 1184 subtests passed in 5.65s
```
Khẳng định: Không có bất kỳ bài kiểm thử nào của các phân hệ orchestration, storage, catalog, render bị ảnh hưởng hay hồi quy.

### 3.3. Kết quả kiểm tra probe đóng gói bắt buộc (Bước 18)
- Lệnh: `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['setuptools']; k = 'controlplane.infrastructure.db.orchestration'; assert k in s['packages'] and k in s['package-dir'], k; assert pathlib.Path('src/controlplane/infrastructure/db/orchestration/postgres_completion.py').is_file(), 'adapter path'; assert not pathlib.Path('src/controlplane/infrastructure/db/completion').exists(), 'no new package db/completion'"`
- Exit code: 0 (Đạt hoàn toàn, không có assertion error nào).

### 3.4. Kiểm tra định dạng git diff (Bước 23)
- Lệnh: `git diff --check`
- Exit code: 0 (Sạch sẽ, không có lỗi định dạng hay khoảng trắng thừa).

## 4. Thứ tự giao dịch và bảng 19 điểm tiêm lỗi

### 4.1. Thứ tự giao dịch trong một transaction duy nhất
Mọi hoạt động được thực thi trên cùng một kết nối mượn từ `TransactionManager.borrow_connection()`, tuyệt đối không mở kết nối thứ hai:
1. Cổng G-09 thẩm tra dữ liệu đầu vào: kiểm tra trạng thái job (`READY_FOR_COMPLETION`), fencing claims và epoch, tính hợp lệ của variant reservation và đối chiếu hash artifact đầu ra.
2. Ghi bản ghi ledger duy nhất vào `controlplane.cp_completion_ledger`. Ràng buộc unique `(workspace_id, job_id)` của cơ sở dữ liệu đóng vai trò chốt chặn cuối cùng cho tính idempotent.
3. Chuyển trạng thái job sang `COMPLETED` và tăng revision thông qua câu lệnh `UPDATE controlplane.cp_video_jobs SET status = 'COMPLETED', revision = %s WHERE workspace_id = %s AND job_id = %s AND revision = %s`.
4. Chuyển capacity reservation sang `CONVERTED` (`UPDATE controlplane.cp_batch_capacity_reservations SET state = 'CONVERTED' WHERE ... AND state = 'ACTIVE'`).
5. Chuyển variant reservation sang `CONVERTED` (`UPDATE controlplane.cp_variant_reservations SET state = 'CONVERTED' WHERE ... AND state = 'ACTIVE'`).
6. CAS cập nhật revision của variant registry (`UPDATE controlplane.cp_variant_registry SET current_registry_revision = %s WHERE workspace_id = %s AND current_registry_revision = %s`).
7. Tăng bộ đếm batch hoàn tất: khóa dòng batch bằng `FOR UPDATE`, đếm số lượng ledger của batch trong bảng `cp_completion_ledger`, kiểm tra không vượt quá `target_count`.
8. Ghi nhận sử dụng media (`cp_media_usage`) qua `MediaUsageRecorder.record_production_usage` mượn trực tiếp kết nối giao dịch của UoW.
9. Ghi sự kiện outbox `VideoCompleted` vào bảng `controlplane.cp_outbox_events` với `PostgresOutboxRepository` trên cùng kết nối giao dịch.
10. Ghi bản ghi dọn dẹp đủ điều kiện vào `controlplane.cp_cleanup_eligibility` với trạng thái `ELIGIBLE` (tuyệt đối không phát sinh lệnh xóa).
11. Commit giao dịch (hoặc rollback toàn bộ nếu có bất kỳ lỗi nào phát sinh).

### 4.2. Bảng 19 điểm tiêm lỗi (trước và sau từng bước)
Kiểm thử `test_failure_at_any_point_rolls_back_everything` xác nhận rằng khi tiêm lỗi tại bất kỳ điểm nào trong 19 điểm, trạng thái cơ sở dữ liệu trước và sau hoàn toàn bằng nhau, không phát sự kiện `VideoCompleted` ra outbox và lần thử lại sau rollback thành công trọn vẹn:

| STT | Điểm tiêm lỗi | Trạng thái trước = sau | Sự kiện VideoCompleted khi rollback | Kết quả thử lại sau rollback |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `before:insert_ledger` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 2 | `after:insert_ledger` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 3 | `before:set_job_state` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 4 | `after:set_job_state` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 5 | `before:convert_capacity_reservation` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 6 | `after:convert_capacity_reservation` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 7 | `before:convert_variant_reservation` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 8 | `after:convert_variant_reservation` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 9 | `before:set_registry_revision` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 10 | `after:set_registry_revision` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 11 | `before:increment_batch_completed` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 12 | `after:increment_batch_completed` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 13 | `before:record_usage` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 14 | `after:record_usage` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 15 | `before:insert_outbox` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 16 | `after:insert_outbox` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 17 | `before:insert_cleanup_eligibility` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 18 | `after:insert_cleanup_eligibility` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |
| 19 | `before:commit` | Khớp 100% | Rỗng (0 sự kiện) | Thành công (COMPLETED) |

## 5. Bảng trạng thái BL

| Mã | Trạng thái | Chi tiết |
| :--- | :--- | :--- |
| BL-CV-08 | PENDING | Tệp `src/controlplane/api/wiring/completion.py` đã tạo theo yêu cầu nhiệm vụ, nhưng `src/main.py` chưa gọi hàm `build_completion_service`, chờ tích hợp composition root toàn cục |
| BL-CV-11 | PENDING | Adapter `postgres_completion.py` được đặt đúng vị trí gói `controlplane.infrastructure.db.orchestration` đã khai báo trong `pyproject.toml`, tuân thủ cấu trúc đóng gói |
| BL-CV-06 | PENDING | Thư mục `src/controlplane/api/wiring` chưa được mở chính thức trong `PATH-COMPOSITION-ROOT`; việc mở rộng composition root sẽ được điều phối ở pha sau |

## 6. GIẢ ĐỊNH

Các giả định kỹ thuật được áp dụng trong gói nhiệm vụ này:
- GIẢ ĐỊNH 1: Hash đầu ra của `VariantReservation` được đối chiếu từ bảng `controlplane.cp_artifact_versions` dựa vào `output_artifact_version_id` vì bảng `controlplane.cp_variant_reservations` hiện chưa có cột lưu trữ hash đầu ra.
- GIẢ ĐỊNH 2: Trường `audit_ref` trong bảng `cp_completion_ledger` được gán bằng giá trị của `completion_id` do contract ledger từ module G hiện chưa cấp riêng một định danh kiểm toán khác biệt.
- GIẢ ĐỊNH 3: Bộ đếm hoàn tất của production batch được tính bằng số lượng bản ghi ledger trong `controlplane.cp_completion_ledger` thuộc về batch đó (hoàn toàn tương thích với cơ chế kiểm tra `consistency_audit`), không tạo cột mới và không tự ý chuyển trạng thái của batch.
- GIẢ ĐỊNH 4: Cột `recovery_epoch` trong bảng `controlplane.cp_outbox_events` có kiểu dữ liệu là `BIGINT`; do đó, nếu `recovery_epoch` từ contract là chuỗi ký tự không thể biểu diễn dưới dạng số nguyên thập phân hợp lệ (ví dụ chuỗi chữ), giá trị này sẽ được lưu là `NULL` trong bảng outbox event để không gây lỗi chuyển kiểu cơ sở dữ liệu.
- GIẢ ĐỊNH 5: Trường `cloud_location_verification_ref` được lưu vào `cp_completion_ledger` trực tiếp từ request payload vì dictionary ledger sinh ra từ module G không chứa trường dữ liệu này.

## 7. DEPENDENCY_GAP

Báo cáo kết quả kiểm tra thực tế đối với hai bài kiểm thử nằm ngoài owned paths (được ghi nhận theo Bước 19 và Bước 20):

1. Bước 19: Quan sát kiểm thử `tests/integration/convergence/test_cp4_wiring.py`
   - Lệnh: `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider`
   - Dòng tóm tắt kết quả:
```text
1 failed, 129 passed, 28 skipped, 1 warning in 2.19s
```
   - Tên bài test đỏ: `tests/integration/convergence/test_cp4_wiring.py::test_wiring_package_stays_empty`
   - Phân tích: Tệp test này thuộc sở hữu của gói `CP-4-WIRING`, chứa assertion khẳng định thư mục `src/controlplane/api/wiring` chỉ có duy nhất tệp `__init__.py`. Khi gói `CP-5-COMPLETION` tạo tệp `completion.py` trong thư mục này theo đúng phân quyền được giao, test trên bị đỏ. Worker tuân thủ kỷ luật không tự ý chỉnh sửa tệp test ngoài owned paths; Control sẽ cập nhật bài test này khi tích hợp.

2. Bước 20: Quan sát kiểm thử `tests/integration/persistence/g/test_persist_g_postgres.py`
   - Lệnh: `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider`
   - Dòng tóm tắt kết quả:
```text
1 failed, 11 passed in 4.77s
```
   - Tên bài test đỏ: `tests/integration/persistence/g/test_persist_g_postgres.py::test_adapter_source_has_no_ddl_completion_store_or_transaction_control`
   - Phân tích: Tệp test này thuộc sở hữu của gói `PERSIST-G`, cấm sự xuất hiện của chuỗi token `.commit(` trong các tệp mã nguồn thuộc thư mục `orchestration`. Khi adapter `postgres_completion.py` cài đặt Unit of Work cần gọi `connection.commit()`, test trên bị đỏ. Worker không tự ý sửa đổi tệp test ngoài owned paths; Control sẽ cập nhật phạm vi kiểm tra cho gói PERSIST-G.

```blocked-manifest
{"step": 19, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-4-WIRING"], "paths": ["src/controlplane/api/wiring/completion.py", "tests/integration/convergence/test_cp4_wiring.py"], "ids": ["tests/integration/convergence/test_cp4_wiring.py::test_wiring_package_stays_empty"]}
```
```blocked-manifest
{"step": 20, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["PERSIST-G"], "paths": ["src/controlplane/infrastructure/db/orchestration/postgres_completion.py", "tests/integration/persistence/g/test_persist_g_postgres.py"], "ids": ["tests/integration/persistence/g/test_persist_g_postgres.py::test_adapter_source_has_no_ddl_completion_store_or_transaction_control"]}
```

## 8. Giới hạn

- Toàn bộ kết quả kiểm thử trong báo cáo này chỉ chứng minh tính đúng đắn về logic nghiệp vụ, tính nguyên tử, tính idempotent và khả năng xử lý đồng thời trên cơ sở dữ liệu PostgreSQL 18.6 cục bộ.
- Báo cáo này KHÔNG đóng cổng G04 và không thay thế bộ kiểm thử fault suite thật (`CP7-G-03`).
- Báo cáo KHÔNG tuyên bố cổng `GATE-CP-5-COMPLETION` đã thả; cổng này do Control thẩm quyền quyết định mở sau khi có kết quả AUDITOR PASS từ Astra-Lead.
- Không có bất kỳ tuyên bố nào cho rằng G04 hoặc fault suite thật đã PASS. Toàn bộ dữ liệu trong báo cáo được trích xuất chính xác từ các câu lệnh đã thực thi.