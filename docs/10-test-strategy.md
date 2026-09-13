# AI Auto Video Creator - Chiến lược kiểm thử trước khi code

**Tệp:** `docs/10-test-strategy.md`  
**Trạng thái:** Đã được user phê duyệt làm baseline; chưa có test code hoặc kết quả runtime tại thời điểm phê duyệt  
**Ngày lập:** 12-09-2026  
**Phạm vi:** toàn bộ 10 phân hệ A-J, các hợp đồng liên phân hệ và các cổng kiến trúc G01-G07  
**Giai đoạn:** trước khi có mã nguồn, test code, test framework hoặc môi trường triển khai

## 1. Mục đích

Tài liệu này xác định cách chứng minh hệ thống làm đúng điều đã đặc tả và đạt đúng mức chất lượng đã phê duyệt. Nó trả lời:

1. Cần kiểm thử những hành vi và rủi ro nào?
2. Kiểm thử ở cấp nào, trong môi trường nào và bằng dữ liệu gì?
3. Kết quả nào là đạt, không đạt hoặc chưa đủ bằng chứng?
4. Bằng chứng nào được phép dùng để đóng từng quality requirement và architecture gate?
5. Khi bắt đầu lập trình, test nào phải được viết trước implementation tương ứng?

Tài liệu này **không phải test code** và không khẳng định bất kỳ yêu cầu hay gate nào đã đạt.

## 2. Nguồn sự thật dùng để thiết kế kiểm thử

Thứ tự ưu tiên khi xác định expected behavior:

1. Quyết định người dùng đã xác nhận trong [00-project-charter.md](./00-project-charter.md) và [01-product-spec.md](./01-product-spec.md).
2. Yêu cầu dữ liệu và chất lượng trong [02-data-model.md](./02-data-model.md) và [03-quality-requirements.md](./03-quality-requirements.md).
3. Luồng, phân hệ và kiến trúc trong [06-system-map.md](./06-system-map.md), [07-data-flow.md](./07-data-flow.md) và [08-architecture.md](./08-architecture.md).
4. ADR trong [adr/README.md](./adr/README.md).
5. Hợp đồng và invariant trong [09-contracts/README.md](./09-contracts/README.md).

Nếu test phát hiện hai tài liệu cho expected behavior khác nhau, đó là **lỗi đặc tả**. Không được chọn tùy ý một cách hiểu rồi viết test.

## 3. Nguyên tắc bắt buộc

### TEST-PRINCIPLE-001 — Test trước implementation

Khi giai đoạn code được phép bắt đầu:

1. Viết test thể hiện hành vi mong muốn.
2. Chạy test và xác nhận nó thất bại vì hành vi chưa được cài đặt, không phải vì test sai cú pháp hoặc môi trường hỏng.
3. Chỉ sau đó mới viết implementation tối thiểu để test đạt.
4. Chạy lại test liên quan và regression suite.
5. Refactor chỉ khi test vẫn đạt.

Không viết test để hợp thức hóa hành vi đã code xong. Ngoại lệ duy nhất sau này là characterization test cho mã cũ chưa có test; ngoại lệ phải được ghi rõ trong test run.

### TEST-PRINCIPLE-002 — Kiểm thử hành vi, không khóa chi tiết cài đặt

Test phải quan sát input, output, state transition, side effect và bằng chứng đã commit. Không phụ thuộc tên hàm nội bộ, cấu trúc private hoặc câu lệnh SQL nếu chúng không phải hợp đồng.

### TEST-PRINCIPLE-003 — Mỗi test có oracle rõ ràng

Mỗi test case phải nêu:

- precondition;
- input và revision/fingerprint;
- hành động;
- kết quả mong đợi;
- side effect được phép;
- side effect bị cấm;
- bằng chứng cần thu;
- cách cleanup dữ liệu thử.

Test không có oracle xác định được không được dùng làm gate.

### TEST-PRINCIPLE-004 — Không biến retry thành cách che lỗi

- Test fail lần đầu vẫn là fail.
- Rerun chỉ dùng để chẩn đoán flakiness, không tự đổi kết luận sang pass.
- Test không ổn định phải được cách ly, có owner và thời hạn sửa; không được âm thầm loại khỏi gate.
- Retry của hệ thống phải được kiểm tra như hành vi nghiệp vụ, không phải retry của test runner.

### TEST-PRINCIPLE-005 — Bằng chứng phải tái tạo được

Kết quả chỉ có giá trị khi ghi đủ phiên bản, cấu hình, dữ liệu, seed nếu có, môi trường, phần cứng, thời gian, dependency/provider và test run ID. Screenshot hoặc video đơn lẻ không thay cho assertion và artifact evidence.

### TEST-PRINCIPLE-006 — Mock không được chứng minh tích hợp thật

Mock/fake dùng để kiểm tra logic xác định và failure injection. Không được dùng để đóng gate về Google Drive, OAuth, quota, Temporal replay, model AI, FFmpeg output, desktop recovery hoặc hiệu năng thực tế.

### TEST-PRINCIPLE-007 — Không hạ ngưỡng để làm test đạt

Nếu hệ thống không đạt ngưỡng đã phê duyệt, sửa hệ thống, dữ liệu hoặc kiến trúc. Mọi đề nghị đổi ngưỡng phải quay lại tài liệu yêu cầu và người dùng phê duyệt trước.

## 4. Những điều không được tuyên bố ở bước này

- Chưa chọn test framework, browser automation tool, load tool hoặc security scanner.
- Chưa tạo test file hoặc fixture thực thi.
- Chưa có baseline hiệu năng.
- Chưa chứng minh 100 video/12 giờ, 95% tự động, 99% lịch chạy hay ngân sách dưới 50 USD/tháng.
- Chưa chứng minh model AI, TTS, word timing hoặc xử lý ảnh đạt chất lượng.
- Chưa chứng minh Drive, OAuth, Temporal hoặc restore hoạt động an toàn.
- Chưa có code coverage thực tế.

Việc lựa chọn công cụ kiểm thử chỉ diễn ra sau khi cấu trúc dự án và version runtime được khóa, dựa trên stack đã duyệt và khả năng chạy trong CI/máy mục tiêu.

## 5. Mô hình các cấp kiểm thử

Không dùng một “test pyramid” cứng cho toàn hệ thống. Hệ thống có logic xác định, workflow phân tán, media thực và AI xác suất nên cần nhiều lớp bổ sung nhau.

| Cấp | Mục tiêu | Dependency thật | Tốc độ kỳ vọng | Dùng để đóng gate |
|---|---|---:|---:|---|
| Tài liệu/schema tĩnh | Bắt lỗi đặc tả, ID, link, schema và compatibility | Không | Rất nhanh | Chưa đủ một mình |
| Unit/domain | Quy tắc thuần, state transition, fingerprint, policy | Không | Rất nhanh | Một phần invariant |
| Component | Một phân hệ qua public port với storage/provider fake | Có kiểm soát | Nhanh | Hành vi phân hệ |
| Contract | Producer/consumer, schema, version, error và event semantics | Adapter fake/real tùy test | Nhanh-trung bình | Hợp đồng A-J |
| Integration | DB, workflow, artifact, API và adapter kết hợp | Có | Trung bình | Một phần G01/G04/G07 |
| System/E2E | Luồng user và pipeline từ đầu đến output | Gần thật | Chậm | Quality gate chức năng |
| Fault/recovery | Crash, duplicate, reorder, offline và outcome unknown | Gần thật | Chậm | G01/G04/G05 |
| Media/output | Byte, codec, audio, subtitle, timing và render | Tool/máy thật | Chậm | G02/G06/G07 |
| AI evaluation | Phân loại, liên kết, chọn media, script và safety | Model thật | Biến động | G06 |
| Security | Trust boundary, secret, SSRF, path, auth và isolation | Gần thật | Trung bình-chậm | G04/G07 |
| Performance/soak | Throughput, latency, capacity, leak và ổn định | Mục tiêu thật | Rất chậm | G02/G07 |
| Restore/DR | Backup, restore cách ly và reconcile | Hạ tầng thật | Rất chậm | G05 |
| User acceptance | Mức phù hợp nội dung/media/hook và trải nghiệm | User + output thật | Theo phiên | G06/G07 |

## 6. Cách đặt mã test và liên kết truy vết

### 6.1. Prefix

| Prefix | Nhóm |
|---|---|
| `TST-DOC-*` | Tài liệu và schema |
| `TST-UNIT-*` | Unit/domain |
| `TST-COMP-*` | Component |
| `TST-CTR-*` | Contract producer/consumer |
| `TST-INT-*` | Integration |
| `TST-WF-*` | Workflow, replay và fault injection |
| `TST-E2E-*` | Luồng đầu-cuối |
| `TST-AI-*` | Chất lượng AI/nội dung |
| `TST-MEDIA-*` | Media, TTS, subtitle và render |
| `TST-SEC-*` | Bảo mật |
| `TST-PERF-*` | Hiệu năng, tải và soak |
| `TST-DR-*` | Backup/restore/recovery |
| `TST-UX-*` | UI, accessibility và thao tác |
| `TST-COST-*` | Chi phí và quota |

### 6.2. Quan hệ bắt buộc

Mỗi test case phải liên kết ít nhất một trong:

- `FR-*` hoặc quyết định R01-R25;
- `QR-*`;
- `ARCH-GATE-*`/G01-G07;
- `CT-*`;
- `INV-*`;
- một defect/regression ID.

Mỗi requirement/invariant đã chốt phải có ít nhất một test tích cực và một test tiêu cực hoặc failure case phù hợp. Requirement không thể test tự động phải có protocol đánh giá thủ công và evidence schema.

