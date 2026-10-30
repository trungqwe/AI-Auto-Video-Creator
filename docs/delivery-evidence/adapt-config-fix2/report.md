# Báo cáo ADAPT-CONFIG-FIX2

## Nhóm lỗi

Mã nhóm lỗi R22: dung sai mốc từ của aligner và karaoke QC còn 150 ms, user quyết nâng lên 200 ms ngày 30/10/2026 (ROADMAP-OPEN-008) theo số đo RG-05 của CP7-6: 101/110 câu trong 150 ms, 106/110 câu trong 200 ms, giữ ngưỡng nghiệm thu 95% câu.

## Tệp đã sửa

- `tools/launcher/prod/profile.json`: aligner.word_timing_tolerance_ms và qc.karaoke_tolerance_ms có value 200, basis DECIDED, reason mới; meta.revision có value 2, basis DECIDED, reason mới.
- `tests/integration/adapt/config/test_adapt_config_profile.py`: sửa giá trị mong đợi 150 thành 200 tại dòng khẳng định bằng nhau của hai khoá dung sai.
- `docs/runbook/runbook-v1.md`: cập nhật hai dòng bảng aligner.word_timing_tolerance_ms và qc.karaoke_tolerance_ms từ 150 ms thành 200 ms.
- `docs/delivery-evidence/adapt-config-fix2/report.md`: báo cáo nghiệm thu chi tiết của task ADAPT-CONFIG-FIX2.

## Lệnh đã chạy

1. `git diff --check`
   - Exit code: 0
   - Kết quả: Không có lỗi định dạng hay khoảng trắng thừa cuối dòng.

2. `python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider`
   - Exit code: 0
   - Kết quả: 11 passed in 0.03s

3. `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider`
   - Exit code: 0
   - Kết quả: 74 passed, 1 warning in 43.69s

4. `python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/launcher/prod/profile.json').read_text(encoding='utf-8')); a = d['aligner']['word_timing_tolerance_ms']; q = d['qc']['karaoke_tolerance_ms']; r = d['meta']['revision']; assert a['value'] == q['value'] == 200 and a['basis'] == q['basis'] == 'DECIDED' and r['value'] == 2, 'ADAPT-CONFIG-FIX2'"`
   - Exit code: 0
   - Kết quả: Khẳng định aligner.word_timing_tolerance_ms và qc.karaoke_tolerance_ms đều có value 200, basis DECIDED; meta.revision có value 2.

5. `python -c "import pathlib; t = pathlib.Path('docs/runbook/runbook-v1.md').read_text(encoding='utf-8'); rows = [l for l in t.splitlines() if 'word_timing_tolerance_ms' in l or 'karaoke_tolerance_ms' in l]; assert len(rows) == 2 and all('200 ms' in l and '150 ms' not in l for l in rows), 'runbook'"`
   - Exit code: 0
   - Kết quả: Đúng 2 dòng bảng runbook chứa aligner.word_timing_tolerance_ms và qc.karaoke_tolerance_ms có 200 ms và không còn 150 ms.

6. `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-config-fix2/report.md').read_text(encoding='utf-8'); assert 'ADAPT-CONFIG-FIX2' in t and 'R22' in t, 'report'"`
   - Exit code: 0
   - Kết quả: Khẳng định báo cáo nêu đầy đủ mã gói ADAPT-CONFIG-FIX2 và mã nhóm lỗi R22.

## Phạm vi

- Xác nhận chỉ chỉnh sửa trong phạm vi 4 tệp thuộc danh sách owned paths đã được giao (`tools/launcher/prod/profile.json`, `tests/integration/adapt/config/test_adapt_config_profile.py`, `docs/runbook/runbook-v1.md`, `docs/delivery-evidence/adapt-config-fix2/report.md`).
- Không sửa bất kỳ mã nguồn nào trong `src/`, không sửa test khác và không sửa `docs/implementation/`.
- Không push remote và không merge vào main.
