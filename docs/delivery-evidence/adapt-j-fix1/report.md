# Báo cáo ADAPT-J-FIX1

## Thông tin gói công việc
- Mã gói: ADAPT-J-FIX1
- Milestone: M7
- Nhóm lỗi: R13 (hạn access token Drive tính lệch miền thời gian giữa đồng hồ tiêm và giờ thật của google-auth)

## Tệp đã sửa
1. `src/controlplane/infrastructure/security/oauth_drive_token.py`:
   - Trong phương thức `DriveAccessTokenBroker._refresh`, tính `remaining = expiry_utc - datetime.now(timezone.utc)` đo bằng giờ thật ngay sau refresh, sau đó neo vào `now` của đồng hồ tiêm: `expires_at = min(expires_at, now + remaining)`.
2. `tests/integration/adapt/j/test_adapt_j_oauth.py`:
   - Thêm hàm test mới `test_server_short_expiry_is_anchored_to_injected_clock_not_real_time` kiểm tra lệch đồng hồ 10 phút về trước mà không monkeypatch hay thay thế lớp production.
3. `docs/delivery-evidence/adapt-j-fix1/report.md`:
   - Tài liệu báo cáo bằng chứng nghiệm thu tiếng Việt đầy đủ dấu theo quy chuẩn.

## Nguyên nhân và hành vi production
- Nguyên nhân: Trước bản sửa, `_refresh` lấy `expires_at = min(now + max_ttl, creds.expiry)`. Biến `now` là thời gian từ đồng hồ tiêm (`clock.now()`), trong khi `creds.expiry` do `google-auth` tính bằng giờ thật (`datetime.utcnow() + expires_in`). Khi đồng hồ tiêm lệch so với giờ thật (hoặc khi refresh trễ hơn 1 giây trong test đứng yên đồng hồ), việc so sánh hai miền thời gian khác nhau dẫn tới tính sai hạn token hoặc token cũ bị trả lại từ cache.
- Hành vi production: Không đổi. Trong môi trường production, đồng hồ tiêm là giờ thật (`datetime.now(timezone.utc)` tại `controlplane/infrastructure/production_ports/assembly.py:59`), do đó `now` và giờ thật đồng nhất. Token không bao giờ bị giữ quá hạn thật và mọi kiểm tra bảo mật, trạng thái tài khoản hay cache theo version đều được giữ nguyên vẹn.

## Lệnh kiểm đã chạy

### 1. Bước 2 - Chứng kiến RED trước khi sửa mã production
- Lệnh thực thi:
```bash
python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider -k test_server_short_expiry_is_anchored_to_injected_clock_not_real_time
```
- Mã thoát: `1`
- Dòng tổng kết nguyên văn pytest:
```text
1 failed, 22 deselected in 1.19s
```
- Chi tiết lỗi xác nhận đúng oracle: `AssertionError: assert 'CANARY-ADAPT-J-ACCESS-1' != 'CANARY-ADAPT-J-ACCESS-1'` do token cache cũ được trả về khi đồng hồ tiêm lệch 10 phút về trước.

### 2. Bước 4 - Chạy kiểm thử 3 tệp sau khi sửa mã production
- Lệnh thực thi:
```bash
python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py tests/integration/prod_ports/test_pp_3_drive_token.py tests/integration/prod_ports/test_pp_8_assembly.py -q -p no:cacheprovider
```
- Mã thoát: `0`
- Dòng tổng kết nguyên văn pytest:
```text
63 passed in 37.27s
```

### 3. Bước 6 - Kiểm tra định dạng git diff
- Lệnh thực thi:
```bash
git diff --check
```
- Mã thoát: `0`
- Kết quả: Không có lỗi khoảng trắng thừa hay lỗi kết thúc dòng.

### 4. Bước 7 - Probe kiểm tra báo cáo bằng chứng
- Lệnh thực thi:
```bash
python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-j-fix1/report.md').read_text(encoding='utf-8'); assert 'ADAPT-J-FIX1' in t and 'R13' in t, 'report'"
```
- Mã thoát: `0`
- Kết quả: Đạt, tệp tồn tại và chứa đầy đủ chuỗi nhận diện.

## Phản ví dụ đã loại trừ
- Không nới khoảng tăng clock trong test mà không sửa broker.
- Không bỏ `creds.expiry`.
- Không dùng giờ thật cho kiểm cache (giữ nguyên đồng hồ tiêm tại dòng kiểm cache).
- Không đổi `max_ttl`, chữ ký API, kiểm trạng thái tài khoản hay cache theo version.
- Test mới hỏng tất định với mã cũ (đã chứng minh bằng chứng RED tại bước 2).
