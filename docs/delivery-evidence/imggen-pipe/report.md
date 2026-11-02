# Báo cáo nghiệm thu bàn giao: IMGGEN-PIPE

## 1. Thông tin chung

- Mã nhiệm vụ: IMGGEN-PIPE
- Nhóm lỗi liên quan: OI-CP7-11-Q2
- Mô tả tóm tắt: Tích hợp ảnh minh họa AI vào pipeline sản xuất video: activity GenerateIllustrations chạy đầu stage media_select (trước SelectCreativeAssets) sau patch Temporal ideo-ai-illustrations. Hạn mức tối đa 4 ảnh AI cho mỗi video để đạt tối đa 5 ảnh không phải seed. Chú thích prompt t2i được kiểm tra bằng mã an toàn. Catalog workflow v2 giữ nguyên và các workflow chạy lại từ lịch sử cũ vẫn phát lại đúng trên bảng legacy.

## 2. Danh sách 16 tệp mã và kiểm thử từ bản tham chiếu Control

Tất cả 16 tệp mã và test đã được chép nguyên văn từng byte từ bản tham chiếu Control tại D:/AIAVC_IMGPROTO/ref/imggen-pipe/ và xác nhận khớp 100% mã băm SHA-256 từ SHA256SUMS:

### 6 tệp tạo mới:
1. src/controlplane/api/wiring/illustrations.py: 37e53dc0c54e15f3c5e186a2420eb4193338b320e21007d81c8279ab48784be4
2. src/controlplane/infrastructure/production_ports/imagegen_client.py: d3ac447040bb60f0eeef45424ce02435d35825a7d270627758bfd0df31001691
3. 	ests/integration/prod_wiring/imggen_pipe_support.py: 9ae2795be9233e35852ac901b8c9103c456065c4ac09c1b654fbb73a1f1120b0
4. 	ests/integration/prod_wiring/test_imggen_pipe_client.py: 6dff27d58d9dab5c7390c736c47dd80b2e6a8b077ece2f1863c87e68cf8a2d31
5. 	ests/integration/prod_wiring/test_imggen_pipe_activity.py: d94732adc769aeed3f5bab9a3da4475b6b72517611cf651e4a8b0c1628709115
6. 	ests/integration/prod_wiring/test_imggen_pipe_replay.py: a9b5d8761e248ffe092f80e0a9a8fa0ab30d68cb5a3dbdad71be830a11a6fca

### 10 tệp cập nhật (ghi đè nguyên bản):
1. src/controlplane/application/orchestration/workflows/activities.py: 141ec57350d17a78129aecbfc18bae704ce3fed914317dc0deb055a8233346ef
2. src/controlplane/application/orchestration/workflows/definitions.py: 126d353caab367fe4ccda5661aeb783bb3e51547edec9bb612590d4ad0aa66dc
3. 	ools/launcher/launcher.py: d67ae236836f2d100cd6818885db5ac37c010f84403f71d942d1cbd7856cffa7
4. 	ests/integration/prod_wiring/test_pw_cat1_catalog.py: 4172b0705fb26b97e04a6046f3e0b5dea8acd7ad818e5e15e671a2ffc4629c2c
5. 	ests/integration/prod_wiring/test_pw_cat2_flow.py: 546091908d6b180c7b8ff1838a78f67ccf69fe0dca69b365a7f6fea422931c24
6. 	ests/integration/prod_wiring/pw_vertical.py: ca38a8387a920bd3b8ba16899a51e9435af6a514b4ffd119688e436b2e943352
7. 	ests/integration/prod_wiring/test_pw_vert_video_flow.py: dfee085e007c7fc084e4e3e33f1c1c19e5f7d009cf6d43013cba50b362ccf823
8. 	ests/integration/prod_wiring/test_pw_w2_launcher_def.py: 8f518a3fe4db4d5060edd68f7cc4ad782cb8a864c46b9ff5d8214be8629fbc1b
9. 	ests/integration/prod_wiring/pw_e2e_support.py: c0896984715351245dde5817f104ea3cb44fa4cbd5f63e300a4d0f20dd39f495
10. 	ests/integration/prod_wiring/test_pw_e2e_batch_video.py: 44bdb51b80d43b980afa39c5b1757b03ba5abf389dbb22f12c5c74df8f0ead52

## 3. Bảng kết quả thực thi các lệnh kiểm tra

