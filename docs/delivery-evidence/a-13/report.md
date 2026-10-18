# Báo cáo bằng chứng A-13

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `91878d46206a05e052217b54e81af614b6ba1bf7`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-13 trong `docs/implementation/a/slices.md`; phụ thuộc A-02, A-12 đã tích hợp.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider`
- Trạng thái mã lúc RED: `stdlib_html_extractor.py` trả ExtractedCandidate với technical_fields rỗng; `package_builder.py` trả dict rỗng `{}` và các hàm chuẩn hoá trả giá trị stub mặc định; `PackageContext` chưa có validate `__post_init__`.
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `45 failed, 4 passed in 0.58s`
- Test FAILED tiêu biểu nguyên văn:
  - `FAILED tests/unit/collection/test_a13_package_builder.py::test_extractor_reads_technical_fields` (AssertionError: assert None == 'stdlib-html-0')
  - `FAILED tests/unit/collection/test_a13_package_builder.py::test_package_passes_a02_validator_with_binding_fields_only` (AssertionError: assert (SchemaError(code='missing_required', field='collected_document_id'), ...) == ())
  - `FAILED tests/unit/collection/test_a13_package_builder.py::test_package_context_rejects_invalid_values[overrides0]` (Failed: DID NOT RAISE ValueError)
- Xác nhận: 0 error, không có ModuleNotFoundError, ImportError hay collection error; mọi lỗi RED là AssertionError hoặc DID NOT RAISE đúng oracle.

## Thay đổi

- `src/source_ingestion/adapters/stdlib_html_extractor.py`: Bộ trích xuất HTML tham chiếu `StdlibHtmlExtractor` chỉ dùng `html.parser` (version `stdlib-html-0`, đánh dấu docstring FIXTURE-ONLY, không phải production extractor); xử lý HTML hỏng thành cảnh báo `html_parse_error`, `html_unbalanced_tags`, `media_locator_skipped`, `html_not_text`, không bao giờ ném ngoại lệ ra ngoài; trích xuất `title`, `text` (bỏ qua script/style/noscript/template), `author`, `canonical_url`, `language_tag`, `published_at_raw`, và `media`.
- `src/source_ingestion/application/package_builder.py`: Bộ dựng gói `CollectedDocumentPackage` chuẩn hoá kỹ thuật: `decode_body` (BOM > Content-Type charset > utf-8, thay thế ký tự lỗi bằng U+FFFD kèm cảnh báo), `normalize_text` (NFC, chuẩn hoá khoảng trắng từng dòng, loại dòng rỗng), `normalize_title` (NFC, chuẩn hoá khoảng trắng), `normalize_timestamp` (RFC3339 UTC `Z`, precision `second`/`day`, confidence `high`/`low`), `normalize_language` (confidence `declared`), `PackageContext` bất biến kiểm tra hợp lệ; tạo `content_fingerprints` (sha256 văn bản chuẩn hoá và raw body sha256, không phụ thuộc title), `media_discoveries` kèm context và bản sao `provenance` riêng cho từng mục, `collected_document_id` xác định theo uuid5 quan sát; luôn chạy qua cổng `validate_package_schema` và `assess_content_eligibility` của A-02; gói không mang bất kỳ trường quyết định nào của Phân hệ B (`disposition`, `article_id`, `article_revision_id`, `dedup_policy_revision`).
- `tests/unit/collection/test_a13_package_builder.py`: Bộ kiểm thử đơn vị bao phủ toàn diện 49 ca kiểm thử với docstring ghi rõ `coveredIds: A-RULE-010, A-RULE-011`, chặn kết nối mạng socket qua fixture autouse, kiểm tra ranh giới phụ thuộc và nhập gói chỉ từ stdlib/domain/ports.

## Ánh xạ yêu cầu → test

| Yêu cầu / phản ví dụ | Test |
|---|---|
| Extractor tham chiếu fixture-only, version `stdlib-html-0`, chỉ dùng `html.parser`, import chỉ stdlib và ports | `test_extractor_is_fixture_only_reference_with_pinned_version`, `test_extractor_imports_only_stdlib_and_html_parser`, `test_builder_imports_only_stdlib_domain_and_ports` |
| Extractor đọc đúng technical fields (title, text, author, canonical, language, published, media) | `test_extractor_reads_technical_fields` |
| HTML hỏng trở thành cảnh báo, không làm crash hay ném ngoại lệ | `test_malformed_html_becomes_warning_without_raising`, `test_unbalanced_markup_is_reported`, `test_parser_exception_is_captured_as_warning`, `test_non_text_input_is_warning` |
| Chuẩn hoá kỹ thuật encoding, whitespace/NFC, timestamp precision & confidence, language candidate | `test_decode_body_charset_bom_default_and_replacement`, `test_normalize_text_and_title_whitespace_and_unicode`, `test_normalize_timestamp_precision_and_confidence`, `test_normalize_language_candidate` |
| Gói tuân thủ schema validator A-02 và chỉ chứa các trường trong binding `CollectedDocumentPackage` | `test_package_passes_a02_validator_with_binding_fields_only`, `test_package_fields_from_observation_and_context`, `test_raw_snapshot_ref_is_carried_from_context` |
| Gói không chứa trường quyết định của Phân hệ B (`disposition`, `article_id`, v.v. - A-RULE-011) | `test_package_has_no_b_decision_fields` |
| Content fingerprint gồm sha256 của text chuẩn hoá, không đổi khi chỉ đổi title; text rỗng không có text sha256 | `test_content_fingerprint_is_sha256_of_normalized_text_not_title`, `test_empty_text_has_no_text_fingerprint_and_is_partial` |
| Media discoveries có locator, vai trò, context, provenance độc lập (A-RULE-010); media thiếu locator bị loại kèm warning | `test_media_discoveries_have_locator_role_context_and_provenance`, `test_media_without_locator_is_dropped_with_warning` |
| Nội dung đổi khi fetch lại tạo package id và fingerprint mới; quan sát giống nhau có tính tất định | `test_refetch_with_changed_content_creates_new_package_and_fingerprint`, `test_same_observation_rebuild_is_deterministic` |
| Chuẩn hoá encoding và HTML hỏng vẫn dựng được package hợp lệ qua validator | `test_encoding_is_normalized_in_package`, `test_malformed_html_package_still_validates` |
| Extractor lỗi ném ngoại lệ được bắt thành disposition FAILED | `test_extractor_failure_yields_failed_disposition` |
| Layer 2 validator A-02 đánh giá tính đủ điều kiện nội dung | `test_extraction_policy_layer_two_sets_content_eligibility` |
| PackageContext từ chối các giá trị không hợp lệ | `test_package_context_rejects_invalid_values` |
| Cổng validator A-02 luôn thực thi và ném `PackageValidationError` khi gói sai quy cách | `test_validator_gate_rejects_invalid_package` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider` | 0 | 49 passed in 0.09s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.06s |
| 3 | `python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider` | 0 | 27 passed, 99 subtests passed in 0.05s |
| 4 | `git diff --check` | 0 | passed (clean, no output) |

