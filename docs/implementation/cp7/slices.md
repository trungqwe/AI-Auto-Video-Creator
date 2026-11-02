# Slice kiểm trên tài nguyên thật — CP7-REAL-RESOURCES

Nguồn: `docs/implementation/cp7/plan.md`. Mười bốn slice do Control biên dịch; tất cả là `work_package_slice`, chỉ kiểm, chạy tuần tự trên một máy (`LOCK-CP7`). Mỗi slice ứng với gate `RG-<mã>` của plan.md mục 4; gate user R1–R6 (plan.md mục 5) không phải slice.

## Quy tắc chung cho mọi slice

- Chỉ sửa tệp trong `ownedPaths` (`tests/real/**`, `tools/real/**`, `docs/delivery-evidence/cp7-<số>/report.md`); không sửa `src/**`, migration, composition root, lockfile, `tests/m1`, `tests/m2`, `ui/dist`, `docs/milestones/**/evidence/**`. Lỗi của phân hệ thì ghi finding (mã, tệp:dòng, cách tái hiện) và báo `BLOCKED` kèm khối `blocked-manifest`, không tự vá.
- Không mock, fake, `memory` hay fixture để đóng gate; mọi test dùng hồ sơ `production` và adapter `real_*`. Thiếu tài nguyên thì test FAIL hoặc `BLOCKED`, không skip và không xanh giả.
- Bí mật chỉ qua `CredentialBroker` (J-17): không đọc `Credentials/`, không in token, client secret, mật khẩu CSDL hay capability. Log và `report.md` phải qua `scan_secrets` của CP7-1 (0 lần khớp).
- `tests/real/conftest.py` (CP7-1) chỉ cho pytest thu thập `tests/real` khi lệnh nêu đường dẫn đó, nên `python -m pytest tests` không chạm tài nguyên thật.
- Test-first: viết test và thấy RED do assertion đúng oracle (thiếu binary, import hay tài nguyên không phải RED hợp lệ) trước khi chạy trên tài nguyên thật.
- Kết quả ghi trong `report.md` theo dòng `RG-<mã>.<mục>: PASS|FAIL|BLOCKED|NOT_OBSERVED`, kèm lệnh, mã thoát, số đo, ngưỡng và finding; các `testCommands` kiểm những dòng này bằng probe. `NOT_OBSERVED` chỉ hợp lệ cho mục được ghi rõ là soft.
- Slice nào cũng nêu `Trần chi phí` và `Cách dừng` trong acceptance; slice tốn AI, Drive hoặc GPU dài có con số tường minh.

### CP7-1: Tiền kiểm runtime thật và thư viện bằng chứng chung

- kind: work_package_slice
- ownedPaths:
  - `tools/real/cp7_common.py`
  - `tests/real/conftest.py`
  - `tests/real/test_cp7_preflight.py`
  - `docs/delivery-evidence/cp7-1/report.md`
