# KIỂM TOÁN CUỐI TRƯỚC CODE

**Ngày:** 12-09-2026  
**Phạm vi:** Kiểm toán tĩnh, đối chiếu tài liệu; không kiểm chứng phần mềm đang chạy.  
**Kết luận audit gốc tại thời điểm 12-09-2026:** **CHƯA ĐỦ ĐIỀU KIỆN MỞ CỔNG CODE.**  
**Trạng thái sau khắc phục hậu kiểm ngày 12-09-2026:** **Đã xử lý 1 BLOCKER và 3 MAJOR của mục 10 ở cấp tài liệu**, theo xác minh và bảng thay đổi tại mục 11. Chưa có bằng chứng runtime. Ngày 13-09-2026, user đã phê duyệt M0 và cấp quyền code chỉ cho M1; việc thực thi đang chờ lệnh bắt đầu tiếp theo.  
**Trạng thái hiện hành sau hậu kiểm M1 ngày 13-09-2026:** năm MAJOR về scope gate, completion UoW, evidence order, PostgreSQL preflight và failure taxonomy đã được xử lý tại mục 12; không còn BLOCKER/MAJOR đã biết trước M1-P0.  
**Phát hiện audit gốc:** 4 BLOCKER, 6 MAJOR, 1 MINOR. Đây là số liệu lịch sử, không cộng với số phát hiện hậu kiểm.  
**Thao tác audit gốc:** Chỉ tạo báo cáo này.  
**Thao tác khắc phục:** Đồng bộ các tài liệu bị ảnh hưởng bằng thay đổi nhỏ nhất; không tạo mã nguồn, cài thư viện hoặc khởi tạo framework.

## 1. Cách đọc kết quả

- **BLOCKER:** Phải thống nhất lại trước khi code vì ảnh hưởng bất biến nghiệp vụ hoặc hợp đồng nền được nhiều phân hệ sử dụng.
- **MAJOR:** Rất nên đóng trước code; tối thiểu phải chặn triển khai lát cắt bị ảnh hưởng cho tới khi được giải quyết.
- **MINOR:** Có thể hoàn thiện sau, nhưng phải có người chịu trách nhiệm và mốc đóng.
- “Cần làm” trong báo cáo là yêu cầu khắc phục, **không phải quyết định thay thế đã được phê duyệt**.
- Một mục đã được công khai để chờ benchmark không tự động là lỗi. Chưa có bằng chứng chạy thật không đồng nghĩa công nghệ không phù hợp.

Các vị trí dòng dưới đây thuộc bản tài liệu tại thời điểm audit. Đường dẫn mở tài liệu; số dòng đi kèm giúp định vị bằng chứng.

## 2. Tài liệu đối chiếu

| Nhóm | Tài liệu |
|---|---|
| Nghiệp vụ và chất lượng | `docs/00-project-charter.md`, `01-product-spec.md`, `02-data-model.md`, `03-quality-requirements.md` |
| Nghiên cứu và thiết kế | `docs/05-technology-research.md`, `06-system-map.md`, `07-data-flow.md`, `08-architecture.md` |
| Hồ sơ quyết định | `docs/adr/README.md` và ADR-0001 đến ADR-0012 |
| Hợp đồng | `docs/09-contracts/README.md` và các tài liệu 00–13 |
| Kiểm thử và triển khai | `docs/10-test-strategy.md`, `11-roadmap.md` |
| Phân hệ đầu tiên | `docs/modules/a-source-collection/spec.md`, `implementation-plan.md` |

Ưu tiên yêu cầu người dùng đã xác nhận khi tài liệu kỹ thuật dẫn xuất mâu thuẫn. Việc viết hợp đồng sau không tự động cho phép thay đổi yêu cầu trước đó.

## 3. BLOCKER

### AUD-B01 — Hợp đồng và QC chuyển thumbnail ra sau hook, trái yêu cầu đã chốt

**Bằng chứng:** [Charter](docs/00-project-charter.md), dòng 44; [đặc tả sản phẩm](docs/01-product-spec.md), dòng 241, yêu cầu thumbnail **trong hook** và không công nhận hoàn thành khi thiếu. Ngược lại, [hợp đồng media](docs/09-contracts/05-content-media-contracts.md), dòng 103, 154; [hợp đồng AI](docs/09-contracts/06-creative-ai-contracts.md), dòng 172; [hợp đồng render/QC](docs/09-contracts/08-render-quality-contracts.md), dòng 64 và CT-QC-001, quy định thumbnail **sau hook**.

**Tình huống và hậu quả:** D tạo plan đúng hợp đồng hiện tại, F dựng và QC cho qua, nhưng video vẫn vi phạm FR-REN-004. Đây là lỗi tiêu chí hoàn thành, không chỉ khác cách diễn đạt.

**Cần làm trước code:** Đồng bộ vị trí thumbnail theo yêu cầu đã xác nhận; định nghĩa rõ khoảng thời gian hook và bằng chứng thumbnail xuất hiện trong khoảng đó. Không cần hỏi lại yêu cầu vốn đã rõ.

**Điều kiện đóng:** Plan chỉ có thumbnail sau hook phải trượt; thumbnail trong hook phải được kiểm tra trên output thực. Cập nhật thống nhất C/D/F và test liên quan. **Chủ trì:** D/F, phối hợp C.

### AUD-B02 — Khóa periodic run cho phép quét lại cùng nguồn trong ngày khi đổi policy

**Bằng chứng:** [Charter](docs/00-project-charter.md), dòng 80 và [FR-COL-001](docs/01-product-spec.md), dòng 98: mỗi nguồn được chọn tối đa một lượt định kỳ/ngày. [Kế hoạch A](docs/modules/a-source-collection/implementation-plan.md), dòng 195: khóa periodic run gồm `workspace + source + local date + policy revision + purpose`. [Spec A](docs/modules/a-source-collection/spec.md), dòng 347, cũng đưa policy revision vào cách diễn đạt quy tắc ngày.

**Tình huống và hậu quả:** Nguồn S đã chạy ngày D với policy P1; đổi sang P2 rồi scheduler chạy lại. Hai khóa khác nhau đều hợp lệ theo kế hoạch, dẫn tới hai periodic run trong một ngày. Đổi timezone giữa ngày còn làm ranh giới này khó xác định hơn.

**Cần làm trước code:** Tách danh tính lượt định kỳ khỏi phiên bản cấu hình dùng để thực thi; chốt quy tắc hiệu lực timezone/ngày. Retry vẫn phải thuộc run cũ, không tạo lượt định kỳ mới.

**Điều kiện đóng:** Test đồng thời hai scheduler, thay policy trong ngày, restart và retry đều giữ giới hạn một lượt theo ngày nghiệp vụ đã định nghĩa. **Chủ trì:** A/G/J.

### AUD-B03 — Recovery epoch có bất biến nhưng chưa có đường truyền và kiểm tra đầy đủ

