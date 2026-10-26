# Báo cáo PW-G7

## 1. Phạm vi
Thực hiện trong bốn tệp thuộc owned paths của nhiệm vụ PW-G7:
- `src/controlplane/application/orchestration/completion_assembler.py`: tạo mới lớp `CompletionAssembler`, `CompletionAssemblyError` và các hằng input/ref liên quan.
- `src/controlplane/application/orchestration/variant_handlers.py`: tạo mới handler `reserve_variant_handler` và `commit_video_completion_handler`.
- `tests/integration/prod_wiring/test_pw_g7_completion.py`: tạo mới bộ kiểm thử tích hợp trên PostgreSQL 18.6 thật gồm 20 ca kiểm thử bao phủ toàn bộ luồng.
- `docs/delivery-evidence/pw-g7/report.md`: tạo mới báo cáo nghiệm thu này.

Không sửa bất kỳ tệp nào ngoài bốn owned paths trên. Không sửa adapter hạ tầng (`postgres_completion.py`, `grants.py`, `variants.py`), không chạm migration hay composition root.

## 2. Thiết kế
- `CompletionAssembler.assemble(connection, request, claims)`:
  - Dựng `commit_request` và `CompletionContext` từ các hàng thật trên kết nối CSDL PostgreSQL được cung cấp.
  - Fencing được thẩm định qua `PostgresGrantStore` và `PostgresRecoveryEpoch` trên kết nối thật; kiểm tra chặt chẽ `execution_generation` mới nhất, epoch hồi phục hiện hành và active grant còn hiệu lực.
  - Về artifact và location: chỉ chấp nhận artifact kind `rendered_video` định dạng `video/mp4`, location phải ở trạng thái `VERIFIED` kèm `verification_evidence_ref` hợp lệ và khớp mã băm quan sát `observed_hash`.
  - Về reservation: yêu cầu reservation ở trạng thái `ACTIVE`, hoặc `CONVERTED` nếu ledger hoàn tất đã tồn tại từ trước (cho phép chạy lại lũy đẳng không ghi đôi).
  - Về validation: tìm bản ghi validation pha `output` khớp chính xác mã băm đầu ra `output_hash` của video, xác định trạng thái xung đột biến thể (`variant_conflict_confirmed`).
  - Về báo cáo kiểm định chất lượng: kiểm tra báo cáo QC thuộc đúng đợt render (`render_attempt_ref`) và đạt yêu cầu (`passed = true`).
- `reserve_variant_handler`:
  - Chỉ cho phép chạy ở giai đoạn `plan`; nếu job đã có các stage chạy sau (`render`, `qc`, `sync`, `complete`) thì từ chối ngay với mã lỗi `RESERVE_AFTER_RENDER`.
  - Đọc validation pha `plan` và snapshot duy nhất, gọi `VariantReservationFlow(PostgresVariantRegistry(connection)).reserve(...)`.
  - Khi trùng khóa thao tác (`operation_key`) và dữ liệu đầu vào, trả lại receipt cũ thành công; khi xung đột fingerprint hoặc job đã có reservation khác trả về lỗi `VARIANT_CONFLICT` với disposition `failed` (`retryable = False`); khi registry biến thể bị thay đổi giữa chừng trả về `VARIANT_VALIDATION_STALE` với disposition `waiting` (`retryable = True`) và giao dịch tự rollback nên không ghi gì vào CSDL.
- `commit_video_completion_handler`:
  - Yêu cầu bắt buộc có `GrantClaims`; gọi `CompletionAssembler.assemble` để thu thập dữ liệu và context.
  - Thực thi hoàn tất qua `CommitVideoCompletion` kết hợp `PostgresCompletionUnitOfWork` và `PostgresMediaUsagePort`.
  - Khi thành công: ghi một dòng vào `cp_completion_ledger`, chuyển trạng thái job sang `COMPLETED`, chuyển cả reservation biến thể và reservation sức chứa đợt sang `CONVERTED` trong cùng một giao dịch.
  - Khi gặp lỗi fencing stale hoặc `GateAction.KEEP_WAITING`: trả disposition `stale` hoặc `waiting`, không ghi gì vào ledger.
  - Khi gặp `VARIANT_CONFLICT` (biến thể trùng lặp được xác nhận sau khi render): chuyển trạng thái job sang `FAILED_FINAL`, đồng thời giải phóng (`RELEASED`) cả reservation biến thể và reservation sức chứa.
  - Khi chạy lại cùng request đã hoàn tất: trả về `ALREADY_COMPLETED` với cờ `replayed = True` mà không ghi trùng thêm dòng ledger.

## 3. Hợp đồng input_refs
Các `ref_type` đầu vào mà PW-VERT và các phân hệ D, F, I cung cấp:
- `production_snapshot`: tham chiếs snapshot đợt sản xuất.
- `script_version`: tham chiếs phiên bản kịch bản video.
- `production_plan`: tham chiếs kế hoạch sản xuất.
- `output_metadata`: tham chiếs siêu dữ liệu xuất bản (đọc `max(revision)`).
- `render_attempt`: mã định danh lần xuất video (`attempt_id`).
- `quality_report`: mã định danh báo cáo QC video.
- `variant_validation`: khóa bản ghi kiểm định biến thể (pha `plan` và pha `output`).
- `output_artifact_version`: UUID của phiên bản artifact video mp4 đã render.
- `cloud_location`: UUID của vị trí lưu trữ đám mây đã được xác minh (`VERIFIED`).