## Quyết định mặc định (D8)

1. Extractor tham chiếu chỉ phục vụ fixture kiểm thử nội bộ, bộ trích xuất production (đề xuất `trafilatura==2.2.0`) chờ nghiệm thu tại `USER-CKPT-D9-D10` và `MODULE-A-OPEN-008`.
2. Thứ tự ưu tiên encoding: BOM > charset khai báo trong Content-Type HTTP header > mặc định utf-8; không quét dò thẻ meta charset; các byte không giải mã được thay bằng ký tự U+FFFD kèm cảnh báo `encoding_replacement_applied`.
3. Chuẩn hoá văn bản và khoảng trắng: chuẩn hoá dạng Unicode NFC, gộp các khoảng trắng liên tiếp trong từng dòng, loại bỏ các dòng trắng rỗng; trong HTML chỉ bỏ qua hoàn toàn nội dung các thẻ `script`, `style`, `noscript`, `template`.
4. Định dạng timestamp UTC chuẩn ISO 8601/RFC 3339 dạng `Z` chính xác tới giây, phân cấp precision `second` hoặc `day`, mức độ tin cậy confidence `high` (khi có thông tin múi giờ tường minh) hoặc `low` (khi giả định UTC hoặc chỉ có ngày).
5. Ngôn ngữ chỉ thu thập từ khai báo (`<html lang>` ưu tiên hơn `<meta http-equiv="content-language">`), confidence `declared`, không tự ý đoán nhận diện ngôn ngữ.
6. `content_fingerprints` gồm `normalized_text_sha256` (loại bỏ nếu văn bản chính rỗng) và `raw_body_sha256`; tuyệt đối không tính title vào fingerprint văn bản.
7. `collected_document_id` tạo bằng uuid5 từ namespace cố định kết hợp chuỗi phân tách các trường quan sát (`source_id`, `source_revision`, `collection_run_id`, `requested_locator`, `final_locator`, `fetched_at`, `raw_sha`); cùng quan sát cho ra cùng id, quan sát mới sinh id mới.
8. `extraction_disposition` nhận các giá trị chuỗi tự do `SUCCESS`, `PARTIAL`, `FAILED` theo quy định của IMPL-PLAN-A §2(c).
9. Phân loại media trích xuất: `og:image` là `hero` image; thẻ `img` là `inline` image; thẻ `video` và thẻ `source` lồng trong video là `embedded` video; thẻ `iframe` là `embedded` embed; chỉ chấp nhận URL tuyệt đối có scheme `http` hoặc `https`, URL dạng `data:` bị loại kèm cảnh báo `media_locator_skipped`; kiểm tra SSRF được thực hiện khi tải ở bước sau (A-04/A-12).
10. Layer 2 của A-02 luôn được kích hoạt kiểm tra; nếu thiếu chính sách trích xuất thì ghi nhận cảnh báo `content_eligibility_not_assessed:missing_extraction_policy`, không tự ý gán trường `content_eligibility`.

## Mục mở / follow-up

- Phiên bản News Corpus gắn kết theo CONV-A-08.
- Quy trình bàn giao media CT-MED-001 gắn kết theo CONV-A-07.
- Thu thập mở rộng `og:locale` và meta charset dự kiến bổ sung khi có quyết định chính thức tại bước tiếp theo.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- MODULE-A-OPEN-008

## Giới hạn

- Không chạy full test suite, `tests/m1` hay `tests/m2`.
- Không thay đổi `pyproject.toml`, `uv.lock` hay cài đặt thêm thư viện ngoài stdlib.
- Không thực hiện bất kỳ cuộc gọi mạng hay DNS thật nào; toàn bộ kiểm thử đơn vị được bảo vệ bằng fixture cô lập mạng.
