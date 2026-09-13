# 13. Truy vết, kiểm toán và điểm còn mở

> Trạng thái: **Bản thiết kế trước triển khai**  
> Mục tiêu: chứng minh các hợp đồng bao phủ quyết định đã chốt và nêu rõ điều chưa thể khóa trước thử nghiệm.

## 1. Luồng xuyên suốt theo hợp đồng

1. G gọi `PlanCollectionCycle`; A tạo quyết định nguồn theo Tier/ngưỡng.
2. G/A chạy `CollectSource`; A phát `CollectedDocumentAvailable` qua outbox.
3. B nhận `CollectedDocumentPackage`, chuẩn hóa, chống trùng và chọn article đại diện.
4. Nếu bài trùng, B không tạo bài/script mới; C nhận media/provenance mới nếu có.
5. B liên kết event và chỉ phát `EventUpdateAccepted` khi có diễn biến/tình tiết mới.
6. G giữ `BatchCapacityReservation` rồi phân bổ `VideoJob`; D commit `ProductionSnapshot` trước lần tạo script đầu tiên.
7. D tạo 1-3 góc kể khác nhau, script có claim mode, chọn hook/media và tạo production plan.
8. E materialize/chuẩn hóa asset cần thiết, tạo voice và word timing theo exact script/hash.
9. F resolve package bất biến, render và kiểm tra hard gates.
10. I upload video đầu ra và verify cloud location.
11. G/C cùng completion unit of work: G commit `CompletionLedger`/capacity conversion, C commit `MediaUsage`, tăng batch count đúng một lần rồi phát `VideoCompleted`.
12. I cấp quyền rồi dọn local staging; original/reusable/output cloud tiếp tục được giữ theo policy.

Luồng media song song:

1. A/B phát hiện media cùng provenance.
2. C định danh media asset và yêu cầu I lưu original.
3. E phân tích/index/transform; C ghi rendition và metadata, I ghi artifact/location.
4. D query candidate bằng chỉ mục, quyết định lựa chọn và khóa refs trong plan.
5. I chỉ tải local khi job gần tới lượt, tối đa working set theo policy cho 5 video.

## 2. Ma trận quyết định R01-R25

| Quyết định | Hợp đồng thể hiện | Invariant chính |
|---|---|---|
| R01 | CT-CNT-006, CT-QC-002 | Đủ dữ liệu và truy nguồn; không bắt buộc fact-check đa nguồn |
| R02 | CT-API-005, CT-AI-004 | Xem/tạo lại; không sửa script hay duyệt |
| R03 | CT-SUB-001, CT-QC-001 | Burn-in subtitle và timing từng từ |
| R04 | CT-SRC-004 | Chỉ mở Tier tiếp theo khi chưa đủ |
| R05 | CT-MED-007 | Cho tìm/tải bổ sung theo video |
| R06 | CT-CNT-004 | Giữ bài riêng; tổng hợp khi liên kết đủ chắc |
| R07 | CT-CNT-005 | Repost không phải diễn biến mới |
| R08 | CT-CNT-002 | Đại diện theo Tier |
| R09 | CT-AI-001, CT-CFG-001 | Snapshot khóa nguồn/config sau khi bắt đầu script |
| R10 | CT-ORC-001/002/008/010 | Target do user đặt; giữ suất nguyên tử; dừng khi đạt hoặc exhausted |
| R11 | CT-HOOK-001, CT-AI-006 | User cung cấp audio hook; hệ thống tìm nhạc/SFX |
| R12 | CT-MED-002, CT-MED-009 | Quyền không chắc vẫn được dùng, có trạng thái rủi ro |
| R13 | CT-PROC-008, CT-STO-010 | Giữ original/reusable; voice/subtitle có thể dọn |
| R14 | CT-API-003/004 | Chỉ sửa metadata quản trị |
| R15 | CT-API-003 | Nguồn quản lý trực tiếp trên UI, không cần file text riêng |
| R16 | CT-API-009, CT-CFG-001 | Config mới áp dụng job chưa bắt đầu script |
| R17 | CT-WF-008, CT-ORC-005/006 | Retry và biến thể là hai lệnh |
| R18 | CT-AI-001, CT-STO-004 | Cloud giữ tin/media/index; script/voice khi desktop online theo route |
| R19 | CT-ORC-007, CT-AI-ROUTE-002 | Việc không cần AI tiếp tục; AI chờ/fallback local; không tự trả phí |
| R20 | CT-COST-001 | Chỉ tính incremental cost |
| R21 | README mục 6 | 10 phân hệ A-J là biên trách nhiệm |
| R22 | CT-CNT-001/002, CT-MED-001 | Bài trùng không tạo script, vẫn bổ sung media/provenance |
| R23 | CT-SRC-004 | Ngưỡng tin mới không trùng theo chủ đề; một article đại diện tính một lần/topic/business-date |

