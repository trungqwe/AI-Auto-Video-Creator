# Báo cáo đóng M4 (revision 1)

## 1. Phạm vi và candidate

- **Mã nhiệm vụ (Task ID):** `M4-MILESTONE-CLOSE`
- **Candidate SHA kiểm định:** `5fd27218759bdfb463f9efc7af34caabd8debe13` (HEAD của worktree khi chạy lệnh kiểm; con trực tiếp của `cc290f002074514001fa0b03b3eb8c9e00c14db6`, commit integrate của ADAPT-LAUNCH)
- **Python interpreter đã khóa:** `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe` (Python 3.13.15, đồng bộ hoàn toàn với `tools/runtime/runtime.lock.json`)
- **Thời điểm thực thi:** Ngày 23/10/2026
- **Phạm vi kiểm tra:** Toàn bộ 288 lệnh kiểm bắt buộc của Milestone M4 theo 12 nhóm bước, 135 gói và cổng trong danh sách yêu cầu nghiệm thu (122 gói công việc và 13 cổng GATE-*) và 6 exit gate trong roadmap.

## 2. Kết luận

Kết luận kỹ thuật: KHÔNG ĐẠT

**Chi tiết đánh giá từng tiêu chí:**
- **Lệnh kiểm:** KHÔNG ĐẠT — 279/288 lệnh kiểm chạy lại trên candidate đạt exit code 0; 9 lệnh thất bại (STT 29, 30, 33, 39, 41, 44, 45, 46, 47 do 6 gói sửa lỗi chưa được tích hợp vào candidate 5fd27218759bdfb463f9efc7af34caabd8debe13).
- **Exit gate kỹ thuật:** ĐẠT — M4-EG1..M4-EG4 PASS, bằng chứng tại exit-gates.md.
- **Exit gate chờ người dùng:** ĐẠT quy chuẩn — M4-EG5 và M4-EG6 ghi PENDING_USER vì cần tài khoản Drive thật và checkpoint duyệt của user; không gate nào khác bị ghi pending.
- **Bao phủ gói:** KHÔNG ĐẠT — 129/135 gói và cổng có SHA tích hợp hoặc recordHash; M4-CI-PLAN ghi SHA `b18dbcff5e5beadb872b0d507b26cb88ffecf01e` do Control xác minh; 6 gói sửa lỗi mới (CP-4-WIRING-FIX2, ADAPT-PROD-FIX1, CP-4B-UI-SCREENS-FIX1, PERSIST-C-FIX1, ADAPT-PROD-FIX2, CP-4B-UI-SCREENS-FIX2) ghi nhận KHÔNG TÌM THẤY trên nhánh candidate.

## 3. Gói được bao phủ

- Tổng số gói trong danh sách yêu cầu nghiệm thu mục 1: **135 gói** (122 gói công việc và 13 cổng kiểm soát GATE-*); danh sách kết thúc ở E-08.
- Số gói công việc có SHA tích hợp 40-hex hợp lệ: **116 / 122**. M4-CI-PLAN ghi SHA `b18dbcff5e5beadb872b0d507b26cb88ffecf01e` do Control cung cấp (gói nghiệm thu ở chuỗi chính trước khi có Portfolio, không có commit integrate; Control đã xác minh receipt Auditor PASS và commit nội dung là tổ tiên của nhánh tích hợp).
- Số cổng kiểm soát có `recordHash` khớp mã Control cấp trong yêu cầu nghiệm thu: **13 / 13** (báo cáo chép mã, không đọc sổ quyết định của Control).
- Số gói thiếu SHA: **6** (6 gói sửa lỗi CP-4-WIRING-FIX2, ADAPT-PROD-FIX1, CP-4B-UI-SCREENS-FIX1, PERSIST-C-FIX1, ADAPT-PROD-FIX2, CP-4B-UI-SCREENS-FIX2 không tìm thấy commit integrate trên nhánh candidate).
- Sáu gói sửa lỗi có trong danh sách (CP-4-WIRING-FIX2, ADAPT-PROD-FIX1, CP-4B-UI-SCREENS-FIX1, PERSIST-C-FIX1, ADAPT-PROD-FIX2, CP-4B-UI-SCREENS-FIX2) đã tra SHA tích hợp từ lịch sử git: các commit integrate tồn tại ở các lane nhánh riêng nhưng chưa được hợp nhất vào candidate 5fd27218759bdfb463f9efc7af34caabd8debe13, ghi nhận KHÔNG TÌM THẤY tại packages.md.
- Chi tiết đối chiếu từng gói: [packages.md](packages.md). Phụ lục cùng tệp liệt kê thêm 98 gói nằm ngoài danh sách yêu cầu (E-09..E-20, F-01..F-22, G-01..G-14, H-01..H-16, I-01..I-13, J-01..J-18, CP0-GOVERNANCE, CP1-CONTRACT-BINDING, CP2A-LAYOUT) chỉ để tham khảo, không tính vào tổng 135 và không dùng để suy ra FAIL.

