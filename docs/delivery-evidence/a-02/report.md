# B?o c?o b?ng ch?ng A-02

## M?i tr??ng

- Interpreter kho?: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `22535f6dcff3dbf2e3187771a9bff1b34c85c838`
- Ngu?n quy?n: IMPL-PLAN-A Auditor PASS, slice A-02 trong docs/implementation/a/slices.md.
- Binding refs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `tests/fixtures/contracts/a-b-collected-document/payloads.json`.

## RED

- L?nh th?c thi: `python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider` (ch?y tr?n skeleton v?i PACKAGE_FIELDS r?ng v? hai h?m stub)
- Exit code th?c t?: 1
- D?ng t?m t?t nguy?n v?n: `79 failed, 18 passed, 7 subtests passed in 0.43s`
- Chi ti?t c?c test FAILED/SUBFAILED ti?u bi?u k?m th?ng ?i?p AssertionError nguy?n v?n:
  - `FAILED tests/unit/collection/test_a02_collected_document_package.py::FieldSpecBindingTests::test_drift_comparison_detects_mutated_binding`: `AssertionError: [] is not true : PACKAGE_FIELDS must not be empty`
  - `FAILED tests/unit/collection/test_a02_collected_document_package.py::FieldSpecBindingTests::test_extraction_disposition_has_no_enum_lock`: `AssertionError: 'extraction_disposition' not found in {}`
  - `FAILED tests/unit/collection/test_a02_collected_document_package.py::FieldSpecBindingTests::test_field_specs_match_binding_exactly`: `AssertionError: Lists differ: [] != [{'name': 'collected_document_id', 'type': 'string', 'required': True}, ...]`
  - `SUBFAILED(case='missing_provenance_chain') tests/unit/collection/test_a02_collected_document_package.py::SchemaLayerTests::test_fixture_invalid_payloads_fail_with_expected_error`: `AssertionError: Tuples differ: () != (SchemaError(code='missing_required', field='provenance_chain'),)`
  - `FAILED tests/unit/collection/test_a02_collected_document_package.py::SchemaLayerTests::test_each_missing_required_field_is_reported`: `AssertionError: Tuples differ: () != (SchemaError(code='missing_required', field='collected_document_id'),)`
  - `SUBFAILED(title="'Sample Title'") tests/unit/collection/test_a02_collected_document_package.py::ContentLayerTests::test_missing_policy_is_input_not_ready_without_default`: `AssertionError: ContentAssessment(outcome='candidate', reason=None, policy_revision=None) != ContentAssessment(outcome='INPUT_NOT_READY', reason='missing_extraction_policy', policy_revision=None)`
  - `SUBFAILED(case='missing_provenance_chain', policy=True) tests/unit/collection/test_a02_collected_document_package.py::ContentLayerTests::test_schema_invalid_package_raises_validation_error`: `AssertionError: PackageValidationError not raised`
- X?c nh?n: Ho?n to?n kh?ng c? ImportError, ModuleNotFoundError hay l?i collection; RED ch?y tr?n skeleton (PACKAGE_FIELDS r?ng, hai h?m stub tr? gi? tr? gi?) v? m?i l?i ??u l? sai oracle (AssertionError).

## Thay ??i

- T?p module domain m?i `src/source_ingestion/domain/package.py`:
  - `FieldSpec`: dataclass ??nh ngh?a quy c?ch tr??ng c?p 1 (name, type, required, enum, items).
  - `PACKAGE_FIELDS`: tuple ch?a ??ng 20 FieldSpec ???c vi?t tay kh?p 1:1 v?i binding `a-b-collected-document.json` 1.0.0 (12 tr??ng required, 8 tr??ng optional).
  - `NON_EMPTY_STRING_FIELDS`: frozenset ch?a `extraction_disposition` ?? t? ch?i chu?i r?ng/kho?ng tr?ng ? l?p 1.
  - `SchemaError`: dataclass bi?u di?n l?i schema v?i code (`missing_required`, `wrong_type`, `enum_violation`) v? field.
  - `PackageValidationError`: ngo?i l? k? th?a ValueError v?i code `VALIDATION_ERROR` v? thu?c t?nh `errors`.
  - `ExtractionPolicy`: dataclass ch?a revision v? mapping `title_required_by_source_kind`, ki?m tra t?nh b?t bi?n v? validate ki?u ? `__post_init__`.
  - `ContentAssessment`: dataclass k?t qu? ??nh gi? n?i dung g?m outcome (`candidate`, `incomplete`, `INPUT_NOT_READY`), reason v? policy_revision.
  - `validate_package_schema`: h?m l?p 1 ki?m tra ki?u, tr??ng b?t bu?c, datetime RFC3339 c? timezone offset, integer kh?ng nh?n bool, enum v? chu?i kh?ng r?ng.
  - `assess_content_eligibility`: h?m l?p 2 th?c thi theo th? t? ki?m tra schema (n?m PackageValidationError n?u sai), ki?m tra policy/source_kind (tr? INPUT_NOT_READY), ki?m tra tr?ch xu?t n?i dung (tr? incomplete n?u thi?u content/text r?ng ho?c thi?u title khi policy y?u c?u), tr? candidate n?u ??t.
