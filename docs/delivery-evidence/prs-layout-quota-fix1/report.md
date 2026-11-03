# Báo cáo chuyển giao: PRS-LAYOUT-QUOTA-FIX1

- Milestone: CP7
- Nhóm lỗi: `OI-CP7-11-Q6` (trần 40% một bố cục trong lô bị vượt do tranh chấp đọc trước, ghi sau)
- Base HEAD của lane: `2ff27b9`
- Trạng thái: đã triển khai và tự kiểm; chưa tuyên bố PASS (chờ Sol/Astra và Control).

## 1. Lỗi và cách sửa

Lô `875e2e7d` của CP7-REMEASURE (03/11/2026): CQ `layout_cap_40` OVER, `HERO_STRIP` 41/100 video hợp lệ, trong khi trần là floor(0,4 x 100) = 40 (quyết định D3 điểm 4).

Gốc lỗi là tranh chấp đọc trước, ghi sau. `ProductionActivityInputs._layout_options` đọc số bố cục lúc activity bắt đầu, còn kế hoạch chỉ được lưu sau 45 đến 70 giây gọi mô hình. `job:43` thấy 39 kế hoạch `HERO_STRIP` lúc 19:47:14 và lưu lúc 19:48:05, khi `job:36` đã lưu kế hoạch thứ 40 lúc 19:48:02.

Cách sửa: trong giao dịch lưu kế hoạch, kiểm lại trần dưới `pg_advisory_xact_lock(hashtextextended('creative.layout_cap:' || batch_id, 0))` theo lô. Nếu bố cục đã chọn đã đầy mà còn bố cục được mời có chỗ thì đổi sang bố cục đó theo thứ tự fallback của `choose_layout` với `fallback_reason = batch_cap_race`. Nếu mọi bố cục được mời đều đầy thì giữ bố cục và ghi `batch_cap_full`. Khoá chỉ giữ trong giao dịch lưu kế hoạch và chỉ theo lô, nên job của lô khác không phải chờ.

## 2. Các tệp đã đổi

Bốn tệp chép nguyên văn từ `D:/AIAVC_IMGPROTO/ref/prs-layout-quota-fix1/` (sha256 sau khi đổi CRLF thành LF):

| Tệp | sha256 |
| --- | --- |
| `src/creative/domain/layout_cap.py` | `3bee13e0da06c06823386679355cfba79a20b8a2146518050f4fde805264a93f` |
| `src/creative/adapters/batch_layout_usage.py` | `987a44deec094fc90ed45b579ea3783873fe480d339efc28483d9db1c7890be9` |
| `tests/integration/prod_wiring/test_prs_layout_quota_fix1.py` | `c6cf16b90b068f79b04394c47136f95948c049a5c35ed8544f0084359ca1a922` |
| `tests/integration/persistence/d/test_layout_cap_lock_postgres.py` | `1a157e97bcf16b14be67bdfda29f64f5bcb754613b4d533fd2792a7e8c98f75d` |

Hai tệp sửa đúng số chỗ được giao, cả hai khớp `SHA256SUMS` của bản tham chiếu:

- `src/creative/application/pipeline.py` (sha256 `0eb55b26e0573e343e2582c9af6ee144e3feb0f7a943dd9133dd01451c4e51a5`), ba chỗ: import `recheck_layout`; lời gọi `self._recheck_layout_cap(...)` trong `store` của `build_production_plan`, đứng trước `unit.plans.append(production_plan_id, 1, plan)`; staticmethod `_recheck_layout_cap`.
- `src/creative/persistence/uow.py` (sha256 `226000a2b2029c40be002d5c6d5361abcd8969e967a5128c5b4fb05888b34c1a`), hai chỗ: import `PostgresBatchLayoutUsage` và `self.layout_usage = PostgresBatchLayoutUsage(source, workspace)` ngay sau `self.outbox = ...`.

Không sửa: `src/creative/domain/layout_choice.py`, `src/creative/adapters/activity_inputs.py`, `src/creative/domain/production_plan.py`, `src/controlplane/api/wiring/**`, `BATCH_SHARE_MAX`, test cũ. Unit trong bộ nhớ không có `layout_usage` nên không đổi hành vi.

