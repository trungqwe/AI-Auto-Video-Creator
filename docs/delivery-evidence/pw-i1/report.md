# PW-I1: MaterializeArtifactSet, ReconcileStorage, RequestCleanupEvaluation

## Thay đổi

Gói công việc PW-I1 đã thực hiện các thay đổi và bổ sung trên đúng bốn tệp thuộc owned paths được giao:

1. `src/controlplane/infrastructure/db/storage_meta/__init__.py`:
   - Mở rộng phương thức `update_location` để tiếp nhận `observed_hash` (chuỗi sha256 hex chữ thường) và `observed_size_bytes` (số nguyên dương) đo thật từ tệp; kiểm tra hợp lệ định dạng digest và kích thước; ghi nhận trực tiếp vào cơ sở dữ liệu qua câu lệnh `UPDATE controlplane.cp_artifact_locations`. Hai tham số mới có giá trị mặc định là `None` giúp bảo toàn khả năng tương thích ngược cho các lời gọi cũ.
   - Thêm phương thức ngữ cảnh lớp `in_transaction`: mở connection mượn từ `transactions.borrow_connection()`, để pool quản lý commit/rollback khi kết thúc khối thực thi của handler. Repository giữ nguyên tính chất không tự kiểm soát giao dịch (không chứa các chuỗi cấm `.commit(`, `.rollback(`, `connect(`, `TransactionManager`, `ConnectionPool`).
   - Bổ sung 5 phương thức truy vấn chỉ đọc phục vụ các handler: `find_location`, `list_version_locations`, `list_backend_locations`, `list_versions`, và `current_recovery_epoch`.
2. `src/controlplane/application/storage_meta/handlers.py`:
   - Tạo mới module chứa ba handler nghiệp vụ của phân hệ I phục vụ luồng thực thi:
     - `materialize_artifact_set_handler`: tiếp nhận yêu cầu vật chất hóa các artifact nguồn (`artifact_source`) hoặc phiên bản đã đăng ký (`artifact_version`), đo kiểm hash sha256 và kích thước thực tế qua `_measure`, đặt bản sao cục bộ phẳng tại đường dẫn `<staging>/<artifact_version_id>`, chuyển dịch trạng thái vị trí tuần tự theo state machine (DECLARED -> MATERIALIZING -> AVAILABLE_UNVERIFIED -> VERIFYING -> VERIFIED) và ghi nhận `observed_hash`/`observed_size_bytes`. Nếu tệp nguồn thiếu hoặc lệch hash/kích thước thì trả kết quả `waiting` với mã lỗi `artifact_not_ready`. Manifest hoàn tất được đóng gói trong `metrics['materialization_manifest']`.
     - `reconcile_storage_handler`: truy vấn các vị trí backend cloud chưa xóa và các phiên bản tương ứng trong giao dịch cơ sở dữ liệu, sau đó thực hiện quan sát đối tượng cloud thông qua hàm `observe` được truyền vào từ bên ngoài giao dịch, lập `ReconcileSnapshot` và gọi `reconcile()`. Trả kết quả `succeeded` kèm danh sách cảnh báo `warnings` và chi tiết `findings` nếu có lệch.
     - `request_cleanup_evaluation_handler`: bọc quy trình đánh giá dọn dẹp `evaluate_cleanup()`, xác minh các điều kiện lưu trữ, recovery epoch và đặc biệt là sự tồn tại của bản sao cloud ở trạng thái VERIFIED trước khi cho phép dọn dẹp bản sao cục bộ của video bền. Handler chỉ đọc dữ liệu từ DB, tuyệt đối không tạo bản ghi cấp quyền dọn dẹp (`CleanupAuthorization`) hay tự ý sửa đổi trạng thái vị trí.
3. `tests/integration/prod_wiring/test_pw_i1_materialize.py`:
   - Xây dựng 9 test case tích hợp chạy trên PostgreSQL thật qua fixture `pw_database` và `TransactionManager`:
     - `test_update_location_writes_measured_observation_only_when_given`: kiểm tra `update_location` ghi nhận đúng `observed_hash`/`observed_size_bytes` và từ chối các giá trị sai quy cách.
     - `test_in_transaction_settles_through_the_pool_and_repository_has_no_commit`: xác minh cơ chế commit khi thành công và rollback khi gặp lỗi qua pool, đồng thời quét mã nguồn đảm bảo không có token commit/rollback trong adapter.
     - `test_release_for_render_rejects_a_location_without_observed_hash`: kiểm tra cổng nghiệm thu `release_for_render` từ chối vị trí VERIFIED nếu thiếu `observed_hash`.
     - `test_materialize_registers_versions_and_verifies_flat_local_copies`: kiểm tra quá trình materialize đăng ký phiên bản, sao chép tệp phẳng, kiểm tra với `StagingArtifactSource` và nghiệm thu render.
     - `test_materialize_replay_is_idempotent`: xác minh tính lũy quyền (idempotency) khi gọi lại cùng thao tác materialize.
     - `test_materialize_waits_with_artifact_not_ready_for_missing_source`: kiểm tra xử lý khi tệp nguồn bị thiếu hoặc ref không hợp lệ.
     - `test_materialize_rejects_a_file_changed_after_registration`: kiểm tra phát hiện tệp bị can thiệp thay đổi sau khi đăng ký và từ chối ở cổng render.
     - `test_reconcile_storage_reports_mismatched_and_missing_cloud_locations`: kiểm tra đối soát lưu trữ phát hiện chính xác `HASH_MISMATCH` và `CLOUD_OBJECT_MISSING`.
     - `test_cleanup_evaluation_never_grants_without_a_verified_cloud_copy`: kiểm tra đánh giá dọn dẹp từ chối (`forbidden`) khi thiếu bản cloud VERIFIED và không bao giờ tự phát hành ủy quyền.
