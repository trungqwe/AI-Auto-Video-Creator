# Báo cáo bằng chứng F-04

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `5795450216f7b989a15d6b4c3db78276b594f113`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-04 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider` (chạy trên stub chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `48 failed, 10 passed in 0.48s`
- Chi tiết các dòng FAILED tiêu biểu từ bước 6:
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_fingerprint_is_request_hash_of_every_field_except_the_two_excluded`: `AssertionError: assert '44136fa355b3...060f61caaff8a' == '9716be5a47d4...4989f2b6a3ec9'`
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_hashed_basis_covers_all_record_fields_but_two`: `AssertionError: assert set() == {'allowed_fal...ix_plan', ...}`
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_changing_any_hashed_field_changes_fingerprint[production_snapshot_ref]`: `AssertionError: assert '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a' != '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'`
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_changing_input_artifact_field_changes_fingerprint[sha256-cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc]`: `AssertionError: assert '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a' != '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'`
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_timeline_segment_order_changes_fingerprint`: `AssertionError: assert '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a' != '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'`
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_verify_rejects_wrong_stored_fingerprint`: `Failed: DID NOT RAISE PackageFingerprintError`
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_compute_and_verify_reject_non_record[None]`: `Failed: DID NOT RAISE PackageFingerprintError`
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_compute_rejects_malformed_collections`: `Failed: DID NOT RAISE PackageFingerprintError`
  - `FAILED tests/unit/render/test_f04_package_fingerprint.py::test_compute_rejects_values_the_canonicalizer_refuses`: `Failed: DID NOT RAISE PackageFingerprintError`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. Tất cả 48 test thất bại đều là `AssertionError` hoặc `DID NOT RAISE` do stub trả hash cố định rỗng và verify trả None.
- Danh sách 10 test đã PASS sẵn trên stub:
  - `test_fingerprint_is_deterministic_and_ignores_identity_fields`
  - `test_dict_key_order_does_not_change_fingerprint`
  - `test_input_artifacts_order_does_not_change_fingerprint`
  - `test_input_artifacts_with_same_version_id_are_ordered_deterministically`
  - `test_language_validation_refs_order_does_not_change_fingerprint`
  - `test_source_payload_mutation_after_resolve_does_not_change_fingerprint`
  - `test_verify_accepts_matching_fingerprint`
  - `test_sealed_record_cannot_be_edited_in_place`
  - `test_module_uses_shared_canonicalizer_and_pure_imports`
  - `test_module_declares_covered_ids`

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider` (chạy sau khi cài đặt mã thật ở bước 7)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `58 passed in 0.30s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/render/domain/package_fingerprint.py`: Cài đặt fingerprint bất biến CT-RND-002 gồm hàm `compute_package_fingerprint` tính request_hash trên 17 trường (loại trừ package_fingerprint và render_package_id), hàm `verify_package_fingerprint` kiểm tra khớp fingerprint, ngoại lệ `PackageFingerprintError` với mã lý do và tên trường tương ứng, xử lý sắp xếp input_artifacts và language_validation_refs ổn định, bảo toàn thứ tự timeline.segments và các danh sách khác, hỗ trợ giải đông mapping/tuple cho canonicalizer.
  - `tests/unit/render/test_f04_package_fingerprint.py`: Bộ kiểm thử toàn diện 58 test cases bao phủ băm request_hash trên 17 trường đã biết, tính xác định và bỏ qua identity fields, độ nhạy khi thay đổi bất kỳ trường nào trong 17 trường hoặc thuộc tính con của input_artifacts, tính bất biến trước thứ tự khóa dict và thứ tự input_artifacts/language_validation_refs, phát hiện thay đổi thứ tự timeline segments, xác thực đối tượng frozen, từ chối non-record hoặc collection dị dạng hoặc giá trị canonicalizer từ chối, và kiểm tra ranh giới import cùng coveredIds.
  - `docs/delivery-evidence/f-04/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider` | 0 | `58 passed in 0.30s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Trường băm lấy từ `dataclasses.fields(RenderPackageRecord)` trừ `package_fingerprint` và `render_package_id` nên trường mới tự được phủ.
2. `input_artifacts` sắp theo `(artifact_version_id, sha256, size_bytes, media_type)` để xác định cả khi trùng id.
3. `language_validation_refs` sắp theo chuỗi.
4. `timeline.segments`, `allowed_fallbacks` và mọi mảng khác giữ thứ tự.
5. Thứ tự khóa dict do JCS của `request_hash` chuẩn hóa.
6. Không-phải-record là `wrong_type/record`, giá trị canonicalizer từ chối là `invalid_value/package_fingerprint`.
7. `RenderPackageRecord` đã frozen từ F-03, F-04 chỉ kiểm bằng test, không sửa `package_contract.py`.
8. Test tự tính lại fingerprint, không đòi khớp giá trị CP1 đặt tay trong fixture.

## Ánh xạ phản ví dụ

- Hash input đổi mà fingerprint không đổi: `test_changing_any_hashed_field_changes_fingerprint` và `test_changing_input_artifact_field_changes_fingerprint`.
- Phụ thuộc thứ tự khóa dict: `test_dict_key_order_does_not_change_fingerprint`.
- Sửa tại chỗ sau resolve: `test_sealed_record_cannot_be_edited_in_place` và `test_verify_rejects_package_edited_after_sealing`.

## coveredIds

- `CT-RND-002`
- `acceptance §8 mục 1`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, package_contract.py.
- Chỉ stdlib và canonicalizer có sẵn.
- Không gọi dịch vụ thật.
