# 10. Hợp đồng lưu trữ và vòng đời artifact

> Trạng thái: **Bản thiết kế trước triển khai**  
> Chủ sở hữu: I.  
> Backend cloud mục tiêu hiện tại: Google Drive, còn phụ thuộc gate kiến trúc G04/G05.

## 1. Phân biệt ba khái niệm

- `Artifact`: đối tượng logic như ảnh gốc, rendition, voice hoặc video đầu ra.
- `ArtifactVersion`: byte stream bất biến, có hash và lineage.
- `ArtifactLocation`: một bản sao vật lý của version trên cloud/local staging/cache.

Phân hệ khác tham chiếu `ArtifactVersion`, không lấy filename hoặc Drive path làm identity.

## 2. Khai báo artifact

### CT-STO-001 — `DeclareArtifactVersion`

Input:

- artifact kind và owner resource ref;
- content hash, size, media type;
- lineage/input refs;
- retention class;
- sensitivity/risk classification;
- intended storage class;
- producer operation/grant.

Output:

- artifact ID/version ID;
- existing matching version hoặc version mới;
- required upload/materialization operation;
- policy decision.

Cùng byte và cùng identity policy có thể quy về version hiện có. Byte khác luôn là version mới, không ghi đè.

## 3. Đăng ký location

### CT-STO-002 — `RegisterArtifactLocation`

Location gồm:

- backend/account/bucket-or-drive namespace refs;
- provider object ID;
- logical path/category;
- device ID nếu local;
- observed hash/size;
- state và last verified time;
- lease/retention/cleanup state;
- provider metadata revision.

Không đưa raw credential vào location. Provider locator chỉ được adapter I diễn giải.

## 4. Tải lên và xác minh cloud

### CT-STO-003 — `PersistArtifactToCloud`

Input:

- artifact version;
- verified source location;
- target storage policy/account route;
- operation key;
- execution grant.

Quy tắc:

1. Chuẩn bị operation receipt trước upload.
2. Cùng operation/cùng byte retry không tạo hai artifact logic.
3. Timeout sau upload chuyển `OUTCOME_UNKNOWN`, sau đó tìm/reconcile bằng provider object ID, app property hoặc hash metadata phù hợp.
4. Upload response chưa đủ; phải verify object tồn tại, size/hash hoặc bằng chứng integrity tương đương.
5. Chỉ sau verify mới phát `ArtifactLocationVerified`.

Google Drive có thể không cung cấp cùng một loại checksum cho mọi loại tệp; phương pháp verify cụ thể là **CONDITIONAL theo G04** nhưng phải đạt invariant nhận diện đúng byte.

## 5. Materialize lên desktop

### CT-STO-004 — `MaterializeArtifactSet`

Input:

- manifest artifact versions cho job;
- target device/staging lease;
- expected total bytes;
- priority/deadline;
- operation key.

Output:

- local location refs;
- verified hash/size cho từng version;
- missing/corrupt items;
- bytes/time metrics;
- lease expiry.

Bất biến:

- Chỉ tải gần lượt xử lý.
- Giới hạn working set mặc định theo policy là tài nguyên cho tối đa 5 video/lần render.
- Có thể prefetch video tiếp theo trong khi render nếu không vượt disk/I/O policy.
- Render chỉ nhận location đã verify.
- Không dùng path ngoài staging root được I cấp.

## 6. Local journal

### CT-STO-005 — `LocalJournalEntry`

SQLite local journal/cache ghi:

- device/session/job/stage refs;
- artifact version và local location;
- materialization/processing/upload operation key;
- generation/lease;
- trạng thái, checkpoint và hash;
- last heartbeat/observed time;
- cleanup eligibility;
- recovery epoch.

Journal hỗ trợ phục hồi sau crash; PostgreSQL/cloud state vẫn là nguồn sự thật nghiệp vụ. Journal không tự phát `VideoCompleted`.

## 7. Đồng bộ video đầu ra

### CT-STO-006 — `PersistVideoOutput`

Video đầu ra có storage class bền vững và luôn được đồng bộ lên cloud. Kết quả phải có:

- output artifact/version/hash;
- cloud location verification;
- output metadata/filename refs;
- upload receipt;
- provider account/namespace ref;
- verified time.

