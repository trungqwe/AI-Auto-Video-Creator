# Báo cáo bằng chứng I-06

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `68e2ae94f4aafb49345a02583208516271e7e05e`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-06 trong `docs/implementation/i/slices.md`, CT-STO-004, CT-STO-008 điều 5.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider` (chạy với stub ở bước 3)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `364 failed, 9 passed, 7 skipped in 1.96s`
- Chi tiết các nhóm test FAILED kèm thông điệp lỗi nguyên văn:
  - Nhóm `test_rejects_empty_absolute_drive_unc_parent_and_non_string` (17 trường hợp gồm `""`, `"../../x"`, `"a/../../x"`, `"a/.."`, `"a/.. /x"`, `"/x"`, `"\x"`, `"C:/x"`, `"C:x"`, `"c:\x"`, `"//server/share/x"`, `"\\server\share\x"`, `"a//b"`, `"a/./b"`, `"a/"`, `None`, `7`): `Failed: DID NOT RAISE StagingPathError`
  - Nhóm `test_rejects_nul_forbidden_windows_and_control_characters` (10 trường hợp gồm `a\x00b.mp4`, `a<b`, `a>b`, `a"b`, `a|b`, `a?b`, `a*b`, `a:b`, `dir/a\x1fb`, `dir/a\nb`): `Failed: DID NOT RAISE StagingPathError`
  - Nhóm `test_rejects_reserved_device_names` (330 trường hợp gồm CON, PRN, AUX, NUL, COM1–COM9, LPT1–LPT9 kết hợp 3 kiểu case upper/lower/title và 5 hậu tố `""`, `".mp4"`, `".tar.gz"`, `" "`, `"."` cho cả đường dẫn trực tiếp lẫn `nested/`): `Failed: DID NOT RAISE StagingPathError`
  - Nhóm link trỏ ra ngoài hoặc qua junction `test_rejects_link_pointing_outside_root` (`link-junction`, `link/x.mp4-junction`, `link/secret.txt-junction`, `link/sub/x.mp4-junction`): `Failed: DID NOT RAISE StagingPathError`
  - Nhóm link trỏ vào trong root `test_rejects_link_pointing_inside_root[junction]`: `Failed: DID NOT RAISE StagingPathError`
  - Nhóm link trung gian dưới thư mục `test_rejects_intermediate_link_below_existing_directory[junction]`: `Failed: DID NOT RAISE StagingPathError`
  - Nhóm bọc containment kiểm tra thoát root khi detector bị mù `test_containment_check_rejects_escape_even_if_link_detection_is_blind[junction]`: `Failed: DID NOT RAISE StagingPathError`
- Ghi nhận skipped hợp lệ: 7 test symlink được skip (`không tạo được symlink trong môi trường này: [WinError 1314] A required privilege is not held by the client`) do môi trường Windows chuẩn không bật Developer Mode/quyền SeCreateSymbolicLinkPrivilege; các trường hợp tương ứng được kiểm chứng đầy đủ bằng junction native trên Windows qua `_winapi.CreateJunction`.
- Xác nhận: Toàn bộ lỗi FAILED đều là `Failed: DID NOT RAISE StagingPathError` do stub tạm thời trả `Path(staging_root) / str(relative_path)`; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection (các test chấp nhận đường dẫn lồng nhau và tên tương tự reserved name đạt PASS).

## Thay đổi

