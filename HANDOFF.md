# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: `M2-P1..P7B_ACCEPTED_CLOSED`; M2-P8/P9 `LOCKED`; M3/Phân hệ A `NOT AUTHORIZED`.
- Đã thêm [kiến trúc triển khai song song](./docs/parallel-delivery/README.md) ở trạng thái `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`. Bundle chỉ là docs/config và định nghĩa DAG, contract registry, ownership/lease, Orca worker protocol, merge queue, traceability, security/performance/recovery.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol-Lead review trên 36092d0:
  1. Hạn chế quyền phát hành bằng chứng độc lập qua capability (Restricted Evidence Issuance): Các phương thức `issue_review_evidence()` và `issue_integration_evidence()` bắt buộc phải có capability xác thực độc lập (`ReviewerCapability` hoặc `ControlCapability`) có chữ ký HMAC không thể giả mạo; caller thông thường từ adapter tuyệt đối không thể tự cấp phát bằng chứng có chữ ký nội bộ để đẩy trạng thái qua `merge_queued` hay `integrated`.
  2. Bảo vệ ranh giới thực thi vòng đời bằng capability độc lập (Lifecycle Context Boundary Protection): Ranh giới `_internal_lifecycle_execution` bắt buộc phải có `ControlCapability` hoặc `ReviewerCapability` hợp lệ đã được xác thực; caller thông thường không thể xâm nhập ranh giới nội bộ, không thể mint token để chuyển trạng thái từ `blocked` sang `ready`.
  3. Bắt buộc một định danh canonical duy nhất cho backend provider và model (Exact Canonical Backend Identities): Loại bỏ toàn bộ alias phi chính tắc (`9router/google`, `9router/openai`, `gemini-3.8-flash-high`, `gpt-5.6-sol`), chỉ chấp nhận duy nhất một định danh canonical cho mỗi phase (`implement`: provider `google`, model `ag/gemini-3.8-flash-high`; `review`: provider `openai`, model `cx/gpt-5.6-sol`); mọi biến thể khác đều bị từ chối fail-closed.
  4. Bộ kiểm thử tự động đạt 321/321 tests PASS (100%), bổ sung 8 fixtures trong `TestSolLeadReview36092d0Remediation` tái hiện và kiểm chứng trọn vẹn 3 counterexamples và controls; toàn bộ project gates PASS.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol-Lead review sau da26686:
  1. Thẩm quyền bằng chứng và chống giả mạo/stale/replay (Evidence Provenance & Freshness): Triển khai `EvidenceAuthority` mang bí mật HMAC nội bộ (`_secret`), cấp phát bằng chứng `ReviewEvidence` và `IntegrationEvidence` kèm chữ ký unforgeable, kiểm tra cửa sổ freshness 300s (chặn bằng chứng năm 2000), theo dõi bằng chứng đã tiêu thụ để ngăn replay (`_consumed_evidence_ids`). Xác thực hoàn tất trước mọi thao tác lưu trữ hay chuyển đổi trạng thái với zero side effects.
  2. Năng lực chuyển đổi vòng đời không thể giả mạo (Unforgeable Lifecycle Capabilities): Đóng hoàn toàn các bề mặt `_mint_transition_token` và `_authorized_transition_scope` trước caller bên ngoài bằng contextmanager `_internal_lifecycle_execution`. Bọc toàn bộ các lifecycle handler hợp lệ (`acknowledge_dispatch`, `start_running`, `create_dispatch`, `handle_worker_done`, `handle_harness_failure`, `handle_review_verdict`, `handle_integration_gates`, `resolve_blocker_and_replan`). Theo dõi giải phóng lease và dàn xếp dispatch có thẩm quyền (`_authoritatively_settled_dispatches`, `_authoritatively_released_tasks`), ngăn chặn thao tác settlement/release ngoài luồng, cấm dùng lại token (`_consumed_transition_tokens`).
  3. Bắt buộc raw canonical spelling tuyệt đối cho tất cả alias định danh: Loại bỏ `.lower()` trước khi xác thực, bắt buộc định danh raw canonical chính xác tuyệt đối trên toàn bộ các vị trí: `effort` (`high`), `provider` (`9router`), `harness` (`Codex CLI` / `Claude Code`), `model` (`ag/gemini-3.8-flash-high` / `cx/gpt-5.6-sol`), `backend_provider` (`google` cho implement, `openai` cho review). Bất kỳ chuỗi đệm khoảng trắng, rỗng, không phải chuỗi, sai hoa thường hoặc mâu thuẫn đều bị từ chối fail-closed.
  4. Bộ kiểm thử tự động đạt 313/313 tests PASS (>297 tests theo yêu cầu); toàn bộ gates kiểm tra độc lập sẵn sàng.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol-Lead review sau 43c96aa:
  1. Thẩm quyền bằng chứng review & integration fail-closed: Từ chối plain caller dicts/strings/booleans; bắt buộc `ReviewEvidence` và `IntegrationEvidence` có xuất xứ kiểm chứng, băm SHA-256; bắt buộc `base_commit` khớp chính xác `approved_base_commit`; bắt buộc `gate_results` không rỗng và có đầy đủ 11 cổng bắt buộc thuộc `MANDATORY_INTEGRATION_GATES`.
  2. Token capability không thể giả mạo & xóa bỏ hoàn toàn stack frame inspection: Loại bỏ toàn bộ `sys._getframe()`; triển khai capability token mang chữ ký HMAC nội bộ ràng buộc `task_id`, `from_state`, `to_state`, `handler`; bắt buộc dispatch phải settle trong registry và toàn bộ lease phải release trước khi chuyển sang `review`; bảo đảm zero side effects khi chuyển đổi thất bại.
  3. Xác thực unpadded cho dataclass identities: Kiểm tra trực tiếp các trường raw trên `LiveTerminalEvidence` và `UsageEvidence` trước bất kỳ bước chuẩn hóa hay so sánh nào; từ chối fail-closed mọi khoảng trắng đệm.
  4. Bộ kiểm thử tự động đạt 297/297 tests PASS (100%); toàn bộ gates kiểm tra độc lập sẵn sàng.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol review sau Astra round 18:
  1. Thẩm quyền chuyển đổi review & integration fail-closed: Bắt buộc review dispatch và review evidence đã xác thực (route cx/gpt-5.6-sol, harness Claude Code, exact HEAD) trước khi chuyển sang merge_queued; bắt buộc integration evidence với tất cả gates PASS và bằng chứng ACCEPT trước khi chuyển sang integrated; caller-supplied strings/booleans đơn lẻ không cấu thành thẩm quyền.
  2. Token chuyển đổi trạng thái không thể giả mạo (Unforgeable Transition Tokens): Triển khai _TransitionAuthToken với single-use consumption và kiểm tra frame nội bộ cho _authorized_transition_scope; ngăn chặn caller bên ngoài giả mạo context chuyển đổi trạng thái.
  3. Xác thực nghiêm ngặt mọi alias hiện diện (_extract_and_validate_alias): Kiểm tra tất cả alias key hiện diện, từ chối fail-closed khi gặp None, non-string, blank, whitespace-padded hoặc mâu thuẫn ngữ nghĩa trên toàn bộ implement và review.
  4. Bộ kiểm thử tự động đạt 289/289 tests PASS (100%); toàn bộ gates kiểm tra độc lập sẵn sàng.
