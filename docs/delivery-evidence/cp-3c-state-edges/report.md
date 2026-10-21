# Báo cáo CP-3C-STATE-EDGES

## Tệp đã sửa/tạo

- `docs/09-contracts/12-state-machines.md`
- `docs/parallel-delivery/contract-registry.yaml`
- `src/controlplane/domain/config_security/status_graph.py`
- `src/controlplane/domain/config_security/external_account.py`
- `src/controlplane/application/config_security/account_recovery.py`
- `src/controlplane/application/storage_meta/__init__.py`
- `tests/unit/config/test_j_status_graph.py`
- `docs/delivery-evidence/cp-3c-state-edges/report.md`

## Cơ sở

Căn cứ quyết định ARCHITECTURE_CHANGE do user phê duyệt ngày 20/10/2026 (đúng hai cạnh PUC-J-03 và YC-HT-I-04; PUC-G-02, CT-STATE-008, CT-STATE-010 giữ nguyên):
- PUC-J-03: Thêm đúng hai cạnh `(DEGRADED, ENABLED)` và `(INVALID, ENABLED)` vào `ACCOUNT_EDGES` của `status_graph.py` (5 thành 7 cạnh), sửa docstring; `REVOKED` vẫn không có cạnh thoát. `external_account.py` thêm hàm thuần `recover_after_passing_test(account)`: chỉ từ `DEGRADED` hoặc `INVALID`, dùng `require_account_transition`, trả tài khoản `ENABLED` với revision + 1.
- YC-HT-I-04: Trong `src/controlplane/application/storage_meta/__init__.py` thêm `ArtifactLocationStore.record_cleanup_deleted(**kwargs)`, đường ghi duy nhất sang `DELETED`: location đang `CLEANUP_AUTHORIZED`, expected_revision khớp, CleanupAuthorization khớp location, artifact version và hash, `cleanup_deleted is True`, `cleanup_receipt_ref` không rỗng và không khớp `_UNSAFE_REFERENCE`; gọi `transition_artifact_location(requested_state=DELETED)` rồi `update_location` với `evidence=None` để không đè verification_evidence_ref. `transition` và `validate_transition` vẫn từ chối `DELETED`; không thêm phương thức tên `delete`; không sửa đồ thị statemachine, migration hay infrastructure/db/storage_meta.

## RED trước implementation

Chứng kiến RED hợp lệ tại Bước 7 trước khi implement, đã dùng stub trả nguyên trạng nên RED là lỗi assert và DID NOT RAISE thật từ oracle kiểm thử, hoàn toàn không có lỗi import hay thu thập:
- Tóm tắt: `44 failed, 74 passed in 0.45s`
- Tên các test fail và thông điệp assert:
  - `test_edge_sets_are_exact_frozensets`: `AssertionError: assert (True and 5 == 7)`
  - `test_account_pair_is_allowed_only_on_declared_edges[DEGRADED-ENABLED]`: `AssertionError: assert False is True`
  - `test_account_pair_is_allowed_only_on_declared_edges[INVALID-ENABLED]`: `AssertionError: assert False is True`
  - `test_account_counterexamples_are_rejected`: `AssertionError: assert set() == {<ExternalAccountStatus.ENABLED: 'ENABLED'>}`
  - `test_recover_after_passing_test_restores_degraded_and_invalid[DEGRADED]`: `AssertionError: assert <ExternalAccountStatus.DEGRADED: 'DEGRADED'> is <ExternalAccountStatus.ENABLED: 'ENABLED'>`
  - `test_recover_after_passing_test_rejects_other_statuses[ENABLED]`: `Failed: DID NOT RAISE ValueError`
  - `test_service_recovers_degraded_and_invalid_with_passing_receipt[DEGRADED]`: `AssertionError: assert <ExternalAccountStatus.DEGRADED: 'DEGRADED'> is <ExternalAccountStatus.ENABLED: 'ENABLED'>`
  - `test_service_rejects_stale_expected_revision[4]`: `Failed: DID NOT RAISE RevisionConflictError`
  - `test_record_cleanup_deleted_happy_path`: `AssertionError: assert <ArtifactLocationState.CLEANUP_AUTHORIZED: 'CLEANUP_AUTHORIZED'> is <ArtifactLocationState.DELETED: 'DELETED'>`
  - `test_record_cleanup_deleted_rejects_invalid_flag[False]`: `Failed: DID NOT RAISE ValueError`
  - `test_record_cleanup_deleted_rejects_unsafe_or_empty_receipt_ref[]`: `Failed: DID NOT RAISE ValueError`
  - `test_record_cleanup_deleted_rejects_non_cleanup_authorized_state[DECLARED]`: `Failed: DID NOT RAISE ValueError`