- dependsOn: `M3-MILESTONE-CLOSE`, `M4-MILESTONE-CLOSE`, `M5-MILESTONE-CLOSE-R2`, `M6-MILESTONE-CLOSE-R2`, `M7-MILESTONE-CLOSE`, `CP7-REAL-RESOURCES`
- resourceLocks: `LOCK-CP7`, `LOCK-DESKTOP-GPU`
- bindingRefs: gate RG-01; `tools/runtime/runtime.lock.json`
- acceptance:
  - requirement: (1) `cp7_common.py` (stdlib): `redact`, `scan_secrets` (mẫu token OAuth Google, khóa API Google, khối khóa riêng PEM, chuỗi canary), `report_line(gate, item, status)`, `CostGuard` (đọc sổ chi phí của J ở chế độ chỉ đọc, dừng khi vượt trần), `Deadline` (dừng cứng); không in giá trị bí mật. (2) `conftest.py` chỉ thu thập `tests/real` khi lệnh nêu đường dẫn đó. (3) `test_cp7_preflight.py` đo thật: sha256 `C:\ffmpeg\bin\ffmpeg.exe` = `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`; digest image `aiavc-postgres` và `aiavc-temporal` khớp `runtime.lock.json`; cổng 57028, 7233, 8443 chỉ bind `127.0.0.1`; `nvidia-smi` báo RTX 4070 SUPER và VRAM ≥ 12 GiB; ổ đĩa trống ≥ 50 GiB; TCP `127.0.0.1:20128` (9Router) mở; kho DPAPI có alias cần dùng (kiểm tồn tại, không đọc giá trị). Trần chi phí: 0 USD, không gọi AI. Cách dừng: kiểm tra tự kết thúc dưới 5 phút; Ctrl+C.
    instrument: `test_cp7_preflight.py` và probe `report.md` có đủ 7 mục `RG-01.*` PASS.
    counterexample: đọc `Credentials/`; in giá trị bí mật; test xanh khi thiếu Docker hay GPU; hằng số hash bịa; sửa `src/**`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_preflight.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-1/report.md').read_text(encoding='utf-8'); keys = ['ffmpeg_pin', 'image_digests', 'loopback_ports', 'gpu', 'disk', 'router_port', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-01[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-2: Phiên sản xuất thật và bảo mật loopback

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_session_security.py`
  - `tools/real/cp7_browser_probe.js`
  - `docs/delivery-evidence/cp7-2/report.md`
- dependsOn: `CP7-1`
- resourceLocks: `LOCK-CP7`
- bindingRefs: gate RG-01; `docs/runbook/runbook-v1.md` mục 1
- acceptance:
  - requirement: (1) Chạy `python tools/launcher/launcher.py start` hồ sơ `production` bằng subprocess, lấy URL `/launch` do launcher cấp mà không in capability. (2) `cp7_browser_probe.js` (CommonJS, nạp `playwright` từ `src/controlplane/ui`) mở phiên qua `/launch`, ghi DOM, HAR và response vào thư mục tạm ngoài cây Git, trả JSON đã che. (3) `test_cp7_session_security.py` kiểm: TLS loopback `127.0.0.1:8443` bắt tay được với chứng chỉ SAN `127.0.0.1` và `localhost`; `/launch` lần hai và sau 60 giây trả 403; `/test-driver/issue-capability` trả 404; Host `evil.example` bị từ chối; POST với Origin `https://evil.example` bị từ chối; POST thiếu token CSRF bị từ chối; cookie `cp_session` HttpOnly, Secure, SameSite=Strict và `csrf_token` Secure, SameSite=Strict; bí mật tổng hợp `cp7-canary` ghi qua broker có 0 lần khớp trong DOM, HAR, log thư mục dữ liệu và body response. Trần chi phí: 0 USD, không gọi AI. Cách dừng: `python tools/launcher/launcher.py stop`; hạn 20 phút.
    instrument: `test_cp7_session_security.py`; `node --check` cho tệp probe; probe `report.md` có đủ 10 mục `RG-01.*` PASS.
    counterexample: dùng `/test-driver`; in capability; canary là bí mật thật; sửa `src/**` hoặc `ui/dist`.
- testCommands:
  - `git diff --check`
  - `node --check tools/real/cp7_browser_probe.js`
  - `python -m pytest tests/real/test_cp7_session_security.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-2/report.md').read_text(encoding='utf-8'); keys = ['tls_loopback', 'launch_one_time', 'launch_expiry', 'test_driver_404', 'host_rejected', 'origin_rejected', 'csrf_required', 'cookie_flags', 'canary_zero_hits', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-01[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-3: Drive, OAuth và toàn vẹn trên tài khoản thật

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_drive_real.py`
  - `docs/delivery-evidence/cp7-3/report.md`