- Orca là execution/communication plane. Dely chỉ quản lý implement → independent review bên trong task đã có authority. Dely implement: Codex CLI / `ag/gemini-3.8-flash-high` / `high`; review: Claude Code / `cx/gpt-5.6-sol` / `high`. Supreme audit `cx/gpt-6-astra-medium` / `medium` nằm ngoài Dely và chỉ cho audit cực khó.
- Rollback reference trước thí nghiệm: `D:/AI_SETUP/backups/AI-Auto-Video-Creator/20260928-175542`; đây không phải bằng chứng G05 PASS.

## Evidence bất biến

- P7B accepted source/tooling: `c44214ad027986a0db7cb9d8e221590f232a0036`; accepted GREEN: `run-m2-p7b-green-20260917040648`; accepted RED: `run-m2-p7b-red-20260917002633`.
- Candidate GREEN lịch sử bị từ chối `run-m2-p7b-green-20260917024918` giữ nguyên. P7B oracle SHA-256 `d83d0f2d808f1b0067d5288ea131ded24d8fc46a16462b5254fd4167f7425738`; P7A oracle SHA-256 `63151da21b07c3dd92c5b4a7acc0d4f952f188ee2425a52c9d3ac8d34eb61035`.
- Migration `0008`, ngoại lệ đúng thân P3 `append()` và compatibility đúng thân P7A H16 tiếp tục là một phần accepted P7B; không sửa hoặc chạy lại evidence chỉ vì checkpoint docs/config này.

## Chưa quyết định

- Chưa kích hoạt runtime pilot cho scheduler/lease/merge queue; cần user checkpoint riêng, validator được review và một work package đã có authority.
- Không có quyết định mới cho sample size, scale dataset, output profile, word-timing tolerance, retry/concurrency, retention, provider/model hoặc các open item sản phẩm.

## Đọc tiếp

1. `docs/12-pre-code-checklist.md`
2. `docs/11-roadmap.md`
3. `docs/parallel-delivery/README.md`
4. `docs/milestones/m2-control-plane/implementation-plan.md`
5. `docs/milestones/m2-control-plane/toolchain-lock.md`

## Điểm tiếp tục

Chờ checkpoint thiết kế/independent review riêng cho P8 hoặc checkpoint riêng để pilot kiến trúc parallel delivery trên scope đã được cấp quyền. Không bắt đầu P8 Behavioral RED, P8/P9 implementation, M3 hoặc Phân hệ A từ bundle đề xuất này.
