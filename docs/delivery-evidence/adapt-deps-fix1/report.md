# ADAPT-DEPS-FIX1: Khoá av==18.1.0 cho faster-whisper 1.2.1 (nhóm lỗi R19)

## 1. Phạm vi và tệp đã sửa
- `pyproject.toml`
- `uv.lock`
- `docs/delivery-evidence/adapt-deps-fix1/report.md`

Không sửa `src/controlplane/pyproject.toml`, `src/controlplane/uv.lock`, `src/controlplane/requirements.lock`, mã nguồn hay site-packages.

## 2. Nhóm lỗi R19 và nguyên nhân
- Nhóm lỗi: `R19` (ghi nhận tại CP7-6, RG-05, 30/10/2026 01:25Z).
- Nguyên nhân: Trong runtime khoá M2_CONTROLPLANE, gói `av==19.0.2` (được kéo gián tiếp bởi `faster-whisper==1.2.1`, vốn yêu cầu `av>=11`) không còn nhận tham số `metadata_errors` của `av.open` (theo PyAV CHANGELOG v19.0.0: "Remove the metadata_encoding and metadata_errors arguments to av.open"). Trong khi đó, `faster-whisper==1.2.1` (phiên bản mới nhất trên PyPI) vẫn gọi `av.open(input_file, mode="r", metadata_errors="ignore")` trong `faster_whisper.audio.decode_audio`. Vì vậy `src/voice/adapters/real_whisper_aligner.py` `RealWhisperAligner.align` khi truyền đường dẫn tệp WAV (`str(audio)`) cho `WhisperModel.transcribe` luôn hỏng `TypeError` tại `av.open`, khiến dây chuyền giọng nói thật không thể căn được thời gian.
- Cách khắc phục: Thêm khoá `constraint-dependencies = ["av==18.1.0"]` vào bảng `[tool.uv]` trong `pyproject.toml` gốc repo (`av 18.1.0` là bản cuối trước 19, có wheel `av-18.1.0-cp311-abi3-win_amd64.whl` cho Python 3.13.15 Windows); tuyệt đối không thêm `av` vào `[project].dependencies` (danh sách 10 phụ thuộc trực tiếp giữ nguyên vẹn). Tái tạo `uv.lock` bằng lệnh `uv lock` (không dùng `--upgrade`) của `uv 0.12.13`.

## 3. Lệnh đã chạy và kết quả thực tế

Bảng lệnh đã chạy từ các bước 2, 3, 4, 5, 6, 7 (toàn bộ kết quả chạy thật trên worktree):

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| 3a | `uv --version` | 0 | `uv 0.12.13 (0ebbd9274 2026-09-10 x86_64-pc-windows-msvc)` |
| 3b | `uv lock` | 0 | `Using CPython 3.13.15`<br>`Resolved 101 packages in 845ms`<br>`Updated av v19.0.2 -> v18.1.0` |
| 3c | `uv lock --locked` | 0 | `Using CPython 3.13.15`<br>`Resolved 101 packages in 2ms` |
| 2 | Probe `pyproject.toml` | 0 | `constraint-dependencies == ['av==18.1.0']`, `package` là False, `av` không là phụ thuộc trực tiếp. |
| 4 | Probe `uv.lock` | 0 | `av 18.1.0` có wheel win_amd64 abi3, hash sha256 hợp lệ, 10 thư viện chính giữ nguyên phiên bản, đủ 101 gói, `[manifest]` có constraint `av==18.1.0`. |
| 5 | Probe ADAPT-DEPS 1 | 0 | Danh sách `project.dependencies` khớp đúng 10 phụ thuộc ghim của ADAPT-DEPS. |
| 6 | Probe ADAPT-DEPS 2 | 0 | Versions, wheels (sha256) và closure đều đạt. |
| 7 | `git diff --check` | 0 | Sạch, không có cảnh báo khoảng trắng thừa. |

Chi tiết đầu ra nguyên văn các probe python trên interpreter khoá `1ca840a7`:

- Bước 2 (`pyproject.toml`):
  - Lệnh: `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); assert d['tool']['uv']['constraint-dependencies'] == ['av==18.1.0'], d['tool']['uv']; assert d['tool']['uv']['package'] is False; assert not any(x.split('==')[0].strip() == 'av' for x in d['project']['dependencies']), 'av not a direct dependency'"`
  - Exit code: 0
  - Đầu ra: (trống, không có ngoại lệ)

- Bước 4 (`uv.lock`):
  - Lệnh: `python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); p = dict((x['name'], x) for x in d['package']); a = p['av']; assert a['version'] == '18.1.0', a['version']; w = [y['url'] for y in a['wheels']]; assert any(u.endswith('av-18.1.0-cp311-abi3-win_amd64.whl') for u in w), 'win wheel'; assert all(re.fullmatch('sha256:[0-9a-f]{64}', y['hash']) for y in a['wheels']), 'hash'; assert all(p[k]['version'] == v for k, v in [('faster-whisper', '1.2.1'), ('kokoro-onnx', '0.4.9'), ('ctranslate2', '4.8.3'), ('onnxruntime', '1.31.0'), ('numpy', '2.5.4'), ('tokenizers', '0.23.3'), ('huggingface-hub', '2.2.0'), ('temporalio', '1.32.0'), ('psycopg', '3.3.5'), ('pydantic', '2.13.5')]), 'others changed'; assert len(p) == 101, len(p); c = d['manifest']['constraints']; assert dict(name='av', specifier='==18.1.0') in c, c"`
  - Exit code: 0
  - Đầu ra: (trống, không có ngoại lệ)