### 6.3. Ma trận phủ các nhóm yêu cầu chất lượng

| Nhóm yêu cầu | Suite chính | Bằng chứng quyết định | Điểm chưa được tự chốt |
|---|---|---|---|
| `QR-PERF-001..008` | TST-PERF, TST-E2E | Ledger/output đã verify, latency distribution, resource timeline | Quy mô bảng và thời gian vòng thu thập |
| `QR-REL-001..009` | TST-WF, TST-E2E | Fault timeline, state/log reconciliation, auto-completion ratio | Retry/timeout từng phân hệ |
| `QR-AVL-001..006` | TST-WF, TST-DR | Schedule records, offline/resume evidence, recovery report | Thời gian fallback AI cụ thể |
| `QR-DATA-001..010` | TST-UNIT, TST-CTR, TST-AI | Provenance chain, revision diff, evaluation set | Ngưỡng/cách đo dedup |
| `QR-CONT-001..007` | TST-AI, user acceptance | Locked sample, rubric và đánh giá user | Proxy hot/trending; không cam kết viral |
| `QR-SAFE-001..006` | TST-AI, TST-MEDIA | Labeled image set, recall/error breakdown, transform evidence | Sample plan chi tiết |
| `QR-OUT-001..008` | TST-MEDIA, TST-E2E | Probe, timeline/QC report, listening review | Output profile và timing error threshold |
| `QR-UX-001..008` | TST-UX, TST-PERF | UI state tests, viewport evidence, latency distribution | Quy mô bảng và thao tác chi tiết |
| `QR-OBS-001..006` | TST-E2E, TST-WF | Session/job/source trace, error/warning log coverage | Log retention |
| `QR-SEC-001..009` | TST-SEC | Security report, canary scan, auth/scope/role evidence | Tool triển khai cụ thể |
| `QR-COST-001..006` | TST-COST, TST-PERF | Usage/cost reconciliation, budget forecast, disk metrics | Cost/video riêng chưa có ngưỡng |
| `QR-SCALE-001..006` | TST-PERF, TST-INT | Growth dataset, query/queue/storage behavior, adapter replacement | Scale dataset và SaaS SLA ngoài v1 |
| `QR-MNT-001..007` | TST-CTR, TST-INT, TST-DR | Contract compatibility, history/revision trace, replacement test | Thời gian thay thành phần định lượng |
| `QR-COMP-001..006` | TST-MEDIA, TST-UX, TST-CTR | Target machine/version manifest, UTF-8/path/profile results | Version matrix và output profile |

Các range trong bảng là chỉ mục truy vết, không có nghĩa mọi mã trong range dùng cùng một test. Test catalog triển khai phải ánh xạ từng mã `QR-*` riêng lẻ.

## 7. Vòng đời test case

| Trạng thái | Ý nghĩa |
|---|---|
| `DRAFT` | Đang thiết kế, chưa review oracle |
| `REVIEWED` | Expected behavior đã đối chiếu tài liệu |
| `READY_FOR_RED` | Đủ dữ liệu/môi trường để viết test code |
| `RED_CONFIRMED` | Test thất bại đúng lý do trước implementation |
| `GREEN` | Implementation làm test đạt |
| `BLOCKED_EXTERNAL` | Không thể chạy vì provider/hạ tầng ngoài; không tính pass |
| `QUARANTINED` | Test flaky hoặc oracle không đáng tin; không được dùng đóng gate |
| `RETIRED` | Requirement bị thay thế có ADR/decision ref |

Không có trạng thái “pass có điều kiện”. Nếu thiếu bằng chứng, kết luận là `NOT_PROVEN`.

## 8. Chiến lược dữ liệu kiểm thử

### 8.1. Các bộ dữ liệu

| Bộ | Mục tiêu | Tính chất |
|---|---|---|
| `Contract Fixtures` | Schema, enum, version, field missing/null, error | Nhỏ, xác định, lưu cùng test |
| `News Corpus` | Extraction, chuẩn hóa, topic, provenance | Bao phủ các nhóm chủ đề sản xuất đã chốt |
| `Duplicate Clusters` | Exact duplicate, near duplicate, repost, revision, media-only | Có bài đại diện và expected disposition |
| `Event Timeline Set` | Liên kết sự kiện và diễn biến mới | Có trường hợp gộp đúng, giữ riêng, repost và update thật |
| `Media Corpus` | Ảnh, clip, audio, hook, metadata và codec | Có file hợp lệ, hỏng, thiếu metadata và biên kỹ thuật |
| `Sensitive Image Set` | Trẻ em, máu me, vũ khí và ảnh an toàn | Có nhãn người đánh giá, gồm ca khó và lỗi đọc |
| `Creative Evaluation Set` | Góc kể, script, inference, media/hook | Không dùng làm ví dụ prompt nếu dùng để nghiệm thu model |
| `Render Golden Set` | Timeline, subtitle, audio mix, preset | Có expected structural evidence, không chỉ so pixel tuyệt đối |
| `Security Corpus` | URL/path/payload độc hại, indirect prompt injection và secret canary | Không chứa secret thật; có bài/metadata/OCR giả làm system instruction |
| `Scale Dataset` | Bảng, tìm kiếm, queue, artifact và lịch sử dài hạn | Kích thước được chốt sau `QUALITY-OPEN-011` |

### 8.2. Quản trị golden set

- Mỗi item có ID, version, nguồn, quyền truy cập nội bộ, nhãn và người/tiến trình gắn nhãn.
- Golden set là immutable theo version; sửa nhãn tạo revision mới.
- Tách dữ liệu dùng để phát triển prompt/model khỏi tập nghiệm thu để tránh leakage.
- Ca lỗi và ca không chắc chắn phải nằm trong mẫu; không được loại để nâng tỷ lệ.
- Mẫu phải bao phủ đủ các chủ đề đang bật, Tier, loại nguồn, loại media và tình trạng dữ liệu.
- Kết quả AI lưu exact model, prompt, config và input revision.
- Dữ liệu nguồn thay đổi ngoài Internet không làm thay golden snapshot của regression test.

### 8.3. Dữ liệu thật và dữ liệu tổng hợp

- Dữ liệu tổng hợp dùng cho schema, bảo mật, boundary và lỗi khó tái tạo.
- Dữ liệu thật đã snapshot dùng cho extraction, dedup, event, media, AI và render.
- Không dùng duy nhất dữ liệu “đẹp”; phải có timeout, HTML lỗi, redirect, ảnh hỏng, media thiếu và nội dung mơ hồ.
- Không dùng production API key, refresh token hoặc dữ liệu secret trong fixture.

### 8.4. Kích thước mẫu

Số lượng item tối thiểu cho các phép đánh giá 90%/95% hiện **CHƯA QUYẾT ĐỊNH**. Trước khi chạy G06 phải lập sampling plan nêu:

- population và đơn vị tính;
- cách phân tầng theo chủ đề/nguồn/loại media;
- cách chọn ngẫu nhiên;
- cách xử lý bất đồng người đánh giá;
- khoảng thời gian lấy dữ liệu;
- số lượng mẫu và lý do đủ tin cậy.

Không được chọn số mẫu sau khi đã xem kết quả.

## 9. Test oracle theo loại hành vi

### 9.1. Hành vi xác định

Áp dụng assertion chính xác cho:

- state transition;
- idempotency/deduplication;
- revision/fingerprint/hash;
- quyền owner ghi;
- Tier và bài đại diện;
- điều kiện timeline narrative;
- completion count;
- filename/path;
- secret redaction;
- duration, codec và artifact existence.

### 9.2. Hành vi xác suất

AI/content/media selection dùng ba lớp oracle:

1. Structural validator: schema, provenance, required fields, claim mode và constraint.
2. Deterministic policy checker: điều cấm/bắt buộc như khác góc, disclosure, hook/thumbnail.
3. Human evaluation trên mẫu đã khóa cho tiêu chí phù hợp/chất lượng.

Không dùng duy nhất chính model tạo nội dung làm judge cho output của nó. AI-assisted review chỉ hỗ trợ sàng lọc; kết luận ngưỡng người dùng đã duyệt phải theo protocol G06.

### 9.3. Media oracle

- Probe/decode thay cho kiểm tra extension.
- Hash/size và lineage thay cho tên file.
- Timeline evidence thay cho chỉ kiểm tra production plan.
- Audio measurement kết hợp nghe mẫu cho intelligibility.
- Karaoke kiểm tra cả data timing và output đã burn-in.
- Golden frame dùng tolerance có kiểm soát khi codec/render có sai khác; không dùng so pixel tuyệt đối cho mọi video.

## 10. Môi trường kiểm thử

| Môi trường | Mục tiêu | Dữ liệu | Có được đóng gate production? |
|---|---|---|---:|
| `E0 Static` | Lint docs/schema và compatibility | Fixture | Không |
| `E1 Isolated` | Unit/component nhanh | Fixture/synthetic | Không |
| `E2 Integrated` | PostgreSQL/workflow/API/storage adapter trong môi trường cô lập | Snapshot dataset | Một phần |
| `E3 Provider Sandbox` | API/AI/OAuth/Drive thật với tài khoản test | Dataset kiểm soát | Một phần G04/G06 |
| `E4 Target Desktop` | Media, render, recovery và UI trên máy mục tiêu | Representative workload | G02/G07 |
| `E5 Pre-production Hybrid` | Cloud + desktop như kiến trúc thật | Representative workload | G01-G04/G07 |
| `E6 Isolated Restore` | Backup/restore/reconcile | Backup test | G05 |

