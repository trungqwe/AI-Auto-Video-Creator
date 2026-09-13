# Hồ sơ quyết định kiến trúc

**Ngày lập:** 12-09-2026  
**Thẩm quyền:** người dùng ủy quyền kiểm toán, điều chỉnh và tự quyết định kỹ thuật khi đủ căn cứ trước khi ghi ADR. Không ghi nhận thay cho người dùng một lần phê duyệt công nghệ/benchmark chưa xảy ra.  
**Căn cứ:** [Kiến trúc hiện hành](../08-architecture.md), [báo cáo kiểm toán](../08-architecture-audit.md), R01-R25 tại [luồng dữ liệu](../07-data-flow.md).

## Trạng thái

- `Accepted`: đã chọn làm baseline thiết kế theo ủy quyền. Không có nghĩa đã triển khai hoặc kiểm thử đạt.
- `Conditional`: đã chọn hướng ưu tiên nhưng chưa khóa tính khả thi; gate ghi trong hồ sơ phải đạt trước production của phần phụ thuộc.
- `Superseded`: được thay bởi ADR mới có liên kết hai chiều; giữ lịch sử quyết định cũ.
- Không có giả định chưa xác nhận nào được dùng làm yêu cầu chính thức. Dữ liệu chưa biết được ghi `CHƯA KIỂM CHỨNG`; ví dụ minh họa cần giả định phải ghi `GIẢ ĐỊNH`.

## Danh mục

| Hồ sơ | Quyết định | Trạng thái | Ánh xạ mã kiến trúc |
|---|---|---|---|
| [0001](./0001-hybrid-modular-monolith.md) | Hybrid, 10 module trong monorepo, cloud/desktop tách tiến trình | Accepted | ARCH-002/003/004 |
| [0002](./0002-authoritative-data-and-search.md) | PostgreSQL, provenance, chỉ mục có phiên bản | Accepted | ARCH-005/007 |
| [0003](./0003-durable-workflow-engine.md) | Temporal ưu tiên; cloud workflow worker, manual/auto và affinity | Conditional | ARCH-001/009 |
| [0004](./0004-commit-idempotency-and-fencing.md) | Commit nghiệp vụ, outbox, fencing, đếm hoàn thành một lần | Accepted | ARCH-010 |
| [0005](./0005-snapshots-and-content-invariants.md) | Snapshot, nguồn trùng/đã xóa, diễn biến và biến thể | Accepted | Bổ sung ARCH-005/010 |
| [0006](./0006-drive-artifacts-and-local-journal.md) | Drive artifact bất biến, kiểm chứng sync, journal local | Conditional | ARCH-008 |
| [0007](./0007-runtime-and-admin-ui.md) | Python/FastAPI, React/grid, FFmpeg và vai trò Sheets | Accepted | ARCH-006/011 |
| [0008](./0008-ai-routing-and-quota.md) | Adapter AI theo vai trò, quota chung và fallback có kiểm soát | Conditional | ARCH-012 |
| [0009](./0009-trust-boundaries-and-secrets.md) | Kết nối, danh tính thiết bị, OAuth và secret lifecycle | Accepted | ARCH-013 |
| [0010](./0010-storage-lifecycle-and-recovery.md) | Dọn tệp theo quyền sử dụng, backup nhất quán và restore cách ly | Conditional | ARCH-016 |
| [0011](./0011-observability-capacity-and-cost.md) | Quan sát, resource admission, ngân sách và chứng minh sản lượng | Conditional | ARCH-015, ARCH-GATE-002/003 |
| [0012](./0012-evolution-and-saas-boundary.md) | Chuẩn bị workspace, nâng version và điều kiện tách service | Accepted | ARCH-014, bổ sung ARCH-002/004 |

## Cổng kiểm chứng

Các gate này được thiết kế ngay; thử nghiệm cần mã chỉ chạy sau khi quy trình cho phép code. Trước đó có thể tiếp tục schema/contract/kiểm thử trên giấy, không được kết luận gate đã đạt.

Trạng thái gate dùng thống nhất:

