# Báo cáo bằng chứng A-04

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `14a2b92677ebf47724fab8a6229b340f45a1a3a7`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-04 trong docs/implementation/a/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `69 failed, 5 passed in 0.39s`
- Chi tiết một số test FAILED tiêu biểu nguyên văn:
  - `FAILED tests/unit/collection/test_a04_locator_ssrf.py::test_canonicalize_locator_normalizes[HTTPS://Example.COM:443/a/b?x=1#frag-https://example.com/a/b?x=1]`: `AssertionError: assert 'HTTPS://Exam.../a/b?x=1#frag' == 'https://example.com/a/b?x=1'`
  - `FAILED tests/unit/collection/test_a04_locator_ssrf.py::test_canonicalize_locator_rejects_non_http_schemes[file:///etc/passwd]`: `Failed: DID NOT RAISE UnsupportedSchemeError`
  - `FAILED tests/unit/collection/test_a04_locator_ssrf.py::test_canonicalize_locator_rejects_malformed[-INVALID_LOCATOR]`: `Failed: DID NOT RAISE LocatorError`
  - `FAILED tests/unit/collection/test_a04_locator_ssrf.py::test_validate_destination_blocks_unsafe_literals[127.0.0.1-LOOPBACK_ADDRESS]`: `Failed: DID NOT RAISE UnsafeDestinationError`
  - `FAILED tests/unit/collection/test_a04_locator_ssrf.py::test_validate_locator_uses_injected_resolver_for_names`: `AssertionError: assert ValidatedLocator('HTTPS://Example.com:443/feed#top', '', ()) == ValidatedLocator('https://example.com/feed', 'example.com', (IPv4Address('8.8.8.8'),))`
- Xác nhận: Hoàn toàn không có ModuleNotFoundError, ImportError hay lỗi collection nào (2 test kiểm tra guard mạng và ranh giới import đã passed: `test_network_guard_blocks_real_dns_and_connect` và `test_locator_module_imports_no_network_modules`).

## Thay đổi

- `src/source_ingestion/domain/locator.py`:
  - API thuần domain (chỉ dùng Python stdlib: ipaddress, re, urllib.parse, dataclasses, collections.abc; không import socket hay I/O mạng).
  - Lớp ngoại lệ phân cấp theo mã lý do: `LocatorError(ValueError)` với thuộc tính `.reason`, `UnsupportedSchemeError`, `UnsafeDestinationError`.
  - Data class bất biến: `ValidatedLocator(locator: str, host: str, addresses: tuple[IPAddress, ...])`.
  - Các hàm chính:
    - `canonicalize_locator(raw: str) -> str`: chuẩn hoá locator dùng urllib.parse, chỉ chấp nhận scheme http/https, host chữ thường qua IDNA, loại bỏ fragment, cổng mặc định (:80, :443), chuẩn hoá path rỗng thành `/`, từ chối thông tin đăng nhập trong locator (`CREDENTIALS_IN_LOCATOR`) mà không echo token bí mật.
    - `validate_destination(host: str, resolved_ips: Iterable[str | IPAddress]) -> tuple[IPAddress, ...]`: chặn loopback, private, link-local, multicast, reserved, unspecified, 169.254.169.254 (metadata), IPv4-mapped IPv6, các dạng IP thay thế (legacy decimal, hex, octal, rút gọn), host localhost/`*.localhost`, địa chỉ non-global, fail-closed khi không có địa chỉ giải được hoặc địa chỉ không hợp lệ.
    - `validate_locator(raw: str, resolver: Resolver) -> ValidatedLocator`: tích hợp canonicalize_locator và validate_destination, chỉ phân giải tên miền qua resolver được tiêm vào, không gọi resolver cho IP literal hay localhost.
