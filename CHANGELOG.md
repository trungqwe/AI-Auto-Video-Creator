# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi trong tệp này theo cấu trúc [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Dự án chưa phát hành phiên bản sản phẩm.

## [Unreleased]

### Added

- Hoàn tất khắc phục toàn diện 5 vấn đề từ đợt tái kiểm toán độc lập trên GitHub HEAD commit `fdd04b5` (R4-01..R4-05) và lập Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r4.md`:
  - R4-01 (ADR-0009 Cloud Token Broker HTTP Process Boundary): Triển khai `CloudTokenBrokerServer` daemon HTTP TCP độc lập (`src/m1proof/broker_service.py`), vault lưu refresh token bên ngoài workspace tại `~/.cloud_token_broker/vault.json`; desktop client giao tiếp qua HTTP IPC (`POST /api/token`), credentials desktop chỉ chứa access token ngắn hạn (`refresh_token=None`); kiểm toán quét ổ đĩa desktop cam kết 0 token plaintext; thực nghiệm live probe E3 thành công trên Google Drive thật (pre-generated ID `1QR8W1...NYct`, resumable upload 64 bytes, tải về đối soát SHA-256 `a1489a57bff218ba...` khớp 100%, dọn dẹp file test); xuất tệp bằng chứng `docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json` với `status: PASS_E3_LIVE` (thêm test TST-M1-P3-012 và TST-M1-P3-LIVE).
  - R4-02 (Đồng bộ Evidence & Trace Số lượng Test Run): Cập nhật đồng bộ các tệp `commands.jsonl`, `status.md`, `hashes.sha256` của P2, P3, P5, P6; trace chính xác 100% kết quả test run hiện hành: **87/87 passed, 0 skipped** (coverage 87%).
  - R4-03 (Minh bạch Test-First & Bằng chứng RED Thực tế): Ghi nhận công khai độ lệch lịch sử `RED_EVIDENCE_MISSING_FOR_R3_REMEDIATION` trong `red-observations.md` của P3, P5, P6; chứng kiến RED thật trước implementation cho 3 bài test R4 mới (`test_tst_m1_p3_012_broker_http_process_boundary`, `test_tst_m1_p5_008_dynamic_matrix_observation`, `test_tst_m1_p6_008_capability_evidence_fail_closed`) và lưu log thô tại `docs/milestones/m1-proof/evidence/m1-p6/red-r4-stdout.txt`.
  - R4-04 (P6 Fail-Closed theo Capability Evidence): Bổ sung `m1-p6` vào mandatory packages; kiểm tra bắt buộc 3 tệp capability evidence (`temporal_server_evidence.json`, `drive_e3_evidence.json`, `compatibility_matrix.json`); hạ trạng thái nếu thiếu; đánh giá động `evidence_classification` (gán `E3` cho `m1-p3` khi probe live pass).
  - R4-05 (Dynamic Compatibility Matrix): Cập nhật `generate_compatibility_matrix()` đo đạc động runtime thực tế (CPython, uv, PostgreSQL, Temporal Server binary, Temporal SDK, FFmpeg/ffprobe), ghi nhận timestamp UTC thực thi và xuất `compatibility_matrix.json`.
  - Toàn bộ test suite M1 đạt **87 passed, 0 skipped** (P0: 10, P1: 32, P2: 10, P3: 13, P4: 6, P5: 8, P6: 8).
- Khắc phục toàn bộ các phát hiện từ kiểm toán độc lập R3 và lập Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r3.md`:
  - P3 (OAuth Boundary ADR-0009): Triển khai `CloudTokenBroker` và `DesktopOAuthClient` trong `src/m1proof/oauth_broker.py`, desktop client chỉ nhận access token ngắn hạn trong RAM (`refresh_token=None`), xóa vĩnh viễn tệp `token_e3_test.json`, kiểm toán đĩa cam kết 0 refresh token plaintext, phân loại lỗi HTTP 403 `insufficientPermissions` và redact bí mật (thêm 4 tests TST-M1-P3-008..011).
  - P2 (Exact Temporal Server 1.31.2): Tải và tích hợp official binary `tools/temporal/temporal-server.exe` v1.31.2 (SHA-256: `5575b369...`), khởi chạy local dev server với SQLite in-memory, kết nối gRPC port 7233, tự động đăng ký namespace, thực thi roundtrip Workflow + Activity và idempotent retry trên máy chủ thật (thêm 3 tests TST-M1-P2-008..010).
  - P5 (Strict Compatibility Matrix & Media Validation): Nâng cấp kiểm tra tương thích lên so khớp nghiêm ngặt 100% phiên bản đã khóa (Python 3.13.15, uv 0.12.13, PG 18.6, psycopg 3.3.5, Temporal Server 1.31.2, Temporal SDK 1.32.0); tạo fixture âm thanh chuẩn RIFF WAV và xác thực đa phương tiện qua `ffprobe` (container wav, codec pcm_s16le, duration > 0); xuất `compatibility_matrix.json`.
  - P6 (Dynamic Fail-Closed Evidence Manifest): Bỏ hard-code kết quả PASS; triển khai parser đọc trạng thái động từ `status.md`; kiểm tra danh sách tệp bằng chứng bắt buộc; phân loại bằng chứng E1..E3; kiểm thử tiêu cực (negative tests) phát hiện tệp thiếu, tampering, canary secret fail-closed (thêm 2 tests TST-M1-P6-006..007).
  - Test suite M1 nâng lên 83 passed, 1 skipped (coverage >91%).