| Bước | Lệnh kiểm tra | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 17 | Kiểm tra tính toàn vẹn SHA-256 của 16 tệp mã và test | 0 | Đạt, tất cả tệp trùng khớp tuyệt đối |
| 18 | git diff --check | 0 | Đạt, không có lỗi khoảng trắng |
| 19 | Pytest bộ kiểm thử mới 	est_imggen_pipe_{client,activity,replay}.py | 0 | Đạt, 23 passed |
| 20 | Pytest catalog, flow, vertical, launcher def và cp6 | 0 | Đạt, 106 passed |
| 21 | Pytest đơn vị orchestration 	ests/unit/orchestration | 0 | Đạt, 1134 passed, 307 subtests passed |
| 22 | Pytest render worker và launcher 	est_pw_f4_render_worker, 	est_adapt_launch_cli, 	est_imggen_launch | 0 | Đạt, 79 passed |
| 23 | Pytest e2e batch video 	est_pw_e2e_batch_video.py | 0 | Đạt, 12 passed, 1 warning |
| 24 | Probe cấu trúc ctivities.py, definitions.py, workflow_catalog.py | 0 | Đạt |
| 25 | Probe cấu trúc illustrations.py, imagegen_client.py | 0 | Đạt |
| 26 | Probe cấu trúc launcher.py (ssemble_dfe_handlers, start_worker) | 0 | Đạt |
| 27 | Probe cấu trúc các tệp test và rig kiểm thử | 0 | Đạt |
| 28 | Probe wiring StartBatch | 0 | Đạt |
| 29 | Probe definitions (PW-G4-FIX1, batch concurrency, patched, batch start) | 0 | Đạt |
| 30 | Probe rig e2e (voice, e2e patch, vision) | 0 | Đạt |
| 31 | Probe RG-13 và D3-FIX3 | 0 | Đạt |
| 32 | Probe rig PW-VERT và inspect_output | 0 | Đạt |
| 33 | Probe launcher (launch-fix2, PW-W2-FIX5, PW-W1-FIX1, executor, resolve_documents, PW-W1) | 0 | Đạt |
| 34 | Probe sidecar imagegen launcher (Deps.start_imagegen, serve order, args) | 0 | Đạt |
| 35 | Probe pyproject.toml package-dir và cấm import src. | 0 | Đạt |

## 4. Dòng tổng kết nguyên văn của pytest

- Bước 19 (	est_imggen_pipe_client.py, 	est_imggen_pipe_activity.py, 	est_imggen_pipe_replay.py):
  23 passed in 18.99s (exit code: 0)
- Bước 20 (	est_pw_cat1_catalog.py, 	est_pw_cat2_flow.py, 	est_pw_vert_video_flow.py, 	est_pw_w2_launcher_def.py, 	est_pw_cat2_fix1_variant_revalidate.py, 	est_pw_g4_fix1_job_terminal.py, 	est_cp6_workflow_catalog.py, 	est_cp6_video_production_flow.py):
  106 passed in 69.07s (0:01:09) (exit code: 0)
- Bước 21 (	ests/unit/orchestration):
  1134 passed, 307 subtests passed in 1.53s (exit code: 0)
- Bước 22 (	est_pw_f4_render_worker.py, 	est_adapt_launch_cli.py, 	est_imggen_launch.py):
  79 passed in 61.86s (0:01:01) (exit code: 0)
- Bước 23 (	est_pw_e2e_batch_video.py):
  12 passed, 1 warning in 200.02s (0:03:20) (exit code: 0)

## 5. Giới hạn kỹ thuật và quyết định Control

Căn cứ quyết định Control ngày 02/11/2026 (DESIGN đợt 42 mục 9):
- Tạo ảnh minh họa sử dụng chế độ Text-to-Image (t2i), không dùng Image-to-Image (i2i).
- Thumbnail video không dùng ảnh AI (thuộc phạm vi gói IMGGEN-CAT).
- Ảnh AI sinh ra được lưu trữ và chia sẻ theo bài viết, do đó hai video của cùng một bài chạy song song có thể cùng chia sẻ ảnh sinh ra.
- Mã chờ ILLUSTRATION_QUEUED ghi nhận trạng thái dependency_wait ở workflow và provider_unavailable ở bảng stage.
- Khi ảnh bài viết bị hệ thống an toàn ảnh loại bỏ, cơ chế fallback sử dụng ảnh seed; do đó video vẫn có khả năng gặp lỗi no_illustration_available nếu toàn bộ ảnh bài bị loại và không đủ ứng viên.
- Lane kiểm thử không sử dụng GPU thật; bộ kiểm thử tích hợp và e2e sử dụng StaticImagegenSidecar cùng cơ chế time-skipping của test server.

## 6. Không chứa bí mật

Xác nhận:
- Không commit hay lưu trữ bất kỳ token, API key, mật khẩu, thông tin xác thực hay dữ liệu cá nhân nào trong mã nguồn và tài liệu.
- Mã sản phẩm không đọc token từ biến môi trường; token được đọc động từ tệp endpoint.json theo đúng quy định phân quyền và bảo mật.
