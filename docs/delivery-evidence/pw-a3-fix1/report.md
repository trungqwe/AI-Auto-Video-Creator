# PW-A3-FIX1: Scheduler thu thập truyền ref business_date khi khởi DailyCollectionWorkflow

## Nhóm lỗi

Nhóm R1: `CollectionScheduler.run_once` (collection_scheduler.py:123) khởi `DailyCollectionWorkflow` với request chỉ gồm settings, input_fingerprint, worker_lease_id. Flow fan-out `CollectSource` chỉ thêm ref `collection_source`, trong khi `_parse_input_refs` của `source_ingestion/worker/activity_handler.py` đòi đúng hai ref `collection_source` và `business_date`, nên mọi `CollectSource` trên production trả `INVALID_ACTIVITY_REQUEST`.

## Tệp đã sửa

- `src/controlplane/infrastructure/db/orchestration/collection_scheduler.py`: `CollectionScheduler.run_once` thêm `input_refs = [{'ref_type': 'business_date', 'ref_id': business_date.isoformat()}]` vào request khởi workflow (định dạng YYYY-MM-DD theo múi giờ Asia/Ho_Chi_Minh).
- `tests/integration/prod_wiring/test_pw_a3_scheduler.py`: thêm import `FlowParams`, `GrantClaims`, `validate_collect_request`; hàm lồng `collect` trong `daily_handlers` lấy đúng ref có `ref_type == 'collection_source'`; assert của `test_pw_a3_01_four_checks_in_a_day_collect_each_source_once` kiểm `input_refs`; thêm `CapturingClient`, `collect_request_for` và test `test_pw_a3_fix1_r1_workflow_request_carries_business_date_ref` gọi trực tiếp mã production thật, không dùng monkeypatch.
- `docs/delivery-evidence/pw-a3-fix1/report.md`: báo cáo này, viết lại bằng UTF-8 đủ dấu để sửa lỗi mất dấu của bản trước.

Không sửa `flow.py`, `activities.py` hay `activity_handler.py`.

## Lệnh đã chạy

| Lệnh | Mã thoát | Kết quả thật |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_a3_scheduler.py -q -p no:cacheprovider` | 0 | `20 passed in 11.74s` |
| `git diff --check` | 0 | Không có output (không thừa khoảng trắng) |

## Dòng RED đã ghi ở lượt trước

Theo báo cáo lượt trước, trước khi sửa mã production pytest cho `2 failed, 18 passed in 12.23s`: `test_pw_a3_01_four_checks_in_a_day_collect_each_source_once` lệch vì request thiếu `input_refs`, và `test_pw_a3_fix1_r1_workflow_request_carries_business_date_ref` báo `KeyError: 'input_refs'`.

## Phản ví dụ đã loại trừ

- Request không có `input_refs`: `validate_collect_request` trả `('invalid_value', 'input_refs')`; test khẳng định điều này.
- Ref `business_date` sai định dạng (`27/10/2026` thay vì `YYYY-MM-DD`): `validate_collect_request` trả `('invalid_value', 'input_refs')`; test khẳng định điều này.
- Nới luật hai ref ở handler thay vì truyền ref: không sửa `activity_handler.py`, giữ nguyên yêu cầu đủ hai ref.
- Patch `validate_collect_request`: test gọi trực tiếp hàm production thật với `GrantClaims` thật, không mock hay patch.

## Mã test phủ

coveredIds: PW-A3-01, CT-SRC-004, FR-COL-001
