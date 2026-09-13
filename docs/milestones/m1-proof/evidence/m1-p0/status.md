# M1-P0 Status

**Trạng thái:** `PASS`  
**Môi trường:** Windows 10 x64, CPython 3.13.15, uv 0.12.13  
**Database preflight:** PostgreSQL 18.6 + psycopg 3.3.5  
**Phạm vi kết luận:** chỉ bootstrap môi trường và test harness M1-P0

## Kết quả

- `uv.lock` resolve 45 package và frozen sync cài 44 package môi trường; danh sách thực tế ở `dependencies.json`.
- PostgreSQL image `postgres:18.6` được khóa bằng digest trong `bootstrap.json`, chỉ publish loopback tại cổng proof.
- PostgreSQL preflight đạt: kết nối, `SELECT 1`, rollback và round-trip Unicode.
- Ba chu kỳ RED được giữ trong `red*-stdout.txt`/`red*-test-results.xml`; không RED nào do import hoặc thiếu setup.
- Test cuối: 7 passed; coverage kết hợp CLI capture và test suite đạt 91%.
- Bootstrap hash, environment source hash, version mismatch và sensitive-key rejection đều được kiểm tra.
- Không có secret/canary trong evidence sau quét.

## Setup observation đã xử lý

- Docker daemon chưa chạy ở lần pull đầu; đã khởi động và pull đúng image/digest.
- Probe PostgreSQL inline đầu tiên lỗi quoting/encoding PowerShell; đã thay bằng probe nguồn ASCII với Unicode escape và so sánh giá trị, kết quả `utf8_equal=True`.
- uv không hardlink được cache qua filesystem và tự dùng copy; không làm đổi package/version hoặc lock hash.

Các observation trên là lỗi setup đã khắc phục, không phải RED nghiệp vụ và không kích hoạt STOP.

## Giới hạn

- Temporal Server và FFmpeg 9.0.1 chưa được dựng; thuộc P2/P5.
- G01 Temporal và G04 Drive/OAuth vẫn `NOT TESTED`.
- Kết quả này không cho phép M2, M3 hoặc Module A.

## Điểm tiếp tục

M1-P1: contract/idempotency/outbox/receipt/completion Unit of Work proof trên PostgreSQL đã vượt preflight.
