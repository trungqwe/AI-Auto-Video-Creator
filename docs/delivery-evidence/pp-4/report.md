# Báo cáo bằng chứng chuyển giao: PP-4

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `src/controlplane/infrastructure/production_ports/artifact_source.py`: Triển khai cổng `StagingArtifactSource(staging_root)` cài đặt cổng giao diện `ArtifactSourcePort`. Tham số `staging_root` bắt buộc phải là một đối tượng `Path` tuyệt đối (`staging_root.is_absolute()`); định danh `artifact_version_id` được kiểm tra chặt chẽ bằng biểu thức chính quy riêng `_ARTIFACT_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')` qua phương thức `fullmatch`; đường dẫn giải quyết `candidate = (staging_root / artifact_version_id).resolve()` bắt buộc phải nằm trong thư mục gốc `base = staging_root.resolve()` (`base in candidate.parents`); nếu thiếu tệp thì ném `FileNotFoundError('ARTIFACT_NOT_FOUND')`, nếu là thư mục hoặc định danh không hợp lệ thì ném `ValueError('INVALID_ARTIFACT_REF')`; luồng tệp được mở ở chế độ đọc nhị phân `rb` (`candidate.open('rb')`). Logic kiểm tra đường dẫn an toàn được viết độc lập, không import `resolve_under_root` từ tầng `controlplane.api`, không tạo, không ghi, không xóa tệp trên đĩa, không đọc biến môi trường và không dùng mock/fake.
- `tests/integration/prod_ports/test_pp_4_artifact_source.py`: Bộ kiểm thử tích hợp toàn diện gồm 19 hàm kiểm thử (bao quát 56 ca kiểm thử) kiểm tra đầy đủ các hành vi của `StagingArtifactSource`: khớp chữ ký với `ArtifactSourcePort.open`, đọc đúng nội dung và SHA-256 khớp tuyệt đối, hỗ trợ đo kích thước qua `seek(0, 2)` / `tell()` và tua lại `seek(0)`, kiểm chứng luồng chỉ đọc `rb` không thể ghi, chấp nhận định danh hợp lệ theo mẫu (kể cả độ dài 128 ký tự), từ chối danh sách `BAD_IDS` (chứa `..`, `a/b`, `a\b`, `/etc/passwd`, `C:x`, chuỗi rỗng, độ dài 129, ký tự điều khiển, khoảng trắng), từ chối định danh không phải chuỗi, từ chối đường dẫn tuyệt đối ra ngoài, từ chối traversal vượt khỏi staging, từ chối symlink trỏ ra ngoài, ném `FileNotFoundError` khi thiếu tệp hoặc thiếu staging root, ném `ValueError` khi mở thư mục, từ chối `staging_root` tương đối, và quét tĩnh AST mã nguồn xác nhận tính độc lập và chỉ đọc.
- `docs/delivery-evidence/pp-4/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ (Bước 5)
Tại Bước 5, sau khi tạo khung tạm (stub) ném `NotImplementedError('PP-4')` tại `artifact_source.py` và hoàn thành bộ kiểm thử `test_pp_4_artifact_source.py`, lệnh pytest được thực thi với Python interpreter đã khóa để chứng kiến oracle RED hợp lệ:
```text
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_open_returns_exact_bytes_and_sha256
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_stream_supports_size_probe_then_rewind
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_stream_is_read_only
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_accepts_ids_matching_the_pattern[a]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_accepts_ids_matching_the_pattern[Z]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_accepts_ids_matching_the_pattern[0]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_accepts_ids_matching_the_pattern[a.b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_accepts_ids_matching_the_pattern[a_b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_accepts_ids_matching_the_pattern[a-b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_accepts_ids_matching_the_pattern[a..b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_accepts_id_of_exactly_128_chars
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[..]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[.]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[../x]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[..\\x]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a/b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a\\b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[/etc/passwd]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[C:x]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[C:\\x]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[C:/x]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[ ]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a\x00b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a\x1fb]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a\x7fb]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a\nb]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a\n]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a\r]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a\tb]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[.hidden]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[-lead]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[_lead]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[\xe9]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a:b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a*b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_ids_outside_the_pattern[a?b]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_non_string_ids[None]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_non_string_ids[1]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_non_string_ids[a]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_non_string_ids[artifact_id3]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_absolute_path_to_existing_file
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_rejects_traversal_to_existing_outside_file
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_missing_file_raises_file_not_found
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_missing_staging_root_raises_file_not_found
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_directory_instead_of_file_is_invalid
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_staging_root_must_be_an_absolute_path[root0]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_staging_root_must_be_an_absolute_path[root1]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_staging_root_must_be_an_absolute_path[root2]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_staging_root_must_be_an_absolute_path[staging]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_staging_root_must_be_an_absolute_path[None]
FAILED tests/integration/prod_ports/test_pp_4_artifact_source.py::test_source_is_independent_and_read_only
54 failed, 1 passed, 1 skipped in 1.40s
```
- **Exit Code:** `1`
- **Xác thực Oracle RED:**
  * 48 ca kiểm thử thất bại do `NotImplementedError: PP-4` từ khung tạm `StagingArtifactSource.open`.
  * 5 ca kiểm thử tham số hóa của `test_staging_root_must_be_an_absolute_path` thất bại do `Failed: DID NOT RAISE ValueError` vì khung tạm chưa kiểm tra tính tuyệt đối của `staging_root`.
  * 1 ca kiểm thử `test_source_is_independent_and_read_only` thất bại do `AssertionError: invalid_artifact_ref` vì khung tạm chưa có các hằng số và biểu thức chính quy.
  * 1 ca kiểm thử `test_signature_matches_artifact_source_port` passed vì chữ ký `(self, artifact_version_id)` đã khớp sẵn với giao diện port.
  * 1 ca kiểm thử `test_rejects_symlink_pointing_outside_staging` skipped (`host forbids creating symlinks`) do hạn chế quyền tạo symlink trên môi trường Windows.
  * Hoàn toàn không có lỗi collection, `ImportError` hay `ModuleNotFoundError`.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm tra
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 10) | `git diff --check` | 0 | Thoát 0, không có lỗi khoảng trắng thừa hay định dạng |
| Lệnh kiểm 2 (Bước 7) | `python -m pytest tests/integration/prod_ports/test_pp_4_artifact_source.py -q -p no:cacheprovider` | 0 | `55 passed, 1 skipped in 0.89s` |
| Lệnh kiểm 3 (Bước 8) | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/artifact_source.py').read_text(encoding='utf-8').lower(); assert 'controlplane.api' not in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-4'"` | 0 | Thoát 0, probe tĩnh đạt chuẩn, không có AssertionError |

