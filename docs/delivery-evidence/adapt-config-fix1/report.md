# Báo cáo ADAPT-CONFIG-FIX1

## Nhóm lỗi

Mã nhóm lỗi R17: Khóa trọng số model-weights.lock.json còn 6 mục sha256 null và status BLOCKED, url faster-whisper còn <commit>, khiến Kokoro và aligner trả weights_unpinned, RG-05 không chạy được (OI-CP7-01).

## Tệp đã sửa

- `tools/launcher/prod/model-weights.lock.json`: Chuyển 6 mục trọng số sang trạng thái PINNED với sha256 do Control đo ngày 30/10/2026; ghim commit d1d751a5f8271d482d14ca55d9e2deeebbae577f cho 4 mục faster-whisper small.en trong URL và trường commit; cập nhật trường reason; không thêm bất kỳ tệp trọng số nào vào cây Git; Worker không tải hay băm lại để đổi giá trị.
- `docs/delivery-evidence/adapt-config-fix1/report.md`: Báo cáo nghiệm thu chi tiết của task ADAPT-CONFIG-FIX1.

## Lệnh đã chạy

1. `git diff --check`
   - Exit code: 0
   - Kết quả: Không có lỗi định dạng hay khoảng trắng thừa cuối dòng.

2. `python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider`
   - Exit code: 0
   - Kết quả: 11 passed in 0.04s.

3. `python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/launcher/prod/model-weights.lock.json').read_text(encoding='utf-8')); m = dict((f['name'], f) for f in d['files']); assert all(m[n]['sha256'] == h and m[n]['status'] == 'PINNED' for n, h in [('kokoro-v1.0.onnx', '7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5'), ('voices-v1.0.bin', 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'), ('config.json', '666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae'), ('model.bin', '62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a'), ('tokenizer.json', '929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df'), ('vocabulary.txt', 'ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf')]), 'pins'; assert all(f['commit'] == 'd1d751a5f8271d482d14ca55d9e2deeebbae577f' and 'd1d751a5f8271d482d14ca55d9e2deeebbae577f' in f['url'] and '<commit>' not in f['url'] for f in d['files'] if f['group'] == 'faster-whisper-small.en'), 'commit'"`
   - Exit code: 0
   - Kết quả: Toàn bộ 6 tệp có sha256 và status PINNED khớp bảng, 4 tệp whisper có commit d1d751a5f8271d482d14ca55d9e2deeebbae577f trong url và trường commit.

4. `python -c "import hashlib, json, pathlib; d = json.loads(pathlib.Path('tools/launcher/prod/model-weights.lock.json').read_text(encoding='utf-8')); b = pathlib.Path.home() / 'AppData' / 'Local' / 'AIAutoVideoCreator' / 'models'; sub = dict([('kokoro-onnx', 'weights'), ('faster-whisper-small.en', 'whisper')]); assert all(hashlib.sha256((b / sub[f['group']] / f['name']).read_bytes()).hexdigest() == f['sha256'] for f in d['files']), 'disk'"`
   - Exit code: 0
   - Kết quả: Băm 6 tệp thực tế ngoài cây Git dưới LOCALAPPDATA/AIAutoVideoCreator/models hoàn toàn khớp với sha256 trong model-weights.lock.json.

5. `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-config-fix1/report.md').read_text(encoding='utf-8'); assert 'ADAPT-CONFIG-FIX1' in t and 'R17' in t, 'report'"`
   - Exit code: 0
   - Kết quả: Khẳng định báo cáo nêu đầy đủ mã gói ADAPT-CONFIG-FIX1 và mã nhóm lỗi R17.

## Phạm vi

- Xác nhận chỉ chỉnh sửa trong phạm vi các tệp thuộc danh sách owned paths đã được giao (`tools/launcher/prod/model-weights.lock.json` và `docs/delivery-evidence/adapt-config-fix1/report.md`).
- Không thêm bất kỳ tệp trọng số (.onnx, .bin, .safetensors) hoặc media vào cây Git.
- Không sửa tệp ngoài owned paths, không push remote và không merge vào main.