- `src/controlplane/infrastructure/storage/staging_paths.py`: Hiện thực `StagingPathError(ValueError)` và hàm `resolve_staging_path(staging_root: Path, relative_path: str) -> Path`. Sử dụng hàm nội bộ `_split_components` kiểm tra kiểu chuỗi, từ chối đường rỗng, chuẩn hoá dấu gạch chéo ngược `\`, chặn đường tuyệt đối/ký tự ổ đĩa/UNC qua anchor của `PureWindowsPath`, kiểm tra thành phần rỗng/dấu chấm/khoảng trắng (`.`, `..`, `...`), chặn ký tự cấm Windows (`<>:"|?*` và dải điều khiển `\x00-\x1f`), chặn tên thiết bị reserved DOS/Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9` không phân biệt hoa thường, kể cả có phần mở rộng). Trong quá trình duyệt từng thành phần, kiểm tra `is_symlink()` và `is_junction()` trên từng bước; sau khi duyệt thực hiện `resolve()` và bắt buộc `is_relative_to(root.resolve())`. Không import `os`/`subprocess`, không sửa `__init__.py`.
- `tests/integration/storage/test_storage_staging_paths.py`: Bộ kiểm thử tích hợp 380 test cases bao quát toàn bộ hợp đồng CT-STO-004 và CT-STO-008 điều 5: từ chối đường dẫn rỗng/tuyệt đối/ổ đĩa/UNC/thành phần `..`/ký tự không phải chuỗi; từ chối NUL và ký tự cấm Windows; từ chối tên thiết bị reserved với mọi biến thể hoa thường và đuôi mở rộng; từ chối symlink và junction trỏ ra ngoài hoặc trỏ vào trong root; kiểm chứng cơ chế chốt chặn `is_relative_to` ngay cả khi detector symlink/junction bị vô hiệu hoá; chấp nhận các đường dẫn hợp lệ lồng nhau, tệp/thư mục đã tồn tại, dấu `\` phân tách và các tên chỉ tương tự tên reserved (`CONSOLE.mp4`, `COM10`, `LPT0`, `aux_1/x.bin`, `a.b/c.d`, `con-x/nul2.mp4`).
- `docs/delivery-evidence/i-06/report.md`: Báo cáo bằng chứng thực thi I-06 ghi nhận môi trường, kết quả RED/GREEN, các quyết định mặc định D8, danh sách chờ và giới hạn kiểm thử.
- Ghi chú: `src/controlplane/infrastructure/storage/__init__.py` không bị sửa đổi.

## GREEN / Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider` | 0 | `373 passed, 7 skipped in 0.96s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: Dấu `\` được coi là dấu phân tách như `/` và được chuẩn hoá thành `/` trước khi phân rã thành phần đường dẫn.
2. GIẢ ĐỊNH: Thành phần rỗng, dấu chấm đơn `.`, dấu chấm đôi `..`, hoặc chỉ gồm chấm và khoảng trắng (sau khi rstrip `" ."`) đều bị từ chối fail-closed bằng `StagingPathError`.
3. GIẢ ĐỊNH: Tên thiết bị reserved (CON, PRN, AUX, NUL, COM1–COM9, LPT1–LPT9) được nhận diện theo stem lấy trước dấu chấm đầu tiên và loại bỏ khoảng trắng cuối (`part.split(".", 1)[0].rstrip(" ").upper()`), không phân biệt chữ hoa chữ thường.
4. GIẢ ĐỊNH: Chính `staging_root` không bị kiểm tra `is_symlink()` / `is_junction()`, chỉ kiểm tra các thành phần bên dưới root từ đường dẫn tương đối.
5. GIẢ ĐỊNH: Mọi symlink và junction trên đường dẫn tương đối từ root tới đích đều bị từ chối bằng `StagingPathError`, kể cả khi đích trỏ vào trong root (chống alias / bất định trạng thái).
6. GIẢ ĐỊNH: `StagingPathError` kế thừa từ ngoại lệ chuẩn `ValueError` để tương thích với các bộ bắt lỗi xử lý dữ liệu đầu vào.

## Danh sách chờ user (pendingUserCheckpoint)

- Không phát sinh mục mới; slice không thêm thư viện (không cần USER-CKPT-D9-D10); ghi rõ không mục nào được coi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không sửa migration, pyproject.toml, lockfile, composition root hay `__init__.py`.
- Chỉ dùng thư viện chuẩn `pathlib`, `re`; không import `os`/`subprocess` trong mã sản phẩm; không gọi dịch vụ thật.
- Không tạo conftest.py hay __init__.py trong tests/.
- Test symlink có thể skipped trên Windows khi tiến trình thiếu đặc quyền `SeCreateSymbolicLinkPrivilege`, trong khi junction được kiểm chứng đầy đủ trên Windows.
- Không commit secret.
