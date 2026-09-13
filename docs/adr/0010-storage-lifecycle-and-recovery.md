# ADR-0010: Vòng đời tệp và phục hồi nhất quán

**Trạng thái:** Conditional - lifecycle là baseline; backup/restore chưa qua G03/G05  
**Căn cứ:** R13/R18, DR-009/010/011, QR-AVL-005, QR-REL-005; ARCH-016.  
**Liên quan:** [ADR-0004](./0004-commit-idempotency-and-fencing.md), [ADR-0006](./0006-drive-artifacts-and-local-journal.md).

## Tại sao phải quyết định

Một tệp có thể phục vụ nhiều job; năm bộ tài nguyên vẫn có thể chiếm nhiều dung lượng. Backup app và workflow không cùng thời điểm có thể làm hồi sinh job cũ hoặc mất completion. Cloud provider còn giữ side effect xảy ra sau snapshot database.

## Các lựa chọn

| Lựa chọn | Lợi ích | Bất lợi |
|---|---|---|
| Không backup | Ít chi phí, phù hợp chấp nhận mất toàn kho | Mất metadata làm khó khai thác media còn trên Drive |
| Logical dump riêng từng DB mỗi ngày | Dễ xuất/đọc/migration | Không có snapshot chung giữa app/Temporal/visibility |
| Physical cluster backup + WAL và restore có reconcile | Bảo toàn điểm DB chung; có quy trình đối chiếu bên ngoài | Tăng volume, phụ thuộc version, phải giữ key và thử restore |
| Replication/HA đa host | Giảm gián đoạn | Vượt nhu cầu/công sức ban đầu; replication không thay backup |

## Chọn cái gì và tại sao

Chọn lifecycle theo manifest/ref và phương án backup thứ ba có điều kiện. PostgreSQL xác nhận dump nhiều database không đồng bộ; physical base backup phục vụ sao lưu cluster. [SQL dump](https://www.postgresql.org/docs/current/backup-dump.html), [pg_basebackup](https://www.postgresql.org/docs/current/app-pgbasebackup.html).

I chỉ dọn input/intermediate khi completion đã commit, không còn reference active và không còn cần reconcile. Voice/subtitle có thể dọn theo R13; script/source/signature/receipt giữ để truy vết, không hứa tái dựng đúng byte khi voice cũ đã dọn. Không xóa output chưa sync vì low-disk.

Backup baseline thử nghiệm một bản cluster/ngày, có WAL đủ để phục hồi bản đó, manifest version và mã hóa; giữ 7 bản ngày/4 bản tuần khi G03 cho phép. Không cam kết PITR liên tục giữa các backup hoặc SLA RPO/RTO mới. Logical dump có thể dùng hỗ trợ migration, không thay backup chung.

Host supervisor/lịch backup phải chạy ngoài Temporal. Secret bundle backup mã hóa riêng; key phục hồi có bản giữ ngoài host và ngoài bundle. Backup cùng các account Drive không bảo vệ khỏi mất toàn bộ account; giữ đúng chấp nhận rủi ro QR-AVL-005.

Restore vào môi trường cách ly, không cho worker/dispatcher/cleanup/provider calls tự chạy. Tạo recovery epoch opaque mới và commit trước khi mở writer, thu hồi lease/grant cũ; đối chiếu Drive file ID/hash, journal desktop và operation/completion ledger. Grant/result/event từ epoch cũ bị từ chối dù generation trùng; dữ liệu cần áp dụng lại phải qua reconcile và được phát hành dưới epoch mới. Chỉ mở writer sau khi các trạng thái chưa rõ đã được cách ly hoặc reconcile. Backup nhất quán DB không có nghĩa side effect bên ngoài đã cùng snapshot.

## Điểm bất lợi

Backup physical phụ thuộc major version/platform/extensions; giữ được build manifest là điều kiện phục hồi. Dung lượng retention có thể không phù hợp ngân sách, phải đo trước khi khóa. Restore có thể tốn thời gian và cần người vận hành, không phải hệ HA tự chữa.

## Kiểm chứng

G05: checksum backup, thiếu WAL/key, restore app/Temporal, output Drive mới hơn backup, worker cũ reconnect và cleanup sau restore. Không có restore drill thì nhãn là “backup chưa kiểm chứng”, không “đã bảo đảm phục hồi”.

## Sau này đổi thì thế nào

Đổi retention là policy có lịch sử; không xóa bản backup tốt duy nhất trong lúc migration. Chuyển sang managed backup/PITR phải thử cùng kịch bản external reconciliation. Khi tách các DB sang cluster khác, phải thiết kế checkpoint/restore coordination mới; ADR hiện tại không còn đủ.