- T?p ki?m th? m?i `tests/unit/collection/test_a02_collected_document_package.py` g?m 27 test qua 3 l?p:
  - `FieldSpecBindingTests` (3 test): so kh?p h?ng v?i binding, self-test b?t drift tr?n 7 k?ch b?n ??t bi?n, x?c nh?n `extraction_disposition` kh?ng kho? enum.
  - `SchemaLayerTests` (14 test): ki?m tra m?i fixture case valid/invalid, t?ng tr??ng required b? thi?u/None, integer t? ch?i bool/string/float, enum validation, RFC3339 datetime, array type/items, tr??ng optional v?ng/None kh?ng l?i, additive fields, payload non-mapping, t?nh t?t ??nh v? b?t bi?n c?a payload.
  - `ContentLayerTests` (10 test): payload h?p l? cho candidate, thi?u policy/source_kind cho INPUT_NOT_READY, text r?ng/kho?ng tr?ng cho incomplete v?i reason `empty_main_text`, thi?u title theo rule c?a source_kind, thi?u published_at_candidate v?n candidate, schema sai n?m PackageValidationError, copy v? validate policy rules.

## ?nh x? coveredIds

| M? y?u c?u / Test ID | C?c test case ki?m ch?ng |
|---|---|
| TST-COL-PKG-001 | `test_each_missing_required_field_is_reported`, `test_fixture_invalid_payloads_fail_with_expected_error`, `test_repeated_invalid_payload_is_deterministic_and_not_mutated`, `test_schema_invalid_package_raises_validation_error` |
| TST-COL-PKG-002 | `test_empty_main_text_is_incomplete_with_reason`, `test_missing_extracted_content_is_incomplete` |
| TST-COL-PKG-003 | `test_title_requirement_follows_source_kind_policy` |
| TST-COL-PKG-004 | `test_missing_policy_is_input_not_ready_without_default`, `test_source_kind_absent_from_policy_is_input_not_ready`, `test_missing_published_at_candidate_stays_candidate`, `test_missing_conditional_fields_are_not_schema_errors` |
| A-RULE-010 | `test_each_missing_required_field_is_reported` (ki?m tra `source_id`, `collection_run_id`, `provenance_chain`), `test_array_fields_check_container_and_item_types` |

## L?nh ki?m

| # | L?nh | Exit code | K?t qu? |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider` | 0 | 27 passed, 99 subtests passed in 0.06s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.04s |
| 3 | `python -c "import pathlib; fs = ['src/source_ingestion/domain/package.py', 'tests/unit/collection/test_a02_collected_document_package.py', 'docs/delivery-evidence/a-02/report.md']; bad = [f for f in fs if (lambda b: b.startswith(b'\xef\xbb\xbf') or b'\r' in b or not b.endswith(b'\n') or any(line != line.rstrip(b' \t') for line in b.split(b'\n')))(pathlib.Path(f).read_bytes())]; print('hygiene bad:', bad); raise SystemExit(1 if bad else 0)"` | 0 | hygiene bad: [] |
| 4 | `git diff --check` | 0 | kh?ng output |

## Quy?t ??nh m?c ??nh (D8)

1. `extraction_disposition` kh?ng kho? enum, ch? t? ch?i chu?i r?ng/kho?ng tr?ng b?ng `wrong_type` ? l?p 1, v? ??y l? tr??ng c?u tr?c b?t bu?c ghi nh?n tr?ng th?i tr?ch xu?t c?a adapter, kh?ng ph?i thi?u n?i dung.
2. Tr??ng optional c? gi? tr? `None` ???c coi nh? v?ng, kh?p v?i logic chu?n ho? c?a `tests/contract/binding_validator.py`.
3. Datetime ???c ki?m tra b?ng regex RFC3339 k?t h?p `datetime.fromisoformat` v? b?t bu?c c? timezone offset (tzinfo is not None).
4. L?p 2 ki?m tra schema tr??c (fail-fast n?m PackageValidationError), sau ?? ??n policy, r?i m?i t?i n?i dung chi ti?t.
5. Tr??ng h?p `source_kind` kh?ng n?m trong danh m?c ch?nh s?ch c?a policy ???c ??nh gi? l? `INPUT_NOT_READY` k?m reason `missing_source_kind_policy`.
6. ??nh danh c?c m? reason: `missing_extraction_policy`, `missing_source_kind_policy`, `missing_extracted_content`, `empty_main_text`, `missing_required_title`.
7. C?c ch?nh s?ch cho `web_page` v? `rss_feed` trong test ch? l? fixture th? nghi?m; kh?ng g?n c? ??nh v?o t?ng domain.
8. Kh?ng th?m b?t k? th? vi?n ngo?i n?o; ch? s? d?ng Python stdlib (re, collections.abc, dataclasses, datetime, types).

## Danh s?ch ch? user (pendingUserCheckpoint)

- MODULE-A-OPEN-005 (gi? tr? ExtractionPolicy production: title theo source kind, ng??ng n?i dung)
- MODULE-A-OPEN-001 (t?p source_kind)
- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 t?i nguy?n th?t (D5)

## Gi?i h?n

- Kh?ng ki?m tra tr??ng con c?a `http_observation`, `provenance_chain`, `extracted_content_candidate` ? l?p 1 (theo IMPL-PLAN-A ?2(c)).
- Ch?a c? ng??ng ?? d?i t?i thi?u c?a text (ch? quy?t ??nh t?i MODULE-A-OPEN-005).
- Y?u c?u raw snapshot theo policy ch?a x? l? trong slice n?y (thu?c ph?m vi A-13/A-14).
- Kh?ng ch?y full test suite, tests/m1, tests/m2.
- Kh?ng thay ??i `pyproject.toml`, `uv.lock`.
- Kh?ng g?i d?ch v? th?t hay ??c b? m?t.
