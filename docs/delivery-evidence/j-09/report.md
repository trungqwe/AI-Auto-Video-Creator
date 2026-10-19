# Báo cáo bằng chứng J-09

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `c5e236f22f8879070c66bdf088230f05d95ef78a`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-09 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider` (chạy khi audit_record.py là stub)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `100 failed, 4 passed in 0.73s`
- Danh sách test PASSED kèm lý do (4 passed do stub đã định nghĩa):
  - `tests/unit/security/test_j_audit_record.py::test_audit_record_has_exactly_the_eleven_contract_fields_in_order` (stub đã khai báo đầy đủ 11 trường của AuditRecord)
  - `tests/unit/security/test_j_audit_record.py::test_unknown_action_error_is_a_value_error` (stub đã định nghĩa class UnknownAuditActionError kế thừa ValueError)
  - `tests/unit/security/test_j_audit_record.py::test_audit_sink_port_is_append_only` (Protocol AuditSinkPort chỉ có phương thức append)
  - `tests/unit/security/test_j_audit_record.py::test_audit_sink_port_append_returns_none` (annotation return của append là None)
- Danh sách nhóm test FAILED kèm thông điệp nguyên văn (100 failed do AssertionError và NotImplementedError):
  - `tests/unit/security/test_j_audit_record.py::test_required_actions_are_exactly_the_22_contract_codes` (AssertionError: assert 0 == 22 do stub khai báo frozenset rỗng)
  - `tests/unit/security/test_j_audit_record.py::test_every_required_action_can_be_built[...]` (22 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_audit_record_is_frozen` (NotImplementedError: J-09 build_audit_record khi gọi _build)
  - `tests/unit/security/test_j_audit_record.py::test_unknown_action_is_rejected_fail_closed[...]` (6 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_allowed_outcomes_are_accepted[...]` (3 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_other_outcomes_are_rejected[...]` (5 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_reason_is_redacted_through_j02_redact_value` (NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_reason_none_gives_empty_redacted_reason` (NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_non_string_reason_is_rejected_with_type_error[...]` (4 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_identity_and_correlation_fields_must_be_non_empty_strings[...]` (20 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_revision_payload_is_rejected_with_type_error[...]` (14 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_revision_accepts_ref_number_or_none[...]` (2 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_negative_number_or_blank_revision_is_value_error[...]` (6 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_aware_occurred_at_is_accepted_and_stored_as_iso_string[...]` (5 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_naive_occurred_at_is_value_error[...]` (3 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_unparsable_occurred_at_is_value_error[...]` (3 test FAILED do NotImplementedError: J-09 build_audit_record)
  - `tests/unit/security/test_j_audit_record.py::test_non_time_occurred_at_is_type_error[...]` (3 test FAILED do NotImplementedError: J-09 build_audit_record)
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy khi audit_record.py là stub và fail hợp lệ do AssertionError và NotImplementedError.

## Thay đổi

- `src/controlplane/domain/config_security/audit_record.py`: AuditRecord dataclass frozen đúng 11 trường theo thứ tự hợp đồng (audit_id, workspace_id, actor_ref, action, resource_ref, revision_before, revision_after, occurred_at, correlation_id, outcome, redacted_reason); AUDIT_REQUIRED_ACTIONS frozenset đúng 22 mã thuộc 7 nhóm CT-SEC-004; AUDIT_OUTCOMES ('succeeded', 'failed', 'denied'); UnknownAuditActionError kế thừa ValueError; Protocol AuditSinkPort chỉ có append(record) -> None; build_audit_record kiểm tra fail-closed action ngoài tập, outcome hợp lệ, trường định danh không rỗng, revision chỉ nhận ref string hoặc số không âm (từ chối dict/list payload với TypeError), occurred_at yêu cầu múi giờ (từ chối naive với ValueError), reason qua redact_value của J-02.
- `tests/unit/security/test_j_audit_record.py`: 104 test bao phủ toàn bộ 22 mã hành động, tính bất biến frozen của AuditRecord, kiểm tra UnknownAuditActionError, outcome hợp lệ/bất hợp lệ, redaction canaries qua redact_value của J-02, kiểm tra identity và correlation không rỗng, revision ref/number/None và từ chối payload/dict/list/float/bool, occurred_at aware/naive/unparsable, AuditSinkPort append-only và append trả về None; docstring có dòng `coveredIds: CT-SEC-004, TST-SEC-INV-012`.
- `docs/delivery-evidence/j-09/report.md`: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider` | 0 | `104 passed in 0.08s` |
| 2 | `git diff --check` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. Validate nằm ở build_audit_record, AuditRecord khởi tạo trực tiếp chỉ là dataclass frozen.
2. Revision số nguyên không âm được chuẩn hóa thành chuỗi, bool/float/dict/list bị TypeError, chuỗi rỗng hoặc số âm bị ValueError.
3. Reason None thành chuỗi rỗng, reason không phải str bị TypeError, str qua redact_value của J-02.
4. Occurred_at nhận str ISO-8601 hoặc datetime có múi giờ và lưu dạng isoformat, naive hoặc không phân tích được bị ValueError.
5. UnknownAuditActionError kế thừa ValueError, action không phải str cũng bị từ chối.
6. Outcome sai bị ValueError.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật.
- Không có triển khai sink hay migration cp_audit_records, thuộc gói hội tụ.
