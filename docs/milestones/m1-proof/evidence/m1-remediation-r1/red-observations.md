# RED observations

Các RED dưới đây được chứng kiến trong phiên khắc phục ngày 13-09-2026 trước implementation tương ứng. Không dựng lại timestamp hoặc stdout đã không được lưu ngay lúc chạy.

- B01: race có barrier trả hai `CommandReceipt`; oracle yêu cầu một accepted và một `REVISION_CONFLICT`.
- B02: authority API/epoch propagation chưa tồn tại; stale command/event/fence chưa có đường kiểm tra xuyên suốt.
- B03: event và activity payload chứa key nhạy cảm không phát sinh `SensitiveDataRejected`.
- M01: capture API chưa nhận live project/DSN và không có live probe.
- M02: cùng operation key ở hai workspace trả cùng receipt; transition API chưa có scope/guard mới.
- M03: activity grant/result chưa có operation key và input fingerprint.
- M05: completion admission owner module chưa tồn tại.

Phân loại trung thực: B01 và B03 là RED hành vi trực tiếp. Các case còn lại bắt đầu bằng thiếu contract/API của remediation; chúng chứng minh capability chưa có nhưng không được dùng riêng để tuyên bố correctness. Kết luận đóng issue dựa trên negative/positive acceptance tests mới, process restart thật, migration proof và full regression.
