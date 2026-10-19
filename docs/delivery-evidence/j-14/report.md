# Báo cáo bằng chứng J-14

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `f3ddb66ffe3256224644f56088ad3f73127c37cc`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-14 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider` (chạy khi fallback_policy.py là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `36 failed, 5 passed in 0.41s`
- Danh sách test PASSED kèm lý do vì stub đã định nghĩa kiểu/hằng/cấu trúc (5 passed):
  - `tests/unit/config/test_j_fallback_policy.py::test_module_docstring_declares_covered_ids` (docstring khai báo coveredIds: CT-AI-ROUTE-002)
  - `tests/unit/config/test_j_fallback_policy.py::test_source_does_not_mention_router_or_http_adapter` (không chứa ProviderRouter hay NineRouterHTTPAdapter)
  - `tests/unit/config/test_j_fallback_policy.py::test_source_imports_only_exception_classes_and_pure_modules` (chỉ import lớp ngoại lệ và module thuần, không import socket/time/random)
  - `tests/unit/config/test_j_fallback_policy.py::test_outcome_and_policy_are_frozen` (FallbackIntentPolicy và FallbackOutcome là frozen dataclass)
  - `tests/unit/config/test_j_fallback_policy.py::test_backoff_parameters_are_required` (chữ ký backoff_seconds và decide_fallback không có tham số mặc định)
- Danh sách nhóm test FAILED kèm thông điệp nguyên văn (36 failed):
  - 35 test failed do `NotImplementedError: J-14 <tên hàm>`:
    - 12 ca parametrize của `test_classify_failure_with_real_exception_classes` (RateLimitError, ProviderRateLimitExceededError, code=429, TimeoutError, ProviderTimeoutError, ProviderAuthenticationError, v.v.): `NotImplementedError: J-14 classify_failure`
    - `test_classify_failure_non_exception_object_is_unknown`: `NotImplementedError: J-14 classify_failure`
    - 17 test kiểm tra `decide_fallback` (`test_rate_limit_switches_to_first_fallback`, `test_timeout_switches_to_first_fallback`, `test_attempted_candidates_are_skipped`, `test_exhausted_fallback_waits`, `test_empty_fallback_order_waits`, `test_auth_and_unknown_wait_even_with_fallback`, `test_ai_not_required_continues_without_ai`, `test_snapshot_committed_without_permission_requires_new_revision`, `test_snapshot_committed_with_permission_switches`, `test_snapshot_not_committed_switches_regardless_of_permission`, `test_snapshot_committed_without_permission_still_waits_for_auth_and_when_exhausted`, `test_local_candidate_skipped_when_desktop_offline`, `test_local_candidate_chosen_when_desktop_online`, `test_provenance_required_is_constant_for_every_action`, `test_never_selects_candidate_outside_fallback_order`, `test_non_string_entries_in_fallback_order_are_ignored`, `test_same_input_gives_equal_outcome_and_inputs_not_mutated`): `NotImplementedError: J-14 decide_fallback`
    - 4 test kiểm tra `backoff_seconds` (`test_backoff_doubles_from_base_and_is_capped`, `test_backoff_huge_attempt_returns_cap_immediately`, `test_backoff_returns_int_and_is_deterministic`, `test_backoff_rejects_invalid_values`): `NotImplementedError: J-14 backoff_seconds`
    - 1 test kiểm tra đầu vào không hợp lệ `test_decide_fallback_rejects_invalid_inputs`: `NotImplementedError: J-14 decide_fallback`
  - 1 test failed do `Failed: DID NOT RAISE ValueError`:
    - `test_intent_policy_requires_bools` (stub FallbackIntentPolicy chưa có `__post_init__` kiểm tra kiểu bool)
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy khi fallback_policy.py là stub và fail hợp lệ do NotImplementedError và DID NOT RAISE đúng oracle.

## Thay đổi

- `src/controlplane/application/config_security/fallback_policy.py`: hiện thực classify_failure, FallbackIntentPolicy (kiểm tra kiểu bool nghiêm ngặt), FallbackOutcome (frozen dataclass), decide_fallback (chuyển fallback an toàn theo fallback_order, hỗ trợ intent policy sau snapshot, bỏ local khi offline, ưu tiên ai_required=False tiếp tục không cần AI, fail-closed khi auth/unknown), backoff_seconds (hàm luỹ thừa min(cap, base * 2 ** attempt) thuần tuý không sleep/random, bảo vệ tràn số bằng bit_length); chỉ import các lớp ngoại lệ RateLimitError, ProviderTimeoutError, ProviderAuthenticationError và ProviderRouteDecision; không import hay nhắc đến ProviderRouter/NineRouterHTTPAdapter.
- `tests/unit/config/test_j_fallback_policy.py`: 41 test bao phủ phân loại lỗi theo mã và lớp ngoại lệ, hành vi fallback switch/wait/continue_without_ai/new_output_revision_required, bảo toàn provenance_required hằng số ('model_ref','prompt_revision','config_revision'), tính bất biến của dataclass và tham số, thuật toán backoff luỹ thừa chặn trần an toàn, kiểm tra chặt chẽ đầu vào; docstring coveredIds: CT-AI-ROUTE-002.
- `docs/delivery-evidence/j-14/report.md`: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider` | 0 | `41 passed in 0.11s` |
| 2 | `git diff --check` | 0 | PASS (không output) |
| 3 | `python -c "import pathlib, re; t = pathlib.Path('src/controlplane/application/config_security/fallback_policy.py').read_text(encoding='utf-8'); assert not re.search('ProviderRouter|NineRouterHTTPAdapter', t)"` | 0 | PASS (assert qua) |
| 4 | `python -c "import pathlib; t = pathlib.Path('tests/unit/config/test_j_fallback_policy.py').read_text(encoding='utf-8'); assert 'coveredIds: CT-AI-ROUTE-002' in t"` | 0 | PASS (assert qua) |

