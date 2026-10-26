# Báo cáo chuyển giao: grant_issuer thật, thu hồi grant sau kết quả, ExecutionGrantCurrency (PW-G3)

- Task: PW-G3
- Milestone: M7
- Trạng thái: IMPLEMENTED

## 1. Tóm tắt

Gói công việc PW-G3 hoàn thành việc triển khai cơ chế cấp quyền thực thi (execution grant) trên cơ sở dữ liệu PostgreSQL thực tế, thu hồi grant sau mỗi kết quả activity và cơ chế kiểm tra tính hiệu lực của grant trong môi trường sản xuất:
- `build_grant_issuer(connection_factory, workspace_id, ttl_by_queue, clock)`: Trả về hàm cấp phát grant trong đúng một giao dịch duy nhất gồm: `PostgresStageRuns.ensure`, `PostgresRecoveryEpoch.current`, và `GrantIssuer` với `PostgresGrantStore` trên cùng một kết nối cơ sở dữ liệu, tự động commit khi hoàn tất. Hỗ trợ cấu hình TTL mặc định theo từng hàng đợi tác vụ (`TaskQueue`) và cho phép ghi đè thông qua tham số hồ sơ cấu hình.
- `GrantRevokingDispatcher(inner, connection_factory, workspace_id)`: Bao bọc bộ điều phối activity (từ PW-G2). Sau mỗi kết quả activity (với mọi `disposition`: `succeeded`, `failed`, `waiting`, `outcome_unknown`, `stale`, và kể cả khi handler ném ngoại lệ), dispatcher thu hồi grant tương ứng trong một giao dịch riêng biệt, đảm bảo hai activity liên tiếp cùng `stage_run_id` có thể lần lượt được cấp grant mới mà không gặp lỗi `ActiveGrantExistsError` (CT-WF-004).
- `ExecutionGrantCurrency(connection_factory, workspace_id, clock)`: Cài đặt phương thức `is_grant_current(ExecutionGrant)` so khớp `operation_id` với `grant_id`, `execution_generation`, `recovery_epoch` hiện hành của phiên, kiểm tra `revoked_at` rỗng và thời gian hết hạn nghiêm ngặt `now < expires_at`; thay thế `StoreBackedClaimsCurrency` trong môi trường sản xuất.
- `_issue_grant_activity` và `_read_capability_view_activity` trong `workflow.py` được chuyển sang gọi bất đồng bộ qua `await asyncio.to_thread` nhằm giải phóng vòng lặp sự kiện (event loop) khi PostgreSQL phản hồi chậm. Module `grant_runtime.py` giữ tính đồng bộ thuần túy, không import `asyncio`, không sử dụng `InMemoryGrantStore` hay `from src.`.

## 2. Tệp đã đổi (Owned paths)

1. `src/controlplane/application/orchestration/grant_runtime.py`: Triển khai `build_grant_issuer`, `GrantRevokingDispatcher`, `ExecutionGrantCurrency` và bảng TTL mặc định `DEFAULT_TTL_BY_QUEUE`.
2. `src/controlplane/api/wiring/workflow.py`: Nâng cấp hai activity nội bộ sang `await asyncio.to_thread`, bổ sung xuất khẩu `ExecutionGrantCurrency` trong `__all__`, giữ nguyên `StoreBackedClaimsCurrency` để tương thích kiểm thử cũ.
3. `tests/integration/prod_wiring/test_pw_g3_grants.py`: Bộ kiểm thử tích hợp 39 test trên PostgreSQL thật cho issuer, TTL, thu hồi grant, tính hiệu lực currency và không chặn vòng lặp sự kiện.
4. `docs/delivery-evidence/pw-g3/report.md`: Báo cáo chuyển giao kỹ thuật đầy đủ dấu tiếng Việt.

## 3. Bằng chứng RED

- Lệnh chạy kiểm thử chứng kiến RED (bước 8):
  `python -m pytest tests/integration/prod_wiring/test_pw_g3_grants.py -q -p no:cacheprovider`
