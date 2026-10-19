# Báo cáo bằng chứng I-12

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d3b0cff0a6c39bb4cce7451ff61435358b50a768`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-12 trong `docs/implementation/i/slices.md`, CT-STO-010, D8-I-09, INV-012.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider` (chạy với stub ở bước 4)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `54 failed, 2 passed in 0.43s`
- Chi tiết các test FAILED kèm thông điệp:
  - `FAILED tests/unit/storage/test_storage_placement.py::test_fixture_kind_voice_has_rule`: `AssertionError: assert PlacementDecision('', '', '', False) == PlacementDecision('acct-a', 'ns-voice', 'rev-1', False)`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_primary_chosen_up_to_reserve_boundary`: `AssertionError: assert ('', False) == ('acct-a', False)`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_fallback_when_primary_hits_reserve`: `AssertionError: assert PlacementDecision('', '', '', False) == PlacementDecision('acct-b', 'ns-voice', 'rev-1', True)`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_fallbacks_are_tried_in_declared_order`: `AssertionError: assert ('', False) == ('acct-c', True)`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_account_outside_rule_is_never_used`: `Failed: DID NOT RAISE PlacementRejected`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_unknown_kind_is_rejected_without_default_account`: `Failed: DID NOT RAISE PlacementRejected`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_shared_quota_domain_does_not_add_capacity`: `AssertionError: assert ('', False) == ('acct-a', False)`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_missing_quota_data_is_rejected_even_when_primary_fits[primary]`: `Failed: DID NOT RAISE PlacementRejected`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_missing_quota_data_is_rejected_even_when_primary_fits[fallback]`: `Failed: DID NOT RAISE PlacementRejected`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_missing_quota_data_is_rejected_even_when_primary_fits[capacity]`: `Failed: DID NOT RAISE PlacementRejected`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_missing_quota_data_is_rejected_even_when_primary_fits[used]`: `Failed: DID NOT RAISE PlacementRejected`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_credential_like_ref_is_rejected[...]` (24 trường hợp kiểm tra các vị trí namespace, primary, fallback, domain với các giá trị bad ref token=abc, TOKEN=abc, my-Secret-acct, drive://folder, rỗng, khoảng trắng): `Failed: DID NOT RAISE PlacementRejected`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_policy_revision_is_copied_into_decision`: `AssertionError: assert '' == 'rev-42'`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_rule_is_selected_by_artifact_kind`: `AssertionError: assert PlacementDecision('', '', '', False) == PlacementDecision('acct-d', 'ns-subtitle', 'rev-1', False)`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_reserve_ratio_comes_from_policy[...]` (6 trường hợp kiểm tra các tỷ lệ reserve 0.0, 0.5, 1.0): `AssertionError` hoặc `Failed: DID NOT RAISE PlacementRejected`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_capacity_scale_comes_from_input[...]` (3 trường hợp kiểm tra các dung lượng 100, 10^15, 20*10^12): `AssertionError: assert '' == 'acct-a'`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_account_count_comes_from_rule`: `AssertionError: assert ('', False) == ('acct-5', True)`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_invalid_size_raises_value_error[...]` (4 trường hợp size -1, True, 1.5, "10"): `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_invalid_reserve_ratio_raises_value_error[...]` (2 trường hợp ratio -0.1, 1.1): `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/storage/test_storage_placement.py::test_duplicate_rule_for_kind_raises_value_error`: `Failed: DID NOT RAISE ValueError`
- Xác nhận: Mọi lỗi đều là AssertionError hoặc Failed: DID NOT RAISE; không có ImportError/ModuleNotFoundError/NameError/TypeError/AttributeError/lỗi collection.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `56 passed in 0.06s`

## Thay đổi

- `src/controlplane/domain/storage_meta/placement.py`:
  - Định nghĩa 4 hằng số mã từ chối: `NO_RULE = "NO_RULE"`, `UNKNOWN_QUOTA_DOMAIN = "UNKNOWN_QUOTA_DOMAIN"`, `NO_CAPACITY = "NO_CAPACITY"`, `INVALID_REF = "INVALID_REF"`.
  - Định nghĩa ngoại lệ `PlacementRejected(code)` kế thừa `Exception` với thuộc tính `self.code = code`.
  - Định nghĩa 3 dataclass frozen:
    - `PlacementRule(artifact_kind, namespace_ref, primary_account_ref, fallback_account_refs)`
    - `StoragePlacementPolicy(policy_revision, rules, quota_domain_by_account, reserve_ratio)`
    - `PlacementDecision(account_ref, namespace_ref, policy_revision, used_fallback)`
  - Hàm kiểm tra tham chiếu an toàn `_check_ref(ref)`: từ chối ref không phải chuỗi, rỗng/toàn khoảng trắng, hoặc chứa các chuỗi cấm không phân biệt hoa thường (`token=`, `secret`, `://`).
  - Hàm tìm luật `_find_rule(policy, artifact_kind)`: tìm luật theo kind, từ chối `NO_RULE` nếu không tìm thấy, ném `ValueError` nếu phát hiện duplicate rule cho cùng kind.
  - Hàm thuần túy `decide_placement(policy, artifact_kind, size_bytes, used_bytes_by_quota_domain, capacity_bytes_by_quota_domain) -> PlacementDecision`:
    - Xác thực `size_bytes` là số nguyên không âm (loại trừ `bool`).
    - Xác thực `reserve_ratio` trong đoạn `[0.0, 1.0]`.
    - Tìm rule theo kind; kiểm tra an toàn `namespace_ref`.
    - Kiểm tra an toàn cho toàn bộ account trong rule (`primary_account_ref` và tất cả `fallback_account_refs`), kiểm tra sự hiện diện của `quota_domain`, `capacity` và `used` tương ứng trước khi đưa ra quyết định (fail-closed, từ chối `UNKNOWN_QUOTA_DOMAIN` nếu thiếu bất kỳ trường nào).
    - Tính ngưỡng dung lượng khả dụng theo công thức `capacity * (1 - reserve_ratio)`.
    - Thử chọn `primary_account_ref` nếu `used + size <= limit`, nếu không thử tuần tự các `fallback_account_refs`.
    - Nếu hết dung lượng ở mọi account, từ chối `NO_CAPACITY`.
  - Xuất khẩu `__all__` gồm đúng 10 biểu tượng công khai theo thứ tự bảng chữ cái.
