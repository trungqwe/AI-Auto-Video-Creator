# AI Auto Video Creator - Lộ trình xây dựng toàn dự án

**Tệp:** `docs/11-roadmap.md`  
**Trạng thái:** Đã được người dùng phê duyệt làm baseline; M0 APPROVED/CLOSED; M1 ACCEPTED/CLOSED (User Checkpoint 13-09-2026, 93 tests PASSED, Audit R5 + R5.1 ACCEPTED); M2 AUTHORIZED_FOR_PLANNING_AND_IMPLEMENTATION; M3 và Phân hệ A NOT AUTHORIZED  
**Ngày lập:** 12-09-2026  
**Ngày phê duyệt M0 và khóa M1-R1:** 13-09-2026  
**Phạm vi:** từ kết thúc thiết kế trước code đến baseline vận hành đầu tiên  
**Cách lập:** theo dependency và evidence gate, chưa gán lịch ngày/tuần khi chưa có dữ liệu nhân lực

## 1. Mục đích

Lộ trình này xác định:

1. Thứ tự xây dựng để giảm rủi ro phải làm lại.
2. Mỗi milestone phải tạo ra năng lực dùng thử và quan sát được nào.
3. Điều kiện nào phải đạt trước khi chuyển sang milestone tiếp theo.
4. Khi nào một quyết định `Conditional` được giữ, thay hoặc mở lại ADR.
5. Các quality gate G01-G07 được chứng minh ở đâu.

Đây là roadmap cấp dự án, không phải danh sách file hay lệnh triển khai. Kế hoạch thực thi chi tiết của từng milestone chỉ được lập sau khi roadmap và kiểm toán trước code được phê duyệt.

## 2. Nguyên tắc điều hành

### RM-PRINCIPLE-001 — Chưa được code trước cổng M0

Không tạo mã nguồn, test code, dependency, framework hoặc hạ tầng chạy thật cho tới khi:

- tài liệu 00-11 được phê duyệt;
- kiểm toán toàn bộ trước code hoàn tất;
- không còn mâu thuẫn chặn implementation;
- user cho phép đi qua ranh giới “CODE DÒNG ĐẦU TIÊN”.

### RM-PRINCIPLE-002 — Test-first trong từng work package

Sau khi được phép code, mỗi hành vi đi theo chu kỳ:

`Contract/requirement → test case → RED → implementation → GREEN → regression → evidence`

Không dồn test đến cuối milestone.

### RM-PRINCIPLE-003 — Xây lát cắt quan sát được

Mỗi milestone phải có:

- command hoặc trigger rõ ràng;
- dữ liệu đầu vào/đầu ra truy vết được;
- trạng thái và lỗi hiển thị trên UI tối thiểu;
- debug từng stage;
- test và evidence;
- rollback/migration path.

Không xây toàn bộ backend rồi mới bổ sung khả năng quan sát ở cuối.

### RM-PRINCIPLE-004 — Proof trước khi phụ thuộc sâu

Temporal, Google Drive/OAuth, recovery, AI quality và throughput không được coi là đã phù hợp chỉ vì đã chọn trong kiến trúc. Proof/gate thất bại phải mở lại ADR trước khi xây thêm trên giả định sai.

### RM-PRINCIPLE-005 — User checkpoint theo phân hệ

Theo `QR-MNT-003`, mỗi milestone có checkpoint user. Milestone sau không được dùng trạng thái “đã duyệt” giả nếu milestone hiện tại chưa có evidence và xác nhận.

### RM-PRINCIPLE-006 — Bảo vệ dữ liệu trước sản lượng

Thứ tự ưu tiên khi đánh đổi giữ nguyên tài liệu chất lượng:

1. Không mất output chưa sync.
2. Không làm dừng cả lô vì một công việc.
3. Tiếp tục đúng sau gián đoạn.
4. Video qua hard gate.
5. Tối ưu 100 video/12 giờ.
6. Giữ incremental cost dưới 50 USD/tháng.
7. Tăng tự động hóa và chất lượng trải nghiệm.

## 3. Critical path

`M0 Khóa thiết kế`  
→ `M1 Proof và nền kỹ thuật`  
→ `M2 Control plane có thể quan sát`  
→ `M3 Thu thập và kho nội dung`  
→ `M4 Kho media và lưu trữ hybrid`  
→ `M5 Bộ não nội dung AI`  
→ `M6 Voice, media processing, render và QC`  
→ `M7 Tự động hóa lô, hardening và baseline vận hành`

G, H và J là năng lực xuyên suốt: được dựng tối thiểu từ M2 và mở rộng cùng từng phân hệ, không chờ tới M7 mới xuất hiện.

## 4. Bảng milestone tổng thể

| Mốc | Kết quả người dùng nhìn thấy | Phân hệ trọng tâm | Gate/checkpoint | Trạng thái |
|---|---|---|---|---|
| M0 | Bộ thiết kế nhất quán và quyết định cho phép code | Toàn hệ thống | Audit trước code + user approval | APPROVED / CLOSED |
| M1 | Proof chứng minh nền workflow/storage khả thi; test harness sẵn sàng | G, I, J | G01 sớm, G04 sớm, compatibility smoke | ACCEPTED / CLOSED — P0-P6 PASS (User Checkpoint 13-09-2026 sau Audit R5.1, 93 passed, 0 skipped, coverage 83%) |
| M2 | UI quản trị tối thiểu thấy command, state, log, config và artifact metadata | G, H, I, J | Contract/state/security foundation | AUTHORIZED_FOR_PLANNING_AND_IMPLEMENTATION (Kích hoạt sau User Checkpoint M1) |
| M3 | Thêm nguồn, quét, chuẩn hóa, chống trùng và xem bài/sự kiện | A, B, G, H | User duyệt A-B; collection/content tests | NOT AUTHORIZED — MODULE A BỊ KHÓA |
| M4 | Kho media/hook có provenance; sync cloud/local và xử lý ảnh nền tảng | C, E một phần, I, H | Drive/integrity/cleanup checkpoint | CHƯA BẮT ĐẦU |
| M5 | Tạo snapshot, góc kể, script, chọn media và kế hoạch dựng | D, B, C, G, J, H | G06 phần nội dung + user duyệt D | CHƯA BẮT ĐẦU |
| M6 | Tạo voice/timing, dựng bằng 5 preset, QC và output cloud verified | E, F, I, G, H | G06 media + G07 output/QC | CHƯA BẮT ĐẦU |
| M7 | Chạy lô không giám sát, phục hồi, đạt gate và phát hành baseline | A-J | G01-G07 đầy đủ + user acceptance | CHƯA BẮT ĐẦU |

## 5. Release increments