- Mã thoát: `1`
- Kết quả kiểm thử: `39 failed in 11.37s`
  - Toàn bộ 39 test đều collect thành công, không gặp lỗi cú pháp hay thiếu fixture.
  - Các test thất bại đúng như mong đợi do các hàm stub ném `NotImplementedError: PW-G3` hoặc vi phạm assert hành vi (chẳng hạn bảng TTL rỗng, activity chặn main thread, chưa có `asyncio.to_thread` trong wiring).
- Các dòng lỗi đại diện:
  - `E   AssertionError: assert {} == {'control-workflows': 300, ...}` (tại `test_default_ttl_table_matches_the_assumption`)
  - `E   NotImplementedError: PW-G3` (xuất phát từ `grant_runtime.py:10: NotImplementedError`)
  - `E   assert ([98408] and 98408 != 98408)` (tại `test_read_capability_view_activity_does_not_block_the_event_loop`)
  - `E   assert ('grantissuer' in '"""pw-g3: stub for the red run."""...')` (tại `test_grant_runtime_source_is_synchronous_and_uses_the_real_store`)
  - `E   assert None` (tại `test_workflow_activities_call_blocking_collaborators_through_to_thread`)

## 4. Lệnh đã chạy và kết quả xác minh

| Bước | Lệnh kiểm thử | Mã thoát | Kết quả xác minh |
| --- | --- | --- | --- |
| Bước 14 | `python -m pytest tests/integration/prod_wiring/test_pw_g3_grants.py -q -p no:cacheprovider` | 0 | `41 passed in 14.67s` (toàn bộ 41 test PW-G3 xanh) |
| Bước 15 | `python -m pytest tests/integration/prod_wiring/test_pw_g3_grants.py tests/integration/convergence/test_cp6_workflow_catalog.py -q -p no:cacheprovider` | 0 | `52 passed in 14.98s` (41 test PW-G3 + 11 test catalog CP6 đạt hoàn toàn) |
| Bước 16 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orchestration/grant_runtime.py').read_text(encoding='utf-8').lower(); assert 'grantissuer' in t and 'inmemory' not in t and 'from src.' not in t, 'PW-G3'"` | 0 | Đạt yêu cầu quét mã nguồn: có `GrantIssuer`, không có `inmemory` hay `from src.`. |
| Bước 18 | `git diff --check` | 0 | Sạch, không có khoảng trắng thừa hay lỗi định dạng dòng. |

## 5. Quyết định thiết kế

1. **Bảng TTL mặc định theo GIẢ ĐỊNH D8 và OI-PW-05**:
   Bảng TTL mặc định được cố định dưới dạng mapping bất biến `MappingProxyType`:
   - `control-workflows`: 300 giây (5 phút, tác vụ điều phối nội bộ ngắn).
   - `cloud-io`: 900 giây (15 phút, tác vụ tải/nhập liệu đám mây).
   - `cloud-ai`: 900 giây (15 phút, tác vụ sinh nội dung AI).
   - `desktop-cpu`: 900 giây (15 phút, xử lý âm thanh/văn bản CPU cục bộ).
   - `desktop-gpu`: 1800 giây (30 phút, suy luận mô hình nặng trên GPU).
   - `desktop-render`: 3600 giây (60 phút, kết xuất video FFmpeg).
   Hàm cấp grant tra cứu queue dựa theo binding của `allowed_operation`. Nếu activity không nằm trong danh mục binding thì sử dụng TTL của hàng đợi `control-workflows` (mức an toàn tối thiểu 300 giây).
2. **Xác thực tham số ghi đè `ttl_by_queue`**:
   Bảng ghi đè chỉ chấp nhận các khoá thuộc danh sách hàng đợi đã định nghĩa trong `TaskQueue` và giá trị phải là số nguyên dương (`isinstance(ttl, int)` và không phải `bool`, `ttl > 0`). Mọi giá trị không hợp lệ đều bị từ chối ngay khi gọi `build_grant_issuer` qua `ValueError`.
