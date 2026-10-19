# Báo cáo bằng chứng J-15

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `f5bef3db069c137b89b0f8313425d220808d57e2`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-15 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider` (chạy khi account_test.py là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `39 failed, 8 passed in 0.51s`
- Danh sách test PASSED kèm lý do (8 passed do stub đã định nghĩa kiểu, giao thức, hằng canary, cấu trúc module):
  - `tests/unit/security/test_j_account_test.py::test_module_docstring_declares_covered_ids` (docstring khai báo coveredIds)
  - `tests/unit/security/test_j_account_test.py::test_tester_name_does_not_start_with_test_so_pytest_never_collects_it` (ExternalAccountTester không bắt đầu bằng Test)
  - `tests/unit/security/test_j_account_test.py::test_dataclass_fields_match_the_contract_in_order` (ProbeResult và AccountTestReceipt khai báo đúng trường theo thứ tự)
  - `tests/unit/security/test_j_account_test.py::test_ports_expose_exactly_the_contract_methods` (AccountProbePort và ReceiptStorePort đúng phương thức)
  - `tests/unit/security/test_j_account_test.py::test_tester_constructor_takes_only_probe_receipts_and_clock` (ExternalAccountTester.__init__ đúng tham số)
  - `tests/unit/security/test_j_account_test.py::test_control_raw_detail_exposes_every_canary` (hằng canary và raw detail hợp lệ)
  - `tests/unit/security/test_j_account_test.py::test_tester_has_no_enable_disable_or_set_route_and_only_run_is_public` (ExternalAccountTester chỉ có run)
  - `tests/unit/security/test_j_account_test.py::test_service_module_does_not_import_route_catalog_or_routing` (module không import route/catalog)
- Danh sách nhóm test FAILED kèm thông điệp nguyên văn (39 failed):
  - 38 test failed do `NotImplementedError: J-15 ExternalAccountTester.run` khi gọi `run(...)`:
    - `test_receipt_and_probe_result_are_frozen`
    - `test_probe_is_always_called_with_minimal_true` (4 tham số: ENABLED, DISABLED, DEGRADED, INVALID)
    - `test_minimal_is_true_even_when_the_probe_fails_or_raises` (2 tham số: None, error1)
    - `test_success_receipt_carries_probe_outcome_and_clock_time`
    - `test_failed_probe_result_is_mapped_without_raising`
    - `test_none_detail_stays_none`
    - `test_receipt_id_is_deterministic_per_account_and_operation_key`
    - `test_invalid_operation_key_is_value_error_and_never_probes_or_saves` (4 tham số: '', None, 7, b'op')
    - `test_second_run_with_same_operation_key_returns_stored_receipt_and_does_not_probe_again`
    - `test_second_run_ignores_a_probe_that_would_now_answer_differently`
    - `test_different_operation_keys_each_probe_once`
    - `test_failed_receipt_is_also_idempotent`
    - `test_revoked_account_is_not_probed_and_gets_revoked_receipt`
    - `test_revoked_receipt_is_idempotent_and_never_probes`
    - `test_raising_probe_becomes_failed_receipt_with_class_name_and_no_canary` (5 tham số lỗi)
    - `test_probe_result_detail_goes_through_redact_value`
    - `test_redacted_detail_has_no_token_pattern`
    - `test_probe_error_class_string_is_redacted_too`
    - `test_probe_exception_with_unprintable_message_still_yields_receipt`
    - `test_probe_returning_garbage_is_a_failed_receipt_not_an_exception`
    - `test_run_never_changes_the_account` (5 tham số: ENABLED, DISABLED, DEGRADED, INVALID, REVOKED)
    - `test_failed_probe_does_not_disable_or_degrade_the_account` (2 tham số: error0, None)
  - 1 test failed do `AttributeError: module 'controlplane.application.config_security.account_test' has no attribute 'redact_value'`:
    - `test_redaction_uses_j02_redact_value`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy khi account_test.py là stub và fail hợp lệ do NotImplementedError và AttributeError đúng oracle.

## Thay đổi

- `src/controlplane/application/config_security/account_test.py`: ProbeResult, AccountTestReceipt, AccountProbePort, ReceiptStorePort, _receipt_id, ExternalAccountTester.run; không mutation, không enable/disable/set_route, không import route/catalog.
- `tests/unit/security/test_j_account_test.py`: 47 test bao phủ minimal=True, idempotent, REVOKED, probe raise, canary redaction, bất biến account, chỉ có run là public, không import route/catalog, redact_value của J-02; docstring coveredIds: CT-ACC-002, TST-SEC-INV-012.
- `docs/delivery-evidence/j-15/report.md`: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider` | 0 | `47 passed in 0.08s` |
| 2 | `git diff --check` | 0 | PASS (không output) |
| 3 | `python -c "import pathlib, re; assert re.search('coveredIds: CT-ACC-002, TST-SEC-INV-012', pathlib.Path('tests/unit/security/test_j_account_test.py').read_text(encoding='utf-8'))"` | 0 | PASS (assert qua) |
| 4 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/j-15/report.md').read_text(encoding='utf-8'); assert 'RED' in t and 'GREEN' in t and 'Exit code' in t and 'NotImplementedError' in t"` | 0 | PASS (assert qua) |

## Quyết định mặc định (D8)

- Clock trả chuỗi ISO-8601 và tested_at = clock(), khớp quy ước now_iso của J-06.
- Receipt_id tất định = 'acctest-' + 24 ký tự đầu sha256 của external_account_id|operation_key.
- Kiểm operation_key rỗng/không phải str là ValueError trước khi probe.
- Tra receipt cũ trước khi xét REVOKED nên REVOKED cũng idempotent.
- Chỉ bắt Exception, không bắt BaseException.
- Error_class và detail đều qua redact_value của J-02.
- Operation_key là khoá đục do caller ghép, không tự gắn account.
- Account_test.py nằm dưới src nhưng là owned path được giao của slice.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật.
- Không có adapter probe thật hay receipt store thật (thuộc gói hội tụ).