| Increment | Hoàn thành tại | Ý nghĩa |
|---|---|---|
| `R0 Evidence Prototype` | M1 | Chỉ chứng minh quyết định rủi ro; chưa phải sản phẩm |
| `R1 Content Alpha` | M3 | Thu thập và quản lý nội dung qua UI/debug được |
| `R2 Media Alpha` | M4 | Kho media/hook và vòng đời artifact hoạt động |
| `R3 Creative Alpha` | M5 | Tạo được script/plan truy vết và biến thể đúng quy tắc |
| `R4 Video Alpha` | M6 | Tạo một video hợp lệ đầu-cuối theo điều khiển có giám sát |
| `R5 Unattended Beta` | M7 trước gate cuối | Chạy lô tự động và chịu lỗi trên workload đại diện |
| `R6 Operational Baseline` | M7 sau gate | Baseline đủ bằng chứng để vận hành theo phạm vi v1 |

Không increment nào đồng nghĩa production-ready nếu gate tương ứng chưa đóng.

## 6. M0 — Khóa thiết kế và cho phép code

**Trạng thái:** APPROVED / CLOSED ngày 13-09-2026. Bằng chứng: checklist 12, AUDIT mục 11 và xác nhận của user. Quyền implementation chỉ mở cho M1; không tự mở milestone sau.

### Mục tiêu

Kết thúc toàn bộ giai đoạn thiết kế, phát hiện mâu thuẫn cuối và tạo quyết định rõ ràng rằng dự án được hoặc chưa được bước sang code.

### Đầu vào

- Tài liệu 00-10 và ADR hiện hành.
- Roadmap này sau khi user duyệt.
- Danh sách `QUALITY-OPEN-*`, `ARCH-OPEN-*`, `TEST-OPEN-*` và giả định có gate.

### Work packages

1. Kiểm toán traceability từ mục tiêu → yêu cầu → dữ liệu → kiến trúc → ADR → hợp đồng → test → roadmap.
2. Kiểm toán mâu thuẫn state/owner, dữ liệu chính, completion, cleanup, retry và security boundary.
3. Phân loại open item thành: phải chốt trước code, chốt trước milestone liên quan hoặc giữ cấu hình runtime.
4. Lập compatibility/dependency selection protocol, chưa cài dependency.
5. Lập danh mục proof M1 và tiêu chí pass/fail/reopen ADR.
6. Ghi quyết định audit cuối và trình user.

### Đầu ra

- Báo cáo kiểm toán toàn dự án trước code.
- Danh sách blocker bằng 0 hoặc có quyết định rõ ràng chưa cho code.
- Backlog milestone cấp cao, không chứa implementation suy đoán.
- Biên bản user cho phép hoặc chưa cho phép “CODE DÒNG ĐẦU TIÊN”.

### Exit gate

- Không có yêu cầu quan trọng bị mất truy vết.
- Không có hai owner ghi cho cùng aggregate.
- Mọi quyết định `Conditional` có proof và fallback decision path.
- Test strategy đủ oracle cho work package đầu tiên.
- User phê duyệt M0.

### Điều cấm

- Không tạo skeleton repo hoặc test framework để “chuẩn bị trước”.
- Không coi tài liệu đầy đủ là bằng chứng công nghệ sẽ chạy được.
- Không tự đóng open item cần user quyết định.

## 7. M1 — Proof kiến trúc và nền kỹ thuật

**Kế hoạch thực thi có thẩm quyền:** [M1 implementation plan](./milestones/m1-proof/implementation-plan.md)  
**Khóa phiên bản:** [M1-R1 version lock](./milestones/m1-proof/version-lock.md)  
**Trạng thái:** `ACCEPTED / CLOSED` ngày 13-09-2026 theo User Checkpoint chính thức sau independent re-audit HEAD `08c857c`. Toàn bộ P0–P6 đã PASS (93 passed, 0 skipped, coverage 83%); Báo cáo Audit R5 kèm R5.1 Addendum đạt; G01 và G04 đạt `PARTIALLY_PROVEN (PASS_M1_SCOPE)`; G07 đạt `SMOKE_COMPATIBILITY_PASS_M1_SCOPE`. Limitation DPAPI cùng một Windows user được giữ nguyên. Toàn bộ Audit R1–R5/R5.1 và evidence lịch sử được lưu giữ đầy đủ. Quyền lập kế hoạch và triển khai cho M2 đã được kích hoạt. M3 và Phân hệ A tiếp tục `NOT AUTHORIZED`.

### Mục tiêu

Sau khi được phép code, dùng test-first proof nhỏ nhất để kiểm chứng các quyết định có blast radius lớn trước khi xây production modules.

### Thứ tự công việc

1. `M1-P0` — khóa môi trường và dựng test harness tối thiểu.
2. `M1-P1` — proof contract/envelope/state/idempotency/fencing/receipt/outbox.
3. `M1-P2` — proof Temporal G01.
4. `M1-P3` — proof Google Drive/OAuth G04; có thể `BLOCKED_EXTERNAL` khi thiếu credential thật.
5. `M1-P4` — proof local journal/recovery.
6. `M1-P5` — compatibility smoke cho runtime/database/workflow SDK/FFmpeg.
7. `M1-P6` — tổng hợp evidence, audit và quyết định giữ hoặc mở lại ADR.

M1-P0 → P1 → P2 có thể thực hiện khi chưa có credential Google thật. M1-P3 không được thay proof bên ngoài bằng mock rồi tuyên bố G04 PASS. Dependency và điều kiện dừng chi tiết do M1 implementation plan quy định.

### Sản phẩm

- `R0 Evidence Prototype`, chưa phải sản phẩm vận hành.
- Test/evidence record theo tài liệu 10.
- Compatibility matrix revision đầu tiên.
- Quyết định rõ: giữ Temporal/Drive design, đổi adapter hoặc dừng để thiết kế lại.

### Test và failure bắt buộc

- RED/GREEN cho `INV-001`, `INV-002`, `INV-003`, `INV-010`, `INV-011`, `INV-012` ở mức proof phù hợp.
- Process chết tại ranh giới DB/outbox/receipt/side effect.
- Upload timeout trước và sau external side effect.
- Credential revoke và secret canary không xuất hiện trong log/history.
- Worker cũ trả kết quả sau worker mới.
- Restore/restart journal không tự commit business state.

### Exit gate

