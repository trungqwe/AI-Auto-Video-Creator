# Runbook vận hành v1

Hệ thống AI Auto Video Creator phiên bản v1 chạy trên máy trạm cục bộ (Windows). Toàn bộ hạ tầng lưu trữ và điều phối gồm PostgreSQL và Temporal Server được đóng gói trong Docker, cấu hình an toàn tuyệt đối chỉ mở giao diện mạng loopback `127.0.0.1` (cổng PostgreSQL `57028` và cổng Temporal `7233`). Giao diện ứng dụng người dùng và API vận hành qua HTTPS loopback tại `https://127.0.0.1:8443`.

Mọi tác vụ quản lý vòng đời được thực hiện thông qua công cụ dòng lệnh:
```bash
python tools/launcher/launcher.py <lệnh>
```
Lệnh trên bắt buộc thực thi bằng Python interpreter đã khóa của dự án (`.local-tools/runtime/33f06a7a/venv/Scripts/python.exe`). Toàn bộ dữ liệu phiên làm việc, chứng chỉ TLS, khóa bí mật, kho DPAPI, mô hình học máy và tệp sao lưu được lưu trữ ngoài cây Git tại thư mục `%LOCALAPPDATA%\AIAutoVideoCreator` (hoặc đường dẫn chỉ định qua biến môi trường `AIAVC_DATA_DIR`). Launcher cam kết không bao giờ in bí mật, mật khẩu CSDL, khóa token hay capability ra console và nhật ký log.

## 1. Khởi động

### Điều kiện tiên quyết
1. Docker Desktop đã được khởi động và đang chạy trên hệ thống máy trạm.
2. Đã chuẩn bị sẵn tệp thông tin ủy quyền Google Cloud OAuth client loại Desktop (`oauth-client.json`) đặt ngoài cây Git theo hướng dẫn tại mục `oauth`.
3. FFmpeg ghim tại `C:\ffmpeg\bin\ffmpeg.exe` (hoặc đường dẫn đặt qua biến môi trường `AIAVC_FFMPEG_PATH`), có sha256 khớp `tools/runtime/runtime.lock.json`; launcher dùng nó để sinh media seed ở lần start đầu tiên.

### Quy trình khởi động
Người vận hành chạy lệnh:
```bash
python tools/launcher/launcher.py start
```
Thứ tự thực thi tuần tự của launcher bao gồm:
1. Đọc và xác thực cấu hình `docker-compose.yml` đối chiếu với digest SHA-256 bất biến trong `runtime.lock.json`.
2. Tạo mật khẩu ngẫu nhiên an toàn cho PostgreSQL (nếu chưa có) và khởi động container `aiavc-postgres` và `aiavc-temporal` ở chế độ ngầm (`docker compose up -d`).
3. Chờ dịch vụ PostgreSQL và Temporal Server đạt trạng thái sẵn sàng (healthcheck và TCP socket mở).
4. Khởi chạy `MigrationRunner` áp dụng các bản di chuyển lược đồ CSDL PostgreSQL.
5. Khởi tạo workspace và actor mặc định cho người vận hành trong CSDL.
6. Mỗi lần start nạp lại, không nhân đôi, nguồn RSS, prompt, render config và bộ media seed theo `hooks.json` (ảnh nền bg-01..12, hook hình vh-01..05, hook âm thanh ah-01..05, tự tạo `SELF_GENERATED`). Lần đầu, hay khi thiếu hoặc lệch tệp so với `seed-manifest.json`, launcher sinh lại cả bộ 22 tệp vào `%LOCALAPPDATA%\AIAutoVideoCreator\seed` (hoặc `<AIAVC_DATA_DIR>\seed`) bằng FFmpeg ghim, cùng sha256, rồi nhập vào catalog và chép vào `staging\media`. Thiếu media seed thì `media_select` dừng `INPUT_NOT_READY`. Người vận hành không thao tác gì.
7. Sinh chứng chỉ TLS tự ký (SAN gồm `127.0.0.1` và `localhost`) ngoài cây Git nếu chưa tồn tại.
8. Xóa cờ dừng tiến trình (`stop.request`) và khởi chạy tiến trình con phục vụ ngầm (`_serve`).
9. Tiến trình worker kết nối Temporal cluster, đồng thời cấp capability một lần có thời hạn 60 giây và tự động mở trình duyệt tại địa chỉ `/launch`.