## 4. Ánh xạ các yêu cầu nghiệm thu (Acceptance Criteria)

### Yêu cầu 1: Cổng StagingArtifactSource(staging_root) đọc tệp an toàn từ thư mục staging
- **Yêu cầu:** `StagingArtifactSource(staging_root)` cài `ArtifactSourcePort`: `staging_root` phải là `Path` tuyệt đối; `open(artifact_version_id)` kiểm id khớp `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`, đường dẫn `(staging_root / id).resolve()` nằm trong `staging_root.resolve()` và là tệp thường, rồi mở `rb`; sai thì `ValueError('INVALID_ARTIFACT_REF')`, thiếu thì `FileNotFoundError`. GIẢ ĐỊNH (D8, OI-PP-03): tên tệp là `artifact_version_id`.
- **Các test chứng minh:**
  * `test_open_returns_exact_bytes_and_sha256`: Đọc chính xác nội dung byte của tệp và mã băm SHA-256 khớp tuyệt đối với dữ liệu gốc.
  * `test_stream_supports_size_probe_then_rewind`: Luồng tệp hỗ trợ `seek(0, 2)` để đo kích thước, `tell()` và tua lại `seek(0)` để đọc lại từ đầu.
  * `test_stream_is_read_only`: Xác nhận luồng mở ở chế độ `rb`, không có cờ `writable()`, cố gắng ghi dữ liệu sẽ ném ngoại lệ `OSError`.
  * `test_accepts_ids_matching_the_pattern`: Chấp nhận các định danh hợp lệ khớp biểu thức chính quy (ví dụ `'a'`, `'Z'`, `'0'`, `'a.b'`, `'a_b'`, `'a-b'`, `'a..b'`).
  * `test_accepts_id_of_exactly_128_chars`: Chấp nhận định danh có độ dài chính xác 128 ký tự.
  * `test_rejects_ids_outside_the_pattern`: Từ chối tất cả các định danh trong danh sách `BAD_IDS` (`..`, `a/b`, `a\b`, `/etc/passwd`, `C:x`, chuỗi rỗng, độ dài 129, ký tự điều khiển, khoảng trắng).
  * `test_rejects_non_string_ids`: Từ chối các định danh không phải chuỗi (`None`, số nguyên, `bytes`, `PurePath`).
  * `test_rejects_absolute_path_to_existing_file`: Từ chối định danh chứa đường dẫn tuyệt đối trỏ tới tệp tồn tại bên ngoài.
  * `test_rejects_traversal_to_existing_outside_file`: Từ chối định danh sử dụng `..` để vượt ra ngoài thư mục staging.
  * `test_rejects_symlink_pointing_outside_staging`: Từ chối symlink trỏ tới tệp nằm ngoài thư mục staging.
  * `test_missing_file_raises_file_not_found`: Ném `FileNotFoundError` khi tệp được yêu cầu không tồn tại trong staging.
  * `test_missing_staging_root_raises_file_not_found`: Ném `FileNotFoundError` khi chính thư mục staging không tồn tại.
  * `test_directory_instead_of_file_is_invalid`: Ném `ValueError('INVALID_ARTIFACT_REF')` khi định danh trỏ vào thư mục thay vì tệp thường.
  * `test_staging_root_must_be_an_absolute_path`: Ném `ValueError` khi `staging_root` là đường dẫn tương đối hoặc không phải `Path`.
