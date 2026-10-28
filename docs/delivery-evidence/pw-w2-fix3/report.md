# PW-W2-FIX3: báo cáo nhóm lỗi R6

## 1. Mục tiêu

Khắc phục nhóm lỗi R6 trong quá trình chuẩn bị đầu vào render từ kế hoạch sản xuất:
- Ánh xạ `visuals` trong kế hoạch sáng tạo sang `visual_asset_refs` trong các segment của timeline; `local_ref` trong manifest là UUID version của artifact_version thay vì chuỗi kết thúc bằng `.mp4`.
- Voice: tạo một mục trong `materialization_manifest` với khoá là `voice_artifact_ref` (dạng `voice-artifact-<sha>`) và `local_ref` là UUID lấy từ ref `artifact_version` có `source_ref_id == "voice/" + voice_ref`; đồng thời đưa voice vào `input_artifacts` với `artifact_version_id = voice_artifact_ref`, `sha256` và `size_bytes` lấy từ artifact version tương ứng.
- Word timing: đưa timing vào `input_artifacts` với `artifact_version_id = word_timing_ref`, `sha256` và `size_bytes` là giá trị băm và độ dài byte của JSON chuẩn hoá (khoá sắp xếp, không khoảng trắng dư thừa, UTF-8) đọc từ bảng `controlplane.cp_word_timings`.
- Phụ đề ASS: bổ sung mục phụ đề ASS vào manifest bằng hàm `with_ass_entry` với cùng `ass_ref` được tạo và sử dụng bởi `render_plan`.
- Đường dẫn xuất: làm sạch định danh phiên render (`render_attempt_id`), loại bỏ các ký tự không an toàn như dấu `:` thành `_` để đường dẫn tệp video và ảnh thumbnail không chứa `:`.

## 2. Các tệp đã sửa

- `src/controlplane/api/wiring/render.py`:
  - Thêm các hằng số `_VOICE_SOURCE_PREFIX`, `_OUTPUT_NAME_UNSAFE`.
  - Thêm các hàm cấp module: `_output_name`, `_timing_digest`, `_timeline_for_render`.
  - Bổ sung các phương thức `_read_timing_payload` và `_build_ass_material` trong `ProductionRenderSources`, tinh gọn `ass_material`.
  - Cập nhật `resolve_inputs` để đưa `visual_asset_refs` vào timeline segments, bổ sung mục voice và timing vào `input_artifacts`, đưa voice và ASS vào `materialization_manifest`.
  - Cập nhật `validation_context` tạo `VerifiedArtifact` cho voice và timing (sử dụng cùng hàm chuẩn hoá `_timing_digest`).
  - Cập nhật `render_plan` làm sạch tên tệp xuất và thumbnail qua `_output_name` và đồng bộ `ass_ref` từ `ass_material`.
- `tests/integration/prod_wiring/test_pw_f3_render_inputs.py`:
  - Bổ sung các import cho production wiring và creative plan.
  - Thêm các hằng số và hàm trợ giúp: `render_runtime`, `stage_and_register`, `creative_plan`, `build_world`.
  - Thêm 2 test tích hợp PostgreSQL thực tế không monkeypatch:
    - `test_resolved_render_package_validates_and_builds_command`
    - `test_resolve_inputs_fails_closed_on_missing_voice_or_timing` (4 ca tham số hoá).
- `docs/delivery-evidence/pw-w2-fix3/report.md`:
  - Báo cáo kết quả chuyển giao cho gói PW-W2-FIX3 (nhóm lỗi R6).

## 3. Quy tắc

- **Voice**: Tra cứu bản ghi `artifact_version` có `source_ref_id == 'voice/' + voice_ref`. Gán `local_ref` trong manifest là UUID của version; gán `sha256` và `size_bytes` trong `input_artifacts` theo version tương ứng dưới khoá `voice_artifact_ref`.
- **Word timing**: Tính `sha256` và `size_bytes` từ chuỗi JSON chuẩn hoá (khoá sắp xếp theo thứ tự từ điển, phân tách `(',', ':')`, mã hoá UTF-8) của payload đọc từ bảng `controlplane.cp_word_timings`. Cả `resolve_inputs` và `validation_context` đều dùng chung một hàm `_timing_digest` để tránh sai lệch băm.
- **Tên tệp output**: Dùng `_output_name` để chuyển đổi các ký tự ngoài tập `[A-Za-z0-9_-]` (đặc biệt là dấu `:`) thành dấu gạch dưới `_`.

## 4. Lệnh kiểm đã chạy

| STT | Lệnh kiểm | Exit Code | Kết quả |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p no:cacheprovider` | 0 | Đạt (40 passed in 18.44s) |
| 2 | `git diff --check` | 0 | Đạt (không có lỗi khoảng trắng) |
| 3 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix3/report.md').read_text(encoding='utf-8'); assert 'PW-W2-FIX3' in t and 'R6' in t, 'report'"` | 0 | Đạt (khớp mã gói và nhóm lỗi) |

## 5. Dòng tổng kết nguyên văn của pytest

```
40 passed in 18.44s
```

## 6. Giới hạn

- Chỉ sửa đúng nhóm lỗi R6 theo quy định của Control; render vẫn chỉ ghép visual đầu tiên của mỗi segment như trước, không đổi.
- Ref hook và thumbnail không cần version do render không ghép hook độc lập.
- Adapter biên giả duy nhất trong test là ffmpeg nhị phân giả có pin khớp, vision_route và các port kên biên.