Đầu ra của các handler:
- `variant_reservation`: trả về `reservation_id` và `revision_id` sau khi đặt chỗ biến thể thành công.
- `video_completion`: trả về `completion_id` của bản ghi ledger hoàn tất video.

## 4. GIẢ ĐỊNH
- Fingerprint đặt chỗ biến thể lấy từ trường `input_hashes.candidate` của bản ghi kiểm định pha plan (`cp_variant_validations`).
- Manifest sử dụng phương tiện (`media_usage_manifest`) được suy diễn từ bản ghi `cp_creative_selections` mới nhất của job với các vai trò: `scene_media` (kèm `rendition_ref`, `artifact_version_ref`), `visual_hook`, `audio_hook`, `thumbnail`.
- cost_usage_summary là dictionary rỗng theo quy định slice v1.
- `cleanup_policy_ref` và `audit_actor` sử dụng giá trị mặc định được truyền vào qua constructor (`cleanup-policy:default`, `system:orchestration`).
- Các câu lệnh SQL truy vấn trực tiếp bảng của phân hệ D, F, I nằm trong tệp application do owned paths không bao gồm các adapter hạ tầng riêng lẻ.

## 5. Lệnh đã chạy
| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_g7_completion.py -q -p no:cacheprovider` (bước 13) | 1 | 20 failed in 10.54s (chứng kiến RED oracle nghiệp vụ) |
| `python -m pytest tests/integration/prod_wiring/test_pw_g7_completion.py -q -p no:cacheprovider` (bước 24) | 0 | 20 passed in 10.26s (toàn bộ 20 ca kiểm thử GREEN) |
| `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/controlplane/application/orchestration/completion_assembler.py', 'src/controlplane/application/orchestration/variant_handlers.py']); assert 'inmemory' not in t and 'fake' not in t and 'from src.' not in t, 'PW-G7'"` (bước 25) | 0 | PASS: không chứa inmemory, fake, from src. |
| `git diff --check` (bước 26) | 0 | PASS: không có lỗi khoảng trắng thừa |

## 6. Oracle
- Bước 13 (Chứng kiến RED): Chạy trên khung rỗng ban đầu, toàn bộ 20 ca kiểm thử đều thất bại do assertion nghiệp vụ chính xác (không lỗi import hay môi trường):
  - `test_reserve_creates_one_active_reservation_and_bumps_the_registry`: fail do handler trả disposition `failed` (`NOT_IMPLEMENTED`).
  - `test_reserve_retry_with_the_same_key_returns_the_old_receipt`: fail do chưa ghi nhận reservation nào (assert (0, 0, None) == (1, 1, 2)).
  - `test_reserve_with_different_input_is_a_variant_conflict`: fail do code là `NOT_IMPLEMENTED` thay vì `VARIANT_CONFLICT`.
  - `test_reserve_for_another_job_with_the_same_fingerprint_is_a_variant_conflict`: fail do code là `NOT_IMPLEMENTED` thay vì `VARIANT_CONFLICT`.
  - `test_reserve_with_a_changed_registry_revision_waits_and_writes_nothing`: fail do disposition `failed` thay vì `waiting`.
  - `test_reserve_after_render_is_refused_and_writes_nothing`: fail do code là `NOT_IMPLEMENTED` thay vì `RESERVE_AFTER_RENDER`.
  - `test_reserve_refuses_an_invalid_plan_validation`: fail do code là `NOT_IMPLEMENTED` thay vì `VARIANT_VALIDATION_INVALID`.
  - `test_assembler_builds_the_request_and_context_from_real_rows`: fail ở `ready_world` do reserve chưa hoạt động.
  - `test_commit_writes_one_ledger_and_converts_the_job_and_both_reservations`: fail ở `ready_world`.
  - `test_rerunning_the_same_request_does_not_write_twice`: fail ở `ready_world`.
  - `test_a_grant_from_an_older_recovery_epoch_is_rejected_and_nothing_is_written`: fail ở `ready_world`.
  - `test_a_superseded_execution_generation_is_rejected_then_the_new_grant_completes`: fail ở `ready_world`.
  - `test_a_location_that_is_not_verified_waits_and_writes_no_ledger`: fail ở `ready_world`.
  - `test_registry_changed_before_commit_waits_and_writes_nothing`: fail ở `ready_world`.
  - `test_confirmed_variant_conflict_fails_the_job_and_releases_both_reservations`: fail ở `ready_world`.
  - `test_output_validation_must_match_the_exact_output_hash`: fail ở `ready_world`.
  - `test_a_failed_quality_report_is_refused`: fail ở `ready_world`.
  - `test_a_job_without_an_active_reservation_is_refused`: fail do code là `NOT_IMPLEMENTED` thay vì `RESERVATION_MISSING`.
  - `test_both_handlers_run_through_service_handler_and_the_activity_dispatcher`: fail do reserve handler trả `failed` (`NOT_IMPLEMENTED`).
  - `test_sources_use_the_postgres_stores_and_contain_no_forbidden_words`: fail do chưa import `PostgresGrantStore` trong khung rỗng.
- Bước 24 (Chứng kiến GREEN): Sau khi hoàn thiện triển khai cả hai tệp nguồn theo đặc tả, toàn bộ 20/20 test đều chuyển sang trạng thái GREEN (20 passed in 10.26s).

## 7. Giới hạn
Kết quả kiểm thử được chứng minh trên cơ sở dữ liệu PostgreSQL 18.6 cục bộ (loopback); các handler và assembler chưa được nối vào composition root (thuộc phạm vi của PW-VERT và PW-W); không mở hay đóng cổng sản xuất (`PRODUCTION_ACTIVATION_BLOCKED`).
