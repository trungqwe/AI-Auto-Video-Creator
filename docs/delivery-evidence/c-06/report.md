# Báo cáo bằng chứng C-06

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `ec66302c0da0adcc0f99de10a983a393563851de`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-06 trong `docs/implementation/c/slices.md`.
- Binding: `docs/parallel-delivery/bindings/c-d-media-candidates.json` và fixture `tests/fixtures/contracts/c-d-media-candidates/payloads.json` (chỉ đọc).

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `35 failed, 10 passed, 1 subtests passed in 0.21s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn từ bước 7:
  - `SUBFAILED(field='media_kinds') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_array_items_must_be_strings`: `AssertionError: None != ('wrong_type', 'media_kinds')`
  - `SUBFAILED(field='roles') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_array_items_must_be_strings`: `AssertionError: None != ('wrong_type', 'roles')`
  - `SUBFAILED(field='excluded_usage_refs') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_array_items_must_be_strings`: `AssertionError: None != ('wrong_type', 'excluded_usage_refs')`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_boolean_limit_is_wrong_type`: `AssertionError: None != ('wrong_type', 'limit')`
  - `SUBFAILED(case='missing_safety_policy_revision') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_invalid_fixture_queries_report_expected_error`: `AssertionError: None != ('missing_required', 'safety_policy_revision')`
  - `SUBFAILED(case='limit_as_string') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_invalid_fixture_queries_report_expected_error`: `AssertionError: None != ('wrong_type', 'limit')`
  - `SUBFAILED(cursor='page:2') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_malformed_page_cursor_is_invalid_value`: `AssertionError: None != ('invalid_value', 'page_cursor')`
  - `SUBFAILED(cursor='offset:-1') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_malformed_page_cursor_is_invalid_value`: `AssertionError: None != ('invalid_value', 'page_cursor')`
  - `SUBFAILED(cursor='offset:abc') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_malformed_page_cursor_is_invalid_value`: `AssertionError: None != ('invalid_value', 'page_cursor')`
  - `SUBFAILED(cursor='offset:01') tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_malformed_page_cursor_is_invalid_value`: `AssertionError: None != ('invalid_value', 'page_cursor')`
  - `SUBFAILED(limit=0) tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_non_positive_limit_is_invalid_value`: `AssertionError: None != ('invalid_value', 'limit')`
  - `SUBFAILED(limit=-1) tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_non_positive_limit_is_invalid_value`: `AssertionError: None != ('invalid_value', 'limit')`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_unknown_query_fields_are_ignored`: `AssertionError: {} != {'production_snapshot_ref': '00000000-0000-4000-8000-000000000010', 'scene_intent': {'goal': 'scene_intro'}, 'media_kinds': ['image', 'clip'], 'roles': ['illustration'], 'safety_policy_revision': 'safe-v1', 'limit': 20}`
  - `SUBFAILED(payload=...) tests/unit/catalog/test_catalog_candidate_query.py::QueryParseTests::test_valid_fixture_queries_parse`: `AssertionError: {} != {'production_snapshot_ref': '00000000-0000-4000-8000-000000000010', 'scene_intent': {'goal': 'scene_intro'}, 'media_kinds': ['image', 'clip'], 'roles': ['illustration'], 'safety_policy_revision': 'safe-v1', 'limit': 20}`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_aggregate_score_key_is_invalid_value`: `AssertionError: None != ('invalid_value', 'semantic_match_components')`
  - `SUBFAILED(components={'entity': 1.5}) tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_component_outside_unit_interval_is_invalid_value`: `AssertionError: None != ('invalid_value', 'semantic_match_components')`
  - `SUBFAILED(components={'topic': -0.1}) tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_component_outside_unit_interval_is_invalid_value`: `AssertionError: None != ('invalid_value', 'semantic_match_components')`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_empty_reason_codes_is_invalid_value`: `AssertionError: None != ('invalid_value', 'reason_codes')`
  - `SUBFAILED(case='single_opaque_score') tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_invalid_fixture_candidates_report_expected_error`: `AssertionError: None != ('wrong_type', 'semantic_match_components')`
  - `SUBFAILED(case='missing_reason_codes') tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_invalid_fixture_candidates_report_expected_error`: `AssertionError: None != ('missing_required', 'reason_codes')`
  - `SUBFAILED(components={'entity': 'high'}) tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_non_numeric_component_is_wrong_type`: `AssertionError: None != ('wrong_type', 'semantic_match_components')`
  - `SUBFAILED(components={'entity': True}) tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_non_numeric_component_is_wrong_type`: `AssertionError: None != ('wrong_type', 'semantic_match_components')`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::CandidateValidationTests::test_unknown_availability_is_enum_violation`: `AssertionError: None != ('enum_violation', 'availability')`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_components_split_entity_topic_scene_without_total`: `AssertionError: 0 != 1`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_drops_not_usable_availability`: `AssertionError: Lists differ: [] != ['AVAILABLE', 'UNAVAILABLE_SOURCE']`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_every_candidate_goes_through_validate_media_candidate`: `AssertionError: Lists differ: [] != ['a', 'b']`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_excluded_usage_refs_drop_entries`: `AssertionError: Lists differ: [] != ['fresh', 'never']`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_filters_by_media_kind_and_role`: `AssertionError: Lists differ: [] != ['img', 'clip']`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_intent_without_terms_scores_zero_and_keeps_reason_codes`: `AssertionError: Lists differ: [] != [{'entity': 0.0, 'topic': 0.0, 'scene': 0.0}]`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_invalid_query_is_rejected_before_search`: `AssertionError: None != ('missing_required', 'safety_policy_revision')`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_keeps_index_order_instead_of_ranking`: `AssertionError: Lists differ: [] != ['weak', 'strong']`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_limit_and_offset_cursor_paginate`: `AssertionError: Tuples differ: ([], None) != (['m0', 'm1'], 'offset:2')`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_never_returns_more_than_limit`: `AssertionError: Tuples differ: (0, None) != (20, 'offset:20')`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_recent_usage_summary_counts_usage_refs`: `AssertionError: Lists differ: [] != [{'times_used': 2}]`
  - `FAILED tests/unit/catalog/test_catalog_candidate_query.py::QueryBehaviourTests::test_unavailable_source_media_stays_queryable`: `AssertionError: Lists differ: [] != ['historic']`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, AttributeError, TypeError, NameError, IndexError hay lỗi collection nào.
- 2 test duy nhất được phép PASS ở RED: `QueryParseTests.test_contract_error_is_value_error_with_code_and_field` và `CandidateValidationTests.test_valid_fixture_candidates_pass`.

## Thay đổi

- `src/catalog/application/candidate_query.py`:
  - Lớp ngoại lệ `ContractError(ValueError)` lưu `code` và `field` theo BINDING-C-D-MEDIA-CANDIDATES.
  - Dataclass `CandidateIndexEntry` với 13 trường chứa dữ liệu index tìm kiếm candidate.
  - Các hằng phân loại lỗi và schema: `MISSING_REQUIRED`, `WRONG_TYPE`, `INVALID_VALUE`, `ENUM_VIOLATION`, `CURSOR_PREFIX`, `MATCH_COMPONENTS`, `QUERY_REQUIRED`, `QUERY_OPTIONAL`, `QUERY_ITEMS`, `CANDIDATE_REQUIRED`, `CANDIDATE_ITEMS`, `_AVAILABILITY_VALUES`, `_CURSOR_PATTERN`.
  - Hàm `parse_media_candidate_query(payload: dict) -> dict`: kiểm tra các trường bắt buộc/tùy chọn, kiểu dữ liệu, bỏ qua các trường lạ (additive fields), xác thực `limit >= 1` và `page_cursor` khớp định dạng `offset:(0|[1-9]\d*)`.
  - Hàm `validate_media_candidate(payload: dict) -> dict`: kiểm tra candidate, đảm bảo `semantic_match_components` chỉ gồm `entity`/`topic`/`scene` nằm trong đoạn `0..1` (chặn hoàn toàn điểm tổng), `availability` thuộc enum hợp lệ, `reason_codes` không rỗng.
  - Hàm `query_media_candidates(query: dict, entries: Iterable[CandidateIndexEntry]) -> tuple[list[dict], str | None]`: lọc theo `media_kinds`, `roles`, loại bỏ entry `not_usable` qua `classify_availability`, loại bỏ entry giao `excluded_usage_refs`, giữ lại `UNAVAILABLE_SOURCE` (CT-SRC-003, CT-MED-009), giữ nguyên thứ tự index (CT-MED-005, C không xếp hạng thay D), phân trang bằng cursor `offset:<n>`.
- `tests/unit/catalog/test_catalog_candidate_query.py`:
  - 3 lớp kiểm thử với tổng cộng 27 test case:
    - `QueryParseTests` (8 test): kiểm tra ContractError, parse payload hợp lệ từ fixture, từ chối payload không hợp lệ, bỏ qua trường lạ, kiểm tra kiểu limit, kiểu mảng, limit không dương, cursor sai định dạng.
    - `CandidateValidationTests` (7 test): kiểm tra candidate hợp lệ từ fixture, từ chối candidate không hợp lệ (single_opaque_score, missing_reason_codes), reason_codes rỗng, điểm thành phần ngoài 0..1, điểm không phải số, điểm tổng thừa, enum availability lạ.
    - `QueryBehaviourTests` (12 test): kiểm tra lọc kind/role, loại bỏ not_usable, giữ lại media unavailable_source, lọc excluded_usage_refs, tính điểm thành phần độc lập, intent rỗng, xác thực mọi candidate qua validate_media_candidate, phân trang limit/cursor, giới hạn kết quả trả về, giữ nguyên thứ tự index, đếm usage_refs và từ chối query sai trước khi tìm kiếm.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider` | 0 | 27 passed, 19 subtests passed in 0.04s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Mã lỗi bổ sung `invalid_value` cho `limit` < 1, `page_cursor` không khớp `offset:<n>` (n thập phân không âm, không số 0 đứng đầu), `reason_codes` rỗng, thành phần ngoài 0..1 hoặc khoá ngoài `entity`/`topic`/`scene` (chặn điểm tổng); `enum_violation` cho `availability` ngoài CT-STATE-005 — theo quy ước mã của `src/ingestion/domain/package_validation.py`, fixture không có case cho các trường hợp này.