- Hoàn thành M1-P6 Evidence Synthesis & Audit: xây dựng manifest tổng hợp 75 artifacts với kiểm tra băm SHA-256 tự động, thực thi gate boundary engine ngăn chặn công bố PASS non-m1 scope, quét bảo mật fail-closed (0 credential/token rò rỉ), hoàn thiện 5 bài test-first (TST-M1-P6-001..005) và lập Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r2.md`.
- Hoàn thành M1-P5 Compatibility Smoke: kiểm chứng tương thích thực tế tập phiên bản M1-R1 với 6 bài test-first (CPython 3.13.15, uv 0.12.13, khóa uv.lock frozen, PostgreSQL 18.6 rollback và lưu trữ UTF-8 tiếng Việt, Temporal SDK 1.32.0 handshake/replay, ranh giới client Google không leak secret khi thiếu credential, và binary FFmpeg thực tế C:\ffmpeg\bin\ffmpeg.exe probe an toàn với argument array).
- Hoàn thành M1-P4 Local Journal & Recovery Proof: kiểm chứng SQLite local journal và atomic file writer trên Windows với 6 bài test-first (crash sau artifact complete trước gửi receipt resend operation, crash giữa chừng reject partial byte, lost ACK sau cloud commit reconcile receipt không lặp side effect, stale recovery epoch quarantine, cache eviction phân biệt với unsent journal active, và phát hiện missing/corrupt hash).
- Hoàn thành M1-P3 Google Drive & OAuth G04 Proof: kiểm chứng Google Drive API v3 và OAuth 2.0 Installed App Flow với 8 bài test-first (pre-generated ID idempotency, resumable upload lost-ACK recovery, timeout classification & reconciliation routing, byte integrity & SHA-256 verification, resumable session reconciliation, OAuth lifecycle & ADR-0009 desktop boundaries, rate limit HTTP 429 bounded backoff và secret scanning trong logs/receipts).
- Thực hiện kiểm chứng thực tế Live E3 Probe trên Google Drive thật: hoàn tất OAuth authorization flow qua localhost, cấp pre-generated ID từ Drive API, resumable upload payload 64 bytes, tải về đối soát SHA-256 khớp 100% và dọn dẹp xóa file test an toàn.
- Hoàn thành M1-P2 Temporal G01 Proof: kiểm chứng Temporal Server 1.31.2 và Python SDK 1.32.0 với 7 bài test-first (worker offline/resume, idempotency lost-ACK, stale generation fencing, child failure isolation, replay versioning/patching, unknown outcome reconciliation và payload/history secret boundaries).
- M1-P1 contract proof cho idempotency, optimistic revision, outbox/consumer dedupe, fencing theo generation/recovery epoch, operation receipt/reconciliation và lọc dữ liệu nhạy cảm.
- Completion Unit of Work proof ghi nguyên tử completion ledger, batch/capacity, variant registry/reservation, `MediaUsage` qua owner port, outbox và cleanup eligibility; có fault injection tại từng ranh giới và lost-ACK recovery.
- M1-P0 environment capture/validation, frozen dependency lock, PostgreSQL 18.6 preflight và test harness với evidence RED/GREEN.
- Baseline tài liệu sản phẩm, dữ liệu, chất lượng, kiến trúc, ADR, contracts, test strategy và roadmap.
- Technical spec và implementation plan cho Phân hệ A, vẫn chưa được phép triển khai.
- M1-R1 version lock và kế hoạch Evidence Prototype từ M1-P0 đến M1-P6.
- Checklist trạng thái, audit nhiều vòng và quy tắc phân biệt proof M1 với gate toàn phần.
- Quy trình duy trì `README`, `CHANGELOG`, `HANDOFF` và sao lưu GitHub sau mỗi phiên sửa đổi hoặc checkpoint quan trọng.

### Changed

- Milestone M1 hoàn tất 100% (P0..P6 PASS, 74/74 automated tests, coverage 88%), chuyển trạng thái sang `READY_FOR_USER_CHECKPOINT`.
- M1-P6 chuyển sang `PASS_M1_SCOPE`.
- Cổng G07 chuyển sang `SMOKE_COMPATIBILITY_PASS_M1_SCOPE`.
- M1-P5 chuyển sang `PASS_M1_SCOPE`.
- M1-P4 chuyển sang `PASS_M1_SCOPE`.
- M1-P3 chuyển sang `PASS_M1_SCOPE`; Cổng G04 chuyển sang `PARTIALLY_PROVEN`.
- ROADMAP-OPEN-003 chuyển sang `CLOSED_FOR_M1_P3`.
- M1-P2 chuyển sang `PASS_M1_SCOPE`; G01 chuyển sang `PARTIALLY_PROVEN`.
- Khắc phục toàn bộ 3 BLOCKER và 5 MAJOR của audit M1 R1: aggregate race, recovery epoch, secret boundaries, live environment probe, scoped operation/activity receipts, restart evidence và completion admission.
- P0/P1 trở lại `PASS` sau remediation review; P2 chuyển `READY`, nhưng M1/G01/G04 chưa PASS.
- M1 tiếp tục `IN PROGRESS`; M1-P0 và M1-P1 đạt PASS, M1-P2 Temporal G01 là work package tiếp theo. M1 và G01/G04 chưa PASS.
- Ghi rõ Windows M1-R1 dùng backend `psycopg-binary==3.3.5` qua extra `psycopg[binary]`, cùng API/version psycopg đã khóa.
- M0 chuyển sang `APPROVED`; PCC-026 đóng và quyền code được giới hạn ở M1.
- ROADMAP-OPEN-002 chuyển `CLOSED_FOR_M1_R1`; ROADMAP-OPEN-003 chỉ chặn M1-P3.
- M1 được làm chặt về evidence order, PostgreSQL preflight, completion Unit of Work, gate scope và failure taxonomy.

### Security

- Thiết lập chính sách không commit credential, token, secret, log chưa redacted hoặc dữ liệu runtime nhạy cảm.

## Trạng thái sau khắc phục audit M1 R1

Remediation R1 có 42 test acceptance qua, migration tiến/lùi và evidence/hash mới. P0/P1 `PASS`, P2 `READY`; G01/G04 vẫn `NOT TESTED` và M2/M3/Module A vẫn `NOT AUTHORIZED`.
