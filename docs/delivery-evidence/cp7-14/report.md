# CP7-14 — Mẫu 20 video và gói bằng chứng nghiệm thu R1–R6 (RG-13)

## Kết quả

RG-13.sample_10_valid: FAIL
RG-13.cloud_verified_10: FAIL
RG-13.trace_per_video: PASS
RG-13.story_angle_distinct: PASS
RG-13.rights_unverified_excluded: FAIL
RG-13.holdout_sheet_40: PASS
RG-13.video_sheet_10: FAIL
RG-13.pack_r1_r6_complete: PASS
RG-13.no_user_field_filled: PASS
RG-13.secret_scan: PASS

- sample_10_valid: valid=16/16
- cloud_verified_10: cloud_ok=16/16 drive_matches=16/16
- trace_per_video: missing=0
- story_angle_distinct: groups=9 multi=7 dups=0
- rights_unverified_excluded: violations=85
- holdout_sheet_40: holdout_ok=True
- video_sheet_10: sheets_ok=False
- pack_r1_r6_complete: missing=0
- no_user_field_filled: user_ok=True
- secret_scan: matches=0

## Ngân sách

- Lời gọi AI: 124 (trần: 120)
- Chi phí ledger: 0 USD (trần: 10 USD)
- Dung lượng Drive: 307516118 byte (0.29 GiB, trần: 3 GiB)
- Thời gian chạy: 3479.5 giây (0.97 giờ, trần: 4 giờ)

Batch ID: `43fb05ea-f976-4bee-a0c4-e393db5502f4`

Theo quyết định của user ngày 04/11/2026, lô mẫu nghiệm thu được nâng lên 20 video (thay vì 10 video); profile.json không sửa (`batch.target.sample_run` giữ 10); trần ngân sách nhân đôi: ≤ 120 lời gọi AI, ledger +10 USD, Drive ≤ 3 GiB, ≤ 4 giờ; giữ nguyên tên các khóa báo cáo dạng *_10 để tương thích probe kiểm tra.

## Bảng R1–R6

