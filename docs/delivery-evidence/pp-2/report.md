# Báo cáo bằng chứng chuyển giao: PP-2

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `tools/launcher/prod/ports.json`: Tệp cấu hình JSON UTF-8 không BOM định nghĩa các cổng sản xuất (`revision`: 1, `router`: `account_ref` `router-primary`, `secret_ref` `router-primary-api-key`; `gpu_lease`: `grace_seconds` 60; `drive`: `placement_state_file` `drive-placement.json`, `artifact_namespaces` `original`, `reusable`, `output`).
- `src/controlplane/infrastructure/production_ports/ports_config.py`: Trình nạp cấu hình chặt chẽ (`PortsConfig`, `RouterPortsConfig`, `GpuLeasePortsConfig`, `DrivePortsConfig` dạng dataclass frozen) qua hàm `load_ports_config(path: Path)`. Kiểm tra nghiêm ngặt cấu trúc JSON, từ chối thiếu khóa, sai kiểu, khóa lạ, tên tệp không hợp lệ, danh sách rỗng hoặc trùng lặp bằng `ValueError`; tuyệt đối không dùng giá trị mặc định ngầm.
- `src/controlplane/infrastructure/production_ports/credentials.py`: Triển khai `ProviderCredentialError` và `RouterKeyCredentials(store, router_account_ref, router_secret_ref)` thực thi cổng `CredentialSourcePort` cho 9Router qua kho bí mật DPAPI (`CT-SEC-001`, `INV-012`). Phương thức `acquire(credential_method, account_ref)` là một `contextmanager` kiểm tra chặt chẽ `credential_method == CREDENTIAL_METHOD` và `account_ref == router_account_ref` (sai ném `ValueError`), đọc khóa qua `DpapiRefreshTokenReader(store).read(secret_ref)`; khi alias bị thiếu, bị thu hồi hoặc không thể giải mã thì ném `ProviderCredentialError` tuyệt đối không chứa giá trị khóa; phương thức `__repr__` che giấu giá trị khóa bằng `[REDACTED]`.
- `src/controlplane/infrastructure/production_ports/router_key_entry.py`: Hàm `store_router_key(store, secret_ref, read_value)` loại bỏ khoảng trắng đầu cuối, từ chối chuỗi rỗng hoặc không phải chuỗi, lưu vào kho DPAPI qua `store.put` và trả về số phiên bản mới. Hàm `run(vault_dir, ports_config_path, read_value, out)` nạp cấu hình trước để kiểm tra lỗi, ghi khóa vào kho và in thông báo duy nhất theo mẫu: `Đã lưu khóa 9Router qua kho DPAPI: <alias> (v<n>)`, tuyệt đối không in giá trị khóa.
- `tools/launcher/prod/set_router_key.py`: Tập lệnh mỏng cho phép người vận hành nhập khóa 9Router một lần vào kho DPAPI. Tự động thêm `src` và `tools/launcher` vào `sys.path`, phân giải bố cục lưu trữ qua `launcher.resolve_layout(os.environ)` và gọi `run(...)` với `getpass.getpass`. Không nhận khóa qua đối số dòng lệnh (`sys.argv` / `argparse`), không sửa đổi `tools/launcher/launcher.py`, không thêm lệnh con vào `launcher.COMMANDS`.
- `tests/integration/prod_ports/test_pp_2_credentials.py`: Bộ kiểm thử tích hợp toàn diện gồm 84 ca kiểm thử bao quát toàn bộ hành vi của `ports.json`, `ports_config.py`, `credentials.py`, `router_key_entry.py`, `set_router_key.py`, kiểm tra bảo toàn lệnh `launcher.COMMANDS` và kiểm tra tĩnh văn bản nguồn không chứa chuỗi cấm.
- `docs/delivery-evidence/pp-2/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ (Bước 11)
Tại Bước 11, sau khi tạo tệp cấu hình `ports.json`, các khung tạm (stub) ném `NotImplementedError` và bộ kiểm thử `test_pp_2_credentials.py`, lệnh pytest được thực thi với Python interpreter đã khóa để chứng kiến oracle RED hợp lệ:
```text
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_real_ports_json_loads_with_expected_values
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys0]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys1]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys2]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys3]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys4]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys5]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys6]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys7]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_key_is_rejected[keys8]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys0-0]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys1--1]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys2-True]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys3-1]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys4-1.5]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys5-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys6-]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys7-  ]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys8-7]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys9-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys10-]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys11-  ]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys12-7]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys13-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys14-0]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys15--1]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys16-True]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys17-60]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys18-60.5]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys19-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys20-]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys21-7]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys22-a/b]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys23-a\b]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys24-..]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys25-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys26-value26]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys27-original]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys28-value28]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys29-value29]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys30-value30]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys31-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys32-value32]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys33-x]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys34-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys35-1]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_wrong_type_or_value_is_rejected[keys36-1]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_non_object_or_invalid_json_is_rejected[]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_non_object_or_invalid_json_is_rejected[[]]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_non_object_or_invalid_json_is_rejected[{]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_non_object_or_invalid_json_is_rejected[\ufeff{}]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_acquire_is_contextmanager_returning_stored_key
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_stored_key_is_stripped
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_unknown_method_or_account_raises_value_error[oauth-router-primary]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_unknown_method_or_account_raises_value_error[-router-primary]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_unknown_method_or_account_raises_value_error[secret_broker_handle-drive-primary]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_unknown_method_or_account_raises_value_error[secret_broker_handle-]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_unknown_method_or_account_raises_value_error[secret_broker_handle-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_missing_alias_raises_provider_credential_error
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_revoked_alias_raises_without_value
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_undecryptable_cipher_raises_without_value
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_constructor_rejects_bad_refs[-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_constructor_rejects_bad_refs[  -router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_constructor_rejects_bad_refs[router-primary-]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_constructor_rejects_bad_refs[router-primary-None]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_constructor_rejects_bad_refs[None-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_constructor_rejects_bad_refs[7-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_no_canary_in_repr_str_stdout_stderr_or_log
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_blank_key_is_rejected_and_nothing_stored[]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_blank_key_is_rejected_and_nothing_stored[   ]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_blank_key_is_rejected_and_nothing_stored[\t\r\n]
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_non_string_key_is_rejected
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_store_router_key_returns_increasing_versions
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_run_prints_only_alias_and_version
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_run_blank_key_prints_nothing
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_run_asks_for_no_key_when_ports_config_is_invalid
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_script_uses_getpass_and_no_command_line_key
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_script_main_stores_key_from_getpass
FAILED tests/integration/prod_ports/test_pp_2_credentials.py::test_script_main_reports_layout_error_without_traceback
79 failed, 5 passed in 1.31s
```
- **Exit Code:** `1`
- **Xác thực Oracle RED:**
  * 51 ca kiểm thử thất bại do `NotImplementedError` từ khung tạm của `load_ports_config`.
  * 17 ca kiểm thử thất bại do `NotImplementedError` từ khung tạm của `RouterKeyCredentials.acquire`.
  * 8 ca kiểm thử thất bại do `NotImplementedError` từ khung tạm của `store_router_key` và `run`.
  * 3 ca kiểm thử thất bại do `AssertionError` (thiếu cấu trúc AST `getpass.getpass`) và `NotImplementedError` từ khung tạm `main`.
  * 5 ca kiểm thử PASS gồm: `test_ports_json_is_utf8_without_bom`, `test_launcher_commands_unchanged`, và 3 test quét tĩnh chuỗi cấm `test_sources_have_no_forbidden_text`.
  * Hoàn toàn không có lỗi collection, `ImportError` hay `ModuleNotFoundError`.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm tra
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 18 / 20) | `git diff --check` | 0 | Thoát 0, không có lỗi khoảng trắng thừa hay định dạng |
| Lệnh kiểm 2 (Bước 16) | `python -m pytest tests/integration/prod_ports/test_pp_2_credentials.py -q -p no:cacheprovider` | 0 | `84 passed in 1.20s` |
| Lệnh kiểm 3 (Bước 17) | `python -c "import pathlib, json; d = pathlib.Path('src/controlplane/infrastructure/production_ports'); t = ' '.join((d / n).read_text(encoding='utf-8').lower() for n in ['credentials.py', 'router_key_entry.py', 'ports_config.py']); assert 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-2'; j = json.loads(pathlib.Path('tools/launcher/prod/ports.json').read_text(encoding='utf-8')); assert j['router']['secret_ref'] != 'drive-primary-oauth', 'alias'"` | 0 | Thoát 0, probe tĩnh đạt chuẩn, không có AssertionError |

## 4. Ánh xạ các yêu cầu nghiệm thu (Acceptance Criteria)

### Yêu cầu 1: Cấu hình ports.json và trình nạp PortsConfig chặt chẽ
- **Yêu cầu:** `ports.json` (UTF-8) có `revision`, `router` (`account_ref` `router-primary`, `secret_ref` `router-primary-api-key`), `gpu_lease` (`grace_seconds` 60), `drive` (`placement_state_file` `drive-placement.json`, `artifact_namespaces` `original`, `reusable`, `output`). `ports_config.py` có `PortsConfig` (dataclass frozen) và `load_ports_config(path)` kiểm chặt: thiếu hoặc sai kiểu thì `ValueError`, không mặc định ngầm.
- **Các test chứng minh:**
  * `test_real_ports_json_loads_with_expected_values`: Xác minh `ports.json` thật được nạp đầy đủ các giá trị chuẩn, là dataclass frozen không thể gán lại trường.
  * `test_ports_json_is_utf8_without_bom`: Xác minh tệp cấu hình được mã hóa UTF-8 chuẩn không có BOM.
  * 9 test `test_missing_key_is_rejected`: Xác minh việc thiếu bất kỳ khóa nào (`revision`, `router`, `account_ref`, `secret_ref`, `gpu_lease`, `grace_seconds`, `drive`, `placement_state_file`, `artifact_namespaces`) đều ném `ValueError`.
  * 37 test `test_wrong_type_or_value_is_rejected`: Xác minh từ chối số âm, 0, boolean `True`, chuỗi số thực, kiểu `None`, chuỗi rỗng/khoảng trắng, tên tệp chứa ký tự phân cách thư mục (`/`, `\`), danh sách rỗng, danh sách chứa trùng lặp hoặc khóa lạ thừa thãi.
  * 4 test `test_non_object_or_invalid_json_is_rejected`: Xác minh từ chối nội dung JSON rỗng, JSON mảng, JSON hỏng cú pháp, và JSON có BOM.
  * Lệnh kiểm probe xác nhận `router.secret_ref != 'drive-primary-oauth'`.
- **Phản ví dụ đã loại trừ:** Mặc định ngầm trong `ports_config.py`; alias trùng `drive-primary-oauth`.

### Yêu cầu 2: RouterKeyCredentials và bảo vệ bí mật DPAPI
- **Yêu cầu:** `credentials.py`: `ProviderCredentialError` và `RouterKeyCredentials(store, router_account_ref, router_secret_ref)` cài `CredentialSourcePort`; `acquire` là `contextmanager`, kiểm `credential_method == CREDENTIAL_METHOD` và `account_ref` đúng (sai thì `ValueError`), đọc khóa bằng `DpapiRefreshTokenReader(store).read`; thiếu hoặc giải mã lỗi thì `ProviderCredentialError` không chứa giá trị; `__repr__` che giá trị.
- **Các test chứng minh:**
  * `test_acquire_is_contextmanager_returning_stored_key`: Xác minh `acquire` có thuộc tính `__wrapped__` (là một `contextmanager`) và trả về đúng canary đã lưu trong kho DPAPI.
  * `test_stored_key_is_stripped`: Xác minh khóa được tước bỏ khoảng trắng đầu cuối trước khi cấp cho caller.
  * 5 test `test_unknown_method_or_account_raises_value_error`: Xác minh từ chối `credential_method` lạ (như `oauth`, rỗng) hoặc `account_ref` sai lệch với `ValueError`, không để lộ canary trong thông báo lỗi.
  * `test_missing_alias_raises_provider_credential_error`: Xác minh khi không tìm thấy alias trong kho DPAPI, ném `ProviderCredentialError`.
  * `test_revoked_alias_raises_without_value`: Xác minh alias đã bị thu hồi (`revoke`) ném `ProviderCredentialError` không chứa giá trị canary.
  * `test_undecryptable_cipher_raises_without_value`: Xác minh bản mã không giải mã được (khác entropy) ném `ProviderCredentialError` mà không bọc nguyên nhân gốc gây lộ thông tin (`__cause__ is None`).
  * 6 test `test_constructor_rejects_bad_refs`: Constructor từ chối các chuỗi tham chiếu rỗng, khoảng trắng, `None` hoặc sai kiểu dữ liệu.
  * `test_no_canary_in_repr_str_stdout_stderr_or_log`: Xác nhận canary xuất hiện 0 lần trong `repr`, `str`, stdout, stderr, log; `repr` hiển thị trường bí mật dạng `[REDACTED]`.
- **Phản ví dụ đã loại trừ:** Đọc khóa từ biến môi trường hay tệp văn bản; in hoặc lộ giá trị trong ngoại lệ hay log.

### Yêu cầu 3: Quy trình nhập khóa 9Router và launcher script an toàn
- **Yêu cầu:** `router_key_entry.py`: `store_router_key(store, secret_ref, read_value)` bỏ khoảng trắng đầu cuối, từ chối rỗng, gọi `store.put`, trả phiên bản; `run(vault_dir, ports_config_path, read_value, out)` chỉ in `Đã lưu khóa 9Router qua kho DPAPI: <alias> (v<n>)`. `tools/launcher/prod/set_router_key.py` là tập lệnh mỏng thêm `src` và `tools/launcher` vào `sys.path`, gọi `launcher.resolve_layout(os.environ)` rồi `run(layout.vault_dir, <ports.json>, getpass.getpass, print)`, không nhận khóa qua đối số, không thêm lệnh con vào `launcher.COMMANDS`, không sửa `tools/launcher/launcher.py`.
- **Các test chứng minh:**
  * 3 test `test_blank_key_is_rejected_and_nothing_stored`: Từ chối nhập khóa rỗng hoặc toàn khoảng trắng/tab/xuống dòng, không lưu bất cứ bản ghi nào vào kho DPAPI.
  * `test_non_string_key_is_rejected`: Từ chối giá trị không phải chuỗi.
  * `test_store_router_key_returns_increasing_versions`: Gọi lưu nhiều lần trả về số phiên bản tăng dần (`v1`, `v2`).
  * `test_run_prints_only_alias_and_version`: Hàm `run` chỉ in duy nhất thông báo định dạng `Đã lưu khóa 9Router qua kho DPAPI: router-primary-api-key (v1)`, canary xuất hiện 0 lần trong toàn bộ output.
  * `test_run_blank_key_prints_nothing`: Khi nhập khóa rỗng, không in thông báo lưu thành công.
  * `test_run_asks_for_no_key_when_ports_config_is_invalid`: Xác minh `load_ports_config` chạy trước `read_value`, không yêu cầu người dùng nhập khóa nếu cấu hình hỏng.
  * `test_script_uses_getpass_and_no_command_line_key`: Phân tích AST của `set_router_key.py` xác minh sử dụng `getpass.getpass`, `launcher.resolve_layout`, `os.environ`, không chứa `sys.argv` hay `argparse`.
  * `test_launcher_commands_unchanged`: Xác minh `launcher.COMMANDS` giữ nguyên 7 lệnh chuẩn, không bị sửa đổi.
  * `test_script_main_stores_key_from_getpass`: Xác minh luồng thực thi của hàm `main()` lưu trữ thành công khóa nhập từ `getpass` vào kho DPAPI và in thông báo chuẩn.
  * `test_script_main_reports_layout_error_without_traceback`: Xác minh khi thiếu biến môi trường layout, trả về mã lỗi 1 và in thông báo lỗi sạch không có traceback.
  * 3 test `test_sources_have_no_forbidden_text`: Quét toàn bộ văn bản của 3 tệp mã nguồn bảo đảm không chứa `from src.`, `mock`, `fake`, `os.environ`, `getenv`, `argv`, hay `subprocess`.
- **Phản ví dụ đã loại trừ:** Nhận khóa qua đối số dòng lệnh; in giá trị khóa; thêm lệnh con vào `launcher.COMMANDS` làm đỏ kiểm thử launcher CLI.

## 5. Giới hạn và an toàn (Limitations)
- Không có bất kỳ bí mật thật, token hay API key nào được đưa vào kho lưu trữ; canary sử dụng trong các ca kiểm thử chỉ là chuỗi tổng hợp ngẫu nhiên (`sk-pp2-canary-0123456789abcdef`) trong thư mục tạm `tmp_path`.
- Không thực hiện chạy full regression suite; tuân thủ đúng nguyên tắc kỷ luật thực thi mục tiêu (chỉ chạy 3 lệnh kiểm thử được chỉ định cho gói `PP-2`).
- Không sửa đổi tệp `tools/launcher/launcher.py`; biến bộ lệnh `launcher.COMMANDS` hoàn toàn bất biến.
- Tuyệt đối không can thiệp vào các nhánh `main` hay `backup`, không tự ý thực hiện `git push` hay `git merge`.
- Cổng kích hoạt sản xuất thực tế vẫn giữ nguyên trạng thái khóa an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
- Mục mở: `pyproject.toml` chưa khai gói `production_ports` là mục mở `OI-PP-07` thuộc thẩm quyền của Control, không tự ý sửa đổi.