- dependsOn: `CP7-2`
- resourceLocks: `LOCK-CP7`, `LOCK-EXTERNAL-DRIVE`
- bindingRefs: gate RG-02; `src/controlplane/infrastructure/storage/drive_object_store.py`; `src/controlplane/security/broker.py`
- acceptance:
  - requirement: (1) Điều kiện: user đã chạy `python tools/launcher/launcher.py oauth` (điểm dừng 1); test chỉ kiểm alias `drive-primary` có trong kho DPAPI (không đọc giá trị), thiếu thì `BLOCKED` (`WAITING_USER_OAUTH`). (2) Dùng `DriveObjectStore` với `DriveTokenBrokerPort` thật: upload resumable ba tệp ngẫu nhiên 1, 9 và 40 MiB vào `AI-Auto-Video-Creator/cp7-fixture/<runId>/`; md5 Drive bằng md5 cục bộ 3/3; tải lại một tệp và sha256 khớp; upload lại với file ID đã cấp trả 409 và vẫn đúng một bản; URI phiên không tồn tại (404 thật) thì mở phiên mới và hoàn tất; bearer cố định không hợp lệ trả 401 và job chuyển chờ credential, không mất; từ chối upload khi dự phóng dung lượng trống dưới 20% (`drive.quota_reserve_ratio`, tính trên quota thật); phạm vi `drive.file`; token 0 lần xuất hiện ngoài kho DPAPI. (3) Dọn bằng CLEANUP_AUTHORIZED chỉ trong `cp7-fixture/<runId>/`; số tệp ngoài thư mục này không đổi. Trần chi phí: 0 USD, ≤ 60 MiB lên Drive, ≤ 200 lời gọi API. Cách dừng: Ctrl+C; hạn 30 phút; dọn trong `finally`.
    instrument: `test_cp7_drive_real.py` và probe `report.md` có đủ 12 mục `RG-02.*` PASS.
    counterexample: đóng bằng fake Drive; đọc `Credentials/`; in token hay file ID đầy đủ; xóa tệp ngoài `cp7-fixture`; thu hồi refresh token thật (OI-CP7-07).
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_drive_real.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-3/report.md').read_text(encoding='utf-8'); keys = ['oauth_present', 'scope_drive_file', 'upload_md5', 'resumable_chunks', 'sha256_redownload', 'conflict_409', 'session_expired', 'token_invalid', 'quota_reserve', 'token_outside_vault', 'cleanup_namespace', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-02[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-4: AI qua 9Router thật và chi phí

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_ai_real.py`
  - `docs/delivery-evidence/cp7-4/report.md`
- dependsOn: `CP7-2`
- resourceLocks: `LOCK-CP7`
- bindingRefs: gate RG-03; `src/creative/adapters/real_ai_invocation.py`; `src/creative/adapters/real_route_executor.py`; `docs/parallel-delivery/bindings/j-provider-route.json`
- acceptance:
  - requirement: (1) Dùng hồ sơ `production` và `RoutedInvocationService` (J-18) qua `real_ai_invocation.py`; 6 vai trò (`analysis`, `angle`, `script`, `selection`, `metadata`, `image_safety`) × 10 lời gọi thật tới `http://127.0.0.1:20128/v1`, model `ag/gemini-3.8-flash-high`; `image_safety` dùng ảnh seed an toàn `bg-01` đến `bg-12`. (2) Đạt: ≥ 57/60 lời gọi qua đúng validator của D hoặc `WAITING_PROVIDER` hợp lệ; 0 request tới host hay cổng khác; 100% lời gọi có bản ghi chi phí; bản ghi và log 0 lần khớp secret; p95 độ trễ ≤ 120 giây; `hard_stop` bật, `monthly_limit` 50 USD, cảnh báo 80% = 40 USD. (3) `quota_wait` là mục soft: PASS chỉ khi gặp 429 hoặc `BUDGET_BLOCKED` thật rồi job chờ và tự chạy tiếp; không gặp thì `NOT_OBSERVED`, không giả lập. Trần chi phí: ≤ 60 lời gọi, ledger +5 USD trong slice; ledger tháng ≥ 40 USD thì `BLOCKED`. Cách dừng: `CostGuard` dừng khi chạm trần; `hard_stop` của J; Ctrl+C; hạn 45 phút.
    instrument: `test_cp7_ai_real.py` và probe `report.md`: 8 mục `RG-03.*` PASS, `quota_wait` PASS hoặc NOT_OBSERVED.
    counterexample: transport giả; gọi host khác 9Router; coi hết hạn mức là FAILED cuối; secret vào record; ép hết hạn mức bằng giả lập.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_ai_real.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-4/report.md').read_text(encoding='utf-8'); keys = ['six_roles_valid', 'router_host_only', 'ledger_recorded', 'record_no_secret', 'latency_p95', 'budget_guard', 'warn_80', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-03[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert re.search(r'(?m)^RG-03[.]quota_wait: (?:PASS|NOT_OBSERVED)[ \t]*\r?(?:\n|\Z)', t), 'quota_wait'; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-5: Thu thập RSS/web thật và khóa holdout

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_collection_real.py`
  - `tests/real/fixtures/cp7_holdout_manifest.json`
  - `docs/delivery-evidence/cp7-5/report.md`
- dependsOn: `CP7-2`
- resourceLocks: `LOCK-CP7`
- bindingRefs: gate RG-04; `tools/launcher/prod/sources.json`; `src/source_ingestion/adapters/real_feed_source.py`
- acceptance:
  - requirement: (1) Bảy nguồn trong `tools/launcher/prod/sources.json` qua `real_http_transport.py` và `real_feed_source.py` (SecureFetcher): mỗi nguồn feed, ≤ 5 bài và ảnh kèm; thêm một URL 404 thật của chính nguồn (đường dẫn `cp7-not-found`); dừng giữa lượt rồi chạy tiếp. (2) Đạt: ≥ 6/7 feed trả 200 và parse ≥ 5 mục; ≥ 90% bài mẫu trích ≥ 600 ký tự; 0 redirect tới địa chỉ riêng tư; không quá 4 fetch toàn cục và 1 fetch mỗi host; nguồn 404 không dừng nguồn khác; chạy tiếp từ checkpoint không tạo bài trùng; raw bytes có sha256; thời gian lượt được ghi (MEASURED). (3) `cp7_holdout_manifest.json`: 40 cặp bài chọn từ mẫu bằng quy tắc xác định (hạt giống cố định), chỉ id và sha256 raw bytes, không nội dung bài; băm manifest ghi vào report trước khi dùng bài mẫu làm đầu vào prompt. Phần scheduler cloud là `OUT_OF_V1_SCOPE` (OI-CP7-03), không ghi PASS. Trần chi phí: 0 USD; ≤ 35 bài, ≤ 35 ảnh, ≤ 200 MiB. Cách dừng: `Deadline` 30 phút; Ctrl+C.
    instrument: `test_cp7_collection_real.py` và probe `report.md` có đủ 10 mục `RG-04.*` PASS.
    counterexample: feedparser hay trafilatura tự mở mạng; bỏ SSRF policy ở hop redirect; fixture thay nguồn thật; nhúng nội dung bài vào manifest; ghi PASS cho scheduler cloud.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_collection_real.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-5/report.md').read_text(encoding='utf-8'); keys = ['feeds_alive', 'extraction_ratio', 'ssrf_policy', 'concurrency_limits', 'source_404_isolated', 'checkpoint_resume', 'raw_hash', 'cycle_time', 'holdout_locked', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-04[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-6: TTS Kokoro và aligner faster-whisper thật

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_voice_real.py`
  - `docs/delivery-evidence/cp7-6/report.md`