| R | Mã chờ gốc | Gate RG | Tệp bằng chứng | sha256 | Màn Dashboard |
| --- | --- | --- | --- | --- | --- |
| R1 | M3-EG7 ; M3-REAL | RG-04 | docs/delivery-evidence/cp7-5/report.md | 5f36460c50c2d22ed6bc901a452857c20c48650f40807076d51a6e6a188a01e4 | sources ; articles ; events ; stage-runs |
| R2 | M4-EG6 ; M4-EG5 | RG-02 ; RG-06 | docs/delivery-evidence/cp7-3/report.md | b45643506df81da71488d15385e56555da24eea4b56719b61d6f56179f3d99dd | media ; hooks ; artifacts |
| R2 | M4-EG6 ; M4-EG5 | RG-02 ; RG-06 | docs/delivery-evidence/cp7-7/report.md | f05ba8d3db639bc18630d12dd6a22b6b3784246ee9bdaad06664072fa2f3970f | media ; hooks ; artifacts |
| R3 | M5-EG7 ; M5-REAL | RG-03 ; RG-04 ; RG-13 | docs/delivery-evidence/cp7-4/report.md | 1a466b91149fa1718a0ccaefc1dc4dcc3ad9fa2e0fa52e05749305f442838afa | snapshots ; story-angles ; scripts |
| R3 | M5-EG7 ; M5-REAL | RG-03 ; RG-04 ; RG-13 | docs/delivery-evidence/cp7-5/report.md | 5f36460c50c2d22ed6bc901a452857c20c48650f40807076d51a6e6a188a01e4 | snapshots ; story-angles ; scripts |
| R3 | M5-EG7 ; M5-REAL | RG-03 ; RG-04 ; RG-13 | docs/delivery-evidence/cp7-14/report.md | SELF | snapshots ; story-angles ; scripts |
| R4 | M6-EG6 ; M6-EG1 ; M6-EG5 | RG-05 ; RG-06 ; RG-07 ; RG-09 ; RG-13 | docs/delivery-evidence/cp7-6/report.md | cae6566ea221ddaedf0cea1b8f2b658a63ee138ea8ee6febf47e9cac41bc5c01 | plan.md mục 5 không nêu tên màn riêng cho R4; user xem 10 video mẫu trên Dashboard |
| R4 | M6-EG6 ; M6-EG1 ; M6-EG5 | RG-05 ; RG-06 ; RG-07 ; RG-09 ; RG-13 | docs/delivery-evidence/cp7-7/report.md | f05ba8d3db639bc18630d12dd6a22b6b3784246ee9bdaad06664072fa2f3970f | plan.md mục 5 không nêu tên màn riêng cho R4; user xem 10 video mẫu trên Dashboard |
| R4 | M6-EG6 ; M6-EG1 ; M6-EG5 | RG-05 ; RG-06 ; RG-07 ; RG-09 ; RG-13 | docs/delivery-evidence/cp7-8/report.md | 26d28a5ff6d15bdf1344ca8f3c10be6f7a371ff17711a4df9cfba174bcda50b6 | plan.md mục 5 không nêu tên màn riêng cho R4; user xem 10 video mẫu trên Dashboard |
| R4 | M6-EG6 ; M6-EG1 ; M6-EG5 | RG-05 ; RG-06 ; RG-07 ; RG-09 ; RG-13 | docs/delivery-evidence/cp7-10/report.md | bf9b4d52f0616660cca61fdff7a3ed5da518512160330deba88d5cfce90b29ed | plan.md mục 5 không nêu tên màn riêng cho R4; user xem 10 video mẫu trên Dashboard |
| R4 | M6-EG6 ; M6-EG1 ; M6-EG5 | RG-05 ; RG-06 ; RG-07 ; RG-09 ; RG-13 | docs/delivery-evidence/cp7-14/report.md | SELF | plan.md mục 5 không nêu tên màn riêng cho R4; user xem 10 video mẫu trên Dashboard |
| R5 | M7-R5-EG1 | RG-08 ; RG-10 | docs/delivery-evidence/cp7-9/report.md | a34b1d3993e91ecc15b68bef2ac4eac337fa9b1ed2b96ae97cbe4a4b9751266f | batches ; jobs ; logs |
| R5 | M7-R5-EG1 | RG-08 ; RG-10 | docs/delivery-evidence/cp7-11/report.md | c68c46f628bed8658bfdb95d7a798ddfbe232bd1092b15c75b2de25ef89d90c3 | batches ; jobs ; logs |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-1/report.md | 16a0e501f4ea29c223f294fe64b27eddb878268c8bb00c03205dd36a34237d7b | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-2/report.md | e4c046b884fec47014a1fd2f6dc3ce28b07dc080520f39ce4c3540ba90cb2687 | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-3/report.md | b45643506df81da71488d15385e56555da24eea4b56719b61d6f56179f3d99dd | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-4/report.md | 1a466b91149fa1718a0ccaefc1dc4dcc3ad9fa2e0fa52e05749305f442838afa | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-5/report.md | 5f36460c50c2d22ed6bc901a452857c20c48650f40807076d51a6e6a188a01e4 | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-6/report.md | cae6566ea221ddaedf0cea1b8f2b658a63ee138ea8ee6febf47e9cac41bc5c01 | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-7/report.md | f05ba8d3db639bc18630d12dd6a22b6b3784246ee9bdaad06664072fa2f3970f | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-8/report.md | 26d28a5ff6d15bdf1344ca8f3c10be6f7a371ff17711a4df9cfba174bcda50b6 | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-9/report.md | a34b1d3993e91ecc15b68bef2ac4eac337fa9b1ed2b96ae97cbe4a4b9751266f | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-10/report.md | bf9b4d52f0616660cca61fdff7a3ed5da518512160330deba88d5cfce90b29ed | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-11/report.md | c68c46f628bed8658bfdb95d7a798ddfbe232bd1092b15c75b2de25ef89d90c3 | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-12/report.md | 885260813463075e811840b2b5d63a411478a287c6fef862b8991c8613d403f1 | cost |
| R6 | M7-R6 | RG-01 ; RG-02 ; RG-03 ; RG-04 ; RG-05 ; RG-06 ; RG-07 ; RG-08 ; RG-09 ; RG-10 ; RG-11 ; RG-12 | docs/delivery-evidence/cp7-13/report.md | 85563d3dc91caba0c8382e9e3372b76bfa58e8b0f0616ff7d818fcabac046dac | cost |

Kết luận R1–R6 là của user; gói này chỉ chuẩn bị bằng chứng.

## Bảng chấm video

| STT | Job | Topic | Media/hook | Cloud verified | Nhãn topic (user) | Nhãn media/hook (user) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:1 |  | article=5 ai=1 seed=0 hook=pxb-2723 | PASS |  |  |
| 2 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:2 |  | article=2 ai=4 seed=0 hook=pxb-1490 | PASS |  |  |
| 3 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:3 |  | article=3 ai=2 seed=0 hook=pxb-1490 | PASS |  |  |
| 4 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:4 |  | article=3 ai=3 seed=0 hook=pxb-2723 | PASS |  |  |
| 5 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:5 |  | article=2 ai=2 seed=0 hook=pxb-2723 | PASS |  |  |
| 6 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:6 |  | article=7 ai=0 seed=0 hook=pxb-2723 | PASS |  |  |
| 7 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:7 |  | article=5 ai=0 seed=0 hook=pxb-2723 | PASS |  |  |
| 8 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:8 |  | article=2 ai=4 seed=0 hook=pxb-2723 | PASS |  |  |
| 9 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:9 |  | article=1 ai=3 seed=0 hook=pxb-2723 | PASS |  |  |
| 10 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:10 |  | article=1 ai=3 seed=0 hook=pxb-1358 | PASS |  |  |
| 11 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:11 |  | article=5 ai=0 seed=0 hook=pxb-2723 | PASS |  |  |
| 12 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:12 |  | article=2 ai=3 seed=0 hook=pxb-2723 | PASS |  |  |
| 13 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:13 |  | article=6 ai=0 seed=0 hook=pxb-2723 | PASS |  |  |
| 14 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:14 |  | article=3 ai=2 seed=0 hook=pxb-2723 | PASS |  |  |
| 15 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:15 |  | article=3 ai=3 seed=0 hook=pxb-2723 | PASS |  |  |
| 16 | 43fb05ea-f976-4bee-a0c4-e393db5502f4:job:16 |  | article=2 ai=3 seed=0 hook=pxb-2723 | PASS |  |  |

