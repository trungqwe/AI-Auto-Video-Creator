# Báo cáo bằng chứng D-08-FIX1

## Nhóm lỗi và bối cảnh: OI-CP7-11-Q3

- Mã nhóm lỗi: `OI-CP7-11-Q3`
- Bối cảnh: Video 7 và 68 của lô 71973394 (CP7-11 lượt 3) hỏng tts với lỗi `voice_duration_out_of_range`. Kịch bản vượt qua luật cũ (dựa trên số từ / 136 từ/phút trong khoảng 61-70 s) nhưng do chứa nhiều từ ngắn nên lần đọc đầu thực tế chỉ đạt 54,763 s và 54,443 s. Lần đọc lại duy nhất ở mức kẹp tỉ lệ 0,85 không thể kéo thời lượng chạm mức tối thiểu 61 s.
- Phân tích đo lường trên 63 lần đọc ở tốc độ 1,0 của lô: số từ chỉ giải thích R2 0,005 (sai số sd 2,75 s), trong khi số ký tự không kể dấu cách đạt R2 0,70 (sai số sd 1,42 s, tốc độ trung bình 13,81 ký tự/s). Ở lần đọc lại kẹp 0,85, thời lượng kéo dài ít nhất x1,1087; ở mức kẹp 1,15 rút ngắn còn x0,9226.
- Trạng thái giải quyết: Đã xử lý ở phía ước lượng kịch bản bằng cách ước lượng theo số ký tự không kể dấu cách và mở rộng dải nhận lần đọc đầu vào khoảng 55,02-75,87 s (với mục tiêu 61-70 s); kịch bản nằm ngoài dải này bị loại để AI viết lại trong số lượt cho phép (`ai.retry.max_attempts`).

## Các tệp đã sửa

- `src/creative/domain/script.py`:
  - Bổ sung 3 hằng số: `SCRIPT_CHARS_PER_SECOND = 13.81`, `FIRST_READ_SLOW_RATIO = 1.1087`, `FIRST_READ_FAST_RATIO = 0.9226` kèm chú thích nguồn đo.
  - Bổ sung trường tuỳ chọn `chars_per_second: float | None = None` vào `LanguageVoicePolicy` (kiểm tra dương, hữu hạn, `ValueError` khi sai).
  - Thêm hàm `count_chars(text: str) -> int` đếm số ký tự không kể dấu cách từ `normalize_narration(text)`.
  - Cập nhật hàm `build_script_version`: khi `chars_per_second` là `None` giữ nguyên luật đếm từ; khi có giá trị thì ước lượng thời lượng bằng `ký tự / chars_per_second` và chỉ chấp nhận kịch bản nếu thời lượng ước lượng nằm trong khoảng `[target_range.min_seconds / FIRST_READ_SLOW_RATIO, target_range.max_seconds / FIRST_READ_FAST_RATIO]` (55,02-75,87 s với khoảng 61-70 s).
- `src/controlplane/api/wiring/creative.py`:
  - Import `SCRIPT_CHARS_PER_SECOND` từ `creative.domain.script`.
  - Trong hàm `creative_settings`: khởi tạo `LanguageVoicePolicy(language=lang, speech_rate=speech_rate, chars_per_second=SCRIPT_CHARS_PER_SECOND)`.
  - Giữ nguyên toàn bộ cấu hình khác: prompt, profile, target_range và `speech_rate_wpm`.
- `tests/unit/creative/test_d08_fix1_char_estimate.py`:
  - Tệp kiểm thử mới độc lập bao phủ 5 trường hợp bắt buộc: `test_constants_follow_the_measured_reads`, `test_first_read_the_reread_can_pull_into_range_is_admitted`, `test_first_read_out_of_reach_is_rejected`, `test_without_chars_per_second_the_word_rule_is_unchanged`, `test_production_settings_estimate_by_characters`.
  - Không chứa `monkeypatch`, `mock` hay `coveredIds`.
