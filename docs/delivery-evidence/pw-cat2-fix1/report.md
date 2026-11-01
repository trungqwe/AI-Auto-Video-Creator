# Báo cáo chuyển giao: đối chiếu lại ValidateVariant khi registry biến thể đổi (PW-CAT2-FIX1)

- Task: PW-CAT2-FIX1
- Trạng thái: IMPLEMENTED

## 1. Tóm tắt

Khi `ReserveVariant` trả waiting `VARIANT_VALIDATION_STALE` hoặc `CommitVideoCompletion` trả waiting `VARIANT_REGISTRY_STALE`, `StageGraphFlow` chạy lại `ValidateVariant` của stage đích rồi gọi lại activity vừa stale, thay vì chờ timer và gọi lại với validation cũ.

| (activity, problem.code) | Stage đích | Activity chạy lại |
| --- | --- | --- |
| (`ReserveVariant`, `VARIANT_VALIDATION_STALE`) | `plan` | `ValidateVariant` |
| (`CommitVideoCompletion`, `VARIANT_REGISTRY_STALE`) | `qc` | `ValidateVariant` |

- Patch id: `variant-stale-revalidate` (`workflow.patched` qua `TemporalGateway.patched`), để history cũ phát lại không lỗi nondeterminism.
- Số vòng bị chặn bởi `should_retry(n, True, settings.retry)` theo `workflow.retry`; hết vòng thì flow trả FAILED, `last_problem` giữ mã stale. PW-G4-FIX1 đưa job sang `FAILED_FINAL` và trả suất.
- `patched` chỉ được gọi ở nhánh waiting có (tên, mã) trong bảng và `ValidateVariant` đích đã thành công. Mã waiting khác hoặc `patched` False giữ nguyên hành vi PW-CAT2.

## 2. Tệp đã đổi

- `src/controlplane/application/orchestration/workflows/flow.py`
- `src/controlplane/application/orchestration/workflows/definitions.py`
- `tests/unit/orchestration/test_g_variant_revalidate_flow.py` (mới)
- `tests/integration/prod_wiring/test_pw_cat2_fix1_variant_revalidate.py` (mới)
- `docs/delivery-evidence/pw-cat2-fix1/report.md` (mới)

`variant_handlers.py` và `completion_gate.py` không đổi.

## 3. Bằng chứng RED (mã chưa sửa)

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 4 | `python -m pytest tests/unit/orchestration/test_g_variant_revalidate_flow.py -q -p no:cacheprovider` | 1 | 5 failed, 4 passed |
| 8 | `python -m pytest tests/integration/prod_wiring/test_pw_cat2_fix1_variant_revalidate.py -q -p no:cacheprovider` | 1 | 1 failed, 1 passed in 130.05s |

- Bước 4, test đỏ (lỗi assert hành vi: trả `WAITING_CAPABILITY` thay vì COMPLETED/FAILED, `patched_calls` rỗng): `test_stale_reserve_once_revalidates_plan_and_reserves`, `test_stale_reserve_forever_fails_after_max_attempts`, `test_stale_commit_once_revalidates_qc_and_commits`, `test_stale_commit_forever_fails_after_max_attempts`, `test_patch_inactive_keeps_the_waiting_behavior`. Bốn ca parametrize xanh.
- Bước 8, test đỏ: `test_stale_registry_revalidates_then_reserves_and_replays`, do `TimeoutError` sau 120 giây thật (workflow chờ timer vì `ReserveVariant` stale mãi). `test_patch_inactive_worker_keeps_waiting_and_replays` xanh với mã cũ như dự kiến.

## 4. Lệnh đã chạy (mã mới)