- `G01_M1_SCOPE=PASS_M1_SCOPE`; G01 toàn phần chỉ chuyển `PARTIALLY_PROVEN`, không được gọi PASS ở M1. Nếu proof phủ định kiến trúc thì mở lại ADR-0003 và phải có phương án được duyệt.
- `G04_M1_SCOPE=PASS_M1_SCOPE` trên tài khoản/OAuth thật; G04 toàn phần chỉ chuyển `PARTIALLY_PROVEN`, không được gọi PASS ở M1. Nếu proof phủ định kiến trúc thì mở lại ADR-0006/0009.
- Không có secret leak, duplicate completion hoặc stale result commit trong proof.
- Test-first workflow và evidence format chạy được trong môi trường đã khóa.
- User duyệt kết quả proof.

Nếu M1-P3 là `BLOCKED_EXTERNAL`, M1 cũng kết luận `BLOCKED_EXTERNAL` tại P6 và không đạt exit gate; P0/P1/P2/P4/P5 đã PASS vẫn được giữ làm evidence, không bị giả thành chưa chạy hoặc dùng để thay G04.

### Điểm dừng bắt buộc

- Dừng nếu workflow không thể bảo toàn grant/receipt/replay semantics.
- Dừng nếu Drive adapter không thể xác minh đúng byte trước cleanup.
- Dừng nếu local/cloud trust boundary buộc desktop giữ refresh token dài hạn trái kiến trúc.
- Không “đi tiếp rồi sửa sau” với các lỗi này.

## 8. M2 — Control plane và nền tảng có thể quan sát

**Kế hoạch thực thi có thẩm quyền:** [M2 implementation plan](./milestones/m2-control-plane/implementation-plan.md)  
**Đặc tả kỹ thuật:** [M2 technical spec](./milestones/m2-control-plane/spec.md)  
**Trạng thái:** `AUTHORIZED_FOR_PLANNING_AND_IMPLEMENTATION` ngày 13-09-2026 theo quyết định User Checkpoint sau khi M1 được chấp thuận. M3 và Phân hệ A tiếp tục `NOT AUTHORIZED`.

### Mục tiêu

Tạo lõi chung để mọi phân hệ sau có owner, trạng thái, revision, audit, config và UI debug thống nhất.

### Năng lực xây dựng

1. Workspace boundary và identity cơ bản.
2. PostgreSQL business state, migration discipline và transaction boundary.
3. Command/query envelope, Problem Detail, optimistic concurrency và idempotency record.
4. Transactional outbox, event checkpoint/deduplication và operation projection.
5. State machine nền cho operation, stage, job, batch và artifact location.
6. J: config/prompt/policy revision, account metadata, secret handle và capability view.
7. I: artifact/version/location metadata, chưa triển khai toàn bộ Drive lifecycle.
8. G: command receipt, stage shell, execution grant có recovery epoch, batch capacity reservation và completion ledger skeleton.

Hậu kiểm AUD2-B01 bổ sung VariantReservation/registry revision ở G, riêng với capacity. Contract và fixture theo CT-ORC-012; kiểm chứng TST-WF-VAR-001..004 trước nghiệm thu pipeline completion. Không phát sinh service hoặc milestone mới.
9. H: admin shell, bảng trạng thái, operation stream/SSE, log/session và error detail an toàn.

### Lát cắt user

User có thể:

- mở UI tiếng Việt;
- xem bảng operation/stage/job giả lập bằng fixture kiểm thử;
- gửi một command mẫu idempotent;
- thấy accepted khác running/succeeded/failed;
- sửa metadata/config revision được phép;
- xem lỗi chi tiết qua hover/focus mà không lộ secret;
- theo dõi SSE reconnect/resync.

Lát cắt này chưa thu thập tin hoặc tạo video.

### Test bắt buộc

- Contract/schema/version/error suite.
- Mọi transition hợp lệ và transition cấm của state nền.
- Concurrent command và `expected_revision` conflict.
- Outbox crash/replay và consumer deduplication.
- Workspace isolation, XSS, CSRF, Host/Origin, session và secret redaction.
- UI UTF-8, 1080p, bảng, error states và operation latency baseline.
- Migration tiến/lùi trên schema thử nghiệm.

### Exit gate

- 100% contract nền được test ở version hiện hành.
- Một command lặp không tạo hai aggregate; event lặp không tạo hai side effect.
- UI không có đường sửa article/script/event relation ngoài phạm vi.
- Secret không xuất hiện trong DB view rộng, UI, event, log hoặc workflow history.
- Mọi lỗi thử nghiệm có trạng thái, correlation và technical detail ref.
- User duyệt trải nghiệm nền và cách debug.

### Đầu ra cho mốc sau

- Public application ports và contract registry ổn định.
- Migration/outbox/audit/config/artifact foundations.
- UI shell để A-J bổ sung màn hình theo lát cắt.
- Test harness dùng lại cho component, contract và integration.

## 9. M3 — Thu thập và kho nội dung

### Mục tiêu

Hoàn thành A-B từ quản lý nguồn đến Article/Event có provenance, chống trùng và có thể xem/debug trên UI.

### Năng lực A — Nguồn và thu thập

1. Thêm, sửa metadata, bật/tắt, remove và restore nguồn trên UI.
2. Source tombstone chặn auto-discovery thêm lại.
3. Lập cycle theo chủ đề, Tier và ngưỡng tin mới không trùng.
4. SourceCandidate lifecycle/auto-registration theo policy; package tối thiểu và multi-topic count theo contract.

Các exit gate tương ứng phải có TST-COL-END-001..004 (retry/reconcile), TST-COL-PKG-001..004 (schema/content) và TST-SRC-RACE-001..004 (registration). Bảng chi tiết nằm trong module A implementation-plan và test strategy; policy title theo source kind vẫn chốt cùng extraction policy trước production.
5. Thu thập RSS/trang nguồn theo adapter được duyệt.
6. Snapshot bằng chứng, extraction candidate và media discovery.
7. Partial run, cursor/checkpoint, retry và lỗi nguồn độc lập.
8. Scheduler cloud hoạt động khi desktop offline.

### Năng lực B — Kho nội dung và sự kiện

1. Chuẩn hóa article revision và provenance.
2. Exact/near duplicate disposition và representative theo Tier.
3. Bài trùng chỉ bổ sung media/provenance, không tạo script mới.
4. Giữ bài độc lập khi liên kết event.
5. Phân biệt repost, nguồn mới và diễn biến mới thật sự.
6. Chỉ `EventUpdateAccepted` cấp quyền narrative “từ lúc đó đến nay”.
7. Tìm kiếm/lọc bài, event, topic, source và revision trên UI.

### Thứ tự lát cắt

1. Nguồn thủ công → fetch một bài → article revision.
2. Nhiều bài → dedup cluster → representative.
3. Repost có media mới → giữ media discovery.
4. Nhiều bài liên quan → event link hoặc kept separate.
5. Diễn biến mới → `EventUpdateAccepted`.
6. Cycle hằng ngày → Tier expansion → scheduler/offline behavior.

