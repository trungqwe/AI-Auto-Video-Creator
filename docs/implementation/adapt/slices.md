# Slice adapter thật và đấu nối sản xuất — IMPL-PLAN-ADAPT

Nguồn: `docs/implementation/adapt/plan.md`. Mười ba slice do Control biên dịch; `ADAPT-DEPS` là `dependency_slice`, `ADAPT-WIRE` và `ADAPT-PROD` là `convergence_slice` (sở hữu composition root), các slice còn lại là `work_package_slice`. Mọi slice chờ `CP-2B-DEPS` và `USER-CKPT-D9-D10` (cổng chờ user, không phải slice); `GATE-<mã>` là cổng thả của gói đã đạt Auditor PASS.

## Quy tắc chung cho mọi slice

- Chỉ sửa tệp trong `ownedPaths`; không sửa migration, composition root ngoài slice được giao, lockfile ngoài `ADAPT-DEPS`, `tests/m2`, `ui/dist`, state machine, contract, `docs/milestones/**/evidence/**`; không đổi chữ ký port; không viết lại adapter đã nghiệm thu.
- Tệp adapter mới ở `adapters/` của A, D, E, F luôn là `real_<tên>.py`, không thư mục glob; mô-đun mới ở `src/controlplane` chỉ nằm trong gói đã khai trong `pyproject.toml`.
- Không gọi dịch vụ thật, không mở `Credentials/`, không tải trọng số trong test; test dùng fixture CP1 và fake, ghi nhãn test-only. Phần cần Drive, OAuth, AI thật, GPU hay chạy 12 giờ chỉ kiểm ở CP7 (plan.md mục 8).
- Test-first: thấy RED do assertion đúng oracle (ImportError, thiếu binary hay thiếu tệp không phải RED hợp lệ) rồi implement tới GREEN; mọi giá trị tham số lấy từ hồ sơ production (plan.md mục 7), không hằng số ẩn; import root `src/`, không tiền tố `src.`.
- Bằng chứng ở `docs/delivery-evidence/adapt-<mã chữ thường>/report.md`; `testCommands` chạy bằng interpreter khoá của runtime D9; mỗi mục slice theo thứ tự kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance, testCommands và không quá 3000 ký tự.

### ADAPT-DEPS: Khóa bốn thư viện adapter vào pyproject.toml và uv.lock gốc

- kind: dependency_slice
- ownedPaths:
  - `pyproject.toml`
  - `uv.lock`
  - `docs/delivery-evidence/adapt-deps/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `IMPL-PLAN-ADAPT`
- resourceLocks: `LOCK-DEPENDENCY-UNIVERSE`, `LOCK-CONVERGENCE`
- bindingRefs: không có binding riêng; bám plan.md mục 3
- acceptance:
  - requirement: Thêm vào `dependencies` của `pyproject.toml` gốc đúng bốn dòng `feedparser==6.0.14`, `trafilatura==2.2.0`, `faster-whisper==1.2.1`, `kokoro-onnx==0.4.9` (lệnh làm việc thắng số ở đây), rồi chạy `uv lock` để `uv.lock` ghim mọi phụ thuộc bắc cầu kèm sha256 từng wheel. Không chép tay khối lock: lane không chạy được `uv lock` thì BLOCKED kèm evidence. Không `latest`, dải phiên bản, gói thứ năm, nâng gói đã khóa, đổi `requires-python`, sửa `src/controlplane/pyproject.toml` hay `requirements.lock`. Thiếu wheel Python 3.13.15 trên Windows thì BLOCKED.
    instrument: probe `tomllib`: `pyproject.toml` có đúng mười dependency gồm bốn gói ghim `==` và sáu gói cũ giữ nguyên; `uv.lock` có khối `[[package]]` đúng phiên bản và wheel sha256 của bốn gói, phụ thuộc bắc cầu đều có khối; cổng nhận: Control chạy `uv lock --locked` (uv ngoài danh sách lệnh của Worker).
    counterexample: dải phiên bản; thêm `av`, `whisperx` hay `kokoro`; nâng `temporalio`; sửa tay `uv.lock`; ghi phiên bản bịa.
- testCommands:
  - `git diff --check`
  - `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert sorted(x) == sorted(['google-api-python-client==2.200.0', 'google-auth-oauthlib==1.4.1', 'psycopg[binary]==3.3.5', 'psycopg-pool==3.3.1', 'pydantic==2.13.5', 'temporalio==1.32.0', 'feedparser==6.0.14', 'trafilatura==2.2.0', 'faster-whisper==1.2.1', 'kokoro-onnx==0.4.9']), x"`
  - `python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); p = {x['name']: x for x in d['package']}; n = {'feedparser': '6.0.14', 'trafilatura': '2.2.0', 'faster-whisper': '1.2.1', 'kokoro-onnx': '0.4.9'}; r = {x['name']: x['specifier'] for x in p['ai-auto-video-creator-m1-proof']['metadata']['requires-dist']}; h = [y['hash'] for x in p.values() if 'registry' in x['source'] for y in x.get('wheels', []) + ([x['sdist']] if 'sdist' in x else [])]; assert len(r) == 10 and all(r[k] == '==' + p[k]['version'] for k in r) and all(p[k]['version'] == v for k, v in n.items()), 'versions'; assert all(p[k]['dependencies'] and all(re.fullmatch('sha256:[0-9a-f]{64}', y['hash']) for y in p[k]['wheels']) for k in n), 'wheels'; assert all(re.fullmatch('sha256:[0-9a-f]{64}', i) for i in h) and all(y['name'] in p for x in p.values() for y in x.get('dependencies', [])), 'closure'"`

