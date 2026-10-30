# Báo cáo bằng chứng chuyển giao: ADAPT-WIRE-FIX2

Nhóm lỗi: `R25`. Milestone: CP7.

## Nguyên nhân

ADAPT-CONFIG-FIX2 (gộp 09:37Z ngày 30/10/2026) nâng `tools/launcher/prod/profile.json` `meta.revision` lên 2 theo quyết định của user cho ROADMAP-OPEN-008 (dung sai mốc từ 200 ms; sổ `user_decisions.json` CLOSURE_NOTE CP7/RG-05). Test `test_profile_loads_typed_values` vẫn khẳng định revision 1. Lỗi lộ ra 30/10/2026 19:56Z khi D-15-FIX1 chạy lệnh kiểm của ADAPT-WIRE. Đây là lỗi do Control gây ra khi lập ADAPT-CONFIG-FIX2.

## Các tệp đã sửa

- `tests/integration/adapt/wire/test_adapt_wire_services.py` (đúng một dòng)
- `docs/delivery-evidence/adapt-wire-fix2/report.md` (tệp này)

## Dòng đã đổi

```diff
-    assert p.revision == 1
+    assert p.revision == 2
```

Lý do: xem mục Nguyên nhân (ADAPT-CONFIG-FIX2, quyết định của user). Không nới khẳng định và không đổi `profile.json`.

## Lệnh kiểm đã chạy

| Lệnh | Mã thoát |
| --- | --- |
| `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` | 0 |
| probe `python -c` xác nhận có `assert p.revision == 2` và không còn `assert p.revision == 1` | 0 |
| probe `python -c` xác nhận report.md nêu `ADAPT-WIRE-FIX2` và `R25` | 0 |
| `git diff --check` | 0 |

Dòng tổng kết pytest nguyên văn:

```
124 passed in 10.84s
```
