# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: `M2-P1..P7B_ACCEPTED_CLOSED`; M2-P8/P9 `LOCKED`; M3/Phân hệ A `NOT AUTHORIZED`.
- Đã thêm [kiến trúc triển khai song song](./docs/parallel-delivery/README.md) ở trạng thái `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`. Bundle chỉ là docs/config và định nghĩa DAG, contract registry, ownership/lease, Orca worker protocol, merge queue, traceability, security/performance/recovery.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol review sau Astra round 18:
  1. Thẩm quyền chuyển đổi review & integration fail-closed: Bắt buộc review dispatch và review evidence đã xác thực (route cx/gpt-5.6-sol, harness Claude Code, exact HEAD) trước khi chuyển sang merge_queued; bắt buộc integration evidence với tất cả gates PASS và bằng chứng ACCEPT trước khi chuyển sang integrated; caller-supplied strings/booleans đơn lẻ không cấu thành thẩm quyền.
  2. Token chuyển đổi trạng thái không thể giả mạo (Unforgeable Transition Tokens): Triển khai _TransitionAuthToken với single-use consumption và kiểm tra frame nội bộ cho _authorized_transition_scope; ngăn chặn caller bên ngoài giả mạo context chuyển đổi trạng thái.
  3. Xác thực nghiêm ngặt mọi alias hiện diện (_extract_and_validate_alias): Kiểm tra tất cả alias key hiện diện, từ chối fail-closed khi gặp None, non-string, blank, whitespace-padded hoặc mâu thuẫn ngữ nghĩa trên toàn bộ implement và review.
  4. Bộ kiểm thử tự động đạt 289/289 tests PASS (100%); toàn bộ gates kiểm tra độc lập sẵn sàng.
- Đã khắc phục triệt để toàn bộ 4 phát hiện blocker từ Astra Lead review round 18 và các vòng Sol review trước đó:
  1. Chống vượt rào thẩm quyền vòng đời (Lifecycle & Authority Fail-Closed): Khóa chặt phương thức công khai `transition_task_state()`, bắt buộc mọi chuyển đổi vòng đời phải thông qua handler được ủy quyền (`create_dispatch`, `acknowledge_dispatch`, `start_running`, `handle_worker_done`, `handle_review_verdict`, `handle_integration_gates`, `resolve_blocker_and_replan`), thẩm quyền tác vụ phải là `granted` và có bằng chứng xác thực active dispatch, active lease và fencing token;
  2. Xác thực nghiêm ngặt mọi alias bằng chứng (Contradictory Evidence Aliases): Hàm `_extract_and_validate_alias()` kiểm tra mọi alias hiện diện phải đúng kiểu chuỗi, không rỗng và đồng nhất về mặt ngữ nghĩa trước khi trích xuất giá trị chính tắc, từ chối mâu thuẫn alias fail-closed trên cả implement và review;
  3. Bắt buộc định danh router raw chuỗi chính xác tuyệt đối (Strict End-to-End Raw Router Identity): Yêu cầu chuỗi raw chính xác `"9router"` tại toàn bộ các vị trí định tuyến (`route.provider`, `launch_requested.provider`, `launch_effective.provider`, `live_terminal_evidence.provider`, `usage_evidence.router`) mà không dùng chuẩn hóa khoảng trắng `.strip()` để biến chuỗi đệm thành hợp lệ;
  4. Chính sách byte chính tắc và tính tái lập băm attestation (Canonical-Byte Policy & Reproducible Git Blobs): Chuẩn hóa toàn bộ tệp trong bundle dùng ký tự xuống dòng LF đồng nhất với Git blob; loại bỏ triệt để sai lệch băm CRLF trên Windows; đảm bảo băm attestation trong báo cáo khớp 100% với Git blob khi clone mới;
  5. Bộ kiểm thử tự động đạt 274/274 tests PASS; toàn bộ gates kiểm tra độc lập sẵn sàng.
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
