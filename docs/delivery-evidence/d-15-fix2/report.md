# Báo cáo D-15-FIX2

## Tóm tắt

Lỗi production CP7-10 (RG-09 thật, ngày 31/10/2026): job `FAILED_FINAL` ở stage analyze với `AnalyzeContent ai_output_schema_violation field_errors {reason: not_json, field: root, attempts: 3}`; cả 3 lượt gọi 9Router đều ok (1198-1500 token đầu ra). Gói D-15-FIX2 thêm một helper dùng chung `parse_model_json_object` gỡ khối code bọc và câu thừa quanh JSON object, rồi cho `CreativePipeline._model_json` và `_parse_vision` của kênh thị giác cùng dùng helper đó.

## Nhóm lỗi R31

- `_model_json` trong `src/creative/application/pipeline.py` gọi `json.loads` nghiêm ngặt, nên JSON đúng nội dung mà model bọc trong khối ```json, kèm một câu trước hay sau, hoặc có xuống dòng thô trong chuỗi đều thành `not_json` ở mọi lượt thử.
- `_parse_vision` của kênh thị giác (cùng model) đã tự gỡ khối bọc riêng, nên hai nơi parse đầu ra model lệch nhau.

## Thay đổi theo tệp

- `src/controlplane/application/model_json.py` (mới, module của gói `controlplane.application` đã khai trong `src/controlplane/pyproject.toml`): `ModelJsonError(ValueError)` có thuộc tính `reason`; `parse_model_json_object` theo thứ tự `empty_output`, gỡ khối bọc, `json.loads(strict=False)`, cắt từ `{` đầu tới `}` cuối thử đúng một lần, `not_json`, `not_a_json_object`. Chỉ bắt `json.JSONDecodeError` nên lỗi do `parse_constant` ném ra đi nguyên vẹn. Chỉ dùng stdlib.
- `src/creative/application/pipeline.py`: `_model_json` dùng `parse_model_json_object`, `ModelJsonError` thành `PipelineRejected(SCHEMA_VIOLATION, error.reason, '$')` (giữ `not_json`, `not_a_json_object`, thêm `empty_output`). Không đổi validator, schema, prompt, số lần thử, `ProviderFailureHandler`.
- `src/voice/adapters/real_llm_image_safety.py`: `_parse_vision` nhánh chuỗi dùng `parse_model_json_object(raw, parse_constant=_reject_constant)`; `not_a_json_object` thành `wrong_type`, lý do khác thành `bad_json`; bỏ `import json` vì không còn dùng. Nhánh Mapping và các kiểm sau giữ nguyên.
- `tests/integration/prod_wiring/test_d15_fix1_ai_output_retry.py`: thêm helper `truncated`; ba test dùng `fenced` làm đầu ra hỏng (`test_story_angles_retry_after_fenced_json_records_both_attempts`, `test_schema_violation_on_every_attempt_stops_at_max_attempts_with_a_structured_problem`, `test_composition_passes_max_attempts_from_the_profile`) đổi sang `truncated`, giữ tên test, assertion và helper `fenced`; thêm ba test mới cuối tệp (`test_analyze_content_accepts_a_fenced_json_object_on_the_first_attempt`, `test_story_angles_accepts_json_surrounded_by_sentences_on_the_first_attempt`, `test_empty_model_output_on_every_attempt_fails_with_reason_empty_output`).
- `tests/integration/prod_wiring/test_d15_fix2_model_json.py` (mới): test thuần, không CSDL, không monkeypatch production, đủ các ca của helper (object thường, khối bọc có/không ngôn ngữ/thiếu đóng, câu thừa, xuống dòng thô và tab, empty_output, not_json, not_a_json_object, `parse_constant`).
- `docs/delivery-evidence/d-15-fix2/report.md` (mới): báo cáo này.

## Đính chính đường dẫn module (D-15-FIX2-MODULE-PATH)

Candidate 43925cc đặt helper ở gói con mới `controlplane.application.ai_output` chưa khai trong `[tool.setuptools.package-dir]` nên hỏng kiểm canh CP2A-LAYOUT (REBASE INTEGRATION_GUARD_FAILED, seq 799). Lượt này chuyển helper thành module `src/controlplane/application/model_json.py`, xoá `src/controlplane/application/ai_output/__init__.py` và `model_json.py` để thư mục `ai_output` không còn, đổi import ở `pipeline.py`, `real_llm_image_safety.py` và `test_d15_fix2_model_json.py` sang `controlplane.application.model_json`, không sửa `pyproject.toml`.

## Lệnh kiểm đã chạy

Interpreter `python` của môi trường lane; `PYTEST_DEBUG_TEMPROOT` đặt theo spec.

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| RED với mã cũ: `python -m pytest tests/integration/prod_wiring/test_d15_fix1_ai_output_retry.py -q -p no:cacheprovider` | 1 | `3 failed, 15 passed in 12.80s`; ba test hỏng: `test_analyze_content_accepts_a_fenced_json_object_on_the_first_attempt`, `test_story_angles_accepts_json_surrounded_by_sentences_on_the_first_attempt`, `test_empty_model_output_on_every_attempt_fails_with_reason_empty_output` (reason cũ `not_json` thay vì `empty_output`) |
| `python -m pytest tests/integration/prod_wiring/test_d15_fix2_model_json.py tests/integration/prod_wiring/test_d15_fix1_ai_output_retry.py tests/integration/prod_wiring/test_pw_d1_roles_prompts.py -q -p no:cacheprovider` | 0 | `68 passed in 19.49s` |
| `python -m pytest tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d15_provider_failure.py tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider` | 0 | `100 passed in 0.26s` |
| `python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_safety_scores.py tests/integration/prod_ports/test_pp_7_vision_route.py -q -p no:cacheprovider` | 0 | `144 passed in 37.71s` |
| `python -m pytest tests/unit/creative/test_d01_package_layout.py tests/m2/test_p0_architecture_rules.py -q -p no:cacheprovider` | 0 | `22 passed, 70 subtests passed in 0.54s` |
| probe `pipeline.py` dùng `parse_model_json_object`, không còn `json.loads(result.output.text)` | 0 | assert đạt |
| probe `real_llm_image_safety.py` dùng `parse_model_json_object` | 0 | assert đạt |
| probe `model_json.py` có `JSONDecodeError` và `strict=False`, thư mục `ai_output` không còn | 0 | assert đạt |
| probe package-dir: mọi `__init__.py` dưới `src/controlplane` nằm trong `[tool.setuptools.package-dir]` | 0 | assert đạt |
| probe `report.md` có `D-15-FIX2` và `R31` | 0 | assert đạt |
| `git diff --check` | 0 | không có output lỗi |

## Không làm

- Không sửa JSON cụt, không `eval`, không đổi nội dung object do model trả.
- Không nới validator hay schema.
- Không đổi prompt, số lần thử, adapter HTTP hay tuyến.
- Không bật JSON mode.

## Mục mở

- Đầu ra thô của ba lượt hỏng không còn (9Router không bật nhật ký chi tiết, store của production nằm trong bộ nhớ), nên dạng hỏng suy từ mã và tiền lệ D-15-FIX1.
- Lý do `empty_output` tách được trường hợp model không trả nội dung khỏi `not_json`.
- Nghiệm thu thật là RG-09 của CP7-10 sau gói này.
- JSON mode chưa bật vì chưa thăm dò tuyến.
