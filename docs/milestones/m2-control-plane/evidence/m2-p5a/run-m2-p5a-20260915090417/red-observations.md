# Quan sát Behavioral RED M2-P5A

Nguồn checkpoint: `a0b724548c22996e827bdbf712e395f3e7b40523`.

Tất cả fixture đã kết nối PostgreSQL thật, tạo database function-scoped, áp dụng production migrations `0001`–`0003`, và teardown thành công trước khi từng oracle chạm seam P5A. Do đó không có failure setup, import, syntax, DSN, quyền `CREATEDB`, skip hoặc regression.

| Test ID | Failure kỳ vọng | Failure quan sát | Phân loại |
|---|---|---|---|
| P5A-001 | Thiếu create/transition ConfigRevision có JCS hash, immutable lineage và CAS revision | `NotImplementedError: P5A ConfigRevision behavior is not implemented` | `VALID_BEHAVIORAL_RED` |
| P5A-002 | Thiếu secret-handle boundary chỉ nhận metadata và từ chối plaintext-shaped input | `NotImplementedError: P5A secret-handle boundary is not implemented` | `VALID_BEHAVIORAL_RED` |
| P5A-003 | Thiếu construction event/audit P5A an toàn qua P3 envelope/outbox | `NotImplementedError: P5A config event/audit construction is not implemented` | `VALID_BEHAVIORAL_RED` |
| P5A-004 | Thiếu production `0004_config_and_secrets.sql` và rollback chính xác | Assertion yêu cầu hai tệp production `0004` | `VALID_BEHAVIORAL_RED` |
| P5A-005 | Thiếu repository scoped theo workspace và publish CAS | `NotImplementedError: P5A scoped configuration repository is not implemented` | `VALID_BEHAVIORAL_RED` |

P5A-004 chỉ chứng minh absence của capability migration sau khi runner P1 và P1–P3 schema đã thành công; không tạo/sửa production migration `0004` trong pha RED này.