Mỗi môi trường phải có inventory version và không chia sẻ secret hoặc dữ liệu ghi với production thật.

## 11. Test doubles và giả lập lỗi

### 11.1. Loại test double

- Fake repository cho domain/component test.
- Stub provider trả response đã khóa.
- Fault proxy để tạo timeout, disconnect, rate limit và partial transfer.
- Fake clock cho schedule, expiry, backoff và retention.
- Deterministic AI response fixture cho workflow/contract test.
- Real provider/model cho quality gate.

### 11.2. Quy tắc

- Test double phải tuân cùng contract version như adapter thật.
- Contract suite chạy cho cả fake và adapter thật để tránh fake “dễ tính” hơn production.
- Fault phải được tạo ở trước, trong và sau side effect.
- Không mock chính logic đang được kiểm tra.
- Không coi test với fake clock là bằng chứng 99% lịch chạy trong tháng.

## 12. Chiến lược theo phân hệ

### 12.1. A — Nguồn và thu thập nội dung

Phải kiểm tra:

- canonicalization và provenance qua redirect;
- RSS, trang bài và lỗi extraction đại diện;
- một nguồn quét định kỳ không quá một lần/cycle ngày;
- đổi policy revision trong cùng business date, chạy hai scheduler hoặc retry không tạo periodic run thứ hai;
- `FAILED_RETRYABLE` chỉ đưa run sang WAITING_RETRY khi policy/nguồn cho phép; hết budget hoặc source inactive áp dụng terminal partial/final CT-STATE-002; OUTCOME_UNKNOWN chờ reconcile và append evidence; terminal không mở lại;
- SourceCandidate trùng/tombstone/rejected không tạo Source, candidate thiếu Tier/discovery policy không tự active;
- package sai cấu trúc bị VALIDATION_ERROR trước document handoff; package đúng schema nhưng nội dung không đủ theo source-kind policy mới incomplete/REJECTED_INCOMPLETE; title không có mặc định chung cho mọi source kind;
- chỉ mở Tier tiếp theo khi chủ đề chưa đạt ngưỡng tin mới không trùng;
- article đa chủ đề chỉ tăng một lần cho từng topic/business-date và không bị cộng thành tổng tin duy nhất;
- nguồn đang bật có thể không được quét vì đã đủ ngưỡng;
- tìm media bổ sung theo video không bị tính là lượt quét định kỳ;
- source disabled/removed không được thu thập hoặc auto-add lại;
- restore về trạng thái hợp lệ;
- một nguồn lỗi không dừng nguồn khác;
- partial run giữ document đã commit và cursor đúng;
- SSRF, redirect loop, nội dung quá lớn và MIME giả.

### 12.2. B — Kho nội dung và tri thức sự kiện

Phải kiểm tra:

- `NEW_ARTICLE`, `NEW_REVISION`, `DUPLICATE_MEDIA_ONLY`, `DUPLICATE_NO_NEW_VALUE`, `REJECTED_INCOMPLETE`;
- bài trùng không tạo Article/Script mới nhưng media/provenance mới được giữ;
- ưu tiên representative theo Tier;
- cùng Tier giữ representative ổn định, phá hòa bằng `source_id`;
- liên kết không làm mất danh tính bài độc lập;
- bài repost/nguồn mới không trở thành diễn biến mới;
- chỉ `EventUpdateAccepted` cấp quyền cho “từ lúc đó đến nay”;
- không bắt buộc fact-check đa nguồn nhưng luôn truy được nguồn;
- revision mới không làm video cũ thay đổi.

### 12.3. C — Danh mục media và hook

Phải kiểm tra:

- cùng byte nhiều provenance và một media nhiều rendition;
- visual hook/audio hook độc lập;
- metadata update không sửa byte;
- candidate query trả score components, provenance, availability, safety và risk;
- media lịch sử vẫn dùng được sau khi source bị remove;
- `MediaUsage` chỉ thành production usage trong cùng completion transaction; ledger và usage cùng commit hoặc cùng rollback;
- artifact missing/corrupt không được trả là renderable;
- visual hook, audio hook và thumbnail trong vùng hook đều có candidate/selection phù hợp.

### 12.4. D — Trí tuệ nội dung

Phải kiểm tra:

- snapshot commit trước script và không đổi input/config sau đó;
- source-backed, inference, creative hypothesis và transition được phân loại;
- 100% đoạn inference/creative có disclosure trong representation/output;
- 1-3 video cùng lượt khác góc kể;
- lượt sau không trùng hoàn toàn và khác ít nhất một yếu tố thực tế;
- không dùng lại script gần nhất;
- hết angle set có thể quay lại tạo set mới;
- single article, multi-article event và from-then-to-now đúng eligibility;
- media/hook selection có rationale và exact refs;
- output metadata tiếng Anh, title/caption và 3-4 hashtag;
- provider fallback không làm mất provenance hoặc revision.

### 12.5. E — Xử lý media, voice và subtitle

Phải kiểm tra:

- probe không tin extension/MIME khai báo;
- transform tạo artifact mới và giữ original;
- safety processing chỉ áp dụng ảnh, không áp clip;
- phát hiện trẻ em, máu me, vũ khí theo bộ mẫu;
- ảnh vũ khí đã nhận diện tạo transform request đúng category/config revision;
- `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED` vẫn có thể dùng ảnh đọc được nhưng không thành `SAFE`;
- một ảnh lỗi không dừng lô;
- voice gắn exact script fingerprint;
- word timing tăng đơn điệu, nằm trong duration và gắn exact voice hash;
- đổi script/voice làm timing cũ invalid;
- reusable rendition khác per-video temporary;
- audio normalization/mix không làm mất lời dẫn.

### 12.6. F — Preset, dựng video và QC

Phải kiểm tra:

- năm preset có revision và resolve deterministic trong cùng spec;
- render package khóa exact artifact/hash/revision;
- thiếu visual hook, audio hook, thumbnail trong vùng hook, voice hoặc timing thì fail sớm;
- path không thuộc staging root bị từ chối;
- render timeout sau side effect vào `OUTCOME_UNKNOWN` và được reconcile;
- mỗi output hoàn thành phát được và dài 61-70 giây;
- script, voice, subtitle, title và hashtag tiếng Anh; evidence phải gắn đúng revision, không chỉ tin metadata tự khai;
- hook visual, hook audio và thumbnail thực sự xuất hiện trong byte output; time range của thumbnail phải nằm trong time range hook;
- subtitle burn-in và karaoke timing theo từng từ;
- inference disclosure xuất hiện khi có điều kiện;
- F không tự đổi script/góc/asset ngoài fallback trong plan;
- render success hoặc QC pass chưa tự tạo completion.

### 12.7. G — Điều phối và quan sát vận hành

Phải kiểm tra:

- command lặp chỉ tạo một batch/job logic;
- child video lỗi không dừng batch;
- retry giữ job/snapshot/intent, variant tạo job mới;
- debug stage không auto-advance;
- desktop/AI offline đưa đúng stage vào waiting;
- công việc không cần AI vẫn tiếp tục;
- không tự thêm dịch vụ trả phí;
- stale execution generation không commit;
- target chỉ đếm `CompletionLedger` duy nhất;
- batch dừng đúng `COMPLETED_TARGET`, `COMPLETED_EXHAUSTED`, `WAITING_CAPABILITY` hoặc `FAILED_SYSTEM`;
- restart tiếp tục từ checkpoint, không quay lại tin đầu tiên;
- script/plan/voice không bắt đầu khi desktop production capability offline.

### 12.8. H — Giao diện quản trị

Phải kiểm tra:

- tiếng Việt và UTF-8 đúng trên toàn bộ label, lỗi và dữ liệu hiển thị;
- dùng được từ 1080p, không chồng lấn nội dung quan trọng;
- trải nghiệm bảng cho lọc, xem, chọn và sửa metadata cho phép;
- không có thao tác sửa article body, script hoặc event relation;
- hover/focus vào lỗi thấy thông tin cụ thể nhưng không lộ secret;
- trạng thái accepted/running/waiting/outcome unknown/succeeded/failed khác nhau rõ ràng;
- SSE reconnect, duplicate event và resync không làm UI sai state;
- 95% thao tác thông thường phản hồi hữu ích trong 2 giây;
- ACK lệnh bắt đầu/tạo lại trong 1 giây;
- local single-user không cần interactive login nhưng session, Host/Origin và CSRF protection vẫn hoạt động;
- mỗi module chính có lệnh debug riêng.

### 12.9. I — Lưu trữ, đồng bộ và vòng đời tệp

Phải kiểm tra:

- artifact identity độc lập filename/path;
- same byte retry quy về cùng version logic; byte khác tạo version mới;
- upload timeout đi qua outcome unknown và reconcile trước retry;
- cloud location chỉ verified khi integrity đạt;
- render chỉ dùng local artifact đã verify hash;
- working set gần lượt xử lý không vượt policy khoảng 5 video;
- prefetch và render không làm vượt disk/I/O admission;
- output local không xóa trước cloud verify và completion;
- cleanup cần đúng artifact, ledger, lease, path và recovery epoch;
- folder phiên rỗng không tồn tại như output folder hợp lệ;
- phiên đầu tiên có video hoàn thành dùng `YY-MM-DD`; phiên tiếp theo cùng ngày tăng `(1)`, `(2)`; qua năm không trùng folder ngày cũ;
- tên file có hashtag, Unicode, ký tự cấm, tên reserved và độ dài biên;
- restore/reconcile tìm được orphan, duplicate, missing và corrupt location.