### ADAPT-A: Adapter RSS, Atom, bài và ảnh thật của nguồn thu thập (A)

- kind: work_package_slice
- ownedPaths:
  - `src/source_ingestion/adapters/real_http_transport.py`
  - `src/source_ingestion/adapters/real_feed_source.py`
  - `src/source_ingestion/adapters/real_media_fetch.py`
  - `tests/integration/adapt/a/test_adapt_a_*.py`
  - `docs/delivery-evidence/adapt-a/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `ADAPT-DEPS`, `A-12`, `C-03`, `GATE-CP-2D-REGISTRY`
- resourceLocks: `LOCK-SRC-SOURCE-INGESTION`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`; binding A→C của `GATE-CP-2D-REGISTRY` (tên tệp chưa có; tới khi có, giao C bằng `DiscoveryObservation`)
- acceptance:
  - requirement: (1) `real_http_transport.py`: `Transport` thật cho `SecureFetcher`: chỉ `GET`, `http.client` nối đúng `addresses` đã ghim (SNI, Host là `host`), không theo redirect, không đọc proxy hay biến môi trường, timeout và body theo chunk. (2) `real_feed_source.py`: `SourceAdapter` cho `rss_feed` và `atom_feed`; feed và bài tải qua `SecureFetcher` (`secure_fetch.py`), `feedparser.parse` và `trafilatura.extract` chỉ trên bytes đã tải (không để thư viện tự mở mạng), giữ raw bytes và phiên bản thư viện trong `technical_fields`; `resume_from_checkpoint`, `supplemental_search` trả `CapabilityUnavailable`; lỗi mạng trả `ProblemDetail`, không ném. (3) `real_media_fetch.py`: tải ảnh gắn với bài (enclosure, `media:content`, ảnh chính) qua cùng `SecureFetcher` với `FetchPolicy` ảnh, tính sha256, ghi vào staging root từ cấu hình, dựng `DiscoveryObservation` cho C; quá giới hạn hoặc ngoài SSRF policy thì từ chối.
    instrument: `test_adapt_a_adapters.py`: transport giả và fixture feed, HTML nhúng trong test; riêng transport thật kiểm trên máy chủ loopback dựng trong test (truyền `addresses` thẳng): địa chỉ ghim, timeout, body quá lớn, redirect không tự theo.
    counterexample: feedparser hay trafilatura tự mở mạng; bỏ SSRF policy ở hop redirect; tải ảnh không qua `SecureFetcher`; cookie hay token vào log; gọi mạng thật trong test; tiền tố `src.`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cacheprovider`
  - `python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_http_transport.py', 'real_feed_source.py', 'real_media_fetch.py']); assert 'feedparser' in t and 'trafilatura' in t and 'SecureFetcher' in t and 'from src.' not in t, 'adapter A'"`

### ADAPT-D: AIInvocationPort trên RoutedInvocationService qua 9Router (D)

