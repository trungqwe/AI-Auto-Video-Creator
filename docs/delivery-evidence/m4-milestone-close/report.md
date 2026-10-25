# Báo cáo đóng M4 (revision 3)

## 1. Phạm vi và candidate

- **Mã nhiệm vụ (Task ID):** `M4-MILESTONE-CLOSE-R3`
- **Candidate SHA kiểm định:** `6042d7a626d3d523881cc86d1b0ac674986bcafa` (integration head, tiêu đề commit: `integrate(ADAPT-LAUNCH-FIX2): lane lane-adapt-launch-fix2 candidate 903393a717cb`; 289 lệnh kiểm chạy trên cây mã nguồn của commit này, bằng chứng chỉ thêm tệp trong `docs/delivery-evidence/m4-milestone-close/`)
- **Lần chạy này:** Revision 3 thay thế hoàn toàn kết quả revision 2 (chạy trên integration head cũ `21d99fc89eb076a036b4d62f026b057a61d96135`, chưa chứa gói sửa lỗi `ADAPT-LAUNCH-FIX2`).
- **Python interpreter đã khóa:** `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe` (Python 3.13.15, đồng bộ hoàn toàn với `tools/runtime/runtime.lock.json`)
- **Thời điểm thực thi:** Ngày 25/10/2026
- **Phạm vi kiểm tra:** Toàn bộ 289 lệnh kiểm bắt buộc của Milestone M4 theo 10 nhóm bước, 131 gói và cổng trong danh sách yêu cầu nghiệm thu (118 gói công việc và 13 cổng GATE-*) và 6 exit gate trong roadmap.

## 2. Kết luận

Kết luận kỹ thuật: ĐẠT

**Chi tiết đánh giá từng tiêu chí:**
- **Lệnh kiểm:** ĐẠT — 289/289 lệnh kiểm chạy lại trên candidate đạt exit code 0; 0 lệnh thất bại.
- **Exit gate kỹ thuật:** ĐẠT — M4-EG1..M4-EG4 PASS, bằng chứng tại exit-gates.md.
- **Exit gate chờ người dùng:** ĐẠT quy chuẩn — M4-EG5 và M4-EG6 ghi PENDING_USER vì cần tài khoản Drive thật và checkpoint duyệt của user; không gate nào khác bị ghi pending.
- **Bao phủ gói:** ĐẠT — 131/131 gói và cổng có SHA tích hợp hoặc recordHash; M4-CI-PLAN ghi SHA `b18dbcff5e5beadb872b0d507b26cb88ffecf01e` do Control xác minh; 8 gói sửa lỗi tích hợp sau ADAPT-LAUNCH (gồm `ADAPT-LAUNCH-FIX2`) đều có commit integrate 40-hex hợp lệ nằm trong lịch sử của HEAD.

## 3. Gói được bao phủ

- Tổng số gói trong danh sách yêu cầu nghiệm thu mục 1: **131 gói** (118 gói công việc và 13 cổng kiểm soát GATE-*); danh sách kết thúc ở E-02.
- Số gói công việc có SHA tích hợp 40-hex hợp lệ: **118 / 118** (117 commit integrate; M4-CI-PLAN ghi SHA `b18dbcff5e5beadb872b0d507b26cb88ffecf01e` do Control cung cấp: gói nghiệm thu ở chuỗi chính trước khi có Portfolio, không có commit integrate; Control đã xác minh receipt Auditor PASS và commit nội dung là tổ tiên của nhánh tích hợp).
- Số cổng kiểm soát có `recordHash` khớp mã Control cấp trong yêu cầu nghiệm thu: **13 / 13** (báo cáo chép mã, không đọc sổ quyết định của Control).
- Số gói thiếu SHA: **0**.
- Tám gói sửa lỗi tích hợp sau ADAPT-LAUNCH đều có commit integrate hợp lệ nằm trong lịch sử của CANDIDATE_HEAD `6042d7a626d3d523881cc86d1b0ac674986bcafa`:
  - `CP-4-WIRING-FIX2`: `759ea0abd830f76b6f6a99232e8183ee50a9f34d` (lane lane-cp-4-wiring-fix2 candidate 5aed9712848f)
  - `ADAPT-PROD-FIX1`: `6ba0bcde40de3d3adf8405d9df6bd8cae431227a` (lane lane-adapt-prod-fix1 candidate d588d9c0e8b0)
  - `CP-4B-UI-SCREENS-FIX1`: `adc7634f45a21c2fa174adee662962d7a1b21a57` (lane lane-cp-4b-ui-screens-fix1 candidate 2760ee3ca0f9)
  - `PERSIST-C-FIX1`: `ab8586d55fc612825888d6a7e26e58ae96d28af6` (lane lane-persist-c-fix1 candidate 2327dcf8e326)
  - `ADAPT-PROD-FIX2`: `fa250e8305aa422ff260f2ce9bb3622a29239740` (lane lane-adapt-prod-fix2 candidate e1cc7f40b25b)
  - `CP-4B-UI-SCREENS-FIX2`: `74c062a29d649ea0e3d1471dee9c739dc33d38fe` (lane lane-cp-4b-ui-screens-fix2 candidate 1c85775dea49)
  - `ADAPT-LAUNCH-FIX1`: `21d99fc89eb076a036b4d62f026b057a61d96135` (lane lane-adapt-launch-fix1 candidate 9bcb10e680dc)
  - `ADAPT-LAUNCH-FIX2`: `6042d7a626d3d523881cc86d1b0ac674986bcafa` (lane lane-adapt-launch-fix2 candidate 903393a717cb; chính là CANDIDATE_HEAD)
