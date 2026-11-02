# Báo cáo nghiệm thu bàn giao: IMGGEN-PIPE

## 1. Thông tin chung

- Mã nhiệm vụ: IMGGEN-PIPE
- Nhóm lỗi liên quan: OI-CP7-11-Q2
- Mô tả tóm tắt: Tích hợp ảnh minh họa AI vào pipeline sản xuất video: activity GenerateIllustrations chạy đầu stage media_select (trước SelectCreativeAssets) sau patch Temporal video-ai-illustrations. Tối đa 4 ảnh AI cho mỗi video để đạt tới 5 ảnh không phải seed. Chú thích t2i được kiểm bằng mã. Catalog workflow v2 giữ nguyên; lịch sử cũ không có marker vẫn phát lại đúng trên bảng LEGACY_VIDEO_STAGE_ACTIVITIES. Launcher gắn handler qua assemble_dfe_handlers.

## 2. Danh sách 16 tệp mã và test từ bản tham chiếu Control

Cả 16 tệp được chép nguyên văn từng byte từ D:/AIAVC_IMGPROTO/ref/imggen-pipe/ và khớp sha256 trong SHA256SUMS (kiểm bằng lệnh ở dòng 6 của mục 3).

### 6 tệp tạo mới

1. `src/controlplane/api/wiring/illustrations.py`: 37e53dc0c54e15f3c5e186a2420eb4193338b320e21007d81c8279ab48784be4
2. `src/controlplane/infrastructure/production_ports/imagegen_client.py`: d3ac447040bb60f0eeef45424ce02435d35825a7d270627758bfd0df31001691
3. `tests/integration/prod_wiring/imggen_pipe_support.py`: 9ae2795be9233e35852ac901b8c9103c456065c4ac09c1b654fbb73a1f1120b0
4. `tests/integration/prod_wiring/test_imggen_pipe_client.py`: 6dff27d58d9dab5c7390c736c47dd80b2e6a8b077ece2f1863c87e68cf8a2d31
5. `tests/integration/prod_wiring/test_imggen_pipe_activity.py`: d94732adc769aeed3f5bab9a3da4475b6b72517611cf651e4a8b0c1628709115
6. `tests/integration/prod_wiring/test_imggen_pipe_replay.py`: aa9b5d8761e248ffe092f80e0a9a8fa0ab30d68cb5a3dbdad71be830a11a6fca

### 10 tệp cập nhật (ghi đè nguyên bản)

1. `src/controlplane/application/orchestration/workflows/activities.py`: 141ec57350d17a78129aecbfc18bae704ce3fed914317dc0deb055a8233346ef
2. `src/controlplane/application/orchestration/workflows/definitions.py`: 126d353caab367fe4ccda5661aeb783bb3e51547edec9bb612590d4ad0aa66dc
3. `tools/launcher/launcher.py`: d67ae236836f2d100cd6818885db5ac37c010f84403f71d942d1cbd7856cffa7
4. `tests/integration/prod_wiring/test_pw_cat1_catalog.py`: 4172b0705fb26b97e04a6046f3e0b5dea8acd7ad818e5e15e671a2ffc4629c2c
5. `tests/integration/prod_wiring/test_pw_cat2_flow.py`: 546091908d6b180c7b8ff1838a78f67ccf69fe0dca69b365a7f6fea422931c24
6. `tests/integration/prod_wiring/pw_vertical.py`: ca38a8387a920bd3b8ba16899a51e9435af6a514b4ffd119688e436b2e943352
7. `tests/integration/prod_wiring/test_pw_vert_video_flow.py`: dfee085e007c7fc084e4e3e33f1c1c19e5f7d009cf6d43013cba50b362ccf823
8. `tests/integration/prod_wiring/test_pw_w2_launcher_def.py`: 8f518a3fe4db4d5060edd68f7cc4ad782cb8a864c46b9ff5d8214be8629fbc1b
9. `tests/integration/prod_wiring/pw_e2e_support.py`: c0896984715351245dde5817f104ea3cb44fa4cbd5f63e300a4d0f20dd39f495
10. `tests/integration/prod_wiring/test_pw_e2e_batch_video.py`: 44bdb51b80d43b980afa39c5b1757b03ba5abf389dbb22f12c5c74df8f0ead52

## 3. Bảng kết quả thực thi các lệnh kiểm

