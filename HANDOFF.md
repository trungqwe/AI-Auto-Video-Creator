# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: `M2-P1..P7B_ACCEPTED_CLOSED`; M2-P8/P9 `LOCKED`; M3/Phân hệ A `NOT AUTHORIZED`.
- Đã thêm [kiến trúc triển khai song song](./docs/parallel-delivery/README.md) ở trạng thái `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`. Bundle chỉ là docs/config và định nghĩa DAG, contract registry, ownership/lease, Orca worker protocol, merge queue, traceability, security/performance/recovery.
- Đã khắc phục triệt để toàn bộ các phát hiện từ Astra audit và các vòng Sol review (Round 3 đến Round 18):
  1. Yêu cầu định danh router raw chính xác tuyệt đối "9router" cho mọi alias (`router`, `route_provider`, `source`) và `UsageEvidence.router`, xóa bỏ hoàn toàn bước chuẩn hóa khoảng trắng `.strip()` trước khi so sánh;
  2. Khóa chặt fail-closed mọi trường hợp router có khoảng trắng đệm (đầu, cuối, hai phía, tab, newline, carriage return) và agreeing/mixed padded aliases;
  3. Bắt buộc khai báo rõ ràng định danh router trong `usage_evidence` (qua `router`, `route_provider` hoặc `source`), cấm fallback ngầm định sang "9router", loại bỏ triệt để counterexample chấp nhận bản ghi sử dụng không chứng minh được router;
  4. Khóa chặt router identity chính xác "9router" cho cả implement và review, từ chối fail-closed `Antigravity native`, `direct-vendor` và nhà cung cấp backend/ngoại lai;
  5. Từ chối fail-closed trước mọi tác động phụ đối với trường router bị thiếu, rỗng, sai kiểu dữ liệu, mâu thuẫn alias hoặc khóa router ngoại lai;
  6. Ràng buộc tương hỗ tuyệt đối giữa explicit usage router với `route.provider`, cả 2 bản đồ launch evidence, `live_terminal_evidence.provider` và phase;
  7. Bắt buộc cặp bằng chứng khởi chạy `launch_requested` và `launch_effective` là machine-readable mapping trên mọi envelope, chứa đầy đủ exact harness, provider ("9router"), model và effort ("high"), loại bỏ toàn bộ counterexample thiếu launch evidence hoặc launch evidence sai lệch (`Antigravity native`, `direct-vendor`, `wrong-model`);
  8. Ràng buộc tương hỗ tuyệt đối giữa requested/effective launch evidence với nhau và với `route`, `live_terminal_evidence`, `usage_evidence` và `phase`;
  9. Tái cấu trúc thứ tự kiểm tra fail-before-side-effect: toàn bộ kiểm tra pure `dispatch_origin` và `execution_envelope` chạy trước bất kỳ side effect hay purge/deactivate lease nào trong `create_dispatch()`, bảo đảm `RoutingEvidenceError` thắng và zero side effects khi envelope sai kết hợp lease hết hạn;
  10. Bắt buộc định danh `orca_task_id` trong `ExecutionEnvelope` và ràng buộc với đối số `create_dispatch()` trước mọi tác động phụ;
  11. Yêu cầu bắt buộc các neo định danh `delivery_task_id`, `dispatch_id` trên cả `LiveTerminalEvidence` và `UsageEvidence`, và trường `effort == "high"` trên `LiveTerminalEvidence`, từ chối fail-closed khi thiếu trường;
  12. Khóa chính xác định danh backend model theo phase (`ag/gemini-3.8-flash-high` / `gemini-3.8-flash-high` cho implement, `cx/gpt-5.6-sol` / `gpt-5.6-sol` cho review), loại bỏ hoàn toàn kiểm tra substring và từ chối mọi foreign alias;
  13. Thực thi fail-closed dispatch origin và execution envelope trước mọi tác động phụ; bắt buộc origin "dely dispatch", loại bỏ counterexample dispatch_without_origin_or_envelope_accepted = ctx-probe;
  14. Xử lý harness failure theo định danh trước (identity-first fail-closed), chỉ thu hồi lease của dispatch đã xác thực;
  15. Bộ kiểm thử tự động đạt 252/252 tests PASS; toàn bộ gates kiểm tra độc lập sẵn sàng.
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