### 12.10. J — Cấu hình, tài khoản và bí mật

Phải kiểm tra:

- config/prompt/policy revision immutable và truy ngược từ video;
- config mới chỉ áp dụng job chưa snapshot;
- secret không đọc lại từ UI/API;
- secret không có trong log, event, trace, workflow history hoặc error;
- desktop không lưu Drive refresh token dài hạn;
- credential ngắn hạn đúng scope/audience/expiry/revocation;
- account chỉ dùng vai trò được phép;
- không giả định bốn tài khoản có quota độc lập;
- rate limit tạo waiting/backoff, không tạo retry storm;
- chi phí chỉ tính phạm vi R20;
- cảnh báo dự báo ở 80% ngân sách, không tự dừng nếu chưa cấu hình;
- credential revoke thắng snapshot cũ.

## 13. Kiểm thử hợp đồng và schema

### 13.1. Mục tiêu

Contract test phải phát hiện producer và consumer hiểu khác nhau trước khi chạy E2E. Mỗi `CT-*` được dùng trong implementation phải có:

- schema hợp lệ;
- positive fixture;
- fixture thiếu field bắt buộc;
- fixture có field/enum mới mà consumer cũ phải xử lý an toàn;
- version không hỗ trợ;
- error mapping;
- owner/caller authorization;
- idempotency hoặc revision behavior nếu là mutation.

### 13.2. Ma trận hợp đồng nền

| Hợp đồng | Ca bắt buộc |
|---|---|
| `MessageEnvelope` | correlation/causation/workspace/time đầy đủ; không chứa secret |
| `CommandEnvelope` | key lặp cùng payload; key lặp payload khác; expected revision cũ |
| `CommandReceipt` | accepted khác completed; duplicate trả resource/receipt cũ |
| `ProblemDetail` | retryable đúng policy; UI detail an toàn; technical ref riêng |
| `ArtifactRef` | đúng/sai hash, version, media type, availability |
| Domain event | duplicate, reorder, missing revision, schema mới, replay |
| Activity request/result | grant hợp lệ, stale generation, input fingerprint khác |
| Operation receipt | succeeded reuse, failed retry, outcome unknown reconcile |
| Configuration bundle | revision/fingerprint ổn định và không chứa secret |
| Completion ledger | commit một lần, conflict khi cùng job nhưng output khác |

### 13.3. Compatibility

- Thay đổi additive phải được consumer version trước bỏ qua an toàn.
- Breaking change phải bị từ chối rõ bằng `UNSUPPORTED_CONTRACT_VERSION` hoặc chạy adapter/migration đã khai báo.
- Workflow history cũ phải replay được với code/version tương thích trước khi nâng production.
- Schema fixture đã phát hành không được sửa hồi tố.
- Fake adapter và real adapter phải chạy cùng provider contract suite.

## 14. Kiểm thử state machine và invariant xuyên phân hệ

### 14.1. Model-based state test

Với mỗi máy trạng thái trong [12-state-machines.md](./09-contracts/12-state-machines.md):

1. Sinh/định nghĩa mọi transition hợp lệ.
2. Kiểm tra mọi transition không hợp lệ trả `FORBIDDEN_TRANSITION` và không side effect.
3. Kiểm tra revision tăng đúng một lần.
4. Kiểm tra terminal state không quay lại running.
5. Kiểm tra event/outbox chỉ phát sau commit.
6. Kiểm tra replay cùng command/event không đổi kết quả logic.

### 14.2. Test catalog cho `INV-*`

| Test ID | Invariant | Kịch bản chính | Kết quả bắt buộc |
|---|---|---|---|
| `TST-CTR-INV-001` | INV-001 | Gửi cùng mutation nhiều lần và đồng thời | Một aggregate/receipt logic |
| `TST-CTR-INV-002` | INV-002 | Giao event lặp trước/sau restart consumer | Side effect chỉ commit một lần |
| `TST-WF-INV-003` | INV-003 | Worker generation cũ trả sau worker mới | Result cũ thành stale, không ghi đè |
| `TST-INT-INV-004` | INV-004 | Đổi nguồn/config sau snapshot | Job cũ giữ refs; job mới nhận revision mới |
| `TST-INT-INV-005` | INV-005 | Nộp repost có/không có media mới | Không có article/script mới; media mới được giữ |
| `TST-CTR-INV-006` | INV-006 | Yêu cầu timeline mode không có update | Bị từ chối; có update thì được phép |
| `TST-MEDIA-INV-007` | INV-007 | Đổi script hoặc voice sau alignment | Timing cũ bị từ chối |
| `TST-INT-INV-008` | INV-008 | Render package có artifact unverified/hash sai | Không được render |
| `TST-E2E-INV-009` | INV-009 | QC pass nhưng upload chưa verify | Không completion, không xóa local |
| `TST-WF-INV-010` | INV-010 | Giao completion command/result lặp | Ledger/count chỉ tăng một lần |
| `TST-DR-INV-011` | INV-011 | Cleanup auth cũ/sai lease/sai path/sai epoch | Không xóa |
| `TST-SEC-INV-012` | INV-012 | Canary secret qua mọi lỗi/log/event/history | Không có giá trị secret trong output lưu |
| `TST-AI-INV-013` | INV-013 | Sinh 1-3 video cùng lượt | Mỗi video khác StoryAngle |
| `TST-AI-INV-014` | INV-014 | Tái khai thác sau một vòng | Không exact duplicate; có khác biệt thực tế |
| `TST-INT-INV-015` | INV-015 | Remove rồi auto-discovery cùng URL | Vẫn tombstone; không tạo Source mới |
| `TST-WF-INV-016` | INV-016 | Sau restore gửi result/event có generation trùng nhưng epoch cũ | Bị từ chối/quarantine; chỉ reconcile dưới epoch mới |
| `TST-WF-INV-017` | INV-017 | Crash/race giữa completion và owner usage records | Ledger và usage cùng commit hoặc cùng rollback; reservation không mất |
| `TST-WF-INV-018` | INV-018 | Hai allocator tranh suất cuối | Chỉ một active reservation/job; không vượt target |
| `TST-QC-INV-019` | INV-019 | Metadata tự khai English nhưng voice/subtitle hoặc revision không khớp | Hard fail; chỉ exact-revision evidence hợp lệ được completion |
| `TST-SEC-INV-020` | INV-020 | Article/metadata/OCR giả system instruction và đề xuất ref sai workspace | Không đổi policy/gọi tool; ref bị resolver từ chối |

## 15. Luồng E2E bắt buộc

### TST-E2E-001 — Tin mới đến video hoàn chỉnh

Nguồn → document → article → analysis → angle/script → media/hook → voice/timing → render/QC → cloud verify → completion. Truy vết ngược từ output tới mọi revision và nguồn.

### TST-E2E-002 — Bài trùng có media mới

Bài repost bị deduplicate, không tạo script mới; media/provenance mới được bổ sung và có thể được chọn trong biến thể sau.

### TST-E2E-003 — Sự kiện có diễn biến mới

Bài mới có tình tiết mới được chấp nhận thành `EventUpdate`; mode “từ lúc đó đến nay” được phép và timeline dùng đúng source revisions.

### TST-E2E-004 — Nguồn mới nhưng không có diễn biến mới

Bài repost/nguồn bổ sung không được phép kích hoạt narrative timeline hoặc article/script mới.

### TST-E2E-005 — Lô đạt target

Batch tái khai thác candidate đến khi số ledger bằng target, sau đó không cấp job vượt target do race.

Chạy ít nhất hai allocator đồng thời khi chỉ còn một suất; job `WAITING` giữ suất, retry không tạo suất mới, job `FAILED_FINAL` giải phóng suất và completion chuyển đúng reservation trong cùng transaction.

### TST-E2E-006 — Lô hết việc

Không còn candidate đủ điều kiện thì batch kết thúc `COMPLETED_EXHAUSTED`, không vòng lặp vô hạn và có lý do quan sát được.

### TST-E2E-007 — Một video lỗi giữa lô

Gây lỗi có kiểm soát tại một stage; job được log/đánh dấu, video độc lập khác tiếp tục.

### TST-E2E-008 — Desktop offline rồi online

Cloud tiếp tục thu thập/làm giàu; script/plan/voice chờ. Khi desktop online, hàng chờ sẵn sàng trong 5 phút và tiếp tục đúng checkpoint.

### TST-E2E-009 — Thay cấu hình giữa lô

Job đã snapshot dùng cấu hình cũ; job chưa bắt đầu script dùng revision mới; lịch sử output cũ không đổi.

### TST-E2E-010 — Retry so với biến thể

Retry giữ job/snapshot/intent và không tăng target; variant tạo job mới, khác biệt hợp lệ và chỉ tăng target sau completion.

### TST-E2E-011 — Ảnh safety thất bại

Ảnh đọc được ở trạng thái uncertain/detection failed/transform failed được dùng theo policy kèm warning; không bị ghi thành safe hoặc processed success; lô không dừng.

### TST-E2E-012 — Đồng bộ gián đoạn

Ngắt mạng trước/trong/sau upload; hệ thống reconcile, không đếm trùng, không mất output local và chỉ cleanup sau verification/completion.

### TST-E2E-013 — Phiên không sản xuất video

Mở/đóng app không tạo output folder hợp lệ rỗng; session/log vẫn truy được nếu policy lưu.

### TST-E2E-014 — Debug từng stage

User chạy một stage từ UI, xem input/output/lỗi và tạo lại; stage sau không tự chạy.

## 16. Ma trận fault injection