### 2.1. Crosswalk các yêu cầu được sửa sau final audit

| Requirement/audit concern | Thiết kế/hợp đồng có thẩm quyền | Kiểm thử bắt buộc |
|---|---|---|
| Thumbnail phải ở trong hook | FR-HOOK-007, FR-REN-004 → CT-MED-004/006, CT-AI-007, CT-RND-003, CT-QC-001 | Test package thiếu/sai time range; kiểm byte output có thumbnail trong vùng hook |
| Một periodic run/source/business-date | FR-COL-001 → CT-SRC-004, CT-STATE-002 | Hai scheduler, đổi policy, retry và restart không tạo run thứ hai |
| Recovery fencing | DR-009/020 → CT-CMN-001 và mục 14 common contract, CT-WF-004/006, CT-EVT-002/005, CT-STO-009 | INV-016 và G05 restore với epoch cũ/generation trùng |
| Completion và media usage | DR-020 → CT-MED-008, CT-ORC-008/009 | INV-017 crash/race: cùng commit hoặc cùng rollback |
| Folder `YY-MM-DD` | FR-OUT-001/002 → CT-RND-006, CT-STO-011 | Phiên đầu/sau trong ngày, năm khác nhau, session rỗng |
| Collection retry state | CT-SRC-005 → CT-STATE-002 | Attempt retryable/wait/retry/final và terminal immutability |
| Tiếng Anh và ảnh vũ khí | QR-SAFE-004, QR-OUT-004, QR-COMP-004 → CT-PROC-005/006, CT-RND-002/003, CT-QC-001 | Sensitive Image Set và exact-revision English evidence |
| Không vượt batch target | R10 → CT-ORC-002/008 | INV-018 và TST-E2E-005 với hai allocator |
| Candidate/package/topic semantics | FR-SRC-004, FR-SRC-011 → CT-SRC-003A/004/006, CT-STATE-002A | Candidate lifecycle, incomplete package và multi-topic counting |
| Dữ liệu nguồn không điều khiển AI | ARCH-012/10.2 → CT-CMN-013, CT-AI-000 | Security Corpus có indirect prompt injection và ref sai workspace |
| R24 | CT-SRC-003, CT-MED-009 | Remove dừng thu thập; dữ liệu cũ vẫn khai thác |
| R25 | CT-PROC-005/006 | Ảnh đọc được vẫn dùng khi uncertain/fail, không ghi nhầm thành công |
| AUD2-B01: Biến thể đồng thời | CT-AI-008, CT-ORC-012/008, CT-STATE-007; ADR-0004 | TST-WF-VAR-001..004; giữ chỗ và validation output có CAS |
| AUD2-M01: Kết thúc retry | CT-SRC-005, CT-STATE-002 | TST-COL-END-001..004; terminal/reconcile/unknown |
| AUD2-M02: READY registration race | CT-SRC-003A, CT-STATE-002A, SourceCandidateResolved | TST-SRC-RACE-001..004; receipt/source/candidate/outbox nhất quán |
| AUD2-M03: Package boundary | CT-SRC-006, CT-STATE-003, VALIDATION_ERROR | TST-COL-PKG-001..004; sai schema khác thiếu nội dung |

## 3. Bất biến xuyên phân hệ cần contract test

