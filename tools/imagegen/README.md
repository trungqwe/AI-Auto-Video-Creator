# Sidecar Sinh Ảnh Minh Hoạ FLUX 3 Image Klein (`tools/imagegen`)

Tài liệu kỹ thuật và hướng dẫn vận hành tiến trình sidecar sinh ảnh cục bộ sử dụng mô hình FLUX 3 Image Klein.

## 1. Mục đích và Kiến trúc

Sidecar phục vụ tạo ảnh minh hoạ cục bộ trên GPU bằng mô hình FLUX 3 Image Klein:
- **Tiến trình độc lập:** Chạy dưới dạng tiến trình riêng biệt ngoài runtime sản phẩm và Keeper.
- **Môi trường uv riêng (`cu130`):** Sử dụng cấu hình `tools/imagegen/pyproject.toml` và `uv.lock` do Control cấp riêng biệt; tuyệt đối không đưa PyTorch, torchvision, diffusers vào runtime khoá của sản phẩm.
- **Bảo mật và loopback:** Chỉ lắng nghe trên giao diện nội bộ `127.0.0.1` với cờ `SO_EXCLUSIVEADDRUSE`, yêu cầu xác thực qua Bearer Token.

## 2. Dựng Môi trường Thực thi (Dành cho Control)

Để thiết lập môi trường uv riêng cho sidecar (lệnh này do Control thực hiện, Worker không chạy trong lane):

```bash
uv sync --project tools/imagegen
```

Biến môi trường bắt buộc:
- `AIAVC_IMAGEGEN_TOKEN`: Khóa bí mật chia sẻ (Bearer token), độ dài tối thiểu 32 ký tự.

## 3. Khởi chạy Dịch vụ

Lệnh khởi động dịch vụ máy chủ HTTP sidecar:

```bash
python tools/imagegen/server.py --out <thư_mục_lưu_ảnh> --parent-pid <pid_tiến_trình_cha> --stop-file <đường_dẫn_tệp_dừng> --port 57030
```

Các tham số tuỳ chọn:
- `--hub`: Đường dẫn kho mô hình Hugging Face hub (mặc định tại `%LOCALAPPDATA%/AIAutoVideoCreator/models/hf-hub`).
- `--manifest`: Đường dẫn tệp khóa trọng số `weights.lock.json`.
- `--full-verify`: Thực hiện băm lại toàn bộ tệp thay vì tin cậy tem `imagegen-weights.stamp.json`.
- `--residency`: Chế độ lưu trú mô hình trong VRAM (`auto`, `phase`, `keep`).

## 4. Bảng Định tuyến API

| Phương thức | Đường dẫn | Xác thực | Trạng thái | Mô tả |
| --- | --- | --- | --- | --- |
| `GET` | `/v1/health` | Không | `200` | Trả về trạng thái dịch vụ, số ảnh chờ, thông số bộ nhớ theo pha và commit hệ thống |
| `POST` | `/v1/jobs` | Có | `202`, `400`, `409`, `429`, `503` | Tiếp nhận công việc sinh ảnh (tối đa 6 ảnh/job). `202`: chấp nhận/idempotent; `400`: sai định dạng; `409`: trùng ID khác thân; `429`: hàng đợi đầy (>96 ảnh); `503`: chưa provision hoặc lỗi |
| `GET` | `/v1/jobs/<job_id>` | Có | `200`, `404` | Lấy tiến độ và trạng thái chi tiết của công việc |
| `GET` | `/v1/jobs/<job_id>/items/<item_id>.png` | Có | `200`, `404`, `409` | Tải dữ liệu ảnh PNG hoàn tất kèm header `X-Content-SHA256`. `409`: ảnh chưa xong |
| `POST` | `/v1/shutdown` | Có | `202` | Yêu cầu dừng dịch vụ một cách an toàn |

## 5. Chu kỳ Xử lý 3 Pha và Cổng Kiểm soát Tài nguyên

Tiến trình gom tối đa 16 ảnh từ hàng đợi vào một chu kỳ xử lý gồm 3 pha tuần tự:
1. `text_encoder`: Nạp text encoder, mã hóa prompt thành embedding cho toàn bộ ảnh.
2. `transformer`: Nạp transformer, thực hiện khử nhiễu FP8 tensorwise theo số bước quy định.
3. `vae`: Nạp VAE, giải mã latents thành ảnh PNG thành phẩm.

Trước mỗi pha, dịch vụ kiểm tra các cổng an toàn tài nguyên (`wait_for_resources`):
- **Cổng VRAM:** Đảm bảo VRAM trống vượt ngưỡng yêu cầu của pha + 1.5 GB.
- **Cổng Commit:** Đảm bảo commit hệ thống khả dụng vượt ngưỡng yêu cầu + 2.0 GB.
- **Cổng RAM:** Đảm bảo RAM khả dụng của máy chủ tối thiểu 2.0 GB.

## 6. Nạp Trọng số Truyền thẳng (Streaming Safetensors)

- Không sử dụng `load_file(`, `safe_open(` hay ánh xạ bộ nhớ `mmap`.
- Trọng số được đọc tuần tự từng khối `STREAM_CHUNK_BYTES = 64 * 1024 * 1024` (64 MiB) truyền thẳng vào bộ đệm VRAM của thiết bị CUDA, giảm thiểu phân mảnh và áp lực lên working set của host.

## 7. Quản lý và Đồng bộ Trọng số (`provision.py`)

Công cụ kiểm tra và nạp trọng số cục bộ:
- Kiểm tra tính toàn vẹn 25 tệp theo `weights.lock.json` bằng SHA-256.
- Hỗ trợ nạp từ kho cục bộ sẵn có: `--from-hub <đường_dẫn_kho_nguồn>` (vừa chép vừa băm SHA-256).
- Hỗ trợ chế độ offline: `--no-download` (báo cáo thiếu nếu không có sẵn, không gọi mạng).
- Tuyệt đối không lưu trữ hay nhận mã xác thực `HF_TOKEN`.

## 8. GIẢ ĐỊNH (Assumptions)

Các giả định kiến trúc hiện tại cần Control kiểm chứng khi chạy thực tế trên phần cứng GPU:
- Tên khóa định dạng prompt bên trong `system_prompts.json` phục vụ cho `prompt_upsampler`.
- Lớp tuyến tính FP8 cụ thể của thư viện `diffusers` (cần vá `patch_bfl_fp8` bằng `torch._scaled_mm`).
- Mức tiêu thụ không gian commit thực tế `PHASE_COMMIT_BYTES` tương ứng từng pha.
- Tên lớp mô hình trích xuất từ cấu hình `config.json` (`architectures` hoặc `_class_name`).
- Trong phạm vi lane `lane-imggen-svc`, Worker không thực thi trên phần cứng GPU thật mà kiểm chứng qua test tích hợp loopback.

## 9. Giới hạn

- Thành phần khởi động tiến trình nền từ Control Plane (`IMGGEN-LAUNCH`) thuộc gói sau.
- Tích hợp luồng sinh ảnh tự động vào pipeline render (`IMGGEN-PIPE`) thuộc gói sau.