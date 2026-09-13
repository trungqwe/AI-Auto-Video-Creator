# AI Auto Video Creator — Checklist cuối trước code

**Ngày lập:** 12-09-2026  
**Trạng thái:** M0 APPROVED/CLOSED; M1 đang triển khai, P0-P5 PASS, P6 là bước tiếp theo (Audit & Evidence Synthesis)  
**Cổng áp dụng:** M0 → M1 của [roadmap](./11-roadmap.md)  
**Căn cứ audit hiện hành:** [M1 audit R1 và hậu kiểm](./milestones/m1-proof/audit-r1.md#hậu-kiểm-sau-khắc-phục)

## 1. Mục đích và cách đọc

Tài liệu này là điểm kiểm tra cuối của giai đoạn thiết kế, không thay thế charter, hợp đồng, ADR hoặc roadmap. Không tạo thêm yêu cầu sản phẩm, không lựa chọn công nghệ mới và không tự cấp quyền implementation.

- `[x]` nghĩa là có bằng chứng hoàn tất **ở cấp tài liệu** trong phạm vi nêu rõ.
- `[ ]` nghĩa là chưa hoàn tất hoặc chưa có xác nhận; không được tự đánh dấu để mở cổng.
- “Không còn BLOCKER” chỉ nói đến phát hiện thiết kế đã biết sau khắc phục, không có nghĩa mọi proof, cấu hình production hoặc kiểm thử runtime đã đạt.
- Phê duyệt baseline và quyền code M1 đã được ghi nhận ngày 13-09-2026. Quyền đó đã được kích hoạt cho M1; P0/P1 đã thực hiện, nhưng không mở quyền cho M2/M3/Phân hệ A.

### 1.1. Trạng thái cổng hiện hành

| Hạng mục | Trạng thái hiện hành | Diễn giải giới hạn |
|---|---|---|
| M0 DESIGN | ✅ `APPROVED` | Baseline thiết kế đã được user chấp thuận |
| PCC-026 | ✅ `CLOSED` | User đã đọc và chấp thuận baseline hiện hành |
| PCC-027 | ✅ `CLOSED — M1 ONLY` | Quyền implementation chỉ áp dụng M1 |
| ROADMAP-OPEN-002 | ✅ `CLOSED_FOR_M1_R1` | Version set đã chọn; compatibility chưa được chứng minh |
| M1 | 🟡 `IN PROGRESS — P0-P5 PASS` | M1 chưa hoàn tất toàn bộ; P0-P5 đã PASS; G01/G04 đạt PASS_M1_SCOPE |
| G01 Temporal | 🟡 `PARTIALLY_PROVEN (PASS_M1_SCOPE)` | P2 đã PASS trong phạm vi M1; server upgrade thuộc M2-M7 |
| G04 Drive/OAuth | 🟡 `PARTIALLY_PROVEN (PASS_M1_SCOPE)` | P3 đã PASS (bao gồm E3 live probe trên Google Drive thật) |
| ROADMAP-OPEN-003 | ✅ `CLOSED_FOR_M1_P3` | Credential thật đã được cung cấp; E3 live verification hoàn tất |
| M2 | ⛔ `NOT AUTHORIZED` | Chỉ được xem xét sau M1 exit, audit và checkpoint user |
| M3 / Module A | ⛔ `NOT AUTHORIZED` | Không được triển khai trong M1 |

Đây là bảng trạng thái có thẩm quyền trước lệnh code đầu tiên. Kết quả P2/P3 đã đạt được ghi `PASS_M1_SCOPE`; G01/G04 toàn phần vẫn `PARTIALLY_PROVEN` cho tới khi đủ evidence các milestone tiếp theo.

## 2. Mục tiêu chung để xác nhận

AI Auto Video Creator giúp một người vận hành tạo video ngắn tiếng Anh cho khán giả Mỹ từ kho tin và media có thể tái khai thác. Hệ thống thu thập, phân loại, chống trùng, xây kịch bản/góc kể, chọn tài nguyên, tạo voice/phụ đề và dựng video; người dùng theo dõi hoặc chạy/tạo lại từng công đoạn để debug, sau đó vận hành hàng loạt theo cấu hình.

Sản phẩm hướng đến tối thiểu **100 video hợp lệ trong 12 giờ** khi quy trình đã được kiểm chứng, trong ngân sách chi phí bổ sung đã chốt tại charter. “Gần như vô tận” là khả năng tiếp tục khai thác khi còn dữ liệu và phương án đủ điều kiện, không phải cam kết công suất vô hạn.

Các ranh giới không được làm mất khi triển khai:

- Một người dùng, UI tiếng Việt trên desktop từ 1080p; chưa xây SaaS đa người dùng hoặc trình sửa kịch bản/timeline, chưa thêm bước duyệt nội dung thủ công.
- Video 61–70 giây; đủ hook video, audio hook và thumbnail **trong hook**; phụ đề tiếng Anh gắn vào video, có timing từng từ cho karaoke.
- Trong cùng lượt, 1–3 video của tin/sự kiện phải khác góc kể; giữa lượt sau, phải khác ít nhất một yếu tố thực, không hoàn toàn trùng video cũ và tuân thủ lịch sử kịch bản đã chốt.
- Chỉ tạo nội dung “từ lúc đó đến nay” khi có diễn biến/tình tiết mới; bài đăng lại không tự thành tin mới nhưng được bổ sung media và xuất xứ.
- Chỉ xử lý ảnh nhạy cảm, không xử lý clip; giữ đúng ngoại lệ R25, không ghi ảnh chưa xử lý thành công là đã xử lý thành công.
- Nguồn và cấu hình khóa theo mốc bắt đầu script; retry kỹ thuật không tự biến thành video mới hoặc đổi đầu vào.
- Cloud tiếp tục thu thập khi desktop offline; script/plan/voice sản xuất bắt đầu khi desktop hoạt động theo R18. Không tự thêm dịch vụ trả phí khi fallback lỗi.
- Chỉ tính hoàn thành khi đủ QC, biến thể hợp lệ và đồng bộ được xác nhận; không xóa output chưa sync. Resume không bắt đầu lại từ tin đầu tiên.
- Chấp nhận rủi ro nội dung của người dùng không tự chứng minh quyền sử dụng tài nguyên. Tiếp tục giữ provenance và trạng thái quyền/rủi ro theo tài liệu đã chốt.

Nguồn có thẩm quyền: [charter](./00-project-charter.md), [product spec](./01-product-spec.md), [R01–R25 và data flow](./07-data-flow.md). Nếu đoạn tóm tắt này bị hiểu khác các nguồn đó, phải làm rõ trước implementation; không dùng checklist để ghi đè quyết định.

## 3. Checklist thiết kế

| ID | Kiểm tra | Trạng thái và bằng chứng |
|---|---|---|
| PCC-001 | Tôi và bạn hiểu cùng một mục tiêu | [x] Charter đã được user xác nhận; mục 2 nhắc lại mục tiêu, không mở rộng phạm vi. [00](./00-project-charter.md). |
| PCC-002 | Không còn câu hỏi Blocking về mục tiêu, ownership và hợp đồng đã audit | [x] Các khoảng thiếu được nêu trong hậu kiểm đã xử lý ở cấp tài liệu. Không bao gồm điều kiện trước code còn chờ tại mục 5. [Audit](../AUDIT.md). |
| PCC-003 | Phạm vi sản phẩm phiên bản đầu đã khóa | [x] Baseline một người dùng, có phạm vi làm/không làm và roadmap release; không đồng nhất prototype M1 với sản phẩm hoàn chỉnh. [00](./00-project-charter.md), [01](./01-product-spec.md), [11](./11-roadmap.md). |
| PCC-004 | Yêu cầu có mã định danh | [x] Có FR, QR và các quyết định R; giao tiếp có CT, kiểm thử có TST. [01](./01-product-spec.md), [03](./03-quality-requirements.md), [crosswalk](./09-contracts/13-traceability-and-open-items.md). |
| PCC-005 | Có bản đồ dữ liệu | [x] Đối tượng, quan hệ, lịch sử và vòng đời đã mô tả. [02](./02-data-model.md). |
| PCC-006 | Có yêu cầu độ ổn định, bảo mật và mở rộng | [x] Quality requirements và gate kiểm chứng đã có; chưa khẳng định đạt runtime. [03](./03-quality-requirements.md), [10](./10-test-strategy.md). |
| PCC-007 | Đã nghiên cứu build-vs-buy | [x] Có đánh giá theo năng lực, phần tái sử dụng/tự xây/hoãn và trade-off. [05](./05-technology-research.md), [ADR](./adr/README.md). |
| PCC-008 | Đã kiểm tra dự án mã nguồn mở phù hợp | [x] Nghiên cứu có nguồn, license, hoạt động, API/test/tài liệu và lý do sử dụng hoặc loại. Không thay kiểm tra version/build/model license thực tế trước dùng. [05](./05-technology-research.md). |
| PCC-009 | Đã chia rõ các phân hệ | [x] A–J là ranh giới trách nhiệm, không mặc định mỗi phân hệ là repo/service riêng. [06](./06-system-map.md). |
| PCC-010 | Mỗi phân hệ có trách nhiệm rõ | [x] Có phạm vi nhận/làm/trả và việc không sở hữu. [06](./06-system-map.md), [contracts README](./09-contracts/README.md). |
| PCC-011 | Dữ liệu đi qua hệ thống đã rõ | [x] Có luồng nội dung, media, sản xuất, lỗi, đồng bộ và cleanup. [07](./07-data-flow.md). |
| PCC-012 | Chủ sở hữu từng loại dữ liệu đã rõ | [x] Có bảng owner; C sở hữu MediaUsage, G sở hữu ledger/capacity/variant reservations; không ghi chéo bảng owner khác. [02](./02-data-model.md), [contracts README](./09-contracts/README.md). |
| PCC-013 | Kiến trúc tổng thể đã chốt baseline | [x] Hybrid modular monolith/monorepo; PostgreSQL nghiệp vụ, Drive artifact, desktop journal/cache. Lựa chọn Conditional vẫn phải qua proof. [08](./08-architecture.md). |
| PCC-014 | Các quyết định lớn có lý do | [x] ADR ghi lựa chọn, nguyên nhân, bất lợi, cách đổi và kiểm chứng; không coi Accepted đồng nghĩa đã chạy thử thành công. [ADR index](./adr/README.md). |
| PCC-015 | Giao tiếp giữa các module đã định nghĩa | [x] Có command/event, schema logic, lỗi, revision/idempotency/fencing, ownership và state machine. [09-contracts](./09-contracts/README.md). |
| PCC-016 | Chiến lược test đã có | [x] Có oracle, fault/security/contract tests và 16 ca bổ sung AUD2; chưa viết/chạy test code. [10](./10-test-strategy.md). |
| PCC-017 | Roadmap đã có | [x] Có M0–M7, dependency, exit gate, proof và checkpoint user; M0 đã APPROVED/CLOSED, M1 READY. [11](./11-roadmap.md). |
| PCC-018 | Module đầu tiên có Technical Spec | [x] `a-source-collection`, phạm vi A; không chiếm chức năng B/C/G/I/J. [spec](./modules/a-source-collection/spec.md). |
| PCC-019 | Module đầu tiên có Implementation Plan | [x] Có A0–A7, test-first, dependency, lỗi và exit gate; không được bỏ qua M1/M2. [plan](./modules/a-source-collection/implementation-plan.md). |
| PCC-020 | Đã audit | [x] Có audit, hậu kiểm và bảng khắc phục; giữ lịch sử kết luận. [AUDIT](../AUDIT.md). |
| PCC-021 | Không còn BLOCKER/MAJOR đã biết chưa xử lý trong báo cáo hiện hành | [x] Mục 11 audit đóng bốn issue AUD2 ở cấp tài liệu; không phải chứng nhận không thể còn lỗi. [AUDIT](../AUDIT.md). |
| PCC-022 | Retry, resume và outcome unknown có đường xử lý | [x] Có receipt/fencing/reconcile; terminal không mở lại, unknown không retry mù. [state machines](./09-contracts/12-state-machines.md). |
| PCC-023 | Chống trùng và completion có ranh giới nguyên tử | [x] Capacity khác VariantReservation; validation output gắn registry revision, ledger/usage/count đồng bộ. [orchestration](./09-contracts/09-orchestration-contracts.md), [ADR-0004](./adr/0004-commit-idempotency-and-fencing.md). |
| PCC-024 | Có bảo vệ dữ liệu, secret và quan sát lỗi | [x] Có cleanup authorization, provenance, secret boundary và logging/monitoring tests. [storage](./09-contracts/10-storage-contracts.md), [security](./09-contracts/11-configuration-security-contracts.md), [10](./10-test-strategy.md). |
| PCC-025 | Open item và giả định không bị coi là quyết định ngầm | [x] Open item có gate/owner theo tài liệu gốc; checklist không xác nhận thay user. Phân loại tại mục 5. |
| PCC-026 | Người dùng đã đọc và chấp thuận bộ kế hoạch hiện hành | [x] User đã chấp thuận baseline 00–12, ADR, contracts, audit, roadmap và kế hoạch Phân hệ A sau khắc phục ngày 13-09-2026. |
| PCC-027 | Người dùng cho phép bước qua ranh giới code | [x] Quyền implementation đã cấp và đang được thực thi **chỉ cho M1 Evidence Prototype**. M2/M3/Phân hệ A chưa được phép. |
| PCC-028 | Runtime/dependency/test-tool versions đã khóa trước test code đầu tiên | [x] `ROADMAP-OPEN-002=CLOSED_FOR_M1_R1`; version set và quy tắc revision/rollback ghi tại [M1-R1 lock](./milestones/m1-proof/version-lock.md). Không đồng nghĩa compatibility/G01/G04/G07 PASS. |

## 4. Xác nhận khắc phục audit

| Issue | Cách đóng ở cấp tài liệu | Kiểm chứng khi triển khai |
|---|---|---|
| AUD2-B01 | CT-ORC-012/008 và CT-AI-008: reservation nội dung, validation còn hiệu lực và exact output binding | TST-WF-VAR-001..004 |
| AUD2-M01 | CT-STATE-002: hết retry, nguồn inactive, partial/final và reconcile | TST-COL-END-001..004 |
| AUD2-M02 | CT-SRC-003A/CT-STATE-002A: kiểm tra lại READY, resolved disposition và receipt nguyên tử | TST-SRC-RACE-001..004 |
| AUD2-M03 | CT-SRC-006: sai schema khác nội dung incomplete, policy theo source kind | TST-COL-PKG-001..004 |

Audit gốc và hậu kiểm không được cộng số issue lịch sử thành số lỗi hiện còn mở. Nếu một test/proof sau này bác bỏ quyết định đóng, phải mở lại issue và gate tương ứng, không giữ dấu hoàn tất cho đẹp báo cáo.

## 5. Điều còn chờ và thời điểm phải chốt

### 5.1. Trước dòng code đầu tiên — đã hoàn tất về quyết định, chờ kích hoạt thực thi

| Điều kiện | Trạng thái | Người thực hiện/xác nhận | Bằng chứng cần có |
|---|---|---|---|
| Chấp thuận bộ kế hoạch sau audit và M0 | HOÀN TẤT | User | Xác nhận ngày 13-09-2026; M0 APPROVED/CLOSED |
| Cho phép implementation/proof | HOÀN TẤT CÓ PHẠM VI | User | Chỉ M1; không cho M2/M3/Phân hệ A. M1-P0/P1 đã thực hiện theo lệnh ngày 13-09-2026 |
| ROADMAP-OPEN-002: khóa versions cho work package có code đầu tiên | CLOSED_FOR_M1_R1 | User | [Version lock R1](./milestones/m1-proof/version-lock.md); lockfile/hash và binary evidence tạo tại P0/P5, không giả là proof đã đạt |

Không còn câu hỏi blocking cần user trả lời trước M1-P2. M1-P0/P1 đã PASS. ROADMAP-OPEN-003 chỉ chặn trực tiếp M1-P3; do P3 là exit dependency nên thiếu credential thật sẽ làm M1 `BLOCKED_EXTERNAL`, nhưng không được dùng để chặn ngược P2.

### 5.2. Không chặn hoàn tất checklist thiết kế, nhưng chặn milestone liên quan

| Nhóm | Mốc phải giải quyết | Quy tắc |
|---|---|---|
| Workflow/Drive/OAuth compatibility và proof G01/G04 sớm | M1 trước xây phụ thuộc sâu | Proof fail mở lại ADR; không coi shortlist hoặc cấu hình có sẵn là proof |
| Nền envelope/outbox/config/secrets/UI/artifact | M2 trước module A implementation | Module A là phân hệ nghiệp vụ đầu tiên, không phải bỏ qua công việc nền |
| Nguồn thử, source-kind/Tier/discovery/extraction policy và title requirement | Theo A0/A3/A4/A6 và gate gốc | Thiếu policy thì chờ; fixture không phải quyết định production |
| Múi giờ, ngưỡng chủ đề, proxy hot/trending và timeout/retry cụ thể | Trước scheduler/content-selection acceptance tương ứng | Không tự lấy ví dụ làm giá trị chính thức |
| Output profile, word timing tolerance, model/TTS và năm preset chi tiết | Trước exit render/AI/media tương ứng | Phải có cấu hình và evidence theo test strategy |
| Retention/storage placement, restore, workload, sampling và hiệu năng/chi phí | Theo G02–G07 và roadmap | Không bật cleanup/unattended hoặc công bố đạt chất lượng khi gate chưa đạt |

Danh mục có thẩm quyền: [roadmap, mục 23](./11-roadmap.md), [contract open items](./09-contracts/13-traceability-and-open-items.md), [module A plan](./modules/a-source-collection/implementation-plan.md). Bảng này nhóm các gate để dễ đọc, không thay thế toàn bộ sổ open item hoặc tự đóng chúng.

## 6. Quy tắc mở cổng

1. Ba điều kiện quyết định PCC-026/027/028 đã hoàn tất cho M1-R1.
2. Lệnh bắt đầu M1 đã được nhận; chỉ tiếp tục theo dependency của [M1 plan](./milestones/m1-proof/implementation-plan.md), hiện là M1-P2.
3. P0 phải tạo lockfile, `bootstrap.json` và PostgreSQL preflight trước dòng test Python đầu tiên; dòng test đầu phải thuộc M1 proof và RED vì `environment.json` chưa được implementation tạo/hoàn thiện, không phải do import/setup lỗi.
4. Không nhảy sang M2, M3 hoặc A1; implementation Phân hệ A chỉ sau M1 exit/audit/checkpoint và dependency M2 theo roadmap.
5. Mỗi work package kết thúc phải ghi PASS/FAIL/BLOCKED_EXTERNAL/STOPPED cùng evidence. `RED_CONFIRMED` không phải FAIL; defect implementation dùng `CORRECTION_REQUIRED`. Chỉ mở ADR khi root-cause evidence phủ định quyết định kiến trúc, còn lỗi version cụ thể đi theo revision R2 trước.

Checklist không phải lệnh cài thư viện, khởi tạo framework, triển khai hạ tầng, chi tiền hoặc bật production. Quyền thực thi phải theo phạm vi user cho phép và các gate hiện hành.

## 7. Biên bản phê duyệt

| Nội dung | Ghi nhận hiện tại |
|---|---|
| Bộ tài liệu trình duyệt | 00–03, 05–08, ADR, 09-contracts, 10, 11, module A spec/plan, AUDIT mục 11 và checklist 12 này |
| User đã đọc và chấp thuận kế hoạch sau audit | ĐÃ XÁC NHẬN cho baseline hiện hành |
| User cho phép code | ĐÃ XÁC NHẬN, chỉ trong M1 Evidence Prototype |
| Phạm vi work package được phép | M1-P0 → M1-P6 theo dependency; M1-P3 có thể BLOCKED_EXTERNAL. Chưa cho phép M2/M3/Phân hệ A |
| Version set trước code | M1-R1 đã khóa; ROADMAP-OPEN-002=CLOSED_FOR_M1_R1 |
| Thời điểm và thông điệp xác nhận | 13-09-2026; xác nhận trong yêu cầu làm rõ open case và lập kế hoạch M1 |
| Trạng thái cổng hiện hành | M0 APPROVED; M1 IN PROGRESS — P0/P1/P2 PASS; P3 BLOCKED_EXTERNAL; G01 PARTIALLY_PROVEN; G04 NOT TESTED; M2 và M3/Module A NOT AUTHORIZED |

Trạng thái phê duyệt đã được đồng bộ vào roadmap và module plan. Nếu có sửa đổi đáng kể sau phê duyệt, xác định phần ảnh hưởng và kiểm toán lại trước khi dùng bản mới.

**Kết luận:** Baseline thiết kế và version set M1-R1 đã được user chấp thuận; quyền code chỉ giới hạn M1. M1-P0/P1/P2/P3/P4/P5 đã PASS theo test-first và evidence; package tiếp theo là M1-P6 (Evidence synthesis & Audit). Không tự mở M2/M3/Phân hệ A.

## Trạng thái sau M1-P2 Temporal G01 Proof

M1-P2 đã hoàn thành với 7 bài test đạt GREEN, evidence đầy đủ tại `docs/milestones/m1-proof/evidence/m1-p2/`. P0/P1/P2 `PASS`; G01 `PARTIALLY_PROVEN (PASS_M1_SCOPE)`. ROADMAP-OPEN-003 chỉ chặn P3; M2/M3/Module A vẫn `NOT AUTHORIZED`.

## Trạng thái sau M1-P3 Google Drive & OAuth G04 Proof

M1-P3 đã hoàn thành với 8 bài test (7 unit/integration + 1 live E3 verification trên Google Drive thật) đạt GREEN, evidence đầy đủ tại `docs/milestones/m1-proof/evidence/m1-p3/`. P0/P1/P2/P3 `PASS`; G01 và G04 đều đạt `PARTIALLY_PROVEN (PASS_M1_SCOPE)`. ROADMAP-OPEN-003 đã được đóng cho M1-P3 (`CLOSED_FOR_M1_P3`). Thư mục `Credentials/` và token cache được bảo vệ tuyệt đối qua `.gitignore`.

## Trạng thái sau M1-P4 Local Journal & Recovery Proof

M1-P4 đã hoàn thành với 6 bài test đạt GREEN, evidence đầy đủ tại `docs/milestones/m1-proof/evidence/m1-p4/`. P0/P1/P2/P3/P4 `PASS`. Đã chứng minh: SQLite local journal lưu giữ trạng thái bền vững sau crash, atomic file write trên Windows từ chối partial byte, lost ACK được reconcile theo idempotency qua port receipt P1, recovery epoch cũ bị cách ly (`QUARANTINED`), cache dọn dẹp không xâm phạm journal active, và phát hiện tệp thiếu/sai lệch hash (`CORRUPT_OR_MISSING`).

## Trạng thái sau M1-P5 Compatibility Smoke

M1-P5 đã hoàn thành với 6 bài test đạt GREEN, evidence đầy đủ tại `docs/milestones/m1-proof/evidence/m1-p5/`. P0/P1/P2/P3/P4/P5 `PASS`. Đã kiểm chứng: CPython 3.13.15, uv 0.12.13, khóa `uv.lock` frozen, PostgreSQL 18.6 rollback và lưu trữ UTF-8 tiếng Việt hoàn hảo, Temporal SDK 1.32.0 handshake/replay xác định, ranh giới client Google không rò rỉ secret khi thiếu khóa, và binary FFmpeg thực tế (`C:\ffmpeg\bin\ffmpeg.exe`, SHA-256: `f845a09b...`) probe media an toàn bằng argument array. Work package tiếp theo là M1-P6 (Evidence synthesis & Audit); M2/M3/Module A vẫn `NOT AUTHORIZED`.
