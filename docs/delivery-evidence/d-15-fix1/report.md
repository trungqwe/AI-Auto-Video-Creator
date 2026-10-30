# Báo cáo D-15-FIX1

## Tóm tắt

Lỗi production CP7-10 (RG-09, AI thật qua 9Router ngày 30/10/2026): 6 job, 0 hoàn tất. Stage script hỏng `FAILED_FINAL` với `ai_output_schema_violation` ở GenerateStoryAngles 3/4 lượt; AnalyzeContent hỏng ở lượt 3 và 4. Gói D-15-FIX1 nối `ProviderFailureHandler` của D-15 vào `CreativePipeline`: mỗi lệnh D có gọi AI gọi model tối đa `max_attempts` lần trong một activity, `max_attempts` lấy từ `profile.ai.retry.max_attempts` qua `creative_activity_deps`.

## Nhóm lỗi R23

Mã cũ có bốn khuyết điểm cùng một nhóm:

- Đầu ra AI sai schema không được thử lại có giới hạn: `CreativePipeline` gọi model đúng một lần, `ProviderFailureHandler` không được gọi ở production.
- Record `AIInvocationRecord` của lượt hỏng bị rollback cùng UoW với lệnh hỏng.
- `COMMAND_REJECTED` retryable=False chỉ mang mã, mất `reason` và `field`.
- `WaitingAIInvocationResult` (hết hạn mức, budget, 429, timeout) bị trả `AI_INVOCATION_FAILED` `FAILED_FINAL` thay vì đi đường chờ.

## Thay đổi theo tệp

- `src/creative/application/provider_failure.py`: thêm `retry_same_provider`, `wait_code`, `provider_wait_code`; `_attempt` bắt mọi từ chối của validator có `code` và `reason` (duck typing); lỗi đầu vào xác định (`INPUT_NOT_READY`, `*context_mismatch`) và defect được ghi record rồi ném lại sau commit; bỏ import cấp module từ pipeline để tránh chu trình.
- `src/creative/application/pipeline.py`: `_execute` tách ba pha (đọc, gọi model có giới hạn, ghi); thêm `_AiPlan`, `_ai_plan`, `_call_model`, `ProviderWaiting`, `failure_policy`, `PipelineRejected.attempts`; sáu lệnh AI dùng `_ai_plan`; hết lượt thì ném lại chính ngoại lệ của vai (AnalysisRejected, ScriptRejected...) kèm `attempts` để giữ kiểu ngoại lệ mà test PW-D1 đã nghiệm thu kiểm.
- `src/creative/worker/activity_handler.py`: `ProviderWaiting` thành kết quả `waiting` (mã `quota_wait` hoặc `provider_unavailable`, retryable True); `COMMAND_REJECTED` mang `field_errors` (reason, field, attempts) dạng token đã redact.
- `src/controlplane/api/wiring/creative.py`: truyền `ProviderFailurePolicy(max_attempts=profile.ai.retry.max_attempts)`; không có số mặc định.
- `tests/integration/prod_wiring/test_d15_fix1_ai_output_retry.py` (mới): 8 ca a-h cùng hai kiểm tĩnh trên PostgreSQL (15 test).
- `tests/integration/creative/test_d15_provider_failure.py`: thêm 3 test cho `retry_same_provider` và từ chối đầu vào xác định; không sửa test cũ.
- `tests/integration/creative/test_d14_creative_pipeline.py`, `tests/integration/creative/test_d16_worker_activity.py`: đổi đúng bốn assertion (bảng dưới).

## Dòng test cũ đã đổi

Lý do chung: record của từng lần gọi model được commit riêng, không rollback theo lệnh hỏng; không xoá test nào.

