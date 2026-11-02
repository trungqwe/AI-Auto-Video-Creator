# Sidecar sinh ảnh minh hoạ (IMGGEN-SVC)

Tiến trình riêng do launcher quản lý, sinh ảnh minh hoạ 9:16 bằng FLUX 3 Image Klein (bản distilled, transformer FP8) trên GPU
của máy. Sidecar có môi trường uv riêng, nằm ngoài runtime khoá của sản phẩm và ngoài Runtime Keeper; torch không bao giờ vào
runtime sản phẩm.

## Tệp

| Tệp | Vai trò |
| --- | --- |
| `pyproject.toml`, `uv.lock` | Môi trường riêng: Python 3.13.15, phiên bản ghim theo nguyên mẫu Control 02/11/2026, torch và torchvision chỉ từ chỉ mục cu130, chỉ Windows |
| `weights.lock.json` | 25 tệp trọng số (24 của `flux-3-image-klein@337337621b85`, `system_prompts.json` của kho pup) với kích thước, SHA-256 và nguồn đối chiếu |
| `protocol.py` | Hằng số, kiểm yêu cầu, băm idempotency, seed (chỉ thư viện chuẩn) |
| `weights.py` | Đọc danh mục, bố cục cache HF, kiểm băm có tem (chỉ thư viện chuẩn) |
| `engine.py` | Chu kỳ ba pha (text encoder, transformer, VAE), nạp từng khúc 64 MiB thẳng vào GPU (không mmap, không gom tệp vào RAM), đo bộ nhớ theo pha, bản vá FP8 cho Ada, lệnh đo trên GPU |
| `server.py` | API HTTP loopback, job, hàng đợi, vòng đời |
| `provision.py` | Cài trọng số vào `<data>/models/hf-hub` (Control chạy một lần) |

## Dựng môi trường

```
set UV_PROJECT_ENVIRONMENT=<data>\imagegen\venv
uv sync --frozen --project tools/imagegen
```

## Cài trọng số

```
<python> -I tools/imagegen/provision.py --hub <data>/models/hf-hub --from-hub D:/AIAVC_IMGPROTO/hub
```

Không có `--from-hub` thì tải bằng `hf_hub_download` theo revision ghim, dưới đăng nhập `hf auth login` của user; mã không đọc
token. Script băm đủ 25 tệp, đặt `refs/main` và ghi tem `imagegen-weights.stamp.json`.

## Chạy

```
set AIAVC_IMAGEGEN_TOKEN=<token mới mỗi lần khởi động, >= 32 ký tự>
<data>\imagegen\venv\Scripts\python.exe -I tools/imagegen/server.py --port 57030 --hub <data>/models/hf-hub
    --out <data>/imagegen/out --parent-pid <pid launcher> --stop-file <data>/state/stop.request
```

- `GET /v1/health` (không cần token): `state` là `not_provisioned`, `verifying`, `idle`, `loading`, `busy` hoặc `error`; kèm
  revision, hàng đợi, `fp8_path`, VRAM trống. Không nạp mô hình.
- `POST /v1/jobs` `{job_id (32 hex), items[1..6]{item_id, caption, width, height, steps, seed}}`: 202. Gửi lại đúng thân thì nhận
  lại job và các ảnh lỗi còn lượt được xếp lại; thân khác cùng `job_id` là 409; chưa cài trọng số là 503.
- `GET /v1/jobs/{id}`, `GET /v1/jobs/{id}/items/{item}` (PNG, `X-Content-SHA256`). Kết quả giữ 24 giờ.
- `POST /v1/shutdown`. Sidecar cũng dừng khi có `stop.request` hoặc khi tiến trình cha thoát.

## Đo trên GPU (Control)

```
set HF_HUB_OFFLINE=1
<python có torch> -I tools/imagegen/engine.py measure --hub <hub> --captions <captions.json> --caption-field t2i --out <thư mục>
```

Ghi PNG và `report.json`: VRAM đỉnh từng pha; bộ nhớ riêng (commit) và VRAM giữ trước, sau nạp, sau pha, sau giải phóng, đỉnh
trong pha và phần dư; bộ nhớ riêng đỉnh của tiến trình, RAM trống thấp nhất; giây mỗi ảnh; `fp8_path` và sai số tự kiểm FP8.
Mỗi pha cũng in một dòng tóm tắt bộ nhớ. `/v1/health` của sidecar trả cùng các số đó cho chu kỳ gần nhất (`last_cycle`), cùng
`memory` (đỉnh suốt đời) và `commit` (giới hạn và phần trống của commit hệ thống).

Trên Windows (WDDM), VRAM được tính vào commit của tiến trình, nên bộ nhớ riêng thô gần bằng nền cộng VRAM đang giữ. Ngân sách vì
thế chấm working set đỉnh <= 4 GiB, đỉnh (private trừ VRAM đang giữ) <= 4 GiB, phần dư sau pha <= 2,5 GiB ở chu kỳ đầu và
<= 512 MiB về sau (`--cycles 2` để đo cả trạng thái ổn định; ngân sách hỏng thì mã thoát 4). Trước mỗi pha, commit trống của hệ
thống phải >= `PHASE_COMMIT_BYTES` của pha cộng 2 GB, không thì chờ tối đa 600 giây rồi báo `HOST_COMMIT_LOW`.
