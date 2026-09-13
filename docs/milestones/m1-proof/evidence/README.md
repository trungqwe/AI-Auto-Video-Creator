# M1 evidence

Thư mục này chỉ nhận bằng chứng được tạo từ các lần chạy M1 thực tế. M1-P0 đã `PASS`; M1-P1 là package tiếp theo. G01/G04 vẫn `NOT TESTED` và không có gate toàn phần nào PASS.

## Quy tắc

- Mỗi work package ghi vào thư mục `m1-p0` đến `m1-p6` khi bắt đầu thực thi.
- Mỗi run có ID/thời gian UTC riêng; không ghi đè RED, failure hoặc evidence revision cũ.
- Không lưu secret, access token, refresh token, authorization code hoặc raw credential.
- Log/request/response phải redacted; account/file ID chỉ giữ khi cần và theo dạng an toàn được plan cho phép.
- Mọi artifact được trích dẫn phải có SHA-256 và tham chiếu đúng lớp version/environment record.
- Mock/fake evidence phải ghi environment class, không được dùng để đóng external gate G04.
- `manifest.json` chỉ được tạo/tổng hợp ở M1-P6 từ artifact thực tế; file tồn tại không tự đồng nghĩa PASS.

## Ba lớp bản ghi không được đánh đồng

| Đường dẫn | Thời điểm tạo | Vai trò | Có thể tạo PASS? |
|---|---|---|---|
| `m1-p0/bootstrap.json` | Trong bootstrap P0, trước test Python đầu tiên | Bản ghi đầu vào bất biến: Python/uv, platform, package metadata, `uv.lock` hash và PostgreSQL preflight | Không |
| `m1-p0/environment.json` | Sau khi đã chứng kiến RED của P0 | Output do implementation capture/validator tạo để đưa P0 về GREEN | Chỉ là một phần evidence P0 |
| `manifest.json` | Chỉ tại P6 | Chỉ mục tổng hợp artifact/hash/revision/status toàn M1 | Không tự tạo PASS |

RED của P0 phải đến từ `environment.json` chưa tồn tại hoặc sai so với `bootstrap.json`. Thiếu runtime, import, PostgreSQL service hoặc binary là setup failure, không phải RED nghiệp vụ hợp lệ.

Hợp đồng chi tiết nằm tại [M1 implementation plan](../implementation-plan.md). Version có thẩm quyền nằm tại [M1-R1 version lock](../version-lock.md).
