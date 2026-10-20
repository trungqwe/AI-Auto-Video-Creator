# Kế hoạch adapter thật và đấu nối sản xuất — IMPL-PLAN-ADAPT

- **Mã gói**: IMPL-PLAN-ADAPT (planning_package)
- **Ngày lập**: 20/10/2026
- **Cơ sở**: HEAD `d9d23586d3af1fa6b2f2b6b741f3bd77e2178ab7`. Trong cây này `RoutedInvocationService` (J-18) đã có ở `src/controlplane/application/config_security/routed_invocation.py`; chưa có `src/main.py`, `src/controlplane/api/wiring/` và `tools/runtime/runtime.lock.json`; migration cuối là `0008` (CP-3 chưa chạy).
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`), chỉ thị user duyệt Phần B ngày 18/10/2026 và bốn quyết định của user ngày 20/10/2026 trong ghi chú Control. `PRODUCTION_ACTIVATION_BLOCKED` vẫn hiệu lực tới nghiệm thu cuối; không push, không merge, không chạm main hay backup.
- **Nguồn chuẩn**: ghi chú Control và policy; `docs/implementation/convergence/plan.md` (mục 3, 4, 6, 7, 10, 12); kế hoạch phân hệ A, D, E, F, I, J (mục CP7 và mục thư viện); `docs/05-technology-research.md`; `docs/11-roadmap.md` §9 đến §13; binding CP1 trong `docs/parallel-delivery/bindings/`.
- **Slice**: `docs/implementation/adapt/slices.md` (13 slice `ADAPT-*`). **Bằng chứng**: `docs/delivery-evidence/impl-plan-adapt/report.md`.

## 1. Phạm vi và nguyên tắc

Kế hoạch đổi các port đã có (hiện chỉ có fake và in-memory dùng cho test logic) thành adapter thật chạy trên đúng một máy của user, rồi đấu nối chúng với kho PostgreSQL và workflow thành hồ sơ production. Nó nối tiếp convergence: `ADAPT-E` và `ADAPT-F` là phần adapter thật của `CONV-E-02` và `CONV-F-02`; A, D, I, J được thêm cùng cách.

1. v1 chỉ chạy trên máy này: PostgreSQL và Temporal chạy trong Docker và chỉ mở `127.0.0.1`; không cloud, không scheduler cloud.
2. Không đổi chữ ký port, không viết lại adapter đã nghiệm thu, không sửa contract hay state machine đã đóng băng (hai cạnh PUC-J-03 và YC-HT-I-04 thuộc `CP-3B-STATE-MACHINE`).
3. Adapter mới ở A, D, E, F là tệp mới `real_<tên>.py` trong `adapters/` của phân hệ, không dùng thư mục glob; ở `src/controlplane` chỉ thêm mô-đun mới trong gói đã khai trong `pyproject.toml` (gói mới cần `CP-2B-DEPS` khai).
4. Slice chỉ dùng fixture CP1 và fake; không gọi dịch vụ thật, không đọc `Credentials/` hay bí mật, không tải trọng số trong test. Phần cần Drive, OAuth, AI thật, GPU hay chạy 12 giờ chỉ kiểm ở CP7 (mục 8).
5. Không dùng mock để tuyên bố gate ngoài PASS (roadmap §13, mục Điều cấm).
6. Import root là `src/`, không tiền tố `src.`; phân hệ không import adapter của phân hệ khác, chỉ trao đổi qua port và tham chiếu chuỗi.
7. Cấm `latest` và dải phiên bản; mọi tham số production có giá trị kèm lý do (mục 7).

## 2. Quyết định đã có (không mở lại)

| Mã | Quyết định | Hệ quả cho kế hoạch |
| --- | --- | --- |
| U1 | User 20/10/2026: v1 chỉ chạy trên máy này; AI cho script và hook đi qua 9Router (tuyến Gemini đang dùng), không phát sinh chi phí thêm; hết hạn mức thì dừng và tự chạy tiếp khi hạn mức hồi | Không cloud; D gọi 9Router qua J; job chờ rồi tự chạy tiếp (mục 5.2) |
| U2 | User: đúng một tài khoản Google Drive thật; OAuth làm một lần; token chỉ đi qua broker DPAPI của J (J-17) | Điểm dừng user thứ nhất; `ADAPT-J`, `ADAPT-I`; kiểm thật ở CP7 |
| U3 | User: state machine chỉ mở hai cạnh PUC-J-03 và YC-HT-I-04 (ARCHITECTURE_CHANGE đã duyệt) | Thuộc `CP-3B-STATE-MACHINE`; adapter chỉ lưu trạng thái, không mã hóa cạnh mới |
| U4 | User: một đêm chạy thử 100 video trong 12 giờ, sau đó mẫu 10 video; user xem trên Dashboard khoảng 30 phút và nghiệm thu (gồm checkpoint M2) | Điểm dừng cuối của v1; thuộc CP7 (mục 8) |
| C1 | Control 20/10/2026 (D9): ghim FFmpeg gyan.dev, image `postgres:18.6`, image `temporalio/server:1.31.2` | Ba giá trị ở mục 3.2, do `CP-2B-DEPS` ghi vào `tools/runtime/runtime.lock.json` |
| C2 | Control: thêm đúng bốn gói `feedparser`, `trafilatura`, `faster-whisper` và thư viện TTS Kokoro; gói khác vẫn hoãn | `ADAPT-DEPS` (mục 3) |
| C3 | Control: TTS Kokoro cục bộ, căn thời gian bằng faster-whisper, an toàn ảnh bằng LLM thị giác qua tuyến AI cộng che bằng `boxblur` của FFmpeg | `ADAPT-E`, `ADAPT-E-MEDIA` |
| C4 | Control: hồ sơ production tắt route test-driver phía máy chủ, launcher cấp capability một lần, UI và spec M2 giữ nguyên; «Dừng» là dừng worker | `ADAPT-PROD`, `ADAPT-LAUNCH` (mục 6) |
| C5 | Control: nóng/xu hướng = số nguồn độc lập + độ mới + tier; RSS cơ sở sửa được trên UI; lưu bản gốc, tài sản dùng lại và đầu ra, xóa tệp tạm sau khi kiểm; AI `monthly_limit` 50 USD, `hard_stop` bật; múi giờ `Asia/Ho_Chi_Minh` lưu UTC | Mục 7 |

## 3. Thư viện và ghim runtime (ADAPT-DEPS)

### 3.1. Bốn gói thêm vào `pyproject.toml` và `uv.lock` gốc

Đây là ngoại lệ duy nhất của quy tắc «slice phân hệ không thêm thư viện». Chỉ `ADAPT-DEPS` (dependency_slice) được sửa `pyproject.toml` và `uv.lock`; slice khác chỉ import.

| Gói (`tên==phiên bản`) | Giấy phép | Dùng cho | Nguồn phiên bản |
| --- | --- | --- | --- |
| `feedparser==6.0.14` | BSD-2-Clause | parse RSS và Atom (A) | `docs/05-technology-research.md` dòng 116 (release 30-07-2026) |
| `trafilatura==2.2.0` | Apache-2.0 | trích nội dung chính (A) | `docs/05-technology-research.md` dòng 136 |
| `faster-whisper==1.2.1` | MIT | căn thời gian từng từ (E) | `docs/05-technology-research.md` dòng 227 |
| `kokoro-onnx==0.4.9` | MIT (trọng số Kokoro: Apache-2.0) | TTS cục bộ (E) | ứng viên của Orchestrator; tài liệu chưa ghi phiên bản (OI-ADAPT-01) |

**Điều kiện hiệu lực**: Control xác minh từng `tên==phiên bản` trên registry (PyPI) trước khi dispatch `ADAPT-DEPS` và ghi kết quả (ngày, URL, phiên bản) vào lệnh làm việc. Phiên bản nào không tồn tại hoặc không có wheel cho Python 3.13.15 trên Windows thì Control thay số trong lệnh làm việc; Worker không tự chọn phiên bản; không xác minh được thì `BLOCKED`. Worker chạy `uv lock` để `uv.lock` ghim mọi phụ thuộc bắc cầu (ví dụ `onnxruntime`, `ctranslate2`, `av`, `tokenizers`, `huggingface-hub`) kèm sha256 từng wheel; không khai riêng gói bắc cầu. Không nâng gói đã khóa (`psycopg`, `pydantic`, `temporalio`, `google-api-python-client`, `google-auth-oauthlib`, pytest), không đổi M1-R1, không sửa `src/controlplane/pyproject.toml` hay `requirements.lock` (hai universe độc lập, convergence mục 3.3). Cấm `latest` và dải phiên bản.

### 3.2. Ba giá trị ghim của Control (do `CP-2B-DEPS` ghi vào `tools/runtime/runtime.lock.json`)

| Vật phẩm | Giá trị ghim |
| --- | --- |
| FFmpeg gyan.dev `2025-03-13-git-958c46800e-essentials_build` (GPL v3; có libass, subtitles, h264_nvenc, libx264, loudnorm) | sha256 của `C:\ffmpeg\bin\ffmpeg.exe` = `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480` |
| Image `postgres:18.6` | digest `sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280` (ghi phần hex sau `sha256:`) |
| Image `temporalio/server:1.31.2` (thay `temporal-server.exe` ở R7) | digest `sha256:b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da` (ghi phần hex sau `sha256:`) |

Quy tắc dùng: adapter FFmpeg đọc `pins.ffmpeg.sha256` trong `tools/runtime/runtime.lock.json` và kiểm sha256 của `ffmpeg.exe` trước khi chạy tiến trình (lệch hoặc `BLOCKED` thì từ chối, không chạy `ffmpeg` trong PATH); `ffprobe.exe` nằm cùng thư mục và chuỗi build của `ffprobe -version` phải trùng chuỗi build của FFmpeg đã ghim. Launcher dùng `image@sha256:<digest>`, không dùng tag trần. Khóa `temporal_server_binary` của tệp lock giữ tên cũ để probe của `CP-2B-DEPS` còn đúng nhưng nay mang digest image Temporal (OI-ADAPT-11).

### 3.3. Lý do chọn `kokoro-onnx` (chấm điểm phương án, 1 đến 5)

| Tiêu chí (trọng số) | `kokoro-onnx` | `kokoro` |
| --- | --- | --- |
| Dễ ghim phiên bản và trọng số (30%) | 4 | 3 |
| Phụ thuộc bắc cầu nhẹ, không cần PyTorch (25%) | 5 | 2 |
| Chất lượng giọng Kokoro v1.0 (25%) | 4 | 4 |
| Vòng đời và bảo trì (20%) | 3 | 4 |
| **Tổng** | **4,05** | **3,20** |

Gemini TTS làm dự phòng về sau, không thuộc v1. Vẫn hoãn: `jusText`, `Scrapy`, `playwright`, `pydantic-ai`, `instructor`, `av` (chỉ vào bắc cầu của faster-whisper), `whisperx`, pgvector.

## 4. Vị trí mã, khóa tài nguyên và DAG

Mọi slice chờ `CP-2B-DEPS` và `USER-CKPT-D9-D10`. Cạnh tới gói bị chặn dùng mã cổng `GATE-<mã>` (`GATE-PERSIST-<chữ cái>`, `GATE-CP-2D-REGISTRY`, `GATE-CP-5-COMPLETION`, `GATE-CP-6-WORKFLOW`); bản biên dịch không được bỏ cạnh nào (convergence mục 11.1).

| Slice | Kind | Tệp chính | Khóa | Chờ thêm |
| --- | --- | --- | --- | --- |
| `ADAPT-DEPS` | dependency_slice | `pyproject.toml`, `uv.lock` | `LOCK-DEPENDENCY-UNIVERSE`, `LOCK-CONVERGENCE` | `IMPL-PLAN-ADAPT` |
| `ADAPT-A` | work_package_slice | `src/source_ingestion/adapters/real_http_transport.py`, `real_feed_source.py`, `real_media_fetch.py` | `LOCK-SRC-SOURCE-INGESTION` | `ADAPT-DEPS`, `GATE-CP-2D-REGISTRY` |
| `ADAPT-D` | work_package_slice | `src/creative/adapters/real_ai_invocation.py`, `src/controlplane/config/ninerouter_executor.py`, `adapter.py` | `LOCK-SRC-CREATIVE`, `LOCK-SRC-CONFIG-SECURITY` | `J-18` |
| `ADAPT-E` | work_package_slice | `src/voice/adapters/real_kokoro_tts.py`, `real_whisper_aligner.py` | `LOCK-SRC-VOICE` | `ADAPT-DEPS` |
| `ADAPT-E-MEDIA` | work_package_slice | `src/voice/adapters/real_ffmpeg_media_tool.py`, `real_llm_image_safety.py` | `LOCK-SRC-VOICE` | `ADAPT-D` |
| `ADAPT-F` | work_package_slice | `src/render/adapters/real_ffmpeg_renderer.py`, `real_ffprobe_probe.py` | `LOCK-SRC-RENDER`, `LOCK-DESKTOP-GPU` | `F-18` |
| `ADAPT-J` | work_package_slice | `src/controlplane/infrastructure/security/google_oauth_loopback.py`, `drive_token_provider.py` | `LOCK-SRC-CONFIG-SECURITY`, `LOCK-EXTERNAL-DRIVE` | `J-17`, `GATE-PERSIST-J` |
| `ADAPT-I` | work_package_slice | `src/controlplane/infrastructure/storage/google_drive_object_store.py` | `LOCK-SRC-STORAGE`, `LOCK-EXTERNAL-DRIVE` | `ADAPT-J` |
| `ADAPT-CONFIG` | work_package_slice | `deploy/production/**` | `LOCK-PRODUCTION-PROFILE` (GIẢ ĐỊNH) | `J-09` |
| `ADAPT-WIRE` | work_package_slice | `src/controlplane/api/wiring/**` | `LOCK-COMPOSITION-ROOT` | `CP-4-WIRING`, `GATE-CP-5-COMPLETION`, mọi slice adapter |
| `ADAPT-SEED` | work_package_slice | `deploy/production/seed/**` | `LOCK-PRODUCTION-PROFILE` | `ADAPT-WIRE`, `GATE-PERSIST-A`, `GATE-PERSIST-C` |
| `ADAPT-PROD` | work_package_slice | `src/main.py`, `src/controlplane/api/wiring/production.py` | `LOCK-COMPOSITION-ROOT` | `CP-4-WIRING`, `GATE-CP-5-COMPLETION`, `GATE-CP-6-WORKFLOW`, `ADAPT-WIRE` |
| `ADAPT-LAUNCH` | work_package_slice | `deploy/launcher/**`, `docs/operations/runbook-v1.md` | `LOCK-PRODUCTION-PROFILE` | `ADAPT-PROD`, `ADAPT-SEED` |

**DAG**: A, D, E, F, J, CONFIG chạy song song khi khóa khác nhau (E và E-MEDIA cùng khóa nên tuần tự); E-MEDIA sau D (dùng route AI); I sau J (token); WIRE sau mọi slice adapter và `CP-4-WIRING`; SEED và PROD sau WIRE; LAUNCH cuối. Khóa của `deploy/**`, `docs/operations/**`, `tests/integration/adapt/**` và `src/controlplane/config/ninerouter_executor.py` chưa có trong `ownership-and-locks.yaml`: Control mở rộng phong bì khi biên dịch (OI-ADAPT-02).

## 5. Chi tiết theo phân hệ

### 5.1. ADAPT-A — RSS, Atom, bài và ảnh (CP7-A-01)

- Transport thật (`real_http_transport.py`) cắm vào `SecureFetcher` (`src/source_ingestion/adapters/secure_fetch.py`): `http.client` nối đúng địa chỉ đã ghim của từng hop, không theo redirect, không proxy; SSRF, giới hạn kích thước và thời gian chờ do `SecureFetcher` và `FetchPolicy` giữ.
- `real_feed_source.py` cài `SourceAdapter` (`src/source_ingestion/ports/source_adapter.py`) cho `rss_feed` và `atom_feed`: `feedparser.parse` chỉ trên bytes đã tải, danh sách locator qua `CandidateListing`; `trafilatura.extract` trên HTML đã tải (không dùng `fetch_url`); raw bytes, phiên bản feedparser và trafilatura nằm trong `technical_fields` vì thuật toán trích xuất có thể đổi (docs/05 dòng 136).
- `real_media_fetch.py` tải ảnh gắn với bài (enclosure, `media:content`, `media:thumbnail`, ảnh chính do trafilatura trả) qua cùng `SecureFetcher` với `FetchPolicy` ảnh, ghi vào staging root theo cấu hình, rồi dựng `DiscoveryObservation` (`src/catalog/application/discovery.py`) để C gọi `register_discovery` và ghi nguồn gốc. Binding A→C (CT-MED-001) do `GATE-CP-2D-REGISTRY` tạo; trước đó seam chỉ dùng kiểu của C.
- Nóng/xu hướng (C5) tính ở B và D, không ở A; A chỉ thu thập.

### 5.2. ADAPT-D — AI qua J và 9Router (CP7-D-01, CP7-D-05)

- `AIInvocationPort` (`src/creative/ports/ai.py`) cài bằng `real_ai_invocation.py` trên `RoutedInvocationService` (J-18); D không nhận secret, không tự resolve route.
- `ninerouter_executor.py` cài `ProviderExecutorPort` bằng `NineRouterHTTPAdapter` (`src/controlplane/config/adapter.py`); endpoint, timeout, retry, backoff lấy từ cấu hình (mục 7.2).
- **BL-CV-04 (quyết định D8-ADAPT-01)**: thêm đường dựng `ApprovedEndpointRegistry` từ danh sách endpoint của cấu hình J; giữ `DEFAULT_APPROVED_ENDPOINTS` (có host `mock-9router`) làm nền test để `tests/unit/security/test_http_router_adapter.py` xanh không sửa; mã production không chứa `mock-9router`.
- **Hết hạn mức**: `WAITING_PROVIDER` và `BUDGET_BLOCKED` của J-18 thành kết quả chờ có thể thử lại; G đặt job chờ (`WAITING_CAPABILITY`, lý do hạn mức) và thăm dò lại mỗi `quota_wait_poll_seconds`, tự chạy tiếp khi hạn mức hồi; không đặt trần thời gian chờ, chỉ cảnh báo.
- **Chi phí**: ghi qua `CostLedgerPort` của J; tuyến Gemini của 9Router không phát sinh chi phí thêm nên `usage_cost` có thể bằng 0, nhưng `monthly_limit` 50 USD và `hard_stop` vẫn được đánh giá (cảnh báo ở 80%).

### 5.3. ADAPT-E và ADAPT-E-MEDIA — TTS, aligner, an toàn ảnh, FFmpeg (CP7-E-01 đến CP7-E-05)

- **TTS** (`real_kokoro_tts.py`, `TtsEnginePort`): `kokoro-onnx` chạy cục bộ, không mạng; nạp `kokoro-v1.0.onnx` và `voices-v1.0.bin` từ thư mục trọng số ngoài cây Git, kiểm sha256 theo `deploy/production/model-weights.lock.json` trước khi nạp; thiếu hoặc lệch sha256 thì `TtsProviderError` không thể thử lại, không tải ngầm. Đầu ra WAV mono PCM 16-bit 24000 Hz trong staging.
- **Aligner** (`real_whisper_aligner.py`, `AlignerPort`): `faster_whisper.WhisperModel` nạp từ thư mục cục bộ (`local_files_only`), `word_timestamps=True`, `language` `en`; từ phiên âm được căn vào `script_text` bằng so khớp chuỗi trên token đã chuẩn hóa; từ không khớp được đánh dấu và đếm, quá `max_unmatched_word_ratio` thì `AlignerError`; không nội suy mốc thời gian. `aligner_revision` gồm phiên bản thư viện và hash model.
- **An toàn ảnh** (`real_llm_image_safety.py`): detector gọi AI thị giác qua route J với `ai_role` `image_safety`, ép đầu ra JSON có kiểu (category, confidence, vùng chuẩn hóa); sai kiểu, quá hạn hay lỗi route là `DETECTION_FAILED` và bị xử lý như không an toàn (fail-closed). Ảnh chỉ đi tới route J đã duyệt, nội dung ảnh không vào log.
- **FFmpeg** (`real_ffmpeg_media_tool.py`): `MediaToolPort`, `TransformPort` và `ProbePort` bằng `subprocess.run` với danh sách đối số (không shell) trên `ffmpeg.exe` và `ffprobe.exe` đã ghim (mục 3.2); che vùng nhạy cảm bằng bộ lọc `boxblur` theo `TransformRegion`; ghi tệp ra tên mới, không ghi đè đầu vào; có timeout.
- Mã kiểm sha256 FFmpeg của E và F là hai bản độc lập (không import chéo phân hệ); mỗi bản dưới 40 dòng.
- Ngoài phạm vi: Gemini TTS, WhisperX, chọn giọng cuối cùng (CP7-E-01), chốt sai số (CP7-E-02).

### 5.4. ADAPT-F — render NVENC, phụ đề libass, QC (CP7-F-01 đến CP7-F-08)

- `real_ffmpeg_renderer.py` cài `RendererPort` và `OutputObservationPort` (`src/render/ports/renderer.py`): chạy một `RenderCommandSpec` bằng `subprocess.run` danh sách đối số; chuỗi bộ lọc `scale=1080:1920:force_original_aspect_ratio=increase`, `crop=1080:1920`, `fps=30`, `subtitles` (libass, tệp ASS của F-09 với thẻ `\k`); mã hóa `h264_nvenc`, nếu encoder không khởi tạo được thì thử một lần bằng `libx264` và ghi encoder đã dùng vào metrics; AAC; MP4 `+faststart`. Đầu ra ghi vào tệp tạm rồi đổi tên nguyên tử sang `output_ref` chỉ khi ffmpeg thoát 0. Quá hạn ném `RendererTimeout` (handler xử lý `OUTCOME_UNKNOWN`). F giữ `LOCK-DESKTOP-GPU` qua `GpuLeasePort`.
- `real_ffprobe_probe.py` cài `OutputProbePort` (`src/render/ports/output_probe.py`) bằng `ffprobe -print_format json`: `decodable`, `duration_ms`, `width`, `height`, `fps`, codec, container, âm thanh; trường không đo được để `None`. QC của F-14 đọc kết quả này, không tự đoán.

### 5.5. ADAPT-I — Google Drive (CP7-I-01)

`google_drive_object_store.py` (trong `src/controlplane/infrastructure/storage/`, gói đã khai) cài `CloudObjectPort` (`cloud_persist.py`) bằng `google-api-python-client` đã khóa: `files.generateIds` cấp file ID trước; upload resumable theo chunk vào đúng file ID đó nên thử lại không tạo tệp thứ hai; HTTP 409 là `ObjectAlreadyExistsError`; phiên hết hạn thì mở phiên mới cùng file ID; hết retry vì timeout là `TimeoutError` để I ghi `OUTCOME_UNKNOWN` rồi reconcile bằng `lookup`; `lookup` dùng metadata Drive và, khi thiếu checksum khớp sha256, tải lại theo chunk để tính sha256. Token chỉ lấy qua `credential_method` của broker J.

### 5.6. ADAPT-J — OAuth một lần và broker DPAPI (CP7-J-01)

`google_oauth_loopback.py` chạy luồng OAuth bằng `google-auth-oauthlib` đã khóa: máy chủ loopback `127.0.0.1` cổng ngẫu nhiên, PKCE và `state`, scope duy nhất `https://www.googleapis.com/auth/drive.file`, đóng cổng ngay khi xong hoặc quá hạn. Client ID và secret của ứng dụng Google do user đặt ở tệp JSON ngoài cây Git (đường dẫn từ cấu hình, nội dung không bao giờ in). Refresh token ghi vào `DpapiSecretStore` qua `SecretStorePort` với `secret_ref` `drive-primary-oauth`; PostgreSQL chỉ giữ metadata handle. `drive_token_provider.py` trả access token ngắn hạn cho broker và làm mới khi hết hạn; refresh token không rời broker. **Điểm dừng user thứ nhất**: user bấm đồng ý trên trình duyệt một lần (CP7-ADAPT-01); hướng dẫn từng bước nằm ở console của launcher và runbook (OI-ADAPT-03).

## 6. Hồ sơ production, wiring, launcher và runbook

1. **Hai hồ sơ**: `test` (mặc định, giữ hành vi của CP-4-WIRING) và `production`. `src/main.py` (BL-CV-06: CP-4-WIRING chỉ tạo bản đọc cấu hình, dựng `TransactionManager` rồi gọi `create_app`) được `ADAPT-PROD` mở rộng để ở `production` nạp `deploy/production/profile.json` (thiếu tham số thì từ chối khởi động, không default ẩn), gọi các `build_<phân hệ>_services` rồi `create_app`.
2. **Một cổng loopback TLS**: uvicorn `127.0.0.1:8443`, chứng chỉ tự ký (SAN `127.0.0.1` và `localhost`) do launcher tạo bằng `cryptography` ngoài cây Git; `/v1/*` do `create_app` phục vụ, đường còn lại phục vụ `src/controlplane/ui/dist`; Origin cho phép đúng `https://127.0.0.1:8443` và `https://localhost:8443`.
3. **Tắt test-driver ở máy chủ**: `create_test_application` và `TestDriver` (`src/controlplane/application/test_driver.py`) chỉ dành cho test; mô-đun production không import chúng nên mọi `/test-driver/*` trả 404.
4. **Capability một lần (BL-CV-13, quyết định D8-ADAPT-02)**: `ui/dist` vẫn gọi `POST /test-driver/issue-capability` khi chưa có phiên (`api/client.ts` dòng 67 đến 83) và `App.tsx` dòng 49 đến 62 chấp nhận bootstrap thất bại khi cookie đã có. Launcher phát capability bằng `BootstrapCapabilityRegistry.issue` (TTL tối đa 60 giây, một lần) và mở `https://127.0.0.1:8443/launch?cap=<capability>`; route `GET /launch` mới (ngoài `/v1`) gọi `consume`, tạo phiên bằng `SessionSecurityService.create`, đặt cookie `cp_session` như `redeem_bootstrap` rồi chuyển hướng `/`. UI và spec M2 giữ nguyên byte; capability dùng lại hoặc quá hạn trả 403.
5. **Wiring**: mỗi phân hệ một mô-đun `src/controlplane/api/wiring/<phân hệ>.py` với `build_<phân hệ>_services(manager, config)` do `CP-4-WIRING` tạo; `ADAPT-WIRE` đọc danh sách thật (tìm `def build_.*_services`) rồi mở rộng để ở `production` dựng service bằng adapter thật (A, D, E, F, I, J) trên kho PostgreSQL của các `GATE-PERSIST-*`; không tạo mô-đun trùng, không import chéo.
6. **Launcher** (`deploy/launcher/launcher.py`, stdlib): `start` (compose, `MigrationRunner`, chứng chỉ, worker, capability, mở trình duyệt), `stop` (chỉ dừng worker; container và dữ liệu giữ nguyên, việc dở tiếp tục khi `start` lại), `down`, `status`, `backup`, `restore`, `oauth`. `docker-compose.yml`: `postgres` và `temporal` theo `image@sha256:<digest>` từ `runtime.lock.json`, cổng chỉ `127.0.0.1` (PostgreSQL `57028`, Temporal `7233`), volume đặt tên, không mở UI Temporal.
7. **Runbook** (`docs/operations/runbook-v1.md`, tiếng Việt, sáu mục): khởi động, dừng, tiếp tục, sao lưu (`pg_dump` qua `docker exec`), khôi phục (recovery epoch mới theo G05), xử lý lỗi theo bảng triệu chứng; cộng danh sách giá trị chọn không có căn cứ đo (mục 7) cần đo ở CP7.
8. **Thứ tự khởi động**: compose up, chờ PostgreSQL và Temporal khỏe, `MigrationRunner`, worker (sáu task queue của `GATE-CP-6-WORKFLOW`), ứng dụng, capability, trình duyệt.

## 7. Cấu hình production (giá trị của mọi đầu vào INPUT_NOT_READY và pendingUserCheckpoint)

Mục này cho giá trị production của mọi tham số mà kế hoạch phân hệ đánh dấu `INPUT_NOT_READY` hoặc `pendingUserCheckpoint`. `ADAPT-CONFIG` ghi chúng vào `deploy/production/profile.json`, mỗi tham số có `value`, `reason` và `basis` (`DECIDED`, `MEASURED` hoặc `CONSERVATIVE_DEFAULT`). Giá trị không có căn cứ đo là `CONSERVATIVE_DEFAULT`, được ghi vào runbook và đo ở CP7; kết quả đo thay giá trị bằng revision cấu hình mới, không đổi mã. Nhãn «chưa đo» nghĩa là chưa có số đo trên máy này.

### 7.1. Thu thập (A)

| Tham số | Giá trị | Lý do |
| --- | --- | --- |
| `source_kind` | `rss_feed`, `atom_feed`, `web_page` | khớp ba loại adapter v1 (MODULE-A-OPEN-001) |
| Tier (MODULE-A-OPEN-002) | `tier_1` thông tấn lớn và cơ quan chính thức, `tier_2` báo chuyên ngành, `tier_3` blog | điểm nóng dùng tier (C5) |
| `fetch_policy.feed` | `max_redirects` 5, `max_body_bytes` 5242880, `timeout_seconds` 20, `application/rss+xml`, `application/atom+xml`, `application/xml`, `text/xml` | feed công khai thường dưới 1 MiB; trần 5 MiB chặn phản hồi bất thường (chưa đo) |
| `fetch_policy.article` | 5 redirect, 5242880 byte, 20 s, `text/html`, `application/xhtml+xml` | trang bài hiếm khi quá 2 MiB |
| `fetch_policy.image` | 5 redirect, 15728640 byte, 30 s, `image/jpeg`, `image/png`, `image/webp` | ảnh báo chí thường dưới 5 MiB; không nhận SVG và GIF vì rủi ro nội dung chủ động |
| `retry.fetch` | 3 lần, backoff mũ cơ số 2 s, trần 60 s, tôn trọng `Retry-After` | tránh dồn tải lên nguồn (MODULE-A-OPEN-009, chưa đo) |
| `concurrency` | 4 fetch toàn cục, 1 mỗi host | một máy, mạng gia đình, lịch sự với nguồn |
| `collection_interval_minutes` | 180 | đủ tươi cho lô qua đêm; chỉ chạy khi worker bật (U1) |
| `freshness_window_hours` | 48 | tin cũ hơn 48 giờ không tính nóng |
| `extraction.min_text_chars` | 600 | dưới ngưỡng thì `PARTIAL`; 600 ký tự đủ cho ý chính một kịch bản |
| `user_agent` | `AIAutoVideoCreator/1.0` | cố định, không chứa bí mật |

### 7.2. AI và ngân sách (D, J)

| Tham số | Giá trị | Lý do |
| --- | --- | --- |
| `ai.route.endpoint` | `http://127.0.0.1:20128/v1` (cổng mặc định của 9Router; Control xác nhận ở CP7, OI-ADAPT-05) | endpoint duy nhất được duyệt, lấy từ cấu hình thay host mock |
| `ai.route.model_ref` | `ag/gemini-3.8-flash-high` cho mọi `ai_role`: `analysis`, `angle`, `script`, `selection`, `metadata`, `image_safety` | tuyến Gemini đang dùng (U1); đổi bằng revision cấu hình |
| `ai.request_timeout_seconds` | 120 | phản hồi script của model flash dưới 60 s, gấp đôi để chịu tải (chưa đo) |
| `ai.retry` | 3 lần, backoff cơ số 2 s, trần 60 s | QUALITY-OPEN-003, chưa đo |
| `ai.reservation_ttl_seconds` | 300 | dài hơn hai lần timeout |
| `ai.quota_wait_poll_seconds` | 300 | thăm dò hạn mức 5 phút một lần, không dồn tải |
| `ai.quota_wait_max` | không trần, cảnh báo mỗi 3600 s | U1: hết hạn mức thì chờ và tự chạy tiếp |
| `budget.monthly_limit` | 50 USD, `hard_stop` true, cảnh báo ở 80% | C5; cửa sổ tháng theo `Asia/Ho_Chi_Minh` |
| `credential.max_ttl_seconds` | 3300 | access token Google sống 3600 s, chừa 300 s |

### 7.3. Voice, timing, âm thanh, an toàn ảnh (E)

| Tham số | Giá trị | Lý do |
| --- | --- | --- |
| `voice.engine` | Kokoro cục bộ (`kokoro-onnx`), giọng `af_heart`, `lang` `en-us`, `speed` 1.0, WAV mono 24000 Hz PCM 16-bit | C3; giọng mặc định của Kokoro v1.0; chốt lại sau nghe thử (CP7-E-01) |
| `voice.duration_range_ms` | 61000 đến 70000 | CT-AI-004 |
| `speech_rate_wpm` | 150 | Kokoro tốc độ 1.0 đọc khoảng 150 đến 170 từ mỗi phút; chọn mức thấp để script không vượt 70 s; hiệu chỉnh ở CP7-D-04 (chưa đo) |
| `aligner` | `faster-whisper` model `small.en`, `device` cpu, `compute_type` int8, `beam_size` 5, `word_timestamps` true | không cần runtime CUDA; nhường GPU cho NVENC; đủ chính xác cho giọng TTS sạch |
| `word_timing.tolerance_ms` | 150 | Whisper lệch từng từ khoảng 100 ms; karaoke chấp nhận dưới 150 ms; đo ở CP7-E-02 |
| `aligner.max_unmatched_word_ratio` | 0.05 | quá 5% từ không khớp là lỗi, không nội suy |
| `audio.loudness` | `integrated_lufs` -16, `true_peak_dbtp` -1.5, `lra` 11, dung sai cảnh báo 1.5 LU | mức phổ biến cho video ngắn dọc; chỉ cảnh báo (roadmap §12); user nghe ở CP7-E-05 |
| `audio.bed_gain_db` | -20 so với giọng | nhạc nền không át giọng; thận trọng |
| `tts.timeout_seconds` | 180 | Kokoro trên CPU mất vài giây cho 10 giây âm thanh; 180 s là trần |
| `image_safety.categories` | `minor_child`, `nudity_sexual`, `graphic_violence`, `weapon`, `hate_symbol` | tập tối thiểu của CT-PROC-006 |
| `image_safety.thresholds` | `reject` khi confidence từ 0.50 với `minor_child` và `nudity_sexual`; `blur` khi từ 0.50 với `graphic_violence`, `weapon`, `hate_symbol` nếu có vùng, không có vùng thì `reject`; confidence từ 0.30 đến dưới 0.50 (`uncertain`) và mọi lỗi detector thì `reject` | nghiêng về chặn vì bỏ một ảnh rẻ hơn rủi ro nội dung; đo ở CP7-E-03 |
| `image_safety.boxblur` | `luma_radius` 40, `luma_power` 3 | che mạnh nhưng giữ bố cục |
| `image_safety.vision` | timeout 120 s, ảnh gửi đi có cạnh dài tối đa 1024 px | giảm token mà vẫn nhận diện được |
| `retry.stage` (E, F do G quyết) | 3 lần mỗi stage, backoff cơ số 5 s, trần 120 s | E và F không tự retry (TEST-OPEN-003) |

### 7.4. Render và QC (F)

| Tham số | Giá trị | Lý do |
| --- | --- | --- |
| `render.profile` | 1080x1920, 30 fps, H.264 `h264_nvenc`, AAC 192 kbit/s 48 kHz stereo, MP4 `+faststart` | C; ROADMAP-OPEN-007 |
| `render.nvenc` | `-preset p5 -tune hq -rc vbr -cq 23 -b:v 0 -maxrate 12M -bufsize 24M -profile:v high -pix_fmt yuv420p -g 60 -bf 2` | cân bằng chất lượng và tốc độ; 100 video trong 12 giờ cần dưới 7 phút mỗi video (chưa đo, CP7-F-07) |
| `render.fallback` | `libx264 -preset medium -crf 21 -pix_fmt yuv420p` | khi NVENC không khởi tạo được; chậm hơn nhưng an toàn |
| `render.timeout_seconds` | 900 | gấp nhiều lần thời gian dự kiến; quá hạn thì `OUTCOME_UNKNOWN` |
| `render.presets` | năm preset `bold-yellow`, `clean-white`, `neon-cyan`, `news-red`, `soft-shadow`; chung font `Arial` đậm cỡ 72, viền 4, `margin_v` 360; khác nhau ở màu highlight karaoke và màu viền | ROADMAP-OPEN-009; user duyệt ở nghiệm thu; font xem OI-ADAPT-08 |
| `qc.duration_range_ms` | 61000 đến 70000, hai đầu bao gồm | CT-QC-001 |
| `qc.required_language` | `en` | CT-QC-002 |
| `qc.karaoke_tolerance_ms` | 150 | trùng `word_timing.tolerance_ms` |
| `qc.hook_similarity_min` | 0.85 | hook phải nhận ra trong khung hình; chưa đo (CP7-F-02) |
| `qc.hook_audio_min_dbfs` | -40 | không im lặng |
| `qc.visual_continuity_min` | 0.60 | chỉ cảnh báo, không chặn (roadmap §12) |
| `qc.max_file_bytes` | 157286400 | 150 MiB; 65 s ở 12 Mbit/s chỉ khoảng 100 MB |
| `gpu.slots` | 2 (`LOCK-DESKTOP-GPU`) | RTX 4070 SUPER 12 GB chạy hai phiên NVENC; đo ở CP7-F-06 |

### 7.5. Drive, working set, retention (I)

| Tham số | Giá trị | Lý do |
| --- | --- | --- |
| `drive.account` | một tài khoản `drive-primary`, scope `drive.file` | U2; quyền tối thiểu |
| `drive.folders` | `AI-Auto-Video-Creator/original`, `.../reusable`, `.../output/YY-MM-DD` (ngày theo `Asia/Ho_Chi_Minh`) | CT-STO-011, D8-I-08 |
| `drive.chunk_bytes` | 8388608 | bội của 262144 mà Drive yêu cầu |
| `drive.chunk_timeout_seconds` | 120 | chưa đo |
| `drive.retry` | 5 lần, backoff cơ số 2 s, trần 60 s | khuyến nghị exponential backoff của Drive |
| `drive.session_ttl_seconds` | 518400 | phiên resumable sống 7 ngày, chừa 1 ngày |
| `drive.quota_reserve_ratio` | 0.20 | dừng upload khi dự phóng dung lượng trống dưới 20% tổng; quota thật đo ở CP7-I-02 |
| `drive.verify` | so md5 Drive với md5 tính khi upload; thiếu checksum thì tải lại và so sha256 | yêu cầu của I |
| `working_set.max_video_sets` | 5 | D8-I-03 |
| `working_set.max_bytes` | 21474836480 | 5 bộ khoảng 1 đến 3 GiB mỗi bộ, có dư; đo ở CP7-I-03 |
| `working_set.disk_reserve_bytes` | 32212254720 | không để ổ đĩa đầy khi render |
| `retention.original`, `reusable`, `output` | giữ vĩnh viễn; bản local chỉ dọn sau khi cloud verified | C5, D8-I-06 |
| `retention.temporary` | xóa sau 24 giờ kể từ khi kiểm xong và hoàn tất | C5 |
| `retention.log_days`, `audit_days` | 30 và 365 | QUALITY-OPEN-009, thận trọng |

### 7.6. Workflow, lô, múi giờ (G, J)

| Tham số | Giá trị | Lý do |
| --- | --- | --- |
| `timezone` | `Asia/Ho_Chi_Minh`, lưu UTC; `business_date`, tên thư mục Drive và cửa sổ tháng ngân sách tính theo múi giờ này | C5 (ROADMAP-OPEN-004) |
| `workflow.start_to_close_s` | `control-workflows` 60, `cloud-io` 900, `cloud-ai` 240, `desktop-cpu` 600, `desktop-gpu` 900, `desktop-render` 1200 | lớn hơn timeout adapter tương ứng (D8-G-07) |
| `workflow.heartbeat_s` | 30 | phát hiện worker chết sớm |
| `workflow.retry` | `initial_interval_s` 5, `backoff_coefficient` 2.0, `maximum_interval_s` 120, `maximum_attempts` 3 | D8-G-07 |
| `batch.videos_per_news_per_round` | 2 | roadmap §13: 1 đến 3 video mỗi tin mỗi lượt |
| `batch.target` | 10 cho lần chạy mẫu, 100 cho đêm chạy thử | U4 |
| `resume.ready_within_seconds` | 300 | roadmap §13 (khởi động lại không chạy lại từ đầu) |
| `schedule` | không bật lịch cloud; thu thập chạy khi worker bật | U1 |

### 7.7. Nguồn RSS công khai cơ sở (sửa được trên UI)

Control đề xuất; địa chỉ chưa kiểm sống vì kế hoạch không gọi mạng (CP7-A-01 kiểm). Nhập qua dịch vụ ứng dụng của A, không qua UI.

| Mã | Địa chỉ | Tier |
| --- | --- | --- |
| `bbc-world` | `https://feeds.bbci.co.uk/news/world/rss.xml` | `tier_1` |
| `bbc-tech` | `https://feeds.bbci.co.uk/news/technology/rss.xml` | `tier_1` |
| `npr-news` | `https://feeds.npr.org/1001/rss.xml` | `tier_1` |
| `guardian-world` | `https://www.theguardian.com/world/rss` | `tier_1` |
| `aljazeera-all` | `https://www.aljazeera.com/xml/rss/all.xml` | `tier_1` |
| `nasa-news` | `https://www.nasa.gov/feed/` | `tier_1` |
| `ars-technica` | `https://feeds.arstechnica.com/arstechnica/index` | `tier_2` |

Lý do: bảy nguồn độc lập đủ cho điểm «số nguồn độc lập» (C5), phủ thế giới, công nghệ và khoa học, đều là feed công khai. Nội dung bài chỉ dùng làm đầu vào phân tích và viết script gốc.

### 7.8. Bộ hook và media seed tối thiểu cho lần chạy mẫu

Tất cả do chính hệ thống tự tạo (không rủi ro bản quyền), sinh bằng `deploy/production/seed/make_seed_media.py`, đặt ngoài cây Git ở thư mục dữ liệu `seed` (gốc dữ liệu mặc định `LOCALAPPDATA/AIAutoVideoCreator`), ghi sha256 từng tệp trong `hooks.json`, nhập qua dịch vụ ứng dụng của C (`import_hook`, `register_discovery`), không qua UI.

| Nhóm | Số lượng và đặc tả | Lý do |
| --- | --- | --- |
| Hook hình `vh-01` đến `vh-05` | 3 giây, 1080x1920, 30 fps, nền chuyển màu và nhịp sáng khác nhau, sinh bằng nguồn `lavfi` của ffmpeg đã ghim | năm kiểu đủ khác biệt |
| Hook âm thanh `ah-01` đến `ah-05` | 1,5 giây, WAV 24000 Hz mono, quét tần số 220 đến 880 Hz với năm hình bao khác nhau, sinh bằng `wave` | tránh nhạc có bản quyền |
| Ảnh nền `bg-01` đến `bg-12` | PNG 1080x1920 chuyển màu theo 12 sắc, sinh bằng stdlib | 10 video mỗi video 3 ảnh vẫn chọn được không lặp |

Năm hook hình nhân năm hook âm thanh cho 25 tổ hợp, đủ cho 10 video mẫu khác nhau. **Quyền ảnh từ bài**: ảnh tải kèm bài được đăng ký với nguồn gốc nhưng `rights_status` mặc định `UNVERIFIED` và không vào video mẫu; chỉ tài sản seed được dùng cho tới khi user quyết (OI-ADAPT-10, pendingUserCheckpoint).

### 7.9. Trọng số model và tài nguyên test

Trọng số đặt ngoài cây Git ở `LOCALAPPDATA/AIAutoVideoCreator/models`. `deploy/production/model-weights.lock.json` ghi URL https cố định kèm sha256 từng tệp; sha256 chưa có trong tài liệu nên là `null` kèm `status` `BLOCKED` tới khi Control tải, tính hash và ghi (OI-ADAPT-06); Worker không bịa giá trị.

| Tài nguyên | Địa chỉ cố định (Control xác minh khi tải) | sha256 |
| --- | --- | --- |
| `kokoro-v1.0.onnx` | `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx` | `null`, `BLOCKED` |
| `voices-v1.0.bin` | `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin` | `null`, `BLOCKED` |
| faster-whisper `small.en` (các tệp model của kho `Systran/faster-whisper-small.en`, ghim theo commit) | địa chỉ `https://huggingface.co/Systran/faster-whisper-small.en/resolve/<commit>/<tệp>` với `<commit>` do Control điền | `null`, `BLOCKED` |

Tài nguyên test (WAV, PNG, feed XML, HTML mẫu) tự tạo trong test hoặc ở `tests/fixtures`, không tải từ mạng; media thật hay trọng số không vào cây Git.

## 8. Việc cần tài nguyên thật (CP7)

Mọi mục dưới đây cần Drive, OAuth, AI thật, GPU hoặc chạy dài; chỉ kiểm bằng slice CP7 do Control mở sau khi user duyệt D5, dùng tài khoản thật chỉ qua broker của J (không mở, chép hay in bí mật). Slice `ADAPT-*` không đóng được gate nào trong số này. Kết quả đo đổi `basis` của tham số từ `CONSERVATIVE_DEFAULT` sang `MEASURED` bằng revision cấu hình mới.

| Mã | Nội dung | Mã gốc |
| --- | --- | --- |
| CP7-ADAPT-01 | OAuth thật một lần (điểm dừng user thứ nhất) và upload Drive thật: resumable, 409, phiên hết hạn, thiếu checksum, token revoked | CP7-I-01, CP7-J-01, CP7-J-02 |
| CP7-ADAPT-02 | Gọi 9Router thật cho sáu `ai_role`; hết hạn mức thì chờ rồi tự chạy tiếp; chi phí ghi qua J | CP7-D-01, CP7-D-05, CP7-J-04, CP7-J-05 |
| CP7-ADAPT-03 | Nghe thử TTS Kokoro, chốt giọng và `speech_rate_wpm` bằng `actual_duration_ms` thật | CP7-E-01, CP7-E-07, CP7-D-04 |
| CP7-ADAPT-04 | Sai số word timing của faster-whisper trên giọng TTS với nhạc và SFX | CP7-E-02 |
| CP7-ADAPT-05 | Bộ ảnh nhạy cảm thật cho LLM thị giác và `boxblur` | CP7-E-03 |
| CP7-ADAPT-06 | Render NVENC thật từng preset, libass, QC ffprobe, loudness, tranh GPU giữa STT, TTS và render | CP7-F-01 đến CP7-F-04, CP7-E-04 đến CP7-E-06, CP7-F-06 |
| CP7-ADAPT-07 | Kiểm sống bảy nguồn RSS cơ sở và độ đầy đủ khi trích xuất | CP7-A-01, CP7-A-05 |
| CP7-ADAPT-08 | Phiên sản xuất thật: TLS loopback, `/launch`, Host, Origin, CSRF, quét secret canary | CP7-H-04, CP7-H-05 |
| CP7-ADAPT-09 | Đêm chạy thử 100 video hợp lệ trong 12 giờ, ít nhất 95% tự động, không ngoại suy từ benchmark ngắn | CP7-G-01, CP7-G-04, CP7-F-07, CP7-F-08 |
| CP7-ADAPT-10 | Restore drill và xoay secret | CP7-G-05, CP7-I-04, CP7-J-02 |
| CP7-ADAPT-11 | Mẫu 10 video; user xem trên Dashboard khoảng 30 phút và nghiệm thu, gồm checkpoint M2 và ngoại lệ `safe-error-modal.spec.ts` của CP-2C (điểm dừng cuối của v1) | U4 |

## 9. Mục mở và quyết định D8

Không mục nào là đã duyệt; mục cần user vẫn ở `pendingUserCheckpoint`.

| Mã | Nội dung | Mặc định đã chọn | Lý do |
| --- | --- | --- | --- |
| OI-ADAPT-01 | Phiên bản registry của bốn gói, nhất là `kokoro-onnx==0.4.9` | Control xác minh trên PyPI trước `ADAPT-DEPS`; lệnh làm việc thắng số trong kế hoạch | Orchestrator không có quyền gọi registry |
| OI-ADAPT-02 | `ownership-and-locks.yaml` chưa phủ `deploy/**`, `docs/operations/**`, `tests/integration/adapt/**`, `ninerouter_executor.py`; `LOCK-PRODUCTION-PROFILE` là tên GIẢ ĐỊNH | Control mở rộng phong bì khi biên dịch | Registry thuộc `CP-2D-REGISTRY` |
| OI-ADAPT-03 | «Dashboard hướng dẫn OAuth từng bước» trong khi UI giữ nguyên | Hướng dẫn ở console của launcher và runbook; màn hình riêng cần slice UI mới | Ghi chú Control giữ nguyên UI và spec M2 |
| OI-ADAPT-04 | Cấp phiên cho UI đã dựng (BL-CV-13) | Route `GET /launch` ở máy chủ (D8-ADAPT-02), không sửa UI | UI chấp nhận bootstrap thất bại khi đã có cookie |
| OI-ADAPT-05 | Cổng và tên tuyến thật của 9Router | `http://127.0.0.1:20128/v1`, `ag/gemini-3.8-flash-high` | Giá trị mặc định thận trọng; Control xác nhận ở CP7-ADAPT-02 |
| OI-ADAPT-06 | sha256 trọng số Kokoro và faster-whisper | `null` kèm `BLOCKED` tới khi Control ghi | Không bịa hash |
| OI-ADAPT-07 | Chứng chỉ TLS tự ký | Trình duyệt cảnh báo lần đầu; runbook hướng dẫn tin cậy chứng chỉ | Không có CA cục bộ |
| OI-ADAPT-08 | Font phụ đề | `Arial` hệ thống Windows; nếu libass không tìm thấy thì `BLOCKED`, Control ghim font mở sau | Tránh thêm tệp lớn và rủi ro giấy phép |
| OI-ADAPT-09 | `DEFAULT_APPROVED_ENDPOINTS` còn host `mock-9router` | Giữ làm nền test; production dùng danh sách từ cấu hình (D8-ADAPT-01) | Giữ `test_http_router_adapter.py` xanh |
| OI-ADAPT-10 | Quyền dùng ảnh tải kèm bài | `UNVERIFIED`, chỉ tài sản seed vào video mẫu | pendingUserCheckpoint; roadmap cấm media không rõ quyền |
| OI-ADAPT-11 | Khóa `temporal_server_binary` mang digest image Temporal | Giữ tên khóa, đổi nghĩa, ghi vào report của `CP-2B-DEPS` | Tương thích probe của `CP-2B-DEPS` |
| OI-ADAPT-12 | Kokoro chỉ hỗ trợ tiếng Anh trong phạm vi v1 | `qc.required_language` là `en` | Đúng yêu cầu `ENGLISH_OUTPUT_VALID` |

### 9.1. Danh sách chờ user (pendingUserCheckpoint)

- Điểm dừng user thứ nhất (U2): user làm OAuth một lần với tài khoản Drive thật.
- Điểm dừng cuối (U4): nghiệm thu mẫu 10 video, gồm checkpoint M2 (M2-P8 và M2-P9 đã có Auditor PASS nhưng chưa ghi checkpoint user).
- D5 cho mọi slice CP7 (mục 8) và `USER-CKPT-D9-D10` cho bốn gói của mục 3.
- OI-ADAPT-10 (quyền ảnh từ bài) và duyệt năm preset (ROADMAP-OPEN-009) khi nghiệm thu.

### 9.2. Quyết định D8 của kế hoạch này

- D8-ADAPT-01: danh sách endpoint được duyệt lấy từ cấu hình J qua đường dựng mới của `ApprovedEndpointRegistry`; `DEFAULT_APPROVED_ENDPOINTS` giữ làm nền test (BL-CV-04).
- D8-ADAPT-02: phiên cho UI đã dựng đi qua `GET /launch` ở máy chủ, không sửa UI, spec M2 hay `ui/dist` (BL-CV-13).
- D8-ADAPT-03: tệp adapter mới của A, D, E, F luôn là `real_<tên>.py`; không dùng glob thư mục.
- D8-ADAPT-04: mã kiểm sha256 FFmpeg có hai bản độc lập ở E và F để không import chéo phân hệ.
- D8-ADAPT-05: mỗi tham số production có `value`, `reason`, `basis`; giá trị không đo được là `CONSERVATIVE_DEFAULT` và nằm trong runbook.

## 10. Ngoài phạm vi và kích thước biên dịch

- Ngoài phạm vi: migration, `MigrationRunner`, state machine, contract, sửa `ui/dist` hay `tests/m2`, tài nguyên thật (CP7), kích hoạt sản xuất (`PRODUCTION_ACTIVATION_BLOCKED`), Gemini TTS, WhisperX, pgvector, cloud, push và merge.
- Kích thước biên dịch: `slices.md` có 13 mục, mỗi mục không quá 3000 ký tự và tổng không quá 38000 ký tự để gói biên dịch của kế hoạch dưới 60000 ký tự (`PLAN_REVIEW_INPUT_TOO_LARGE` nếu vượt).