## Quyết định mặc định (D8)

- D8-J-07: base và cap là tham số bắt buộc trong `backoff_seconds`, không có giá trị mặc định để tránh cấu hình ngầm ngoài hợp đồng.
- `snapshot_committed` chỉ chặn và yêu cầu `NEW_OUTPUT_REVISION_REQUIRED` khi resolver thực sự chuẩn bị chuyển sang provider khác (`SWITCH`); khi đã hết candidate trong `fallback_order` hoặc gặp lỗi không thể chuyển đổi (`AUTH`, `UNKNOWN`), hệ thống vẫn trả về `WAIT` fail-closed.
- `ai_required=False` thắng mọi điều kiện thất bại: luôn trả về `CONTINUE_WITHOUT_AI` để quy trình không phụ thuộc AI có thể tiếp tục mà không bị nghẽn.
- Giá trị `failure_kind` không nhận diện được (chuỗi lạ) được xử lý như lỗi không chuyển đổi và trả về `WAIT` fail-closed.
- Kiểm tra `code == 429` so sánh số nguyên chính xác bằng `==`; chuỗi `'429'` trả về `UNKNOWN` để bảo đảm tính chuẩn xác của mã lỗi HTTP.
- Thuật toán `backoff_seconds` trả về ngay `cap` khi `attempt >= cap.bit_length()` để phòng chống tính toán luỹ thừa số nguyên cực lớn gây cạn kiệt tài nguyên CPU/bộ nhớ.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: Danh mục thư viện đề xuất cố định phiên bản và cách dựng lại runtime.
- CP7: Tài nguyên thật (D5) qua secret broker.
- User checkpoint M2 (P8/P9): Đã triển khai và có Auditor PASS nhưng chưa ghi user checkpoint M2 nên chưa coi là user đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật hay I/O mạng.
- Tích hợp fallback policy vào tầng gọi `RoutedInvocation` thuộc phạm vi công việc của slice J-18.
- QUALITY-OPEN-003/004 chờ kết quả benchmark.