4. `docs/delivery-evidence/pw-i1/report.md`:
   - Báo cáo chi tiết quá trình triển khai, kết quả nghiệm thu và bằng chứng kiểm thử của gói PW-I1.

## Giả định và quyết định (D8)

- Đầu vào của `MaterializeArtifactSet` hỗ trợ hai loại tham chiếu qua `input_refs`: `artifact_source` (với `ref_id` là đường dẫn tương đối dưới staging root, ví dụ `voice/line.wav`) và `artifact_version` (UUID của phiên bản đã đăng ký từ trước, chỉ kiểm tra lại trạng thái vị trí).
- Phiên bản artifact mới được gán chính sách lưu trữ `retention_ref='per_video'` và phân loại bảo mật `sensitivity_ref='internal'` theo mặc định.
- Tệp phụ đề `.ass` do phân hệ F ghi và đưa vào manifest riêng (`with_ass_entry`), do đó không thuộc phạm vi đăng ký của handler này.
- Vị trí ở trạng thái VERIFIED không bao giờ được ghi đè hay cập nhật lại; do đó nếu tệp trên đĩa bị sửa đổi sau khi đã VERIFIED, thao tác gọi lại sẽ phát hiện lệch hash và trả trạng thái `waiting` với lỗi `artifact_not_ready`.
- Manifest vật chất hóa được trả trong `metrics['materialization_manifest']` vì hạ tầng `service_handler` của composition root chỉ chuyển tiếp các trường `metrics`, `warnings` và `problem`.
- `ReconcileStorage` chỉ đối soát các vị trí thuộc backend `cloud` chưa ở trạng thái `DELETED`; hàm `observe(provider_object_ref)` là cổng quan sát do composition root cấp ngoài giao dịch DB; các danh mục nhật ký (journal), bằng chứng hoàn thành (completion) và danh sách đối tượng mồ côi tạm thời để trống do chưa có nguồn dữ liệu ở slice này.
- Đường commit của giao dịch được đặt tại `PostgresStorageMetaRepository.in_transaction` qua pool kết nối, vì kiểm thử `test_adapter_source_has_no_ddl_cloud_adapter_or_transaction_control` (trong `tests/integration/persistence/i/test_persist_i_postgres.py`) cấm hoàn toàn sự xuất hiện của chuỗi `.commit(` trong thư mục adapter.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_i1_materialize.py tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider` | 0 | `25 passed in 8.46s` |
| `git diff --check` | 0 | Không có output (sạch khoảng trắng thừa) |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/storage_meta/__init__.py').read_text(encoding='utf-8'); assert 'observed_hash' in t and 'observed_size_bytes' in t and t.count('UPDATE controlplane.cp_artifact_locations') >= 1, 'PW-I1'"` | 0 | Khẳng định thành công, không in lỗi |

## Phản ví dụ đã loại trừ

- `observed_hash` rỗng khiến cổng render fail: Đã kiểm chứng qua test `test_release_for_render_rejects_a_location_without_observed_hash`, đảm bảo `release_for_render` từ chối bất kỳ vị trí VERIFIED nào không có `observed_hash`.
- Repository tự ý commit: Đã kiểm chứng qua test `test_in_transaction_settles_through_the_pool_and_repository_has_no_commit`, khẳng định adapter không sở hữu phương thức commit/rollback nội bộ mà toàn bộ việc chốt giao dịch do pool xử lý khi khối `in_transaction` kết thúc.
- Ghi nhận vị trí nhưng không đo hash: Đã kiểm chứng qua test `test_update_location_writes_measured_observation_only_when_given`, khẳng định hash và kích thước phải được truyền vào đầy đủ và đo thực tế qua `_measure` trước khi chuyển sang VERIFIED.
- Cấp quyền dọn dẹp khi chưa có bản cloud VERIFIED: Đã kiểm chứng qua test `test_cleanup_evaluation_never_grants_without_a_verified_cloud_copy`, khẳng định yêu cầu dọn dẹp bản cục bộ bền luôn bị trả về `forbidden` với mã `DURABLE_COPY_NOT_VERIFIED` nếu chưa tồn tại bản cloud VERIFIED.

## Mã test phủ

`coveredIds: PW-I1-01, CT-STO-004, CT-STO-006, CT-STO-007`

Yêu cầu CT-STO-006 được bao phủ ở phía tiêu thụ (video đầu ra bền chưa có bản sao cloud VERIFIED thì không được phép dọn dẹp) vì thao tác ghi nhận `PersistVideoOutput` thuộc gói PW-I2 kế tiếp.

## Mục mở

- Nguồn quan sát cloud (`observe`) phục vụ `ReconcileStorage` sẽ do composition root cấp trong slice tích hợp sau.
- Handler `PersistVideoOutput` ghi nhận video hoàn chỉnh lên lưu trữ cloud sẽ được triển khai trong gói công việc PW-I2.