## 4. Lệnh kiểm

- Toàn bộ **288 / 288 lệnh kiểm** bắt buộc đã chạy lại trên candidate 5fd27218759bdfb463f9efc7af34caabd8debe13, mỗi lệnh một tiến trình riêng.
- Số lệnh exit code 0: **279 / 288** (9 lệnh thất bại: STT 29, 30, 33, 39, 41, 44, 45, 46, 47 do các gói sửa lỗi chưa được tích hợp vào candidate).
- Lệnh có test skipped: STT 22, 118, 133, 142, 241 (test PostgreSQL tự bỏ qua khi không có dịch vụ thật theo D5).
- Hai lệnh mang cờ --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression: STT 115 và STT 142; hoãn sang CP7 theo quyết định của user ngày 21/10/2026, test h36 không được chạy.
- Chi tiết kết quả, mã thoát và tóm tắt nguyên văn từng lệnh: [commands.md](commands.md).

## 5. Exit gate

Tóm tắt đối chiếu 6 exit gate Milestone M4 (chi tiết tại [exit-gates.md](exit-gates.md)):

| Mã gate | Tóm tắt nội dung | Trạng thái | Ghi chú bằng chứng |
| --- | --- | --- | --- |
| M4-EG1 | Không location nào thành verified nếu chưa có integrity evidence. | PASS | Lệnh STT 238 (`tests/unit/storage/test_storage_verification.py`, exit 0, lines 53-63 `test_upload_response_without_hash_is_never_verified`, lines 82-86 `test_recovery_edges_to_verified_are_forbidden`), STT 239 (`tests/unit/storage/test_storage_cloud_persist.py`, exit 0, lines 209-242 `test_lookup_without_hash_is_not_verified`, `test_only_verified_observation_carries_evidence`), STT 279 (`tests/integration/persistence/i/test_persist_i_postgres.py`, exit 0). |
| M4-EG2 | Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified. | PASS | Lệnh STT 243 (`tests/unit/storage/test_storage_cleanup_evaluation.py`, exit 0, lines 46-50 kiểm tra bảng quyết định: retention `output`, `original`, `reusable` khi `cloud_copy_verified=False` đều trả về `forbidden` kèm mã vi phạm `DURABLE`), STT 244 (`tests/integration/storage/test_storage_cleanup_executor.py`, exit 0). |
| M4-EG3 | Render tương lai chỉ có thể lấy artifact local đã verify. | PASS | Lệnh STT 191 (`tests/unit/render/test_f07_preconditions_artifacts_language.py`, exit 0, lines 66-75, 103-107 `test_all_verified_has_no_finding`, `test_state_other_than_verified_is_not_verified` trả về finding `ARTIFACT_NOT_VERIFIED`), STT 242 (`tests/unit/storage/test_storage_materialization.py`, exit 0, lines 152-165, 183-190 `test_verified_matching_location_is_released`, `test_every_non_verified_state_is_rejected`), STT 108 (`tests/unit/catalog/test_catalog_renderable.py`, exit 0). |
| M4-EG4 | UI phân biệt original, processed, uncertain, failed và unavailable. | PASS | Lệnh STT 230 (`tests/unit/control_ui/test_h_status_presentation.py::test_artifact_availability_five_states`, exit 0, lines 38-44 `EXPECTED_ARTIFACT` định nghĩa đủ 5 trạng thái với nhãn tiếng Việt có dấu `Bản gốc`, `Đã xử lý`, `Chưa chắc chắn`, `Lỗi`, `Không khả dụng`), STT 231 (`tests/unit/control_ui/test_h_status_pill.py`, exit 0), STT 121 (probe `screenRegistry.ts` định nghĩa đủ 18 screens với `backendStatus`, exit 0). |
| M4-EG5 | Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật. | PENDING_USER | Cần tài khoản Google Drive thật và phiên xác thực OAuth một lần của người dùng tại gói CP7. Ở thời điểm kiểm định M4, hệ thống đang vận hành hoàn toàn trên fixture và dịch vụ giả lập (fake/fixture theo CP1), tuân thủ nghiêm ngặt nguyên tắc D5. |
| M4-EG6 | User duyệt C-I và R2 Media Alpha. | PENDING_USER | Cần checkpoint duyệt của user đối với Phân hệ C-I và R2 Media Alpha; chưa có biên bản checkpoint trong các quyết định hiện hành. |