### Test và dữ liệu bắt buộc

- News Corpus, Duplicate Clusters và Event Timeline Set version đầu tiên.
- SSRF, redirect, MIME giả, HTML lỗi, timeout và nguồn không truy cập được.
- `NEW_ARTICLE`, `NEW_REVISION`, `DUPLICATE_MEDIA_ONLY`, `DUPLICATE_NO_NEW_VALUE`, `REJECTED_INCOMPLETE`.
- Representative cùng Tier ổn định và phá hòa bằng `source_id`.
- Không fact-check đa nguồn như hard gate; provenance vẫn bắt buộc.
- Scheduler đủ ngưỡng không mở Tier tiếp theo.
- Desktop offline không dừng collection cloud.

### Exit gate

- User có thể thêm nguồn và theo dõi từng lượt/stage/error trên UI.
- Article/Event truy ngược được source, fetch evidence và revision.
- Bài repost không tạo article/script candidate mới.
- Event update không bị đồng nhất với nguồn đăng lại.
- Một nguồn lỗi không dừng cycle còn lại.
- A-B contract, integration, failure và security tests đạt.
- User duyệt phân hệ A-B và `R1 Content Alpha`.

### Điểm còn mở phải chốt trước hoặc trong M3

- `QUALITY-OPEN-002`: thời gian tối đa một cycle, chỉ cần trước khi tuyên bố performance đạt.
- `QUALITY-OPEN-005`: proxy hot/trending, phải chốt trước khi nghiệm thu content selection.
- `QUALITY-OPEN-014`/`TEST-OPEN-009`: múi giờ schedule/log/folder, phải chốt trước lịch production.
- Ngưỡng tin mới không trùng từng chủ đề là config revision, không hard-code.

## 10. M4 — Kho media, hook và lưu trữ hybrid

### Mục tiêu

Hoàn thành C-I đủ để original, rendition, hook và output tương lai có identity, provenance, integrity, availability và vòng đời an toàn giữa cloud/desktop.

### Năng lực C — Danh mục media và hook

1. Nhập media discovery từ bài và official social source.
2. Một byte có nhiều provenance; một media logic có nhiều rendition.
3. Index metadata/semantic/technical có version.
4. Kho visual hook và audio hook độc lập; user nhập và sửa metadata trên UI.
5. Candidate query theo scene/entity/topic, score components, availability, safety và risk.
6. Media nguồn lịch sử vẫn khai thác được sau khi source bị remove.
7. Usage kỹ thuật tách production usage; `MediaUsage` C cùng commit/rollback với completion unit of work.

### Năng lực I — Artifact và storage

1. Artifact, immutable version và location model.
2. Upload resumable/idempotent, verify integrity và outcome-unknown reconciliation.
3. Placement theo loại dữ liệu trên bốn tài khoản/namespace được kiểm chứng.
4. Materialize local gần lượt xử lý, lease và hash verification.
5. SQLite local journal/recovery checkpoint.
6. Working set theo policy khoảng năm video; prefetch có admission control.
7. Cleanup authorization theo ledger, lease, path và recovery epoch.
8. Output path allocator, sanitize title/hashtag và folder session hợp lệ.

### Năng lực E nền tảng

- Probe media thực, không tin extension/MIME.
- Technical metadata và corruption detection.
- Image safety assessment contract và transform pipeline cơ bản.
- Original luôn tách rendition; reusable khác temporary.
- Không chạy safety blur/recolor trên clip.

### Lát cắt user

User có thể:

- xem media gắn với bài/event;
- nhập visual/audio hook;
- sửa tag, ghi chú, trạng thái bật/tắt;
- xem original/rendition/provenance/safety/availability;
- yêu cầu tải/xử lý lại một asset;
- quan sát upload, verify, lỗi và cleanup state.

### Test bắt buộc

- `INV-008`, `INV-011`, `INV-012`, `INV-015` phần liên quan.
- Upload gián đoạn trước/trong/sau side effect.
- Same byte retry, byte khác version mới, hash mismatch và object missing.
- Path traversal, symlink/junction, reserved name, hashtag, Unicode và collision.
- Source removed nhưng media lịch sử vẫn query được.
- Sensitive Image Set gồm safe, trẻ em, máu me, vũ khí, uncertain, detector/transform failure và unreadable.
- Clip không bị safety transform.
- Desktop restart/reconcile và cleanup authorization cũ bị từ chối.

### Exit gate

- Không location nào thành verified nếu chưa có integrity evidence.
- Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified.
- Render tương lai chỉ có thể lấy artifact local đã verify.
- UI phân biệt original, processed, uncertain, failed và unavailable.
- Drive/OAuth/integrity phần M4 của G04 đạt trên tài khoản test thật.
- User duyệt C-I và `R2 Media Alpha`.

### Điểm còn mở phải chốt trước hoặc trong M4

- Storage placement/quota thật của bốn tài khoản sau G04.
- Retention original, reusable, temporary, log và evidence.
- Scale dataset cho catalog/index.
- Cơ chế checksum/integrity cụ thể nếu Drive không cung cấp cùng checksum cho mọi tệp.

## 11. M5 — Bộ não nội dung AI

### Mục tiêu

Hoàn thành D từ snapshot bất biến đến production plan, có biến thể, provenance, disclosure và đánh giá chất lượng có thể tái tạo.

### Năng lực xây dựng

1. `ProductionSnapshot` khóa exact article/event/source/config/prompt/index revisions trước script.
2. Content analysis: entities, timeline, claim/evidence, uncertainty và media needs.
3. StoryAngle generation: 1-3 góc khác nhau trong cùng lượt.
4. Script generation tiếng Anh, 61-70 giây mục tiêu và pronunciation hints.
5. `source_backed`, `inference`, `creative_hypothesis`, `transition` theo segment.
6. Disclosure bắt buộc cho inference/creative content.
7. `from_then_to_now` chỉ khi có `EventUpdateAccepted`.
8. Query/chọn visual hook, audio hook, thumbnail, media, music/SFX intent.
9. Production plan có scene/timeline/fallback/preset intent.
10. Variant validation trong cùng lượt và giữa các lượt.
11. Title/caption tiếng Anh và 3-4 hashtag, có representation an toàn cho filename.
12. J điều phối provider/model/account/project/role, quota và fallback có version.
13. Giữ biên instruction-data cho nội dung nguồn không tin cậy; mọi ref/tool intent từ model qua resolver/allowlist độc lập.

### Thứ tự lát cắt