G chỉ commit completion sau kết quả này.

## 8. Cleanup

### CT-STO-007 — `RequestCleanupEvaluation`

Input:

- local artifact/location refs;
- completion ledger hoặc superseded-stage refs;
- retention policy;
- active lease/consumer checks;
- recovery epoch.

Output:

- `eligible`, `deferred`, `forbidden`;
- reason codes;
- earliest cleanup time;
- cleanup authorization candidate.

### CT-STO-008 — `CleanupAuthorization`

Authorization bất biến gồm:

- exact location và artifact version/hash;
- reason và policy revision;
- completion/verification evidence;
- issued/expiry time;
- recovery epoch;
- authorizing owner.

I chỉ xóa khi:

1. artifact thuộc staging/cache được phép xóa;
2. không có lease/consumer đang hoạt động;
3. output/reusable artifact cần giữ đã verify trên cloud;
4. authorization còn hiệu lực và cùng recovery epoch;
5. resolved absolute path nằm trong staging root dự kiến.

Sau xóa, I ghi kết quả và phát `CleanupCompleted`. Lỗi xóa không đảo ngược completion ledger.

## 9. Recovery và epoch

### CT-STO-009 — `RecoveryEpoch`

Mỗi lần restore/rebuild control state tạo recovery epoch opaque mới và commit nó trước khi mở writer/dispatcher. Command/result/event/cleanup authorization từ epoch cũ không được mutation trong epoch mới. Dữ liệu an toàn cần áp dụng lại phải qua reconcile và được cấp grant hoặc phát hành dưới epoch mới; generation/revision trùng không thay thế kiểm tra epoch.

Reconciliation kiểm tra:

- DB record ↔ cloud object;
- expected hash/size ↔ observed byte;
- local journal ↔ workflow/stage generation;
- completed ledger ↔ durable output;
- orphan upload/temp file;
- duplicate provider object.

## 10. Phân bổ cloud và retention

### CT-STO-010 — `StoragePlacementPolicy`

Kho Google Drive 4 tài khoản, tổng dung lượng danh nghĩa do user cung cấp là 20 TB, được phân vùng logic theo **loại dữ liệu**. Policy phải quyết định:

- loại artifact nào vào namespace/account nào;
- ngưỡng quota và reserve;
- fallback account;
- original, reusable, temporary và output retention;
- metadata catalog không phụ thuộc duy nhất vào cấu trúc folder Drive.

Chi tiết tỷ lệ phân bổ và retention duration là **CẤU HÌNH** sau đo thực tế. Không giả định bốn tài khoản có quota/API project độc lập.

## 11. Tên file và folder

### CT-STO-011 — `AllocateOutputPath`

Input:

- app session;
- completion candidate;
- display caption/title và 3-4 hashtag;
- date/naming policy;
- target root.

Output:

- sanitized filename;
- logical output folder;
- collision sequence;
- display metadata nguyên gốc.

Quy tắc:

- Folder của phiên đầu tiên có video hoàn thành trong ngày: `YY-MM-DD`.
- Các phiên hợp lệ tiếp theo trong cùng ngày: `YY-MM-DD (1)`, `YY-MM-DD (2)`...; không tạo folder sản phẩm hợp lệ cho session không có video hoàn thành.
- Không tạo folder hợp lệ liên tục cho session không có video hoàn thành; staging ẩn/tạm không được trình bày là output folder.
- Ký tự cấm, tên reserved và độ dài filesystem được sanitize deterministic.
- Dấu `#` được giữ khi backend/filesystem mục tiêu hỗ trợ; nếu không, mapping được ghi trong metadata.

## 12. Acceptance contract

1. Upload timeout không tạo duplicate logic hoặc xóa local trước reconcile.
2. Render không dùng artifact local chưa verify hash.
3. Desktop restart phục hồi đúng job/stage từ journal và cloud control state.
4. Chỉ giữ working set gần tối đa 5 video theo policy.
5. Hoàn thành video đồng nghĩa có output cloud đã verify.
6. Cleanup chỉ thực hiện với authorization đúng artifact, path và recovery epoch.
7. Original/reusable rendition/output không bị xóa như tệp trung gian per-video.
