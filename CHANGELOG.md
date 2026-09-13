# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi trong tệp này theo cấu trúc [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Dự án chưa phát hành phiên bản sản phẩm.

## [Unreleased]

### Added

- M1-P1 contract proof cho idempotency, optimistic revision, outbox/consumer dedupe, fencing theo generation/recovery epoch, operation receipt/reconciliation và lọc dữ liệu nhạy cảm.
- Completion Unit of Work proof ghi nguyên tử completion ledger, batch/capacity, variant registry/reservation, `MediaUsage` qua owner port, outbox và cleanup eligibility; có fault injection tại từng ranh giới và lost-ACK recovery.
- M1-P0 environment capture/validation, frozen dependency lock, PostgreSQL 18.6 preflight và test harness với evidence RED/GREEN.
- Baseline tài liệu sản phẩm, dữ liệu, chất lượng, kiến trúc, ADR, contracts, test strategy và roadmap.
- Technical spec và implementation plan cho Phân hệ A, vẫn chưa được phép triển khai.
- M1-R1 version lock và kế hoạch Evidence Prototype từ M1-P0 đến M1-P6.
- Checklist trạng thái, audit nhiều vòng và quy tắc phân biệt proof M1 với gate toàn phần.
- Quy trình duy trì `README`, `CHANGELOG`, `HANDOFF` và sao lưu GitHub sau mỗi phiên sửa đổi hoặc checkpoint quan trọng.

### Changed

- M1 tiếp tục `IN PROGRESS`; M1-P0 và M1-P1 đạt PASS, M1-P2 Temporal G01 là work package tiếp theo. M1 và G01/G04 chưa PASS.
- Ghi rõ Windows M1-R1 dùng backend `psycopg-binary==3.3.5` qua extra `psycopg[binary]`, cùng API/version psycopg đã khóa.
- M0 chuyển sang `APPROVED`; PCC-026 đóng và quyền code được giới hạn ở M1.
- ROADMAP-OPEN-002 chuyển `CLOSED_FOR_M1_R1`; ROADMAP-OPEN-003 chỉ chặn M1-P3.
- M1 được làm chặt về evidence order, PostgreSQL preflight, completion Unit of Work, gate scope và failure taxonomy.

### Security

- Thiết lập chính sách không commit credential, token, secret, log chưa redacted hoặc dữ liệu runtime nhạy cảm.

## Trạng thái sau audit M1 R1

Audit ngày 13-09-2026 tại `docs/milestones/m1-proof/audit-r1.md` mở 3 BLOCKER và 5 MAJOR. P0/P1 hiện `CORRECTION_REQUIRED`; P2 chưa được bắt đầu vì dependency chưa đạt. Các kết luận PASS trước audit trong tài liệu này chỉ là lịch sử. Giữ nguyên evidence cũ; G01/G04 NOT TESTED và M2/M3/Module A NOT AUTHORIZED. Chưa sửa implementation trong lượt audit.