**Bằng chứng:** [Kiến trúc](docs/08-architecture.md), dòng 555 và [CT-STO-009](docs/09-contracts/10-storage-contracts.md), dòng 179–181, yêu cầu vô hiệu command/result cũ sau restore. Tuy nhiên [MessageEnvelope](docs/09-contracts/00-common-contract.md), mục 3; [ExecutionGrant và ActivityResult](docs/09-contracts/03-workflow-and-execution.md), mục 5, 7, không định nghĩa epoch hoặc ràng buộc grant với epoch. Danh sách điều kiện nhận result chỉ kiểm tra grant, generation, fingerprint và receipt. [DomainEvent](docs/09-contracts/02-domain-events.md), mục 2, cũng chưa xác định cách mang epoch dù mục phục hồi yêu cầu phân biệt event trước restore.

**Tình huống và hậu quả:** Khôi phục database về thời điểm một grant còn hợp lệ. Worker cũ trả kết quả có grant/generation/fingerprint khớp dữ liệu đã restore. Các điều kiện nhận result được liệt kê chưa đủ phân biệt worker thuộc thế hệ phục hồi cũ. Nguy cơ commit kết quả hoặc side effect cũ vào trạng thái mới.

**Cần làm trước code:** Chọn và ghi rõ cơ chế ràng buộc epoch trong grant/message hoặc tra cứu có thẩm quyền; xác định nơi cấp, nơi lưu ngoài trạng thái có thể bị quay lùi, nơi kiểm tra và ngoại lệ reconcile. Không bắt buộc thêm trường vào mọi payload nếu cơ chế khác chứng minh tương đương.

**Điều kiện đóng:** Restore khi worker cũ còn sống; gửi lại command/result/event cũ có generation trùng; tất cả mutation không được phép đều bị từ chối, còn reconcile có đường xử lý rõ. **Chủ trì:** G/I/J và mọi owner nhận result.

### AUD-B04 — Giao dịch hoàn thành và thời điểm ghi usage không thống nhất

**Bằng chứng:** [CT-ORC-008](docs/09-contracts/09-orchestration-contracts.md), dòng 159–168, đặt ghi media/content usage **trong** giao dịch hoàn thành nguyên tử. [CT-MED-008](docs/09-contracts/05-content-media-contracts.md), dòng 178–189, chỉ commit usage **sau khi** giao dịch hoàn thành thành công. [Bảng ownership](docs/09-contracts/README.md), dòng 97, giao MediaUsage cho C; hợp đồng G cấm G tự sửa output của owner khác. [Catalog event](docs/09-contracts/02-domain-events.md), dòng 127, chỉ liệt kê H/I là consumer chính của VideoCompleted, chưa làm rõ đường cập nhật lịch sử C/D.

**Tình huống và hậu quả:** Hai nhóm triển khai có thể chọn hai mô hình khác nhau: G ghi bảng C trong completion, hoặc C cập nhật bất đồng bộ sau completion. Ở mô hình thứ hai, crash/khoảng trễ tạo trạng thái video đã hoàn thành nhưng lịch sử sử dụng chưa theo kịp. Reservation ở kiến trúc giảm nguy cơ trùng, nhưng chưa làm rõ thời điểm chuyển từ reservation sang lịch sử bền vững.

**Cần làm trước code:** Chốt một ngữ nghĩa giao dịch và ownership: ai gọi owner nào, dữ liệu nào phải nguyên tử, dữ liệu nào chỉ là projection có thể trễ; lúc nào giải phóng reservation; thuật toán chọn biến thể đọc nguồn nào trong khoảng trễ.

**Điều kiện đóng:** Crash giữa commit và cập nhật usage, event lặp/mất kết nối, allocation ngay sau completion đều không làm mất lịch sử hoặc tính sai biến thể. **Chủ trì:** G/C/D/B.

## 4. MAJOR

### AUD-M01 — Định dạng thư mục bị đổi ngược về DD-MM

**Bằng chứng:** [Charter](docs/00-project-charter.md), dòng 174–175; [FR-OUT-001/002](docs/01-product-spec.md), dòng 259–260; [data flow](docs/07-data-flow.md), dòng 313: `YY-MM-DD` và hậu tố phiên. [Render contract](docs/09-contracts/08-render-quality-contracts.md), dòng 154–157 và [storage contract](docs/09-contracts/10-storage-contracts.md), dòng 227–228 lại quy định `DD-MM`, gán `YY-MM-DD` cho ngày dữ liệu khác.

**Hậu quả:** Đầu ra sai yêu cầu, mất năm trong tên thư mục và dễ gom nhầm khi lưu nhiều năm. Đây không phải mục cấu hình chưa chốt.

**Cần làm/đóng:** Đồng bộ naming policy theo yêu cầu đã xác nhận; test nhiều phiên cùng ngày, qua năm và restart. **Chủ trì:** I/G/F.

### AUD-M02 — CollectionRun chưa phân biệt lỗi có thể retry với trạng thái terminal

**Bằng chứng:** [Spec A](docs/modules/a-source-collection/spec.md), dòng 332–337: `SCHEDULED → RUNNING → COMPLETED | COMPLETED_PARTIAL | FAILED`, đồng thời “Retryable failure tạo attempt mới trong cùng run” và “Run terminal không quay lại running”. [Kế hoạch A](docs/modules/a-source-collection/implementation-plan.md), dòng 376–397, yêu cầu kiểm thử terminal immutability và trường hợp terminal bị yêu cầu resume. Dòng 44 còn gọi retry là purpose riêng, trong khi spec dòng 348 coi retry là attempt của run cũ.

**Hậu quả:** Sau lỗi mạng, người triển khai chưa biết giữ run RUNNING, đưa FAILED rồi mở lại, hay tạo run mới. Hai cách sau có thể trái terminal invariant hoặc giới hạn một run/ngày.

**Cần làm/đóng:** Phân biệt lỗi attempt với kết thúc run, định nghĩa transition cho retryable/final/partial và purpose của retry. Test timeout, retry thành công, hết retry và tiếp tục sau crash phải có expected state duy nhất. **Chủ trì:** A/G. Chặn code state machine A2 khi chưa đóng.

### AUD-M03 — Một số yêu cầu chất lượng chưa được chuyển đầy đủ xuống hợp đồng kiểm tra

**Bằng chứng:** [Yêu cầu chất lượng](docs/03-quality-requirements.md), dòng 50–51, 139, 152, 237: tiếng Anh là bắt buộc; QR-SAFE-004 yêu cầu ảnh nhận diện có vũ khí tạo được yêu cầu xử lý theo cấu hình. [CT-QC-001](docs/09-contracts/08-render-quality-contracts.md) liệt kê hard gates nhưng thiếu gate hoặc tham chiếu bắt buộc xác nhận ngôn ngữ. [CT-PROC-005/006](docs/09-contracts/07-media-processing-contracts.md), mục 4, mô tả mục tiêu trẻ em/máu me nhưng không ánh xạ rõ vũ khí vào kết quả phân loại và transform request. Test strategy đã nhắc tiếng Anh/vũ khí, nên đây là khoảng trống hợp đồng, không phải toàn bộ test bị bỏ quên.

