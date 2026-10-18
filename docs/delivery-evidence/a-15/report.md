# Báo cáo bằng chứng A-15

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `7f6c060c32c3dc545b857a1714b5fea0b445429f`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-15 trong docs/implementation/a/slices.md, coveredIds A-RULE-006, A-RULE-007; CT-SRC-004 (docs/09-contracts/04-source-content-contracts.md).

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `59 failed, 9 passed, 1 subtests passed in 0.34s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn của bước 9:
  - `SUBFAILED(order=['s-c', 's-a', 's-d', 's-b']) tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_order_is_independent_of_input_and_dict_order`: `AssertionError`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_order_is_independent_of_input_and_dict_order`: `AssertionError`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_orders_by_tier_then_source_id`: `AssertionError: Lists differ: ['s-c', 's-a', 's-b', 's-d', 's-e'] != ['s-b', 's-d', 's-c', 's-e', 's-a']`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_tier_order_is_an_input`: `AssertionError: Lists differ: ['s-c', 's-a', 's-b', 's-d', 's-e'] != ['s-a', 's-b', 's-d', 's-c', 's-e']`
  - `SUBFAILED(tier_order=frozenset({'T1', 'T2', 'T3'})) tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_tier_order_must_be_unique_ordered_sequence`: `AssertionError: ValueError not raised`
  - `SUBFAILED(tier_order=()) tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_tier_order_must_be_unique_ordered_sequence`: `AssertionError: ValueError not raised`
  - `SUBFAILED(tier_order=('T1', 'T1')) tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_tier_order_must_be_unique_ordered_sequence`: `AssertionError: ValueError not raised`
  - `SUBFAILED(tier_order='T1') tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_tier_order_must_be_unique_ordered_sequence`: `AssertionError: ValueError not raised`
  - `SUBFAILED(tier_order=('T1', '')) tests/unit/collection/test_a15_source_eligibility.py::RankingOrderTests::test_tier_order_must_be_unique_ordered_sequence`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::EligibilityFilterTests::test_only_active_sources_are_selected`: `AssertionError: Lists differ: ['s-2', 's-3', 's-1'] != ['s-1']`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::EligibilityFilterTests::test_periodic_run_in_business_date_excludes_source`: `AssertionError`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::EligibilityFilterTests::test_ranking_is_pure_and_repeatable`: `AssertionError`
  - `SUBFAILED(case='duplicate_source_id') tests/unit/collection/test_a15_source_eligibility.py::EligibilityFilterTests::test_rejects_malformed_snapshot`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='not_a_source') tests/unit/collection/test_a15_source_eligibility.py::EligibilityFilterTests::test_rejects_malformed_snapshot`: `AssertionError: TypeError not raised`
  - `SUBFAILED(case='not_a_run') tests/unit/collection/test_a15_source_eligibility.py::EligibilityFilterTests::test_rejects_malformed_snapshot`: `AssertionError: TypeError not raised`
  - `SUBFAILED(case='datetime_business_date') tests/unit/collection/test_a15_source_eligibility.py::EligibilityFilterTests::test_rejects_malformed_snapshot`: `AssertionError: TypeError not raised`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::EligibilityFilterTests::test_scope_and_tier_reasons`: `AssertionError`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_below_target_opens_next_tier`: `AssertionError: None != 'T2'`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_last_tier_below_target_has_no_more_tiers`: `AssertionError: <TierExpansionAction.OPEN_NEXT_TIER: 'OPEN_NEXT_TIER'> is not <TierExpansionAction.NO_MORE_TIERS: 'NO_MORE_TIERS'>`
  - `SUBFAILED(count=5) tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_reaching_target_stops_expansion_for_g_to_record`: `AssertionError: <TierExpansionAction.OPEN_NEXT_TIER: 'OPEN_NEXT_TIER'> is not <TierExpansionAction.STOP_SUFFICIENT: 'STOP_SUFFICIENT'>`
  - `SUBFAILED(count=9) tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_reaching_target_stops_expansion_for_g_to_record`: `AssertionError: <TierExpansionAction.OPEN_NEXT_TIER: 'OPEN_NEXT_TIER'> is not <TierExpansionAction.STOP_SUFFICIENT: 'STOP_SUFFICIENT'>`
  - `SUBFAILED(case='target_zero') tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_rejects_invalid_decision_input`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='target_bool') tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_rejects_invalid_decision_input`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='target_text') tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_rejects_invalid_decision_input`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='unknown_tier') tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_rejects_invalid_decision_input`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='other_topic') tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_rejects_invalid_decision_input`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='other_business_date') tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_rejects_invalid_decision_input`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::TierExpansionDecisionTests::test_threshold_is_an_input`: `AssertionError: <TierExpansionAction.OPEN_NEXT_TIER: 'OPEN_NEXT_TIER'> is not <TierExpansionAction.STOP_SUFFICIENT: 'STOP_SUFFICIENT'>`
  - `SUBFAILED(overrides={'unique_article_count': -1}) tests/unit/collection/test_a15_source_eligibility.py::UniqueCounterOnlyTests::test_counter_values_are_validated`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'unique_article_count': True}) tests/unit/collection/test_a15_source_eligibility.py::UniqueCounterOnlyTests::test_counter_values_are_validated`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'unique_article_count': 1.0}) tests/unit/collection/test_a15_source_eligibility.py::UniqueCounterOnlyTests::test_counter_values_are_validated`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'topic': ''}) tests/unit/collection/test_a15_source_eligibility.py::UniqueCounterOnlyTests::test_counter_values_are_validated`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'business_date': datetime.datetime(2026, 10, 19, 6, 0, tzinfo=datetime.timezone.utc)}) tests/unit/collection/test_a15_source_eligibility.py::UniqueCounterOnlyTests::test_counter_values_are_validated`: `AssertionError: TypeError not raised`
  - `SUBFAILED(raw=50) tests/unit/collection/test_a15_source_eligibility.py::UniqueCounterOnlyTests::test_raw_url_or_item_counts_are_rejected`: `AssertionError: TypeError not raised`
  - `SUBFAILED(raw={'url_count': 50}) tests/unit/collection/test_a15_source_eligibility.py::UniqueCounterOnlyTests::test_raw_url_or_item_counts_are_rejected`: `AssertionError: TypeError not raised`
  - `SUBFAILED(raw={'item_count': 50}) tests/unit/collection/test_a15_source_eligibility.py::UniqueCounterOnlyTests::test_raw_url_or_item_counts_are_rejected`: `AssertionError: TypeError not raised`
  - `FAILED tests/unit/collection/test_a15_source_eligibility.py::NoFakeRunTests::test_outputs_carry_no_collection_run`: `AssertionError: <TierExpansionAction.OPEN_NEXT_TIER: 'OPEN_NEXT_TIER'> is not <TierExpansionAction.STOP_SUFFICIENT: 'STOP_SUFFICIENT'>`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (3 test đạt gồm `test_module_hard_codes_no_tier_literal`, `test_counter_carries_only_unique_article_count`, `test_module_never_builds_runs_or_decisions`; tất cả các lỗi FAILED/SUBFAILED đều là AssertionError do khung stub chưa cài đặt logic kiểm tra).

## Thay đổi

- 2 tệp mới:
  - `src/source_ingestion/application/source_eligibility.py`: cài đặt các hàm thuần xếp hạng nguồn deterministic theo Tier và quyết định mở rộng/dừng Tier expansion.
  - `tests/unit/collection/test_a15_source_eligibility.py`: bộ kiểm thử đơn vị bao phủ các phản ví dụ và ràng buộc bất biến (coveredIds: A-RULE-006, A-RULE-007).
- Các API và cấu trúc dữ liệu:
  - `EligibilityReason`: Enum gồm `SELECTED`, `SOURCE_NOT_ACTIVE`, `WORKSPACE_OUT_OF_SCOPE`, `TOPIC_OUT_OF_SCOPE`, `TIER_NOT_RANKED`, `PERIODIC_RUN_EXISTS`.
  - `TierExpansionAction`: Enum gồm `OPEN_NEXT_TIER`, `STOP_SUFFICIENT`, `NO_MORE_TIERS`.
  - `SourceEligibility`: Frozen dataclass chứa thông tin đủ điều kiện của một nguồn (`source_id`, `tier`, `selected`, `reason`).
  - `EligibilityPlan`: Frozen dataclass chứa kết quả xếp hạng nguồn (`workspace_id`, `topic`, `business_date`, `tier_order`, `selected`, `skipped`).
  - `UniqueArticleCount`: Frozen dataclass mang bộ đếm bài viết duy nhất do G/B cung cấp (`topic`, `business_date`, `unique_article_count`).
  - `TierExpansionDecision`: Frozen dataclass mang quyết định mở rộng Tier (`topic`, `business_date`, `completed_tier`, `action`, `next_tier`, `unopened_tiers`, `unscanned_source_ids`, `unique_article_count`, `fresh_unique_article_target`).
  - `rank_eligible_sources`: Hàm thuần xếp nguồn theo thứ tự Tier (input `tier_order`), phá hoà bằng `source_id`, lọc chỉ nguồn ACTIVE, đúng workspace, đúng topic, chưa có run PERIODIC trong business_date.
  - `decide_tier_expansion`: Hàm thuần quyết định mở Tier tiếp theo hoặc dừng khi đủ ngưỡng bài viết duy nhất.
- Ánh xạ phản ví dụ sang class test:
  - Thứ tự phụ thuộc dict: `RankingOrderTests`
  - Nguồn DISABLED được chọn: `EligibilityFilterTests`
  - Dùng số URL thay số unique: `UniqueCounterOnlyTests`
  - Tạo CollectionRun cho nguồn bị bỏ qua: `NoFakeRunTests`
  - A-RULE-006 (ngưỡng và mở Tier sau): `TierExpansionDecisionTests`

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider` | 0 | 20 passed, 49 subtests passed in 0.05s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider` | 0 | 48 passed, 51 subtests passed in 0.12s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Thứ tự Tier là input `tier_order` (chuỗi có thứ tự, không trùng), không hard-code vì tiêu chí Tier là MODULE-A-OPEN-002; nguồn có Tier ngoài tier_order bị bỏ qua với TIER_NOT_RANKED (fail-closed).
2. Chỉ run PERIODIC cùng workspace_id + source_id + business_date chặn nguồn (A-RULE-004); SUPPLEMENTAL/SOURCE_TEST không chặn (CT-SRC-004 bất biến 4).
3. Ngưỡng `fresh_unique_article_target` là int ≥ 1 do caller truyền (MODULE-A-OPEN-003); `unique_article_count >= target` thì STOP_SUFFICIENT.
4. Khi dừng, decision trả `unopened_tiers` và `unscanned_source_ids` để G ghi SKIPPED_SUFFICIENT; A không tạo CollectionRun, không ghi CollectionDecision.
5. Counter phải khớp topic và business_date của plan.
6. Chỉ dùng stdlib và source_ingestion.domain; chưa có binding CT-SRC-004, wiring cycle ở CONV-A-06.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- MODULE-A-OPEN-002 tiêu chí Tier
- MODULE-A-OPEN-003 giá trị ngưỡng từng chủ đề

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.