| Bước | Lệnh | Exit code | Dòng tổng kết pytest |
| --- | --- | --- | --- |
| 14 | pytest unit mới + `test_cp6_workflow_static` + `test_cp6_workflow_catalog` + `test_cp6_video_production_flow` | 0 | `39 passed in 1.92s` |
| 15 | pytest `test_pw_cat2_fix1_variant_revalidate`, `test_pw_cat2_flow`, `test_pw_g7_completion`, `test_pw_g4_fix1_job_terminal`, `test_pw_g5_fix1_batch_concurrency` | 0 | `74 passed in 65.06s (0:01:05)` |
| 16 | pytest `test_pw_vert_video_flow`, `test_pw_g3_grants` | 0 | `49 passed in 54.19s` |
| 17 | pytest `test_pw_e2e_batch_video` | 0 | `10 passed in 125.59s (0:02:05)` |
| 18 | pytest `tests/integration/collection creative voice render` | 0 | `544 passed, 25 subtests passed in 4.61s` |
| 19 | pytest `tests/unit` | 0 | `7572 passed, 2561 subtests passed in 25.48s` |
| 20 | probe tĩnh `flow.py` | 0 | không AssertionError |
| 21 | probe tĩnh `definitions.py` | 0 | không AssertionError |
| 22 | probe bố cục CP2A-LAYOUT | 0 | không AssertionError |
| 24 | probe báo cáo (`PW-CAT2-FIX1`, `R38`) | 0 | không AssertionError |
| 25 | `git diff --check` | 0 | không lỗi whitespace |

Số lần gọi activity trong test unit (`StageGraphFlow` thật, gateway giả):

| Ca | `ReserveVariant` / `CommitVideoCompletion` | `ValidateVariant` (stage đích) | Kết quả |
| --- | --- | --- | --- |
| Stale một lần ở plan | `ReserveVariant` 2 lần | 2 lần (`…:r1`, `…:r1:v1`) | COMPLETED, `BuildProductionPlan` 1 lần |
| Stale mãi ở plan | `ReserveVariant` 3 lần | 3 lần (`…:r1`, `:v1`, `:v2`) | FAILED ở plan, mã `VARIANT_VALIDATION_STALE` |
| Stale một lần ở complete | `CommitVideoCompletion` 2 lần | 2 lần ở qc (`…:r1`, `:v1`) | COMPLETED, `PersistVideoOutput` 1 lần |
| Stale mãi ở complete | `CommitVideoCompletion` 3 lần | — | FAILED ở complete, mã `VARIANT_REGISTRY_STALE` |

Replayer (trong test tích hợp, bước 15): history có marker `variant-stale-revalidate` (ca COMPLETED, `ReserveVariant` 2 lần, `validation_ref` kết thúc `:r2`, registry 3) phát lại không lỗi; history của worker tắt patch (workflow chờ, không chạy lại `ValidateVariant`, không có marker) phát lại không lỗi nondeterminism. Cả hai test đạt.

## 5. Quyết định thiết kế

- (a) `operation_key` của `ValidateVariant` chạy lại thêm `:v{n}` vì khoá cũ gây `IdempotencyConflict`.
- (b) `input_refs` đã đóng băng của `ValidateVariant` đích được giữ nguyên.
- (c) Ref của vòng đối chiếu thay ref cùng (`ref_type`, `ref_id`) trong `output_refs` của stage đích, không thêm bản trùng.
- (d) `patched` chỉ gọi ở nhánh waiting có (tên, mã) trong bảng và `ValidateVariant` đích đã thành công.
- (e) Bộ đếm vòng theo (stage, activity, index, revision), không reset, nên `RetryStage` sau khi hết vòng không có vòng mới (ghi nhận là giới hạn).

## 6. Giới hạn còn lại

- 3 workflow đang kẹt không tự gỡ (`patched` ghi nhớ False khi phát lại); Control dọn riêng.
- Đợt dồn nhiều job vào plan sau khi khởi động lại có thể hết vòng và `FAILED_FINAL` (chỉnh theo PUC-G-04).
- Nhãn `wait_reason` `provider_unavailable` cho mã stale và `VARIANT_VALIDATION_UNAVAILABLE` để backlog.
- RED của test tích hợp là `TimeoutError` 120 giây thật vì mã cũ chờ vô hạn.

## 7. Mục R38

R38
Mã đối chiếu R38 theo lệnh kiểm của task; các giới hạn còn lại nằm ở mục 6.

## 8. Tính toàn vẹn ký tự

Tệp được ghi bằng công cụ ghi tệp (UTF-8, LF) và đọc lại sau khi ghi; chữ có dấu còn nguyên, không có ký tự `?` thay thế.