- kind: work_package_slice
- ownedPaths:
  - `src/creative/adapters/real_ai_invocation.py`
  - `src/creative/adapters/real_route_executor.py`
  - `src/controlplane/config/adapter.py`
  - `tests/integration/adapt/d/test_adapt_d_*.py`
  - `docs/delivery-evidence/adapt-d/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `J-18`, `D-17`
- resourceLocks: `LOCK-SRC-CREATIVE`, `LOCK-SRC-CONFIG-SECURITY`
- bindingRefs: `docs/parallel-delivery/bindings/j-provider-route.json`, `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
- acceptance:
  - requirement: (1) `real_ai_invocation.py`: lớp cài `AIInvocationPort` (`src/creative/ports/ai.py`) gọi `RoutedInvocationService.invoke` (J-18), không tự resolve route, không nhận secret, trả `AIInvocationResult` kèm record đã redact; `WAITING_PROVIDER` hoặc `BUDGET_BLOCKED` thành kết quả chờ có thể thử lại (không phải lỗi cuối) để G đặt job chờ và chạy tiếp khi hạn mức hồi; chi phí ghi qua `CostLedgerPort` của J (`monthly_limit` 50 USD, `hard_stop` bật, từ cấu hình). (2) `real_route_executor.py` (mô-đun mới trong `src/creative/adapters/`): `ProviderExecutorPort` gọi 9Router bằng `NineRouterHTTPAdapter`; endpoint, timeout, retry, backoff từ cấu hình, credential chỉ qua `credential_method`. (3) `adapter.py`: thêm đường dựng `ApprovedEndpointRegistry` từ danh sách endpoint của cấu hình (BL-CV-04); giữ `DEFAULT_APPROVED_ENDPOINTS` làm nền test, không đổi hành vi cũ; mã production không chứa `mock-9router`.
    instrument: `test_adapt_d_ai.py` với transport HTTP giả: SUCCEEDED, 429 rồi hết hạn mức thành kết quả chờ, `hard_stop` chặn, endpoint ngoài danh sách bị từ chối, record không chứa secret; `tests/unit/security/test_http_router_adapter.py` vẫn xanh không sửa.
    counterexample: gọi 9Router thật; bỏ qua `RoutedInvocationService`; coi hết hạn mức là FAILED cuối; hard-code endpoint hay 50 USD; sửa `test_http_router_adapter.py`; secret trong record hay log.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/creative/adapters/real_ai_invocation.py', 'src/creative/adapters/real_route_executor.py']); assert 'RoutedInvocationService' in t and 'mock-9router' not in t and 'from src.' not in t, 'adapter D'"`

### ADAPT-E: TTS Kokoro cục bộ và aligner faster-whisper (E)

- kind: work_package_slice
- ownedPaths:
  - `src/voice/adapters/real_kokoro_tts.py`
  - `src/voice/adapters/real_whisper_aligner.py`
  - `tests/integration/adapt/e/test_adapt_e_*.py`
  - `docs/delivery-evidence/adapt-e/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `ADAPT-DEPS`, `E-15`, `E-18`, `J-18`
- resourceLocks: `LOCK-SRC-VOICE`
- bindingRefs: `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`, `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: (1) `real_kokoro_tts.py`: `TtsEnginePort` (`src/voice/ports/tts.py`) chạy `kokoro_onnx` cục bộ, không mạng; nạp `kokoro-v1.0.onnx` và `voices-v1.0.bin` từ thư mục trọng số ngoài cây Git, kiểm sha256 theo `tools/launcher/prod/model-weights.lock.json` trước khi nạp (thiếu hoặc lệch thì `TtsProviderError` không thể thử lại, không tải ngầm); giọng, tốc độ, ngôn ngữ, sample rate từ cấu hình; ghi WAV mono PCM vào staging, trả `TtsSynthesis`; lỗi runtime là `TtsProviderError` đã redact. (2) `real_whisper_aligner.py`: `AlignerPort` (`src/voice/ports/aligner.py`) dùng `faster_whisper.WhisperModel` nạp từ thư mục cục bộ với `word_timestamps=True`, căn từ phiên âm vào `script_text` theo tokenization policy của E, trả `AlignmentResult` (`start_ms`, `end_ms`, `confidence`, `aligner_revision` gồm phiên bản thư viện và hash model); từ không khớp được đánh dấu và đếm, vượt `max_unmatched_word_ratio` thì `AlignerError`, không bịa mốc.
    instrument: `test_adapt_e_tts_aligner.py` thay lớp model ở biên thư viện bằng đối tượng giả test-only và WAV tự tạo bằng `wave`: lệch sha256 bị từ chối, không truy cập mạng, mốc đơn điệu, từ không khớp; nghe thật và độ chính xác thuộc CP7.
    counterexample: tải trọng số trong test; bỏ kiểm sha256; gọi Gemini TTS; mốc thời gian chia đều thay vì từ model; trọng số trong cây Git; tiền tố `src.`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider`
  - `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_kokoro_tts.py', 'real_whisper_aligner.py']); assert 'kokoro_onnx' in t and 'faster_whisper' in t and 'sha256' in t and 'from src.' not in t, 'adapter E'"`

### ADAPT-E-MEDIA: An toàn ảnh bằng LLM thị giác, boxblur và công cụ FFmpeg (E)