| STT | Lệnh nguyên văn | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/integration/prod_wiring/test_imggen_pipe_client.py tests/integration/prod_wiring/test_imggen_pipe_activity.py tests/integration/prod_wiring/test_imggen_pipe_replay.py -q -p no:cacheprovider` | 0 | 23 passed in 18.86s |
| 2 | `python -m pytest tests/integration/prod_wiring/test_pw_cat1_catalog.py tests/integration/prod_wiring/test_pw_cat2_flow.py tests/integration/prod_wiring/test_pw_vert_video_flow.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/integration/prod_wiring/test_pw_cat2_fix1_variant_revalidate.py tests/integration/prod_wiring/test_pw_g4_fix1_job_terminal.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 0 | 106 passed in 62.27s (0:01:02) |
| 3 | `python -m pytest tests/unit/orchestration -q -p no:cacheprovider` | 0 | 1134 passed, 307 subtests passed in 0.94s |
| 4 | `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/launch/test_imggen_launch.py -q -p no:cacheprovider` | 0 | 79 passed in 59.71s |
| 5 | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | 12 passed, 1 warning in 263.85s (0:04:23) |
| 6 | Probe `python -c` so sha256 của 16 tệp mã và test với D:/AIAVC_IMGPROTO/ref/imggen-pipe/SHA256SUMS (lệnh nguyên văn là mục probe hashlib trong danh sách lệnh kiểm bắt buộc của task) | 0 | Đạt, 16 tệp trùng sha256 |
| 7 | `git diff --check` | 0 | Không có lỗi khoảng trắng |
| 8 | Các probe `python -c` cấu trúc còn lại trong danh sách lệnh kiểm bắt buộc của task (activities, definitions, illustrations, imagegen_client, launcher gồm assemble_dfe_handlers và start_worker, test và rig, pyproject) | 0 | Worker đã chạy ở vòng trước, mã thoát 0; Control chạy lại ở bước checks |

## 4. Dòng tổng kết nguyên văn của pytest

- Lệnh 1 (test_imggen_pipe_client.py, test_imggen_pipe_activity.py, test_imggen_pipe_replay.py): 23 passed in 18.86s (mã thoát 0)
- Lệnh 2 (test_pw_cat1_catalog.py, test_pw_cat2_flow.py, test_pw_vert_video_flow.py, test_pw_w2_launcher_def.py, test_pw_cat2_fix1_variant_revalidate.py, test_pw_g4_fix1_job_terminal.py, test_cp6_workflow_catalog.py, test_cp6_video_production_flow.py): 106 passed in 62.27s (0:01:02) (mã thoát 0)
- Lệnh 3 (tests/unit/orchestration): 1134 passed, 307 subtests passed in 0.94s (mã thoát 0)
- Lệnh 4 (test_pw_f4_render_worker.py, test_adapt_launch_cli.py, test_imggen_launch.py): 79 passed in 59.71s (mã thoát 0)
- Lệnh 5 (test_pw_e2e_batch_video.py): 12 passed, 1 warning in 263.85s (0:04:23) (mã thoát 0)

## 5. Giới hạn kỹ thuật và quyết định Control

Căn cứ quyết định Control ngày 02/11/2026 (DESIGN đợt 42 mục 9):

- Tạo ảnh minh họa dùng text-to-image (t2i), không dùng image-to-image (i2i).
- Thumbnail video không dùng ảnh AI (thuộc phạm vi gói IMGGEN-CAT).
- Ảnh AI được lưu và dùng chung theo bài viết, nên hai video cùng bài chạy song song có thể cùng sinh ảnh.
- Mã chờ ILLUSTRATION_QUEUED không phải WaitReason nên luồng ghi dependency_wait, hàng stage ghi provider_unavailable.
- Khi ảnh bài bị an toàn ảnh loại, fallback chỉ là seed; video vẫn có thể hỏng no_illustration_available dù có ảnh AI.
- Lane không chạy GPU; kiểm thử tích hợp và e2e dùng StaticImagegenSidecar và test server time-skipping.

## 6. Không chứa bí mật

- Không commit hay lưu token, API key, mật khẩu, thông tin xác thực hay dữ liệu cá nhân trong mã nguồn và tài liệu.
- Mã sản phẩm không đọc token từ biến môi trường; token được đọc mỗi lần gọi từ tệp endpoint.json trong thư mục dữ liệu.
