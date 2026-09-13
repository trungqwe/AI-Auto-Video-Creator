# M1-P2 — Bằng chứng quan sát RED (Test-First)

**Ngày ghi nhận:** 13-09-2026  
**Lệnh thực thi:** `py -3.13 -m uv run --frozen pytest tests/m1/p2 -v`  
**Kết quả:** 4 FAILED, 3 PASSED trong 8.28s (exit code 1).

## Chi tiết các ca kiểm thử RED đúng Oracle

1. **`TST-M1-P2-001` (`test_worker_lifecycle.py`):**
   - **Mục tiêu:** Workflow chờ khi desktop worker offline và resume đúng stage khi online lại, không restart từ đầu.
   - **Hiện tượng RED:** `AssertionError: Expected WAITING_DESKTOP_ONLINE but got COMPLETED`.
   - **Lý do Oracle:** Workflow stub ban đầu chạy thẳng qua các stage mà không tạm dừng chờ signal Desktop Worker Online.

2. **`TST-M1-P2-003` (`test_activity_idempotency.py`):**
   - **Mục tiêu:** Worker mang generation cũ (thấp hơn generation active) bị từ chối với lỗi `STALE_GENERATION`.
   - **Hiện tượng RED:** `Failed: DID NOT RAISE WorkflowFailureError`.
   - **Lý do Oracle:** Activity stub ban đầu chưa có logic đối chiếu `worker_generation` với `active_generation` của hệ thống nên không ném lỗi.

3. **`TST-M1-P2-006` (`test_reconciliation_routing.py`):**
   - **Mục tiêu:** Khi gặp kết quả bên ngoài không xác định (`UNKNOWN_OUTCOME`), workflow không retry mù mà định tuyến vào `reconcile_external_outcome_activity`.
   - **Hiện tượng RED:** `AssertionError: assert 'DIRECT' == 'RECONCILED'`.
   - **Lý do Oracle:** Activity stub ban đầu chưa mô phỏng `UnknownExternalOutcomeError` và workflow chưa có cơ chế bắt lỗi để định tuyến vào activity đối soát.

4. **`TST-M1-P2-007` (`test_temporal_payload_boundaries.py`):**
   - **Mục tiêu:** Chặn secret token canary và binary blob lớn ngay tại boundary; không để lọt secret vào Temporal event history.
   - **Hiện tượng RED:** `Failed: DID NOT RAISE WorkflowFailureError`.
   - **Lý do Oracle:** Workflow và Activity stub ban đầu chưa có bộ lọc kiểm tra regex secret và kiểm tra dung lượng payload.

---

Bằng chứng RED này chứng minh các bài kiểm thử đã được thiết lập đúng với các invariant nghiệp vụ của M1-P2 trước khi bước vào cài đặt mã nguồn chính thức.
