# Báo cáo IMGGEN-DEPS

Mã gói: IMGGEN-DEPS. Nhóm lỗi: OI-CP7-11-Q2 (định nghĩa gốc của Q2 không nằm trong repo; theo spec của task, ghi GIẢ ĐỊNH).

## Phạm vi

Slice phụ thuộc tách từ IMGGEN-SVC theo quyết định Control 02/11/2026; env uv riêng của sidecar sinh ảnh nằm ngoài runtime khoá và Runtime Keeper, torch không vào runtime sản phẩm; Worker không sửa mã hay test của tools/imagegen.

## Tệp đã tạo

| Tệp | SHA-256 | Nguồn / Ghi chú |
| --- | --- | --- |
| 	ools/imagegen/pyproject.toml | 2874bc655d3876b59b61fd535dcb01aa0af2c6ae984375d3a702bc88d401e245 | Chép nguyên văn từ D:/AIAVC_IMGPROTO/ref/imggen-svc/ bằng Copy-Item -LiteralPath |
| 	ools/imagegen/uv.lock | 301f4bfd3043860df880bdfe9f32fbd6bd69af28fbf7245dee8987f3e460353a | Dựng bằng uv lock --offline --project tools/imagegen, không sửa tay |
| 	ests/integration/imagegen/test_imagegen_env.py | 9fcd09b89c0705bae48deba49b916ab0867a9ee5fc8135654fb934d891fd608 | Chép nguyên văn từ D:/AIAVC_IMGPROTO/ref/imggen-svc/ bằng Copy-Item -LiteralPath |
| docs/delivery-evidence/imggen-deps/report.md | - | Do Worker tạo, ghi lại bằng chứng thực thi |

## Đầu ra uv

Đầu ra nguyên văn của uv --version:

`
uv 0.12.13 (0ebbd9274 2026-09-10 x86_64-pc-windows-msvc)
`

Đầu ra nguyên văn của uv lock --offline --project tools/imagegen:

`
Using CPython 3.13.15
Resolved 46 packages in 150ms
`

## Lệnh kiểm đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| Probe kiểm tra pyproject.toml (Bước 3) | 0 | Đúng 10 dependencies, 45 constraint-dependencies, package=false, environments win32, index pytorch-cu130 explicit |
| Probe kiểm tra uv.lock (đủ 46 gói, torch từ cu130, khớp SHA-256) (Bước 5) | 0 | SHA-256 thực tế = 301f4bfd3043860df880bdfe9f32fbd6bd69af28fbf7245dee8987f3e460353a, đúng 46 gói, torch 2.14.1+cu130 từ cu130 registry |
| python -m pytest tests/integration/imagegen/test_imagegen_env.py -q -p no:cacheprovider (Bước 6) | 0 | Dòng tổng kết nguyên văn: 2 passed in 0.03s |
| Probe SHA-256 ba tệp so với bản tham chiếu (Bước 7) | 0 | Tất cả 3 tệp cùng SHA-256 với bản tham chiếu D:/AIAVC_IMGPROTO/ref/imggen-svc, danh sách bad rỗng |
| git diff --check (Bước 8) | 0 | Không có lỗi khoảng trắng |
| Probe nội dung report.md (có IMGGEN-DEPS và OI-CP7-11-Q2) (Bước 10) | 0 | Có mặt chuỗi IMGGEN-DEPS và OI-CP7-11-Q2, assert đạt |
| git diff --check lần cuối (Bước 11) | 0 | Hoàn toàn sạch lỗi khoảng trắng |

## Giới hạn và GIẢ ĐỊNH

- Không chạy uv sync, không tải gói từ mạng ngoài, không dùng GPU.
- Venv sidecar <data>/imagegen/venv do launcher IMGGEN-LAUNCH dựng bằng uv sync --frozen từ khoá này.
- 	ools/imagegen/uv.lock không thuộc vũ trụ runtime khoá config/runtime-universes.json.
