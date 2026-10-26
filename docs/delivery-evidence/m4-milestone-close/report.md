# Báo cáo đóng M4 (revision 4)

## 1. Phạm vi và candidate

- **Mã nhiệm vụ (Task ID):** `M4-MILESTONE-CLOSE-R4`
- **Candidate SHA kiểm định:** `3497cecbf9fe9a09818192e9c7c12c0c68396c01` (HEAD của worktree, tiêu đề commit: `integrate(M4-MILESTONE-CLOSE-R3): lane lane-m4-milestone-close-r3 candidate cb368a9d8eea`; 290 lệnh kiểm chạy trên cây mã nguồn này, bằng chứng chỉ thêm tệp trong `docs/delivery-evidence/m4-milestone-close/`)
- **Lần chạy này:** Revision 4 thay thế hoàn toàn revision 3 (candidate cũ `6042d7a626d3d523881cc86d1b0ac674986bcafa`, 289 lệnh).
- **Python interpreter đã khóa:** `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe` (Python 3.13.15, đồng bộ hoàn toàn với `tools/runtime/runtime.lock.json`)
- **Thời điểm thực thi:** Ngày 26/10/2026
- **Phạm vi kiểm tra:** Toàn bộ 290 lệnh kiểm bắt buộc của Milestone M4 theo 14 nhóm bước, 159 gói và cổng trong danh sách yêu cầu nghiệm thu (146 gói công việc và 13 cổng GATE-*) và 6 exit gate trong roadmap.

## 2. Kết luận

Kết luận kỹ thuật: ĐẠT

**Chi tiết đánh giá từng tiêu chí:**
- **Lệnh kiểm:** ĐẠT — 290/290 lệnh kiểm chạy lại trên candidate đạt exit code 0; 0 lệnh thất bại.
- **Exit gate kỹ thuật:** ĐẠT — M4-EG1..M4-EG4 PASS, bằng chứng tại exit-gates.md.
- **Exit gate chờ người dùng:** ĐẠT quy chuẩn — M4-EG5 và M4-EG6 ghi PENDING_USER vì cần tài khoản Drive thật và checkpoint duyệt của user; không gate nào khác bị ghi pending.
- **Bao phủ gói:** ĐẠT — 159/159 gói và cổng có SHA tích hợp hoặc recordHash; M4-CI-PLAN ghi SHA `b18dbcff5e5beadb872b0d507b26cb88ffecf01e` do Control xác minh.

## 3. Gói được bao phủ

- Tổng số gói trong danh sách yêu cầu nghiệm thu mục 1: **159 gói** (146 gói công việc và 13 cổng kiểm soát GATE-*); danh sách kết thúc ở G-01.
- Số gói công việc có SHA tích hợp 40-hex hợp lệ: **146 / 146** (145 commit integrate; M4-CI-PLAN ghi SHA `b18dbcff5e5beadb872b0d507b26cb88ffecf01e` do Control cung cấp: gói nghiệm thu ở chuỗi chính trước khi có Portfolio, không có commit integrate; Control đã xác minh receipt Auditor PASS và commit nội dung là tổ tiên của nhánh tích hợp).
- Số cổng kiểm soát có `recordHash` khớp mã Control cấp trong yêu cầu nghiệm thu: **13 / 13** (báo cáo chép mã, không đọc sổ quyết định của Control).
- Số gói thiếu SHA: **0**.
- Revision 4 không còn 13 gói sửa lỗi trong danh sách yêu cầu, các gói đó cùng G-02..G-14, H, I, J, CP0, CP1, CP2A nằm ở phụ lục tham khảo của [packages.md](packages.md), không tính vào tổng 159.
- Chi tiết đối chiếu từng gói: [packages.md](packages.md).

## 4. Lệnh kiểm

- Toàn bộ **290 / 290 lệnh kiểm** bắt buộc đã chạy lại trên candidate `3497cecbf9fe9a09818192e9c7c12c0c68396c01`, mỗi lệnh một tiến trình riêng, chia thành 14 nhóm theo cột «Nhóm bước» của [commands.md](commands.md).
- Số lệnh exit code 0: **290 / 290** (0 lệnh thất bại).
- Lệnh mới của revision 4: STT 290 (probe `launch-fix3`), exit code 0.
- Lệnh có test skipped: STT 91, 110, 122, 123, 223 (theo kết quả thực tế trong [commands.md](commands.md)).
- Hai lệnh mang cờ `--deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression`: STT 88 và STT 123 (hoãn sang CP7 theo quyết định của user ngày 21/10/2026, test h36 không được chạy).
- Lệnh phải chạy lại sau lỗi môi trường: không có.
- Chi tiết kết quả, mã thoát và tóm tắt nguyên văn từng lệnh: [commands.md](commands.md).

## 5. Exit gate

Tóm tắt đối chiếu 6 exit gate Milestone M4 (chi tiết tại [exit-gates.md](exit-gates.md)):