- kind: work_package_slice
- ownedPaths:
  - `src/voice/adapters/real_ffmpeg_media_tool.py`
  - `src/voice/adapters/real_llm_image_safety.py`
  - `tests/integration/adapt/e_media/test_adapt_e_media_*.py`
  - `docs/delivery-evidence/adapt-e-media/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `E-15`, `J-18`, `ADAPT-D`
- resourceLocks: `LOCK-SRC-VOICE`
- bindingRefs: `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`, `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: (1) `real_ffmpeg_media_tool.py`: `MediaToolPort` (`src/voice/ports/media_tool.py`), `TransformPort` (`src/voice/domain/image_transform.py`) và `ProbePort` (`src/voice/ports/probe.py`) bằng `subprocess.run` danh sách đối số (không shell) trên `ffmpeg.exe` và `ffprobe.exe` cùng thư mục; trước khi chạy kiểm sha256 của `ffmpeg.exe` bằng `pins.ffmpeg.sha256` trong `tools/runtime/runtime.lock.json` (lệch hoặc `BLOCKED` thì từ chối), kiểm `ffprobe -version` cùng chuỗi build; có timeout, ghi tệp ra tên mới, không ghi đè đầu vào, trả `ToolOutcome` kèm sha256 đầu ra; che vùng bằng `boxblur` theo `TransformRegion`. (2) `real_llm_image_safety.py`: detector gọi AI thị giác qua route J (`ai_role` `image_safety`), ép đầu ra JSON có kiểu (category, confidence, vùng chuẩn hóa), phân loại theo `ImageSafetyPolicy` (plan.md 7.3); sai kiểu, quá hạn hay lỗi route là `DETECTION_FAILED` (fail-closed); ảnh chỉ đi tới route J, nội dung ảnh không vào log.
    instrument: `test_adapt_e_media_tools.py`: `runtime.lock.json` test-only trong thư mục tạm cho kiểm sha256 (khớp, lệch, BLOCKED), đối số lệnh dựng đúng, JSON sai kiểu thành `DETECTION_FAILED`; FFmpeg thật và ảnh nhạy cảm thật thuộc CP7-E-03, CP7-E-04.
    counterexample: `shell=True`; bỏ kiểm sha256; coi lỗi detector là an toàn; ảnh gửi ra ngoài route J; dùng `ffmpeg` trong PATH; ghi đè đầu vào.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q -p no:cacheprovider`
  - `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_media_tool.py', 'real_llm_image_safety.py']); assert 'boxblur' in t and 'runtime.lock.json' in t and 'shell=True' not in t and 'from src.' not in t, 'adapter E media'"`

### ADAPT-F: Render NVENC, phụ đề libass và QC ffprobe (F)

- kind: work_package_slice
- ownedPaths:
  - `src/render/adapters/real_ffmpeg_renderer.py`
  - `src/render/adapters/real_ffprobe_probe.py`
  - `tests/integration/adapt/f/test_adapt_f_*.py`
  - `docs/delivery-evidence/adapt-f/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `F-13`, `F-18`
- resourceLocks: `LOCK-SRC-RENDER`, `LOCK-DESKTOP-GPU`
- bindingRefs: `docs/parallel-delivery/bindings/f-render-package.json`, `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- acceptance:
  - requirement: (1) `real_ffmpeg_renderer.py`: `RendererPort` và `OutputObservationPort` (`src/render/ports/renderer.py`) chạy một `RenderCommandSpec` bằng `subprocess.run` danh sách đối số (không shell) trên `ffmpeg.exe` đã kiểm sha256 theo `pins.ffmpeg.sha256` của `tools/runtime/runtime.lock.json` (lệch hoặc `BLOCKED` thì từ chối): 1080x1920, 30 fps, `h264_nvenc` (encoder không khởi tạo được thì thử một lần bằng `libx264` và ghi encoder đã dùng vào metrics), AAC, MP4 `+faststart`, phụ đề ASS qua bộ lọc `subtitles` (libass), tham số theo preset production (plan.md 7.4); quá hạn ném `RendererTimeout`; đầu ra ghi tệp tạm rồi đổi tên nguyên tử sang `output_ref` chỉ khi ffmpeg thoát 0; giữ `LOCK-DESKTOP-GPU` qua `GpuLeasePort`. (2) `real_ffprobe_probe.py`: `OutputProbePort` (`src/render/ports/output_probe.py`) đo bằng `ffprobe -print_format json`: `decodable`, `duration_ms`, kích thước, `fps`, codec, container, âm thanh; không đo được thì `None`, không đoán.
    instrument: `test_adapt_f_render.py` dùng tệp `ffmpeg` giả là script Python test-only trong thư mục tạm: dựng lệnh, mã thoát, timeout, đổi tên nguyên tử, dự phòng `libx264`, sha256 lệch hoặc BLOCKED; JSON ffprobe mẫu cho `OutputMeasurements`; render NVENC thật thuộc CP7-F-01.
    counterexample: `shell=True`; ghi thẳng `output_ref` khi ffmpeg lỗi; bỏ kiểm sha256; NVENC lỗi mà báo thành công; tự đoán `fps`; không trả GPU lease khi lỗi.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider`
  - `python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_renderer.py', 'real_ffprobe_probe.py']); assert 'h264_nvenc' in t and 'libx264' in t and 'subtitles' in t and 'shell=True' not in t and 'from src.' not in t, 'adapter F'"`