3. **Phạm vi an toàn khi thu hồi grant (`GrantRevokingDispatcher`)**:
   Hàm thu hồi nội bộ chỉ thực hiện lệnh SQL `revoke` khi `grant.stage_run_id` khớp chính xác với `request.stage_run_id`. Quy tắc này ngăn ngừa các request độc hại hoặc cấu trúc sai vô tình thu hồi grant của stage run khác. Ngoài ra, trong khối bắt lỗi ngoại lệ của handler, lỗi phát sinh khi thu hồi được chặn bằng `contextlib.suppress(Exception)` để đảm bảo ngoại lệ gốc của handler không bị che giấu.
4. **Quy tắc so khớp nghiêm ngặt trong `ExecutionGrantCurrency`**:
   Để một `ExecutionGrant` được xem là hợp lệ (`is_grant_current`), các điều kiện sau phải được thỏa mãn đồng thời:
   - Đối số truyền vào phải là thực thể `ExecutionGrant` và khớp đúng `workspace_id`.
   - `operation_id` khớp với `grant_id` trong kho lưu trữ.
   - `execution_generation` khớp với thế hệ cấp phát.
   - `recovery_epoch` khớp với recovery epoch hiện hành của phiên ứng dụng (so sánh chuỗi ký tự chuẩn hóa).
   - Kho lưu trữ có grant đang hoạt động (`active_grant`, tức `revoked_at IS NULL`).
   - Thời điểm kiểm tra phải nhỏ hơn thời điểm hết hạn (`now < expires_at`, cận loại trừ nghiêm ngặt).
   Nếu phiên không hoạt động hoặc ném `OrchestrationContractError` thì trả về `False`.
5. **Duy trì lớp `StoreBackedClaimsCurrency`**:
   Lớp `StoreBackedClaimsCurrency` tiếp tục được lưu giữ trong `workflow.py` kèm chú thích định hướng sản xuất nhằm đảm bảo tương thích ngược cho bộ kiểm thử `test_cp6_workflow_catalog.py` (vốn nằm ngoài phạm vi owned paths).
6. **Ranh giới tích hợp Composition Root**:
   Việc tích hợp `build_grant_issuer` và `ExecutionGrantCurrency` vào composition root (`launcher.py` hoặc `main.py`) thuộc trách nhiệm của các work package phân phối tiếp theo; gói PW-G3 chỉ bàn giao các thành phần sẵn sàng tại tầng application và wiring.

7. **Bao phủ INV-003 và INV-016**:
   - INV-003 (fencing generation đơn điệu): `test_inv003_older_generation_grant_is_not_current_once_a_newer_one_is_issued` chứng minh grant generation 1 không còn hiệu lực khi generation 2 được cấp và grant generation 2 bị từ chối nếu mang generation 1.
   - INV-016 (epoch cũ bị từ chối): `test_inv016_grant_from_an_old_recovery_epoch_is_rejected_and_reissued_under_the_new_one` chứng minh grant epoch '5' bị từ chối sau khi phiên mới epoch '6' bắt đầu, grant cấp lại mang epoch '6' hợp lệ và epoch cũ vẫn bị từ chối.

## 6. Khoảng hở và Open Items

Không có open item hay khoảng hở kỹ thuật nào cản trở nghiệm thu. Toàn bộ tiêu chí nghiệm thu của PW-G3 đều đã được chứng minh trên PostgreSQL thực tế.

## 7. Đọc lại và xác nhận tính toàn vẹn ký tự

Đã đọc lại toàn bộ tệp báo cáo này bằng UTF-8:
- Toàn bộ dấu tiếng Việt được giữ nguyên vẹn, không có ký tự lỗi hoặc biến dạng bảng mã.
- Các số liệu kiểm thử và kết quả khớp chính xác với kết quả thực thi thực tế trong môi trường.