- `NOT_TESTED`: chưa có proof runtime phù hợp;
- `PASS_M1_SCOPE`: phần proof được định nghĩa cho M1 đã đạt, không đại diện toàn gate;
- `PARTIALLY_PROVEN`: gate tổng thể đã có một hoặc nhiều proof hợp lệ nhưng chưa đủ lớp evidence để đóng;
- `PASS`: toàn bộ evidence bắt buộc của gate đã đạt ở lần đóng chính;
- `FAIL`/`BLOCKED_EXTERNAL`: proof hợp lệ thất bại hoặc không thể chạy vì phụ thuộc ngoài.

Hiện tại G01 Temporal và G04 Drive/OAuth đều `NOT_TESTED`. M1-P2/P3 nếu đạt chỉ có quyền tạo `PASS_M1_SCOPE`; G01/G04 tổng thể khi đó là `PARTIALLY_PROVEN`, không phải PASS.

| Gate | Chủ sở hữu | Bằng chứng cần có | Chặn điều gì nếu chưa đạt |
|---|---|---|---|
| G01 = ARCH-GATE-001 | G, phối hợp I/J | Crash/retry, offline desktop, worker cũ về muộn, child failure, replay/upgrade; không mất job/đếm trùng | Khóa Temporal làm engine production |
| G02 = ARCH-GATE-002 | F/G/E/I | 100 output hợp lệ đã sync/12 giờ trên máy mục tiêu; stage timing và tài nguyên; áp đủ hard gate QR, kiểm tra ít nhất 95% video đủ đầu vào hoàn thành tự động theo QR-REL-007 | Tuyên bố đạt sản lượng/độ ổn định và chốt concurrency/profile |
| G03 = ARCH-GATE-003 | G/J/I | Workload tháng + báo giá/hóa đơn/thực đo; tổng phần phát sinh dưới 50 USD, kể cả egress/backup/retry | Khóa cấu hình host và phương án chi phí |
| G04 | J/I/H | Quyền/quota thật, Drive ID/hash/upload gián đoạn, token refresh khi desktop tắt, thu hồi credential, local HTTPS/Origin và Temporal authorization | Vận hành không giám sát, xóa bản local duy nhất, đưa tài khoản vào pool |
| G05 | I/G/J | Backup cluster có WAL, manifest/build/key phục hồi; restore cách ly và reconcile Drive/journal; không replay side effect mù | Tuyên bố backup có thể phục hồi; bật writer/cleanup sau restore |
| G06 | D/E/B/C | Bộ mẫu chủ đề 90%, event link 95%, media/hook 90%, nhận diện ảnh 95% theo tài liệu 03; TTS/word timing/biến thể/gắn nhãn suy luận | Chốt model, threshold và tuyên bố chất lượng nội dung |
| G07 | H/F/J/G | Profile đầu ra, preset, pin runtime/SDK/server/DB/extension và license build; UI p95 2 giây, ACK 1 giây, resume 5 phút, lịch 99% theo định nghĩa phép đo được chốt | Phát hành baseline tương thích và nhận đạt các QR tương ứng |

G06/G07 giữ nguyên ngưỡng đã duyệt; không thêm một ngưỡng timing karaoke khi người dùng chưa duyệt. Việc quan sát một mẫu đạt không đại diện toàn bộ gate.

## Quy tắc cập nhật

Mỗi ADR ghi quyết định, bối cảnh, lựa chọn thay thế, lý do, điểm bất lợi, kiểm chứng và cách thay đổi. Sửa lỗi diễn đạt được ghi lịch sử trong chính hồ sơ; đổi quyết định tạo ADR kế tiếp và đánh dấu hồ sơ cũ `Superseded`. Không dùng việc tạo đủ file làm bằng chứng kiến trúc đúng.

Các tài liệu 00-07 giữ các yêu cầu và lịch sử giai đoạn; quyết định kỹ thuật mới được tra ở 08/ADR. Không được dùng ADR để hạ ngưỡng chất lượng hoặc thay đổi nghiệp vụ mà người dùng đã xác nhận.