- `docs/delivery-evidence/d-08-fix1/report.md`:
  - Báo cáo bằng chứng thực thi chi tiết bằng tiếng Việt có dấu.

## Bảng kết quả lệnh kiểm tra thực tế (Bước 10 - 18)

| Bước | Lệnh kiểm tra | Exit Code | Dòng tổng kết / Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 10 | `python -m pytest tests/unit/creative/test_d08_fix1_char_estimate.py tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider` | 0 | `82 passed in 2.05s` |
| Bước 11 | `git diff --check` | 0 | Thành công, không có khoảng trắng thừa |
| Bước 12 | `python -m pytest tests/unit/creative -q -p no:cacheprovider` | 0 | `928 passed, 200 subtests passed in 2.95s` |
| Bước 13 | `python -m pytest tests/integration/prod_wiring/test_d15_fix1_ai_output_retry.py tests/integration/creative/test_d15_provider_failure.py tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/integration/prod_wiring/test_pw_d2_context_selection.py tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider` | 0 | `315 passed in 38.42s` |
| Bước 14 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7809 passed, 1 warning, 2561 subtests passed in 24.81s` |
| Bước 15 | `python -c "import json, pathlib; t = pathlib.Path('src/creative/domain/script.py').read_text(encoding='utf-8'); assert all(s in t for s in ['SCRIPT_CHARS_PER_SECOND = 13.81', 'FIRST_READ_SLOW_RATIO = 1.1087', 'FIRST_READ_FAST_RATIO = 0.9226', 'chars_per_second: float | None = None', 'def count_chars(', 'target_range.min_seconds / FIRST_READ_SLOW_RATIO', 'target_range.max_seconds / FIRST_READ_FAST_RATIO']), 'script'; w = pathlib.Path('src/controlplane/api/wiring/creative.py').read_text(encoding='utf-8'); assert 'chars_per_second=SCRIPT_CHARS_PER_SECOND' in w, 'wiring'; v = json.loads(pathlib.Path('tools/launcher/prod/profile.json').read_text(encoding='utf-8'))['voice']; assert v['duration_range_ms']['value'] == {'min': 61000, 'max': 70000} and v['speed_fit']['value']['min_scale'] == 0.85 and v['speed_fit']['value']['max_scale'] == 1.15 and v['speech_rate_wpm']['value'] == 136, v"` | 0 | Khớp đầy đủ hằng số, trường, wiring và profile.json không đổi |
| Bước 16 | `python -c "import pathlib; t = pathlib.Path('tests/unit/creative/test_d08_fix1_char_estimate.py').read_text(encoding='utf-8'); assert all('def ' + n + '(' in t for n in ['test_constants_follow_the_measured_reads', 'test_first_read_the_reread_can_pull_into_range_is_admitted', 'test_first_read_out_of_reach_is_rejected', 'test_without_chars_per_second_the_word_rule_is_unchanged', 'test_production_settings_estimate_by_characters']), 'tests'; assert 'monkeypatch' not in t and 'mock' not in t.lower(), 'fixture'"` | 0 | Đủ 5 test bắt buộc, không chứa fixture monkeypatch hay mock |
| Bước 17 | `python -c "import ast, pathlib; t = pathlib.Path('src/controlplane/api/wiring/creative.py').read_text(encoding='utf-8'); fs = [n for n in ast.parse(t).body if isinstance(n, ast.FunctionDef) and n.name == 'build_creative_services']; assert len(fs) == 1, 'build_creative_services missing'; body = fs[0].body; branches = [s for s in body if isinstance(s, ast.If)]; assert branches, 'test branch missing'; rest = [s for s in body if s is not branches[0]]; names = [x.id for s in rest for x in ast.walk(s) if isinstance(x, ast.Name)] + [x.attr for s in rest for x in ast.walk(s) if isinstance(x, ast.Attribute)]; bad = [x for x in names if x.startswith(('Fake', 'InMemory', 'Memory'))]; assert not bad, bad; assert 'from src.' not in t, 'PW-W2'"` | 0 | AST hợp lệ, không dùng Fake/InMemory ngoài nhánh test, không import từ src. |
| Bước 18 | `python -c "import pathlib, re, tomllib; root = pathlib.Path('src/controlplane'); keys = set(tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['package-dir']); pk = set('.'.join(('controlplane',) + q.parent.relative_to(root).parts) for q in root.rglob('*.py') if q.stem.strip('_') == 'init' and 'node_modules' not in q.parts); miss = sorted(pk - keys); assert not miss, miss; ini = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['tool']['pytest']['ini_options']; assert 'src' in ini.get('pythonpath', []), 'pytest pythonpath must include src'; bad = [str(q) for d in ['src', 'tests'] for q in pathlib.Path(d).rglob('*.py') if 'node_modules' not in q.parts and re.search(r'(?m)^\s*(from|import)\s+src\.', q.read_text(encoding='utf-8', errors='replace'))]; assert not bad, bad"` | 0 | Cấu hình pyproject hợp lệ, pythonpath có src, không import tiền tố src. |

## Kết quả từng tiêu chí nghiệm thu

- **Tiêu chí 1 (Mã nguồn domain script, wiring và kiểm thử đơn vị mới):** ĐẠT
  - Đã cập nhật `src/creative/domain/script.py` với 3 hằng số, trường `chars_per_second` và hàm `count_chars`.
  - Hàm `build_script_version` duy trì hành vi cũ khi `chars_per_second` là `None` và chuyển sang ước lượng theo ký tự khi có giá trị.
  - Cập nhật `src/controlplane/api/wiring/creative.py` để truyền `SCRIPT_CHARS_PER_SECOND` ở production settings mà không thay đổi cấu hình profile hay prompt.
  - Tệp kiểm thử `tests/unit/creative/test_d08_fix1_char_estimate.py` vượt qua toàn bộ 20 bài kiểm thử đơn vị, kiểm thử tích hợp và kiểm thử toàn bộ `tests/unit` đạt 100%.
  - Được kiểm chứng qua các lệnh ở bước 10, 11, 12, 13, 14, 15, 16, 17, 18 (tất cả đều exit code 0).
- **Tiêu chí 2 (Báo cáo bằng chứng thực thi):** ĐẠT
  - Báo cáo tại `docs/delivery-evidence/d-08-fix1/report.md` nêu rõ nhóm lỗi `OI-CP7-11-Q3`, mã gói `D-08-FIX1`, danh sách tệp sửa đổi, bảng lệnh kiểm tra với exit code và dòng tổng kết pytest nguyên văn từ lần chạy thật.
  - Được kiểm chứng qua probe ở bước 20.

## Giới hạn

- Các hằng số `SCRIPT_CHARS_PER_SECOND = 13.81`, `FIRST_READ_SLOW_RATIO = 1.1087`, `FIRST_READ_FAST_RATIO = 0.9226` được đo trên một giọng đọc cụ thể (Kokoro af_heart) và một lô dữ liệu (lô 71973394); nếu thay đổi giọng đọc hoặc mức kẹp tốc độ thì cần tiến hành đo lường lại.
- Prompt vẫn nhắm mục tiêu theo số từ.
- Kịch bản bị loại do vượt ngưỡng sẽ tiêu tốn một lượt thử lại của AI (`ai.retry.max_attempts`).
- Lưới an toàn xử lý đuôi ngắn thuộc phạm vi gói `E-16-FIX3`.
- Không thay đổi `tools/launcher/prod/profile.json`, prompts.py, khoảng thời lượng 61-70 s, dải kẹp 0,85-1,15, không thêm thư viện bên ngoài và không sửa đổi bất kỳ tệp kiểm thử cũ nào.