1. Snapshot + analysis trên một article.
2. Một StoryAngle + script có claim annotations.
3. Ba StoryAngle cùng lượt và validator khác góc.
4. Media/hook candidate query + selection rationale.
5. Production plan hoàn chỉnh nhưng chưa render.
6. Variant mới ở lượt sau và exact-duplicate rejection.
7. Event timeline mode có/không có update.
8. Provider failure/fallback giữ queue/history.

### Test và đánh giá bắt buộc

- RED/GREEN cho `INV-004`, `INV-005`, `INV-006`, `INV-013`, `INV-014`.
- Config/source đổi sau snapshot không làm job cũ thay đổi.
- AI response sai schema, thiếu field, hallucinated ref và timeout/rate limit.
- 100% inference/creative segment có disclosure.
- Topic classification đạt ít nhất 90% trên mẫu được user đánh giá.
- Event links đạt yêu cầu ít nhất 95% không gộp nhầm.
- Media/thumbnail đạt ít nhất 90%; hook combination đạt ít nhất 90%.
- Không dùng model tự tạo làm judge duy nhất.
- Locked holdout set tách khỏi prompt-development set.

### Exit gate

- Mọi output D truy được snapshot, model, prompt, config và input revision.
- Ba video cùng lượt không chỉ đổi style mà thật sự khác StoryAngle.
- Variant lượt sau không exact duplicate và có khác biệt thực tế được ghi.
- Narrative timeline bị chặn khi chỉ có repost/nguồn mới.
- Provider lỗi không làm mất job/history và không tự thêm dịch vụ trả phí.
- G06 phần content đạt hoặc có defect/gap rõ; chưa tuyên bố toàn G06 nếu E/F chưa đạt.
- User duyệt D và `R3 Creative Alpha`.

### Điểm còn mở phải chốt trước hoặc trong M5

- `TEST-OPEN-001`: sampling plan cho ngưỡng 90%/95%.
- Ngưỡng dedup và event-link confidence sau corpus evaluation.
- Proxy hot/trending trước content-selection acceptance.
- Provider/model/prompt cụ thể theo vai trò sau benchmark, không khóa bằng suy đoán.

## 12. M6 — Media production, render và video alpha

### Mục tiêu

Hoàn thành E-F để một job được giám sát có thể tạo voice, timing, media renditions, render, QC, sync và completion an toàn.

### Năng lực E — Processing, voice và timing

1. Reusable crop/resize/normalize/transcode/extract-frame operations có lineage.
2. Image safety detection/transform theo policy đã chốt; clip chỉ xử lý kỹ thuật.
3. TTS voice gắn exact script fingerprint.
4. Word timing gắn exact script/voice hash và có confidence/gap report.
5. Music/SFX preparation, loudness và mix constraints.
6. Invalidation downstream khi script, voice hoặc artifact revision đổi.

### Năng lực F — Preset, render và QC

1. Thiết kế chi tiết đúng năm preset, mỗi preset có revision.
2. Resolve immutable render package với exact artifact refs/hash.
3. Validate input sớm trước render nặng.
4. Render attempt/receipt và outcome-unknown reconciliation.
5. QC tự động cho playability, duration, output profile, hook, thumbnail, voice, subtitle và bằng chứng tiếng Anh của exact revisions.
6. Burn-in English subtitle và karaoke timing từng từ.
7. Kiểm tra disclosure đầu ra khi có inference/creative segment.
8. Đồng bộ cloud, verify output rồi G mới commit completion ledger.

### Lát cắt user

User chọn một job/script/plan, chạy từng stage E-F, xem artifact/report, thử lại hoặc tạo biến thể mới, rồi nhận một video hợp lệ đã sync. Không có script editor hoặc approval workflow.

### Test bắt buộc

- `INV-007`, `INV-008`, `INV-009`, `INV-010`, `INV-011` đầu-cuối.
- Word timing monotonic, coverage, exact binding và invalidation.
- Render package thiếu hook/audio hook/thumbnail trong vùng hook/voice/timing phải fail sớm.
- FFmpeg crash, partial file, timeout sau side effect và output corrupt.
- 100% output được tính hoàn thành: phát được, 61-70 giây, tiếng Anh, đủ hook, thumbnail trong vùng hook, subtitle và cloud verified.
- Audio measurement kết hợp user nghe mẫu; visual/karaoke review theo mẫu.
- Output filename/folder đúng policy trên desktop và Drive.
- Render success, QC pass, upload success và completion là bốn mốc riêng.

### Exit gate

- Tạo được `R4 Video Alpha` theo luồng giám sát từ snapshot đến completion.
- Không output nào được đếm trước cloud verification.
- Không local output bị xóa khi sync/completion chưa đủ.
- F không tự đổi script/góc/media ngoài fallback plan.
- G06 phần TTS/timing/media và G07 phần output/QC có evidence.
- User duyệt E-F và 5 preset mẫu.

### Điểm còn mở phải chốt trước M6 exit

- `QUALITY-OPEN-006`/`TEST-OPEN-005`: output profile chính thức.
- `QUALITY-OPEN-007`/`TEST-OPEN-006`: ngưỡng sai số word timing.
- Tên, style và thông số chi tiết của 5 preset.
- Audio quality/visual continuity thresholds dùng cho warning hoặc hard gate.

## 13. M7 — Tự động hóa lô, hardening và baseline vận hành

### Mục tiêu

Nối mọi phân hệ thành quy trình tự động có thể chịu lỗi, đạt các gate đã phê duyệt và có quy trình vận hành/khôi phục rõ ràng.

### Năng lực hoàn thiện G-H-J

1. Batch target do user đặt; allocation theo vòng và 1-3 video/tin/lượt.
2. Child workflow cô lập lỗi; waiting/resume theo capability.
3. Retry và variant là hai command/semantics khác nhau.
4. Desktop reconnect không chạy lại từ đầu; sẵn sàng tiếp tục trong 5 phút.
5. Auto mode dùng cùng handlers/contract với debug mode.
6. UI hoàn chỉnh cho source, article/event, media/hook, job/stage/batch/session/log/config/account/cost.
7. SSE reconnect/resync và no-silent-failure reconciliation.
8. Provider/account routing, quota, health, 80% budget forecast warning.
9. Resource admission cho CPU/GPU/RAM/disk/network và working set.
10. Maintenance/reconcile/cleanup/recovery workflows.

### Chuỗi hardening

1. Full contract/state/integration regression.
2. E2E-001 đến E2E-014 theo tài liệu 10.
3. Fault injection ở mọi ranh giới side effect.
4. Security test trust boundary, SSRF, path, XSS, secret, OAuth và workspace.
5. G01 workflow/replay/recovery đầy đủ.
6. G04 Drive/OAuth/security đầy đủ.
7. G05 isolated restore/recovery epoch nếu tuyên bố backup dùng được.
8. G06 locked evaluation sets và user acceptance.
9. G07 target desktop/UI/QC/compatibility.
10. G02 benchmark 100 video hợp lệ/12 giờ và ít nhất 95% tự động.
11. G03 workload tháng và incremental cost dưới 50 USD.
12. Pilot vận hành, defect burn-down và release audit.