**Hậu quả:** Implementation theo danh sách hợp đồng có thể chấp nhận video sai ngôn ngữ hoặc không tạo yêu cầu xử lý ảnh vũ khí dù test cấp cao đòi hỏi.

**Cần làm/đóng:** Bổ sung ánh xạ yêu cầu tới validator/report cụ thể, có thể dùng báo cáo từ upstream thay vì bắt F tự nhận diện mọi thứ. Test phải gắn bằng chứng với đúng script/voice/output revision. Không mở rộng sang xử lý clip, không thay ngoại lệ ảnh gốc R25. **Chủ trì:** D/E/F.

### AUD-M04 — Target lô có test chống vượt nhưng allocation contract chưa khóa số chỗ đang chạy

**Bằng chứng:** [CT-ORC-002 và CT-ORC-008](docs/09-contracts/09-orchestration-contracts.md) có allocation, đếm completion đúng một lần, nhưng chưa chỉ rõ invariant giữa target, completed và các job đã cấp chưa hoàn thành. [TST-E2E-005](docs/10-test-strategy.md), dòng 553–555, yêu cầu không cấp job vượt target do race. Reservation chống trùng nội dung trong [kiến trúc](docs/08-architecture.md), dòng 364, không tự đồng nghĩa reservation cho số lượng target.

**Tình huống:** Target còn một video, hai allocator cùng nhìn completed count và cấp hai job khác nhau; cả hai đều hoàn thành hợp lệ. Exactly-once cho từng job không ngăn vượt target của lô.

**Cần làm/đóng:** Ghi invariant admission nguyên tử, cách tính job đang chạy và cách trả chỗ khi lỗi/hủy. Test nhiều allocator, job lỗi được thay thế, completion trùng và target gần đầy. **Chủ trì:** G.

### AUD-M05 — Module đầu tiên vẫn thiếu hợp đồng đầu vào để có thể tuyên bố sẵn sàng triển khai toàn bộ

**Bằng chứng:** [Kế hoạch A](docs/modules/a-source-collection/implementation-plan.md), dòng 48–64, 301–302, 824–832, công khai chưa khóa minimum package fields, SourceCandidate lifecycle và quy tắc đa chủ đề. [Data flow](docs/07-data-flow.md), dòng 126, coi cách đếm tin đa chủ đề là cấu hình. A0 dự kiến đóng các điểm này, A6 được chặn có chủ đích.

**Đánh giá:** Đây là khoản nợ đã được ghi nhận, không phải giả định bị che giấu. Tuy nhiên “cấu hình sau” chưa đủ cho quy tắc làm thay đổi số tin đạt ngưỡng, disposition package và event trao đổi A/B/G. Không thể ghi cổng cuối là “module A đã sẵn sàng toàn bộ”.

**Cần làm/đóng:** Đóng phần hợp đồng A0 bằng tài liệu trước code phần phụ thuộc; chỉ rõ required/optional fields, owner candidate, lifecycle và ngữ nghĩa đếm. Các giá trị số ngưỡng/timeout có thể tiếp tục để cấu hình. Không yêu cầu hoàn thành M1/M2 bằng code trước khi được phép code: đó là dependency triển khai đã được roadmap ghi đúng. **Chủ trì:** A/B/G/J.

### AUD-M06 — Thiếu kịch bản kiểm soát prompt injection từ dữ liệu nguồn

**Bằng chứng:** [Hợp đồng sáng tạo AI](docs/09-contracts/06-creative-ai-contracts.md) nhận nội dung ngoài để phân tích/tạo script; [hợp đồng chung](docs/09-contracts/00-common-contract.md) có actor external_source và refs nhưng không định nghĩa mức tin cậy cho nội dung đưa vào model. [Chiến lược kiểm thử](docs/10-test-strategy.md), phần security, đã bao phủ SSRF, secret, path/command injection nhưng chưa có tình huống bài tin/media metadata chứa chỉ dẫn nhằm điều khiển AI.

**Tình huống và hậu quả:** Nội dung cào được chứa yêu cầu bỏ marker suy luận, dựng source reference giả hoặc thay chỉ dẫn chọn media. Typed output có thể vẫn hợp schema. Việc người dùng không yêu cầu kiểm chứng đa nguồn không có nghĩa dữ liệu nguồn được quyền thay prompt hệ thống hoặc policy.

**Cần làm/đóng:** Định nghĩa ranh giới giữa chỉ dẫn tin cậy và dữ liệu ngoài; validator kiểm tra refs/quyền/policy độc lập với lời khẳng định của model. Thêm fixture bài tin, metadata và kết quả truy xuất có chỉ dẫn độc hại; test không tạo hành động hoặc refs vượt quyền và không tự bỏ disclosure. Không cam kết model chống injection tuyệt đối. **Chủ trì:** D/J, phối hợp A/C và kiểm thử.

## 5. MINOR

### AUD-N01 — Traceability theo nhóm chưa đủ để phát hiện trượt từng requirement

**Bằng chứng:** [Traceability hợp đồng](docs/09-contracts/13-traceability-and-open-items.md) và [test strategy](docs/10-test-strategy.md), phần ma trận QR, chủ yếu tổng hợp theo invariant/nhóm mã; không phải bảng chứng minh mỗi FR/QR có đúng owner, hợp đồng, gate và expected result. Các sai khác thumbnail, tên thư mục và language gate vẫn tồn tại dù đã có ma trận.

**Cần làm/đóng:** Khi sửa các phát hiện, bổ sung liên kết từng requirement bị ảnh hưởng tới contract và test cụ thể; ghi trạng thái “đã thiết kế test” tách “đã chạy đạt”. Không cần viết lại mọi tài liệu hay tạo thêm hệ thống quản lý yêu cầu. **Chủ trì:** Người quản lý đặc tả và kiểm thử.

## 6. Đánh giá theo 18 tiêu chí

