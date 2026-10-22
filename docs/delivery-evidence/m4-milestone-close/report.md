# Báo cáo đóng M4 (revision 1)

## 1. Phạm vi và candidate

- **Mã nhiệm vụ (Task ID):** `M4-MILESTONE-CLOSE`
- **Candidate SHA kiểm định:** `cc290f002074514001fa0b03b3eb8c9e00c14db6` (HEAD của worktree hiện hành)
- **Python interpreter đã khóa:** `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe` (Python 3.13.15, đồng bộ hoàn toàn với `tools/runtime/runtime.lock.json`)
- **Thời điểm thực thi:** Ngày 22/10/2026
- **Phạm vi kiểm tra:** Toàn bộ 274 lệnh kiểm bắt buộc của Milestone M4 theo 31 nhóm bước của Orchestrator, kiểm tra tính toàn vẹn của 148 gói yêu cầu và đối chiếu 6 exit gate trong roadmap.

## 2. Kết luận

Kết luận kỹ thuật: KHÔNG ĐẠT

**Chi tiết đánh giá từng tiêu chí:**
- **Lệnh kiểm kiểm thử:** ĐẠT — 274/274 lệnh kiểm thực thi đạt mã thoát 0 (100% PASS), không có lệnh nào bị lỗi.
- **Exit gate kỹ thuật:** ĐẠT — 4/4 exit gate kỹ thuật (M4-EG1..M4-EG4) đều đạt trạng thái PASS với đầy đủ bằng chứng kiểm thử.
- **Exit gate chờ người dùng:** ĐẠT quy chuẩn — 2 exit gate (M4-EG5 và M4-EG6) được ghi nhận chính xác trạng thái PENDING_USER chờ tài nguyên thật và checkpoint phê duyệt của người dùng.
- **Bao phủ gói công việc:** KHÔNG ĐẠT — Trong danh sách 148 gói yêu cầu tại tiêu chí nghiệm thu mục 1, có 147 gói/cổng có SHA tích hợp hoặc recordHash xác thực; tuy nhiên gói `M4-CI-PLAN` không tìm thấy commit integrate dạng `integrate(M4-CI-PLAN)` trong git log (commit gốc của gói mang subject `feat(parallel-delivery): create M4-CI execution package, contract freeze, and test plan` tại SHA `b18dbcff5e5beadb872b0d507b26cb88ffecf01e`), do đó theo quy chuẩn nghiêm ngặt phải ghi nhận `KHÔNG TÌM THẤY` và đánh dấu FAIL tiêu chí tích hợp này.

## 3. Gói được bao phủ

- Tổng số gói trong danh sách yêu cầu nghiệm thu mục 1: **148 gói** (135 gói công việc và 13 cổng kiểm soát `GATE-*`).
- Số gói có commit tích hợp SHA 40-hex hợp lệ: **134 / 135 gói công việc**.
- Số cổng kiểm soát có `recordHash` hợp lệ trong `decisions.jsonl`: **13 / 13 cổng**.
- Số gói thiếu commit integrate: **1 gói** (`M4-CI-PLAN`).
- Chi tiết đối chiếu từng gói được lưu trữ đầy đủ tại tệp [packages.md](packages.md).
- **Vấn đề danh sách kết thúc ở F-07:** Danh sách yêu cầu nghiệm thu mục 1 kết thúc tại `F-07, )` do chuỗi văn bản bị cắt. Tuy nhiên, toàn bộ 79 gói công việc thực tế của Milestone M4 (từ F-08..F-22, G-01..G-14, H-01..H-16, I-01..I-13, J-01..J-18, CP0-GOVERNANCE, CP1-CONTRACT-BINDING, CP2A-LAYOUT) đều đã hoàn thành và tích hợp thành công vào git log. Danh sách đầy đủ các gói này được ghi nhận chi tiết tại Phụ lục của [packages.md](packages.md).

## 4. Lệnh kiểm

- Toàn bộ **274 / 274 lệnh kiểm** bắt buộc của Milestone M4 đã được thực thi độc lập trên candidate `cc290f002074514001fa0b03b3eb8c9e00c14db6`.
- Toàn bộ 274 lệnh đều kết thúc với **exit code 0**.
- Có **5 lệnh kiểm** ghi nhận test skipped (STT 22, 99, 117, 126, 226) do các test PostgreSQL được cấu hình tự động bỏ qua khi không có dịch vụ PostgreSQL thật đang chạy cục bộ, tuân thủ nguyên tắc cách ly tài nguyên thật D5.
- Có **2 lệnh kiểm** mang cờ `--deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` gồm STT 96 (Nhóm 11) và STT 126 (Nhóm 14). Hạng mục này đã được hoãn sang slice CP7 theo quyết định của người dùng ngày 21/10/2026.
- Chi tiết kết quả, mã thoát và tóm tắt nguyên văn của từng lệnh được lưu trữ tại tệp [commands.md](commands.md).

## 5. Exit gate

Tóm tắt đối chiếu 6 exit gate Milestone M4 (chi tiết tại [exit-gates.md](exit-gates.md)):