| ID | Bất biến | Producer | Consumer kiểm tra |
|---|---|---|---|
| INV-001 | Một command lặp không tạo hai aggregate logic | Mọi module | API/G |
| INV-002 | Event lặp không tạo side effect lặp | Producer outbox | Mọi consumer |
| INV-003 | Result generation cũ không được commit | Worker | G/owner output |
| INV-004 | Job đã snapshot không đổi nguồn/config | D/J | G/D |
| INV-005 | Bài trùng không tạo article/script mới | B | D/G |
| INV-006 | Timeline narrative cần EventUpdateAccepted | B | D |
| INV-007 | Word timing khớp script và voice hash | E | F |
| INV-008 | Render package chỉ chứa artifact đã verify | I/D/E | F |
| INV-009 | QC pass chưa đủ cho completion nếu cloud chưa verify | F/I | G |
| INV-010 | Completion tăng target đúng một lần | G | H/reporting |
| INV-011 | Cleanup cần ledger, verify, lease check và đúng epoch | G/I | I |
| INV-012 | Secret không xuất hiện trong event/log/history | J | Toàn hệ thống |
| INV-013 | Trong cùng lượt, 1-3 video khác góc kể | D | G |
| INV-014 | Giữa lượt, biến thể khác ít nhất một yếu tố thực tế | D | G |
| INV-015 | Source tombstone không bị auto-add | A | A/G/H |
| INV-016 | Message/grant/result/event từ recovery epoch cũ không được mutation | G/J/producer | Mọi owner/consumer |
| INV-017 | Completion ledger và `MediaUsage` của C cùng commit/rollback | G phối hợp C | G/C |
| INV-018 | Completed count cộng active capacity reservations không vượt batch target | G | G/H |
| INV-019 | Output hoàn thành có bằng chứng tiếng Anh gắn đúng script/voice/subtitle/metadata revisions | D/E/F | F/G |
| INV-020 | Dữ liệu nguồn không tin cậy không được đổi policy, gọi tool hoặc tạo ref chưa kiểm tra | A/C/D/J | D/J/resolver |

## 4. Failure matrix tối thiểu

| Tình huống | Trạng thái | Hành động hợp lệ |
|---|---|---|
| Desktop offline trước stage local | Waiting capability | Chờ heartbeat/capability rồi resume |
| Worker mất kết nối đang chạy | Running → outcome unknown hoặc retryable theo side effect | Reconcile receipt/lease trước retry |
| AI provider rate limit | Waiting/quota | Backoff hoặc route fallback đã cho phép |
| Upload timeout | Outcome unknown | Tìm object/hash rồi commit hoặc retry |
| Local file hash mismatch | Corrupt | Tải lại từ location cloud đã verify |
| Render thành công, QC fail | Stage failed/retryable theo lỗi | Retry/regenerate đúng semantics; không completion |
| QC pass, cloud sync fail | Ready for completion/waiting | Retry sync; không tăng target |
| Result từ worker cũ | Stale | Bỏ kết quả, giữ audit |
| Result/event từ recovery epoch cũ | Stale/quarantine | Không mutation; reconcile rồi cấp quyền/phát hành dưới epoch mới nếu cần |
| Crash trong completion/usage | Chưa commit hoặc đã commit toàn bộ | Cùng rollback hoặc trả receipt của ledger và `MediaUsage` C |
| Hai allocator tranh suất cuối | Một reservation thắng | Bên còn lại nhận target reached/retry allocation; không tạo job thừa |
| Config đổi khi batch chạy | Hai revision cùng tồn tại | Job chưa snapshot dùng mới; job đã snapshot giữ cũ |
| Nguồn bị remove | Source tombstone | Dừng thu thập; giữ dữ liệu cũ |

## 5. Điểm chưa quyết định nhưng không chặn hợp đồng

Các mục dưới đây là **CẤU HÌNH/THỬ NGHIỆM**, không cần user trả lời trước khi hoàn tất thiết kế hợp đồng:

1. Giờ và múi giờ chạy lượt thu thập hằng ngày.
2. Ngưỡng tin mới không trùng cho từng chủ đề.
3. Timeout, heartbeat, retry count và backoff cho từng activity/provider.
4. Page size, event/SSE retention và log retention.
5. Ngưỡng safety confidence, audio quality và visual continuity.
6. Codec, resolution, bitrate và output profile chi tiết.
7. Retention duration và tỷ lệ phân bổ 20 TB theo loại dữ liệu.
8. Provider/model/local AI cụ thể theo từng vai trò tại thời điểm triển khai.
9. Tên, phong cách và thông số chi tiết của 5 preset.
10. Ngưỡng “liên kết sự kiện đủ chắc” và “tình tiết mới” sau đo chất lượng.

Mỗi giá trị phải có default được ghi rõ, revision, phạm vi áp dụng và cách rollback trước khi code phụ thuộc vào nó.

## 6. Quyết định có điều kiện cần gate

