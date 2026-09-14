# HANDOFF

- Đã quyết định: M1, M2-P0, M2-P1, M2-P2 và M2-P3 là `ACCEPTED / CLOSED`. M2-P4 ở `M2-P4_PLAN_READY_FOR_REVIEW`; chỉ planning đã được ủy quyền, Behavioral RED và implementation chưa được ủy quyền. M2-P5..P7, M3 và Module A bị khóa.
- Kế hoạch P4 khóa năm state machine thuần theo `CT-STATE-008..012`, mapper `CT-API-007`, `CT-CMN-005` revision và `FORBIDDEN_TRANSITION`; catalogue RED đề xuất cố định đúng 9 identity trong `implementation-plan.md`.
- Hợp đồng P4 đã đóng ba mơ hồ: Operation `OUTCOME_UNKNOWN → SUCCEEDED | FAILED` chỉ với reconciliation evidence; reconcile inconclusive giữ unknown; `SUCCEEDED`/`FAILED` terminal. Job cho phép `ACTIVE` hoặc `WAITING → READY_FOR_COMPLETION`; Batch cho phép `RUNNING` hoặc `WAITING_CAPABILITY` → terminal. Không có edge bổ sung.
- Không tự phát minh cạnh Stage Run: `CT-STATE-008` không định nghĩa lối ra từ `WAITING_*`/`FAILED_RETRYABLE`; `OUTCOME_UNKNOWN` chỉ reconcile. Artifact chỉ có cạnh `VERIFIED → MISSING` sau later verification và cleanup chain contract. Mapper waiting chỉ dùng `wait_reason` structured của `CT-API-007`, không timestamp/progress/UI.
- P4 tương lai chỉ được phép chạm `domain/statemachine/**`, mapper projection thuần, test P4 và profile/synthesizer/evidence P4 sau authorization. Cấm HTTP/SSE/UI/Temporal/persistence/migration/P5+/M3/Module A và mọi thay đổi P1-P3 đã accept.
- Tệp cần đọc tiếp: `docs/milestones/m2-control-plane/spec.md`, `implementation-plan.md`, `docs/09-contracts/12-state-machines.md`, `docs/09-contracts/01-control-api-and-stream.md`, `docs/09-contracts/00-common-contract.md`, `docs/12-pre-code-checklist.md`.
- Điểm tiếp tục: independent audit P4 plan. Không tạo test/source/evidence RED, không mở P5+/M3/Module A.
