# Báo cáo đóng M7 (revision 4) - TRẠNG THÁI: BLOCKED TẠI BƯỚC 6 ĐOẠN 5

## 1. Phạm vi và candidate

- Task: `M7-MILESTONE-CLOSE-R4` (đóng milestone M7, revision 4).
- Candidate: `b8b46c6365c243088988581dbf6d18ba5c7b4e20` (tiêu đề: `integrate(PW-E2E): lane lane-pw-e2e candidate 44e8965191b6`), là HEAD của nhánh tích hợp.
- Interpreter khoá của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\1ca840a7\venv\Scripts\python.exe`.
- Ngày thực thi: `2026-10-29`.
- Quyền hạn: Lane chỉ sở hữu `docs/delivery-evidence/m7-milestone-close/**`; cấm sửa bất kỳ tệp nào thuộc `src/**`, `tests/**`, `migrations/**` hoặc các đường dẫn cấm khác.

## 2. Tiến trình thực thi

Thực hiện theo lệnh làm việc (Work Order) của Orchestrator:
- Chuỗi 1/15: 13/13 đoạn đạt exit code 0 (`git diff --check` và 12 probe kiểm tra cấu trúc plan/slices của các phân hệ A, B, C, I, D, E, F, J, G, H, convergence và checkpoint D9-D10).
- Chuỗi 2/15: 3/3 đoạn đạt exit code 0 (plan/slices của convergence-ext, persist và adapt).
- Chuỗi 3/15: 37/37 đoạn đạt exit code 0 (các bộ unit tests của control_ui, voice, unit toàn bộ, m2 SSE stream, m2 hardening không gồm h36, collection, convergence migration, p9 m2 exit gate, PostgreSQL DSN harness, persistence integration tests, adapt wire, adapt prod sources/app, gitattributes, vite config).
- Chuỗi 4/15: 28/28 đoạn đạt exit code 0 (build UI thành công với dist khớp nguyên trạng, các test catalog hooks, persistence C, adapt prod hooks, launch CLI, docker-compose, launcher, screen registry, wiring fix3, query routes).
- Chuỗi 5/15: 12/12 đoạn đạt exit code 0 (các probe plan/slices của prod-wiring, music survey, prod-wiring v3/v4, layout pkgdir fix, unit tests, scheduler A3).
- Chuỗi 6/15:
  - Đoạn 1: `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py -q -p no:cacheprovider` đạt exit code 0 (9 passed in 3.57s).
  - Đoạn 2: probe kiểm tra `pw-e3-fix1/report.md` đạt exit code 0.
  - Đoạn 3: `python -m pytest tests/integration/prod_wiring/test_pw_i1_materialize.py -q -p no:cacheprovider` đạt exit code 0 (14 passed in 6.00s).
  - Đoạn 4: probe kiểm tra `pw-i1-fix1/report.md` đạt exit code 0.
  - Đoạn 5: `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider` thất bại với exit code 1 (1 failed, 15 passed in 51.50s).

Tổng số đoạn lệnh đã thực thi: 98 đoạn (97 đạt exit code 0, 1 đoạn thất bại exit code 1).

## 3. Chi tiết lỗi tại Bước 6 Đoạn 5

- **Lệnh thực thi:**
  ```bash
  python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider
  ```
- **Exit code:** `1`
- **Thông báo lỗi (pytest short summary & failure):**
  ```text
  FAILED tests/integration/prod_wiring/test_pw_f4_render_worker.py::test_inspect_output_disclosure_gate_follows_the_script_segments
  1 failed, 15 passed in 51.50s

  _________________ test_inspect_output_disclosure_gate_follows_the_script_segments _________________
      world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed', 'inference'])
      insp_out, report, cmd, rec_inputs, deps = qc(world, 'att-qc-1')
      assert report is not None
      gate = next(g for g in report.gates if g.gate == GateName.INFERENCE_DISCLOSURE_PRESENT)
  >   assert gate.status == GateStatus.PASSED
  E   AssertionError: assert <GateStatus.FAILED: 'failed'> == <GateStatus.PASSED: 'passed'>
  ```

## 4. Phân tích nguyên nhân gốc (Root Cause Analysis)

1. Gói `F-10-FIX2` (commit `d594e124d9461d7be3219c7ae3128c8c003af955`, tích hợp trong `9e67a6b`) đã thay đổi `build_render_command` tại `src/render/domain/render_command.py` để phủ visual hook lên trên luồng video nền (`[base]`) trong khoảng thời gian `hook_time_range` (`0..3000ms`).
2. Trong tệp kiểm thử `tests/integration/prod_wiring/test_pw_f4_render_worker.py`, kịch bản test sử dụng `visual_hook_ref = V1` (`visual-1.mp4`) kéo dài từ 0 đến 3000ms.
3. Khi thực hiện kiểm tra cổng `INFERENCE_DISCLOSURE_PRESENT`, inspector `RealOutputInspector` đo độ lệch dải sáng (`band_difference`, sử dụng bộ lọc FFmpeg `signalstats.YAVG`) giữa khung hình mẫu (`sample_ms = 2950ms`) và khung hình chuẩn (`baseline_ms = 1000ms`).
4. Do lớp overlay của `visual-1.mp4` che khuất `visual-2.mp4` tại thời điểm 2950ms, cả hai khung hình đều có nền là `visual-1.mp4` (`testsrc2`). Do đó, độ lệch dải sáng chỉ đạt `4.39954`, thấp hơn ngưỡng `disclosure_min_difference = 5.0` được khai báo trong cấu hình `SETTINGS` của `test_pw_f4_render_worker.py`.
5. Trong báo cáo bằng chứng `docs/delivery-evidence/f-10-fix2/report.md`, tác giả của gói `F-10-FIX2` đã ghi nhận sự ảnh hưởng này nhưng không thể sửa vì nằm ngoài owned paths:
   > "Các tệp kiểm thử `tests/integration/prod_wiring/test_pw_f3_render_inputs.py` và `test_pw_f4_render_worker.py` cũng gọi `build_render_command` nhưng nằm ngoài phạm vi owned paths của gói này."

## 5. Ranh giới phân quyền và kết luận

- Tệp `tests/integration/prod_wiring/test_pw_f4_render_worker.py` nằm ngoài `owned paths` của `M7-MILESTONE-CLOSE-R4` (`docs/delivery-evidence/m7-milestone-close/**`) và thuộc danh sách cấm sửa đổi (`tests/**`).
- Theo quy định phân quyền nghiêm ngặt và tự vệ đóng (Fail-Closed & Zero Hallucinated Authority) tại mục 1.3 và 3.1 của quy chuẩn điều phối Orca: Worker dừng thực thi ngay lập tức, không tự ý sửa đổi tệp ngoài owned paths, ghi nhật ký bằng chứng và báo cáo trạng thái `BLOCKED` kèm khối `blocked-manifest` kiểu `DEPENDENCY_GAP` để Control phân bổ gói sửa lỗi hoặc điều chỉnh kiểm thử phù hợp.

```blocked-manifest
{
  "step": 6,
  "kind": "DEPENDENCY_GAP",
  "ownerTaskIds": ["PW-F4", "F-10-FIX2"],
  "paths": ["tests/integration/prod_wiring/test_pw_f4_render_worker.py"],
  "ids": ["test_inspect_output_disclosure_gate_follows_the_script_segments"]
}
```