| Tiêu chí | Kết quả |
|---|---|
| 1. Yêu cầu bị bỏ sót | M03: ngôn ngữ/vũ khí chưa được chuyển đầy đủ xuống hợp đồng |
| 2. Tài liệu mâu thuẫn | B01, B02, B04, M01, M02 |
| 3. Giả định chưa xác nhận | M05 là phần công khai còn mở; B01/M01 là thay đổi trái yêu cầu, không thể hợp thức hóa bằng nhãn giả định |
| 4. Quá phức tạp | Temporal/private network/TLS có chi phí vận hành đáng kể; ADR-0003/0009 đã nêu đánh đổi. Chưa đủ bằng chứng yêu cầu thay kiến trúc |
| 5. Mở rộng không đủ | Host chung có rủi ro contention; ADR-0002 và G02/G03 đã có cổng đo. Chưa xác nhận năng lực thực tế |
| 6. Phụ thuộc vòng | Chưa xác lập vòng triển khai bắt buộc từ bằng chứng hiện có. A phụ thuộc nền M1/M2 là hợp lệ; phải tách stub/contract test khỏi nghiệm thu tích hợp thật |
| 7. Trách nhiệm chồng chéo | B04: completion/usage giữa G và các owner |
| 8. Ownership dữ liệu | B04; M05: SourceCandidate còn phải đóng contract |
| 9. Mất hoặc sai dữ liệu | B03: restore nhận kết quả cũ; B04: khoảng trống completion/usage |
| 10. Dữ liệu trùng | B02: periodic run; B04: lịch sử/reservation; M04: cấp thừa video |
| 11. Khó thay nhà cung cấp | Có ports, artifact refs, model/index revision và ADR về thay thế; chưa có bằng chứng adapter thay được trong thực tế |
| 12. Logging/monitoring | Có correlation, session/job/stage, metrics và cost ledger; không kết luận thiếu toàn bộ. Cần quan sát lỗi epoch/usage/admission từ các phát hiện trên |
| 13. Đường xử lý lỗi | M02; B03/B04 cần làm rõ phục hồi |
| 14. Thiếu test | M06; bổ sung ca biên cụ thể cho B01–B04/M01–M04; test strategy hiện là thiết kế, chưa phải kết quả chạy |
| 15. Quyết định khó đảo ngược | Engine, storage và model có trạng thái Conditional/gate; không được đổi thành cam kết vận hành khi chưa có proof |
| 16. Nghiên cứu công nghệ | Tài liệu 05 là nguồn ứng viên và lịch sử nghiên cứu; chưa thay thế lockfile/version matrix, license review và benchmark thật. Audit này không tái xác minh mọi release/contributor trên Internet |
| 17. Requirement không truy tới thiết kế | M03/N01; B01 cho thấy có liên kết nhưng nội dung liên kết sai |
| 18. Thiết kế không phục vụ requirement | Chưa có bằng chứng đủ mạnh để yêu cầu bỏ một phân hệ. Workspace boundary phục vụ khả năng tích hợp về sau, không mặc nhiên mở scope SaaS đầy đủ |

“Chưa xác lập phát hiện” không phải chứng nhận không có rủi ro. Báo cáo không suy ra độ đúng của implementation chưa tồn tại.

## 7. Các phần không nên sửa chỉ vì audit này

- Giữ 10 phân hệ A–J làm ranh giới trách nhiệm; không suy ra cần 10 repo hoặc microservice.
- Giữ PostgreSQL là dữ liệu nghiệp vụ, Drive là nơi chứa artifact, SQLite là journal/cache desktop; không chuyển Google Sheets thành lõi.
- Giữ phạm vi chỉ xử lý ảnh nhạy cảm, không xử lý clip; giữ ngoại lệ R25 và provenance/risk metadata.
- Giữ kiểm tra đầy đủ dữ liệu/truy được nguồn, không tự thêm bước duyệt hoặc kiểm chứng sự thật đa nguồn.
- Giữ snapshot tại mốc tạo script, retry khác tạo biến thể, cloud thu thập khi desktop offline và cleanup có điều kiện.
- Không hạ mục tiêu 100 video/12 giờ hoặc ngân sách để làm đẹp kết luận. G01–G07 phải tiếp tục được kiểm chứng đúng roadmap.

## 8. Thứ tự khắc phục và mở lại cổng

1. Đóng B01/B02 bằng đối chiếu yêu cầu đã xác nhận; đồng bộ M01 cùng đợt để tránh sửa đi sửa lại naming/output rules.
2. Đóng B03/B04 bằng hợp đồng quyền thực thi, ownership và transaction rõ ràng; không cần redesign toàn hệ thống.
3. Đóng M02/M04 và các phần A0 của M05 trước triển khai state machine, scheduler hoặc allocation liên quan.
4. Hoàn thiện M03/M06 và ánh xạ test N01; chỉ rõ phần nào được duyệt hoãn, phần nào chặn milestone.
5. Audit lại diff tài liệu, bảo đảm tất cả BLOCKER có bằng chứng đóng và MAJOR có kết luận xử lý. Sau đó mới xin người dùng cho phép code.

**Phân biệt cổng:** Đóng audit tài liệu chỉ tạo điều kiện xin phép bắt đầu implementation/proof. Không đồng nghĩa Temporal/Drive/model đã đạt benchmark, không đóng G01–G07, không cho phép phát hành hoặc unattended production.

**Lưu ý lịch sử:** Bảng dưới đây ghi nhận kết luận của lượt khắc phục trước, không còn là trạng thái đóng issue hiện hành. Kết quả hậu kiểm tại mục 10 thay thế kết luận này. Các gate Conditional G01-G07 vẫn phải được chứng minh trong quá trình triển khai.

## 9. Bảng giải quyết từng issue — lịch sử lượt khắc phục