2. `excluded_usage_refs` phải là mảng chuỗi (binding không ghi items).
3. Tỉ lệ khớp = |giao| / |tập yêu cầu| với `scene_intent.entities|topics|scenes`, tập rỗng hoặc không phải list → 0.0, phần tử không phải chuỗi bị bỏ (D8-C-03 so khớp xác định).
4. C giữ nguyên thứ tự index, không xếp hạng, D quyết định cuối (CT-MED-005).
5. `recent_usage_summary` = `{"times_used": len(usage_refs)}`.
6. `reason_codes` luôn có `KIND_MATCH`, `ROLE_MATCH`, thêm `ENTITY_MATCH`/`TOPIC_MATCH`/`SCENE_MATCH` khi thành phần > 0 và `SOURCE_UNAVAILABLE` khi `UNAVAILABLE_SOURCE` (CT-SRC-003, CT-MED-009).
7. Lọc theo `safety_policy_revision`, `technical_constraints`, `recency_diversity_preferences` chưa thuộc slice — giá trị được parse và giữ lại, `safety_rights_status` trả nguyên, không tự chặn (D8-C-06); ghi là GIẢ ĐỊNH chờ D/E chốt.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-010
- ROADMAP-OPEN-011
(Không tự ý ghi nhận bất kỳ mục nào ở trên là đã được người dùng phê duyệt.)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa `pyproject.toml`, `uv.lock`, migration, fixture, binding hay state machine dùng chung.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib (`re`, `collections.abc`, `dataclasses`, `types`, `json`, `pathlib`, `unittest`, `unittest.mock`).
- Không gọi dịch vụ thật.
- Không tạo `conftest.py` hay `__init__.py` trong `tests/`.