- Bước 5 (ADAPT-DEPS 1):
  - Lệnh: `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert sorted(x) == sorted(['google-api-python-client==2.200.0', 'google-auth-oauthlib==1.4.1', 'psycopg[binary]==3.3.5', 'psycopg-pool==3.3.1', 'pydantic==2.13.5', 'temporalio==1.32.0', 'feedparser==6.0.14', 'trafilatura==2.2.0', 'faster-whisper==1.2.1', 'kokoro-onnx==0.4.9']), x"`
  - Exit code: 0
  - Đầu ra: (trống, không có ngoại lệ)

- Bước 6 (ADAPT-DEPS 2):
  - Lệnh: `python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); p = {x['name']: x for x in d['package']}; n = {'feedparser': '6.0.14', 'trafilatura': '2.2.0', 'faster-whisper': '1.2.1', 'kokoro-onnx': '0.4.9'}; r = {x['name']: x['specifier'] for x in p['ai-auto-video-creator-m1-proof']['metadata']['requires-dist']}; h = [y['hash'] for x in p.values() if 'registry' in x['source'] for y in x.get('wheels', []) + ([x['sdist']] if 'sdist' in x else [])]; assert len(r) == 10 and all(r[k] == '==' + p[k]['version'] for k in r) and all(p[k]['version'] == v for k, v in n.items()), 'versions'; assert all(p[k]['dependencies'] and all(re.fullmatch('sha256:[0-9a-f]{64}', y['hash']) for y in p[k]['wheels']) for k in n), 'wheels'; assert all(re.fullmatch('sha256:[0-9a-f]{64}', i) for i in h) and all(y['name'] in p for x in p.values() for y in x.get('dependencies', [])), 'closure'"`
  - Exit code: 0
  - Đầu ra: (trống, không có ngoại lệ)

- Bước 7 (`git diff --check`):
  - Lệnh: `git diff --check`
  - Exit code: 0
  - Đầu ra: (trống, không có cảnh báo khoảng trắng thừa)

## 4. Phiên bản uv

Đầu ra nguyên văn từ lệnh `uv --version`:
```
uv 0.12.13 (0ebbd9274 2026-09-10 x86_64-pc-windows-msvc)
```

## 5. Diff tóm tắt của uv.lock

- Khối `[manifest]` được thêm vào với ràng buộc `constraints = [{ name = "av", specifier = "==18.1.0" }]`.
- Khối `[[package]] name = "av"` hạ phiên bản từ `19.0.2` xuống `18.1.0`, cập nhật sdist và wheels (bao gồm `av-18.1.0-cp311-abi3-win_amd64.whl`), toàn bộ hash dạng sha256 đầy đủ 64 chữ số hex.
- Toàn bộ 10 thư viện chính và 90 gói phụ thuộc khác giữ nguyên phiên bản, tổng số gói giữ nguyên 101 gói.

Trích đoạn `git diff -U0 -- uv.lock`:
```diff
diff --git a/uv.lock b/uv.lock
index a4e2f1c..594c971 100644
--- a/uv.lock
+++ b/uv.lock
@@ -4,0 +5,3 @@ requires-python = "==3.13.15"
+[manifest]
+constraints = [{ name = "av", specifier = "==18.1.0" }]
+
@@ -83 +86 @@ name = "av"
-version = "19.0.2"
+version = "18.1.0"
@@ -85 +88 @@ source = { registry = "https://pypi.org/simple" }
-sdist = { url = "https://files.pythonhosted.org/packages/23/01/76b6bf563fe907597cf58f10d10168e93fe588b6db9f2658db87e87efa7e/av-19.0.2.tar.gz", hash = "sha256:bebbc52598886480f4d861c575dc2b020785d6c04e1308680ddcc545e1b94c66", size = 4277157, upload-time = "2026-10-21T03:45:30.799Z" }
+sdist = { url = "https://files.pythonhosted.org/packages/8d/f4/f22114d30d3435e38c6af2b4870f37b864403dca6ae7af747a289ce0a18e/av-18.1.0.tar.gz", hash = "sha256:47bfc286e1bc9de7ab4681fc2b575cd2460a66919d31ffe1bd5aa54fae531a28", size = 4451061, upload-time = "2026-08-12T22:28:18.761Z" }
@@ -87,9 +90,9 @@ wheels = [
-    { url = "https://files.pythonhosted.org/packages/4a/2f/f51f37820741134516e841053d5ecebf6350fbd451adcbff9ead96aa1244/av-19.0.2-cp312-abi3-macosx_11_0_x86_64.whl", hash = "sha256:f5f7bcf987567cd3f9b01f1c375c59bf59d8a5b98c9c5c154aeda7a11e0c5dce", size = 22627374, upload-time = "2026-10-21T03:44:28.296Z" },
...
+    { url = "https://files.pythonhosted.org/packages/33/b4/76ba21e46704f632004276b85289a1582e95f5eff760436d6149875a1881/av-18.1.0-cp311-abi3-win_amd64.whl", hash = "sha256:ea1480b7a8d5405cb5f382b344731bf125fd2c1c6fae3964f6c48595628387ff", size = 27595679, upload-time = "2026-08-12T22:27:35.177Z" },
...
```

## 6. Việc của Control sau khi gộp

- Sau khi candidate được gộp, Runtime Keeper sẽ dựng lại runtime khoá theo vân tay mới (do Control thực hiện, không thuộc phạm vi của Worker).
- Bằng chứng chạy thật của đường giải mã production đến từ CP7-6, CP7-7 và các lane dây chuyền sau đó khi chạy trên runtime mới.