| Issue | Kết quả kiểm tra | Tài liệu bị ảnh hưởng | Thay đổi nhỏ nhất đã áp dụng | Trạng thái |
|---|---|---|---|---|
| `AUD-B01` | **Hợp lý.** Requirement gốc nói thumbnail ở trong hook; ba hợp đồng dẫn xuất đã đổi thành sau hook. | `09-contracts/05`, `06`, `08`; test strategy; roadmap | Đổi duy nhất placement thành time range nằm trong vùng hook; QC kiểm tra trên output thực. | **ĐÃ GIẢI QUYẾT** |
| `AUD-B02` | **Hợp lý.** Đưa policy revision vào unique key cho phép lượt định kỳ thứ hai cùng ngày. | Data model; data flow; `09-contracts/04`, `12`; module A spec/plan; test strategy | Khóa identity thành workspace/source/business-date/periodic; policy chỉ là metadata. Khóa semantics đếm một lần/article/topic/business-date. | **ĐÃ GIẢI QUYẾT** |
| `AUD-B03` | **Hợp lý.** Storage có khái niệm epoch nhưng grant/result/event chưa mang và kiểm tra nó. | Data model; architecture; ADR-0004/0010; `09-contracts/00`, `02`, `03`, `09`, `10`, `13`; test strategy | Thêm recovery epoch opaque vào grant/result/receipt/event; tạo epoch mới trước khi mở writer; epoch cũ bị stale/quarantine dù generation trùng. | **ĐÃ GIẢI QUYẾT** |
| `AUD-B04` | **Hợp lý.** Completion yêu cầu atomic nhưng ownership/timing của MediaUsage mâu thuẫn. | Data model; architecture; ADR-0004; contracts README, `05`, `09`, `13`; test strategy | Trong modular monolith, G điều phối một PostgreSQL unit of work và gọi application port C; ledger/reservation/MediaUsage cùng commit hoặc rollback, không ghi chéo bảng. | **ĐÃ GIẢI QUYẾT** |
| `AUD-M01` | **Hợp lý.** `DD-MM` trái quyết định `YY-MM-DD`. | `09-contracts/08`, `10`; test strategy | Trả folder về `YY-MM-DD`, thêm hậu tố `(1)`, `(2)` cho phiên hợp lệ tiếp theo; session rỗng không tạo folder sản phẩm. | **ĐÃ GIẢI QUYẾT** |
| `AUD-M02` | **Hợp lý.** Run terminal mơ hồ retryable failure với terminal failure. | Data model; `09-contracts/04`, `12`; module A spec/plan; test strategy | Tách `CollectionAttempt`; run dùng `WAITING_RETRY`/`WAITING_RECONCILIATION`; chỉ `FAILED_FINAL` là terminal. | **ĐÃ GIẢI QUYẾT** |
| `AUD-M03` | **Hợp lý nhưng phạm vi hẹp.** Requirement/test cấp cao đã có; thiếu ánh xạ ở contract QC và xử lý ảnh. | `09-contracts/07`, `08`; test strategy; roadmap | Thêm category vũ khí vào transform request theo cấu hình và hard gate `ENGLISH_OUTPUT_VALID` gắn đúng script/voice/subtitle/metadata revisions. Không mở rộng sang clip. | **ĐÃ GIẢI QUYẾT** |
| `AUD-M04` | **Hợp lý.** Architecture có ý niệm giữ suất nhưng allocation contract chưa khóa race. | Data model; architecture; ADR-0004; contracts README, `09`, `13`; test strategy; roadmap | Chính thức hóa `BatchCapacityReservation`; allocation nguyên tử và invariant `completed + active reservations <= target`. | **ĐÃ GIẢI QUYẾT** |
| `AUD-M05` | **Hợp lý một phần, đã thu hẹp.** Không chặn M1/M2 hoặc toàn module A; chỉ chặn lát cắt dùng contract còn thiếu. | Data model; data flow; `09-contracts/02`, `04`, `12`, README; module A spec/plan; test strategy; roadmap | Định nghĩa SourceCandidate owner/lifecycle/command/event, required/conditional package fields và multi-topic count. Giá trị Tier, ngưỡng, timezone, nguồn vẫn là cấu hình/gate đúng kế hoạch. | **ĐÃ GIẢI QUYẾT** |
| `AUD-M06` | **Hợp lý nhưng architecture đã có biên bảo vệ.** Khoảng thiếu nằm ở contract AI và security tests. | `09-contracts/00`, `06`; test strategy; roadmap; đối chiếu architecture mục 10.2 | Gắn `untrusted_data`/trust class, tách instruction-data, kiểm ref qua resolver/allowlist và thêm indirect prompt-injection corpus. | **ĐÃ GIẢI QUYẾT** |
| `AUD-N01` | **Hợp lý.** Traceability theo nhóm đã không phát hiện ba mâu thuẫn cụ thể. | `09-contracts/13-traceability-and-open-items.md` | Thêm crosswalk từng concern từ requirement sang contract và test; tách rõ “đã thiết kế” khỏi gate chạy thật. | **ĐÃ GIẢI QUYẾT** |

### Kết luận sau khắc phục — đã được hậu kiểm lại tại mục 10

- Không còn chuỗi cũ “thumbnail sau hook”, folder `DD-MM`, periodic unique key chứa policy revision hoặc SourceCandidate contract gap trong tập tài liệu đã rà soát.
- Ownership không đổi: A sở hữu nguồn/thu thập, C sở hữu `MediaUsage`, G sở hữu batch/reservation/completion, mỗi owner vẫn ghi qua application port của mình.
- Không redesign 10 phân hệ, không đổi hybrid topology, database, storage, workflow candidate hay provider strategy.
- Đây là **document verification**, chưa phải bằng chứng runtime. Test strategy và các gate G01-G07 phải được thực thi sau khi người dùng cho phép code.

## 10. Hậu kiểm sau khắc phục

### 10.1. Phạm vi và kết luận — lịch sử trước lượt sửa mục 11

Hậu kiểm đối chiếu điều kiện đóng của 11 issue gốc với yêu cầu, kiến trúc, ADR, hợp đồng, máy trạng thái, test strategy và kế hoạch module A. Tập trung vào tính nhất quán sau sửa và các tình huống đồng thời, retry, dữ liệu đầu vào không hợp lệ. Đây là kiểm toán tĩnh, không phải kiểm chứng runtime hoặc nghiên cứu lại toàn bộ nhà cung cấp.

**Kết quả: 1 BLOCKER, 3 MAJOR; không xác lập thêm MINOR trong lượt này.** Phần sửa trước có giá trị, nhưng một số bất biến mới dừng ở mô tả kiến trúc hoặc chưa có đường xử lý đầy đủ trong hợp đồng. Không cần redesign toàn hệ thống. Lượt hậu kiểm chỉ cập nhật báo cáo này, không tự sửa thiết kế.

### 10.2. BLOCKER — AUD2-B01: Thiếu giao thức chống trùng biến thể khi nhiều job chạy đồng thời

**Liên hệ issue cũ:** `AUD-B04` đã sửa đúng tính nguyên tử của `MediaUsage` và completion ledger, nhưng chưa đủ để đóng toàn bộ nguy cơ trùng biến thể.

**Bằng chứng:**

