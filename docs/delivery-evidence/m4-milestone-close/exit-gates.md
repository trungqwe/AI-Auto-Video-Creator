# M4-MILESTONE-CLOSE-R4: đối chiếu exit gate Milestone M4 (revision 4)

Đối chiếu sáu exit gate của Milestone M4 theo tài liệu chuẩn `docs/11-roadmap.md` mục 10, phần `### Exit gate` (dòng 409-416).

| Mã gate | Nội dung theo roadmap | Trạng thái | Bằng chứng |
| --- | --- | --- | --- |
| M4-EG1 | Không location nào thành verified nếu chưa có integrity evidence. | PASS | Lệnh STT 220 (`tests/unit/storage/test_storage_verification.py`, exit 0; dòng 60-62 `test_upload_response_without_hash_is_never_verified`: `observed_sha256=None` cho kết quả `State.OUTCOME_UNKNOWN`; dòng 82-88 `test_recovery_edges_to_verified_are_forbidden`), STT 221 (`tests/unit/storage/test_storage_cloud_persist.py`, exit 0; dòng 209 `test_lookup_without_hash_is_not_verified`, dòng 220 `test_only_verified_observation_carries_evidence`), STT 263 (`tests/integration/persistence/i/test_persist_i_postgres.py`, exit 0). |
| M4-EG2 | Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified. | PASS | Lệnh STT 225 (`tests/unit/storage/test_storage_cleanup_evaluation.py`, exit 0; dòng 46-48 bảng quyết định: retention `output`, `original`, `reusable` với `cloud_copy_verified=False` đều trả `forbidden` kèm mã `DURABLE_COPY_NOT_VERIFIED`, hằng `DURABLE` ở dòng 26), STT 226 (`tests/integration/storage/test_storage_cleanup_executor.py`, exit 0). |
| M4-EG3 | Render tương lai chỉ có thể lấy artifact local đã verify. | PASS | Lệnh STT 172 (`tests/unit/render/test_f07_preconditions_artifacts_language.py`, exit 0; dòng 66 `test_all_verified_has_no_finding`, dòng 71 `test_state_other_than_verified_is_not_verified` trả Finding `ARTIFACT_NOT_VERIFIED` ở dòng 73, 77, 82), STT 224 (`tests/unit/storage/test_storage_materialization.py`, exit 0; dòng 152 `test_verified_matching_location_is_released`, dòng 159 `test_every_non_verified_state_is_rejected`), STT 81 (`tests/unit/catalog/test_catalog_renderable.py`, exit 0). |
| M4-EG4 | UI phân biệt original, processed, uncertain, failed và unavailable. | PASS | Lệnh STT 212 (`tests/unit/control_ui/test_h_status_presentation.py`, exit 0; dòng 37-43 `EXPECTED_ARTIFACT` có đủ 5 trạng thái `original`, `processed`, `uncertain`, `failed`, `unavailable` với nhãn Bản gốc, Đã xử lý, Chưa chắc chắn, Lỗi, Không khả dụng; dòng 132 `test_artifact_availability_five_states`), STT 213 (`tests/unit/control_ui/test_h_status_pill.py`, exit 0), STT 97 (probe `screenRegistry.ts` đủ 18 màn hình với `backendStatus`, exit 0). |
| M4-EG5 | Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật. | PENDING_USER | Cần tài khoản Google Drive thật và phiên xác thực OAuth một lần của người dùng tại gói CP7. Ở thời điểm kiểm định M4, hệ thống đang vận hành hoàn toàn trên fixture và dịch vụ giả lập (fake/fixture theo CP1), tuân thủ nghiêm ngặt nguyên tắc D5. |
| M4-EG6 | User duyệt C-I và `R2 Media Alpha`. | PENDING_USER | Cần checkpoint phê duyệt chính thức từ người dùng đối với Phân hệ C-I và thiết lập `R2 Media Alpha`. Chưa có biên bản checkpoint này trong các quyết định hiện hành. |

## Mục mở của roadmap (không phải exit gate)

Căn cứ tài liệu `docs/parallel-delivery/M4-CI-execution-package.md` mục 6, các hạng mục dưới đây là open decision items kỹ thuật, không phải exit gate của milestone và tuyệt đối KHÔNG được ghi vào `pendingUserCheckpoint`:

- `ROADMAP-OPEN-010`: Chính sách retention và storage placement cho 4 tài khoản Drive (phân bổ quota và lưu trữ theo CT-STO-010, hạn chốt trước khi kích hoạt unattended cleanup).
- `QUALITY-OPEN-004`: Cơ chế checksum và integrity verification cụ thể trên Google Drive (xác thực mã băm tệp trên cloud theo Gate G04, hạn chốt trước khi nghiệm thu Gate G04 trên tài khoản thật).
- `QUALITY-OPEN-006`: Ngưỡng working set và disk buffer cho desktop materialization (giới hạn dung lượng staging cục bộ 5 video, hạn chốt trước khi nghiệm thu gate hiệu năng render).
- `POLICY-CAT-001`: Trọng số thành phần tính điểm lựa chọn media candidate (`QueryMediaCandidates` CT-MED-005, cung cấp qua `ConfigRevision` từ Phân hệ J, không hardcode).

## Ghi chú theo quyết định của user (2026-10-22)

Exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú trong báo cáo đóng mốc, không phải FAIL và không hỏi user (quyết định của user, ghi trong sổ quyết định của user, 2026-10-22, ai-setup decide). Sáu exit gate M4-EG1..M4-EG6 trong docs/11-roadmap.md mục 10 đã được đối chiếu ở trên: M4-EG1..M4-EG4 PASS bằng test chạy lại trên candidate 3497cecbf9fe9a09818192e9c7c12c0c68396c01 (HEAD của worktree revision 4); M4-EG5 và M4-EG6 ghi PENDING_USER vì cần tài khoản Drive thật (CP7) và checkpoint duyệt của user; không gate nào khác được ghi vào pendingUserCheckpoint.