Mỗi fault phải được tiêm ở ít nhất ba thời điểm khi có side effect: trước khi bắt đầu, đang thực hiện và sau khi bên ngoài hoàn thành nhưng trước khi nội bộ commit receipt.

| Fault | Điểm tiêm | Expected state | Điều tuyệt đối không được xảy ra |
|---|---|---|---|
| API request giao lặp | Control API | duplicate receipt | Tạo hai aggregate |
| Process chết sau DB commit trước publish | Outbox publisher | event phát khi hồi phục | Mất event |
| Event lặp | Consumer | deduplicated | Side effect lặp |
| Event lệch thứ tự | Consumer | gap/revision handling | Revision cũ ghi đè mới |
| Workflow worker chết | G/worker | retry/wait theo policy | Mất job |
| Worker cũ về muộn | Activity result | stale | Ghi đè output mới |
| Result/event epoch cũ sau restore | Owner/event consumer | stale/quarantine | Mutation dù generation/revision trùng |
| Desktop mất điện | E/F/I | recover từ journal/checkpoint | Chạy lại toàn pipeline |
| Desktop hết dung lượng | I/E/F | waiting/insufficient disk | Xóa dữ liệu chưa sync |
| File local bị sửa | I/F | hash mismatch/corrupt | Render byte sai |
| Drive timeout trước upload | I | retryable failure | Tạo location verified giả |
| Drive timeout sau upload | I | outcome unknown/reconcile | Upload lặp mù |
| Drive trả quota/rate limit | I/J/G | waiting/backoff | Retry storm |
| Token hết hạn | J/I | refresh/credential flow | Log token hoặc mất job |
| Credential bị revoke | J/G | waiting/failure an toàn | Dùng credential cũ |
| AI timeout/rate limit | D/E/J | waiting/fallback cho phép | Tự thêm dịch vụ trả phí |
| AI trả schema sai | D/E | validation failure | Commit output sai schema |
| AI trả nội dung thiếu disclosure | D/F | policy/QC fail | Completion |
| TTS trả audio thiếu/hỏng | E | failed/retryable | Timing/render được coi ready |
| Alignment thiếu từ | E/F | validation/QC fail | Karaoke được coi đạt |
| FFmpeg crash giữa render | F | failed/outcome unknown | Output partial thành ready |
| QC process chết | F/G | retry QC cùng output | Render lại không cần thiết hoặc completion sớm |
| DB unavailable | Mọi writer | waiting/failure rõ | Ghi cục bộ thành sự thật nghiệp vụ |
| Restore từ backup | G/I/J | recovery epoch opaque mới, grant cũ bị thu hồi | Writer/result/event/cleanup cũ hoạt động |
| SSE disconnect | H | reconnect/resync | UI mất trạng thái cuối |
| Log sink lỗi | G/J/H | trạng thái lỗi vẫn bền vững | Công việc biến mất im lặng |

## 17. Kiểm thử hiệu năng, sản lượng và độ ổn định

### 17.1. Nguyên tắc đo

Mọi phép đo phải ghi:

- hardware/OS/driver và cấu hình desktop;
- cloud host, database, workflow và network profile;
- version code/tool/model/provider;
- dataset/workload revision;
- concurrency/admission/retry/config revisions;
- warm-up và thời gian đo;
- số lỗi, retry, waiting và output bị loại;
- chi phí phát sinh trong run;
- raw metrics và cách tính.

Kết quả không đủ metadata là `INVALID_EVIDENCE`.

### 17.2. Workload profile

Benchmark G02 phải dùng workload có:

- đủ candidate để target không bị chặn do hết tin;
- hỗn hợp bài đơn và event đủ điều kiện;
- ảnh, clip, audio và hook có phân bố đại diện;
- cả reusable rendition đã có và media cần tải/xử lý;
- 5 preset được phân phối theo policy thực;
- AI/TTS/provider route như production dự kiến;
- nguồn lỗi và media khó ở tỷ lệ được ghi trước khi chạy;
- output profile thật trên máy render mục tiêu.

Không được dùng 100 video đơn giản bất thường để tuyên bố toàn pipeline đạt.

### 17.3. G02 — 100 video trong 12 giờ

Phép thử chính:

1. Khóa workload/config/version trước run.
2. Chạy liên tục 12 giờ trên máy mục tiêu.
3. Chỉ đếm `CompletionLedger` duy nhất có output cloud verified và mọi hard gate đạt.
4. Không đếm retry kỹ thuật, file render chưa QC, QC pass chưa sync hoặc duplicate ledger.
5. Kết quả đạt khi có ít nhất 100 video hợp lệ trong cửa sổ 12 giờ.
6. Báo cáo stage latency, queue wait, utilization, peak disk/RAM/GPU/CPU/network và bottleneck.

Tỷ lệ hoàn thành tự động:

`số video đủ đầu vào hoàn thành không cần thao tác sau StartBatch / tổng video đủ đầu vào được đưa vào sản xuất`.

Phải đạt ít nhất 95%. Mọi exclusion khỏi mẫu phải có reason code được định nghĩa trước; không loại lỗi hệ thống khỏi mẫu.

### 17.4. UI và command latency

- Đo từ thao tác user đến phản hồi hữu ích, không chỉ tới request sent.
- Thao tác thông thường phải đạt p95 không quá 2 giây.
- Start/retry/variant command phải có durable acceptance phản ánh trên UI trong không quá 1 giây.
- Đo cold/warm cache riêng.
- Dataset/quy mô bảng dùng để nghiệm thu còn `QUALITY-OPEN-001/011`; chưa được tuyên bố đạt trước khi khóa workload.

### 17.5. Resume

- Đo từ lúc app/desktop agent bắt đầu đến khi trạng thái được reconcile và hàng chờ có thể tiếp tục.
- Phải không quá 5 phút.
- Kiểm tra với stage bị gián đoạn ở D, E, F và I, cùng journal sạch/bẩn có kiểm soát.
- Không coi “UI mở được” là queue đã sẵn sàng.

### 17.6. Scheduler 99%

- Mẫu số là lượt chạy theo lịch hợp lệ phải bắt đầu trong tháng.
- `SKIPPED_SUFFICIENT` do ngưỡng chủ đề không phải lượt bị mất.
- Lỗi scheduler, cloud unavailable hoặc không tạo run hợp lệ vẫn nằm trong mẫu số.
- Test tăng tốc kiểm tra logic schedule nhưng tuyên bố 99% theo tháng cần bằng chứng vận hành đủ cửa sổ thời gian tương ứng.

### 17.7. Soak và leak

Run 12 giờ G02 đồng thời quan sát:

- queue growth;
- handle/process/thread/file descriptor theo nền tảng;
- memory/GPU memory/disk growth;
- temp/orphan artifact;
- database connection/lock/WAL/index behavior;
- retry amplification;
- log volume;
- provider quota/cost drift.

Không chỉ lấy số output cuối run; phải chứng minh hệ thống không tiến dần tới mất ổn định.

## 18. Đánh giá AI và chất lượng nội dung

### 18.1. Phân loại chủ đề

- Mẫu được khóa và phân tầng trước khi chạy.
- User đánh giá `đúng/chấp nhận được` hoặc `không đạt` theo rubric.
- Tỷ lệ đạt = số item đúng/chấp nhận được chia tổng item hợp lệ trong mẫu.
- Ngưỡng: ít nhất 90%.
- Parse/model failure được tính là không đạt, không bị loại.

### 18.2. Liên kết sự kiện

- Ưu tiên đo lỗi gộp nhầm vì yêu cầu là ít nhất 95% liên kết tự động không gộp hai sự kiện khác nhau.
- Mẫu phải có các cặp giống người/địa điểm/thời gian nhưng khác sự kiện.
- `needs_more_evidence` không được tính như liên kết đúng.
- Bài độc lập phải được bảo toàn dù có event link.

### 18.3. Trùng bài và diễn biến mới

Chưa có ngưỡng dedup chính thức. Trước khi khóa model/policy phải báo riêng:

- exact duplicate accuracy;
- near-duplicate/repost disposition;
- false merge;
- false split;
- media-only preservation;
- update mới bị bỏ sót;
- repost bị gắn nhầm thành update.

Không gộp các chỉ số thành một accuracy duy nhất che lỗi quan trọng.

### 18.4. Media và hook

- User đánh giá thumbnail/ảnh/clip phù hợp hoặc không đạt theo scene intent.
- Ngưỡng media: ít nhất 90% trên mẫu.
- User đánh giá tổ hợp visual hook/audio hook theo cảm xúc/ngữ cảnh.
- Ngưỡng hook: ít nhất 90% trên mẫu.
- Mẫu phải có candidate phong phú và candidate gây nhiễu; không chỉ chấm các lựa chọn dễ.

### 18.5. Ảnh nhạy cảm

- Ground truth do người đánh giá gắn nhãn trên vùng/yếu tố liên quan.
- Recall phát hiện = true positive chia tổng ảnh/yếu tố positive trong bộ mẫu.
- Ngưỡng ít nhất 95%.
- `UNCERTAIN`, detector error và unreadable được báo riêng; không loại khỏi mẫu để tăng recall nếu item vẫn thuộc population đánh giá.
- Kiểm tra transform mask, blur/recolor và preservation của ảnh không cần xử lý.
- Clip không được đưa qua safety transform; đây là scope test riêng.

### 18.6. Góc kể, biến thể và disclosure

- 100% nhóm 1-3 video cùng lượt phải có StoryAngle khác nhau.
- 100% video tái khai thác không exact duplicate và ghi ít nhất một khác biệt thực tế.
- 100% segment inference/creative phải có `claim_mode` và disclosure đầu ra phù hợp.
- Hash/embedding chỉ hỗ trợ phát hiện candidate trùng; quyết định khác góc phải dựa trên semantic rubric và plan/script evidence.