### Cảnh báo chứng chỉ TLS trên trình duyệt (OI-ADAPT-07)
Trong lần truy cập đầu tiên, trình duyệt web sẽ cảnh báo chứng chỉ tự ký chưa tin cậy:
- Người vận hành bấm **Nâng cao (Advanced)** và chọn **Tiếp tục truy cập 127.0.0.1 (không an toàn)**.
- Hoặc nhập chứng chỉ `tls/cert.pem` vào kho chứng chỉ tin cậy của người dùng hiện tại (Trusted Root Certification Authorities) trên Windows để loại bỏ hoàn toàn cảnh báo.

### Cấp quyền Google Drive OAuth
Sau lần khởi động đầu tiên, người vận hành cần thực hiện ủy quyền Google Drive một lần duy nhất qua lệnh:
```bash
python tools/launcher/launcher.py oauth
```
Quy trình thực hiện gồm 4 bước rõ ràng:
- **Bước 1.** Xác nhận tệp client secrets JSON đặt ngoài cây Git (mặc định tại `%LOCALAPPDATA%\AIAutoVideoCreator\secrets\oauth-client.json`).
- **Bước 2.** Launcher hiển thị liên kết xác thực cục bộ và mở nó trên trình duyệt mặc định.
- **Bước 3.** Đăng nhập đúng một tài khoản Google Drive và chấp thuận phạm vi quyền tối thiểu `drive.file` một lần duy nhất.
- **Bước 4.** Chờ thông báo đã nhận xác nhận trên trình duyệt rồi đóng tab. Refresh token được mã hóa an toàn vào kho DPAPI cục bộ (`vault/`) và không bao giờ hiển thị trên màn hình.

## 2. Dừng

Hệ thống hỗ trợ hai cấp độ dừng tùy theo mục đích vận hành:

### Dừng tác vụ xử lý (Worker & Web Application)
```bash
python tools/launcher/launcher.py stop
```
- Lệnh `stop` chỉ gửi tín hiệu yêu cầu dừng (`stop.request`) tới worker và ứng dụng, chờ worker hoàn tất công việc đang dang dở trong khoảng thời gian chờ an toàn (60 giây).
- Các container Docker (`aiavc-postgres`, `aiavc-temporal`) và volume lưu trữ CSDL (`aiavc_pgdata`) được giữ nguyên 100%.
- Tuyệt đối không ép tắt cưỡng bức để bảo đảm tính toàn vẹn của tác vụ đang render hoặc đồng bộ.

### Gỡ bỏ container dịch vụ (Compose Down)
```bash
python tools/launcher/launcher.py down
```
- Lệnh `down` sẽ kiểm tra và yêu cầu worker dừng trước, sau đó thực thi `docker compose down`.
- Thể tích dữ liệu `aiavc_pgdata` và mọi tệp ngoài Git được bảo toàn trọn vẹn. Lệnh không sử dụng bất kỳ cờ xóa volume nào (`-v`, `--volumes`, `--rmi`).

## 3. Tiếp tục

Khi cần tiếp tục vận hành sau khi dừng hoặc sau khi khởi động lại máy tính:
1. Đảm bảo Docker Desktop đã hoạt động.
2. Chạy lại lệnh:
```bash
python tools/launcher/launcher.py start
```
Hệ thống sẽ tự động khôi phục và tiếp tục:
- Nhờ cơ chế lưu trữ trạng thái bền bỉ của Temporal Server, các workflow đang chạy dở dang sẽ tiếp tục thực thi từ checkpoint gần nhất mà không làm thất thoát tiến độ.
- Trường hợp hệ thống chạm hạn mức chi phí AI hàng tháng hoặc bị giới hạn tốc độ (rate limit), hệ thống tự động tạm dừng chờ và định kỳ thăm dò phục hồi, sau đó tiếp tục công việc mà không cần can thiệp thủ công.
- Mục tiêu sẵn sàng hoạt động trở lại của hệ thống được quy định trong tham số `resume.ready_within_seconds` (300 giây).
## 4. Sao lưu

Để bảo toàn dữ liệu giao dịch và cấu hình của hệ thống, người vận hành thực hiện tạo bản sao lưu định kỳ qua lệnh:
```bash
python tools/launcher/launcher.py backup [--out <đường_dẫn_tùy_chọn>]
```

Cơ chế sao lưu:
- Lệnh sử dụng tiện ích nội bộ của PostgreSQL qua lệnh gọi:
  ```bash
  docker exec aiavc-postgres pg_dump -U controlplane -Fc -d controlplane
  ```
