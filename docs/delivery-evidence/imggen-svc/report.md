# Báo cáo IMGGEN-SVC

Mã gói: `IMGGEN-SVC`. Nhóm lỗi: `OI-CP7-11-Q2` (định nghĩa gốc của Q2 không nằm trong repo; theo spec của task, ghi `GIẢ ĐỊNH`).

## Lý do làm lại

Candidate 62f57ab bị Auditor (Opus 5.5) FAIL với F1 BLOCKER (engine giả: pha trả tensor 0, VAE trả ảnh đồng màu, không dùng mô hình) và F2 MAJOR (cổng VRAM, commit, RAM không nối vào server); Control (đính chính IMGGEN-SVC-REFERENCE-COPY ngày 02/11/2026) yêu cầu chép nguyên văn bản tham chiếu đã được đo và kiểm chứng thực tế trên phần cứng GPU từ `D:/AIAVC_IMGPROTO/ref/imggen-svc/`.

## Tệp

Bảng 13 tệp trong owned paths: 12 tệp mã nguồn và kiểm thử được chép nguyên văn byte-for-byte từ thư mục tham chiếu `D:/AIAVC_IMGPROTO/ref/imggen-svc/` kèm mã SHA-256 (kiểm tra ở bước 13), cùng tệp `docs/delivery-evidence/imggen-svc/report.md` do Worker lập. Các tệp `tools/imagegen/pyproject.toml`, `tools/imagegen/uv.lock` và `tests/integration/imagegen/test_imagegen_env.py` KHÔNG thuộc gói này mà thuộc gói phụ thuộc `IMGGEN-DEPS`; Worker tuyệt đối không tạo hay chỉnh sửa các tệp đó.

| Tệp | SHA-256 | Nguồn / Ghi chú |
| --- | --- | --- |
| `tools/imagegen/__init__.py` | `963caa74c376e0cedd6e2a2d18bf805ec2fc5ebd4ab252597ba36f36e9c86bee` | Chép nguyên văn từ tham chiếu Control |
| `tools/imagegen/README.md` | `da7ff23c574721214ddd9026287fd68da2fa4500662a9b5143c69cd5fce60724` | Chép nguyên văn từ tham chiếu Control |
| `tools/imagegen/weights.lock.json` | `acb29143ae4ab41e53e73e18e3c28351dd3ac0debe258eb1f89ca13f691ebfbe` | Chép nguyên văn từ tham chiếu Control |
| `tools/imagegen/protocol.py` | `ffd211a292a563724c4a191d9fa2a1fc7ce9db2d453e88a3f637700b06289970` | Chép nguyên văn từ tham chiếu Control |
| `tools/imagegen/weights.py` | `a0fea7409702532e1c1225a5533ea5dbe94da6f77b14c31b1fddc711b72b1035` | Chép nguyên văn từ tham chiếu Control |
| `tools/imagegen/engine.py` | `d45322f39d03a2bef8edb9803def01ac43635f05bbda25b57877bc90d313cbb4` | Chép nguyên văn từ tham chiếu Control |
| `tools/imagegen/server.py` | `c6026bd4c726855fb8ba6e3bbd30d3750fbd816e921bdbe58b3cefea5f34ae8d` | Chép nguyên văn từ tham chiếu Control |
| `tools/imagegen/provision.py` | `ecb1db4502bb4b8fe2d32ea9d8619d72f38bada29c000321b79586cc8764aaa7` | Chép nguyên văn từ tham chiếu Control |
| `tests/integration/imagegen/test_imagegen_protocol.py` | `61c6be34b66a402ccd691aed8d47ddc2fc17b39e30a8065c6ee1606baaebcb07` | Chép nguyên văn từ tham chiếu Control |
| `tests/integration/imagegen/test_imagegen_weights.py` | `4d6684297708feea2cd576ffed4ecaaecb5c68ac7bf6bd3efefa7c0e17d3e2af` | Chép nguyên văn từ tham chiếu Control |
| `tests/integration/imagegen/test_imagegen_server.py` | `edb68d7c8cf5f8e1341992a0ed79e6364821c006fb29c6557a1cab221db8b895` | Chép nguyên văn từ tham chiếu Control |
| `tests/real/test_imagegen_real.py` | `b886237456f4960a3d466c6246ff1169954093d037f1f7da1599c50f88738ee9` | Chép nguyên văn từ tham chiếu Control |
| `docs/delivery-evidence/imggen-svc/report.md` | - | Do Worker tạo, ghi lại bằng chứng thực thi |

## Lệnh kiểm đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `git diff --check` (Bước 14) | 0 | Không có lỗi khoảng trắng |
| `python -m pytest tests/integration/imagegen -q -p no:cacheprovider` (Bước 15) | 0 | Dòng tổng kết nguyên văn: `75 passed in 7.58s` |
| Probe SHA-256 của 12 tệp tham chiếu (Bước 13) | 0 | Tất cả 12 tệp khớp SHA-256 tham chiếu, danh sách `bad` rỗng |
| Probe `weights.lock.json` nội dung tệp (Bước 16) | 0 | Khớp chính xác 25 mục tệp, size và SHA-256 |
| Probe `weights.lock.json` metadata lưu trữ và nguồn (Bước 17) | 0 | `schema_version == 1`, `in_git == False`, đúng revision và blob ID |
| Probe AST import thư viện nặng (Bước 18) | 0 | Không module nào import thư viện nặng ở mức module |
| Probe chuỗi và hằng số bắt buộc (Bước 19) | 0 | Có đầy đủ các ký hiệu, hàm, cổng tài nguyên và cơ chế nạp streaming |
| Probe test suite và test nhân bản (Bước 20) | 0 | Đủ 16 hàm test tích hợp, dùng `ScriptedBackend`, không dùng mock hay monkeypatch; test real có đủ ràng buộc hằng số |
| Probe cấu trúc controlplane và cấm import `src.` (Bước 21) | 0 | Cấu trúc gói hợp lệ, không có import tiền tố `src.` |
| Probe nội dung report.md (Bước 23) | 0 | Có mặt chuỗi `IMGGEN-SVC` và `OI-CP7-11-Q2` |
| `git diff --check` lần cuối (Bước 24) | 0 | Hoàn toàn sạch lỗi khoảng trắng |

