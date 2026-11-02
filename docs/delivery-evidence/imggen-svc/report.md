# Báo cáo IMGGEN-SVC

Mã gói: `IMGGEN-SVC`. Nhóm lỗi: `OI-CP7-11-Q2` (theo spec của task: định nghĩa gốc của Q2 không nằm trong repo; nội dung trên là `GIẢ ĐỊNH` theo spec của task).

## 1. Tệp đã tạo trong owned paths

Worker chỉ tạo 13 tệp được phân quyền trong `owned paths`. Hai tệp `tools/imagegen/pyproject.toml` và `tools/imagegen/uv.lock` KHÔNG thuộc gói IMGGEN-SVC: đây là tệp phụ thuộc, chỉ slice phụ thuộc được sửa, nên gói `IMGGEN-DEPS` (dependency_slice, mở sau gói này) tạo chúng; gói này không tạo hay sửa hai tệp đó (xem mục 6):

| Tệp | Mô tả |
| --- | --- |
| `tools/imagegen/__init__.py` | Khởi tạo module sidecar FLUX 3 Image Klein, docstring UTF-8, `__version__ = '0.0.0'`, không import thư viện nặng. |
| `tools/imagegen/protocol.py` | Giao thức chuẩn: hằng số mạng (57030, 127.0.0.1), giới hạn job/chu kỳ, `parse_job`, `derive_seed`, `body_sha256`, `utf8_stdio`. |
| `tools/imagegen/weights.py` | Quản lý và kiểm tra trọng số: `STAMP_NAME`, `load_manifest`, `file_path`, `verify` (hashing 1 lần, tin tem), `write_stamp`. |
| `tools/imagegen/weights.lock.json` | Khóa cấu hình 25 tệp trọng số FLUX 3 Image Klein và pup prompts theo SHA-256 cố định. |
| `tools/imagegen/engine.py` | Engine nạp truyền thẳng (streaming safetensors), đo bộ nhớ `MemoryProbe`, `KleinBackend`, `run_cycle` 3 pha, `wait_for_resources`, `memory_budget`. |
| `tools/imagegen/server.py` | Máy chủ HTTP loopback 127.0.0.1 với `SO_EXCLUSIVEADDRUSE`, `JobStore` lưu vết bền vững, xác thực Bearer token, dừng an toàn qua `watch_stop`. |
| `tools/imagegen/provision.py` | Công cụ chuẩn bị trọng số offline/from-hub, băm khi sao chép, không chứa `HF_TOKEN` hay `token=`. |
| `tests/integration/imagegen/test_imagegen_protocol.py` | Kiểm thử tích hợp protocol, kiểm tra không import torch lúc nạp, kiểm tra cấu trúc lock. |
| `tests/integration/imagegen/test_imagegen_weights.py` | Kiểm thử xác minh trọng số, tem tin cậy, đọc safetensors không torch, không dùng mock/monkeypatch. |
| `tests/integration/imagegen/test_imagegen_server.py` | Kiểm thử máy chủ `ScriptedBackend`, chia sẻ chu kỳ, thử lại OOM, cổng bộ nhớ, vòng đời stop file/parent pid. |
| `tests/real/test_imagegen_real.py` | Kiểm thử thực tế trên GPU (chỉ chạy khi có GPU và venv uv riêng biệt, không có mạng ngoài). |
| `tools/imagegen/README.md` | Hướng dẫn vận hành, kiến trúc, bảng API, chu kỳ 3 pha, nạp streaming và các giả định kỹ thuật. |
| `docs/delivery-evidence/imggen-svc/report.md` | Báo cáo giao nộp này. |

## 2. Bảng lệnh kiểm đã chạy

Các dòng Bước 16-28 là kết quả trước rebase; kết quả hiệu lực là mục 7 (chạy lại trên mã đã rebase).

