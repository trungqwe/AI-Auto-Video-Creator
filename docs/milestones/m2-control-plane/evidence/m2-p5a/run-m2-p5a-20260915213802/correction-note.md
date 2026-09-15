# M2-P5A RED immutable-race oracle correction

Run này tiếp tục từ `b492b72dd41fc51d08da0bb2ee81badc8d1286a6` và chỉ sửa lỗi green-capability trong P5A-005. Assertion hậu race giờ kiểm tra rõ `revision == 2`, `status == PUBLISHED` và snapshot immutable theo tên trường (`config_revision_id`, workspace/scope facts, `config_revision_number`, content hash và canonical payload). `_revision_snapshot` độc lập, đầy đủ mọi dataclass field, vẫn được giữ nguyên cho các probe forbidden/stale zero-mutation.

Không thay đổi production implementation, migration `0004`, P5B/P6+/M3/Module A, pyproject hoặc uv lock. Các evidence run trước không bị rewrite; exact five testcase identities không đổi. `source_commit_sha` không được tự gán ở RED stage. Lifecycle cuối cùng vẫn là `M2-P5A_RED_READY_FOR_REVIEW`; independent audit vẫn bắt buộc.
