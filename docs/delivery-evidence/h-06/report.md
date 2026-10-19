# Báo cáo bằng chứng H-06

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `d6f0c277e1d921c36e0ba0553aca131ca6d991da`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-06 trong `docs/implementation/h/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 5)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `84 failed, 7 passed in 0.51s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_config_account_views.py::test_build_config_revision_view_keeps_values - NotImplementedError: H-06 RED skeleton: config`
  - `FAILED tests/unit/control_ui/test_h_config_account_views.py::test_build_config_revision_view_drops_unknown_keys - NotImplementedError: H-06 RED skeleton: config`
  - `FAILED tests/unit/control_ui/test_h_config_account_views.py::test_build_account_view_accepts_every_status[enabled] - NotImplementedError: H-06 RED skeleton: account`
  - `FAILED tests/unit/control_ui/test_h_config_account_views.py::test_top_level_secret_key_rejected[refresh_token] - NotImplementedError: H-06 RED skeleton: account`
  - `FAILED tests/unit/control_ui/test_h_config_account_views.py::test_committed_job_with_refs_and_fingerprint_is_valid - NotImplementedError: H-06 RED skeleton: job`
  - `FAILED tests/unit/control_ui/test_h_config_account_views.py::test_committed_job_with_empty_refs_rejected[empty_refs0] - NotImplementedError: H-06 RED skeleton: job`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 7 test hợp lệ (`test_config_view_fields_match_configs_query_keys`, `test_config_view_is_frozen`, `test_account_constants`, `test_account_view_dict_has_no_secret_keys`, `test_job_constants`, `test_job_field_names_match_binding`, `test_module_is_pure_stdlib`) đã PASS ngay từ đầu. Tất cả 84 test thất bại đều là `NotImplementedError` do khung skeleton chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 9)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `91 passed in 0.09s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/application/projections/config_account_views.py`: Module thuần định nghĩa 3 read model view (`ConfigRevisionView`, `ExternalAccountView`, `JobConfigRevisionView`), các hằng số cấu hình/trường/trạng thái/tập khóa nhạy cảm, cùng 3 builder (`build_config_revision_view`, `build_account_view`, `build_job_config_revision_view`).
  - `tests/unit/control_ui/test_h_config_account_views.py`: Bộ kiểm thử đơn vị gồm 91 test cases kiểm tra khớp 8 khóa query của configs, bỏ khóa lạ, bắt buộc frozen dataclass, kiểm tra trạng thái tài khoản, từ chối khóa bí mật ở mọi độ sâu không phân biệt hoa thường, bảo vệ rò rỉ secret trong thông báo lỗi, kiểm tra trạng thái snapshot job, đối chiếu 2 trường của job với contract binding JSON và chứng minh module chỉ import stdlib.
  - `docs/delivery-evidence/h-06/report.md`: Báo cáo bằng chứng nghiệm thu tiếng Việt đầy đủ dấu.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider` | 0 | `91 passed in 0.09s` |
| 2 | `git diff --check` | 0 | PASS (không output, không whitespace error) |

## Quyết định mặc định (D8)

1. Status của `ConfigRevisionView` chuyển tiếp nguyên giá trị, không kiểm enum.
2. Payload không phải Mapping ném `ValueError('invalid_payload')`.
3. Thứ tự kiểm tra tài khoản: kiểm tra khóa bí mật (`secret_field_present`), kiểm tra trường bắt buộc (`missing_field`), kiểm tra trạng thái hợp lệ (`invalid_status`).
4. Thứ tự kiểm tra job: kiểm tra trường bắt buộc (`missing_field`), kiểm tra snapshot state (`invalid_snapshot_state`), kiểm tra revision refs (`invalid_revision_refs`), sau đó kiểm tra refs không rỗng cho COMMITTED (`missing_revision_refs`) hoặc fingerprint hợp lệ (`invalid_fingerprint`).
5. `NOT_COMMITTED` cho phép refs rỗng và fingerprint None hoặc chuỗi rỗng (chuẩn hóa thành None).
6. Thông báo lỗi chỉ là mã cố định (`ValueError`), tuyệt đối không nhúng hay làm rò rỉ giá trị bí mật từ payload.

## Ánh xạ phản ví dụ

- View account mang `refresh_token`: Được ngăn chặn và kiểm chứng qua `test_top_level_secret_key_rejected`, `test_nested_secret_key_rejected`, `test_secret_error_does_not_leak_value`, `test_account_view_dict_has_no_secret_keys`.
- Job đã commit không hiển thị revision: Được ngăn chặn và kiểm chứng qua `test_committed_job_with_empty_refs_rejected` (bắt buộc refs không rỗng khi COMMITTED) và `test_committed_job_with_refs_and_fingerprint_is_valid`.
- Trạng thái viết hoa lẫn thường: Được ngăn chặn và kiểm chứng qua `test_build_account_view_rejects_bad_status` (từ chối `ENABLED`, `Enabled`) và `test_invalid_snapshot_state` (từ chối `committed`, `Committed`).
- Tên trường lệch binding: Được ngăn chặn và đối chiếu trực tiếp qua `test_job_field_names_match_binding` (so khớp `configuration_revision_refs` và `configuration_bundle_fingerprint` với `docs/parallel-delivery/bindings/b-d-production-snapshot.json`) và `test_config_view_fields_match_configs_query_keys`.

## coveredIds

- `CT-API-006`
- `CT-API-009`
- `CT-API-010`
- `TST-INT-INV-004`
- `TST-SEC-INV-012`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`
- `YC-HT-H-03 nối view vào route/UI nếu cần`

## Giới hạn

- Không sửa `src/controlplane/infrastructure/db/control_api_queries.py`.
- Không sửa routes, UI, `pyproject.toml`, `uv.lock`.
- Không chạy full suite, `tests/m1`, `tests/m2`.
- Chỉ sử dụng thư viện chuẩn stdlib.
- Không gọi dịch vụ thật.