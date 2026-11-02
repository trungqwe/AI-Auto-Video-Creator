# Báo cáo nghiệm thu CP7-12: Hiệu năng UI, xoay secret và rollback cấu hình (RG-11)

## Kết luận

Toàn bộ 9/9 hạng mục kiểm thử RG-11 đều đạt trạng thái PASS, không còn bất kỳ điều kiện BLOCKED nào. Chi phí thực hiện là 0 USD, không gọi dịch vụ AI ngoài phong bì. Nhánh lane đã được rebase thành công lên đầu tích hợp 27b510e417a6507f823dc2dc23586af238535bba (đã chứa OPSTREAM-WIRE).

## Lệnh đã chạy

Lệnh kiểm thử bước 9:
`python -m pytest tests/real/test_cp7_ui_perf.py tests/real/test_cp7_rotation_rollback.py -q -p no:cacheprovider`

Mã thoát (exit code): 0
Kết quả tổng kết pytest: `9 passed in 69.27s (0:01:09)`

## Dữ liệu khoá

Bảng đếm và mã băm dữ liệu xác thực từ môi trường thật sau CP7-11 (>= 100 video job):
- dataset_counts_sha256: `022a5b4bd3d6508d4da22489e1bbfec3aa6589840396fec2bf3c36a8b4830ba1`
- dataset_counts: `{"cp_artifact_locations": 1936, "cp_artifact_versions": 1506, "cp_completion_ledger": 429, "cp_cost_records": 0, "cp_operation_stream": 1649, "cp_production_batches": 39, "cp_video_jobs": 517}`

Ghi nhận thiết kế:
- `cp_cost_records` = 0 là hoàn toàn đúng thiết kế vì tác vụ AI đi qua 9Router tính phí 0 USD, do đó `routed_invocation` không ghi nhận chi phí lớn hơn 0. Màn `cost` được đo đạc chính xác ở trạng thái rỗng và xác nhận giao diện hiển thị đúng khi chưa có dữ liệu.
- `stream_ids_used`: 400 sự kiện luồng thao tác đã được sử dụng.
- `seed_writes`: 0 (không cần bổ sung ghi thêm vì đầu tích hợp OPSTREAM-WIRE đã tự động chuyển đổi sự kiện outbox sang operation stream).
- `min_required`: 320.

## Bằng chứng RG-11

RG-11.ui_p95_cold: PASS
- ui_p95_cold: browser=chromium viewport=1920x1080 samples=30 limit_ms=2000
- ui_p95_cold: dataset_counts_sha256=022a5b4bd3d6508d4da22489e1bbfec3aa6589840396fec2bf3c36a8b4830ba1
- ui_p95_cold: dataset_counts={"cp_artifact_locations": 1936, "cp_artifact_versions": 1506, "cp_completion_ledger": 429, "cp_cost_records": 0, "cp_operation_stream": 1649, "cp_production_batches": 39, "cp_video_jobs": 517}
- ui_p95_cold: jobs: n=30 p50_ms=51 p95_ms=79 rows_min=50
- ui_p95_cold: batches: n=30 p50_ms=53 p95_ms=72 rows_min=39
- ui_p95_cold: artifacts: n=30 p50_ms=100 p95_ms=133 rows_min=50
- ui_p95_cold: cost: n=30 p50_ms=41 p95_ms=52 rows_min=0

RG-11.ack_p95_cold: PASS
- ack_p95_cold: command=PUT /v1/configs/policy:cp7-rg11-ack samples=30 limit_ms=1000
- ack_p95_cold: p50_ms=14 p95_ms=39

RG-11.ui_p95_warm: PASS
- ui_p95_warm: browser=chromium viewport=1920x1080 samples=30 limit_ms=2000
- ui_p95_warm: dataset_counts_sha256=022a5b4bd3d6508d4da22489e1bbfec3aa6589840396fec2bf3c36a8b4830ba1
- ui_p95_warm: dataset_counts={"cp_artifact_locations": 1936, "cp_artifact_versions": 1506, "cp_completion_ledger": 429, "cp_cost_records": 0, "cp_operation_stream": 1649, "cp_production_batches": 39, "cp_video_jobs": 517}
- ui_p95_warm: jobs: n=30 p50_ms=45 p95_ms=60 rows_min=50
- ui_p95_warm: batches: n=30 p50_ms=43 p95_ms=59 rows_min=39
- ui_p95_warm: artifacts: n=30 p50_ms=94 p95_ms=116 rows_min=50
- ui_p95_warm: cost: n=30 p50_ms=40 p95_ms=55 rows_min=0

RG-11.ack_p95_warm: PASS
- ack_p95_warm: command=PUT /v1/configs/policy:cp7-rg11-ack samples=30 limit_ms=1000
- ack_p95_warm: p50_ms=17 p95_ms=37

RG-11.sse_resync: PASS
- sse_resync: replay_events=150+150 duplicates=0 gaps=0 expired_cursor_event=resync_required recovery_first_id_ok=True watermark_restored=True
- sse_resync: stream_ids_used=400 seed_writes=0 min_required=320

RG-11.rotation_old_version_rejected: PASS
- rotation_old_version_rejected: versions=v13->v14 old_bin_removed=True old_revoked_marker=True export_is_new_version=True all_revoked_denied=True

RG-11.revoke_job_waiting: PASS
- revoke_job_waiting: old_grant_rejected=True job_wait_reason=credential_unavailable job_rows=1 resumed_active_after_new_credential=True db=disposable

RG-11.rollback_hash_restored: PASS
- rollback_hash_restored: scope=policy:cp7-rg11-probe revisions=n13->n15 hash_a=7ede5d59 hash_b=b0864cc2 hash_after_rollback=7ede5d59 old_rows_unchanged=True

RG-11.secret_scan: PASS
- secret_scan: surfaces=3 secret_pattern_matches=0 synthetic_value_hits=0

## Giới hạn

- Theo OI-CP7-07: Tuyệt đối không thu hồi token Drive thật.
- Kiểm thử xoay bí mật và thu hồi credential chạy trên bí mật tổng hợp `cp7-rotate` và cơ sở dữ liệu dùng một lần (disposable).
- Rollback cấu hình thực hiện bằng cách tạo revision mới với nội dung trước đó, xác nhận băm cấu hình phục hồi nguyên trạng.
- Thao tác ACK đo trên lệnh `PUT /v1/configs/policy:cp7-rg11-ack`. Scope dự phòng tạo sự kiện SSE là `policy:cp7-rg11-sse`.
