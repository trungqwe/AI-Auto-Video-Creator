# Báo cáo bằng chứng chuyển giao: PP-6

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `src/controlplane/infrastructure/production_ports/route_catalog.py`: Triển khai `ProfileRouteCatalog` và protocol `SecretVersionPort` theo hồ sơ production (CT-AI-ROUTE-001, QR-SEC-009):
  * `ProfileRouteCatalog`: Cài đặt `RouteCatalogPort.candidates(workspace_id, ai_role)`. Nhận `(model_refs, account_ref, secret_ref, store)` trong hàm khởi tạo; sao chép bất biến và kiểm tra hợp lệ các tham số đầu vào (từ chối chuỗi rỗng, kiểu không hợp lệ hoặc mapping rỗng bằng `ValueError`).
  * `candidates(workspace_id, ai_role)`: Nếu vai trò `ai_role` không nằm trong danh mục `model_refs` thì trả về tuple rỗng `()`; ngược lại trả về đúng một `RouteCandidate` duy nhất với các thuộc tính: `provider_ref='9router'`, `model_ref=model_refs[ai_role]`, `candidate_ref='9router:' + model_ref`, `cost_class='free'`, `max_data_sensitivity='internal'`, `local=False`, `quota_domain_key='9router-gemini'`, `roles` là tập frozenset tất cả vai trò được cấu hình.
  * Đối tượng `ExternalAccount` gắn kèm candidate có `external_account_id=account_ref`, `workspace_id` đúng tham số truyền vào, `provider='9router'`, `account_label=account_ref`, `capabilities` là tập frozenset các vai trò, `project_ref=None`, `revision=1`.
  * Quy tắc trạng thái tài khoản: Lấy trực tiếp từ `store.current_version(secret_ref)` mà không đọc giá trị bí mật; nếu phiên bản khác `None` thì trạng thái là `ExternalAccountStatus.ENABLED` và `credential_version=version`; nếu `store.current_version` trả về `None` (chưa có khóa hoặc khóa bị thu hồi) thì trạng thái là `ExternalAccountStatus.REVOKED` và `credential_version=0`.
  * Hoàn toàn là mã thuần: không truy cập mạng, không đọc CSDL, không đọc giá trị khóa bí mật và không sửa `route_resolver.py`.
