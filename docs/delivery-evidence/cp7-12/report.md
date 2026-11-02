# CP7-12 — Hiệu năng UI, xoay secret và rollback cấu hình (RG-11)

## Kết luận trung thực

Phần kiểm thử xoay bí mật, thu hồi credential và rollback cấu hình (`tests/real/test_cp7_rotation_rollback.py`) đã hoàn thành và đạt 4/4 kiểm thử PASS trên môi trường thật:
- `RG-11.rotation_old_version_rejected`: PASS
- `RG-11.revoke_job_waiting`: PASS
- `RG-11.rollback_hash_restored`: PASS
- `RG-11.secret_scan`: PASS

Phần kiểm thử hiệu năng UI và SSE (`tests/real/test_cp7_ui_perf.py`) đã được triển khai đầy đủ theo đúng Bước 9–12 của Work Order, nhưng bị chặn (BLOCKED) tại Bước 13 do điều kiện tiên quyết của cơ sở dữ liệu sau CP7-11 không thoả mãn:
- `controlplane.cp_cost_records`: 0 bản ghi (yêu cầu > 0)
- `controlplane.cp_operation_stream`: 0 bản ghi (yêu cầu > 0 và >= 300 sự kiện SSE)

## Lệnh đã chạy

- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`
- Biến môi trường: `PYTEST_DEBUG_TEMPROOT=C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\CP7-12-implement-r0-ac1b5c0961`

1. Lệnh kiểm rotation & rollback:
`python -m pytest tests/real/test_cp7_rotation_rollback.py -q -p no:cacheprovider`
Exit code: 0
Kết quả: `4 passed in 14.90s`

2. Lệnh kiểm UI & SSE:
`python -m pytest tests/real/test_cp7_ui_perf.py -q -p no:cacheprovider`
Exit code: 1
Kết quả: `5 errors in 0.41s` (Failed: BLOCKED: dữ liệu rỗng hoặc dưới 100 video job)

## Dữ liệu khoá

Số lượng bản ghi thực tế trong cơ sở dữ liệu `controlplane` (workspace `AI Auto Video Creator`):
- `cp_video_jobs`: 517 (đạt yêu cầu >= 100)
- `cp_production_batches`: 39 (đạt yêu cầu > 0)
- `cp_artifact_versions`: 1506 (đạt yêu cầu > 0)
- `cp_artifact_locations`: 1936 (đạt yêu cầu > 0)
- `cp_cost_records`: 0 (KHÔNG ĐẠT: yêu cầu > 0)
- `cp_completion_ledger`: 429 (đạt yêu cầu > 0)
- `cp_operation_stream`: 0 (KHÔNG ĐẠT: yêu cầu > 0, SSE yêu cầu >= 300)

## Phân tích nguyên nhân DEPENDENCY_GAP

1. Bảng `cp_cost_records` = 0:
Trong đợt chạy 100 video CP7-11, toàn bộ các lượt gọi AI script và hook được định tuyến qua tuyến 9Router (Gemini) miễn phí với đơn giá 0 USD (`route_cost_per_request = 0`). Hàm `_charge()` trong `src/controlplane/application/config_security/routed_invocation.py` có điều kiện kiểm tra:
`if not isinstance(cost, Decimal) or not cost.is_finite() or cost <= 0: return`
Do đó không có bản ghi chi phí nào được tạo ra trong suốt quá trình chạy thật của CP7-11.

2. Bảng `cp_operation_stream` = 0:
Có 11.570 sự kiện domain thật được lưu trong `controlplane.cp_outbox_events` từ các đợt chạy lô của CP7-11. Tuy nhiên, launcher trong chế độ production chỉ chạy tiến trình `OutboxRelay` để chuyển tiếp sự kiện `production_batch.start_accepted` sang Temporal, mà không chạy background projector để chuyển đổi các domain events trong outbox thành stream events trong bảng `cp_operation_stream`.

## Ranh giới tuân thủ kiến trúc và phân quyền

Worker bị nghiêm cấm:
- Tự ý UPDATE / INSERT dữ liệu giả mạo vào cơ sở dữ liệu production `controlplane` (ngoại trừ thao tác ghi rồi khôi phục hàng watermark SSE ở Bước 12).
- Tự ý sửa mã nguồn `src/**` hoặc `tools/real/**` (ngoài 3 owned paths được cấp).
- Dùng mock để bypass gate kiểm thử thực tế.

Do đó, Worker dừng lại đúng Bước 13 và báo cáo trạng thái `BLOCKED` fail-closed theo đúng quy định điều phối toàn cục `ORCA-UNIV-GOV-001`.

## Xoay, thu hồi, rollback

- `RG-11.rotation_old_version_rejected`: PASS (versions=v9->v10 old_bin_removed=True old_revoked_marker=True export_is_new_version=True all_revoked_denied=True)
- `RG-11.revoke_job_waiting`: PASS (old_grant_rejected=True job_wait_reason=credential_unavailable job_rows=1 resumed_active_after_new_credential=True db=disposable)
- `RG-11.rollback_hash_restored`: PASS (scope=policy:cp7-rg11-probe revisions=n7->n9 hash_a=7ede5d59 hash_b=b0864cc2 hash_after_rollback=7ede5d59 old_rows_unchanged=True)
- `RG-11.secret_scan`: PASS (surfaces=2 secret_pattern_matches=0 synthetic_value_hits=0)

## Giới hạn

- Tuân thủ OI-CP7-07: Không thu hồi token Google Drive thật.
- Kiểm thử thu hồi credential chạy trên cơ sở dữ liệu tạm thời dùng một lần (`cp7_*`) để cách ly hoàn toàn với production.
- Rollback cấu hình được thực hiện bằng cách công bố revision mới trên scope tổng hợp `policy:cp7-rg11-probe` mà không sửa tay revision cũ.