- dependsOn: `CP7-2`
- resourceLocks: `LOCK-CP7`, `LOCK-DESKTOP-GPU`
- bindingRefs: gate RG-05; `src/voice/adapters/real_kokoro_tts.py`; `src/voice/adapters/real_whisper_aligner.py`; `tools/launcher/prod/model-weights.lock.json`
- acceptance:
  - requirement: (1) Điều kiện: `tools/launcher/prod/model-weights.lock.json` có `status` PINNED và sha256 khớp tệp trong `LOCALAPPDATA/AIAutoVideoCreator/models` (OI-CP7-01); thiếu thì `BLOCKED`, không bịa hash. (2) `real_kokoro_tts.py`: 20 đoạn thoại tiếng Anh 15–60 từ và 5 kịch bản 150–190 từ, ghi `actual_duration_ms`; `real_whisper_aligner.py` chạy trên giọng có nhạc nền −20 dB và SFX; mốc câu so với `silencedetect` của FFmpeg đã ghim. (3) Đạt: 100% WAV hợp lệ (24 kHz, mono, thời lượng > 0); tỷ lệ từ không khớp ≤ 5% ở ≥ 95% đoạn; lệch mốc đầu/cuối câu ≤ 150 ms ở ≥ 95% câu; sau hiệu chỉnh `speech_rate_wpm` ước lượng lệch ≤ 10% ở ≥ 90% đoạn, ghi giá trị đo để Control tạo revision cấu hình (slice không sửa profile); VRAM đỉnh (`nvidia-smi` mỗi giây) ≤ 11 GiB. Trần chi phí: 0 USD; GPU ≤ 60 phút. Cách dừng: `Deadline` 90 phút; Ctrl+C.
    instrument: `test_cp7_voice_real.py` và probe `report.md` có đủ 7 mục `RG-05.*` PASS.
    counterexample: TTS hoặc aligner giả; hash trọng số bịa; tải trọng số vào cây Git; ghi PASS khi thiếu GPU.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_voice_real.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-6/report.md').read_text(encoding='utf-8'); keys = ['weights_pinned', 'tts_valid_wav', 'aligner_unmatched', 'aligner_timing', 'speech_rate_calibrated', 'vram_peak', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-05[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-7: An toàn ảnh thật

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_image_safety_real.py`
  - `docs/delivery-evidence/cp7-7/report.md`
- dependsOn: `CP7-4`
- resourceLocks: `LOCK-CP7`
- bindingRefs: gate RG-06; `src/voice/adapters/real_llm_image_safety.py`; ROADMAP-OPEN-006
- acceptance:
  - requirement: (1) Điều kiện: Sensitive Image Set ngoài cây Git ở `LOCALAPPDATA/AIAutoVideoCreator/real-fixtures/sensitive/` kèm manifest sha256, đủ ≥ 7 nhóm × ≥ 5 ảnh (safe, trẻ em, máu me, vũ khí, uncertain, detector/transform lỗi, không đọc được); thiếu thì `BLOCKED` (OI-CP7-02), không tự sinh ảnh giả để PASS. (2) `real_llm_image_safety.py` qua tuyến `image_safety` và `boxblur` (luma_radius 40, luma_power 3) của FFmpeg đã ghim; lỗi detector thật bằng timeout 1 ms trên tuyến thật. (3) Đạt: 0 ảnh trẻ em, máu me, vũ khí kết thúc ở safe hoặc ở dạng không che; 100% ảnh uncertain, lỗi, không đọc được không bao giờ thành safe; vùng che giảm độ sắc nét ≥ 50% theo `signalstats` (D8); tỷ lệ phát hiện chỉ ghi số đo, không tuyên bố ngưỡng; báo cáo không nhúng ảnh. Trần chi phí: ≤ 70 lời gọi AI, ledger +5 USD. Cách dừng: `CostGuard`; `Deadline` 45 phút; Ctrl+C.
    instrument: `test_cp7_image_safety_real.py` và probe `report.md` có đủ 7 mục `RG-06.*` PASS.
    counterexample: detector giả; ảnh nhạy cảm vào cây Git hay report; coi lỗi detector là safe; không rõ quyền ảnh.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_image_safety_real.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-7/report.md').read_text(encoding='utf-8'); keys = ['set_present', 'false_safe_zero', 'uncertain_never_safe', 'blur_applied', 'failure_modes', 'detection_rate_recorded', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-06[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-8: Render, QC và tranh GPU thật

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_render_real.py`
  - `tests/real/test_cp7_gpu_contention.py`
  - `tools/real/cp7_media_probe.py`
  - `docs/delivery-evidence/cp7-8/report.md`
