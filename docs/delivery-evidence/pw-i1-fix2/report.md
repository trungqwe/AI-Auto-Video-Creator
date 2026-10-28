# PW-I1-FIX2: verified_version_for_sha tra được version VERIFIED của clip và âm thanh

## Nhóm lỗi

Gói công việc PW-I1-FIX2 sửa nhóm lỗi R10 (phân giải hook): verified_version_for_sha chỉ thử media/<sha>.{png,jpg,jpeg,webp} (handlers.py, dòng 49 và vòng lặp trong hàm) nên hook mp4/wav đã đăng ký không bao giờ tra được; nhóm R9 (lệnh render) và phần thumbnail của R10 nằm ngoài gói này.

## Tệp đã sửa

Liệt kê ba tệp:

1. `src/controlplane/application/storage_meta/handlers.py`: thêm STAGED_HOOK_EXTENSIONS = mp4, mov, webm, wav, mp3, m4a; thêm tham số keyword extensions: tuple[str, ...] = STAGED_IMAGE_EXTENSIONS; mặc định giữ nguyên hành vi; không thêm câu SQL; cập nhật docstring.
2. `tests/integration/prod_wiring/test_pw_i1_materialize.py`: thêm import STAGED_HOOK_EXTENSIONS và test test_verified_version_for_sha_resolves_staged_hook_media_by_extension trên Postgres thật, không monkeypatch.
3. `docs/delivery-evidence/pw-i1-fix2/report.md`: chính báo cáo này.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_i1_materialize.py -q -p no:cacheprovider` | 0 | `14 passed in 6.55s` |
| `git diff --check` | 0 | Không có output (sạch khoảng trắng thừa) |
| `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-i1-fix2/report.md').read_text(encoding='utf-8'); assert 'PW-I1-FIX2' in t and 'R10' in t, 'report'"` | 0 | Khẳng định thành công, báo cáo hợp lệ |

## Phản ví dụ đã loại trừ

- (a) Đổi mặc định thành mọi hậu tố: test khẳng định gọi mặc định trả None cho mp4 và wav.
- (b) Thêm SQL mới: chỉ dùng lại find_version và list_version_locations.
- (c) Trả version không có location VERIFIED: test với location chưa VERIFIED trả None.

## Mục mở

- R9 và phần thumbnail của R10 thuộc gói khác.