### ADAPT-J: Luồng OAuth một lần qua loopback và token qua broker DPAPI (J)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/security/oauth_google_loopback.py`
  - `src/controlplane/infrastructure/security/oauth_drive_token.py`
  - `tests/integration/adapt/j/test_adapt_j_*.py`
  - `docs/delivery-evidence/adapt-j/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `J-17`, `J-18`, `GATE-PERSIST-J`
- resourceLocks: `LOCK-SRC-CONFIG-SECURITY`
- bindingRefs: `docs/parallel-delivery/bindings/j-provider-route.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: (1) `oauth_google_loopback.py`: luồng OAuth một lần bằng `google-auth-oauthlib`: máy chủ loopback `127.0.0.1` cổng ngẫu nhiên, PKCE và `state`, scope duy nhất `https://www.googleapis.com/auth/drive.file`, chờ tối đa `oauth_consent_timeout_seconds`, đóng cổng ngay khi xong hoặc quá hạn; client ID và secret của ứng dụng đọc từ tệp JSON user đặt ngoài cây Git (đường dẫn từ cấu hình, không in nội dung); refresh token ghi qua `SecretStorePort` (`DpapiSecretStore`) với `secret_ref` `drive-primary-oauth`, không in, không log, không vào PostgreSQL (chỉ metadata handle). (2) `oauth_drive_token.py`: trả access token ngắn hạn (`max_ttl_seconds` từ cấu hình) cho `credential_method` của broker, làm mới khi hết hạn, từ chối khi handle `REVOKED`; refresh token không rời broker.
    instrument: `test_adapt_j_oauth.py` với máy chủ OAuth giả cục bộ test-only: `state` sai bị từ chối, quá hạn thì đóng cổng, token ghi vào `DpapiSecretStore` ở thư mục tạm, token không xuất hiện trong stdout, log hay audit record; consent thật bằng tài khoản thật thuộc CP7-J-01 (điểm dừng user thứ nhất).
    counterexample: scope rộng hơn `drive.file`; cổng loopback còn mở sau khi xong; token in ra console; refresh token trong PostgreSQL hay biến môi trường; thiếu `state` hay PKCE; test gọi `accounts.google.com`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider`
  - `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/security'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['oauth_google_loopback.py', 'oauth_drive_token.py']); assert 'drive.file' in t and 'SecretStorePort' in t and 'from src.' not in t, 'adapter J'"`

### ADAPT-I: Adapter Google Drive thật (I)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/storage/drive_object_store.py`
  - `tests/integration/adapt/i/test_adapt_i_*.py`
  - `docs/delivery-evidence/adapt-i/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `I-04`, `J-17`, `ADAPT-J`
- resourceLocks: `LOCK-SRC-STORAGE`
- bindingRefs: `docs/parallel-delivery/bindings/i-artifact-version.json`, `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: Mô-đun mới `drive_object_store.py` cài `CloudObjectPort` (`src/controlplane/application/storage_meta/cloud_persist.py`) bằng `google-api-python-client`: `reserve_object_id` cấp file ID trước (`files.generateIds`) theo `namespace_ref`; `upload` là upload resumable theo chunk vào đúng file ID đã cấp (thử lại không tạo tệp thứ hai); HTTP 409 ném `ObjectAlreadyExistsError`; phiên hết hạn (404, 410 hoặc quá `session_ttl_seconds`) thì mở phiên mới cùng file ID; hết retry vì timeout thì ném `TimeoutError` để I ghi `OUTCOME_UNKNOWN`; `lookup` trả `IntegrityObservation` từ metadata Drive, và khi Drive thiếu checksum khớp sha256 thì tải lại tệp theo chunk để tính sha256. Access token chỉ lấy qua `credential_method` của broker J, không log; chunk, timeout, retry, backoff, placement, quota từ cấu hình (plan.md 7.5); từ chối upload khi dự phóng dung lượng trống dưới `quota_reserve_ratio`.
    instrument: `test_adapt_i_drive.py` với dịch vụ Drive giả ở tầng transport của thư viện, test-only: 409, phiên hết hạn, thiếu checksum phải tải lại, timeout thành `OUTCOME_UNKNOWN`, token không xuất hiện trong log; Drive thật và token thật thuộc CP7-I-01.
    counterexample: tạo tệp mới mỗi lần thử lại; coi 409 là lỗi cuối; tin md5 thay sha256; tải cả tệp vào RAM; log token; gọi Drive thật trong test; giữ refresh token trong adapter.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/storage/drive_object_store.py').read_text(encoding='utf-8'); assert 'CloudObjectPort' in t and 'ObjectAlreadyExistsError' in t and 'generateIds' in t and 'from src.' not in t, 'adapter I'"`

