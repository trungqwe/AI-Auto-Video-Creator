# Báo cáo bằng chứng B-4

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `91878d46206a05e052217b54e81af614b6ba1bf7`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS, slice B-4 trong docs/implementation/b/slices.md, D3 user duyệt Phần B ngày 18/10/2026.
- Binding refs: `docs/parallel-delivery/bindings/domain-event-envelope.json` 1.0.0 và `tests/fixtures/contracts/domain-event-envelope/payloads.json`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `62 failed, 2 passed in 0.33s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_domain_events.py::test_event_names_are_exactly_module_b_catalog`: `AssertionError: assert frozenset() == frozenset({'A...ateAccepted'})`
  - `FAILED tests/unit/ingestion/test_ingestion_domain_events.py::test_output_has_binding_required_fields_with_binding_types[ArticleRevisionAccepted]`: `AssertionError: assert set() == {'aggregate_i...payload', ...}`
  - `FAILED tests/unit/ingestion/test_ingestion_domain_events.py::test_unknown_event_name_is_rejected[ArticleIngested]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/ingestion/test_ingestion_domain_events.py::test_payload_token_key_is_rejected_by_contract_guard[token]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/ingestion/test_ingestion_domain_events.py::test_payload_article_text_key_is_rejected[normalized_text]`: `Failed: DID NOT RAISE ValueError`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; 2 test PASS là `test_missing_recovery_epoch_argument_is_rejected` và `test_events_module_reuses_contract_guard_without_src_prefix`.

## Thay đổi

- `src/ingestion/domain/events.py`: Module xây dựng domain event của Phân hệ B tuân thủ BINDING-DOMAIN-EVENT-ENVELOPE 1.0.0:
  - `EVENT_NAMES`: frozenset gồm 4 sự kiện: `ArticleRevisionAccepted`, `DuplicateDocumentResolved`, `EventLinkResolved`, `EventUpdateAccepted`.
  - `AGGREGATE_TYPES`: frozenset gồm 5 aggregate: `Article`, `ArticleRevision`, `CollectedDocumentResolution`, `Event`, `EventUpdate`.
  - Hằng số binding: `PRODUCER = 'B'`, `SCHEMA_VERSION = '1.0.0'`, `SENSITIVITY = 'internal'`, `MAX_VALUE_LENGTH = 256`.
  - `_require_token`: Hàm kiểm tra chuỗi token không khoảng trắng độ dài 1..256.
  - `_payload_scalar`: Hàm xác thực giá trị scalar chỉ nhận int >= 0 hoặc chuỗi token 1..256.
  - `_payload_value`: Hàm xử lý giá trị payload dạng scalar hoặc list các giá trị scalar.
  - `build_event`: Hàm dựng domain event envelope với 10 trường theo schema binding, xác thực chặt chẽ đầu vào, gọi `ensure_safe_event_payload` và lọc khóa theo allow-list id/revision/ref (CT-EVT-002, CT-EVT-003).