## Bảng 40 cặp holdout (event-link)

holdout_manifest_sha256: c2e1fc1d8309d57d26ddcdf3bbd83c65b100a391d2659e4c6aba61e9f6aba314

| STT | Bài A | Bài B | Nhãn event-link (user) |
| --- | --- | --- | --- |
| 1 | aljazeera-all-4498dfa315ab | aljazeera-all-5043a38b063f |  |
| 2 | aljazeera-all-4498dfa315ab | bbc-tech-6f0240bccdc0 |  |
| 3 | aljazeera-all-4ab3a42f36bc | aljazeera-all-5043a38b063f |  |
| 4 | aljazeera-all-4ab3a42f36bc | bbc-tech-e19bd8c68654 |  |
| 5 | aljazeera-all-4ab3a42f36bc | nasa-news-6a8e8f4a60c5 |  |
| 6 | aljazeera-all-5043a38b063f | guardian-world-2f3de9f7785b |  |
| 7 | aljazeera-all-5043a38b063f | npr-news-e58da7a8afb0 |  |
| 8 | aljazeera-all-af11012ee96e | bbc-tech-91124b3ea1c8 |  |
| 9 | aljazeera-all-e3d5295b0592 | bbc-tech-2c43e290abc0 |  |
| 10 | aljazeera-all-e3d5295b0592 | bbc-tech-6f0240bccdc0 |  |
| 11 | aljazeera-all-e3d5295b0592 | guardian-world-49c28743b657 |  |
| 12 | bbc-tech-2c43e290abc0 | nasa-news-4b2c059bd94e |  |
| 13 | bbc-tech-6f0240bccdc0 | bbc-world-42b4ece9731d |  |
| 14 | bbc-tech-6f0240bccdc0 | guardian-world-2f3de9f7785b |  |
| 15 | bbc-tech-6f0240bccdc0 | guardian-world-6dbae2bdfca2 |  |
| 16 | bbc-tech-6f0240bccdc0 | npr-news-205c9d0aceef |  |
| 17 | bbc-tech-91124b3ea1c8 | nasa-news-dbf41850dbae |  |
| 18 | bbc-tech-b65ab71cbfef | bbc-world-8dd76e232746 |  |
| 19 | bbc-tech-b65ab71cbfef | guardian-world-2f3de9f7785b |  |
| 20 | bbc-tech-b65ab71cbfef | guardian-world-49c28743b657 |  |
| 21 | bbc-tech-b65ab71cbfef | nasa-news-4b2c059bd94e |  |
| 22 | bbc-tech-b65ab71cbfef | nasa-news-dbf41850dbae |  |
| 23 | bbc-tech-e19bd8c68654 | bbc-world-8dd76e232746 |  |
| 24 | bbc-tech-e19bd8c68654 | guardian-world-c889760de5d3 |  |
| 25 | bbc-world-42b4ece9731d | bbc-world-8dd76e232746 |  |
| 26 | bbc-world-42b4ece9731d | nasa-news-dddd54e7732b |  |
| 27 | bbc-world-42b4ece9731d | npr-news-da8b8634258e |  |
| 28 | bbc-world-6a9e1f4905d4 | guardian-world-2f3de9f7785b |  |
| 29 | bbc-world-6a9e1f4905d4 | nasa-news-624e1e1e3d1b |  |
| 30 | bbc-world-8dd76e232746 | npr-news-e58da7a8afb0 |  |
| 31 | bbc-world-fab0cbed0e94 | npr-news-0703acb0aa63 |  |
| 32 | bbc-world-fab0cbed0e94 | npr-news-da8b8634258e |  |
| 33 | guardian-world-49c28743b657 | nasa-news-4b2c059bd94e |  |
| 34 | guardian-world-49c28743b657 | npr-news-093ad3a9e12b |  |
| 35 | guardian-world-6dbae2bdfca2 | npr-news-093ad3a9e12b |  |
| 36 | guardian-world-c889760de5d3 | nasa-news-624e1e1e3d1b |  |
| 37 | guardian-world-c889760de5d3 | npr-news-da8b8634258e |  |
| 38 | nasa-news-624e1e1e3d1b | npr-news-093ad3a9e12b |  |
| 39 | nasa-news-6a8e8f4a60c5 | npr-news-e58da7a8afb0 |  |
| 40 | nasa-news-dbf41850dbae | npr-news-e58da7a8afb0 |  |