### ADAPT-CONFIG: Hồ sơ cấu hình production, nguồn RSS, bộ hook và khóa trọng số

- kind: work_package_slice
- ownedPaths:
  - `tools/launcher/prod/profile.json`
  - `tools/launcher/prod/sources.json`
  - `tools/launcher/prod/hooks.json`
  - `tools/launcher/prod/model-weights.lock.json`
  - `tests/integration/adapt/config/test_adapt_config_*.py`
  - `docs/delivery-evidence/adapt-config/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `J-09`, `J-18`
- resourceLocks: `LOCK-COMPOSITION-ROOT`
- bindingRefs: `docs/parallel-delivery/bindings/j-provider-route.json`; bám plan.md mục 7
- acceptance:
  - requirement: Tạo `profile.json` (UTF-8) chứa mọi tham số ở plan.md mục 7.1 đến 7.6 (A, AI và J, E, F, I, G, múi giờ `Asia/Ho_Chi_Minh` lưu UTC), mỗi tham số là đối tượng `value`, `reason`, `basis` (`DECIDED`, `MEASURED` hoặc `CONSERVATIVE_DEFAULT`), không `null`, `budget.monthly_limit` bằng 50 và `hard_stop` là true. `sources.json`: bảy nguồn RSS của mục 7.7 kèm Tier và cờ bật. `hooks.json`: hook hình, hook âm thanh và ảnh nền seed của mục 7.8 (tự tạo, kèm công thức sinh). `model-weights.lock.json`: URL https cố định và sha256 từng tệp trọng số của mục 7.9, hoặc `null` kèm `BLOCKED`; không bịa hash. Không đặt dữ liệu lớn trong cây Git.
    instrument: `test_adapt_config_profile.py` đọc JSON bằng stdlib: đủ nhóm tham số, mọi mục có `reason` không rỗng, 50 USD và `hard_stop` đúng, đúng năm preset, nguồn RSS đều `https`, lock trọng số đúng cấu trúc, không khóa nào chứa `secret`, `token` hay `password`.
    counterexample: tham số thiếu lý do; `null` thay giá trị; URL `http`; bí mật hay khóa API trong profile; media hay trọng số trong cây Git; hash trọng số bịa.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider`
  - `python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [json.loads((d / n).read_text(encoding='utf-8')) for n in ['profile.json', 'sources.json', 'hooks.json', 'model-weights.lock.json']]; assert 'Asia/Ho_Chi_Minh' in (d / 'profile.json').read_text(encoding='utf-8'), 'profile'"`

