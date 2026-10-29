# CP7-3 — Drive, OAuth và toàn vẹn trên tài khoản thật (RG-02)

Ngày đo: 29/10/2026, trên lane `lane-cp7-3`, bằng interpreter khoá `.local-tools/runtime/1ca840a7/venv`, dưới quyền thường.

Lệnh: `python -m pytest tests/real/test_cp7_drive_real.py -q -p no:cacheprovider` bằng interpreter khoá `.local-tools/runtime/1ca840a7/venv`. Kết quả: 12 passed, mã thoát 0. Trần chi phí: 0 USD; 52.50 MiB lên Drive (trần 60 MiB); 56 lời gọi API (trần 200).

## Kết quả

RG-02.oauth_present: PASS
RG-02.scope_drive_file: PASS
RG-02.upload_md5: PASS
RG-02.resumable_chunks: PASS
RG-02.sha256_redownload: PASS
RG-02.conflict_409: PASS
RG-02.session_expired: PASS
RG-02.token_invalid: PASS
RG-02.quota_reserve: PASS
RG-02.token_outside_vault: PASS
RG-02.cleanup_namespace: PASS
RG-02.secret_scan: PASS

## Chi tiết đo

- oauth_present: alias OAuth Drive có trong kho DPAPI; chỉ kiểm tồn tại, không đọc giá trị.
- scope_drive_file: tokeninfo của access token do broker cấp có đúng một phạm vi `https://www.googleapis.com/auth/drive.file`.
- upload_md5: ba tệp ngẫu nhiên 1, 9 và 40 MiB tải bằng `DriveObjectStore` với broker thật vào `AI-Auto-Video-Creator/cp7-fixture/<runId>/`; `md5Checksum` của Drive bằng md5 cục bộ 3/3, kích thước khớp, cha đúng thư mục của lần chạy.
- resumable_chunks: chunk 8 MiB của hồ sơ production; tệp 9 MiB lên bằng 2 lần PUT, tệp 40 MiB bằng 5 lần PUT; mã trung gian 308 được xử lý như "Resume Incomplete".
- sha256_redownload: `DriveObjectStore.lookup` (bằng chứng `sha256Checksum`) và một lần tải lại thật tệp 9 MiB đều cho sha256 khớp sha256 cục bộ.
- conflict_409: upload lại với file ID đã cấp ném `ObjectAlreadyExistsError` (409); Drive giữ đúng một bản.
- session_expired: tệp 1 MiB, chunk 256 KiB; sau chunk đầu, `upload_id` của phiên được đổi thành giá trị không tồn tại; Drive trả 404 thật; store mở phiên mới (tổng 2 phiên), hoàn tất, md5 khớp. Mã đã thấy: 200, 308, 404.
- token_invalid: bearer cố định không hợp lệ trả HTTP 401 thật; `DriveObjectStore` ném `DriveCredentialError` với `code = DRIVE_CREDENTIAL_INVALID`; handler `PersistVideoOutput` thật (cùng `PersistArtifactToCloud` và `DriveObjectStore`) trả `waiting` với `problem.code = credential_unavailable`, `retryable = True`, `output_refs = []`; file ID đã cấp trước đó vẫn upload được bằng broker thật. Giới hạn trung thực: ở phép đo trên tài khoản thật, lớp PostgreSQL (receipt, bản ghi version) được thay bằng bộ nhớ; việc job chuyển `WAITING` với `wait_reason = credential_unavailable` rồi hoàn tất đúng một đối tượng được kiểm bằng `tests/integration/prod_wiring/test_pw_i2_persist_output.py` trên PostgreSQL thật.
- quota_reserve: `storageQuota` thật của tài khoản; phần trống dự phóng sau tệp 1 MiB lớn hơn ngưỡng 0,2 của hồ sơ, nên các upload thật ở trên qua được chốt. Đặt `quota_reserve_ratio` ngay trên phần trống dự phóng thật thì store ném `DriveQuotaError` trước khi tạo tệp; `files.get` của file ID đã cấp trả 404.
- token_outside_vault: access token và refresh token (lấy qua broker, chỉ trong bộ nhớ của test) xuất hiện 0 lần trong 420 tệp của thư mục dữ liệu (trừ `vault/`) và trong báo cáo này.
- cleanup_namespace: test chỉ xoá tệp có cha đúng `cp7-fixture/<runId>` và chính thư mục đó (cha phải là `cp7-fixture`); 5 mục được xoá; 167 tệp ứng dụng thấy được ở ngoài thư mục đó không đổi (so tập ID đã băm trước và sau).
- secret_scan: báo cáo này 0 lần khớp mẫu bí mật; dòng bằng chứng của test đi qua `scan_secrets`.

## Finding

- F-CP7-3-01 (ĐÃ ĐÓNG): trước đây activity `PersistVideoOutput` chưa được nối và lỗi 401 chưa có mã riêng khiến `token_invalid` bị BLOCKED. Hiện tại `DriveCredentialError` đã có mã `DRIVE_CREDENTIAL_INVALID` và handler `PersistVideoOutput` đã được nối trong `storage_activity_services`, trả `waiting` với `credential_unavailable` khi gặp lỗi 401 thật từ Drive; file ID đã cấp trước đó không mất và upload hoàn tất sau đó với broker thật.
- Đã sửa trong lúc làm slice (commit `53330a5`, kèm test hồi quy): `DriveObjectStore` và `DrivePlacementBootstrap` tự tạo `httplib2.Http`, nên 308 "Resume Incomplete" của Drive bị coi là chuyển hướng và mọi tệp lớn hơn một chunk hỏng với `RedirectMissingLocation`. Hai lớp giờ dùng chung `drive_http(timeout)`, loại 308 khỏi mã chuyển hướng như `googleapiclient.http.build_http`.

## Ghi chú

- Test không in token, refresh token hay file ID; file ID chỉ được giữ dưới dạng băm.
- Mọi tệp thử nằm trong thư mục tạm ngoài cây Git và bị xoá khi xong; trên Drive chỉ còn thư mục rỗng `cp7-fixture`.
- Chi tiết in ra terminal là ASCII vì stdout của harness dùng cp1252, chữ có dấu chỉ nằm trong báo cáo.
