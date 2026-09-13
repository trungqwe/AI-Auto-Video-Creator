# ADR-0004: Commit nghiệp vụ, idempotency và fencing

**Trạng thái:** Accepted - bất biến thiết kế; chưa có failure test  
**Căn cứ:** R10/R17, DR-009/014/020, QR-REL-004/005/008; ARCH-010.  
**Liên quan:** [ADR-0003](./0003-durable-workflow-engine.md), [ADR-0006](./0006-drive-artifacts-and-local-journal.md).

## Tại sao phải quyết định

Một operation có thể chạy lại sau timeout dù side effect đã xảy ra. Worker cũ còn chạy sau khi worker mới nhận việc. PostgreSQL, Temporal và Drive không cùng một transaction. Nếu không có ranh giới commit, hệ thống có thể mất tiến độ, xóa sớm hoặc đếm hai video từ một job.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Tin ACK từ worker/workflow | Ít cơ chế | ACK và DB commit có thể lệch; worker cũ vẫn ghi |
| Idempotency key đơn thuần | Chống request lặp cùng key | Không chống kết quả đến muộn của generation khác |
| Transaction + outbox + receipt + fencing | Chốt một kết quả hợp lệ và khôi phục lost ACK | Thêm trạng thái/constraint/reconciliation |

## Chọn cái gì và tại sao

Chọn phương án ba. PostgreSQL giữ business result; Temporal giữ tiến độ thực thi. Module owner xác thực command/result; không để UI hoặc worker tự gán `COMPLETED`.

1. Lệnh được ghi cùng outbox trong transaction. Dispatcher start/signal bằng ID ổn định; command nhận lại trả receipt, không nhân đôi workflow.
2. G cấp quyền thực thi với operation ID, input revision, device, generation và recovery epoch. Khi thay quyền, tăng generation; sau restore tạo epoch opaque mới trước khi mở writer. Commit từ generation hoặc epoch cũ bị từ chối.
3. Artifact theo attempt bất biến. Worker commit stage result + outbox, nhận durable receipt rồi mới báo activity thành công. Lost ACK tra lại receipt trước khi làm lại.
4. G giữ suất batch/biến thể đang chạy bằng transaction. Chỉ giải phóng khi có kết quả trạng thái rõ; job chờ không tự mất suất hoặc bị gọi là cạn dữ liệu.
5. Completion unit of work gắn QC F/D, sync receipt I, checksum của cùng output, content/variant refs, completion ledger duy nhất, capacity reservation và một lần tăng bộ đếm lô. G gọi application port của C để C ghi `MediaUsage` trong cùng transaction; G không ghi chéo bảng C.
6. Cleanup chỉ chạy từ commit hợp lệ và khi tệp không còn reference active. Cleanup lỗi không hạ trạng thái video hoặc bắt render lại.

Làm rõ hậu kiểm AUD2-B01: suất batch là BatchCapacityReservation; nội dung đang chạy là VariantReservation (G). CT-ORC-012 dùng revision registry theo workspace để D đối chiếu ngoài transaction rồi G compare-and-swap khi reserve/complete. Bằng chứng cuối phải gắn output hash; registry đổi thì đối chiếu lại. Completion chuyển cả hai reservation và ghi C/G cùng UoW; terminal lỗi release, WAITING không release tự động. Không dùng unique job ledger để thay kiểm tra biến thể giữa các job.

Đánh đổi: thay đổi ở workspace khác nội dung vẫn có thể làm validation stale, cần đối chiếu lại. Chấp nhận khóa metadata ngắn trong baseline một người dùng; không giữ khóa qua AI. Sau này chia scope khóa phải kiểm chứng article/event chồng lấn và các race trước khi thay, không tự bỏ ràng buộc.

Đích byte không cùng transaction DB: dùng file ID ổn định, artifact bất biến và đối chiếu. Không sửa trực tiếp database Temporal để cố đồng bộ hai kho trạng thái.

## Điểm bất lợi

Fencing chỉ có hiệu lực tại nơi kiểm tra token; external provider không hỗ trợ token đó. Vì vậy không cho overwrite một file chuẩn có thể đang thuộc attempt khác. AI call mất phản hồi có thể bị tính tiền nhiều lần dù chỉ một result được chấp nhận; không cam kết exactly-once bên ngoài.

Progress/SSE có thể đến muộn hoặc sai thứ tự; không được làm trạng thái đã commit lùi lại. Kết quả stale giữ để audit/quarantine, không âm thầm xóa bằng chứng.

## Kiểm chứng

G01: crash trước/sau mỗi commit, lost ACK, hai completion đồng thời ở suất cuối, worker cũ về muộn, outbox gửi lặp, duplicate Drive result. Đối chiếu ledger và byte thực, không chỉ đếm số workflow xanh.

TST-WF-VAR-001..004 kiểm tra hai lô cùng biến thể, validation cũ, retry/lost ACK và hai biến thể khác hợp lệ; không coi capacity test là đã kiểm chứng content reservation.

## Sau này đổi thì thế nào

Có thể thay workflow engine/transport nhưng phải giữ operation identity và receipt. Thay schema ledger cần migration có version và đối chiếu tổng theo batch. Không reset key/generation khi retry, restart hoặc đổi process. Chi phí thay semantics cao vì liên quan mọi side effect.