- `tests/integration/prod_ports/test_pp_6_route_catalog.py`: Bộ kiểm thử tích hợp 11 hàm kiểm thử (bao quát 27 ca kiểm thử) tích hợp trực tiếp với `ProviderRouteResolver`, `CapacityReservationBook`, `InMemoryReservationStore` và `DpapiSecretStore` thật, kiểm chứng toàn diện từ điều hướng vai trò, các trường thuộc tính, tính kế thừa workspace_id, từ chối vai trò lạ, chặn tuyến khi thiếu/thu hồi khóa, kiểm soát tham số hàm dựng và kiểm tra tĩnh AST/mã nguồn.
- `docs/delivery-evidence/pp-6/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ
Tại Bước 5, sau khi tạo khung tạm (stub) ném `NotImplementedError('PP-6')` tại `route_catalog.py` và hoàn thành bộ kiểm thử `test_pp_6_route_catalog.py`, lệnh pytest được thực thi với Python interpreter đã khóa để chứng kiến oracle RED hợp lệ:
```text
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_role_resolves_to_profile_model[analysis]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_role_resolves_to_profile_model[angle]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_role_resolves_to_profile_model[image_safety]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_role_resolves_to_profile_model[metadata]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_role_resolves_to_profile_model[script]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_role_resolves_to_profile_model[selection]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_candidate_fields
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_account_workspace_follows_argument
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_unknown_role_has_no_candidate_and_no_route
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_missing_key_marks_account_revoked_and_blocks_route
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_revoke_removes_route_and_new_key_restores_it
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_status_comes_only_from_current_version[1-ENABLED]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_status_comes_only_from_current_version[7-ENABLED]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_status_comes_only_from_current_version[None-REVOKED]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_model_refs_are_copied_at_construction
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs0-router-primary-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[None-router-primary-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs2-router-primary-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs3-router-primary-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs4-router-primary-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs5-router-primary-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs6--router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs7-None-router-primary-api-key]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs8-router-primary-]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs9-router-primary-  ]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_constructor_rejects_bad_arguments[model_refs10-router-primary-None]
FAILED tests/integration/prod_ports/test_pp_6_route_catalog.py::test_source_is_pure_and_hard_codes_no_model
27 failed in 0.40s
```
- **Exit Code:** `1`
- **Xác thực Oracle RED:**
  * 15 ca kiểm thử vai trò/candidate/revoke/status thất bại do `NotImplementedError: PP-6` phát ra từ phương thức `candidates()` của khung tạm.
  * 11 ca kiểm thử tham số hóa của `test_constructor_rejects_bad_arguments` thất bại do `Failed: DID NOT RAISE ValueError` vì hàm dựng của khung tạm chỉ có lệnh `pass`.
  * 1 ca kiểm thử `test_source_is_pure_and_hard_codes_no_model` thất bại do `AssertionError: assert 'routecandidate' in ...` vì mã nguồn khung tạm chưa có tham chiếu tới `RouteCandidate`.
  * Hoàn toàn không có lỗi collection, `ImportError` hay `ModuleNotFoundError`.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 9) | `git diff --check` | 0 | Thoát 0, không có cảnh báo khoảng trắng hay định dạng dòng |
| Lệnh kiểm 2 (Bước 7) | `python -m pytest tests/integration/prod_ports/test_pp_6_route_catalog.py -q -p no:cacheprovider` | 0 | `27 passed in 0.22s` |
| Lệnh kiểm 3 (Bước 8) | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/route_catalog.py').read_text(encoding='utf-8').lower(); assert 'routecandidate' in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-6'"` | 0 | Thoát 0, probe tĩnh đạt chuẩn, không có AssertionError |

## 4. Ánh xạ yêu cầu nghiệm thu

### Yêu cầu 1: ProfileRouteCatalog cài đặt RouteCatalogPort.candidates(workspace_id, ai_role)
- **Yêu cầu:** `ProfileRouteCatalog(model_refs, account_ref, secret_ref, store)` cài `RouteCatalogPort.candidates(workspace_id, ai_role)`: vai trò không có trong `model_refs` thì trả danh sách rỗng; ngược lại trả đúng một `RouteCandidate` với `provider_ref='9router'`, `model_ref=model_refs[ai_role]`, `candidate_ref='9router:' + model_ref`, `cost_class='free'`, `max_data_sensitivity='internal'`, `local=False`, `quota_domain_key='9router-gemini'`, `roles` là tập vai trò, và `ExternalAccount` có `external_account_id=account_ref`, `workspace_id` đúng tham số, `capabilities` là tập vai trò, `status=ENABLED` khi `store.current_version(secret_ref)` khác `None`, ngược lại `REVOKED`.
- **Các test chứng minh:**
  * `test_role_resolves_to_profile_model`: Sáu vai trò `analysis`, `angle`, `script`, `selection`, `metadata`, `image_safety` thông qua `ProviderRouteResolver` và `CapacityReservationBook` thật cho decision có `account_ref='router-primary'`, `provider_ref='9router'`, `model_ref` đúng profile, `credential_acquisition_method='secret_broker_handle'`, `estimated_cost_class='free'` và giữ reservation trong domain `9router-gemini`.
  * `test_candidate_fields`: Kiểm tra đầy đủ các thuộc tính của `RouteCandidate` và `ExternalAccount` (đóng băng, `roles` và `capabilities` là frozenset, `status` là `ENABLED`).
  * `test_account_workspace_follows_argument`: `workspace_id` của tài khoản khớp chính xác với tham số truyền vào hàm `candidates()`.
  * `test_unknown_role_has_no_candidate_and_no_route`: Vai trò lạ trả về danh sách rỗng và khiến resolver ném `NoRouteError` mã `NO_ELIGIBLE_ROUTE`.
  * `test_status_comes_only_from_current_version`: Trạng thái `ENABLED` hay `REVOKED` chỉ lấy từ `store.current_version(secret_ref)`.
  * `test_model_refs_are_copied_at_construction`: `model_refs` được sao chép lúc khởi tạo, việc thay đổi dict bên ngoài không ảnh hưởng đến catalog.
  * `test_constructor_rejects_bad_arguments`: Từ chối các tham số sai lệch, rỗng, không phải string hoặc mapping rỗng bằng `ValueError`.