| Mã gate | Tóm tắt nội dung | Trạng thái | Ghi chú bằng chứng |
| --- | --- | --- | --- |
| M4-EG1 | Không location nào thành verified nếu chưa có integrity evidence. | PASS | Lệnh STT 220 (`tests/unit/storage/test_storage_verification.py`, exit 0), STT 221 (`tests/unit/storage/test_storage_cloud_persist.py`, exit 0), STT 263 (`tests/integration/persistence/i/test_persist_i_postgres.py`, exit 0). |
| M4-EG2 | Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified. | PASS | Lệnh STT 225 (`tests/unit/storage/test_storage_cleanup_evaluation.py`, exit 0), STT 226 (`tests/integration/storage/test_storage_cleanup_executor.py`, exit 0). |
| M4-EG3 | Render tương lai chỉ có thể lấy artifact local đã verify. | PASS | Lệnh STT 172 (`tests/unit/render/test_f07_preconditions_artifacts_language.py`, exit 0), STT 224 (`tests/unit/storage/test_storage_materialization.py`, exit 0), STT 81 (`tests/unit/catalog/test_catalog_renderable.py`, exit 0). |
| M4-EG4 | UI phân biệt original, processed, uncertain, failed và unavailable. | PASS | Lệnh STT 212 (`tests/unit/control_ui/test_h_status_presentation.py`, exit 0), STT 213 (`tests/unit/control_ui/test_h_status_pill.py`, exit 0), STT 97 (probe `screenRegistry.ts`, exit 0). |
| M4-EG5 | Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật. | PENDING_USER | Cần tài khoản Google Drive thật và phiên xác thực OAuth một lần của người dùng tại gói CP7. Ở thời điểm kiểm định M4, hệ thống đang vận hành hoàn toàn trên fixture và dịch vụ giả lập (fake/fixture theo CP1), tuân thủ nghiêm ngặt nguyên tắc D5. |
| M4-EG6 | User duyệt C-I và R2 Media Alpha. | PENDING_USER | Cần checkpoint duyệt của user đối với Phân hệ C-I và R2 Media Alpha; chưa có biên bản checkpoint trong các quyết định hiện hành. |

Ghi chú: theo quyết định của user (2026-10-22), exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú, không phải FAIL; chỉ M4-EG5 và M4-EG6 vào pendingUserCheckpoint.

## 6. Chờ user

pendingUserCheckpoint: M4-EG5, M4-EG6

- **M4-EG5:** Yêu cầu tài khoản Google Drive thật và người dùng thực hiện cấp quyền OAuth một lần ở slice CP7 để kiểm thử tính năng upload/integrity trên tài nguyên đám mây thật.
- **M4-EG6:** Yêu cầu người dùng xác nhận và phê duyệt nghiệm thu checkpoint đối với Phân hệ C-I và cấu hình R2 Media Alpha.

## 7. Tác dụng phụ

Tại nhóm bước 7 (lệnh kiểm STT 93), lệnh `npm --prefix src/controlplane/ui run build` chạy bằng `node_modules` do Control cấp sẵn, không chạy `npm install` hay `npm ci`, exit 0; các probe dist STT 95, 126, 281 kiểm `src/controlplane/ui/dist` (không tệp băm mồ côi, đúng 4 tệp) cũng đạt sau build. Worker chỉ commit tệp trong `docs/delivery-evidence/m4-milestone-close/`; không phát sinh tác dụng phụ ngoài owned paths.

Nếu bạn kiểm tra bằng `git status --porcelain` (lệnh chỉ đọc, không phải bước của lệnh làm việc này) mà thấy tệp theo dõi nào ngoài owned paths bị đổi, thì ghi đúng sự thật vào đoạn này (tên tệp, nguyên nhân) và tuyệt đối không commit tệp đó; không tự khôi phục bằng lệnh git. Hiện tại, `git status --porcelain` xác nhận không có bất kỳ tệp nào ngoài `docs/delivery-evidence/m4-milestone-close/` bị thay đổi.

## 8. GIẢ ĐỊNH và giới hạn

- **Giới hạn quyền hạn của Worker:** Worker chỉ thực thi các lệnh kiểm tra, đối chiếu bằng chứng kỹ thuật và lập báo cáo đóng Milestone M4; tuyệt đối không tự ý thay đổi trạng thái trong các tài liệu nguồn sự thật như `docs/11-roadmap.md`, `docs/12-pre-code-checklist.md`, `HANDOFF.md`, `README.md` hay `CHANGELOG.md`.
- **Nguyên tắc không gọi dịch vụ thật (D5):** Toàn bộ kiểm thử được thực thi trên môi trường cô lập, sử dụng mock/fixture và fake backend theo thiết kế của CP1; không đọc thư mục `Credentials/`, không đọc secret và không gọi dịch vụ bên ngoài.
- **Khóa kích hoạt sản xuất:** Trạng thái kích hoạt sản xuất tiếp tục bị khóa đóng (`PRODUCTION_ACTIVATION_BLOCKED`) cho tới khi hoàn tất toàn bộ các milestone và có phê duyệt thẩm quyền cấp cao.
- **Các mục mở (Open Items):** Các điểm kỹ thuật mở trong roadmap (`ROADMAP-OPEN-010`, `QUALITY-OPEN-004`, `QUALITY-OPEN-006`, `POLICY-CAT-001`) được ghi nhận là các giả định thiết kế chờ cấu hình chính thức, không phải là exit gate và không được đưa vào danh sách chờ user.
