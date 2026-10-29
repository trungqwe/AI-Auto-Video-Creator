# CP7-1 — Báo cáo tiền kiểm runtime thật (RG-01)

## Ngữ cảnh

- HEAD sau rebase: `07726cc3a0644d5cbafad9cba2696bf6be7b4073`
- Đầu tích hợp: `07726cc3a0644d5cbafad9cba2696bf6be7b4073`
- Trần chi phí: 0 USD, không gọi AI
- Không đọc `Credentials/`, không sửa `src/**`

## Lệnh đã chạy

- `python -m pytest tests/real/test_cp7_preflight.py -q -p no:cacheprovider`: exit code 0, 58/58 test đạt (51 test đơn vị, 7 test tiền kiểm RG-01)
- `git diff --check`: exit code 0
- Probe `python -c` cuối: exit code 0

## Kết quả RG-01

RG-01.ffmpeg_pin: PASS
RG-01.image_digests: PASS
RG-01.loopback_ports: PASS
RG-01.gpu: PASS
RG-01.disk: PASS
RG-01.router_port: PASS
RG-01.secret_scan: PASS

## Giá trị đo

- ffmpeg_pin: sha256=f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480 path=C:\ffmpeg\bin\ffmpeg.exe
- image_digests: aiavc-postgres sha256=4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280
- image_digests: aiavc-temporal sha256=b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da
- loopback_ports: ports=57028,7233,8443 bind=127.0.0.1 only
- gpu: name=NVIDIA GeForce RTX 4070 SUPER memory_total_mib=12282 threshold_mib=12000
- disk: drive=C:\ free_gib=60.0 threshold_gib=50
- router_port: tcp=127.0.0.1:20128 open
- secret_scan: dpapi_aliases=drive-primary-oauth,router-primary-api-key present (existence only) report_matches=0