### 18.7. Chống thiên lệch đánh giá

- Rubric và mẫu được khóa trước khi xem kết quả.
- Thứ tự output được xáo trộn khi user đánh giá phù hợp.
- Không hiển thị model/provider nếu không cần cho đánh giá.
- Bất đồng được ghi, không ép sửa nhãn sau khi biết mục tiêu.
- Thay prompt/model cần chạy lại cùng locked holdout set và kiểm tra regression theo chủ đề.

## 19. Kiểm thử video, âm thanh và hard gate

### 19.1. Kiểm tra trên mọi video được tính hoàn thành

Không sampling đối với:

- file phát/decode được;
- duration 61-70 giây;
- output profile;
- visual hook;
- audio hook;
- thumbnail;
- voice tồn tại;
- subtitle burn-in;
- timing từng từ có cấu trúc hợp lệ;
- cloud location verified;
- variant validation;
- completion ledger duy nhất.

### 19.2. Kiểm tra theo mẫu

Sampling được phép cho đánh giá cảm nhận:

- lời dẫn nghe hiểu được trong mix;
- không có âm vỡ/im lặng ngoài chủ ý;
- media/thumbnail phù hợp;
- hook phù hợp ngữ cảnh;
- visual continuity;
- karaoke nhìn khớp lời.

Nếu sampling phát hiện lỗi hard gate mà detector tự động bỏ sót, phải tạo regression test và đánh giá lại detector; không chỉ sửa video mẫu.

### 19.3. Word timing

Phải kiểm tra:

- coverage từ trong script/voice;
- monotonicity và overlap;
- start/end nằm trong audio duration;
- binding với exact script/voice hash;
- burn-in/highlight thực tế trong output;
- sai lệch so với mốc người gắn nhãn trên mẫu.

Ngưỡng sai số timing định lượng đang `QUALITY-OPEN-007`; báo phân phối sai số nhưng không tự đặt pass threshold trước khi được chốt.

### 19.4. Output profile

Resolution, aspect ratio, frame rate, codec và bitrate còn `QUALITY-OPEN-006`. Test suite phải parameter hóa theo `OutputProfileRevision`; chỉ đóng G07 sau khi profile chính thức được phê duyệt.

## 20. Kiểm thử bảo mật

### 20.1. Authentication, session và trust boundary

- Local UI không yêu cầu interactive login cho user đơn nhưng request vẫn cần session hợp lệ.
- Kiểm tra session fixation, expiry, cookie flags, CSRF, `Host` và `Origin` giả.
- Cloud-desktop identity không chỉ dựa hostname/device-supplied ID.
- Temporal/API/worker endpoint từ mạng không được phép bị từ chối.
- Workspace ID giả hoặc thay trên request không vượt biên dữ liệu.

### 20.2. SSRF và fetch bên ngoài

Kiểm tra:

- loopback, link-local, private network, metadata endpoint;
- IPv4/IPv6 và dạng biểu diễn địa chỉ khác nhau;
- redirect từ public sang private;
- DNS rebinding/toctou theo khả năng adapter;
- protocol không cho phép;
- URL có credential;
- redirect loop và response quá lớn;
- media/article URL do AI hoặc nguồn cung cấp.

### 20.3. File và command boundary

- Path traversal, absolute path, UNC path, reserved device name và ký tự điều khiển.
- Symlink/junction/reparse point thoát staging root.
- Filename caption/hashtag quá dài hoặc collision.
- Shell metacharacter trong title, URL, metadata và AI output.
- Cleanup target phải resolve trong root cho phép trước khi xóa.
- Renderer/processor nhận argument có cấu trúc, không command string do AI tạo.

### 20.4. Secret

- Dùng canary secret riêng cho test.
- Gây lỗi tại update, validation, provider call, refresh, retry và debug view.
- Quét UI response, logs, event/outbox, trace, workflow history, DB export, crash report và artifact metadata.
- Secret cũ bị revoke không dùng lại.
- Desktop không lưu refresh token Drive dài hạn.

### 20.5. Input/output và UI

- XSS qua title, article HTML, source name, error detail, hashtag và metadata.
- Injection qua filter/sort/search/config và structured AI output.
- Indirect prompt injection trong article, caption, metadata, OCR/transcript không được đổi policy, bỏ disclosure, gọi tool/tải URL hoặc tạo ref chưa qua resolver.
- Cùng security corpus phải chạy qua provider/fallback được chọn; typed output hợp schema nhưng chứa ref không tồn tại hoặc sai workspace vẫn bị từ chối.
- File/media malformed không gây thực thi ngoài ý muốn.
- Technical detail chỉ hiện theo quyền và vẫn redacted.

### 20.6. Dependency và build

Khi có code/dependency:

- khóa version/lockfile;
- vulnerability và license scan;
- secret scan;
- static analysis;
- container/image/config scan nếu có;
- SBOM/build manifest cho release;
- kiểm tra artifact build đúng source revision.

Chưa chọn scanner cụ thể ở bước này.

## 21. Backup, restore và phục hồi thảm họa

### 21.1. Phạm vi cam kết

User không yêu cầu cam kết phục hồi sau mất toàn bộ kho và backup bổ sung có ưu tiên thấp. Tuy vậy, nếu kiến trúc tuyên bố backup dùng được hoặc cho phép cleanup dựa trên nó, G05 phải chứng minh restore thật; kiểm tra tồn tại file backup không đủ.

### 21.2. Protocol G05

1. Tạo workload có job ở nhiều state, artifact đã/đang/chưa sync và outbox chưa publish.
2. Ghi backup/manifest theo thiết kế.
3. Cô lập writer production test.
4. Restore sang môi trường E6 mới.
5. Tạo và commit `RecoveryEpoch` opaque mới trước khi mở writer/dispatcher.
6. Reconcile PostgreSQL, workflow state, Drive object và local journal.
7. Chứng minh result/event/grant từ epoch cũ bị từ chối dù generation/revision trùng; dữ liệu áp dụng lại chỉ qua reconcile dưới epoch mới; không replay side effect mù, tăng completion count lặp hoặc cleanup bằng authorization cũ.
8. Chọn mẫu output/article/script/preset để truy vết và kiểm hash.
9. Ghi dữ liệu mất, thời gian restore, manual steps và giới hạn thật.

### 21.3. Crash matrix bắt buộc

Gây crash tại các ranh giới:

- trước/sau DB commit;
- trước/sau outbox publish;
- trước/sau provider side effect;
- trước/sau operation receipt;
- trước/sau render hoàn tất;
- trước/sau cloud upload;
- trước/sau cloud verification;
- trước/sau completion ledger;
- trước/sau cleanup authorization;
- trong quá trình restore/reconcile.

## 22. Chiến lược chạy test theo nhịp phát triển

| Thời điểm | Suite bắt buộc | Mục tiêu thời gian |
|---|---|---|
| Khi sửa code cục bộ | Unit + component liên quan + contract nhỏ | Phản hồi nhanh |
| Trước merge | Unit, component, contract, integration liên quan, static/security cơ bản | Không có regression đã biết |
| Hằng đêm | Integration rộng, workflow replay, adapter sandbox có quota kiểm soát | Phát hiện drift |
| Theo lịch riêng | AI evaluation, media/render corpus, security dynamic | Quản lý chi phí/thời gian |
| Trước release candidate | Full regression, E2E, G01/G04/G07 phần áp dụng | Chặn release |
| Benchmark candidate | G02 12 giờ và capacity profile | Khóa concurrency/profile |
| Kiểm tra phục hồi | G05 isolated restore | Khóa claim restore/cleanup |
| Đánh giá định kỳ | G03 cost, G06 quality, scheduler 99% | Phát hiện drift dài hạn |

Không chạy provider-costly test trên mọi commit. Suite bị tách nhịp nhưng vẫn phải chạy trước khi đóng gate liên quan.

## 23. Coverage và chất lượng test code

### TEST-COVERAGE-001 — Requirement coverage

- 100% `INV-001` đến `INV-015` có test trực tiếp.
- 100% hard gate có automated check hoặc manual protocol bắt buộc.
- 100% state transition hợp lệ và không hợp lệ quan trọng được kiểm tra.
- Mọi defect production sau này phải có regression test trước khi fix nếu có thể tái tạo.

### TEST-COVERAGE-002 — Code coverage tối thiểu đề xuất

**TEST-PROPOSED:** Khi có code, phần application/domain có thể kiểm thử tự động phải đạt tối thiểu 80% line coverage và 80% branch coverage. Mức này là guardrail, không thay cho test invariant, integration hoặc E2E.

Các loại loại trừ coverage phải được ghi rõ và review; không loại file chỉ để nâng số. Threshold cuối cùng trở thành chính thức sau khi người dùng duyệt tài liệu này.

### TEST-COVERAGE-003 — Chất lượng assertion

- Không có test chỉ assert “không ném lỗi” cho nghiệp vụ quan trọng.
- Test side effect phải kiểm cả điều được ghi và điều không được ghi.
- Snapshot test UI/schema không thay cho assertion semantics.
- Với logic critical như completion, cleanup, fencing và secret, mutation/fault test được ưu tiên để chứng minh assertion bắt được lỗi; ngưỡng mutation coverage chưa được đặt.

## 24. Quản lý flaky test