- dependsOn: `CP7-6`
- resourceLocks: `LOCK-CP7`, `LOCK-DESKTOP-GPU`
- bindingRefs: gate RG-07; `src/render/adapters/real_ffmpeg_renderer.py`; `src/render/adapters/real_ffprobe_probe.py`
- acceptance:
  - requirement: (1) `cp7_media_probe.py` (stdlib) bọc ffprobe, `loudnorm`, `silencedetect`, `signalstats` của FFmpeg đã ghim (sha256 `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`). (2) `test_cp7_render_real.py`: 5 preset × 2 video qua `real_ffmpeg_renderer.py` bằng NVENC và 1 video libx264 dự phòng, đầu vào là hook, ảnh seed và giọng của CP7-6. Đạt: 1080×1920, 30 fps, H.264, AAC, MP4; 61–70 giây; ≤ 157286400 byte; `-f null` exit 0; hook similarity ≥ 0.85, hook audio ≥ −40 dBFS, visual continuity ≥ 0.6; phụ đề burn-in thấy được ở ≥ 90% mốc lấy mẫu; lệch karaoke ≤ 150 ms ở ≥ 95% từ (đối chiếu tệp ASS với mốc aligner và lấy mẫu khung hình); loudness và true peak chỉ ghi số đo (warn_only: −16 LUFS ± 1,5 LU, ≤ −1,5 dBTP); ghi render p95 cho G02. (3) Lỗi thật: kill FFmpeg giữa lượt, cắt cụt output, timeout sau side effect, output hỏng, chốt chặn `working_set.disk_reserve_bytes` bằng số đo đĩa thật (không lấp đầy đĩa). Đạt: attempt `failed` và không còn tệp dở; `OUTCOME_UNKNOWN` rồi reconcile bằng probe; output hỏng thì QC FAIL; chốt chặn từ chối. (4) `test_cp7_gpu_contention.py`: STT, TTS và render cùng lúc dưới `LOCK-DESKTOP-GPU` 2 khe: không quá 2 khe cùng lúc, yêu cầu thứ 3 → `WAITING_CAPABILITY`, 0 OOM, VRAM đỉnh ≤ 11 GiB. Trần chi phí: 0 USD; GPU ≤ 4 giờ; ≤ 5 GiB tạm. Cách dừng: `Deadline` 4 giờ kill tiến trình con; Ctrl+C.
    instrument: hai tệp test và probe `report.md` có đủ 20 mục `RG-07.*` PASS.
    counterexample: renderer giả; lấp đầy đĩa thật; bỏ QC để tăng tốc; benchmark ngắn ngoại suy; FFmpeg không phải bản đã ghim.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_render_real.py tests/real/test_cp7_gpu_contention.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-8/report.md').read_text(encoding='utf-8'); keys = ['ffmpeg_pin_used', 'nvenc_presets', 'libx264_fallback', 'container_spec', 'duration_61_70', 'size_cap', 'playable', 'subtitle_visible', 'karaoke_timing', 'hook_checks', 'loudness_recorded', 'crash_recovery', 'partial_output', 'timeout_outcome_unknown', 'corrupt_qc_fail', 'disk_guard', 'gpu_two_slots', 'vram_peak', 'render_p95', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-07[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-9: Runtime PostgreSQL và Temporal thật, ranh giới lỗi

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_runtime_fault.py`
  - `docs/delivery-evidence/cp7-9/report.md`
- dependsOn: `CP7-2`
- resourceLocks: `LOCK-CP7`, `LOCK-POSTGRES-TEST-DB`
- bindingRefs: gate RG-08; OI-CP7-05; `tools/launcher/launcher.py`
- acceptance:
  - requirement: (1) Với PostgreSQL thật trong Docker (database dùng-một-lần `cp7_<runId>`, partition `db:cp7_<runId>`), test chạy bằng subprocess `python -m pytest ... -q -p no:cacheprovider -rs` các bộ `tests/integration/convergence/test_cp3_migration_sequence.py`, `tests/integration/convergence/test_cp4_queries_postgres.py`, `tests/integration/convergence/test_cp5_completion_uow.py`, `tests/integration/orchestration/test_g_commit_completion.py` và đọc lý do skip. (2) `launcher down` rồi `start`: volume `aiavc_pgdata` giữ nguyên, số hàng các bảng chính trước và sau bằng nhau. (3) `tests/m1` bằng interpreter khoá, loại `tests/m1/p3/test_drive_live_probe.py::test_live_e3_drive_verification` (OI-CP7-05): 92 passed, 0 failed; thiếu runtime thì `BLOCKED`; không chạy h36 nguyên văn và không sửa test M1, M2. Đạt: 0 skip có lý do DSN hoặc PostgreSQL; mọi bộ exit 0; rollback đúng tại trước, trong và sau side effect ngoài. Trần chi phí: 0 USD; ≤ 40 phút. Cách dừng: `Deadline` 60 phút; chỉ xóa database `cp7_<runId>` do chính test tạo, trong `finally`.
    instrument: `test_cp7_runtime_fault.py` và probe `report.md` có đủ 6 mục `RG-08.*` PASS.
    counterexample: DSN trỏ vào database sản xuất; xóa database không do test tạo; đọc `Credentials/` qua test M1; fake thay PostgreSQL thật.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_runtime_fault.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-9/report.md').read_text(encoding='utf-8'); keys = ['pg_suites_no_dsn_skip', 'commit_rollback_boundaries', 'volume_preserved', 'row_counts_equal', 'm1_regression_adjusted', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-08[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-10: R4 Video Alpha có giám sát trên ngăn xếp thật

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_video_alpha_e2e.py`
  - `tools/real/cp7_batch_driver.py`
  - `docs/delivery-evidence/cp7-10/report.md`