### Exit gate cho `R5 Unattended Beta`

- Batch chạy không giám sát trên workload đại diện.
- Một video/nguồn/provider lỗi không làm dừng việc độc lập.
- Không job biến mất không trạng thái/log.
- Resume, retry, reconcile và cleanup qua fault suite.
- Không P0/P1 mở và không hard-gate/INV test bị quarantine.

### Exit gate cho `R6 Operational Baseline`

- G01-G07 có evidence đạt hoặc gate không thuộc claim được ghi rõ và user chấp nhận phạm vi.
- Tối thiểu 100 video hợp lệ đã sync trong 12 giờ trên máy mục tiêu.
- Ít nhất 95% video đủ đầu vào hoàn thành không cần thao tác sau khi bắt đầu lô.
- UI p95, command ACK, resume và scheduler đạt ngưỡng đã duyệt trên workload đã khóa.
- Chất lượng topic/event/media/hook/safety đạt ngưỡng đã duyệt.
- Incremental cost dưới 50 USD/tháng theo phạm vi R20 và có cảnh báo 80%.
- Runbook, recovery, credential rotation, capacity, upgrade và rollback được kiểm thử.
- User nghiệm thu baseline.

### Điều cấm

- Không tối ưu throughput bằng cách bỏ QC, sync, provenance hoặc cleanup safety.
- Không loại video lỗi khỏi mẫu số 95% nếu lỗi thuộc hệ thống.
- Không dùng benchmark ngắn rồi ngoại suy thành 12 giờ.
- Không dùng mock để đóng Drive/OAuth/AI/render/restore gate.
- Không phát hành khi contract/state migration hoặc workflow replay chưa tương thích.

## 14. Bản đồ phân hệ theo milestone

| Phân hệ | M1 | M2 | M3 | M4 | M5 | M6 | M7 |
|---|---|---|---|---|---|---|---|
| A Nguồn/thu thập | Proof I/O nếu cần | Contract shell | Hoàn thiện alpha | Media discovery integration | Cung cấp snapshot input | Regression | Auto/hardening |
| B Nội dung/sự kiện | Schema proof | Owner/state shell | Hoàn thiện alpha | Media relations | Snapshot/event input | Regression | Scale/hardening |
| C Media/hook | Artifact contract proof | Metadata shell | Nhận discovery | Hoàn thiện alpha | Candidate selection | Render integration | Scale/hardening |
| D Trí tuệ nội dung | AI adapter feasibility nhỏ | Config/contract shell | Không production | Index contract | Hoàn thiện alpha | Plan/render feedback | Quality/hardening |
| E Xử lý media/audio | Tool compatibility proof | Stage shell | Không production | Probe/image nền | Contract với plan | Hoàn thiện alpha | Capacity/hardening |
| F Preset/render/QC | Media tool proof | Stage shell | Không production | Artifact contract | Render-plan contract | Hoàn thiện alpha | Throughput/hardening |
| G Điều phối | Workflow proof | Core state/receipt | Collection workflow | Storage workflow | Creative workflow | Video workflow | Batch hoàn chỉnh |
| H Giao diện | Không hoặc proof nhỏ | Admin shell | A-B screens | C-I screens | D screens | E-F screens | Full operations UI |
| I Lưu trữ | Drive/journal proof | Artifact metadata | Raw snapshots | Hoàn thiện alpha | AI artifact refs | Output sync/cleanup | Recovery/capacity |
| J Cấu hình/secret | OAuth/secret proof | Core hoàn thiện | Source policies | Storage accounts | AI routing | Preset/tool config | Cost/health/rotation |

“Hoàn thiện alpha” chỉ nghĩa năng lực của phân hệ đủ dùng thử theo milestone, không phải đóng mọi performance/security gate của production.

## 15. Công việc có thể song song

Sau khi dependency tương ứng được khóa, có thể chạy song song:

| Workstream | Có thể chạy song song với | Điều kiện không được phá |
|---|---|---|
| Golden datasets/rubric | M2-M6 implementation | Schema ID/revision ổn định; holdout không rò vào prompt development |
| UI screen theo contract | Backend module cùng milestone | Dùng contract fixtures; không tự tạo API/field ngoài hợp đồng |
| Adapter provider | Domain logic dùng fake | Cùng provider contract suite; secret boundary đã có |
| Media corpus/render fixtures | M4-M5 | Output profile chưa chốt phải parameter hóa |
| Security threat cases | M1-M7 | Không đợi cuối mới tạo canary/fault corpus |
| Observability dashboard | M2-M7 | Metric/event owner rõ; không đọc chéo DB ngoài contract |
| Documentation/runbook | Mỗi milestone | Chỉ mô tả behavior đã test; không tuyên bố gate sớm |

Không song song hóa nếu hai workstream đang cùng thay đổi một contract/state machine chưa được review. Khi đó owner contract phải khóa revision trước.

## 16. Definition of Ready cho một milestone

Milestone chỉ được bắt đầu khi:

1. Milestone trước đạt exit gate và có user checkpoint.
2. Phạm vi, owner và dependency được ghi rõ.
3. Contract/state machine liên quan đã review.
4. Open item chặn milestone đã được quyết định hoặc có proof cụ thể.
5. Test cases có oracle; fixture/golden data có kế hoạch.
6. Migration, rollback và failure scenarios được mô tả.
7. Provider/account/hardware cần thiết khả dụng hoặc milestone ghi rõ `BLOCKED_EXTERNAL`.
8. Không có thay đổi yêu cầu mới chưa đi qua change control.

## 17. Definition of Done cho work package

Một work package tạo code chỉ hoàn thành khi:

- RED được xác nhận trước implementation;
- implementation và regression suite GREEN;
- positive, boundary, error và recovery cases liên quan đạt;
- contract/schema/version không bị phá;
- migrations có đường tiến/lùi hoặc forward-fix được duyệt;
- logs/metrics/traces không lộ secret và đủ correlation;
- tài liệu và test evidence cập nhật;
- không có P0/P1 phát sinh chưa xử lý;
- code coverage đạt policy đã phê duyệt;
- reviewer xác nhận không vượt scope.

“Đã viết xong” hoặc “chạy được trên máy dev” không phải Definition of Done.

## 18. Definition of Done cho milestone

Ngoài mọi work package hoàn thành, milestone cần:

1. Lát cắt user trong milestone hoạt động trên môi trường mục tiêu tương ứng.
2. Acceptance/failure/security/performance tests trong scope đạt.
3. Không có test hard gate/INV bị fail hoặc quarantine.
4. Dữ liệu cũ và output của milestone trước không bị hỏng.
5. Upgrade/rollback/recovery path được thử ở mức phù hợp.
6. Evidence manifest và known limitations đầy đủ.
7. Open item mới được phân loại, không giấu trong backlog chung.
8. User duyệt năng lực của milestone trước khi chuyển bước.

## 19. Bản đồ G01-G07 theo thời điểm

| Gate | Proof sớm | Xây dần | Lần đóng chính | Nếu thất bại |
|---|---|---|---|---|
| G01 Workflow | M1: code-revision replay, crash/retry/offline/stale/child trong scope proof | M2-M6 replay/fault và upgrade/runtime path | M7 | Mở ADR-0003; thay adapter/engine trước mở rộng |
| G02 Throughput | Capability baseline M1 | Stage metrics M3-M6 | M7, run 12 giờ | Tối ưu bottleneck/capacity; không hạ hard gate |
| G03 Cost | Cost model M1-M2 | Usage records M3-M6 | M7, workload tháng | Đổi placement/provider/concurrency; không tự thêm trả phí |
| G04 Drive/OAuth/Security | M1: Drive/OAuth account thật, upload/integrity/revoke/refresh trong scope proof | M2/M4/M6: local HTTPS/Origin, Temporal authorization, account pool và production path | M7 | Mở ADR-0006/0009; chặn cleanup/unattended |
| G05 Restore | Recovery design M1-M2 | Journal/reconcile M4-M6 | M7 khi claim restore | Chặn claim backup và writer/cleanup sau restore |
| G06 AI/Content | Sampling plan M3-M4 | D ở M5, E/F ở M6 | M7 regression | Đổi model/prompt/threshold qua revision; không cherry-pick |
| G07 Compatibility/UI/QC | Matrix smoke M1 | UI/tool/profile M2-M6 | M7 | Pin/đổi version hoặc output profile trước release |

Một gate có thể có proof đạt sớm nhưng vẫn phải chạy lại khi production path, version hoặc workload thay đổi. Trạng thái trước test là `NOT_TESTED`; proof M1 đạt dùng `PASS_M1_SCOPE`, còn gate tổng thể dùng `PARTIALLY_PROVEN`. Chỉ lần đóng chính có đủ toàn bộ evidence mới dùng `PASS` không kèm phạm vi.

## 20. Risk register và trigger re-plan

| Mã | Rủi ro | Tác động | Trigger | Hành động |
|---|---|---|---|---|
| `RM-RISK-001` | Workflow engine không giữ đúng replay/fencing semantics | Làm lại G và trạng thái chạy | M1 G01 fail | Dừng M2 dependency, mở ADR-0003 |
| `RM-RISK-002` | Drive integrity/quota/OAuth không phù hợp | Mất/nhân bản tệp, không cleanup an toàn | M1/M4 G04 fail | Đổi adapter/storage design, giữ Artifact contract |
| `RM-RISK-003` | Một PostgreSQL host nghẽn bởi nhiều workload | UI/job chậm, không đạt throughput | Query/lock/WAL/resource metric vượt bound | Tối ưu/index/admission; chỉ tách khi metric chứng minh |
| `RM-RISK-004` | Desktop không đạt 100 video/12 giờ | Không đạt mục tiêu sản lượng | Stage profile/soak cho thấy critical bottleneck | Tối ưu pipeline/prefetch/preset hoặc tăng tài nguyên được duyệt |
| `RM-RISK-005` | AI quality không đạt 90%/95% | Script/media/event sai | Locked evaluation fail | Đổi model/prompt/validator; giữ output contract và history |
| `RM-RISK-006` | Word timing/karaoke không đạt | Video fail hard gate | Corpus/user review fail | Đổi aligner/pipeline; không bỏ karaoke gate |
| `RM-RISK-007` | Pool 4 account không tạo quota độc lập | Throughput/quota thấp hơn dự kiến | G04/J observations | Route theo quota domain thật, không nhân giả capacity |
| `RM-RISK-008` | Provider/version/license thay đổi | Build/replay hoặc quyền dùng hỏng | Compatibility/license scan fail | Pin/upgrade có proof; ADR nếu đổi lớn |
| `RM-RISK-009` | Dữ liệu/index tăng nhanh | Query/UI/backup suy giảm | Scale metrics vượt bound | Partition/archive/index/tách read workload theo evidence |
| `RM-RISK-010` | Secret/path/SSRF boundary bị phá | Lộ tài khoản hoặc hại máy/cloud | Security test/incident | Chặn release, rotate/contain, sửa và regression test |
| `RM-RISK-011` | User acceptance trở thành bottleneck | Gate G06/G07 kéo dài | Golden sample chưa được chấm đúng hạn | Chuẩn bị mẫu/rubric sớm, đánh giá theo milestone |
| `RM-RISK-012` | Rủi ro quyền nội dung/tài nguyên | Khiếu nại hoặc nguồn mất | Source/right state thay đổi | Giữ provenance/risk status; vận hành theo chấp nhận rủi ro của user |

Không gán xác suất định lượng cho các rủi ro trên vì chưa có dữ liệu thực nghiệm.

## 21. Quản lý thay đổi và re-plan

Re-plan bắt buộc khi:

- user thay đổi mục tiêu, phạm vi hoặc hard gate;
- proof phủ định ADR;
- contract breaking change xuất hiện;
- milestone fail cùng blocker ba vòng sửa liên tiếp;
- dependency/provider/license thay đổi làm cách tiếp cận không còn hợp lệ;
- benchmark cho thấy kiến trúc không đạt throughput/cost;
- security finding thay đổi trust boundary;
- công việc phát sinh vượt quá phạm vi milestone đã duyệt.

Quy trình:

1. Ghi thay đổi và bằng chứng.
2. Đánh giá ảnh hưởng tới tài liệu 00-11, ADR, contract, test và milestone chưa làm.
3. Không sửa hồi tố evidence của milestone đã hoàn thành.
4. Cập nhật roadmap/status/dependency/risk.
5. Trình user duyệt delta trước khi tiếp tục phần bị ảnh hưởng.

## 22. Lập kế hoạch thời gian và nguồn lực

Roadmap hiện **không đưa ra số tuần/tháng** vì chưa biết:

- số người và mức thời gian thực tế dành cho dự án;
- mức độ quen thuộc với stack đã chọn;
- quyền truy cập provider/account/hardware test;
- số adapter nguồn cần làm trong baseline;
- tốc độ user đánh giá golden samples/presets;
- kết quả proof và số vòng sửa.