- [Kiến trúc, dòng 364](docs/08-architecture.md#L364) yêu cầu D/G giữ reservation nguyên tử cho phương án đang chạy và đối chiếu lại output trước completion.
- [ValidateVariant, dòng 191](docs/09-contracts/06-creative-ai-contracts.md#L191) nhận lịch sử hoàn thành và video trong lượt, nhưng chưa định nghĩa reservation/token, phạm vi khóa hay hiệu lực kết quả khi lịch sử thay đổi.
- [Allocation, dòng 71](docs/09-contracts/09-orchestration-contracts.md#L71) chỉ chính thức hóa `BatchCapacityReservation`, tức suất số lượng, không phải giữ chỗ nội dung.
- [CommitVideoCompletion, dòng 149](docs/09-contracts/09-orchestration-contracts.md#L149) nhận variant validation ref nhưng transaction chưa có bước chống xung đột với biến thể vừa được job khác giữ chỗ hoặc hoàn thành.

**Tình huống:** Hai lô khai thác cùng tin, có đủ suất số lượng; hai job cùng kiểm tra một lịch sử cũ và nhận kết quả hợp lệ cho cùng biến thể thực tế. Job thứ nhất hoàn thành; job thứ hai vẫn dùng validation ref cũ. Ledger duy nhất theo job và usage nguyên tử không ngăn hai job khác nhau hoàn thành nội dung trùng.

**Tác động:** Vi phạm yêu cầu không hoàn toàn giống video cũ. Đây là khoảng thiếu trong hợp đồng D/G, không phải khẳng định implementation chưa tồn tại đã có lỗi.

**Thay đổi nhỏ nhất đề xuất:** Cụ thể hóa reservation đã có trong kiến trúc: owner, phạm vi article/event và lượt, danh tính phương án, hiệu lực validation, cách giữ/giải phóng khi retry hoặc terminal; quy định kiểm tra xung đột nguyên tử ở completion và kết quả trả về khi validation đã cũ. Không thêm service hoặc thay database.

**Tài liệu cần đồng bộ:** Contracts `06`, `09`, `12`, `13`; test strategy; đối chiếu architecture và ADR-0004 để cùng một semantics.

**Điều kiện đóng:** Có contract test cho hai job khác nhau ở hai lô cùng chọn một biến thể; chỉ một được hoàn thành, job còn lại nhận disposition rõ ràng. Có trường hợp retry cùng job, reservation hết hiệu lực và hai phương án khác biệt hợp lệ. Các test này phải được đặc tả trước code, thực thi khi triển khai.

### 10.3. MAJOR — AUD2-M01: Run đang chờ retry chưa có đường kết thúc đầy đủ

**Liên hệ issue cũ:** Mở lại một phần `AUD-M02`.

**Bằng chứng:** [CT-STATE-002, dòng 28–35](docs/09-contracts/12-state-machines.md#L28) có `WAITING_RETRY → RUNNING`, nhưng đường tới terminal chỉ bắt đầu từ `RUNNING`. Mọi attempt `FAILED_RETRYABLE` đều được mô tả đưa run vào `WAITING_RETRY`. [Module A, dòng 334](docs/modules/a-source-collection/spec.md#L334) lặp lại quy tắc này. [Quy tắc lỗi chung, dòng 194](docs/09-contracts/00-common-contract.md#L194) chỉ cho retry khi policy cho phép.

**Tình huống:** Attempt cuối lỗi có thể retry về mặt kỹ thuật nhưng đã hết ngân sách retry. Run vào `WAITING_RETRY`; không được tạo attempt tiếp theo, cũng chưa có chuyển trạng thái hợp lệ để kết thúc. Tương tự cần xác định kết quả khi nguồn bị tắt/xóa trong thời gian chờ. Reconcile ra kết quả retryable cũng chưa được thể hiện rõ bằng transition từ `WAITING_RECONCILIATION` sang `WAITING_RETRY`.

**Tác động:** Run/cycle có thể chờ vô hạn hoặc các bên tự chọn terminal khác nhau; UI và scheduler không có kết quả thống nhất.

**Thay đổi nhỏ nhất đề xuất:** Bổ sung các hàng transition với trigger, điều kiện và terminal disposition khi hết retry, nguồn không còn được phép thu thập, hoặc reconcile xác nhận được retry. Phân biệt partial đã có dữ liệu với lỗi không có kết quả; không đổi toàn bộ máy trạng thái.

**Tài liệu cần đồng bộ:** Contracts `04`, `12`; module A spec/implementation-plan; test strategy; data model nếu cần làm rõ kết quả attempt.

**Điều kiện đóng:** Mỗi trường hợp trên có trạng thái cuối hoặc điều kiện chờ hữu hạn rõ ràng; test không cần tạo attempt giả chỉ để đưa run về terminal. Chặn triển khai đường retry của module A tới khi thống nhất.

### 10.4. MAJOR — AUD2-M02: Candidate đã sẵn sàng thiếu đường xử lý xung đột lúc đăng ký

**Liên hệ issue cũ:** Phần còn thiếu của `AUD-M05`.

**Bằng chứng:** [CT-SRC-003A, dòng 56](docs/09-contracts/04-source-content-contracts.md#L56) cho phép registration trả conflict/policy error và phải tôn trọng source/tombstone hiện hành. Tuy nhiên, [CT-STATE-002A, dòng 39–41](docs/09-contracts/12-state-machines.md#L39) chỉ cho `READY_FOR_REGISTRATION → REGISTERED`; nhánh matched/tombstone chỉ xuất phát từ `VALIDATING`.

**Tình huống:** Candidate đã READY, sau đó thao tác khác đăng ký cùng nguồn hoặc tạo tombstone trước khi candidate được đăng ký. RegisterSource đúng sẽ không tạo nguồn mới, nhưng candidate chưa có transition hợp lệ sang `MATCHED_EXISTING`/`BLOCKED_TOMBSTONE` hoặc quay lại validation.

**Tác động:** Không chứng minh rằng tombstone bị vượt qua; vấn đề là candidate có thể mắc kẹt READY, lặp conflict và không phát được kết quả resolved nhất quán.

**Thay đổi nhỏ nhất đề xuất:** Quy định tái kiểm tra identity/tombstone tại registration và đường chuyển trạng thái tương ứng; kết quả candidate phải nhất quán với receipt/source thực tế khi retry. Có thể bổ sung transition trực tiếp hoặc đường revalidation, không cần đổi mô hình SourceCandidate.

**Tài liệu cần đồng bộ:** Contracts `04`, `12`, event `SourceCandidateResolved` trong `02`; module A spec/plan; test strategy.

**Điều kiện đóng:** Test các race READY–register cùng nguồn, READY–tombstone và retry registration sau commit mất ACK; candidate có disposition/receipt xác định và không tạo nguồn trùng. Chặn lát cắt auto-registration, không chặn toàn bộ thu thập.

### 10.5. MAJOR — AUD2-M03: Package sai cấu trúc bị đánh đồng với nội dung không đủ

**Liên hệ issue cũ:** Quy tắc bổ sung khi sửa `AUD-M05` chưa nhất quán.

**Bằng chứng:** [Document package, dòng 144](docs/09-contracts/04-source-content-contracts.md#L144) bắt buộc ID/source/run refs, URL, thời gian và provenance cho mọi package. Nhưng acceptance cuối cùng của cùng tài liệu yêu cầu package thiếu trường bắt buộc vẫn lưu incomplete; [test strategy, dòng 315](docs/10-test-strategy.md#L315) xác nhận cả thiếu trường cấu trúc lẫn title/main text rỗng đều chuyển `REJECTED_INCOMPLETE`.

**Tình huống:** Payload thiếu source/run ref hoặc ID được xử lý như bài trích xuất thiếu nội dung. Nếu vẫn chuyển sang B thì không đủ định danh/provenance cho lưu trữ và retry; nếu validator từ chối thì lại trái test đang viết.

**Tác động:** Hai cách triển khai đều có thể viện dẫn tài liệu nhưng hành vi giao tiếp không tương thích; có nguy cơ lưu bản ghi không truy được nguồn hoặc retry không ổn định.

**Thay đổi nhỏ nhất đề xuất:** Tách lỗi schema/envelope ở biên nhận khỏi package hợp lệ về cấu trúc nhưng nội dung không đủ. Trường hợp thứ nhất trả lỗi validation có cấu trúc và ghi quan sát lỗi bằng định danh hợp lệ; trường hợp thứ hai mới được lưu `incomplete` để B quyết định. Không tự điền nguồn hoặc ID còn thiếu như thể đã xác minh.

**Tài liệu cần đồng bộ:** Contracts `04` và quy tắc lỗi `00`; module A spec/plan; test strategy. Đồng thời kiểm tra điều kiện title bắt buộc với từng source kind: chưa nên coi mọi social source có title riêng khi source-kind policy vẫn đang mở.

**Điều kiện đóng:** Test riêng payload thiếu ID/source ref, extraction lỗi có đủ provenance, bài thiếu text và nội dung không có title theo source-kind policy. Mỗi trường hợp có điểm từ chối/lưu, owner và disposition duy nhất. Chặn implementation package boundary tới khi thống nhất.

### 10.6. Trạng thái từng issue gốc sau hậu kiểm

| Issue gốc | Kết quả hiện hành | Căn cứ/khoảng còn lại |
|---|---|---|
| AUD-B01 | Đóng ở cấp tài liệu | Thumbnail đã ở trong hook; contract và QC có ràng buộc thời gian. |
| AUD-B02 | Đóng ở cấp tài liệu | Periodic identity không chứa policy revision; giữ business-date của lượt. |
| AUD-B03 | Đóng ở cấp tài liệu | Epoch mới trước mở writer; grant/result/receipt có kiểm tra epoch. Chưa chứng minh restore runtime. |
| AUD-B04 | Đóng phần atomic usage; còn BLOCKER liên quan | UoW C/G đã rõ; giao thức chống trùng đồng thời còn thiếu: AUD2-B01. |
| AUD-M01 | Đóng ở cấp tài liệu | Folder dùng YY-MM-DD, hậu tố phiên và không tạo folder sản phẩm rỗng. |
| AUD-M02 | Chưa đóng hết | Tách attempt/run đúng; thiếu terminal path khi không còn được retry: AUD2-M01. |
| AUD-M03 | Đóng ở cấp tài liệu | English evidence gắn revision và category xử lý ảnh đã được bổ sung; không mở sang clip. |
| AUD-M04 | Đóng ở cấp tài liệu | Capacity reservation nguyên tử giải quyết vượt target; không được hiểu là content reservation. |
| AUD-M05 | Chưa đóng hết | Có owner/package/candidate contract, nhưng còn AUD2-M02 và AUD2-M03. |
| AUD-M06 | Đóng ở cấp tài liệu | Trust boundary, untrusted data, resolver/allowlist và security corpus đã được nối vào contract/test. |
| AUD-N01 | Đóng yêu cầu bổ sung crosswalk | Crosswalk đã có; sự tồn tại của crosswalk không thay thế kiểm tra semantics, race và error paths. |

### 10.7. Thứ tự xử lý và giới hạn kết luận

1. Đóng AUD2-B01 trước khi mở cổng code vì liên quan bất biến liên phân hệ.
2. Đóng AUD2-M01 và AUD2-M03 trước các lát cắt retry/package của module A; đóng AUD2-M02 trước auto-registration. Khuyến nghị hoàn tất cả ba trước code để tránh lệch contract.
3. Đồng bộ test và crosswalk theo từng sửa đổi, sau đó hậu kiểm lại các tình huống cụ thể nêu trên.

Không có căn cứ từ hậu kiểm này để thay 10 phân hệ, topology hybrid, PostgreSQL/Drive hoặc thêm dịch vụ mới. Các lựa chọn Conditional G01–G07 vẫn chờ bằng chứng theo roadmap; báo cáo không coi chúng đã đạt, cũng không đòi benchmark sản phẩm hoàn chỉnh trước dòng code thử nghiệm đầu tiên. **Chưa sửa kỹ thuật và chưa được phép viết code.**

## 11. Khắc phục hậu kiểm theo yêu cầu người dùng

### 11.1. Xác minh và thay đổi nhỏ nhất

Đã kiểm tra lại bốn nhận xét trước khi sửa. Cả bốn hợp lý trong phạm vi hợp đồng, không phải bằng chứng lỗi phần mềm đang chạy. B01 không phủ nhận bản sửa atomic MediaUsage; M02 không khẳng định có thể vượt tombstone. Không redesign topology, thêm service/database hoặc cài công nghệ.

| Issue | Kết quả xác minh | Tài liệu bị ảnh hưởng | Thay đổi đã áp dụng | Bằng chứng đóng ở cấp tài liệu |
|---|---|---|---|---|
| AUD2-B01 — BLOCKER | Hợp lý: capacity reservation không bảo vệ nội dung; validation có thể cũ khi completion | Data model, data flow, architecture, ADR-0004; contracts README/00/06/09/12/13; test strategy, roadmap | G sở hữu VariantReservation riêng và registry revision theo workspace; D validation gắn lịch sử/active reservations, exact output. Reserve/complete dùng CAS trong transaction ngắn, không gọi AI trong khóa; stale đối chiếu lại, conflict thực kết thúc job, retry giữ identity, WAITING không tự release. | CT-ORC-012/008 và CT-AI-008 thống nhất; TST-WF-VAR-001..004 có oracle race, stale, lost ACK, output binding. **ĐÓNG Ở TÀI LIỆU**. |
| AUD2-M01 — MAJOR | Hợp lý: WAITING_RETRY không có terminal path khi hết quyền retry | Data model; contracts 00/04/12/13; module A spec/plan; test strategy, roadmap | Bảng transition thêm hết budget/deadline, nguồn inactive, reconcile retryable/success/final; partial giữ package đã commit. Unknown append evidence và chờ có log/cảnh báo, không bịa kết quả. | CT-STATE-002 và A2 dùng cùng oracle; TST-COL-END-001..004. **ĐÓNG Ở TÀI LIỆU**. |
| AUD2-M02 — MAJOR | Hợp lý: Source được bảo vệ nhưng candidate READY thiếu đường resolved khi registration gặp dữ liệu mới | Data model; contracts 02/04/12/13; module A spec/plan; test strategy, roadmap | READY được chuyển REGISTERED/MATCHED_EXISTING/BLOCKED_TOMBSTONE/REJECTED sau kiểm tra nguyên tử identity/policy; candidate/source/receipt/outbox cùng transaction. WAITING_POLICY không giả thành terminal; lost ACK trả receipt cũ. | CT-SRC-003A/CT-STATE-002A/event thống nhất; TST-SRC-RACE-001..004 tại A6. **ĐÓNG Ở TÀI LIỆU**. |
| AUD2-M03 — MAJOR | Hợp lý: acceptance/test đánh đồng schema invalid với content incomplete | Data model; contracts 00/02/04/12/13; module A spec/plan; test strategy, roadmap | Sai cấu trúc trả VALIDATION_ERROR trước document handoff, chỉ ghi quan sát lỗi an toàn. Đúng schema nhưng thiếu nội dung mới incomplete. Title theo source-kind policy, thiếu policy không tự chọn mặc định. | CT-SRC-006 và boundary/state/test cùng semantics; TST-COL-PKG-001..004 tại A4. **ĐÓNG Ở TÀI LIỆU**. |

### 11.2. Kiểm tra đồng bộ và giới hạn

- Kiểm tra tĩnh 44 tệp Markdown: UTF-8 hợp lệ, không ký tự thay thế hoặc code fence lẻ, không đường dẫn đích Markdown bị thiếu. 16 ID test mới có đủ định nghĩa và không trùng. Tìm kiếm các câu mâu thuẫn cũ về package/retry/title và tham chiếu CT-CMN-014 không còn kết quả trong docs. Đây là kiểm tra cấu trúc hỗ trợ việc đọc chéo, không chứng minh semantics runtime.
- Bổ sung 16 ca kiểm thử đặc tả tại mục 34 test strategy, nối từng nhóm với contract và exit gate module/roadmap; chưa viết hoặc chạy test code.
- Không thay mục tiêu sản phẩm, phạm vi xử lý ảnh, quyền người dùng, provider hoặc 10 phân hệ. Giá trị retry/backoff, source-kind policy và benchmark vẫn phải chốt theo gate hiện có; không coi fixture test là cấu hình production đã duyệt.
- Chấp nhận đánh đổi kỹ thuật có phạm vi hẹp: revision workspace có thể gây stale vì thay đổi không liên quan. ADR-0004 ghi rõ lý do dùng khóa metadata ngắn ở baseline một người dùng và điều kiện tối ưu sau này. Không giữ khóa qua AI/render.
- Sửa hai tham chiếu nhất quán khi đối chiếu: crosswalk không còn trỏ CT-CMN-014 không tồn tại mà trỏ mục 14 common contract; dòng tổng kết data model không còn nói nơi lưu chính chưa quyết định sau khi bước 08 đã chọn PostgreSQL.
- Mục 9 và 10 được giữ làm lịch sử; trạng thái hiện hành là mục 11. Các con số lịch sử không cộng thành số lỗi hiện còn mở.

**Kết luận giới hạn:** Bốn khoảng thiếu được nêu trong hậu kiểm đã có hợp đồng, đường lỗi, ownership và oracle kiểm thử tương ứng. Đây không phải chứng nhận toàn hệ thống không còn lỗi hoặc G01–G07 đã đạt. Không tạo mã nguồn, không cài thư viện; chỉ thực hiện cập nhật tài liệu theo yêu cầu lần này.

## 12. Hậu kiểm M1 trước dòng code đầu tiên và kết quả khắc phục

### 12.1. Phạm vi

Đã kiểm tra chéo checklist, roadmap, version lock, M1 implementation plan, evidence protocol, test strategy và ADR liên quan. Năm nhận xét MAJOR dưới đây đều hợp lý; chúng là khoảng thiếu trong cách diễn đạt proof/gate và kế hoạch kiểm thử, không yêu cầu redesign topology hay thay công nghệ.

### 12.2. Bảng giải quyết issue

| Issue | Tài liệu bị ảnh hưởng | Thay đổi nhỏ nhất đã áp dụng | Trạng thái |
|---|---|---|---|
| `AUD3-M01` — M1 có thể bị hiểu là đóng toàn bộ G01/G04 | M1 plan, roadmap, test strategy, ADR index, ADR-0003, ADR-0006, checklist, version lock | Tách `PASS_M1_SCOPE` khỏi `PARTIALLY_PROVEN` và PASS toàn phần. P2 thêm replay qua revision workflow tương thích; upgrade Server/SDK để M2-M7. P3 chỉ chứng minh Drive/OAuth slice; local HTTPS/Origin, Temporal authorization và account pool để M2-M7. | **ĐÃ GIẢI QUYẾT** |
| `AUD3-M02` — P1 thiếu proof completion Unit of Work cho INV-010/017 | M1 implementation plan | Thêm `TST-M1-P1-009/010` cho ledger, capacity reservation/count, `MediaUsage` qua owner port C, outbox, crash boundary và lost ACK/duplicate. Không dựng video pipeline. | **ĐÃ GIẢI QUYẾT** |
| `AUD3-M03` — Thứ tự bootstrap/evidence/RED mâu thuẫn | Version lock, M1 plan, evidence README, checklist | Tách `bootstrap.json` trước test, `environment.json` là output sau RED và `manifest.json` chỉ tổng hợp tại P6. RED P0 chỉ hợp lệ khi environment output thiếu/sai, không phải setup/import lỗi. | **ĐÃ GIẢI QUYẾT** |
| `AUD3-M04` — P1 phụ thuộc PostgreSQL smoke ở P5 tạo vòng thời gian | Version lock, M1 plan, checklist | Đưa preflight PostgreSQL kết nối/`SELECT 1`/rollback/UTF-8 vào điều kiện PASS P0. P5 chỉ kiểm compatibility rộng và recheck; P1 chỉ phụ thuộc P0. | **ĐÃ GIẢI QUYẾT** |
| `AUD3-M05` — RED, defect, FAIL, STOP và ADR reopening bị trộn | M1 plan, test strategy, checklist | Định nghĩa `RED_CONFIRMED`, `CORRECTION_REQUIRED`, `FAIL`, `STOPPED`; setup failure không phải RED. Chỉ mở ADR khi root-cause evidence phủ định kiến trúc; lỗi version đi theo R2 trước. | **ĐÃ GIẢI QUYẾT** |

### 12.3. Trạng thái cổng sau khắc phục

| Hạng mục | Trạng thái |
|---|---|
| M0 DESIGN | `APPROVED` |
| PCC-026 | `CLOSED` |
| PCC-027 | `CLOSED — M1 ONLY` |
| ROADMAP-OPEN-002 | `CLOSED_FOR_M1_R1` |
| M1 | `READY TO START` |
| G01 Temporal | `NOT TESTED` |
| G04 Drive/OAuth | `NOT TESTED` |
| ROADMAP-OPEN-003 | `OPEN — BLOCKS M1-P3 ONLY` |
| M2 | `NOT AUTHORIZED` |
| M3 / Module A | `NOT AUTHORIZED` |

### 12.4. Kết luận giới hạn

Không còn BLOCKER hoặc MAJOR đã biết trong kế hoạch M1 trước khi bắt đầu P0. Đây là kết luận ở cấp tài liệu, không phải bằng chứng runtime. G01/G04 chưa được thử; M1 chưa bắt đầu và chưa PASS. Không có mã nguồn, dependency, lockfile hay evidence run nào được tạo trong lượt khắc phục này. Dự án chỉ ở trạng thái sẵn sàng chờ lệnh bắt đầu M1-P0; M2, M3 và Module A tiếp tục bị khóa.