- Tệp kết xuất được lưu dưới định dạng nén nhị phân tùy biến (`-Fc`) tại thư mục `backups/aiavc-<timestamp>.dump`.
- Tệp mã băm kiểm tra tính toàn vẹn kèm theo (`.dump.sha256`) được tự động sinh song song.
- **Lưu ý quan trọng:** Bên cạnh bản sao lưu CSDL PostgreSQL, người vận hành cần sao lưu thêm hai thư mục `vault/` (chứa refresh token DPAPI) và `state/` (chứa định danh và recovery epoch). Bản sao lưu CSDL không thay thế cho quy trình đồng bộ và đối soát dữ liệu trên Google Drive (`reconcile Drive`).

## 5. Khôi phục

Quy trình khôi phục CSDL từ bản sao lưu bảo đảm nguyên tắc bất biến và an toàn tối đa:
```bash
python tools/launcher/launcher.py restore --file <đường_dẫn_tệp_dump> [--yes]
```

Các nguyên tắc vận hành khi khôi phục:
1. **Kiểm tra điều kiện:** Worker bắt buộc phải ở trạng thái đã dừng (`stop`). Tính toàn vẹn của tệp dump được xác minh tự động thông qua mã băm SHA-256 từ tệp sidecar trước khi thực thi bất kỳ thao tác nào trên Docker.
2. **Khởi tạo CSDL mới:** Launcher tạo một CSDL PostgreSQL hoàn toàn mới mang tên `controlplane_<yyyymmddHHMMSS>` và nạp dữ liệu bằng công cụ `pg_restore` (chạy qua `docker exec` vào container).
3. **Cấp recovery epoch mới:** Một recovery epoch độc bản có định dạng `rec-<yyyymmddHHMMSS>-<hex>` được sinh ra và ghi bền vững vào tệp `state/recovery-epoch.json` **TRƯỚC KHI** chuyển đổi tệp `state/active-db`.
4. **Bảo toàn CSDL cũ:** CSDL cũ được giữ nguyên trạng để đối chiếu và kiểm tra tính toàn vẹn (người vận hành có thể chủ động xóa thủ công sau khi đã kiểm tra hoàn tất).
5. **Cách ly trạng thái:** Mọi kết quả, sự kiện và grant thuộc recovery epoch cũ đều bị hệ thống từ chối dù generation hay revision có trùng khớp.
6. **Đối soát sau khôi phục:** Sau khi hoàn tất lệnh khôi phục, người vận hành cần khởi động lại hệ thống (`start`) và tiến hành đối soát trạng thái Google Drive, journal nhật ký và workflow dưới recovery epoch mới (CP7-ADAPT-10) trước khi kích hoạt quy trình dọn dẹp (cleanup).
7. **GIẢ ĐỊNH:** Biến môi trường `AIAVC_RECOVERY_EPOCH` được launcher cấp cho tiến trình ứng dụng con, tuy nhiên việc các bộ ghi dữ liệu kiểm tra epoch này chưa được kết nối hoàn chỉnh trong phạm vi gói này và sẽ hoàn thiện tại các mốc tiếp theo.

## 6. Xử lý lỗi

Bảng hướng dẫn chẩn đoán và khắc phục các sự cố thường gặp:

