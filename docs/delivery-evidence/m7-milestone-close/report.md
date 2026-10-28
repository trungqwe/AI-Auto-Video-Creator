# Báo cáo đóng M7 (revision 4) - CÓ ĐOẠN KIỂM THẤT BẠI (FAIL của tiêu chí kiểm)

## 1. Phạm vi và candidate

- Task: `M7-MILESTONE-CLOSE-R4` (đóng milestone M7, revision 4).
- Candidate: `b8b46c6365c243088988581dbf6d18ba5c7b4e20` (tiêu đề: `integrate(PW-E2E): lane lane-pw-e2e candidate 44e8965191b6`), là HEAD của nhánh tích hợp.
- Interpreter khoá của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\1ca840a7\venv\Scripts\python.exe`.
- Ngày thực thi: `2026-10-29`.
- Quyền hạn: Lane chỉ sở hữu `docs/delivery-evidence/m7-milestone-close/**`; cấm sửa bất kỳ tệp nào thuộc `src/**`, `tests/**`, `migrations/**` hoặc các đường dẫn cấm khác.

## 2. Tiến trình thực thi

Thực hiện theo lệnh làm việc (Work Order) của Orchestrator:
- Tổng số đoạn lệnh đã ghi nhận trong nhật ký `command-results.md`: 466 đoạn lệnh kiểm tra (gồm 98 đoạn từ lượt trước và 368 đoạn chạy lại/chạy tiếp ở lượt này).
- Kết quả tổng thể: 459 đoạn đạt exit code 0 và 7 đoạn thất bại với exit code 1.
- Toàn bộ các chuỗi từ Chuỗi 1 đến Chuỗi 23 đã được thực thi đầy đủ trên candidate `b8b46c6365c243088988581dbf6d18ba5c7b4e20`.
- Riêng kiểm thử `tests/m2/test_p7b_hardening.py::test_h36_m1_regression` được hoãn sang CP7 (`--deselect`) theo quyết định của user ngày 21/10/2026 và chỉ đạo của Control.

## 3. Chi tiết lỗi kiểm thử

1. **Lỗi tại PW-F4 (`test_inspect_output_disclosure_gate_follows_the_script_segments`):**
   - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider`
   - Exit code: `1` (1 failed, 15 passed in 43.44s)
   - Lỗi tái hiện được tại Bước 1 (Chuỗi 6 chạy lại đoạn 5) và các chuỗi tổng hợp (Chuỗi 11 đoạn 9, Chuỗi 13 đoạn 6, Chuỗi 22 đoạn 21):
     ```text
     FAILED tests/integration/prod_wiring/test_pw_f4_render_worker.py::test_inspect_output_disclosure_gate_follows_the_script_segments
     AssertionError: assert <GateStatus.FAILED: 'failed'> == <GateStatus.PASSED: 'passed'>
     ```
2. **Lỗi tại adapt_f (`test_command_is_an_argument_list_with_production_parameters`):**
   - Lệnh: `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider`
   - Exit code: `1` (1 failed, 53 passed in 3.70s)
   - Lỗi xuất hiện tại Chuỗi 9 đoạn 11, Chuỗi 11 đoạn 9, Chuỗi 13 đoạn 6, Chuỗi 22 đoạn 17, 21:
     ```text
     FAILED tests/integration/adapt/f/test_adapt_f_render.py::test_command_is_an_argument_list_with_production_parameters
     AssertionError: assert 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30' in '[0:v:0]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p[v0]...'
     ```

## 4. Phân tích nguyên nhân gốc (Root Cause Analysis)

1. Gói `F-10-FIX2` (commit `d594e124d9461d7be3219c7ae3128c8c003af955`, tích hợp trong `9e67a6b`) đã cập nhật hàm `build_render_command` tại `src/render/domain/render_command.py` để phủ visual hook lên trên luồng video nền (`[base]`) trong khoảng thời gian `hook_time_range` (`0..3000ms`), đồng thời bổ sung `setsar=1,format=yuv420p` vào bộ lọc complex filtergraph.
2. Trong tệp kiểm thử `tests/integration/prod_wiring/test_pw_f4_render_worker.py`, kịch bản test sử dụng `visual_hook_ref = V1` (`visual-1.mp4`) kéo dài từ 0 đến 3000ms. Khi inspector `RealOutputInspector` đo độ lệch dải sáng (`band_difference`) giữa khung hình mẫu (`sample_ms = 2950ms`) và khung hình chuẩn (`baseline_ms = 1000ms`), do lớp visual hook overlay che khuất timeline, độ lệch dải sáng chỉ đạt `4.39954` (< `5.0`). Lỗi này nằm ở tệp test của PW-F4 chưa được căn lại theo thay đổi của `F-10-FIX2`.
3. Trong khi đó, kiểm thử `tests/integration/prod_wiring/test_pw_e2e_batch_video.py` của `GATE-PW-E2E` cùng đo cổng `INFERENCE_DISCLOSURE_PRESENT` đã chạy đạt exit 0 (`10 passed, 1 warning in 127.03s`), xác nhận rằng cổng này hoạt động bình thường trên rig có hook sử dụng nguồn testsrc chuẩn.
4. Đối với `tests/integration/adapt/f/test_adapt_f_render.py`, assertion trong `test_command_is_an_argument_list_with_production_parameters` kiểm tra chuỗi bộ lọc cũ không có `setsar=1` và `format=yuv420p`, do đó mismatch với đầu ra thực tế của `build_render_command` sau `F-10-FIX2`.

## 5. Kết luận

- Lane `lane-m7-milestone-close-r4` chỉ sở hữu `docs/delivery-evidence/m7-milestone-close/**`, tuyệt đối không sửa đổi tệp ngoài owned paths (như `tests/**` hay `src/**`).
- Các đoạn lệnh kiểm có exit code khác 0 được ghi nhận trung thực là FAIL của tiêu chí kiểm thử tương ứng.
- Lane hoàn thành nhiệm vụ ghi nhận bằng chứng, đối chiếu toàn bộ các gói và exit gate, và bàn giao lại cho Control để lập gói sửa mục tiêu (remediation slice) cho hai tệp kiểm thử nói trên.

## 6. Gói được bao phủ

- Danh sách toàn bộ các gói được bao phủ và SHA tích hợp được trình bày chi tiết tại [packages.md](packages.md).
- Tổng số gói được bao phủ: 139 gói (gồm gói mốc `M7-INTEGRATION-PLAN`, các gói kế hoạch phân hệ, gói hạ tầng, các gói tính năng phân hệ A..J, các gói adapt, các gói prod-ports PP-1..PP-8, các gói sửa lỗi và gói tích hợp kiểm thử E2E).

## 7. Cổng RELEASE

- Toàn bộ 16 cổng `GATE-*` đã được Control phát hành quyết định RELEASE với mã recordHash xác thực, được liệt kê đầy đủ tại mục `## Cổng RELEASE (recordHash)` trong [packages.md](packages.md).

## 8. Gói đã retire

- Hai gói kế hoạch `IMPL-PLAN-PROD-WIRING-FIX1` và `IMPL-PLAN-PROD-WIRING-V3-FIX1` đã được retire và không nằm trong danh sách bao phủ của revision 4.
- Kết quả tra cứu grep trong toàn bộ thư mục `docs/` trả về 0 kết quả (không có tệp tài liệu hay cam kết nào tham chiếu hoặc phụ thuộc vào hai mã này).
- Việc retire hai gói này là phù hợp vì phạm vi của chúng đã được thay thế hoàn toàn bởi `IMPL-PLAN-PROD-WIRING-V3`, `IMPL-PLAN-PROD-WIRING-V4` và các gói sửa lỗi PW; việc này không làm thay đổi các exit gate `M7-R5-EG1` và `M7-R6`.

## 9. Lý do mở revision 4

- Revision 3 đóng mà không tích hợp do các gói `RS-1..RS-13`, bốn gói sửa read-screens, gói kế hoạch PW, chuỗi các gói `PW-*` và `GATE-PW-E2E` không nằm trong danh sách `coveredTasks` đã đóng băng của R3.
- Theo `docs/plans/PROD_WIRING_REOPEN_PLAN_20261025.md`, việc mở revision 4 là cần thiết để bao phủ toàn bộ các gói wiring và read-screens mới mà không lãng phí tài nguyên kiểm thử lặp lại vô ích.
- Tất cả các gói này đã được kiểm tra lại đầy đủ trên candidate qua các đoạn kiểm tra `RS-1..RS-13` (Chuỗi 23), chuỗi `PW-*` (Chuỗi 21, 22), và kiểm thử batch E2E `test_pw_e2e_batch_video.py` (Chuỗi 22 đoạn 40 đạt exit 0).

## 10. Exit gate

- Đối chiếu chi tiết toàn bộ các exit gate của Milestone M7 theo roadmap được trình bày tại [exit-gates.md](exit-gates.md).
- Danh sách chờ phê duyệt của người dùng (`pendingUserCheckpoint`) chỉ bao gồm đúng 2 mục: `M7-R5-EG1` và `M7-R6` (yêu cầu tài nguyên thật và vận hành thực tế tại gói CP7). Mọi exit gate khác không bị ghi pending.
- Kiểm thử `tests/m2/test_p7b_hardening.py::test_h36_m1_regression` mang cờ `--deselect` theo quyết định của user ngày 21/10/2026 hoãn sang CP7.