- Chi tiết đối chiếu từng gói: [packages.md](packages.md). Phụ lục cùng tệp liệt kê thêm 104 gói nằm ngoài danh sách yêu cầu (E-03..E-20, F-01..F-22, G-01..G-14, H-01..H-16, I-01..I-13, J-01..J-18, CP0-GOVERNANCE, CP1-CONTRACT-BINDING, CP2A-LAYOUT) chỉ để tham khảo, không tính vào tổng 131 và không dùng để suy ra FAIL.

## 4. Lệnh kiểm

- Toàn bộ **289 / 289 lệnh kiểm** bắt buộc đã chạy lại trên candidate `6042d7a626d3d523881cc86d1b0ac674986bcafa`, mỗi lệnh một tiến trình riêng, chia thành 10 nhóm theo cột «Nhóm bước» của commands.md (mỗi nhóm là một bước RUN của lệnh làm việc, các lệnh nối bằng `&&`).
- Số lệnh exit code 0: **289 / 289** (0 lệnh thất bại).
- Lệnh mới của revision 3: STT 50 (probe `tools/launcher/launcher.py` cho `ADAPT-LAUNCH-FIX2`: có `build_production_ports`, `load_ports_config`, `ports.json`, không có `from tools`), exit code 0; các STT từ 51 trở đi lệch +1 so với revision 2.
- Lệnh có test skipped: STT 22, 119, 134, 143, 242 (test PostgreSQL tự bỏ qua khi không có dịch vụ thật theo D5).
- Hai lệnh mang cờ --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression: STT 116 và STT 143; hoãn sang CP7 theo quyết định của user ngày 21/10/2026, test h36 không được chạy.
- Lệnh phải chạy lại sau lỗi môi trường: không có.
- Chi tiết kết quả, mã thoát và tóm tắt nguyên văn từng lệnh: [commands.md](commands.md).

## 5. Exit gate

Tóm tắt đối chiếu 6 exit gate Milestone M4 (chi tiết tại [exit-gates.md](exit-gates.md)):

| Mã gate | Tóm tắt nội dung | Trạng thái | Ghi chú bằng chứng |
| --- | --- | --- | --- |
| M4-EG1 | Không location nào thành verified nếu chưa có integrity evidence. | PASS | Lệnh STT 239 (`tests/unit/storage/test_storage_verification.py`, exit 0, lines 53-63 `test_upload_response_without_hash_is_never_verified`, lines 82-86 `test_recovery_edges_to_verified_are_forbidden`), STT 240 (`tests/unit/storage/test_storage_cloud_persist.py`, exit 0, lines 209-242 `test_lookup_without_hash_is_not_verified`, `test_only_verified_observation_carries_evidence`), STT 280 (`tests/integration/persistence/i/test_persist_i_postgres.py`, exit 0). |
| M4-EG2 | Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified. | PASS | Lệnh STT 244 (`tests/unit/storage/test_storage_cleanup_evaluation.py`, exit 0, lines 46-50 kiểm tra bảng quyết định: retention `output`, `original`, `reusable` khi `cloud_copy_verified=False` đều trả về `forbidden` kèm mã vi phạm `DURABLE`), STT 245 (`tests/integration/storage/test_storage_cleanup_executor.py`, exit 0). |
| M4-EG3 | Render tương lai chỉ có thể lấy artifact local đã verify. | PASS | Lệnh STT 192 (`tests/unit/render/test_f07_preconditions_artifacts_language.py`, exit 0, lines 66-75, 103-107 `test_all_verified_has_no_finding`, `test_state_other_than_verified_is_not_verified` trả về finding `ARTIFACT_NOT_VERIFIED`), STT 243 (`tests/unit/storage/test_storage_materialization.py`, exit 0, lines 152-165, 183-190 `test_verified_matching_location_is_released`, `test_every_non_verified_state_is_rejected`), STT 109 (`tests/unit/catalog/test_catalog_renderable.py`, exit 0). |
| M4-EG4 | UI phân biệt original, processed, uncertain, failed và unavailable. | PASS | Lệnh STT 231 (`tests/unit/control_ui/test_h_status_presentation.py::test_artifact_availability_five_states`, exit 0, lines 38-44 `EXPECTED_ARTIFACT` định nghĩa đủ 5 trạng thái với nhãn tiếng Việt có dấu `Bản gốc`, `Đã xử lý`, `Chưa chắc chắn`, `Lỗi`, `Không khả dụng`), STT 232 (`tests/unit/control_ui/test_h_status_pill.py`, exit 0), STT 122 (probe `screenRegistry.ts` định nghĩa đủ 18 screens với `backendStatus`, exit 0). |
| M4-EG5 | Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật. | PENDING_USER | Cần tài khoản Google Drive thật và phiên xác thực OAuth một lần của người dùng tại gói CP7. Ở thời điểm kiểm định M4, hệ thống đang vận hành hoàn toàn trên fixture và dịch vụ giả lập (fake/fixture theo CP1), tuân thủ nghiêm ngặt nguyên tắc D5. |
| M4-EG6 | User duyệt C-I và R2 Media Alpha. | PENDING_USER | Cần checkpoint duyệt của user đối với Phân hệ C-I và R2 Media Alpha; chưa có biên bản checkpoint trong các quyết định hiện hành. |

