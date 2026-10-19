# Báo cáo bằng chứng B-9

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `8a56becbaf7a1814b73fc5d2886b390f6c17c45b`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-9 trong `docs/implementation/b/slices.md`; D3 user duyệt Phần B ngày 18/10/2026; Contract CT-AI-001 (binding `docs/parallel-delivery/bindings/b-d-production-snapshot.json`).

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider` (chạy trên skeleton của `source_set.py`)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `33 failed, 6 passed in 0.34s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_source_set.py::test_source_set_fields_match_binding_names_and_types - AssertionError: assert (True and ())`
  - `FAILED tests/unit/ingestion/test_ingestion_source_set.py::test_single_article_pins_latest_revision_as_representative - AssertionError: assert [] == [{'article_id...revision': 4}]`
  - `FAILED tests/unit/ingestion/test_ingestion_source_set.py::test_single_article_without_revision_is_rejected - Failed: DID NOT RAISE SourceSetRejected`
  - `FAILED tests/unit/ingestion/test_ingestion_source_set.py::test_multi_article_event_needs_two_linked_articles[one_member] - Failed: DID NOT RAISE SourceSetRejected`
  - `FAILED tests/unit/ingestion/test_ingestion_source_set.py::test_from_then_to_now_without_update_is_rejected - Failed: DID NOT RAISE SourceSetRejected`
  - `FAILED tests/unit/ingestion/test_ingestion_source_set.py::test_invalid_production_mode_raises_value_error[timeline] - Failed: DID NOT RAISE ValueError`
- Xác nhận: Hoàn toàn không có `ImportError`, `ModuleNotFoundError` hay lỗi collection; 6 test PASS trên skeleton là `test_production_modes_match_binding_enum`, `test_rejection_is_not_a_value_error_and_carries_reason`, `test_boundary_regex_detects_forbidden_imports`, `test_source_set_source_has_no_write_calls_or_forbidden_imports` cùng các kiểm thử độc lập khác; 33 test còn lại FAILED do `AssertionError` hoặc `Failed: DID NOT RAISE`.

## Thay đổi

- `src/ingestion/application/source_set.py`:
  - Hằng số: `SINGLE_ARTICLE`, `MULTI_ARTICLE_EVENT`, `FROM_THEN_TO_NOW`, `PRODUCTION_MODES`, `SOURCE_REF_FIELDS`, `REASON_SINGLE_ELIGIBLE`, `REASON_MULTI_ELIGIBLE`, `REASON_TIMELINE_ELIGIBLE`, `REASON_NO_REPRESENTATIVE`, `REASON_NOT_ENOUGH_LINKED`, `REASON_UPDATE_NOT_ACCEPTED`.
  - Ngoại lệ: `SourceSetRejected(reason)` kế thừa `Exception`, lưu `self.reason` phục vụ phản hồi lỗi từ chối điều kiện nghiệp vụ dạng mã máy ổn định.
  - Dataclass: `SourceSet` (frozen, kw_only) gồm `production_mode`, `source_refs`, `source_set_fingerprint`, `eligibility_reason`.
  - Helper private: `_require_text`, `_load_revision`, `_source_ref`, `_sorted_refs`, `_event`, `_member_pairs`, `_pinned`, `_single_article`, `_multi_article_event`, `_from_then_to_now`, cùng mapping `_BUILDERS`.
  - Hàm tính fingerprint: `fingerprint_source_refs(refs)` tính SHA-256 hex từ JSON chuẩn hóa các ref đã sắp xếp theo `(article_id, article_revision_id)`.
  - Hàm nghiệp vụ chính: `build_source_set(production_mode, subject_id, uow)` trả về `SourceSet` ghim chính xác các revision, chỉ đọc, không mở ngữ cảnh transaction và không lưu bản ghi nào.
- `tests/unit/ingestion/test_ingestion_source_set.py`:
  - 39 test items bao quát toàn diện các yêu cầu CT-AI-001, TST-INT-INV-004, TST-CTR-INV-006, kiểm tra khớp binding `b-d-production-snapshot.json`, tính bất biến của bộ source refs khi có revision mới, tính độc lập thứ tự của fingerprint, kiểm soát fail-closed khi thiếu update hợp lệ hoặc không đủ 2 bài liên kết, và ranh giới import CHECK-B.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider` | 0 | 39 passed in 0.08s |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.07s |

## Quyết định mặc định (D8)

(Ghi nhận dưới dạng GIẢ ĐỊNH theo quy chế D8, chưa duyệt chính thức):
1. `subject_id` là `article_id` với chế độ `single_article`, và là `event_id` với hai chế độ sự kiện (`multi_article_event`, `from_then_to_now`).
2. Revision đại diện của `single_article` là revision có `revision_number` lớn nhất (`Article.latest_revision`), không dùng `representative_source_id`.
3. Chế độ `multi_article_event` yêu cầu event có `member_refs` thuộc ít nhất 2 `article_id` khác nhau (`member_refs` của module B chỉ chứa bài seed và bài LINKED).
4. Chế độ `from_then_to_now` cần ít nhất một bản ghi kind `event_update` có `event_id` khớp và state `ACCEPTED_NEW_DEVELOPMENT`, refs = `member_refs` của event cộng revision của các update đó, loại trùng.
5. Từ chối bằng `SourceSetRejected(reason)` với các reason chuẩn: `event_update_not_accepted`, `event_needs_two_linked_articles`, `no_representative_revision`; subject/ref không tồn tại ném `LookupError`; tham số sai kiểu hoặc rỗng ném `ValueError`.
6. `source_refs` gồm 4 trường `article_id`, `article_revision_id`, `source_id`, `source_revision` (`str`, `str`, `str`, `int`) theo tiêu chí nghiệm thu; binding chỉ khai tổng quát `items: object`.
7. `source_set_fingerprint` là SHA-256 hex của chuỗi JSON canonical (`json.dumps(refs_sorted, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`) mã hóa UTF-8.
8. `eligibility_reason` hợp lệ gồm: `single_article_eligible`, `multi_article_event_eligible`, `from_then_to_now_eligible`.
9. Hàm `build_source_set` hoàn toàn chỉ đọc, không mở transaction, không gọi `save`, `put`, `commit`, `rollback` hay `append_event`.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).
- Adapter PostgreSQL qua REQ-B-CONV-02.

## Giới hạn

- Không chạy full suite, không chạy `tests/m1`, `tests/m2`.
- Không sửa tệp ngoài 3 owned paths: `src/ingestion/application/source_set.py`, `tests/unit/ingestion/test_ingestion_source_set.py`, `docs/delivery-evidence/b-9/report.md`.
- Không gọi dịch vụ thật hay đọc bí mật.