Ghi chú: theo quyết định của user (2026-10-22), exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú, không phải FAIL; chỉ M4-EG5 và M4-EG6 vào pendingUserCheckpoint.

## 6. Chờ user

pendingUserCheckpoint: M4-EG5, M4-EG6

- **M4-EG5:** Yêu cầu tài khoản Google Drive thật và người dùng thực hiện cấp quyền OAuth một lần ở slice CP7 để kiểm thử tính năng upload/integrity trên tài nguyên đám mây thật.
- **M4-EG6:** Yêu cầu người dùng xác nhận và phê duyệt nghiệm thu checkpoint đối với Phân hệ C-I và cấu hình R2 Media Alpha.

## 7. Tác dụng phụ

Tại nhóm bước 4 (lệnh kiểm STT 35), lệnh `npm --prefix src/controlplane/ui run build` chạy bằng `node_modules` Control cấp sẵn, không chạy `npm install` hay `npm ci`. Lệnh exit code 0. Sau khi chạy, git status cho thấy không có tệp theo dõi nào ngoài owned paths bị đổi so với HEAD `5fd27218759bdfb463f9efc7af34caabd8debe13`, không phát sinh tác dụng phụ.

## 8. GIẢ ĐỊNH và giới hạn

- **Giới hạn quyền hạn của Worker:** Worker chỉ thực thi các lệnh kiểm tra, đối chiếu bằng chứng kỹ thuật và lập báo cáo đóng Milestone M4; tuyệt đối không tự ý thay đổi trạng thái trong các tài liệu nguồn sự thật như `docs/11-roadmap.md`, `docs/12-pre-code-checklist.md`, `HANDOFF.md`, `README.md` hay `CHANGELOG.md`.
- **Nguyên tắc không gọi dịch vụ thật (D5):** Toàn bộ kiểm thử được thực thi trên môi trường cô lập, sử dụng mock/fixture và fake backend theo thiết kế của CP1; không đọc thư mục `Credentials/`, không đọc secret và không gọi dịch vụ bên ngoài.
- **Khóa kích hoạt sản xuất:** Trạng thái kích hoạt sản xuất tiếp tục bị khóa đóng (`PRODUCTION_ACTIVATION_BLOCKED`) cho tới khi hoàn tất toàn bộ các milestone và có phê duyệt thẩm quyền cấp cao.
- **Các mục mở (Open Items):** Các điểm kỹ thuật mở trong roadmap (`ROADMAP-OPEN-010`, `QUALITY-OPEN-004`, `QUALITY-OPEN-006`, `POLICY-CAT-001`) được ghi nhận là các giả định thiết kế chờ cấu hình chính thức, không phải là exit gate và không được đưa vào danh sách chờ user.