1. Test không ổn định bị đánh `QUARANTINED`, tạo defect và owner.
2. Quarantine không được tính pass hoặc coverage cho gate.
3. Ghi tỷ lệ fail, môi trường, seed/time và lần xuất hiện.
4. Sửa nguyên nhân về clock, ordering, shared state, external drift hoặc resource race.
5. Chỉ đưa lại gate sau nhiều lần chạy ổn định theo policy sẽ chốt.
6. Không thêm sleep tùy ý để che race; dùng signal/condition hoặc clock kiểm soát khi phù hợp.

Số lần ổn định cần thiết trước khi bỏ quarantine là **CHƯA QUYẾT ĐỊNH**.

## 25. Phân loại lỗi và release blocker

| Mức | Ví dụ | Hành động |
|---|---|---|
| `P0 Critical` | Mất output chưa sync, lộ secret, xóa ngoài staging, ghi sai workspace, duplicate completion diện rộng | Dừng release và cô lập ngay |
| `P1 High` | Vi phạm hard gate được tính hoàn thành, lô dừng vì một job, không resume, stale worker commit | Chặn release |
| `P2 Medium` | Một luồng debug/UI chính hỏng, quan sát thiếu, performance vượt ngưỡng đã duyệt | Chặn release nếu thuộc scope candidate |
| `P3 Low` | Lỗi trình bày không che thao tác, cảnh báo thiếu ưu tiên thấp | Lập kế hoạch sửa; không tự động chặn nếu ngoài gate |

Bất kỳ test nào của INV, hard gate, security boundary hoặc completion/cleanup fail đều là release blocker dù defect được gán mức thấp hơn.

## 26. Bằng chứng để đóng G01-G07

Trạng thái phải phản ánh đúng phạm vi evidence: `NOT_TESTED` trước runtime proof; `PASS_M1_SCOPE` cho lát cắt M1 đạt; `PARTIALLY_PROVEN` cho gate tổng thể đã có proof M1 nhưng chưa đủ; `PASS` chỉ khi toàn bộ evidence ở bảng dưới và lần đóng chính của roadmap đều đạt. `RED_CONFIRMED` là trạng thái test-first mong đợi, không phải gate/package FAIL. Lỗi setup/import/binary không được dùng làm RED nghiệp vụ; defect implementation dùng `CORRECTION_REQUIRED` trong package, còn ADR chỉ mở lại khi root-cause evidence phủ định quyết định kiến trúc.

Trong M1, P2 phải có replay history qua revision workflow tương thích trên cùng Server/SDK R1; upgrade Server/SDK được để cho các bước M2-M7. P3 phải dùng tài khoản/OAuth thật cho Drive slice; local HTTPS/Origin, Temporal authorization và account-pool production path được để cho M2-M7. Vì vậy P2/P3 không thể tự đóng G01/G04 toàn phần.

| Gate | Test suite tối thiểu | Evidence bắt buộc | Không được thay bằng |
|---|---|---|---|
| G01 Workflow | Contract, replay, crash matrix, stale worker, child isolation, offline/resume | History/replay report, receipts, ledger/state diff, fault timeline | Unit test hoặc happy-path E2E |
| G02 Throughput | 12h target hardware, hard gates toàn output, auto-rate, resource/soak | 100+ unique ledgers, cloud verify, metrics, config/workload manifest | Số file render hoặc phép ngoại suy ngắn |
| G03 Cost | Workload tháng, usage/cost reconciliation, 80% alert | Provider bill/usage, internal records, scope R20, projection method | Giá niêm yết đơn lẻ |
| G04 Drive/OAuth/Security | Real account sandbox, interrupted upload, scope/revoke/refresh, local/API security | Object/hash evidence, OAuth scope, redacted logs, security report | Mock Drive/OAuth |
| G05 Restore | Isolated restore + recovery epoch + reconcile | Restore log, data/hash diff, orphan/side-effect result, limits | “Backup job succeeded” |
| G06 AI/Content | Locked stratified sets, human rubric, model/prompt refs, all approved thresholds | Raw evaluations, sample plan, confusion/error breakdown, output refs | Demo đẹp hoặc AI tự chấm duy nhất |
| G07 Compatibility/UI/QC | Target desktop/UI timings/output profile/runtime matrix/replay compatibility | Version manifest, screenshots/measurements, QC reports, latency distributions | Chạy trên máy phát triển khác |

## 27. Entry và exit criteria

### 27.1. Trước khi viết test code đầu tiên

- Tài liệu 00-10 được user phê duyệt cho phạm vi tương ứng.
- Contract/state machine liên quan ở trạng thái đủ để kiểm thử.
- Test case có requirement/contract ref và oracle.
- Test data/fixture plan không dựa vào secret production.
- Chọn framework sau khi runtime/project structure được khóa; không cài trước quyết định.

### 27.2. Trước khi viết implementation của một hành vi

- Test case đã `REVIEWED`.
- Test code được viết theo framework đã duyệt.
- RED được xác nhận đúng lý do.
- Không có implementation tương ứng được viết trước test.

### 27.3. Trước khi nối hai phân hệ

- Unit/component của hai bên đạt.
- Producer/consumer contract suite đạt.
- Version/schema compatibility được kiểm tra.
- Failure/error semantics có test, không chỉ happy path.

### 27.4. Trước release candidate

- Không có P0/P1 mở.
- Không có hard gate/INV test fail hoặc quarantined.
- Full regression phù hợp đạt.
- Security scan/test thuộc scope đạt.
- Migration/restore/replay test cần thiết đạt.
- Build/version/config manifest đầy đủ.
- Các gate cần cho claim release có evidence được audit.

### 27.5. Điều kiện không được gọi là “đạt”

- Test chỉ chạy một lần nhưng flaky chưa xử lý.
- Chỉ dùng mock cho tích hợp ngoài.
- Thiếu raw evidence hoặc version manifest.
- Mẫu được thay sau khi xem kết quả.
- Exclusion không có reason từ trước.
- Chỉ có screenshot/demo.
- Metric trung bình đạt nhưng p95/hard gate không đạt.
- Video tồn tại local nhưng chưa cloud verified/completion commit.

## 28. Trách nhiệm kiểm thử

| Khu vực | Owner chính | Phối hợp/duyệt |
|---|---|---|
| A-B collection/content/dedup/event | Owner phân hệ A/B | G, D và user cho quality sample |
| C media/hook/catalog | C | D, E, I và user |
| D AI/content/variant | D | B, C, G và user đánh giá |
| E media/TTS/timing | E | C, F, I và user nghe/xem mẫu |
| F render/QC/preset | F | E, G, I và user |
| G workflow/batch/completion | G | Tất cả producer/consumer |
| H UI/UX | H | G/J và user nghiệm thu |
| I storage/recovery | I | F/G/J |
| J config/security/cost | J | G/I/H |
| Contract/schema toàn hệ thống | Owner contract producer | Mọi consumer ký xác nhận |
| Gate G01-G07 | Owner trong ADR index | Người audit độc lập với tác giả thay đổi khi khả thi |

Một người có thể giữ nhiều vai trò trong dự án một người dùng, nhưng evidence phải ghi vai trò đang thực hiện để tránh nhầm self-review với user acceptance.

## 29. Test run record và báo cáo

Mỗi run dùng để làm bằng chứng phải lưu:

- `test_run_id`, suite/case IDs và purpose;
- source/build/contract/config/prompt/model/preset revisions;
- environment inventory và target identity;
- dataset/workload/golden-set revisions;
- start/end time và timezone;
- seed, clock mode và concurrency;
- result từng case: pass/fail/error/blocked/quarantined;
- expected/actual và evidence refs;
- logs/metrics/traces/artifact refs đã redacted;
- provider/account/project refs, không có secret;
- resource/cost summary;
- defect refs;
- reviewer và approval state.

Báo cáo tổng hợp không thay raw result. Raw evidence có retention policy riêng và phải truy được từ gate report.

## 30. Các vấn đề chưa quyết định

| Mã | Vấn đề | Tác động | Thời điểm chốt |
|---|---|---|---|
| `TEST-OPEN-001` | Số lượng và phương pháp thống kê cho các mẫu 90%/95% | Độ tin cậy G06 | Trước xây golden holdout set |
| `TEST-OPEN-002` | Quy mô hàng/cột và scale dataset | UI/search/performance | Sau ước lượng tăng trưởng dữ liệu |
| `TEST-OPEN-003` | Timeout/retry/backoff từng activity/provider | Fault/recovery oracle | Sau proof và benchmark adapter |
| `TEST-OPEN-004` | Thước đo hot/trending | Content selection | Sau nghiên cứu proxy phù hợp |
| `TEST-OPEN-005` | Output profile cụ thể | Render/QC/compatibility | Trước khóa G02/G07 workload |
| `TEST-OPEN-006` | Sai số word timing được chấp nhận | Karaoke quality | Sau đo corpus và user duyệt |
| `TEST-OPEN-007` | Log/test evidence retention | Debug/storage cost | Trước vận hành dài hạn |
| `TEST-OPEN-008` | Mốc scale dài hạn của nguồn/bài/media/video | Growth test | Sau capacity model |
| `TEST-OPEN-009` | Múi giờ chuẩn | Scheduler/log/folder tests | Trước cấu hình lịch production |
| `TEST-OPEN-010` | `CLOSED_FOR_M1_R1` tại [version lock](./milestones/m1-proof/version-lock.md); version M2–M7/production vẫn chưa khóa | M1 replay/build proof dùng exact R1; không đóng G07 production | M1 kiểm theo P0/P5; milestone sau khóa khi bắt đầu phụ thuộc |
| `TEST-OPEN-011` | Số lần chạy ổn định để bỏ quarantine | Flaky policy | Trước CI gate chính thức |
| `TEST-OPEN-012` | Mutation coverage threshold | Chất lượng assertion critical logic | Sau khi có domain code đầu tiên |

