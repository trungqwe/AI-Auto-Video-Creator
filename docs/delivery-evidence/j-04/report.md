# Báo cáo bằng chứng J-04

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `2f4646097605e31871a73832e6fd0a7cbda289d3`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-04 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider` (chạy khi status_graph.py là stub)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `67 failed, 1 passed in 0.41s`
- Các test FAILED kèm thông điệp nguyên văn (NotImplementedError / AssertionError):
  - `tests/unit/config/test_j_status_graph.py::test_edge_sets_are_exact_frozensets_of_five FAILED (AssertionError: assert (True and 0 == 5))`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[DRAFT-DRAFT] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[DRAFT-PUBLISHED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[DRAFT-SUPERSEDED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[DRAFT-INVALIDATED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[PUBLISHED-DRAFT] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[PUBLISHED-PUBLISHED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[PUBLISHED-SUPERSEDED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[PUBLISHED-INVALIDATED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[SUPERSEDED-DRAFT] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[SUPERSEDED-PUBLISHED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[SUPERSEDED-SUPERSEDED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[SUPERSEDED-INVALIDATED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[INVALIDATED-DRAFT] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[INVALIDATED-PUBLISHED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[INVALIDATED-SUPERSEDED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_config_pair_is_allowed_only_on_declared_edges[INVALIDATED-INVALIDATED] FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[ENABLED-ENABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[ENABLED-DISABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[ENABLED-DEGRADED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[ENABLED-INVALID] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[ENABLED-REVOKED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DISABLED-ENABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DISABLED-DISABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DISABLED-DEGRADED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DISABLED-INVALID] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DISABLED-REVOKED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DEGRADED-ENABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DEGRADED-DISABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DEGRADED-DEGRADED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DEGRADED-INVALID] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[DEGRADED-REVOKED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[INVALID-ENABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[INVALID-DISABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[INVALID-DEGRADED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[INVALID-INVALID] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[INVALID-REVOKED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[REVOKED-ENABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[REVOKED-DISABLED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[REVOKED-DEGRADED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[REVOKED-INVALID] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_pair_is_allowed_only_on_declared_edges[REVOKED-REVOKED] FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_config_graph_matches_application_allowed_transition[...] FAILED (NotImplementedError: J-04 can_transition_config)` (16 cặp)
  - `tests/unit/config/test_j_status_graph.py::test_config_counterexamples_are_rejected FAILED (NotImplementedError: J-04 can_transition_config)`
  - `tests/unit/config/test_j_status_graph.py::test_account_counterexamples_are_rejected FAILED (NotImplementedError: J-04 can_transition_account)`
  - `tests/unit/config/test_j_status_graph.py::test_account_status_view_is_lowercase_value[...] FAILED (NotImplementedError: J-04 account_status_view)` (5 trạng thái)
  - `tests/unit/config/test_j_status_graph.py::test_account_status_view_matches_projection_statuses FAILED (NotImplementedError: J-04 account_status_view)`
  - `tests/unit/config/test_j_status_graph.py::test_account_status_view_rejects_unknown_status FAILED (NotImplementedError: J-04 account_status_view)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED hợp lệ do NotImplementedError và AssertionError.

## Thay đổi

- `src/controlplane/domain/config_security/status_graph.py`: CONFIG_REVISION_EDGES (frozenset 5 cạnh theo CT-STATE-013), ExternalAccountStatus (StrEnum gồm ENABLED, DISABLED, DEGRADED, INVALID, REVOKED), ACCOUNT_EDGES (frozenset 5 cạnh theo CT-STATE-013), can_transition_config, can_transition_account, require_config_transition, require_account_transition (raise ForbiddenTransitionError mang đúng aggregate_type config_revision hoặc external_account), và account_status_view (trả chuỗi chữ thường theo CT-ACC-001).
- `tests/unit/config/test_j_status_graph.py`: test kiểm tra toàn bộ thành viên enum, kích thước frozenset 5 cạnh, tham số hóa kiểm tra mọi cặp trạng thái cho phép/từ chối, so khớp _allowed_transition của controlplane.application.config_security, kiểm tra các phản ví dụ bị từ chối, kiểm tra account_status_view khớp ACCOUNT_STATUSES; docstring chứa coveredIds: CT-STATE-013, CT-ACC-001.
- `docs/delivery-evidence/j-04/report.md`: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider` | 0 | `68 passed in 0.09s` |
| 2 | `git diff --check` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. D8-J-09: chỉ các cạnh văn bản CT-STATE-013; self-transition cấm; INVALIDATED terminal; DEGRADED, INVALID, REVOKED không có cạnh thoát; REVOKED chỉ kích hoạt lại bằng credential version mới (J-06).
2. require_* nhận (current, requested, current_revision) khớp chữ ký ForbiddenTransitionError mà controlplane.application.config_security đang gọi.
3. account_status_view dùng ExternalAccountStatus(status).value.lower(), giá trị lạ raise ValueError.
4. status_graph giữ cục bộ trong J, chưa đăng ký vào controlplane.domain.statemachine (YC-HT-J-04), application.config_security chưa được nối vào module này vì ngoài owned paths.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt
- PUC-J-03 (cạnh phục hồi cho DEGRADED/INVALID cần quyết định của Control trước M5)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, lockfile, fixture hay binding.
- Không gọi dịch vụ thật.