| Bước | Lệnh kiểm | Exit code | Kết quả quan sát thực tế |
| --- | --- | --- | --- |
| Bước 16 | `git diff --check` | 0 | Không có lỗi khoảng trắng thừa (trailing whitespace sạch). |
| Bước 17 | `python -m pytest tests/integration/imagegen -q -p no:cacheprovider` | 0 | Dòng tổng kết nguyên văn của pytest: `33 passed, 1 skipped in 5.32s` (test_uv_lock_resolves_the_pins_from_the_cu130_index_with_hashes skip có lý do vì tools/imagegen/uv.lock thuộc IMGGEN-DEPS và chưa có trong worktree). |
| Bước 18 | Probe AST kiểm tra không import nặng ở mức module (`__init__.py`, `protocol.py`, `weights.py`, `engine.py`, `server.py`, `provision.py`) | 0 | Đạt exit 0, không có import nặng ở module-level. |
| Bước 19 | Probe chuỗi nguyên văn bắt buộc của protocol, weights, engine, server, provision | 0 | Đạt exit 0, chứa đầy đủ tất cả chuỗi hằng số, tên hàm và cơ chế streaming. |
| Bước 20 | Probe tên test bắt buộc, `ScriptedBackend`, kiểm tra không chứa `mock` hay `monkeypatch`, và các hằng số trong `test_imagegen_real.py` | 0 | Đạt exit 0, 17/17 tên test bắt buộc tồn tại, không có từ mock/monkeypatch. |
| Bước 21 | Probe `weights.lock.json` thứ nhất (kích thước và SHA-256 của 25 tệp) | 0 | Đạt exit 0, 25 mục khớp 100% với bảng `want`. |
| Bước 22 | Probe `weights.lock.json` thứ hai (repo, revision, component, source.kind, blob_id) | 0 | Đạt exit 0, cấu trúc phân loại khớp 100% với bảng `want`. |
| Bước 24 | Probe kiểm tra nội dung `report.md` | 0 | Đạt exit 0, chứa đầy đủ `IMGGEN-SVC` và `OI-CP7-11-Q2`. |
| Bước 25 | Probe controlplane package layout và không import `src.` | 0 | Đạt exit 0, toàn bộ layout hợp lệ. |
| Bước 26-27 (cũ) | Probe `tools/imagegen/pyproject.toml` và `tools/imagegen/uv.lock` | - | Đã rời khỏi lệnh kiểm của IMGGEN-SVC: hai tệp thuộc gói IMGGEN-DEPS (dependency_slice), probe của chúng do IMGGEN-DEPS chạy. |
| Bước 28 | `git diff --check` (lần cuối) | 0 | Sạch hoàn toàn, không có lỗi định dạng. |
| Bước 3 (lượt sửa) | `git diff --check` | 0 | Sạch. |

## 3. Kiến trúc API Dịch vụ

- **Giao diện mạng:** Chỉ bind vào `127.0.0.1` với tùy chọn `SO_EXCLUSIVEADDRUSE`, không mở ra ngoài máy chủ (`0.0.0.0`).
- **Xác thực:** Mọi route (ngoại trừ `GET /v1/health`) bắt buộc có header `Authorization: Bearer <token>` với độ dài token tối thiểu 32 ký tự, so khớp an toàn bằng `hmac.compare_digest`.
- **Định tuyến:**
  - `GET /v1/health`: Trả về trạng thái, số lượng ảnh trong hàng đợi, thông số bộ nhớ chi tiết theo pha và commit hệ thống.
  - `POST /v1/jobs`: Tiếp nhận tối đa 6 ảnh/job. Phản hồi `202 Accepted` (idempotent nếu cùng thân body), `400 Bad Request` nếu sai định dạng, `409 Conflict` nếu trùng ID khác thân, `429 Too Many Requests` khi hàng đợi đầy (>96 ảnh), `503 Service Unavailable` khi chưa provision.
  - `GET /v1/jobs/<job_id>`: Truy vấn trạng thái chi tiết của công việc.
  - `GET /v1/jobs/<job_id>/items/<item_id>.png`: Tải ảnh PNG thành phẩm, trả kèm header `X-Content-SHA256` khớp với SHA-256 của nội dung ảnh.
  - `POST /v1/shutdown`: Dừng dịch vụ có kiểm soát.

## 4. Kiểm tra Trọng số theo SHA-256

- Cơ chế khóa: `weights.lock.json` ghim chính xác 25 tệp trọng số từ repo `black-forest-labs/flux-3-image-klein` (revision `337337621b85...`) và `black-forest-labs/flux-3-image-klein-pup` (revision `3f3edb52b2c5...`).
- Tem xác thực: Quá trình `verify` chỉ băm SHA-256 một lần đầu tiên, sau đó ghi nhận tem `imagegen-weights.stamp.json` lưu cặp `(size, mtime_ns)`. Các lần kiểm tra sau tái sử dụng tem tin cậy để khởi động tức thì mà không phải đọc lại hàng chục gigabyte từ đĩa.
- Công cụ provision: `provision.py` hỗ trợ sao chép từ kho có sẵn `--from-hub`, thực hiện băm luồng đồng thời trong quá trình chép và kiểm tra khớp SHA-256 trước khi ghi nhận `refs/main`. Tuyệt đối không đọc hay yêu cầu `HF_TOKEN`.

## 5. Quản lý Bộ nhớ và Các Cổng Kiểm soát Tài nguyên

Tiến trình chia chu kỳ xử lý thành 3 pha tuần tự (`text_encoder`, `transformer`, `vae`):
- **Cổng VRAM (`wait_for_resources`):** Kiểm tra VRAM trống tối thiểu bằng dung lượng pha + 1.5 GB margin. Chờ tối đa 600 giây; nếu không đủ sẽ trả lỗi `GPU_MEMORY_UNAVAILABLE`.
- **Cổng Commit:** Kiểm tra commit khả dụng của Windows tối thiểu bằng dung lượng pha + 2.0 GB margin. Nếu thiếu sẽ trả lỗi `HOST_COMMIT_LOW`.
- **Cổng RAM Host:** Đảm bảo RAM trống tối thiểu 2.0 GB (`HOST_MEMORY_LOW`).
- **Ngân sách bộ nhớ (`memory_budget`):**
  - Working set tối đa: 4 GiB (`WSET_MAX_BYTES`).
  - Private trừ VRAM tối đa: 4 GiB (`PRIVATE_MINUS_GPU_MAX_BYTES`).
  - Bộ nhớ dư (residual) sau pha: Giới hạn 2.5 GiB ở chu kỳ đầu (`RESIDUAL_FIRST_CYCLE_MAX_BYTES`), giới hạn 512 MiB ở các chu kỳ sau (`RESIDUAL_LATER_CYCLE_MAX_BYTES`). Nếu vượt ngưỡng, tiến trình dọn dẹp bộ nhớ và từ chối các tác vụ tiếp theo để tránh tràn RAM.

