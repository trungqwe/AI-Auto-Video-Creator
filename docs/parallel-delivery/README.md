# Kiến trúc triển khai song song có kiểm soát

> **Trạng thái:** `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`  
> **Ngày lập:** 28-09-2026  
> **Phạm vi:** cơ chế lập kế hoạch, điều phối, giao tiếp, tích hợp và bằng chứng cho công việc đã được cấp quyền; không thay đổi kiến trúc sản phẩm hoặc trạng thái milestone.

## 1. Mục đích

Bộ tài liệu này biến quy tắc triển khai song song thành một control plane có thể kiểm tra bằng máy. Nó bổ sung cho roadmap và milestone plan, không thay thế chúng. Mục tiêu là cho phép nhiều đơn vị công việc độc lập tiến hành đồng thời mà vẫn giữ:

- một nguồn sự thật cho authority và trạng thái;
- một writer cho mỗi path, aggregate, migration và contract revision;
- dependency, contract, lock và evidence có định danh;
- test-first với RED phân biệt được implementation sai;
- merge tuần tự trên candidate đã pin;
- fail-closed, phục hồi được và không sửa hồi tố evidence đã accepted.

Thiết kế này không tự kích hoạt task nào. Mọi task thực thi phải được tạo trong plan milestone có thẩm quyền và phải qua checkpoint riêng.

## 2. Giới hạn authority hiện hành

- M1: `ACCEPTED / CLOSED`.
- M2: `M2-P1..P7B_ACCEPTED_CLOSED`.
- M2-P8 và M2-P9: `LOCKED`; không được bắt đầu Behavioral RED hoặc implementation từ tài liệu này.
- M3 và Phân hệ A: `NOT AUTHORIZED`.
- Các node M3–M7 trong [task DAG](./task-dag.yaml) chỉ là template thiết kế `future_template`, không phải backlog đang hoạt động.
- Toolchain M2 vẫn do [`toolchain-lock.md`](../milestones/m2-control-plane/toolchain-lock.md) khóa; không có pin nào trong bundle này được dùng để thay nó.
- Accepted/rejected evidence lịch sử giữ bất biến.

## 3. Nguồn sự thật và thứ tự ưu tiên

1. [`HANDOFF.md`](../../HANDOFF.md) cho điểm tiếp tục ngắn.
2. [`docs/12-pre-code-checklist.md`](../12-pre-code-checklist.md) cho authority hiện hành.
3. [`docs/11-roadmap.md`](../11-roadmap.md) cho milestone, dependency và user checkpoint.
4. Milestone spec/plan/toolchain lock đang hoạt động cho hành vi và phạm vi file.
5. Contracts, ADR, test strategy và system map cho ranh giới kỹ thuật.
6. Bundle này cho scheduling, lease, protocol và merge control.

Khi có mâu thuẫn, dừng node bị ảnh hưởng ở `needs_replan` hoặc `stopped`; không chọn tài liệu thuận tiện hơn.

## 4. Bản đồ artifact

| Tệp | Vai trò | Máy đọc được |
|---|---|---:|
| [`operating-model.md`](./operating-model.md) | Mô hình điều hành, wave, role, Dely/Orca và model routing | Một phần |
| [`task-dag.yaml`](./task-dag.yaml) | Schema, node mẫu, dependency, authority, wave và acceptance | Có |
| [`contract-registry.yaml`](./contract-registry.yaml) | Contract revision, owner, consumer và compatibility window | Có |
| [`ownership-and-locks.yaml`](./ownership-and-locks.yaml) | Module owner, path owner, resource lock và lease/fencing | Có |
| [`protocol.md`](./protocol.md) | Máy trạng thái task/worker, heartbeat/check/ask/escalation/done | Một phần |
| [`merge-and-integration.md`](./merge-and-integration.md) | Worktree/branch, merge queue và integration gates | Một phần |
| [`traceability.md`](./traceability.md) | Mục tiêu → FR/QR → module → contract/invariant → gate | Một phần |
| [`security-performance-recovery.md`](./security-performance-recovery.md) | Guardrail bảo mật, hiệu năng, evidence và phục hồi | Một phần |

YAML dùng YAML 1.2, UTF-8 không BOM. Giá trị enum và identifier dùng tiếng Anh; mô tả cho người dùng dùng tiếng Việt.

## 5. Quy tắc kích hoạt tối thiểu

Một node chỉ được chuyển từ `planned` hoặc `waiting_dependency` sang `ready` khi tất cả điều kiện đều đúng:

```text
authority_granted
AND dependencies_accepted
AND contract_revisions_frozen
AND owned_paths_disjoint
AND resource_locks_available
AND runtime_prerequisites_available
AND acceptance_oracle_ready
```

`authority_granted` là điều kiện độc lập, không thể suy từ việc dependency đã xong. Node thiếu một điều kiện phải chờ hoặc dừng, không được thu hẹp/đổi phạm vi ngầm.

## 6. Rollback và khôi phục thiết kế

Bản sao trước thí nghiệm nằm tại:

`D:/AI_SETUP/backups/AI-Auto-Video-Creator/20260928-175542`

Đây là tham chiếu khôi phục tài liệu/config, không phải evidence rằng restore sản phẩm hoặc G05 đã PASS. Trước khi dùng phải xác minh checksum, provenance và phạm vi; không chép đè accepted evidence hoặc worktree có thay đổi chưa bảo toàn.

## 7. Điều kiện đưa thiết kế vào vận hành

Cần một user checkpoint riêng để:

1. duyệt schema và validator;
2. chọn một work package đã có authority để pilot;
3. cấp Orca run/dispatch/commit authority cụ thể;
4. chứng minh lock conflict, worker loss và merge-queue recovery trên fixture;
5. audit kết quả pilot;
6. quyết định giữ, sửa hoặc loại bỏ thí nghiệm.

Không điều nào ở trên đã được bundle này chứng minh runtime.