Các mục này không được tự điền trong test. Test phải nhận chúng từ policy/config revision hoặc báo `NOT_PROVEN`.

Riêng TEST-OPEN-010 đã có giá trị trong scope M1-R1 do user phê duyệt. Việc `uv.lock`, binary digest, build configuration và compatibility result chưa tồn tại trước P0/P5 là evidence phải tạo, không làm version selection quay lại OPEN và cũng không được gọi là PASS sớm.

## 31. GIẢ ĐỊNH

**Không có GIẢ ĐỊNH chưa được xác nhận nào được dùng để tuyên bố một test hoặc gate sẽ đạt.**

Bốn giả định kỹ thuật đang được quản lý trong hợp đồng được chuyển thành mục tiêu kiểm chứng, không được coi là sự thật:

- `AS-CTR-001` được kiểm tra tại G01.
- `AS-CTR-002` được kiểm tra tại G04.
- `AS-CTR-003` được kiểm tra tại G02/G07.
- `AS-CTR-004` được kiểm tra tại G02/G07.

Khả năng tiếp cận tài khoản test thật, máy mục tiêu, provider quota và dữ liệu mẫu đủ đại diện hiện là **CHƯA KIỂM CHỨNG**. Thiếu chúng làm gate `BLOCKED_EXTERNAL` hoặc `NOT_PROVEN`, không làm gate pass.

## 32. Thứ tự tạo test khi bắt đầu code

Không phải lịch triển khai đầy đủ; đây là dependency order để giữ test-first:

1. Schema/envelope/error và state transition tests.
2. Pure domain tests cho Tier, dedup, snapshot, variant, completion và cleanup eligibility.
3. Producer/consumer contract tests cho A-J.
4. Persistence/outbox/idempotency/fencing integration tests.
5. Workflow replay, offline và fault-injection tests.
6. Artifact/hash/upload/reconcile/cleanup tests.
7. AI/media/TTS/render validators và corpus evaluation harness.
8. Control API/UI component và SSE tests.
9. E2E critical flows.
10. Security, performance, soak và restore gate suites.

Không chuyển sang implementation của một mục trong thứ tự này khi test RED tương ứng chưa được xác nhận.

## 33. Kiểm toán chiến lược

### 33.1. Những rủi ro đã được bao phủ trực tiếp

- Duplicate command/event/result và đếm completion lặp.
- Worker cũ ghi kết quả sau reassign.
- Side effect thành công nhưng nội bộ chưa biết kết quả.
- Lệch trạng thái PostgreSQL, workflow, Drive và SQLite journal.
- Xóa local trước sync/verify hoặc xóa nhầm path/epoch.
- Repost bị coi là tin/update mới.
- Job đã snapshot bị đổi nguồn/config.
- Render/QC/upload bị hiểu nhầm là completion.
- AI output sai schema, thiếu disclosure hoặc trùng biến thể.
- Ảnh safety lỗi bị ghi nhầm thành đã xử lý.
- Secret leak, SSRF, path traversal, command injection và workspace crossing.
- Benchmark đẹp nhưng không đại diện hoặc loại lỗi khỏi mẫu.

### 33.2. Những điều chỉ có thể chứng minh sau khi có implementation

- Code coverage và chất lượng assertion thực tế.
- Tính tương thích version runtime/library.
- Temporal replay và upgrade thật.
- Google Drive integrity/quota/OAuth thật.
- Hiệu năng máy render và 100 video/12 giờ.
- Chất lượng model, TTS, timing và preset.
- Security của code, container, dependency và cấu hình triển khai.
- Restore từ backup thật.

### 33.3. Kết luận

Chiến lược đã tạo đường kiểm chứng cho mọi phân hệ, `INV-001` đến `INV-015`, R01-R25, các hard gate và G01-G07. Các ngưỡng chưa được user quyết định vẫn ở `TEST-OPEN-*`; không có giá trị kỹ thuật nào được điền bằng phỏng đoán.

Lộ trình xây dựng được ghi tại [11-roadmap.md](./11-roadmap.md). Sau khi tài liệu này và roadmap được user phê duyệt, bước tiếp theo theo quy trình dự án vẫn là kiểm toán toàn bộ trước khi cho phép viết test code hoặc implementation code.

## 34. Ca kiểm thử đóng hậu kiểm AUD2

Đây là đặc tả test chưa thực thi. Dùng barrier để hai worker đọc cùng revision rồi kiểm soát thứ tự commit, không dựa vào sleep hoặc xác suất race. Assert cả trạng thái DB/receipt/outbox/ledger/count/usage và không có cleanup trái phép. A2/A4/A6 và pipeline completion phải qua nhóm tương ứng trước exit.

| ID | Đầu vào/tình huống | Oracle bắt buộc |
|---|---|---|
| TST-WF-VAR-001 | Hai job ở hai lô cùng article/event, cùng chữ ký, cùng registry revision | Một reserve thắng; bên kia stale, đối chiếu lại thấy active trùng và conflict. Không có hai completion cho biến thể trùng. |
| TST-WF-VAR-002 | Output validation hợp lệ nhưng registry đổi trước completion | CAS từ chối, không ledger/usage/count/cleanup; đối chiếu lại exact output. Kết quả trùng dẫn job FAILED_FINAL/release, không đổi đầu vào bằng retry. |
| TST-WF-VAR-003 | Reserve/complete mất ACK, retry cùng input; desktop offline, lease hết hạn; job terminal | Receipt cũ, tối đa một active/job; offline/lease không release; terminal release hai reservation, completed convert một lần; receipt reserve cũ không hồi sinh ACTIVE. |
| TST-WF-VAR-004 | Hai phương án thật sự khác hợp lệ; cùng lượt thử thêm hai góc giống nhau; output khác plan | Khác hợp lệ có thể hoàn thành sau refresh revision; góc giống cùng lượt bị chặn. Output phải validate chữ ký thực/exact hash, không dùng plan-only evidence. |
| TST-COL-END-001 | Attempt retryable cuối cùng, biến thể có/không có package hợp lệ đã commit | Không tạo attempt giả; COMPLETED_PARTIAL hoặc FAILED_FINAL với RETRY_EXHAUSTED; checkpoint/data còn nguyên. |
| TST-COL-END-002 | Source disabled/removed khi SCHEDULED, RUNNING hoặc WAITING_RETRY | Không fetch tiếp; partial/final theo CT-STATE-002, SCHEDULED chưa chạy thì FAILED_FINAL; SOURCE_INACTIVE; không mở lại terminal khi restore nguồn. |
| TST-COL-END-003 | Reconcile xác nhận retryable/full success/partial success/final error với budget còn/hết | Các transition theo bảng CT-STATE-002; không lặp side effect; append evidence, cycle tổng hợp đúng. |
| TST-COL-END-004 | Outcome vẫn unknown khi hết reconcile deadline | Giữ WAITING_RECONCILIATION có log/cảnh báo, không retry side effect hoặc tự kết thúc thành công; khi bằng chứng tới tiếp tục đúng transition. |
| TST-SRC-RACE-001 | Candidate READY, nguồn active/disabled cùng identity được đăng ký trước | MATCHED_EXISTING cùng ref hiện có; không Source mới; candidate/receipt/outbox nhất quán. |
| TST-SRC-RACE-002 | Candidate READY, register/remove đồng thời với cả hai thứ tự commit | Tombstone cuối cùng được giữ; nếu remove thắng thì BLOCKED_TOMBSTONE; không tự phục hồi hoặc đăng ký trùng. |
| TST-SRC-RACE-003 | READY rồi policy cấm, thiếu policy hoặc expected revision cũ | REJECTED, READY/WAITING_POLICY hoặc REVISION_CONFLICT tương ứng; không tự active, không phát resolved khi vẫn chờ. |
| TST-SRC-RACE-004 | Registration commit mất ACK và gửi lại cùng key/input; thử payload khác | Trả receipt/disposition cũ; không Source/event nghiệp vụ mới; payload khác bị idempotency conflict. |
| TST-COL-PKG-001 | Thiếu ID/source/run ref hoặc provenance bắt buộc; lặp lại payload sai | VALIDATION_ERROR tại biên; không document/article/event handoff; quan sát lỗi có correlation an toàn, không giả provenance. |
| TST-COL-PKG-002 | Extraction lỗi/empty main text nhưng schema và provenance đầy đủ | Lưu incomplete có reason; B REJECTED_INCOMPLETE; không tính tin mới và không đánh đồng với invalid schema. |
| TST-COL-PKG-003 | Fixture source kind yêu cầu title và fixture cho phép thiếu title, cùng main text hợp lệ | Theo policy revision từng fixture; không mặc định mọi nguồn có title, không tác động title/hashtag của video. Đây là cấu hình test, không phải policy production được tự duyệt. |
| TST-COL-PKG-004 | Thiếu source-kind policy; publication time tùy chọn thiếu; fetch fail chưa đủ package | INPUT_NOT_READY khi thiếu policy; thiếu trường conditional không tự thành schema error; fetch failure chỉ là observation/run outcome, không tạo tin incomplete giả. |

Các thay đổi registry không liên quan có thể gây stale nhưng không được dẫn tới busy loop: retry có giới hạn/backoff theo policy, hết budget đi đường lỗi job hiện có, không bỏ qua validation. Timeout/backoff số cụ thể vẫn qua benchmark/cấu hình trước production.
