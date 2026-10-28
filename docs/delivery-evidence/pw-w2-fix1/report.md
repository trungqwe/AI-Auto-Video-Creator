# Báo cáo PW-W2-FIX1

- Mã gói: `PW-W2-FIX1`
- Nhóm lỗi: `R2`

## Nhóm lỗi R2

- Mô tả lỗi cũ: `src/controlplane/api/wiring/creative.py` gọi `hashlib.sha256` mà không `import hashlib` dẫn đến lỗi `NameError` tại mọi lần gọi `ValidateVariant` ở pha output. Đồng thời, hàm băm chuỗi tham chiếu (`output_ref`) hoặc chuỗi `"out:{job_id}"` thay vì băm nội dung video, trong khi `completion_assembler.py` so sánh `output_hash` với SHA-256 nội dung tệp video thực tế.
- Cách sửa: `output_hash` được lấy trực tiếp từ trường `sha256` của tham chiếu `render_output` (giá trị hash nội dung video đã được xác minh tại thời điểm render theo PW-F4-FIX1). Nếu thiếu hoặc không có trường `sha256` hợp lệ (chuỗi không rỗng), không gán trường `output_hash` vào ngữ cảnh để tầng domain trả về `INPUT_NOT_READY missing_output_hash` theo đúng `creative/domain/variant.py`. Loại bỏ hoàn toàn nhánh băm chuỗi và không tự băm tệp ở pha output.

## Tệp đã sửa

- `src/controlplane/api/wiring/creative.py`
- `tests/integration/prod_wiring/test_pw_d2_context_selection.py`
- `docs/delivery-evidence/pw-w2-fix1/report.md`

## Lệnh kiểm đã chạy

1. `git diff --check`
   - Mã thoát: `0`
   - Kết quả: Không có lỗi khoảng trắng thừa.

2. `python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py -q -p no:cacheprovider`
   - Mã thoát: `0`
   - Dòng tổng kết nguyên văn của pytest:
```
16 passed in 8.38s
```

3. `python -c "import pathlib; t = pathlib.Path('src/controlplane/api/wiring/creative.py').read_text(encoding='utf-8'); assert 'hashlib' not in t and 'out:' not in t and 'sha256' in t, 'creative'"`
   - Mã thoát: `0`
   - Kết quả: Xác nhận `creative.py` không còn `hashlib`, không còn `out:`, và có trường `sha256`.

4. `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix1/report.md').read_text(encoding='utf-8'); assert 'PW-W2-FIX1' in t and 'R2' in t, 'report'"`
   - Mã thoát: `0`
   - Kết quả: Báo cáo chứa đúng mã gói `PW-W2-FIX1` và mã nhóm lỗi `R2`.

## Giới hạn

- Gói chỉ sửa đúng nhóm lỗi R2, không thay đổi bất kỳ hành vi hay cấu trúc nào khác.
- Không chứa commit SHA trong báo cáo do commit được tạo sau khi lập báo cáo theo đúng quy trình.
