# ADAPT-DEPS: Khóa bốn thư viện adapter vào pyproject.toml và uv.lock

## 1. Phạm vi và tệp đã sửa
- `pyproject.toml`
- `uv.lock`
- `docs/delivery-evidence/adapt-deps/report.md`

Không sửa bất kỳ tệp nào ngoài 3 tệp thuộc owned paths ở trên (không sửa `src/controlplane/pyproject.toml`, `requirements.lock`, hay bất kỳ tệp nào trong `src/**`, `migrations/**`, `.ai-pm/**`, `docs/milestones/**/evidence/**`).

## 2. Thiết kế
- Ghim cứng chính xác bốn thư viện phụ thuộc mới vào mảng `project.dependencies` trong `pyproject.toml` gốc:
  - `feedparser==6.0.14`
  - `trafilatura==2.2.0`
  - `faster-whisper==1.2.1`
  - `kokoro-onnx==0.4.9`
- Tuyệt đối không dùng dải phiên bản, không dùng `latest`, không thêm gói thứ năm (không thêm `av`, `whisperx` hay `kokoro`), giữ nguyên sáu gói phụ thuộc cũ và không thay đổi cấu hình `requires-python = "==3.13.15"`, `[dependency-groups]`, `[tool.uv]`, `[tool.pytest.ini_options]`.
- Tệp `uv.lock` được sinh hoàn toàn tự động bằng công cụ `uv lock` thật trên môi trường máy chủ (không sửa tay hay bịa khối lock), đảm bảo tính toàn vẹn phụ thuộc bắc cầu, đầy đủ khối `[[package]]`, và mọi wheel đều có mã băm SHA-256 hợp lệ.

## 3. Lệnh đã chạy
Kết quả thực tế trên worktree (stdout/stderr và exit code):

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| Lệnh kiểm pyproject | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert sorted(x) == sorted(['google-api-python-client==2.200.0', 'google-auth-oauthlib==1.4.1', 'psycopg[binary]==3.3.5', 'psycopg-pool==3.3.1', 'pydantic==2.13.5', 'temporalio==1.32.0', 'feedparser==6.0.14', 'trafilatura==2.2.0', 'faster-whisper==1.2.1', 'kokoro-onnx==0.4.9']), x"` | 0 | Đạt assertion; 10 dependencies đúng danh mục ghim ==. |
| Sinh lock | `uv lock` | 0 | Using CPython 3.13.15, Resolved 101 packages in 1.47s. |
| Kiểm tra lock | `uv lock --locked` | 0 | Using CPython 3.13.15, Resolved 101 packages in 0.78ms (khớp khóa hoàn toàn). |
| Lệnh kiểm uv.lock | `python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); p = {x['name']: x for x in d['package']}; n = {'feedparser': '6.0.14', 'trafilatura': '2.2.0', 'faster-whisper': '1.2.1', 'kokoro-onnx': '0.4.9'}; r = {x['name']: x['specifier'] for x in p['ai-auto-video-creator-m1-proof']['metadata']['requires-dist']}; h = [y['hash'] for x in p.values() if 'registry' in x['source'] for y in x.get('wheels', []) + ([x['sdist']] if 'sdist' in x else [])]; assert len(r) == 10 and all(r[k] == '==' + p[k]['version'] for k in r) and all(p[k]['version'] == v for k, v in n.items()), 'versions'; assert all(p[k]['dependencies'] and all(re.fullmatch('sha256:[0-9a-f]{64}', y['hash']) for y in p[k]['wheels']) for k in n), 'wheels'; assert all(re.fullmatch('sha256:[0-9a-f]{64}', i) for i in h) and all(y['name'] in p for x in p.values() for y in x.get('dependencies', [])), 'closure'"` | 0 | Đạt assertions: versions (10 gói ghim đúng), wheels (đầy đủ sha256), closure (bao đóng toàn bộ dependency). |
| Kiểm tra diff | `git diff --check` | 0 | Sạch, không có cảnh báo khoảng trắng thừa. |

## 4. Phiên bản uv và số gói bắc cầu mới
- Phiên bản uv: `uv 0.12.13 (0ebbd9274 2026-09-10 x86_64-pc-windows-msvc)`
- Tổng số gói mới được thêm vào `uv.lock`: 55 gói (4 gói trực tiếp và 51 gói phụ thuộc bắc cầu).
- Danh sách 55 gói mới:
  `anyio`, `attrs`, `av`, `babel`, `click`, `cloudpickle`, `colorlog`, `courlan`, `csvw`, `ctranslate2`, `dateparser`, `dlinfo`, `espeakng-loader`, `faster-whisper`, `feedparser`, `feedparser-sgmllib`, `filelock`, `flatbuffers`, `fsspec`, `h11`, `hf-xet`, `htmldate`, `httpcore2`, `httpx2`, `httpx2-jsfetch`, `huggingface-hub`, `isodate`, `joblib`, `jsonschema`, `jsonschema-specifications`, `justext`, `kokoro-onnx`, `language-tags`, `lxml`, `lxml-html-clean`, `numpy`, `onnxruntime`, `phonemizer-fork`, `python-dateutil`, `pytz`, `pyyaml`, `rdflib`, `referencing`, `regex`, `rfc3986`, `rpds-py`, `segments`, `six`, `termcolor`, `tld`, `tokenizers`, `tqdm`, `trafilatura`, `truststore`, `tzlocal`.

## 5. Việc còn lại (backlog, không làm trong slice này)
- Cài đặt runtime phụ thuộc thật trên máy chủ / môi trường thực thi (do gói cài đặt runtime hoặc deployment đảm nhiệm).
- Tải mô hình cục bộ cho Kokoro TTS và mô hình faster-whisper (thuộc các gói thích ứng và nghiệm thu runtime riêng).
- Giữ nguyên ranh giới không can thiệp vào `src/controlplane/pyproject.toml` và `requirements.lock`.