| Triệu chứng | Nguyên nhân khả dĩ | Cách xử lý |
| :--- | :--- | :--- |
| Docker chưa chạy (compose up lỗi) | Dịch vụ Docker Desktop bị tắt hoặc đang khởi động dở | Khởi động Docker Desktop, chờ biểu tượng chuyển màu xanh rồi chạy lại lệnh `start`. |
| Cổng 57028, 7233 hoặc 8443 bị chiếm | Ứng dụng khác hoặc phiên launcher cũ đang chiếm cổng mạng loopback | Kiểm tra tiến trình bằng `netstat -ano \| findstr <cổng>`, kết thúc tiến trình xung đột hoặc khởi động lại máy. |
| Chứng chỉ bị trình duyệt chặn | Trình duyệt cảnh báo chứng chỉ HTTPS tự ký chưa được tin cậy | Bấm "Nâng cao" chọn tiếp tục tới 127.0.0.1, hoặc nhập `tls/cert.pem` vào Trusted Root của Windows. |
| Truy cập `/launch` trả về mã lỗi 403 Forbidden | Capability URL chỉ dùng một lần đã được kích hoạt hoặc đã quá hạn 60 giây | Chạy `python tools/launcher/launcher.py stop` rồi chạy lại `start` để nhận đường dẫn capability mới. |
| Start báo `BLOCKED: thiếu cổng ProductionRuntime` | Thiếu adapter thật cho 6 cổng ProductionRuntime (gói J, G, I hoặc CP7) | Kiểm tra nhật ký `logs/serve.log`; đây là thiết kế fail-closed chuẩn khi chưa nối adapter sản xuất thực tế. |
| Start báo `Nạp media seed thất bại` | FFmpeg ghim thiếu hay lệch sha256, hoặc không ghi được thư mục dữ liệu | Đặt đúng FFmpeg ghim, kiểm quyền ghi rồi chạy lại `start` (không nhân đôi dữ liệu). |
| Di chuyển CSDL báo lệch checksum di chuyển | Tệp migration trong mã nguồn bị thay đổi trái phép sau khi áp dụng | Tuyệt đối không sửa tay CSDL; đối chiếu lịch sử git của `src/controlplane/infrastructure/db/migrations` và báo cáo điều phối. |
| Worker không thoát sau 60 giây khi chạy `stop` | Tiến trình worker đang thực hiện render video nặng hoặc đồng bộ khối lượng lớn | Không ép tắt; chờ tác vụ hiện tại hoàn tất tiến trình con rồi chạy lại lệnh `stop`. |
| Lệnh `oauth` báo lỗi thiếu tệp client | Chưa đặt tệp `oauth-client.json` tại `secrets/` hoặc biến `AIAVC_OAUTH_CLIENT_SECRETS` sai | Tải tệp cấu hình OAuth Desktop từ Google Cloud Console và đặt đúng vị trí ngoài cây Git. |
| Lệnh `oauth` bị quá thời gian chờ (timeout) | Người vận hành không hoàn tất đăng nhập trình duyệt trong 300 giây | Chạy lại lệnh `python tools/launcher/launcher.py oauth` và chấp thuận quyền ngay khi trình duyệt mở. |
| Tệp backup rỗng hoặc lệnh pg_dump báo lỗi | Container PostgreSQL chưa sẵn sàng hoặc đĩa lưu trữ cục bộ bị đầy | Kiểm tra trạng thái container bằng `status`, giải phóng dung lượng đĩa và thử lại. |
| Lệnh restore báo sai checksum mã băm | Tệp dump bị lỗi truyền dẫn hoặc tệp `.dump.sha256` không trùng khớp | Tải lại bản sao lưu gốc nguyên vẹn và xác minh mã băm SHA-256 trước khi khôi phục. |
| Hạn mức AI hàng tháng bị chạm ngưỡng | Tổng chi phí AI chạm mức monthly_limit đã cấu hình | Hệ thống tự động chuyển sang chế độ chờ; không cần thao tác, hạn ngạch sẽ tự phục hồi theo chu kỳ. |
## Phụ lục. Giá trị chọn chưa có căn cứ đo (đo ở CP7)

Các giá trị tham số cấu hình dưới đây mang nhãn cơ sở `CONSERVATIVE_DEFAULT` trong tệp cấu hình sản xuất `tools/launcher/prod/profile.json` và chưa có số đo thực nghiệm kiểm chứng trên phần cứng máy trạm này. Trong cột mốc CP7, các kết quả đo đạc thực tế sẽ được cập nhật thông qua revision cấu hình mới mà không làm thay đổi mã nguồn.