## Hành vi của bản tham chiếu

Bản tham chiếu triển khai hoàn chỉnh dịch vụ sidecar sinh ảnh theo các chuẩn kỹ thuật:
- **Chu kỳ 3 pha tuần tự trên GPU**: `text_encoder` -> `transformer` -> `vae`. Mỗi pha chỉ nạp mô hình tương ứng vào VRAM, xử lý toàn bộ các ảnh trong hàng đợi, sau đó giải phóng hoàn toàn qua `gc.collect()` và `torch.cuda.empty_cache()` trước khi chuyển pha tiếp theo.
- **Cổng tài nguyên nghiêm ngặt**: Kiểm tra VRAM trống (dư >= nhu cầu + 1.5 GB), bộ nhớ commit hệ thống qua `GlobalMemoryStatusEx` (commit trống >= commit pha + 2 GB), và RAM trống >= 2 GB. Cổng cho phép chờ tối đa 600 s trước khi từ chối an toàn với mã `GPU_MEMORY_UNAVAILABLE`, `HOST_COMMIT_LOW` hoặc `HOST_MEMORY_LOW`. Xử lý OOM bằng cách thử lại duy nhất một lần (`GPU_OUT_OF_MEMORY`).
- **Nạp streaming trực tiếp vào CUDA không qua RAM**: Đọc header safetensors bằng thư viện chuẩn, nạp từng khúc 64 MiB thẳng vào CUDA tensor, không dùng mmap, `load_file` hay `safe_open`. Text encoder và VAE dựng trên `torch.device('meta')` rồi gọi `load_state_dict(assign=True)`; Transformer dựng qua `from_single_file(dict)`. Đo lường qua `MemoryProbe` và tính ngân sách `memory_budget` (working set <= 4 GiB, private trừ VRAM <= 4 GiB, dư <= 2.5 GiB ở chu kỳ đầu và <= 512 MiB ở các chu kỳ sau).
- **API dịch vụ HTTP loopback**: Lắng nghe độc quyền tại `127.0.0.1` (`SO_EXCLUSIVEADDRUSE`) với cổng mặc định `57030`. Xác thực token Bearer qua `hmac.compare_digest` trên mọi endpoint (trừ `GET /v1/health`).
- **Endpoint và hàng đợi**:
  - `POST /v1/jobs`: Tiếp nhận job (tối đa 6 ảnh/job, hàng đợi tối đa 96 ảnh), trả về HTTP 202; idempotent với cùng job_id và cùng thân (xếp lại các ảnh lỗi còn lượt); trả về HTTP 409 nếu trùng job_id khác thân; HTTP 429 nếu hàng đợi đầy; HTTP 503 nếu chưa provision hoặc có lỗi nghiêm trọng.
  - `GET /v1/jobs/<job_id>`: Truy xuất trạng thái và tiến độ xử lý ảnh.
  - `GET /v1/jobs/<job_id>/artifacts/<item_id>.png`: Tải ảnh kết quả kèm header xác thực `X-Content-SHA256`.
  - `GET /v1/health`: Báo cáo trạng thái sức khoẻ, bộ nhớ theo từng pha, commit hệ thống và tiến độ hàng đợi không cần token.
  - `POST /v1/shutdown`: Dừng dịch vụ an toàn.
- **Kiểm tra trọng số theo SHA-256 và tem xác thực**: `weights.py` định vị tệp theo cache Hugging Face, đối chiếu toàn bộ 25 mục tệp với `weights.lock.json`. Sau khi xác thực toàn diện lần đầu, ghi tem `imagegen-weights.stamp.json` để tăng tốc khởi động lần sau; chỉ xác thực lại khi tem thiếu hoặc commit refs thay đổi.

## Giới hạn và GIẢ ĐỊNH

- **GPU và môi trường thực**: Các số đo hiệu năng phần cứng (28,8 s/ảnh trên NVIDIA GeForce RTX 4070 SUPER) là số liệu do Control đo đạc thực tế trên bản tham chiếu. Worker trong lane này chạy trên môi trường không có GPU CUDA, không tải trọng số từ mạng ngoài và không gọi Internet.
- **Kiểm thử thực tế**: Tệp `tests/real/test_imagegen_real.py` yêu cầu GPU thật, trọng số mô hình thật và env uv riêng (cu130), chỉ do Control thực thi; Worker không chạy tệp này.
- **Môi trường giả lập tích hợp**: Bộ kiểm thử tích hợp `tests/integration/imagegen/test_imagegen_server.py` sử dụng backend kịch bản hoá `ScriptedBackend` độc lập để xác minh giao thức, hàng đợi, idempotency và các cổng tài nguyên mà không nạp hay chạy mô hình thật.
