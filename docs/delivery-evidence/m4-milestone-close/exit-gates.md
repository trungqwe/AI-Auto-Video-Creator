# M4-MILESTONE-CLOSE: đối chiếu exit gate Milestone M4 (revision 1)

Đối chiếu sáu exit gate của Milestone M4 theo tài liệu chuẩn `docs/11-roadmap.md` mục 10, phần `### Exit gate` (dòng 409-416).

| Mã gate | Nội dung theo roadmap | Trạng thái | Bằng chứng |
| --- | --- | --- | --- |
| M4-EG1 | Không location nào thành verified nếu chưa có integrity evidence. | PASS | Lệnh STT 223 (`tests/unit/storage/test_storage_verification.py`, exit 0, lines 53-63 `test_upload_response_without_hash_is_never_verified`, lines 82-86 `test_recovery_edges_to_verified_are_forbidden`), STT 224 (`tests/unit/storage/test_storage_cloud_persist.py`, exit 0, lines 209-242 `test_lookup_without_hash_is_not_verified`, `test_only_verified_observation_carries_evidence`), STT 265 (`tests/integration/persistence/i/test_persist_i_postgres.py`, exit 0). |
| M4-EG2 | Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified. | PASS | Lệnh STT 228 (`tests/unit/storage/test_storage_cleanup_evaluation.py`, exit 0, lines 46-50 kiểm tra bảng quyết định: retention `output`, `original`, `reusable` khi `cloud_copy_verified=False` đều trả về `forbidden` kèm mã vi phạm `DURABLE`), STT 229 (`tests/integration/storage/test_storage_cleanup_executor.py`, exit 0). |
| M4-EG3 | Render tương lai chỉ có thể lấy artifact local đã verify. | PASS | Lệnh STT 175 (`tests/unit/render/test_f07_preconditions_artifacts_language.py`, exit 0, lines 66-75, 103-107 `test_all_verified_has_no_finding`, `test_state_other_than_verified_is_not_verified` trả về finding `ARTIFACT_NOT_VERIFIED`), STT 227 (`tests/unit/storage/test_storage_materialization.py`, exit 0, lines 152-165, 183-190 `test_verified_matching_location_is_released`, `test_every_non_verified_state_is_rejected`), STT 89 (`tests/unit/catalog/test_catalog_renderable.py`, exit 0). |
| M4-EG4 | UI phân biệt original, processed, uncertain, failed và unavailable. | PASS | Lệnh STT 215 (`tests/unit/control_ui/test_h_status_presentation.py::test_artifact_availability_five_states`, exit 0, lines 38-44 `EXPECTED_ARTIFACT` định nghĩa đủ 5 trạng thái với nhãn tiếng Việt có dấu `Bản gốc`, `Đã xử lý`, `Chưa chắc chắn`, `Lỗi`, `Không khả dụng`), STT 216 (`tests/unit/control_ui/test_h_status_pill.py`, exit 0), STT 105 (probe `screenRegistry.ts` định nghĩa đủ 18 screens với `backendStatus`, exit 0). |
| M4-EG5 | Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật. | PENDING_USER | Cần tài khoản Google Drive thật và phiên xác thực OAuth một lần của người dùng tại gói CP7. Ở thời điểm kiểm định M4, hệ thống đang vận hành hoàn toàn trên fixture và dịch vụ giả lập (fake/fixture theo CP1), tuân thủ nghiêm ngặt nguyên tắc D5. |
| M4-EG6 | User duyệt C-I và `R2 Media Alpha`. | PENDING_USER | Cần checkpoint phê duyệt chính thức từ người dùng đối với Phân hệ C-I và thiết lập `R2 Media Alpha`. Chưa có biên bản checkpoint này trong các quyết định hiện hành. |

## Mục mở của roadmap (không phải exit gate)

Căn cứ tài liệu `docs/parallel-delivery/M4-CI-execution-package.md` mục 6, các hạng mục dưới đây là open decision items kỹ thuật, không phải exit gate của milestone và tuyệt đối KHÔNG được ghi vào `pendingUserCheckpoint`:

- `ROADMAP-OPEN-010`: Chính sách retention và storage placement cho 4 tài khoản Drive (phân bổ quota và lưu trữ theo CT-STO-010, hạn chốt trước khi kích hoạt unattended cleanup).
- `QUALITY-OPEN-004`: Cơ chế checksum và integrity verification cụ thể trên Google Drive (xác thực mã băm tệp trên cloud theo Gate G04, hạn chốt trước khi nghiệm thu Gate G04 trên tài khoản thật).
- `QUALITY-OPEN-006`: Ngưỡng working set và disk buffer cho desktop materialization (giới hạn dung lượng staging cục bộ 5 video, hạn chốt trước khi nghiệm thu gate hiệu năng render).
- `POLICY-CAT-001`: Trọng số thành phần tính điểm lựa chọn media candidate (`QueryMediaCandidates` CT-MED-005, cung cấp qua `ConfigRevision` từ Phân hệ J, không hardcode).
