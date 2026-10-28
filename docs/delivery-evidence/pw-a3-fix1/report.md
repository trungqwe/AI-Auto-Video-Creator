# PW-A3-FIX1: Scheduler thu th?p truy?n ref business_date khi kh?i DailyCollectionWorkflow

## Nh?m l?i

Nh?m R1: CollectionScheduler.run_once (collection_scheduler.py:123) kh?i DailyCollectionWorkflow v?i request ch? g?m settings, input_fingerprint, worker_lease_id. Flow fan-out CollectSource (FAN_OUT_FROM_OUTPUT trong activities.py, `_frozen_input_refs` trong flow.py) ch? th?m ref collection_source, trong khi `_parse_input_refs` c?a source_ingestion/worker/activity_handler.py ??i ??ng hai ref collection_source v? business_date, n?n m?i CollectSource tr?n production tr? INVALID_ACTIVITY_REQUEST.

## Thay ??i

Ba t?p thu?c owned paths v? vi?c ?? th?c hi?n:
- `src/controlplane/infrastructure/db/orchestration/collection_scheduler.py`: `CollectionScheduler.run_once` th?m `input_refs = [{'ref_type': 'business_date', 'ref_id': business_date.isoformat()}]` v?o request kh?i `DailyCollectionWorkflow` (??ng format YYYY-MM-DD theo m?i gi? Asia/Ho_Chi_Minh).
- `tests/integration/prod_wiring/test_pw_a3_scheduler.py`: th?m c?c import `FlowParams`, `GrantClaims`, `validate_collect_request`; c?p nh?t h?m l?ng `collect` trong `daily_handlers` ?? tr?ch xu?t ??ng ref c? `ref_type == 'collection_source'`; c?p nh?t assert c?a `test_pw_a3_01_four_checks_in_a_day_collect_each_source_once` ?? ki?m tra `input_refs`; th?m `CapturingClient`, `collect_request_for` v? test m?i `test_pw_a3_fix1_r1_workflow_request_carries_business_date_ref` g?i tr?c ti?p c?c h?m/l?p production th?t m? kh?ng d?ng monkeypatch.
- `docs/delivery-evidence/pw-a3-fix1/report.md`: b?o c?o b?ng ch?ng th?c thi.

N?u r?: Kh?ng s?a `flow.py`, `activities.py` hay `activity_handler.py`.

## L?nh ?? ch?y

| B??c | L?nh | Exit code | K?t qu? th?t |
| --- | --- | --- | --- |
| 3 | `python -m pytest tests/integration/prod_wiring/test_pw_a3_scheduler.py -q -p no:cacheprovider` | 1 | `2 failed, 18 passed in 12.23s` |
| 5 | `python -m pytest tests/integration/prod_wiring/test_pw_a3_scheduler.py -q -p no:cacheprovider` | 0 | `20 passed in 10.66s` |
| 6 | `git diff --check` | 0 | Kh?ng c? output (s?ch kho?ng tr?ng th?a) |

## D?ng RED

D?ng FAILED th?t ???c ghi nh?n t?i b??c 3 tr??c khi s?a m? production:
```
FAILED tests/integration/prod_wiring/test_pw_a3_scheduler.py::test_pw_a3_01_four_checks_in_a_day_collect_each_source_once
>           assert args[1] == {'settings': SETTINGS.to_payload(), 'input_fingerprint': 'collect:2026-10-27:000', 'worker_lease_id': 'ses-1', 'input_refs': [{'ref_type': 'business_date', 'ref_id': '2026-10-27'}]}
E           AssertionError: assert {'settings': ..._id': 'ses-1'} == {'settings': ...2026-10-27'}]}
E             
E             Omitting 3 identical items, use -vv to show
E             Right contains 1 more item:
E             {'input_refs': [{'ref_id': '2026-10-27', 'ref_type': 'business_date'}]}

FAILED tests/integration/prod_wiring/test_pw_a3_scheduler.py::test_pw_a3_fix1_r1_workflow_request_carries_business_date_ref
>           assert request['input_refs'] == [{'ref_type': 'business_date', 'ref_id': expected_date}]
                   ^^^^^^^^^^^^^^^^^^^^^
E           KeyError: 'input_refs'
```

## Ph?n v? d? ?? lo?i tr?

- Request kh?ng c? `input_refs`: `validate_collect_request` tr? v? `('invalid_value', 'input_refs')`.
- Ref `business_date` sai ??nh d?ng (`27/10/2026` thay v? `YYYY-MM-DD`): `validate_collect_request` tr? v? `('invalid_value', 'input_refs')`.
- N?i lu?t hai ref ? handler thay v? truy?n ref: Tuy?t ??i kh?ng s?a `activity_handler.py`, gi? nguy?n invariant b?t bu?c c? hai ref `collection_source` v? `business_date`.
- Patch `validate_collect_request`: Test m?i g?i tr?c ti?p h?m production th?t v?i typed `GrantClaims`, kh?ng mock hay patch logic ki?m ??nh.

## M? test ph?

coveredIds: PW-A3-01, CT-SRC-004, FR-COL-001