- dependsOn: `CP7-3`, `CP7-4`, `CP7-5`, `CP7-6`, `CP7-7`, `CP7-8`, `CP7-9`
- resourceLocks: `LOCK-CP7`, `LOCK-EXTERNAL-DRIVE`, `LOCK-DESKTOP-GPU`
- bindingRefs: gate RG-09; `src/controlplane/api/wiring/production.py`; `tools/launcher/prod/profile.json`
- acceptance:
  - requirement: (1) `cp7_batch_driver.py` tạo lô 1 video qua Control API (phiên từ `/launch`), theo dõi từng stage và ghi trace đã che. (2) Đạt: snapshot → script AI → TTS → align → render → upload Drive → verify → completion đều SUCCEEDED; 0 adapter `Fake` hay `Memory` trong composition production (đọc chỉ đọc `controlplane.api.wiring.production`); QC hard gate 100%; chỉ đếm output sau khi cloud verified (md5 khớp); chỉ dọn bản local sau verified; script, góc và media không đổi so với snapshot (băm khớp); truy vết đủ snapshot, model, prompt, config. (3) Giữa lúc render chạy `launcher stop` rồi `start`: sẵn sàng ≤ 300 giây (`resume.ready_within_seconds`) và stage đã SUCCEEDED không chạy lại (số attempt không tăng). Trần chi phí: ≤ 25 lời gọi AI, ledger +3 USD, Drive ≤ 200 MiB, ≤ 2 giờ. Cách dừng: `python tools/launcher/launcher.py stop`; `Deadline` 2 giờ; `CostGuard`.
    instrument: `test_cp7_video_alpha_e2e.py` và probe `report.md` có đủ 10 mục `RG-09.*` PASS.
    counterexample: stage dùng fake; đếm output chưa cloud verified; F đổi script hay media ngoài fallback plan; chạy lại stage đã xong sau resume.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-10/report.md').read_text(encoding='utf-8'); keys = ['stages_succeeded', 'no_fake_adapters', 'qc_hard_gates', 'cloud_verified_before_count', 'cleanup_after_verify', 'plan_unchanged', 'resume_300s', 'no_rerun_completed', 'trace_complete', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-09[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-11: Đêm chạy 100 video trong 12 giờ

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_overnight.py`
  - `tools/real/cp7_overnight_monitor.py`
  - `docs/delivery-evidence/cp7-11/report.md`
- dependsOn: `CP7-10`
- resourceLocks: `LOCK-CP7`, `LOCK-EXTERNAL-DRIVE`, `LOCK-DESKTOP-GPU`
- bindingRefs: gate RG-10; `tools/launcher/prod/profile.json` (`batch`, `budget`, `resume`); OI-CP7-06, OI-CP7-11
- acceptance:
  - requirement: (1) Trước khi chạy: Drive trống ≥ 12 GiB cộng 20% dự trữ (đọc `storageQuota`), thiếu thì `BLOCKED` (OI-CP7-06). (2) Lô `batch.target` = 100, `videos_per_news_per_round` = 2, không thao tác sau khi bắt đầu; `cp7_overnight_monitor.py` ghi mỗi 5 phút sổ đếm, ledger, ổ đĩa, VRAM; khoảng giờ thứ 6 chạy `launcher stop` rồi `start`; thêm một nguồn URL 404 thật. (3) Đạt: ≥ 100 video hợp lệ đã cloud verified trong ≤ 12 giờ kể từ lúc bắt đầu lô (thời gian chờ hạn mức tính vào 12 giờ, báo riêng `wait_provider_seconds`); ≥ 95% video đủ đầu vào hoàn thành không thao tác, không loại lỗi do hệ thống khỏi mẫu số; 0 job biến mất không trạng thái hoặc log; lỗi một nguồn hoặc một video không dừng việc độc lập; resume ≤ 300 giây và không chạy lại stage đã xong; working set ≤ 20 GiB; 0 secret trong log; số liệu theo stage cho G02 và chi phí cho G03. `warn_80_visible` là mục soft (PASS hoặc NOT_OBSERVED). Trần chi phí: ledger AI cả đêm +25 USD và tháng ≤ 50 USD (`hard_stop`); Drive ≤ 12 GiB. Cách dừng: `Deadline` ở 12 giờ 15 phút gọi `python tools/launcher/launcher.py stop` (dừng worker, việc làm tiếp khi bật lại, không mất dữ liệu); cảnh báo ở 40 USD.
    instrument: `test_cp7_overnight.py` và probe `report.md`: 12 mục `RG-10.*` PASS, `warn_80_visible` PASS hoặc NOT_OBSERVED.
    counterexample: ngoại suy từ benchmark ngắn; loại video lỗi hệ thống khỏi mẫu số; đếm output chưa cloud verified; thao tác tay giữa lô.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-11/report.md').read_text(encoding='utf-8'); keys = ['valid_synced_100', 'within_12h', 'auto_ratio_95', 'no_vanished_jobs', 'failure_isolated', 'resume_300s_midrun', 'no_rerun_completed', 'cost_under_cap', 'working_set_cap', 'drive_quota_ok', 'stage_metrics', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-10[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert re.search(r'(?m)^RG-10[.]warn_80_visible: (?:PASS|NOT_OBSERVED)[ \t]*\r?(?:\n|\Z)', t), 'warn_80_visible'; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-12: Hiệu năng UI, xoay secret và rollback cấu hình

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_ui_perf.py`
  - `tests/real/test_cp7_rotation_rollback.py`
  - `docs/delivery-evidence/cp7-12/report.md`