Ghi chú: theo quyết định của user (2026-10-22), exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú, không phải FAIL; chỉ M4-EG5 và M4-EG6 vào pendingUserCheckpoint.


## 6. Chờ user

pendingUserCheckpoint: M4-EG5, M4-EG6

- **M4-EG5:** Yêu cầu tài khoản Google Drive thật và người dùng thực hiện cấp quyền OAuth một lần ở slice CP7 để kiểm thử tính năng upload/integrity trên tài nguyên đám mây thật.
- **M4-EG6:** Yêu cầu người dùng xác nhận và phê duyệt nghiệm thu checkpoint đối với Phân hệ C-I và cấu hình R2 Media Alpha.

## 7. Tác dụng phụ

Tại nhóm bước 3 (lệnh kiểm STT 35), lệnh `npm --prefix src/controlplane/ui run build` chạy bằng `node_modules` Control cấp sẵn, không chạy `npm install` hay `npm ci`. Lệnh exit code 0; hai probe STT 37 và STT 38 kiểm `src/controlplane/ui/dist` (không tệp băm mồ côi, đúng 4 tệp) cũng đạt sau build. Worker chỉ commit tệp trong `docs/delivery-evidence/m4-milestone-close/`; không phát sinh tác dụng phụ ngoài owned paths.

Nếu bạn kiểm tra bằng `git status --porcelain` (lệnh chỉ đọc, không phải bước của lệnh làm việc này) mà thấy tệp theo dõi nào ngoài owned paths bị đổi, thì ghi đúng sự thật vào đoạn này (tên tệp, nguyên nhân) và tuyệt đối không commit tệp đó; không tự khôi phục bằng lệnh git.

## 8. GIẢ ĐỊNH và giới hạn

- **Giới hạn quyền hạn của Worker:** Worker chỉ thực thi các lệnh kiểm tra, đối chiếu bằng chứng kỹ thuật và lập báo cáo đóng Milestone M4; tuyệt đối không tự ý thay đổi trạng thái trong các tài liệu nguồn sự thật như `docs/11-roadmap.md`, `docs/12-pre-code-checklist.md`, `HANDOFF.md`, `README.md` hay `CHANGELOG.md`.
- **Nguyên tắc không gọi dịch vụ thật (D5):** Toàn bộ kiểm thử được thực thi trên môi trường cô lập, sử dụng mock/fixture và fake backend theo thiết kế của CP1; không đọc thư mục `Credentials/`, không đọc secret và không gọi dịch vụ bên ngoài.
- **Khóa kích hoạt sản xuất:** Trạng thái kích hoạt sản xuất tiếp tục bị khóa đóng (`PRODUCTION_ACTIVATION_BLOCKED`) cho tới khi hoàn tất toàn bộ các milestone và có phê duyệt thẩm quyền cấp cao.
- **Các mục mở (Open Items):** Các điểm kỹ thuật mở trong roadmap (`ROADMAP-OPEN-010`, `QUALITY-OPEN-004`, `QUALITY-OPEN-006`, `POLICY-CAT-001`) được ghi nhận là các giả định thiết kế chờ cấu hình chính thức, không phải là exit gate và không được đưa vào danh sách chờ user.