- **Phản ví dụ đã loại trừ:** Cho phép thoát khỏi staging qua path traversal hoặc symlink; ghi đè hoặc xóa tệp trên đĩa.

### Yêu cầu 2: Kiểm tra đường dẫn viết riêng, tính độc lập và độ sạch của mã nguồn
- **Yêu cầu:** Kiểm chứa đường dẫn viết riêng, không import `resolve_under_root` từ tầng `api`; không ghi, không xóa tệp; không có `controlplane.api`, `from src.`, `mock`, `fake`, `os.environ` trong mã.
- **Các test chứng minh:**
  * `test_source_is_independent_and_read_only`: Phân tích cây cú pháp trừu tượng AST và quét toàn văn bản của `artifact_source.py`, xác nhận chỉ import các mô-đun chuẩn `__future__`, `re`, `pathlib`, `typing`; không import bất kỳ thành phần nào từ tầng `controlplane.api` (đặc biệt không import `resolve_under_root`); không chứa các chuỗi cấm `controlplane.api`, `from src.`, `mock`, `fake`, `os.environ`, `getenv`, `resolve_under_root`, `unlink`, `rmtree`, `.write`, `.mkdir`, `.touch`, `.rename`, `'w'`, `'wb'`, `'ab'`, `'r+b'`, `subprocess`; có đầy đủ các biểu tượng bắt buộc `stagingartifactsource`, `invalid_artifact_ref`, `fullmatch`, `.resolve()`, `'rb'`.
  * Lệnh probe tĩnh kiểm tra trực tiếp tệp mã nguồn thoát mã 0 không có `AssertionError`.
- **Phản ví dụ đã loại trừ:** Import `resolve_under_root` từ `controlplane.api`; sử dụng mock/fake hay nhánh giả lập; mở tệp ở chế độ ghi.

## 5. Giới hạn và an toàn (Limitations)
- GIẢ ĐỊNH (D8, OI-PP-03): Tên tệp trong thư mục staging chính là `artifact_version_id`.
- Ca kiểm thử `test_rejects_symlink_pointing_outside_staging` được bỏ qua (`skipped`) trên môi trường Windows do hệ điều hành hạn chế quyền tạo symlink đối với tài khoản không có đặc quyền Administrator hoặc Developer Mode; mã nguồn vẫn triển khai đầy đủ cơ chế bảo vệ `.resolve()` và `candidate.parents`.
- Kiểm tra sự tồn tại và mở tệp là hai thao tác tuần tự (check-then-open) nên không chống được tình huống TOCTOU (Time of Check to Time of Use) nếu một tiến trình ngoài can thiệp thay thế tệp giữa hai thời điểm trong thư mục staging.
- Không thực hiện chạy full regression suite; tuân thủ nghiêm ngặt nguyên tắc kỷ luật thực thi mục tiêu (`targetedCommand`).
- Không thực hiện `git push` hay `git merge`, không chạm vào nhánh `main` hay `backup`.
- Cổng kích hoạt sản xuất thực tế vẫn giữ nguyên trạng thái khóa an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