- dependsOn: `CP7-11`
- resourceLocks: `LOCK-CP7`
- bindingRefs: gate RG-11; `tools/real/cp7_browser_probe.js` (chỉ gọi, không sửa); OI-CP7-07
- acceptance:
  - requirement: (1) `test_cp7_ui_perf.py`: Chromium Playwright 1920×1080, ≥ 30 lần mỗi thao tác (cold và warm riêng) trên màn `jobs`, `batches`, `artifacts`, `cost`, trên cơ sở dữ liệu sau CP7-11 (≥ 100 video job; băm bảng đếm ghi vào report). Đạt: p95 thao tác UI ≤ 2000 ms và p95 ACK lệnh ≤ 1000 ms ở cả cold và warm; ngắt SSE rồi nối lại không lặp event, cursor ngoài retention thì resync. (2) `test_cp7_rotation_rollback.py`: xoay bí mật tổng hợp `cp7-rotate` sang version mới qua broker, version cũ bị từ chối; thu hồi credential ngắn hạn của J khi job đang chạy thì job chuyển chờ credential, không mất; công bố cấu hình rồi rollback bằng revision mới, băm cấu hình trở về giá trị trước. Không thu hồi token Drive thật. Trần chi phí: 0 USD, không gọi AI. Cách dừng: `Deadline` 90 phút; Ctrl+C.
    instrument: hai tệp test và probe `report.md` có đủ 9 mục `RG-11.*` PASS.
    counterexample: đo trên dữ liệu rỗng; gộp cold và warm; xoay hay thu hồi bí mật thật; sửa `src/**`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_ui_perf.py tests/real/test_cp7_rotation_rollback.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-12/report.md').read_text(encoding='utf-8'); keys = ['ui_p95_cold', 'ui_p95_warm', 'ack_p95_cold', 'ack_p95_warm', 'sse_resync', 'rotation_old_version_rejected', 'revoke_job_waiting', 'rollback_hash_restored', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-11[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-13: Restore drill và đối soát Drive

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_restore_drill.py`
  - `docs/delivery-evidence/cp7-13/report.md`
- dependsOn: `CP7-12`
- resourceLocks: `LOCK-CP7`, `LOCK-EXTERNAL-DRIVE`
- bindingRefs: gate RG-12; `docs/runbook/runbook-v1.md` mục 4 và 5; `tools/launcher/launcher.py`
- acceptance:
  - requirement: (1) Chạy theo runbook: `launcher backup` → upload một output nhỏ vào `AI-Auto-Video-Creator/cp7-fixture/<runId>/` sau backup → `launcher stop` → `launcher restore --file <dump>` → `launcher start`. (2) Đạt: sha256 `.dump` khớp tệp sidecar; có CSDL mới `controlplane_<yyyymmddHHMMSS>`; `state/recovery-epoch.json` ghi trước khi đổi `state/active-db`; kết quả và grant thuộc epoch cũ bị từ chối; CSDL cũ còn nguyên; số hàng bảng chính bằng lúc backup; đối soát Drive phát hiện output mới hơn backup và không cleanup trước khi reconcile xong; hệ thống sẵn sàng ≤ 300 giây sau `start`. Thay đổi `state/active-db` là có chủ đích; không xóa CSDL hay tệp nào ngoài `cp7-fixture/<runId>/`. Trần chi phí: 0 USD; ≤ 60 phút; Drive ≤ 10 MiB. Cách dừng: `Deadline` 60 phút; lỗi giữa chừng thì dừng, giữ nguyên CSDL cũ và báo `BLOCKED` kèm evidence.
    instrument: `test_cp7_restore_drill.py` và probe `report.md` có đủ 10 mục `RG-12.*` PASS.
    counterexample: restore đè lên CSDL đang dùng; xóa CSDL cũ; bỏ đối soát Drive; chạy cleanup trước reconcile.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_restore_drill.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-13/report.md').read_text(encoding='utf-8'); keys = ['dump_sha256', 'new_db_created', 'epoch_before_switch', 'old_epoch_rejected', 'old_db_kept', 'row_counts_equal', 'drive_reconcile_newer', 'no_cleanup_before_reconcile', 'resume_after_restore', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-12[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`