- `tests/unit/ingestion/test_ingestion_domain_events.py`: Bộ kiểm thử đơn vị gồm 64 test cases:
  - `test_event_names_are_exactly_module_b_catalog`: Kiểm tra danh mục sự kiện khớp chính xác 4 event của Phân hệ B.
  - `test_aggregate_types_are_module_b_aggregates`: Kiểm tra 5 aggregate type của Phân hệ B.
  - `test_output_has_binding_required_fields_with_binding_types`: Kiểm tra output có đủ trường required và đúng kiểu theo binding cho cả 4 event.
  - `test_output_keys_match_fixture_valid_event`: Đối chiếu các khóa output với payload hợp lệ trong fixture chuẩn.
  - `test_output_has_no_binding_forbidden_field`: Đảm bảo output và payload không chứa bất kỳ forbidden_field nào của binding.
  - `test_forbidden_field_in_payload_is_rejected`: Kiểm tra từ chối khi payload chứa trường cấm của binding.
  - `test_unknown_event_name_is_rejected`: Ném ValueError với các tên sự kiện không thuộc Phân hệ B hoặc không hợp lệ.
  - `test_payload_token_key_is_rejected_by_contract_guard`: Ném ValueError khi payload chứa khóa token do ensure_safe_event_payload bảo vệ.
  - `test_payload_article_text_key_is_rejected`: Ném ValueError khi payload chứa khóa văn bản bài như normalized_text, title, body, raw_html, extracted_content_candidate.
  - `test_payload_article_text_value_is_rejected`: Ném ValueError khi giá trị chứa văn bản dài, khoảng trắng hoặc chuỗi rỗng.
  - `test_payload_canary_secret_value_is_rejected`: Ném ValueError khi giá trị chứa canary secret do contract guard phát hiện.
  - `test_payload_value_outside_id_revision_ref_is_rejected`: Ném ValueError khi giá trị không thuộc kiểu id/revision/ref (None, dict lồng, bool, float, bytes, số âm).
  - `test_payload_must_be_non_empty_mapping`: Bắt buộc payload phải là mapping không rỗng.
  - `test_invalid_recovery_epoch_is_rejected`: Ném ValueError khi recovery_epoch không phải chuỗi không khoảng trắng hợp lệ.
  - `test_missing_recovery_epoch_argument_is_rejected`: Ném TypeError khi thiếu tham số recovery_epoch.
  - `test_invalid_envelope_argument_is_rejected`: Ném ValueError khi các tham số envelope (event_id, aggregate_id, aggregate_revision, aggregate_type) không hợp lệ.
  - `test_build_event_calls_contract_payload_guard`: Spy test xác nhận build_event gọi ensure_safe_event_payload với payload truyền vào.
  - `test_events_module_reuses_contract_guard_without_src_prefix`: Xác nhận import ensure_safe_event_payload không có tiền tố src. và không import thư viện mạng.
  - `test_payload_is_copied_not_aliased`: Đảm bảo payload trong event được copy an toàn, không bị biến đổi ngoài ý muốn (aliasing).
  - `test_duplicate_document_resolved_carries_new_media_discovery_refs`: Xác nhận sự kiện DuplicateDocumentResolved mang đúng payload chứa new_media_discovery_refs.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider` | 0 | 64 passed in 0.06s |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.04s |
| 3 | `git diff --check` | 0 | không output |

## Quyết định mặc định (D8)

1. Khóa payload theo allow-list snake_case kết thúc bằng id/ids/revision/revisions/ref/refs, mọi khóa khác như normalized_text, title, body bị từ chối, hiện thực CT-EVT-003.
2. Giá trị payload chỉ là chuỗi không khoảng trắng dài 1..256, số nguyên >= 0, hoặc list các giá trị đó; không dict lồng, None, bool, float, bytes.
3. ensure_safe_event_payload được gọi trên bản sao dict của payload trước allow-list.
4. event_id, aggregate_id, recovery_epoch là chuỗi không khoảng trắng 1..256, recovery_epoch kiểu string theo binding.
5. aggregate_revision số nguyên >= 1 (revision sau commit, CT-EVT-002).
6. aggregate_type giới hạn 5 aggregate B sở hữu theo plan §4.
7. Output là dict đúng 10 trường binding, chuyển sang dataclass DomainEvent (schema_version int, recovery_epoch int|None) khi nối outbox thuộc REQ-B-CONV-07, không làm ở slice này.
8. Không thêm thư viện, chỉ dùng stdlib (re, collections.abc, typing).

## Mục mở

- Nếu B-7/B-8 cần mang khóa ngoài allow-list (ví dụ disposition của EventLinkResolved) thì đề xuất mở rộng qua slice riêng, không tự nới allow-list.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- EG-M3-7

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa pyproject.toml, uv.lock, binding, fixture, src/controlplane.
- Không gọi dịch vụ thật hay đọc bí mật.
- Không sửa HANDOFF.md, README.md, CHANGELOG.md hay checklist ngoài owned paths.
