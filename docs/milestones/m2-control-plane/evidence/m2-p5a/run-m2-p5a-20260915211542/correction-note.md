# M2-P5A RED hardening correction

Run này tiếp tục từ checkpoint `4ac207e39bad22cdd0c76505b43003fea10c22d8` và chỉ hiệu chỉnh exact five RED oracles. P5A-001 giờ persist payload tương đương ở scope riêng, xác nhận cùng `request_hash` qua production create path, đồng thời persist payload thay đổi và xác nhận hash khác biệt bền vững trong database. P5A-005 thêm rollback probe độc lập: publish và outbox mutation xảy ra trên cùng active P1 `SqlUnitOfWork.connection`, sau đó exception trước UoW exit phải rollback cả hai.

Không thay đổi production implementation, migration `0004`, P5B/P6+/M3/Module A, pyproject hoặc uv lock. Run `run-m2-p5a-20260915205019` được giữ nguyên và không bị rewrite. `source_commit_sha` không được tự gán ở RED stage; run này giữ plan checkpoint, red parent checkpoint, oracle hash và run ID. Exact five testcase identities không đổi. Lifecycle cuối cùng vẫn là `M2-P5A_RED_READY_FOR_REVIEW`; independent audit vẫn bắt buộc.
