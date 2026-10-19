# Báo cáo bằng chứng J-08

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `7467ff26031adb5063e0d851be7f2de3cf4f2105`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-08 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider` (chạy khi incremental_cost.py là stub)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `129 failed, 2 passed in 1.53s`
- Các test FAILED kèm thông điệp nguyên văn (NotImplementedError):
  - `tests/unit/config/test_j_incremental_cost.py::test_record_is_frozen_dataclass_with_fourteen_declared_fields FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_and_status_are_frozen_with_declared_defaults FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_incremental_categories_are_accepted[api_paid] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_incremental_categories_are_accepted[background_service] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_incremental_categories_are_accepted[extra_storage] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_incremental_categories_are_accepted[other_direct] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_non_incremental_or_unknown_category_is_rejected[existing_plan] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_non_incremental_or_unknown_category_is_rejected[electricity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_non_incremental_or_unknown_category_is_rejected[internet] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_non_incremental_or_unknown_category_is_rejected[hardware] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_non_incremental_or_unknown_category_is_rejected[gemini_plan] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_non_incremental_or_unknown_category_is_rejected[] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_non_incremental_or_unknown_category_is_rejected[None] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1.5_0-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1.5_0-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1.5_0-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[0.0-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[0.0-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[0.0-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[True-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[True-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[True-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[False-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[False-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[False-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1.5_1-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1.5_1-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[1.5_1-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad6-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad6-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad6-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad7-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad7-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad7-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad8-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad8-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad8-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad9-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad9-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad9-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad10-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad10-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad10-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad11-quantity] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad11-estimated_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_non_decimal_negative_or_nan_amounts[bad11-actual_cost] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_accepts_valid_decimal_amounts_and_actual_none FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_naive_or_unparsable_occurred_at[2026-10-05T00:00:00] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_naive_or_unparsable_occurred_at[not-a-date] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_naive_or_unparsable_occurred_at[] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_naive_or_unparsable_occurred_at[None] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[-record_id] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[-provider] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[-service] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[-operation_ref] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[-unit] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[-currency] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[-source] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[  -record_id] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[  -provider] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[  -service] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[  -operation_ref] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[  -unit] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[  -currency] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[  -source] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[None-record_id] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[None-provider] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[None-service] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[None-operation_ref] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[None-unit] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[None-currency] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[None-source] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[5-record_id] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[5-provider] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[5-service] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[5-operation_ref] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[5-unit] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[5-currency] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_or_non_string_text_fields[5-source] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_optional_refs[job_ref] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_record_rejects_blank_optional_refs[batch_ref] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_monthly_limit[50] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_monthly_limit[50.0] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_monthly_limit[True] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_monthly_limit[bad3] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_monthly_limit[bad4] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_monthly_limit[bad5] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_monthly_limit[bad6] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_warn_ratio[0.8] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_warn_ratio[bad1] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_warn_ratio[bad2] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_warn_ratio[bad3] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_rejects_invalid_warn_ratio[bad4] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_policy_accepts_ratio_one_and_rejects_non_bool_hard_stop_or_blank_currency FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_spent_counts_only_records_inside_half_open_window FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_window_uses_absolute_instants_across_timezone_offsets FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_spent_prefers_actual_cost_over_estimated_cost FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_empty_records_give_zero_spent_zero_forecast_and_ok FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_forecast_is_linear_extrapolation_over_the_window FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_forecast_is_none_when_no_time_has_elapsed[now0] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_forecast_is_none_when_no_time_has_elapsed[now1] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_forecast_is_capped_at_window_length_after_the_window_ends FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_no_limit_when_monthly_limit_is_none FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_forecast_41_against_limit_50_warns_with_forecast_reason FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_forecast_exactly_at_threshold_warns FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_spent_at_eighty_percent_without_forecast_warns_with_spent_reason FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_spent_and_forecast_over_threshold_list_both_reasons_in_order FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_spent_reaching_limit_is_exceeded[50] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_spent_reaching_limit_is_exceeded[75] FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_below_threshold_is_ok FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_limit_100_and_25_are_evaluated_without_hard_coded_50 FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_custom_warn_ratio_changes_threshold_but_keeps_reason_code FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_currency_mismatch_inside_window_raises FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_currency_is_checked_against_policy_currency FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_currency_mismatch_outside_window_is_ignored FAILED (NotImplementedError: J-08 IncrementalCostRecord)`
  - `tests/unit/config/test_j_incremental_cost.py::test_naive_datetimes_or_empty_window_are_rejected FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_evaluate_budget_rejects_items_that_are_not_cost_records FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_is_false_when_hard_stop_is_off_even_if_exceeded FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_is_true_only_when_hard_stop_and_total_exceeds_limit FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_is_false_without_configured_limit FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_uses_policy_limit_not_hard_coded_50 FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_rejects_invalid_additional_estimate[1.5] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_rejects_invalid_additional_estimate[5] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_rejects_invalid_additional_estimate[True] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_rejects_invalid_additional_estimate[bad3] FAILED (NotImplementedError: J-08 BudgetPolicy)`
  - `tests/unit/config/test_j_incremental_cost.py::test_should_block_rejects_invalid_additional_estimate[bad4] FAILED (NotImplementedError: J-08 BudgetPolicy)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED hợp lệ do NotImplementedError.

## Thay đổi

- `src/controlplane/domain/config_security/incremental_cost.py`: Dataclass frozen `IncrementalCostRecord` (14 trường theo thứ tự spec) kiểm tra nghiêm ngặt kiểu dữ liệu, danh mục hợp lệ thuộc ALLOWED_COST_CATEGORIES (loại trừ và báo `NotIncrementalCostError` với existing_plan, electricity, internet, hardware), số tiền Decimal không âm hữu hạn (InvalidAmountError với float, bool, NaN, âm, Infinity), `BudgetPolicy` cấu hình giới hạn ngân sách và tỷ lệ cảnh báo, hàm pure-domain `evaluate_budget` tính chi phí phát sinh thực tế/ước tính trong cửa sổ nửa mở [window_start, window_end) và dự báo tuyến tính theo microsecond không dùng float hay đọc đồng hồ, và hàm `should_block` chỉ chặn khi bật hard_stop và chi phí vượt ngưỡng monthly_limit.
- `tests/unit/config/test_j_incremental_cost.py`: Bộ kiểm thử 131 test cases bao phủ toàn diện dataclass frozen, kiểm tra danh mục chi phí phát sinh, từ chối số tiền không hợp lệ, phân tích timestamp có offset, tính toán spent và forecast theo cửa sổ thời gian, xử lý lệch múi giờ, phân loại ngân sách (NO_LIMIT, OK, WARN_80, EXCEEDED), reason codes, cơ chế chặn giao dịch `should_block`, và kiểm tra tĩnh mã nguồn không đọc đồng hồ hay dùng float; docstring chứa dòng `coveredIds: CT-COST-001, QR-COST-001`.
- `docs/delivery-evidence/j-08/report.md`: Báo cáo bằng chứng thực thi RED/GREEN, các quyết định D8 và danh sách chờ user của task J-08.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider` | 0 | `131 passed in 0.13s` |
| 2 | `git diff --check` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. category lạ hoặc không phải str -> NotIncrementalCostError (fail-closed).
2. quantity, estimated_cost, actual_cost, monthly_limit, warn_ratio, additional_estimated đều phải là Decimal hữu hạn không âm, Infinity cũng bị từ chối, int/float/bool/str bị từ chối.
3. monthly_limit phải > 0, warn_ratio thuộc (0, 1].
4. occurred_at là ISO-8601 có offset, kiểm khi tạo record và parse lại khi đánh giá.
5. CurrencyMismatchError chỉ xét record nằm trong cửa sổ, record ngoài cửa sổ bị bỏ qua.
6. thời gian đã trôi bị chặn tối đa bằng độ dài cửa sổ (sau cuối kỳ forecast = spent), tính bằng Decimal trên microsecond, không dùng float.
7. reason SPENT_80 đứng trước FORECAST_80, mã cố định dù warn_ratio khác, EXCEEDED chỉ có LIMIT_REACHED, NO_LIMIT và OK không có reason.
8. should_block chỉ True khi hard_stop is True, monthly_limit khác None và spent + additional_estimated > monthly_limit (so sánh nghiêm ngặt), không đọc đồng hồ hay currency.
9. con số 50 USD/tháng không được mã hoá cứng, chỉ đóng bằng workload tháng thật ở CP7-J-04 (G03).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt
- PUC-J-01 (múi giờ/cửa sổ tháng ngân sách)
- PUC-J-02 (xác nhận hard_stop mặc định tắt)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật.
- Chưa nối vào application/infrastructure.