| Tham số | Giá trị | Đo ở |
| :--- | :--- | :--- |
| `collection.fetch_policy.feed` | max_body 5MB, timeout 20s, max_redirects 5 | CP7-ADAPT-07 |
| `collection.fetch_policy.article` | max_body 5MB, timeout 20s, text/html, xhtml | CP7-ADAPT-07 |
| `collection.fetch_policy.image` | max_body 15MB, timeout 30s, jpeg/png/webp | CP7-ADAPT-07 |
| `collection.retry_fetch` | 3 lần thử, backoff 2-60s, respect_retry_after | CP7-ADAPT-07 |
| `collection.concurrency` | global_fetches 4, per_host_fetches 1 | CP7-ADAPT-07 |
| `collection.extraction_min_text_chars` | 600 ký tự | CP7-ADAPT-07 |
| `ai.route_endpoint` | http://127.0.0.1:20128/v1 | CP7-ADAPT-02 |
| `ai.request_timeout_seconds` | 120 giây | CP7-ADAPT-02 |
| `ai.retry` | 3 lần thử, backoff 2-60s | CP7-ADAPT-02 |
| `ai.reservation_ttl_seconds` | 300 giây | CP7-ADAPT-02 |
| `ai.quota_wait_poll_seconds` | 300 giây | CP7-ADAPT-02 |
| `credential.max_ttl_seconds` | 3300 giây (55 phút) | CP7-ADAPT-01 |
| `voice.speech_rate_wpm` | 150 từ/phút | CP7-ADAPT-03 |
| `voice.tts_timeout_seconds` | 180 giây | CP7-ADAPT-03 |
| `voice.stage_retry` | 3 lần thử, backoff 5-120s | CP7-ADAPT-03 |
| `aligner.word_timing_tolerance_ms` | 200 ms | CP7-ADAPT-04 |
| `aligner.max_unmatched_word_ratio` | 0.05 (5%) | CP7-ADAPT-04 |
| `audio.loudness` | -16 LUFS, true peak -1.5 dBTP, lra 11 | CP7-ADAPT-06 |
| `audio.bed_gain_db` | -20 dB | CP7-ADAPT-06 |
| `image_safety.thresholds` | 0.5 reject, 0.5 blur, range [0.3, 0.5) reject | CP7-ADAPT-05 |
| `image_safety.boxblur` | luma_radius 40, luma_power 3 | CP7-ADAPT-05 |
| `image_safety.vision` | timeout 120s, max_long_edge 1024px | CP7-ADAPT-05 |
| `render.nvenc` | h264_nvenc, p5, vbr cq 23, maxrate 12M | CP7-ADAPT-06 |
| `render.fallback` | libx264, medium, crf 21, yuv420p | CP7-ADAPT-06 |
| `render.timeout_seconds` | 900 giây (15 phút) | CP7-ADAPT-06 |
| `render.presets` | font Arial 72pt, viền 4px, 5 biến thể màu | CP7-ADAPT-06 |
| `qc.karaoke_tolerance_ms` | 200 ms | CP7-ADAPT-06 |
| `qc.hook_similarity_min` | 0.85 | CP7-ADAPT-06 |
| `qc.hook_audio_min_dbfs` | -40 dBFS | CP7-ADAPT-06 |
| `qc.visual_continuity_min` | 0.6 | CP7-ADAPT-06 |
| `qc.max_file_bytes` | 157286400 byte (150 MB) | CP7-ADAPT-06 |
| `gpu.slots` | 2 khe desktop GPU (LOCK-DESKTOP-GPU) | CP7-ADAPT-06 |
| `drive.chunk_bytes` | 8388608 byte (8 MB) | CP7-ADAPT-01 |
| `drive.chunk_timeout_seconds` | 120 giây | CP7-ADAPT-01 |
| `drive.retry` | 5 lần thử, backoff 2-60s | CP7-ADAPT-01 |
| `drive.session_ttl_seconds` | 518400 giây (6 ngày) | CP7-ADAPT-01 |
| `drive.quota_reserve_ratio` | 0.2 (20% dung lượng trống) | CP7-ADAPT-01 |
| `working_set.max_bytes` | 21474836480 byte (20 GB) | CP7-ADAPT-01 |
| `working_set.disk_reserve_bytes` | 32212254720 byte (30 GB) | CP7-ADAPT-01 |
| `retention.log_days` | 30 ngày | CP7-ADAPT-09 |
| `retention.audit_days` | 365 ngày | CP7-ADAPT-09 |
| `workflow.start_to_close_seconds` | control 60s, io 900s, ai 240s, cpu 600s, render 1200s | CP7-ADAPT-09 |
| `workflow.heartbeat_seconds` | 30 giây | CP7-ADAPT-09 |
| `workflow.retry` | init 5s, coeff 2.0, max 120s, 3 lần thử | CP7-ADAPT-09 |
| `resume.ready_within_seconds` | 300 giây (5 phút) | CP7-ADAPT-09 |
| `OAUTH_CONSENT_TIMEOUT_SECONDS` | 300 giây | CP7-ADAPT-08 |
| `STOP_GRACE_SECONDS` | 60 giây | CP7-ADAPT-08 |
| `PG_WAIT_SECONDS` | 120 giây | CP7-ADAPT-08 |
| `render.ass_style` | 13 khoá kiểu ASS (viền, bóng, căn dưới giữa) | R4 (user duyệt preset) |
| `render.layout` | lề 60, tối đa 4 từ và 28 ký tự mỗi dòng, dòng công bố cỡ 40 | R4 (user duyệt preset) |
| `render.sections` | UNSPECIFIED_V1 cho 4 phần CT-RND-001, render v1 không đọc | R4 (user duyệt preset) |
| `render.output_stream` | h264, yuv420p | R4 (user duyệt preset) |
| `qc.quality_thresholds` | SUBTITLE_BURNED_IN ít nhất 2 khung có chữ, VOICE_AUDIBLE từ -40 dB | R4 (user duyệt preset) |