### ADAPT-WIRE: Đấu nối từng phân hệ với adapter thật và kho PostgreSQL

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/api/wiring/**`
  - `tests/integration/adapt/wire/test_adapt_wire_*.py`
  - `docs/delivery-evidence/adapt-wire/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `CP-4-WIRING`, `GATE-CP-5-COMPLETION`, `ADAPT-A`, `ADAPT-D`, `ADAPT-E`, `ADAPT-E-MEDIA`, `ADAPT-F`, `ADAPT-I`, `ADAPT-J`, `ADAPT-CONFIG`
- resourceLocks: `LOCK-COMPOSITION-ROOT`
- bindingRefs: `docs/parallel-delivery/bindings/g-activity-execution.json`, `docs/parallel-delivery/bindings/j-provider-route.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: Với mỗi mô-đun `src/controlplane/api/wiring/<phân hệ>.py` mà `CP-4-WIRING` đã tạo (liệt kê bằng tìm `def build_.*_services` trong thư mục đó), mở rộng `build_<phân hệ>_services(manager, config)` để ở hồ sơ production dựng service bằng adapter thật: A (`real_feed_source`, `real_media_fetch`, `real_http_transport`), D (`real_ai_invocation` trên `RoutedInvocationService`), E (`real_kokoro_tts`, `real_whisper_aligner`, `real_ffmpeg_media_tool`, `real_llm_image_safety`), F (`real_ffmpeg_renderer`, `real_ffprobe_probe`), I (`drive_object_store`), J (`oauth_google_loopback`, `oauth_drive_token`, broker DPAPI), luôn trên kho PostgreSQL của các `GATE-PERSIST-*` qua `TransactionManager`; hồ sơ test giữ adapter giả hoặc in-memory. Thêm `production_profile.py`: đọc `tools/launcher/prod/profile.json` thành cấu hình có kiểu, thiếu tham số thì ném lỗi gọi tên tham số (không default ẩn). Không tạo mô-đun phân hệ trùng; không import chéo adapter giữa phân hệ.
    instrument: `test_adapt_wire_services.py` dựng từng `build_<phân hệ>_services` với `TransactionManager` trên PostgreSQL 18.6 dùng một lần (mẫu persist plan.md mục 4; thiếu `M2_TEST_PG_DSN` thì fail `BLOCKED_EXTERNAL`): production nhận đúng kiểu adapter thật, test nhận đúng kiểu giả, thiếu một tham số thì lỗi gọi tên tham số.
    counterexample: service production vẫn dùng fake; adapter tự đọc biến môi trường; mô-đun wiring trùng; kho tạm thay PostgreSQL; import `controlplane.application.test_driver`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider`
  - `python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert 'application.test_driver' not in t and 'from src.' not in t and 'real_' in t, 'wiring'"`

### ADAPT-SEED: Nhập nguồn RSS cơ sở, bộ hook và media seed qua dịch vụ ứng dụng

- kind: work_package_slice
- ownedPaths:
  - `tools/launcher/prod/seed/make_seed_media.py`
  - `tools/launcher/prod/seed/import_seed.py`
  - `tests/integration/adapt/seed/test_adapt_seed_*.py`
  - `docs/delivery-evidence/adapt-seed/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `ADAPT-WIRE`, `ADAPT-CONFIG`, `GATE-PERSIST-A`, `GATE-PERSIST-C`
- resourceLocks: `LOCK-COMPOSITION-ROOT`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `docs/parallel-delivery/bindings/c-d-media-candidates.json`
- acceptance:
  - requirement: `make_seed_media.py` tự tạo media seed tối thiểu của plan.md mục 7.8 vào thư mục dữ liệu ngoài cây Git theo `hooks.json`: ảnh PNG 1080x1920 sinh bằng stdlib, hook âm thanh WAV sinh bằng `wave`, hook hình bằng ffmpeg đã ghim sha256 với nguồn `lavfi`; in sha256 từng tệp. `import_seed.py` nhập `sources.json` bằng dịch vụ ứng dụng của A (đăng ký nguồn kèm Tier) và `hooks.json` cùng media seed bằng dịch vụ ứng dụng của C (`register_discovery`, `import_hook` của `src/catalog/application`) qua `build_*_services` của `ADAPT-WIRE`; không đi qua UI hay HTTP; chạy lại không nhân đôi (idempotent theo locator canonical, `discovery_id`, `hook_id`); ảnh tải kèm bài giữ `rights_status` `UNVERIFIED`.
    instrument: `test_adapt_seed_import.py` chạy `import_seed` hai lần trên PostgreSQL dùng một lần: số nguồn, hook và tài sản không đổi ở lần hai; mọi nguồn `https`; sha256 media sinh ra ổn định giữa hai lần; thư mục dữ liệu nằm ngoài cây Git.
    counterexample: media tải từ internet không rõ quyền; tệp seed trong cây Git; nhập qua HTTP của UI; lần hai nhân đôi dòng; gọi RSS thật.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_seed.py').read_text(encoding='utf-8'); assert 'register_discovery' in t and 'import_hook' in t and 'urllib' not in t, 'seed'"`

### ADAPT-PROD: Hồ sơ production, src/main.py, TLS loopback và capability một lần

- kind: convergence_slice
- ownedPaths:
  - `src/main.py`
  - `src/controlplane/api/wiring/production.py`
  - `tests/integration/adapt/prod/test_adapt_prod_*.py`
  - `docs/delivery-evidence/adapt-prod/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `CP-4-WIRING`, `GATE-CP-5-COMPLETION`, `GATE-CP-6-WORKFLOW`, `ADAPT-WIRE`, `ADAPT-CONFIG`
- resourceLocks: `LOCK-COMPOSITION-ROOT`
- bindingRefs: `docs/parallel-delivery/bindings/domain-event-envelope.json`, `docs/parallel-delivery/bindings/g-activity-execution.json`
- acceptance:
  - requirement: (1) Mở rộng `src/main.py` (CP-4-WIRING chỉ đọc cấu hình, dựng `TransactionManager`, gọi `create_app`; BL-CV-06): nhận hồ sơ `production` hoặc `test` (mặc định `test`); ở `production` nạp profile, gọi các `build_<phân hệ>_services` rồi `create_app`. (2) `production.py`: ASGI ghép `create_app` (`/v1/`) với phục vụ tĩnh `src/controlplane/ui/dist` trên một cổng loopback TLS `127.0.0.1` (uvicorn, chứng chỉ tự ký do launcher tạo), Origin cho phép đúng `https://127.0.0.1:<cổng>` và `https://localhost:<cổng>`; không import `controlplane.application.test_driver` nên mọi `/test-driver/*` trả 404; thêm `GET /launch?cap=` đổi capability một lần (`BootstrapCapabilityRegistry`, TTL tối đa 60 giây) thành cookie `cp_session` rồi chuyển hướng `/`; UI, `ui/dist` và spec M2 giữ nguyên byte. (3) Khởi động worker Temporal đăng ký sáu workflow của `GATE-CP-6-WORKFLOW`; «Dừng» chỉ dừng worker, việc dở tiếp tục khi chạy lại.
    instrument: `test_adapt_prod_app.py` dựng app production với `TestClient` trên PostgreSQL dùng một lần: `/test-driver/health` 404; `/launch` dùng một lần (lần hai 403), cookie `HttpOnly` và `Secure`; không có route đọc lại secret; `ui/dist` được phục vụ; chạy lại `tests/m2` và `tests/unit/control_ui` không đổi.
    counterexample: giữ route test-driver ở production; capability dùng lại được hay sống quá 60 giây; bind `0.0.0.0`; sửa `ui/dist` hay spec M2; hồ sơ production thiếu tham số vẫn khởi động.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/main.py', 'src/controlplane/api/wiring/production.py']); assert 'controlplane.application.test_driver' not in t and '/launch' in t and '127.0.0.1' in t and '0.0.0.0' not in t and 'from src.' not in t, 'prod'"`

### ADAPT-LAUNCH: Launcher Docker PostgreSQL và Temporal, worker và runbook

- kind: work_package_slice
- ownedPaths:
  - `tools/launcher/docker-compose.yml`
  - `tools/launcher/launcher.py`
  - `docs/runbook/runbook-v1.md`
  - `tests/integration/adapt/launch/test_adapt_launch_*.py`
  - `docs/delivery-evidence/adapt-launch/report.md`
- dependsOn: `CP-2B-DEPS`, `USER-CKPT-D9-D10`, `ADAPT-PROD`, `ADAPT-SEED`, `GATE-CP-6-WORKFLOW`
- resourceLocks: `LOCK-COMPOSITION-ROOT`
- bindingRefs: `docs/parallel-delivery/bindings/g-activity-execution.json`; bám plan.md mục 6
- acceptance:
  - requirement: (1) `docker-compose.yml`: `postgres` và `temporal` theo `image@sha256:<digest>` lấy từ `tools/runtime/runtime.lock.json` (không tag trần), cổng chỉ `127.0.0.1` (PostgreSQL `57028`, Temporal `7233`), volume đặt tên, không mở UI Temporal. (2) `launcher.py` (stdlib) với lệnh `start`, `stop`, `down`, `status`, `backup`, `restore`, `oauth`: `start` chạy compose, `MigrationRunner`, tạo chứng chỉ TLS ngoài cây Git, khởi worker, phát capability một lần và mở trình duyệt tại `/launch`; `stop` chỉ dừng worker (container và volume giữ nguyên), `start` lần sau tiếp tục việc dở; `oauth` hướng dẫn từng bước bằng tiếng Việt trên console rồi gọi luồng của `ADAPT-J`; không in bí mật. (3) `runbook-v1.md` tiếng Việt, sáu mục đánh số: khởi động, dừng, tiếp tục, sao lưu (`pg_dump` qua `docker exec`), khôi phục (recovery epoch mới), xử lý lỗi; kèm danh sách giá trị chọn không có căn cứ đo (plan.md mục 7) cần đo ở CP7.
    instrument: `test_adapt_launch_cli.py` với `subprocess` giả (không chạy Docker): lệnh compose dựng đúng, digest từ lock vào image, `stop` không gọi `down`, mọi cổng bind `127.0.0.1`; probe đếm tiêu đề `## ` của runbook.
    counterexample: image theo tag trần; cổng bind `0.0.0.0`; `stop` xóa container hay volume; bí mật in ra console; runbook thiếu một mục.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider`
  - `python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml').read_text(encoding='utf-8'); r = pathlib.Path('docs/runbook/runbook-v1.md').read_text(encoding='utf-8'); assert '@sha256:' in c and '127.0.0.1:' in c and '0.0.0.0' not in c and r.count(chr(10) + '## ') >= 6, 'launch'"`
