# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: `M2-P1..P7B_ACCEPTED_CLOSED`; M2-P8/P9 `LOCKED`; M3/Phân hệ A `NOT AUTHORIZED`.
- Đã thêm [kiến trúc triển khai song song](./docs/parallel-delivery/README.md) ở trạng thái `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`. Bundle chỉ là docs/config và định nghĩa DAG, contract registry, ownership/lease, Orca worker protocol, merge queue, traceability, security/performance/recovery.
- Đã khắc phục triệt để toàn bộ 21 bypass độc lập từ Sol review, 3 boundary probe, toàn bộ các phát hiện Sol Round 3, toàn bộ 9 blocker Sol Round 4, toàn bộ 12 blocker Sol Round 5, toàn bộ 7 blocker Sol Round 6, toàn bộ 5 blocker Sol Round 7, và toàn bộ 3 blocker Sol Round 8:
  1. `set_task_state` cấm tuyệt đối tái mở trạng thái terminal (`integrated`, `cancelled`, `stopped`) hoặc tua ngược `review`/`merge_queued` về `planned`; toàn bộ đột biến trạng thái tác vụ được thực hiện nguyên tử qua `_task_state_lock`;
  2. Xác thực attestation freshness tuân thủ đúng cấu trúc cây Git DAG cho phép (Direct HEAD hoặc Parent-plus-wrapper với wrapper tại HEAD), loại bỏ hoàn toàn quan hệ thuộc tập hợp `{HEAD, HEAD^}` lỏng lẻo;
  3. Đột biến phức hợp khi `create_dispatch` là một giao dịch nguyên tử đa tiến trình duy nhất trên `SharedOrcaExecutionRegistry` qua `register_dispatch_and_orca_task`, tự động rollback sạch sẽ và loại bỏ triệt để orphan dispatch binding khi có tranh chấp;
  4. Bộ kiểm thử tự động đạt 165/165 tests PASS; `validate.py --audit` và `--release` PASS 100%.
- Orca là execution/communication plane. Dely chỉ quản lý implement → independent review bên trong task đã có authority. Dely implement: Codex CLI / `ag/gemini-3.8-flash-high` / `high`; review: Claude Code / `cx/gpt-5.6-sol-high` / `high`. Supreme audit `cx/gpt-6-astra-medium` / `medium` nằm ngoài Dely và chỉ cho audit cực khó.
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
