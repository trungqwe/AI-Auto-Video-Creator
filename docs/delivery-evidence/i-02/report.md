# Báo cáo bằng chứng I-02

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 8a56becbaf7a1814b73fc5d2886b390f6c17c45b
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-02 trong docs/implementation/i/slices.md, binding docs/parallel-delivery/bindings/i-artifact-version.json và fixture 	ests/fixtures/contracts/i-artifact-version/payloads.json của I-01.

## RED

- Lệnh thực thi: python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider (chạy với stub ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 23 failed, 1 passed in 0.19s
- Danh sách test FAILED kèm thông điệp NotImplementedError nguyên văn từ bước 5:
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_first_declare_creates_new_artifact_and_version: NotImplementedError: I-02 declare is not implemented
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_same_bytes_twice_keeps_one_version: NotImplementedError: I-02 declare is not implemented
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_different_bytes_add_second_version_and_keep_first_unchanged: NotImplementedError: I-02 declare is not implemented
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_other_owner_or_kind_gets_new_artifact_id[owner_resource_ref-00000000-0000-4000-8000-0000000000aa]: NotImplementedError: I-02 declare is not implemented
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_other_owner_or_kind_gets_new_artifact_id[artifact_kind-video]: NotImplementedError: I-02 declare is not implemented
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_unknown_fields_ignored_and_payload_not_mutated: NotImplementedError: I-02 declare is not implemented
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_invalid_fixture_payload_raises_value_error_with_code_and_field[content_hash_uppercase]: NotImplementedError: I-02 declare is not implemented
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_invalid_fixture_payload_raises_value_error_with_code_and_field[missing_retention_class]: NotImplementedError: I-02 declare is not implemented
  - 10 test missing_each_field (artifact_kind, owner_resource_ref, content_sha256, size_bytes, media_type, lineage_refs, retention_class, sensitivity_class, intended_storage_class, producer_operation_ref): đều thất bại với NotImplementedError: I-02 declare is not implemented
  - FAILED tests/unit/storage/test_storage_declare_version.py::test_wrong_type_raises_with_field: NotImplementedError: I-02 declare is not implemented
  - 4 test non_dict_payload_raises_wrong_type_payload (None, [], x, 5): đều thất bại với NotImplementedError: I-02 declare is not implemented
- Xác nhận: Toàn bộ 23 lỗi FAILED đều là NotImplementedError từ stub; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection (test test_port_and_service_expose_no_overwrite_api PASS).

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 24 passed in 0.04s

## Thay đổi

- src/controlplane/application/storage_meta/declare_version.py: Định nghĩa ArtifactVersionRef (frozen dataclass gồm rtifact_id, rtifact_version_id), ArtifactVersionCatalogPort (Protocol gồm 3 phương thức ind_matching, ind_artifact_id, insert_version), DeclareRequestInvalidError (kế thừa ValueError, chứa .code và .field), và DeclareArtifactVersionService với phương thức declare(payload: dict). Triển khai validate payload qua alidate_declare_request của I-01 và raise DeclareRequestInvalidError mang mã lỗi và trường lỗi đầu tiên; lọc dữ liệu payload theo ields(DeclareArtifactVersionRequest) (bỏ qua trường lạ và không làm biến đổi payload đầu vào); kiểm tra version trùng thông qua ind_matching(owner_resource_ref, artifact_kind, content_sha256), nếu trùng trả về DeclareArtifactVersionResult với matched_existing=True, policy_decision="matched_existing" và không gọi insert_version; nếu không trùng tìm rtifact_id qua ind_artifact_id, tái sử dụng rtifact_id đã có hoặc tạo id mới qua id_factory, sinh rtifact_version_id, gọi insert_version và trả về kết quả với matched_existing=False, policy_decision="new_version", equired_operation="upload". Không cung cấp bất kỳ phương thức update/overwrite/replace/delete nào.
- 	ests/unit/storage/test_storage_declare_version.py: Định nghĩa test fake in-memory FakeCatalog triển khai ArtifactVersionCatalogPort (với assertion loại trừ duplicate insert bảo đảm tính bất biến). Bao phủ 24 test cases gồm: tạo artifact/version đầu tiên, gọi cùng byte 2 lần giữ nguyên 1 version (matched_existing=True, không gọi insert lần 2), gọi byte khác thêm version thứ 2 giữ artifact_id và không đổi version cũ, khác owner hoặc kind tạo artifact_id mới, bỏ qua trường lạ và không làm biến đổi payload gốc, các trường hợp invalid fixture raise ValueError đúng code/field, missing từng trường bắt buộc, sai kiểu trường size_bytes, payload không phải dict, và xác nhận CatalogPort và Service không lộ bất kỳ API overwrite nào.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider | 0 | 24 passed in 0.04s |
| 2 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 3 | python -c "import pathlib; fs=['src/controlplane/application/storage_meta/declare_version.py','tests/unit/storage/test_storage_declare_version.py','docs/delivery-evidence/i-02/report.md']; data={f: pathlib.Path(f).read_bytes() for f in fs}; bad=[(f,i) for f in fs for i,l in enumerate(data[f].decode('utf-8').split('\n'),1) if l.rstrip('\r')!=l.rstrip()]; assert not bad, bad; assert all(d.endswith(b'\n') and not d.startswith(b'\xef\xbb\xbf') for d in data.values()); print('OK')" | 0 | OK (UTF-8 không BOM, không trailing whitespace, kết thúc LF) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH 1: insert_version(artifact_id, artifact_version_id, request) trả None, id sinh bằng uuid4 qua id_factory tiêm được.
2. GIẢ ĐỊNH 2: lỗi validate chỉ raise lỗi đầu tiên theo thứ tự binding.
3. GIẢ ĐỊNH 3: kết quả matched_existing để equired_operation=None (trường optional).
4. GIẢ ĐỊNH 4: không có API update/overwrite nào được cung cấp trên port hay service.
5. GIẢ ĐỊNH 5: không kiểm UUID/enum vì binding khai kiểu string.

## Danh sách chờ user (pendingUserCheckpoint)

Không phát sinh mục mới; không mục nào được coi là đã duyệt.

## Giới hạn

- Không chạy full suite; không chạm tests/m1, tests/m2.
- Không sửa src/controlplane/application/storage_meta/__init__.py, không sửa domain, binding, fixture, pyproject.toml hay lockfile.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib (uuid, dataclasses, 	yping).
- Không gọi dịch vụ thật, không đọc secrets hay credentials.
- Không tạo conftest.py hay __init__.py trong tests/.
- Không commit secret, token, credential hay dữ liệu cá nhân.