Sau M0, mỗi milestone được ước lượng bằng work package có:

- dependency;
- độ phức tạp và rủi ro;
- thời gian code/test/review/fix/evidence;
- external waiting time tách riêng;
- contingency cho proof có rủi ro cao;
- owner và capacity thật.

Không dùng tổng số dòng code hoặc số màn hình làm thước đo tiến độ.

## 23. Open items và hạn quyết định

| Mã | Vấn đề | Chặn mốc nào | Hạn quyết định |
|---|---|---|---|
| `ROADMAP-OPEN-001` | Nhân lực/capacity và lịch calendar | Không chặn thứ tự; chặn ngày cam kết | Sau M0 |
| `ROADMAP-OPEN-002` | `CLOSED_FOR_M1_R1` — version set M1 đã khóa; không đóng compatibility/G01/G04/G07 | Không chặn M1-P0..P6 trong phạm vi R1; version khác cần revision mới | Đã đóng cho M1-R1 ngày 13-09-2026 |
| `ROADMAP-OPEN-003` | `OPEN — BLOCKS M1-P3 ONLY` — tài khoản test, quota và OAuth access thật | Chặn M1-P3 và `G04_M1_SCOPE`; không chặn M1-P0/P1/P2 | Trước khi thực hiện external proof M1-P3 |
| `ROADMAP-OPEN-004` | Múi giờ production | M3 scheduler | Trước bật lịch production |
| `ROADMAP-OPEN-005` | Proxy hot/trending | M3/M5 acceptance | Trước đóng content selection |
| `ROADMAP-OPEN-006` | Sampling plan và cỡ mẫu | M5/M7 G06 | Trước khóa holdout set |
| `ROADMAP-OPEN-007` | Output profile | M6 | Trước render/QC exit |
| `ROADMAP-OPEN-008` | Word timing tolerance | M6 | Trước G07 output acceptance |
| `ROADMAP-OPEN-009` | Năm preset chi tiết | M6 | Trước Video Alpha |
| `ROADMAP-OPEN-010` | Retention/storage placement | M4/M7 | Trước unattended cleanup |
| `ROADMAP-OPEN-011` | Scale workload | M7 | Trước performance/scale claim |
| `ROADMAP-OPEN-012` | Backup/restore scope triển khai | M7 G05 | Trước bật writer/cleanup sau restore |

Open item không được trì hoãn quá milestone ghi ở cột “Chặn mốc nào”. Nếu chưa chốt, phần bị chặn kết luận `NOT_READY` hoặc `BLOCKED_EXTERNAL` theo plan, không dùng default ẩn. Riêng ROADMAP-OPEN-003 thiếu credential thật làm M1-P3 `BLOCKED_EXTERNAL`; không được dùng mock để tuyên bố G04 PASS, nhưng không làm P0/P1/P2 mất trạng thái READY.

## 24. GIẢ ĐỊNH

**Không có GIẢ ĐỊNH chưa được xác nhận nào được dùng để cam kết lịch hoặc tuyên bố milestone sẽ đạt.**

Các giả định kỹ thuật `AS-CTR-001..004` vẫn được xử lý bằng G01, G02, G04 và G07. Khả năng có đủ tài khoản test, quota, phần cứng và thời gian user đánh giá hiện là **CHƯA KIỂM CHỨNG**, vì vậy roadmap dùng dependency gate thay cho ngày cố định.

## 25. Những thứ roadmap không đưa vào v1

- Xuất bản YouTube hoặc tự đăng lên nền tảng.
- SaaS nhiều tenant, billing, public remote access hoặc SLA nhiều khách.
- Google Sheets làm cơ sở dữ liệu chính hoặc bắt buộc trong runtime path.
- Trình sửa article/script/event relation hoặc approval workflow.
- Fact-check đa nguồn bắt buộc.
- Safety blur/recolor cho clip.
- Cam kết viral hoặc đo hiệu quả sau đăng.
- Tự thêm dịch vụ AI trả phí khi fallback.
- Cam kết khôi phục sau mất toàn bộ kho ngoài phạm vi user đã chốt.

Mục ngoài v1 chỉ được thêm qua change control, không chen vào milestone đang chạy.

## 26. Tài liệu thực thi milestone sau khi duyệt

Roadmap này chỉ giữ bức tranh tổng thể. Sau khi user duyệt roadmap và M0 cho phép code, mỗi milestone phải có plan riêng, nhỏ và tự đủ ngữ cảnh, bao gồm:

- goal và data flow;
- contract/state được triển khai;
- test cases phải RED trước;
- task/dependency và phạm vi file dự kiến;
- failure scenarios;
- performance/security constraints;
- rejection criteria;
- migration/rollback;
- acceptance/evidence;
- checkpoint user.

Không viết trước toàn bộ phase implementation plans khi proof M1 có thể làm thay đổi kiến trúc nền.

## 27. Biên bản phê duyệt roadmap

User đã xác nhận ngày 13-09-2026:

1. Đồng ý thứ tự M0-M7 và critical path.
2. Đồng ý proof G01/G04 diễn ra trước khi xây sâu production modules.
3. Đồng ý mỗi milestone có user checkpoint và không chuyển bước khi exit gate chưa đạt.
4. Đồng ý không gán lịch calendar trước khi có capacity/proof data.
5. Đồng ý `R4 Video Alpha`, `R5 Unattended Beta` và `R6 Operational Baseline` là ba mức khác nhau.
6. Đồng ý mở lại ADR khi proof phủ định quyết định `Conditional`.

Các điều kiện trên đã được chấp thuận cùng baseline 00–12, ADR, contracts, audit và kế hoạch Phân hệ A. M0 chuyển `APPROVED/CLOSED`; quyền code chỉ áp dụng M1 Evidence Prototype. M2, M3 và implementation Phân hệ A tiếp tục bị khóa cho tới khi M1 đạt exit gate, được audit và user xác nhận checkpoint tiếp theo.

Lệnh triển khai M1 đã được nhận ngày 13-09-2026. M1-P0 và M1-P1 đã PASS theo evidence tương ứng; M1 vẫn `IN PROGRESS`, M2/M3/Phân hệ A tiếp tục bị khóa và không được suy ra là đã có quyền triển khai.

## Trạng thái sau khắc phục audit M1 R1

Ba BLOCKER và năm MAJOR đã được đóng sau remediation/review. P0/P1 `PASS`; P2 `READY`. Kết quả không làm M1 PASS, không thay đổi G01/G04 `NOT TESTED` và không cấp quyền cho M2/M3/Module A.