| Gate | Điều cần chứng minh | Ảnh hưởng hợp đồng nếu không đạt |
|---|---|---|
| G01 Temporal | Crash/retry/replay, versioning, worker offline và operation receipt | Thay workflow adapter; giữ nguyên state/grant/receipt contract |
| G02 Throughput | Tối thiểu 100 video/12 giờ, auto success 95% | Điều chỉnh capacity/concurrency/preset; không hạ completion invariant |
| G03 Chi phí | Incremental cost dưới 50 USD/tháng | Đổi placement/provider/routing; giữ cost record contract |
| G04 Drive/OAuth | Account, quota, integrity, rate limit và bảo mật | Thay storage adapter/backend; giữ ArtifactRef/location/verify contract |
| G05 Restore | Khôi phục DB/workflow/catalog/output/journal | Điều chỉnh backup/recovery; giữ recovery epoch contract |
| G06 AI/content | Script, biến thể, disclosure, media selection đạt chất lượng | Đổi model/prompt/validator; giữ typed outputs/provenance |
| G07 Compatibility/UI/QC | Máy 1080p+, Vietnamese UI, codec/subtitle/timing | Điều chỉnh UI/render adapter; giữ API/QC semantics |

## 7. Các giả định đang được quản lý

- **GIẢ ĐỊNH AS-CTR-001:** Adapter workflow có thể ánh xạ đầy đủ `ExecutionGrant`, `OperationReceipt`, waiting và replay semantics; phải được chứng minh ở G01.
- **GIẢ ĐỊNH AS-CTR-002:** Google Drive có thể cung cấp hoặc hỗ trợ xây dựng bằng chứng integrity đủ để xác minh đúng byte; phải được chứng minh ở G04.
- **GIẢ ĐỊNH AS-CTR-003:** Desktop có thể giữ working set cho 5 video và vẫn đạt throughput; phải được đo ở G02/G07.
- **GIẢ ĐỊNH AS-CTR-004:** Có thể tạo word timing đủ chính xác cho karaoke trên 100 video/12 giờ trong giới hạn tài nguyên; phải được đo ở G02/G07.

Các giả định này chưa trở thành cam kết công nghệ hoặc chất lượng cho tới khi gate tương ứng đạt.

## 8. Kiểm toán logic

### Đã giải quyết

- Không còn ghi chồng owner giữa G và workflow engine: G sở hữu business state; workflow engine giữ execution state.
- Không còn nhầm Drive path với artifact identity.
- Không còn nhầm render success, QC pass, upload success và video completion.
- Không còn retry mù khi outcome của side effect chưa biết.
- Không còn dùng event delivery exactly-once giả tạo.
- Không còn xem bài repost là update hoặc video candidate mới.
- Không còn áp safety image lên clip trái quyết định user.
- Không còn endpoint sửa nội dung ngoài phạm vi UI đã chốt.
- Thumbnail và folder naming đã đồng bộ với requirement gốc.
- Recovery epoch đã đi qua grant/result/event và được kiểm tra độc lập generation.
- Completion/MediaUsage và batch capacity đã có một bất biến giao dịch rõ.
- SourceCandidate, package tối thiểu, multi-topic count và CollectionAttempt đã có contract.
- Gate tiếng Anh, ảnh vũ khí và indirect prompt injection đã có đường kiểm thử.

### Chưa có mâu thuẫn cần user quyết định ngay

Các điểm còn mở đều có thể được quyết định bằng nghiên cứu, benchmark, policy revision hoặc gate trước khi triển khai. Không có điểm nào buộc phải đoán để định nghĩa biên trách nhiệm hiện tại.

## 9. Điều kiện chuyển sang thiết kế kiểm thử

Chiến lược đáp ứng bước này được ghi tại [10-test-strategy.md](../10-test-strategy.md). Các điều kiện dưới đây trở thành đầu vào bắt buộc của test catalog triển khai:

1. Tạo test catalog cho mọi `Acceptance contract` và `INV-*`.
2. Tạo schema registry kế hoạch cho command/event/result, chưa cần sinh code.
3. Chốt owner và consumer cho từng event được dùng thật; loại event không có consumer.
4. Chốt default policy ban đầu và đánh dấu rõ giá trị cần benchmark.
5. Thiết kế failure-injection cho crash, duplicate, reorder, stale worker, offline desktop và upload outcome unknown.
6. Thiết kế security tests cho auth, workspace isolation, SSRF, secret redaction và path confinement.
