# Báo cáo bằng chứng F-11

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 4fd21816ce8c657983f0e09d226209f381b13f5c
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-11 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider (chạy trên stub trung tính ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 92 failed, 3 passed, 2 errors in 0.85s
- Các dòng FAILED tiêu biểu:
  - FAILED tests/unit/render/test_f11_render_attempt.py::test_attempt_is_frozen_and_has_the_ct_rnd_004_fields: AssertionError: assert (None, None, None) == ('attempt-1',..., 'receipt-1')
  - FAILED tests/unit/render/test_f11_render_attempt.py::test_output_artifact_ref_must_be_a_relative_ref[C:/out/a.mp4]: Failed: DID NOT RAISE RenderAttemptRejected
  - FAILED tests/unit/render/test_f11_render_attempt.py::test_prepare_rejects_invalid_inputs[changes0]: Failed: DID NOT RAISE RenderAttemptRejected
  - FAILED tests/unit/render/test_f11_render_attempt.py::test_forbidden_edges_raise[PREPARED-succeed]: Failed: DID NOT RAISE ForbiddenTransitionError
  - FAILED tests/unit/render/test_f11_render_attempt.py::test_reconcile_succeeds_only_for_present_playable_matching_output: AssertionError: assert (<OperationState.PREPARED: 'PREPARED'>, 0) == (<OperationState.SUCCEEDED: 'SUCCEEDED'>, 3)
  - FAILED tests/unit/render/test_f11_render_attempt.py::test_command_spec_is_redacted_and_never_holds_argv: KeyError: 'kind'
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED do assertion hoặc DID NOT RAISE (và 2 fixture error do stub chưa định nghĩa transition_operation).

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 97 passed in 0.12s

## Thay đổi

- src/render/domain/render_attempt.py: ProbeEvidence, RenderAttempt frozen, RenderAttemptRejected, prepare_attempt, start_attempt, succeed_attempt, fail_attempt, mark_outcome_unknown, reconcile_attempt, can_retry_directly.
- 	ests/unit/render/test_f11_render_attempt.py: 23 hàm test, 97 test cases đã chạy (gồm các cases tham số hoá cho refs, inputs, edges, revisions, finish inputs, probe inconclusive/missing/corrupt, redaction).
- docs/delivery-evidence/f-11/report.md: báo cáo này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider | 0 | 97 passed in 0.12s |
| 2 | probe không còn marker STUB- | 0 | PASS (không AssertionError, không còn marker STUB-) |
| 3 | git diff --check | 0 | PASS (không có output, không lỗi định dạng diff) |
| 4 | probe tiếng Việt của report.md | 0 | PASS (tiếng Việt đầy đủ dấu, không có ký tự thay thế) |

## Quyết định mặc định (D8)

1. ProbeEvidence là DTO F-local, GIẢ ĐỊNH: expected_sha256 do I/G cung cấp từ bản ghi đã verify, hội tụ qua CONV-F-05 và CONV-F-12.
2. Probe của output khác ref hoặc thiếu evidence_ref, exists/playable/sha chưa rõ thì không kết luận: giữ nguyên attempt OUTCOME_UNKNOWN, revision không đổi.
3. Thiếu file hoặc playable False hoặc sha256 lệch expected_sha256 thì FAILED với mã reconcile_output_missing hoặc reconcile_output_corrupt.
4. receipt_ref bắt buộc khi prepare_attempt, GIẢ ĐỊNH lấy từ operation receipt của G.
5. Redact cục bộ trong mô-đun (không import controlplane.infrastructure): secret khai báo qua secret_values, mẫu gán secret, Bearer, khoá riêng, đường dẫn tuyệt đối, cắt 500 ký tự; giới hạn: secret trần không khai báo và không có mẫu gán thì không phát hiện được.
6. command_spec lưu dạng JSON đã redact từ RenderCommandSpec.to_dict, không lưu argv.
7. Metrics CPU/GPU là ánh xạ khoá snake_case giá trị số không âm, tên khoá là GIẢ ĐỊNH.
8. can_retry_directly chỉ True với FAILED, retry luôn là attempt mới với output_artifact_ref mới.
9. Không dựng máy trạng thái riêng, chỉ dùng transition_operation.

## Ánh xạ phản ví dụ

- Retry trực tiếp từ OUTCOME_UNKNOWN -> 	est_outcome_unknown_is_never_retried_directly, 	est_forbidden_edges_raise.
- Attempt mới ghi đè output cũ -> 	est_new_attempt_gets_its_own_output_and_never_overwrites_the_old_one.
- Terminal mở lại STARTED -> 	est_forbidden_edges_raise.
- Lỗi chứa canary -> 	est_error_and_warning_text_is_redacted_in_every_view, 	est_declared_secret_values_are_removed_wherever_they_appear, 	est_command_spec_is_redacted_and_never_holds_argv.
- Render thành công bị coi là video hoàn thành -> 	est_attempt_has_no_completed_field_or_function.

## coveredIds

- CT-RND-004, CT-STATE-011, TST-SEC-INV-012.

## Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-007, ROADMAP-OPEN-009, TECH-OPEN-012 (ffmpeg, xác minh ở CP7).
- USER-CKPT-D9-D10.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Không chạy ffmpeg thật, không gọi dịch vụ thật.
