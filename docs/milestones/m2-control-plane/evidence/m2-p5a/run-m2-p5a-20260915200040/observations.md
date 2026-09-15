# Quan sát và giới hạn provenance

## Correction trước implementation

Test-only checkpoint thay wiring sang PostgreSQL repository/event-sink được inject. So sánh AST trước/sau bằng phép chuẩn hóa duy nhất ba tên factory và loại import/helper mới xác nhận toàn bộ phần còn lại giống nhau, gồm năm oracle và mọi assertion/expected value.

Correction RED xảy ra sau test-only commit tại preserved worktree chứa persistence/migration corrections chưa commit. Không có immutable production RED commit cho trạng thái này. `correction-provenance.json` ghi timestamp JUnit, command, original stdout SHA, exit code 1 và mô tả trạng thái; không gán `source_commit_sha` mới cho execution cũ. Snapshot application RED được tái dựng bằng đảo đúng ba minimal fixes đã ghi, không tuyên bố hash này đã được đo trực tiếp khi RED chạy. Stdout được chuyển encoding sang UTF-8/LF; JUnit giữ nguyên nội dung/kết quả và được chuẩn hóa newline sang LF. Chỉ output của run mới được chuẩn hóa CRLF/trailing whitespace để qua staged whitespace check; không đổi oracle hoặc historical evidence. Bản capture gốc còn dưới ignored `.local-tools/temp/`.

Stale probe chứng minh DB đã ở revision 2, nhưng code trả current_revision=1 khi object caller cũ và expected_revision=0. Hai explicit-ID probe thất bại tại duplicate-keyword TypeError trước persistence. Sau sửa, cùng harness đạt 3/3, ID được giữ nguyên cả kết quả lẫn DB; stale path không đổi full revision snapshot hoặc outbox count.

Lần fix đầu bỏ cả check graph của caller làm oracle forbidden-transition thất bại. Nhánh graph đã được giữ nguyên, chỉ bỏ check revision từ caller; không đổi assertion hay contract để GREEN. Full pre-source chạy lại từ đầu PASS trước commit production.

## Closure trên immutable source

Tất cả JUnit/stdout P5A/P4/P3/P2/P1/P0/architecture/M1 tại run này được tạo bởi execution mới sau source checkpoint. Không copy PASS report P0/M1 từ evidence lịch sử. `source-manifest.json` pin toàn bộ tracked source/tests và dependency manifest/lock đã dùng; profile đối chiếu với immutable Git blobs và worktree hiện tại.

M1 dùng đúng PostgreSQL endpoint 127.0.0.1:55432/aiavc_m1 và exact Temporal Server 1.31.2. OAuth được người dùng cấp quyền lại; vault cũ giữ nguyên dưới user profile, default vault mới DPAPI. Evidence không chứa token, client secret, OAuth code hoặc credential JSON. Fresh E3 thực hiện API upload/download/hash/cleanup thật; accepted historical Drive artifact được khôi phục đúng SHA sau mỗi live regression.

`commands.jsonl` phân biệt fresh immutable-source execution với export supplementary RED. `results.json`/`status.json` giữ đủ identity và count; verifier đọc actual testcase và không tin self-reported PASS. Lint/type/build không được tuyên bố PASS khi tool không có. Đây là candidate review checkpoint, không phải acceptance hoặc quyền mở work package tiếp theo.