## 3. Lệnh đã chạy

Interpreter khoá: `.local-tools/runtime/8715e538/venv/Scripts/python.exe`; `PYTEST_DEBUG_TEMPROOT` đặt theo spec.

| Bước | Lệnh | Mã thoát | Dòng tổng kết |
| --- | --- | --- | --- |
| 5 (RED, trước khi sửa pipeline.py và uow.py) | `python -m pytest tests/integration/prod_wiring/test_prs_layout_quota_fix1.py -q -p no:cacheprovider` | 1 | `4 failed, 3 passed in 4.32s` (lỗi assert oracle / thiếu `layout_usage`, không phải lỗi import; nguyên mẫu Control đo 6 failed 1 passed, số thật ở lane là 4 failed 3 passed) |
| 11 | `git diff --check` | 0 | không có lỗi khoảng trắng |
| 12, 13 | probe băm bốn tệp chép và hai tệp đã sửa | 0 | khớp sha256 |
| 14, 15, 16 | probe cấu trúc `pipeline.py`, `uow.py` và tên bảng, CRLF | 0 | đạt |
| 17 (nhóm 1) | `python -m pytest tests/integration/prod_wiring/test_prs_layout_quota_fix1.py tests/integration/prod_wiring/test_prs_layout_quota.py tests/integration/creative tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/integration/prod_wiring/test_pw_d2_context_selection.py tests/integration/prod_wiring/test_d15_fix1_ai_output_retry.py tests/integration/prod_wiring/test_d15_fix2_model_json.py tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/integration/prod_wiring/test_imggen_pipe_activity.py tests/integration/prod_wiring/test_pw_d3_fix3_illustration.py tests/m2/test_p0_architecture_rules.py -q -p no:cacheprovider` | 0 | `382 passed in 81.27s (0:01:21)` |
| 18 (nhóm 2) | `python -m pytest tests/unit/creative -q -p no:cacheprovider` | 0 | `934 passed, 200 subtests passed in 4.04s` |
| 19 (nhóm 3, PostgreSQL) | `python -m pytest tests/integration/persistence/d/test_layout_cap_lock_postgres.py tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider` | 0 | `24 passed in 12.47s` (không có ca skipped; ca hai giao dịch cùng lô chạy thật trên PostgreSQL, gồm kiểm giao dịch thứ hai chờ khoá và lô khác không chờ) |
| 20 đến 26 | probe `layout_choice` (băm, hàm và hằng), D-15-FIX1, D-15-FIX2, ghi chú minh hoạ AI, CP2A-LAYOUT, pyproject và import tiền tố `src` | 0 | đạt |
| 28 | probe `report.md` nêu `PRS-LAYOUT-QUOTA-FIX1` và `OI-CP7-11-Q6` | 0 | đạt (chạy sau khi ghi báo cáo) |
| 29 | `git diff --check` | 0 | không có lỗi khoảng trắng |

## 4. Giới hạn

- Bố cục mô hình đã viết nội dung theo (tiêu đề, lý do) được giữ khi chuyển.
- `SPLIT_STACK` nhận qua chuyển thì không có `contrast_pair` (như fallback sẵn có, render bỏ nhãn trên dưới).
- Nhánh mọi bố cục được mời đều đầy (`batch_cap_full`) chỉ giữ bố cục đã chọn và ghi lý do; nhánh này chưa từng xảy ra ở lô đo. Nới điều kiện `FULL_BLEED_INSET` cần biết ảnh dọc, để gói riêng.
- Số bố cục là của kế hoạch, không phải video hợp lệ: job lỗi sau khi lập kế hoạch nhưng chưa `FAILED_FINAL` vẫn giữ chỗ tới khi thành `FAILED_FINAL`.
- Unit trong bộ nhớ (`InMemoryUnitOfWork`) không đổi hành vi.

## 5. Mục mở và việc tiếp theo

- `OI-CP7-11-Q6`: đã có bản sửa và test, chờ Sol/Astra nghiệm thu; Worker không tự nhận PASS.
- Control cần đo lại trên lô mới để xác nhận không còn bố cục vượt trần 40% và xem có gặp `batch_cap_full` hay không.