| Tệp | Test | Dòng cũ | Dòng mới |
| --- | --- | --- | --- |
| test_d14_creative_pipeline.py | test_new_key_for_same_script_id_does_not_create_a_second_script | `assert rig.uow.receipts.get(WS, 'k-script-2') is None and rig.uow.invocations.latest('ws-1:k-script-2') is None` | `assert rig.uow.receipts.get(WS, 'k-script-2') is None` và `assert [(item.revision, item.record.validation_result) for item in rig.uow.invocations.revisions('ws-1:k-script-2')] == [(1, 'passed')]` |
| test_d14_creative_pipeline.py | test_outbox_failure_rolls_back_output_record_receipt_and_outbox_together | `assert uow.scripts.latest('script-1') is None and uow.invocations.latest('ws-1:k-script') is None` | `assert uow.scripts.latest('script-1') is None` và `assert [(item.revision, item.record.validation_result) for item in uow.invocations.revisions('ws-1:k-script')] == [(1, 'passed')]` |
| test_d16_worker_activity.py | test_provider_failure_is_a_failed_result_with_a_code_only_problem | `assert rig.uow.analyses.latest('an-1') is None and rig.uow.invocations.latest('ws-1:op-analysis') is None` | `assert rig.uow.analyses.latest('an-1') is None`, `(attempt,) = rig.uow.invocations.revisions('ws-1:op-analysis')`, `assert (attempt.record.validation_result, SECRET in attempt.record.to_json()) == ('not_run', False)` |
| test_d16_worker_activity.py | test_a_new_key_for_an_existing_script_id_is_a_non_retryable_conflict_and_commits_nothing | `assert rig.uow.invocations.latest('ws-1:op-script-2') is None` | `assert rig.uow.invocations.latest('ws-1:op-script-2').record.validation_result == 'passed'` |

## Lệnh kiểm đã chạy

Interpreter khoá của lane, `PYTEST_DEBUG_TEMPROOT` đặt theo spec.

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | không có lỗi khoảng trắng |
| pytest lệnh 1 (D15-FIX1, D15, D14, D16, PW-D1, PW-D2) | 0 | `160 passed in 22.57s` |
| pytest lệnh 2 (ADAPT-WIRE, PW-W2) | 1 | `1 failed, 125 passed in 14.60s` |
| probe pipeline.py (`ProviderFailureHandler`, không `from src.`) | 0 | đạt |
| probe report (CP7-10, `ai_output_schema_violation`) | 0 | đạt |
| probe report (D-15-FIX1, R23) | 0 | đạt |

Lệnh 2 đỏ ở `tests/integration/adapt/wire/test_adapt_wire_services.py::test_profile_loads_typed_values` (`assert p.revision == 1`, thực tế 2). Nguyên nhân có sẵn từ trước gói này: `tools/launcher/prod/profile.json` ở HEAD đã ghi `revision` = 2 (commit "revision cấu hình theo kết quả đo CP7"), còn test đòi 1. Tệp profile và test đó nằm ngoài owned paths nên gói không sửa; 125 test còn lại của lệnh đạt.

Kiểm chứng đỏ với mã cũ: chạy test mới trên `src` của HEAD cho `13 failed, 2 passed` (hai ca đạt là ca e và f, vốn là chốt chặn không gọi AI). Sau đó áp lại mã mới.

## Không làm

Không nới parser hay validator, không gỡ code fence, không bật JSON mode, không đổi prompt, adapter HTTP, route, schema DB, state machine hay flow G. Test mới không monkeypatch mã production (chỉ gán hằng `WS` của module test D14 như PW-D2); chỉ giả ở biên AI, source set và grant.

## Giới hạn

Nghiệm thu thật là RG-09 của CP7-10 sau gói này; nếu lệnh AI vẫn hỏng sau `max_attempts`, Control đọc `field_errors` để quyết gói prompt. `ai.retry.max_attempts` = 3 là giá trị hồ sơ đã duyệt, không đặt số mới. `failure_policy=None` chỉ dành cho test D-14/PW-D1/PW-D2 không cấu hình thử lại và gọi model một lần.