- `tests/unit/storage/test_storage_placement.py`:
  - Bộ 56 test case bao phủ toàn diện:
    1. Kiểm tra kind `voice` từ fixture contract `payloads.json` có rule và chọn primary thành công.
    2. Biên reserve: chọn primary khi dung lượng còn đủ đến đúng biên `capacity * (1 - reserve_ratio)`.
    3. Chuyển sang fallback khi primary chạm ngưỡng reserve.
    4. Các fallback account được thử tuần tự theo đúng thứ tự khai báo trong rule.
    5. Account nằm ngoài rule không bao giờ được sử dụng (`NO_CAPACITY`).
    6. Kind không có rule bị từ chối `NO_RULE`, không có cơ chế gán vào account mặc định.
    7. Quota domain dùng chung giữa các account không cộng dồn dung lượng.
    8. Thiếu quota domain/capacity/used cho primary hoặc fallback đều bị từ chối `UNKNOWN_QUOTA_DOMAIN`.
    9. Tham chiếu chứa credential (`token=`, `secret`, `://`) hoặc rỗng bị từ chối `INVALID_REF` ở mọi vị trí (namespace, primary, fallback, domain).
    10. `policy_revision` được sao chép nguyên vẹn vào `PlacementDecision`.
    11. Rule được chọn chính xác theo `artifact_kind`.
    12. Tỷ lệ `reserve_ratio` lấy từ policy, không hard-code.
    13. Quy mô `capacity` lấy từ input (kiểm tra với các giá trị 100, 10^15, 20 TB), không hard-code.
    14. Số lượng account lấy từ rule, không hard-code.
    15. Các dataclass đều `frozen=True` và không có default value.
    16. Xác thực `size_bytes` âm / không phải int ném `ValueError`.
    17. Xác thực `reserve_ratio` ngoài [0, 1] ném `ValueError`.
    18. Trùng rule cho cùng kind ném `ValueError`.
    19. Tính thuần túy (pure): không làm thay đổi dữ liệu đầu vào và luôn đơn định.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider` (RED) | 1 | 54 failed, 2 passed in 0.43s |
| 2 | `python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider` (GREEN) | 0 | 56 passed in 0.06s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 4 | `python -c "import pathlib; fs=['src/controlplane/domain/storage_meta/placement.py','tests/unit/storage/test_storage_placement.py','docs/delivery-evidence/i-12/report.md']; bad=[(f,i) for f in fs for i,l in enumerate(pathlib.Path(f).read_text(encoding='utf-8').splitlines(),1) if l!=l.rstrip()]; assert not bad, bad; print('OK')"` | 0 | OK (UTF-8 không BOM, LF, không trailing whitespace) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: mã `INVALID_REF` cho ref chứa `token=`, `secret`, `://` (so khớp không phân biệt hoa thường) hoặc rỗng / chỉ chứa khoảng trắng;
2. GIẢ ĐỊNH: mọi account của rule phải có quota domain, capacity và used, thiếu bất kỳ thông tin nào trong số này → `UNKNOWN_QUOTA_DOMAIN` (fail-closed, kiểm tra toàn bộ accounts trước khi chọn);
3. GIẢ ĐỊNH: biên dung lượng là inclusive `used + size <= capacity * (1 - reserve_ratio)`;
4. GIẢ ĐỊNH: `size_bytes` âm hoặc không phải kiểu `int` (loại trừ `bool`), `reserve_ratio` ngoài đoạn `[0, 1]`, rule trùng kind → ném `ValueError`;
5. GIẢ ĐỊNH: `used_fallback = True` khi account được chọn khác với `primary_account_ref`.

## Danh sách chờ user (pendingUserCheckpoint)

- Không phát sinh mục chờ user mới; giá trị cấu hình placement thật chờ PUC-I-01 / CP7-I-02; không mục nào được coi là đã duyệt.

## Giới hạn

- Không chạy full suite; không chạy tests/m1, tests/m2.
- Không sửa `__init__.py`, migration, pyproject.toml, lockfile.
- Không thêm thư viện ngoài stdlib.
- Không gọi dịch vụ thật (Google Drive, Cloud Storage thật).
- Không tạo conftest.py hay __init__.py trong tests/.
- Không hard-code tỷ lệ reserve, dung lượng (kể cả 20 TB), số account hay account mặc định.
- Chỉ sửa đúng 3 owned paths được phân quyền:
  - `src/controlplane/domain/storage_meta/placement.py`
  - `tests/unit/storage/test_storage_placement.py`
  - `docs/delivery-evidence/i-12/report.md`
