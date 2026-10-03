# Bounded product slice: TASK-CAP-J-P2

## Mục tiêu

Triển khai projection `CapabilityView` cho Module J theo `CT-CAP-003` của
`CONTRACT-CONFIG-SECURITY`. Projection chỉ đọc các capacity observations đã có,
không gọi mạng, không đọc secret, không cấp authority và không thay đổi
`CapacityAccounting`.

## Phạm vi được phép sửa

1. `src/controlplane/config/capability_view.py`
2. `tests/unit/security/test_capability_view.py`

Không sửa DAG, contract registry, migration, API root, secret broker, module
khác hoặc bất kỳ đường dẫn nào ngoài allowlist.

## Yêu cầu hành vi

- Cung cấp một builder/projection API rõ ràng, nhận observation dạng mapping và
  trả về view mới, không alias hoặc mutate input.
- View phải có `capability_id`, `capability_type`, `location`, `provider`,
  `account_scope`, `status`, `compatible_versions`, `capacity`,
  `last_observed_at`, `expires_at`, `reason` và `next_check_at`.
- `status` chỉ được là `available`, `degraded`, `unavailable` hoặc `unknown`.
- Observation hợp lệ, còn capacity và health tốt → `available`.
- Hết capacity hoặc health `unavailable`/`revoked`/`invalid` → `unavailable`.
- Health suy giảm, quota không chắc hoặc backoff đang hoạt động → `degraded`.
- Thiếu identity, thời gian hoặc dữ liệu số không hợp lệ → `unknown` và phải có
  `reason` fail-closed; không tự điền placeholder để biến thành `available`.
- Capacity indicator phải có `limit`, `used`, `remaining`, `utilization` và
  `confidence`; giá trị phải không âm, hữu hạn và được tính lại từ observation.
- Loại bỏ hoặc redacted mọi key/value có dấu hiệu secret (`token`, `secret`,
  `password`, `credential`, `api_key`, `private_key`, `bearer`).
- Với nhiều observation cùng scope, chọn bản có `observed_at` mới nhất (hòa thì
  dùng `sequence` cao hơn), giữ nguyên các bản ghi đầu vào.

## Kiểm thử bắt buộc

Trước implementation, tạo test RED có tính hành vi và chạy:

```text
python -m unittest tests.unit.security.test_capability_view
```

Sau implementation, lệnh trên phải PASS toàn bộ; chạy thêm:

```text
python -m unittest discover -s tests/unit/security
git diff --check
```

Worker phải báo `worker_done` bằng tiếng Việt, kèm candidate SHA, scope hash,
output từng lệnh và xác nhận không sửa ngoài hai owned paths. Không commit
secret, không push remote.

## Quy trình review

Sol-Lead review read-only exact candidate và chỉ gửi `ACCEPT` khi các oracle
trên đạt. Sau đó Astra-Lead audit read-only exact candidate và chỉ gửi `PASS`.
Không chạy hai reviewer song song. Chưa có đủ `ACCEPT` và `PASS` thì không
được tích hợp local.
