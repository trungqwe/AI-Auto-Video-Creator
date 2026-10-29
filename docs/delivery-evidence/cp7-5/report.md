# CP7-5 — Thu thập RSS/web thật và khóa holdout (RG-04)

Ngày đo: 30/10/2026, trên lane lane-cp7-5, bằng interpreter khoá .local-tools/runtime/1ca840a7/venv, dưới quyền thường, qua Internet công khai.

Lệnh: python -m pytest tests/real/test_cp7_collection_real.py -q -p no:cacheprovider. Lượt 1 (khóa manifest): 11 passed, mã thoát 0. Lượt xác nhận (sau khi khóa manifest, kèm đối chiếu băm với report): 11 passed, mã thoát 0, manifest không đổi. Trần chi phí: 0 USD; 30 bài (trần 35); 30 ảnh (trần 35); 35.36 MiB (trần 200).

## Kết quả

RG-04.feeds_alive: PASS
RG-04.extraction_ratio: PASS
RG-04.ssrf_policy: PASS
RG-04.concurrency_limits: PASS
RG-04.source_404_isolated: PASS
RG-04.checkpoint_resume: PASS
RG-04.raw_hash: PASS
RG-04.cycle_time: PASS
RG-04.holdout_locked: PASS
RG-04.secret_scan: PASS

## Khóa holdout

holdout_manifest_sha256: c2e1fc1d8309d57d26ddcdf3bbd83c65b100a391d2659e4c6aba61e9f6aba314
- seed cp7-5-holdout-v1.
- quy tắc chọn: sort article ids; list all unordered id pairs in lexicographic order; random.Random(seed).sample(range(pair_total), 40); keep chosen indices ascending.
- 40 cặp chọn từ 30 bài của lượt 1.
- manifest chỉ có id và sha256 raw bytes.
- thời điểm khóa là lượt 1, trước mọi bước dùng bài làm đầu vào prompt (slice này không dùng bài làm prompt).

## Chi tiết đo

- feeds_alive: 7/7 nguồn tốt (≥ 6/7 feed trả 200 và parse ≥ 5 mục), 67 hop mạng HTTP 200; bbc-world (28 entries, 5 bài, 5 ảnh, 7.6 giây), bbc-tech (20 entries, 5 bài, 5 ảnh, 8.6 giây), npr-news (10 entries, 5 bài, 5 ảnh, 8.0 giây), guardian-world (45 entries, 5 bài, 5 ảnh, 5.4 giây), aljazeera-all (25 entries, 5 bài, 5 ảnh, 2.6 giây), nasa-news (10 entries, 5 bài, 5 ảnh, 9.5 giây), ars-technica (20 entries, 0 bài, 0 ảnh, 6.3 giây).
- extraction_ratio: 30 bài thu thập, 29 bài có văn bản ≥ 600 ký tự (đạt 96.7% ≥ ngưỡng 90%).
- ssrf_policy: 78 hop mạng thật, 0 hop redirect, 0 địa chỉ IP riêng tư; 3 probe control offline bị từ chối kết nối trước khi gửi (UNSAFE_REDIRECT).
- concurrency_limits: max_global = 4 (trần 4), max_host = 1 (trần 1), tổng số fetch = 78.
- source_404_isolated: 6 nguồn có bài commit đều nhận mã phản hồi 404 cho URL thử nghiệm cp7-not-found (HTTP_STATUS_REJECTED 404), các bài hợp lệ khác vẫn được commit đầy đủ mà không bị dừng tiến trình.
- checkpoint_resume: 6 nguồn dừng giữa lượt sau 2 bài, chạy tiếp thành công từ checkpoint; 0 bài trùng lặp; revision checkpoint tăng từ revision 1 lên revision 2 khớp số bài.
- raw_hash: 30 gói bài viết có sha256 khớp chuẩn với thân phản hồi thật của SecureFetcher; 67 body digest phân biệt; toàn bộ ảnh tải về khớp sha256.
- cycle_time: 17.1 giây, cơ sở MEASURED (< 30 phút).
- secret_scan: manifest và báo cáo 0 khớp mẫu bí mật; các dòng bằng chứng emit đều được quét sạch bí mật.

## Ngoài phạm vi v1

- Scheduler cloud khi desktop offline: OUT_OF_V1_SCOPE (OI-CP7-03); không ghi PASS, user ghi nhận ở R1.

## Giới hạn

- Byte thô của mẫu không lưu trong repo, chỉ có sha256; bước dùng bài làm prompt sau này phải lấy từ gói thu thập có sha256 trùng manifest.
- Control SSRF offline chỉ là đối chứng; bằng chứng chính là các hop thật.
- Không dòng nào bắt đầu bằng RG- ngoài 10 dòng ở mục Kết quả. Không chép mẫu khóa bí mật vào báo cáo.
