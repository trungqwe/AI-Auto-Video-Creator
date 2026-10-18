# Báo cáo bằng chứng B-2

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 91878d46206a05e052217b54e81af614b6ba1bf7
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-2 trong docs/implementation/b/slices.md; D3 user duyệt Phần B ngày 18/10/2026.
- Binding refs: binding docs/parallel-delivery/bindings/a-b-collected-document.json 1.0.0.

## RED

- Lệnh thực thi: python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cacheprovider (chạy trên skeleton của normalization.py, fingerprint.py và topic.py)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 29 failed, 1 passed in 0.19s
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - FAILED tests/unit/ingestion/test_ingestion_normalization.py::test_nfd_input_is_normalized_to_nfc: AssertionError: assert 'Ha\u0300 No\... xe ma\u0301y' == 'H\xe0 N\u1ed...11i xe m\xe1y'
  - FAILED tests/unit/ingestion/test_ingestion_normalization.py::test_control_characters_are_removed: AssertionError: assert 'H\xe0\\x00 N\u1ed9i\\x...200b to\\ufeff' == 'H\xe0 N\u1ed9i m\u01b0a to'
  - FAILED tests/unit/ingestion/test_ingestion_normalization.py::test_normalizer_version_is_set: AssertionError: assert '' == 'normalize-text-r1'
  - FAILED tests/unit/ingestion/test_ingestion_normalization.py::test_topic_matches_keyword_phrase: AssertionError: assert ('', False) == ('the_thao', False)
  - FAILED tests/unit/ingestion/test_ingestion_fingerprint.py::test_exact_fingerprint_is_sha256_hex_of_normalized_text: AssertionError: assert '' == 'ba7816bf8f01...0ff61f20015ad'
  - FAILED tests/unit/ingestion/test_ingestion_fingerprint.py::test_boundary_exactly_090_is_near_duplicate: AssertionError: assert 0.0 == 0.9
  - FAILED tests/unit/ingestion/test_ingestion_fingerprint.py::test_missing_or_invalid_policy_values_fail_closed: Failed: DID NOT RAISE KeyError
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; duy nhất 	est_fingerprint_module_has_no_hard_coded_policy_values PASS trên skeleton; 29 test còn lại FAILED do AssertionError hoặc Failed: DID NOT RAISE.

## Thay đổi

- src/ingestion/domain/normalization.py: Chuẩn hóa văn bản tất định (D8-B-01, CT-CNT-003):
  - Hằng số phiên bản: NORMALIZER_VERSION = 'normalize-text-r1'.
  - Tập ký tự loại bỏ: _REMOVED_CATEGORIES = frozenset({'Cc', 'Cf'}).
  - Hàm chuẩn hóa:
ormalize_text(text: str) -> str: loại bỏ ký tự điều khiển/định dạng (Cc/Cf không phải khoảng trắng), gộp khoảng trắng liên tiếp bằng str.split, strip hai đầu và trả về dạng Unicode chuẩn NFC.
- src/ingestion/domain/fingerprint.py: Fingerprint chính xác và phát hiện gần trùng lặp (D8-B-01):
  - Hằng số định danh cấu hình: NEAR_DUPLICATE_JACCARD = 'near_duplicate_jaccard', SHINGLE_SIZE = 'shingle_size'.
  - Hàm exact_fingerprint(text: str) -> str: băm SHA-256 chuỗi văn bản UTF-8 đã qua
ormalize_text.
  - Hàm shingles(text: str, size: int) -> frozenset[tuple[str, ...]]: tách chuỗi n-gram từ (shingles) trên văn bản đã chuẩn hóa.
  - Hàm jaccard(a: Set, b: Set) -> float: tính độ tương đồng Jaccard giữa hai tập shingle.
  - Hàm is_near_duplicate(a: str, b: str, policy: Mapping) -> bool: kiểm tra trùng lặp theo ngưỡng và kích thước shingle đọc động từ policy.
- src/ingestion/domain/topic.py: Phân loại chủ đề theo từ khóa (D8-B-08):
  - Hằng số: UNCLASSIFIED = 'unclassified'.
  - Hàm helper _phrase(text: str) -> str: tách token \w+ trên văn bản đã chuẩn hóa và chuyển thường (casefold).
  - Hàm classify_topic(text: str, topic_rules: Sequence[Mapping]) -> tuple[str, bool]: phân loại dựa trên số cụm từ khóa khớp nhiều nhất, hòa luật thì giữ luật trước và trả uncertain=True, không khớp hoặc luật rỗng trả ('unclassified', True).