## GREEN sau implementation

Sau khi implement Bước 8-11, chạy kiểm thử Bước 12 đạt GREEN:
- Tóm tắt: `118 passed in 0.17s`

## Lệnh đã chạy

| Bước | Lệnh | Exit Code | Kết quả |
|---|---|---|---|
| 12 | `python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider` | 0 | `118 passed in 0.17s` |
| 15 | `python -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path('docs/09-contracts/12-state-machines.md').read_bytes()).hexdigest())"` | 0 | sha256 byte mới: `dba18f16f63959c95e4d2ff7d629fd1598137b432876e073cb7152b297aab0af`; giá trị cũ `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28` đã biến mất |
| 17 | `python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery/contract-registry.yaml').read_text(encoding='utf-8'); h = hashlib.sha256(pathlib.Path('docs/09-contracts/12-state-machines.md').read_bytes()).hexdigest(); m = re.search('id: CONTRACT-STATE-MACHINES[^@]*?current_revision: sha256:([0-9a-f]{64})[^@]*?source_sha256: ([0-9a-f]{64})', t); assert m is not None and m.group(1) == h and m.group(2) == h, h; assert '2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28' not in t, 'old hash must be gone'"` | 0 | Khớp cả hai trường registry và sha256 byte contract |
| 18 | `python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines.md').read_text(encoding='utf-8'); assert 'PUC-J-03' in t and 'YC-HT-I-04' in t, 'contract names both approved edges'"` | 0 | Contract có đủ cả hai cạnh PUC-J-03 và YC-HT-I-04 |
| 19 | `python -m pytest tests/unit/config tests/unit/storage tests/unit/statemachine -q -p no:cacheprovider` | 1 | `ERROR: file or directory not found: tests/unit/statemachine` (tests/unit/config và tests/unit/storage: 1100 passed, nhưng tests/unit/statemachine không tồn tại do CP-3B đặt test tại tests/integration/convergence/) |
| 20 | `python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | `679 passed, 398 subtests passed in 1.28s` |
| 21 | `git diff --check` | 0 | Clean whitespace |
| 22 | `python -m pytest tests/unit/config tests/unit/storage tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p no:cacheprovider` | 0 | `1125 passed, 239 subtests passed in 0.84s` |
| 23 | `python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | `679 passed, 398 subtests passed in 0.78s` |
| 24 | `python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider` | 0 | `118 passed in 0.11s` |
| 25 | `python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery/contract-registry.yaml').read_text(encoding='utf-8'); h = hashlib.sha256(pathlib.Path('docs/09-contracts/12-state-machines.md').read_bytes()).hexdigest(); m = re.search('id: CONTRACT-STATE-MACHINES[^@]*?current_revision: sha256:([0-9a-f]{64})[^@]*?source_sha256: ([0-9a-f]{64})', t); assert m is not None and m.group(1) == h and m.group(2) == h, h; assert '2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28' not in t, 'old hash must be gone'"` | 0 | sha256 current_revision và source_sha256 khớp byte contract; giá trị cũ đã biến mất |
| 26 | `python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines.md').read_text(encoding='utf-8'); assert 'PUC-J-03' in t and 'YC-HT-I-04' in t, 'contract names both approved edges'"` | 0 | contract nêu PUC-J-03 và YC-HT-I-04 |
| 27 | `git diff --check` | 0 | Clean whitespace |

## Quyết định

1. REVOKED vẫn không có cạnh thoát trong ACCOUNT_EDGES; chỉ tái kích hoạt qua reactivate_with_new_credential với credential version mới, không hồi sinh secret cũ.
2. transition và validate_transition vẫn từ chối DELETED; không có phương thức delete; record_cleanup_deleted là đường duy nhất ghi DELETED, đòi đủ bằng chứng và gọi update_location với evidence=None để không đè verification_evidence_ref.
3. Service phục hồi không probe, không chạm secret; chỉ nhận receipt đã có của chính tài khoản và kiểm tra revision.

## Mục mở

- OI-EXT-01: PENDING, nơi lưu cleanup_receipt_ref ngoài receipt của cleanup executor, không thêm cột hay migration.
- Control chạy tests/m2 trên PostgreSQL 18.6, Worker không chạy.
- Tách test sang tệp riêng là backlog.
- Đã giải quyết: Bước 19 cũ dùng đường dẫn `tests/unit/statemachine` không tồn tại; lệnh kiểm bắt buộc hiện hành của task dùng `tests/integration/convergence/test_cp3b_catalog_graphs.py` và `tests/integration/convergence/test_cp3b_source_parity.py` (cả hai đã có ở HEAD) và đã chạy ở bước 22 với kết quả đạt.