- `tests/unit/collection/test_a04_locator_ssrf.py`:
  - Docstring đầu tệp ghi coveredIds: `A-RULE-013, CT-SRC-001, CT-SEC-003`.
  - Fixture autouse `_no_network` thay thế `socket.getaddrinfo`, `socket.create_connection`, `socket.gethostbyname`, `socket.gethostbyname_ex` bằng hàm ném `AssertionError` để ngăn chặn hoàn toàn gọi DNS hoặc mạng thật.
  - Lớp giả lập `FakeResolver` để tiêm bảng định tuyến DNS kiểm thử.
  - 6 nhóm test:
    - `test_network_guard_blocks_real_dns_and_connect` và `test_locator_module_imports_no_network_modules`: bảo vệ không gọi mạng thật và không import module mạng.
    - `test_canonicalize_locator_*`: bao phủ chuẩn hoá IDNA, cổng, IPv6 literal, từ chối scheme lạ, định dạng sai, loại dữ liệu sai, từ chối credentials mà không echo bí mật.
    - `test_validate_destination_*`: bao phủ chặn IP nguy hiểm, chấp nhận IP công cộng, chặn phân giải không an toàn/localhost/rebinding.
    - `test_validate_locator_*`: kiểm tra phối hợp với resolver tiêm vào, chặn IP literal không gọi DNS, chặn scheme file:// trước khi resolve, chặn DNS rebinding, fail-closed khi resolver lỗi (`RESOLUTION_FAILED`), từ chối localhost không gọi resolver.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider` | 0 | 74 passed in 0.08s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.03s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Locator có userinfo bị từ chối với mã `CREDENTIALS_IN_LOCATOR`, thông điệp lỗi chỉ chứa mã lý do mà không echo giá trị locator hay credentials (A-RULE-014).
2. Host số dạng legacy (thập phân như 2130706433, hex như 0x7f000001, octal như 0177.0.0.1, dạng rút gọn như 127.1) được chuẩn hoá về dạng chuẩn dotted-quad; host kết thúc bằng số nhưng không hợp lệ chuyển thành lỗi `AMBIGUOUS_NUMERIC_HOST` theo quy tắc host IPv4 của WHATWG URL.
3. Chặn mọi địa chỉ IPv4-mapped IPv6 (`::ffff:x.x.x.x`) kể cả ánh xạ IP công cộng với mã `IPV4_MAPPED_ADDRESS`; các địa chỉ 6to4 (`2002::/16`) được giải nén để kiểm tra địa chỉ IPv4 nhúng.
4. Chỉ cần một địa chỉ IP sau phân giải không an toàn là lập tức chặn cả host; nếu kết quả phân giải rỗng hoặc resolver ném lỗi OSError thì fail-closed với mã tương ứng (`UNRESOLVED_HOST`, `RESOLUTION_FAILED`).
5. Tên miền `localhost` hoặc kết thúc bằng `.localhost` bị chặn trực tiếp với mã `LOCALHOST_NAME` trước khi chuyển sang resolver phân giải.
6. Địa chỉ IP không thuộc phạm vi global (ví dụ mạng CGNAT 100.64.0.0/10) bị chặn với mã `NON_GLOBAL_ADDRESS`.
7. Chuẩn hoá locator tự động loại bỏ một dấu chấm cuối hostname (FQDN trailing dot), gán đường dẫn mặc định là `/` nếu rỗng, giữ nguyên query parameters, cổng 0 bị từ chối với mã `INVALID_PORT`, IPv6 có zone ID (`%`) bị từ chối với mã `INVALID_HOST`.
8. Module `locator.py` hoàn toàn không import socket hay thực hiện I/O mạng; resolver được tiêm từ bên ngoài; module fetcher ở slice A-12 có trách nhiệm gọi lại `validate_destination` ở mỗi bước redirect HTTP và pin kết nối socket vào địa chỉ an toàn đã được thẩm định.
9. Không dùng mã test `TST-SEC-SSRF-*` vì nằm ngoài test catalog hiện hành (errata m3-a #6); mô tả hành vi kiểm thử theo các mã chuẩn `CT-SRC-001` và `CT-SEC-003` được bảo lưu tới `CONV-A-08`.
10. Không thêm bất kỳ thư viện ngoài nào vào dự án, chỉ sử dụng Python stdlib có sẵn (ipaddress, re, urllib.parse, dataclasses, collections.abc).

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full test suite, tests/m1, tests/m2.
- Không thay đổi `pyproject.toml`, `uv.lock`.
- Không gọi DNS hoặc kết nối mạng thật; SSRF ở mức fetch/redirect thuộc phạm vi thực thi của A-12.