- 	ests/unit/ingestion/test_ingestion_normalization.py: Bộ kiểm thử đơn vị gồm 16 test cases:
  - 7 test cho normalization: chuẩn hóa NFD sang NFC, loại bỏ ký tự điều khiển (\x00, \x07, \x7f, ZWSP, BOM), gộp/strip khoảng trắng, ký tự điều khiển xen giữa base và mark, tính tất định/idempotent, từ chối kiểu dữ liệu phi chuỗi, kiểm tra NORMALIZER_VERSION.
  - 9 test cho topic classification: khớp cụm từ khóa, không phân biệt hoa thường và dạng NFC/NFD, khớp nguyên từ, không khớp luật trả unclassified/uncertain, luật rỗng, luật nhiều từ khóa nhất thắng, hòa luật ưu tiên luật trước và uncertain, tất định, từ chối quy tắc không hợp lệ.
- 	ests/unit/ingestion/test_ingestion_fingerprint.py: Bộ kiểm thử đơn vị gồm 14 test cases:
  - 5 test cho exact_fingerprint: băm SHA-256 của chuỗi chuẩn hóa, tính bất biến giữa NFC và NFD, miễn nhiễm với nhiễu khoảng trắng/ký tự điều khiển, văn bản khác nhau cho fingerprint khác nhau, tất định qua nhiều lần gọi.
  - 9 test cho near-duplicate: sinh shingle theo kích thước, kiểm tra hợp lệ của kích thước shingle, tỷ lệ Jaccard, ngưỡng biên đúng 0.90, dưới biên 0.80, đọc ngưỡng từ policy, đọc shingle_size từ policy, fail-closed khi thiếu hoặc sai khóa policy, kiểm tra mã nguồn fingerprint.py không chứa giá trị viết cứng.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | git diff --check | 0 | không output |
| 2 | python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cacheprovider | 0 | 30 passed in 0.07s |
| 3 | python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider | 0 | 35 passed in 0.05s |

## Quyết định mặc định (D8)

(Ghi nhận dưới dạng GIẢ ĐỊNH theo quy chế D8, không phải đã duyệt chính thức):
1. Bỏ ký tự Unicode Cc và Cf không phải khoảng trắng; các ký tự Cc dạng khoảng trắng (\t, \n, \r) được chuyển thành dấu cách.
2. Thứ tự xử lý chuẩn hóa: bỏ ký tự định dạng/điều khiển → gộp khoảng trắng bằng split() → chuyển sang dạng Unicode NFC; đảm bảo đầu ra luôn ở dạng NFC và idempotent.
3.
ormalize_text và exact_fingerprint giữ nguyên phân biệt hoa thường; classify_topic so khớp không phân biệt hoa thường bằng cách gọi casefold().
4. Shingle là chuỗi các từ được phân tách theo khoảng trắng sau khi chuẩn hóa; văn bản ngắn hơn shingle_size sinh ra đúng một shingle gồm toàn bộ các từ; văn bản rỗng trả về tập rỗng.
5. Độ tương đồng Jaccard của hai tập rỗng được định nghĩa bằng 0.0.
6. is_near_duplicate so sánh >= ngưỡng chỉ định; thiếu khóa policy gây lỗi KeyError; ngưỡng ngoài khoảng (0, 1] hoặc sai kiểu gây lỗi ValueError; giá trị ngưỡng 0.90 và kích thước shingle 5 (dedup-policy-r1, D8-B-01) chỉ nằm trong test suite để kiểm thử, chờ hiệu chỉnh chính thức ở CP7.
7. 	opic_rules là danh sách các mapping {'topic', 'keywords'} theo thứ tự ưu tiên; so khớp cụm từ nguyên theo token regex \w+; nhiều luật hòa điểm thì chọn luật đứng trước kèm uncertain=True; không khớp hoặc luật rỗng trả về ('unclassified', True) (D8-B-08).
8. NORMALIZER_VERSION = 'normalize-text-r1' được thiết lập để B-3/B-6 ghi nhận trường
ormalizer_version.
9. Tuyệt đối không thêm thư viện ngoài, chỉ sử dụng thư viện chuẩn của Python (unicodedata, hashlib,
e, collections.abc).

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Hiệu chỉnh ngưỡng D8-B-01 trên mẫu chất lượng
- Danh mục chủ đề D8-B-08 do Phân hệ J và user phê duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa pyproject.toml, uv.lock, file binding hay fixture.
- Không gọi dịch vụ thật hay đọc bí mật.
- Không sửa HANDOFF.md, README.md, CHANGELOG.md hay checklist nằm ngoài owned paths trong slice này.