- **Phản ví dụ đã loại trừ:** Hard-code tên model; đọc CSDL hay gọi mạng.

### Yêu cầu 2: Quản lý khóa trong kho bí mật và bảo đảm mã nguồn thuần túy
- **Yêu cầu:** Chưa có khóa trong kho thì `NoRouteError` mã `NO_ELIGIBLE_ROUTE` kèm `ACCOUNT_NOT_ELIGIBLE`; sau `revoke` khóa thì tuyến bị loại. Mã thuần: không mạng, không CSDL, không đọc giá trị bí mật, không sửa `route_resolver.py`; không có `from src.`, `mock`, `fake`, `os.environ`.
- **Các test chứng minh:**
  * `test_missing_key_marks_account_revoked_and_blocks_route`: Khi chưa lưu khóa vào kho, tài khoản có trạng thái `REVOKED` và resolver ném `NoRouteError` mã `NO_ELIGIBLE_ROUTE` kèm mã lý do `ACCOUNT_NOT_ELIGIBLE`, không cấp reservation.
  * `test_revoke_removes_route_and_new_key_restores_it`: Khi thu hồi (`revoke`) khóa trong kho, tài khoản chuyển sang `REVOKED` và tuyến bị loại; khi thêm khóa mới thì tuyến tự động hồi phục và điều hướng thành công.
  * `test_source_is_pure_and_hard_codes_no_model`: Kiểm tra tĩnh AST và văn bản mã nguồn xác nhận mã thuần túy, chỉ import các module trong phạm vi cho phép, không chứa chuỗi cấm (`from src.`, `mock`, `fake`, `os.environ`, `getenv`, `sqlite`, `socket`, `subprocess`, `urllib`, `httpx`, `requests`, `psycopg`, `sqlalchemy`, `open(`, `reveal`, `dpapi`), không hard-code tên model.
  * Probe lệnh dòng lệnh `python -c`: Xác nhận `routecandidate` có mặt và các chuỗi cấm không xuất hiện trong `route_catalog.py`.
- **Phản ví dụ đã loại trừ:** Cho tuyến chạy khi thiếu khóa; sửa đổi `route_resolver.py`.

## 5. Giới hạn và GIẢ ĐỊNH
- (a) Trạng thái tài khoản lấy từ `store.current_version` tại mỗi lần gọi `candidates`, không sử dụng bộ nhớ đệm (cache) nội bộ.
- (b) Một tuyến cho mỗi vai trò, `project_ref=None`, `credential_version=0` khi chưa có khóa trong kho, `revision=1`.
- (c) Quota capacity do caller cấp; bộ kiểm thử sử dụng hàm callback trả về `None` nên rationale ghi nhận là `QUOTA_UNCERTAIN` theo cơ chế chuẩn của `ProviderRouteResolver`.
- (d) Không thực hiện chạy full regression suite; tuân thủ nghiêm ngặt nguyên tắc kỷ luật thực thi mục tiêu (`targetedCommand`). Không tự ý `git push` hay `git merge`, không chạm vào nhánh `main` hay `backup`. Cổng kích hoạt sản xuất thực tế vẫn giữ nguyên trạng thái khóa an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