### CP7-14: Mẫu 10 video và gói bằng chứng nghiệm thu R1–R6

- kind: work_package_slice
- ownedPaths:
  - `tests/real/test_cp7_sample_run.py`
  - `tools/real/cp7_acceptance_pack.py`
  - `docs/delivery-evidence/cp7-14/report.md`
- dependsOn: `CP7-13`, `CP7-5`
- resourceLocks: `LOCK-CP7`, `LOCK-EXTERNAL-DRIVE`, `LOCK-DESKTOP-GPU`
- bindingRefs: gate RG-13; `docs/implementation/cp7/plan.md` mục 5; `tests/real/fixtures/cp7_holdout_manifest.json`
- acceptance:
  - requirement: (1) Lô mẫu `batch.target.sample_run` = 10 trên hồ sơ `production` sau restore; đạt: 10 video hợp lệ và cloud verified; mỗi video truy vết đủ snapshot, model, prompt, config; các video cùng lượt của một tin có StoryAngle khác nhau; ảnh `UNVERIFIED` vào video sau khi che mờ tối thiểu logo và chi tiết nhạy cảm, không video nào chỉ có ảnh nền, thiếu ảnh thì dùng ảnh AI cùng phong cách với ảnh trong bài (OI-ADAPT-10, CLOSURE_NOTE CP7/RG-13). (2) `cp7_acceptance_pack.py` sinh trong `report.md`: bảng R1–R6 (mã chờ gốc, tệp bằng chứng, băm sha256, màn Dashboard tương ứng theo plan.md mục 5), bảng chấm 10 video (topic, media/hook) và bảng 40 cặp holdout (event-link) với cột nhãn của user để trống; không ô nào ghi thay user và không ghi user đã duyệt. Trần chi phí: ≤ 60 lời gọi AI, ledger +5 USD, Drive ≤ 1,5 GiB, ≤ 3 giờ. Cách dừng: `python tools/launcher/launcher.py stop`; `Deadline` 3 giờ; `CostGuard`.
    instrument: `test_cp7_sample_run.py` và probe `report.md` có đủ 10 mục `RG-13.*` PASS. Khoá `rights_unverified_excluded` của probe giữ nguyên tên; xét theo CLOSURE_NOTE CP7/RG-13: PASS khi ảnh `UNVERIFIED` vào video sau khi che mờ tối thiểu và không video nào chỉ có ảnh nền.
    counterexample: tự điền nhãn hay duyệt thay user; dùng ảnh `UNVERIFIED` chưa che mờ logo và chi tiết nhạy cảm; video chỉ có ảnh nền; video chưa cloud verified; thiếu một trong R1–R6.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/real/test_cp7_sample_run.py -q -p no:cacheprovider`
  - `python -c "import re, pathlib; t = pathlib.Path('docs/delivery-evidence/cp7-14/report.md').read_text(encoding='utf-8'); keys = ['sample_10_valid', 'cloud_verified_10', 'trace_per_video', 'story_angle_distinct', 'rights_unverified_excluded', 'holdout_sheet_40', 'video_sheet_10', 'pack_r1_r6_complete', 'no_user_field_filled', 'secret_scan']; bad = [k for k in keys if not re.search(r'(?m)^RG-13[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', t)]; assert not bad, bad; assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', t), 'failed item'; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', t), 'secret pattern'"`