## 6. GIẢ ĐỊNH và Giới hạn

- **Phần cứng GPU:** Lane `lane-imggen-svc` kiểm chứng toàn bộ luồng logic, giao thức, HTTP API, quản lý trọng số và state machine thông qua test suite độc lập `tests/integration/imagegen` (sử dụng `ScriptedBackend`, không cần GPU thật và không gọi mạng ngoài).
- **Mã KleinBackend và vá FP8:** Các hàm `patch_bfl_fp8`, `fp8_self_test`, và cấu hình `from_single_file` là `GIẢ ĐỊNH` cần Control đo đạc và xác thực lại khi chạy thực tế trên phần cứng NVIDIA GPU qua `tests/real/test_imagegen_real.py`.
- **Hai tệp pyproject.toml và uv.lock thuộc gói IMGGEN-DEPS (Finding F1).**
  - `tools/imagegen/pyproject.toml` và `tools/imagegen/uv.lock` là tệp phụ thuộc, chỉ slice phụ thuộc được sửa. Gói `IMGGEN-DEPS` (dependency_slice, mở sau gói này) tạo chúng; IMGGEN-SVC không tạo hay sửa hai tệp này và hai tệp không nằm trong owned paths.
  - Hậu quả: test `test_uv_lock_resolves_the_pins_from_the_cu130_index_with_hashes` chỉ skip (có lý do) khi `tools/imagegen/uv.lock` chưa có và chạy chặt khi tệp có mặt; hai probe `pyproject.toml` và `uv.lock` đã rời khỏi lệnh kiểm của IMGGEN-SVC và do IMGGEN-DEPS chạy.

## 7. Rebase lên integration head 432a6f9ce4bf6f6458c8d9043062006a73e62cdc

Lệnh `git rebase 432a6f9ce4bf6f6458c8d9043062006a73e62cdc` đã rebase thành công 4 commit của lane lên integration head 432a6f9ce4bf6f6458c8d9043062006a73e62cdc; không có xung đột, cây làm việc sạch.

Bảng kết quả các lệnh kiểm tra chạy lại trên mã đã rebase:

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/imagegen -q -p no:cacheprovider` | 0 | Đạt exit 0; dòng tổng kết nguyên văn của pytest: `33 passed, 1 skipped in 5.32s` (test_uv_lock_resolves_the_pins_from_the_cu130_index_with_hashes skip có lý do vì tools/imagegen/uv.lock thuộc IMGGEN-DEPS và chưa có trong worktree). |
| `python -c "import json, pathlib; ... assert got == want"` (probe weights.lock.json kích thước/sha256) | 0 | Đạt exit 0; 25 mục (path, size, sha256) khớp 100% với danh sách ghim. |
| `python -c "import json, pathlib; ... assert set(...) == ..."` (probe weights.lock.json repo/blob) | 0 | Đạt exit 0; repo, revision, component, source.kind, blob_id của 25 mục khớp danh sách ghim. |
| `python -c "import ast, pathlib; ... assert not bad, bad"` (probe AST import nặng) | 0 | Đạt exit 0; không module nào trong `tools/imagegen` import thư viện nặng ở mức module. |
| `python -c "import pathlib; ... assert all(x in p ...) ..."` (probe chuỗi bắt buộc) | 0 | Đạt exit 0; đầy đủ các chuỗi hằng số, tên hàm và cơ chế streaming bắt buộc trong protocol, weights, engine, server, provision. |
| `python -c "import pathlib; ... assert all('def ' + x in a ...) ..."` (probe tên test) | 0 | Đạt exit 0; đủ 17 tên test bắt buộc, có `ScriptedBackend`, không có mock/monkeypatch, hằng số trong `test_imagegen_real.py` khớp. |
| `python -c "import pathlib, re, tomllib; ... assert not miss ... assert not bad, bad"` (probe layout controlplane) | 0 | Đạt exit 0; package-dir của `src/controlplane/pyproject.toml` đủ gói, pytest pythonpath có src, không import tiền tố `src.`. |
| `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/imggen-svc/report.md').read_text(encoding='utf-8'); assert 'IMGGEN-SVC' in t and 'OI-CP7-11-Q2' in t, 'report'"` (probe report.md) | 0 | Đạt exit 0; report.md chứa đầy đủ mã gói `IMGGEN-SVC` và nhóm lỗi `OI-CP7-11-Q2`. |
| `git diff --check` | 0 | Đạt exit 0; không có lỗi khoảng trắng thừa (trailing whitespace sạch). |