| Mã gate | Tóm tắt nội dung | Trạng thái | Ghi chú bằng chứng |
| --- | --- | --- | --- |
| --- | --- | --- | --- |
| M4-EG1 | Không location nào thành verified nếu chưa có integrity evidence. | PASS | Lệnh STT 223 (`tests/unit/storage/test_storage_verification.py`, exit 0, lines 53-63 `test_upload_response_without_hash_is_never_verified`, lines 82-86 `test_recovery_edges_to_verified_are_forbidden`), STT 224 (`tests/unit/storage/test_storage_cloud_persist.py`, exit 0, lines 209-242 `test_lookup_without_hash_is_not_verified`, `test_only_verified_observation_carries_evidence`), STT 265 (`tests/integration/persistence/i/test_persist_i_postgres.py`, exit 0). |
| M4-EG2 | Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified. | PASS | Lệnh STT 228 (`tests/unit/storage/test_storage_cleanup_evaluation.py`, exit 0, lines 46-50 kiểm tra bảng quyết định: retention `output`, `original`, `reusable` khi `cloud_copy_verified=False` đều trả về `forbidden` kèm mã vi phạm `DURABLE`), STT 229 (`tests/integration/storage/test_storage_cleanup_executor.py`, exit 0). |
| M4-EG3 | Render tương lai chỉ có thể lấy artifact local đã verify. | PASS | Lệnh STT 175 (`tests/unit/render/test_f07_preconditions_artifacts_language.py`, exit 0, lines 66-75, 103-107 `test_all_verified_has_no_finding`, `test_state_other_than_verified_is_not_verified` trả về finding `ARTIFACT_NOT_VERIFIED`), STT 227 (`tests/unit/storage/test_storage_materialization.py`, exit 0, lines 152-165, 183-190 `test_verified_matching_location_is_released`, `test_every_non_verified_state_is_rejected`), STT 89 (`tests/unit/catalog/test_catalog_renderable.py`, exit 0). |
| M4-EG4 | UI phân biệt original, processed, uncertain, failed và unavailable. | PASS | Lệnh STT 215 (`tests/unit/control_ui/test_h_status_presentation.py::test_artifact_availability_five_states`, exit 0, lines 38-44 `EXPECTED_ARTIFACT` định nghĩa đủ 5 trạng thái với nhãn tiếng Việt có dấu `Bản gốc`, `Đã xử lý`, `Chưa chắc chắn`, `Lỗi`, `Không khả dụng`), STT 216 (`tests/unit/control_ui/test_h_status_pill.py`, exit 0), STT 105 (probe `screenRegistry.ts` định nghĩa đủ 18 screens với `backendStatus`, exit 0). |
| M4-EG5 | Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật. | PENDING_USER | Cần tài khoản Google Drive thật và phiên xác thực OAuth một lần của người dùng tại gói CP7. Ở thời điểm kiểm định M4, hệ thống đang vận hành hoàn toàn trên fixture và dịch vụ giả lập (fake/fixture theo CP1), tuân thủ nghiêm ngặt nguyên tắc D5. |

## 6. Chờ user

pendingUserCheckpoint: M4-EG5, M4-EG6

- **M4-EG5:** Yêu cầu tài khoản Google Drive thật và người dùng thực hiện cấp quyền OAuth một lần ở slice CP7 để kiểm thử tính năng upload/integrity trên tài nguyên đám mây thật.
- **M4-EG6:** Yêu cầu người dùng xác nhận và phê duyệt nghiệm thu checkpoint đối với Phân hệ C-I và cấu hình R2 Media Alpha.

## 7. Tác dụng phụ

Tại bước 12 (lệnh kiểm STT 101), lệnh `npm --prefix src/controlplane/ui run build` đã được chạy trực tiếp bằng các gói trong `node_modules` có sẵn của Control mà không chạy `npm install` hay `npm ci`. Lệnh build hoàn thành thành công (exit code 0) và không làm biến đổi bất kỳ tệp theo dõi nào ngoài phạm vi quyền sở hữu (không có tệp `dist/` nào bị thay đổi so với HEAD commit `cc290f002074514001fa0b03b3eb8c9e00c14db6`). Do đó, không phát sinh tác dụng phụ và không cần thực hiện lệnh hoàn tác nào.

## 8. GIẢ ĐỊNH và giới hạn

- **Giới hạn quyền hạn của Worker:** Worker chỉ thực thi các lệnh kiểm tra, đối chiếu bằng chứng kỹ thuật và lập báo cáo đóng Milestone M4; tuyệt đối không tự ý thay đổi trạng thái trong các tài liệu nguồn sự thật như `docs/11-roadmap.md`, `docs/12-pre-code-checklist.md`, `HANDOFF.md`, `README.md` hay `CHANGELOG.md`.
- **Nguyên tắc không gọi dịch vụ thật (D5):** Toàn bộ kiểm thử được thực thi trên môi trường cô lập, sử dụng mock/fixture và fake backend theo thiết kế của CP1; không đọc thư mục `Credentials/`, không đọc secret và không gọi dịch vụ bên ngoài.
- **Khóa kích hoạt sản xuất:** Trạng thái kích hoạt sản xuất tiếp tục bị khóa đóng (`PRODUCTION_ACTIVATION_BLOCKED`) cho tới khi hoàn tất toàn bộ các milestone và có phê duyệt thẩm quyền cấp cao.
- **Các mục mở (Open Items):** Các điểm kỹ thuật mở trong roadmap (`ROADMAP-OPEN-010`, `QUALITY-OPEN-004`, `QUALITY-OPEN-006`, `POLICY-CAT-001`) được ghi nhận là các giả định thiết kế chờ cấu hình chính thức, không phải là exit gate và không được đưa vào danh sách chờ user.
